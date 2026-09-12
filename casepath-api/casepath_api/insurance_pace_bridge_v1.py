from __future__ import annotations

from datetime import datetime
import hashlib
from pathlib import Path
from typing import Any, Protocol, Sequence

from .claim_loop import reduce_claim_loop_event
from .claim_loop_contracts import (
    ClaimLoopEventLike,
    ClaimLoopState,
    load_claim_loop_event_v1,
)
from .foundation.common import canonical_json_bytes, digest_value
from .insurance_protocol_v1 import (
    ActionIntentV1,
    AdapterDryRunReceiptV1,
    DecisionRecordV1,
    DecisionProposalV1,
    INSURANCE_AUTHORITY_POLICY_VERSION,
    InsuranceProtocolRecordSetV1,
    MANUAL_NEUTRAL_ASSESSMENT_CAPABILITY,
    SOURCE_REGISTER_CAPABILITY,
    StagedArtifactReceiptV1,
    capability_catalog_sha256_v1,
    capability_catalog_v1,
    hash_record_set_v1,
)
from .pace_canonical import canonical_pace_json_bytes_v1, pace_digest_v1
from .pace_contracts import (
    PACEActionSpec,
    PACEActionCertificate,
    PACEBranchProvenanceBinding,
    PACECompileRequest,
    PACEHistoryEvent,
    PACEProcessEvidenceGraph,
    PACEState,
)
from .pace_core.compiler import compile_pace_v1
from .pace_core.verifier import verify_certificate_v1
from .playbook_template import PlaybookTemplate, PlaybookTemplateError


class InsurancePACEBridgeError(ValueError):
    pass


class _LocalRegistryIdentity(Protocol):
    adapter_id: str
    implementation_id: str

    @property
    def implementation_source_sha256(self) -> str: ...

    @property
    def implementation_sha256(self) -> str: ...

    def dry_run(
        self,
        *,
        intent: ActionIntentV1,
        staged: StagedArtifactReceiptV1,
        evaluated_at: str,
    ) -> AdapterDryRunReceiptV1: ...


def _source_sha256(module_file: str) -> str:
    return hashlib.sha256(Path(module_file).read_bytes()).hexdigest()


def _pace_model(model_type: type, payload: dict[str, object], hash_field: str):
    value = {**payload, hash_field: pace_digest_v1(payload)}
    return model_type.model_validate_json(canonical_pace_json_bytes_v1(value))


def _require_mapping(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InsurancePACEBridgeError(f"{label} is not a closed mapping")
    return value


def _require_string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise InsurancePACEBridgeError(f"{label} is not a non-empty string")
    return value


def _pace_document_state(status: object) -> str:
    mapping = {
        "conditional": "requested",
        "missing": "missing",
        "not_applicable": "unavailable",
        "provided_insufficient": "received",
        "provided_sufficient": "validated",
        "stale": "stale",
        "unavailable": "unavailable",
    }
    try:
        return mapping[str(status)]
    except KeyError as exc:
        raise InsurancePACEBridgeError(
            f"unsupported checklist evidence status: {status!r}"
        ) from exc


def _validated_state_and_template(
    state: ClaimLoopState,
) -> tuple[ClaimLoopState, PlaybookTemplate]:
    try:
        validated = ClaimLoopState.model_validate_json(
            canonical_json_bytes(state.model_dump(mode="json"))
        )
        record = _require_mapping(
            validated.accepted_artifacts.get("playbook_template_record"),
            label="accepted playbook template record",
        )
        template = PlaybookTemplate.from_persisted_record(record)
        template.require_claim(validated.claim_id)
    except (PlaybookTemplateError, TypeError, ValueError) as exc:
        raise InsurancePACEBridgeError(
            "PACE input is not an accepted replayable claim state"
        ) from exc
    if (
        validated.six_agent_cycle_receipt.playbook_template_sha256
        != template.template_sha256
    ):
        raise InsurancePACEBridgeError(
            "accepted cycle and persisted playbook template identities differ"
        )
    return validated, template


def _validate_journal_prefix(
    *, state: ClaimLoopState, journal_events: Sequence[ClaimLoopEventLike]
) -> tuple[ClaimLoopEventLike, ...]:
    """Replay and authenticate the complete journal prefix used by PACE.

    Event self-hashes deliberately exclude the reducer result.  A tail-only
    comparison therefore cannot establish state authority.  This boundary
    revalidates every event, verifies the hash chain, reruns the canonical
    reducer, checks every declared result, and finally requires byte-identical
    equality with the supplied state.
    """

    if not journal_events:
        raise InsurancePACEBridgeError("PACE journal prefix is empty")
    replayed: ClaimLoopState | None = None
    previous_event_sha256: str | None = None
    validated_events: list[ClaimLoopEventLike] = []
    try:
        for expected_sequence, raw_event in enumerate(journal_events, start=1):
            event = load_claim_loop_event_v1(
                raw_event.model_dump(mode="json")
            )
            if (
                event.session_id != state.session_id
                or event.loop_id != state.loop_id
                or event.sequence != expected_sequence
                or event.previous_event_sha256 != previous_event_sha256
            ):
                raise InsurancePACEBridgeError(
                    "PACE journal prefix identity or hash chain diverged"
                )
            replayed = reduce_claim_loop_event(
                replayed,
                event_type=event.event_type,
                command=event.command,
                sequence=event.sequence,
                event_sha256=event.event_sha256,
                timestamp=event.created_at,
            )
            if replayed.state_sha256 != event.resulting_state_sha256:
                raise InsurancePACEBridgeError(
                    "PACE journal event result diverged from canonical replay"
                )
            validated_events.append(event)
            previous_event_sha256 = event.event_sha256
    except InsurancePACEBridgeError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise InsurancePACEBridgeError("PACE journal prefix is invalid") from exc
    if replayed is None or replayed != state:
        raise InsurancePACEBridgeError(
            "PACE journal prefix does not reproduce the accepted claim state"
        )
    return tuple(validated_events)


def _claim_derived_pace_payloads(
    *,
    state: ClaimLoopState,
    template: PlaybookTemplate,
    journal_events: Sequence[ClaimLoopEventLike],
) -> tuple[
    dict[str, object],
    list[dict[str, object]],
    dict[str, object],
    list[dict[str, object]],
    dict[str, object],
]:
    """Project only the current accepted decision slice into PACE M1.

    The projection is deliberately not a claim-wide scheduler.  It uses the
    accepted route-program row for the current process decision and proves the
    information value of the bounded assessment for that slice.  ClaimLoop
    remains authoritative for global ordering and may select an earlier
    mandatory obligation after the supplied material is registered.
    """

    process = _require_mapping(state.process, label="claim process")
    checklist = _require_mapping(state.checklist, label="claim checklist")
    overlay = _require_mapping(
        process.get("current_overlay"), label="current process overlay"
    )
    current_node_id = _require_string(
        overlay.get("current_node_id"), label="current process node"
    )
    next_node_id = _require_string(
        overlay.get("next_action_node_id"), label="next action node"
    )

    process_nodes = {
        _require_string(value.get("node_id"), label="process node ID"): value
        for value in process.get("nodes", [])
        if isinstance(value, dict)
    }
    current_node = process_nodes.get(current_node_id)
    if current_node is None:
        raise InsurancePACEBridgeError("current process node is absent from the graph")
    branch_by_target = {
        _require_string(value.get("target"), label="branch target"): value
        for value in current_node.get("branches", [])
        if isinstance(value, dict)
    }
    if len(branch_by_target) < 3:
        raise InsurancePACEBridgeError(
            "current decision slice lacks a nontrivial branch roster"
        )

    catalog = template.catalog
    route_program = _require_mapping(
        catalog.get("route_program"), label="accepted route program"
    )
    route_steps = tuple(
        value
        for value in route_program.get("steps", [])
        if isinstance(value, dict) and value.get("node_id") == current_node_id
    )
    if len(route_steps) != 1:
        raise InsurancePACEBridgeError(
            "current process node lacks one accepted route-program decision"
        )
    route_step = route_steps[0]
    decision_key = _require_string(
        route_step.get("decision_key"), label="current decision key"
    )
    decision_options = _require_mapping(
        _require_mapping(catalog.get("decision_options"), label="decision catalog").get(
            decision_key
        ),
        label="current decision options",
    )
    fail_closed_normalized = _require_string(
        _require_mapping(
            catalog.get("fail_closed_normalized_values"),
            label="fail-closed decision catalog",
        ).get(decision_key),
        label="fail-closed normalized value",
    )
    normalized_by_decision = {
        _require_string(decision_value, label="decision value"): _require_string(
            normalized, label="normalized decision value"
        )
        for normalized, decision_value in decision_options.items()
    }
    if fail_closed_normalized not in decision_options:
        raise InsurancePACEBridgeError(
            "fail-closed value is absent from the accepted decision catalog"
        )
    transitions = _require_mapping(
        route_step.get("transitions"), label="current route transitions"
    )
    option_by_target: dict[str, str] = {}
    branch_by_normalized: dict[str, dict[str, Any]] = {}
    for decision_value, raw_transition in transitions.items():
        transition = _require_mapping(raw_transition, label="route transition")
        normalized = normalized_by_decision.get(decision_value)
        target = _require_string(
            transition.get("target_node_id"), label="route target"
        )
        branch_id = _require_string(
            transition.get("selected_branch_id"), label="route branch"
        )
        branch = branch_by_target.get(target)
        if (
            normalized is None
            or target in option_by_target
            or branch is None
            or branch.get("branch_id") != branch_id
            or normalized in branch_by_normalized
        ):
            raise InsurancePACEBridgeError(
                "route transition is not exactly bound to a unique process branch"
            )
        option_by_target[target] = normalized
        branch_by_normalized[normalized] = branch
    if (
        set(branch_by_target) != set(option_by_target)
        or set(branch_by_normalized) != set(decision_options)
    ):
        raise InsurancePACEBridgeError(
            "process branches and accepted decision options are not bijective"
        )

    controlling_facts = tuple(
        value
        for value in state.facts
        if value.get("decision_key") == decision_key
        and value.get("controls_process") is True
    )
    if len(controlling_facts) != 1:
        raise InsurancePACEBridgeError(
            "current decision lacks one accepted controlling fact"
        )
    controlling_fact = controlling_facts[0]
    fact_id = _require_string(
        controlling_fact.get("fact_id"), label="controlling fact ID"
    )
    current_decision_value = decision_options[fail_closed_normalized]
    if (
        controlling_fact.get("state") != "unknown"
        or controlling_fact.get("normalized_value") != fail_closed_normalized
        or controlling_fact.get("decision_value") != current_decision_value
        or _require_mapping(overlay.get("decisions"), label="overlay decisions").get(
            decision_key
        )
        != current_decision_value
        or overlay.get("selected_branch_id")
        != branch_by_normalized[fail_closed_normalized].get("branch_id")
        or branch_by_normalized[fail_closed_normalized].get("target") != next_node_id
    ):
        raise InsurancePACEBridgeError(
            "current decision slice is not the accepted fail-closed unknown state"
        )

    obligations_by_id = {value.obligation_id: value for value in state.obligations}
    candidate_items = tuple(
        value
        for value in checklist.get("items", [])
        if isinstance(value, dict)
        and value.get("fact_id") == fact_id
        and value.get("current_path") is True
        and (obligation := obligations_by_id.get(value.get("item_id"))) is not None
        and obligation.mandatory_now
        and obligation.status.value in {"active", "contradicted", "blocked"}
        and value.get("status") != "provided_sufficient"
    )
    if len(candidate_items) != 1:
        raise InsurancePACEBridgeError(
            "current decision slice lacks one mandatory unresolved evidence item"
        )
    evidence_item = candidate_items[0]
    evidence_item_id = _require_string(
        evidence_item.get("item_id"), label="evidence item ID"
    )
    obligation = obligations_by_id[evidence_item_id]
    if next_node_id not in obligation.process_node_ids:
        raise InsurancePACEBridgeError(
            "decision-slice obligation does not bind the current evidence node"
        )

    capability_catalog = _require_mapping(
        catalog.get("evidence_artifact_capabilities"),
        label="evidence capability catalog",
    )
    raw_capabilities = capability_catalog.get(evidence_item_id)
    if not isinstance(raw_capabilities, (list, tuple)):
        raise InsurancePACEBridgeError(
            "current evidence item lacks an accepted capability roster"
        )
    capability_ids = tuple(
        sorted(_require_string(value, label="artifact capability") for value in raw_capabilities)
    )
    if not capability_ids or len(capability_ids) != len(set(capability_ids)):
        raise InsurancePACEBridgeError(
            "current evidence capability roster is empty or noncanonical"
        )

    selected_path = tuple(
        _require_string(value, label="selected process path node")
        for value in process.get("selected_path", [])
    )
    if (
        not selected_path
        or current_node_id not in selected_path
        or selected_path[-1] != next_node_id
    ):
        raise InsurancePACEBridgeError(
            "selected process prefix does not end at the current evidence node"
        )
    included_node_ids = tuple(
        dict.fromkeys((*selected_path, *sorted(branch_by_target))).keys()
    )
    if any(value not in process_nodes for value in included_node_ids):
        raise InsurancePACEBridgeError("PACE process projection cites an unknown node")
    edge_pairs = {
        (
            _require_string(value.get("source"), label="process edge source"),
            _require_string(value.get("target"), label="process edge target"),
        )
        for value in process.get("edges", [])
        if isinstance(value, dict) and value.get("state") != "loop"
    }
    selected_pairs = tuple(zip(selected_path, selected_path[1:], strict=False))
    if any(pair not in edge_pairs for pair in selected_pairs):
        raise InsurancePACEBridgeError(
            "selected process prefix is not supported by accepted edges"
        )
    ordered_node_ids = tuple(
        dict.fromkeys(
            (*selected_path, *(value for value in sorted(branch_by_target) if value not in selected_path))
        ).keys()
    )
    topological_index = {
        node_id: index for index, node_id in enumerate(ordered_node_ids)
    }
    node_kind = {
        "action": "evidence",
        "decision": "decision",
        "entry": "entry",
        "outcome": "terminal",
    }
    nodes = [
        {
            "node_id": node_id,
            "node_kind": node_kind[
                _require_string(process_nodes[node_id].get("kind"), label="node kind")
            ],
            "topological_index": topological_index[node_id],
        }
        for node_id in sorted(included_node_ids)
    ]

    non_fail_values = tuple(
        value for value in sorted(decision_options) if value != fail_closed_normalized
    )
    if len(non_fail_values) < 2:
        raise InsurancePACEBridgeError(
            "PACE DISAMBIGUATE requires at least two live alternatives"
        )
    predicate_by_value = {
        value: f"decision.{decision_key}.is.{value}" for value in non_fail_values
    }
    predicate_ids = tuple(sorted(predicate_by_value.values()))
    predicate_specs = [
        {
            "predicate_id": predicate_id,
            "domain": ["false", "true"],
            "semantic_type": "boolean",
        }
        for predicate_id in predicate_ids
    ]

    world_values = (fail_closed_normalized, *non_fail_values)

    def assignment_atoms(normalized: str) -> list[dict[str, str]]:
        return [
            {
                "predicate_id": predicate_by_value[value],
                "value": "true" if value == normalized else "false",
            }
            for value in non_fail_values
        ]

    constraints = [
        {
            "constraint_id": f"constraint.decision.{decision_key}.one-or-fail-closed",
            "condition": {
                "operator": "DNF",
                "clauses": sorted(
                    ({"atoms": assignment_atoms(value)} for value in world_values),
                    key=lambda value: tuple(
                        (atom["predicate_id"], atom["value"])
                        for atom in value["atoms"]
                    ),
                ),
            },
        }
    ]
    decision_id = f"decision.{decision_key}"
    branch_specs: list[dict[str, object]] = []
    branch_edges: list[dict[str, object]] = []
    for normalized in sorted(branch_by_normalized):
        branch = branch_by_normalized[normalized]
        target = _require_string(branch.get("target"), label="branch target")
        branch_id = _require_string(branch.get("branch_id"), label="branch ID")
        if (current_node_id, target) not in edge_pairs:
            raise InsurancePACEBridgeError("decision branch lacks its accepted edge")
        branch_specs.append(
            {
                "branch_id": branch_id,
                "process_node_id": current_node_id,
                "target_node_id": target,
                "decision_id": decision_id,
                "condition": {
                    "operator": "DNF",
                    "clauses": [{"atoms": assignment_atoms(normalized)}],
                },
                "material": True,
            }
        )
        branch_edges.append(
            {
                "edge_id": f"edge.{current_node_id}.{target}",
                "source_node_id": current_node_id,
                "target_node_id": target,
                "branch_id": branch_id,
            }
        )
    path_edges = [
        {
            "edge_id": f"edge.{source}.{target}",
            "source_node_id": source,
            "target_node_id": target,
            "branch_id": None,
        }
        for source, target in selected_pairs
        if source != current_node_id
    ]
    all_edges = sorted((*path_edges, *branch_edges), key=lambda value: value["edge_id"])

    template_source_id = template.template_id
    capability_locator_material = {
        "contract": "casepath.pace-capability-registry-locator/1.0.0",
        "template_sha256": template.template_sha256,
        "evidence_item_id": evidence_item_id,
        "capability_ids": list(capability_ids),
    }
    capability_locator_id = "locator.capability." + pace_digest_v1(
        capability_locator_material
    )
    capability_specs = [
        {
            "capability_id": capability_id,
            "evidence_item_id": evidence_item_id,
            "action_kinds": ["acquire"],
            "predicate_ids": list(predicate_ids),
            "source_ids": [template_source_id],
            "source_locator_bindings": [
                {
                    "source_id": template_source_id,
                    "locator_id": capability_locator_id,
                }
            ],
            "requires_exact_locator": True,
        }
        for capability_id in capability_ids
    ]

    static_item_policy = {
        key: evidence_item.get(key)
        for key in (
            "acceptable_alternatives",
            "applies_when",
            "fact_id",
            "item_id",
            "legal_basis_ids",
            "node_id",
            "node_ids",
            "required_level",
            "title",
            "why",
        )
    }
    process_blueprint = {
        "contract": "casepath.pace-current-decision-blueprint/1.0.0",
        "template_sha256": template.template_sha256,
        "decision_key": decision_key,
        "route_step": route_step,
        "nodes": nodes,
        "edges": all_edges,
        "branches": sorted(branch_specs, key=lambda value: value["branch_id"]),
    }
    rule_blueprint = {
        "contract": "casepath.pace-current-obligation-policy/1.0.0",
        "template_sha256": template.template_sha256,
        "item_policy": static_item_policy,
        "capability_ids": list(capability_ids),
        "uniform_cost_policy": {
            "burden_cost": 1,
            "delay_cost": 1,
            "safety_privacy_cost": 0,
        },
    }
    graph_payload: dict[str, object] = {
        "contract": "casepath.pace-process-evidence-graph/1.0.0",
        "case_id": state.claim_id,
        "process_version": "claim-loop-current-decision." + pace_digest_v1(process_blueprint),
        "rule_version": "claim-loop-current-obligation." + pace_digest_v1(rule_blueprint),
        "source_registry_version": "playbook-template." + template.template_sha256,
        "knowledge_version": "playbook-template." + template.template_sha256,
        "predicate_specs": predicate_specs,
        "constraints": constraints,
        "nodes": nodes,
        "edges": all_edges,
        "branches": sorted(branch_specs, key=lambda value: value["branch_id"]),
        "capability_specs": capability_specs,
        "critical_decision_ids": [decision_id],
    }

    capability_children = [
        {"operator": "CAPABILITY", "capability_id": value, "children": []}
        for value in capability_ids
    ]
    capability_children.sort(key=pace_digest_v1)
    evidence_capability = (
        capability_children[0]
        if len(capability_children) == 1
        else {
            "operator": "OR",
            "capability_id": None,
            "children": capability_children,
        }
    )
    obligation_payload = {
        "obligation_id": obligation.obligation_id,
        "kind": "DISAMBIGUATE",
        "process_node_id": current_node_id,
        "predicate_ids": list(predicate_ids),
        "target_atoms": [],
        "source_ids": [],
        "activation": {"operator": "ALWAYS", "clauses": []},
        "evidence_capability": evidence_capability,
        "criticality_weight": 100,
        "verification_time": None,
        "deadline": None,
        "satisfaction_event_types": [],
    }
    obligation_expression = {
        "operator": "OBLIGATION",
        "obligation_id": obligation.obligation_id,
        "children": [],
        "condition": None,
        "temporal_at": None,
    }
    outcomes = sorted(
        (
            {
                "outcome_id": f"outcome.{decision_key}.{normalized}",
                "restrictions": assignment_atoms(normalized),
            }
            for normalized in world_values
        ),
        key=lambda value: value["outcome_id"],
    )
    action_payload = {
        "action_id": MANUAL_NEUTRAL_ASSESSMENT_CAPABILITY,
        "action_kind": "acquire",
        "process_node_id": current_node_id,
        "process_topological_index": topological_index[current_node_id],
        "evidence_item_id": evidence_item_id,
        "obligation_ids": [obligation.obligation_id],
        "capability_ids": list(capability_ids),
        "outcomes": outcomes,
        "source_ids": [template_source_id],
        "locator_ids": [capability_locator_id],
        "source_locator_bindings": [
            {
                "source_id": template_source_id,
                "locator_id": capability_locator_id,
            }
        ],
        "allowed_document_states": [_pace_document_state(evidence_item.get("status"))],
        "not_before": None,
        "not_after": None,
        "burden_cost": 1,
        "delay_cost": 1,
        "safety_privacy_cost": 0,
    }
    source_payload = {
        "source_id": template_source_id,
        "source_version": template.template_version,
        "source_sha256": template.template_sha256,
        "locator_ids": [capability_locator_id],
        "authority_valid": True,
        "valid_from": None,
        "valid_until": None,
    }
    relevant_observations = tuple(
        value
        for value in state.observations
        if value.fact_id == fact_id or value.evidence_item_id == evidence_item_id
    )
    relevant_record_sha256s = {
        value.observation_sha256 for value in relevant_observations
    }
    relevant_projection_ledger = tuple(
        value
        for value in state.projection_ledger
        if value.record_sha256 in relevant_record_sha256s
    )
    timestamp_candidates = [journal_events[0].created_at]
    timestamp_candidates.extend(
        value.observed_at for value in relevant_observations
    )
    timestamp_candidates.extend(
        value.recorded_at for value in relevant_projection_ledger
    )
    semantic_recorded_at = max(
        timestamp_candidates,
        key=lambda value: datetime.fromisoformat(value.replace("Z", "+00:00")),
    )
    document_payload = {
        "evidence_item_id": evidence_item_id,
        "state": _pace_document_state(evidence_item.get("status")),
        # A missing evidence requirement is not an acquired evidence source.
        "source_ids": [],
        "last_transition_at": semantic_recorded_at,
    }
    observable_snapshot = {
        "contract": "casepath.pace-observable-snapshot/1.0.0",
        "session_id": state.session_id,
        "loop_id": state.loop_id,
        "claim_id": state.claim_id,
        "record_version": state.record_version,
        "template_sha256": template.template_sha256,
        "graph_sha256": pace_digest_v1(graph_payload),
        "controlling_fact": {
            key: controlling_fact.get(key)
            for key in (
                "controls_process",
                "decision_key",
                "decision_value",
                "explanation",
                "fact_id",
                "normalized_value",
                "source_refs",
                "state",
                "value",
            )
        },
        "controlling_fact_confidence_milli": int(
            round(float(controlling_fact.get("confidence", 0.0)) * 1000)
        ),
        "evidence_item": evidence_item,
        "obligation": obligation.model_dump(mode="json"),
        "relevant_observations": [
            value.model_dump(mode="json") for value in relevant_observations
        ],
        "relevant_projection_ledger": [
            value.model_dump(mode="json") for value in relevant_projection_ledger
        ],
        "semantic_recorded_at": semantic_recorded_at,
    }
    scope = {
        "contract": "casepath.pace-current-decision-scope/1.0.0",
        "decision_key": decision_key,
        "fact_id": fact_id,
        "evidence_item_id": evidence_item_id,
        "global_scheduler_authority": "CLAIM_LOOP_ONLY",
        "certificate_scope": "CURRENT_DECISION_SLICE_NOT_GLOBAL_NEXT_ACTION",
        "earlier_mandatory_obligation_ids": [
            item.get("item_id")
            for item in checklist.get("items", [])
            if isinstance(item, dict)
            and item.get("item_id") != evidence_item_id
            and (candidate := obligations_by_id.get(item.get("item_id"))) is not None
            and candidate.mandatory_now
            and item.get("status") != "provided_sufficient"
        ],
    }
    return graph_payload, [obligation_payload], obligation_expression, [
        action_payload,
        source_payload,
        document_payload,
    ], {
        "observable_snapshot": observable_snapshot,
        "scope": scope,
        "semantic_recorded_at": semantic_recorded_at,
    }


def _assemble_neutral_assessment_request_v1(
    *,
    state: ClaimLoopState,
    template: PlaybookTemplate,
    journal_events: Sequence[ClaimLoopEventLike],
) -> PACECompileRequest:
    graph_payload, obligations, obligation_expression, components, metadata = (
        _claim_derived_pace_payloads(
            state=state,
            template=template,
            journal_events=journal_events,
        )
    )
    action_payload, source_payload, document_payload = components
    graph = _pace_model(PACEProcessEvidenceGraph, graph_payload, "graph_sha256")

    observable_snapshot_sha256 = pace_digest_v1(metadata["observable_snapshot"])
    history_payload = {
        "event_id": "event.pace-observable-snapshot." + observable_snapshot_sha256,
        "event_type": "PACE_OBSERVABLE_SNAPSHOT_BOUND",
        "recorded_at": metadata["semantic_recorded_at"],
    }
    history = _pace_model(PACEHistoryEvent, history_payload, "event_sha256")

    branch_provenance = []
    for branch in graph.branches:
        binding_payload = {
            "branch_id": branch.branch_id,
            "graph_sha256": graph.graph_sha256,
            "observation_ids": [],
            "source_locator_bindings": [],
        }
        branch_provenance.append(
            _pace_model(
                PACEBranchProvenanceBinding,
                binding_payload,
                "binding_sha256",
            ).model_dump(mode="json")
        )

    state_payload = {
        "contract": "casepath.pace-state/1.0.0",
        "graph": graph.model_dump(mode="json"),
        "observations": [],
        "sources": [source_payload],
        "documents": [document_payload],
        "history": [history.model_dump(mode="json")],
        "current_time": metadata["semantic_recorded_at"],
        "kernel_snapshot_sha256": observable_snapshot_sha256,
        "predecessor_event_sha256": history.event_sha256,
        "branch_provenance": sorted(
            branch_provenance, key=lambda value: value["branch_id"]
        ),
    }
    pace_state = _pace_model(PACEState, state_payload, "state_sha256")
    action = PACEActionSpec.model_validate_json(
        canonical_pace_json_bytes_v1(action_payload)
    )

    config_payload = {
        "contract": "casepath.pace-compiler-config/1.0.0",
        "selection_policy": "static_non_dominated_v1",
        "maximum_predicates": 8,
        "maximum_worlds": 256,
    }
    config = {
        **config_payload,
        "config_sha256": pace_digest_v1(config_payload),
    }

    request_payload = {
        "contract": "casepath.pace-compile-request/1.0.0",
        "state": pace_state.model_dump(mode="json"),
        "obligations": obligations,
        "obligation_expression": obligation_expression,
        "actions": [action.model_dump(mode="json")],
        "config": config,
    }
    return _pace_model(PACECompileRequest, request_payload, "request_sha256")


def build_neutral_assessment_request_v1(
    *, state: ClaimLoopState, journal_events: Sequence[ClaimLoopEventLike]
) -> PACECompileRequest:
    """Compile the actual accepted claim state into the frozen M1 compiler."""

    state, template = _validated_state_and_template(state)
    validated_events = _validate_journal_prefix(
        state=state, journal_events=journal_events
    )
    request = _assemble_neutral_assessment_request_v1(
        state=state,
        template=template,
        journal_events=validated_events,
    )
    validate_claim_derived_pace_request_v1(
        state=state,
        journal_events=validated_events,
        request=request,
    )
    return request


def pace_current_decision_scope_v1(
    *, state: ClaimLoopState, journal_events: Sequence[ClaimLoopEventLike]
) -> dict[str, object]:
    """Return the exact non-global scope asserted by the proposal."""

    state, template = _validated_state_and_template(state)
    validated_events = _validate_journal_prefix(
        state=state, journal_events=journal_events
    )
    *_, metadata = _claim_derived_pace_payloads(
        state=state,
        template=template,
        journal_events=validated_events,
    )
    scope = metadata["scope"]
    assert isinstance(scope, dict)
    return {**scope, "scope_sha256": digest_value(scope)}


def validate_claim_derived_pace_request_v1(
    *,
    state: ClaimLoopState,
    journal_events: Sequence[ClaimLoopEventLike],
    request: PACECompileRequest,
    certificate: PACEActionCertificate | None = None,
) -> None:
    """Reject any request or certificate not reconstructed from journal state."""

    state, template = _validated_state_and_template(state)
    validated_events = _validate_journal_prefix(
        state=state, journal_events=journal_events
    )
    expected_request = _assemble_neutral_assessment_request_v1(
        state=state,
        template=template,
        journal_events=validated_events,
    )
    if request != expected_request:
        raise InsurancePACEBridgeError(
            "PACE request is not the exact claim-derived decision slice"
        )
    if request.state.graph.knowledge_version.endswith(state.state_sha256):
        raise InsurancePACEBridgeError(
            "static graph knowledge cannot bind full mutable claim state"
        )
    if certificate is not None:
        from .pace_core import compiler as compiler_module
        from .pace_core import verifier as verifier_module

        action = request.actions[0]
        if (
            certificate.compile_request_sha256 != request.request_sha256
            or certificate.graph_sha256 != request.state.graph.graph_sha256
            or certificate.state_sha256 != request.state.state_sha256
            or certificate.action_id != action.action_id
            or certificate.action_spec_sha256
            != pace_digest_v1(action.model_dump(mode="json"))
            or certificate.process_node_id != action.process_node_id
            or certificate.evidence_item_id != action.evidence_item_id
            or certificate.obligation_ids
            != tuple(value.obligation_id for value in request.obligations)
            or certificate.source_ids != action.source_ids
            or certificate.locator_ids != action.locator_ids
            or certificate.derived_capability_ids != action.capability_ids
        ):
            raise InsurancePACEBridgeError(
                "PACE certificate is not the exact claim-derived request result"
            )
        try:
            receipt = verify_certificate_v1(
                request,
                certificate,
                expected_compiler_source_sha256=_source_sha256(
                    compiler_module.__file__
                ),
                verifier_source_sha256=_source_sha256(verifier_module.__file__),
            )
        except (TypeError, ValueError) as exc:
            raise InsurancePACEBridgeError(
                "PACE certificate failed the independent verifier"
            ) from exc
        if not receipt.valid:
            raise InsurancePACEBridgeError(
                "PACE certificate failed the independent verifier"
            )


def build_verified_neutral_assessment_proposal_v1(
    *, state: ClaimLoopState, journal_events: Sequence[ClaimLoopEventLike]
) -> DecisionProposalV1:
    validated_events = _validate_journal_prefix(
        state=state, journal_events=journal_events
    )
    tail_event = validated_events[-1]
    request = build_neutral_assessment_request_v1(
        state=state,
        journal_events=validated_events,
    )
    from .pace_core import compiler as compiler_module
    from .pace_core import verifier as verifier_module

    compiler_sha256 = _source_sha256(compiler_module.__file__)
    verifier_sha256 = _source_sha256(verifier_module.__file__)
    result = compile_pace_v1(
        request,
        compiler_source_sha256=compiler_sha256,
        verifier_source_sha256=verifier_sha256,
    )
    if result.certificate is None:
        raise InsurancePACEBridgeError(
            f"PACE did not produce an action: {result.terminal_state}"
        )
    verification = verify_certificate_v1(
        request,
        result.certificate,
        expected_compiler_source_sha256=compiler_sha256,
        verifier_source_sha256=verifier_sha256,
    )
    validate_claim_derived_pace_request_v1(
        state=state,
        journal_events=validated_events,
        request=request,
        certificate=result.certificate,
    )
    payload = {
        "contract": "casepath.decision-proposal/1.0.0",
        "session_id": state.session_id,
        "loop_id": state.loop_id,
        "claim_id": state.claim_id,
        "record_version": state.record_version,
        "source_revision": state.revision,
        "source_state_sha256": state.state_sha256,
        "capability_id": MANUAL_NEUTRAL_ASSESSMENT_CAPABILITY,
        "execution_mode": "manual_external",
        "proposer": "PACE_CORE_COMPILER_V1",
        "pace_request": request.model_dump(mode="json"),
        "pace_result": result.model_dump(mode="json"),
        "pace_verification": verification.model_dump(mode="json"),
        "proposed_at": tail_event.created_at,
        "authoritative": False,
        "robust_voi": "NOT_COMPUTED_BY_METHOD_VERSION",
        "model_calls": 0,
        "provider_calls": 0,
        "credential_reads": 0,
        "cost_usd": 0.0,
    }
    return DecisionProposalV1.model_validate_json(
        canonical_json_bytes({**payload, "proposal_sha256": digest_value(payload)})
    )


def build_registration_compatibility_action_v1(
    *,
    state: ClaimLoopState,
    adapter: _LocalRegistryIdentity,
):
    """Derive the sole registration action from accepted server state."""

    from .claim_loop_contracts import EvidenceAction

    technical_item = next(
        (
            value
            for value in state.checklist.get("items", [])
            if value.get("item_id") == "technical_assessment"
        ),
        None,
    )
    technical_obligation = next(
        (
            value
            for value in state.obligations
            if value.obligation_id == "technical_assessment"
        ),
        None,
    )
    if technical_item is None or technical_obligation is None:
        raise InsurancePACEBridgeError(
            "current playbook has no neutral-assessment obligation"
        )
    next_node_id = state.process["current_overlay"]["next_action_node_id"]
    if (
        technical_obligation.status.value == "satisfied"
        or not technical_obligation.mandatory_now
        or technical_item.get("current_path") is not True
        or next_node_id not in technical_obligation.process_node_ids
    ):
        raise InsurancePACEBridgeError(
            "neutral assessment is not a current mandatory obligation"
        )
    action_payload = {
        "contract": "casepath.evidence-action/1.0.0",
        # The handler has already supplied the assessment.  This compatibility
        # action authorizes only local source registration; it never claims
        # that the registry acquired or commissioned evidence.
        "action_kind": "register",
        "process_node_id": next_node_id,
        "evidence_item_id": "technical_assessment",
        "fact_id": technical_obligation.fact_id,
        "title": technical_item["title"],
        "bounded_tool_id": adapter.adapter_id,
    }
    action_sha256 = digest_value(action_payload)
    return EvidenceAction.model_validate(
        {
            **action_payload,
            "action_id": f"action.{action_sha256}",
            "action_sha256": action_sha256,
        }
    )


def build_registration_authority_v1(
    *,
    state: ClaimLoopState,
    proposal: DecisionProposalV1,
    staged: StagedArtifactReceiptV1,
    adapter: _LocalRegistryIdentity,
    decided_at: str,
    effective_until: str,
    source_journal_events: Sequence[ClaimLoopEventLike],
) -> InsuranceProtocolRecordSetV1:
    expected_proposal = build_verified_neutral_assessment_proposal_v1(
        state=state,
        journal_events=source_journal_events,
    )
    if proposal != expected_proposal:
        raise InsurancePACEBridgeError(
            "PACE proposal differs from the current replay-derived state"
        )
    if (
        staged.session_id != state.session_id
        or staged.loop_id != state.loop_id
        or staged.claim_id != state.claim_id
        or staged.record_version != state.record_version
        or staged.adapter_id != adapter.adapter_id
    ):
        raise InsurancePACEBridgeError(
            "staged material does not bind the current case record"
        )
    compatibility_action = build_registration_compatibility_action_v1(
        state=state,
        adapter=adapter,
    )
    dry_run_payload = {
        "contract": "casepath.artifact-registry-dry-run/1.0.0",
        "source_state_sha256": state.state_sha256,
        "proposal_sha256": proposal.proposal_sha256,
        "staged_artifact_receipt_sha256": staged.receipt_sha256,
        "content_sha256": staged.content_sha256,
        "capability_id": SOURCE_REGISTER_CAPABILITY,
        "adapter_id": adapter.adapter_id,
        "adapter_implementation_id": adapter.implementation_id,
        "adapter_implementation_source_sha256": (adapter.implementation_source_sha256),
        "adapter_implementation_sha256": adapter.implementation_sha256,
        "evaluated_at": decided_at,
        "would_commit": True,
    }
    dry_run = AdapterDryRunReceiptV1.model_validate(
        {**dry_run_payload, "receipt_sha256": digest_value(dry_run_payload)}
    )
    catalog = {value.capability_id: value for value in capability_catalog_v1()}
    certificate = proposal.pace_result.certificate
    if certificate is None:  # pragma: no cover - proposal validator requires it
        raise InsurancePACEBridgeError("proposal has no certificate")
    decision_payload = {
        "contract": "casepath.decision-record/1.0.0",
        "session_id": state.session_id,
        "loop_id": state.loop_id,
        "claim_id": state.claim_id,
        "record_version": state.record_version,
        "source_revision": state.revision,
        "source_state_sha256": state.state_sha256,
        "proposal_sha256": proposal.proposal_sha256,
        "certificate_sha256": certificate.certificate_sha256,
        "authority": "deterministic_claim_loop_authority_v1",
        "authority_policy_version": INSURANCE_AUTHORITY_POLICY_VERSION,
        "disposition": "AUTHORIZE_LOCAL_REGISTRATION_OF_SUPPLIED_MATERIAL",
        "proposed_capability_id": MANUAL_NEUTRAL_ASSESSMENT_CAPABILITY,
        "authorized_capability_id": SOURCE_REGISTER_CAPABILITY,
        "proposed_descriptor_sha256": catalog[
            MANUAL_NEUTRAL_ASSESSMENT_CAPABILITY
        ].descriptor_sha256,
        "authorized_descriptor_sha256": catalog[
            SOURCE_REGISTER_CAPABILITY
        ].descriptor_sha256,
        "capability_catalog_sha256": capability_catalog_sha256_v1(),
        "adapter_id": adapter.adapter_id,
        "adapter_implementation_id": adapter.implementation_id,
        "adapter_implementation_source_sha256": (adapter.implementation_source_sha256),
        "adapter_implementation_sha256": adapter.implementation_sha256,
        "compatibility_action": compatibility_action.model_dump(mode="json"),
        "dry_run_receipt": dry_run.model_dump(mode="json"),
        "dry_run_receipt_sha256": dry_run.receipt_sha256,
        "staged_artifact_receipt_sha256": staged.receipt_sha256,
        "decided_at": decided_at,
        "effective_until": effective_until,
    }
    decision = DecisionRecordV1.model_validate_json(
        canonical_json_bytes(
            {
                **decision_payload,
                "decision_sha256": digest_value(decision_payload),
            }
        )
    )
    effect_key = digest_value(
        {
            "contract": "casepath.local-registration-effect/1.0.0",
            "session_id": state.session_id,
            "loop_id": state.loop_id,
            "claim_id": state.claim_id,
            "record_version": state.record_version,
            "capability_id": SOURCE_REGISTER_CAPABILITY,
            "content_sha256": staged.content_sha256,
        }
    )
    intent_payload = {
        "contract": "casepath.action-intent/1.0.0",
        "session_id": state.session_id,
        "loop_id": state.loop_id,
        "claim_id": state.claim_id,
        "record_version": state.record_version,
        "source_revision": state.revision,
        "source_state_sha256": state.state_sha256,
        "proposal_sha256": proposal.proposal_sha256,
        "decision_sha256": decision.decision_sha256,
        "capability_id": SOURCE_REGISTER_CAPABILITY,
        "adapter_id": adapter.adapter_id,
        "policy_version": INSURANCE_AUTHORITY_POLICY_VERSION,
        "capability_catalog_sha256": capability_catalog_sha256_v1(),
        "authorized_descriptor_sha256": catalog[
            SOURCE_REGISTER_CAPABILITY
        ].descriptor_sha256,
        "adapter_implementation_id": adapter.implementation_id,
        "adapter_implementation_source_sha256": (adapter.implementation_source_sha256),
        "adapter_implementation_sha256": adapter.implementation_sha256,
        "compatibility_action_sha256": compatibility_action.action_sha256,
        "dry_run_receipt_sha256": dry_run.receipt_sha256,
        "staged_artifact_receipt_sha256": staged.receipt_sha256,
        "content_sha256": staged.content_sha256,
        "effect_idempotency_key": effect_key,
        "created_at": decided_at,
        "expires_at": effective_until,
        "dry_run_passed": True,
    }
    intent = ActionIntentV1.model_validate_json(
        canonical_json_bytes(
            {
                **intent_payload,
                "intent_sha256": digest_value(intent_payload),
            }
        )
    )
    if (
        adapter.dry_run(intent=intent, staged=staged, evaluated_at=decided_at)
        != dry_run
    ):
        raise InsurancePACEBridgeError("adapter dry-run receipt diverged")
    return hash_record_set_v1(
        {
            "contract": "casepath.insurance-protocol-record-set/1.0.0",
            "proposal": proposal.model_dump(mode="json"),
            "staged_artifact": staged.model_dump(mode="json"),
            "decision": decision.model_dump(mode="json"),
            "intent": intent.model_dump(mode="json"),
            "action_receipt": None,
            "source_observation": None,
            "normalized_assertion": None,
            "interpretation": None,
        }
    )


__all__ = [
    "InsurancePACEBridgeError",
    "build_neutral_assessment_request_v1",
    "build_registration_authority_v1",
    "build_registration_compatibility_action_v1",
    "build_verified_neutral_assessment_proposal_v1",
]
