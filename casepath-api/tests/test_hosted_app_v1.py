from datetime import timedelta
import httpx
import pytest
from fastapi.testclient import TestClient

from casepath_api.hosted_app_v1 import create_hosted_app
from casepath_api.hosted_model_v1 import HostedModel
from casepath_api.autonomous_model_v1 import AutonomousModelError
from casepath_api.hosted_sql_v1 import TursoDatabase
from hosted_hrana_fixture import MockHrana
from test_autonomous_model_v1 import entry


def test_readonly_cloud_boot_health_and_intake_boundary(tmp_path):
    server = MockHrana(tmp_path / 'cloud.db')
    database = TursoDatabase('libsql://fixture.turso.io', 'fixture-token-' * 4, client_factory=server.client)
    env = {'CASEPATH_SITE_ORIGIN': 'https://casepath.example', 'CASEPATH_PROXY_TOKEN': 't'*48,
           'CASEPATH_SOURCE_COMMIT': 'a'*40, 'CASEPATH_HOSTED_WRITABLE': '0', 'CASEPATH_AUTONOMOUS_ENABLED': '0'}
    app = create_hosted_app(database=database, environment=env, runtime_directory=tmp_path / 'runtime')
    headers = {'X-CasePath-Proxy-Token': 't'*48, 'X-CasePath-Site-Origin': env['CASEPATH_SITE_ORIGIN'],
               'Origin': env['CASEPATH_SITE_ORIGIN'], 'X-CasePath-Agent-Work': '1'}
    try:
        with TestClient(app) as client:
            health = client.get('/healthz')
            assert health.status_code == 200 and health.json()['source_commit'] == 'a'*40
            prefix = '/api/claim-loops/v1/autonomous'
            assert client.get(prefix+'/claims').status_code == 403
            assert client.get(prefix+'/claims', headers=headers).json() == {'claims': []}
            assert client.get(prefix+'/status', headers=headers).json()['provider_ready'] is False
            assert client.post(prefix+'/claims', headers=headers, json={}).status_code == 503
    finally:
        server.close()


def test_model_metadata_refresh_is_free_bounded_and_never_sends_inference():
    requests, reject = [], []
    def handler(request):
        requests.append(request)
        assert request.method == 'GET' and request.url.path == '/api/v1/models'
        return httpx.Response(503) if reject else httpx.Response(200, json={'data': [entry()]})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    model = HostedModel(None, 'test/semantic', 'sk-or-fixture-only', catalogue_client=client)
    original = model.config
    assert model._refresh().config == original and len(requests) == 1
    model._model._catalogue_fetched_at -= timedelta(hours=13)
    assert model._refresh().config == original and len(requests) == 2
    model._model._catalogue_fetched_at -= timedelta(hours=13)
    reject.append(True)
    with pytest.raises(AutonomousModelError, match='No model request was sent'):
        model._refresh()
    assert len(requests) == 3 and model.config == original
    client.close()
