"""Cache-only replay of stored product runs, to show that a product version gives the same results from the same
stored responses. No model call: every request is answered from runs/product/cache or the case-run fails with a cache
miss (case_child.py --mode cache-only).

    <venv>/bin/python harness/speed/replay.py --product WT --label L [--sets dev,study3] [--workers 12] [--env JSON]

Sets (each entry's stored plan file and settings):
- dev: the development runs of the tested commit 6a72159c on fresh/ and dev_probe/ (labels e-check, e-full12, e-full-s4,
  e67-check, probe e);
- study3: every case-run of the finished study's two product designs, runs/study3/confirm/plans_{tenancy,theft}_casepath
  {,_checklist}.json (data fresh2: cache-only replay is the one use allowed).
Writes runs/speed/replay_<label>.json: per case-run the replayed plan entry, and its comparison with the stored entry.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMIS = HERE.parents[1]
OUT = TMIS / "runs" / "speed"
P = TMIS / "runs" / "product"
S3 = TMIS / "runs" / "study3" / "confirm"
SETS = {
    "dev": [("tenancy", "fresh", "checklist", P / "plans_tenancy_gpt-6-luna_fresh_e-check.json"),
            ("tenancy", "fresh", "full", P / "plans_tenancy_gpt-6-luna_fresh_e-full12.json"),
            ("tenancy", "probe", "full", P / "plans_tenancy_gpt-6-luna_probe_e.json"),
            ("theft", "fresh", "checklist", P / "plans_theft_gpt-6-luna_fresh_e-check.json"),
            ("theft", "fresh", "checklist", P / "plans_theft_gpt-6-luna_fresh_e67-check.json"),
            ("theft", "fresh", "full", P / "plans_theft_gpt-6-luna_fresh_e-full-s4.json")],
    "study3": [("tenancy", "fresh2", "full", S3 / "plans_tenancy_casepath.json"),
               ("tenancy", "fresh2", "checklist", S3 / "plans_tenancy_casepath_checklist.json"),
               ("theft", "fresh2", "full", S3 / "plans_theft_casepath.json"),
               ("theft", "fresh2", "checklist", S3 / "plans_theft_casepath_checklist.json")],
}
COMPARED = ("status", "plan", "plan_workflow_only", "product_extra", "calls", "tokens", "agents")


def compare(stored, replayed, regime):
    out = {f: stored.get(f) == replayed.get(f) for f in COMPARED}
    if regime == "theft":
        out["plan_ids"] = stored.get("plan_ids") == replayed.get("plan_ids")
    stored_keys = list(dict.fromkeys(stored.get("keys") or []))
    replay_keys = list(dict.fromkeys((replayed.get("transport") or {}).get("keys") or []))
    out["same_requests"] = sorted(stored_keys) == sorted(replay_keys)
    out["same_request_order"] = stored_keys == replay_keys
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--sets", default="dev,study3")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--env", default="{}")
    ap.add_argument("--only", default=None, help="file:key,... to replay a few entries")
    a = ap.parse_args()
    jobs = []
    for name in a.sets.split(","):
        for regime, data, scope, path in SETS[name]:
            for key, entry in json.loads(path.read_text()).items():
                _, case, run = key.split("|")
                if a.only and f"{path.name}:{key}" not in a.only.split(","):
                    continue
                jobs.append((name, path.name, key, regime, data, scope, case, int(run), entry))
    out_path = OUT / f"replay_{a.label}.json"
    done = json.loads(out_path.read_text()) if out_path.exists() and not a.only else {}
    todo = [j for j in jobs if f"{j[1]}:{j[2]}" not in done]
    print(f"{len(jobs)} case-runs, {len(todo)} to replay", flush=True)

    def one(job):
        name, fname, key, regime, data, scope, case, run, entry = job
        p = subprocess.run([sys.executable, str(HERE / "case_child.py"), "--product", a.product, "--data", data, "--regime", regime,
                            "--case", case, "--run", str(run), "--mode", "cache-only", "--scope", scope, "--env", a.env],
                           capture_output=True, text=True)
        line = next((ln for ln in p.stdout.splitlines() if ln.startswith("RESULT ")), None)
        res = json.loads(line[7:]) if line else {"status": "adapter_error", "error": p.stderr[-1500:]}
        return job, res

    t0 = time.time()
    with ThreadPoolExecutor(a.workers) as pool:
        for i, f in enumerate(as_completed([pool.submit(one, j) for j in todo])):
            (name, fname, key, regime, data, scope, case, run, entry), res = f.result()
            row = {"set": name, "file": fname, "regime": regime, "data": data, "scope": scope,
                   "misses": len((res.get("transport") or {}).get("misses") or []),
                   "compare": compare(entry, res, regime) if res.get("status") != "adapter_error" else None,
                   "replayed": {k: res.get(k) for k in ("status", "error", "plan", "plan_workflow_only", "plan_ids", "product_extra",
                                                         "calls", "tokens", "agents", "result_sha256", "routing_sha256",
                                                         "result_fields_sha256", "checklist_equals_result", "timing")},
                   "replay_keys": list(dict.fromkeys((res.get("transport") or {}).get("keys") or []))}
            done[f"{fname}:{key}"] = row
            if i % 50 == 0 or i == len(todo) - 1:
                out_path.write_text(json.dumps(done, ensure_ascii=False))
                print(f"{i + 1}/{len(todo)} {time.time() - t0:.0f}s", flush=True)
    out_path.write_text(json.dumps(done, ensure_ascii=False))


if __name__ == "__main__":
    main()
