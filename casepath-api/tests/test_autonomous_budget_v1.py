"""Persistent cross-profile spending invariants; disposable SQLite only."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import json
from threading import Event

import httpx
import pytest

from casepath_api.agent_work.contracts import Role, Operation, canonical, digest
from casepath_api.agent_work.openrouter import OpenRouterConfig
from casepath_api.agent_work.store import WorkStore, WorkStoreError, ConflictError
from casepath_api.autonomous_model_v1 import AutonomousModelV1, AutonomousModelError
from test_autonomous_model_v1 import POLICY, SCHEMA, IDENTITY, entry, worker, response, setup


def legacy_run(store, index):
    cfg = OpenRouterConfig(model="test/legacy", prompt_price=Decimal("0.0000001"),
        completion_price=Decimal("0.0000005"), catalogue_entry_sha256="a" * 64)
    request = {"facts_worker": "external_facts", "context": {}, "worker_config": cfg.public(), "worker_config_sha256": digest(cfg.public())}
    run, _ = store.create("legacy-claim-" + str(index), "legacy-idempotency-" + str(index), request, external_limit=3)
    assert store.acquire(run["run_id"], "legacy-owner")
    return run["run_id"]


def legacy_call(store, run, index, cost):
    call = "provider.request." + str(index)
    store.begin_provider_call(run, "legacy-owner", call, "b" * 64, model="test/legacy", maximum_cost_usd="0.0028000")
    store.complete_call(run, "legacy-owner", Role.FACTS, call, {"ok": True}, [{"role": Role.FACTS,
        "operation": Operation.PROVIDER_RESPONSE_RECEIVED, "object_kind": "provider_response", "object_id": call,
        "status": "completed", "worker_kind": "external", "message": "Fixture provider receipt", "after": {"usage": {"cost": cost}}}])


def test_historical_nine_calls_four_runs_and_unknown_reserve_are_never_reset(tmp_path):
    store = WorkStore(tmp_path / "work.sqlite3")
    store.configure_external_budget(POLICY)
    counter = 0
    grant = None
    for index, count in enumerate((2, 2, 4, 1)):
        if index == 3:
            grant = store.grant_one_external_run(digest(store.external_budget()), "Fixture handler", "Fourth historical run", "historical-grant-key")
        run = legacy_run(store, index)
        for n in range(count):
            counter += 1
            legacy_call(store, run, n, None if counter == 1 else 0.0005861 if counter == 9 else 0.0002)
        store.finish(run, "legacy-owner", "completed", "Fixture complete")
    before = store.external_budget()
    assert before["runs_used"] == 4 and before["provider_calls_used"] == 9
    assert Decimal(before["actual_cost_usd"]) == Decimal("0.0019861")
    assert Decimal(before["reserved_cost_usd"]) == Decimal("0.0028000")
    with store.connect() as db:
        rows_before = list(db.execute("SELECT event_json,event_sha256 FROM work_events ORDER BY run_id,sequence"))
        rows_before = [tuple(row) for row in rows_before]
    policy = store.activate_autonomous_policy(digest(before), "CasePath autonomous demo", "New bounded autonomous workflow", "autonomous-mode-key")
    assert store.activate_autonomous_policy(digest(before), "CasePath autonomous demo", "New bounded autonomous workflow", "autonomous-mode-key") == policy
    calls = []
    client = httpx.Client(transport=httpx.MockTransport(lambda request: calls.append(request) or response()))
    model = AutonomousModelV1(store, worker=worker(entry()), schemas={"interpret": SCHEMA, "verify": SCHEMA}, catalogue_entry=entry(), client=client)
    proposal = model.interpret({}, IDENTITY)
    model.verify({}, proposal["result"], IDENTITY)
    after = store.external_budget()
    assert (after["max_runs"], after["effective_max_runs"], after["runs_used"]) == (3, 4, 4)
    assert after["run_grant"] == grant and after["provider_calls_used"] == 11 and after["unknown_calls"] == 1
    assert Decimal(after["actual_cost_usd"]) == Decimal("0.0021861")
    assert Decimal(after["reserved_cost_usd"]) == Decimal("0.0028000")
    assert after["max_provider_calls"] == 18 and after["total_cost_limit_usd"] == "0.10"
    with store.connect() as db:
        assert [tuple(row) for row in db.execute("SELECT event_json,event_sha256 FROM work_events ORDER BY run_id,sequence")] == rows_before
    with pytest.raises(ConflictError):
        legacy_run(store, 4)
    store.close()
    reopened = WorkStore(tmp_path / "work.sqlite3")
    assert reopened.external_budget() == after
    reopened.close()


def test_concurrent_policy_activation_is_exactly_once(tmp_path):
    path = tmp_path / "work.sqlite3"
    stores = [WorkStore(path), WorkStore(path)]
    stores[0].configure_external_budget(POLICY)
    budget_hash = digest(stores[0].external_budget())
    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(lambda s: s.activate_autonomous_policy(budget_hash, "Controller", "Bounded policy", "same-policy-key"), stores))
    assert receipts[0] == receipts[1]
    with pytest.raises(ConflictError):
        stores[0].activate_autonomous_policy(budget_hash, "Controller", "Different intent", "different-policy-key")
    for store in stores:
        store.close()


def test_two_store_instances_do_not_send_the_same_pending_intent_twice(tmp_path):
    entered, release = Event(), Event()
    def transport(_):
        entered.set()
        assert release.wait(3)
        return response()
    store, model, calls, _ = setup(tmp_path, transport)
    second = WorkStore(tmp_path / "work.sqlite3")
    other = AutonomousModelV1(second, worker=worker(entry()), schemas={"interpret": SCHEMA, "verify": SCHEMA}, catalogue_entry=entry(), client=model._client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(model.interpret, {}, IDENTITY)
        try:
            assert entered.wait(3)
            with pytest.raises(WorkStoreError):
                other.interpret({}, IDENTITY)
        finally:
            release.set()
        result = first.result()
    assert other.interpret({}, IDENTITY) == result and len(calls) == 1
    store.close(); second.close()


def test_old_provider_reservation_observes_new_global_pending_slot(tmp_path):
    store, model, _, _ = setup(tmp_path, lambda _: (_ for _ in ()).throw(httpx.ReadTimeout("unknown")))
    old = legacy_run(store, 1)
    with pytest.raises(AutonomousModelError):
        model.interpret({}, IDENTITY)
    with pytest.raises(ConflictError):
        legacy_call(store, old, 1, 0.0001)
    assert store.external_budget()["provider_calls_used"] == 1
    store.close()


def test_global_dollar_reservation_prevents_parallel_workflow_overcommit(tmp_path):
    store, model, calls, _ = setup(tmp_path, policy={**POLICY, "total_cost_limit_usd": "0.02"})
    first = model.interpret({}, IDENTITY)
    assert Decimal(store.external_budget()["actual_cost_usd"]) + Decimal(store.external_budget()["reserved_cost_usd"]) == Decimal("0.02")
    with pytest.raises(AutonomousModelError, match='configured inference allowance is unavailable'):
        model.interpret({}, {**IDENTITY, "workflow_id": "other-workflow"})
    model.verify({}, first["result"], IDENTITY)
    assert len(calls) == 2 and Decimal(store.external_budget()["reserved_cost_usd"]) == 0
    store.close()


def test_provider_overrun_is_recorded_then_freezes_both_admission_paths(tmp_path):
    store, model, calls, _ = setup(tmp_path, lambda _: response(cost=0.03))
    with pytest.raises(AutonomousModelError):
        model.interpret({}, IDENTITY)
    budget = store.external_budget()
    assert Decimal(budget["actual_cost_usd"]) == Decimal("0.03")
    assert budget["reason"] == budget["autonomous_reason"] == "provider_cost_bound_exceeded"
    with pytest.raises(AutonomousModelError, match='configured inference allowance is unavailable'):
        model.interpret({}, {**IDENTITY, "workflow_id": "other-workflow"})
    with pytest.raises(ConflictError):
        legacy_run(store, 1)
    assert len(calls) == 1
    store.close()


@pytest.mark.parametrize("table,field", [("work_autonomous_policy", "max_calls_per_workflow"), ("work_autonomous_calls", "maximum_cost_usd"), ("work_autonomous_outcomes", "result")])
def test_tampered_sealed_records_cannot_expand_limits_or_change_cached_results(tmp_path, table, field):
    store, model, calls, _ = setup(tmp_path)
    model.interpret({}, IDENTITY)
    with store.connect() as db:
        db.execute(f"DROP TRIGGER {table}_no_update")
        row = db.execute(f"SELECT record_json FROM {table} LIMIT 1").fetchone()
        value = json.loads(row[0]); value[field] = 999 if field == "max_calls_per_workflow" else "0" if field == "maximum_cost_usd" else {"accepted": False}
        db.execute(f"UPDATE {table} SET record_json=?", (canonical(value).decode(),))
    with pytest.raises(WorkStoreError):
        model.interpret({}, IDENTITY)
    assert len(calls) == 1
    store.close()


def test_abandon_releases_only_unsent_remainder_and_prevents_late_verification(tmp_path):
    store, model, calls, _ = setup(tmp_path)
    before = store.external_budget()
    assert model.abandon('never-admitted', 'execution_deferred') is None
    assert store.external_budget() == before
    first = model.interpret({}, IDENTITY)
    assert Decimal(store.external_budget()['reserved_cost_usd']) == Decimal('0.0199')
    closed = model.abandon(IDENTITY['workflow_id'], 'execution_deferred')
    assert closed['status'] == 'abandoned'
    assert model.abandon(IDENTITY['workflow_id'], 'execution_deferred') == closed
    assert model.interpret({}, IDENTITY) == first
    after = store.external_budget()
    assert Decimal(after['reserved_cost_usd']) == 0 and Decimal(after['actual_cost_usd']) == Decimal('0.0001')
    with pytest.raises(ConflictError, match='already ended'):
        model.verify({}, first['result'], IDENTITY)
    assert len(calls) == 1
    store.close()
    reloaded = WorkStore(tmp_path / 'work.sqlite3')
    assert reloaded.external_budget() == after
    reloaded.close()


def test_abandon_cannot_release_unknown_call_cost_or_enable_resend(tmp_path):
    store, model, calls, _ = setup(tmp_path, lambda _: (_ for _ in ()).throw(httpx.ReadTimeout('unknown')))
    with pytest.raises(AutonomousModelError):
        model.interpret({}, IDENTITY)
    before = store.external_budget()
    terminal = model.abandon(IDENTITY['workflow_id'], 'execution_deferred')
    assert terminal['status'] == 'unknown'
    assert store.external_budget() == before and Decimal(before['reserved_cost_usd']) > 0
    with pytest.raises(AutonomousModelError):
        model.interpret({}, IDENTITY)
    assert len(calls) == 1
    store.close()


def test_resealed_invalid_terminal_cannot_release_reserved_budget(tmp_path):
    store, model, calls, _ = setup(tmp_path)
    first = model.interpret({}, IDENTITY)
    with store.connect() as db:
        work = json.loads(db.execute('SELECT record_json FROM work_autonomous_workflows').fetchone()[0])
        # Hashes are checksums, not authority: structural parent validation must
        # reject even a self-consistent terminal that invents verifier completion.
        material = {'contract': 'casepath.autonomous-workflow-terminal/1.0.0', 'workflow_id': IDENTITY['workflow_id'],
                    'workflow_sha256': work['workflow_sha256'], 'receipt_sha256': first['receipt']['receipt_sha256'],
                    'status': 'completed', 'recorded_at': first['receipt']['recorded_at']}
        store._autonomous_insert(db, 'work_autonomous_terminals', {'workflow_id': IDENTITY['workflow_id']}, material, 'terminal_sha256')
    with pytest.raises(WorkStoreError):
        store.external_budget()
    assert len(calls) == 1
    store.close()


def test_activation_requires_original_policy_exact_budget_and_no_pending_work(tmp_path):
    store = WorkStore(tmp_path / 'work.sqlite3')
    with pytest.raises(WorkStoreError):
        store.activate_autonomous_policy('a' * 64, 'Controller', 'Bounded policy', 'autonomous-policy')
    store.configure_external_budget(POLICY)
    with pytest.raises(ConflictError):
        store.activate_autonomous_policy('a' * 64, 'Controller', 'Bounded policy', 'autonomous-policy')
    run = legacy_run(store, 1)
    with pytest.raises(ConflictError):
        store.activate_autonomous_policy(digest(store.external_budget()), 'Controller', 'Bounded policy', 'autonomous-policy')
    store.close()
