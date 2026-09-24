"""Independent replay of the CasePath V3 operating-characteristic simulation.

This module deliberately does not import the production V3 estimator, decision,
Holm, Wilson, draw, or simulation helpers.  It shares only the repository's
audited Student-t distribution kernel.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from contracts.custom_factorial_v3 import (
    CustomFactorialProtocolV3,
    FactorialHypothesisV3,
    PairwiseHypothesisV3,
    PublicBenchmarkCohortV3,
)
from manifests.digests import digest_json, digest_paths
from runners.publication_v2 import student_t_cdf, student_t_quantile

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_CODE_PATHS = [Path(__file__).resolve()]
Hypothesis = FactorialHypothesisV3 | PairwiseHypothesisV3


def independent_verifier_code_sha256_v3() -> str:
    return digest_paths(ROOT, REFERENCE_CODE_PATHS)


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("cannot average an empty sequence")
    return math.fsum(values) / len(values)


def _reference_cluster_t(
    case_values: Mapping[str, float],
    cohort: PublicBenchmarkCohortV3,
) -> tuple[float, float, float, float, float]:
    hidden = tuple(case for case in cohort.cases if case.split == "hidden_test")
    if set(case_values) != {case.case_id for case in hidden}:
        raise ValueError("reference estimator requires every sealed case exactly once")
    nested: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for case in hidden:
        nested[case.domain][case.family_id].append(case_values[case.case_id])
    if len(nested) != 3 or sum(len(families) for families in nested.values()) != 17:
        raise ValueError("reference estimator requires the exact 3-domain/17-family geometry")
    family_means = {
        domain: {family: _mean(values) for family, values in families.items()}
        for domain, families in nested.items()
    }
    estimate = _mean(
        [_mean(list(families.values())) for _, families in sorted(family_means.items())]
    )
    components: list[tuple[float, int]] = []
    for families in family_means.values():
        values = list(families.values())
        center = _mean(values)
        variance = math.fsum((value - center) ** 2 for value in values) / (len(values) - 1)
        components.append((variance / len(values) / len(family_means) ** 2, len(values)))
    total_variance = math.fsum(component for component, _ in components)
    if total_variance == 0.0:
        degrees_of_freedom = float(sum(count - 1 for _, count in components))
    else:
        denominator = math.fsum(
            component * component / (count - 1) for component, count in components
        )
        degrees_of_freedom = total_variance * total_variance / denominator
    standard_error = math.sqrt(total_variance)
    if standard_error == 0.0:
        lower = upper = estimate
    else:
        critical = student_t_quantile(0.975, degrees_of_freedom)
        lower = estimate - critical * standard_error
        upper = estimate + critical * standard_error
    return estimate, standard_error, degrees_of_freedom, lower, upper


def _wilson(successes: int, trials: int) -> tuple[float, float]:
    z = 1.959963984540054
    proportion = successes / trials
    denominator = 1.0 + z * z / trials
    center = (proportion + z * z / (2.0 * trials)) / denominator
    radius = (
        z
        * math.sqrt(proportion * (1.0 - proportion) / trials + z * z / (4 * trials * trials))
        / denominator
    )
    return max(0.0, center - radius), min(1.0, center + radius)


def _hypotheses(
    protocol: CustomFactorialProtocolV3,
) -> tuple[tuple[str, float, Hypothesis], ...]:
    result: list[tuple[str, float, Hypothesis]] = []
    for family in protocol.multiplicity_families:
        for factorial in family.factorial_hypotheses:
            result.append((family.family_id, family.familywise_alpha, factorial))
        for pairwise in family.pairwise_hypotheses:
            result.append((family.family_id, family.familywise_alpha, pairwise))
    if len(result) != 40:
        raise ValueError("reference replay requires 40 frozen hypotheses")
    return tuple(result)


def _boundary(hypothesis: Hypothesis) -> float:
    if hypothesis.decision_rule == "superiority":
        return hypothesis.margin
    if hypothesis.decision_rule == "noninferiority":
        return -hypothesis.margin
    return 0.0


def _conservative_missing_value(
    hypothesis: Hypothesis, protocol: CustomFactorialProtocolV3
) -> float:
    if hypothesis.decision_rule == "two_sided_interaction":
        return 0.0
    if isinstance(hypothesis, PairwiseHypothesisV3):
        return -1.0
    contrast = next(
        contrast
        for contrast in protocol.contrasts
        if contrast.contrast_id == hypothesis.contrast_id
    )
    return math.fsum(min(0.0, term.coefficient) for term in contrast.terms)


def _draw(
    rng: random.Random,
    cohort: PublicBenchmarkCohortV3,
    *,
    mean: float,
    family_sd: float,
    case_sd: float,
) -> dict[str, float]:
    hidden = tuple(case for case in cohort.cases if case.split == "hidden_test")
    family_effect = {
        family_id: rng.gauss(0.0, family_sd)
        for family_id in sorted({case.family_id for case in hidden})
    }
    return {
        case.case_id: mean + family_effect[case.family_id] + rng.gauss(0.0, case_sd)
        for case in hidden
    }


def _decision(hypothesis: Hypothesis, result: tuple[float, ...]) -> tuple[float, bool]:
    estimate, standard_error, degrees_of_freedom, lower, upper = result
    if hypothesis.decision_rule == "two_sided_interaction":
        if standard_error == 0.0:
            p_value = 0.0 if estimate != 0.0 else 1.0
        else:
            statistic = abs(estimate) / standard_error
            p_value = min(1.0, 2.0 * (1.0 - student_t_cdf(statistic, degrees_of_freedom)))
        return p_value, lower > 0.0 or upper < 0.0
    boundary = _boundary(hypothesis)
    if standard_error == 0.0:
        p_value = 0.0 if estimate > boundary else 1.0
    else:
        statistic = (estimate - boundary) / standard_error
        p_value = 1.0 - student_t_cdf(statistic, degrees_of_freedom)
    return p_value, lower > boundary


def _holm(raw: Mapping[str, float]) -> dict[str, float]:
    ordered = sorted(raw, key=lambda key: (raw[key], key))
    running = 0.0
    adjusted: dict[str, float] = {}
    for index, key in enumerate(ordered):
        running = max(running, min(1.0, (len(ordered) - index) * raw[key]))
        adjusted[key] = running
    return adjusted


def independent_simulation_summary_v3(
    *,
    protocol: CustomFactorialProtocolV3,
    cohort: PublicBenchmarkCohortV3,
    repetitions: int,
    seed: int,
    target_effect: float,
    family_standard_deviation: float,
    case_standard_deviation: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    hypotheses = _hypotheses(protocol)
    grouped: dict[str, list[tuple[float, Hypothesis]]] = defaultdict(list)
    for family_id, alpha, hypothesis in hypotheses:
        grouped[family_id].append((alpha, hypothesis))
    hidden = tuple(case for case in cohort.cases if case.split == "hidden_test")
    missing_ids = {
        case.case_id
        for index, case in enumerate(sorted(hidden, key=lambda row: row.case_id))
        if index % 10 == 0
    }
    coverage = {hypothesis.hypothesis_id: 0 for _, _, hypothesis in hypotheses}
    power = {hypothesis.hypothesis_id: 0 for _, _, hypothesis in hypotheses}
    null_rejections = {family_id: 0 for family_id in grouped}
    missing_rejections = {family_id: 0 for family_id in grouped}
    rng = random.Random(seed)

    for _ in range(repetitions):
        null_rows: dict[str, tuple[float, bool]] = {}
        missing_rows: dict[str, tuple[float, bool]] = {}
        target_rows: dict[str, tuple[float, bool]] = {}
        for _, _, hypothesis in hypotheses:
            boundary = _boundary(hypothesis)
            null_values = _draw(
                rng,
                cohort,
                mean=boundary,
                family_sd=family_standard_deviation,
                case_sd=case_standard_deviation,
            )
            null_result = _reference_cluster_t(null_values, cohort)
            null_rows[hypothesis.hypothesis_id] = _decision(hypothesis, null_result)
            if null_result[3] <= boundary <= null_result[4]:
                coverage[hypothesis.hypothesis_id] += 1
            missing_values = dict(null_values)
            conservative = _conservative_missing_value(hypothesis, protocol)
            for case_id in missing_ids:
                missing_values[case_id] = conservative
            missing_rows[hypothesis.hypothesis_id] = _decision(
                hypothesis, _reference_cluster_t(missing_values, cohort)
            )
            target_values = _draw(
                rng,
                cohort,
                mean=boundary + target_effect,
                family_sd=family_standard_deviation,
                case_sd=case_standard_deviation,
            )
            target_rows[hypothesis.hypothesis_id] = _decision(
                hypothesis, _reference_cluster_t(target_values, cohort)
            )

        for family_id, family_hypotheses in grouped.items():
            alpha = family_hypotheses[0][0]
            ids = [hypothesis.hypothesis_id for _, hypothesis in family_hypotheses]
            null_adjusted = _holm({key: null_rows[key][0] for key in ids})
            missing_adjusted = _holm({key: missing_rows[key][0] for key in ids})
            target_adjusted = _holm({key: target_rows[key][0] for key in ids})
            if any(null_rows[key][1] and null_adjusted[key] <= alpha for key in ids):
                null_rejections[family_id] += 1
            if any(missing_rows[key][1] and missing_adjusted[key] <= alpha for key in ids):
                missing_rejections[family_id] += 1
            for key in ids:
                if target_rows[key][1] and target_adjusted[key] <= alpha:
                    power[key] += 1

    families: list[dict[str, Any]] = []
    for family_id, rows in sorted(grouped.items()):
        alpha = rows[0][0]
        null_fwer = null_rejections[family_id] / repetitions
        missing_fwer = missing_rejections[family_id] / repetitions
        null_upper = _wilson(null_rejections[family_id], repetitions)[1]
        missing_upper = _wilson(missing_rejections[family_id], repetitions)[1]
        maximum = alpha + 0.02
        families.append(
            {
                "family_id": family_id,
                "hypothesis_count": len(rows),
                "familywise_alpha": alpha,
                "null_fwer": null_fwer,
                "null_fwer_upper_95": null_upper,
                "missingness_null_fwer": missing_fwer,
                "missingness_null_fwer_upper_95": missing_upper,
                "maximum_allowed_fwer": maximum,
                "passed": null_upper <= maximum and missing_upper <= maximum,
            }
        )
    family_membership = {
        hypothesis.hypothesis_id: family_id for family_id, _, hypothesis in hypotheses
    }
    hypothesis_rows: list[dict[str, Any]] = []
    for _, _, hypothesis in hypotheses:
        hypothesis_id = hypothesis.hypothesis_id
        observed_coverage = coverage[hypothesis_id] / repetitions
        observed_power = power[hypothesis_id] / repetitions
        coverage_lower, coverage_upper = _wilson(coverage[hypothesis_id], repetitions)
        power_lower = _wilson(power[hypothesis_id], repetitions)[0]
        hypothesis_rows.append(
            {
                "hypothesis_id": hypothesis_id,
                "family_id": family_membership[hypothesis_id],
                "null_interval_coverage": observed_coverage,
                "null_interval_coverage_lower_95": coverage_lower,
                "null_interval_coverage_upper_95": coverage_upper,
                "target_effect": target_effect,
                "target_power": observed_power,
                "target_power_lower_95": power_lower,
                "minimum_coverage": 0.925,
                "maximum_coverage": 0.975,
                "minimum_power": 0.80,
                "passed": (
                    coverage_lower >= 0.925 and coverage_upper <= 0.975 and power_lower >= 0.80
                ),
            }
        )
    return families, hypothesis_rows


def verify_independent_simulation_v3(
    *,
    protocol: CustomFactorialProtocolV3,
    cohort: PublicBenchmarkCohortV3,
    repetitions: int,
    seed: int,
    target_effect: float,
    family_standard_deviation: float,
    case_standard_deviation: float,
    reported_families: Sequence[Mapping[str, Any]],
    reported_hypotheses: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    families, hypotheses = independent_simulation_summary_v3(
        protocol=protocol,
        cohort=cohort,
        repetitions=repetitions,
        seed=seed,
        target_effect=target_effect,
        family_standard_deviation=family_standard_deviation,
        case_standard_deviation=case_standard_deviation,
    )

    def matches(left: Any, right: Any) -> bool:
        if isinstance(left, float) and isinstance(right, int | float):
            return math.isclose(left, float(right), rel_tol=5e-12, abs_tol=5e-12)
        return bool(left == right)

    expected_families = {row["family_id"]: row for row in families}
    expected_hypotheses = {row["hypothesis_id"]: row for row in hypotheses}
    family_matches = 0
    hypothesis_matches = 0
    value_matches = 0
    for reported in reported_families:
        expected = expected_families.get(reported["family_id"])
        if expected is not None and set(expected) == set(reported):
            row_matches = sum(matches(expected[key], reported[key]) for key in expected)
            value_matches += row_matches
            family_matches += row_matches == len(expected)
    for reported in reported_hypotheses:
        expected = expected_hypotheses.get(reported["hypothesis_id"])
        if expected is not None and set(expected) == set(reported):
            row_matches = sum(matches(expected[key], reported[key]) for key in expected)
            value_matches += row_matches
            hypothesis_matches += row_matches == len(expected)
    if (family_matches, hypothesis_matches, value_matches) != (5, 40, 525):
        raise ValueError(
            "independent simulation replay differs from the production summary: "
            f"families={family_matches}/5 hypotheses={hypothesis_matches}/40 "
            f"values={value_matches}/525"
        )
    return {
        "independent_verifier_code_sha256": independent_verifier_code_sha256_v3(),
        "independent_reference_summary_sha256": digest_json(
            {"family_results": families, "hypothesis_results": hypotheses}
        ),
        "independent_verification_scope": (
            "rng_family_case_geometry_estimator_decisions_holm_wilson_reimplemented_"
            "shared_student_t_kernel"
        ),
        "independent_family_result_match_count": family_matches,
        "independent_hypothesis_result_match_count": hypothesis_matches,
        "independent_reported_value_match_count": value_matches,
        "independent_replay_passed": True,
    }
