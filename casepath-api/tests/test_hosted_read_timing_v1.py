"""Read timings follow real work without changing authority or response bytes."""
import asyncio
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from casepath_api.autonomous_api_v1 import create_autonomous_router
from casepath_api.hosted_proxy_v1 import HostedReadTiming
from casepath_api.hosted_read_timing_v1 import CURRENT_READ, primary_request
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
            assert 'SELECT' not in header and 'fixture' not in header and len(header) < 512
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
        assert values == {'primary_count': 1, 'primary': 10, 'connect': 1, 'tls': 2, 'headers': 1, 'body': 1}
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
