"""Run the product on tenancy claims and store its plans.

    python pilot.py --set dev12|fresh [--model gpt-6-luna] [--k 1] [--workers 6] [--cap 2.50]

dev12: the 12 Study 1 development claims of the earlier terra pilots, workflows converted from the original pack.
fresh: the 72 fresh claims (now development data), workflows converted from the pack with the silence-policy clause.
Output: runs/product/plans_tenancy_<model>_<set>.json keyed "PRODUCT|<claim>|<run>".
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMIS = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(TMIS / "harness"))
sys.path.insert(0, str(TMIS / "fresh"))
import run_product as rp  # noqa: E402

DEV12 = ['clm_0b431bbf8391ce3e', 'clm_0c373e693a363f9e', 'clm_0e11979130681bd0', 'clm_136438c6463a5721',
         'clm_16ac3b7054d73cc0', 'clm_1afd6bbf29e6539a', 'clm_280ce47169bdff61', 'clm_2a9c260c26afaa34',
         'clm_2c55cdd816b1d0e8', 'clm_2e6d8907d83dae8f', 'clm_314f2d309fea25e6', 'clm_329b8e1bf37554bf']


def claims(which):
    if which == "dev12":
        import tenancy_data as D
        return D, DEV12, HERE / "workflows" / "original-serial"
    import tenancy_fresh as F
    return F, F.claim_ids("test"), HERE / "workflows" / "fresh-serial"


def inputs(D, cid):
    packet = D.intake(cid)
    msg = packet["customer_message"]
    text = (f"Subject: {msg.get('subject', '')}\n\n" if msg.get("subject") else "") + msg["body"]
    atts = [{"file_name": a["file_name"], "media_type": a["media_type"], "bytes": base64.b64decode(a["content_base64"])}
            for a in packet.get("attachments", [])]
    return text, atts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True, choices=["dev12", "fresh"])
    ap.add_argument("--model", default="gpt-6-luna")
    ap.add_argument("--k", type=int, default=1)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--cap", type=float, default=2.50)
    ap.add_argument("--only", default=None)
    a = ap.parse_args()
    D, ids, catalogue = claims(a.set)
    if a.only:
        ids = [i for i in ids if i in a.only.split(",")]
    out = rp.RUNS / f"plans_tenancy_{a.model}_{a.set}.json"
    plans = json.loads(out.read_text()) if out.exists() else {}
    todo = [(cid, r) for cid in ids for r in range(a.k) if f"PRODUCT|{cid}|{r}" not in plans]
    print(f"{len(todo)} claim-runs to do; spent so far {rp.spent(a.model):.4f} USD", flush=True)

    def one(cid, r):
        if rp.spent(a.model) >= a.cap:
            return cid, r, {"plan": None, "status": "skipped_budget"}
        text, atts = inputs(D, cid)
        t0 = time.time()
        res = rp.run_product(text, atts, catalogue, a.model, r, cid)
        res["seconds"] = round(time.time() - t0, 1)
        return cid, r, res

    with ThreadPoolExecutor(a.workers) as pool:
        futs = [pool.submit(one, cid, r) for cid, r in todo]
        for f in as_completed(futs):
            cid, r, res = f.result()
            u = res.get("usage", [])
            res["tokens"] = {"input": sum(x.get("input_tokens", 0) for x in u), "cached": sum(x.get("cached_tokens", 0) for x in u),
                             "output": sum(x.get("output_tokens", 0) for x in u)}
            res.pop("usage", None)
            plans[f"PRODUCT|{cid}|{r}"] = res
            out.write_text(json.dumps(plans, indent=1, ensure_ascii=False))
            p = res.get("plan") or {}
            print(cid, r, res["status"], res.get("calls"), p.get("family"), "req", len(p.get("requests", [])),
                  "hold", len(p.get("holds", [])), "def", p.get("deferred"), res.get("error") or "", flush=True)
    print(f"spent {rp.spent(a.model):.4f} USD", flush=True)


if __name__ == "__main__":
    main()
