from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from ..claim_loop_contracts import ClaimLoopState, EvidenceAction
from ..foundation.common import canonical_json_bytes, digest_value, is_sha256
from ..pace_canonical import canonical_pace_json_bytes_v1, pace_digest_v1
from ..pace_contracts import (
    PACEActionSpec,
    PACEAtom,
    PACEBranchProvenanceBinding,
    PACECapabilityExpression,
    PACECompileRequest,
    PACECompileResult,
    PACECompilerConfig,
    PACECondition,
    PACEDocumentRecord,
    PACEHistoryEvent,
    PACEModel,
    PACEObligationKind,
    PACEObligationExpression,
    PACEObligationSpec,
    PACEObservation,
    PACEProcessEvidenceGraph,
    PACESourceLocatorBinding,
    PACESourceRecord,
    PACEState,
    PACEVerificationReceipt,
)
from .verifier import verify_certificate_v1, verify_compile_result_v1


class PACEKernelActionProjectionV1(PACEModel):
    """Frozen semantic projection for one action, never a selected action input."""

    pace_action_id: str = Field(min_length=1)
    action_kind: Literal["acquire", "validate", "clarify", "replan"]
    process_node_id: str = Field(min_length=1)
    evidence_item_id: str = Field(min_length=1)
    fact_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    bounded_tool_id: str | None


class PACEKernelBlueprintV1(PACEModel):
    """Complete outcome-blind static input required to construct a request."""

    contract: Literal["casepath.pace-kernel-blueprint/1.0.0"] = (
        "casepath.pace-kernel-blueprint/1.0.0"
    )
    template_version: str = Field(min_length=1)
    graph: PACEProcessEvidenceGraph
    sources: tuple[PACESourceRecord, ...] = Field(min_length=1)
    obligations: tuple[PACEObligationSpec, ...] = Field(min_length=1)
    obligation_expression: PACEObligationExpression
    actions: tuple[PACEActionSpec, ...] = Field(min_length=1)
    action_projections: tuple[PACEKernelActionProjectionV1, ...] = Field(min_length=1)
    config: PACECompilerConfig
    blueprint_sha256: str

    @model_validator(mode="after")
    def validate_blueprint(self) -> PACEKernelBlueprintV1:
        if not is_sha256(self.blueprint_sha256):
            raise ValueError("kernel blueprint identity is invalid")
        for values, label in (
            (tuple(value.source_id for value in self.sources), "source"),
            (tuple(value.obligation_id for value in self.obligations), "obligation"),
            (tuple(value.action_id for value in self.actions), "action"),
            (
                tuple(value.pace_action_id for value in self.action_projections),
                "action projection",
            ),
        ):
            if values != tuple(sorted(set(values))):
                raise ValueError(f"kernel blueprint {label} roster is not canonical")
        if {value.action_id for value in self.actions} != {
            value.pace_action_id for value in self.action_projections
        }:
            raise ValueError("kernel blueprint action projections are not exact")
        actions = {value.action_id: value for value in self.actions}
        obligations = {value.obligation_id: value for value in self.obligations}
        action_obligation_ids = {
            obligation_id
            for action in self.actions
            for obligation_id in action.obligation_ids
        }
        if not action_obligation_ids.issubset(obligations):
            raise ValueError("kernel action references an unknown obligation")

        expression_ids = self.obligation_expression.referenced_obligation_ids()
        canonical_obligation_ids = tuple(
            value.obligation_id for value in self.obligations
        )
        obligation_ids = frozenset(obligations)
        if (
            expression_ids != canonical_obligation_ids
            or action_obligation_ids != obligation_ids
        ):
            raise ValueError(
                "kernel blueprint obligations lack complete expression/action coverage"
            )
        if any(
            obligation.kind
            not in {
                PACEObligationKind.ESTABLISH,
                PACEObligationKind.REFUTE,
                PACEObligationKind.RESOLVE_CONFLICT,
            }
            or len(obligation.predicate_ids) != 1
            for obligation in self.obligations
        ):
            raise ValueError(
                "kernel blueprint obligation is not lossless in the single-fact ABI"
            )
        capabilities = {
            value.capability_id: value for value in self.graph.capability_specs
        }
        predicate_domains = {
            value.predicate_id: set(value.domain)
            for value in self.graph.predicate_specs
        }
        predicate_ids = set(predicate_domains)
        source_by_id = {value.source_id: value for value in self.sources}
        process_node_ids = {value.node_id for value in self.graph.nodes}

        def require_atom(atom: PACEAtom, *, field: str) -> None:
            if (
                atom.predicate_id not in predicate_domains
                or atom.value not in predicate_domains[atom.predicate_id]
            ):
                raise ValueError(f"kernel {field} atom is outside the predicate catalog")

        def require_condition(condition: PACECondition, *, field: str) -> None:
            for clause in condition.clauses:
                for atom in clause.atoms:
                    require_atom(atom, field=field)

        def require_expression(expression: PACEObligationExpression) -> None:
            if expression.condition is not None:
                require_condition(expression.condition, field="expression condition")
            for child in expression.children:
                require_expression(child)

        def expression_capability_ids(
            expression: PACECapabilityExpression,
        ) -> frozenset[str]:
            if expression.capability_id is not None:
                return frozenset({expression.capability_id})
            return frozenset(
                capability_id
                for child in expression.children
                for capability_id in expression_capability_ids(child)
            )

        for capability in self.graph.capability_specs:
            if not set(capability.source_ids).issubset(source_by_id) or any(
                binding.locator_id
                not in source_by_id[binding.source_id].locator_ids
                for binding in capability.source_locator_bindings
            ):
                raise ValueError("kernel capability source binding is invalid")
        require_expression(self.obligation_expression)
        for obligation in self.obligations:
            if (
                obligation.process_node_id not in process_node_ids
                or not set(obligation.predicate_ids).issubset(predicate_ids)
                or not set(obligation.source_ids).issubset(source_by_id)
                or not expression_capability_ids(
                    obligation.evidence_capability
                ).issubset(capabilities)
            ):
                raise ValueError("kernel obligation cross-reference is invalid")
            require_condition(obligation.activation, field="obligation activation")
            for atom in obligation.target_atoms:
                require_atom(atom, field="obligation target")
        for action in self.actions:
            if (
                action.process_node_id not in process_node_ids
                or not set(action.source_ids).issubset(source_by_id)
                or not set(action.capability_ids).issubset(capabilities)
            ):
                raise ValueError("kernel action cross-reference is invalid")
            for outcome in action.outcomes:
                for atom in outcome.restrictions:
                    require_atom(atom, field="action outcome")
        for projection in self.action_projections:
            action = actions[projection.pace_action_id]
            addressed_predicates = {
                predicate_id
                for obligation_id in action.obligation_ids
                for predicate_id in obligations[obligation_id].predicate_ids
            }
            capability_predicates = {
                predicate_id
                for capability_id in action.capability_ids
                for predicate_id in capabilities[capability_id].predicate_ids
            }
            outcome_predicates = {
                atom.predicate_id
                for outcome in action.outcomes
                for atom in outcome.restrictions
            }
            if (
                projection.action_kind != action.action_kind
                or projection.process_node_id != action.process_node_id
                or projection.evidence_item_id != action.evidence_item_id
                or projection.fact_id not in predicate_ids
                or addressed_predicates != {projection.fact_id}
                or capability_predicates != {projection.fact_id}
                or outcome_predicates != {projection.fact_id}
            ):
                raise ValueError(
                    "kernel action projection is not lossless in the single-fact ABI"
                )
        payload = self.model_dump(mode="json", exclude={"blueprint_sha256"})
        if pace_digest_v1(payload) != self.blueprint_sha256:
            raise ValueError("kernel blueprint self-hash mismatch")
        return self


class PACEKernelCompletedActionV1(PACEModel):
    """Completed observable action without raw kernel event/action fingerprints."""

    action_kind: Literal["acquire", "validate", "clarify", "replan"]
    process_node_id: str = Field(min_length=1)
    evidence_item_id: str = Field(min_length=1)
    fact_id: str = Field(min_length=1)
    bounded_tool_id: str | None
    outcome: Literal["observed", "unavailable", "failed", "unknown"]
    observation_sha256: str | None
    recorded_at: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_observation_hash(self) -> PACEKernelCompletedActionV1:
        if self.observation_sha256 is not None and not is_sha256(
            self.observation_sha256
        ):
            raise ValueError("kernel completed action observation identity is invalid")
        return self


class PACEKernelObservableSnapshotV1(PACEModel):
    """Closed compiler-visible state: no selected action or raw event hash."""

    contract: Literal["casepath.pace-kernel-observable-snapshot/1.0.0"] = (
        "casepath.pace-kernel-observable-snapshot/1.0.0"
    )
    record_version: str = Field(min_length=1)
    template_version: str = Field(min_length=1)
    process_version: str = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    source_registry_version: str = Field(min_length=1)
    knowledge_version: str = Field(min_length=1)
    observations: tuple[PACEObservation, ...]
    documents: tuple[PACEDocumentRecord, ...] = Field(min_length=1)
    completed_history: tuple[PACEKernelCompletedActionV1, ...]
    current_time: str = Field(min_length=1)
    snapshot_sha256: str

    @model_validator(mode="after")
    def validate_snapshot(self) -> PACEKernelObservableSnapshotV1:
        if not is_sha256(self.snapshot_sha256):
            raise ValueError("kernel observable snapshot identity is invalid")
        observation_ids = tuple(value.observation_id for value in self.observations)
        document_ids = tuple(value.evidence_item_id for value in self.documents)
        if observation_ids != tuple(sorted(set(observation_ids))):
            raise ValueError("kernel observations are not sorted and unique")
        if document_ids != tuple(sorted(set(document_ids))):
            raise ValueError("kernel documents are not sorted and unique")
        history_keys = tuple(
            (value.recorded_at, pace_digest_v1(value.model_dump(mode="json")))
            for value in self.completed_history
        )
        if history_keys != tuple(sorted(history_keys)):
            raise ValueError("kernel completed history is not chronological")
        payload = self.model_dump(mode="json", exclude={"snapshot_sha256"})
        if pace_digest_v1(payload) != self.snapshot_sha256:
            raise ValueError("kernel observable snapshot self-hash mismatch")
        return self


class PACEKernelInputV1(PACEModel):
    """The sole preimage accepted by the deterministic request constructor."""

    contract: Literal["casepath.pace-kernel-input/1.0.0"] = (
        "casepath.pace-kernel-input/1.0.0"
    )
    blueprint: PACEKernelBlueprintV1
    snapshot: PACEKernelObservableSnapshotV1
    input_sha256: str

    @model_validator(mode="after")
    def validate_input(self) -> PACEKernelInputV1:
        if not is_sha256(self.input_sha256):
            raise ValueError("kernel input identity is invalid")
        if (
            self.snapshot.template_version != self.blueprint.template_version
            or self.snapshot.process_version != self.blueprint.graph.process_version
            or self.snapshot.rule_version != self.blueprint.graph.rule_version
            or self.snapshot.source_registry_version
            != self.blueprint.graph.source_registry_version
            or self.snapshot.knowledge_version != self.blueprint.graph.knowledge_version
        ):
            raise ValueError("kernel snapshot versions disagree with blueprint")
        payload = self.model_dump(mode="json", exclude={"input_sha256"})
        if pace_digest_v1(payload) != self.input_sha256:
            raise ValueError("kernel input self-hash mismatch")
        return self


class PACEKernelProvenanceEnvelopeV1(PACEModel):
    """Audit-only kernel identities; never passed to the compiler."""

    contract: Literal["casepath.pace-kernel-provenance-envelope/1.0.0"] = (
        "casepath.pace-kernel-provenance-envelope/1.0.0"
    )
    iteration29_root_anchor_file_sha256: str
    iteration29_source_manifest_file_sha256: str
    adapter_source_sha256: str
    session_id: str = Field(min_length=1)
    loop_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    source_state_sha256: str
    source_last_event_sha256: str
    accepted_artifacts_sha256: str
    accepted_cycle_artifacts_sha256: str
    blueprint_sha256: str | None
    snapshot_sha256: str | None
    kernel_input_sha256: str | None
    envelope_sha256: str

    @model_validator(mode="after")
    def validate_envelope(self) -> PACEKernelProvenanceEnvelopeV1:
        required = (
            self.iteration29_root_anchor_file_sha256,
            self.iteration29_source_manifest_file_sha256,
            self.adapter_source_sha256,
            self.source_state_sha256,
            self.source_last_event_sha256,
            self.accepted_artifacts_sha256,
            self.accepted_cycle_artifacts_sha256,
            self.envelope_sha256,
        )
        optional = (
            self.blueprint_sha256,
            self.snapshot_sha256,
            self.kernel_input_sha256,
        )
        if any(not is_sha256(value) for value in required) or any(
            value is not None and not is_sha256(value) for value in optional
        ):
            raise ValueError("kernel provenance envelope contains an invalid digest")
        if (self.blueprint_sha256 is None) != (self.snapshot_sha256 is None) or (
            self.snapshot_sha256 is None
        ) != (self.kernel_input_sha256 is None):
            raise ValueError("kernel provenance input identities are incomplete")
        payload = self.model_dump(mode="json", exclude={"envelope_sha256"})
        if pace_digest_v1(payload) != self.envelope_sha256:
            raise ValueError("kernel provenance envelope self-hash mismatch")
        return self


class PACEKernelAdapterReadinessReceiptV1(PACEModel):
    contract: Literal["casepath.pace-kernel-adapter-readiness/1.0.0"] = (
        "casepath.pace-kernel-adapter-readiness/1.0.0"
    )
    classification: Literal["PACE_CORE_ADAPTER_NOT_READY"]
    reason_code: Literal["NEUTRAL_BLUEPRINT_UNAVAILABLE"]
    provenance_envelope_sha256: str
    request_constructed: Literal[False] = False
    compiler_executed: Literal[False] = False
    certificate_emitted: Literal[False] = False
    kernel_mutated: Literal[False] = False
    receipt_sha256: str

    @model_validator(mode="after")
    def validate_receipt(self) -> PACEKernelAdapterReadinessReceiptV1:
        if not is_sha256(self.provenance_envelope_sha256) or not is_sha256(
            self.receipt_sha256
        ):
            raise ValueError("kernel adapter readiness identity is invalid")
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if pace_digest_v1(payload) != self.receipt_sha256:
            raise ValueError("kernel adapter readiness self-hash mismatch")
        return self


class PACEKernelCompatibilityReceiptV1(PACEModel):
    contract: Literal["casepath.pace-kernel-compatibility/1.0.0"] = (
        "casepath.pace-kernel-compatibility/1.0.0"
    )
    kernel_input_sha256: str
    provenance_envelope_sha256: str
    derived_request_sha256: str
    result_sha256: str
    certificate_sha256: str
    supplied_verification_receipt_sha256: str
    recomputed_verification_receipt_sha256: str
    legacy_action_sha256: str
    compatible: bool
    mismatch_codes: tuple[str, ...]
    shadow_only: Literal[True] = True
    kernel_mutated: Literal[False] = False
    receipt_sha256: str

    @model_validator(mode="after")
    def validate_receipt(self) -> PACEKernelCompatibilityReceiptV1:
        hashes = (
            self.kernel_input_sha256,
            self.provenance_envelope_sha256,
            self.derived_request_sha256,
            self.result_sha256,
            self.certificate_sha256,
            self.supplied_verification_receipt_sha256,
            self.recomputed_verification_receipt_sha256,
            self.legacy_action_sha256,
            self.receipt_sha256,
        )
        if any(not is_sha256(value) for value in hashes):
            raise ValueError("compatibility receipt contains an invalid digest")
        if self.mismatch_codes != tuple(sorted(set(self.mismatch_codes))):
            raise ValueError("compatibility mismatch codes are not canonical")
        if self.compatible == bool(self.mismatch_codes):
            raise ValueError("compatibility status contradicts mismatch codes")
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if pace_digest_v1(payload) != self.receipt_sha256:
            raise ValueError("compatibility receipt self-hash mismatch")
        return self


def _branch_provenance(
    graph: PACEProcessEvidenceGraph,
    observations: tuple[PACEObservation, ...],
) -> tuple[PACEBranchProvenanceBinding, ...]:
    rows: list[PACEBranchProvenanceBinding] = []
    for branch in graph.branches:
        predicates = {
            atom.predicate_id
            for clause in branch.condition.clauses
            for atom in clause.atoms
        }
        bound = tuple(
            value for value in observations if value.predicate_id in predicates
        )
        pairs = tuple(
            sorted(
                {
                    (value.source_id, value.locator_id)
                    for value in bound
                }
            )
        )
        payload = {
            "branch_id": branch.branch_id,
            "graph_sha256": graph.graph_sha256,
            "observation_ids": sorted(value.observation_id for value in bound),
            "source_locator_bindings": [
                PACESourceLocatorBinding(source_id=source_id, locator_id=locator_id)
                .model_dump(mode="json")
                for source_id, locator_id in pairs
            ],
        }
        rows.append(
            PACEBranchProvenanceBinding.model_validate_json(
                canonical_pace_json_bytes_v1(
                    {**payload, "binding_sha256": pace_digest_v1(payload)}
                )
            )
        )
    return tuple(sorted(rows, key=lambda value: value.branch_id))


def compile_request_from_kernel_input_v1(
    kernel_input: PACEKernelInputV1,
) -> PACECompileRequest:
    """Construct the entire request from one closed canonical adapter input."""

    kernel_input = PACEKernelInputV1.model_validate_json(
        canonical_pace_json_bytes_v1(kernel_input.model_dump(mode="json"))
    )
    blueprint = kernel_input.blueprint
    snapshot = kernel_input.snapshot
    safe_predecessor = pace_digest_v1(
        {
            "domain": "casepath.pace-safe-predecessor/1.0.0",
            "snapshot_sha256": snapshot.snapshot_sha256,
            "completed_history": [
                value.model_dump(mode="json") for value in snapshot.completed_history
            ],
        }
    )
    history_payload = {
        "event_id": f"pace.snapshot.{safe_predecessor}",
        "event_type": "KERNEL_OBSERVABLE_SNAPSHOT_PROJECTED",
        "recorded_at": snapshot.current_time,
    }
    history = PACEHistoryEvent.model_validate_json(
        canonical_pace_json_bytes_v1(
            {**history_payload, "event_sha256": pace_digest_v1(history_payload)}
        )
    )
    state_payload = {
        "contract": "casepath.pace-state/1.0.0",
        "graph": blueprint.graph.model_dump(mode="json"),
        "observations": [
            value.model_dump(mode="json") for value in snapshot.observations
        ],
        "sources": [value.model_dump(mode="json") for value in blueprint.sources],
        "documents": [
            value.model_dump(mode="json") for value in snapshot.documents
        ],
        "history": [history.model_dump(mode="json")],
        "current_time": snapshot.current_time,
        "kernel_snapshot_sha256": kernel_input.input_sha256,
        "predecessor_event_sha256": history.event_sha256,
        "branch_provenance": [
            value.model_dump(mode="json")
            for value in _branch_provenance(blueprint.graph, snapshot.observations)
        ],
    }
    state = PACEState.model_validate_json(
        canonical_pace_json_bytes_v1(
            {**state_payload, "state_sha256": pace_digest_v1(state_payload)}
        )
    )
    request_payload = {
        "contract": "casepath.pace-compile-request/1.0.0",
        "state": state.model_dump(mode="json"),
        "obligations": [
            value.model_dump(mode="json") for value in blueprint.obligations
        ],
        "obligation_expression": blueprint.obligation_expression.model_dump(
            mode="json"
        ),
        "actions": [value.model_dump(mode="json") for value in blueprint.actions],
        "config": blueprint.config.model_dump(mode="json"),
    }
    return PACECompileRequest.model_validate_json(
        canonical_pace_json_bytes_v1(
            {**request_payload, "request_sha256": pace_digest_v1(request_payload)}
        )
    )


def make_kernel_input_v1(
    *,
    blueprint: PACEKernelBlueprintV1,
    snapshot: PACEKernelObservableSnapshotV1,
) -> PACEKernelInputV1:
    payload = {
        "contract": "casepath.pace-kernel-input/1.0.0",
        "blueprint": blueprint.model_dump(mode="json"),
        "snapshot": snapshot.model_dump(mode="json"),
    }
    return PACEKernelInputV1.model_validate_json(
        canonical_pace_json_bytes_v1(
            {**payload, "input_sha256": pace_digest_v1(payload)}
        )
    )


def _provenance_envelope(
    state: ClaimLoopState,
    *,
    iteration29_root_anchor_file_sha256: str,
    iteration29_source_manifest_file_sha256: str,
    adapter_source_sha256: str,
    kernel_input: PACEKernelInputV1 | None,
) -> PACEKernelProvenanceEnvelopeV1:
    payload = {
        "contract": "casepath.pace-kernel-provenance-envelope/1.0.0",
        "iteration29_root_anchor_file_sha256": (
            iteration29_root_anchor_file_sha256
        ),
        "iteration29_source_manifest_file_sha256": (
            iteration29_source_manifest_file_sha256
        ),
        "adapter_source_sha256": adapter_source_sha256,
        "session_id": state.session_id,
        "loop_id": state.loop_id,
        "revision": state.revision,
        "source_state_sha256": state.state_sha256,
        "source_last_event_sha256": state.last_event_sha256,
        "accepted_artifacts_sha256": state.accepted_artifacts_sha256,
        "accepted_cycle_artifacts_sha256": state.accepted_cycle_artifacts_sha256,
        "blueprint_sha256": (
            kernel_input.blueprint.blueprint_sha256 if kernel_input else None
        ),
        "snapshot_sha256": (
            kernel_input.snapshot.snapshot_sha256 if kernel_input else None
        ),
        "kernel_input_sha256": kernel_input.input_sha256 if kernel_input else None,
    }
    return PACEKernelProvenanceEnvelopeV1.model_validate_json(
        canonical_pace_json_bytes_v1(
            {**payload, "envelope_sha256": pace_digest_v1(payload)}
        )
    )


def project_kernel_state_v1(
    state: ClaimLoopState,
    *,
    iteration29_root_anchor_file_sha256: str,
    iteration29_source_manifest_file_sha256: str,
    adapter_source_sha256: str,
) -> tuple[PACEKernelAdapterReadinessReceiptV1, PACEKernelProvenanceEnvelopeV1]:
    """Fail before compilation until a neutral real playbook blueprint is frozen."""

    state = ClaimLoopState.model_validate_json(
        canonical_json_bytes(state.model_dump(mode="json"))
    )
    envelope = _provenance_envelope(
        state,
        iteration29_root_anchor_file_sha256=(
            iteration29_root_anchor_file_sha256
        ),
        iteration29_source_manifest_file_sha256=(
            iteration29_source_manifest_file_sha256
        ),
        adapter_source_sha256=adapter_source_sha256,
        kernel_input=None,
    )
    payload = {
        "contract": "casepath.pace-kernel-adapter-readiness/1.0.0",
        "classification": "PACE_CORE_ADAPTER_NOT_READY",
        "reason_code": "NEUTRAL_BLUEPRINT_UNAVAILABLE",
        "provenance_envelope_sha256": envelope.envelope_sha256,
        "request_constructed": False,
        "compiler_executed": False,
        "certificate_emitted": False,
        "kernel_mutated": False,
    }
    receipt = PACEKernelAdapterReadinessReceiptV1.model_validate_json(
        canonical_pace_json_bytes_v1(
            {**payload, "receipt_sha256": pace_digest_v1(payload)}
        )
    )
    return receipt, envelope


def build_fixture_provenance_envelope_v1(
    *,
    kernel_input: PACEKernelInputV1,
    iteration29_root_anchor_file_sha256: str,
    iteration29_source_manifest_file_sha256: str,
    adapter_source_sha256: str,
) -> PACEKernelProvenanceEnvelopeV1:
    """Build an audit envelope for the synthetic invariant fixture only."""

    payload = {
        "contract": "casepath.pace-kernel-provenance-envelope/1.0.0",
        "iteration29_root_anchor_file_sha256": (
            iteration29_root_anchor_file_sha256
        ),
        "iteration29_source_manifest_file_sha256": (
            iteration29_source_manifest_file_sha256
        ),
        "adapter_source_sha256": adapter_source_sha256,
        "session_id": "synthetic-invariant-session",
        "loop_id": "synthetic-invariant-loop",
        "revision": 1,
        "source_state_sha256": "3" * 64,
        "source_last_event_sha256": "4" * 64,
        "accepted_artifacts_sha256": "5" * 64,
        "accepted_cycle_artifacts_sha256": "6" * 64,
        "blueprint_sha256": kernel_input.blueprint.blueprint_sha256,
        "snapshot_sha256": kernel_input.snapshot.snapshot_sha256,
        "kernel_input_sha256": kernel_input.input_sha256,
    }
    return PACEKernelProvenanceEnvelopeV1.model_validate_json(
        canonical_pace_json_bytes_v1(
            {**payload, "envelope_sha256": pace_digest_v1(payload)}
        )
    )


def compare_certificate_to_legacy_action_v1(
    kernel_input: PACEKernelInputV1,
    provenance: PACEKernelProvenanceEnvelopeV1,
    result: PACECompileResult,
    supplied_verification: PACEVerificationReceipt,
    legacy_action: EvidenceAction,
    *,
    expected_iteration29_root_anchor_file_sha256: str,
    expected_iteration29_source_manifest_file_sha256: str,
    expected_adapter_source_sha256: str,
    expected_blueprint_sha256: str,
    expected_snapshot_sha256: str,
    expected_kernel_input_sha256: str,
    expected_compiler_source_sha256: str,
    expected_verifier_source_sha256: str,
) -> PACEKernelCompatibilityReceiptV1:
    """Rebuild and independently verify every join before shadow comparison."""

    kernel_input = PACEKernelInputV1.model_validate_json(
        canonical_pace_json_bytes_v1(kernel_input.model_dump(mode="json"))
    )
    provenance = PACEKernelProvenanceEnvelopeV1.model_validate_json(
        canonical_pace_json_bytes_v1(provenance.model_dump(mode="json"))
    )
    result = PACECompileResult.model_validate_json(
        canonical_pace_json_bytes_v1(result.model_dump(mode="json"))
    )
    supplied_verification = PACEVerificationReceipt.model_validate_json(
        canonical_pace_json_bytes_v1(supplied_verification.model_dump(mode="json"))
    )
    legacy_action = EvidenceAction.model_validate_json(
        canonical_json_bytes(legacy_action.model_dump(mode="json"))
    )
    request = compile_request_from_kernel_input_v1(kernel_input)
    certificate = result.certificate
    mismatches: list[str] = []
    if (
        provenance.iteration29_root_anchor_file_sha256
        != expected_iteration29_root_anchor_file_sha256
        or provenance.iteration29_source_manifest_file_sha256
        != expected_iteration29_source_manifest_file_sha256
        or provenance.adapter_source_sha256 != expected_adapter_source_sha256
    ):
        mismatches.append("EXTERNAL_PROVENANCE_ANCHOR_MISMATCH")
    if (
        kernel_input.blueprint.blueprint_sha256 != expected_blueprint_sha256
        or kernel_input.snapshot.snapshot_sha256 != expected_snapshot_sha256
        or kernel_input.input_sha256 != expected_kernel_input_sha256
    ):
        mismatches.append("EXTERNAL_KERNEL_INPUT_ANCHOR_MISMATCH")
    if (
        provenance.blueprint_sha256 != kernel_input.blueprint.blueprint_sha256
        or provenance.snapshot_sha256 != kernel_input.snapshot.snapshot_sha256
        or provenance.kernel_input_sha256 != kernel_input.input_sha256
    ):
        mismatches.append("PROVENANCE_INPUT_MISMATCH")
    if result.request_sha256 != request.request_sha256:
        mismatches.append("RESULT_REQUEST_MISMATCH")
    if verify_compile_result_v1(
        request,
        result,
        expected_compiler_source_sha256=expected_compiler_source_sha256,
        verifier_source_sha256=expected_verifier_source_sha256,
    ):
        mismatches.append("RESULT_RECOMPUTATION_MISMATCH")
    certificate_sha256 = certificate.certificate_sha256 if certificate else "0" * 64
    recomputed = supplied_verification
    if certificate is None:
        mismatches.append("CERTIFICATE_ABSENT")
    else:
        if (
            result.terminal_state != "ACTION_SELECTED"
            or result.feasible_world_set_sha256
            != certificate.feasible_world_set_sha256
            or not set(certificate.obligation_ids).issubset(
                result.unresolved_obligation_ids
            )
            or any(
                value.startswith(f"{certificate.action_id}:")
                for value in result.rejected_action_reasons
            )
        ):
            mismatches.append("RESULT_CERTIFICATE_CROSS_BINDING_MISMATCH")
        recomputed = verify_certificate_v1(
            request,
            certificate,
            expected_compiler_source_sha256=expected_compiler_source_sha256,
            verifier_source_sha256=expected_verifier_source_sha256,
        )
        if (
            supplied_verification.model_dump(mode="json")
            != recomputed.model_dump(mode="json")
            or not recomputed.valid
        ):
            mismatches.append("VERIFICATION_RECOMPUTATION_MISMATCH")
        if certificate.case_id != kernel_input.blueprint.graph.case_id:
            mismatches.append("CASE_TOKEN_MISMATCH")
        if certificate.graph_sha256 != kernel_input.blueprint.graph.graph_sha256:
            mismatches.append("CERTIFICATE_GRAPH_MISMATCH")
        projections = tuple(
            value
            for value in kernel_input.blueprint.action_projections
            if value.pace_action_id == certificate.action_id
        )
        if len(projections) != 1:
            mismatches.append("ACTION_PROJECTION_ABSENT")
        else:
            projection = projections[0]
            if certificate.required_predicate_ids != (projection.fact_id,):
                mismatches.append("ACTION_PROJECTION_SEMANTIC_MISMATCH")
            reconstructed = {
                "contract": "casepath.evidence-action/1.0.0",
                "action_kind": projection.action_kind,
                "process_node_id": projection.process_node_id,
                "evidence_item_id": projection.evidence_item_id,
                "fact_id": projection.fact_id,
                "title": projection.title,
                "bounded_tool_id": projection.bounded_tool_id,
            }
            reconstructed_sha = digest_value(reconstructed)
            if (
                reconstructed_sha != legacy_action.action_sha256
                or legacy_action.action_id != f"action.{reconstructed_sha}"
                or reconstructed
                != legacy_action.model_dump(
                    mode="json", exclude={"action_id", "action_sha256"}
                )
            ):
                mismatches.append("LEGACY_ACTION_RECONSTRUCTION_MISMATCH")
    payload = {
        "contract": "casepath.pace-kernel-compatibility/1.0.0",
        "kernel_input_sha256": kernel_input.input_sha256,
        "provenance_envelope_sha256": provenance.envelope_sha256,
        "derived_request_sha256": request.request_sha256,
        "result_sha256": result.result_sha256,
        "certificate_sha256": certificate_sha256,
        "supplied_verification_receipt_sha256": supplied_verification.receipt_sha256,
        "recomputed_verification_receipt_sha256": recomputed.receipt_sha256,
        "legacy_action_sha256": legacy_action.action_sha256,
        "compatible": not mismatches,
        "mismatch_codes": sorted(set(mismatches)),
        "shadow_only": True,
        "kernel_mutated": False,
    }
    return PACEKernelCompatibilityReceiptV1.model_validate_json(
        canonical_pace_json_bytes_v1(
            {**payload, "receipt_sha256": pace_digest_v1(payload)}
        )
    )
