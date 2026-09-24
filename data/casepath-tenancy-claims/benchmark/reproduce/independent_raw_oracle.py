"""Independent executable oracle for the frozen synthetic claim state.

This module deliberately does not import the autonomous compiler, its helpers,
or any scorer.  It interprets the typed raw graph and checklist directly.  The
audit runner may later compare this independent result with compiled contracts
and scorer behavior.
"""

from __future__ import annotations

import ast
import itertools
import re
from collections import defaultdict, deque
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from contracts.schema import (
    CandidateArtifact,
    CandidateBranchPredicate,
    CandidateConcept,
    CandidateDocument,
    CandidateRelation,
    ConceptKind,
    DocumentState,
    RelationType,
    RequestMode,
)
from manifests.digests import digest_json

_DOCUMENT_CONDITION = re.compile(r"^scenario flag '([a-z][a-z0-9_]*)' is active$")
DocumentExpectation = Literal[
    "provided_sufficient",
    "provided_insufficient",
    "missing",
    "conditional",
    "irrelevant",
]


class RawOracleError(ValueError):
    """Raw generator state is not executable under the frozen audit semantics."""


@dataclass(frozen=True)
class RawNode:
    node_id: str
    label: str
    kind: ConceptKind


@dataclass(frozen=True)
class RawEdge:
    edge_id: str
    source_id: str
    target_id: str
    expression: str
    conditional: bool


@dataclass(frozen=True)
class RawDocument:
    checklist_item_id: str
    document_type: str
    label: str
    requirement_class: Literal["mandatory", "conditional", "optional", "irrelevant"]
    required_at_node_ids: tuple[str, ...]
    condition_expression: str
    actual_condition_triggered: bool
    expected_state: DocumentExpectation


@dataclass(frozen=True)
class RawAssignmentOutcome:
    assignment: tuple[tuple[str, bool], ...]
    reached_node_ids: tuple[str, ...]
    traversed_edge_ids: tuple[str, ...]
    terminal_node_id: str
    active_checklist_item_ids: tuple[str, ...]
    active_obligation_item_ids: tuple[str, ...]

    def assignment_dict(self) -> dict[str, bool]:
        return dict(self.assignment)


@dataclass(frozen=True)
class RawOracleCase:
    case_id: str
    family_id: str
    scenario_template_id: str
    process_graph_id: str
    start_node_id: str
    nodes: tuple[RawNode, ...]
    edges: tuple[RawEdge, ...]
    documents: tuple[RawDocument, ...]
    scenario_names: tuple[str, ...]
    actual_assignment: tuple[tuple[str, bool], ...]
    outcomes: tuple[RawAssignmentOutcome, ...]
    expected_claim_category: str
    expected_subcategory: str
    expected_next_action: dict[str, Any]
    expected_current_process_state: dict[str, Any]

    @property
    def actual_assignment_dict(self) -> dict[str, bool]:
        return dict(self.actual_assignment)

    @property
    def actual_outcome(self) -> RawAssignmentOutcome:
        for outcome in self.outcomes:
            if outcome.assignment == self.actual_assignment:
                return outcome
        raise RawOracleError(f"actual assignment is absent for {self.case_id}")


def evaluate_boolean(expression: str, assignment: Mapping[str, bool]) -> bool:
    """Evaluate the audit's intentionally tiny Boolean language."""

    normalized = re.sub(r"\btrue\b", "True", expression, flags=re.IGNORECASE)
    normalized = re.sub(r"\bfalse\b", "False", normalized, flags=re.IGNORECASE)
    try:
        tree = ast.parse(normalized, mode="eval")
    except SyntaxError as exc:
        raise RawOracleError(f"invalid Boolean expression: {expression}") from exc

    def visit(node: ast.AST) -> bool:
        if isinstance(node, ast.Constant) and type(node.value) is bool:
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in assignment:
                raise RawOracleError(f"missing Boolean assignment: {node.id}")
            return assignment[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not visit(node.operand)
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
            return all(visit(value) for value in node.values)
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
            return any(visit(value) for value in node.values)
        raise RawOracleError(f"unsupported Boolean node: {type(node).__name__}")

    return visit(tree.body)


def expression_names(expression: str) -> frozenset[str]:
    normalized = re.sub(r"\btrue\b", "True", expression, flags=re.IGNORECASE)
    normalized = re.sub(r"\bfalse\b", "False", normalized, flags=re.IGNORECASE)
    try:
        tree = ast.parse(normalized, mode="eval")
    except SyntaxError as exc:
        raise RawOracleError(f"invalid Boolean expression: {expression}") from exc
    names = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id not in {"True", "False"}
    }
    # Evaluation validates the full node surface, including constant expressions.
    evaluate_boolean(expression, dict.fromkeys(names, False))
    return frozenset(names)


def enumerate_assignments(names: Iterable[str]) -> tuple[dict[str, bool], ...]:
    ordered = tuple(sorted(set(names)))
    return tuple(
        dict(zip(ordered, values, strict=True))
        for values in itertools.product((False, True), repeat=len(ordered))
    )


def _branch_expression(branch: Mapping[str, Any]) -> str:
    clauses: list[str] = []
    raw_clauses = branch.get("all_of")
    if not isinstance(raw_clauses, list) or not raw_clauses:
        raise RawOracleError("branch decision lacks typed clauses")
    for clause in raw_clauses:
        if not isinstance(clause, dict):
            raise RawOracleError("branch clause is not an object")
        flag = clause.get("fact_key")
        expected = clause.get("expected_value")
        if (
            clause.get("operator") != "equals"
            or not isinstance(flag, str)
            or not flag.isidentifier()
            or type(expected) is not bool
        ):
            raise RawOracleError("branch clause is not a Boolean flag equality")
        clauses.append(flag if expected else f"not {flag}")
    return " and ".join(clauses)


def _document_expression(item: Mapping[str, Any]) -> str:
    condition = item.get("condition")
    triggered = item.get("condition_triggered")
    if type(triggered) is not bool:
        raise RawOracleError("document condition_triggered is not Boolean")
    if condition is None:
        return "true" if triggered else "false"
    if not isinstance(condition, str):
        raise RawOracleError("document condition is not text")
    match = _DOCUMENT_CONDITION.fullmatch(condition)
    if match is None:
        raise RawOracleError(f"unsupported document condition: {condition}")
    return match.group(1)


def _document_state(
    document_type: str,
    *,
    actual_triggered: bool,
    reference: Mapping[str, Any],
) -> DocumentExpectation:
    partitions: tuple[tuple[str, DocumentExpectation], ...] = (
        ("satisfied_document_types", "provided_sufficient"),
        ("present_but_insufficient_document_types", "provided_insufficient"),
        ("physically_absent_document_types", "missing"),
    )
    matches = [
        state for field, state in partitions if document_type in set(reference.get(field, ()))
    ]
    if len(matches) > 1:
        raise RawOracleError(f"document state partitions overlap for {document_type}")
    if matches:
        return matches[0]
    return "irrelevant" if actual_triggered else "conditional"


def _traverse(
    *,
    start_node_id: str,
    terminal_node_ids: frozenset[str],
    nodes: frozenset[str],
    edges: tuple[RawEdge, ...],
    assignment: Mapping[str, bool],
) -> tuple[tuple[str, ...], tuple[str, ...], str]:
    by_source: dict[str, list[RawEdge]] = defaultdict(list)
    for edge in edges:
        by_source[edge.source_id].append(edge)
    queue = deque([start_node_id])
    reached: list[str] = []
    reached_set: set[str] = set()
    traversed: list[str] = []
    while queue:
        source = queue.popleft()
        if source in reached_set:
            continue
        if source not in nodes:
            raise RawOracleError(f"graph reaches unknown node {source}")
        reached.append(source)
        reached_set.add(source)
        outgoing = by_source.get(source, ())
        conditional = [edge for edge in outgoing if edge.conditional]
        selected_conditional = [
            edge for edge in conditional if evaluate_boolean(edge.expression, assignment)
        ]
        if conditional and len(selected_conditional) != 1:
            raise RawOracleError(
                f"reachable branch family at {source} selects {len(selected_conditional)} edges"
            )
        enabled_edges = [
            edge for edge in outgoing if not edge.conditional or edge in selected_conditional
        ]
        if len(enabled_edges) > 1:
            raise RawOracleError(f"reachable node {source} has multiple enabled successors")
        for edge in enabled_edges:
            traversed.append(edge.edge_id)
            queue.append(edge.target_id)
    terminals = reached_set.intersection(terminal_node_ids)
    if len(terminals) != 1:
        raise RawOracleError(f"assignment reaches {len(terminals)} terminals")
    return tuple(reached), tuple(traversed), next(iter(terminals))


def _validate_state_and_derive_action(
    *,
    process_graph: Mapping[str, Any],
    start_node_id: str,
    edges: tuple[RawEdge, ...],
    nodes: tuple[RawNode, ...],
    documents: tuple[RawDocument, ...],
    actual_outcome: RawAssignmentOutcome,
    current_process_state: Mapping[str, Any],
    expected_next_action: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate the raw state snapshot and derive its permitted next action."""

    outgoing = tuple(edge for edge in edges if edge.source_id == start_node_id)
    expected_state = dict(current_process_state)
    if expected_state.get("contract") != "casepath.current-process-state/1.0.0":
        raise RawOracleError("current process state has an unknown contract")
    if expected_state.get("process_graph_id") != process_graph.get("process_graph_id"):
        raise RawOracleError("current process state references another graph")
    if expected_state.get("as_of_sequence") != 1 or expected_state.get("state") != "submitted":
        raise RawOracleError("current process state is not the frozen intake snapshot")
    if expected_state.get("completed_node_ids") != []:
        raise RawOracleError("intake snapshot unexpectedly contains completed nodes")
    if expected_state.get("current_node_ids") != [start_node_id]:
        raise RawOracleError("intake snapshot does not start at the graph start node")
    if set(expected_state.get("next_node_ids", ())) != {edge.target_id for edge in outgoing}:
        raise RawOracleError("intake next nodes differ from raw graph successors")
    if set(expected_state.get("unresolved_branch_edge_ids", ())) != {
        edge.edge_id for edge in outgoing if edge.conditional
    }:
        raise RawOracleError("intake unresolved branches differ from raw graph")

    action = dict(expected_next_action)
    if action.get("as_of_sequence") != 2:
        raise RawOracleError("next action is not the event after the intake snapshot")
    if action.get("supporting_artifact_ids") != expected_state.get("source_artifact_ids"):
        raise RawOracleError("next action does not bind the intake source artifacts")
    arguments = action.get("arguments")
    if not isinstance(arguments, dict):
        raise RawOracleError("next action arguments are malformed")
    action_key = action.get("action_key")
    if action_key == "request_required_document":
        active_obligations = set(actual_outcome.active_obligation_item_ids)
        first_unmet = next(
            (item for item in documents if item.checklist_item_id in active_obligations),
            None,
        )
        if first_unmet is None:
            raise RawOracleError("document request has no active unmet requirement")
        expected_arguments = {
            "document_type": first_unmet.document_type,
            "requirement_class": first_unmet.requirement_class,
        }
        if arguments != expected_arguments or action.get("actor_role") != "claim_handler":
            raise RawOracleError("document request is not the first active unmet requirement")
    elif action_key == "execute_process_step":
        process_node_id = arguments.get("process_node_id")
        node_by_id = {node.node_id: node for node in nodes}
        if (
            not isinstance(process_node_id, str)
            or process_node_id not in expected_state.get("next_node_ids", ())
            or process_node_id not in actual_outcome.reached_node_ids
            or process_node_id not in node_by_id
            or arguments.get("action") != node_by_id[process_node_id].label
        ):
            raise RawOracleError("next process step is not the active raw graph successor")
        expected_actor = (
            "external_specialist" if process_node_id.endswith("_safety") else "claim_handler"
        )
        if action.get("actor_role") != expected_actor:
            raise RawOracleError("next process step has an inconsistent actor")
    else:
        raise RawOracleError(f"unsupported next action: {action_key}")
    return expected_state, action


def build_raw_oracle(
    *,
    case_id: str,
    process_graph: Mapping[str, Any],
    document_checklist: Mapping[str, Any],
    reference_answer: Mapping[str, Any],
    canonical_claim: Mapping[str, Any],
    expected_next_action: Mapping[str, Any],
    current_process_state: Mapping[str, Any],
    hidden_subcategory: str,
) -> RawOracleCase:
    """Execute one raw evaluator row without consulting compiled artifacts."""

    graph_case_id = reference_answer.get("claim_id")
    if graph_case_id != case_id:
        raise RawOracleError("reference answer belongs to another case")
    raw_nodes = process_graph.get("nodes")
    raw_edges = process_graph.get("edges")
    raw_branches = process_graph.get("branch_decisions")
    raw_items = document_checklist.get("items")
    if (
        not isinstance(raw_nodes, list)
        or not isinstance(raw_edges, list)
        or not isinstance(raw_branches, list)
        or not isinstance(raw_items, list)
    ):
        raise RawOracleError("raw graph or checklist collections are malformed")

    branch_expression_by_edge: dict[str, str] = {}
    branch_sources: set[str] = set()
    edge_source_by_id = {
        edge["edge_id"]: edge["source_node_id"] for edge in raw_edges if isinstance(edge, dict)
    }
    for branch in raw_branches:
        if not isinstance(branch, dict):
            raise RawOracleError("branch decision is not an object")
        edge_id = branch.get("edge_id")
        if not isinstance(edge_id, str) or edge_id not in edge_source_by_id:
            raise RawOracleError("branch decision references an unknown edge")
        branch_expression_by_edge[edge_id] = _branch_expression(branch)
        branch_sources.add(edge_source_by_id[edge_id])

    terminal_ids = frozenset(process_graph.get("terminal_node_ids", ()))
    nodes = tuple(
        RawNode(
            node_id=node["node_id"],
            label=node["name"],
            kind=(
                ConceptKind.OUTCOME
                if node["node_id"] in terminal_ids
                else ConceptKind.DECISION
                if node["node_id"] in branch_sources
                else ConceptKind.PROCESS_STEP
            ),
        )
        for node in raw_nodes
        if isinstance(node, dict)
    )
    node_ids = frozenset(node.node_id for node in nodes)
    if len(nodes) != len(raw_nodes) or len(node_ids) != len(nodes):
        raise RawOracleError("graph nodes are malformed or repeated")
    edges = tuple(
        RawEdge(
            edge_id=edge["edge_id"],
            source_id=edge["source_node_id"],
            target_id=edge["target_node_id"],
            expression=branch_expression_by_edge.get(edge["edge_id"], "true"),
            conditional=edge["edge_id"] in branch_expression_by_edge,
        )
        for edge in raw_edges
        if isinstance(edge, dict)
    )
    if len(edges) != len(raw_edges) or len({edge.edge_id for edge in edges}) != len(edges):
        raise RawOracleError("graph edges are malformed or repeated")
    if any(edge.source_id not in node_ids or edge.target_id not in node_ids for edge in edges):
        raise RawOracleError("graph edge has an unknown endpoint")

    documents = tuple(
        RawDocument(
            checklist_item_id=item["checklist_item_id"],
            document_type=item["document_type"],
            label=item["label"],
            requirement_class=item["requirement_class"],
            required_at_node_ids=tuple(item["required_at_node_ids"]),
            condition_expression=_document_expression(item),
            actual_condition_triggered=item["condition_triggered"],
            expected_state=_document_state(
                item["document_type"],
                actual_triggered=item["condition_triggered"],
                reference=reference_answer,
            ),
        )
        for item in raw_items
        if isinstance(item, dict)
    )
    if len(documents) != len(raw_items):
        raise RawOracleError("checklist items are malformed")
    if any(not set(item.required_at_node_ids).issubset(node_ids) for item in documents):
        raise RawOracleError("checklist item cites an unknown process node")

    scenario_names = tuple(
        sorted(
            set().union(
                *(expression_names(edge.expression) for edge in edges if edge.conditional),
                *(expression_names(item.condition_expression) for item in documents),
            )
        )
    )
    case_specification = canonical_claim.get("hidden_ground_truth", {}).get(
        "case_specification", {}
    )
    active_flags = set(case_specification.get("active_flags", ()))
    actual_assignment = tuple((name, name in active_flags) for name in scenario_names)
    assignments = enumerate_assignments(scenario_names)
    outcomes: list[RawAssignmentOutcome] = []
    start = process_graph.get("start_node_id")
    if not isinstance(start, str):
        raise RawOracleError("graph start node is missing")
    for assignment in assignments:
        reached, traversed, terminal = _traverse(
            start_node_id=start,
            terminal_node_ids=terminal_ids,
            nodes=node_ids,
            edges=edges,
            assignment=assignment,
        )
        active_documents = {
            item.checklist_item_id
            for item in documents
            if evaluate_boolean(item.condition_expression, assignment)
            and set(item.required_at_node_ids).issubset(reached)
        }
        obligations = {
            item.checklist_item_id
            for item in documents
            if item.checklist_item_id in active_documents
            and item.requirement_class not in {"optional", "irrelevant"}
            and item.expected_state != "provided_sufficient"
        }
        outcomes.append(
            RawAssignmentOutcome(
                assignment=tuple(sorted(assignment.items())),
                reached_node_ids=reached,
                traversed_edge_ids=traversed,
                terminal_node_id=terminal,
                active_checklist_item_ids=tuple(sorted(active_documents)),
                active_obligation_item_ids=tuple(sorted(obligations)),
            )
        )

    actual_outcome = next(
        outcome for outcome in outcomes if outcome.assignment == actual_assignment
    )
    process_state, next_action = _validate_state_and_derive_action(
        process_graph=process_graph,
        start_node_id=start,
        edges=edges,
        nodes=nodes,
        documents=documents,
        actual_outcome=actual_outcome,
        current_process_state=current_process_state,
        expected_next_action=expected_next_action,
    )
    oracle = RawOracleCase(
        case_id=case_id,
        family_id=process_graph["near_duplicate_group_id"],
        scenario_template_id=process_graph["scenario_template_id"],
        process_graph_id=process_graph["process_graph_id"],
        start_node_id=start,
        nodes=nodes,
        edges=edges,
        documents=documents,
        scenario_names=scenario_names,
        actual_assignment=actual_assignment,
        outcomes=tuple(outcomes),
        expected_claim_category=str(reference_answer["expected_claim_category"]),
        expected_subcategory=hidden_subcategory,
        expected_next_action=next_action,
        expected_current_process_state=process_state,
    )
    actual = oracle.actual_outcome
    expected_path = tuple(reference_answer["expected_process_path_node_ids"])
    if actual.reached_node_ids != expected_path:
        raise RawOracleError("raw executor does not reproduce the frozen actual path")
    raw_actual_path = process_graph.get("actual_path")
    if not isinstance(raw_actual_path, list) or any(
        not isinstance(item, dict) for item in raw_actual_path
    ):
        raise RawOracleError("raw graph actual path is malformed")
    if tuple(item.get("node_id") for item in raw_actual_path) != actual.reached_node_ids:
        raise RawOracleError("raw graph actual node sequence differs from execution")
    if (
        tuple(item.get("edge_id_from_previous") for item in raw_actual_path[1:])
        != actual.traversed_edge_ids
    ):
        raise RawOracleError("raw graph actual edge sequence differs from execution")
    if actual.terminal_node_id != process_graph.get("reached_terminal_node_id"):
        raise RawOracleError("raw executor does not reproduce the frozen terminal")
    return oracle


def _activation_expression(
    oracle: RawOracleCase,
    predicate: Callable[[RawAssignmentOutcome], bool],
) -> str:
    satisfying = [outcome.assignment_dict() for outcome in oracle.outcomes if predicate(outcome)]
    if not satisfying:
        return "false"
    if len(satisfying) == len(oracle.outcomes):
        return "true"
    terms = []
    for assignment in satisfying:
        clauses = [name if assignment[name] else f"not {name}" for name in oracle.scenario_names]
        terms.append(f"({' and '.join(clauses)})" if clauses else "true")
    return " or ".join(terms)


def _chain_ids(checklist_item_id: str) -> tuple[str, str, str, str]:
    suffix = checklist_item_id.removeprefix("chk_")
    return (
        f"oracle.decision.{suffix}",
        f"oracle.fact.{suffix}",
        f"oracle.capability.{suffix}",
        f"oracle.document.{suffix}",
    )


def build_raw_oracle_candidate(oracle: RawOracleCase) -> CandidateArtifact:
    """Build a scorer input only from independently executed raw state."""

    node_active: dict[str, str] = {}
    for node in oracle.nodes:
        node_id = node.node_id

        def has_node(outcome: RawAssignmentOutcome, node_id: str = node_id) -> bool:
            return node_id in outcome.reached_node_ids

        node_active[node_id] = _activation_expression(oracle, has_node)
    document_active: dict[str, str] = {}
    for item in oracle.documents:
        item_id = item.checklist_item_id

        def has_document(outcome: RawAssignmentOutcome, item_id: str = item_id) -> bool:
            return item_id in outcome.active_checklist_item_ids

        document_active[item_id] = _activation_expression(oracle, has_document)
    concepts: list[CandidateConcept] = [
        CandidateConcept(
            concept_id=f"oracle.node.{node.node_id}",
            kind=node.kind,
            label=node.label,
            active_when=node_active[node.node_id],
        )
        for node in oracle.nodes
    ]
    relations: list[CandidateRelation] = [
        CandidateRelation(
            relation_id=f"oracle.edge.{edge.edge_id}",
            relation_type=(RelationType.BRANCHES_TO if edge.conditional else RelationType.PRECEDES),
            source_id=f"oracle.node.{edge.source_id}",
            target_id=f"oracle.node.{edge.target_id}",
            active_when=edge.expression,
        )
        for edge in oracle.edges
    ]
    documents: list[CandidateDocument] = []
    actual_obligations = set(oracle.actual_outcome.active_obligation_item_ids)
    for item in oracle.documents:
        if item.requirement_class in {"optional", "irrelevant"}:
            continue
        decision_id, fact_id, capability_id, document_id = _chain_ids(item.checklist_item_id)
        active_when = document_active[item.checklist_item_id]
        concepts.extend(
            (
                CandidateConcept(
                    concept_id=decision_id,
                    kind=ConceptKind.DECISION,
                    label=f"Decide whether {item.label} is needed",
                    active_when=active_when,
                ),
                CandidateConcept(
                    concept_id=fact_id,
                    kind=ConceptKind.FACT,
                    label=f"Evidence state for {item.label}",
                    active_when=active_when,
                ),
                CandidateConcept(
                    concept_id=capability_id,
                    kind=ConceptKind.EVIDENCE_CAPABILITY,
                    label=f"Evidence capable of resolving {item.label}",
                    active_when=active_when,
                ),
            )
        )
        for required_node_id in item.required_at_node_ids:
            relations.append(
                CandidateRelation(
                    relation_id=f"oracle.{item.checklist_item_id}.at.{required_node_id}",
                    relation_type=RelationType.PRECEDES,
                    source_id=f"oracle.node.{required_node_id}",
                    target_id=decision_id,
                    active_when=active_when,
                )
            )
        relations.extend(
            (
                CandidateRelation(
                    relation_id=f"oracle.{item.checklist_item_id}.requires_fact",
                    relation_type=RelationType.REQUIRES_FACT,
                    source_id=decision_id,
                    target_id=fact_id,
                    active_when=active_when,
                ),
                CandidateRelation(
                    relation_id=f"oracle.{item.checklist_item_id}.supported_by",
                    relation_type=RelationType.SUPPORTED_BY,
                    source_id=fact_id,
                    target_id=capability_id,
                    active_when=active_when,
                ),
                CandidateRelation(
                    relation_id=f"oracle.{item.checklist_item_id}.satisfied_by",
                    relation_type=RelationType.SATISFIED_BY,
                    source_id=capability_id,
                    target_id=f"oracle.request.{item.checklist_item_id.removeprefix('chk_')}",
                    active_when=active_when,
                ),
            )
        )
        documents.append(
            CandidateDocument(
                item_id=f"oracle.request.{item.checklist_item_id.removeprefix('chk_')}",
                document_id=document_id,
                label=item.label,
                state=DocumentState(item.expected_state),
                request_mode=(
                    RequestMode.NOW
                    if item.checklist_item_id in actual_obligations
                    else RequestMode.NONE
                ),
                active_when=active_when,
            )
        )
    candidate = CandidateArtifact(
        artifact_version="casepath.candidate-artifact/0.1.0",
        case_id=oracle.case_id,
        concepts=tuple(concepts),
        relations=tuple(relations),
        branch_predicates=tuple(
            CandidateBranchPredicate(
                predicate_id=f"oracle.predicate.{edge.edge_id}",
                expression=edge.expression,
            )
            for edge in oracle.edges
            if edge.conditional
        ),
        documents=tuple(documents),
        terminal_outcome_ids=tuple(
            f"oracle.node.{node.node_id}"
            for node in oracle.nodes
            if node.kind is ConceptKind.OUTCOME
        ),
    )
    # Force deterministic serialization while the object is still close to raw state.
    digest_json(candidate.model_dump(mode="json"))
    return candidate


__all__ = [
    "RawAssignmentOutcome",
    "RawDocument",
    "RawEdge",
    "RawNode",
    "RawOracleCase",
    "RawOracleError",
    "build_raw_oracle",
    "build_raw_oracle_candidate",
    "enumerate_assignments",
    "evaluate_boolean",
    "expression_names",
]
