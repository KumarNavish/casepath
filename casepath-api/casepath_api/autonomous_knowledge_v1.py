"""Immutable procedural knowledge qualified against the admitted rule pack."""
from copy import deepcopy
from itertools import product

from .autonomous_policy_v1 import POLICY_ID, REQUIRED_FIELDS, compile_process
from .causal_process_v1 import evaluate, seal_graph
from .workspace_corpus import digest_value


DEFINITION_KEYS = ('family', 'rule_pack_sha256', 'graph', 'facts', 'obligations', 'policy_id', 'evidence_recipes')


def _procedure_id(family):
    return 'procedure.' + family


def _definition(version):
    try:
        definition = {key: version[key] for key in DEFINITION_KEYS}
        if (version['qualification']['status'] != 'qualified'
                or digest_value(definition) != version['qualification']['definition_sha256']
                or version['knowledge_id'] != _procedure_id(version['family'])
                or type(version['version']) is not int or version['version'] < 1):
            raise ValueError('knowledge definition identity differs')
        if 'knowledge_sha256' in version and version['knowledge_sha256'] != digest_value({
                key: value for key, value in version.items() if key != 'knowledge_sha256'}):
            raise ValueError('knowledge publication seal differs')
        parents = [version.get('parent_definition_sha256'), version.get('parent_knowledge_sha256')]
        if version['version'] == 1:
            if parents != [None, None]:
                raise ValueError('initial knowledge version cannot have a parent')
        elif any(not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value)
                 for value in parents):
            raise ValueError('knowledge version requires exact parent identities')
        return definition
    except (KeyError, TypeError) as error:
        raise ValueError('knowledge definition is incomplete') from error


def _recipe(document, template):
    document_type = document['document_type']
    if document_type not in REQUIRED_FIELDS:
        raise ValueError('knowledge recipe has no admitted evidence criteria')
    return {'document_type': document_type, 'required_fields': list(REQUIRED_FIELDS[document_type]),
            'summary': document['assertion'], 'rule_refs': [template['template_id']]}


def _validate_recipes(recipes, template):
    documents = {row['document_type']: row for row in template['process_catalog']['documents']}
    if not isinstance(recipes, list) or len(recipes) > len(documents):
        raise ValueError('knowledge recipe roster is invalid')
    seen = set()
    for recipe in recipes:
        if not isinstance(recipe, dict) or recipe.get('document_type') not in documents:
            raise ValueError('knowledge recipe refers to an unsupported document')
        document_type = recipe['document_type']
        if document_type in seen or recipe != _recipe(documents[document_type], template):
            raise ValueError('knowledge recipe differs from the admitted evidence criteria')
        seen.add(document_type)


def _observed_recipes(state, template, candidates):
    if not isinstance(candidates, list) or len(candidates) > 30:
        raise ValueError('knowledge candidate roster is invalid')
    if not candidates:
        return [], []
    interpretation = next((row['receipt'] for row in reversed(state.get('receipts', []))
                           if row['kind'] == 'interpretation.accepted'), None)
    if (not interpretation or interpretation.get('rule_pack_sha256') != digest_value(template)
            or interpretation.get('receipt_sha256') != digest_value({
                key: value for key, value in interpretation.items() if key != 'receipt_sha256'})):
        raise ValueError('knowledge candidates lack a current sealed interpretation receipt')
    checks = {row['item_id']: row['accepted'] for row in interpretation.get('checks', [])}
    documents = {row['document_type']: row for row in template['process_catalog']['documents']}
    held = {row['document_type']: {item['artifact_id']: item for item in row['held_files']
                                if item['review'] == 'sufficient'} for row in state['graph']['document_catalog']}
    sources = {source['artifact_id']: source for source in state['acquired_sources']}
    recipes, evidence, seen = [], [], set()
    for candidate in candidates:
        if not isinstance(candidate, dict) or candidate.get('document_type') not in documents:
            raise ValueError('knowledge candidate refers to an unsupported document')
        document_type = candidate['document_type']
        if document_type in seen:
            raise ValueError('duplicate knowledge candidate')
        seen.add(document_type)
        canonical = _recipe(documents[document_type], template)
        fields = candidate.get('required_fields')
        if (not isinstance(fields, list) or any(not isinstance(field, str) for field in fields)
                or len(fields) != len(canonical['required_fields']) or set(fields) != set(canonical['required_fields'])):
            raise ValueError('knowledge candidate weakens or changes required evidence fields')
        if (candidate.get('rule_refs') != canonical['rule_refs']
                or checks.get(f'knowledge:{document_type}') is not True):
            raise ValueError('knowledge candidate lacks admitted authority or independent verification')
        citations = candidate.get('citations')
        if not isinstance(citations, list) or not 1 <= len(citations) <= 6:
            raise ValueError('knowledge candidate requires supporting source citations')
        for citation in citations:
            source = sources.get(citation.get('artifact_id')) if isinstance(citation, dict) else None
            quote = citation.get('quote') if isinstance(citation, dict) else None
            if (source is None or source['role'] != 'supporting_document' or source.get('complete') is not True
                    or source['artifact_id'] not in held.get(document_type, {})
                    or checks.get(f"document:{document_type}:{source['artifact_id']}") is not True
                    or not isinstance(quote, str) or not quote or quote not in source['text']
                    or citation.get('sha256', source['sha256']) != source['sha256']
                    or citation.get('text_sha256', source['text_sha256']) != source['text_sha256']):
                raise ValueError('knowledge candidate is not bound to a verified sufficient supporting file')
            if 'start_char' in citation or 'end_char' in citation:
                start, end = citation.get('start_char'), citation.get('end_char')
                if (type(start) is not int or type(end) is not int or start < 0 or end <= start
                        or source['text'][start:end] != quote):
                    raise ValueError('knowledge candidate citation span differs')
        if candidate not in interpretation.get('knowledge_candidates', []):
            raise ValueError('knowledge candidate differs from the accepted interpretation')
        # The proposed narrative remains provenance. Only canonical procedure
        # text enters the reusable definition, so names and case values cannot.
        recipes.append(canonical)
        evidence.append({'document_type': document_type, 'proposed_summary': candidate.get('summary', ''),
                         'citations': deepcopy(citations), 'interpretation_receipt_sha256': interpretation['receipt_sha256']})
    return recipes, evidence


def blank_interpretation(family):
    return {'category': {'family': family, 'summary': 'Reusable source-grounded evidence routing.', 'citations': []},
            'conditions': [], 'documents': [], 'steps': []}


def _routing(graph, conditions):
    view = evaluate(graph, conditions)
    return {'nodes': [(r['node_id'], r['activation'], r['execution_state']) for r in view['nodes']],
            'documents': [(r['document_type'], r['activation'], r['route_state'], r['required_at_node_ids']) for r in view['documents']]}


def qualify(policy, state, *, candidates=None, previous=None):
    """Promote a process definition, never the claim's truth values or files."""
    current = state['graph']
    template = next(row for row in policy['templates'] if row['domain'] == current['family'])
    if current['assessment_context']['rule_pack_sha256'] != digest_value(template):
        raise ValueError('knowledge candidate uses a different rule version')
    if not state.get('outcome'):
        raise ValueError('knowledge qualification requires a recorded claim outcome')
    observed, source_evidence = _observed_recipes(state, template, candidates if candidates is not None else [])
    prior_definition = _definition(previous) if previous is not None else None
    if previous is not None and previous['family'] != current['family']:
        raise ValueError('knowledge parent belongs to another procedure')
    same_rules = previous is not None and previous['rule_pack_sha256'] == digest_value(template) and previous['policy_id'] == POLICY_ID
    if same_rules:
        graph, facts, obligations = (deepcopy(previous[key]) for key in ('graph', 'facts', 'obligations'))
    else:
        graph, facts, obligations = compile_process(policy, 'reusable-procedure', blank_interpretation(current['family']))
    prior_recipes = deepcopy(previous['evidence_recipes']) if same_rules else []
    _validate_recipes(prior_recipes, template)
    recipes = {row['document_type']: row for row in prior_recipes}
    additions = sorted(row['document_type'] for row in observed if row['document_type'] not in recipes)
    recipes.update({row['document_type']: row for row in observed})
    # The operational instance may hold facts, reviews and completions. Strip
    # those before comparing it with the authoritative procedural definition.
    candidate = deepcopy(current)
    candidate['claim_id'] = graph['claim_id']
    candidate['revision'] = 0
    candidate['history'] = []
    candidate['conditions'] = deepcopy(graph['conditions'])
    candidate['assessment_context'] = deepcopy(graph['assessment_context'])
    candidate.pop('fragment_instances', None)
    for node in candidate['nodes']:
        node['completed'] = False
    for doc in candidate['document_catalog']:
        doc['held_files'] = []
    candidate = seal_graph(candidate)
    if candidate['graph_sha256'] != graph['graph_sha256']:
        raise ValueError('knowledge candidate changes the admitted process definition')
    definition = {'family': graph['family'], 'rule_pack_sha256': digest_value(template),
                  'graph': graph, 'facts': facts, 'obligations': obligations, 'policy_id': POLICY_ID,
                  'evidence_recipes': [recipes[key] for key in sorted(recipes)]}
    identity = digest_value(definition)
    if prior_definition == definition:
        return None
    flags = sorted(graph['conditions'])
    cases = 0
    for values in product(('true', 'false', 'unresolved'), repeat=len(flags)):
        conditions = dict(zip(flags, values))
        if _routing(candidate, conditions) != _routing(graph, conditions):
            raise ValueError('knowledge candidate fails causal routing regression')
        cases += 1
    change_reason = (f'Initial qualification with {len(recipes)} observed evidence recipes.' if previous is None else
                     'Requalified the procedure against the current admitted rule version.' if not same_rules else
                     f"Added {len(additions)} verified evidence recipes: {', '.join(additions)}.")
    return {'knowledge_id': _procedure_id(graph['family']), 'version': previous['version'] + 1 if previous else 1,
            'parent_definition_sha256': previous['qualification']['definition_sha256'] if previous else None,
            'parent_knowledge_sha256': previous.get('knowledge_sha256', digest_value(previous)) if previous else None,
            'change_reason': change_reason, 'added_document_types': additions,
            'title': template['title'], 'category': graph['family'], **definition,
            'source_claim_id': state['claim_id'], 'source_state_sha256': state['state_sha256'],
            'source_evidence': source_evidence,
            'qualification': {'status': 'qualified', 'regression_cases': cases,
                              'checks': ['admitted_rule_identity', 'no_case_values_or_files', 'all_ternary_branch_assignments',
                                         'graph_and_checklist_equivalence', 'source_bound_proposer_and_verifier',
                                         'exact_required_evidence_fields', 'verified_sufficient_source_binding'],
                              'evidence_recipe_count': len(recipes), 'recipe_coverage_document_types': sorted(recipes),
                              'definition_sha256': identity},
            'source_outcome': state.get('outcome'), 'created_at': state.get('updated_at')}


class AutonomousKnowledge:
    def __init__(self, store, policy):
        self.store, self.policy = store, policy

    def view(self):
        versions, uses, quarantined, conflicts = {}, [], [], set()
        for state in self.store.list():
            # Store.list may return queue summaries; authoritative retrieval is
            # necessary for knowledge, including its immutable provenance.
            state = self.store.get(state['claim_id'])
            for value in state.get('knowledge_published', []):
                if value.get('qualification', {}).get('status') == 'qualified':
                    try:
                        definition = _definition(value)
                        identity = (value['knowledge_id'], value['version'])
                        prior = versions.get(identity)
                        if prior is not None and (_definition(prior) != definition
                                or prior.get('parent_definition_sha256') != value.get('parent_definition_sha256')
                                or prior.get('parent_knowledge_sha256') != value.get('parent_knowledge_sha256')):
                            conflicts.add(identity)
                            raise ValueError('knowledge version has conflicting immutable definitions')
                        versions.setdefault(identity, value)
                    except ValueError as error:
                        quarantined.append({'knowledge_id': value.get('knowledge_id'), 'version': value.get('version'),
                                            'qualification': {'status': 'quarantined', 'reason': str(error)},
                                            'source_claim_id': state['claim_id']})
                else:
                    quarantined.append(value)
            uses.extend({**value, 'claim_id': state['claim_id']} for value in state.get('knowledge_uses', []))
        admitted = {}
        for key, value in sorted(versions.items()):
            if key in conflicts:
                continue
            if value['version'] > 1:
                parent = admitted.get((value['knowledge_id'], value['version'] - 1))
                if (parent is None or value['parent_definition_sha256'] != parent['qualification']['definition_sha256']
                        or value['parent_knowledge_sha256'] != parent.get('knowledge_sha256', digest_value(parent))):
                    quarantined.append({'knowledge_id': value['knowledge_id'], 'version': value['version'],
                                        'qualification': {'status': 'quarantined', 'reason': 'knowledge parent lineage differs'},
                                        'source_claim_id': value.get('source_claim_id')})
                    continue
            admitted[key] = value
        return {'versions': list(admitted.values()),
                'uses': uses, 'quarantined': quarantined}

    def latest(self, family):
        return max((row for row in self.view()['versions'] if row['family'] == family),
                   key=lambda row: row['version'], default=None)

    def compatible(self, family):
        template = next(row for row in self.policy['templates'] if row['domain'] == family)
        return max((row for row in self.view()['versions'] if row['family'] == family
                    and row['rule_pack_sha256'] == digest_value(template) and row['policy_id'] == POLICY_ID),
                   key=lambda row: row['version'], default=None)

    def instantiate(self, version, claim_id, verified):
        """Reuse compiled structure while reassessing every case fact."""
        family = verified['category']['family']
        template = next(row for row in self.policy['templates'] if row['domain'] == family)
        if version['family'] != family or version['rule_pack_sha256'] != digest_value(template) or version['policy_id'] != POLICY_ID:
            raise ValueError('knowledge applicability differs from this claim')
        _definition(version)
        _validate_recipes(version['evidence_recipes'], template)
        graph, facts, obligations = deepcopy(version['graph']), deepcopy(version['facts']), deepcopy(version['obligations'])
        graph['claim_id'] = claim_id
        for row in verified['conditions']:
            graph['conditions'][row['flag']] = {**deepcopy(row), 'worker': 'autonomous_verification'}
        for fact in facts:
            if fact['fact_id'].startswith('condition:'):
                condition = graph['conditions'][fact['fact_id'].split(':', 1)[1]]
                fact.update(status=condition['verdict'], summary=condition['summary'], citations=condition['citations'])
        graph['assessment_context'].update(facts=facts, obligations=obligations, summary=verified['category']['summary'])
        return seal_graph(graph), facts, obligations
