#!/usr/bin/env python3
"""Build explorer_data.json for explore.html from released files only.

Every field is copied or derived from benchmark/, predictions/ and expected/; nothing is
recomputed by a different rule than the frozen scorer. In particular the reference realisation
shown for each pair and arm is the one the frozen scorer selected, read from
expected/HELDOUT_RESULT.json, so the correct / spurious / missed marks in the page are exactly
the ones the paper counts.

    python3 build_explorer_data.py
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARMS = [
    ("b5_process_compiled", "CasePath"),
    ("b1_direct", "Direct"),
    ("b3_representation_then_list", "Graph as context"),
    ("b6_evidence_first", "Evidence-first"),
]
CONCEPT_LABEL = {
    "PR_scheduled_valuable_1000": "Scheduled valuable at or above the policy threshold",
    "PR_bicycle_claimed": "A bicycle or e-bike among the stolen items",
    "PR_sim_card_stolen": "SIM-card theft with misuse",
    "PR_third_party_causer": "An identifiable third-party causer",
    "PR_expert_procedure_requested": "A formal expert procedure",
    "PR_repair_over_500": "A repair above the consent threshold",
    "PR_nachfrist_set": "A written demand with a forfeiture period (Nachfrist)",
    "PR_goods_recovered": "Recovery of stolen goods",
    "PR_declined": "Insurer declination",
}


def main() -> None:
    bench = json.loads((HERE / "benchmark" / "BENCHMARK_V3.json").read_text())
    result = json.loads((HERE / "expected" / "HELDOUT_RESULT.json").read_text())
    rows = [dict(r, arm="b5_process_compiled") for r in json.loads((HERE / "predictions" / "heldout" / "casepath.json").read_text())]
    rows += json.loads((HERE / "predictions" / "heldout" / "comparators.json").read_text())

    pairs_by_id = {p["pair_id"]: p for p in bench["pairs"]}
    by_key = {(r["arm"], r["pair_id"]): r for r in rows}
    pair_ids = sorted({r["pair_id"] for r in rows})

    # One shared document vocabulary keeps the payload small and makes set differences obvious.
    vocab: list[str] = []
    index: dict[str, int] = {}

    def idx(atom: str) -> int:
        if atom not in index:
            index[atom] = len(vocab)
            vocab.append(atom)
        return index[atom]

    out_pairs = []
    for pid in pair_ids:
        spec = pairs_by_id[pid]
        entry = {
            "pair_id": pid,
            "concept": spec["scenario"],
            "concept_label": CONCEPT_LABEL.get(spec["scenario"], spec["scenario"]),
            "context_index": spec["context_index"],
            "statement_before": spec["changed_statement_false"],
            "statement_after": spec["changed_statement_true"],
            "acceptable": [[idx(a) for a in alt] for alt in spec["acceptable_signed_deltas"]],
            "arms": {},
        }
        for arm, _label in ARMS:
            row = by_key.get((arm, pid))
            if row is None:
                continue
            predicted = [idx(a) for a in row["predicted_signed_delta"]]
            selected = [idx(a) for a in result["scores"][arm]["selected_gold_realizations"][pid]]
            sel = set(selected)
            entry["arms"][arm] = {
                "predicted": predicted,
                "selected_reference": selected,
                "correct": sorted(a for a in predicted if a in sel),
                "spurious": sorted(a for a in predicted if a not in sel),
                "missed": sorted(a for a in selected if a not in set(predicted)),
                "before_count": len(row["before_documents"]),
                "after_count": len(row["after_documents"]),
            }
            if arm == "b5_process_compiled":
                entry["arms"][arm]["changed_guards"] = row.get("changed_guard_ids", [])
                entry["arms"][arm]["all_requests_source_chained"] = row.get("all_requests_source_chained")
        out_pairs.append(entry)

    payload = {
        "schema": "casepath.branch-benchmark-explorer/1.0.0",
        "generated_by": "build_explorer_data.py",
        "note": "Selected reference realisations and therefore all correct/spurious/missed marks are read "
                "from the frozen scorer's preserved held-out report, not recomputed by this script.",
        "alternative_semantics": bench["alternative_semantics"],
        "arms": [{"key": k, "label": l} for k, l in ARMS],
        "totals": {
            k: {
                "micro_f1": result["scores"][k]["micro_f1"],
                "precision": result["scores"][k]["precision"],
                "recall": result["scores"][k]["recall"],
                "exact_rate": result["scores"][k]["exact_rate"],
                "predicted_atoms": result["scores"][k]["predicted_atoms"],
                "spurious_atoms": result["scores"][k]["spurious_atoms"],
                "missed_atoms": result["scores"][k]["missed_atoms"],
                "family_pair_f1": result["scores"][k]["family_pair_f1"],
            }
            for k, _ in ARMS
        },
        "gold_atoms": result["scores"]["b5_process_compiled"]["gold_atoms"],
        "vocabulary": vocab,
        "pairs": out_pairs,
    }
    path = HERE / "explorer_data.json"
    path.write_text(json.dumps(payload, indent=1) + "\n")

    # Inline the same payload into the page so it opens from disk without a web server.
    # `</` cannot appear inside a script element, and the data is JSON, so escaping the
    # slash is both sufficient and value-preserving.
    page = HERE / "explore.html"
    compact = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")
    html = page.read_text()
    marker = '<script id="inline-data" type="application/json">'
    start = html.index(marker) + len(marker)
    end = html.index("</script>", start)
    page.write_text(html[:start] + compact + html[end:])

    # Consistency check: the per-pair marks must sum to the totals the paper reports.
    for arm, label in ARMS:
        spur = sum(len(p["arms"][arm]["spurious"]) for p in out_pairs)
        miss = sum(len(p["arms"][arm]["missed"]) for p in out_pairs)
        pred = sum(len(p["arms"][arm]["predicted"]) for p in out_pairs)
        t = payload["totals"][arm]
        assert (spur, miss, pred) == (t["spurious_atoms"], t["missed_atoms"], t["predicted_atoms"]), \
            f"{label}: per-pair marks {spur}/{miss}/{pred} != report {t['spurious_atoms']}/{t['missed_atoms']}/{t['predicted_atoms']}"
        print(f"  {label:<18} predicted {pred:>3}  spurious {spur:>3}  missed {miss:>3}  (matches the report)")
    print(f"\nwrote {path.name} ({path.stat().st_size / 1024:.0f} KB) and inlined it into "
          f"{page.name} ({page.stat().st_size / 1024:.0f} KB): {len(out_pairs)} pairs, "
          f"{len(vocab)} distinct signed atoms")


if __name__ == "__main__":
    main()
