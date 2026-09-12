from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime

from ..foundation.common import is_sha256
from ..pace_canonical import canonical_pace_json_bytes_v1, pace_digest_v1
from ..pace_contracts import (
    PACEActionCertificate,
    PACEActionSpec,
    PACEAtom,
    PACECapabilityExpression,
    PACECapabilityOperator,
    PACECompileRequest,
    PACECompileResult,
    PACECondition,
    PACEObligationKind,
    PACEObligationExpression,
    PACEObligationSpec,
    PACEOutcomePartition,
    PACEStaticPriority,
    PACETruthPolarity,
    PACEWorld,
)


class PACECompilerError(ValueError):
    pass


def evaluate_condition_v1(
    condition: PACECondition,
    assignment: Mapping[str, str],
) -> bool:
    if condition.operator == "ALWAYS":
        return True
    return any(
        all(assignment.get(atom.predicate_id) == atom.value for atom in clause.atoms)
        for clause in condition.clauses
    )


def _observation_domains(request: PACECompileRequest) -> dict[str, tuple[str, ...]]:
    domains = {
        value.predicate_id: set(value.domain)
        for value in request.state.graph.predicate_specs
    }
    for observation in request.state.observations:
        source = next(
            value
            for value in request.state.sources
            if value.source_id == observation.source_id
        )
        if (
            observation.reliability_milli != 1000
            or not source.authority_valid
            or not _source_is_temporally_valid(request, observation.source_id)
        ):
            continue
        if observation.polarity in {
            PACETruthPolarity.SUPPORTS,
            PACETruthPolarity.LIMITS,
        }:
            domains[observation.predicate_id].intersection_update(
                observation.allowed_values
            )
        elif observation.polarity is PACETruthPolarity.REFUTES:
            domains[observation.predicate_id].difference_update(
                observation.allowed_values
            )
    return {key: tuple(sorted(value)) for key, value in domains.items()}


def enumerate_worlds_v1(request: PACECompileRequest) -> tuple[PACEWorld, ...]:
    specs = request.state.graph.predicate_specs
    if len(specs) > request.config.maximum_predicates:
        raise PACECompilerError("predicate count exceeds the frozen enumeration cap")
    domains = _observation_domains(request)
    upper_bound = 1
    for spec in specs:
        upper_bound *= len(domains[spec.predicate_id])
    if upper_bound > request.config.maximum_worlds:
        raise PACECompilerError("world count exceeds the frozen enumeration cap")

    worlds: list[PACEWorld] = []
    assignment: dict[str, str] = {}

    def visit(index: int) -> None:
        if index < len(specs):
            predicate_id = specs[index].predicate_id
            for value in domains[predicate_id]:
                assignment[predicate_id] = value
                visit(index + 1)
            assignment.pop(predicate_id, None)
            return
        if not all(
            evaluate_condition_v1(constraint.condition, assignment)
            for constraint in request.state.graph.constraints
        ):
            return
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
                if not evaluate_condition_v1(branch.condition, assignment):
                    continue
                active.add(branch.branch_id)
            reachable.add(edge.target_node_id)
        active_branches = tuple(sorted(active))
        material_branches = tuple(
            branch.branch_id
            for branch in request.state.graph.branches
            if branch.branch_id in active_branches and branch.material
        )
        decisions = tuple(
            sorted(
                {
                    branch.decision_id
                    for branch in request.state.graph.branches
                    if branch.branch_id in active_branches
                }
            )
        )
        material = {
            "assignments": [
                {"predicate_id": key, "value": assignment[key]}
                for key in sorted(assignment)
            ],
            "reachable_node_ids": sorted(reachable),
            "active_branch_ids": list(active_branches),
            "material_branch_ids": list(material_branches),
            "justified_decision_ids": list(decisions),
        }
        worlds.append(
            PACEWorld(
                assignments=tuple(
                    PACEAtom(predicate_id=key, value=assignment[key])
                    for key in sorted(assignment)
                ),
                reachable_node_ids=tuple(sorted(reachable)),
                active_branch_ids=active_branches,
                material_branch_ids=material_branches,
                justified_decision_ids=decisions,
                world_sha256=pace_digest_v1(material),
            )
        )

    visit(0)
    return tuple(sorted(worlds, key=lambda value: value.world_sha256))


def _assignment(world: PACEWorld) -> dict[str, str]:
    return {value.predicate_id: value.value for value in world.assignments}


def _active_worlds(
    obligation: PACEObligationSpec,
    worlds: tuple[PACEWorld, ...],
) -> tuple[PACEWorld, ...]:
    return tuple(
        world
        for world in worlds
        if evaluate_condition_v1(obligation.activation, _assignment(world))
    )


def _source_is_temporally_valid(
    request: PACECompileRequest,
    source_id: str,
    *,
    at: str | None = None,
) -> bool:
    current = datetime.fromisoformat(
        (at or request.state.current_time).replace("Z", "+00:00")
    )
    source = next(
        value for value in request.state.sources if value.source_id == source_id
    )
    if source.valid_from is not None and current < datetime.fromisoformat(
        source.valid_from.replace("Z", "+00:00")
    ):
        return False
    return not (
        source.valid_until is not None
        and current > datetime.fromisoformat(source.valid_until.replace("Z", "+00:00"))
    )


def obligation_is_resolved_v1(
    request: PACECompileRequest,
    obligation: PACEObligationSpec,
    worlds: tuple[PACEWorld, ...],
) -> bool:
    relevant = _active_worlds(obligation, worlds)
    if not relevant:
        return True
    assignments = tuple(_assignment(world) for world in relevant)
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
        return all(
            sources[source_id].authority_valid for source_id in obligation.source_ids
        )
    if obligation.kind is PACEObligationKind.VERIFY_TEMPORAL_VALIDITY:
        assert obligation.verification_time is not None
        return all(
            _source_is_temporally_valid(
                request,
                source_id,
                at=obligation.verification_time,
            )
            for source_id in obligation.source_ids
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
    raise PACECompilerError("unsupported obligation kind")


def _unresolved_obligation_worlds_v1(
    request: PACECompileRequest,
    worlds: tuple[PACEWorld, ...],
) -> dict[str, tuple[PACEWorld, ...]]:
    obligations_by_id = {value.obligation_id: value for value in request.obligations}
    worlds_by_hash = {value.world_sha256: value for value in worlds}

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
        scoped_worlds: tuple[PACEWorld, ...],
    ) -> dict[str, frozenset[str]]:
        if expression.operator == "OBLIGATION":
            assert expression.obligation_id is not None
            obligation = obligations_by_id[expression.obligation_id]
            active_worlds = _active_worlds(obligation, scoped_worlds)
            return (
                {
                    expression.obligation_id: frozenset(
                        value.world_sha256 for value in active_worlds
                    )
                }
                if not obligation_is_resolved_v1(request, obligation, active_worlds)
                else {}
            )
        if expression.operator == "CONDITIONAL":
            assert expression.condition is not None
            conditional_worlds = tuple(
                world
                for world in scoped_worlds
                if evaluate_condition_v1(expression.condition, _assignment(world))
            )
            return open_scopes(expression.children[0], conditional_worlds)
        if expression.operator == "TEMPORAL":
            assert expression.temporal_at is not None
            current = datetime.fromisoformat(
                request.state.current_time.replace("Z", "+00:00")
            )
            activation = datetime.fromisoformat(
                expression.temporal_at.replace("Z", "+00:00")
            )
            return (
                open_scopes(expression.children[0], scoped_worlds)
                if current >= activation
                else {}
            )
        child_values = tuple(
            open_scopes(value, scoped_worlds) for value in expression.children
        )
        if expression.operator == "ANY_OF" and any(not value for value in child_values):
            return {}
        return merge_scopes(child_values)

    scope_hashes = open_scopes(request.obligation_expression, worlds)
    return {
        obligation_id: tuple(
            worlds_by_hash[world_sha256]
            for world_sha256 in sorted(world_hashes)
        )
        for obligation_id, world_hashes in sorted(scope_hashes.items())
    }


def unresolved_obligations_v1(
    request: PACECompileRequest,
    worlds: tuple[PACEWorld, ...],
) -> tuple[PACEObligationSpec, ...]:
    unresolved_ids = _unresolved_obligation_worlds_v1(request, worlds)

    return tuple(
        value for value in request.obligations if value.obligation_id in unresolved_ids
    )


def capability_expression_satisfied_v1(
    expression: PACECapabilityExpression,
    capability_ids: frozenset[str],
) -> bool:
    if expression.operator is PACECapabilityOperator.CAPABILITY:
        assert expression.capability_id is not None
        return expression.capability_id in capability_ids
    results = tuple(
        capability_expression_satisfied_v1(value, capability_ids)
        for value in expression.children
    )
    return (
        all(results)
        if expression.operator is PACECapabilityOperator.AND
        else any(results)
    )


def _derived_capability_ids(
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


def _partition_worlds(
    worlds: tuple[PACEWorld, ...],
    restrictions: Iterable[PACEAtom],
) -> tuple[PACEWorld, ...]:
    required = {value.predicate_id: value.value for value in restrictions}
    return tuple(
        world
        for world in worlds
        if all(_assignment(world).get(key) == value for key, value in required.items())
    )


def _action_informs_obligation(
    action: PACEActionSpec,
    obligation: PACEObligationSpec,
    worlds: tuple[PACEWorld, ...],
) -> bool:
    signature = _partition_signature(action, worlds)
    relevant = _active_worlds(obligation, worlds)
    for predicate_id in obligation.predicate_ids:
        values_by_outcome: dict[str, set[str]] = {}
        for world in relevant:
            values_by_outcome.setdefault(signature[world.world_sha256], set()).add(
                _assignment(world)[predicate_id]
            )
        if (
            len(values_by_outcome) >= 2
            and all(len(values) == 1 for values in values_by_outcome.values())
            and len({next(iter(values)) for values in values_by_outcome.values()}) >= 2
        ):
            return True
    return False


def _valid_action_reason(
    request: PACECompileRequest,
    action: PACEActionSpec,
    worlds: tuple[PACEWorld, ...],
    unresolved: tuple[PACEObligationSpec, ...],
    unresolved_worlds: Mapping[str, tuple[PACEWorld, ...]],
    possible_branch_ids: frozenset[str],
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
        action.process_node_id not in world.reachable_node_ids for world in worlds
    ):
        return "ORPHAN_OR_INACTIVE_PROCESS_NODE"
    if process_node.topological_index != action.process_topological_index:
        return "PROCESS_TOPOLOGICAL_INDEX_MISMATCH"
    source_by_id = {value.source_id: value for value in request.state.sources}
    declared_pairs = {
        (source_id, locator)
        for source_id in action.source_ids
        for locator in source_by_id[source_id].locator_ids
    }
    action_pairs = {
        (value.source_id, value.locator_id) for value in action.source_locator_bindings
    }
    if not action_pairs.issubset(declared_pairs):
        return "UNDECLARED_LOCATOR"
    derived_capabilities = _derived_capability_ids(request, action)
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
        not capability_expression_satisfied_v1(value.evidence_capability, capabilities)
        for value in addressed
    ):
        return "EVIDENCE_CAPABILITY_UNSATISFIED"
    document = next(
        (
            value
            for value in request.state.documents
            if value.evidence_item_id == action.evidence_item_id
        ),
        None,
    )
    if document is None or document.state not in action.allowed_document_states:
        return "DOCUMENT_STATE_INVALID"
    current = datetime.fromisoformat(request.state.current_time.replace("Z", "+00:00"))
    if action.not_before is not None and current < datetime.fromisoformat(
        action.not_before.replace("Z", "+00:00")
    ):
        return "ACTION_TOO_EARLY"
    if action.not_after is not None and current > datetime.fromisoformat(
        action.not_after.replace("Z", "+00:00")
    ):
        return "ACTION_TOO_LATE"
    if any(not source_by_id[value].authority_valid for value in action.source_ids):
        return "SOURCE_AUTHORITY_INVALID"
    if any(
        not _source_is_temporally_valid(request, value) for value in action.source_ids
    ):
        return "SOURCE_TEMPORAL_VALIDITY_INVALID"
    relevant_branches = {
        value.branch_id
        for value in request.state.graph.branches
        if value.branch_id in possible_branch_ids
        and value.process_node_id == action.process_node_id
    }
    provenance_by_branch = {
        value.branch_id: value for value in request.state.branch_provenance
    }
    if not relevant_branches or not relevant_branches.issubset(provenance_by_branch):
        return "INHERITED_PROVENANCE_INCOMPLETE"
    partitions = tuple(
        _partition_worlds(worlds, outcome.restrictions) for outcome in action.outcomes
    )
    if any(not partition for partition in partitions):
        return "OUTCOME_PARTITION_EMPTY"
    for world in worlds:
        if sum(world in partition for partition in partitions) != 1:
            return "OUTCOME_PARTITION_NOT_DISJOINT_EXHAUSTIVE"
    if (
        len(
            {
                tuple(value.world_sha256 for value in partition)
                for partition in partitions
            }
        )
        < 2
    ):
        return "ZERO_INFORMATION_OUTCOME_PARTITION"
    if any(
        value.predicate_ids
        and not _action_informs_obligation(
            action,
            value,
            unresolved_worlds[value.obligation_id],
        )
        for value in addressed
    ):
        return "OUTCOME_DOES_NOT_RESOLVE_ADDRESSED_OBLIGATION"
    return None


def _partition_signature(
    action: PACEActionSpec,
    worlds: tuple[PACEWorld, ...],
) -> dict[str, str]:
    signature: dict[str, str] = {}
    for outcome in action.outcomes:
        for world in _partition_worlds(worlds, outcome.restrictions):
            signature[world.world_sha256] = outcome.outcome_id
    return signature


def _partition_refines(
    left: PACEActionSpec,
    right: PACEActionSpec,
    worlds: tuple[PACEWorld, ...],
) -> bool:
    left_signature = _partition_signature(left, worlds)
    right_signature = _partition_signature(right, worlds)
    for first in worlds:
        for second in worlds:
            if (
                left_signature[first.world_sha256]
                == left_signature[second.world_sha256]
            ):
                if (
                    right_signature[first.world_sha256]
                    != right_signature[second.world_sha256]
                ):
                    return False
    return True


def _action_dominates(
    left: PACEActionSpec,
    right: PACEActionSpec,
    unresolved_ids: frozenset[str],
    unresolved_worlds: Mapping[str, tuple[PACEWorld, ...]],
) -> bool:
    left_obligations = set(left.obligation_ids).intersection(unresolved_ids)
    right_obligations = set(right.obligation_ids).intersection(unresolved_ids)
    left_cost = (left.burden_cost, left.delay_cost, left.safety_privacy_cost)
    right_cost = (right.burden_cost, right.delay_cost, right.safety_privacy_cost)
    no_worse = all(first <= second for first, second in zip(left_cost, right_cost))
    resolving_superset = left_obligations.issuperset(right_obligations)
    right_scopes = tuple(
        unresolved_worlds[obligation_id]
        for obligation_id in sorted(right_obligations)
    )
    information_no_worse = all(
        _partition_refines(left, right, scope) for scope in right_scopes
    )
    strict = (
        left_obligations != right_obligations
        or any(not _partition_refines(right, left, scope) for scope in right_scopes)
        or any(first < second for first, second in zip(left_cost, right_cost))
    )
    return no_worse and resolving_superset and information_no_worse and strict


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


def _outcome_partitions(
    action: PACEActionSpec,
    worlds: tuple[PACEWorld, ...],
) -> tuple[PACEOutcomePartition, ...]:
    partitions: list[PACEOutcomePartition] = []
    for outcome in action.outcomes:
        hashes = tuple(
            value.world_sha256
            for value in _partition_worlds(worlds, outcome.restrictions)
        )
        material = {"outcome_id": outcome.outcome_id, "world_sha256s": list(hashes)}
        partitions.append(
            PACEOutcomePartition(
                outcome_id=outcome.outcome_id,
                world_sha256s=hashes,
                partition_sha256=pace_digest_v1(material),
            )
        )
    return tuple(partitions)


def _static_priority(
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
    worlds: tuple[PACEWorld, ...],
    selected_node_id: str,
) -> tuple[str, ...]:
    graph = request.state.graph
    indexes = {value.node_id: value.topological_index for value in graph.nodes}
    inherited: set[str] = set()
    for world in worlds:
        if selected_node_id not in world.reachable_node_ids:
            continue
        ancestors = {selected_node_id}
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
                or edge.source_node_id not in world.reachable_node_ids
                or (
                    edge.branch_id is not None
                    and edge.branch_id not in world.active_branch_ids
                )
            ):
                continue
            ancestors.add(edge.source_node_id)
            if edge.branch_id is not None:
                inherited.add(edge.branch_id)
    return tuple(sorted(inherited))


def _build_result(
    request: PACECompileRequest,
    *,
    world_set_sha256: str,
    certificate: PACEActionCertificate | None,
    terminal_state: str,
    unresolved: tuple[PACEObligationSpec, ...],
    rejected: tuple[str, ...],
) -> PACECompileResult:
    payload = {
        "contract": "casepath.pace-compile-result/1.0.0",
        "request_sha256": request.request_sha256,
        "feasible_world_set_sha256": world_set_sha256,
        "certificate": certificate.model_dump(mode="json") if certificate else None,
        "terminal_state": terminal_state,
        "unresolved_obligation_ids": sorted(
            value.obligation_id for value in unresolved
        ),
        "rejected_action_reasons": sorted(set(rejected)),
    }
    return PACECompileResult.model_validate_json(
        canonical_pace_json_bytes_v1(
            {**payload, "result_sha256": pace_digest_v1(payload)}
        )
    )


def compile_pace_v1(
    request: PACECompileRequest,
    *,
    compiler_source_sha256: str,
    verifier_source_sha256: str,
) -> PACECompileResult:
    if not is_sha256(compiler_source_sha256):
        raise PACECompilerError("compiler source identity is invalid")
    if not is_sha256(verifier_source_sha256):
        raise PACECompilerError("verifier source identity is invalid")
    worlds = enumerate_worlds_v1(request)
    world_set_sha256 = pace_digest_v1(
        [value.model_dump(mode="json") for value in worlds]
    )
    if not worlds:
        return _build_result(
            request,
            world_set_sha256=world_set_sha256,
            certificate=None,
            terminal_state="NO_FEASIBLE_WORLD",
            unresolved=(),
            rejected=(),
        )
    possible_branch_ids = frozenset(
        value for world in worlds for value in world.active_branch_ids
    )
    if not possible_branch_ids:
        return _build_result(
            request,
            world_set_sha256=world_set_sha256,
            certificate=None,
            terminal_state="NO_PROCESS_COVERAGE",
            unresolved=(),
            rejected=(),
        )
    unresolved_worlds = _unresolved_obligation_worlds_v1(request, worlds)
    unresolved = tuple(
        value
        for value in request.obligations
        if value.obligation_id in unresolved_worlds
    )
    invalid_authority = any(
        value.kind
        in {
            PACEObligationKind.VERIFY_AUTHORITY,
            PACEObligationKind.VERIFY_TEMPORAL_VALIDITY,
        }
        for value in unresolved
    )
    if invalid_authority:
        return _build_result(
            request,
            world_set_sha256=world_set_sha256,
            certificate=None,
            terminal_state="UNRESOLVED_AUTHORITY",
            unresolved=unresolved,
            rejected=(),
        )
    decision_profiles = {
        (value.material_branch_ids, value.justified_decision_ids) for value in worlds
    }
    if not unresolved and len(decision_profiles) == 1:
        return _build_result(
            request,
            world_set_sha256=world_set_sha256,
            certificate=None,
            terminal_state="ALL_WORLDS_AGREE",
            unresolved=unresolved,
            rejected=(),
        )

    valid: list[PACEActionSpec] = []
    rejected: list[str] = []
    for action in request.actions:
        reason = _valid_action_reason(
            request,
            action,
            worlds,
            unresolved,
            unresolved_worlds,
            possible_branch_ids,
        )
        if reason is None:
            valid.append(action)
        else:
            rejected.append(f"{action.action_id}:{reason}")
    unresolved_ids = frozenset(value.obligation_id for value in unresolved)
    non_dominated: list[PACEActionSpec] = []
    for action in valid:
        dominators = [
            other
            for other in valid
            if other.action_id != action.action_id
            and _action_dominates(
                other,
                action,
                unresolved_ids,
                unresolved_worlds,
            )
        ]
        if dominators:
            rejected.append(f"{action.action_id}:DOMINATED")
        else:
            non_dominated.append(action)
    if not non_dominated:
        return _build_result(
            request,
            world_set_sha256=world_set_sha256,
            certificate=None,
            terminal_state="NO_ADMISSIBLE_ACTION",
            unresolved=unresolved,
            rejected=tuple(rejected),
        )

    unresolved_by_id = {value.obligation_id: value for value in unresolved}
    ranked: list[
        tuple[PACEActionSpec, PACEStaticPriority, tuple[PACEOutcomePartition, ...]]
    ] = []
    for action in non_dominated:
        addressed_for_action = tuple(
            unresolved_by_id[value]
            for value in action.obligation_ids
            if value in unresolved_by_id
        )
        ranked.append(
            (
                action,
                _static_priority(action, addressed_for_action),
                _outcome_partitions(action, worlds),
            )
        )
    selected, static_priority, partitions = sorted(
        ranked, key=lambda value: _priority_key(value[1])
    )[0]
    active_branch_ids = tuple(
        sorted(set.intersection(*(set(value.active_branch_ids) for value in worlds)))
    )
    addressed = tuple(
        unresolved_by_id[value]
        for value in selected.obligation_ids
        if value in unresolved_by_id
    )
    document = next(
        value
        for value in request.state.documents
        if value.evidence_item_id == selected.evidence_item_id
    )
    selected_branch_ids = set(_inherited_branch_ids(request, worlds, selected.process_node_id))
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
                value.world_sha256
                for value in unresolved_worlds[obligation.obligation_id]
            ],
        }
        obligation_world_scopes.append(
            {**scope_payload, "scope_sha256": pace_digest_v1(scope_payload)}
        )
    certificate_payload = {
        "contract": "casepath.pace-action-certificate/1.0.0",
        "case_id": request.state.graph.case_id,
        "process_version": request.state.graph.process_version,
        "rule_version": request.state.graph.rule_version,
        "graph_sha256": request.state.graph.graph_sha256,
        "source_registry_version": request.state.graph.source_registry_version,
        "knowledge_version": request.state.graph.knowledge_version,
        "state_sha256": request.state.state_sha256,
        "compile_request_sha256": request.request_sha256,
        "feasible_world_set_sha256": world_set_sha256,
        "feasible_world_sha256s": [value.world_sha256 for value in worlds],
        "active_branch_ids": list(active_branch_ids),
        "possible_branch_ids": sorted(possible_branch_ids),
        "blocking_decision_ids": sorted(
            {
                branch.decision_id
                for branch in request.state.graph.branches
                if branch.branch_id in possible_branch_ids
            }
        ),
        "obligation_ids": sorted(value.obligation_id for value in addressed),
        "obligation_world_scopes": obligation_world_scopes,
        "required_predicate_ids": sorted(
            {item for value in addressed for item in value.predicate_ids}
        ),
        "derived_capability_ids": list(_derived_capability_ids(request, selected)),
        "evidence_capability_expressions": [
            value.model_dump(mode="json") for value in capability_expressions
        ],
        "evidence_capability_sha256s": [
            pace_digest_v1(value.model_dump(mode="json"))
            for value in capability_expressions
        ],
        "accepted_action_alternative_ids": sorted(
            value.action_id for value in non_dominated
        ),
        "accepted_document_alternative_ids": sorted(
            {value.evidence_item_id for value in non_dominated}
        ),
        "evidence_item_id": selected.evidence_item_id,
        "document_state": document.state.value,
        "request_time": request.state.current_time,
        "source_ids": list(selected.source_ids),
        "locator_ids": list(selected.locator_ids),
        "source_locator_bindings": [
            value.model_dump(mode="json") for value in selected.source_locator_bindings
        ],
        "outcome_partitions": [value.model_dump(mode="json") for value in partitions],
        "static_priority": static_priority.model_dump(mode="json"),
        "action_id": selected.action_id,
        "action_kind": selected.action_kind,
        "process_node_id": selected.process_node_id,
        "action_spec_sha256": pace_digest_v1(selected.model_dump(mode="json")),
        "compiler_source_sha256": compiler_source_sha256,
        "verifier_source_sha256": verifier_source_sha256,
        "predecessor_event_sha256": request.state.predecessor_event_sha256,
        "active_chain_provenance": [
            value.model_dump(mode="json") for value in active_chain
        ],
        "hidden_oracle_inputs_read": False,
    }
    certificate = PACEActionCertificate.model_validate_json(
        canonical_pace_json_bytes_v1(
            {
                **certificate_payload,
                "certificate_sha256": pace_digest_v1(certificate_payload),
            }
        )
    )
    return _build_result(
        request,
        world_set_sha256=world_set_sha256,
        certificate=certificate,
        terminal_state="ACTION_SELECTED",
        unresolved=unresolved,
        rejected=tuple(rejected),
    )


def canonical_result_bytes_v1(result: PACECompileResult) -> bytes:
    return canonical_pace_json_bytes_v1(result.model_dump(mode="json"))
