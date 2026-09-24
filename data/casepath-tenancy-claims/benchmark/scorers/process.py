"""Process, predicate, path, and partial-order scoring."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

from contracts.expressions import ExpressionError, evaluate_expression
from contracts.schema import (
    AcceptanceContract,
    CandidateArtifact,
    ConceptKind,
    RelationSpec,
    RelationType,
    Requirement,
)

from .alignment import Alignment


@dataclass(frozen=True)
class ProcessScore:
    metrics: dict[str, float]
    counts: dict[str, int]
    failures: tuple[str, ...]


def _active(expression: str, assignment: dict[str, Any], failures: list[str], label: str) -> bool:
    try:
        return evaluate_expression(expression, assignment)
    except ExpressionError as exc:
        failures.append(f"{label}: {exc}")
        return False


def _ratio(numerator: int, denominator: int, *, empty: float = 1.0) -> float:
    return numerator / denominator if denominator else empty


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _relation_matches(
    relation: RelationSpec,
    candidate_source: str,
    candidate_target: str,
    candidate_type: RelationType,
    alignment: Alignment,
) -> bool:
    endpoint_map = alignment.endpoint_map
    return (
        relation.relation_type is candidate_type
        and relation.source_id in endpoint_map.get(candidate_source, frozenset())
        and relation.target_id in endpoint_map.get(candidate_target, frozenset())
    )


def _reachable(graph: dict[str, set[str]], start: str, end: str) -> bool:
    pending = deque([start])
    visited: set[str] = set()
    while pending:
        node = pending.popleft()
        if node == end:
            return True
        if node in visited:
            continue
        visited.add(node)
        pending.extend(graph.get(node, set()).difference(visited))
    return False


def score_process(
    contract: AcceptanceContract,
    candidate: CandidateArtifact,
    alignment: Alignment,
) -> ProcessScore:
    failures: list[str] = []
    assignment = contract.scenario
    active_contract = {
        concept.concept_id: concept
        for concept in contract.concepts
        if _active(concept.active_when, assignment, failures, f"concept {concept.concept_id}")
    }
    active_candidates = {
        concept.concept_id
        for concept in candidate.concepts
        if _active(
            concept.active_when,
            assignment,
            failures,
            f"candidate concept {concept.concept_id}",
        )
    }
    covered_contract = {
        contract_id
        for candidate_id in active_candidates
        for contract_id in alignment.concept_map.get(candidate_id, frozenset())
    }
    required_ids = {
        concept_id
        for concept_id, concept in active_contract.items()
        if concept.requirement is Requirement.MANDATORY
    }
    allowed_ids = {
        concept_id
        for concept_id, concept in active_contract.items()
        if concept.requirement is not Requirement.FORBIDDEN
    }
    forbidden_ids = {
        concept_id
        for concept_id, concept in active_contract.items()
        if concept.requirement is Requirement.FORBIDDEN
    }
    required_node_hits = len(required_ids.intersection(covered_contract))
    supported_candidate_nodes = sum(
        bool(alignment.concept_map.get(candidate_id, frozenset()).intersection(allowed_ids))
        for candidate_id in active_candidates
    )
    forbidden_concept_violations = sum(
        bool(alignment.concept_map.get(candidate_id, frozenset()).intersection(forbidden_ids))
        for candidate_id in active_candidates
    )

    active_contract_relations = [
        relation
        for relation in contract.relations
        if _active(relation.active_when, assignment, failures, f"relation {relation.relation_id}")
    ]
    active_candidate_relations = [
        relation
        for relation in candidate.relations
        if _active(
            relation.active_when,
            assignment,
            failures,
            f"candidate relation {relation.relation_id}",
        )
    ]
    required_relations = [
        relation
        for relation in active_contract_relations
        if relation.requirement is Requirement.MANDATORY
    ]
    allowed_relations = [
        relation
        for relation in active_contract_relations
        if relation.requirement is not Requirement.FORBIDDEN
    ]
    forbidden_relations = [
        relation
        for relation in active_contract_relations
        if relation.requirement is Requirement.FORBIDDEN
    ]
    required_relation_hits = sum(
        any(
            _relation_matches(
                relation,
                candidate_relation.source_id,
                candidate_relation.target_id,
                candidate_relation.relation_type,
                alignment,
            )
            for candidate_relation in active_candidate_relations
        )
        for relation in required_relations
    )
    supported_candidate_relations = sum(
        any(
            _relation_matches(
                relation,
                candidate_relation.source_id,
                candidate_relation.target_id,
                candidate_relation.relation_type,
                alignment,
            )
            for relation in allowed_relations
        )
        for candidate_relation in active_candidate_relations
    )
    forbidden_relation_violations = sum(
        any(
            _relation_matches(
                relation,
                candidate_relation.source_id,
                candidate_relation.target_id,
                candidate_relation.relation_type,
                alignment,
            )
            for relation in forbidden_relations
        )
        for candidate_relation in active_candidate_relations
    )

    control_graph: dict[str, set[str]] = defaultdict(set)
    for relation in active_candidate_relations:
        if relation.relation_type in {RelationType.PRECEDES, RelationType.BRANCHES_TO}:
            control_graph[relation.source_id].add(relation.target_id)
    active_order = [
        order
        for order in contract.partial_order
        if _active(order.active_when, assignment, failures, "partial-order constraint")
    ]
    order_hits = 0
    for order in active_order:
        before_candidates = alignment.candidate_ids_for(order.before_id)
        after_candidates = alignment.candidate_ids_for(order.after_id)
        if any(
            _reachable(control_graph, before, after)
            for before in before_candidates
            for after in after_candidates
        ):
            order_hits += 1

    candidate_predicates = {
        predicate.predicate_id: predicate.expression for predicate in candidate.branch_predicates
    }
    branch_total = 0
    branch_hits = 0
    for expected_predicate in contract.branch_predicates:
        aligned_predicate_ids = alignment.candidate_predicate_ids_for(
            expected_predicate.predicate_id
        )
        candidate_expression = next(
            (candidate_predicates[candidate_id] for candidate_id in sorted(aligned_predicate_ids)),
            None,
        )
        for predicate_probe in expected_predicate.probes:
            branch_total += 1
            if candidate_expression is None:
                # An omitted or unaligned predicate is an ordinary model error, not an
                # evaluator failure.  It earns zero for this probe and remains in the ITT
                # denominator.
                continue
            try:
                if (
                    evaluate_expression(candidate_expression, predicate_probe.assignment)
                    is predicate_probe.expected
                ):
                    branch_hits += 1
            except ExpressionError as exc:
                failures.append(f"branch predicate {expected_predicate.predicate_id}: {exc}")

    valid_paths = 0
    terminal_hits: set[str] = set()
    contract_kinds = {concept.concept_id: concept.kind for concept in contract.concepts}
    control_kinds = {ConceptKind.PROCESS_STEP, ConceptKind.DECISION, ConceptKind.OUTCOME}
    for path_probe in contract.path_probes:
        active_candidate_ids = {
            concept.concept_id
            for concept in candidate.concepts
            if _active(
                concept.active_when,
                path_probe.assignment,
                failures,
                f"path {path_probe.probe_id} concept {concept.concept_id}",
            )
        }
        active_mapped = {
            contract_id
            for candidate_id in active_candidate_ids
            for contract_id in alignment.concept_map.get(candidate_id, frozenset())
        }
        path_graph: dict[str, set[str]] = defaultdict(set)
        for relation in candidate.relations:
            if (
                relation.relation_type in {RelationType.PRECEDES, RelationType.BRANCHES_TO}
                and relation.source_id in active_candidate_ids
                and relation.target_id in active_candidate_ids
                and _active(
                    relation.active_when,
                    path_probe.assignment,
                    failures,
                    f"path {path_probe.probe_id} relation {relation.relation_id}",
                )
            ):
                path_graph[relation.source_id].add(relation.target_id)

        accepted_candidate_terminals = {
            candidate_id
            for candidate_id in candidate.terminal_outcome_ids
            if candidate_id in active_candidate_ids
            and alignment.concept_map.get(candidate_id, frozenset()).intersection(
                path_probe.accepted_terminal_outcomes
            )
        }
        required_control_ids = {
            contract_id
            for contract_id in path_probe.required_concept_ids
            if contract_kinds[contract_id] in control_kinds
            and contract_kinds[contract_id] is not ConceptKind.OUTCOME
        }
        reachable_terminals = {
            terminal_id
            for terminal_id in accepted_candidate_terminals
            if all(
                any(
                    candidate_id in active_candidate_ids
                    and _reachable(path_graph, candidate_id, terminal_id)
                    for candidate_id in alignment.candidate_ids_for(contract_id)
                )
                for contract_id in required_control_ids
            )
        }
        terminal_ok = bool(reachable_terminals)
        for terminal_id in reachable_terminals:
            terminal_hits.update(
                alignment.concept_map.get(terminal_id, frozenset()).intersection(
                    path_probe.accepted_terminal_outcomes
                )
            )
        if (
            set(path_probe.required_concept_ids).issubset(active_mapped)
            and not set(path_probe.inactive_concept_ids).intersection(active_mapped)
            and terminal_ok
        ):
            valid_paths += 1

    node_recall = _ratio(required_node_hits, len(required_ids))
    node_precision = _ratio(supported_candidate_nodes, len(active_candidates))
    edge_recall = _ratio(required_relation_hits, len(required_relations))
    edge_precision = _ratio(
        supported_candidate_relations,
        len(active_candidate_relations),
    )
    metrics = {
        "required_node_recall": node_recall,
        "required_node_precision": node_precision,
        "required_node_f1": _f1(node_precision, node_recall),
        "required_edge_recall": edge_recall,
        "required_edge_precision": edge_precision,
        "required_edge_f1": _f1(edge_precision, edge_recall),
        "partial_order_accuracy": _ratio(order_hits, len(active_order)),
        "branch_predicate_accuracy": _ratio(branch_hits, branch_total),
        "valid_path_rate": _ratio(valid_paths, len(contract.path_probes)),
        "terminal_outcome_coverage": _ratio(
            len(terminal_hits),
            len(
                {
                    outcome
                    for probe in contract.path_probes
                    for outcome in probe.accepted_terminal_outcomes
                }
            ),
        ),
        "forbidden_concept_violation_rate": _ratio(
            forbidden_concept_violations, len(active_candidates), empty=0.0
        ),
        "forbidden_relation_violation_rate": _ratio(
            forbidden_relation_violations, len(active_candidate_relations), empty=0.0
        ),
        "critical_step_omission": sum(
            active_contract[concept_id].criticality
            for concept_id in required_ids.difference(covered_contract)
        ),
    }
    counts = {
        "required_nodes": len(required_ids),
        "required_node_hits": required_node_hits,
        "candidate_nodes": len(active_candidates),
        "required_relations": len(required_relations),
        "required_relation_hits": required_relation_hits,
        "candidate_relations": len(active_candidate_relations),
        "forbidden_concept_violations": forbidden_concept_violations,
        "forbidden_relation_violations": forbidden_relation_violations,
        "branch_probe_total": branch_total,
        "branch_probe_hits": branch_hits,
        "path_probe_total": len(contract.path_probes),
        "valid_paths": valid_paths,
    }
    return ProcessScore(metrics=metrics, counts=counts, failures=tuple(dict.fromkeys(failures)))
