"""Explicit, synchronous application of a fully completed saved semantic pair.

This path has no provider dispatch, catalogue refresh, retry queue or send flag.
The original failure remains active until the matching deterministic completion.
"""
from contextlib import contextmanager
from copy import deepcopy

from .autonomous_controller_v1 import AutonomousController, SupersededWorkflow
from .autonomous_model_v1 import SavedAutonomousResultsV1
from .autonomous_policy_v1 import (
    POLICY_ID, INTERPRET_SCHEMA, VERIFY_SCHEMA, compile_verification_proposal,
    validate_interpretation,
)
from .autonomous_store_v1 import AutonomousStoreError, _identifier, _text
from .agent_work.store import WorkStoreError
from .workspace_corpus import digest_value


@contextmanager
def _explicit_ownership(controller):
    lease = getattr(controller, '_hosted_lease', None)
    if lease is None:
        yield
        return
    from .hosted_lease_v1 import _CURRENT_OWNER, HostedOwnershipLost
    nested = _CURRENT_OWNER.get()
    if nested is not None:
        if nested.lease is not lease:
            raise AutonomousStoreError('reconciliation belongs to another hosted lease')
        yield
        return
    token = reset = None
    try:
        token = lease.acquire()
        if token is None:
            raise AutonomousStoreError('hosted workflow ownership is busy; no reconciliation was queued')
        reset = _CURRENT_OWNER.set(token)
        yield
    except HostedOwnershipLost:
        raise AutonomousStoreError('hosted reconciliation ownership was not confirmed; no retry was queued') from None
    finally:
        if reset is not None:
            _CURRENT_OWNER.reset(reset)
        if token is not None:
            lease.release(token)


def _workflow_identity(controller, state, saved_identity):
    source_identity = digest_value(state['source_descriptors'])
    workflow = 'autonomy.' + digest_value({'claim': state['claim_id'], 'sources': source_identity,
        'policy': POLICY_ID, 'rules': digest_value(controller.policy)})[:24]
    identity = {'workflow_id': workflow, 'claim_id': state['claim_id'], 'policy_id': POLICY_ID,
                'source_roster_sha256': source_identity, 'rule_set_sha256': digest_value(controller.policy)}
    binding = state.get('original_binding', {})
    binding_fields = {'original_binding_sha256', 'claim_binding_sha256', 'corpus_manifest_sha256'}
    for key in set(saved_identity) - set(identity):
        if key not in binding_fields or saved_identity[key] != binding.get(key):
            raise AutonomousStoreError('saved workflow admitted binding differs from the claim')
        identity[key] = binding[key]
    if state.get('run_id') != workflow or identity != saved_identity:
        raise AutonomousStoreError('saved workflow identity differs from the current sources or rules')
    return identity


def _preflight(controller, work_store, state):
    if (state.get('deferral') or {}).get('code') != 'verification_deferred':
        raise AutonomousStoreError('only a verification-deferred claim can reconcile completed saved results')
    workflow = state.get('run_id')
    context = state.get('semantic_contexts', {}).get(workflow)
    if not isinstance(context, dict):
        raise AutonomousStoreError('the failed workflow has no frozen semantic context')
    try:
        saved = work_store.saved_completed_autonomous_workflow(workflow)
    except WorkStoreError as error:
        raise AutonomousStoreError(str(error)) from error
    identity = _workflow_identity(controller, state, saved['record']['identity'])
    source_fields = ('artifact_id', 'file_name', 'media_type', 'role', 'sha256', 'text', 'complete', 'coverage')
    sources = [{key: source[key] for key in source_fields} for source in state['acquired_sources']]
    rule_packs = [{'family': t['domain'], 'template_id': t['template_id'], 'title': t['title'],
                   'content': t['content'], 'template_sha256': digest_value(t),
                   'process_catalog': {kind: [{k: v for k, v in row.items() if k != 'assertion'} for row in rows]
                                       for kind, rows in t['process_catalog'].items()}}
                  for t in controller.policy['templates']]
    if (context.get('claim_id') != state['claim_id'] or context.get('policy_id') != POLICY_ID
            or context.get('title') != state['title'] or context.get('sources') != sources
            or context.get('rule_packs') != rule_packs
            or {s['artifact_id'] for s in state['acquired_sources']}
               != {s['artifact_id'] for s in state['source_descriptors']}):
        raise AutonomousStoreError('frozen semantic context differs from exact current sources or rules')
    results = SavedAutonomousResultsV1(saved, context=context, identity=identity,
                                     schemas={'interpret': INTERPRET_SCHEMA, 'verify': VERIFY_SCHEMA})
    verification_proposal, compilation = compile_verification_proposal(context, results.proposal['result'])
    verified = validate_interpretation(controller.policy, state['acquired_sources'],
                                       verification_proposal, results.verifier['result'])
    return context, results, verified, compilation


class _SavedExecution(AutonomousController):
    """Command-local deterministic writer. No model, executor or scheduler exists."""
    def __init__(self, controller, state, admission):
        self.store, self.policy, self.knowledge = controller.store, controller.policy, controller.knowledge
        self._lock = controller._lock
        self._contexts = {state['run_id']: digest_value(state['source_descriptors'])}
        self._failure = deepcopy(state['deferral'])
        self._admission = admission

    def _current(self, state, workflow):
        super()._current(state, workflow)
        if (state.get('deferral') != self._failure or state.get('run_id') != workflow
                or digest_value(state.get('semantic_contexts', {}).get(workflow)) != self._admission['context_sha256']):
            raise SupersededWorkflow('The failed saved-result workflow changed during reconciliation.')


def reconcile_saved_results(controller, claim_id, *, work_store, expected_revision,
                            expected_state_sha256, idempotency_key, actor, reason):
    _identifier(claim_id, 'claim identity')
    _identifier(idempotency_key, 'reconciliation identity')
    _identifier(idempotency_key + '.completed', 'reconciliation completion identity')
    _identifier(idempotency_key + '.failed', 'reconciliation failure identity')
    _text(actor, 'reconciliation actor', 180)
    _text(reason, 'reconciliation reason')
    if (type(expected_revision) is not int or expected_revision < 1
            or not isinstance(expected_state_sha256, str) or len(expected_state_sha256) != 64
            or set(expected_state_sha256) - set('0123456789abcdef')):
        raise AutonomousStoreError('reconciliation requires an exact failed claim revision and state hash')
    request = {'claim_id': claim_id, 'expected_revision': expected_revision,
               'expected_state_sha256': expected_state_sha256, 'idempotency_key': idempotency_key,
               'actor': actor, 'reason': reason}
    with controller._lock, _explicit_ownership(controller):
        if controller._closed:
            raise AutonomousStoreError('autonomous controller is closed')
        state = controller.store.get(claim_id)  # Validate the full current journal and immutable bytes.
        events = controller.store.events(claim_id)
        prior = next((e for e in events if e['idempotency_key'] == idempotency_key), None)
        if prior is not None:
            if prior['kind'] != 'reconciliation.started' or prior['payload']['request'] != request:
                raise AutonomousStoreError('idempotency key binds different reconciliation input')
            completed = next((e for e in events if e['kind'] == 'reconciliation.completed'
                              and e['payload']['reconciliation_id'] == idempotency_key), None)
            if completed is None:
                raise AutonomousStoreError('saved reconciliation is incomplete or failed; use an explicit new current-head command')
            pinned = controller.store.replay(claim_id, expected_revision)['state']
            _, results, _, _ = _preflight(controller, work_store, pinned)
            if results.admission != prior['payload']['admission']:
                raise AutonomousStoreError('saved reconciliation admission differs from its completed record')
            return controller.store.replay(claim_id, completed['sequence'])['state']
        if state['revision'] != expected_revision or state['state_sha256'] != expected_state_sha256:
            raise AutonomousStoreError('stale claim revision or state hash')
        context, results, verified, compilation = _preflight(controller, work_store, state)
        failure = next((e for e in reversed(events) if e['kind'] == 'work.deferred'), None)
        if failure is None or failure['payload'] != state['deferral']:
            raise AutonomousStoreError('the active original failure has no matching journal event')
        payload = {'reconciliation_id': idempotency_key, 'request': request,
                   'original_deferral': state['deferral'], 'failure_event_sha256': failure['event_sha256'],
                   'admission': results.admission}
        controller.store.append(claim_id, 'reconciliation.started', payload,
            expected_revision=expected_revision, expected_state_sha256=expected_state_sha256,
            idempotency_key=idempotency_key)
        execution = _SavedExecution(controller, state, results.admission)
        try:
            execution._apply_verified(claim_id, state['run_id'], context, results.proposal, results.verifier,
                                      verified, compilation)
            current = controller.store.get(claim_id)
            execution._current(current, state['run_id'])
            return controller.store.append(claim_id, 'reconciliation.completed',
                {'reconciliation_id': idempotency_key, 'admission_sha256': results.admission['admission_sha256']},
                expected_revision=current['revision'], expected_state_sha256=current['state_sha256'],
                idempotency_key=idempotency_key + '.completed')
        except Exception as error:
            current = controller.store.get(claim_id)
            # A pause or new source owns its own head; never clear or overwrite it.
            if current.get('deferral') == state['deferral'] and current.get('run_id') == state['run_id']:
                controller.store.append(claim_id, 'reconciliation.failed',
                    {'reconciliation_id': idempotency_key, 'admission_sha256': results.admission['admission_sha256'],
                     'reason': str(error)[:1000] if isinstance(error, (ValueError, SupersededWorkflow))
                               else 'Saved-result application stopped before deterministic completion.'},
                    expected_revision=current['revision'], expected_state_sha256=current['state_sha256'],
                    idempotency_key=idempotency_key + '.failed')
            raise AutonomousStoreError('saved-result reconciliation did not complete; the original failure remains recorded') from error
