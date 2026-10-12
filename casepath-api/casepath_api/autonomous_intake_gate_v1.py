"""Pure source-backed eligibility and checklist; no acquisition or journal writes."""
from copy import deepcopy

from .autonomous_policy_v1 import compile_process
from .autonomous_reference_v1 import ReferenceProfile, reference_findings
from .autonomous_reference_policy_v1 import SCOPES, bounded_reference_policy
from .causal_process_v1 import evaluate, seal_graph, _document_definition_sha256
from .workspace_corpus import digest_value

GATE_CONTRACT = 'casepath.source-backed-intake/1.0.0'


def inspect_sources(store, state):
    # This is extraction for inspection. It does not admit acquired evidence.
    result = []
    for descriptor in state['source_descriptors']:
        raw = store._validate_descriptor(descriptor, state['claim_id'])
        result.append({**descriptor, **store._extract(raw, descriptor['media_type'])})
    return result


def assess_intake(state, sources, base_policy, *, reference_policy=None, profile=None):
    policy = reference_policy or bounded_reference_policy(base_policy)
    profile = profile or ReferenceProfile()
    provenance = profile.match(state, sources)
    proposal = predicates = None
    if provenance:
        proposal, predicates = reference_findings(policy, sources)
    else:
        # A source account can identify an investigation family, never readiness.
        text = '\n'.join(s.get('text', '') for s in sources).casefold()
        family = ('defect_mold_heating' if any(x in text for x in ['heating', 'heizung', 'schimmel']) else
                  'rent_increase_dispute' if any(x in text for x in ['mietzinserhöhung', 'erhöhungsformular', 'rent increase']) else
                  'lease_termination_dispute' if any(x in text for x in ['termination', 'kündigung']) else None)
        if family:
            proposal = {'category': {'family': family, 'summary': 'Source inspection identifies an investigation scope only.',
                                    'citations': []}, 'conditions': [], 'documents': [], 'steps': [],
                        'rule_pack_sha256': digest_value(next(t for t in base_policy['templates'] if t['domain'] == family))}
            policy = base_policy
    checklist, active = [], []
    if proposal:
        graph, _, _ = compile_process(policy, state['claim_id'], proposal)
        assessments = {d['document_type']: d for d in proposal['documents']}
        by_id = {s['artifact_id']: s for s in sources}
        for definition in graph['document_catalog']:
            doc = assessments.get(definition['document_type'])
            if doc:
                source = by_id[doc['artifact_id']]
                definition['held_files'] = [{'artifact_id': source['artifact_id'], 'file_name': source['file_name'],
                    'media_type': source['media_type'], 'sha256': source['sha256'], 'source_quote': doc['citations'][0]['quote'],
                    'review': doc['assessment'], 'reviewed_by': 'reference_source_inspection', 'note': doc['summary'],
                    'document_definition_sha256': _document_definition_sha256(definition)}]
        view = evaluate(seal_graph(graph))
        active = [n['node_id'] for n in view['nodes'] if n['activation'] == 'true']
        for doc in view['documents']:
            if doc['activation'] == 'true' and doc['requirement_class'] != 'optional':
                checklist.append({'document_type': doc['document_type'], 'label': doc['label'],
                                  'node_ids': doc['required_at_node_ids'],
                                  'status': 'sufficient' if doc['review_state'] == 'sufficient' else 'missing' if not doc['held_files'] else 'insufficient',
                                  'artifact_ids': [f['artifact_id'] for f in doc['held_files']]})
    predicates = predicates or [{'predicate_id': 'source_backed_assessment_scope', 'status': 'unknown', 'citations': [], 'rule_refs': []}]
    missing = [row for row in checklist if row['status'] != 'sufficient']
    eligible = provenance is not None and not missing and all(p['status'] != 'unknown' for p in predicates)
    if provenance:
        provenance['rule_set_sha256'] = digest_value(policy)
    value = {'contract': GATE_CONTRACT, 'status': 'complete' if eligible else 'incomplete' if proposal else 'unsupported',
             'eligible': eligible, 'assessment_scope': SCOPES[proposal['category']['family']]['id'] if provenance else None,
             'active_node_ids': active, 'checklist': checklist, 'missing_documents': missing,
             'legal_predicates': predicates, 'provenance': provenance}
    return {**value, 'gate_sha256': digest_value(value)}


def require_complete(gate):
    if not gate['eligible']:
        from .autonomous_store_v1 import AutonomousStoreError
        raise AutonomousStoreError('intake incomplete: source-backed bounded assessment requirements are not established')
