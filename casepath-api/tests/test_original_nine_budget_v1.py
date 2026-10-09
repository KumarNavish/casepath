"""Exact-nine epoch guards use temporary journals and deterministic calls only."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from decimal import Decimal
import sqlite3

import pytest

from casepath_api.agent_work.contracts import canonical, digest
from casepath_api.agent_work.store import WorkStore, WorkStoreError, ConflictError, ReconciliationRequired
from test_autonomous_budget_grant_v1 import prepared, grant, pair, history
from test_original_nine_preflight_v1 import load_tool, selection, corpus


@pytest.fixture
def exhausted(tmp_path):
    store = prepared(tmp_path)
    grant(store)
    for index in range(10, 13):
        pair(store, index)
    assert store.external_budget()["provider_calls_used"] == 24
    yield store
    store.close()


@pytest.fixture
def proposal(exhausted, selection, corpus):
    tool = load_tool()
    return tool.build_preflight(selection, corpus=corpus, source_commit="8" * 40,
        budget_snapshot=exhausted.external_budget())


def apply(store, proposal, **changes):
    return store.apply_original_nine_grant(**{
        "preflight": proposal, "expected_budget_sha256": proposal["prior_budget_sha256"],
        "actor": "fixture:authenticated-database-operator", "reason": "Explicit temporary-fixture application",
        "idempotency_key": "fixture-exact-nine", "human_approval_reference": "fixture:direct-human-approval",
        "monetary_option": "new_018_total_022", "acknowledged_preflight_sha256": proposal["preflight_sha256"], **changes})


def test_empty_preflight_cannot_apply_an_allowance(exhausted):
    before = exhausted.external_budget()
    with pytest.raises(WorkStoreError):
        exhausted.apply_original_nine_grant(preflight={}, expected_budget_sha256=digest(before),
            actor="fixture:operator", reason="Fixture rejection", idempotency_key="fixture-empty",
            human_approval_reference="fixture:direct-human", monetary_option="existing_010",
            acknowledged_preflight_sha256="0" * 64)
    assert exhausted.external_budget() == before


def begin(store, proposal, index, stage="interpret", **changes):
    row = proposal["eligible_originals"][index]
    return store.begin_autonomous_call(stage, changes.pop("identity", row["identity"]),
        changes.pop("config", proposal["frozen_model_config"]),
        request_sha256=digest({"fixture": index, "stage": stage}), request_bytes=64000,
        context_sha256=row["interpretation"]["context_sha256"],
        schema_sha256=changes.pop("schema_sha256",row["interpretation" if stage == "interpret" else "verification"]["schema_sha256"]),
        proposal_sha256=digest({"accepted": True}) if stage == "verify" else None, **changes)


def complete(store, proposal, index, stage="interpret", *, cost="0.009750000", status="completed"):
    intent = begin(store, proposal, index, stage)["intent"]
    return store.complete_autonomous_call(proposal["eligible_originals"][index]["identity"]["workflow_id"], stage,
        intent_sha256=intent["intent_sha256"], status=status,
        result={"accepted": True} if status == "completed" else None, cost_usd=cost, metadata={"fixture": True})


def test_additive_epoch_preserves_old_rows_and_admits_only_eighteen_calls(exhausted, proposal):
    before, old = exhausted.external_budget(), history(exhausted)
    receipt = apply(exhausted, proposal)
    assert history(exhausted) == {**old, "work_original_nine_grant": history(exhausted)["work_original_nine_grant"]}
    after = exhausted.external_budget()
    assert {k:after[k] for k in ("max_provider_calls", "total_cost_limit_usd", "run_cost_limit_usd")} == {
        "max_provider_calls": 18, "total_cost_limit_usd": "0.10", "run_cost_limit_usd": "0.02"}
    assert after["autonomous_capacity_grant"] == before["autonomous_capacity_grant"]
    assert after["effective_autonomous_max_provider_calls"] == 42
    assert after["effective_total_cost_limit_usd"] == "0.22"
    assert after["original_nine_workflows_used"] == after["original_nine_provider_calls_used"] == 0
    for index in range(9):
        complete(exhausted, proposal, index)
        complete(exhausted, proposal, index, "verify")
    final = exhausted.external_budget()
    assert final["provider_calls_used"] == 42 and final["original_nine_provider_calls_used"] == 18
    assert final["original_nine_workflows_used"] == 9
    assert final["autonomous_grant_workflows_used"] == 3 and final["autonomous_grant_provider_calls_used"] == 6
    assert Decimal(final["reserved_cost_usd"]) == Decimal(before["reserved_cost_usd"])
    assert Decimal(final["original_nine_committed_cost_usd"]) == Decimal("0.1755")
    assert final["autonomous_can_start"] is False
    assert apply(exhausted, proposal) == receipt
    saved = begin(exhausted, proposal, 8, "verify", allow_send=False)
    exhausted.close()
    second = WorkStore(exhausted.path)
    try:
        assert second.external_budget() == final
        assert begin(second, proposal, 8, "verify", allow_send=False) == saved
        assert apply(second, proposal) == receipt
    finally:
        second.close()


def test_same_approval_concurrent_application_is_one_immutable_receipt(exhausted, proposal):
    peer = WorkStore(exhausted.path)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            rows = list(pool.map(lambda s:apply(s, proposal), (exhausted, peer)))
        assert rows[0] == rows[1]
        with exhausted.connect() as db:
            assert db.execute("SELECT COUNT(*) FROM work_original_nine_grant").fetchone()[0] == 1
    finally:
        peer.close()


@pytest.mark.parametrize("change", ["budget", "approval", "option", "ack", "key", "actor", "preflight"])
def test_stale_or_different_approval_never_replaces_grant(exhausted, proposal, change):
    if change == "budget":
        with pytest.raises(ConflictError):
            apply(exhausted, proposal, expected_budget_sha256="0" * 64)
        return
    apply(exhausted, proposal)
    values = {"approval":{"human_approval_reference":"fixture:different-human-approval"},
              "option":{"monetary_option":"existing_010"}, "ack":{"acknowledged_preflight_sha256":"0" * 64},
              "key":{"idempotency_key":"fixture:different-key"}, "actor":{"actor":"fixture:other-operator"}}
    if change == "preflight":
        changed = deepcopy(proposal); changed["source_commit"] = "9" * 40
        changed["preflight_sha256"] = digest({k:v for k,v in changed.items() if k != "preflight_sha256"})
        values[change] = {"preflight": changed, "acknowledged_preflight_sha256":changed["preflight_sha256"]}
    with pytest.raises(WorkStoreError):
        apply(exhausted, proposal, **values[change])


@pytest.mark.parametrize("change", ["claim", "workflow", "sources", "rules", "binding", "corpus", "model", "price"])
def test_wrong_original_identity_or_config_is_denied_before_reservation(exhausted, proposal, change):
    apply(exhausted, proposal)
    identity = deepcopy(proposal["eligible_originals"][0]["identity"])
    config = deepcopy(proposal["frozen_model_config"])
    keys = {"claim":"claim_id", "workflow":"workflow_id", "sources":"source_roster_sha256", "rules":"rule_set_sha256",
            "binding":"original_binding_sha256", "corpus":"corpus_manifest_sha256"}
    if change in keys:
        identity[keys[change]] = "clm_0000000000000000" if change == "claim" else "0" * 64
    else:
        config["model" if change == "model" else "prompt_price"] = "test/other" if change == "model" else "0.000000126"
    before = exhausted.external_budget()
    with pytest.raises(ConflictError):
        begin(exhausted, proposal, 0, identity=identity, config=config)
    assert exhausted.external_budget() == before


def test_pending_serial_slot_unknown_and_rejection_consume_original_slots(exhausted, proposal):
    apply(exhausted, proposal)
    complete(exhausted, proposal, 0, status="rejected")
    assert exhausted.external_budget()["original_nine_workflows_used"] == 1
    with pytest.raises(ConflictError):
        begin(exhausted, proposal, 0, "verify")
    intent = begin(exhausted, proposal, 1)["intent"]
    with pytest.raises(ReconciliationRequired):
        begin(exhausted, proposal, 1)
    with pytest.raises(ConflictError, match="pending"):
        begin(exhausted, proposal, 2)
    unknown = exhausted.complete_autonomous_call(proposal["eligible_originals"][1]["identity"]["workflow_id"], "interpret",
        intent_sha256=intent["intent_sha256"], status="unknown", result=None, cost_usd=None, metadata={})
    before = exhausted.external_budget()
    assert before["original_nine_workflows_used"] == 2 and before["in_flight"] is True
    assert begin(exhausted, proposal, 1, allow_send=False)["receipt"] == unknown["receipt"]
    with pytest.raises(ConflictError, match="pending"):
        begin(exhausted, proposal, 2)
    assert exhausted.external_budget() == before


def test_existing_dollar_option_stops_truthfully_at_full_workflow_reservation(exhausted, proposal):
    apply(exhausted, proposal, monetary_option="existing_010")
    for index in range(4):
        complete(exhausted, proposal, index)
        complete(exhausted, proposal, index, "verify")
    before = exhausted.external_budget()
    assert before["effective_total_cost_limit_usd"] == "0.10"
    with pytest.raises(ConflictError, match="cost_limit"):
        begin(exhausted, proposal, 4)
    assert exhausted.external_budget() == before


@pytest.mark.parametrize("action", ["UPDATE work_original_nine_grant SET record_sha256='changed'",
                                     "DELETE FROM work_original_nine_grant",
                                     "INSERT OR REPLACE INTO work_original_nine_grant SELECT * FROM work_original_nine_grant"])
def test_grant_immutable_at_sql_boundary(exhausted, proposal, action):
    apply(exhausted, proposal)
    with exhausted.connect() as db, pytest.raises(sqlite3.IntegrityError, match="immutable"):
        db.execute(action)


def test_missing_or_resealed_invalid_prior_epoch_fails_closed(exhausted, proposal):
    apply(exhausted, proposal)
    complete(exhausted, proposal, 0)
    with exhausted.connect() as db:
        db.execute("DROP TRIGGER work_autonomous_outcomes_no_update")
        row = db.execute("SELECT * FROM work_autonomous_outcomes WHERE workflow_id='fixture.workflow.10' AND stage='interpret'").fetchone()
        import json
        value = json.loads(row["record_json"])
        value["metadata"] = {"fixture":"resealed historical rewrite"}
        value["receipt_sha256"] = digest({k:v for k,v in value.items() if k != "receipt_sha256"})
        db.execute("UPDATE work_autonomous_outcomes SET record_json=?,record_sha256=? WHERE workflow_id=? AND stage=?",
                   (canonical(value).decode(),value["receipt_sha256"],row["workflow_id"],row["stage"]))
    with pytest.raises(WorkStoreError):
        exhausted.external_budget()


def test_launcher_readback_partitions_old_and_new_receipt_counters(exhausted, proposal):
    from test_agent_demo_launcher import demo
    apply(exhausted,proposal)
    complete(exhausted,proposal,0)
    complete(exhausted,proposal,0,'verify')
    projected = demo.verified_autonomous_capacity(exhausted.external_budget())
    assert projected['autonomous_grant_workflows_used'] == 3
    assert projected['autonomous_grant_provider_calls_used'] == 6
    assert projected['original_nine_workflows_used'] == 1
    assert projected['original_nine_provider_calls_used'] == 2
    assert projected['original_nine_grant_sha256'] == exhausted.external_budget()['original_nine_grant']['grant_sha256']


def test_changed_stage_schema_is_refused_before_any_new_reservation(exhausted, proposal):
    apply(exhausted,proposal)
    before = exhausted.external_budget()
    with pytest.raises(ConflictError,match='schema'):
        begin(exhausted,proposal,0,schema_sha256='b'*64)
    assert exhausted.external_budget() == before
    complete(exhausted,proposal,0)
    before = exhausted.external_budget()
    with pytest.raises(ConflictError,match='schema'):
        begin(exhausted,proposal,0,'verify',schema_sha256='b'*64)
    assert exhausted.external_budget() == before


def test_prior_epoch_approval_identity_cannot_be_reused(exhausted,proposal):
    prior_key = exhausted.external_budget()['autonomous_capacity_grant']['idempotency_key']
    before = exhausted.external_budget()
    with pytest.raises(ConflictError,match='old epoch'):
        apply(exhausted,proposal,idempotency_key=prior_key)
    assert exhausted.external_budget() == before


def test_resealed_wrong_schema_intent_is_rejected_during_readback(exhausted,proposal):
    import json
    apply(exhausted,proposal)
    begin(exhausted,proposal,0)
    with exhausted.connect() as db:
        db.execute('DROP TRIGGER work_autonomous_calls_no_update')
        workflow = proposal['eligible_originals'][0]['identity']['workflow_id']
        row = db.execute('SELECT * FROM work_autonomous_calls WHERE workflow_id=?',(workflow,)).fetchone()
        value = json.loads(row['record_json']); value['schema_sha256'] = 'b'*64
        value['intent_sha256'] = digest({k:v for k,v in value.items() if k != 'intent_sha256'})
        db.execute('UPDATE work_autonomous_calls SET record_json=?,record_sha256=? WHERE workflow_id=?',
                   (canonical(value).decode(),value['intent_sha256'],workflow))
    with pytest.raises(WorkStoreError):
        exhausted.external_budget()


def test_preserved_legacy_bytes_have_same_seal_under_reversed_sql_traversal(exhausted):
    with exhausted.connect() as db:
        forward = exhausted._original_nine_legacy_seal(db)
        db.execute('PRAGMA reverse_unordered_selects=ON')
        assert exhausted._original_nine_legacy_seal(db) == forward
