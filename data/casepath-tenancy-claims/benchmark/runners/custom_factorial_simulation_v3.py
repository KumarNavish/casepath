"""Outcome-blind operating-characteristic audit for the V3 custom study.

The simulation exercises the exact frozen cluster-t estimator, hypothesis
boundaries, Holm families, and hidden-test family geometry.  It never reads
model outputs or provider credentials.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

from contracts.custom_factorial_v3 import (
    CustomFactorialProtocolV3,
    FactorialHypothesisV3,
    PairwiseHypothesisV3,
    PublicBenchmarkCohortV3,
)
from contracts.publication_v3 import StatisticalSimulationReceiptV3
from manifests.digests import digest_json, digest_paths
from runners.custom_factorial_analysis_v3 import (
    _cluster_t_v3,
    _decision,
    _holm_adjusted,
)
from validation.statistical_simulation_v3 import verify_independent_simulation_v3

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_CODE_PATHS = (
    ROOT / "contracts/custom_factorial_v3.py",
    ROOT / "runners/custom_factorial_analysis_v3.py",
)
SIMULATION_CODE_PATHS = (
    ROOT / "contracts/publication_v3.py",
    ROOT / "runners/custom_factorial_simulation_v3.py",
)
HypothesisV3 = FactorialHypothesisV3 | PairwiseHypothesisV3


def analysis_code_sha256_v3() -> str:
    return digest_paths(ROOT, list(ANALYSIS_CODE_PATHS))


def simulation_code_sha256_v3() -> str:
    return digest_paths(ROOT, list(SIMULATION_CODE_PATHS))


def _hypothesis_boundary(hypothesis: HypothesisV3) -> float:
    if hypothesis.decision_rule == "superiority":
        return hypothesis.margin
    if hypothesis.decision_rule == "noninferiority":
        return -hypothesis.margin
    return 0.0


def _wilson_interval(successes: int, trials: int) -> tuple[float, float]:
    """Two-sided 95% Wilson interval for a deterministic Monte Carlo rate."""

    if not 0 <= successes <= trials or trials <= 0:
        raise ValueError("invalid binomial counts")
    z = 1.959963984540054
    proportion = successes / trials
    denominator = 1.0 + z * z / trials
    center = (proportion + z * z / (2.0 * trials)) / denominator
    radius = (
        z
        * math.sqrt(proportion * (1.0 - proportion) / trials + z * z / (4.0 * trials * trials))
        / denominator
    )
    return max(0.0, center - radius), min(1.0, center + radius)


def _worst_case_benefit(hypothesis: HypothesisV3, protocol: CustomFactorialProtocolV3) -> float:
    if hypothesis.decision_rule == "two_sided_interaction":
        return 0.0
    if isinstance(hypothesis, PairwiseHypothesisV3):
        return -1.0
    contrast = next(
        item for item in protocol.contrasts if item.contrast_id == hypothesis.contrast_id
    )
    return sum(min(0.0, term.coefficient) for term in contrast.terms)


def _draw_case_benefits(
    *,
    rng: random.Random,
    cohort: PublicBenchmarkCohortV3,
    mean: float,
    family_standard_deviation: float,
    case_standard_deviation: float,
) -> dict[str, float]:
    hidden = tuple(item for item in cohort.cases if item.split == "hidden_test")
    family_effects = {
        family_id: rng.gauss(0.0, family_standard_deviation)
        for family_id in sorted({item.family_id for item in hidden})
    }
    return {
        item.case_id: mean
        + family_effects[item.family_id]
        + rng.gauss(0.0, case_standard_deviation)
        for item in hidden
    }


def _hypotheses(
    protocol: CustomFactorialProtocolV3,
) -> tuple[tuple[str, float, HypothesisV3], ...]:
    rows: list[tuple[str, float, HypothesisV3]] = []
    for family in protocol.multiplicity_families:
        rows.extend(
            (family.family_id, family.familywise_alpha, hypothesis)
            for hypothesis in family.factorial_hypotheses
        )
        rows.extend(
            (family.family_id, family.familywise_alpha, hypothesis)
            for hypothesis in family.pairwise_hypotheses
        )
    if len(rows) != 40 or len({item[2].hypothesis_id for item in rows}) != 40:
        raise ValueError("simulation requires the exact 40-hypothesis V3 protocol")
    return tuple(rows)


def simulate_custom_factorial_v3(
    *,
    protocol: CustomFactorialProtocolV3,
    cohort: PublicBenchmarkCohortV3,
    repetitions: int = 4000,
    seed: int = 20260821,
    target_effect: float = 0.12,
    family_standard_deviation: float = 0.06,
    case_standard_deviation: float = 0.10,
) -> StatisticalSimulationReceiptV3:
    """Simulate null, deterministic-missingness, and target-effect behavior."""

    if repetitions < 4000:
        raise ValueError("publication simulation requires at least 4,000 repetitions")
    if (
        target_effect,
        family_standard_deviation,
        case_standard_deviation,
    ) != (0.12, 0.06, 0.10):
        raise ValueError("simulation data-generating parameters are frozen")
    hidden = tuple(item for item in cohort.cases if item.split == "hidden_test")
    if (
        len(hidden) != 90
        or len({item.family_id for item in hidden}) != 17
        or len({item.domain for item in hidden}) != 3
    ):
        raise ValueError("simulation cohort must have the exact 90/17/3 hidden geometry")
    hypotheses = _hypotheses(protocol)
    by_family: dict[str, list[tuple[float, HypothesisV3]]] = defaultdict(list)
    for family_id, alpha, hypothesis in hypotheses:
        by_family[family_id].append((alpha, hypothesis))
    missing_case_ids = {
        item.case_id
        for index, item in enumerate(sorted(hidden, key=lambda row: row.case_id))
        if index % 10 == 0
    }
    if len(missing_case_ids) != 9:
        raise ValueError("deterministic missingness pattern must affect exactly nine cases")

    coverage = {hypothesis.hypothesis_id: 0 for _, _, hypothesis in hypotheses}
    target_rejections = {hypothesis.hypothesis_id: 0 for _, _, hypothesis in hypotheses}
    null_family_rejections = {family_id: 0 for family_id in by_family}
    missing_family_rejections = {family_id: 0 for family_id in by_family}
    rng = random.Random(seed)

    for _ in range(repetitions):
        null_rows: dict[str, tuple[float, bool]] = {}
        missing_rows: dict[str, tuple[float, bool]] = {}
        target_rows: dict[str, tuple[float, bool]] = {}
        for _, _, hypothesis in hypotheses:
            boundary = _hypothesis_boundary(hypothesis)
            null_benefits = _draw_case_benefits(
                rng=rng,
                cohort=cohort,
                mean=boundary,
                family_standard_deviation=family_standard_deviation,
                case_standard_deviation=case_standard_deviation,
            )
            null_result = _cluster_t_v3(null_benefits, cohort, confidence_level=0.95)
            null_p, null_margin = _decision(hypothesis, null_result)
            null_rows[hypothesis.hypothesis_id] = (null_p, null_margin)
            if null_result.confidence_lower <= boundary <= null_result.confidence_upper:
                coverage[hypothesis.hypothesis_id] += 1

            missing_benefits = dict(null_benefits)
            worst = _worst_case_benefit(hypothesis, protocol)
            for case_id in missing_case_ids:
                missing_benefits[case_id] = worst
            missing_result = _cluster_t_v3(missing_benefits, cohort, confidence_level=0.95)
            missing_p, missing_margin = _decision(hypothesis, missing_result)
            missing_rows[hypothesis.hypothesis_id] = (missing_p, missing_margin)

            target_benefits = _draw_case_benefits(
                rng=rng,
                cohort=cohort,
                mean=boundary + target_effect,
                family_standard_deviation=family_standard_deviation,
                case_standard_deviation=case_standard_deviation,
            )
            target_result = _cluster_t_v3(target_benefits, cohort, confidence_level=0.95)
            target_p, target_margin = _decision(hypothesis, target_result)
            target_rows[hypothesis.hypothesis_id] = (target_p, target_margin)

        for family_id, family_hypotheses in by_family.items():
            alpha = family_hypotheses[0][0]
            ids = [hypothesis.hypothesis_id for _, hypothesis in family_hypotheses]
            null_adjusted = _holm_adjusted({key: null_rows[key][0] for key in ids})
            missing_adjusted = _holm_adjusted({key: missing_rows[key][0] for key in ids})
            target_adjusted = _holm_adjusted({key: target_rows[key][0] for key in ids})
            if any(null_rows[key][1] and null_adjusted[key] <= alpha for key in ids):
                null_family_rejections[family_id] += 1
            if any(missing_rows[key][1] and missing_adjusted[key] <= alpha for key in ids):
                missing_family_rejections[family_id] += 1
            for key in ids:
                if target_rows[key][1] and target_adjusted[key] <= alpha:
                    target_rejections[key] += 1

    minimum_coverage = 0.925
    maximum_coverage = 0.975
    minimum_power = 0.80
    family_results: list[dict[str, Any]] = []
    for family_id, rows in sorted(by_family.items()):
        null_fwer = null_family_rejections[family_id] / repetitions
        missingness_null_fwer = missing_family_rejections[family_id] / repetitions
        null_fwer_upper = _wilson_interval(null_family_rejections[family_id], repetitions)[1]
        missingness_fwer_upper = _wilson_interval(
            missing_family_rejections[family_id], repetitions
        )[1]
        familywise_alpha = rows[0][0]
        maximum_allowed_fwer = familywise_alpha + 0.02
        family_results.append(
            {
                "family_id": family_id,
                "hypothesis_count": len(rows),
                "familywise_alpha": familywise_alpha,
                "null_fwer": null_fwer,
                "null_fwer_upper_95": null_fwer_upper,
                "missingness_null_fwer": missingness_null_fwer,
                "missingness_null_fwer_upper_95": missingness_fwer_upper,
                "maximum_allowed_fwer": maximum_allowed_fwer,
                "passed": (
                    null_fwer_upper <= maximum_allowed_fwer
                    and missingness_fwer_upper <= maximum_allowed_fwer
                ),
            }
        )
    family_by_hypothesis = {
        hypothesis.hypothesis_id: family_id for family_id, _, hypothesis in hypotheses
    }
    hypothesis_results: list[dict[str, Any]] = []
    for _, _, hypothesis in hypotheses:
        hypothesis_id = hypothesis.hypothesis_id
        interval_coverage = coverage[hypothesis_id] / repetitions
        power = target_rejections[hypothesis_id] / repetitions
        coverage_lower, coverage_upper = _wilson_interval(coverage[hypothesis_id], repetitions)
        power_lower = _wilson_interval(target_rejections[hypothesis_id], repetitions)[0]
        hypothesis_results.append(
            {
                "hypothesis_id": hypothesis_id,
                "family_id": family_by_hypothesis[hypothesis_id],
                "null_interval_coverage": interval_coverage,
                "null_interval_coverage_lower_95": coverage_lower,
                "null_interval_coverage_upper_95": coverage_upper,
                "target_effect": target_effect,
                "target_power": power,
                "target_power_lower_95": power_lower,
                "minimum_coverage": minimum_coverage,
                "maximum_coverage": maximum_coverage,
                "minimum_power": minimum_power,
                "passed": (
                    coverage_lower >= minimum_coverage
                    and coverage_upper <= maximum_coverage
                    and power_lower >= minimum_power
                ),
            }
        )
    all_passed = all(item["passed"] for item in family_results) and all(
        item["passed"] for item in hypothesis_results
    )
    if not all_passed:
        failed = [str(item["family_id"]) for item in family_results if not item["passed"]] + [
            str(item["hypothesis_id"]) for item in hypothesis_results if not item["passed"]
        ]
        diagnostics = {
            "families": family_results,
            "failed_hypotheses": [item for item in hypothesis_results if not item["passed"]],
        }
        raise ValueError(
            "V3 statistical acceptance failed: "
            f"{', '.join(failed)}; diagnostics={json.dumps(diagnostics, sort_keys=True)}"
        )
    payload: dict[str, Any] = {
        "contract": "casepath.custom-factorial-simulation/3.0.0",
        "protocol_sha256": protocol.protocol_sha256,
        "cohort_sha256": cohort.cohort_sha256,
        "analysis_code_sha256": analysis_code_sha256_v3(),
        "simulation_code_sha256": simulation_code_sha256_v3(),
        "seed": seed,
        "repetitions": repetitions,
        "hidden_case_count": 90,
        "hidden_family_count": 17,
        "tenancy_subdomain_count": 3,
        "hypothesis_count": 40,
        "family_count": 5,
        "cluster_geometry": (
            "equal_case_within_family_equal_family_within_subdomain_equal_subdomain"
        ),
        "null_data_generating_process": (
            "gaussian_family_random_effect_plus_case_residual_at_each_frozen_decision_boundary"
        ),
        "target_effect": target_effect,
        "family_standard_deviation": family_standard_deviation,
        "case_standard_deviation": case_standard_deviation,
        "missingness_pattern": (
            "deterministic_ten_percent_case_failures_scored_at_the_frozen_contrast_"
            "conservative_value"
        ),
        "family_results": family_results,
        "hypothesis_results": hypothesis_results,
        **verify_independent_simulation_v3(
            protocol=protocol,
            cohort=cohort,
            repetitions=repetitions,
            seed=seed,
            target_effect=target_effect,
            family_standard_deviation=family_standard_deviation,
            case_standard_deviation=case_standard_deviation,
            reported_families=family_results,
            reported_hypotheses=hypothesis_results,
        ),
        "all_acceptance_thresholds_passed": True,
        "runtime_model_calls": 0,
    }
    payload["receipt_sha256"] = digest_json(payload)
    return StatisticalSimulationReceiptV3.model_validate(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=4000)
    parser.add_argument("--seed", type=int, default=20260821)
    args = parser.parse_args()
    protocol = CustomFactorialProtocolV3.model_validate_json(args.protocol.read_bytes())
    cohort = PublicBenchmarkCohortV3.model_validate_json(args.cohort.read_bytes())
    receipt = simulate_custom_factorial_v3(
        protocol=protocol,
        cohort=cohort,
        repetitions=args.repetitions,
        seed=args.seed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(receipt.receipt_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
