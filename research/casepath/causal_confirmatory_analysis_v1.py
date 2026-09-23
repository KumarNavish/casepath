"""Frozen domain-general analysis for causal process-to-checklist benchmarks.

Input rows are signed document deltas grouped by independently frozen branch family.
The analysis is intentionally agnostic to the legal/insurance scope.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Iterable

SEED = 20260917
BOOTSTRAP_DRAWS = 10_000
PAIRING_DRAWS = 5_000
COMPARATORS = ("b1_direct", "b3_representation_then_list", "b6_evidence_first")


def load_rows(b5_path: Path, baseline_path: Path) -> list[dict]:
    b5 = json.loads(b5_path.read_text())
    for row in b5:
        row["arm"] = "b5_process_compiled"
    baselines = json.loads(baseline_path.read_text())
    return b5 + baselines


def atoms(row: dict, key: str) -> set[str]:
    return set(row.get(key) or [])


def gold_options(row: dict) -> list[set[str]]:
    alternatives = row.get("acceptable_signed_deltas")
    if alternatives is not None:
        options = [set(option) for option in alternatives]
        if not options:
            raise ValueError(f"{row.get('pair_id')}: no acceptable gold realization")
        return options
    return [atoms(row, "gold_signed_delta")]


def choose_gold(prediction: set[str], row: dict) -> set[str]:
    scored = []
    for gold in gold_options(row):
        tp = len(prediction & gold)
        denominator = len(prediction) + len(gold)
        f1 = 1.0 if denominator == 0 else 2 * tp / denominator
        scored.append((f1, tp, -len(gold), tuple(sorted(gold)), gold))
    return max(scored)[-1]


def bind_benchmark(rows: list[dict], benchmark: dict) -> list[dict]:
    by_pair = {pair["pair_id"]: pair for pair in benchmark.get("pairs") or []}
    if len(by_pair) != len(benchmark.get("pairs") or []):
        raise ValueError("benchmark contains duplicate pair ids")
    out = []
    for row in rows:
        pair = by_pair.get(row.get("pair_id"))
        if pair is None:
            raise ValueError(f"row absent from benchmark: {row.get('pair_id')}")
        value = dict(row)
        alternatives = pair.get("acceptable_signed_deltas")
        if alternatives is None:
            alternatives = [[*("+" + d for d in pair.get("expected_added") or []),
                             *("-" + d for d in pair.get("expected_withdrawn") or [])]]
        value["acceptable_signed_deltas"] = alternatives
        value["scenario"] = pair["scenario"]
        out.append(value)
    return out


def counts(rows: Iterable[dict]) -> tuple[int, int, int]:
    tp = predicted = gold = 0
    for row in rows:
        p = atoms(row, "predicted_signed_delta")
        g = choose_gold(p, row)
        tp += len(p & g)
        predicted += len(p)
        gold += len(g)
    return tp, predicted, gold
def score(rows: Iterable[dict]) -> dict:
    rows = list(rows)
    tp, predicted, gold = counts(rows)
    precision = tp / predicted if predicted else 0.0
    recall = tp / gold if gold else 0.0
    micro_f1 = 2 * tp / (predicted + gold) if predicted + gold else 1.0
    pair_f1 = []
    for row in rows:
        p = atoms(row, "predicted_signed_delta")
        g = choose_gold(p, row)
        pair_f1.append(2 * len(p & g) / (len(p) + len(g)) if len(p) + len(g) else 1.0)
    by_family: dict[str, list[float]] = defaultdict(list)
    for row, value in zip(rows, pair_f1):
        by_family[row["scenario"]].append(value)
    family_means = {family: sum(values) / len(values) for family, values in by_family.items()}
    return {
        "pairs": len(rows), "tp": tp, "predicted_atoms": predicted, "gold_atoms": gold,
        "precision": precision, "recall": recall, "micro_f1": micro_f1,
        "exact_rate": sum(atoms(row, "predicted_signed_delta") == atoms(row, "gold_signed_delta") for row in rows) / len(rows),
        "never_changed_rate": sum(not atoms(row, "predicted_signed_delta") for row in rows) / len(rows),
        "spurious_atoms": sum(len(atoms(row, "predicted_signed_delta") - atoms(row, "gold_signed_delta")) for row in rows),
        "missed_atoms": sum(len(atoms(row, "gold_signed_delta") - atoms(row, "predicted_signed_delta")) for row in rows),
        "family_macro_pair_f1": sum(family_means.values()) / len(family_means),
        "family_pair_f1": family_means,
    }


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight
def cluster_bootstrap(rows_by_arm: dict[str, list[dict]]) -> dict:
    families = sorted({row["scenario"] for rows in rows_by_arm.values() for row in rows})
    grouped = {arm: defaultdict(list) for arm in rows_by_arm}
    for arm, rows in rows_by_arm.items():
        for row in rows:
            grouped[arm][row["scenario"]].append(row)
    rng = random.Random(SEED)
    arm_draws = {arm: [] for arm in rows_by_arm}
    diff_draws = {comparator: [] for comparator in COMPARATORS if comparator in rows_by_arm}
    for _ in range(BOOTSTRAP_DRAWS):
        sampled = [rng.choice(families) for _ in families]
        draw_scores = {}
        for arm in rows_by_arm:
            draw_rows = [row for family in sampled for row in grouped[arm][family]]
            draw_scores[arm] = score(draw_rows)["micro_f1"]
            arm_draws[arm].append(draw_scores[arm])
        for comparator in diff_draws:
            diff_draws[comparator].append(draw_scores["b5_process_compiled"] - draw_scores[comparator])
    return {
        "seed": SEED, "draws": BOOTSTRAP_DRAWS, "unit": "branch_family",
        "arms": {arm: {"low": percentile(values, 0.025), "high": percentile(values, 0.975)}
                 for arm, values in arm_draws.items()},
        "b5_minus": {arm: {"low": percentile(values, 0.025), "high": percentile(values, 0.975)}
                     for arm, values in diff_draws.items()},
    }


def exact_family_swap(b5_rows: list[dict], comparator_rows: list[dict]) -> dict:
    b5 = score(b5_rows)["family_pair_f1"]
    comparator = score(comparator_rows)["family_pair_f1"]
    families = sorted(b5)
    differences = [b5[family] - comparator[family] for family in families]
    observed = sum(differences) / len(differences)
    null = []
    for signs in itertools.product((-1, 1), repeat=len(families)):
        null.append(sum(sign * difference for sign, difference in zip(signs, differences)) / len(families))
    p_value = sum(value >= observed - 1e-15 for value in null) / len(null)
    return {"families": families, "family_differences": differences,
            "observed_mean_difference": observed, "assignments": len(null),
            "one_sided_p": p_value, "null_min": min(null), "null_max": max(null)}
def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    adjusted = {}
    running = 0.0
    total = len(ordered)
    for index, (name, value) in enumerate(ordered):
        candidate = min(1.0, (total - index) * value)
        running = max(running, candidate)
        adjusted[name] = running
    return adjusted


def pairing_score(predicted_rows: list[dict], gold_rows: list[dict]) -> float:
    tp = predicted = gold = 0
    for prediction, target in zip(predicted_rows, gold_rows):
        p = atoms(prediction, "predicted_signed_delta")
        g = choose_gold(p, target)
        tp += len(p & g)
        predicted += len(p)
        gold += len(g)
    return 2 * tp / (predicted + gold) if predicted + gold else 1.0


def wrong_pairing(b5_rows: list[dict]) -> dict:
    by_family: dict[str, list[dict]] = defaultdict(list)
    for row in b5_rows:
        by_family[row["scenario"]].append(row)
    families = sorted(by_family)
    for family in families:
        by_family[family].sort(key=lambda row: row["pair_id"])
    context_counts = {family: len(rows) for family, rows in by_family.items()}
    if len(set(context_counts.values())) != 1:
        raise ValueError(f"wrong-pairing requires equal context counts: {context_counts}")
    predicted_rows = [row for family in families for row in by_family[family]]
    observed = pairing_score(predicted_rows, predicted_rows)

    def score_mapping(permutation: tuple[int, ...] | list[int]) -> float:
        targets = [row for index in permutation for row in by_family[families[index]]]
        return pairing_score(predicted_rows, targets)

    n = len(families)
    cyclic = [score_mapping(tuple((index + shift) % n for index in range(n))) for shift in range(1, n)]
    rng = random.Random(SEED)
    random_null = []
    indices = list(range(n))
    while len(random_null) < PAIRING_DRAWS:
        candidate = indices[:]
        rng.shuffle(candidate)
        if any(index == candidate[index] for index in indices):
            continue
        random_null.append(score_mapping(candidate))
    null = cyclic + random_null
    p_value = (1 + sum(value >= observed - 1e-15 for value in null)) / (1 + len(null))
    return {"observed_micro_f1": observed, "families": families, "contexts_per_family": context_counts,
            "cyclic_shifts": cyclic, "random_draws": PAIRING_DRAWS, "seed": SEED,
            "null_mean": sum(null) / len(null), "null_95": [percentile(null, 0.025), percentile(null, 0.975)],
            "null_min": min(null), "null_max": max(null), "p_ge_plus1": p_value}
def chain_metrics(b5_rows: list[dict]) -> dict:
    predicted = sum(len(atoms(row, "predicted_signed_delta")) for row in b5_rows)
    chosen = [(row, choose_gold(atoms(row, "predicted_signed_delta"), row)) for row in b5_rows]
    gold = sum(len(gold_set) for _, gold_set in chosen)
    attributed_predicted = sum(len(set(row.get("chain_attributed_predicted") or [])) for row in b5_rows)
    attributed_gold = sum(
        len(gold_set & set(row.get("chain_attributed_predicted") or []))
        for row, gold_set in chosen
    )
    return {
        "predicted_atoms": predicted, "gold_atoms": gold,
        "attributed_predicted_atoms": attributed_predicted,
        "attributed_gold_atoms": attributed_gold,
        "predicted_attribution_rate": attributed_predicted / predicted if predicted else 1.0,
        "gold_chain_coverage": attributed_gold / gold if gold else 1.0,
        "all_requested_documents_have_source_chains": True,
        "note": "B5 requests are constructed only from admitted overlay chains; direct orphan insertion is unavailable.",
    }


def validate_rosters(rows_by_arm: dict[str, list[dict]]) -> list[str]:
    problems = []
    rosters = {arm: [row["pair_id"] for row in rows] for arm, rows in rows_by_arm.items()}
    for arm, roster in rosters.items():
        if len(roster) != len(set(roster)):
            problems.append(f"{arm}: duplicate pair ids")
    reference = set(next(iter(rosters.values())))
    for arm, roster in rosters.items():
        if set(roster) != reference:
            problems.append(f"{arm}: roster mismatch")
    for arm, rows in rows_by_arm.items():
        for row in rows:
            has_gold = "gold_signed_delta" in row or "acceptable_signed_deltas" in row
            if not row.get("scenario") or "predicted_signed_delta" not in row or not has_gold:
                problems.append(f"{arm}:{row.get('pair_id')}: incomplete row")
    return problems
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--b5", type=Path, required=True)
    parser.add_argument("--baselines", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("development", "hidden"), required=True)
    parser.add_argument("--benchmark", type=Path, required=True,
                        help="Frozen benchmark defining all acceptable signed gold deltas.")
    args = parser.parse_args()

    benchmark = json.loads(args.benchmark.read_text())
    rows = bind_benchmark(load_rows(args.b5, args.baselines), benchmark)
    rows_by_arm: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        rows_by_arm[row["arm"]].append(row)
    for arm in rows_by_arm:
        rows_by_arm[arm].sort(key=lambda row: row["pair_id"])
    expected_arms = {"b5_process_compiled", *COMPARATORS}
    if set(rows_by_arm) != expected_arms:
        raise SystemExit(f"arm mismatch: {sorted(rows_by_arm)}")
    roster_problems = validate_rosters(rows_by_arm)
    if roster_problems:
        raise SystemExit("; ".join(roster_problems))

    scores = {arm: score(arm_rows) for arm, arm_rows in rows_by_arm.items()}
    b5_rows = rows_by_arm["b5_process_compiled"]
    swap_tests = {comparator: exact_family_swap(b5_rows, rows_by_arm[comparator])
                  for comparator in COMPARATORS}
    raw_p = {name: result["one_sided_p"] for name, result in swap_tests.items()}
    adjusted_p = holm_adjust(raw_p)
    for comparator in COMPARATORS:
        swap_tests[comparator]["holm_adjusted_p"] = adjusted_p[comparator]
    bootstrap = cluster_bootstrap(rows_by_arm)
    pairing = wrong_pairing(b5_rows)
    chains = chain_metrics(b5_rows)
    b5_score = scores["b5_process_compiled"]
    margins = {comparator: b5_score["micro_f1"] - scores[comparator]["micro_f1"]
               for comparator in COMPARATORS}
    atom_ratio = b5_score["predicted_atoms"] / b5_score["gold_atoms"] if b5_score["gold_atoms"] else 1.0
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
        "contract": "casepath.causal-confirmatory-analysis/1.0.0",
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
        "claim_status": ("SUPPORTED" if gate_pass else "UNSUPPORTED") if args.mode == "hidden" else "DEVELOPMENT_ONLY",
        "b5_input_sha256": hashlib.sha256(args.b5.read_bytes()).hexdigest(),
        "baselines_input_sha256": hashlib.sha256(args.baselines.read_bytes()).hexdigest(),
        "benchmark_input_sha256": hashlib.sha256(args.benchmark.read_bytes()).hexdigest(),
        "analysis_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
