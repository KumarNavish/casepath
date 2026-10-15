"""Same-origin operational intake and read-only autonomous projections."""
from functools import lru_cache
import asyncio
import json
import os
from queue import Empty, Full, Queue
from threading import Event, Thread, Lock
from time import monotonic
from urllib.parse import quote, urlsplit

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
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


class SavedResultReconciliation(RevisionCommand):
    actor: str = Field(min_length=1, max_length=180)
    reason: str = Field(min_length=1, max_length=1000)


class OriginalStart(StrictBody):
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r'^[a-zA-Z0-9_.:-]+$')
    expected_revision: int = Field(ge=0)
    expected_state_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')


def create_autonomous_router(service_getter, budget_getter=lambda: None, *, corpus_getter=None, saved_work_getter=None,
                             read_only=False):
    router = APIRouter(prefix='/api/claim-loops/v1/autonomous')

    def invoke(fn):
        try:
            return fn(service_getter())
        except AutonomousStoreError as error:
            raise HTTPException(409, str(error)) from error
        except (ValueError, KeyError):
            raise HTTPException(422, 'The saved autonomous state could not be verified.')

    def guard(request):
        if read_only:
            raise HTTPException(403, 'The public workspace is read-only.')
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
        result = {'revision': state['revision'], 'state_sha256': state['state_sha256'],
                'node_capabilities': {n['node_id']: execution_capability(n['node_id'])
                                      for n in (state['graph'] or {}).get('nodes', [])}}
        corpus = original(state['claim_id'])
        service = service_getter()
        if originals() is not None or getattr(service, 'reference_adapter', None) is not None:
            sources = ([{**s, **corpus.source_preview(state['claim_id'], s['artifact_id'])}
                        for s in state['source_descriptors']] if state['revision'] == 0 else None)
            result['intake'] = service.intake_projection(state, sources=sources, historical=True)
        return result

    def eligible(service, state, *, corpus=None):
        if hasattr(service, 'assert_execution_policy'):
            service.assert_execution_policy(state)
        if corpus is None and originals() is None and getattr(service, 'reference_adapter', None) is None:
            return True  # Historical generic/private composition keeps its contract.
        sources = ([{**s, **corpus.source_preview(state['claim_id'], s['artifact_id'])}
                    for s in state['source_descriptors']] if state['revision'] == 0 and corpus else None)
        return service.intake_projection(state, sources=sources)['eligible']

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
                      'current_state_sha256': state['state_sha256'], 'current_event_sha256': None,
                      'replay_start': None}
        if after > result['current_revision']:
            raise AutonomousStoreError('event cursor exceeds current revision')
        state = result['state']
        return {**result, 'events': event_rows(result['events']), 'projection': projection(state),
                'mode': 'unprocessed' if state['revision'] == 0 else 'saved',
                'cursor_sha256': result['current_event_sha256']}

    @router.get('/status')
    def status():
        return invoke(lambda s: {'enabled': True, 'provider_ready': s.model is not None,
                                  'read_only': read_only, 'writable': not read_only,
                                  'model': s.model.config if s.model is not None and hasattr(s.model, 'config') else None,
                                  'policy_id': POLICY_ID, 'limits': budget_getter(),
                                  'capabilities': (['saved_claims.read', 'original_sources.read', 'original_sources.preview',
                                                    'claim_history.replay', 'knowledge.inspect'] if read_only else
                                                   ['local_inbox.read', 'local_evidence.assess', 'local_assessment.record',
                                                    'local_request.prepare', 'knowledge.qualify']),
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
            if eligible(service, state):
                service.submit(state['claim_id'])
            return state
        return invoke(apply)

    @router.get('/claims/{claim_id}')
    def claim(claim_id: str):
        return invoke(lambda service: snapshot(service, claim_id))

    @router.get('/claims/{claim_id}/snapshot')
    def claim_snapshot(claim_id: str, after: int = Query(0, ge=0)):
        return invoke(lambda service: snapshot(service, claim_id, after))

    @router.get('/claims/{claim_id}/operations')
    async def operations(claim_id: str, request: Request, mode: str = Query('live', pattern='^(live|recorded)$')):
        from . import autonomous_operations_v1 as runtime
        from .autonomous_reference_v1 import ReferenceProfile
        from .autonomous_reference_policy_v1 import bounded_reference_policy, REFERENCE_POLICY_ID
        from .workspace_corpus import canonical_json_bytes
        # Identity-independent admission precedes saved reads or execution.
        if claim_id not in ReferenceProfile().ids:
            raise HTTPException(403, 'Only the nine synthetic reference claims support this check.')
        if not runtime.PUBLIC_LIMITS.acquire():
            raise HTTPException(429, 'The shared check limit is busy. Retry shortly.', headers={'Retry-After': '60'})
        cancellation, finished = Event(), Event()
        deadline = monotonic() + runtime.MAX_SECONDS
        # A count bound plus a byte bound prevents large checkpoint frames from
        # defeating backpressure. At most 2 MiB of encoded frames can queue.
        queue, queued_bytes, byte_lock = Queue(maxsize=8), [0], Lock()

        def check():
            if cancellation.is_set() or monotonic() >= deadline:
                raise runtime.OperationCancelled('The check stopped before completion.')

        def send(frame):
            encoded = canonical_json_bytes(frame) + b'\n'
            if len(encoded) > 2 * 1024 * 1024:
                raise runtime.OperationCancelled('A check frame exceeds the streaming bound.')
            while True:
                check()
                with byte_lock:
                    if queued_bytes[0] + len(encoded) <= 2 * 1024 * 1024:
                        try:
                            queue.put_nowait(encoded)
                        except Full:
                            pass
                        else:
                            queued_bytes[0] += len(encoded)
                            return
                # Event wait is cancellation-responsive backpressure; no engine
                # or presentation delay is introduced when the consumer reads.
                cancellation.wait(0.01)

        def work():
            try:
                service = service_getter()
                if mode == 'recorded':
                    from .autonomous_operation_trace_store_v1 import OperationTraceStore
                    saved = service.store.snapshot(claim_id)
                    head, start = saved['state'], saved['replay_start']
                    if start is None:
                        raise runtime.OperationsUnavailable('No recorded reference check is available.')
                    sidecar = OperationTraceStore(service.store.journal.connect).read(
                        claim_id, head_state_sha256=head['state_sha256'], head_event_sha256=head['last_event_sha256'],
                        run_id=start['run_id'], profile_sha256=start['profile_sha256'],
                        instrumentation_id=runtime.INSTRUMENTATION_ID, check=check)
                    if sidecar is None:
                        raise runtime.OperationsUnavailable('No recorded operation trace is available for this exact saved head.')
                    for frame in sidecar['frames']:
                        check()
                        send(frame)
                else:
                    policy = service.policy
                    if policy.get('policy_id') != REFERENCE_POLICY_ID:
                        policy = bounded_reference_policy(policy)
                    bundle = runtime.capture_operation_inputs(service.store, claim_id, policy, check=check)
                    runtime.recompute_operations(bundle, send=send, cancellation=cancellation, deadline=deadline)
            except Exception as error:
                if not cancellation.is_set() and monotonic() < deadline:
                    try:
                        send({'contract': runtime.CONTRACT, 'type': 'error', 'code': 'recomputation_unavailable',
                              'detail': str(error) if isinstance(error, ValueError) else 'The saved check is unavailable.'})
                    except runtime.OperationCancelled:
                        pass
            finally:
                finished.set()
                # Keep concurrency owned until the actual worker exits, even
                # when a visitor disconnects while a bounded read is pending.
                runtime.PUBLIC_LIMITS.release()

        thread = Thread(target=work, name='casepath-read-only-operations', daemon=True)
        try:
            thread.start()
        except BaseException:
            runtime.PUBLIC_LIMITS.release()
            raise
        # Return an ordinary rejection before opening a stream when immutable
        # inputs or an admitted recorded sidecar are unavailable.
        async def first_chunk():
            while True:
                if await request.is_disconnected() or monotonic() >= deadline:
                    raise HTTPException(408, 'The bounded check stopped before its saved inputs were verified.')
                try:
                    chunk = queue.get_nowait()
                except Empty:
                    if finished.is_set():
                        raise HTTPException(409, 'No verified operation trace is available.')
                    await asyncio.sleep(0.005)
                else:
                    with byte_lock:
                        queued_bytes[0] -= len(chunk)
                    return chunk
        try:
            first = await first_chunk()
        except BaseException:
            cancellation.set()
            raise
        first_frame = json.loads(first)
        if first_frame['type'] == 'error':
            cancellation.set()
            raise HTTPException(409, first_frame['detail'])

        async def stream():
            try:
                yield first
                while True:
                    if await request.is_disconnected():
                        break
                    if monotonic() >= deadline:
                        yield canonical_json_bytes({'contract': runtime.CONTRACT, 'type': 'error', 'code': 'deadline',
                                                    'detail': 'The bounded check stopped. The saved assessment remains available.'}) + b'\n'
                        break
                    try:
                        chunk = queue.get_nowait()
                    except Empty:
                        if finished.is_set():
                            break
                        await asyncio.sleep(0.005)
                    else:
                        with byte_lock:
                            queued_bytes[0] -= len(chunk)
                        yield chunk
            finally:
                cancellation.set()
                with byte_lock:
                    while not queue.empty():
                        try:
                            queue.get_nowait()
                        except Empty:
                            break
                    queued_bytes[0] = 0

        return StreamingResponse(stream(), media_type='application/x-ndjson', headers={
            'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no', 'X-Content-Type-Options': 'nosniff',
            'X-CasePath-Operation-Mode': mode})

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
            try:
                current = service.store.get(claim_id)
            except AutonomousStoreError as error:
                if str(error) != 'claim does not exist':
                    raise
                current = corpus.preview_state(claim_id)
            if not eligible(service, current, corpus=corpus):
                raise HTTPException(409, {'code': 'intake_incomplete', 'intake': projection(current)['intake']})
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
                          'replay_start': head.get('replay_start'),
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
            if eligible(service, state):
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
            if not eligible(service, service.store.get(claim_id)):
                raise HTTPException(409, {'code': 'intake_incomplete',
                                        'intake': projection(service.store.get(claim_id))['intake']})
            state = service.store.append(claim_id, 'work.resumed', {'reason': 'The operator resumed autonomous work.'}, **body.model_dump())
            service.submit(claim_id)
            return state
        return invoke(apply)

    @router.post('/claims/{claim_id}/reconcile-saved-results')
    def reconcile(claim_id: str, body: SavedResultReconciliation, request: Request):
        guard(request)
        def apply(service):
            if saved_work_getter is None:
                raise AutonomousStoreError('saved semantic results are unavailable for explicit reconciliation')
            return service.reconcile_saved_results(claim_id, work_store=saved_work_getter(), **body.model_dump())
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
        return AutonomousController(AutonomousStore(storage_getter()), corpus_getter().static_policy(), model,
                                    enforce_intake_gate=True)

    app.include_router(create_autonomous_router(service, lambda: agent_work_getter().store.external_budget(),
                                               corpus_getter=canonical_corpus,
                                               saved_work_getter=lambda: agent_work_getter().store))
    app.add_event_handler('startup', lambda: service().resume())
    app.add_event_handler('shutdown', lambda: service().shutdown())
    return service
