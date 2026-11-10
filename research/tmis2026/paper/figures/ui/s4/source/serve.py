"""Serve the frozen product locally for the Section 4 screens, with the harness's model transport.

    <venv>/bin/python serve.py --product <worktree at 6a72159c> --data <empty temporary dir> --port 8791 --cap 0.55

The app is the product's own (`create_app`), with the settings `harness/product/run_api.settings_env` gives every
product run of the paper, plus CASEPATH_MODEL_REASONING=true (the tested configuration; readings, open rule and run
scope stay at the commit's defaults). The catalogue is `harness/product/workflows/fresh-serial-sync` (the three tenancy
workflows). The model connector is the product's `ChatCompletionsModel` with the harness transport
(`run_product.CachingTransport`: response cache and the development cost ledger, rows marked with --arm). The only
addition here is a spend guard: once the ledger rows of this arm reach --cap USD, further model calls fail.
Nothing in the product, the harness or the runs is changed by this script.
"""
import argparse
import json
import sys
from pathlib import Path

TMIS = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(TMIS / "harness" / "product"))

ap = argparse.ArgumentParser()
ap.add_argument("--product", required=True)
ap.add_argument("--data", required=True)
ap.add_argument("--port", type=int, required=True)
ap.add_argument("--cap", type=float, required=True)
ap.add_argument("--arm", default="paper-s4-screens")
ap.add_argument("--model", default="gpt-6-luna")
a = ap.parse_args()

import run_api  # noqa: E402  (settings and product loading, as every product run of the paper)
import run_product as rp  # noqa: E402  (the caching, cost-recording transport)

P = run_api.load_product(a.product)
catalogue = TMIS / "harness" / "product" / "workflows" / "fresh-serial-sync"
env = {**run_api.settings_env(a.data, catalogue, a.model), "CASEPATH_MODEL_REASONING": "true"}
settings = P["config"].load_settings(env)


def arm_spent():
    path = rp.RUNS / f"ledger_dev_{a.model}.jsonl"
    if not path.exists():
        return 0.0
    rows = (json.loads(x) for x in path.read_text().splitlines() if x.strip())
    return sum(r.get("usd") or 0 for r in rows if r.get("arm") == a.arm)


class Guarded(rp.CachingTransport):
    def handle_request(self, request):
        if arm_spent() >= a.cap:
            raise RuntimeError(f"spend guard: {a.arm} reached {a.cap} USD")
        return super().handle_request(request)


transport = Guarded(a.model, 0, "paper-s4-screens", arm=a.arm)
model = P["chat_model"].ChatCompletionsModel(settings.model, lambda: "proxy-injected", transport=transport)
app = P["app"].create_app(settings, model_factory=lambda *args: model)
manifest = P["parity"].manifest(settings, catalogue_dir=catalogue, knowledge=[])
(Path(a.data).parent / "parity.json").write_text(json.dumps(manifest, indent=1, default=str))
print("source tree", manifest["source_tree_sha256"], "git", manifest["git"], "settings", manifest["settings"], flush=True)

import uvicorn  # noqa: E402
uvicorn.run(app, host="127.0.0.1", port=a.port, log_level="warning")
