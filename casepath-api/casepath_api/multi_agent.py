from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from itertools import combinations
import json
import math
import operator
import os
import threading
from time import perf_counter, sleep
from typing import Annotated, Any, Literal, Protocol, TypedDict, get_args

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict, Field, create_model, model_validator

from .canonicalizer import (
    GENERATION_METADATA_POLL_ATTEMPTS,
    GENERATION_METADATA_POLL_INTERVAL_SECONDS,
    GENERATION_METADATA_TIMEOUT_SECONDS,
    INPUT_USD_PER_MILLION_TOKENS,
    OPENROUTER_ACCEPTED_RESPONSE_MODELS,
    OPENROUTER_MODEL,
    OPENROUTER_PROVIDER,
    OPENROUTER_URL,
    OUTPUT_USD_PER_MILLION_TOKENS,
    MetadataTransport,
    ModelCostGuardError,
    ModelResponseError,
    _default_metadata_transport,
    _generation_metadata_ledger_patch,
    cumulative_usd_cap,
    observable_source_reference_registry,
    resolve_observable_source_reference_id,
    source_reference_id,
)
from .storage import Storage
from .projections import (
    DECISION_OPTIONS,
    apply_evidence_projection,
    apply_process_projection,
    checklist_derived_sections,
    decision_projection,
)
from .evidence_relations import apply_evidence_relations
from .langchain_runtime import (
    OPENROUTER_EXPECTED_UPSTREAM_PROVIDER,
    OPENROUTER_REASONING,
    OpenRouterProtocolError,
    OpenRouterSendAdmissionTimeoutError,
    OpenRouterUpstreamRejectionError,
    assert_external_tracing_disabled,
    openrouter_provider_policy,
    sanitize_provider_provenance,
    structured_nemotron_runnable,
)
from .playbook_template import MOULD_PLAYBOOK_TEMPLATE, PlaybookTemplate


MULTI_AGENT_VERSION = "1.5.0"
MULTI_AGENT_SCHEMA_VERSION = "casepath.nemotron-agent-dag/1.0.0"
MULTI_AGENT_AUTHORITY_MODE = "multi_agent_hybrid_guarded"
MULTI_AGENT_IMPLEMENTATION = "langgraph_stategraph_langchain_openrouter"
AGENT_RUNTIME_PROFILE = "nemotron_langgraph_multi_agent_hybrid_guarded"
LANGCHAIN_VERSION = "1.3.14"
LANGGRAPH_VERSION = "1.2.9"
LANGCHAIN_OPENROUTER_VERSION = "0.2.7"

AI_AGENT_IDS = (
    "canonical_facts",
    "orchestrator_plan",
    "document_source_integrity",
    "process_decision_mapping",
    "evidence_checklist",
    "final_claim_brief_audit",
)
MODEL_AGENT_IDS = AI_AGENT_IDS[1:]
DETERMINISTIC_GATE_IDS = (
    "deterministic_process_gate",
    "deterministic_evidence_gate",
    "whole_playbook_gate",
)
PARALLEL_GROUP = ("document_source_integrity", "process_decision_mapping")
EXECUTION_DELEGATIONS = (
    {"agent_id": "document_source_integrity", "dependencies": ["orchestrator_plan"]},
    {"agent_id": "process_decision_mapping", "dependencies": ["orchestrator_plan"]},
    {"agent_id": "evidence_checklist", "dependencies": ["deterministic_process_gate"]},
    {"agent_id": "final_claim_brief_audit", "dependencies": ["deterministic_evidence_gate"]},
)
PROCESS_DECISION_VALUE_CANDIDATES = {
    key: sorted(values.values()) for key, values in DECISION_OPTIONS.items()
}
EVIDENCE_STATUS_CANDIDATES = [
    "provided_sufficient",
    "provided_insufficient",
    "missing",
    "conditional",
    "not_applicable",
]
EVIDENCE_ARTIFACT_SELECTION_CAP = 8
EvidenceItemId = Literal[
    "claim_message",
    "source_integrity",
    "lease",
    "policy_reference",
    "customer_objective",
    "management_position",
    "health_safety_statement",
    "defect_notice",
    "proof_of_delivery",
    "dated_photos",
    "recurrence_chronology",
    "technical_assessment",
    "moisture_measurements",
    "building_envelope",
    "repair_history",
    "use_evidence",
    "remediation_plan",
    "financial_impact",
    "settlement_proposal",
    "conciliation_bundle",
    "completion_record",
]
EVIDENCE_ITEM_IDS = tuple(get_args(EvidenceItemId))
EVIDENCE_ARTIFACT_CAPABILITIES: dict[str, frozenset[str]] = {
    "claim_message": frozenset({"claim_message"}),
    "source_integrity": frozenset({"submitted_source"}),
    "lease": frozenset({"lease"}),
    "policy_reference": frozenset({"policy_reference"}),
    "customer_objective": frozenset({"claim_message", "customer_correspondence"}),
    "management_position": frozenset({"management_correspondence"}),
    "health_safety_statement": frozenset({"claim_message", "customer_correspondence", "medical"}),
    "defect_notice": frozenset({"defect_notice", "customer_correspondence"}),
    "proof_of_delivery": frozenset({"delivery_proof"}),
    "dated_photos": frozenset({"photo"}),
    "recurrence_chronology": frozenset({"timeline"}),
    "technical_assessment": frozenset({"technical_report", "inspection_report"}),
    "moisture_measurements": frozenset({"measurement_report"}),
    "building_envelope": frozenset({"building_report", "technical_report"}),
    "repair_history": frozenset({"maintenance_record", "management_correspondence"}),
    "use_evidence": frozenset({"use_log", "utility_record"}),
    "remediation_plan": frozenset({"remediation_plan", "maintenance_record"}),
    "financial_impact": frozenset({"invoice", "financial_record"}),
    "settlement_proposal": frozenset({"settlement_record", "correspondence"}),
    "conciliation_bundle": frozenset({"legal_filing"}),
    "completion_record": frozenset({"completion_record", "maintenance_record"}),
}
SOURCE_INTEGRITY_PROPOSAL_COUNT = 6
PROCESS_DECISION_PROPOSAL_COUNT = 6
PRIORITY_TASK_CODES = (
    "source_integrity",
    "process_decisions",
    "evidence_gaps",
    "final_brief",
)
FINAL_AUDIT_CHECK_IDS = (
    "current_node_supported_by_canonical_facts",
    "next_action_connected_in_static_topology",
    "evidence_items_bound_to_process_nodes",
    "upstream_contribution_lineage_complete",
)

ROLE_OUTPUT_TOKENS = {
    "orchestrator_plan": 4_096,
    "document_source_integrity": 4_096,
    "process_decision_mapping": 4_096,
    "evidence_checklist": 8_192,
    "final_claim_brief_audit": 4_096,
}
SOURCE_INTEGRITY_REASONING_EFFORT = "none"
ROLE_REASONING = {
    agent_id: (
        {"effort": SOURCE_INTEGRITY_REASONING_EFFORT}
        if agent_id == "document_source_integrity"
        else dict(OPENROUTER_REASONING)
    )
    for agent_id in MODEL_AGENT_IDS
}
ROLE_PURPOSES = {
    "orchestrator_plan": "bounded claim-agent focus and priority plan",
    "document_source_integrity": "bounded source-integrity proposals",
    "process_decision_mapping": "bounded process-decision proposals",
    "evidence_checklist": "bounded evidence-checklist proposals",
    "final_claim_brief_audit": "bounded final-claim-brief audit proposal",
}
ROLE_LABELS = {
    "orchestrator_plan": "Nemotron Orchestrator",
    "document_source_integrity": "Document and Source Integrity Agent",
    "process_decision_mapping": "Process Decision Mapping Agent",
    "evidence_checklist": "Evidence and Checklist Agent",
    "final_claim_brief_audit": "Final Claim Brief Agent",
}
ROLE_OUTPUT_ARTIFACTS = {
    "orchestrator_plan": "bounded_orchestration_focus",
    "document_source_integrity": "source_integrity_contribution",
    "process_decision_mapping": "process_mapping_contribution",
    "evidence_checklist": "evidence_checklist_contribution",
    "final_claim_brief_audit": "final_claim_brief_contribution",
}
ROLE_HANDOFFS = {
    "orchestrator_plan": ("canonical_facts", "document_source_integrity+process_decision_mapping"),
    "document_source_integrity": ("orchestrator_plan", "deterministic_process_gate"),
    "process_decision_mapping": ("orchestrator_plan", "deterministic_process_gate"),
    "evidence_checklist": ("deterministic_process_gate", "deterministic_evidence_gate"),
    "final_claim_brief_audit": ("deterministic_evidence_gate", "whole_playbook_gate"),
}


class AgentBoundaryError(RuntimeError):
    """Safe role/invariant-only error for a bounded model contribution."""

    def __init__(self, agent_id: str, invariant: str):
        super().__init__(f"{agent_id}: {invariant} invariant failed")
        self.agent_id = agent_id
        self.invariant = invariant


class AgentInvocationFailure(AgentBoundaryError):
    """Failed agent call carrying only ledger-safe provider provenance."""

    def __init__(
        self,
        agent_id: str,
        invariant: str,
        *,
        safe_context: Mapping[str, Any],
    ):
        super().__init__(agent_id, invariant)
        self.safe_context = dict(safe_context)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# Together's structured-output grammar does not implement JSON Schema's
# ``uniqueItems`` keyword.  Keep wire schemas within that supported subset;
# the validators below and each contribution gate enforce list uniqueness
# before any model-owned value is accepted.
class OrchestratorPlan(_StrictModel):
    priority_fact_ids: list[str] = Field(
        min_length=1,
        max_length=6,
    )
    priority_task_codes: list[
        Literal["source_integrity", "process_decisions", "evidence_gaps", "final_brief"]
    ] = Field(
        min_length=4,
        max_length=4,
    )


class SourceIntegrityProposal(_StrictModel):
    artifact_id: str
    integrity_class: Literal["text_grounded", "visual_only", "metadata_only"]
    source_ref_ids: list[str] = Field(
        max_length=1,
    )
    confidence_basis_points: int = Field(ge=0, le=10_000)


class SourceIntegrityResponse(_StrictModel):
    proposals: list[SourceIntegrityProposal] = Field(
        min_length=SOURCE_INTEGRITY_PROPOSAL_COUNT,
        max_length=SOURCE_INTEGRITY_PROPOSAL_COUNT,
    )

    @model_validator(mode="after")
    def require_unique_artifact_ids(self) -> SourceIntegrityResponse:
        artifact_ids = [proposal.artifact_id for proposal in self.proposals]
        if len(set(artifact_ids)) != len(artifact_ids):
            raise ValueError("source_integrity_proposal_membership")
        return self


def _bounded_source_integrity_schema(
    *,
    artifact_ids: tuple[str, ...],
    source_ref_ids: tuple[str, ...],
) -> type[SourceIntegrityResponse]:
    """Bind the provider-native source response to one finite request vocabulary."""

    if not artifact_ids or not source_ref_ids or len(set(artifact_ids)) != len(
        artifact_ids
    ):
        raise AgentBoundaryError(
            "document_source_integrity", "source_candidate_membership"
        )
    artifact_id_type = Literal.__getitem__(artifact_ids)
    source_ref_id_type = Literal.__getitem__(source_ref_ids)
    proposal_schema = create_model(
        "BoundedSourceIntegrityProposal",
        __base__=SourceIntegrityProposal,
        artifact_id=(artifact_id_type, ...),
        source_ref_ids=(
            list[source_ref_id_type],
            Field(max_length=1),
        ),
    )
    return create_model(
        "BoundedSourceIntegrityResponse",
        __base__=SourceIntegrityResponse,
        proposals=(
            list[proposal_schema],
            Field(
                min_length=len(artifact_ids),
                max_length=len(artifact_ids),
            ),
        ),
    )


DecisionOption = Literal[
    "in_scope",
    "out_of_scope",
    "scope_unverified",
    "dispute_present",
    "no_dispute",
    "dispute_unverified",
    "urgent",
    "not_urgent",
    "urgency_unverified",
    "notified",
    "not_notified",
    "notification_unverified",
    "recurrence_supported",
    "recurrence_not_supported",
    "recurrence_unverified",
    "cause_building",
    "cause_tenant_use",
    "cause_mixed",
    "cause_unresolved",
]


class ProcessDecisionProposal(_StrictModel):
    fact_id: str
    decision_value: DecisionOption
    confidence: float = Field(ge=0, le=1)


class ProcessDecisionResponse(_StrictModel):
    proposals: list[ProcessDecisionProposal] = Field(
        min_length=PROCESS_DECISION_PROPOSAL_COUNT,
        max_length=PROCESS_DECISION_PROPOSAL_COUNT,
    )

    @model_validator(mode="after")
    def require_unique_fact_ids(self) -> ProcessDecisionResponse:
        fact_ids = [proposal.fact_id for proposal in self.proposals]
        if len(set(fact_ids)) != len(fact_ids):
            raise ValueError("process_decision_proposal_membership")
        return self


def _bounded_process_decision_schema(
    controlling_facts: Mapping[str, Mapping[str, Any]],
    decision_options: Mapping[str, Mapping[str, str]],
) -> type[BaseModel]:
    """Bind one process response to the template's exact facts and vocabulary."""

    fact_ids = tuple(controlling_facts)
    decision_values = tuple(
        sorted(
            {
                value
                for options in decision_options.values()
                for value in options.values()
            }
        )
    )
    if (
        not fact_ids
        or len(set(fact_ids)) != len(fact_ids)
        or not decision_values
    ):
        raise AgentBoundaryError(
            "process_decision_mapping", "process_candidate_membership"
        )
    proposal_schema = create_model(
        "BoundedProcessDecisionProposal",
        __base__=ProcessDecisionProposal,
        fact_id=(Literal.__getitem__(fact_ids), ...),
        decision_value=(Literal.__getitem__(decision_values), ...),
    )
    return create_model(
        "BoundedProcessDecisionResponse",
        __base__=_StrictModel,
        proposals=(
            list[proposal_schema],
            Field(min_length=len(fact_ids), max_length=len(fact_ids)),
        ),
    )


class EvidenceChecklistProposal(_StrictModel):
    item_id: EvidenceItemId
    status: Literal[
        "provided_sufficient",
        "provided_insufficient",
        "missing",
        "conditional",
        "not_applicable",
    ]
    artifact_ids: list[str] = Field(
        max_length=8,
    )
    confidence: float = Field(ge=0, le=1)


class EvidenceChecklistResponse(_StrictModel):
    proposals: list[EvidenceChecklistProposal] = Field(
        min_length=len(EVIDENCE_ITEM_IDS),
        max_length=len(EVIDENCE_ITEM_IDS),
    )

    @model_validator(mode="after")
    def require_exact_item_ids(self) -> EvidenceChecklistResponse:
        item_ids = [proposal.item_id for proposal in self.proposals]
        if len(set(item_ids)) != len(item_ids) or set(item_ids) != set(
            EVIDENCE_ITEM_IDS
        ):
            raise ValueError("evidence_proposal_membership")
        return self


def _coherent_evidence_statuses(
    *, required_level: str, has_artifacts: bool
) -> tuple[str, ...]:
    """Return only status choices coherent with one checklist slot state."""

    if required_level not in {"mandatory", "conditional"}:
        raise AgentBoundaryError("evidence_checklist", "evidence_required_level")
    if has_artifacts:
        choices = {"provided_sufficient", "provided_insufficient"}
        if required_level == "conditional":
            choices.add("conditional")
    elif required_level == "mandatory":
        choices = {"missing"}
    else:
        choices = {"conditional", "not_applicable"}
    return tuple(status for status in EVIDENCE_STATUS_CANDIDATES if status in choices)


def _evidence_selection_id(status: str, artifact_ids: tuple[str, ...]) -> str:
    """Encode one self-describing provider choice without relying on parsing it."""

    artifacts = "+".join(artifact_ids) if artifact_ids else "none"
    return f"{status}::{artifacts}"


def _evidence_selection_catalog(
    *, required_level: str, candidate_artifact_ids: list[str]
) -> dict[str, dict[str, Any]]:
    """Enumerate every bounded, status/artifact-coherent choice for one slot."""

    if (
        any(
            not isinstance(artifact_id, str) or not artifact_id
            for artifact_id in candidate_artifact_ids
        )
        or candidate_artifact_ids != sorted(set(candidate_artifact_ids))
        or len(candidate_artifact_ids) > EVIDENCE_ARTIFACT_SELECTION_CAP
    ):
        raise AgentBoundaryError(
            "evidence_checklist", "evidence_candidate_artifact_cap"
        )
    selections: list[tuple[str, tuple[str, ...]]] = [
        (status, ())
        for status in _coherent_evidence_statuses(
            required_level=required_level, has_artifacts=False
        )
    ]
    for size in range(1, len(candidate_artifact_ids) + 1):
        for artifact_ids in combinations(candidate_artifact_ids, size):
            selections.extend(
                (status, artifact_ids)
                for status in _coherent_evidence_statuses(
                    required_level=required_level, has_artifacts=True
                )
            )
    catalog = {
        _evidence_selection_id(status, artifact_ids): {
            "status": status,
            "artifact_ids": list(artifact_ids),
        }
        for status, artifact_ids in selections
    }
    if len(catalog) != len(selections):
        raise AgentBoundaryError("evidence_checklist", "evidence_selection_identity")
    return dict(sorted(catalog.items()))


def _evidence_selection_catalogs(
    candidate_contracts: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, dict[str, Any]]]:
    item_ids = tuple(candidate_contracts)
    if not item_ids or len(set(item_ids)) != len(item_ids):
        raise AgentBoundaryError("evidence_checklist", "evidence_candidate_membership")
    catalogs: dict[str, dict[str, dict[str, Any]]] = {}
    for item_id in item_ids:
        contract = candidate_contracts[item_id]
        if contract.get("item_id") != item_id:
            raise AgentBoundaryError(
                "evidence_checklist", "evidence_candidate_membership"
            )
        candidate_artifact_ids = contract.get("candidate_artifact_ids")
        if not isinstance(candidate_artifact_ids, list):
            raise AgentBoundaryError(
                "evidence_checklist", "evidence_candidate_artifacts"
            )
        catalogs[item_id] = _evidence_selection_catalog(
            required_level=contract.get("required_level"),
            candidate_artifact_ids=candidate_artifact_ids,
        )
    return catalogs


def _bounded_evidence_checklist_schema(
    candidate_contracts: Mapping[str, Mapping[str, Any]],
) -> type[BaseModel]:
    """Create fixed provider slots whose enums permit only coherent selections."""

    catalogs = _evidence_selection_catalogs(candidate_contracts)
    item_fields: dict[str, tuple[type[BaseModel], Any]] = {}
    for item_id in candidate_contracts:
        class_suffix = "".join(part.title() for part in item_id.split("_"))
        selection_enum = Enum(
            f"BoundedEvidence{class_suffix}SelectionId",
            {
                f"option_{index:03d}": selection_id
                for index, selection_id in enumerate(catalogs[item_id])
            },
        )
        slot_schema = create_model(
            f"BoundedEvidence{class_suffix}Slot",
            __base__=_StrictModel,
            selection_id=(selection_enum, ...),
            confidence=(float, Field(ge=0, le=1)),
        )
        item_fields[item_id] = (slot_schema, ...)
    items_schema = create_model(
        "BoundedEvidenceChecklistItems",
        __base__=_StrictModel,
        **item_fields,
    )
    return create_model(
        "BoundedEvidenceChecklistResponse",
        __base__=_StrictModel,
        items=(items_schema, ...),
    )


def _normalize_evidence_checklist_response(
    value: Mapping[str, Any],
    *,
    candidate_contracts: Mapping[str, Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Restore the internal proposal list after validating fixed provider slots."""

    catalogs = _evidence_selection_catalogs(candidate_contracts)
    if set(value) != {"items"}:
        raise AgentBoundaryError("evidence_checklist", "evidence_wire_slots")
    items = value.get("items")
    if not isinstance(items, Mapping) or set(items) != set(candidate_contracts):
        raise AgentBoundaryError("evidence_checklist", "evidence_wire_slots")
    proposals: list[dict[str, Any]] = []
    for item_id in candidate_contracts:
        slot = items.get(item_id)
        if not isinstance(slot, Mapping) or set(slot) != {
            "selection_id",
            "confidence",
        }:
            raise AgentBoundaryError("evidence_checklist", "evidence_wire_slots")
        selection_id = slot.get("selection_id")
        selection = catalogs[item_id].get(selection_id)
        confidence = slot.get("confidence")
        if selection is None or (
            not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not math.isfinite(float(confidence))
            or not 0 <= float(confidence) <= 1
        ):
            raise AgentBoundaryError("evidence_checklist", "evidence_wire_selection")
        proposals.append(
            {
                "item_id": item_id,
                "status": selection["status"],
                "artifact_ids": list(selection["artifact_ids"]),
                "confidence": float(confidence),
            }
        )
    return {"proposals": proposals}


class FinalClaimBriefProposal(_StrictModel):
    current_node_id: str
    next_action_node_id: str
    supporting_fact_ids: list[str] = Field(
        max_length=6,
    )
    upstream_contribution_ids: list[
        Literal[
            "document_source_integrity",
            "process_decision_mapping",
            "evidence_checklist",
        ]
    ] = Field(max_length=3)
    audit_check_ids: list[
        Literal[
            "current_node_supported_by_canonical_facts",
            "next_action_connected_in_static_topology",
            "evidence_items_bound_to_process_nodes",
            "upstream_contribution_lineage_complete",
        ]
    ] = Field(max_length=4)
    confidence: float = Field(ge=0, le=1)


class FinalClaimBriefResponse(_StrictModel):
    proposal: FinalClaimBriefProposal


class AgentGraphState(TypedDict, total=False):
    run_id: str
    orchestration_id: str
    playbook_template_sha256: str
    observable_package: dict[str, Any]
    canonicalization: dict[str, Any]
    facts: list[dict[str, Any]]
    process: dict[str, Any]
    checklist: dict[str, Any]
    verification: dict[str, Any]
    verification_builder: Callable[
        [dict[str, Any], dict[str, Any]], dict[str, Any]
    ]
    seed_process_hash: str
    seed_checklist_hash: str
    source_registry: list[dict[str, Any]]
    orchestrator_plan: dict[str, Any]
    orchestrator_call_id: str
    source_integrity: dict[str, Any]
    process_mapping: dict[str, Any]
    evidence_checklist: dict[str, Any]
    final_brief: dict[str, Any]
    audit_entries: Annotated[list[dict[str, Any]], operator.add]
    orchestration_audit: dict[str, Any]
    accepted_cycle_artifacts: dict[str, Any]


class StructuredRunnable(Protocol):
    def invoke(self, value: Any, config: dict[str, Any] | None = None) -> Any: ...


RunnableFactory = Callable[[str, type[BaseModel], str, str, int], StructuredRunnable]
ContributionValidator = Callable[[dict[str, Any]], tuple[dict[str, Any], dict[str, Any]]]


_LOCKS_GUARD = threading.Lock()
_CACHE_KEY_LOCKS: dict[str, threading.Lock] = {}


def _cache_lock(cache_key: str) -> threading.Lock:
    with _LOCKS_GUARD:
        return _CACHE_KEY_LOCKS.setdefault(cache_key, threading.Lock())


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _safe_hash(value: Any) -> str:
    return sha256(_json(value).encode("utf-8")).hexdigest()


def _reject_floats(value: Any, *, path: str = "$") -> None:
    if isinstance(value, float):
        raise AgentBoundaryError("accepted_artifact", f"float_at_{path}")
    if isinstance(value, Mapping):
        for key, child in value.items():
            _reject_floats(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_floats(child, path=f"{path}[{index}]")


def accepted_artifact_hash(value: Any) -> str:
    """Hash a cross-runtime DTO only after excluding JSON float ambiguity."""

    _reject_floats(value)
    return _safe_hash(value)


def _confidence_basis_points(value: Any) -> int:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or not 0 <= float(value) <= 1
    ):
        raise AgentBoundaryError("provider", "confidence")
    return int(math.floor(float(value) * 10_000 + 0.5))


def _input_token_estimate(value: str) -> int:
    return max(1, math.ceil(len(value.encode("utf-8")) / 3))


def _estimated_cost(input_tokens: int, output_tokens: int) -> float:
    return round(
        input_tokens * INPUT_USD_PER_MILLION_TOKENS / 1_000_000
        + output_tokens * OUTPUT_USD_PER_MILLION_TOKENS / 1_000_000,
        8,
    )


def _ref_id(ref: Mapping[str, Any]) -> str:
    if ref.get("locator_kind") == "text_quote":
        return source_reference_id(dict(ref))
    public_locator = {
        key: ref[key]
        for key in (
            "artifact_id",
            "locator_kind",
            "page",
            "region",
            "observation",
            "field",
            "value",
        )
        if key in ref
    }
    return f"src_{_safe_hash(public_locator)[:24]}"


def _source_registry(package: dict[str, Any]) -> list[dict[str, Any]]:
    return observable_source_reference_registry(package)


def _integrity_class(media_type: str) -> str:
    normalized = media_type.split(";", 1)[0].strip().lower()
    if normalized.startswith("image/"):
        return "visual_only"
    if normalized.startswith("text/") or normalized in {
        "application/pdf",
        "message/rfc822",
    }:
        return "text_grounded"
    return "metadata_only"


def _artifact_capabilities(
    artifact: Mapping[str, Any],
    *,
    template: PlaybookTemplate = MOULD_PLAYBOOK_TEMPLATE,
    authoritative_capabilities: set[str] | None = None,
) -> set[str]:
    """Resolve reusable semantic capabilities without claim-specific IDs."""

    if template.template_sha256 != MOULD_PLAYBOOK_TEMPLATE.template_sha256:
        if authoritative_capabilities is None:
            raise AgentBoundaryError(
                "evidence_checklist", "artifact_capability_contract"
            )
        return set(authoritative_capabilities)

    artifact_id = str(artifact.get("artifact_id", "")).casefold()
    filename = str(artifact.get("filename", "")).casefold()
    media_type = str(artifact.get("media_type", "")).casefold()
    text = f"{artifact_id} {filename}"
    capabilities = {"submitted_source"}
    if artifact_id == "message":
        capabilities.update({"claim_message", "customer_correspondence", "correspondence"})
    if artifact_id == "intake":
        capabilities.add("policy_reference")
    if media_type.startswith("image/") or any(word in text for word in ("photo", "image", "photograph")):
        capabilities.add("photo")
    if any(word in text for word in ("lease", "tenancy", "rental_agreement", "contract")):
        capabilities.add("lease")
    if any(word in text for word in ("delivery", "receipt", "registered_mail")):
        capabilities.add("delivery_proof")
    if any(word in text for word in ("timeline", "chronology")):
        capabilities.add("timeline")
    if any(word in text for word in ("notification", "notice", "reported_defect")):
        capabilities.update({"defect_notice", "customer_correspondence", "correspondence"})
    if any(word in text for word in ("management_reply", "landlord_reply", "property_manager")):
        capabilities.update({"management_correspondence", "correspondence"})
    if any(word in text for word in ("inspection", "technical", "expert", "building_physics")):
        capabilities.update({"technical_report", "inspection_report"})
    if any(word in text for word in ("moisture", "humidity", "temperature", "measurement")):
        capabilities.add("measurement_report")
    if any(word in text for word in ("envelope", "facade", "window_seal", "thermal_bridge")):
        capabilities.add("building_report")
    if any(word in text for word in ("maintenance", "repair", "work_order", "contractor")):
        capabilities.add("maintenance_record")
    if any(word in text for word in ("ventilation_log", "heating", "occupancy", "use_log")):
        capabilities.add("use_log")
    if any(word in text for word in ("utility", "energy_bill")):
        capabilities.add("utility_record")
    if any(word in text for word in ("remediation_plan", "scope_of_work")):
        capabilities.add("remediation_plan")
    if any(word in text for word in ("invoice", "rent_record", "financial", "loss")):
        capabilities.update({"invoice", "financial_record"})
    if any(word in text for word in ("settlement", "mediation", "proposal")):
        capabilities.add("settlement_record")
    if any(word in text for word in ("conciliation", "court", "filing")):
        capabilities.add("legal_filing")
    if any(word in text for word in ("completion", "closure", "completed")):
        capabilities.add("completion_record")
    if any(word in text for word in ("medical", "doctor", "health_report")):
        capabilities.add("medical")
    return capabilities


def _evidence_artifact_catalog(
    state: AgentGraphState,
    *,
    template: PlaybookTemplate = MOULD_PLAYBOOK_TEMPLATE,
) -> list[dict[str, Any]]:
    authoritative_grants: dict[str, set[str]] = {}
    if template.template_sha256 != MOULD_PLAYBOOK_TEMPLATE.template_sha256:
        checklist = state.get("checklist")
        items = checklist.get("items") if isinstance(checklist, Mapping) else None
        if not isinstance(items, list):
            raise AgentBoundaryError(
                "evidence_checklist", "artifact_capability_contract"
            )
        for checklist_item in items:
            if not isinstance(checklist_item, Mapping):
                raise AgentBoundaryError(
                    "evidence_checklist", "artifact_capability_contract"
                )
            item_id = checklist_item.get("item_id")
            artifact_ids = checklist_item.get("artifact_ids")
            capabilities = template.evidence_artifact_capabilities.get(item_id)
            if (
                not isinstance(item_id, str)
                or not isinstance(artifact_ids, list)
                or (
                    not artifact_ids
                    and checklist_item.get("status")
                    not in {"conditional", "missing", "not_required"}
                )
                or capabilities is None
            ):
                raise AgentBoundaryError(
                    "evidence_checklist", "artifact_capability_contract"
                )
            for artifact_id in artifact_ids:
                if not isinstance(artifact_id, str) or not artifact_id:
                    raise AgentBoundaryError(
                        "evidence_checklist", "artifact_capability_contract"
                    )
                authoritative_grants.setdefault(artifact_id, set()).update(
                    capabilities
                )
    inventory = [
        {
            "artifact_id": "message",
            "filename": "Claim message",
            "media_type": "text/plain",
            "integrity_class": "text_grounded",
            "capabilities": [
                "claim_message",
                "customer_correspondence",
                "correspondence",
            ],
        },
        {
            "artifact_id": "intake",
            "filename": "Claim intake",
            "media_type": "application/casepath-intake+json",
            "integrity_class": "metadata_only",
            "capabilities": ["policy_reference"],
        },
    ]
    integrity = {
        item["artifact_id"]: item
        for item in state.get("source_integrity", {}).get("artifacts", [])
    }
    for artifact in state["observable_package"].get("artifacts", []):
        accepted = integrity.get(artifact["artifact_id"], {})
        inventory.append(
            {
                "artifact_id": artifact["artifact_id"],
                "filename": artifact["filename"],
                "media_type": artifact["media_type"],
                "integrity_class": accepted.get(
                    "integrity_class", _integrity_class(artifact["media_type"])
                ),
            }
        )
    return [
        {
            **item,
            "capabilities": sorted(
                _artifact_capabilities(
                    item,
                    template=template,
                    authoritative_capabilities=(
                        authoritative_grants.get(item["artifact_id"], set())
                        if template.template_sha256
                        != MOULD_PLAYBOOK_TEMPLATE.template_sha256
                        else None
                    ),
                )
            ),
        }
        for item in inventory
    ]


def _compatible_evidence_artifact_ids(
    item_id: str,
    artifact_catalog: list[dict[str, Any]],
    *,
    template: PlaybookTemplate = MOULD_PLAYBOOK_TEMPLATE,
) -> list[str]:
    capabilities = template.evidence_artifact_capabilities.get(item_id)
    if capabilities is None:
        raise AgentBoundaryError("evidence_checklist", "evidence_item_capability")
    return sorted(
        item["artifact_id"]
        for item in artifact_catalog
        if set(capabilities) & set(item["capabilities"])
        and (
            (item_id == "source_integrity" and item["artifact_id"] not in {"message", "intake"})
            or item["artifact_id"] not in {"message", "intake"}
            or item_id in {
                "claim_message",
                "policy_reference",
                "customer_objective",
                "health_safety_statement",
                "defect_notice",
            }
        )
    )


def _evidence_candidate_artifact_ids(
    state: AgentGraphState,
    *,
    template: PlaybookTemplate = MOULD_PLAYBOOK_TEMPLATE,
) -> dict[str, list[str]]:
    artifact_catalog = _evidence_artifact_catalog(state, template=template)
    facts = state.get("facts")
    checklist = state.get("checklist")
    if not isinstance(facts, list) or not isinstance(checklist, Mapping):
        raise AgentBoundaryError("evidence_checklist", "evidence_candidate_context")
    items = checklist.get("items")
    if not isinstance(items, list):
        raise AgentBoundaryError("evidence_checklist", "evidence_candidate_items")
    facts_by_id = {
        fact.get("fact_id"): fact
        for fact in facts
        if isinstance(fact, Mapping) and isinstance(fact.get("fact_id"), str)
    }
    candidates: dict[str, list[str]] = {}
    for item in items:
        if not isinstance(item, Mapping):
            raise AgentBoundaryError("evidence_checklist", "evidence_candidate_item")
        item_id = item.get("item_id")
        fact = facts_by_id.get(item.get("fact_id"))
        if not isinstance(item_id, str) or not isinstance(fact, Mapping):
            raise AgentBoundaryError("evidence_checklist", "evidence_candidate_fact")
        grounded_artifact_ids = {
            ref.get("artifact_id")
            for ref in fact.get("source_refs", [])
            if isinstance(ref, Mapping) and isinstance(ref.get("artifact_id"), str)
        }
        candidates[item_id] = sorted(
            set(
                _compatible_evidence_artifact_ids(
                    item_id, artifact_catalog, template=template
                )
            )
            & grounded_artifact_ids
        )
    if set(candidates) != {
        item.get("item_id") for item in items if isinstance(item, Mapping)
    }:
        raise AgentBoundaryError(
            "evidence_checklist", "evidence_candidate_membership"
        )
    return candidates


def _expected_text_ref_ids(
    refs: list[dict[str, Any]],
    registry: list[dict[str, Any]],
) -> list[str]:
    return sorted(
        resolve_observable_source_reference_id(ref, registry)
        for ref in refs
        if ref.get("locator_kind") == "text_quote"
    )


def _deterministic_focus_source_ref_ids(
    registry: list[dict[str, Any]],
    required_text_artifact_ids: list[str],
) -> list[str]:
    """Select one stable observable passage for every text-bearing artifact."""

    if len(set(required_text_artifact_ids)) != len(required_text_artifact_ids):
        raise AgentBoundaryError("orchestrator_plan", "text_artifact_membership")
    refs_by_artifact: dict[str, list[str]] = {}
    for item in registry:
        artifact_id = item.get("artifact_id")
        source_ref_id = item.get("source_ref_id")
        if isinstance(artifact_id, str) and isinstance(source_ref_id, str):
            refs_by_artifact.setdefault(artifact_id, []).append(source_ref_id)
    selected: list[str] = []
    for artifact_id in required_text_artifact_ids:
        candidates = refs_by_artifact.get(artifact_id, [])
        if not candidates:
            raise AgentBoundaryError(
                "orchestrator_plan", "text_artifact_source_coverage"
            )
        selected.append(min(candidates))
    return selected


def _assigned_focus(plan: Mapping[str, Any], task_code: str) -> dict[str, Any]:
    task_codes = plan["priority_task_codes"]
    return {
        "fact_ids": plan["focus_fact_ids"],
        "source_ref_ids": plan["focus_source_ref_ids"],
        "task_code": task_code,
        "priority_rank": task_codes.index(task_code),
    }


def _evidence_provider_payload(
    state: AgentGraphState,
    *,
    template: PlaybookTemplate = MOULD_PLAYBOOK_TEMPLATE,
) -> dict[str, Any]:
    focus_rank = {
        fact_id: index
        for index, fact_id in enumerate(state["orchestrator_plan"]["focus_fact_ids"])
    }
    artifact_inventory = _evidence_artifact_catalog(state, template=template)
    candidate_artifact_ids_by_item = _evidence_candidate_artifact_ids(
        state, template=template
    )
    evidence_candidates = []
    for item in sorted(
        state["checklist"]["items"],
        key=lambda value: (focus_rank[value["fact_id"]], value["item_id"]),
    ):
        candidate_artifact_ids = candidate_artifact_ids_by_item[item["item_id"]]
        evidence_candidates.append(
            {
                **{
                    key: deepcopy(item[key])
                    for key in (
                        "item_id",
                        "title",
                        "fact_id",
                        "node_id",
                        "legal_basis_ids",
                        "acceptable_alternatives",
                        "applies_when",
                        "required_level",
                        "current_path",
                    )
                },
                "candidate_artifact_ids": candidate_artifact_ids,
                "status_choices": {
                    "with_artifacts": list(
                        _coherent_evidence_statuses(
                            required_level=item["required_level"],
                            has_artifacts=True,
                        )
                    ),
                    "without_artifacts": list(
                        _coherent_evidence_statuses(
                            required_level=item["required_level"],
                            has_artifacts=False,
                        )
                    ),
                },
            }
        )
    required_item_ids = [item["item_id"] for item in evidence_candidates]
    checklist_item_ids = [
        item.get("item_id") for item in state["checklist"]["items"]
    ]
    matching_claim_ids = [
        candidate_claim_id
        for candidate_claim_id, item_ids in template.catalog[
            "evidence_item_ids_by_claim"
        ].items()
        if list(item_ids) == checklist_item_ids
    ]
    if len(matching_claim_ids) != 1:
        raise AgentBoundaryError(
            "evidence_checklist", "evidence_template_claim_membership"
        )
    claim_id = matching_claim_ids[0]
    expected_item_ids = tuple(
        template.catalog["evidence_item_ids_by_claim"][claim_id]
    )
    if (
        len(required_item_ids) != len(expected_item_ids)
        or len(set(required_item_ids)) != len(required_item_ids)
        or set(required_item_ids) != set(expected_item_ids)
    ):
        raise AgentBoundaryError("evidence_checklist", "evidence_candidate_membership")
    return {
        "orchestrator_focus": _assigned_focus(
            state["orchestrator_plan"], "evidence_gaps"
        ),
        "accepted_process_gate_handoff": {
            "gate_id": "deterministic_process_gate",
            **{
                key: deepcopy(state["process"]["current_overlay"][key])
                for key in (
                    "completed_node_ids",
                    "current_node_id",
                    "selected_branch_id",
                    "blocked_node_ids",
                    "inactive_branch_ids",
                    "next_action_node_id",
                    "decisions",
                )
            },
        },
        "required_proposal_count": len(expected_item_ids),
        "required_item_ids": required_item_ids,
        "evidence_candidates": evidence_candidates,
        "allowed_statuses": EVIDENCE_STATUS_CANDIDATES,
        "selection_id_format": (
            "status::artifact_id+artifact_id; use status::none when no artifact "
            "is selected"
        ),
        "canonical_fact_handoff": [
            {
                "fact_id": fact["fact_id"],
                "label": fact["label"],
                "value": fact["value"],
                "state": fact["state"],
                "normalized_value": fact.get("normalized_value"),
                "source_artifact_ids": sorted(
                    {
                        ref["artifact_id"]
                        for ref in fact.get("source_refs", [])
                        if isinstance(ref.get("artifact_id"), str)
                    }
                ),
                "source_ref_ids": _expected_text_ref_ids(
                    fact.get("source_refs", []), state["source_registry"]
                ),
            }
            for fact in sorted(
                state["facts"], key=lambda value: focus_rank[value["fact_id"]]
            )
        ],
        "source_integrity_artifact_inventory": artifact_inventory,
    }


def _final_brief_provider_payload(state: AgentGraphState) -> dict[str, Any]:
    """Expose accepted handoffs for one bounded, independently scored audit."""

    source_items = state.get("source_integrity", {}).get("artifacts", [])
    process_items = state.get("process_mapping", {}).get("decisions", [])
    evidence_items = state.get("evidence_checklist", {}).get("items", [])
    focus_rank = {
        fact_id: index
        for index, fact_id in enumerate(state["orchestrator_plan"]["focus_fact_ids"])
    }
    canonical_items = sorted(
        state["facts"], key=lambda item: focus_rank[item["fact_id"]]
    )
    process_items = sorted(
        process_items, key=lambda item: focus_rank[item["fact_id"]]
    )
    return {
        "orchestrator_focus": _assigned_focus(
            state["orchestrator_plan"], "final_brief"
        ),
        "accepted_process_gate_handoff": {
            "gate_id": "deterministic_process_gate",
            "current_overlay": deepcopy(state["process"]["current_overlay"]),
        },
        "accepted_evidence_gate_handoff": {
            "gate_id": "deterministic_evidence_gate",
            "item_ids": sorted(item["item_id"] for item in evidence_items),
            "fallback_unit_ids": sorted(
                contribution["contribution_id"]
                for item in evidence_items
                for contribution in item.get("field_contributions", [])
                if contribution.get("deterministic_fallback_applied") is True
            ),
        },
        "static_process_topology": {
            "nodes": [
                {
                    "node_id": node["node_id"],
                    "title": node["title"],
                    "kind": node["kind"],
                    "main_spine": node["main_spine"],
                    "fact_ids": list(node.get("fact_ids", [])),
                    "activation": node.get("activation", "always"),
                    "branches": [
                        {
                            key: branch[key]
                            for key in ("branch_id", "label", "condition", "target")
                            if key in branch
                        }
                        for branch in node.get("branches", [])
                    ],
                }
                for node in state["process"]["nodes"]
            ],
            "edges": [
                {
                    key: edge[key]
                    for key in ("source", "target", "condition")
                    if key in edge
                }
                for edge in state["process"]["edges"]
            ],
            "evidence_bindings": [
                {
                    "item_id": item["item_id"],
                    "fact_id": item["fact_id"],
                    "node_id": item["node_id"],
                }
                for item in state["checklist"]["items"]
            ],
        },
        "canonical_fact_handoff": [
            {
                "fact_id": fact["fact_id"],
                "label": fact["label"],
                "state": fact["state"],
                "normalized_value": fact.get("normalized_value"),
                "source_ref_ids": _expected_text_ref_ids(
                    fact.get("source_refs", []), state["source_registry"]
                ),
            }
            for fact in canonical_items
        ],
        "prior_accepted_contributions": {
            "document_source_integrity": {
                "artifact_ids": [item["artifact_id"] for item in source_items],
                "source_ref_ids": sorted(
                    {
                        source_id
                        for item in source_items
                        for source_id in item.get("source_ref_ids", [])
                    }
                ),
                "fallback_artifact_ids": [
                    item["artifact_id"]
                    for item in source_items
                    if item.get("deterministic_fallback_applied") is True
                ],
            },
            "process_decision_mapping": {
                "decisions": [
                    {
                        key: item[key]
                        for key in (
                            "fact_id",
                            "state",
                            "normalized_value",
                            "decision_value",
                            "source_ref_ids",
                            "confidence_basis_points",
                            "contribution_scope",
                            "deterministic_fallback_applied",
                        )
                        if key in item
                    }
                    for item in process_items
                ]
            },
            "evidence_checklist": {
                "item_ids": [item["item_id"] for item in evidence_items],
                "source_ref_ids": sorted(
                    {
                        source_id
                        for item in evidence_items
                        for source_id in item.get("source_ref_ids", [])
                    }
                ),
                "fallback_item_ids": [
                    item["item_id"]
                    for item in evidence_items
                    if item.get("deterministic_fallback_applied") is True
                ],
            },
        },
        "audit_check_candidates": [
            {
                "audit_check_id": check_id,
                "requirement": {
                    "current_node_supported_by_canonical_facts": (
                        "The current node is bound to the supplied canonical facts."
                    ),
                    "next_action_connected_in_static_topology": (
                        "The next action is connected from the accepted current route."
                    ),
                    "evidence_items_bound_to_process_nodes": (
                        "Every supplied evidence item is bound to a static process node."
                    ),
                    "upstream_contribution_lineage_complete": (
                        "All three required upstream specialist contribution IDs are present."
                    ),
                }[check_id],
            }
            for check_id in FINAL_AUDIT_CHECK_IDS
        ],
    }
def _raw_metadata(raw: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    if isinstance(raw, Mapping):
        response_metadata = raw.get("response_metadata")
        usage_metadata = raw.get("usage_metadata")
    else:
        response_metadata = getattr(raw, "response_metadata", None)
        usage_metadata = getattr(raw, "usage_metadata", None)
    return (
        dict(response_metadata) if isinstance(response_metadata, Mapping) else {},
        dict(usage_metadata) if isinstance(usage_metadata, Mapping) else {},
    )


def _partial_provider_identity(raw: Any) -> dict[str, Any]:
    response_metadata, _ = _raw_metadata(raw)
    sanitized, violation = sanitize_provider_provenance(
        response_id=response_metadata.get("id"),
        response_model=response_metadata.get("model_name") or response_metadata.get("model"),
        upstream_provider=response_metadata.get("provider_name")
        or response_metadata.get("upstream_provider"),
        finish_reason=response_metadata.get("finish_reason"),
    )
    return {
        "response_id": sanitized["response_id"],
        "response_model": sanitized["response_model"],
        "response_finish_reason": sanitized["finish_reason"],
        "upstream_provider": sanitized["upstream_provider"],
        "provenance_violation": violation,
    }


def _validate_provider_identity(identity: Mapping[str, Any]) -> None:
    if identity.get("provenance_violation") is not None:
        raise AgentBoundaryError("provider", "invalid_provenance")
    if identity.get("response_id") is None:
        raise AgentBoundaryError("provider", "response_identity")
    if identity.get("response_model") not in OPENROUTER_ACCEPTED_RESPONSE_MODELS:
        raise AgentBoundaryError("provider", "response_model")


def _response_usage(raw: Any, *, identity: dict[str, Any], latency_ms: float) -> dict[str, Any] | None:
    response_metadata, usage_metadata = _raw_metadata(raw)
    usage = response_metadata.get("usage")
    if not isinstance(usage, Mapping):
        usage = response_metadata.get("token_usage")
    usage = dict(usage) if isinstance(usage, Mapping) else {}
    prompt_tokens = usage.get("prompt_tokens", usage_metadata.get("input_tokens"))
    completion_tokens = usage.get("completion_tokens", usage_metadata.get("output_tokens"))
    total_tokens = usage.get("total_tokens", usage_metadata.get("total_tokens"))
    cost = usage.get("cost", response_metadata.get("cost"))
    upstream_provider = identity.get("upstream_provider")
    if (
        not isinstance(prompt_tokens, int)
        or isinstance(prompt_tokens, bool)
        or prompt_tokens <= 0
        or not isinstance(completion_tokens, int)
        or isinstance(completion_tokens, bool)
        or completion_tokens <= 0
        or not isinstance(total_tokens, int)
        or isinstance(total_tokens, bool)
        or total_tokens < prompt_tokens + completion_tokens
        or not isinstance(cost, (int, float))
        or isinstance(cost, bool)
        or not math.isfinite(float(cost))
        or float(cost) <= 0
    ):
        return None
    patch = {
        "latency_ms": latency_ms,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "actual_cost_usd": float(cost),
        "usage_source": "response",
        "finish_reason": identity["response_finish_reason"],
    }
    if upstream_provider is not None:
        patch["upstream_provider"] = upstream_provider
    if identity.get("response_id") is not None:
        patch["response_id"] = identity["response_id"]
    if identity.get("response_model") is not None:
        patch["response_model"] = identity["response_model"]
    return patch


def _model_dump(value: Any) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return dict(value)
    raise AgentBoundaryError("provider", "structured_response")


def _default_runnable_factory(
    agent_id: str,
    schema: type[BaseModel],
    api_key: str,
    orchestration_id: str,
    max_tokens: int,
) -> StructuredRunnable:
    # A structured runnable is used instead of a tool-loop agent so each graph node
    # makes exactly one provider-native schema call with no parsing/tool retries.
    return structured_nemotron_runnable(
        schema=schema,
        api_key=api_key,
        orchestration_id=orchestration_id,
        max_tokens=max_tokens,
        reasoning=ROLE_REASONING[agent_id],
    )


def _diagnostics(
    accepted_ids: list[str],
    rejected: list[dict[str, str]],
    *,
    ignored_count: int = 0,
) -> dict[str, Any]:
    return {
        "authority_mode": MULTI_AGENT_AUTHORITY_MODE,
        "accepted_item_ids": accepted_ids,
        "accepted_item_count": len(accepted_ids),
        "rejected_items": rejected,
        "rejected_item_count": len(rejected),
        "ignored_proposal_count": ignored_count,
        "deterministic_fallback_applied": bool(rejected),
    }


def _require_contribution_majority(agent_id: str, diagnostics: Mapping[str, Any]) -> None:
    accepted = diagnostics.get("accepted_item_count")
    rejected = diagnostics.get("rejected_item_count")
    if (
        not isinstance(accepted, int)
        or isinstance(accepted, bool)
        or not isinstance(rejected, int)
        or isinstance(rejected, bool)
        or accepted <= rejected
    ):
        raise AgentBoundaryError(agent_id, "model_contribution_majority")


def _compatible_process_decision_values(
    fact: Mapping[str, Any],
    *,
    template: PlaybookTemplate = MOULD_PLAYBOOK_TEMPLATE,
) -> set[str]:
    decision_key = fact.get("decision_key")
    normalized_value = fact.get("normalized_value")
    try:
        exact = template.decision_options[decision_key][normalized_value]
    except (KeyError, TypeError) as exc:
        raise AgentBoundaryError(
            "process_decision_mapping", "accepted_fact_decision_binding"
        ) from exc
    fail_closed_normalized = template.fail_closed_normalized_values[decision_key]
    conservative = template.decision_options[decision_key][
        fail_closed_normalized
    ]
    # A specialist may preserve the exact assertion or conservatively stop at
    # the key's unresolved outcome. It may never choose a contradictory branch.
    return {exact, conservative}


def apply_process_contribution(
    process: Mapping[str, Any],
    contribution: Mapping[str, Any],
    canonical_facts: list[dict[str, Any]],
    *,
    template: PlaybookTemplate = MOULD_PLAYBOOK_TEMPLATE,
) -> dict[str, Any]:
    """Reproject a process from accepted-or-fallback specialist decision units."""

    expected = {
        fact["fact_id"]: fact
        for fact in canonical_facts
        if fact.get("controls_process") is True
    }
    decisions = contribution.get("decisions")
    if not isinstance(decisions, list):
        raise AgentBoundaryError("deterministic_process_gate", "process_contribution")
    by_fact = {
        item.get("fact_id"): item
        for item in decisions
        if isinstance(item, Mapping) and isinstance(item.get("fact_id"), str)
    }
    if len(by_fact) != len(decisions) or set(by_fact) != set(expected):
        raise AgentBoundaryError(
            "deterministic_process_gate", "process_fact_membership"
        )
    projection_facts: list[dict[str, Any]] = []
    for fact_id, fact in expected.items():
        item = by_fact[fact_id]
        if item.get("decision_key") != fact.get("decision_key") or item.get(
            "decision_value"
        ) not in _compatible_process_decision_values(fact, template=template):
            raise AgentBoundaryError(
                "deterministic_process_gate", "canonical_decision_binding"
            )
        projection_facts.append(
            {
                "controls_process": True,
                "decision_key": item["decision_key"],
                "decision_value": item["decision_value"],
            }
        )
    projection = decision_projection(
        projection_facts, route_program=template.route_program
    )
    accepted = deepcopy(dict(process))
    accepted["nodes"] = deepcopy(list(process["nodes"]))
    accepted["edges"] = deepcopy(list(process["edges"]))
    overlay = apply_process_projection(
        accepted["nodes"],
        accepted["edges"],
        projection,
        list(process["main_spine"]),
        rendering_profile=template.process_rendering_profile,
    )
    accepted["current_node"] = projection["current_node"]
    accepted["selected_path"] = list(projection["selected_path"])
    accepted["current_overlay"] = overlay
    return accepted


def apply_evidence_contribution(
    checklist: Mapping[str, Any],
    contribution: Mapping[str, Any],
    *,
    candidate_artifact_ids_by_item: Mapping[str, list[str]],
) -> dict[str, Any]:
    """Build the accepted checklist from model-owned or fallback field units."""

    proposed = contribution.get("items")
    if not isinstance(proposed, list):
        raise AgentBoundaryError(
            "deterministic_evidence_gate", "evidence_contribution"
        )
    by_id = {
        item.get("item_id"): item
        for item in proposed
        if isinstance(item, Mapping) and isinstance(item.get("item_id"), str)
    }
    source_items = checklist.get("items")
    if not isinstance(source_items, list):
        raise AgentBoundaryError("deterministic_evidence_gate", "evidence_items")
    expected_ids = {item["item_id"] for item in source_items}
    if len(by_id) != len(proposed) or set(by_id) != expected_ids:
        raise AgentBoundaryError(
            "deterministic_evidence_gate", "evidence_item_membership"
        )
    accepted = deepcopy(dict(checklist))
    accepted_items: list[dict[str, Any]] = []
    for source in source_items:
        item = deepcopy(source)
        effective = by_id[item["item_id"]]
        status = effective.get("status")
        artifact_ids = effective.get("artifact_ids")
        if status not in EVIDENCE_STATUS_CANDIDATES or not isinstance(
            artifact_ids, list
        ):
            raise AgentBoundaryError(
                "deterministic_evidence_gate", "evidence_effective_fields"
            )
        if (
            any(not isinstance(value, str) for value in artifact_ids)
            or len(set(artifact_ids)) != len(artifact_ids)
            or artifact_ids != sorted(artifact_ids)
        ):
            raise AgentBoundaryError(
                "deterministic_evidence_gate", "evidence_artifact_order"
            )
        effective_candidates = candidate_artifact_ids_by_item.get(item["item_id"])
        if (
            not isinstance(effective_candidates, list)
            or any(not isinstance(value, str) for value in effective_candidates)
            or effective_candidates != sorted(set(effective_candidates))
        ):
            raise AgentBoundaryError(
                "deterministic_evidence_gate", "evidence_candidate_catalog"
            )
        candidate_artifact_ids = set(effective_candidates)
        if set(artifact_ids) - candidate_artifact_ids:
            raise AgentBoundaryError(
                "deterministic_evidence_gate", "evidence_candidate_binding"
            )
        if artifact_ids:
            coherent_statuses = {
                "provided_sufficient",
                "provided_insufficient",
            }
            if source.get("required_level") == "conditional":
                coherent_statuses.add("conditional")
        elif source.get("required_level") == "mandatory":
            coherent_statuses = {"missing"}
        else:
            coherent_statuses = {"conditional", "not_applicable"}
        if status not in coherent_statuses:
            raise AgentBoundaryError(
                "deterministic_evidence_gate", "evidence_status_coherence"
            )
        item["status"] = status
        selected_ids = set(artifact_ids)
        source_order = [
            artifact_id
            for artifact_id in source.get("artifact_ids", [])
            if artifact_id in selected_ids
        ]
        item["artifact_ids"] = [
            *source_order,
            *sorted(selected_ids - set(source_order)),
        ]
        accepted_items.append(item)
    accepted["items"] = accepted_items
    accepted.update(checklist_derived_sections(accepted_items))
    return accepted


@dataclass
class InstrumentedStructuredAgent:
    storage: Storage
    runnable_factory: RunnableFactory = _default_runnable_factory
    metadata_transport: MetadataTransport = _default_metadata_transport
    api_key_provider: Callable[[], str | None] = lambda: os.getenv("OPENROUTER_API_KEY")
    metadata_sleep: Callable[[float], None] = sleep

    def invoke(
        self,
        *,
        run_id: str,
        orchestration_id: str,
        agent_id: str,
        schema: type[BaseModel],
        system_prompt: str,
        provider_payload: dict[str, Any],
        validator: ContributionValidator,
        private_contract_hash: str,
        parent_call_id: str | None = None,
        delegation_id: str | None = None,
        progress_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        if agent_id not in MODEL_AGENT_IDS:
            raise AgentBoundaryError(agent_id, "registered_agent")
        cache_key = _safe_hash(
            {
                "implementation": MULTI_AGENT_IMPLEMENTATION,
                "version": MULTI_AGENT_VERSION,
                "model": OPENROUTER_MODEL,
                "agent_id": agent_id,
                "schema": schema.model_json_schema(),
                "system_prompt_sha256": sha256(
                    system_prompt.encode("utf-8")
                ).hexdigest(),
                "max_tokens": ROLE_OUTPUT_TOKENS[agent_id],
                "reasoning": ROLE_REASONING[agent_id],
                "provider_policy": openrouter_provider_policy(),
                "payload": provider_payload,
                "private_contract_hash": private_contract_hash,
            }
        )
        with _cache_lock(cache_key):
            cached = self.storage.cached_model_output(cache_key)
            if isinstance(cached, dict):
                contribution = cached.get("contribution")
                diagnostics = cached.get("diagnostics")
                origin = cached.get("origin")
                if isinstance(contribution, dict) and isinstance(diagnostics, dict):
                    _require_contribution_majority(agent_id, diagnostics)
                    origin = origin if isinstance(origin, dict) else {}
                    call_id = self.storage.create_model_call(
                        run_id=run_id,
                        provider=OPENROUTER_PROVIDER,
                        model=OPENROUTER_MODEL,
                        cache_key=cache_key,
                        purpose=ROLE_PURPOSES[agent_id],
                        call_count=0,
                        estimated_cost_usd=0,
                        outcome="cache_hit",
                        provider_endpoint=OPENROUTER_URL,
                        implementation=MULTI_AGENT_IMPLEMENTATION,
                        orchestration_id=orchestration_id,
                        agent_id=agent_id,
                        agent_role=ROLE_LABELS[agent_id],
                        parent_call_id=parent_call_id,
                        delegation_id=delegation_id,
                    )
                    cache_provenance = {
                        key: origin[key]
                        for key in (
                            "origin_call_id",
                            "response_id",
                            "response_model",
                            "upstream_provider",
                            "origin_usage",
                            "origin_finish_reason",
                        )
                        if key in origin
                    }
                    self.storage.finish_model_call(
                        call_id,
                        outcome="cache_hit",
                        **diagnostics,
                        **cache_provenance,
                        usage_source="cache",
                        finish_reason=origin.get("origin_finish_reason"),
                    )
                    return {
                        "contribution": contribution,
                        "diagnostics": diagnostics,
                        "call_id": call_id,
                        "cache_key": cache_key,
                        "cache_hit": True,
                        "outcome": "cache_hit",
                        **cache_provenance,
                        "usage_source": "cache",
                    }
            return self._invoke_uncached(
                run_id=run_id,
                orchestration_id=orchestration_id,
                agent_id=agent_id,
                schema=schema,
                system_prompt=system_prompt,
                provider_payload=provider_payload,
                validator=validator,
                cache_key=cache_key,
                parent_call_id=parent_call_id,
                delegation_id=delegation_id,
                progress_sink=progress_sink,
            )

    def _invoke_uncached(
        self,
        *,
        run_id: str,
        orchestration_id: str,
        agent_id: str,
        schema: type[BaseModel],
        system_prompt: str,
        provider_payload: dict[str, Any],
        validator: ContributionValidator,
        cache_key: str,
        parent_call_id: str | None,
        delegation_id: str | None,
        progress_sink: Callable[[dict[str, Any]], None] | None,
    ) -> dict[str, Any]:
        assert_external_tracing_disabled()
        user_prompt = _json(provider_payload)
        provider_schema = _json(schema.model_json_schema())
        max_tokens = ROLE_OUTPUT_TOKENS[agent_id]
        estimated_tokens = _input_token_estimate(
            system_prompt + "\n" + user_prompt + "\n" + provider_schema
        )
        estimated_cost = _estimated_cost(estimated_tokens, max_tokens)
        cap = cumulative_usd_cap()
        key = self.api_key_provider()
        with self.storage.lock:
            if self.storage.model_cost_committed_or_reserved() + estimated_cost > cap:
                blocked_call_id = self.storage.create_model_call(
                    run_id=run_id,
                    provider=OPENROUTER_PROVIDER,
                    model=OPENROUTER_MODEL,
                    cache_key=cache_key,
                    purpose=ROLE_PURPOSES[agent_id],
                    call_count=0,
                    estimated_cost_usd=estimated_cost,
                    outcome="blocked_cost_guard",
                    provider_endpoint=OPENROUTER_URL,
                    implementation=MULTI_AGENT_IMPLEMENTATION,
                    orchestration_id=orchestration_id,
                    agent_id=agent_id,
                    agent_role=ROLE_LABELS[agent_id],
                    parent_call_id=parent_call_id,
                    delegation_id=delegation_id,
                )
                raise AgentInvocationFailure(
                    agent_id,
                    "cost_guard",
                    safe_context={
                        "call_id": blocked_call_id,
                        "parent_call_id": parent_call_id,
                        "delegation_id": delegation_id,
                        "outcome": "blocked_cost_guard",
                    },
                )
            if not key:
                blocked_call_id = self.storage.create_model_call(
                    run_id=run_id,
                    provider=OPENROUTER_PROVIDER,
                    model=OPENROUTER_MODEL,
                    cache_key=cache_key,
                    purpose=ROLE_PURPOSES[agent_id],
                    call_count=0,
                    estimated_cost_usd=estimated_cost,
                    outcome="blocked_missing_credential",
                    provider_endpoint=OPENROUTER_URL,
                    implementation=MULTI_AGENT_IMPLEMENTATION,
                    orchestration_id=orchestration_id,
                    agent_id=agent_id,
                    agent_role=ROLE_LABELS[agent_id],
                    parent_call_id=parent_call_id,
                    delegation_id=delegation_id,
                )
                raise AgentInvocationFailure(
                    agent_id,
                    "missing_credential",
                    safe_context={
                        "call_id": blocked_call_id,
                        "parent_call_id": parent_call_id,
                        "delegation_id": delegation_id,
                        "outcome": "blocked_missing_credential",
                    },
                )
            call_id = self.storage.create_model_call(
                run_id=run_id,
                provider=OPENROUTER_PROVIDER,
                model=OPENROUTER_MODEL,
                cache_key=cache_key,
                purpose=ROLE_PURPOSES[agent_id],
                call_count=1,
                estimated_cost_usd=estimated_cost,
                outcome="started",
                provider_endpoint=OPENROUTER_URL,
                implementation=MULTI_AGENT_IMPLEMENTATION,
                orchestration_id=orchestration_id,
                agent_id=agent_id,
                agent_role=ROLE_LABELS[agent_id],
                parent_call_id=parent_call_id,
                delegation_id=delegation_id,
            )
        if progress_sink is not None:
            progress_sink(
                {
                    "receipt_type": "agent_started",
                    "agent_id": agent_id,
                    "role": ROLE_LABELS[agent_id],
                    "actor_type": "nemotron_agent",
                    "delegation_id": delegation_id,
                    "parent_call_id": parent_call_id,
                    "call_id": call_id,
                    "call_count": 1,
                    "cache_hit": False,
                    "status": "started",
                    "handoff_from": ROLE_HANDOFFS[agent_id][0],
                    "handoff_to": ROLE_HANDOFFS[agent_id][1],
                    "input_artifact": "bounded_provider_payload",
                    "input_artifact_hash": _safe_hash(provider_payload),
                }
            )
        started = perf_counter()
        provider_patch: dict[str, Any] = {}
        finished = False
        try:
            runnable = self.runnable_factory(agent_id, schema, key, orchestration_id, max_tokens)
            assert_external_tracing_disabled()
            response = runnable.invoke(
                [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)],
                # Empty callbacks prevent LangSmith/global callback persistence. The
                # sanitized SQLite model-call ledger is the sole audit sink.
                config={"callbacks": []},
            )
            if not isinstance(response, Mapping):
                raise AgentBoundaryError(agent_id, "structured_response_envelope")
            raw = response.get("raw")
            latency_ms = round((perf_counter() - started) * 1000, 3)
            identity = _partial_provider_identity(raw)
            provider_patch = {"latency_ms": latency_ms}
            if identity["response_id"] is not None:
                provider_patch["response_id"] = identity["response_id"]
            if identity["response_model"] is not None:
                provider_patch["response_model"] = identity["response_model"]
            if identity["response_finish_reason"] is not None:
                provider_patch["finish_reason"] = identity["response_finish_reason"]
            if identity["provenance_violation"] is not None:
                provider_patch.update(identity["provenance_violation"])
            usage = _response_usage(raw, identity=identity, latency_ms=latency_ms)
            if usage is not None:
                provider_patch.update(usage)
            needs_metadata = usage is None or (
                identity["provenance_violation"] is None
                and (
                    identity.get("response_finish_reason") is None
                    or identity.get("upstream_provider") is None
                )
            )
            if needs_metadata and identity["response_id"] is not None:
                metadata_patch = _generation_metadata_ledger_patch(
                    identity=identity,
                    headers={"Authorization": f"Bearer {key}"},
                    metadata_transport=self.metadata_transport,
                    metadata_sleep=self.metadata_sleep,
                    timeout_seconds=GENERATION_METADATA_TIMEOUT_SECONDS,
                    poll_attempts=GENERATION_METADATA_POLL_ATTEMPTS,
                    poll_interval_seconds=GENERATION_METADATA_POLL_INTERVAL_SECONDS,
                    latency_ms=latency_ms,
                )
                provider_patch.update(metadata_patch)
                if identity["response_finish_reason"] is not None:
                    provider_patch["finish_reason"] = identity[
                        "response_finish_reason"
                    ]
            if "actual_cost_usd" in provider_patch:
                with self.storage.lock:
                    self.storage.finish_model_call(
                        call_id, outcome="provider_succeeded", **provider_patch
                    )
                    actual_overrun = self.storage.model_actual_cost_total() > cap
            else:
                actual_overrun = False
            _validate_provider_identity(identity)
            if (
                provider_patch.get("generation_model") is not None
                and provider_patch["generation_model"]
                not in OPENROUTER_ACCEPTED_RESPONSE_MODELS
            ):
                raise AgentBoundaryError(agent_id, "generation_metadata_model")
            if "actual_cost_usd" not in provider_patch:
                raise AgentBoundaryError(agent_id, "generation_metadata_completeness")
            if (
                provider_patch.get("upstream_provider")
                != OPENROUTER_EXPECTED_UPSTREAM_PROVIDER
            ):
                raise AgentBoundaryError(agent_id, "upstream_provider_policy")
            if provider_patch.get("finish_reason") != "stop":
                raise AgentBoundaryError(agent_id, "provider_finish_reason")
            if response.get("parsing_error") is not None or response.get("parsed") is None:
                raise AgentBoundaryError(agent_id, "provider_native_schema")
            parsed = _model_dump(response["parsed"])
            contribution, diagnostics = validator(parsed)
            bounded_diagnostics = {
                key: diagnostics[key]
                for key in (
                    "authority_mode",
                    "accepted_item_ids",
                    "accepted_item_count",
                    "rejected_items",
                    "rejected_item_count",
                    "ignored_proposal_count",
                )
            }
            with self.storage.lock:
                self.storage.finish_model_call(
                    call_id,
                    outcome="provider_succeeded",
                    **provider_patch,
                    **bounded_diagnostics,
                )
            _require_contribution_majority(agent_id, diagnostics)
            outcome = (
                "succeeded"
                if diagnostics.get("rejected_item_count") == 0
                else "succeeded_with_guarded_fallback"
            )
            with self.storage.lock:
                self.storage.finish_model_call(
                    call_id,
                    outcome="actual_cost_overrun" if actual_overrun else outcome,
                    **provider_patch,
                    **diagnostics,
                    canonical_output={
                        "contribution": contribution,
                        "diagnostics": diagnostics,
                        "origin": {
                            "origin_call_id": call_id,
                            "response_id": provider_patch["response_id"],
                            "response_model": provider_patch["response_model"],
                            "upstream_provider": provider_patch["upstream_provider"],
                            "usage_source": provider_patch["usage_source"],
                            "origin_finish_reason": provider_patch["finish_reason"],
                            "origin_usage": {
                                "prompt_tokens": provider_patch["prompt_tokens"],
                                "completion_tokens": provider_patch["completion_tokens"],
                                "total_tokens": provider_patch["total_tokens"],
                                "actual_cost_usd": provider_patch["actual_cost_usd"],
                                "usage_source": provider_patch["usage_source"],
                            },
                        },
                    },
                )
            finished = True
            if actual_overrun:
                raise AgentInvocationFailure(
                    agent_id,
                    "actual_cost_overrun",
                    safe_context={
                        "call_id": call_id,
                        "parent_call_id": parent_call_id,
                        "delegation_id": delegation_id,
                        "outcome": "actual_cost_overrun",
                        **{
                            key: provider_patch[key]
                            for key in (
                                "response_id",
                                "response_model",
                                "upstream_provider",
                                "usage_source",
                                "finish_reason",
                            )
                        },
                    },
                )
            return {
                "contribution": contribution,
                "diagnostics": diagnostics,
                "call_id": call_id,
                "cache_key": cache_key,
                "cache_hit": False,
                "outcome": outcome,
                "origin_call_id": call_id,
                "response_id": provider_patch["response_id"],
                "response_model": provider_patch["response_model"],
                "upstream_provider": provider_patch["upstream_provider"],
                "usage_source": provider_patch["usage_source"],
                "finish_reason": provider_patch["finish_reason"],
                "usage": {
                    "prompt_tokens": provider_patch["prompt_tokens"],
                    "completion_tokens": provider_patch["completion_tokens"],
                    "total_tokens": provider_patch["total_tokens"],
                    "actual_cost_usd": provider_patch["actual_cost_usd"],
                    "usage_source": provider_patch["usage_source"],
                },
            }
        except Exception as exc:
            concurrency_blocked = isinstance(
                exc, OpenRouterSendAdmissionTimeoutError
            )
            if isinstance(exc, ModelResponseError):
                for key in (
                    "latency_ms",
                    "metadata_latency_ms",
                    "metadata_poll_count",
                    "prompt_tokens",
                    "completion_tokens",
                    "total_tokens",
                    "actual_cost_usd",
                    "usage_source",
                    "response_id",
                    "response_model",
                    "upstream_provider",
                    "finish_reason",
                    "invalid_provenance_field",
                    "invalid_provenance_value_hash",
                    "provider_error_code",
                    "provider_boundary",
                    "expected_upstream_provider",
                ):
                    if key in exc.safe_context:
                        provider_patch[key] = exc.safe_context[key]
            elif isinstance(exc, OpenRouterUpstreamRejectionError):
                provider_patch.update(exc.safe_context)
            if not finished:
                patch = {
                    **provider_patch,
                    "latency_ms": provider_patch.get(
                        "latency_ms", round((perf_counter() - started) * 1000, 3)
                    ),
                    "error_type": type(exc).__name__,
                    "error_agent_id": agent_id,
                }
                if concurrency_blocked:
                    patch["call_count"] = 0
                if isinstance(
                    exc,
                    (
                        AgentBoundaryError,
                        ModelResponseError,
                        OpenRouterProtocolError,
                        OpenRouterSendAdmissionTimeoutError,
                        OpenRouterUpstreamRejectionError,
                    ),
                ):
                    patch["error_invariant"] = exc.invariant
                self.storage.finish_model_call(
                    call_id,
                    outcome=(
                        "blocked_provider_concurrency"
                        if concurrency_blocked
                        else "failed"
                    ),
                    **patch,
                )
            if isinstance(exc, (ModelCostGuardError, AgentInvocationFailure)):
                raise
            invariant = (
                exc.invariant
                if isinstance(
                    exc,
                    (
                        AgentBoundaryError,
                        ModelResponseError,
                        OpenRouterProtocolError,
                        OpenRouterSendAdmissionTimeoutError,
                        OpenRouterUpstreamRejectionError,
                    ),
                )
                else "provider_invocation"
            )
            safe_context = {
                "call_id": call_id,
                "parent_call_id": parent_call_id,
                "delegation_id": delegation_id,
                "outcome": (
                    "blocked_provider_concurrency"
                    if concurrency_blocked
                    else "failed"
                ),
                **{
                    key: provider_patch[key]
                    for key in (
                        "response_id",
                        "response_model",
                        "upstream_provider",
                        "usage_source",
                        "finish_reason",
                        "invalid_provenance_field",
                        "invalid_provenance_value_hash",
                        "provider_error_code",
                        "provider_boundary",
                        "expected_upstream_provider",
                    )
                    if key in provider_patch
                },
            }
            raise AgentInvocationFailure(
                agent_id,
                invariant,
                safe_context=safe_context,
            ) from None


@dataclass(frozen=True, slots=True)
class DeterministicStructuredAgent:
    """Credential-, cache-, and network-free transport for the same StateGraph."""

    def invoke(
        self,
        *,
        run_id: str,
        orchestration_id: str,
        agent_id: str,
        schema: type[BaseModel],
        system_prompt: str,
        provider_payload: dict[str, Any],
        validator: ContributionValidator,
        private_contract_hash: str,
        private_contract: Any,
        parent_call_id: str | None = None,
        delegation_id: str | None = None,
        progress_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        del run_id, system_prompt, progress_sink
        if agent_id == "orchestrator_plan":
            response: dict[str, Any] = {
                "priority_fact_ids": [
                    value["fact_id"]
                    for value in provider_payload["fact_candidates"][:6]
                ],
                "priority_task_codes": list(provider_payload["task_codes"]),
            }
        elif agent_id == "document_source_integrity":
            response = {
                "proposals": [
                    {
                        **deepcopy(private_contract[artifact_id]),
                        "confidence_basis_points": 10_000,
                    }
                    for artifact_id in sorted(private_contract)
                ]
            }
        elif agent_id == "process_decision_mapping":
            handoff = {
                value["fact_id"]: value
                for value in provider_payload["canonical_fact_handoff"]
            }
            response = {
                "proposals": [
                    {
                        "fact_id": slot["fact_id"],
                        "decision_value": private_contract[
                            "decision_options"
                        ][slot["decision_key"]][
                            handoff[slot["fact_id"]]["normalized_value"]
                        ],
                        "confidence": 1.0,
                    }
                    for slot in private_contract["fact_slots"]
                ]
            }
        elif agent_id == "evidence_checklist":
            response = {
                "items": {
                    value["item_id"]: {
                        "selection_id": _evidence_selection_id(
                            value["status"], tuple(value["artifact_ids"])
                        ),
                        "confidence": 1.0,
                    }
                    for value in private_contract["item_catalog"]
                }
            }
        elif agent_id == "final_claim_brief_audit":
            response = {
                "proposal": {**deepcopy(private_contract), "confidence": 1.0}
            }
        else:  # pragma: no cover - graph registration is static
            raise AgentBoundaryError(agent_id, "deterministic_runner_role")
        validated = schema.model_validate(response).model_dump(mode="json")
        contribution, diagnostics = validator(validated)
        _require_contribution_majority(agent_id, diagnostics)
        call_id = "deterministic-cycle." + _safe_hash(
            {
                "orchestration_id": orchestration_id,
                "agent_id": agent_id,
                "provider_payload": provider_payload,
                "private_contract_hash": private_contract_hash,
                "parent_call_id": parent_call_id,
                "delegation_id": delegation_id,
            }
        )
        return {
            "contribution": contribution,
            "diagnostics": diagnostics,
            "call_id": call_id,
            "origin_call_id": call_id,
            "cache_hit": True,
            "outcome": "deterministic_test_double",
            "transport_mode": "deterministic_test_double",
            "response_id": None,
            "response_model": None,
            "upstream_provider": None,
            "usage_source": None,
            "usage": None,
            "finish_reason": "deterministic_test_double",
        }


def _proposal_map(values: Any, key: str, agent_id: str) -> tuple[dict[str, dict[str, Any]], int]:
    if not isinstance(values, list):
        raise AgentBoundaryError(agent_id, "proposal_list")
    mapped: dict[str, dict[str, Any]] = {}
    duplicates = 0
    for value in values:
        if not isinstance(value, dict) or not isinstance(value.get(key), str):
            raise AgentBoundaryError(agent_id, "proposal_shape")
        item_id = value[key]
        if item_id in mapped:
            duplicates += 1
        else:
            mapped[item_id] = value
    return mapped, duplicates


def _require_exact_proposal_membership(
    proposed: Mapping[str, Any],
    *,
    duplicates: int,
    expected_ids: set[str],
    agent_id: str,
    invariant: str,
) -> None:
    if duplicates or set(proposed) != expected_ids:
        raise AgentBoundaryError(agent_id, invariant)


def _plan_validator(
    *,
    canonical_fact_ids: list[str],
    deterministic_focus_source_ref_ids: list[str],
    required_text_artifact_ids: list[str],
) -> ContributionValidator:
    if len(set(canonical_fact_ids)) != len(canonical_fact_ids):
        raise AgentBoundaryError("orchestrator_plan", "canonical_fact_membership")
    allowed_fact_ids = set(canonical_fact_ids)
    allowed_task_codes = set(PRIORITY_TASK_CODES)

    def validate(value: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        priority_fact_ids = value.get("priority_fact_ids")
        task_codes = value.get("priority_task_codes")
        accepted = (
            isinstance(priority_fact_ids, list)
            and 1 <= len(priority_fact_ids) <= 6
            and all(isinstance(item, str) for item in priority_fact_ids)
            and len(set(priority_fact_ids)) == len(priority_fact_ids)
            and set(priority_fact_ids) <= allowed_fact_ids
            and isinstance(task_codes, list)
            and len(task_codes) == len(allowed_task_codes)
            and all(isinstance(item, str) for item in task_codes)
            and len(set(task_codes)) == len(task_codes)
            and set(task_codes) == allowed_task_codes
        )
        model_priority_fact_ids = list(priority_fact_ids) if accepted else []
        deterministic_fact_ids = (
            [
                fact_id
                for fact_id in canonical_fact_ids
                if fact_id not in model_priority_fact_ids
            ]
            if accepted
            else []
        )
        focus_fact_ids = (
            [*model_priority_fact_ids, *deterministic_fact_ids]
            if accepted
            else []
        )
        focus_source_ref_ids = (
            list(deterministic_focus_source_ref_ids) if accepted else []
        )
        contribution = {
            "model_priority_fact_ids": model_priority_fact_ids,
            "model_priority_task_codes": list(task_codes) if accepted else [],
            "priority_task_codes": list(task_codes) if accepted else [],
            "model_priority_attribution": (
                "Nemotron Orchestrator" if accepted else None
            ),
            "deterministic_coverage": {
                "fact_ids": deterministic_fact_ids,
                "source_ref_ids": focus_source_ref_ids,
                "required_text_artifact_ids": (
                    list(required_text_artifact_ids) if accepted else []
                ),
                "attribution": "deterministic_application",
            },
            "focus_fact_ids": focus_fact_ids,
            "focus_source_ref_ids": focus_source_ref_ids,
            "contribution_type": "constrained_focus_prioritization",
        }
        diagnostics = _diagnostics(
            ["model_priority_order"] if accepted else [],
            []
            if accepted
            else [
                {
                    "item_id": "model_priority_order",
                    "invariant": "bounded_priority_selection",
                }
            ],
        )
        diagnostics.update(
            {
                "model_priority_fact_ids": model_priority_fact_ids,
                "deterministic_coverage_fact_ids": deterministic_fact_ids,
                "derived_focus_fact_ids": focus_fact_ids,
                "derived_focus_source_ref_ids": focus_source_ref_ids,
            }
        )
        return contribution, diagnostics

    return validate


@dataclass
class NemotronMultiAgentOrchestrator:
    storage: Storage
    agent_runner: InstrumentedStructuredAgent | DeterministicStructuredAgent | None = None
    verification_builder: Callable[
        [dict[str, Any], dict[str, Any]], dict[str, Any]
    ] | None = None
    playbook_template: PlaybookTemplate = MOULD_PLAYBOOK_TEMPLATE

    def __post_init__(self) -> None:
        self.agent_runner = self.agent_runner or InstrumentedStructuredAgent(self.storage)
        builder = StateGraph(AgentGraphState)
        builder.add_node("canonical_facts", self._canonical_facts_node)
        builder.add_node("orchestrator_plan", self._orchestrator_plan_node)
        builder.add_node("document_source_integrity", self._source_integrity_node)
        builder.add_node("process_decision_mapping", self._process_mapping_node)
        builder.add_node("deterministic_process_gate", self._process_gate_node)
        builder.add_node("evidence_checklist", self._evidence_node)
        builder.add_node("deterministic_evidence_gate", self._evidence_gate_node)
        builder.add_node("final_claim_brief_audit", self._final_brief_node)
        builder.add_node("whole_playbook_gate", self._whole_playbook_gate_node)
        builder.add_edge(START, "canonical_facts")
        builder.add_edge("canonical_facts", "orchestrator_plan")
        builder.add_edge("orchestrator_plan", "document_source_integrity")
        builder.add_edge("orchestrator_plan", "process_decision_mapping")
        builder.add_edge(
            ["document_source_integrity", "process_decision_mapping"],
            "deterministic_process_gate",
        )
        builder.add_edge("deterministic_process_gate", "evidence_checklist")
        builder.add_edge("evidence_checklist", "deterministic_evidence_gate")
        builder.add_edge("deterministic_evidence_gate", "final_claim_brief_audit")
        builder.add_edge("final_claim_brief_audit", "whole_playbook_gate")
        builder.add_edge("whole_playbook_gate", END)
        self.graph = builder.compile()

    def invoke(
        self,
        *,
        run_id: str,
        orchestration_id: str,
        observable_package: dict[str, Any],
        canonicalization: dict[str, Any],
        facts: list[dict[str, Any]],
        process: dict[str, Any],
        checklist: dict[str, Any],
        verification: dict[str, Any],
        verification_builder: Callable[
            [dict[str, Any], dict[str, Any]], dict[str, Any]
        ]
        | None = None,
        progress_sink: Callable[[dict[str, Any]], None] | None = None,
        include_accepted_artifacts: bool = False,
    ) -> dict[str, Any]:
        input_state: AgentGraphState = {
            "run_id": run_id,
            "orchestration_id": orchestration_id,
            "playbook_template_sha256": self.playbook_template.template_sha256,
            "observable_package": observable_package,
            "canonicalization": canonicalization,
            "facts": facts,
            "process": process,
            "checklist": checklist,
            "verification": verification,
            "seed_process_hash": accepted_artifact_hash(process),
            "seed_checklist_hash": accepted_artifact_hash(checklist),
            "source_registry": _source_registry(observable_package),
            "audit_entries": [],
        }
        effective_verification_builder = (
            verification_builder or self.verification_builder
        )
        if effective_verification_builder is not None:
            input_state["verification_builder"] = effective_verification_builder
        audit: dict[str, Any] | None = None
        accepted_cycle_artifacts: dict[str, Any] | None = None
        assert_external_tracing_disabled()
        for chunk in self.graph.stream(
            input_state,
            {"max_concurrency": 2, "callbacks": []},
            stream_mode=["updates", "custom"],
            version="v2",
        ):
            if chunk.get("type") == "custom":
                receipt = chunk.get("data")
                if progress_sink is not None and isinstance(receipt, dict):
                    progress_sink(receipt)
                continue
            data = chunk.get("data")
            if not isinstance(data, dict):
                continue
            update = data.get("whole_playbook_gate")
            if isinstance(update, dict) and isinstance(update.get("orchestration_audit"), dict):
                audit = update["orchestration_audit"]
                value = update.get("accepted_cycle_artifacts")
                if isinstance(value, dict):
                    accepted_cycle_artifacts = value
        if audit is None:
            raise AgentBoundaryError("whole_playbook_gate", "stream_completion")
        if include_accepted_artifacts:
            if accepted_cycle_artifacts is None:
                raise AgentBoundaryError(
                    "whole_playbook_gate", "accepted_cycle_artifacts"
                )
            return {
                "orchestration_audit": audit,
                "accepted_cycle_artifacts": accepted_cycle_artifacts,
            }
        return audit

    @staticmethod
    def _canonical_facts_node(state: AgentGraphState) -> dict[str, Any]:
        canonicalization = state["canonicalization"]
        diagnostics = canonicalization.get("diagnostics", {})
        provider_free = (
            canonicalization.get("transport_mode") == "deterministic_test_double"
        )
        actor_type = (
            "deterministic_structured_agent"
            if provider_free
            else "nemotron_agent"
        )
        if (
            canonicalization.get("model") != OPENROUTER_MODEL
            or diagnostics.get("accepted_fact_count", 0)
            + diagnostics.get("rejected_fact_count", 0)
            != len(state["facts"])
        ):
            raise AgentBoundaryError("canonical_facts", "model_contribution")
        return {
            "audit_entries": [
                {
                    "stage": "understand",
                    "acceptance_scope": "pre_review_model_output",
                    "agent_id": "canonical_facts",
                    "role": "Guarded Canonical Facts Agent",
                    "actor_type": actor_type,
                    "model": None if provider_free else OPENROUTER_MODEL,
                    "provider": None if provider_free else OPENROUTER_PROVIDER,
                    "requested_model": None if provider_free else OPENROUTER_MODEL,
                    "transport_mode": canonicalization.get(
                        "transport_mode", "openrouter"
                    ),
                    "call_count": (
                        0 if provider_free or canonicalization.get("cache_hit") else 1
                    ),
                    "parent_call_id": None,
                    "delegation_id": None,
                    "call_id": canonicalization.get("call_id"),
                    "origin_call_id": canonicalization.get(
                        "origin_call_id", canonicalization.get("call_id")
                    ),
                    "response_id": canonicalization.get("response_id"),
                    "response_model": canonicalization.get("response_model"),
                    "upstream_provider": canonicalization.get("upstream_provider"),
                    "usage_source": canonicalization.get("usage_source"),
                    "finish_reason": canonicalization.get("finish_reason")
                    or canonicalization.get("origin_finish_reason"),
                    "usage": canonicalization.get("usage")
                    or canonicalization.get("origin_usage"),
                    "output_artifact": "canonical_claim_state",
                    "cache_hit": canonicalization.get("cache_hit", False),
                    "outcome": (
                        "cache_hit"
                        if canonicalization.get("cache_hit") is True
                        else "succeeded_with_guarded_fallback"
                        if diagnostics.get("rejected_fact_count")
                        else "succeeded"
                    ),
                    "accepted_count": diagnostics.get("accepted_fact_count"),
                    "accepted_ids": diagnostics.get("accepted_fact_ids", []),
                    "rejected_count": diagnostics.get("rejected_fact_count"),
                    "source_reference_projection_fact_ids": diagnostics.get(
                        "source_reference_projection_fact_ids", []
                    ),
                    "source_reference_projection_count": diagnostics.get(
                        "source_reference_projection_count", 0
                    ),
                    "deterministic_fallback_applied": bool(
                        diagnostics.get("deterministic_fallback_applied")
                    ),
                    "input_artifact_hash": _safe_hash(state["observable_package"]),
                    "output_artifact_hash": _safe_hash(state["facts"]),
                }
            ]
        }

    def _run_agent(
        self,
        state: AgentGraphState,
        *,
        agent_id: str,
        schema: type[BaseModel],
        system_prompt: str,
        provider_payload: dict[str, Any],
        validator: ContributionValidator,
        private_contract: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        assert self.agent_runner is not None
        deterministic_runner = isinstance(
            self.agent_runner, DeterministicStructuredAgent
        )
        attempted_actor_type = (
            "deterministic_structured_agent"
            if deterministic_runner
            else "nemotron_agent"
        )
        writer = get_stream_writer()
        delegation_id = f"dlg_{_safe_hash({'orchestration_id': state['orchestration_id'], 'agent_id': agent_id})[:20]}"
        parent_call_id = (
            state["canonicalization"].get("call_id")
            if agent_id == "orchestrator_plan"
            else state.get("orchestrator_call_id")
        )
        try:
            invocation = {
                "run_id": state["run_id"],
                "orchestration_id": state["orchestration_id"],
                "agent_id": agent_id,
                "schema": schema,
                "system_prompt": system_prompt,
                "provider_payload": provider_payload,
                "validator": validator,
                "private_contract_hash": _safe_hash(private_contract),
                "parent_call_id": parent_call_id,
                "delegation_id": delegation_id,
                "progress_sink": writer,
            }
            if isinstance(self.agent_runner, DeterministicStructuredAgent):
                result = self.agent_runner.invoke(
                    **invocation,
                    private_contract=deepcopy(private_contract),
                )
            else:
                result = self.agent_runner.invoke(**invocation)
        except Exception as exc:
            safe_context = (
                exc.safe_context
                if isinstance(exc, AgentInvocationFailure)
                else {}
            )
            failure_outcome = safe_context.get("outcome", "failed")
            writer(
                {
                    "receipt_type": "agent_failed",
                    "acceptance_scope": "pre_review_model_output",
                    "agent_id": agent_id,
                    "role": ROLE_LABELS[agent_id],
                    "actor_type": attempted_actor_type,
                    "model": None if deterministic_runner else OPENROUTER_MODEL,
                    "provider": None if deterministic_runner else OPENROUTER_PROVIDER,
                    "requested_model": (
                        None if deterministic_runner else OPENROUTER_MODEL
                    ),
                    "call_count": (
                        0
                        if failure_outcome
                        in {
                            "blocked_cost_guard",
                            "blocked_missing_credential",
                            "blocked_provider_concurrency",
                        }
                        else 0 if deterministic_runner else 1
                    ),
                    "delegation_id": delegation_id,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error_invariant": getattr(exc, "invariant", None),
                    "outcome": failure_outcome,
                    **{
                        key: safe_context[key]
                        for key in (
                            "call_id",
                            "parent_call_id",
                            "response_id",
                            "response_model",
                            "upstream_provider",
                            "usage_source",
                            "finish_reason",
                            "outcome",
                            "invalid_provenance_field",
                            "invalid_provenance_value_hash",
                            "provider_error_code",
                            "provider_boundary",
                            "expected_upstream_provider",
                        )
                        if key in safe_context
                    },
                    "handoff_from": ROLE_HANDOFFS[agent_id][0],
                    "handoff_to": "failure_boundary",
                    "input_artifact_hash": _safe_hash(provider_payload),
                }
            )
            raise
        diagnostics = result["diagnostics"]
        provider_free = result.get("transport_mode") == "deterministic_test_double"
        actor_type = (
            "deterministic_structured_agent"
            if provider_free
            else "nemotron_agent"
        )
        usage = result.get("usage") or result.get("origin_usage")
        audit = {
            "stage": agent_id,
            "acceptance_scope": "pre_review_model_output",
            "agent_id": agent_id,
            "role": ROLE_LABELS[agent_id],
            "actor_type": actor_type,
            "model": None if provider_free else OPENROUTER_MODEL,
            "provider": None if provider_free else OPENROUTER_PROVIDER,
            "requested_model": None if provider_free else OPENROUTER_MODEL,
            "transport_mode": result.get("transport_mode", "openrouter"),
            "call_count": 0 if provider_free or result["cache_hit"] else 1,
            "delegation_id": delegation_id,
            "parent_call_id": parent_call_id,
            "call_id": result["call_id"],
            "origin_call_id": result.get("origin_call_id", result["call_id"]),
            "cache_hit": result["cache_hit"],
            "outcome": result["outcome"],
            "response_model": result.get("response_model"),
            "upstream_provider": result.get("upstream_provider"),
            "usage_source": result.get("usage_source"),
            "response_id": result.get("response_id"),
            "finish_reason": result.get("finish_reason")
            or result.get("origin_finish_reason"),
            "usage": usage,
            "output_artifact": ROLE_OUTPUT_ARTIFACTS[agent_id],
            "accepted_ids": diagnostics["accepted_item_ids"],
            "accepted_count": diagnostics["accepted_item_count"],
            "rejected": diagnostics["rejected_items"],
            "rejected_count": diagnostics["rejected_item_count"],
            "deterministic_fallback_applied": diagnostics["deterministic_fallback_applied"],
            "input_artifact_hash": _safe_hash(provider_payload),
            "output_artifact_hash": _safe_hash(result["contribution"]),
        }
        writer(
            {
                "receipt_type": "agent_completed",
                "acceptance_scope": "pre_review_model_output",
                "agent_id": agent_id,
                "role": ROLE_LABELS[agent_id],
                "actor_type": actor_type,
                "delegation_id": delegation_id,
                "status": "completed",
                "call_id": result["call_id"],
                "parent_call_id": parent_call_id,
                "response_id": result.get("response_id"),
                "outcome": result["outcome"],
                "cache_hit": result["cache_hit"],
                "transport_mode": result.get("transport_mode", "openrouter"),
                "call_count": 0 if provider_free or result["cache_hit"] else 1,
                "response_model": result.get("response_model"),
                "upstream_provider": result.get("upstream_provider"),
                "usage_source": result.get("usage_source"),
                "accepted_count": diagnostics["accepted_item_count"],
                "rejected_count": diagnostics["rejected_item_count"],
                "deterministic_fallback_applied": diagnostics[
                    "deterministic_fallback_applied"
                ],
                "accepted_ids": diagnostics["accepted_item_ids"],
                "output_artifact": ROLE_OUTPUT_ARTIFACTS[agent_id],
                "handoff_from": ROLE_HANDOFFS[agent_id][0],
                "handoff_to": ROLE_HANDOFFS[agent_id][1],
                "output_artifact_hash": _safe_hash(result["contribution"]),
            }
        )
        return result["contribution"], audit

    def _orchestrator_plan_node(self, state: AgentGraphState) -> dict[str, Any]:
        canonical_fact_ids = [fact["fact_id"] for fact in state["facts"]]
        required_text_artifact_ids = sorted(
            {
                item["artifact_id"]
                for item in state["observable_package"].get("artifacts", [])
                if _integrity_class(item["media_type"]) == "text_grounded"
            }
        )
        deterministic_source_ref_ids = _deterministic_focus_source_ref_ids(
            state["source_registry"], required_text_artifact_ids
        )
        contribution, audit = self._run_agent(
            state,
            agent_id="orchestrator_plan",
            schema=OrchestratorPlan,
            system_prompt=(
                "Prioritize between one and six of the supplied observable fact IDs by consequence, then return "
                "an exact priority ordering of every supplied specialist task code. Return only those two bounded "
                "lists; the application adds mandatory fact and source coverage deterministically. Do not return "
                "topology, source references, expected decisions, legal conclusions, or prose."
            ),
            provider_payload={
                "schema_version": MULTI_AGENT_SCHEMA_VERSION,
                "max_priority_fact_count": 6,
                "fact_candidates": [
                    {"fact_id": fact["fact_id"], "label": fact["label"]}
                    for fact in state["facts"]
                ],
                "task_codes": list(PRIORITY_TASK_CODES),
            },
            validator=_plan_validator(
                canonical_fact_ids=canonical_fact_ids,
                deterministic_focus_source_ref_ids=deterministic_source_ref_ids,
                required_text_artifact_ids=required_text_artifact_ids,
            ),
            private_contract={
                "canonical_fact_ids": canonical_fact_ids,
                "deterministic_source_ref_ids": deterministic_source_ref_ids,
            },
        )
        audit.update(
            {
                "model_priority_fact_ids": contribution[
                    "model_priority_fact_ids"
                ],
                "model_priority_attribution": contribution[
                    "model_priority_attribution"
                ],
                "model_priority_task_codes": contribution[
                    "model_priority_task_codes"
                ],
                "deterministic_coverage": contribution[
                    "deterministic_coverage"
                ],
                "derived_focus_fact_ids": contribution["focus_fact_ids"],
                "derived_focus_source_ref_ids": contribution[
                    "focus_source_ref_ids"
                ],
            }
        )
        return {
            "orchestrator_plan": contribution,
            "orchestrator_call_id": audit["call_id"],
            "audit_entries": [audit],
        }

    def _source_integrity_node(self, state: AgentGraphState) -> dict[str, Any]:
        registry = state["source_registry"]
        registry_by_id = {item["source_ref_id"]: item for item in registry}
        focused_source_order = state["orchestrator_plan"]["focus_source_ref_ids"]
        focused_source_ids = set(focused_source_order)
        focused_refs_by_artifact: dict[str, list[str]] = {}
        for source_id in focused_source_order:
            ref = registry_by_id[source_id]
            focused_refs_by_artifact.setdefault(ref["artifact_id"], []).append(source_id)
        expected: dict[str, dict[str, Any]] = {}
        for artifact in state["observable_package"].get("artifacts", []):
            integrity_class = _integrity_class(artifact["media_type"])
            fallback_refs = focused_refs_by_artifact.get(artifact["artifact_id"], [])
            if integrity_class == "text_grounded" and not fallback_refs:
                raise AgentBoundaryError(
                    "document_source_integrity", "orchestrator_text_source_coverage"
                )
            expected[artifact["artifact_id"]] = {
                "artifact_id": artifact["artifact_id"],
                "integrity_class": integrity_class,
                # Private fallback is bounded to one plan-selected observable ref.
                "source_ref_ids": fallback_refs[:1] if integrity_class == "text_grounded" else [],
            }
        expected_count = len(expected)
        if expected_count < 1:
            raise AgentBoundaryError(
                "document_source_integrity", "source_candidate_membership"
            )

        def validate(value: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
            proposed, duplicates = _proposal_map(
                value.get("proposals"), "artifact_id", "document_source_integrity"
            )
            _require_exact_proposal_membership(
                proposed,
                duplicates=duplicates,
                expected_ids=set(expected),
                agent_id="document_source_integrity",
                invariant="source_proposal_membership",
            )
            accepted: list[str] = []
            rejected: list[dict[str, str]] = []
            output: list[dict[str, Any]] = []
            for item_id, oracle in expected.items():
                proposal = proposed.get(item_id)
                source_ids = proposal.get("source_ref_ids") if proposal is not None else None
                matches = (
                    proposal is not None
                    and proposal.get("artifact_id") == item_id
                    and proposal.get("integrity_class") == oracle["integrity_class"]
                    and isinstance(source_ids, list)
                    and len(set(source_ids)) == len(source_ids)
                    and set(source_ids) <= focused_source_ids
                    and all(
                        source_id in registry_by_id
                        and registry_by_id[source_id]["artifact_id"] == item_id
                        for source_id in source_ids
                    )
                    and (
                        bool(source_ids)
                        if oracle["integrity_class"] == "text_grounded"
                        else not source_ids
                    )
                )
                if matches:
                    accepted.append(item_id)
                else:
                    rejected.append({"item_id": item_id, "invariant": "source_integrity_contract"})
                output.append(
                    {
                        **oracle,
                        "source_ref_ids": source_ids if matches else oracle["source_ref_ids"],
                        "confidence_basis_points": (
                            proposal["confidence_basis_points"]
                            if matches
                            else 10_000
                        ),
                        "attribution": ROLE_LABELS["document_source_integrity"] if matches else "deterministic_application",
                        "deterministic_fallback_applied": not matches,
                    }
                )
            ignored = len(set(proposed) - set(expected)) + duplicates
            return {"artifacts": output}, _diagnostics(accepted, rejected, ignored_count=ignored)

        contribution, audit = self._run_agent(
            state,
            agent_id="document_source_integrity",
            schema=_bounded_source_integrity_schema(
                artifact_ids=tuple(expected),
                source_ref_ids=tuple(focused_source_order),
            ),
            system_prompt=(
                "Return exactly required_proposal_count proposals: exactly one for every required_artifact_id and no duplicates or "
                "omissions. Assess every supplied artifact using only its observable media class and a small nonempty "
                "subset of the orchestrator-selected source-reference IDs for each text artifact. Text IDs "
                "must belong to that artifact; copy exactly one matching ID for each text artifact, while visual "
                "and metadata-only artifacts use no text IDs. Return confidence_basis_points as an integer from "
                "0 through 10000. "
                "Never return an empty or partial proposal list. Return no prose, legal conclusions, process "
                "decisions, or hidden metadata."
            ),
            provider_payload={
                "orchestrator_focus": _assigned_focus(
                    state["orchestrator_plan"], "source_integrity"
                ),
                "required_proposal_count": expected_count,
                "required_artifact_ids": list(expected),
                "artifact_candidates": [
                    {"artifact_id": item["artifact_id"], "media_type": item["media_type"]}
                    for item in state["observable_package"].get("artifacts", [])
                ],
                "source_reference_registry": [
                    registry_by_id[source_id] for source_id in focused_source_order
                ],
            },
            validator=validate,
            private_contract=expected,
        )
        return {"source_integrity": contribution, "audit_entries": [audit]}

    def _process_mapping_node(self, state: AgentGraphState) -> dict[str, Any]:
        focus_rank = {
            fact_id: index
            for index, fact_id in enumerate(
                state["orchestrator_plan"]["focus_fact_ids"]
            )
        }
        controlling_facts: dict[str, dict[str, Any]] = {}
        for fact in state["facts"]:
            if fact.get("controls_process") is True:
                controlling_facts[fact["fact_id"]] = {
                    "fact_id": fact["fact_id"],
                    "decision_key": fact["decision_key"],
                    "decision_value": fact["decision_value"],
                    "state": fact["state"],
                    "normalized_value": fact["normalized_value"],
                    "source_ref_ids": _expected_text_ref_ids(
                        fact.get("source_refs", []), state["source_registry"]
                    ),
                }
        if (
            not controlling_facts
            or len(controlling_facts)
            > self.playbook_template.maximum_controlling_facts
        ):
            raise AgentBoundaryError(
                "process_decision_mapping", "process_candidate_membership"
            )
        canonical_fact_handoff = [
            {
                "fact_id": fact["fact_id"],
                "label": fact["label"],
                "state": fact["state"],
                "decision_key": fact["decision_key"],
                "normalized_value": fact["normalized_value"],
                "source_ref_ids": _expected_text_ref_ids(
                    fact.get("source_refs", []), state["source_registry"]
                ),
            }
            for fact in sorted(
                state["facts"], key=lambda item: focus_rank[item["fact_id"]]
            )
            if fact.get("controls_process") is True
        ]

        def validate(value: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
            proposed, duplicates = _proposal_map(
                value.get("proposals"), "fact_id", "process_decision_mapping"
            )
            _require_exact_proposal_membership(
                proposed,
                duplicates=duplicates,
                expected_ids=set(controlling_facts),
                agent_id="process_decision_mapping",
                invariant="process_proposal_membership",
            )
            accepted: list[str] = []
            rejected: list[dict[str, str]] = []
            output: list[dict[str, Any]] = []
            for item_id, accepted_fact in controlling_facts.items():
                proposal = proposed.get(item_id)
                contribution_id = f"fact:{item_id}:decision_value"
                compatible_decisions = _compatible_process_decision_values(
                    accepted_fact, template=self.playbook_template
                )
                matches = (
                    proposal is not None
                    and proposal.get("fact_id") == item_id
                    and proposal.get("decision_value") in compatible_decisions
                )
                if matches:
                    accepted.append(contribution_id)
                else:
                    rejected.append(
                        {
                            "item_id": contribution_id,
                            "invariant": "process_decision_contract",
                        }
                    )
                output.append(
                    {
                        **accepted_fact,
                        "decision_value": (
                            proposal["decision_value"]
                            if matches
                            else accepted_fact["decision_value"]
                        ),
                        "contribution_id": contribution_id,
                        "contribution_scope": "canonical_to_process_decision_mapping",
                        "model_owned_fields": ["decision_value"],
                        "confidence_basis_points": _confidence_basis_points(
                            proposal["confidence"] if matches else 1
                        ),
                        "attribution": ROLE_LABELS["process_decision_mapping"] if matches else "deterministic_application",
                        "deterministic_fallback_applied": not matches,
                    }
                )
            ignored = len(set(proposed) - set(controlling_facts)) + duplicates
            return {"decisions": output}, _diagnostics(accepted, rejected, ignored_count=ignored)

        contribution, audit = self._run_agent(
            state,
            agent_id="process_decision_mapping",
            schema=_bounded_process_decision_schema(
                controlling_facts, self.playbook_template.decision_options
            ),
            system_prompt=(
                "Return exactly required_proposal_count proposals: exactly one for every required_fact_id and no duplicates or omissions. "
                "Map every accepted canonical controlling fact to one bounded decision_value from the general "
                "vocabulary for its decision_key. Return only fact_id, decision_value, and confidence. Never return "
                "an empty or partial proposal list. The "
                "deterministic application verifies each mapping and reprojects the route; return no citations, "
                "raw evidence, process nodes, edges, current path, next action, expected values, or prose."
            ),
            provider_payload={
                "orchestrator_focus": _assigned_focus(
                    state["orchestrator_plan"], "process_decisions"
                ),
                "required_proposal_count": len(controlling_facts),
                "required_fact_ids": [
                    fact["fact_id"] for fact in canonical_fact_handoff
                ],
                "canonical_fact_handoff": canonical_fact_handoff,
                "decision_value_vocabulary": {
                    key: sorted(values.values())
                    for key, values in self.playbook_template.decision_options.items()
                },
            },
            validator=validate,
            private_contract={
                "fact_slots": [
                    {
                        "fact_id": fact_id,
                        "decision_key": value["decision_key"],
                    }
                    for fact_id, value in sorted(controlling_facts.items())
                ],
                "decision_options": self.playbook_template.decision_options,
            },
        )
        return {"process_mapping": contribution, "audit_entries": [audit]}

    def _process_gate_node(self, state: AgentGraphState) -> dict[str, Any]:
        writer = get_stream_writer()
        if not state.get("source_integrity", {}).get("artifacts"):
            raise AgentBoundaryError("deterministic_process_gate", "source_contribution")
        if not state.get("process_mapping", {}).get("decisions"):
            raise AgentBoundaryError("deterministic_process_gate", "process_contribution")
        accepted_process = apply_process_contribution(
            state["process"],
            state["process_mapping"],
            state["facts"],
            template=self.playbook_template,
        )
        accepted_checklist = deepcopy(state["checklist"])
        accepted_checklist["items"] = deepcopy(state["checklist"]["items"])
        apply_evidence_relations(accepted_process, accepted_checklist["items"])
        apply_evidence_projection(
            accepted_checklist["items"],
            accepted_process,
            projection_mode=self.playbook_template.evidence_projection_mode,
        )
        apply_evidence_relations(accepted_process, accepted_checklist["items"])
        accepted_checklist.update(
            checklist_derived_sections(accepted_checklist["items"])
        )
        current = accepted_process["current_overlay"]["current_node_id"]
        if current != accepted_process["current_node"]:
            raise AgentBoundaryError("deterministic_process_gate", "current_node")
        input_hash = _safe_hash(
            {"source_integrity": state["source_integrity"], "process_mapping": state["process_mapping"]}
        )
        output_hash = accepted_artifact_hash(accepted_process)
        writer(
            {
                "receipt_type": "gate_passed",
                "agent_id": "deterministic_process_gate",
                "role": "Deterministic Process Contract Gate",
                "actor_type": "deterministic_gate",
                "status": "completed",
                "handoff_from": "document_source_integrity+process_decision_mapping",
                "handoff_to": "evidence_checklist",
                "input_artifact": "parallel_specialist_contributions",
                "output_artifact": "verified_process_graph",
                "input_artifact_hash": input_hash,
                "output_artifact_hash": output_hash,
                "playbook_template_sha256": state[
                    "playbook_template_sha256"
                ],
            }
        )
        return {
            "process": accepted_process,
            "checklist": accepted_checklist,
            "audit_entries": [
                {
                    "agent_id": "deterministic_process_gate",
                    "role": "Deterministic Process Contract Gate",
                    "actor_type": "deterministic_gate",
                    "model": None,
                    "outcome": "passed",
                    "input_artifact_hash": input_hash,
                    "output_artifact_hash": output_hash,
                    "playbook_template_sha256": state[
                        "playbook_template_sha256"
                    ],
                }
            ]
        }

    def _evidence_node(self, state: AgentGraphState) -> dict[str, Any]:
        facts = {fact["fact_id"]: fact for fact in state["facts"]}
        allowed_artifact_ids = {
            "message",
            "intake",
            *(
                artifact["artifact_id"]
                for artifact in state["observable_package"].get("artifacts", [])
            ),
        }
        candidate_contracts: dict[str, dict[str, Any]] = {}
        candidate_artifact_ids_by_item = _evidence_candidate_artifact_ids(
            state, template=self.playbook_template
        )
        for item in state["checklist"]["items"]:
            fact = facts[item["fact_id"]]
            candidate_artifact_ids = candidate_artifact_ids_by_item[
                item["item_id"]
            ]
            if (
                len(set(candidate_artifact_ids)) != len(candidate_artifact_ids)
                or set(candidate_artifact_ids) - allowed_artifact_ids
            ):
                raise AgentBoundaryError(
                    "evidence_checklist", "evidence_candidate_artifacts"
                )
            if set(item.get("artifact_ids", [])) - set(candidate_artifact_ids):
                raise AgentBoundaryError(
                    "evidence_checklist", "evidence_reference_catalog_binding"
                )
            candidate_contracts[item["item_id"]] = {
                "item_id": item["item_id"],
                "fact_id": item["fact_id"],
                "required_level": item["required_level"],
                "current_path": item["current_path"],
                "candidate_artifact_ids": candidate_artifact_ids,
                "source_ref_ids": _expected_text_ref_ids(
                    fact.get("source_refs", []), state["source_registry"]
                ),
            }
        evidence_wire_schema = _bounded_evidence_checklist_schema(
            candidate_contracts
        )
        source_items = {
            item["item_id"]: item for item in state["checklist"]["items"]
        }

        def validate(value: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
            value = _normalize_evidence_checklist_response(
                value,
                candidate_contracts=candidate_contracts,
            )
            proposed, duplicates = _proposal_map(
                value.get("proposals"), "item_id", "evidence_checklist"
            )
            _require_exact_proposal_membership(
                proposed,
                duplicates=duplicates,
                expected_ids=set(candidate_contracts),
                agent_id="evidence_checklist",
                invariant="evidence_proposal_membership",
            )
            accepted: list[str] = []
            rejected: list[dict[str, str]] = []
            output: list[dict[str, Any]] = []
            for item_id, contract in candidate_contracts.items():
                proposal = proposed.get(item_id)
                proposed_artifacts = (
                    proposal.get("artifact_ids") if proposal is not None else None
                )
                artifacts_well_formed = (
                    isinstance(proposed_artifacts, list)
                    and all(isinstance(value, str) for value in proposed_artifacts)
                    and len(set(proposed_artifacts)) == len(proposed_artifacts)
                    and set(proposed_artifacts) <= allowed_artifact_ids
                    and set(proposed_artifacts)
                    <= set(contract["candidate_artifact_ids"])
                )
                canonical_artifacts = (
                    sorted(proposed_artifacts) if artifacts_well_formed else []
                )
                proposed_status = proposal.get("status") if proposal is not None else None
                coherent_statuses = set(
                    _coherent_evidence_statuses(
                        required_level=contract["required_level"],
                        has_artifacts=bool(canonical_artifacts),
                    )
                )
                status_matches = (
                    proposal is not None
                    and proposed_status in coherent_statuses
                )
                artifacts_match = proposal is not None and artifacts_well_formed
                pair_matches = status_matches and artifacts_match
                status_id = f"item:{item_id}:status"
                artifacts_id = f"item:{item_id}:artifacts"
                field_contributions: list[dict[str, Any]] = []
                for contribution_id, field in (
                    (status_id, "status"),
                    (artifacts_id, "artifact_ids"),
                ):
                    if pair_matches:
                        accepted.append(contribution_id)
                    else:
                        rejected.append(
                            {
                                "item_id": contribution_id,
                                "invariant": "evidence_contract",
                            }
                        )
                    field_contributions.append(
                        {
                            "contribution_id": contribution_id,
                            "field": field,
                            "attribution": (
                                ROLE_LABELS["evidence_checklist"]
                                if pair_matches
                                else "deterministic_application"
                            ),
                            "confidence_basis_points": _confidence_basis_points(
                                proposal["confidence"]
                                if pair_matches and proposal is not None
                                else 1
                            ),
                            "deterministic_fallback_applied": not pair_matches,
                        }
                    )
                fallback = source_items[item_id]
                output.append(
                    {
                        "item_id": item_id,
                        "source_ref_ids": contract["source_ref_ids"],
                        "status": (
                            proposal["status"] if pair_matches else fallback["status"]
                        ),
                        "artifact_ids": (
                            canonical_artifacts
                            if pair_matches
                            else sorted(fallback.get("artifact_ids", []))
                        ),
                        "field_contributions": field_contributions,
                        "model_owned_fields": ["status", "artifact_ids"],
                        "confidence_basis_points": _confidence_basis_points(
                            proposal["confidence"] if proposal is not None else 1
                        ),
                        "attribution": (
                            ROLE_LABELS["evidence_checklist"]
                            if pair_matches
                            else "deterministic_application"
                        ),
                        "deterministic_fallback_applied": not pair_matches,
                    }
                )
            ignored = len(set(proposed) - set(candidate_contracts)) + duplicates
            return {"items": output}, _diagnostics(accepted, rejected, ignored_count=ignored)

        contribution, audit = self._run_agent(
            state,
            agent_id="evidence_checklist",
            schema=evidence_wire_schema,
            system_prompt=(
                "Fill every predeclared property in the fixed items object. Each item slot returns only selection_id "
                "and confidence. Choose selection_id only from that exact slot's enum. Each selection_id is a complete "
                "status::artifact selection: its status is coherent with whether artifacts are selected, and every "
                "artifact is capability-compatible with that item. Use the verified process overlay, applicability "
                "metadata, accepted canonical facts, and fact-to-artifact bindings. Never omit an item, repeat an "
                "item ID, copy a selection from another slot unless that slot permits it, or return a partial items "
                "object. The application decodes selections, binds canonical source references, and rebuilds checklist "
                "aggregates. Return no item_id fields, source-reference IDs, raw excerpts, deterministic why, requests, "
                "legal conclusions, or prose."
            ),
            provider_payload=_evidence_provider_payload(
                state, template=self.playbook_template
            ),
            validator=validate,
            private_contract={
                "item_catalog": [
                    {
                        "item_id": value["item_id"],
                        "fact_id": value["fact_id"],
                        "required_level": value["required_level"],
                        "current_path": value["current_path"],
                        "candidate_artifact_ids": value[
                            "candidate_artifact_ids"
                        ],
                        "status": source_items[item_id]["status"],
                        "artifact_ids": sorted(
                            source_items[item_id].get("artifact_ids", [])
                        ),
                    }
                    for item_id, value in sorted(candidate_contracts.items())
                ],
                "allowed_statuses": EVIDENCE_STATUS_CANDIDATES,
                "allowed_artifact_ids": sorted(allowed_artifact_ids),
                "wire_contract": "fixed_item_coherent_selection/1.0.0",
            },
        )
        return {"evidence_checklist": contribution, "audit_entries": [audit]}

    def _evidence_gate_node(self, state: AgentGraphState) -> dict[str, Any]:
        writer = get_stream_writer()
        if not state.get("evidence_checklist", {}).get("items"):
            raise AgentBoundaryError("deterministic_evidence_gate", "evidence_contribution")
        if state["verification"].get("valid") is not True:
            raise AgentBoundaryError("deterministic_evidence_gate", "playbook_verification")
        accepted_checklist = apply_evidence_contribution(
            state["checklist"],
            state["evidence_checklist"],
            candidate_artifact_ids_by_item=_evidence_candidate_artifact_ids(
                state, template=self.playbook_template
            ),
        )
        verification_builder = state.get("verification_builder")
        changed = (
            accepted_artifact_hash(state["process"])
            != state.get("seed_process_hash")
            or accepted_artifact_hash(accepted_checklist)
            != state.get("seed_checklist_hash")
        )
        if callable(verification_builder):
            fresh_verification = verification_builder(
                state["process"], accepted_checklist
            )
        elif changed:
            raise AgentBoundaryError(
                "deterministic_evidence_gate", "verification_recompute_required"
            )
        else:
            fresh_verification = deepcopy(state["verification"])
        if (
            not isinstance(fresh_verification, dict)
            or fresh_verification.get("valid") is not True
            or fresh_verification.get("computed") is not True
        ):
            raise AgentBoundaryError(
                "deterministic_evidence_gate", "fresh_playbook_verification"
            )
        input_hash = _safe_hash(state["evidence_checklist"])
        output_hash = accepted_artifact_hash(accepted_checklist)
        writer(
            {
                "receipt_type": "gate_passed",
                "agent_id": "deterministic_evidence_gate",
                "role": "Deterministic Evidence Contract Gate",
                "actor_type": "deterministic_gate",
                "status": "completed",
                "handoff_from": "evidence_checklist",
                "handoff_to": "final_claim_brief_audit",
                "input_artifact": "evidence_checklist_contribution",
                "output_artifact": "verified_evidence_model",
                "input_artifact_hash": input_hash,
                "output_artifact_hash": output_hash,
                "playbook_template_sha256": state[
                    "playbook_template_sha256"
                ],
            }
        )
        return {
            "checklist": accepted_checklist,
            "verification": fresh_verification,
            "audit_entries": [
                {
                    "agent_id": "deterministic_evidence_gate",
                    "role": "Deterministic Evidence Contract Gate",
                    "actor_type": "deterministic_gate",
                    "model": None,
                    "outcome": "passed",
                    "input_artifact_hash": input_hash,
                    "output_artifact_hash": output_hash,
                    "playbook_template_sha256": state[
                        "playbook_template_sha256"
                    ],
                }
            ]
        }

    def _final_brief_node(self, state: AgentGraphState) -> dict[str, Any]:
        current = state["process"]["current_overlay"]
        current_node = next(
            node for node in state["process"]["nodes"] if node["node_id"] == current["current_node_id"]
        )
        expected = {
            "current_node_id": current["current_node_id"],
            "next_action_node_id": current["next_action_node_id"],
            "supporting_fact_ids": sorted(current_node.get("fact_ids", [])),
            "upstream_contribution_ids": [
                "document_source_integrity",
                "process_decision_mapping",
                "evidence_checklist",
            ],
            "audit_check_ids": list(FINAL_AUDIT_CHECK_IDS),
        }

        def validate(value: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
            proposal = value.get("proposal")
            proposal = proposal if isinstance(proposal, dict) else {}
            accepted: list[str] = []
            rejected: list[dict[str, str]] = []
            effective: dict[str, Any] = {}
            field_contributions: list[dict[str, Any]] = []
            units = (
                ("current_node_id", "final:current_node"),
                ("next_action_node_id", "final:next_action"),
                ("supporting_fact_ids", "final:supporting_facts"),
                (
                    "upstream_contribution_ids",
                    "final:upstream_contributions",
                ),
                ("audit_check_ids", "final:audit_checks"),
            )
            for field, contribution_id in units:
                proposed_value = proposal.get(field)
                expected_value = expected[field]
                if isinstance(expected_value, list):
                    well_formed = (
                        isinstance(proposed_value, list)
                        and all(isinstance(item, str) for item in proposed_value)
                        and len(set(proposed_value)) == len(proposed_value)
                    )
                    canonical_value = sorted(proposed_value) if well_formed else []
                    canonical_expected = sorted(expected_value)
                    matches = well_formed and canonical_value == canonical_expected
                    effective[field] = (
                        canonical_value if matches else canonical_expected
                    )
                else:
                    matches = proposed_value == expected_value
                    effective[field] = (
                        proposed_value if matches else expected_value
                    )
                if matches:
                    accepted.append(contribution_id)
                else:
                    rejected.append(
                        {
                            "item_id": contribution_id,
                            "invariant": "final_brief_contract",
                        }
                    )
                field_contributions.append(
                    {
                        "contribution_id": contribution_id,
                        "field": field,
                        "attribution": (
                            ROLE_LABELS["final_claim_brief_audit"]
                            if matches
                            else "deterministic_application"
                        ),
                        "confidence_basis_points": _confidence_basis_points(
                            proposal["confidence"] if matches else 1
                        ),
                        "deterministic_fallback_applied": not matches,
                    }
                )
            accepted_supporting = set(effective["supporting_fact_ids"])
            bound_source_ids = sorted(
                {
                    resolve_observable_source_reference_id(
                        ref, state["source_registry"]
                    )
                    for fact in state["facts"]
                    if fact["fact_id"] in accepted_supporting
                    for ref in fact.get("source_refs", [])
                    if ref.get("locator_kind") == "text_quote"
                }
            )
            fallback_applied = bool(rejected)
            return {
                **effective,
                "source_ref_ids": bound_source_ids,
                "input_contribution_ids": effective[
                    "upstream_contribution_ids"
                ],
                "lineage_authority": (
                    "hybrid_guarded_model_audit"
                    if "final:upstream_contributions" in accepted
                    else "deterministic_application"
                ),
                "contribution_scope": "independent_final_claim_brief_audit",
                "field_contributions": field_contributions,
                "confidence_basis_points": _confidence_basis_points(
                    proposal["confidence"]
                ),
                "attribution": (
                    ROLE_LABELS["final_claim_brief_audit"]
                    if not fallback_applied
                    else "mixed_model_and_deterministic"
                    if accepted
                    else "deterministic_application"
                ),
                "deterministic_fallback_applied": fallback_applied,
            }, _diagnostics(accepted, rejected)

        contribution, audit = self._run_agent(
            state,
            agent_id="final_claim_brief_audit",
            schema=FinalClaimBriefResponse,
            system_prompt=(
                "Independently audit the accepted process and evidence gate handoffs against the static topology, "
                "canonical facts, and prior accepted specialist contributions. Return only current_node_id, "
                "next_action_node_id, supporting_fact_ids, upstream_contribution_ids, audit_check_ids, and confidence. "
                "The application scores each field independently and binds source references from accepted canonical "
                "supporting facts. Return no source-reference IDs, prose, legal conclusion, remedy, or new action."
            ),
            provider_payload=_final_brief_provider_payload(state),
            validator=validate,
            private_contract=expected,
        )
        return {"final_brief": contribution, "audit_entries": [audit]}

    def _whole_playbook_gate_node(self, state: AgentGraphState) -> dict[str, Any]:
        writer = get_stream_writer()
        if (
            state.get("playbook_template_sha256")
            != self.playbook_template.template_sha256
            or state["verification"].get("valid") is not True
            or not state.get("final_brief")
        ):
            raise AgentBoundaryError("whole_playbook_gate", "whole_playbook")
        current = state["process"]["current_overlay"]
        if (
            state["final_brief"].get("current_node_id")
            != current["current_node_id"]
            or state["final_brief"].get("next_action_node_id")
            != current["next_action_node_id"]
        ):
            raise AgentBoundaryError("whole_playbook_gate", "final_route_binding")
        current_node = next(
            node
            for node in state["process"]["nodes"]
            if node["node_id"] == current["current_node_id"]
        )
        if state["final_brief"].get("supporting_fact_ids") != sorted(
            current_node.get("fact_ids", [])
        ):
            raise AgentBoundaryError(
                "whole_playbook_gate", "final_supporting_fact_binding"
            )
        if state["final_brief"].get("input_contribution_ids") != [
            "document_source_integrity",
            "evidence_checklist",
            "process_decision_mapping",
        ]:
            raise AgentBoundaryError("whole_playbook_gate", "final_lineage_binding")
        input_hash = _safe_hash(
            {"final_brief": state["final_brief"], "verification": state["verification"]}
        )
        output_hash = accepted_artifact_hash(
            {"process": state["process"], "checklist": state["checklist"], "final_brief": state["final_brief"]}
        )
        gate = {
            "agent_id": "whole_playbook_gate",
            "role": "Deterministic Whole-Playbook Gate",
            "actor_type": "deterministic_gate",
            "model": None,
            "outcome": "passed",
            "input_artifact_hash": input_hash,
            "output_artifact_hash": output_hash,
            "output_projection_contract": "casepath.accepted-playbook-projection/1.0.0",
            "final_brief_artifact_hash": accepted_artifact_hash(
                state["final_brief"]
            ),
            "verification_report_hash": accepted_artifact_hash(
                state["verification"]
            ),
            "verification_whole_playbook_hash": state["verification"].get(
                "whole_playbook_hash"
            ),
            "playbook_template_sha256": self.playbook_template.template_sha256,
        }
        writer(
            {
                "receipt_type": "gate_passed",
                "agent_id": "whole_playbook_gate",
                "role": "Deterministic Whole-Playbook Gate",
                "actor_type": "deterministic_gate",
                "status": "completed",
                "handoff_from": "final_claim_brief_audit",
                "handoff_to": "complete",
                "input_artifact": "final_claim_brief_contribution",
                "output_artifact": "verified_claim_playbook",
                "input_artifact_hash": input_hash,
                "output_artifact_hash": output_hash,
                "output_projection_contract": gate[
                    "output_projection_contract"
                ],
                "final_brief_artifact_hash": gate[
                    "final_brief_artifact_hash"
                ],
                "verification_report_hash": gate[
                    "verification_report_hash"
                ],
                "verification_whole_playbook_hash": gate[
                    "verification_whole_playbook_hash"
                ],
                "playbook_template_sha256": self.playbook_template.template_sha256,
            }
        )
        entries = [*state["audit_entries"], gate]
        agent_entries = [
            item
            for item in entries
            if item["actor_type"]
            in {"nemotron_agent", "deterministic_structured_agent"}
        ]
        accepted_cycle_payload = {
            "contract": "casepath.accepted-cycle-artifacts/1.0.0",
            "facts": deepcopy(state["facts"]),
            "process": deepcopy(state["process"]),
            "checklist": deepcopy(state["checklist"]),
            "final_claim_brief": deepcopy(state["final_brief"]),
            "verification": deepcopy(state["verification"]),
            "role_artifacts": {
                "contract": "casepath.accepted-role-artifacts/1.0.0",
                "canonical_facts": deepcopy(state["facts"]),
                "orchestrator_plan": deepcopy(state["orchestrator_plan"]),
                "document_source_integrity": deepcopy(state["source_integrity"]),
                "process_decision_mapping": deepcopy(state["process_mapping"]),
                "evidence_checklist": deepcopy(state["evidence_checklist"]),
                "final_claim_brief_audit": deepcopy(state["final_brief"]),
            },
        }
        accepted_cycle_payload["role_artifacts"] = {
            **accepted_cycle_payload["role_artifacts"],
            "receipt_sha256": _safe_hash(accepted_cycle_payload["role_artifacts"]),
        }
        accepted_cycle_artifacts = {
            **accepted_cycle_payload,
            "receipt_sha256": _safe_hash(accepted_cycle_payload),
        }
        return {
            "audit_entries": [gate],
            "accepted_cycle_artifacts": accepted_cycle_artifacts,
            "orchestration_audit": {
                "schema_version": MULTI_AGENT_SCHEMA_VERSION,
                "implementation": MULTI_AGENT_IMPLEMENTATION,
                "framework": {
                    "langchain": LANGCHAIN_VERSION,
                    "langgraph": LANGGRAPH_VERSION,
                    "langchain_openrouter": LANGCHAIN_OPENROUTER_VERSION,
                },
                "orchestration_id": state["orchestration_id"],
                "playbook_template_sha256": self.playbook_template.template_sha256,
                "model": (
                    None
                    if state["canonicalization"].get("transport_mode")
                    == "deterministic_test_double"
                    else OPENROUTER_MODEL
                ),
                "authority_mode": MULTI_AGENT_AUTHORITY_MODE,
                "model_assisted": (
                    state["canonicalization"].get("transport_mode")
                    != "deterministic_test_double"
                ),
                "transport_mode": state["canonicalization"].get(
                    "transport_mode", "openrouter"
                ),
                "deterministic_safety_authority": True,
                "external_tracing": False,
                "prompt_storage": False,
                "raw_output_storage": False,
                "execution_topology": {
                    "authority": "deterministic_application",
                    "implementation": "compiled_langgraph_stategraph",
                    "delegations": [dict(value) for value in EXECUTION_DELEGATIONS],
                    "parallel_groups": [list(PARALLEL_GROUP)],
                },
                "agents": agent_entries,
                "deterministic_gates": [
                    item for item in entries if item["actor_type"] == "deterministic_gate"
                ],
                "all_required_agents_contributed": {
                    item["agent_id"] for item in agent_entries
                }
                == set(AI_AGENT_IDS)
                and all(
                    (
                        item.get("accepted_count", 0)
                        + item.get("rejected_count", 0)
                        > 0
                        if item.get("agent_id") == "canonical_facts"
                        else item.get("accepted_count", 0)
                        > item.get("rejected_count", 0)
                    )
                    for item in agent_entries
                ),
                "guarded_fallback_count": sum(
                    int(item.get("deterministic_fallback_applied", False)) for item in agent_entries
                ),
                "specialist_artifacts": {
                    "orchestrator_plan": state["orchestrator_plan"],
                    "document_source_integrity": state["source_integrity"],
                    "process_decision_mapping": state["process_mapping"],
                    "evidence_checklist": state["evidence_checklist"],
                    "final_claim_brief_audit": state["final_brief"],
                },
                "final_claim_brief": state["final_brief"],
            },
        }


__all__ = [
    "AI_AGENT_IDS",
    "AGENT_RUNTIME_PROFILE",
    "AgentBoundaryError",
    "accepted_artifact_hash",
    "AgentGraphState",
    "DETERMINISTIC_GATE_IDS",
    "DeterministicStructuredAgent",
    "EvidenceChecklistResponse",
    "FinalClaimBriefResponse",
    "InstrumentedStructuredAgent",
    "MULTI_AGENT_AUTHORITY_MODE",
    "MULTI_AGENT_IMPLEMENTATION",
    "MULTI_AGENT_SCHEMA_VERSION",
    "MULTI_AGENT_VERSION",
    "NemotronMultiAgentOrchestrator",
    "OrchestratorPlan",
    "ProcessDecisionResponse",
    "SourceIntegrityResponse",
]
