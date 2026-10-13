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
