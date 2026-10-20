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
from casepath_api.autonomous_knowledge_v1 import AutonomousKnowledge
from casepath_api.hosted_sql_v1 import HostedStorageError
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
            knowledge = client.get(PREFIX + '/knowledge', headers=HEADERS).json()
            assert knowledge == passive.knowledge.learning_view()
            assert {key: knowledge[key] for key in ('versions', 'uses', 'quarantined')} == passive.knowledge.view()
            sql = list(statements(server.requests[baseline:]))
            assert not [command for command in sql if re.match(r'\s*(INSERT|UPDATE|DELETE|REPLACE|CREATE|ALTER|DROP)\b', command, re.I)]
            assert rows(server.path) == before
        assert rows(server.path) == before
    assert resumes == [] and provider_calls == 2 and len(controllers) == 2


def test_public_startup_verifies_knowledge_after_readonly_shutdown_before_readiness(saved_runtime, tmp_path, monkeypatch):
    server, database, store, corpus, pending, completed, original, provider_calls = saved_runtime
    controllers, warmed, summaries = [], [], []
    construct = hosted_app_v1.HostedAutonomousController
    learning_view = AutonomousKnowledge.learning_view
    read_summaries = HostedAutonomousStore._read_summaries
    def controller(*args, **kwargs):
        value = construct(*args, **kwargs)
        controllers.append(value)
        return value
    def warm(knowledge):
        value = controllers[-1]
        assert knowledge is value.knowledge
        assert value._closed and value.model is None and value.store._read_only
        before = rows(server.path)
        baseline = len(server.requests)
        result = learning_view(knowledge)
        calls = server.requests[baseline:]
        assert calls and rows(server.path) == before
        assert all(item['type'] in ('execute', 'close', 'batch')
                   for call in calls for item in call['requests'])
        assert all(re.match(r'\s*(SELECT|BEGIN|COMMIT)\b', command, re.I)
                   for command in statements(calls))
        warmed.append(result)
        return result
    def summary_read(saved_store, *, statuses=None):
        value = controllers[-1]
        assert saved_store is value.store
        assert value._closed and value.model is None and saved_store._read_only
        before = rows(server.path)
        baseline = len(server.requests)
        result = read_summaries(saved_store, statuses=statuses)
        calls = server.requests[baseline:]
        assert calls and rows(server.path) == before
        assert all(re.match(r'\s*(SELECT|BEGIN|COMMIT)\b', command, re.I)
                   for command in statements(calls))
        summaries.append(result)
        return result
    def forbidden_model(*args, **kwargs):
        pytest.fail('read-only warmup constructed a provider model')
    def forbidden_discovery(*args, **kwargs):
        pytest.fail('read-only startup entered claim discovery or execution')
    monkeypatch.setattr(hosted_app_v1, 'HostedAutonomousController', controller)
    monkeypatch.setattr(AutonomousKnowledge, 'learning_view', warm)
    monkeypatch.setattr(HostedAutonomousStore, '_read_summaries', summary_read)
    monkeypatch.setattr(hosted_model_v1, 'HostedModel', forbidden_model)
    for target, name in ((HostedAutonomousStore, 'list'),
                         (construct, 'resume'), (construct, 'wake_pending')):
        monkeypatch.setattr(target, name, forbidden_discovery)
    env = {'CASEPATH_SITE_ORIGIN': ORIGIN, 'CASEPATH_PROXY_TOKEN': TOKEN,
           'CASEPATH_SOURCE_COMMIT': 'a' * 40}
    app = hosted_app_v1.create_hosted_app(database=database, environment=env, runtime_directory=tmp_path / 'warm')
    before = rows(server.path)
    with TestClient(app) as client:
        assert len(warmed) == len(summaries) == 1
        assert {row['claim_id'] for row in summaries[0]} == {pending['claim_id'], completed['claim_id'], original['claim_id']}
        assert client.get('/healthz').status_code == 200
        assert rows(server.path) == before
    assert rows(server.path) == before


def test_public_readiness_is_closed_before_startup_and_after_failed_warmup(saved_runtime, tmp_path, monkeypatch):
    server, database, *_ = saved_runtime
    attempted, closed = [], []
    construct = hosted_app_v1.HostedAutonomousController
    def controller(*args, **kwargs):
        value = construct(*args, **kwargs)
        close = value.shutdown
        def shutdown():
            closed.append(value)
            close()
        value.shutdown = shutdown
        return value
    def failed_warm(knowledge):
        attempted.append(True)
        raise HostedStorageError('synthetic saved knowledge verification failure')
    monkeypatch.setattr(hosted_app_v1, 'HostedAutonomousController', controller)
    monkeypatch.setattr(AutonomousKnowledge, 'learning_view', failed_warm)
    env = {'CASEPATH_SITE_ORIGIN': ORIGIN, 'CASEPATH_PROXY_TOKEN': TOKEN,
           'CASEPATH_SOURCE_COMMIT': 'a' * 40}
    app = hosted_app_v1.create_hosted_app(database=database, environment=env, runtime_directory=tmp_path / 'failed-warm')
    before = len(server.requests)
    client = TestClient(app)
    try:
        assert client.get('/healthz').status_code == 503
        assert len(server.requests) == before
        with pytest.raises(HostedStorageError, match='verification failure'):
            with client:
                pytest.fail('startup exposed a partially warmed service')
        after = len(server.requests)
        assert client.get('/healthz').status_code == 503
        assert len(server.requests) == after and attempted == [True]
        assert closed and all(value._closed for value in closed)
    finally:
        client.close()


def saved_seed_environment(server, tmp_path):
    import base64
    from hashlib import sha256
    from casepath_api.hosted_read_seed_v1 import pack_seed
    with sqlite3.connect(server.path) as db:
        db.row_factory = sqlite3.Row
        journal_rows = [dict(row) for row in db.execute('SELECT * FROM claim_loop_events ORDER BY loop_id,sequence')]
        chunks = {}
        for row in db.execute('SELECT * FROM autonomous_source_chunks ORDER BY sha256,chunk_index'):
            chunks.setdefault(row['sha256'], bytearray()).extend(row['content'])
    sources = [{'sha256': digest, 'content_base64': base64.b64encode(raw).decode('ascii')}
               for digest, raw in chunks.items()]
    raw = pack_seed('a' * 40, journal_rows, sources)
    path = tmp_path / 'read-seed.json'
    path.write_bytes(raw)
    return {'CASEPATH_SITE_ORIGIN': ORIGIN, 'CASEPATH_PROXY_TOKEN': TOKEN,
            'CASEPATH_SOURCE_COMMIT': 'a' * 40, 'CASEPATH_READ_SEED_PATH': str(path),
            'CASEPATH_READ_SEED_SHA256': sha256(raw).hexdigest()}


def test_public_startup_seed_avoids_raw_reads_before_readiness_without_changing_rows(saved_runtime, tmp_path, monkeypatch):
    server, database, *_ = saved_runtime
    env = saved_seed_environment(server, tmp_path)
    before, controllers = rows(server.path), []
    construct = hosted_app_v1.HostedAutonomousController
    def controller(*args, **kwargs):
        value = construct(*args, **kwargs)
        controllers.append(value)
        return value
    monkeypatch.setattr(hosted_app_v1, 'HostedAutonomousController', controller)
    monkeypatch.setattr(HostedSources, '_fetch_many', lambda *a, **k: pytest.fail('Seed startup downloaded raw bytes'))
    app = hosted_app_v1.create_hosted_app(database=database, environment=env, runtime_directory=tmp_path / 'seeded')
    with TestClient(app) as client:
        assert controllers[-1]._closed and controllers[-1].store._read_only
        assert client.get('/healthz').status_code == 200
        baseline = len(server.requests)
        assert client.get(PREFIX + '/knowledge', headers=HEADERS).status_code == 200
        requests = server.requests[baseline:]
        assert len(requests) == 1
        assert any('casepath-journal-bytes-v1:set:' in sql for sql in statements(requests))
        assert any('casepath-source-bytes-v1:set:' in sql for sql in statements(requests))
        assert rows(server.path) == before


def test_public_startup_invalid_seed_checksum_keeps_readiness_closed(saved_runtime, tmp_path):
    from casepath_api.hosted_read_seed_v1 import SeedError
    server, database, *_ = saved_runtime
    env = saved_seed_environment(server, tmp_path)
    env['CASEPATH_READ_SEED_SHA256'] = '0' * 64
    before = rows(server.path)
    app = hosted_app_v1.create_hosted_app(database=database, environment=env, runtime_directory=tmp_path / 'bad-seed')
    client = TestClient(app)
    try:
        with pytest.raises(SeedError):
            with client:
                pytest.fail('Invalid seed reached readiness')
        assert client.get('/healthz').status_code == 503
        assert rows(server.path) == before
    finally:
        client.close()


def test_confirmed_stale_seed_uses_existing_cold_startup_for_valid_new_rows(saved_runtime, tmp_path, monkeypatch):
    server, database, fixture_store, *_ = saved_runtime
    env = saved_seed_environment(server, tmp_path)
    fixture_store.intake(packet(), 'valid-new-intake-after-seed')
    before, admitted = rows(server.path), []
    original = HostedAutonomousStore.admit_read_seed
    def admit(store, *args, **kwargs):
        result = original(store, *args, **kwargs)
        admitted.append(result)
        return result
    monkeypatch.setattr(HostedAutonomousStore, 'admit_read_seed', admit)
    app = hosted_app_v1.create_hosted_app(database=database, environment=env, runtime_directory=tmp_path / 'stale-seed')
    with TestClient(app) as client:
        assert admitted == [False]
        assert client.get('/healthz').status_code == 200
        assert rows(server.path) == before


def test_public_app_closes_only_its_owned_shared_database(saved_runtime, tmp_path, monkeypatch):
    server, injected, *_ = saved_runtime
    created, closed = [], []
    def database(url, token, *, reuse_http):
        assert reuse_http is True
        value = TursoDatabase(url, token, reuse_http=True, client_factory=server.client)
        original = value.close
        def close():
            closed.append(value)
            original()
        value.close = close
        created.append(value)
        return value
    monkeypatch.setattr(hosted_app_v1, 'TursoDatabase', database)
    env = {'CASEPATH_SITE_ORIGIN': ORIGIN, 'CASEPATH_PROXY_TOKEN': TOKEN,
           'CASEPATH_SOURCE_COMMIT': 'a' * 40, 'CASEPATH_TURSO_URL': 'libsql://fixture.turso.io',
           'TURSO_AUTH_TOKEN': 'fixture-token-' * 4}
    owned = hosted_app_v1.create_hosted_app(environment=env, runtime_directory=tmp_path / 'owned')
    with TestClient(owned) as client:
        assert client.get('/healthz').status_code == 200 and closed == []
    assert closed == created and len(created) == 1
    with pytest.raises(HostedStorageError):
        created[0].connect()
    external = hosted_app_v1.create_hosted_app(database=injected, environment=env,
                                              runtime_directory=tmp_path / 'injected')
    with TestClient(external):
        pass
    with injected.connect() as db:
        assert db.execute('SELECT 1').fetchone()[0] == 1


def test_failed_warmup_closes_owned_resources_even_if_controller_cleanup_fails(saved_runtime, tmp_path, monkeypatch):
    server, *_ = saved_runtime
    databases, work_closed = [], []
    def database(url, token, *, reuse_http):
        value = TursoDatabase(url, token, reuse_http=reuse_http, client_factory=server.client)
        databases.append(value)
        return value
    construct = hosted_app_v1.HostedAutonomousController
    def controller(*args, **kwargs):
        value = construct(*args, **kwargs)
        original = value.shutdown
        calls = []
        def shutdown():
            original()
            calls.append(True)
            if len(calls) > 1:
                raise RuntimeError('synthetic controller cleanup failure')
        value.shutdown = shutdown
        return value
    close_work = hosted_app_v1.WorkStore.close
    def close(value):
        work_closed.append(value)
        close_work(value)
    def failed_warm(knowledge):
        raise HostedStorageError('original warmup validation failure')
    monkeypatch.setattr(hosted_app_v1, 'TursoDatabase', database)
    monkeypatch.setattr(hosted_app_v1, 'HostedAutonomousController', controller)
    monkeypatch.setattr(hosted_app_v1.WorkStore, 'close', close)
    monkeypatch.setattr(AutonomousKnowledge, 'learning_view', failed_warm)
    env = {'CASEPATH_SITE_ORIGIN': ORIGIN, 'CASEPATH_PROXY_TOKEN': TOKEN,
           'CASEPATH_SOURCE_COMMIT': 'a' * 40, 'CASEPATH_TURSO_URL': 'libsql://fixture.turso.io',
           'TURSO_AUTH_TOKEN': 'fixture-token-' * 4}
    app = hosted_app_v1.create_hosted_app(environment=env, runtime_directory=tmp_path / 'cleanup-failure')
    try:
        with pytest.raises(HostedStorageError, match='original warmup validation failure'):
            with TestClient(app):
                pytest.fail('failed startup became ready')
        assert len(work_closed) == 1 and databases[0]._shared_client.is_closed
    finally:
        for value in databases:
            value.close()
