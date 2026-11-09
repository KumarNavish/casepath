"""Single runner for the Study 2 designs.

Usage (from harness/v2):
  TMIS_MODEL=openai/gpt-6-luna TMIS_BUDGET_USD=<cap> python3 run.py tenancy|theft
      [--data original|fresh] [--split dev|heldout] [--k 3] [--designs CPv2,B1v2,CPv1,B1] [--limit N] [--workers 8]
Plans go to runs/v2/plans_<exp>_<model>_<data>_<split>.json, keyed "<design>|<case>|<run>" with a "plan" entry
in the format analysis/analyze.py reads (requests / holds / family / deferred ...). Failed calls are recorded.
The evolution arms run with evolve.py (sequential by construction).
"""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import common
import llm

ap = argparse.ArgumentParser()
ap.add_argument("exp", choices=["tenancy", "theft"])
ap.add_argument("--data", default="original", choices=["original", "fresh"])
ap.add_argument("--split", default="dev", choices=["dev", "heldout"])
ap.add_argument("--k", type=int, default=3)
ap.add_argument("--designs", default=None)
ap.add_argument("--limit", type=int, default=None, help="first N cases (pilots)")
ap.add_argument("--workers", type=int, default=8)
args = ap.parse_args()

D = common.data(args.exp, args.data)
if args.exp == "tenancy":
    import tenancy_v2 as mod
    cases = D.claim_ids("dev" if args.split == "dev" else "test")
    call = lambda f, c, r: f(D, c, r)
else:
    import theft_v2 as mod
    T = D.texts()
    dev_story = min(v["story"] for v in T.values())
    cases = sorted(k for k, v in T.items() if (v["story"] == dev_story) == (args.split == "dev"))
    call = lambda f, c, r: f(c, T[c]["text"], r)
if args.limit:
    cases = cases[:args.limit]
designs = {d: f for d, f in mod.DESIGNS.items() if not args.designs or d in args.designs.split(",")}
out_path = common.OUT / f"plans_{args.exp}_{common.TAG}_{args.data}_{args.split}.json"
results = json.loads(out_path.read_text()) if out_path.exists() else {}
jobs = [(d, c, r) for r in range(args.k) for c in cases for d in designs if f"{d}|{c}|{r}" not in results]
print(f"{len(jobs)} jobs; v2 spend so far {common.spent():.4f} USD", flush=True)
with ThreadPoolExecutor(args.workers) as ex:
    futs = {ex.submit(call, designs[d], c, r): (d, c, r) for d, c, r in jobs}
    for i, f in enumerate(as_completed(futs), 1):
        d, c, r = futs[f]
        try:
            results[f"{d}|{c}|{r}"] = f.result()
        except llm.BudgetExceeded as e:
            print("STOP:", e, flush=True)
            continue
        except Exception as e:  # recorded, never dropped
            results[f"{d}|{c}|{r}"] = {"plan": None, "error": f"{type(e).__name__}: {e}"}
        if i % 25 == 0:
            out_path.write_text(json.dumps(results, ensure_ascii=False))
out_path.write_text(json.dumps(results, ensure_ascii=False))
print(f"finished; v2 spend {common.spent():.4f} USD -> {out_path.name}", flush=True)
