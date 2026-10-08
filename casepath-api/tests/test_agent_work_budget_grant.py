"""One explicitly approved extra run; synthetic SQLite fixtures, no providers."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import sqlite3

import pytest

from casepath_api.agent_work.contracts import Operation, Role, canonical, digest
from casepath_api.agent_work.store import ConflictError, WorkStore, WorkStoreError


POLICY = {"max_runs": 3, "max_provider_calls": 18,
          "total_cost_limit_usd": "0.10", "run_cost_limit_usd": "0.02"}
CONFIG = {"model": "test/reader", "prompt_price": "0.0000001",
          "completion_price": "0.0000002", "request_price": "0",
          "max_request_bytes": 20000, "max_output_tokens": 4000,
          "max_requests": 6, "cost_limit_usd": "0.02"}
REQUEST = {"facts_worker": "external_facts", "worker_config": CONFIG,
           "worker_config_sha256": digest(CONFIG)}


@pytest.fixture
def store(tmp_path):
    value = WorkStore(tmp_path / "work.sqlite3")
    value.configure_external_budget(POLICY)
    yield value
    value.close()


def start(store, index, *, external_limit=3):
    row, created = store.create("synthetic-" + str(index), "explicit-run-" + str(index),
                                REQUEST, external_limit=external_limit)
    assert created and store.acquire(row["run_id"], "owner")
    return row["run_id"]


def call(store, run_id, index, cost):
    call_id = "provider.request." + str(index)
    store.begin_provider_call(run_id, "owner", call_id, "b" * 64,
                              model="test/reader", maximum_cost_usd="0.0028")
    store.complete_call(run_id, "owner", Role.FACTS, call_id, {"ok": True}, [{
        "role": Role.FACTS, "operation": Operation.PROVIDER_RESPONSE_RECEIVED,
        "object_kind": "provider_response", "object_id": call_id,
        "status": "completed", "worker_kind": "external", "message": "Synthetic receipt",
        "after": {"usage": {"cost": cost}}}])


def exhaust(store):
    for index in range(3):
        run_id = start(store, index)
        if index == 0:
            call(store, run_id, 0, "0.001463")
        elif index == 1:
            call(store, run_id, 0, None)
        store.finish(run_id, "owner", "failed", "Synthetic failure")
    return store.external_budget()


def grant(store, before=None, **updates):
    command = {"expected_budget_sha256": digest(before or store.external_budget()),
               "actor": "human:synthetic", "reason": "Approve one bounded fourth attempt",
               "idempotency_key": "explicit-fourth-run"}
    return store.grant_one_external_run(**{**command, **updates})


def history(store):
    with store.connect() as db:
        return {name: [tuple(row) for row in db.execute("SELECT * FROM " + name + " ORDER BY rowid")]
                for name in ("work_external_budget", "work_runs", "work_external_permits",
                             "work_events", "work_calls", "work_objects")}


def test_grant_retains_all_history_and_caps_across_reload_and_only_admits_fourth(store):
    before = exhaust(store)
    saved = history(store)
    receipt = grant(store, before)
    assert history(store) == saved
    assert receipt["additional_runs"] == 1
    assert receipt["base_policy_sha256"] == digest(POLICY)
    assert receipt["prior_budget"] == before
    assert receipt["prior_budget_sha256"] == digest(before)
    assert receipt["grant_sha256"] == digest({k: v for k, v in receipt.items() if k != "grant_sha256"})
    store.close()
    loaded = WorkStore(store.path)
    try:
        loaded.configure_external_budget(POLICY)
        after = loaded.external_budget()
        assert {k: after[k] for k in POLICY} == POLICY
        assert after["max_runs"] == 3 and after["effective_max_runs"] == 4
        assert after["run_grant"] == receipt and after["can_start"] is True
        for key in ("runs_used", "provider_calls_used", "actual_cost_usd", "reserved_cost_usd", "unknown_calls"):
            assert after[key] == before[key]
        assert Decimal(after["actual_cost_usd"]) == Decimal("0.001463")
        assert Decimal(after["reserved_cost_usd"]) == Decimal("0.0028")
        with pytest.raises(WorkStoreError):
            start(loaded, 4, external_limit=4)
        with pytest.raises(ConflictError):
            start(loaded, 4, external_limit=2)
        fourth = start(loaded, 4)
        assert loaded.events(fourth)[0]["after"]["external_run_grant_sha256"] == receipt["grant_sha256"]
        assert grant(loaded, before) == receipt
        loaded.finish(fourth, "owner", "failed", "Synthetic failure")
        with pytest.raises(ConflictError, match="budget"):
            start(loaded, 5)
        assert loaded.external_budget()["runs_used"] == 4
        assert loaded.external_budget()["reason"] == "run_limit_reached"
        with pytest.raises(ConflictError):
            grant(loaded, before, idempotency_key="another-fourth-run")
        with pytest.raises(WorkStoreError):
            loaded.configure_external_budget({**POLICY, "max_runs": 4})
    finally:
        loaded.close()


@pytest.mark.parametrize("field,value", [("actor", ""), ("actor", "  "), ("actor", "a\n"),
    ("actor", "x" * 181), ("reason", None), ("reason", "x" * 2001),
    ("idempotency_key", "short"), ("idempotency_key", "x" * 129),
    ("expected_budget_sha256", "z" * 64), ("expected_budget_sha256", True)])
def test_grant_rejects_invalid_command_without_mutation(store, field, value):
    before = exhaust(store)
    with pytest.raises(WorkStoreError):
        grant(store, before, **{field: value})
    assert store.external_budget() == before


def test_grant_requires_policy_exhausted_base_budget_and_fresh_snapshot(store, tmp_path):
    empty = WorkStore(tmp_path / "empty.sqlite3")
    try:
        with pytest.raises(WorkStoreError, match="policy|budget"):
            grant(empty)
    finally:
        empty.close()
    original = store.external_budget()
    with pytest.raises(ConflictError, match="exhausted|three|3"):
        grant(store, original)
    before = exhaust(store)
    with pytest.raises(ConflictError, match="changed|snapshot"):
        grant(store, original)
    assert store.external_budget() == before


@pytest.mark.parametrize("pending", [False, True])
def test_grant_denies_active_run_or_terminal_run_with_pending_call(store, pending):
    for index in range(3):
        run_id = start(store, index)
        if index < 2:
            store.finish(run_id, "owner", "failed", "Synthetic failure")
    if pending:
        store.begin_provider_call(run_id, "owner", "provider.pending", "b" * 64,
                                  model="test/reader", maximum_cost_usd="0.0028")
        store.finish(run_id, "owner", "failed", "Synthetic unknown outcome")
    before = store.external_budget()
    with pytest.raises(ConflictError, match="active|pending|unfinished"):
        grant(store, before)
    assert store.external_budget() == before


@pytest.mark.parametrize("same_key", [True, False])
def test_concurrent_grants_are_singleton_and_exact_retries_are_identical(store, same_key):
    before = exhaust(store)
    second = WorkStore(store.path)
    def attempt(index):
        try:
            return grant([store, second][index], before,
                         idempotency_key="concurrent-grant-" + ("same" if same_key else str(index)))
        except ConflictError:
            return None
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, range(2)))
        if same_key:
            assert outcomes[0] == outcomes[1] and outcomes[0] is not None
        else:
            assert sum(result is not None for result in outcomes) == 1
        receipt = next(result for result in outcomes if result is not None)
        with pytest.raises(ConflictError):
            grant(store, before, idempotency_key=receipt["idempotency_key"], reason="Different approval")
        with store.connect() as db:
            assert db.execute("SELECT COUNT(*) FROM work_external_run_grant").fetchone()[0] == 1
    finally:
        second.close()


def test_grant_and_base_policy_rows_are_immutable(store):
    grant(store, exhaust(store))
    with store.connect() as db:
        for table in ("work_external_run_grant", "work_external_budget"):
            for statement in ("DELETE FROM " + table, "UPDATE " + table + " SET singleton=1",
                              "INSERT OR REPLACE INTO " + table + " SELECT * FROM " + table):
                with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                    db.execute(statement)


@pytest.mark.parametrize("tamper", ["unsealed", "resealed_allowance", "base_policy", "snapshot", "removed_after_admission"])
def test_grant_tampering_fails_closed_on_read_and_admission(store, tamper):
    receipt = grant(store, exhaust(store))
    if tamper == "removed_after_admission":
        fourth = start(store, 4)
        store.finish(fourth, "owner", "failed", "Synthetic failure")
    with store.connect() as db:
        if tamper == "removed_after_admission":
            db.execute("DROP TRIGGER work_external_run_grant_no_delete")
            db.execute("DELETE FROM work_external_run_grant")
        else:
            db.execute("DROP TRIGGER work_external_run_grant_no_update")
            material = {k: v for k, v in receipt.items() if k != "grant_sha256"}
            if tamper in ("unsealed", "resealed_allowance"):
                material["additional_runs"] = 2
            elif tamper == "base_policy":
                material["base_policy_sha256"] = "a" * 64
            else:
                material["prior_budget"]["unknown_calls"] = 0
            seal = receipt["grant_sha256"] if tamper == "unsealed" else digest(material)
            changed = {**material, "grant_sha256": seal}
            db.execute("UPDATE work_external_run_grant SET receipt_json=?,receipt_sha256=?",
                       (canonical(changed).decode(), seal))
    with pytest.raises(WorkStoreError, match="grant|allowance|budget"):
        store.external_budget()
    with pytest.raises(WorkStoreError):
        start(store, 5)


@pytest.mark.parametrize("cap", ["calls", "overrun"])
def test_grant_does_not_relax_provider_or_cost_caps(store, cap):
    # Consume the original runs while the call ceiling still permits admission.
    for index in range(3):
        run_id = start(store, index)
        for request_index in range(6):
            call(store, run_id, request_index, "0.003" if cap == "overrun" and index == 2 and request_index == 5 else "0")
        store.finish(run_id, "owner", "failed", "Synthetic failure")
    before = store.external_budget()
    grant(store, before)
    after = store.external_budget()
    assert {k: after[k] for k in POLICY} == POLICY
    assert after["provider_calls_used"] == 18 and after["can_start"] is False
    with pytest.raises(ConflictError):
        start(store, 4)


def test_grant_retains_total_cost_admission_guard(tmp_path):
    limited = WorkStore(tmp_path / "limited.sqlite3")
    limited.configure_external_budget({**POLICY, "total_cost_limit_usd": "0.03"})
    try:
        for index in range(3):
            run_id = start(limited, index)
            if index == 2:
                for request_index in range(4):
                    call(limited, run_id, request_index, "0.0028")
            limited.finish(run_id, "owner", "failed", "Synthetic failure")
        before = limited.external_budget()
        grant(limited, before)
        after = limited.external_budget()
        assert after["total_cost_limit_usd"] == "0.03" and after["run_cost_limit_usd"] == "0.02"
        assert after["provider_calls_used"] == 4 and after["reason"] == "cost_limit_reached"
        assert after["actual_cost_usd"] == before["actual_cost_usd"]
        with pytest.raises(ConflictError, match="cost_limit"):
            start(limited, 4)
    finally:
        limited.close()


def test_grant_does_not_allow_a_larger_per_run_cost(store):
    grant(store, exhaust(store))
    cfg = {**CONFIG, "cost_limit_usd": "0.03"}
    request = {**REQUEST, "worker_config": cfg, "worker_config_sha256": digest(cfg)}
    with pytest.raises(ConflictError, match="cost"):
        store.create("synthetic-fourth", "explicit-fourth-run", request, external_limit=3)
    assert store.external_budget()["runs_used"] == 3


def test_concurrent_fourth_admission_consumes_grant_once(store):
    grant(store, exhaust(store))
    second = WorkStore(store.path)
    def attempt(index):
        try:
            return start([store, second][index], index + 4)
        except ConflictError:
            return None
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, range(2)))
        assert sum(result is not None for result in outcomes) == 1
        assert store.external_budget()["runs_used"] == 4
    finally:
        second.close()
