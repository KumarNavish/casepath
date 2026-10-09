"""Hrana HTTP backed by isolated SQLite files and mocked provider HTTP."""
from hashlib import sha256

import httpx
import pytest

from hosted_hrana_fixture import MockHrana

from casepath_api.agent_work.contracts import digest
from casepath_api.agent_work.store import WorkStore, ReconciliationRequired
from casepath_api.autonomous_model_v1 import AutonomousModelV1
from casepath_api.hosted_storage_v1 import (
    HostedAutonomousStore as AutonomousStore, HostedJournal, HostedSources, HostedStorageError, LibsqlConnection, TursoDatabase,
)
from test_autonomous_model_v1 import POLICY, SCHEMA, IDENTITY, entry, worker, response


SERVERS = {}

@pytest.fixture(autouse=True)
def close_mock_streams():
    yield
    for server in SERVERS.values():
        server.close()
    SERVERS.clear()


def connection_factory(path):
    if path not in SERVERS:
        SERVERS[path] = MockHrana(path)
    return SERVERS[path].connection


def autonomous(path):
    connect = connection_factory(path)
    journal = HostedJournal(path.parent / 'unused-local-journal', connect)
    return AutonomousStore(journal.path, journal=journal, source_store=HostedSources(connect))


def test_original_bytes_and_exact_event_hash_survive_new_store(tmp_path):
    path = tmp_path / 'remote-surrogate.db'
    store = autonomous(path)
    packet = {'title': 'Fictional source packet', 'message': 'Exact original. Réception.', 'files': []}
    first = store.intake(packet, 'durable-intake-01')
    del store
    reopened = autonomous(path)
    assert reopened.get(first['claim_id']) == first
    assert reopened.intake(packet, 'durable-intake-01') == first
    raw, descriptor = reopened.artifact(first['claim_id'], first['source_descriptors'][0]['artifact_id'])
    assert raw == packet['message'].encode() and sha256(raw).hexdigest() == descriptor['sha256']
    assert not reopened.path.exists()  # The placeholder path is never a database.


def test_chunked_sources_commit_once_and_reject_tampering(tmp_path):
    connect = connection_factory(tmp_path / 'sources.db')
    HostedJournal(tmp_path / 'unused', connect)
    sources = HostedSources(connect)
    raw = bytes(range(256)) * 2500
    identity = sources.publish(raw)
    assert sources.publish(raw) == identity
    assert HostedSources(connect).read(identity) == raw
    with connect() as db:
        assert db.execute('SELECT COUNT(*) FROM autonomous_source_chunks').fetchone()[0] == 3
        with pytest.raises(HostedStorageError):
            db.execute('UPDATE autonomous_source_chunks SET content=?', (b'changed',))


def test_schema_failure_rolls_back_instead_of_silently_succeeding(tmp_path):
    connect = connection_factory(tmp_path / 'schema.db')
    with connect() as db:
        with pytest.raises(HostedStorageError):
            db.executescript('CREATE TABLE must_not_survive(x); INVALID SQL;')
        assert db.execute("SELECT name FROM sqlite_master WHERE name='must_not_survive'").fetchone() is None
        with pytest.raises(HostedStorageError):
            db.execute('SELECT ?', (2**63,))


def model_fixture(tmp_path):
    path = tmp_path / 'ledger.db'
    connect = connection_factory(path)
    store = WorkStore(tmp_path / 'unused-local-ledger', connection_factory=connect)
    store.configure_external_budget(POLICY)
    store.activate_autonomous_policy(digest(store.external_budget()), 'Fixture', 'Isolated mocked calls', 'hosted-test-policy')
    observed = []
    def transport(request):
        # An independent connection sees the committed intent before HTTP.
        peer = WorkStore(tmp_path / 'unused-peer', connection_factory=connection_factory(path))
        budget = peer.external_budget()
        assert budget['provider_calls_used'] == len(observed) + 1
        assert budget['in_flight'] is True
        peer.close()
        observed.append(request)
        return response()
    model = AutonomousModelV1(store, worker=worker(entry()), catalogue_entry=entry(),
        schemas={'interpret': SCHEMA, 'verify': SCHEMA},
        client=httpx.Client(transport=httpx.MockTransport(transport)))
    return store, model, observed, connect


def test_remote_style_budget_commit_and_restart_never_resend(tmp_path):
    store, model, observed, connect = model_fixture(tmp_path)
    result = model.interpret({}, IDENTITY)
    verified = model.verify({}, result['result'], IDENTITY)
    budget = store.external_budget()
    store.close()
    model.store = WorkStore(tmp_path / 'unused-restarted', connection_factory=connect)
    assert model.store.external_budget() == budget
    assert model.interpret({}, IDENTITY) == result
    assert model.verify({}, result['result'], IDENTITY) == verified
    assert len(observed) == 2
    model.store.close()


def test_unconfirmed_reservation_commit_never_dispatches_or_retries(tmp_path):
    store, model, observed, _ = model_fixture(tmp_path)
    SERVERS[tmp_path / 'ledger.db'].fail_next('timeout', sql_prefix='COMMIT')
    with pytest.raises(HostedStorageError):
        model.interpret({}, IDENTITY)
    with pytest.raises(ReconciliationRequired):
        model.interpret({}, IDENTITY)
    assert observed == []
    assert store.external_budget()['provider_calls_used'] == 1
    assert store.external_budget()['in_flight'] is True
    store.close()


@pytest.mark.parametrize('url', ['file:/tmp/local.db', 'https://db.turso.io', 'libsql://user:secret@db.turso.io',
                                 'libsql://db.turso.io/path', 'libsql://db.turso.io?auth=secret'])
def test_database_configuration_never_falls_back_to_local_file(url):
    with pytest.raises(ValueError):
        TursoDatabase(url, 'fixture-secret-' * 4)


def test_fenced_hosted_controller_completes_graph_checklist_and_knowledge(tmp_path):
    from casepath_api.hosted_lease_v1 import HostedAutonomousController, HostedWorkflowLease
    from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root
    from test_autonomous_controller_v1 import SemanticFixture, packet

    connect = connection_factory(tmp_path / 'hosted-workflow.db')
    lease = HostedWorkflowLease(connect)
    lease.initialize()
    journal = HostedJournal(tmp_path / 'unused-hosted-journal', lease.connect)
    store = AutonomousStore(journal.path, journal=journal, source_store=HostedSources(lease.connect))
    model = SemanticFixture()
    policy = PublicCorpus(default_workspace_corpus_root()).static_policy()
    controller = HostedAutonomousController(store, policy, model, lease=lease)
    try:
        state = store.intake(packet(), 'hosted-complete-workflow')
        controller.run(state['claim_id'])
        saved = store.get(state['claim_id'])
        assert saved['outcome'] and saved['graph']['family'] == 'lease_termination_dispute'
        assert saved['evaluation']['documents']
        assert saved['knowledge_published'][0]['qualification']['regression_cases'] == 243
        assert len(model.calls) == 2
        with connect() as db:
            assert db.execute('SELECT owner FROM hosted_workflow_lease').fetchone()[0] is None
        controller.run(state['claim_id'])
        assert store.get(state['claim_id'])['state_sha256'] == saved['state_sha256']
        assert len(model.calls) == 2
    finally:
        controller.shutdown()
