"""Available originals can be reviewed without activating a conditional route."""
import base64
from copy import deepcopy
import json
from pathlib import Path

import pytest

from casepath_api.autonomous_controller_v1 import AutonomousController
from casepath_api.autonomous_policy_v1 import (
    OPERATIONAL_CONDITION_QUESTIONS, POLICY_ID, SUPPLIED_DOCUMENT_REVIEW_POLICY,
    compile_verification_proposal, proposal_items,
)
from casepath_api.autonomous_store_v1 import AutonomousStore
from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root, digest_value


def nila():
    return json.loads((Path(__file__).parent / 'fixtures/autonomous_nila_held_reviews_v1.json').read_text())


def packet():
    sources = nila()['sources']
    return {'title': 'Fictional Nila source-assessment regression',
            'message': next(row['text'] for row in sources if row['role'] == 'customer_message'),
            'files': [{'file_name': row['file_name'], 'media_type': row['media_type'],
                       'content_base64': base64.b64encode(row['text'].encode()).decode()}
                      for row in sources if row['role'] == 'supporting_document']}


class NilaFixture:
    """Replay the exact public-fictional response shape with isolated claim IDs."""
    def __init__(self, verdict='unresolved', lease_only=False):
        self.verdict, self.lease_only, self.calls = verdict, lease_only, []

    def interpret(self, context, identity):
        self.calls.append('interpret')
        saved = nila()
        names = {row['file_name']: row['artifact_id'] for row in context['sources']}
        remap = {row['artifact_id']: names[row['file_name']] for row in saved['sources']}
        proposal = deepcopy(saved['raw_proposal'])
        for row in [proposal['category'], *proposal['conditions'], *proposal['documents'],
                    *proposal['steps'], *proposal['knowledge_candidates']]:
            if 'artifact_id' in row:
                row['artifact_id'] = remap[row['artifact_id']]
            for citation in row['citations']:
                citation['artifact_id'] = remap[citation['artifact_id']]
        next(row for row in proposal['conditions'] if row['flag'] == 'termination_received')['verdict'] = self.verdict
        if self.lease_only:
            proposal['documents'] = [row for row in proposal['documents'] if row['document_type'] == 'lease_contract']
        return {'result': proposal, 'receipt': {'fixture': True, 'result': deepcopy(proposal), 'result_sha256': digest_value(proposal)}}

    def verify(self, context, proposal, identity):
        self.calls.append('verify')
        compiled, compilation = compile_verification_proposal(context, proposal)
        return {'result': {'family_supported': True, 'checks': [
            {'item_id': key, 'accepted': True, 'reason': 'Isolated independently accepted document/route fixture'}
            for key in proposal_items(compiled)], 'issues': []},
            'receipt': {'fixture': True, 'metadata': {'knowledge_recipe_compilation': compilation}}}


@pytest.mark.parametrize('verdict', ['unresolved', 'false'])
def test_held_or_inactive_original_reviews_qualify_v2_without_activating_process(tmp_path, verdict):
    store = AutonomousStore(tmp_path / 'claims.sqlite3')
    model = NilaFixture(verdict, lease_only=True)
    service = AutonomousController(store, PublicCorpus(default_workspace_corpus_root()).static_policy(), model)
    try:
        first = service.run(store.intake(packet(), 'review.baseline')['claim_id'])
        assert first['outcome'], first.get('deferral')
        v1 = deepcopy(first['knowledge_published'][0])
        assert v1['version'] == 1 and [row['document_type'] for row in v1['evidence_recipes']] == ['lease_contract']
        model.lease_only = False
        second = service.run(store.intake(packet(), 'review.refinement')['claim_id'])
        assert second['outcome'], second.get('deferral')
        v2 = second['knowledge_published'][0]
        assert v2['qualification']['status'] == 'qualified' and v2['version'] == 2
        assert v2['added_document_types'] == ['proof_of_receipt'] and v2['qualification']['regression_cases'] == 243
        assert second['graph']['conditions']['termination_received']['verdict'] == verdict
        assert all(row['activation'] == verdict for row in second['evaluation']['documents'])
        for kind in ('lease_contract', 'proof_of_receipt'):
            doc = next(row for row in second['evaluation']['documents'] if row['document_type'] == kind)
            assert doc['review_state'] == 'sufficient' and len(doc['held_files']) == 1
        assert all(row['request'] is False for row in second['evaluation']['documents'])
        assert not second['outcome']['missing_evidence']
        assert {row['node_id'] for row in second['graph']['nodes'] if row['completed']} == {'lt_intake'}
        assert not second['evaluation']['inconsistent_completed_node_ids']
        actions = [row['result'] for row in second['actions']]
        reviews = [row for row in actions if row['type'] == 'document_review']
        assert len(reviews) == 2
        assert all(row['capability_id'] == 'local_evidence.assess' and row['route_activation_at_review'] == verdict
                   and row['review_scope'] == 'supplied_file_assessment' for row in reviews)
        assert [row['node_id'] for row in actions if row['type'] == 'assessment_record'] == ['lt_intake']
        context = next(iter(second['semantic_contexts'].values()))
        assert context['document_review_policy'] == SUPPLIED_DOCUMENT_REVIEW_POLICY
        assert context['operational_condition_questions'] == OPERATIONAL_CONDITION_QUESTIONS
        for row in second['receipts']:
            if row['kind'] == 'action.completed':
                assert row['receipt']['document_review_policy'] == context['document_review_policy']
        assert store.get(first['claim_id'])['knowledge_published'][0] == v1
        saved = second['state_sha256']
        assert service.run(second['claim_id'])['state_sha256'] == saved and len(model.calls) == 4
    finally:
        service.shutdown()


def test_context_without_review_policy_retains_historical_skip_and_quarantine(tmp_path, monkeypatch):
    store = AutonomousStore(tmp_path / 'claims.sqlite3')
    append = store.append
    def legacy_context(claim_id, kind, payload, **kwargs):
        if kind == 'work.context':
            payload = deepcopy(payload)
            payload['context'].pop('document_review_policy', None)
            payload['context'].pop('operational_condition_questions', None)
        return append(claim_id, kind, payload, **kwargs)
    monkeypatch.setattr(store, 'append', legacy_context)
    model = NilaFixture()
    service = AutonomousController(store, PublicCorpus(default_workspace_corpus_root()).static_policy(), model)
    # The first invocation records a context as an older executable would, then
    # stops before model work. Reconnection must load that exact pinned context.
    original_interpret = model.interpret
    model.interpret = lambda *_: (_ for _ in ()).throw(ValueError('fixture interruption after pinning'))
    try:
        incoming = store.intake(packet(), 'review.legacy-context')
        interrupted = service.run(incoming['claim_id'])
        assert all('document_review_policy' not in context for context in interrupted['semantic_contexts'].values())
        model.interpret = original_interpret
        done = service.run(incoming['claim_id'])
        assert done['outcome'], done.get('deferral')
        assert all(row['result']['type'] != 'document_review' for row in done['actions'])
        assert all(not row['held_files'] for row in done['graph']['document_catalog'])
        assert done['knowledge_published'][0]['qualification']['status'] == 'quarantined'
        assert all('document_review_policy' not in row['receipt'] for row in done['receipts'] if row['kind'] == 'interpretation.accepted')
    finally:
        service.shutdown()


def test_review_receipt_cannot_override_the_pinned_context_policy(tmp_path):
    store = AutonomousStore(tmp_path / 'claims.sqlite3')
    service = AutonomousController(store, PublicCorpus(default_workspace_corpus_root()).static_policy(), NilaFixture())
    try:
        state = service.run(store.intake(packet(), 'review.binding')['claim_id'])
        workflow = next(iter(state['semantic_contexts']))
        before = state['state_sha256']
        with pytest.raises(ValueError, match='pinned workflow context'):
            service._documents(state['claim_id'], workflow, {'documents': []}, {})
        assert store.get(state['claim_id'])['state_sha256'] == before
    finally:
        service.shutdown()


def test_operational_question_matches_admitted_intake_then_form_and_service_order():
    policy = PublicCorpus(default_workspace_corpus_root()).static_policy()
    template = next(row for row in policy['templates'] if row['domain'] == 'lease_termination_dispute')
    question = OPERATIONAL_CONDITION_QUESTIONS['lease_termination_dispute']['termination_received']
    assert question['rule_refs'] == [template['template_id']]
    nodes = {row['node_id']: row for row in template['process_catalog']['nodes']}
    assert nodes['lt_intake']['label'] == 'Capture issuer, receipt and end date'
    assert nodes['lt_form']['label'] == 'Check form and service'
    assert 'Then verify the notice, receipt, form, service' in template['content']
    assert 'ambiguous, hypothetical or contradicted receipt unresolved' in question['meaning']
    assert 'does not establish authenticated contents' in question['limits']


def test_unknown_pinned_review_policy_rejects_before_any_model_call(tmp_path):
    store = AutonomousStore(tmp_path / 'claims.sqlite3')
    policy = PublicCorpus(default_workspace_corpus_root()).static_policy()
    model = NilaFixture()
    service = AutonomousController(store, policy, model)
    try:
        state = store.intake(packet(), 'review.unknown-policy')
        claim_id = state['claim_id']
        workflow = 'autonomy.' + digest_value({'claim': claim_id, 'sources': digest_value(state['source_descriptors']),
                                              'policy': POLICY_ID, 'rules': digest_value(policy)})[:24]
        context = {'claim_id': claim_id, 'document_review_policy': 'casepath.unrecognized-review/99.0.0'}
        store.append(claim_id, 'work.context', {'workflow_id': workflow, 'context': context},
                     expected_revision=state['revision'], expected_state_sha256=state['state_sha256'],
                     idempotency_key='fixture.pin-unknown-policy')
        done = service.run(claim_id)
        assert done['deferral']['code'] == 'verification_deferred'
        assert done['deferral']['reason'] == 'unknown supplied-document review policy'
        assert done['semantic_contexts'][workflow] == context
        assert model.calls == [] and not done['outcome'] and not done['knowledge_published']
        assert not any(row['kind'] == 'interpretation.accepted' for row in done['receipts'])
    finally:
        service.shutdown()
