from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import os
import threading
import time
from datetime import datetime
from typing import Any, Callable, Literal, TypedDict

from .canonicalizer import (
    CANONICALIZER_VERSION,
    CanonicalizerError,
    MODEL_MODE_OPENROUTER,
    MODEL_MODE_REFERENCE,
    OPENROUTER_MODEL,
    OPENROUTER_PROVIDER,
    OpenRouterNemotronCanonicalizer,
    configured_model_mode,
)
from .data import ARTIFACTS, CLAIMS, HISTORICAL_CASES, observable_claim_package
from .evidence_relations import apply_evidence_relations, validate_evidence_item_order
from .fact_relations import SEMANTIC_FACT_ID_BY_CLAIM
from .law_registry import LAW_SOURCES, legal_context
from .live_events import (
    accepted_artifact_events,
    fact_events,
    legal_source_events,
    precedent_events,
)
from .multi_agent import (
    AGENT_RUNTIME_PROFILE,
    AgentBoundaryError,
    DeterministicStructuredAgent,
    MULTI_AGENT_AUTHORITY_MODE,
    MULTI_AGENT_IMPLEMENTATION,
    MULTI_AGENT_VERSION,
    NemotronMultiAgentOrchestrator,
    _evidence_candidate_artifact_ids,
    accepted_artifact_hash,
    apply_evidence_contribution,
    apply_process_contribution,
)
from .projections import (
    DECISION_OPTIONS,
    apply_evidence_projection,
    apply_process_projection,
    checklist_derived_sections,
    decision_projection,
)
from .precedent_ranking import rank_precedents
from .storage import Storage
from .record_projector import (
    project_record_driven_facts_v1,
)
from .playbook_template import MOULD_PLAYBOOK_TEMPLATE, PlaybookTemplate
from .playbook_materializer import (
    build_template_cycle_verification_v1,
    materialize_template_cycle_v1,
    validate_template_legal_context_v1,
)
from .validation import (
    ContractValidationError,
    LEARNING_SNAPSHOT_FIELDS,
    validate_playbook,
    validate_review_operations,
)
from .visual_annotations import visual_annotation_ref


RELEASE = "15.2.0"
ORCHESTRATOR = "casepath-langgraph-orchestrator/15.2"
PROFILE = "nemotron-langgraph-multi-agent-hybrid-guarded"
DETERMINISTIC_PROFILE = "deterministic-reference-playbook"
COMPONENT_VERSIONS = {
    "api": "15.2.0",
    "pipeline": "15.2.0",
    "contracts": "1.4.0",
    "canonicalizer": CANONICALIZER_VERSION,
    "agent_graph": MULTI_AGENT_VERSION,
    "storage": "1.4.0",
}

MEMORY_CONTRACT = "casepath.reviewed-case-memory/1.0.0"
MEMORY_GUIDANCE_CONTRACT = "casepath.case-specific-memory-guidance/1.0.0"
MEMORY_RECEIPT_CONTRACT = "casepath.memory-application-receipt/1.0.0"
MEMORY_BOUNDARY_CONTRACT = "casepath.memory-application-boundary/1.0.0"
MEMORY_ELIGIBILITY_CONTRACT = "casepath.semantic-memory-eligibility/1.0.0"
MEMORY_AUTHORITY = "unverified_demo"
SHARED_PLAYBOOK_VERSION = "mould-playbook-v3"
MEMORY_OPERATION_IDS = (
    "add_ventilation_dispute_node",
    "add_evidence_gap_to_ventilation_edge",
    "add_ventilation_to_causation_edge",
    "condition_building_envelope",
    "reassign_use_evidence_to_ventilation",
)
MEMORY_REQUIRED_DECISIONS = {
    "scope": "in_scope",
    "dispute": "dispute_present",
    "urgency": "not_urgent",
    "notification": "notified",
    "recurrence": "recurrence_supported",
    "causation": "cause_unresolved",
}
MEMORY_REQUIRED_FACT_ROLES = {
    "management_ventilation_allegation": {
        "state": "known",
        "min_grounded_sources": 1,
    }
}


def _timestamp_seconds(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("learning_timestamp_type")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError as exc:
            raise ValueError("learning_timestamp_value") from exc
    raise ValueError("learning_timestamp_type")


def _counterfactual_learning_freeze(
    memories: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not memories:
        return None
    if len(memories) != 1:
        raise ValueError("counterfactual_memory_count")
    memory = memories[0]
    identity = {
        "memory_id": memory.get("memory_id"),
        "review_id": memory.get("review_id"),
        "content_hash": memory.get("content_hash"),
        "candidate_id": memory.get("candidate_id"),
        "updated_at": memory.get("updated_at"),
    }
    if (
        any(not isinstance(identity[key], str) or not identity[key] for key in identity)
        or len(identity["content_hash"]) != 64
        or any(char not in "0123456789abcdef" for char in identity["content_hash"])
    ):
        raise ValueError("counterfactual_memory_identity")
    return {
        "contract": "casepath.counterfactual-learning-freeze/1.0.0",
        "memory": identity,
        "identity_hash": digest(identity),
        "application_suppressed": True,
    }


class ReviewOperation(TypedDict):
    component: Literal["process_graph", "evidence_model"]
    operation: Literal["add", "replace", "remove"]
    pointer: str
    old_value: Any
    new_value: Any
    reason: str


class MemoryApplicationError(ValueError):
    def __init__(self, invariant: str):
        self.invariant = invariant
        self.safe_context = {"error_invariant": invariant}
        super().__init__(invariant)


VISIBLE_STAGES = [
    ("read", "Read the submission", "Attachment Parsing Tool"),
    ("understand", "Build the claim state", "Canonical Claim Preparation Tool"),
    ("research", "Research Swiss tenant law", "Swiss Legal Source Tool"),
    ("process", "Discover the full handling process", "Process Projection Tool"),
    ("evidence", "Derive the complete evidence model", "Evidence Checklist Tool"),
    ("experience", "Retrieve organizational experience", "Historical Retrieval Tool"),
    ("verify", "Verify the complete playbook", "Whole-Playbook Verification Gate"),
]


def digest(value: Any) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def semantic_process_dto(process: dict[str, Any]) -> dict[str, Any]:
    """Remove run-specific model attribution while preserving process semantics."""

    value = deepcopy(process)
    value.pop("agent_contribution", None)
    for node in value.get("nodes", []):
        node.pop("agent_decision_contributions", None)
    return value


def semantic_checklist_dto(checklist: dict[str, Any]) -> dict[str, Any]:
    """Remove run-specific model attribution while preserving evidence semantics."""

    value = deepcopy(checklist)
    value.pop("agent_contribution", None)
    for item in value.get("items", []):
        item.pop("agent_contribution", None)
    return value


def strip_model_contribution_attribution(
    process: dict[str, Any], checklist: dict[str, Any]
) -> None:
    """Remove model field ownership after an unverified deterministic transform."""

    process.pop("agent_contribution", None)
    for node in process.get("nodes", []):
        node.pop("agent_decision_contributions", None)
    checklist.pop("agent_contribution", None)
    for item in checklist.get("items", []):
        item.pop("agent_contribution", None)


def _accepted_agent_lineage(value: dict[str, Any]) -> dict[str, Any]:
    """Keep accepted artifacts float-free while retaining an audit join key."""

    return {
        key: value[key]
        for key in (
            "agent_id",
            "call_id",
            "origin_call_id",
            "cache_hit",
            "call_count",
            "usage_source",
            "response_id",
            "input_artifact_hash",
            "output_artifact_hash",
            "delegation_id",
            "parent_call_id",
            "outcome",
            "accepted_ids",
            "accepted_count",
            "rejected_count",
            "deterministic_fallback_applied",
        )
        if key in value
    }


def fact(
    fact_id: str,
    label: str,
    value: str,
    state: str,
    explanation: str,
    source_refs: list[dict[str, Any]],
    confidence: float = 1.0,
    *,
    decision_key: str | None = None,
    normalized_value: str | None = None,
    semantic_role: str | None = None,
) -> dict[str, Any]:
    if (decision_key is None) != (normalized_value is None):
        raise ValueError("decision_key and normalized_value must be provided together")
    decision_value = None
    if decision_key is not None:
        try:
            decision_value = DECISION_OPTIONS[decision_key][normalized_value]
        except KeyError as exc:
            raise ValueError("unsupported normalized decision value") from exc
    return {
        "fact_id": fact_id,
        "label": label,
        "value": value,
        "state": state,
        "explanation": explanation,
        "source_refs": source_refs,
        "confidence": confidence,
        "controls_process": decision_key is not None,
        "decision_key": decision_key,
        "normalized_value": normalized_value,
        "decision_value": decision_value,
        "semantic_role": semantic_role,
    }


def text_ref(artifact_id: str, page: int, excerpt: str, agent: str) -> dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "locator_kind": "text_quote",
        "page": page,
        "excerpt": excerpt,
        "agent": agent,
    }


def visual_ref(
    artifact_id: str,
    region: list[float],
    observation: str,
) -> dict[str, Any]:
    return visual_annotation_ref(
        artifact_id=artifact_id,
        image_sha256=ARTIFACTS[artifact_id]["sha256"],
        region=region,
        observation=observation,
    )


def metadata_ref(
    artifact_id: str,
    field: str,
    value: str | int | float | bool,
    agent: str,
) -> dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "locator_kind": "metadata_field",
        "field": field,
        "value": value,
        "agent": agent,
    }


def process_node(
    node_id: str,
    title: str,
    question: str,
    state: str,
    *,
    answer: str = "",
    why: str = "",
    kind: str = "decision",
    main_spine: bool = True,
    fact_ids: list[str] | None = None,
    legal_source_ids: list[str] | None = None,
    evidence_requirement_ids: list[str] | None = None,
    branches: list[dict[str, Any]] | None = None,
    activation: str = "always",
) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "title": title,
        "question": question,
        "state": state,
        "answer": answer,
        "why": why,
        "kind": kind,
        "main_spine": main_spine,
        "fact_ids": fact_ids or [],
        "legal_source_ids": legal_source_ids or [],
        "evidence_requirement_ids": evidence_requirement_ids or [],
        "branches": branches or [],
        "activation": activation,
    }


def edge(
    source: str, target: str, condition: str, state: str = "available"
) -> dict[str, Any]:
    return {"source": source, "target": target, "condition": condition, "state": state}


def replay_case_specific_memory_transform(
    process: dict[str, Any],
    checklist: dict[str, Any],
    *,
    ventilation_fact_id: str,
) -> dict[str, Any]:
    """Apply the one allowed memory transform as a pure, replayable operation."""

    if any(
        node.get("node_id") == "ventilation_dispute"
        for node in process.get("nodes", [])
    ) or any(
        (value.get("source"), value.get("target"))
        in {
            ("evidence_gap", "ventilation_dispute"),
            ("ventilation_dispute", "causation"),
        }
        for value in process.get("edges", [])
    ):
        raise MemoryApplicationError("memory_extension_already_present")
    items = {value["item_id"]: value for value in checklist["items"]}
    if not {"building_envelope", "use_evidence"} <= set(items):
        raise MemoryApplicationError("memory_evidence_precondition")

    ventilation_node = process_node(
        "ventilation_dispute",
        "Test the ventilation allegation",
        "What exactly is alleged, and does competent evidence support it?",
        "inactive",
        answer="Preserve as disputed; test only if competent assessment leaves a plausible use-related branch",
        why="Unverified demo memory guidance keeps the allegation explicit without treating it as technical cause.",
        kind="action",
        main_spine=False,
        fact_ids=[ventilation_fact_id],
        legal_source_ids=["handling-causation", "handling-evidence-order"],
        evidence_requirement_ids=["management_position", "use_evidence"],
        activation="recurrence + ventilation allegation + cause unresolved",
    )
    first_edge = edge(
        "evidence_gap",
        "ventilation_dispute",
        "neutral inspection leaves a plausible use-related factor",
        "possible",
    )
    second_edge = edge(
        "ventilation_dispute",
        "causation",
        "allegation evidence assessed",
        "loop",
    )
    process["nodes"].append(ventilation_node)
    process["edges"].extend([first_edge, second_edge])
    removed_from: list[str] = []
    for node in process["nodes"]:
        if node["node_id"] == "ventilation_dispute":
            continue
        if "use_evidence" in node.get("evidence_requirement_ids", []):
            node["evidence_requirement_ids"] = [
                value
                for value in node["evidence_requirement_ids"]
                if value != "use_evidence"
            ]
            removed_from.append(node["node_id"])
    process["memory_used"] = True
    process["case_specific_guidance_applied"] = True
    process["shared_rule_applied"] = False

    building_before = deepcopy(items["building_envelope"])
    items["building_envelope"].update(
        {
            "status": "conditional",
            "required_level": "conditional",
            "applies_when": "The neutral first assessment is inconclusive or indicates an envelope issue",
            "why": "Unverified demo memory guidance keeps broader building-envelope testing conditional on the first competent assessment.",
        }
    )
    use_before = deepcopy(items["use_evidence"])
    items["use_evidence"].update(
        {
            "status": "conditional",
            "required_level": "conditional",
            "applies_when": "A competent assessment leaves a plausible use-related branch",
            "why": "Unverified demo memory guidance requests use-related evidence only if competent assessment leaves that branch plausible.",
        }
    )
    apply_evidence_relations(process, checklist["items"])
    apply_evidence_projection(checklist["items"], process)
    apply_evidence_relations(process, checklist["items"])
    checklist.update(checklist_derived_sections(checklist["items"]))
    checklist["memory_used"] = True
    checklist["case_specific_guidance_applied"] = True
    checklist["shared_rule_applied"] = False
    strip_model_contribution_attribution(process, checklist)
    return {
        "ventilation_node": ventilation_node,
        "first_edge": first_edge,
        "second_edge": second_edge,
        "removed_from": removed_from,
        "building_before": building_before,
        "use_before": use_before,
    }


def _memory_content_hash(memory: dict[str, Any]) -> str:
    excluded = {"content_hash", "memory_id", "claim_id", "updated_at"}
    return digest({key: value for key, value in memory.items() if key not in excluded})


def _fact_signature(understanding: dict[str, Any]) -> dict[str, Any]:
    roles: dict[str, Any] = {}
    for value in understanding["facts"]:
        role = value.get("semantic_role")
        if role is None:
            continue
        if role in roles:
            raise ValueError("duplicate_semantic_fact_role")
        roles[role] = {
            "fact_id": value["fact_id"],
            "state": value["state"],
            "grounded_source_count": len(value.get("source_refs", [])),
        }
    return roles


def _memory_semantic_signature(rule: dict[str, Any]) -> dict[str, Any]:
    return {
        "category": rule.get("category"),
        "subcategory": rule.get("subcategory"),
        "required_decisions": rule.get("required_decisions"),
        "required_fact_roles": rule.get("required_fact_roles"),
    }


def _eligibility_evaluation(
    guidance: dict[str, Any],
    *,
    claim_id: str,
    category: str,
    subcategory: str,
    decisions: dict[str, str],
    facts: dict[str, Any],
) -> dict[str, Any]:
    rule = guidance.get("eligibility", {})
    required_decisions = rule.get("required_decisions", {})
    required_fact_roles = rule.get("required_fact_roles", {})
    ventilation = facts.get("management_ventilation_allegation", {})
    ventilation_rule = required_fact_roles.get("management_ventilation_allegation", {})
    checks = {
        "source_claim_excluded": claim_id != rule.get("source_claim_id"),
        "category_matched": category == rule.get("category"),
        "subcategory_matched": subcategory == rule.get("subcategory"),
        "required_decisions_matched": all(
            decisions.get(key) == expected
            for key, expected in required_decisions.items()
        ),
        "ventilation_allegation_grounded": (
            ventilation.get("state") == ventilation_rule.get("state")
            and type(ventilation.get("grounded_source_count")) is int
            and ventilation.get("grounded_source_count", 0)
            >= ventilation_rule.get("min_grounded_sources", 0)
        ),
        "semantic_signature_bound": rule.get("semantic_signature_hash")
        == digest(_memory_semantic_signature(rule)),
        "guidance_enabled": guidance.get("enabled") is True,
    }
    manifest = {
        "rule_id": rule.get("rule_id"),
        "contract": rule.get("contract"),
        "claim_id": claim_id,
        "semantic_signature_hash": rule.get("semantic_signature_hash"),
        "decisions": decisions,
        "facts_hash": digest(facts),
        "checks": checks,
    }
    return {
        **manifest,
        "eligible": all(checks.values()),
        "manifest_hash": digest(manifest),
    }


def _guidance_eligibility(
    guidance: dict[str, Any],
    *,
    claim_id: str,
    understanding: dict[str, Any],
) -> dict[str, Any]:
    return _eligibility_evaluation(
        guidance,
        claim_id=claim_id,
        category=understanding["category"],
        subcategory=understanding["subcategory"],
        decisions={
            value["decision_key"]: value["decision_value"]
            for value in understanding["facts"]
            if value.get("controls_process") is True
        },
        facts=_fact_signature(understanding),
    )


def _protected_output_context_from_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "result": deepcopy(result),
    }


def _protected_output_context_from_origin(
    source_run: dict[str, Any],
    review: dict[str, Any],
) -> dict[str, Any]:
    snapshot = review.get("protected_output_snapshot")
    if (
        not isinstance(snapshot, dict)
        or digest(snapshot) != source_run.get("pre_review_result_hash")
        or digest(snapshot) != review.get("pre_review_result_hash")
        or snapshot.get("claim_id") != source_run.get("claim_id")
    ):
        raise ValueError("protected_output_snapshot_binding")
    return _protected_output_context_from_result(snapshot)


def _execute_protected_output_control(
    guidance: dict[str, Any],
    protected_output_context: dict[str, Any],
) -> dict[str, Any]:
    """Run the real eligibility gate and pure transform against a copied playbook.

    The protected source claim is expected to be ineligible.  Hashes are computed
    independently from the copied before and after DTOs; they are never mirrored
    by assignment.  The eligible branch deliberately uses the same replayable
    transform as production memory application so a regression cannot pass by
    relabelling an eligibility result as an output test.
    """

    source_result = protected_output_context.get("result")
    if not isinstance(source_result, dict):
        raise ValueError("protected_output_result_missing")
    before_result = deepcopy(source_result)
    after_result = deepcopy(source_result)
    facts = before_result.get("facts")
    process = after_result.get("process")
    checklist = after_result.get("checklist")
    if (
        not isinstance(facts, list)
        or not isinstance(process, dict)
        or not isinstance(checklist, dict)
    ):
        raise ValueError("protected_output_result_contract")
    semantic_facts = _fact_signature({"facts": facts})
    evaluation = _eligibility_evaluation(
        guidance,
        claim_id=before_result["claim_id"],
        category=before_result["category"],
        subcategory=before_result["subcategory"],
        decisions={
            value["decision_key"]: value["decision_value"]
            for value in facts
            if value.get("controls_process") is True
        },
        facts=semantic_facts,
    )
    applied = evaluation["eligible"] is True
    if applied:
        ventilation = semantic_facts.get("management_ventilation_allegation", {})
        ventilation_fact_id = ventilation.get("fact_id")
        if not isinstance(ventilation_fact_id, str):
            raise ValueError("protected_output_semantic_fact_missing")
        replay_case_specific_memory_transform(
            process,
            checklist,
            ventilation_fact_id=ventilation_fact_id,
        )
        after_result["memory_used"] = True
        after_result["reviewed_memory_used"] = True
        after_result["memory_application"] = {
            "applied": True,
            "scope": "protected_output_control_only",
        }
    before_hashes = {
        "result_hash": digest(before_result),
        "process_hash": digest(before_result["process"]),
        "checklist_hash": digest(before_result["checklist"]),
    }
    after_hashes = {
        "result_hash": digest(after_result),
        "process_hash": digest(after_result["process"]),
        "checklist_hash": digest(after_result["checklist"]),
    }
    return {
        "evaluation": evaluation,
        "actual_memory_application": applied,
        "before_hashes": before_hashes,
        "after_hashes": after_hashes,
        "output_unchanged": before_result == after_result
        and before_hashes == after_hashes,
    }


def _governance_test_report(
    guidance: dict[str, Any],
    *,
    protected_output_context: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    target = {
        "claim_id": "UNSEEN-MOULD-999",
        "category": "Rental defect - mould and moisture",
        "subcategory": "Recurring moisture with disputed causation",
        "decisions": {
            "scope": "in_scope",
            "dispute": "dispute_present",
            "urgency": "not_urgent",
            "notification": "notified",
            "recurrence": "recurrence_supported",
            "causation": "cause_unresolved",
        },
        "facts": {
            "management_ventilation_allegation": {
                "fact_id": "novel_fact_management_allegation",
                "state": "known",
                "grounded_source_count": 1,
            }
        },
    }
    protected = [
        ("source_claim_self_match", {}, {}, {"claim_id": "DEF-027-E0-DEMO"}),
        (
            "category_only",
            {},
            {
                "management_ventilation_allegation": {
                    "fact_id": "x",
                    "state": "unknown",
                    "grounded_source_count": 0,
                }
            },
            {},
        ),
        ("out_of_scope", {"scope": "out_of_scope"}, {}, {}),
        ("no_dispute", {"dispute": "no_dispute"}, {}, {}),
        ("urgent", {"urgency": "urgent"}, {}, {}),
        ("unnotified", {"notification": "not_notified"}, {}, {}),
        ("no_recurrence", {"recurrence": "recurrence_not_supported"}, {}, {}),
        ("resolved_cause", {"causation": "cause_building"}, {}, {}),
        (
            "missing_ventilation_allegation",
            {},
            {
                "management_ventilation_allegation": {
                    "fact_id": "novel_fact_management_allegation",
                    "state": "unknown",
                    "grounded_source_count": 0,
                }
            },
            {},
        ),
    ]

    def execute(
        case_id: str,
        fixture: dict[str, Any],
        *,
        expected: bool,
    ) -> dict[str, Any]:
        evaluation = _eligibility_evaluation(
            guidance,
            claim_id=fixture["claim_id"],
            category=fixture["category"],
            subcategory=fixture["subcategory"],
            decisions=fixture["decisions"],
            facts=fixture["facts"],
        )
        actual = evaluation["eligible"]
        return {
            "case_id": case_id,
            "expected_eligible": expected,
            "actual_eligible": actual,
            "operation_count": len(guidance["allowed_operation_ids"]) if actual else 0,
            "status": "passed" if actual is expected else "failed",
            "manifest_hash": evaluation["manifest_hash"],
        }

    target_cases = [execute("eligible_later_claim", target, expected=True)]
    protected_cases: list[dict[str, Any]] = []
    for case_id, decision_patch, fact_patch, fixture_patch in protected:
        fixture = deepcopy(target)
        fixture["decisions"].update(decision_patch)
        fixture["facts"].update(fact_patch)
        fixture.update(fixture_patch)
        protected_cases.append(execute(case_id, fixture, expected=False))

    output_control = _execute_protected_output_control(
        guidance,
        protected_output_context,
    )
    output_evaluation = output_control["evaluation"]
    output_unchanged = (
        output_control["actual_memory_application"] is False
        and output_control["output_unchanged"] is True
    )
    protected_cases.append(
        {
            "case_id": "source_claim_full_playbook_unchanged",
            "execution_contract": "deterministic_case_specific_memory_gate/1.0.0",
            "gate_executed": True,
            "expected_memory_application": False,
            "actual_memory_application": output_control["actual_memory_application"],
            "before_hashes": output_control["before_hashes"],
            "after_hashes": output_control["after_hashes"],
            "output_unchanged": output_unchanged,
            "eligibility_manifest_hash": output_evaluation["manifest_hash"],
            "status": "passed" if output_unchanged else "failed",
        }
    )

    def report(cases: list[dict[str, Any]]) -> dict[str, Any]:
        passed = sum(value["status"] == "passed" for value in cases)
        value = {
            "status": "passed" if passed == len(cases) else "failed",
            "evaluator": "deterministic_case_specific_eligibility_and_output/2.0.0",
            "passed": passed,
            "failed": len(cases) - passed,
            "cases": cases,
        }
        value["manifest_hash"] = digest(value)
        return value

    return report(target_cases), report(protected_cases)


def _validate_memory(memory: dict[str, Any]) -> None:
    exact = {
        "title",
        "memory_contract",
        "authority",
        "scope",
        "review_status",
        "reviewer",
        "source_run_id",
        "review_id",
        "candidate_id",
        "category",
        "current_blocker",
        "canonical_facts",
        "reviewed_process",
        "reviewed_checklist",
        "final_process",
        "final_checklist",
        "verification",
        "operations",
        "next_action",
        "reviewer_explanation",
        "confidence",
        "playbook_version",
        "source_result_hash",
        "reviewed_result_hash",
        "shared_rule_authority",
        "case_specific_guidance",
        "content_hash",
        "memory_id",
        "claim_id",
        "updated_at",
    }
    if set(memory) != exact:
        raise ValueError("memory_contract_fields")
    if (
        memory.get("memory_contract") != MEMORY_CONTRACT
        or memory.get("authority") != MEMORY_AUTHORITY
        or memory.get("scope") != "case_specific_guidance_only"
        or memory.get("review_status") != "unverified_demo_memory"
        or memory.get("shared_rule_authority") is not False
        or memory.get("playbook_version") != SHARED_PLAYBOOK_VERSION
        or memory.get("content_hash") != _memory_content_hash(memory)
    ):
        raise ValueError("memory_contract_integrity")
    guidance = memory.get("case_specific_guidance")
    if not isinstance(guidance, dict) or set(guidance) != {
        "contract",
        "variant",
        "enabled",
        "authority",
        "scope",
        "eligibility",
        "allowed_operation_ids",
    }:
        raise ValueError("memory_guidance_contract")
    if (
        guidance.get("contract") != MEMORY_GUIDANCE_CONTRACT
        or guidance.get("authority") != MEMORY_AUTHORITY
        or guidance.get("scope") != "case_specific_guidance_only"
    ):
        raise ValueError("memory_guidance_authority")
    eligibility = guidance.get("eligibility")
    if (
        not isinstance(eligibility, dict)
        or set(eligibility)
        != {
            "contract",
            "rule_id",
            "source_claim_id",
            "category",
            "subcategory",
            "required_decisions",
            "required_fact_roles",
            "semantic_signature_hash",
        }
        or eligibility.get("contract") != MEMORY_ELIGIBILITY_CONTRACT
        or eligibility.get("source_claim_id") != memory["claim_id"]
        or eligibility.get("category") != memory["category"]
        or eligibility.get("required_decisions") != MEMORY_REQUIRED_DECISIONS
        or eligibility.get("required_fact_roles") != MEMORY_REQUIRED_FACT_ROLES
        or eligibility.get("semantic_signature_hash")
        != digest(_memory_semantic_signature(eligibility))
    ):
        raise ValueError("memory_guidance_eligibility")
    operation_ids = guidance.get("allowed_operation_ids")
    expected = list(MEMORY_OPERATION_IDS) if guidance.get("enabled") else []
    if operation_ids != expected:
        raise ValueError("memory_guidance_operations")


def _review_guidance_contract(
    *,
    claim_id: str,
    category: str,
    subcategory: str,
    building_envelope_mode: str,
) -> dict[str, Any]:
    """Derive reusable authority from the accepted review mode, never storage labels."""

    if building_envelope_mode not in {"conditional", "required_now"}:
        raise ValueError("memory_guidance_review_mode")
    enabled = building_envelope_mode == "conditional"
    guidance = {
        "contract": MEMORY_GUIDANCE_CONTRACT,
        "variant": (
            "disputed_ventilation_neutral_first_v1"
            if enabled
            else "no_reusable_guidance_required_now_v1"
        ),
        "enabled": enabled,
        "authority": MEMORY_AUTHORITY,
        "scope": "case_specific_guidance_only",
        "eligibility": {
            "contract": MEMORY_ELIGIBILITY_CONTRACT,
            "rule_id": "same_grounded_mould_signature_v2",
            "source_claim_id": claim_id,
            "category": category,
            "subcategory": subcategory,
            "required_decisions": deepcopy(MEMORY_REQUIRED_DECISIONS),
            "required_fact_roles": deepcopy(MEMORY_REQUIRED_FACT_ROLES),
        },
        "allowed_operation_ids": list(MEMORY_OPERATION_IDS) if enabled else [],
    }
    guidance["eligibility"]["semantic_signature_hash"] = digest(
        _memory_semantic_signature(guidance["eligibility"])
    )
    return guidance


def _validate_memory_origin(
    memory: dict[str, Any],
    *,
    source_run: dict[str, Any] | None,
    review: dict[str, Any] | None,
) -> None:
    """Bind a reusable memory to the separately persisted accepted review."""

    _validate_memory(memory)
    if not isinstance(source_run, dict) or not isinstance(review, dict):
        raise ValueError("memory_origin_missing")
    response = review.get("response")
    reviewed_result = response.get("result") if isinstance(response, dict) else None
    review_record = response.get("review") if isinstance(response, dict) else None
    candidate = response.get("candidate") if isinstance(response, dict) else None
    request = review.get("request")
    reviewer = review.get("reviewer")
    expected_guidance = (
        _review_guidance_contract(
            claim_id=memory["claim_id"],
            category=reviewed_result.get("category", ""),
            subcategory=reviewed_result.get("subcategory", ""),
            building_envelope_mode=request.get("building_envelope_mode", ""),
        )
        if isinstance(reviewed_result, dict) and isinstance(request, dict)
        else None
    )
    if (
        review.get("accepted") is not True
        or review.get("review_id") != memory["review_id"]
        or review.get("run_id") != memory["source_run_id"]
        or review.get("claim_id") != memory["claim_id"]
        or not isinstance(response, dict)
        or response.get("accepted") is not True
        or response.get("review_id") != memory["review_id"]
        or response.get("memory_id") != memory["memory_id"]
        or not isinstance(reviewed_result, dict)
        or not isinstance(review_record, dict)
        or not isinstance(candidate, dict)
        or not isinstance(request, dict)
        or source_run.get("run_id") != memory["source_run_id"]
        or source_run.get("claim_id") != memory["claim_id"]
        or source_run.get("review_id") != memory["review_id"]
        or source_run.get("memory_id") != memory["memory_id"]
        or source_run.get("result") != reviewed_result
        or source_run.get("review_response") != response
        or source_run.get("candidate") != candidate
        or candidate.get("candidate_id") != memory["candidate_id"]
        or memory.get("reviewer") != reviewer
        or memory.get("reviewer_explanation") != request.get("justification")
        or memory.get("confidence") != request.get("confidence")
        or memory.get("canonical_facts") != reviewed_result.get("facts")
        or memory.get("category") != reviewed_result.get("category")
        or memory.get("current_blocker") != reviewed_result.get("current_blocker")
        or memory.get("reviewed_process") != reviewed_result.get("process")
        or memory.get("reviewed_checklist") != reviewed_result.get("checklist")
        or memory.get("verification") != reviewed_result.get("verification")
        or memory.get("verification") != response.get("verification")
        or memory.get("operations") != review_record.get("operations")
        or memory.get("next_action") != reviewed_result.get("next_action")
        or memory.get("final_process")
        != [
            node["title"]
            for node in reviewed_result.get("process", {}).get("nodes", [])
        ]
        or memory.get("final_checklist")
        != [
            {
                "title": evidence["title"],
                "status": evidence["status"],
                "why": evidence["why"],
                "node_id": evidence["node_id"],
            }
            for evidence in reviewed_result.get("checklist", {}).get("items", [])
        ]
        or memory.get("source_result_hash") != review.get("pre_review_result_hash")
        or memory.get("source_result_hash") != source_run.get("pre_review_result_hash")
        or not isinstance(review.get("protected_output_snapshot"), dict)
        or digest(review["protected_output_snapshot"])
        != memory.get("source_result_hash")
        or memory.get("reviewed_result_hash") != digest(reviewed_result)
        or memory.get("case_specific_guidance") != expected_guidance
    ):
        raise ValueError("memory_origin_binding")


def _validate_candidate_origin(
    candidate: dict[str, Any],
    *,
    memory: dict[str, Any],
    source_run: dict[str, Any],
    review: dict[str, Any],
) -> None:
    response = review.get("response", {})
    expected_target, expected_protected = _governance_test_report(
        memory["case_specific_guidance"],
        protected_output_context=_protected_output_context_from_origin(
            source_run,
            review,
        ),
    )
    if (
        candidate.get("candidate_id") != memory.get("candidate_id")
        or source_run.get("candidate") != candidate
        or response.get("candidate") != candidate
        or candidate.get("status") != "quarantined"
        or candidate.get("target_tests") != expected_target
        or candidate.get("protected_regression") != expected_protected
        or candidate.get("qualified_support_count") != 0
        or candidate.get("support_authority") != "unverified_demo_only"
        or candidate.get("approval")
        != {"status": "pending", "qualified_reviewer": False}
        or candidate.get("shared_knowledge_changed") is not False
        or candidate.get("base_version") != SHARED_PLAYBOOK_VERSION
        or candidate.get("rollback_target") != SHARED_PLAYBOOK_VERSION
    ):
        raise ValueError("candidate_origin_binding")


def _validate_memory_receipt(
    receipt: dict[str, Any],
    *,
    memory: dict[str, Any],
    expected_context: dict[str, Any] | None = None,
) -> None:
    if set(receipt) != {
        "receipt_type",
        "contract",
        "authority",
        "scope",
        "source_memory",
        "target",
        "observable_input_hash",
        "canonical_state_hash",
        "eligibility",
        "allowed_operation_ids",
        "applied_operation_ids",
        "process_operations",
        "evidence_operations",
        "before",
        "after",
        "verification_hash",
        "shared_playbook_version",
        "shared_rule_applied",
        "model_acceptance_reused",
        "applied",
        "application_hash",
    }:
        raise ValueError("memory_receipt_fields")
    _validate_memory(memory)
    source = receipt.get("source_memory", {})
    if (
        receipt.get("receipt_type") != "memory_application_receipt"
        or receipt.get("contract") != MEMORY_RECEIPT_CONTRACT
        or receipt.get("authority") != MEMORY_AUTHORITY
        or receipt.get("scope") != "case_specific_guidance_only"
        or source.get("memory_id") != memory["memory_id"]
        or source.get("claim_id") != memory["claim_id"]
        or source.get("review_id") != memory["review_id"]
        or source.get("content_hash") != memory["content_hash"]
        or source.get("review_status") != "unverified_demo_memory"
        or receipt.get("allowed_operation_ids") != list(MEMORY_OPERATION_IDS)
        or receipt.get("applied_operation_ids") != list(MEMORY_OPERATION_IDS)
        or receipt.get("shared_playbook_version") != SHARED_PLAYBOOK_VERSION
        or receipt.get("shared_rule_applied") is not False
        or receipt.get("model_acceptance_reused") is not False
        or receipt.get("applied") is not True
        or receipt.get("eligibility", {}).get("eligible") is not True
    ):
        raise ValueError("memory_receipt_integrity")
    expected_boundary_hashes = {
        "process_dto_hash",
        "checklist_dto_hash",
        "process_semantic_hash",
        "checklist_semantic_hash",
    }
    if (
        set(receipt.get("before", {})) != expected_boundary_hashes
        or set(receipt.get("after", {})) != expected_boundary_hashes
    ):
        raise ValueError("memory_receipt_boundary_fields")
    process_operations = receipt.get("process_operations")
    evidence_operations = receipt.get("evidence_operations")
    if (
        not isinstance(process_operations, list)
        or not isinstance(evidence_operations, list)
        or [value.get("operation_id") for value in process_operations]
        != list(MEMORY_OPERATION_IDS[:3])
        or [value.get("operation_id") for value in evidence_operations]
        != list(MEMORY_OPERATION_IDS[3:])
    ):
        raise ValueError("memory_receipt_operations")
    if (
        set(process_operations[0])
        != {
            "operation_id",
            "operation",
            "node_id",
            "evidence_requirement_ids",
            "after_hash",
        }
        or process_operations[0].get("operation") != "add_node"
        or process_operations[0].get("node_id") != "ventilation_dispute"
        or process_operations[0].get("evidence_requirement_ids")
        != ["management_position", "use_evidence"]
        or any(
            set(value)
            != {
                "operation_id",
                "operation",
                "source",
                "target",
                "after_hash",
            }
            or value.get("operation") != "add_edge"
            for value in process_operations[1:]
        )
        or set(evidence_operations[0])
        != {
            "operation_id",
            "operation",
            "item_id",
            "before_hash",
            "after_hash",
        }
        or evidence_operations[0].get("operation") != "replace_item"
        or evidence_operations[0].get("item_id") != "building_envelope"
        or set(evidence_operations[1])
        != {
            "operation_id",
            "operation",
            "item_id",
            "removed_from_node_ids",
            "added_to_node_id",
            "before_hash",
            "after_hash",
        }
        or evidence_operations[1].get("operation") != "reassign_item"
        or evidence_operations[1].get("item_id") != "use_evidence"
        or evidence_operations[1].get("added_to_node_id") != "ventilation_dispute"
    ):
        raise ValueError("memory_receipt_operation_fields")
    hashes = [
        receipt.get("observable_input_hash"),
        receipt.get("canonical_state_hash"),
        receipt.get("verification_hash"),
        source.get("content_hash"),
        receipt.get("before", {}).get("process_dto_hash"),
        receipt.get("before", {}).get("checklist_dto_hash"),
        receipt.get("after", {}).get("process_dto_hash"),
        receipt.get("after", {}).get("checklist_dto_hash"),
        receipt.get("before", {}).get("process_semantic_hash"),
        receipt.get("before", {}).get("checklist_semantic_hash"),
        receipt.get("after", {}).get("process_semantic_hash"),
        receipt.get("after", {}).get("checklist_semantic_hash"),
        *[
            operation.get(field)
            for operation in [*process_operations, *evidence_operations]
            for field in ("before_hash", "after_hash")
            if field in operation
        ],
    ]
    if not all(
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
        for value in hashes
    ):
        raise ValueError("memory_receipt_hashes")
    if (
        receipt["before"]["process_dto_hash"] == receipt["after"]["process_dto_hash"]
        or receipt["before"]["checklist_dto_hash"]
        == receipt["after"]["checklist_dto_hash"]
        or receipt["before"]["process_semantic_hash"]
        == receipt["after"]["process_semantic_hash"]
        or receipt["before"]["checklist_semantic_hash"]
        == receipt["after"]["checklist_semantic_hash"]
    ):
        raise ValueError("memory_receipt_zero_delta")
    expected_application_hash = digest(
        {key: value for key, value in receipt.items() if key != "application_hash"}
    )
    if receipt.get("application_hash") != expected_application_hash:
        raise ValueError("memory_receipt_application_hash")
    if expected_context is not None:
        allowed_context_fields = {
            "target",
            "observable_input_hash",
            "canonical_state_hash",
            "eligibility",
            "before",
            "after",
            "verification_hash",
        }
        if set(expected_context) - allowed_context_fields:
            raise ValueError("memory_receipt_context_fields")
        if any(receipt.get(key) != value for key, value in expected_context.items()):
            raise ValueError("memory_receipt_context_binding")


def _memory_application_boundary(
    *,
    run_id: str,
    claim_id: str,
    memory: dict[str, Any],
    before: dict[str, Any],
) -> dict[str, Any]:
    """Retain an independent hash boundary for the exact pre-transform DTOs."""

    boundary = {
        "contract": MEMORY_BOUNDARY_CONTRACT,
        "target": {"run_id": run_id, "claim_id": claim_id},
        "source_memory": {
            "memory_id": memory["memory_id"],
            "content_hash": memory["content_hash"],
        },
        "before": deepcopy(before),
    }
    boundary["boundary_hash"] = digest(boundary)
    return boundary


def _validate_memory_application_boundary(
    boundary: dict[str, Any],
    *,
    run_id: str,
    claim_id: str,
    memory: dict[str, Any],
) -> None:
    if set(boundary) != {
        "contract",
        "target",
        "source_memory",
        "before",
        "boundary_hash",
    }:
        raise ValueError("memory_boundary_fields")
    before = boundary.get("before", {})
    if (
        boundary.get("contract") != MEMORY_BOUNDARY_CONTRACT
        or boundary.get("target") != {"run_id": run_id, "claim_id": claim_id}
        or boundary.get("source_memory")
        != {
            "memory_id": memory["memory_id"],
            "content_hash": memory["content_hash"],
        }
        or set(before)
        != {
            "process_dto_hash",
            "checklist_dto_hash",
            "process_semantic_hash",
            "checklist_semantic_hash",
        }
        or any(
            not isinstance(value, str)
            or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)
            for value in before.values()
        )
        or boundary.get("boundary_hash")
        != digest(
            {key: value for key, value in boundary.items() if key != "boundary_hash"}
        )
    ):
        raise ValueError("memory_boundary_integrity")


def _validate_memory_application_event(
    run: dict[str, Any], receipt: dict[str, Any]
) -> None:
    """Cross-bind the mutable result to the separately persisted event row."""

    events = [
        value
        for value in run.get("events", [])
        if value.get("stage") == "memory_application"
        and value.get("receipt_type") == "memory_application_receipt"
        and value.get("status") == "completed"
    ]
    if len(events) != 1:
        raise ValueError("memory_event_count")
    event = events[0]
    if any(key not in event for key in receipt):
        raise ValueError("memory_event_fields")
    event_receipt = {key: deepcopy(event[key]) for key in receipt}
    if event_receipt != receipt:
        raise ValueError("memory_event_receipt_binding")


class ClaimPipeline:
    """Reference implementation of the full CasePath lifecycle.

    Specialist agents share one claim-level orchestrator context. The public profile is
    intentionally deterministic and typed; the audit record names this explicitly. The
    same canonical artifacts can later be produced by a live model profile.
    """

    def __init__(
        self,
        storage: Storage,
        *,
        model_mode: str | None = None,
        canonicalizer: OpenRouterNemotronCanonicalizer | None = None,
        agent_orchestrator: NemotronMultiAgentOrchestrator | None = None,
        playbook_template: PlaybookTemplate = MOULD_PLAYBOOK_TEMPLATE,
        pace_seconds: float = 1.0,
    ):
        self.storage = storage
        self.playbook_template = playbook_template
        configured_from_environment = model_mode is None
        self.model_mode = model_mode or configured_model_mode()
        if self.model_mode not in {MODEL_MODE_REFERENCE, MODEL_MODE_OPENROUTER}:
            raise ValueError(f"Unsupported model mode {self.model_mode!r}")
        if configured_from_environment and self.model_mode == MODEL_MODE_OPENROUTER:
            configured_profile = os.getenv("CASEPATH_AGENT_RUNTIME_PROFILE", "").strip()
            if configured_profile != AGENT_RUNTIME_PROFILE:
                raise ValueError(
                    "CASEPATH_AGENT_RUNTIME_PROFILE must match the compiled LangGraph runtime"
                )
        self.canonicalizer = canonicalizer or (
            OpenRouterNemotronCanonicalizer(storage)
            if self.model_mode == MODEL_MODE_OPENROUTER
            else None
        )
        self.agent_orchestrator = agent_orchestrator or (
            NemotronMultiAgentOrchestrator(
                storage, playbook_template=self.playbook_template
            )
            if self.model_mode == MODEL_MODE_OPENROUTER
            else None
        )
        if isinstance(self.agent_orchestrator, NemotronMultiAgentOrchestrator) and (
            self.agent_orchestrator.playbook_template.template_sha256
            != self.playbook_template.template_sha256
        ):
            raise ValueError("pipeline and StateGraph template identities differ")
        self.pace_seconds = max(0.0, float(pace_seconds))
        self.review_lock = threading.RLock()

    def create(
        self,
        claim_id: str,
        *,
        knowledge_mode: str = "current",
        session_id: str = "public",
    ) -> str:
        if (
            self.playbook_template.template_sha256
            != MOULD_PLAYBOOK_TEMPLATE.template_sha256
        ):
            raise ValueError("full source-run creation remains explicitly Mould-only")
        if claim_id not in CLAIMS:
            raise KeyError(claim_id)
        self.playbook_template.require_claim(claim_id)
        if knowledge_mode not in {"current", "baseline"}:
            raise ValueError("Unsupported knowledge mode")
        run_id = self.storage.create_run(claim_id, session_id=session_id)
        threading.Thread(
            target=self._execute,
            args=(run_id, claim_id, knowledge_mode, session_id),
            daemon=True,
        ).start()
        return run_id

    def create_declarative_source(
        self,
        claim_id: str,
        *,
        observable_package: dict[str, Any],
        legal_research: dict[str, Any],
        session_id: str = "public",
    ) -> str:
        """Create-or-resume one provider-free source run by semantic identity."""

        if self.playbook_template.materializer_mode != "declarative_cycle_v1":
            raise ValueError(
                "declarative source creation requires a declarative template"
            )
        if self.model_mode != MODEL_MODE_REFERENCE:
            raise ValueError("declarative source creation is provider-free only")
        if not isinstance(self.agent_orchestrator, NemotronMultiAgentOrchestrator):
            raise ValueError("declarative source creation requires the six-agent graph")
        if not isinstance(
            self.agent_orchestrator.agent_runner, DeterministicStructuredAgent
        ):
            raise ValueError("declarative source creation requires deterministic roles")
        self.playbook_template.require_claim(claim_id)
        validate_template_legal_context_v1(
            template=self.playbook_template,
            legal=legal_research,
        )
        observable = deepcopy(observable_package)
        legal = deepcopy(legal_research)
        source_request = {
            "contract": "casepath.declarative-source-request/1.0.0",
            "session_id": session_id,
            "claim_id": claim_id,
            "template_sha256": self.playbook_template.template_sha256,
            "observable_package_sha256": digest(observable),
            "legal_research_sha256": digest(legal),
        }
        source_request_sha256 = digest(source_request)
        run_id = "run_source_" + source_request_sha256[:32]
        with self.review_lock:
            self.storage.create_run(
                claim_id,
                session_id=session_id,
                run_id=run_id,
                source_request_sha256=source_request_sha256,
                return_existing=True,
            )
            existing = self.storage.get_run(run_id, session_id=session_id)
            if existing is None:
                raise RuntimeError("declarative source reservation disappeared")
            if existing.get("source_request_sha256") != source_request_sha256:
                raise RuntimeError("declarative source reservation changed identity")
            if existing.get("status") == "complete":
                if (
                    existing.get("playbook_template") != self.playbook_template.receipt
                    or digest(existing.get("observable_package"))
                    != source_request["observable_package_sha256"]
                    or digest(existing.get("result", {}).get("legal_research"))
                    != source_request["legal_research_sha256"]
                ):
                    raise RuntimeError("completed declarative source changed identity")
                return run_id
            if existing.get("status") != "queued":
                raise RuntimeError("declarative source is not safely resumable")
            return self._create_declarative_source_once(
                run_id=run_id,
                source_request_sha256=source_request_sha256,
                claim_id=claim_id,
                observable_package=observable,
                legal_research=legal,
                session_id=session_id,
            )

    def _create_declarative_source_once(
        self,
        *,
        run_id: str,
        source_request_sha256: str,
        claim_id: str,
        observable_package: dict[str, Any],
        legal_research: dict[str, Any],
        session_id: str,
    ) -> str:
        """Materialize one already-elected declarative source run."""

        if self.playbook_template.materializer_mode != "declarative_cycle_v1":
            raise ValueError(
                "declarative source creation requires a declarative template"
            )
        if self.model_mode != MODEL_MODE_REFERENCE:
            raise ValueError("declarative source creation is provider-free only")
        if not isinstance(self.agent_orchestrator, NemotronMultiAgentOrchestrator):
            raise ValueError("declarative source creation requires the six-agent graph")
        if not isinstance(
            self.agent_orchestrator.agent_runner, DeterministicStructuredAgent
        ):
            raise ValueError("declarative source creation requires deterministic roles")
        self.playbook_template.require_claim(claim_id)
        validate_template_legal_context_v1(
            template=self.playbook_template,
            legal=legal_research,
        )
        materialized = materialize_template_cycle_v1(
            template=self.playbook_template,
            claim_id=claim_id,
            observable_package=observable_package,
        )
        orchestration_id = "declarative-source." + digest(
            {
                "run_id": run_id,
                "template_sha256": self.playbook_template.template_sha256,
                "observable_package_sha256": digest(observable_package),
            }
        )
        cycle = self.analyze_cycle(
            source_run_id=run_id,
            orchestration_id=orchestration_id,
            observable_package=deepcopy(observable_package),
            facts=[deepcopy(value) for value in materialized.facts],
            process=deepcopy(materialized.process),
            checklist=deepcopy(materialized.checklist),
            verification=deepcopy(materialized.verification),
            transport_mode="deterministic_test_double",
            cycle_verification_builder=lambda facts, process, checklist: (
                build_template_cycle_verification_v1(
                    template=self.playbook_template,
                    facts=facts,
                    process=process,
                    checklist=checklist,
                )
            ),
        )
        audit = cycle["orchestration_audit"]
        accepted = cycle["accepted_cycle_artifacts"]
        verification = cycle["verification"]
        process = deepcopy(accepted["process"])
        checklist = deepcopy(accepted["checklist"])
        nodes_by_id = {node["node_id"]: node for node in process["nodes"]}
        next_node_id = process["current_overlay"]["next_action_node_id"]
        next_node = nodes_by_id[next_node_id]
        result = {
            "claim_id": claim_id,
            "facts": deepcopy(accepted["facts"]),
            "legal_research": deepcopy(legal_research),
            "process": process,
            "checklist": checklist,
            "verification": deepcopy(verification),
            "agent_orchestration": deepcopy(audit),
            "next_action": {
                "title": next_node["title"],
                "detail": next_node["why"],
                "requires_expert_approval": False,
                "process_node_id": next_node_id,
                "agent_brief_contribution": deepcopy(accepted["final_claim_brief"]),
            },
            "playbook_template": self.playbook_template.receipt,
            "playbook_template_record": self.playbook_template.persisted_record,
            "observable_package": deepcopy(observable_package),
            "audit": {
                "input_hash": digest(observable_package),
                "observable_input_hash": digest(observable_package),
                "canonical_state_hash": digest(accepted["facts"]),
                "profile": DETERMINISTIC_PROFILE,
                "orchestrator": ORCHESTRATOR,
                "schema": "casepath.declarative-playbook-source/1.0.0",
                "accepted": True,
                "verification_computed": True,
                "authority_mode": MODEL_MODE_REFERENCE,
            },
        }
        self.storage.patch_run(
            run_id,
            status="complete",
            patch={
                "profile": DETERMINISTIC_PROFILE,
                "release": RELEASE,
                "model_mode": MODEL_MODE_REFERENCE,
                "model": None,
                "source_request_sha256": source_request_sha256,
                "playbook_template": self.playbook_template.receipt,
                "playbook_template_record": self.playbook_template.persisted_record,
                "observable_package": deepcopy(observable_package),
                "agent_orchestration": deepcopy(audit),
                "verification": deepcopy(verification),
                "result": result,
            },
        )
        return run_id

    def pause(self, seconds: float) -> None:
        if self.pace_seconds:
            time.sleep(seconds * self.pace_seconds)

    def analyze_cycle(
        self,
        *,
        source_run_id: str,
        orchestration_id: str,
        observable_package: dict[str, Any],
        facts: list[dict[str, Any]],
        process: dict[str, Any],
        checklist: dict[str, Any],
        verification: dict[str, Any],
        transport_mode: Literal["openrouter", "deterministic_test_double"],
        cycle_verification_builder: Callable[
            [list[dict[str, Any]], dict[str, Any], dict[str, Any]],
            dict[str, Any],
        ],
        progress_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """Run one fresh cycle through the existing six-role StateGraph.

        The outer claim loop supplies record-projected, deterministically gated
        artifacts.  Model-owned fields remain bounded by the same production
        validators and may not replace those artifacts silently.
        """

        if self.agent_orchestrator is None:
            raise RuntimeError("cycle analysis requires the compiled StateGraph")
        if transport_mode != "deterministic_test_double":
            raise RuntimeError(
                "the zero-cost claim-loop candidate permits only provider-free cycles"
            )
        if not isinstance(
            self.agent_orchestrator.agent_runner, DeterministicStructuredAgent
        ):
            raise RuntimeError(
                "deterministic cycle requires the credential-free structured runner"
            )
        expected_gate_hash = verification.get("receipt_sha256")
        gate_material = {
            key: value for key, value in verification.items() if key != "receipt_sha256"
        }
        if (
            verification.get("valid") is not True
            or verification.get("computed") is not True
            or expected_gate_hash != digest(gate_material)
            or verification.get("facts_sha256") != digest(facts)
            or verification.get("process_sha256") != digest(process)
            or verification.get("checklist_sha256") != digest(checklist)
        ):
            raise RuntimeError("cycle input does not carry a fresh deterministic gate")
        canonicalization = {
            "model": OPENROUTER_MODEL,
            "call_id": f"cycle-canonical.{digest({'orchestration_id': orchestration_id, 'facts': facts})}",
            "origin_call_id": f"cycle-canonical.{digest({'orchestration_id': orchestration_id, 'facts': facts})}",
            "cache_hit": True,
            "response_id": None,
            "response_model": None,
            "upstream_provider": None,
            "usage_source": None,
            "finish_reason": "deterministic_test_double",
            "usage": None,
            "transport_mode": "deterministic_test_double",
            "diagnostics": {
                "accepted_fact_ids": [value["fact_id"] for value in facts],
                "accepted_fact_count": len(facts),
                "rejected_facts": [],
                "rejected_fact_count": 0,
                "source_reference_projection_fact_ids": [],
                "source_reference_projection_count": 0,
                "deterministic_fallback_applied": False,
            },
        }

        fresh_verifications: list[dict[str, Any]] = []

        def fresh_verification(
            accepted_process: dict[str, Any],
            accepted_checklist: dict[str, Any],
        ) -> dict[str, Any]:
            value = cycle_verification_builder(
                deepcopy(facts),
                deepcopy(accepted_process),
                deepcopy(accepted_checklist),
            )
            if not isinstance(value, dict):
                raise RuntimeError(
                    "cycle verification builder did not run the release gates"
                )
            material = {
                key: item for key, item in value.items() if key != "receipt_sha256"
            }
            if (
                value.get("valid") is not True
                or value.get("computed") is not True
                or value.get("facts_sha256") != digest(facts)
                or value.get("process_sha256") != digest(accepted_process)
                or value.get("checklist_sha256") != digest(accepted_checklist)
                or value.get("whole_playbook_hash")
                != digest(
                    {
                        "process": accepted_process,
                        "checklist": accepted_checklist,
                    }
                )
                or value.get("receipt_sha256") != digest(material)
            ):
                raise RuntimeError(
                    "cycle verification builder did not run the release gates"
                )
            return value

        seed_verification = fresh_verification(process, checklist)

        def rebuild_verification(
            accepted_process: dict[str, Any],
            accepted_checklist: dict[str, Any],
        ) -> dict[str, Any]:
            value = fresh_verification(accepted_process, accepted_checklist)
            fresh_verifications.append(deepcopy(value))
            return value

        graph_result = self.agent_orchestrator.invoke(
            run_id=source_run_id,
            orchestration_id=orchestration_id,
            observable_package=observable_package,
            canonicalization=canonicalization,
            facts=deepcopy(facts),
            process=deepcopy(process),
            checklist=deepcopy(checklist),
            verification=seed_verification,
            verification_builder=rebuild_verification,
            progress_sink=progress_sink,
            include_accepted_artifacts=True,
        )
        audit = graph_result.get("orchestration_audit")
        accepted_cycle_artifacts = graph_result.get("accepted_cycle_artifacts")
        if not isinstance(audit, dict) or not isinstance(
            accepted_cycle_artifacts, dict
        ):
            raise RuntimeError("cycle graph did not return accepted artifacts")
        if audit.get(
            "playbook_template_sha256"
        ) != self.playbook_template.template_sha256 or any(
            gate.get("playbook_template_sha256")
            != self.playbook_template.template_sha256
            for gate in audit.get("deterministic_gates", [])
        ):
            raise RuntimeError("cycle graph template provenance is invalid")
        if len(fresh_verifications) != 1:
            raise RuntimeError("cycle graph did not produce one fresh verification")
        accepted_verification = fresh_verifications[0]
        whole_gate = next(
            (
                value
                for value in audit.get("deterministic_gates", [])
                if value.get("agent_id") == "whole_playbook_gate"
            ),
            None,
        )
        if (
            not isinstance(whole_gate, dict)
            or whole_gate.get("verification_report_hash")
            != accepted_artifact_hash(accepted_verification)
            or whole_gate.get("verification_whole_playbook_hash")
            != accepted_verification["whole_playbook_hash"]
        ):
            raise RuntimeError("cycle graph did not bind its fresh verification")
        accepted_payload = {
            key: value
            for key, value in accepted_cycle_artifacts.items()
            if key != "receipt_sha256"
        }
        if (
            accepted_cycle_artifacts.get("contract")
            != "casepath.accepted-cycle-artifacts/1.0.0"
            or accepted_cycle_artifacts.get("receipt_sha256")
            != digest(accepted_payload)
            or accepted_cycle_artifacts.get("facts") != facts
            or accepted_cycle_artifacts.get("verification") != accepted_verification
            or whole_gate.get("output_artifact_hash")
            != accepted_artifact_hash(
                {
                    "process": accepted_cycle_artifacts.get("process"),
                    "checklist": accepted_cycle_artifacts.get("checklist"),
                    "final_brief": accepted_cycle_artifacts.get("final_claim_brief"),
                }
            )
        ):
            raise RuntimeError("cycle accepted-artifact receipt is invalid")
        return {
            "orchestration_audit": audit,
            "verification": accepted_verification,
            "accepted_cycle_artifacts": accepted_cycle_artifacts,
        }

    def emit(
        self,
        run_id: str,
        stage: str,
        label: str,
        agent: str,
        status: str,
        **payload: Any,
    ):
        return self.storage.add_event(
            run_id,
            {
                "stage": stage,
                "label": label,
                "agent": agent,
                "status": status,
                "implementation": "deterministic_application_tool",
                "model": None,
                "actor_type": "deterministic_tool",
                "orchestrator": ORCHESTRATOR,
                "shared_context": f"claim-context:{run_id}",
                "validator": f"{stage}-validator/15.2",
                "prompt_version": f"{stage}/15.2",
                **payload,
            },
        )

    def _execute(
        self, run_id: str, claim_id: str, knowledge_mode: str, session_id: str
    ):
        claim = CLAIMS[claim_id]
        governed_memories = self.storage.memories(session_id=session_id)
        counterfactual_learning_freeze = (
            _counterfactual_learning_freeze(governed_memories)
            if knowledge_mode == "baseline"
            else None
        )
        memories = [] if knowledge_mode == "baseline" else governed_memories
        knowledge = self._active_knowledge(session_id=session_id)
        self.storage.patch_run(
            run_id,
            status="running",
            patch={
                "profile": (
                    PROFILE
                    if self.model_mode == MODEL_MODE_OPENROUTER
                    else DETERMINISTIC_PROFILE
                ),
                "release": RELEASE,
                "orchestrator": ORCHESTRATOR,
                "shared_context": {"claim_id": claim_id, "version": 1, "artifacts": []},
                "knowledge_version": knowledge["version"],
                "knowledge_mode": knowledge_mode,
                "model_mode": self.model_mode,
                "model": OPENROUTER_MODEL
                if self.model_mode == MODEL_MODE_OPENROUTER
                else None,
                "playbook_template": self.playbook_template.receipt,
                "playbook_template_record": self.playbook_template.persisted_record,
                "counterfactual_learning_freeze": counterfactual_learning_freeze,
            },
        )
        self.storage.add_event(
            run_id,
            {
                "stage": "orchestrator",
                "label": "Orchestrator opened one shared claim context",
                "agent": "Claim Context Initialization Tool",
                "actor_type": "deterministic_tool",
                "status": "started",
                "headline": "Specialists will build one claim-handling playbook",
                "detail": "Each specialist receives the same claim context and contributes a typed artifact for the next specialist.",
                "implementation": "deterministic_application_tool",
                "model": None,
                "orchestrator": ORCHESTRATOR,
                "validator": "orchestrator-state/15.2",
                "prompt_version": None,
                "output_artifact": "shared_claim_context",
            },
        )
        try:
            parsed = self._read_stage(run_id, claim)
            understanding = self._understand_stage(run_id, claim, parsed)
            legal = self._research_stage(run_id, claim, understanding)
            process = self._process_stage(
                run_id, claim, understanding, legal, memories, knowledge
            )
            checklist = self._evidence_stage(
                run_id, claim, understanding, process, legal, memories, knowledge
            )
            precedents = self._experience_stage(
                run_id, claim, understanding, process, checklist, memories
            )
            precedent_ranking = (
                self.storage.get_run(run_id, session_id=session_id) or {}
            ).get("precedent_ranking")
            if not isinstance(precedent_ranking, dict):
                raise ValueError("precedent_ranking_receipt_missing")
            verification = self._verify_stage(
                run_id,
                claim,
                understanding,
                legal,
                process,
                checklist,
                precedents,
                precedent_ranking,
                memories,
            )

            def rebuild_agent_verification(
                accepted_process: dict[str, Any],
                accepted_checklist: dict[str, Any],
            ) -> dict[str, Any]:
                reranked = rank_precedents(
                    current_claim_id=claim["claim_id"],
                    understanding=understanding,
                    process=accepted_process,
                    checklist=accepted_checklist,
                    memories=memories,
                    corpus=HISTORICAL_CASES,
                )
                precedents[:] = reranked["results"]
                precedent_ranking.clear()
                precedent_ranking.update(reranked["receipt"])
                return self._verification_report(
                    claim,
                    understanding,
                    legal,
                    accepted_process,
                    accepted_checklist,
                    precedents,
                    precedent_ranking,
                    memories,
                )

            agent_orchestration = self._agent_orchestration_stage(
                run_id,
                claim,
                understanding,
                process,
                checklist,
                verification,
                verification_builder=rebuild_agent_verification,
            )
            # Bind the execution authority at the run boundary in every mode.
            # OpenRouter runs add accepted candidates below; deterministic
            # reference runs must still make their zero-model execution explicit.
            self.storage.patch_run(
                run_id,
                patch={"agent_orchestration": agent_orchestration},
            )
            if self.model_mode == MODEL_MODE_OPENROUTER:
                verification = self._verification_report(
                    claim,
                    understanding,
                    legal,
                    process,
                    checklist,
                    precedents,
                    precedent_ranking,
                    memories,
                )
                self.storage.patch_run(
                    run_id,
                    patch={
                        "understanding": understanding,
                        "process": process,
                        "checklist": checklist,
                        "precedents": precedents,
                        "precedent_ranking": precedent_ranking,
                        "verification": verification,
                        "agent_orchestration": agent_orchestration,
                    },
                )
                gate_by_id = {
                    item["agent_id"]: item
                    for item in agent_orchestration["deterministic_gates"]
                }
                accepted_artifacts = [
                    (
                        "deterministic_process_gate",
                        "process_graph",
                        process,
                        "Process graph accepted after the Nemotron mapping contribution and deterministic gate",
                    ),
                    (
                        "deterministic_evidence_gate",
                        "evidence_model",
                        checklist,
                        "Evidence model accepted after the Nemotron checklist contribution and deterministic gate",
                    ),
                    (
                        "whole_playbook_gate",
                        "verified_claim_playbook",
                        None,
                        "Final claim brief and recomputed verification accepted after the Nemotron critic and whole-playbook gate",
                    ),
                ]
                for (
                    gate_id,
                    artifact_name,
                    artifact_value,
                    headline,
                ) in accepted_artifacts:
                    gate = gate_by_id[gate_id]
                    if gate_id != "whole_playbook_gate":
                        gate["output_artifact_hash"] = accepted_artifact_hash(
                            artifact_value
                        )
                    else:
                        gate["verification_report_hash"] = digest(verification)
                        gate["verification_whole_playbook_hash"] = verification[
                            "whole_playbook_hash"
                        ]
                        gate["accepted_verification_ids"] = [
                            item["name"] for item in verification["checks"]
                        ]
                    self.storage.add_event(
                        run_id,
                        {
                            "stage": "agent_orchestration",
                            "label": f"Accepted {artifact_name.replace('_', ' ')}",
                            "agent": gate["role"],
                            "agent_id": gate_id,
                            "source_agent_id": gate["source_agent_id"],
                            "actor_type": "deterministic_gate",
                            "status": "completed",
                            "receipt_type": "accepted_artifact",
                            "acceptance_scope": "pre_review_model_output",
                            "headline": headline,
                            "detail": "The retained hash covers the exact hybrid DTO rebuilt from accepted model fields and explicit deterministic fallbacks.",
                            "implementation": MULTI_AGENT_IMPLEMENTATION,
                            "model": None,
                            "source_model": OPENROUTER_MODEL,
                            "source_call_id": gate["source_call_id"],
                            "delegation_id": gate.get("delegation_id"),
                            "accepted_ids": gate.get("accepted_ids", []),
                            "accepted_count": gate.get("accepted_count", 0),
                            "output_artifact": artifact_name,
                            "output_artifact_hash": gate["output_artifact_hash"],
                            **(
                                {
                                    "verification_report_hash": gate[
                                        "verification_report_hash"
                                    ],
                                    "verification_whole_playbook_hash": gate[
                                        "verification_whole_playbook_hash"
                                    ],
                                    "accepted_verification_ids": gate[
                                        "accepted_verification_ids"
                                    ],
                                }
                                if gate_id == "whole_playbook_gate"
                                else {}
                            ),
                            "external_tracing": False,
                        },
                    )
                self.storage.patch_run(
                    run_id,
                    patch={
                        "understanding": understanding,
                        "process": process,
                        "checklist": checklist,
                        "precedents": precedents,
                        "precedent_ranking": precedent_ranking,
                        "verification": verification,
                        "agent_orchestration": agent_orchestration,
                    },
                )
            memory_application, memory_verification = self._apply_case_specific_memory(
                run_id,
                session_id,
                claim,
                understanding,
                legal,
                process,
                checklist,
                precedents,
                memories,
                precedent_ranking,
            )
            if memory_verification is not None:
                verification = memory_verification
            self.storage.patch_run(
                run_id,
                patch={
                    "understanding": understanding,
                    "process": process,
                    "checklist": checklist,
                    "precedents": precedents,
                    "precedent_ranking": precedent_ranking,
                    "verification": verification,
                    "agent_orchestration": agent_orchestration,
                },
                stream_events=accepted_artifact_events(
                    understanding,
                    process,
                    checklist,
                    agent_orchestration,
                    verification,
                    memory_application,
                ),
            )
            result = self._final_result(
                claim,
                parsed,
                understanding,
                legal,
                process,
                checklist,
                precedents,
                verification,
                knowledge,
                knowledge_mode,
                agent_orchestration,
                memory_application,
                precedent_ranking,
            )
            self.storage.add_event(
                run_id,
                {
                    "stage": "complete",
                    "label": "Final acceptance gate assembled the playbook",
                    "agent": "Final Playbook Acceptance Gate",
                    "actor_type": "deterministic_gate",
                    "status": "completed",
                    "headline": f"{len(process['nodes'])} process nodes and {len(checklist['items'])} evidence relationships ready",
                    "detail": "The full process, evidence model, current claim overlay, precedents and verification record now form one reviewable artifact.",
                    "implementation": (
                        MULTI_AGENT_IMPLEMENTATION
                        if self.model_mode == MODEL_MODE_OPENROUTER
                        else "deterministic_acceptance_gate"
                    ),
                    "model": None,
                    "orchestrator": ORCHESTRATOR,
                    "validator": "whole-playbook-validator/15.2",
                    "prompt_version": None,
                    "input_artifacts": [
                        "canonical_claim_state",
                        "legal_context",
                        "process_graph",
                        "evidence_model",
                        "precedents",
                    ],
                    "output_artifact": "claim_handling_playbook",
                    "output_hash": digest(result),
                },
            )
            self.storage.patch_run(
                run_id,
                status="complete",
                patch={"result": result, "completed_at": time.time()},
            )
        except Exception as exc:  # pragma: no cover - fail-safe path
            partial = self.storage.get_run(run_id, session_id=session_id) or {}
            safe_context = getattr(exc, "safe_context", {})
            failure_stage = (
                getattr(exc, "agent_id", None)
                or safe_context.get("agent_id")
                or "deterministic_failure_boundary"
            )
            failure_invariant = (
                getattr(exc, "invariant", None)
                or safe_context.get("error_invariant")
                or "execution_failed"
            )
            accepted_state = {
                "canonical_state_prepared": isinstance(
                    partial.get("understanding"), dict
                ),
                "process_candidate_prepared": isinstance(
                    partial.get("process_candidate") or partial.get("process"), dict
                ),
                "evidence_candidate_prepared": isinstance(
                    partial.get("checklist_candidate") or partial.get("checklist"), dict
                ),
                "final_playbook_accepted": False,
            }
            self.storage.add_event(
                run_id,
                {
                    "stage": "failed",
                    "label": "Analysis stopped safely",
                    "agent": "Failure boundary",
                    "status": "failed",
                    "headline": "No final playbook was accepted",
                    "detail": "Partial candidate artifacts may remain visible for audit, but the terminal acceptance boundary failed closed.",
                    "implementation": "deterministic",
                    "model": None,
                    "actor_type": "deterministic_gate",
                    "failure_stage": failure_stage,
                    "failure_invariant": failure_invariant,
                    "accepted_state": accepted_state,
                    "validator": "fail-closed/15.2",
                    "prompt_version": None,
                },
            )
            self.storage.patch_run(
                run_id,
                status="failed",
                patch={
                    "error": f"{type(exc).__name__}: {failure_invariant}",
                    "failure_stage": failure_stage,
                    "accepted_state": accepted_state,
                },
            )

    def _read_stage(self, run_id: str, claim: dict[str, Any]) -> dict[str, Any]:
        stage, label, agent = VISIBLE_STAGES[0]
        self.emit(
            run_id,
            stage,
            label,
            agent,
            "started",
            headline=f"Reading the message and {len(claim['artifact_ids'])} source files",
            detail="The originals remain separate from every machine representation.",
            question="What did the customer actually submit?",
            input_artifacts=["observable_claim_package"],
            output_artifact="parsed_submission",
            handoff_to="Canonical Claim Preparation Tool",
        )
        self.pause(0.35)
        files = []
        page_count = 0
        image_count = 0
        correspondence_count = 1
        for artifact_id in claim["artifact_ids"]:
            artifact = ARTIFACTS[artifact_id]
            page_count += (
                artifact.get("page_count", 1)
                if artifact["media_type"] == "application/pdf"
                else 0
            )
            image_count += int(artifact["media_type"].startswith("image/"))
            correspondence_count += int(artifact["media_type"] == "message/rfc822")
            if artifact["media_type"] == "application/pdf":
                read_detail = (
                    f"{artifact['page_count']} rendered pages and extracted text"
                )
            elif artifact["media_type"] == "message/rfc822":
                read_detail = f"Correspondence from {artifact['email']['from']}"
            else:
                read_detail = "Original pixels, dimensions and checksum recorded"
            files.append(
                {
                    "artifact_id": artifact_id,
                    "title": artifact["title"],
                    "filename": artifact["filename"],
                    "read_detail": read_detail,
                }
            )
        parsed = {
            "message_chars": len(claim["message"]),
            "files": files,
            "source_count": len(files) + 1,
            "pdf_pages": page_count,
            "images": image_count,
            "correspondence": correspondence_count,
            "input_hash": digest(
                {
                    "claim": claim,
                    "artifact_hashes": [
                        ARTIFACTS[item]["sha256"] for item in claim["artifact_ids"]
                    ],
                }
            ),
        }
        self.storage.patch_run(run_id, patch={"parsed_submission": parsed})
        self.emit(
            run_id,
            stage,
            label,
            agent,
            "completed",
            headline=f"{parsed['source_count']} sources read",
            detail=f"{page_count} PDF pages, {image_count} photograph and {correspondence_count} correspondence records entered the shared context.",
            question="What did the customer actually submit?",
            items=[f"{item['title']}: {item['read_detail']}" for item in files],
            metrics={
                "sources": parsed["source_count"],
                "pdf_pages": page_count,
                "images": image_count,
            },
            input_hash=parsed["input_hash"],
            output_hash=digest(parsed),
            input_artifacts=["observable_claim_package"],
            output_artifact="parsed_submission",
            handoff_to="Canonical Claim Preparation Tool",
        )
        self.pause(0.25)
        return parsed

    def _understand_stage(
        self, run_id: str, claim: dict[str, Any], parsed: dict[str, Any]
    ) -> dict[str, Any]:
        stage, label, agent = VISIBLE_STAGES[1]
        self.emit(
            run_id,
            stage,
            label,
            agent,
            "started",
            headline="Reconciling claims across the message and attachments",
            detail="Supported facts, allegations, conflicts and unknowns remain distinct.",
            question="What claim state is supported by the observable evidence?",
            input_artifacts=["parsed_submission"],
            output_artifact="canonical_claim_state",
            handoff_to="Swiss Legal Source Tool",
        )
        self.pause(0.4)
        primary = claim["claim_id"] == "DEF-027-E0-DEMO"
        if primary:
            facts = [
                fact(
                    "fact_tenancy",
                    "Residential tenancy",
                    "Established",
                    "known",
                    "The document is a residential lease agreement, identifies Alex Morgan as the tenant and states that the apartment is rented for residential use.",
                    [
                        text_ref("art_lease", 1, "Residential Lease Agreement", agent),
                        text_ref(
                            "art_lease",
                            1,
                            "Tenant Alex Morgan, Feldbergstrasse 114, 4057 Basel",
                            agent,
                        ),
                        text_ref(
                            "art_lease",
                            1,
                            "The apartment is rented for residential use.",
                            agent,
                        ),
                    ],
                    decision_key="scope",
                    normalized_value="supported_in_scope",
                ),
                fact(
                    "fact_policy_route",
                    "Legal-protection policy reference",
                    "Present",
                    "known",
                    "The intake contains a policy reference. This demo does not decide coverage terms.",
                    [
                        metadata_ref(
                            "intake",
                            "policy_reference",
                            claim["customer"]["policy"],
                            "Intake Metadata Agent",
                        )
                    ],
                ),
                fact(
                    "fact_dispute",
                    "Concrete disagreement",
                    "Established",
                    "known",
                    "The customer states disagreement and asks for cause clarification and repair; management says the marks appear consistent with insufficient ventilation and does not plan a technical inspection.",
                    [
                        text_ref(
                            "message",
                            1,
                            "I disagree because the problem keeps returning.",
                            agent,
                        ),
                        text_ref(
                            "message",
                            1,
                            "I want the cause clarified and the defect repaired.",
                            agent,
                        ),
                        text_ref(
                            "art_management_reply",
                            1,
                            "the marks appear consistent with insufficient ventilation",
                            agent,
                        ),
                        text_ref(
                            "art_management_reply",
                            1,
                            "We do not currently plan a technical inspection.",
                            agent,
                        ),
                    ],
                    decision_key="dispute",
                    normalized_value="present",
                ),
                fact(
                    "fact_recurrence",
                    "Recurring mould",
                    "Established",
                    "known",
                    "The message, photograph and timeline describe recurrence after cleaning.",
                    [
                        text_ref("message", 1, "keeps coming back", agent),
                        visual_ref(
                            "art_photo",
                            [0.42, 0.10, 0.20, 0.70],
                            "Visible dark spotting is concentrated along the external wall corner.",
                        ),
                        text_ref(
                            "art_timeline",
                            1,
                            "spots returned within approximately two weeks",
                            agent,
                        ),
                    ],
                    decision_key="recurrence",
                    normalized_value="supported",
                ),
                fact(
                    "fact_notification",
                    "Landlord notified",
                    "Established",
                    "known",
                    "The original email is dated 15 July 2026 and asks for inspection and repair; the delivery record says the recipient mail server accepted it.",
                    [
                        text_ref(
                            "art_notification",
                            1,
                            "Wed, 15 Jul 2026 08:32:00 +0200",
                            agent,
                        ),
                        text_ref(
                            "art_notification",
                            1,
                            "Please arrange an inspection and repair.",
                            agent,
                        ),
                        text_ref(
                            "art_delivery",
                            1,
                            "Accepted by recipient mail server",
                            agent,
                        ),
                    ],
                    decision_key="notification",
                    normalized_value="notified",
                ),
                fact(
                    "fact_ventilation_allegation",
                    "Management alleges insufficient ventilation",
                    "Established as an allegation",
                    "known",
                    "The reply contains the allegation but no technical proof.",
                    [
                        text_ref(
                            "art_management_reply",
                            1,
                            "consistent with insufficient ventilation",
                            agent,
                        )
                    ],
                    semantic_role="management_ventilation_allegation",
                ),
                fact(
                    "fact_cause",
                    "Cause of mould",
                    "Unresolved",
                    "unknown",
                    "No neutral assessment establishes a building defect, tenant-use cause or mixed cause.",
                    [
                        text_ref(
                            "art_management_reply",
                            1,
                            "Based on your description",
                            agent,
                        ),
                        text_ref(
                            "art_timeline",
                            1,
                            "No independent inspection has been carried out.",
                            agent,
                        ),
                    ],
                    confidence=0.92,
                    decision_key="causation",
                    normalized_value="unresolved",
                ),
                fact(
                    "fact_health",
                    "Immediate health or safety concern",
                    "Not reported",
                    "known",
                    "The customer reports no current symptoms or emergency.",
                    [
                        text_ref(
                            "message",
                            1,
                            "There are no current health symptoms and no urgent deadline.",
                            agent,
                        )
                    ],
                    decision_key="urgency",
                    normalized_value="not_urgent",
                ),
                fact(
                    "fact_date_conflict",
                    "First-observation date",
                    "Conflicting",
                    "conflicting",
                    "The customer says around 20 March; the timeline says 12 March.",
                    [
                        text_ref("message", 1, "around 20 March", agent),
                        text_ref("art_timeline", 1, "12 Mar 2026", agent),
                    ],
                    confidence=0.99,
                ),
            ]
            summary = "Recurring bedroom mould in a Basel tenancy. Written notice and a concrete dispute are established. Management blames ventilation, but technical causation remains unresolved."
            issues = [
                {
                    "issue": "Technical cause remains unresolved",
                    "severity": "controlling",
                    "why": "Responsibility and remedy branches depend on competent causation evidence.",
                },
                {
                    "issue": "First-observation date conflicts",
                    "severity": "clarify",
                    "why": "The message and chronology give different March dates.",
                },
            ]
        else:
            facts = [
                fact(
                    "later_fact_tenancy",
                    "Residential tenancy",
                    "Established",
                    "known",
                    "The lease identifies Sam Keller as tenant of the Basel apartment and states residential use.",
                    [
                        text_ref(
                            "art_later_lease",
                            1,
                            "Tenant Sam Keller, Klybeckstrasse 77, 4057 Basel",
                            agent,
                        ),
                        text_ref(
                            "art_later_lease", 1, "Permitted use Residential use", agent
                        ),
                    ],
                    decision_key="scope",
                    normalized_value="supported_in_scope",
                ),
                fact(
                    "later_fact_dispute",
                    "Concrete disagreement",
                    "Established",
                    "known",
                    "The customer disagrees with management's ventilation position and requests investigation and repair; management acknowledges the notice and refuses inspection.",
                    [
                        text_ref(
                            "art_later_email",
                            1,
                            "I disagree with the management's position.",
                            agent,
                        ),
                        text_ref(
                            "art_later_email",
                            1,
                            "I want the cause checked and the recurring condition repaired.",
                            agent,
                        ),
                        text_ref(
                            "art_later_management_reply",
                            1,
                            "We do not plan a technical inspection",
                            agent,
                        ),
                    ],
                    decision_key="dispute",
                    normalized_value="present",
                ),
                fact(
                    "later_fact_recurrence",
                    "Recurring dark spots after window work",
                    "Established",
                    "known",
                    "The email and photograph describe recurrence beside the replaced window.",
                    [
                        text_ref(
                            "art_later_email",
                            1,
                            "dark spots have appeared around the bedroom window",
                            agent,
                        ),
                        text_ref(
                            "art_later_notification",
                            1,
                            "Condensation and dark spots have repeatedly appeared around the bedroom window since the replacement work in May.",
                            agent,
                        ),
                        visual_ref(
                            "art_later_photo",
                            [0.08, 0.40, 0.82, 0.42],
                            "Visible condensation crosses the lower glazing and dark spotting appears beside the window reveal.",
                        ),
                    ],
                    decision_key="recurrence",
                    normalized_value="supported",
                ),
                fact(
                    "later_fact_recent_window_work",
                    "Recent window replacement",
                    "Established",
                    "known",
                    "The contractor completion record confirms replacement in May 2026.",
                    [
                        text_ref(
                            "art_window_notice",
                            1,
                            "replaced between 18 and 22 May 2026",
                            agent,
                        )
                    ],
                ),
                fact(
                    "later_fact_ventilation_allegation",
                    "Management alleges insufficient airing",
                    "Established as an allegation",
                    "known",
                    "Management's original reply alleges insufficient airing while supplying no technical assessment.",
                    [
                        text_ref(
                            "art_later_management_reply",
                            1,
                            "we consider insufficient airing the likely cause",
                            agent,
                        )
                    ],
                    semantic_role="management_ventilation_allegation",
                ),
                fact(
                    "later_fact_cause",
                    "Cause around replaced window",
                    "Unresolved",
                    "unknown",
                    "No inspection links the condition to use, seals, insulation or another building cause.",
                    [
                        text_ref(
                            "art_later_email",
                            1,
                            "No technician has inspected the window or wall.",
                            agent,
                        ),
                        text_ref(
                            "art_later_management_reply",
                            1,
                            "We do not plan a technical inspection",
                            agent,
                        ),
                    ],
                    confidence=0.94,
                    decision_key="causation",
                    normalized_value="unresolved",
                ),
                fact(
                    "later_fact_health",
                    "Immediate health or safety concern",
                    "Not reported",
                    "known",
                    "The customer reports no current health symptoms and no urgent deadline.",
                    [
                        text_ref(
                            "art_later_email",
                            1,
                            "I have no current health symptoms and there is no urgent deadline.",
                            agent,
                        )
                    ],
                    decision_key="urgency",
                    normalized_value="not_urgent",
                ),
            ]
            summary = "Recurring dark spots beside a recently replaced window in a Basel tenancy. Written notice and a concrete dispute are established. Management blames airing, but technical causation remains unresolved."
            issues = [
                {
                    "issue": "Technical cause remains unresolved",
                    "severity": "controlling",
                    "why": "The timing after window work and the ventilation allegation require competent evidence.",
                },
                {
                    "issue": "No technical inspection has occurred",
                    "severity": "evidence",
                    "why": "Management's allegation is attached, but no competent evidence distinguishes use, seals, insulation or mixed causes.",
                },
            ]
        if primary:
            facts.extend(
                [
                    fact(
                        "fact_source_integrity",
                        "Source package integrity",
                        "Recorded",
                        "known",
                        "Source hashes and media metadata were recorded before reasoning.",
                        [
                            metadata_ref(
                                artifact_id,
                                "sha256",
                                ARTIFACTS[artifact_id]["sha256"],
                                "Source Integrity Agent",
                            )
                            for artifact_id in claim["artifact_ids"]
                        ],
                    ),
                    fact(
                        "fact_customer_objective",
                        "Customer objective",
                        "Clarify cause and repair the defect",
                        "known",
                        "The customer asks for the cause to be clarified and the defect repaired.",
                        [
                            text_ref(
                                "message",
                                1,
                                "I want the cause clarified and the defect repaired.",
                                agent,
                            )
                        ],
                    ),
                    fact(
                        "fact_repair_history",
                        "Inspection and repair history",
                        "No technical inspection reported",
                        "known",
                        "Management states that it does not plan a technical inspection.",
                        [
                            text_ref(
                                "art_management_reply",
                                1,
                                "We do not currently plan a technical inspection.",
                                agent,
                            )
                        ],
                    ),
                    fact(
                        "fact_tenant_use_cause",
                        "Supported use-related cause",
                        "Unresolved",
                        "unknown",
                        "A ventilation allegation is present, but no competent evidence establishes a use-related cause.",
                        [
                            text_ref(
                                "art_management_reply",
                                1,
                                "appear consistent with insufficient ventilation",
                                agent,
                            )
                        ],
                    ),
                    fact(
                        "fact_remedy_plan",
                        "Supported remedy plan",
                        "Not reached",
                        "unknown",
                        "A remedy plan depends on supported causation and responsibility.",
                        [],
                    ),
                    fact(
                        "fact_financial_remedy",
                        "Supported financial remedy",
                        "Not reached",
                        "unknown",
                        "No financial remedy branch has been selected.",
                        [],
                    ),
                    fact(
                        "fact_settlement_proposal",
                        "Settlement position",
                        "Not reached",
                        "unknown",
                        "No settlement branch has been reached.",
                        [],
                    ),
                    fact(
                        "fact_escalation_ready",
                        "Escalation readiness",
                        "Not reached",
                        "unknown",
                        "Escalation depends on the supported remedy and dispute state.",
                        [],
                    ),
                    fact(
                        "fact_resolution_complete",
                        "Resolution complete",
                        "Not reached",
                        "unknown",
                        "No terminal outcome has been reached.",
                        [],
                    ),
                ]
            )
        else:
            facts.extend(
                [
                    fact(
                        "later_fact_source_integrity",
                        "Source package integrity",
                        "Recorded",
                        "known",
                        "Source hashes and media metadata were recorded before reasoning.",
                        [
                            metadata_ref(
                                artifact_id,
                                "sha256",
                                ARTIFACTS[artifact_id]["sha256"],
                                "Source Integrity Agent",
                            )
                            for artifact_id in claim["artifact_ids"]
                        ],
                    ),
                    fact(
                        "later_fact_policy_route",
                        "Legal-protection policy reference",
                        "Present",
                        "known",
                        "The intake contains a policy reference without deciding coverage.",
                        [
                            metadata_ref(
                                "intake",
                                "policy_reference",
                                claim["customer"]["policy"],
                                "Intake Metadata Agent",
                            )
                        ],
                    ),
                    fact(
                        "later_fact_customer_objective",
                        "Customer objective",
                        "Clarify cause and repair the condition",
                        "known",
                        "The customer requests investigation of the cause and repair of the recurring condition.",
                        [
                            text_ref(
                                "art_later_email",
                                1,
                                "I want the cause checked and the recurring condition repaired.",
                                agent,
                            )
                        ],
                    ),
                    fact(
                        "later_fact_notification",
                        "Landlord notification",
                        "Established",
                        "known",
                        "The original notice requests inspection and repair, and management's reply acknowledges receiving it.",
                        [
                            text_ref(
                                "art_later_notification",
                                1,
                                "Please arrange an inspection of the window and wall",
                                agent,
                            ),
                            text_ref(
                                "art_later_management_reply",
                                1,
                                "We received your message of 3 August.",
                                agent,
                            ),
                        ],
                        decision_key="notification",
                        normalized_value="notified",
                    ),
                    fact(
                        "later_fact_remedy_plan",
                        "Supported remedy plan",
                        "Not reached",
                        "unknown",
                        "A remedy plan depends on supported causation and responsibility.",
                        [],
                    ),
                    fact(
                        "later_fact_financial_remedy",
                        "Supported financial remedy",
                        "Not reached",
                        "unknown",
                        "No financial remedy branch has been selected.",
                        [],
                    ),
                    fact(
                        "later_fact_settlement_proposal",
                        "Settlement position",
                        "Not reached",
                        "unknown",
                        "No settlement branch has been reached.",
                        [],
                    ),
                    fact(
                        "later_fact_escalation_ready",
                        "Escalation readiness",
                        "Not reached",
                        "unknown",
                        "Escalation depends on the supported remedy and dispute state.",
                        [],
                    ),
                    fact(
                        "later_fact_resolution_complete",
                        "Resolution complete",
                        "Not reached",
                        "unknown",
                        "No terminal outcome has been reached.",
                        [],
                    ),
                ]
            )
        observation_records = claim.get("observation_records", ())
        record_projection = project_record_driven_facts_v1(
            seed_facts=facts,
            observation_records=observation_records,
        )
        facts = [deepcopy(value) for value in record_projection.facts]
        catalog = [deepcopy(value) for value in record_projection.catalog]
        canonicalization = {
            "implementation": "deterministic_reference_oracle",
            "model": None,
            "provider": None,
            "mode": MODEL_MODE_REFERENCE,
        }
        # Preserve the exact v20 result surface when no outer-loop observation
        # exists.  A later record-driven cycle binds its projector receipt
        # explicitly, without retroactively changing accepted v20 artifacts.
        if observation_records:
            canonicalization["record_projection_receipt"] = deepcopy(
                record_projection.receipt
            )
        if self.model_mode == MODEL_MODE_OPENROUTER:
            if self.canonicalizer is None:  # pragma: no cover - constructor invariant
                raise RuntimeError("OpenRouter model mode requires a canonicalizer")
            canonical_input = observable_claim_package(claim)
            canonical_input_hash = digest(canonical_input)

            def emit_canonical_provider_start(receipt: dict[str, Any]) -> None:
                self.emit(
                    run_id,
                    stage,
                    label,
                    "Guarded Canonical Facts Agent",
                    "started",
                    headline="Selecting bounded fact meanings from exact source text",
                    detail=(
                        "A fresh Nemotron call selects a bounded meaning, exact source references and confidence for controlling facts. "
                        "CasePath validates each selection and materializes the fact fields; non-controlling meanings remain application-owned."
                    ),
                    implementation="hybrid_guarded_openrouter_canonicalizer",
                    model=OPENROUTER_MODEL,
                    actor_type="nemotron_agent",
                    agent_id="canonical_facts",
                    receipt_type="agent_started",
                    root_agent=True,
                    acceptance_scope="pre_review_model_output",
                    input_artifact="observable_claim_package",
                    input_artifact_hash=canonical_input_hash,
                    provider=OPENROUTER_PROVIDER,
                    requested_model=OPENROUTER_MODEL,
                    call_id=receipt.get("call_id"),
                    call_count=1,
                    cache_hit=False,
                    parent_call_id=None,
                    delegation_id=None,
                    handoff_from="observable_claim_package",
                    handoff_to="orchestrator_plan",
                    external_tracing=False,
                )

            try:
                model_result = self.canonicalizer.canonicalize(
                    canonical_input,
                    run_id=run_id,
                    allowed_fact_catalog=catalog,
                    progress_sink=emit_canonical_provider_start,
                )
            except CanonicalizerError as exc:
                safe_context = exc.safe_context
                outcome = safe_context.get("outcome", "failed")
                error_invariant = (
                    getattr(exc, "invariant", None)
                    or safe_context.get("error_invariant")
                    or {
                        "blocked_missing_credential": "missing_credential",
                        "blocked_cost_guard": "cost_guard",
                        "blocked_provider_concurrency": "provider_concurrency_timeout",
                        "actual_cost_overrun": "actual_cost_overrun",
                    }.get(outcome)
                    or "canonicalization_failed"
                )
                self.emit(
                    run_id,
                    stage,
                    label,
                    "Guarded Canonical Facts Agent",
                    "failed",
                    headline="Canonical facts were not accepted",
                    detail="The bounded provider call failed a local invariant; no final playbook was accepted.",
                    implementation="hybrid_guarded_openrouter_canonicalizer",
                    model=OPENROUTER_MODEL,
                    actor_type="nemotron_agent",
                    agent_id="canonical_facts",
                    receipt_type="agent_failed",
                    failure_scope="root_canonical_facts",
                    root_agent=True,
                    acceptance_scope="pre_review_model_output",
                    error_type=type(exc).__name__,
                    error_invariant=error_invariant,
                    input_artifact="observable_claim_package",
                    input_artifact_hash=canonical_input_hash,
                    provider=OPENROUTER_PROVIDER,
                    requested_model=OPENROUTER_MODEL,
                    call_count=(
                        0
                        if outcome
                        in {
                            "blocked_missing_credential",
                            "blocked_cost_guard",
                            "blocked_provider_concurrency",
                        }
                        else 1
                    ),
                    parent_call_id=None,
                    delegation_id=None,
                    response_id=safe_context.get("response_id"),
                    response_model=safe_context.get("response_model"),
                    upstream_provider=safe_context.get("upstream_provider"),
                    usage_source=safe_context.get("usage_source"),
                    finish_reason=safe_context.get("finish_reason"),
                    outcome=outcome,
                    handoff_from="observable_claim_package",
                    handoff_to="failure_boundary",
                    **{
                        key: safe_context[key]
                        for key in (
                            "call_id",
                            "orchestration_id",
                            "invalid_provenance_field",
                            "invalid_provenance_value_hash",
                            "provider_error_code",
                            "provider_boundary",
                            "expected_upstream_provider",
                        )
                        if key in safe_context
                    },
                    external_tracing=False,
                )
                raise
            facts = model_result["facts"]
            diagnostics = model_result["diagnostics"]
            unresolved = [
                value["label"]
                for value in facts
                if value["state"] in {"unknown", "conflicting"}
            ]
            summary = (
                "Model-assisted hybrid canonicalization accepted "
                f"{diagnostics['accepted_fact_count']} bounded fact contributions; deterministic fallback "
                f"replaced {diagnostics['rejected_fact_count']} rejected proposals, and the deterministic source "
                f"gate projected {diagnostics['source_reference_projection_count']} authoritative citation sets. "
                "Consequential uncertainty "
                "remains explicit."
            )
            issues = [
                {
                    "issue": label,
                    "severity": "requires_review",
                    "why": "The hybrid canonical fact remains unknown or conflicting after deterministic verification.",
                }
                for label in unresolved
            ]
            canonicalization = {
                **model_result,
                "mode": MODEL_MODE_OPENROUTER,
                "authority_mode": "hybrid_guarded",
                "input_artifact_hash": canonical_input_hash,
                "output_artifact_hash": digest(facts),
            }
        understanding = {
            "summary": summary,
            "category": (
                "Rental defect - mould and moisture"
                if primary
                else "Rental defect - mould and moisture"
            ),
            "subcategory": "Recurring moisture with disputed causation",
            "scope": (
                "Swiss residential tenancy" if primary else "Swiss residential tenancy"
            ),
            "dispute": "Concrete dispute appears to exist",
            "facts": facts,
            "issues": issues,
            "observable_only": True,
            "canonicalization": canonicalization,
        }
        self.storage.patch_run(
            run_id,
            patch={"understanding": understanding},
            stream_events=fact_events(understanding),
        )
        unknowns = sum(item["state"] == "unknown" for item in facts)
        conflicts = sum(item["state"] == "conflicting" for item in facts)
        completed_actor = (
            "Guarded Canonical Facts Agent"
            if self.model_mode == MODEL_MODE_OPENROUTER
            else "Canonical Fact Projection Tool"
        )
        self.emit(
            run_id,
            stage,
            label,
            completed_actor,
            "completed",
            headline=f"{len(facts)} supported claim facts assembled",
            detail=f"{unknowns} controlling unknown and {conflicts} conflict remain explicit.",
            question="What claim state is supported by the observable evidence?",
            items=[f"{item['label']}: {item['value']}" for item in facts],
            metrics={"facts": len(facts), "unknowns": unknowns, "conflicts": conflicts},
            input_hash=parsed["input_hash"],
            output_hash=digest(understanding),
            input_artifacts=["parsed_submission"],
            output_artifact="canonical_claim_state",
            handoff_to="Swiss Legal Source Tool",
            implementation=canonicalization["implementation"],
            model=canonicalization["model"],
            actor_type=(
                "nemotron_agent"
                if self.model_mode == MODEL_MODE_OPENROUTER
                else "deterministic_tool"
            ),
            agent_id="canonical_facts",
            receipt_type=(
                "agent_completed"
                if self.model_mode == MODEL_MODE_OPENROUTER
                else "deterministic_stage_completed"
            ),
            acceptance_scope=(
                "pre_review_model_output"
                if self.model_mode == MODEL_MODE_OPENROUTER
                else "deterministic_reference_output"
            ),
            **(
                {
                    "call_id": canonicalization.get("call_id"),
                    "parent_call_id": None,
                    "delegation_id": None,
                    "origin_call_id": canonicalization.get("origin_call_id"),
                    "response_id": canonicalization.get("response_id"),
                    "response_model": canonicalization.get("response_model"),
                    "upstream_provider": canonicalization.get("upstream_provider"),
                    "usage_source": canonicalization.get("usage_source"),
                    "provider": canonicalization.get("provider"),
                    "requested_model": OPENROUTER_MODEL,
                    "call_count": 0 if canonicalization.get("cache_hit") else 1,
                    "cache_hit": canonicalization.get("cache_hit", False),
                    "outcome": (
                        "cache_hit"
                        if canonicalization.get("cache_hit") is True
                        else "succeeded_with_guarded_fallback"
                        if canonicalization.get("diagnostics", {}).get(
                            "rejected_fact_count"
                        )
                        else "succeeded"
                    ),
                    "finish_reason": canonicalization.get("finish_reason")
                    or canonicalization.get("origin_finish_reason"),
                    "usage": canonicalization.get("usage")
                    or canonicalization.get("origin_usage"),
                }
                if self.model_mode == MODEL_MODE_OPENROUTER
                else {}
            ),
            accepted_ids=canonicalization.get("diagnostics", {}).get(
                "accepted_fact_ids", []
            ),
            accepted_count=canonicalization.get("diagnostics", {}).get(
                "accepted_fact_count"
            ),
            rejected_count=canonicalization.get("diagnostics", {}).get(
                "rejected_fact_count"
            ),
            source_reference_projection_fact_ids=canonicalization.get(
                "diagnostics", {}
            ).get("source_reference_projection_fact_ids", []),
            source_reference_projection_count=canonicalization.get(
                "diagnostics", {}
            ).get("source_reference_projection_count", 0),
            deterministic_fallback_applied=canonicalization.get("diagnostics", {}).get(
                "deterministic_fallback_applied", False
            ),
            input_artifact="observable_claim_package",
            external_tracing=False,
        )
        self.pause(0.25)
        return understanding

    def _research_stage(
        self, run_id: str, claim: dict[str, Any], understanding: dict[str, Any]
    ) -> dict[str, Any]:
        stage, label, agent = VISIBLE_STAGES[2]
        legal = legal_context()
        questions = legal["questions"]
        self.emit(
            run_id,
            stage,
            label,
            agent,
            "started",
            headline="Resolving official Swiss-law passages into handling questions",
            detail="A deterministic versioned registry lookup binds each question to exact official passages, interpretations and process nodes.",
            question="Which legal questions shape the complete handling process?",
            input_artifacts=["canonical_claim_state"],
            output_artifact="legal_context",
            handoff_to="Process Projection Tool",
        )
        self.pause(0.4)
        self.storage.patch_run(
            run_id,
            patch={"legal_research": legal},
            stream_events=legal_source_events(legal),
        )
        self.emit(
            run_id,
            stage,
            label,
            agent,
            "completed",
            headline=f"{len(questions)} legal questions and {len(LAW_SOURCES)} official sources linked",
            detail="Every retained source affects at least one process node or evidence requirement.",
            question="Which legal questions shape the complete handling process?",
            items=[
                f"{source['title']}: {source['role']}" for source in legal["sources"]
            ],
            metrics={
                "questions": len(questions),
                "official_sources": len(LAW_SOURCES),
                "handling_principles": 2,
            },
            input_hash=digest(understanding),
            output_hash=digest(legal),
            input_artifacts=["canonical_claim_state"],
            output_artifact="legal_context",
            handoff_to="Process Projection Tool",
            retrieval_method="versioned_official_source_registry_lookup",
        )
        self.pause(0.25)
        return legal

    def _process_stage(
        self,
        run_id: str,
        claim: dict[str, Any],
        understanding: dict[str, Any],
        legal: dict[str, Any],
        memories: list[dict[str, Any]],
        knowledge: dict[str, Any],
    ) -> dict[str, Any]:
        stage, label, agent = VISIBLE_STAGES[3]
        self.emit(
            run_id,
            stage,
            label,
            agent,
            "started",
            headline="Synthesizing the full claim-handling decision graph",
            detail="The deterministic projection instantiates entry checks, factual decisions, evidence loops, remedy branches, escalation and closure.",
            question="How should this claim type be handled from intake to resolution?",
            input_artifacts=["canonical_claim_state", "legal_context"],
            output_artifact="process_graph",
            handoff_to="Evidence Checklist Tool",
        )
        self.pause(0.45)
        later = claim["claim_id"] == "DEMO-MOULD-002"
        notification_answer = "Written notice and receipt established"
        notification_state = "complete"
        node_facts = {
            "scope": ["fact_tenancy"] if not later else ["later_fact_tenancy"],
            "dispute": ["fact_dispute"] if not later else ["later_fact_dispute"],
            "urgency": ["fact_health"] if not later else ["later_fact_health"],
            "notification": ["fact_notification"]
            if not later
            else ["later_fact_notification"],
            "defect": ["fact_recurrence"]
            if not later
            else ["later_fact_recurrence", "later_fact_recent_window_work"],
            "causation": ["fact_cause", "fact_ventilation_allegation"]
            if not later
            else [
                "later_fact_cause",
                "later_fact_ventilation_allegation",
                "later_fact_recent_window_work",
            ],
        }
        branches = [
            {
                "branch_id": "building-defect",
                "label": "Building or installation defect",
                "condition": "Competent evidence supports a building-related cause",
                "target": "building_defect",
                "state": "possible",
            },
            {
                "branch_id": "tenant-use",
                "label": "Use-related cause",
                "condition": "Competent evidence supports a use-related cause",
                "target": "tenant_use",
                "state": "possible",
            },
            {
                "branch_id": "mixed-cause",
                "label": "Mixed contribution",
                "condition": "Evidence supports more than one contributing cause",
                "target": "mixed_cause",
                "state": "possible",
            },
            {
                "branch_id": "insufficient",
                "label": "Evidence still insufficient",
                "condition": "No competent evidence yet distinguishes the plausible causes",
                "target": "evidence_gap",
                "state": "selected",
            },
        ]
        nodes = [
            process_node(
                "intake",
                "Claim intake",
                "Are the message and source files readable and attributable?",
                "complete",
                answer="Yes",
                why="Handling starts from the exact observable package.",
                kind="entry",
                evidence_requirement_ids=["claim_message", "source_integrity"],
            ),
            process_node(
                "scope",
                "Tenant-law scope",
                "Is this a Swiss residential-tenancy matter?",
                "complete",
                answer="Yes",
                why="The applicable process depends on legal scope and jurisdiction.",
                fact_ids=node_facts["scope"],
                legal_source_ids=["fedlex-or-256"],
                evidence_requirement_ids=["lease", "policy_reference"],
                branches=[
                    {
                        "branch_id": "out-of-scope",
                        "label": "Outside scope",
                        "condition": "Observable facts establish a route outside Swiss residential tenancy",
                        "target": "out_of_scope",
                        "state": "possible",
                    },
                    {
                        "branch_id": "scope-unverified",
                        "label": "Scope unverified",
                        "condition": "Observable facts do not yet establish scope",
                        "target": "scope",
                        "state": "possible",
                    },
                ],
            ),
            process_node(
                "dispute",
                "Existence of a dispute",
                "Is there a concrete disagreement requiring legal handling?",
                "complete",
                answer="Yes",
                why="A legal-protection process should not start for a purely advisory or unsupported complaint.",
                fact_ids=node_facts["dispute"],
                evidence_requirement_ids=["customer_objective", "management_position"],
                branches=[
                    {
                        "branch_id": "no-dispute",
                        "label": "No dispute",
                        "condition": "Observable facts establish no concrete disagreement",
                        "target": "no_dispute",
                        "state": "possible",
                    },
                    {
                        "branch_id": "dispute-unverified",
                        "label": "Dispute unverified",
                        "condition": "Observable facts do not establish whether a concrete disagreement exists",
                        "target": "dispute",
                        "state": "possible",
                    },
                ],
            ),
            process_node(
                "urgency",
                "Urgency and safety",
                "Is immediate health, safety or deadline action required?",
                "complete",
                answer="No acute concern reported",
                why="Urgent risks can bypass the ordinary evidence sequence.",
                fact_ids=node_facts["urgency"],
                evidence_requirement_ids=["health_safety_statement"],
                branches=[
                    {
                        "branch_id": "urgent",
                        "label": "Urgent",
                        "condition": "Observable facts establish an acute risk or deadline",
                        "target": "urgent_escalation",
                        "state": "possible",
                    },
                    {
                        "branch_id": "urgency-unverified",
                        "label": "Urgency unverified",
                        "condition": "Observable facts do not establish urgency",
                        "target": "urgency",
                        "state": "possible",
                    },
                ],
            ),
            process_node(
                "notification",
                "Landlord notification",
                "Was the landlord told about the defect?",
                notification_state,
                answer=notification_answer,
                why="Notification affects later remedy and escalation steps.",
                fact_ids=node_facts["notification"],
                legal_source_ids=["fedlex-or-257g"],
                evidence_requirement_ids=["defect_notice", "proof_of_delivery"],
                branches=[
                    {
                        "branch_id": "notice-gap",
                        "label": "Notification gap",
                        "condition": "Notification is absent or unverified",
                        "target": "formal_notice",
                        "state": "possible",
                    }
                ],
            ),
            process_node(
                "defect",
                "Defect and recurrence",
                "Is a recurring condition sufficiently documented?",
                "complete",
                answer="Visible recurrence supported",
                why="The process must distinguish a recurring condition from a one-off observation.",
                fact_ids=node_facts["defect"],
                legal_source_ids=["fedlex-or-256"],
                evidence_requirement_ids=["dated_photos", "recurrence_chronology"],
                branches=[
                    {
                        "branch_id": "recurrence-gap",
                        "label": "Recurrence gap",
                        "condition": "Observable facts do not establish recurrence",
                        "target": "defect",
                        "state": "possible",
                    }
                ],
            ),
            process_node(
                "causation",
                "Causation assessment",
                "What caused the recurring moisture condition?",
                "current",
                answer="Unresolved",
                why="Responsibility and remedy depend on competent evidence that distinguishes plausible causes.",
                fact_ids=node_facts["causation"],
                legal_source_ids=["fedlex-or-256", "handling-causation"],
                evidence_requirement_ids=[
                    "technical_assessment",
                    "moisture_measurements",
                    "building_envelope",
                    "use_evidence",
                ],
                branches=branches,
            ),
            process_node(
                "responsibility",
                "Responsibility",
                "Who is responsible for the established cause?",
                "blocked",
                answer="Waits for causation",
                why="The system must not convert an allegation into responsibility.",
                legal_source_ids=[
                    "fedlex-or-256",
                    "fedlex-or-259a",
                    "handling-causation",
                ],
                evidence_requirement_ids=["technical_assessment", "repair_history"],
            ),
            process_node(
                "remedy",
                "Remedy selection",
                "Which repair, reduction, settlement or other remedy branch applies?",
                "blocked",
                answer="Waits for responsibility",
                why="Remedies follow the supported facts and the customer's objective.",
                legal_source_ids=["fedlex-or-259a"],
                evidence_requirement_ids=[
                    "remediation_plan",
                    "financial_impact",
                    "settlement_proposal",
                ],
            ),
            process_node(
                "escalation",
                "Escalation",
                "Is conciliation or another legal escalation required?",
                "future",
                answer="Not reached",
                why="Escalation becomes relevant only if the supported remedy branch does not resolve the dispute.",
                legal_source_ids=["bwo-conciliation"],
                evidence_requirement_ids=["conciliation_bundle"],
            ),
            process_node(
                "resolution",
                "Resolution and closure",
                "Has the agreed remedy been completed and documented?",
                "future",
                answer="Not reached",
                why="Closure requires a recorded outcome and completion evidence.",
                kind="outcome",
                evidence_requirement_ids=["completion_record"],
            ),
            process_node(
                "out_of_scope",
                "Route outside tenant law",
                "Which service should receive the matter?",
                "inactive",
                answer="Not applicable",
                why="Used only when the scope check fails.",
                kind="outcome",
                main_spine=False,
                activation="scope = no",
            ),
            process_node(
                "no_dispute",
                "Advice or closure",
                "Can the matter be resolved without a legal dispute process?",
                "inactive",
                answer="Not applicable",
                why="Used when no concrete disagreement exists.",
                kind="outcome",
                main_spine=False,
                activation="dispute = no",
            ),
            process_node(
                "urgent_escalation",
                "Immediate protective action",
                "What must happen before ordinary handling continues?",
                "inactive",
                answer="Not applicable",
                why="Used only for acute safety, health or deadline risk.",
                kind="action",
                main_spine=False,
                activation="urgency = yes",
            ),
            process_node(
                "formal_notice",
                "Complete the notification record",
                "What notification or proof gap should be addressed before later remedies are considered?",
                "inactive",
                answer="No current gap",
                why="Notification is relevant; written evidence can help establish it, without treating Article 257g as a statutory writing requirement.",
                kind="action",
                main_spine=False,
                legal_source_ids=["fedlex-or-257g"],
                evidence_requirement_ids=["defect_notice", "proof_of_delivery"],
                activation="notification = no or unverified",
            ),
            process_node(
                "building_defect",
                "Building-defect branch",
                "Which building condition caused the defect and what remediation is required?",
                "unresolved",
                answer="Possible",
                why="Activated only when competent evidence supports a building or installation cause.",
                main_spine=False,
                legal_source_ids=["fedlex-or-256", "fedlex-or-259a"],
                evidence_requirement_ids=[
                    "technical_assessment",
                    "building_envelope",
                    "remediation_plan",
                ],
                activation="causation = building defect",
            ),
            process_node(
                "tenant_use",
                "Use-related branch",
                "Which use factor is supported and what response is proportionate?",
                "unresolved",
                answer="Possible",
                why="Activated only when competent evidence supports a use-related cause.",
                main_spine=False,
                evidence_requirement_ids=["technical_assessment", "use_evidence"],
                activation="causation = tenant use",
            ),
            process_node(
                "mixed_cause",
                "Mixed-cause branch",
                "How should responsibility and remedy reflect multiple contributing causes?",
                "unresolved",
                answer="Possible",
                why="Activated when evidence supports both building and use-related contributions.",
                main_spine=False,
                evidence_requirement_ids=[
                    "technical_assessment",
                    "building_envelope",
                    "use_evidence",
                    "settlement_proposal",
                ],
                activation="causation = mixed",
            ),
            process_node(
                "evidence_gap",
                "Causation evidence loop",
                "Which competent evidence can distinguish the plausible causes?",
                "next",
                answer="Neutral technical assessment first",
                why="The selected interim branch gathers evidence and returns to the causation decision.",
                kind="action",
                main_spine=False,
                legal_source_ids=["handling-causation", "handling-evidence-order"],
                evidence_requirement_ids=[
                    "technical_assessment",
                    "moisture_measurements",
                    "building_envelope",
                ],
                activation="causation = insufficient evidence",
            ),
        ]
        edges = [
            edge("intake", "scope", "source package readable", "selected"),
            edge("scope", "dispute", "tenant-law scope confirmed", "selected"),
            edge("scope", "out_of_scope", "outside tenant law", "inactive"),
            edge("dispute", "urgency", "concrete dispute exists", "selected"),
            edge("dispute", "no_dispute", "no concrete dispute", "inactive"),
            edge("urgency", "urgent_escalation", "acute risk or deadline", "inactive"),
            edge("urgency", "notification", "ordinary handling", "selected"),
            edge(
                "notification",
                "defect",
                "notice established",
                "selected" if not later else "possible",
            ),
            edge(
                "notification",
                "formal_notice",
                "notice missing or unverified",
                "inactive" if not later else "possible",
            ),
            edge("defect", "causation", "recurring condition supported", "selected"),
            edge(
                "causation", "building_defect", "building cause supported", "possible"
            ),
            edge("causation", "tenant_use", "use-related cause supported", "possible"),
            edge("causation", "mixed_cause", "mixed cause supported", "possible"),
            edge("causation", "evidence_gap", "evidence insufficient", "selected"),
            edge("evidence_gap", "causation", "new evidence received", "loop"),
            edge("building_defect", "responsibility", "cause established", "possible"),
            edge("tenant_use", "responsibility", "cause established", "possible"),
            edge(
                "mixed_cause", "responsibility", "contributions established", "possible"
            ),
            edge("responsibility", "remedy", "responsibility established", "blocked"),
            edge("remedy", "resolution", "remedy accepted and completed", "future"),
            edge("remedy", "escalation", "remedy disputed or refused", "future"),
            edge(
                "escalation",
                "resolution",
                "settlement, decision or withdrawal",
                "future",
            ),
        ]
        main_spine = [
            "intake",
            "scope",
            "dispute",
            "urgency",
            "notification",
            "defect",
            "causation",
            "responsibility",
            "remedy",
            "escalation",
            "resolution",
        ]
        projection = decision_projection(understanding["facts"])
        current_overlay = apply_process_projection(nodes, edges, projection, main_spine)
        for node in nodes:
            node["legal_source_ids"] = deepcopy(
                legal.get("node_links", {}).get(node["node_id"], [])
            )

        process = {
            "process_id": f"process-{claim['claim_id'].lower()}",
            "title": "Recurring mould and moisture handling playbook",
            "scope": "claim-specific instance of the mould and moisture process library",
            "nodes": nodes,
            "edges": edges,
            "main_spine": main_spine,
            "current_node": projection["current_node"],
            "selected_path": projection["selected_path"],
            "current_overlay": current_overlay,
            "playbook_version": knowledge["version"],
            "memory_used": False,
            "shared_rule_applied": False,
            "validator": {
                "valid": True,
                "checks": [
                    "one current node",
                    "all selected edges connect",
                    "entry, scope, dispute, evidence, remedy and closure represented",
                    "unknown causation not treated as false",
                    "blocked remedy not marked complete",
                    "every evidence-bearing node has requirement links",
                    "inactive branches remain inspectable but do not control the current claim",
                ],
            },
        }
        self.storage.patch_run(
            run_id,
            patch={
                "process_candidate"
                if self.model_mode == MODEL_MODE_OPENROUTER
                else "process": process
            },
        )
        branch_count = sum(len(node.get("branches", [])) for node in nodes)
        self.emit(
            run_id,
            stage,
            label,
            agent,
            "candidate_prepared"
            if self.model_mode == MODEL_MODE_OPENROUTER
            else "completed",
            headline=f"{len(nodes)} decision and branch nodes proposed",
            detail=f"The full path contains entry checks, {branch_count} causation outcomes, an evidence loop, remedy, escalation and closure.",
            question="How should this claim type be handled from intake to resolution?",
            items=[
                f"{node['title']}: {node['state']}"
                for node in nodes
                if node["main_spine"]
            ],
            metrics={
                "nodes": len(nodes),
                "edges": len(edges),
                "conditional_branches": branch_count + 5,
                "main_spine_nodes": len(main_spine),
            },
            input_hash=digest(
                {
                    "understanding": understanding,
                    "legal": legal,
                    "knowledge": knowledge["version"],
                }
            ),
            output_hash=digest(process),
            input_artifacts=["canonical_claim_state", "legal_context"],
            output_artifact=(
                "candidate_process_graph"
                if self.model_mode == MODEL_MODE_OPENROUTER
                else "process_graph"
            ),
            handoff_to="Evidence Checklist Tool",
            playbook_version=knowledge["version"],
        )
        self.pause(0.25)
        return process

    def _evidence_stage(
        self,
        run_id: str,
        claim: dict[str, Any],
        understanding: dict[str, Any],
        process: dict[str, Any],
        legal: dict[str, Any],
        memories: list[dict[str, Any]],
        knowledge: dict[str, Any],
    ) -> dict[str, Any]:
        stage, label, agent = VISIBLE_STAGES[4]
        self.emit(
            run_id,
            stage,
            label,
            agent,
            "started",
            headline="Deriving evidence requirements across the full graph",
            detail="Each requirement must establish a fact required by a reached or possible process branch.",
            question="What complete evidence model does this process require?",
            input_artifacts=["canonical_claim_state", "legal_context", "process_graph"],
            output_artifact="evidence_model",
            handoff_to="Historical Retrieval Tool",
        )
        self.pause(0.45)
        later = claim["claim_id"] == "DEMO-MOULD-002"

        def item(
            item_id: str,
            title: str,
            status: str,
            node_id: str,
            fact_id: str,
            why: str,
            *,
            legal_basis_ids: list[str] | None = None,
            artifact_ids: list[str] | None = None,
            acceptable_alternatives: list[str] | None = None,
            applies_when: str = "always",
            required_level: str = "mandatory",
        ) -> dict[str, Any]:
            return {
                "item_id": item_id,
                "title": title,
                "status": status,
                "node_id": node_id,
                "fact_id": fact_id,
                "why": why,
                "legal_basis_ids": legal_basis_ids or [],
                "artifact_ids": artifact_ids or [],
                "acceptable_alternatives": acceptable_alternatives or [],
                "applies_when": applies_when,
                "required_level": required_level,
                "current_path": node_id in process["selected_path"]
                or node_id in {"responsibility", "remedy"},
            }

        if not later:
            items = [
                item(
                    "claim_message",
                    "Original claim message",
                    "provided_sufficient",
                    "intake",
                    "fact_customer_objective",
                    "Defines the customer's account, objective and first observable claim state.",
                    artifact_ids=["message"],
                ),
                item(
                    "source_integrity",
                    "Source-file checksums and metadata",
                    "provided_sufficient",
                    "intake",
                    "fact_source_integrity",
                    "Keeps original files distinct from derived representations.",
                    artifact_ids=claim["artifact_ids"],
                ),
                item(
                    "lease",
                    "Residential lease agreement",
                    "provided_sufficient",
                    "scope",
                    "fact_tenancy",
                    "Establishes the parties, premises and residential-tenancy relationship.",
                    legal_basis_ids=["fedlex-or-256"],
                    artifact_ids=["art_lease"],
                ),
                item(
                    "policy_reference",
                    "Policy and routing reference",
                    "provided_sufficient",
                    "scope",
                    "fact_policy_route",
                    "Routes the case to the correct legal-protection workflow without deciding coverage.",
                    artifact_ids=["intake"],
                ),
                item(
                    "customer_objective",
                    "Customer's requested outcome",
                    "provided_sufficient",
                    "dispute",
                    "fact_customer_objective",
                    "Distinguishes a concrete repair dispute from a general advisory question.",
                    artifact_ids=["message"],
                ),
                item(
                    "management_position",
                    "Management reply or refusal",
                    "provided_sufficient",
                    "dispute",
                    "fact_dispute",
                    "Establishes the opposing position and the existence of a concrete disagreement.",
                    artifact_ids=["art_management_reply"],
                ),
                item(
                    "health_safety_statement",
                    "Current health and safety information",
                    "provided_sufficient",
                    "urgency",
                    "fact_health",
                    "Supports the present non-emergency triage while leaving escalation available if facts change.",
                    artifact_ids=["message"],
                ),
                item(
                    "defect_notice",
                    "Evidence of landlord notification",
                    "provided_sufficient",
                    "notification",
                    "fact_notification",
                    "Shows that the landlord was told about the alleged defect; the available evidence happens to be written.",
                    legal_basis_ids=["fedlex-or-257g"],
                    artifact_ids=["art_notification"],
                ),
                item(
                    "proof_of_delivery",
                    "Proof that the notice was received",
                    "provided_sufficient",
                    "notification",
                    "fact_notification",
                    "Supports when and how the written notice reached management.",
                    legal_basis_ids=["fedlex-or-257g"],
                    artifact_ids=["art_delivery"],
                ),
                item(
                    "dated_photos",
                    "Dated photographs of the condition",
                    "provided_sufficient",
                    "defect",
                    "fact_recurrence",
                    "Shows the visible condition and helps establish recurrence, but not technical cause.",
                    artifact_ids=["art_photo"],
                ),
                item(
                    "recurrence_chronology",
                    "Chronology of recurrence and prior action",
                    "provided_insufficient",
                    "defect",
                    "fact_date_conflict",
                    "The chronology supports recurrence but conflicts with the message on the first-observation date.",
                    artifact_ids=["art_timeline"],
                    acceptable_alternatives=[
                        "Corrected chronology",
                        "Clarifying customer statement",
                    ],
                ),
                item(
                    "technical_assessment",
                    "Independent technical assessment",
                    "missing",
                    "causation",
                    "fact_cause",
                    "Competent evidence is needed to distinguish building, use-related and mixed causes before responsibility is assigned.",
                    legal_basis_ids=["fedlex-or-256", "handling-causation"],
                    acceptable_alternatives=[
                        "Independent building-physics report",
                        "Qualified moisture inspection",
                        "Landlord inspection accepted by both parties",
                    ],
                ),
                item(
                    "moisture_measurements",
                    "Moisture and environmental measurements",
                    "conditional",
                    "causation",
                    "fact_cause",
                    "Measurements may support the technical assessment when the source cannot be identified visually.",
                    legal_basis_ids=["handling-causation"],
                    acceptable_alternatives=[
                        "Moisture mapping",
                        "Humidity and surface-temperature log",
                        "Thermal imaging",
                    ],
                    applies_when="The first inspection needs quantitative confirmation",
                    required_level="conditional",
                ),
                item(
                    "building_envelope",
                    "Building-envelope assessment",
                    "conditional",
                    "causation",
                    "fact_cause",
                    "Broader testing is justified only if the neutral first assessment cannot establish the moisture source.",
                    legal_basis_ids=["handling-evidence-order"],
                    acceptable_alternatives=[
                        "Facade inspection",
                        "Window-seal assessment",
                        "Thermal-bridge analysis",
                    ],
                    applies_when="The neutral first assessment is inconclusive or indicates an envelope issue",
                    required_level="conditional",
                ),
                item(
                    "repair_history",
                    "Landlord inspection and repair records",
                    "conditional",
                    "responsibility",
                    "fact_repair_history",
                    "Shows what the landlord investigated or repaired and whether prior action addressed the supported cause.",
                    legal_basis_ids=["fedlex-or-256"],
                    artifact_ids=["art_management_reply"],
                    acceptable_alternatives=[
                        "Inspection report",
                        "Work order",
                        "Contractor correspondence",
                    ],
                    applies_when="The landlord states that inspection or remediation occurred",
                    required_level="conditional",
                ),
                item(
                    "use_evidence",
                    "Use-related evidence",
                    "not_applicable",
                    "tenant_use",
                    "fact_tenant_use_cause",
                    "This becomes relevant only if competent evidence points to ventilation, heating or another use-related factor.",
                    acceptable_alternatives=[
                        "Ventilation log",
                        "Heating records",
                        "Occupancy/use information",
                    ],
                    applies_when="The tenant-use branch becomes supported",
                    required_level="conditional",
                ),
                item(
                    "remediation_plan",
                    "Repair or remediation plan",
                    "not_applicable",
                    "remedy",
                    "fact_remedy_plan",
                    "Needed only after a building-related responsibility branch is supported.",
                    legal_basis_ids=["fedlex-or-259a"],
                    acceptable_alternatives=[
                        "Landlord repair commitment",
                        "Contractor scope of work",
                    ],
                    applies_when="Building responsibility is established",
                    required_level="conditional",
                ),
                item(
                    "financial_impact",
                    "Evidence supporting a financial remedy",
                    "conditional",
                    "remedy",
                    "fact_financial_remedy",
                    "Needed only if the selected remedy includes rent reduction, reimbursement or loss evidence.",
                    legal_basis_ids=["fedlex-or-259a"],
                    acceptable_alternatives=[
                        "Invoices",
                        "Rent records",
                        "Documented loss",
                    ],
                    applies_when="A financial remedy is pursued",
                    required_level="conditional",
                ),
                item(
                    "settlement_proposal",
                    "Settlement proposal and response",
                    "conditional",
                    "remedy",
                    "fact_settlement_proposal",
                    "A settlement record becomes relevant only if the parties negotiate a supported remedy.",
                    legal_basis_ids=["fedlex-or-259a"],
                    acceptable_alternatives=[
                        "Written proposal",
                        "Recorded mediation position",
                    ],
                    applies_when="A settlement branch is pursued",
                    required_level="conditional",
                ),
                item(
                    "conciliation_bundle",
                    "Conciliation evidence bundle",
                    "conditional",
                    "escalation",
                    "fact_escalation_ready",
                    "A concise record of notice, disputed facts, technical evidence and requested remedy supports escalation.",
                    legal_basis_ids=["bwo-conciliation"],
                    acceptable_alternatives=[
                        "Conciliation application with indexed exhibits"
                    ],
                    applies_when="The remedy is refused or remains disputed",
                    required_level="conditional",
                ),
                item(
                    "completion_record",
                    "Repair, settlement or closure record",
                    "not_applicable",
                    "resolution",
                    "fact_resolution_complete",
                    "Closure should record what resolved the claim and whether the agreed action was completed.",
                    acceptable_alternatives=[
                        "Repair completion record",
                        "Settlement",
                        "Decision",
                        "Reasoned closure note",
                    ],
                    applies_when="The claim reaches a terminal outcome",
                    required_level="conditional",
                ),
            ]
        else:
            items = [
                item(
                    "claim_message",
                    "Original claim message",
                    "provided_sufficient",
                    "intake",
                    "later_fact_customer_objective",
                    "Defines the customer's account and objective.",
                    artifact_ids=["art_later_email"],
                ),
                item(
                    "source_integrity",
                    "Source-file checksums and metadata",
                    "provided_sufficient",
                    "intake",
                    "later_fact_source_integrity",
                    "Keeps original files distinct from derived representations.",
                    artifact_ids=claim["artifact_ids"],
                ),
                item(
                    "lease",
                    "Residential lease agreement",
                    "provided_sufficient",
                    "scope",
                    "later_fact_tenancy",
                    "Establishes the parties, premises and residential-tenancy relationship.",
                    legal_basis_ids=["fedlex-or-256"],
                    artifact_ids=["art_later_lease"],
                ),
                item(
                    "policy_reference",
                    "Policy and routing reference",
                    "provided_sufficient",
                    "scope",
                    "later_fact_policy_route",
                    "Routes the case without deciding coverage.",
                    artifact_ids=["intake"],
                ),
                item(
                    "customer_objective",
                    "Customer's requested outcome",
                    "provided_sufficient",
                    "dispute",
                    "later_fact_customer_objective",
                    "Distinguishes the requested guidance from any inferred legal remedy.",
                    artifact_ids=["art_later_email"],
                ),
                item(
                    "management_position",
                    "Original management ventilation allegation",
                    "provided_sufficient",
                    "dispute",
                    "later_fact_dispute",
                    "Establishes management's opposing position, receipt acknowledgement and refusal to inspect.",
                    artifact_ids=["art_later_management_reply"],
                ),
                item(
                    "health_safety_statement",
                    "Current health and safety information",
                    "provided_sufficient",
                    "urgency",
                    "later_fact_health",
                    "Supports the present non-emergency triage.",
                    artifact_ids=["art_later_email"],
                ),
                item(
                    "defect_notice",
                    "Evidence of landlord notification",
                    "provided_sufficient",
                    "notification",
                    "later_fact_notification",
                    "The original notice records what the customer reported and requested; Article 257g does not itself impose a writing form.",
                    legal_basis_ids=["fedlex-or-257g"],
                    artifact_ids=["art_later_notification"],
                ),
                item(
                    "proof_of_delivery",
                    "Evidence that notification reached management",
                    "provided_sufficient",
                    "notification",
                    "later_fact_notification",
                    "Management's reply expressly acknowledges receiving the 3 August notice.",
                    legal_basis_ids=["fedlex-or-257g"],
                    artifact_ids=["art_later_management_reply"],
                ),
                item(
                    "dated_photos",
                    "Dated photograph of the condition",
                    "provided_sufficient",
                    "defect",
                    "later_fact_recurrence",
                    "Shows the visible condition beside the replaced window.",
                    artifact_ids=["art_later_photo"],
                ),
                item(
                    "recurrence_chronology",
                    "Chronology of recurrence",
                    "provided_insufficient",
                    "defect",
                    "later_fact_recurrence",
                    "The dated correspondence and photograph support recurrence and timing but do not provide a complete chronology.",
                    artifact_ids=["art_later_notification", "art_later_photo"],
                    acceptable_alternatives=[
                        "Inspection chronology",
                        "Clarifying customer statement",
                    ],
                ),
                item(
                    "repair_history",
                    "Window replacement completion record",
                    "provided_sufficient",
                    "defect",
                    "later_fact_recent_window_work",
                    "The contractor completion record confirms replacement in May 2026 and makes installation condition relevant to the causation branch.",
                    legal_basis_ids=["fedlex-or-256"],
                    artifact_ids=["art_window_notice"],
                ),
                item(
                    "technical_assessment",
                    "Independent technical assessment",
                    "missing",
                    "causation",
                    "later_fact_cause",
                    "Competent evidence is needed to distinguish seals, insulation, use factors and mixed causes.",
                    legal_basis_ids=["fedlex-or-256", "handling-causation"],
                    acceptable_alternatives=[
                        "Independent moisture inspection",
                        "Building-physics report",
                    ],
                ),
                item(
                    "moisture_measurements",
                    "Moisture and environmental measurements",
                    "conditional",
                    "causation",
                    "later_fact_cause",
                    "Measurements support the assessment when visual inspection is inconclusive.",
                    legal_basis_ids=["handling-causation"],
                    applies_when="The first assessment needs quantitative confirmation",
                    required_level="conditional",
                ),
                item(
                    "building_envelope",
                    "Building-envelope assessment",
                    "missing",
                    "causation",
                    "later_fact_cause",
                    "The unchanged v3 reference requests the broader assessment immediately; no case-specific memory guidance has been applied.",
                    legal_basis_ids=["handling-evidence-order"],
                    applies_when="Immediate under the v3 reference",
                    required_level="mandatory",
                ),
                item(
                    "use_evidence",
                    "Use-related evidence",
                    "conditional",
                    "tenant_use",
                    "later_fact_ventilation_allegation",
                    "Use-related evidence is requested only after competent assessment makes the allegation relevant.",
                    acceptable_alternatives=[
                        "Ventilation record",
                        "Heating data",
                        "Inspection observations",
                    ],
                    applies_when="The neutral assessment leaves a plausible use-related branch",
                    required_level="conditional",
                ),
                item(
                    "remediation_plan",
                    "Repair or remediation plan",
                    "not_applicable",
                    "remedy",
                    "later_fact_remedy_plan",
                    "Needed only after responsibility is supported.",
                    legal_basis_ids=["fedlex-or-259a"],
                    applies_when="Building responsibility is established",
                    required_level="conditional",
                ),
                item(
                    "financial_impact",
                    "Evidence supporting a financial remedy",
                    "conditional",
                    "remedy",
                    "later_fact_financial_remedy",
                    "Needed only if a supported financial remedy is pursued.",
                    legal_basis_ids=["fedlex-or-259a"],
                    applies_when="A financial remedy is pursued",
                    required_level="conditional",
                ),
                item(
                    "settlement_proposal",
                    "Settlement proposal and response",
                    "conditional",
                    "remedy",
                    "later_fact_settlement_proposal",
                    "Relevant only if the parties negotiate a supported remedy.",
                    legal_basis_ids=["fedlex-or-259a"],
                    applies_when="A settlement branch is pursued",
                    required_level="conditional",
                ),
                item(
                    "conciliation_bundle",
                    "Conciliation evidence bundle",
                    "conditional",
                    "escalation",
                    "later_fact_escalation_ready",
                    "Used only if the supported remedy remains disputed.",
                    legal_basis_ids=["bwo-conciliation"],
                    applies_when="Remedy refused or disputed",
                    required_level="conditional",
                ),
                item(
                    "completion_record",
                    "Repair, settlement or closure record",
                    "not_applicable",
                    "resolution",
                    "later_fact_resolution_complete",
                    "Records the terminal outcome.",
                    applies_when="Claim resolved",
                    required_level="conditional",
                ),
            ]
        validate_evidence_item_order(claim["claim_id"], items)
        apply_evidence_relations(process, items)
        apply_evidence_projection(items, process)
        apply_evidence_relations(process, items)
        derived = checklist_derived_sections(items)
        summary = derived["summary"]
        checklist = {
            "title": "Complete process-grounded evidence model",
            "items": items,
            **derived,
            "playbook_version": knowledge["version"],
            "memory_used": False,
            "shared_rule_applied": False,
            "validator": {
                "valid": True,
                "checks": [
                    "every requirement linked to a process node",
                    "every requirement linked to a fact",
                    "every requirement explains why the fact matters",
                    "provided evidence not requested again",
                    "conditionality explicit",
                    "inactive-branch evidence marked conditional or not applicable",
                    "document alternatives preserved",
                ],
            },
        }
        self.storage.patch_run(
            run_id,
            patch={
                "checklist_candidate"
                if self.model_mode == MODEL_MODE_OPENROUTER
                else "checklist": checklist
            },
        )
        self.emit(
            run_id,
            stage,
            label,
            agent,
            "candidate_prepared"
            if self.model_mode == MODEL_MODE_OPENROUTER
            else "completed",
            headline=f"{len(items)} evidence relationships linked to {summary['process_nodes_covered']} process nodes",
            detail=f"{summary['provided_sufficient']} sufficient, {summary['provided_insufficient']} insufficient, {summary['missing']} missing, {summary['conditional']} conditional and {summary['not_applicable']} not currently applicable.",
            question="What complete evidence model does this process require?",
            items=[
                f"{item['title']}: {item['status']} → {item['node_id']}"
                for item in items
            ],
            metrics={"requirements": len(items), **summary},
            input_hash=digest(
                {"process": process, "artifacts": claim["artifact_ids"], "legal": legal}
            ),
            output_hash=digest(checklist),
            input_artifacts=["canonical_claim_state", "legal_context", "process_graph"],
            output_artifact=(
                "candidate_evidence_model"
                if self.model_mode == MODEL_MODE_OPENROUTER
                else "evidence_model"
            ),
            handoff_to="Historical Retrieval Tool",
            playbook_version=knowledge["version"],
        )
        self.pause(0.25)
        return checklist

    def _experience_stage(
        self,
        run_id: str,
        claim: dict[str, Any],
        understanding: dict[str, Any],
        process: dict[str, Any],
        checklist: dict[str, Any],
        memories: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        stage, label, agent = VISIBLE_STAGES[5]
        self.emit(
            run_id,
            stage,
            label,
            agent,
            "started",
            headline="Searching provenance-labelled organizational experience",
            detail="Ranking uses legal question, process branch, unresolved fact and evidence need while preserving each record's review status.",
            question="Which provenance-labelled cases can inform this handling plan?",
            input_artifacts=[
                "canonical_claim_state",
                "process_graph",
                "evidence_model",
            ],
            output_artifact="precedents",
            handoff_to="Whole-Playbook Verification Gate",
        )
        self.pause(0.4)
        ranked = rank_precedents(
            current_claim_id=claim["claim_id"],
            understanding=understanding,
            process=process,
            checklist=checklist,
            memories=memories,
            corpus=HISTORICAL_CASES,
        )
        results = ranked["results"]
        ranking_receipt = ranked["receipt"]
        self.storage.patch_run(
            run_id,
            patch={
                "precedents": results,
                "precedent_ranking": ranking_receipt,
            },
            stream_events=precedent_events(results, ranking_receipt),
        )
        self.emit(
            run_id,
            stage,
            label,
            agent,
            "completed",
            headline=f"{len(results)} provenance-labelled precedents retrieved",
            detail="Each result explains the process branch and evidence lesson while declaring whether it is generated reference data or unverified demo memory.",
            question="Which provenance-labelled cases can inform this handling plan?",
            items=[f"{item['claim_id']}: {item['why_useful']}" for item in results],
            metrics={
                "precedents": len(results),
                "qualified_expert_reviewed": sum(
                    item.get("review_status") == "qualified_expert_reviewed"
                    for item in results
                ),
                "unverified_demo_memory": sum(
                    item.get("review_status") == "unverified_demo_memory"
                    for item in results
                ),
                "generated_reference": sum(
                    item.get("review_status") == "generated_reference"
                    for item in results
                ),
            },
            input_hash=digest({"process": process, "checklist": checklist}),
            output_hash=digest(results),
            input_artifacts=[
                "canonical_claim_state",
                "process_graph",
                "evidence_model",
            ],
            output_artifact="precedents",
            handoff_to="Whole-Playbook Verification Gate",
            ranking_dimensions=[
                "legal question",
                "process branch",
                "unresolved fact",
                "evidence need",
                "declared provenance",
            ],
            ranking_contract=ranking_receipt["contract"],
            ranking_context_hash=ranking_receipt["context_hash"],
            ranking_result_hash=ranking_receipt["result_hash"],
            selected_claim_ids=ranking_receipt["selected_claim_ids"],
        )
        self.pause(0.2)
        return results

    def _apply_case_specific_memory(
        self,
        run_id: str,
        session_id: str,
        claim: dict[str, Any],
        understanding: dict[str, Any],
        legal: dict[str, Any],
        process: dict[str, Any],
        checklist: dict[str, Any],
        precedents: list[dict[str, Any]],
        memories: list[dict[str, Any]],
        precedent_ranking: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        # This store contains only reviewed-case memories. Any malformed or
        # authority-relabelled record is a hard boundary failure, never an
        # instruction that may be silently ignored.
        governed_memories = list(memories)
        eligible: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for memory in governed_memories:
            try:
                source_run = self.storage.get_run(
                    memory.get("source_run_id", ""),
                    session_id=session_id,
                )
                review = self.storage.get_review_for_run(
                    memory.get("source_run_id", ""),
                    session_id=session_id,
                )
                _validate_memory_origin(
                    memory,
                    source_run=source_run,
                    review=review,
                )
                candidate = next(
                    (
                        value
                        for value in self.storage.candidates(session_id=session_id)
                        if value.get("candidate_id") == memory.get("candidate_id")
                    ),
                    None,
                )
                if (
                    not isinstance(candidate, dict)
                    or not isinstance(source_run, dict)
                    or not isinstance(review, dict)
                ):
                    raise ValueError("candidate_origin_missing")
                _validate_candidate_origin(
                    candidate,
                    memory=memory,
                    source_run=source_run,
                    review=review,
                )
            except ValueError as exc:
                raise MemoryApplicationError(str(exc)) from exc
            evaluation = _guidance_eligibility(
                memory["case_specific_guidance"],
                claim_id=claim["claim_id"],
                understanding=understanding,
            )
            if evaluation["eligible"]:
                eligible.append((memory, evaluation))
        if not eligible:
            return None, None
        if len(eligible) != 1:
            raise MemoryApplicationError("ambiguous_applicable_memory")
        memory, eligibility = eligible[0]
        ventilation_fact_id = eligibility.get("facts_hash")
        semantic_facts = _fact_signature(understanding)
        ventilation_fact = semantic_facts.get("management_ventilation_allegation", {})
        expected_ventilation_fact_id = SEMANTIC_FACT_ID_BY_CLAIM.get(
            claim["claim_id"], {}
        ).get("management_ventilation_allegation")
        if (
            ventilation_fact_id != digest(semantic_facts)
            or not isinstance(ventilation_fact.get("fact_id"), str)
            or ventilation_fact.get("fact_id") != expected_ventilation_fact_id
        ):
            raise MemoryApplicationError("semantic_fact_role_binding")
        before = {
            "process_dto_hash": digest(process),
            "checklist_dto_hash": digest(checklist),
            "process_semantic_hash": digest(semantic_process_dto(process)),
            "checklist_semantic_hash": digest(semantic_checklist_dto(checklist)),
        }

        transform = replay_case_specific_memory_transform(
            process,
            checklist,
            ventilation_fact_id=ventilation_fact["fact_id"],
        )
        ventilation_node = transform["ventilation_node"]
        first_edge = transform["first_edge"]
        second_edge = transform["second_edge"]
        removed_from = transform["removed_from"]
        building_before = transform["building_before"]
        use_before = transform["use_before"]
        items = {value["item_id"]: value for value in checklist["items"]}

        reranked = rank_precedents(
            current_claim_id=claim["claim_id"],
            understanding=understanding,
            process=process,
            checklist=checklist,
            memories=memories,
            corpus=HISTORICAL_CASES,
        )
        precedents[:] = reranked["results"]
        precedent_ranking.clear()
        precedent_ranking.update(reranked["receipt"])

        verification = self._verification_report(
            claim,
            understanding,
            legal,
            process,
            checklist,
            precedents,
            precedent_ranking,
            memories,
            allowed_process_extension_node_ids={"ventilation_dispute"},
            allowed_process_extension_edge_pairs={
                ("evidence_gap", "ventilation_dispute"),
                ("ventilation_dispute", "causation"),
            },
        )
        after = {
            "process_dto_hash": digest(process),
            "checklist_dto_hash": digest(checklist),
            "process_semantic_hash": digest(semantic_process_dto(process)),
            "checklist_semantic_hash": digest(semantic_checklist_dto(checklist)),
        }
        process_operations = [
            {
                "operation_id": "add_ventilation_dispute_node",
                "operation": "add_node",
                "node_id": "ventilation_dispute",
                "evidence_requirement_ids": deepcopy(
                    ventilation_node["evidence_requirement_ids"]
                ),
                "after_hash": digest(ventilation_node),
            },
            {
                "operation_id": "add_evidence_gap_to_ventilation_edge",
                "operation": "add_edge",
                "source": "evidence_gap",
                "target": "ventilation_dispute",
                "after_hash": digest(first_edge),
            },
            {
                "operation_id": "add_ventilation_to_causation_edge",
                "operation": "add_edge",
                "source": "ventilation_dispute",
                "target": "causation",
                "after_hash": digest(second_edge),
            },
        ]
        evidence_operations = [
            {
                "operation_id": "condition_building_envelope",
                "operation": "replace_item",
                "item_id": "building_envelope",
                "before_hash": digest(
                    semantic_checklist_dto({"items": [building_before]})["items"][0]
                ),
                "after_hash": digest(items["building_envelope"]),
            },
            {
                "operation_id": "reassign_use_evidence_to_ventilation",
                "operation": "reassign_item",
                "item_id": "use_evidence",
                "removed_from_node_ids": sorted(removed_from),
                "added_to_node_id": "ventilation_dispute",
                "before_hash": digest(
                    semantic_checklist_dto({"items": [use_before]})["items"][0]
                ),
                "after_hash": digest(items["use_evidence"]),
            },
        ]
        receipt = {
            "receipt_type": "memory_application_receipt",
            "contract": MEMORY_RECEIPT_CONTRACT,
            "authority": MEMORY_AUTHORITY,
            "scope": "case_specific_guidance_only",
            "source_memory": {
                "memory_id": memory["memory_id"],
                "claim_id": memory["claim_id"],
                "review_id": memory["review_id"],
                "content_hash": memory["content_hash"],
                "review_status": memory["review_status"],
            },
            "target": {"run_id": run_id, "claim_id": claim["claim_id"]},
            "observable_input_hash": digest(observable_claim_package(claim)),
            "canonical_state_hash": digest(understanding["facts"]),
            "eligibility": eligibility,
            "allowed_operation_ids": list(MEMORY_OPERATION_IDS),
            "applied_operation_ids": list(MEMORY_OPERATION_IDS),
            "process_operations": process_operations,
            "evidence_operations": evidence_operations,
            "before": before,
            "after": after,
            "verification_hash": verification["whole_playbook_hash"],
            "shared_playbook_version": SHARED_PLAYBOOK_VERSION,
            "shared_rule_applied": False,
            "model_acceptance_reused": False,
            "applied": True,
        }
        receipt["application_hash"] = digest(receipt)
        memory_boundary = _memory_application_boundary(
            run_id=run_id,
            claim_id=claim["claim_id"],
            memory=memory,
            before=before,
        )
        try:
            _validate_memory_receipt(
                receipt,
                memory=memory,
                expected_context={
                    "target": receipt["target"],
                    "observable_input_hash": receipt["observable_input_hash"],
                    "canonical_state_hash": receipt["canonical_state_hash"],
                    "eligibility": eligibility,
                    "before": before,
                    "after": after,
                    "verification_hash": verification["whole_playbook_hash"],
                },
            )
        except ValueError as exc:
            raise MemoryApplicationError(str(exc)) from exc
        verification["checks"].append(
            {
                "name": "Bounded case-specific memory application",
                "status": "passed",
                "detail": "The exact unverified-demo memory, eligibility manifest, allowed operations and before/after DTO hashes are receipt-bound.",
            }
        )
        self.storage.patch_run(
            run_id,
            patch={
                "process": process,
                "checklist": checklist,
                "verification": verification,
                "memory_application": receipt,
                "memory_application_boundary": memory_boundary,
                "precedents": precedents,
                "precedent_ranking": precedent_ranking,
            },
        )
        self.storage.add_event(
            run_id,
            {
                "stage": "memory_application",
                "label": "Bounded case-specific memory guidance applied",
                "agent": "Deterministic Memory Application Gate",
                "actor_type": "deterministic_gate",
                "status": "completed",
                "implementation": "deterministic_case_specific_memory_transform",
                "model": None,
                "orchestrator": ORCHESTRATOR,
                "validator": MEMORY_RECEIPT_CONTRACT,
                "prompt_version": None,
                "output_artifact": "case_specific_memory_guidance",
                **deepcopy(receipt),
            },
        )
        return receipt, verification

    def _verification_report(
        self,
        claim: dict[str, Any],
        understanding: dict[str, Any],
        legal: dict[str, Any],
        process: dict[str, Any],
        checklist: dict[str, Any],
        precedents: list[dict[str, Any]],
        precedent_ranking: dict[str, Any] | None = None,
        precedent_memories: list[dict[str, Any]] | None = None,
        *,
        allowed_process_extension_node_ids: set[str] | None = None,
        allowed_process_extension_edge_pairs: set[tuple[str, str]] | None = None,
    ) -> dict[str, Any]:
        effective_understanding = {
            **understanding,
            "category": understanding.get(
                "category", "Rental defect - mould and moisture"
            ),
            "subcategory": understanding.get(
                "subcategory", "Recurring moisture with disputed causation"
            ),
        }
        governed_memories = (
            self.storage.memories()
            if precedent_memories is None
            else precedent_memories
        )
        if precedent_ranking is None:
            precedent_ranking = rank_precedents(
                current_claim_id=claim["claim_id"],
                understanding=effective_understanding,
                process=process,
                checklist=checklist,
                memories=governed_memories,
                corpus=HISTORICAL_CASES,
            )["receipt"]
        checks = validate_playbook(
            claim_id=claim["claim_id"],
            understanding=effective_understanding,
            legal=legal,
            process=process,
            checklist=checklist,
            precedents=precedents,
            precedent_ranking=precedent_ranking,
            precedent_memories=governed_memories,
            precedent_corpus=HISTORICAL_CASES,
            allowed_artifact_ids=set(claim["artifact_ids"]),
            artifact_page_counts={
                artifact_id: int(ARTIFACTS[artifact_id]["page_count"])
                for artifact_id in claim["artifact_ids"]
            },
            artifact_media_types={
                artifact_id: ARTIFACTS[artifact_id]["media_type"]
                for artifact_id in claim["artifact_ids"]
            },
            observable_package=observable_claim_package(claim),
            allowed_process_extension_node_ids=(allowed_process_extension_node_ids),
            allowed_process_extension_edge_pairs=(allowed_process_extension_edge_pairs),
        )
        process_checks = [
            check["name"]
            for check in checks
            if check["name"]
            in {"Graph integrity", "Current-state safety", "Law-to-process linkage"}
        ]
        evidence_checks = [
            check["name"]
            for check in checks
            if check["name"]
            in {
                "Process-to-evidence linkage",
                "Current-state safety",
                "Law-to-process linkage",
            }
        ]
        process["validator"] = {
            "valid": True,
            "computed": True,
            "checks": process_checks,
        }
        checklist["validator"] = {
            "valid": True,
            "computed": True,
            "checks": evidence_checks,
        }
        return {
            "valid": True,
            "computed": True,
            "contract_version": "casepath.playbook-contracts/1.2.0",
            "checks": checks,
            "rejected_proposals": [],
            "accepted_artifacts": [
                "canonical_claim_state",
                "legal_context",
                "process_graph",
                "evidence_model",
                "precedents",
            ],
            "whole_playbook_hash": digest(
                {
                    "understanding": effective_understanding,
                    "legal": legal,
                    "process": process,
                    "checklist": checklist,
                    "precedents": precedents,
                    "precedent_ranking": precedent_ranking,
                }
            ),
        }

    def _verify_stage(
        self,
        run_id: str,
        claim: dict[str, Any],
        understanding: dict[str, Any],
        legal: dict[str, Any],
        process: dict[str, Any],
        checklist: dict[str, Any],
        precedents: list[dict[str, Any]],
        precedent_ranking: dict[str, Any],
        precedent_memories: list[dict[str, Any]],
    ) -> dict[str, Any]:
        stage, label, agent = VISIBLE_STAGES[6]
        self.emit(
            run_id,
            stage,
            label,
            agent,
            "started",
            headline="Checking grounding, graph integrity and evidence links",
            detail="Specialist proposals cannot enter canonical state until deterministic checks pass.",
            question="Is the complete playbook internally consistent and source-grounded?",
            input_artifacts=[
                "canonical_claim_state",
                "legal_context",
                "process_graph",
                "evidence_model",
                "precedents",
            ],
            output_artifact="verification_report",
            handoff_to="LangGraph Orchestration Boundary",
        )
        self.pause(0.35)
        report = self._verification_report(
            claim,
            understanding,
            legal,
            process,
            checklist,
            precedents,
            precedent_ranking,
            precedent_memories,
        )
        checks = report["checks"]
        self.storage.patch_run(
            run_id,
            patch={
                "verification_candidate"
                if self.model_mode == MODEL_MODE_OPENROUTER
                else "verification": report
            },
        )
        self.emit(
            run_id,
            stage,
            label,
            agent,
            "candidate_prepared"
            if self.model_mode == MODEL_MODE_OPENROUTER
            else "completed",
            headline=f"{len(checks)} executable contract checks passed",
            detail="The final graph, sources, facts, evidence relationships and precedent provenance passed the fail-closed contract gate.",
            question="Is the complete playbook internally consistent and source-grounded?",
            items=[f"{item['name']}: {item['status']}" for item in checks],
            metrics={"checks_passed": len(checks), "canonical_artifacts": 5},
            input_hash=digest({"process": process, "checklist": checklist}),
            output_hash=digest(report),
            input_artifacts=[
                "canonical_claim_state",
                "legal_context",
                "process_graph",
                "evidence_model",
                "precedents",
            ],
            output_artifact=(
                "candidate_verification_report"
                if self.model_mode == MODEL_MODE_OPENROUTER
                else "verification_report"
            ),
            handoff_to="LangGraph Orchestration Boundary",
            implementation="deterministic_verification_agent",
            model=None,
        )
        self.pause(0.2)
        return report

    def _agent_orchestration_stage(
        self,
        run_id: str,
        claim: dict[str, Any],
        understanding: dict[str, Any],
        process: dict[str, Any],
        checklist: dict[str, Any],
        verification: dict[str, Any],
        *,
        verification_builder: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]
        | None = None,
    ) -> dict[str, Any]:
        if self.model_mode != MODEL_MODE_OPENROUTER:
            return {
                "executed": False,
                "authority_mode": MODEL_MODE_REFERENCE,
                "model": None,
                "external_tracing": False,
                "deterministic_safety_authority": True,
            }
        if self.agent_orchestrator is None:  # pragma: no cover - constructor invariant
            raise RuntimeError(
                "OpenRouter model mode requires the LangGraph agent orchestrator"
            )
        canonicalization = understanding["canonicalization"]

        def persist_receipt(receipt: dict[str, Any]) -> None:
            actor_type = receipt.get("actor_type")
            is_model = actor_type == "nemotron_agent"
            self.storage.add_event(
                run_id,
                {
                    "stage": "agent_orchestration",
                    "label": receipt.get("role", receipt["agent_id"]),
                    "agent": receipt.get("role", receipt["agent_id"]),
                    "agent_id": receipt["agent_id"],
                    "actor_type": actor_type,
                    "status": receipt["status"],
                    "headline": (
                        "Bounded specialist call failed closed"
                        if receipt["status"] == "failed"
                        else f"{receipt.get('accepted_count', 0)} bounded contributions accepted"
                        if receipt["status"] == "completed" and is_model
                        else "Deterministic contract gate passed"
                        if receipt.get("receipt_type") == "gate_passed"
                        else "Bounded specialist call started"
                    ),
                    "detail": (
                        "Safe call identity and invariant class were retained; prompts, raw output and reasoning were not persisted."
                        if receipt["status"] == "failed"
                        else "Only accepted IDs and artifact hashes are streamed; prompts, raw output and reasoning are not persisted."
                        if is_model
                        else "This gate is application code and is not represented as an AI agent."
                    ),
                    "implementation": MULTI_AGENT_IMPLEMENTATION,
                    "model": OPENROUTER_MODEL if is_model else None,
                    "orchestrator": ORCHESTRATOR,
                    "validator": f"{receipt['agent_id']}-contract/{MULTI_AGENT_VERSION}",
                    "prompt_version": (
                        f"{receipt['agent_id']}/{MULTI_AGENT_VERSION}"
                        if is_model
                        else None
                    ),
                    **{
                        key: receipt[key]
                        for key in (
                            "receipt_type",
                            "acceptance_scope",
                            "delegation_id",
                            "parent_call_id",
                            "call_id",
                            "response_id",
                            "outcome",
                            "provider",
                            "requested_model",
                            "call_count",
                            "response_model",
                            "upstream_provider",
                            "usage_source",
                            "accepted_ids",
                            "accepted_count",
                            "rejected_count",
                            "deterministic_fallback_applied",
                            "source_agent_id",
                            "source_call_id",
                            "handoff_from",
                            "handoff_to",
                            "input_artifact",
                            "input_artifact_hash",
                            "output_artifact",
                            "output_artifact_hash",
                            "output_projection_contract",
                            "final_brief_artifact_hash",
                            "verification_report_hash",
                            "verification_whole_playbook_hash",
                            "error_type",
                            "error_invariant",
                            "invalid_provenance_field",
                            "invalid_provenance_value_hash",
                            "provider_error_code",
                            "provider_boundary",
                            "expected_upstream_provider",
                        )
                        if key in receipt
                    },
                    "external_tracing": False,
                },
            )

        audit = self.agent_orchestrator.invoke(
            run_id=run_id,
            orchestration_id=canonicalization["orchestration_id"],
            observable_package=observable_claim_package(claim),
            canonicalization=canonicalization,
            facts=understanding["facts"],
            process=process,
            checklist=checklist,
            verification=verification,
            verification_builder=verification_builder,
            progress_sink=persist_receipt,
        )
        if audit.get("all_required_agents_contributed") is not True:
            raise RuntimeError(
                "Required Nemotron specialist contribution is incomplete"
            )
        artifacts = audit["specialist_artifacts"]
        agents = {entry["agent_id"]: entry for entry in audit["agents"]}
        accepted_process = apply_process_contribution(
            process,
            artifacts["process_decision_mapping"],
            understanding["facts"],
        )
        process.clear()
        process.update(accepted_process)
        accepted_checklist_template = deepcopy(checklist)
        apply_evidence_relations(process, accepted_checklist_template["items"])
        apply_evidence_projection(accepted_checklist_template["items"], process)
        apply_evidence_relations(process, accepted_checklist_template["items"])
        accepted_checklist_template.update(
            checklist_derived_sections(accepted_checklist_template["items"])
        )
        accepted_checklist = apply_evidence_contribution(
            accepted_checklist_template,
            artifacts["evidence_checklist"],
            candidate_artifact_ids_by_item=_evidence_candidate_artifact_ids(
                {
                    "observable_package": observable_claim_package(claim),
                    "source_integrity": artifacts["document_source_integrity"],
                    "facts": understanding["facts"],
                    "checklist": accepted_checklist_template,
                }
            ),
        )
        checklist.clear()
        checklist.update(accepted_checklist)
        process_fallback_fields = [
            f"{item['fact_id']}.decision_value"
            for item in artifacts["process_decision_mapping"]["decisions"]
            if item["deterministic_fallback_applied"] is True
        ]
        process["agent_contribution"] = {
            "authority": "hybrid_guarded_model_contribution",
            "model_owned_fields": ["decision_value"],
            "deterministic_fallback_fields": process_fallback_fields,
            "deterministic_fallback_count": len(process_fallback_fields),
            "derived_from": "accepted_or_fallback_specialist_artifact",
            "artifact": artifacts["process_decision_mapping"],
            "provenance": _accepted_agent_lineage(agents["process_decision_mapping"]),
            "source_integrity_artifact": artifacts["document_source_integrity"],
            "source_integrity_provenance": _accepted_agent_lineage(
                agents["document_source_integrity"]
            ),
        }
        decision_contributions = {
            item["fact_id"]: item
            for item in artifacts["process_decision_mapping"]["decisions"]
        }
        for node in process["nodes"]:
            bound = [
                decision_contributions[fact_id]
                for fact_id in node.get("fact_ids", [])
                if fact_id in decision_contributions
            ]
            if bound:
                node["agent_decision_contributions"] = bound
        evidence_fallback_fields = sorted(
            contribution["contribution_id"]
            for item in artifacts["evidence_checklist"]["items"]
            for contribution in item["field_contributions"]
            if contribution["deterministic_fallback_applied"] is True
        )
        checklist["agent_contribution"] = {
            "authority": "hybrid_guarded_model_contribution",
            "model_owned_fields": ["status", "artifact_ids"],
            "deterministic_fallback_fields": evidence_fallback_fields,
            "deterministic_fallback_count": len(evidence_fallback_fields),
            "derived_from": "accepted_or_fallback_specialist_artifact",
            "artifact": artifacts["evidence_checklist"],
            "provenance": _accepted_agent_lineage(agents["evidence_checklist"]),
        }
        evidence_contributions = {
            item["item_id"]: item for item in artifacts["evidence_checklist"]["items"]
        }
        for item in checklist["items"]:
            item["agent_contribution"] = evidence_contributions[item["item_id"]][
                "field_contributions"
            ]
        gate_bindings = {
            "deterministic_process_gate": (
                "process_graph",
                process,
                "process_decision_mapping",
            ),
            "deterministic_evidence_gate": (
                "evidence_model",
                checklist,
                "evidence_checklist",
            ),
            "whole_playbook_gate": (
                "verified_claim_playbook",
                audit["final_claim_brief"],
                "final_claim_brief_audit",
            ),
        }
        for gate in audit["deterministic_gates"]:
            output_artifact, artifact_value, source_agent_id = gate_bindings[
                gate["agent_id"]
            ]
            source_agent = agents[source_agent_id]
            accepted_binding = {
                "receipt_type": "accepted_artifact",
                "acceptance_scope": "pre_review_model_output",
                "output_artifact": output_artifact,
                "source_agent_id": source_agent_id,
                "source_call_id": source_agent["call_id"],
                "delegation_id": source_agent.get("delegation_id"),
                "accepted_ids": source_agent.get("accepted_ids", []),
                "accepted_count": source_agent.get("accepted_count", 0),
            }
            if gate["agent_id"] == "whole_playbook_gate":
                # Preserve the graph gate's hash of the complete accepted
                # process+checklist+brief bundle. The model brief is a
                # separate join and must never replace that bundle hash.
                accepted_binding["final_brief_artifact_hash"] = accepted_artifact_hash(
                    artifact_value
                )
                accepted_binding.update(
                    {
                        "output_projection_contract": "casepath.accepted-playbook-projection/1.0.0",
                        "published_process_hash": accepted_artifact_hash(process),
                        "published_checklist_hash": accepted_artifact_hash(checklist),
                        "published_bundle_hash": accepted_artifact_hash(
                            {
                                "process": process,
                                "checklist": checklist,
                                "final_brief": artifact_value,
                            }
                        ),
                    }
                )
            else:
                accepted_binding["output_artifact_hash"] = accepted_artifact_hash(
                    artifact_value
                )
            gate.update(accepted_binding)
        understanding["summary"] = (
            f"{understanding['summary']} Nemotron specialists supplied bounded process decisions, evidence "
            "statuses, artifact selections and final-brief audit fields through a guarded LangGraph DAG; the "
            "application verified every field, applied explicit fallbacks, reprojected the route and checklist, "
            "and retained deterministic acceptance authority."
        )
        self.storage.patch_run(run_id, patch={"agent_orchestration": audit})
        return audit

    def _final_result(
        self,
        claim: dict[str, Any],
        parsed: dict[str, Any],
        understanding: dict[str, Any],
        legal: dict[str, Any],
        process: dict[str, Any],
        checklist: dict[str, Any],
        precedents: list[dict[str, Any]],
        verification: dict[str, Any],
        knowledge: dict[str, Any],
        knowledge_mode: str,
        agent_orchestration: dict[str, Any],
        memory_application: dict[str, Any] | None = None,
        precedent_ranking: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        reviewed_memory_retrieved = any(
            precedent.get("review_status") == "unverified_demo_memory"
            for precedent in precedents
        )
        reviewed_memory_used = memory_application is not None
        current_overlay = process["current_overlay"]
        nodes_by_id = {node["node_id"]: node for node in process["nodes"]}
        current_node_id = current_overlay["current_node_id"]
        next_action_node_id = current_overlay["next_action_node_id"]
        if self.model_mode == MODEL_MODE_OPENROUTER and memory_application is None:
            final_brief = agent_orchestration.get("final_claim_brief")
            if not isinstance(final_brief, dict):
                raise AgentBoundaryError("whole_playbook_gate", "final_brief_binding")
            if (
                final_brief.get("current_node_id") != current_node_id
                or final_brief.get("next_action_node_id") != next_action_node_id
            ):
                raise AgentBoundaryError("whole_playbook_gate", "final_route_binding")
            current_node_id = final_brief["current_node_id"]
            next_action_node_id = final_brief["next_action_node_id"]
        current_node = nodes_by_id[current_node_id]
        next_node = nodes_by_id[next_action_node_id]
        return {
            "claim_id": claim["claim_id"],
            "summary": understanding["summary"],
            "scope": understanding["scope"],
            "category": understanding["category"],
            "subcategory": understanding["subcategory"],
            "dispute": understanding["dispute"],
            "facts": understanding["facts"],
            "issues": understanding["issues"],
            "legal_research": legal,
            "process": process,
            "checklist": checklist,
            "precedents": precedents,
            "precedent_ranking": deepcopy(precedent_ranking),
            "verification": verification,
            "agent_orchestration": agent_orchestration,
            "current_overlay": current_overlay,
            "current_blocker": current_node["question"],
            "why_blocked": current_node["why"],
            "next_action": {
                "title": next_node["title"],
                "detail": next_node["why"],
                "requires_expert_approval": True,
                "process_node_id": next_node["node_id"],
                "agent_brief_contribution": (
                    agent_orchestration.get("final_claim_brief")
                    if memory_application is None
                    else None
                ),
            },
            "playbook": {
                "title": process["title"],
                "version": process["playbook_version"],
                "full_process_nodes": len(process["nodes"]),
                "main_spine_nodes": len(process["main_spine"]),
                "evidence_relationships": len(checklist["items"]),
                "current_claim_overlay": current_overlay,
            },
            "memory_used": reviewed_memory_used,
            "reviewed_memory_used": reviewed_memory_used,
            "reviewed_memory_retrieved": reviewed_memory_retrieved,
            "memory_application": deepcopy(memory_application),
            "shared_rule_applied": False,
            "knowledge": {
                "mode": knowledge_mode,
                "reviewed_memory_used": reviewed_memory_used,
                "reviewed_memory_retrieved": reviewed_memory_retrieved,
                "shared_playbook_version": knowledge["version"],
                "shared_rule_applied": False,
            },
            "audit": {
                "input_hash": parsed["input_hash"],
                "observable_input_hash": digest(observable_claim_package(claim)),
                "canonical_state_hash": digest(understanding["facts"]),
                "profile": (
                    PROFILE
                    if self.model_mode == MODEL_MODE_OPENROUTER
                    else DETERMINISTIC_PROFILE
                ),
                "orchestrator": ORCHESTRATOR,
                "schema": "casepath.claim-handling-playbook/15.2",
                "accepted": verification["valid"],
                "verification_computed": verification.get("computed") is True,
                "canonicalization": understanding.get("canonicalization"),
                "agent_orchestration": agent_orchestration,
                "authority_mode": (
                    MULTI_AGENT_AUTHORITY_MODE
                    if self.model_mode == MODEL_MODE_OPENROUTER
                    else MODEL_MODE_REFERENCE
                ),
                "warnings": [
                    "Fictional generated claim package",
                    "Legal and operational translations require qualified review",
                    "No autonomous customer contact or legal decision",
                    *(
                        [
                            "Case-specific unverified-demo memory transform; pre-transform model acceptance was not reused"
                        ]
                        if memory_application is not None
                        else []
                    ),
                ],
            },
        }

    def review(
        self, run_id: str, payload: dict[str, Any], *, session_id: str = "public"
    ) -> dict[str, Any]:
        decision = payload.get("decision", "approve_with_edit")
        mode = payload.get("building_envelope_mode", "conditional")
        if decision not in {"approve_with_edit", "reject"}:
            raise ValueError("Unsupported review decision")
        if mode not in {"conditional", "required_now"}:
            raise ValueError("Unsupported evidence mode")
        request = {
            "decision": decision,
            "building_envelope_mode": mode,
            "confidence": float(payload.get("confidence", 0.9)),
            "justification": payload.get("justification", "").strip(),
        }
        reviewer = {
            "type": "unverified_demo_user",
            "qualification_status": "not_verified",
        }

        with self.review_lock:
            run = self.storage.get_run(run_id, session_id=session_id)
            if not run or run.get("status") != "complete":
                raise ValueError("A completed analysis is required")
            if run["claim_id"] != "DEF-027-E0-DEMO":
                raise ValueError("The public lifecycle demo reviews the flagship claim")
            existing = self.storage.get_review_for_run(run_id, session_id=session_id)
            if existing:
                if existing.get("request") == request and isinstance(
                    existing.get("response"), dict
                ):
                    return deepcopy(existing["response"])
                raise ValueError("This run already has a different review")

            original_result = deepcopy(run["result"])
            if decision == "reject":
                response = {
                    "accepted": False,
                    "review_id": None,
                    "memory_id": None,
                    "reviewer": reviewer,
                    "candidate": None,
                    "result": original_result,
                    "review": {"decision": decision, "operations": []},
                    "changes": {
                        "process_nodes": {
                            "before": len(original_result["process"]["nodes"]),
                            "after": len(original_result["process"]["nodes"]),
                            "added": [],
                        },
                        "evidence_relationships": {
                            "before": len(original_result["checklist"]["items"]),
                            "after": len(original_result["checklist"]["items"]),
                            "changed": [],
                        },
                    },
                    "knowledge": {
                        "reviewed_memory_available": False,
                        "shared_playbook_version": "mould-playbook-v3",
                        "candidate_status": None,
                        "shared_knowledge_changed": False,
                    },
                }
                review_id = self.storage.save_review(
                    run_id,
                    run["claim_id"],
                    {"request": request, "reviewer": reviewer, "accepted": False},
                    session_id=session_id,
                )
                response["review_id"] = review_id
                self.storage.update_review(
                    review_id,
                    {
                        "request": request,
                        "reviewer": reviewer,
                        "accepted": False,
                        "response": response,
                    },
                    session_id=session_id,
                )
                self.storage.patch_run(
                    run_id, patch={"review_id": review_id, "review_response": response}
                )
                self.storage.add_event(
                    run_id,
                    {
                        "stage": "review",
                        "label": "Generated-demo review rejected",
                        "agent": "Demo Review Boundary",
                        "status": "completed",
                        "headline": "No memory, candidate, or shared knowledge was created",
                        "detail": "The original computed result remains unchanged.",
                        "implementation": "unverified_demo_review",
                        "model": None,
                        "orchestrator": ORCHESTRATOR,
                        "validator": "review-contract/15.2",
                        "prompt_version": None,
                        "input_artifacts": ["claim_handling_playbook", "demo_review"],
                        "output_artifact": "rejected_review_record",
                    },
                )
                return response

            result = deepcopy(original_result)
            process = result["process"]
            checklist = result["checklist"]
            process_before = len(process["nodes"])
            evidence_before = len(checklist["items"])
            operations: list[ReviewOperation] = []

            ventilation_node = process_node(
                "ventilation_dispute",
                "Test the ventilation allegation",
                "What exactly is alleged, and does competent evidence support it?",
                "possible",
                answer="Preserve as disputed; test only when competent assessment leaves a plausible use-related branch",
                why="Unverified demo edit: represent the allegation as a question, not as established technical cause.",
                kind="action",
                main_spine=False,
                fact_ids=[
                    SEMANTIC_FACT_ID_BY_CLAIM[run["claim_id"]][
                        "management_ventilation_allegation"
                    ]
                ],
                legal_source_ids=["handling-causation", "handling-evidence-order"],
                evidence_requirement_ids=["management_position", "use_evidence"],
                activation="recurrence + ventilation allegation + cause unresolved",
            )
            process["nodes"].append(ventilation_node)
            operations.append(
                {
                    "component": "process_graph",
                    "operation": "add",
                    "pointer": "/nodes/ventilation_dispute",
                    "old_value": None,
                    "new_value": ventilation_node,
                    "reason": "Keep the reported ventilation allegation explicit and unresolved.",
                }
            )
            for node in process["nodes"]:
                if node["node_id"] == "ventilation_dispute":
                    continue
                if "use_evidence" in node.get("evidence_requirement_ids", []):
                    before_requirements = deepcopy(node["evidence_requirement_ids"])
                    node["evidence_requirement_ids"] = [
                        value
                        for value in node["evidence_requirement_ids"]
                        if value != "use_evidence"
                    ]
                    operations.append(
                        {
                            "component": "process_graph",
                            "operation": "replace",
                            "pointer": f"/nodes/{node['node_id']}/evidence_requirement_ids",
                            "old_value": before_requirements,
                            "new_value": deepcopy(node["evidence_requirement_ids"]),
                            "reason": "Reassign the conditional use-evidence relationship to the explicit allegation question.",
                        }
                    )
            for value in (
                edge(
                    "evidence_gap",
                    "ventilation_dispute",
                    "neutral inspection leaves a plausible use-related factor",
                    "possible",
                ),
                edge(
                    "ventilation_dispute",
                    "causation",
                    "allegation evidence assessed",
                    "loop",
                ),
            ):
                process["edges"].append(value)
                operations.append(
                    {
                        "component": "process_graph",
                        "operation": "add",
                        "pointer": f"/edges/{value['source']}->{value['target']}",
                        "old_value": None,
                        "new_value": value,
                        "reason": "Connect the proposed question without changing the selected path.",
                    }
                )

            changed_evidence: list[str] = []
            for evidence in checklist["items"]:
                if evidence["item_id"] == "building_envelope":
                    before = deepcopy(evidence)
                    evidence["status"] = (
                        "conditional" if mode == "conditional" else "missing"
                    )
                    evidence["required_level"] = (
                        "conditional" if mode == "conditional" else "mandatory"
                    )
                    evidence["applies_when"] = (
                        "The neutral first assessment is inconclusive or indicates an envelope issue"
                        if mode == "conditional"
                        else "Immediate in this unverified demo edit"
                    )
                    evidence["why"] = (
                        "Unverified demo edit: broader building-envelope testing remains conditional on the first competent assessment."
                        if mode == "conditional"
                        else "Unverified demo edit: retain broader building-envelope testing as an immediate request."
                    )
                    if evidence != before:
                        changed_evidence.append(evidence["item_id"])
                        operations.append(
                            {
                                "component": "evidence_model",
                                "operation": "replace",
                                "pointer": "/items/building_envelope",
                                "old_value": before,
                                "new_value": deepcopy(evidence),
                                "reason": "Apply the selected generated-demo evidence-order edit.",
                            }
                        )
                elif evidence["item_id"] == "use_evidence":
                    before = deepcopy(evidence)
                    evidence["status"] = "conditional"
                    evidence["required_level"] = "conditional"
                    evidence["applies_when"] = (
                        "A competent assessment leaves a plausible use-related branch"
                    )
                    evidence["why"] = (
                        "Unverified demo edit: use-related evidence becomes relevant only after competent assessment leaves a plausible use-related branch."
                    )
                    changed_evidence.append(evidence["item_id"])
                    operations.append(
                        {
                            "component": "evidence_model",
                            "operation": "replace",
                            "pointer": "/items/use_evidence",
                            "old_value": before,
                            "new_value": deepcopy(evidence),
                            "reason": "Move the conditional request to the explicit allegation question.",
                        }
                    )

            apply_evidence_relations(process, checklist["items"])
            apply_evidence_projection(checklist["items"], process)
            apply_evidence_relations(process, checklist["items"])
            reviewed_items = {value["item_id"]: value for value in checklist["items"]}
            for operation in operations:
                if operation["component"] != "evidence_model":
                    continue
                item_id = operation["pointer"].rsplit("/", 1)[-1]
                operation["new_value"] = deepcopy(reviewed_items[item_id])
            checklist.update(checklist_derived_sections(checklist["items"]))
            strip_model_contribution_attribution(process, checklist)
            result["next_action"]["agent_brief_contribution"] = None
            review_ranking = rank_precedents(
                current_claim_id=run["claim_id"],
                understanding={
                    "facts": result["facts"],
                    "category": result["category"],
                    "subcategory": result["subcategory"],
                },
                process=process,
                checklist=checklist,
                memories=self.storage.memories(session_id=session_id),
                corpus=HISTORICAL_CASES,
            )
            result["precedents"] = review_ranking["results"]
            result["precedent_ranking"] = review_ranking["receipt"]
            process["playbook_version"] = "mould-playbook-v3"
            checklist["playbook_version"] = "mould-playbook-v3"
            result["playbook"]["version"] = "mould-playbook-v3"
            result["playbook"]["full_process_nodes"] = len(process["nodes"])
            result["playbook"]["evidence_relationships"] = len(checklist["items"])
            result["next_action"]["detail"] = (
                "Arrange one neutral technical assessment first; keep building-envelope and use-related evidence conditional on what it finds."
                if mode == "conditional"
                else "Arrange a neutral technical assessment and retain the broader building-envelope request in this unverified demo edit."
            )
            review_record = {
                **request,
                "reviewer": reviewer,
                "operations": operations,
                "authority": MEMORY_AUTHORITY,
            }
            result["review"] = review_record
            result["knowledge"] = {
                "mode": result.get("knowledge", {}).get("mode", "current"),
                "reviewed_memory_used": False,
                "shared_playbook_version": "mould-playbook-v3",
                "shared_rule_applied": False,
            }
            result["reviewed_memory_used"] = False
            result["shared_rule_applied"] = False
            review_operation_checks = validate_review_operations(operations)
            verification = self._verification_report(
                CLAIMS[run["claim_id"]],
                {
                    "facts": result["facts"],
                    "category": result["category"],
                    "subcategory": result["subcategory"],
                },
                result["legal_research"],
                process,
                checklist,
                result["precedents"],
                result["precedent_ranking"],
                self.storage.memories(session_id=session_id),
                allowed_process_extension_node_ids={"ventilation_dispute"},
                allowed_process_extension_edge_pairs={
                    ("evidence_gap", "ventilation_dispute"),
                    ("ventilation_dispute", "causation"),
                },
            )
            verification["checks"].extend(review_operation_checks)
            verification["review_operations_hash"] = digest(operations)
            result["verification"] = verification
            result["audit"]["accepted"] = verification["valid"]
            result["audit"]["verification_computed"] = verification["computed"]
            for gate in result.get("agent_orchestration", {}).get(
                "deterministic_gates", []
            ):
                if gate.get("receipt_type") == "accepted_artifact":
                    gate["acceptance_scope"] = "pre_review_model_output"
            review_transform = {
                "acceptance_scope": "post_review_unverified_transform",
                "authority": reviewer["type"],
                "qualification_status": reviewer["qualification_status"],
                "input_run_id": run_id,
                "input_process_hash": digest(original_result["process"]),
                "input_checklist_hash": digest(original_result["checklist"]),
                "output_process_hash": digest(process),
                "output_checklist_hash": digest(checklist),
                "model_acceptance_reused": False,
            }
            result["review_transform"] = review_transform
            result["audit"]["review_transform"] = review_transform

            review_id = self.storage.ident("review")
            existing_memory = next(
                (
                    value
                    for value in self.storage.memories(session_id=session_id)
                    if value.get("claim_id") == run["claim_id"]
                ),
                None,
            )
            memory_id = (
                existing_memory["memory_id"]
                if existing_memory is not None
                else self.storage.ident("memory")
            )
            candidate_id = "candidate_disputed_ventilation_v4"
            guidance = _review_guidance_contract(
                claim_id=run["claim_id"],
                category=result["category"],
                subcategory=result["subcategory"],
                building_envelope_mode=mode,
            )
            supporting_claims = sorted(
                {
                    value["claim_id"]
                    for value in self.storage.memories(session_id=session_id)
                    if value.get("candidate_id") == candidate_id
                    and value.get("review_status") == "unverified_demo_memory"
                }
                | {run["claim_id"]}
            )
            target_tests, protected_regression = _governance_test_report(
                guidance,
                protected_output_context=_protected_output_context_from_result(
                    original_result
                ),
            )
            candidate = {
                "candidate_id": candidate_id,
                "title": "Candidate disputed-ventilation evidence-order branch",
                "status": "quarantined",
                "supporting_claims": supporting_claims,
                "support_count": len(supporting_claims),
                "required_support": 3,
                "qualified_support_count": 0,
                "required_qualified_support": 3,
                "support_authority": "unverified_demo_only",
                "base_version": "mould-playbook-v3",
                "proposed_version": "mould-playbook-v4",
                "previous_version": "mould-playbook-v3",
                "new_version": "mould-playbook-v4",
                "proposed_change": (
                    "Represent the disputed ventilation allegation explicitly and make broader testing conditional on a neutral first assessment."
                    if mode == "conditional"
                    else "Represent the disputed ventilation allegation explicitly while retaining immediate broader testing."
                ),
                "delta": {
                    "process_nodes_added": 1,
                    "edges_added": 2,
                    "evidence_relationships_changed": len(changed_evidence),
                    "node_ids": ["ventilation_dispute"],
                    "evidence_item_ids": changed_evidence,
                },
                "target_tests": target_tests,
                "protected_regression": protected_regression,
                "approval": {"status": "pending", "qualified_reviewer": False},
                "shared_knowledge_changed": False,
                "rollback_target": "mould-playbook-v3",
                "provenance": "one unverified generated-demo review",
            }
            result["knowledge_update"] = deepcopy(candidate)
            result["knowledge"]["reviewed_memory_available"] = True
            result["knowledge"]["candidate_status"] = "quarantined"
            result["knowledge"]["shared_knowledge_changed"] = False
            memory = {
                "title": "Generated-demo edit: disputed ventilation allegation and evidence ordering",
                "memory_contract": MEMORY_CONTRACT,
                "authority": MEMORY_AUTHORITY,
                "scope": "case_specific_guidance_only",
                "review_status": "unverified_demo_memory",
                "reviewer": reviewer,
                "source_run_id": run_id,
                "review_id": review_id,
                "candidate_id": candidate_id,
                "category": result["category"],
                "current_blocker": result["current_blocker"],
                "canonical_facts": deepcopy(result["facts"]),
                "reviewed_process": deepcopy(process),
                "reviewed_checklist": deepcopy(checklist),
                "final_process": [node["title"] for node in process["nodes"]],
                "final_checklist": [
                    {
                        "title": evidence["title"],
                        "status": evidence["status"],
                        "why": evidence["why"],
                        "node_id": evidence["node_id"],
                    }
                    for evidence in checklist["items"]
                ],
                "verification": deepcopy(verification),
                "operations": deepcopy(operations),
                "next_action": deepcopy(result["next_action"]),
                "reviewer_explanation": request["justification"],
                "confidence": request["confidence"],
                "playbook_version": "mould-playbook-v3",
                "source_result_hash": digest(original_result),
                "reviewed_result_hash": digest(result),
                "shared_rule_authority": False,
                "case_specific_guidance": guidance,
            }
            memory["content_hash"] = _memory_content_hash(memory)
            changes = {
                "process_nodes": {
                    "before": process_before,
                    "after": len(process["nodes"]),
                    "added": ["ventilation_dispute"],
                },
                "evidence_relationships": {
                    "before": evidence_before,
                    "after": len(checklist["items"]),
                    "changed": changed_evidence,
                },
            }
            response = {
                "accepted": True,
                "review_id": review_id,
                "memory_id": memory_id,
                "reviewer": reviewer,
                "candidate": candidate,
                "result": result,
                "review": review_record,
                "verification": verification,
                "changes": changes,
                "review_transform": review_transform,
                "knowledge": {
                    "reviewed_memory_available": True,
                    "shared_playbook_version": "mould-playbook-v3",
                    "candidate_status": "quarantined",
                    "shared_knowledge_changed": False,
                },
            }
            review_event = {
                "stage": "review",
                "label": "Unverified generated-demo edit recorded",
                "agent": "Demo Review Boundary",
                "actor_type": "deterministic_gate",
                "status": "completed",
                "headline": f"{len(operations)} typed operations passed post-review verification",
                "detail": "The reviewed result is retrievable as unverified demo memory; its candidate remains quarantined and shared playbook v3 is unchanged.",
                "implementation": "unverified_demo_review",
                "model": None,
                "orchestrator": ORCHESTRATOR,
                "validator": "review-contract/15.2",
                "prompt_version": None,
                "input_artifacts": ["claim_handling_playbook", "demo_review"],
                "output_artifact": "unverified_demo_memory",
                "receipt_type": "review_transform",
                **review_transform,
                "metrics": {
                    "support_count": candidate["support_count"],
                    "required_support": candidate["required_support"],
                    "shared_knowledge_changed": False,
                },
            }
            consolidation_event = {
                "stage": "consolidate",
                "label": "Unverified case memory consolidated under governance",
                "agent": "Deterministic Knowledge Consolidation Gate",
                "actor_type": "deterministic_gate",
                "status": "completed",
                "headline": "Case memory stored and candidate quarantined",
                "detail": "One unverified-demo case memory and its deterministic test manifests were stored atomically; qualified approval remains pending and shared v3 is unchanged.",
                "implementation": "deterministic_knowledge_consolidation",
                "model": None,
                "orchestrator": ORCHESTRATOR,
                "validator": "knowledge-consolidation/1.0.0",
                "prompt_version": None,
                "receipt_type": "knowledge_consolidation_receipt",
                "authority": MEMORY_AUTHORITY,
                "qualification_status": "not_verified",
                "output_artifact": "unverified_demo_memory_and_quarantined_candidate",
                "memory_id": memory_id,
                "memory_content_hash": memory["content_hash"],
                "candidate_id": candidate_id,
                "candidate_hash": digest(candidate),
                "target_tests_manifest_hash": candidate["target_tests"][
                    "manifest_hash"
                ],
                "protected_regression_manifest_hash": candidate["protected_regression"][
                    "manifest_hash"
                ],
                "approval_status": "pending",
                "qualified_reviewer": False,
                "shared_playbook_version": SHARED_PLAYBOOK_VERSION,
                "shared_knowledge_changed": False,
            }
            self.storage.persist_review_learning_bundle(
                run_id=run_id,
                claim_id=run["claim_id"],
                session_id=session_id,
                review_id=review_id,
                review_payload={
                    "request": request,
                    "reviewer": reviewer,
                    "accepted": True,
                    "pre_review_result_hash": digest(original_result),
                    "protected_output_snapshot": deepcopy(original_result),
                    "response": response,
                },
                memory_id=memory_id,
                memory_payload=memory,
                candidate_id=candidate_id,
                candidate_payload=candidate,
                run_patch={
                    "result": result,
                    "review_id": review_id,
                    "memory_id": memory_id,
                    "candidate": candidate,
                    "review_response": response,
                    "pre_review_result_hash": digest(original_result),
                },
                events=[review_event, consolidation_event],
            )
            return response

    def _active_knowledge(self, *, session_id: str = "public") -> dict[str, Any]:
        return {
            "version": "mould-playbook-v3",
            "previous_version": "mould-playbook-v2",
            "status": "current_reference",
            "candidate": None,
            "shared_knowledge_changed": False,
            "qualified_release_evidence": False,
        }

    def knowledge(self, *, session_id: str = "public") -> dict[str, Any]:
        active = self._active_knowledge(session_id=session_id)
        versions = [
            {
                "version": "mould-playbook-v3",
                "status": "current_reference",
                "description": "General recurring-mould process without an explicit disputed-ventilation evidence-order branch.",
                "qualified_review_status": "pending",
            }
        ]
        memories = self.storage.memories(session_id=session_id)
        candidates = self.storage.candidates(session_id=session_id)
        candidates_by_id = {value.get("candidate_id"): value for value in candidates}
        if len(candidates_by_id) != len(candidates):
            raise MemoryApplicationError("knowledge_candidate_identity")
        for memory in memories:
            source_run = self.storage.get_run(
                memory.get("source_run_id", ""), session_id=session_id
            )
            review = self.storage.get_review_for_run(
                memory.get("source_run_id", ""), session_id=session_id
            )
            try:
                _validate_memory_origin(memory, source_run=source_run, review=review)
                candidate = candidates_by_id.get(memory.get("candidate_id"))
                if (
                    candidate is None
                    or not isinstance(source_run, dict)
                    or not isinstance(review, dict)
                ):
                    raise ValueError("knowledge_candidate_missing")
                _validate_candidate_origin(
                    candidate,
                    memory=memory,
                    source_run=source_run,
                    review=review,
                )
            except ValueError as exc:
                raise MemoryApplicationError("knowledge_integrity") from exc
        if set(candidates_by_id) != {memory.get("candidate_id") for memory in memories}:
            raise MemoryApplicationError("knowledge_orphan_candidate")
        return {
            "active_playbook": active,
            "playbook_versions": versions,
            "memories": [self._public_memory(value) for value in memories],
            "candidates": [self._public_candidate(value) for value in candidates],
            "shared_knowledge_changed": False,
        }

    @staticmethod
    def _public_memory(memory: dict[str, Any]) -> dict[str, Any]:
        guidance = memory["case_specific_guidance"]
        eligibility = guidance["eligibility"]
        return {
            "memory_id": memory["memory_id"],
            "title": memory["title"],
            "memory_contract": memory["memory_contract"],
            "authority": memory["authority"],
            "scope": memory["scope"],
            "review_status": memory["review_status"],
            "reviewer_qualification_status": memory["reviewer"]["qualification_status"],
            "category": memory["category"],
            "playbook_version": memory["playbook_version"],
            "shared_rule_authority": memory["shared_rule_authority"],
            "candidate_id": memory["candidate_id"],
            "guidance": {
                "contract": guidance["contract"],
                "variant": guidance["variant"],
                "enabled": guidance["enabled"],
                "authority": guidance["authority"],
                "scope": guidance["scope"],
                "eligibility_contract": eligibility["contract"],
                "semantic_signature_hash": eligibility["semantic_signature_hash"],
                "allowed_operation_ids": deepcopy(guidance["allowed_operation_ids"]),
            },
            "updated_at": memory["updated_at"],
        }

    @staticmethod
    def _public_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
        test_fields = ("status", "passed", "failed", "manifest_hash")
        return {
            key: deepcopy(candidate[key])
            for key in (
                "candidate_id",
                "title",
                "status",
                "support_count",
                "required_support",
                "qualified_support_count",
                "required_qualified_support",
                "support_authority",
                "base_version",
                "proposed_version",
                "proposed_change",
                "delta",
                "approval",
                "shared_knowledge_changed",
                "rollback_target",
                "provenance",
            )
        } | {
            "target_tests": {
                key: candidate["target_tests"][key] for key in test_fields
            },
            "protected_regression": {
                key: candidate["protected_regression"][key] for key in test_fields
            },
        }

    def _learning_snapshot(
        self, run: dict[str, Any], *, session_id: str
    ) -> dict[str, Any]:
        result = run["result"]
        claim_id = run.get("claim_id")
        claim = CLAIMS.get(claim_id)
        if claim is None or result.get("claim_id") != claim_id:
            raise MemoryApplicationError("memory_proof_claim_binding")
        understanding = run.get("understanding")
        if (
            not isinstance(understanding, dict)
            or result.get("facts") != understanding.get("facts")
            or result.get("category") != understanding.get("category")
            or result.get("subcategory") != understanding.get("subcategory")
        ):
            raise MemoryApplicationError("memory_proof_canonical_artifact_binding")
        observable_input_hash = digest(observable_claim_package(claim))
        canonical_state_hash = digest(understanding["facts"])
        audit = result.get("audit", {})
        if (
            audit.get("observable_input_hash") != observable_input_hash
            or audit.get("canonical_state_hash") != canonical_state_hash
        ):
            raise MemoryApplicationError("memory_proof_run_integrity")
        retained_memory_ids = {
            value.get("memory_id")
            for value in result.get("precedents", [])
            if value.get("review_status") == "unverified_demo_memory"
        }
        governed_memories = [
            value
            for value in self.storage.memories(session_id=session_id)
            if value.get("memory_id") in retained_memory_ids
        ]
        if {
            value.get("memory_id") for value in governed_memories
        } != retained_memory_ids:
            raise MemoryApplicationError("memory_proof_precedent_source")
        has_memory_application = isinstance(result.get("memory_application"), dict)
        process_copy = deepcopy(result["process"])
        checklist_copy = deepcopy(result["checklist"])
        try:
            proof_understanding = deepcopy(understanding)
            for key in (
                "summary",
                "scope",
                "category",
                "subcategory",
                "dispute",
                "facts",
                "issues",
            ):
                proof_understanding[key] = deepcopy(result[key])
            recomputed_verification = self._verification_report(
                claim,
                proof_understanding,
                deepcopy(result["legal_research"]),
                process_copy,
                checklist_copy,
                deepcopy(result["precedents"]),
                deepcopy(result["precedent_ranking"]),
                deepcopy(governed_memories),
                allowed_process_extension_node_ids=(
                    {"ventilation_dispute"} if has_memory_application else None
                ),
                allowed_process_extension_edge_pairs=(
                    {
                        ("evidence_gap", "ventilation_dispute"),
                        ("ventilation_dispute", "causation"),
                    }
                    if has_memory_application
                    else None
                ),
            )
        except (ContractValidationError, KeyError, TypeError, ValueError) as exc:
            raise MemoryApplicationError("memory_proof_playbook_integrity") from exc
        expected_checks = deepcopy(recomputed_verification["checks"])
        if has_memory_application:
            expected_checks.append(
                {
                    "name": "Bounded case-specific memory application",
                    "status": "passed",
                    "detail": "The exact unverified-demo memory, eligibility manifest, allowed operations and before/after DTO hashes are receipt-bound.",
                }
            )
        stored_verification = result.get("verification", {})
        verification_valid = (
            stored_verification.get("valid") is True
            and stored_verification.get("computed") is True
            and stored_verification.get("checks") == expected_checks
            and stored_verification.get("whole_playbook_hash")
            == recomputed_verification["whole_playbook_hash"]
            and stored_verification.get("accepted_artifacts")
            == recomputed_verification["accepted_artifacts"]
            and stored_verification.get("rejected_proposals")
            == recomputed_verification["rejected_proposals"]
            and result.get("audit", {}).get("accepted") is True
            and result.get("audit", {}).get("verification_computed") is True
        )
        snapshot = {
            "run_id": run["run_id"],
            "completed_at": run.get("completed_at"),
            "result_hash": digest(result),
            "verification_hash": result["verification"]["whole_playbook_hash"],
            "verification_valid": verification_valid,
            "observable_input_hash": observable_input_hash,
            "canonical_state_hash": canonical_state_hash,
            "process_dto_hash": digest(result["process"]),
            "checklist_dto_hash": digest(result["checklist"]),
            "process_semantic_hash": digest(semantic_process_dto(result["process"])),
            "checklist_semantic_hash": digest(
                semantic_checklist_dto(result["checklist"])
            ),
            "process_node_ids": [
                node["node_id"] for node in result["process"]["nodes"]
            ],
            "process_edge_pairs": [
                [value["source"], value["target"]]
                for value in result["process"]["edges"]
            ],
            "current_node_id": result["process"]["current_node"],
            "required_now_item_ids": [
                item["item_id"]
                for item in result["checklist"]["required"]
                if item["status"] == "still_needed"
            ],
            "conditional_item_ids": [
                item["item_id"]
                for item in result["checklist"]["required"]
                if item["status"] == "conditional"
            ],
            "precedents": [
                {
                    "claim_id": item["claim_id"],
                    "memory_id": item.get("memory_id"),
                    "review_status": item["review_status"],
                }
                for item in result["precedents"]
            ],
            "reviewed_memory_used": result.get("reviewed_memory_used") is True,
            "memory_application": deepcopy(result.get("memory_application")),
            "shared_rule_applied": result.get("shared_rule_applied") is True,
            "playbook_version": result["playbook"]["version"],
        }
        if set(snapshot) != LEARNING_SNAPSHOT_FIELDS:
            raise MemoryApplicationError("memory_proof_snapshot_contract")
        return snapshot

    def learning_proof(
        self, baseline_run_id: str, later_run_id: str, *, session_id: str = "public"
    ) -> dict[str, Any]:
        if baseline_run_id == later_run_id:
            raise ValueError("Learning proof requires two distinct completed runs")
        baseline_run = self.storage.get_run(baseline_run_id, session_id=session_id)
        later_run = self.storage.get_run(later_run_id, session_id=session_id)
        if not baseline_run or not later_run:
            raise ValueError("Both bound runs must exist")
        if (
            baseline_run.get("status") != "complete"
            or later_run.get("status") != "complete"
        ):
            raise ValueError("Both bound runs must be complete")
        if (
            baseline_run.get("claim_id") != "DEMO-MOULD-002"
            or later_run.get("claim_id") != "DEMO-MOULD-002"
        ):
            raise ValueError("Both bound runs must analyze the later demo claim")
        if baseline_run.get("knowledge_mode") != "baseline":
            raise ValueError("The baseline run must use baseline knowledge mode")
        if later_run.get("knowledge_mode") != "current":
            raise ValueError("The later run must use current knowledge mode")
        freeze = baseline_run.get("counterfactual_learning_freeze")
        current_memories = self.storage.memories(session_id=session_id)
        expected_freeze = _counterfactual_learning_freeze(current_memories)
        if freeze != expected_freeze:
            raise ValueError("counterfactual_learning_freeze_binding")
        if current_memories:
            if not isinstance(freeze, dict):
                raise ValueError("counterfactual_learning_freeze_missing")
            memory = current_memories[0]
            source_review = self.storage.get_review_for_run(
                memory["source_run_id"], session_id=session_id
            )
            if not isinstance(source_review, dict):
                raise ValueError("counterfactual_review_missing")
            freeze_time = max(
                _timestamp_seconds(source_review["created_at"]),
                _timestamp_seconds(memory["updated_at"]),
            )
            baseline_created = _timestamp_seconds(baseline_run["created_at"])
            baseline_completed = _timestamp_seconds(baseline_run["completed_at"])
            later_created = _timestamp_seconds(later_run["created_at"])
            if not (
                freeze_time <= baseline_created <= baseline_completed <= later_created
            ):
                raise ValueError("counterfactual_learning_temporal_order")
        before = self._learning_snapshot(baseline_run, session_id=session_id)
        after = self._learning_snapshot(later_run, session_id=session_id)
        before_result = baseline_run["result"]
        after_result = later_run["result"]
        before_process = semantic_process_dto(before_result["process"])
        after_process = semantic_process_dto(after_result["process"])
        before_checklist = semantic_checklist_dto(before_result["checklist"])
        after_checklist = semantic_checklist_dto(after_result["checklist"])
        before_precedents = {item["claim_id"] for item in before["precedents"]}
        after_precedents = {item["claim_id"] for item in after["precedents"]}
        memory_ids = {
            item["memory_id"]
            for item in after["precedents"]
            if item.get("review_status") == "unverified_demo_memory"
            and item.get("memory_id")
        }
        candidate = next(
            (
                value
                for value in self.storage.candidates(session_id=session_id)
                if value.get("candidate_id") == "candidate_disputed_ventilation_v4"
            ),
            None,
        )
        before_nodes = {value["node_id"]: value for value in before_process["nodes"]}
        after_nodes = {value["node_id"]: value for value in after_process["nodes"]}
        before_edges = {
            (value["source"], value["target"]): value
            for value in before_process["edges"]
        }
        after_edges = {
            (value["source"], value["target"]): value
            for value in after_process["edges"]
        }
        before_items = {value["item_id"]: value for value in before_checklist["items"]}
        after_items = {value["item_id"]: value for value in after_checklist["items"]}
        added_node_ids = sorted(set(after_nodes) - set(before_nodes))
        removed_node_ids = sorted(set(before_nodes) - set(after_nodes))
        changed_node_ids = sorted(
            node_id
            for node_id in set(before_nodes) & set(after_nodes)
            if before_nodes[node_id] != after_nodes[node_id]
        )
        added_edge_pairs = sorted(set(after_edges) - set(before_edges))
        removed_edge_pairs = sorted(set(before_edges) - set(after_edges))
        changed_edge_pairs = sorted(
            pair
            for pair in set(before_edges) & set(after_edges)
            if before_edges[pair] != after_edges[pair]
        )
        added_item_ids = sorted(set(after_items) - set(before_items))
        removed_item_ids = sorted(set(before_items) - set(after_items))
        changed_item_ids = sorted(
            item_id
            for item_id in set(before_items) & set(after_items)
            if before_items[item_id] != after_items[item_id]
        )
        process_root_before = {
            key: value
            for key, value in before_process.items()
            if key not in {"nodes", "edges"}
        }
        process_root_after = {
            key: value
            for key, value in after_process.items()
            if key not in {"nodes", "edges"}
        }
        changed_process_root_keys = sorted(
            key
            for key in set(process_root_before) | set(process_root_after)
            if process_root_before.get(key) != process_root_after.get(key)
        )
        checklist_root_before = {
            key: value for key, value in before_checklist.items() if key != "items"
        }
        checklist_root_after = {
            key: value for key, value in after_checklist.items() if key != "items"
        }
        changed_checklist_root_keys = sorted(
            key
            for key in set(checklist_root_before) | set(checklist_root_after)
            if checklist_root_before.get(key) != checklist_root_after.get(key)
        )
        causal_delta = {
            "nonzero": bool(
                added_node_ids
                or removed_node_ids
                or changed_node_ids
                or added_edge_pairs
                or removed_edge_pairs
                or changed_edge_pairs
                or added_item_ids
                or removed_item_ids
                or changed_item_ids
            ),
            "process": {
                "added_node_ids": added_node_ids,
                "removed_node_ids": removed_node_ids,
                "changed_node_ids": changed_node_ids,
                "added_edges": [
                    {"source": source, "target": target}
                    for source, target in added_edge_pairs
                ],
                "removed_edges": [
                    {"source": source, "target": target}
                    for source, target in removed_edge_pairs
                ],
                "changed_edges": [
                    {"source": source, "target": target}
                    for source, target in changed_edge_pairs
                ],
                "changed_root_keys": changed_process_root_keys,
            },
            "evidence": {
                "added_item_ids": added_item_ids,
                "removed_item_ids": removed_item_ids,
                "changed_item_ids": changed_item_ids,
                "changed_root_keys": changed_checklist_root_keys,
            },
        }

        receipt = after["memory_application"]
        receipt_valid = False
        source_memory_current = False
        current_memory: dict[str, Any] | None = None
        expected_target_tests: dict[str, Any] | None = None
        expected_protected_regression: dict[str, Any] | None = None
        candidate_origin_valid = False
        if receipt is not None:
            source_id = receipt.get("source_memory", {}).get("memory_id")
            current_memory = next(
                (
                    value
                    for value in self.storage.memories(session_id=session_id)
                    if value.get("memory_id") == source_id
                ),
                None,
            )
            if current_memory is None:
                raise MemoryApplicationError("memory_proof_source_missing")
            try:
                _validate_memory_origin(
                    current_memory,
                    source_run=self.storage.get_run(
                        current_memory.get("source_run_id", ""),
                        session_id=session_id,
                    ),
                    review=self.storage.get_review_for_run(
                        current_memory.get("source_run_id", ""),
                        session_id=session_id,
                    ),
                )
            except ValueError as exc:
                raise MemoryApplicationError("memory_proof_origin_integrity") from exc
            proof_understanding = {
                "facts": after_result["facts"],
                "category": after_result["category"],
                "subcategory": after_result["subcategory"],
            }
            expected_eligibility = _guidance_eligibility(
                current_memory["case_specific_guidance"],
                claim_id=after_result["claim_id"],
                understanding=proof_understanding,
            )
            try:
                memory_boundary = later_run.get("memory_application_boundary")
                if not isinstance(memory_boundary, dict):
                    raise ValueError("memory_boundary_missing")
                _validate_memory_application_boundary(
                    memory_boundary,
                    run_id=later_run_id,
                    claim_id=after_result["claim_id"],
                    memory=current_memory,
                )
                _validate_memory_application_event(later_run, receipt)
                if memory_boundary["before"] != receipt["before"]:
                    raise ValueError("memory_boundary_receipt_binding")
                _validate_memory_receipt(
                    receipt,
                    memory=current_memory,
                    expected_context={
                        "target": {
                            "run_id": later_run_id,
                            "claim_id": after_result["claim_id"],
                        },
                        "observable_input_hash": after["observable_input_hash"],
                        "canonical_state_hash": after["canonical_state_hash"],
                        "eligibility": expected_eligibility,
                        "before": memory_boundary["before"],
                        "after": {
                            "process_dto_hash": after["process_dto_hash"],
                            "checklist_dto_hash": after["checklist_dto_hash"],
                            "process_semantic_hash": after["process_semantic_hash"],
                            "checklist_semantic_hash": after["checklist_semantic_hash"],
                        },
                        "verification_hash": after["verification_hash"],
                    },
                )
            except ValueError as exc:
                raise MemoryApplicationError("memory_proof_source_integrity") from exc
            receipt_valid = True
            source_memory_current = True
            if candidate is not None:
                try:
                    source_run = self.storage.get_run(
                        current_memory["source_run_id"], session_id=session_id
                    )
                    review = self.storage.get_review_for_run(
                        current_memory["source_run_id"], session_id=session_id
                    )
                    if not isinstance(source_run, dict) or not isinstance(review, dict):
                        raise ValueError("candidate_origin_missing")
                    (
                        expected_target_tests,
                        expected_protected_regression,
                    ) = _governance_test_report(
                        current_memory["case_specific_guidance"],
                        protected_output_context=(
                            _protected_output_context_from_origin(
                                source_run,
                                review,
                            )
                        ),
                    )
                    _validate_candidate_origin(
                        candidate,
                        memory=current_memory,
                        source_run=source_run,
                        review=review,
                    )
                except ValueError:
                    candidate_origin_valid = False
                else:
                    candidate_origin_valid = True

        replay_exact = False
        if receipt_valid:
            replay_process = deepcopy(before_process)
            replay_checklist = deepcopy(before_checklist)
            semantic_facts = _fact_signature(
                {
                    "facts": after_result["facts"],
                }
            )
            ventilation_fact = semantic_facts.get(
                "management_ventilation_allegation", {}
            )
            if not isinstance(ventilation_fact.get("fact_id"), str):
                raise MemoryApplicationError("memory_proof_semantic_role_missing")
            replay = replay_case_specific_memory_transform(
                replay_process,
                replay_checklist,
                ventilation_fact_id=ventilation_fact["fact_id"],
            )
            replay_exact = (
                replay_process == after_process
                and replay_checklist == after_checklist
                and receipt["process_operations"][0]["after_hash"]
                == digest(replay["ventilation_node"])
                and receipt["process_operations"][1]["after_hash"]
                == digest(replay["first_edge"])
                and receipt["process_operations"][2]["after_hash"]
                == digest(replay["second_edge"])
                and receipt["evidence_operations"][0]["after_hash"]
                == digest(
                    next(
                        item
                        for item in replay_checklist["items"]
                        if item["item_id"] == "building_envelope"
                    )
                )
                and receipt["evidence_operations"][1]["after_hash"]
                == digest(
                    next(
                        item
                        for item in replay_checklist["items"]
                        if item["item_id"] == "use_evidence"
                    )
                )
                and receipt["evidence_operations"][0]["before_hash"]
                == digest(replay["building_before"])
                and receipt["evidence_operations"][1]["before_hash"]
                == digest(replay["use_before"])
                and receipt["evidence_operations"][1]["removed_from_node_ids"]
                == sorted(replay["removed_from"])
            )

        expected_changed_nodes: list[str] = []
        expected_added_nodes: list[str] = []
        expected_added_edges: list[tuple[str, str]] = []
        expected_changed_items: list[str] = []
        if receipt_valid:
            expected_added_nodes = sorted(
                value["node_id"]
                for value in receipt["process_operations"]
                if value["operation"] == "add_node"
            )
            expected_added_edges = sorted(
                (value["source"], value["target"])
                for value in receipt["process_operations"]
                if value["operation"] == "add_edge"
            )
            expected_changed_items = sorted(
                {value["item_id"] for value in receipt["evidence_operations"]}
                | {
                    item_id
                    for value in receipt["process_operations"]
                    if value["operation"] == "add_node"
                    for item_id in value.get("evidence_requirement_ids", [])
                    if item_id in before_items
                }
            )
            reassignment = next(
                value
                for value in receipt["evidence_operations"]
                if value["operation_id"] == "reassign_use_evidence_to_ventilation"
            )
            expected_changed_nodes = sorted(reassignment["removed_from_node_ids"])
        allowed_delta_exact = (
            receipt_valid
            and added_node_ids == expected_added_nodes
            and removed_node_ids == []
            and changed_node_ids == expected_changed_nodes
            and added_edge_pairs == expected_added_edges
            and removed_edge_pairs == []
            and changed_edge_pairs == []
            and added_item_ids == []
            and removed_item_ids == []
            and changed_item_ids == expected_changed_items
            and changed_process_root_keys
            == ["case_specific_guidance_applied", "memory_used"]
            and changed_checklist_root_keys
            == [
                "case_specific_guidance_applied",
                "memory_used",
                "required",
                "summary",
            ]
        )
        before_hashes_match = bool(
            receipt_valid
            and isinstance(memory_boundary, dict)
            and receipt["before"] == memory_boundary["before"]
            and receipt["before"]["process_semantic_hash"]
            == before["process_semantic_hash"]
            and receipt["before"]["checklist_semantic_hash"]
            == before["checklist_semantic_hash"]
        )
        after_hashes_match = bool(
            receipt_valid
            and receipt["after"]
            == {
                "process_dto_hash": after["process_dto_hash"],
                "checklist_dto_hash": after["checklist_dto_hash"],
                "process_semantic_hash": after["process_semantic_hash"],
                "checklist_semantic_hash": after["checklist_semantic_hash"],
            }
        )
        candidate_checks_pass = bool(
            current_memory
            and candidate
            and candidate_origin_valid
            and candidate.get("candidate_id") == current_memory.get("candidate_id")
            and candidate.get("status") == "quarantined"
            and candidate.get("target_tests") == expected_target_tests
            and candidate.get("protected_regression") == expected_protected_regression
            and candidate.get("qualified_support_count") == 0
            and candidate.get("approval")
            == {"status": "pending", "qualified_reviewer": False}
        )
        shared_rule_unchanged = (
            before["playbook_version"] == SHARED_PLAYBOOK_VERSION
            and after["playbook_version"] == SHARED_PLAYBOOK_VERSION
            and before["shared_rule_applied"] is False
            and after["shared_rule_applied"] is False
            and (receipt is None or receipt.get("shared_rule_applied") is False)
        )
        check_values = [
            (
                "Same observable input",
                before["observable_input_hash"] == after["observable_input_hash"],
            ),
            (
                "Same canonical state",
                before["canonical_state_hash"] == after["canonical_state_hash"]
                and before_result.get("category") == after_result.get("category")
                and before_result.get("subcategory") == after_result.get("subcategory")
                and before["verification_valid"]
                and after["verification_valid"],
            ),
            (
                "Exact current memory receipt",
                receipt_valid
                and source_memory_current
                and before.get("memory_application") is None
                and before["reviewed_memory_used"] is False
                and not any(
                    item.get("review_status") == "unverified_demo_memory"
                    for item in before["precedents"]
                )
                and after["reviewed_memory_used"] is True
                and receipt.get("source_memory", {}).get("memory_id") in memory_ids,
            ),
            ("Pure memory replay matches learned DTOs", replay_exact),
            ("Receipt before semantic hashes match baseline DTOs", before_hashes_match),
            ("Receipt after hashes match learned DTOs", after_hashes_match),
            ("Nonzero causal DTO delta", causal_delta["nonzero"]),
            ("Only allowed causal operations changed", allowed_delta_exact),
            ("Deterministic target and protected checks passed", candidate_checks_pass),
            ("Shared v3 remains unchanged", shared_rule_unchanged),
        ]
        deterministic_checks = [
            {
                "name": name,
                "status": "passed" if passed else "failed",
                "detail": "Computed from the two bound run DTOs and current governed storage.",
            }
            for name, passed in check_values
        ]
        ready = all(passed for _, passed in check_values)
        return {
            "ready": ready,
            "computed": True,
            "claim_id": "DEMO-MOULD-002",
            "baseline_run_id": baseline_run_id,
            "later_run_id": later_run_id,
            "counterfactual_learning_freeze": deepcopy(freeze),
            "before": before,
            "after": after,
            "changes": {
                "process_node_ids_added": sorted(
                    set(after["process_node_ids"]) - set(before["process_node_ids"])
                ),
                "process_node_ids_removed": sorted(
                    set(before["process_node_ids"]) - set(after["process_node_ids"])
                ),
                "required_now_added": sorted(
                    set(after["required_now_item_ids"])
                    - set(before["required_now_item_ids"])
                ),
                "required_now_removed": sorted(
                    set(before["required_now_item_ids"])
                    - set(after["required_now_item_ids"])
                ),
                "conditional_added": sorted(
                    set(after["conditional_item_ids"])
                    - set(before["conditional_item_ids"])
                ),
                "conditional_removed": sorted(
                    set(before["conditional_item_ids"])
                    - set(after["conditional_item_ids"])
                ),
                "precedent_claim_ids_added": sorted(
                    after_precedents - before_precedents
                ),
                "precedent_claim_ids_removed": sorted(
                    before_precedents - after_precedents
                ),
            },
            "reviewed_memory_proof": {
                "used": after["reviewed_memory_used"],
                "memory_ids": sorted(memory_ids),
                "present_in_baseline": any(
                    item.get("review_status") == "unverified_demo_memory"
                    for item in before["precedents"]
                ),
                "present_in_later_run": bool(memory_ids),
            },
            "causal_delta": causal_delta,
            "memory_application_proof": {
                "receipt_present": receipt is not None,
                "receipt_valid": receipt_valid,
                "source_memory_current": source_memory_current,
                "before_hashes_match": before_hashes_match,
                "after_hashes_match": after_hashes_match,
                "allowed_delta_exact": allowed_delta_exact,
                "replay_exact": replay_exact,
                "application_hash": receipt.get("application_hash")
                if receipt
                else None,
            },
            "deterministic_checks": deterministic_checks,
            "candidate": candidate,
            "shared_rule": {
                "applied": after["shared_rule_applied"],
                "version_before": before["playbook_version"],
                "version_after": after["playbook_version"],
                "shared_knowledge_changed": (
                    candidate.get("shared_knowledge_changed")
                    if candidate_origin_valid and candidate
                    else None
                ),
                "candidate_status": candidate.get("status") if candidate else None,
            },
            "interpretation": "This run-bound proof reports a bounded case-specific unverified-demo memory transform over the same observable and canonical inputs. It does not establish quality improvement, expert validation, qualified approval, or shared-rule promotion.",
        }
