"""Calibration diagnostics for concept-level confidence."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.expressions import ExpressionError, evaluate_expression
from contracts.schema import AcceptanceContract, CandidateArtifact, Requirement

from .alignment import Alignment


@dataclass(frozen=True)
class CalibrationScore:
    metrics: dict[str, float]
    counts: dict[str, int]
    failures: tuple[str, ...]


def score_calibration(
    contract: AcceptanceContract,
    candidate: CandidateArtifact,
    alignment: Alignment,
    *,
    bins: int = 10,
) -> CalibrationScore:
    failures: list[str] = []
    allowed: set[str] = set()
    for concept in contract.concepts:
        try:
            active = evaluate_expression(concept.active_when, contract.scenario)
        except ExpressionError as exc:
            failures.append(f"concept {concept.concept_id}: {exc}")
            active = False
        if active and concept.requirement is not Requirement.FORBIDDEN:
            allowed.add(concept.concept_id)

    observations = []
    for candidate_concept in candidate.concepts:
        try:
            candidate_active = evaluate_expression(
                candidate_concept.active_when,
                contract.scenario,
            )
        except ExpressionError as exc:
            failures.append(f"candidate concept {candidate_concept.concept_id}: {exc}")
            candidate_active = False
        if candidate_active:
            observations.append(
                (
                    candidate_concept.confidence,
                    float(
                        bool(
                            alignment.concept_map.get(
                                candidate_concept.concept_id,
                                frozenset(),
                            )
                            & allowed
                        )
                    ),
                )
            )
    if not observations:
        return CalibrationScore(
            metrics={"brier_score": 0.0, "expected_calibration_error": 0.0},
            counts={"calibration_items": 0},
            failures=tuple(failures),
        )
    brier = sum((confidence - outcome) ** 2 for confidence, outcome in observations) / len(
        observations
    )
    ece = 0.0
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        bucket = [
            item
            for item in observations
            if (lower <= item[0] <= upper if index == bins - 1 else lower <= item[0] < upper)
        ]
        if bucket:
            mean_confidence = sum(item[0] for item in bucket) / len(bucket)
            mean_outcome = sum(item[1] for item in bucket) / len(bucket)
            ece += len(bucket) / len(observations) * abs(mean_confidence - mean_outcome)
    return CalibrationScore(
        metrics={"brier_score": brier, "expected_calibration_error": ece},
        counts={"calibration_items": len(observations)},
        failures=tuple(dict.fromkeys(failures)),
    )
