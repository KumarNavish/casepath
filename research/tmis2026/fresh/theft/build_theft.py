"""Build the fresh theft stories with the released, deterministic construction scripts.

Steps (no model calls, no method outputs consulted):
1. Copy the frozen reference contract and the two construction scripts into a work folder.
2. Run theft_branch_diagnostic.py on the contract (the branch-document projection).
3. Run theft_causal_benchmark.py with its four original story contexts followed by the four
   new ones (only the CONTEXTS list is replaced; everything else is the released script).
4. Check that the rebuilt original stories reproduce BENCHMARK_V3 (texts identical; references
   identical except where amendments V2/V3 changed them) and that the v1 references of every
   condition are identical across all eight stories (the reference depends on the condition only).
5. Write the new stories in the BENCHMARK_V3 format: each new pair carries the V3 reference of its
   condition (requirement ids renamed), each unit the V3 gold documents of its condition and value.

Output: fresh/theft/BENCHMARK_FRESH.json and fresh/theft/build/ (work files, build log).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DATA = REPO / "data" / "casepath-theft-pairs"
V3 = json.loads((DATA / "benchmark" / "benchmark" / "BENCHMARK_V3.json").read_text())
WORK = HERE / "build"

NEW_CONTEXTS = [
    "A couple renting a terraced house in St. Gallen returned from a weekend away on 14 June 2026 to a forced garden door. Jewellery and binoculars are missing; police and insurer were informed.",
    "A student sharing a flat in Lucerne found the balcony door pried open on the morning of 2 July 2026. A games console and headphones were taken; she told the police and the insurer.",
    "After a hospital stay, a retired teacher in Lugano found his ground-floor apartment broken into on 19 August 2026. A coin collection and a television are gone; a neighbour alerted the police.",
    "Burglars entered a family's detached house near Winterthur through the terrace door during the night of 5 September 2026. Musical instruments and a sewing machine are missing; the police and the insurer were notified.",
]
N_OLD = 4


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    if WORK.exists():
        shutil.rmtree(WORK)
    (WORK / "reference_contracts").mkdir(parents=True)
    (WORK / "artifacts").mkdir()
    shutil.copy(DATA / "reference-contract" / "theft.json", WORK / "reference_contracts" / "theft.json")
    shutil.copy(DATA / "construction" / "theft_branch_diagnostic.py", WORK / "theft_branch_diagnostic.py")
    src = (DATA / "construction" / "theft_causal_benchmark.py").read_text()
    start = src.index("CONTEXTS = [")
    end = src.index("]\n", start) + 2
    old_contexts = eval(src[start + len("CONTEXTS = "):end])  # the released list, a literal
    patched = src[:start] + "CONTEXTS = " + json.dumps(old_contexts + NEW_CONTEXTS, indent=4, ensure_ascii=False) + "\n" + src[end:]
    (WORK / "theft_causal_benchmark.py").write_text(patched)
    diag = subprocess.run([sys.executable, "theft_branch_diagnostic.py"], cwd=WORK, capture_output=True, text=True, check=True)
    (WORK / "artifacts" / "THEFT_BRANCH_DIAGNOSTIC.json").write_text(diag.stdout)
    run = subprocess.run([sys.executable, "theft_causal_benchmark.py"], cwd=WORK, capture_output=True, text=True, check=True)
    (WORK / "build_log.json").write_text(run.stdout)
    built = json.loads((WORK / "theft_causal" / "BENCHMARK.json").read_text())
    admission = json.loads(run.stdout)["shortcut_admission"]
    assert all(admission.values()), admission  # the released input-free and minimal-edit preflight

    # ---- checks against the released benchmark
    v3_units = {u["unit_id"]: u for u in V3["units"]}
    v3_pairs = {p["pair_id"]: p for p in V3["pairs"]}
    amended = {"PR_scheduled_valuable_1000", "PR_bicycle_claimed"}  # BENCHMARK_AMENDMENT_V2 / _V3
    checks = {"original_texts_identical": 0, "original_v1_refs_identical_or_amended": 0}
    for u in built["units"]:
        if u["context_index"] < N_OLD:
            assert u["customer_message"] == v3_units[u["unit_id"]]["customer_message"], u["unit_id"]
            checks["original_texts_identical"] += 1
    for p in built["pairs"]:
        if p["context_index"] < N_OLD:
            same = p["expected_added"] == v3_pairs[p["pair_id"]]["expected_added"]
            assert same or p["scenario"] in amended, p["pair_id"]
            checks["original_v1_refs_identical_or_amended"] += 1
    by_scen = {}
    for p in built["pairs"]:
        by_scen.setdefault(p["scenario"], set()).add(json.dumps(p["expected_added"]))
    assert all(len(v) == 1 for v in by_scen.values()), "v1 reference differs between stories"
    checks["v1_reference_depends_on_condition_only"] = True

    # ---- new stories in the V3 format
    template_pair = {p["scenario"]: p for p in V3["pairs"] if p["context_index"] == 1}
    template_unit = {(u["scenario"], u["target_value"]): u for u in V3["units"] if u["context_index"] == 1}
    units, pairs = [], []
    for u in built["units"]:
        if u["context_index"] < N_OLD:
            continue
        t = template_unit[(u["scenario"], u["target_value"])]
        nu = {**u, "gold_branch_documents": t["gold_branch_documents"]}
        assert set(nu) == set(t)
        units.append(nu)
    for p in built["pairs"]:
        if p["context_index"] < N_OLD:
            continue
        t = deepcopy(template_pair[p["scenario"]])
        np_ = {**t, "pair_id": p["pair_id"], "context_index": p["context_index"], "false_unit_id": p["false_unit_id"],
               "true_unit_id": p["true_unit_id"]}
        for i, req in enumerate(np_["expected_added_requirements"], 1):
            req["requirement_id"] = f"{p['pair_id']}-added-{i:02d}"
        for i, req in enumerate(np_["expected_withdrawn_requirements"], 1):
            req["requirement_id"] = f"{p['pair_id']}-withdrawn-{i:02d}"
        assert np_["changed_statement_false"] == p["changed_statement_false"]
        assert np_["changed_statement_true"] == p["changed_statement_true"]
        assert set(np_) == set(t)
        pairs.append(np_)
    out = {k: v for k, v in V3.items() if k not in ("units", "pairs")}
    out.update({"contract": V3["contract"] + "+fresh-stories-4-7", "units": units, "pairs": pairs,
                "fresh_build": {"contexts": NEW_CONTEXTS, "context_indices": list(range(N_OLD, N_OLD + len(NEW_CONTEXTS))),
                                "reference_contract_sha256": sha(DATA / "reference-contract" / "theft.json"),
                                "construction_script_sha256": {f: sha(DATA / "construction" / f) for f in
                                                               ("theft_causal_benchmark.py", "theft_branch_diagnostic.py")},
                                "benchmark_v3_sha256": sha(DATA / "benchmark" / "benchmark" / "BENCHMARK_V3.json"),
                                "checks": checks}})
    (HERE / "BENCHMARK_FRESH.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"units": len(units), "pairs": len(pairs), **checks}, indent=1))


if __name__ == "__main__":
    main()
