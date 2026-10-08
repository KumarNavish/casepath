"""Bounded explicit model work; all transports and credentials here are synthetic."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import json

import httpx
import pytest

from casepath_api.agent_work.contracts import Operation, Role, digest
from casepath_api.agent_work.openrouter import OpenRouterConfig, OpenRouterFactsWorker, choose_model
from casepath_api.agent_work.service import AgentWorkService
from casepath_api.agent_work.store import WorkStore, ConflictError, WorkStoreError

POLICY = {"max_runs": 3, "max_provider_calls": 18, "total_cost_limit_usd": "0.10", "run_cost_limit_usd": "0.02"}


def catalogue(**pricing):
    return {"data": [{"id": "test/reader", "canonical_slug": "test/reader-v1", "context_length": 32768,
        "supported_parameters": ["tools", "tool_choice"], "pricing": {"prompt": "0.0000001", "completion": "0.0000002", "request": "0", **pricing}}]}


def config(**updates):
    return OpenRouterConfig(model="test/reader", canonical_model="test/reader-v1", prompt_price=Decimal("0.0000001"),
        completion_price=Decimal("0.0000002"), catalogue_entry_sha256="a" * 64, **updates)


def run(store, key, claim=None):
    cfg = config()
    request = {"facts_worker": "external_facts", "context": {"subject": "Synthetic"}, "worker_config": cfg.public(),
               "worker_config_sha256": digest(cfg.public())}
    row, _ = store.create(claim or key, key, request, external_limit=3)
    assert store.acquire(row["run_id"], "owner")
    return row["run_id"]


def reserve(store, run_id, call_id="provider.request.1", amount="0.00256"):
    return store.begin_provider_call(run_id, "owner", call_id, "b" * 64, model="test/reader", maximum_cost_usd=amount)


def complete(store, run_id, call_id="provider.request.1", cost=0.001):
    return store.complete_call(run_id, "owner", Role.FACTS, call_id, {"ok": True}, [{
        "role": Role.FACTS, "operation": Operation.PROVIDER_RESPONSE_RECEIVED,
        "object_kind": "provider_response", "object_id": call_id, "status": "completed", "worker_kind": "external",
        "message": "Received provider usage", "after": {"usage": {"cost": cost}}}])


def test_selected_model_is_pinned_and_unknown_surcharges_or_tiers_are_rejected():
    assert choose_model(catalogue(), model="test/reader")["model"] == "test/reader"
    for packet in [catalogue(unknown_surcharge="0.001"), catalogue(tiers=[{"prompt": "1"}]), catalogue(prompt="NaN")]:
        with pytest.raises(Exception, match="compatible|priced|model"):
            choose_model(packet, model="test/reader")
    with pytest.raises(Exception, match="compatible|model"):
        choose_model(catalogue(), model="not/admitted")


def test_durable_policy_cannot_be_replenished_or_increased_on_restart(tmp_path):
    path = tmp_path / "work.sqlite3"
    first = WorkStore(path)
    first.configure_external_budget(POLICY)
    run_id = run(first, "explicit-run-1")
    reserve(first, run_id)
    first.close()
    second = WorkStore(path)
    try:
        second.configure_external_budget(POLICY)
        budget = second.external_budget()
        assert budget["runs_used"] == 1 and budget["provider_calls_used"] == 1
        assert budget["unknown_calls"] == 1 and budget["in_flight"] is True
        assert Decimal(budget["reserved_cost_usd"]) == Decimal("0.02")
        assert budget["can_start"] is False
        with pytest.raises(ConflictError, match="budget"):
            second.configure_external_budget({**POLICY, "max_provider_calls": 17})
    finally:
        second.close()


def test_two_store_instances_admit_one_physical_provider_call(tmp_path):
    path = tmp_path / "work.sqlite3"
    stores = [WorkStore(path), WorkStore(path)]
    stores[0].configure_external_budget(POLICY)
    ids = [run(stores[i], "explicit-run-" + str(i)) for i in range(2)]
    def attempt(index):
        try:
            reserve(stores[index], ids[index])
            return "reserved"
        except ConflictError:
            return "blocked"
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2))) == ["blocked", "reserved"]
    assert stores[0].external_budget()["provider_calls_used"] == 1
    for store in stores: store.close()


def test_known_receipt_releases_slot_but_unknown_cost_stays_reserved(tmp_path):
    store = WorkStore(tmp_path / "work.sqlite3")
    store.configure_external_budget(POLICY)
    first = run(store, "explicit-run-1")
    reserve(store, first)
    complete(store, first, cost=None)
    store.finish(first, "owner", "blocked", "Unpriced response")
    budget = store.external_budget()
    assert budget["in_flight"] is False and budget["unknown_calls"] == 1
    assert Decimal(budget["reserved_cost_usd"]) == Decimal("0.00256")
    second = run(store, "explicit-run-2")
    reserve(store, second)
    assert store.external_budget()["provider_calls_used"] == 2
    store.close()


def test_call_cap_and_run_cap_survive_separate_run_requests(tmp_path):
    store = WorkStore(tmp_path / "work.sqlite3")
    store.configure_external_budget({**POLICY, "max_provider_calls": 1})
    first = run(store, "explicit-run-1")
    reserve(store, first)
    complete(store, first)
    store.finish(first, "owner", "completed", "Done")
    with pytest.raises(ConflictError, match="budget|call"):
        run(store, "explicit-run-2")
    store.close()


def test_unknown_provider_timeout_is_never_retried_or_unreserved(tmp_path):
    store = WorkStore(tmp_path / "work.sqlite3")
    store.configure_external_budget(POLICY)
    run_id = run(store, "explicit-run-1")
    requests = []
    def transport(request):
        requests.append(request)
        raise httpx.ReadTimeout("No confirmed response")
    worker = OpenRouterFactsWorker(config(), "sk-or-synthetic-test", httpx.Client(transport=httpx.MockTransport(transport)))
    from casepath_api.agent_work.runtime import ToolRuntime, WorkBlocked
    runtime = ToolRuntime(store, object(), run_id, "owner", Role.FACTS, "external")
    with pytest.raises(WorkBlocked, match="unconfirmed"):
        worker.run(runtime)
    with pytest.raises(WorkBlocked, match="prior provider"):
        worker.run(runtime)
    assert len(requests) == 1 and len(store.pending_calls(run_id)) == 1
    assert store.external_budget()["unknown_calls"] == 1
    assert "sk-or-synthetic-test" not in json.dumps(store.events(run_id))
    store.close()


def test_applicable_tiers_are_reserved_and_unrequested_features_do_not_add_cost():
    packet = catalogue(web_search="0.01", input_cache_write="0.001", overrides=[
        {"min_prompt_tokens": 100000, "prompt": "1", "completion": "2"},
        {"min_prompt_tokens": 4000, "prompt": "0.0000003", "completion": "0.0000004"}])
    selected = choose_model(packet, model="test/reader")
    assert Decimal(selected["prompt_price"]) == Decimal("0.0000003")
    assert Decimal(selected["completion_price"]) == Decimal("0.0000004")
    for override in [{"min_prompt_tokens": True, "prompt": "1"}, {"min_prompt_tokens": 0, "new_condition": "1"}]:
        with pytest.raises(Exception, match="compatible"):
            choose_model(catalogue(overrides=[override]), model="test/reader")


def test_explicit_start_replays_same_run_and_guard_rejection_spends_nothing(tmp_path):
    class Authority:
        def context(self, claim_id):
            return {"claim_id": claim_id, "subject": "Synthetic", "state_sha256": "c" * 64}
    store = WorkStore(tmp_path / "work.sqlite3")
    store.configure_external_budget(POLICY)
    authority = Authority()
    worker = OpenRouterFactsWorker(config(), "sk-or-synthetic-test")
    service = AgentWorkService(store, authority, facts_worker=worker, max_external_runs=3)
    checked = []
    def guard(claim_id, context):
        checked.append(claim_id)
        if claim_id == "unassigned":
            raise WorkStoreError("An accountable handler is required")
    service.external_start_guard = guard
    try:
        with pytest.raises(WorkStoreError, match="handler"):
            service.start("unassigned", idempotency_key="explicit-unassigned", expected_context_sha256=digest(authority.context("unassigned")), facts_worker="external_facts", dispatch=False)
        assert store.external_budget()["runs_used"] == 0
        context_hash = digest(authority.context("assigned"))
        first = service.start("assigned", idempotency_key="explicit-assigned", expected_context_sha256=context_hash, facts_worker="external_facts", dispatch=False)
        again = service.start("assigned", idempotency_key="explicit-assigned", expected_context_sha256=context_hash, facts_worker="external_facts", dispatch=False)
        assert first == again and store.external_budget()["runs_used"] == 1
        assert first["response_sha256"] == digest({key: value for key,value in first.items() if key != "response_sha256"})
        assert first["summary"]["requested_context_sha256"] == context_hash
        assert first["summary"]["idempotency_key"] == "explicit-assigned"
        assert checked == ["unassigned", "assigned"]
    finally:
        service.shutdown()


def test_whole_run_reservations_enforce_aggregate_limit_before_send(tmp_path):
    store = WorkStore(tmp_path / "work.sqlite3")
    store.configure_external_budget({**POLICY, "total_cost_limit_usd": "0.03"})
    run(store, "explicit-run-1")
    with pytest.raises(ConflictError, match="cost_limit"):
        run(store, "explicit-run-2")
    assert store.external_budget()["provider_calls_used"] == 0
    store.close()


def test_observed_provider_overrun_is_retained_and_stops_further_calls(tmp_path):
    store = WorkStore(tmp_path / "work.sqlite3")
    store.configure_external_budget(POLICY)
    first = run(store, "explicit-run-1")
    reserve(store, first)
    complete(store, first, cost=0.003)
    assert store.external_budget()["reason"] == "provider_cost_bound_exceeded"
    with pytest.raises(ConflictError, match="budget"):
        reserve(store, first, "provider.request.2")
    assert Decimal(store.external_budget()["actual_cost_usd"]) == Decimal("0.003")
    store.close()


class SourceAuthority:
    def __init__(self):
        from hashlib import sha256
        self.text = "Die Kündigung ist eingegangen."
        self.identity = {"binding_sha256": "c" * 64, "source_roster_sha256": "d" * 64}
        self.source = {"claim_id": "source-claim", "source_id": "message", "source_sha256": sha256(self.text.encode()).hexdigest(),
            "text_sha256": sha256(self.text.encode()).hexdigest(), "text": self.text, "extraction": "message_body",
            "complete": True, "filename": "message.txt", "media_type": "message/rfc822", "role": "customer_message"}
    def context(self, claim_id):
        return {"claim_id": claim_id, "subject": "Synthetic source review", **self.identity}
    def packet_identity(self, claim_id):
        return self.identity
    def list_sources(self, claim_id):
        return [self.source]
    def read_source(self, claim_id, source_id):
        assert claim_id == "source-claim" and source_id == "message"
        return self.source


def test_mocked_model_uses_real_source_gates_and_never_records_private_reasoning(tmp_path):
    from casepath_api.agent_work.runtime import ToolRuntime
    authority = SourceAuthority()
    store = WorkStore(tmp_path / "work.sqlite3")
    store.configure_external_budget(POLICY)
    cfg = config(reasoning_supported=True)
    request = {"facts_worker": "external_facts", "context": authority.context("source-claim"),
               "worker_config": cfg.public(), "worker_config_sha256": digest(cfg.public())}
    current, _ = store.create("source-claim", "explicit-source-review", request, external_limit=3)
    run_id = current["run_id"]
    assert store.acquire(run_id, "owner")
    private = "PRIVATE_PROVIDER_REASONING_MUST_NOT_PERSIST"
    seen = []
    def transport(outbound):
        payload = json.loads(outbound.content)
        seen.append(payload)
        assert payload["model"] == "test/reader" and payload["stream"] is False
        assert payload["reasoning"] == {"enabled": False, "exclude": True}
        assert payload["provider"]["allow_fallbacks"] is False
        assert payload["provider"]["data_collection"] == "deny"
        assert "cache_control" not in json.dumps(payload) and "plugins" not in payload
        assert private not in json.dumps(payload)
        if len(seen) == 1:
            functions = [("list_sources", {}), ("read_customer_message", {})]
        elif len(seen) == 2:
            functions = [("select_source_span", {"source_id": "message", "start": 0, "end": len(authority.text), "quote": authority.text})]
        else:
            selected = json.loads(payload["messages"][-1]["content"])["result"]
            functions = [("propose_assertion", {"assertion_id": "notice", "span_id": selected["span_id"], "text": authority.text}), ("finish_work", {})]
        calls = [{"id": f"call-{len(seen)}-{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}} for i, (name,args) in enumerate(functions)]
        return httpx.Response(200, json={"id": "generation-"+str(len(seen)), "model": "test/reader-v1",
            "choices": [{"finish_reason": "tool_calls", "message": {"content": private, "reasoning": private, "tool_calls": calls}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120, "cost": 0.00001}})
    client = httpx.Client(transport=httpx.MockTransport(transport))
    OpenRouterFactsWorker(cfg, "sk-or-synthetic-test", client).run(ToolRuntime(store, authority, run_id, "owner", Role.FACTS, "external"))
    snapshot = store.snapshot(run_id)
    assert len(seen) == 3 and snapshot["pending_calls"] == []
    assertion = next(o["value"] for o in snapshot["objects"] if o["kind"] == "assertion")
    assert assertion["text"] == authority.text and assertion["status"] == "reported"
    assert assertion["source"]["scope"] == "source_statement_not_established_fact"
    assert any(e["operation"] == "AGENT_COMPLETED" for e in snapshot["events"])
    assert private not in json.dumps(snapshot) and "sk-or-synthetic-test" not in json.dumps(snapshot)
    client.close(); store.close()


@pytest.mark.parametrize("kind", ["different-model", "no-tools", "oversized", "duplicate-json", "unavailable-tool"])
def test_invalid_provider_envelopes_never_produce_work_or_retry(tmp_path, kind):
    from casepath_api.agent_work.runtime import ToolRuntime, WorkBlocked
    store = WorkStore(tmp_path / "work.sqlite3")
    store.configure_external_budget(POLICY)
    run_id = run(store, "explicit-invalid-response")
    calls = []
    def transport(request):
        calls.append(request)
        if kind == "oversized": return httpx.Response(200, content=b"x" * 128001)
        arguments = '{"a":1,"a":2}' if kind == "duplicate-json" else '{}'
        tools = [] if kind == "no-tools" else [{"id": "call", "type": "function", "function": {
            "name": "execute_shell" if kind == "unavailable-tool" else "list_sources", "arguments": arguments}}]
        return httpx.Response(200, json={"model": "other/model" if kind == "different-model" else "test/reader", "choices": [{"message": {"tool_calls": tools}}]})
    client = httpx.Client(transport=httpx.MockTransport(transport))
    worker = OpenRouterFactsWorker(config(), "sk-or-synthetic-test", client)
    with pytest.raises(WorkBlocked):
        worker.run(ToolRuntime(store, object(), run_id, "owner", Role.FACTS, "external"))
    assert len(calls) == 1 and store.snapshot(run_id)["objects"] == []
    assert store.external_budget()["unknown_calls"] == 1
    assert len(store.pending_calls(run_id)) == 1
    client.close(); store.close()


def test_context_bound_stops_request_before_send(tmp_path):
    from casepath_api.agent_work.runtime import ToolRuntime, WorkBlocked
    store = WorkStore(tmp_path / "work.sqlite3")
    cfg = config(context_length=8192, max_request_bytes=24000)
    run_id = run(store, "explicit-context-bound")
    runtime = ToolRuntime(store, object(), run_id, "owner", Role.FACTS, "external")
    runtime.claim_id = "x" * 10000
    client = httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail("context overflow sent a request")))
    with pytest.raises(WorkBlocked, match="context"):
        OpenRouterFactsWorker(cfg, "sk-or-synthetic-test", client).run(runtime)
    assert store.pending_calls(run_id) == []
    client.close(); store.close()


def test_external_start_cannot_jump_over_an_unresolved_local_claim_effect(tmp_path):
    store = WorkStore(tmp_path / "work.sqlite3")
    previous, _ = store.create("same-claim", "previous-local-review", {"facts_worker": "reference"})
    assert store.acquire(previous["run_id"], "old-owner")
    store.begin_call(previous["run_id"], "old-owner", Role.PROCESS, "local-effect", "prepare_handling_process", {})
    store.finish(previous["run_id"], "old-owner", "blocked", "Outcome unknown")
    with pytest.raises(ConflictError, match="unfinished|unresolved"):
        run(store, "explicit-external-review", claim="same-claim")
    assert len(store.list_runs("same-claim")) == 1
    store.close()


def test_external_stop_retains_inflight_request_and_blocks_next_send(tmp_path):
    from casepath_api.agent_work.store import WorkCancelled
    store = WorkStore(tmp_path / "work.sqlite3")
    store.configure_external_budget(POLICY)
    run_id = run(store, "explicit-stop-review")
    reserve(store, run_id)
    store.request_cancel(run_id)
    before = store.events(run_id)
    store.request_cancel(run_id)
    assert store.events(run_id) == before
    assert len(store.pending_calls(run_id)) == 1 and store.get_run(run_id)["status"] == "running"
    complete(store, run_id)
    with pytest.raises(WorkCancelled):
        reserve(store, run_id, "provider.request.2")
    store.finish(run_id, "owner", "cancelled", "Stopped after provider response")
    assert store.get_run(run_id)["status"] == "cancelled"
    assert store.pending_calls(run_id) == [] and store.external_budget()["provider_calls_used"] == 1
    store.close()


def test_external_stop_after_unknown_outcome_never_clears_pending_receipt(tmp_path):
    store = WorkStore(tmp_path / "work.sqlite3")
    store.configure_external_budget(POLICY)
    run_id = run(store, "explicit-unknown-stop")
    reserve(store, run_id)
    store.finish(run_id, "owner", "interrupted", "No confirmed outcome")
    store.request_cancel(run_id)
    assert len(store.pending_calls(run_id)) == 1
    assert store.external_budget()["unknown_calls"] == 1
    assert store.external_budget()["can_start"] is False
    store.close()


def test_external_stop_racing_completed_run_is_a_safe_noop(tmp_path):
    store = WorkStore(tmp_path / "work.sqlite3")
    run_id = run(store, "explicit-completed-stop")
    store.finish(run_id, "owner", "completed", "Already completed")
    before = store.snapshot(run_id)
    store.request_cancel(run_id)
    assert store.snapshot(run_id) == before
    store.close()


def configure_demo_env(monkeypatch, tmp_path):
    from datetime import datetime, timezone
    packet = catalogue()
    path = tmp_path / "catalogue.json"
    path.write_text(json.dumps({"fetched_at": datetime.now(timezone.utc).isoformat(), "catalogue": packet, "catalogue_sha256": digest(packet)}))
    for key, value in {
        "CASEPATH_AGENT_WORK_EXTERNAL_FACTS": "1", "CASEPATH_AGENT_WORK_DEMO": "1", "CASEPATH_AGENT_WORK_MODEL": "test/reader",
        "CASEPATH_AGENT_WORK_CATALOGUE": str(path), "CASEPATH_AGENT_WORK_MAX_EXTERNAL_RUNS": "3",
        "CASEPATH_AGENT_WORK_MAX_PROVIDER_CALLS": "18", "CASEPATH_AGENT_WORK_TOTAL_COST_USD": "0.10",
        "CASEPATH_AGENT_WORK_RUN_COST_USD": "0.02", "OPENROUTER_API_KEY": "sk-or-synthetic-test"}.items():
        monkeypatch.setenv(key,value)
    return path


def test_installed_demo_requires_owner_and_respects_paused_delegate_without_calls(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from fastapi import FastAPI
    from casepath_api.agent_work.install import install_agent_work
    from casepath_api.agent_desk_v1 import DelegateJournal
    configure_demo_env(monkeypatch, tmp_path)
    monkeypatch.setattr(httpx.Client, "post", lambda *_args, **_kwargs: pytest.fail("configuration made an inference call"))
    current = {"owner": None, "state_sha256": "c" * 64}
    workspace = SimpleNamespace(store=SimpleNamespace(recover=lambda _claim: current, journal=object()))
    service = install_agent_work(FastAPI(), lambda: workspace, lambda: object(), tmp_path / "work.sqlite3")()
    service.authority = SimpleNamespace(context=lambda claim: {"claim_id": claim, "state_sha256": "c" * 64, "subject": "Synthetic"})
    paused = [False]
    monkeypatch.setattr(DelegateJournal, "state", lambda *_: {"paused": paused[0]})
    try:
        cap = service.capabilities()
        assert cap["external_configuration_status"] == "ready" and cap["external"]["model"] == "test/reader"
        assert cap["external_budget"]["runs_used"] == 0 and cap["external_budget"]["can_start"] is True
        context_hash = digest(service.authority.context("claim"))
        with pytest.raises(WorkStoreError, match="handler"):
            service.start("claim", idempotency_key="owner-guard-attempt", expected_context_sha256=context_hash, facts_worker="external_facts", dispatch=False)
        current["owner"] = "Reviewer"
        paused[0] = True
        with pytest.raises(WorkStoreError, match="paused"):
            service.start("claim", idempotency_key="owner-guard-attempt", expected_context_sha256=context_hash, facts_worker="external_facts", dispatch=False)
        assert service.capabilities()["external_budget"]["runs_used"] == 0
        paused[0] = False
        accepted = service.start("claim", idempotency_key="owner-guard-attempt", expected_context_sha256=context_hash, facts_worker="external_facts", dispatch=False)
        assert accepted["summary"]["status"] == "queued"
        assert service.capabilities()["external_budget"]["runs_used"] == 1
    finally:
        service.shutdown()


@pytest.mark.parametrize("damage", ["over-budget", "missing-model", "wrong-catalogue-hash", "stale-catalogue"])
def test_demo_configuration_failure_never_silently_selects_reference(tmp_path, monkeypatch, damage):
    from fastapi import FastAPI
    from casepath_api.agent_work.install import install_agent_work
    path = configure_demo_env(monkeypatch, tmp_path)
    if damage == "over-budget": monkeypatch.setenv("CASEPATH_AGENT_WORK_TOTAL_COST_USD", "0.11")
    elif damage == "missing-model": monkeypatch.delenv("CASEPATH_AGENT_WORK_MODEL")
    else:
        packet = json.loads(path.read_text())
        if damage == "wrong-catalogue-hash": packet["catalogue_sha256"] = "a" * 64
        else: packet["fetched_at"] = "2000-01-01T00:00:00+00:00"
        path.write_text(json.dumps(packet))
    service = install_agent_work(FastAPI(), lambda: object(), lambda: object(), tmp_path / "work.sqlite3")()
    try:
        cap = service.capabilities()
        assert cap["external_configuration_status"] == "rejected" and cap["facts_workers"] == ["reference"]
        assert cap["external"] is None
        with pytest.raises(WorkStoreError, match="not configured"):
            service.start("claim", idempotency_key="invalid-external-attempt", expected_context_sha256="a"*64, facts_worker="external_facts", dispatch=False)
        assert service.store.list_runs() == []
    finally:
        service.shutdown()


def test_default_install_remains_provider_free_even_with_a_credential(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from casepath_api.agent_work.install import install_agent_work
    monkeypatch.delenv("CASEPATH_AGENT_WORK_EXTERNAL_FACTS", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-synthetic-test")
    service = install_agent_work(FastAPI(), lambda: object(), lambda: object(), tmp_path / "work.sqlite3")()
    try:
        assert service.capabilities()["external_configuration_status"] == "disabled"
        assert service.capabilities()["external"] is None
        assert service.capabilities()["external_budget"] is None
    finally:
        service.shutdown()
