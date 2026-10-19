"""Read timings follow real work without changing authority or response bytes."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from casepath_api.autonomous_api_v1 import create_autonomous_router
from casepath_api.hosted_proxy_v1 import HostedReadTiming
from casepath_api.hosted_read_timing_v1 import CURRENT_READ, CURRENT_SHAPE, primary_request, primary_shape, statement_timing_fields
from test_hosted_knowledge_warm_proof_v1 import native_proof_store


def test_read_diagnostics_cross_worker_thread_and_count_real_primary_requests(native_proof_store):
    server, store, knowledge = native_proof_store
    expected = knowledge.learning_view()
    service = SimpleNamespace(store=store, knowledge=knowledge, policy={})
    app = FastAPI()
    app.include_router(create_autonomous_router(lambda: service, read_only=True))
    app.add_middleware(HostedReadTiming)
    with TestClient(app) as client:
        for path in ('knowledge', 'claims'):
            server.reset()
            response = client.get('/api/claim-loops/v1/autonomous/' + path)
            assert response.status_code == 200
            if path == 'knowledge':
                assert response.json() == expected
            header = response.headers['server-timing']
            assert f'casepath_primary_count;desc="{len(server.requests)}"' in header
            assert len(server.requests) == 1 and not server.raw_journal and not server.raw_sources
            for phase in ('primary', 'connect', 'tls', 'headers', 'body', 'lock', 'compute', 'json'):
                assert 'casepath_' + phase + ';dur=' in header
            assert 'SELECT' not in header and 'fixture' not in header and len(header) < 1024
            assert 'casepath_p1_shape;desc="1"' in header
            assert 'casepath_p1_statements;desc="6"' in header
            assert CURRENT_READ.get() is None


def test_network_trace_measures_connect_and_tls_but_retains_no_trace_info(monkeypatch):
    from casepath_api import hosted_read_timing_v1 as timing
    ticks = iter((0, 1, 2, 3, 5, 6, 7, 8, 9, 10))
    monkeypatch.setattr(timing, 'monotonic', lambda: next(ticks))
    values = {}
    token = CURRENT_READ.set(values)
    try:
        with primary_request() as arguments:
            callback = arguments['extensions']['trace']
            callback('connection.connect_tcp.started', {'host': 'private.example'})
            callback('connection.connect_tcp.complete', {'return_value': 'private socket'})
            callback('connection.start_tls.started', {'ssl_context': 'private'})
            callback('connection.start_tls.failed', {'exception': 'private'})
            callback('http11.receive_response_headers.started', {'request': 'private'})
            callback('http11.receive_response_headers.complete', {'return_value': 'private'})
            callback('http11.receive_response_body.started', {'request': 'private'})
            callback('http11.receive_response_body.complete', {'return_value': 'private'})
        assert values == {'primary_count': 1, 'primary_requests': [{'shape': 0, 'statements': []}],
                          'primary': 10, 'connect': 1, 'tls': 2, 'headers': 1, 'body': 1}
    finally:
        CURRENT_READ.reset(token)
    with primary_request() as arguments:
        assert arguments == {}


def test_overlapping_read_contexts_and_exception_cleanup():
    async def run():
        arrived = asyncio.Event()
        release = asyncio.Event()
        captures = []

        async def application(scope, receive, send):
            values = CURRENT_READ.get()
            values['primary_count'] = scope['count']
            if scope['count'] == 1:
                arrived.set()
                await release.wait()
            else:
                await arrived.wait()
                release.set()
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})

        async def call(count):
            sent = []
            async def send(message):
                sent.append(message)
            await HostedReadTiming(application)({'type': 'http', 'method': 'GET',
                'path': '/api/claim-loops/v1/autonomous/knowledge', 'count': count}, None, send)
            assert CURRENT_READ.get() is None
            captures.append((count, sent[0]['headers']))

        await asyncio.gather(call(1), call(2))
        for count, headers in captures:
            assert f'casepath_primary_count;desc="{count}"'.encode() in headers[-1][1]

        async def fails(*args):
            raise RuntimeError('fixture failure')
        with pytest.raises(RuntimeError):
            await HostedReadTiming(fails)({'type': 'http', 'method': 'GET',
                'path': '/api/claim-loops/v1/autonomous/knowledge'}, None, None)
        assert CURRENT_READ.get() is None
    asyncio.run(run())


def test_statement_metadata_is_numeric_ordered_and_does_not_change_native_payload(native_proof_store, monkeypatch):
    server, store, knowledge = native_proof_store
    expected = knowledge.learning_view()
    statement, emitted = server._statement, []

    def metadata(connection, command):
        result = statement(connection, command)
        result.update(query_duration_ms=len(emitted) + 0.125, rows_read=len(result['rows']))
        emitted.append((result, deepcopy(result)))
        return result

    monkeypatch.setattr(server, '_statement', metadata)
    app = FastAPI()
    app.include_router(create_autonomous_router(lambda: SimpleNamespace(store=store, knowledge=knowledge, policy={}), read_only=True))
    app.add_middleware(HostedReadTiming)
    server.reset()
    with TestClient(app) as client:
        response = client.get('/api/claim-loops/v1/autonomous/knowledge')
    assert response.status_code == 200 and response.json() == expected
    header = response.headers['server-timing']
    assert len(server.requests) == 1 and len(emitted) == 6
    for index, (result, original) in enumerate(emitted):
        assert result == original
        assert f'casepath_p1_s{index};dur={index + 0.125:.3f};desc="{len(result["rows"])}"' in header
    assert 'casepath_p1_shape;desc="1"' in header
    assert all(private not in header for private in ('SELECT', 'BEGIN', 'COMMIT', 'fixture', 'autonomous.', 'sha256'))


@pytest.mark.parametrize('optional', [{}, {'query_duration_ms': 'secret SQL', 'rows_read': {'token': 'private'}},
    {'query_duration_ms': -1, 'rows_read': -1}, {'query_duration_ms': True, 'rows_read': False},
    {'query_duration_ms': 10**100, 'rows_read': 2**63}])
def test_absent_or_malformed_optional_metadata_does_not_change_result_or_escape(tmp_path, monkeypatch, optional):
    from hosted_hrana_fixture import MockHrana
    server = MockHrana(tmp_path / 'isolated.sqlite3')
    original_statement = server._statement

    def metadata(connection, command):
        return {**original_statement(connection, command), **optional}

    monkeypatch.setattr(server, '_statement', metadata)
    token = CURRENT_READ.set({})
    values = CURRENT_READ.get()
    try:
        with server.connection() as db:
            assert db.execute_read_once('SELECT 7 AS value').fetchone()['value'] == 7
        fields = ', '.join(statement_timing_fields(values))
        assert fields == 'casepath_p1_shape;desc="0", casepath_p1_statements;desc="1"'
        assert len(server.requests) == 1 and server.open_streams == 0
    finally:
        CURRENT_READ.reset(token)
        server.close()


def test_statement_diagnostics_are_bounded_and_shape_context_resets(tmp_path, monkeypatch):
    from hosted_hrana_fixture import MockHrana
    server = MockHrana(tmp_path / 'isolated.sqlite3')
    original_statement = server._statement
    monkeypatch.setattr(server, '_statement', lambda *args: {
        **original_statement(*args), 'query_duration_ms': 999999999.999, 'rows_read': 2**63 - 1})
    token = CURRENT_READ.set({})
    try:
        with primary_shape(3), server.connection() as db:
            cursors = db.read_snapshot([('SELECT 7', ())] * 128)
        assert len(cursors) == 128 and all(cursor.fetchone()[0] == 7 for cursor in cursors)
        assert CURRENT_SHAPE.get() == 0
        values = CURRENT_READ.get()
        fields = statement_timing_fields(values)
        assert 'casepath_p1_shape;desc="3"' in fields
        assert 'casepath_p1_statements;desc="130"' in fields
        assert 'casepath_statements_omitted;desc="66"' in fields
        assert sum(field.startswith('casepath_p1_s') and ';dur=' in field for field in fields) == 64
        assert len(', '.join(fields)) < 6144
        for _ in range(9):
            with server.connection() as db:
                assert db.execute_read_once('SELECT 8').fetchone()[0] == 8
        assert values['primary_count'] == 10 and len(values['primary_requests']) == 8
        assert CURRENT_READ.get() is values
    finally:
        CURRENT_READ.reset(token)
        server.close()
    assert CURRENT_READ.get() is None and CURRENT_SHAPE.get() == 0


def test_optional_metadata_never_admits_a_malformed_core_result(tmp_path, monkeypatch):
    from hosted_hrana_fixture import MockHrana
    from casepath_api.hosted_sql_v1 import HostedStorageError
    server = MockHrana(tmp_path / 'isolated.sqlite3')
    statement = server._statement

    def malformed(connection, command):
        result = statement(connection, command)
        result.update(query_duration_ms=1.25, rows_read=1,
                      rows=[[{'type': 'unknown', 'value': 'private fixture'}]])
        return result

    monkeypatch.setattr(server, '_statement', malformed)
    token = CURRENT_READ.set({})
    db = server.connection()
    try:
        with pytest.raises(HostedStorageError):
            db.execute_read_once('SELECT 7')
        sent = len(server.requests)
        with pytest.raises(HostedStorageError):
            db.execute('SELECT 8')
        assert len(server.requests) == sent == 1
        assert 'private fixture' not in ', '.join(statement_timing_fields(CURRENT_READ.get()))
    finally:
        db.close()
        CURRENT_READ.reset(token)
        server.close()
