"""One bounded work executor; the original CasePath services remain state authority."""
from concurrent.futures import ThreadPoolExecutor
from threading import RLock
from pathlib import Path
import sqlite3
import time
from .authority import ExistingCasePathAuthority, AuthorityError
from .contracts import digest, Role, ROLE_ORDER, ROLE_LABELS, VERSION, tool_definitions
from .store import WorkStore, ConflictError, WorkStoreError
from .runtime import AgentWorkExecutor
from .projection import summarize


class AgentWorkService:
    def __init__(self, store: WorkStore, authority, *, facts_worker=None, max_external_runs=1, max_queued=20, external_configuration_status=None):
        self.store,self.authority,self.facts_worker=store,authority,facts_worker
        self.max_external_runs,self.max_queued=max_external_runs,max_queued
        self.external_configuration_status=external_configuration_status or ("ready" if facts_worker else "disabled")
        self._executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='casepath-work')
        self._lock=RLock(); self._jobs={}
        # Cost reservations survive process restart. A new request cannot reset
        # the explicitly small model integration proof's run budget.
        with self.store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS work_external_permits(run_id TEXT PRIMARY KEY REFERENCES work_runs(run_id))')

    def capabilities(self):
        return {'contract':VERSION,'roles':[{'id':r.value,'label':ROLE_LABELS[r],'tools':tool_definitions(r)} for r in ROLE_ORDER],
                'facts_workers':['reference']+(['external_facts'] if self.facts_worker else []),
                'external':self.facts_worker.config.public() if self.facts_worker else None,
                'external_configuration_status':self.external_configuration_status,
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
        self._jobs[run_id]=self._executor.submit(runner.execute,run_id)

    def resume(self,claim_id,run_id):
        with self._lock:
            run=self._scoped(claim_id,run_id)
            self.store.mark_expired_interrupted()
            run=self._scoped(claim_id,run_id)
            if run['status'] not in ('queued','interrupted'):raise ConflictError('this work is not safely resumable')
            if self.store.pending_calls(run_id):raise ConflictError('an unfinished effect or provider request needs reconciliation; it will not be resent')
            if run['request']['facts_worker']=='external_facts' and any(e['operation']=='PROVIDER_REQUEST_STARTED' for e in self.store.events(run_id)):
                raise ConflictError('external inference is not automatically retried')
            self._submit(run_id)
        return self.run(claim_id,run_id)

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
        return {'contract':VERSION,'summary':summary,'objects':objects}

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
            return {'can_resume':False,'reason':'pending_operation'}
        if run['request'].get('facts_worker')=='external_facts' and any(
                e['operation']=='PROVIDER_REQUEST_STARTED' for e in snapshot['events']):
            return {'can_resume':False,'reason':'provider_attempt_recorded'}
        expired = run['status']=='running' and (run.get('lease_until') or 0)<=time.time()
        eligible = run['status'] in ('queued','interrupted') or expired
        return {'can_resume':eligible,'reason':'safe_checkpoint' if eligible else 'not_resumable'}

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
