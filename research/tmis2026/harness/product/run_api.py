"""Run casepath-internal on tenancy claims through its public API, exactly as a case worker's browser does.

    python run_api.py [--product /home/user/work/casepath-product-7ff7af64] --set dev12|fresh --label p7ff [--k 3]
                      [--catalogue DIR] [--model gpt-6-luna] [--workers 6] [--cap USD] [--only id,id]

Per claim-run: a fresh app (`create_app`) on a fresh temporary store with the given catalogue and no Knowledge;
POST /api/cases, POST /api/cases/{id}/files for the message and every attachment, POST /api/cases/{id}/runs, poll
GET /api/runs/{id}, then GET /api/cases/{id}. Every stage a real case runs is run, with the app's defaults: settings come
from `load_settings` with only these values set (the run manifest lists them):
  CASEPATH_DATA_DIR (temporary), CASEPATH_WORKFLOW_CATALOGUE, CASEPATH_DEV_USER, the model (provider "databricks" chat
  connector at OpenRouter: CASEPATH_MODEL_*), CASEPATH_ORGANISATION and CASEPATH_WRITING_LANGUAGE (configuration).
The one non-product element is the HTTP transport of the model connector: the same connector class
(`chat_model.ChatCompletionsModel`) with the same settings, given an httpx transport that answers a repeated request
from a cache and records cost (run_product.CachingTransport). It is passed through `create_app(model_factory=...)`.

Output: runs/product/plans_tenancy_<model>_<set>_<label>.json keyed "PRODUCT|<claim>|<run>", and
runs/product/manifest_tenancy_<model>_<set>_<label>.json: the output of the product's own `python -m casepath parity
--catalogue <dir>` (run as a subprocess in the worktree, with the run settings as its environment), plus the run
settings; the in-process manifest of the imported package must have the same source_tree_sha256.
"""
from __future__ import annotations

import argparse
import base64
import importlib
import json
import os
import shutil
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMIS = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(TMIS / "harness"))
sys.path.insert(0, str(TMIS / "fresh"))

WRITING = "in the language of the case files"
ORGANISATION = "the legal-expenses insurer's"


def settings_env(data_dir, catalogue, model):
    return {"CASEPATH_DATA_DIR": str(data_dir), "CASEPATH_WORKFLOW_CATALOGUE": str(catalogue),
            "CASEPATH_DEV_USER": "Case handler (research)",
            "CASEPATH_MODEL_PROVIDER": "databricks", "CASEPATH_MODEL_ENDPOINT": "https://openrouter.ai",
            "CASEPATH_MODEL": model, "CASEPATH_MODEL_GATEWAY_HOSTS": "openrouter.ai",
            "CASEPATH_CHAT_PATH": "/api/v1/chat/completions", "CASEPATH_MODEL_API": "chat",
            "CASEPATH_CA_BUNDLE": "/root/.ccr/ca-bundle.crt",
            "CASEPATH_ORGANISATION": ORGANISATION, "CASEPATH_WRITING_LANGUAGE": WRITING}


def load_product(path):
    sys.path.insert(0, str(Path(path) / "casepath-internal"))
    layout = {"app": "casepath.web.app", "config": "casepath.config", "chat_model": "casepath.agents.chat_model",
              "parity": "casepath.parity", "workflows": "casepath.process.workflows"}  # the package layout since 2821bf3
    if not (Path(path) / "casepath-internal" / "casepath" / "web").is_dir():
        layout = {name: f"casepath_internal.{name}" for name in layout}
    mods = {name: importlib.import_module(module) for name, module in layout.items()}
    assert Path(mods["app"].__file__).resolve().is_relative_to(Path(path).resolve()), "imported another product package"
    return mods


def run_case(P, rp, catalogue, model, run, cid, text, atts, title="Tenancy claim", record_path=None):
    """``record_path``: also write the claim-run's full run record there (gzipped JSON: the run as GET /api/runs/{id}
    returns it and the case as GET /api/cases/{id} returns it), for a replay bundle. Off by default."""
    from fastapi.testclient import TestClient
    data_dir = Path(tempfile.mkdtemp(prefix="cp-api-"))
    try:
        settings = P["config"].load_settings(settings_env(data_dir, catalogue, model))
        transport = rp.CachingTransport(model, run, cid)
        factory = lambda: P["chat_model"].ChatCompletionsModel(settings.model, lambda: "proxy-injected", transport=transport)
        app = P["app"].create_app(settings, model_factory=factory)
        with TestClient(app) as client:
            case = client.post("/api/cases", json={"title": title, "intake": {}}).json()
            files = [("message.txt", text.encode(), "text/plain")] + [(a["file_name"], a["bytes"], a["media_type"]) for a in atts]
            for name, data, media in files:
                r = client.post(f"/api/cases/{case['id']}/files", files={"file": (name, data, media)})
                if r.status_code >= 300:
                    raise RuntimeError(f"upload {name}: {r.status_code} {r.text[:200]}")
            for attempt in range(2):
                run_row = client.post(f"/api/cases/{case['id']}/runs").json()
                while True:
                    state = client.get(f"/api/runs/{run_row['id']}").json()
                    if state["status"] not in {"queued", "running"}:
                        break
                    time.sleep(2)
                if state["status"] == "completed":
                    break
            full = client.get(f"/api/cases/{case['id']}").json()
        if record_path is not None:
            import gzip
            Path(record_path).parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(record_path, "wt", encoding="utf-8") as fh:
                json.dump({"format": "casepath.harness.run_record/1", "claim": cid, "run_index": run, "model": model,
                           "catalogue": str(catalogue), "run": state, "case": full}, fh, ensure_ascii=False, default=str)
        run_full = full["run"]
        outcome = {"status": run_full["status"], "error": run_full.get("error"), "result": run_full.get("result") or {},
                   "routing": run_full.get("routing") or {},
                   "workflow": {"id": run_full["workflow_id"], "version": run_full.get("workflow_version")} if run_full.get("workflow_id") else None}
        catalogue_obj = P["workflows"].Catalogue.load(catalogue)
        return rp.to_plan(outcome, catalogue_obj)
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", default=None)
    ap.add_argument("--k", type=int, default=1)
    ap.add_argument("--set", required=True, choices=["dev12", "fresh"])
    ap.add_argument("--label", required=True)
    ap.add_argument("--catalogue", default=None)
    ap.add_argument("--model", default="gpt-6-luna")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--cap", type=float, required=True, help="stop starting claim-runs once the dev ledger reaches this USD total")
    ap.add_argument("--only", default=None)
    ap.add_argument("--records", action="store_true", help="also store each claim-run's full run record under "
                    "runs/product/records_<model>_<set>_<label>/ (off by default)")
    a = ap.parse_args()
    import run_product as rp  # the caching transport and the plan mapping; imports nothing from the product
    product = a.product or str(rp.PRODUCT_ROOT)
    P = load_product(product)
    assert not any(m.startswith("casepath_internal") for m in sys.modules), "an earlier product package was imported"
    import pilot
    D, ids, default_catalogue = pilot.claims(a.set)
    catalogue = Path(a.catalogue) if a.catalogue else default_catalogue
    if a.only:
        ids = [i for i in ids if i in a.only.split(",")]
    out = rp.RUNS / f"plans_tenancy_{a.model}_{a.set}_{a.label}.json"
    manifest_path = rp.RUNS / f"manifest_tenancy_{a.model}_{a.set}_{a.label}.json"
    import subprocess
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1",
           **settings_env("/tmp/manifest-only", catalogue, a.model)}
    cli = subprocess.run([sys.executable, "-m", "casepath", "parity", "--catalogue", str(catalogue)],
                         cwd=str(Path(product) / "casepath-internal"), env=env, capture_output=True, text=True, check=True)
    manifest = json.loads(cli.stdout)
    in_process = P["parity"].manifest(P["config"].load_settings(settings_env("/tmp/manifest-only", catalogue, a.model)),
                                      catalogue_dir=catalogue, knowledge=[])
    assert in_process["source_tree_sha256"] == manifest["source_tree_sha256"], "imported package differs from the worktree"
    assert not (manifest.get("git") or {}).get("package_modified"), "the product worktree is modified"
    manifest.update({"parity_command": "python -m casepath parity --catalogue " + str(catalogue),
                     "model_identifier": f"openrouter:openai/{a.model}", "interface_language": "en (not used by the agents)",
                     "run_settings_env": {k: v for k, v in settings_env("<temporary>", catalogue, a.model).items()},
                     "model_transport": "chat_model.ChatCompletionsModel with the app's settings; httpx transport = response cache + cost ledger",
                     "entry_point": "create_app + HTTP API (POST cases, files, runs; GET runs, case)",
                     "scoring_views": {"plan": "conservative: workflow needs and process-builder additions marked required",
                                       "plan_workflow_only": "workflow needs only"},
                     "claims": a.set, "claim_ids": ids, "runs_per_claim": a.k})
    manifest_path.write_text(json.dumps(manifest, indent=1, default=str))
    plans = json.loads(out.read_text()) if out.exists() else {}
    todo = [(cid, r) for r in range(a.k) for cid in ids if f"PRODUCT|{cid}|{r}" not in plans]
    print(f"{len(todo)} to do; tree {manifest['source_tree_sha256'][:16]}; spent {rp.spent(a.model):.4f} USD", flush=True)

    def one(cid, r):
        if rp.spent(a.model) >= a.cap:
            return cid, r, {"plan": None, "status": "skipped_budget"}
        text, atts = pilot.inputs(D, cid)
        t0 = time.time()
        try:
            res = run_case(P, rp, catalogue, a.model, r, cid, text, atts,
                           record_path=(rp.RUNS / f"records_{a.model}_{a.set}_{a.label}" / f"{cid}_{r}.json.gz") if a.records else None)
        except Exception as error:  # an adapter failure is recorded, never silently dropped
            res = {"plan": None, "status": "adapter_error", "error": f"{type(error).__name__}: {error}", "usage": []}
        res["seconds"] = round(time.time() - t0, 1)
        return cid, r, res

    with ThreadPoolExecutor(a.workers) as pool:
        for f in as_completed([pool.submit(one, cid, r) for cid, r in todo]):
            cid, r, res = f.result()
            if res["status"] == "skipped_budget":
                continue
            u = res.pop("usage", []) or []
            res["tokens"] = {"input": sum(x.get("input_tokens", 0) for x in u), "cached": sum(x.get("cached_tokens", 0) for x in u),
                             "output": sum(x.get("output_tokens", 0) for x in u)}
            plans[f"PRODUCT|{cid}|{r}"] = res
            out.write_text(json.dumps(plans, indent=1, ensure_ascii=False))
            p = res.get("plan") or {}
            print(cid, r, res["status"], res.get("calls"), p.get("family"), "req", len(p.get("requests", [])), "hold", len(p.get("holds", [])),
                  "def", p.get("deferred"), res.get("error") or "", flush=True)
    print(f"spent {rp.spent(a.model):.4f} USD", flush=True)


if __name__ == "__main__":
    main()
