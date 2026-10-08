"""One bounded work executor; the original CasePath services remain state authority."""
from concurrent.futures import ThreadPoolExecutor
from threading import RLock
from pathlib import Path
import sqlite3
import time
from .authority import ExistingCasePathAuthority, AuthorityError
from .contracts import digest, Role, ROLE_ORDER, ROLE_LABELS, VERSION, tool_definitions, ObjectProposal
from .store import WorkStore, ConflictError, WorkStoreError
from .runtime import AgentWorkExecutor, ToolRuntime
from .projection import summarize


class AgentWorkService:
    def __init__(self, store: WorkStore, authority, *, facts_worker=None, max_external_runs=1, max_queued=20, external_configuration_status=None):
        self.store,self.authority,self.facts_worker=store,authority,facts_worker
        self.max_external_runs,self.max_queued=max_external_runs,max_queued
        self.external_configuration_status=external_configuration_status or ("ready" if facts_worker else "disabled")
        self._executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='casepath-work')
        self._lock=RLock(); self._jobs={}
        self.reference_completion=None
        self.external_completion=None
        self.external_start_guard=None
        self.reference_finished=None
        # Cost reservations survive process restart. A new request cannot reset
        # the explicitly small model integration proof's run budget.
        with self.store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS work_external_permits(run_id TEXT PRIMARY KEY REFERENCES work_runs(run_id))')

    def capabilities(self):
        return {'contract':VERSION,'roles':[{'id':r.value,'label':ROLE_LABELS[r],'tools':tool_definitions(r)} for r in ROLE_ORDER],
                'facts_workers':['reference']+(['external_facts'] if self.facts_worker else []),
                'external':self.facts_worker.config.public() if self.facts_worker else None,
                'external_configuration_status':self.external_configuration_status,
                'external_budget':self.store.external_budget(),
                'authority':'existing_casepath','automatic_inference_retry':False,'max_queued':self.max_queued}

    def context(self,claim_id):
        value=self.authority.context(claim_id)
        return {'contract':VERSION,'context':value,'context_sha256':digest(value)}

    def start(self,claim_id,*,idempotency_key,expected_context_sha256,facts_worker='reference',dispatch=True):
        if facts_worker not in ('reference','external_facts'):
            raise WorkStoreError('unknown facts worker')
        with self._lock:
            # Return an exact prior request before requiring unchanged context:
            # the successful prior work may itself have advanced setup.
            previous=self.store.find_request(claim_id,idempotency_key)
            if previous:
                if previous['request'].get('requested_context_sha256')!=expected_context_sha256 or previous['request']['facts_worker']!=facts_worker:
                    raise ConflictError('the idempotency key binds a different work request')
                return self.run(claim_id,previous['run_id'])
            if facts_worker=='external_facts' and self.facts_worker is None:
                raise WorkStoreError('external facts are not configured; no model call was made')
            context=self.authority.context(claim_id)
            if digest(context)!=expected_context_sha256:raise ConflictError('claim context changed; refresh before starting work')
            if facts_worker=='external_facts' and self.external_start_guard is not None:
                self.external_start_guard(claim_id,context)
            worker_config=self.facts_worker.config.public() if facts_worker=='external_facts' else None
            run,created=self.store.create(claim_id,idempotency_key,{'context':context,'requested_context_sha256':expected_context_sha256,'facts_worker':facts_worker,'worker_config':worker_config,'worker_config_sha256':digest(worker_config) if worker_config else None},
                                          external_limit=self.max_external_runs if facts_worker=='external_facts' else None, max_active=self.max_queued)
            if dispatch:self._submit(run['run_id'])
        return self.run(claim_id,run['run_id'])

    def _submit(self,run_id):
        self._jobs={key:job for key,job in self._jobs.items() if not job.done()}
        job=self._jobs.get(run_id)
        if job is not None and not job.done():return
        runner=AgentWorkExecutor(self.store,self.authority,self.facts_worker)
        def execute():
            result=runner.execute(run_id)
            if (result['status']=='completed' and result['request']['facts_worker']=='reference'
                    and self.reference_completion is not None):
                self.reference_completion(result['claim_id'],run_id)
            if (result['status']=='completed' and result['request']['facts_worker']=='external_facts'
                    and self.external_completion is not None):
                self.external_completion(result['claim_id'],run_id)
            if (result['status'] in {'completed','cancelled','blocked','failed','interrupted'}
                    and result['request']['facts_worker']=='reference' and self.reference_finished is not None):
                self.reference_finished(result['claim_id'],run_id)
            return result
        self._jobs[run_id]=self._executor.submit(execute)

    def resume(self,claim_id,run_id):
        with self._lock:
            run=self._scoped(claim_id,run_id)
            self.store.mark_expired_interrupted()
            run=self._scoped(claim_id,run_id)
            if run['status'] not in ('queued','interrupted'):raise ConflictError('this work is not safely resumable')
            if self.store.pending_calls(run_id):raise ConflictError('an unfinished effect or provider request needs reconciliation; it will not be resent')
            if run['request']['facts_worker']=='external_facts' and any(e['operation']=='PROVIDER_REQUEST_STARTED' for e in self.store.events(run_id)):
                raise ConflictError('external inference is not automatically retried')
            self.store.clear_pause(run_id)
            self._submit(run_id)
        return self.run(claim_id,run_id)

    def reconcile_process_node(self, claim_id, run_id, *, call_id, object_id,
                               expected_last_event_sha256, expected_work_state_sha256,
                               actor, reason, check_only=False, verify_parent=None):
        """Reconstruct one proven local node buffer, without executing its call again."""
        command = dict(call_id=call_id, object_id=object_id,
                       expected_last_event_sha256=expected_last_event_sha256,
                       expected_work_state_sha256=expected_work_state_sha256, actor=actor, reason=reason)
        if not actor.strip() or not reason.strip():
            raise ConflictError('a handler and reconciliation reason are required')
        with self._lock:
            self._scoped(claim_id, run_id)
            snapshot = self.store.snapshot(run_id)
            prior = self.store.reconciliation_receipt(snapshot['events'], command)
            if prior:
                return {'event_sha256': prior['event_sha256'], 'replayed': True, 'reconciled': True, 'claim_state_changed': False}
            job = self._jobs.get(run_id)
            if job is not None and not job.done():
                raise ConflictError('this review is still scheduled in the current executor')
            candidate = self._node_reconciliation(snapshot)
            if candidate is None or any(candidate[key] != command[key] for key in (
                    'call_id', 'object_id', 'expected_last_event_sha256', 'expected_work_state_sha256')):
                raise ConflictError('the saved checkpoint does not match this local proposal')
            context = snapshot['run']['request']['context']
            def verify_authority():
                identity = self.authority.packet_identity(claim_id)
                if any(identity[key] != context[key] for key in ('binding_sha256', 'source_roster_sha256')):
                    raise ConflictError('the source packet changed; this proposal cannot be reconstructed')
                if self.authority.snapshot(claim_id)['state_sha256'] != expected_work_state_sha256:
                    raise ConflictError('the claim changed; this proposal cannot be reconstructed')
                if verify_parent is not None:
                    verify_parent()
            verify_authority()
            runtime = ToolRuntime(self.store, self.authority, run_id, '', Role.PROCESS, 'reference')
            output = runtime._tool_propose_process_node(ObjectProposal(object_id=object_id))
            if check_only:
                return {'checked': True, 'claim_state_changed': False}
            return self.store.reconcile_process_node(run_id, command,
                {'ok': True, 'tool': 'propose_process_node', 'result': output},
                runtime.emitted, runtime.changed, verify_authority)

    def pause(self,claim_id,run_id):
        with self._lock:
            self._scoped(claim_id,run_id)
            self.store.request_pause(run_id)
        return self.run(claim_id,run_id)

    def cancel(self,claim_id,run_id):
        with self._lock:
            self._scoped(claim_id,run_id)
            self.store.request_cancel(run_id)
            job=self._jobs.get(run_id)
            if job is not None:
                job.cancel()
        return self.run(claim_id,run_id)

    def supersede_reference(self,claim_id,run_id,accepted_process_event_sha256):
        """Keep an obsolete local executor alive until its safe cancellation checkpoint."""
        with self._lock:
            self._scoped(claim_id,run_id)
            snapshot=self.store.snapshot(run_id)  # Validate history before adding a stop receipt.
            if snapshot['run']['request']['facts_worker']!='reference':
                raise ConflictError('external work requires manual reconciliation')
            terminal={'completed','cancelled','blocked','failed'}
            if snapshot['run']['status'] in terminal:
                return snapshot
            try:
                self.store.request_cancel(run_id,
                    message='A newer accepted process edit superseded this reference review; stop at its next safe checkpoint',
                    after={'accepted_process_event_sha256':accepted_process_event_sha256})
            except ConflictError:
                # Finish commits without the service lock. Only a validated
                # terminal receipt reconciles that race; preserve other errors.
                snapshot=self.store.snapshot(run_id)
                if snapshot['run']['status'] in terminal and not snapshot['pending_calls']:
                    return snapshot
                raise
        # Do not cancel the Future: queued work must still reach the terminal
        # callback, and the immutable store controls cancellation and leases.
        return self.store.snapshot(run_id)

    def _scoped(self,claim_id,run_id):
        value=self.store.get_run(run_id)
        if value['claim_id']!=claim_id:raise WorkStoreError('work run is outside this claim')
        return value

    def run(self,claim_id,run_id):
        run=self._scoped(claim_id,run_id)
        snapshot=self.store.snapshot(run_id)
        summary=summarize(self.store,run,snapshot)
        summary['recovery']=self.recovery(snapshot)
        job=self._jobs.get(run_id)
        if job is not None and not job.done() and summary['recovery']['can_resume']:
            summary['recovery']={'can_resume':False,'reason':'scheduled_here'}
        objects=snapshot['objects']
        summary['currentness']=self._currentness(run,objects)
        result={'contract':VERSION,'summary':summary,'objects':objects}
        return {**result,'response_sha256':digest(result)}

    def _currentness(self,run,objects):
        saved=next((o['value'] for o in objects if o['kind']=='authority_snapshot'),None)
        if saved is None:
            return 'not_yet_checked'
        try:
            original=run['request']['context']
            context=self.authority.context(run['claim_id'])
            if any(context[key]!=original[key] for key in ('binding_sha256','source_roster_sha256')):
                return 'historical'
            current=self.authority.snapshot(run['claim_id'])
            return 'current' if current['state_sha256']==saved['state_sha256'] else 'historical'
        except (AuthorityError,ValueError,KeyError):
            return 'unconfirmed'

    def events(self,claim_id,run_id,after=0,limit=200):
        self._scoped(claim_id,run_id)
        events=self.store.events(run_id,after,limit)
        return {'contract':VERSION,'run_id':run_id,'claim_id':claim_id,'events':events,
                'next_after':events[-1]['sequence'] if events else after}

    @staticmethod
    def recovery(snapshot):
        """Read-only recovery classification; never resolves an unknown effect by guessing."""
        run = snapshot['run']
        if snapshot['pending_calls']:
            result = {'can_resume':False,'reason':'pending_operation'}
            candidate = AgentWorkService._node_reconciliation(snapshot)
            if candidate is not None:
                result['reconciliation'] = candidate
            return result
        if run['request'].get('facts_worker')=='external_facts' and any(
                e['operation']=='PROVIDER_REQUEST_STARTED' for e in snapshot['events']):
            return {'can_resume':False,'reason':'provider_attempt_recorded'}
        expired = run['status']=='running' and (run.get('lease_until') or 0)<=time.time()
        eligible = run['status'] in ('queued','interrupted') or expired
        return {'can_resume':eligible,'reason':'safe_checkpoint' if eligible else 'not_resumable'}

    @staticmethod
    def _node_reconciliation(snapshot):
        run, pending, events = snapshot['run'], snapshot['pending_calls'], snapshot['events']
        if (run['request'].get('facts_worker') != 'reference' or len(pending) != 1
                or run['status'] not in {'running', 'interrupted', 'blocked'}
                or (run.get('lease_until') or 0) > time.time()
                or any(e['operation'].startswith('PROVIDER_') or e['operation'] == 'RUN_CANCEL_REQUESTED' for e in events)):
            return None
        call = pending[0]
        if (call['role'] != Role.PROCESS.value or call['tool_name'] != 'propose_process_node'
                or not call['call_id'].startswith('reference.process_decision_mapping.')):
            return None
        objects = snapshot['objects']
        if any(o['id'] == 'complete:' + Role.PROCESS.value for o in objects):
            return None
        saved = next((o['value'] for o in objects if o['id'] == 'authority_snapshot' and o['kind'] == 'authority_snapshot'), None)
        if saved is None:
            return None
        matches = [node for node in saved.get('process', {}).get('nodes', [])
                   if digest({'tool': 'propose_process_node', 'arguments': {'object_id': node['node_id']}}) == call.get('request_sha256')]
        if len(matches) != 1 or any(o['id'] == 'node:' + matches[0]['node_id'] for o in objects):
            return None
        node = matches[0]
        return {'kind': 'process_node', 'run_id': run['run_id'], 'call_id': call['call_id'],
                'object_id': node['node_id'], 'title': node.get('title') or node.get('label') or node['node_id'],
                'expected_last_event_sha256': events[-1]['event_sha256'],
                'expected_work_state_sha256': saved['state_sha256']}

    def workforce(self,claim_id=None):
        if claim_id is None:
            runs,coverage=self.store.latest_claim_runs(150)
        else:
            runs=self.store.list_runs(claim_id,150)
            coverage={'kind':'claim_history','returned_runs':len(runs),'has_more':len(runs)==150}
        summaries=[]
        for run in runs:
            summaries.append({
                'run_id':run['run_id'],'claim_id':run['claim_id'],
                'subject':run['request']['context'].get('subject','Claim'),
                'status':run['status'],'created_at':run['created_at'],
                'facts_worker':run['request']['facts_worker'],
                'currentness':'not_yet_checked',
            })
        return {'contract':VERSION,'runs':summaries,
                'roles':[{'id':r.value,'label':ROLE_LABELS[r]} for r in ROLE_ORDER],
                'limit':150,'coverage':coverage,'includes_invented_activity':False}

    def shutdown(self):
        self._executor.shutdown(wait=True,cancel_futures=False)
        self.store.close()
