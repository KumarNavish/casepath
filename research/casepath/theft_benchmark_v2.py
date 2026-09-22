from __future__ import annotations

import hashlib
import itertools
import json
import math
from collections import Counter
from pathlib import Path
from typing import Iterable, Sequence

ROOT = Path(__file__).resolve().parent
BASE = ROOT / "theft_causal"
REFERENCE = ROOT / "reference_contracts/theft.json"
INPUT = BASE / "BENCHMARK.json"
OUTPUT = BASE / "BENCHMARK_V2.json"
PREFLIGHT = BASE / "SHORTCUT_PREFLIGHT_V2.json"
AMENDMENT = BASE / "BENCHMARK_AMENDMENT_V2.json"
GOAL = "a9cd441ef939e36d7ed2c546b76aa41554813aba11ba1a379f23479ded4cc37b"
SEED = 20260917


def connected_components(documents: Sequence[str], alternatives: dict[str, set[str]]) -> list[list[str]]:
    remaining = set(documents)
    components = []
    while remaining:
        seed = min(remaining)
        stack = [seed]
        component = set()
        while stack:
            document = stack.pop()
            if document in component:
                continue
            component.add(document)
            stack.extend((alternatives.get(document) or set()) & set(documents))
        remaining -= component
        components.append(sorted(component))
    return sorted(components, key=lambda group: group[0])


def requirement_groups(documents: Sequence[str], alternatives: dict[str, set[str]], prefix: str) -> list[dict]:
    groups = []
    for index, component in enumerate(connected_components(documents, alternatives), 1):
        if len(component) == 1:
            routes = [[component[0]]]
        else:
            # The reference contract's alternative_set_with relation denotes singleton substitutes.
            routes = [[document] for document in component]
        groups.append({
            "requirement_id": f"{prefix}-{index:02d}",
            "acceptable_routes": routes,
            "source_documents": component,
        })
    return groups


def enumerate_realizations(added: Sequence[dict], withdrawn: Sequence[dict]) -> list[list[str]]:
    route_lists = []
    signs = []
    for group in added:
        route_lists.append(group["acceptable_routes"])
        signs.append("+")
    for group in withdrawn:
        route_lists.append(group["acceptable_routes"])
        signs.append("-")
    if not route_lists:
        return [[]]
    realizations = set()
    for selected in itertools.product(*route_lists):
        atoms = []
        for sign, route in zip(signs, selected):
            atoms.extend(sign + document for document in route)
        realizations.add(tuple(sorted(set(atoms))))
    return [list(atoms) for atoms in sorted(realizations)]


def best_realization(predicted: Iterable[str], acceptable: Sequence[Sequence[str]]) -> tuple[set[str], dict]:
    prediction = set(predicted)
    candidates = [set(option) for option in acceptable] or [set()]
    scored = []
    for gold in candidates:
        tp = len(prediction & gold)
        denominator = len(prediction) + len(gold)
        f1 = 1.0 if denominator == 0 else 2 * tp / denominator
        scored.append((f1, tp, -len(gold), tuple(sorted(gold)), gold))
    _, tp, _, _, gold = max(scored)
    return gold, {"tp": tp, "predicted": len(prediction), "gold": len(gold),
                  "f1": (1.0 if len(prediction) + len(gold) == 0
                         else 2 * tp / (len(prediction) + len(gold)))}


def pooled_score(prediction: set[str], pairs: Sequence[dict]) -> dict:
    tp = predicted = gold = 0
    exact = 0
    choices = []
    for pair in pairs:
        selected, local = best_realization(prediction, pair["acceptable_signed_deltas"])
        tp += local["tp"]
        predicted += local["predicted"]
        gold += local["gold"]
        exact += prediction == selected
        choices.append(sorted(selected))
    denominator = predicted + gold
    return {
        "micro_f1": 1.0 if denominator == 0 else 2 * tp / denominator,
        "precision": tp / predicted if predicted else 0.0,
        "recall": tp / gold if gold else 0.0,
        "exact_rate": exact / len(pairs) if pairs else 0.0,
        "tp": tp, "predicted_atoms": predicted, "gold_atoms": gold,
        "selected_realizations": choices,
    }


def best_constant(pairs: Sequence[dict], universe: Sequence[str]) -> tuple[set[str], dict]:
    best_prediction: set[str] = set()
    best_score = None
    for mask in range(1 << len(universe)):
        prediction = {universe[index] for index in range(len(universe)) if mask & (1 << index)}
        result = pooled_score(prediction, pairs)
        key = (result["micro_f1"], result["exact_rate"], -len(prediction), tuple(sorted(prediction)))
        if best_score is None or key > best_score[0]:
            best_score = key, result
            best_prediction = prediction
    assert best_score is not None
    return best_prediction, best_score[1]


def build() -> tuple[dict, dict, dict]:
    benchmark = json.loads(INPUT.read_text())
    reference = json.loads(REFERENCE.read_text())["contract"]
    alternatives = {
        item["document_type"]: set(item.get("alternative_set_with") or [])
        for item in reference["documents"]
    }
    revised = json.loads(INPUT.read_text())
    revised["contract"] = "casepath.theft-causal-branch-benchmark/2.0.0"
    revised["goal_contract_sha256"] = GOAL
    revised["alternative_semantics"] = (
        "Each requirement has one or more acceptable document routes. A valid realization "
        "selects exactly one route per requirement; documents beyond the selected realization are spurious."
    )
    for pair in revised["pairs"]:
        added = requirement_groups(pair.get("expected_added") or [], alternatives,
                                   pair["pair_id"] + "-added")
        withdrawn = requirement_groups(pair.get("expected_withdrawn") or [], alternatives,
                                       pair["pair_id"] + "-withdrawn")
        pair["expected_added_requirements"] = added
        pair["expected_withdrawn_requirements"] = withdrawn
        pair["acceptable_signed_deltas"] = enumerate_realizations(added, withdrawn)
        if not pair["acceptable_signed_deltas"]:
            raise RuntimeError(f"pair {pair['pair_id']} has no valid gold realization")

    pair_by_id = {pair["pair_id"]: pair for pair in revised["pairs"]}
    families = list(revised["selected_predicates"])
    universe = sorted({atom for pair in revised["pairs"]
                       for option in pair["acceptable_signed_deltas"] for atom in option})
    folds = []
    for held_out in families:
        train = [pair for pair in revised["pairs"] if pair["scenario"] != held_out]
        test = [pair for pair in revised["pairs"] if pair["scenario"] == held_out]
        prediction, train_result = best_constant(train, universe)
        test_result = pooled_score(prediction, test)
        folds.append({
            "held_out_scenario": held_out,
            "selected_constant": sorted(prediction),
            "train_micro_f1": train_result["micro_f1"],
            "held_out_micro_f1": test_result["micro_f1"],
            "held_out_exact_rate": test_result["exact_rate"],
        })
    target_signatures = Counter(
        tuple(tuple(option) for option in pair["acceptable_signed_deltas"])
        for pair in revised["pairs"])
    probabilities = [count / len(revised["pairs"]) for count in target_signatures.values()]
    preflight = {
        "contract": "casepath.theft-causal-shortcut-preflight/2.0.0",
        "benchmark_contract": revised["contract"],
        "pairs": len(revised["pairs"]),
        "units": len(revised["units"]),
        "scenarios": len(families),
        "signed_document_universe": universe,
        "distinct_acceptable_target_signatures": len(target_signatures),
        "target_signature_entropy_bits": -sum(p * math.log2(p) for p in probabilities),
        "crossfit_no_input_folds": folds,
        "max_held_out_no_input_micro_f1": max(fold["held_out_micro_f1"] for fold in folds),
        "admission": {
            "input_free_control_pass": max(fold["held_out_micro_f1"] for fold in folds) <= 0.10,
            "target_diversity_pass": len(target_signatures) == len(families),
        },
    }
    amendment = {
        "contract": "casepath.theft-benchmark-amendment/2.0.0",
        "goal_contract_sha256": GOAL,
        "old_benchmark_sha256": hashlib.sha256(INPUT.read_bytes()).hexdigest(),
        "reference_contract_sha256": hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),
        "reason": (
            "The scheduled-valuables reference contract marks a purchase receipt and an expert valuation "
            "as alternatives. Version 1 flattened both into a conjunction. Version 2 preserves one-of route semantics."
        ),
        "affected_scenarios": ["PR_scheduled_valuable_1000"],
        "development_pairs_opened_before_amendment": 9,
        "hidden_pairs_opened_before_amendment": 0,
        "hidden_units_remaining": 54,
        "old_artifacts_preserved": True,
        "scientific_effect": (
            "Either valid alternative receives full gold credit; predicting both incurs an extra-document penalty."
        ),
    }
    return revised, preflight, amendment


def main() -> None:
    benchmark, preflight, amendment = build()
    OUTPUT.write_text(json.dumps(benchmark, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    PREFLIGHT.write_text(json.dumps(preflight, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    amendment["new_benchmark_sha256"] = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    amendment["new_preflight_sha256"] = hashlib.sha256(PREFLIGHT.read_bytes()).hexdigest()
    AMENDMENT.write_text(json.dumps(amendment, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({"benchmark": amendment, "preflight": preflight["admission"],
                      "max_no_input_f1": preflight["max_held_out_no_input_micro_f1"]},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
