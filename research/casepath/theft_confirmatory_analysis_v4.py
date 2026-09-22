from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping, Sequence

SEED = 20260917
BOOTSTRAP_DRAWS = 10_000
PAIRING_DRAWS = 5_000
COMPARATORS = ("b1_direct", "b3_representation_then_list", "b6_evidence_first")
B5 = "b5_process_compiled"


def load_rows(b5_path: Path, baseline_path: Path) -> list[dict]:
    b5 = json.loads(b5_path.read_text())
    for row in b5:
        row["arm"] = B5
    return b5 + json.loads(baseline_path.read_text())


def load_pairs(benchmark_path: Path) -> dict[str, dict]:
    benchmark = json.loads(benchmark_path.read_text())
    if benchmark.get("contract") != "casepath.theft-causal-branch-benchmark/2.0.0":
        raise ValueError("route-aware benchmark v2 is required")
    pairs = {pair["pair_id"]: pair for pair in benchmark["pairs"]}
    if len(pairs) != len(benchmark["pairs"]):
        raise ValueError("duplicate benchmark pair ids")
    return pairs


def best_realization(predicted: Iterable[str], pair: Mapping[str, object]) -> tuple[set[str], dict]:
    prediction = set(predicted)
    options = [set(option) for option in pair.get("acceptable_signed_deltas") or []]
    if not options:
        raise ValueError(f"pair {pair.get('pair_id')} has no acceptable gold realization")
    scored = []
    for gold in options:
        tp = len(prediction & gold)
        denominator = len(prediction) + len(gold)
        f1 = 1.0 if denominator == 0 else 2 * tp / denominator
        precision = tp / len(prediction) if prediction else 0.0
        recall = tp / len(gold) if gold else 0.0
        key = (f1, tp, precision, recall, -len(gold), tuple(sorted(gold)))
        scored.append((key, gold))
    _, selected = max(scored)
    tp = len(prediction & selected)
    denominator = len(prediction) + len(selected)
    return selected, {
        "tp": tp,
        "predicted": len(prediction),
        "gold": len(selected),
        "precision": tp / len(prediction) if prediction else 0.0,
        "recall": tp / len(selected) if selected else 0.0,
        "f1": 1.0 if denominator == 0 else 2 * tp / denominator,
        "exact": prediction == selected,
    }


def evaluate_row(row: Mapping[str, object], pair: Mapping[str, object]) -> dict:
    prediction = set(row.get("predicted_signed_delta") or [])
    selected, metrics = best_realization(prediction, pair)
    return {
        **metrics,
        "pair_id": row["pair_id"],
        "scenario": pair["scenario"],
        "prediction": prediction,
        "selected_gold": selected,
        "acceptable_gold_count": len(pair.get("acceptable_signed_deltas") or []),
        "spurious": prediction - selected,
        "missed": selected - prediction,
    }


def score(rows: Sequence[Mapping[str, object]], pairs: Mapping[str, Mapping[str, object]]) -> dict:
    evaluations = [evaluate_row(row, pairs[str(row["pair_id"])]) for row in rows]
    tp = sum(item["tp"] for item in evaluations)
    predicted = sum(item["predicted"] for item in evaluations)
    gold = sum(item["gold"] for item in evaluations)
    denominator = predicted + gold
    family_values: dict[str, list[float]] = defaultdict(list)
    for item in evaluations:
        family_values[str(item["scenario"])].append(float(item["f1"]))
    family_means = {
        family: sum(values) / len(values)
        for family, values in family_values.items()
    }
    return {
        "pairs": len(evaluations),
        "tp": tp,
        "predicted_atoms": predicted,
        "gold_atoms": gold,
        "precision": tp / predicted if predicted else 0.0,
        "recall": tp / gold if gold else 0.0,
        "micro_f1": 1.0 if denominator == 0 else 2 * tp / denominator,
        "exact_rate": sum(bool(item["exact"]) for item in evaluations) / len(evaluations),
        "never_changed_rate": sum(not item["prediction"] for item in evaluations) / len(evaluations),
        "spurious_atoms": sum(len(item["spurious"]) for item in evaluations),
        "missed_atoms": sum(len(item["missed"]) for item in evaluations),
        "family_macro_pair_f1": sum(family_means.values()) / len(family_means),
        "family_pair_f1": family_means,
        "selected_gold_realizations": {
            str(item["pair_id"]): sorted(item["selected_gold"])
            for item in evaluations
        },
        "evaluations": evaluations,
    }


def percentile(values: Sequence[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def cluster_bootstrap(rows_by_arm: Mapping[str, Sequence[Mapping[str, object]]],
                      pairs: Mapping[str, Mapping[str, object]]) -> dict:
    families = sorted({str(pair["scenario"]) for pair in pairs.values()
                       if any(row["pair_id"] == pair["pair_id"]
                              for rows in rows_by_arm.values() for row in rows)})
    grouped = {arm: defaultdict(list) for arm in rows_by_arm}
    for arm, rows in rows_by_arm.items():
        for row in rows:
            family = str(pairs[str(row["pair_id"])]["scenario"])
            grouped[arm][family].append(row)
    rng = random.Random(SEED)
    arm_draws = {arm: [] for arm in rows_by_arm}
    difference_draws = {arm: [] for arm in COMPARATORS if arm in rows_by_arm}
    for _ in range(BOOTSTRAP_DRAWS):
        sampled = [rng.choice(families) for _ in families]
        draw_scores = {}
        for arm in rows_by_arm:
            draw_rows = [row for family in sampled for row in grouped[arm][family]]
            draw_scores[arm] = score(draw_rows, pairs)["micro_f1"]
            arm_draws[arm].append(draw_scores[arm])
        for comparator in difference_draws:
            difference_draws[comparator].append(draw_scores[B5] - draw_scores[comparator])
    return {
        "seed": SEED,
        "draws": BOOTSTRAP_DRAWS,
        "unit": "branch_family",
        "arms": {arm: {"low": percentile(values, 0.025), "high": percentile(values, 0.975)}
                 for arm, values in arm_draws.items()},
        "b5_minus": {arm: {"low": percentile(values, 0.025), "high": percentile(values, 0.975)}
                     for arm, values in difference_draws.items()},
    }


def exact_family_swap(b5_rows: Sequence[Mapping[str, object]],
                      comparator_rows: Sequence[Mapping[str, object]],
                      pairs: Mapping[str, Mapping[str, object]]) -> dict:
    b5_family = score(b5_rows, pairs)["family_pair_f1"]
    comparator_family = score(comparator_rows, pairs)["family_pair_f1"]
    families = sorted(b5_family)
    differences = [b5_family[family] - comparator_family[family] for family in families]
    observed = sum(differences) / len(differences)
    null = [sum(sign * difference for sign, difference in zip(signs, differences)) / len(families)
            for signs in itertools.product((-1, 1), repeat=len(families))]
    return {
        "families": families,
        "family_differences": differences,
        "observed_mean_difference": observed,
        "assignments": len(null),
        "one_sided_p": sum(value >= observed - 1e-15 for value in null) / len(null),
        "null_min": min(null),
        "null_max": max(null),
    }


def holm_adjust(p_values: Mapping[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    adjusted = {}
    running = 0.0
    total = len(ordered)
    for index, (name, value) in enumerate(ordered):
        candidate = min(1.0, (total - index) * value)
        running = max(running, candidate)
        adjusted[name] = running
    return adjusted


def pairing_score(prediction_rows: Sequence[Mapping[str, object]],
                  target_pairs: Sequence[Mapping[str, object]]) -> float:
    tp = predicted = gold = 0
    for row, pair in zip(prediction_rows, target_pairs):
        selected, local = best_realization(row.get("predicted_signed_delta") or [], pair)
        del selected
        tp += local["tp"]
        predicted += local["predicted"]
        gold += local["gold"]
    denominator = predicted + gold
    return 1.0 if denominator == 0 else 2 * tp / denominator


def wrong_pairing(b5_rows: Sequence[Mapping[str, object]],
                  pairs: Mapping[str, Mapping[str, object]]) -> dict:
    rows_by_family: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    targets_by_family: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in b5_rows:
        pair = pairs[str(row["pair_id"])]
        family = str(pair["scenario"])
        rows_by_family[family].append(row)
        targets_by_family[family].append(pair)
    families = sorted(rows_by_family)
    for family in families:
        rows_by_family[family].sort(key=lambda row: int(pairs[str(row["pair_id"])]["context_index"]))
        targets_by_family[family].sort(key=lambda pair: int(pair["context_index"]))
    context_counts = {family: len(rows) for family, rows in rows_by_family.items()}
    if len(set(context_counts.values())) != 1:
        raise ValueError(f"wrong-pairing requires equal context counts: {context_counts}")
    prediction_rows = [row for family in families for row in rows_by_family[family]]
    correct_targets = [pair for family in families for pair in targets_by_family[family]]
    observed = pairing_score(prediction_rows, correct_targets)

    def mapped_score(permutation: Sequence[int]) -> float:
        targets = [pair for index in permutation for pair in targets_by_family[families[index]]]
        return pairing_score(prediction_rows, targets)
    count = len(families)
    cyclic = [mapped_score(tuple((index + shift) % count for index in range(count)))
              for shift in range(1, count)]
    rng = random.Random(SEED)
    random_null = []
    indices = list(range(count))
    while len(random_null) < PAIRING_DRAWS:
        candidate = indices[:]
        rng.shuffle(candidate)
        if any(index == candidate[index] for index in indices):
            continue
        random_null.append(mapped_score(candidate))
    null = cyclic + random_null
    return {
        "observed_micro_f1": observed,
        "families": families,
        "contexts_per_family": context_counts,
        "cyclic_shifts": cyclic,
        "random_draws": PAIRING_DRAWS,
        "seed": SEED,
        "null_mean": sum(null) / len(null),
        "null_95": [percentile(null, 0.025), percentile(null, 0.975)],
        "null_min": min(null),
        "null_max": max(null),
        "p_ge_plus1": (1 + sum(value >= observed - 1e-15 for value in null)) / (1 + len(null)),
    }


def chain_metrics(b5_rows: Sequence[Mapping[str, object]],
                  pairs: Mapping[str, Mapping[str, object]]) -> dict:
    predicted_total = gold_total = attributed_predicted = covered_gold = 0
    details = []
    for row in b5_rows:
        pair = pairs[str(row["pair_id"])]
        selected_gold, _ = best_realization(row.get("predicted_signed_delta") or [], pair)
        predicted = set(row.get("predicted_signed_delta") or [])
        attributed = set(row.get("chain_attributed_predicted") or [])
        chainable_gold = set(row.get("chain_attributable_gold_atoms") or [])
        predicted_total += len(predicted)
        gold_total += len(selected_gold)
        attributed_predicted += len(predicted & attributed)
        covered_gold += len(selected_gold & chainable_gold)
        details.append({
            "pair_id": row["pair_id"],
            "selected_gold": sorted(selected_gold),
            "attributed_predicted": sorted(predicted & attributed),
            "covered_gold": sorted(selected_gold & chainable_gold),
        })
    return {
        "predicted_atoms": predicted_total,
        "gold_atoms": gold_total,
        "attributed_predicted_atoms": attributed_predicted,
        "covered_gold_atoms": covered_gold,
        "predicted_attribution_rate": (attributed_predicted / predicted_total
                                       if predicted_total else 1.0),
        "gold_chain_coverage": covered_gold / gold_total if gold_total else 1.0,
        "all_requested_documents_have_source_chains": all(
            bool(row.get("all_requests_source_chained", False)) for row in b5_rows),
        "details": details,
    }


def validate_rosters(rows_by_arm: Mapping[str, Sequence[Mapping[str, object]]],
                     pairs: Mapping[str, Mapping[str, object]]) -> list[str]:
    problems = []
    expected = None
    for arm, rows in rows_by_arm.items():
        roster = [str(row["pair_id"]) for row in rows]
        if len(roster) != len(set(roster)):
            problems.append(f"{arm}: duplicate pair ids")
        unknown = sorted(set(roster) - set(pairs))
        if unknown:
            problems.append(f"{arm}: unknown pair ids {unknown}")
        if expected is None:
            expected = set(roster)
        elif set(roster) != expected:
            problems.append(f"{arm}: roster mismatch")
        for row in rows:
            if "predicted_signed_delta" not in row:
                problems.append(f"{arm}:{row.get('pair_id')}: missing predicted delta")
    if expected is not None:
        contexts = {int(pairs[pair_id]["context_index"]) for pair_id in expected}
        if len(contexts) not in {1, 3, 4}:
            problems.append(f"unexpected context roster {sorted(contexts)}")
    return problems


def public_score(value: dict) -> dict:
    return {key: item for key, item in value.items()
            if key not in {"evaluations"}}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--b5", type=Path, required=True)
    parser.add_argument("--baselines", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("development", "hidden"), required=True)
    args = parser.parse_args()

    pairs = load_pairs(args.benchmark)
    rows = load_rows(args.b5, args.baselines)
    rows_by_arm: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        rows_by_arm[str(row["arm"])].append(row)
    for arm in rows_by_arm:
        rows_by_arm[arm].sort(key=lambda row: str(row["pair_id"]))
    expected_arms = {B5, *COMPARATORS}
    if set(rows_by_arm) != expected_arms:
        raise SystemExit(f"arm mismatch: {sorted(rows_by_arm)}")
    roster_problems = validate_rosters(rows_by_arm, pairs)
    if roster_problems:
        raise SystemExit("; ".join(roster_problems))

    score_details = {arm: score(arm_rows, pairs) for arm, arm_rows in rows_by_arm.items()}
    scores = {arm: public_score(value) for arm, value in score_details.items()}
    b5_rows = rows_by_arm[B5]
    swap_tests = {comparator: exact_family_swap(b5_rows, rows_by_arm[comparator], pairs)
                  for comparator in COMPARATORS}
    adjusted_p = holm_adjust({name: result["one_sided_p"]
                              for name, result in swap_tests.items()})
    for comparator in COMPARATORS:
        swap_tests[comparator]["holm_adjusted_p"] = adjusted_p[comparator]
    bootstrap = cluster_bootstrap(rows_by_arm, pairs)
    pairing = wrong_pairing(b5_rows, pairs)
    chains = chain_metrics(b5_rows, pairs)
    b5_score = scores[B5]
    margins = {comparator: b5_score["micro_f1"] - scores[comparator]["micro_f1"]
               for comparator in COMPARATORS}
    atom_ratio = (b5_score["predicted_atoms"] / b5_score["gold_atoms"]
                  if b5_score["gold_atoms"] else 1.0)
    gates = {
        "margin_at_least_0_10_against_all": all(value >= 0.10 for value in margins.values()),
        "holm_p_at_most_0_05_against_all": all(adjusted_p[name] <= 0.05 for name in COMPARATORS),
        "delta_precision_at_least_0_70": b5_score["precision"] >= 0.70,
        "predicted_gold_ratio_in_range": 0.75 <= atom_ratio <= 1.50,
        "predicted_chain_attribution_at_least_0_90": chains["predicted_attribution_rate"] >= 0.90,
        "gold_chain_coverage_at_least_0_80": chains["gold_chain_coverage"] >= 0.80,
        "correct_pairing_above_null_97_5": pairing["observed_micro_f1"] > pairing["null_95"][1],
        "no_orphan_insertion_path": chains["all_requested_documents_have_source_chains"],
    }
    gate_pass = all(gates.values())
    result = {
        "contract": "casepath.theft-confirmatory-analysis/4.0.0",
        "benchmark_semantics": "one acceptable document route per independently frozen requirement",
        "mode": args.mode,
        "seed": SEED,
        "scores": scores,
        "b5_minus_comparator_micro_f1": margins,
        "family_swap_tests": swap_tests,
        "cluster_bootstrap": bootstrap,
        "wrong_pairing": pairing,
        "chain_metrics": chains,
        "predicted_to_gold_atom_ratio": atom_ratio,
        "positive_claim_gates": gates,
        "gate_pass": gate_pass,
        "claim_status": (("SUPPORTED" if gate_pass else "UNSUPPORTED")
                         if args.mode == "hidden" else "DEVELOPMENT_ONLY"),
        "benchmark_sha256": hashlib.sha256(args.benchmark.read_bytes()).hexdigest(),
        "b5_input_sha256": hashlib.sha256(args.b5.read_bytes()).hexdigest(),
        "baselines_input_sha256": hashlib.sha256(args.baselines.read_bytes()).hexdigest(),
        "analysis_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
