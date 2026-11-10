"""Run casepath-internal on tenancy claims through its public API, exactly as a case worker's browser does.

    python run_api.py --product /home/user/work/casepath-sync --set dev12|fresh --label sync [--model gpt-6-luna]
                      [--workers 6] [--cap 2.50] [--only id,id]

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
runs/product/manifest_tenancy_<model>_<set>_<label>.json (casepath_internal.parity manifest plus run settings).
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
    mods = {name: importlib.import_module(f"casepath_internal.{name}") for name in ("app", "config", "chat_model", "parity", "workflows")}
    assert Path(mods["app"].__file__).resolve().is_relative_to(Path(path).resolve()), "imported another casepath_internal"
    return mods


def run_case(P, rp, catalogue, model, run, cid, text, atts):
    from fastapi.testclient import TestClient
    data_dir = Path(tempfile.mkdtemp(prefix="cp-api-"))
    try:
        settings = P["config"].load_settings(settings_env(data_dir, catalogue, model))
        transport = rp.CachingTransport(model, run, cid)
        factory = lambda: P["chat_model"].ChatCompletionsModel(settings.model, lambda: "proxy-injected", transport=transport)
        app = P["app"].create_app(settings, model_factory=factory)
        with TestClient(app) as client:
            case = client.post("/api/cases", json={"title": "Tenancy claim", "intake": {}}).json()
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
    ap.add_argument("--product", required=True)
    ap.add_argument("--set", required=True, choices=["dev12", "fresh"])
    ap.add_argument("--label", required=True)
    ap.add_argument("--catalogue", default=None)
    ap.add_argument("--model", default="gpt-6-luna")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--cap", type=float, default=2.50)
    ap.add_argument("--only", default=None)
    a = ap.parse_args()
    P = load_product(a.product)
    import run_product as rp  # the caching transport and the plan mapping; it imports the as-built product only by path
    import pilot
    D, ids, default_catalogue = pilot.claims(a.set)
    catalogue = Path(a.catalogue) if a.catalogue else default_catalogue
    if a.only:
        ids = [i for i in ids if i in a.only.split(",")]
    out = rp.RUNS / f"plans_tenancy_{a.model}_{a.set}_{a.label}.json"
    manifest_path = rp.RUNS / f"manifest_tenancy_{a.model}_{a.set}_{a.label}.json"
    settings = P["config"].load_settings(settings_env("/tmp/manifest-only", catalogue, a.model))
    manifest = P["parity"].manifest(settings, catalogue_dir=catalogue, knowledge=[],
                                    extra={"model_identifier": f"openrouter:openai/{a.model}", "interface_language": "en (not used by the agents)",
                                           "run_settings_env": {k: v for k, v in settings_env("<temporary>", catalogue, a.model).items()},
                                           "model_transport": "chat_model.ChatCompletionsModel with the app's settings; httpx transport = response cache + cost ledger",
                                           "entry_point": "create_app + HTTP API (POST cases, files, runs; GET runs, case)",
                                           "claims": a.set, "claim_ids": ids})
    manifest_path.write_text(json.dumps(manifest, indent=1, default=str))
    plans = json.loads(out.read_text()) if out.exists() else {}
    todo = [cid for cid in ids if f"PRODUCT|{cid}|0" not in plans]
    print(f"{len(todo)} to do; tree {manifest['source_tree_sha256'][:16]}; spent {rp.spent(a.model):.4f} USD", flush=True)

    def one(cid):
        if rp.spent(a.model) >= a.cap:
            return cid, {"plan": None, "status": "skipped_budget"}
        text, atts = pilot.inputs(D, cid)
        t0 = time.time()
        try:
            res = run_case(P, rp, catalogue, a.model, 0, cid, text, atts)
        except Exception as error:  # an adapter failure is recorded, never silently dropped
            res = {"plan": None, "status": "adapter_error", "error": f"{type(error).__name__}: {error}", "usage": []}
        res["seconds"] = round(time.time() - t0, 1)
        return cid, res

    with ThreadPoolExecutor(a.workers) as pool:
        for f in as_completed([pool.submit(one, cid) for cid in todo]):
            cid, res = f.result()
            u = res.pop("usage", []) or []
            res["tokens"] = {"input": sum(x.get("input_tokens", 0) for x in u), "cached": sum(x.get("cached_tokens", 0) for x in u),
                             "output": sum(x.get("output_tokens", 0) for x in u)}
            plans[f"PRODUCT|{cid}|0"] = res
            out.write_text(json.dumps(plans, indent=1, ensure_ascii=False))
            p = res.get("plan") or {}
            print(cid, res["status"], res.get("calls"), p.get("family"), "req", len(p.get("requests", [])), "hold", len(p.get("holds", [])),
                  "def", p.get("deferred"), res.get("error") or "", flush=True)
    print(f"spent {rp.spent(a.model):.4f} USD", flush=True)


if __name__ == "__main__":
    main()
