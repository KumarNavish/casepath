"""Accepted hosted work recovers without browser traffic or live providers."""
from base64 import b64encode
from threading import Event, RLock

import pytest

from casepath_api import hosted_lease_v1 as hosted
from casepath_api.agent_work.store import WorkStore
from casepath_api.autonomous_controller_v1 import AutonomousController
from casepath_api.autonomous_corpus_v1 import CanonicalCorpus
from casepath_api.autonomous_model_v1 import AutonomousModelError
from casepath_api.hosted_storage_v1 import HostedAutonomousStore, HostedJournal, HostedSources
from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root, digest_value
from hosted_hrana_fixture import MockHrana
from test_autonomous_canonical_store_v1 import admit, original_packet
from test_autonomous_controller_v1 import SemanticFixture, packet
from test_autonomous_model_v1 import POLICY


class ManualClock:
    """Fire production timer callbacks and drain real executor callbacks exactly."""
    def __init__(self):
        self.now, self.timers = 0.0, []
        self.lock = RLock()

    def timer(self, interval, callback):
        clock = self
        class Timer:
            def __init__(self):
                self.when, self.cancelled, self.started = clock.now + interval, False, False
                self.daemon = False

            def start(self):
                self.started = True
                with clock.lock:
                    clock.timers.append(self)

            def cancel(self):
                self.cancelled = True

            def fire(self):
                self.cancelled = True
                callback()
        return Timer()

    @property
    def pending(self):
        with self.lock:
            return [timer for timer in self.timers if not timer.cancelled]

    def advance(self, seconds, controller):
        target = self.now + seconds
        while True:
            due = sorted((timer for timer in self.pending if timer.when <= target), key=lambda t: t.when)
            if not due:
                self.now = target
                return
            self.now = due[0].when
            due[0].fire()
            drain(controller)


def drain(controller):
    controller._executor.submit(lambda: None).result(timeout=10)


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    clock = ManualClock()
    monkeypatch.setattr(hosted, 'Timer', clock.timer, raising=False)
    monkeypatch.setattr(hosted, 'monotonic', lambda: clock.now)
    server = MockHrana(tmp_path / 'accepted-work.sqlite')
    lease = hosted.HostedWorkflowLease(server.connection)
    lease.initialize()
    journal = HostedJournal(tmp_path / 'unused-journal', lease.connect)
    store = HostedAutonomousStore(journal.path, journal=journal, source_store=HostedSources(lease.connect))
    policy = PublicCorpus(default_workspace_corpus_root()).static_policy()
    controller = hosted.HostedAutonomousController(store, policy, lease=lease)
    try:
        yield controller, store, lease, clock, server
    finally:
        controller.shutdown()
        server.close()


def accepted(store, identity):
    if identity == 'canonical':
        return admit(store, original_packet())['state']['claim_id']
    return store.intake(packet(), 'legacy-intake')['claim_id']


@pytest.mark.parametrize('identity', ['canonical', 'legacy'])
def test_busy_accepted_work_resumes_after_release_without_http_or_resubmission(runtime, identity):
    controller, store, lease, clock, _ = runtime
    claim = accepted(store, identity)
    incumbent = lease.acquire()
    controller.submit(claim)
    drain(controller)
    assert store.get(claim)['revision'] == 1
    assert claim in controller._waiting
    lease.release(incumbent)
    clock.advance(5, controller)
    settled = store.get(claim)
    assert settled['deferral']['code'] == 'model_unavailable'
    assert len(settled['acquired_sources']) == 2
    assert controller._waiting == {}
    assert clock.pending == []


@pytest.mark.parametrize('identity', ['canonical', 'legacy'])
def test_startup_busy_work_recovers_only_saved_claims(runtime, identity, monkeypatch):
    controller, store, lease, clock, _ = runtime
    claim = accepted(store, identity)
    incumbent = lease.acquire()
    controller.resume()
    drain(controller)
    assert len(clock.pending) == 1
    monkeypatch.setattr(store, 'list', lambda: pytest.fail('timer performed global discovery'))
    lease.release(incumbent)
    clock.advance(5, controller)
    assert store.get(claim)['deferral']['code'] == 'model_unavailable'
    assert [s['claim_id'] for s in HostedAutonomousStore.list(store)] == [claim]
    assert clock.pending == []


def test_never_started_originals_have_no_timer_queue_or_journals(runtime):
    controller, store, _, clock, _ = runtime
    corpus = CanonicalCorpus(PublicCorpus(default_workspace_corpus_root()))
    assert len(corpus.ids) == 150
    for claim in corpus.ids:
        assert corpus.preview_state(claim)['revision'] == 0
    controller.resume()
    clock.advance(1000, controller)
    assert store.list() == []
    assert controller._waiting == controller._jobs == {}
    assert clock.pending == []


@pytest.mark.parametrize('identity', ['canonical', 'legacy'])
def test_lost_ownership_after_saved_start_resumes_same_work(runtime, identity, monkeypatch):
    controller, store, _, clock, _ = runtime
    claim = accepted(store, identity)
    once = controller._once
    lost = []
    def interrupted(*args, **kwargs):
        state = once(*args, **kwargs)
        if not lost:
            lost.append(True)
            raise hosted.HostedOwnershipLost('saved start acknowledgement lost')
        return state
    monkeypatch.setattr(controller, '_once', interrupted)
    controller.submit(claim)
    drain(controller)
    assert store.get(claim)['status'] == 'running'
    clock.advance(5, controller)
    events = store.events(claim)
    assert sum(e['kind'] == 'work.started' for e in events) == 1
    assert store.get(claim)['deferral']['code'] == 'model_unavailable'
    assert controller._jobs == controller._waiting == {}
    assert clock.pending == []


@pytest.mark.parametrize('identity', ['canonical', 'legacy'])
@pytest.mark.parametrize('code', ['paused', 'provider_deferred', 'verification_deferred', 'execution_deferred'])
def test_lost_job_with_recorded_deferral_is_never_resent(runtime, identity, code, monkeypatch):
    controller, store, _, clock, _ = runtime
    claim = accepted(store, identity)
    calls = []
    def interrupted(instance, cid):
        calls.append(cid)
        state = store.get(cid)
        store.append(cid, 'work.deferred', {'code': code, 'reason': 'Recorded physical attempt boundary.'},
                     expected_revision=state['revision'], expected_state_sha256=state['state_sha256'],
                     idempotency_key='recorded-deferral')
        raise hosted.HostedOwnershipLost('lost after accepted deferral')
    monkeypatch.setattr(AutonomousController, 'run', interrupted)
    controller.submit(claim)
    drain(controller)
    assert claim in controller._waiting
    saved = store.get(claim)['state_sha256']
    clock.advance(500, controller)
    assert calls == [claim]
    assert store.get(claim)['state_sha256'] == saved
    assert controller._waiting == {}
    assert clock.pending == []


@pytest.mark.parametrize('identity', ['canonical', 'legacy'])
@pytest.mark.parametrize('outcome', [None, 'unknown'])
def test_unknown_provider_reservation_survives_loss_without_second_attempt(runtime, identity, outcome, monkeypatch):
    controller, store, lease, clock, server = runtime
    claim = accepted(store, identity)
    model = SemanticFixture()
    controller.model = model
    work = WorkStore('/unused', connection_factory=lease.connect)
    work.configure_external_budget(POLICY)
    work.activate_autonomous_policy(digest_value(work.external_budget()), 'Fixture', 'Bounded fixture', 'activate-fixture')
    config = {'model': 'test/semantic', 'context_length': 131072, 'catalogue_entry_sha256': 'a'*64,
              'prompt_price': '0.0000001', 'completion_price': '0.0000002', 'request_price': '0',
              'max_request_bytes': 64000, 'max_output_tokens': 3500, 'max_calls_per_workflow': 2,
              'protocol': 'strict_json_schema', 'adapter_version': 'casepath.autonomous-model/1.0.0',
              'reasoning_supported': False, 'free': False, 'timeout_seconds': 60}
    physical_attempts = []
    def interpret(context, identity):
        context_hash = digest_value(context)
        reservation = work.begin_autonomous_call('interpret', identity, config,
            request_sha256=context_hash, request_bytes=100, context_sha256=context_hash, schema_sha256='b'*64)
        if 'intent' not in reservation:
            raise AutonomousModelError('Saved provider result is unknown; no resend.', reservation['receipt'])
        physical_attempts.append(identity['workflow_id'])
        if outcome:
            work.complete_autonomous_call(identity['workflow_id'], 'interpret',
                intent_sha256=reservation['intent']['intent_sha256'], status=outcome,
                result=None, cost_usd=None, metadata={'reason': 'fixture_unconfirmed'})
        raise hosted.HostedOwnershipLost('ownership lost after physical attempt')
    monkeypatch.setattr(model, 'interpret', interpret)
    try:
        controller.submit(claim)
        drain(controller)
        before = work.external_budget()
        assert before['provider_calls_used'] == before['unknown_calls'] == 1
        clock.advance(500, controller)
        after = work.external_budget()
        assert len(physical_attempts) == 1
        assert after['provider_calls_used'] == after['unknown_calls'] == 1
        assert after['reserved_cost_usd'] == before['reserved_cost_usd']
        assert after['actual_cost_usd'] == before['actual_cost_usd']
        assert after['autonomous_policy'] == before['autonomous_policy']
        assert store.get(claim)['deferral']['code'] in {'execution_deferred', 'provider_deferred'}
        with server.connection() as db:
            assert db.execute('SELECT COUNT(*) FROM work_autonomous_calls').fetchone()[0] == 1
        assert controller._waiting == {}
        assert clock.pending == []
    finally:
        work.close()


def test_other_process_completion_replaces_stale_run_with_learning_only(runtime):
    controller, store, lease, clock, _ = runtime
    claim = accepted(store, 'legacy')
    model = SemanticFixture()
    controller.model = model
    incumbent = lease.acquire()
    controller.submit(claim)
    drain(controller)
    lease.release(incumbent)
    other = hosted.HostedAutonomousController(store, controller.policy, model, lease=lease)
    try:
        settled = other.run(claim)
        assert settled['outcome'] and len(model.calls) == 2
        clock.advance(5, controller)
        assert store.get(claim)['state_sha256'] == settled['state_sha256']
        assert len(model.calls) == 2
        assert settled['run_id'] in controller._learned
        assert controller._jobs == controller._waiting == {}
        assert clock.pending == []
    finally:
        other.shutdown()


def test_pending_queue_is_fair_and_one_worker_serial(runtime, monkeypatch):
    controller, store, lease, clock, _ = runtime
    claims = [accepted(store, 'canonical'), accepted(store, 'legacy')]
    incumbent = lease.acquire()
    entered, release = Event(), Event()
    calls, active = [], []
    def run(instance, claim):
        assert active == []
        active.append(claim)
        calls.append(claim)
        if claim == claims[0]:
            entered.set()
            assert release.wait(timeout=10)
        active.pop()
    monkeypatch.setattr(AutonomousController, 'run', run)
    for claim in claims:
        controller.submit(claim)
    drain(controller)
    lease.release(incumbent)
    timer = clock.pending[0]
    clock.now = timer.when
    timer.fire()
    try:
        assert entered.wait(timeout=10)
        assert calls == [claims[0]]
        assert clock.pending == []
    finally:
        release.set()
    drain(controller)
    assert calls == claims
    assert active == []
    assert controller._jobs == controller._waiting == {}
    assert clock.pending == []


def test_late_source_waits_for_completion_and_receives_fresh_retry_window(runtime, monkeypatch):
    controller, store, _, clock, _ = runtime
    claim = accepted(store, 'legacy')
    model = SemanticFixture()
    controller.model = model
    entered, release = Event(), Event()
    interpret = model.interpret
    def blocked(context, identity):
        if not model.calls:
            entered.set()
            assert release.wait(timeout=10)
        return interpret(context, identity)
    monkeypatch.setattr(model, 'interpret', blocked)
    controller.submit(claim)
    try:
        assert entered.wait(timeout=10)
        state = store.get(claim)
        store.add_sources(claim, [{'file_name': 'late.txt', 'media_type': 'text/plain',
                                 'content_base64': b64encode(b'Additional spouse notice.').decode()}],
                          expected_revision=state['revision'], expected_state_sha256=state['state_sha256'],
                          idempotency_key='late-source')
        controller.submit(claim)
        assert claim in controller._waiting
        assert clock.pending == []
        clock.now = 500  # The physical job takes longer than the recovery window.
    finally:
        release.set()
    drain(controller)
    assert len(model.calls) == 1  # Superseded attempt never reaches verification.
    assert len(clock.pending) == 1
    clock.advance(5, controller)
    settled = store.get(claim)
    assert settled['outcome'] and len(settled['acquired_sources']) == 3
    assert len(model.calls) == 3
    assert controller._jobs == controller._waiting == {}
    assert clock.pending == []


def test_normal_lease_expiry_is_inside_bounded_recovery_window(runtime):
    controller, store, lease, clock, server = runtime
    claim = accepted(store, 'canonical')
    lease.acquire()
    controller.resume()
    drain(controller)
    clock.advance(175, controller)
    assert store.get(claim)['revision'] == 1
    with server.connection() as db:
        db.execute('UPDATE hosted_workflow_lease SET expires_at=0')
    clock.advance(5, controller)
    assert store.get(claim)['deferral']['code'] == 'model_unavailable'
    assert clock.pending == []


def test_persistent_owner_parks_after_bound_and_explicit_wake_rearms(runtime, monkeypatch):
    controller, store, lease, clock, _ = runtime
    claim = accepted(store, 'legacy')
    incumbent = lease.acquire()
    controller.submit(claim)
    drain(controller)
    monkeypatch.setattr(store, 'list', lambda: pytest.fail('timer performed global discovery'))
    clock.advance(190, controller)
    assert claim in controller._waiting
    assert store.get(claim)['revision'] == 1
    assert clock.pending == []
    lease.release(incumbent)
    clock.advance(1000, controller)
    assert store.get(claim)['revision'] == 1
    controller.submit(claim)
    drain(controller)
    assert store.get(claim)['deferral']['code'] == 'model_unavailable'
    assert clock.pending == []


def test_shutdown_cancels_timer_and_racing_callback_cannot_dispatch(runtime, monkeypatch):
    controller, store, lease, clock, _ = runtime
    claim = accepted(store, 'canonical')
    incumbent = lease.acquire()
    controller.submit(claim)
    drain(controller)
    timer = clock.pending[0]
    controller.shutdown()
    lease.release(incumbent)
    monkeypatch.setattr(store, 'get', lambda *a: pytest.fail('shutdown timer read saved work'))
    timer.fire()  # Cancellation cannot prevent an already-entering callback.
    assert clock.pending == []
    assert controller._jobs == {}
