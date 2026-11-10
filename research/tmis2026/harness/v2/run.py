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
ap.add_argument("--stories", default=None, help="theft: comma-separated story indices (overrides --split selection)")
ap.add_argument("--dry-run", action="store_true", help="build every request, send nothing, report counts and sizes")
args = ap.parse_args()

if args.data == "fresh" and not args.dry_run:
    common.require_frozen_plan()
DRY = []
if args.dry_run:
    import hashlib

    def _record(**kw):
        DRY.append({"tag": kw["tag"], "run": kw["run"], "system_chars": len(kw["system"]), "user_chars": len(kw["user"]),
                    "system_sha": hashlib.sha256(kw["system"].encode()).hexdigest()[:12],
                    "user_sha": hashlib.sha256(kw["user"].encode()).hexdigest()[:12],
                    "has_silence_clause": "Silence policy" in kw["system"]})
        return {"result": None, "error": "dry-run", "cached": False}
    llm.call = _record
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
    if args.data == "fresh":  # every fresh story is held out
        cases = sorted(T)
    if args.stories:
        cases = sorted(k for k, v in T.items() if str(v["story"]) in args.stories.split(","))
    call = lambda f, c, r: f(c, T[c]["text"], r)
if args.limit:
    cases = cases[:args.limit]
designs = {d: f for d, f in mod.DESIGNS.items() if not args.designs or d in args.designs.split(",")}
out_path = common.OUT / f"plans_{args.exp}_{common.TAG}_{args.data}_{args.split}.json"
if args.dry_run:
    for d, f in designs.items():
        for r in range(args.k):
            for c in cases:
                call(f, c, r)
    summary = {}
    for row in DRY:
        k = row["tag"]["method"]
        s = summary.setdefault(k, {"calls": 0, "system_chars": 0, "user_chars": 0, "distinct_system_prompts": set(),
                                   "with_silence_clause": 0})
        s["calls"] += 1; s["system_chars"] += row["system_chars"]; s["user_chars"] += row["user_chars"]
        s["distinct_system_prompts"].add(row["system_sha"]); s["with_silence_clause"] += row["has_silence_clause"]
    for s in summary.values():
        s["distinct_system_prompts"] = len(s["distinct_system_prompts"])
        s["mean_prompt_tokens_est"] = round((s["system_chars"] + s["user_chars"]) / s["calls"] / 4)
    # identical case material across designs (same claim/text, same run): user message hashes per case
    by_case = {}
    for row in DRY:
        by_case.setdefault(row["tag"]["case"], set()).add(row["user_sha"])
    summary["_cases"] = len(cases)
    summary["_distinct_user_messages_per_case_max"] = max(len(v) for v in by_case.values()) if by_case else 0
    print(json.dumps(summary, indent=1))
    common.dump(common.OUT / f"dryrun_{args.exp}_{common.TAG}_{args.data}.json", summary)
    raise SystemExit(0)
results = json.loads(out_path.read_text()) if out_path.exists() else {}
def transient(entry):
    """A recorded provider failure (502 inside a 200 body) is retried on the next run."""
    text = json.dumps({k: entry.get(k) for k in ("error", "interpret_error", "verify_error")})
    return "no choices" in text


jobs = [(d, c, r) for r in range(args.k) for c in cases for d in designs
        if f"{d}|{c}|{r}" not in results or transient(results[f"{d}|{c}|{r}"] or {})]
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
