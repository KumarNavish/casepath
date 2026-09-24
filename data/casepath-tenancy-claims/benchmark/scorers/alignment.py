"""Frozen expert alignment, including explicitly allowed split/merge variants."""

from __future__ import annotations

import re
from dataclasses import dataclass

from contracts.expressions import ExpressionError, evaluate_expression
from contracts.schema import (
    AcceptanceContract,
    BranchPredicateSpec,
    CandidateArtifact,
    ConceptKind,
)


def _normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


@dataclass(frozen=True)
class Alignment:
    concept_map: dict[str, frozenset[str]]
    document_map: dict[str, frozenset[str]]
    predicate_map: dict[str, frozenset[str]]

    @property
    def endpoint_map(self) -> dict[str, frozenset[str]]:
        return {**self.concept_map, **self.document_map}

    def candidate_ids_for(self, contract_id: str) -> frozenset[str]:
        return frozenset(
            candidate_id
            for candidate_id, contract_ids in self.endpoint_map.items()
            if contract_id in contract_ids
        )

    def candidate_predicate_ids_for(self, contract_id: str) -> frozenset[str]:
        return frozenset(
            candidate_id
            for candidate_id, contract_ids in self.predicate_map.items()
            if contract_id in contract_ids
        )


def _predicate_matches(candidate_expression: str, expected: BranchPredicateSpec) -> bool:
    probes = expected.probes
    try:
        return all(
            evaluate_expression(candidate_expression, probe.assignment) is probe.expected
            for probe in probes
        )
    except ExpressionError:
        return False


def _align_predicates(
    contract: AcceptanceContract,
    candidate: CandidateArtifact,
) -> dict[str, frozenset[str]]:
    """Align renamed predicates only when their probe behavior identifies one unique target."""

    expected_by_id = {predicate.predicate_id: predicate for predicate in contract.branch_predicates}
    candidate_by_id = {
        predicate.predicate_id: predicate for predicate in candidate.branch_predicates
    }
    predicate_map: dict[str, frozenset[str]] = {}

    exact_ids = expected_by_id.keys() & candidate_by_id.keys()
    for predicate_id in exact_ids:
        predicate_map[predicate_id] = frozenset({predicate_id})

    unmatched_expected = {
        predicate_id: predicate
        for predicate_id, predicate in expected_by_id.items()
        if predicate_id not in exact_ids
    }
    unmatched_candidates = {
        predicate_id: predicate
        for predicate_id, predicate in candidate_by_id.items()
        if predicate_id not in exact_ids
    }
    compatible_targets = {
        candidate_id: {
            expected_id
            for expected_id, expected in unmatched_expected.items()
            if _predicate_matches(candidate_predicate.expression, expected)
        }
        for candidate_id, candidate_predicate in unmatched_candidates.items()
    }
    compatible_sources: dict[str, set[str]] = {
        expected_id: set() for expected_id in unmatched_expected
    }
    for candidate_id, expected_ids in compatible_targets.items():
        for expected_id in expected_ids:
            compatible_sources[expected_id].add(candidate_id)

    for candidate_id, expected_ids in compatible_targets.items():
        if len(expected_ids) != 1:
            predicate_map[candidate_id] = frozenset()
            continue
        expected_id = next(iter(expected_ids))
        if len(compatible_sources[expected_id]) == 1:
            predicate_map[candidate_id] = frozenset({expected_id})
        else:
            predicate_map[candidate_id] = frozenset()

    return predicate_map


def align_candidate(contract: AcceptanceContract, candidate: CandidateArtifact) -> Alignment:
    """Align concepts by frozen naming rules and predicates by frozen behavior probes."""

    concepts = {concept.concept_id: concept for concept in contract.concepts}
    label_index: dict[tuple[ConceptKind, str], set[str]] = {}
    for concept in contract.concepts:
        for label in (concept.label, *concept.aliases):
            label_index.setdefault((concept.kind, _normalise(label)), set()).add(concept.concept_id)

    variant_index: dict[str, set[str]] = {}
    for variant in contract.variants:
        for candidate_id in variant.candidate_concept_ids:
            variant_index.setdefault(candidate_id, set()).update(variant.contract_concept_ids)

    concept_map: dict[str, frozenset[str]] = {}
    for candidate_concept in candidate.concepts:
        concept_matches: set[str] = set()
        exact = concepts.get(candidate_concept.concept_id)
        if exact is not None and exact.kind is candidate_concept.kind:
            concept_matches.add(exact.concept_id)
        concept_matches.update(
            label_index.get(
                (candidate_concept.kind, _normalise(candidate_concept.label)),
                set(),
            )
        )
        concept_matches.update(variant_index.get(candidate_concept.concept_id, set()))
        concept_map[candidate_concept.concept_id] = frozenset(concept_matches)

    document_map: dict[str, frozenset[str]] = {}
    for candidate_document in candidate.documents:
        document_matches: set[str] = set()
        exact = concepts.get(candidate_document.document_id)
        if exact is not None and exact.kind is ConceptKind.DOCUMENT:
            document_matches.add(exact.concept_id)
        document_matches.update(
            label_index.get(
                (ConceptKind.DOCUMENT, _normalise(candidate_document.label)),
                set(),
            )
        )
        document_matches.update(variant_index.get(candidate_document.document_id, set()))
        document_map[candidate_document.item_id] = frozenset(document_matches)

    return Alignment(
        concept_map=concept_map,
        document_map=document_map,
        predicate_map=_align_predicates(contract, candidate),
    )
