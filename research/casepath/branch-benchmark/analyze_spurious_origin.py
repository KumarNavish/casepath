#!/usr/bin/env python3
"""Attribute every spurious signed change on the held-out split.

    python3 analyze_spurious_origin.py

Aggregate counts say CasePath makes fewer unjustified changes. This partitions them to see whether
they are also a different kind. It reports only what the benchmark's own fields support.

A document counts as *branch-governed* if it appears in any unit's `gold_branch_documents` or in any
pair's `acceptable_signed_deltas`. Each spurious change is then one of:

  required_in_one_unit    branch-governed, and required in exactly one unit of this very pair, so
                          the system moved a document this intervention does govern, wrongly
  governed_elsewhere      branch-governed, but not required in either unit of this pair
  not_branch_governed     not branch-governed anywhere in this benchmark

`not_branch_governed` means exactly that. It does **not** establish that the document is a
universally required baseline: the benchmark fixes branch documents and signed deltas, not a full
per-unit reference checklist, so that stronger statement cannot be tested here.

Also reports how many guards the controller's extractor changed per pair, which bounds any
monotonicity reading, and the direction split of the reference and the predictions.

Reads released files only. Writes SPURIOUS_ORIGIN.json and table_spurious_origin.tex.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARMS = [("b5_process_compiled", r"\casepath"), ("b1_direct", "Direct"),
        ("b3_representation_then_list", "Graph as context"), ("b6_evidence_first", "Evidence-first")]
KINDS = ["required_in_one_unit", "governed_elsewhere", "not_branch_governed"]


def main() -> None:
    bench = json.loads((HERE / "benchmark" / "BENCHMARK_V3.json").read_text())
    report = json.loads((HERE / "expected" / "HELDOUT_RESULT.json").read_text())
    casepath_rows = json.loads((HERE / "predictions" / "heldout" / "casepath.json").read_text())
    rows = [dict(r, arm="b5_process_compiled") for r in casepath_rows]
    rows += json.loads((HERE / "predictions" / "heldout" / "comparators.json").read_text())

    unit_gold = {u["unit_id"]: set(u["gold_branch_documents"]) for u in bench["units"]}
    delta_atoms = {a.lstrip("+-") for p in bench["pairs"]
                   for alt in p["acceptable_signed_deltas"] for a in alt}
    governed = set().union(*unit_gold.values()) | delta_atoms
    pairs = {p["pair_id"]: p for p in bench["pairs"]}

    counts = {a: Counter() for a, _ in ARMS}
    distinct: dict[str, set] = {a: set() for a, _ in ARMS}
    for row in rows:
        arm, pid = row["arm"], row["pair_id"]
        if arm not in counts or pid not in pairs:
            continue
        pair = pairs[pid]
        before, after = unit_gold[pair["false_unit_id"]], unit_gold[pair["true_unit_id"]]
        selected = set(report["scores"][arm]["selected_gold_realizations"][pid])
        for atom in row["predicted_signed_delta"]:
            if atom in selected:
                continue
            doc = atom.lstrip("+-")
            if doc not in governed:
                kind = "not_branch_governed"
            elif (doc in before) != (doc in after):
                kind = "required_in_one_unit"
            else:
                kind = "governed_elsewhere"
            counts[arm][kind] += 1
            counts[arm]["added" if atom.startswith("+") else "withdrawn"] += 1
            distinct[arm].add(doc)

    guards = Counter(r.get("changed_guard_count", len(r.get("changed_guard_ids") or []))
                     for r in casepath_rows)
    silent = [r["pair_id"] for r in casepath_rows
              if not r.get("changed_guard_count") and r["predicted_signed_delta"]]
    ref_dir = Counter(a[0] for atoms in
                      report["scores"]["b5_process_compiled"]["selected_gold_realizations"].values()
                      for a in atoms)

    out = {
        "schema": "casepath.spurious-origin/2",
        "branch_governed_documents": len(governed),
        "branch_governed_definition": "union of every unit's gold_branch_documents and every "
                                      "acceptable_signed_deltas atom",
        "bound": "not_branch_governed means outside that union. It does not establish that a "
                 "document is universally required; the benchmark contains no full per-unit "
                 "reference checklist, so that cannot be tested here.",
        "reference_changes_by_direction": {"added": ref_dir["+"], "withdrawn": ref_dir["-"]},
        "changed_guards_per_pair": {str(k): v for k, v in sorted(guards.items())},
        "pairs_with_more_than_one_changed_guard": sum(v for k, v in guards.items() if k > 1),
        "pairs_total": len(casepath_rows),
        "pairs_with_zero_changed_guards_and_a_predicted_change": silent,
        "monotonicity_bound": "The reference intervention edits one sentence, but the extractor "
                              "changed more than one guard on most pairs, so zero withdrawals "
                              "cannot be attributed to a single branch turning on.",
        "benchmark_note": "Amendment V3 added the bicycle purchase voucher to expected_added and "
                          "acceptable_signed_deltas but not to gold_branch_documents or "
                          "branch_document_universe. Scoring uses the amended fields and the "
                          "voucher never appears as a spurious atom, so no count here changes; "
                          "those two auxiliary fields are stale.",
        "arms": {},
    }
    lines = [r"\begin{tabular}{lrrrrrr}", r"\toprule",
             r"& & \multicolumn{2}{c}{Branch-governed} & & \multicolumn{2}{c}{Direction} \\",
             r"\cmidrule(lr){3-4}\cmidrule(lr){6-7}",
             r"Method & Spurious & this pair & elsewhere & Not governed & added & withdrawn \\",
             r"\midrule"]
    for arm, label in ARMS:
        c = counts[arm]
        total = sum(c[k] for k in KINDS)
        assert total == report["scores"][arm]["spurious_atoms"], \
            f"{label}: attributed {total} != report {report['scores'][arm]['spurious_atoms']}"
        out["arms"][arm] = {"label": label.replace("\\casepath", "CasePath"), "spurious": total,
                            **{k: c[k] for k in KINDS}, "added": c["added"],
                            "withdrawn": c["withdrawn"], "distinct_documents": len(distinct[arm])}
        lines.append(f"{label} & {total} & {c['required_in_one_unit']} & {c['governed_elsewhere']}"
                     f" & {c['not_branch_governed']} & {c['added']} & {c['withdrawn']} \\\\")
        print(f"  {label.replace(chr(92) + 'casepath', 'CasePath'):<18} spurious {total:>3} = "
              f"this pair {c['required_in_one_unit']:>2} / elsewhere {c['governed_elsewhere']:>2} / "
              f"not governed {c['not_branch_governed']:>3}   (+{c['added']} -{c['withdrawn']}, "
              f"{len(distinct[arm])} distinct)")
    lines += [r"\bottomrule", r"\end{tabular}"]

    (HERE / "SPURIOUS_ORIGIN.json").write_text(json.dumps(out, indent=1) + "\n")
    (HERE / "table_spurious_origin.tex").write_text("\n".join(lines) + "\n")
    print(f"\n  branch-governed documents: {len(governed)}")
    print(f"  reference changes: {ref_dir['+']} added, {ref_dir['-']} withdrawn")
    print(f"  changed guards per pair: {dict(sorted(guards.items()))} "
          f"(more than one on {out['pairs_with_more_than_one_changed_guard']} of {len(casepath_rows)})")
    print(f"  pairs with no changed guard yet a predicted change: {silent or 'none'}")


if __name__ == "__main__":
    main()
