"""Public access has no work authority; isolated SQLite/MockHrana only."""
from pathlib import Path
import re
import sqlite3

from fastapi.testclient import TestClient
import pytest

from casepath_api import hosted_app_v1, hosted_lease_v1, hosted_model_v1
from casepath_api.agent_work.store import WorkStore
from casepath_api.autonomous_corpus_v1 import CanonicalCorpus
from casepath_api.autonomous_store_v1 import AutonomousStoreError
from casepath_api.hosted_sql_v1 import TursoDatabase
from casepath_api.hosted_storage_v1 import HostedAutonomousStore, HostedJournal, HostedSources
from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root
from hosted_hrana_fixture import MockHrana
from test_autonomous_controller_v1 import SemanticFixture, packet
from test_hosted_pending_recovery_v1 import ManualClock


PREFIX = '/api/claim-loops/v1/autonomous'
ORIGIN, TOKEN = 'https://casepath.example', 't' * 48
HEADERS = {'X-CasePath-Proxy-Token': TOKEN, 'X-CasePath-Site-Origin': ORIGIN,
           'Origin': ORIGIN, 'X-CasePath-Agent-Work': '1',
           'X-CasePath-User-Id': 'owner', 'X-CasePath-User-Email': 'owner@example.test'}


def rows(path):
    with sqlite3.connect(f'file:{Path(path)}?mode=ro', uri=True) as db:
        tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {name: db.execute(f'SELECT * FROM "{name}" ORDER BY rowid').fetchall() for name in tables}


def statements(value):
    if isinstance(value, dict):
        if 'sql' in value:
            yield value['sql']
        for nested in value.values():
            yield from statements(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from statements(nested)


@pytest.fixture
def saved_runtime(tmp_path):
    server = MockHrana(tmp_path / 'public-saved.db')
    lease = hosted_lease_v1.HostedWorkflowLease(server.connection)
    lease.initialize()
    journal = HostedJournal(tmp_path / 'seed-journal', lease.connect)
    store = HostedAutonomousStore(journal.path, journal=journal, source_store=HostedSources(lease.connect))
    public_corpus = PublicCorpus(default_workspace_corpus_root())
    corpus, policy = CanonicalCorpus(public_corpus), public_corpus.static_policy()
    model = SemanticFixture()
    seed = hosted_lease_v1.HostedAutonomousController(store, policy, model, lease=lease)
    seed._learn = lambda *args: None  # Accepted outcome awaiting publication at restart.
    pending = store.intake(packet(), 'public-pending-fixture')
    completed = seed.run(store.intake(packet(), 'public-completed-fixture')['claim_id'])
    assert pending['status'] == 'received' and completed['outcome'] and not completed['knowledge_published']
    original_id = corpus.ids[0]
    original = store.admit_original(original_id, corpus.packet(original_id), expected_revision=0,
                                    expected_state_sha256=corpus.preview_state(original_id)['state_sha256'],
                                    idempotency_key='public-original-pending-fixture')['state']
    work = WorkStore(tmp_path / 'seed-work', connection_factory=lease.connect)
    work.close()
    seed.shutdown()
    database = TursoDatabase('libsql://fixture.turso.io', 'fixture-token-' * 4, client_factory=server.client)
    try:
        yield server, database, store, corpus, pending, completed, original, len(model.calls)
    finally:
        server.close()


@pytest.mark.parametrize('flags', [('0', '0'), ('1', '1')])
def test_public_restarts_reads_commands_and_callback_races_preserve_all_saved_rows(saved_runtime, tmp_path, monkeypatch, flags):
    server, database, store, corpus, pending, completed, original, provider_calls = saved_runtime
    clock, controllers, resumes = ManualClock(), [], []
    monkeypatch.setattr(hosted_lease_v1, 'Timer', clock.timer)
    monkeypatch.setattr(hosted_lease_v1, 'monotonic', lambda: clock.now)
    construct = hosted_app_v1.HostedAutonomousController
    def controller(*args, **kwargs):
        value = construct(*args, **kwargs)
        controllers.append(value)
        return value
    def forbidden_model(*args, **kwargs):
        pytest.fail('public startup constructed provider model/catalogue transport')
    def forbidden_resume(*args, **kwargs):
        resumes.append(True)
        pytest.fail('public startup resumed pending or unpublished work')
    monkeypatch.setattr(hosted_app_v1, 'HostedAutonomousController', controller)
    monkeypatch.setattr(hosted_model_v1, 'HostedModel', forbidden_model)
    monkeypatch.setattr(hosted_app_v1, 'HostedModel', forbidden_model, raising=False)
    monkeypatch.setattr(construct, 'resume', forbidden_resume)
    env = {'CASEPATH_SITE_ORIGIN': ORIGIN, 'CASEPATH_PROXY_TOKEN': TOKEN, 'CASEPATH_SOURCE_COMMIT': 'a' * 40,
           'CASEPATH_HOSTED_WRITABLE': flags[0], 'CASEPATH_AUTONOMOUS_ENABLED': flags[1]}
    before = rows(server.path)
    paths = [PREFIX + '/claims', *[PREFIX + '/claims/' + pending['claim_id'] + '/' + action for action in
             ('start', 'sources', 'pause', 'resume', 'reconcile-saved-results')],
             '/api/claim-loops/v1/claims/example/commands', '/api/agent-work/v1/start',
             '/api/demo/reset', '/api/unknown/', '/api/', '/deployment-health', '/healthz', '/readyz', '/unknown']
    for restart in range(2):
        app = hosted_app_v1.create_hosted_app(database=database, environment=env,
                                             runtime_directory=tmp_path / f'public-{restart}')
        with TestClient(app) as client:
            passive = controllers[-1]
            assert passive._closed and passive.model is None and passive.store._read_only
            assert passive._jobs == passive._waiting == {} and passive._recovery_timer is None
            assert rows(server.path) == before
            baseline = len(server.requests)
            for method in ('POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'TRACE', 'CONNECT'):
                for path in paths:
                    response = client.request(method, path, headers=HEADERS, content=b'not even valid JSON')
                    assert response.status_code == 403, (method, path, response.text)
                    assert response.headers['cache-control'] == 'no-store'
            assert len(server.requests) == baseline, 'rejected commands reached durable service'
            # A callback racing shutdown and any accidental internal wake are inert.
            timer = clock.timer(5, lambda: passive._recover_pending(timer))
            passive._recovery_timer = timer
            timer.fire()
            passive.submit(pending['claim_id'])
            passive.wake_pending(force_discovery=True)
            with passive._lock:
                passive._arm_recovery()
            clock.advance(1000, passive)
            assert clock.pending == [] and passive._jobs == passive._waiting == {}
            assert len(server.requests) == baseline
            # Existing source publication rejects before chunks can be written.
            with pytest.raises(AutonomousStoreError, match='read-only'):
                passive.store.intake(packet(), 'public-internal-intake')
            assert len(server.requests) == baseline
            health = client.get('/healthz').json()
            assert health['writable'] is False and health['read_only'] is True
            assert client.get(PREFIX + '/status').status_code == 403
            status = client.get(PREFIX + '/status', headers=HEADERS).json()
            assert status['read_only'] is True and status['writable'] is False and status['provider_ready'] is False
            assert status['capabilities'] == ['saved_claims.read', 'original_sources.read', 'original_sources.preview',
                                               'claim_history.replay', 'knowledge.inspect']
            collection = client.get(PREFIX + '/claims', headers=HEADERS).json()
            assert collection['total'] == 152  # 150 originals plus two native fixtures.
            assert len([row for row in collection['claims'] if row['origin'] == 'canonical_original']) == 150
            assert client.head('/healthz', headers=HEADERS).status_code in (200, 405)
            for saved in (pending, completed, original):
                cid = saved['claim_id']
                for suffix in ('', '/snapshot', '/events', '/replay?through_seq=' + str(saved['revision'])):
                    result = client.get(PREFIX + '/claims/' + cid + suffix, headers=HEADERS)
                    assert result.status_code == 200, result.text
                assert client.get(PREFIX + '/claims/' + cid, headers=HEADERS).json()['state'] == saved
                for descriptor in saved['source_descriptors']:
                    path = PREFIX + '/sources/' + cid + '/' + descriptor['artifact_id']
                    raw = client.get(path, headers=HEADERS)
                    assert raw.status_code == 200 and raw.content == store.artifact(cid, descriptor['artifact_id'])[0]
                    assert raw.headers['x-content-sha256'] == descriptor['sha256']
                    assert client.get(path + '/preview', headers=HEADERS).status_code == 200
                    if any(source['artifact_id'] == descriptor['artifact_id'] for source in saved['acquired_sources']):
                        assert client.get(path + '/text', headers=HEADERS).status_code == 200
            assert client.get(PREFIX + '/knowledge', headers=HEADERS).json() == passive.knowledge.view()
            sql = list(statements(server.requests[baseline:]))
            assert not [command for command in sql if re.match(r'\s*(INSERT|UPDATE|DELETE|REPLACE|CREATE|ALTER|DROP)\b', command, re.I)]
            assert rows(server.path) == before
        assert rows(server.path) == before
    assert resumes == [] and provider_calls == 2 and len(controllers) == 2
