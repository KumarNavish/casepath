from fastapi import FastAPI
from fastapi.testclient import TestClient
import asyncio
from contextvars import ContextVar
import pytest

from casepath_api.autonomous_api_v1 import create_autonomous_router
from casepath_api.autonomous_controller_v1 import AutonomousController
from casepath_api.autonomous_store_v1 import AutonomousStore
from casepath_api.hosted_proxy_v1 import HostedReadTiming, SitesProxyBoundary
from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root


def test_public_method_denial_precedes_asgi_body_headers_and_route():
    async def forbidden(*args):
        pytest.fail('public command reached ASGI request body or application')
    sent = []
    async def send(message):
        sent.append(message)
    boundary = SitesProxyBoundary(forbidden, site_origin='https://casepath.example', token='t' * 48)
    asyncio.run(boundary({'type': 'http', 'method': 'POST', 'path': '/api/unknown'}, forbidden, send))
    assert sent[0]['status'] == 403


def test_authenticated_public_sites_hop_refuses_all_intake_and_preserves_originals(tmp_path):
    store = AutonomousStore(tmp_path / 'claims.sqlite3')
    service = AutonomousController(store, PublicCorpus(default_workspace_corpus_root()).static_policy())
    service.submit = lambda _: None  # Isolated transport test, no provider or background work.
    app = FastAPI()
    app.include_router(create_autonomous_router(lambda: service))
    origin, token = 'https://casepath-demo.example', 't' * 48
    app = SitesProxyBoundary(app, site_origin=origin, token=token)
    headers = {'X-CasePath-Proxy-Token': token, 'X-CasePath-Site-Origin': origin,
               'X-CasePath-Agent-Work': '1', 'Origin': origin}
    prefix = '/api/claim-loops/v1/autonomous'
    packet = {'title': 'Fictional hosted intake', 'message': 'A termination notice arrived.',
              'files': [], 'idempotency_key': 'hosted-intake-01'}
    state = store.intake(
        {k: v for k, v in packet.items() if k != 'idempotency_key'}, packet['idempotency_key'])
    with TestClient(app, base_url='https://upstream.example') as client:
        assert client.get(prefix+'/claims').status_code == 403
        for overrides in [{'X-CasePath-Proxy-Token': 'wrong'}, {'Origin': 'https://hostile.example'},
                          {'X-CasePath-Site-Origin': 'https://hostile.example'}, {'X-CasePath-Agent-Work': '0'}]:
            assert client.post(prefix+'/claims', json=packet, headers={**headers, **overrides}).status_code == 403
        response = client.post(prefix+'/claims', json=packet, headers=headers)
        assert response.status_code == 403, response.text
        assert client.get(prefix+'/claims', headers=headers).json()['claims'][0]['claim_id'] == state['claim_id']
        source = state['source_descriptors'][0]
        original = client.get(f"{prefix}/sources/{state['claim_id']}/{source['artifact_id']}", headers=headers)
        assert original.status_code == 200 and original.content == packet['message'].encode()
        assert original.headers['x-content-sha256'] == source['sha256']
    service.shutdown()


@pytest.mark.parametrize('origin,token', [('http://insecure.example','x'*40),
    ('https://user:password@example.com','x'*40), ('https://example.com/path','x'*40),
    ('https://example.com','short')])
def test_hosted_boundary_rejects_unsafe_configuration(origin, token):
    with pytest.raises(ValueError):
        SitesProxyBoundary(None, site_origin=origin, token=token)


def test_hosted_entrypoint_rejects_unsafe_boundary_before_opening_database(monkeypatch):
    from casepath_api import hosted_app_v1

    def unexpected_database(*args, **kwargs):
        pytest.fail('Unsafe boundary configuration must fail before opening the database.')

    monkeypatch.setattr(hosted_app_v1, 'TursoDatabase', unexpected_database)
    env = {'CASEPATH_SITE_ORIGIN': 'http://insecure.example',
           'CASEPATH_PROXY_TOKEN': 't' * 48, 'CASEPATH_SOURCE_COMMIT': 'a' * 40,
           'CASEPATH_TURSO_URL': 'libsql://fixture.turso.io',
           'TURSO_AUTH_TOKEN': 'fixture-token'}
    with pytest.raises(ValueError, match='fixed HTTPS Site origin and server secret'):
        hosted_app_v1.create_hosted_app(environment=env)


@pytest.mark.parametrize('method,path,timed', [
    ('GET', '/api/claim-loops/v1/autonomous/knowledge', True),
    ('GET', '/api/claim-loops/v1/autonomous/claims', True),
    ('HEAD', '/api/claim-loops/v1/autonomous/knowledge', False),
    ('POST', '/api/claim-loops/v1/autonomous/claims', False),
    ('GET', '/api/claim-loops/v1/autonomous/knowledge/', False),
    ('GET', '/api/claim-loops/v1/autonomous/claims/example', False),
    ('GET', '/healthz', False),
])
def test_hosted_read_timing_preserves_response_and_exact_get_scope(monkeypatch, method, path, timed):
    from casepath_api import hosted_proxy_v1

    ticks = iter((10.0, 10.012345))
    monkeypatch.setattr(hosted_proxy_v1, 'monotonic', lambda: next(ticks))
    headers = [(b'content-type', b'application/json'), (b'server-timing', b'existing;dur=2')]
    start = {'type': 'http.response.start', 'status': 409, 'headers': headers}
    body = {'type': 'http.response.body', 'body': b'{"detail":"unchanged saved-state refusal"}'}

    async def application(scope, receive, send):
        await send(start)
        await send(body)

    async def run():
        messages = []
        async def send(message):
            messages.append(message)
        await HostedReadTiming(application)({'type': 'http', 'method': method, 'path': path,
                                             'query_string': b'limit=2'}, None, send)
        return messages

    sent = asyncio.run(run())
    assert sent[0]['status'] == start['status'] and sent[1] == body
    assert sent[0]['headers'] == headers + ([(b'server-timing', b'casepath_api;dur=12.345')] if timed else [])
    assert start['headers'] is headers and len(headers) == 2


def test_hosted_read_timing_is_request_local_and_copies_shared_start_headers(monkeypatch):
    from casepath_api import hosted_proxy_v1

    clock = ContextVar('isolated_test_clock')
    monkeypatch.setattr(hosted_proxy_v1, 'monotonic', lambda: next(clock.get()))
    headers = [(b'server-timing', b'existing;dur=1')]
    start = {'type': 'http.response.start', 'status': 200, 'headers': headers}

    async def run():
        ready, entered = asyncio.Event(), []
        async def application(scope, receive, send):
            entered.append(True)
            if len(entered) == 2:
                ready.set()
            await ready.wait()
            await send(start)
            await send({'type': 'http.response.body', 'body': b'unchanged'})
        wrapped = HostedReadTiming(application)
        async def request(ticks):
            clock.set(iter(ticks))
            messages = []
            async def send(message):
                messages.append(message)
            await wrapped({'type': 'http', 'method': 'GET',
                           'path': '/api/claim-loops/v1/autonomous/knowledge'}, None, send)
            return messages
        return await asyncio.gather(request((1.0, 1.125)), request((100.0, 100.25)))

    first, second = asyncio.run(run())
    assert first[0]['headers'] == headers + [(b'server-timing', b'casepath_api;dur=125.000')]
    assert second[0]['headers'] == headers + [(b'server-timing', b'casepath_api;dur=250.000')]
    assert first[1] == second[1] == {'type': 'http.response.body', 'body': b'unchanged'}
    assert start == {'type': 'http.response.start', 'status': 200, 'headers': headers}
    assert headers == [(b'server-timing', b'existing;dur=1')]


@pytest.mark.parametrize('elapsed,formatted', [
    (float('nan'), '0.000'), (float('inf'), '0.000'),
    (-1.0, '0.000'), (1e20, '999999999.999'),
])
def test_hosted_read_timing_has_finite_bounded_duration(monkeypatch, elapsed, formatted):
    from casepath_api import hosted_proxy_v1

    ticks = iter((0.0, elapsed))
    monkeypatch.setattr(hosted_proxy_v1, 'monotonic', lambda: next(ticks))
    async def application(scope, receive, send):
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
    async def run():
        messages = []
        async def send(message):
            messages.append(message)
        await HostedReadTiming(application)({'type': 'http', 'method': 'GET',
                                             'path': '/api/claim-loops/v1/autonomous/claims'}, None, send)
        return messages
    sent = asyncio.run(run())
    assert sent[0]['headers'] == [(b'server-timing', ('casepath_api;dur=' + formatted).encode('ascii'))]


def test_hosted_read_timing_wraps_denial_without_opening_stores():
    from casepath_api.hosted_app_v1 import create_hosted_app

    app = create_hosted_app(database=object(), environment={
        'CASEPATH_SITE_ORIGIN': 'https://casepath.example', 'CASEPATH_PROXY_TOKEN': 't' * 48,
        'CASEPATH_SOURCE_COMMIT': 'a' * 40})
    client = TestClient(app)  # No lifespan: unauthenticated reads must not reach stores.
    try:
        prefix = '/api/claim-loops/v1/autonomous'
        rejected = client.get(prefix + '/knowledge')
        assert rejected.status_code == 403 and rejected.json() == {'detail': 'Authenticated Site access required.'}
        assert rejected.headers['server-timing'].startswith('casepath_api;dur=')
        assert client.get(prefix + '/knowledge/').status_code == 403
        assert 'server-timing' not in client.get(prefix + '/knowledge/').headers
        command = client.post(prefix + '/claims', content=b'unread command')
        assert command.status_code == 403 and command.headers['cache-control'] == 'no-store'
        assert 'server-timing' not in command.headers
    finally:
        client.close()
