"""Attribute CasePath's theft errors (new runs) to faulty rules or to judgments."""
import json, sys
from collections import Counter
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "harness"))
import theft_methods as tm
from theft_data import pairs, best_realization
from theft_score import delta

TAG = sys.argv[1] if len(sys.argv) > 1 else "gpt-6.1-terra"
P = json.loads((HERE.parent / "runs" / f"plans_theft_{TAG}.json").read_text())
FAULTY = {"overlay_rule_074", "overlay_rule_084", "overlay_rule_010", "overlay_rule_042", "overlay_rule_003"}
COND_GUARD = {}  # benchmark condition -> guards that should change (from original judgments analysis)
counts = Counter()
examples = []
for p in pairs():
    if p["split"] != "heldout":
        continue
    for r in range(3):
        a, b = P.get(f"CP|{p['off']}|{r}", {}), P.get(f"CP|{p['variant']}|{r}", {})
        if not a.get("judgments") or not b.get("judgments"):
            counts["unavailable"] += 1
            continue
        nu0, nu1 = a["judgments"], b["judgments"]
        changed = {g for g in tm.GUARDS if nu0[g] != nu1[g]}
        off, var = set(tm.plan(nu0)["requests"]), set(tm.plan(nu1)["requests"])
        pred = delta(off, var)
        if p["kind"] == "on":
            selected, _ = best_realization(pred, p["reference"])
            wrong = set(pred) - set(selected)
            missed = set(selected) - set(pred)
        else:
            on_docs = {d.lstrip("+") for o in p["reference"]["acceptable_signed_deltas"] for d in o}
            wrong = set(pred)
            missed = set()
        t0, t1 = tm.trace(nu0), tm.trace(nu1)
        for atom in wrong:
            d = atom[1:]
            producers = (t1 if atom[0] == "+" else t0).get(d, [])
            rules = {o["rule"] for o in producers if o["guard"] in changed or o["guard"] is None}
            kind = "faulty_rule" if rules & FAULTY else "judgment_variance"
            counts[(p["kind"], "wrong", atom[0], kind)] += 1
        for atom in missed:
            d = atom[1:]
            if d in off:
                why = "already_on_both_lists"
            elif not changed:
                why = "condition_not_detected"
            else:
                why = "other"
            counts[(p["kind"], "missed", why)] += 1
        counts[(p["kind"], "pairs")] += 1
        counts[(p["kind"], "changed_guards")] += len(changed)
for k, v in sorted(counts.items(), key=str):
    print(k, v)
