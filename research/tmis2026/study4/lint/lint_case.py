"""Child process: one product run on one Study 4 development file with a given workflow directory. Prints "RESULT <json>".
Development material (post hoc, not a result).

    python lint_case.py --product WT --regime R --file ID --run 0 --arm ARM --catalogue DIR --model gpt-6-luna

Adapted from harness/study3/product_case.py (Study 3's path, unchanged in what it runs): the product is imported from the
worktree with run_api.load_product; run_api.settings_env gets the checklist-only settings of Study 3's design
(CASEPATH_RUN_SCOPE=checklist, CASEPATH_MODEL_REASONING=true); store ids are deterministic per (file, run); every model
request goes through run_product.CachingTransport. Changed: the workflow directory, the case files (a Study 4 file from
dev/<regime>/final/), and the output locations (cache, ledger and run records under study4/lint/runs/).
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
S4 = HERE.parent
TMIS = S4.parent
for p in (TMIS / "harness" / "product", TMIS / "harness", TMIS / "harness" / "v2"):
    sys.path.insert(0, str(p))
import run_api  # noqa: E402
import run_product as rp  # noqa: E402

RUNS = HERE / "runs"
EXTRA = {"CASEPATH_MODEL_REASONING": "true", "CASEPATH_RUN_SCOPE": "checklist"}
TITLES = {"tenancy": "Tenancy claim", "theft": "Theft claim", "dismissal": "Employment claim"}


def inputs(regime, fid):
    """The file as it exists in the set: text.txt (degraded where scan_noise is set) and attachments/<doc>.txt,
    uploaded under neutral names attachment_<n>.txt in sorted document-id order."""
    d = S4 / "dev" / regime / "final" / fid
    text = (d / "text.txt").read_text(encoding="utf-8")
    atts = []
    docs = sorted(p for p in (d / "attachments").glob("*.txt") if not p.name.endswith(".clean.txt")) if (d / "attachments").is_dir() else []
    for i, p in enumerate(docs, 1):
        atts.append({"file_name": f"attachment_{i}.txt", "media_type": "text/plain", "bytes": p.read_bytes(), "document": p.stem})
    return text, atts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", required=True)
    ap.add_argument("--regime", required=True, choices=list(TITLES))
    ap.add_argument("--file", required=True)
    ap.add_argument("--run", type=int, default=0)
    ap.add_argument("--arm", required=True)
    ap.add_argument("--catalogue", required=True)
    ap.add_argument("--model", default="gpt-6-luna")
    ap.add_argument("--record", required=True)
    a = ap.parse_args()
    _se = run_api.settings_env
    run_api.settings_env = lambda *x: {**_se(*x), **EXTRA}
    rp.RUNS = RUNS  # ledger: study4/lint/runs/ledger_dev_<model>.jsonl
    rp.CACHE = RUNS / "cache"

    P = run_api.load_product(a.product)
    import casepath.web.store as store
    counter = itertools.count()
    store.new_id = lambda prefix: f"{prefix}_" + hashlib.sha256(f"{a.file}|{a.run}|{prefix}|{next(counter)}".encode()).hexdigest()[:16]
    keys = []

    class Recording(rp.CachingTransport):
        def handle_request(self, request):
            body = request.read()
            keys.append(hashlib.sha256(str(request.url).encode() + b"\0" + body + b"\0" + str(self.run).encode()).hexdigest())
            return super().handle_request(request)

    rp.CachingTransport = lambda model, run, cid: Recording(model, run, cid, arm=a.arm)
    text, atts = inputs(a.regime, a.file)
    res = run_api.run_case(P, rp, Path(a.catalogue), a.model, a.run, a.file, text,
                           [{k: v for k, v in x.items() if k != "document"} for x in atts],
                           title=TITLES[a.regime], record_path=a.record)
    res["keys"] = keys
    res["attachments"] = {x["file_name"]: x["document"] for x in atts}
    print("RESULT " + json.dumps(res, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
