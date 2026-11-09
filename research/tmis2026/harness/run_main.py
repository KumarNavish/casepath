"""Run the main experiments; plans are written to runs/plans_<exp>_<model>.json.

Usage: python3 run_main.py tenancy|theft [--k 3] [--workers 12] [--split heldout]
The model is taken from TMIS_MODEL (default openai/gpt-6.1-terra).
"""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import llm

ap = argparse.ArgumentParser()
ap.add_argument("exp", choices=["tenancy", "theft"])
ap.add_argument("--k", type=int, default=3)
ap.add_argument("--workers", type=int, default=12)
ap.add_argument("--split", default="heldout")
ap.add_argument("--methods", default=None)
args = ap.parse_args()
tag = llm.MODEL.split("/")[-1]
out_path = llm.RUNS / f"plans_{args.exp}_{tag}.json"
results = json.loads(out_path.read_text()) if out_path.exists() else {}

if args.exp == "tenancy":
    from tenancy_data import claim_ids, sources
    from tenancy_methods import run_b1, run_b2, run_cp
    from casepath_tenancy import casepath_plan_exact
    cases = claim_ids("test" if args.split == "heldout" else "dev")
    methods = {"B1": run_b1, "B2": run_b2, "CP": run_cp}

    def work(m, c, r):
        o = methods[m](c, r)
        if m != "CP":
            return {"plan": o["plan"], "error": o["raw"]["error"]}
        res = {"interpret_error": o["interpret"]["error"],
               "verify_error": (o["verify"] or {}).get("error"), "plan": o["plan"],
               "plan_no_verifier": o["plan_no_verifier"]}
        if o["interpret"]["result"] and o["verify"] and o["verify"]["result"]:
            prop = {**o["interpret"]["result"], "steps": [], "knowledge_candidates": []}
            try:
                res["plan_exact"] = casepath_plan_exact(c, prop, o["verify"]["result"], sources(c))
                res["plan_exact_no_verifier"] = casepath_plan_exact(c, prop, None, sources(c))
            except ValueError as e:
                res["plan_exact"] = {"deferred": True, "deferral_reason": str(e), "requests": [], "holds": []}
            res["judgments"] = {"family": o["interpret"]["result"]["category"]["family"],
                                "conditions": {x["flag"]: x["verdict"] for x in o["interpret"]["result"]["conditions"]},
                                "verifier": {x["item_id"]: x["accepted"] for x in o["verify"]["result"]["checks"]},
                                "family_supported": o["verify"]["result"]["family_supported"]}
        return res
else:
    import theft_methods as tm
    from theft_data import texts
    T = texts()
    cases = sorted(k for k, v in T.items() if (v["story"] != 0) == (args.split == "heldout"))
    methods = {"D": tm.run_direct, "R": tm.run_rules, "CP": tm.run_casepath}

    def work(m, c, r):
        o = methods[m](c, T[c]["text"], r)
        if m != "CP":
            return {"plan": o["plan"], "error": o["raw"]["error"]}
        res = {"interpret_error": o["interpret"]["error"], "verify_error": (o["verify"] or {}).get("error")}
        if o.get("judgments"):
            res.update(judgments=o["judgments"], plan=tm.plan(o["judgments"]),
                       plan_all_routes=tm.plan(o["judgments"], all_routes=True))
        if o.get("judgments_no_verifier"):
            res.update(judgments_no_verifier=o["judgments_no_verifier"], plan_no_verifier=tm.plan(o["judgments_no_verifier"]))
        return res

if args.methods:
    methods = {m: f for m, f in methods.items() if m in args.methods.split(",")}
jobs = [(m, c, r) for r in range(args.k) for c in cases for m in methods
        if f"{m}|{c}|{r}" not in results]
print(f"{len(jobs)} jobs; spent so far {llm.spent():.3f} USD", flush=True)
done = 0
with ThreadPoolExecutor(args.workers) as ex:
    futs = {ex.submit(work, *j): j for j in jobs}
    for f in as_completed(futs):
        m, c, r = futs[f]
        try:
            results[f"{m}|{c}|{r}"] = f.result()
        except llm.BudgetExceeded as e:
            print("STOP:", e, flush=True)
            break
        except Exception as e:  # recorded, never silently dropped
            results[f"{m}|{c}|{r}"] = {"plan": None, "error": f"{type(e).__name__}: {e}"}
        done += 1
        if done % 25 == 0:
            out_path.write_text(json.dumps(results, ensure_ascii=False))
            print(f"{done}/{len(jobs)} done; spent {llm.spent():.3f} USD", flush=True)
out_path.write_text(json.dumps(results, ensure_ascii=False))
print(f"finished; spent {llm.spent():.3f} USD", flush=True)
