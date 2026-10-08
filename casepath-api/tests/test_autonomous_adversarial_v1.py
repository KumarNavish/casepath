"""Adversarial orchestration regressions with explicit in-process model doubles."""
import base64
from copy import deepcopy
from threading import Event
from time import monotonic, sleep

from casepath_api.autonomous_controller_v1 import AutonomousController
from casepath_api.autonomous_store_v1 import AutonomousStore
from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root
from casepath_api.workspace_corpus import digest_value
from test_autonomous_controller_v1 import SemanticFixture, packet


class InterleavingModel(SemanticFixture):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def interpret(self, context, identity):
        result = super().interpret(context, identity)
        self.callback(context['claim_id'])
        return result


def test_arrival_during_inference_cannot_be_overwritten_by_old_terminal_outcome(tmp_path):
    store = AutonomousStore(tmp_path / 'claims.sqlite3')
    added = []

    def arrival(claim_id):
        if added:
            return
        state = store.get(claim_id)
        arrived = store.add_sources(claim_id, [{
            'file_name': 'new-evidence.txt', 'media_type': 'text/plain',
            'content_base64': base64.b64encode(b'The later notice supersedes the first notice.').decode(),
        }], expected_revision=state['revision'], expected_state_sha256=state['state_sha256'], idempotency_key='evidence.arrived')
        added.append(arrived['source_descriptors'][-1]['artifact_id'])

    service = AutonomousController(store, PublicCorpus(default_workspace_corpus_root()).static_policy(), InterleavingModel(arrival))
    try:
        state = service.run(store.intake(packet(), 'arrival-race')['claim_id'])
        acquired = {source['artifact_id'] for source in state['acquired_sources']}
        assert added[0] in acquired or state['status'] in {'received', 'running'}, (
            'Old inference overwrote the arrival with a terminal state while the new evidence remains unacquired')
    finally:
        service.shutdown()


def test_pause_during_inference_stops_before_the_verifier_and_graph_commit(tmp_path):
    store = AutonomousStore(tmp_path / 'claims.sqlite3')

    def pause(claim_id):
        state = store.get(claim_id)
        store.append(claim_id, 'work.deferred', {'code': 'paused', 'reason': 'Pause requested.'},
                     expected_revision=state['revision'], expected_state_sha256=state['state_sha256'], idempotency_key='pause.now')

    model = InterleavingModel(pause)
    service = AutonomousController(store, PublicCorpus(default_workspace_corpus_root()).static_policy(), model)
    try:
        state = service.run(store.intake(packet(), 'pause-race')['claim_id'])
        assert state.get('deferral', {}).get('code') == 'paused'
        assert [kind for kind, _ in model.calls] == ['interpret'], 'A paused workflow dispatched new verifier inference'
        assert state['graph']['family'] == 'incoming_packet'
        assert not state['actions'] and not state['outcome']
    finally:
        service.shutdown()


class MixedDocumentModel(SemanticFixture):
    def interpret(self, context, identity):
        packet = super().interpret(context, identity)
        packet['result']['documents'][-1]['assessment'] = 'insufficient'
        packet['result']['documents'][-1]['summary'] = 'This additional file is incomplete.'
        return packet


def test_document_fact_aggregates_all_sources_instead_of_last_file(tmp_path):
    store = AutonomousStore(tmp_path / 'claims.sqlite3')
    incoming = packet()
    incoming['files'].append({'file_name': 'partial-copy.txt', 'media_type': 'text/plain',
                              'content_base64': base64.b64encode(b'An incomplete copy.').decode()})
    service = AutonomousController(store, PublicCorpus(default_workspace_corpus_root()).static_policy(), MixedDocumentModel())
    try:
        state = service.run(store.intake(incoming, 'mixed-document-source')['claim_id'])
        document = next(row for row in state['evaluation']['documents'] if row['document_type'] == 'spouse_notice_copy')
        fact = next(row for row in state['facts'] if row['fact_id'] == 'fact:spouse_notice_copy')
        assert document['review_state'] == 'sufficient'
        assert fact['status'] == 'established', 'Fact status contradicts the sufficient original document because an extra file was inspected last'
    finally:
        service.shutdown()


def add_evidence(store, claim_id, key):
    state = store.get(claim_id)
    result = store.add_sources(claim_id, [{
        'file_name': f'{key}.txt', 'media_type': 'text/plain',
        'content_base64': base64.b64encode(f'Additional supporting notice {key}.'.encode()).decode(),
    }], expected_revision=state['revision'], expected_state_sha256=state['state_sha256'], idempotency_key=key)
    return result['source_descriptors'][-1]['artifact_id']


def await_finished(service, store, claim_id, artifact_id, timeout=15):
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        state = store.get(claim_id)
        with service._lock:
            future = service._jobs.get(claim_id)
            idle = future is not None and future.done() and claim_id not in service._pending
        if idle and state['outcome'] and artifact_id in {s['artifact_id'] for s in state['acquired_sources']}:
            future.result()
            return state
        sleep(.01)
    raise AssertionError(f'Automatic reassessment did not settle: {store.get(claim_id)}')


def test_submit_automatically_resumes_new_evidence_arriving_during_inference(tmp_path):
    store = AutonomousStore(tmp_path / 'claims.sqlite3')
    entered, release = Event(), Event()

    def block_first(_):
        if not entered.is_set():
            entered.set()
            assert release.wait(10), 'Test did not release the first inference'

    model = InterleavingModel(block_first)
    service = AutonomousController(store, PublicCorpus(default_workspace_corpus_root()).static_policy(), model)
    try:
        claim_id = store.intake(packet(), 'submit-arrival-race')['claim_id']
        service.submit(claim_id)
        assert entered.wait(10)
        source_id = add_evidence(store, claim_id, 'while-inference')
        service.submit(claim_id)
        release.set()
        state = await_finished(service, store, claim_id, source_id)
        assert [kind for kind, _ in model.calls] == ['interpret', 'interpret', 'verify']
        assert len({identity['workflow_id'] for _, identity in model.calls}) == 2
        assert len([e for e in state['events'] if e['kind'] == 'interpretation.accepted']) == 1
        assert state['knowledge_published'][0]['qualification']['status'] == 'qualified'
    finally:
        release.set()
        service.shutdown()


def test_submit_reassesses_arrival_after_outcome_before_knowledge_publication(tmp_path):
    store = AutonomousStore(tmp_path / 'claims.sqlite3')
    model = SemanticFixture()
    service = AutonomousController(store, PublicCorpus(default_workspace_corpus_root()).static_policy(), model)
    original = service._outcome
    added = []

    def arrival_after_outcome(claim_id, workflow, verified, base_receipt):
        original(claim_id, workflow, verified, base_receipt)
        if not added:
            added.append(add_evidence(store, claim_id, 'after-outcome'))
            service.submit(claim_id)

    service._outcome = arrival_after_outcome
    try:
        claim_id = store.intake(packet(), 'outcome-arrival-race')['claim_id']
        service.submit(claim_id)
        deadline = monotonic() + 10
        while not added and monotonic() < deadline:
            sleep(.01)
        assert added, 'Workflow did not reach its first outcome'
        state = await_finished(service, store, claim_id, added[0])
        assert [kind for kind, _ in model.calls] == ['interpret', 'verify', 'interpret', 'verify']
        events = store.events(claim_id)
        published = [row for row in events if row['kind'] == 'knowledge.published']
        assert len(published) == 1
        assert published[0]['idempotency_key'].startswith(model.calls[-1][1]['workflow_id'])
        assert state['knowledge_published'][0]['qualification']['status'] == 'qualified'
    finally:
        service.shutdown()


def test_changed_rule_pack_reassesses_instead_of_accepting_old_terminal_workflow(tmp_path):
    store = AutonomousStore(tmp_path / 'claims.sqlite3')
    model = SemanticFixture()
    policy = PublicCorpus(default_workspace_corpus_root()).static_policy()
    service = AutonomousController(store, policy, model)
    try:
        claim_id = store.intake(packet(), 'rule-version-restart')['claim_id']
        original = service.run(claim_id)
    finally:
        service.shutdown()
    changed = deepcopy(policy)
    template = next(row for row in changed['templates'] if row['domain'] == 'lease_termination_dispute')
    template['content'] += '\nOperational rule clarification for the next admitted version.'
    restarted = AutonomousController(store, changed, model)
    try:
        state = restarted.run(claim_id)
        assert state['outcome']
        assert len(model.calls) == 4, 'A terminal event from a previous rule version skipped fresh interpretation and verification'
        assert state['graph']['assessment_context']['rule_pack_sha256'] == digest_value(template)
        assert state['graph']['assessment_context']['rule_pack_sha256'] != original['graph']['assessment_context']['rule_pack_sha256']
    finally:
        restarted.shutdown()


def test_startup_skips_paused_terminal_and_incomplete_claims(tmp_path):
    store = AutonomousStore(tmp_path / 'claims.sqlite3')
    model = SemanticFixture()
    service = AutonomousController(store, PublicCorpus(default_workspace_corpus_root()).static_policy(), model)
    scheduled, paused_states = [], []
    try:
        terminal = service.run(store.intake(packet(), 'paused.terminal')['claim_id'])
        incomplete = store.intake(packet(), 'paused.incomplete')
        for state in (terminal, incomplete):
            paused_states.append(store.append(state['claim_id'], 'work.deferred',
                {'code': 'paused', 'reason': 'Remain paused across restart.'},
                expected_revision=state['revision'], expected_state_sha256=state['state_sha256'],
                idempotency_key='pause.restart'))
        service._learn = lambda claim_id, workflow: scheduled.append(('knowledge', claim_id))
        service.submit = lambda claim_id: scheduled.append(('inference', claim_id))
        service.resume()
    finally:
        service.shutdown()
    assert scheduled == []
    assert [kind for kind, _ in model.calls] == ['interpret', 'verify']
    assert all(store.get(state['claim_id'])['state_sha256'] == state['state_sha256'] for state in paused_states)
