"""Real deterministic execution, immutable checkpoints, and public read boundaries."""
from copy import deepcopy
from hashlib import sha256
import json
import base64
import sqlite3
from types import SimpleNamespace
from threading import Event
from time import monotonic

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
            'condition.evaluate', 'branch.activate', 'document.require', 'document.check', 'step.complete', 'decision', 'knowledge.reuse'} <= kinds
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
        assert statements and all(sql.split()[0] in {'SELECT', 'BEGIN', 'COMMIT', 'ROLLBACK'} for sql in statements)
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
