"""Single deterministic entry point for contract evaluation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from contracts.schema import AcceptanceContract, CandidateArtifact

from .alignment import align_candidate
from .calibration import score_calibration
from .evidence import score_evidence
from .grounding import score_grounding
from .process import score_process

EVALUATOR_VERSION = "casepath-evaluator/0.1.0"


class GateResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    gate_id: str
    metric: str
    observed: float | None
    comparator: Literal[">=", "<=", ">", "<", "=="]
    threshold: float
    fatal: bool
    passed: bool
    reason: str


class EvaluationReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    receipt_version: Literal["casepath.evaluation-receipt/0.1.0"]
    evaluator_version: str
    case_id: str
    candidate_artifact_version: str
    metrics: dict[str, float]
    counts: dict[str, int]
    gates: tuple[GateResult, ...]
    evaluation_failures: tuple[str, ...]
    accepted: bool


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
    raise ValueError(f"unsupported comparator: {comparator}")


def evaluate_candidate(
    contract: AcceptanceContract,
    candidate: CandidateArtifact,
) -> EvaluationReceipt:
    if contract.case_id != candidate.case_id:
        raise ValueError(
            f"case mismatch: contract={contract.case_id}, candidate={candidate.case_id}"
        )
    alignment = align_candidate(contract, candidate)
    scores = (
        score_process(contract, candidate, alignment),
        score_evidence(contract, candidate, alignment),
        score_grounding(contract, candidate, alignment),
        score_calibration(contract, candidate, alignment),
    )
    metrics: dict[str, float] = {}
    counts: dict[str, int] = {}
    failures: list[str] = []
    for score in scores:
        overlap = metrics.keys() & score.metrics.keys()
        if overlap:
            raise RuntimeError(f"duplicate metric names: {sorted(overlap)}")
        metrics.update(score.metrics)
        counts.update(score.counts)
        failures.extend(score.failures)

    gate_results: list[GateResult] = []
    for gate in contract.acceptance_gates:
        observed = metrics.get(gate.metric)
        passed = observed is not None and _compare(observed, gate.comparator, gate.threshold)
        reason = (
            f"{observed:.6g} {gate.comparator} {gate.threshold:.6g}"
            if observed is not None
            else f"metric {gate.metric!r} was not produced"
        )
        gate_results.append(
            GateResult(
                gate_id=gate.gate_id,
                metric=gate.metric,
                observed=observed,
                comparator=gate.comparator,
                threshold=gate.threshold,
                fatal=gate.fatal,
                passed=passed,
                reason=reason,
            )
        )
    unique_failures = tuple(dict.fromkeys(failures))
    accepted = not unique_failures and all(gate.passed or not gate.fatal for gate in gate_results)
    return EvaluationReceipt(
        receipt_version="casepath.evaluation-receipt/0.1.0",
        evaluator_version=EVALUATOR_VERSION,
        case_id=contract.case_id,
        candidate_artifact_version=candidate.artifact_version,
        metrics=metrics,
        counts=counts,
        gates=tuple(gate_results),
        evaluation_failures=unique_failures,
        accepted=accepted,
    )
