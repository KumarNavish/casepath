from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from casepath_api.autonomous_api_v1 import create_autonomous_router
from casepath_api.autonomous_controller_v1 import AutonomousController
from casepath_api.autonomous_store_v1 import AutonomousStore
from casepath_api.hosted_proxy_v1 import SitesProxyBoundary
from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root


def test_authenticated_sites_hop_preserves_real_intake_guards_and_originals(tmp_path):
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
    with TestClient(app, base_url='https://upstream.example') as client:
        assert client.get(prefix+'/claims').status_code == 403
        for overrides in [{'X-CasePath-Proxy-Token': 'wrong'}, {'Origin': 'https://hostile.example'},
                          {'X-CasePath-Site-Origin': 'https://hostile.example'}, {'X-CasePath-Agent-Work': '0'}]:
            assert client.post(prefix+'/claims', json=packet, headers={**headers, **overrides}).status_code == 403
        response = client.post(prefix+'/claims', json=packet, headers=headers)
        assert response.status_code == 202, response.text
        state = response.json()
        assert client.post(prefix+'/claims', json=packet, headers=headers).json() == state
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


def test_hosted_entrypoint_installs_boundary_before_opening_app(monkeypatch):
    import sys
    from types import SimpleNamespace
    from casepath_api.hosted_proxy_v1 import create_app
    app = FastAPI()
    monkeypatch.setitem(sys.modules, 'casepath_api.app', SimpleNamespace(app=app))
    monkeypatch.setenv('CASEPATH_SITE_ORIGIN', 'https://casepath-demo.example')
    monkeypatch.setenv('CASEPATH_PROXY_TOKEN', 't'*48)
    boundary = create_app()
    assert isinstance(boundary, SitesProxyBoundary) and boundary.app is app
    with TestClient(boundary) as client:
        assert client.get('/api/claim-loops/v1/autonomous/claims').status_code == 403
