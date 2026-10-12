#!/usr/bin/env python3
"""Private operator prepare/apply for exact synthetic reference journal appends.

prepare reads the existing private database and executes only in disposable
SQLite. apply inserts that reviewed, hash-bound plan under the existing hosted
lease and journal CAS. It never creates an HTTP route or a provider allowance.
"""
import argparse
import base64
from contextlib import closing
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import runpy
import sqlite3
import subprocess
import sys
import tempfile
from threading import RLock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'casepath-api'))
from casepath_api.agent_work.store import WorkStore
from casepath_api.autonomous_controller_v1 import AutonomousController
from casepath_api.autonomous_corpus_v1 import CanonicalCorpus
from casepath_api.autonomous_reference_v1 import DeterministicReferenceAdapter, ReferenceProfile
from casepath_api.autonomous_reference_policy_v1 import bounded_reference_policy
from casepath_api.autonomous_store_v1 import AutonomousStore, SESSION_ID
from casepath_api.hosted_lease_v1 import HostedWorkflowLease, _CURRENT_OWNER
from casepath_api.hosted_storage_v1 import HostedSources, HostedAutonomousStore, JOURNAL_SCHEMA
from casepath_api.hosted_sql_v1 import MAX_BYTES
from casepath_api.workspace_corpus import digest_value

_migration = runpy.run_path(str(Path(__file__).with_name('migrate_hosted.py')))
q, schema_objects, table_info, table_digest, insert_sql = (
    _migration[k] for k in ('q', 'schema_objects', 'table_info', 'table_digest', 'insert_sql'))
CONTRACT = 'casepath.reference-admission-plan/1.0.0'


class Refused(RuntimeError):
    pass


def _wire_bound_sql(columns):
    """Conservative typed-cell JSON size, including UTF-8, NUL and base64.

    JSON escaping needs at most six bytes per UTF-8 byte (including controls,
    quotes and supplementary Unicode). Base64 has its exact four-per-three
    bound. Sixty-four bytes cover each typed cell's metadata and any finite
    signed-64 integer/float/null representation. Include row separators and
    reserve envelope/column metadata separately within the transport limit.
    """
    cells = []
    for column in columns:
        key = q(column)
        cells.append("1+CASE typeof(" + key + ") WHEN 'text' THEN 64+6*length(CAST(" + key + " AS BLOB)) "
                     "WHEN 'blob' THEN 64+4*((length(" + key + ")+2)/3) ELSE 64 END")
    return '2+' + '+'.join(cells)


def _candidate_page(db, name, table, last):
    """Aggregate only an ordered, keyset-limited candidate prefix; no PK payload."""
    reserved = {column.casefold() for column in table['columns']}
    bound_alias, null_alias = '__reference_candidate_wire_bound', '__reference_candidate_null_key'
    while bound_alias.casefold() in reserved:
        bound_alias += '_'
    while null_alias.casefold() in reserved:
        null_alias += '_'
    keys = ','.join(q(key) for key in table['primary_key'])
    where = '' if last is None else ' WHERE (' + keys + ') > (' + ','.join('?' for _ in last) + ')'
    nullable = ' OR '.join(q(key) + ' IS NULL' for key in table['primary_key'])
    sql = ('SELECT count(*) AS candidate_count,COALESCE(MAX(' + q(bound_alias) + '),0) AS max_wire_row_bytes,'
           'COALESCE(sum(' + q(null_alias) + '),0) AS nullable_keys FROM (SELECT ' + _wire_bound_sql(table['columns']) +
           ' AS ' + q(bound_alias) + ',CASE WHEN ' + nullable + ' THEN 1 ELSE 0 END AS ' + q(null_alias) + ' FROM ' + q(name) +
           where + ' ORDER BY ' + keys + ' LIMIT ?)')
    row = db.execute(sql, tuple(last or ()) + (_migration['MAX_ROWS'],)).fetchone()
    count, bound, nullable_keys = (row[key] for key in ('candidate_count', 'max_wire_row_bytes', 'nullable_keys'))
    envelope = 16384 + sum(128 + 6 * len(column.encode()) for column in table['columns'])
    if (type(count) is not int or not 0 <= count <= _migration['MAX_ROWS']
            or type(bound) is not int or bound < 0 or (count == 0) != (bound == 0)
            or type(nullable_keys) is not int or not 0 <= nullable_keys <= count):
        raise Refused('Persisted candidate metadata is invalid: ' + name)
    if nullable_keys:
        raise Refused('Remote nullable primary key would evade keyset verification: ' + name)
    if bound + 128 + envelope > MAX_BYTES:
        raise Refused('A persisted row cannot be read within the existing transport bound: ' + name)
    return count, bound, envelope


def bounded_rows(db, name, table):
    """Size at most 64 candidates before each exact, bounded payload page.

    Both reads use the same caller-owned snapshot and keyset cursor. The extra
    per-row proof never enters the persisted row digest or admission plan.
    """
    columns, key_columns = table['columns'], table['primary_key']
    reserved = {column.casefold() for column in columns}
    bound_alias = '__reference_wire_bound'
    while bound_alias.casefold() in reserved:
        bound_alias += '_'
    last = None
    while True:
        count, bound, envelope = _candidate_page(db, name, table, last)
        if not count:
            return
        limit = min(count, max(1, (_migration['READ_BYTES'] - envelope) // max(256, bound + 128)))
        keys = ','.join(q(key) for key in key_columns)
        where = '' if last is None else ' WHERE (' + keys + ') > (' + ','.join('?' for _ in last) + ')'
        sql = ('SELECT ' + ','.join(q(column) for column in columns) + ',' + _wire_bound_sql(columns) +
               ' AS ' + q(bound_alias) + ' FROM ' + q(name) + where + ' ORDER BY ' + keys + ' LIMIT ?')
        page = db.execute(sql, tuple(last or ()) + (limit,)).fetchall()
        if len(page) != limit:
            raise Refused('Persisted payload count differs from its snapshot metadata: ' + name)
        page_keys = set()
        for row in page:
            values, row_bound = tuple(row)[:-1], tuple(row)[-1]
            identity = tuple(values[columns.index(key)] for key in key_columns)
            identity_bytes = _migration['row_bytes'](identity)
            if any(value is None for value in identity) or identity_bytes in page_keys:
                raise Refused('Persisted payload primary key differs: ' + name)
            page_keys.add(identity_bytes)
            if (len(values) != len(columns) or type(row_bound) is not int or not 0 < row_bound <= bound
                    or _migration['wire_size'](values) > row_bound):
                raise Refused('A persisted row exceeded its snapshot-bound wire-size proof: ' + name)
            yield values
            last = identity
        if count < _migration['MAX_ROWS'] and limit == count:
            return


def _wire(row):
    return [{'blob_base64': base64.b64encode(cell).decode()} if isinstance(cell, bytes) else cell for cell in row]


def _unwire(row):
    return tuple(base64.b64decode(cell['blob_base64'], validate=True) if isinstance(cell, dict) else cell for cell in row)


def source_identity(commit):
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise Refused('An exact source commit is required.')
    paths = [ROOT / 'casepath-api' / 'casepath_api' / name for name in (
        'autonomous_controller_v1.py', 'autonomous_store_v1.py', 'autonomous_policy_v1.py',
        'autonomous_knowledge_v1.py', 'autonomous_intake_gate_v1.py', 'autonomous_reference_v1.py',
        'autonomous_reference_policy_v1.py', 'causal_process_v1.py')]
    paths += sorted((ROOT / 'casepath-api/casepath_api/reference_profiles/synthetic-nine-v1').rglob('*'))
    paths.append(Path(__file__))
    return {'source_commit': commit, 'files': {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest()
                                               for p in paths if p.is_file()}}


def inventory(connect, *, owner=None):
    """Read all authoritative rows, including the unchanged physical cost ledger."""
    values, tables = {}, {}
    with connect() as db:
        db.execute('BEGIN')
        objects = schema_objects(db)
        for obj in objects:
            name = obj['name']
            if obj['type'] != 'table' or name == 'hosted_workflow_lease':
                continue
            info = table_info(db, name)
            rows = list(bounded_rows(db, name, info))
            values[name] = {'columns': info['columns'], 'rows': [_wire(r) for r in rows]}
            tables[name] = table_digest(rows, info['columns'])
        lease = db.execute('SELECT owner,expires_at,CAST(strftime(\'%s\',\'now\') AS INTEGER) AS now '
                           'FROM hosted_workflow_lease WHERE singleton=1').fetchone()
        if lease is None or (lease['owner'] is not None and lease['expires_at'] > lease['now']
                             and (owner is None or lease['owner'] != owner.owner)):
            raise Refused('Hosted workflow ownership is busy or unavailable.')
        if not {'claim_loop_events', 'autonomous_source_chunks', 'work_external_budget'} <= values.keys():
            raise Refused('Existing journal, source store or budget schema is missing.')
        work = WorkStore.__new__(WorkStore)
        work._validated_source_commit = None
        work._validated_event_cache, work._validated_object_cache = {}, {}
        budget = work._external_budget(db)
        if budget and budget.get('in_flight'):
            raise Refused('Missing or unknown physical provider outcomes require explicit reconciliation.')
        if budget and budget.get('autonomous_policy'):
            usage = work._autonomous_usage(db, budget['autonomous_policy'])
            selected = set(ReferenceProfile().ids)
            for workflow in usage['workflows'].values():
                if workflow['record']['identity']['claim_id'] not in selected:
                    continue
                if (set(workflow['calls']) != {'interpret', 'verify'}
                        or workflow['terminal'] is None or any(call['outcome'] is None
                            or call['outcome']['status'] != 'completed' for call in workflow['calls'].values())):
                    raise Refused('A selected reference claim has a missing, unknown or rejected prior provider stage.')
        # A reserved but unsent workflow is also an active owner, not free work.
        if 'work_autonomous_workflows' in values:
            workflows = values['work_autonomous_workflows']['rows']
            terminal_ids = {r[0] for r in values.get('work_autonomous_terminals', {}).get('rows', [])}
            if any(row[0] not in terminal_ids for row in workflows):
                raise Refused('An unfinished provider workflow prevents reference admission.')
        before = {'tables': tables, 'budget': budget, 'schema_sha256': digest_value(objects)}
    return before, values


def _head_rows(values):
    rows = values['claim_loop_events']
    columns = rows['columns']
    heads = {}
    for raw in rows['rows']:
        row = dict(zip(columns, _unwire(raw)))
        if row['session_id'] == SESSION_ID:
            event = json.loads(row['event_json'])
            previous = heads.get(event['claim_id'])
            if previous is None or row['sequence'] > previous['revision']:
                heads[event['claim_id']] = {'revision': row['sequence'], 'event_sha256': row['event_sha256'],
                                          'state_sha256': event['resulting_state_sha256']}
    return heads


def _reference_source_bytes(corpus, profile):
    """Only the selected originals and their exact reviewed supplements."""
    result = {}
    for cid in profile.ids:
        packet = corpus.packet(cid)
        for descriptor in packet['sources']:
            raw = packet['source_bytes'][descriptor['artifact_id']]
            if sha256(raw).hexdigest() != descriptor['sha256'] or len(raw) != descriptor['size_bytes']:
                raise Refused('Selected original source bytes differ from their manifest-bound packet.')
            result[descriptor['sha256']] = raw
        for file, descriptor in zip(profile.files(cid), profile.value['claims'][cid]['sources']):
            raw = base64.b64decode(file['content_base64'], validate=True)
            if sha256(raw).hexdigest() != descriptor['sha256'] or len(raw) != descriptor['size_bytes']:
                raise Refused('Selected supplemental source bytes differ from their reviewed profile.')
            result[descriptor['sha256']] = raw
    return result


def prepare(connect, *, source_commit, corpus=None):
    identity = source_identity(source_commit)
    corpus, profile = corpus or CanonicalCorpus(), ReferenceProfile()
    before, rows = inventory(connect)
    sources = HostedSources(connect)
    source_hashes = {row[0] for row in rows['autonomous_source_chunks']['rows']}
    sources.verify_many(source_hashes)
    reference_bytes = _reference_source_bytes(corpus, profile)
    policy = bounded_reference_policy(corpus._corpus.static_policy())
    with tempfile.TemporaryDirectory(prefix='casepath-reference-plan-') as folder:
        path = Path(folder) / 'stage.sqlite'
        with sqlite3.connect(path) as db:
            db.executescript(JOURNAL_SCHEMA)
            for wire in rows['claim_loop_events']['rows']:
                db.execute(*insert_sql('claim_loop_events', rows['claim_loop_events']['columns'], [_unwire(wire)]))
        store = AutonomousStore(path)
        for digest in source_hashes:
            raw = sources.read(digest)
            if store._publish(raw) != digest:
                raise Refused('Source byte publication differs in isolated staging.')
        controller = AutonomousController(store, policy, reference_adapter=DeterministicReferenceAdapter(policy, profile))
        try:
            # Validate every pre-existing accepted stream before staging any new one.
            for cid in _head_rows(rows):
                store.get(cid)
            for cid in profile.ids:
                if cid not in _head_rows(rows):
                    packet = corpus.packet(cid)
                    store.admit_original(cid, packet, expected_revision=0,
                        expected_state_sha256=packet['initial_state_sha256'], idempotency_key='reference.original.' + cid)
                state = store.get(cid)
                if state.get('original_binding') != corpus.preview_state(cid)['original_binding']:
                    raise Refused('An existing canonical claim has a different original binding.')
                if (state.get('deferral') or {}).get('code') not in (None, 'model_unavailable'):
                    raise Refused('A paused or failed claim must be inspected before reference admission.')
                known = {d['sha256'] for d in state['source_descriptors']}
                missing = [f for f, source in zip(profile.files(cid), profile.value['claims'][cid]['sources'])
                           if source['sha256'] not in known]
                if missing:
                    store.add_sources(cid, missing, expected_revision=state['revision'],
                        expected_state_sha256=state['state_sha256'], idempotency_key='reference.sources.' + profile.sha256[:16] + '.' + cid)
                final = controller.run(cid)
                if (final.get('outcome') or {}).get('assessment_status') != 'complete':
                    raise Refused('Staged bounded execution did not complete: ' + cid)
            with sqlite3.connect(path) as db:
                db.row_factory = sqlite3.Row
                original_keys = {tuple(_unwire(r)[:3]) for r in rows['claim_loop_events']['rows']}
                append = [tuple(r) for r in db.execute('SELECT * FROM claim_loop_events ORDER BY session_id,loop_id,sequence')
                          if tuple(r)[:3] not in original_keys]
            chunks = []
            for file in sorted(store.source_root.iterdir()):
                if file.name in source_hashes:
                    continue
                raw = file.read_bytes()
                if file.name not in reference_bytes or raw != reference_bytes[file.name]:
                    raise Refused('Staging added a source outside the exact selected original and supplement roster.')
                chunks.extend((file.name, i, raw[offset:offset + HostedSources.CHUNK_BYTES])
                              for i, offset in enumerate(range(0, len(raw), HostedSources.CHUNK_BYTES)))
            if {row[0] for row in chunks} != set(reference_bytes) - source_hashes:
                raise Refused('Staging source additions differ from the exact selected missing byte roster.')
            final_heads = {cid: {'revision': store.get(cid)['revision'],
                                 'state_sha256': store.get(cid)['state_sha256'],
                                 'event_sha256': store.get(cid)['last_event_sha256']} for cid in profile.ids}
            plan = {'contract': CONTRACT, 'source_identity': identity, 'before': before,
                    'corpus_sha256': corpus._corpus.identity['manifest_sha256'],
                    'profile_sha256': profile.sha256, 'rule_set_sha256': digest_value(policy),
                    'before_heads': _head_rows(rows), 'final_heads': final_heads,
                    'append_rows': [_wire(r) for r in append], 'source_chunks': [_wire(r) for r in chunks],
                    'event_columns': rows['claim_loop_events']['columns'],
                    'source_columns': rows['autonomous_source_chunks']['columns'],
                    'provider_calls': 0, 'budget_writes': 0}
            return {**plan, 'plan_sha256': digest_value(plan)}
        finally:
            controller.shutdown()


def apply(connect, plan, *, source_commit):
    if (plan.get('contract') != CONTRACT or plan.get('plan_sha256') != digest_value({k: v for k, v in plan.items() if k != 'plan_sha256'})
            or plan['source_identity'] != source_identity(source_commit)):
        raise Refused('Plan or executing source identity changed.')
    corpus, profile = CanonicalCorpus(), ReferenceProfile()
    policy = bounded_reference_policy(corpus._corpus.static_policy())
    if (set(plan['final_heads']) != set(profile.ids) or plan['corpus_sha256'] != corpus._corpus.identity['manifest_sha256']
            or plan['profile_sha256'] != profile.sha256 or plan['rule_set_sha256'] != digest_value(policy)
            or plan['provider_calls'] != 0 or plan['budget_writes'] != 0):
        raise Refused('Plan expands or changes the exact source-bound reference scope.')
    current, values = inventory(connect)
    existing = {tuple(_unwire(r)) for r in values['claim_loop_events']['rows']}
    planned = {tuple(_unwire(r)) for r in plan['append_rows']}
    replayed = planned <= existing
    if replayed:
        baseline = deepcopy_inventory_without_planned(values, plan)
        if (baseline != plan['before']['tables'] or current['budget'] != plan['before']['budget']
                or current['schema_sha256'] != plan['before']['schema_sha256']):
            raise Refused('Post-admission rows or budget changed; exact retry is not established.')
        baseline_values = {}
        for table, data in values.items():
            exclude = plan['append_rows'] if table == 'claim_loop_events' else plan['source_chunks'] if table == 'autonomous_source_chunks' else []
            exclude = {tuple(_unwire(row)) for row in exclude}
            baseline_values[table] = {'columns': data['columns'],
                'rows': [row for row in data['rows'] if tuple(_unwire(row)) not in exclude]}
        _verify_plan(baseline_values, plan)
    else:
        if current != plan['before'] or _head_rows(values) != plan['before_heads']:
            raise Refused('Stale journal, source, cost, or schema snapshot.')
        _verify_plan(values, plan)
    # Inventory, local execution and query encoding may exceed a lease lifetime.
    # Ownership starts only when the final exact-CAS transaction is ready.
    queries = list(_query_batches(_cas_queries(values)))
    lease = HostedWorkflowLease(connect)
    token = lease.acquire()
    if token is None:
        raise Refused('Hosted workflow ownership is busy.')
    owner = _CURRENT_OWNER.set(token)
    try:
        with lease.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if digest_value(schema_objects(db)) != current['schema_sha256']:
                raise Refused('Schema changed at the final exact-row CAS.')
            for batch in queries:
                if hasattr(db, 'prefetch'):
                    db.prefetch([(sql, args) for sql, args, expected in batch])
                for sql, args, expected in batch:
                    if db.execute(sql, args).fetchone()['matched'] != expected:
                        raise Refused('Snapshot changed at the final exact-row CAS.')
            if not replayed:
                for table, columns, wires in [('autonomous_source_chunks', plan['source_columns'], plan['source_chunks']),
                                               ('claim_loop_events', plan['event_columns'], plan['append_rows'])]:
                    for batch in _row_batches(wires, len(columns)):
                        db.execute(*insert_sql(table, columns, [_unwire(wire) for wire in batch]))
            # Entire accepted plan remains one CAS commit; uncertain commit is not retried.
        sources = HostedSources(connect)
        corpus = CanonicalCorpus()
        sources.verify_many(set(_reference_source_bytes(corpus, profile)))
        class ExistingJournal:
            path = Path('/tmp/reference-readback-unused')
        journal = ExistingJournal()
        journal.connect = connect
        with tempfile.TemporaryDirectory(prefix='casepath-reference-readback-') as folder:
            store = HostedAutonomousStore(journal.path, Path(folder), journal=journal, source_store=sources)
            for cid, expected in plan['final_heads'].items():
                state = store.get(cid)
                if {k: state[v] for k, v in [('revision', 'revision'), ('state_sha256', 'state_sha256'),
                                           ('event_sha256', 'last_event_sha256')]} != expected:
                    raise Refused('Committed journal readback differs from the reviewed exact plan.')
        return {'contract': 'casepath.reference-admission-receipt/1.0.0', 'plan_sha256': plan['plan_sha256'],
                'replayed': replayed, 'provider_calls': 0, 'budget_writes': 0, 'final_heads': plan['final_heads']}
    finally:
        _CURRENT_OWNER.reset(owner)
        lease.release(token)


def _row_batches(rows, columns):
    batch, size = [], 0
    for row in rows:
        amount = len(json.dumps(row, ensure_ascii=False).encode())
        if amount > 2 * 1024 * 1024:
            raise Refused('A plan row exceeds the reviewed bounded insert size.')
        if batch and (size + amount > 2 * 1024 * 1024 or len(batch) >= min(64, 900 // columns)):
            yield batch
            batch, size = [], 0
        batch.append(row)
        size += amount
    if batch:
        yield batch


def _cas_queries(values):
    result = []
    for table, data in values.items():
        columns, rows = data['columns'], data['rows']
        result.append(('SELECT count(*) AS matched FROM ' + q(table), (), len(rows)))
        names = ','.join(q(c) for c in columns)
        equality = ' AND '.join('actual.' + q(c) + ' IS expected.' + q(c) for c in columns)
        for batch in _row_batches(rows, len(columns)):
            slots = ','.join('(' + ','.join('?' for c in columns) + ')' for row in batch)
            sql = ('SELECT (WITH expected(' + names + ') AS (VALUES ' + slots + ') SELECT count(*) '
                   'FROM expected WHERE EXISTS (SELECT 1 FROM ' + q(table) + ' actual WHERE ' + equality + ')) AS matched')
            result.append((sql, tuple(cell for wire in batch for cell in _unwire(wire)), len(batch)))
    return result


def _query_batches(queries):
    batch, size = [], 0
    for query in queries:
        amount = len(query[0].encode()) + sum(len(json.dumps(_wire([arg])).encode()) for arg in query[1])
        if batch and (size + amount > 2 * 1024 * 1024 or len(batch) == 128):
            yield batch
            batch, size = [], 0
        batch.append(query)
        size += amount
    if batch:
        yield batch


def deepcopy_inventory_without_planned(values, plan):
    result = {}
    for table, data in values.items():
        excluded = plan['append_rows'] if table == 'claim_loop_events' else plan['source_chunks'] if table == 'autonomous_source_chunks' else []
        excluded = {tuple(_unwire(r)) for r in excluded}
        kept = [tuple(_unwire(r)) for r in data['rows'] if tuple(_unwire(r)) not in excluded]
        result[table] = table_digest(kept, data['columns'])
    return result


def _verify_plan(values, plan):
    """Reject altered source/chains before any irreversible remote insert."""
    with tempfile.TemporaryDirectory(prefix='casepath-reference-verify-') as folder:
        path = Path(folder) / 'verify.sqlite'
        with sqlite3.connect(path) as db:
            db.executescript(JOURNAL_SCHEMA)
            for row in values['claim_loop_events']['rows']:
                db.execute(*insert_sql('claim_loop_events', plan['event_columns'], [_unwire(row)]))
        corpus, profile = CanonicalCorpus(), ReferenceProfile()
        if (plan['event_columns'] != values['claim_loop_events']['columns']
                or plan['source_columns'] != values['autonomous_source_chunks']['columns']):
            raise Refused('Plan column roster differs from the existing admission surfaces.')
        expected, consumed = {}, set()
        for wire in plan['append_rows']:
            row = dict(zip(plan['event_columns'], _unwire(wire)))
            event = json.loads(row['event_json'])
            key = (event['claim_id'], event['idempotency_key'])
            if (event['claim_id'] not in profile.ids or row['session_id'] != SESSION_ID
                    or row['loop_id'] != 'autonomous.' + event['claim_id'] or key in expected):
                raise Refused('Planned events expand the exact nine canonical claim identities.')
            expected[key] = (wire, event)

        class PlannedExecutionStore(AutonomousStore):
            def _commit_command(self, claim_id, command, command_hash, idempotency_key):
                key = (claim_id, idempotency_key)
                item = expected.get(key)
                if item is None or key in consumed:
                    raise Refused('Deterministic execution produced an operation absent from the reviewed plan.')
                wire, event = item
                if (command_hash != event['command_sha256']
                        or command != {k: event[k] for k in ('kind', 'payload', 'expected_revision', 'expected_state_sha256')}):
                    raise Refused('Planned operation differs from actual source-backed deterministic execution.')
                with self.journal.connect() as db:
                    db.execute('BEGIN IMMEDIATE')
                    db.execute(*insert_sql('claim_loop_events', plan['event_columns'], [_unwire(wire)]))
                consumed.add(key)
                # Full ordinary replay validates the recorded timestamp, chain,
                # parent and physical source bytes without inventing any step.
                return {'state': self.get(claim_id), 'replayed': False}

        store = PlannedExecutionStore(path)
        old_digests = {wire[0] for wire in values['autonomous_source_chunks']['rows']}
        reference_bytes = _reference_source_bytes(corpus, profile)
        wanted = set(reference_bytes) - old_digests
        if {wire[0] for wire in plan['source_chunks']} != wanted:
            raise Refused('Plan source additions differ from the exact reviewed synthetic byte roster.')
        chunks = {}
        for wire in values['autonomous_source_chunks']['rows'] + plan['source_chunks']:
            digest, index, raw = _unwire(wire)
            if (not isinstance(raw, bytes) or type(index) is not int or index < 0
                    or len(raw) > HostedSources.CHUNK_BYTES or index in chunks.setdefault(digest, {})):
                raise Refused('Planned source chunks are duplicate, invalid or oversized.')
            chunks[digest][index] = raw
        for digest, parts in chunks.items():
            if sorted(parts) != list(range(len(parts))):
                raise Refused('Planned source chunk roster has a gap.')
            raw = b''.join(parts[i] for i in range(len(parts)))
            if sha256(raw).hexdigest() != digest or digest in wanted and raw != reference_bytes[digest]:
                raise Refused('Planned source bytes do not match their immutable hash.')
            if digest in old_digests and store._publish(raw) != digest:
                raise Refused('Existing source byte publication differs.')
        before_heads = _head_rows(values)
        for cid in before_heads:
            store.get(cid)  # New sources may not repair an invalid accepted prefix.
        for digest in wanted:
            if store._publish(reference_bytes[digest]) != digest:
                raise Refused('Selected source byte publication differs.')
        policy = bounded_reference_policy(corpus._corpus.static_policy())
        controller = AutonomousController(store, policy, reference_adapter=DeterministicReferenceAdapter(policy))
        try:
            for cid in profile.ids:
                if cid not in before_heads:
                    packet = corpus.packet(cid)
                    store.admit_original(cid, packet, expected_revision=0,
                        expected_state_sha256=packet['initial_state_sha256'], idempotency_key='reference.original.' + cid)
                state = store.get(cid)
                known = {d['sha256'] for d in state['source_descriptors']}
                missing = [f for f, source in zip(profile.files(cid), profile.value['claims'][cid]['sources'])
                           if source['sha256'] not in known]
                if missing:
                    store.add_sources(cid, missing, expected_revision=state['revision'], expected_state_sha256=state['state_sha256'],
                        idempotency_key='reference.sources.' + profile.sha256[:16] + '.' + cid)
                controller.run(cid)
            if consumed != set(expected):
                raise Refused('Plan contains extra journal steps absent from actual execution.')
            for cid, expected in plan['final_heads'].items():
                state = store.get(cid)
                if (state['revision'] != expected['revision'] or state['state_sha256'] != expected['state_sha256']
                        or state['last_event_sha256'] != expected['event_sha256']
                        or state.get('original_binding') != corpus.preview_state(cid)['original_binding']
                        or not controller.intake_projection(state)['eligible']
                        or state['evaluation']['process_status'] != 'complete'
                        or state.get('outcome', {}).get('assessment_status') != 'complete'):
                    raise Refused('Planned accepted execution differs from its pinned source-backed final head.')
        finally:
            controller.shutdown()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare', 'dry-run', 'apply'])
    parser.add_argument('--plan', required=True, type=Path)
    args = parser.parse_args()
    from casepath_api.hosted_sql_v1 import TursoDatabase
    preflight = runpy.run_path(str(ROOT / 'casepath/tools/preflight_original_nine.py'))
    commit = preflight['clean_source_commit']()
    database = TursoDatabase(os.environ['CASEPATH_TURSO_URL'], os.environ['TURSO_AUTH_TOKEN'])
    if args.mode in {'prepare', 'dry-run'}:
        plan = prepare(database.connect, source_commit=commit)
        if args.plan.exists():
            raise Refused('Plan already exists; preserve the reviewed artifact.')
        args.plan.write_text(json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
        print(json.dumps({'plan_sha256': plan['plan_sha256'], 'append_events': len(plan['append_rows']),
                          'new_chunks': len(plan['source_chunks']), 'provider_calls': 0, 'budget_writes': 0}))
    else:
        print(json.dumps(apply(database.connect, json.loads(args.plan.read_text()), source_commit=commit)))


if __name__ == '__main__':
    main()
