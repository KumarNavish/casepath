from __future__ import annotations

from ..pace_canonical import canonical_pace_json_bytes_v1, pace_digest_v1
from ..pace_contracts import (
    PACEActionSpec,
    PACEAtom,
    PACEBranchSpec,
    PACEBranchProvenanceBinding,
    PACECapabilityLocatorBinding,
    PACECapabilityExpression,
    PACECapabilityOperator,
    PACECompileRequest,
    PACECompilerConfig,
    PACECondition,
    PACEConjunction,
    PACEDocumentRecord,
    PACEDocumentState,
    PACEHistoryEvent,
    PACEEvidenceCapabilitySpec,
    PACEObligationKind,
    PACEObligationExpression,
    PACEObligationSpec,
    PACEObservation,
    PACEOutcomeSpec,
    PACEPredicateSpec,
    PACEProcessEdgeSpec,
    PACEProcessEvidenceGraph,
    PACEProcessNodeSpec,
    PACESourceLocatorBinding,
    PACESourceRecord,
    PACEState,
    PACETruthPolarity,
)


_NOW = "2026-04-30T12:00:00+00:00"


def _dnf(predicate_id: str, value: str) -> PACECondition:
    return PACECondition(
        operator="DNF",
        clauses=(
            PACEConjunction(atoms=(PACEAtom(predicate_id=predicate_id, value=value),)),
        ),
    )


def _leaf(capability_id: str) -> PACECapabilityExpression:
    return PACECapabilityExpression(
        operator=PACECapabilityOperator.CAPABILITY,
        capability_id=capability_id,
    )


def build_invariant_request_v1() -> PACECompileRequest:
    graph_payload = {
        "contract": "casepath.pace-process-evidence-graph/1.0.0",
        "case_id": "SYNTHETIC-PACE-INVARIANT-001",
        "process_version": "pace-fixture-process-v1",
        "rule_version": "pace-fixture-rules-v1",
        "source_registry_version": "pace-fixture-sources-v1",
        "knowledge_version": "pace-fixture-knowledge-v1",
        "predicate_specs": [
            PACEPredicateSpec(
                predicate_id="causation_supported",
                domain=("false", "true"),
                semantic_type="boolean",
            ).model_dump(mode="json"),
            PACEPredicateSpec(
                predicate_id="claim_timely",
                domain=("false", "true"),
                semantic_type="boolean",
            ).model_dump(mode="json"),
        ],
        "constraints": [],
        "nodes": [
            PACEProcessNodeSpec(
                node_id="acquire_causation_support",
                node_kind="decision",
                topological_index=3,
            ).model_dump(mode="json"),
            PACEProcessNodeSpec(
                node_id="entry", node_kind="entry", topological_index=0
            ).model_dump(mode="json"),
            PACEProcessNodeSpec(
                node_id="evidence_gap_causation",
                node_kind="evidence",
                topological_index=2,
            ).model_dump(mode="json"),
            PACEProcessNodeSpec(
                node_id="inactive_future_node",
                node_kind="decision",
                topological_index=1,
            ).model_dump(mode="json"),
            PACEProcessNodeSpec(
                node_id="merits_review",
                node_kind="terminal",
                topological_index=4,
            ).model_dump(mode="json"),
        ],
        "edges": [
            PACEProcessEdgeSpec(
                edge_id="edge.entry",
                source_node_id="entry",
                target_node_id="evidence_gap_causation",
                branch_id=None,
            ).model_dump(mode="json"),
            PACEProcessEdgeSpec(
                edge_id="edge.evidence_gap",
                source_node_id="evidence_gap_causation",
                target_node_id="acquire_causation_support",
                branch_id="branch.evidence_gap",
            ).model_dump(mode="json"),
            PACEProcessEdgeSpec(
                edge_id="edge.inactive",
                source_node_id="entry",
                target_node_id="inactive_future_node",
                branch_id=None,
            ).model_dump(mode="json"),
            PACEProcessEdgeSpec(
                edge_id="edge.merits",
                source_node_id="evidence_gap_causation",
                target_node_id="merits_review",
                branch_id="branch.merits",
            ).model_dump(mode="json"),
        ],
        "branches": [
            PACEBranchSpec(
                branch_id="branch.evidence_gap",
                process_node_id="evidence_gap_causation",
                target_node_id="acquire_causation_support",
                decision_id="decision.acquire_causation",
                condition=_dnf("causation_supported", "false"),
            ).model_dump(mode="json"),
            PACEBranchSpec(
                branch_id="branch.merits",
                process_node_id="evidence_gap_causation",
                target_node_id="merits_review",
                decision_id="decision.merits_review",
                condition=_dnf("causation_supported", "true"),
            ).model_dump(mode="json"),
        ],
        "capability_specs": [
            PACEEvidenceCapabilitySpec(
                capability_id="capability.exact_locator",
                evidence_item_id="evidence.causation_support",
                action_kinds=("acquire",),
                predicate_ids=("causation_supported",),
                source_ids=("source.medical_record",),
                source_locator_bindings=(
                    PACECapabilityLocatorBinding(
                        source_id="source.medical_record",
                        locator_id="locator.causation_section",
                    ),
                ),
            ).model_dump(mode="json"),
            PACEEvidenceCapabilitySpec(
                capability_id="capability.fact_causation",
                evidence_item_id="evidence.causation_support",
                action_kinds=("acquire",),
                predicate_ids=("causation_supported",),
                source_ids=("source.medical_record",),
                source_locator_bindings=(
                    PACECapabilityLocatorBinding(
                        source_id="source.medical_record",
                        locator_id="locator.causation_section",
                    ),
                ),
            ).model_dump(mode="json"),
        ],
        "critical_decision_ids": [
            "decision.acquire_causation",
            "decision.merits_review",
        ],
    }
    graph = PACEProcessEvidenceGraph.model_validate_json(
        canonical_pace_json_bytes_v1(
            {**graph_payload, "graph_sha256": pace_digest_v1(graph_payload)}
        )
    )
    source = PACESourceRecord(
        source_id="source.medical_record",
        source_version="medical-record-v1",
        source_sha256="1" * 64,
        locator_ids=("locator.causation_section", "locator.timeliness_field"),
        authority_valid=True,
        valid_from="2026-01-01T00:00:00+00:00",
        valid_until="2026-12-31T23:59:59+00:00",
    )
    observation_payload = {
        "contract": "casepath.pace-observation/1.0.0",
        "observation_id": "observation.claim_timely",
        "predicate_id": "claim_timely",
        "allowed_values": ["true"],
        "polarity": PACETruthPolarity.SUPPORTS.value,
        "source_id": source.source_id,
        "source_version": source.source_version,
        "locator_id": "locator.timeliness_field",
        "observed_at": _NOW,
        "reliability_milli": 1000,
    }
    observation = PACEObservation.model_validate_json(
        canonical_pace_json_bytes_v1(
            {
                **observation_payload,
                "observation_sha256": pace_digest_v1(observation_payload),
            }
        )
    )
    history_payload = {
        "event_id": "event.fixture.created",
        "event_type": "FIXTURE_CREATED",
        "recorded_at": _NOW,
    }
    history = PACEHistoryEvent.model_validate_json(
        canonical_pace_json_bytes_v1(
            {**history_payload, "event_sha256": pace_digest_v1(history_payload)}
        )
    )
    branch_provenance = []
    for branch_id, observation_ids, bindings in (
        ("branch.evidence_gap", (), ()),
        ("branch.merits", (), ()),
    ):
        binding_payload = {
            "branch_id": branch_id,
            "graph_sha256": graph.graph_sha256,
            "observation_ids": list(observation_ids),
            "source_locator_bindings": list(bindings),
        }
        branch_provenance.append(
            PACEBranchProvenanceBinding.model_validate_json(
                canonical_pace_json_bytes_v1(
                    {
                        **binding_payload,
                        "binding_sha256": pace_digest_v1(binding_payload),
                    }
                )
            )
        )
    state_payload = {
        "contract": "casepath.pace-state/1.0.0",
        "graph": graph.model_dump(mode="json"),
        "observations": [observation.model_dump(mode="json")],
        "sources": [source.model_dump(mode="json")],
        "documents": [
            PACEDocumentRecord(
                evidence_item_id="evidence.causation_support",
                state=PACEDocumentState.MISSING,
                source_ids=(source.source_id,),
                last_transition_at=_NOW,
            ).model_dump(mode="json")
        ],
        "history": [history.model_dump(mode="json")],
        "current_time": _NOW,
        "kernel_snapshot_sha256": None,
        "predecessor_event_sha256": history.event_sha256,
        "branch_provenance": [
            value.model_dump(mode="json") for value in branch_provenance
        ],
    }
    state = PACEState.model_validate_json(
        canonical_pace_json_bytes_v1(
            {**state_payload, "state_sha256": pace_digest_v1(state_payload)}
        )
    )
    capability = PACECapabilityExpression(
        operator=PACECapabilityOperator.AND,
        children=tuple(
            sorted(
                (_leaf("capability.fact_causation"), _leaf("capability.exact_locator")),
                key=lambda value: pace_digest_v1(value.model_dump(mode="json")),
            )
        ),
    )
    obligation = PACEObligationSpec(
        obligation_id="obligation.establish_causation",
        kind=PACEObligationKind.ESTABLISH,
        process_node_id="evidence_gap_causation",
        predicate_ids=("causation_supported",),
        target_atoms=(PACEAtom(predicate_id="causation_supported", value="true"),),
        activation=PACECondition(operator="ALWAYS"),
        evidence_capability=capability,
        criticality_weight=100,
    )
    obligation_expression = PACEObligationExpression(
        operator="OBLIGATION",
        obligation_id=obligation.obligation_id,
    )
    outcomes = (
        PACEOutcomeSpec(
            outcome_id="outcome.false",
            restrictions=(PACEAtom(predicate_id="causation_supported", value="false"),),
        ),
        PACEOutcomeSpec(
            outcome_id="outcome.true",
            restrictions=(PACEAtom(predicate_id="causation_supported", value="true"),),
        ),
    )

    def action(
        action_id: str,
        *,
        process_node_id: str = "evidence_gap_causation",
        burden: int,
    ) -> PACEActionSpec:
        return PACEActionSpec(
            action_id=action_id,
            action_kind="acquire",
            process_node_id=process_node_id,
            process_topological_index=2,
            evidence_item_id="evidence.causation_support",
            obligation_ids=(obligation.obligation_id,),
            capability_ids=(
                "capability.exact_locator",
                "capability.fact_causation",
            ),
            outcomes=outcomes,
            source_ids=(source.source_id,),
            locator_ids=("locator.causation_section",),
            source_locator_bindings=(
                PACESourceLocatorBinding(
                    source_id=source.source_id,
                    locator_id="locator.causation_section",
                ),
            ),
            allowed_document_states=(PACEDocumentState.MISSING,),
            burden_cost=burden,
            delay_cost=1,
            safety_privacy_cost=0,
        )

    actions = (
        action("action.acquire_causation", burden=1),
        action("action.acquire_causation_expensive", burden=3),
        action("action.orphan", process_node_id="inactive_future_node", burden=1),
    )
    config_payload = {
        "contract": "casepath.pace-compiler-config/1.0.0",
        "selection_policy": "static_non_dominated_v1",
        "maximum_predicates": 8,
        "maximum_worlds": 256,
    }
    config = PACECompilerConfig.model_validate_json(
        canonical_pace_json_bytes_v1(
            {**config_payload, "config_sha256": pace_digest_v1(config_payload)}
        )
    )
    request_payload = {
        "contract": "casepath.pace-compile-request/1.0.0",
        "state": state.model_dump(mode="json"),
        "obligations": [obligation.model_dump(mode="json")],
        "obligation_expression": obligation_expression.model_dump(mode="json"),
        "actions": [value.model_dump(mode="json") for value in actions],
        "config": config.model_dump(mode="json"),
    }
    return PACECompileRequest.model_validate_json(
        canonical_pace_json_bytes_v1(
            {**request_payload, "request_sha256": pace_digest_v1(request_payload)}
        )
    )
