"""Acceptance Contract v0.1 and experiment receipt schemas."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from enum import Enum
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

from .expressions import ExpressionError, parse_expression, referenced_names

Identifier = str
Primitive = bool | int | float | str | None
Assignment = dict[str, Primitive]
PublicScenarioVariable = Literal[
    "visible_condition",
    "technical_cause_established",
    "manager_notification_established",
]
PublicScenarioAssignment = dict[PublicScenarioVariable, StrictBool]
FailureCode = Literal[
    "budget_exceeded",
    "provider_response_error",
    "schema_validation_error",
    "invalid_output",
    "execution_error",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class ConceptKind(str, Enum):
    PROCESS_STEP = "process_step"
    DECISION = "decision"
    OUTCOME = "outcome"
    FACT = "fact"
    EVIDENCE_CAPABILITY = "evidence_capability"
    DOCUMENT = "document"


class Requirement(str, Enum):
    MANDATORY = "mandatory"
    OPTIONAL = "optional"
    FORBIDDEN = "forbidden"


class RelationType(str, Enum):
    PRECEDES = "precedes"
    BRANCHES_TO = "branches_to"
    REQUIRES_FACT = "requires_fact"
    SUPPORTED_BY = "supported_by"
    SATISFIED_BY = "satisfied_by"
    CONTRADICTS = "contradicts"


class DocumentState(str, Enum):
    PROVIDED_SUFFICIENT = "provided_sufficient"
    PROVIDED_INSUFFICIENT = "provided_insufficient"
    MISSING = "missing"
    CONDITIONAL = "conditional"
    IRRELEVANT = "irrelevant"
    UNKNOWN = "unknown"


class RequestMode(str, Enum):
    NOW = "now"
    CONDITIONAL = "conditional"
    NONE = "none"


class LocatorKind(str, Enum):
    TEXT_SPAN = "text_span"
    IMAGE_REGION = "image_region"
    WHOLE_ARTIFACT = "whole_artifact"
    AUTHORITY_PASSAGE = "authority_passage"
    JSON_POINTER = "json_pointer"


class PacketArtifact(StrictModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=False)

    artifact_id: Identifier
    path: str
    media_type: str
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    inline_text: str = Field(min_length=1, max_length=100_000)

    @field_validator("path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        value = value.strip()
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or value in {"", "."}:
            raise ValueError("artifact path must be a non-empty relative path without '..'")
        return value

    @field_validator("artifact_id", "media_type")
    @classmethod
    def validate_metadata_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("artifact metadata must not be empty")
        return value

    @model_validator(mode="after")
    def validate_observable_content(self) -> PacketArtifact:
        if not (self.media_type.startswith("text/") or self.media_type == "application/json"):
            raise ValueError("the current experiment admits only inline textual artifacts")
        observed = hashlib.sha256(self.inline_text.encode("utf-8")).hexdigest()
        if observed != self.artifact_sha256:
            raise ValueError("inline_text does not match artifact_sha256")
        return self


class ObservableClaimPacket(StrictModel):
    """Only fields that a prediction condition is allowed to observe."""

    packet_version: Literal["casepath.claim-packet/0.2.0"]
    case_id: Identifier
    received_at: datetime
    language: str
    scenario: PublicScenarioAssignment
    artifacts: tuple[PacketArtifact, ...] = Field(min_length=1)
    source_artifacts: tuple[PacketArtifact, ...] = Field(min_length=1)
    source_snapshot_id: str
    source_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_artifacts(self) -> ObservableClaimPacket:
        artifact_ids = [
            artifact.artifact_id for artifact in (*self.artifacts, *self.source_artifacts)
        ]
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("claim and source artifact IDs must be unique")
        source_payload = [artifact.model_dump(mode="json") for artifact in self.source_artifacts]
        source_bytes = json.dumps(
            source_payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if hashlib.sha256(source_bytes).hexdigest() != self.source_snapshot_sha256:
            raise ValueError("source_snapshot_sha256 does not match source artifact bytes")
        return self


class SourceLocator(StrictModel):
    artifact_id: Identifier
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    locator_kind: LocatorKind
    page: int | None = Field(default=None, ge=1)
    exact_text: str | None = None
    text_start: int | None = Field(default=None, ge=0)
    text_end: int | None = Field(default=None, ge=1)
    image_region: tuple[float, float, float, float] | None = None
    source_version: str | None = None
    effective_date: date | None = None
    json_pointer: str | None = None
    canonical_value_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_locator(self) -> SourceLocator:
        if self.locator_kind in {LocatorKind.TEXT_SPAN, LocatorKind.AUTHORITY_PASSAGE}:
            if self.page is None or not self.exact_text:
                raise ValueError("text and authority locators require page and exact_text")
            if (self.text_start is None) != (self.text_end is None):
                raise ValueError("text_start and text_end must be provided together")
            if (
                self.text_start is not None
                and self.text_end is not None
                and self.text_end <= self.text_start
            ):
                raise ValueError("text_end must be greater than text_start")
        if self.locator_kind is LocatorKind.IMAGE_REGION:
            if self.page is None or self.image_region is None:
                raise ValueError("image-region locators require page and image_region")
            x0, y0, x1, y1 = self.image_region
            if not all(0.0 <= value <= 1.0 for value in self.image_region):
                raise ValueError("image_region coordinates must be normalized to [0, 1]")
            if x1 <= x0 or y1 <= y0:
                raise ValueError("image_region must have positive area")
        if self.locator_kind is LocatorKind.JSON_POINTER and (
            self.json_pointer is None
            or not self.json_pointer.startswith("/")
            or self.canonical_value_sha256 is None
        ):
            raise ValueError("JSON-pointer locators require a pointer and value hash")
        return self


def _validate_predicate(expression: str) -> str:
    try:
        parse_expression(expression)
    except ExpressionError as exc:
        raise ValueError(str(exc)) from exc
    return expression


class ConceptSpec(StrictModel):
    concept_id: Identifier
    kind: ConceptKind
    label: str
    requirement: Requirement
    aliases: tuple[str, ...] = ()
    criticality: int = Field(default=1, ge=1, le=5)
    active_when: str = "true"
    source_requirements: tuple[SourceLocator, ...] = ()

    _predicate = field_validator("active_when")(_validate_predicate)


class RelationSpec(StrictModel):
    relation_id: Identifier
    relation_type: RelationType
    source_id: Identifier
    target_id: Identifier
    requirement: Requirement
    active_when: str = "true"

    _predicate = field_validator("active_when")(_validate_predicate)


class VariantMapping(StrictModel):
    mapping_id: Identifier
    mode: Literal["split", "merge", "alias"]
    candidate_concept_ids: tuple[Identifier, ...] = Field(min_length=1)
    contract_concept_ids: tuple[Identifier, ...] = Field(min_length=1)
    represented_kinds: tuple[ConceptKind, ...] = Field(min_length=1)
    rationale: str


class PartialOrderConstraint(StrictModel):
    before_id: Identifier
    after_id: Identifier
    active_when: str = "true"

    _predicate = field_validator("active_when")(_validate_predicate)


class PredicateProbe(StrictModel):
    assignment: Assignment
    expected: bool


class BranchPredicateSpec(StrictModel):
    predicate_id: Identifier
    expression: str
    probes: tuple[PredicateProbe, ...] = Field(min_length=2)
    source_requirements: tuple[SourceLocator, ...] = ()

    _predicate = field_validator("expression")(_validate_predicate)

    @model_validator(mode="after")
    def validate_probe_coverage(self) -> BranchPredicateSpec:
        variables = referenced_names(self.expression)
        for probe in self.probes:
            missing = variables.difference(probe.assignment)
            if missing:
                raise ValueError(f"probe is missing variables: {sorted(missing)}")
        if {probe.expected for probe in self.probes} != {False, True}:
            raise ValueError("branch probes must include both true and false outcomes")
        return self


class PathProbe(StrictModel):
    probe_id: Identifier
    assignment: Assignment
    required_concept_ids: tuple[Identifier, ...] = ()
    inactive_concept_ids: tuple[Identifier, ...] = ()
    accepted_terminal_outcomes: tuple[Identifier, ...] = Field(min_length=1)


class EvidenceContract(StrictModel):
    evidence_contract_id: Identifier
    fact_id: Identifier
    decision_ids: tuple[Identifier, ...] = Field(min_length=1)
    required_capability_ids: tuple[Identifier, ...] = Field(min_length=1)
    acceptable_document_sets: tuple[tuple[Identifier, ...], ...] = Field(min_length=1)
    active_when: str = "true"
    criticality: int = Field(default=1, ge=1, le=5)
    expected_document_states: dict[Identifier, DocumentState]
    incompatible_with: tuple[Identifier, ...] = ()
    abstention_allowed: bool = False

    _predicate = field_validator("active_when")(_validate_predicate)

    @field_validator("acceptable_document_sets")
    @classmethod
    def validate_document_sets(
        cls, value: tuple[tuple[Identifier, ...], ...]
    ) -> tuple[tuple[Identifier, ...], ...]:
        if any(not option for option in value):
            raise ValueError("acceptable document sets must not be empty")
        return value


class AcceptanceGate(StrictModel):
    gate_id: Identifier
    metric: str
    comparator: Literal[">=", "<=", ">", "<", "=="]
    threshold: float
    fatal: bool = True
    rationale: str


class BenchmarkMetadata(StrictModel):
    family: str
    split: Literal["pilot", "dev", "validation", "hidden"]
    packet_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_snapshot_id: str
    source_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authored_without_system_output: bool
    annotator_ids: tuple[str, ...] = ()
    adjudicator_id: str | None = None
    locked_at: datetime | None = None


class AcceptanceContract(StrictModel):
    contract_version: Literal["casepath.acceptance-contract/0.1.0"]
    case_id: Identifier
    metadata: BenchmarkMetadata
    scenario: Assignment
    concepts: tuple[ConceptSpec, ...]
    relations: tuple[RelationSpec, ...]
    variants: tuple[VariantMapping, ...] = ()
    partial_order: tuple[PartialOrderConstraint, ...] = ()
    branch_predicates: tuple[BranchPredicateSpec, ...] = ()
    path_probes: tuple[PathProbe, ...] = ()
    evidence_contracts: tuple[EvidenceContract, ...]
    acceptance_gates: tuple[AcceptanceGate, ...]

    @model_validator(mode="after")
    def validate_references(self) -> AcceptanceContract:
        concept_ids = [concept.concept_id for concept in self.concepts]
        if len(concept_ids) != len(set(concept_ids)):
            raise ValueError("concept IDs must be unique")
        relation_ids = [relation.relation_id for relation in self.relations]
        if len(relation_ids) != len(set(relation_ids)):
            raise ValueError("relation IDs must be unique")
        known = set(concept_ids)
        kinds = {concept.concept_id: concept.kind for concept in self.concepts}
        control_kinds = {ConceptKind.PROCESS_STEP, ConceptKind.DECISION, ConceptKind.OUTCOME}
        relation_kinds = {
            RelationType.PRECEDES: (control_kinds, control_kinds),
            RelationType.BRANCHES_TO: ({ConceptKind.DECISION}, control_kinds),
            RelationType.REQUIRES_FACT: ({ConceptKind.DECISION}, {ConceptKind.FACT}),
            RelationType.SUPPORTED_BY: (
                {ConceptKind.FACT},
                {ConceptKind.EVIDENCE_CAPABILITY},
            ),
            RelationType.SATISFIED_BY: (
                {ConceptKind.EVIDENCE_CAPABILITY},
                {ConceptKind.DOCUMENT},
            ),
        }
        for relation in self.relations:
            if relation.source_id not in known or relation.target_id not in known:
                raise ValueError(f"relation {relation.relation_id} references an unknown concept")
            expected = relation_kinds.get(relation.relation_type)
            if expected is not None and (
                kinds[relation.source_id] not in expected[0]
                or kinds[relation.target_id] not in expected[1]
            ):
                raise ValueError(f"relation {relation.relation_id} has invalid endpoint kinds")
        for constraint in self.partial_order:
            if constraint.before_id not in known or constraint.after_id not in known:
                raise ValueError("partial-order constraint references an unknown concept")
        for mapping in self.variants:
            unknown = set(mapping.contract_concept_ids).difference(known)
            if unknown:
                raise ValueError(f"variant references unknown contract concepts: {sorted(unknown)}")
            mapped_kinds = {kinds[concept_id] for concept_id in mapping.contract_concept_ids}
            if not mapped_kinds.issubset(set(mapping.represented_kinds)):
                raise ValueError(f"variant {mapping.mapping_id} omits a represented concept kind")
        for evidence in self.evidence_contracts:
            references = {
                evidence.fact_id,
                *evidence.decision_ids,
                *evidence.required_capability_ids,
                *(doc for option in evidence.acceptable_document_sets for doc in option),
                *evidence.expected_document_states,
            }
            unknown = references.difference(known)
            if unknown:
                raise ValueError(
                    f"evidence contract references unknown concepts: {sorted(unknown)}"
                )
            if kinds[evidence.fact_id] is not ConceptKind.FACT:
                raise ValueError(f"{evidence.evidence_contract_id} fact_id is not a fact")
            if any(kinds[item] is not ConceptKind.DECISION for item in evidence.decision_ids):
                raise ValueError(f"{evidence.evidence_contract_id} has a non-decision decision_id")
            if any(
                kinds[item] is not ConceptKind.EVIDENCE_CAPABILITY
                for item in evidence.required_capability_ids
            ):
                raise ValueError(f"{evidence.evidence_contract_id} has a non-capability ID")
            document_ids = {
                item for option in evidence.acceptable_document_sets for item in option
            } | set(evidence.expected_document_states)
            if any(kinds[item] is not ConceptKind.DOCUMENT for item in document_ids):
                raise ValueError(f"{evidence.evidence_contract_id} has a non-document ID")
        for probe in self.path_probes:
            referenced = (
                set(probe.required_concept_ids)
                | set(probe.inactive_concept_ids)
                | set(probe.accepted_terminal_outcomes)
            )
            unknown = referenced.difference(known)
            if unknown:
                raise ValueError(f"path probe references unknown concepts: {sorted(unknown)}")
            if any(
                kinds[item] is not ConceptKind.OUTCOME for item in probe.accepted_terminal_outcomes
            ):
                raise ValueError(f"path probe {probe.probe_id} has a non-outcome terminal")
        predicate_ids = [predicate.predicate_id for predicate in self.branch_predicates]
        probe_ids = [probe.probe_id for probe in self.path_probes]
        gate_ids = [gate.gate_id for gate in self.acceptance_gates]
        if len(predicate_ids) != len(set(predicate_ids)):
            raise ValueError("branch predicate IDs must be unique")
        if len(probe_ids) != len(set(probe_ids)):
            raise ValueError("path probe IDs must be unique")
        if len(gate_ids) != len(set(gate_ids)):
            raise ValueError("acceptance gate IDs must be unique")
        scenario_names = set(self.scenario)
        guarded_expressions = [
            *(concept.active_when for concept in self.concepts),
            *(relation.active_when for relation in self.relations),
            *(constraint.active_when for constraint in self.partial_order),
            *(evidence.active_when for evidence in self.evidence_contracts),
        ]
        unknown_variables = (
            set()
            .union(*(referenced_names(expression) for expression in guarded_expressions))
            .difference(scenario_names)
        )
        if unknown_variables:
            raise ValueError(
                f"contract predicates use unknown scenario variables: {sorted(unknown_variables)}"
            )
        return self


class CandidateConcept(StrictModel):
    concept_id: Identifier
    kind: ConceptKind
    label: str
    active_when: str = "true"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: tuple[SourceLocator, ...] = ()

    _predicate = field_validator("active_when")(_validate_predicate)


class CandidateRelation(StrictModel):
    relation_id: Identifier
    relation_type: RelationType
    source_id: Identifier
    target_id: Identifier
    active_when: str = "true"

    _predicate = field_validator("active_when")(_validate_predicate)


class CandidateBranchPredicate(StrictModel):
    predicate_id: Identifier
    expression: str
    provenance: tuple[SourceLocator, ...] = ()

    _predicate = field_validator("expression")(_validate_predicate)


class CandidateDocument(StrictModel):
    item_id: Identifier
    document_id: Identifier
    label: str
    state: DocumentState
    request_mode: RequestMode
    active_when: str = "true"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: tuple[SourceLocator, ...] = ()

    _predicate = field_validator("active_when")(_validate_predicate)


class CandidateArtifact(StrictModel):
    artifact_version: Literal["casepath.candidate-artifact/0.1.0"]
    case_id: Identifier
    concepts: tuple[CandidateConcept, ...]
    relations: tuple[CandidateRelation, ...]
    branch_predicates: tuple[CandidateBranchPredicate, ...] = ()
    documents: tuple[CandidateDocument, ...]
    terminal_outcome_ids: tuple[Identifier, ...]
    abstained_concept_ids: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def validate_candidate(self) -> CandidateArtifact:
        concept_ids = [concept.concept_id for concept in self.concepts]
        relation_ids = [relation.relation_id for relation in self.relations]
        item_ids = [document.item_id for document in self.documents]
        if len(concept_ids) != len(set(concept_ids)):
            raise ValueError("candidate concept IDs must be unique")
        if len(relation_ids) != len(set(relation_ids)):
            raise ValueError("candidate relation IDs must be unique")
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("candidate document item IDs must be unique")
        if set(concept_ids).intersection(item_ids):
            raise ValueError("candidate concept IDs and document item IDs must not overlap")
        known = set(concept_ids).union(item_ids)
        concept_kinds = {concept.concept_id: concept.kind for concept in self.concepts}
        endpoint_kinds = {
            **concept_kinds,
            **{document.item_id: ConceptKind.DOCUMENT for document in self.documents},
        }
        control_kinds = {ConceptKind.PROCESS_STEP, ConceptKind.DECISION, ConceptKind.OUTCOME}
        relation_kinds = {
            RelationType.PRECEDES: (control_kinds, control_kinds),
            RelationType.BRANCHES_TO: ({ConceptKind.DECISION}, control_kinds),
            RelationType.REQUIRES_FACT: ({ConceptKind.DECISION}, {ConceptKind.FACT}),
            RelationType.SUPPORTED_BY: (
                {ConceptKind.FACT},
                {ConceptKind.EVIDENCE_CAPABILITY},
            ),
            RelationType.SATISFIED_BY: (
                {ConceptKind.EVIDENCE_CAPABILITY},
                {ConceptKind.DOCUMENT},
            ),
        }
        for relation in self.relations:
            if relation.source_id not in known or relation.target_id not in known:
                raise ValueError(
                    f"candidate relation {relation.relation_id} has an unknown endpoint"
                )
            expected = relation_kinds.get(relation.relation_type)
            if expected is not None and (
                endpoint_kinds[relation.source_id] not in expected[0]
                or endpoint_kinds[relation.target_id] not in expected[1]
            ):
                raise ValueError(
                    f"candidate relation {relation.relation_id} has invalid endpoint kinds"
                )
        outcomes = {
            concept_id for concept_id, kind in concept_kinds.items() if kind is ConceptKind.OUTCOME
        }
        unknown_terminals = set(self.terminal_outcome_ids).difference(outcomes)
        if unknown_terminals:
            raise ValueError(
                "candidate terminal outcomes are not declared outcomes: "
                f"{sorted(unknown_terminals)}"
            )
        return self


class BudgetSpec(StrictModel):
    model: str
    model_revision: str
    source_snapshot_id: str
    source_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    max_model_calls: int = Field(ge=0)
    max_tool_calls: int = Field(ge=0)
    max_input_tokens: int = Field(ge=0)
    max_output_tokens: int = Field(ge=0)
    max_retrieved_bytes: int = Field(ge=0)
    temperature: float = Field(ge=0.0)
    samples: int = Field(default=1, ge=1)
    timeout_seconds: float = Field(default=120.0, gt=0)
    max_retries: int = Field(default=0, ge=0)


class ProviderCallReceipt(StrictModel):
    request_id: Identifier
    response_id: Identifier
    stage: str
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    requested_model: str
    response_model: str
    upstream_provider: str
    finish_reason: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost_usd: float | None = Field(default=None, ge=0.0)


class UsageReceipt(StrictModel):
    attempted_model_calls: int = Field(ge=0)
    model_calls: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    retrieved_bytes: int = Field(ge=0)
    latency_ms: int = Field(ge=0)
    cost_usd: float | None = Field(default=None, ge=0.0)
    failures: tuple[str, ...] = ()
    model_backed: bool = False
    provider_calls: tuple[ProviderCallReceipt, ...] = ()

    @model_validator(mode="after")
    def validate_model_provenance(self) -> UsageReceipt:
        if self.model_calls > self.attempted_model_calls:
            raise ValueError("admitted model calls cannot exceed attempted model calls")
        if self.provider_calls and len(self.provider_calls) != self.model_calls:
            raise ValueError("partial provider provenance is not an admissible usage receipt")
        complete_provenance = (
            self.model_calls > 0
            and self.attempted_model_calls == self.model_calls
            and len(self.provider_calls) == self.model_calls
        )
        if self.model_backed != complete_provenance:
            raise ValueError(
                "model_backed must be true exactly when every model call has provider provenance"
            )
        return self


class RunManifest(StrictModel):
    manifest_version: Literal["casepath.run-manifest/0.2.0"]
    run_id: Identifier
    case_id: Identifier
    condition_id: Literal["B3", "B6", "B7", "B8", "B9"]
    started_at: datetime
    finished_at: datetime
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    runtime_image_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    prompt_bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluator_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    benchmark_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schedule_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    analysis_plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    study_lock_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    budget: BudgetSpec
    usage: UsageReceipt
    candidate_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_class: Literal["fixture_only", "model_backed"]
    status: Literal["completed", "failed", "budget_rejected"]

    @model_validator(mode="after")
    def validate_time(self) -> RunManifest:
        if self.finished_at < self.started_at:
            raise ValueError("finished_at must not precede started_at")
        return self


class FailedRunManifest(StrictModel):
    manifest_version: Literal["casepath.failed-run-manifest/0.2.0"]
    run_id: Identifier
    case_id: Identifier
    condition_id: Literal["B3", "B6", "B7", "B8", "B9"]
    started_at: datetime
    finished_at: datetime
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    runtime_image_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    prompt_bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluator_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    benchmark_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schedule_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    analysis_plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    study_lock_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    budget: BudgetSpec
    usage: UsageReceipt
    failure_stage: str
    failure_code: FailureCode
    execution_class: Literal["model_backed", "unverified"]
    status: Literal["failed", "budget_rejected"]

    @model_validator(mode="after")
    def validate_failure(self) -> FailedRunManifest:
        if self.finished_at < self.started_at:
            raise ValueError("finished_at must not precede started_at")
        if self.status == "budget_rejected" and self.failure_code != "budget_exceeded":
            raise ValueError("budget_rejected requires a budget_exceeded failure")
        return self


def utc_now() -> datetime:
    return datetime.now(UTC)
