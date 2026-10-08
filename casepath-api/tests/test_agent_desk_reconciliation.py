from copy import deepcopy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from casepath_api.agent_desk_v1 import AgentDeskServiceV1, create_agent_desk_router
from casepath_api.agent_work.runtime import AgentWorkExecutor, ToolRuntime
from casepath_api.agent_work.store import ConflictError
from test_agent_desk_v1 import CLAIM, desk, control_body


@pytest.fixture
def pending_desk(desk, monkeypatch):
    context = desk.work.context(CLAIM)
    started = desk.work.start(CLAIM, idempotency_key="reconcile.integration.pending",
                              expected_context_sha256=context["context_sha256"], dispatch=False)
    run_id = started["summary"]["run_id"]
    original = ToolRuntime._tool_propose_process_node
    def interrupted_local_buffer(self, args):
        original(self, args)
        raise RuntimeError("isolated executor interrupted before atomic buffer commit")
    monkeypatch.setattr(ToolRuntime, "_tool_propose_process_node", interrupted_local_buffer)
    result = AgentWorkExecutor(desk.work.store, desk.work.authority).execute(run_id)
    assert result["status"] == "blocked"
    monkeypatch.setattr(ToolRuntime, "_tool_propose_process_node", original)
    agent = desk.claim(CLAIM)
    assert agent["recovery_required"] is True
    assert "local step" in agent["recovery_ask"]
    candidate = agent["run"]["recovery"]["reconciliation"]
    body = {k: v for k, v in control_body(desk, "resume").items() if k != "action"}
    body.update({k: v for k, v in candidate.items() if k not in {"kind", "title"}})
    body["reason"] = "Checked the unchanged authoritative node and the unfinished local buffer."
    return desk, run_id, body


def test_control_plane_reconciliation_preserves_authority_and_resumes_exact_calls(pending_desk, monkeypatch):
    desk, run_id, body = pending_desk
    app = FastAPI()
    app.include_router(create_agent_desk_router(lambda: desk))
    client = TestClient(app)
    path = f"/api/claim-loops/v1/workspace/claims/{CLAIM}/agent/reconcile"
    headers = {"X-CasePath-Idempotency-Key": "reconcile.http.0001", "X-CasePath-Agent-Work": "1"}
    before = deepcopy(desk.workspace.store.recover(CLAIM))
    journal_before = desk.work.store.snapshot(run_id)
    delegate_before = desk.delegate.state(CLAIM)
    assert client.post(path, json=body).status_code == 400
    assert client.post(path, json=body, headers={"X-CasePath-Idempotency-Key": "reconcile.http.0001"}).status_code == 403
    assert client.post(path, json=body, headers={**headers, "Origin": "https://elsewhere.example"}).status_code == 403
    assert client.post(path, json={**body, "expected_state_sha256": "f" * 64}, headers=headers).status_code == 409
    assert client.post(path, json={**body, "expected_agent_revision": body["expected_agent_revision"] + 1}, headers=headers).status_code == 409
    assert client.post(path, json={**body, "reason": "x" * 1001}, headers=headers).status_code == 422
    assert desk.work.store.snapshot(run_id) == journal_before
    assert desk.delegate.state(CLAIM) == delegate_before

    monkeypatch.setattr(desk.work, "_submit", lambda *_: pytest.fail("reconciliation may not resume"))
    response = client.post(path, json=body, headers=headers)
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert receipt["contract"] == "casepath.agent-reconciliation-result/1.0.0"
    assert receipt["agent"]["run"]["recovery"]["can_resume"] is True
    assert receipt["reconciliation"]["claim_state_changed"] is False
    assert receipt["reconciliation"]["replayed"] is False
    assert desk.workspace.store.recover(CLAIM) == before
    delegate = desk.delegate.state(CLAIM)
    assert delegate["revision"] == delegate_before["revision"] + 1
    assert delegate["paused"] == delegate_before["paused"] and delegate["decisions"] == delegate_before["decisions"]
    after = desk.work.store.snapshot(run_id)
    assert after["pending_calls"] == [] and after["run"]["status"] == "interrupted"
    repeated = client.post(path, json=body, headers=headers)
    assert repeated.status_code == 200 and repeated.json()["replayed"] is True
    assert repeated.json()["reconciliation"]["event_sha256"] == receipt["reconciliation"]["event_sha256"]
    assert desk.work.store.snapshot(run_id) == after
    assert client.post(path, json={**body, "reason": "Different decision."}, headers=headers).status_code == 409

    # A restarted delegate reducer can read the new additive request exactly.
    restarted = AgentDeskServiceV1(desk.workspace, desk.work)
    assert restarted.delegate.state(CLAIM) == delegate
    node_id = "node:" + body["object_id"]
    node_events_before = [e for e in after["events"] if e["object_id"] == node_id]
    result = AgentWorkExecutor(desk.work.store, desk.work.authority).execute(run_id)
    assert result["status"] == "completed"
    final = desk.work.store.snapshot(run_id)
    assert [e for e in final["events"] if e["object_id"] == node_id] == node_events_before
    assert desk.work.run(CLAIM, run_id)["summary"]["provider_requests"] == 0
    assert desk.workspace.store.recover(CLAIM) == before


def test_recovery_request_survives_interruption_before_work_receipt(pending_desk, monkeypatch):
    desk, run_id, body = pending_desk
    original = desk.work.reconcile_process_node
    def fail_after_request(*args, **kwargs):
        if not kwargs.get("check_only"):
            raise ConflictError("isolated interruption after the handler request")
        return original(*args, **kwargs)
    monkeypatch.setattr(desk.work, "reconcile_process_node", fail_after_request)
    with pytest.raises(ConflictError):
        desk.reconcile(CLAIM, **body, idempotency_key="reconcile.crash.0001")
    requested = desk.delegate.state(CLAIM)
    assert requested["revision"] == body["expected_agent_revision"] + 1
    assert len(desk.work.store.pending_calls(run_id)) == 1
    monkeypatch.setattr(desk.work, "reconcile_process_node", original)
    recovered = desk.reconcile(CLAIM, **body, idempotency_key="reconcile.crash.0001")
    assert recovered["replayed"] is True and recovered["reconciliation"]["replayed"] is False
    assert desk.delegate.state(CLAIM) == requested
    assert desk.work.store.pending_calls(run_id) == []


def test_superseded_recovery_request_cannot_reconstruct_after_new_handler_control(pending_desk, monkeypatch):
    desk, run_id, body = pending_desk
    original = desk.work.reconcile_process_node
    def fail_after_request(*args, **kwargs):
        if not kwargs.get("check_only"):
            raise ConflictError("isolated interruption after the handler request")
        return original(*args, **kwargs)
    monkeypatch.setattr(desk.work, "reconcile_process_node", fail_after_request)
    with pytest.raises(ConflictError):
        desk.reconcile(CLAIM, **body, idempotency_key="reconcile.superseded.0001")
    command = {k: v for k, v in control_body(desk, "pause").items() if k != "action"}
    desk.delegate.append(CLAIM, "AGENT_MANDATE_PAUSED", command, "reconcile.superseding.pause")
    monkeypatch.setattr(desk.work, "reconcile_process_node", original)
    before = desk.work.store.snapshot(run_id)
    result = desk.reconcile(CLAIM, **body, idempotency_key="reconcile.superseded.0001")
    assert result["reconciliation"] == {"reconciled": False, "reason": "superseded_recovery_request"}
    assert desk.work.store.snapshot(run_id) == before
    assert desk.delegate.state(CLAIM)["paused"] is True


def test_verified_local_reconciliation_is_visible_and_preserves_a_paused_mandate(pending_desk):
    desk, run_id, body = pending_desk
    command = {k: v for k, v in control_body(desk, "pause").items() if k != "action"}
    desk.delegate.append(CLAIM, "AGENT_MANDATE_PAUSED", command, "reconcile.paused.mandate")
    agent = desk.claim(CLAIM)
    assert agent["pause_requested"] is True and agent["recovery_required"] is True
    assert agent["run"]["recovery"]["reconciliation"]["run_id"] == run_id
    body.update(expected_agent_revision=agent["agent_revision"], expected_agent_state_sha256=agent["agent_state_sha256"])
    result = desk.reconcile(CLAIM, **body, idempotency_key="reconcile.paused.step")
    assert result["reconciliation"]["reconciled"] is True
    assert result["agent"]["pause_requested"] is True
    assert desk.delegate.state(CLAIM)["paused"] is True
    assert desk.work.store.snapshot(run_id)["run"]["status"] == "interrupted"
