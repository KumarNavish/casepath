"""Private immutable trace admission and public read-only fallback boundaries."""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from casepath_api.autonomous_operation_trace_store_v1 import (
    CHUNK_BYTES, MAX_TRACE_BYTES, OperationTraceError, OperationTraceStore,
    admit_operation_trace, initialize_operation_trace_storage,
)
from casepath_api.autonomous_operations_v1 import build_operation_sidecar, capture_operation_inputs
from casepath_api.autonomous_corpus_v1 import CanonicalCorpus
from casepath_api.autonomous_reference_v1 import ReferenceProfile
from casepath_api.hosted_storage_v1 import JOURNAL_SCHEMA
from test_complete_reference_intake_v1 import admit, service_at


class OperationTraceStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='operation-trace-storage-')
        path = Path(cls.temporary.name) / 'native.sqlite'
        corpus = CanonicalCorpus()
        claim_id = 'clm_0f4f13b1e3e1328c'
        prior = service_at(path, corpus, ReferenceProfile.for_profile('synthetic-nine-v1'))
        try:
            admit(prior, corpus, claim_id)
            before = prior.run(claim_id)
        finally:
            prior.shutdown()
        current = service_at(path, corpus)
        try:
            current.store.add_sources(claim_id, ReferenceProfile().files(claim_id),
                                      expected_revision=before['revision'], expected_state_sha256=before['state_sha256'],
                                      idempotency_key='storage-v2-supplements')
            current.run(claim_id)
            cls.bundle = capture_operation_inputs(current.store, claim_id, current.policy)
            cls.sidecar = build_operation_sidecar(cls.bundle)
        finally:
            current.shutdown()

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.db = sqlite3.connect(':memory:', isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(JOURNAL_SCHEMA)
        columns = ('session_id', 'loop_id', 'sequence', 'idempotency_key',
                   'command_sha256', 'event_sha256', 'event_json', 'created_at')
        self.db.executemany('INSERT INTO claim_loop_events VALUES (?,?,?,?,?,?,?,?)',
                            [tuple(row[key] for key in columns) for row in self.bundle['rows']])
        self.sql, self.before_begin = [], None
        self.db.set_trace_callback(self.sql.append)
        self.reader = OperationTraceStore(self.connect)
        binding = self.sidecar['frames'][0]
        self.identity = {'head_state_sha256': binding['current_state_sha256'],
                         'head_event_sha256': binding['current_event_sha256'],
                         'run_id': binding['run_id'], 'profile_sha256': binding['profile_sha256'],
                         'instrumentation_id': binding['instrumentation_id']}

    def tearDown(self):
        self.db.close()

    @contextmanager
    def connect(self):
        fixture = self
        class Connection:
            def execute(self, sql, args=()):
                if sql == 'BEGIN IMMEDIATE' and fixture.before_begin:
                    callback, fixture.before_begin = fixture.before_begin, None
                    callback()
                return fixture.db.execute(sql, args)
            def executescript(self, sql):
                return fixture.db.executescript(sql)
        try:
            yield Connection()
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def read(self, **overrides):
        return self.reader.read(self.bundle['claim_id'], **{**self.identity, **overrides})

    def initialize(self):
        initialize_operation_trace_storage(self.connect)

    def test_reader_constructor_and_absent_fallback_never_create_or_write(self):
        self.assertEqual(self.sql, [])
        self.assertIsNone(self.read())
        self.assertTrue(all(sql.startswith('SELECT') for sql in self.sql))
        self.assertIsNone(self.db.execute("SELECT name FROM sqlite_master WHERE name='autonomous_operation_traces'").fetchone())

    def test_native_sidecar_admission_is_idempotent_and_preserves_every_journal_row(self):
        self.initialize()
        before = [tuple(row) for row in self.db.execute('SELECT * FROM claim_loop_events ORDER BY sequence')]
        self.assertTrue(admit_operation_trace(self.connect, self.bundle, self.sidecar)['admitted'])
        self.assertEqual(self.read(), self.sidecar)
        self.assertTrue(admit_operation_trace(self.connect, self.bundle, self.sidecar)['idempotent'])
        self.assertEqual(before, [tuple(row) for row in self.db.execute('SELECT * FROM claim_loop_events ORDER BY sequence')])
        self.assertEqual(self.db.execute('SELECT count(*) FROM autonomous_operation_traces').fetchone()[0], 1)
        self.sql.clear()
        self.assertEqual(self.read(), self.sidecar)
        self.assertTrue(all(sql.startswith('SELECT') for sql in self.sql), self.sql)

    def test_stale_head_never_reuses_another_recorded_trace(self):
        self.initialize()
        admit_operation_trace(self.connect, self.bundle, self.sidecar)
        self.assertIsNone(self.read(head_state_sha256='0' * 64))
        self.assertIsNone(self.read(head_event_sha256='1' * 64))
        self.assertIsNone(self.read(profile_sha256='2' * 64))
        self.assertIsNone(self.read(run_id='another-run'))

    def test_recorded_reads_use_terminal_selects_without_a_read_transaction(self):
        self.initialize()
        admit_operation_trace(self.connect, self.bundle, self.sidecar)
        calls, fixture = [], self
        @contextmanager
        def closed_reads():
            class Connection:
                def execute(self, *_):
                    raise AssertionError('recorded read retained a remote stream')
                def execute_read_once(self, sql, args=()):
                    fixture.assertTrue(sql.startswith('SELECT'))
                    fixture.assertFalse(fixture.db.in_transaction)
                    calls.append(sql)
                    return fixture.db.execute(sql, args)
            yield Connection()
        self.sql.clear()
        reader = OperationTraceStore(closed_reads)
        self.assertEqual(reader.read(self.bundle['claim_id'], **self.identity), self.sidecar)
        self.assertGreaterEqual(len(calls), 3)
        self.assertTrue(all(sql.startswith('SELECT') for sql in self.sql))

    def test_new_instrumentation_revision_appends_without_replacing_the_old_trace(self):
        self.initialize()
        admit_operation_trace(self.connect, self.bundle, self.sidecar)
        earlier = tuple(self.db.execute('SELECT * FROM autonomous_operation_traces').fetchone())
        with patch('casepath_api.autonomous_operations_v1.INSTRUMENTATION_ID', 'casepath.reference-operations/2.0.0'):
            newer = build_operation_sidecar(self.bundle)
            self.assertTrue(admit_operation_trace(self.connect, self.bundle, newer)['admitted'])
            self.assertTrue(admit_operation_trace(self.connect, self.bundle, newer)['idempotent'])
            self.assertEqual(self.reader.read(self.bundle['claim_id'], **{key: value for key, value in self.identity.items()
                                                                          if key != 'instrumentation_id'}), newer)
        self.assertEqual(self.read(), self.sidecar)
        self.assertEqual(self.read(instrumentation_id='casepath.reference-operations/2.0.0'), newer)
        self.assertEqual(tuple(self.db.execute('SELECT * FROM autonomous_operation_traces WHERE sidecar_sha256=?',
                                              (self.sidecar['sidecar_sha256'],)).fetchone()), earlier)
        self.assertEqual(self.db.execute('SELECT count(*) FROM autonomous_operation_traces').fetchone()[0], 2)

    def test_changed_source_fails_native_verification_before_any_write(self):
        self.initialize()
        changed = deepcopy(self.bundle)
        digest = next(iter(changed['sources_base64']))
        changed['sources_base64'][digest] = 'YWx0ZXJlZA=='
        self.sql.clear()
        with self.assertRaisesRegex(ValueError, 'source hash differs'):
            admit_operation_trace(self.connect, changed, self.sidecar)
        self.assertFalse(any(sql.startswith(('BEGIN', 'INSERT')) for sql in self.sql))
        self.assertEqual(self.db.execute('SELECT count(*) FROM autonomous_operation_traces').fetchone()[0], 0)

    def test_exact_row_cas_rejects_changed_older_event_with_unchanged_head(self):
        self.initialize()
        def changed():
            self.db.execute("UPDATE claim_loop_events SET created_at='altered' WHERE sequence=1")
        self.before_begin = changed
        with self.assertRaisesRegex(OperationTraceError, 'journal changed'):
            admit_operation_trace(self.connect, self.bundle, self.sidecar)
        self.assertEqual(self.db.execute('SELECT count(*) FROM autonomous_operation_traces').fetchone()[0], 0)

    def test_native_verification_finishes_before_ownership_transaction(self):
        self.initialize()
        from casepath_api.autonomous_operations_v1 import verify_operation_sidecar
        def verify(bundle, sidecar):
            self.assertFalse(self.db.in_transaction)
            self.assertFalse(any(sql.startswith('BEGIN') for sql in self.sql))
            return verify_operation_sidecar(bundle, sidecar)
        self.sql.clear()
        with patch('casepath_api.autonomous_operations_v1.verify_operation_sidecar', side_effect=verify):
            self.assertTrue(admit_operation_trace(self.connect, self.bundle, self.sidecar)['admitted'])

    def test_existing_trace_header_chunks_and_conflicting_replace_are_immutable(self):
        self.initialize()
        admit_operation_trace(self.connect, self.bundle, self.sidecar)
        for sql in ('UPDATE autonomous_operation_traces SET input_sha256=\'changed\'',
                    'DELETE FROM autonomous_operation_traces',
                    'DELETE FROM autonomous_operation_trace_chunks',
                    "UPDATE autonomous_operation_trace_chunks SET content=x'00'",
                    'INSERT OR REPLACE INTO autonomous_operation_traces SELECT * FROM autonomous_operation_traces',
                    'INSERT OR REPLACE INTO autonomous_operation_trace_chunks SELECT * FROM autonomous_operation_trace_chunks'):
            with self.assertRaisesRegex(sqlite3.IntegrityError, 'immutable'):
                self.db.execute(sql)
        values = dict(self.db.execute('SELECT * FROM autonomous_operation_traces').fetchone())
        values['sidecar_sha256'] = 'a' * 64
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'immutable'):
            self.db.execute('INSERT OR REPLACE INTO autonomous_operation_traces VALUES (' + ','.join('?' for _ in values) + ')', tuple(values.values()))

    def test_corrupted_chunk_and_oversized_header_are_rejected_before_decode(self):
        self.initialize()
        admit_operation_trace(self.connect, self.bundle, self.sidecar)
        self.db.execute('DROP TRIGGER autonomous_operation_traces_no_update')
        self.db.execute('UPDATE autonomous_operation_traces SET content_bytes=?', (MAX_TRACE_BYTES + 1,))
        self.sql.clear()
        with self.assertRaisesRegex(OperationTraceError, 'size is invalid'):
            self.read()
        self.assertFalse(any('FROM autonomous_operation_trace_chunks' in sql for sql in self.sql))
        self.db.execute('UPDATE autonomous_operation_traces SET content_bytes=?',
                        (len(json.dumps(self.sidecar, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()),))
        self.db.execute('DROP TRIGGER autonomous_operation_trace_chunks_no_update')
        self.db.execute("UPDATE autonomous_operation_trace_chunks SET content=x'00' WHERE chunk_index=0")
        with self.assertRaisesRegex(OperationTraceError, 'trace (chunk|bytes) differs'):
            self.read()

    def test_cancelled_recorded_read_never_fetches_another_chunk_page(self):
        self.initialize()
        admit_operation_trace(self.connect, self.bundle, self.sidecar)
        self.sql.clear()
        def check():
            if any('FROM autonomous_operation_trace_chunks' in sql for sql in self.sql):
                raise RuntimeError('recorded read cancelled')
        with self.assertRaisesRegex(RuntimeError, 'read cancelled'):
            self.read(check=check)
        self.assertEqual(sum('FROM autonomous_operation_trace_chunks' in sql for sql in self.sql), 1)
        self.assertTrue(all(sql.startswith('SELECT') for sql in self.sql))
