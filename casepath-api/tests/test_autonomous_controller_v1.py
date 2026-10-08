import base64
from copy import deepcopy

from casepath_api.autonomous_controller_v1 import AutonomousController
from casepath_api.autonomous_policy_v1 import proposal_items
from casepath_api.autonomous_store_v1 import AutonomousStore
from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root


class SemanticFixture:
    """Explicit isolated test double; never installed by product configuration."""
    def __init__(self):
        self.calls = []

    def interpret(self, context, identity):
        self.calls.append(('interpret', identity))
        source = next(s for s in context['sources'] if s['role'] == 'customer_message')
        cite = [{'artifact_id': source['artifact_id'], 'quote': source['text']}]
        result = {'category': {'family': 'lease_termination_dispute', 'summary': 'A termination dispute.', 'citations': cite},
                  'conditions': [{'flag': flag, 'verdict': 'true' if flag in {'family_home', 'termination_received'} else 'false',
                                  'summary': 'Explicit statement in the intake.', 'citations': cite}
                                 for flag in ('termination_received', 'family_home', 'arrears', 'retaliation_screen', 'extension_relevant')],
                  'documents': [], 'steps': [{'node_id': 'lt_intake', 'status': 'established', 'summary': 'Captured the termination account.', 'citations': cite}],
                  'knowledge_candidates': []}
        for source in context['sources']:
            if source['role'] == 'supporting_document':
                result['documents'].append({'document_type': 'spouse_notice_copy', 'artifact_id': source['artifact_id'],
                                            'assessment': 'sufficient', 'summary': 'Separate spouse notice is supplied.',
                                            'citations': [{'artifact_id': source['artifact_id'], 'quote': source['text']}]})
        return {'result': result, 'receipt': {'fixture': True}}

    def verify(self, context, proposal, identity):
        self.calls.append(('verify', identity))
        return {'result': {'family_supported': True, 'checks': [{'item_id': key, 'accepted': True, 'reason': 'Test fixture'}
                                                               for key in proposal_items(proposal)], 'issues': []}, 'receipt': {'fixture': True}}


def packet(title='New incoming termination'):
    return {'title': title, 'message': 'I received a termination of our family home. No arrears, retaliation or extension request.',
            'files': [{'file_name': 'spouse-notice.txt', 'media_type': 'text/plain',
                       'content_base64': base64.b64encode(b'Separate termination addressed to spouse Alex. Delivered 2026-10-01.').decode()}]}


def test_two_incoming_claims_execute_acquire_learn_reuse_and_restart(tmp_path):
    store = AutonomousStore(tmp_path / 'claims.sqlite3')
    model = SemanticFixture()
    policy = PublicCorpus(default_workspace_corpus_root()).static_policy()
    service = AutonomousController(store, policy, model)
    first = store.intake(packet(), 'new-intake-one')
    done = service.run(first['claim_id'])
    assert done['status'] == 'deferred', done.get('deferral')
    assert done['outcome'], done.get('deferral')
    assert len(done['acquired_sources']) == 2
    assert done['graph']['conditions']['family_home']['verdict'] == 'true'
    spouse = next(d for d in done['evaluation']['documents'] if d['document_type'] == 'spouse_notice_copy')
    assert spouse['review_state'] == 'sufficient'
    assert next(n for n in done['evaluation']['nodes'] if n['node_id'] == 'lt_intake')['execution_state'] == 'completed'
    assert done['outcome']['request_draft']['status'] == 'prepared_not_sent'
    assert len(done['knowledge_published']) == 1
    knowledge = done['knowledge_published'][0]
    assert knowledge['qualification']['status'] == 'qualified', knowledge
    assert knowledge['qualification']['regression_cases'] == 243
    assert all(not d['held_files'] for d in knowledge['graph']['document_catalog'])
    assert all(v['verdict'] == 'unresolved' for v in knowledge['graph']['conditions'].values())
    second = store.intake(packet('Another new claim'), 'new-intake-two')
    second = service.run(second['claim_id'])
    assert second['outcome'], second.get('deferral')
    assert second['knowledge_uses'][0]['avoided_rule_compilations'] == 1
    assert len(model.calls) == 4
    saved = second['state_sha256']
    assert service.run(second['claim_id'])['state_sha256'] == saved
    assert len(model.calls) == 4
    assert AutonomousStore(tmp_path / 'claims.sqlite3').get(second['claim_id'])['state_sha256'] == saved
    service.shutdown()


def test_no_provider_is_explicit_deferral_never_fake_review(tmp_path):
    store = AutonomousStore(tmp_path / 'claims.sqlite3')
    service = AutonomousController(store, PublicCorpus(default_workspace_corpus_root()).static_policy())
    state = service.run(store.intake(packet(), 'no-provider')['claim_id'])
    assert state['deferral']['code'] == 'model_unavailable'
    assert state['graph']['family'] == 'incoming_packet'
    assert not state['actions'] and not state['knowledge_published']
    service.shutdown()
