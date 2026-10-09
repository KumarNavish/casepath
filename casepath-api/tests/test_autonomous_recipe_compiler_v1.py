"""Missing recipe coverage from a real public-fictional response; no network."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from casepath_api.autonomous_controller_v1 import AutonomousController
from casepath_api.autonomous_policy_v1 import (
    INTERPRET_SCHEMA, VERIFY_SCHEMA, KNOWLEDGE_RECIPE_COMPILER, REQUIRED_FIELDS,
    compile_verification_proposal, proposal_items, validate_interpretation,
)
from casepath_api.autonomous_store_v1 import AutonomousStore
from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root, digest_value
from test_autonomous_knowledge_refinement_v1 import RecipeFixture, packet, with_receipt
from test_autonomous_model_v1 import IDENTITY, response, setup


@pytest.fixture
def robin():
    data = json.loads((Path(__file__).parent / 'fixtures/autonomous_robin_omitted_recipe_v1.json').read_text())
    policy = PublicCorpus(default_workspace_corpus_root()).static_policy()
    context = {'knowledge_recipe_compiler': KNOWLEDGE_RECIPE_COMPILER, 'sources': data['sources'],
               'rule_packs': [{'family': row['domain'], 'template_id': row['template_id'],
                              'process_catalog': row['process_catalog']} for row in policy['templates']]}
    return policy, context, data['raw_proposal'], data['original_verifier']


def accept_all(proposal):
    return {'family_supported': True, 'checks': [{'item_id': key, 'accepted': True, 'reason': 'Isolated verifier fixture'}
                                                for key in proposal_items(proposal)], 'issues': []}


def test_actual_omission_is_compiled_before_verification_and_raw_output_is_unchanged(robin):
    policy, context, proposal, original_verifier = robin
    original = deepcopy(proposal)
    assert [row['document_type'] for row in proposal['documents']] == ['lease_contract', 'proof_of_receipt']
    assert [row['document_type'] for row in proposal['knowledge_candidates']] == ['lease_contract']
    compiled, receipt = compile_verification_proposal(context, proposal)
    assert proposal == original and compiled['knowledge_candidates'][0] == proposal['knowledge_candidates'][0]
    recipe = compiled['knowledge_candidates'][1]
    proof = proposal['documents'][1]
    assert recipe['document_type'] == 'proof_of_receipt'
    assert recipe['required_fields'] == REQUIRED_FIELDS['proof_of_receipt']
    assert recipe['rule_refs'] == ['policy-lease_termination_dispute-v1']
    assert recipe['citations'] == proof['citations']
    assert receipt['raw_proposal_sha256'] == digest_value(proposal)
    assert receipt['compiled_proposal_sha256'] == digest_value(compiled)
    assert receipt['receipt_sha256'] == digest_value({k: v for k, v in receipt.items() if k != 'receipt_sha256'})
    assert receipt['derived_items'] == [{'item_id': 'knowledge:proof_of_receipt',
        'source_item_id': 'document:proof_of_receipt:' + proof['artifact_id'],
        'source_item_sha256': digest_value(proof), 'candidate_sha256': digest_value(recipe)}]
    with pytest.raises(ValueError, match='coverage'):
        validate_interpretation(policy, context['sources'], compiled, original_verifier)
    verified = validate_interpretation(policy, context['sources'], compiled, accept_all(compiled))
    assert [row['document_type'] for row in verified['knowledge_candidates']] == ['lease_contract', 'proof_of_receipt']


def test_independent_rejection_of_derived_candidate_remains_a_rejection(robin):
    policy, context, proposal, _ = robin
    compiled, _ = compile_verification_proposal(context, proposal)
    verifier = accept_all(compiled)
    next(row for row in verifier['checks'] if row['item_id'] == 'knowledge:proof_of_receipt')['accepted'] = False
    verified = validate_interpretation(policy, context['sources'], compiled, verifier)
    assert [row['document_type'] for row in verified['knowledge_candidates']] == ['lease_contract']
    assert verified['knowledge_rejections'][0]['candidate']['document_type'] == 'proof_of_receipt'


@pytest.mark.parametrize('mutation', ['insufficient', 'incomplete', 'message', 'unsupported', 'wrong_source', 'wrong_artifact_quote', 'invented_quote'])
def test_compiler_cannot_invent_support_for_ineligible_documents(robin, mutation):
    policy, context, proposal, _ = robin
    document = proposal['documents'][1]
    source = next(row for row in context['sources'] if row['artifact_id'] == document['artifact_id'])
    if mutation == 'insufficient':
        document['assessment'] = 'insufficient'
    elif mutation == 'incomplete':
        source['complete'] = False
    elif mutation == 'message':
        source['role'] = 'customer_message'
    elif mutation == 'unsupported':
        document['document_type'] = 'settlement_authorization'
    elif mutation == 'wrong_source':
        document['citations'] = deepcopy(proposal['category']['citations'])
    elif mutation == 'wrong_artifact_quote':
        document['citations'][0]['quote'] = proposal['category']['citations'][0]['quote']
    else:
        document['citations'][0]['quote'] = 'This text was never supplied.'
    original = deepcopy(proposal)
    compiled, receipt = compile_verification_proposal(context, proposal)
    assert proposal == original and compiled == proposal and receipt['derived_items'] == []
    if mutation in {'unsupported', 'wrong_source', 'wrong_artifact_quote', 'invented_quote'}:
        with pytest.raises(ValueError):
            validate_interpretation(policy, context['sources'], compiled, accept_all(compiled))
    else:
        verified = validate_interpretation(policy, context['sources'], compiled, accept_all(compiled))
        assert verified['documents'][1]['assessment'] == 'insufficient'


def test_invalid_model_candidate_is_preserved_and_duplicates_are_never_repaired(robin):
    _, context, proposal, _ = robin
    invalid = {'document_type': 'proof_of_receipt', 'required_fields': [], 'summary': 'Unsupported original candidate',
               'citations': [], 'rule_refs': []}
    proposal['knowledge_candidates'].append(invalid)
    compiled, receipt = compile_verification_proposal(context, proposal)
    assert compiled == proposal and receipt['derived_items'] == []
    proposal['knowledge_candidates'].append(deepcopy(invalid))
    with pytest.raises(ValueError, match='duplicate'):
        compile_verification_proposal(context, proposal)


def test_compilation_cannot_overflow_the_closed_candidate_or_verifier_rosters(robin):
    _, context, proposal, _ = robin
    proposal['knowledge_candidates'] = [{'document_type': 'explicit_' + str(index), 'required_fields': [],
        'summary': 'Unmodified explicit candidate', 'citations': [], 'rule_refs': []} for index in range(10)]
    before = deepcopy(proposal)
    with pytest.raises(ValueError, match='bounded verification contract'):
        compile_verification_proposal(context, proposal)
    assert proposal == before


@pytest.mark.parametrize('legacy', [False, True])
def test_real_adapter_binds_raw_parent_and_compiled_verifier_request_then_replays_without_send(tmp_path, robin, legacy):
    _, context, proposal, _ = robin
    if legacy:
        context.pop('knowledge_recipe_compiler')
    envelopes = []
    def reply(request):
        body = json.loads(request.content)
        envelope = json.loads(body['messages'][1]['content'])
        envelopes.append(envelope)
        output = proposal if body['response_format']['json_schema']['name'] == 'casepath_interpret' else accept_all(envelope['proposal'])
        return response(json.dumps(output))
    budget, model, calls, _ = setup(tmp_path, reply)
    model.schemas = {'interpret': INTERPRET_SCHEMA, 'verify': VERIFY_SCHEMA}
    try:
        raw = model.interpret(context, IDENTITY)
        verified = model.verify(context, raw['result'], IDENTITY)
        assert raw['result'] == proposal and raw['receipt']['result_sha256'] == digest_value(proposal)
        compiled, compilation = compile_verification_proposal(context, proposal)
        assert envelopes[1]['proposal'] == compiled
        assert envelopes[1]['item_ids'] == list(proposal_items(compiled))
        assert verified['receipt']['metadata'].get('knowledge_recipe_compilation') == compilation
        if legacy:
            assert envelopes[1] == {'context': context, 'proposal': proposal, 'item_ids': list(proposal_items(proposal))}
        else:
            assert envelopes[1]['knowledge_recipe_compilation'] == compilation
            assert 'knowledge:proof_of_receipt' in envelopes[1]['item_ids']
        with budget.connect() as db:
            intent = json.loads(db.execute("SELECT record_json FROM work_autonomous_calls WHERE stage='verify'").fetchone()[0])
            stored = json.loads(db.execute("SELECT record_json FROM work_autonomous_outcomes WHERE stage='interpret'").fetchone()[0])
        assert intent['proposal_sha256'] == digest_value(proposal) and stored['result'] == proposal
        assert intent['context_sha256'] == digest_value(context)
        assert model.verify(context, proposal, IDENTITY) == verified and len(calls) == 2
    finally:
        budget.close()


class OmittedRecipeFixture(RecipeFixture):
    def interpret(self, context, identity):
        result = super().interpret(context, identity)
        result['result']['knowledge_candidates'] = [row for row in result['result']['knowledge_candidates']
                                                   if row['document_type'] != 'proof_of_receipt']
        return result


def test_omitted_recipe_produces_verified_v2_then_reuse_without_rewriting_v1(tmp_path):
    store = AutonomousStore(tmp_path / 'claims.sqlite3')
    model = OmittedRecipeFixture()
    service = AutonomousController(store, PublicCorpus(default_workspace_corpus_root()).static_policy(), model)
    try:
        first = service.run(store.intake(packet(), 'compiler.first')['claim_id'])
        v1 = deepcopy(first['knowledge_published'][0])
        second = service.run(store.intake(with_receipt(), 'compiler.second')['claim_id'])
        assert second['outcome'], second.get('deferral')
        v2 = second['knowledge_published'][0]
        assert v2['version'] == 2 and v2['added_document_types'] == ['proof_of_receipt']
        receipt = next(row['receipt'] for row in second['receipts'] if row['kind'] == 'interpretation.accepted')
        compilation = receipt['knowledge_recipe_compilation']
        assert compilation['raw_proposal_sha256'] == receipt['proposal_sha256']
        assert compilation == receipt['verifier_receipt']['metadata']['knowledge_recipe_compilation']
        assert [row['item_id'] for row in compilation['derived_items']] == ['knowledge:proof_of_receipt']
        assert store.get(first['claim_id'])['knowledge_published'][0] == v1
        third = service.run(store.intake(with_receipt(), 'compiler.third')['claim_id'])
        assert third['outcome'] and third['knowledge_published'] == []
        assert third['knowledge_uses'][0]['version'] == 2 and len(model.calls) == 6
        saved = third['state_sha256']
        assert service.run(third['claim_id'])['state_sha256'] == saved and len(model.calls) == 6
    finally:
        service.shutdown()


def test_controller_rejects_verifier_receipt_without_exact_compilation_binding(tmp_path):
    class UnboundVerifier(OmittedRecipeFixture):
        def verify(self, context, proposal, identity):
            result = super().verify(context, proposal, identity)
            result['receipt']['metadata'] = {}
            return result
    store = AutonomousStore(tmp_path / 'claims.sqlite3')
    service = AutonomousController(store, PublicCorpus(default_workspace_corpus_root()).static_policy(), UnboundVerifier())
    try:
        state = service.run(store.intake(with_receipt(), 'compiler.unbound')['claim_id'])
        assert state['deferral']['code'] == 'verification_deferred'
        assert 'compiled proposal' in state['deferral']['reason']
        assert not state['knowledge_published'] and not state['outcome']
    finally:
        service.shutdown()


def test_rejected_parent_document_cannot_qualify_a_derived_recipe(tmp_path):
    class RejectedDocument(OmittedRecipeFixture):
        def verify(self, context, proposal, identity):
            result = super().verify(context, proposal, identity)
            for row in result['result']['checks']:
                if row['item_id'].startswith('document:proof_of_receipt:'):
                    row['accepted'] = False
                    row['reason'] = 'The supplied source does not establish delivery.'
            return result
    store = AutonomousStore(tmp_path / 'claims.sqlite3')
    service = AutonomousController(store, PublicCorpus(default_workspace_corpus_root()).static_policy(), RejectedDocument())
    try:
        first = service.run(store.intake(packet(), 'compiler.valid-base')['claim_id'])
        assert first['knowledge_published'][0]['version'] == 1
        second = service.run(store.intake(with_receipt(), 'compiler.rejected-document')['claim_id'])
        assert second['outcome'], second.get('deferral')
        assert next(row for row in second['evaluation']['documents'] if row['document_type'] == 'proof_of_receipt')['review_state'] == 'insufficient'
        assert second['knowledge_published'] and all(row['qualification']['status'] == 'quarantined' for row in second['knowledge_published'])
        assert service.knowledge.compatible('lease_termination_dispute')['version'] == 1
    finally:
        service.shutdown()
