import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ref = json.loads((ROOT / "reference_contracts/theft.json").read_text())["contract"]
facts = {f["fact_id"]: f for f in ref["facts"]}
caps = {c["capability_id"]: c for c in ref["capabilities"]}
decs = {d["decision_id"]: d for d in ref["decisions"]}
paths = defaultdict(list)

for doc in ref["documents"]:
    for cid in doc["establishes_capabilities"]:
        cap = caps[cid]
        fact = facts[cap["for_fact"]]
        dec = decs[fact["for_decision"]]
        conds = tuple(sorted({x for x in (fact.get("conditional_on"), dec.get("conditional_on")) if x and x != "none"}))
        paths[doc["document_type"]].append((cid, fact["fact_id"], dec["decision_id"], conds))

out = {"scope": ref["scope"], "predicates": []}
for pred in ref["predicates"]:
    pid = pred["predicate_id"]
    closed = set(pred.get("closes_decisions_when_false") or [])
    released = []
    for doc, supports in paths.items():
        external = any(any(c != pid for c in conds) for _, _, _, conds in supports)
        if external:
            continue
        active_true = []
        active_false = []
        for cid, fid, did, conds in supports:
            active_true.append((cid, fid, did, conds))
            if pid not in conds and did not in closed:
                active_false.append((cid, fid, did, conds))
        if active_true and not active_false:
            released.append(doc)
    if released:
        out["predicates"].append({
            "predicate_id": pid,
            "statement": pred["statement"],
            "released_if_false": sorted(released),
            "n_released": len(released),
        })

print(json.dumps(out, ensure_ascii=False, indent=2))
