"""Run the product on the probe claims through harness/product/run_api.run_case, one subprocess per claim-run.

    CASEPATH_PRODUCT=<worktree> <venv>/bin/python run_product_probe.py --label L --k 2 --cap USD_FOR_THIS_ARM [--only id,id]

Settings as the r3 runs (scratchpad tools/measure.py + one_run.py): run_api.settings_env plus CASEPATH_MODEL_REASONING=true,
default (full) run scope, catalogue workflows/fresh-serial-sync, store ids deterministic per claim-run, model calls only
through run_product.CachingTransport (cache runs/product/cache, cost in runs/product/ledger_dev_<model>.jsonl, arm
PRODUCT-<label>). Writes runs/product/plans_tenancy_<model>_probe_<label>.json, manifest_tenancy_<model>_probe_<label>.json
and, per claim-run, the product's full run outcome (routing, facts with both readings, evaluation) to --outcomes.
"""
import argparse
import hashlib
import itertools
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
H = HERE.parent / "harness" / "product"
for p in (H, HERE.parent / "harness", HERE.parent / "fresh", HERE):
    sys.path.insert(0, str(p))
import run_api  # noqa: E402
import run_product as rp  # noqa: E402

_se = run_api.settings_env
run_api.settings_env = lambda *a: {**_se(*a), "CASEPATH_MODEL_REASONING": "true",  # SCOPE=checklist: the checklist-only run scope
                                   **({"CASEPATH_RUN_SCOPE": os.environ["SCOPE"]} if os.environ.get("SCOPE") else {})}
CATALOGUE = H / "workflows" / "fresh-serial-sync"


def child(a):
    P = run_api.load_product(a.product)
    import casepath.web.store as store
    counter = itertools.count()
    store.new_id = lambda prefix: f"{prefix}_" + hashlib.sha256(f"{a.cid}|{a.run}|{prefix}|{next(counter)}".encode()).hexdigest()[:16]
    keys, seen = [], {}

    class Recording(rp.CachingTransport):
        def handle_request(self, request):
            body = request.read()
            keys.append(hashlib.sha256(str(request.url).encode() + b"\0" + body + b"\0" + str(self.run).encode()).hexdigest())
            return super().handle_request(request)

    rp.CachingTransport = lambda model, run, cid: Recording(model, run, cid, arm=a.arm)
    _to_plan = rp.to_plan
    rp.to_plan = lambda outcome, catalogue: (seen.setdefault("outcome", outcome), _to_plan(outcome, catalogue))[1]
    import pilot
    import tenancy_probe as D
    text, atts = pilot.inputs(D, a.cid)
    records = os.environ.get("RECORDS")  # also store the full run record there (off by default)
    res = run_api.run_case(P, rp, CATALOGUE, a.model, a.run, a.cid, text, atts,
                           record_path=(Path(records) / f"{a.cid}_{a.run}.json.gz") if records else None)
    res["keys"] = keys
    Path(a.outcomes).mkdir(parents=True, exist_ok=True)
    (Path(a.outcomes) / f"{a.cid}_{a.run}.json").write_text(json.dumps(seen.get("outcome"), ensure_ascii=False, default=str))
    print("RESULT " + json.dumps(res, ensure_ascii=False, default=str))


def arm_spent(model, arm):
    """Spend recorded under this probe's arm only (other sessions write to the same ledger)."""
    path = rp.RUNS / f"ledger_dev_{model}.jsonl"
    rows = (json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()) if path.exists() else []
    return sum(r["usd"] or 0 for r in rows if r.get("arm") == arm)


def parent(a):
    import tenancy_probe as D
    ids = D.claim_ids()
    if a.only:
        ids = [i for i in ids if i in a.only.split(",")]
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1", **run_api.settings_env("/tmp/manifest-only", CATALOGUE, a.model)}
    cli = subprocess.run([sys.executable, "-m", "casepath", "parity", "--catalogue", str(CATALOGUE)],
                         cwd=str(Path(a.product) / "casepath-internal"), env=env, capture_output=True, text=True, check=True)
    manifest = json.loads(cli.stdout)
    assert not (manifest.get("git") or {}).get("package_modified"), "the product worktree is modified"
    manifest.update({"parity_command": f"python -m casepath parity --catalogue {CATALOGUE}", "model_identifier": f"openrouter:openai/{a.model}",
                     "run_settings_env": run_api.settings_env("<temporary>", CATALOGUE, a.model),
                     "entry_point": "run_api.run_case (create_app + HTTP API), one subprocess per claim-run, store ids deterministic per claim-run",
                     "claims": "dev_probe/claims.json (development probe)", "ids": ids, "runs_per_case": a.k, "label": a.label})
    (rp.RUNS / f"manifest_tenancy_{a.model}_probe_{a.label}.json").write_text(json.dumps(manifest, indent=1, default=str))
    out = rp.RUNS / f"plans_tenancy_{a.model}_probe_{a.label}.json"
    plans = json.loads(out.read_text()) if out.exists() else {}
    todo = [(c, r) for r in range(a.k) for c in ids if f"PRODUCT|{c}|{r}" not in plans]
    print(f"{len(todo)} to do; commit {(manifest.get('git') or {}).get('commit')}; spent {rp.spent(a.model):.4f}", flush=True)

    def one(c, r):
        if arm_spent(a.model, f"PRODUCT-probe-{a.label}") >= a.cap:
            return c, r, None
        t0 = time.time()
        p = subprocess.run([sys.executable, __file__, "--child", "--product", a.product, "--cid", c, "--run", str(r),
                            "--arm", f"PRODUCT-probe-{a.label}", "--model", a.model, "--outcomes", a.outcomes, "--label", a.label],
                           capture_output=True, text=True)
        line = next((ln for ln in p.stdout.splitlines() if ln.startswith("RESULT ")), None)
        res = json.loads(line[7:]) if line else {"plan": None, "status": "adapter_error", "error": p.stderr[-800:], "usage": [], "keys": []}
        res["seconds"] = round(time.time() - t0, 1)
        return c, r, res

    with ThreadPoolExecutor(a.workers) as pool:
        for f in as_completed([pool.submit(one, c, r) for c, r in todo]):
            c, r, res = f.result()
            if res is None:
                continue
            u = res.pop("usage", []) or []
            res["tokens"] = {"input": sum(x.get("input_tokens", 0) or 0 for x in u), "cached": sum(x.get("cached_tokens", 0) or 0 for x in u),
                             "output": sum(x.get("output_tokens", 0) or 0 for x in u)}
            res["agents"] = [x.get("agent") for x in u]
            plans[f"PRODUCT|{c}|{r}"] = res
            out.write_text(json.dumps(plans, indent=1, ensure_ascii=False))
            p = res.get("plan") or {}
            print(c, r, res["status"], res.get("calls"), p.get("family"), "req", len(p.get("requests", [])), "hold", len(p.get("holds", [])),
                  "def", p.get("deferred"), (res.get("error") or "")[:120], f"{res['seconds']}s", f"arm spent {arm_spent(a.model, f'PRODUCT-probe-{a.label}'):.4f}", flush=True)
    print(f"arm spent {arm_spent(a.model, f'PRODUCT-probe-{a.label}'):.4f}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", default=str(rp.PRODUCT_ROOT))
    ap.add_argument("--label", default="p90a")
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--cap", type=float, default=None)
    ap.add_argument("--only")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--model", default="gpt-6-luna")
    ap.add_argument("--outcomes", default=None)
    ap.add_argument("--child", action="store_true")
    ap.add_argument("--cid")
    ap.add_argument("--run", type=int)
    ap.add_argument("--arm")
    a = ap.parse_args()
    a.outcomes = a.outcomes or str(rp.RUNS / f"outcomes_tenancy_{a.model}_probe_{a.label}")
    if a.child:
        child(a)
    else:
        assert a.cap is not None, "--cap is required"
        parent(a)
