"""Rules in context (design B1v2p of harness/v2/run.py) on the probe claims.

    cd harness/v2 && TMIS_MODEL=openai/gpt-6-luna TMIS_BUDGET_USD=<cap> python3 ../../dev_probe/run_rules_probe.py --k 2

Calls tenancy_v2.run_b1v2 unchanged (same system material: the fresh pack with the silence clause, same task, schema,
effort and cache), with the probe loader as the data module. Cost goes to runs/v2/ledger_<model>.jsonl (tag method
B1v2p, case pcl_...). Writes runs/v2/plans_tenancy_<model>_probe_dev.json keyed "B1v2p|<claim>|<run>".
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "harness" / "v2"))
import common  # noqa: E402  (sets the v2 ledger before any call)
import llm  # noqa: E402
import tenancy_v2 as mod  # noqa: E402

D = common._load("probe_tenancy_data", HERE / "tenancy_probe.py")
ap = argparse.ArgumentParser()
ap.add_argument("--k", type=int, default=2)
ap.add_argument("--workers", type=int, default=8)
a = ap.parse_args()
out = common.OUT / f"plans_tenancy_{common.TAG}_probe_dev.json"
results = json.loads(out.read_text()) if out.exists() else {}
jobs = [(c, r) for r in range(a.k) for c in D.claim_ids() if f"B1v2p|{c}|{r}" not in results]
print(f"{len(jobs)} jobs; v2 ledger total {common.spent():.4f}", flush=True)
with ThreadPoolExecutor(a.workers) as ex:
    futs = {ex.submit(mod.run_b1v2, D, c, r): (c, r) for c, r in jobs}
    for f in as_completed(futs):
        c, r = futs[f]
        try:
            results[f"B1v2p|{c}|{r}"] = f.result()
        except llm.BudgetExceeded as e:
            print("STOP:", e, flush=True)
            continue
        except Exception as e:  # recorded, never dropped
            results[f"B1v2p|{c}|{r}"] = {"plan": None, "error": f"{type(e).__name__}: {e}"}
out.write_text(json.dumps(results, ensure_ascii=False, indent=1))
print(f"done; v2 ledger total {common.spent():.4f} -> {out}", flush=True)
