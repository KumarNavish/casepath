"""Model-free check: the converted theft workflow under the product's evaluator vs the harness's CP4 plan_exact.

    python3 compare_theft.py [--product <worktree>]

Fails (exit 1) when a document decision differs, or when a document the reviewed rules can demand (requested or held by
plan_exact under some assignment: every condition alone, all together, and the random assignments) has no need in the
workflow."""
import json, random, sys
_PRODUCT = next((sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--product"), "/home/user/work/casepath-product-7ff7af64")
sys.path[:0] = ["/home/user/casepath/research/tmis2026/harness/product", "/home/user/casepath/research/tmis2026/harness",
                "/home/user/casepath/research/tmis2026/harness/v2", f"{_PRODUCT}/casepath-internal"]
import convert_theft as ct
from casepath.process import workflows as W
import load_reviewed, theft_v2
from theft_data import doc_ids
ids = doc_ids()
wf = json.load(open("/home/user/casepath/research/tmis2026/harness/product/workflows/theft-reviewed/household_theft.json"))
pack = theft_v2.TheftPack(load_reviewed.load(ct.RULES), judge_all=True)
g2f = {g: ct.fact_id(g) for g in pack.guards}
used = {f["id"] for f in wf["facts"]}
rng = random.Random(7)
n = agree = docs = 0
for i in range(3000):
    p = [0.15, 0.35, 0.5][i % 3]
    nu = {g: rng.choice(["true"] * 1 + ["false"] * 2 + ["unresolved"] * (3 if i % 2 else 0)) for g in pack.guards}
    ref = pack.plan_exact(nu)
    facts = {g2f[g]: (v == "true") for g, v in nu.items() if v != "unresolved" and g2f[g] in used}
    ev = W.evaluate(wf, facts, {}, checked=True)
    req = {r["document"] for r in ev["documents"] if r["required"] == "yes" and r["status"] == "missing"}
    hold = {r["document"] for r in ev["documents"] if r["required"] == "depends"}
    rq = {ids[d].lower() for d in ref["requests"]}; rh = {ids[d].lower() for d in ref["holds"]}
    n += 1
    for d in {x["id"] for x in wf["documents"]}:
        docs += 1
        agree += ((d in req) == (d in rq)) and ((d in hold) == (d in rh))
    if req != rq or hold != rh:
        print("DIFF", sorted(req ^ rq), sorted(hold ^ rh)); break
print(f"{n} assignments, {agree}/{docs} document decisions agree")
# Every document the rules can demand must have a need in the workflow.
demandable = set()
for g in pack.guards:
    nu = {x: "false" for x in pack.guards}
    nu[g] = "true"
    plan = pack.plan_exact(nu)
    demandable |= set(plan["requests"]) | set(plan["holds"])
plan = pack.plan_exact({x: "true" for x in pack.guards})
demandable |= set(plan["requests"]) | set(plan["holds"])
rng = random.Random(7)
for i in range(3000):
    plan = pack.plan_exact({g: rng.choice(["true", "false", "unresolved"]) for g in pack.guards})
    demandable |= set(plan["requests"]) | set(plan["holds"])
needs = {d["id"] for d in wf["documents"]}
lacking = sorted(d for d in demandable if ids[d].lower() not in needs)
print(f"{len(demandable)} documents the rules can demand; {len(lacking)} without a need in the workflow" + (": " + "; ".join(lacking) if lacking else ""))
if agree != docs or lacking:
    sys.exit(1)
