from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import casepath_api.app as app_module
from casepath_api.canonicalizer import (
    MODEL_MODE_OPENROUTER,
    MODEL_MODE_REFERENCE,
    OPENROUTER_MODEL,
    ModelResponseError,
)
from casepath_api.multi_agent import MULTI_AGENT_VERSION
from casepath_api.pipeline_v15 import COMPONENT_VERSIONS, PROFILE, ClaimPipeline, digest
from casepath_api.storage import ActiveRunResetError, Storage

SESSION_A = "session-a-12345678"
SESSION_B = "session-b-12345678"


def headers(session_id: str = SESSION_A) -> dict[str, str]:
    return {"X-CasePath-Session": session_id}


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    storage = Storage(str(tmp_path / "api.db"))
    pipeline = ClaimPipeline(storage, pace_seconds=0)
    held_out_pipeline = ClaimPipeline(
        storage,
        model_mode=MODEL_MODE_REFERENCE,
        pace_seconds=0,
    )
    monkeypatch.setattr(app_module, "storage", storage)
    monkeypatch.setattr(app_module, "pipeline", pipeline)
    monkeypatch.setattr(app_module, "held_out_pipeline", held_out_pipeline)
    return TestClient(app_module.app)


def test_local_product_static_responses_are_never_reused_from_cache(
    tmp_path: Path,
) -> None:
    (tmp_path / "index.html").write_text("<!doctype html><p>local</p>")
    local_app = FastAPI()
    local_app.mount(
        "/",
        app_module._LocalNoStoreStaticFiles(
            directory=str(tmp_path), html=True, check_dir=True
        ),
    )
    response = TestClient(local_app).get("/")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.headers["pragma"] == "no-cache"


def wait(client: TestClient, run_id: str, *, session_id: str = SESSION_A) -> dict:
    for _ in range(500):
        response = client.get(f"/api/runs/{run_id}", headers=headers(session_id))
        assert response.status_code == 200
        run = response.json()
        if run["status"] in {"complete", "failed"}:
            return run
        time.sleep(0.01)
    raise AssertionError("run timeout")


def create_and_wait(
    client: TestClient,
    claim_id: str,
    *,
    knowledge_mode: str = "current",
    session_id: str = SESSION_A,
) -> dict:
    response = client.post(
        "/api/runs",
        json={"claim_id": claim_id, "knowledge_mode": knowledge_mode},
        headers=headers(session_id),
    )
    assert response.status_code == 202, response.text
    assert response.json()["knowledge_mode"] == knowledge_mode
    return wait(client, response.json()["run_id"], session_id=session_id)


@pytest.mark.parametrize(
    "origin",
    [
        "https://casepath.onrender.com",
        "https://casepath-swiss-claim-lab.onrender.com",
    ],
)
def test_production_frontend_origins_pass_cors_preflight(
    client: TestClient,
    origin: str,
) -> None:
    response = client.options(
        "/api/demo",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-CasePath-Session",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


def test_health_and_release_metadata_expose_semantic_identity(client: TestClient, monkeypatch):
    source_commit = "a" * 40
    monkeypatch.delenv("RENDER_GIT_COMMIT", raising=False)
    monkeypatch.setenv("CASEPATH_SOURCE_COMMIT", source_commit)
    health = client.get("/healthz")
    assert health.status_code == 200
    value = health.json()
    assert value["release"] == "15.2.0"
    assert value["release_id"] == "casepath-v20-reference-20260811"
    assert value["pipeline_release"] == "15.2.0"
    assert value["source_commit"] == source_commit
    assert value["source_commit_source"] == "casepath_source_commit_fallback"
    assert value["source_commit_aligned"] is True
    assert value["source_commit_conflict"] is False
    assert value["model_mode"] == "deterministic_reference"
    assert value["model"] is None
    assert value["profile"] == "deterministic-reference-playbook"
    assert value["runtime_profile"] == "deterministic_reference"
    assert value["agentic_runtime"]["compiled_profile"] == (
        "nemotron_langgraph_multi_agent_hybrid_guarded"
    )
    assert value["agentic_runtime"]["profile_aligned"] is True
    assert value["agentic_runtime"]["safety"]["ledger_persistence"] == (
        "ephemeral_instance"
    )
    assert value["agentic_runtime"]["safety"]["provider_max_in_flight"] == 1
    assert value["configured_model_identity"] == OPENROUTER_MODEL
    assert value["components"] == COMPONENT_VERSIONS
    assert value["components"]["agent_graph"] == MULTI_AGENT_VERSION
    deployment = client.get("/deployment-health").json()
    assert deployment["source_commit"] == source_commit
    assert deployment["api_release"] == "15.2.0"
    assert deployment["release_id"] == "casepath-v20-reference-20260811"
    assert deployment["frontend_contract"] == "focused-claim-workspace-v20"
    demo = client.get("/api/demo", headers=headers()).json()
    assert demo["release_id"] == "casepath-v20-reference-20260811"
    ready = client.get("/readyz").json()
    assert ready["agentic_runtime"]["safety"]["provider_max_in_flight"] == 1
    assert ready["model_budget"]["cumulative_usd_cap"] == 25.0
    assert ready["model_budget"]["network_calls"] == 0
    assert ready["model_budget"]["actual_cost_complete"] is True
    assert ready["model_budget"]["unknown_cost_call_count"] == 0
    assert ready["model_budget"]["budget_scope"] == "instance_lifetime"
    assert ready["model_budget"]["ledger_persistence"] == "ephemeral_instance"


def test_model_ready_requires_exact_runtime_profile_and_secret_presence(
    client: TestClient, monkeypatch
):
    monkeypatch.setattr(app_module.pipeline, "model_mode", "openrouter_nemotron")
    monkeypatch.setenv(
        "CASEPATH_AGENT_RUNTIME_PROFILE",
        "nemotron_langgraph_multi_agent_hybrid_guarded",
    )
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    missing = client.get("/readyz")
    assert missing.status_code == 503
    assert missing.json()["status"] == "not_ready"
    assert missing.json()["model_budget"]["credential_configured"] is False
    assert "OPENROUTER_API_KEY" not in missing.text

    monkeypatch.setenv("OPENROUTER_API_KEY", "runtime-only-test-value")
    ready = client.get("/readyz")
    assert ready.status_code == 200
    assert ready.json()["agentic_runtime"]["profile_aligned"] is True
    assert ready.json()["agentic_runtime"]["safety"]["credential_configured"] is True
    health = client.get("/healthz").json()
    assert health["agentic_runtime"]["safety"]["provider_routing"] == {
        "endpoint_tag": "together",
        "expected_upstream_provider": "Together",
        "allow_fallbacks": False,
        "require_parameters": True,
        "data_collection": "deny",
    }
    assert "runtime-only-test-value" not in ready.text

    monkeypatch.setenv("CASEPATH_AGENT_RUNTIME_PROFILE", "wrong-runtime")
    mismatch = client.get("/readyz")
    assert mismatch.status_code == 503
    assert mismatch.json()["agentic_runtime"]["profile_aligned"] is False
    assert mismatch.json()["agentic_runtime"]["configured_profile"] == "wrong-runtime"


def test_environment_selected_model_mode_rejects_mismatched_compiled_profile(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setenv("CASEPATH_MODEL_MODE", "openrouter_nemotron")
    monkeypatch.setenv("CASEPATH_AGENT_RUNTIME_PROFILE", "wrong-runtime")
    with pytest.raises(ValueError, match="compiled LangGraph runtime"):
        ClaimPipeline(Storage(str(tmp_path / "profile.db")), pace_seconds=0)


@pytest.mark.parametrize(
    "trace_variable",
    ["LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2", "LANGCHAIN_TRACING"],
)
def test_model_ready_rejects_every_external_trace_alias(
    client: TestClient, monkeypatch, trace_variable: str
):
    monkeypatch.setattr(app_module.pipeline, "model_mode", "openrouter_nemotron")
    monkeypatch.setenv(
        "CASEPATH_AGENT_RUNTIME_PROFILE",
        "nemotron_langgraph_multi_agent_hybrid_guarded",
    )
    monkeypatch.setenv("OPENROUTER_API_KEY", "runtime-only-test-value")
    for name in ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2", "LANGCHAIN_TRACING"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(trace_variable, "true")
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["agentic_runtime"]["trace_policy_aligned"] is False


def test_render_commit_is_authoritative_and_conflicts_fail_alignment(client: TestClient, monkeypatch):
    render_commit = "b" * 40
    custom_commit = "c" * 40
    monkeypatch.setenv("RENDER_GIT_COMMIT", render_commit)
    monkeypatch.setenv("CASEPATH_SOURCE_COMMIT", custom_commit)
    value = client.get("/healthz").json()
    assert value["source_commit"] == render_commit
    assert value["source_commit_source"] == "render_git_commit"
    assert value["source_commit_aligned"] is False
    assert value["source_commit_conflict"] is True


def test_run_and_review_requests_are_typed_and_reject_unknown_values(client: TestClient):
    invalid_run = client.post(
        "/api/runs",
        json={"claim_id": "DEF-027-E0-DEMO", "knowledge_mode": "promoted"},
        headers=headers(),
    )
    assert invalid_run.status_code == 422
    run = create_and_wait(client, "DEF-027-E0-DEMO")
    invalid_review = client.post(
        f"/api/runs/{run['run_id']}/review",
        json={"decision": "approve_as_expert", "building_envelope_mode": "conditional"},
        headers=headers(),
    )
    assert invalid_review.status_code == 422
    rejected = client.post(
        f"/api/runs/{run['run_id']}/review",
        json={
            "decision": "reject",
            "building_envelope_mode": "conditional",
            "confidence": 0.3,
            "justification": "No generated-demo edit accepted.",
        },
        headers=headers(),
    )
    assert rejected.status_code == 200
    assert rejected.json()["accepted"] is False
    assert rejected.json()["memory_id"] is None
    assert client.get("/api/knowledge", headers=headers()).json()["memories"] == []


def test_learning_proof_requires_explicit_bound_run_ids(client: TestClient):
    assert client.get("/api/learning-proof", headers=headers()).status_code == 422
    flagship = create_and_wait(client, "DEF-027-E0-DEMO")
    review = client.post(
        f"/api/runs/{flagship['run_id']}/review",
        json={
            "decision": "approve_with_edit",
            "building_envelope_mode": "conditional",
            "confidence": 0.9,
            "justification": "Generated-demo edit, not qualified review.",
        },
        headers=headers(),
    )
    assert review.status_code == 200, review.text
    baseline = create_and_wait(client, "DEMO-MOULD-002", knowledge_mode="baseline")
    later = create_and_wait(client, "DEMO-MOULD-002", knowledge_mode="current")
    proof = client.get(
        "/api/learning-proof",
        params={"baseline_run_id": baseline["run_id"], "later_run_id": later["run_id"]},
        headers=headers(),
    )
    assert proof.status_code == 200, proof.text
    value = proof.json()
    assert value["reviewed_memory_proof"]["used"] is True
    assert value["shared_rule"]["applied"] is False
    assert value["shared_rule"]["version_after"] == "mould-playbook-v3"


def test_held_out_routing_is_zero_model_and_preserves_cross_pipeline_learning(
    tmp_path: Path,
    monkeypatch,
):
    class ExplodingCanonicalizer:
        def __init__(self) -> None:
            self.calls = 0

        def canonicalize(self, *args, **kwargs):
            self.calls += 1
            raise ModelResponseError(
                "The model provider must not be called by a held-out run",
                invariant="test_exploding_provider",
            )

    class ExplodingAgentOrchestrator:
        def __init__(self) -> None:
            self.calls = 0

        def invoke(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError(
                "The agent provider must not be called by a held-out run"
            )

    storage = Storage(str(tmp_path / "held-out-routing.db"))
    exploding_canonicalizer = ExplodingCanonicalizer()
    exploding_orchestrator = ExplodingAgentOrchestrator()
    flagship_pipeline = ClaimPipeline(
        storage,
        model_mode=MODEL_MODE_OPENROUTER,
        canonicalizer=exploding_canonicalizer,
        agent_orchestrator=exploding_orchestrator,
        pace_seconds=0,
    )
    held_out_pipeline = ClaimPipeline(
        storage,
        model_mode=MODEL_MODE_REFERENCE,
        pace_seconds=0,
    )
    source_pipeline = ClaimPipeline(
        storage,
        model_mode=MODEL_MODE_REFERENCE,
        pace_seconds=0,
    )
    monkeypatch.setattr(app_module, "storage", storage)
    monkeypatch.setattr(app_module, "pipeline", flagship_pipeline)
    monkeypatch.setattr(app_module, "held_out_pipeline", held_out_pipeline)
    client = TestClient(app_module.app)

    assert app_module.run_pipeline_for_claim("DEF-027-E0-DEMO") is flagship_pipeline
    assert app_module.run_pipeline_for_claim("DEMO-MOULD-002") is held_out_pipeline
    assert app_module.run_pipeline_for_claim("DEMO-MOULD-002-shadow") is flagship_pipeline

    source_run_id = source_pipeline.create(
        "DEF-027-E0-DEMO",
        session_id=SESSION_A,
    )
    source = wait(client, source_run_id)
    assert source["status"] == "complete"
    review = client.post(
        f"/api/runs/{source_run_id}/review",
        json={
            "decision": "approve_with_edit",
            "building_envelope_mode": "conditional",
            "confidence": 0.9,
            "justification": "Generated-demo edit, not qualified review.",
        },
        headers=headers(),
    )
    assert review.status_code == 200, review.text

    ledger_before = storage.sanitized_model_ledger()
    summary_before = storage.model_call_summary()
    baseline_response = client.post(
        "/api/runs",
        json={"claim_id": "DEMO-MOULD-002", "knowledge_mode": "baseline"},
        headers=headers(),
    )
    assert baseline_response.status_code == 202, baseline_response.text
    assert baseline_response.json()["model_mode"] == MODEL_MODE_REFERENCE
    baseline = wait(client, baseline_response.json()["run_id"])
    later_response = client.post(
        "/api/runs",
        json={"claim_id": "DEMO-MOULD-002", "knowledge_mode": "current"},
        headers=headers(),
    )
    assert later_response.status_code == 202, later_response.text
    assert later_response.json()["model_mode"] == MODEL_MODE_REFERENCE
    later = wait(client, later_response.json()["run_id"])

    expected_orchestration = {
        "executed": False,
        "authority_mode": MODEL_MODE_REFERENCE,
        "model": None,
        "external_tracing": False,
        "deterministic_safety_authority": True,
    }
    expected_canonicalization = {
        "implementation": "deterministic_reference_oracle",
        "model": None,
        "provider": None,
        "mode": MODEL_MODE_REFERENCE,
    }
    for run in (baseline, later):
        assert run["status"] == "complete"
        assert run["model_mode"] == MODEL_MODE_REFERENCE
        assert run["model"] is None
        assert run["agent_orchestration"] == expected_orchestration
        assert run["result"]["agent_orchestration"] == expected_orchestration
        assert run["result"]["audit"]["agent_orchestration"] == expected_orchestration
        assert run["result"]["audit"]["canonicalization"] == expected_canonicalization
        assert run["result"]["audit"]["authority_mode"] == MODEL_MODE_REFERENCE
        assert all(event.get("actor_type") != "nemotron_agent" for event in run["events"])
        assert all(event.get("model") is None for event in run["events"])
        assert all(
            not ({"call_id", "response_id", "cache_hit", "call_count"} & set(event))
            for event in run["events"]
        )

    assert baseline["result"]["memory_application"] is None
    assert later["result"]["memory_application"]["model_acceptance_reused"] is False
    assert exploding_canonicalizer.calls == 0
    assert exploding_orchestrator.calls == 0
    assert storage.sanitized_model_ledger() == ledger_before
    assert storage.model_call_summary() == summary_before

    proof = client.get(
        "/api/learning-proof",
        params={
            "baseline_run_id": baseline["run_id"],
            "later_run_id": later["run_id"],
        },
        headers=headers(),
    )
    assert proof.status_code == 200, proof.text
    proof_value = proof.json()
    assert proof_value["ready"] is True
    assert proof_value["computed"] is True
    assert len(proof_value["deterministic_checks"]) == 10
    assert {value["status"] for value in proof_value["deterministic_checks"]} == {
        "passed"
    }
    assert proof_value["reviewed_memory_proof"]["used"] is True
    assert isinstance(
        proof_value["memory_application_proof"]["application_hash"],
        str,
    )
    for field in (
        "receipt_present",
        "receipt_valid",
        "source_memory_current",
        "before_hashes_match",
        "after_hashes_match",
        "allowed_delta_exact",
        "replay_exact",
    ):
        assert proof_value["memory_application_proof"][field] is True
    assert storage.sanitized_model_ledger() == ledger_before
    assert storage.model_call_summary() == summary_before

    client_controlled_mode = client.post(
        "/api/runs",
        json={
            "claim_id": "DEMO-MOULD-002",
            "knowledge_mode": "baseline",
            "model_mode": MODEL_MODE_OPENROUTER,
        },
        headers=headers(),
    )
    assert client_controlled_mode.status_code == 422

    flagship_response = client.post(
        "/api/runs",
        json={"claim_id": "DEF-027-E0-DEMO", "knowledge_mode": "baseline"},
        headers=headers(),
    )
    assert flagship_response.status_code == 202, flagship_response.text
    assert flagship_response.json()["model_mode"] == MODEL_MODE_OPENROUTER
    assert flagship_response.json()["profile"] == PROFILE
    failed_flagship = wait(client, flagship_response.json()["run_id"])
    assert failed_flagship["status"] == "failed"
    assert failed_flagship["failure_stage"] == "deterministic_failure_boundary"
    assert exploding_canonicalizer.calls == 1
    assert exploding_orchestrator.calls == 0


def test_public_knowledge_projects_private_review_state(client: TestClient):
    sentinel = "PRIVATE_REVIEW_NOTE account=internal-only"
    run = create_and_wait(client, "DEF-027-E0-DEMO")
    review = client.post(
        f"/api/runs/{run['run_id']}/review",
        json={
            "decision": "approve_with_edit",
            "building_envelope_mode": "conditional",
            "confidence": 0.9,
            "justification": sentinel,
        },
        headers=headers(),
    )
    assert review.status_code == 200, review.text

    knowledge = client.get("/api/knowledge", headers=headers()).json()
    demo_knowledge = client.get("/api/demo", headers=headers()).json()["knowledge"]
    for public_value in (knowledge, demo_knowledge):
        serialized = str(public_value)
        assert sentinel not in serialized
        assert "canonical_facts" not in serialized
        assert "reviewed_process" not in serialized
        assert "reviewed_checklist" not in serialized
        assert "reviewer_explanation" not in serialized
        assert set(public_value["memories"][0]) == {
            "memory_id",
            "title",
            "memory_contract",
            "authority",
            "scope",
            "review_status",
            "reviewer_qualification_status",
            "category",
            "playbook_version",
            "shared_rule_authority",
            "candidate_id",
            "guidance",
            "updated_at",
        }

    assert sentinel in str(app_module.storage.memories(session_id=SESSION_A)[0])


@pytest.mark.parametrize("target", ["memory", "candidate"])
def test_public_knowledge_fails_closed_on_rehashed_authority_forgery(
    client: TestClient, target
):
    run = create_and_wait(client, "DEF-027-E0-DEMO")
    review = client.post(
        f"/api/runs/{run['run_id']}/review",
        json={
            "decision": "approve_with_edit",
            "building_envelope_mode": "conditional",
            "confidence": 0.9,
            "justification": "Generated-demo edit only.",
        },
        headers=headers(),
    )
    assert review.status_code == 200, review.text

    with app_module.storage.connect() as connection:
        if target == "memory":
            row = connection.execute(
                "SELECT memory_id, payload FROM memories WHERE session_id=?",
                (SESSION_A,),
            ).fetchone()
            payload = json.loads(row["payload"])
            payload["authority"] = "qualified_expert"
            payload["review_status"] = "qualified_expert_reviewed"
            payload["reviewer"]["qualification_status"] = "verified"
            payload["content_hash"] = digest(
                {
                    key: value
                    for key, value in payload.items()
                    if key
                    not in {"content_hash", "memory_id", "claim_id", "updated_at"}
                }
            )
            connection.execute(
                "UPDATE memories SET payload=? WHERE memory_id=?",
                (json.dumps(payload), row["memory_id"]),
            )
        else:
            row = connection.execute(
                "SELECT candidate_id, payload FROM candidates WHERE session_id=?",
                (SESSION_A,),
            ).fetchone()
            payload = json.loads(row["payload"])
            payload["status"] = "approved"
            payload["qualified_support_count"] = 99
            payload["approval"] = {
                "status": "approved",
                "qualified_reviewer": True,
            }
            payload["shared_knowledge_changed"] = True
            connection.execute(
                "UPDATE candidates SET payload=? WHERE candidate_id=?",
                (json.dumps(payload), row["candidate_id"]),
            )

    for path in ("/api/knowledge", "/api/demo"):
        response = client.get(path, headers=headers())
        assert response.status_code == 409
        assert response.json() == {"detail": "knowledge integrity boundary"}
        assert "qualified_expert" not in response.text
        assert "approved" not in response.text


def test_public_artifact_extraction_does_not_expose_reference_fact_ids(client: TestClient):
    value = client.get("/api/artifacts/art_lease/extraction")
    assert value.status_code == 200
    assert "facts" not in value.json()
    assert "fact_ids" not in value.json()
    claim = client.get("/api/claims/DEF-027-E0-DEMO").json()
    assert claim["generated"] is True
    assert claim["lineage"] == "DEF-027-E0"
    assert all("fact_ids" not in artifact for artifact in claim["artifacts"])
    assert all("description" in artifact for artifact in claim["artifacts"])


def test_mutation_and_session_state_endpoints_require_valid_session(client: TestClient):
    assert client.post("/api/runs", json={"claim_id": "DEF-027-E0-DEMO"}).status_code == 400
    assert client.get("/api/demo").status_code == 400
    assert client.get("/api/knowledge").status_code == 400
    assert client.post("/api/demo/reset").status_code == 400
    assert client.get("/api/knowledge", headers=headers("short")).status_code == 400
    assert client.get("/api/claims").status_code == 200
    assert client.get("/api/model-ledger").status_code == 200


def test_two_sessions_are_isolated_and_reset_preserves_other_session_and_global_ledger(client: TestClient):
    run_a = create_and_wait(client, "DEF-027-E0-DEMO", session_id=SESSION_A)
    run_b = create_and_wait(client, "DEMO-MOULD-002", session_id=SESSION_B)
    assert client.get(f"/api/runs/{run_a['run_id']}", headers=headers(SESSION_B)).status_code == 404
    assert client.get(f"/api/runs/{run_b['run_id']}", headers=headers(SESSION_A)).status_code == 404

    review = client.post(
        f"/api/runs/{run_a['run_id']}/review",
        headers=headers(SESSION_A),
        json={
            "decision": "approve_with_edit",
            "building_envelope_mode": "conditional",
            "confidence": 0.9,
            "justification": "Session-isolation generated-demo review.",
        },
    )
    assert review.status_code == 200
    assert len(client.get("/api/knowledge", headers=headers(SESSION_A)).json()["memories"]) == 1
    assert client.get("/api/knowledge", headers=headers(SESSION_B)).json()["memories"] == []

    call_id = app_module.storage.create_model_call(
        run_id=run_a["run_id"],
        provider="openrouter",
        model=OPENROUTER_MODEL,
        cache_key="global-cache",
        purpose="isolation-test",
        call_count=0,
        estimated_cost_usd=0,
        outcome="blocked_missing_credential",
    )
    reset = client.post("/api/demo/reset", headers=headers(SESSION_A))
    assert reset.status_code == 200
    assert reset.json()["session_scope"] == "caller_only"
    assert reset.json()["model_ledger_scope"] == "global"
    assert reset.json()["model_ledger_preserved"] is True
    assert client.get(f"/api/runs/{run_a['run_id']}", headers=headers(SESSION_A)).status_code == 404
    assert client.get(f"/api/runs/{run_b['run_id']}", headers=headers(SESSION_B)).status_code == 200
    assert app_module.storage.model_calls()[0]["call_id"] == call_id


def test_storage_reset_rejects_active_runs_then_allows_terminal_reset(tmp_path: Path):
    storage = Storage(str(tmp_path / "active-reset.db"))
    queued_run_id = storage.create_run("DEF-027-E0-DEMO", session_id=SESSION_A)
    running_run_id = storage.create_run("DEMO-MOULD-002", session_id=SESSION_A)
    storage.patch_run(running_run_id, status="running")

    with pytest.raises(ActiveRunResetError, match="while a run is active") as caught:
        storage.reset(session_id=SESSION_A)

    assert caught.value.__cause__ is None
    assert queued_run_id not in str(caught.value)
    assert running_run_id not in str(caught.value)
    assert storage.get_run(queued_run_id, session_id=SESSION_A) is not None
    assert storage.get_run(running_run_id, session_id=SESSION_A) is not None

    storage.patch_run(queued_run_id, status="failed")
    storage.patch_run(running_run_id, status="complete")
    removed = storage.reset(session_id=SESSION_A)

    assert removed["runs"] == 2
    assert storage.get_run(queued_run_id, session_id=SESSION_A) is None
    assert storage.get_run(running_run_id, session_id=SESSION_A) is None


def test_active_reset_guard_is_session_scoped_and_returns_bounded_409(client: TestClient):
    active_run_id = app_module.storage.create_run(
        "DEF-027-E0-DEMO",
        session_id=SESSION_A,
    )
    app_module.storage.patch_run(
        active_run_id,
        status="running",
        patch={"raw_error": "RAW_ACTIVE_RESET_SENTINEL"},
    )
    other_run_id = app_module.storage.create_run(
        "DEMO-MOULD-002",
        session_id=SESSION_B,
    )
    app_module.storage.patch_run(other_run_id, status="running")
    call_id = app_module.storage.create_model_call(
        run_id=active_run_id,
        provider="openrouter",
        model=OPENROUTER_MODEL,
        cache_key="active-reset-global-ledger",
        purpose="active-reset-test",
        call_count=0,
        estimated_cost_usd=0,
        outcome="blocked_missing_credential",
    )

    blocked = client.post("/api/demo/reset", headers=headers(SESSION_A))

    assert blocked.status_code == 409
    assert blocked.json() == {
        "detail": "Cannot reset demo state while this session has a queued or running analysis"
    }
    assert active_run_id not in blocked.text
    assert other_run_id not in blocked.text
    assert "RAW_ACTIVE_RESET_SENTINEL" not in blocked.text
    assert "OPENROUTER_API_KEY" not in blocked.text
    assert app_module.storage.get_run(active_run_id, session_id=SESSION_A) is not None
    assert app_module.storage.get_run(other_run_id, session_id=SESSION_B) is not None
    assert app_module.storage.model_calls()[0]["call_id"] == call_id

    app_module.storage.patch_run(active_run_id, status="failed")
    reset = client.post("/api/demo/reset", headers=headers(SESSION_A))

    assert reset.status_code == 200
    assert reset.json()["session_scope"] == "caller_only"
    assert reset.json()["model_ledger_preserved"] is True
    assert app_module.storage.get_run(active_run_id, session_id=SESSION_A) is None
    assert app_module.storage.get_run(other_run_id, session_id=SESSION_B) is not None
    assert app_module.storage.model_calls()[0]["call_id"] == call_id


def test_model_ledger_endpoint_is_global_and_strictly_sanitized(client: TestClient):
    call_id = app_module.storage.create_model_call(
        run_id="session-private-run",
        provider="openrouter",
        provider_endpoint="https://openrouter.ai/api/v1/chat/completions",
        model=OPENROUTER_MODEL,
        implementation="model_backed_openrouter_canonicalizer",
        cache_key="safe-cache-key",
        purpose="observable package to canonical facts",
        call_count=1,
        estimated_cost_usd=0.01,
        outcome="started",
        orchestration_id="orch_safe_identifier",
        agent_id="canonical_facts",
        agent_role="guarded_canonical_facts",
        parent_call_id=None,
    )
    app_module.storage.finish_model_call(
        call_id,
        outcome="failed",
        error_type="SafeErrorType",
        error_fact_id="fact_safe_identifier",
        error_invariant="normalized_value_admissibility",
        provider_error_code="provider-error-secret-must-not-leak",
        ignored_noncontrolling_normalized_proposals=1,
        authority_mode="hybrid_guarded",
        accepted_fact_ids=["fact_safe_identifier"],
        accepted_fact_count=1,
        rejected_facts=[{"fact_id": "fact_rejected", "invariant": "source_reference_set"}],
        rejected_fact_count=1,
        usage_source="generation_metadata",
        generation_model="nvidia/nemotron-3-ultra-550b-a55b-20260604",
        metadata_poll_count=2,
        metadata_latency_ms=2.5,
        error_message="secret-message-must-not-leak",
        canonical_output={"secret": "canonical-output-must-not-leak"},
        usage={"provider_internal": "must-not-leak"},
        prompt_tokens=10,
        completion_tokens=2,
        total_tokens=12,
        latency_ms=1.5,
    )
    response = client.get("/api/model-ledger")
    assert response.status_code == 200
    value = response.json()
    assert value["scope"] == "global_budget_ledger"
    assert value["summary"]["network_calls"] == 1
    assert value["summary"]["actual_cost_usd"] == 0
    assert value["summary"]["actual_cost_complete"] is False
    assert value["summary"]["unknown_cost_call_count"] == 1
    assert value["items"][0]["error_type"] == "SafeErrorType"
    assert value["items"][0]["orchestration_id"] == "orch_safe_identifier"
    assert value["items"][0]["agent_id"] == "canonical_facts"
    assert value["items"][0]["agent_role"] == "guarded_canonical_facts"
    assert value["items"][0]["parent_call_id"] is None
    assert value["items"][0]["error_fact_id"] == "fact_safe_identifier"
    assert value["items"][0]["error_invariant"] == "normalized_value_admissibility"
    assert value["items"][0]["ignored_noncontrolling_normalized_proposals"] == 1
    assert value["items"][0]["authority_mode"] == "hybrid_guarded"
    assert value["items"][0]["accepted_fact_ids"] == ["fact_safe_identifier"]
    assert value["items"][0]["accepted_fact_count"] == 1
    assert value["items"][0]["rejected_facts"] == [
        {"fact_id": "fact_rejected", "invariant": "source_reference_set"}
    ]
    assert value["items"][0]["rejected_fact_count"] == 1
    assert value["items"][0]["usage_source"] == "generation_metadata"
    assert value["items"][0]["generation_model"] == "nvidia/nemotron-3-ultra-550b-a55b-20260604"
    assert value["items"][0]["metadata_poll_count"] == 2
    assert value["items"][0]["metadata_latency_ms"] == 2.5
    for forbidden_key in (
        "run_id",
        "error_message",
        "canonical_output",
        "usage",
        "openrouter_metadata",
        "origin_usage",
        "origin_finish_reason",
        "provider_error_code",
    ):
        assert forbidden_key not in value["items"][0]
    serialized = response.text
    for forbidden in (
        "session-private-run",
        "secret-message-must-not-leak",
        "canonical-output-must-not-leak",
        "provider_internal",
        "provider-error-secret-must-not-leak",
    ):
        assert forbidden not in serialized
