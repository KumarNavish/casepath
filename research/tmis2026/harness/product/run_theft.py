"""Run casepath-internal on fresh theft texts through its HTTP API (run_api.run_case), with the converted reviewed rule
base (workflows/theft-reviewed, convert_theft.py) as its only workflow. Development data.

    python run_theft.py --stories 4,5 [--k 1] [--workers 8] --cap USD [--only text,text]

Per text-run: a fresh app and store; the text is the case's one file (message.txt); case title "Theft claim".
Plans map the product's need ids (d07) back to the catalogue document names the theft scorer uses.
Output: runs/product/plans_theft_<model>_fresh_reviewed.json keyed "PRODUCT|<text>|<run>" and
runs/product/manifest_theft_<model>_fresh_reviewed.json (the product's own parity output plus run settings).
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
for p in (HERE, TMIS / "harness", TMIS / "harness" / "v2", TMIS / "fresh"):
    sys.path.insert(0, str(p))
import run_api  # noqa: E402
import run_product as rp  # noqa: E402

CATALOGUE = HERE / "workflows" / "theft-reviewed"


def map_plan(plan, inv):
    if plan is None:
        return None
    out = dict(plan)
    for key in ("requests", "holds", "added_requests", "added_holds"):
        if key in out:
            out[key] = sorted(inv.get(d, d) for d in out[key])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stories", default="4,5")
    ap.add_argument("--k", type=int, default=1)
    ap.add_argument("--model", default="gpt-6-luna")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--cap", type=float, required=True)
    ap.add_argument("--only", default=None)
    a = ap.parse_args()
    import theft_fresh as T
    from theft_data import doc_ids
    inv = {v.lower(): k for k, v in doc_ids().items()}
    texts = T.texts()
    ids = sorted(t for t, v in texts.items() if str(v["story"]) in a.stories.split(","))
    if a.only:
        ids = [i for i in ids if i in a.only.split(",")]
    P = run_api.load_product(str(rp.PRODUCT_ROOT))
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1",
           **run_api.settings_env("/tmp/manifest-only", CATALOGUE, a.model)}
    cli = subprocess.run([sys.executable, "-m", "casepath", "parity", "--catalogue", str(CATALOGUE)],
                         cwd=str(rp.PRODUCT_ROOT / "casepath-internal"), env=env, capture_output=True, text=True, check=True)
    manifest = json.loads(cli.stdout)
    assert not (manifest.get("git") or {}).get("package_modified")
    manifest.update({"parity_command": f"python -m casepath parity --catalogue {CATALOGUE}",
                     "model_identifier": f"openrouter:openai/{a.model}",
                     "run_settings_env": run_api.settings_env("<temporary>", CATALOGUE, a.model),
                     "entry_point": "create_app + HTTP API (POST cases, files, runs; GET runs, case)", "case_title": "Theft claim",
                     "texts": ids, "runs_per_text": a.k})
    (rp.RUNS / f"manifest_theft_{a.model}_fresh_reviewed.json").write_text(json.dumps(manifest, indent=1, default=str))
    out = rp.RUNS / f"plans_theft_{a.model}_fresh_reviewed.json"
    plans = json.loads(out.read_text()) if out.exists() else {}
    todo = [(t, r) for r in range(a.k) for t in ids if f"PRODUCT|{t}|{r}" not in plans]
    print(f"{len(todo)} to do; tree {manifest['source_tree_sha256'][:16]}; ledger {rp.spent(a.model):.4f} USD", flush=True)

    def one(t, r):
        if rp.spent(a.model) >= a.cap:
            return t, r, None
        t0 = time.time()
        try:
            res = run_api.run_case(P, rp, CATALOGUE, a.model, r, t, texts[t]["text"], [], title="Theft claim")
        except Exception as error:
            res = {"plan": None, "status": "adapter_error", "error": f"{type(error).__name__}: {error}", "usage": []}
        res["seconds"] = round(time.time() - t0, 1)
        return t, r, res

    with ThreadPoolExecutor(a.workers) as pool:
        for f in as_completed([pool.submit(one, t, r) for t, r in todo]):
            t, r, res = f.result()
            if res is None:
                continue
            u = res.pop("usage", []) or []
            res["tokens"] = {"input": sum(x.get("input_tokens", 0) for x in u), "output": sum(x.get("output_tokens", 0) for x in u)}
            res["plan_ids"] = res.get("plan")
            res["plan"] = map_plan(res.get("plan"), inv)
            res["plan_workflow_only"] = map_plan(res.get("plan_workflow_only"), inv)
            plans[f"PRODUCT|{t}|{r}"] = res
            out.write_text(json.dumps(plans, indent=1, ensure_ascii=False))
            p = res.get("plan") or {}
            print(t, r, res["status"], res.get("calls"), "req", len(p.get("requests", [])), "hold", len(p.get("holds", [])),
                  "added", len(p.get("added_requests", [])), res.get("error") or "", f"{res['seconds']}s", flush=True)
    print(f"ledger {rp.spent(a.model):.4f} USD", flush=True)


if __name__ == "__main__":
    main()
