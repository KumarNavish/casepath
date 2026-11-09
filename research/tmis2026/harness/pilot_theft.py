import json
from concurrent.futures import ThreadPoolExecutor
import llm, theft_methods as tm
from theft_data import texts, pairs
from theft_score import score_pair

T = texts()
ids = ["s0-off", "s0-on-PR_scheduled_valuable_1000", "s0-on-PR_declined",
       "s0-unres-PR_scheduled_valuable_1000", "s0-unres-PR_bicycle_claimed"]
before = llm.spent()
fn = {"D": tm.run_direct, "R": tm.run_rules, "CP": tm.run_casepath}
jobs = [(m, i) for i in ids for m in fn]
with ThreadPoolExecutor(8) as ex:
    res = dict(ex.map(lambda mi: (mi, fn[mi[0]](mi[1], T[mi[1]]["text"], 0)), jobs))
plans = {}
for (m, i), o in res.items():
    if m == "CP":
        plans[(m, i)] = tm.plan(o["judgments"]) if o.get("judgments") else None
        nu = o.get("judgments") or {}
        print(m, i, "verdicts T/F/U:", sum(v == "true" for v in nu.values()), sum(v == "false" for v in nu.values()),
              sum(v == "unresolved" for v in nu.values()), "| interp err", o["interpret"]["error"], "| verify err", (o["verify"] or {}).get("error"))
    else:
        plans[(m, i)] = o["plan"]
        print(m, i, "requests", len(o["plan"]["requests"]) if o["plan"] else None, "holds", len(o["plan"]["holds"]) if o["plan"] else None, "err", o["raw"]["error"])
for p in pairs():
    if p["off"] in ids and p["variant"] in ids:
        for m in fn:
            print(m, p["pair_id"], score_pair(p, plans[(m, p["off"])], plans[(m, p["variant"])]))
print("pilot cost USD", round(llm.spent() - before, 4))
rows = [json.loads(l) for l in open(llm.LEDGER)][-20:]
for r in rows:
    print(r["tag"]["method"], r["prompt_tokens"], "cached", r["cached_tokens"], "out", r["completion_tokens"], "reason", r["reasoning_tokens"], "cost", r["cost"], "lat", round(r["latency_s"] or 0, 1))
