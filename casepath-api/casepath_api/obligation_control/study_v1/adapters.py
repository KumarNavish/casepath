"""Preparation, real learned adapters and shared product execution core.

Model I/O is injected from the guarded executor. No fixed/reference prediction is
substituted. The only deterministic comparison rows explicitly share the fresh
CASEPATH_CONTROL assessment. Full plans survive native projection.
"""
from __future__ import annotations
import copy
import importlib.util
from pathlib import Path
import sys
import types
from .wire import decode, digest, immutable, load, save, sha, Invalid
from .preparation import materialize
from ..source_only_runtime_v1 import SourceOnlyRuntime


class NativeBoundary:
    """Only original schema/parser modules; never imports scorers or targets."""
    def __init__(self, root:Path, expected:dict[str,str]):
        root=Path(root)
        if set(expected)!={'schema.py','expressions.py'}:raise Invalid('bind both native schema and parser')
        for name,checksum in expected.items():
            p=root/'contracts'/name
            if p.is_symlink() or sha(p.read_bytes())!=checksum:raise Invalid('native schema/parser identity mismatch')
        namespace='_casepath_native_'+digest(expected)[:16]
        pkg=types.ModuleType(namespace);pkg.__path__=[str(root/'contracts')];sys.modules.setdefault(namespace,pkg)
        name=namespace+'.schema'
        if name not in sys.modules:
            spec=importlib.util.spec_from_file_location(name,root/'contracts/schema.py')
            mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod
            try:spec.loader.exec_module(mod)
            except BaseException:
                sys.modules.pop(name,None);raise
        self.candidate_type=sys.modules[name].CandidateArtifact
        self.identity=digest(expected)
    def validate(self,value:dict)->dict:
        # This validates the response contract only, never evaluates correctness.
        return self.candidate_type.model_validate(value).model_dump(mode='json')


def expand_candidate(value:dict,case:dict,native:NativeBoundary)->dict:
    result=copy.deepcopy(value)
    if result.get('case_id')!='live_case':raise Invalid('model emitted a scheduling/cross-case identity')
    result['case_id']=case['case_id']
    for family in ('concepts','documents','branch_predicates'):
        if not isinstance(result.get(family),list):raise Invalid('native response missing typed array')
        for item in result[family]:
            refs=item.get('provenance',[])
            resolved=[]
            for ref in refs:
                if not isinstance(ref,dict) or set(ref)!={'source_ref'} or ref['source_ref'] not in case['registry']:
                    raise Invalid('invented/unbound source reference')
                resolved.append(copy.deepcopy(case['registry'][ref['source_ref']]['locator']))
            item['provenance']=resolved
    return native.validate(result)


def observation(value:dict,case:dict,prepared:dict,receipt_sha:str,origin:str)->dict:
    if set(value)!={'guard_verdicts','evidence'}:raise Invalid('assessment output shape mismatch')
    if set(value['guard_verdicts'])!=set(prepared['control']['variables']):raise Invalid('assessment omitted or introduced variables')
    docs={d for c in prepared['capabilities'] for r in c['routes'] for d in r['document_ids']}
    if set(value['evidence']['documents'])!=docs:raise Invalid('assessment omitted or introduced document states')
    return {'contract':'casepath.observation-state/1.0.0','case_id':case['case_id'],
        'materials':copy.deepcopy(case['visible']['materials']), 'guard_verdicts':copy.deepcopy(value['guard_verdicts']),
        'evidence':copy.deepcopy(value['evidence']), 'origin':origin,
        'inference_receipt_sha256':receipt_sha if origin=='model_execution' else None}


class StudyRunner:
    def __init__(self,plan:dict,sources:dict,cases:list[dict],executor,native:NativeBoundary,output:Path):
        self.plan,self.sources,self.cases,self.executor,self.native,self.output=plan,sources,cases,executor,native,Path(output)
        if sources['identity']!=plan['bindings']['source_identity']:raise Invalid('source identity changed')
        actual=[(c['case_id'],c['visible_sha256'],c['split'],c['family_id'],c['domain']) for c in sorted(cases,key=lambda c:c['case_id'])]
        if [list(x) for x in actual]!=[list(x) for x in plan['bindings']['cohort']]:raise Invalid('case inputs or cohort changed')
        self.parent_raw={};self.preparation=None
    @property
    def origin(self):
        return 'engineering_fixture' if self.executor.transport.origin=='engineering_fixture' else 'model_execution'
    def _call(self,slot):
        prior=self.executor.recover(slot,self.parent_raw)
        return prior if prior is not None else self.executor.call(slot,self.parent_raw)
    def prepare(self)->dict:
        for stage in range(2):
            key='prep:'+str(stage)
            raw,receipt=self._call(key)
            self.parent_raw[key]=raw
            save(self.output/'stages'/(digest(key)+'.json'),{'slot_id':key,'response_sha256':sha(raw),'receipt_sha256':receipt,'origin':self.origin})
        self.preparation=materialize(self.sources,decode(raw),self.output/'source_pack',response_receipt_sha256=receipt,origin=self.origin)
        return self.preparation
    def run_cell(self,case:dict,arm:str)->dict:
        if self.preparation is None:raise Invalid('source-only preparation is incomplete')
        key=case['case_id']+':'+arm
        saved=self.output/'cells'/(digest(key)+'.json')
        if saved.is_file():
            record=load(saved)
            if record.get('plan_id')!=self.plan['plan_id'] or record.get('origin')!=self.origin:
                raise Invalid('cell result belongs to another admitted execution')
            return record
        try:
            for stage in range(2):
                slot=key+':'+str(stage)
                raw,receipt=self._call(slot)
                self.parent_raw[slot]=raw
            value=decode(raw)
            review_trace=None
            if self.plan['bindings']['config'].get('review_delta_enabled'):
                from .review_delta_v1 import apply_review
                value,review_trace=apply_review(self.parent_raw[key+':0'],raw,self.plan['bindings']['config']['case_output_bytes'])
                save(self.output/'expanded_reviews'/(digest(key)+'.json'),{'final':value,'trace':review_trace,'final_provider_receipt_sha256':receipt})
            if arm=='CASEPATH_CONTROL':
                obs=observation(value,case,self.preparation['prepared'],receipt,self.origin)
                result=self.preparation['runtime'].run(obs)
                result['native_artifact']=self.native.validate(result['native_artifact'])
                result['observation']=obs
            else:
                result={'native_artifact':expand_candidate(value,case,self.native),
                        'planning':None,'planning_unavailable_reason':'this comparator emits a native artifact, not the controller proof-route state',
                        'inference_receipt_sha256':receipt}
            record={'case_id':case['case_id'],'arm':arm,'state':'completed','origin':self.origin,
                    'plan_id':self.plan['plan_id'],'result':result,'scoring_performed':False,
                    **({'review_trace':review_trace} if review_trace is not None else {})}
        except (ValueError,KeyError,TypeError) as exc:
            record={'case_id':case['case_id'],'arm':arm,'state':'failed','origin':self.origin,
                    'plan_id':self.plan['plan_id'],'error_type':type(exc).__name__,'error':str(exc),
                    'candidate':None,'failure_policy':'original frozen worst-score policy; no fabricated empty successful artifact',
                    'scoring_performed':False}
        save(self.output/'cells'/(digest(key)+'.json'),record)
        return record
    def deterministic(self,case:dict,arm:str,full:dict)->dict:
        key=case['case_id']+':'+arm
        if full['state']!='completed':
            record={'case_id':case['case_id'],'arm':arm,'state':'blocked_dependency','origin':self.origin,'candidate':None}
        else:
            runtime=self.preparation['runtime'];obs=full['result']['observation']
            if arm=='COMPILED_EQUIVALENT':
                result=runtime.run(obs,execution_mode='compiled')
            elif arm=='LOCAL_SCOPE_ABLATION':
                p=self.preparation['prepared'];graph=copy.deepcopy(p['control'])
                for scope in graph['scopes']:
                    scope['parents']=[];scope['join']='all'
                # Remove only inherited applicability; keep each local guard and
                # all acquisition/adequacy/route rules. This is NOT frozen V5.
                from .preparation import runtime_registry
                result=SourceOnlyRuntime(graph,p['capabilities'],p['native_binding'],runtime_registry(self.sources)).run(obs)
            else:raise Invalid('unknown deterministic comparison')
            result['native_artifact']=self.native.validate(result['native_artifact'])
            record={'case_id':case['case_id'],'arm':arm,'state':'completed','origin':self.origin,
                    'result':result,'plan_id':self.plan['plan_id'],'conditioned_on':case['case_id']+':CASEPATH_CONTROL:1','independent_model_replication':False}
        save(self.output/'cells'/(digest(key)+'.json'),record)
        return record
    def run_all(self, *, split:str | None=None)->list[dict]:
        """Called by canonical managed worker only after complete-study reservation.

        A definitive model/schema failure stays a failed cell; an unknown send or
        charge stops new sends in the Journal until the exact request reconciles.
        """
        if self.origin!='engineering_fixture' and split not in {'public_dev','hidden_test'}:
            raise Invalid('managed execution must name one phase; no automatic development-to-protected transition')
        if split not in {None,'public_dev','hidden_test'}:raise Invalid('unknown phase')
        if split=='hidden_test' and self.origin!='engineering_fixture':
            receipt_path=self.output/'PHASE_public_dev.json'
            if not receipt_path.is_file() or load(receipt_path).get('plan_id')!=self.plan['plan_id']:
                raise Invalid('development phase not collected for this exact method')
        if self.preparation is None:self.prepare()
        records=[]
        selected=[c for c in self.cases if split is None or c['split']==split]
        for case in sorted(selected,key=lambda c:(c['split'] != 'public_dev',c['case_id'])):
            full=None
            for arm in self.plan['case_schedule'][case['case_id']]:
                rec=self.run_cell(case,arm);records.append(rec)
                if arm=='CASEPATH_CONTROL':full=rec
                facts=self.executor.journal.facts(self.plan['plan_id'],include_events=False)
                if any(r['state'] in {'sent','uncertain','cost_unknown','overrun'} for r in facts['requests']):
                    save(self.output/'STOP.json',{'reason':'unreconciled request or charge','at_cell':[case['case_id'],arm],'automatic_retry':False})
                    return records
            for arm in self.plan['bindings']['config']['deterministic_arms']:
                records.append(self.deterministic(case,arm,full))
        if split is not None:
            save(self.output/('PHASE_'+split+'.json'),{'plan_id':self.plan['plan_id'],'split':split,'records':len(records),'origin':self.origin,'scoring_performed':False})
        if split is None:self.export_submissions(records)
        return records
    def export_submissions(self,records:list[dict])->None:
        expected={(r['case_id'],r['arm']) for r in self.plan['matrix']}
        got={(r['case_id'],r['arm']) for r in records}
        if len(records)!=len(got) or got!=expected:raise Invalid('incomplete or duplicate full matrix')
        from .wire import canonical
        submission_dir='engineering_fixture_submissions' if self.origin=='engineering_fixture' else 'submissions'
        for arm in self.plan['bindings']['config']['arms']+self.plan['bindings']['config']['deterministic_arms']:
            selected=sorted((r for r in records if r['arm']==arm),key=lambda r:r['case_id'])
            valid=[{'case_id':r['case_id'],'candidate':r['result']['native_artifact']} for r in selected if r['state']=='completed']
            failed=[{'case_id':r['case_id'],'state':r['state'],'error':r.get('error')} for r in selected if r['state']!='completed']
            immutable(self.output/submission_dir/(arm+'.jsonl'),b''.join(canonical(r)+b'\n' for r in valid))
            save(self.output/submission_dir/(arm+'.failures.json'),failed)
        save(self.output/'EVALUATOR_BOUNDARY.json',{'plan_id':self.plan['plan_id'],'rows':len(records),
           'native_schema_identity':self.native.identity,'targets_read':False,'scoring_performed':False,
           'partial_submission_is_complete_case_sensitivity_only':True,
           'failures_must_receive_original_worst_scores_before_any_population_estimate':True,
           'native_projection_is_lossless':False,'full_planning_objects_retained':'cells/*.json',
           'origin':self.origin,'provider_receipts_retained':True})
