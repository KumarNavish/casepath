"""Plan section 6 (original-pack ablation): the original extracted pack has eight conditions (guards) that the
verified pack does not contain, so CPv2p never judged them. As the plan states, they are obtained with ONE
additional gpt-6-luna call per theft text (run index 0), with the same case-reading policy and task wording as
CasePath's interpretation call and the same normalised-quotation admission. Used for that ablation only.
Usage: TMIS_MODEL=openai/gpt-6-luna TMIS_BUDGET_USD=<cap> python3 judge_extra.py --data fresh
"""
import argparse
import json

import common
import llm
import theft_methods as tm
import theft_v2

ap = argparse.ArgumentParser()
ap.add_argument("--data", default="fresh")
args = ap.parse_args()
if args.data == "fresh":
    common.require_frozen_plan()
T = common.data("theft", args.data).texts()
prep = json.loads((common.REPO / "data" / "casepath-theft-pairs" / "representation" / "PREPARED.json").read_text())
orig = theft_v2.TheftPack({"overlay": prep["overlay"], "requirements": prep["requirements"],
                           "resolvers": prep["resolvers"], "quarantined_rules": []})
missing = sorted(set(orig.guards) - set(theft_v2.DEFAULT.guards))
guards = {g: orig.guards[g] for g in missing}
schema = tm.obj({"conditions": tm.arr(tm.obj({"guard_id": {"type": "string", "enum": missing},
                                             "verdict": {"type": "string", "enum": ["true", "false", "unresolved"]},
                                             "quote": {"type": "string", "maxLength": 400}}), 20)})
out_path = common.OUT / f"extra_judgments_theft_{common.TAG}_{args.data}.json"
out = json.loads(out_path.read_text()) if out_path.exists() else {}
for t in sorted(T):
    if t in out and out[t].get("judgments"):
        continue
    r = llm.call(system=tm.POLICY + "\n\n" + tm.CP_TASK + json.dumps(guards, ensure_ascii=False), user="CASE:\n" + T[t]["text"],
                 schema=schema, schema_name="casepath_conditions", run=0, max_tokens=3000,
                 tag={"exp": "v2-theft", "method": "origpack-extra-guards", "case": t})
    rows = {}
    for row in (r["result"] or {}).get("conditions", []):
        rows.setdefault(row["guard_id"], row)
    judged = {g: "unresolved" for g in missing}
    for g in missing:
        row = rows.get(g)
        if row and row["verdict"] in {"true", "false"} and row["quote"] and theft_v2.match.contains(T[t]["text"], row["quote"]):
            judged[g] = row["verdict"]
    out[t] = {"judgments": judged if r["result"] else None, "error": r["error"], "raw": r["result"]}
    out_path.write_text(json.dumps(out, ensure_ascii=False))
print(f"{len(out)} texts; failed {sum(1 for v in out.values() if not v['judgments'])}; guards {missing}; spend {common.spent():.4f}")
