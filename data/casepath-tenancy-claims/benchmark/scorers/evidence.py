"""Evidence obligation, document burden, and chain-validity scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contracts.expressions import ExpressionError, evaluate_expression
from contracts.schema import (
    AcceptanceContract,
    CandidateArtifact,
    DocumentState,
    EvidenceContract,
    RelationType,
    RequestMode,
)

from .alignment import Alignment


@dataclass(frozen=True)
class EvidenceScore:
    metrics: dict[str, float]
    counts: dict[str, int]
    failures: tuple[str, ...]


def _ratio(numerator: int | float, denominator: int | float, *, empty: float = 1.0) -> float:
    return float(numerator / denominator) if denominator else empty


def _active(expression: str, assignment: dict[str, Any], failures: list[str], label: str) -> bool:
    try:
        return evaluate_expression(expression, assignment)
    except ExpressionError as exc:
        failures.append(f"{label}: {exc}")
        return False


def _accepted_documents(evidence: EvidenceContract) -> set[str]:
    return {document for option in evidence.acceptable_document_sets for document in option}


def score_evidence(
    contract: AcceptanceContract,
    candidate: CandidateArtifact,
    alignment: Alignment,
) -> EvidenceScore:
    failures: list[str] = []
    assignment = contract.scenario
    active_obligations = [
        evidence
        for evidence in contract.evidence_contracts
        if _active(
            evidence.active_when,
            assignment,
            failures,
            f"evidence contract {evidence.evidence_contract_id}",
        )
    ]
    inactive_obligations = [
        evidence for evidence in contract.evidence_contracts if evidence not in active_obligations
    ]
    active_concepts = {
        concept.concept_id
        for concept in candidate.concepts
        if _active(
            concept.active_when,
            assignment,
            failures,
            f"candidate concept {concept.concept_id}",
        )
    }
    active_documents = [
        document
        for document in candidate.documents
        if _active(
            document.active_when,
            assignment,
            failures,
            f"candidate document {document.item_id}",
        )
    ]
    requested_documents = [
        document for document in active_documents if document.request_mode is not RequestMode.NONE
    ]
    active_relations = [
        relation
        for relation in candidate.relations
        if _active(
            relation.active_when,
            assignment,
            failures,
            f"candidate relation {relation.relation_id}",
        )
    ]

    def candidates_for(contract_id: str) -> set[str]:
        return set(alignment.candidate_ids_for(contract_id)).intersection(active_concepts)

    def has_edge(kind: RelationType, sources: set[str], targets: set[str]) -> bool:
        return any(
            relation.relation_type is kind
            and relation.source_id in sources
            and relation.target_id in targets
            for relation in active_relations
        )

    requested_contract_docs = {
        contract_id
        for document in requested_documents
        for contract_id in alignment.document_map.get(document.item_id, frozenset())
    }

    covered_obligations: set[str] = set()
    valid_obligations: set[str] = set()
    valid_chain_items: set[str] = set()
    fact_ids_with_chain: set[str] = set()
    obligation_chain_items: dict[str, set[str]] = {}

    for evidence in active_obligations:
        if any(
            set(option).issubset(requested_contract_docs)
            for option in evidence.acceptable_document_sets
        ):
            covered_obligations.add(evidence.evidence_contract_id)

        decision_candidates = {
            candidate_id
            for decision_id in evidence.decision_ids
            for candidate_id in candidates_for(decision_id)
        }
        fact_candidates = candidates_for(evidence.fact_id)
        capability_candidates = {
            candidate_id
            for capability_id in evidence.required_capability_ids
            for candidate_id in candidates_for(capability_id)
        }
        valid_items: set[str] = set()
        if has_edge(RelationType.REQUIRES_FACT, decision_candidates, fact_candidates) and has_edge(
            RelationType.SUPPORTED_BY, fact_candidates, capability_candidates
        ):
            for document in requested_documents:
                mapped_docs = alignment.document_map.get(document.item_id, frozenset())
                if not mapped_docs.intersection(_accepted_documents(evidence)):
                    continue
                if has_edge(
                    RelationType.SATISFIED_BY,
                    capability_candidates,
                    {document.item_id},
                ):
                    valid_items.add(document.item_id)
                    valid_chain_items.add(document.item_id)
                    fact_ids_with_chain.add(evidence.fact_id)
        obligation_chain_items[evidence.evidence_contract_id] = valid_items

        for option in evidence.acceptable_document_sets:
            option_satisfied = True
            for required_document in option:
                if not any(
                    document.item_id in valid_items
                    and required_document
                    in alignment.document_map.get(document.item_id, frozenset())
                    for document in requested_documents
                ):
                    option_satisfied = False
                    break
            if option_satisfied:
                valid_obligations.add(evidence.evidence_contract_id)
                break

    necessary_items: set[str] = set()
    for document in requested_documents:
        mapped_docs = alignment.document_map.get(document.item_id, frozenset())
        for evidence in active_obligations:
            accepted = _accepted_documents(evidence)
            expected = {
                doc_id: evidence.expected_document_states.get(doc_id, DocumentState.UNKNOWN)
                for doc_id in mapped_docs.intersection(accepted)
            }
            if any(
                state not in {DocumentState.PROVIDED_SUFFICIENT, DocumentState.IRRELEVANT}
                for state in expected.values()
            ):
                necessary_items.add(document.item_id)
                break

    wrong_branch_items = {
        document.item_id
        for document in requested_documents
        if document.item_id not in necessary_items
        and any(
            alignment.document_map.get(document.item_id, frozenset()).intersection(
                _accepted_documents(evidence)
            )
            for evidence in inactive_obligations
        )
    }
    premature_items: set[str] = set()
    for document in requested_documents:
        if document.request_mode is not RequestMode.NOW:
            continue
        mapped_docs = alignment.document_map.get(document.item_id, frozenset())
        if any(
            evidence.expected_document_states.get(doc_id)
            in {
                DocumentState.CONDITIONAL,
                DocumentState.PROVIDED_SUFFICIENT,
                DocumentState.IRRELEVANT,
            }
            for evidence in active_obligations
            for doc_id in mapped_docs
        ):
            premature_items.add(document.item_id)

    expected_states: list[tuple[str, DocumentState]] = []
    state_hits = 0
    for evidence in active_obligations:
        for document_id, expected_state in evidence.expected_document_states.items():
            expected_states.append((document_id, expected_state))
            if any(
                expected_state is document.state
                and document_id in alignment.document_map.get(document.item_id, frozenset())
                for document in active_documents
            ):
                state_hits += 1

    duplicate_count = 0
    seen_documents: set[str] = set()
    for document in requested_documents:
        identity = document.document_id
        if identity in seen_documents:
            duplicate_count += 1
        seen_documents.add(identity)

    active_by_id = {evidence.evidence_contract_id: evidence for evidence in active_obligations}
    incompatible_pairs: set[tuple[str, str]] = set()
    for evidence in active_obligations:
        if evidence.evidence_contract_id not in covered_obligations:
            continue
        for other_id in evidence.incompatible_with:
            if other_id in active_by_id and other_id in covered_obligations:
                first, second = sorted((evidence.evidence_contract_id, other_id))
                incompatible_pairs.add((first, second))

    critical_weight = sum(evidence.criticality for evidence in active_obligations)
    covered_weight = sum(
        evidence.criticality
        for evidence in active_obligations
        if evidence.evidence_contract_id in covered_obligations
    )
    active_fact_ids = {evidence.fact_id for evidence in active_obligations}
    counts = {
        "active_evidence_obligations": len(active_obligations),
        "covered_evidence_obligations": len(covered_obligations),
        "valid_evidence_obligations": len(valid_obligations),
        "active_required_facts": len(active_fact_ids),
        "facts_with_valid_chain": len(active_fact_ids.intersection(fact_ids_with_chain)),
        "requested_documents": len(requested_documents),
        "necessary_requested_documents": len(necessary_items),
        "valid_chain_documents": len(valid_chain_items),
        "orphan_documents": len({doc.item_id for doc in requested_documents} - valid_chain_items),
        "wrong_branch_documents": len(wrong_branch_items),
        "premature_documents": len(premature_items),
        "duplicate_documents": duplicate_count,
        "incompatible_requirement_pairs": len(incompatible_pairs),
        "document_state_expectations": len(expected_states),
        "document_state_hits": state_hits,
        "criticality_weight_total": critical_weight,
        "criticality_weight_covered": covered_weight,
    }
    metrics = {
        "critical_evidence_recall": _ratio(covered_weight, critical_weight),
        "unnecessary_document_rate": _ratio(
            len(requested_documents) - len(necessary_items),
            len(requested_documents),
            empty=0.0,
        ),
        "valid_chain_precision": _ratio(
            len(valid_chain_items), len(requested_documents), empty=1.0
        ),
        "fact_chain_completeness": _ratio(
            len(active_fact_ids.intersection(fact_ids_with_chain)), len(active_fact_ids)
        ),
        "evidence_obligation_completeness": _ratio(len(valid_obligations), len(active_obligations)),
        "document_state_accuracy": _ratio(state_hits, len(expected_states)),
        "evidence_gap_rate": _ratio(
            len(active_obligations) - len(covered_obligations), len(active_obligations), empty=0.0
        ),
        "orphan_document_rate": _ratio(
            counts["orphan_documents"], len(requested_documents), empty=0.0
        ),
        "wrong_branch_attachment_rate": _ratio(
            len(wrong_branch_items), len(requested_documents), empty=0.0
        ),
        "premature_request_rate": _ratio(len(premature_items), len(requested_documents), empty=0.0),
        "duplicate_request_rate": _ratio(duplicate_count, len(requested_documents), empty=0.0),
        "incompatible_requirement_count": float(len(incompatible_pairs)),
    }
    return EvidenceScore(metrics=metrics, counts=counts, failures=tuple(dict.fromkeys(failures)))
