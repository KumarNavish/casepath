"""Product binding to the SAME guarded inference and planning path as the study.

This adapter does not mutate the existing claim authority, admit evidence, send
customer requests, or fabricate six-role completion. It publishes the preserved
full planning object and its explicitly lossy native projection.
"""
from __future__ import annotations
from threading import RLock
from .wire import digest,load,Invalid
from .schedule import implementation_identity


class ProductPlanService:
    def __init__(self,runner):
        self.runner=runner;self.lock=RLock()
        self.cases={c['case_id']:c for c in runner.cases}
    def plan(self,case_id:str,*,expected_visible_sha256:str,expected_plan_id:str)->dict:
        with self.lock:
            if expected_plan_id!=self.runner.plan['plan_id'] or self.runner.plan['bindings']['code_identity']!=implementation_identity():
                raise Invalid('stale method/source/request plan')
            case=self.cases.get(case_id)
            if case is None or case['visible_sha256']!=expected_visible_sha256:
                raise Invalid('case context changed or lies outside the admitted study')
            if self.runner.preparation is None:
                raise Invalid('no source-only preparation is bound; product does not create it implicitly')
            path=self.runner.output/'cells'/(digest(case_id+':CASEPATH_CONTROL')+'.json')
            if path.is_file():
                record=load(path)
                if record.get('plan_id')!=expected_plan_id:
                    raise Invalid('retained output belongs to another study')
                return {'record':record,'same_request_replay':True,'new_provider_calls':0}
            record=self.runner.run_cell(case,'CASEPATH_CONTROL')
            return {'record':record,'same_request_replay':False,
                    'claim_authority_mutated':False,'customer_request_sent':False,
                    'six_role_workflow_claimed':False}


def create_router(service_getter):
    """Existing app may mount explicitly; no configuration or inference on import."""
    from fastapi import APIRouter,HTTPException
    from pydantic import BaseModel,ConfigDict,Field
    class PlanRequest(BaseModel):
        model_config=ConfigDict(extra='forbid')
        case_id:str=Field(min_length=1,max_length=256)
        expected_visible_sha256:str=Field(pattern='^[0-9a-f]{64}$')
        expected_plan_id:str=Field(pattern='^[0-9a-f]{64}$')
    router=APIRouter(prefix='/api/obligation-control',tags=['obligation-control'])
    # A concrete signature avoids postponed-local-annotation resolution in FastAPI.
    def endpoint(req):
        try:
            return service_getter().plan(req.case_id,expected_visible_sha256=req.expected_visible_sha256,
                                        expected_plan_id=req.expected_plan_id)
        except Invalid as exc:
            raise HTTPException(status_code=409,detail=str(exc)) from None
    endpoint.__annotations__={'req':PlanRequest}
    router.add_api_route('/plan',endpoint,methods=['POST'])
    return router
