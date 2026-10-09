"""Optimistic append contract checks; SQLite memory only, no model/provider."""
from pathlib import Path
import json
import sqlite3
from threading import RLock
import unittest
from uuid import uuid4

from casepath_api.autonomous_store_v1 import AutonomousStoreError
from casepath_api.hosted_lease_v1 import HostedOwnershipLost, HostedWorkflowLease, _CURRENT_OWNER
from casepath_api.hosted_storage_v1 import HostedAutonomousStore, HostedJournal, HostedSources


class TrackedConnection:
    def __init__(self, raw, fixture):
        self.raw, self.fixture = raw, fixture

    def __getattr__(self, name):
        return getattr(self.raw, name)

    def execute(self, sql, args=()):
        beginning = sql.strip().upper().startswith('BEGIN')
        if beginning and self.fixture.before_begin is not None:
            callback, self.fixture.before_begin = self.fixture.before_begin, None
            callback()
        result = self.raw.execute(sql, args)
        if beginning:
            self.fixture.active += 1
        return result

    def commit(self):
        active = self.raw.in_transaction
        self.raw.commit()
        self.fixture.active -= int(active)

    def rollback(self):
        active = self.raw.in_transaction
        self.raw.rollback()
        self.fixture.active -= int(active)

    def close(self):
        self.rollback()
        self.raw.close()

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        try:
            self.commit() if kind is None else self.rollback()
        finally:
            self.close()


class HostedAppendTests(unittest.TestCase):
    def setUp(self):
        self.uri = 'file:append-' + uuid4().hex + '?mode=memory&cache=shared'
        self.keeper = sqlite3.connect(self.uri, uri=True, isolation_level=None)
        self.active, self.before_begin, self.probes = 0, None, []
        self.lease = HostedWorkflowLease(self.connect)
        self.lease.initialize()
        self.journal = HostedJournal(Path('/unused'), self.lease.connect)
        fixture = self
        class Sources(HostedSources):
            def read(self, digest):
                fixture.assertEqual(fixture.active, 0, 'source read held a write transaction')
                fixture.probes.append('source')
                return super().read(digest)
        class Store(HostedAutonomousStore):
            def _replay(self, rows, **options):
                fixture.assertEqual(fixture.active, 0, 'replay held a write transaction')
                fixture.probes.append('replay')
                return super()._replay(rows, **options)
            def _reduce(self, state, event):
                fixture.assertEqual(fixture.active, 0, 'reduction held a write transaction')
                fixture.probes.append('reduce')
                return super()._reduce(state, event)
        self.store_type, self.sources = Store, Sources(self.lease.connect)
        self.store, self.peer = self.new_store(), self.new_store()
        self.first = self.store.intake({'title': 'Fictional packet', 'message': 'Original source.', 'files': []},
                                       'optimistic-intake')
        self.claim = self.first['claim_id']
        self.command = {'claim_id': self.claim, 'kind': 'work.phase',
                        'payload': {'phase': 'queued', 'summary': 'Preparing source work.'},
                        'expected_revision': self.first['revision'],
                        'expected_state_sha256': self.first['state_sha256'],
                        'idempotency_key': 'optimistic-phase'}

    def tearDown(self):
        self.assertEqual(self.active, 0)
        self.keeper.close()

    def connect(self):
        raw = sqlite3.connect(self.uri, uri=True, isolation_level=None)
        raw.row_factory = sqlite3.Row
        return TrackedConnection(raw, self)

    def new_store(self):
        store = self.store_type.__new__(self.store_type)
        store._read_only, store.storage = False, None
        store.journal, store._source_store = self.journal, self.sources
        store.path, store.source_root = Path('/unused'), Path('/unused')
        store._extractions, store._extraction_lock = {}, RLock()
        return store

    def test_full_replay_sources_and_new_reduction_stay_outside_transaction(self):
        self.probes.clear()
        result = self.store.append(**self.command)
        self.assertEqual(result['revision'], 2)
        self.assertTrue({'replay', 'source', 'reduce'} <= set(self.probes))
        self.assertEqual(self.store.get(self.claim), result)
        self.assertEqual(self.store.append(**self.command), result)

    def test_stale_competing_write_is_not_overwritten(self):
        competing = {**self.command, 'idempotency_key': 'different-phase',
                     'payload': {'phase': 'other', 'summary': 'Another accepted writer.'}}
        self.before_begin = lambda: self.peer.append(**competing)
        with self.assertRaisesRegex(AutonomousStoreError, 'stale claim revision'):
            self.store.append(**self.command)
        self.assertEqual([row['idempotency_key'] for row in self.store.events(self.claim)],
                         ['optimistic-intake', 'different-phase'])

    def test_identical_concurrent_retry_returns_original_saved_state(self):
        winner = []
        self.before_begin = lambda: winner.append(self.peer.append(**self.command))
        result = self.store.append(**self.command)
        self.assertEqual(result, winner[0])
        self.assertEqual(len(self.store.events(self.claim)), 2)
        with self.assertRaisesRegex(AutonomousStoreError, 'idempotency key binds different input'):
            self.store.append(**{**self.command, 'payload': {'phase': 'changed', 'summary': 'Different input.'}})

    def test_full_snapshot_detects_old_row_tampering_with_unchanged_head(self):
        def tamper():
            row = self.keeper.execute('SELECT event_json FROM claim_loop_events WHERE sequence=1').fetchone()
            event = json.loads(row[0])
            event['payload']['title'] = 'Changed without changing the head or hash column'
            self.keeper.execute('UPDATE claim_loop_events SET event_json=? WHERE sequence=1',
                                (json.dumps(event),))
        self.before_begin = tamper
        with self.assertRaisesRegex(AutonomousStoreError, 'journal event identity or hash differs'):
            self.store.append(**self.command)
        self.assertEqual(self.keeper.execute('SELECT COUNT(*) FROM claim_loop_events').fetchone()[0], 1)

    def test_second_snapshot_race_stops_after_one_reprepare(self):
        races = []
        def first_race():
            races.append(1)
            winner = self.peer.append(**self.command)
            def second_race():
                races.append(2)
                self.peer.append(self.claim, 'work.phase', {'phase': 'later', 'summary': 'Later accepted work.'},
                    expected_revision=winner['revision'], expected_state_sha256=winner['state_sha256'],
                    idempotency_key='later-phase')
            self.before_begin = second_race
        self.before_begin = first_race
        with self.assertRaisesRegex(AutonomousStoreError, 'stale claim revision'):
            self.store.append(**self.command)
        self.assertEqual(races, [1, 2])
        self.assertEqual(len(self.store.events(self.claim)), 3)

    def test_lease_loss_between_prepare_and_begin_fences_the_insert(self):
        token = self.lease.acquire()
        reset = _CURRENT_OWNER.set(token)
        try:
            self.before_begin = lambda: self.keeper.execute('UPDATE hosted_workflow_lease SET expires_at=0')
            with self.assertRaises(HostedOwnershipLost):
                self.store.append(**self.command)
        finally:
            _CURRENT_OWNER.reset(reset)
            self.lease.release(token)
        self.assertEqual(len(self.store.events(self.claim)), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
