"""Driver of the planted-defect test (study4 step 2d). Development material, post hoc, not a result.

    <venv>/bin/python study4/lint/run.py --arm clean|blunt|subtle --regime tenancy|theft|dismissal
        [--model gpt-6-luna] [--files id,id | --first-per-type] [--workers 6] [--stop-usd 3.20] [--check-only]

Before anything else: the sealed design (DESIGN.json and DESIGN.sha256) must match; the product's own parity command
(`python -m casepath parity --catalogue DIR`, run in the worktree with the run settings and no bytecode written) must load
the catalogue and show readings 3, open rule "any", run scope "checklist", the tested source tree, and an unmodified
package. Then one product run (run index 0) per file through lint_case.py. Spend = the sum of every row of the ledgers
under study4/lint/runs/ (paid calls only; cached answers write no row); no file is launched once it reaches --stop-usd.
A failed output is stored as failed and never run again.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
S4 = HERE.parent
TMIS = S4.parent
RUNS = HERE / "runs"
PRODUCT = "/home/user/work/casepath-sync-e"
TREE = "030480203f7d10b364e4ecc34e0c0b544c4038e107f489bc2080aba6b349ab4d"
sys.path[:0] = [str(TMIS / "harness" / "product")]
_lock = threading.Lock()


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def spent():
    tot = 0.0
    for p in RUNS.glob("ledger_dev_*.jsonl"):
        for line in p.read_text().splitlines():
            if line.strip():
                tot += float(json.loads(line).get("usd") or 0)
    return tot


def catalogue(arm, regime):
    """The workflows an arm reads. The first lint runs read the rule sets now kept in rules/<regime>/rev0/ (the revision
    after first use, 2026-11-12, changed rules/<regime>/workflow/); arm clean_rev1 reads the revised workflows."""
    if arm == "clean":
        return S4 / "rules" / regime / "rev0" / "workflow"
    if arm == "clean_rev1":
        return S4 / "rules" / regime / "workflow"
    return HERE / "widened" / regime / arm


def check_design():
    h = hashlib.sha256((HERE / "DESIGN.json").read_bytes()).hexdigest()
    sealed = (HERE / "DESIGN.sha256").read_text().split()[0]
    if h != sealed:
        raise SystemExit("DESIGN.json does not match its seal")
    return h


def parity(cat, model):
    import run_api  # settings only; imports nothing from the product at module level
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1",
           **run_api.settings_env("/tmp/manifest-only", cat, model), "CASEPATH_MODEL_REASONING": "true", "CASEPATH_RUN_SCOPE": "checklist"}
    cli = subprocess.run([sys.executable, "-m", "casepath", "parity", "--catalogue", str(cat)], cwd=str(Path(PRODUCT) / "casepath-internal"),
                         env=env, capture_output=True, text=True)
    if cli.returncode != 0:
        raise SystemExit(f"parity failed on {cat}: {cli.stderr[-800:]}")
    m = json.loads(cli.stdout)
    st = m.get("settings") or {}
    problems = []
    if st.get("readings") != 3 or st.get("open_rule") != "any" or st.get("run_scope") != "checklist":
        problems.append(f"settings {st}")
    if m.get("source_tree_sha256") != TREE:
        problems.append(f"source tree {m.get('source_tree_sha256')}")
    if (m.get("git") or {}).get("package_modified"):
        problems.append("package modified")
    return m, problems


def files_of(regime):
    man = json.loads((S4 / "dev" / regime / "final" / "MANIFEST.json").read_text())
    return man["files"]


def first_per_type(regime):
    seen, out = set(), []
    for f in files_of(regime):
        if f["type"] not in seen and not f["denied_event"]:
            seen.add(f["type"])
            out.append(f["file_id"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=["clean", "blunt", "subtle", "clean_rev1"])
    ap.add_argument("--regime", required=True, choices=["tenancy", "theft", "dismissal"])
    ap.add_argument("--model", default="gpt-6-luna")
    ap.add_argument("--files", default=None)
    ap.add_argument("--first-per-type", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--stop-usd", type=float, default=3.20)
    ap.add_argument("--check-only", action="store_true")
    a = ap.parse_args()
    dh = check_design()
    cat = catalogue(a.arm, a.regime)
    m, problems = parity(cat, a.model)
    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / f"parity_{a.arm}_{a.regime}_{a.model}.json").write_text(json.dumps(m, indent=1, default=str) + "\n")
    print(f"design {dh[:16]}; parity on {cat.relative_to(TMIS)}: workflows {sorted((m.get('workflows') or {}).keys()) if isinstance(m.get('workflows'), dict) else m.get('workflows')}; "
          f"settings {m.get('settings')}; problems {problems or 'none'}", flush=True)
    if problems:
        raise SystemExit("parity check failed")
    if a.check_only:
        return
    ids = [f["file_id"] for f in files_of(a.regime)]
    if a.files:
        want = a.files.split(",")
        ids = [i for i in ids if i in want]
    elif a.first_per_type:
        ids = first_per_type(a.regime)
    out = RUNS / f"results_{a.arm}_{a.regime}_{a.model}.json"
    store = json.loads(out.read_text()) if out.exists() else {}
    todo = [i for i in ids if i not in store]
    arm_label = f"LINT-{a.arm}-{a.regime}" + ("" if a.model == "gpt-6-luna" else f"-{a.model}")
    t_start, s_start = now(), spent()
    print(f"{a.arm}/{a.regime}/{a.model}: {len(ids)} files, {len(ids) - len(todo)} stored, {len(todo)} to do; spent {s_start:.4f} USD", flush=True)
    stopped = "complete"

    def one(fid):
        if spent() >= a.stop_usd:
            return fid, None, "stop-usd reached"
        t0 = time.time()
        rec = RUNS / "records" / a.model / a.arm / a.regime / f"{fid}.json.gz"
        p = subprocess.run([sys.executable, str(HERE / "lint_case.py"), "--product", PRODUCT, "--regime", a.regime, "--file", fid,
                            "--run", "0", "--arm", arm_label, "--catalogue", str(cat), "--model", a.model, "--record", str(rec)],
                           capture_output=True, text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        line = next((ln for ln in p.stdout.splitlines() if ln.startswith("RESULT ")), None)
        if line is None and (p.returncode < 0 or "KeyboardInterrupt" in p.stderr):
            return fid, None, "interrupted"
        res = json.loads(line[7:]) if line else {"plan": None, "status": "adapter_error", "error": p.stderr[-1500:], "usage": [], "keys": []}
        u = res.pop("usage", []) or []
        res["tokens"] = {"input": sum(x.get("input_tokens", 0) or 0 for x in u), "cached": sum(x.get("cached_tokens", 0) or 0 for x in u),
                         "output": sum(x.get("output_tokens", 0) or 0 for x in u)}
        res["agents"] = [x.get("agent") for x in u]
        res["seconds"] = round(time.time() - t0, 1)
        res["record"] = str(rec.relative_to(HERE)) if rec.exists() else None
        return fid, res, None

    new, failed = 0, []
    with ThreadPoolExecutor(a.workers) as pool:
        for f in as_completed([pool.submit(one, i) for i in todo]):
            fid, res, why = f.result()
            if res is None:
                stopped = why
                continue
            with _lock:
                store[fid] = res
                tmp = out.with_name(out.name + ".tmp")
                tmp.write_text(json.dumps(store, indent=1, ensure_ascii=False, sort_keys=True, default=str) + "\n")
                os.replace(tmp, out)
            new += 1
            pl = res.get("plan") or {}
            bad = res.get("plan") is None or res.get("status") in {"failed", "adapter_error"}
            if bad:
                failed.append(fid)
            print(f"  {fid} {res.get('status')} family {pl.get('family')} req {len(pl.get('requests', []))} hold {len(pl.get('holds', []))}"
                  f"{' FAILED ' + str(res.get('error'))[:200] if bad else ''}  spent {spent():.4f}", flush=True)
    row = {"start": t_start, "end": now(), "arm": a.arm, "regime": a.regime, "model": a.model, "files_requested": len(ids), "new": new,
           "stored": len(store), "spent_before": round(s_start, 6), "spent_after": round(spent(), 6), "stopped": stopped, "failed_new": failed,
           "design_sha256": dh, "args": vars(a)}
    with (RUNS / "RUNLOG.jsonl").open("a") as fh:
        fh.write(json.dumps(row) + "\n")
    print("DONE " + json.dumps(row), flush=True)


if __name__ == "__main__":
    main()
