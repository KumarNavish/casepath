from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import threading
import time
from typing import Any

import httpx
from langchain_core.messages import AIMessage, HumanMessage
from langsmith.run_helpers import tracing_context
from openrouter import OpenRouter, components, errors
from openrouter.utils.unmarshal_json_response import unmarshal_json_response
import pytest
from pydantic import ValidationError

from casepath_api import canonicalizer as canonicalizer_module
from casepath_api import langchain_runtime
from casepath_api import multi_agent as multi_agent_module
from casepath_api.canonicalizer import OPENROUTER_MODEL
from casepath_api.data import CLAIMS, observable_claim_package
from casepath_api.evidence_relations import (
    EVIDENCE_ITEM_IDS_BY_CLAIM,
    apply_evidence_relations,
)
from casepath_api.multi_agent import (
    AI_AGENT_IDS,
    AgentBoundaryError,
    AgentInvocationFailure,
    DETERMINISTIC_GATE_IDS,
    EVIDENCE_ITEM_IDS,
    EVIDENCE_STATUS_CANDIDATES,
    EvidenceChecklistResponse,
    FINAL_AUDIT_CHECK_IDS,
    InstrumentedStructuredAgent,
    NemotronMultiAgentOrchestrator,
    OrchestratorPlan,
    PROCESS_DECISION_VALUE_CANDIDATES,
    PROCESS_DECISION_PROPOSAL_COUNT,
    ProcessDecisionResponse,
    ROLE_REASONING,
    ROLE_OUTPUT_TOKENS,
    SOURCE_INTEGRITY_PROPOSAL_COUNT,
    SOURCE_INTEGRITY_REASONING_EFFORT,
    SourceIntegrityResponse,
    _bounded_evidence_checklist_schema,
    _bounded_source_integrity_schema,
    _evidence_candidate_artifact_ids,
    _compatible_process_decision_values,
    _default_runnable_factory,
    _evidence_provider_payload,
    _evidence_selection_id,
    _final_brief_provider_payload,
    _normalize_evidence_checklist_response,
    _plan_validator,
    _require_exact_proposal_membership,
    _source_registry,
    accepted_artifact_hash,
    apply_evidence_contribution,
    apply_process_contribution,
)
from casepath_api.pipeline_v15 import ClaimPipeline
from casepath_api.projections import apply_evidence_projection
from casepath_api.storage import Storage


def wait(storage: Storage, run_id: str) -> dict[str, Any]:
    for _ in range(500):
        run = storage.get_run(run_id)
        if run and run["status"] in {"complete", "failed"}:
            return run
        time.sleep(0.01)
    raise AssertionError("run timeout")


def assert_together_compatible_schema(schema: dict[str, Any]) -> None:
    assert '"uniqueItems"' not in json.dumps(schema, sort_keys=True)


def oracle_result(tmp_path: Path) -> dict[str, Any]:
    storage = Storage(str(tmp_path / "oracle.db"))
    pipeline = ClaimPipeline(storage, pace_seconds=0)
    run = wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    assert run["status"] == "complete", run.get("error")
    return run["result"]


class FakeStructuredRunnable:
    def __init__(
        self,
        *,
        agent_id: str,
        schema,
        response: dict[str, Any],
        captures: dict[str, list[dict[str, Any]]],
        fanout_barrier: threading.Barrier,
    ):
        self.agent_id = agent_id
        self.schema = schema
        self.response = response
        self.captures = captures
        self.fanout_barrier = fanout_barrier

    def invoke(self, messages, config=None):
        payload = json.loads(messages[-1].content)
        self.captures[self.agent_id].append(payload)
        if self.agent_id in {"document_source_integrity", "process_decision_mapping"}:
            self.fanout_barrier.wait(timeout=2)
            time.sleep(0.02)
        try:
            parsed = self.schema.model_validate(self.response)
            parsing_error = None
        except ValidationError as exc:
            parsed = None
            parsing_error = exc
        raw = AIMessage(
            content="",
            response_metadata={
                "id": f"gen-{self.agent_id}",
                "model_name": OPENROUTER_MODEL,
                "finish_reason": "stop",
                "provider_name": "Together",
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 40,
                    "total_tokens": 140,
                    "cost": 0.001,
                },
            },
            usage_metadata={"input_tokens": 100, "output_tokens": 40, "total_tokens": 140},
        )
        return {"raw": raw, "parsed": parsed, "parsing_error": parsing_error}


def graph_fixture(tmp_path: Path):
    result = oracle_result(tmp_path)
    facts = result["facts"]
    process = result["process"]
    checklist = result["checklist"]
    package = observable_claim_package(CLAIMS["DEF-027-E0-DEMO"])
    registry = _source_registry(package)
    refs_by_artifact: dict[str, list[str]] = defaultdict(list)
    for ref in registry:
        refs_by_artifact[ref["artifact_id"]].append(ref["source_ref_id"])
    source_proposals = []
    for artifact in package["artifacts"]:
        source_proposals.append(
            {
                "artifact_id": artifact["artifact_id"],
                "integrity_class": (
                    "visual_only"
                    if artifact["media_type"].startswith("image/")
                    else "text_grounded"
                ),
                "source_ref_ids": (
                    sorted(refs_by_artifact[artifact["artifact_id"]])[:1]
                    if not artifact["media_type"].startswith("image/")
                    else []
                ),
                "confidence_basis_points": 8_100,
            }
        )
    controlling = [fact for fact in facts if fact["controls_process"] is True]
    process_proposals = [
        {
            "fact_id": fact["fact_id"],
            "decision_value": fact["decision_value"],
            "confidence": 0.82,
        }
        for fact in controlling
    ]
    evidence_proposals = [
        {
            "item_id": item["item_id"],
            "status": item["status"],
            "artifact_ids": sorted(item.get("artifact_ids", [])),
            "confidence": 0.83,
        }
        for item in checklist["items"]
    ]
    current = process["current_overlay"]
    current_node = next(
        node for node in process["nodes"] if node["node_id"] == current["current_node_id"]
    )
    evidence_slots = {
        proposal["item_id"]: {
            "selection_id": _evidence_selection_id(
                proposal["status"], tuple(proposal["artifact_ids"])
            ),
            "confidence": proposal["confidence"],
        }
        for proposal in evidence_proposals
    }
    responses = {
        "orchestrator_plan": {
            "priority_fact_ids": [fact["fact_id"] for fact in facts[:6]],
            "priority_task_codes": [
                "source_integrity",
                "process_decisions",
                "evidence_gaps",
                "final_brief",
            ],
        },
        "document_source_integrity": {"proposals": source_proposals},
        "process_decision_mapping": {"proposals": process_proposals},
        "evidence_checklist": {"items": evidence_slots},
        "final_claim_brief_audit": {
            "proposal": {
                "current_node_id": current["current_node_id"],
                "next_action_node_id": current["next_action_node_id"],
                "supporting_fact_ids": sorted(current_node.get("fact_ids", [])),
                "upstream_contribution_ids": [
                    "document_source_integrity",
                    "process_decision_mapping",
                    "evidence_checklist",
                ],
                "audit_check_ids": list(FINAL_AUDIT_CHECK_IDS),
                "confidence": 0.84,
            }
        },
    }
    captures: dict[str, list[dict[str, Any]]] = defaultdict(list)
    barrier = threading.Barrier(2)

    def factory(agent_id, schema, _key, _orchestration_id, _max_tokens):
        return FakeStructuredRunnable(
            agent_id=agent_id,
            schema=schema,
            response=responses[agent_id],
            captures=captures,
            fanout_barrier=barrier,
        )

    storage = Storage(str(tmp_path / "agents.db"))
    runner = InstrumentedStructuredAgent(
        storage,
        runnable_factory=factory,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    def rebuild_verification(
        accepted_process: dict[str, Any], accepted_checklist: dict[str, Any]
    ) -> dict[str, Any]:
        fresh = json.loads(json.dumps(result["verification"]))
        fresh["whole_playbook_hash"] = accepted_artifact_hash(
            {
                "process": accepted_process,
                "checklist": accepted_checklist,
            }
        )
        return fresh

    orchestrator = NemotronMultiAgentOrchestrator(
        storage,
        agent_runner=runner,
        verification_builder=rebuild_verification,
    )
    canonicalization = {
        "model": OPENROUTER_MODEL,
        "call_id": "modelcall-canonical",
        "cache_hit": False,
        "origin_call_id": "modelcall-canonical",
        "response_id": "gen-canonical",
        "response_model": OPENROUTER_MODEL,
        "upstream_provider": "Together",
        "usage_source": "response",
        "finish_reason": "stop",
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 40,
            "total_tokens": 140,
            "actual_cost_usd": 0.001,
            "usage_source": "response",
        },
        "diagnostics": {
            "accepted_fact_ids": [fact["fact_id"] for fact in facts],
            "accepted_fact_count": len(facts),
            "rejected_facts": [],
            "rejected_fact_count": 0,
        },
    }
    return orchestrator, storage, captures, responses, package, canonicalization, result


def evidence_candidate_contracts(
    package: dict[str, Any], result: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    candidate_ids = _evidence_candidate_artifact_ids(
        {
            "observable_package": package,
            "source_integrity": {"artifacts": []},
            "facts": result["facts"],
            "checklist": result["checklist"],
        }
    )
    return {
        item["item_id"]: {
            "item_id": item["item_id"],
            "required_level": item["required_level"],
            "candidate_artifact_ids": candidate_ids[item["item_id"]],
        }
        for item in result["checklist"]["items"]
    }


def test_compiled_langgraph_fanout_join_and_bounded_payloads(tmp_path: Path):
    (
        orchestrator,
        storage,
        captures,
        responses,
        package,
        canonicalization,
        result,
    ) = graph_fixture(tmp_path)
    receipts: list[dict[str, Any]] = []
    audit = orchestrator.invoke(
        run_id="run-graph-test",
        orchestration_id="orch-graph-test",
        observable_package=package,
        canonicalization=canonicalization,
        facts=result["facts"],
        process=result["process"],
        checklist=result["checklist"],
        verification=result["verification"],
        progress_sink=receipts.append,
    )

    assert audit["all_required_agents_contributed"] is True
    assert {item["agent_id"] for item in audit["agents"]} == set(AI_AGENT_IDS)
    assert {item["agent_id"] for item in audit["deterministic_gates"]} == set(
        DETERMINISTIC_GATE_IDS
    )
    assert all(item["actor_type"] == "nemotron_agent" for item in audit["agents"])
    assert all(
        item["acceptance_scope"] == "pre_review_model_output"
        for item in audit["agents"]
    )
    assert all(item["provider"] == "openrouter" for item in audit["agents"])
    assert all(item["requested_model"] == OPENROUTER_MODEL for item in audit["agents"])
    assert all(item["response_id"] for item in audit["agents"])
    assert all(item["finish_reason"] == "stop" for item in audit["agents"])
    assert all(item["usage"]["total_tokens"] > 0 for item in audit["agents"])
    assert audit["execution_topology"] == {
        "authority": "deterministic_application",
        "implementation": "compiled_langgraph_stategraph",
        "delegations": [
            {
                "agent_id": "document_source_integrity",
                "dependencies": ["orchestrator_plan"],
            },
            {
                "agent_id": "process_decision_mapping",
                "dependencies": ["orchestrator_plan"],
            },
            {
                "agent_id": "evidence_checklist",
                "dependencies": ["deterministic_process_gate"],
            },
            {
                "agent_id": "final_claim_brief_audit",
                "dependencies": ["deterministic_evidence_gate"],
            },
        ],
        "parallel_groups": [
            ["document_source_integrity", "process_decision_mapping"]
        ],
    }
    plan_artifact = audit["specialist_artifacts"]["orchestrator_plan"]
    fact_ids = [item["fact_id"] for item in result["facts"]]
    assert len(fact_ids) == 18
    assert plan_artifact["contribution_type"] == "constrained_focus_prioritization"
    assert plan_artifact["model_priority_fact_ids"] == fact_ids[:6]
    assert plan_artifact["model_priority_attribution"] == "Nemotron Orchestrator"
    assert plan_artifact["model_priority_task_codes"] == plan_artifact[
        "priority_task_codes"
    ]
    assert "attribution" not in plan_artifact
    assert plan_artifact["focus_fact_ids"] == fact_ids
    assert len(plan_artifact["focus_source_ref_ids"]) == 5
    assert plan_artifact["deterministic_coverage"] == {
        "fact_ids": fact_ids[6:],
        "source_ref_ids": plan_artifact["focus_source_ref_ids"],
        "required_text_artifact_ids": [
            "art_delivery",
            "art_lease",
            "art_management_reply",
            "art_notification",
            "art_timeline",
        ],
        "attribution": "deterministic_application",
    }
    plan_audit = next(
        item for item in audit["agents"] if item["agent_id"] == "orchestrator_plan"
    )
    assert plan_audit["model_priority_fact_ids"] == fact_ids[:6]
    assert plan_audit["model_priority_task_codes"] == plan_artifact[
        "priority_task_codes"
    ]
    assert plan_audit["derived_focus_fact_ids"] == fact_ids
    assert plan_audit["derived_focus_source_ref_ids"] == plan_artifact[
        "focus_source_ref_ids"
    ]
    assert plan_audit["deterministic_coverage"] == plan_artifact[
        "deterministic_coverage"
    ]
    assert "delegations" not in plan_artifact
    assert "parallel_groups" not in plan_artifact
    assert audit["external_tracing"] is False
    assert set(audit["specialist_artifacts"]) == {
        "orchestrator_plan",
        "document_source_integrity",
        "process_decision_mapping",
        "evidence_checklist",
        "final_claim_brief_audit",
    }
    assert any(item["receipt_type"] == "gate_passed" for item in receipts)
    assert all("reasoning" not in json.dumps(item).lower() for item in receipts)
    completed_receipts = [
        item for item in receipts if item.get("receipt_type") == "agent_completed"
    ]
    assert len(completed_receipts) == 5
    assert all(
        item["acceptance_scope"] == "pre_review_model_output"
        for item in completed_receipts
    )

    source_payload = captures["document_source_integrity"][0]
    assert set(source_payload) == {
        "orchestrator_focus",
        "required_proposal_count",
        "required_artifact_ids",
        "artifact_candidates",
        "source_reference_registry",
    }
    assert source_payload["required_proposal_count"] == 6
    assert source_payload["required_artifact_ids"] == [
        item["artifact_id"] for item in source_payload["artifact_candidates"]
    ]
    process_payload = captures["process_decision_mapping"][0]
    assert set(process_payload) == {
        "orchestrator_focus",
        "required_proposal_count",
        "required_fact_ids",
        "canonical_fact_handoff",
        "decision_value_vocabulary",
    }
    assert process_payload["required_proposal_count"] == 6
    assert process_payload["required_fact_ids"] == [
        item["fact_id"] for item in process_payload["canonical_fact_handoff"]
    ]
    assert process_payload["decision_value_vocabulary"] == (
        PROCESS_DECISION_VALUE_CANDIDATES
    )
    assert len(process_payload["canonical_fact_handoff"]) == 6
    assert all(
        set(item)
        == {
            "fact_id",
            "label",
            "state",
            "decision_key",
            "normalized_value",
            "source_ref_ids",
        }
        and "decision_value" not in item
        for item in process_payload["canonical_fact_handoff"]
    )
    evidence_payload = captures["evidence_checklist"][0]
    assert set(evidence_payload) == {
        "orchestrator_focus",
        "accepted_process_gate_handoff",
        "required_proposal_count",
        "required_item_ids",
        "evidence_candidates",
        "allowed_statuses",
        "selection_id_format",
        "canonical_fact_handoff",
        "source_integrity_artifact_inventory",
    }
    assert evidence_payload["allowed_statuses"] == EVIDENCE_STATUS_CANDIDATES
    assert evidence_payload["required_proposal_count"] == len(EVIDENCE_ITEM_IDS) == 21
    assert evidence_payload["required_item_ids"] == [
        item["item_id"] for item in evidence_payload["evidence_candidates"]
    ]
    assert set(evidence_payload["required_item_ids"]) == set(EVIDENCE_ITEM_IDS)
    assert all(
        "status" not in item
        and "artifact_ids" not in item
        and "why" not in item
        and isinstance(item["candidate_artifact_ids"], list)
        and set(item["status_choices"])
        == {"with_artifacts", "without_artifacts"}
        for item in evidence_payload["evidence_candidates"]
    )
    assert all(
        "source_artifact_ids" in item
        for item in evidence_payload["canonical_fact_handoff"]
    )
    final_payload = captures["final_claim_brief_audit"][0]
    assert set(final_payload) == {
        "orchestrator_focus",
        "accepted_process_gate_handoff",
        "accepted_evidence_gate_handoff",
        "static_process_topology",
        "canonical_fact_handoff",
        "prior_accepted_contributions",
        "audit_check_candidates",
    }
    assert "source_reference_registry" not in final_payload
    topology = final_payload["static_process_topology"]
    assert all("answer" not in item and "state" not in item for item in topology["nodes"])
    assert all("state" not in branch for item in topology["nodes"] for branch in item["branches"])
    assert all("state" not in item for item in topology["edges"])
    assert len(topology["edges"]) == len(result["process"]["edges"]) == 22
    assert len(
        {
            (item["source"], item["target"], item["condition"])
            for item in topology["edges"]
        }
    ) == 22
    serialized_payloads = json.dumps(captures, sort_keys=True)
    plan_payload = captures["orchestrator_plan"][0]
    assert set(responses["orchestrator_plan"]) == {
        "priority_fact_ids",
        "priority_task_codes",
    }
    plan_schema = OrchestratorPlan.model_json_schema()
    assert set(plan_schema["properties"]) == {
        "priority_fact_ids",
        "priority_task_codes",
    }
    assert plan_schema["properties"]["priority_fact_ids"] == {
        "items": {"type": "string"},
        "maxItems": 6,
        "minItems": 1,
        "title": "Priority Fact Ids",
        "type": "array",
    }
    assert plan_schema["properties"]["priority_task_codes"]["maxItems"] == 4
    assert plan_schema["properties"]["priority_task_codes"]["minItems"] == 4
    assert_together_compatible_schema(plan_schema)
    assert set(plan_payload) == {
        "schema_version",
        "max_priority_fact_count",
        "fact_candidates",
        "task_codes",
    }
    assert len(plan_payload["fact_candidates"]) == 18
    assert len(_source_registry(package)) >= 300
    assert "source_reference_candidates" not in plan_payload
    assert "source_ref_id" not in json.dumps(plan_payload, sort_keys=True)
    assert len(json.dumps(plan_payload, separators=(",", ":")).encode()) < 2_000
    for private_name in (
        "expected_state",
        "canonical_value",
        "canonical_explanation",
        "required_text_reference_count",
        "required_source_reference_count",
        "expected_status",
        "expected_artifact_ids",
        "expected_current_node_id",
        "expected_next_action_node_id",
    ):
        assert private_name not in serialized_payloads

    specialist_artifacts = audit["specialist_artifacts"]
    assert specialist_artifacts["process_decision_mapping"]["decisions"][0][
        "confidence_basis_points"
    ] == 8200
    assert specialist_artifacts["evidence_checklist"]["items"][0][
        "confidence_basis_points"
    ] == 8300
    assert specialist_artifacts["final_claim_brief_audit"][
        "confidence_basis_points"
    ] == 8400
    assert specialist_artifacts["final_claim_brief_audit"][
        "input_contribution_ids"
    ] == [
        "document_source_integrity",
        "evidence_checklist",
        "process_decision_mapping",
    ]
    assert specialist_artifacts["final_claim_brief_audit"][
        "lineage_authority"
    ] == "hybrid_guarded_model_audit"

    calls = storage.model_calls()
    assert len(calls) == 5
    assert all(item["call_count"] == 1 for item in calls)
    plan_call = next(item for item in calls if item["agent_id"] == "orchestrator_plan")
    workers = [item for item in calls if item["agent_id"] != "orchestrator_plan"]
    assert all(item["parent_call_id"] == plan_call["call_id"] for item in workers)
    assert all(item["delegation_id"].startswith("dlg_") for item in calls)
    assert all(item["actual_cost_usd"] == 0.001 for item in calls)


def test_specialist_concurrency_block_emits_truthful_zero_call_receipt(tmp_path: Path):
    (
        orchestrator,
        storage,
        _captures,
        _responses,
        package,
        canonicalization,
        result,
    ) = graph_fixture(tmp_path)

    class Runnable:
        def invoke(self, *_args, **_kwargs):
            raise langchain_runtime.OpenRouterSendAdmissionTimeoutError()

    assert orchestrator.agent_runner is not None
    orchestrator.agent_runner.runnable_factory = lambda *_args: Runnable()
    receipts: list[dict[str, Any]] = []

    with pytest.raises(
        AgentInvocationFailure,
        match="provider_concurrency_timeout",
    ):
        orchestrator.invoke(
            run_id="run-concurrency-blocked-receipt",
            orchestration_id="orch-concurrency-blocked-receipt",
            observable_package=package,
            canonicalization=canonicalization,
            facts=result["facts"],
            process=result["process"],
            checklist=result["checklist"],
            verification=result["verification"],
            progress_sink=receipts.append,
        )

    failed = next(
        item for item in receipts if item.get("receipt_type") == "agent_failed"
    )
    assert failed["agent_id"] == "orchestrator_plan"
    assert failed["provider"] == "openrouter"
    assert failed["requested_model"] == OPENROUTER_MODEL
    assert failed["call_count"] == 0
    assert failed["outcome"] == "blocked_provider_concurrency"
    assert failed["error_invariant"] == "provider_concurrency_timeout"
    assert storage.model_call_summary()["network_calls"] == 0


def _replace_process_decisions_with_valid_alternatives(
    responses: dict[str, dict[str, Any]],
    facts: list[dict[str, Any]],
    count: int,
) -> None:
    facts_by_id = {item["fact_id"]: item for item in facts}
    for proposal in responses["process_decision_mapping"]["proposals"][:count]:
        fact = facts_by_id[proposal["fact_id"]]
        proposal["decision_value"] = next(
            candidate
            for candidate in PROCESS_DECISION_VALUE_CANDIDATES[
                fact["decision_key"]
            ]
            if candidate not in _compatible_process_decision_values(fact)
        )


def test_process_specialist_four_of_six_passes_with_two_field_fallbacks(
    tmp_path: Path,
):
    (
        orchestrator,
        _storage,
        _captures,
        responses,
        package,
        canonicalization,
        result,
    ) = graph_fixture(tmp_path)
    _replace_process_decisions_with_valid_alternatives(
        responses, result["facts"], 2
    )

    audit = orchestrator.invoke(
        run_id="run-process-four-of-six",
        orchestration_id="orch-process-four-of-six",
        observable_package=package,
        canonicalization=canonicalization,
        facts=result["facts"],
        process=result["process"],
        checklist=result["checklist"],
        verification=result["verification"],
    )

    process_audit = next(
        item
        for item in audit["agents"]
        if item["agent_id"] == "process_decision_mapping"
    )
    assert process_audit["accepted_count"] == 4
    assert process_audit["rejected_count"] == 2
    assert process_audit["outcome"] == "succeeded_with_guarded_fallback"
    decisions = audit["specialist_artifacts"]["process_decision_mapping"][
        "decisions"
    ]
    assert sum(item["deterministic_fallback_applied"] for item in decisions) == 2
    assert audit["all_required_agents_contributed"] is True


def test_process_specialist_three_of_six_fails_without_cache_or_raw_diagnostics(
    tmp_path: Path,
):
    (
        orchestrator,
        storage,
        captures,
        responses,
        package,
        canonicalization,
        result,
    ) = graph_fixture(tmp_path)
    _replace_process_decisions_with_valid_alternatives(
        responses, result["facts"], 3
    )

    with pytest.raises(
        AgentInvocationFailure, match="model_contribution_majority"
    ):
        orchestrator.invoke(
            run_id="run-process-three-of-six",
            orchestration_id="orch-process-three-of-six",
            observable_package=package,
            canonicalization=canonicalization,
            facts=result["facts"],
            process=result["process"],
            checklist=result["checklist"],
            verification=result["verification"],
        )

    second_package = json.loads(json.dumps(package))
    image = next(
        item
        for item in second_package["artifacts"]
        if item["media_type"].startswith("image/")
    )
    image["media_type"] = "image/png"
    with pytest.raises(
        AgentInvocationFailure, match="model_contribution_majority"
    ):
        orchestrator.invoke(
            run_id="run-process-three-of-six-repeat",
            orchestration_id="orch-process-three-of-six-repeat",
            observable_package=second_package,
            canonicalization=canonicalization,
            facts=result["facts"],
            process=result["process"],
            checklist=result["checklist"],
            verification=result["verification"],
        )

    process_ledger = [
        item
        for item in storage.model_calls()
        if item["agent_id"] == "process_decision_mapping"
    ]
    assert len(process_ledger) == 2
    assert len(captures["process_decision_mapping"]) == 2
    assert len({item["cache_key"] for item in process_ledger}) == 1
    assert all(item["call_count"] == 1 for item in process_ledger)
    expected_rejected = [
        {
            "item_id": f"fact:{proposal['fact_id']}:decision_value",
            "invariant": "process_decision_contract",
        }
        for proposal in responses["process_decision_mapping"]["proposals"][:3]
    ]
    for ledger in process_ledger:
        assert ledger["outcome"] == "failed"
        assert ledger["accepted_item_count"] == 3
        assert ledger["rejected_item_count"] == 3
        assert ledger["ignored_proposal_count"] == 0
        assert len(ledger["accepted_item_ids"]) == 3
        assert all(
            item.startswith("fact:") and item.endswith(":decision_value")
            for item in ledger["accepted_item_ids"]
        )
        assert ledger["rejected_items"] == expected_rejected
        assert storage.cached_model_output(ledger["cache_key"]) is None
        for forbidden in (
            "deterministic_fallback_applied",
            "canonical_output",
        ):
            assert forbidden not in ledger
        serialized_ledger = json.dumps(ledger, sort_keys=True)
        assert "source_ref" not in serialized_ledger
        assert "excerpt" not in serialized_ledger


def test_evidence_specialist_accepts_valid_alternate_bounded_status(
    tmp_path: Path,
):
    (
        orchestrator,
        _storage,
        _captures,
        responses,
        package,
        canonicalization,
        result,
    ) = graph_fixture(tmp_path)
    item_id = EVIDENCE_ITEM_IDS[0]
    source_item = next(
        item for item in result["checklist"]["items"] if item["item_id"] == item_id
    )
    alternate_status = (
        "provided_insufficient"
        if source_item["status"] == "provided_sufficient"
        else "provided_sufficient"
    )
    responses["evidence_checklist"]["items"][item_id]["selection_id"] = (
        _evidence_selection_id(
            alternate_status, tuple(sorted(source_item.get("artifact_ids", [])))
        )
    )

    audit = orchestrator.invoke(
        run_id="run-evidence-independent-units",
        orchestration_id="orch-evidence-independent-units",
        observable_package=package,
        canonicalization=canonicalization,
        facts=result["facts"],
        process=result["process"],
        checklist=result["checklist"],
        verification=result["verification"],
    )

    evidence_audit = next(
        item
        for item in audit["agents"]
        if item["agent_id"] == "evidence_checklist"
    )
    assert evidence_audit["accepted_count"] == 42
    assert evidence_audit["rejected_count"] == 0
    accepted_item = audit["specialist_artifacts"]["evidence_checklist"][
        "items"
    ][0]
    contributions = {
        item["field"]: item for item in accepted_item["field_contributions"]
    }
    assert contributions["status"]["deterministic_fallback_applied"] is False
    assert contributions["artifact_ids"]["deterministic_fallback_applied"] is False
    assert accepted_item["attribution"] == "Evidence and Checklist Agent"
    assert accepted_item["status"] == alternate_status


def test_coverage_schemas_require_exact_bounded_cardinality_and_ids():
    for response_schema, expected_count in (
        (SourceIntegrityResponse, SOURCE_INTEGRITY_PROPOSAL_COUNT),
        (ProcessDecisionResponse, PROCESS_DECISION_PROPOSAL_COUNT),
        (EvidenceChecklistResponse, len(EVIDENCE_ITEM_IDS)),
    ):
        proposals_schema = response_schema.model_json_schema()["properties"][
            "proposals"
        ]
        assert proposals_schema["minItems"] == expected_count
        assert proposals_schema["maxItems"] == expected_count
        assert_together_compatible_schema(response_schema.model_json_schema())
        with pytest.raises(ValidationError):
            response_schema.model_validate({"proposals": []})

    source_proposals = [
        {
            "artifact_id": f"artifact-{index}",
            "integrity_class": "metadata_only",
            "source_ref_ids": [],
            "confidence_basis_points": 5_000,
        }
        for index in range(SOURCE_INTEGRITY_PROPOSAL_COUNT)
    ]
    process_proposals = [
        {
            "fact_id": f"fact-{index}",
            "decision_value": "in_scope",
            "confidence": 0.5,
        }
        for index in range(PROCESS_DECISION_PROPOSAL_COUNT)
    ]
    for response_schema, proposals, id_key in (
        (SourceIntegrityResponse, source_proposals, "artifact_id"),
        (ProcessDecisionResponse, process_proposals, "fact_id"),
    ):
        assert len(
            response_schema.model_validate({"proposals": proposals}).proposals
        ) == 6
        duplicate = [dict(item) for item in proposals]
        duplicate[-1][id_key] = duplicate[0][id_key]
        with pytest.raises(ValidationError):
            response_schema.model_validate({"proposals": duplicate})
        with pytest.raises(ValidationError):
            response_schema.model_validate({"proposals": proposals[:4]})

    evidence_schema = EvidenceChecklistResponse.model_json_schema()
    item_id_schema = evidence_schema["$defs"]["EvidenceChecklistProposal"][
        "properties"
    ]["item_id"]
    assert item_id_schema["enum"] == list(EVIDENCE_ITEM_IDS)
    evidence_proposals = [
        {
            "item_id": item_id,
            "status": "missing",
            "artifact_ids": [],
            "confidence": 0.5,
        }
        for item_id in EVIDENCE_ITEM_IDS
    ]
    assert len(
        EvidenceChecklistResponse.model_validate(
            {"proposals": evidence_proposals}
        ).proposals
    ) == 21
    for malformed in (
        evidence_proposals[:11],
        evidence_proposals[:20],
        [*evidence_proposals, evidence_proposals[0]],
        [
            {**evidence_proposals[0], "item_id": "unknown"},
            *evidence_proposals[1:],
        ],
        [*evidence_proposals[:-1], dict(evidence_proposals[0])],
    ):
        with pytest.raises(ValidationError):
            EvidenceChecklistResponse.model_validate({"proposals": malformed})


def test_all_specialist_wire_schemas_avoid_unsupported_unique_items():
    bounded_source_response = _bounded_source_integrity_schema(
        artifact_ids=tuple(f"artifact-{index}" for index in range(6)),
        source_ref_ids=("src-a", "src-b"),
    )
    bounded_evidence_response = _bounded_evidence_checklist_schema(
        {
            item_id: {
                "item_id": item_id,
                "required_level": "mandatory",
                "candidate_artifact_ids": [],
            }
            for item_id in EVIDENCE_ITEM_IDS
        }
    )
    for response_schema in (
        OrchestratorPlan,
        SourceIntegrityResponse,
        bounded_source_response,
        ProcessDecisionResponse,
        EvidenceChecklistResponse,
        bounded_evidence_response,
        multi_agent_module.FinalClaimBriefResponse,
    ):
        assert_together_compatible_schema(response_schema.model_json_schema())


def test_evidence_wire_schema_has_exact_slots_and_coherent_item_enums(
    tmp_path: Path,
):
    (
        _orchestrator,
        _storage,
        _captures,
        responses,
        package,
        _canonicalization,
        result,
    ) = graph_fixture(tmp_path)
    contracts = evidence_candidate_contracts(package, result)
    response_schema = _bounded_evidence_checklist_schema(contracts)
    schema = response_schema.model_json_schema()
    serialized_schema = json.dumps(schema, sort_keys=True)
    for unsupported in ("uniqueItems", '"oneOf"', '"anyOf"', '"const"'):
        assert unsupported not in serialized_schema

    items_ref = schema["properties"]["items"]["$ref"].rsplit("/", 1)[-1]
    items_schema = schema["$defs"][items_ref]
    assert set(items_schema["properties"]) == set(EVIDENCE_ITEM_IDS)
    assert set(items_schema["required"]) == set(EVIDENCE_ITEM_IDS)
    assert items_schema["additionalProperties"] is False
    assert len(responses["evidence_checklist"]["items"]) == 21
    parsed = response_schema.model_validate(responses["evidence_checklist"])
    normalized = _normalize_evidence_checklist_response(
        parsed.model_dump(mode="json"),
        candidate_contracts=contracts,
    )
    assert len(normalized["proposals"]) == 21
    assert {
        item["item_id"]: (item["status"], item["artifact_ids"])
        for item in normalized["proposals"]
    } == {
        item["item_id"]: (item["status"], sorted(item.get("artifact_ids", [])))
        for item in result["checklist"]["items"]
    }
    facts_by_id = {fact["fact_id"]: fact for fact in result["facts"]}
    checklist_by_id = {
        item["item_id"]: item for item in result["checklist"]["items"]
    }
    for item_id, contract in contracts.items():
        linked_fact = facts_by_id[checklist_by_id[item_id]["fact_id"]]
        grounded_artifact_ids = {
            ref["artifact_id"] for ref in linked_fact["source_refs"]
        }
        assert set(contract["candidate_artifact_ids"]) <= grounded_artifact_ids
        assert set(checklist_by_id[item_id]["artifact_ids"]) <= set(
            contract["candidate_artifact_ids"]
        )
    assert contracts["customer_objective"]["candidate_artifact_ids"] == [
        "message"
    ]
    assert contracts["defect_notice"]["candidate_artifact_ids"] == [
        "art_notification"
    ]
    assert contracts["health_safety_statement"]["candidate_artifact_ids"] == [
        "message"
    ]
    assert contracts["settlement_proposal"]["candidate_artifact_ids"] == []

    for item_id, artifact_ids in (
        ("customer_objective", ("art_notification", "message")),
        ("defect_notice", ("art_notification", "message")),
    ):
        fact_unbound = json.loads(json.dumps(responses["evidence_checklist"]))
        fact_unbound["items"][item_id]["selection_id"] = _evidence_selection_id(
            "provided_sufficient", artifact_ids
        )
        with pytest.raises(ValidationError):
            response_schema.model_validate(fact_unbound)

    invalid_reuse = json.loads(json.dumps(responses["evidence_checklist"]))
    invalid_reuse["items"]["lease"]["selection_id"] = invalid_reuse["items"][
        "claim_message"
    ]["selection_id"]
    with pytest.raises(ValidationError):
        response_schema.model_validate(invalid_reuse)

    invalid_status_pair = json.loads(json.dumps(responses["evidence_checklist"]))
    invalid_status_pair["items"]["source_integrity"]["selection_id"] = (
        "provided_sufficient::none"
    )
    with pytest.raises(ValidationError):
        response_schema.model_validate(invalid_status_pair)

    omitted = json.loads(json.dumps(responses["evidence_checklist"]))
    omitted["items"].pop("completion_record")
    with pytest.raises(ValidationError):
        response_schema.model_validate(omitted)


def test_source_schema_finitely_binds_request_artifacts_refs_and_confidence():
    artifact_ids = tuple(f"artifact-{index}" for index in range(6))
    source_ref_ids = ("src-a", "src-b", "src-c")
    response_schema = _bounded_source_integrity_schema(
        artifact_ids=artifact_ids,
        source_ref_ids=source_ref_ids,
    )
    schema = response_schema.model_json_schema()
    proposal = schema["$defs"]["BoundedSourceIntegrityProposal"]
    properties = proposal["properties"]
    assert schema["additionalProperties"] is False
    assert proposal["additionalProperties"] is False
    assert properties["artifact_id"]["enum"] == list(artifact_ids)
    assert properties["source_ref_ids"] == {
        "items": {"enum": list(source_ref_ids), "type": "string"},
        "maxItems": 1,
        "title": "Source Ref Ids",
        "type": "array",
    }
    assert_together_compatible_schema(schema)
    assert properties["confidence_basis_points"]["type"] == "integer"
    assert properties["confidence_basis_points"]["minimum"] == 0
    assert properties["confidence_basis_points"]["maximum"] == 10_000

    valid = [
        {
            "artifact_id": artifact_id,
            "integrity_class": "text_grounded",
            "source_ref_ids": [source_ref_ids[index % len(source_ref_ids)]],
            "confidence_basis_points": 8_100,
        }
        for index, artifact_id in enumerate(artifact_ids)
    ]
    assert len(response_schema.model_validate({"proposals": valid}).proposals) == 6
    malformed = (
        [{**valid[0], "artifact_id": "unknown"}, *valid[1:]],
        [{**valid[0], "source_ref_ids": ["unknown"]}, *valid[1:]],
        [{**valid[0], "source_ref_ids": ["src-a", "src-b"]}, *valid[1:]],
        [{**valid[0], "confidence_basis_points": 10_001}, *valid[1:]],
        [*valid[:-1], dict(valid[0])],
    )
    for proposals in malformed:
        with pytest.raises(ValidationError):
            response_schema.model_validate({"proposals": proposals})


def test_source_role_uses_bounded_reasoning_without_changing_other_roles(monkeypatch):
    captured: list[dict[str, Any]] = []

    def factory(**kwargs):
        captured.append(kwargs)
        return object()

    monkeypatch.setattr(multi_agent_module, "structured_nemotron_runnable", factory)
    _default_runnable_factory(
        "document_source_integrity",
        SourceIntegrityResponse,
        "runtime-only-test-value",
        "orch-source-reasoning",
        ROLE_OUTPUT_TOKENS["document_source_integrity"],
    )
    _default_runnable_factory(
        "process_decision_mapping",
        ProcessDecisionResponse,
        "runtime-only-test-value",
        "orch-process-reasoning",
        ROLE_OUTPUT_TOKENS["process_decision_mapping"],
    )

    assert SOURCE_INTEGRITY_REASONING_EFFORT == "none"
    assert ROLE_REASONING["document_source_integrity"] == {"effort": "none"}
    assert captured[0]["reasoning"] == {"effort": "none"}
    assert captured[0]["max_tokens"] == 4_096
    assert captured[1]["reasoning"] == {"effort": "low"}


@pytest.mark.parametrize("claim_id", sorted(CLAIMS))
def test_governed_claims_share_exact_specialist_candidate_cardinality(
    tmp_path: Path,
    claim_id: str,
):
    storage = Storage(str(tmp_path / f"{claim_id}.db"))
    pipeline = ClaimPipeline(storage, pace_seconds=0)
    run = wait(storage, pipeline.create(claim_id))
    assert run["status"] == "complete", run.get("error")
    result = run["result"]
    package = observable_claim_package(CLAIMS[claim_id])
    assert len(package["artifacts"]) == SOURCE_INTEGRITY_PROPOSAL_COUNT == 6
    assert sum(
        fact.get("controls_process") is True for fact in result["facts"]
    ) == PROCESS_DECISION_PROPOSAL_COUNT == 6
    assert len(result["checklist"]["items"]) == len(EVIDENCE_ITEM_IDS) == 21
    assert {item["item_id"] for item in result["checklist"]["items"]} == set(
        EVIDENCE_ITEM_IDS
    )
    assert tuple(
        item["item_id"] for item in result["checklist"]["items"]
    ) == EVIDENCE_ITEM_IDS_BY_CLAIM[claim_id]
    if claim_id == "DEF-027-E0-DEMO":
        assert EVIDENCE_ITEM_IDS == EVIDENCE_ITEM_IDS_BY_CLAIM[claim_id]


@pytest.mark.parametrize(
    ("agent_id", "invariant"),
    [
        ("document_source_integrity", "source_proposal_membership"),
        ("process_decision_mapping", "process_proposal_membership"),
        ("evidence_checklist", "evidence_proposal_membership"),
    ],
)
def test_coverage_membership_guard_rejects_omissions_unknowns_and_duplicates(
    agent_id: str,
    invariant: str,
):
    expected = {f"candidate-{index}" for index in range(6)}
    malformed = (
        ({key: {} for key in sorted(expected)[:-1]}, 0),
        ({**{key: {} for key in expected}, "unknown": {}}, 0),
        ({key: {} for key in expected}, 1),
    )
    for proposed, duplicates in malformed:
        with pytest.raises(AgentBoundaryError, match=invariant):
            _require_exact_proposal_membership(
                proposed,
                duplicates=duplicates,
                expected_ids=expected,
                agent_id=agent_id,
                invariant=invariant,
            )


def test_evidence_specialist_rejects_empty_native_output_without_cache_or_retry(
    tmp_path: Path,
):
    (
        orchestrator,
        storage,
        captures,
        responses,
        package,
        canonicalization,
        result,
    ) = graph_fixture(tmp_path)
    responses["evidence_checklist"]["items"] = {}

    for ordinal in range(2):
        with pytest.raises(
            AgentInvocationFailure, match="provider_native_schema"
        ):
            orchestrator.invoke(
                run_id=f"run-evidence-empty-{ordinal}",
                orchestration_id=f"orch-evidence-empty-{ordinal}",
                observable_package=package,
                canonicalization=canonicalization,
                facts=result["facts"],
                process=result["process"],
                checklist=result["checklist"],
                verification=result["verification"],
            )

    ledger = [
        item
        for item in storage.model_calls()
        if item["agent_id"] == "evidence_checklist"
    ]
    assert len(ledger) == len(captures["evidence_checklist"]) == 2
    assert len({item["cache_key"] for item in ledger}) == 1
    assert all(item["outcome"] == "failed" for item in ledger)
    assert all(item["call_count"] == 1 for item in ledger)
    assert all(item["error_invariant"] == "provider_native_schema" for item in ledger)
    assert all(item["actual_cost_usd"] == pytest.approx(0.001) for item in ledger)
    assert all(storage.cached_model_output(item["cache_key"]) is None for item in ledger)


def test_evidence_specialist_rejects_cross_slot_and_status_artifact_mismatch(
    tmp_path: Path,
):
    (
        orchestrator,
        storage,
        _captures,
        responses,
        package,
        canonicalization,
        result,
    ) = graph_fixture(tmp_path)
    message_selection = responses["evidence_checklist"]["items"]["claim_message"][
        "selection_id"
    ]
    assert "message" in message_selection
    responses["evidence_checklist"]["items"]["lease"]["selection_id"] = (
        message_selection
    )
    responses["evidence_checklist"]["items"]["source_integrity"][
        "selection_id"
    ] = "provided_sufficient::none"

    with pytest.raises(
        AgentInvocationFailure, match="provider_native_schema"
    ):
        orchestrator.invoke(
            run_id="run-evidence-equal-split",
            orchestration_id="orch-evidence-equal-split",
            observable_package=package,
            canonicalization=canonicalization,
            facts=result["facts"],
            process=result["process"],
            checklist=result["checklist"],
            verification=result["verification"],
        )
    ledger = next(
        item
        for item in storage.model_calls()
        if item["agent_id"] == "evidence_checklist"
    )
    assert ledger["error_invariant"] == "provider_native_schema"
    assert "accepted_item_count" not in ledger
    assert "rejected_item_count" not in ledger
    assert storage.cached_model_output(ledger["cache_key"]) is None


def test_final_specialist_accepts_three_of_five_independent_audit_units(
    tmp_path: Path,
):
    (
        orchestrator,
        _storage,
        _captures,
        responses,
        package,
        canonicalization,
        result,
    ) = graph_fixture(tmp_path)
    proposal = responses["final_claim_brief_audit"]["proposal"]
    proposal["current_node_id"] = "scope"
    supporting_fact_id = proposal["supporting_fact_ids"][0]
    proposal["supporting_fact_ids"] = [supporting_fact_id, supporting_fact_id]

    audit = orchestrator.invoke(
        run_id="run-final-three-of-five",
        orchestration_id="orch-final-three-of-five",
        observable_package=package,
        canonicalization=canonicalization,
        facts=result["facts"],
        process=result["process"],
        checklist=result["checklist"],
        verification=result["verification"],
    )

    final_audit = next(
        item
        for item in audit["agents"]
        if item["agent_id"] == "final_claim_brief_audit"
    )
    assert (final_audit["accepted_count"], final_audit["rejected_count"]) == (
        3,
        2,
    )
    final = audit["final_claim_brief"]
    assert final["attribution"] == "mixed_model_and_deterministic"
    assert final["current_node_id"] == result["process"]["current_node"]
    fields = {item["field"]: item for item in final["field_contributions"]}
    assert fields["current_node_id"]["deterministic_fallback_applied"] is True
    assert fields["supporting_fact_ids"]["deterministic_fallback_applied"] is True
    assert fields["next_action_node_id"]["deterministic_fallback_applied"] is False


def test_final_parent_attribution_is_deterministic_when_no_unit_is_accepted(
    tmp_path: Path, monkeypatch
):
    (
        orchestrator,
        _storage,
        _captures,
        responses,
        package,
        canonicalization,
        result,
    ) = graph_fixture(tmp_path)
    proposal = responses["final_claim_brief_audit"]["proposal"]
    proposal.update(
        {
            "current_node_id": "not-a-current-node",
            "next_action_node_id": "not-a-next-node",
            "supporting_fact_ids": [],
            "upstream_contribution_ids": [],
            "audit_check_ids": [],
        }
    )
    # Bypass only the runner's majority raise so this test can inspect the
    # already-computed, fallback-only aggregate attribution.
    monkeypatch.setattr(
        multi_agent_module,
        "_require_contribution_majority",
        lambda *_args, **_kwargs: None,
    )

    audit = orchestrator.invoke(
        run_id="run-final-zero-of-five-attribution",
        orchestration_id="orch-final-zero-of-five-attribution",
        observable_package=package,
        canonicalization=canonicalization,
        facts=result["facts"],
        process=result["process"],
        checklist=result["checklist"],
        verification=result["verification"],
    )

    final = audit["final_claim_brief"]
    assert final["attribution"] == "deterministic_application"
    assert all(
        item["deterministic_fallback_applied"] is True
        for item in final["field_contributions"]
    )
    final_audit = next(
        item
        for item in audit["agents"]
        if item["agent_id"] == "final_claim_brief_audit"
    )
    assert (final_audit["accepted_count"], final_audit["rejected_count"]) == (
        0,
        5,
    )
    assert audit["all_required_agents_contributed"] is False


def test_hybrid_materializers_rebuild_routes_and_checklist_aggregates_fail_closed(
    tmp_path: Path,
):
    result = oracle_result(tmp_path)
    controlling = [
        fact for fact in result["facts"] if fact["controls_process"] is True
    ]
    process_contribution = {
        "decisions": [
            {
                "fact_id": fact["fact_id"],
                "decision_key": fact["decision_key"],
                "decision_value": fact["decision_value"],
            }
            for fact in controlling
        ]
    }
    poisoned_process = json.loads(json.dumps(result["process"]))
    poisoned_process["current_node"] = "scope"
    poisoned_process["selected_path"] = ["intake", "scope"]
    poisoned_process["current_overlay"] = {
        "completed_node_ids": [],
        "current_node_id": "scope",
        "selected_branch_id": "scope-unverified",
        "blocked_node_ids": [],
        "inactive_branch_ids": [],
        "next_action_node_id": "scope",
        "decisions": {},
    }
    for node in poisoned_process["nodes"]:
        node["state"] = "inactive"
        for branch in node.get("branches", []):
            branch["state"] = "possible"
    for edge in poisoned_process["edges"]:
        edge["state"] = "possible"

    rebuilt_process = apply_process_contribution(
        poisoned_process, process_contribution, result["facts"]
    )
    assert rebuilt_process["current_node"] == result["process"]["current_node"]
    assert rebuilt_process["selected_path"] == result["process"]["selected_path"]
    assert rebuilt_process["current_overlay"] == result["process"][
        "current_overlay"
    ]
    assert [
        (node["node_id"], node["state"], node.get("answer"))
        for node in rebuilt_process["nodes"]
    ] == [
        (node["node_id"], node["state"], node.get("answer"))
        for node in result["process"]["nodes"]
    ]
    tampered_process_contribution = json.loads(json.dumps(process_contribution))
    first = tampered_process_contribution["decisions"][0]
    fact = next(item for item in controlling if item["fact_id"] == first["fact_id"])
    first["decision_value"] = next(
        value
        for value in PROCESS_DECISION_VALUE_CANDIDATES[fact["decision_key"]]
        if value != fact["decision_value"]
    )
    with pytest.raises(AgentBoundaryError, match="canonical_decision_binding"):
        apply_process_contribution(
            result["process"], tampered_process_contribution, result["facts"]
        )

    evidence_contribution = {
        "items": [
            {
                "item_id": item["item_id"],
                "status": item["status"],
                "artifact_ids": sorted(item.get("artifact_ids", [])),
            }
            for item in result["checklist"]["items"]
        ]
    }
    poisoned_checklist = json.loads(json.dumps(result["checklist"]))
    poisoned_checklist["present"] = []
    poisoned_checklist["required"] = []
    poisoned_checklist["summary"] = {"missing": 999}
    rebuilt_checklist = apply_evidence_contribution(
        poisoned_checklist,
        evidence_contribution,
        candidate_artifact_ids_by_item=_evidence_candidate_artifact_ids(
            {
                "observable_package": observable_claim_package(
                    CLAIMS["DEF-027-E0-DEMO"]
                ),
                "source_integrity": {"artifacts": []},
                "facts": result["facts"],
                "checklist": result["checklist"],
            }
        ),
    )
    assert rebuilt_checklist["present"] == result["checklist"]["present"]
    assert rebuilt_checklist["required"] == result["checklist"]["required"]
    assert rebuilt_checklist["summary"] == result["checklist"]["summary"]
    duplicate_evidence = json.loads(json.dumps(evidence_contribution))
    duplicate_artifacts = next(
        item for item in duplicate_evidence["items"] if item["artifact_ids"]
    )
    artifact_id = duplicate_artifacts["artifact_ids"][0]
    duplicate_artifacts["artifact_ids"] = [artifact_id, artifact_id]
    with pytest.raises(AgentBoundaryError, match="evidence_artifact_order"):
        apply_evidence_contribution(
            result["checklist"],
            duplicate_evidence,
            candidate_artifact_ids_by_item=_evidence_candidate_artifact_ids(
                {
                    "observable_package": observable_claim_package(
                        CLAIMS["DEF-027-E0-DEMO"]
                    ),
                    "source_integrity": {"artifacts": []},
                    "facts": result["facts"],
                    "checklist": result["checklist"],
                }
            ),
        )
    tampered_evidence = json.loads(json.dumps(evidence_contribution))
    tampered_evidence["items"][0]["artifact_ids"] = ["art_photo"]
    with pytest.raises(AgentBoundaryError, match="evidence_candidate_binding"):
        apply_evidence_contribution(
            result["checklist"],
            tampered_evidence,
            candidate_artifact_ids_by_item=_evidence_candidate_artifact_ids(
                {
                    "observable_package": observable_claim_package(
                        CLAIMS["DEF-027-E0-DEMO"]
                    ),
                    "source_integrity": {"artifacts": []},
                    "facts": result["facts"],
                    "checklist": result["checklist"],
                }
            ),
        )


def test_valid_alternate_process_decision_changes_path_and_refreshes_verification(
    tmp_path: Path,
):
    (
        orchestrator,
        _storage,
        _captures,
        responses,
        package,
        canonicalization,
        result,
    ) = graph_fixture(tmp_path)
    facts_by_id = {fact["fact_id"]: fact for fact in result["facts"]}
    scope_fact = next(
        fact
        for fact in result["facts"]
        if fact.get("decision_key") == "scope"
    )
    assert scope_fact["decision_value"] != "scope_unverified"
    scope_proposal = next(
        proposal
        for proposal in responses["process_decision_mapping"]["proposals"]
        if proposal["fact_id"] == scope_fact["fact_id"]
    )
    scope_proposal["decision_value"] = "scope_unverified"
    process_contribution = {
        "decisions": [
            {
                "fact_id": proposal["fact_id"],
                "decision_key": facts_by_id[proposal["fact_id"]]["decision_key"],
                "decision_value": proposal["decision_value"],
            }
            for proposal in responses["process_decision_mapping"]["proposals"]
        ]
    }
    expected_process = apply_process_contribution(
        result["process"], process_contribution, result["facts"]
    )
    assert expected_process["selected_path"] != result["process"]["selected_path"]
    assert accepted_artifact_hash(expected_process) != accepted_artifact_hash(
        result["process"]
    )
    expected_checklist = json.loads(json.dumps(result["checklist"]))
    apply_evidence_relations(expected_process, expected_checklist["items"])
    apply_evidence_projection(expected_checklist["items"], expected_process)
    apply_evidence_relations(expected_process, expected_checklist["items"])
    for item in expected_checklist["items"]:
        responses["evidence_checklist"]["items"][item["item_id"]][
            "selection_id"
        ] = _evidence_selection_id(
            item["status"], tuple(sorted(item.get("artifact_ids", [])))
        )
    current_id = expected_process["current_overlay"]["current_node_id"]
    current_node = next(
        node for node in expected_process["nodes"] if node["node_id"] == current_id
    )
    responses["final_claim_brief_audit"]["proposal"].update(
        {
            "current_node_id": current_id,
            "next_action_node_id": expected_process["current_overlay"][
                "next_action_node_id"
            ],
            "supporting_fact_ids": sorted(current_node.get("fact_ids", [])),
        }
    )
    verification_inputs: list[tuple[dict[str, Any], dict[str, Any]]] = []

    def rebuild_verification(
        accepted_process: dict[str, Any], accepted_checklist: dict[str, Any]
    ) -> dict[str, Any]:
        verification_inputs.append(
            (
                json.loads(json.dumps(accepted_process)),
                json.loads(json.dumps(accepted_checklist)),
            )
        )
        fresh = json.loads(json.dumps(result["verification"]))
        fresh["whole_playbook_hash"] = accepted_artifact_hash(
            {
                "process": accepted_process,
                "checklist": accepted_checklist,
            }
        )
        return fresh

    orchestrator.verification_builder = rebuild_verification
    audit = orchestrator.invoke(
        run_id="run-valid-alternate-process",
        orchestration_id="orch-valid-alternate-process",
        observable_package=package,
        canonicalization=canonicalization,
        facts=result["facts"],
        process=result["process"],
        checklist=result["checklist"],
        verification=result["verification"],
    )

    assert verification_inputs
    verified_process, verified_checklist = verification_inputs[-1]
    assert verified_process == expected_process
    fresh_hash = accepted_artifact_hash(
        {"process": verified_process, "checklist": verified_checklist}
    )
    whole_gate = next(
        gate
        for gate in audit["deterministic_gates"]
        if gate["agent_id"] == "whole_playbook_gate"
    )
    assert whole_gate["output_projection_contract"] == (
        "casepath.accepted-playbook-projection/1.0.0"
    )
    assert whole_gate["verification_whole_playbook_hash"] == fresh_hash
    assert whole_gate["verification_whole_playbook_hash"] != result["verification"][
        "whole_playbook_hash"
    ]


def test_valid_alternate_evidence_status_changes_derived_checklist_state(
    tmp_path: Path,
):
    result = oracle_result(tmp_path)
    contribution = {
        "items": [
            {
                "item_id": item["item_id"],
                "status": item["status"],
                "artifact_ids": sorted(item.get("artifact_ids", [])),
            }
            for item in result["checklist"]["items"]
        ]
    }
    chronology = next(
        item
        for item in contribution["items"]
        if item["item_id"] == "recurrence_chronology"
    )
    assert chronology["status"] == "provided_insufficient"
    chronology["status"] = "provided_sufficient"
    candidate_map = _evidence_candidate_artifact_ids(
        {
            "observable_package": observable_claim_package(
                CLAIMS["DEF-027-E0-DEMO"]
            ),
            "source_integrity": {"artifacts": []},
            "facts": result["facts"],
            "checklist": result["checklist"],
        }
    )

    accepted = apply_evidence_contribution(
        result["checklist"],
        contribution,
        candidate_artifact_ids_by_item=candidate_map,
    )

    before_present = next(
        item
        for item in result["checklist"]["present"]
        if item["item_id"] == "recurrence_chronology"
    )
    after_present = next(
        item
        for item in accepted["present"]
        if item["item_id"] == "recurrence_chronology"
    )
    assert before_present["status"] == "insufficient"
    assert after_present["status"] == "available"
    assert accepted["summary"]["provided_sufficient"] == (
        result["checklist"]["summary"]["provided_sufficient"] + 1
    )
    assert accepted["summary"]["provided_insufficient"] == (
        result["checklist"]["summary"]["provided_insufficient"] - 1
    )
    assert accepted_artifact_hash(accepted) != accepted_artifact_hash(
        result["checklist"]
    )


def test_evidence_payload_omits_poisoned_private_answers_and_plan_changes_order(
    tmp_path: Path,
):
    (
        _orchestrator,
        _storage,
        _captures,
        _responses,
        package,
        _canonicalization,
        result,
    ) = graph_fixture(tmp_path)
    registry = _source_registry(package)
    text_artifacts = {
        item["artifact_id"]
        for item in package["artifacts"]
        if item["media_type"] in {"application/pdf", "message/rfc822"}
    }
    focused_sources: list[str] = []
    for artifact_id in sorted(text_artifacts):
        focused_sources.append(
            next(
                item["source_ref_id"]
                for item in registry
                if item["artifact_id"] == artifact_id
            )
        )
    poisoned = json.loads(json.dumps(result["checklist"]))
    for item in poisoned["items"]:
        item["why"] = "PRIVATE_WHY_SENTINEL"
        item["status"] = "PRIVATE_STATUS_SENTINEL"
        item["artifact_ids"] = ["PRIVATE_EXPECTED_ARTIFACT_SENTINEL"]
    fact_ids = [item["fact_id"] for item in result["facts"]]
    task_codes = [
        "source_integrity",
        "process_decisions",
        "evidence_gaps",
        "final_brief",
    ]

    def payload(fact_order, task_order):
        return _evidence_provider_payload(
            {
                "orchestrator_plan": {
                    "focus_fact_ids": fact_order,
                    "focus_source_ref_ids": focused_sources,
                    "priority_task_codes": task_order,
                },
                "source_integrity": {"artifacts": []},
                "process": result["process"],
                "checklist": poisoned,
                "facts": result["facts"],
                "source_registry": registry,
                "observable_package": package,
            }
        )

    forward = payload(fact_ids, task_codes)
    reverse = payload(list(reversed(fact_ids)), list(reversed(task_codes)))
    serialized = json.dumps(forward, sort_keys=True)
    for sentinel in (
        "PRIVATE_WHY_SENTINEL",
        "PRIVATE_STATUS_SENTINEL",
        "PRIVATE_EXPECTED_ARTIFACT_SENTINEL",
    ):
        assert sentinel not in serialized
    assert all(
        set(item)
        == {
            "item_id",
            "title",
            "fact_id",
            "node_id",
            "legal_basis_ids",
            "acceptable_alternatives",
            "applies_when",
            "required_level",
            "current_path",
            "candidate_artifact_ids",
            "status_choices",
        }
        for item in forward["evidence_candidates"]
    )
    assert {
        item["item_id"] for item in forward["evidence_candidates"]
    } == {item["item_id"] for item in reverse["evidence_candidates"]}
    assert forward["evidence_candidates"] != reverse["evidence_candidates"]
    assert forward["orchestrator_focus"]["task_code"] == "evidence_gaps"
    assert forward["orchestrator_focus"]["priority_rank"] == 2
    assert reverse["orchestrator_focus"]["priority_rank"] == 1


def test_final_audit_payload_ignores_applied_answers_but_tracks_prior_contributions(
    tmp_path: Path,
):
    (
        orchestrator,
        _storage,
        _captures,
        _responses,
        package,
        canonicalization,
        result,
    ) = graph_fixture(tmp_path)
    audit = orchestrator.invoke(
        run_id="run-final-payload",
        orchestration_id="orch-final-payload",
        observable_package=package,
        canonicalization=canonicalization,
        facts=result["facts"],
        process=result["process"],
        checklist=result["checklist"],
        verification=result["verification"],
    )
    artifacts = audit["specialist_artifacts"]
    state = {
        "orchestrator_plan": artifacts["orchestrator_plan"],
        "source_integrity": artifacts["document_source_integrity"],
        "process_mapping": artifacts["process_decision_mapping"],
        "evidence_checklist": artifacts["evidence_checklist"],
        "facts": result["facts"],
        "process": result["process"],
        "checklist": result["checklist"],
        "verification": result["verification"],
        "source_registry": _source_registry(package),
    }
    baseline = _final_brief_provider_payload(state)
    assert set(baseline) == {
        "orchestrator_focus",
        "accepted_process_gate_handoff",
        "accepted_evidence_gate_handoff",
        "static_process_topology",
        "canonical_fact_handoff",
        "prior_accepted_contributions",
        "audit_check_candidates",
    }
    assert baseline["accepted_process_gate_handoff"] == {
        "gate_id": "deterministic_process_gate",
        "current_overlay": result["process"]["current_overlay"],
    }
    assert baseline["accepted_evidence_gate_handoff"]["gate_id"] == (
        "deterministic_evidence_gate"
    )
    assert set(baseline["static_process_topology"]) == {
        "nodes",
        "edges",
        "evidence_bindings",
    }
    assert all(
        set(item) == {
            "node_id",
            "title",
            "kind",
            "main_spine",
            "fact_ids",
            "activation",
            "branches",
        }
        for item in baseline["static_process_topology"]["nodes"]
    )
    assert all(
        set(item) == {"source", "target", "condition"}
        for item in baseline["static_process_topology"]["edges"]
    )
    assert all(
        set(item) == {"item_id", "fact_id", "node_id"}
        for item in baseline["static_process_topology"]["evidence_bindings"]
    )
    poisoned = json.loads(json.dumps(state))
    poison_values = {
        "state": "PRIVATE_APPLIED_STATE_SENTINEL",
        "answer": "PRIVATE_APPLIED_ANSWER_SENTINEL",
        "why": "PRIVATE_APPLIED_WHY_SENTINEL",
        "status": "PRIVATE_APPLIED_STATUS_SENTINEL",
        "current_path": "PRIVATE_CURRENT_PATH_SENTINEL",
        "artifact_ids": ["PRIVATE_EXPECTED_ARTIFACT_SENTINEL"],
        "name": "PRIVATE_VERIFICATION_NAME_SENTINEL",
    }

    def recursively_poison(value):
        if isinstance(value, dict):
            return {
                key: poison_values[key]
                if key in poison_values
                else recursively_poison(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [recursively_poison(item) for item in value]
        return value

    poisoned["process"] = recursively_poison(poisoned["process"])
    poisoned["checklist"] = recursively_poison(poisoned["checklist"])
    poisoned["verification"] = {
        "PRIVATE_VERIFICATION_OBJECT_SENTINEL": recursively_poison(
            poisoned["verification"]
        )
    }

    poisoned_payload = _final_brief_provider_payload(poisoned)
    assert poisoned_payload == baseline
    serialized = json.dumps(poisoned_payload, sort_keys=True)
    assert all(
        sentinel not in serialized
        for value in poison_values.values()
        for sentinel in ([value] if isinstance(value, str) else value)
    )
    for sentinel in ("PRIVATE_VERIFICATION_OBJECT_SENTINEL",):
        assert sentinel not in serialized
    assert all("state" not in item for item in baseline["static_process_topology"]["nodes"])
    assert all("state" not in item for item in baseline["static_process_topology"]["edges"])
    assert all(
        "state" not in branch
        for item in baseline["static_process_topology"]["nodes"]
        for branch in item["branches"]
    )
    assert set(baseline["prior_accepted_contributions"]["evidence_checklist"]) == {
        "item_ids",
        "source_ref_ids",
        "fallback_item_ids",
    }
    assert "contribution_candidates" not in baseline
    assert "relied_on_contribution_ids" not in serialized
    assert "source_reference_registry" not in baseline
    assert "excerpt" not in serialized

    unreferenced = json.loads(json.dumps(state))
    unreferenced["source_registry"].append(
        {
            "source_ref_id": "src_unreferenced_private_sentinel",
            "artifact_id": "PRIVATE_UNREFERENCED_ARTIFACT_SENTINEL",
            "page": 1,
            "excerpt": "PRIVATE_UNREFERENCED_EXCERPT_SENTINEL",
        }
    )
    assert _final_brief_provider_payload(unreferenced) == baseline

    counterfactual = json.loads(json.dumps(state))
    counterfactual["process_mapping"]["decisions"][0][
        "normalized_value"
    ] = "counterfactual_bounded_value"
    counterfactual_payload = _final_brief_provider_payload(counterfactual)
    assert counterfactual_payload["prior_accepted_contributions"][
        "process_decision_mapping"
    ] != baseline["prior_accepted_contributions"]["process_decision_mapping"]
    assert {
        key: value
        for key, value in counterfactual_payload.items()
        if key != "prior_accepted_contributions"
    } == {
        key: value
        for key, value in baseline.items()
        if key != "prior_accepted_contributions"
    }


def test_shared_langchain_adapter_has_exact_nonretrying_private_configuration(monkeypatch):
    sdk_kwargs: dict[str, Any] = {}
    chat_kwargs: dict[str, Any] = {}
    structured_kwargs: dict[str, Any] = {}

    class FakeProviderClient:
        def __init__(self, **kwargs):
            sdk_kwargs.update(kwargs)
            self.chat = object()

    class FakeChatOpenRouter:
        def __init__(self, **kwargs):
            chat_kwargs.update(kwargs)

        def with_structured_output(self, schema, **kwargs):
            structured_kwargs.update({"schema": schema, **kwargs})
            return object()

    monkeypatch.setattr(langchain_runtime, "OpenRouter", FakeProviderClient)
    monkeypatch.setattr(langchain_runtime, "ChatOpenRouter", FakeChatOpenRouter)
    schema = {"type": "object", "properties": {}, "additionalProperties": False}
    langchain_runtime.structured_nemotron_runnable(
        schema=schema,
        api_key="runtime-only-test-value",
        orchestration_id="orch-adapter",
        max_tokens=777,
    )

    assert sdk_kwargs["retry_config"] is None
    assert sdk_kwargs["timeout_ms"] == 180_000
    assert sdk_kwargs["x_open_router_title"] == "CasePath"
    assert "client" not in sdk_kwargs
    assert langchain_runtime.OPENROUTER_ENDPOINT_TAG == "together"
    assert chat_kwargs["model"] == OPENROUTER_MODEL
    assert chat_kwargs["max_retries"] == 0
    assert chat_kwargs["timeout"] == 180_000
    assert chat_kwargs["max_tokens"] == 777
    assert chat_kwargs["reasoning"] == {"effort": "low"}
    assert set(chat_kwargs["reasoning"]) == {"effort"}
    assert chat_kwargs["openrouter_provider"] == {
        "only": ["together"],
        "allow_fallbacks": False,
        "require_parameters": True,
        "data_collection": "deny",
    }
    assert "model_kwargs" not in chat_kwargs
    assert chat_kwargs["openrouter_provider"] is not langchain_runtime.OPENROUTER_PROVIDER_POLICY
    assert (
        chat_kwargs["openrouter_provider"]["only"]
        is not langchain_runtime.OPENROUTER_PROVIDER_POLICY["only"]
    )
    assert components.ProviderPreferences.model_validate(
        chat_kwargs["openrouter_provider"]
    ).model_dump(exclude_none=True, by_alias=True) == {
        "only": ["together"],
        "allow_fallbacks": False,
        "require_parameters": True,
        "data_collection": "deny",
    }
    assert isinstance(chat_kwargs["client"], langchain_runtime._OpenRouterClientBridge)
    assert chat_kwargs["client"].chat._chat.__class__ is object
    assert (
        chat_kwargs["client"].chat._send_limiter
        is langchain_runtime._OPENROUTER_SEND_LIMITER
    )
    assert langchain_runtime.OPENROUTER_PROVIDER_MAX_IN_FLIGHT == 1
    assert "trace" not in chat_kwargs
    assert structured_kwargs == {
        "schema": schema,
        "method": "json_schema",
        "strict": True,
        "include_raw": True,
    }


def test_shared_send_bridge_serializes_physical_sends_across_clients():
    limiter = langchain_runtime._OpenRouterSendLimiter(
        max_in_flight=1,
        admission_timeout_seconds=1,
    )
    state_lock = threading.Lock()
    release_first = threading.Event()
    first_entered = threading.Event()
    start = threading.Barrier(3)
    calls = 0
    active = 0
    peak_active = 0
    results: list[dict[str, Any]] = []

    class Chat:
        def send(self, **_kwargs):
            nonlocal calls, active, peak_active
            with state_lock:
                calls += 1
                ordinal = calls
                active += 1
                peak_active = max(peak_active, active)
            if ordinal == 1:
                first_entered.set()
                assert release_first.wait(timeout=1)
            with state_lock:
                active -= 1
            return {"ordinal": ordinal}

    bridges = [
        langchain_runtime._ChatSendBridge(Chat(), send_limiter=limiter),
        langchain_runtime._ChatSendBridge(Chat(), send_limiter=limiter),
    ]

    def invoke(bridge):
        start.wait(timeout=1)
        results.append(bridge.send(messages=[]))

    workers = [threading.Thread(target=invoke, args=(bridge,)) for bridge in bridges]
    for worker in workers:
        worker.start()
    start.wait(timeout=1)
    assert first_entered.wait(timeout=1)
    time.sleep(0.02)
    with state_lock:
        assert calls == 1
        assert active == 1
    release_first.set()
    for worker in workers:
        worker.join(timeout=1)
        assert not worker.is_alive()

    assert calls == 2
    assert peak_active == 1
    assert sorted(item["ordinal"] for item in results) == [1, 2]


def test_shared_send_bridge_admission_timeout_never_calls_waiting_client():
    limiter = langchain_runtime._OpenRouterSendLimiter(
        max_in_flight=1,
        admission_timeout_seconds=0.02,
    )
    first_entered = threading.Event()
    release_first = threading.Event()
    waiting_calls = 0

    class BlockingChat:
        def send(self, **_kwargs):
            first_entered.set()
            assert release_first.wait(timeout=1)
            return {"status": "complete"}

    class WaitingChat:
        def send(self, **_kwargs):
            nonlocal waiting_calls
            waiting_calls += 1
            return {"status": "unexpected"}

    holding_bridge = langchain_runtime._ChatSendBridge(
        BlockingChat(), send_limiter=limiter
    )
    waiting_bridge = langchain_runtime._ChatSendBridge(
        WaitingChat(), send_limiter=limiter
    )
    worker = threading.Thread(target=lambda: holding_bridge.send(messages=[]))
    worker.start()
    assert first_entered.wait(timeout=1)

    with pytest.raises(
        langchain_runtime.OpenRouterSendAdmissionTimeoutError,
        match="admission timed out",
    ) as captured:
        waiting_bridge.send(messages=[])

    assert captured.value.invariant == "provider_concurrency_timeout"
    assert waiting_calls == 0
    release_first.set()
    worker.join(timeout=1)
    assert not worker.is_alive()


def test_specialist_admission_timeout_is_zero_call_noncacheable_ledger_record(
    tmp_path: Path,
):
    class Runnable:
        def invoke(self, *_args, **_kwargs):
            raise langchain_runtime.OpenRouterSendAdmissionTimeoutError()

    storage = Storage(str(tmp_path / "provider-concurrency-timeout.db"))
    runner = InstrumentedStructuredAgent(
        storage,
        runnable_factory=lambda *_args: Runnable(),
        api_key_provider=lambda: "runtime-only-test-value",
    )

    with pytest.raises(
        AgentInvocationFailure,
        match="provider_concurrency_timeout",
    ) as captured:
        _invoke_plan(runner, run_id="run-provider-concurrency-timeout")

    assert captured.value.safe_context["outcome"] == "blocked_provider_concurrency"
    ledger = storage.model_calls()[0]
    assert ledger["call_count"] == 0
    assert ledger["outcome"] == "blocked_provider_concurrency"
    assert ledger["actual_cost_usd"] is None
    assert ledger["error_invariant"] == "provider_concurrency_timeout"
    assert storage.model_call_summary()["network_calls"] == 0
    assert storage.model_call_summary()["unknown_cost_call_count"] == 0
    assert storage.model_cost_committed_or_reserved() == 0
    assert storage.cached_model_output(ledger["cache_key"]) is None


def test_shared_runnable_forwards_exact_private_route_in_one_sdk_send(monkeypatch):
    requests: list[httpx.Request] = []
    sdk_clients: list[httpx.Client] = []
    real_client = httpx.Client
    real_openrouter = OpenRouter

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={
                "id": "gen-exact-route-1",
                "model": OPENROUTER_MODEL,
                "object": "chat.completion",
                "created": 1786483159,
                "system_fingerprint": None,
                "openrouter_metadata": {
                    "attempt": 1,
                    "endpoints": {
                        "available": [
                            {
                                "model": OPENROUTER_MODEL,
                                "provider": "Together",
                                "selected": True,
                            }
                        ],
                        "total": 1,
                    },
                    "is_byok": False,
                    "region": None,
                    "requested": OPENROUTER_MODEL,
                    "strategy": "direct",
                    "summary": "RAW_ROUTER_SUMMARY_SENTINEL",
                },
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({"answer": "bounded"}),
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 2,
                    "total_tokens": 12,
                    "cost": 0.001,
                },
            },
        )

    def instrumented_openrouter(**kwargs):
        client = real_client(transport=httpx.MockTransport(handler))
        sdk_clients.append(client)
        return real_openrouter(client=client, **kwargs)

    monkeypatch.setattr(langchain_runtime, "OpenRouter", instrumented_openrouter)
    runnable = langchain_runtime.structured_nemotron_runnable(
        schema={
            "title": "exact_route_test",
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
            "additionalProperties": False,
        },
        api_key="runtime-only-test-value",
        orchestration_id="orch-exact-route",
        max_tokens=100,
    )

    envelope = runnable.invoke(
        [HumanMessage(content="Return the bounded object")],
        config={"callbacks": []},
    )

    assert envelope["parsed"] == {"answer": "bounded"}
    assert envelope["raw"].response_metadata["provider_name"] == "Together"
    assert "RAW_ROUTER_SUMMARY_SENTINEL" not in repr(
        envelope["raw"].response_metadata
    )
    assert len(requests) == 1
    body = json.loads(requests[0].content)
    assert body["model"] == OPENROUTER_MODEL
    assert body["provider"] == {
        "only": ["together"],
        "allow_fallbacks": False,
        "require_parameters": True,
        "data_collection": "deny",
    }
    assert body["reasoning"] == {"effort": "low"}
    assert "max_tokens" not in body["reasoning"]
    assert "exclude" not in body["reasoning"]
    assert "x_open_router_metadata" not in body
    assert "models" not in body
    assert "trace" not in body
    assert requests[0].headers["X-OpenRouter-Metadata"] == "enabled"
    assert len(sdk_clients) == 1
    sdk_clients[0].close()


def test_source_role_wire_request_is_finite_strict_and_disables_reasoning(
    monkeypatch,
):
    requests: list[httpx.Request] = []
    sdk_clients: list[httpx.Client] = []
    real_client = httpx.Client
    real_openrouter = OpenRouter
    artifact_ids = tuple(f"artifact-{index}" for index in range(6))
    source_ref_ids = ("source-a", "source-b", "source-c")
    response_schema = _bounded_source_integrity_schema(
        artifact_ids=artifact_ids,
        source_ref_ids=source_ref_ids,
    )
    parsed = {
        "proposals": [
            {
                "artifact_id": artifact_id,
                "integrity_class": "metadata_only",
                "source_ref_ids": [],
                "confidence_basis_points": 8_100,
            }
            for artifact_id in artifact_ids
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={
                "id": "gen-source-wire-1",
                "model": OPENROUTER_MODEL,
                "object": "chat.completion",
                "created": 1786533000,
                "system_fingerprint": None,
                "openrouter_metadata": {
                    "attempt": 1,
                    "endpoints": {
                        "available": [
                            {
                                "model": OPENROUTER_MODEL,
                                "provider": "Together",
                                "selected": True,
                            }
                        ],
                        "total": 1,
                    },
                    "is_byok": False,
                    "region": None,
                    "requested": OPENROUTER_MODEL,
                    "strategy": "direct",
                    "summary": "",
                },
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(parsed),
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 20,
                    "completion_tokens": 100,
                    "total_tokens": 120,
                    "cost": 0.001,
                },
            },
        )

    def instrumented_openrouter(**kwargs):
        client = real_client(transport=httpx.MockTransport(handler))
        sdk_clients.append(client)
        return real_openrouter(client=client, **kwargs)

    monkeypatch.setattr(langchain_runtime, "OpenRouter", instrumented_openrouter)
    runnable = _default_runnable_factory(
        "document_source_integrity",
        response_schema,
        "runtime-only-test-value",
        "orch-source-wire",
        ROLE_OUTPUT_TOKENS["document_source_integrity"],
    )

    envelope = runnable.invoke(
        [HumanMessage(content="Return the bounded source object")],
        config={"callbacks": []},
    )

    assert len(envelope["parsed"].proposals) == 6
    assert len(requests) == 1
    body = json.loads(requests[0].content)
    assert body["max_tokens"] == 4_096
    assert body["reasoning"] == {"effort": "none"}
    assert body["provider"] == {
        "only": ["together"],
        "allow_fallbacks": False,
        "require_parameters": True,
        "data_collection": "deny",
    }
    native_schema = body["response_format"]["json_schema"]["schema"]
    assert "$defs" not in json.dumps(native_schema)
    proposal = native_schema["properties"]["proposals"]
    assert proposal["minItems"] == proposal["maxItems"] == 6
    properties = proposal["items"]["properties"]
    assert properties["artifact_id"]["enum"] == list(artifact_ids)
    assert properties["source_ref_ids"]["items"]["enum"] == list(
        source_ref_ids
    )
    assert properties["source_ref_ids"]["maxItems"] == 1
    assert properties["confidence_basis_points"] == {
        "maximum": 10_000,
        "minimum": 0,
        "type": "integer",
    }
    assert native_schema["additionalProperties"] is False
    assert proposal["items"]["additionalProperties"] is False
    for client in sdk_clients:
        client.close()


def _native_response_payload() -> dict[str, Any]:
    return {
        "id": "gen-response-bridge-123",
        "model": OPENROUTER_MODEL,
        "object": "chat.completion",
        "created": 1786479000,
        # OpenRouter legitimately omits this nullable field; openrouter==0.11.46
        # nevertheless declares it required in its generated ChatResult model.
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": json.dumps({"answer": "bounded"}),
                },
            }
        ],
        "usage": {
            "prompt_tokens": 120,
            "completion_tokens": 30,
            "total_tokens": 150,
            "cost": 0.0042,
            "cost_details": {"provider_authored_extra": "RAW_USAGE_SENTINEL"},
        },
    }


def _http_response(
    body: str,
    *,
    status: int = 200,
    content_type: str = "application/json",
    headers: dict[str, str] | None = None,
):
    return httpx.Response(
        status,
        headers={"content-type": content_type, **(headers or {})},
        content=body.encode("utf-8"),
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
    )


def test_response_bridge_recovers_sdk_schema_drift_through_langchain_once():
    payload = _native_response_payload()

    class GeneratedSdkChat:
        calls = 0

        def send(self, **kwargs):
            self.calls += 1
            response = _http_response(json.dumps(payload))
            return unmarshal_json_response(components.ChatResult, response)

    chat = GeneratedSdkChat()
    client = type("ProviderClient", (), {"chat": chat})()
    model = langchain_runtime.ChatOpenRouter(
        model=OPENROUTER_MODEL,
        api_key="runtime-only-test-value",
        client=langchain_runtime._OpenRouterClientBridge(client),
        temperature=0,
        max_tokens=100,
        max_retries=0,
    )
    runnable = model.with_structured_output(
        {
            "title": "response_bridge_test",
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
            "additionalProperties": False,
        },
        method="json_schema",
        strict=True,
        include_raw=True,
    )

    envelope = runnable.invoke(
        [HumanMessage(content="Return the bounded test object")],
        config={"callbacks": []},
    )

    assert chat.calls == 1
    assert envelope["parsed"] == {"answer": "bounded"}
    assert envelope["parsing_error"] is None
    raw = envelope["raw"]
    assert raw.response_metadata["id"] == payload["id"]
    assert raw.response_metadata["model_name"] == OPENROUTER_MODEL
    assert raw.response_metadata["finish_reason"] == "stop"
    assert raw.response_metadata["cost"] == 0.0042
    assert raw.usage_metadata == {
        "input_tokens": 120,
        "output_tokens": 30,
        "total_tokens": 150,
    }
    assert "cost_details" not in raw.response_metadata
    assert "RAW_USAGE_SENTINEL" not in repr(raw.response_metadata)


def test_response_bridge_projects_text_content_parts_through_langchain_once():
    payload = _native_response_payload()
    payload["choices"][0]["message"]["content"] = [
        {"type": "text", "text": json.dumps({"answer": "bounded-parts"})}
    ]

    class GeneratedSdkChat:
        calls = 0

        def send(self, **_kwargs):
            self.calls += 1
            response = _http_response(json.dumps(payload))
            return unmarshal_json_response(components.ChatResult, response)

    chat = GeneratedSdkChat()
    client = type("ProviderClient", (), {"chat": chat})()
    model = langchain_runtime.ChatOpenRouter(
        model=OPENROUTER_MODEL,
        api_key="runtime-only-test-value",
        client=langchain_runtime._OpenRouterClientBridge(client),
        temperature=0,
        max_tokens=100,
        max_retries=0,
    )
    runnable = model.with_structured_output(
        {
            "title": "response_bridge_text_parts_test",
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
            "additionalProperties": False,
        },
        method="json_schema",
        strict=True,
        include_raw=True,
    )

    envelope = runnable.invoke(
        [HumanMessage(content="Return the bounded test object")],
        config={"callbacks": []},
    )

    assert chat.calls == 1
    assert envelope["parsed"] == {"answer": "bounded-parts"}
    assert envelope["parsing_error"] is None
    assert envelope["raw"].response_metadata["id"] == payload["id"]
    assert envelope["raw"].usage_metadata == {
        "input_tokens": 120,
        "output_tokens": 30,
        "total_tokens": 150,
    }


def test_response_bridge_recovers_nullable_content_as_bounded_failed_finish():
    payload = _native_response_payload()
    payload["choices"][0]["finish_reason"] = "error"
    payload["choices"][0]["message"]["content"] = None
    payload["choices"][0]["error"] = {"message": "RAW_NULL_CONTENT_SENTINEL"}

    class GeneratedSdkChat:
        calls = 0

        def send(self, **_kwargs):
            self.calls += 1
            response = _http_response(json.dumps(payload))
            return unmarshal_json_response(components.ChatResult, response)

    chat = GeneratedSdkChat()
    client = type("ProviderClient", (), {"chat": chat})()
    recovered = langchain_runtime._OpenRouterClientBridge(client).chat.send(messages=[])

    assert chat.calls == 1
    assert recovered["id"] == payload["id"]
    assert recovered["model"] == payload["model"]
    assert recovered["choices"][0]["finish_reason"] == "error"
    assert recovered["choices"][0]["message"]["content"] == ""
    assert recovered["usage"] == {
        "prompt_tokens": 120,
        "completion_tokens": 30,
        "total_tokens": 150,
        "cost": 0.0042,
    }
    assert "RAW_NULL_CONTENT_SENTINEL" not in repr(recovered)


def test_response_bridge_passes_through_sdk_validated_results_by_identity():
    payload = {**_native_response_payload(), "system_fingerprint": None}
    expected = unmarshal_json_response(
        components.ChatResult,
        _http_response(json.dumps(payload)),
    )

    class PassingChat:
        calls = 0

        def send(self, **kwargs):
            self.calls += 1
            return expected

    chat = PassingChat()
    bridge = langchain_runtime._ChatSendBridge(chat)

    assert bridge.send(messages=[]) is expected
    assert chat.calls == 1


@pytest.mark.parametrize("variant", ["missing", "odd"])
def test_response_bridge_ignores_nonconsumed_envelope_field_drift(variant):
    payload = _native_response_payload()
    if variant == "missing":
        payload.pop("created")
        payload.pop("object")
        payload["choices"][0].pop("index")
    else:
        payload["created"] = "RAW_CREATED_SENTINEL"
        payload["object"] = {"raw": "RAW_OBJECT_SENTINEL"}
        payload["choices"][0]["index"] = True
    body = json.dumps(payload)

    class RejectingSdkChat:
        calls = 0

        def send(self, **_kwargs):
            self.calls += 1
            response = _http_response(body)
            raise errors.ResponseValidationError(
                "RAW_FIELD_DRIFT_SENTINEL",
                response,
                ValueError("RAW_FIELD_DRIFT_SENTINEL"),
                body,
            )

    chat = RejectingSdkChat()
    recovered = langchain_runtime._ChatSendBridge(chat).send(messages=[])

    assert chat.calls == 1
    assert recovered["id"] == payload["id"]
    assert recovered["model"] == payload["model"]
    assert "created" not in recovered
    assert "object" not in recovered
    assert "index" not in recovered["choices"][0]
    assert "RAW_" not in repr(recovered)


@pytest.mark.parametrize(
    ("generation_id", "error_code", "expected_context"),
    [
        (
            "gen-1786483159-hyYthqPv76o6PHXpGLzl",
            400,
            {
                "response_id": "gen-1786483159-hyYthqPv76o6PHXpGLzl",
                "provider_error_code": 400,
                "provider_boundary": "openrouter",
                "expected_upstream_provider": "Together",
            },
        ),
        (
            "DEF-027-E0-DEMO",
            400,
            {
                "provider_error_code": 400,
                "provider_boundary": "openrouter",
                "expected_upstream_provider": "Together",
            },
        ),
        (
            "DOC-8842-INSPECTION",
            400,
            {
                "provider_error_code": 400,
                "provider_boundary": "openrouter",
                "expected_upstream_provider": "Together",
            },
        ),
        (
            "REVGLTAyNy1FMC1ERU1P",
            400,
            {
                "provider_error_code": 400,
                "provider_boundary": "openrouter",
                "expected_upstream_provider": "Together",
            },
        ),
        (
            "Bearer RAW_HEADER_SENTINEL",
            100_000,
            {
                "provider_boundary": "openrouter",
                "expected_upstream_provider": "Together",
            },
        ),
    ],
)
def test_response_bridge_classifies_top_level_upstream_rejection_without_raw(
    generation_id,
    error_code,
    expected_context,
):
    body = json.dumps(
        {
            "error": {
                "code": error_code,
                "message": "RAW_UPSTREAM_REJECTION_SENTINEL",
                "metadata": {"raw": "RAW_UPSTREAM_METADATA_SENTINEL"},
            }
        }
    )

    class RejectingSdkChat:
        calls = 0

        def send(self, **_kwargs):
            self.calls += 1
            response = _http_response(
                body,
                headers={"X-Generation-Id": generation_id},
            )
            return unmarshal_json_response(components.ChatResult, response)

    chat = RejectingSdkChat()
    with pytest.raises(
        langchain_runtime.OpenRouterUpstreamRejectionError
    ) as captured:
        langchain_runtime._ChatSendBridge(chat).send(messages=[])

    assert chat.calls == 1
    assert captured.value.invariant == "provider_upstream_rejection"
    assert captured.value.safe_context == expected_context
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    assert "RAW_" not in str(captured.value)
    assert "RAW_" not in repr(captured.value)
    assert "RAW_" not in repr(captured.value.safe_context)


@pytest.mark.parametrize(
    ("generation_id", "expected_response_id"),
    [
        ("gen-1786483164-EEEEEEEEEEEEEEEEEEEE", "gen-1786483164-EEEEEEEEEEEEEEEEEEEE"),
        ("Bearer RAW_HEADER_SENTINEL", None),
    ],
)
def test_response_bridge_classifies_sdk_429_once_without_raw_provider_material(
    generation_id,
    expected_response_id,
):
    body = json.dumps(
        {
            "error": {
                "code": 429,
                "message": "RAW_RATE_LIMIT_BODY_SENTINEL",
                "metadata": {"secret": "sk-or-RAW_SECRET_SENTINEL"},
            }
        }
    )

    class RejectingSdkChat:
        calls = 0

        def send(self, **_kwargs):
            self.calls += 1
            response = _http_response(
                body,
                status=429,
                headers={
                    "X-Generation-Id": generation_id,
                    "X-Provider-Secret": "RAW_RESPONSE_HEADER_SENTINEL",
                },
            )
            data = errors.TooManyRequestsResponseErrorData(
                error={
                    "code": 429,
                    "message": "RAW_RATE_LIMIT_MESSAGE_SENTINEL",
                    "metadata": {"secret": "RAW_ERROR_DATA_SENTINEL"},
                }
            )
            raise errors.TooManyRequestsResponseError(data, response, body)

    chat = RejectingSdkChat()
    with pytest.raises(
        langchain_runtime.OpenRouterUpstreamRejectionError
    ) as captured:
        langchain_runtime._ChatSendBridge(chat).send(messages=[])

    expected_context = {
        "provider_error_code": 429,
        "provider_boundary": "openrouter",
        "expected_upstream_provider": "Together",
    }
    if expected_response_id is not None:
        expected_context["response_id"] = expected_response_id
    assert chat.calls == 1
    assert captured.value.invariant == "provider_upstream_rejection"
    assert captured.value.safe_context == expected_context
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    serialized = json.dumps(captured.value.safe_context)
    assert "upstream_provider" not in captured.value.safe_context
    assert "RAW_" not in serialized
    assert "sk-or-" not in serialized


@pytest.mark.parametrize(
    ("body", "status", "content_type"),
    [
        ("RAW_PROTOCOL_SENTINEL", 200, "application/json"),
        ('{"id":"a","id":"b"}', 200, "application/json"),
        ('{"value":NaN}', 200, "application/json"),
        (json.dumps({**_native_response_payload(), "choices": []}), 200, "application/json"),
        (
            json.dumps(
                {
                    **_native_response_payload(),
                    "choices": [
                        {
                            **_native_response_payload()["choices"][0],
                            "message": {
                                "role": "assistant",
                                "content": [
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": "RAW_MULTIMODAL_SENTINEL"
                                        },
                                    }
                                ],
                            },
                        }
                    ],
                }
            ),
            200,
            "application/json",
        ),
        (
            json.dumps(
                {
                    **_native_response_payload(),
                    "choices": [
                        {
                            **_native_response_payload()["choices"][0],
                            "message": {
                                "role": "assistant",
                                "content": [
                                    {"type": "text", "text": "x"}
                                    for _ in range(
                                        langchain_runtime.OPENROUTER_RESPONSE_TEXT_PART_LIMIT
                                        + 1
                                    )
                                ],
                            },
                        }
                    ],
                }
            ),
            200,
            "application/json",
        ),
        (json.dumps({key: value for key, value in _native_response_payload().items() if key != "id"}), 200, "application/json"),
        (json.dumps({key: value for key, value in _native_response_payload().items() if key != "model"}), 200, "application/json"),
        (json.dumps(_native_response_payload()), 200, "text/plain"),
        ("x" * (langchain_runtime.OPENROUTER_RESPONSE_BODY_LIMIT_BYTES + 1), 200, "application/json"),
        ("[" * 20_000 + "0" + "]" * 20_000, 200, "application/json"),
    ],
)
def test_response_bridge_fails_bounded_without_raw_exception_chain(
    body: str,
    status: int,
    content_type: str,
):
    class RejectingSdkChat:
        calls = 0

        def send(self, **kwargs):
            self.calls += 1
            response = _http_response(body, status=status, content_type=content_type)
            raise errors.ResponseValidationError(
                "RAW_PROTOCOL_SENTINEL",
                response,
                ValueError("RAW_PROTOCOL_SENTINEL"),
                body,
            )

    chat = RejectingSdkChat()
    bridge = langchain_runtime._ChatSendBridge(chat)

    with pytest.raises(langchain_runtime.OpenRouterProtocolError) as captured:
        bridge.send(messages=[])

    assert chat.calls == 1
    assert captured.value.invariant == "provider_response_envelope"
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    assert "RAW_PROTOCOL_SENTINEL" not in str(captured.value)
    assert "RAW_PROTOCOL_SENTINEL" not in repr(captured.value)


def test_response_bridge_classifies_non_2xx_validation_failure_without_body():
    body = "RAW_MALFORMED_503_BODY_SENTINEL"

    class RejectingSdkChat:
        calls = 0

        def send(self, **_kwargs):
            self.calls += 1
            response = _http_response(
                body,
                status=503,
                content_type="text/plain",
                headers={"X-Generation-Id": "Bearer RAW_503_HEADER_SENTINEL"},
            )
            raise errors.ResponseValidationError(
                "RAW_503_VALIDATION_SENTINEL",
                response,
                ValueError("RAW_503_CAUSE_SENTINEL"),
                body,
            )

    chat = RejectingSdkChat()
    with pytest.raises(
        langchain_runtime.OpenRouterUpstreamRejectionError
    ) as captured:
        langchain_runtime._ChatSendBridge(chat).send(messages=[])

    assert chat.calls == 1
    assert captured.value.safe_context == {
        "provider_error_code": 503,
        "provider_boundary": "openrouter",
        "expected_upstream_provider": "Together",
    }
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    assert "RAW_" not in json.dumps(captured.value.safe_context)


@pytest.mark.parametrize(
    "finish_reason",
    [None, "length", "content_filter", "tool_calls", "error", "cancelled"],
)
def test_response_bridge_retains_bounded_nonstop_identity_and_usage(finish_reason):
    payload = _native_response_payload()
    payload["choices"][0]["finish_reason"] = finish_reason
    payload["choices"][0]["message"]["content"] = ""
    body = json.dumps(payload)

    class RejectingSdkChat:
        calls = 0

        def send(self, **_kwargs):
            self.calls += 1
            response = _http_response(body)
            raise errors.ResponseValidationError(
                "RAW_NONSTOP_SENTINEL",
                response,
                ValueError("RAW_NONSTOP_SENTINEL"),
                body,
            )

    chat = RejectingSdkChat()
    recovered = langchain_runtime._ChatSendBridge(chat).send(messages=[])

    assert chat.calls == 1
    assert recovered["id"] == payload["id"]
    assert recovered["model"] == payload["model"]
    assert recovered["choices"][0]["finish_reason"] == finish_reason
    assert recovered["choices"][0]["message"]["content"] == ""
    assert recovered["usage"] == {
        "prompt_tokens": 120,
        "completion_tokens": 30,
        "total_tokens": 150,
        "cost": 0.0042,
    }
    assert "RAW_NONSTOP_SENTINEL" not in repr(recovered)


def test_response_bridge_projects_choice_error_to_bounded_failed_finish():
    payload = _native_response_payload()
    payload["choices"][0]["error"] = {"message": "RAW_CHOICE_ERROR_SENTINEL"}
    body = json.dumps(payload)

    class RejectingSdkChat:
        calls = 0

        def send(self, **_kwargs):
            self.calls += 1
            response = _http_response(body)
            raise errors.ResponseValidationError(
                "RAW_CHOICE_ERROR_SENTINEL",
                response,
                ValueError("RAW_CHOICE_ERROR_SENTINEL"),
                body,
            )

    chat = RejectingSdkChat()
    recovered = langchain_runtime._ChatSendBridge(chat).send(messages=[])

    assert chat.calls == 1
    assert recovered["choices"][0]["finish_reason"] == "error"
    assert "error" not in recovered["choices"][0]
    assert "RAW_CHOICE_ERROR_SENTINEL" not in repr(recovered)


def test_provider_provenance_field_grammars_accept_real_ids_and_hash_credentials():
    for response_model in (
        OPENROUTER_MODEL,
        f"{OPENROUTER_MODEL}-20260604",
    ):
        sanitized, violation = langchain_runtime.sanitize_provider_provenance(
            response_id="gen-1786460163-SVSIhqiSG3ko4ZbBb0IS",
            response_model=response_model,
            upstream_provider="Together",
            finish_reason="stop",
        )
        assert violation is None
        assert sanitized == {
            "response_id": "gen-1786460163-SVSIhqiSG3ko4ZbBb0IS",
            "response_model": response_model,
            "upstream_provider": "Together",
            "finish_reason": "stop",
        }

    for field, invalid_value in (
        ("response_id", "sk-or-v1-credential-material"),
        ("response_id", "tenant-reported-moisture"),
        ("upstream_provider", "Deep Infra"),
        ("upstream_provider", "landlord-claim"),
        ("response_model", "different/model"),
        ("finish_reason", "tenant stopped payment"),
    ):
        values = {
            "response_id": "gen-safe-id",
            "response_model": OPENROUTER_MODEL,
            "upstream_provider": "Together",
            "finish_reason": "stop",
        }
        values[field] = invalid_value
        sanitized, violation = langchain_runtime.sanitize_provider_provenance(
            **values
        )
        assert violation is not None
        assert violation["invalid_provenance_field"] == field
        assert len(violation["invalid_provenance_value_hash"]) == 64
        assert sanitized[field] is None
        assert invalid_value not in json.dumps(
            {"sanitized": sanitized, "violation": violation}
        )


@pytest.mark.parametrize(
    ("status_code", "generation_id"),
    [
        (429, "gen-1786483165-FFFFFFFFFFFFFFFFFFFF"),
        (503, "gen-1786483166-GGGGGGGGGGGGGGGGGGGG"),
    ],
    ids=["429-too-many-requests", "503-service-unavailable"],
)
def test_openrouter_sdk_non_2xx_bridge_makes_one_attempt_and_retains_only_bounded_context(
    status_code,
    generation_id,
):
    class CountingClient:
        def __init__(self):
            self.delegate = httpx.Client()
            self.attempts = 0

        def build_request(self, *args, **kwargs):
            return self.delegate.build_request(*args, **kwargs)

        def send(self, request, **_kwargs):
            self.attempts += 1
            return httpx.Response(
                status_code,
                request=request,
                headers={
                    "X-Generation-Id": generation_id,
                    "X-Provider-Secret": "RAW_HTTP_HEADER_SENTINEL",
                },
                json={
                    "error": {
                        "code": status_code,
                        "message": "RAW_HTTP_BODY_SENTINEL",
                        "metadata": {"secret": "sk-or-RAW_HTTP_SECRET_SENTINEL"},
                    }
                },
            )

        def close(self):
            self.delegate.close()

    client = CountingClient()
    sdk = OpenRouter(
        api_key="runtime-only-test-value",
        client=client,
        retry_config=None,
        timeout_ms=180_000,
    )
    bridge = langchain_runtime._OpenRouterClientBridge(sdk)
    with pytest.raises(
        langchain_runtime.OpenRouterUpstreamRejectionError
    ) as captured:
        bridge.chat.send(
            model=OPENROUTER_MODEL,
            messages=[{"role": "user", "content": "bounded test"}],
            max_tokens=1,
        )
    assert client.attempts == 1
    assert captured.value.safe_context == {
        "response_id": generation_id,
        "provider_error_code": status_code,
        "provider_boundary": "openrouter",
        "expected_upstream_provider": "Together",
    }
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    serialized = json.dumps(captured.value.safe_context)
    assert "RAW_" not in serialized
    assert "sk-or-" not in serialized


def test_external_tracing_blocks_runner_and_graph_before_invocation(
    tmp_path: Path, monkeypatch
):
    factory_calls = 0

    def forbidden_factory(*_args):
        nonlocal factory_calls
        factory_calls += 1
        raise AssertionError("provider runnable must not be created")

    runner = InstrumentedStructuredAgent(
        Storage(str(tmp_path / "trace-runner.db")),
        runnable_factory=forbidden_factory,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with tracing_context(enabled=True), pytest.raises(
        RuntimeError, match="Inherited LangChain tracing"
    ):
        runner.invoke(
            run_id="run-trace",
            orchestration_id="orch-trace",
            agent_id="orchestrator_plan",
            schema=OrchestratorPlan,
            system_prompt="bounded",
            provider_payload={"fact_candidates": []},
            validator=lambda value: (value, {}),
            private_contract_hash="0" * 64,
        )
    assert factory_calls == 0

    (
        orchestrator,
        _storage,
        _captures,
        _responses,
        package,
        canonicalization,
        result,
    ) = graph_fixture(tmp_path)

    class SpyGraph:
        entered = False

        def stream(self, *_args, **_kwargs):
            self.entered = True
            return iter(())

    spy = SpyGraph()
    orchestrator.graph = spy
    with tracing_context(enabled=True), pytest.raises(
        RuntimeError, match="Inherited LangChain tracing"
    ):
        orchestrator.invoke(
            run_id="run-trace-graph",
            orchestration_id="orch-trace-graph",
            observable_package=package,
            canonicalization=canonicalization,
            facts=result["facts"],
            process=result["process"],
            checklist=result["checklist"],
            verification=result["verification"],
        )
    assert spy.entered is False

    monkeypatch.setattr(
        langchain_runtime,
        "get_tracing_context",
        lambda: {"enabled": "local"},
    )
    with pytest.raises(RuntimeError, match="Inherited LangChain tracing"):
        orchestrator.invoke(
            run_id="run-trace-graph-nonboolean",
            orchestration_id="orch-trace-graph-nonboolean",
            observable_package=package,
            canonicalization=canonicalization,
            facts=result["facts"],
            process=result["process"],
            checklist=result["checklist"],
            verification=result["verification"],
        )
    assert spy.entered is False


def test_specialist_requires_strict_accepted_majority_and_never_caches_minority(
    tmp_path: Path,
):
    calls = 0

    class Runnable:
        def invoke(self, _messages, config=None):
            nonlocal calls
            calls += 1
            return {
                "raw": AIMessage(
                    content="",
                    response_metadata={
                        "id": f"gen-majority-{calls}",
                        "model_name": OPENROUTER_MODEL,
                        "finish_reason": "stop",
                        "provider_name": "Together",
                        "usage": {
                            "prompt_tokens": 10,
                            "completion_tokens": 5,
                            "total_tokens": 15,
                            "cost": 0.001,
                        },
                    },
                ),
                "parsed": OrchestratorPlan(
                    priority_fact_ids=["fact"],
                    priority_task_codes=[
                        "source_integrity",
                        "process_decisions",
                        "evidence_gaps",
                        "final_brief",
                    ],
                ),
                "parsing_error": None,
            }

    storage = Storage(str(tmp_path / "majority.db"))
    runner = InstrumentedStructuredAgent(
        storage,
        runnable_factory=lambda *_args: Runnable(),
        api_key_provider=lambda: "runtime-only-test-value",
    )
    diagnostics = {
        "authority_mode": "multi_agent_hybrid_guarded",
        "accepted_item_ids": ["accepted"],
        "accepted_item_count": 1,
        "rejected_items": [{"item_id": "rejected", "invariant": "bounded"}],
        "rejected_item_count": 1,
        "ignored_proposal_count": 0,
        "deterministic_fallback_applied": True,
    }
    for index in range(2):
        with pytest.raises(
            AgentInvocationFailure, match="model_contribution_majority"
        ):
            runner.invoke(
                run_id=f"run-majority-{index}",
                orchestration_id="orch-majority",
                agent_id="orchestrator_plan",
                schema=OrchestratorPlan,
                system_prompt="bounded",
                provider_payload={"stable": True},
                validator=lambda value: (value, diagnostics),
                private_contract_hash="1" * 64,
            )
    assert calls == 2
    ledger = storage.model_calls()
    assert [item["outcome"] for item in ledger] == ["failed", "failed"]
    assert all(item["accepted_item_ids"] == ["accepted"] for item in ledger)
    assert all(
        item["rejected_items"]
        == [{"item_id": "rejected", "invariant": "bounded"}]
        for item in ledger
    )
    assert all(item["accepted_item_count"] == 1 for item in ledger)
    assert all(item["rejected_item_count"] == 1 for item in ledger)
    assert all("canonical_output" not in item for item in ledger)
    assert all("deterministic_fallback_applied" not in item for item in ledger)
    assert all(storage.cached_model_output(item["cache_key"]) is None for item in ledger)


@pytest.mark.parametrize("value", [1.0, -0.0, 1e-7, float("inf"), float("nan")])
def test_accepted_artifact_hash_rejects_all_floats(value: float):
    with pytest.raises(AgentBoundaryError, match="float_at"):
        accepted_artifact_hash({"bounded": [1, value]})


def test_evidence_role_reserves_large_answer_headroom(tmp_path: Path):
    (
        orchestrator,
        _storage,
        _captures,
        responses,
        package,
        canonicalization,
        result,
    ) = graph_fixture(tmp_path)
    orchestrator.invoke(
        run_id="run-size-test",
        orchestration_id="orch-size-test",
        observable_package=package,
        canonicalization=canonicalization,
        facts=result["facts"],
        process=result["process"],
        checklist=result["checklist"],
        verification=result["verification"],
    )
    slots = responses["evidence_checklist"]["items"]
    assert len(slots) == len(result["checklist"]["items"]) == 21
    conservative_tokens = (
        len(json.dumps({"items": slots}, separators=(",", ":")).encode()) + 2
    ) // 3
    assert conservative_tokens * 2 < ROLE_OUTPUT_TOKENS["evidence_checklist"] == 8_192


def test_all_production_specialist_artifacts_leave_half_completion_budget(
    tmp_path: Path,
):
    assert ROLE_OUTPUT_TOKENS == {
        "orchestrator_plan": 4_096,
        "document_source_integrity": 4_096,
        "process_decision_mapping": 4_096,
        "evidence_checklist": 8_192,
        "final_claim_brief_audit": 4_096,
    }
    (
        orchestrator,
        _storage,
        _captures,
        responses,
        package,
        canonicalization,
        result,
    ) = graph_fixture(tmp_path)
    audit = orchestrator.invoke(
        run_id="run-answer-headroom",
        orchestration_id="orch-answer-headroom",
        observable_package=package,
        canonicalization=canonicalization,
        facts=result["facts"],
        process=result["process"],
        checklist=result["checklist"],
        verification=result["verification"],
    )

    assert audit["all_required_agents_contributed"] is True
    assert set(responses) == set(ROLE_OUTPUT_TOKENS)
    for role, response in responses.items():
        conservative_answer_tokens = (
            len(json.dumps(response, separators=(",", ":")).encode()) + 2
        ) // 3
        assert conservative_answer_tokens * 2 < ROLE_OUTPUT_TOKENS[role], (
            role,
            conservative_answer_tokens,
            ROLE_OUTPUT_TOKENS[role],
        )


@pytest.mark.parametrize(
    ("priority_fact_ids", "task_codes"),
    [
        ([], ["source_integrity", "process_decisions", "evidence_gaps", "final_brief"]),
        (["fact_1", "fact_1"], ["source_integrity", "process_decisions", "evidence_gaps", "final_brief"]),
        (["unknown"], ["source_integrity", "process_decisions", "evidence_gaps", "final_brief"]),
        (
            [f"fact_{index}" for index in range(1, 8)],
            ["source_integrity", "process_decisions", "evidence_gaps", "final_brief"],
        ),
        (["fact_1"], ["source_integrity", "process_decisions", "evidence_gaps"]),
        (
            ["fact_1"],
            ["source_integrity", "source_integrity", "evidence_gaps", "final_brief"],
        ),
        (
            ["fact_1"],
            ["source_integrity", "process_decisions", "evidence_gaps", "unknown"],
        ),
    ],
)
def test_plan_validator_rejects_unbounded_or_incomplete_priorities(
    priority_fact_ids: list[str], task_codes: list[str]
):
    canonical_fact_ids = [f"fact_{index}" for index in range(1, 19)]
    validator = _plan_validator(
        canonical_fact_ids=canonical_fact_ids,
        deterministic_focus_source_ref_ids=[f"src_{index}" for index in range(5)],
        required_text_artifact_ids=[f"artifact_{index}" for index in range(5)],
    )

    contribution, diagnostics = validator(
        {
            "priority_fact_ids": priority_fact_ids,
            "priority_task_codes": task_codes,
        }
    )

    assert diagnostics["accepted_item_count"] == 0
    assert diagnostics["rejected_item_count"] == 1
    assert diagnostics["rejected_items"][0]["invariant"] == (
        "bounded_priority_selection"
    )
    assert contribution["model_priority_fact_ids"] == []
    assert contribution["focus_fact_ids"] == []
    assert contribution["focus_source_ref_ids"] == []


def test_model_fact_priority_changes_derived_downstream_order_without_losing_coverage(
    tmp_path: Path,
):
    (
        _orchestrator,
        _storage,
        _captures,
        _responses,
        package,
        _canonicalization,
        result,
    ) = graph_fixture(tmp_path)
    canonical_fact_ids = [item["fact_id"] for item in result["facts"]]
    required_artifacts = sorted(
        item["artifact_id"]
        for item in package["artifacts"]
        if item["media_type"] in {"application/pdf", "message/rfc822"}
    )
    registry = _source_registry(package)
    deterministic_sources = [
        min(
            item["source_ref_id"]
            for item in registry
            if item["artifact_id"] == artifact_id
        )
        for artifact_id in required_artifacts
    ]
    validator = _plan_validator(
        canonical_fact_ids=canonical_fact_ids,
        deterministic_focus_source_ref_ids=deterministic_sources,
        required_text_artifact_ids=required_artifacts,
    )
    task_codes = ["source_integrity", "process_decisions", "evidence_gaps", "final_brief"]

    forward, forward_diagnostics = validator(
        {
            "priority_fact_ids": canonical_fact_ids[:2],
            "priority_task_codes": task_codes,
        }
    )
    reverse, reverse_diagnostics = validator(
        {
            "priority_fact_ids": list(reversed(canonical_fact_ids[-2:])),
            "priority_task_codes": task_codes,
        }
    )

    assert forward_diagnostics["accepted_item_count"] == 1
    assert reverse_diagnostics["accepted_item_count"] == 1
    assert forward["focus_fact_ids"][:2] == canonical_fact_ids[:2]
    assert reverse["focus_fact_ids"][:2] == list(reversed(canonical_fact_ids[-2:]))
    assert set(forward["focus_fact_ids"]) == set(reverse["focus_fact_ids"]) == set(
        canonical_fact_ids
    )
    assert len(forward["focus_fact_ids"]) == len(reverse["focus_fact_ids"]) == 18
    assert forward["focus_source_ref_ids"] == reverse["focus_source_ref_ids"]
    assert len(forward["focus_source_ref_ids"]) == 5

    def evidence_order(plan: dict[str, Any]) -> list[str]:
        payload = _evidence_provider_payload(
            {
                "orchestrator_plan": plan,
                "source_integrity": {"artifacts": []},
                "process": result["process"],
                "checklist": result["checklist"],
                "facts": result["facts"],
                "source_registry": registry,
                "observable_package": package,
            }
        )
        return [item["fact_id"] for item in payload["canonical_fact_handoff"]]

    assert evidence_order(forward) != evidence_order(reverse)


def _accepted_plan_validator(value: dict[str, Any]):
    return value, {
        "authority_mode": "multi_agent_hybrid_guarded",
        "accepted_item_ids": ["orchestration_focus"],
        "accepted_item_count": 1,
        "rejected_items": [],
        "rejected_item_count": 0,
        "ignored_proposal_count": 0,
        "deterministic_fallback_applied": False,
    }


def _plan_envelope(
    *,
    response_id: str | None = "gen-plan",
    response_model: str = OPENROUTER_MODEL,
    provider_name: str | None = "Together",
    finish_reason: str | None = "stop",
    usage: dict[str, Any] | None = None,
    parsed: bool = True,
):
    metadata: dict[str, Any] = {
        "model_name": response_model,
        "provider_name": provider_name,
        "finish_reason": finish_reason,
    }
    if response_id is not None:
        metadata["id"] = response_id
    if usage is not None:
        metadata["usage"] = usage
    return {
        "raw": AIMessage(content="", response_metadata=metadata),
        "parsed": (
            OrchestratorPlan(
                priority_fact_ids=["fact"],
                priority_task_codes=[
                    "source_integrity",
                    "process_decisions",
                    "evidence_gaps",
                    "final_brief",
                ],
            )
            if parsed
            else None
        ),
        "parsing_error": None if parsed else ValueError("raw-provider-detail"),
    }


def _invoke_plan(
    runner: InstrumentedStructuredAgent,
    *,
    run_id: str = "run-plan",
    agent_id: str = "orchestrator_plan",
    system_prompt: str = "bounded",
    progress_sink=None,
):
    return runner.invoke(
        run_id=run_id,
        orchestration_id="orch-plan",
        agent_id=agent_id,
        schema=OrchestratorPlan,
        system_prompt=system_prompt,
        provider_payload={"observable": True},
        validator=_accepted_plan_validator,
        private_contract_hash="2" * 64,
        progress_sink=progress_sink,
    )


def test_specialist_cost_preflight_includes_serialized_provider_schema(
    tmp_path: Path,
    monkeypatch,
):
    estimated_inputs: list[str] = []
    original = multi_agent_module._input_token_estimate

    def capture_estimate(value: str) -> int:
        estimated_inputs.append(value)
        return original(value)

    class Runnable:
        def invoke(self, *_args, **_kwargs):
            return _plan_envelope(
                usage={
                    "prompt_tokens": 20,
                    "completion_tokens": 10,
                    "total_tokens": 30,
                    "cost": 0.001,
                }
            )

    monkeypatch.setattr(
        multi_agent_module,
        "_input_token_estimate",
        capture_estimate,
    )
    runner = InstrumentedStructuredAgent(
        Storage(str(tmp_path / "schema-cost.db")),
        runnable_factory=lambda *_args: Runnable(),
        api_key_provider=lambda: "runtime-only-test-value",
    )
    _invoke_plan(runner, run_id="run-schema-cost")

    assert len(estimated_inputs) == 1
    assert '"priority_fact_ids"' in estimated_inputs[0]
    assert '"maxItems":6' in estimated_inputs[0]


def test_orchestrator_plan_accepts_completion_above_legacy_ceiling_with_exact_new_cap(
    tmp_path: Path,
):
    provider_calls = 0
    received_ceilings: list[int] = []

    class Runnable:
        def invoke(self, *_args, **_kwargs):
            nonlocal provider_calls
            provider_calls += 1
            return _plan_envelope(
                usage={
                    "prompt_tokens": 700,
                    "completion_tokens": 3_500,
                    "total_tokens": 4_200,
                    "cost": 0.008,
                }
            )

    def factory(_agent_id, _schema, _key, _orchestration_id, max_tokens):
        received_ceilings.append(max_tokens)
        return Runnable()

    storage = Storage(str(tmp_path / "expanded-plan-ceiling.db"))
    runner = InstrumentedStructuredAgent(
        storage,
        runnable_factory=factory,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    result = _invoke_plan(runner, run_id="run-expanded-plan-ceiling")

    assert ROLE_OUTPUT_TOKENS["orchestrator_plan"] == 4_096
    assert received_ceilings == [4_096]
    assert provider_calls == 1
    assert result["cache_hit"] is False
    assert result["outcome"] == "succeeded"
    assert result["usage"]["completion_tokens"] == 3_500 > 800
    ledger = storage.model_calls()
    assert len(ledger) == 1
    assert ledger[0]["call_count"] == 1
    assert ledger[0]["outcome"] == "succeeded"


def test_multi_agent_version_bump_invalidates_success_cache(
    tmp_path: Path, monkeypatch
):
    provider_calls = 0

    class Runnable:
        def invoke(self, *_args, **_kwargs):
            nonlocal provider_calls
            provider_calls += 1
            return _plan_envelope(
                usage={
                    "prompt_tokens": 20,
                    "completion_tokens": 10,
                    "total_tokens": 30,
                    "cost": 0.001,
                }
            )

    storage = Storage(str(tmp_path / "versioned-cache.db"))
    runner = InstrumentedStructuredAgent(
        storage,
        runnable_factory=lambda *_args: Runnable(),
        api_key_provider=lambda: "runtime-only-test-value",
    )
    progress_receipts: list[dict[str, Any]] = []

    assert multi_agent_module.MULTI_AGENT_VERSION == "1.5.0"
    assert multi_agent_module.MULTI_AGENT_SCHEMA_VERSION.endswith("/1.0.0")
    first = _invoke_plan(
        runner,
        run_id="run-version-cache-first",
        progress_sink=progress_receipts.append,
    )
    cached = _invoke_plan(
        runner,
        run_id="run-version-cache-hit",
        progress_sink=progress_receipts.append,
    )
    assert first["cache_hit"] is False
    assert cached["cache_hit"] is True
    assert provider_calls == 1
    assert len(progress_receipts) == 1
    assert progress_receipts[0]["receipt_type"] == "agent_started"
    assert progress_receipts[0]["call_id"] == first["call_id"]
    assert progress_receipts[0]["cache_hit"] is False

    monkeypatch.setattr(
        multi_agent_module,
        "MULTI_AGENT_VERSION",
        "1.3.0-test-cache-invalidation",
    )
    invalidated = _invoke_plan(runner, run_id="run-version-cache-invalidated")
    assert invalidated["cache_hit"] is False
    assert invalidated["cache_key"] != first["cache_key"]
    assert provider_calls == 2


def test_prompt_reasoning_token_and_provider_policy_are_specialist_cache_identity(
    tmp_path: Path, monkeypatch
):
    provider_calls = 0

    class Runnable:
        def invoke(self, *_args, **_kwargs):
            nonlocal provider_calls
            provider_calls += 1
            return _plan_envelope(
                response_id=f"gen-cache-policy-{provider_calls}",
                usage={
                    "prompt_tokens": 20,
                    "completion_tokens": 10,
                    "total_tokens": 30,
                    "cost": 0.001,
                },
            )

    storage = Storage(str(tmp_path / "runtime-policy-cache.db"))
    runner = InstrumentedStructuredAgent(
        storage,
        runnable_factory=lambda *_args: Runnable(),
        api_key_provider=lambda: "runtime-only-test-value",
    )

    baseline = _invoke_plan(runner, run_id="run-policy-baseline")
    cached = _invoke_plan(runner, run_id="run-policy-cached")
    changed_prompt = _invoke_plan(
        runner,
        run_id="run-policy-prompt",
        system_prompt="bounded but changed",
    )
    monkeypatch.setitem(
        multi_agent_module.ROLE_REASONING,
        "orchestrator_plan",
        {"max_tokens": 512},
    )
    changed_reasoning = _invoke_plan(runner, run_id="run-policy-reasoning")
    monkeypatch.setitem(
        multi_agent_module.ROLE_OUTPUT_TOKENS,
        "orchestrator_plan",
        4_097,
    )
    changed_ceiling = _invoke_plan(runner, run_id="run-policy-ceiling")
    monkeypatch.setattr(
        multi_agent_module,
        "openrouter_provider_policy",
        lambda: {
            "only": ["alternate-provider-test"],
            "allow_fallbacks": False,
            "require_parameters": True,
            "data_collection": "deny",
        },
    )
    changed_provider = _invoke_plan(runner, run_id="run-policy-provider")

    assert baseline["cache_hit"] is False
    assert cached["cache_hit"] is True
    assert provider_calls == 5
    assert len(
        {
            baseline["cache_key"],
            changed_prompt["cache_key"],
            changed_reasoning["cache_key"],
            changed_ceiling["cache_key"],
            changed_provider["cache_key"],
        }
    ) == 5


@pytest.mark.parametrize(
    ("agent_id", "ceiling"),
    [
        ("orchestrator_plan", 4_096),
        ("document_source_integrity", 4_096),
        ("process_decision_mapping", 4_096),
        ("evidence_checklist", 8_192),
        ("final_claim_brief_audit", 4_096),
    ],
)
def test_each_specialist_length_at_new_ceiling_is_billed_and_never_cached(
    tmp_path: Path, agent_id: str, ceiling: int
):
    provider_calls = 0
    received_ceilings: list[int] = []

    class Runnable:
        def invoke(self, *_args, **_kwargs):
            nonlocal provider_calls
            provider_calls += 1
            return _plan_envelope(
                finish_reason="length",
                usage={
                    "prompt_tokens": 700,
                    "completion_tokens": ceiling,
                    "total_tokens": 700 + ceiling,
                    "cost": 0.009,
                },
            )

    def factory(_agent_id, _schema, _key, _orchestration_id, max_tokens):
        received_ceilings.append(max_tokens)
        return Runnable()

    storage = Storage(str(tmp_path / f"length-at-{agent_id}-ceiling.db"))
    runner = InstrumentedStructuredAgent(
        storage,
        runnable_factory=factory,
        api_key_provider=lambda: "runtime-only-test-value",
    )

    for run_id in ("run-length-at-new-cap-1", "run-length-at-new-cap-2"):
        with pytest.raises(AgentInvocationFailure, match="provider_finish_reason"):
            _invoke_plan(runner, run_id=run_id, agent_id=agent_id)

    assert ROLE_OUTPUT_TOKENS[agent_id] == ceiling
    assert received_ceilings == [ceiling, ceiling]
    assert provider_calls == 2
    ledger = storage.model_calls()
    assert len(ledger) == 2
    assert all(item["call_count"] == 1 for item in ledger)
    assert all(item["outcome"] == "failed" for item in ledger)
    assert all(item["error_invariant"] == "provider_finish_reason" for item in ledger)
    assert all(item["finish_reason"] == "length" for item in ledger)
    assert all(item["completion_tokens"] == ceiling for item in ledger)
    assert all(storage.cached_model_output(item["cache_key"]) is None for item in ledger)


def test_specialist_wrong_model_metadata_billing_and_missing_id_sync_billing_are_retained(
    tmp_path: Path,
):
    metadata_calls = 0

    class WrongModelRunnable:
        def invoke(self, *_args, **_kwargs):
            return _plan_envelope(response_model="different/model", usage=None)

    def metadata_transport(*_args):
        nonlocal metadata_calls
        metadata_calls += 1
        return {
            "data": {
                "id": "gen-plan",
                "model": "nvidia/nemotron-3-ultra-550b-a55b-20260604",
                "provider_name": "Together",
                "native_tokens_prompt": 41,
                "native_tokens_completion": 17,
                "total_cost": 0.0041,
                "usage": 0.0041,
                "finish_reason": "stop",
            }
        }

    wrong_storage = Storage(str(tmp_path / "wrong-model.db"))
    wrong_runner = InstrumentedStructuredAgent(
        wrong_storage,
        runnable_factory=lambda *_args: WrongModelRunnable(),
        metadata_transport=metadata_transport,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(AgentInvocationFailure, match="invalid_provenance") as caught:
        _invoke_plan(wrong_runner, run_id="run-wrong-model")
    assert metadata_calls == 1
    assert caught.value.safe_context["response_id"] == "gen-plan"
    wrong_ledger = wrong_storage.model_calls()[0]
    assert wrong_ledger["outcome"] == "failed"
    assert wrong_ledger["actual_cost_usd"] == pytest.approx(0.0041)
    assert wrong_ledger["prompt_tokens"] == 41
    assert wrong_ledger["completion_tokens"] == 17
    assert "response_model" not in wrong_ledger
    assert wrong_ledger["invalid_provenance_field"] == "response_model"
    assert len(wrong_ledger["invalid_provenance_value_hash"]) == 64
    assert wrong_ledger["generation_model"].endswith("-20260604")
    assert "different/model" not in json.dumps(wrong_ledger)

    class MissingIdRunnable:
        def invoke(self, *_args, **_kwargs):
            return _plan_envelope(
                response_id=None,
                usage={
                    "prompt_tokens": 31,
                    "completion_tokens": 11,
                    "total_tokens": 42,
                    "cost": 0.0031,
                },
            )

    missing_storage = Storage(str(tmp_path / "missing-id.db"))
    missing_runner = InstrumentedStructuredAgent(
        missing_storage,
        runnable_factory=lambda *_args: MissingIdRunnable(),
        metadata_transport=lambda *_args: (_ for _ in ()).throw(
            AssertionError("metadata lookup requires a valid response ID")
        ),
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(AgentInvocationFailure, match="response_identity"):
        _invoke_plan(missing_runner, run_id="run-missing-id")
    missing_ledger = missing_storage.model_calls()[0]
    assert missing_ledger["actual_cost_usd"] == pytest.approx(0.0031)
    assert missing_ledger["prompt_tokens"] == 31
    assert "response_id" not in missing_ledger


def test_specialist_missing_upstream_provider_uses_generation_metadata(
    tmp_path: Path,
):
    metadata_calls = 0
    inference_calls = 0

    class Runnable:
        def invoke(self, *_args, **_kwargs):
            nonlocal inference_calls
            inference_calls += 1
            return _plan_envelope(
                provider_name=None,
                usage={
                    "prompt_tokens": 31,
                    "completion_tokens": 11,
                    "total_tokens": 42,
                    "cost": 0.0031,
                },
            )

    def metadata_transport(*_args):
        nonlocal metadata_calls
        metadata_calls += 1
        return {
            "data": {
                "id": "gen-plan",
                "model": "nvidia/nemotron-3-ultra-550b-a55b-20260604",
                "provider_name": "Together",
                "native_tokens_prompt": 41,
                "native_tokens_completion": 17,
                "total_cost": 0.0041,
                "usage": 0.0041,
                "finish_reason": "stop",
            }
        }

    storage = Storage(str(tmp_path / "missing-specialist-provider.db"))
    runner = InstrumentedStructuredAgent(
        storage,
        runnable_factory=lambda *_args: Runnable(),
        metadata_transport=metadata_transport,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    result = _invoke_plan(runner, run_id="run-missing-specialist-provider")

    assert inference_calls == metadata_calls == 1
    assert result["upstream_provider"] == "Together"
    assert result["usage_source"] == "generation_metadata"
    ledger = storage.sanitized_model_ledger()[0]
    assert ledger["outcome"] == "succeeded"
    assert ledger["upstream_provider"] == "Together"
    assert ledger["usage_source"] == "generation_metadata"


def test_specialist_generation_metadata_eventual_consistency_uses_bounded_backoff(
    tmp_path: Path,
):
    metadata_calls = 0
    inference_calls = 0
    sleeps: list[float] = []

    class Runnable:
        def invoke(self, *_args, **_kwargs):
            nonlocal inference_calls
            inference_calls += 1
            return _plan_envelope(
                provider_name=None,
                usage={
                    "prompt_tokens": 31,
                    "completion_tokens": 11,
                    "total_tokens": 42,
                    "cost": 0.0031,
                },
            )

    def metadata_transport(*_args):
        nonlocal metadata_calls
        metadata_calls += 1
        if metadata_calls < canonicalizer_module.GENERATION_METADATA_POLL_ATTEMPTS:
            return {"data": {}}
        return {
            "data": {
                "id": "gen-plan",
                "model": "nvidia/nemotron-3-ultra-550b-a55b-20260604",
                "provider_name": "Together",
                "native_tokens_prompt": 31,
                "native_tokens_completion": 11,
                "total_cost": 0.0031,
                "usage": 0.0031,
                "finish_reason": "stop",
            }
        }

    storage = Storage(str(tmp_path / "delayed-specialist-provider.db"))
    runner = InstrumentedStructuredAgent(
        storage,
        runnable_factory=lambda *_args: Runnable(),
        metadata_transport=metadata_transport,
        metadata_sleep=sleeps.append,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    result = _invoke_plan(runner, run_id="run-delayed-specialist-provider")

    assert inference_calls == 1
    assert metadata_calls == 8
    assert sleeps == [0.5, 1.0, 2.0, 4.0, 8.0, 8.0, 8.0]
    assert result["upstream_provider"] == "Together"
    assert result["usage_source"] == "generation_metadata"
    ledger = storage.sanitized_model_ledger()[0]
    assert ledger["outcome"] == "succeeded"
    assert ledger["metadata_poll_count"] == 8
    assert ledger["actual_cost_usd"] == pytest.approx(0.0031)


def test_specialist_missing_upstream_provider_fails_closed_without_metadata(
    tmp_path: Path,
):
    inference_calls = 0
    metadata_calls = 0

    class Runnable:
        def invoke(self, *_args, **_kwargs):
            nonlocal inference_calls
            inference_calls += 1
            return _plan_envelope(
                provider_name=None,
                usage={
                    "prompt_tokens": 31,
                    "completion_tokens": 11,
                    "total_tokens": 42,
                    "cost": 0.0031,
                },
            )

    def incomplete_metadata(*_args):
        nonlocal metadata_calls
        metadata_calls += 1
        return {"data": {}}

    storage = Storage(str(tmp_path / "missing-specialist-provider-incomplete.db"))
    runner = InstrumentedStructuredAgent(
        storage,
        runnable_factory=lambda *_args: Runnable(),
        metadata_transport=incomplete_metadata,
        metadata_sleep=lambda _seconds: None,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(
        AgentInvocationFailure,
        match="generation_metadata_completeness",
    ):
        _invoke_plan(runner, run_id="run-missing-specialist-provider-incomplete")

    assert inference_calls == 1
    assert metadata_calls == 8
    ledger = storage.sanitized_model_ledger()[0]
    assert ledger["outcome"] == "failed"
    assert ledger["error_invariant"] == "generation_metadata_completeness"
    assert ledger["actual_cost_usd"] == pytest.approx(0.0031)
    assert ledger["usage_source"] == "response"
    assert ledger["response_id"] == "gen-plan"
    assert ledger["response_model"] == OPENROUTER_MODEL
    assert ledger["finish_reason"] == "stop"
    assert ledger["prompt_tokens"] == 31
    assert ledger["completion_tokens"] == 11
    assert ledger["total_tokens"] == 42
    assert ledger["metadata_poll_count"] == 8
    assert ledger["metadata_latency_ms"] >= 0
    assert ledger["error_type"] != "KeyError"
    assert storage.cached_model_output(ledger["cache_key"]) is None


def test_specialist_invalid_generation_usage_retains_bounded_poll_evidence(
    tmp_path: Path,
):
    inference_calls = 0
    metadata_calls = 0

    class Runnable:
        def invoke(self, *_args, **_kwargs):
            nonlocal inference_calls
            inference_calls += 1
            return _plan_envelope(
                provider_name=None,
                usage={
                    "prompt_tokens": 31,
                    "completion_tokens": 11,
                    "total_tokens": 42,
                    "cost": 0.0031,
                },
            )

    def invalid_metadata(*_args):
        nonlocal metadata_calls
        metadata_calls += 1
        return {
            "data": {
                "id": "gen-plan",
                "model": "nvidia/nemotron-3-ultra-550b-a55b-20260604",
                "provider_name": "Together",
                "native_tokens_prompt": 31,
                "native_tokens_completion": 11,
                "total_cost": 0.0,
                "usage": 0.0,
                "finish_reason": "stop",
            }
        }

    storage = Storage(str(tmp_path / "invalid-specialist-generation-usage.db"))
    runner = InstrumentedStructuredAgent(
        storage,
        runnable_factory=lambda *_args: Runnable(),
        metadata_transport=invalid_metadata,
        metadata_sleep=lambda _seconds: None,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(AgentInvocationFailure, match="generation_metadata_usage"):
        _invoke_plan(runner, run_id="run-invalid-specialist-generation-usage")

    assert inference_calls == metadata_calls == 1
    ledger = storage.sanitized_model_ledger()[0]
    assert ledger["outcome"] == "failed"
    assert ledger["error_invariant"] == "generation_metadata_usage"
    assert ledger["response_id"] == "gen-plan"
    assert ledger["response_model"] == OPENROUTER_MODEL
    assert ledger["finish_reason"] == "stop"
    assert ledger["prompt_tokens"] == 31
    assert ledger["completion_tokens"] == 11
    assert ledger["total_tokens"] == 42
    assert ledger["actual_cost_usd"] == pytest.approx(0.0031)
    assert ledger["usage_source"] == "response"
    assert ledger["metadata_poll_count"] == 1
    assert ledger["metadata_latency_ms"] >= 0
    assert storage.cached_model_output(ledger["cache_key"]) is None


@pytest.mark.parametrize(
    "envelope_overrides",
    [
        {"response_id": "gen-" + "x" * 200},
        {"provider_name": "SECRET_SENTINEL_PROVIDER"},
        {"finish_reason": "SECRET_SENTINEL_FINISH"},
    ],
)
def test_specialist_provider_provenance_is_bounded_before_ledger_and_failure_context(
    tmp_path: Path,
    envelope_overrides: dict[str, Any],
):
    invalid_value = next(iter(envelope_overrides.values()))

    class Runnable:
        def invoke(self, *_args, **_kwargs):
            return _plan_envelope(
                **envelope_overrides,
                usage={
                    "prompt_tokens": 31,
                    "completion_tokens": 11,
                    "total_tokens": 42,
                    "cost": 0.0031,
                    "secret_usage_sentinel": "must-not-be-stored",
                },
            )

    storage = Storage(str(tmp_path / "invalid-provenance.db"))
    runner = InstrumentedStructuredAgent(
        storage,
        runnable_factory=lambda *_args: Runnable(),
        metadata_transport=lambda *_args: (_ for _ in ()).throw(
            AssertionError("invalid provenance must not trigger metadata polling")
        ),
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(AgentInvocationFailure, match="invalid_provenance") as caught:
        _invoke_plan(runner, run_id="run-invalid-provenance")
    ledger = storage.model_calls()[0]
    serialized = json.dumps(ledger)
    assert ledger["outcome"] == "failed"
    assert ledger["error_invariant"] == "invalid_provenance"
    assert ledger["actual_cost_usd"] == pytest.approx(0.0031)
    assert len(ledger["invalid_provenance_value_hash"]) == 64
    assert invalid_value not in serialized
    assert "secret_usage_sentinel" not in serialized
    assert "must-not-be-stored" not in serialized
    assert caught.value.safe_context["invalid_provenance_value_hash"] == ledger[
        "invalid_provenance_value_hash"
    ]


def test_specialist_schema_failure_retains_billing_without_raw_error(tmp_path: Path):
    class Runnable:
        def invoke(self, *_args, **_kwargs):
            return _plan_envelope(
                parsed=False,
                usage={
                    "prompt_tokens": 21,
                    "completion_tokens": 9,
                    "total_tokens": 30,
                    "cost": 0.0021,
                },
            )

    storage = Storage(str(tmp_path / "schema-failure.db"))
    runner = InstrumentedStructuredAgent(
        storage,
        runnable_factory=lambda *_args: Runnable(),
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(AgentInvocationFailure, match="provider_native_schema") as caught:
        _invoke_plan(runner)
    assert caught.value.safe_context["call_id"] == storage.model_calls()[0]["call_id"]
    ledger = storage.model_calls()[0]
    assert ledger["actual_cost_usd"] == pytest.approx(0.0021)
    assert ledger["outcome"] == "failed"
    assert ledger["error_invariant"] == "provider_native_schema"
    assert "raw-provider-detail" not in json.dumps(storage.sanitized_model_ledger())


def test_nonstop_specialist_response_cannot_be_accepted_or_cached(tmp_path: Path):
    class Runnable:
        def invoke(self, *_args, **_kwargs):
            return _plan_envelope(
                finish_reason="length",
                usage={
                    "prompt_tokens": 21,
                    "completion_tokens": 9,
                    "total_tokens": 30,
                    "cost": 0.0021,
                },
            )

    storage = Storage(str(tmp_path / "nonstop-specialist.db"))
    runner = InstrumentedStructuredAgent(
        storage,
        runnable_factory=lambda *_args: Runnable(),
        api_key_provider=lambda: "runtime-only-test-value",
    )

    with pytest.raises(AgentInvocationFailure, match="provider_finish_reason"):
        _invoke_plan(runner, run_id="run-nonstop-specialist")

    ledger = storage.model_calls()[0]
    assert ledger["outcome"] == "failed"
    assert ledger["error_invariant"] == "provider_finish_reason"
    assert ledger["finish_reason"] == "length"
    assert ledger["actual_cost_usd"] == pytest.approx(0.0021)
    assert storage.cached_model_output(ledger["cache_key"]) is None


def test_specialist_sdk_drift_nonstop_retains_billing_before_rejection(
    tmp_path: Path,
    monkeypatch,
):
    provider_calls = 0
    metadata_calls = 0
    provider_payload = {
        "id": "gen-plan-drift",
        "model": OPENROUTER_MODEL,
        "object": "chat.completion",
        "created": 1786479000,
        "choices": [
            {
                "index": 0,
                "finish_reason": "length",
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "priority_fact_ids": ["fact"],
                            "priority_task_codes": [
                                "source_integrity",
                                "process_decisions",
                                "evidence_gaps",
                                "final_brief",
                            ],
                        }
                    ),
                },
            }
        ],
        "usage": {
            "prompt_tokens": 21,
            "completion_tokens": 9,
            "total_tokens": 30,
            "cost": 0.0021,
        },
    }

    class GeneratedSdkChat:
        def send(self, **_kwargs):
            nonlocal provider_calls
            provider_calls += 1
            response_value = _http_response(json.dumps(provider_payload))
            return unmarshal_json_response(components.ChatResult, response_value)

    class FakeOpenRouter:
        def __init__(self, **_kwargs):
            self.chat = GeneratedSdkChat()

    def metadata_transport(*_args):
        nonlocal metadata_calls
        metadata_calls += 1
        return {
            "data": {
                "id": "gen-plan-drift",
                "model": OPENROUTER_MODEL,
                "provider_name": "Together",
                "native_tokens_prompt": 31,
                "native_tokens_completion": 11,
                "total_cost": 0.0033,
                "usage": 0.0033,
                "finish_reason": "stop",
            }
        }

    monkeypatch.setattr(langchain_runtime, "OpenRouter", FakeOpenRouter)
    storage = Storage(str(tmp_path / "sdk-drift-specialist-nonstop.db"))
    runner = InstrumentedStructuredAgent(
        storage,
        metadata_transport=metadata_transport,
        api_key_provider=lambda: "runtime-only-test-value",
    )

    with pytest.raises(AgentInvocationFailure, match="provider_finish_reason"):
        _invoke_plan(runner, run_id="run-sdk-drift-specialist-nonstop")

    assert provider_calls == 1
    assert metadata_calls == 1
    ledger = storage.sanitized_model_ledger()[0]
    assert ledger["outcome"] == "failed"
    assert ledger["error_invariant"] == "provider_finish_reason"
    assert ledger["response_id"] == "gen-plan-drift"
    assert ledger["finish_reason"] == "length"
    assert ledger["actual_cost_usd"] == pytest.approx(0.0033)
    assert storage.cached_model_output(ledger["cache_key"]) is None


def test_specialist_protocol_failure_has_bounded_invariant_and_ledger(tmp_path: Path):
    class Runnable:
        def invoke(self, *_args, **_kwargs):
            raise langchain_runtime.OpenRouterProtocolError()

    storage = Storage(str(tmp_path / "protocol-failure.db"))
    runner = InstrumentedStructuredAgent(
        storage,
        runnable_factory=lambda *_args: Runnable(),
        api_key_provider=lambda: "runtime-only-test-value",
    )

    with pytest.raises(AgentInvocationFailure, match="provider_response_envelope") as caught:
        _invoke_plan(runner, run_id="run-protocol-failure")

    ledger = storage.model_calls()[0]
    assert ledger["outcome"] == "failed"
    assert ledger["error_type"] == "OpenRouterProtocolError"
    assert ledger["error_invariant"] == "provider_response_envelope"
    assert caught.value.safe_context["call_id"] == ledger["call_id"]
    assert "response envelope" not in json.dumps(storage.sanitized_model_ledger())


def test_specialist_upstream_rejection_retains_only_safe_unknown_cost_evidence(
    tmp_path: Path,
):
    inference_calls = 0

    class Runnable:
        def invoke(self, *_args, **_kwargs):
            nonlocal inference_calls
            inference_calls += 1
            raise langchain_runtime.OpenRouterUpstreamRejectionError(
                response_id="gen-1786483162-CCCCCCCCCCCCCCCCCCCC",
                provider_error_code=429,
            )

    storage = Storage(str(tmp_path / "specialist-upstream-rejection.db"))
    runner = InstrumentedStructuredAgent(
        storage,
        runnable_factory=lambda *_args: Runnable(),
        api_key_provider=lambda: "runtime-only-test-value",
    )

    with pytest.raises(
        AgentInvocationFailure,
        match="provider_upstream_rejection",
    ) as captured:
        _invoke_plan(runner, run_id="run-specialist-upstream-rejection")

    assert inference_calls == 1
    assert captured.value.safe_context["response_id"] == (
        "gen-1786483162-CCCCCCCCCCCCCCCCCCCC"
    )
    assert captured.value.safe_context["provider_error_code"] == 429
    assert captured.value.safe_context["provider_boundary"] == "openrouter"
    assert captured.value.safe_context["expected_upstream_provider"] == "Together"
    ledger = storage.sanitized_model_ledger()[0]
    assert ledger["outcome"] == "failed"
    assert ledger["error_invariant"] == "provider_upstream_rejection"
    assert ledger["response_id"] == "gen-1786483162-CCCCCCCCCCCCCCCCCCCC"
    assert ledger["provider_error_code"] == 429
    assert ledger["provider_boundary"] == "openrouter"
    assert ledger["expected_upstream_provider"] == "Together"
    assert ledger["actual_cost_usd"] is None
    assert "usage_source" not in ledger
    assert "prompt_tokens" not in ledger
    assert storage.cached_model_output(ledger["cache_key"]) is None
    assert storage.model_call_summary()["actual_cost_complete"] is False
    assert storage.model_call_summary()["unknown_cost_call_count"] == 1


def test_specialist_upstream_rejection_receipt_exposes_only_bounded_status(
    tmp_path: Path,
):
    _, _, _, _, package, canonicalization, result = graph_fixture(tmp_path)
    receipts: list[dict[str, Any]] = []

    class FailingRunner:
        calls = 0

        def invoke(self, **values):
            self.calls += 1
            raise AgentInvocationFailure(
                values["agent_id"],
                "provider_upstream_rejection",
                safe_context={
                    "call_id": "modelcall-specialist-rejected",
                    "parent_call_id": values["parent_call_id"],
                    "delegation_id": values["delegation_id"],
                    "response_id": "gen-1786483163-DDDDDDDDDDDDDDDDDDDD",
                    "provider_error_code": 429,
                    "provider_boundary": "openrouter",
                    "expected_upstream_provider": "Together",
                    "outcome": "failed",
                },
            )

    runner = FailingRunner()
    orchestrator = NemotronMultiAgentOrchestrator(
        Storage(str(tmp_path / "specialist-receipt.db")),
        agent_runner=runner,
    )

    with pytest.raises(AgentInvocationFailure, match="provider_upstream_rejection"):
        orchestrator.invoke(
            run_id="run-specialist-receipt",
            orchestration_id="orch-specialist-receipt",
            observable_package=package,
            canonicalization=canonicalization,
            facts=result["facts"],
            process=result["process"],
            checklist=result["checklist"],
            verification=result["verification"],
            progress_sink=receipts.append,
        )

    assert runner.calls == 1
    failure = next(item for item in receipts if item.get("receipt_type") == "agent_failed")
    assert failure["agent_id"] == "orchestrator_plan"
    assert failure["error_invariant"] == "provider_upstream_rejection"
    assert failure["response_id"] == "gen-1786483163-DDDDDDDDDDDDDDDDDDDD"
    assert failure["provider_error_code"] == 429
    assert failure["provider_boundary"] == "openrouter"
    assert failure["expected_upstream_provider"] == "Together"
    assert "response_model" not in failure
    assert "upstream_provider" not in failure
    assert "usage_source" not in failure


def test_specialist_success_rejects_nonpinned_upstream_after_retaining_billing(
    tmp_path: Path,
):
    inference_calls = 0

    class Runnable:
        def invoke(self, *_args, **_kwargs):
            nonlocal inference_calls
            inference_calls += 1
            return _plan_envelope(
                provider_name="DeepInfra",
                usage={
                    "prompt_tokens": 31,
                    "completion_tokens": 11,
                    "total_tokens": 42,
                    "cost": 0.0031,
                },
            )

    storage = Storage(str(tmp_path / "specialist-wrong-upstream.db"))
    runner = InstrumentedStructuredAgent(
        storage,
        runnable_factory=lambda *_args: Runnable(),
        api_key_provider=lambda: "runtime-only-test-value",
    )

    with pytest.raises(
        AgentInvocationFailure,
        match="upstream_provider_policy",
    ):
        _invoke_plan(runner, run_id="run-specialist-wrong-upstream")

    assert inference_calls == 1
    ledger = storage.sanitized_model_ledger()[0]
    assert ledger["outcome"] == "failed"
    assert ledger["error_invariant"] == "upstream_provider_policy"
    assert ledger["response_id"] == "gen-plan"
    assert ledger["response_model"] == OPENROUTER_MODEL
    assert ledger["upstream_provider"] == "DeepInfra"
    assert ledger["actual_cost_usd"] == pytest.approx(0.0031)
    assert ledger["usage_source"] == "response"
    assert storage.cached_model_output(ledger["cache_key"]) is None


def test_specialist_blocked_and_actual_overrun_failures_keep_safe_ledger_lineage(
    tmp_path: Path,
):
    factory_calls = 0

    def forbidden_factory(*_args):
        nonlocal factory_calls
        factory_calls += 1
        raise AssertionError("missing credential must block before provider construction")

    blocked_storage = Storage(str(tmp_path / "blocked.db"))
    blocked_runner = InstrumentedStructuredAgent(
        blocked_storage,
        runnable_factory=forbidden_factory,
        api_key_provider=lambda: None,
    )
    with pytest.raises(AgentInvocationFailure, match="missing_credential") as blocked:
        _invoke_plan(blocked_runner, run_id="run-blocked")
    assert factory_calls == 0
    assert blocked.value.safe_context["outcome"] == "blocked_missing_credential"
    assert blocked_storage.model_calls()[0]["outcome"] == "blocked_missing_credential"

    cost_storage = Storage(str(tmp_path / "blocked-cost.db"))
    committed_call = cost_storage.create_model_call(
        run_id="prior",
        provider="openrouter",
        model=OPENROUTER_MODEL,
        cache_key="prior",
        purpose="prior paid call",
        call_count=1,
        estimated_cost_usd=25.0,
        outcome="started",
    )
    cost_storage.finish_model_call(
        committed_call, outcome="failed", actual_cost_usd=25.0
    )
    cost_runner = InstrumentedStructuredAgent(
        cost_storage,
        runnable_factory=forbidden_factory,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(AgentInvocationFailure, match="cost_guard") as blocked_cost:
        _invoke_plan(cost_runner, run_id="run-blocked-cost")
    assert blocked_cost.value.safe_context["outcome"] == "blocked_cost_guard"
    assert cost_storage.model_calls()[-1]["outcome"] == "blocked_cost_guard"

    class ExpensiveRunnable:
        def invoke(self, *_args, **_kwargs):
            return _plan_envelope(
                usage={
                    "prompt_tokens": 20,
                    "completion_tokens": 10,
                    "total_tokens": 30,
                    "cost": 26.0,
                }
            )

    overrun_storage = Storage(str(tmp_path / "overrun.db"))
    overrun_runner = InstrumentedStructuredAgent(
        overrun_storage,
        runnable_factory=lambda *_args: ExpensiveRunnable(),
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(AgentInvocationFailure, match="actual_cost_overrun") as overrun:
        _invoke_plan(overrun_runner, run_id="run-overrun")
    assert overrun.value.safe_context["outcome"] == "actual_cost_overrun"
    assert overrun.value.safe_context["response_id"] == "gen-plan"
    ledger = overrun_storage.model_calls()[0]
    assert ledger["outcome"] == "actual_cost_overrun"
    assert ledger["actual_cost_usd"] == 26.0
