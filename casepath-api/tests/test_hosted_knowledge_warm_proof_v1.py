"""Fresh, typed database proofs reuse only completely validated native bytes."""
import base64
from copy import deepcopy
from hashlib import sha256
import json
import sqlite3

import httpx
import pytest

from casepath_api.autonomous_knowledge_v1 import AutonomousKnowledge
from casepath_api.autonomous_store_v1 import AutonomousStore, AutonomousStoreError, SESSION_ID
from casepath_api.hosted_storage_v1 import HostedAutonomousStore, HostedJournal, HostedSources, HostedStorageError
from casepath_api.hosted_sql_v1 import _decode
from hosted_hrana_fixture import MockHrana


class ProofHrana(MockHrana):
    def __init__(self, path):
        super().__init__(path)
        self.wire_bytes, self.raw_journal, self.raw_sources = [], [], []
        self.raw_http_policy = []

    def _statement(self, connection, statement):
        result = super()._statement(connection, statement)
        names = [column['name'] for column in result['cols']]
        if 'event_json' in names:
            self.raw_journal.append((statement, len(result['rows'])))
        if 'content' in names:
            self.raw_sources.append((statement, len(result['rows'])))
        return result

    def handle(self, request):
        commands = [item.get('stmt', {}).get('sql', '') for item in json.loads(request.content)['requests']]
        raw = any('CROSS JOIN claim_loop_events AS j' in sql or sql.startswith('SELECT sha256,chunk_index')
                  for sql in commands)
        self.raw_http_policy.append((raw, request.headers.get('connection')))
        response = super().handle(request)
        self.wire_bytes.append(len(response.content))
        return response

    def reset(self):
        self.requests.clear()
        self.wire_bytes.clear()
        self.raw_journal.clear()
        self.raw_sources.clear()
        self.raw_http_policy.clear()


@pytest.fixture
def native_proof_store(tmp_path, monkeypatch):
    native = AutonomousStore(tmp_path / 'native.sqlite3')
    original_file = b'Isolated synthetic original attachment.\n' * 7500
    for index in range(2):
        native.intake({'title': f'Native proof fixture {index}', 'message': f'Original statement {index}. ' * 500,
                       'files': [{'file_name': 'original.txt', 'media_type': 'text/plain',
                                  'content_base64': base64.b64encode(original_file).decode()}]}, f'proof.intake.{index}')
    server = ProofHrana(tmp_path / 'hosted.sqlite3')
    journal = HostedJournal(tmp_path / 'unused', server.connection)
    with sqlite3.connect(native.path) as source, sqlite3.connect(server.path) as target:
        target.executemany('INSERT INTO claim_loop_events VALUES (?,?,?,?,?,?,?,?)',
                           source.execute('SELECT * FROM claim_loop_events').fetchall())
        for path in native.source_root.iterdir():
            raw = path.read_bytes()
            target.executemany('INSERT INTO autonomous_source_chunks VALUES (?,?,?)',
                               [(path.name, index, raw[offset:offset + HostedSources.CHUNK_BYTES])
                                for index, offset in enumerate(range(0, len(raw), HostedSources.CHUNK_BYTES))])
    store = HostedAutonomousStore(journal.path, journal=journal, source_store=HostedSources(server.connection))
    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', lambda *a, **k: pytest.fail('Unexpected provider/network dispatch'))
    server.reset()
    yield server, store, AutonomousKnowledge(store, {})
    server.close()


def test_cold_population_keeps_prior_128_row_and_eight_chunk_raw_pages(native_proof_store):
    server, _, knowledge = native_proof_store
    knowledge.learning_view()
    assert server.raw_journal and server.raw_sources
    for statement, _ in server.raw_journal:
        arguments = [_decode(value) for value in statement.get('args', [])]
        assert arguments[-2] == 128
    assert all('LIMIT 8' in statement['sql'] for statement, _ in server.raw_sources)


def test_warm_read_has_one_final_atomic_proof_without_raw_bytes_or_writes(native_proof_store, monkeypatch):
    server, store, knowledge = native_proof_store
    original = knowledge.learning_view()
    server.reset()
    monkeypatch.setattr(store, '_replay', lambda *a, **k: pytest.fail('Unchanged journal replayed'))
    assert knowledge.learning_view() == original
    assert len(server.requests) == 1
    assert not server.raw_journal and not server.raw_sources
    assert sum(server.wire_bytes) < 16 * 1024
    for request in server.requests:
        operations = request['requests']
        assert [operation['type'] for operation in operations] == ['execute'] * 6 + ['close']
        assert operations[0]['stmt']['sql'] == 'BEGIN' and operations[-2]['stmt']['sql'] == 'COMMIT'
        assert all(operation['stmt']['sql'].startswith('SELECT') for operation in operations[1:-2])
    assert server.open_streams == 0


@pytest.mark.parametrize('domain', ['journal', 'source'])
def test_final_atomic_proof_follows_all_local_validation(native_proof_store, monkeypatch, domain):
    server, store, knowledge = native_proof_store
    knowledge.learning_view()
    validate, changed = store._validate_descriptor, []

    def mutate_after_local_source_check(descriptor, claim_id):
        result = validate(descriptor, claim_id)
        if not changed:
            changed.append(True)
            with sqlite3.connect(server.path) as db:
                if domain == 'journal':
                    db.execute("UPDATE claim_loop_events SET created_at='changed after local byte validation'")
                else:
                    db.execute('DROP TRIGGER autonomous_source_chunks_no_update')
                    db.execute('UPDATE autonomous_source_chunks SET content=? WHERE sha256=? AND chunk_index=0',
                               (b'Changed after local byte validation.', descriptor['sha256']))
        return result

    monkeypatch.setattr(store, '_validate_descriptor', mutate_after_local_source_check)
    server.reset()
    with pytest.raises(AutonomousStoreError):
        knowledge.learning_view()
    first = [operation.get('stmt', {}).get('sql', '') for operation in server.requests[0]['requests']]
    assert any('casepath-journal-bytes-v1:set:' in sql for sql in first)
    assert any('casepath-source-bytes-v1:set:' in sql for sql in first)
    assert changed and server.open_streams == 0


@pytest.mark.parametrize('column', ['event_json', 'created_at', 'command_sha256', 'idempotency_key'])
def test_unchanged_heads_cannot_hide_an_earlier_row_mutation(native_proof_store, column):
    server, _, knowledge = native_proof_store
    knowledge.learning_view()
    with sqlite3.connect(server.path) as db:
        if column == 'event_json':
            value = json.loads(db.execute('SELECT event_json FROM claim_loop_events LIMIT 1').fetchone()[0])
            value['payload']['title'] = 'A tampered fixture title.'
            value = json.dumps(value)
        else:
            value = 'unaccepted replacement'
        db.execute('UPDATE claim_loop_events SET ' + column + '=? WHERE loop_id=(SELECT loop_id FROM claim_loop_events LIMIT 1)', (value,))
    server.reset()
    with pytest.raises(AutonomousStoreError, match='journal event identity or hash differs'):
        knowledge.learning_view()
    assert server.raw_journal


@pytest.mark.parametrize('mutation', ['changed', 'deleted', 'extra_empty', 'wrong_type'])
def test_fresh_source_proof_requires_exact_persisted_chunks(native_proof_store, mutation):
    server, store, knowledge = native_proof_store
    knowledge.learning_view()
    digest = next(digest for digest, raw in store._source_store._cache.items() if len(raw) > HostedSources.CHUNK_BYTES)
    with sqlite3.connect(server.path) as db:
        if mutation in {'changed', 'wrong_type'}:
            db.execute('DROP TRIGGER autonomous_source_chunks_no_update')
            db.execute('UPDATE autonomous_source_chunks SET content=? WHERE sha256=? AND chunk_index=1',
                       ('wrong SQL type' if mutation == 'wrong_type' else b'changed final bytes', digest))
        elif mutation == 'deleted':
            db.execute('DROP TRIGGER autonomous_source_chunks_no_delete')
            db.execute('DELETE FROM autonomous_source_chunks WHERE sha256=? AND chunk_index=1', (digest,))
        else:
            db.execute('INSERT INTO autonomous_source_chunks VALUES (?,?,?)', (digest, 2, b''))
    server.reset()
    with pytest.raises(AutonomousStoreError, match='source|bytes|chunk|hash'):
        knowledge.learning_view()
    assert server.raw_sources


def test_unknown_journal_columns_fail_closed_without_partial_column_certificate(native_proof_store):
    server, _, knowledge = native_proof_store
    original = knowledge.learning_view()
    with sqlite3.connect(server.path) as db:
        db.execute("ALTER TABLE claim_loop_events ADD COLUMN unknown_authority TEXT DEFAULT 'original'")
    for value in ('original', 'changed'):
        with sqlite3.connect(server.path) as db:
            db.execute('UPDATE claim_loop_events SET unknown_authority=?', (value,))
        server.reset()
        with pytest.raises(AutonomousStoreError, match='complete native journal schema'):
            knowledge.learning_view()
        assert server.raw_journal


@pytest.mark.parametrize('phase', ['SELECT', 'COMMIT'])
def test_unconfirmed_warm_proof_never_returns_a_cached_projection(native_proof_store, phase):
    server, _, knowledge = native_proof_store
    knowledge.learning_view()
    server.reset()
    server.fail_next('timeout', sql_prefix=phase)
    with pytest.raises(HostedStorageError, match='unconfirmed'):
        knowledge.learning_view()


def test_failed_final_source_validation_never_admits_journal_byte_cache(native_proof_store, monkeypatch):
    server, store, knowledge = native_proof_store
    verify = store._source_store.verify_knowledge_many
    monkeypatch.setattr(store._source_store, 'verify_knowledge_many',
                        lambda *a: (_ for _ in ()).throw(AutonomousStoreError('Isolated final source refusal.')))
    with pytest.raises(AutonomousStoreError, match='final source refusal'):
        knowledge.learning_view()
    assert store._summary_cache  # Native reducer caching precedes final verification.
    assert getattr(store, '_knowledge_byte_cache', None) is None
    monkeypatch.setattr(store._source_store, 'verify_knowledge_many', verify)
    server.reset()
    knowledge.learning_view()
    assert server.raw_journal
    assert store._knowledge_byte_cache is not None


def test_evicted_original_bytes_require_raw_read_before_fresh_source_proof(native_proof_store):
    server, store, knowledge = native_proof_store
    original = knowledge.learning_view()
    sources = store._source_store
    with sources._lock:
        sources._cache.clear()
        sources._size = 0
    server.reset()
    assert knowledge.learning_view() == original
    assert not server.raw_journal and server.raw_sources
    assert 'casepath-source-bytes-v1:set:' in server.requests[-1]['requests'][2]['stmt']['sql']


def test_cold_collected_values_must_match_final_snapshot_before_replay(native_proof_store, monkeypatch):
    server, store, knowledge = native_proof_store
    original_handle, changed = server.handle, []

    def mutate_closed_page(request):
        response = original_handle(request)
        if server.raw_journal and not changed:
            assert server.open_streams == 0
            changed.append(True)
            with sqlite3.connect(server.path) as db:
                db.execute("UPDATE claim_loop_events SET created_at='changed after closed raw page'")
        return response

    monkeypatch.setattr(server, 'handle', mutate_closed_page)
    monkeypatch.setattr(store, '_replay', lambda *a, **k: pytest.fail('Uncertified collection reached replay'))
    with pytest.raises(AutonomousStoreError, match='changed while collecting'):
        knowledge.learning_view()
    assert changed and getattr(store, '_knowledge_byte_cache', None) is None


def test_cold_unconfirmed_closed_page_never_admits_or_replays(native_proof_store, monkeypatch):
    server, store, knowledge = native_proof_store
    server.fail_next('timeout', sql_prefix='COMMIT')
    monkeypatch.setattr(store, '_replay', lambda *a, **k: pytest.fail('Unconfirmed page reached replay'))
    with pytest.raises(HostedStorageError, match='unconfirmed'):
        knowledge.learning_view()
    assert getattr(store, '_knowledge_byte_cache', None) is None and server.open_streams == 0


@pytest.mark.parametrize('mutation', ['session', 'loop', 'sequence', 'event_hash', 'real_sequence', 'text_blob', 'nul'])
def test_every_typed_journal_column_and_full_roster_remain_authority(native_proof_store, mutation):
    server, _, knowledge = native_proof_store
    knowledge.learning_view()
    column, value = {'session': ('session_id', 'other.session'), 'loop': ('loop_id', 'autonomous.changed'),
                     'sequence': ('sequence', 99), 'event_hash': ('event_sha256', '0' * 64),
                     'real_sequence': ('sequence', 1.5), 'text_blob': ('created_at', b'blob timestamp'),
                     'nul': ('created_at', 'original\0suffix')}[mutation]
    with sqlite3.connect(server.path) as db:
        db.execute('UPDATE claim_loop_events SET ' + column + '=? WHERE rowid=(SELECT rowid FROM claim_loop_events LIMIT 1)', (value,))
    server.reset()
    with pytest.raises(AutonomousStoreError):
        knowledge.learning_view()
    assert server.raw_journal


@pytest.mark.parametrize('schema', ['generated', 'view'])
def test_hidden_columns_and_views_never_enter_standard_column_proof_cache(native_proof_store, schema):
    server, store, knowledge = native_proof_store
    original = knowledge.learning_view()
    with sqlite3.connect(server.path) as db:
        if schema == 'generated':
            db.execute("ALTER TABLE claim_loop_events ADD COLUMN extra_generated TEXT GENERATED ALWAYS AS ('hidden') VIRTUAL")
        else:
            db.execute('ALTER TABLE claim_loop_events RENAME TO original_events')
            db.execute('CREATE VIEW claim_loop_events AS SELECT * FROM original_events')
    for _ in range(2):
        server.reset()
        with pytest.raises(AutonomousStoreError, match='complete native journal schema'):
            knowledge.learning_view()
        assert server.raw_journal and store._knowledge_byte_cache is None


def test_empty_roster_has_a_distinct_certified_cache_and_no_source_read(native_proof_store):
    server, store, knowledge = native_proof_store
    with sqlite3.connect(server.path) as db:
        db.execute('DELETE FROM claim_loop_events')
    original = knowledge.learning_view()
    assert original['learning_replay']['journal_heads'] == []
    assert store._knowledge_byte_cache is not None
    server.reset()
    assert knowledge.learning_view() == original
    assert len(server.requests) == 1 and not server.raw_journal and not server.raw_sources


def test_sql_aggregate_order_and_raw_byte_encoding_match_local_fixed_vectors():
    from casepath_api.hosted_storage_v1 import _JOURNAL_COLUMNS, _proof_expected, _proof_query, _proof_matches
    rows = [dict(zip(_JOURNAL_COLUMNS, [SESSION_ID, loop, sequence, 'key\0suffix', 'é\0字', 'hash', '{}\n', 'at']))
            for loop, sequence in [('autonomous.é', 2 ** 63 - 1), ('autonomous.a', -(2 ** 63)), ('autonomous.字', 0)]]
    rows.sort(key=lambda row: (row['loop_id'], row['sequence']))
    expected = _proof_expected(rows, _JOURNAL_COLUMNS, 'casepath-journal-bytes-v1')
    query = _proof_query('claim_loop_events', _JOURNAL_COLUMNS, 'casepath-journal-bytes-v1', 'session_id=?', 'loop_id,sequence')
    with sqlite3.connect(':memory:') as db:
        db.row_factory = sqlite3.Row
        db.create_function('crypto_sha256', 1, lambda raw: sha256(raw).digest())
        db.execute('CREATE TABLE claim_loop_events (session_id TEXT,loop_id TEXT,sequence INTEGER,idempotency_key TEXT,'
                   'command_sha256 TEXT,event_sha256 TEXT,event_json TEXT,created_at TEXT)')
        for reverse in (False, True):
            db.execute('DELETE FROM claim_loop_events')
            db.executemany('INSERT INTO claim_loop_events VALUES (?,?,?,?,?,?,?,?)',
                           [tuple(row[name] for name in _JOURNAL_COLUMNS) for row in (reversed(rows) if reverse else rows)])
            for unordered in (0, 1):
                db.execute('PRAGMA reverse_unordered_selects=' + str(unordered))
                assert _proof_matches(db.execute(query, (SESSION_ID, len(rows) + 1)), expected)
        db.execute("UPDATE claim_loop_events SET loop_id='autonomous.changed' WHERE sequence=0")
        assert not _proof_matches(db.execute(query, (SESSION_ID, len(rows) + 1)), expected)
        db.execute('DELETE FROM claim_loop_events')
        assert _proof_matches(db.execute(query, (SESSION_ID, 1)),
                              _proof_expected([], _JOURNAL_COLUMNS, 'casepath-journal-bytes-v1'))
        with pytest.raises(ValueError, match='exact native SQL storage types'):
            _proof_expected([{**rows[0], 'sequence': 1.0}], _JOURNAL_COLUMNS, 'casepath-journal-bytes-v1')


@pytest.mark.parametrize('fault', ['null', 'short', 'truncated_concat', 'wrong_count'])
def test_malformed_or_truncated_aggregate_cannot_accept_cached_rows(native_proof_store, monkeypatch, fault):
    server, _, knowledge = native_proof_store
    knowledge.learning_view()
    statement = server._statement

    def broken_result(connection, command):
        result = statement(connection, command)
        if 'casepath-journal-bytes-v1:set:' in command['sql']:
            names = [column['name'] for column in result['cols']]
            name, value = {'null': ('root', None), 'short': ('root', 'ab'),
                           'truncated_concat': ('concat_bytes', 0), 'wrong_count': ('valid_n', 0)}[fault]
            result['rows'][0][names.index(name)] = server._value(value)
        return result

    monkeypatch.setattr(server, '_statement', broken_result)
    with pytest.raises(AutonomousStoreError, match='malformed or truncated'):
        knowledge.learning_view()


def test_changed_source_schema_forces_raw_eight_chunk_refresh_and_new_final_certificate(native_proof_store):
    server, store, knowledge = native_proof_store
    original = knowledge.learning_view()
    previous = store._source_store._knowledge_schema
    with sqlite3.connect(server.path) as db:
        db.execute('CREATE INDEX fixture_extra_source_index ON autonomous_source_chunks(chunk_index)')
    server.reset()
    assert knowledge.learning_view() == original
    assert server.raw_sources and not server.raw_journal
    assert all('LIMIT 8' in statement['sql'] for statement, _ in server.raw_sources)
    assert store._source_store._knowledge_schema != previous
    server.reset()
    assert knowledge.learning_view() == original and len(server.requests) == 1
    assert not server.raw_sources


@pytest.mark.parametrize('field', ['type', 'name'])
def test_fresh_schema_result_types_and_column_names_cannot_alias_cached_schema(native_proof_store, monkeypatch, field):
    server, _, knowledge = native_proof_store
    knowledge.learning_view()
    statement, changed = server._statement, []

    def malformed_schema(connection, command):
        result = statement(connection, command)
        if "pragma_table_xinfo('claim_loop_events')" in command['sql'] and not changed:
            changed.append(True)
            names = [column['name'] for column in result['cols']]
            if field == 'name':
                result['cols'][names.index('required')]['name'] = 'different_required'
            else:
                offset = names.index('required')
                for row in result['rows']:
                    if _decode(row[offset]) == 1:
                        row[offset] = server._value(1.0)
        return result

    monkeypatch.setattr(server, '_statement', malformed_schema)
    server.reset()
    knowledge.learning_view()  # Confirmed schema miss may take the full raw path.
    assert changed and server.raw_journal


def test_cold_journal_byte_budget_is_256k_before_full_payload_materialization(native_proof_store):
    server, _, knowledge = native_proof_store
    # Whitespace preserves exact parsed native events and their sealed hashes,
    # while exercising actual persisted UTF-8 payload size rather than tiny rows.
    with sqlite3.connect(server.path) as db:
        db.execute('UPDATE claim_loop_events SET event_json=event_json||?', (' ' * 150000,))
    knowledge.learning_view()
    assert len(server.raw_journal) >= 3
    for statement, count in server.raw_journal:
        arguments = [_decode(value) for value in statement.get('args', [])]
        assert arguments[-1] == 256 * 1024
        assert 'CROSS JOIN claim_loop_events AS j' in statement['sql']
        assert 'SELECT session_id,loop_id,sequence,' in statement['sql']
        assert count <= 128


def test_certified_row_cache_is_immutable_and_returned_rows_cannot_replace_persisted_head(native_proof_store):
    server, store, knowledge = native_proof_store
    original = knowledge.learning_view()
    rows = store._knowledge_rows()
    # A wholly valid, separately persisted native replacement must not become
    # authority merely by replacing an object returned from the certified cache.
    replacement = AutonomousStore(store.path.parent / 'replacement-native.sqlite3')
    replacement.intake({'title': 'Different fully valid fixture', 'message': 'Original different evidence.'}, 'replacement.intake')
    with sqlite3.connect(replacement.path) as db:
        db.row_factory = sqlite3.Row
        other = [dict(row) for row in db.execute('SELECT * FROM claim_loop_events ORDER BY loop_id,sequence')]
    rows[:] = other
    frozen = store._knowledge_byte_cache[0]
    assert type(frozen) is tuple and all(type(row) is tuple for row in frozen)
    assert rows[0]['loop_id'] != dict(frozen[0])['loop_id']
    assert knowledge.learning_view() == original


def test_failed_validation_then_legacy_reader_cannot_promote_old_pending_certificate(native_proof_store, monkeypatch):
    server, store, knowledge = native_proof_store
    verify = store._source_store.verify_knowledge_many
    monkeypatch.setattr(store._source_store, 'verify_knowledge_many',
                        lambda *a: (_ for _ in ()).throw(AutonomousStoreError('Isolated pending refusal.')))
    with pytest.raises(AutonomousStoreError, match='pending refusal'):
        knowledge.learning_view()
    assert store._knowledge_pending is not None and store._knowledge_byte_cache is None
    monkeypatch.setattr(store._source_store, 'verify_knowledge_many', verify)

    def sqlite_connection():
        db = sqlite3.connect(server.path)
        db.row_factory = sqlite3.Row
        return db

    monkeypatch.setattr(store.journal, 'connect', sqlite_connection)
    knowledge.learning_view()
    assert store._knowledge_pending is None and store._knowledge_byte_cache is None


def test_post_validation_admission_rejects_different_fully_valid_native_rows(native_proof_store, monkeypatch):
    server, store, knowledge = native_proof_store
    replacement = AutonomousStore(store.path.parent / 'alternative-native.sqlite3')
    expected_state = replacement.intake({'title': 'Alternative fully valid native claim',
        'message': 'Distinct original source bytes for the alternate valid journal.'}, 'alternate.intake')
    with sqlite3.connect(replacement.path) as db:
        db.row_factory = sqlite3.Row
        other = [dict(row) for row in db.execute('SELECT * FROM claim_loop_events ORDER BY loop_id,sequence')]
    with sqlite3.connect(server.path) as db:
        for digest in {source['sha256'] for source in expected_state['source_descriptors']}:
            raw = (replacement.source_root / digest).read_bytes()
            db.execute('INSERT INTO autonomous_source_chunks SELECT ?,?,? WHERE NOT EXISTS '
                       '(SELECT 1 FROM autonomous_source_chunks WHERE sha256=? AND chunk_index=0)',
                       (digest, 0, raw, digest))
    collect = store._knowledge_rows

    def substitute_after_certificate():
        collect()  # Certifies actual persisted DB rows, not the alternative.
        return deepcopy(other)

    monkeypatch.setattr(store, '_knowledge_rows', substitute_after_certificate)
    with pytest.raises(AutonomousStoreError, match='Certified journal bytes differ'):
        knowledge.learning_view()
    # The replacement was valid and completely reduced; only exact certificate
    # binding prevents its unpersisted head from becoming the projected result.
    assert store._summary_cache[expected_state['claim_id']][1] == expected_state
    assert store._knowledge_byte_cache is None and store._knowledge_pending is None


@pytest.mark.parametrize('first', ['summaries', 'knowledge'])
def test_claim_summaries_and_knowledge_share_only_fully_certified_states(native_proof_store, first):
    server, store, knowledge = native_proof_store
    native = AutonomousStore.open_read_only(store.path.parent / 'native.sqlite3')
    expected = native.list_summaries()
    initial = store.list_summaries() if first == 'summaries' else knowledge.learning_view()
    assert initial == expected if first == 'summaries' else initial['learning_replay']['journal_heads']
    server.reset()
    if first == 'summaries':
        assert len(knowledge.learning_view()['learning_replay']['journal_heads']) == len(expected)
    else:
        assert store.list_summaries() == expected
    assert len(server.requests) == 1 and not server.raw_journal and not server.raw_sources
    returned = store.list_summaries(statuses={expected[0]['status']})
    assert returned == [state for state in expected if state['status'] == expected[0]['status']]
    returned[0]['title'] = 'Caller-only mutation'
    assert store.list_summaries() == expected


def test_concurrent_claim_and_knowledge_reads_keep_ordered_certification_and_reject_mutation(native_proof_store):
    from concurrent.futures import ThreadPoolExecutor
    server, store, knowledge = native_proof_store
    original = knowledge.learning_view()
    server.reset()
    with ThreadPoolExecutor(max_workers=2) as executor:
        a, b = executor.submit(store.list_summaries), executor.submit(knowledge.learning_view)
        assert len(a.result()) == 2 and b.result() == original
    assert len(server.requests) == 2 and not server.raw_journal and not server.raw_sources
    # SummaryLock orders complete atomic journal/source certificates together.
    for request in server.requests:
        proofs = [operation.get('stmt', {}).get('sql', '') for operation in request['requests']]
        assert sum('casepath-journal-bytes-v1:set:' in sql for sql in proofs) == 1
        assert sum('casepath-source-bytes-v1:set:' in sql for sql in proofs) == 1
    with sqlite3.connect(server.path) as db:
        db.execute("UPDATE claim_loop_events SET created_at='unaccepted metadata change'")
    for read in (store.list_summaries, knowledge.learning_view):
        with pytest.raises(AutonomousStoreError, match='journal event identity or hash differs'):
            read()


def test_raw_payload_reads_retire_http_sockets_while_compact_proofs_keep_pool(native_proof_store):
    server, _, knowledge = native_proof_store
    original = knowledge.learning_view()
    raw = [header for payload, header in server.raw_http_policy if payload]
    compact = [header for payload, header in server.raw_http_policy if not payload]
    assert raw and all(header == 'close' for header in raw)
    assert compact and all(header != 'close' for header in compact)
    server.reset()
    assert knowledge.learning_view() == original
    assert len(server.raw_http_policy) == 1
    assert all(not payload and header != 'close' for payload, header in server.raw_http_policy)


def test_raw_source_sqlite_fallback_receives_no_http_keyword(native_proof_store):
    from contextlib import contextmanager
    server, _, _ = native_proof_store

    @contextmanager
    def connect():
        db = sqlite3.connect(server.path)
        db.row_factory = sqlite3.Row
        try:
            yield db
        finally:
            db.close()

    with connect() as db:
        digest = db.execute('SELECT sha256 FROM autonomous_source_chunks ORDER BY sha256 LIMIT 1').fetchone()[0]
    sources = HostedSources(connect)
    raw = sources.read(digest)
    assert sha256(raw).hexdigest() == digest
    sources.verify_knowledge_many([digest])
    assert sources.read(digest) == raw
