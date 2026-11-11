"""Child process: one product case-run through the product's HTTP API, for the speed work. Prints one line "RESULT <json>".

    python case_child.py --product WT --data fresh|probe|fresh2 --regime tenancy|theft --case ID --run R
                         --mode cache-only|live [--scope full|checklist] [--env JSON] [--arm ARM] [--model gpt-6-luna]

What it does is run_api.run_case (harness/product), with three differences, all in this file:
- the model transport is chosen by --mode:
  * cache-only: answers every request from runs/product/cache with the harness's key sha256(url, body, run) and raises
    on a miss (no request ever leaves the process, nothing is written to the ledger or the cache);
  * live: transport.LiveTransport (the caching, cost-recording transport of run_product.py, plus the latency of each
    call), cost rows under --arm in runs/product/ledger_dev_<model>.jsonl;
- the run is polled every 0.2 s (run_api polls every 2 s), and the time from POST /runs to the first time the run carries
  a checklist (the field `checklist` of the speed branch; a product without it: when the run ends) and to the end of the
  run are returned;
- store ids are deterministic per case-run (as harness/study3/product_case.py and the earlier dev runs set them), so
  a request repeated by another arm or a rerun is answered from the cache.
Data: fresh (tenancy claims of fresh/, theft texts of fresh/theft_fresh.py), probe (dev_probe/tenancy_probe.py) and
fresh2 (only through harness/v2/common.py::data, so the fresh2 guard applies; the driver refuses live mode on fresh2,
and this child refuses it too).
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import shutil
import sys
import tempfile
import time

sys.dont_write_bytecode = True
from pathlib import Path  # noqa: E402

HERE = Path(__file__).resolve().parent
TMIS = HERE.parents[1]
for p in (TMIS / "harness" / "product", TMIS / "harness", TMIS / "harness" / "v2", TMIS / "fresh", TMIS / "dev_probe", HERE):
    sys.path.insert(0, str(p))
import run_api  # noqa: E402
import run_product as rp  # noqa: E402
import transport as tp  # noqa: E402

CATALOGUES = {"tenancy": TMIS / "harness" / "product" / "workflows" / "fresh-serial-sync",
              "theft": TMIS / "harness" / "product" / "workflows" / "theft-reviewed"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", required=True)
    ap.add_argument("--data", required=True, choices=["fresh", "probe", "fresh2"])
    ap.add_argument("--regime", required=True, choices=["tenancy", "theft"])
    ap.add_argument("--case", required=True)
    ap.add_argument("--run", type=int, required=True)
    ap.add_argument("--mode", required=True, choices=["cache-only", "live"])
    ap.add_argument("--scope", default="full", choices=["full", "checklist"])
    ap.add_argument("--env", default="{}", help="further product settings as a JSON object")
    ap.add_argument("--arm", default=None)
    ap.add_argument("--model", default="gpt-6-luna")
    ap.add_argument("--save-result", default=None, help="write the run's result (gzipped JSON) here")
    a = ap.parse_args()
    if a.data == "fresh2" and a.mode != "cache-only":
        raise SystemExit("fresh2 is used only for a cache-only replay")
    if a.mode == "live" and not a.arm:
        raise SystemExit("a live run needs --arm for its ledger rows")
    extra = {"CASEPATH_MODEL_REASONING": "true", **({"CASEPATH_RUN_SCOPE": "checklist"} if a.scope == "checklist" else {}),
             **json.loads(a.env)}
    catalogue = CATALOGUES[a.regime]
    P = run_api.load_product(a.product)
    import casepath.web.store as store
    counter = itertools.count()
    store.new_id = lambda prefix: f"{prefix}_" + hashlib.sha256(f"{a.case}|{a.run}|{prefix}|{next(counter)}".encode()).hexdigest()[:16]
    if a.mode == "cache-only":
        transport = tp.CacheOnlyTransport(a.run)
    else:
        transport = tp.LiveTransport(a.model, a.run, a.case, arm=a.arm)
    if a.data == "fresh2":
        import common
        D = common.data(a.regime, "fresh2")
    elif a.data == "probe":
        import tenancy_probe as D
    elif a.regime == "tenancy":
        import pilot
        D, _, _ = pilot.claims("fresh")
    else:
        import theft_fresh as D
    if a.regime == "tenancy":
        import pilot
        text, atts = pilot.inputs(D, a.case)
        title = "Tenancy claim"
    else:
        text, atts, title = D.texts()[a.case]["text"], [], "Theft claim"

    from fastapi.testclient import TestClient
    data_dir = Path(tempfile.mkdtemp(prefix="cp-speed-"))
    timing = {}
    try:
        settings = P["config"].load_settings({**run_api.settings_env(data_dir, catalogue, a.model), **extra})
        factory = lambda: P["chat_model"].ChatCompletionsModel(settings.model, lambda: "proxy-injected", transport=transport)
        app = P["app"].create_app(settings, model_factory=factory)
        with TestClient(app) as client:
            case = client.post("/api/cases", json={"title": title, "intake": {}}).json()
            files = [("message.txt", text.encode(), "text/plain")] + [(x["file_name"], x["bytes"], x["media_type"]) for x in atts]
            for name, data, media in files:
                r = client.post(f"/api/cases/{case['id']}/files", files={"file": (name, data, media)})
                if r.status_code >= 300:
                    raise RuntimeError(f"upload {name}: {r.status_code} {r.text[:200]}")
            for attempt in range(2):  # as run_api.run_case: a run that did not complete is started once more
                t0 = time.monotonic()
                run_row = client.post(f"/api/cases/{case['id']}/runs").json()
                after, checklist_seen = 0, None
                while True:
                    state = client.get(f"/api/runs/{run_row['id']}", params={"after": after}).json()
                    if state.get("events"):
                        after = state["events"][-1]["seq"]
                    if checklist_seen is None and state.get("checklist"):
                        checklist_seen = time.monotonic() - t0
                    if state["status"] not in {"queued", "running"}:
                        break
                    time.sleep(0.2)
                done = time.monotonic() - t0
                timing = {"attempt": attempt, "to_checklist_s": round(checklist_seen if checklist_seen is not None else done, 2),
                          "to_result_s": round(done, 2), "checklist_field": checklist_seen is not None}
                if state["status"] == "completed":
                    break
            full = client.get(f"/api/cases/{case['id']}").json()
            run_final = client.get(f"/api/runs/{run_row['id']}").json()
        run_full = full["run"]
        result = run_full.get("result") or {}
        outcome = {"status": run_full["status"], "error": run_full.get("error"), "result": result,
                   "routing": run_full.get("routing") or {},
                   "workflow": {"id": run_full["workflow_id"], "version": run_full.get("workflow_version")} if run_full.get("workflow_id") else None}
        catalogue_obj = P["workflows"].Catalogue.load(catalogue)
        res = rp.to_plan(outcome, catalogue_obj)
        canon = lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False, default=str)
        res["result_sha256"] = hashlib.sha256(canon(result).encode()).hexdigest()
        res["routing_sha256"] = hashlib.sha256(canon(outcome["routing"]).encode()).hexdigest()
        res["result_fields_sha256"] = {k: hashlib.sha256(canon(v).encode()).hexdigest() for k, v in result.items()}
        if run_final.get("checklist"):
            ck = run_final["checklist"]
            res["checklist_equals_result"] = {
                "evaluation": canon(ck.get("evaluation")) == canon(result.get("evaluation")),
                "facts": canon(ck.get("facts")) == canon(result.get("facts")),
                "documents": canon(ck.get("documents")) == canon(result.get("documents"))}
        if a.save_result:
            Path(a.save_result).parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(a.save_result, "wt", encoding="utf-8") as fh:
                json.dump({"run": run_final, "outcome": outcome}, fh, ensure_ascii=False, default=str)
        res["timing"] = timing
        res["transport"] = transport.report()
        u = res.pop("usage", []) or []
        res["tokens"] = {"input": sum(x.get("input_tokens", 0) or 0 for x in u), "cached": sum(x.get("cached_tokens", 0) or 0 for x in u),
                         "output": sum(x.get("output_tokens", 0) or 0 for x in u)}
        res["agents"] = [x.get("agent") for x in u]
        if a.regime == "theft":  # need ids -> catalogue names, as run_theft.py and the study3 worker store them
            import run_theft
            from theft_data import doc_ids
            inv = {v.lower(): k for k, v in doc_ids().items()}
            res["plan_ids"] = res.get("plan")
            res["plan"] = run_theft.map_plan(res.get("plan"), inv)
            res["plan_workflow_only"] = run_theft.map_plan(res.get("plan_workflow_only"), inv)
        print("RESULT " + json.dumps(res, ensure_ascii=False, default=str))
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
