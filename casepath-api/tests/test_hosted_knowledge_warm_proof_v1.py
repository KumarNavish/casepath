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

    def _statement(self, connection, statement):
        result = super()._statement(connection, statement)
        names = [column['name'] for column in result['cols']]
        if 'event_json' in names:
            self.raw_journal.append((statement, len(result['rows'])))
        if 'content' in names:
            self.raw_sources.append((statement, len(result['rows'])))
        return result

    def handle(self, request):
        response = super().handle(request)
        self.wire_bytes.append(len(response.content))
        return response

    def reset(self):
        self.requests.clear()
        self.wire_bytes.clear()
        self.raw_journal.clear()
        self.raw_sources.clear()


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


def test_warm_read_has_two_fresh_compact_proofs_without_raw_bytes_or_writes(native_proof_store, monkeypatch):
    server, store, knowledge = native_proof_store
    original = knowledge.learning_view()
    server.reset()
    monkeypatch.setattr(store, '_replay', lambda *a, **k: pytest.fail('Unchanged journal replayed'))
    assert knowledge.learning_view() == original
    assert len(server.requests) == 2
    assert not server.raw_journal and not server.raw_sources
    assert sum(server.wire_bytes) < 16 * 1024
    for request in server.requests:
        operations = request['requests']
        assert [operation['type'] for operation in operations] == ['execute'] * 4 + ['close']
        assert operations[0]['stmt']['sql'] == 'BEGIN' and operations[-2]['stmt']['sql'] == 'COMMIT'
        assert all(operation['stmt']['sql'].startswith('SELECT') for operation in operations[1:-2])
    assert server.open_streams == 0


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


def test_unknown_journal_columns_force_all_column_fallback_on_every_read(native_proof_store):
    server, _, knowledge = native_proof_store
    original = knowledge.learning_view()
    with sqlite3.connect(server.path) as db:
        db.execute("ALTER TABLE claim_loop_events ADD COLUMN unknown_authority TEXT DEFAULT 'original'")
    for value in ('original', 'changed'):
        with sqlite3.connect(server.path) as db:
            db.execute('UPDATE claim_loop_events SET unknown_authority=?', (value,))
        server.reset()
        assert knowledge.learning_view() == original
        assert server.raw_journal


@pytest.mark.parametrize('phase', ['SELECT', 'COMMIT'])
def test_unconfirmed_warm_proof_never_returns_a_cached_projection(native_proof_store, phase):
    server, _, knowledge = native_proof_store
    knowledge.learning_view()
    server.reset()
    server.fail_next('timeout', sql_prefix=phase)
    with pytest.raises(HostedStorageError, match='unconfirmed'):
        knowledge.learning_view()
