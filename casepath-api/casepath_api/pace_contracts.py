from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from .foundation.common import is_sha256
from .foundation.contracts import FoundationModel
from .pace_canonical import pace_digest_v1, validate_pace_value_v1


PACE_METHOD_CONTRACT: Literal["casepath.pace-method/1.0.0"] = (
    "casepath.pace-method/1.0.0"
)
PACE_PROCESS_CONTRACT: Literal[
    "casepath.pace-process-evidence-graph/1.0.0"
] = "casepath.pace-process-evidence-graph/1.0.0"
PACE_STATE_CONTRACT: Literal["casepath.pace-state/1.0.0"] = (
    "casepath.pace-state/1.0.0"
)
PACE_REQUEST_CONTRACT: Literal["casepath.pace-compile-request/1.0.0"] = (
    "casepath.pace-compile-request/1.0.0"
)
PACE_CERTIFICATE_CONTRACT: Literal[
    "casepath.pace-action-certificate/1.0.0"
] = "casepath.pace-action-certificate/1.0.0"


class PACEContractError(ValueError):
    pass


class PACEModel(FoundationModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    @model_validator(mode="after")
    def validate_canonical_domain(self) -> PACEModel:
        validate_pace_value_v1(self.model_dump(mode="json"))
        return self


def _require_sorted_unique(values: tuple[str, ...], *, field: str) -> None:
    if values != tuple(sorted(set(values))):
        raise ValueError(f"{field} must be sorted and unique")


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamp must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include an offset")
    return parsed


class PACETruthPolarity(str, Enum):
    SUPPORTS = "supports"
    REFUTES = "refutes"
    CONFLICTS = "conflicts"
    LIMITS = "limits"


class PACEObligationKind(str, Enum):
    ESTABLISH = "ESTABLISH"
    REFUTE = "REFUTE"
    DISAMBIGUATE = "DISAMBIGUATE"
    RESOLVE_CONFLICT = "RESOLVE_CONFLICT"
    VERIFY_AUTHORITY = "VERIFY_AUTHORITY"
    VERIFY_TEMPORAL_VALIDITY = "VERIFY_TEMPORAL_VALIDITY"
    SATISFY_DEADLINE = "SATISFY_DEADLINE"


class PACECapabilityOperator(str, Enum):
    CAPABILITY = "CAPABILITY"
    AND = "AND"
    OR = "OR"


class PACEDocumentState(str, Enum):
    MISSING = "missing"
    REQUESTED = "requested"
    RECEIVED = "received"
    VALIDATED = "validated"
    REJECTED = "rejected"
    UNAVAILABLE = "unavailable"
    STALE = "stale"


class PACEAtom(PACEModel):
    predicate_id: str = Field(min_length=1)
    value: str = Field(min_length=1)


class PACEConjunction(PACEModel):
    atoms: tuple[PACEAtom, ...] = ()

    @model_validator(mode="after")
    def validate_atoms(self) -> PACEConjunction:
        predicate_ids = tuple(atom.predicate_id for atom in self.atoms)
        _require_sorted_unique(predicate_ids, field="conjunction predicate IDs")
        return self


class PACECondition(PACEModel):
    operator: Literal["ALWAYS", "DNF"]
    clauses: tuple[PACEConjunction, ...] = ()

    @model_validator(mode="after")
    def validate_condition(self) -> PACECondition:
        if self.operator == "ALWAYS" and self.clauses:
            raise ValueError("ALWAYS condition cannot carry clauses")
        if self.operator == "DNF" and not self.clauses:
            raise ValueError("DNF condition requires at least one clause")
        clause_keys = tuple(
            tuple((atom.predicate_id, atom.value) for atom in clause.atoms)
            for clause in self.clauses
        )
        if clause_keys != tuple(sorted(set(clause_keys))):
            raise ValueError("condition clauses must be sorted and unique")
        return self


class PACEPredicateSpec(PACEModel):
    predicate_id: str = Field(min_length=1)
    domain: tuple[str, ...] = Field(min_length=1)
    semantic_type: Literal["boolean", "categorical", "state", "temporal"]

    @model_validator(mode="after")
    def validate_domain(self) -> PACEPredicateSpec:
        _require_sorted_unique(self.domain, field="predicate domain")
        return self


class PACEConstraintSpec(PACEModel):
    constraint_id: str = Field(min_length=1)
    condition: PACECondition


class PACEProcessNodeSpec(PACEModel):
    node_id: str = Field(min_length=1)
    node_kind: Literal["entry", "decision", "evidence", "terminal"]
    topological_index: int = Field(ge=0)


class PACEProcessEdgeSpec(PACEModel):
    edge_id: str = Field(min_length=1)
    source_node_id: str = Field(min_length=1)
    target_node_id: str = Field(min_length=1)
    branch_id: str | None = Field(default=None, min_length=1)


class PACEBranchSpec(PACEModel):
    branch_id: str = Field(min_length=1)
    process_node_id: str = Field(min_length=1)
    target_node_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    condition: PACECondition
    material: bool = True


class PACECapabilityLocatorBinding(PACEModel):
    source_id: str = Field(min_length=1)
    locator_id: str = Field(min_length=1)


class PACEEvidenceCapabilitySpec(PACEModel):
    """A graph-owned capability; actions cannot mint capability semantics."""

    capability_id: str = Field(min_length=1)
    evidence_item_id: str = Field(min_length=1)
    action_kinds: tuple[Literal["acquire", "validate", "clarify", "replan"], ...]
    predicate_ids: tuple[str, ...] = Field(min_length=1)
    source_ids: tuple[str, ...] = Field(min_length=1)
    source_locator_bindings: tuple[PACECapabilityLocatorBinding, ...] = Field(
        min_length=1
    )
    requires_exact_locator: bool = True

    @model_validator(mode="after")
    def validate_capability(self) -> PACEEvidenceCapabilitySpec:
        if self.action_kinds != tuple(sorted(set(self.action_kinds))):
            raise ValueError("capability action kinds must be sorted and unique")
        _require_sorted_unique(self.predicate_ids, field="capability predicate IDs")
        _require_sorted_unique(self.source_ids, field="capability source IDs")
        pairs = tuple(
            (value.source_id, value.locator_id)
            for value in self.source_locator_bindings
        )
        if pairs != tuple(sorted(set(pairs))) or {
            value.source_id for value in self.source_locator_bindings
        } != set(self.source_ids):
            raise ValueError(
                "capability source-locator bindings must be exact and canonical"
            )
        return self


class PACEProcessEvidenceGraph(PACEModel):
    contract: Literal["casepath.pace-process-evidence-graph/1.0.0"] = (
        PACE_PROCESS_CONTRACT
    )
    case_id: str = Field(min_length=1)
    process_version: str = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    source_registry_version: str = Field(min_length=1)
    knowledge_version: str = Field(min_length=1)
    predicate_specs: tuple[PACEPredicateSpec, ...] = Field(min_length=1)
    constraints: tuple[PACEConstraintSpec, ...] = ()
    nodes: tuple[PACEProcessNodeSpec, ...] = Field(min_length=2)
    edges: tuple[PACEProcessEdgeSpec, ...] = Field(min_length=1)
    branches: tuple[PACEBranchSpec, ...] = Field(min_length=1)
    capability_specs: tuple[PACEEvidenceCapabilitySpec, ...] = Field(min_length=1)
    critical_decision_ids: tuple[str, ...] = Field(min_length=1)
    graph_sha256: str

    @field_validator("graph_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError("graph_sha256 must be a SHA-256 digest")
        return value

    @model_validator(mode="after")
    def validate_graph(self) -> PACEProcessEvidenceGraph:
        predicate_ids = tuple(value.predicate_id for value in self.predicate_specs)
        branch_ids = tuple(value.branch_id for value in self.branches)
        constraint_ids = tuple(value.constraint_id for value in self.constraints)
        node_ids = tuple(value.node_id for value in self.nodes)
        edge_ids = tuple(value.edge_id for value in self.edges)
        capability_ids = tuple(value.capability_id for value in self.capability_specs)
        _require_sorted_unique(predicate_ids, field="predicate IDs")
        _require_sorted_unique(branch_ids, field="branch IDs")
        _require_sorted_unique(constraint_ids, field="constraint IDs")
        _require_sorted_unique(node_ids, field="process node IDs")
        _require_sorted_unique(edge_ids, field="process edge IDs")
        _require_sorted_unique(capability_ids, field="capability IDs")
        _require_sorted_unique(
            self.critical_decision_ids, field="critical decision IDs"
        )
        domains = {
            value.predicate_id: set(value.domain) for value in self.predicate_specs
        }
        for condition in (
            *(value.condition for value in self.constraints),
            *(value.condition for value in self.branches),
        ):
            for clause in condition.clauses:
                for atom in clause.atoms:
                    if (
                        atom.predicate_id not in domains
                        or atom.value not in domains[atom.predicate_id]
                    ):
                        raise ValueError(
                            "condition atom is outside the predicate catalog"
                        )
        if not set(self.critical_decision_ids).issubset(
            {value.decision_id for value in self.branches}
        ):
            raise ValueError("critical decision is absent from the branch catalog")
        node_by_id = {value.node_id: value for value in self.nodes}
        indexes = tuple(value.topological_index for value in self.nodes)
        if len(indexes) != len(set(indexes)):
            raise ValueError("process topological indexes must be unique")
        if not any(value.node_kind == "entry" for value in self.nodes):
            raise ValueError("process graph lacks an entry node")
        edge_by_branch: dict[str, PACEProcessEdgeSpec] = {}
        incoming_count = {node_id: 0 for node_id in node_by_id}
        outgoing_count = {node_id: 0 for node_id in node_by_id}
        for edge in self.edges:
            if (
                edge.source_node_id not in node_by_id
                or edge.target_node_id not in node_by_id
            ):
                raise ValueError("process edge references an unknown node")
            if (
                node_by_id[edge.source_node_id].topological_index
                >= node_by_id[edge.target_node_id].topological_index
            ):
                raise ValueError("process edge violates topological order")
            incoming_count[edge.target_node_id] += 1
            outgoing_count[edge.source_node_id] += 1
            if edge.branch_id is not None:
                if edge.branch_id in edge_by_branch:
                    raise ValueError("a branch must map to exactly one process edge")
                edge_by_branch[edge.branch_id] = edge
        if set(edge_by_branch) != set(branch_ids):
            raise ValueError("process edges must cover the exact branch roster")
        for branch in self.branches:
            edge = edge_by_branch[branch.branch_id]
            if (
                branch.process_node_id != edge.source_node_id
                or branch.target_node_id != edge.target_node_id
            ):
                raise ValueError("branch topology disagrees with its process edge")
        entry_ids = {
            value.node_id for value in self.nodes if value.node_kind == "entry"
        }
        if any(incoming_count[value] for value in entry_ids):
            raise ValueError("entry process nodes cannot have incoming edges")
        if any(
            outgoing_count[value.node_id]
            for value in self.nodes
            if value.node_kind == "terminal"
        ):
            raise ValueError("terminal process nodes cannot have outgoing edges")
        reachable = set(entry_ids)
        for edge in sorted(
            self.edges,
            key=lambda value: node_by_id[value.target_node_id].topological_index,
        ):
            if edge.source_node_id in reachable:
                reachable.add(edge.target_node_id)
        if reachable != set(node_ids):
            raise ValueError("process graph contains a node unreachable from entry")
        for capability in self.capability_specs:
            if not set(capability.predicate_ids).issubset(domains):
                raise ValueError("capability references an unknown predicate")
        payload = self.model_dump(mode="json", exclude={"graph_sha256"})
        if pace_digest_v1(payload) != self.graph_sha256:
            raise ValueError("graph_sha256 does not match graph content")
        return self


class PACESourceRecord(PACEModel):
    source_id: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    source_sha256: str
    locator_ids: tuple[str, ...] = Field(min_length=1)
    authority_valid: bool
    valid_from: str | None = None
    valid_until: str | None = None

    @field_validator("source_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError("source_sha256 must be a SHA-256 digest")
        return value

    @model_validator(mode="after")
    def validate_source(self) -> PACESourceRecord:
        _require_sorted_unique(self.locator_ids, field="source locator IDs")
        lower = _parse_utc(self.valid_from) if self.valid_from is not None else None
        upper = _parse_utc(self.valid_until) if self.valid_until is not None else None
        if lower is not None and upper is not None and upper < lower:
            raise ValueError("source validity interval is inverted")
        return self


class PACESourceLocatorBinding(PACEModel):
    source_id: str = Field(min_length=1)
    locator_id: str = Field(min_length=1)


class PACEObservation(PACEModel):
    contract: Literal["casepath.pace-observation/1.0.0"] = (
        "casepath.pace-observation/1.0.0"
    )
    observation_id: str = Field(min_length=1)
    predicate_id: str = Field(min_length=1)
    allowed_values: tuple[str, ...] = Field(min_length=1)
    polarity: PACETruthPolarity
    source_id: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    locator_id: str = Field(min_length=1)
    observed_at: str
    reliability_milli: int = Field(ge=0, le=1000)
    observation_sha256: str

    @field_validator("observation_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError("observation_sha256 must be a SHA-256 digest")
        return value

    @model_validator(mode="after")
    def validate_observation(self) -> PACEObservation:
        _require_sorted_unique(self.allowed_values, field="observation values")
        _parse_utc(self.observed_at)
        payload = self.model_dump(mode="json", exclude={"observation_sha256"})
        if pace_digest_v1(payload) != self.observation_sha256:
            raise ValueError("observation_sha256 does not match observation")
        return self


class PACEBranchProvenanceBinding(PACEModel):
    """Exact graph/observation/source lineage for one process branch."""

    branch_id: str = Field(min_length=1)
    graph_sha256: str
    observation_ids: tuple[str, ...]
    source_locator_bindings: tuple[PACESourceLocatorBinding, ...]
    binding_sha256: str

    @model_validator(mode="after")
    def validate_binding(self) -> PACEBranchProvenanceBinding:
        if not is_sha256(self.graph_sha256) or not is_sha256(self.binding_sha256):
            raise ValueError("branch provenance contains an invalid digest")
        _require_sorted_unique(
            self.observation_ids, field="branch provenance observation IDs"
        )
        pairs = tuple(
            (value.source_id, value.locator_id)
            for value in self.source_locator_bindings
        )
        if pairs != tuple(sorted(set(pairs))):
            raise ValueError("branch provenance source-locator pairs must be sorted")
        payload = self.model_dump(mode="json", exclude={"binding_sha256"})
        if pace_digest_v1(payload) != self.binding_sha256:
            raise ValueError("branch provenance self-hash mismatch")
        return self


class PACECapabilityExpression(PACEModel):
    operator: PACECapabilityOperator
    capability_id: str | None = None
    children: tuple[PACECapabilityExpression, ...] = ()

    @model_validator(mode="after")
    def validate_expression(self) -> PACECapabilityExpression:
        if self.operator is PACECapabilityOperator.CAPABILITY:
            if not self.capability_id or self.children:
                raise ValueError("capability leaf is malformed")
        elif self.capability_id is not None or len(self.children) < 2:
            raise ValueError("capability operator requires two or more children")
        child_hashes = tuple(
            pace_digest_v1(value.model_dump(mode="json")) for value in self.children
        )
        if child_hashes != tuple(sorted(set(child_hashes))):
            raise ValueError("capability children must be sorted and unique")
        return self


def _capability_ids(expression: PACECapabilityExpression) -> tuple[str, ...]:
    if expression.operator is PACECapabilityOperator.CAPABILITY:
        assert expression.capability_id is not None
        return (expression.capability_id,)
    return tuple(
        sorted(
            value for child in expression.children for value in _capability_ids(child)
        )
    )


class PACEObligationSpec(PACEModel):
    obligation_id: str = Field(min_length=1)
    kind: PACEObligationKind
    process_node_id: str = Field(min_length=1)
    predicate_ids: tuple[str, ...] = ()
    target_atoms: tuple[PACEAtom, ...] = ()
    source_ids: tuple[str, ...] = ()
    activation: PACECondition
    evidence_capability: PACECapabilityExpression
    criticality_weight: int = Field(ge=1, le=1000)
    verification_time: str | None = None
    deadline: str | None = None
    satisfaction_event_types: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_obligation(self) -> PACEObligationSpec:
        _require_sorted_unique(self.predicate_ids, field="obligation predicate IDs")
        _require_sorted_unique(self.source_ids, field="obligation source IDs")
        _require_sorted_unique(
            self.satisfaction_event_types,
            field="deadline satisfaction event types",
        )
        atom_ids = tuple(value.predicate_id for value in self.target_atoms)
        _require_sorted_unique(atom_ids, field="obligation target predicate IDs")
        if not set(atom_ids).issubset(self.predicate_ids):
            raise ValueError("obligation target atom is outside its predicate roster")
        if (
            self.kind
            in {
                PACEObligationKind.ESTABLISH,
                PACEObligationKind.REFUTE,
            }
            and len(self.target_atoms) != 1
        ):
            raise ValueError("ESTABLISH and REFUTE require one target atom")
        if self.kind is PACEObligationKind.DISAMBIGUATE and len(self.predicate_ids) < 2:
            raise ValueError("DISAMBIGUATE requires two or more predicates")
        if (
            self.kind is PACEObligationKind.RESOLVE_CONFLICT
            and len(self.predicate_ids) != 1
        ):
            raise ValueError("RESOLVE_CONFLICT requires one predicate")
        if self.kind in {
            PACEObligationKind.VERIFY_AUTHORITY,
            PACEObligationKind.VERIFY_TEMPORAL_VALIDITY,
        } and not self.source_ids:
            raise ValueError("source verification obligation lacks a source")
        if self.kind is PACEObligationKind.VERIFY_TEMPORAL_VALIDITY:
            if self.verification_time is None:
                raise ValueError("temporal-validity obligation lacks its target time")
            _parse_utc(self.verification_time)
        elif self.verification_time is not None:
            raise ValueError("only temporal-validity obligations carry a target time")
        if self.kind is PACEObligationKind.SATISFY_DEADLINE:
            if self.deadline is None:
                raise ValueError("deadline obligation lacks a deadline")
            if not self.satisfaction_event_types:
                raise ValueError("deadline obligation lacks a completion event")
            _parse_utc(self.deadline)
        elif self.deadline is not None or self.satisfaction_event_types:
            raise ValueError("only deadline obligations may carry deadline completion")
        return self


class PACEObligationExpression(PACEModel):
    """Executable Omega, tensor, alternative, conditional and temporal algebra."""

    operator: Literal["OBLIGATION", "ALL_OF", "ANY_OF", "CONDITIONAL", "TEMPORAL"]
    obligation_id: str | None = None
    children: tuple[PACEObligationExpression, ...] = ()
    condition: PACECondition | None = None
    temporal_at: str | None = None

    @model_validator(mode="after")
    def validate_expression(self) -> PACEObligationExpression:
        if self.operator == "OBLIGATION":
            if (
                not self.obligation_id
                or self.children
                or self.condition is not None
                or self.temporal_at is not None
            ):
                raise ValueError("obligation leaf is malformed")
            return self
        if self.operator in {"ALL_OF", "ANY_OF"}:
            if (
                self.obligation_id is not None
                or len(self.children) < 2
                or self.condition is not None
                or self.temporal_at is not None
            ):
                raise ValueError("obligation composition requires two or more children")
        elif self.operator == "CONDITIONAL":
            if (
                self.obligation_id is not None
                or len(self.children) != 1
                or self.condition is None
                or self.temporal_at is not None
            ):
                raise ValueError(
                    "conditional obligation requires one child and condition"
                )
        elif (
            self.obligation_id is not None
            or len(self.children) != 1
            or self.condition is not None
            or self.temporal_at is None
        ):
            raise ValueError(
                "temporal obligation requires one child and activation time"
            )
        if self.temporal_at is not None:
            _parse_utc(self.temporal_at)
        if not self.children:
            raise ValueError("obligation composition requires two or more children")
        child_hashes = tuple(
            pace_digest_v1(value.model_dump(mode="json")) for value in self.children
        )
        if child_hashes != tuple(sorted(set(child_hashes))):
            raise ValueError("obligation children must be sorted and unique")
        return self

    def referenced_obligation_ids(self) -> tuple[str, ...]:
        if self.operator == "OBLIGATION":
            assert self.obligation_id is not None
            return (self.obligation_id,)
        return tuple(
            sorted(
                value
                for child in self.children
                for value in child.referenced_obligation_ids()
            )
        )


class PACEDocumentRecord(PACEModel):
    evidence_item_id: str = Field(min_length=1)
    state: PACEDocumentState
    source_ids: tuple[str, ...] = ()
    last_transition_at: str

    @model_validator(mode="after")
    def validate_document(self) -> PACEDocumentRecord:
        _require_sorted_unique(self.source_ids, field="document source IDs")
        _parse_utc(self.last_transition_at)
        return self


class PACEOutcomeSpec(PACEModel):
    outcome_id: str = Field(min_length=1)
    restrictions: tuple[PACEAtom, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_restrictions(self) -> PACEOutcomeSpec:
        predicate_ids = tuple(value.predicate_id for value in self.restrictions)
        _require_sorted_unique(predicate_ids, field="outcome predicate IDs")
        return self


class PACEActionSpec(PACEModel):
    action_id: str = Field(min_length=1)
    action_kind: Literal["acquire", "validate", "clarify", "replan"]
    process_node_id: str = Field(min_length=1)
    process_topological_index: int = Field(ge=0)
    evidence_item_id: str = Field(min_length=1)
    obligation_ids: tuple[str, ...] = Field(min_length=1)
    capability_ids: tuple[str, ...] = Field(min_length=1)
    outcomes: tuple[PACEOutcomeSpec, ...] = Field(min_length=2)
    source_ids: tuple[str, ...] = Field(min_length=1)
    locator_ids: tuple[str, ...] = Field(min_length=1)
    source_locator_bindings: tuple[PACESourceLocatorBinding, ...] = Field(min_length=1)
    allowed_document_states: tuple[PACEDocumentState, ...] = Field(min_length=1)
    not_before: str | None = None
    not_after: str | None = None
    burden_cost: int = Field(ge=0, le=1000)
    delay_cost: int = Field(ge=0, le=1000)
    safety_privacy_cost: int = Field(ge=0, le=1000)

    @model_validator(mode="after")
    def validate_action(self) -> PACEActionSpec:
        for values, field in (
            (self.obligation_ids, "action obligation IDs"),
            (self.capability_ids, "action capability IDs"),
            (self.source_ids, "action source IDs"),
            (self.locator_ids, "action locator IDs"),
        ):
            _require_sorted_unique(values, field=field)
        outcome_ids = tuple(value.outcome_id for value in self.outcomes)
        _require_sorted_unique(outcome_ids, field="action outcome IDs")
        pairs = tuple(
            (value.source_id, value.locator_id)
            for value in self.source_locator_bindings
        )
        if pairs != tuple(sorted(set(pairs))):
            raise ValueError("action source-locator bindings must be sorted and unique")
        if {value.source_id for value in self.source_locator_bindings} != set(
            self.source_ids
        ) or {value.locator_id for value in self.source_locator_bindings} != set(
            self.locator_ids
        ):
            raise ValueError("action source-locator bindings must cover exact rosters")
        if self.allowed_document_states != tuple(
            sorted(set(self.allowed_document_states), key=lambda value: value.value)
        ):
            raise ValueError("allowed document states must be sorted and unique")
        lower = _parse_utc(self.not_before) if self.not_before is not None else None
        upper = _parse_utc(self.not_after) if self.not_after is not None else None
        if lower is not None and upper is not None and upper < lower:
            raise ValueError("action timing interval is inverted")
        return self


class PACEHistoryEvent(PACEModel):
    event_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    recorded_at: str
    event_sha256: str

    @model_validator(mode="after")
    def validate_event(self) -> PACEHistoryEvent:
        _parse_utc(self.recorded_at)
        if not is_sha256(self.event_sha256):
            raise ValueError("event_sha256 must be a SHA-256 digest")
        payload = self.model_dump(mode="json", exclude={"event_sha256"})
        if pace_digest_v1(payload) != self.event_sha256:
            raise ValueError("event_sha256 does not match the event")
        return self


class PACECompilerConfig(PACEModel):
    contract: Literal["casepath.pace-compiler-config/1.0.0"] = (
        "casepath.pace-compiler-config/1.0.0"
    )
    selection_policy: Literal["static_non_dominated_v1"] = "static_non_dominated_v1"
    maximum_predicates: int = Field(ge=1, le=16)
    maximum_worlds: int = Field(ge=1, le=65536)
    config_sha256: str

    @model_validator(mode="after")
    def validate_config(self) -> PACECompilerConfig:
        payload = self.model_dump(mode="json", exclude={"config_sha256"})
        if pace_digest_v1(payload) != self.config_sha256:
            raise ValueError("config_sha256 does not match compiler config")
        return self


class PACEState(PACEModel):
    contract: Literal["casepath.pace-state/1.0.0"] = PACE_STATE_CONTRACT
    graph: PACEProcessEvidenceGraph
    observations: tuple[PACEObservation, ...]
    sources: tuple[PACESourceRecord, ...]
    documents: tuple[PACEDocumentRecord, ...]
    history: tuple[PACEHistoryEvent, ...] = Field(min_length=1)
    current_time: str
    kernel_snapshot_sha256: str | None = None
    predecessor_event_sha256: str
    branch_provenance: tuple[PACEBranchProvenanceBinding, ...] = Field(min_length=1)
    state_sha256: str

    @model_validator(mode="after")
    def validate_state(self) -> PACEState:
        current_time = _parse_utc(self.current_time)
        for values, field in (
            (
                tuple(value.observation_id for value in self.observations),
                "observation IDs",
            ),
            (tuple(value.source_id for value in self.sources), "source IDs"),
            (
                tuple(value.evidence_item_id for value in self.documents),
                "document IDs",
            ),
        ):
            _require_sorted_unique(values, field=field)
        if self.kernel_snapshot_sha256 is not None and not is_sha256(
            self.kernel_snapshot_sha256
        ):
            raise ValueError("kernel snapshot identity is invalid")
        if not is_sha256(self.predecessor_event_sha256):
            raise ValueError("state provenance contains an invalid SHA-256 digest")
        predicate_domains = {
            value.predicate_id: set(value.domain)
            for value in self.graph.predicate_specs
        }
        source_by_id = {value.source_id: value for value in self.sources}
        for observation in self.observations:
            source = source_by_id.get(observation.source_id)
            if (
                observation.predicate_id not in predicate_domains
                or not set(observation.allowed_values).issubset(
                    predicate_domains[observation.predicate_id]
                )
                or source is None
                or source.source_version != observation.source_version
                or observation.locator_id not in source.locator_ids
            ):
                raise ValueError(
                    "observation is not bound to graph and source registry"
                )
            if _parse_utc(observation.observed_at) > current_time:
                raise ValueError("observation time is in the future")
        observation_by_id = {value.observation_id: value for value in self.observations}
        provenance_branch_ids = tuple(
            value.branch_id for value in self.branch_provenance
        )
        if provenance_branch_ids != tuple(
            sorted(value.branch_id for value in self.branch_provenance)
        ) or set(provenance_branch_ids) != {
            value.branch_id for value in self.graph.branches
        }:
            raise ValueError(
                "branch provenance must cover the exact graph branch roster"
            )
        for binding in self.branch_provenance:
            if binding.graph_sha256 != self.graph.graph_sha256:
                raise ValueError("branch provenance graph identity mismatch")
            branch = next(
                value
                for value in self.graph.branches
                if value.branch_id == binding.branch_id
            )
            condition_predicates = {
                atom.predicate_id
                for clause in branch.condition.clauses
                for atom in clause.atoms
            }
            expected_observations = tuple(
                sorted(
                    value.observation_id
                    for value in self.observations
                    if value.predicate_id in condition_predicates
                )
            )
            if binding.observation_ids != expected_observations:
                raise ValueError(
                    "branch provenance must cite every relevant observation"
                )
            expected_pairs: set[tuple[str, str]] = set()
            for observation_id in binding.observation_ids:
                bound_observation = observation_by_id.get(observation_id)
                if (
                    bound_observation is None
                    or bound_observation.predicate_id not in condition_predicates
                ):
                    raise ValueError("branch provenance cites an unrelated observation")
                expected_pairs.add(
                    (bound_observation.source_id, bound_observation.locator_id)
                )
            actual_pairs = {
                (value.source_id, value.locator_id)
                for value in binding.source_locator_bindings
            }
            if actual_pairs != expected_pairs:
                raise ValueError("branch provenance source-locator set is not exact")
        for document in self.documents:
            if not set(document.source_ids).issubset(source_by_id):
                raise ValueError("document references an unknown source")
            if _parse_utc(document.last_transition_at) > current_time:
                raise ValueError("document transition time is in the future")
        event_ids = tuple(value.event_id for value in self.history)
        event_hashes = tuple(value.event_sha256 for value in self.history)
        if len(event_ids) != len(set(event_ids)) or len(event_hashes) != len(
            set(event_hashes)
        ):
            raise ValueError("history event IDs and hashes must be unique")
        if self.predecessor_event_sha256 != self.history[-1].event_sha256:
            raise ValueError("predecessor event must be the history tail")
        history_order = tuple(
            (_parse_utc(value.recorded_at), value.event_id) for value in self.history
        )
        if history_order != tuple(sorted(history_order)):
            raise ValueError("history must preserve canonical chronological order")
        if history_order[-1][0] > current_time:
            raise ValueError("history tail time is in the future")
        payload = self.model_dump(mode="json", exclude={"state_sha256"})
        if pace_digest_v1(payload) != self.state_sha256:
            raise ValueError("state_sha256 does not match PACE state")
        return self


class PACECompileRequest(PACEModel):
    contract: Literal["casepath.pace-compile-request/1.0.0"] = PACE_REQUEST_CONTRACT
    state: PACEState
    obligations: tuple[PACEObligationSpec, ...]
    obligation_expression: PACEObligationExpression
    actions: tuple[PACEActionSpec, ...]
    config: PACECompilerConfig
    request_sha256: str

    @model_validator(mode="after")
    def validate_request(self) -> PACECompileRequest:
        obligation_ids = tuple(value.obligation_id for value in self.obligations)
        action_ids = tuple(value.action_id for value in self.actions)
        _require_sorted_unique(obligation_ids, field="obligation IDs")
        referenced_ids = self.obligation_expression.referenced_obligation_ids()
        if referenced_ids != obligation_ids:
            raise ValueError(
                "obligation expression must reference every obligation exactly once"
            )
        _require_sorted_unique(action_ids, field="action IDs")
        predicate_domains = {
            value.predicate_id: set(value.domain)
            for value in self.state.graph.predicate_specs
        }
        predicate_ids = set(predicate_domains)
        source_by_id = {value.source_id: value for value in self.state.sources}
        source_ids = set(source_by_id)
        process_nodes = {value.node_id: value for value in self.state.graph.nodes}
        capability_ids = {
            value.capability_id for value in self.state.graph.capability_specs
        }
        for capability in self.state.graph.capability_specs:
            if not set(capability.source_ids).issubset(source_ids):
                raise ValueError("capability references an unknown source")
            if any(
                binding.locator_id
                not in source_by_id[binding.source_id].locator_ids
                for binding in capability.source_locator_bindings
            ):
                raise ValueError("capability references an unknown source locator")

        def require_catalog_atom(atom: PACEAtom, *, field: str) -> None:
            if (
                atom.predicate_id not in predicate_domains
                or atom.value not in predicate_domains[atom.predicate_id]
            ):
                raise ValueError(f"{field} atom is outside the predicate catalog")

        def require_catalog_condition(
            condition: PACECondition, *, field: str
        ) -> None:
            for clause in condition.clauses:
                for atom in clause.atoms:
                    require_catalog_atom(atom, field=field)

        def require_catalog_expression(expression: PACEObligationExpression) -> None:
            if expression.condition is not None:
                require_catalog_condition(
                    expression.condition,
                    field="obligation expression condition",
                )
            for child in expression.children:
                require_catalog_expression(child)

        require_catalog_expression(self.obligation_expression)
        for obligation in self.obligations:
            if not set(obligation.predicate_ids).issubset(predicate_ids) or not set(
                obligation.source_ids
            ).issubset(source_ids):
                raise ValueError("obligation references an unknown predicate or source")
            if obligation.process_node_id not in process_nodes:
                raise ValueError("obligation references an unknown process node")
            if not set(_capability_ids(obligation.evidence_capability)).issubset(
                capability_ids
            ):
                raise ValueError("obligation references an unknown capability")
            require_catalog_condition(
                obligation.activation,
                field="obligation activation",
            )
            for atom in obligation.target_atoms:
                require_catalog_atom(atom, field="obligation target")
        for action in self.actions:
            if not set(action.obligation_ids).issubset(set(obligation_ids)):
                raise ValueError("action references an unknown obligation")
            if action.process_node_id not in process_nodes:
                raise ValueError("action references an unknown process node")
            if not set(action.source_ids).issubset(source_ids):
                raise ValueError("action references an unknown source")
            if not set(action.capability_ids).issubset(capability_ids):
                raise ValueError("action references an unknown capability")
            for outcome in action.outcomes:
                for atom in outcome.restrictions:
                    require_catalog_atom(atom, field="action outcome")
        payload = self.model_dump(mode="json", exclude={"request_sha256"})
        if pace_digest_v1(payload) != self.request_sha256:
            raise ValueError("request_sha256 does not match compile request")
        return self


class PACEWorld(PACEModel):
    assignments: tuple[PACEAtom, ...]
    reachable_node_ids: tuple[str, ...]
    active_branch_ids: tuple[str, ...]
    material_branch_ids: tuple[str, ...]
    justified_decision_ids: tuple[str, ...]
    world_sha256: str

    @model_validator(mode="after")
    def validate_world(self) -> PACEWorld:
        predicate_ids = tuple(value.predicate_id for value in self.assignments)
        _require_sorted_unique(predicate_ids, field="world predicate IDs")
        _require_sorted_unique(self.reachable_node_ids, field="world reachable nodes")
        _require_sorted_unique(self.active_branch_ids, field="world branch IDs")
        _require_sorted_unique(
            self.material_branch_ids, field="world material branches"
        )
        if not set(self.material_branch_ids).issubset(self.active_branch_ids):
            raise ValueError("material branches must be active")
        _require_sorted_unique(self.justified_decision_ids, field="world decision IDs")
        payload = self.model_dump(mode="json", exclude={"world_sha256"})
        if pace_digest_v1(payload) != self.world_sha256:
            raise ValueError("world_sha256 does not match world")
        return self


class PACEOutcomePartition(PACEModel):
    outcome_id: str
    world_sha256s: tuple[str, ...]
    partition_sha256: str

    @model_validator(mode="after")
    def validate_partition(self) -> PACEOutcomePartition:
        _require_sorted_unique(self.world_sha256s, field="partition world hashes")
        if any(not is_sha256(value) for value in self.world_sha256s):
            raise ValueError("partition contains a non-SHA-256 world identity")
        payload = self.model_dump(mode="json", exclude={"partition_sha256"})
        if pace_digest_v1(payload) != self.partition_sha256:
            raise ValueError("partition_sha256 does not match partition")
        return self


class PACEObligationWorldScope(PACEModel):
    """The exact feasible-world subset in which an obligation is unresolved."""

    obligation_id: str = Field(min_length=1)
    world_sha256s: tuple[str, ...] = Field(min_length=1)
    scope_sha256: str

    @model_validator(mode="after")
    def validate_scope(self) -> PACEObligationWorldScope:
        _require_sorted_unique(self.world_sha256s, field="obligation-scope worlds")
        if any(not is_sha256(value) for value in self.world_sha256s):
            raise ValueError("obligation scope contains a non-SHA-256 world identity")
        payload = self.model_dump(mode="json", exclude={"scope_sha256"})
        if pace_digest_v1(payload) != self.scope_sha256:
            raise ValueError("obligation scope self-hash mismatch")
        return self


class PACEStaticPriority(PACEModel):
    process_topological_index: int = Field(ge=0)
    maximum_criticality_weight: int = Field(ge=0)
    obligation_operator_rank: int = Field(ge=0)
    action_kind_rank: int = Field(ge=0)
    burden_cost: int = Field(ge=0)
    delay_cost: int = Field(ge=0)
    safety_privacy_cost: int = Field(ge=0)
    semantic_action_key_sha256: str

    @field_validator("semantic_action_key_sha256")
    @classmethod
    def validate_key_hash(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError("semantic action key must be a SHA-256 digest")
        return value


class PACEActionCertificate(PACEModel):
    contract: Literal["casepath.pace-action-certificate/1.0.0"] = (
        PACE_CERTIFICATE_CONTRACT
    )
    case_id: str
    process_version: str
    rule_version: str
    graph_sha256: str
    source_registry_version: str
    knowledge_version: str
    state_sha256: str
    compile_request_sha256: str
    feasible_world_set_sha256: str
    feasible_world_sha256s: tuple[str, ...]
    active_branch_ids: tuple[str, ...]
    possible_branch_ids: tuple[str, ...]
    blocking_decision_ids: tuple[str, ...]
    obligation_ids: tuple[str, ...]
    obligation_world_scopes: tuple[PACEObligationWorldScope, ...]
    required_predicate_ids: tuple[str, ...]
    derived_capability_ids: tuple[str, ...]
    evidence_capability_expressions: tuple[PACECapabilityExpression, ...]
    evidence_capability_sha256s: tuple[str, ...]
    accepted_action_alternative_ids: tuple[str, ...]
    accepted_document_alternative_ids: tuple[str, ...]
    evidence_item_id: str
    document_state: PACEDocumentState
    request_time: str
    source_ids: tuple[str, ...]
    locator_ids: tuple[str, ...]
    source_locator_bindings: tuple[PACESourceLocatorBinding, ...]
    outcome_partitions: tuple[PACEOutcomePartition, ...]
    static_priority: PACEStaticPriority
    action_id: str
    action_kind: Literal["acquire", "validate", "clarify", "replan"]
    process_node_id: str
    action_spec_sha256: str
    compiler_source_sha256: str
    verifier_source_sha256: str
    predecessor_event_sha256: str
    active_chain_provenance: tuple[PACEBranchProvenanceBinding, ...]
    hidden_oracle_inputs_read: Literal[False] = False
    certificate_sha256: str

    @model_validator(mode="after")
    def validate_certificate(self) -> PACEActionCertificate:
        hash_fields = (
            self.graph_sha256,
            self.state_sha256,
            self.compile_request_sha256,
            self.feasible_world_set_sha256,
            self.action_spec_sha256,
            self.compiler_source_sha256,
            self.verifier_source_sha256,
            self.predecessor_event_sha256,
            self.certificate_sha256,
            *self.feasible_world_sha256s,
            *(value.scope_sha256 for value in self.obligation_world_scopes),
            *self.evidence_capability_sha256s,
            *(value.binding_sha256 for value in self.active_chain_provenance),
        )
        if any(not is_sha256(value) for value in hash_fields):
            raise ValueError("certificate contains an invalid SHA-256 digest")
        for values, field in (
            (self.feasible_world_sha256s, "certificate world hashes"),
            (self.active_branch_ids, "certificate active branches"),
            (self.possible_branch_ids, "certificate possible branches"),
            (self.blocking_decision_ids, "certificate decisions"),
            (self.obligation_ids, "certificate obligations"),
            (self.required_predicate_ids, "certificate predicates"),
            (self.derived_capability_ids, "certificate derived capabilities"),
            (self.evidence_capability_sha256s, "certificate capabilities"),
            (self.accepted_action_alternative_ids, "certificate alternatives"),
            (
                self.accepted_document_alternative_ids,
                "certificate document alternatives",
            ),
            (self.source_ids, "certificate sources"),
            (self.locator_ids, "certificate locators"),
        ):
            _require_sorted_unique(values, field=field)
        expression_hashes = tuple(
            pace_digest_v1(value.model_dump(mode="json"))
            for value in self.evidence_capability_expressions
        )
        if expression_hashes != self.evidence_capability_sha256s:
            raise ValueError("certificate capability expressions and hashes disagree")
        provenance_keys = tuple(
            value.branch_id for value in self.active_chain_provenance
        )
        if provenance_keys != tuple(sorted(set(provenance_keys))):
            raise ValueError("certificate active-chain provenance is not canonical")
        scope_ids = tuple(value.obligation_id for value in self.obligation_world_scopes)
        if scope_ids != self.obligation_ids:
            raise ValueError("certificate obligation scopes do not cover obligations")
        if any(
            not set(value.world_sha256s).issubset(self.feasible_world_sha256s)
            for value in self.obligation_world_scopes
        ):
            raise ValueError("certificate obligation scope is outside feasible worlds")
        outcome_ids = tuple(value.outcome_id for value in self.outcome_partitions)
        _require_sorted_unique(outcome_ids, field="certificate outcomes")
        binding_keys = tuple(
            (value.source_id, value.locator_id)
            for value in self.source_locator_bindings
        )
        if binding_keys != tuple(sorted(set(binding_keys))):
            raise ValueError("source-locator bindings must be sorted and unique")
        if {value.source_id for value in self.source_locator_bindings} != set(
            self.source_ids
        ) or {value.locator_id for value in self.source_locator_bindings} != set(
            self.locator_ids
        ):
            raise ValueError("source-locator bindings do not cover exact source sets")
        _parse_utc(self.request_time)
        payload = self.model_dump(mode="json", exclude={"certificate_sha256"})
        if pace_digest_v1(payload) != self.certificate_sha256:
            raise ValueError("certificate_sha256 does not match certificate")
        return self


class PACECompileResult(PACEModel):
    contract: Literal["casepath.pace-compile-result/1.0.0"] = (
        "casepath.pace-compile-result/1.0.0"
    )
    request_sha256: str
    feasible_world_set_sha256: str
    certificate: PACEActionCertificate | None
    terminal_state: Literal[
        "ACTION_SELECTED",
        "ALL_WORLDS_AGREE",
        "NO_ADMISSIBLE_ACTION",
        "NO_FEASIBLE_WORLD",
        "NO_PROCESS_COVERAGE",
        "UNRESOLVED_AUTHORITY",
    ]
    unresolved_obligation_ids: tuple[str, ...]
    rejected_action_reasons: tuple[str, ...]
    result_sha256: str

    @model_validator(mode="after")
    def validate_result(self) -> PACECompileResult:
        _require_sorted_unique(
            self.unresolved_obligation_ids, field="result obligations"
        )
        _require_sorted_unique(
            self.rejected_action_reasons, field="result rejection reasons"
        )
        if self.terminal_state == "ACTION_SELECTED" and self.certificate is None:
            raise ValueError("selected action result lacks a certificate")
        if self.terminal_state != "ACTION_SELECTED" and self.certificate is not None:
            raise ValueError("terminal result cannot carry an action certificate")
        payload = self.model_dump(mode="json", exclude={"result_sha256"})
        if pace_digest_v1(payload) != self.result_sha256:
            raise ValueError("result_sha256 does not match compile result")
        return self


class PACEVerificationReceipt(PACEModel):
    contract: Literal["casepath.pace-verification-receipt/1.0.0"] = (
        "casepath.pace-verification-receipt/1.0.0"
    )
    request_sha256: str
    certificate_sha256: str
    verifier_source_sha256: str
    valid: bool
    failure_codes: tuple[str, ...]
    checked_world_count: int = Field(ge=0)
    hidden_oracle_inputs_read: Literal[False] = False
    receipt_sha256: str

    @model_validator(mode="after")
    def validate_receipt(self) -> PACEVerificationReceipt:
        for value in (
            self.request_sha256,
            self.certificate_sha256,
            self.verifier_source_sha256,
            self.receipt_sha256,
        ):
            if not is_sha256(value):
                raise ValueError("verification receipt contains an invalid digest")
        _require_sorted_unique(self.failure_codes, field="verification failure codes")
        if self.valid == bool(self.failure_codes):
            raise ValueError("verification validity contradicts failure codes")
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if pace_digest_v1(payload) != self.receipt_sha256:
            raise ValueError("receipt_sha256 does not match verification receipt")
        return self


PACECapabilityExpression.model_rebuild()
PACEObligationExpression.model_rebuild()
