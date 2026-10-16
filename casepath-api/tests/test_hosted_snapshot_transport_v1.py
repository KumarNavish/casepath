"""Snapshot and HTTP ownership invariants using only local synthetic Hrana."""
from concurrent.futures import ThreadPoolExecutor
import json
from threading import Barrier, Event, Lock, get_ident

import httpx
import pytest

from casepath_api import hosted_sql_v1 as sql
from hosted_hrana_fixture import MockHrana


@pytest.fixture
def server(tmp_path):
    value = MockHrana(tmp_path / 'snapshot.db')
    try:
        yield value
    finally:
        value.close()


def connection(handler):
    return sql.LibsqlConnection('https://fixture.turso.io', 'fixture-token-' * 4,
        client=httpx.Client(transport=httpx.MockTransport(handler), trust_env=False))


def test_snapshot_returns_all_results_from_one_closed_transaction(server):
    with server.connection() as db:
        result = db.read_snapshot([('SELECT ? AS exact, ? AS raw', (2**53 + 1, b'\x00\xff')),
                                   ('SELECT ? AS text', ('Réception 😀; -- quoted',))])
        assert isinstance(result, tuple) and len(result) == 2
        assert tuple(result[0].fetchone()) == (2**53 + 1, b'\x00\xff')
        assert result[1].fetchone()['text'] == 'Réception 😀; -- quoted'
        assert not db.in_transaction and db._baton is None and db._cache == {}
        assert server.open_streams == 0 and len(server.requests) == 1
    assert len(server.requests) == 1
    payload = server.requests[0]
    assert payload['baton'] is None
    assert [item['type'] for item in payload['requests']] == ['execute'] * 4 + ['close']
    assert [item['stmt']['sql'] for item in payload['requests'][:-1]] == [
        'BEGIN', 'SELECT ? AS exact, ? AS raw', 'SELECT ? AS text', 'COMMIT']


def test_snapshot_accepts_valid_retained_last_insert_metadata_on_readonly_results(server):
    def handler(request):
        body = server.handle(request).json()
        for entry in body['results'][:-1]:
            entry['response']['result']['last_insert_rowid'] = str(2**53 + 1)
        return httpx.Response(200, json=body)
    with connection(handler) as db:
        cursor, = db.read_snapshot([('SELECT 7 AS value', ())])
        assert cursor.fetchone()['value'] == 7 and cursor.lastrowid == 2**53 + 1
        assert not db.in_transaction and db._baton is None
    assert server.open_streams == 0 and len(server.requests) == 1


@pytest.mark.parametrize('queries', [[], [('SELECT 1', ())] * 129, [('DELETE FROM proof', ())],
    [('WITH value AS (SELECT 1) SELECT * FROM value', ())], [('SELECT 1; DELETE FROM proof', ())],
    [('SELECT 1; SELECT 2', ())], [('SELECT 1', (object(),))], [('SELECT 1',)], None,
    [('SELECT 1', 'invalid parameters')]])
def test_snapshot_rejects_invalid_or_unbounded_input_before_transport(server, queries):
    with server.connection() as db:
        with pytest.raises(sql.HostedStorageError):
            db.read_snapshot(queries)
        assert server.requests == [] and not db.in_transaction
        assert db.execute('SELECT 1').fetchone()[0] == 1


@pytest.mark.parametrize('first', ['SELECT 1', 'BEGIN', 'read_once', 'snapshot'])
def test_snapshot_requires_a_fresh_connection(server, first):
    with server.connection() as db:
        if first == 'read_once':
            db.execute_read_once('SELECT 1')
        elif first == 'snapshot':
            db.read_snapshot([('SELECT 1', ())])
        else:
            db.execute(first)
        before = len(server.requests)
        with pytest.raises(sql.HostedStorageError, match='fresh connection'):
            db.read_snapshot([('SELECT 2', ())])
        assert len(server.requests) == before


@pytest.mark.parametrize('fault', [
    'begin_error', 'select_error', 'commit_error', 'close_error', 'baton', 'count', 'entry',
    'type', 'begin_result', 'commit_result', 'close_result', 'row', 'cell', 'affected',
    'begin_rows', 'commit_rows', 'begin_affected', 'commit_affected', 'origin', 'timeout',
    'non_json', 'encoding', 'http_error'])
def test_snapshot_rejects_every_unconfirmed_result_without_partial_cursors_or_retry(server, fault):
    seen = []
    def handler(request):
        seen.append(request)
        response = server.handle(request)
        if fault == 'timeout':
            raise httpx.ReadTimeout('synthetic private detail', request=request)
        if fault == 'non_json':
            return httpx.Response(200, content=b'PRIVATE_UNTRUSTED_RESPONSE')
        if fault == 'encoding':
            return httpx.Response(200, headers={'content-encoding': 'gzip'}, content=b'')
        if fault == 'http_error':
            return httpx.Response(503)
        body = response.json()
        entries = body['results']
        if fault.endswith('_error'):
            index = {'begin_error': 0, 'select_error': 1, 'commit_error': 3, 'close_error': 4}[fault]
            entries[index] = {'type': 'error', 'error': {'message': 'PRIVATE_SQL_DETAIL'}}
        elif fault == 'baton':
            body['baton'] = 'unclosed-stream'
        elif fault == 'count':
            entries.pop()
        elif fault == 'entry':
            entries[2] = None
        elif fault == 'type':
            entries[2]['response']['type'] = 'close'
        elif fault in ('begin_result', 'commit_result'):
            del entries[0 if fault == 'begin_result' else 3]['response']['result']
        elif fault == 'close_result':
            entries[4]['response']['result'] = {}
        elif fault == 'row':
            entries[2]['response']['result']['rows'][0].append({'type': 'null'})
        elif fault == 'cell':
            entries[2]['response']['result']['rows'][0][0] = {'type': 'integer', 'value': 'NaN'}
        elif fault == 'affected':
            entries[1]['response']['result']['affected_row_count'] = 1
        elif fault.endswith('_rows'):
            entries[0 if fault == 'begin_rows' else 3]['response']['result']['rows'] = [[]]
        elif fault.endswith('_affected'):
            entries[0 if fault == 'begin_affected' else 3]['response']['result']['affected_row_count'] = 1
        elif fault == 'origin':
            body['base_url'] = 'https://different.example'
        return httpx.Response(200, json=body)
    db = connection(handler)
    with pytest.raises(sql.HostedStorageError) as error:
        db.read_snapshot([('SELECT 1', ()), ('SELECT 2', ())])
    assert 'PRIVATE' not in str(error.value) and db._poisoned and db._cache == {}
    for action in (lambda: db.read_snapshot([('SELECT 1', ())]),
                   lambda: db.execute('SELECT 1'), db.commit, db.rollback):
        with pytest.raises(sql.HostedStorageError):
            action()
    db.close()
    assert len(seen) == 1


def test_snapshot_request_size_limit_stays_local_and_preserves_connection(server, monkeypatch):
    monkeypatch.setattr(sql, 'MAX_BYTES', 512)
    with server.connection() as db:
        with pytest.raises(sql.HostedStorageError, match='size bound'):
            db.read_snapshot([('SELECT ?', ('x' * 1024,))])
        assert server.requests == [] and not db._poisoned
        assert db.execute('SELECT 1').fetchone()[0] == 1


@pytest.mark.parametrize('fault', ['bytes', 'deadline'])
def test_snapshot_response_retains_byte_and_total_deadline_guards(server, monkeypatch, fault):
    seen, clock = [], [0.0]
    monkeypatch.setattr(sql.time, 'monotonic', lambda: clock[0])
    class BoundStream(httpx.SyncByteStream):
        closed = False
        def __iter__(self):
            if fault == 'deadline':
                clock[0] = sql.REQUEST_SECONDS + 1
                yield b'{}'
            else:
                yield b'x' * (sql.MAX_BYTES + 1)
        def close(self):
            self.closed = True
    if fault == 'bytes':
        monkeypatch.setattr(sql, 'MAX_BYTES', 1024)
    stream = BoundStream()
    def handler(request):
        seen.append(request)
        return httpx.Response(200, stream=stream)
    db = connection(handler)
    with pytest.raises(sql.HostedStorageError):
        db.read_snapshot([('SELECT 1', ())])
    db.close()
    assert stream.closed and db._poisoned and len(seen) == 1


def test_reused_http_client_never_reuses_connection_transaction_baton_or_cache(server):
    clients = []
    def factory():
        client = server.client()
        clients.append(client)
        return client
    database = sql.TursoDatabase('libsql://fixture.turso.io', 'fixture-token-' * 4,
                                client_factory=factory, reuse_http=True)
    first, second = database.connect(), database.connect()
    try:
        assert first._client is second._client and len(clients) == 1
        assert first._cache is not second._cache
        first.execute('BEGIN')
        second.execute('BEGIN')
        assert first._baton != second._baton and server.open_streams == 2
        first.close()
        assert not clients[0].is_closed and server.open_streams == 1
        assert second.execute('SELECT 2').fetchone()[0] == 2
        second.close()
        with database.connect() as fresh:
            assert fresh._baton is None and not fresh.in_transaction and fresh._cache == {}
            assert fresh.read_snapshot([('SELECT 3', ())])[0].fetchone()[0] == 3
        assert not clients[0].is_closed
    finally:
        first.close()
        second.close()
        database.close()
    assert clients[0].is_closed and server.open_streams == 0
    database.close()
    with pytest.raises(sql.HostedStorageError):
        database.connect()


def test_default_injected_http_client_still_closes_unless_explicitly_borrowed(server):
    owned = server.client()
    sql.LibsqlConnection(server.origin, 'fixture-token-' * 4, client=owned).close()
    assert owned.is_closed
    borrowed = server.client()
    sql.LibsqlConnection(server.origin, 'fixture-token-' * 4, client=borrowed, close_client=False).close()
    assert not borrowed.is_closed
    borrowed.close()


def test_concurrent_shared_http_sessions_isolate_batons_caches_and_poisoned_close():
    begin_barrier, read_barrier = Barrier(2), Barrier(2)
    failed_closed, lock = Event(), Lock()
    sessions, generations, observed, failed_requests = {}, {}, [], []

    def result(value=None):
        return {'cols': [] if value is None else [{'name': 'value'}],
                'rows': [] if value is None else [[sql._encode(value)]],
                'affected_row_count': 0, 'last_insert_rowid': None}

    def handler(request):
        payload = json.loads(request.content)
        operation, = payload['requests']
        kind, incoming = operation['type'], payload['baton']
        statement = operation.get('stmt', {}).get('sql', '')
        with lock:
            if incoming is None:
                assert statement in ('BEGIN /* healthy */', 'BEGIN /* failed */')
                label = 'healthy' if 'healthy' in statement else 'failed'
                assert label not in generations
                generations[label] = 0
            else:
                label = sessions.pop(incoming)
                assert incoming.startswith(label + '-')
            generations[label] += 1
            baton = None if kind == 'close' else label + '-' + str(generations[label])
            if baton is not None:
                sessions[baton] = label
            observed.append((label, incoming, kind, statement, get_ident()))
        if statement.startswith('BEGIN'):
            # Both real worker threads must be inside the same client's handler.
            begin_barrier.wait(timeout=5)
            response = {'type': 'execute', 'result': result()}
        elif kind == 'batch':
            step, = operation['batch']['steps']
            assert sql._decode(step['stmt']['args'][0]) == label
            response = {'type': 'batch', 'result': {'step_results': [result(label)], 'step_errors': []}}
        elif statement.startswith('SELECT'):
            assert sql._decode(operation['stmt']['args'][0]) == label
            read_barrier.wait(timeout=5)
            if label == 'failed':
                failed_requests.append(True)
                raise httpx.ReadTimeout('synthetic lost session response', request=request)
            response = {'type': 'execute', 'result': result(label)}
        elif statement == 'COMMIT':
            assert label == 'healthy' and failed_closed.is_set()
            response = {'type': 'execute', 'result': result()}
        else:
            assert kind == 'close' and label == 'healthy' and failed_closed.is_set()
            response = {'type': 'close'}
        return httpx.Response(200, json={'baton': baton, 'base_url': None,
                                       'results': [{'type': 'ok', 'response': response}]})

    client = httpx.Client(transport=httpx.MockTransport(handler), trust_env=False, follow_redirects=False)
    database = sql.TursoDatabase('libsql://fixture.turso.io', 'fixture-token-' * 4,
                                client_factory=lambda: client, reuse_http=True)
    def worker(label):
        db = database.connect()
        try:
            assert db._baton is None and not db.in_transaction and db._cache == {}
            db.execute('BEGIN /* ' + label + ' */')
            db.prefetch([('SELECT ? AS value', (label,))])
            assert db.execute('SELECT ? AS value', (label,)).fetchone()[0] == label
            cache_identity = id(db._cache)
            if label == 'failed':
                with pytest.raises(sql.HostedStorageError):
                    db.execute('SELECT ? AS fresh', (label,))
                assert db._poisoned and db._cache == {}
                with pytest.raises(sql.HostedStorageError):
                    db.execute('SELECT ? AS value', (label,))
                db.close()
                assert not client.is_closed
                failed_closed.set()
            else:
                assert db.execute('SELECT ? AS fresh', (label,)).fetchone()[0] == label
                assert failed_closed.wait(timeout=5)
                assert not client.is_closed and not db._poisoned and db.in_transaction
                # Poisoning/closing the peer must not erase this transaction's cache.
                assert db.execute('SELECT ? AS value', (label,)).fetchone()[0] == label
                db.commit()
                assert not db.in_transaction
            return db, cache_identity
        finally:
            db.close()
            if label == 'failed':
                failed_closed.set()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            healthy = executor.submit(worker, 'healthy')
            failed = executor.submit(worker, 'failed')
            healthy_db, healthy_cache = healthy.result(timeout=10)
            failed_db, failed_cache = failed.result(timeout=10)
        assert healthy_db._client is failed_db._client is client
        assert healthy_cache != failed_cache and failed_requests == [True]
        assert not client.is_closed and healthy_db._closed and failed_db._closed
        assert len({item[4] for item in observed}) == 2
        assert [(item[2], item[3].split()[0] if item[3] else '') for item in observed if item[0] == 'failed'] == [
            ('execute', 'BEGIN'), ('batch', ''), ('execute', 'SELECT')]
        assert [(item[2], item[3].split()[0] if item[3] else '') for item in observed if item[0] == 'healthy'] == [
            ('execute', 'BEGIN'), ('batch', ''), ('execute', 'SELECT'), ('execute', 'COMMIT'), ('close', '')]
        assert list(sessions.values()) == ['failed']  # No retry/hidden rollback after response loss.
    finally:
        database.close()
    assert client.is_closed


def test_reused_default_http_transport_has_bounded_pool_and_original_timeouts(monkeypatch):
    constructed = []
    original = httpx.Client
    def construct(**kwargs):
        constructed.append(kwargs)
        return original(**kwargs)
    monkeypatch.setattr(sql.httpx, 'Client', construct)
    database = sql.TursoDatabase('libsql://fixture.turso.io', 'fixture-token-' * 4, reuse_http=True)
    try:
        with database.connect():
            pass
        with database.connect():
            pass
        assert len(constructed) == 1
        options = constructed[0]
        assert options['follow_redirects'] is options['trust_env'] is False
        assert options['timeout'].as_dict() == {'connect': 3, 'read': 8, 'write': 4, 'pool': 2}
        assert options['limits'].max_connections == 8
        assert options['limits'].max_keepalive_connections == 4
        assert options['limits'].keepalive_expiry == 30
        pool = options['transport']._pool
        assert pool._max_connections == 8 and pool._max_keepalive_connections == 4
        assert pool._retries == 0
        assert sql.MAX_BYTES == 32 * 1024 * 1024 and sql.REQUEST_SECONDS == 12
    finally:
        database.close()
