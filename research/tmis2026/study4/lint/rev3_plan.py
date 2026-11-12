"""Write REV3_PLAN.json before any rev3 call: estimate, stop line and regime order. DEVELOPMENT, not a result.
python3 -I -B study4/lint/rev3_plan.py"""
import json
from collections import defaultdict
from pathlib import Path
HERE = Path(__file__).resolve().parent
S4 = HERE.parent
rows = []
for p in (HERE / "runs").glob("ledger_dev_*.jsonl"):
    rows += [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
total = sum(float(r.get("usd") or 0) for r in rows)
usd, files = defaultdict(float), defaultdict(set)
for r in rows:
    a = r.get("arm") or ""
    for reg in ("tenancy", "theft", "dismissal"):
        if a in (f"LINT-clean-{reg}", f"LINT-clean_rev1-{reg}"):
            usd[(a.split("-")[1], reg)] += float(r["usd"])
            files[(a.split("-")[1], reg)].add(r["case"])
per = {reg: max(usd[(arm, reg)] / len(files[(arm, reg)]) for arm in ("clean", "clean_rev1")) for reg in ("tenancy", "theft", "dismissal")}
order, cum = [], 0.0
for reg in ("dismissal", "theft", "tenancy"):
    n = len(json.loads((S4 / "dev" / reg / "final" / "MANIFEST.json").read_text())["files"])
    e = n * per[reg]
    cum += e
    order.append({"regime": reg, "files": n, "usd_per_file": round(per[reg], 5), "estimate_usd": round(e, 4), "cumulative": round(cum, 4)})
plan = {"label": "DEVELOPMENT, written before any rev3 call",
        "ledger_total_before_usd": round(total, 6), "budget_usd": 0.70, "stop_launch_at_run_usd": 0.60,
        "stop_usd_ledger_total": round(total + 0.60, 6),
        "cache_estimate": "Every workflow differs from rev1 (the routing question is in every workflow and every reading request), so the routing and reading calls are all new; only document-finder turns that open with an unchanged process reference and identical tool results can come from the cache. Estimate: every call new, at the higher of the per-file cost of the clean arm and of the rev1 re-run per regime (upper bound).",
        "estimate_usd_total": round(cum, 4), "exceeds_stop": cum > 0.60,
        "decision": "Estimate exceeds USD 0.60: whole regimes in the order dismissal, theft, tenancy; launching stops when the ledger total reaches before + 0.60; only complete regimes are reported as such." if cum > 0.60 else "Estimate under USD 0.60: all regimes.",
        "order": order, "workers": 4, "arm": "clean_rev3", "model": "gpt-6-luna"}
(HERE / "REV3_PLAN.json").write_text(json.dumps(plan, indent=1) + "\n")
print(json.dumps(plan, indent=1))
