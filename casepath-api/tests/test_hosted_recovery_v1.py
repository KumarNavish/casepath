"""Focused recovery checks: in-memory DB and explicit model fixture only."""
from copy import deepcopy
from pathlib import Path
import sqlite3
from threading import Event, RLock
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from casepath_api.autonomous_controller_v1 import AutonomousController
from casepath_api.autonomous_store_v1 import AutonomousStore
from casepath_api.hosted_lease_v1 import HostedAutonomousController, HostedWorkflowLease
from casepath_api.hosted_storage_v1 import HostedJournal, HostedSources
from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


class StateStore:
    def __init__(self):
        self.rows, self.lock = {}, RLock()

    def get(self, claim):
        with self.lock:
            return deepcopy(self.rows[claim])

    def list(self):
        with self.lock:
            return deepcopy(list(self.rows.values()))

    def put(self, claim, **changes):
        with self.lock:
            self.rows[claim] = {'claim_id': claim, 'status': 'received', 'outcome': None,
                                'run_id': None, 'source_descriptors': [], 'deferral': None, **changes}


class HostedRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.uri = 'file:recovery-' + uuid4().hex + '?mode=memory&cache=shared'
        self.keeper = sqlite3.connect(self.uri, uri=True, isolation_level=None)
        self.lease = HostedWorkflowLease(self.connect)
        self.lease.initialize()
        self.store, self.controllers = StateStore(), []

    def tearDown(self):
        for controller in self.controllers:
            controller.shutdown()
        self.keeper.close()

    def connect(self):
        db = sqlite3.connect(self.uri, uri=True, isolation_level=None, factory=ClosingConnection)
        db.row_factory = sqlite3.Row
        return db

    def controller(self, store=None, model=None, policy=None):
        value = HostedAutonomousController(store or self.store, policy or {}, model, lease=self.lease)
        self.controllers.append(value)
        return value

    def drain(self, controller):
        # A queue barrier also waits for prior Future completion callbacks.
        controller._executor.submit(lambda: None).result(timeout=10)

    def test_http_poll_discovers_claim_saved_after_startup(self):
        from fastapi.testclient import TestClient
        import casepath_api.hosted_app_v1 as hosted_app
        live, calls = [], []
        def construct(store, policy, model, *, lease):
            controller = HostedAutonomousController(store, policy, model, lease=lease)
            live.append(controller)
            self.controllers.append(controller)
            return controller
        def run(instance, claim):
            calls.append(claim)
            instance.store.put(claim, status='deferred', deferral={'code': 'model_unavailable'})
        env = {'CASEPATH_SITE_ORIGIN': 'https://casepath.example', 'CASEPATH_PROXY_TOKEN': 't'*48,
               'CASEPATH_SOURCE_COMMIT': 'a'*40, 'CASEPATH_HOSTED_WRITABLE': '1',
               'CASEPATH_AUTONOMOUS_ENABLED': '0'}
        headers = {'X-CasePath-Proxy-Token': 't'*48, 'X-CasePath-Site-Origin': env['CASEPATH_SITE_ORIGIN'],
                   'Origin': env['CASEPATH_SITE_ORIGIN'], 'X-CasePath-Agent-Work': '1'}
        with patch.object(hosted_app, 'HostedAutonomousController', side_effect=construct), \
             patch.object(hosted_app, 'HostedAutonomousStore', return_value=self.store), \
             patch.object(AutonomousController, 'run', run):
            app = hosted_app.create_hosted_app(database=SimpleNamespace(connect=self.connect),
                                               environment=env, runtime_directory='/private/tmp')
            with TestClient(app) as client:
                self.drain(live[0])
                self.store.put('late-claim')  # Another process commits after resume().
                self.assertEqual(calls, [])
                live[0]._next_discovery = 0.0  # Next actual HTTP poll is due.
                response = client.get('/api/claim-loops/v1/autonomous/status', headers=headers)
                self.assertEqual(response.status_code, 200)
                self.drain(live[0])
                self.assertEqual(calls, ['late-claim'])
                client.get('/api/claim-loops/v1/autonomous/status', headers=headers)
                self.drain(live[0])
                self.assertEqual(calls, ['late-claim'])

    def test_all_failure_deferrals_and_pause_are_excluded(self):
        for code in ('paused', 'provider_deferred', 'verification_deferred', 'execution_deferred', 'model_unavailable'):
            self.store.put(code, status='deferred', deferral={'code': code})
        # An outcome left behind by a later failure does not override its deferral.
        self.store.put('failed-learning', status='deferred', outcome={'status': 'deferred'},
                       run_id='old-workflow', deferral={'code': 'execution_deferred'})
        service = self.controller()
        with patch.object(AutonomousController, 'run', side_effect=AssertionError('unexpected redispatch')), \
             patch.object(AutonomousController, '_learn', side_effect=AssertionError('unexpected learning')):
            service.wake_pending()
            self.drain(service)
        self.assertEqual(service._waiting, {})
        with patch.object(AutonomousController, 'run', return_value=None) as run:
            service.model = object()
            service.wake_pending(force_discovery=True)
            self.drain(service)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args, (service, 'model_unavailable'))

    def test_queued_claim_is_rechecked_after_ownership(self):
        self.store.put('queued')
        service = self.controller()
        incumbent = self.lease.acquire()
        service.wake_pending()
        self.drain(service)
        self.assertIn('queued', service._waiting)
        self.store.put('queued', status='deferred', deferral={'code': 'provider_deferred'})
        self.lease.release(incumbent)
        # Exercise an already-queued stale run directly, before new discovery.
        with patch.object(AutonomousController, 'run', side_effect=AssertionError('unexpected redispatch')):
            self.assertEqual(service.run('queued')['deferral']['code'], 'provider_deferred')
            service.wake_pending(force_discovery=True)
            self.drain(service)
        self.assertNotIn('queued', service._waiting)

    def test_learning_noop_runs_once_per_process_and_busy_attempt_is_not_settled(self):
        self.store.put('finished', status='deferred', outcome={'status': 'deferred'}, run_id='workflow')
        service = self.controller()
        incumbent = self.lease.acquire()
        with patch.object(AutonomousController, '_learn', return_value=None) as learn:
            service.wake_pending()
            self.drain(service)
            self.assertEqual(learn.call_count, 0)
            self.assertNotIn('workflow', service._learned)
            self.lease.release(incumbent)
            for _ in range(3):
                service.wake_pending(force_discovery=True)
                self.drain(service)
            self.assertEqual(learn.call_count, 1)
            restarted = self.controller()
            restarted.resume()
            self.drain(restarted)
            self.assertEqual(learn.call_count, 2)  # Existing one-time restart recovery.

    def test_http_discovery_does_not_queue_duplicate_active_work(self):
        self.store.put('active')
        service = self.controller()
        entered, release, calls = Event(), Event(), []
        def run(instance, claim):
            calls.append(claim)
            entered.set()
            self.assertTrue(release.wait(timeout=2))
            self.store.put(claim, status='deferred', deferral={'code': 'provider_deferred'})
        with patch.object(AutonomousController, 'run', run):
            try:
                service.wake_pending()
                self.assertTrue(entered.wait(timeout=2))
                service.wake_pending()
                service.wake_pending()
                self.assertNotIn('active', service._waiting)
            finally:
                release.set()
            self.drain(service)
            service.wake_pending()
            self.drain(service)
        self.assertEqual(calls, ['active'])

    def test_finished_real_engine_work_never_redispatches_model_on_poll_or_restart(self):
        from test_autonomous_controller_v1 import SemanticFixture, packet
        # Construct the accepted store around only in-memory durable surrogates.
        # No source directories, physical database files or provider calls exist.
        store = AutonomousStore.__new__(AutonomousStore)
        store._read_only, store.storage = False, None
        store.journal = HostedJournal(Path('/unused'), self.lease.connect)
        store._source_store = HostedSources(self.lease.connect)
        store.path, store.source_root = Path('/unused'), Path('/unused')
        store._extractions, store._extraction_lock = {}, RLock()
        model = SemanticFixture()
        policy = PublicCorpus(default_workspace_corpus_root()).static_policy()
        service = self.controller(store, model, policy)
        service.resume()
        first = store.intake(packet(), 'after-startup-intake')
        service.wake_pending(force_discovery=True)
        self.drain(service)
        settled = store.get(first['claim_id'])
        self.assertIsNotNone(settled['outcome'])
        self.assertEqual(len(model.calls), 2)
        for _ in range(3):
            service.wake_pending(force_discovery=True)
            self.drain(service)
        restarted = self.controller(store, model, policy)
        restarted.resume()
        self.drain(restarted)
        self.assertEqual(store.get(first['claim_id'])['state_sha256'], settled['state_sha256'])
        self.assertEqual(len(model.calls), 2)

    def test_discovery_is_throttled_without_timers(self):
        service = self.controller()
        with patch.object(self.store, 'list', wraps=self.store.list) as discover:
            service.resume()
            for _ in range(3):
                service.wake_pending()
            self.assertEqual(discover.call_count, 1)
            service._next_discovery = 0.0
            service.wake_pending()
            self.assertEqual(discover.call_count, 2)
            service.resume()  # Explicit startup recovery always scans.
            self.assertEqual(discover.call_count, 3)
if __name__ == '__main__':
    unittest.main(verbosity=2)
