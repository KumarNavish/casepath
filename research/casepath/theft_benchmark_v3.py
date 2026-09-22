from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = ROOT / "theft_causal"
REFERENCE = ROOT / "reference_contracts/theft.json"
INPUT = BASE / "BENCHMARK_V2.json"
OUTPUT = BASE / "BENCHMARK_V3.json"
PREFLIGHT = BASE / "SHORTCUT_PREFLIGHT_V3.json"
AMENDMENT = BASE / "BENCHMARK_AMENDMENT_V3.json"
GOAL = "a9cd441ef939e36d7ed2c546b76aa41554813aba11ba1a379f23479ded4cc37b"

spec = importlib.util.spec_from_file_location("theft_benchmark_v2", ROOT / "theft_benchmark_v2.py")
v2 = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(v2)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def branch_documents(reference: dict, predicate_id: str) -> list[str]:
    facts = [f for f in reference["facts"] if f.get("conditional_on") == predicate_id]
    fact_ids = {f["fact_id"] for f in facts}
    capability_ids = {
        c["capability_id"] for c in reference["capabilities"]
        if c.get("for_fact") in fact_ids
    }
    documents = []
    for document in reference["documents"]:
        if capability_ids & set(document.get("establishes_capabilities") or []):
            documents.append(document["document_type"])
    return sorted(documents)


def rebuild_pair_targets(pair: dict, alternatives: dict[str, set[str]]) -> None:
    added = v2.requirement_groups(pair.get("expected_added") or [], alternatives,
                                  pair["pair_id"] + "-added")
    withdrawn = v2.requirement_groups(pair.get("expected_withdrawn") or [], alternatives,
                                      pair["pair_id"] + "-withdrawn")
    pair["expected_added_requirements"] = added
    pair["expected_withdrawn_requirements"] = withdrawn
    pair["acceptable_signed_deltas"] = v2.enumerate_realizations(added, withdrawn)
    if not pair["acceptable_signed_deltas"]:
        raise RuntimeError(f"pair {pair['pair_id']} has no acceptable realization")


def preflight(benchmark: dict) -> dict:
    families = list(benchmark["selected_predicates"])
    universe = sorted({
        atom for pair in benchmark["pairs"]
        for option in pair["acceptable_signed_deltas"] for atom in option
    })
    folds = []
    for held_out in families:
        train = [p for p in benchmark["pairs"] if p["scenario"] != held_out]
        test = [p for p in benchmark["pairs"] if p["scenario"] == held_out]
        prediction, train_result = v2.best_constant(train, universe)
        test_result = v2.pooled_score(prediction, test)
        folds.append({
            "held_out_scenario": held_out,
            "selected_constant": sorted(prediction),
            "train_micro_f1": train_result["micro_f1"],
            "held_out_micro_f1": test_result["micro_f1"],
            "held_out_exact_rate": test_result["exact_rate"],
        })
    signatures = Counter(
        tuple(tuple(option) for option in pair["acceptable_signed_deltas"])
        for pair in benchmark["pairs"]
    )
    probabilities = [count / len(benchmark["pairs"]) for count in signatures.values()]
    maximum = max(row["held_out_micro_f1"] for row in folds)
    return {
        "contract": "casepath.theft-causal-shortcut-preflight/3.0.0",
        "benchmark_contract": benchmark["contract"],
        "pairs": len(benchmark["pairs"]),
        "units": len(benchmark["units"]),
        "scenarios": len(families),
        "signed_document_universe": universe,
        "distinct_acceptable_target_signatures": len(signatures),
        "target_signature_entropy_bits": -sum(p * math.log2(p) for p in probabilities),
        "crossfit_no_input_folds": folds,
        "max_held_out_no_input_micro_f1": maximum,
        "admission": {
            "input_free_control_pass": maximum <= 0.10,
            "target_diversity_pass": len(signatures) == len(families),
        },
    }


def build() -> tuple[dict, dict, dict]:
    benchmark = json.loads(INPUT.read_text())
    reference = json.loads(REFERENCE.read_text())["contract"]
    alternatives = {
        item["document_type"]: set(item.get("alternative_set_with") or [])
        for item in reference["documents"]
    }
    bicycle_documents = branch_documents(reference, "PR_bicycle_claimed")
    expected_bicycle = sorted([
        "Bicycle purchase voucher (Kaufbeleg des Fahrrads / Originalkaufbeleg)",
        "Detailed cost estimate for the bicycle with an image of the damaged or stolen bicycle or part (Detaillierter Kostenvoranschlag mit Foto)",
    ])
    if bicycle_documents != expected_bicycle:
        raise RuntimeError({"unexpected_bicycle_reference_projection": bicycle_documents})

    benchmark["contract"] = "casepath.theft-causal-branch-benchmark/3.0.0"
    benchmark["goal_contract_sha256"] = GOAL
    for pair in benchmark["pairs"]:
        if pair["scenario"] == "PR_bicycle_claimed":
            pair["expected_added"] = expected_bicycle
        rebuild_pair_targets(pair, alternatives)

    check = preflight(benchmark)
    amendment = {
        "contract": "casepath.theft-benchmark-amendment/3.0.0",
        "goal_contract_sha256": GOAL,
        "parent_benchmark_sha256": sha(INPUT),
        "reference_contract_sha256": sha(REFERENCE),
        "reason": (
            "The independent theft reference contract states that the bicycle branch opens both the "
            "bicycle purchase voucher and the detailed photographed cost estimate. Benchmark v2 "
            "projected only the estimate. Version 3 restores the omitted source-named requirement."
        ),
        "affected_scenarios": ["PR_bicycle_claimed"],
        "development_pairs_opened_before_amendment": 9,
        "hidden_pairs_opened_before_amendment": 0,
        "hidden_units_remaining": 54,
        "old_artifacts_preserved": True,
        "scientific_effect": (
            "Both source-distinct bicycle evidence requirements receive gold credit; neither is an alternative."
        ),
        "reference_projection": bicycle_documents,
    }
    return benchmark, check, amendment


def main() -> None:
    benchmark, check, amendment = build()
    OUTPUT.write_text(json.dumps(benchmark, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    PREFLIGHT.write_text(json.dumps(check, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    amendment["new_benchmark_sha256"] = sha(OUTPUT)
    amendment["new_preflight_sha256"] = sha(PREFLIGHT)
    AMENDMENT.write_text(json.dumps(amendment, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({"amendment": amendment, "preflight": check["admission"],
                      "max_no_input_f1": check["max_held_out_no_input_micro_f1"]}, indent=2))


if __name__ == "__main__":
    main()
