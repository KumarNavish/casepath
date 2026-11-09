"""Original study (gpt-5.6-terra, one run, 27 held-out theft pairs), recomputed from the released
predictions and recorded judgments with the frozen scorer; plus the error trace of its CasePath
checklists (original_error_trace.json from harness/trace_original_errors.py). No model calls.
Writes original_study.json."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "harness"))
from theft_data import DATA, pairs  # noqa: E402
from theft_score import score_pair, pooled  # noqa: E402
import theft_methods as tm  # noqa: E402
from parity_original import original_judgments  # noqa: E402

PRED = DATA / "benchmark" / "predictions" / "heldout"
held = {(p["story"], p["condition"]): p for p in pairs() if p["split"] == "heldout" and p["kind"] == "on"}


def score_predictions(rows):
    out = []
    for x in rows:
        p = held[(x["context_index"], x["scenario"])]
        out.append(score_pair(p, {"requests": x["before_documents"], "holds": []}, {"requests": x["after_documents"], "holds": []}))
    return out


def summary(rows):
    s = pooled(rows)
    return {**s, "pairs": len(rows), "required_changes": s["correct"] + s["missed"], "wrong_per_pair": s["wrong"] / len(rows),
            "missed_per_pair": s["missed"] / len(rows)}


table = {"CP-allroutes": summary(score_predictions(json.loads((PRED / "casepath.json").read_text())))}
nu = original_judgments("v11-b5-hidden-v5")
rows = []
for p in held.values():
    ref = p["reference"]
    off = tm.plan({g: nu[ref["false_unit_id"]].get(g, "unresolved") for g in tm.GUARDS})
    on = tm.plan({g: nu[ref["true_unit_id"]].get(g, "unresolved") for g in tm.GUARDS})
    rows.append(score_pair(p, off, on))
table["CP-oneroute"] = summary(rows)
comp = json.loads((PRED / "comparators.json").read_text())
for arm, name in (("b1_direct", "D"), ("b3_representation_then_list", "R"), ("b6_evidence_first", "EvidenceFirst")):
    table[name] = summary(score_predictions([x for x in comp if x["arm"] == arm]))

trace = json.loads((HERE / "original_error_trace.json").read_text())
FAULTY = {"overlay_rule_074", "overlay_rule_084", "overlay_rule_010", "overlay_rule_042", "overlay_rule_003"}
wrong = [r for r in trace if r["error"] == "wrong"]
missed = [r for r in trace if r["error"] == "missed"]
rules_of = lambda r: {o["rule"] for o in r.get("producers", r.get("already_requested_by", []))}
out = {"table": table,
       "trace": {"wrong": len(wrong), "missed": len(missed),
                 "wrong_by_five_rules": sum(bool(rules_of(r) & FAULTY) for r in wrong),
                 "wrong_by_rule_023": sum("overlay_rule_023" in rules_of(r) for r in wrong),
                 "missed_by_five_rules": sum(bool(rules_of(r) & FAULTY) for r in missed)}}
(HERE / "original_study.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
