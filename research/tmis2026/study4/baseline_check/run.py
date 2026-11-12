"""Run the fair-baseline designs (study4/SPEC.md, step 1). POST HOC, development data.

    python3 run.py estimate                      # no calls: cost estimate from Study 3's measured cost per case-run
    python3 run.py format-check                  # three fresh/ files per design and regime (A: both models; B: terra)
    python3 run.py full [--only BATCH,...] [--workers 6]

Prompts must be sealed first (prompts/SHA256SUMS.json; the run refuses if a sealed file changed). Spend is read from
the two ledgers in runs/ (ledger_<model>.jsonl, every paid call) before every case; no new case starts at
CAP_STOP (4.50 USD, both ledgers together). Batches run in the priority order of the brief. A key already stored is
never run again; a failed output (no plan) is stored as failed, not retried (the client's transport retries only).
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import designs as DS  # noqa: E402

CAP_STOP = 4.50
CAP_HARD = 5.00
# Study 3 measured cost per case-run (analysis/study3_results_fresh2_confirm.json)
S3_COST = {("ric", "luna", "tenancy"): 0.00068, ("ric", "luna", "theft"): 0.00072, ("ric", "terra", "tenancy"): 0.0063,
           ("ric", "terra", "theft"): 0.00408, ("mer", "luna", "tenancy"): 0.00068, ("mer", "luna", "theft"): 0.00174}
# (batch id, design, regime, model short, runs)
BATCHES = [("A-terra-tenancy", "A", "tenancy", "terra", 1), ("A-terra-theft", "A", "theft", "terra", 1),
           ("A-luna-tenancy", "A", "tenancy", "luna", 3), ("A-luna-theft", "A", "theft", "luna", 3),
           ("B-terra-tenancy", "B", "tenancy", "terra", 1), ("B-terra-theft", "B", "theft", "terra", 1)]
N = {"tenancy": 96, "theft": 128}
_lock = threading.Lock()


def estimate():
    """A: Rules in context's cost per case-run on the same model (same material, similar output). B on terra: Study 3's
    luna cost of Model executes rules x the terra/luna ratio of Rules in context on the same regime."""
    rows = []
    for bid, d, reg, m, runs in BATCHES:
        if d == "A":
            per = S3_COST[("ric", m, reg)]
        else:
            per = S3_COST[("mer", "luna", reg)] * S3_COST[("ric", "terra", reg)] / S3_COST[("ric", "luna", reg)]
        rows.append({"batch": bid, "case_runs": N[reg] * runs, "usd_per_case_run": per, "usd": per * N[reg] * runs})
    return rows, sum(r["usd"] for r in rows)


def check_seal():
    seal = json.loads((DS.PROMPTS / "SHA256SUMS.json").read_text())
    bad = [f for f, h in seal["files"].items() if DS.sha((HERE / f).read_text()) != h]
    if bad:
        raise SystemExit(f"sealed files changed: {bad}")
    return seal


def store_path(bid):
    return DS.RUNS / f"plans_{bid}.json"


def load(path):
    return json.loads(path.read_text()) if path.exists() else {}


def save(path, obj):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=True) + "\n")
    tmp.replace(path)


def run_jobs(M, jobs, path, workers, log):
    """jobs: [(key, design, regime, case, run, model, tag)]. Returns why it stopped."""
    store = load(path)
    todo = [j for j in jobs if j[0] not in store]
    stopped = "complete"

    def one(j):
        key, d, reg, case, run, model, tag = j
        with _lock:
            if DS.spent_total() >= CAP_STOP:
                return key, None
        try:
            return key, M.call(d, reg, case, run, model, tag)
        except Exception as e:  # recorded as failed, never retried
            return key, {"plan": None, "error": f"{type(e).__name__}: {e}"[:400]}

    # the first case alone, so that the provider's prompt cache holds the shared system prompt before the parallel
    # calls start (request bodies are unchanged; only the order of sending)
    with ThreadPoolExecutor(workers) as pool:
        futs = []
        if todo:
            first = pool.submit(one, todo[0])
            first.result()
            futs.append(first)
        futs += [pool.submit(one, j) for j in todo[1:]]
        for f in as_completed(futs):
            key, res = f.result()
            if res is None:
                stopped = "cap"
                continue
            with _lock:
                store[key] = res
                save(path, store)
            if res.get("plan") is None:
                log(f"  FAILED {key}: {str(res.get('error'))[:160]}")
    done = sum(j[0] in store for j in jobs)
    return stopped, done, len(jobs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["estimate", "format-check", "full"])
    ap.add_argument("--only", default=None)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    rows, tot = estimate()
    if a.what == "estimate":
        print(json.dumps({"rows": rows, "total_usd": tot}, indent=1))
        return
    check_seal()
    DS.RUNS.mkdir(parents=True, exist_ok=True)
    logf = DS.RUNS / "RUNLOG.txt"

    def log(s):
        line = f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {s}"
        print(line, flush=True)
        with logf.open("a") as f:
            f.write(line + "\n")

    log(f"start {a.what}; ledger total {DS.spent_total():.4f} USD; estimate full {tot:.3f} USD")
    if a.what == "format-check":
        M = DS.Material("fresh")
        ten = M.cases("tenancy")[:3]
        P = M.Dth.pairs()
        on = next(p for p in P if p["kind"] == "on")
        un = next(p for p in P if p["kind"] == "unresolved")
        th = [on["off"], on["variant"], un["variant"]]
        for d, models in (("A", ("luna", "terra")), ("B", ("terra",))):
            for m in models:
                DS.use_model(DS.MODELS[m])
                jobs = [(f"{d}|{m}|{reg}|{c}", d, reg, c, 0, DS.MODELS[m], f"{d}-format")
                        for reg, cs in (("tenancy", ten), ("theft", th)) for c in cs]
                st = run_jobs(M, jobs, DS.RUNS / "format_check.json", a.workers, log)
                log(f"format-check {d}/{m}: {st}; ledger total {DS.spent_total():.4f} USD")
        fc = load(DS.RUNS / "format_check.json")
        for k, v in sorted(fc.items()):
            p = v.get("plan")
            log(f"  {k}: {'PARSED' if p else 'FAILED ' + str(v.get('error'))[:100]}"
                + (f" req {len(p['requests'])} hold {len(p['holds'])}" if p else ""))
        return
    M = DS.Material("fresh2")
    only = set(a.only.split(",")) if a.only else None
    for bid, d, reg, m, runs in BATCHES:
        if only and bid not in only:
            continue
        if DS.spent_total() >= CAP_STOP:
            log(f"cap {CAP_STOP} reached before {bid}")
            break
        model = DS.MODELS[m]
        DS.use_model(model)
        jobs = [(f"{d}|{c}|{r}", d, reg, c, r, model, f"{d}") for r in range(runs) for c in M.cases(reg)]
        t0 = time.time()
        stopped, done, n = run_jobs(M, jobs, store_path(bid), a.workers, log)
        log(f"batch {bid}: {done}/{n} stored, {stopped}, {time.time() - t0:.0f}s; ledger total {DS.spent_total():.4f} USD")
        if stopped != "complete":
            break
    log(f"end; ledger total {DS.spent_total():.4f} USD")


if __name__ == "__main__":
    main()
