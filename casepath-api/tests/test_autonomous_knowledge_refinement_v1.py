"""Bounded learning regressions use isolated stores and explicit model doubles."""
import base64
from copy import deepcopy
import json

import pytest

from casepath_api.autonomous_controller_v1 import AutonomousController
from casepath_api import autonomous_knowledge_v1 as knowledge_module
from casepath_api.autonomous_knowledge_v1 import AutonomousKnowledge, DEFINITION_KEYS, qualify
from casepath_api.autonomous_policy_v1 import REQUIRED_FIELDS
from casepath_api.autonomous_store_v1 import AutonomousStore
from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root, digest_value
from test_autonomous_controller_v1 import SemanticFixture, packet


class RecipeFixture(SemanticFixture):
    def __init__(self):
        super().__init__()
        self.contexts = []

    def interpret(self, context, identity):
        self.contexts.append(deepcopy(context))
        proposal = super().interpret(context, identity)
        template = next(row for row in context['rule_packs'] if row['family'] == 'lease_termination_dispute')
        supporting = {row['artifact_id']: row for row in context['sources'] if row['role'] == 'supporting_document'}
        candidates = []
        for document in proposal['result']['documents']:
            source = supporting[document['artifact_id']]
            document_type = 'proof_of_receipt' if source['file_name'] == 'receipt.txt' else 'spouse_notice_copy'
            document['document_type'] = document_type
            candidates.append({'document_type': document_type, 'required_fields': REQUIRED_FIELDS[document_type],
                               'summary': 'Alex CASE-SECRET-9281 supplied this observed evidence.',
                               'citations': document['citations'], 'rule_refs': [template['template_id']]})
        proposal['result']['knowledge_candidates'] = candidates
        return proposal


def with_receipt():
    incoming = packet()
    incoming['files'].append({'file_name': 'receipt.txt', 'media_type': 'text/plain',
                              'content_base64': base64.b64encode(b'Alex received the separate notice on 2026-10-01.').decode()})
    return incoming


def candidates_from(state):
    return next(row['receipt']['knowledge_candidates'] for row in reversed(state['receipts'])
                if row['kind'] == 'interpretation.accepted')


@pytest.fixture(scope='module')
def observed(tmp_path_factory):
    policy = PublicCorpus(default_workspace_corpus_root()).static_policy()
    store = AutonomousStore(tmp_path_factory.mktemp('qualified-recipes') / 'claims.sqlite3')
    service = AutonomousController(store, policy, RecipeFixture())
    try:
        state = service.run(store.intake(with_receipt(), 'knowledge.observed')['claim_id'])
        assert state['outcome'], state.get('deferral')
        assert state['knowledge_published'][0]['qualification']['status'] == 'qualified', state['knowledge_published']
        return policy, state
    finally:
        service.shutdown()


def test_second_claim_adds_immutable_recipe_version_and_unchanged_claim_publishes_nothing(tmp_path):
    policy = PublicCorpus(default_workspace_corpus_root()).static_policy()
    store = AutonomousStore(tmp_path / 'claims.sqlite3')
    model = RecipeFixture()
    service = AutonomousController(store, policy, model)
    try:
        first = service.run(store.intake(packet(), 'version.first')['claim_id'])
        assert first['outcome'], first.get('deferral')
        v1 = deepcopy(first['knowledge_published'][0])
        second = service.run(store.intake(with_receipt(), 'version.second')['claim_id'])
        assert second['outcome'], second.get('deferral')
        v2 = second['knowledge_published'][0]
        assert v1['knowledge_id'] == v2['knowledge_id']
        assert (v1['version'], v2['version']) == (1, 2)
        assert v2['parent_definition_sha256'] == v1['qualification']['definition_sha256']
        assert v2['parent_knowledge_sha256'] == v1['knowledge_sha256']
        assert v2['added_document_types'] == ['proof_of_receipt']
        assert len(v1['evidence_recipes']) == 1 and len(v2['evidence_recipes']) == 2
        assert v2['qualification']['regression_cases'] == 243
        assert store.get(first['claim_id'])['knowledge_published'][0] == v1
        third = service.run(store.intake(with_receipt(), 'version.unchanged')['claim_id'])
        assert third['outcome'], third.get('deferral')
        assert third['knowledge_published'] == []
        assert [kind for kind, _ in model.calls] == ['interpret', 'verify'] * 3
        assert model.contexts[1]['compatible_knowledge'][0]['evidence_recipes'] == v1['evidence_recipes']
        assert model.contexts[2]['compatible_knowledge'][0]['version'] == 2
        assert service.knowledge.compatible(v1['family'])['version'] == 2
        assert [row['version'] for row in service.knowledge.view()['versions']] == [1, 2]
        reusable = json.dumps({key: v2[key] for key in DEFINITION_KEYS})
        for source in second['acquired_sources']:
            assert source['artifact_id'] not in reusable
        assert 'CASE-SECRET-9281' not in reusable
        assert 'CASE-SECRET-9281' in json.dumps(v2['source_evidence'])
    finally:
        service.shutdown()


@pytest.mark.parametrize('mutation,reason', [
    ('weaken', 'required evidence fields'),
    ('add_field', 'required evidence fields'),
    ('rule', 'admitted authority'),
    ('unsupported', 'unsupported document'),
    ('no_quote', 'supporting source citations'),
    ('customer_account', 'sufficient supporting file'),
    ('reject_check', 'independent verification'),
    ('insufficient', 'sufficient supporting file'),
    ('changed_span', 'citation span differs'),
    ('changed_summary', 'accepted interpretation'),
])
def test_invalid_recipe_cannot_qualify(observed, mutation, reason):
    policy, original = observed
    state = deepcopy(original)
    candidate = deepcopy(candidates_from(state)[0])
    if mutation == 'weaken':
        candidate['required_fields'].pop()
    elif mutation == 'add_field':
        candidate['required_fields'].append('customer_value')
    elif mutation == 'rule':
        candidate['rule_refs'] = ['unadmitted-rule']
    elif mutation == 'unsupported':
        candidate['document_type'] = 'settlement_authorization'
    elif mutation == 'no_quote':
        candidate['citations'] = []
    elif mutation == 'customer_account':
        source = state['acquired_sources'][0]
        candidate['citations'] = [{'artifact_id': source['artifact_id'], 'quote': source['text']}]
    elif mutation == 'reject_check':
        receipt = next(row['receipt'] for row in reversed(state['receipts']) if row['kind'] == 'interpretation.accepted')
        next(row for row in receipt['checks'] if row['item_id'] == 'knowledge:' + candidate['document_type'])['accepted'] = False
        receipt['receipt_sha256'] = digest_value({key: value for key, value in receipt.items() if key != 'receipt_sha256'})
    elif mutation == 'insufficient':
        document = next(row for row in state['graph']['document_catalog'] if row['document_type'] == candidate['document_type'])
        document['held_files'][0]['review'] = 'insufficient'
    elif mutation == 'changed_span':
        candidate['citations'][0]['start_char'] += 1
    elif mutation == 'changed_summary':
        candidate['summary'] = 'This was never the accepted model output.'
    with pytest.raises(ValueError, match=reason):
        qualify(policy, state, candidates=[candidate])


def test_recipe_version_identity_and_case_independence_are_checked_on_reuse(observed):
    policy, state = observed
    v1 = qualify(policy, state, candidates=candidates_from(state))
    assert v1['qualification']['evidence_recipe_count'] == 2
    assert qualify(policy, state, candidates=candidates_from(state), previous=v1) is None
    knowledge = AutonomousKnowledge(None, policy)
    verified = {'category': {'family': v1['family'], 'summary': 'A new claim with no established conditions.'}, 'conditions': []}
    graph, facts, _ = knowledge.instantiate(v1, 'auto_independent', verified)
    assert all(not row['held_files'] for row in graph['document_catalog'])
    assert all(row['verdict'] == 'unresolved' for row in graph['conditions'].values())
    assert all(not row['citations'] for row in facts)
    corrupt = deepcopy(v1)
    corrupt['evidence_recipes'][0]['required_fields'].pop()
    with pytest.raises(ValueError, match='identity differs'):
        knowledge.instantiate(corrupt, 'auto_corrupt', verified)
    corrupt['qualification']['definition_sha256'] = digest_value({key: corrupt[key] for key in DEFINITION_KEYS})
    with pytest.raises(ValueError, match='admitted evidence criteria'):
        knowledge.instantiate(corrupt, 'auto_corrupt', verified)


def test_conflicting_version_identity_is_quarantined_in_projection(observed):
    policy, state = observed
    original = qualify(policy, state, candidates=candidates_from(state))
    corrupt = deepcopy(original)
    corrupt['evidence_recipes'].pop()
    corrupt['qualification']['definition_sha256'] = digest_value({key: corrupt[key] for key in DEFINITION_KEYS})

    class ReadOnlyStore:
        def list(self):
            return [{'claim_id': 'one'}, {'claim_id': 'two'}]

        def get(self, claim_id):
            return {'claim_id': claim_id, 'knowledge_published': [original if claim_id == 'one' else corrupt]}

    view = AutonomousKnowledge(ReadOnlyStore(), policy).view()
    assert view['versions'] == []
    assert view['quarantined'][0]['qualification']['status'] == 'quarantined'


def test_unchanged_recipe_reuses_qualification_without_unobserved_work_claims(observed, monkeypatch):
    policy, state = observed
    qualified = qualify(policy, state, candidates=candidates_from(state))

    def unexpected(*args, **kwargs):
        raise AssertionError('An unchanged sealed definition must not be recompiled or requalified')

    monkeypatch.setattr(knowledge_module, 'compile_process', unexpected)
    monkeypatch.setattr(knowledge_module, '_routing', unexpected)
    assert qualify(policy, state, candidates=candidates_from(state), previous=qualified) is None


def test_parent_identity_mismatch_is_quarantined(observed):
    policy, state = observed
    parent = qualify(policy, state, candidates=candidates_from(state)[:1])
    child = qualify(policy, state, candidates=candidates_from(state), previous=parent)
    child['parent_knowledge_sha256'] = '0' * 64

    class ReadOnlyStore:
        def list(self):
            return [{'claim_id': 'lineage'}]

        def get(self, claim_id):
            return {'claim_id': claim_id, 'knowledge_published': [parent, child]}

    knowledge = AutonomousKnowledge(ReadOnlyStore(), policy)
    assert knowledge.latest(parent['family'])['version'] == 1
    assert knowledge.view()['quarantined'][0]['qualification']['reason'] == 'knowledge parent lineage differs'
