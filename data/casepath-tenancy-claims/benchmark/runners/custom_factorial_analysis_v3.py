"""Locked analysis for the internal CasePath-150 2x2 factorial diagnostic."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from pathlib import Path
from statistics import fmean
from typing import Any

from contracts.custom_factorial_v3 import (
    AbsoluteFloorResultV3,
    CompleteCaseSensitivityV3,
    CustomFactorialAnalysisReceiptV3,
    CustomFactorialProtocolV3,
    CustomOutcomeBundleV3,
    EndpointIdV3,
    FactorialEstimateV3,
    FactorialHypothesisV3,
    MediationResultV3,
    PairwiseHypothesisV3,
    PublicBenchmarkCohortV3,
    PublicBenchmarkManifestV3,
    PublicBenchmarkReleaseGateV3,
)
from contracts.custom_run import CustomRunCompletenessReceiptV3
from contracts.publication_v3 import PublicationStudyLockV3
from manifests.digests import digest_json
from runners.publication_v2 import (
    ClusterTResult,
    student_t_cdf,
    student_t_quantile,
)
from scorers.identity import scorer_code_sha256

ROOT = Path(__file__).resolve().parents[1]

FINAL_CONDITIONS_V3 = (
    "PF_TYPED_V3",
    "PF_PLAIN_V3",
    "DIRECT_TYPED_V3",
    "DIRECT_PLAIN_V3",
    "EXIDE_V3",
    "DOCUMENT_FIRST_V3",
    "VERIFY_PF_TYPED_V3",
    "ONTOLOGY_RULE_HEURISTIC_V3",
)
FACTORIAL_CONDITIONS_V3 = FINAL_CONDITIONS_V3[:4]
ENDPOINTS_V3: tuple[EndpointIdV3, ...] = (
    "behavioral_valid_path_rate",
    "branch_predicate_accuracy",
    "required_node_recall",
    "required_edge_recall",
    "critical_evidence_recall",
    "unnecessary_document_rate",
    "document_state_accuracy",
    "valid_chain_precision",
    "fact_chain_completeness",
    "evidence_obligation_completeness",
    "source_grounding_exactness",
)
MEDIATION_ENDPOINTS_V3: tuple[EndpointIdV3, ...] = (
    "critical_evidence_recall",
    "unnecessary_document_rate",
    "valid_chain_precision",
    "fact_chain_completeness",
    "evidence_obligation_completeness",
)


def _hidden_case_ids(cohort: PublicBenchmarkCohortV3) -> tuple[str, ...]:
    return tuple(item.case_id for item in cohort.cases if item.split == "hidden_test")


def _cluster_t_v3(
    case_benefits: Mapping[str, float],
    cohort: PublicBenchmarkCohortV3,
    *,
    confidence_level: float,
    included_domain: str | None = None,
    excluded_family: str | None = None,
    included_case_ids: set[str] | None = None,
) -> ClusterTResult:
    """Equal-case/family/domain cluster-t estimator on sealed test families."""

    eligible = [
        case
        for case in cohort.cases
        if case.split == "hidden_test"
        and (included_domain is None or case.domain == included_domain)
        and (excluded_family is None or case.family_id != excluded_family)
        and (included_case_ids is None or case.case_id in included_case_ids)
    ]
    expected_ids = {case.case_id for case in eligible}
    supplied = {
        case_id: value for case_id, value in case_benefits.items() if case_id in expected_ids
    }
    if set(supplied) != expected_ids:
        raise ValueError("paired benefits do not cover the exact sealed-test subset")
    clusters: dict[str, dict[str, list[float]]] = {}
    for case in eligible:
        clusters.setdefault(case.domain, {}).setdefault(case.family_id, []).append(
            supplied[case.case_id]
        )
    if not clusters or any(len(families) < 2 for families in clusters.values()):
        raise ValueError("each retained domain requires at least two sealed-test families")
    family_means = {
        domain: {family: fmean(values) for family, values in families.items()}
        for domain, families in clusters.items()
    }
    estimate = fmean(fmean(families.values()) for _, families in sorted(family_means.items()))
    domain_count = len(family_means)
    components: list[tuple[float, int]] = []
    for families in family_means.values():
        values = tuple(families.values())
        mean = fmean(values)
        variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
        components.append((variance / len(values) / domain_count**2, len(values)))
    total_variance = sum(value for value, _ in components)
    if total_variance == 0.0:
        degrees_of_freedom = float(sum(count - 1 for _, count in components))
    else:
        denominator = sum(value * value / (count - 1) for value, count in components)
        degrees_of_freedom = total_variance * total_variance / denominator
    standard_error = math.sqrt(total_variance)
    if standard_error == 0.0:
        lower = upper = estimate
    else:
        critical = student_t_quantile(0.5 + confidence_level / 2.0, degrees_of_freedom)
        lower = estimate - critical * standard_error
        upper = estimate + critical * standard_error
    return ClusterTResult(
        estimate=estimate,
        standard_error=standard_error,
        degrees_of_freedom=degrees_of_freedom,
        confidence_lower=lower,
        confidence_upper=upper,
        analyzed_cases=len(eligible),
        analyzed_families=sum(len(families) for families in family_means.values()),
        analyzed_domains=domain_count,
    )


def _holm_adjusted(raw: Mapping[str, float]) -> dict[str, float]:
    ordered = sorted(raw, key=lambda key: (raw[key], key))
    adjusted: dict[str, float] = {}
    running = 0.0
    total = len(ordered)
    for rank, key in enumerate(ordered):
        running = max(running, min(1.0, (total - rank) * raw[key]))
        adjusted[key] = running
    return adjusted


def _one_sided(result: ClusterTResult, boundary: float) -> float:
    if result.standard_error == 0.0:
        return 0.0 if result.estimate > boundary else 1.0
    statistic = (result.estimate - boundary) / result.standard_error
    return 1.0 - student_t_cdf(statistic, result.degrees_of_freedom)


def _two_sided_zero(result: ClusterTResult) -> float:
    if result.standard_error == 0.0:
        return 0.0 if result.estimate != 0.0 else 1.0
    statistic = abs(result.estimate) / result.standard_error
    return min(1.0, 2.0 * (1.0 - student_t_cdf(statistic, result.degrees_of_freedom)))


def _score(value: float | None, status: str, *, direction: str) -> float:
    if status == "observed":
        assert value is not None
        return value
    return 0.0 if direction == "higher" else 1.0


def _factorial_case_effects(
    *,
    hypothesis: FactorialHypothesisV3,
    coefficients: Mapping[str, float],
    values: Mapping[tuple[str, str, str], tuple[float | None, str]],
    case_ids: Iterable[str],
) -> dict[str, float]:
    sign = 1.0 if hypothesis.benefit_direction == "higher" else -1.0
    effects: dict[str, float] = {}
    for case_id in case_ids:
        rows = {
            condition: values[(case_id, condition, hypothesis.endpoint_id)]
            for condition in coefficients
        }
        if any(status != "observed" for _, status in rows.values()):
            effects[case_id] = (
                0.0
                if hypothesis.decision_rule == "two_sided_interaction"
                else sum(min(0.0, sign * coefficient) for coefficient in coefficients.values())
            )
            continue
        effects[case_id] = sign * sum(
            coefficient * _score(*rows[condition], direction=hypothesis.benefit_direction)
            for condition, coefficient in coefficients.items()
        )
    return effects


def _pairwise_case_effects(
    *,
    hypothesis: PairwiseHypothesisV3,
    values: Mapping[tuple[str, str, str], tuple[float | None, str]],
    case_ids: Iterable[str],
) -> dict[str, float]:
    sign = 1.0 if hypothesis.benefit_direction == "higher" else -1.0
    effects: dict[str, float] = {}
    for case_id in case_ids:
        treatment = values[(case_id, hypothesis.treatment, hypothesis.endpoint_id)]
        control = values[(case_id, hypothesis.control, hypothesis.endpoint_id)]
        if treatment[1] != "observed" or control[1] != "observed":
            effects[case_id] = -1.0
            continue
        effects[case_id] = sign * (
            _score(*treatment, direction=hypothesis.benefit_direction)
            - _score(*control, direction=hypothesis.benefit_direction)
        )
    return effects


def _decision(
    hypothesis: FactorialHypothesisV3 | PairwiseHypothesisV3,
    result: ClusterTResult,
) -> tuple[float, bool]:
    if hypothesis.decision_rule == "superiority":
        return _one_sided(result, hypothesis.margin), result.confidence_lower > hypothesis.margin
    if hypothesis.decision_rule == "noninferiority":
        return _one_sided(result, -hypothesis.margin), (
            result.confidence_lower > -hypothesis.margin
        )
    return _two_sided_zero(result), (result.confidence_lower > 0.0 or result.confidence_upper < 0.0)


def _required_conditions(
    hypothesis: FactorialHypothesisV3 | PairwiseHypothesisV3,
    coefficients: Mapping[str, Mapping[str, float]],
) -> tuple[str, ...]:
    if isinstance(hypothesis, FactorialHypothesisV3):
        return tuple(coefficients[hypothesis.contrast_id])
    return (hypothesis.treatment, hypothesis.control)


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Small deterministic Gaussian elimination with partial pivoting."""

    size = len(vector)
    augmented = [[*row, value] for row, value in zip(matrix, vector, strict=True)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            raise ValueError("mediation design matrix is singular")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        scale = augmented[column][column]
        augmented[column] = [value / scale for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                current - factor * source
                for current, source in zip(augmented[row], augmented[column], strict=True)
            ]
    return [augmented[row][-1] for row in range(size)]


def _weighted_mediator_slope(
    *,
    endpoint_id: EndpointIdV3,
    cohort: PublicBenchmarkCohortV3,
    final_values: Mapping[tuple[str, str, str], tuple[float | None, str]],
    mediator_values: Mapping[tuple[str, str], tuple[float | None, str]],
    excluded_family: str | None = None,
) -> float:
    family_sizes: dict[str, int] = {}
    domain_families: dict[str, set[str]] = {}
    for case in cohort.cases:
        if case.split != "hidden_test":
            continue
        family_sizes[case.family_id] = family_sizes.get(case.family_id, 0) + 1
        domain_families.setdefault(case.domain, set()).add(case.family_id)
    rows: list[tuple[list[float], float, float]] = []
    for case in cohort.cases:
        if case.split != "hidden_test" or case.family_id == excluded_family:
            continue
        weight = (
            1.0
            / 3.0
            / len(domain_families[case.domain] - ({excluded_family} if excluded_family else set()))
            / family_sizes[case.family_id]
            / 4.0
        )
        domain_dummies = [
            float(case.domain == "lease_termination_dispute"),
            float(case.domain == "rent_increase_dispute"),
        ]
        for condition in FACTORIAL_CONDITIONS_V3:
            order = float(condition.startswith("PF_"))
            representation = float("_TYPED_" in condition)
            mediator = _score(*mediator_values[(case.case_id, condition)], direction="higher")
            outcome_status = final_values[(case.case_id, condition, endpoint_id)]
            direction = "lower" if endpoint_id == "unnecessary_document_rate" else "higher"
            outcome = _score(*outcome_status, direction=direction)
            if direction == "lower":
                outcome = -outcome
            design = [
                1.0,
                mediator,
                order,
                representation,
                order * representation,
                *domain_dummies,
            ]
            rows.append((design, outcome, weight))
    size = len(rows[0][0])
    gram = [[0.0 for _ in range(size)] for _ in range(size)]
    rhs = [0.0 for _ in range(size)]
    for design, outcome, weight in rows:
        for left in range(size):
            rhs[left] += weight * design[left] * outcome
            for right in range(size):
                gram[left][right] += weight * design[left] * design[right]
    return _solve(gram, rhs)[1]


def _mediation_product(
    *,
    endpoint_id: EndpointIdV3,
    cohort: PublicBenchmarkCohortV3,
    contrast_coefficients: Mapping[str, float],
    final_values: Mapping[tuple[str, str, str], tuple[float | None, str]],
    mediator_values: Mapping[tuple[str, str], tuple[float | None, str]],
    excluded_family: str | None = None,
) -> tuple[float, float, float]:
    case_ids = list(_hidden_case_ids(cohort))
    mediator_effects = {
        case_id: sum(
            coefficient * _score(*mediator_values[(case_id, condition)], direction="higher")
            for condition, coefficient in contrast_coefficients.items()
        )
        for case_id in case_ids
    }
    order_to_mediator = _cluster_t_v3(
        mediator_effects,
        cohort,
        confidence_level=0.95,
        excluded_family=excluded_family,
    ).estimate
    slope = _weighted_mediator_slope(
        endpoint_id=endpoint_id,
        cohort=cohort,
        final_values=final_values,
        mediator_values=mediator_values,
        excluded_family=excluded_family,
    )
    return order_to_mediator, slope, order_to_mediator * slope


def analyze_custom_factorial_v3(
    *,
    protocol: CustomFactorialProtocolV3,
    cohort: PublicBenchmarkCohortV3,
    bundle: CustomOutcomeBundleV3,
    study_lock: PublicationStudyLockV3,
    manifest: PublicBenchmarkManifestV3,
    release_gate: PublicBenchmarkReleaseGateV3,
    run_completeness: CustomRunCompletenessReceiptV3,
) -> CustomFactorialAnalysisReceiptV3:
    if bundle.custom_protocol_sha256 != protocol.protocol_sha256:
        raise ValueError("outcome bundle belongs to another custom protocol")
    if bundle.cohort_sha256 != cohort.cohort_sha256:
        raise ValueError("outcome bundle belongs to another cohort")
    scorer_sha256 = scorer_code_sha256(ROOT)
    if (
        bundle.publication_lock_sha256 != study_lock.lock_sha256
        or bundle.release_manifest_sha256 != manifest.manifest_sha256
        or bundle.release_gate_receipt_sha256 != release_gate.receipt_sha256
        or release_gate.manifest_sha256 != manifest.manifest_sha256
        or bundle.evaluator_bundle_sha256 != manifest.evaluator_bundle_sha256
        or bundle.scorer_code_sha256 != scorer_sha256
        or bundle.run_completeness_receipt_sha256 != run_completeness.receipt_sha256
        or run_completeness.publication_lock_sha256 != study_lock.lock_sha256
        or run_completeness.custom_protocol_sha256 != protocol.protocol_sha256
        or not run_completeness.complete
        or not run_completeness.outcome_scoring_ready
        or study_lock.custom_release_manifest_sha256 != manifest.manifest_sha256
        or study_lock.custom_release_gate_receipt_sha256 != release_gate.receipt_sha256
        or study_lock.custom_evaluator_bundle_sha256 != manifest.evaluator_bundle_sha256
    ):
        raise ValueError("analysis inputs differ from the locked run and evaluator")
    all_case_ids = tuple(case.case_id for case in cohort.cases)
    case_ids = _hidden_case_ids(cohort)
    if len(all_case_ids) != 150 or len(set(all_case_ids)) != 150:
        raise ValueError("factorial analysis requires 150 unique locked cases")
    if len(case_ids) != 90 or len(set(case_ids)) != 90:
        raise ValueError("factorial inference requires 90 unique sealed-test cases")

    final_values: dict[tuple[str, str, str], tuple[float | None, str]] = {
        (item.case_id, item.condition, item.endpoint_id): (item.value, item.status)
        for item in bundle.outcomes
    }
    expected_final = {
        (case_id, condition, endpoint)
        for case_id in all_case_ids
        for condition in FINAL_CONDITIONS_V3
        for endpoint in ENDPOINTS_V3
    }
    if set(final_values) != expected_final:
        raise ValueError("final outcomes do not form the exact 150 x 8 x 11 grid")
    mediator_values: dict[tuple[str, str], tuple[float | None, str]] = {
        (item.case_id, item.condition): (item.value, item.status)
        for item in bundle.mediator_outcomes
    }
    expected_mediator = {
        (case_id, condition) for case_id in all_case_ids for condition in FACTORIAL_CONDITIONS_V3
    }
    if set(mediator_values) != expected_mediator:
        raise ValueError("mediator outcomes do not form the exact 150 x 4 grid")

    coefficients: dict[str, dict[str, float]] = {
        contrast.contrast_id: {term.condition_id: term.coefficient for term in contrast.terms}
        for contrast in protocol.contrasts
    }
    staged: dict[str, tuple[str, Any, ClusterTResult, float, bool]] = {}
    for family in protocol.multiplicity_families:
        for factorial_hypothesis in family.factorial_hypotheses:
            case_effects = _factorial_case_effects(
                hypothesis=factorial_hypothesis,
                coefficients=coefficients[factorial_hypothesis.contrast_id],
                values=final_values,
                case_ids=case_ids,
            )
            result = _cluster_t_v3(case_effects, cohort, confidence_level=0.95)
            raw_p, margin_passed = _decision(factorial_hypothesis, result)
            staged[factorial_hypothesis.hypothesis_id] = (
                family.family_id,
                factorial_hypothesis,
                result,
                raw_p,
                margin_passed,
            )
        for pairwise_hypothesis in family.pairwise_hypotheses:
            case_effects = _pairwise_case_effects(
                hypothesis=pairwise_hypothesis,
                values=final_values,
                case_ids=case_ids,
            )
            result = _cluster_t_v3(case_effects, cohort, confidence_level=0.95)
            raw_p, margin_passed = _decision(pairwise_hypothesis, result)
            staged[pairwise_hypothesis.hypothesis_id] = (
                family.family_id,
                pairwise_hypothesis,
                result,
                raw_p,
                margin_passed,
            )

    estimates: list[FactorialEstimateV3] = []
    for family in protocol.multiplicity_families:
        family_rows = [row for row in staged.values() if row[0] == family.family_id]
        adjusted = _holm_adjusted({row[1].hypothesis_id: row[3] for row in family_rows})
        for family_id, hypothesis, result, raw_p, margin_passed in family_rows:
            if (
                result.analyzed_cases,
                result.analyzed_families,
                result.analyzed_domains,
            ) != (90, 17, 3):
                raise ValueError("headline estimates must use 90 cases in 17 sealed families")
            adjusted_p = adjusted[hypothesis.hypothesis_id]
            multiplicity_passed = adjusted_p <= family.familywise_alpha
            estimates.append(
                FactorialEstimateV3(
                    hypothesis_id=hypothesis.hypothesis_id,
                    family_id=family_id,
                    effect_kind=(
                        "factorial" if isinstance(hypothesis, FactorialHypothesisV3) else "pairwise"
                    ),
                    contrast_id=(
                        hypothesis.contrast_id
                        if isinstance(hypothesis, FactorialHypothesisV3)
                        else f"{hypothesis.treatment}_MINUS_{hypothesis.control}"
                    ),
                    endpoint_id=hypothesis.endpoint_id,
                    benefit_estimate=result.estimate,
                    confidence_lower=result.confidence_lower,
                    confidence_upper=result.confidence_upper,
                    raw_p_value=raw_p,
                    adjusted_p_value=adjusted_p,
                    margin=hypothesis.margin,
                    decision_rule=hypothesis.decision_rule,
                    margin_passed=margin_passed,
                    multiplicity_passed=multiplicity_passed,
                    passed=margin_passed and multiplicity_passed,
                    analyzed_cases=90,
                    analyzed_families=17,
                    analyzed_domains=3,
                )
            )

    sensitivity_staged: dict[
        str,
        tuple[
            str,
            FactorialHypothesisV3 | PairwiseHypothesisV3,
            set[str],
            ClusterTResult | None,
            float | None,
        ],
    ] = {}
    for family in protocol.multiplicity_families:
        hypotheses: tuple[FactorialHypothesisV3 | PairwiseHypothesisV3, ...] = (
            *family.factorial_hypotheses,
            *family.pairwise_hypotheses,
        )
        for hypothesis in hypotheses:
            required_conditions = _required_conditions(hypothesis, coefficients)
            complete_ids = {
                case_id
                for case_id in case_ids
                if all(
                    final_values[(case_id, condition, hypothesis.endpoint_id)][1] == "observed"
                    for condition in required_conditions
                )
            }
            try:
                if isinstance(hypothesis, FactorialHypothesisV3):
                    effects = _factorial_case_effects(
                        hypothesis=hypothesis,
                        coefficients=coefficients[hypothesis.contrast_id],
                        values=final_values,
                        case_ids=complete_ids,
                    )
                else:
                    effects = _pairwise_case_effects(
                        hypothesis=hypothesis,
                        values=final_values,
                        case_ids=complete_ids,
                    )
                sensitivity_result = _cluster_t_v3(
                    effects,
                    cohort,
                    confidence_level=0.95,
                    included_case_ids=complete_ids,
                )
                sensitivity_p = _decision(hypothesis, sensitivity_result)[0]
            except ValueError:
                sensitivity_result = None
                sensitivity_p = None
            sensitivity_staged[hypothesis.hypothesis_id] = (
                family.family_id,
                hypothesis,
                complete_ids,
                sensitivity_result,
                sensitivity_p,
            )

    sensitivity_rows: list[CompleteCaseSensitivityV3] = []
    for family in protocol.multiplicity_families:
        sensitivity_family_rows = [
            row for row in sensitivity_staged.values() if row[0] == family.family_id
        ]
        estimable_p = {
            row[1].hypothesis_id: row[4] for row in sensitivity_family_rows if row[4] is not None
        }
        adjusted = _holm_adjusted(
            {key: value for key, value in estimable_p.items() if value is not None}
        )
        for (
            family_id,
            hypothesis,
            complete_ids,
            sensitivity_result,
            sensitivity_raw_p,
        ) in sensitivity_family_rows:
            retained_cases = [case for case in cohort.cases if case.case_id in complete_ids]
            sensitivity_rows.append(
                CompleteCaseSensitivityV3(
                    hypothesis_id=hypothesis.hypothesis_id,
                    family_id=family_id,
                    complete_case_count=len(complete_ids),
                    complete_family_count=len({case.family_id for case in retained_cases}),
                    complete_domain_count=len({case.domain for case in retained_cases}),
                    estimable=sensitivity_result is not None,
                    benefit_estimate=(
                        None if sensitivity_result is None else sensitivity_result.estimate
                    ),
                    confidence_lower=(
                        None if sensitivity_result is None else sensitivity_result.confidence_lower
                    ),
                    confidence_upper=(
                        None if sensitivity_result is None else sensitivity_result.confidence_upper
                    ),
                    raw_p_value=sensitivity_raw_p,
                    adjusted_p_value=(
                        None if sensitivity_result is None else adjusted[hypothesis.hypothesis_id]
                    ),
                    role="sensitivity_only_cannot_rescue",
                )
            )

    floor_results: list[AbsoluteFloorResultV3] = []
    for floor in protocol.absolute_floors:
        scores = {
            case_id: _score(
                *final_values[(case_id, "PF_TYPED_V3", floor.endpoint_id)],
                direction=floor.direction,
            )
            for case_id in case_ids
        }
        for scope in (
            "pooled",
            "defect_mold_heating",
            "lease_termination_dispute",
            "rent_increase_dispute",
        ):
            result = _cluster_t_v3(
                scores,
                cohort,
                confidence_level=0.95,
                included_domain=None if scope == "pooled" else scope,
            )
            passed = (
                result.confidence_lower >= floor.threshold
                if floor.direction == "higher"
                else result.confidence_upper <= floor.threshold
            )
            floor_results.append(
                AbsoluteFloorResultV3(
                    condition="PF_TYPED_V3",
                    endpoint_id=floor.endpoint_id,
                    scope=scope,
                    direction=floor.direction,
                    threshold=floor.threshold,
                    estimate=result.estimate,
                    confidence_lower=result.confidence_lower,
                    confidence_upper=result.confidence_upper,
                    passed=passed,
                )
            )

    order_coefficients = coefficients["ORDER_MAIN"]
    family_ids = sorted({case.family_id for case in cohort.cases if case.split == "hidden_test"})
    mediation: list[MediationResultV3] = []
    for endpoint in MEDIATION_ENDPOINTS_V3:
        try:
            order_to_mediator, slope, product = _mediation_product(
                endpoint_id=endpoint,
                cohort=cohort,
                contrast_coefficients=order_coefficients,
                final_values=final_values,
                mediator_values=mediator_values,
            )
            deletions = [
                _mediation_product(
                    endpoint_id=endpoint,
                    cohort=cohort,
                    contrast_coefficients=order_coefficients,
                    final_values=final_values,
                    mediator_values=mediator_values,
                    excluded_family=family_id,
                )[2]
                for family_id in family_ids
            ]
        except ValueError:
            mediation.append(
                MediationResultV3(
                    endpoint_id=endpoint,
                    estimable=False,
                    family_deletions=17,
                    nonestimable_reason="zero_mediator_variance_or_singular_design",
                    interpretation="mechanism_consistency_only_not_causal",
                )
            )
            continue
        deletion_mean = fmean(deletions)
        standard_error = math.sqrt(
            (len(deletions) - 1)
            / len(deletions)
            * sum((value - deletion_mean) ** 2 for value in deletions)
        )
        critical = student_t_quantile(0.975, len(deletions) - 1)
        mediation.append(
            MediationResultV3(
                endpoint_id=endpoint,
                estimable=True,
                order_to_mediator=order_to_mediator,
                adjusted_mediator_to_outcome=slope,
                product_estimate=product,
                jackknife_lower=product - critical * standard_error,
                jackknife_upper=product + critical * standard_error,
                family_deletions=17,
                nonestimable_reason=None,
                interpretation="mechanism_consistency_only_not_causal",
            )
        )

    estimate_map = {item.hypothesis_id: item for item in estimates}
    benchmark_order = all(
        estimate_map[item].passed
        for item in (
            "H-ORDER-PATH",
            "H-ORDER-BRANCH",
            "H-ORDER-CER",
            "H-ORDER-UDR",
        )
    )
    absolute_quality = all(item.passed for item in floor_results)
    payload: dict[str, Any] = {
        "contract": "casepath.custom-factorial-analysis/3.0.0",
        "publication_lock_sha256": bundle.publication_lock_sha256,
        "custom_protocol_sha256": protocol.protocol_sha256,
        "cohort_sha256": cohort.cohort_sha256,
        "outcome_bundle_sha256": bundle.bundle_sha256,
        "release_manifest_sha256": manifest.manifest_sha256,
        "release_gate_receipt_sha256": release_gate.receipt_sha256,
        "evaluator_bundle_sha256": manifest.evaluator_bundle_sha256,
        "scorer_code_sha256": scorer_sha256,
        "run_completeness_receipt_sha256": run_completeness.receipt_sha256,
        "estimates": [item.model_dump(mode="json") for item in estimates],
        "absolute_floor_results": [item.model_dump(mode="json") for item in floor_results],
        "mediation_results": [item.model_dump(mode="json") for item in mediation],
        "complete_case_sensitivity": [item.model_dump(mode="json") for item in sensitivity_rows],
        "complete_case_sensitivity_reported": True,
        "complete_case_can_rescue": False,
        "benchmark_order_claim_passed": benchmark_order,
        "absolute_quality_passed": absolute_quality,
        "benchmark_coprimary_passed": benchmark_order and absolute_quality,
        "paper_headline_eligible": benchmark_order and absolute_quality,
        "paper_role": "casepath_benchmark_coprimary",
        "public_native_results_required_for_full_paper_claim": True,
        "human_evidence_used": False,
    }
    payload["receipt_sha256"] = digest_json(payload)
    return CustomFactorialAnalysisReceiptV3.model_validate(payload)
