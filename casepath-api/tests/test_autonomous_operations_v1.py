"""Real deterministic execution, immutable checkpoints, and public read boundaries."""
from copy import deepcopy
from hashlib import sha256
import asyncio
import gzip
import json
import base64
import sqlite3
from types import SimpleNamespace
from threading import Event
from time import monotonic
import zlib

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from casepath_api import autonomous_operations_v1 as runtime
from casepath_api.autonomous_api_v1 import create_autonomous_router
from casepath_api.autonomous_controller_v1 import AutonomousController
from casepath_api.autonomous_corpus_v1 import CanonicalCorpus
from casepath_api.autonomous_reference_v1 import ReferenceProfile, _find
from casepath_api.autonomous_store_v1 import AutonomousStore
from casepath_api.causal_process_v1 import evaluate
from casepath_api.workspace_corpus import canonical_json_bytes, digest_value
from test_causal_process_v1 import graph
from test_complete_reference_intake_v1 import admit, service_at


async def raw_operations(app, cid, encoding, *, on_chunk=None, disconnected=None, mode='live'):
    """Observe actual ASGI bytes without HTTP client's transparent decoding."""
    messages, chunks = [], []
    async def receive():
        if disconnected is not None and disconnected.is_set():
            return {'type': 'http.disconnect'}
        await asyncio.Future()
    async def send(message):
        messages.append(message)
        if message['type'] == 'http.response.body' and message.get('body'):
            chunks.append(message['body'])
            if on_chunk is not None:
                await on_chunk(chunks)
    fields = encoding if isinstance(encoding, list) else [encoding]
    headers = [(b'accept-encoding', field.encode()) for field in fields if field is not None]
    await app({'type': 'http', 'asgi': {'version': '3.0', 'spec_version': '2.4'},
               'http_version': '1.1', 'method': 'GET', 'scheme': 'http', 'server': ('test', 80),
               'client': ('test', 1), 'root_path': '', 'path':
               '/api/claim-loops/v1/autonomous/claims/' + cid + '/operations',
               'query_string': ('mode=' + mode).encode(), 'headers': headers}, receive, send)
    start = next(message for message in messages if message['type'] == 'http.response.start')
    return start['status'], dict(start['headers']), chunks


@pytest.fixture
def transport_app(monkeypatch):
    from casepath_api.autonomous_reference_policy_v1 import REFERENCE_POLICY_ID
    service = SimpleNamespace(policy={'policy_id': REFERENCE_POLICY_ID}, store=SimpleNamespace())
    monkeypatch.setattr(runtime, 'capture_operation_inputs', lambda *args, **kwargs: None)
    monkeypatch.setattr(runtime, 'PUBLIC_LIMITS', runtime.PublicOperationLimits(concurrency=1, total=100))
    app = FastAPI()
    app.include_router(create_autonomous_router(lambda: service, read_only=True))
    return app, ReferenceProfile().ids[0]


@pytest.mark.parametrize(('encoding', 'expected'), [
    (None, None), ('', None), ('gzip', 'gzip'), ('GZip;Q=1', 'gzip'),
    ('gzip;q=0', None), ('gzip;q=0, *;q=1', None), ('*;q=1', 'gzip'),
    ('gzip;q=0.5', 'gzip'), ('gzip;q=0.5, identity;q=0.2', 'gzip'),
    ('gzip;q=0.5, identity;q=1', None),
    ('gzip;q=1, identity;q=1', 'gzip'), ('identity;q=0, gzip;q=0.1', 'gzip'),
    ('*;q=0, gzip;q=0.5', 'gzip'), ('br, gzip;q=0.7, identity;q=0.3', 'gzip'),
    ('gzip;q=1.001', None), ('gzip;q=2', None), ('gzip;q=.5', None),
    ('gzip;q=0.0000', None), ('gzip;q=wat', None), ('gzip;q=1;other=x', None),
    ('gzip;q=1, gzip;q=0', None),
    ('identity;q=0, gzip;q=0', 'reject'), ('*;q=0', 'reject'),
    ('br, identity;q=0', 'reject'), ('identity;q=0, gzip;q=invalid', 'reject'),
    (['gzip;q=1', 'gzip;q=0'], None), (['gzip;q=0', 'identity;q=0'], 'reject'),
    (['identity;q=0', 'gzip;q=1'], 'gzip'),
])
def test_operation_transport_negotiates_encoding_before_admission(transport_app, monkeypatch, encoding, expected):
    app, cid = transport_app
    frames = [{'type': 'binding'}, {'type': 'result'}]
    def recompute(_, *, send, **kwargs):
        for frame in frames:
            send(frame)
    monkeypatch.setattr(runtime, 'recompute_operations', recompute)
    status, headers, chunks = asyncio.run(raw_operations(app, cid, encoding))
    if expected == 'reject':
        assert status == 406 and not runtime.PUBLIC_LIMITS.starts
        return
    assert status == 200
    assert headers.get(b'content-encoding') == (expected.encode() if expected else None)
    assert headers[b'vary'] == b'Accept-Encoding'
    body = b''.join(chunks)
    assert (gzip.decompress(body) if expected else body) == b''.join(canonical_json_bytes(f) + b'\n' for f in frames)


@pytest.mark.parametrize('encoding', ['identity', 'gzip'])
def test_operation_transport_flushes_binding_then_batches_available_frames(transport_app, monkeypatch, encoding):
    app, cid = transport_app
    binding_sent, release = Event(), Event()
    frames = [{'type': 'binding', 'claim_id': cid}]
    frames += [{'type': 'operation', 'id': index, 'text': 'é😀' * 1700} for index in range(16)]
    frames += [{'type': 'checkpoint', 'text': 'x' * 70000}, {'type': 'result'}]
    def recompute(_, *, send, **kwargs):
        send(frames[0])
        binding_sent.set()
        assert release.wait(1), 'binding was buffered until computation finished'
        for frame in frames[1:]:
            send(frame)
    monkeypatch.setattr(runtime, 'recompute_operations', recompute)
    inflater = zlib.decompressobj(31) if encoding == 'gzip' else None
    decoded = []
    async def on_chunk(chunks):
        chunk = inflater.decompress(chunks[-1]) if inflater else chunks[-1]
        decoded.append(chunk)
        if len(chunks) == 1:
            assert binding_sent.is_set() and not release.is_set()
            assert chunk == canonical_json_bytes(frames[0]) + b'\n'
            release.set()
            # Allow the bounded producer queue to fill, so batching is observable.
            await asyncio.sleep(0.02)
    status, _, chunks = asyncio.run(raw_operations(app, cid, encoding, on_chunk=on_chunk))
    assert status == 200 and (inflater is None or inflater.eof)
    assert b''.join(decoded) == b''.join(canonical_json_bytes(f) + b'\n' for f in frames)
    batches = [chunk for chunk in decoded[1:] if chunk]
    assert any(chunk.count(b'\n') > 1 for chunk in batches)
    assert len(batches) < len(frames) - 1
    assert all(len(chunk) <= 65536 or chunk.count(b'\n') == 1 for chunk in batches)
    assert len(chunks) < len(frames) + 1


@pytest.mark.parametrize('encoding', ['identity', 'gzip'])
@pytest.mark.parametrize('stop', ['disconnect', 'deadline', 'error'])
def test_operation_transport_closes_bounded_worker_and_encoded_errors(transport_app, monkeypatch, encoding, stop):
    app, cid = transport_app
    disconnected, stopped, produced = Event(), Event(), []
    if stop == 'deadline':
        monkeypatch.setattr(runtime, 'MAX_SECONDS', 0.06)
    def recompute(_, *, send, cancellation, **kwargs):
        try:
            send({'type': 'binding'})
            if stop == 'error':
                raise ValueError('controlled transport failure')
            if stop == 'deadline':
                assert cancellation.wait(1)
            else:
                # A nonreading client must leave the producer at the existing queue bound.
                for index in range(100):
                    send({'type': 'operation', 'id': index, 'text': 'x' * 400000})
                    produced.append(index)
        finally:
            stopped.set()
    monkeypatch.setattr(runtime, 'recompute_operations', recompute)
    async def on_chunk(chunks):
        if stop == 'disconnect' and len(chunks) == 1:
            await asyncio.sleep(0.02)
            assert not stopped.is_set(), 'producer escaped bounded backpressure'
            assert 1 <= len(produced) <= 5, 'producer escaped the 2 MiB queued-byte bound'
            disconnected.set()
    _, _, chunks = asyncio.run(raw_operations(app, cid, encoding, on_chunk=on_chunk, disconnected=disconnected))
    assert stopped.wait(1) and runtime.PUBLIC_LIMITS.active == 0
    data = gzip.decompress(b''.join(chunks)) if encoding == 'gzip' else b''.join(chunks)
    frames = [json.loads(line) for line in data.splitlines()]
    assert frames[0]['type'] == 'binding'
    if stop == 'disconnect':
        assert len(frames) == 1
    else:
        assert frames[-1]['type'] == 'error'
        assert frames[-1]['code'] == ('deadline' if stop == 'deadline' else 'recomputation_unavailable')


@pytest.mark.parametrize('encoding', ['identity', 'gzip'])
def test_operation_transport_rejects_oversized_frame_without_emitting_its_bytes(transport_app, monkeypatch, encoding):
    app, cid = transport_app
    def recompute(_, *, send, **kwargs):
        send({'type': 'binding'})
        send({'type': 'checkpoint', 'text': 'x' * (2 * 1024 * 1024)})
    monkeypatch.setattr(runtime, 'recompute_operations', recompute)
    status, _, chunks = asyncio.run(raw_operations(app, cid, encoding))
    data = gzip.decompress(b''.join(chunks)) if encoding == 'gzip' else b''.join(chunks)
    frames = [json.loads(line) for line in data.splitlines()]
    assert status == 200 and [frame['type'] for frame in frames] == ['binding', 'error']
    assert frames[-1]['code'] == 'recomputation_unavailable' and b'checkpoint' not in data


@pytest.mark.parametrize('encoding', ['identity', 'gzip'])
def test_operation_transport_keeps_lookahead_charged_under_backpressure(transport_app, monkeypatch, encoding):
    app, cid = transport_app
    release, disconnected, stopped, produced = Event(), Event(), Event(), []
    def recompute(_, *, send, **kwargs):
        try:
            send({'type': 'binding'})
            assert release.wait(1)
            for size in [40000, 1500000] + [400000] * 10:
                send({'type': 'checkpoint', 'text': 'x' * size})
                produced.append(size)
        finally:
            stopped.set()
    monkeypatch.setattr(runtime, 'recompute_operations', recompute)
    async def on_chunk(chunks):
        if len(chunks) == 1:
            release.set()
            await asyncio.sleep(0.03)
        elif len(chunks) == 2:
            # A 1.5 MiB frame does not fit after the small batch. While this
            # send is blocked, lookahead plus the queue must still fit 2 MiB.
            await asyncio.sleep(0.03)
            assert produced == [40000, 1500000, 400000]
            assert not stopped.is_set()
            disconnected.set()
    asyncio.run(raw_operations(app, cid, encoding, on_chunk=on_chunk, disconnected=disconnected))
    assert stopped.wait(1) and runtime.PUBLIC_LIMITS.active == 0


@pytest.fixture(scope='module')
def migrated(tmp_path_factory):
    root = tmp_path_factory.mktemp('real-operation-history')
    corpus = CanonicalCorpus()
    cid = ReferenceProfile().ids[0]
    old = service_at(root / 'journal.sqlite', corpus, ReferenceProfile.for_profile('synthetic-nine-v1'))
    admit(old, corpus, cid)
    previous = old.run(cid)
    old.shutdown()
    service = service_at(root / 'journal.sqlite', corpus)
    service.store.add_sources(cid, service.reference_adapter.profile.files(cid), expected_revision=previous['revision'],
                             expected_state_sha256=previous['state_sha256'], idempotency_key='operation-cleaned-v2')
    head = service.run(cid)
    assert head['outcome']['assessment_status'] == 'complete'
    bundle = runtime.capture_operation_inputs(service.store, cid, service.policy)
    yield service, corpus, cid, head, bundle
    service.shutdown()


def test_real_callsite_trace_preserves_every_prefix_and_exact_final_output(migrated, monkeypatch):
    service, _, cid, head, bundle = migrated
    original_events = service.store.events(cid)
    def forbidden(*args, **kwargs):
        raise AssertionError('A writable constructor or persistent command was called')
    monkeypatch.setattr(AutonomousStore, '__init__', forbidden)
    monkeypatch.setattr(AutonomousStore, 'append', forbidden)
    monkeypatch.setattr(AutonomousController, '__init__', forbidden)
    monkeypatch.setattr(service.store, '_publish', forbidden)
    sidecar = runtime.build_operation_sidecar(bundle)
    assert runtime.verify_operation_sidecar(bundle, sidecar)['verified']
    frames = sidecar['frames']
    binding, result = frames[0], frames[-1]
    assert binding['mode'] == 'historical_recomputed' and binding['newly_recomputed'] is True
    assert result['exact_output_verified'] and result['state_sha256'] == head['state_sha256']
    state, chain, ids = None, None, set()
    kinds = set()
    for frame in frames:
        if frame['type'] == 'checkpoint':
            assert frame['verified'] and frame['journal_seq'] >= binding['from_seq']
            if 'state' in frame:
                state = frame['state']
            else:
                assert state['state_sha256'] == frame['base_state_sha256']
                state = {**state, **frame['state_delta']['set']}
                for key in frame['state_delta']['remove']:
                    state.pop(key)
            assert digest_value({key: value for key, value in state.items() if key != 'state_sha256'}) == frame['state_sha256']
            assert state == service.store.replay(cid, frame['journal_seq'])['state']
            assert frame['events'][0]['seq'] == frame['journal_seq']
        elif frame['type'] == 'operation':
            assert frame['journal_seq'] >= binding['from_seq']
            assert frame['id'] not in ids and set(frame['cause_ids']) <= ids
            assert frame['previous_operation_sha256'] == chain
            payload = {key: value for key, value in frame.items() if key not in {'contract', 'type', 'operation_sha256'}}
            assert digest_value(payload) == frame['operation_sha256']
            assert digest_value(frame['input']) == frame['input_sha256']
            assert digest_value(frame['result']) == frame['result_sha256']
            chain = frame['operation_sha256']
            ids.add(frame['id']); kinds.add(frame['kind'])
            if frame['kind'] == 'fact.extract' and frame['stage'] in {'interpret_reference', 'verify_reference'}:
                assert frame['result']['status'] == 'provisional'
    assert {'source.open', 'span.read', 'phrase.match', 'fact.extract', 'verification.check',
            'process.inspect', 'condition.evaluate', 'node.evaluate', 'dependency.evaluate', 'document.require', 'document.check', 'step.complete', 'decision', 'knowledge.reuse'} <= kinds
    assert not any(kind.startswith('branch.') for kind in kinds)
    assert chain == result['operation_chain_sha256']
    assert state == head and service.store.events(cid) == original_events
    assert len(canonical_json_bytes(sidecar)) < 8 * 1024 * 1024
    assert result['trace_sha256'] == digest_value([digest_value(frame) for frame in frames[:-1]])


def test_real_unicode_regex_offsets_and_causal_drop_come_from_execution():
    text = '😀 é\nQuoted heating failure.'
    source = {'artifact_id': 'src_unicode', 'sha256': sha256(text.encode()).hexdigest(), 'text': text,
              'role': 'supporting_document', 'complete': True, 'file_name': 'unicode.txt'}
    sink = runtime.OperationSink()
    with sink.scope('interpret_reference', 1):
        result = _find([source], r'Quoted heating failure\.')
    assert result == {'artifact_id': 'src_unicode', 'quote': 'Quoted heating failure.'}
    matched = next(frame for frame in sink.frames if frame.get('kind') == 'phrase.match')
    pin = matched['source']
    assert pin['start_char'] == 4 and pin['offset_unit'] == 'unicode_code_point'
    assert text[pin['start_char']:pin['end_char']] == pin['quote']
    assert pin['sha256'] == source['sha256'] and pin['text_sha256'] == sha256(text.encode()).hexdigest()
    plain = evaluate(graph(), {'branch': 'false'})
    with sink.scope('native_execution', 2):
        observed = evaluate(graph(), {'branch': 'false'})
    assert plain == observed
    drop = next(frame for frame in sink.frames if frame.get('kind') == 'branch.drop' and frame['object']['id'] == 'left_path')
    assert drop['input']['condition_verdict'] == 'false' and drop['result']['activation'] == 'false'
    unknown = runtime.OperationSink()
    with unknown.scope('native_execution', 3):
        evaluate(graph(), {'branch': 'unresolved'})
    unresolved = [frame for frame in unknown.frames if frame.get('kind') == 'branch.evaluate']
    assert unresolved and all(frame['result']['activation'] == 'unresolved' for frame in unresolved)
    assert not any(frame.get('kind') == 'branch.activate' and frame['result']['activation'] != 'true' for frame in unknown.frames)
    dependency_graph = deepcopy(graph())
    dependency_graph['edges'][0]['relation'] = 'requires'
    dependencies = runtime.OperationSink()
    with dependencies.scope('native_execution', 4):
        evaluate(dependency_graph, {'branch': 'false'})
    left = [frame for frame in dependencies.frames if frame.get('object', {}).get('id') == 'left_path']
    assert any(frame.get('kind') == 'dependency.evaluate' for frame in left)
    assert not any(frame.get('kind', '').startswith('branch.') for frame in left)


@pytest.mark.parametrize('damage', ['source', 'checkpoint', 'historical_event', 'policy'])
def test_any_snapshot_damage_fails_closed(migrated, damage):
    bundle = deepcopy(migrated[-1])
    if damage == 'source':
        key = next(iter(bundle['sources_base64'])); bundle['sources_base64'][key] = 'YXJiaXRyYXJ5'
    elif damage in {'checkpoint', 'historical_event'}:
        event = json.loads(bundle['rows'][0]['event_json'])
        event['resulting_state_sha256' if damage == 'checkpoint' else 'event_sha256'] = '0' * 64
        bundle['rows'][0]['event_json'] = canonical_json_bytes(event).decode()
    else:
        bundle['policy']['templates'][0]['title'] = 'Changed rules'
    with pytest.raises(ValueError):
        runtime.build_operation_sidecar(bundle)


def test_sidecar_corruption_and_cancellation_fail_closed(migrated):
    bundle = migrated[-1]
    sidecar = runtime.build_operation_sidecar(bundle)
    damaged = deepcopy(sidecar)
    damaged['frames'][1]['result'] = {'invented': True}
    with pytest.raises(runtime.OperationsUnavailable, match='sidecar differs'):
        runtime.verify_operation_sidecar(bundle, damaged)
    stop = Event(); stop.set()
    with pytest.raises(runtime.OperationCancelled):
        runtime.recompute_operations(bundle, cancellation=stop)
    with pytest.raises(runtime.OperationCancelled):
        runtime.recompute_operations(bundle, deadline=monotonic() - 1)


def test_live_get_is_write_free_allowlisted_globally_limited_and_releases(migrated, monkeypatch):
    service, corpus, cid, head, _ = migrated
    limits = runtime.PublicOperationLimits(concurrency=1, total=1)
    monkeypatch.setattr(runtime, 'PUBLIC_LIMITS', limits)
    before = service.store.events(cid)
    app = FastAPI()
    app.include_router(create_autonomous_router(lambda: service, corpus_getter=lambda: corpus, read_only=True))
    def forbidden(*args, **kwargs):
        raise AssertionError('Public GET attempted a write or constructed a worker')
    monkeypatch.setattr(AutonomousController, '__init__', forbidden)
    monkeypatch.setattr(AutonomousStore, '__init__', forbidden)
    monkeypatch.setattr(AutonomousStore, 'append', forbidden)
    monkeypatch.setattr(service.store, '_publish', forbidden)
    with TestClient(app) as client:
        prefix = '/api/claim-loops/v1/autonomous/claims/'
        rejected = client.get(prefix + 'clm_not_allowed/operations')
        assert rejected.status_code == 403 and limits.active == 0 and not limits.starts
        response = client.get(prefix + cid + '/operations', headers={'X-CasePath-User-Id': 'visitor-a'})
        assert response.status_code == 200
        frames = [json.loads(row) for row in response.text.splitlines()]
        assert frames[0]['type'] == 'binding' and frames[-1]['type'] == 'result', frames[-1]
        assert frames[-1]['state_sha256'] == head['state_sha256'] and limits.active == 0
        limited = client.get(prefix + cid + '/operations', headers={'X-CasePath-User-Id': 'spoofed-new-user'})
        assert limited.status_code == 429 and limits.active == 0
    assert service.store.events(cid) == before


def test_stream_delivers_operations_during_compute_and_cancel_stops_work(migrated):
    bundle = migrated[-1]
    stop, received = Event(), []
    def send(frame):
        received.append(frame)
        if frame['type'] == 'operation':
            stop.set()
    with pytest.raises(runtime.OperationCancelled):
        runtime.recompute_operations(bundle, send=send, cancellation=stop)
    assert received[0]['type'] == 'binding' and received[-1]['type'] == 'operation'
    assert not any(frame['type'] == 'result' for frame in received)


def test_public_get_rejects_warm_cached_but_corrupt_persistent_sources(migrated, tmp_path, monkeypatch):
    from casepath_api.hosted_storage_v1 import HostedJournal, HostedSources, HostedAutonomousStore
    from hosted_hrana_fixture import MockHrana
    service, _, cid, _, bundle = migrated
    server = MockHrana(tmp_path / 'remote.sqlite')
    try:
        journal = HostedJournal(tmp_path / 'unused-journal', server.connection)
        sources = HostedSources(server.connection)
        store = HostedAutonomousStore(journal.path, journal=journal, source_store=sources)
        for digest, encoded in bundle['sources_base64'].items():
            assert sources.publish(base64.b64decode(encoded)) == digest
        with sqlite3.connect(server.path) as db:
            db.executemany('INSERT INTO claim_loop_events (session_id,loop_id,sequence,idempotency_key,command_sha256,event_sha256,event_json,created_at) '
                           'VALUES (:session_id,:loop_id,:sequence,:idempotency_key,:command_sha256,:event_sha256,:event_json,:created_at)', bundle['rows'])
        digest, encoded = next(iter(bundle['sources_base64'].items()))
        original = base64.b64decode(encoded)
        assert store._blob(digest) == original
        # Test-only corruption bypasses the fixture's production immutability
        # trigger, demonstrating that a hot cache is not persistent authority.
        with sqlite3.connect(server.path) as db:
            db.execute('DROP TRIGGER autonomous_source_chunks_no_update')
            db.execute('UPDATE autonomous_source_chunks SET content=? WHERE sha256=? AND chunk_index=0', (b'corrupt', digest))
        assert store._blob(digest) == original
        readonly = SimpleNamespace(store=store, policy=service.policy)
        monkeypatch.setattr(runtime, 'PUBLIC_LIMITS', runtime.PublicOperationLimits())
        app = FastAPI()
        app.include_router(create_autonomous_router(lambda: readonly, read_only=True))
        baseline = len(server.requests)
        with TestClient(app) as client:
            response = client.get('/api/claim-loops/v1/autonomous/claims/' + cid + '/operations')
        assert response.status_code == 409 and 'source' in response.json()['detail'].lower()
        assert '"type":"binding"' not in response.text and '"type":"result"' not in response.text
        statements = [item['stmt']['sql'] for request in server.requests[baseline:] for item in request['requests']
                      if item['type'] == 'execute']
        assert statements and all(sql.split()[0] == 'SELECT' for sql in statements)
        assert runtime.PUBLIC_LIMITS.active == 0 and server.open_streams == 0
    finally:
        server.close()


def test_capture_enforces_limits_before_blob_reads(migrated, monkeypatch):
    service, _, cid, _, _ = migrated
    def forbidden(*args, **kwargs):
        raise AssertionError('Oversized input reached a source reader')
    monkeypatch.setattr(service.store, '_blob', forbidden)
    monkeypatch.setattr(runtime, 'MAX_EVENTS', 1)
    with pytest.raises(runtime.OperationsUnavailable, match='journal exceeds'):
        runtime.capture_operation_inputs(service.store, cid, service.policy)


def test_recorded_get_requires_admitted_trace_and_never_recomputes(migrated, monkeypatch):
    from casepath_api.autonomous_operation_trace_store_v1 import initialize_operation_trace_storage, admit_operation_trace
    service, corpus, cid, head, bundle = migrated
    monkeypatch.setattr(runtime, 'PUBLIC_LIMITS', runtime.PublicOperationLimits())
    app = FastAPI()
    app.include_router(create_autonomous_router(lambda: service, corpus_getter=lambda: corpus, read_only=True))
    url = '/api/claim-loops/v1/autonomous/claims/' + cid + '/operations?mode=recorded'
    before = service.store.events(cid)
    with TestClient(app) as client:
        assert client.get(url).status_code == 409
        sidecar = runtime.build_operation_sidecar(bundle)
        initialize_operation_trace_storage(service.store.journal.connect)
        admit_operation_trace(service.store.journal.connect, bundle, sidecar)
        def forbidden(*args, **kwargs):
            raise AssertionError('A recorded GET recomputed or admitted operations')
        monkeypatch.setattr(runtime, 'recompute_operations', forbidden)
        monkeypatch.setattr(runtime, 'capture_operation_inputs', forbidden)
        monkeypatch.setattr(AutonomousStore, 'append', forbidden)
        response = client.get(url)
        assert response.status_code == 200 and response.headers['X-CasePath-Operation-Mode'] == 'recorded'
        assert [json.loads(row) for row in response.text.splitlines()] == sidecar['frames']
        assert service.store.events(cid) == before and service.store.get(cid) == head
        assert runtime.PUBLIC_LIMITS.active == 0


def test_unrun_claim_is_not_found_while_a_damaged_head_still_conflicts(migrated, tmp_path, monkeypatch):
    service, corpus, cid, head, _ = migrated
    monkeypatch.setattr(runtime, 'PUBLIC_LIMITS', runtime.PublicOperationLimits())
    url = '/api/claim-loops/v1/autonomous/claims/' + cid + '/operations'
    empty = service_at(tmp_path / 'unrun.sqlite', corpus)
    try:
        app = FastAPI()
        app.include_router(create_autonomous_router(lambda: empty, corpus_getter=lambda: corpus, read_only=True))
        with TestClient(app) as client:
            for mode in ('live', 'recorded'):
                response = client.get(url + '?mode=' + mode)
                assert response.status_code == 404, (mode, response.text)
                assert response.json()['detail'] == 'No saved history for this claim.'
                assert '"type":"binding"' not in response.text
        from casepath_api.autonomous_store_v1 import AutonomousStoreError
        with pytest.raises(AutonomousStoreError, match='does not exist'):
            empty.store.snapshot(cid)  # the GETs wrote nothing
        assert runtime.PUBLIC_LIMITS.active == 0
    finally:
        empty.shutdown()
    with pytest.raises(runtime.OperationsNoHistory) as missing:
        runtime.capture_operation_inputs(empty.store, cid, empty.policy)
    assert missing.value.code == 'no_history'

    # A saved head whose bounded read loses its tail is a conflict, never "no history".
    original = service.store.journal.connect
    class Truncated:
        def __enter__(self):
            self.connection = original().__enter__()
            outer = self
            class Reader:
                def execute(self, query, parameters=()):
                    rows = outer.connection.execute(query, parameters).fetchall()
                    return SimpleNamespace(fetchall=lambda: rows[:-1] if '__tail' in query else rows)
            return Reader()
        def __exit__(self, *error):
            return self.connection.__exit__(*error)
    monkeypatch.setattr(service.store.journal, 'connect', Truncated)
    with pytest.raises(runtime.OperationsUnavailable, match='row count differs') as damaged:
        runtime.capture_operation_inputs(service.store, cid, service.policy)
    assert not isinstance(damaged.value, runtime.OperationsNoHistory)
    app = FastAPI()
    app.include_router(create_autonomous_router(lambda: service, corpus_getter=lambda: corpus, read_only=True))
    with TestClient(app) as client:
        response = client.get(url)
    assert response.status_code == 409 and 'row count differs' in response.json()['detail']
    monkeypatch.setattr(service.store.journal, 'connect', original)
    assert service.store.get(cid) == head and runtime.PUBLIC_LIMITS.active == 0


@pytest.mark.parametrize('mode', ['live', 'recorded'])
def test_real_operation_transport_preserves_exact_ndjson_and_hashes_in_both_encodings(migrated, monkeypatch, mode):
    from casepath_api.autonomous_operation_trace_store_v1 import initialize_operation_trace_storage, admit_operation_trace
    service, corpus, cid, head, bundle = migrated
    sidecar = runtime.build_operation_sidecar(bundle)
    initialize_operation_trace_storage(service.store.journal.connect)
    admit_operation_trace(service.store.journal.connect, bundle, sidecar)
    expected = b''.join(canonical_json_bytes(frame) + b'\n' for frame in sidecar['frames'])
    before = service.store.events(cid)
    def forbidden(*args, **kwargs):
        raise AssertionError('Read-only transport invoked a writer or model')
    for cls in (AutonomousStore, AutonomousController):
        monkeypatch.setattr(cls, '__init__', forbidden)
    monkeypatch.setattr(AutonomousStore, 'append', forbidden)
    monkeypatch.setattr(service.store, '_publish', forbidden)
    monkeypatch.setattr(service, 'model', SimpleNamespace(infer=forbidden))
    if mode == 'recorded':
        monkeypatch.setattr(runtime, 'recompute_operations', forbidden)
        monkeypatch.setattr(runtime, 'capture_operation_inputs', forbidden)
    monkeypatch.setattr(runtime, 'PUBLIC_LIMITS', runtime.PublicOperationLimits())
    app = FastAPI()
    app.include_router(create_autonomous_router(lambda: service, corpus_getter=lambda: corpus, read_only=True))
    for encoding in ('identity', 'gzip'):
        status, headers, chunks = asyncio.run(raw_operations(app, cid, encoding, mode=mode))
        assert status == 200 and headers[b'x-casepath-operation-mode'] == mode.encode()
        assert b'content-length' not in headers
        body = gzip.decompress(b''.join(chunks)) if encoding == 'gzip' else b''.join(chunks)
        assert body == expected and sha256(body).digest() == sha256(expected).digest()
        result = json.loads(body.splitlines()[-1])
        assert result['state_sha256'] == head['state_sha256']
        assert result['trace_sha256'] == sidecar['frames'][-1]['trace_sha256']
        assert result['operation_chain_sha256'] == sidecar['frames'][-1]['operation_chain_sha256']
    assert service.store.events(cid) == before and service.store.get(cid) == head
    assert runtime.PUBLIC_LIMITS.active == 0


@pytest.fixture(scope='module')
def multi_family_history(tmp_path_factory):
    root = tmp_path_factory.mktemp('selected-knowledge-family')
    corpus = CanonicalCorpus()
    ids = ReferenceProfile().ids
    old = service_at(root / 'journal.sqlite', corpus, ReferenceProfile.for_profile('synthetic-nine-v1'))
    try:
        # The first three pinned claims publish the three distinct procedures;
        # the fourth receives the first family's exact historical definition.
        for cid in ids[:4]:
            admit(old, corpus, cid)
            previous = old.run(cid)
            assert previous['outcome']['assessment_status'] == 'complete'
    finally:
        old.shutdown()
    service = service_at(root / 'journal.sqlite', corpus)
    cid = ids[3]
    service.store.add_sources(cid, service.reference_adapter.profile.files(cid), expected_revision=previous['revision'],
                             expected_state_sha256=previous['state_sha256'], idempotency_key='selected-family-v2')
    head = service.run(cid)
    context = head['semantic_contexts'][head['run_id']]
    assert len({pin['family'] for pin in context['compatible_knowledge']}) == 3
    yield service, cid, head
    service.shutdown()


def test_capture_fetches_only_exact_selected_family_publisher(multi_family_history, monkeypatch):
    service, cid, head = multi_family_history
    statements = []
    original_connect = service.store.journal.connect
    class TrackedConnection:
        def __init__(self):
            self.connection = original_connect()
        def __enter__(self):
            self.connection.__enter__()
            return self
        def __exit__(self, *args):
            return self.connection.__exit__(*args)
        def __getattr__(self, name):
            return getattr(self.connection, name)
        def execute(self, sql, parameters=()):
            statements.append((sql, parameters))
            return self.connection.execute(sql, parameters)
    monkeypatch.setattr(service.store.journal, 'connect', TrackedConnection)
    bundle = runtime.capture_operation_inputs(service.store, cid, service.policy)
    peers = bundle['knowledge_histories']
    assert len(peers) == 1 and peers[0]['claim_id'] == ReferenceProfile().ids[0]
    journal_reads = [(sql, params) for sql, params in statements if '__max_count' in sql]
    fetched = {value for _, params in journal_reads for value in params if isinstance(value, str) and value.startswith('autonomous.')}
    assert fetched == {'autonomous.' + cid, 'autonomous.' + peers[0]['claim_id']}
    assert len(journal_reads) == 2
    assert len(statements) == 3 and all(sql.startswith('SELECT ') for sql, _ in statements)
    # The full frozen context still contains all three pins, unchanged.
    context = head['semantic_contexts'][head['run_id']]
    frozen = next(json.loads(row['event_json'])['payload']['context'] for row in reversed(bundle['rows'])
                  if json.loads(row['event_json'])['kind'] == 'work.context')
    assert frozen == context
    sidecar = runtime.build_operation_sidecar(bundle)
    assert sidecar['frames'][-1]['state_sha256'] == head['state_sha256']
    assert not any(frame.get('kind', '').startswith('branch.') for frame in sidecar['frames'])


def test_missing_or_tampered_relevant_pin_never_uses_another_version(multi_family_history):
    service, cid, head = multi_family_history
    bundle = runtime.capture_operation_inputs(service.store, cid, service.policy)
    missing = deepcopy(bundle)
    peer = missing['knowledge_histories'][0]
    publication = next(index for index, row in enumerate(peer['rows']) if json.loads(row['event_json'])['kind'] == 'knowledge.published')
    peer['rows'] = peer['rows'][:publication]
    # This is a valid native prefix without the pinned publication, rather
    # than a corrupt journal. A latest or other-family substitution must fail.
    with pytest.raises(runtime.OperationsUnavailable, match='pinned knowledge definition|exact required lineage'):
        runtime.build_operation_sidecar(missing)
    damaged = deepcopy(bundle)
    row = next(row for row in reversed(damaged['rows']) if json.loads(row['event_json'])['kind'] == 'work.context')
    event = json.loads(row['event_json'])
    pin = next(pin for pin in event['payload']['context']['compatible_knowledge'] if pin['family'] == head['graph']['family'])
    pin['knowledge_sha256'] = '0' * 64
    row['event_json'] = canonical_json_bytes(event).decode()
    with pytest.raises(ValueError):
        runtime.build_operation_sidecar(damaged)


def test_own_pinned_version_reuses_exact_nonreference_ancestor(tmp_path):
    from casepath_api.autonomous_knowledge_v1 import qualify, blank_interpretation
    from casepath_api.autonomous_policy_v1 import compile_process, receipt
    corpus = CanonicalCorpus()
    old = service_at(tmp_path / 'foreign-ancestor.sqlite', corpus, ReferenceProfile.for_profile('synthetic-nine-v1'))
    try:
        store = old.store
        historical = store.intake({'title': 'Historical admitted procedure', 'message': 'A legacy procedural qualification.', 'files': []},
                                  'foreign-procedure-intake')
        foreign_id = historical['claim_id']
        workflow = 'autonomy.foreign-procedure'
        def append(kind, payload, key):
            state = store.get(foreign_id)
            return store.append(foreign_id, kind, payload(state) if callable(payload) else payload,
                                expected_revision=state['revision'], expected_state_sha256=state['state_sha256'], idempotency_key=key)
        append('work.started', {'run_id': workflow, 'policy_id': old.policy_id}, workflow + '.start')
        graph, facts, obligations = compile_process(old.policy, foreign_id, blank_interpretation('lease_termination_dispute'))
        append('process.prepared', lambda state: {'graph': graph, 'facts': facts, 'obligations': obligations,
               'receipt': receipt(state, 'historical_procedure', after_graph_sha256=graph['graph_sha256'])}, workflow + '.prepare')
        historical = append('outcome.recorded', lambda state: {'outcome': {'status': 'deferred', 'summary': 'No case outcome is established.'},
                            'receipt': receipt(state, 'historical_deferral')}, workflow + '.outcome')
        version = qualify(old.policy, historical, candidates=[])
        version['knowledge_sha256'] = digest_value(version)
        append('knowledge.published', {'knowledge': version}, workflow + '.knowledge')
        assert foreign_id not in ReferenceProfile().ids and version['version'] == 1 and not version['evidence_recipes']
        cid = ReferenceProfile().ids[0]
        admit(old, corpus, cid)
        previous = old.run(cid)
        version2 = previous['knowledge_published'][0]
        assert version2['version'] == 2 and version2['parent_knowledge_sha256'] == version['knowledge_sha256']
    finally:
        old.shutdown()
    service = service_at(tmp_path / 'foreign-ancestor.sqlite', corpus)
    try:
        service.store.add_sources(cid, service.reference_adapter.profile.files(cid), expected_revision=previous['revision'],
                                 expected_state_sha256=previous['state_sha256'], idempotency_key='foreign-parent-cleaned-v2')
        head = service.run(cid)
        pin = next(pin for pin in head['semantic_contexts'][head['run_id']]['compatible_knowledge'] if pin['family'] == head['graph']['family'])
        assert pin['version'] == 2 and pin['knowledge_sha256'] == version2['knowledge_sha256']
        bundle = runtime.capture_operation_inputs(service.store, cid, service.policy)
        assert [peer['claim_id'] for peer in bundle['knowledge_histories']] == [foreign_id]
        sidecar = runtime.build_operation_sidecar(bundle)
        assert sidecar['frames'][0]['instrumentation_id'] == runtime.INSTRUMENTATION_ID
        assert sidecar['frames'][-1]['state_sha256'] == head['state_sha256']
        reuse = next(frame for frame in sidecar['frames'] if frame.get('kind') == 'knowledge.reuse')
        assert reuse['input']['version'] == 2 and reuse['input']['knowledge_sha256'] == version2['knowledge_sha256']
        # Historical source/controller operations never appear in this trace.
        assert all(frame.get('object', {}).get('id') != foreign_id for frame in sidecar['frames'])
        unrelated = deepcopy(bundle)
        unrelated['knowledge_histories'].append({'claim_id': 'auto_' + '0' * 24,
                                                'rows': bundle['knowledge_histories'][0]['rows'],
                                                'sources_base64': bundle['knowledge_histories'][0]['sources_base64']})
        with pytest.raises(ValueError):
            runtime.build_operation_sidecar(unrelated)
    finally:
        service.shutdown()


def test_working_evaluation_is_exact_provisional_and_override_scoped():
    definition = graph()
    sink = runtime.OperationSink()
    with sink.scope('native_execution', 2):
        false_result = evaluate(definition, {'branch': 'false'})
        true_result = evaluate(definition, {'branch': 'true'})
        assert evaluate(definition, {'branch': 'true'}) == true_result
    inspections = [frame for frame in sink.frames if frame.get('kind') == 'process.inspect']
    assert len(inspections) == 2
    assert len({frame['result']['evaluation_sha256'] for frame in inspections}) == 2
    expected_graph = {key: definition[key] for key in ('contract', 'family', 'claim_id', 'revision', 'graph_sha256',
                                                     'conditions', 'nodes', 'edges', 'document_catalog')}
    assert all(frame['result']['graph'] == expected_graph for frame in inspections)
    assert inspections[0]['result']['effective_conditions']['branch']['verdict'] == 'false'
    assert inspections[1]['result']['effective_conditions']['branch']['verdict'] == 'true'
    expected_by_evaluation = {inspections[0]['result']['evaluation_sha256']: false_result,
                              inspections[1]['result']['evaluation_sha256']: true_result}
    inspect_by_evaluation = {frame['result']['evaluation_sha256']: frame['id'] for frame in inspections}
    for frame in sink.frames:
        if frame.get('kind') not in {'node.evaluate', 'document.require', 'dependency.evaluate', 'branch.activate', 'branch.drop', 'branch.evaluate'}:
            continue
        result = frame['result']
        evaluation = result['evaluation_sha256']
        assert result['phase'] == 'provisional' and result['graph_sha256'] == definition['graph_sha256']
        assert inspect_by_evaluation[evaluation] in frame['cause_ids']
        if frame['kind'] == 'node.evaluate':
            actual = next(node for node in expected_by_evaluation[evaluation]['nodes'] if node['node_id'] == frame['object']['id'])
            for key in ('activation', 'execution_state', 'effective_completed', 'inconsistent_completion', 'blocked_by', 'unresolved_dependencies'):
                assert result[key] == actual[key]
        elif frame['kind'] == 'document.require':
            actual = next(doc for doc in expected_by_evaluation[evaluation]['documents'] if doc['document_type'] == frame['object']['id'])
            for key in ('activation', 'route_state', 'request', 'review_state', 'required_at_node_ids', 'active_node_ids'):
                assert result[key] == actual[key]
    blocked = [frame for frame in sink.frames if frame.get('kind') == 'node.evaluate'
               and frame['object']['id'] == 'down' and frame['result']['evaluation_sha256'] == inspections[1]['result']['evaluation_sha256']]
    assert blocked and all(frame['result']['activation'] == 'true' and frame['result']['execution_state'] == 'blocked'
                           and frame['result']['blocked_by'] == ['left'] and not frame['result']['effective_completed'] for frame in blocked)


def test_capture_sql_guards_oversized_wire_before_returning_bodies(migrated, monkeypatch):
    service, _, cid, _, _ = migrated
    original_connect = service.store.journal.connect
    local = sqlite3.connect(':memory:')
    local.row_factory = sqlite3.Row
    local.execute('CREATE TABLE claim_loop_events AS SELECT NULL AS session_id,NULL AS loop_id,NULL AS sequence,NULL AS idempotency_key,NULL AS command_sha256,NULL AS event_sha256,NULL AS event_json,NULL AS created_at WHERE 0')
    for row in migrated[-1]['rows']:
        local.execute('INSERT INTO claim_loop_events VALUES (?,?,?,?,?,?,?,?)', tuple(row[key] for key in ('session_id','loop_id','sequence','idempotency_key','command_sha256','event_sha256','event_json','created_at')))
    statements = []
    class RestrictedConnection:
        def __enter__(self):
            self.connection = local
            return self
        def __exit__(self, *args):
            return None
        def execute(self, statement, params):
            statements.append(statement)
            # An authority column, not event_json, can alone exceed the
            # conservative hosted wire budget. The guarded result omits all
            # actual columns before the client receives them.
            self.connection.execute('UPDATE claim_loop_events SET idempotency_key=? WHERE loop_id=? AND sequence=1',
                                    ('é' * (3 * 1024 * 1024), 'autonomous.' + cid))
            page = self.connection.execute(statement, params).fetchall()
            assert page and page[0]['__wire'] > 32 * 1024 * 1024 - 65536
            assert all(row['event_json'] is None and row['idempotency_key'] is None for row in page)
            return SimpleNamespace(fetchall=lambda: page)
    monkeypatch.setattr(service.store.journal, 'connect', RestrictedConnection)
    monkeypatch.setattr(service.store, '_blob', lambda digest: (_ for _ in ()).throw(AssertionError('Source I/O before journal bound')))
    try:
        with pytest.raises(runtime.OperationsUnavailable, match='wire bound'):
            runtime.capture_operation_inputs(service.store, cid, service.policy)
    finally:
        monkeypatch.setattr(service.store.journal, 'connect', original_connect)
        local.close()
    assert len(statements) == 1


def test_capture_fresh_verifies_union_sources_once(multi_family_history, monkeypatch):
    service, cid, head = multi_family_history
    baseline = runtime.capture_operation_inputs(service.store, cid, service.policy)
    cached = {digest: base64.b64decode(value) for snapshot in [baseline, *baseline['knowledge_histories']]
              for digest, value in snapshot['sources_base64'].items()}
    calls = []
    def verify(digests):
        calls.append(set(digests))
    reader = SimpleNamespace(verify_many=verify, read=lambda digest: cached[digest])
    monkeypatch.setattr(service.store, '_source_store', reader)
    bundle = runtime.capture_operation_inputs(service.store, cid, service.policy)
    assert calls == [set(cached)]
    assert runtime.build_operation_sidecar(bundle)['frames'][-1]['state_sha256'] == head['state_sha256']
