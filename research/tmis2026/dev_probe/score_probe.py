"""Score the probe runs with the Study 2 tenancy measures (analysis/study2.py::ten_row). No model calls.

    python3 score_probe.py [--label p90a]

Reads runs/product/plans_tenancy_gpt-6-luna_probe_<label>.json (PRODUCT, plan = conservative view) and
runs/v2/plans_tenancy_<model>_probe_dev.json (B1v2p). Prints the table by claim kind x design and every deviating
claim-run, and writes runs/product/score_tenancy_probe_<label>.json.
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMIS = HERE.parent
sys.path.insert(0, str(TMIS / "analysis"))
sys.path.insert(0, str(HERE))
from study2 import ten_row  # noqa: E402
import tenancy_probe as D  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--label", default="p90a")
a = ap.parse_args()
designs = {
    "Product (luna)": (TMIS / "runs" / "product" / f"plans_tenancy_gpt-6-luna_probe_{a.label}.json", "PRODUCT", 2),
    "Rules in context (luna)": (TMIS / "runs" / "v2" / "plans_tenancy_gpt-6-luna_probe_dev.json", "B1v2p", 2),
    "Rules in context (terra)": (TMIS / "runs" / "v2" / "plans_tenancy_gpt-6.1-terra_probe_dev.json", "B1v2p", 1),
}
rows, dev = [], []
for name, (path, prefix, k) in designs.items():
    plans = json.loads(path.read_text()) if path.exists() else {}
    for cid in D.claim_ids():
        ref = D.reference(cid)
        for r in range(k):
            entry = plans.get(f"{prefix}|{cid}|{r}")
            plan = (entry or {}).get("plan")
            row = ten_row(ref, plan)
            row.update({"design": name, "claim": cid, "run": r, "kind": ref["probe"]["kind"], "slug": ref["probe"]["slug"],
                        "family": ref["family"], "present": entry is not None,
                        "holds_total": len(set((plan or {}).get("holds", [])) - set((plan or {}).get("requests", [])))})
            rows.append(row)
            if row["strict_unsafe"] or row["spurious_hold"] or row["held_req"] or row["correct_hold"] != row["ref_held"] or row["deferred"]:
                dev.append({**row, "requests": (plan or {}).get("requests"), "holds": (plan or {}).get("holds"),
                            "routed": (plan or {}).get("family"), "deferral_reason": (plan or {}).get("deferral_reason")})

table = defaultdict(lambda: defaultdict(int))
for row in rows:
    t = table[(row["kind"], row["design"])]
    t["claim_runs"] += 1
    for key in ("unnecessary", "holds_total", "correct_hold", "premature", "deferred", "strict_unsafe", "missed",
                "requested", "req_now", "held_req", "silent_skip", "spurious_hold", "handed", "ref_held"):
        t[key] += row[key]
print(f"{'kind':8} {'design':26} {'runs':>4} {'unnec/cl':>8} {'held/cl':>7} {'corrhold':>8} {'premat':>6} {'handed':>6} "
      f"{'unsafe/cl':>9} {'req/reqnow':>10} {'missed':>6} {'skip':>4} {'spur':>4}")
for kind in ("denied", "open", "control"):
    for name in designs:
        t = table[(kind, name)]
        n = t["claim_runs"] or 1
        print(f"{kind:8} {name:26} {t['claim_runs']:4d} {t['unnecessary'] / n:8.2f} {t['holds_total'] / n:7.2f} "
              f"{t['correct_hold']:4d}/{t['ref_held']:<3d} {t['premature']:6d} {t['deferred']:6d} {t['strict_unsafe'] / n:9.2f} "
              f"{t['requested']:4d}/{t['req_now']:<5d} {t['missed']:6d} {t['silent_skip']:4d} {t['spurious_hold']:4d}")
print("\nDeviations:")
for d in dev:
    print(d["design"], d["slug"], d["claim"], d["run"], d["kind"], "routed", d["routed"], "deferred", d["deferred"],
          "unsafe", d["strict_unsafe"], "unnec", d["unnecessary"], "missed", d["missed"], "premat", d["premature"],
          "skip", d["silent_skip"], "spur", d["spurious_hold"], "req", d["requests"], "holds", d["holds"])
out = TMIS / "runs" / "product" / f"score_tenancy_probe_{a.label}.json"
out.write_text(json.dumps({"rows": rows, "deviations": dev,
                           "table": {f"{k}|{n}": dict(v) for (k, n), v in table.items()}}, indent=1, ensure_ascii=False))
