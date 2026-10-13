"""Optional real engine observations and bounded, write-free historical recomputation.

The sidecar is a newly computed trace, never an assertion that an old journal
captured these operations. Journals remain the lifecycle authority.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from hashlib import sha256
import base64
import json
from threading import Event, Lock, RLock
from time import monotonic

from .workspace_corpus import canonical_json_bytes, digest_value

CONTRACT = 'casepath.operations-stream/1.0.0'
BUNDLE_CONTRACT = 'casepath.operation-inputs/1.0.0'
SIDECAR_CONTRACT = 'casepath.operation-sidecar/1.0.0'
MAX_SECONDS = 10.0
MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_OUTPUT_BYTES = 24 * 1024 * 1024
MAX_OPERATIONS = 10_000
MAX_EVENTS = 256
_SINK = ContextVar('casepath_engine_operation_sink', default=None)


class OperationsUnavailable(ValueError):
    pass


class OperationCancelled(RuntimeError):
    pass


def observe(kind, object_type, object_id, inputs, result, *, source=None, causes=()):
    sink = _SINK.get()
    if sink is not None:
        return sink.emit(kind, object_type, object_id, inputs, result, source=source, causes=causes)
    return None


def observing():
    return _SINK.get() is not None


@contextmanager
def suspend_observations():
    token = _SINK.set(None)
    try:
        yield
    finally:
        _SINK.reset(token)


def citation_source(citation, sources):
    if not citation or not observing():
        return None
    source = next((row for row in sources if row['artifact_id'] == citation['artifact_id']), None)
    if source is None:
        raise ValueError('operation citation source is unavailable')
    quote = citation['quote']
    start = citation.get('start_char', source['text'].find(quote))
    end = citation.get('end_char', start + len(quote))
    if type(start) is not int or type(end) is not int or start < 0 or source['text'][start:end] != quote:
        raise ValueError('operation citation is not an exact source span')
    return {'artifact_id': source['artifact_id'], 'sha256': source['sha256'],
            'text_sha256': sha256(source['text'].encode()).hexdigest(),
            'start_char': start, 'end_char': end, 'offset_unit': 'unicode_code_point', 'quote': quote}


class OperationSink:
    def __init__(self, send=None, *, cancellation=None, deadline=None):
        self.send = send or (lambda frame: None)
        self.cancel = cancellation or Event()
        self.deadline = deadline if deadline is not None else monotonic() + MAX_SECONDS
        self.frames, self.frame_hashes, self.previous, self.sequence, self.bytes = [], [], None, 0, 0
        self.retain = send is None
        self.stage, self.journal_seq = 'validation', None
        self.latest, self.opened, self.occurrences = {}, {}, {}

    def check(self):
        if self.cancel.is_set() or monotonic() >= self.deadline:
            raise OperationCancelled('Recomputation stopped before completion.')

    def frame(self, frame_type, **value):
        self.check()
        row = {'contract': CONTRACT, 'type': frame_type, **deepcopy(value)}
        self.bytes += len(canonical_json_bytes(row)) + 1
        if self.bytes > MAX_OUTPUT_BYTES:
            raise OperationCancelled('Recomputation exceeded the output bound.')
        if self.retain:
            self.frames.append(row)
        self.frame_hashes.append(digest_value(row))
        self.send(row)
        return row

    @contextmanager
    def scope(self, stage, journal_seq):
        old = self.stage, self.journal_seq
        self.stage, self.journal_seq = stage, journal_seq
        token = _SINK.set(self)
        try:
            self.check()
            yield
        finally:
            _SINK.reset(token)
            self.stage, self.journal_seq = old

    def emit(self, kind, object_type, object_id, inputs, result, *, source=None, causes=()):
        self.check()
        if kind == 'source.open':
            identity = (self.stage, object_id)
            if identity in self.opened:
                return self.opened[identity]
        self.sequence += 1
        if self.sequence > MAX_OPERATIONS:
            raise OperationCancelled('Recomputation exceeded the operation bound.')
        predecessors = list(dict.fromkeys(item for item in causes if item))
        if source:
            predecessor = self.latest.get(('span', source['artifact_id'], source['start_char'], source['end_char']))
            if predecessor and predecessor not in predecessors:
                predecessors.append(predecessor)
        identity = digest_value({'kind': kind, 'stage': self.stage, 'object': {'type': object_type, 'id': object_id},
                                 'input_sha256': digest_value(inputs), 'result_sha256': digest_value(result), 'source': source})
        occurrence = self.occurrences.get(identity, 0) + 1
        self.occurrences[identity] = occurrence
        material = {'seq': self.sequence, 'id': 'op_' + digest_value({'semantic_sha256': identity, 'occurrence': occurrence})[:32], 'kind': kind,
                    'cause_ids': predecessors, 'object': {'type': object_type, 'id': object_id},
                    'stage': self.stage, 'journal_seq': self.journal_seq,
                    'input': deepcopy(inputs), 'result': deepcopy(result),
                    'input_sha256': digest_value(inputs), 'result_sha256': digest_value(result),
                    'previous_operation_sha256': self.previous}
        if source is not None:
            material['source'] = deepcopy(source)
        # Hash the operation payload; the transport contract/type are excluded.
        material['operation_sha256'] = digest_value(material)
        self.previous = material['operation_sha256']
        self.latest[(object_type, object_id)] = material['id']
        if kind == 'source.open':
            self.opened[(self.stage, object_id)] = material['id']
        if source and kind in {'span.read', 'phrase.match'}:
            self.latest[('span', source['artifact_id'], source['start_char'], source['end_char'])] = material['id']
        self.frame('operation', **material)
        return material['id']


def _memory_store(blobs, check=lambda: None):
    """Use native validation/reduction without invoking a store constructor."""
    from .autonomous_store_v1 import AutonomousStore, AutonomousStoreError
    class BytesOnly:
        def read(self, digest):
            try:
                return blobs[digest]
            except KeyError as error:
                raise AutonomousStoreError('snapshot source bytes are unavailable') from error
    class MemoryReducer(AutonomousStore):
        def _reduce(self, state, event):
            check()
            return super()._reduce(state, event)
    store = MemoryReducer.__new__(MemoryReducer)
    store._read_only, store.storage, store._source_store = True, None, BytesOnly()
    store._extractions, store._extraction_lock = {}, RLock()
    store._summary_lock = RLock()
    return store


def capture_operation_inputs(store, claim_id, policy, *, check=lambda: None):
    """Freeze one journal read snapshot and its exact immutable bytes in memory."""
    from .autonomous_reference_v1 import ReferenceProfile
    if claim_id not in ReferenceProfile().ids:
        raise OperationsUnavailable('This claim is outside the nine reference profiles.')
    collected = [len(canonical_json_bytes(policy))]
    def reserve(size):
        collected[0] += size
        if collected[0] > MAX_INPUT_BYTES:
            raise OperationsUnavailable('Snapshot exceeds the input bound.')
    def bounded_rows(connection, cid):
        from .autonomous_store_v1 import SESSION_ID
        check()
        metadata = connection.execute('SELECT COUNT(*) AS n,COALESCE(SUM(length(CAST(event_json AS BLOB))),0) AS bytes '
                                      'FROM claim_loop_events WHERE session_id=? AND loop_id=?',
                                      (SESSION_ID, 'autonomous.' + cid)).fetchone()
        if metadata['n'] > MAX_EVENTS or metadata['bytes'] > MAX_INPUT_BYTES - collected[0]:
            raise OperationsUnavailable('Snapshot journal exceeds the input bound.')
        check()
        rows = [dict(row) for row in connection.execute(
            'SELECT * FROM claim_loop_events WHERE session_id=? AND loop_id=? ORDER BY sequence LIMIT ?',
            (SESSION_ID, 'autonomous.' + cid, MAX_EVENTS + 1)).fetchall()]
        if len(rows) > MAX_EVENTS:
            raise OperationsUnavailable('Snapshot journal exceeds the event bound.')
        return rows
    def capture_blobs(source_rows, cid):
        descriptors = {}
        for row in source_rows:
            check()
            event = json.loads(row['event_json'])
            if event['claim_id'] != cid:
                raise OperationsUnavailable('Snapshot contains another claim.')
            if event['kind'] in {'intake', 'sources.arrived'}:
                for descriptor in event['payload']['sources']:
                    store._descriptor_metadata(descriptor, cid)
                    digest = descriptor['sha256']
                    if digest not in descriptors:
                        reserve(4 * ((descriptor['size_bytes'] + 2) // 3) + 80)
                        descriptors[digest] = descriptor
        persistent = getattr(store, '_source_store', None)
        if persistent is not None and hasattr(persistent, 'verify_many'):
            # Preserve the native fresh persistent-roster check; an extraction
            # or hosted byte cache cannot mask missing/tampered remote chunks.
            check()
            from .hosted_storage_v1 import HostedSources
            if isinstance(persistent, HostedSources):
                persistent.verify_many(descriptors, check=check)
            else:
                persistent.verify_many(descriptors)
        result = {}
        for digest in descriptors:
            check()
            result[digest] = base64.b64encode(store._blob(digest)).decode()
        return result
    check()
    with store.journal.connect() as connection:
        connection.execute('BEGIN')
        rows = bounded_rows(connection, claim_id)
        connection.commit()
    if not rows or len(rows) > MAX_EVENTS:
        raise OperationsUnavailable('A bounded saved reference history is required.')
    reserve(len(canonical_json_bytes(rows)))
    blobs = capture_blobs(rows, claim_id)
    bundle = {'contract': BUNDLE_CONTRACT, 'claim_id': claim_id, 'rows': rows,
              'sources_base64': blobs, 'policy': deepcopy(policy), 'knowledge_histories': []}
    contexts = [json.loads(row['event_json'])['payload']['context'] for row in rows
                if json.loads(row['event_json'])['kind'] == 'work.context']
    pinned = {value['knowledge_sha256'] for context in contexts[-1:]
              for value in context.get('compatible_knowledge', []) if value.get('knowledge_sha256')}
    own = {json.loads(row['event_json'])['payload']['knowledge'].get('knowledge_sha256') for row in rows
           if json.loads(row['event_json'])['kind'] == 'knowledge.published'}
    missing = pinned - own
    # Resolve only exact pinned definitions; peer journals are frozen too and
    # natively replayed, never replaced with today's latest knowledge version.
    for peer in ReferenceProfile().ids:
        if not missing or peer == claim_id:
            continue
        check()
        with store.journal.connect() as connection:
            peer_rows = bounded_rows(connection, peer)
        peer_versions = {json.loads(row['event_json'])['payload']['knowledge'].get('knowledge_sha256')
                         for row in peer_rows if json.loads(row['event_json'])['kind'] == 'knowledge.published'}
        if not peer_versions & missing:
            continue
        reserve(len(canonical_json_bytes(peer_rows)))
        peer_blobs = capture_blobs(peer_rows, peer)
        bundle['knowledge_histories'].append({'claim_id': peer, 'rows': peer_rows, 'sources_base64': peer_blobs})
        missing -= peer_versions
    if missing:
        raise OperationsUnavailable('Exact historical knowledge version is unavailable.')
    if len(canonical_json_bytes(bundle)) > MAX_INPUT_BYTES:
        raise OperationsUnavailable('Snapshot exceeds the input bound.')
    return bundle


def operation_inputs_from_export(snapshot, raw_sources, policy, *, knowledge_snapshots=()):
    """Freeze authorized API exports without opening or modifying a journal.

    ``raw_sources`` maps ``claim_id/artifact_id`` to canonical base64 bytes.
    ``knowledge_snapshots`` supplies other authorized nine-claim snapshots when
    the selected context pins a procedure published by another claim.
    """
    event_fields = {'contract', 'session_id', 'claim_id', 'kind', 'payload', 'expected_revision',
                    'expected_state_sha256', 'sequence', 'command_sha256', 'idempotency_key',
                    'previous_event_sha256', 'created_at', 'event_sha256', 'resulting_state_sha256'}
    def convert(value):
        cid = value['state']['claim_id']
        rows, blobs = [], {}
        for envelope in value['events']:
            event = {key: row for key, row in envelope.items() if key in event_fields}
            rows.append({'session_id': event['session_id'], 'loop_id': 'autonomous.' + cid,
                         **{key: event[key] for key in ('sequence', 'command_sha256', 'event_sha256', 'idempotency_key', 'created_at')},
                         'event_json': canonical_json_bytes(event).decode()})
            if event['kind'] in {'intake', 'sources.arrived'}:
                for descriptor in event['payload']['sources']:
                    blobs[descriptor['sha256']] = raw_sources[cid + '/' + descriptor['artifact_id']]
        return {'claim_id': cid, 'rows': rows, 'sources_base64': blobs}
    main = convert(snapshot)
    pinned = {pin.get('knowledge_sha256') for pin in snapshot['state']['semantic_contexts'][snapshot['state']['run_id']].get('compatible_knowledge', [])}
    own = {value.get('knowledge_sha256') for value in snapshot['state']['knowledge_published']}
    peers = []
    for value in knowledge_snapshots:
        if value['state']['claim_id'] == main['claim_id']:
            continue
        published = {version.get('knowledge_sha256') for version in value['state']['knowledge_published']}
        if published & (pinned - own):
            peers.append(convert(value))
            own |= published
    bundle = {'contract': BUNDLE_CONTRACT, **main, 'policy': deepcopy(policy), 'knowledge_histories': peers}
    if len(canonical_json_bytes(bundle)) > MAX_INPUT_BYTES:
        raise OperationsUnavailable('Authorized export exceeds the input bound.')
    return bundle


def _validated(bundle, sink):
    from .autonomous_reference_v1 import ReferenceProfile, reference_replay_start
    if bundle.get('contract') != BUNDLE_CONTRACT or bundle.get('claim_id') not in ReferenceProfile().ids:
        raise OperationsUnavailable('Only the nine reference profiles can be recomputed.')
    if len(canonical_json_bytes(bundle)) > MAX_INPUT_BYTES or not 0 < len(bundle['rows']) <= MAX_EVENTS:
        raise OperationsUnavailable('Snapshot exceeds the input bound.')
    blobs = {digest: base64.b64decode(value, validate=True) for digest, value in bundle['sources_base64'].items()}
    if any(sha256(raw).hexdigest() != digest for digest, raw in blobs.items()):
        raise OperationsUnavailable('Snapshot source hash differs.')
    store = _memory_store(blobs, sink.check)
    # Every saved prefix uses the existing hash-chain and native reducer checks.
    sink.check()
    head, events, states = store._replay(bundle['rows'], with_history=True)
    sink.check()
    start = reference_replay_start(head, events)
    if start is None:
        raise OperationsUnavailable('No current reference replay run is available.')
    policy = bundle['policy']
    context = head['semantic_contexts'][start['run_id']]
    if (head['claim_id'] != bundle['claim_id'] or digest_value(policy) != context['reference_provenance']['rule_set_sha256']
            or policy['policy_id'] != context['policy_id']):
        raise OperationsUnavailable('Snapshot rule identity differs.')
    knowledge = [row['payload']['knowledge'] for row in events
                 if row['kind'] == 'knowledge.published' and row['sequence'] < start['from_seq']]
    for peer in bundle.get('knowledge_histories', []):
        if (peer['claim_id'] not in ReferenceProfile().ids or peer['claim_id'] == bundle['claim_id']
                or not 0 < len(peer['rows']) <= MAX_EVENTS):
            raise OperationsUnavailable('Historical knowledge snapshot is outside the allowlist.')
        peer_blobs = {digest: base64.b64decode(value, validate=True) for digest, value in peer['sources_base64'].items()}
        if any(sha256(raw).hexdigest() != digest for digest, raw in peer_blobs.items()):
            raise OperationsUnavailable('Historical knowledge bytes differ.')
        peer_head, _, _ = _memory_store(peer_blobs, sink.check)._replay(peer['rows'])
        if peer_head['claim_id'] != peer['claim_id']:
            raise OperationsUnavailable('Historical knowledge snapshot belongs to another claim.')
        knowledge.extend(peer_head['knowledge_published'])
    from .autonomous_knowledge_v1 import _definition
    pinned = context.get('compatible_knowledge', [])
    for pin in pinned:
        versions = [version for version in knowledge if version.get('knowledge_id') == pin['knowledge_id']
                    and version.get('version') == pin['version'] and version.get('knowledge_sha256') == pin['knowledge_sha256']]
        if len(versions) != 1:
            raise OperationsUnavailable('Exact pinned knowledge definition is missing or ambiguous.')
        _definition(versions[0])
        if any(versions[0].get(key) != pin.get(key) for key in ('family', 'rule_pack_sha256', 'evidence_recipes', 'knowledge_sha256')):
            raise OperationsUnavailable('Pinned knowledge metadata differs from its exact definition.')
    ceilings = {pin['knowledge_id']: pin['version'] for pin in pinned}
    knowledge = [version for version in knowledge if version.get('qualification', {}).get('status') == 'qualified'
                 and version.get('knowledge_id') in ceilings and version.get('version', 0) <= ceilings[version['knowledge_id']]]
    return store, head, events, states, start, context, knowledge


def recompute_operations(bundle, *, send=None, cancellation=None, deadline=None):
    """Reexecute native callsites against a command-comparing in-memory facade."""
    from .autonomous_reference_v1 import DeterministicReferenceAdapter, ReferenceProfile
    from .autonomous_controller_v1 import AutonomousController, execution_capability
    from .autonomous_knowledge_v1 import AutonomousKnowledge
    from .autonomous_policy_v1 import compile_verification_proposal, validate_interpretation
    sink = OperationSink(send, cancellation=cancellation, deadline=deadline)
    store, head, events, states, start, context, versions = _validated(deepcopy(bundle), sink)
    binding = {'claim_id': head['claim_id'], 'run_id': start['run_id'], 'mode': 'historical_recomputed',
               'newly_recomputed': True, 'input_sha256': digest_value(bundle),
               'profile_id': start['profile_id'], 'profile_sha256': start['profile_sha256'],
               'source_roster_sha256': head['source_roster_sha256'], 'rule_set_sha256': digest_value(bundle['policy']),
               'from_seq': start['from_seq'], 'current_revision': head['revision'],
               'current_state_sha256': head['state_sha256'], 'current_event_sha256': head['last_event_sha256']}
    sink.frame('binding', **binding)
    adapter = DeterministicReferenceAdapter(bundle['policy'], ReferenceProfile.for_profile(start['profile_id']))
    previous_checkpoint = None

    def checkpoint(state, event):
        nonlocal previous_checkpoint
        value = {'journal_seq': event['sequence'], 'through_seq': event['sequence'],
                 'event_sha256': event['event_sha256'], 'state_sha256': state['state_sha256'], 'verified': True,
                 'events': [{**event, 'seq': event['sequence'], 'revision': event['sequence'],
                             'timestamp': event['created_at'], 'state_sha256': event['resulting_state_sha256']}],
                 'replay_only': True, 'mode': 'replay', 'cursor_sha256': event['event_sha256'],
                 'current_revision': head['revision'], 'current_state_sha256': head['state_sha256'],
                 'current_event_sha256': head['last_event_sha256'], 'replay_start': start,
                 'provenance': store._provenance(state),
                 'projection': {'revision': state['revision'], 'state_sha256': state['state_sha256'],
                                'node_capabilities': {node['node_id']: execution_capability(node['node_id'])
                                                      for node in (state['graph'] or {}).get('nodes', [])}}}
        if previous_checkpoint is None:
            value['state'] = state
        else:
            value['base_state_sha256'] = previous_checkpoint['state_sha256']
            value['state_delta'] = {'set': {key: row for key, row in state.items() if previous_checkpoint.get(key) != row},
                                    'remove': [key for key in previous_checkpoint if key not in state]}
        sink.frame('checkpoint', **value)
        previous_checkpoint = state

    class ExecutionMemory:
        def __init__(self, index):
            self.index = index
            self.state = states[index - 1] if index else None

        def get(self, claim_id):
            sink.check()
            if claim_id != head['claim_id']:
                raise OperationsUnavailable('Execution crossed the frozen claim boundary.')
            sink.journal_seq = self.index + 1
            return deepcopy(self.state)

        def events(self, claim_id):
            self.get(claim_id)
            return events[:self.index]

        def validated_states(self):
            # Exact frozen versions, rather than mutable latest knowledge.
            return [{'claim_id': 'frozen-procedures', 'knowledge_published': versions, 'knowledge_uses': []}]

        def _validate_descriptor(self, descriptor, claim_id):
            return store._validate_descriptor(descriptor, claim_id)

        def _extract(self, raw, media):
            return store._extract(raw, media)

        def append(self, claim_id, kind, payload, *, expected_revision, expected_state_sha256, idempotency_key):
            self.get(claim_id)
            if self.index >= len(events):
                raise OperationsUnavailable('Recomputation proposed an unsaved command.')
            event = events[self.index]
            computed = {'kind': kind, 'payload': payload, 'expected_revision': expected_revision,
                        'expected_state_sha256': expected_state_sha256}
            if (idempotency_key != event['idempotency_key'] or digest_value(computed) != event['command_sha256']
                    or any(computed[key] != event[key] for key in computed)):
                raise OperationsUnavailable('Computed native command differs from accepted historical bytes.')
            candidate = store._reduce(self.state, event)
            if candidate != states[self.index] or candidate['state_sha256'] != event['resulting_state_sha256']:
                raise OperationsUnavailable('Computed native command checkpoint differs.')
            self.state, self.index = candidate, self.index + 1
            checkpoint(candidate, event)
            return deepcopy(candidate)

    accepted = next(event for event in events if event['idempotency_key'] == start['run_id'] + '.interpretation')
    applying = next((event for event in events if event['idempotency_key'] == start['run_id'] + '.reuse'), accepted)
    # Prefixes before the selected run are verified above, never instrumented.
    for event in events[start['from_seq'] - 1:applying['sequence'] - 1]:
        with sink.scope('native_reducer', event['sequence']):
            prior = states[event['sequence'] - 2] if event['sequence'] > 1 else None
            computed = store._reduce(prior, event)
        if computed != states[event['sequence'] - 1]:
            raise OperationsUnavailable('Selected run prefix differs.')
        checkpoint(computed, event)

    memory = ExecutionMemory(applying['sequence'] - 1)
    identity = {'workflow_id': start['run_id'], 'claim_id': head['claim_id'], 'policy_id': context['policy_id'],
                'source_roster_sha256': head['source_roster_sha256'], 'rule_set_sha256': digest_value(bundle['policy'])}
    with sink.scope('interpret_reference', accepted['sequence']):
        proposal = adapter.interpret_reference(context, identity)
    with sink.scope('verify_reference', accepted['sequence']):
        verifier = adapter.verify_reference(context, proposal['result'], identity)
        compiled, compilation = compile_verification_proposal(context, proposal['result'])
        verified = validate_interpretation(bundle['policy'], memory.state['acquired_sources'], compiled, verifier['result'])
    receipt = accepted['payload']['receipt']
    if (proposal['receipt'] != receipt['proposal_receipt'] or verifier['receipt'] != receipt['verifier_receipt']
            or digest_value(proposal['result']) != receipt['proposal_sha256']
            or digest_value(verifier['result']) != receipt['verifier_sha256']):
        raise OperationsUnavailable('New reference computation differs from accepted verification.')
    # No controller constructor, executor, provider, or persistent writer.
    controller = AutonomousController.__new__(AutonomousController)
    controller.store, controller.policy, controller.policy_id = memory, bundle['policy'], context['policy_id']
    controller.reference_adapter, controller.model = adapter, None
    controller.knowledge = AutonomousKnowledge(memory, bundle['policy'])
    controller._lock, controller._contexts, controller._closed = RLock(), {start['run_id']: head['source_roster_sha256']}, False
    controller.enforce_intake_gate = True
    with sink.scope('native_execution', applying['sequence']):
        controller._apply_verified(head['claim_id'], start['run_id'], context, proposal, verifier, verified, compilation)
    # Historical ancillary events may follow a completed native execution.
    for event in events[memory.index:]:
        sink.check()
        if event['kind'] in {'action.completed', 'interpretation.accepted', 'outcome.recorded'}:
            raise OperationsUnavailable('Native execution did not compute every selected accepted command.')
        candidate = store._reduce(memory.state, event)
        if candidate != states[event['sequence'] - 1]:
            raise OperationsUnavailable('Historical suffix differs.')
        memory.state, memory.index = candidate, event['sequence']
        checkpoint(candidate, event)
    if memory.state != head:
        raise OperationsUnavailable('Final exact output differs from the saved head.')
    trace_hash = digest_value(sink.frame_hashes)
    sink.frame('result', state_sha256=head['state_sha256'], current_revision=head['revision'],
               current_event_sha256=head['last_event_sha256'], exact_output_verified=True, operation_count=sink.sequence,
               operation_chain_sha256=sink.previous, trace_sha256=trace_hash)
    return sink.frames


def build_operation_sidecar(bundle):
    """Build a content-addressed sidecar from an authorized exported input bundle."""
    frames = recompute_operations(bundle)
    value = {'contract': SIDECAR_CONTRACT, 'input_sha256': digest_value(bundle), 'frames': frames}
    return {**value, 'sidecar_sha256': digest_value(value)}


def verify_operation_sidecar(bundle, sidecar):
    """Verify chain, every checkpoint, source bytes, and freshly computed semantics."""
    expected = build_operation_sidecar(bundle)
    if sidecar != expected:
        raise OperationsUnavailable('Operation sidecar differs from exact recomputation.')
    return {'verified': True, 'sidecar_sha256': expected['sidecar_sha256'],
            'state_sha256': expected['frames'][-1]['state_sha256']}


class PublicOperationLimits:
    """Global totals and concurrency do not depend on a visitor-supplied identity."""
    def __init__(self, *, concurrency=2, total=12, window_seconds=60):
        self.concurrency, self.total, self.window_seconds = concurrency, total, window_seconds
        self.active, self.starts, self.lock = 0, [], Lock()

    def acquire(self):
        with self.lock:
            now = monotonic()
            self.starts = [stamp for stamp in self.starts if now - stamp < self.window_seconds]
            if self.active >= self.concurrency or len(self.starts) >= self.total:
                return False
            self.active += 1
            self.starts.append(now)
            return True

    def release(self):
        with self.lock:
            self.active -= 1


PUBLIC_LIMITS = PublicOperationLimits()
