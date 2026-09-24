"""Exact proposition-to-source support scoring."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.expressions import ExpressionError, evaluate_expression
from contracts.schema import (
    AcceptanceContract,
    CandidateArtifact,
    LocatorKind,
    Requirement,
    SourceLocator,
)

from .alignment import Alignment


@dataclass(frozen=True)
class GroundingScore:
    metrics: dict[str, float]
    counts: dict[str, int]
    failures: tuple[str, ...]


def _exact_locator_set(
    candidate: tuple[SourceLocator, ...], required: tuple[SourceLocator, ...]
) -> bool:
    if len(candidate) != len(required):
        return False
    return all(any(item == expected for item in candidate) for expected in required)


def score_grounding(
    contract: AcceptanceContract,
    candidate: CandidateArtifact,
    alignment: Alignment,
) -> GroundingScore:
    failures: list[str] = []
    required_document_ids: set[str] = set()
    for evidence in contract.evidence_contracts:
        try:
            active = evaluate_expression(evidence.active_when, contract.scenario)
        except ExpressionError as exc:
            failures.append(f"evidence {evidence.evidence_contract_id}: {exc}")
            active = False
        if active:
            required_document_ids.update(evidence.expected_document_states)

    required_concepts = []
    for concept in contract.concepts:
        try:
            active = evaluate_expression(concept.active_when, contract.scenario)
        except ExpressionError as exc:
            failures.append(f"concept {concept.concept_id}: {exc}")
            active = False
        if (
            active
            and (
                concept.requirement is Requirement.MANDATORY
                or concept.concept_id in required_document_ids
            )
            and concept.source_requirements
        ):
            required_concepts.append(concept)

    required_predicates = [
        predicate for predicate in contract.branch_predicates if predicate.source_requirements
    ]

    supported = 0
    exact_span_expectations = 0
    exact_span_hits = 0
    stale_source_uses = 0

    def matching_endpoints(contract_id: str) -> list[object]:
        candidate_ids = alignment.candidate_ids_for(contract_id)
        return [
            *(item for item in candidate.concepts if item.concept_id in candidate_ids),
            *(item for item in candidate.documents if item.item_id in candidate_ids),
        ]

    for concept in required_concepts:
        matching_candidates = matching_endpoints(concept.concept_id)
        if any(
            _exact_locator_set(item.provenance, concept.source_requirements)  # type: ignore[attr-defined]
            for item in matching_candidates
        ):
            supported += 1
        for required_locator in concept.source_requirements:
            if required_locator.locator_kind not in {
                LocatorKind.TEXT_SPAN,
                LocatorKind.AUTHORITY_PASSAGE,
            }:
                continue
            exact_span_expectations += 1
            exact_span_hits += any(
                required_locator in item.provenance  # type: ignore[attr-defined]
                for item in matching_candidates
            )
        for item in matching_candidates:
            for locator in item.provenance:  # type: ignore[attr-defined]
                if any(
                    requirement.source_version is not None
                    and locator.artifact_id == requirement.artifact_id
                    and locator.source_version != requirement.source_version
                    for requirement in concept.source_requirements
                ):
                    stale_source_uses += 1

    for predicate in required_predicates:
        candidate_ids = alignment.candidate_predicate_ids_for(predicate.predicate_id)
        matching = [
            item for item in candidate.branch_predicates if item.predicate_id in candidate_ids
        ]
        if any(
            _exact_locator_set(item.provenance, predicate.source_requirements) for item in matching
        ):
            supported += 1
        for required_locator in predicate.source_requirements:
            if required_locator.locator_kind not in {
                LocatorKind.TEXT_SPAN,
                LocatorKind.AUTHORITY_PASSAGE,
            }:
                continue
            exact_span_expectations += 1
            exact_span_hits += any(required_locator in item.provenance for item in matching)
        for predicate_item in matching:
            for locator in predicate_item.provenance:
                if any(
                    requirement.source_version is not None
                    and locator.artifact_id == requirement.artifact_id
                    and locator.source_version != requirement.source_version
                    for requirement in predicate.source_requirements
                ):
                    stale_source_uses += 1

    concepts_by_id = {item.concept_id: item for item in contract.concepts}
    chain_expectations = 0
    inherited_chain_hits = 0
    for evidence in contract.evidence_contracts:
        try:
            active = evaluate_expression(evidence.active_when, contract.scenario)
        except ExpressionError as exc:
            failures.append(f"evidence {evidence.evidence_contract_id}: {exc}")
            active = False
        if not active:
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
                        locator_sets = [
                            set(concepts_by_id[item_id].source_requirements)
                            for item_id in endpoint_ids
                        ]
                        inherited = set.intersection(*locator_sets)
                        if not inherited:
                            continue
                        chain_expectations += 1
                        candidate_groups = [matching_endpoints(item_id) for item_id in endpoint_ids]
                        inherited_chain_hits += all(
                            any(
                                inherited.issubset(set(item.provenance))  # type: ignore[attr-defined]
                                for item in group
                            )
                            for group in candidate_groups
                        )

    total = len(required_concepts) + len(required_predicates)
    exact_support_rate = supported / total if total else 1.0
    exact_span_rate = exact_span_hits / exact_span_expectations if exact_span_expectations else 1.0
    chain_rate = inherited_chain_hits / chain_expectations if chain_expectations else 1.0
    counts = {
        "source_grounded_required_concepts": total,
        "exactly_supported_required_concepts": supported,
        "unsupported_required_concepts": total - supported,
        "stale_source_uses": stale_source_uses,
        "exact_source_span_expectations": exact_span_expectations,
        "exact_source_span_hits": exact_span_hits,
        "provenance_chain_expectations": chain_expectations,
        "provenance_chain_inheritance_hits": inherited_chain_hits,
    }
    metrics = {
        "exact_source_support_rate": exact_support_rate,
        "exact_source_span_rate": exact_span_rate,
        "provenance_chain_inheritance_rate": chain_rate,
        "traceability_exactness": min(exact_support_rate, exact_span_rate, chain_rate),
        "unsupported_claim_rate": (total - supported) / total if total else 0.0,
        "stale_source_usage_rate": stale_source_uses / total if total else 0.0,
    }
    return GroundingScore(metrics=metrics, counts=counts, failures=tuple(dict.fromkeys(failures)))
