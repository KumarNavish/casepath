"""Exact citation rejection is per item; original isolated outputs stay intact."""
from copy import deepcopy
from hashlib import sha256

import pytest

from casepath_api.autonomous_policy_v1 import (
    KNOWLEDGE_RECIPE_COMPILER, REQUIRED_FIELDS, compile_process, compile_verification_proposal, proposal_items,
    validate_interpretation,
)
from casepath_api.autonomous_corpus_v1 import CanonicalCorpus
from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root
from test_autonomous_controller_v1 import SemanticFixture


@pytest.fixture
def materials():
    policy = PublicCorpus(default_workspace_corpus_root()).static_policy()
    sources = []
    for artifact_id, role, text in (
        ('message', 'customer_message', 'I received a termination of our family home.\n'
         'Die Verwaltung sagte telefonisch, eines sei eine Korrektur;\n'
         'Grün blieb die Tür.\nFirst line\nSecond line'),
        ('spouse-notice', 'supporting_document',
         'Separate termination addressed to spouse Alex. Delivered 2026-10-01.'),
    ):
        digest = sha256(text.encode()).hexdigest()
        sources.append({'artifact_id': artifact_id, 'role': role, 'text': text, 'complete': True,
                        'file_name': artifact_id + '.txt', 'media_type': 'text/plain',
                        'sha256': digest, 'text_sha256': digest})
    fixture = SemanticFixture()
    context = {'sources': sources}
    proposal = fixture.interpret(context, {'fixture': True})['result']
    for row in proposal_items(proposal).values():
        row['citations'] = deepcopy(row['citations'])
    verifier = fixture.verify(context, proposal, {'fixture': True})['result']
    return policy, sources, proposal, verifier


def accept_all(proposal):
    return {'family_supported': True, 'checks': [
        {'item_id': item_id, 'accepted': True, 'reason': 'Isolated verifier fixture'}
        for item_id in proposal_items(proposal)], 'issues': []}


def identity(field, row):
    if field == 'conditions':
        return 'condition:' + row['flag']
    if field == 'documents':
        return 'document:' + row['document_type'] + ':' + row['artifact_id']
    return 'step:' + row['node_id']


def assert_rejected(verified, field, original, reason):
    row = verified[field][0]
    value_key = {'conditions': 'verdict', 'documents': 'assessment', 'steps': 'status'}[field]
    assert row[value_key] == ('insufficient' if field == 'documents' else 'unresolved')
    assert row['independently_verified'] is False
    assert row['citations'] == []
    assert row['summary'] == 'This interpretation item was rejected: ' + reason + '.'
    assert row['summary'] != original['summary']
    assert verified['item_rejections'] == [{'item_id': identity(field, original),
                                          'item': original, 'reason': reason}]


@pytest.mark.parametrize('field', ['conditions', 'documents', 'steps'])
@pytest.mark.parametrize('mutation', ['unknown_source', 'nonexact_quote', 'missing_required'])
def test_invalid_known_item_citations_reject_only_the_whole_item(materials, field, mutation):
    policy, sources, proposal, verifier = materials
    row = proposal[field][0]
    row['summary'] = 'Untrusted factual conclusion must not enter accepted state.'
    if mutation == 'unknown_source':
        row['citations'][0]['artifact_id'] = 'different-claim-source'
    elif mutation == 'nonexact_quote':
        row['citations'][0]['quote'] = 'Words absent from this source.'
    else:
        row['citations'] = []
    original = deepcopy(row)
    untouched = deepcopy((sources, proposal, verifier))
    verified = validate_interpretation(policy, sources, proposal, verifier)
    reason = ('established interpretation requires a source citation' if mutation == 'missing_required'
              else 'interpretation citation is not an exact claim source span')
    assert_rejected(verified, field, original, reason)
    assert (sources, proposal, verifier) == untouched
    for other_field in ('conditions', 'documents', 'steps'):
        if other_field != field:
            assert all(row['independently_verified'] for row in verified[other_field])
            assert all(row['citations'] for row in verified[other_field])
    assert verified['category']['citations']


@pytest.mark.parametrize('quote', [
    'die Verwaltung sagte telefonisch, eines sei eine Korrektur;',
    'Die Verwaltung sagte telefonisch, eines sei eine Korrektur:',
    'Gru\u0308n blieb die Tu\u0308r.',
    'First line Second line',
])
def test_unresolved_step_still_rejects_nonexact_quote_without_normalizing(materials, quote):
    policy, sources, proposal, _ = materials
    proposal['steps'] = [{'node_id': 'lt_type', 'status': 'unresolved',
                          'summary': 'The telephone account established the type.',
                          'citations': [{'artifact_id': 'message', 'quote': quote}]}]
    original = deepcopy(proposal['steps'][0])
    verifier = accept_all(proposal)
    untouched = deepcopy((sources, proposal, verifier))
    verified = validate_interpretation(policy, sources, proposal, verifier)
    assert_rejected(verified, 'steps', original, 'interpretation citation is not an exact claim source span')
    assert (sources, proposal, verifier) == untouched


@pytest.mark.parametrize('bad_first', [False, True])
def test_one_invalid_span_discards_all_citations_for_the_item(materials, bad_first):
    policy, sources, proposal, verifier = materials
    row = proposal['conditions'][0]
    bad = {'artifact_id': 'message', 'quote': 'This quotation is absent.'}
    row['citations'].insert(0 if bad_first else len(row['citations']), bad)
    original = deepcopy(row)
    verified = validate_interpretation(policy, sources, proposal, verifier)
    assert_rejected(verified, 'conditions', original, 'interpretation citation is not an exact claim source span')
    graph, facts, _ = compile_process(policy, 'isolated-rejection', verified)
    condition = graph['conditions'][row['flag']]
    fact = next(value for value in facts if value['fact_id'] == 'condition:' + row['flag'])
    assert condition['verdict'] == fact['status'] == 'unresolved'
    assert condition['citations'] == fact['citations'] == []
    assert fact['summary'] != original['summary']
    assert all(not node['completed'] for node in graph['nodes'])


@pytest.mark.parametrize('mutation', ['wrong_source', 'unknown_document_source'])
def test_document_source_binding_rejects_entire_assessment(materials, mutation):
    policy, sources, proposal, _ = materials
    row = proposal['documents'][0]
    if mutation == 'wrong_source':
        row['citations'] = deepcopy(proposal['category']['citations'])
    else:
        row['artifact_id'] = 'missing-document-source'
    original = deepcopy(row)
    verifier = accept_all(proposal)
    verified = validate_interpretation(policy, sources, proposal, verifier)
    assert_rejected(verified, 'documents', original, 'document assessment source differs from its citations')


@pytest.mark.parametrize('field,key', [('conditions', 'flag'), ('documents', 'document_type'), ('steps', 'node_id')])
def test_unknown_policy_item_is_fatal_even_after_an_invalid_citation(materials, field, key):
    policy, sources, proposal, _ = materials
    proposal['conditions'][0]['citations'][0]['quote'] = 'Absent quotation.'
    row = deepcopy(proposal[field][0])
    row[key] = 'unadmitted-policy-item'
    row['citations'][0]['quote'] = 'Also absent.'
    proposal[field].append(row)
    with pytest.raises(ValueError, match='unknown policy item'):
        validate_interpretation(policy, sources, proposal, accept_all(proposal))


@pytest.mark.parametrize('mutation', ['unknown_source', 'nonexact_quote', 'missing_required', 'family', 'verifier_rejected'])
def test_invalid_category_remains_fatal(materials, mutation):
    policy, sources, proposal, verifier = materials
    category = proposal['category']
    if mutation == 'unknown_source':
        category['citations'][0]['artifact_id'] = 'different-claim-source'
    elif mutation == 'nonexact_quote':
        category['citations'][0]['quote'] = 'Nonexact category quotation.'
    elif mutation == 'missing_required':
        category['citations'] = []
    elif mutation == 'family':
        category['family'] = 'unsupported'
    else:
        verifier['checks'][0]['accepted'] = False
    with pytest.raises(ValueError):
        validate_interpretation(policy, sources, proposal, verifier)


@pytest.mark.parametrize('mutation', ['duplicate_item', 'missing_check', 'duplicate_check', 'unknown_check'])
def test_structural_roster_errors_remain_fatal(materials, mutation):
    policy, sources, proposal, verifier = materials
    if mutation == 'duplicate_item':
        proposal['steps'].append(deepcopy(proposal['steps'][0]))
    elif mutation == 'missing_check':
        verifier['checks'].pop()
    elif mutation == 'duplicate_check':
        verifier['checks'][-1] = deepcopy(verifier['checks'][0])
    else:
        verifier['checks'][-1]['item_id'] = 'step:unadmitted-policy-item'
    with pytest.raises(ValueError, match='duplicate|coverage'):
        validate_interpretation(policy, sources, proposal, verifier)


@pytest.mark.parametrize('candidate_uses_rejected_source', [False, True])
def test_rejected_document_cannot_support_recipe_but_other_source_can(materials, candidate_uses_rejected_source):
    policy, sources, proposal, _ = materials
    bad_source = deepcopy(sources[1])
    bad_source['artifact_id'] = 'other-spouse-notice'
    sources.append(bad_source)
    rejected = deepcopy(proposal['documents'][0])
    rejected['artifact_id'] = bad_source['artifact_id']
    rejected['citations'] = [{'artifact_id': bad_source['artifact_id'], 'quote': 'An absent supporting span.'}]
    proposal['documents'].append(rejected)
    template = next(row for row in policy['templates'] if row['domain'] == proposal['category']['family'])
    kind = 'spouse_notice_copy'
    candidate = {'document_type': kind, 'required_fields': list(REQUIRED_FIELDS[kind]),
                 'summary': 'Isolated recipe fixture.', 'rule_refs': [template['template_id']],
                 'citations': deepcopy(proposal['documents'][0]['citations'])}
    if candidate_uses_rejected_source:
        candidate['citations'].append({'artifact_id': bad_source['artifact_id'], 'quote': bad_source['text']})
    proposal['knowledge_candidates'] = [candidate]
    original = deepcopy(proposal)
    verified = validate_interpretation(policy, sources, proposal, accept_all(proposal))
    assert proposal == original
    assert verified['documents'][0]['assessment'] == 'sufficient'
    assert verified['documents'][1]['assessment'] == 'insufficient'
    assert verified['documents'][1]['citations'] == []
    assert verified['item_rejections'][0]['item'] == rejected
    if candidate_uses_rejected_source:
        assert verified['knowledge_candidates'] == []
        assert verified['knowledge_rejections'] == [{'candidate': candidate,
            'reason': 'Knowledge candidate cites a document item rejected during citation admission.'}]
    else:
        assert verified['knowledge_candidates'][0]['document_type'] == kind
        assert verified['knowledge_candidates'][0]['independently_verified'] is True
        assert verified['knowledge_rejections'] == []


def test_valid_items_keep_exact_source_spans_and_no_rejections(materials):
    policy, sources, proposal, verifier = materials
    original = deepcopy((sources, proposal, verifier))
    verified = validate_interpretation(policy, sources, proposal, verifier)
    assert verified['item_rejections'] == []
    assert (sources, proposal, verifier) == original
    for row in proposal_items(verified).values():
        for citation in row['citations']:
            source = next(source for source in sources if source['artifact_id'] == citation['artifact_id'])
            assert source['text'][citation['start_char']:citation['end_char']] == citation['quote']
            assert citation['sha256'] == source['sha256']
            assert citation['text_sha256'] == source['text_sha256']
    compiled, compilation = compile_verification_proposal({'sources': sources}, proposal)
    assert compiled == proposal and compilation is None


@pytest.mark.parametrize('explicit_rejected_candidate', [False, True])
def test_mixed_document_recipes_keep_valid_candidate_and_compiler_support(materials, explicit_rejected_candidate):
    policy, sources, proposal, _ = materials
    rejected = proposal['documents'][0]
    rejected['citations'][0]['quote'] = 'A quote absent from the spouse notice.'
    valid = {'document_type': 'termination_notice', 'artifact_id': sources[1]['artifact_id'],
             'assessment': 'sufficient', 'summary': 'Isolated accepted document fixture.',
             'citations': [{'artifact_id': sources[1]['artifact_id'], 'quote': sources[1]['text']}]}
    proposal['documents'].append(valid)
    template = next(row for row in policy['templates'] if row['domain'] == proposal['category']['family'])
    if explicit_rejected_candidate:
        proposal['knowledge_candidates'] = [{
            'document_type': 'spouse_notice_copy', 'required_fields': list(REQUIRED_FIELDS['spouse_notice_copy']),
            'summary': 'The recipe must not inherit rejected document support.',
            'citations': deepcopy(valid['citations']), 'rule_refs': [template['template_id']]}]
    original = deepcopy(proposal)
    context = {'sources': sources, 'knowledge_recipe_compiler': KNOWLEDGE_RECIPE_COMPILER,
               'rule_packs': [{'family': template['domain'], 'template_id': template['template_id'],
                               'process_catalog': template['process_catalog']}]}
    compiled, compilation = compile_verification_proposal(context, proposal)
    assert proposal == original
    assert [row['source_item_id'] for row in compilation['derived_items']] == [identity('documents', valid)]
    verified = validate_interpretation(policy, sources, compiled, accept_all(compiled))
    assert [row['document_type'] for row in verified['knowledge_candidates']] == ['termination_notice']
    assert verified['documents'][0]['assessment'] == 'insufficient'
    assert verified['documents'][0]['citations'] == []
    assert verified['documents'][1]['assessment'] == 'sufficient'
    assert verified['item_rejections'][0]['item'] == original['documents'][0]
    if explicit_rejected_candidate:
        assert verified['knowledge_rejections'] == [{'candidate': original['knowledge_candidates'][0],
            'reason': 'Knowledge candidate cites a document item rejected during citation admission.'}]
    else:
        assert verified['knowledge_rejections'] == []


def test_original_five_observable_quote_is_case_exact_in_deterministic_fixture():
    # These are immutable public intake bytes, read only as an isolated fixture.
    # No production/model receipt or evidence-admission event is reproduced.
    public = PublicCorpus(default_workspace_corpus_root())
    canonical = CanonicalCorpus(public)
    claim_id = 'clm_0c5e7c7723a3c694'
    artifact_id = 'src_f01ecd78c8d140ba8feb51a4e9c0bf3e'
    source = canonical.source_preview(claim_id, artifact_id)
    raw, _ = canonical.artifact(claim_id, artifact_id)
    exact = 'Die Verwaltung sagte telefonisch, eines sei eine Korrektur;'
    nonexact = 'die Verwaltung sagte telefonisch, eines sei eine Korrektur;'
    assert source['preview_only'] is True and source['evidence_admitted'] is False
    assert source['sha256'] == sha256(raw).hexdigest()
    assert exact in source['text'] and nonexact not in source['text']
    fixture = SemanticFixture()
    context = {'sources': [source]}
    proposal = fixture.interpret(context, {'fixture': True})['result']
    for row in proposal_items(proposal).values():
        row['citations'] = [{'artifact_id': artifact_id, 'quote': exact}]
    invalid_step = {'node_id': 'lt_type', 'status': 'unresolved', 'summary': 'Unaccepted type conclusion.',
                    'citations': [{'artifact_id': artifact_id, 'quote': nonexact}]}
    proposal['steps'].append(invalid_step)
    verifier = fixture.verify(context, proposal, {'fixture': True})['result']
    untouched = deepcopy((source, proposal, verifier))
    verified = validate_interpretation(public.static_policy(), [source], proposal, verifier)
    assert (source, proposal, verifier) == untouched
    assert verified['item_rejections'] == [{'item_id': 'step:lt_type', 'item': invalid_step,
                                          'reason': 'interpretation citation is not an exact claim source span'}]
    assert verified['steps'][1]['status'] == 'unresolved'
    assert verified['steps'][1]['independently_verified'] is False
    assert verified['steps'][1]['citations'] == []
    assert verified['steps'][1]['summary'] != invalid_step['summary']
    assert verified['category']['citations'][0]['quote'] == exact
    assert verified['steps'][0]['citations'][0]['quote'] == exact
    assert all(row['citations'][0]['quote'] == exact for row in verified['conditions'])
    assert canonical.artifact(claim_id, artifact_id)[0] == raw
