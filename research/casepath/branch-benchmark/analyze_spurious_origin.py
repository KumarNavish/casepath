#!/usr/bin/env python3
"""Where do the spurious signed changes come from?

    python3 analyze_spurious_origin.py

Aggregate counts say CasePath makes fewer unjustified changes. This asks whether they are the
*kind* of error the architecture predicts.

Each held-out pair intervenes on exactly one branch concept, and in this benchmark every reference
atom belongs to exactly one concept, so each spurious change can be attributed:

  on-branch    the atom belongs to the intervened concept - the system moved the right branch but
               chose the wrong route, or moved it in the wrong direction
  off-branch   the atom belongs to a different concept - the system moved documents that the
               changed fact cannot justify
  off-vocab    the atom is no concept's reference document - a document no branch intervention
               should ever move

CasePath projects its plan from guards, and only a changed guard can change a document, so its
errors should concentrate on-branch. A generator has no such constraint. If that separation does
not appear, the mechanism claim is weaker than the aggregate suggests.

Reads only released files; writes SPURIOUS_ORIGIN.json and table_spurious_origin.tex.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARMS = [("b5_process_compiled", r"\casepath"), ("b1_direct", "Direct"),
        ("b3_representation_then_list", "Graph as context"), ("b6_evidence_first", "Evidence-first")]


def main() -> None:
    bench = json.loads((HERE / "benchmark" / "BENCHMARK_V3.json").read_text())
    report = json.loads((HERE / "expected" / "HELDOUT_RESULT.json").read_text())
    rows = [dict(r, arm="b5_process_compiled")
            for r in json.loads((HERE / "predictions" / "heldout" / "casepath.json").read_text())]
    rows += json.loads((HERE / "predictions" / "heldout" / "comparators.json").read_text())

    # Which concept can justify which document? Built from the reference contract's own
    # acceptable realisations, so it is the benchmark's definition, not a judgement made here.
    owner: dict[str, set[str]] = defaultdict(set)
    for pair in bench["pairs"]:
        for alt in pair["acceptable_signed_deltas"]:
            for atom in alt:
                owner[atom.lstrip("+-")].add(pair["scenario"])
    ambiguous = {d for d, cs in owner.items() if len(cs) > 1}
    if ambiguous:
        raise SystemExit(f"attribution is not well defined: {len(ambiguous)} atom(s) span concepts")

    pair_concept = {p["pair_id"]: p["scenario"] for p in bench["pairs"]}
    counts = {a: defaultdict(int) for a, _ in ARMS}
    distinct: dict[str, set] = {a: set() for a, _ in ARMS}
    examples: dict[str, list] = {a: [] for a, _ in ARMS}
    for row in rows:
        arm, pid = row["arm"], row["pair_id"]
        if arm not in counts or pid not in pair_concept:
            continue
        selected = set(report["scores"][arm]["selected_gold_realizations"][pid])
        for atom in row["predicted_signed_delta"]:
            if atom in selected:
                continue
            doc = atom.lstrip("+-")
            concepts = owner.get(doc)
            if concepts is None:
                kind = "off_vocab"
            elif pair_concept[pid] in concepts:
                kind = "on_branch"
            else:
                kind = "off_branch"
            counts[arm][kind] += 1
            counts[arm]["added" if atom.startswith("+") else "withdrawn"] += 1
            distinct[arm].add(doc)
            if kind != "on_branch" and len(examples[arm]) < 3:
                examples[arm].append({"pair": pid, "intervened": pair_concept[pid], "atom": atom,
                                      "belongs_to": sorted(concepts) if concepts else None})

    # Direction of the justified changes: needed to read the withdrawal counts honestly.
    ref_dir = defaultdict(int)
    for pid, atoms in report["scores"]["b5_process_compiled"]["selected_gold_realizations"].items():
        for atom in atoms:
            ref_dir["added" if atom.startswith("+") else "withdrawn"] += 1

    out = {"schema": "casepath.spurious-origin/1",
           "note": "Attribution of every spurious signed change on the held-out split. Concept "
                   "ownership comes from the reference contract's acceptable realisations; the "
                   "selected realisation per pair and arm is the frozen scorer's own choice.",
           "atoms_in_reference_vocabulary": len(owner),
           "reference_changes_by_direction": dict(ref_dir),
           "reading_note": "Every justified change on this split is an addition, so each withdrawal "
                           "any system makes is unjustified. CasePath's plan is a projection of "
                           "active rules, so a branch turning on can only add documents: its zero "
                           "withdrawals are a structural property of the architecture, not a "
                           "measured surprise. The split therefore does not test whether a system "
                           "correctly withdraws a document when a branch turns off.",
           "arms": {}}
    lines = [r"\begin{tabular}{lrrrrrr}", r"\toprule",
             r"& \multicolumn{3}{c}{Spurious change belongs to} & \multicolumn{3}{c}{Of those} \\",
             r"\cmidrule(lr){2-4}\cmidrule(lr){5-7}",
             r"Method & the intervened branch & another branch & no branch & added & withdrawn & distinct docs \\",
             r"\midrule"]
    for arm, label in ARMS:
        c = counts[arm]
        total = c["on_branch"] + c["off_branch"] + c["off_vocab"]
        assert total == report["scores"][arm]["spurious_atoms"], \
            f"{label}: attributed {total} != report {report['scores'][arm]['spurious_atoms']}"
        out["arms"][arm] = {"label": label.replace("\\casepath", "CasePath"), "spurious": total,
                            "on_branch": c["on_branch"], "off_branch": c["off_branch"],
                            "off_vocab": c["off_vocab"], "added": c["added"],
                            "withdrawn": c["withdrawn"], "distinct_documents": len(distinct[arm]),
                            "examples_not_on_branch": examples[arm]}
        lines.append(f"{label} & {c['on_branch']} & {c['off_branch']} & {c['off_vocab']} & "
                     f"{c['added']} & {c['withdrawn']} & {len(distinct[arm])} \\\\")
        print(f"  {label.replace(chr(92)+'casepath','CasePath'):<18} spurious {total:>3} = "
              f"branch {c['on_branch']:>3} / other {c['off_branch']:>3} / none {c['off_vocab']:>3}"
              f"   (+{c['added']} -{c['withdrawn']}, {len(distinct[arm])} distinct)")
    lines += [r"\bottomrule", r"\end{tabular}"]

    (HERE / "SPURIOUS_ORIGIN.json").write_text(json.dumps(out, indent=1) + "\n")
    (HERE / "table_spurious_origin.tex").write_text("\n".join(lines) + "\n")
    print(f"\n  reference changes by direction: {dict(ref_dir)}")
    print(f"\nwrote SPURIOUS_ORIGIN.json and table_spurious_origin.tex "
          f"({len(owner)} atoms in the reference vocabulary)")


if __name__ == "__main__":
    main()
