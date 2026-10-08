"""An interrupted local proposal can be recovered without repeating an effect."""
from copy import deepcopy

import pytest

from casepath_api.agent_work.contracts import Operation, Role
from casepath_api.agent_work.service import AgentWorkService
from casepath_api.agent_work.store import ConflictError, WorkStore, WorkStoreError


class ReadOnlyAuthority:
    def __init__(self):
        self.identity = {"binding_sha256": "a" * 64, "source_roster_sha256": "b" * 64}
        self.saved = {"state_sha256": "c" * 64, "revision": 4,
                      "process": {"nodes": [{"node_id": "deadline", "title": "Preserve deadline"}]}}

    def context(self, claim_id):
        return {**self.identity, "subject": "Interrupted local review"}

    def packet_identity(self, claim_id):
        return dict(self.identity)

    def snapshot(self, claim_id):
        return deepcopy(self.saved)

    def prepare(self, *args):
        raise AssertionError("reconciliation must never invoke authoritative setup")


@pytest.fixture
def interrupted(tmp_path, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr("casepath_api.agent_work.store.time.time", lambda: clock[0])
    authority = ReadOnlyAuthority()
    store = WorkStore(tmp_path / "work.sqlite3")
    service = AgentWorkService(store, authority)
    run, _ = store.create("claim-1", "reference-interrupted-0001",
                          {"facts_worker": "reference", "context": authority.context("claim-1")})
    run_id = run["run_id"]
    assert store.acquire(run_id, "gone", lease_seconds=1)
    store.append(run_id, "gone", role=Role.PROCESS, operation=Operation.AGENT_STARTED,
                 object_kind="role", object_id=Role.PROCESS, status="started",
                 message="Process mapping started", worker_kind="reference")
    store.begin_call(run_id, "gone", Role.PROCESS, "saved-snapshot", "prepare_handling_process", {})
    store.complete_call(run_id, "gone", Role.PROCESS, "saved-snapshot", {"ok": True}, [],
                        objects=[{"id": "authority_snapshot", "kind": "authority_snapshot", "value": authority.saved}])
    store.begin_call(run_id, "gone", Role.PROCESS, "reference.process_decision_mapping.4",
                     "propose_process_node", {"object_id": "deadline"})
    clock[0] = 1002.0
    command = {"call_id": "reference.process_decision_mapping.4", "object_id": "deadline",
               "expected_last_event_sha256": store.events(run_id)[-1]["event_sha256"],
               "expected_work_state_sha256": authority.saved["state_sha256"],
               "actor": "Test handler", "reason": "Reviewed the saved local proposal."}
    yield service, run_id, command, clock
    service.shutdown()


def test_reconcile_commits_exact_saved_proposal_without_dispatch_or_claim_change(interrupted, monkeypatch):
    service, run_id, command, _ = interrupted
    before = service.store.snapshot(run_id)
    authority_before = service.authority.snapshot("claim-1")
    monkeypatch.setattr(service, "_submit", lambda *_: pytest.fail("reconciliation dispatched work"))
    receipt = service.reconcile_process_node("claim-1", run_id, **command)
    after = service.store.snapshot(run_id)
    assert after["events"][:len(before["events"])] == before["events"]
    assert after["run"]["status"] == "interrupted" and after["pending_calls"] == []
    assert after["run"]["owner"] is None and after["run"]["lease_until"] is None
    assert service.authority.snapshot("claim-1") == authority_before
    assert service.store.object(run_id, "node:deadline")["value"] == authority_before["process"]["nodes"][0]
    assert len([e for e in after["events"] if e["operation"] == "LOCAL_PROPOSAL_RECONCILED"]) == 1
    assert receipt["replayed"] is False and receipt["claim_state_changed"] is False
    assert service.recovery(after)["can_resume"] is True
    replay = service.reconcile_process_node("claim-1", run_id, **command)
    assert replay["replayed"] is True and replay["event_sha256"] == receipt["event_sha256"]
    assert service.store.snapshot(run_id) == after
    # The existing runner can now replay this exact call; no second proposal is emitted.
    assert service.store.acquire(run_id, "resumer")
    result = service.store.begin_call(run_id, "resumer", Role.PROCESS, command["call_id"],
                                      "propose_process_node", {"object_id": "deadline"})
    assert result["ok"] is True and result["result"]["node"] == authority_before["process"]["nodes"][0]


@pytest.mark.parametrize("damage", ["active_lease", "different_node", "different_event", "different_state", "source_changed", "claim_changed", "cross_claim"])
def test_reconcile_rejects_unproven_identity_without_journal_change(interrupted, damage):
    service, run_id, command, clock = interrupted
    claim = "claim-1"
    if damage == "active_lease": clock[0] = 1000.5
    elif damage == "different_node": command["object_id"] = "other"
    elif damage == "different_event": command["expected_last_event_sha256"] = "d" * 64
    elif damage == "different_state": command["expected_work_state_sha256"] = "d" * 64
    elif damage == "source_changed": service.authority.identity["source_roster_sha256"] = "d" * 64
    elif damage == "claim_changed": service.authority.saved["state_sha256"] = "d" * 64
    elif damage == "cross_claim": claim = "claim-2"
    before = service.store.snapshot(run_id)
    with pytest.raises((ConflictError, WorkStoreError)):
        service.reconcile_process_node(claim, run_id, **command)
    assert service.store.snapshot(run_id) == before


def test_recovery_projects_only_a_unique_hash_bound_local_node(interrupted):
    service, run_id, command, _ = interrupted
    snapshot = service.store.snapshot(run_id)
    recovery = service.recovery(snapshot)
    candidate = recovery["reconciliation"]
    assert candidate == {"kind": "process_node", "run_id": run_id,
                         "call_id": command["call_id"], "object_id": "deadline", "title": "Preserve deadline",
                         "expected_last_event_sha256": command["expected_last_event_sha256"],
                         "expected_work_state_sha256": command["expected_work_state_sha256"]}
    for tool in ("prepare_handling_process", "provider.request", "unknown_tool"):
        altered = deepcopy(snapshot)
        altered["pending_calls"][0]["tool_name"] = tool
        assert service.recovery(altered) == {"can_resume": False, "reason": "pending_operation"}


def test_reconcile_replay_does_not_accept_changed_handler_command(interrupted):
    service, run_id, command, _ = interrupted
    service.reconcile_process_node("claim-1", run_id, **command)
    after = service.store.snapshot(run_id)
    with pytest.raises(ConflictError):
        service.reconcile_process_node("claim-1", run_id, **{**command, "reason": "Different reason"})
    assert service.store.snapshot(run_id) == after


@pytest.mark.parametrize("damage", ["provider_event", "pending_authority", "pending_unknown", "multiple_pending", "cancelled", "scheduled_here"])
def test_reconcile_never_releases_an_effectful_or_still_owned_call(interrupted, damage):
    service, run_id, command, clock = interrupted
    clock[0] = 1000.5
    if damage == "provider_event":
        service.store.append(run_id, "gone", role=Role.FACTS, operation=Operation.PROVIDER_REQUEST_STARTED,
                             object_kind="provider", object_id="request-1", status="started",
                             message="Unconfirmed provider call", worker_kind="external")
    elif damage in {"pending_authority", "pending_unknown", "multiple_pending"}:
        tool = "prepare_handling_process" if damage == "pending_authority" else "unknown" if damage == "pending_unknown" else "propose_process_node"
        service.store.begin_call(run_id, "gone", Role.PROCESS, "another-call", tool, {})
    elif damage == "cancelled":
        service.store.request_cancel(run_id)
    else:
        from concurrent.futures import Future
        service._jobs[run_id] = Future()
    clock[0] = 1002.0
    command["expected_last_event_sha256"] = service.store.events(run_id)[-1]["event_sha256"]
    before = service.store.snapshot(run_id)
    with pytest.raises(ConflictError):
        service.reconcile_process_node("claim-1", run_id, **command)
    assert service.store.snapshot(run_id) == before


def test_reconcile_rechecks_lease_at_commit(interrupted, monkeypatch):
    service, run_id, command, clock = interrupted
    before = service.store.snapshot(run_id)
    original = service.store.reconcile_process_node
    def lease_renewed(*args, **kwargs):
        clock[0] = 1000.5
        return original(*args, **kwargs)
    monkeypatch.setattr(service.store, "reconcile_process_node", lease_renewed)
    with pytest.raises(ConflictError):
        service.reconcile_process_node("claim-1", run_id, **command)
    assert service.store.snapshot(run_id) == before


def test_reconcile_rechecks_authority_at_commit(interrupted, monkeypatch):
    service, run_id, command, _ = interrupted
    before = service.store.snapshot(run_id)
    original = service.store.reconcile_process_node
    def authority_changed(*args, **kwargs):
        service.authority.saved["state_sha256"] = "d" * 64
        return original(*args, **kwargs)
    monkeypatch.setattr(service.store, "reconcile_process_node", authority_changed)
    with pytest.raises(ConflictError):
        service.reconcile_process_node("claim-1", run_id, **command)
    assert service.store.snapshot(run_id) == before


def test_two_service_instances_reconcile_one_call_only_once(interrupted):
    from concurrent.futures import ThreadPoolExecutor
    service, run_id, command, _ = interrupted
    other = AgentWorkService(WorkStore(service.store.path), service.authority)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker.reconcile_process_node, "claim-1", run_id, **command)
                       for worker in (service, other)]
            receipts = [future.result() for future in futures]
        assert sorted(receipt["replayed"] for receipt in receipts) == [False, True]
        assert receipts[0]["event_sha256"] == receipts[1]["event_sha256"]
        assert len([e for e in service.store.events(run_id) if e["operation"] == "LOCAL_PROPOSAL_RECONCILED"]) == 1
    finally:
        other.shutdown()


def test_reconcile_can_read_back_its_receipt_after_store_restart(interrupted):
    service, run_id, command, _ = interrupted
    receipt = service.reconcile_process_node("claim-1", run_id, **command)
    reopened = AgentWorkService(WorkStore(service.store.path), service.authority)
    try:
        assert reopened.reconcile_process_node("claim-1", run_id, **command) == {**receipt, "replayed": True}
        assert reopened.store.pending_calls(run_id) == []
    finally:
        reopened.shutdown()
