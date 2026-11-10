"""CP4: claim reader with two independent readings that must agree (cyclic pairing of runs r and r+1 mod 3),
normalised-quotation admission, exact deferral; no verifier, no checker (theft). Also Rules in context on the same pack.

Usage: TMIS_MODEL=... TMIS_BUDGET_USD=... python3 cp4.py --data original|fresh --stories 0,1,2 --pack original|v2p|reviewed
       [--pack-file f] [--designs CP4,Rpack] [--k 3]
Output: runs/v2/cp4/plans_theft_<model>_<data>_<pack>.json keyed "CP4|<text>|<run>" and "Rpack|<text>|<run>".
"""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import common
import llm
import v3

OUT = common.OUT / "cp4"
OUT.mkdir(exist_ok=True)

ap = argparse.ArgumentParser()
ap.add_argument("--data", default="original")
ap.add_argument("--stories", required=True)
ap.add_argument("--pack", default="original", choices=["original", "v2p", "reviewed"])
ap.add_argument("--pack-file", default=None)
ap.add_argument("--designs", default="CP4,Rpack")
ap.add_argument("--k", type=int, default=3)
ap.add_argument("--workers", type=int, default=6)
args = ap.parse_args()

T = common.data("theft", args.data).texts()
texts = sorted(t for t, v in T.items() if str(v["story"]) in args.stories.split(","))
system = v3.TheftV3(v3.theft_pack(args.pack, args.pack_file))


def cp4(t, r):
    a = system.reading(t, T[t]["text"], r)
    b = system.reading(t, T[t]["text"], (r + 1) % args.k)
    if a is None:
        return {"plan": None, "error": "reading failed"}
    nu = {g: (v if v in {"true", "false"} and b is not None and b.get(g) == v else "unresolved") for g, v in a.items()}
    return {"plan": system.tp.plan_exact(nu), "judgments": nu, "reading_a": a, "reading_b": b}


def rpack(t, r):
    return system.tp.run_rv2(t, T[t]["text"], r)


DESIGNS = {"CP4": cp4, "Rpack": rpack}
path = OUT / f"plans_theft_{common.TAG}_{args.data}_{args.pack}.json"
results = json.loads(path.read_text()) if path.exists() else {}
jobs = [(d, t, r) for d in args.designs.split(",") for r in range(args.k) for t in texts if f"{d}|{t}|{r}" not in results]
print(f"{len(jobs)} jobs; v2 spend so far {common.spent():.4f}", flush=True)
with ThreadPoolExecutor(args.workers) as ex:
    futs = {ex.submit(DESIGNS[d], t, r): (d, t, r) for d, t, r in jobs}
    for i, f in enumerate(as_completed(futs), 1):
        d, t, r = futs[f]
        try:
            results[f"{d}|{t}|{r}"] = f.result()
        except llm.BudgetExceeded as e:
            print("STOP:", e, flush=True)
            continue
        except Exception as e:  # noqa: BLE001
            results[f"{d}|{t}|{r}"] = {"plan": None, "error": f"{type(e).__name__}: {e}"}
        if i % 25 == 0:
            path.write_text(json.dumps(results, ensure_ascii=False))
path.write_text(json.dumps(results, ensure_ascii=False))
print(f"finished; v2 spend {common.spent():.4f} -> {path.name}", flush=True)
