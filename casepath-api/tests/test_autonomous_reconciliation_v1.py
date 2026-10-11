"""Explicit saved-result reconciliation; synthetic bytes and mocked transport only."""
from copy import deepcopy
import json

import httpx
import pytest

from casepath_api import autonomous_controller_v1 as controller_module
from casepath_api.agent_work.contracts import canonical, digest
from casepath_api.agent_work.store import WorkStore
from casepath_api.autonomous_controller_v1 import AutonomousController
from casepath_api.autonomous_model_v1 import AutonomousModelV1, SavedAutonomousResultsV1
from casepath_api.autonomous_policy_v1 import INTERPRET_SCHEMA, VERIFY_SCHEMA
from casepath_api.autonomous_store_v1 import AutonomousStore, AutonomousStoreError
from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root
from test_autonomous_controller_v1 import SemanticFixture, packet
from test_autonomous_model_v1 import POLICY, entry, response, worker
from test_autonomous_canonical_store_v1 import admit, original_packet


def ledger_bytes(work):
    with work.connect() as db:
        tables = [row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'work_%' ORDER BY name")]
        return canonical({name: [dict(row) for row in db.execute(f'SELECT * FROM {name} ORDER BY rowid')]
                          for name in tables})


@pytest.fixture
def failed_runtime(tmp_path, monkeypatch, request):
    mode = getattr(request, 'param', 'legacy')
    server = lease = None
    if mode == 'hosted':
        from hosted_hrana_fixture import MockHrana
        from casepath_api.hosted_lease_v1 import HostedWorkflowLease, HostedAutonomousController
        from casepath_api.hosted_storage_v1 import HostedAutonomousStore, HostedJournal, HostedSources
        server = MockHrana(tmp_path / 'hosted.sqlite')
        lease = HostedWorkflowLease(server.connection)
        lease.initialize()
        journal = HostedJournal(tmp_path / 'unused-claims', lease.connect)
        store = HostedAutonomousStore(journal.path, journal=journal, source_store=HostedSources(lease.connect))
        work = WorkStore(tmp_path / 'unused-work', connection_factory=lease.connect)
    else:
        store = AutonomousStore(tmp_path / 'claims.sqlite')
        work = WorkStore(tmp_path / 'work.sqlite')
    work.configure_external_budget(POLICY)
    work.activate_autonomous_policy(digest(work.external_budget()), 'Fixture operator',
                                   'Synthetic bounded workflow', 'fixture-autonomous-policy')
    calls, semantic = [], SemanticFixture()
    def transport(request):
        calls.append(request)
        body = json.loads(request.content)
        envelope = json.loads(body['messages'][1]['content'])
        if body['response_format']['json_schema']['name'] == 'casepath_interpret':
            result = semantic.interpret(envelope, {})['result']
            source = next(s for s in envelope['sources'] if s['role'] == 'supporting_document')
            result['steps'].append({'node_id': 'lt_type', 'status': 'unresolved',
                                   'summary': 'Optional type is unresolved.', 'citations': [
                                       {'artifact_id': source['artifact_id'], 'quote': 'separate termination'}]})
            if mode == 'bad_document':
                result['documents'][0]['artifact_id'] = 'src_unknown_saved_document'
        else:
            result = semantic.verify(envelope['context'], envelope['proposal'], {})['result']
        return response(canonical(result).decode())
    client = httpx.Client(transport=httpx.MockTransport(transport))
    model = AutonomousModelV1(work, worker=worker(entry()), catalogue_entry=entry(),
        schemas={'interpret': INTERPRET_SCHEMA, 'verify': VERIFY_SCHEMA}, client=client)
    policy = PublicCorpus(default_workspace_corpus_root()).static_policy()
    service = (HostedAutonomousController(store, policy, model, lease=lease) if lease is not None
               else AutonomousController(store, policy, model))
    state = admit(store, original_packet())['state'] if mode == 'canonical' else store.intake(packet(), 'fixture-reconcile-intake')
    with monkeypatch.context() as legacy:
        def reject_optional_quote(*args):
            raise ValueError('citation quote differs from the exact acquired source')
        legacy.setattr(controller_module, 'validate_interpretation', reject_optional_quote)
        state = service.run(state['claim_id'])
    assert state['deferral']['code'] == 'verification_deferred', state.get('deferral')
    assert len(calls) == 2
    command = {'expected_revision': state['revision'], 'expected_state_sha256': state['state_sha256'],
               'idempotency_key': 'operator.saved-reconcile.01', 'actor': 'Fixture operator',
               'reason': 'Apply the completed saved results after exact item rejection support.'}
    try:
        yield service, store, work, state, command, calls
    finally:
        service.shutdown()
        client.close()
        work.close()
        if server is not None:
            server.close()


@pytest.mark.parametrize('failed_runtime', ['legacy', 'canonical', 'hosted'], indirect=True)
def test_completed_saved_results_reconcile_twice_without_transport_or_budget_write(failed_runtime, monkeypatch):
    service, store, work, failed, command, calls = failed_runtime
    before, budget = ledger_bytes(work), canonical(work.external_budget())
    original_events = deepcopy(store.events(failed['claim_id']))
    def no_transport(*args, **kwargs):
        pytest.fail('cache-only reconciliation reached provider transport')
    monkeypatch.setattr(service.model, 'interpret', no_transport)
    monkeypatch.setattr(service.model, 'verify', no_transport)
    completed = service.reconcile_saved_results(failed['claim_id'], work_store=work, **command)
    assert completed['deferral'] is None and completed['outcome']['status'] == 'deferred'
    assert completed['run_id'] == failed['run_id']
    assert completed['source_descriptors'] == failed['source_descriptors']
    assert completed.get('original_binding') == failed.get('original_binding')
    assert store.events(failed['claim_id'])[:len(original_events)] == original_events
    assert service.reconcile_saved_results(failed['claim_id'], work_store=work, **command) == completed
    kinds = [e['kind'] for e in store.events(failed['claim_id'])]
    assert kinds.count('reconciliation.started') == kinds.count('reconciliation.completed') == 1
    assert len(calls) == 2 and ledger_bytes(work) == before and canonical(work.external_budget()) == budget
    receipt = next(r['receipt'] for r in completed['receipts'] if r['kind'] == 'interpretation.accepted')
    assert [row['item_id'] for row in receipt['item_rejections']] == ['step:lt_type']
    assert receipt['item_rejections'][0]['item']['citations'][0]['quote'] == 'separate termination'
    assert not any(r.get('node_id') == 'lt_type' for r in completed['results'])
    assert store.replay(failed['claim_id'], completed['revision'])['state']['state_sha256'] == completed['state_sha256']
    prefix = store.replay(failed['claim_id'], failed['revision'])['state']
    assert prefix == failed and 'reconciliations' not in prefix


@pytest.mark.parametrize('change', ['key', 'head', 'reason', 'actor'])
def test_completed_retry_conflicts_on_any_changed_command_input(failed_runtime, change):
    service, store, work, failed, command, calls = failed_runtime
    completed = service.reconcile_saved_results(failed['claim_id'], work_store=work, **command)
    changed = {**command}
    field = {'key': 'idempotency_key', 'head': 'expected_state_sha256', 'reason': 'reason', 'actor': 'actor'}[change]
    changed[field] = 'a' * 64 if change == 'head' else command[field] + '.changed'
    with pytest.raises(AutonomousStoreError):
        service.reconcile_saved_results(failed['claim_id'], work_store=work, **changed)
    assert store.get(failed['claim_id']) == completed and len(calls) == 2


@pytest.mark.parametrize('mode', ['absent', 'missing_verify', 'pending', 'unknown', 'rejected', 'bad_terminal'])
def test_uncompleted_saved_pair_never_admits_or_dispatches(failed_runtime, monkeypatch, mode):
    service, store, work, failed, command, calls = failed_runtime
    saved = work.saved_completed_autonomous_workflow(failed['run_id'])
    if mode == 'absent':
        from casepath_api.agent_work.store import ConflictError
        def unavailable(_):
            raise ConflictError('cache-only saved pair is absent')
        monkeypatch.setattr(work, 'saved_completed_autonomous_workflow', unavailable)
    else:
        if mode == 'missing_verify':
            saved['calls'].pop('verify')
        elif mode == 'pending':
            saved['calls']['verify']['outcome'] = None
        elif mode in {'unknown', 'rejected'}:
            saved['calls']['verify']['outcome']['status'] = mode
            saved['calls']['verify']['outcome']['result'] = None
        else:
            saved['terminal']['receipt_sha256'] = '0' * 64
        monkeypatch.setattr(work, 'saved_completed_autonomous_workflow', lambda _: saved)
    before = ledger_bytes(work)
    with pytest.raises((AutonomousStoreError, ValueError, KeyError, TypeError)):
        service.reconcile_saved_results(failed['claim_id'], work_store=work, **command)
    assert store.get(failed['claim_id']) == failed and ledger_bytes(work) == before and len(calls) == 2


@pytest.mark.parametrize('field', ['config', 'schema', 'context', 'proposal', 'binding', 'request'])
def test_frozen_identity_changes_reject_before_journal_admission(failed_runtime, field):
    service, store, work, failed, command, calls = failed_runtime
    saved = work.saved_completed_autonomous_workflow(failed['run_id'])
    context = deepcopy(failed['semantic_contexts'][failed['run_id']])
    identity, schemas = deepcopy(saved['record']['identity']), {'interpret': INTERPRET_SCHEMA, 'verify': VERIFY_SCHEMA}
    if field == 'config':
        saved['record']['config']['timeout_seconds'] -= 1
    elif field == 'schema':
        schemas = deepcopy(schemas)
        schemas['verify']['title'] = 'A different schema identity'
    elif field == 'context':
        context['sources'][0]['text'] += ' Changed.'
    elif field == 'proposal':
        saved['calls']['interpret']['outcome']['result']['category']['summary'] += ' Changed.'
    elif field == 'binding':
        identity['original_binding_sha256'] = 'b' * 64
    else:
        saved['calls']['verify']['intent']['request_sha256'] = 'c' * 64
    with pytest.raises(ValueError):
        SavedAutonomousResultsV1(saved, context=context, identity=identity, schemas=schemas)
    assert store.get(failed['claim_id']) == failed and len(calls) == 2


@pytest.mark.parametrize('key_length', [171, 180])
def test_oversized_child_event_keys_reject_before_admission(failed_runtime, key_length):
    service, store, work, failed, command, calls = failed_runtime
    with pytest.raises(AutonomousStoreError):
        service.reconcile_saved_results(failed['claim_id'], work_store=work,
                                       **{**command, 'idempotency_key': 'a' * key_length})
    assert store.get(failed['claim_id']) == failed and len(calls) == 2


def test_failure_is_not_resumed_or_retried_by_normal_controller(failed_runtime, monkeypatch):
    service, store, work, failed, command, calls = failed_runtime
    monkeypatch.setattr(service.model, 'interpret', lambda *_: pytest.fail('failed workflow was sent'))
    assert service.run(failed['claim_id']) == failed
    service.resume()
    service._executor.submit(lambda: None).result(timeout=10)
    assert service._jobs == {} and store.get(failed['claim_id']) == failed
    with pytest.raises(AutonomousStoreError, match='paused'):
        store.append(failed['claim_id'], 'work.resumed', {'reason': 'Bypass failed verification'},
                     expected_revision=failed['revision'], expected_state_sha256=failed['state_sha256'],
                     idempotency_key='fixture.resume-failed')
    assert len(calls) == 2


@pytest.mark.parametrize('failed_runtime', ['hosted'], indirect=True)
def test_busy_hosted_lease_denies_without_queue_or_event(failed_runtime):
    service, store, work, failed, command, calls = failed_runtime
    token = service._hosted_lease.acquire()
    try:
        with pytest.raises(AutonomousStoreError, match='busy'):
            service.reconcile_saved_results(failed['claim_id'], work_store=work, **command)
        assert store.get(failed['claim_id']) == failed
        assert service._jobs == service._waiting == {} and len(calls) == 2
    finally:
        service._hosted_lease.release(token)


@pytest.mark.parametrize('race', ['paused', 'new_source'])
def test_pause_or_new_evidence_during_application_keeps_its_own_head(failed_runtime, monkeypatch, race):
    service, store, work, failed, command, calls = failed_runtime
    apply = AutonomousController._apply_verified
    raced = []
    def change(execution, *args):
        state = store.get(failed['claim_id'])
        if race == 'paused':
            state = store.append(failed['claim_id'], 'work.deferred', {'code': 'paused', 'reason': 'Operator paused.'},
                                 expected_revision=state['revision'], expected_state_sha256=state['state_sha256'],
                                 idempotency_key='fixture.concurrent-pause')
        else:
            files = packet('Extra')['files']
            files[0]['file_name'] = 'extra-notice.txt'
            state = store.add_sources(failed['claim_id'], files,
                                      expected_revision=state['revision'], expected_state_sha256=state['state_sha256'],
                                      idempotency_key='fixture.concurrent-source')
        raced.append(state)
        return apply(execution, *args)
    monkeypatch.setattr(AutonomousController, '_apply_verified', change)
    with pytest.raises(AutonomousStoreError, match='did not complete'):
        service.reconcile_saved_results(failed['claim_id'], work_store=work, **command)
    assert store.get(failed['claim_id']) == raced[0]
    assert not any(e['kind'] == 'reconciliation.completed' for e in store.events(failed['claim_id']))
    assert len(calls) == 2


def test_failed_deterministic_application_preserves_failure_and_requires_new_command(failed_runtime, monkeypatch):
    service, store, work, failed, command, calls = failed_runtime
    with monkeypatch.context() as interruption:
        interruption.setattr(AutonomousController, '_apply_verified',
                            lambda *_: (_ for _ in ()).throw(ValueError('deterministic fixture stopped')))
        with pytest.raises(AutonomousStoreError, match='did not complete'):
            service.reconcile_saved_results(failed['claim_id'], work_store=work, **command)
    stopped = store.get(failed['claim_id'])
    assert stopped['deferral'] == failed['deferral'] and stopped['reconciliations'][0]['status'] == 'failed'
    with pytest.raises(AutonomousStoreError, match='incomplete or failed'):
        service.reconcile_saved_results(failed['claim_id'], work_store=work, **command)
    complete = service.reconcile_saved_results(failed['claim_id'], work_store=work, **{**command,
        'idempotency_key': 'operator.saved-reconcile.02', 'expected_revision': stopped['revision'],
        'expected_state_sha256': stopped['state_sha256']})
    assert complete['deferral'] is None and [r['status'] for r in complete['reconciliations']] == ['failed', 'completed']
    assert len(calls) == 2


@pytest.mark.parametrize('failed_runtime', ['bad_document'], indirect=True)
def test_rejected_document_is_preserved_but_never_reviewed_or_learned(failed_runtime):
    service, store, work, failed, command, calls = failed_runtime
    complete = service.reconcile_saved_results(failed['claim_id'], work_store=work, **command)
    receipt = next(r['receipt'] for r in complete['receipts'] if r['kind'] == 'interpretation.accepted')
    rejected = next(r for r in receipt['item_rejections'] if r['item_id'].startswith('document:'))
    assert rejected['item_id'] == 'document:spouse_notice_copy:src_unknown_saved_document'
    assert rejected['item']['artifact_id'] == 'src_unknown_saved_document'
    assert rejected['item']['assessment'] == 'sufficient' and rejected['item']['citations']
    assert rejected['reason'] == 'document assessment source differs from its citations'
    assert not any(a['result']['type'] == 'document_review' for a in complete['actions'])
    assert all(not d['held_files'] for d in complete['graph']['document_catalog'])
    assert receipt['knowledge_candidates'] == []
    assert all(not k.get('evidence_recipes') for k in complete['knowledge_published'])
    assert store.replay(failed['claim_id'], complete['revision'])['state'] == complete
    assert len(calls) == 2


def test_control_plane_cache_only_route_keeps_existing_origin_guard_and_denials(failed_runtime, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from casepath_api.autonomous_api_v1 import create_autonomous_router
    from casepath_api.agent_work.store import ConflictError, WorkStoreError
    from casepath_api.hosted_model_v1 import HostedModel
    service, store, work, failed, command, calls = failed_runtime
    service.model = None  # Saved-result repair remains usable with the paid profile disabled.
    monkeypatch.setattr(HostedModel, '_refresh', lambda *_: pytest.fail('cache-only route refreshed provider catalogue'))
    monkeypatch.setattr(service, 'submit', lambda *_: pytest.fail('cache-only route queued model work'))
    app = FastAPI()
    app.include_router(create_autonomous_router(lambda: service, saved_work_getter=lambda: work))
    path = f"/api/claim-loops/v1/autonomous/claims/{failed['claim_id']}/reconcile-saved-results"
    headers = {'X-CasePath-Agent-Work': '1'}
    with TestClient(app) as client:
        assert client.get(path).status_code == 405
        assert client.post(path, json=command).status_code == 403
        assert client.post(path, json=command, headers={**headers, 'Origin': 'https://external.test'}).status_code == 403
        for error in (ConflictError('both completed saved stages are required'), WorkStoreError('autonomous provider ledger is invalid')):
            with monkeypatch.context() as absent:
                absent.setattr(work, 'saved_completed_autonomous_workflow', lambda _, error=error: (_ for _ in ()).throw(error))
                denied = client.post(path, json=command, headers=headers)
                assert denied.status_code == 409, denied.text
                assert store.get(failed['claim_id']) == failed
        completed = client.post(path, json=command, headers=headers)
        assert completed.status_code == 200, completed.text
        assert client.post(path, json=command, headers=headers).json() == completed.json()
    assert len(calls) == 2


def test_saved_workflow_accessor_is_select_only_and_requires_complete_pair(tmp_path):
    from casepath_api.agent_work.store import ConflictError
    from test_autonomous_model_v1 import setup, IDENTITY
    work, model, calls, _ = setup(tmp_path)
    try:
        interpreted = model.interpret({}, IDENTITY)
        before = ledger_bytes(work)
        with pytest.raises(ConflictError, match='both completed'):
            work.saved_completed_autonomous_workflow(IDENTITY['workflow_id'])
        assert ledger_bytes(work) == before
        model.verify({}, interpreted['result'], IDENTITY)
        snapshot, budget = ledger_bytes(work), canonical(work.external_budget())
        frozen = work.saved_completed_autonomous_workflow(IDENTITY['workflow_id'])
        frozen['record']['config']['model'] = 'caller/mutation'
        assert work.saved_completed_autonomous_workflow(IDENTITY['workflow_id'])['record']['config']['model'] != 'caller/mutation'
        assert ledger_bytes(work) == snapshot and canonical(work.external_budget()) == budget and len(calls) == 2
    finally:
        model._client.close()
        work.close()
