"""Child process: one product case-run through harness/product/run_api.run_case. Prints one line "RESULT <json>".

    python product_case.py --product WT --data fresh|fresh2 --regime tenancy|theft --case ID --run R --arm ARM
                           --catalogue DIR --env JSON [--model gpt-6-luna]

Adapted from the child of dev_probe/run_product_probe.py (copied, because that one is fixed to the probe claims):
- the product is imported from the worktree with run_api.load_product (which checks the imported package lies there);
- run_api.settings_env gets the extra settings of --env (CASEPATH_MODEL_REASONING, CASEPATH_RUN_SCOPE);
- the store's ids are deterministic per case-run, so a repeated request is answered from the response cache;
- every model request goes through run_product.CachingTransport (cache runs/product/cache, cost in
  runs/product/ledger_dev_<model>.jsonl under --arm); the cache key of each request is recorded in "keys";
- data only through harness/v2/common.py::data(kind, data), so the fresh2 guard applies.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys

sys.dont_write_bytecode = True
from pathlib import Path  # noqa: E402

HERE = Path(__file__).resolve().parent
TMIS = HERE.parents[1]
for p in (TMIS / "harness" / "product", TMIS / "harness", TMIS / "harness" / "v2"):
    sys.path.insert(0, str(p))
import run_api  # noqa: E402
import run_product as rp  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", required=True)
    ap.add_argument("--data", required=True, choices=["fresh", "fresh2"])
    ap.add_argument("--regime", required=True, choices=["tenancy", "theft"])
    ap.add_argument("--case", required=True)
    ap.add_argument("--run", type=int, required=True)
    ap.add_argument("--arm", required=True)
    ap.add_argument("--catalogue", required=True)
    ap.add_argument("--env", required=True, help="extra product settings as a JSON object")
    ap.add_argument("--model", default="gpt-6-luna")
    a = ap.parse_args()
    extra = json.loads(a.env)
    _se = run_api.settings_env
    run_api.settings_env = lambda *x: {**_se(*x), **extra}

    P = run_api.load_product(a.product)
    import casepath.web.store as store
    counter = itertools.count()
    store.new_id = lambda prefix: f"{prefix}_" + hashlib.sha256(f"{a.case}|{a.run}|{prefix}|{next(counter)}".encode()).hexdigest()[:16]
    keys = []

    class Recording(rp.CachingTransport):
        def handle_request(self, request):
            body = request.read()
            keys.append(hashlib.sha256(str(request.url).encode() + b"\0" + body + b"\0" + str(self.run).encode()).hexdigest())
            return super().handle_request(request)

    rp.CachingTransport = lambda model, run, cid: Recording(model, run, cid, arm=a.arm)
    import common  # after the product import: the data loaders and the fresh2 guard
    D = common.data(a.regime, a.data)
    catalogue = Path(a.catalogue)
    if a.regime == "tenancy":
        import pilot  # pilot.inputs: message text and attachments as the earlier product runs built them
        text, atts = pilot.inputs(D, a.case)
        res = run_api.run_case(P, rp, catalogue, a.model, a.run, a.case, text, atts)
    else:
        res = run_api.run_case(P, rp, catalogue, a.model, a.run, a.case, D.texts()[a.case]["text"], [], title="Theft claim")
    res["keys"] = keys
    print("RESULT " + json.dumps(res, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
