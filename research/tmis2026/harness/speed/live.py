"""Live development runs for the speed work (Part B live measurement, Part D shorter answer). Model calls only through
the harness transport (case_child.py --mode live: cache, then the proxy; cost rows in runs/product/ledger_dev_gpt-6-luna.jsonl
under arm SPEED-<label>-<config>), development data only (fresh/ and dev_probe/); fresh2 is refused.

    <venv>/bin/python harness/speed/live.py --plan partb|partd|probe-base --cap USD [--workers N]

partb: 12 tenancy claims (the 12 of the earlier e-full12 run) and 8 theft texts (stories 4-7: of story i (0-3), the (2i)-th "on-" and the
       (2i+1)-th "unres-" text, sorted, so the changed facts vary), each in four configurations, one case-run at a time, configurations rotated per case:
       base-full / base-check: the tested commit 6a72159c (a git archive of it, unmodified), full and checklist only;
       branch-full / branch-check: the speed branch, full (checklist first) and checklist only.
       Each configuration has its own run index (41-44), so no response is shared between them or with earlier runs.
partd: the shorter answer (CASEPATH_READING_FORM=addressed) on the speed branch, checklist only, three runs (50-52) of the
       72 fresh tenancy claims, the 64 theft texts of stories 4-7 and the 16 probe claims.
probe-base: the tested commit, checklist only, three runs (0-2) of the 16 probe claims: the checklist-only reference for
       the probe (the stored probe runs of the tested commit are full runs; their readings are served from the cache).
Writes runs/speed/live_<plan>.json keyed "<config>|<case>|<run>".
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMIS = HERE.parents[1]
OUT = TMIS / "runs" / "speed"
LEDGER = TMIS / "runs" / "product" / "ledger_dev_gpt-6-luna.jsonl"
SCRATCH = Path(os.environ.get("SPEED_SCRATCH", "/tmp/claude-0/-home-user-casepath/ef865128-25b1-5a5b-af7f-a334bf6c5b16/scratchpad/speed"))
BASE = str(SCRATCH / "base6a7")  # git archive of 6a72159c casepath-internal
BRANCH = "/home/user/work/casepath-speed"


def spent_speed():
    total = 0.0
    if LEDGER.exists():
        for line in LEDGER.read_text().splitlines():
            if '"SPEED-' in line:
                r = json.loads(line)
                if str(r.get("arm", "")).startswith("SPEED-"):
                    total += float(r.get("usd") or 0)
    return total


def tenancy_ids(which):
    if which == "e-full12":
        return sorted({k.split("|")[1] for k in json.loads((TMIS / "runs/product/plans_tenancy_gpt-6-luna_fresh_e-full12.json").read_text())})
    return sorted({k.split("|")[1] for k in json.loads((TMIS / "runs/product/plans_tenancy_gpt-6-luna_fresh_e-check.json").read_text())})


def theft_ids(stories=("4", "5", "6", "7"), pick=False):
    sys.path.insert(0, str(TMIS / "fresh"))
    import theft_fresh as T
    texts = T.texts()
    ids = sorted(t for t, v in texts.items() if str(v["story"]) in stories)
    if not pick:
        return ids
    out = []
    for i, s in enumerate(stories):  # story i: its i-th "on-" text and its (i+4)-th "unres-" text, so the changed facts vary
        mine = [t for t in ids if str(texts[t]["story"]) == s]
        on, unres = [t for t in mine if "-on-" in t], [t for t in mine if "-unres-" in t]
        out += [on[(2 * i) % len(on)], unres[(2 * i + 1) % len(unres)]]
    return out


def probe_ids():
    sys.path.insert(0, str(TMIS / "dev_probe"))
    import tenancy_probe as D
    return sorted({k.split("|")[1] for k in json.loads((TMIS / "runs/product/plans_tenancy_gpt-6-luna_probe_e.json").read_text())})


def tasks(plan):
    if plan == "partb":
        configs = [("base-full", BASE, "full", 41, {}), ("base-check", BASE, "checklist", 42, {}),
                   ("branch-full", BRANCH, "full", 43, {}), ("branch-check", BRANCH, "checklist", 44, {})]
        cases = [("tenancy", "fresh", c) for c in tenancy_ids("e-full12")] + [("theft", "fresh", c) for c in theft_ids(pick=True)]
        out = []
        for i, (regime, data, case) in enumerate(cases):
            rot = configs[i % 4:] + configs[:i % 4]  # rotate the order of the configurations per case
            out += [(name, product, scope, run, env, regime, data, case) for name, product, scope, run, env in rot]
        return out
    if plan == "partd":
        env = {"CASEPATH_READING_FORM": "addressed"}
        cases = [("tenancy", "fresh", c) for c in tenancy_ids("all")] + [("theft", "fresh", c) for c in theft_ids()] + \
                [("tenancy", "probe", c) for c in probe_ids()]
        return [("short-check", BRANCH, "checklist", run, env, regime, data, case) for run in (50, 51, 52) for regime, data, case in cases]
    if plan == "probe-base":
        return [("base-check", BASE, "checklist", run, {}, "tenancy", "probe", c) for run in (0, 1, 2) for c in probe_ids()]
    raise SystemExit(plan)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True, choices=["partb", "partd", "probe-base"])
    ap.add_argument("--cap", type=float, required=True, help="no new case-run starts once all SPEED- arms together reach this USD")
    ap.add_argument("--workers", type=int, default=1)
    a = ap.parse_args()
    out_path = OUT / f"live_{a.plan}.json"
    done = json.loads(out_path.read_text()) if out_path.exists() else {}
    todo = [t for t in tasks(a.plan) if f"{t[0]}|{t[7]}|{t[3]}" not in done]
    print(f"{len(todo)} to do; SPEED spend so far {spent_speed():.4f}", flush=True)

    def one(t):
        name, product, scope, run, env, regime, data, case = t
        if spent_speed() >= a.cap:
            return t, None
        wall = time.time()
        p = subprocess.run([sys.executable, str(HERE / "case_child.py"), "--product", product, "--data", data, "--regime", regime,
                            "--case", case, "--run", str(run), "--mode", "live", "--scope", scope, "--env", json.dumps(env),
                            "--arm", f"SPEED-{a.plan}-{name}"], capture_output=True, text=True)
        line = next((ln for ln in p.stdout.splitlines() if ln.startswith("RESULT ")), None)
        res = json.loads(line[7:]) if line else {"status": "adapter_error", "error": p.stderr[-1500:]}
        res["process_seconds"] = round(time.time() - wall, 2)
        res["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(wall))
        res.update({"config": name, "regime": regime, "data": data, "case": case, "run": run, "scope": scope, "env": env})
        return t, res

    with ThreadPoolExecutor(a.workers) as pool:
        for f in as_completed([pool.submit(one, t) for t in todo]):
            t, res = f.result()
            if res is None:
                continue
            done[f"{t[0]}|{t[7]}|{t[3]}"] = res
            out_path.write_text(json.dumps(done, ensure_ascii=False))
            calls = (res.get("transport") or {}).get("calls") or []
            usd = sum(c.get("usd") or 0 for c in calls)
            tm = res.get("timing") or {}
            print(t[0], t[7], t[3], res.get("status"), f"calls {len(calls)} usd {usd:.5f} checklist {tm.get('to_checklist_s')}s "
                  f"result {tm.get('to_result_s')}s spent {spent_speed():.4f}", (res.get("error") or "")[:150], flush=True)
    print(f"SPEED spend {spent_speed():.4f}", flush=True)


if __name__ == "__main__":
    main()
