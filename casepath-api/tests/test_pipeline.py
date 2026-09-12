from __future__ import annotations

from copy import deepcopy
import json
import math
import sqlite3
import time
from pathlib import Path

import pytest

from casepath_api.data import ARTIFACTS, CLAIMS, HISTORICAL_CASES, observable_claim_package
from casepath_api.canonicalizer import (
    MAX_OUTPUT_TOKENS,
    MODEL_MODE_OPENROUTER,
    OPENROUTER_MODEL,
    ModelResponseError,
    OpenRouterNemotronCanonicalizer,
    bounded_fact_assertion_catalog,
    observable_source_reference_registry,
    resolve_observable_source_reference_id,
)
from casepath_api.pipeline_v15 import (
    ClaimPipeline,
    MEMORY_OPERATION_IDS,
    _eligibility_evaluation,
    _execute_protected_output_control,
    apply_evidence_projection,
    apply_process_projection,
    decision_projection,
    digest,
    replay_case_specific_memory_transform,
    semantic_checklist_dto,
    semantic_process_dto,
)
from casepath_api.multi_agent import (
    AgentBoundaryError,
    AgentInvocationFailure,
    accepted_artifact_hash,
)
from casepath_api.precedent_ranking import rank_precedents
from casepath_api.projections import DECISION_OPTIONS
from casepath_api.storage import Storage
from casepath_api.validation import ContractValidationError


def wait(storage: Storage, run_id: str) -> dict:
    for _ in range(500):
        run = storage.get_run(run_id)
        if run and run["status"] in {"complete", "failed"}:
            return run
        time.sleep(0.01)
    raise AssertionError("run timeout")


@pytest.fixture
def runtime(tmp_path: Path) -> tuple[Storage, ClaimPipeline]:
    storage = Storage(str(tmp_path / "casepath.db"))
    return storage, ClaimPipeline(storage, pace_seconds=0)


def accepted_review(pipeline: ClaimPipeline, run_id: str, *, mode: str = "conditional") -> dict:
    return pipeline.review(
        run_id,
        {
            "decision": "approve_with_edit",
            "building_envelope_mode": mode,
            "confidence": 0.91,
            "justification": "Generated-demo edit only; qualified review has not occurred.",
        },
    )


def accepted_learning_freeze(
    storage: Storage, pipeline: ClaimPipeline
) -> tuple[dict, dict]:
    flagship = wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    accepted_review(pipeline, flagship["run_id"])
    baseline = wait(
        storage,
        pipeline.create("DEMO-MOULD-002", knowledge_mode="baseline"),
    )
    return baseline, flagship


def provider_fact_proposals(oracle_facts: list[dict]) -> list[dict]:
    registry = observable_source_reference_registry(
        observable_claim_package(CLAIMS["DEF-027-E0-DEMO"])
    )
    contracts = [
        {
            "fact_id": value["fact_id"],
            "label": value["label"],
            "controls_process": value["controls_process"],
            "decision_key": value["decision_key"],
            "normalized_options": DECISION_OPTIONS.get(value["decision_key"], {}),
            "admissible_normalized_values": (
                [value["normalized_value"]] if value["controls_process"] else []
            ),
            "expected_state": value["state"],
            "canonical_value": value["value"],
            "canonical_explanation": value["explanation"],
            "semantic_role": value["semantic_role"],
            "deterministic_confidence": value["confidence"],
            "admissible_text_refs": [
                {
                    "artifact_id": ref["artifact_id"],
                    "page": ref["page"],
                    "excerpt": ref["excerpt"],
                }
                for ref in value["source_refs"]
                if ref["locator_kind"] == "text_quote"
            ],
            "deterministic_text_refs": [
                ref
                for ref in value["source_refs"]
                if ref["locator_kind"] == "text_quote"
            ],
            "bounded_enrichments": [
                ref
                for ref in value["source_refs"]
                if ref["locator_kind"] in {"visual_observation", "metadata_field"}
            ],
        }
        for value in oracle_facts
    ]
    slots = {
        slot["fact_id"]: slot
        for slot in bounded_fact_assertion_catalog(contracts, registry)
    }
    proposals = []
    for value in oracle_facts:
        assertion = next(
            candidate
            for candidate in slots[value["fact_id"]]["assertions"]
            if candidate["state"] == value["state"]
            and candidate["value"] == value["value"]
            and candidate["normalized_value"] == value["normalized_value"]
        )
        proposal = {
            "fact_id": value["fact_id"],
            "assertion_id": assertion["assertion_id"],
            "confidence": deepcopy(value["confidence"]),
        }
        selected_ref_by_artifact: dict[str, str] = {}
        for ref in value["source_refs"]:
            if ref["locator_kind"] != "text_quote":
                continue
            selected_ref_by_artifact.setdefault(
                ref["artifact_id"],
                resolve_observable_source_reference_id(ref, registry),
            )
        proposal["source_ref_ids"] = [
            selected_ref_by_artifact[artifact_id]
            for artifact_id in sorted(selected_ref_by_artifact)
        ]
        proposals.append(proposal)
    return proposals


def provider_wire_facts(proposals: list[dict]) -> dict[str, dict]:
    """Encode normalized proposal fixtures in the strict provider-native shape."""

    registry = observable_source_reference_registry(
        observable_claim_package(CLAIMS["DEF-027-E0-DEMO"])
    )
    artifact_by_ref_id = {
        item["source_ref_id"]: item["artifact_id"] for item in registry
    }
    return {
        proposal["fact_id"]: {
            **proposal,
            "source_ref_ids": {
                artifact_by_ref_id[ref_id]: ref_id
                for ref_id in proposal["source_ref_ids"]
            },
        }
        for proposal in proposals
    }


class StubAgentOrchestrator:
    """Pipeline-only seam; real StateGraph behavior is covered in test_multi_agent_v15."""

    def invoke(self, **values):
        facts = values["facts"]
        process = values["process"]
        checklist = values["checklist"]
        progress_sink = values.get("progress_sink")
        roles = [
            "orchestrator_plan",
            "document_source_integrity",
            "process_decision_mapping",
            "evidence_checklist",
            "final_claim_brief_audit",
        ]
        agents = [
            {
                "stage": "understand",
                "acceptance_scope": "pre_review_model_output",
                "agent_id": "canonical_facts",
                "role": "Guarded Canonical Facts Agent",
                "actor_type": "nemotron_agent",
                "model": OPENROUTER_MODEL,
                "provider": "openrouter",
                "requested_model": OPENROUTER_MODEL,
                "call_count": 1,
                "parent_call_id": None,
                "delegation_id": None,
                "call_id": values["canonicalization"]["call_id"],
                "cache_hit": False,
                "outcome": "succeeded",
                "accepted_count": len(facts),
                "rejected_count": 0,
                "deterministic_fallback_applied": False,
            }
        ]
        plan_call_id = "modelcall-plan-stub"
        for index, role in enumerate(roles):
            entry = {
                "stage": role,
                "acceptance_scope": "pre_review_model_output",
                "agent_id": role,
                "role": role.replace("_", " ").title(),
                "actor_type": "nemotron_agent",
                "model": OPENROUTER_MODEL,
                "provider": "openrouter",
                "requested_model": OPENROUTER_MODEL,
                "call_count": 1,
                "parent_call_id": (
                    values["canonicalization"]["call_id"]
                    if role == "orchestrator_plan"
                    else plan_call_id
                ),
                "delegation_id": f"dlg-stub-{index}",
                "call_id": plan_call_id if role == "orchestrator_plan" else f"modelcall-{role}-stub",
                "cache_hit": False,
                "outcome": "succeeded",
                "accepted_ids": [role],
                "accepted_count": 1,
                "rejected": [],
                "rejected_count": 0,
                "deterministic_fallback_applied": False,
                "output_artifact": f"{role}_contribution",
                "input_artifact_hash": "1" * 64,
                "output_artifact_hash": "2" * 64,
            }
            agents.append(entry)
            if progress_sink:
                progress_sink(
                    {
                        "receipt_type": "agent_completed",
                        "acceptance_scope": "pre_review_model_output",
                        "agent_id": role,
                        "role": entry["role"],
                        "actor_type": "nemotron_agent",
                        "status": "completed",
                        "call_id": entry["call_id"],
                        "parent_call_id": entry["parent_call_id"],
                        "delegation_id": entry["delegation_id"],
                        "accepted_ids": entry["accepted_ids"],
                        "accepted_count": 1,
                        "rejected_count": 0,
                        "deterministic_fallback_applied": False,
                        "output_artifact": entry["output_artifact"],
                        "output_artifact_hash": entry["output_artifact_hash"],
                    }
                )
        decisions = [
            {
                "fact_id": fact["fact_id"],
                "decision_key": fact["decision_key"],
                "decision_value": fact["decision_value"],
                "state": fact["state"],
                "normalized_value": fact["normalized_value"],
                "source_ref_ids": [],
                "contribution_id": (
                    f"fact:{fact['fact_id']}:decision_value"
                ),
                "contribution_scope": (
                    "canonical_to_process_decision_mapping"
                ),
                "model_owned_fields": ["decision_value"],
                "confidence_basis_points": 8200,
                "attribution": "Process Decision Mapping Agent",
                "deterministic_fallback_applied": False,
            }
            for fact in facts
            if fact["controls_process"]
        ]
        evidence_items = [
            {
                "item_id": item["item_id"],
                "status": item["status"],
                "artifact_ids": sorted(item.get("artifact_ids", [])),
                "source_ref_ids": [],
                "field_contributions": [
                    {
                        "contribution_id": f"item:{item['item_id']}:status",
                        "field": "status",
                        "attribution": "Evidence and Checklist Agent",
                        "confidence_basis_points": 8300,
                        "deterministic_fallback_applied": False,
                    },
                    {
                        "contribution_id": f"item:{item['item_id']}:artifacts",
                        "field": "artifact_ids",
                        "attribution": "Evidence and Checklist Agent",
                        "confidence_basis_points": 8300,
                        "deterministic_fallback_applied": False,
                    },
                ],
                "model_owned_fields": ["status", "artifact_ids"],
                "confidence_basis_points": 8300,
                "attribution": "Evidence and Checklist Agent",
                "deterministic_fallback_applied": False,
            }
            for item in checklist["items"]
        ]
        final_brief = {
            "current_node_id": process["current_overlay"]["current_node_id"],
            "next_action_node_id": process["current_overlay"]["next_action_node_id"],
            "supporting_fact_ids": sorted(
                next(
                    node
                    for node in process["nodes"]
                    if node["node_id"]
                    == process["current_overlay"]["current_node_id"]
                ).get("fact_ids", [])
            ),
            "upstream_contribution_ids": [
                "document_source_integrity",
                "evidence_checklist",
                "process_decision_mapping",
            ],
            "audit_check_ids": [
                "current_node_supported_by_canonical_facts",
                "evidence_items_bound_to_process_nodes",
                "next_action_connected_in_static_topology",
                "upstream_contribution_lineage_complete",
            ],
            "source_ref_ids": [],
            "input_contribution_ids": [
                "document_source_integrity",
                "evidence_checklist",
                "process_decision_mapping",
            ],
            "lineage_authority": "hybrid_guarded_model_audit",
            "confidence_basis_points": 8400,
            "attribution": "Final Claim Brief Agent",
            "deterministic_fallback_applied": False,
        }
        gate_outputs = {
            "deterministic_process_gate": accepted_artifact_hash(process),
            "deterministic_evidence_gate": accepted_artifact_hash(checklist),
            "whole_playbook_gate": accepted_artifact_hash(
                {
                    "process": process,
                    "checklist": checklist,
                    "final_brief": final_brief,
                }
            ),
        }
        gates = [
            {
                "agent_id": gate_id,
                "role": gate_id.replace("_", " ").title(),
                "actor_type": "deterministic_gate",
                "model": None,
                "outcome": "passed",
                "input_artifact_hash": "3" * 64,
                "output_artifact_hash": gate_outputs[gate_id],
            }
            for gate_id in (
                "deterministic_process_gate",
                "deterministic_evidence_gate",
                "whole_playbook_gate",
            )
        ]
        return {
            "schema_version": "casepath.nemotron-agent-dag/1.0.0",
            "implementation": "langgraph_stategraph_langchain_openrouter",
            "orchestration_id": values["orchestration_id"],
            "model": OPENROUTER_MODEL,
            "authority_mode": "multi_agent_hybrid_guarded",
            "all_required_agents_contributed": True,
            "external_tracing": False,
            "agents": agents,
            "deterministic_gates": gates,
            "specialist_artifacts": {
                "orchestrator_plan": {"focus_fact_ids": [facts[0]["fact_id"]]},
                "document_source_integrity": {"artifacts": []},
                "process_decision_mapping": {"decisions": decisions},
                "evidence_checklist": {"items": evidence_items},
                "final_claim_brief_audit": final_brief,
            },
            "final_claim_brief": final_brief,
        }


def test_source_artifacts_are_real_files():
    lease = ARTIFACTS["art_lease"]
    assert lease["media_type"] == "application/pdf"
    assert lease["page_count"] == 6
    assert lease["path"].read_bytes().startswith(b"%PDF")
    assert ARTIFACTS["art_photo"]["path"].read_bytes()[:2] == b"\xff\xd8"
    assert "From:" in ARTIFACTS["art_notification"]["path"].read_text()
    assert ARTIFACTS["art_photo"]["sha256"] == "b8de375c0a951e3970f4b4a392b5af348ea35b30f5750974fa1d9411da179860"
    assert ARTIFACTS["art_later_photo"]["sha256"] == "ff16af84a7dffa53305de336bc6cebeb80cb1c8b1544a3303d29caa92f8d5e9f"
    assert ARTIFACTS["art_later_lease"]["page_count"] == 2
    assert ARTIFACTS["art_later_lease"]["path"].read_bytes().startswith(b"%PDF")
    assert "Please arrange an inspection" in ARTIFACTS["art_later_notification"]["email"]["body"]
    assert "We received your message" in ARTIFACTS["art_later_management_reply"]["email"]["body"]
    assert "signed" not in ARTIFACTS["art_lease"]["description"].lower()
    assert "signed" not in ARTIFACTS["art_later_lease"]["description"].lower()
    assert all(
        "signed" not in page.lower()
        for artifact_id in ("art_lease", "art_later_lease")
        for page in ARTIFACTS[artifact_id]["pages"]
    )


@pytest.mark.parametrize("claim_id", ["DEF-027-E0-DEMO", "DEMO-MOULD-002"])
def test_v15_completed_outputs_have_no_dangling_contract_refs(runtime, claim_id: str):
    storage, pipeline = runtime
    run = wait(storage, pipeline.create(claim_id))
    assert run["status"] == "complete", run.get("error")
    result = run["result"]
    assert result["verification"]["valid"] is True
    assert result["verification"]["computed"] is True
    assert len(result["verification"]["checks"]) == 11
    assert len(result["process"]["nodes"]) == 19
    assert len(result["process"]["edges"]) == 22
    assert result["process"]["validator"] == {
        "valid": True,
        "computed": True,
        "checks": ["Graph integrity", "Law-to-process linkage", "Current-state safety"],
    }
    assert result["checklist"]["validator"]["valid"] is True
    supplied = {value["item_id"] for value in result["checklist"]["present"]}
    requested = {value["item_id"] for value in result["checklist"]["required"]}
    assert supplied.isdisjoint(requested)
    facts_by_id = {value["fact_id"]: value for value in result["facts"]}
    for item in result["checklist"]["items"]:
        if item["status"].startswith("provided"):
            fact_sources = {
                ref["artifact_id"]
                for ref in facts_by_id[item["fact_id"]]["source_refs"]
            }
            assert set(item["artifact_ids"]) & fact_sources


def test_whole_playbook_validation_binds_exact_projection_and_checklist_derivations(
    runtime,
):
    storage, pipeline = runtime
    result = wait(storage, pipeline.create("DEF-027-E0-DEMO"))["result"]
    claim = CLAIMS["DEF-027-E0-DEMO"]
    understanding = {"facts": result["facts"]}

    def verify(
        *,
        process: dict | None = None,
        checklist: dict | None = None,
    ) -> dict:
        return pipeline._verification_report(
            claim,
            understanding,
            result["legal_research"],
            deepcopy(process if process is not None else result["process"]),
            deepcopy(checklist if checklist is not None else result["checklist"]),
            result["precedents"],
        )

    assert verify()["valid"] is True

    tampered_overlay = deepcopy(result["process"])
    tampered_overlay["current_overlay"]["decisions"]["causation"] = (
        "cause_building"
    )
    with pytest.raises(ContractValidationError, match="current_overlay.decisions"):
        verify(process=tampered_overlay)

    tampered_node = deepcopy(result["process"])
    current_node = next(
        node
        for node in tampered_node["nodes"]
        if node["node_id"] == tampered_node["current_node"]
    )
    current_node["answer"] = "Tampered projected answer"
    with pytest.raises(ContractValidationError, match="nodes.*answer"):
        verify(process=tampered_node)

    tampered_edge = deepcopy(result["process"])
    selected_edge = next(
        edge for edge in tampered_edge["edges"] if edge["state"] == "selected"
    )
    selected_edge["state"] = "possible"
    with pytest.raises(ContractValidationError, match="edges.*state"):
        verify(process=tampered_edge)

    tampered_summary = deepcopy(result["checklist"])
    tampered_summary["summary"]["missing"] += 1
    with pytest.raises(ContractValidationError, match="summary"):
        verify(checklist=tampered_summary)

    tampered_present = deepcopy(result["checklist"])
    tampered_present["present"][0]["why"] = "Tampered derived entry"
    with pytest.raises(ContractValidationError, match="present"):
        verify(checklist=tampered_present)


def test_model_final_result_consumes_only_matching_final_brief_route(tmp_path: Path):
    oracle_storage = Storage(str(tmp_path / "final-selector-oracle.db"))
    oracle = ClaimPipeline(oracle_storage, pace_seconds=0)
    result = wait(
        oracle_storage, oracle.create("DEF-027-E0-DEMO")
    )["result"]
    pipeline = ClaimPipeline(
        Storage(str(tmp_path / "final-selector-model.db")),
        model_mode=MODEL_MODE_OPENROUTER,
        canonicalizer=object(),
        agent_orchestrator=object(),
        pace_seconds=0,
    )
    overlay = result["process"]["current_overlay"]

    class TrackingBrief(dict):
        item_reads: list[str]

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.item_reads = []

        def __getitem__(self, key):
            self.item_reads.append(key)
            return super().__getitem__(key)

    final_brief = TrackingBrief(
        current_node_id=overlay["current_node_id"],
        next_action_node_id=overlay["next_action_node_id"],
    )
    understanding = {
        key: result[key]
        for key in (
            "summary",
            "scope",
            "category",
            "subcategory",
            "dispute",
            "facts",
            "issues",
        )
    }
    values = {
        "claim": CLAIMS["DEF-027-E0-DEMO"],
        "parsed": {"input_hash": "1" * 64},
        "understanding": understanding,
        "legal": result["legal_research"],
        "process": result["process"],
        "checklist": result["checklist"],
        "precedents": result["precedents"],
        "verification": result["verification"],
        "knowledge": {"version": result["process"]["playbook_version"]},
        "knowledge_mode": "current",
    }
    model_result = pipeline._final_result(
        **values,
        agent_orchestration={"final_claim_brief": final_brief},
    )
    assert final_brief.item_reads == [
        "current_node_id",
        "next_action_node_id",
    ]
    nodes = {node["node_id"]: node for node in result["process"]["nodes"]}
    assert model_result["current_blocker"] == nodes[
        final_brief["current_node_id"]
    ]["question"]
    assert model_result["next_action"]["process_node_id"] == final_brief[
        "next_action_node_id"
    ]

    mismatched = {
        "current_node_id": "scope",
        "next_action_node_id": overlay["next_action_node_id"],
    }
    with pytest.raises(AgentBoundaryError, match="final_route_binding"):
        pipeline._final_result(
            **values,
            agent_orchestration={"final_claim_brief": mismatched},
        )


def test_later_claim_is_in_scope_and_reaches_causation_from_attachments(runtime):
    storage, pipeline = runtime
    result = wait(storage, pipeline.create("DEMO-MOULD-002"))["result"]
    tenancy = next(value for value in result["facts"] if value["fact_id"] == "later_fact_tenancy")
    assert tenancy["state"] == "known"
    assert tenancy["normalized_value"] == "supported_in_scope"
    assert {ref["artifact_id"] for ref in tenancy["source_refs"]} == {"art_later_lease"}
    assert result["category"] == "Rental defect - mould and moisture"
    assert result["scope"] == "Swiss residential tenancy"
    assert result["process"]["current_node"] == "causation"
    assert result["process"]["selected_path"] == [
        "intake", "scope", "dispute", "urgency", "notification", "defect", "causation", "evidence_gap",
    ]
    assert result["process"]["current_overlay"]["next_action_node_id"] == "evidence_gap"
    items = {value["item_id"]: value for value in result["checklist"]["items"]}
    assert items["lease"]["artifact_ids"] == ["art_later_lease"]
    assert items["management_position"]["artifact_ids"] == ["art_later_management_reply"]
    assert items["health_safety_statement"]["status"] == "provided_sufficient"
    assert items["defect_notice"]["artifact_ids"] == ["art_later_notification"]
    assert items["proof_of_delivery"]["artifact_ids"] == ["art_later_management_reply"]
    assert items["building_envelope"]["status"] == "missing"
    assert items["building_envelope"]["current_path"] is True


def test_all_model_visible_subjects_and_filenames_are_neutral() -> None:
    shortcuts = {"mould", "ventilation", "condensation", "tenant fault"}
    for claim in CLAIMS.values():
        package = observable_claim_package(claim)
        surfaces = [package["customer_message"]["subject"]]
        for artifact in package["artifacts"]:
            surfaces.append(artifact["filename"])
            if isinstance(artifact.get("parsed_email"), dict):
                surfaces.append(
                    str(artifact["parsed_email"].get("subject", ""))
                )
        normalized = "\n".join(surfaces).casefold()
        assert all(shortcut not in normalized for shortcut in shortcuts)


def test_primary_scope_dispute_and_notification_propositions_have_sufficient_exact_refs(runtime):
    storage, pipeline = runtime
    result = wait(storage, pipeline.create("DEF-027-E0-DEMO"))["result"]
    facts = {value["fact_id"]: value for value in result["facts"]}

    def text_ref_tuples(fact_id: str) -> set[tuple[str, int, str]]:
        return {
            (ref["artifact_id"], ref["page"], ref["excerpt"])
            for ref in facts[fact_id]["source_refs"]
            if ref["locator_kind"] == "text_quote"
        }

    assert text_ref_tuples("fact_tenancy") == {
        ("art_lease", 1, "Residential Lease Agreement"),
        ("art_lease", 1, "Tenant Alex Morgan, Feldbergstrasse 114, 4057 Basel"),
        ("art_lease", 1, "The apartment is rented for residential use."),
    }
    assert text_ref_tuples("fact_dispute") == {
        ("message", 1, "I disagree because the problem keeps returning."),
        ("message", 1, "I want the cause clarified and the defect repaired."),
        ("art_management_reply", 1, "the marks appear consistent with insufficient ventilation"),
        ("art_management_reply", 1, "We do not currently plan a technical inspection."),
    }
    assert text_ref_tuples("fact_notification") == {
        ("art_notification", 1, "Wed, 15 Jul 2026 08:32:00 +0200"),
        ("art_notification", 1, "Please arrange an inspection and repair."),
        ("art_delivery", 1, "Accepted by recipient mail server"),
    }
    assert "residential lease agreement" in facts["fact_tenancy"]["explanation"]
    assert "cause clarification and repair" in facts["fact_dispute"]["explanation"]
    assert "dated 15 July 2026" in facts["fact_notification"]["explanation"]


def test_verifier_rejects_unknown_fact_and_evidence_ids(runtime):
    storage, pipeline = runtime
    run = wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    result = deepcopy(run["result"])
    result["process"]["nodes"][0]["fact_ids"] = ["unknown_fact"]
    result["process"]["nodes"][0]["evidence_requirement_ids"] = ["unknown_evidence"]
    with pytest.raises(ContractValidationError) as caught:
        pipeline._verification_report(  # noqa: SLF001 - acceptance-gate regression test
            CLAIMS[run["claim_id"]],
            {"facts": result["facts"]},
            result["legal_research"],
            result["process"],
            result["checklist"],
            result["precedents"],
        )
    paths = {issue.path for issue in caught.value.issues}
    assert "nodes[0].fact_ids[0]" in paths
    assert "nodes[0].evidence_requirement_ids[0]" in paths


def test_verifier_rejects_unknown_source_and_precedent_provenance(runtime):
    storage, pipeline = runtime
    run = wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    result = deepcopy(run["result"])
    result["facts"][0]["source_refs"][0]["artifact_id"] = "hidden_answer_file"
    result["precedents"][0]["review_status"] = "expert_reviewed_memory"
    with pytest.raises(ContractValidationError):
        pipeline._verification_report(  # noqa: SLF001
            CLAIMS[run["claim_id"]],
            {"facts": result["facts"]},
            result["legal_research"],
            result["process"],
            result["checklist"],
            result["precedents"],
        )


def test_verifier_rejects_provided_evidence_not_linked_to_fact_source(runtime):
    storage, pipeline = runtime
    run = wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    result = deepcopy(run["result"])
    policy = next(value for value in result["checklist"]["items"] if value["item_id"] == "policy_reference")
    policy["artifact_ids"] = ["message"]
    with pytest.raises(ContractValidationError, match="ground its linked fact"):
        pipeline._verification_report(  # noqa: SLF001
            CLAIMS[run["claim_id"]],
            {"facts": result["facts"]},
            result["legal_research"],
            result["process"],
            result["checklist"],
            result["precedents"],
        )


def test_grounding_rejects_fake_image_quote_invalid_region_and_metadata_mismatch(runtime):
    storage, pipeline = runtime
    run = wait(storage, pipeline.create("DEF-027-E0-DEMO"))

    fake_quote = deepcopy(run["result"])
    visual_fact = next(
        value for value in fake_quote["facts"]
        if any(ref["locator_kind"] == "visual_observation" for ref in value["source_refs"])
    )
    visual_index = next(
        index for index, ref in enumerate(visual_fact["source_refs"])
        if ref["locator_kind"] == "visual_observation"
    )
    artifact_id = visual_fact["source_refs"][visual_index]["artifact_id"]
    visual_fact["source_refs"][visual_index] = {
        "artifact_id": artifact_id,
        "locator_kind": "text_quote",
        "page": 1,
        "excerpt": "The image proves a building defect.",
        "agent": "Claim Understanding Agent",
    }
    with pytest.raises(ContractValidationError, match="text quotes require an observable textual source"):
        pipeline._verification_report(  # noqa: SLF001
            CLAIMS[run["claim_id"]],
            {"facts": fake_quote["facts"]},
            fake_quote["legal_research"],
            fake_quote["process"],
            fake_quote["checklist"],
            fake_quote["precedents"],
        )

    bad_region = deepcopy(run["result"])
    visual_ref = next(
        ref for value in bad_region["facts"] for ref in value["source_refs"]
        if ref["locator_kind"] == "visual_observation"
    )
    visual_ref["region"] = [0.9, 0.9, 0.2, 0.2]
    with pytest.raises(ContractValidationError, match="hash-bound"):
        pipeline._verification_report(  # noqa: SLF001
            CLAIMS[run["claim_id"]],
            {"facts": bad_region["facts"]},
            bad_region["legal_research"],
            bad_region["process"],
            bad_region["checklist"],
            bad_region["precedents"],
        )

    bad_metadata = deepcopy(run["result"])
    metadata_ref = next(
        ref for value in bad_metadata["facts"] for ref in value["source_refs"]
        if ref["locator_kind"] == "metadata_field"
    )
    metadata_ref["value"] = "mismatched-observed-value"
    with pytest.raises(ContractValidationError, match="metadata value does not match"):
        pipeline._verification_report(  # noqa: SLF001
            CLAIMS[run["claim_id"]],
            {"facts": bad_metadata["facts"]},
            bad_metadata["legal_research"],
            bad_metadata["process"],
            bad_metadata["checklist"],
            bad_metadata["precedents"],
        )


@pytest.mark.parametrize(
    ("decision_key", "normalized_value", "decision_value", "expected_current", "expected_next"),
    [
        ("scope", "supported_out_of_scope", "out_of_scope", "scope", "out_of_scope"),
        ("dispute", "absent", "no_dispute", "dispute", "no_dispute"),
        ("urgency", "urgent", "urgent", "urgency", "urgent_escalation"),
        ("notification", "unverified", "notification_unverified", "notification", "formal_notice"),
        ("recurrence", "unverified", "recurrence_unverified", "defect", "defect"),
        ("causation", "building", "cause_building", "causation", "building_defect"),
    ],
)
def test_typed_fact_decisions_own_process_and_evidence_projection(
    runtime,
    decision_key: str,
    normalized_value: str,
    decision_value: str,
    expected_current: str,
    expected_next: str,
):
    storage, pipeline = runtime
    result = wait(storage, pipeline.create("DEF-027-E0-DEMO"))["result"]
    facts = deepcopy(result["facts"])
    controlling = next(value for value in facts if value["decision_key"] == decision_key)
    controlling["normalized_value"] = normalized_value
    controlling["decision_value"] = decision_value

    projection = decision_projection(facts)
    nodes = deepcopy(result["process"]["nodes"])
    edges = deepcopy(result["process"]["edges"])
    overlay = apply_process_projection(nodes, edges, projection, result["process"]["main_spine"])
    projected_process = {
        **deepcopy(result["process"]),
        "nodes": nodes,
        "edges": edges,
        "current_node": projection["current_node"],
        "selected_path": projection["selected_path"],
        "current_overlay": overlay,
    }
    assert projected_process["current_node"] == expected_current
    assert overlay["next_action_node_id"] == expected_next
    assert len(nodes) == 19
    assert len(edges) == 22
    assert result["category"] == "Rental defect - mould and moisture"

    projected_items = deepcopy(result["checklist"]["items"])
    apply_evidence_projection(projected_items, projected_process)
    before = {(value["item_id"], value["status"], value["current_path"]) for value in result["checklist"]["items"]}
    after = {(value["item_id"], value["status"], value["current_path"]) for value in projected_items}
    assert after != before


def test_post_review_result_is_recomputed_and_reverified(runtime):
    storage, pipeline = runtime
    run = wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    before_hash = run["result"]["verification"]["whole_playbook_hash"]
    before_fact_ids = {
        value["node_id"]: value["fact_ids"]
        for value in run["result"]["process"]["nodes"]
    }
    reviewed = accepted_review(pipeline, run["run_id"])
    assert reviewed["accepted"] is True
    assert reviewed["verification"]["valid"] is True
    assert reviewed["verification"]["computed"] is True
    assert reviewed["verification"]["whole_playbook_hash"] != before_hash
    assert all(
        operation["component"] in {"process_graph", "evidence_model"}
        and operation["operation"] in {"add", "replace"}
        and operation["pointer"].startswith("/")
        for operation in reviewed["review"]["operations"]
    )
    assert reviewed["result"]["process"]["playbook_version"] == "mould-playbook-v3"
    assert reviewed["result"]["checklist"]["playbook_version"] == "mould-playbook-v3"
    assert reviewed["result"]["playbook"]["version"] == "mould-playbook-v3"
    reviewed_nodes = {value["node_id"]: value for value in reviewed["result"]["process"]["nodes"]}
    assert {
        node_id: reviewed_nodes[node_id]["fact_ids"]
        for node_id in before_fact_ids
    } == before_fact_ids
    assert reviewed_nodes["ventilation_dispute"]["fact_ids"] == ["fact_ventilation_allegation"]
    assert not any(
        fact_id.startswith("later_fact_")
        for node in reviewed_nodes.values()
        for fact_id in node["fact_ids"]
    )
    transform = reviewed["review_transform"]
    assert transform == reviewed["result"]["audit"]["review_transform"]
    assert transform["acceptance_scope"] == "post_review_unverified_transform"
    assert transform["authority"] == "unverified_demo_user"
    assert transform["qualification_status"] == "not_verified"
    assert transform["input_run_id"] == run["run_id"]
    assert transform["input_process_hash"] == digest(run["result"]["process"])
    assert transform["input_checklist_hash"] == digest(run["result"]["checklist"])
    assert transform["output_process_hash"] == digest(reviewed["result"]["process"])
    assert transform["output_checklist_hash"] == digest(reviewed["result"]["checklist"])
    assert transform["model_acceptance_reused"] is False


def test_reject_cannot_create_memory_or_activate_knowledge(runtime):
    storage, pipeline = runtime
    run = wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    original = deepcopy(run["result"])
    response = pipeline.review(
        run["run_id"],
        {
            "decision": "reject",
            "building_envelope_mode": "conditional",
            "confidence": 0.2,
            "justification": "Reject this generated-demo edit.",
        },
    )
    assert response["accepted"] is False
    assert response["memory_id"] is None
    assert response["candidate"] is None
    assert response["result"] == original
    assert storage.memories() == []
    assert storage.candidates() == []
    assert pipeline.knowledge()["active_playbook"]["version"] == "mould-playbook-v3"
    assert storage.get_run(run["run_id"])["result"] == original


def test_one_review_creates_memory_and_quarantined_candidate(runtime):
    storage, pipeline = runtime
    run = wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    response = accepted_review(pipeline, run["run_id"])
    candidate = response["candidate"]
    assert candidate["status"] == "quarantined"
    assert candidate["supporting_claims"] == ["DEF-027-E0-DEMO"]
    assert candidate["support_count"] == 1
    assert candidate["required_support"] == 3
    assert candidate["qualified_support_count"] == 0
    assert candidate["required_qualified_support"] == 3
    assert candidate["support_authority"] == "unverified_demo_only"
    assert candidate["target_tests"]["status"] == "passed"
    assert candidate["target_tests"]["failed"] == 0
    assert candidate["protected_regression"]["status"] == "passed"
    assert candidate["protected_regression"]["failed"] == 0
    protected_output = next(
        case
        for case in candidate["protected_regression"]["cases"]
        if case["case_id"] == "source_claim_full_playbook_unchanged"
    )
    assert protected_output["expected_memory_application"] is False
    assert protected_output["actual_memory_application"] is False
    assert protected_output["execution_contract"] == "deterministic_case_specific_memory_gate/1.0.0"
    assert protected_output["gate_executed"] is True
    assert protected_output["output_unchanged"] is True
    assert protected_output["before_hashes"] == protected_output["after_hashes"]
    assert set(protected_output["before_hashes"]) == {
        "result_hash",
        "process_hash",
        "checklist_hash",
    }
    review = storage.get_review_for_run(run["run_id"])
    assert review is not None
    assert digest(review["protected_output_snapshot"]) == review["pre_review_result_hash"]
    eligible_guidance = deepcopy(storage.memories()[0]["case_specific_guidance"])
    eligible_guidance["eligibility"]["source_claim_id"] = "OTHER-SOURCE"
    applied_control = _execute_protected_output_control(
        eligible_guidance,
        {"result": review["protected_output_snapshot"]},
    )
    assert applied_control["actual_memory_application"] is True
    assert applied_control["output_unchanged"] is False
    assert applied_control["before_hashes"] != applied_control["after_hashes"]
    assert candidate["target_tests"]["manifest_hash"]
    assert candidate["protected_regression"]["manifest_hash"]
    assert candidate["approval"] == {"status": "pending", "qualified_reviewer": False}
    assert candidate["shared_knowledge_changed"] is False
    memory = storage.memories()[0]
    assert memory["memory_contract"] == "casepath.reviewed-case-memory/1.0.0"
    assert memory["authority"] == "unverified_demo"
    assert memory["scope"] == "case_specific_guidance_only"
    assert len(memory["content_hash"]) == 64
    assert memory["case_specific_guidance"]["enabled"] is True
    assert memory["review_status"] == "unverified_demo_memory"
    assert memory["reviewer"] == {
        "type": "unverified_demo_user",
        "qualification_status": "not_verified",
    }
    assert memory["shared_rule_authority"] is False
    assert memory["playbook_version"] == "mould-playbook-v3"
    assert memory["verification"]["valid"] is True
    stages = [value["stage"] for value in storage.get_run(run["run_id"])["events"]]
    assert stages[-2:] == ["review", "consolidate"]


def test_required_now_does_not_release_conditional_rule(runtime):
    storage, pipeline = runtime
    run = wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    response = accepted_review(pipeline, run["run_id"], mode="required_now")
    envelope = next(
        value for value in response["result"]["checklist"]["items"]
        if value["item_id"] == "building_envelope"
    )
    assert envelope["status"] == "missing"
    assert response["candidate"]["status"] == "quarantined"
    assert response["knowledge"]["shared_playbook_version"] == "mould-playbook-v3"
    assert response["knowledge"]["shared_knowledge_changed"] is False


def test_static_precedents_are_generated_reference_not_expert_reviewed():
    assert HISTORICAL_CASES
    assert {value["review_status"] for value in HISTORICAL_CASES} == {"generated_reference"}
    assert all(value["provenance"] == "generated_reference_not_qualified_review" for value in HISTORICAL_CASES)
    assert all("expert_correction" not in value for value in HISTORICAL_CASES)


def test_later_claim_retrieves_memory_without_promoting_shared_rule(runtime):
    storage, pipeline = runtime
    flagship = wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    accepted_review(pipeline, flagship["run_id"])
    later = wait(storage, pipeline.create("DEMO-MOULD-002", knowledge_mode="current"))
    assert later["status"] == "complete", later.get("error")
    result = later["result"]
    assert result["reviewed_memory_used"] is True
    assert result["shared_rule_applied"] is False
    assert result["playbook"]["version"] == "mould-playbook-v3"
    assert result["process"]["playbook_version"] == "mould-playbook-v3"
    assert result["precedents"][0]["review_status"] == "unverified_demo_memory"
    assert result["precedents"][0]["claim_id"] == "DEF-027-E0-DEMO"
    receipt = result["memory_application"]
    assert receipt["contract"] == "casepath.memory-application-receipt/1.0.0"
    assert receipt["authority"] == "unverified_demo"
    assert receipt["shared_rule_applied"] is False
    assert receipt["before"]["process_dto_hash"] != receipt["after"]["process_dto_hash"]
    assert receipt["before"]["checklist_dto_hash"] != receipt["after"]["checklist_dto_hash"]
    assert {value["node_id"] for value in result["process"]["nodes"]} - {
        value["node_id"]
        for value in wait(storage, pipeline.create("DEMO-MOULD-002", knowledge_mode="baseline"))["result"]["process"]["nodes"]
    } == {"ventilation_dispute"}
    assert {
        (value["source"], value["target"])
        for value in result["process"]["edges"]
        if value["source"] == "ventilation_dispute" or value["target"] == "ventilation_dispute"
    } == {("evidence_gap", "ventilation_dispute"), ("ventilation_dispute", "causation")}
    envelope = next(value for value in result["checklist"]["items"] if value["item_id"] == "building_envelope")
    assert envelope["status"] == "conditional"
    assert envelope["current_path"] is True
    use_evidence = next(value for value in result["checklist"]["items"] if value["item_id"] == "use_evidence")
    assert use_evidence["node_id"] == "ventilation_dispute"
    assert pipeline.knowledge()["active_playbook"]["version"] == "mould-playbook-v3"


def test_learning_proof_is_bound_to_completed_later_runs(runtime):
    storage, pipeline = runtime
    flagship = wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    accepted_review(pipeline, flagship["run_id"])
    baseline = wait(storage, pipeline.create("DEMO-MOULD-002", knowledge_mode="baseline"))
    later = wait(storage, pipeline.create("DEMO-MOULD-002", knowledge_mode="current"))
    proof = pipeline.learning_proof(baseline["run_id"], later["run_id"])
    assert proof["ready"] is True
    assert proof["computed"] is True
    assert proof["baseline_run_id"] == baseline["run_id"]
    assert proof["later_run_id"] == later["run_id"]
    assert proof["counterfactual_learning_freeze"] == baseline[
        "counterfactual_learning_freeze"
    ]
    assert proof["counterfactual_learning_freeze"]["application_suppressed"] is True
    assert proof["before"]["result_hash"] != proof["after"]["result_hash"]
    assert proof["before"]["observable_input_hash"] == proof["after"]["observable_input_hash"]
    assert proof["before"]["canonical_state_hash"] == proof["after"]["canonical_state_hash"]
    assert proof["causal_delta"]["nonzero"] is True
    assert proof["causal_delta"]["process"]["added_node_ids"] == ["ventilation_dispute"]
    assert proof["causal_delta"]["evidence"]["changed_item_ids"] == [
        "building_envelope",
        "management_position",
        "use_evidence",
    ]
    assert proof["memory_application_proof"] == {
        **proof["memory_application_proof"],
        "receipt_present": True,
        "receipt_valid": True,
        "source_memory_current": True,
        "before_hashes_match": True,
        "after_hashes_match": True,
        "allowed_delta_exact": True,
    }
    assert {value["status"] for value in proof["deterministic_checks"]} == {"passed"}
    assert proof["reviewed_memory_proof"]["used"] is True
    assert proof["reviewed_memory_proof"]["present_in_baseline"] is False
    assert proof["reviewed_memory_proof"]["present_in_later_run"] is True
    assert proof["changes"]["precedent_claim_ids_added"] == ["DEF-027-E0-DEMO"]
    assert proof["shared_rule"]["applied"] is False
    assert proof["shared_rule"]["version_before"] == "mould-playbook-v3"
    assert proof["shared_rule"]["version_after"] == "mould-playbook-v3"
    with pytest.raises(ValueError):
        pipeline.learning_proof(later["run_id"], later["run_id"])


def test_learning_proof_rejects_baseline_created_before_learning_freeze(runtime):
    storage, pipeline = runtime
    baseline = wait(
        storage,
        pipeline.create("DEMO-MOULD-002", knowledge_mode="baseline"),
    )
    flagship = wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    accepted_review(pipeline, flagship["run_id"])
    later = wait(
        storage,
        pipeline.create("DEMO-MOULD-002", knowledge_mode="current"),
    )
    with pytest.raises(ValueError, match="counterfactual_learning_freeze"):
        pipeline.learning_proof(baseline["run_id"], later["run_id"])


def test_learning_proof_rejects_current_run_started_before_baseline_completed(runtime):
    storage, pipeline = runtime
    flagship = wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    accepted_review(pipeline, flagship["run_id"])
    baseline = wait(
        storage,
        pipeline.create("DEMO-MOULD-002", knowledge_mode="baseline"),
    )
    later = wait(
        storage,
        pipeline.create("DEMO-MOULD-002", knowledge_mode="current"),
    )
    with storage.connect() as connection:
        row = connection.execute(
            "SELECT payload FROM runs WHERE run_id=?", (later["run_id"],)
        ).fetchone()
        payload = json.loads(row["payload"])
        connection.execute(
            "UPDATE runs SET created_at=? WHERE run_id=?",
            ("2000-01-01T00:00:00+00:00", later["run_id"]),
        )
        assert payload["status"] == "complete"
    with pytest.raises(ValueError, match="counterfactual_learning_temporal_order"):
        pipeline.learning_proof(baseline["run_id"], later["run_id"])


def test_learning_proof_is_not_ready_without_a_nonzero_memory_delta(runtime):
    storage, pipeline = runtime
    baseline = wait(storage, pipeline.create("DEMO-MOULD-002", knowledge_mode="baseline"))
    current = wait(storage, pipeline.create("DEMO-MOULD-002", knowledge_mode="current"))
    proof = pipeline.learning_proof(baseline["run_id"], current["run_id"])
    assert proof["ready"] is False
    assert proof["causal_delta"]["nonzero"] is False
    assert proof["memory_application_proof"]["receipt_present"] is False
    failed = {value["name"] for value in proof["deterministic_checks"] if value["status"] == "failed"}
    assert "Nonzero causal DTO delta" in failed
    assert "Exact current memory receipt" in failed


def test_required_now_memory_is_valid_but_ineligible_for_later_claim(runtime):
    storage, pipeline = runtime
    flagship = wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    review = accepted_review(pipeline, flagship["run_id"], mode="required_now")
    assert review["candidate"]["target_tests"]["status"] == "failed"
    later = wait(storage, pipeline.create("DEMO-MOULD-002", knowledge_mode="current"))
    assert later["status"] == "complete", later.get("error")
    assert later["result"]["memory_application"] is None
    assert later["result"]["memory_used"] is False
    assert later["result"]["reviewed_memory_used"] is False
    assert later["result"]["reviewed_memory_retrieved"] is True
    assert later["result"]["knowledge"] == {
        **later["result"]["knowledge"],
        "reviewed_memory_used": False,
        "reviewed_memory_retrieved": True,
    }
    assert all(value["node_id"] != "ventilation_dispute" for value in later["result"]["process"]["nodes"])


def test_rehashed_required_now_memory_cannot_grant_reusable_authority(runtime):
    storage, pipeline = runtime
    flagship = wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    accepted_review(pipeline, flagship["run_id"], mode="required_now")
    with storage.connect() as connection:
        row = connection.execute("SELECT memory_id, payload FROM memories").fetchone()
        payload = json.loads(row["payload"])
        guidance = payload["case_specific_guidance"]
        guidance["enabled"] = True
        guidance["variant"] = "disputed_ventilation_neutral_first_v1"
        guidance["allowed_operation_ids"] = list(MEMORY_OPERATION_IDS)
        payload["content_hash"] = digest(
            {
                key: value
                for key, value in payload.items()
                if key not in {"content_hash", "memory_id", "claim_id", "updated_at"}
            }
        )
        connection.execute(
            "UPDATE memories SET payload=? WHERE memory_id=?",
            (json.dumps(payload), row["memory_id"]),
        )

    later = wait(
        storage,
        pipeline.create("DEMO-MOULD-002", knowledge_mode="current"),
    )
    assert later["status"] == "failed"
    assert later["error"] == "MemoryApplicationError: memory_origin_binding"
    assert later["accepted_state"]["final_playbook_accepted"] is False


def test_forged_memory_fails_current_run_closed(runtime):
    storage, pipeline = runtime
    flagship = wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    accepted_review(pipeline, flagship["run_id"])
    with storage.connect() as connection:
        row = connection.execute("SELECT memory_id, payload FROM memories").fetchone()
        payload = json.loads(row["payload"])
        payload["authority"] = "qualified_expert"
        connection.execute(
            "UPDATE memories SET payload=? WHERE memory_id=?",
            (json.dumps(payload), row["memory_id"]),
        )
    later = wait(storage, pipeline.create("DEMO-MOULD-002", knowledge_mode="current"))
    assert later["status"] == "failed"
    assert later["error"] == "MemoryApplicationError: memory_contract_integrity"
    assert later["accepted_state"]["final_playbook_accepted"] is False


def test_rehashed_memory_must_match_the_separately_persisted_review(runtime):
    storage, pipeline = runtime
    flagship = wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    accepted_review(pipeline, flagship["run_id"])
    with storage.connect() as connection:
        row = connection.execute("SELECT memory_id, payload FROM memories").fetchone()
        payload = json.loads(row["payload"])
        payload["reviewer_explanation"] = "rehashed but not review-bound"
        payload["content_hash"] = digest(
            {
                key: value
                for key, value in payload.items()
                if key not in {"content_hash", "memory_id", "claim_id", "updated_at"}
            }
        )
        connection.execute(
            "UPDATE memories SET payload=? WHERE memory_id=?",
            (json.dumps(payload), row["memory_id"]),
        )

    later = wait(
        storage,
        pipeline.create("DEMO-MOULD-002", knowledge_mode="current"),
    )
    assert later["status"] == "failed"
    assert later["error"] == "MemoryApplicationError: memory_origin_binding"
    assert later["accepted_state"]["final_playbook_accepted"] is False


@pytest.mark.parametrize("field", ["source_result_hash", "reviewed_result_hash"])
def test_rehashed_memory_result_hashes_are_origin_bound(runtime, field):
    storage, pipeline = runtime
    flagship = wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    accepted_review(pipeline, flagship["run_id"])
    with storage.connect() as connection:
        row = connection.execute("SELECT memory_id, payload FROM memories").fetchone()
        payload = json.loads(row["payload"])
        payload[field] = "0" * 64
        payload["content_hash"] = digest(
            {
                key: value
                for key, value in payload.items()
                if key not in {"content_hash", "memory_id", "claim_id", "updated_at"}
            }
        )
        connection.execute(
            "UPDATE memories SET payload=? WHERE memory_id=?",
            (json.dumps(payload), row["memory_id"]),
        )

    later = wait(
        storage,
        pipeline.create("DEMO-MOULD-002", knowledge_mode="current"),
    )
    assert later["status"] == "failed"
    assert later["error"] == "MemoryApplicationError: memory_origin_binding"


def test_learning_proof_rejects_memory_tampered_after_application(runtime):
    storage, pipeline = runtime
    baseline, _flagship = accepted_learning_freeze(storage, pipeline)
    later = wait(storage, pipeline.create("DEMO-MOULD-002", knowledge_mode="current"))
    with storage.connect() as connection:
        row = connection.execute("SELECT memory_id, payload FROM memories").fetchone()
        payload = json.loads(row["payload"])
        payload["reviewer_explanation"] = "tampered"
        connection.execute(
            "UPDATE memories SET payload=? WHERE memory_id=?",
            (json.dumps(payload), row["memory_id"]),
        )
    with pytest.raises(ValueError, match="memory_proof_origin_integrity"):
        pipeline.learning_proof(baseline["run_id"], later["run_id"])


def test_learning_proof_rejects_rebound_receipt_with_recomputed_hash(runtime):
    storage, pipeline = runtime
    baseline, _flagship = accepted_learning_freeze(storage, pipeline)
    later = wait(
        storage,
        pipeline.create("DEMO-MOULD-002", knowledge_mode="current"),
    )
    forged_result = deepcopy(later["result"])
    receipt = forged_result["memory_application"]
    receipt["target"] = {"run_id": "replayed", "claim_id": "OTHER"}
    receipt["application_hash"] = digest(
        {key: value for key, value in receipt.items() if key != "application_hash"}
    )
    storage.patch_run(later["run_id"], patch={"result": forged_result})

    with pytest.raises(
        ValueError,
        match="memory_proof_source_integrity",
    ):
        pipeline.learning_proof(baseline["run_id"], later["run_id"])


def test_learning_proof_binds_full_before_hashes_to_pre_transform_boundary(runtime):
    storage, pipeline = runtime
    baseline, _flagship = accepted_learning_freeze(storage, pipeline)
    later = wait(
        storage,
        pipeline.create("DEMO-MOULD-002", knowledge_mode="current"),
    )
    boundary = later["memory_application_boundary"]
    receipt = later["result"]["memory_application"]
    assert receipt["before"] == boundary["before"]
    assert boundary["boundary_hash"] == digest(
        {key: value for key, value in boundary.items() if key != "boundary_hash"}
    )

    forged_result = deepcopy(later["result"])
    forged_receipt = forged_result["memory_application"]
    forged_receipt["before"]["process_dto_hash"] = "1" * 64
    forged_receipt["before"]["checklist_dto_hash"] = "2" * 64
    forged_receipt["application_hash"] = digest(
        {
            key: value
            for key, value in forged_receipt.items()
            if key != "application_hash"
        }
    )
    storage.patch_run(later["run_id"], patch={"result": forged_result})

    with pytest.raises(ValueError, match="memory_proof_source_integrity"):
        pipeline.learning_proof(baseline["run_id"], later["run_id"])


def test_learning_proof_cross_binds_before_hashes_to_persisted_event(runtime):
    storage, pipeline = runtime
    baseline, _flagship = accepted_learning_freeze(storage, pipeline)
    later = wait(
        storage,
        pipeline.create("DEMO-MOULD-002", knowledge_mode="current"),
    )
    forged_result = deepcopy(later["result"])
    forged_receipt = forged_result["memory_application"]
    forged_receipt["before"]["process_dto_hash"] = "a" * 64
    forged_receipt["before"]["checklist_dto_hash"] = "b" * 64
    forged_receipt["application_hash"] = digest(
        {
            key: value
            for key, value in forged_receipt.items()
            if key != "application_hash"
        }
    )
    forged_boundary = deepcopy(later["memory_application_boundary"])
    forged_boundary["before"] = deepcopy(forged_receipt["before"])
    forged_boundary["boundary_hash"] = digest(
        {
            key: value
            for key, value in forged_boundary.items()
            if key != "boundary_hash"
        }
    )
    storage.patch_run(
        later["run_id"],
        patch={
            "result": forged_result,
            "memory_application_boundary": forged_boundary,
        },
    )

    with pytest.raises(ValueError, match="memory_proof_source_integrity"):
        pipeline.learning_proof(baseline["run_id"], later["run_id"])


def test_learning_proof_recomputes_canonical_hash_from_returned_facts(runtime):
    storage, pipeline = runtime
    baseline, _flagship = accepted_learning_freeze(storage, pipeline)
    later = wait(
        storage,
        pipeline.create("DEMO-MOULD-002", knowledge_mode="current"),
    )
    forged_result = deepcopy(later["result"])
    allegation = next(
        fact
        for fact in forged_result["facts"]
        if fact["semantic_role"] == "management_ventilation_allegation"
    )
    tenancy = next(
        fact
        for fact in forged_result["facts"]
        if fact["fact_id"] == "later_fact_tenancy"
    )
    allegation["semantic_role"] = None
    tenancy["semantic_role"] = "management_ventilation_allegation"
    forged_result["audit"]["canonical_state_hash"] = digest(
        forged_result["facts"]
    )
    storage.patch_run(later["run_id"], patch={"result": forged_result})

    with pytest.raises(
        ValueError,
        match="memory_proof_canonical_artifact_binding",
    ):
        pipeline.learning_proof(baseline["run_id"], later["run_id"])


def test_learning_proof_requires_matching_canonical_category(runtime):
    storage, pipeline = runtime
    baseline, _flagship = accepted_learning_freeze(storage, pipeline)
    later = wait(
        storage,
        pipeline.create("DEMO-MOULD-002", knowledge_mode="current"),
    )
    forged_result = deepcopy(baseline["result"])
    forged_understanding = deepcopy(baseline["understanding"])
    forged_result["category"] = "Forged unrelated category"
    forged_understanding["category"] = "Forged unrelated category"
    reranked = rank_precedents(
        current_claim_id=forged_result["claim_id"],
        understanding={
            "facts": forged_result["facts"],
            "category": forged_result["category"],
            "subcategory": forged_result["subcategory"],
        },
        process=forged_result["process"],
        checklist=forged_result["checklist"],
        memories=[],
        corpus=HISTORICAL_CASES,
    )
    forged_result["precedents"] = reranked["results"]
    forged_result["precedent_ranking"] = reranked["receipt"]
    verification = pipeline._verification_report(
        CLAIMS["DEMO-MOULD-002"],
        {**forged_understanding, "facts": forged_result["facts"]},
        forged_result["legal_research"],
        forged_result["process"],
        forged_result["checklist"],
        forged_result["precedents"],
        forged_result["precedent_ranking"],
        [],
    )
    forged_result["verification"] = verification
    storage.patch_run(
        baseline["run_id"],
        patch={"understanding": forged_understanding, "result": forged_result},
    )

    proof = pipeline.learning_proof(baseline["run_id"], later["run_id"])
    assert proof["ready"] is False
    same_state = next(
        check
        for check in proof["deterministic_checks"]
        if check["name"] == "Same canonical state"
    )
    assert same_state["status"] == "failed"


def test_learning_proof_replay_binds_operation_before_fragments(runtime):
    storage, pipeline = runtime
    baseline, _flagship = accepted_learning_freeze(storage, pipeline)
    later = wait(
        storage,
        pipeline.create("DEMO-MOULD-002", knowledge_mode="current"),
    )
    forged_result = deepcopy(later["result"])
    receipt = forged_result["memory_application"]
    receipt["evidence_operations"][0]["before_hash"] = "1" * 64
    receipt["evidence_operations"][1]["before_hash"] = "2" * 64
    receipt["application_hash"] = digest(
        {key: value for key, value in receipt.items() if key != "application_hash"}
    )
    storage.patch_run(later["run_id"], patch={"result": forged_result})

    with pytest.raises(ValueError, match="memory_proof_source_integrity"):
        pipeline.learning_proof(baseline["run_id"], later["run_id"])


def test_learning_proof_recomputes_candidate_governance_reports(runtime):
    storage, pipeline = runtime
    baseline, _flagship = accepted_learning_freeze(storage, pipeline)
    later = wait(
        storage,
        pipeline.create("DEMO-MOULD-002", knowledge_mode="current"),
    )
    with storage.connect() as connection:
        row = connection.execute(
            "SELECT candidate_id, payload FROM candidates"
        ).fetchone()
        payload = json.loads(row["payload"])
        payload["target_tests"] = {
            "status": "passed",
            "passed": 999,
            "failed": 0,
            "cases": [],
            "manifest_hash": "0" * 64,
        }
        payload["protected_regression"] = {
            "status": "passed",
            "passed": 999,
            "failed": 0,
            "cases": [],
            "manifest_hash": "1" * 64,
        }
        connection.execute(
            "UPDATE candidates SET payload=? WHERE candidate_id=?",
            (json.dumps(payload), row["candidate_id"]),
        )

    proof = pipeline.learning_proof(baseline["run_id"], later["run_id"])
    assert proof["ready"] is False
    assert next(
        check
        for check in proof["deterministic_checks"]
        if check["name"]
        == "Deterministic target and protected checks passed"
    )["status"] == "failed"


def test_learning_proof_binds_candidate_to_its_governed_origin(runtime):
    storage, pipeline = runtime
    baseline, _flagship = accepted_learning_freeze(storage, pipeline)
    later = wait(
        storage,
        pipeline.create("DEMO-MOULD-002", knowledge_mode="current"),
    )
    with storage.connect() as connection:
        row = connection.execute(
            "SELECT candidate_id, payload FROM candidates"
        ).fetchone()
        payload = json.loads(row["payload"])
        payload["shared_knowledge_changed"] = True
        connection.execute(
            "UPDATE candidates SET payload=? WHERE candidate_id=?",
            (json.dumps(payload), row["candidate_id"]),
        )

    proof = pipeline.learning_proof(baseline["run_id"], later["run_id"])
    assert proof["ready"] is False
    assert proof["shared_rule"]["shared_knowledge_changed"] is None
    assert next(
        check
        for check in proof["deterministic_checks"]
        if check["name"]
        == "Deterministic target and protected checks passed"
    )["status"] == "failed"


@pytest.mark.parametrize("run_kind", ["baseline", "later"])
def test_learning_proof_requires_both_bound_playbooks_to_remain_accepted(
    runtime, run_kind
):
    storage, pipeline = runtime
    baseline, _flagship = accepted_learning_freeze(storage, pipeline)
    later = wait(
        storage,
        pipeline.create("DEMO-MOULD-002", knowledge_mode="current"),
    )
    target = baseline if run_kind == "baseline" else later
    forged_result = deepcopy(target["result"])
    forged_result["verification"]["valid"] = False
    forged_result["audit"]["accepted"] = False
    storage.patch_run(target["run_id"], patch={"result": forged_result})

    proof = pipeline.learning_proof(baseline["run_id"], later["run_id"])
    assert proof["ready"] is False
    assert next(
        check
        for check in proof["deterministic_checks"]
        if check["name"] == "Same canonical state"
    )["status"] == "failed"


@pytest.mark.parametrize("target", ["law", "precedent"])
def test_learning_proof_revalidates_bound_playbook_content(runtime, target):
    storage, pipeline = runtime
    baseline, _flagship = accepted_learning_freeze(storage, pipeline)
    later = wait(
        storage,
        pipeline.create("DEMO-MOULD-002", knowledge_mode="current"),
    )
    forged_result = deepcopy(later["result"])
    if target == "law":
        forged_result["legal_research"]["sources"][0]["passage_text"] = (
            "FORGED LAW"
        )
    else:
        forged_result["precedents"][0]["why_useful"] = "FORGED PRECEDENT"
    storage.patch_run(later["run_id"], patch={"result": forged_result})

    with pytest.raises(
        ValueError, match="memory_proof_playbook_integrity"
    ):
        pipeline.learning_proof(baseline["run_id"], later["run_id"])


def test_learning_proof_replay_rejects_rehashed_semantic_tamper(runtime):
    storage, pipeline = runtime
    baseline, _flagship = accepted_learning_freeze(storage, pipeline)
    later = wait(
        storage,
        pipeline.create("DEMO-MOULD-002", knowledge_mode="current"),
    )
    forged_result = deepcopy(later["result"])
    forged_item = next(
        item
        for item in forged_result["checklist"]["items"]
        if item["item_id"] == "building_envelope"
    )
    forged_item["why"] = "Conclusive tenant fault; deny the claim."
    receipt = forged_result["memory_application"]
    receipt["after"] = {
        "process_dto_hash": digest(forged_result["process"]),
        "checklist_dto_hash": digest(forged_result["checklist"]),
        "process_semantic_hash": digest(
            semantic_process_dto(forged_result["process"])
        ),
        "checklist_semantic_hash": digest(
            semantic_checklist_dto(forged_result["checklist"])
        ),
    }
    receipt["evidence_operations"][0]["after_hash"] = digest(forged_item)
    receipt["application_hash"] = digest(
        {key: value for key, value in receipt.items() if key != "application_hash"}
    )
    storage.patch_run(later["run_id"], patch={"result": forged_result})

    with pytest.raises(
        ValueError, match="memory_proof_playbook_integrity"
    ):
        pipeline.learning_proof(baseline["run_id"], later["run_id"])


def test_memory_eligibility_and_transform_are_claim_and_fact_id_agnostic(runtime):
    storage, pipeline = runtime
    flagship = wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    accepted_review(pipeline, flagship["run_id"])
    memory = storage.memories()[0]
    guidance = memory["case_specific_guidance"]
    evaluation = _eligibility_evaluation(
        guidance,
        claim_id="UNSEEN-MOULD-999",
        category="Rental defect - mould and moisture",
        subcategory="Recurring moisture with disputed causation",
        decisions=deepcopy(guidance["eligibility"]["required_decisions"]),
        facts={
            "management_ventilation_allegation": {
                "fact_id": "novel_fact_management_allegation",
                "state": "known",
                "grounded_source_count": 1,
            }
        },
    )
    assert evaluation["eligible"] is True

    baseline = wait(
        storage,
        pipeline.create("DEMO-MOULD-002", knowledge_mode="baseline"),
    )
    process = semantic_process_dto(deepcopy(baseline["result"]["process"]))
    checklist = semantic_checklist_dto(deepcopy(baseline["result"]["checklist"]))
    replay_case_specific_memory_transform(
        process,
        checklist,
        ventilation_fact_id="novel_fact_management_allegation",
    )
    extension = next(
        node for node in process["nodes"] if node["node_id"] == "ventilation_dispute"
    )
    assert extension["fact_ids"] == ["novel_fact_management_allegation"]


def test_atomic_learning_bundle_rolls_back_on_candidate_failure(runtime):
    storage, pipeline = runtime
    run = wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    original = deepcopy(run["result"])
    with storage.connect() as connection:
        connection.execute(
            "CREATE TRIGGER fail_candidate_insert BEFORE INSERT ON candidates "
            "BEGIN SELECT RAISE(ABORT, 'injected candidate failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="injected candidate failure"):
        accepted_review(pipeline, run["run_id"])
    assert storage.memories() == []
    assert storage.candidates() == []
    assert storage.get_review_for_run(run["run_id"]) is None
    persisted = storage.get_run(run["run_id"])
    assert persisted["result"] == original
    assert not {"review", "consolidate"} & {value["stage"] for value in persisted["events"]}


def test_observable_package_excludes_hidden_generation_fields():
    package = observable_claim_package(CLAIMS["DEF-027-E0-DEMO"])

    def keys(value):
        if isinstance(value, dict):
            for key, child in value.items():
                yield key
                yield from keys(child)
        elif isinstance(value, list):
            for child in value:
                yield from keys(child)

    all_keys = set(keys(package))
    assert {"generated", "lineage", "fact_ids", "description", "document_type", "title"}.isdisjoint(all_keys)
    assert "claim_id" not in all_keys
    assert package["schema"] == "casepath.observable-claim-package/1.0.0"


@pytest.mark.parametrize("claim_id", ["DEF-027-E0-DEMO", "DEMO-MOULD-002"])
def test_observable_envelope_does_not_disclose_category_or_causation_shortcut(
    claim_id,
):
    package = observable_claim_package(CLAIMS[claim_id])
    envelope = " ".join(
        [
            package["customer_message"]["subject"],
            *(artifact["filename"] for artifact in package["artifacts"]),
        ]
    ).lower()
    assert all(
        marker not in envelope
        for marker in ("mould", "ventilation", "condensation", "tenant fault")
    )


def test_duplicate_review_is_idempotent_or_rejected(runtime):
    storage, pipeline = runtime
    run = wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    payload = {
        "decision": "approve_with_edit",
        "building_envelope_mode": "conditional",
        "confidence": 0.91,
        "justification": "Generated-demo edit only; qualified review has not occurred.",
    }
    first = pipeline.review(run["run_id"], payload)
    duplicate = pipeline.review(run["run_id"], payload)
    assert duplicate == first
    assert len(storage.memories()) == 1
    assert len(storage.candidates()) == 1
    assert len([value for value in storage.get_run(run["run_id"])["events"] if value["stage"] == "review"]) == 1
    with pytest.raises(ValueError, match="different review"):
        pipeline.review(run["run_id"], {**payload, "building_envelope_mode": "required_now"})


def test_second_flagship_review_versions_the_same_case_memory(runtime):
    storage, pipeline = runtime
    first_run = wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    first = accepted_review(pipeline, first_run["run_id"])
    second_run = wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    second = accepted_review(pipeline, second_run["run_id"])
    assert second["memory_id"] == first["memory_id"]
    assert len(storage.memories()) == 1
    assert storage.memories()[0]["source_run_id"] == second_run["run_id"]
    assert len(storage.candidates()) == 1
    assert [value["stage"] for value in storage.get_run(second_run["run_id"])["events"]][-2:] == ["review", "consolidate"]


def test_pipeline_events_disclose_deterministic_vs_model_identity(runtime):
    storage, pipeline = runtime
    run = wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    assert run["status"] == "complete"
    understand = next(
        value for value in run["events"]
        if value["stage"] == "understand" and value["status"] == "completed"
    )
    assert understand["implementation"] == "deterministic_reference_oracle"
    assert understand["model"] is None
    assert run["result"]["audit"]["canonicalization"]["mode"] == "deterministic_reference"


def test_model_mode_retains_process_owned_visual_locator_and_passes_grounding(tmp_path: Path):
    oracle_storage = Storage(str(tmp_path / "oracle.db"))
    oracle = ClaimPipeline(oracle_storage, pace_seconds=0)
    oracle_result = wait(oracle_storage, oracle.create("DEF-027-E0-DEMO"))["result"]
    oracle_facts = oracle_result["facts"]
    proposed_noncontrolling_id = next(
        value["fact_id"]
        for value in oracle_facts
        if value["controls_process"] is False
    )
    raw_facts = provider_fact_proposals(oracle_facts)

    def transport(_url, _headers, _payload, _timeout):
        return {
            "id": "mock-flagship-model-call",
            "model": OPENROUTER_MODEL,
            "provider": "Together",
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"facts": provider_wire_facts(raw_facts)})}}],
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 2500,
                "total_tokens": 3500,
                "cost": 0.01,
            },
        }

    model_storage = Storage(str(tmp_path / "model.db"))
    canonicalizer = OpenRouterNemotronCanonicalizer(
        model_storage,
        transport=transport,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    pipeline = ClaimPipeline(
        model_storage,
        model_mode=MODEL_MODE_OPENROUTER,
        canonicalizer=canonicalizer,
        agent_orchestrator=StubAgentOrchestrator(),
        pace_seconds=0,
    )
    run = wait(model_storage, pipeline.create("DEF-027-E0-DEMO"))
    assert run["status"] == "complete", run.get("error")
    visual_refs = [
        ref for value in run["result"]["facts"] for ref in value["source_refs"]
        if ref["locator_kind"] == "visual_observation"
    ]
    assert visual_refs
    assert {ref["producer"] for ref in visual_refs} == {
        "deterministic_reference_annotation"
    }
    assert {ref["authority"] for ref in visual_refs} == {
        "generated_demo_reference_only"
    }
    assert {
        ref["image_sha256"] for ref in visual_refs
    } == {ARTIFACTS["art_photo"]["sha256"]}
    noncontrolling_fact = next(
        value
        for value in run["result"]["facts"]
        if value["fact_id"] == proposed_noncontrolling_id
    )
    assert noncontrolling_fact["normalized_value"] is None
    assert noncontrolling_fact["decision_value"] is None
    assert run["result"]["process"]["current_node"] == oracle_result["process"]["current_node"]
    diagnostics = run["result"]["audit"]["canonicalization"]["diagnostics"]
    assert diagnostics["authority_mode"] == "hybrid_guarded"
    assert diagnostics["accepted_fact_ids"] == [value["fact_id"] for value in oracle_facts]
    assert diagnostics["accepted_fact_count"] == len(oracle_facts)
    assert diagnostics["rejected_facts"] == []
    assert diagnostics["rejected_fact_count"] == 0
    assert diagnostics["ignored_noncontrolling_normalized_proposals"] == 0
    assert "Model-assisted hybrid canonicalization" in run["result"]["summary"]
    assert "deterministic fallback replaced 0 rejected proposals" in run["result"]["summary"]
    assert run["result"]["verification"]["valid"] is True
    scope_node = next(
        item for item in run["result"]["process"]["nodes"] if item["node_id"] == "scope"
    )
    assert scope_node["agent_decision_contributions"][0]["confidence_basis_points"] == 8200
    assert scope_node["agent_decision_contributions"][0]["attribution"] == (
        "Process Decision Mapping Agent"
    )
    checklist_contributions = run["result"]["checklist"]["items"][0][
        "agent_contribution"
    ]
    assert {item["field"] for item in checklist_contributions} == {
        "status",
        "artifact_ids",
    }
    assert all(
        item["confidence_basis_points"] == 8300
        and item["attribution"] == "Evidence and Checklist Agent"
        for item in checklist_contributions
    )
    assert run["result"]["next_action"]["agent_brief_contribution"]["confidence_basis_points"] == 8400
    assert run["result"]["audit"]["canonicalization"]["mode"] == MODEL_MODE_OPENROUTER
    assert run["result"]["audit"]["canonicalization"]["authority_mode"] == "hybrid_guarded"
    gates = {
        item["agent_id"]: item
        for item in run["result"]["agent_orchestration"]["deterministic_gates"]
    }
    assert gates["deterministic_process_gate"]["output_artifact_hash"] == (
        accepted_artifact_hash(run["result"]["process"])
    )
    assert gates["deterministic_evidence_gate"]["output_artifact_hash"] == (
        accepted_artifact_hash(run["result"]["checklist"])
    )
    assert gates["whole_playbook_gate"]["output_artifact_hash"] == (
        accepted_artifact_hash(
            {
                "process": semantic_process_dto(run["result"]["process"]),
                "checklist": semantic_checklist_dto(run["result"]["checklist"]),
                "final_brief": run["result"]["agent_orchestration"]["final_claim_brief"],
            }
        )
    )
    assert gates["whole_playbook_gate"]["final_brief_artifact_hash"] == (
        accepted_artifact_hash(run["result"]["agent_orchestration"]["final_claim_brief"])
    )
    assert gates["whole_playbook_gate"]["verification_report_hash"] == digest(
        run["result"]["verification"]
    )
    assert gates["whole_playbook_gate"]["verification_whole_playbook_hash"] == (
        run["result"]["verification"]["whole_playbook_hash"]
    )
    whole_playbook_event = next(
        item
        for item in run["events"]
        if item.get("output_artifact") == "verified_claim_playbook"
    )
    assert whole_playbook_event["verification_whole_playbook_hash"] == (
        run["result"]["verification"]["whole_playbook_hash"]
    )
    assert run["precedents"] == run["result"]["precedents"]
    assert run["precedent_ranking"] == run["result"]["precedent_ranking"]
    for key in (
        "summary",
        "category",
        "subcategory",
        "scope",
        "dispute",
        "facts",
        "issues",
    ):
        assert run["understanding"][key] == run["result"][key]
    assert all(
        item["acceptance_scope"] == "pre_review_model_output"
        for item in run["result"]["agent_orchestration"]["agents"]
    )
    assert model_storage.model_calls()[0]["outcome"] == "succeeded"

    reviewed = accepted_review(pipeline, run["run_id"])["result"]
    assert "agent_contribution" not in reviewed["process"]
    assert all(
        "agent_decision_contributions" not in node
        for node in reviewed["process"]["nodes"]
    )
    assert "agent_contribution" not in reviewed["checklist"]
    assert all(
        "agent_contribution" not in item
        for item in reviewed["checklist"]["items"]
    )
    assert reviewed["next_action"]["agent_brief_contribution"] is None


def test_production_shaped_missing_grounding_fails_closed_without_projection(
    tmp_path: Path,
):
    oracle_storage = Storage(str(tmp_path / "oracle-projection.db"))
    oracle = ClaimPipeline(oracle_storage, pace_seconds=0)
    oracle_result = wait(oracle_storage, oracle.create("DEF-027-E0-DEMO"))["result"]
    proposals = provider_fact_proposals(oracle_result["facts"])
    text_grounded_fact_ids = {
        value["fact_id"]
        for value in oracle_result["facts"]
        if any(ref["locator_kind"] == "text_quote" for ref in value["source_refs"])
    }
    for proposal in proposals:
        if proposal["fact_id"] in text_grounded_fact_ids:
            proposal["source_ref_ids"] = []
    next(
        value for value in proposals if value["fact_id"] == "fact_date_conflict"
    )["confidence"] = 1.01

    def transport(_url, _headers, _payload, _timeout):
        return {
            "id": "mock-production-shaped-projection",
            "model": OPENROUTER_MODEL,
            "provider": "Together",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": json.dumps({"facts": provider_wire_facts(proposals)})},
                }
            ],
            "usage": {
                "prompt_tokens": 23141,
                "completion_tokens": 1931,
                "total_tokens": 25072,
                "cost": 0.0157931,
            },
        }

    model_storage = Storage(str(tmp_path / "model-projection.db"))
    pipeline = ClaimPipeline(
        model_storage,
        model_mode=MODEL_MODE_OPENROUTER,
        canonicalizer=OpenRouterNemotronCanonicalizer(
            model_storage,
            transport=transport,
            api_key_provider=lambda: "runtime-only-test-value",
        ),
        agent_orchestrator=StubAgentOrchestrator(),
        pace_seconds=0,
    )
    run = wait(model_storage, pipeline.create("DEF-027-E0-DEMO"))
    assert run["status"] == "failed"
    assert run["error"] == "ModelResponseError: provider_native_schema"
    assert "result" not in run
    ledger = model_storage.model_calls()[0]
    assert ledger["outcome"] == "failed"
    assert ledger["error_invariant"] == "provider_native_schema"
    assert "accepted_fact_count" not in ledger
    assert "rejected_facts" not in ledger
    assert model_storage.cached_model_output(ledger["cache_key"]) is None


def test_hybrid_rejected_controlling_fact_fails_without_oracle_fallback(tmp_path: Path):
    oracle_storage = Storage(str(tmp_path / "oracle.db"))
    oracle = ClaimPipeline(oracle_storage, pace_seconds=0)
    oracle_result = wait(oracle_storage, oracle.create("DEF-027-E0-DEMO"))["result"]
    proposals = provider_fact_proposals(oracle_result["facts"])
    rejected_proposal = next(value for value in proposals if value["fact_id"] == "fact_dispute")
    rejected_proposal["confidence"] = 1.01
    accepted_proposal = next(value for value in proposals if value["fact_id"] == "fact_tenancy")
    accepted_proposal["confidence"] = 0.41

    def transport(_url, _headers, _payload, _timeout):
        return {
            "id": "mock-hybrid-fallback-call",
            "model": OPENROUTER_MODEL,
            "provider": "Together",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": json.dumps({"facts": provider_wire_facts(proposals)})},
                }
            ],
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 2400,
                "total_tokens": 3400,
                "cost": 0.01,
            },
        }

    model_storage = Storage(str(tmp_path / "model.db"))
    pipeline = ClaimPipeline(
        model_storage,
        model_mode=MODEL_MODE_OPENROUTER,
        canonicalizer=OpenRouterNemotronCanonicalizer(
            model_storage,
            transport=transport,
            api_key_provider=lambda: "runtime-only-test-value",
        ),
        agent_orchestrator=StubAgentOrchestrator(),
        pace_seconds=0,
    )
    run = wait(model_storage, pipeline.create("DEF-027-E0-DEMO"))
    assert run["status"] == "failed"
    assert run["error"] == "ModelResponseError: hybrid_model_contribution"
    assert "result" not in run
    ledger = model_storage.model_calls()[0]
    assert ledger["outcome"] == "failed"
    assert ledger["authority_mode"] == "hybrid_guarded"
    assert ledger["accepted_fact_count"] == len(proposals) - 1
    assert ledger["rejected_facts"] == [
        {"fact_id": "fact_dispute", "invariant": "confidence_contract"}
    ]
    assert ledger["rejected_fact_count"] == 1
    assert ledger["deterministic_fallback_applied"] is False
    assert model_storage.cached_model_output(ledger["cache_key"]) is None


def test_late_specialist_failure_keeps_bounded_partial_truth_and_no_final_result(
    tmp_path: Path,
):
    oracle_storage = Storage(str(tmp_path / "oracle-late.db"))
    oracle_pipeline = ClaimPipeline(oracle_storage, pace_seconds=0)
    oracle_result = wait(
        oracle_storage, oracle_pipeline.create("DEF-027-E0-DEMO")
    )["result"]
    raw_facts = provider_fact_proposals(oracle_result["facts"])

    def transport(*_args):
        return {
            "id": "gen-late-failure",
            "model": OPENROUTER_MODEL,
            "provider": "Together",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": json.dumps({"facts": provider_wire_facts(raw_facts)})},
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 200,
                "total_tokens": 300,
                "cost": 0.002,
            },
        }

    class FailingOrchestrator:
        def invoke(self, **values):
            failure = AgentInvocationFailure(
                "evidence_checklist",
                "invalid_provenance",
                safe_context={
                    "call_id": "modelcall-failed-specialist",
                    "parent_call_id": "modelcall-plan",
                    "response_id": "gen-failed-specialist",
                    "response_model": OPENROUTER_MODEL,
                    "upstream_provider": "Together",
                    "usage_source": "response",
                    "finish_reason": "stop",
                    "outcome": "failed",
                    "invalid_provenance_field": "response_model",
                    "invalid_provenance_value_hash": "2" * 64,
                },
            )
            values["progress_sink"](
                    {
                        "receipt_type": "agent_failed",
                        "acceptance_scope": "pre_review_model_output",
                        "agent_id": "evidence_checklist",
                    "role": "Evidence and Checklist Agent",
                    "actor_type": "nemotron_agent",
                    "status": "failed",
                    "delegation_id": "dlg-failed",
                    "call_id": "modelcall-failed-specialist",
                    "parent_call_id": "modelcall-plan",
                    "response_id": "gen-failed-specialist",
                    "response_model": OPENROUTER_MODEL,
                    "upstream_provider": "Together",
                    "usage_source": "response",
                    "outcome": "failed",
                    "error_type": "AgentInvocationFailure",
                    "error_invariant": "invalid_provenance",
                    "invalid_provenance_field": "response_model",
                    "invalid_provenance_value_hash": "2" * 64,
                    "input_artifact_hash": "1" * 64,
                    "handoff_from": "deterministic_process_gate",
                    "handoff_to": "failure_boundary",
                }
            )
            raise failure

    storage = Storage(str(tmp_path / "late.db"))
    pipeline = ClaimPipeline(
        storage,
        model_mode=MODEL_MODE_OPENROUTER,
        canonicalizer=OpenRouterNemotronCanonicalizer(
            storage,
            transport=transport,
            api_key_provider=lambda: "runtime-only-test-value",
        ),
        agent_orchestrator=FailingOrchestrator(),
        pace_seconds=0,
    )
    run = wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    assert run["status"] == "failed"
    assert "result" not in run
    assert run["accepted_state"] == {
        "canonical_state_prepared": True,
        "process_candidate_prepared": True,
        "evidence_candidate_prepared": True,
        "final_playbook_accepted": False,
    }
    assert "process_candidate" in run and "checklist_candidate" in run
    failed_receipt = next(
        item
        for item in run["events"]
        if item.get("receipt_type") == "agent_failed"
        and item.get("agent_id") == "evidence_checklist"
    )
    assert failed_receipt["headline"] == "Bounded specialist call failed closed"
    assert failed_receipt["acceptance_scope"] == "pre_review_model_output"
    assert failed_receipt["call_id"] == "modelcall-failed-specialist"
    assert failed_receipt["error_invariant"] == "invalid_provenance"
    assert failed_receipt["invalid_provenance_field"] == "response_model"
    assert failed_receipt["invalid_provenance_value_hash"] == "2" * 64
    terminal = run["events"][-1]
    assert terminal["headline"] == "No final playbook was accepted"
    assert terminal["accepted_state"] == run["accepted_state"]
    assert "raw-provider-detail" not in json.dumps(run).lower()


def test_canonical_paid_failure_emits_joinable_safe_agent_receipt(tmp_path: Path):
    def transport(*_args):
        return {
            "id": "gen-canonical-wrong-model",
            "model": "different/model",
            "provider": "Together",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": json.dumps({"facts": []})},
                }
            ],
            "usage": {
                "prompt_tokens": 20,
                "completion_tokens": 10,
                "total_tokens": 30,
                "cost": 0.003,
            },
        }

    storage = Storage(str(tmp_path / "canonical-failure.db"))
    pipeline = ClaimPipeline(
        storage,
        model_mode=MODEL_MODE_OPENROUTER,
        canonicalizer=OpenRouterNemotronCanonicalizer(
            storage,
            transport=transport,
            api_key_provider=lambda: "runtime-only-test-value",
        ),
        agent_orchestrator=StubAgentOrchestrator(),
        pace_seconds=0,
    )
    run = wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    assert run["status"] == "failed"
    ledger = storage.model_calls()[0]
    receipt = next(
        item
        for item in run["events"]
        if item.get("receipt_type") == "agent_failed"
        and item.get("agent_id") == "canonical_facts"
    )
    assert receipt["call_id"] == ledger["call_id"]
    assert receipt["response_id"] == ledger["response_id"]
    assert receipt["response_model"] is None
    assert "response_model" not in ledger
    assert receipt["upstream_provider"] == ledger["upstream_provider"]
    assert receipt["usage_source"] == ledger["usage_source"] == "response"
    assert receipt["outcome"] == ledger["outcome"] == "failed"
    assert receipt["error_invariant"] == ledger["error_invariant"] == "invalid_provenance"
    assert receipt["invalid_provenance_field"] == ledger[
        "invalid_provenance_field"
    ] == "response_model"
    assert receipt["invalid_provenance_value_hash"] == ledger[
        "invalid_provenance_value_hash"
    ]
    assert len(receipt["invalid_provenance_value_hash"]) == 64
    assert receipt["failure_scope"] == "root_canonical_facts"
    assert receipt["root_agent"] is True
    assert receipt["input_artifact"] == "observable_claim_package"
    assert receipt["input_artifact_hash"] == digest(
        observable_claim_package(CLAIMS["DEF-027-E0-DEMO"])
    )
    assert receipt["orchestration_id"] == ledger["orchestration_id"]
    assert receipt["parent_call_id"] is None
    assert receipt["delegation_id"] is None
    assert receipt["provider"] == "openrouter"
    assert receipt["requested_model"] == OPENROUTER_MODEL
    assert receipt["call_count"] == 1
    assert receipt["handoff_from"] == "observable_claim_package"
    assert receipt["handoff_to"] == "failure_boundary"
    specialist_failures = [
        item
        for item in run["events"]
        if item.get("receipt_type") == "agent_failed"
        and item.get("failure_scope") != "root_canonical_facts"
    ]
    assert specialist_failures == []
    terminal = run["events"][-1]
    assert terminal.get("receipt_type") is None
    assert terminal["actor_type"] == "deterministic_gate"
    assert ledger["actual_cost_usd"] == pytest.approx(0.003)
    serialized = json.dumps(run)
    assert "different/model" not in run["error"]
    assert "different/model" not in serialized
    assert "different/model" not in json.dumps(ledger)
    for forbidden in (
        "raw_output",
        "provider_payload",
        "messages",
        "reasoning",
        "runtime-only-test-value",
    ):
        assert forbidden not in serialized


def test_canonical_upstream_rejection_receipt_exposes_only_bounded_status(
    tmp_path: Path,
):
    inference_calls = 0

    def rejected_invoker(*_args):
        nonlocal inference_calls
        inference_calls += 1
        raise ModelResponseError(
            "provider_upstream_rejection invariant failed",
            invariant="provider_upstream_rejection",
            safe_context={
                "response_id": "gen-1786483164-EEEEEEEEEEEEEEEEEEEE",
                "provider_error_code": 429,
                "provider_boundary": "openrouter",
                "expected_upstream_provider": "Together",
            },
        )

    storage = Storage(str(tmp_path / "canonical-upstream-rejection.db"))
    pipeline = ClaimPipeline(
        storage,
        model_mode=MODEL_MODE_OPENROUTER,
        canonicalizer=OpenRouterNemotronCanonicalizer(
            storage,
            structured_invoker=rejected_invoker,
            api_key_provider=lambda: "runtime-only-test-value",
        ),
        agent_orchestrator=StubAgentOrchestrator(),
        pace_seconds=0,
    )

    run = wait(storage, pipeline.create("DEF-027-E0-DEMO"))

    assert inference_calls == 1
    assert run["status"] == "failed"
    receipt = next(
        item
        for item in run["events"]
        if item.get("receipt_type") == "agent_failed"
        and item.get("agent_id") == "canonical_facts"
    )
    assert receipt["error_invariant"] == "provider_upstream_rejection"
    assert receipt["response_id"] == "gen-1786483164-EEEEEEEEEEEEEEEEEEEE"
    assert receipt["provider_error_code"] == 429
    assert receipt["provider_boundary"] == "openrouter"
    assert receipt["expected_upstream_provider"] == "Together"
    assert receipt["call_count"] == 1
    assert receipt["response_model"] is None
    assert receipt["upstream_provider"] is None
    assert receipt["usage_source"] is None
    ledger = storage.sanitized_model_ledger()[0]
    assert ledger["provider_error_code"] == 429
    assert ledger["provider_boundary"] == "openrouter"
    assert ledger["expected_upstream_provider"] == "Together"
    assert ledger["actual_cost_usd"] is None
    assert storage.model_call_summary()["actual_cost_complete"] is False
    serialized = json.dumps(run)
    assert "provider_error_code" in serialized
    assert "provider message" not in serialized.lower()


def test_canonical_root_blocked_receipt_has_explicit_safe_invariant(tmp_path: Path):
    storage = Storage(str(tmp_path / "canonical-blocked.db"))
    pipeline = ClaimPipeline(
        storage,
        model_mode=MODEL_MODE_OPENROUTER,
        canonicalizer=OpenRouterNemotronCanonicalizer(
            storage,
            transport=lambda *_args: (_ for _ in ()).throw(
                AssertionError("credential gate must prevent transport")
            ),
            api_key_provider=lambda: None,
        ),
        agent_orchestrator=StubAgentOrchestrator(),
        pace_seconds=0,
    )
    run = wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    receipt = next(
        item
        for item in run["events"]
        if item.get("failure_scope") == "root_canonical_facts"
    )
    assert receipt["error_invariant"] == "missing_credential"
    assert receipt["outcome"] == "blocked_missing_credential"
    assert receipt["call_count"] == 0
    assert receipt["response_id"] is None
    assert receipt["parent_call_id"] is None
    assert receipt["delegation_id"] is None
    assert run["failure_stage"] == "canonical_facts"
    assert run["error"].endswith(": missing_credential")


def test_canonical_provider_concurrency_block_is_truthful_zero_call_receipt(
    tmp_path: Path,
):
    def blocked_invoker(*_args):
        raise ModelResponseError(
            "provider_concurrency_timeout invariant failed",
            invariant="provider_concurrency_timeout",
            safe_context={
                "call_count": 0,
                "outcome": "blocked_provider_concurrency",
            },
        )

    storage = Storage(str(tmp_path / "canonical-provider-concurrency.db"))
    pipeline = ClaimPipeline(
        storage,
        model_mode=MODEL_MODE_OPENROUTER,
        canonicalizer=OpenRouterNemotronCanonicalizer(
            storage,
            structured_invoker=blocked_invoker,
            api_key_provider=lambda: "runtime-only-test-value",
        ),
        agent_orchestrator=StubAgentOrchestrator(),
        pace_seconds=0,
    )

    run = wait(storage, pipeline.create("DEF-027-E0-DEMO"))

    assert run["status"] == "failed"
    receipt = next(
        item
        for item in run["events"]
        if item.get("failure_scope") == "root_canonical_facts"
    )
    assert receipt["error_invariant"] == "provider_concurrency_timeout"
    assert receipt["outcome"] == "blocked_provider_concurrency"
    assert receipt["call_count"] == 0
    assert receipt["response_id"] is None
    ledger = storage.model_calls()[0]
    assert ledger["outcome"] == "blocked_provider_concurrency"
    assert ledger["call_count"] == 0
    assert ledger["actual_cost_usd"] is None
    assert storage.model_call_summary()["network_calls"] == 0
    assert storage.model_call_summary()["unknown_cost_call_count"] == 0
    assert storage.model_cost_committed_or_reserved() == 0
    assert run["failure_stage"] == "canonical_facts"
    assert run["error"].endswith(": provider_concurrency_timeout")


def test_flagship_fact_contract_fits_single_bounded_model_response(runtime):
    storage, pipeline = runtime
    run = wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    facts = run["result"]["facts"]
    compact = json.dumps({"facts": facts}, ensure_ascii=False, separators=(",", ":"))
    conservative_tokens = math.ceil(len(compact.encode("utf-8")) / 3)
    assert len(facts) == 18
    assert conservative_tokens < MAX_OUTPUT_TOKENS == 8192
