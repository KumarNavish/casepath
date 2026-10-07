from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from casepath_api.agent_desk_v1 import AgentDeskServiceV1, _fingerprint_row, create_agent_desk_router
from casepath_api.agent_work.authority import ExistingCasePathAuthority
from casepath_api.agent_work.service import AgentWorkService
from casepath_api.agent_work.runtime import AgentWorkExecutor
from casepath_api.agent_work.store import WorkStore
from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root
from casepath_api.workspace_corpus import digest_value
from casepath_api.claim_loop_router import create_claim_loop_router
from test_workspace_claim_loop_v1 import _system

CLAIM = "clm_f69b1747447bc221"


@pytest.fixture
def desk(tmp_path):
    storage, workspace, _, facade = _system(tmp_path, corpus=PublicCorpus(default_workspace_corpus_root()))
    workspace.seed()
    work = AgentWorkService(WorkStore(tmp_path / "work.sqlite3"), ExistingCasePathAuthority(lambda: workspace, lambda: facade))
    service = AgentDeskServiceV1(workspace, work)
    yield service
    work.shutdown()


def control_body(service, action):
    agent = service.claim(CLAIM)
    return {"action": action, "actor": "Test handler", "reason": "Inspect this claim before continuing.",
            "expected_revision": agent["workspace_revision"], "expected_state_sha256": agent["workspace_state_sha256"],
            "expected_agent_revision": agent["agent_revision"], "expected_agent_state_sha256": agent["agent_state_sha256"]}


def test_desk_reads_are_side_effect_free_and_unknown_is_not_completed(desk):
    before = desk.workspace.states()
    value = desk.desk()
    assert value["total"] == 150
    assert sum(group["count"] for group in value["groups"]) == 150
    assert value["unstarted_count"] == 150
    assert all(row["review_started"] is False for group in value["groups"] for row in group["claims"])
    assert desk.workspace.states() == before
    assert desk.work.store.list_runs() == []
    assert value["counts"]["closed"] == 0
    assert value["counts"]["quiet"] == 150
    assert all(row["agent_state"] == "unknown" for group in value["groups"] for row in group["claims"])


@pytest.mark.parametrize("status", ["interrupted", "unconfirmed_safe", "unconfirmed_pending"])
def test_interrupted_and_unconfirmed_work_needs_handler_recovery_without_blind_retry(desk, status):
    context = desk.work.context(CLAIM)
    started = desk.work.start(CLAIM, idempotency_key="desk.recovery." + status,
        expected_context_sha256=context["context_sha256"], dispatch=False)
    run_id = started["summary"]["run_id"]
    assert desk.work.store.acquire(run_id, "vanished-owner")
    if status == "interrupted":
        desk.work.store.finish(run_id, "vanished-owner", "interrupted", "Executor stopped at its saved checkpoint")
    else:
        if status == "unconfirmed_pending":
            desk.work.store.begin_call(run_id, "vanished-owner", "source_integrity", "unfinished-read", "source.open", {"source_id": "pending-source"})
        # Expire only this isolated executor lease, preserving real pending
        # call receipts and journal history for the recovery projection.
        with desk.work.store.connect() as db:
            db.execute("UPDATE work_runs SET lease_until=0 WHERE run_id=?", (run_id,))
    agent = desk.claim(CLAIM)
    assert agent["questions"] == [] and agent["pause_requested"] is False
    assert agent["state"] == "unknown" and agent["recovery_required"] is True
    assert agent["run"]["status"] == ("interrupted" if status == "interrupted" else "unconfirmed")
    value = desk.desk()
    row = next(row for group in value["groups"] for row in group["claims"] if row["claim_id"] == CLAIM)
    assert row["group"] == "needs_you" and row["review_started"] is True
    assert row["recovery_required"] is True and row["ask"] == agent["recovery_ask"]
    assert value["counts"]["quiet"] == value["unstarted_count"] == 149
    if status == "unconfirmed_pending":
        assert agent["run"]["recovery"] == {"can_resume": False, "reason": "pending_operation"}
        assert "reconcile" in row["ask"].lower() and "resume" not in row["ask"].lower()
    else:
        assert agent["run"]["recovery"]["can_resume"] is True
        assert "saved checkpoint" in row["ask"].lower()
    assert desk.work.store.get_run(run_id)["status"] == ("interrupted" if status == "interrupted" else "running")


def test_pause_idempotency_stale_revision_and_restart(desk):
    body = control_body(desk, "pause")
    paused = desk.control(CLAIM, **body, idempotency_key="desk.pause.first.0001")
    assert paused["agent"]["state"] == "paused"
    assert desk.control(CLAIM, **body, idempotency_key="desk.pause.first.0001")["event_sha256"] == paused["event_sha256"]
    with pytest.raises(ValueError, match="idempotency"):
        desk.control(CLAIM, **{**body, "reason": "Different request."}, idempotency_key="desk.pause.first.0001")
    with pytest.raises(ValueError, match="stale"):
        desk.control(CLAIM, **body, idempotency_key="desk.pause.stale.0001")
    restarted = AgentDeskServiceV1(desk.workspace, desk.work)
    assert restarted.claim(CLAIM)["state"] == "paused"
    restarted.start(limit=1)
    assert desk.work.store.list_runs(CLAIM) == []


def test_decision_preview_override_reason_and_exact_replay(desk):
    state = desk.workspace.store.recover(CLAIM)
    desk.workspace.start(CLAIM, expected_revision=state["revision"], idempotency_key="desk.setup.start.0001")
    agent = desk.claim(CLAIM)
    question = next(q for q in agent["questions"] if q["question_id"] == "condition:family_home")
    assert question["prompt"] == "Is this a family home?"
    assert question["sources"][0]["quote"]
    body = {"question_id": question["question_id"], "answer_id": "false", "actor": "Test handler", "reason": "The shared home is not established by this report.",
            "expected_revision": agent["workspace_revision"], "expected_state_sha256": agent["workspace_state_sha256"]}
    with pytest.raises(ValueError, match="reason"):
        desk.preview_decision(CLAIM, **{**body, "reason": ""})
    preview = desk.preview_decision(CLAIM, **body)
    assert preview["contract"] == "casepath.agent-decision-preview/1.0.0"
    assert preview["causal"]["contract"] == "casepath.causal-process-preview/1.0.0"
    assert preview["response_sha256"] == digest_value({k: v for k, v in preview.items() if k != "response_sha256"})
    assert preview["preview_sha256"] == digest_value({k: v for k, v in preview.items() if k not in {"response_sha256", "preview_sha256"}})
    assert preview["impact"]["changed_document_types"]
    args = {**body, "preview_sha256": preview["preview_sha256"], "idempotency_key": "desk.decision.apply.0001"}
    with pytest.raises(ValueError, match="preview differs"):
        desk.apply_decision(CLAIM, **{**args, "preview_sha256": preview["causal"]["preview_sha256"]}, dispatch=False)
    accepted = desk.apply_decision(CLAIM, **args, dispatch=False)
    assert accepted["process"]["claim_decision_authorized"] is False
    assert accepted["process"]["workspace_state_sha256"] == accepted["agent"]["workspace_state_sha256"]
    repeated = desk.apply_decision(CLAIM, **args, dispatch=False)
    assert repeated["event_sha256"] == accepted["event_sha256"]
    assert repeated["replayed"] is True
    assert AgentDeskServiceV1(desk.workspace, desk.work).claim(CLAIM)["workspace_state_sha256"] == accepted["agent"]["workspace_state_sha256"]


def test_routes_reject_invented_authority_and_require_idempotency(desk):
    app = FastAPI()
    app.include_router(create_agent_desk_router(lambda: desk))
    client = TestClient(app)
    path = f"/api/claim-loops/v1/workspace/claims/{CLAIM}/agent/control"
    body = control_body(desk, "pause")
    assert client.post(path, json={**body, "claim_ready": True}, headers={"X-CasePath-Idempotency-Key": "desk.http.invalid.0001"}).status_code == 422
    assert client.post(path, json=body).status_code == 400
    assert client.get("/api/claim-loops/v1/workspace/desk").status_code == 200


def test_reference_pause_then_resume_preserves_the_run_and_completed_calls(desk):
    context = desk.work.context(CLAIM)
    started = desk.work.start(CLAIM, idempotency_key="desk.work.pause.0001", expected_context_sha256=context["context_sha256"], dispatch=False)
    run_id = started["summary"]["run_id"]
    desk.work.pause(CLAIM, run_id)
    assert desk.work.run(CLAIM, run_id)["summary"]["status"] == "interrupted"
    assert desk.work.store.acquire(run_id, "test-owner") is False
    resumed = desk.work.resume(CLAIM, run_id)
    assert resumed["summary"]["run_id"] == run_id
    desk.work.shutdown()
    assert desk.work.store.get_run(run_id)["status"] == "completed"
    assert len(desk.work.store.list_runs(CLAIM)) == 1
    assert desk.work.store.pending_calls(run_id) == []


def test_active_reference_pause_persists_checkpoint_and_resumes_real_source_work(desk, monkeypatch):
    context = desk.work.context(CLAIM)
    started = desk.work.start(CLAIM, idempotency_key="desk.work.active-pause.0001",
        expected_context_sha256=context["context_sha256"], dispatch=False)
    run_id = started["summary"]["run_id"]
    store = desk.work.store
    complete_call = store.complete_call
    paused = False

    def pause_after_real_source(call_run, owner, role, call_id, result, events, objects=()):
        nonlocal paused
        response = complete_call(call_run, owner, role, call_id, result, events, objects)
        if not paused and any(o["kind"] == "opened_source" for o in objects):
            paused = True
            # The real source operation has already committed. The next tool
            # checkpoint observes this request through the actual executor.
            store.request_pause(run_id)
        return response

    monkeypatch.setattr(store, "complete_call", pause_after_real_source)
    result = AgentWorkExecutor(store, desk.work.authority).execute(run_id)
    assert paused
    assert result["status"] == "interrupted"
    assert result["owner"] is None and result["lease_until"] is None
    snapshot = store.snapshot(run_id)
    assert snapshot["events"][-1]["operation"] == "RUN_INTERRUPTED"
    assert snapshot["events"][-1]["status"] == "unknown"
    assert any(o["kind"] == "opened_source" for o in snapshot["objects"])
    assert store.pending_calls(run_id) == []
    with store.connect() as db:
        saved_calls = [dict(row) for row in db.execute("SELECT * FROM work_calls WHERE run_id=? ORDER BY role,call_id", (run_id,))]
    assert saved_calls and all(call["status"] == "completed" for call in saved_calls)

    monkeypatch.undo()
    reopened = WorkStore(store.path)
    assert reopened.snapshot(run_id)["run"]["status"] == "interrupted"
    assert AgentWorkService.recovery(reopened.snapshot(run_id))["can_resume"] is True
    assert reopened.acquire(run_id, "other-owner") is False
    desk.work.resume(CLAIM, run_id)
    desk.work.shutdown()
    assert reopened.snapshot(run_id)["run"]["status"] == "completed"
    assert len(reopened.list_runs(CLAIM)) == 1
    with reopened.connect() as db:
        for original in saved_calls:
            current = dict(db.execute("SELECT * FROM work_calls WHERE run_id=? AND role=? AND call_id=?",
                (run_id, original["role"], original["call_id"])).fetchone())
            assert current == original
    assert reopened.pending_calls(run_id) == []


def test_resume_recovers_an_expired_running_executor_through_existing_service(desk):
    context = desk.work.context(CLAIM)
    started = desk.work.start(CLAIM, idempotency_key="desk.work.vanished.0001",
        expected_context_sha256=context["context_sha256"], dispatch=False)
    run_id = started["summary"]["run_id"]
    assert desk.work.store.acquire(run_id, "vanished-executor", lease_seconds=-1)
    assert desk.work.store.get_run(run_id)["status"] == "running"
    desk.control(CLAIM, **control_body(desk, "pause"), idempotency_key="desk.vanished.pause.0001")
    accepted = desk.control(CLAIM, **control_body(desk, "resume"), idempotency_key="desk.vanished.resume.0001")
    assert accepted["continuation"]["run"]["run_id"] == run_id
    desk.work.shutdown()
    assert desk.work.store.get_run(run_id)["status"] == "completed"
    assert any(event["operation"] == "RUN_INTERRUPTED" for event in desk.work.store.events(run_id))
    assert len(desk.work.store.list_runs(CLAIM)) == 1


def test_scalar_fingerprint_binds_values_types_lengths_and_column_names():
    from hashlib import sha256
    def fingerprint(row):
        signature = sha256()
        _fingerprint_row(signature, row)
        return signature.digest()
    original = {"run_id": "abc", "result_json": '{"body":"line1\\nline2"}', "lease_until": 1.25, "count": 1, "owner": None}
    baseline = fingerprint(original)
    for key, value in original.items():
        replacement = "changed" if value is None else str(value) + "changed"
        assert fingerprint({**original, key: replacement}) != baseline
    assert fingerprint({"x": 1}) != fingerprint({"x": "1"})
    assert fingerprint({"x": "ab", "y": "c"}) != fingerprint({"x": "a", "y": "bc"})
    assert fingerprint({"different": "abc"}) != fingerprint({"run_id": "abc"})


def test_desk_fingerprints_work_tables_in_one_snapshot_during_run_creation(desk, monkeypatch):
    context = desk.work.context(CLAIM)
    desk.work.start(CLAIM, idempotency_key="desk.snapshot.first", expected_context_sha256=context["context_sha256"], dispatch=False)
    other = next(state["claim_id"] for state in desk.workspace.states() if state["claim_id"] != CLAIM)
    other_context = desk.work.context(other)
    import casepath_api.agent_desk_v1 as module
    fingerprint = module._fingerprint_row
    inserted = False
    def create_during_scan(signature, row):
        nonlocal inserted
        fingerprint(signature, row)
        if not inserted and "request_json" in row.keys():
            inserted = True
            desk.work.start(other, idempotency_key="desk.snapshot.concurrent", expected_context_sha256=other_context["context_sha256"], dispatch=False)
    monkeypatch.setattr(module, "_fingerprint_row", create_during_scan)
    first = desk.desk()
    assert inserted and first["total"] == 150
    assert first["unstarted_count"] == 149
    second = desk.desk()
    assert second["unstarted_count"] == 148
    assert {row["claim_id"] for group in second["groups"] for row in group["claims"] if row["review_started"]} == {CLAIM, other}


def test_exact_arrival_replay_uses_one_verified_batch_without_full_work_views(desk, monkeypatch):
    first = desk.start(limit=2, idempotency_key="desk.arrival.batch.0001")
    def full_view_forbidden(*args, **kwargs):
        raise AssertionError("an exact arrival replay rebuilt a full authority view")
    monkeypatch.setattr(desk.work, "run", full_view_forbidden)
    repeated = desk.start(limit=2, idempotency_key="desk.arrival.batch.0001")
    assert repeated["replayed"] is True and repeated["provider_calls"] == 0
    assert [item["run"]["run_id"] for item in repeated["results"]] == [item["run"]["run_id"] for item in first["results"]]
    assert all(item["started"] is False for item in repeated["results"])
    assert repeated["projection_sha256"] == digest_value({k: v for k, v in repeated.items() if k != "projection_sha256"})


@pytest.mark.parametrize("paused_at_finish", [False, True])
def test_rapid_process_edits_cancel_at_checkpoint_then_review_only_latest_context(desk, monkeypatch, paused_at_finish):
    from threading import Event
    import time
    entered, release = Event(), Event()
    complete_call = desk.work.store.complete_call
    held = False
    def hold_after_committed_read(run_id, owner, role, call_id, result, events, objects=()):
        nonlocal held
        value = complete_call(run_id, owner, role, call_id, result, events, objects)
        if not held and any(obj["kind"] == "opened_source" for obj in objects):
            held = True
            entered.set()
            assert release.wait(30), "the isolated source checkpoint was not released"
        return value
    monkeypatch.setattr(desk.work.store, "complete_call", hold_after_committed_read)
    state = desk.workspace.store.recover(CLAIM)
    desk.workspace.start(CLAIM, expected_revision=state["revision"], idempotency_key="desk.rapid.setup",
        process_model="casepath.causal-process/1.0.0")
    def accept(flag):
        state = desk.workspace.store.recover(CLAIM)
        body = {"operation": {"type": "conditions.set", "flag": flag, "verdict": "false"}, "actor": "Test handler",
            "reason": "This condition is not established by the admitted sources.", "expected_revision": state["revision"], "expected_state_sha256": state["state_sha256"]}
        preview = desk.process.preview(CLAIM, **body)
        receipt = desk.process.apply(CLAIM, **body, preview_sha256=preview["preview_sha256"], idempotency_key="desk.rapid.edit." + flag)
        return receipt, desk.process_accepted(CLAIM, receipt)
    try:
        first_receipt, first = accept("family_home")
        old_id = first["run"]["run_id"]
        assert entered.wait(30)
        second_receipt, second = accept("arrears")
        latest_receipt, latest = accept("extension_relevant")
        assert second["reason"] == latest["reason"] == "latest_process_review_queued"
        assert len(desk.work.store.list_runs(CLAIM)) == 1
        if paused_at_finish:
            desk.control(CLAIM, **control_body(desk, "pause"), idempotency_key="desk.rapid.pause")
        release.set()
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            runs = desk.work.store.list_runs(CLAIM)
            if paused_at_finish and runs[0]["status"] == "cancelled":
                break
            if not paused_at_finish and len(runs) == 2 and runs[0]["status"] == "completed":
                break
            time.sleep(0.05)
        else:
            raise AssertionError("latest accepted process continuation did not reach its real terminal checkpoint")
        old = desk.work.store.snapshot(old_id)
        assert old["run"]["status"] == "cancelled" and old["pending_calls"] == []
        assert any(event["operation"] == "RUN_CANCEL_REQUESTED" and event["after"]["accepted_process_event_sha256"] == second_receipt["event_sha256"] for event in old["events"])
        if paused_at_finish:
            assert len(runs) == 1 and desk.delegate.state(CLAIM)["paused"] is True
            assert desk.process_accepted(CLAIM, latest_receipt)["reason"] == "paused_by_handler"
        else:
            assert len(runs) == 2 and runs[0]["idempotency_key"] == "desk.continue." + latest_receipt["event_sha256"]
            current = desk.work.store.snapshot(runs[0]["run_id"])
            assert current["pending_calls"] == []
            assert sum(event["operation"] == "AGENT_COMPLETED" for event in current["events"]) == 6
            assert not any(event["operation"] == "PROVIDER_REQUEST_STARTED" for event in current["events"])
            assert current["events"][0]["timestamp"] >= old["events"][-1]["timestamp"]
            assert desk.claim(CLAIM)["run"]["currentness"] == "current"
            desk.process_accepted(CLAIM, second_receipt)
            desk.process_accepted(CLAIM, latest_receipt)
            assert len(desk.work.store.list_runs(CLAIM)) == 2
    finally:
        release.set()


def test_queued_supersession_survives_restart_gap_and_exact_latest_retry(desk, monkeypatch):
    state = desk.workspace.store.recover(CLAIM)
    desk.workspace.start(CLAIM, expected_revision=state["revision"], idempotency_key="desk.restart.setup",
        process_model="casepath.causal-process/1.0.0")
    def accept(flag):
        state = desk.workspace.store.recover(CLAIM)
        body = {"operation": {"type": "conditions.set", "flag": flag, "verdict": "false"}, "actor": "Test handler",
            "reason": "This condition is not established by the admitted sources.", "expected_revision": state["revision"], "expected_state_sha256": state["state_sha256"]}
        preview = desk.process.preview(CLAIM, **body)
        return desk.process.apply(CLAIM, **body, preview_sha256=preview["preview_sha256"], idempotency_key="desk.restart.edit." + flag)
    first = accept("family_home")
    old = desk.process_accepted(CLAIM, first, dispatch=False)["run"]["run_id"]
    latest = accept("arrears")
    def exit_before_submission(*args, **kwargs):
        raise RuntimeError("simulated process exit after durable cancellation")
    monkeypatch.setattr(desk.work, "start", exit_before_submission)
    with pytest.raises(RuntimeError, match="durable cancellation"):
        desk.process_accepted(CLAIM, latest, dispatch=False)
    saved = desk.work.store.snapshot(old)
    assert saved["run"]["status"] == "cancelled" and saved["pending_calls"] == []
    desk.work.shutdown()
    work = AgentWorkService(WorkStore(desk.work.store.path), desk.work.authority)
    recovered = AgentDeskServiceV1(desk.workspace, work)
    try:
        assert len(work.store.list_runs(CLAIM)) == 1  # Reopening performs no writes.
        resumed = recovered.process_accepted(CLAIM, latest, dispatch=False)
        assert resumed["started"] is True
        current = work.store.get_run(resumed["run"]["run_id"])
        assert current["request"]["context"]["revision"] >= latest["process"]["workspace_revision"]
        assert current["idempotency_key"] == "desk.continue." + latest["event_sha256"]
        assert recovered.process_accepted(CLAIM, latest, dispatch=False)["started"] is False
        assert recovered.process_accepted(CLAIM, first, dispatch=False)["reason"] == "superseded_process_edit"
        assert len(work.store.list_runs(CLAIM)) == 2
        assert work.store.snapshot(old) == saved
    finally:
        work.shutdown()


def test_supersession_reconciles_finish_between_snapshot_and_cancel(desk, monkeypatch):
    state = desk.workspace.store.recover(CLAIM)
    desk.workspace.start(CLAIM, expected_revision=state["revision"], idempotency_key="desk.finish-race.setup",
        process_model="casepath.causal-process/1.0.0")
    context = desk.work.context(CLAIM)
    old = desk.work.start(CLAIM, idempotency_key="desk.finish-race.old", expected_context_sha256=context["context_sha256"], dispatch=False)["summary"]["run_id"]
    assert desk.work.store.acquire(old, "isolated-finish-owner")
    state = desk.workspace.store.recover(CLAIM)
    body = {"operation": {"type": "conditions.set", "flag": "family_home", "verdict": "false"}, "actor": "Test handler",
        "reason": "Review the admitted evidence.", "expected_revision": state["revision"], "expected_state_sha256": state["state_sha256"]}
    preview = desk.process.preview(CLAIM, **body)
    receipt = desk.process.apply(CLAIM, **body, preview_sha256=preview["preview_sha256"], idempotency_key="desk.finish-race.edit")
    cancel = desk.work.store.request_cancel
    def finish_before_cancel(run_id, **kwargs):
        desk.work.store.finish(run_id, "isolated-finish-owner", "blocked", "The earlier claim context no longer supports this review")
        return cancel(run_id, **kwargs)
    monkeypatch.setattr(desk.work.store, "request_cancel", finish_before_cancel)
    result = desk.process_accepted(CLAIM, receipt, dispatch=False)
    assert result["started"] is True
    runs = desk.work.store.list_runs(CLAIM)
    assert len(runs) == 2 and runs[0]["idempotency_key"] == "desk.continue." + receipt["event_sha256"]
    saved = desk.work.store.snapshot(old)
    assert saved["run"]["status"] == "blocked" and saved["pending_calls"] == []
    assert saved["events"][-1]["operation"] == "RUN_BLOCKED"
    assert not any(event["operation"] == "RUN_CANCEL_REQUESTED" for event in saved["events"])
    assert desk.process_accepted(CLAIM, receipt, dispatch=False)["started"] is False
    assert len(desk.work.store.list_runs(CLAIM)) == 2


def test_continuation_and_terminal_callback_do_not_retry_unfinished_effect(desk):
    state = desk.workspace.store.recover(CLAIM)
    desk.workspace.start(CLAIM, expected_revision=state["revision"], idempotency_key="desk.pending.setup",
        process_model="casepath.causal-process/1.0.0")
    context = desk.work.context(CLAIM)
    run = desk.work.start(CLAIM, idempotency_key="desk.pending.old", expected_context_sha256=context["context_sha256"], dispatch=False)["summary"]["run_id"]
    assert desk.work.store.acquire(run, "isolated-pending-owner")
    desk.work.store.begin_call(run, "isolated-pending-owner", "source_integrity", "unfinished-read", "source.open", {"source_id": "pending-source"})
    desk.work.store.finish(run, "isolated-pending-owner", "blocked", "An operation needs outcome reconciliation")
    state = desk.workspace.store.recover(CLAIM)
    body = {"operation": {"type": "conditions.set", "flag": "family_home", "verdict": "false"}, "actor": "Test handler",
        "reason": "Review the admitted evidence.", "expected_revision": state["revision"], "expected_state_sha256": state["state_sha256"]}
    preview = desk.process.preview(CLAIM, **body)
    receipt = desk.process.apply(CLAIM, **body, preview_sha256=preview["preview_sha256"], idempotency_key="desk.pending.edit")
    assert desk.process_accepted(CLAIM, receipt, dispatch=False)["reason"] == "recorded_operation_requires_reconciliation"
    before = desk.work.store.snapshot(run)
    desk._reference_finished(CLAIM, run)
    assert desk.work.store.snapshot(run) == before
    assert len(desk.work.store.list_runs(CLAIM)) == 1


@pytest.mark.parametrize("surface", ["process", "documents"])
def test_direct_causal_apply_hook_prepares_current_draft_and_is_exactly_replayable(desk, surface):
    state = desk.workspace.store.recover(CLAIM)
    desk.workspace.start(CLAIM, expected_revision=state["revision"], idempotency_key="desk.direct.setup." + surface,
        process_model="casepath.causal-process/1.0.0")
    state = desk.workspace.store.recover(CLAIM)
    parent = {"actor": "Test handler", "reason": "Review this bounded process requirement.",
              "expected_revision": state["revision"], "expected_state_sha256": state["state_sha256"]}
    if surface == "process":
        body = {**parent, "operation": {"type": "node.update", "node_id": "lt_deadline",
            "changes": {"document_types": ["proof_of_receipt", "notice_period_evidence", "lease_contract"]}}}
        suffix = "/process"
    else:
        source = next(item for item in desk.workspace.detail(CLAIM)["artifacts"]
            if "tenant" in item["file_name"].lower() and item["media_type"] == "application/pdf")
        body = {**parent, "document_type": "termination_notice", "artifact_id": source["artifact_id"],
                "quote": "30. Juni", "note": "The end date is readable; this does not establish a complete copy.", "review": "insufficient"}
        suffix = "/process/documents"
    app = FastAPI()
    app.include_router(create_claim_loop_router(lambda: desk.workspace.storage, workspace_service_getter=lambda: desk.workspace,
        accepted_process_hook=lambda claim_id, result: desk.process_accepted(claim_id, result, dispatch=False)))
    client = TestClient(app)
    route = f"/api/claim-loops/v1/workspace/claims/{CLAIM}" + suffix
    preview = client.post(route + "/preview", json=body)
    assert preview.status_code == 200, preview.text
    assert desk.workspace.store.recover(CLAIM) == state
    assert desk.workspace.drafts(CLAIM)["latest"] is None and desk.work.store.list_runs(CLAIM) == []
    request = {**body, "preview_sha256": preview.json()["preview_sha256"]}
    header = {"X-CasePath-Idempotency-Key": "desk.direct.apply." + surface}
    response = client.post(route + "/apply", json=request, headers=header)
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert receipt["contract"] == "casepath.causal-process-result/1.0.0"
    assert receipt["result_sha256"] == digest_value({k: v for k, v in receipt.items() if k != "result_sha256"})
    assert "agent" not in receipt and "continuation" not in receipt
    current = desk.workspace.store.recover(CLAIM)
    draft = desk.workspace.drafts(CLAIM)["latest"]
    assert draft and draft["status"] == "draft_not_sent"
    assert current["revision"] > receipt["process"]["workspace_revision"]
    if surface == "process":
        assert "lease_contract" in {item["document_type"] for item in draft["requested"]}
    runs = desk.work.store.list_runs(CLAIM)
    assert len(runs) == 1 and runs[0]["request"]["facts_worker"] == "reference"
    repeated = client.post(route + "/apply", json=request, headers=header)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["replayed"] is True
    assert repeated.json()["event_sha256"] == receipt["event_sha256"]
    assert repeated.json()["process"] == receipt["process"]
    assert desk.workspace.store.recover(CLAIM) == current
    assert len(desk.workspace.drafts(CLAIM)["items"]) == 1
    assert len(desk.work.store.list_runs(CLAIM)) == 1
    if surface == "process":
        desk.work.resume(CLAIM, runs[0]["run_id"])
        desk.work.shutdown()
        assert desk.work.run(CLAIM, runs[0]["run_id"])["summary"]["currentness"] == "current"
        assert desk.work.store.get_run(runs[0]["run_id"])["status"] == "completed"
        assert "lease_contract" in {item["document_type"] for item in desk.workspace.drafts(CLAIM)["latest"]["requested"]}


def test_accepted_process_hook_cannot_revive_superseded_edit_or_saved_pause(desk):
    state = desk.workspace.store.recover(CLAIM)
    desk.workspace.start(CLAIM, expected_revision=state["revision"], idempotency_key="desk.direct.superseded.setup",
        process_model="casepath.causal-process/1.0.0")
    results = []
    for index, flag in enumerate(("family_home", "arrears")):
        state = desk.workspace.store.recover(CLAIM)
        body = {"operation": {"type": "conditions.set", "flag": flag, "verdict": "false"}, "actor": "Test handler",
                "reason": "The admitted sources do not establish this condition.", "expected_revision": state["revision"], "expected_state_sha256": state["state_sha256"]}
        preview = desk.process.preview(CLAIM, **body)
        results.append(desk.process.apply(CLAIM, **body, preview_sha256=preview["preview_sha256"], idempotency_key="desk.direct.superseded." + str(index)))
    assert desk.process_accepted(CLAIM, results[0], dispatch=False)["reason"] == "superseded_process_edit"
    assert desk.workspace.drafts(CLAIM)["latest"] is None and desk.work.store.list_runs(CLAIM) == []
    desk.control(CLAIM, **control_body(desk, "pause"), idempotency_key="desk.direct.pause.current")
    assert desk.process_accepted(CLAIM, results[1], dispatch=False)["reason"] == "paused_by_handler"
    assert desk.workspace.drafts(CLAIM)["latest"] is None and desk.work.store.list_runs(CLAIM) == []


def test_process_hook_rechecks_latest_edit_after_draft_preparation(desk, monkeypatch):
    state = desk.workspace.store.recover(CLAIM)
    desk.workspace.start(CLAIM, expected_revision=state["revision"], idempotency_key="desk.direct.concurrent.setup",
        process_model="casepath.causal-process/1.0.0")
    def accept(flag, key):
        state = desk.workspace.store.recover(CLAIM)
        body = {"operation": {"type": "conditions.set", "flag": flag, "verdict": "false"}, "actor": "Test handler",
                "reason": "The source does not establish this condition.", "expected_revision": state["revision"], "expected_state_sha256": state["state_sha256"]}
        preview = desk.process.preview(CLAIM, **body)
        return desk.process.apply(CLAIM, **body, preview_sha256=preview["preview_sha256"], idempotency_key=key)
    first = accept("family_home", "desk.direct.concurrent.first")
    prepare = desk._prepare_draft
    def prepare_then_accept_another(claim_id, run_id=None):
        prepare(claim_id, run_id)
        accept("arrears", "desk.direct.concurrent.second")
    monkeypatch.setattr(desk, "_prepare_draft", prepare_then_accept_another)
    result = desk.process_accepted(CLAIM, first, dispatch=False)
    assert result["reason"] == "superseded_process_edit"
    assert desk.work.store.list_runs(CLAIM) == []
    assert desk.workspace.drafts(CLAIM)["latest"] is None


@pytest.mark.parametrize("drift", ["manual_draft", "process", "owner"])
def test_desk_equivalence_allows_only_verified_automatic_draft_suffix(desk, drift):
    desk.start(limit=1, idempotency_key="desk.equivalence.start." + drift)
    desk.work.shutdown()
    run = desk.work.store.list_runs(CLAIM)[0]
    assert run["status"] == "completed"
    assert desk.work.run(CLAIM, run["run_id"])["summary"]["currentness"] == "historical"
    summary = desk.claim(CLAIM)["run"]
    assert summary["currentness"] == "current"
    assert summary["currentness_scope"] == "reviewed_sources_and_process"
    assert summary["authority_snapshot_currentness"] == "historical"
    state = desk.workspace.store.recover(CLAIM)
    if drift == "manual_draft":
        draft = desk.workspace.drafts(CLAIM)["latest"]
        desk.workspace.record_draft(CLAIM, expected_revision=state["revision"], expected_state_sha256=state["state_sha256"],
            idempotency_key="desk.equivalence.handler-draft", replaces_event_sha256=draft["event_sha256"],
            edited_body=draft["body_markdown"] + "\nPlease call me to discuss these copies.")
    elif drift == "owner":
        desk.workspace.assign(CLAIM, owner="Another accountable handler", expected_revision=state["revision"], idempotency_key="desk.equivalence.owner")
    else:
        body = {"operation": {"type": "conditions.set", "flag": "family_home", "verdict": "false"}, "actor": "Test handler",
            "reason": "The report does not establish a family home.", "expected_revision": state["revision"], "expected_state_sha256": state["state_sha256"]}
        preview = desk.process.preview(CLAIM, **body)
        desk.process.apply(CLAIM, **body, preview_sha256=preview["preview_sha256"], idempotency_key="desk.equivalence.process")
    after = desk.claim(CLAIM)["run"]
    assert after["currentness"] == "historical" and after["authority_snapshot_currentness"] == "historical"
    assert after["currentness_scope"] == "authority_state"
    with desk.workspace.store.journal.connect() as db:
        db.execute("UPDATE claim_loop_events SET event_sha256=? WHERE session_id=? AND loop_id=? AND sequence=4",
            ("f" * 64, "casepath-workspace-local", "workspace." + CLAIM))
    with pytest.raises(ValueError, match="chain"):
        desk.claim(CLAIM)


def test_conflict_decision_exact_retry_retains_unknown_truth_and_citations(desk):
    state = desk.workspace.store.recover(CLAIM)
    desk.workspace.start(CLAIM, expected_revision=state["revision"], idempotency_key="desk.conflict.setup.0001")
    agent = desk.claim(CLAIM)
    question = next(q for q in agent["questions"] if q["kind"] == "source_conflict")
    assert question["prompt"] == "How should we handle the conflicting termination dates?"
    assert len(question["sources"]) == 2
    body = {"question_id": question["question_id"], "answer_id": "keep_open", "actor": "Test handler", "reason": "",
            "expected_revision": agent["workspace_revision"], "expected_state_sha256": agent["workspace_state_sha256"]}
    preview = desk.preview_decision(CLAIM, **body)
    args = {**body, "preview_sha256": preview["preview_sha256"], "idempotency_key": "desk.conflict.accept.0001"}
    accepted = desk.apply_decision(CLAIM, **args, dispatch=False)
    assert question["question_id"] not in {q["question_id"] for q in accepted["agent"]["questions"]}
    assert accepted["agent"]["conflicts"][0]["truth_status"] == "unresolved"
    assert accepted["agent"]["conflicts"][0]["sources"] == question["sources"]
    row = next(row for group in desk.desk()["groups"] for row in group["claims"] if row["claim_id"] == CLAIM)
    assert row["ask"] == accepted["agent"]["questions"][0]["prompt"]
    assert row["question_count"] == len(accepted["agent"]["questions"])
    assert desk.apply_decision(CLAIM, **args, dispatch=False)["event_sha256"] == accepted["event_sha256"]
    assert desk.workspace.store.recover(CLAIM)["deadline_at"]["date"] is None


@pytest.mark.parametrize("kind,answer", [("draft_approval", "approve"), ("source_conflict", "keep_open")])
def test_historical_delegate_retry_preserves_pause_and_cannot_revive_effects(desk, kind, answer):
    state = desk.workspace.store.recover(CLAIM)
    state = desk.workspace.start(CLAIM, expected_revision=state["revision"], idempotency_key="desk.retry.setup." + kind,
        process_model="casepath.causal-process/1.0.0")["state"]
    desk.workspace.record_draft(CLAIM, expected_revision=state["revision"], expected_state_sha256=state["state_sha256"],
        idempotency_key="desk.retry.prepare." + kind)
    desk.control(CLAIM, **control_body(desk, "pause"), idempotency_key="desk.retry.pause." + kind)
    agent = desk.claim(CLAIM)
    question = next(q for q in agent["questions"] if q["kind"] == kind)
    body = {"question_id": question["question_id"], "answer_id": answer, "actor": "Test handler", "reason": "",
        "expected_revision": agent["workspace_revision"], "expected_state_sha256": agent["workspace_state_sha256"]}
    preview = desk.preview_decision(CLAIM, **body)
    args = {**body, "preview_sha256": preview["preview_sha256"], "idempotency_key": "desk.retry.accept." + kind}
    accepted = desk.apply_decision(CLAIM, **args, dispatch=False)
    assert accepted["continuation"]["reason"] == "paused_by_handler"
    assert desk.work.store.list_runs(CLAIM) == []

    state = desk.workspace.store.recover(CLAIM)
    edit = {"operation": {"type": "conditions.set", "flag": "family_home", "verdict": "false"},
        "actor": "Test handler", "reason": "The family-home condition is not established.",
        "expected_revision": state["revision"], "expected_state_sha256": state["state_sha256"]}
    causal_preview = desk.process.preview(CLAIM, **edit)
    desk.process.apply(CLAIM, **edit, preview_sha256=causal_preview["preview_sha256"], idempotency_key="desk.retry.process." + kind)
    assert desk.workspace.drafts(CLAIM)["latest"] is None
    before = desk.workspace.store.recover(CLAIM)
    paused_retry = desk.apply_decision(CLAIM, **args, dispatch=False)
    assert paused_retry["event_sha256"] == accepted["event_sha256"] and paused_retry["replayed"] is True
    assert paused_retry["continuation"]["reason"] == "paused_by_handler"
    assert desk.workspace.store.recover(CLAIM) == before
    assert desk.workspace.drafts(CLAIM)["latest"] is None and desk.work.store.list_runs(CLAIM) == []

    # Persist a genuine resumed mandate without dispatch, as if the server
    # stopped between the accepted control event and its work submission.
    command = control_body(desk, "resume")
    command.pop("action")
    desk.delegate.append(CLAIM, "AGENT_MANDATE_RESUMED", command, "desk.retry.resume." + kind)
    resumed_retry = desk.apply_decision(CLAIM, **args, dispatch=False)
    assert resumed_retry["event_sha256"] == accepted["event_sha256"] and resumed_retry["replayed"] is True
    assert resumed_retry["continuation"]["reason"] == "superseded_agent_decision"
    assert desk.workspace.store.recover(CLAIM) == before
    assert desk.workspace.drafts(CLAIM)["latest"] is None and desk.work.store.list_runs(CLAIM) == []
    assert resumed_retry["response_sha256"] == digest_value({k: v for k, v in resumed_retry.items() if k != "response_sha256"})


@pytest.mark.parametrize("kind", ["step_validation", "relationship_validation"])
def test_disputed_answer_uses_the_engine_rejected_status_in_preview_and_apply(desk, kind):
    state = desk.workspace.store.recover(CLAIM)
    desk.workspace.start(CLAIM, expected_revision=state["revision"], idempotency_key="desk.dispute.setup." + kind,
        process_model="casepath.causal-process/1.0.0")
    agent = desk.claim(CLAIM)
    question = next(q for q in agent["questions"] if q["kind"] == kind)
    body = {"question_id": question["question_id"], "answer_id": "disputed", "actor": "Test handler",
        "reason": "This proposed process requirement does not fit the admitted sources.",
        "expected_revision": agent["workspace_revision"], "expected_state_sha256": agent["workspace_state_sha256"]}
    preview = desk.preview_decision(CLAIM, **body)
    assert preview["answer_id"] == "disputed"
    assert preview["causal"]["operation"]["status"] == "rejected"
    accepted = desk.apply_decision(CLAIM, **body, preview_sha256=preview["preview_sha256"],
        idempotency_key="desk.dispute.accept." + kind, dispatch=False)
    assert accepted["answer_id"] == "disputed"
    target = question["question_id"].split(":", 1)[1]
    collection, id_field = ("nodes", "node_id") if kind == "step_validation" else ("edges", "edge_id")
    item = next(item for item in accepted["process"]["graph"][collection] if item[id_field] == target)
    assert item["validation"]["status"] == "rejected"


def test_native_reopen_clears_inconsistent_completion_and_replays_one_real_continuation(desk):
    state = desk.workspace.store.recover(CLAIM)
    desk.workspace.start(CLAIM, expected_revision=state["revision"], idempotency_key="desk.reopen.setup",
        process_model="casepath.causal-process/1.0.0")
    node_id = "review_lease_copy"

    def edit(operation, key):
        parent = desk.workspace.store.recover(CLAIM)
        body = {"operation": operation, "actor": "Test handler", "reason": "Review the lease-copy prerequisite.",
            "expected_revision": parent["revision"], "expected_state_sha256": parent["state_sha256"]}
        preview = desk.process.preview(CLAIM, **body)
        return desk.process.apply(CLAIM, **body, preview_sha256=preview["preview_sha256"], idempotency_key=key)

    edit({"type": "node.add", "node": {"node_id": node_id, "label": "Review the lease copy", "entry": True,
        "document_types": []}}, "desk.reopen.add")
    completed = edit({"type": "node.complete", "node_id": node_id, "completed": True}, "desk.reopen.complete")
    prior = next(row for row in completed["process"]["evaluation"]["nodes"] if row["node_id"] == node_id)
    assert prior["effective_completed"] is True and prior["inconsistent_completion"] is False
    changed = edit({"type": "node.update", "node_id": node_id, "changes": {"document_types": ["lease_contract"]}},
        "desk.reopen.prerequisite")
    inconsistent = next(row for row in changed["process"]["evaluation"]["nodes"] if row["node_id"] == node_id)
    assert inconsistent["completed"] is True and inconsistent["inconsistent_completion"] is True
    assert inconsistent["missing_document_types"] == ["lease_contract"]

    before = desk.workspace.store.recover(CLAIM)
    agent = desk.claim(CLAIM)
    question = next(row for row in agent["questions"] if row["question_id"] == "completion:" + node_id)
    assert question["kind"] == "inconsistent_completion"
    body = {"question_id": question["question_id"], "answer_id": "reopen", "actor": "Test handler", "reason": "",
        "expected_revision": agent["workspace_revision"], "expected_state_sha256": agent["workspace_state_sha256"]}
    preview = desk.preview_decision(CLAIM, **body)
    assert preview["causal"]["operation"] == {"type": "node.complete", "node_id": node_id, "completed": False}
    assert desk.workspace.store.recover(CLAIM) == before and desk.work.store.list_runs(CLAIM) == []
    assert preview["impact"]["changed_node_ids"] == [node_id]
    assert node_id not in preview["impact"]["inconsistent_completed_node_ids"]
    assert "lease_contract" in preview["impact"]["unchanged_document_types"]
    assert preview["impact"]["next_action_changed"] is True

    args = {**body, "preview_sha256": preview["preview_sha256"], "idempotency_key": "desk.reopen.accept"}
    accepted = desk.apply_decision(CLAIM, **args, dispatch=False)
    reopened = next(row for row in accepted["process"]["evaluation"]["nodes"] if row["node_id"] == node_id)
    assert reopened["completed"] is False and reopened["effective_completed"] is False
    assert reopened["inconsistent_completion"] is False and reopened["missing_document_types"] == ["lease_contract"]
    assert question["question_id"] not in {row["question_id"] for row in accepted["agent"]["questions"]}
    assert accepted["process"]["claim_decision_authorized"] is False
    assert accepted["agent"]["claim_decision_authorized"] is False
    assert accepted["continuation"]["started"] is True
    runs = desk.work.store.list_runs(CLAIM)
    assert len(runs) == 1 and runs[0]["request"]["facts_worker"] == "reference"
    assert runs[0]["idempotency_key"] == "desk.continue." + accepted["event_sha256"]
    current = desk.workspace.store.recover(CLAIM)
    draft = desk.workspace.drafts(CLAIM)["latest"]
    assert draft["status"] == "draft_not_sent"
    assert "lease_contract" in {row["document_type"] for row in draft["requested"]}
    repeated = desk.apply_decision(CLAIM, **args, dispatch=False)
    assert repeated["replayed"] is True and repeated["event_sha256"] == accepted["event_sha256"]
    assert repeated["causal_result"]["process"] == accepted["causal_result"]["process"]
    assert desk.workspace.store.recover(CLAIM) == current
    assert len(desk.workspace.drafts(CLAIM)["items"]) == 1 and len(desk.work.store.list_runs(CLAIM)) == 1

    # Execute the genuine queued reference review, rather than substituting a
    # successful summary. Reopening a step does not supply its missing evidence.
    run_id = runs[0]["run_id"]
    result = AgentWorkExecutor(desk.work.store, desk.work.authority).execute(run_id)
    assert result["status"] == "completed"
    final = desk.claim(CLAIM)
    assert final["run"]["completed_roles"] == final["run"]["role_count"] == 6
    assert final["run"]["currentness"] == "current"
    assert final["run"]["provider_requests"] == 0 and final["run"]["pending_calls"] == []
    assert final["claim_decision_authorized"] is False
    final_state = desk.workspace.store.recover(CLAIM)
    assert final_state["intake_assessment"] == before["intake_assessment"]
    assert final_state["deadline_at"]["date"] is None
    replayed = desk.apply_decision(CLAIM, **args, dispatch=False)
    assert replayed["event_sha256"] == accepted["event_sha256"] and replayed["replayed"] is True
    assert len(desk.work.store.list_runs(CLAIM)) == len(desk.workspace.drafts(CLAIM)["items"]) == 1


def test_delegate_continuation_rechecks_workspace_after_context_and_preserves_receipt(desk, monkeypatch):
    state = desk.workspace.store.recover(CLAIM)
    desk.workspace.start(CLAIM, expected_revision=state["revision"], idempotency_key="desk.delegate.concurrent.setup",
        process_model="casepath.causal-process/1.0.0")
    agent = desk.claim(CLAIM)
    question = next(q for q in agent["questions"] if q["kind"] == "source_conflict")
    body = {"question_id": question["question_id"], "answer_id": "keep_open", "actor": "Test handler", "reason": "",
        "expected_revision": agent["workspace_revision"], "expected_state_sha256": agent["workspace_state_sha256"]}
    preview = desk.preview_decision(CLAIM, **body)
    args = {**body, "preview_sha256": preview["preview_sha256"], "idempotency_key": "desk.delegate.concurrent.accept"}
    real_context = desk.work.context
    changed = False
    def context_then_edit(claim_id):
        nonlocal changed
        value = real_context(claim_id)
        current = desk.workspace.store.recover(claim_id)
        edit = {"operation": {"type": "conditions.set", "flag": "family_home", "verdict": "false"},
            "actor": "Other handler", "reason": "The source does not establish this condition.",
            "expected_revision": current["revision"], "expected_state_sha256": current["state_sha256"]}
        causal_preview = desk.process.preview(claim_id, **edit)
        desk.process.apply(claim_id, **edit, preview_sha256=causal_preview["preview_sha256"], idempotency_key="desk.delegate.concurrent.edit")
        changed = True
        return value
    monkeypatch.setattr(desk.work, "context", context_then_edit)
    accepted = desk.apply_decision(CLAIM, **args, dispatch=False)
    assert changed and accepted["replayed"] is False
    assert accepted["continuation"]["reason"] == "superseded_agent_decision"
    assert desk.work.store.list_runs(CLAIM) == [] and desk.workspace.drafts(CLAIM)["latest"] is None
    monkeypatch.undo()
    before = desk.workspace.store.recover(CLAIM)
    repeated = desk.apply_decision(CLAIM, **args, dispatch=False)
    assert repeated["event_sha256"] == accepted["event_sha256"] and repeated["replayed"] is True
    assert repeated["continuation"]["reason"] == "superseded_agent_decision"
    assert desk.workspace.store.recover(CLAIM) == before and desk.work.store.list_runs(CLAIM) == []


def test_desk_cache_does_not_hide_altered_prefix_or_expose_mutable_cached_rows(desk):
    value = desk.desk()
    group = next(g for g in value["groups"] if g["claims"])
    claim_id = group["claims"][0]["claim_id"]
    group["claims"][0]["ask"] = "Invented activity"
    assert all(row["ask"] != "Invented activity" for g in desk.desk()["groups"] for row in g["claims"])
    with desk.workspace.store.journal.connect() as db:
        db.execute("UPDATE claim_loop_events SET event_sha256=? WHERE session_id=? AND loop_id=? AND sequence=1",
            ("a" * 64, "casepath-workspace-local", "workspace." + claim_id))
    with pytest.raises(ValueError, match="chain"):
        desk.desk()


def test_one_delegate_change_rebuilds_only_its_row_and_other_prefix_tamper_still_fails(desk, monkeypatch):
    before = desk.desk()
    original_rows = {row["claim_id"]: row for group in before["groups"] for row in group["claims"]}
    desk.control(CLAIM, **control_body(desk, "pause"), idempotency_key="desk.cache.one-claim.pause")
    projected = []
    claim = desk.claim
    def count_projection(claim_id, **kwargs):
        projected.append(claim_id)
        return claim(claim_id, **kwargs)
    monkeypatch.setattr(desk, "claim", count_projection)
    after = desk.desk()
    assert projected == [CLAIM]
    current_rows = {row["claim_id"]: row for group in after["groups"] for row in group["claims"]}
    assert current_rows[CLAIM]["agent_state"] == "paused"
    assert all(row == current_rows[claim_id] for claim_id, row in original_rows.items() if claim_id != CLAIM)
    other = next(claim_id for claim_id in current_rows if claim_id != CLAIM)
    with desk.workspace.store.journal.connect() as db:
        db.execute("UPDATE claim_loop_events SET event_sha256=? WHERE session_id=? AND loop_id=? AND sequence=1",
            ("c" * 64, "casepath-workspace-local", "workspace." + other))
    with pytest.raises(ValueError, match="chain"):
        desk.desk()


def test_desk_arrival_is_persistently_idempotent_and_prepares_real_not_sent_draft(desk):
    before = desk.desk()
    assert before["total"] == before["unstarted_count"] == 150
    first = desk.start(limit=1, idempotency_key="desk.arrival.stable.0001")
    repeated = AgentDeskServiceV1(desk.workspace, desk.work).start(limit=1, idempotency_key="desk.arrival.stable.0001")
    assert first["results"][0]["run"]["run_id"] == repeated["results"][0]["run"]["run_id"]
    assert len(desk.work.store.list_runs(CLAIM)) == 1
    with pytest.raises(ValueError, match="idempotency"):
        desk.start(limit=2, idempotency_key="desk.arrival.stable.0001")
    desk.work.shutdown()
    run = desk.work.store.list_runs(CLAIM)[0]
    assert run["status"] == "completed"
    assert desk.workspace.drafts(CLAIM)["latest"]["status"] == "draft_not_sent"
    assert any(q["kind"] == "draft_approval" for q in desk.claim(CLAIM)["questions"])
    after = desk.desk()
    rows = [row for group in after["groups"] for row in group["claims"]]
    assert after["total"] == len(rows) == 150
    assert after["unstarted_count"] == 149
    assert {row["claim_id"] for row in rows if row["review_started"]} == {CLAIM}
    assert all(row["review_started"] is (row["run_id"] is not None) for row in rows)
    assert after["projection_sha256"] == digest_value({k: v for k, v in after.items() if k != "projection_sha256"})


def test_approved_draft_is_not_sent_and_exact_retry_is_accepted(desk):
    state = desk.workspace.store.recover(CLAIM)
    state = desk.workspace.start(CLAIM, expected_revision=state["revision"], idempotency_key="desk.draft.setup.0001")["state"]
    state = desk.workspace.record_draft(CLAIM, expected_revision=state["revision"], expected_state_sha256=state["state_sha256"], idempotency_key="desk.draft.prepare.0001")["state"]
    body = {"question_id": "draft:request", "answer_id": "approve", "actor": "Test handler", "reason": "",
            "expected_revision": state["revision"], "expected_state_sha256": state["state_sha256"]}
    preview = desk.preview_decision(CLAIM, **body)
    assert preview["question"]["draft"]["body_markdown"]
    args = {**body, "preview_sha256": preview["preview_sha256"], "idempotency_key": "desk.draft.approve.0001"}
    accepted = desk.apply_decision(CLAIM, **args, dispatch=False)
    assert accepted["not_sent"] is True
    assert desk.apply_decision(CLAIM, **args, dispatch=False)["event_sha256"] == accepted["event_sha256"]
    assert desk.workspace.drafts(CLAIM)["latest"]["status"] == "draft_not_sent"
    current = desk.workspace.store.recover(CLAIM)
    latest = desk.workspace.drafts(CLAIM)["latest"]
    desk.workspace.record_draft(CLAIM, expected_revision=current["revision"], expected_state_sha256=current["state_sha256"],
        idempotency_key="desk.draft.edit.after-approval.0001", replaces_event_sha256=latest["event_sha256"],
        edited_body=latest["body_markdown"] + "\nPlease include readable copies of the requested pages.")
    assert any(q["kind"] == "draft_approval" for q in desk.claim(CLAIM)["questions"])
    row = next(row for group in desk.desk()["groups"] for row in group["claims"] if row["claim_id"] == CLAIM)
    assert row["draft_status"] == "draft_not_sent"


def test_lesson_preview_requires_validated_scope_and_approval_is_replayable(desk):
    state = desk.workspace.store.recover(CLAIM)
    desk.workspace.start(CLAIM, expected_revision=state["revision"], idempotency_key="desk.lesson.setup.0001")
    agent = desk.claim(CLAIM)
    scope = {"name": "Family-home service review", "node_ids": ["lt_family"], "actor": "Test handler", "reason": "Keep this bounded reviewed step for later proposals.",
             "expected_revision": agent["workspace_revision"], "expected_state_sha256": agent["workspace_state_sha256"]}
    with pytest.raises(ValueError, match="validate"):
        desk.preview_lesson(CLAIM, **scope)
    decision = {"question_id": "node:lt_family", "answer_id": "validated", "actor": "Test handler", "reason": "",
                "expected_revision": agent["workspace_revision"], "expected_state_sha256": agent["workspace_state_sha256"]}
    preview = desk.preview_decision(CLAIM, **decision)
    accepted = desk.apply_decision(CLAIM, **decision, preview_sha256=preview["preview_sha256"], idempotency_key="desk.lesson.validate.0001", dispatch=False)
    scope.update(expected_revision=accepted["agent"]["workspace_revision"], expected_state_sha256=accepted["agent"]["workspace_state_sha256"])
    preview = desk.preview_lesson(CLAIM, **scope)
    assert preview["approval_required"] is True
    assert preview["automatic_learning"] is False
    assert preview["scope"]["boundary_relationships"]
    assert all(doc["held_files"] == [] for doc in preview["fragment_preview"]["document_catalog"])
    args = {**scope, "preview_sha256": preview["preview_sha256"], "idempotency_key": "desk.lesson.approve.0001"}
    saved = desk.apply_lesson(CLAIM, **args)
    assert desk.apply_lesson(CLAIM, **args)["fragment"] == saved["fragment"]
    assert any(f["fragment_sha256"] == saved["fragment"]["fragment_sha256"] for f in desk.claim(CLAIM)["learning"]["fragments"])


def test_replaying_superseded_pause_does_not_stop_a_resumed_delegate(desk):
    original = control_body(desk, "pause")
    desk.control(CLAIM, **original, idempotency_key="desk.pause.superseded.0001")
    desk.control(CLAIM, **control_body(desk, "resume"), idempotency_key="desk.resume.current.0001")
    repeated = desk.control(CLAIM, **original, idempotency_key="desk.pause.superseded.0001")
    assert repeated["replayed"] is True
    assert repeated["agent"]["pause_requested"] is False
    with desk.work.store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM work_pause_requests").fetchone()[0] == 0
