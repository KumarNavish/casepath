"""Compact response adapters on the existing guarded executor/journal/product seam.

No standalone paid entry point. Canonical authorizer, whole-study reservation,
phase freeze, provider identity, token/price attestation and secret supplier are
inherited requirements. Frozen targets/evaluators are never imported.
"""
from __future__ import annotations
from ..adapters import StudyRunner,observation
from ..transport import BoundExecutor
from ..wire import canonical,decode,digest,load,save,Invalid
from .schedule import render_request,normalized_response
from .preparation import compile_public
from .codec import Book


class CompactExecutor(BoundExecutor):
    def render(self,slot_id,parents):
        return render_request(self.plan,slot_id,parents)


class CompactRunner(StudyRunner):
    def prepare(self):
        binding=compile_public(self.sources)
        if binding['manifest']!=self.plan['bindings']['preparation_manifest']:
            raise Invalid('compiled public preparation changed since freeze')
        self.preparation={**binding,'source_identity':self.sources['identity'],'origin':'compiled_public_templates'}
        save(self.output/'source_pack'/'PREPARATION.json',{'manifest':binding['manifest'],'prepared':binding['prepared']})
        return self.preparation

    def route_checks(self):
        """Explicit, already-reserved external route checks; never implicit in prepare."""
        for i in range(self.plan['bindings']['config']['route_validation_requests']):
            slot='prep:route:'+str(i)
            raw,receipt=self._call(slot)
            body=decode(raw)
            if body!={'answer':{'route_check':True},'notes':''}:raise Invalid('route-check response malformed')
            save(self.output/'route_checks'/(str(i)+'.json'),{'slot':slot,'receipt_sha256':receipt,'origin':self.origin})
        # Effective parameters remain the canonical authorizer's responsibility;
        # returned literal text cannot attest server decoding settings.

    def run_cell(self,case,arm):
        if self.preparation is None:raise Invalid('public preparation not bound')
        if arm not in self.plan['bindings']['config']['arms']:raise Invalid('unknown comparison arm')
        key=case['case_id']+':'+arm;path=self.output/'cells'/(digest(key)+'.json')
        if path.is_file():
            record=load(path)
            if record.get('plan_id')!=self.plan['plan_id'] or record.get('origin')!=self.origin:raise Invalid('retained cell from another run')
            return record
        try:
            config=self.plan['bindings']['config'];book=Book(self.preparation,case,self.native)
            for stage in range(2):
                slot=key+':'+str(stage);raw,receipt=self._call(slot)
                self.parent_raw[slot]=raw
                normalized=normalized_response(raw,config,stage=stage)
                save(self.output/'decoded_stages'/(digest(slot)+'.json'),{'wire':decode(normalized),'receipt_sha256':receipt,'codebook_identity':book.identity,'origin':self.origin})
            answer=decode(normalized)['answer']
            if arm=='CASEPATH_CONTROL':
                obs=observation(book.decode_state(answer),case,self.preparation['prepared'],receipt,self.origin)
                result=self.preparation['runtime'].run(obs)
                result['native_artifact']=self.native.validate(result['native_artifact']);result['observation']=obs
            else:
                result={'native_artifact':book.decode_native(answer),'planning':None,
                  'planning_unavailable_reason':'native projection comparator, not full control-route state','inference_receipt_sha256':receipt}
            record={'case_id':case['case_id'],'arm':arm,'state':'completed','origin':self.origin,'plan_id':self.plan['plan_id'],
              'result':result,'codebook_identity':book.identity,'scoring_performed':False,'preparation_origin':'compiled_public_templates_not_induction'}
        except (ValueError,KeyError,TypeError,IndexError) as exc:
            record={'case_id':case['case_id'],'arm':arm,'state':'failed','origin':self.origin,'plan_id':self.plan['plan_id'],
              'error_type':type(exc).__name__,'error':str(exc),'candidate':None,'scoring_performed':False,
              'failure_policy':'original native worst-score policy; raw adverse outputs retained, no retry'}
        save(path,record);return record

    def run_all(self,*,split=None):
        if self.origin!='engineering_fixture':
            for i in range(self.plan['bindings']['config']['route_validation_requests']):
                p=self.output/'route_checks'/(str(i)+'.json')
                if not p.is_file():raise Invalid('reserved route verification not collected')
        return super().run_all(split=split)
