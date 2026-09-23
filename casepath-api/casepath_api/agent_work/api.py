"""Browser API exposes work requests and read projections, not arbitrary tools."""
import asyncio
import json
from typing import Literal
from urllib.parse import urlsplit
from fastapi import APIRouter,Request,HTTPException,Query
from fastapi.responses import StreamingResponse
from pydantic import Field
from .contracts import StrictModel
from .store import WorkStoreError,ConflictError
from .authority import AuthorityError

class StartWork(StrictModel):
    idempotency_key:str=Field(min_length=8,max_length=128,pattern=r'^[a-zA-Z0-9_.:-]+$')
    expected_context_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')
    facts_worker:Literal['reference','external_facts']='reference'


def create_agent_work_router(service_getter):
    router=APIRouter(prefix='/api/agent-work/v1')
    def invoke(fn):
        try:return fn(service_getter())
        except ConflictError as exc:raise HTTPException(409,str(exc)) from exc
        except (WorkStoreError,AuthorityError,ValueError) as exc:raise HTTPException(422,str(exc) if isinstance(exc,(WorkStoreError,AuthorityError)) else 'The current authority could not be verified.') from exc
    def guard(request):
        if request.headers.get('X-CasePath-Agent-Work')!='1':raise HTTPException(403,'Explicit same-origin work request required.')
        origin=request.headers.get('origin')
        if origin and (urlsplit(origin).netloc!=request.url.netloc or urlsplit(origin).scheme!=request.url.scheme):raise HTTPException(403,'Cross-origin work requests are not accepted.')
    @router.get('/capabilities')
    def capabilities():return invoke(lambda s:s.capabilities())
    @router.get('/workforce')
    def workforce():return invoke(lambda s:s.workforce())
    @router.get('/claims/{claim_id}/context')
    def context(claim_id:str):return invoke(lambda s:s.context(claim_id))
    @router.get('/claims/{claim_id}/runs')
    def runs(claim_id:str):return invoke(lambda s:s.workforce(claim_id))
    @router.post('/claims/{claim_id}/runs',status_code=202)
    def start(claim_id:str,body:StartWork,request:Request):
        guard(request)
        return invoke(lambda s:s.start(claim_id,**body.model_dump()))
    @router.get('/claims/{claim_id}/runs/{run_id}')
    def get_run(claim_id:str,run_id:str):return invoke(lambda s:s.run(claim_id,run_id))
    @router.get('/claims/{claim_id}/runs/{run_id}/events')
    def events(claim_id:str,run_id:str,after:int=Query(0,ge=0),limit:int=Query(200,ge=1,le=500)):
        return invoke(lambda s:s.events(claim_id,run_id,after,limit))
    @router.get('/claims/{claim_id}/runs/{run_id}/stream')
    async def stream(claim_id:str,run_id:str,request:Request,after:int=Query(0,ge=0)):
        service=service_getter()
        invoke(lambda s:s.events(claim_id,run_id,after,1))
        last=request.headers.get('last-event-id')
        if last is not None:
            if not last.isdecimal():raise HTTPException(422,'Invalid event cursor')
            after=max(after,int(last))

        async def send_events():
            cursor=after
            yield 'retry: 1500\n\n'
            while not await request.is_disconnected():
                try:
                    packet=await asyncio.to_thread(service.events,claim_id,run_id,cursor,500)
                    for event in packet['events']:
                        cursor=event['sequence']
                        yield f"id: {cursor}\nevent: work\ndata: {json.dumps(event,ensure_ascii=False)}\n\n"
                    run=await asyncio.to_thread(service.store.get_run,run_id)
                    if run['status'] in {'completed','blocked','failed'} and not packet['events']:
                        yield 'event: done\ndata: {}\n\n'
                        return
                except (WorkStoreError,ValueError):
                    yield 'event: error\ndata: {"message":"Saved work could not be read"}\n\n'
                    return
                await asyncio.sleep(0.2)
        return StreamingResponse(send_events(),media_type='text/event-stream',headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})
    @router.post('/claims/{claim_id}/runs/{run_id}/resume')
    def resume(claim_id:str,run_id:str,request:Request):
        guard(request)
        return invoke(lambda s:s.resume(claim_id,run_id))
    return router
