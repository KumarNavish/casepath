"""Fenced workflow ownership using isolated in-memory SQLite."""
from concurrent.futures import ThreadPoolExecutor
import sqlite3
from threading import Barrier
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from casepath_api.autonomous_controller_v1 import AutonomousController
from casepath_api.hosted_lease_v1 import (
    HostedAutonomousController, HostedOwnershipLost, HostedWorkflowLease,
    _CURRENT_OWNER, _FencedConnection,
)


class Connection:
    """Tiny closing DB-API adapter with controllable ambiguous commit."""
    def __init__(self, raw, *, fail_commit=False, fail_prefetch=False):
        self.raw = raw
        self.fail_commit, self.fail_prefetch = fail_commit, fail_prefetch

    def __getattr__(self, name):
        return getattr(self.raw, name)

    def commit(self):
        self.raw.commit()
        if self.fail_commit:
            raise RuntimeError('Simulated lost COMMIT acknowledgement')

    def prefetch(self, queries):
        if self.fail_prefetch:
            raise RuntimeError('Simulated batch transport failure')
        for sql, args in queries:
            self.raw.execute(sql, args).fetchall()

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        try:
            self.commit() if kind is None else self.raw.rollback()
        finally:
            self.raw.close()


class HostedLeaseTests(unittest.TestCase):
    def setUp(self):
        self.uri = 'file:lease-test-' + uuid4().hex + '?mode=memory&cache=shared'
        self.keeper = sqlite3.connect(self.uri, uri=True, isolation_level=None)
        self.keeper.execute('CREATE TABLE effects(value TEXT)')
        self.lease = HostedWorkflowLease(self.connect)
        self.lease.initialize()
        self.controllers = []

    def tearDown(self):
        for controller in self.controllers:
            controller.shutdown()
        self.keeper.close()

    def connect(self, **options):
        raw = sqlite3.connect(self.uri, uri=True, isolation_level=None)
        raw.row_factory = sqlite3.Row
        return Connection(raw, **options)

    def controller(self, store=None):
        store = store or SimpleNamespace(
            list=lambda: [],
            get=lambda claim: {'claim_id': claim, 'status': 'received', 'outcome': None,
                               'run_id': None, 'source_descriptors': [], 'deferral': None})
        controller = HostedAutonomousController(store, {}, lease=self.lease)
        self.controllers.append(controller)
        return controller

    def row(self):
        with self.connect() as db:
            return dict(db.execute('SELECT * FROM hosted_workflow_lease').fetchone())

    def expire(self):
        with self.connect() as db:
            db.execute('UPDATE hosted_workflow_lease SET expires_at=0')

    def test_concurrent_acquisition_has_one_committed_winner(self):
        barrier = Barrier(2)
        def acquire():
            barrier.wait(timeout=2)
            try:
                return self.lease.acquire()
            except HostedOwnershipLost:
                return None  # SQLite shared-memory BUSY is fail-closed too.
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: acquire(), range(2)))
        winners = [result for result in results if result is not None]
        self.assertEqual(len(winners), 1)
        self.assertEqual(self.row()['owner'], winners[0].owner)
        self.assertIsNone(self.lease.acquire())
        self.lease.release(winners[0])
        newer = self.lease.acquire()
        self.assertGreater(newer.generation, winners[0].generation)

    def test_generation_continues_above_32_bit(self):
        with self.connect() as db:
            db.execute('UPDATE hosted_workflow_lease SET generation=2147483647')
        token = self.lease.acquire()
        self.assertIsNotNone(token)
        self.assertEqual(token.generation, 2147483648)

    def test_renewal_uses_db_clock_and_expired_begin_rolls_back(self):
        token = self.lease.acquire()
        reset = _CURRENT_OWNER.set(token)
        try:
            with self.lease.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                delta = db.execute("SELECT expires_at-CAST(strftime('%s','now') AS INTEGER) FROM hosted_workflow_lease").fetchone()[0]
                self.assertIn(delta, (179, 180))
                db.execute('INSERT INTO effects VALUES (?)', ('first',))
            self.expire()
            db = self.lease.connect()
            try:
                with self.assertRaises(HostedOwnershipLost):
                    db.execute('BEGIN IMMEDIATE')
                self.assertFalse(db.in_transaction)
            finally:
                db.close()
        finally:
            _CURRENT_OWNER.reset(reset)
        successor = self.lease.acquire()
        self.lease.release(token)
        self.assertEqual(self.row()['owner'], successor.owner)
        self.assertEqual(self.keeper.execute('SELECT * FROM effects').fetchall(), [('first',)])

    def test_owned_autocommit_and_changed_context_are_refused(self):
        token = self.lease.acquire()
        reset = _CURRENT_OWNER.set(token)
        try:
            with self.lease.connect() as db:
                with self.assertRaises(HostedOwnershipLost):
                    db.execute("INSERT INTO effects VALUES ('unfenced')")
                db.execute('BEGIN IMMEDIATE')
                db.execute("INSERT INTO effects VALUES ('uncommitted')")
                nested_reset = _CURRENT_OWNER.set(None)
                try:
                    with self.assertRaises(HostedOwnershipLost):
                        db.commit()
                finally:
                    _CURRENT_OWNER.reset(nested_reset)
                db.rollback()
        finally:
            _CURRENT_OWNER.reset(reset)
        with self.lease.connect() as db:
            db.execute("INSERT INTO effects VALUES ('api-intake')")
        self.assertEqual(self.keeper.execute('SELECT * FROM effects').fetchall(), [('api-intake',)])

    def test_unconfirmed_acquisition_grants_no_local_authority(self):
        uncertain = HostedWorkflowLease(lambda: self.connect(fail_commit=True))
        with self.assertRaises(HostedOwnershipLost):
            uncertain.acquire()
        self.assertIsNotNone(self.row()['owner'])  # Commit may actually persist.
        self.assertIsNone(self.lease.acquire())

    def test_prefetch_and_commit_failure_bypass_generic_abandon(self):
        controller = self.controller()
        deferred = []
        def callback(failure):
            try:
                raw = self.connect(fail_prefetch=failure == 'prefetch', fail_commit=failure == 'commit')
                with _FencedConnection(raw, self.lease) as db:
                    db.execute('BEGIN IMMEDIATE')
                    db.prefetch([('SELECT 1', ())])
                    db.execute('INSERT INTO effects VALUES (?)', (failure,))
            except Exception:
                deferred.append(failure)  # Same boundary as the base controller.
                raise
        for failure in ('prefetch', 'commit'):
            self.assertIsNone(controller._owned(failure, ('run', None), lambda: callback(failure)))
            self.assertIn(failure, controller._waiting)
        self.assertEqual(deferred, [])
        self.assertEqual(self.keeper.execute('SELECT * FROM effects').fetchall(), [('commit',)])
        self.assertIsNone(self.row()['owner'])

    def test_busy_controller_has_no_effect_and_retries_on_http_wake_only(self):
        incumbent = self.lease.acquire()
        controller = self.controller()
        calls = []
        def run(instance, claim):
            calls.append(('run', claim))
        with patch.object(AutonomousController, 'run', run):
            with controller._lock:
                controller.submit('claim')
                blocked = controller._jobs['claim']
            self.assertIsNone(blocked.result(timeout=2))
            self.assertEqual(calls, [])
            self.assertIn('claim', controller._waiting)
            self.lease.release(incumbent)
            self.assertEqual(calls, [])
            with controller._lock:
                controller.wake_pending()
                resumed = controller._jobs['claim']
            resumed.result(timeout=2)
        self.assertEqual(calls, [('run', 'claim')])
        self.assertNotIn('claim', controller._waiting)

    def test_startup_learning_is_guarded_and_survives_nested_shutdown(self):
        state = {'claim_id': 'claim', 'run_id': 'workflow', 'status': 'deferred',
                 'outcome': {'status': 'deferred'}, 'source_descriptors': []}
        controller = self.controller(SimpleNamespace(list=lambda: [dict(state)], get=lambda claim: dict(state)))
        incumbent = self.lease.acquire()
        learned = []
        def learn(instance, claim, workflow):
            learned.append((claim, workflow, _CURRENT_OWNER.get().owner))
        with patch.object(AutonomousController, '_learn', learn):
            with controller._lock:
                controller.resume()
                blocked = controller._jobs['claim']
            blocked.result(timeout=2)
            self.assertEqual(learned, [])
            self.assertEqual(controller._waiting['claim'], ('learn', 'workflow'))
            self.lease.release(incumbent)
            with controller._lock:
                controller.wake_pending()
                resumed = controller._jobs['claim']
            resumed.result(timeout=2)
            def finishing_run(instance, claim):
                instance._closed = True  # Shutdown admission closed mid-run.
                state.update(status='deferred', outcome={'status': 'deferred'}, run_id='nested-workflow')
                instance._learn(claim, 'nested-workflow')
            state.update(status='received', outcome=None, run_id=None)
            with patch.object(AutonomousController, 'run', finishing_run):
                controller.run('claim')
        self.assertEqual([item[:2] for item in learned],
                         [('claim', 'workflow'), ('claim', 'nested-workflow')])
        self.assertIsNone(self.row()['owner'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
