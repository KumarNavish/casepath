"""Independent fatal-gate evaluator for CasePath-Bench-v3.

This implementation is deliberately separate from :mod:`scorers`.  It does
not import, wrap, or call the production evaluator.  Release verification can
therefore use it as a second implementation of the frozen fatal endpoints.

The contract's eight fatal metrics determine ``fatal_gates_accepted``.  Exact
source support is an additional release-integrity check because provenance is
scored but is not one of the frozen model-performance gates.  ``accepted`` is
true only when both checks pass.
"""

from __future__ import annotations

import ast
import re
from collections import defaultdict, deque
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal

from contracts.schema import (
    AcceptanceContract,
    CandidateArtifact,
    CandidateBranchPredicate,
    CandidateConcept,
    CandidateDocument,
    CandidateRelation,
    ConceptKind,
    DocumentState,
    EvidenceContract,
    LocatorKind,
    RelationType,
    RequestMode,
    Requirement,
    SourceLocator,
)

INDEPENDENT_EVALUATOR_VERSION = "casepath-independent-evaluator/3.0.0"
INDEPENDENT_AUDIT_VERSION = "casepath-independent-evaluator-audit/3.0.0"
REPORTED_ENDPOINTS_V3 = frozenset(
    {
        "valid_path_rate",
        "branch_predicate_accuracy",
        "required_node_recall",
        "required_edge_recall",
        "critical_evidence_recall",
        "unnecessary_document_rate",
        "document_state_accuracy",
        "valid_chain_precision",
        "fact_chain_completeness",
        "evidence_obligation_completeness",
        "exact_source_support_rate",
        "exact_source_span_rate",
        "provenance_chain_inheritance_rate",
        "traceability_exactness",
    }
)
FATAL_METRICS = frozenset(
    {
        "valid_path_rate",
        "required_node_recall",
        "required_edge_recall",
        "branch_predicate_accuracy",
        "evidence_obligation_completeness",
        "document_state_accuracy",
        "unnecessary_document_rate",
        "forbidden_concept_violation_rate",
    }
)


class IndependentEvaluationError(ValueError):
    """The independent evaluator cannot safely interpret an input."""


@dataclass(frozen=True)
class IndependentGateResultV3:
    gate_id: str
    metric: str
    comparator: Literal[">=", "<=", ">", "<", "=="]
    threshold: float
    observed: float | None
    fatal: bool
    passed: bool


@dataclass(frozen=True)
class IndependentEvaluationReceiptV3:
    evaluator_version: str
    case_id: str
    metrics: dict[str, float]
    gates: tuple[IndependentGateResultV3, ...]
    evaluation_failures: tuple[str, ...]
    fatal_gates_accepted: bool
    source_grounding_passed: bool
    accepted: bool


@dataclass(frozen=True)
class IndependentCaseAuditV3:
    case_id: str
    reported_endpoints_complete: bool
    reference_candidate_accepted: bool
    semantic_attack_attempt_count: int
    semantic_attack_kill_count: int
    grounding_attack_attempt_count: int
    grounding_attack_kill_count: int
    empty_output_rejected: bool
    request_everything_rejected: bool


@dataclass(frozen=True)
class IndependentEvaluatorAuditReceiptV3:
    audit_version: str
    evaluator_version: str
    expected_case_count: int
    audited_case_count: int
    unique_case_count: int
    reported_endpoint_count: int
    reported_endpoint_complete_case_count: int
    reference_candidate_accepted_count: int
    semantic_attack_attempt_count: int
    semantic_attack_kill_count: int
    grounding_attack_attempt_count: int
    grounding_attack_kill_count: int
    empty_output_rejected_count: int
    request_everything_rejected_count: int
    cases: tuple[IndependentCaseAuditV3, ...]
    failures: tuple[str, ...]
    eligible: bool


@dataclass(frozen=True)
class _Alignment:
    concepts: dict[str, frozenset[str]]
    documents: dict[str, frozenset[str]]
    predicates: dict[str, frozenset[str]]

    @property
    def endpoints(self) -> dict[str, frozenset[str]]:
        return {**self.concepts, **self.documents}

    def candidate_endpoints_for(self, contract_id: str) -> frozenset[str]:
        return frozenset(
            candidate_id
            for candidate_id, targets in self.endpoints.items()
            if contract_id in targets
        )


class _ExpressionFailure(ValueError):
    pass


def _normalise_expression(expression: str) -> str:
    value = expression.strip()
    if not value:
        raise _ExpressionFailure("empty expression")
    for source, target in (("true", "True"), ("false", "False"), ("null", "None")):
        value = re.sub(rf"\b{source}\b", target, value, flags=re.IGNORECASE)
    return value


def _expression_value(node: ast.AST, assignment: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in assignment:
            raise _ExpressionFailure(f"missing variable {node.id}")
        return assignment[node.id]
    if isinstance(node, ast.List):
        return [_expression_value(item, assignment) for item in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_expression_value(item, assignment) for item in node.elts)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not bool(_expression_value(node.operand, assignment))
    if isinstance(node, ast.BoolOp):
        values = (_expression_value(item, assignment) for item in node.values)
        if isinstance(node.op, ast.And):
            return all(bool(item) for item in values)
        if isinstance(node.op, ast.Or):
            return any(bool(item) for item in values)
    if isinstance(node, ast.Compare):
        left = _expression_value(node.left, assignment)
        for operator, comparator_node in zip(node.ops, node.comparators, strict=True):
            right = _expression_value(comparator_node, assignment)
            if isinstance(operator, ast.Eq):
                matched = left == right
            elif isinstance(operator, ast.NotEq):
                matched = left != right
            elif isinstance(operator, ast.Lt):
                matched = left < right
            elif isinstance(operator, ast.LtE):
                matched = left <= right
            elif isinstance(operator, ast.Gt):
                matched = left > right
            elif isinstance(operator, ast.GtE):
                matched = left >= right
            elif isinstance(operator, ast.In):
                matched = left in right
            elif isinstance(operator, ast.NotIn):
                matched = left not in right
            elif isinstance(operator, ast.Is):
                matched = left is right
            elif isinstance(operator, ast.IsNot):
                matched = left is not right
            else:
                raise _ExpressionFailure(f"unsupported comparator {type(operator).__name__}")
            if not matched:
                return False
            left = right
        return True
    raise _ExpressionFailure(f"unsupported expression node {type(node).__name__}")


def _evaluate_expression(expression: str, assignment: dict[str, Any]) -> bool:
    try:
        tree = ast.parse(_normalise_expression(expression), mode="eval")
    except SyntaxError as exc:
        raise _ExpressionFailure(f"invalid syntax: {exc.msg}") from exc
    allowed = (
        ast.Expression,
        ast.BoolOp,
        ast.UnaryOp,
        ast.Compare,
        ast.Name,
        ast.Load,
        ast.Constant,
        ast.List,
        ast.Tuple,
        ast.And,
        ast.Or,
        ast.Not,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.In,
        ast.NotIn,
        ast.Is,
        ast.IsNot,
    )
    unexpected = next((node for node in ast.walk(tree) if not isinstance(node, allowed)), None)
    if unexpected is not None:
        raise _ExpressionFailure(f"unsafe node {type(unexpected).__name__}")
    try:
        return bool(_expression_value(tree.body, assignment))
    except (TypeError, ValueError) as exc:
        if isinstance(exc, _ExpressionFailure):
            raise
        raise _ExpressionFailure(f"invalid comparison: {exc}") from exc


def _active(
    expression: str,
    assignment: dict[str, Any],
    failures: list[str],
    identity: str,
) -> bool:
    try:
        return _evaluate_expression(expression, assignment)
    except _ExpressionFailure as exc:
        failures.append(f"{identity}: {exc}")
        return False


def _normalise_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _align(contract: AcceptanceContract, candidate: CandidateArtifact) -> _Alignment:
    specs = {item.concept_id: item for item in contract.concepts}
    label_targets: dict[tuple[ConceptKind, str], set[str]] = defaultdict(set)
    for concept_spec in contract.concepts:
        for label in (concept_spec.label, *concept_spec.aliases):
            label_targets[(concept_spec.kind, _normalise_label(label))].add(concept_spec.concept_id)
    variants: dict[str, set[str]] = defaultdict(set)
    for variant in contract.variants:
        for candidate_id in variant.candidate_concept_ids:
            variants[candidate_id].update(variant.contract_concept_ids)

    concept_map: dict[str, frozenset[str]] = {}
    for candidate_concept in candidate.concepts:
        targets: set[str] = set()
        exact = specs.get(candidate_concept.concept_id)
        if exact is not None and exact.kind is candidate_concept.kind:
            targets.add(exact.concept_id)
        targets.update(
            label_targets[(candidate_concept.kind, _normalise_label(candidate_concept.label))]
        )
        targets.update(variants[candidate_concept.concept_id])
        concept_map[candidate_concept.concept_id] = frozenset(targets)

    document_map: dict[str, frozenset[str]] = {}
    for candidate_document in candidate.documents:
        targets = set()
        exact = specs.get(candidate_document.document_id)
        if exact is not None and exact.kind is ConceptKind.DOCUMENT:
            targets.add(exact.concept_id)
        targets.update(
            label_targets[(ConceptKind.DOCUMENT, _normalise_label(candidate_document.label))]
        )
        targets.update(variants[candidate_document.document_id])
        document_map[candidate_document.item_id] = frozenset(targets)

    expected_predicates = {item.predicate_id: item for item in contract.branch_predicates}
    offered_predicates = {item.predicate_id: item for item in candidate.branch_predicates}
    exact_ids = expected_predicates.keys() & offered_predicates.keys()
    predicate_map = {item_id: frozenset({item_id}) for item_id in exact_ids}
    unmatched_expected = {
        item_id: item for item_id, item in expected_predicates.items() if item_id not in exact_ids
    }
    unmatched_offered = {
        item_id: item for item_id, item in offered_predicates.items() if item_id not in exact_ids
    }
    compatible: dict[str, set[str]] = {}
    for candidate_id, candidate_predicate in unmatched_offered.items():
        targets = set()
        for expected_id, expected in unmatched_expected.items():
            try:
                if all(
                    _evaluate_expression(candidate_predicate.expression, probe.assignment)
                    is probe.expected
                    for probe in expected.probes
                ):
                    targets.add(expected_id)
            except _ExpressionFailure:
                continue
        compatible[candidate_id] = targets
    reverse: dict[str, set[str]] = defaultdict(set)
    for candidate_id, targets in compatible.items():
        for target in targets:
            reverse[target].add(candidate_id)
    for candidate_id, targets in compatible.items():
        predicate_map[candidate_id] = (
            frozenset(targets)
            if len(targets) == 1 and len(reverse[next(iter(targets))]) == 1
            else frozenset()
        )
    return _Alignment(concept_map, document_map, predicate_map)


def _ratio(numerator: int | float, denominator: int | float, *, empty: float) -> float:
    return float(numerator / denominator) if denominator else empty


def _reachable(graph: dict[str, set[str]], start: str, end: str) -> bool:
    pending = deque((start,))
    visited: set[str] = set()
    while pending:
        current = pending.popleft()
        if current == end:
            return True
        if current not in visited:
            visited.add(current)
            pending.extend(graph.get(current, set()).difference(visited))
    return False


def _process_metrics(
    contract: AcceptanceContract,
    candidate: CandidateArtifact,
    alignment: _Alignment,
    failures: list[str],
) -> dict[str, float]:
    scenario = contract.scenario
    active_specs = {
        item.concept_id: item
        for item in contract.concepts
        if _active(item.active_when, scenario, failures, f"concept {item.concept_id}")
    }
    active_candidates = {
        item.concept_id
        for item in candidate.concepts
        if _active(item.active_when, scenario, failures, f"candidate concept {item.concept_id}")
    }
    covered = {
        target
        for candidate_id in active_candidates
        for target in alignment.concepts.get(candidate_id, frozenset())
    }
    required = {
        item_id
        for item_id, item in active_specs.items()
        if item.requirement is Requirement.MANDATORY
    }
    forbidden = {
        item_id
        for item_id, item in active_specs.items()
        if item.requirement is Requirement.FORBIDDEN
    }

    active_spec_relations = [
        item
        for item in contract.relations
        if _active(item.active_when, scenario, failures, f"relation {item.relation_id}")
    ]
    active_candidate_relations = [
        item
        for item in candidate.relations
        if _active(
            item.active_when,
            scenario,
            failures,
            f"candidate relation {item.relation_id}",
        )
    ]

    def relation_matches(spec: Any, offered: CandidateRelation) -> bool:
        return (
            spec.relation_type is offered.relation_type
            and spec.source_id in alignment.endpoints.get(offered.source_id, frozenset())
            and spec.target_id in alignment.endpoints.get(offered.target_id, frozenset())
        )

    required_relations = [
        item for item in active_spec_relations if item.requirement is Requirement.MANDATORY
    ]
    relation_hits = sum(
        any(relation_matches(spec, offered) for offered in active_candidate_relations)
        for spec in required_relations
    )

    candidate_predicates = {
        item.predicate_id: item.expression for item in candidate.branch_predicates
    }
    branch_hits = 0
    branch_total = 0
    for expected in contract.branch_predicates:
        aligned_ids = sorted(
            candidate_id
            for candidate_id, targets in alignment.predicates.items()
            if expected.predicate_id in targets
        )
        expression = candidate_predicates[aligned_ids[0]] if aligned_ids else None
        for predicate_probe in expected.probes:
            branch_total += 1
            if expression is None:
                continue
            try:
                observed = _evaluate_expression(expression, predicate_probe.assignment)
            except _ExpressionFailure as exc:
                failures.append(f"branch predicate {expected.predicate_id}: {exc}")
                continue
            if observed is predicate_probe.expected:
                branch_hits += 1

    kinds = {item.concept_id: item.kind for item in contract.concepts}
    control_kinds = {ConceptKind.PROCESS_STEP, ConceptKind.DECISION, ConceptKind.OUTCOME}
    valid_paths = 0
    for path_probe in contract.path_probes:
        active_ids = {
            item.concept_id
            for item in candidate.concepts
            if _active(
                item.active_when,
                path_probe.assignment,
                failures,
                f"path {path_probe.probe_id} concept {item.concept_id}",
            )
        }
        mapped = {
            target
            for candidate_id in active_ids
            for target in alignment.concepts.get(candidate_id, frozenset())
        }
        graph: dict[str, set[str]] = defaultdict(set)
        for relation in candidate.relations:
            if (
                relation.relation_type in {RelationType.PRECEDES, RelationType.BRANCHES_TO}
                and relation.source_id in active_ids
                and relation.target_id in active_ids
                and _active(
                    relation.active_when,
                    path_probe.assignment,
                    failures,
                    f"path {path_probe.probe_id} relation {relation.relation_id}",
                )
            ):
                graph[relation.source_id].add(relation.target_id)
        accepted_terminals = {
            item_id
            for item_id in candidate.terminal_outcome_ids
            if item_id in active_ids
            and alignment.concepts.get(item_id, frozenset()).intersection(
                path_probe.accepted_terminal_outcomes
            )
        }
        required_controls = {
            item_id
            for item_id in path_probe.required_concept_ids
            if kinds[item_id] in control_kinds and kinds[item_id] is not ConceptKind.OUTCOME
        }
        reachable_terminals = {
            terminal
            for terminal in accepted_terminals
            if all(
                any(
                    candidate_id in active_ids and _reachable(graph, candidate_id, terminal)
                    for candidate_id in alignment.candidate_endpoints_for(contract_id)
                )
                for contract_id in required_controls
            )
        }
        if (
            set(path_probe.required_concept_ids).issubset(mapped)
            and not set(path_probe.inactive_concept_ids).intersection(mapped)
            and reachable_terminals
        ):
            valid_paths += 1

    forbidden_violations = sum(
        bool(alignment.concepts.get(item_id, frozenset()).intersection(forbidden))
        for item_id in active_candidates
    )
    return {
        "required_node_recall": _ratio(
            len(required.intersection(covered)), len(required), empty=1.0
        ),
        "required_edge_recall": _ratio(relation_hits, len(required_relations), empty=1.0),
        "branch_predicate_accuracy": _ratio(branch_hits, branch_total, empty=1.0),
        "valid_path_rate": _ratio(valid_paths, len(contract.path_probes), empty=1.0),
        "forbidden_concept_violation_rate": _ratio(
            forbidden_violations, len(active_candidates), empty=0.0
        ),
    }


def _accepted_documents(evidence: EvidenceContract) -> set[str]:
    return {document for option in evidence.acceptable_document_sets for document in option}


def _evidence_metrics(
    contract: AcceptanceContract,
    candidate: CandidateArtifact,
    alignment: _Alignment,
    failures: list[str],
) -> dict[str, float]:
    scenario = contract.scenario
    active_obligations = [
        item
        for item in contract.evidence_contracts
        if _active(
            item.active_when,
            scenario,
            failures,
            f"evidence contract {item.evidence_contract_id}",
        )
    ]
    active_concepts = {
        item.concept_id
        for item in candidate.concepts
        if _active(item.active_when, scenario, failures, f"candidate concept {item.concept_id}")
    }
    active_documents = [
        item
        for item in candidate.documents
        if _active(item.active_when, scenario, failures, f"candidate document {item.item_id}")
    ]
    requested = [item for item in active_documents if item.request_mode is not RequestMode.NONE]
    active_relations = [
        item
        for item in candidate.relations
        if _active(
            item.active_when,
            scenario,
            failures,
            f"candidate relation {item.relation_id}",
        )
    ]

    def candidates_for(contract_id: str) -> set[str]:
        return set(alignment.candidate_endpoints_for(contract_id)).intersection(active_concepts)

    def has_edge(kind: RelationType, sources: set[str], targets: set[str]) -> bool:
        return any(
            item.relation_type is kind and item.source_id in sources and item.target_id in targets
            for item in active_relations
        )

    requested_contract_documents = {
        contract_id
        for document in requested
        for contract_id in alignment.documents.get(document.item_id, frozenset())
    }
    covered_obligation_ids: set[str] = set()
    valid_obligation_ids: set[str] = set()
    valid_chain_items: set[str] = set()
    facts_with_valid_chain: set[str] = set()
    for evidence in active_obligations:
        if any(
            set(option).issubset(requested_contract_documents)
            for option in evidence.acceptable_document_sets
        ):
            covered_obligation_ids.add(evidence.evidence_contract_id)
        decisions = {
            candidate_id
            for decision_id in evidence.decision_ids
            for candidate_id in candidates_for(decision_id)
        }
        facts = candidates_for(evidence.fact_id)
        capabilities = {
            candidate_id
            for capability_id in evidence.required_capability_ids
            for candidate_id in candidates_for(capability_id)
        }
        valid_items: set[str] = set()
        if has_edge(RelationType.REQUIRES_FACT, decisions, facts) and has_edge(
            RelationType.SUPPORTED_BY, facts, capabilities
        ):
            for document in requested:
                if not alignment.documents.get(document.item_id, frozenset()).intersection(
                    _accepted_documents(evidence)
                ):
                    continue
                if has_edge(RelationType.SATISFIED_BY, capabilities, {document.item_id}):
                    valid_items.add(document.item_id)
                    valid_chain_items.add(document.item_id)
                    facts_with_valid_chain.add(evidence.fact_id)
        if any(
            all(
                any(
                    document.item_id in valid_items
                    and required_document in alignment.documents.get(document.item_id, frozenset())
                    for document in requested
                )
                for required_document in option
            )
            for option in evidence.acceptable_document_sets
        ):
            valid_obligation_ids.add(evidence.evidence_contract_id)

    necessary: set[str] = set()
    for document in requested:
        mapped = alignment.documents.get(document.item_id, frozenset())
        for evidence in active_obligations:
            expected = {
                document_id: evidence.expected_document_states.get(
                    document_id, DocumentState.UNKNOWN
                )
                for document_id in mapped.intersection(_accepted_documents(evidence))
            }
            if any(
                state not in {DocumentState.PROVIDED_SUFFICIENT, DocumentState.IRRELEVANT}
                for state in expected.values()
            ):
                necessary.add(document.item_id)
                break

    state_total = 0
    state_hits = 0
    for evidence in active_obligations:
        for document_id, expected_state in evidence.expected_document_states.items():
            state_total += 1
            state_hits += any(
                document.state is expected_state
                and document_id in alignment.documents.get(document.item_id, frozenset())
                for document in active_documents
            )
    criticality_total = sum(item.criticality for item in active_obligations)
    criticality_covered = sum(
        item.criticality
        for item in active_obligations
        if item.evidence_contract_id in covered_obligation_ids
    )
    active_fact_ids = {item.fact_id for item in active_obligations}
    return {
        "critical_evidence_recall": _ratio(criticality_covered, criticality_total, empty=1.0),
        "valid_chain_precision": _ratio(len(valid_chain_items), len(requested), empty=1.0),
        "fact_chain_completeness": _ratio(
            len(active_fact_ids.intersection(facts_with_valid_chain)),
            len(active_fact_ids),
            empty=1.0,
        ),
        "evidence_obligation_completeness": _ratio(
            len(valid_obligation_ids), len(active_obligations), empty=1.0
        ),
        "document_state_accuracy": _ratio(state_hits, state_total, empty=1.0),
        "unnecessary_document_rate": _ratio(
            len(requested) - len(necessary), len(requested), empty=0.0
        ),
    }


def _same_locator_set(
    offered: tuple[SourceLocator, ...], expected: tuple[SourceLocator, ...]
) -> bool:
    return len(offered) == len(expected) and all(item in offered for item in expected)


def _grounding_metrics(
    contract: AcceptanceContract,
    candidate: CandidateArtifact,
    alignment: _Alignment,
    failures: list[str],
) -> dict[str, float]:
    active_document_ids: set[str] = set()
    for evidence in contract.evidence_contracts:
        if _active(
            evidence.active_when,
            contract.scenario,
            failures,
            f"evidence {evidence.evidence_contract_id}",
        ):
            active_document_ids.update(evidence.expected_document_states)
    targets = []
    for concept in contract.concepts:
        active = _active(
            concept.active_when,
            contract.scenario,
            failures,
            f"concept {concept.concept_id}",
        )
        if (
            active
            and (
                concept.requirement is Requirement.MANDATORY
                or concept.concept_id in active_document_ids
            )
            and concept.source_requirements
        ):
            targets.append((concept.concept_id, concept.source_requirements, False))
    targets.extend(
        (predicate.predicate_id, predicate.source_requirements, True)
        for predicate in contract.branch_predicates
        if predicate.source_requirements
    )

    supported = 0
    span_expectations = 0
    span_hits = 0

    def offered_provenance(target_id: str) -> list[tuple[SourceLocator, ...]]:
        candidate_ids = set(alignment.candidate_endpoints_for(target_id))
        return [
            item.provenance for item in candidate.concepts if item.concept_id in candidate_ids
        ] + [item.provenance for item in candidate.documents if item.item_id in candidate_ids]

    for target_id, required, predicate_target in targets:
        if predicate_target:
            candidate_ids = {
                candidate_id
                for candidate_id, mapped in alignment.predicates.items()
                if target_id in mapped
            }
            offered = [
                item.provenance
                for item in candidate.branch_predicates
                if item.predicate_id in candidate_ids
            ]
        else:
            offered = offered_provenance(target_id)
        supported += any(_same_locator_set(locators, required) for locators in offered)
        for required_locator in required:
            if required_locator.locator_kind not in {
                LocatorKind.TEXT_SPAN,
                LocatorKind.AUTHORITY_PASSAGE,
            }:
                continue
            span_expectations += 1
            span_hits += any(required_locator in locators for locators in offered)

    concepts_by_id = {item.concept_id: item for item in contract.concepts}
    chain_expectations = 0
    chain_hits = 0
    for evidence in contract.evidence_contracts:
        if not _active(
            evidence.active_when,
            contract.scenario,
            failures,
            f"evidence {evidence.evidence_contract_id}",
        ):
            continue
        for decision_id in evidence.decision_ids:
            for capability_id in evidence.required_capability_ids:
                for option in evidence.acceptable_document_sets:
                    for document_id in option:
                        endpoint_ids = (
                            decision_id,
                            evidence.fact_id,
                            capability_id,
                            document_id,
                        )
                        inherited = set.intersection(
                            *(
                                set(concepts_by_id[item_id].source_requirements)
                                for item_id in endpoint_ids
                            )
                        )
                        if not inherited:
                            continue
                        chain_expectations += 1
                        chain_hits += all(
                            any(
                                inherited.issubset(set(locators))
                                for locators in offered_provenance(endpoint_id)
                            )
                            for endpoint_id in endpoint_ids
                        )
    source_rate = _ratio(supported, len(targets), empty=1.0)
    span_rate = _ratio(span_hits, span_expectations, empty=1.0)
    chain_rate = _ratio(chain_hits, chain_expectations, empty=1.0)
    return {
        "exact_source_support_rate": source_rate,
        "exact_source_span_rate": span_rate,
        "provenance_chain_inheritance_rate": chain_rate,
        "traceability_exactness": min(source_rate, span_rate, chain_rate),
    }


def _compare(observed: float, comparator: str, threshold: float) -> bool:
    if comparator == ">=":
        return observed >= threshold
    if comparator == "<=":
        return observed <= threshold
    if comparator == ">":
        return observed > threshold
    if comparator == "<":
        return observed < threshold
    if comparator == "==":
        return observed == threshold
    raise IndependentEvaluationError(f"unsupported gate comparator: {comparator}")


def evaluate_independently_v3(
    contract: AcceptanceContract,
    candidate: CandidateArtifact,
) -> IndependentEvaluationReceiptV3:
    """Evaluate all frozen fatal endpoints without using production scorer code."""

    if contract.case_id != candidate.case_id:
        raise IndependentEvaluationError(
            f"case mismatch: contract={contract.case_id}, candidate={candidate.case_id}"
        )
    declared_fatal_metrics = {gate.metric for gate in contract.acceptance_gates if gate.fatal}
    if declared_fatal_metrics != FATAL_METRICS:
        raise IndependentEvaluationError(
            "fatal metric policy differs from the CasePath-Bench-v3 freeze: "
            f"{sorted(declared_fatal_metrics)}"
        )

    failures: list[str] = []
    alignment = _align(contract, candidate)
    metrics = _process_metrics(contract, candidate, alignment, failures)
    evidence_metrics = _evidence_metrics(contract, candidate, alignment, failures)
    overlap = metrics.keys() & evidence_metrics.keys()
    if overlap:
        raise IndependentEvaluationError(f"duplicate independent metrics: {sorted(overlap)}")
    metrics.update(evidence_metrics)
    grounding_metrics = _grounding_metrics(contract, candidate, alignment, failures)
    overlap = metrics.keys() & grounding_metrics.keys()
    if overlap:
        raise IndependentEvaluationError(
            f"duplicate independent grounding metrics: {sorted(overlap)}"
        )
    metrics.update(grounding_metrics)
    missing_reported = REPORTED_ENDPOINTS_V3.difference(metrics)
    if missing_reported:
        raise IndependentEvaluationError(
            f"independent evaluator omitted reported endpoints: {sorted(missing_reported)}"
        )

    gates = tuple(
        IndependentGateResultV3(
            gate_id=gate.gate_id,
            metric=gate.metric,
            comparator=gate.comparator,
            threshold=gate.threshold,
            observed=metrics.get(gate.metric),
            fatal=gate.fatal,
            passed=(
                gate.metric in metrics
                and _compare(metrics[gate.metric], gate.comparator, gate.threshold)
            ),
        )
        for gate in contract.acceptance_gates
    )
    unique_failures = tuple(dict.fromkeys(failures))
    fatal_accepted = not unique_failures and all(item.passed or not item.fatal for item in gates)
    grounding_passed = metrics["traceability_exactness"] == 1.0
    return IndependentEvaluationReceiptV3(
        evaluator_version=INDEPENDENT_EVALUATOR_VERSION,
        case_id=contract.case_id,
        metrics=metrics,
        gates=gates,
        evaluation_failures=unique_failures,
        fatal_gates_accepted=fatal_accepted,
        source_grounding_passed=grounding_passed,
        accepted=fatal_accepted and grounding_passed,
    )


def build_reference_candidate_v3(contract: AcceptanceContract) -> CandidateArtifact:
    """Build the deterministic semantic-and-provenance reference candidate."""

    concepts_by_id = {item.concept_id: item for item in contract.concepts}
    concepts = tuple(
        CandidateConcept(
            concept_id=item.concept_id,
            kind=item.kind,
            label=item.label,
            active_when=item.active_when,
            provenance=item.source_requirements,
        )
        for item in contract.concepts
        if item.kind is not ConceptKind.DOCUMENT and item.requirement is not Requirement.FORBIDDEN
    )
    active_states = {
        document_id: state
        for evidence in contract.evidence_contracts
        if _evaluate_expression(evidence.active_when, contract.scenario)
        for document_id, state in evidence.expected_document_states.items()
    }
    document_items: dict[str, str] = {}
    documents: list[CandidateDocument] = []
    for item in contract.concepts:
        if item.kind is not ConceptKind.DOCUMENT or item.requirement is Requirement.FORBIDDEN:
            continue
        candidate_id = f"candidate.{item.concept_id}"
        document_items[item.concept_id] = candidate_id
        documents.append(
            CandidateDocument(
                item_id=candidate_id,
                document_id=item.concept_id,
                label=item.label,
                state=active_states.get(item.concept_id, DocumentState.PROVIDED_SUFFICIENT),
                request_mode=(
                    RequestMode.NOW if item.concept_id in active_states else RequestMode.NONE
                ),
                active_when=item.active_when,
                provenance=item.source_requirements,
            )
        )
    relations = tuple(
        CandidateRelation(
            relation_id=item.relation_id,
            relation_type=item.relation_type,
            source_id=document_items.get(item.source_id, item.source_id),
            target_id=document_items.get(item.target_id, item.target_id),
            active_when=item.active_when,
        )
        for item in contract.relations
        if item.requirement is not Requirement.FORBIDDEN
        and concepts_by_id[item.source_id].requirement is not Requirement.FORBIDDEN
        and concepts_by_id[item.target_id].requirement is not Requirement.FORBIDDEN
    )
    return CandidateArtifact(
        artifact_version="casepath.candidate-artifact/0.1.0",
        case_id=contract.case_id,
        concepts=concepts,
        relations=relations,
        branch_predicates=tuple(
            CandidateBranchPredicate(
                predicate_id=item.predicate_id,
                expression=item.expression,
                provenance=item.source_requirements,
            )
            for item in contract.branch_predicates
        ),
        documents=tuple(documents),
        terminal_outcome_ids=tuple(
            item.concept_id
            for item in contract.concepts
            if item.kind is ConceptKind.OUTCOME and item.requirement is not Requirement.FORBIDDEN
        ),
    )


def _semantic_attacks_v3(
    contract: AcceptanceContract,
    candidate: CandidateArtifact,
) -> tuple[CandidateArtifact, ...]:
    active_required_concepts = [
        item
        for item in contract.concepts
        if item.kind is not ConceptKind.DOCUMENT
        and item.requirement is Requirement.MANDATORY
        and _evaluate_expression(item.active_when, contract.scenario)
    ]
    active_required_relations = [
        item
        for item in contract.relations
        if item.requirement is Requirement.MANDATORY
        and _evaluate_expression(item.active_when, contract.scenario)
    ]
    if (
        not active_required_concepts
        or not active_required_relations
        or not candidate.branch_predicates
    ):
        raise IndependentEvaluationError(
            f"{contract.case_id} cannot instantiate the frozen semantic attack set"
        )
    required = active_required_concepts[0]
    missing_node = candidate.model_copy(
        update={
            "concepts": tuple(
                item for item in candidate.concepts if item.concept_id != required.concept_id
            ),
            "relations": tuple(
                item
                for item in candidate.relations
                if required.concept_id not in {item.source_id, item.target_id}
            ),
            "terminal_outcome_ids": tuple(
                item for item in candidate.terminal_outcome_ids if item != required.concept_id
            ),
        }
    )
    required_relation = active_required_relations[0]
    missing_relation = candidate.model_copy(
        update={
            "relations": tuple(
                item
                for item in candidate.relations
                if item.relation_id != required_relation.relation_id
            )
        }
    )
    first_predicate = candidate.branch_predicates[0]
    wrong_branch = candidate.model_copy(
        update={
            "branch_predicates": tuple(
                item.model_copy(update={"expression": f"not ({item.expression})"})
                if item.predicate_id == first_predicate.predicate_id
                else item
                for item in candidate.branch_predicates
            )
        }
    )
    orphan_request = candidate.model_copy(
        update={
            "documents": (
                *candidate.documents,
                CandidateDocument(
                    item_id="independent-attack.orphan.item",
                    document_id="independent-attack.orphan.document",
                    label="Irrelevant document",
                    state=DocumentState.MISSING,
                    request_mode=RequestMode.NOW,
                ),
            )
        }
    )
    premature_targets = [
        item for item in candidate.documents if item.request_mode is RequestMode.NONE
    ]
    state_targets = [
        item
        for item in candidate.documents
        if item.request_mode is RequestMode.NOW
        and _evaluate_expression(item.active_when, contract.scenario)
    ]
    if not premature_targets or not state_targets:
        raise IndependentEvaluationError(
            f"{contract.case_id} cannot instantiate document semantic attacks"
        )
    premature_target = premature_targets[0]
    premature_request = candidate.model_copy(
        update={
            "documents": tuple(
                item.model_copy(update={"request_mode": RequestMode.NOW, "active_when": "true"})
                if item.item_id == premature_target.item_id
                else item
                for item in candidate.documents
            )
        }
    )
    state_target = state_targets[0]
    wrong_state_value = (
        DocumentState.MISSING
        if state_target.state is not DocumentState.MISSING
        else DocumentState.PROVIDED_SUFFICIENT
    )
    wrong_document_state = candidate.model_copy(
        update={
            "documents": tuple(
                item.model_copy(update={"state": wrong_state_value})
                if item.item_id == state_target.item_id
                else item
                for item in candidate.documents
            )
        }
    )
    return (
        missing_node,
        missing_relation,
        wrong_branch,
        candidate.model_copy(update={"terminal_outcome_ids": ()}),
        orphan_request,
        premature_request,
        wrong_document_state,
    )


def _changed_locator(locator: SourceLocator, **updates: object) -> SourceLocator:
    return SourceLocator.model_validate({**locator.model_dump(mode="json"), **updates})


def _grounding_attacks_v3(candidate: CandidateArtifact) -> tuple[CandidateArtifact, ...]:
    indexed = [(index, item) for index, item in enumerate(candidate.concepts) if item.provenance]
    if len(indexed) < 2:
        raise IndependentEvaluationError(
            f"{candidate.case_id} cannot instantiate the frozen grounding attack set"
        )
    first_index, first = indexed[0]
    distinct = [pair for pair in indexed[1:] if pair[1].provenance != first.provenance]
    if not distinct:
        raise IndependentEvaluationError(f"{candidate.case_id} has no distinct grounding target")
    second_index, second = distinct[0]

    def update_concept(
        index: int,
        concept: CandidateConcept,
        provenance: tuple[SourceLocator, ...],
    ) -> CandidateArtifact:
        changed = list(candidate.concepts)
        changed[index] = concept.model_copy(update={"provenance": provenance})
        return candidate.model_copy(update={"concepts": tuple(changed)})

    absent = update_concept(first_index, first, ())
    swapped_concepts = list(candidate.concepts)
    swapped_concepts[first_index] = first.model_copy(update={"provenance": second.provenance})
    swapped_concepts[second_index] = second.model_copy(update={"provenance": first.provenance})
    swapped = candidate.model_copy(update={"concepts": tuple(swapped_concepts)})
    stale = update_concept(
        first_index,
        first,
        (
            _changed_locator(first.provenance[0], source_version="stale-source-version"),
            *first.provenance[1:],
        ),
    )
    fabricated = update_concept(
        first_index,
        first,
        (
            _changed_locator(first.provenance[0], artifact_id="fabricated-source"),
            *first.provenance[1:],
        ),
    )
    json_targets = [
        (concept_index, concept, locator_index)
        for concept_index, concept in indexed
        for locator_index, locator in enumerate(concept.provenance)
        if locator.json_pointer is not None
    ]
    if not json_targets:
        raise IndependentEvaluationError(
            f"{candidate.case_id} has no JSON-pointer grounding target"
        )
    json_index, json_concept, locator_index = json_targets[0]
    json_locator = json_concept.provenance[locator_index]
    wrong_pointer_values = list(json_concept.provenance)
    wrong_pointer_values[locator_index] = _changed_locator(
        json_locator, json_pointer="/independent-attack/wrong-pointer"
    )
    wrong_pointer = update_concept(json_index, json_concept, tuple(wrong_pointer_values))
    wrong_hash_values = list(json_concept.provenance)
    wrong_hash_values[locator_index] = _changed_locator(
        json_locator, canonical_value_sha256="0" * 64
    )
    wrong_hash = update_concept(json_index, json_concept, tuple(wrong_hash_values))
    cite_everything = update_concept(
        first_index,
        first,
        (*first.provenance, second.provenance[0]),
    )
    return absent, swapped, stale, fabricated, wrong_pointer, wrong_hash, cite_everything


def audit_contracts_independently_v3(
    contracts: Iterable[AcceptanceContract],
    *,
    expected_case_count: int = 150,
) -> IndependentEvaluatorAuditReceiptV3:
    """Run the independent reference and adversarial audit over a frozen roster."""

    if expected_case_count < 1:
        raise IndependentEvaluationError("expected_case_count must be positive")
    roster = tuple(contracts)
    failures: list[str] = []
    case_results: list[IndependentCaseAuditV3] = []
    for contract in roster:
        candidate = build_reference_candidate_v3(contract)
        reference = evaluate_independently_v3(contract, candidate)
        semantic_receipts = tuple(
            evaluate_independently_v3(contract, attack)
            for attack in _semantic_attacks_v3(contract, candidate)
        )
        grounding_receipts = tuple(
            evaluate_independently_v3(contract, attack)
            for attack in _grounding_attacks_v3(candidate)
        )
        empty = CandidateArtifact(
            artifact_version="casepath.candidate-artifact/0.1.0",
            case_id=contract.case_id,
            concepts=(),
            relations=(),
            documents=(),
            terminal_outcome_ids=(),
        )
        empty_receipt = evaluate_independently_v3(contract, empty)
        request_everything = candidate.model_copy(
            update={
                "documents": tuple(
                    item.model_copy(update={"request_mode": RequestMode.NOW, "active_when": "true"})
                    for item in candidate.documents
                )
            }
        )
        request_everything_receipt = evaluate_independently_v3(contract, request_everything)
        reported_complete = REPORTED_ENDPOINTS_V3.issubset(reference.metrics)
        semantic_kills = sum(not item.fatal_gates_accepted for item in semantic_receipts)
        grounding_kills = sum(
            item.fatal_gates_accepted and not item.source_grounding_passed and not item.accepted
            for item in grounding_receipts
        )
        empty_rejected = not empty_receipt.fatal_gates_accepted
        request_all_rejected = not request_everything_receipt.fatal_gates_accepted
        result = IndependentCaseAuditV3(
            case_id=contract.case_id,
            reported_endpoints_complete=reported_complete,
            reference_candidate_accepted=reference.accepted,
            semantic_attack_attempt_count=len(semantic_receipts),
            semantic_attack_kill_count=semantic_kills,
            grounding_attack_attempt_count=len(grounding_receipts),
            grounding_attack_kill_count=grounding_kills,
            empty_output_rejected=empty_rejected,
            request_everything_rejected=request_all_rejected,
        )
        case_results.append(result)
        if not reported_complete:
            failures.append(f"{contract.case_id}: reported endpoint set is incomplete")
        if not reference.accepted:
            failures.append(f"{contract.case_id}: reference candidate was rejected")
        if semantic_kills != len(semantic_receipts):
            failures.append(f"{contract.case_id}: a semantic attack survived")
        if grounding_kills != len(grounding_receipts):
            failures.append(f"{contract.case_id}: a grounding attack survived")
        if not empty_rejected:
            failures.append(f"{contract.case_id}: empty output survived")
        if not request_all_rejected:
            failures.append(f"{contract.case_id}: request-everything survived")

    unique_count = len({item.case_id for item in roster})
    if len(roster) != expected_case_count:
        failures.append(f"expected {expected_case_count} contracts but audited {len(roster)}")
    if unique_count != len(roster):
        failures.append("contract roster contains duplicate case IDs")
    results = tuple(case_results)
    semantic_attempts = sum(item.semantic_attack_attempt_count for item in results)
    semantic_kills = sum(item.semantic_attack_kill_count for item in results)
    grounding_attempts = sum(item.grounding_attack_attempt_count for item in results)
    grounding_kills = sum(item.grounding_attack_kill_count for item in results)
    return IndependentEvaluatorAuditReceiptV3(
        audit_version=INDEPENDENT_AUDIT_VERSION,
        evaluator_version=INDEPENDENT_EVALUATOR_VERSION,
        expected_case_count=expected_case_count,
        audited_case_count=len(roster),
        unique_case_count=unique_count,
        reported_endpoint_count=len(REPORTED_ENDPOINTS_V3),
        reported_endpoint_complete_case_count=sum(
            item.reported_endpoints_complete for item in results
        ),
        reference_candidate_accepted_count=sum(
            item.reference_candidate_accepted for item in results
        ),
        semantic_attack_attempt_count=semantic_attempts,
        semantic_attack_kill_count=semantic_kills,
        grounding_attack_attempt_count=grounding_attempts,
        grounding_attack_kill_count=grounding_kills,
        empty_output_rejected_count=sum(item.empty_output_rejected for item in results),
        request_everything_rejected_count=sum(item.request_everything_rejected for item in results),
        cases=results,
        failures=tuple(failures),
        eligible=not failures,
    )


__all__ = [
    "FATAL_METRICS",
    "INDEPENDENT_AUDIT_VERSION",
    "INDEPENDENT_EVALUATOR_VERSION",
    "REPORTED_ENDPOINTS_V3",
    "IndependentCaseAuditV3",
    "IndependentEvaluationError",
    "IndependentEvaluationReceiptV3",
    "IndependentEvaluatorAuditReceiptV3",
    "IndependentGateResultV3",
    "audit_contracts_independently_v3",
    "build_reference_candidate_v3",
    "evaluate_independently_v3",
]
