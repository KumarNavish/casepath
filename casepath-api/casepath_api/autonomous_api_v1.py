"""Same-origin operational intake and read-only autonomous projections."""
from functools import lru_cache
import os
from urllib.parse import quote, urlsplit

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from .autonomous_controller_v1 import AutonomousController, execution_capability
from .autonomous_corpus_v1 import CanonicalCorpus
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


class OriginalStart(StrictBody):
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r'^[a-zA-Z0-9_.:-]+$')
    expected_revision: int = Field(ge=0)
    expected_state_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')


def create_autonomous_router(service_getter, budget_getter=lambda: None, *, corpus_getter=None):
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

    def originals():
        return corpus_getter() if corpus_getter is not None else None

    def original(claim_id):
        corpus = originals()
        return corpus if corpus is not None and corpus.contains(claim_id) else None

    def projection(state):
        return {'revision': state['revision'], 'state_sha256': state['state_sha256'],
                'node_capabilities': {n['node_id']: execution_capability(n['node_id'])
                                      for n in (state['graph'] or {}).get('nodes', [])}}

    def event_rows(rows):
        return [{**event, 'seq': event['sequence'], 'revision': event['sequence'],
                 'timestamp': event['created_at'], 'state_sha256': event['resulting_state_sha256']}
                for event in rows]

    def snapshot(service, claim_id, after=0):
        try:
            result = service.store.snapshot(claim_id, after=after)
        except AutonomousStoreError as error:
            # Verification failures must never turn a recorded claim back into
            # an unprocessed original. Only an absent stream can use this view.
            if str(error) != 'claim does not exist':
                raise
            corpus = originals()
            if corpus is None:
                raise
            if not corpus.contains(claim_id):
                if claim_id.startswith('clm_'):
                    raise HTTPException(404, 'Unknown original claim.') from error
                raise
            if after:
                raise AutonomousStoreError('event cursor exceeds current revision')
            state = corpus.preview_state(claim_id)
            result = {'state': state, 'events': [], 'current_revision': 0,
                      'current_state_sha256': state['state_sha256'], 'current_event_sha256': None}
        if after > result['current_revision']:
            raise AutonomousStoreError('event cursor exceeds current revision')
        state = result['state']
        return {**result, 'events': event_rows(result['events']), 'projection': projection(state),
                'mode': 'unprocessed' if state['revision'] == 0 else 'saved',
                'cursor_sha256': result['current_event_sha256']}

    @router.get('/status')
    def status():
        return invoke(lambda s: {'enabled': True, 'provider_ready': s.model is not None,
                                  'model': s.model.config if s.model is not None and hasattr(s.model, 'config') else None,
                                  'policy_id': POLICY_ID, 'limits': budget_getter(),
                                  'capabilities': ['local_inbox.read', 'local_evidence.assess', 'local_assessment.record',
                                                   'local_request.prepare', 'knowledge.qualify'],
                                  'automatic_inference_retry': False})

    @router.get('/claims')
    def claims(limit: int = Query(200, ge=1, le=500), offset: int = Query(0, ge=0),
               q: str = Query('', max_length=300), domain: str = Query('', max_length=80)):
        def read(service):
            corpus = originals()
            base = {row['claim_id']: {**row, 'origin': 'canonical_original'}
                    for row in corpus.summary_rows()} if corpus is not None else {}
            for row in service.store.list_summaries():
                cid = row['claim_id']
                base[cid] = {**base.get(cid, {}), **row, 'mode': 'saved',
                             'origin': 'canonical_original' if cid in base else 'native_intake'}
            values = sorted(base.values(), key=lambda row: row['claim_id'])
            domain_counts = {}
            for row in values:
                name = row.get('browse_metadata', {}).get('domain')
                if name:
                    domain_counts[name] = domain_counts.get(name, 0) + 1
            # Navigation taxonomy is separate from engine context. Absent
            # taxonomy stays absent; never classify a claim from its wording.
            if domain:
                values = [r for r in values if r.get('browse_metadata', {}).get('domain') == domain]
            terms = q.casefold().split()
            if terms:
                values = [r for r in values if all(term in (' '.join(str(r.get(k, '')) for k in
                          ('claim_id', 'title', 'source_preview', 'language', 'channel'))).casefold() for term in terms)]
            if corpus is None and not q and not domain and offset == 0 and limit == 200:
                # Preserve the legacy router's envelope for integrations that
                # have deliberately not installed canonical browsing.
                return {'claims': values[:limit]}
            return {'claims': values[offset:offset + limit], 'total': len(values), 'limit': limit, 'offset': offset,
                    'collection_sha256': digest_value(values), 'domain_counts': domain_counts}
        return invoke(read)

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
        return invoke(lambda service: snapshot(service, claim_id))

    @router.get('/claims/{claim_id}/snapshot')
    def claim_snapshot(claim_id: str, after: int = Query(0, ge=0)):
        return invoke(lambda service: snapshot(service, claim_id, after))

    @router.get('/claims/{claim_id}/events')
    def events(claim_id: str, after: int = Query(0, ge=0)):
        def read(service):
            result = snapshot(service, claim_id, after)
            return {k: result[k] for k in ('events', 'current_revision', 'current_state_sha256', 'cursor_sha256')}
        return invoke(read)

    @router.post('/claims/{claim_id}/start', status_code=202)
    def start(claim_id: str, body: OriginalStart, request: Request):
        guard(request)
        def apply(service):
            corpus = original(claim_id)
            if corpus is None:
                raise HTTPException(404, 'Unknown original claim.')
            result = service.store.admit_original(claim_id, corpus.packet(claim_id), **body.model_dump())
            if not result['replayed']:
                service.submit(claim_id)
            elif hasattr(service, 'wake_pending'):
                # Explicit retry may recover an already accepted hosted job
                # parked behind a busy/lost lease. The existing scheduler
                # retains in-flight and uncertain-attempt guards; GETs stay inert.
                service.wake_pending()
            return result['state']
        return invoke(apply)

    @router.get('/claims/{claim_id}/replay')
    def replay(claim_id: str, through_seq: int = Query(..., ge=0)):
        def read(service):
            if through_seq == 0:
                corpus = original(claim_id)
                if corpus is None:
                    raise HTTPException(409, 'Only an original claim has a revision-zero source projection.')
                # Validate the whole saved head, including suffixes, before
                # exposing any historical prefix. This read has no side effects.
                head = snapshot(service, claim_id)
                state = corpus.preview_state(claim_id)
                result = {'state': state, 'events': [], 'through_seq': 0, 'replay_only': True,
                          'current_revision': head['current_revision'], 'current_state_sha256': head['current_state_sha256'],
                          'current_event_sha256': head['current_event_sha256'],
                          'provenance': {'source_roster_sha256': state['source_roster_sha256'],
                                         'original_binding_sha256': state['original_binding']['original_binding_sha256'],
                                         'policy_id': None, 'run_id': None, 'event_sha256': None}}
            else:
                result = service.store.replay(claim_id, through_seq)
                state = result['state']
            return {**result, 'events': event_rows(result['events']), 'projection': projection(state), 'mode': 'replay',
                    'cursor_sha256': state['last_event_sha256']}
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
            state = snapshot(service, claim_id)['state']
            corpus = original(claim_id)
            if corpus is not None:
                try:
                    _, descriptor = corpus.artifact(claim_id, artifact_id)
                    artifact_id_bound = descriptor['artifact_id']
                except ValueError:
                    artifact_id_bound = artifact_id
            else:
                artifact_id_bound = artifact_id
            source = next((row for row in state['acquired_sources'] if row['artifact_id'] == artifact_id_bound), None)
            if source is None:
                raise HTTPException(409, 'This source has not yet been acquired.')
            return source
        return invoke(read)

    @router.get('/sources/{claim_id}/{artifact_id}/preview')
    def preview(claim_id: str, artifact_id: str):
        def read(service):
            corpus = original(claim_id)
            if corpus is not None:
                state = corpus.preview_state(claim_id)
                source_ids = {r['artifact_id'] for r in state['source_descriptors']} | {
                              r['original_artifact_id'] for r in state['original_binding']['source_map']}
                if artifact_id in source_ids:
                    return corpus.source_preview(claim_id, artifact_id)
            raw, descriptor = service.store.artifact(claim_id, artifact_id)
            extraction = service.store._extract(raw, descriptor['media_type'].split(';', 1)[0].strip().lower())
            result = {**descriptor, **extraction, 'preview_only': True, 'evidence_admitted': False}
            return {**result, 'preview_sha256': digest_value(result)}
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
            corpus = original(claim_id)
            if corpus is not None:
                state = corpus.preview_state(claim_id)
                source_ids = {r['artifact_id'] for r in state['source_descriptors']} | {
                              r['original_artifact_id'] for r in state['original_binding']['source_map']}
                if artifact_id in source_ids:
                    raw, descriptor = corpus.artifact(claim_id, artifact_id)
                else:
                    raw, descriptor = service.store.artifact(claim_id, artifact_id)
            else:
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
    def canonical_corpus():
        return CanonicalCorpus(corpus_getter())

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

    app.include_router(create_autonomous_router(service, lambda: agent_work_getter().store.external_budget(),
                                               corpus_getter=canonical_corpus))
    app.add_event_handler('startup', lambda: service().resume())
    app.add_event_handler('shutdown', lambda: service().shutdown())
    return service
