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
from .autonomous_reference_policy_v1 import PROFILE_ROOT, V2_PROFILE_ROOT, REFERENCE_POLICY_ID, SCOPES
from .workspace_corpus import digest_value
from .autonomous_operations_v1 import observe, citation_source, observing

REFERENCE_CONTRACT = 'casepath.deterministic-reference/1.0.0'
CLEANUP_CONTRACT = 'casepath.synthetic-reference-cleanup/2.0.0'
LEGACY_PROFILE_SHA256 = '15c44d004cc1a34b90e8662b3185deb63652ab066c7727b080dfc0987a648de7'
V2_PROFILE_SHA256 = '18c2ff55eb39324fee225b2b44330079715d1de11234d2367a2ed172b59c0869'
V2_LABEL = 'Synthetic demonstration document (fictional)\n'


def clean_reference_source(raw):
    """Deterministic presentation cleanup; scenario facts and dates stay intact."""
    lines = raw.decode('utf-8').splitlines(keepends=True)
    if (len(lines) < 11 or lines[0] != 'SYNTHETIC SUPPLEMENT — FICTIONAL DEMONSTRATION SOURCE\n'
            or not lines[6].startswith('Fictional source date: ')
            or not lines[7].startswith('Fictional review as-of: ')
            or not lines[8].startswith('Fixture author: ') or lines[9] != '\n'):
        raise ValueError('unknown legacy reference source header')
    body = ''.join(lines[10:])
    body = re.sub(r' with SHA256 [a-f0-9]{64}', '', body)
    body = re.sub(r', SHA256 [a-f0-9]{64}', '', body)
    for before, after in (
        ('The landlord in this fictional supplement is ', 'The landlord is '),
        ('Fictional service author: ', 'Service author: '),
        ('synthetic building-heating technician', 'building-heating technician'),
        ('fictional calibration check', 'calibration check'),
        ('Fictional speaker: ', 'Speaker: '),
        ('Our fictional call log records', 'Our call log records'),
        ('Fictional issuance archive', 'Issuance archive'),
        ('fictional review as-of date', 'review as-of date'),
        ('Fictional email archive: ', 'Email archive: '),
        ('The fictional managing agent confirms', 'The managing agent confirms'),
        ('by this candidate packet', 'in this packet'),
        ('This archive confirmation records the fictional factual packet only; it does not assert a legal decision.',
         'This archive confirmation records the factual packet only; it does not assert a legal decision.'),
        ('This fictional service finding makes no legal decision, awards no compensation and claims no real commissioned inspection.',
         'This service finding makes no legal decision and awards no compensation.'),
        ('The original unknown date/basis is clarified by this new fictional packet confirmation; no original bytes are rewritten and no challenge or communication has actually been filed/sent.',
         'This packet confirmation clarifies the previously unknown notification date and basis; no challenge has been filed and no communication has been sent.'),
    ):
        body = body.replace(before, after)
    return (V2_LABEL + lines[6].replace('Fictional source date:', 'Source date:')
            + lines[7].replace('Fictional review as-of:', 'Review as-of:') + '\n' + body).encode('utf-8')


class ReferenceProfile:
    def __init__(self, root=V2_PROFILE_ROOT):
        self.root = root
        self.raw = (root / 'profile.json').read_bytes()
        self.value = json.loads(self.raw)
        self.sha256 = sha256(self.raw).hexdigest()
        if self.value['contract'] != 'casepath.synthetic-reference-sources/1.0.0':
            raise ValueError('unknown reference source profile')
        if self.value['profile_id'] not in {'synthetic-nine-v1', 'synthetic-nine-v2'}:
            raise ValueError('unknown reference source profile')
        if self.value['profile_id'] == 'synthetic-nine-v1' and self.sha256 != LEGACY_PROFILE_SHA256:
            raise ValueError('legacy reference profile bytes changed')
        if self.value['profile_id'] == 'synthetic-nine-v2':
            if self.sha256 != V2_PROFILE_SHA256:
                raise ValueError('reference source profile bytes changed')
            legacy = self.for_profile('synthetic-nine-v1')
            if (self.value.get('supersedes') != {'profile_id': 'synthetic-nine-v1', 'profile_sha256': legacy.sha256}
                    or self.value.get('cleanup_contract') != CLEANUP_CONTRACT or self.ids != legacy.ids):
                raise ValueError('reference cleanup lineage differs')
            for cid in self.ids:
                entry, old_entry = self.value['claims'][cid], legacy.value['claims'][cid]
                if {k: v for k, v in entry.items() if k != 'sources'} != {k: v for k, v in old_entry.items() if k != 'sources'}:
                    raise ValueError('reference cleanup claim binding differs')
                if len(entry['sources']) != len(old_entry['sources']):
                    raise ValueError('reference cleanup source roster differs')
                for source, old in zip(entry['sources'], old_entry['sources']):
                    if source.get('legacy_source') != old or source['file_name'] != old['file_name'] or source['media_type'] != old['media_type']:
                        raise ValueError('reference cleanup source lineage differs')
                    old_raw = legacy._raw(cid, old)
                    cleaned = clean_reference_source(old_raw)
                    equivalence = {'contract': CLEANUP_CONTRACT, 'legacy_source_sha256': old['sha256'],
                                   'source_sha256': source['sha256']}
                    if (self._raw(cid, source) != cleaned
                            or source.get('cleanup_equivalence_sha256') != digest_value(equivalence)):
                        raise ValueError('reference cleanup equivalence differs')

    @classmethod
    def for_profile(cls, profile_id):
        roots = {'synthetic-nine-v1': PROFILE_ROOT, 'synthetic-nine-v2': V2_PROFILE_ROOT}
        if profile_id not in roots:
            raise ValueError('unknown reference source profile')
        return cls(roots[profile_id])

    @classmethod
    def resolve(cls, state, sources):
        """Resolve an exact physical roster for read-only historical projections."""
        for profile_id in ('synthetic-nine-v1', 'synthetic-nine-v2'):
            profile = cls.for_profile(profile_id)
            if profile.match(state, sources):
                return profile
        return None

    @property
    def ids(self):
        return tuple(sorted(self.value['claims']))

    def files(self, claim_id):
        result = []
        for source in self.value['claims'][claim_id]['sources']:
            raw = self._raw(claim_id, source)
            result.append({'file_name': source['file_name'], 'media_type': source['media_type'],
                           'content_base64': base64.b64encode(raw).decode()})
        return result

    def _raw(self, claim_id, source):
        raw = (self.root / claim_id / source['file_name']).read_bytes()
        if sha256(raw).hexdigest() != source['sha256'] or len(raw) != source['size_bytes']:
            raise ValueError('synthetic reference source bytes changed')
        return raw

    def match(self, state, sources):
        entry = self.value['claims'].get(state['claim_id'])
        binding = state.get('original_binding', {})
        if (entry is None or binding.get('corpus_manifest_sha256') != entry['corpus_manifest_sha256']
                or binding.get('claim_binding_sha256') != entry['original_binding_sha256']):
            return None
        by_hash = {row['sha256']: row for row in sources}
        expected = {s['sha256'] for s in entry['sources']}
        originals = {row['sha256'] for row in binding['source_map']}
        retired = {s['legacy_source']['sha256'] for s in entry['sources']} if self.value['profile_id'] == 'synthetic-nine-v2' else set()
        # Only a complete registered legacy roster may survive a v2 admission.
        # Unknown, partial or foreign extras may contain adverse evidence.
        physical = set(by_hash)
        if physical not in (expected | originals, expected | originals | retired) or len(sources) != len(physical):
            return None
        registered = entry['sources'] + ([s['legacy_source'] for s in entry['sources']] if physical & retired else [])
        for source in registered:
            actual = by_hash[source['sha256']]
            raw_root = PROFILE_ROOT if source['sha256'] in retired else self.root
            raw = (raw_root / state['claim_id'] / source['file_name']).read_bytes()
            if (actual.get('complete') is not True or actual.get('role') != 'supporting_document'
                    or sha256(raw).hexdigest() != source['sha256'] or len(raw) != source['size_bytes']
                    or actual.get('text') != raw.decode('utf-8')):
                return None
        provenance = {'contract': REFERENCE_CONTRACT, 'mode': 'deterministic_reference', 'synthetic': True,
                'profile_id': self.value['profile_id'], 'profile_sha256': self.sha256, 'as_of': entry['as_of'],
                'source_roster_sha256': digest_value(state['source_descriptors'])}
        if self.value['profile_id'] == 'synthetic-nine-v2':
            provenance['source_artifact_ids'] = [s['artifact_id'] for s in sources if s['sha256'] in expected | originals]
            provenance['superseded_source_artifact_ids'] = [s['artifact_id'] for s in sources if s['sha256'] in retired]
            provenance['superseded_sources'] = [{
                'artifact_id': by_hash[s['legacy_source']['sha256']]['artifact_id'],
                'sha256': s['legacy_source']['sha256'],
                'replacement_artifact_id': by_hash[s['sha256']]['artifact_id'],
                'replacement_sha256': s['sha256'], 'cleanup_equivalence_sha256': s['cleanup_equivalence_sha256']}
                for s in entry['sources'] if s['legacy_source']['sha256'] in by_hash]
        return provenance

    def active_sources(self, state, sources):
        if not self.match(state, sources):
            raise ValueError('reference physical source roster differs')
        expected = {s['sha256'] for s in self.value['claims'][state['claim_id']]['sources']}
        originals = {s['sha256'] for s in state['original_binding']['source_map']}
        return [s for s in sources if s['sha256'] in expected | originals]


def reference_replay_start(head, events):
    """Metadata for a real accepted reset, derived from one verified journal head."""
    if (not head or not isinstance(head.get('outcome'), dict) or head['outcome'].get('assessment_status') != 'complete'
            or not isinstance(head.get('evaluation'), dict) or head['evaluation'].get('process_status') != 'complete'):
        return None
    run_id = head.get('run_id')
    contexts = head.get('semantic_contexts', {})
    context = contexts.get(run_id, {}) if isinstance(contexts, dict) else {}
    provenance = context.get('reference_provenance') if isinstance(context, dict) else None
    if not isinstance(provenance, dict) or provenance.get('profile_id') != 'synthetic-nine-v2':
        return None
    completed = next((e for e in reversed(events) if e['idempotency_key'] == f'{run_id}.outcome'
                      and e['kind'] == 'outcome.recorded'), None)
    baseline = next((e for e in events if e['idempotency_key'] == f'{run_id}.prepare'
                     and e['kind'] == 'process.prepared'), None)
    accepted = next((e for e in events if e['idempotency_key'] == f'{run_id}.interpretation'
                     and e['kind'] == 'interpretation.accepted'), None)
    if (completed is None or baseline is None or accepted is None
            or not baseline['sequence'] < accepted['sequence'] < completed['sequence']
            or any(e['claim_id'] != head['claim_id'] for e in (baseline, accepted, completed))
            or any(e['kind'] in {'process.prepared', 'interpretation.accepted', 'action.completed'}
                   for e in events[completed['sequence']:])
            or baseline['payload']['graph']['family'] != 'incoming_packet'
            or not any(e['kind'] in {'process.prepared', 'interpretation.accepted'}
                       for e in events[:baseline['sequence'] - 1])):
        return None
    execution = completed['payload']['receipt'].get('reference_execution')
    if not isinstance(execution, dict) or not isinstance(execution.get('config'), dict):
        return None
    config = execution['config']
    rule_hash = config.get('rule_set_sha256')
    if not isinstance(rule_hash, str) or re.fullmatch('[a-f0-9]{64}', rule_hash) is None:
        return None
    profile = ReferenceProfile.for_profile('synthetic-nine-v2')
    matched = profile.match(head, head['acquired_sources'])
    if matched is None:
        return None
    expected_config = {'contract': REFERENCE_CONTRACT, 'mode': 'deterministic_reference', 'provider_calls': 0,
                       'profile_sha256': profile.sha256, 'policy_id': REFERENCE_POLICY_ID, 'rule_set_sha256': rule_hash}
    expected_provenance = {**matched, 'rule_set_sha256': rule_hash}
    active = profile.active_sources(head, head['acquired_sources'])
    sources = [{k: s[k] for k in ('artifact_id', 'file_name', 'media_type', 'role', 'sha256',
                                'text', 'complete', 'coverage')} for s in active]
    packs = context.get('rule_packs')
    selected = [p for p in packs if isinstance(p, dict) and p.get('family') == head['graph']['family']] if isinstance(packs, list) else []
    normative = json.loads((PROFILE_ROOT / 'normative_sources.json').read_bytes())
    if (provenance != expected_provenance or config != expected_config
            or head['outcome'].get('reference_provenance') != provenance
            or execution != {'config': config, 'provenance': provenance, 'normative_sources_sha256': digest_value(normative)}
            or accepted['payload']['receipt'].get('reference_execution') != execution
            or context.get('claim_id') != head['claim_id'] or context.get('policy_id') != REFERENCE_POLICY_ID
            or head.get('policy_id') != REFERENCE_POLICY_ID or context.get('execution_mode') != 'deterministic_reference'
            or context.get('normative_sources') != normative or context.get('sources') != sources
            or len(selected) != 1 or selected[0].get('template_sha256') != accepted['payload']['receipt'].get('rule_pack_sha256')
            or selected[0].get('template_sha256') != completed['payload']['receipt'].get('rule_pack_sha256')
            or run_id != 'autonomy.' + digest_value({'claim': head['claim_id'], 'sources': matched['source_roster_sha256'],
                'policy': REFERENCE_POLICY_ID, 'rules': rule_hash, 'reference': config})[:24]):
        return None
    return {'contract': 'casepath.reference-replay-start/1.0.0', 'claim_id': head['claim_id'],
            'from_seq': baseline['sequence'], 'state_sha256': baseline['resulting_state_sha256'],
            'event_sha256': baseline['event_sha256'], 'run_id': run_id,
            'profile_id': provenance['profile_id'], 'profile_sha256': provenance['profile_sha256'],
            'source_artifact_ids': list(provenance['source_artifact_ids'])}


def _find(sources, pattern, *, role='supporting_document'):
    for source in sources:
        if source['role'] != role or source.get('complete') is not True:
            continue
        opened = read = None
        if observing():
            opened = observe('source.open', 'source', source['artifact_id'],
                             {'artifact_id': source['artifact_id'], 'sha256': source['sha256']},
                             {'artifact_id': source['artifact_id'], 'sha256': source['sha256'],
                              'text': source['text'], 'text_sha256': sha256(source['text'].encode()).hexdigest(),
                              'complete': source['complete'], 'role': source['role'], 'file_name': source.get('file_name')})
            examined = citation_source({'artifact_id': source['artifact_id'], 'quote': source['text'],
                                        'start_char': 0, 'end_char': len(source['text'])}, sources)
            read = observe('span.read', 'source', source['artifact_id'], {'pattern': pattern, 'flags': ['DOTALL']},
                           {'characters_read': len(source['text'])}, source=examined, causes=[opened])
        match = re.search(pattern, source['text'], re.S)
        matched_span = citation_source({'artifact_id': source['artifact_id'], 'quote': match.group(),
                                       'start_char': match.start(), 'end_char': match.end()}, sources) if match else None
        observe('phrase.match', 'source', source['artifact_id'], {'pattern': pattern, 'flags': ['DOTALL']},
                {'matched': bool(match), 'admissible_length': bool(match and 0 < len(match.group()) <= 800)},
                source=matched_span, causes=[read])
        if match and 0 < len(match.group()) <= 800:
            return {'artifact_id': source['artifact_id'], 'quote': match.group()}
    return None


def reference_findings(policy, sources):
    """Closed source rules. A matched filename, type or boolean grants nothing."""
    # A v2 physical roster can retain complete immutable v1 counterparts. They
    # remain in acquisition/history, but only the cleaned documents are active.
    v2 = any(s.get('text', '').startswith(V2_LABEL) for s in sources)
    if v2:
        legacy_hashes = {s['sha256'] for entry in ReferenceProfile.for_profile('synthetic-nine-v1').value['claims'].values()
                         for s in entry['sources']}
        sources = [s for s in sources if s['sha256'] not in legacy_hashes]
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
            observe('fact.extract', 'fact', 'fact:' + kind, {'document_type': kind},
                    {'status': 'provisional', 'summary': summary, 'verification_required': True},
                    source=citation_source(citation, sources))

    def predicate(name, citation, articles, *, failed=False):
        predicates.append({'predicate_id': name, 'status': 'unknown' if not citation else 'failed' if failed else 'supported',
                           'citations': [citation] if citation else [],
                           'rule_refs': ['CO:' + a for a in articles]})
        observe('fact.extract', 'fact', name, {'rule_refs': ['CO:' + a for a in articles]},
                {'status': 'provisional', 'proposed_status': predicates[-1]['status'], 'verification_required': True},
                source=citation_source(citation, sources))

    document('tenancy_terms_evidence', terms, 'Source attestation establishes the relevant tenancy terms; no complete lease is claimed received.')
    predicate('residential_tenancy_scope', terms, SCOPES[family]['articles'])
    if family == 'defect_mold_heating':
        observation = _find(sources, r'On [^\n]+?no tenant alteration or misuse explains the failure\.')
        continuing = _find(sources, r'The defect persists[^\n]+?principal living rooms\.')
        knowledge = _find(sources, r'Our call log records[^\n]+?first documented knowledge of the defect\.' if v2 else r'Our fictional call log records[^\n]+?first documented knowledge of the defect\.')
        responsibility = _find(sources, r'We confirm the tenant[^\n]+?as of this acknowledgment\.')
        document('objective_defect_observation', observation, 'The dated calibrated observation identifies the fixed-pump fault and its causal limits.')
        document('landlord_knowledge_evidence', knowledge, 'The landlord acknowledgment records first knowledge of the reported continuing defect.')
        predicate('objective_use_impairment', continuing, ['259a', '259d'])
        predicate('outside_small_tenant_maintenance_and_no_tenant_cause', observation, ['259', '259a'])
        predicate('landlord_first_knowledge', knowledge, ['259d'])
        predicate('continuing_defect_without_remedy', responsibility, ['259a', '259d'])
        summary = 'The fictional source packet supports defect removal and proportional reduction eligibility from documented landlord knowledge until remedy. The reduction amount, repair itself and any award remain undetermined.'
        if v2:
            summary = 'The sources support defect removal and proportional rent-reduction eligibility from documented landlord knowledge until remedy. Repair, the reduction amount and any award remain undetermined.'
    elif family == 'lease_termination_dispute':
        archive = _find(sources, r'Issuance archive[^\n]+?receipt at that time\.' if v2 else r'Fictional issuance archive[^\n]+?receipt at that time\.')
        no_form = _find(sources, r'It was a plain letter, not a canton-approved termination form\.')
        complete = _find(sources, r'No other attachment, approved form[^\n]+?as-of date\.')
        notice = _find(sources, r'(?:Termination of tenancy|Kündigung[^\n]*)[\s\S]{1,450}?(?:three months after receipt|drei Monate[^\n]*)')
        # The actual unsigned received letter is reviewed, never a nonexistent approved form.
        document('received_termination_packet', notice, 'The actual received letter is readable for form assessment; this does not authenticate an approved form or valid termination.')
        document('original_notification_context', archive, 'The issuance archive establishes issuer authority and the actual delivery context.')
        predicate('issuer_authority_and_received_packet', archive, ['266l'])
        predicate('complete_channel_archive', complete, ['266l', '266o'])
        predicate('canton_approved_form', no_form, ['266l', '266o'], failed=True)
        summary = 'The fictional complete received packet lacks a canton-approved termination form, supporting a finding that the notice is invalid under CO 266l/266o. No challenge was filed and no court outcome or verified filing deadline is recorded.'
        if v2:
            summary = 'The complete received packet lacks a canton-approved termination form, supporting invalidity under CO 266l/266o. A court outcome and verified filing deadline remain unknown.'
    else:
        notice = _find(sources, r'Begründung der Erhöhung:\nBegründung gemäss separatem Begleitschreiben1')
        archive = _find(sources, r'The managing agent confirms[^\n]+?original notification\.' if v2 else r'The fictional managing agent confirms[^\n]+?original notification\.')
        none = _find(sources, r'No contemporaneous accompanying reason letter[^\n]+?was issued or received\.')
        ordinary = _find(sources, r'The rent is not indexed or stepped, and there is no Article269c agreed increase\.')
        later = _find(sources, r'This reply was sent after[^\n]+?original communication\.')
        document('received_rent_increase_packet', notice, 'The received original form permits a bounded assessment of its uncompleted reasons field; lawful reasons are not claimed established.')
        document('original_notification_context', archive, 'The authorized issuer confirms the complete original notification and absence of contemporaneous reasons.')
        predicate('ordinary_non269c_tenancy', ordinary, ['269d'])
        predicate('issuer_authority_and_complete_packet', archive, ['269d'])
        predicate('contemporaneous_substantive_reasons', none, ['269d'], failed=True)
        predicate('later_email_is_not_original_reasons', later, ['269d'])
        summary = 'The fictional complete original increase packet omitted substantive reasons, supporting a finding that the increase notice is invalid under CO 269d(2)(b). The later market reply is contextual evidence. A mechanical signature is permitted at this historical date; whether the rent is excessive, the disputed amount and filing deadlines remain undetermined.'
        if v2:
            summary = 'The complete original increase packet omitted substantive reasons, supporting invalidity under CO 269d(2)(b); the later market reply remains contextual evidence. Whether the rent is excessive, the disputed amount and filing deadlines remain undetermined.'
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
            observe('verification.check', 'fact' if not key.startswith('document:') else 'document', key,
                    {'candidate': row, 'expected': expected_items.get(key)}, checks[-1],
                    source=citation_source(row.get('citations', [None])[0] if valid and row.get('citations') else None, context['sources']))
        result = {'family_supported': candidate['category']['family'] == expected['category']['family'], 'checks': checks,
                  'issues': [p['predicate_id'] + ' remains unknown' for p in predicates if p['status'] == 'unknown']}
        validate_result(result, VERIFY_SCHEMA)
        return {'result': result, 'receipt': self._receipt('verify_reference', context, identity, result, compilation)}
