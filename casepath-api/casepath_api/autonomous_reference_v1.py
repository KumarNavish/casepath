"""Provider-free reference execution from pinned, visible synthetic source bytes.

No expected-answer, audit-checklist, research graph or provider result is read.
The two reference stages apply closed evidence rules, then independently
recompute and check every item before the existing validator admits it.
"""
import base64
from copy import deepcopy
from hashlib import sha256
import json
import re

from .autonomous_model_v1 import validate_result
from .autonomous_policy_v1 import (INTERPRET_SCHEMA, VERIFY_SCHEMA, REQUIRED_FIELDS,
                                  compile_verification_proposal, proposal_items)
from .autonomous_reference_policy_v1 import PROFILE_ROOT, REFERENCE_POLICY_ID, SCOPES
from .workspace_corpus import digest_value

REFERENCE_CONTRACT = 'casepath.deterministic-reference/1.0.0'


class ReferenceProfile:
    def __init__(self, root=PROFILE_ROOT):
        self.root = root
        self.raw = (root / 'profile.json').read_bytes()
        self.value = json.loads(self.raw)
        self.sha256 = sha256(self.raw).hexdigest()
        if self.value['contract'] != 'casepath.synthetic-reference-sources/1.0.0':
            raise ValueError('unknown reference source profile')

    @property
    def ids(self):
        return tuple(sorted(self.value['claims']))

    def files(self, claim_id):
        result = []
        for source in self.value['claims'][claim_id]['sources']:
            raw = (self.root / claim_id / source['file_name']).read_bytes()
            if sha256(raw).hexdigest() != source['sha256'] or len(raw) != source['size_bytes']:
                raise ValueError('synthetic reference source bytes changed')
            result.append({'file_name': source['file_name'], 'media_type': source['media_type'],
                           'content_base64': base64.b64encode(raw).decode()})
        return result

    def match(self, state, sources):
        entry = self.value['claims'].get(state['claim_id'])
        binding = state.get('original_binding', {})
        if (entry is None or binding.get('corpus_manifest_sha256') != entry['corpus_manifest_sha256']
                or binding.get('claim_binding_sha256') != entry['original_binding_sha256']):
            return None
        by_hash = {row['sha256']: row for row in sources}
        expected = {s['sha256'] for s in entry['sources']}
        originals = {row['sha256'] for row in binding['source_map']}
        # Extra material changes the interpretation; do not ignore adverse input.
        if set(by_hash) != expected | originals or len(sources) != len(expected | originals):
            return None
        for source in entry['sources']:
            actual = by_hash[source['sha256']]
            text = actual.get('text', '')
            if (actual.get('complete') is not True or actual.get('role') != 'supporting_document'
                    or sha256((self.root / state['claim_id'] / source['file_name']).read_bytes()).hexdigest() != source['sha256']
                    or not text.startswith('SYNTHETIC SUPPLEMENT — FICTIONAL DEMONSTRATION SOURCE\n')
                    or f"Original claim ID: {state['claim_id']}\n" not in text
                    or f"Fictional review as-of: {entry['as_of']}\n" not in text):
                return None
        return {'contract': REFERENCE_CONTRACT, 'mode': 'deterministic_reference', 'synthetic': True,
                'profile_id': self.value['profile_id'], 'profile_sha256': self.sha256, 'as_of': entry['as_of'],
                'source_roster_sha256': digest_value(state['source_descriptors'])}


def _find(sources, pattern, *, role='supporting_document'):
    for source in sources:
        if source['role'] != role or source.get('complete') is not True:
            continue
        match = re.search(pattern, source['text'], re.S)
        if match and 0 < len(match.group()) <= 800:
            return {'artifact_id': source['artifact_id'], 'quote': match.group()}
    return None


def reference_findings(policy, sources):
    """Closed source rules. A matched filename, type or boolean grants nothing."""
    request = family = None
    for candidate, scope in SCOPES.items():
        request = _find(sources, re.escape(scope['request']))
        if request:
            family = candidate
            break
    if family is None:
        raise ValueError('source-requested bounded assessment is unknown')
    terms = _find(sources, r'I, [^\n]+?under an indefinite[^\n]+?(?:winter\.|family home\.|three months\x27 notice\.)')
    if terms is None:
        # Termination request source ends its tenancy terms before household facts.
        terms = _find(sources, r'I, [^\n]+?indefinite residential lease[^\n]+?not a family home\.')
    template = next(t for t in policy['templates'] if t['domain'] == family)
    docs, predicates = [], []

    def document(kind, citation, summary):
        if citation:
            docs.append({'document_type': kind, 'artifact_id': citation['artifact_id'], 'assessment': 'sufficient',
                         'summary': summary, 'citations': [citation]})

    def predicate(name, citation, articles, *, failed=False):
        predicates.append({'predicate_id': name, 'status': 'unknown' if not citation else 'failed' if failed else 'supported',
                           'citations': [citation] if citation else [],
                           'rule_refs': ['CO:' + a for a in articles]})

    document('tenancy_terms_evidence', terms, 'Source attestation establishes the relevant tenancy terms; no complete lease is claimed received.')
    predicate('residential_tenancy_scope', terms, SCOPES[family]['articles'])
    if family == 'defect_mold_heating':
        observation = _find(sources, r'On [^\n]+?no tenant alteration or misuse explains the failure\.')
        continuing = _find(sources, r'The defect persists[^\n]+?principal living rooms\.')
        knowledge = _find(sources, r'Our fictional call log records[^\n]+?first documented knowledge of the defect\.')
        responsibility = _find(sources, r'We confirm the tenant[^\n]+?as of this acknowledgment\.')
        document('objective_defect_observation', observation, 'The dated calibrated observation identifies the fixed-pump fault and its causal limits.')
        document('landlord_knowledge_evidence', knowledge, 'The landlord acknowledgment records first knowledge of the reported continuing defect.')
        predicate('objective_use_impairment', continuing, ['259a', '259d'])
        predicate('outside_small_tenant_maintenance_and_no_tenant_cause', observation, ['259', '259a'])
        predicate('landlord_first_knowledge', knowledge, ['259d'])
        predicate('continuing_defect_without_remedy', responsibility, ['259a', '259d'])
        summary = 'The fictional source packet supports defect removal and proportional reduction eligibility from documented landlord knowledge until remedy. Quantum, repair and any award remain undetermined.'
    elif family == 'lease_termination_dispute':
        archive = _find(sources, r'Fictional issuance archive[^\n]+?receipt at that time\.')
        no_form = _find(sources, r'It was a plain letter, not a canton-approved termination form\.')
        complete = _find(sources, r'No other attachment, approved form[^\n]+?as-of date\.')
        notice = _find(sources, r'(?:Termination of tenancy|Kündigung[^\n]*)[\s\S]{1,450}?(?:three months after receipt|drei Monate[^\n]*)')
        # The actual unsigned received letter is reviewed, never a nonexistent approved form.
        document('received_termination_packet', notice, 'The actual received letter is readable for form assessment; this does not authenticate an approved form or valid termination.')
        document('original_notification_context', archive, 'The issuance archive establishes issuer authority and the actual delivery context.')
        predicate('issuer_authority_and_received_packet', archive, ['266l'])
        predicate('complete_channel_archive', complete, ['266l', '266o'])
        predicate('canton_approved_form', no_form, ['266l', '266o'], failed=True)
        summary = 'The fictional complete received packet lacks a canton-approved termination form, supporting the bounded nullity assessment under CO 266l/266o. No challenge was filed and no court outcome or verified filing deadline is recorded.'
    else:
        notice = _find(sources, r'Begründung der Erhöhung:\nBegründung gemäss separatem Begleitschreiben1')
        archive = _find(sources, r'The fictional managing agent confirms[^\n]+?original notification\.')
        none = _find(sources, r'No contemporaneous accompanying reason letter[^\n]+?was issued or received\.')
        ordinary = _find(sources, r'The rent is not indexed or stepped, and there is no Article269c agreed increase\.')
        later = _find(sources, r'This reply was sent after[^\n]+?original communication\.')
        document('received_rent_increase_packet', notice, 'The received original form permits a bounded assessment of its uncompleted reasons field; lawful reasons are not claimed established.')
        document('original_notification_context', archive, 'The authorized issuer confirms the complete original notification and absence of contemporaneous reasons.')
        predicate('ordinary_non269c_tenancy', ordinary, ['269d'])
        predicate('issuer_authority_and_complete_packet', archive, ['269d'])
        predicate('contemporaneous_substantive_reasons', none, ['269d'], failed=True)
        predicate('later_email_is_not_original_reasons', later, ['269d'])
        summary = 'The fictional complete original increase packet omitted substantive reasons, supporting the bounded nullity assessment under CO 269d(2)(b). The later market reply is contextual evidence. A mechanical signature is permitted at this historical date; excessive rent, quantum and filing deadlines remain undetermined.'
    present = {d['document_type'] for d in docs}
    complete = all(p['status'] != 'unknown' for p in predicates) and present == {
        d['document_type'] for d in template['process_catalog']['documents']}
    cites = [p['citations'][0] for p in predicates if p['citations']][:6]
    proposal = {'category': {'family': family, 'summary': summary, 'citations': [request]}, 'conditions': [],
                'documents': docs, 'steps': [{'node_id': row['node_id'], 'status': 'established' if complete else 'unresolved',
                    'summary': summary if row['terminal'] else row['label'] + ' is supported within the bounded source packet.',
                    'citations': cites} for row in template['process_catalog']['nodes']], 'knowledge_candidates': []}
    validate_result(proposal, INTERPRET_SCHEMA)
    return proposal, predicates


class DeterministicReferenceAdapter:
    def __init__(self, policy, profile=None):
        self.policy, self.profile = policy, profile or ReferenceProfile()
        self.config = {'contract': REFERENCE_CONTRACT, 'mode': 'deterministic_reference', 'provider_calls': 0,
                       'profile_sha256': self.profile.sha256, 'policy_id': REFERENCE_POLICY_ID,
                       'rule_set_sha256': digest_value(policy)}

    def _receipt(self, stage, context, identity, result, compilation=None):
        material = {'contract': REFERENCE_CONTRACT, 'stage': stage, 'identity': identity,
                    'context_sha256': digest_value(context), 'result_sha256': digest_value(result),
                    'metadata': {'execution_mode': 'deterministic_reference', 'synthetic': True,
                                 'as_of': context['reference_provenance']['as_of'],
                                 'knowledge_recipe_compilation': compilation}, 'provider_calls': 0, 'budget_writes': 0}
        return {**material, 'receipt_sha256': digest_value(material)}

    def interpret_reference(self, context, identity):
        result, _ = reference_findings(self.policy, context['sources'])
        return {'result': result, 'receipt': self._receipt('interpret_reference', context, identity, result)}

    def verify_reference(self, context, proposal, identity):
        # Fresh rule evaluation verifies semantic content, not only matching quotes.
        expected, predicates = reference_findings(self.policy, context['sources'])
        expected, compilation = compile_verification_proposal(context, expected)
        candidate, _ = compile_verification_proposal(context, proposal)
        checks = []
        expected_items = proposal_items(expected)
        for key, row in proposal_items(candidate).items():
            valid = row == expected_items.get(key) and all(
                any(s['artifact_id'] == c['artifact_id'] and s.get('complete') is True and c['quote'] in s['text']
                    for s in context['sources']) for c in row.get('citations', []))
            if key.startswith('knowledge:'):
                kind = row['document_type']
                valid = valid and row['required_fields'] == self.policy['required_fields_by_document'][kind]
            checks.append({'item_id': key, 'accepted': valid,
                           'reason': 'Recomputed bounded evidence rule and exact source span.' if valid else 'Source rule or item differs.'})
        result = {'family_supported': candidate['category']['family'] == expected['category']['family'], 'checks': checks,
                  'issues': [p['predicate_id'] + ' remains unknown' for p in predicates if p['status'] == 'unknown']}
        validate_result(result, VERIFY_SCHEMA)
        return {'result': result, 'receipt': self._receipt('verify_reference', context, identity, result, compilation)}
