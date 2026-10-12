"""Explicit, versioned local assessment scope, compiled by the existing engine.

This policy never amends the original corpus policy. It records bounded tenant
eligibility/form assessments, not repairs, filing deadlines or court outcomes.
"""
from copy import deepcopy
import json
from pathlib import Path

from .workspace_corpus import digest_value

REFERENCE_POLICY_ID = 'casepath.bounded-reference-assessment/1.0.0'
PROFILE_ROOT = Path(__file__).parent / 'reference_profiles' / 'synthetic-nine-v1'
REFERENCE_FIELDS = {
    'tenancy_terms_evidence': ['contracting_parties', 'property', 'tenancy_terms'],
    'original_notification_context': ['issuer_authority', 'packet_completeness', 'contemporaneous_contents'],
    'objective_defect_observation': ['location', 'observation_date', 'observed_fault', 'causal_limits'],
    'landlord_knowledge_evidence': ['recipient', 'reported_defect', 'first_knowledge_date', 'repair_status'],
    'received_termination_packet': ['issuer', 'addressee', 'received_contents'],
    'received_rent_increase_packet': ['notified_amount', 'effective_date', 'addressee', 'form_contents'],
}
REFERENCE_FACTS = {
    'tenancy_terms_evidence': 'Relevant residential tenancy terms, parties and dwelling; this is not a complete lease contract',
    'original_notification_context': 'Issuer authority and complete contemporaneous notification packet',
    'objective_defect_observation': 'Dated objective defect observations and limits of causal attribution',
    'landlord_knowledge_evidence': 'Landlord knowledge of the reported defect and continuing repair status',
    'received_termination_packet': 'The actual received termination letter contents, without asserting lawful approved form',
    'received_rent_increase_packet': 'The actual received increase notification contents, without asserting lawful reasons',
}

# Scope definitions are procedural rules, not claim-specific expected answers.
SCOPES = {
    'defect_mold_heating': {
        'id': 'defect_removal_and_reduction_eligibility',
        'request': 'removal of the continuing heating defect and assessment of proportional rent-reduction eligibility',
        'nodes': [('dh_intake', 'Capture the reported defect'), ('dh_scope', 'Establish relevant tenancy terms'),
                  ('dh_notice', 'Establish landlord knowledge'), ('dh_cause', 'Assess supported cause'),
                  ('dh_evidence', 'Assess objective defect evidence'), ('dh_response', 'Record repair and rent reduction eligibility')],
        'documents': [('tenancy_terms_evidence', 'Relevant tenancy terms', 'dh_scope'),
                      ('landlord_knowledge_evidence', 'Landlord knowledge and continuing repair status', 'dh_notice'),
                      ('objective_defect_observation', 'Dated technical defect observation', 'dh_evidence')],
        'articles': ['259', '259a', '259d'],
    },
    'lease_termination_dispute': {
        'id': 'termination_form_nullity_assessment',
        'request': "assessment of the received landlord notice's approved-form/nullity defect",
        'nodes': [('lt_intake', 'Capture the received termination packet'), ('lt_form', 'Assess whether the termination notice is valid')],
        'documents': [('tenancy_terms_evidence', 'Relevant tenancy terms', 'lt_form'),
                      ('received_termination_packet', 'Received termination notice', 'lt_form'),
                      ('original_notification_context', 'Who sent the notice and how it arrived', 'lt_form')],
        'articles': ['266l', '266o'],
    },
    'rent_increase_dispute': {
        'id': 'rent_increase_reasons_nullity_assessment',
        'request': "assessment of the original notice's missing-reasons/nullity ground",
        'nodes': [('ri_intake', 'Capture the original increase packet'), ('ri_form', 'Assess notification context'),
                  ('ri_reason', 'Assess whether the increase notice is valid')],
        'documents': [('tenancy_terms_evidence', 'Relevant ordinary tenancy terms', 'ri_form'),
                      ('received_rent_increase_packet', 'Received rent increase notice', 'ri_form'),
                      ('original_notification_context', 'Reasons supplied with the increase notice', 'ri_reason')],
        'articles': ['269d'],
    },
}


def bounded_reference_policy(base):
    law = json.loads((PROFILE_ROOT / 'normative_sources.json').read_text())
    result = {'policy_id': REFERENCE_POLICY_ID, 'base_rule_set_sha256': digest_value(base),
              'normative_sources': law, 'normative_sources_sha256': digest_value(law), 'templates': [],
              'required_facts_by_document': deepcopy(REFERENCE_FACTS), 'required_fields_by_document': deepcopy(REFERENCE_FIELDS)}
    for original in base['templates']:
        family = original['domain']
        scope = SCOPES[family]
        template = deepcopy(original)
        template.update(template_id=original['template_id'] + '.bounded-reference-v1',
                        title=original['title'] + ' — bounded synthetic reference assessment',
                        content='Record only the source-requested internal assessment. Relevant tenancy terms may be '
                                'established by a source attestation; do not assert receipt of a full lease. Technical '
                                'observations may establish a heating defect without photographs. A defective received '
                                'notice is assessable; absent lawful form/reasons is a failed legal predicate, not an '
                                'unreceived document. Exclude future repair, quantum, filing and court actions.',
                        scope_id=scope['id'], base_template_sha256=digest_value(original),
                        required_fields_by_document=deepcopy(REFERENCE_FIELDS),
                        legal_authority=[{'article': article, 'text': law['articles'][article],
                                          'source': law['current_snapshot']} for article in scope['articles']])
        nodes = [{'node_id': node, 'label': label, 'responsibility': 'claim_handler',
                  'terminal': index == len(scope['nodes']) - 1,
                  'assertion': f"The bounded {scope['id']} assessment includes '{label}', an internal assessment only."}
                 for index, (node, label) in enumerate(scope['nodes'])]
        documents = [{'document_type': kind, 'label': label, 'required_at_node_ids': [node],
                      'requirement_class': 'mandatory', 'condition': None,
                      'assertion': f"'{label}' is required to assess {node} within {scope['id']}."}
                     for kind, label, node in scope['documents']]
        transitions = [{'edge_id': f'reference_{family}_{i}', 'source_node_id': a['node_id'],
                        'target_node_id': b['node_id'], 'condition': 'assessment recorded', 'optional_path': False,
                        'assertion': 'The preceding source-backed internal assessment must be recorded first.'}
                       for i, (a, b) in enumerate(zip(nodes, nodes[1:]))]
        template['process_catalog'] = {'nodes': nodes, 'documents': documents, 'transitions': transitions}
        result['templates'].append(template)
    return result
