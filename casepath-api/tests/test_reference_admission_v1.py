import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import runpy

import pytest

from hosted_hrana_fixture import MockHrana
from casepath_api.agent_work.store import WorkStore
from casepath_api.autonomous_controller_v1 import AutonomousController
from casepath_api.autonomous_corpus_v1 import CanonicalCorpus
from casepath_api.hosted_lease_v1 import HostedWorkflowLease, HostedOwnershipLost, LEASE_SECONDS, _CURRENT_OWNER
from casepath_api.hosted_storage_v1 import HostedAutonomousStore, HostedJournal, HostedSources

operator = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'tools/admit_reference.py'))
COMMIT = 'e176657b9307ad657fd895e57e83ce88e140bcf5'


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
