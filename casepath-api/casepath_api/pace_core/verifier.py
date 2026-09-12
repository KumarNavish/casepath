from __future__ import annotations

from datetime import datetime
from itertools import product
from typing import Any

from ..foundation.common import is_sha256
from ..pace_canonical import canonical_pace_json_bytes_v1, pace_digest_v1
from ..pace_contracts import (
    PACEActionCertificate,
    PACEActionSpec,
    PACECapabilityExpression,
    PACECapabilityOperator,
    PACECompileRequest,
    PACECompileResult,
    PACECondition,
    PACEObligationKind,
    PACEObligationExpression,
    PACEObligationSpec,
    PACEStaticPriority,
    PACETruthPolarity,
    PACEVerificationReceipt,
)


class PACEVerificationError(ValueError):
    pass


_OBLIGATION_OPERATOR_RANK = {
    PACEObligationKind.VERIFY_AUTHORITY: 0,
    PACEObligationKind.VERIFY_TEMPORAL_VALIDITY: 1,
    PACEObligationKind.SATISFY_DEADLINE: 2,
    PACEObligationKind.RESOLVE_CONFLICT: 3,
    PACEObligationKind.DISAMBIGUATE: 4,
    PACEObligationKind.ESTABLISH: 5,
    PACEObligationKind.REFUTE: 6,
}
_ACTION_KIND_RANK = {"validate": 0, "clarify": 1, "acquire": 2, "replan": 3}


def _condition_true(condition: PACECondition, assignment: dict[str, str]) -> bool:
    if condition.operator == "ALWAYS":
        return True
    for clause in condition.clauses:
        if all(
            assignment.get(atom.predicate_id) == atom.value for atom in clause.atoms
        ):
            return True
    return False


def _independent_worlds(request: PACECompileRequest) -> tuple[dict[str, Any], ...]:
    specs = request.state.graph.predicate_specs
    if len(specs) > request.config.maximum_predicates:
        raise PACEVerificationError("predicate cap exceeded")
    narrowed = {value.predicate_id: set(value.domain) for value in specs}
    for observation in request.state.observations:
        source = next(
            value
            for value in request.state.sources
            if value.source_id == observation.source_id
        )
        if (
            observation.reliability_milli != 1000
            or not source.authority_valid
            or not _source_temporally_valid(request, observation.source_id)
        ):
            continue
        if observation.polarity in {
            PACETruthPolarity.SUPPORTS,
            PACETruthPolarity.LIMITS,
        }:
            narrowed[observation.predicate_id] &= set(observation.allowed_values)
        elif observation.polarity is PACETruthPolarity.REFUTES:
            narrowed[observation.predicate_id] -= set(observation.allowed_values)
    domains = tuple(tuple(sorted(narrowed[value.predicate_id])) for value in specs)
    count = 1
    for domain in domains:
        count *= len(domain)
    if count > request.config.maximum_worlds:
        raise PACEVerificationError("world cap exceeded")
    worlds: list[dict[str, Any]] = []
    for values in product(*domains):
        assignment = {
            spec.predicate_id: value for spec, value in zip(specs, values, strict=True)
        }
        if not all(
            _condition_true(constraint.condition, assignment)
            for constraint in request.state.graph.constraints
        ):
            continue
        graph = request.state.graph
        branch_by_id = {value.branch_id: value for value in graph.branches}
        node_indexes = {
            value.node_id: value.topological_index for value in graph.nodes
        }
        reachable = {
            value.node_id for value in graph.nodes if value.node_kind == "entry"
        }
        active: set[str] = set()
        for edge in sorted(
            graph.edges,
            key=lambda value: (
                node_indexes[value.target_node_id],
                value.edge_id,
            ),
        ):
            if edge.source_node_id not in reachable:
                continue
            if edge.branch_id is not None:
                branch = branch_by_id[edge.branch_id]
                if not _condition_true(branch.condition, assignment):
                    continue
                active.add(branch.branch_id)
            reachable.add(edge.target_node_id)
        branches = tuple(sorted(active))
        material_branches = tuple(
            branch.branch_id
            for branch in request.state.graph.branches
            if branch.branch_id in branches and branch.material
        )
        decisions = tuple(
            sorted(
                {
                    branch.decision_id
                    for branch in request.state.graph.branches
                    if branch.branch_id in branches
                }
            )
        )
        material = {
            "assignments": [
                {"predicate_id": key, "value": assignment[key]}
                for key in sorted(assignment)
            ],
            "reachable_node_ids": sorted(reachable),
            "active_branch_ids": list(branches),
            "material_branch_ids": list(material_branches),
            "justified_decision_ids": list(decisions),
        }
        worlds.append({**material, "world_sha256": pace_digest_v1(material)})
    return tuple(sorted(worlds, key=lambda value: value["world_sha256"]))


def _source_temporally_valid(
    request: PACECompileRequest,
    source_id: str,
    *,
    at: str | None = None,
) -> bool:
    now = datetime.fromisoformat(
        (at or request.state.current_time).replace("Z", "+00:00")
    )
    source = next(
        value for value in request.state.sources if value.source_id == source_id
    )
    if source.valid_from is not None:
        if now < datetime.fromisoformat(source.valid_from.replace("Z", "+00:00")):
            return False
    if source.valid_until is not None:
        if now > datetime.fromisoformat(source.valid_until.replace("Z", "+00:00")):
            return False
    return True


def _relevant_worlds(
    obligation: PACEObligationSpec,
    worlds: tuple[dict[str, Any], ...],
) -> tuple[dict[str, Any], ...]:
    return tuple(
        world
        for world in worlds
        if _condition_true(
            obligation.activation,
            {value["predicate_id"]: value["value"] for value in world["assignments"]},
        )
    )


def _obligation_resolved(
    request: PACECompileRequest,
    obligation: PACEObligationSpec,
    worlds: tuple[dict[str, Any], ...],
) -> bool:
    relevant = _relevant_worlds(obligation, worlds)
    if not relevant:
        return True
    assignments = tuple(
        {value["predicate_id"]: value["value"] for value in world["assignments"]}
        for world in relevant
    )
    if obligation.kind is PACEObligationKind.ESTABLISH:
        target = obligation.target_atoms[0]
        return all(value[target.predicate_id] == target.value for value in assignments)
    if obligation.kind is PACEObligationKind.REFUTE:
        target = obligation.target_atoms[0]
        return all(value[target.predicate_id] != target.value for value in assignments)
    if obligation.kind in {
        PACEObligationKind.DISAMBIGUATE,
        PACEObligationKind.RESOLVE_CONFLICT,
    }:
        worlds_resolved = all(
            len({value[predicate_id] for value in assignments}) == 1
            for predicate_id in obligation.predicate_ids
        )
        if obligation.kind is PACEObligationKind.RESOLVE_CONFLICT:
            unresolved_conflict = any(
                value.polarity is PACETruthPolarity.CONFLICTS
                and value.predicate_id in obligation.predicate_ids
                and value.reliability_milli > 0
                for value in request.state.observations
            )
            return worlds_resolved and not unresolved_conflict
        return worlds_resolved
    if obligation.kind is PACEObligationKind.VERIFY_AUTHORITY:
        sources = {value.source_id: value for value in request.state.sources}
        return all(sources[value].authority_valid for value in obligation.source_ids)
    if obligation.kind is PACEObligationKind.VERIFY_TEMPORAL_VALIDITY:
        assert obligation.verification_time is not None
        return all(
            _source_temporally_valid(
                request,
                value,
                at=obligation.verification_time,
            )
            for value in obligation.source_ids
        )
    if obligation.kind is PACEObligationKind.SATISFY_DEADLINE:
        assert obligation.deadline is not None
        deadline = datetime.fromisoformat(obligation.deadline.replace("Z", "+00:00"))
        return any(
            value.event_type in obligation.satisfaction_event_types
            and datetime.fromisoformat(value.recorded_at.replace("Z", "+00:00"))
            <= deadline
            for value in request.state.history
        )
    raise PACEVerificationError("unknown obligation operator")


def _open_obligation_worlds(
    request: PACECompileRequest,
    worlds: tuple[dict[str, Any], ...],
) -> dict[str, tuple[dict[str, Any], ...]]:
    obligations_by_id = {value.obligation_id: value for value in request.obligations}
    worlds_by_hash = {value["world_sha256"]: value for value in worlds}

    def merge_scopes(
        values: tuple[dict[str, frozenset[str]], ...],
    ) -> dict[str, frozenset[str]]:
        merged: dict[str, frozenset[str]] = {}
        for value in values:
            for obligation_id, world_hashes in value.items():
                merged[obligation_id] = merged.get(
                    obligation_id, frozenset()
                ).union(world_hashes)
        return merged

    def open_scopes(
        expression: PACEObligationExpression,
        scoped_worlds: tuple[dict[str, Any], ...],
    ) -> dict[str, frozenset[str]]:
        if expression.operator == "OBLIGATION":
            assert expression.obligation_id is not None
            obligation = obligations_by_id[expression.obligation_id]
            active_worlds = _relevant_worlds(obligation, scoped_worlds)
            return (
                {
                    expression.obligation_id: frozenset(
                        value["world_sha256"] for value in active_worlds
                    )
                }
                if not _obligation_resolved(request, obligation, active_worlds)
                else {}
            )
        if expression.operator == "CONDITIONAL":
            assert expression.condition is not None
            conditional_worlds = tuple(
                world
                for world in scoped_worlds
                if _condition_true(
                    expression.condition,
                    {
                        value["predicate_id"]: value["value"]
                        for value in world["assignments"]
                    },
                )
            )
            return open_scopes(expression.children[0], conditional_worlds)
        if expression.operator == "TEMPORAL":
            assert expression.temporal_at is not None
            now = datetime.fromisoformat(
                request.state.current_time.replace("Z", "+00:00")
            )
            activation = datetime.fromisoformat(
                expression.temporal_at.replace("Z", "+00:00")
            )
            return (
                open_scopes(expression.children[0], scoped_worlds)
                if now >= activation
                else {}
            )
        values = tuple(
            open_scopes(child, scoped_worlds) for child in expression.children
        )
        if expression.operator == "ANY_OF" and any(not value for value in values):
            return {}
        return merge_scopes(values)

    scope_hashes = open_scopes(request.obligation_expression, worlds)
    return {
        obligation_id: tuple(
            worlds_by_hash[world_sha256]
            for world_sha256 in sorted(world_hashes)
        )
        for obligation_id, world_hashes in sorted(scope_hashes.items())
    }


def _open_obligations(
    request: PACECompileRequest,
    worlds: tuple[dict[str, Any], ...],
) -> tuple[PACEObligationSpec, ...]:
    unresolved_ids = _open_obligation_worlds(request, worlds)
    return tuple(
        value for value in request.obligations if value.obligation_id in unresolved_ids
    )


def _capability_satisfied(
    expression: PACECapabilityExpression,
    capability_ids: frozenset[str],
) -> bool:
    if expression.operator is PACECapabilityOperator.CAPABILITY:
        assert expression.capability_id is not None
        return expression.capability_id in capability_ids
    values = tuple(
        _capability_satisfied(child, capability_ids) for child in expression.children
    )
    if expression.operator is PACECapabilityOperator.AND:
        return all(values)
    return any(values)


def _derived_capabilities(
    request: PACECompileRequest,
    action: PACEActionSpec,
) -> tuple[str, ...]:
    outcome_predicates = {
        atom.predicate_id
        for outcome in action.outcomes
        for atom in outcome.restrictions
    }
    action_pairs = {
        (value.source_id, value.locator_id)
        for value in action.source_locator_bindings
    }
    return tuple(
        spec.capability_id
        for spec in request.state.graph.capability_specs
        if spec.evidence_item_id == action.evidence_item_id
        and action.action_kind in spec.action_kinds
        and set(spec.source_ids).issubset(action.source_ids)
        and set(spec.predicate_ids).issubset(outcome_predicates)
        and (
            not spec.requires_exact_locator
            or {
                (value.source_id, value.locator_id)
                for value in spec.source_locator_bindings
            }.issubset(action_pairs)
        )
    )


def _world_matches(world: dict[str, Any], restrictions: tuple[Any, ...]) -> bool:
    assignment = {
        value["predicate_id"]: value["value"] for value in world["assignments"]
    }
    return all(assignment[value.predicate_id] == value.value for value in restrictions)


def _partition_map(
    action: PACEActionSpec,
    worlds: tuple[dict[str, Any], ...],
) -> tuple[dict[str, str], tuple[dict[str, Any], ...]]:
    mapping: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    for outcome in action.outcomes:
        hashes = tuple(
            world["world_sha256"]
            for world in worlds
            if _world_matches(world, outcome.restrictions)
        )
        rows.append(
            {
                "outcome_id": outcome.outcome_id,
                "world_sha256s": list(hashes),
                "partition_sha256": pace_digest_v1(
                    {"outcome_id": outcome.outcome_id, "world_sha256s": list(hashes)}
                ),
            }
        )
        for world_hash in hashes:
            if world_hash in mapping:
                raise PACEVerificationError("overlapping action outcomes")
            mapping[world_hash] = outcome.outcome_id
        if not hashes:
            raise PACEVerificationError("empty action outcome")
    if set(mapping) != {world["world_sha256"] for world in worlds}:
        raise PACEVerificationError("non-exhaustive action outcomes")
    return mapping, tuple(rows)


def _scope_partition_map(
    action: PACEActionSpec,
    worlds: tuple[dict[str, Any], ...],
) -> dict[str, str]:
    """Map a proven world subset without requiring every global outcome to occur."""

    mapping: dict[str, str] = {}
    for outcome in action.outcomes:
        for world in worlds:
            if not _world_matches(world, outcome.restrictions):
                continue
            world_hash = world["world_sha256"]
            if world_hash in mapping:
                raise PACEVerificationError("overlapping action outcomes")
            mapping[world_hash] = outcome.outcome_id
    if set(mapping) != {world["world_sha256"] for world in worlds}:
        raise PACEVerificationError("non-exhaustive action outcomes")
    return mapping


def _informs_obligation(
    action: PACEActionSpec,
    obligation: PACEObligationSpec,
    worlds: tuple[dict[str, Any], ...],
) -> bool:
    mapping = _scope_partition_map(action, worlds)
    relevant = _relevant_worlds(obligation, worlds)
    for predicate_id in obligation.predicate_ids:
        values_by_outcome: dict[str, set[str]] = {}
        for world in relevant:
            assignment = {
                value["predicate_id"]: value["value"]
                for value in world["assignments"]
            }
            values_by_outcome.setdefault(mapping[world["world_sha256"]], set()).add(
                assignment[predicate_id]
            )
        if (
            len(values_by_outcome) >= 2
            and all(len(values) == 1 for values in values_by_outcome.values())
            and len({next(iter(values)) for values in values_by_outcome.values()}) >= 2
        ):
            return True
    return False


def _action_rejection(
    request: PACECompileRequest,
    action: PACEActionSpec,
    worlds: tuple[dict[str, Any], ...],
    unresolved: tuple[PACEObligationSpec, ...],
    unresolved_worlds: dict[str, tuple[dict[str, Any], ...]],
    possible_branches: frozenset[str],
) -> str | None:
    unresolved_by_id = {value.obligation_id: value for value in unresolved}
    addressed = tuple(
        unresolved_by_id[value]
        for value in action.obligation_ids
        if value in unresolved_by_id
    )
    if not addressed:
        return "ADDRESSES_NO_UNRESOLVED_OBLIGATION"
    if any(value.process_node_id != action.process_node_id for value in addressed):
        return "OBLIGATION_PROCESS_NODE_MISMATCH"
    if any(value.kind is PACEObligationKind.SATISFY_DEADLINE for value in addressed):
        return "NON_PREDICATE_OBLIGATION_ACTION_UNSUPPORTED_V1"
    process_node = next(
        value
        for value in request.state.graph.nodes
        if value.node_id == action.process_node_id
    )
    if process_node.node_kind in {"entry", "terminal"}:
        return "PROCESS_NODE_KIND_INVALID"
    if any(
        action.process_node_id not in world["reachable_node_ids"] for world in worlds
    ):
        return "ORPHAN_OR_INACTIVE_PROCESS_NODE"
    if process_node.topological_index != action.process_topological_index:
        return "PROCESS_TOPOLOGICAL_INDEX_MISMATCH"
    sources = {value.source_id: value for value in request.state.sources}
    allowed_pairs = {
        (source_id, locator)
        for source_id in action.source_ids
        for locator in sources[source_id].locator_ids
    }
    action_pairs = {
        (value.source_id, value.locator_id) for value in action.source_locator_bindings
    }
    if not action_pairs.issubset(allowed_pairs):
        return "UNDECLARED_LOCATOR"
    derived_capabilities = _derived_capabilities(request, action)
    if action.capability_ids != derived_capabilities:
        return "CAPABILITY_ROSTER_NOT_GRAPH_DERIVED"
    capability_by_id = {
        value.capability_id: value
        for value in request.state.graph.capability_specs
    }
    expected_capability_pairs = {
        (binding.source_id, binding.locator_id)
        for capability_id in derived_capabilities
        for binding in capability_by_id[capability_id].source_locator_bindings
        if capability_by_id[capability_id].requires_exact_locator
    }
    actual_capability_pairs = {
        (value.source_id, value.locator_id)
        for value in action.source_locator_bindings
    }
    capability_source_ids = {
        source_id
        for capability_id in derived_capabilities
        for source_id in capability_by_id[capability_id].source_ids
    }
    non_exact_source_ids = {
        source_id
        for capability_id in derived_capabilities
        if not capability_by_id[capability_id].requires_exact_locator
        for source_id in capability_by_id[capability_id].source_ids
    }
    if capability_source_ids != set(action.source_ids):
        return "CAPABILITY_SOURCE_ROSTER_NOT_EXACT"
    if not expected_capability_pairs.issubset(actual_capability_pairs) or any(
        pair not in expected_capability_pairs and pair[0] not in non_exact_source_ids
        for pair in actual_capability_pairs
    ):
        return "CAPABILITY_LOCATOR_ROSTER_NOT_EXACT"
    covered_predicates = {
        predicate_id
        for capability_id in derived_capabilities
        for predicate_id in capability_by_id[capability_id].predicate_ids
    }
    required_predicates = {
        predicate_id for obligation in addressed for predicate_id in obligation.predicate_ids
    }
    if not required_predicates.issubset(covered_predicates):
        return "CAPABILITY_PREDICATE_COVERAGE_INCOMPLETE"
    if any(
        not required_predicates.issubset(
            {atom.predicate_id for atom in outcome.restrictions}
        )
        for outcome in action.outcomes
    ):
        return "OUTCOME_PREDICATE_COVERAGE_INCOMPLETE"
    capabilities = frozenset(derived_capabilities)
    if any(
        not _capability_satisfied(value.evidence_capability, capabilities)
        for value in addressed
    ):
        return "EVIDENCE_CAPABILITY_UNSATISFIED"
    documents = {value.evidence_item_id: value for value in request.state.documents}
    document = documents.get(action.evidence_item_id)
    if document is None or document.state not in action.allowed_document_states:
        return "DOCUMENT_STATE_INVALID"
    now = datetime.fromisoformat(request.state.current_time.replace("Z", "+00:00"))
    if action.not_before is not None:
        if now < datetime.fromisoformat(action.not_before.replace("Z", "+00:00")):
            return "ACTION_TOO_EARLY"
    if action.not_after is not None:
        if now > datetime.fromisoformat(action.not_after.replace("Z", "+00:00")):
            return "ACTION_TOO_LATE"
    if any(not sources[value].authority_valid for value in action.source_ids):
        return "SOURCE_AUTHORITY_INVALID"
    if any(not _source_temporally_valid(request, value) for value in action.source_ids):
        return "SOURCE_TEMPORAL_VALIDITY_INVALID"
    relevant_branches = {
        value.branch_id
        for value in request.state.graph.branches
        if value.branch_id in possible_branches
        and value.process_node_id == action.process_node_id
    }
    provenance = {value.branch_id for value in request.state.branch_provenance}
    if not relevant_branches or not relevant_branches.issubset(provenance):
        return "INHERITED_PROVENANCE_INCOMPLETE"
    try:
        _partition_map(action, worlds)
    except PACEVerificationError as exc:
        return str(exc).upper().replace(" ", "_")
    if any(
        value.predicate_ids
        and not _informs_obligation(
            action,
            value,
            unresolved_worlds[value.obligation_id],
        )
        for value in addressed
    ):
        return "OUTCOME_DOES_NOT_RESOLVE_ADDRESSED_OBLIGATION"
    return None


def _refines(
    left: dict[str, str],
    right: dict[str, str],
    world_hashes: tuple[str, ...],
) -> bool:
    for first in world_hashes:
        for second in world_hashes:
            if left[first] == left[second] and right[first] != right[second]:
                return False
    return True


def _dominates(
    left: PACEActionSpec,
    right: PACEActionSpec,
    unresolved_ids: frozenset[str],
    unresolved_worlds: dict[str, tuple[dict[str, Any], ...]],
) -> bool:
    left_obligations = set(left.obligation_ids) & unresolved_ids
    right_obligations = set(right.obligation_ids) & unresolved_ids
    scope_maps = tuple(
        (
            _scope_partition_map(left, unresolved_worlds[obligation_id]),
            _scope_partition_map(right, unresolved_worlds[obligation_id]),
            tuple(
                world["world_sha256"]
                for world in unresolved_worlds[obligation_id]
            ),
        )
        for obligation_id in sorted(right_obligations)
    )
    left_cost = (left.burden_cost, left.delay_cost, left.safety_privacy_cost)
    right_cost = (right.burden_cost, right.delay_cost, right.safety_privacy_cost)
    return (
        left_obligations.issuperset(right_obligations)
        and all(
            _refines(left_map, right_map, hashes)
            for left_map, right_map, hashes in scope_maps
        )
        and all(first <= second for first, second in zip(left_cost, right_cost))
        and (
            left_obligations != right_obligations
            or any(
                not _refines(right_map, left_map, hashes)
                for left_map, right_map, hashes in scope_maps
            )
            or any(first < second for first, second in zip(left_cost, right_cost))
        )
    )


def _priority(
    action: PACEActionSpec,
    addressed: tuple[PACEObligationSpec, ...],
) -> PACEStaticPriority:
    semantic_key = [
        action.action_kind,
        action.process_node_id,
        action.evidence_item_id,
        list(action.obligation_ids),
        list(action.capability_ids),
        list(action.source_ids),
        list(action.locator_ids),
        [value.model_dump(mode="json") for value in action.source_locator_bindings],
        [value.model_dump(mode="json") for value in action.outcomes],
    ]
    return PACEStaticPriority(
        process_topological_index=action.process_topological_index,
        maximum_criticality_weight=max(
            (value.criticality_weight for value in addressed), default=0
        ),
        obligation_operator_rank=min(
            (_OBLIGATION_OPERATOR_RANK[value.kind] for value in addressed), default=999
        ),
        action_kind_rank=_ACTION_KIND_RANK[action.action_kind],
        burden_cost=action.burden_cost,
        delay_cost=action.delay_cost,
        safety_privacy_cost=action.safety_privacy_cost,
        semantic_action_key_sha256=pace_digest_v1(semantic_key),
    )


def _priority_key(value: PACEStaticPriority) -> tuple[int | str, ...]:
    return (
        value.process_topological_index,
        -value.maximum_criticality_weight,
        value.obligation_operator_rank,
        value.action_kind_rank,
        value.burden_cost,
        value.delay_cost,
        value.safety_privacy_cost,
        value.semantic_action_key_sha256,
    )


def _inherited_branch_ids(
    request: PACECompileRequest,
    worlds: tuple[dict[str, Any], ...],
    selected_node_id: str,
) -> tuple[str, ...]:
    graph = request.state.graph
    indexes = {value.node_id: value.topological_index for value in graph.nodes}
    inherited: set[str] = set()
    for world in worlds:
        if selected_node_id not in world["reachable_node_ids"]:
            continue
        ancestors = {selected_node_id}
        reachable = set(world["reachable_node_ids"])
        active = set(world["active_branch_ids"])
        for edge in sorted(
            graph.edges,
            key=lambda value: (
                indexes[value.target_node_id],
                value.edge_id,
            ),
            reverse=True,
        ):
            if (
                edge.target_node_id not in ancestors
                or edge.source_node_id not in reachable
                or (edge.branch_id is not None and edge.branch_id not in active)
            ):
                continue
            ancestors.add(edge.source_node_id)
            if edge.branch_id is not None:
                inherited.add(edge.branch_id)
    return tuple(sorted(inherited))


def _expected_certificate_payload(
    request: PACECompileRequest,
    certificate: PACEActionCertificate,
    worlds: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    possible_branches = frozenset(
        branch for world in worlds for branch in world["active_branch_ids"]
    )
    unresolved_worlds = _open_obligation_worlds(request, worlds)
    unresolved = tuple(
        value
        for value in request.obligations
        if value.obligation_id in unresolved_worlds
    )
    valid = tuple(
        action
        for action in request.actions
        if _action_rejection(
            request,
            action,
            worlds,
            unresolved,
            unresolved_worlds,
            possible_branches,
        )
        is None
    )
    unresolved_ids = frozenset(value.obligation_id for value in unresolved)
    alternatives = tuple(
        action
        for action in valid
        if not any(
            other.action_id != action.action_id
            and _dominates(
                other,
                action,
                unresolved_ids,
                unresolved_worlds,
            )
            for other in valid
        )
    )
    if not alternatives:
        raise PACEVerificationError("no certifiable action")
    unresolved_by_id = {value.obligation_id: value for value in unresolved}
    ranked: list[tuple[tuple[int | str, ...], PACEActionSpec, PACEStaticPriority]] = []
    for action in alternatives:
        addressed = tuple(
            unresolved_by_id[value]
            for value in action.obligation_ids
            if value in unresolved_by_id
        )
        priority = _priority(action, addressed)
        ranked.append((_priority_key(priority), action, priority))
    _, selected, priority = sorted(ranked, key=lambda value: value[0])[0]
    addressed = tuple(
        unresolved_by_id[value]
        for value in selected.obligation_ids
        if value in unresolved_by_id
    )
    _, partition_rows = _partition_map(selected, worlds)
    documents = {value.evidence_item_id: value for value in request.state.documents}
    world_set_material = [
        {
            "assignments": world["assignments"],
            "reachable_node_ids": world["reachable_node_ids"],
            "active_branch_ids": world["active_branch_ids"],
            "material_branch_ids": world["material_branch_ids"],
            "justified_decision_ids": world["justified_decision_ids"],
            "world_sha256": world["world_sha256"],
        }
        for world in worlds
    ]
    active_branches = tuple(
        sorted(set.intersection(*(set(world["active_branch_ids"]) for world in worlds)))
    )
    selected_branch_ids = set(
        _inherited_branch_ids(request, worlds, selected.process_node_id)
    )
    active_chain = tuple(
        value
        for value in request.state.branch_provenance
        if value.branch_id in selected_branch_ids
    )
    capability_expressions = tuple(
        sorted(
            (value.evidence_capability for value in addressed),
            key=lambda value: pace_digest_v1(value.model_dump(mode="json")),
        )
    )
    obligation_world_scopes = []
    for obligation in addressed:
        scope_payload = {
            "obligation_id": obligation.obligation_id,
            "world_sha256s": [
                value["world_sha256"]
                for value in unresolved_worlds[obligation.obligation_id]
            ],
        }
        obligation_world_scopes.append(
            {**scope_payload, "scope_sha256": pace_digest_v1(scope_payload)}
        )
    return {
        "contract": "casepath.pace-action-certificate/1.0.0",
        "case_id": request.state.graph.case_id,
        "process_version": request.state.graph.process_version,
        "rule_version": request.state.graph.rule_version,
        "graph_sha256": request.state.graph.graph_sha256,
        "source_registry_version": request.state.graph.source_registry_version,
        "knowledge_version": request.state.graph.knowledge_version,
        "state_sha256": request.state.state_sha256,
        "compile_request_sha256": request.request_sha256,
        "feasible_world_set_sha256": pace_digest_v1(world_set_material),
        "feasible_world_sha256s": [world["world_sha256"] for world in worlds],
        "active_branch_ids": list(active_branches),
        "possible_branch_ids": sorted(possible_branches),
        "blocking_decision_ids": sorted(
            {
                branch.decision_id
                for branch in request.state.graph.branches
                if branch.branch_id in possible_branches
            }
        ),
        "obligation_ids": sorted(value.obligation_id for value in addressed),
        "obligation_world_scopes": obligation_world_scopes,
        "required_predicate_ids": sorted(
            {item for value in addressed for item in value.predicate_ids}
        ),
        "derived_capability_ids": list(_derived_capabilities(request, selected)),
        "evidence_capability_expressions": [
            value.model_dump(mode="json") for value in capability_expressions
        ],
        "evidence_capability_sha256s": [
            pace_digest_v1(value.model_dump(mode="json"))
            for value in capability_expressions
        ],
        "accepted_action_alternative_ids": sorted(
            value.action_id for value in alternatives
        ),
        "accepted_document_alternative_ids": sorted(
            {value.evidence_item_id for value in alternatives}
        ),
        "evidence_item_id": selected.evidence_item_id,
        "document_state": documents[selected.evidence_item_id].state.value,
        "request_time": request.state.current_time,
        "source_ids": list(selected.source_ids),
        "locator_ids": list(selected.locator_ids),
        "source_locator_bindings": [
            value.model_dump(mode="json") for value in selected.source_locator_bindings
        ],
        "outcome_partitions": list(partition_rows),
        "static_priority": priority.model_dump(mode="json"),
        "action_id": selected.action_id,
        "action_kind": selected.action_kind,
        "process_node_id": selected.process_node_id,
        "action_spec_sha256": pace_digest_v1(selected.model_dump(mode="json")),
        "compiler_source_sha256": certificate.compiler_source_sha256,
        "verifier_source_sha256": certificate.verifier_source_sha256,
        "predecessor_event_sha256": request.state.predecessor_event_sha256,
        "active_chain_provenance": [
            value.model_dump(mode="json") for value in active_chain
        ],
        "hidden_oracle_inputs_read": False,
    }


def verify_certificate_v1(
    request: PACECompileRequest,
    certificate: PACEActionCertificate,
    *,
    expected_compiler_source_sha256: str,
    verifier_source_sha256: str,
) -> PACEVerificationReceipt:
    request = PACECompileRequest.model_validate_json(
        canonical_pace_json_bytes_v1(request.model_dump(mode="json"))
    )
    certificate = PACEActionCertificate.model_validate_json(
        canonical_pace_json_bytes_v1(certificate.model_dump(mode="json"))
    )
    if not is_sha256(expected_compiler_source_sha256):
        raise PACEVerificationError("expected compiler identity is invalid")
    if not is_sha256(verifier_source_sha256):
        raise PACEVerificationError("verifier identity is invalid")
    failures: list[str] = []
    if certificate.compiler_source_sha256 != expected_compiler_source_sha256:
        failures.append("COMPILER_SOURCE_IDENTITY_MISMATCH")
    if certificate.verifier_source_sha256 != verifier_source_sha256:
        failures.append("VERIFIER_SOURCE_IDENTITY_MISMATCH")
    try:
        worlds = _independent_worlds(request)
        expected = _expected_certificate_payload(request, certificate, worlds)
        expected_hash = pace_digest_v1(expected)
        actual = certificate.model_dump(mode="json", exclude={"certificate_sha256"})
        if actual != expected or certificate.certificate_sha256 != expected_hash:
            failures.append("CERTIFICATE_CONTENT_MISMATCH")
    except PACEVerificationError as exc:
        worlds = ()
        failures.append(
            f"VERIFICATION_DOMAIN_ERROR:{str(exc).upper().replace(' ', '_')}"
        )
    payload = {
        "contract": "casepath.pace-verification-receipt/1.0.0",
        "request_sha256": request.request_sha256,
        "certificate_sha256": certificate.certificate_sha256,
        "verifier_source_sha256": verifier_source_sha256,
        "valid": not failures,
        "failure_codes": sorted(set(failures)),
        "checked_world_count": len(worlds),
        "hidden_oracle_inputs_read": False,
    }
    return PACEVerificationReceipt.model_validate_json(
        canonical_pace_json_bytes_v1(
            {**payload, "receipt_sha256": pace_digest_v1(payload)}
        )
    )


def _expected_result_summary(
    request: PACECompileRequest,
) -> tuple[str, str, tuple[str, ...], tuple[str, ...], tuple[dict[str, Any], ...]]:
    worlds = _independent_worlds(request)
    world_set_sha256 = pace_digest_v1(list(worlds))
    if not worlds:
        return "NO_FEASIBLE_WORLD", world_set_sha256, (), (), worlds
    possible_branches = frozenset(
        branch for world in worlds for branch in world["active_branch_ids"]
    )
    if not possible_branches:
        return "NO_PROCESS_COVERAGE", world_set_sha256, (), (), worlds
    unresolved_worlds = _open_obligation_worlds(request, worlds)
    unresolved = tuple(
        value
        for value in request.obligations
        if value.obligation_id in unresolved_worlds
    )
    unresolved_ids = tuple(sorted(value.obligation_id for value in unresolved))
    if any(
        value.kind
        in {
            PACEObligationKind.VERIFY_AUTHORITY,
            PACEObligationKind.VERIFY_TEMPORAL_VALIDITY,
        }
        for value in unresolved
    ):
        return "UNRESOLVED_AUTHORITY", world_set_sha256, unresolved_ids, (), worlds
    decision_profiles = {
        (
            tuple(world["material_branch_ids"]),
            tuple(world["justified_decision_ids"]),
        )
        for world in worlds
    }
    if not unresolved and len(decision_profiles) == 1:
        return "ALL_WORLDS_AGREE", world_set_sha256, (), (), worlds

    valid: list[PACEActionSpec] = []
    rejected: list[str] = []
    for action in request.actions:
        reason = _action_rejection(
            request,
            action,
            worlds,
            unresolved,
            unresolved_worlds,
            possible_branches,
        )
        if reason is None:
            valid.append(action)
        else:
            rejected.append(f"{action.action_id}:{reason}")
    unresolved_set = frozenset(unresolved_ids)
    alternatives: list[PACEActionSpec] = []
    for action in valid:
        if any(
            other.action_id != action.action_id
            and _dominates(
                other,
                action,
                unresolved_set,
                unresolved_worlds,
            )
            for other in valid
        ):
            rejected.append(f"{action.action_id}:DOMINATED")
        else:
            alternatives.append(action)
    terminal_state = "ACTION_SELECTED" if alternatives else "NO_ADMISSIBLE_ACTION"
    return (
        terminal_state,
        world_set_sha256,
        unresolved_ids,
        tuple(sorted(set(rejected))),
        worlds,
    )


def verify_compile_result_v1(
    request: PACECompileRequest,
    result: PACECompileResult,
    *,
    expected_compiler_source_sha256: str,
    verifier_source_sha256: str,
) -> tuple[str, ...]:
    """Independently recompute the complete result, not only its certificate."""

    request = PACECompileRequest.model_validate_json(
        canonical_pace_json_bytes_v1(request.model_dump(mode="json"))
    )
    result = PACECompileResult.model_validate_json(
        canonical_pace_json_bytes_v1(result.model_dump(mode="json"))
    )
    failures: list[str] = []
    if result.request_sha256 != request.request_sha256:
        failures.append("RESULT_REQUEST_MISMATCH")
    try:
        (
            expected_terminal,
            expected_world_set,
            expected_unresolved,
            expected_rejections,
            _,
        ) = _expected_result_summary(request)
        if result.terminal_state != expected_terminal:
            failures.append("RESULT_TERMINAL_STATE_MISMATCH")
        if result.feasible_world_set_sha256 != expected_world_set:
            failures.append("RESULT_WORLD_SET_MISMATCH")
        if result.unresolved_obligation_ids != expected_unresolved:
            failures.append("RESULT_UNRESOLVED_OBLIGATIONS_MISMATCH")
        if result.rejected_action_reasons != expected_rejections:
            failures.append("RESULT_REJECTION_REASONS_MISMATCH")
        if expected_terminal == "ACTION_SELECTED":
            if result.certificate is None:
                failures.append("RESULT_CERTIFICATE_ABSENT")
            else:
                verification = verify_certificate_v1(
                    request,
                    result.certificate,
                    expected_compiler_source_sha256=(
                        expected_compiler_source_sha256
                    ),
                    verifier_source_sha256=verifier_source_sha256,
                )
                if not verification.valid:
                    failures.append("RESULT_CERTIFICATE_INVALID")
        elif result.certificate is not None:
            failures.append("RESULT_CERTIFICATE_UNEXPECTED")
    except PACEVerificationError as exc:
        failures.append(
            f"RESULT_DOMAIN_ERROR:{str(exc).upper().replace(' ', '_')}"
        )
    return tuple(sorted(set(failures)))
