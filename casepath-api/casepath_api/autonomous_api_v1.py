"""Same-origin operational intake and read-only autonomous projections."""
from functools import lru_cache
import os
from urllib.parse import quote, urlsplit

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from .autonomous_controller_v1 import AutonomousController, execution_capability
from .autonomous_policy_v1 import POLICY_ID, INTERPRET_SCHEMA, VERIFY_SCHEMA
from .autonomous_store_v1 import AutonomousStore, AutonomousStoreError
from .workspace_corpus import digest_value


class StrictBody(BaseModel):
    model_config = ConfigDict(extra='forbid')


class IncomingFile(StrictBody):
    file_name: str = Field(min_length=1, max_length=240)
    media_type: str = Field(min_length=1, max_length=120)
    content_base64: str = Field(max_length=12_000_000)


class Intake(StrictBody):
    title: str = Field(min_length=1, max_length=300)
    message: str = Field(min_length=1, max_length=100_000)
    files: list[IncomingFile] = Field(default_factory=list, max_length=20)
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r'^[a-zA-Z0-9_.:-]+$')


class RevisionCommand(StrictBody):
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r'^[a-zA-Z0-9_.:-]+$')
    expected_revision: int = Field(ge=1)
    expected_state_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')


class SourceArrival(RevisionCommand):
    files: list[IncomingFile] = Field(min_length=1, max_length=20)


def create_autonomous_router(service_getter, budget_getter=lambda: None):
    router = APIRouter(prefix='/api/claim-loops/v1/autonomous')

    def invoke(fn):
        try:
            return fn(service_getter())
        except AutonomousStoreError as error:
            raise HTTPException(409, str(error)) from error
        except (ValueError, KeyError):
            raise HTTPException(422, 'The saved autonomous state could not be verified.')

    def guard(request):
        if request.headers.get('X-CasePath-Agent-Work') != '1':
            raise HTTPException(403, 'Explicit same-origin work request required.')
        origin = request.headers.get('origin')
        if origin and (urlsplit(origin).netloc != request.url.netloc or urlsplit(origin).scheme != request.url.scheme):
            raise HTTPException(403, 'Cross-origin work requests are not accepted.')

    @router.get('/status')
    def status():
        return invoke(lambda s: {'enabled': True, 'provider_ready': s.model is not None,
                                  'model': s.model.config if s.model is not None and hasattr(s.model, 'config') else None,
                                  'policy_id': POLICY_ID, 'limits': budget_getter(),
                                  'capabilities': ['local_inbox.read', 'local_evidence.assess', 'local_assessment.record',
                                                   'local_request.prepare', 'knowledge.qualify'],
                                  'automatic_inference_retry': False})

    @router.get('/claims')
    def claims():
        return invoke(lambda s: {'claims': [{key: row.get(key) for key in ('claim_id', 'title', 'status', 'phase',
                                                                          'phase_summary', 'revision', 'state_sha256', 'updated_at', 'outcome')}
                                            for row in s.store.list()]})

    @router.post('/claims', status_code=202)
    def intake(body: Intake, request: Request):
        guard(request)
        def apply(service):
            packet = body.model_dump()
            key = packet.pop('idempotency_key')
            state = service.store.intake(packet, key)
            service.submit(state['claim_id'])
            return state
        return invoke(apply)

    @router.get('/claims/{claim_id}')
    def claim(claim_id: str):
        def read(service):
            state = service.store.get(claim_id)
            return {'state': state, 'projection': {'revision': state['revision'], 'state_sha256': state['state_sha256'],
                    'node_capabilities': {n['node_id']: execution_capability(n['node_id']) for n in (state['graph'] or {}).get('nodes', [])}}}
        return invoke(read)

    @router.get('/claims/{claim_id}/events')
    def events(claim_id: str, after: int = Query(0, ge=0)):
        def read(service):
            rows = service.store.events(claim_id, after)
            state = service.store.get(claim_id)
            return {'events': [{**event, 'seq': event['sequence'], 'revision': event['sequence'],
                                'timestamp': event['created_at'], 'state_sha256': event['resulting_state_sha256']} for event in rows],
                    'current_revision': state['revision'], 'current_state_sha256': state['state_sha256']}
        return invoke(read)

    @router.post('/claims/{claim_id}/sources', status_code=202)
    def sources(claim_id: str, body: SourceArrival, request: Request):
        guard(request)
        def apply(service):
            state = service.store.add_sources(claim_id, **body.model_dump())
            service.submit(claim_id)
            return state
        return invoke(apply)

    @router.get('/sources/{claim_id}/{artifact_id}/text')
    def text(claim_id: str, artifact_id: str):
        def read(service):
            state = service.store.get(claim_id)
            source = next((row for row in state['acquired_sources'] if row['artifact_id'] == artifact_id), None)
            if source is None:
                raise HTTPException(409, 'This source has not yet been acquired.')
            return source
        return invoke(read)

    @router.post('/claims/{claim_id}/pause')
    def pause(claim_id: str, body: RevisionCommand, request: Request):
        guard(request)
        return invoke(lambda s: s.store.append(claim_id, 'work.deferred',
                        {'code': 'paused', 'reason': 'Autonomous work was paused. An in-flight provider request may still settle, but its interpretation will not be applied.'},
                        **body.model_dump()))

    @router.post('/claims/{claim_id}/resume', status_code=202)
    def resume(claim_id: str, body: RevisionCommand, request: Request):
        guard(request)
        def apply(service):
            state = service.store.append(claim_id, 'work.resumed', {'reason': 'The operator resumed autonomous work.'}, **body.model_dump())
            service.submit(claim_id)
            return state
        return invoke(apply)

    @router.get('/sources/{claim_id}/{artifact_id}')
    def source(claim_id: str, artifact_id: str):
        def read(service):
            raw, descriptor = service.store.artifact(claim_id, artifact_id)
            return Response(raw, media_type=descriptor['media_type'], headers={
                'Content-Disposition': f"attachment; filename*=UTF-8''{quote(descriptor['file_name'])}",
                'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'no-store', 'X-Content-SHA256': descriptor['sha256']})
        return invoke(read)

    @router.get('/knowledge')
    def knowledge():
        return invoke(lambda s: s.knowledge.view())

    return router


def install_autonomous(app, storage_getter, corpus_getter, agent_work_getter):
    @lru_cache(maxsize=1)
    def service():
        model = None
        if os.getenv('CASEPATH_AUTONOMOUS_ENABLED') == '1':
            from .autonomous_model_v1 import AutonomousModelV1
            work = agent_work_getter()
            if work.facts_worker is not None:
                budget = work.store.external_budget()
                if budget and not budget.get('autonomous_policy'):
                    work.store.activate_autonomous_policy(
                        digest_value(budget), 'CasePath local autonomous policy',
                        'User-authorized autonomous product demonstration; retain original lifetime request and cost limits.',
                        'casepath-autonomous-product-20261008')
                model = AutonomousModelV1(work.store, worker=work.facts_worker,
                                          schemas={'interpret': INTERPRET_SCHEMA, 'verify': VERIFY_SCHEMA})
        return AutonomousController(AutonomousStore(storage_getter()), corpus_getter().static_policy(), model)

    app.include_router(create_autonomous_router(service, lambda: agent_work_getter().store.external_budget()))
    app.add_event_handler('startup', lambda: service().resume())
    app.add_event_handler('shutdown', lambda: service().shutdown())
    return service
