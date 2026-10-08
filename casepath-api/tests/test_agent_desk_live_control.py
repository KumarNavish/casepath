"""Handler stop dispatch with real isolated journals and no provider transport."""
import pytest
from types import SimpleNamespace

from casepath_api.agent_desk_v1 import AgentDeskServiceV1
from casepath_api.workspace_corpus import digest_value
from test_agent_desk_v1 import CLAIM, control_body, desk
from test_agent_work_openrouter_demo import POLICY, config, reserve, complete


def external_run(desk, status):
    context = desk.work.context(CLAIM)
    cfg = config().public()
    desk.work.store.configure_external_budget(POLICY)
    row, _ = desk.work.store.create(CLAIM, "desk.explicit.external.stop", {
        "context": context["context"], "requested_context_sha256": context["context_sha256"],
        "facts_worker": "external_facts", "worker_config": cfg, "worker_config_sha256": digest_value(cfg)}, external_limit=3)
    run_id = row["run_id"]
    if status != "queued":
        assert desk.work.store.acquire(run_id, "owner")
    if status in {"running", "interrupted"}:
        reserve(desk.work.store, run_id)
    if status == "interrupted":
        desk.work.store.finish(run_id, "owner", "interrupted", "Synthetic unknown provider outcome")
    return run_id


@pytest.mark.parametrize("status", ["queued", "running", "interrupted"])
def test_handler_stop_cancels_further_external_work_without_erasing_pending_outcome(desk, monkeypatch, status):
    run_id = external_run(desk, status)
    before = desk.work.store.pending_calls(run_id)
    monkeypatch.setattr(desk.work, "pause", lambda *args: pytest.fail("external requests cannot enter resumable local pause"))
    body = control_body(desk, "pause")
    result = desk.control(CLAIM, **body, idempotency_key="desk.external.stop.once")
    assert result["projection_sha256"] == digest_value({k: v for k, v in result.items() if k != "projection_sha256"})
    assert result["agent"]["pause_requested"] is True and result["continuation"] is None
    assert result["agent"]["run"]["run_id"] == run_id
    assert desk.work.store.pending_calls(run_id) == before
    assert desk.work.store.get_run(run_id)["status"] == ("running" if status == "running" else "cancelled")
    events = desk.work.store.events(run_id)
    assert sum(e["operation"] == "RUN_CANCEL_REQUESTED" for e in events) == 1
    assert all(e["operation"] != "RUN_PAUSE_REQUESTED" for e in events)
    assert len(desk.work.store.list_runs(CLAIM)) == 1
    repeated = desk.control(CLAIM, **body, idempotency_key="desk.external.stop.once")
    assert repeated["replayed"] and repeated["event_sha256"] == result["event_sha256"]
    assert desk.work.store.events(run_id) == events
    assert desk.work.store.pending_calls(run_id) == before


def test_external_completion_between_stop_projection_and_dispatch_preserves_handler_receipt(desk, monkeypatch):
    run_id = external_run(desk, "terminal-race")
    cancel = desk.work.cancel
    def finish_then_cancel(claim_id, selected_run):
        desk.work.store.finish(selected_run, "owner", "completed", "Finished before the stop was dispatched")
        return cancel(claim_id, selected_run)
    monkeypatch.setattr(desk.work, "cancel", finish_then_cancel)
    result = desk.control(CLAIM, **control_body(desk, "pause"), idempotency_key="desk.external.stop.raced")
    assert result["agent"]["pause_requested"] is True
    assert result["agent"]["run"]["status"] == "completed"
    assert result["agent"]["run"]["run_id"] == run_id
    assert all(e["operation"] != "RUN_CANCEL_REQUESTED" for e in desk.work.store.events(run_id))
    assert result["continuation"] is None


def test_reference_stop_remains_resumable_local_pause(desk, monkeypatch):
    context = desk.work.context(CLAIM)
    run = desk.work.start(CLAIM, idempotency_key="desk.reference.stop.check", expected_context_sha256=context["context_sha256"], dispatch=False)
    monkeypatch.setattr(desk.work, "cancel", lambda *args: pytest.fail("reference stop must retain its resumable checkpoint"))
    result = desk.control(CLAIM, **control_body(desk, "pause"), idempotency_key="desk.reference.pause.once")
    assert result["agent"]["run"]["status"] == "interrupted"
    assert result["agent"]["run"]["run_id"] == run["summary"]["run_id"]
    assert any(e["operation"] == "RUN_PAUSE_REQUESTED" for e in desk.work.store.events(run["summary"]["run_id"]))


@pytest.mark.parametrize("completed_provider", [False, True])
def test_known_external_terminal_pause_clears_without_any_new_execution(desk, monkeypatch, completed_provider):
    run_id = external_run(desk, "running" if completed_provider else "queued")
    if completed_provider:
        complete(desk.work.store, run_id)
        desk.work.store.finish(run_id, "owner", "completed", "Synthetic response and usage recorded")
    stopped = desk.control(CLAIM, **control_body(desk, "pause"), idempotency_key="desk.external.pause.before.clear")
    assert stopped["agent"]["can_clear_external_pause"] is True
    work_before = desk.work.store.snapshot(run_id)
    claim_before = desk.workspace.store.recover(CLAIM)
    def no_execution(*args, **kwargs):
        pytest.fail("Clearing the external mandate cannot execute, retry, or start reference work")
    monkeypatch.setattr(desk, "_continue", no_execution)
    monkeypatch.setattr(desk.work, "start", no_execution)
    monkeypatch.setattr(desk.work, "resume", no_execution)
    body = control_body(desk, "resume")
    resumed = desk.control(CLAIM, **body, idempotency_key="desk.external.clear.only")
    assert resumed["agent"]["pause_requested"] is False and resumed["continuation"] is None
    assert resumed["agent"]["can_clear_external_pause"] is False
    assert desk.work.store.snapshot(run_id) == work_before
    assert desk.workspace.store.recover(CLAIM) == claim_before
    repeated = desk.control(CLAIM, **body, idempotency_key="desk.external.clear.only")
    assert repeated["replayed"] and repeated["event_sha256"] == resumed["event_sha256"]
    assert desk.work.store.snapshot(run_id) == work_before and len(desk.work.store.list_runs(CLAIM)) == 1


def test_unknown_external_stop_outcome_cannot_clear_mandate_or_create_a_retry(desk):
    run_id = external_run(desk, "interrupted")
    desk.control(CLAIM, **control_body(desk, "pause"), idempotency_key="desk.external.unknown.stop")
    before = desk.delegate.state(CLAIM)
    assert desk.claim(CLAIM)["can_clear_external_pause"] is False
    with pytest.raises(ValueError, match="before clearing its pause"):
        desk.control(CLAIM, **control_body(desk, "resume"), idempotency_key="desk.external.unknown.resume")
    assert desk.delegate.state(CLAIM) == before
    assert len(desk.work.store.pending_calls(run_id)) == 1
    assert len(desk.work.store.list_runs(CLAIM)) == 1


def test_external_pause_clearability_requires_known_cost_and_a_finished_local_job():
    service = object.__new__(AgentDeskServiceV1)
    service.work = SimpleNamespace(_jobs={})
    summary = {"run_id": "work.example", "facts_worker": "external_facts", "status": "completed",
               "pending_calls": [], "provider_requests": 1, "provider_cost_usd": 0.001}
    assert service._external_pause_clearable(summary)
    for changes in [{"provider_cost_usd": None}, {"provider_cost_usd": -1}, {"provider_cost_usd": float("nan")},
                    {"provider_cost_usd": True}, {"provider_requests": True}, {"provider_requests": -1},
                    {"pending_calls": ["unconfirmed"]}, {"status": "running"}, {"status": "interrupted"},
                    {"facts_worker": "reference"}]:
        assert not service._external_pause_clearable({**summary, **changes})
    service.work._jobs[summary["run_id"]] = SimpleNamespace(done=lambda: False)
    assert not service._external_pause_clearable(summary)
    service.work._jobs[summary["run_id"]] = SimpleNamespace(done=lambda: True)
    assert service._external_pause_clearable(summary)
