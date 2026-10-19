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


def test_public_hosted_intake_stays_readonly_with_legacy_writable_flag(tmp_path):
    server = MockHrana(tmp_path / 'public-boundary.db')
    database = TursoDatabase('libsql://fixture.turso.io', 'fixture-token-' * 4, client_factory=server.client)
    env = {'CASEPATH_SITE_ORIGIN': 'https://casepath.example', 'CASEPATH_PROXY_TOKEN': 't'*48,
           'CASEPATH_SOURCE_COMMIT': 'a'*40, 'CASEPATH_HOSTED_WRITABLE': '1', 'CASEPATH_AUTONOMOUS_ENABLED': '0'}
    headers = {'X-CasePath-Proxy-Token': 't'*48, 'X-CasePath-Site-Origin': env['CASEPATH_SITE_ORIGIN'],
               'Origin': env['CASEPATH_SITE_ORIGIN'], 'X-CasePath-Agent-Work': '1',
               'X-CasePath-User-Id': 'owner', 'X-CasePath-User-Email': 'owner@example.test'}
    app = create_hosted_app(database=database, environment=env, runtime_directory=tmp_path / 'runtime')
    try:
        with TestClient(app) as client:
            baseline = len(server.requests)
            result = client.post('/api/claim-loops/v1/autonomous/claims', headers=headers, json={
                'title': 'Public visitor', 'message': 'Untrusted intake', 'files': [],
                'idempotency_key': 'public-forged-work-1'})
            assert result.status_code == 403, result.text
            assert len(server.requests) == baseline
    finally:
        server.close()


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
            collection = client.get(prefix+'/claims', headers=headers).json()
            assert collection['total'] == 150 and len(collection['claims']) == 150
            assert all(row['mode'] == 'unprocessed' and row['revision'] == 0 for row in collection['claims'])
            assert client.get(prefix+'/status', headers=headers).json()['provider_ready'] is False
            assert client.post(prefix+'/claims', headers=headers, json={}).status_code == 403
    finally:
        server.close()


def test_legacy_writable_flag_never_wakes_or_starts_public_work(tmp_path, monkeypatch):
    from casepath_api.hosted_lease_v1 import HostedAutonomousController
    def forbidden(*args, **kwargs):
        raise AssertionError('GET or never-started startup dispatched work')
    monkeypatch.setattr(HostedAutonomousController, 'submit', forbidden)
    monkeypatch.setattr(HostedAutonomousController, 'wake_pending', forbidden)
    monkeypatch.setattr(HostedAutonomousController, 'resume', forbidden)
    server = MockHrana(tmp_path / 'browse.db')
    database = TursoDatabase('libsql://fixture.turso.io', 'fixture-token-' * 4, client_factory=server.client)
    env = {'CASEPATH_SITE_ORIGIN': 'https://casepath.example', 'CASEPATH_PROXY_TOKEN': 't'*48,
           'CASEPATH_SOURCE_COMMIT': 'a'*40, 'CASEPATH_HOSTED_WRITABLE': '1', 'CASEPATH_AUTONOMOUS_ENABLED': '0'}
    app = create_hosted_app(database=database, environment=env, runtime_directory=tmp_path / 'runtime')
    headers = {'X-CasePath-Proxy-Token': 't'*48, 'X-CasePath-Site-Origin': env['CASEPATH_SITE_ORIGIN'],
               'Origin': env['CASEPATH_SITE_ORIGIN']}
    try:
        with TestClient(app) as client:
            result = client.get('/api/claim-loops/v1/autonomous/claims', headers=headers)
            assert result.status_code == 200 and result.json()['total'] == 150
            cid = result.json()['claims'][0]['claim_id']
            for path in ('', '/snapshot', '/events', '/replay?through_seq=0'):
                response = client.get(f'/api/claim-loops/v1/autonomous/claims/{cid}{path}', headers=headers)
                assert response.status_code == 200, response.text
            with database.connect() as db:
                assert db.execute('SELECT COUNT(*) AS n FROM claim_loop_events').fetchone()['n'] == 0
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


def test_cloud_import_does_not_require_generated_legacy_artifacts(tmp_path):
    from pathlib import Path
    import shutil
    import subprocess
    import sys
    source = Path(__file__).resolve().parents[1] / 'casepath_api'
    shutil.copytree(source, tmp_path / 'casepath_api', ignore=shutil.ignore_patterns('corpora','__pycache__'))
    result = subprocess.run([sys.executable, '-B', '-c', 'import casepath_api.hosted_app_v1'],
                            cwd=tmp_path, env={'PYTHONDONTWRITEBYTECODE':'1'}, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / 'artifacts').exists()


@pytest.mark.parametrize('failure', [None, 'knowledge_handler', 'claims_render'])
def test_default_reads_and_serialization_finish_before_readiness_and_fail_closed(tmp_path, monkeypatch, failure):
    from functools import wraps
    from casepath_api import hosted_app_v1 as hosted
    from casepath_api.hosted_proxy_v1 import ReadTimedJSONResponse
    from casepath_api.hosted_storage_v1 import HostedStorageError

    events, controllers, work_closed, startup_done = [], [], [], []
    router_factory = hosted.create_autonomous_router
    original_render = ReadTimedJSONResponse.render
    original_controller, original_close = hosted.HostedAutonomousController, hosted.WorkStore.close

    def controller(*args, **kwargs):
        value = original_controller(*args, **kwargs)
        controllers.append(value)
        return value

    def close(work):
        work_closed.append(True)
        return original_close(work)

    def observed(endpoint, name):
        @wraps(endpoint)
        def read(**arguments):
            events.append(name + '_handler')
            if not startup_done and failure == name + '_handler':
                raise RuntimeError('Isolated startup handler failure')
            return endpoint(**arguments)
        return read

    def router(*args, **kwargs):
        value = router_factory(*args, **kwargs)
        for route in value.routes:
            name = route.path.rsplit('/', 1)[-1]
            if name in ('knowledge', 'claims') and route.methods == {'GET'}:
                route.endpoint = observed(route.endpoint, name)
        return value

    def render(response, content):
        name = 'claims' if 'claims' in content else 'knowledge'
        events.append(name + '_render')
        if not startup_done:
            with pytest.raises(HostedStorageError, match='not ready'):
                health()
        if not startup_done and failure == name + '_render':
            raise RuntimeError('Isolated startup serialization failure')
        return original_render(response, content)

    monkeypatch.setattr(hosted, 'create_autonomous_router', router)
    monkeypatch.setattr(hosted, 'HostedAutonomousController', controller)
    monkeypatch.setattr(hosted.WorkStore, 'close', close)
    monkeypatch.setattr(ReadTimedJSONResponse, 'render', render)
    server = MockHrana(tmp_path / 'startup-prime.sqlite3')
    database = TursoDatabase('libsql://fixture.turso.io', 'fixture-token-' * 4, client_factory=server.client)
    env = {'CASEPATH_SITE_ORIGIN': 'https://casepath.example', 'CASEPATH_PROXY_TOKEN': 't' * 48,
           'CASEPATH_SOURCE_COMMIT': 'a' * 40, 'CASEPATH_AUTONOMOUS_ENABLED': '0'}
    app = hosted.create_hosted_app(database=database, environment=env, runtime_directory=tmp_path / 'runtime')
    health = next(route.endpoint for route in app.routes if route.path == '/healthz')
    headers = {'X-CasePath-Proxy-Token': 't' * 48, 'X-CasePath-Site-Origin': env['CASEPATH_SITE_ORIGIN']}
    try:
        if failure:
            with pytest.raises(RuntimeError, match='Isolated startup'):
                with TestClient(app):
                    pytest.fail('Failed startup admitted readiness')
            startup_done.append(True)
            with pytest.raises(HostedStorageError, match='not ready'):
                health()
            knowledge = next(route.endpoint for route in app.routes if route.path.endswith('/knowledge'))
            with pytest.raises(HostedStorageError, match='not ready'):
                knowledge()
            assert work_closed and controllers[0]._closed is True
        else:
            with TestClient(app) as client:
                startup_done.append(True)
                assert events == ['knowledge_handler', 'knowledge_render', 'claims_handler', 'claims_render']
                assert client.get('/healthz').json()['status'] == 'ok'
                for name in ('knowledge', 'claims'):
                    before = len(server.requests)
                    response = client.get('/api/claim-loops/v1/autonomous/' + name, headers=headers)
                    assert response.status_code == 200
                    assert len(server.requests) > before  # Startup never replaces this read's primary validation.
                assert events[-4:] == ['knowledge_handler', 'knowledge_render', 'claims_handler', 'claims_render']

                # A valid new primary head after startup invalidates the warmed
                # result. Only this isolated fixture database receives writes.
                import sqlite3
                from casepath_api.autonomous_store_v1 import AutonomousStore
                native = AutonomousStore(tmp_path / 'new-primary-head.sqlite3')
                added = native.intake({'title': 'New fictional source after readiness',
                    'message': 'A distinct recorded intake added after startup.'}, 'startup.new.head')
                with sqlite3.connect(native.path) as source, sqlite3.connect(server.path) as target:
                    target.executemany('INSERT INTO claim_loop_events VALUES (?,?,?,?,?,?,?,?)',
                                       source.execute('SELECT * FROM claim_loop_events').fetchall())
                    for path in native.source_root.iterdir():
                        target.execute('INSERT INTO autonomous_source_chunks VALUES (?,?,?)',
                                       (path.name, 0, path.read_bytes()))
                changed = client.get('/api/claim-loops/v1/autonomous/knowledge', headers=headers)
                assert changed.status_code == 200
                assert changed.json()['learning_replay']['journal_heads'] == [{
                    'claim_id': added['claim_id'], 'revision': added['revision'],
                    'event_sha256': added['last_event_sha256'], 'state_sha256': added['state_sha256']}]
                claims = client.get('/api/claim-loops/v1/autonomous/claims', headers=headers).json()
                assert claims['total'] == 151
                assert next(row for row in claims['claims'] if row['claim_id'] == added['claim_id'])['revision'] == added['revision']
    finally:
        server.close()
