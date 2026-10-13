import base64
import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import runpy
import sqlite3

import pytest

from hosted_hrana_fixture import MockHrana
from casepath_api.agent_work.store import WorkStore
from casepath_api.autonomous_controller_v1 import AutonomousController
from casepath_api.autonomous_corpus_v1 import CanonicalCorpus
from casepath_api.autonomous_reference_policy_v1 import bounded_reference_policy
from casepath_api.autonomous_reference_v1 import DeterministicReferenceAdapter, ReferenceProfile
from casepath_api.autonomous_store_v1 import AutonomousStore, AutonomousStoreError
from casepath_api.hosted_lease_v1 import HostedWorkflowLease, HostedOwnershipLost, LEASE_SECONDS, _CURRENT_OWNER
from casepath_api.hosted_storage_v1 import HostedAutonomousStore, HostedJournal, HostedSources

operator = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'tools/admit_reference.py'))
COMMIT = 'e176657b9307ad657fd895e57e83ce88e140bcf5'


def test_operator_pins_current_profile_and_both_immutable_source_histories():
    profile = operator['_current_profile']()
    assert profile.value['profile_id'] == 'synthetic-nine-v2'
    identity = operator['source_identity'](COMMIT)
    for name in ('synthetic-nine-v1', 'synthetic-nine-v2'):
        root = operator['ROOT'] / 'casepath-api/casepath_api/reference_profiles' / name
        files = {str(path.relative_to(operator['ROOT'])): sha256(path.read_bytes()).hexdigest()
                 for path in root.rglob('*') if path.is_file()}
        assert files and files.items() <= identity['files'].items()


def _copy_native_to_hosted(store, connect):
    sources = HostedSources(connect)
    for path in store.source_root.iterdir():
        assert sources.publish(path.read_bytes()) == path.name
    with store.journal.connect() as local, connect() as remote:
        rows = local.execute('SELECT * FROM claim_loop_events ORDER BY session_id,loop_id,sequence').fetchall()
        if rows:
            columns = list(rows[0].keys())
            for row in rows:
                remote.execute(*operator['insert_sql']('claim_loop_events', columns, [tuple(row)]))


def _native_from_inventory(path, values):
    with sqlite3.connect(path) as db:
        db.executescript(operator['JOURNAL_SCHEMA'])
        for wire in values['claim_loop_events']['rows']:
            db.execute(*operator['insert_sql']('claim_loop_events', values['claim_loop_events']['columns'],
                                               [operator['_unwire'](wire)]))
    store = AutonomousStore(path, source_root=path.with_suffix('.sources'))
    chunks = {}
    for wire in values['autonomous_source_chunks']['rows']:
        digest, index, raw = operator['_unwire'](wire)
        chunks.setdefault(digest, {})[index] = raw
    for digest, parts in chunks.items():
        assert sorted(parts) == list(range(len(parts)))
        assert store._publish(b''.join(parts[i] for i in range(len(parts)))) == digest
    return store


def test_mock_hrana_complete_v1_readmission_appends_exact_v2_and_preserves_every_old_prefix(tmp_path):
    server = MockHrana(tmp_path / 'readmission.sqlite')
    work = None
    try:
        connect = server.connection
        HostedWorkflowLease(connect).initialize()
        journal = HostedJournal(tmp_path / 'unused', connect)
        work = WorkStore(tmp_path / 'unused-work', connection_factory=connect)
        from test_autonomous_budget_v1 import legacy_run, legacy_call, POLICY
        work.configure_external_budget(POLICY)
        legacy = legacy_run(work, 0)
        legacy_call(work, legacy, 0, None)
        work.finish(legacy, 'legacy-owner', 'completed', 'Historic unknown cost remains reserved')
        corpus = CanonicalCorpus()
        old_profile = ReferenceProfile.for_profile('synthetic-nine-v1')
        current_profile = operator['_current_profile']()
        assert old_profile.ids == current_profile.ids
        policy = bounded_reference_policy(corpus._corpus.static_policy())
        old_store = AutonomousStore(tmp_path / 'legacy.sqlite')
        old_controller = AutonomousController(old_store, policy,
            reference_adapter=DeterministicReferenceAdapter(policy, old_profile))
        old_states, old_events, old_history = {}, {}, {}
        try:
            for cid in old_profile.ids:
                packet = corpus.packet(cid)
                old_store.admit_original(cid, packet, expected_revision=0,
                    expected_state_sha256=packet['initial_state_sha256'], idempotency_key='reference.original.' + cid)
                state = old_store.get(cid)
                old_store.add_sources(cid, old_profile.files(cid), expected_revision=state['revision'],
                    expected_state_sha256=state['state_sha256'],
                    idempotency_key='reference.sources.' + old_profile.sha256[:16] + '.' + cid)
                old_states[cid] = old_controller.run(cid)
                assert old_states[cid]['outcome']['assessment_status'] == 'complete'
                assert old_states[cid]['policy_id'] == policy['policy_id']
                with old_store.journal.connect() as db:
                    _, old_events[cid], old_history[cid] = old_store._replay(old_store._rows(db, cid), with_history=True)
        finally:
            old_controller.shutdown()
        _copy_native_to_hosted(old_store, connect)
        before, baseline = operator['inventory'](connect)
        assert before['budget']['unknown_calls'] == 1 and not before['budget']['in_flight']
        plan = operator['prepare'](connect, source_commit=COMMIT, corpus=corpus)
        assert operator['inventory'](connect) == (before, baseline)
        v2_hashes = {row['sha256'] for entry in current_profile.value['claims'].values() for row in entry['sources']}
        assert len(v2_hashes) == len(plan['source_chunks']) == 21
        assert {row[0] for row in plan['source_chunks']} == v2_hashes
        assert plan['profile_sha256'] == current_profile.sha256
        assert plan['provider_calls'] == plan['budget_writes'] == 0
        assert set(plan['final_heads']) == set(old_profile.ids)
        for cid in old_profile.ids:
            events = [json.loads(dict(zip(plan['event_columns'], operator['_unwire'](row)))['event_json'])
                      for row in plan['append_rows'] if row[1] == 'autonomous.' + cid]
            assert sum(event['kind'] == 'sources.arrived' for event in events) == 1
            reset = [event for event in events if event['kind'] == 'process.prepared']
            assert len(reset) == 1 and reset[0]['payload']['graph']['family'] == 'incoming_packet'
            assert events[0]['kind'] == 'sources.arrived' and events[0]['idempotency_key'] != (
                'reference.sources.' + old_profile.sha256[:16] + '.' + cid)

        # New v2 bytes cannot replace a missing legacy source in an accepted prefix.
        broken = deepcopy(baseline)
        missing = old_profile.value['claims'][old_profile.ids[0]]['sources'][0]['sha256']
        broken['autonomous_source_chunks']['rows'] = [row for row in broken['autonomous_source_chunks']['rows'] if row[0] != missing]
        with pytest.raises(AutonomousStoreError, match='source bytes'):
            operator['_verify_plan'](broken, plan)

        receipt = operator['apply'](connect, plan, source_commit=COMMIT)
        assert receipt['replayed'] is False and receipt['provider_calls'] == receipt['budget_writes'] == 0
        after, values = operator['inventory'](connect)
        assert after['budget'] == before['budget']
        for table, data in baseline.items():
            if table in {'claim_loop_events', 'autonomous_source_chunks'}:
                assert {tuple(operator['_unwire'](row)) for row in data['rows']} <= {
                    tuple(operator['_unwire'](row)) for row in values[table]['rows']}
            else:
                assert values[table] == data
        restarted = HostedAutonomousStore(journal.path, tmp_path / 'restart-sources', journal=journal,
                                           source_store=HostedSources(connect))
        local = _native_from_inventory(tmp_path / 'prefixes.sqlite', values)
        for cid in current_profile.ids:
            snapshot = restarted.snapshot(cid)
            state = snapshot['state']
            assert state['state_sha256'] == plan['final_heads'][cid]['state_sha256']
            assert state['outcome']['assessment_status'] == state['evaluation']['process_status'] == 'complete'
            assert state['policy_id'] == old_states[cid]['policy_id']
            assert restarted.events(cid)[:len(old_events[cid])] == old_events[cid]
            assert restarted.replay(cid, old_states[cid]['revision'])['state'] == old_states[cid]
            assert old_states[cid]['semantic_contexts'].items() <= state['semantic_contexts'].items()
            current_sources = state['semantic_contexts'][state['run_id']]['sources']
            originals = {row['sha256'] for row in state['original_binding']['source_map']}
            active = originals | {row['sha256'] for row in current_profile.value['claims'][cid]['sources']}
            assert {row['sha256'] for row in current_sources} == active
            retired = {row['sha256'] for row in old_profile.value['claims'][cid]['sources']}
            assert {row['sha256'] for row in state['source_descriptors']} == active | retired
            v2_ids = {row['artifact_id'] for row in state['source_descriptors'] if row['sha256'] in v2_hashes}
            citations = {citation['artifact_id'] for fact in state['facts'] for citation in fact['citations']}
            assert v2_ids <= citations
            assert not citations & {row['artifact_id'] for row in state['source_descriptors'] if row['sha256'] in retired}
            with local.journal.connect() as db:
                head, events, history = local._replay(local._rows(db, cid), with_history=True)
            assert head == state and history[:len(old_history[cid])] == old_history[cid]
            reset = next(event for event in events if event['kind'] == 'process.prepared'
                         and event['sequence'] > old_states[cid]['revision'])
            reset_state = history[reset['sequence'] - 1]
            assert reset_state['graph']['family'] == 'incoming_packet'
            assert all(fact['status'] == 'pending' and not fact['citations'] for fact in reset_state['facts'])
            assert all(node['execution_state'] != 'completed' for node in reset_state['evaluation']['nodes'])
            start = snapshot['replay_start']
            assert start['from_seq'] == reset['sequence'] and start['run_id'] == state['run_id']
            assert start['state_sha256'] == reset_state['state_sha256']
            assert start['event_sha256'] == reset['event_sha256'] and start['profile_sha256'] == current_profile.sha256
            assert start['source_artifact_ids'] == [row['artifact_id'] for row in current_sources]
            assert start['source_artifact_ids'] == state['outcome']['reference_provenance']['source_artifact_ids']
            assert restarted.replay(cid, start['from_seq'])['state'] == reset_state
            for event, prefix in zip(events, history):
                local._validate_state_sources(prefix)
                assert prefix['revision'] == event['sequence']
                assert prefix['state_sha256'] == event['resulting_state_sha256']
        assert operator['apply'](connect, plan, source_commit=COMMIT)['replayed'] is True
        assert operator['inventory'](connect) == (after, values)
        settled = operator['prepare'](connect, source_commit=COMMIT, corpus=corpus)
        assert not settled['append_rows'] and not settled['source_chunks']
        assert settled['final_heads'] == plan['final_heads']
        assert operator['apply'](connect, settled, source_commit=COMMIT)['replayed'] is True
        assert operator['inventory'](connect) == (after, values)
    finally:
        if work is not None:
            work.close()
        server.close()


@pytest.mark.parametrize('extra', ['unknown', 'adverse', 'partial_legacy', 'foreign_policy'])
def test_mock_hrana_v2_prepare_rejects_unsafe_source_roster_or_foreign_policy_read_only(tmp_path, extra):
    server = MockHrana(tmp_path / 'unsafe-roster.sqlite')
    work = None
    try:
        connect = server.connection
        HostedWorkflowLease(connect).initialize()
        HostedJournal(tmp_path / 'unused', connect)
        work = WorkStore(tmp_path / 'unused-work', connection_factory=connect)
        from test_autonomous_budget_v1 import POLICY
        work.configure_external_budget(POLICY)
        corpus = CanonicalCorpus()
        cid = operator['_current_profile']().ids[0]
        packet = corpus.packet(cid)
        store = AutonomousStore(tmp_path / 'unsafe-local.sqlite')
        store.admit_original(cid, packet, expected_revision=0,
            expected_state_sha256=packet['initial_state_sha256'], idempotency_key='unsafe-original')
        state = store.get(cid)
        if extra == 'foreign_policy':
            store.append(cid, 'work.started', {'run_id': 'foreign.fixture', 'policy_id': 'foreign.fixture-policy/1.0.0'},
                expected_revision=state['revision'], expected_state_sha256=state['state_sha256'], idempotency_key='foreign-policy')
        else:
            files = ReferenceProfile.for_profile('synthetic-nine-v1').files(cid)[:1] if extra == 'partial_legacy' else [{
                'file_name': 'additional-account.txt', 'media_type': 'text/plain',
                'content_base64': base64.b64encode((
                    'An unreviewed additional account.' if extra == 'unknown' else
                    'The supplied supplement is disputed. The landlord never received notice and the defect was repaired.'
                ).encode()).decode()}]
            store.add_sources(cid, files, expected_revision=state['revision'],
                expected_state_sha256=state['state_sha256'], idempotency_key='unsafe-extra')
        _copy_native_to_hosted(store, connect)
        before = operator['inventory'](connect)
        with pytest.raises(AutonomousStoreError, match='different explicit execution policy' if extra == 'foreign_policy' else 'intake incomplete'):
            operator['prepare'](connect, source_commit=COMMIT, corpus=corpus)
        assert operator['inventory'](connect) == before
    finally:
        if work is not None:
            work.close()
        server.close()


def test_mock_hrana_prepare_apply_all_nine_preserves_old_rows_budget_restart_and_exact_retry(tmp_path, monkeypatch):
    server = MockHrana(tmp_path / 'remote.sqlite')
    connect = server.connection
    try:
        lease = HostedWorkflowLease(connect); lease.initialize()
        journal = HostedJournal(tmp_path / 'unused', connect)
        work = WorkStore(tmp_path / 'unused-work', connection_factory=connect)
        from test_autonomous_budget_v1 import legacy_run, legacy_call, POLICY
        work.configure_external_budget(POLICY)
        legacy = legacy_run(work, 0)
        legacy_call(work, legacy, 0, None)
        work.finish(legacy, 'legacy-owner', 'completed', 'Completed historic fixture with unknown cost; keep reservation')
        assert work.external_budget()['unknown_calls'] == 1 and not work.external_budget()['in_flight']
        source = HostedSources(connect)
        corpus = CanonicalCorpus()
        store = HostedAutonomousStore(journal.path, tmp_path / 'unused-sources', journal=journal, source_store=source)
        cid = 'clm_0f4f13b1e3e1328c'
        packet = corpus.packet(cid)
        store.admit_original(cid, packet, expected_revision=0, expected_state_sha256=packet['initial_state_sha256'],
                             idempotency_key='existing-original')
        old_controller = AutonomousController(store, corpus._corpus.static_policy())
        old = old_controller.run(cid)
        legacy_draft = store.intake({'title': 'Preserved native legacy fixture',
                                    'message': 'Saved unselected intake; no new assessment requested.', 'files': []}, 'native-legacy')
        legacy_state = old_controller.run(legacy_draft['claim_id'])
        old_controller.shutdown()
        assert old['deferral']['code'] == 'model_unavailable'
        original_rows = store.events(cid)
        legacy_rows = store.events(legacy_state['claim_id'])
        from casepath_api.autonomous_reference_v1 import ReferenceProfile
        selected_originals = {d['sha256'] for selected in ReferenceProfile().ids
                              for d in corpus.preview_state(selected)['source_descriptors']}
        stored = {d['sha256'] for d in old['source_descriptors'] + legacy_state['source_descriptors']}
        for unselected in corpus.ids:
            if unselected in ReferenceProfile().ids:
                continue
            for raw in corpus.packet(unselected)['source_bytes'].values():
                digest = source.publish(raw) if sha256(raw).hexdigest() not in selected_originals else None
                if digest:
                    stored.add(digest)
                if len(stored) == 31:
                    break
            if len(stored) == 31:
                break
        assert len(stored) == 31 and len(stored & selected_originals) == 2
        with connect() as db:
            db.execute('CREATE TABLE operator_fixture_cas(key INTEGER PRIMARY KEY,value TEXT)')
            db.execute('INSERT INTO operator_fixture_cas VALUES(1,\'baseline\')')
        before, _ = operator['inventory'](connect)
        operator_request_start = len(server.requests)
        plan = operator['prepare'](connect, source_commit=COMMIT, corpus=corpus)
        assert json.loads(json.dumps(plan)) == plan
        assert operator['inventory'](connect)[0] == before
        assert len(plan['final_heads']) == 9 and len(plan['source_chunks']) == 34
        added = {row[0] for row in plan['source_chunks']}
        assert len(added & selected_originals) == 13
        assert added == set(operator['_reference_source_bytes'](corpus, ReferenceProfile())) - stored
        from casepath_api.workspace_corpus import digest_value
        expanded = deepcopy(plan)
        expanded['final_heads']['auto_unreviewed'] = next(iter(plan['final_heads'].values()))
        expanded['plan_sha256'] = digest_value({k: v for k, v in expanded.items() if k != 'plan_sha256'})
        with pytest.raises(operator['Refused'], match='scope'):
            operator['apply'](connect, expanded, source_commit=COMMIT)
        original_chunk = next(row for row in plan['source_chunks'] if row[0] in selected_originals)
        for change in ('substituted_original', 'unselected_original', 'missing_original'):
            invalid = deepcopy(plan)
            if change == 'substituted_original':
                position = invalid['source_chunks'].index(original_chunk)
                invalid['source_chunks'][position] = operator['_wire']((original_chunk[0], 0, b'Changed original source'))
            elif change == 'missing_original':
                invalid['source_chunks'].remove(original_chunk)
            else:
                unselected = next(other for other in corpus.ids if other not in ReferenceProfile().ids
                                  and any(d['sha256'] not in stored for d in corpus.preview_state(other)['source_descriptors']))
                packet = corpus.packet(unselected)
                descriptor = next(d for d in packet['sources'] if d['sha256'] not in stored)
                invalid['source_chunks'].append(operator['_wire']((descriptor['sha256'], 0,
                                                 packet['source_bytes'][descriptor['artifact_id']])))
            invalid['plan_sha256'] = digest_value({k: v for k, v in invalid.items() if k != 'plan_sha256'})
            with pytest.raises(operator['Refused'], match='source'):
                operator['apply'](connect, invalid, source_commit=COMMIT)
            assert operator['inventory'](connect)[0] == before

        from casepath_api.autonomous_store_v1 import AutonomousStoreError
        _, baseline_values = operator['inventory'](connect)
        absent = old['source_descriptors'][0]
        broken_values = deepcopy(baseline_values)
        broken_values['autonomous_source_chunks']['rows'] = [row for row in broken_values['autonomous_source_chunks']['rows']
                                                           if row[0] != absent['sha256']]
        repaired = deepcopy(plan)
        packet = corpus.packet(cid)
        repaired['source_chunks'].append(operator['_wire']((absent['sha256'], 0,
                                            packet['source_bytes'][absent['artifact_id']])))
        with pytest.raises(AutonomousStoreError, match='source bytes'):
            operator['_verify_plan'](broken_values, repaired)

        # A slow preparation owns no lease. Every meaningful race is still
        # rejected at the final fenced CAS before admission rows are inserted.
        original_acquire = HostedWorkflowLease.acquire
        for race in ('row', 'schema', 'busy', 'expired', 'stolen'):
            incumbent = []
            def raced_acquire(instance):
                assert _CURRENT_OWNER.get() is None
                if race == 'row':
                    with connect() as db:
                        db.execute('UPDATE operator_fixture_cas SET value=\'raced\' WHERE key=1')
                elif race == 'schema':
                    with connect() as db:
                        db.execute('CREATE TABLE operator_fixture_schema(key INTEGER PRIMARY KEY)')
                elif race == 'busy':
                    incumbent.append(original_acquire(lease))
                token = original_acquire(instance)
                if race in ('expired', 'stolen'):
                    with connect() as db:
                        if race == 'expired':
                            db.execute('UPDATE hosted_workflow_lease SET expires_at=0 WHERE singleton=1')
                        else:
                            db.execute('UPDATE hosted_workflow_lease SET owner=\'fixture-stolen\',generation=generation+1 '
                                       'WHERE singleton=1')
                return token
            with monkeypatch.context() as patch:
                patch.setattr(HostedWorkflowLease, 'acquire', raced_acquire)
                error = HostedOwnershipLost if race in ('expired', 'stolen') else operator['Refused']
                with pytest.raises(error):
                    operator['apply'](connect, plan, source_commit=COMMIT)
            assert store.events(cid) == original_rows and store.events(legacy_state['claim_id']) == legacy_rows
            with connect() as db:
                assert db.execute('SELECT count(DISTINCT sha256) AS n FROM autonomous_source_chunks').fetchone()['n'] == 31
                if race == 'row':
                    db.execute('UPDATE operator_fixture_cas SET value=\'baseline\' WHERE key=1')
                elif race == 'schema':
                    db.execute('DROP TABLE operator_fixture_schema')
                elif race == 'stolen':
                    assert db.execute('SELECT owner FROM hosted_workflow_lease').fetchone()['owner'] == 'fixture-stolen'
                    db.execute('UPDATE hosted_workflow_lease SET owner=NULL,expires_at=0 WHERE singleton=1')
            if incumbent:
                lease.release(incumbent[0])
            assert operator['inventory'](connect)[0] == before

        elapsed, phases = [0], []
        globals_ = operator['apply'].__globals__
        def unowned_phase(name, callback):
            def wrapped(*args, **kwargs):
                assert _CURRENT_OWNER.get() is None
                with connect() as db:
                    assert db.execute('SELECT owner FROM hosted_workflow_lease').fetchone()['owner'] is None
                elapsed[0] += LEASE_SECONDS + 1  # Simulated elapsed time; no sleep.
                phases.append(name)
                return callback(*args, **kwargs)
            return wrapped
        def ready_acquire(instance):
            assert elapsed[0] > LEASE_SECONDS and phases == ['inventory', 'verify', 'cas', 'batches']
            return original_acquire(instance)
        with monkeypatch.context() as patch:
            for name, key in [('inventory', 'inventory'), ('verify', '_verify_plan'), ('cas', '_cas_queries'), ('batches', '_query_batches')]:
                patch.setitem(globals_, key, unowned_phase(name, globals_[key]))
            patch.setattr(HostedWorkflowLease, 'acquire', ready_acquire)
            receipt = operator['apply'](connect, plan, source_commit=COMMIT)
        assert receipt['replayed'] is False and receipt['provider_calls'] == receipt['budget_writes'] == 0
        assert store.events(cid)[:len(original_rows)] == original_rows
        assert store.events(legacy_state['claim_id']) == legacy_rows
        assert store.replay(cid, old['revision'])['state'] == old
        restarted = HostedAutonomousStore(journal.path, tmp_path / 'restart-sources', journal=journal, source_store=HostedSources(connect))
        for claim, head in plan['final_heads'].items():
            state = restarted.get(claim)
            assert state['state_sha256'] == head['state_sha256']
            assert state['outcome']['assessment_status'] == 'complete'
        after, _ = operator['inventory'](connect)
        assert after['budget'] == before['budget']
        assert all(after['tables'][name] == value for name, value in before['tables'].items()
                   if name not in {'claim_loop_events', 'autonomous_source_chunks'})
        retry = operator['apply'](connect, plan, source_commit=COMMIT)
        assert retry['replayed'] is True
        assert operator['inventory'](connect)[0] == after
        token = lease.acquire()
        try:
            with pytest.raises(operator['Refused'], match='busy'):
                operator['apply'](connect, plan, source_commit=COMMIT)
        finally:
            lease.release(token)
        store.intake({'title': 'Late source changes the reviewed journal snapshot',
                      'message': 'New independently saved native draft.', 'files': []}, 'late-native-draft')
        with pytest.raises(operator['Refused'], match='changed'):
            operator['apply'](connect, plan, source_commit=COMMIT)
        # Only the lease and two admission tables receive DML during apply.
        forbidden = []
        for request in server.requests[operator_request_start:]:
            for operation in request.get('requests', []):
                statements = [operation['stmt']] if operation['type'] == 'execute' else []
                for statement in statements:
                    sql = statement['sql'].upper()
                    if sql.startswith(('UPDATE WORK_', 'DELETE FROM WORK_', 'INSERT INTO WORK_AUTONOMOUS')):
                        forbidden.append(sql)
        assert not forbidden
        work.close()
    finally:
        server.close()


def test_selected_rejected_provider_stage_and_global_unknown_outcome_refuse_read_only(tmp_path):
    from casepath_api.agent_work.contracts import digest
    from test_autonomous_model_v1 import POLICY
    from test_autonomous_budget_grant_v1 import CONFIG
    from casepath_api.autonomous_reference_v1 import ReferenceProfile
    for status in ('rejected', 'unknown'):
        server = MockHrana(tmp_path / (status + '.sqlite'))
        try:
            connect = server.connection
            lease = HostedWorkflowLease(connect); lease.initialize()
            HostedJournal(tmp_path / ('unused-' + status), connect)
            work = WorkStore(tmp_path / ('work-' + status), connection_factory=connect)
            work.configure_external_budget(POLICY)
            work.activate_autonomous_policy(digest(work.external_budget()), 'Fixture', 'Existing policy fixture', 'fixture-policy')
            identity = {'workflow_id': 'fixture.selected', 'claim_id': ReferenceProfile().ids[0]}
            intent = work.begin_autonomous_call('interpret', identity, CONFIG, request_sha256='a'*64,
                request_bytes=1000, context_sha256='b'*64, schema_sha256='c'*64, proposal_sha256=None)['intent']
            work.complete_autonomous_call(identity['workflow_id'], 'interpret', intent_sha256=intent['intent_sha256'],
                status=status, result=None, cost_usd=None, metadata={'fixture': True})
            before = work.external_budget()
            with pytest.raises(operator['Refused'], match='provider'):
                operator['inventory'](connect)
            assert work.external_budget() == before
            work.close()
        finally:
            server.close()


def test_hosted_canonical_draft_submit_run_startup_recovery_never_calls_model_or_writes(tmp_path):
    from casepath_api.hosted_lease_v1 import HostedAutonomousController
    from casepath_api.autonomous_store_v1 import AutonomousStoreError
    server = MockHrana(tmp_path / 'draft.sqlite')
    try:
        connect = server.connection
        lease = HostedWorkflowLease(connect); lease.initialize()
        journal = HostedJournal(tmp_path / 'unused', connect)
        store = HostedAutonomousStore(journal.path, tmp_path / 'draft-sources', journal=journal, source_store=HostedSources(connect))
        calls = []
        class Spy:
            def interpret(self, *args):
                calls.append('model interpret')
                raise AssertionError('Incomplete draft invoked model')
        service = HostedAutonomousController(store, CanonicalCorpus()._corpus.static_policy(), Spy(), lease=lease,
                                            enforce_intake_gate=True)
        try:
            draft = store.intake({'title': 'Draft', 'message': 'A termination notice arrived.', 'files': []}, 'hosted-incomplete-draft')
            with connect() as db:
                before_lease = tuple(db.execute('SELECT * FROM hosted_workflow_lease').fetchone())
            rows = store.events(draft['claim_id'])
            service.resume()
            service.wake_pending(force_discovery=True)
            assert not service._waiting and not service._jobs and service._recovery_timer is None
            for entry in (service.submit, service.run):
                with pytest.raises(AutonomousStoreError, match='intake incomplete'):
                    entry(draft['claim_id'])
            assert not calls and store.events(draft['claim_id']) == rows
            with connect() as db:
                assert tuple(db.execute('SELECT * FROM hosted_workflow_lease').fetchone()) == before_lease
        finally:
            service.shutdown()
    finally:
        server.close()
