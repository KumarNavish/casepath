"""Durable local claim execution with independent semantic verification."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import RLock

from .assessment_grammar_v1 import FAMILY_FLAGS
from .autonomous_knowledge_v1 import AutonomousKnowledge, qualify
from .autonomous_policy_v1 import (
    POLICY_ID, REQUIRED_FACTS, REQUIRED_FIELDS, KNOWLEDGE_RECIPE_COMPILER,
    SUPPLIED_DOCUMENT_REVIEW_POLICY, OPERATIONAL_CONDITION_QUESTIONS,
    INTERPRET_INSTRUCTIONS, VERIFY_INSTRUCTIONS, compile_process, compile_verification_proposal,
    initial_process, receipt, validate_interpretation,
)
from .causal_process_v1 import evaluate, seal_graph, _document_definition_sha256
from .workspace_corpus import digest_value


class SupersededWorkflow(RuntimeError):
    pass


EXTERNAL_CAPABILITIES = {
    'dh_safety': 'A medical or safety escalation requires a configured external specialist channel.',
    'dh_specialist': 'An on-site technical inspection requires an external specialist.',
    'dh_deposit': 'Official rent-deposit handling requires verified filing authority.',
    'dh_resolution': 'Repair or referral needs a confirmed external action or outcome.',
    'dh_close': 'Closing the claim requires a confirmed repair, referral or authorized decision.',
    'lt_deadline': 'A verified deadline calculation and filing capability are not configured.',
    'lt_resolution': 'Challenge, extension or settlement execution requires external authority.',
    'lt_close': 'A termination outcome requires a confirmed external decision or agreement.',
    'ri_deadline': 'A verified deadline calculation and filing capability are not configured.',
    'ri_reference': 'A reference-rate calculation requires an admitted calculation rule and verified inputs.',
    'ri_renovation': 'Cost allocation requires a qualified specialist assessment.',
    'ri_resolution': 'A challenge or negotiated resolution requires external execution authority.',
    'ri_close': 'The outcome requires a confirmed external decision or agreement.',
}


def execution_capability(node_id):
    if node_id == 'investigate_packet':
        return {'id': 'local_inbox.read', 'authorized': True, 'reason': 'Acquire supplied bytes and record their extraction coverage.'}
    if node_id in EXTERNAL_CAPABILITIES:
        return {'id': None, 'authorized': False, 'reason': EXTERNAL_CAPABILITIES[node_id]}
    return {'id': 'local_assessment.record', 'authorized': True,
            'reason': 'Record a verified internal assessment when source sufficiency and process prerequisites are established.'}


class AutonomousController:
    def __init__(self, store, policy, model=None):
        self.store, self.policy, self.model = store, policy, model
        self.knowledge = AutonomousKnowledge(store, policy)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='casepath-autonomous')
        self._lock, self._jobs, self._pending, self._contexts = RLock(), {}, set(), {}
        self._closed = False

    def submit(self, claim_id):
        with self._lock:
            if self._closed:
                return
            current = self._jobs.get(claim_id)
            if current and not current.done():
                self._pending.add(claim_id)
                return
            roster = digest_value(self.store.get(claim_id)['source_descriptors'])
            future = self._executor.submit(self.run, claim_id)
            self._jobs[claim_id] = future
            def finished(_):
                with self._lock:
                    changed = digest_value(self.store.get(claim_id)['source_descriptors']) != roster
                    pending = claim_id in self._pending
                    self._pending.discard(claim_id)
                    if (changed or pending) and (self.store.get(claim_id).get('deferral') or {}).get('code') != 'paused':
                        self.submit(claim_id)
            future.add_done_callback(finished)

    def resume(self):
        for state in self.store.list():
            if (state.get('deferral') or {}).get('code') == 'paused':
                continue
            if state.get('outcome') and state.get('run_id'):
                # The accepted outcome may precede a process stop by only one
                # event. Resume its deterministic publication, never inference.
                self._contexts[state['run_id']] = digest_value(state['source_descriptors'])
                self._executor.submit(self._learn, state['claim_id'], state['run_id'])
            elif state['status'] in {'received', 'running'} or self.model is not None and (state.get('deferral') or {}).get('code') == 'model_unavailable':
                self.submit(state['claim_id'])

    def shutdown(self):
        with self._lock:
            self._closed = True
        self._executor.shutdown(wait=True, cancel_futures=True)

    def _once(self, claim_id, key, kind, payload):
        with self._lock:
            state = self.store.get(claim_id)
            workflow = '.'.join(key.split('.')[:2])
            self._current(state, workflow)
            existing = next((e for e in self.store.events(claim_id) if e['idempotency_key'] == key), None)
            if existing:
                if existing['kind'] != kind:
                    raise ValueError('autonomous operation identity changed')
                return state
            data = payload(state) if callable(payload) else payload
            return self.store.append(claim_id, kind, data, expected_revision=state['revision'],
                                     expected_state_sha256=state['state_sha256'], idempotency_key=key)

    def _current(self, state, workflow):
        expected = self._contexts.get(workflow)
        if expected is not None and digest_value(state['source_descriptors']) != expected:
            raise SupersededWorkflow('New evidence superseded this interpretation.')
        if (state.get('deferral') or {}).get('code') == 'paused':
            raise SupersededWorkflow('Autonomous work is paused.')

    def _phase(self, claim_id, workflow, name, summary):
        return self._once(claim_id, f'{workflow}.{name}', 'work.phase', {'phase': name, 'summary': summary})

    def run(self, claim_id):
        state = self.store.get(claim_id)
        source_identity = digest_value(state['source_descriptors'])
        workflow = 'autonomy.' + digest_value({'claim': claim_id, 'sources': source_identity, 'policy': POLICY_ID,
                                              'rules': digest_value(self.policy)})[:24]
        self._contexts[workflow] = source_identity
        if (state.get('deferral') or {}).get('code') == 'paused':
            return state
        # A terminal outcome for this exact input is settled on reconnect.
        if any(e['idempotency_key'] == f'{workflow}.outcome' for e in self.store.events(claim_id)):
            self._learn(claim_id, workflow)
            return self.store.get(claim_id)
        try:
            self._once(claim_id, f'{workflow}.start', 'work.started', {'run_id': workflow, 'policy_id': POLICY_ID})
            if self.model is not None and (self.store.get(claim_id).get('deferral') or {}).get('code') == 'model_unavailable':
                self._once(claim_id, f'{workflow}.configured', 'work.started', {'run_id': workflow, 'policy_id': POLICY_ID})
            state = self.store.get(claim_id)
            if state['graph'] is None:
                graph, facts, obligations = initial_process(claim_id, [d for d in state['source_descriptors'] if d['role'] != 'customer_message'])
                self._once(claim_id, f'{workflow}.prepare', 'process.prepared', lambda s: {
                    'graph': graph, 'facts': facts, 'obligations': obligations,
                    'receipt': receipt(s, 'prepare_source_investigation', after_graph_sha256=graph['graph_sha256'])})
            self._phase(claim_id, workflow, 'acquiring', 'Opening the supplied supporting files and verifying their original bytes.')
            for descriptor in state['source_descriptors']:
                if descriptor['artifact_id'] in {s['artifact_id'] for s in self.store.get(claim_id)['acquired_sources']}:
                    continue
                source = self.store.acquire(claim_id, descriptor['artifact_id'])
                self._once(claim_id, f"{workflow}.acquire.{descriptor['artifact_id']}", 'sources.acquired', {'sources': [source]})
            state = self.store.get(claim_id)
            if self.model is None:
                self._once(claim_id, f'{workflow}.model_unavailable', 'work.deferred', {
                    'code': 'model_unavailable', 'reason': 'The evidence is saved. Autonomous interpretation requires the configured inference service.'})
                return self.store.get(claim_id)
            self._phase(claim_id, workflow, 'interpreting', 'Interpreting the source packet against the admitted tenancy rules.')
            context = {'claim_id': claim_id, 'title': state['title'], 'policy_id': POLICY_ID,
                       'knowledge_recipe_compiler': KNOWLEDGE_RECIPE_COMPILER,
                       'document_review_policy': SUPPLIED_DOCUMENT_REVIEW_POLICY,
                       'operational_condition_questions': deepcopy(OPERATIONAL_CONDITION_QUESTIONS),
                       'rule_packs': [{'family': t['domain'], 'template_id': t['template_id'], 'title': t['title'],
                                       'content': t['content'], 'template_sha256': digest_value(t),
                                       'process_catalog': {kind: [{k: v for k, v in row.items() if k != 'assertion'} for row in rows]
                                                           for kind, rows in t['process_catalog'].items()}} for t in self.policy['templates']],
                       'condition_catalog': FAMILY_FLAGS,
                       'required_facts_by_document': REQUIRED_FACTS,
                       'required_fields_by_document': REQUIRED_FIELDS,
                       'sources': [{key: source[key] for key in ('artifact_id', 'file_name', 'media_type', 'role', 'sha256',
                                                                 'text', 'complete', 'coverage')} for source in state['acquired_sources']],
                       'instructions': {'interpret': INTERPRET_INSTRUCTIONS, 'verify': VERIFY_INSTRUCTIONS}}
            if workflow in state.get('semantic_contexts', {}):
                context = state['semantic_contexts'][workflow]
            else:
                context['compatible_knowledge'] = [{key: value.get(key) for key in ('knowledge_id', 'version', 'family',
                                                   'rule_pack_sha256', 'evidence_recipes', 'knowledge_sha256')}
                    for family in FAMILY_FLAGS if (value := self.knowledge.compatible(family))]
                self._once(claim_id, f'{workflow}.context', 'work.context', {'workflow_id': workflow, 'context': context})
            if context.get('document_review_policy') not in (None, SUPPLIED_DOCUMENT_REVIEW_POLICY):
                raise ValueError('unknown supplied-document review policy')
            identity = {'workflow_id': workflow, 'claim_id': claim_id, 'policy_id': POLICY_ID,
                        'source_roster_sha256': source_identity, 'rule_set_sha256': digest_value(self.policy)}
            proposal = self.model.interpret(context, identity)
            self._current(self.store.get(claim_id), workflow)
            verification_proposal, compilation = compile_verification_proposal(context, proposal['result'])
            self._phase(claim_id, workflow, 'verifying', 'Independently checking the proposed facts, branches and document sufficiency.')
            verifier = self.model.verify(context, proposal['result'], identity)
            self._current(self.store.get(claim_id), workflow)
            if compilation is not None and verifier['receipt'].get('metadata', {}).get('knowledge_recipe_compilation') != compilation:
                raise ValueError('independent verifier receipt differs from the compiled proposal')
            verified = validate_interpretation(self.policy, state['acquired_sources'], verification_proposal, verifier['result'])
            base_receipt = {'proposal_sha256': digest_value(proposal['result']), 'verifier_sha256': digest_value(verifier['result']),
                            'rule_pack_sha256': verified['rule_pack_sha256'], 'workflow_id': workflow,
                            'proposal_receipt': proposal['receipt'], 'verifier_receipt': verifier['receipt'],
                            'checks': verifier['result']['checks'], 'knowledge_candidates': verified['knowledge_candidates'],
                            'knowledge_rejections': verified['knowledge_rejections']}
            if compilation is not None:
                base_receipt['knowledge_recipe_compilation'] = compilation
            if context.get('document_review_policy') is not None:
                base_receipt['document_review_policy'] = context['document_review_policy']
            pinned = next((k for k in context.get('compatible_knowledge', []) if k['family'] == verified['category']['family']), None)
            version = next((k for k in self.knowledge.view()['versions'] if pinned and k['knowledge_id'] == pinned['knowledge_id']
                            and k['version'] == pinned['version']), None)
            if version:
                graph, facts, obligations = self.knowledge.instantiate(version, claim_id, verified)
                self._once(claim_id, f'{workflow}.reuse', 'knowledge.used', {'knowledge': {
                    'knowledge_id': version['knowledge_id'], 'version': version['version'],
                    'definition_sha256': version['qualification']['definition_sha256'], 'rule_pack_sha256': version['rule_pack_sha256'],
                    'applicability': 'same_verified_family_and_rule_version', 'avoided_rule_compilations': 1,
                    'reused_evidence_recipes': len(version.get('evidence_recipes', [])), 'workflow_id': workflow}})
            else:
                graph, facts, obligations = compile_process(self.policy, claim_id, verified)
            self._once(claim_id, f'{workflow}.interpretation', 'interpretation.accepted', lambda s: {
                'graph': graph, 'facts': facts, 'obligations': obligations,
                'receipt': receipt(s, 'accept_verified_interpretation', **base_receipt, after_graph_sha256=graph['graph_sha256'])})
            self._phase(claim_id, workflow, 'progressing', 'Applying verified evidence to active process obligations.')
            self._documents(claim_id, workflow, verified, base_receipt)
            self._steps(claim_id, workflow, verified, base_receipt)
            self._outcome(claim_id, workflow, verified, base_receipt)
            self._learn(claim_id, workflow)
        except SupersededWorkflow:
            if digest_value(self.store.get(claim_id)['source_descriptors']) != source_identity and hasattr(self.model, 'abandon'):
                self.model.abandon(workflow, 'superseded_or_paused')
            return self.store.get(claim_id)
        except Exception as error:
            # Known provider failures and unknown HTTP effects are durable in the
            # shared provider ledger. Never resend here or fabricate a result.
            from .autonomous_store_v1 import AutonomousStoreError
            from .autonomous_model_v1 import AutonomousModelError
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise
            code = 'provider_deferred' if isinstance(error, AutonomousModelError) else 'verification_deferred' if isinstance(error, ValueError) else 'execution_deferred'
            reason = str(error) if isinstance(error, (ValueError, AutonomousStoreError, AutonomousModelError)) else 'Autonomous work stopped before a verified result. Its saved request receipts are available for diagnosis.'
            try:
                self._once(claim_id, f'{workflow}.failure.{digest_value(reason)[:12]}', 'work.deferred',
                           {'code': code, 'reason': reason[:1800], 'details': {'error_type': type(error).__name__, 'workflow_id': workflow}})
            except SupersededWorkflow:
                pass
            if hasattr(self.model, 'abandon'):
                self.model.abandon(workflow, 'execution_deferred')
        return self.store.get(claim_id)

    def _documents(self, claim_id, workflow, verified, base_receipt):
        context = self.store.get(claim_id).get('semantic_contexts', {}).get(workflow, {})
        review_policy = context.get('document_review_policy')
        if (review_policy not in (None, SUPPLIED_DOCUMENT_REVIEW_POLICY)
                or base_receipt.get('document_review_policy') != review_policy):
            raise ValueError('document review policy differs from the pinned workflow context')
        for document in verified['documents']:
            state = self.store.get(claim_id)
            graph = deepcopy(state['graph'])
            view = evaluate(graph)
            route = next(d for d in view['documents'] if d['document_type'] == document['document_type'])
            source = next(s for s in state['acquired_sources'] if s['artifact_id'] == document['artifact_id'])
            # Reviewing an available original does not activate its process
            # route. Historical contexts retain the original active-only rule.
            supplied_review = (review_policy == SUPPLIED_DOCUMENT_REVIEW_POLICY
                               and document.get('independently_verified') is True
                               and source['role'] == 'supporting_document')
            if route['activation'] != 'true' and not supplied_review:
                continue
            definition = next(d for d in graph['document_catalog'] if d['document_type'] == document['document_type'])
            review = {'artifact_id': source['artifact_id'], 'file_name': source['file_name'], 'media_type': source['media_type'],
                      'sha256': source['sha256'], 'source_quote': document['citations'][0]['quote'] if document['citations'] else '',
                      'review': document['assessment'], 'reviewed_by': 'independent_machine_verification',
                      'note': document['summary'], 'citations': document['citations'],
                      'document_definition_sha256': _document_definition_sha256(definition)}
            definition['held_files'] = [d for d in definition['held_files'] if d['artifact_id'] != source['artifact_id']] + [review]
            sufficient = [item for item in definition['held_files'] if item['review'] == 'sufficient']
            for fact in graph['assessment_context']['facts']:
                if fact['fact_id'] == f"fact:{document['document_type']}":
                    fact.update(status='established' if sufficient else 'insufficient',
                                summary=sufficient[0]['note'] if sufficient else document['summary'],
                                citations=[c for item in sufficient for c in item['citations']] if sufficient else document['citations'])
            graph['revision'] += 1
            graph = seal_graph(graph)
            result = {'action_id': f"review:{document['document_type']}:{source['artifact_id']}", 'type': 'document_review',
                      'document_type': document['document_type'], 'node_ids': route['required_at_node_ids'],
                      'capability_id': 'local_evidence.assess', 'status': 'completed', 'summary': document['summary'],
                      'assessment': document['assessment'], 'citations': document['citations']}
            if review_policy is not None:
                result.update(review_scope='supplied_file_assessment', route_activation_at_review=route['activation'])
            self._once(claim_id, f"{workflow}.document.{document['document_type']}.{source['artifact_id']}", 'action.completed', lambda s: {
                'graph': graph, 'result': result, 'receipt': receipt(s, 'record_verified_document_review', **base_receipt,
                                                                 after_graph_sha256=graph['graph_sha256'])})

    def _steps(self, claim_id, workflow, verified, base_receipt):
        findings = {row['node_id']: row for row in verified['steps']}
        # These steps require real external capability or specific legal/time
        # computation. A generated paragraph cannot establish their completion.
        for _ in range(100):
            state = self.store.get(claim_id)
            view = evaluate(state['graph'])
            ready = next((node for node in view['nodes'] if node['execution_state'] == 'ready'
                          and not node['missing_document_types'] and execution_capability(node['node_id'])['authorized']
                          and findings.get(node['node_id'], {}).get('status') == 'established'), None)
            if ready is None:
                return
            finding = findings[ready['node_id']]
            graph = deepcopy(state['graph'])
            next(n for n in graph['nodes'] if n['node_id'] == ready['node_id'])['completed'] = True
            graph['revision'] += 1
            graph = seal_graph(graph)
            if evaluate(graph)['inconsistent_completed_node_ids']:
                raise ValueError('autonomous action fails causal prerequisites')
            result = {'action_id': f"assessment:{ready['node_id']}", 'type': 'assessment_record', 'node_id': ready['node_id'],
                      'capability_id': 'local_assessment.record', 'status': 'completed', 'summary': finding['summary'],
                      'citations': finding['citations']}
            self._once(claim_id, f"{workflow}.step.{ready['node_id']}", 'action.completed', lambda s: {
                'graph': graph, 'result': result, 'receipt': receipt(s, 'record_verified_internal_assessment', **base_receipt,
                                                                 after_graph_sha256=graph['graph_sha256'])})
        raise ValueError('autonomous process exceeded its acyclic step bound')

    def _outcome(self, claim_id, workflow, verified, base_receipt):
        state = self.store.get(claim_id)
        view = state['evaluation']
        gaps = [{'document_type': d['document_type'], 'label': d['label'], 'reason': d['reason'],
                 'node_ids': d['required_at_node_ids'], 'review_state': d['review_state']}
                for d in view['documents'] if d['activation'] == 'true' and d['requirement_class'] != 'optional'
                and d['review_state'] != 'sufficient']
        unresolved = [{'fact_id': f"condition:{flag}", 'summary': value['summary']} for flag, value in state['graph']['conditions'].items()
                      if value['verdict'] == 'unresolved']
        outcome = {'status': 'deferred', 'title': 'Evidence assessment complete; claim deferred',
                   'summary': verified['category']['summary'], 'missing_evidence': gaps, 'unresolved_facts': unresolved,
                   'issues': verified['verifier_issues'], 'authority_limits': list(dict.fromkeys(
                       EXTERNAL_CAPABILITIES[n['node_id']] for n in view['nodes']
                       if n['activation'] == 'true' and n['node_id'] in EXTERNAL_CAPABILITIES)),
                   'next_action': 'Await the named evidence or an authorized external action. New supporting files trigger reassessment.',
                   'citations': verified['category']['citations'], 'request_draft': {
                       'status': 'prepared_not_sent', 'subject': 'Evidence needed for the active claim process',
                       'body': '\n'.join(f"- {d['label']}: {d['reason']}" for d in gaps) or 'No additional active document gap was identified.'}}
        self._once(claim_id, f'{workflow}.outcome', 'outcome.recorded', lambda s: {
            'outcome': outcome, 'receipt': receipt(s, 'record_justified_deferral', **base_receipt,
                                                  graph_sha256=state['graph']['graph_sha256'])})

    def _learn(self, claim_id, workflow):
        state = self.store.get(claim_id)
        if not state.get('outcome') or state['graph']['family'] == 'incoming_packet':
            return
        previous = self.knowledge.latest(state['graph']['family'])
        accepted = next((r['receipt'] for r in reversed(state.get('receipts', [])) if r['kind'] == 'interpretation.accepted'
                         and r['receipt'].get('workflow_id') == workflow), None)
        if accepted is None:
            return
        for index, rejected in enumerate(accepted.get('knowledge_rejections', [])):
            self._once(claim_id, f'{workflow}.knowledge-rejection.{index}', 'knowledge.published', {'knowledge': {
                'knowledge_id': f'quarantine.{workflow}.{index}', 'qualification': {'status': 'quarantined', 'reason': rejected['reason']},
                'candidate': rejected['candidate'], 'source_claim_id': claim_id, 'source_state_sha256': state['state_sha256']}})
        try:
            knowledge = qualify(self.policy, state, candidates=accepted.get('knowledge_candidates', []), previous=previous)
            if knowledge is None:
                return
            knowledge['knowledge_sha256'] = digest_value(knowledge)
        except ValueError as error:
            knowledge = {'knowledge_id': 'quarantine.' + workflow, 'qualification': {'status': 'quarantined', 'reason': str(error)},
                         'source_claim_id': claim_id, 'source_state_sha256': state['state_sha256']}
        self._once(claim_id, f'{workflow}.knowledge', 'knowledge.published', {'knowledge': knowledge})
