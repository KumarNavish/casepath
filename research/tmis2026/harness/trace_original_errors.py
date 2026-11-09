"""Trace each wrong or missed change of CasePath (original ICLR judgments, unified
planner) to the rules and conditions that produced it."""
import json
from collections import Counter
from parity_original import original_judgments
import theft_methods as tm
from theft_data import pairs, best_realization
from theft_score import delta

nu_all = original_judgments("v11-b5-hidden-v5")
rows = []
for p in pairs():
    if p["split"] != "heldout" or p["kind"] != "on":
        continue
    ref = p["reference"]
    nu0 = {g: nu_all[ref["false_unit_id"]].get(g, "unresolved") for g in tm.GUARDS}
    nu1 = {g: nu_all[ref["true_unit_id"]].get(g, "unresolved") for g in tm.GUARDS}
    off, on = tm.plan(nu0), tm.plan(nu1)
    pred = delta(set(off["requests"]), set(on["requests"]))
    selected, _ = best_realization(pred, ref)
    changed_guards = sorted(g for g in tm.GUARDS if nu0[g] != nu1[g])
    t1 = tm.trace(nu1)
    for atom in sorted(set(pred) - set(selected)):
        d = atom[1:]
        rows.append({"pair": p["pair_id"], "condition": p["condition"], "error": "wrong", "atom": atom[:60],
                     "changed_guards": changed_guards, "producers": [o for o in t1.get(d, []) if o["guard"] in changed_guards]})
    for atom in sorted(set(selected) - set(pred)):
        d = atom[1:]
        rows.append({"pair": p["pair_id"], "condition": p["condition"], "error": "missed", "atom": atom[:60],
                     "changed_guards": changed_guards, "already_requested_by": tm.trace(nu0).get(d, [])})
print(Counter((r["condition"], r["error"]) for r in rows))
for r in rows:
    if r["pair"].startswith("s1-"):
        print(json.dumps(r, ensure_ascii=False)[:420])
json.dump(rows, open("../analysis/original_error_trace.json", "w"), indent=1, ensure_ascii=False)
