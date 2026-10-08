from copy import deepcopy

import pytest

from casepath_api.autonomous_policy_v1 import (
    proposal_items, validate_interpretation, compile_process, initial_process,
)
from casepath_api.causal_process_v1 import evaluate
from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root, digest_value


def materials():
    policy = PublicCorpus(default_workspace_corpus_root()).static_policy()
    source = {'artifact_id': 'message', 'sha256': 'a' * 64, 'text': 'My landlord sent a termination. This is not a family home.',
              'complete': True, 'role': 'message', 'file_name': 'message.txt', 'media_type': 'text/plain'}
    citation = {'artifact_id': 'message', 'quote': 'My landlord sent a termination.'}
    proposal = {'category': {'family': 'lease_termination_dispute', 'summary': 'Termination reported.', 'citations': [citation]},
                'conditions': [{'flag': 'family_home', 'verdict': 'false', 'summary': 'Customer expressly denies family-home status.',
                                'citations': [{'artifact_id': 'message', 'quote': 'This is not a family home.'}]}],
                'documents': [], 'steps': [{'node_id': 'lt_intake', 'status': 'established', 'summary': 'Termination reported.', 'citations': [citation]}]}
    verifier = {'family_supported': True, 'checks': [{'item_id': key, 'accepted': True, 'reason': 'Supported by the cited text.'}
                for key in proposal_items(proposal)], 'issues': []}
    return policy, [source], proposal, verifier


def test_verifier_must_cover_every_proposition_and_exact_source():
    policy, sources, proposal, verifier = materials()
    with pytest.raises(ValueError, match='coverage'):
        validate_interpretation(policy, sources, proposal, {**verifier, 'checks': []})
    proposal['conditions'][0]['citations'][0]['artifact_id'] = 'another-claim'
    with pytest.raises(ValueError, match='source'):
        validate_interpretation(policy, sources, proposal, verifier)


def test_quotes_are_not_semantic_acceptance_and_absence_stays_unknown():
    policy, sources, proposal, verifier = materials()
    verifier['checks'][1]['accepted'] = False
    verified = validate_interpretation(policy, sources, proposal, verifier)
    graph, facts, obligations = compile_process(policy, 'claim', verified)
    assert graph['conditions']['family_home']['verdict'] == 'unresolved'
    assert graph['conditions']['arrears']['verdict'] == 'unresolved'
    assert all(not node['completed'] for node in graph['nodes'])
    assert all(o['required_fact_ids'] and o['rule_refs'] for o in obligations)
    assert {o['document_type'] for o in obligations} == {d['document_type'] for d in graph['document_catalog']}
    assert evaluate(graph)['documents']


def test_message_cannot_stand_in_for_a_required_original_document():
    policy, sources, proposal, _ = materials()
    proposal['documents'] = [{'document_type': 'termination_notice', 'artifact_id': 'message', 'assessment': 'sufficient',
                              'summary': 'Notice mentioned.', 'citations': proposal['category']['citations']}]
    verifier = {'family_supported': True, 'checks': [{'item_id': key, 'accepted': True, 'reason': 'Supported'}
                for key in proposal_items(proposal)], 'issues': []}
    verified = validate_interpretation(policy, sources, proposal, verifier)
    assert verified['documents'][0]['assessment'] == 'insufficient'


def test_initial_process_is_operational_and_has_no_claim_decisions():
    graph, facts, obligations = initial_process('claim', [{'artifact_id': 'file', 'file_name': 'proof.pdf'}])
    assert graph['family'] == 'incoming_packet'
    assert facts[0]['fact_id'] == obligations[0]['required_fact_ids'][0]
    assert obligations[0]['capability_id'] == 'local_inbox.read'
    assert evaluate(graph)['documents'][0]['route_state'] == 'needed_now'


def test_invalid_optional_knowledge_does_not_discard_valid_claim_interpretation():
    policy, sources, proposal, verifier = materials()
    proposal['knowledge_candidates'] = [{'document_type': 'invented_rule', 'required_fields': [], 'summary': 'Unsupported',
                                          'citations': [{'artifact_id': 'another-claim', 'quote': 'not here'}], 'rule_refs': []}]
    verifier['checks'].append({'item_id': 'knowledge:invented_rule', 'accepted': False, 'reason': 'Unsupported'})
    verified = validate_interpretation(policy, sources, proposal, verifier)
    assert verified['category']['family'] == 'lease_termination_dispute'
    assert verified['knowledge_candidates'] == []
    assert verified['knowledge_rejections'][0]['candidate']['document_type'] == 'invented_rule'
