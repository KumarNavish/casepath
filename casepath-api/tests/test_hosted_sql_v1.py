"""Durable HTTP/source acceptance with isolated SQLite and MockTransport."""
from base64 import b64encode
from hashlib import sha256
import json
from types import SimpleNamespace

import httpx
import pytest

from hosted_hrana_fixture import MockHrana
from casepath_api import hosted_sql_v1 as sql
from casepath_api.autonomous_store_v1 import AutonomousStore, AutonomousStoreError, MAX_FILE_BYTES
from casepath_api.hosted_storage_v1 import HostedJournal, HostedSources


@pytest.fixture
def server(tmp_path):
    value = MockHrana(tmp_path / 'isolated-hrana.sqlite')
    try:
        yield value
    finally:
        value.close()


def mock_connection(handler):
    return sql.LibsqlConnection('https://fixture.turso.io', 'fictional-test-token-' * 3,
        client=httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False, trust_env=False))


def test_exact_int64_unicode_blob_and_cursor_rows(server):
    values = (-(2**63), 2**63-1, 2**53+1, b'\x00\xff', 'Réception', 1.25, None)
    with server.connection() as db:
        cursor = db.execute('SELECT ? AS low, ? AS high, ? AS exact, ? AS raw, '
                            '? AS text, ? AS real, ? AS absent', values)
        row = cursor.fetchone()
        assert tuple(row) == values
        assert row[2] == row['exact'] == 2**53+1
        assert dict(row)['raw'] == b'\x00\xff'
        assert cursor.fetchone() is None
        assert cursor.fetchall() == []
        assert cursor.description[2] == ('exact', None, None, None, None, None, None)


@pytest.mark.parametrize('value', [2**63, -(2**63)-1, float('inf'), float('nan'), object()])
def test_invalid_parameters_are_rejected_before_transport(server, value):
    with server.connection() as db:
        sent = len(server.requests)
        with pytest.raises(sql.HostedStorageError):
            db.execute('SELECT ?', (value,))
        assert len(server.requests) == sent
        assert db.execute('SELECT 1').fetchone()[0] == 1


def test_received_sql_failure_keeps_latest_baton_for_rollback(server):
    with server.connection() as db:
        db.executescript('CREATE TABLE proof(value TEXT UNIQUE);')
        db.execute('BEGIN IMMEDIATE')
        db.execute("INSERT INTO proof VALUES ('must roll back')")
        with pytest.raises(sql.HostedSQLFailure):
            db.execute("INSERT INTO absent_table VALUES ('private fixture detail')")
        db.rollback()
        assert db.execute('SELECT COUNT(*) FROM proof').fetchone()[0] == 0
    assert server.open_streams == 0


def test_failed_sequence_rolls_back_schema_and_successful_context_commits(server):
    with server.connection() as db:
        with pytest.raises(sql.HostedSQLFailure):
            db.executescript('CREATE TABLE failed_schema(value TEXT); INVALID SQL;')
        assert db.execute("SELECT name FROM sqlite_master WHERE name='failed_schema'").fetchone() is None
        db.executescript("CREATE TABLE proof(value TEXT); CREATE TRIGGER immutable BEFORE DELETE ON proof "
                         "BEGIN SELECT RAISE(ABORT,'immutable source'); END;")
        db.execute('BEGIN IMMEDIATE')
        db.execute("INSERT INTO proof VALUES ('committed')")
    with server.connection() as peer:
        assert peer.execute('SELECT value FROM proof').fetchone()[0] == 'committed'
        with pytest.raises(sql.HostedSQLFailure):
            peer.execute('DELETE FROM proof')
    with pytest.raises(RuntimeError, match='caller failure'):
        with server.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("INSERT INTO proof VALUES ('rolled back')")
            raise RuntimeError('caller failure')
    with server.connection() as peer:
        assert peer.execute('SELECT COUNT(*) FROM proof').fetchone()[0] == 1


def test_trimmed_batches_cache_only_inside_current_unmodified_transaction(server):
    query = 'SELECT value FROM proof ORDER BY value'
    count = 'SELECT COUNT(*) AS n FROM proof'
    with server.connection() as db:
        db.executescript('CREATE TABLE proof(value TEXT);')
        db.execute('BEGIN IMMEDIATE')
        db.execute("INSERT INTO proof VALUES ('one')")
        db.prefetch([(query, ()), (count, ())])
        sent = len(server.requests)
        assert [row[0] for row in db.execute(query)] == ['one']
        assert db.execute(count).fetchone()['n'] == 1
        assert [row[0] for row in db.execute(query)] == ['one']
        assert len(server.requests) == sent
        db.execute("INSERT INTO proof VALUES ('two')")
        assert db.execute(count).fetchone()[0] == 2
        db.prefetch([(query, ())])
        db.commit()
        sent = len(server.requests)
        assert [row[0] for row in db.execute(query)] == ['one', 'two']
        assert len(server.requests) == sent + 1
        db.execute('BEGIN')
        with pytest.raises(sql.HostedSQLFailure):
            db.prefetch([('SELECT * FROM absent', ()), ('SELECT 1', ())])
        db.rollback()
        assert db.execute('SELECT 1').fetchone()[0] == 1


@pytest.mark.parametrize('fault', ['timeout', 'http_error', 'origin', 'missing_result'])
def test_lost_commit_acknowledgement_poisons_without_retry_or_hidden_rollback(server, fault):
    with server.connection() as setup:
        setup.executescript('CREATE TABLE proof(value TEXT);')
    db = server.connection()
    db.execute('BEGIN IMMEDIATE')
    db.execute("INSERT INTO proof VALUES ('committed before response loss')")
    server.fail_next(fault, sql_prefix='COMMIT')
    with pytest.raises(sql.HostedStorageError):
        db.commit()
    sent = len(server.requests)
    for action in (lambda: db.execute('SELECT 1'), db.commit, db.rollback):
        with pytest.raises(sql.HostedStorageError):
            action()
    db.close()
    assert len(server.requests) == sent
    with server.connection() as peer:
        assert peer.execute('SELECT value FROM proof').fetchone()[0] == 'committed before response loss'


def test_disappearing_transaction_baton_does_not_open_fresh_transaction(server):
    db = server.connection()
    db.execute('BEGIN')
    server.fail_next('closed_baton', sql_prefix='SELECT')
    with pytest.raises(sql.HostedStorageError):
        db.execute('SELECT 1')
    sent = len(server.requests)
    with pytest.raises(sql.HostedStorageError):
        db.execute('SELECT 2')
    db.close()
    assert len(server.requests) == sent


@pytest.mark.parametrize('fault', ['non_json', 'missing_statement_result', 'invalid_cell', 'redirect'])
def test_malformed_http_responses_are_sanitized_and_never_followed(fault, caplog):
    seen = []
    private = 'PRIVATE_FIXTURE_SQL_AND_TOKEN'
    def handler(request):
        seen.append(request)
        if fault == 'non_json':
            return httpx.Response(200, content=private.encode())
        if fault == 'redirect':
            return httpx.Response(307, headers={'Location': 'https://unexpected.example/'}, content=private.encode())
        response = {'type': 'execute'}
        if fault == 'invalid_cell':
            response['result'] = {'cols': [{'name': 'value'}],
                'rows': [[{'type': 'unexpected', 'value': private}]], 'affected_row_count': 0,
                'last_insert_rowid': None}
        return httpx.Response(200, json={'baton': 'baton', 'base_url': None,
                                       'results': [{'type': 'ok', 'response': response}]})
    db = mock_connection(handler)
    with pytest.raises(sql.HostedStorageError) as error:
        db.execute('SELECT 1')
    assert private not in str(error.value)
    with pytest.raises(sql.HostedStorageError):
        db.execute('SELECT 2')
    db.close()
    assert len(seen) == 1
    assert str(seen[0].url) == 'https://fixture.turso.io/v2/pipeline'
    assert 'fictional-test-token' not in repr(db)
    assert private not in caplog.text
    assert 'fictional-test-token' not in caplog.text
    assert 'https://' not in caplog.text


def test_response_byte_limit_closes_stream_and_poisons_connection(monkeypatch):
    assert sql.MAX_BYTES == 32 * 1024 * 1024
    monkeypatch.setattr(sql, 'MAX_BYTES', 256)
    class Oversized(httpx.SyncByteStream):
        closed = False
        def __iter__(self):
            yield b'x' * 257
        def close(self):
            self.closed = True
    stream, seen = Oversized(), []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, stream=stream)
    db = mock_connection(handler)
    with pytest.raises(sql.HostedStorageError):
        db.execute('SELECT 1')
    with pytest.raises(sql.HostedStorageError):
        db.execute('SELECT 2')
    db.close()
    assert stream.closed and len(seen) == 1


def test_slow_drip_cannot_hide_total_response_deadline(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(sql, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    class SlowDrip(httpx.SyncByteStream):
        closed = False
        def __iter__(self):
            for chunk in (b'{', b'"'):
                clock[0] += sql.REQUEST_SECONDS / 2 + 1
                yield chunk
        def close(self):
            self.closed = True
    stream, seen = SlowDrip(), []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, stream=stream)
    db = mock_connection(handler)
    with pytest.raises(sql.HostedStorageError):
        db.execute('SELECT 1')
    db.close()
    assert stream.closed and len(seen) == 1
    assert clock[0] > sql.REQUEST_SECONDS


def test_interrupted_source_upload_admits_no_event_and_exact_retry_recovers(server, tmp_path):
    raw = bytes(range(256)) * 3500  # Four chunks; interrupt after chunk index 1 commits.
    identity = sha256(raw).hexdigest()
    interrupted = []
    def handler(request):
        response = server.handle(request)
        data = json.loads(request.content)
        for operation in data['requests']:
            statement = operation.get('stmt', {})
            args = statement.get('args', [])
            if (not interrupted and statement.get('sql', '').startswith('INSERT INTO autonomous_source_chunks')
                    and sql._decode(args[0]) == identity and sql._decode(args[1]) == 1):
                interrupted.append(True)
                raise httpx.ReadTimeout('Synthetic lost chunk acknowledgement', request=request)
        return response
    connect = lambda: mock_connection(handler)
    journal = HostedJournal(tmp_path / 'unused-local-journal', connect)
    store = AutonomousStore(journal.path, journal=journal, source_store=HostedSources(connect))
    packet = {'title': 'Fictional interrupted upload', 'message': 'Preserve exact supplied originals.',
              'files': [{'file_name': 'fixture.bin', 'media_type': 'application/octet-stream',
                         'content_base64': b64encode(raw).decode('ascii')}]}
    with pytest.raises(sql.HostedStorageError):
        store.intake(packet, 'hosted-upload-recovery-01')
    assert interrupted == [True]
    with server.connection() as db:
        assert db.execute('SELECT COUNT(*) FROM claim_loop_events').fetchone()[0] == 0
        assert [row[0] for row in db.execute('SELECT chunk_index FROM autonomous_source_chunks '
                                            'WHERE sha256=? ORDER BY chunk_index', (identity,))] == [0, 1]
    with pytest.raises(AutonomousStoreError):
        HostedSources(server.connection).read(identity)
    recovered_journal = HostedJournal(tmp_path / 'unused-reopened-journal', server.connection)
    recovered = AutonomousStore(recovered_journal.path, journal=recovered_journal,
                                source_store=HostedSources(server.connection))
    state = recovered.intake(packet, 'hosted-upload-recovery-01')
    assert recovered.intake(packet, 'hosted-upload-recovery-01') == state
    descriptor = next(item for item in state['source_descriptors'] if item['sha256'] == identity)
    saved, actual_descriptor = recovered.artifact(state['claim_id'], descriptor['artifact_id'])
    assert saved == raw and actual_descriptor == descriptor
    with server.connection() as db:
        assert db.execute('SELECT COUNT(*) FROM claim_loop_events').fetchone()[0] == 1
        assert db.execute('SELECT COUNT(*) FROM autonomous_source_chunks WHERE sha256=?', (identity,)).fetchone()[0] == 4


def test_maximum_source_survives_restart_under_small_response_bound(server, tmp_path, monkeypatch):
    # This is stricter than production's 32MiB transport bound and fails if a
    # single query attempts to return the entire 16MiB original as base64 JSON.
    monkeypatch.setattr(sql, 'MAX_BYTES', 4 * 1024 * 1024)
    assert MAX_FILE_BYTES == 16 * 1024 * 1024
    HostedJournal(tmp_path / 'unused-large-source-journal', server.connection)
    raw = bytes(range(256)) * (MAX_FILE_BYTES // 256)
    expected = sha256(raw).hexdigest()
    assert HostedSources(server.connection).publish(raw) == expected
    before = len(server.requests)
    assert HostedSources(server.connection).read(expected) == raw
    statements = [operation['stmt'] for request in server.requests[before:]
                  for operation in request['requests'] if operation['type'] == 'execute']
    source_reads = [stmt for stmt in statements if 'SELECT chunk_index,content' in stmt['sql']]
    assert len(source_reads) > 1
    with server.connection() as db:
        count, length = db.execute('SELECT COUNT(*),SUM(length(content)) FROM autonomous_source_chunks '
                                  'WHERE sha256=?', (expected,)).fetchone()
        assert count == 64 and length == MAX_FILE_BYTES
    sent = len(server.requests)
    with pytest.raises(AutonomousStoreError):
        HostedSources(server.connection).publish(raw + b'!')
    assert len(server.requests) == sent


@pytest.mark.parametrize('raw', [b'', b'x', b'xy', b'xyz', bytes(range(256))])
def test_turso_unpadded_blob_encoding_preserves_exact_bytes(raw):
    encoded = b64encode(raw).decode('ascii')
    assert sql._decode({'type': 'blob', 'base64': encoded}) == raw
    assert sql._decode({'type': 'blob', 'base64': encoded.rstrip('=')}) == raw
    with pytest.raises(ValueError):
        sql._decode({'type': 'blob', 'base64': encoded + '!'})
