"""Re-score the ORIGINAL ICLR held-out judgments (gpt-5.6-terra) with the harness
scorer, in the original all-routes mode and the unified route-selection mode."""
import json
from parity_original import original_judgments
import theft_methods as tm
from theft_data import pairs
from theft_score import score_pair, pooled

nu = original_judgments("v11-b5-hidden-v5")
unit = {}
for p in pairs():
    if p["split"] != "heldout" or p["kind"] != "on":
        continue
    ref = p["reference"]
    unit[p["off"]] = ref["false_unit_id"]; unit[p["variant"]] = ref["true_unit_id"]
for mode, all_routes in (("all routes (ICLR planner)", True), ("route selection (unified)", False)):
    plans = {}
    rows = []
    for p in pairs():
        if p["split"] != "heldout" or p["kind"] != "on":
            continue
        ref = p["reference"]
        off = tm.plan({g: nu[ref["false_unit_id"]].get(g, "unresolved") for g in tm.GUARDS}, all_routes=all_routes)
        on = tm.plan({g: nu[ref["true_unit_id"]].get(g, "unresolved") for g in tm.GUARDS}, all_routes=all_routes)
        rows.append(score_pair(p, off, on))
    print(mode, json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in pooled(rows).items()}))
