"""One fixed local-demo extension; disposable SQLite and no provider transport."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import sqlite3

import pytest

from casepath_api.agent_work.contracts import canonical, digest
from casepath_api.agent_work.store import ConflictError, WorkStore, WorkStoreError
from test_agent_work_budget_grant import POLICY, start, call


CONFIG = {"model": "test/capacity", "prompt_price": "0.0000001", "completion_price": "0.0000027",
          "request_price": "0", "max_request_bytes": 64000, "max_output_tokens": 1000,
          "max_calls_per_workflow": 2, "context_length": 131072, "protocol": "strict_json_schema",
          "adapter_version": "casepath.autonomous-model/1.0.0", "catalogue_entry_sha256": "a" * 64,
          "reasoning_supported": False, "free": False, "timeout_seconds": 30}
RESULT = {"accepted": True}


def identity(index):
    return {"workflow_id": "fixture.workflow." + str(index), "claim_id": "synthetic-" + str(index)}


def begin(store, index, stage="interpret", *, config=None, allow_send=True):
    return store.begin_autonomous_call(stage, identity(index), config or CONFIG,
        request_sha256=digest({"index": index, "stage": stage}), request_bytes=1000,
        context_sha256=digest({"index": index}), schema_sha256="b" * 64,
        proposal_sha256=digest(RESULT) if stage == "verify" else None, allow_send=allow_send)


def complete(store, index, stage="interpret", *, cost="0.0001", status="completed", config=None):
    admitted = begin(store, index, stage, config=config)
    return store.complete_autonomous_call(identity(index)["workflow_id"], stage,
        intent_sha256=admitted["intent"]["intent_sha256"], status=status,
        result=RESULT if status == "completed" else None, cost_usd=cost, metadata={"fixture": True})


def pair(store, index, cost="0.0001"):
    complete(store, index, cost=cost)
    return complete(store, index, "verify", cost=cost)


def grant(store, before=None, **changes):
    return store.grant_three_autonomous_workflows(**{
        "expected_budget_sha256": digest(before or store.external_budget()), "actor": "fixture:operator",
        "reason": "Three future local client workflows under the original dollar ceiling",
        "idempotency_key": "fixture-three-workflows", **changes})


def history(store):
    with store.connect() as db:
        tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                  if row[0] != "work_autonomous_capacity_grant"]
        return {table: [tuple(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY rowid")] for table in tables}


def prepared(tmp_path, *, cost="0.0001", last="complete", active_legacy=False):
    store = WorkStore(tmp_path / "work.sqlite3")
    store.configure_external_budget(POLICY)
    store.activate_autonomous_policy(digest(store.external_budget()), "fixture:operator", "Disposable test policy", "fixture-activation")
    for index, count in enumerate((2, 2, 1, 1)):
        if index == 3:
            store.grant_one_external_run(digest(store.external_budget()), "fixture:operator", "Historical fourth run", "fixture-legacy-grant")
        run = start(store, index)
        for n in range(count):
            call(store, run, n, None if index == n == 0 else cost)
        if not (active_legacy and index == 3):
            store.finish(run, "owner", "completed", "Fixture complete")
    for index in range(5):
        pair(store, index, cost)
    if last == "rejected":
        complete(store, 5, cost=cost, status="rejected")
        return store
    if last == "not_started":
        return store
    complete(store, 5, cost=cost)
    if last == "pending":
        begin(store, 5, "verify")
    else:
        complete(store, 5, "verify", cost=None if last == "unknown" else cost,
                 status="unknown" if last == "unknown" else "completed")
    return store


@pytest.fixture
def store(tmp_path):
    value = prepared(tmp_path)
    yield value
    value.close()


def test_grant_preserves_all_history_and_dollars_then_admits_exactly_three_pairs(store):
    before, rows = store.external_budget(), history(store)
    assert before["provider_calls_used"] == 18 and before["autonomous_can_start"] is False
    with pytest.raises(ConflictError):
        begin(store, 10)
    receipt = grant(store, before)
    assert history(store) == rows
    assert receipt["prior_budget"] == before
    assert receipt["prior_budget_sha256"] == digest(before)
    assert receipt["grant_sha256"] == digest({k: v for k, v in receipt.items() if k != "grant_sha256"})
    after = store.external_budget()
    assert {k: after[k] for k in POLICY} == POLICY
    for key in ("runs_used", "effective_max_runs", "run_grant", "provider_calls_used", "autonomous_workflows_used",
                "autonomous_provider_calls_used", "actual_cost_usd", "reserved_cost_usd", "unknown_calls"):
        assert after[key] == before[key]
    assert after["effective_autonomous_max_provider_calls"] == 24
    assert after["autonomous_capacity_grant"] == receipt and after["autonomous_can_start"] is True
    assert after["can_start"] is False and after["automatic_retry"] is False
    assert Decimal(after["reserved_cost_usd"]) == Decimal("0.0028")
    with pytest.raises(ConflictError):
        start(store, 20)
    saved = None
    for index in range(10, 13):
        saved = pair(store, index)
    exhausted = store.external_budget()
    assert exhausted["provider_calls_used"] == 24 and exhausted["autonomous_grant_provider_calls_used"] == 6
    assert exhausted["autonomous_grant_workflows_used"] == 3
    assert exhausted["autonomous_can_start"] is False and exhausted["autonomous_reason"] == "call_limit_reached"
    assert Decimal(exhausted["reserved_cost_usd"]) == Decimal(before["reserved_cost_usd"])
    assert Decimal(exhausted["actual_cost_usd"]) == Decimal(before["actual_cost_usd"]) + Decimal("0.0006")
    with pytest.raises(ConflictError):
        begin(store, 13)
    assert store.external_budget() == exhausted
    assert grant(store, before) == receipt
    store.close()
    reopened = WorkStore(store.path)
    try:
        assert reopened.external_budget() == exhausted
        assert begin(reopened, 12, "verify", allow_send=False) == saved
        assert reopened.external_budget() == exhausted
        with pytest.raises(ConflictError):
            grant(reopened, before, reason="Another allowance")
    finally:
        reopened.close()


def test_early_rejections_consume_workflow_slots_without_inventing_calls_or_retries(store):
    grant(store)
    receipts = [complete(store, index, status="rejected") for index in range(10, 13)]
    budget = store.external_budget()
    assert budget["provider_calls_used"] == 21 and budget["autonomous_grant_provider_calls_used"] == 3
    assert budget["autonomous_grant_workflows_used"] == 3 and budget["autonomous_can_start"] is False
    with pytest.raises(ConflictError):
        begin(store, 13)
    with pytest.raises(ConflictError, match="already ended"):
        begin(store, 12, "verify")
    assert begin(store, 12, allow_send=False) == receipts[-1]
    assert store.external_budget() == budget


def test_seventeen_calls_after_one_stage_rejection_grants_exactly_three_pairs(tmp_path):
    value = prepared(tmp_path, last="rejected")
    try:
        before, rows = value.external_budget(), history(value)
        assert before["provider_calls_used"] == 17 and before["autonomous_reason"] == "call_limit_reached"
        with pytest.raises(ConflictError):
            begin(value, 10)
        receipt = grant(value, before)
        assert receipt["prior_budget"]["provider_calls_used"] == 17 and history(value) == rows
        assert value.external_budget()["effective_autonomous_max_provider_calls"] == 24
        for index in range(10, 13):
            pair(value, index)
        after = value.external_budget()
        assert after["provider_calls_used"] == 23 and after["autonomous_grant_provider_calls_used"] == 6
        assert after["autonomous_grant_workflows_used"] == 3 and after["autonomous_can_start"] is False
        assert after["autonomous_reason"] == "call_limit_reached"
        with pytest.raises(ConflictError):
            begin(value, 13)
        assert value.external_budget() == after
        value.close()
        value = WorkStore(value.path)
        assert value.external_budget() == after and grant(value, before) == receipt
    finally:
        value.close()


def test_sixteen_calls_still_allow_a_pair_and_cannot_receive_a_capacity_grant(tmp_path):
    value = prepared(tmp_path, last="not_started")
    try:
        before, rows = value.external_budget(), history(value)
        assert before["provider_calls_used"] == 16 and before["autonomous_can_start"] is True
        with pytest.raises(ConflictError, match="two-call workflow"):
            grant(value, before)
        assert value.external_budget() == before and history(value) == rows
    finally:
        value.close()


def test_grant_is_cas_bound_and_concurrent_exact_replay_is_idempotent(store):
    before, rows = store.external_budget(), history(store)
    with pytest.raises(ConflictError, match="snapshot changed"):
        grant(store, expected_budget_sha256="a" * 64)
    second = WorkStore(store.path)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            receipts = list(pool.map(lambda value: grant(value, before), (store, second)))
        assert receipts[0] == receipts[1]
        assert history(store) == rows
        with pytest.raises(ConflictError):
            grant(second, before, idempotency_key="different-extension-key")
    finally:
        second.close()


@pytest.mark.parametrize("kind", ["pending", "unknown", "active_legacy", "insufficient_dollars"])
def test_grant_rejects_unsettled_work_and_insufficient_original_dollars(tmp_path, kind):
    value = prepared(tmp_path, last=kind if kind in {"pending", "unknown"} else "complete",
                     active_legacy=kind == "active_legacy", cost="0.0028" if kind == "insufficient_dollars" else "0.0001")
    try:
        before, rows = value.external_budget(), history(value)
        assert before["provider_calls_used"] == 18
        with pytest.raises(ConflictError):
            grant(value, before)
        assert value.external_budget() == before and history(value) == rows
    finally:
        value.close()


def test_grant_requires_existing_exact_policy_activation_and_exhausted_calls(tmp_path):
    value = WorkStore(tmp_path / "work.sqlite3")
    try:
        with pytest.raises(WorkStoreError):
            grant(value, expected_budget_sha256="a" * 64)
        value.configure_external_budget(POLICY)
        with pytest.raises(WorkStoreError):
            grant(value)
        value.activate_autonomous_policy(digest(value.external_budget()), "fixture:operator", "Policy", "fixture-activation")
        with pytest.raises(ConflictError, match="eighteen-call"):
            grant(value)
    finally:
        value.close()


def test_workflow_ceiling_pending_slot_and_unknown_reservations_still_apply(store):
    grant(store)
    expensive = {**CONFIG, "request_price": "0.018"}
    before = store.external_budget()
    with pytest.raises(ConflictError, match="cost ceiling"):
        begin(store, 10, config=expensive)
    assert store.external_budget() == before
    pending = begin(store, 10)
    reserved = store.external_budget()
    with pytest.raises(ConflictError, match="pending"):
        begin(store, 11)
    unknown = store.complete_autonomous_call(identity(10)["workflow_id"], "interpret",
        intent_sha256=pending["intent"]["intent_sha256"], status="unknown", result=None, cost_usd=None, metadata={})
    after = store.external_budget()
    assert after["unknown_calls"] == before["unknown_calls"] + 1 and after["in_flight"] is True
    assert Decimal(after["reserved_cost_usd"]) == Decimal(before["reserved_cost_usd"]) + Decimal("0.0028")
    assert Decimal(reserved["reserved_cost_usd"]) == Decimal(before["reserved_cost_usd"]) + Decimal("0.02")
    assert begin(store, 10, allow_send=False) == unknown
    assert store.external_budget() == after


def test_both_stages_share_the_same_original_workflow_cost_ceiling(store):
    grant(store)
    config = {**CONFIG, "request_price": "0.009"}
    complete(store, 10, cost="0.0118", config=config)
    before = store.external_budget()
    with pytest.raises(ConflictError, match="cost ceiling"):
        begin(store, 10, "verify", config=config)
    assert store.external_budget() == before


def test_three_full_cost_workflows_remain_inside_original_aggregate_dollar_limit(tmp_path):
    value = prepared(tmp_path, cost="0.002")
    try:
        grant(value)
        before = value.external_budget()
        assert Decimal(before["remaining_cost_usd"]) == Decimal("0.0632")
        config = {**CONFIG, "request_price": "0.0072"}
        for index in range(10, 13):
            for stage in ("interpret", "verify"):
                complete(value, index, stage, cost="0.0100", config=config)
                budget = value.external_budget()
                assert Decimal(budget["actual_cost_usd"]) + Decimal(budget["reserved_cost_usd"]) <= Decimal("0.10")
        after = value.external_budget()
        assert Decimal(after["actual_cost_usd"]) - Decimal(before["actual_cost_usd"]) == Decimal("0.06")
        assert Decimal(after["remaining_cost_usd"]) == Decimal("0.0032")
        with pytest.raises(ConflictError):
            begin(value, 13)
        assert value.external_budget() == after
    finally:
        value.close()


def test_provider_overrun_after_grant_freezes_new_work_and_retains_observed_cost(store):
    grant(store)
    complete(store, 10, status="rejected", cost="0.003")
    before = store.external_budget()
    assert before["autonomous_reason"] == before["reason"] == "provider_cost_bound_exceeded"
    with pytest.raises(ConflictError):
        begin(store, 11)
    assert store.external_budget() == before


@pytest.mark.parametrize("sql", ["UPDATE work_autonomous_capacity_grant SET record_sha256='changed'",
                                 "DELETE FROM work_autonomous_capacity_grant",
                                 "INSERT OR REPLACE INTO work_autonomous_capacity_grant SELECT * FROM work_autonomous_capacity_grant"])
def test_capacity_grant_is_immutable_at_sql_boundary(store, sql):
    grant(store)
    before = store.external_budget()
    with store.connect() as db, pytest.raises(sqlite3.IntegrityError, match="immutable"):
        db.execute(sql)
    assert store.external_budget() == before


@pytest.mark.parametrize("mutation", ["unsealed", "workflows", "calls", "base", "activation", "roster", "prior_count", "prior_money"])
def test_resealed_invalid_grant_cannot_expand_or_rebind_capacity(store, mutation):
    receipt = grant(store)
    if mutation == "unsealed":
        receipt["reason"] = "Changed without a seal"
    else:
        if mutation == "workflows":
            receipt["additional_workflows"] = 4
        elif mutation == "calls":
            receipt["additional_provider_calls"] = 8
        elif mutation in {"base", "activation"}:
            receipt["base_policy_sha256" if mutation == "base" else "autonomous_policy_sha256"] = "f" * 64
        elif mutation == "roster":
            receipt["prior_workflows"][0]["workflow_sha256"] = "f" * 64
        else:
            receipt["prior_budget"]["provider_calls_used" if mutation == "prior_count" else "remaining_cost_usd"] = 16 if mutation == "prior_count" else "0.05"
            receipt["prior_budget_sha256"] = digest(receipt["prior_budget"])
        receipt["grant_sha256"] = digest({k: v for k, v in receipt.items() if k != "grant_sha256"})
    with store.connect() as db:
        db.execute("DROP TRIGGER work_autonomous_capacity_grant_no_update")
        db.execute("UPDATE work_autonomous_capacity_grant SET record_json=?,record_sha256=?", (canonical(receipt).decode(), receipt["grant_sha256"]))
    with pytest.raises(WorkStoreError):
        store.external_budget()
    with pytest.raises(WorkStoreError):
        begin(store, 10)


@pytest.mark.parametrize("missing", ["grant", "policy", "prior_workflow"])
def test_missing_grant_or_ancestors_reject_replay(store, missing):
    grant(store)
    pair(store, 10)
    table = {"grant": "work_autonomous_capacity_grant", "policy": "work_autonomous_policy",
             "prior_workflow": "work_autonomous_workflows"}[missing]
    with store.connect() as db:
        db.execute(f"DROP TRIGGER {table}_no_delete")
        if missing == "prior_workflow":
            db.execute(f"DELETE FROM {table} WHERE workflow_id=?", (identity(0)["workflow_id"],))
        else:
            db.execute(f"DELETE FROM {table}")
    with pytest.raises(WorkStoreError):
        store.external_budget()
