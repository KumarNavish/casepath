"""POST HOC repair of whole-claim handoffs, evaluated on the recorded judgments (no model calls).

Every gpt-6.1-terra handoff and most gpt-6-luna handoffs arise because the verifier rejects the
category item while affirming family_supported. Repair: when the verifier affirms family_supported,
treat its category check as accepted; every other admission rule is unchanged. The repair adjusts the
verifier output passed to the unchanged product function validate_interpretation; product code is
not edited. Variants: (a) repair alone, (b) repair plus the routing presumption of tenancy_extra.py.
A baseline without the repair must reproduce analyze.py's CP-exact rows exactly (checked).

Usage: python3 repair_family.py <model_tag>; writes repair_family.json (all tags)."""
import json, os, random, sys
from collections import defaultdict
from copy import deepcopy
TAG = sys.argv[1] if len(sys.argv) > 1 else "gpt-6.1-terra"
os.environ["TMIS_MODEL"] = f"openai/{TAG}"  # bind the client before import
os.environ["TMIS_BUDGET_USD"] = "0"  # cached responses only
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "harness"))
sys.argv = [sys.argv[0], TAG]  # analyze.py reads its tag from argv
import llm  # noqa: E402,F401
from analyze import paired_bootstrap, signflip_p, summ, tenancy_row, test_meta  # noqa: E402
from tenancy_data import claim_ids, reference, sources  # noqa: E402
from tenancy_methods import run_cp  # noqa: E402
from tenancy_score import unscored  # noqa: E402
from casepath_tenancy import plan_from_verified_exact, proposal_items, templates, validate_interpretation  # noqa: E402

ROUTING = {"lease_termination_dispute": "termination_received", "rent_increase_dispute": "claim_received"}
P = json.loads((HERE.parent / "runs" / f"plans_tenancy_{TAG}.json").read_text())
HANDOFF = {"family": None, "requests": [], "holds": [], "deferred": True}


def repaired(ver):
    ver = deepcopy(ver)
    if ver["family_supported"]:
        for chk in ver["checks"]:
            if chk["item_id"] == "category":
                chk["accepted"] = True
    return ver


def presume_routing(verified):
    flag = ROUTING.get(verified["category"]["family"])
    if flag:
        for c in verified["conditions"]:
            if c["flag"] == flag and c["verdict"] == "unresolved":
                c["verdict"] = "true"
        if flag not in {c["flag"] for c in verified["conditions"]}:
            verified["conditions"].append({"flag": flag, "verdict": "true", "summary": "", "citations": []})
    return verified


def plans_for(cid, r):
    o = run_cp(cid, r)
    it = o["interpret"]["result"]
    if not it:
        return {k: None for k in ("baseline", "repair", "repair_presumption")}  # failed output
    prop = {**it, "steps": [], "knowledge_candidates": []}
    try:
        proposal_items(prop)
    except ValueError:  # duplicate items: the product rejects the interpretation before verification
        return {k: HANDOFF for k in ("baseline", "repair", "repair_presumption")}
    ver = (o["verify"] or {}).get("result")
    if not ver:
        return {k: None for k in ("baseline", "repair", "repair_presumption")}
    srcs = sources(cid)
    out = {}
    for name, v, presume in (("baseline", ver, False), ("repair", repaired(ver), False), ("repair_presumption", repaired(ver), True)):
        try:
            verified = validate_interpretation(templates(), srcs, prop, v)
        except ValueError:
            out[name] = HANDOFF
            continue
        out[name] = plan_from_verified_exact(cid, presume_routing(verified) if presume else verified, srcs)
    return out


def ratio(u_cp, d_cp, u_b, d_b):
    return None if u_b - u_cp <= 1e-12 else max(0.0, (d_cp - d_b) / (u_b - u_cp))


METRICS = {"unsafe": lambda rs: sum(r["fp"] + r["miss"] for r in rs) / len(rs),
           "unsafe_strict": lambda rs: sum(r["fp"] + r["miss"] + r["handed"] for r in rs) / len(rs),
           "deferred_pc": lambda rs: sum(r["held"] + r["handed"] for r in rs) / len(rs)}

cids = claim_ids("test")
fam = {c: reference(c)["family_id"] or reference(c)["family"] for c in cids}
rows = defaultdict(list)
for c in cids:
    R = set(reference(c)["request_set"]) - unscored(c)
    for r in range(3):
        for name, plan in plans_for(c, r).items():
            rows[name].append(tenancy_row(c, plan, R))
        rows["B1"].append(tenancy_row(c, P[f"B1|{c}|{r}"]["plan"], R))
        rows["CP-exact-recorded"].append(tenancy_row(c, P[f"CP|{c}|{r}"]["plan_exact"], R))
assert rows["baseline"] == rows["CP-exact-recorded"], "baseline does not reproduce the recorded CP-exact plans"

res = {"post_hoc": True, "baseline_reproduces_cp_exact": True}
sb = summ(rows["B1"])
for name in ("repair", "repair_presumption"):
    s = summ(rows[name])
    ca, cb = defaultdict(list), defaultdict(list)
    for x in rows[name]:
        ca[fam[x["c"]]].append(x)
    for x in rows["B1"]:
        cb[fam[x["c"]]].append(x)
    contrasts = {}
    for metric, val in METRICS.items():
        diffs = [val(ca[f]) - val(cb[f]) for f in sorted(ca)]
        diff = val(rows[name]) - val(rows["B1"])
        contrasts[metric] = {"a_value": val(rows[name]), "b_value": val(rows["B1"]), "diff": diff,
                             "p_signflip": signflip_p(diffs),
                             "diff_ci": paired_bootstrap(ca, cb, lambda sm, v=val: v([x for cl in sm for x in cl]),
                                                         f"repair|{name}|{metric}"),
                             **test_meta(diffs, diff)}
    d_cp, d_b = s["held_per_claim"] + s["handed_per_claim"], sb["held_per_claim"] + sb["handed_per_claim"]
    res[name] = {"summary": {k: v for k, v in s.items()}, "vs_B1": contrasts,
                 "break_even": {"ratio": ratio(s["unsafe_per_claim"], d_cp, sb["unsafe_per_claim"], d_b),
                                "ratio_strict": ratio(s["unsafe_strict_per_claim"], s["held_per_claim"],
                                                      sb["unsafe_strict_per_claim"], sb["held_per_claim"])}}
path = HERE / "repair_family.json"
allres = json.loads(path.read_text()) if path.exists() else {}
allres[TAG] = res
path.write_text(json.dumps(dict(sorted(allres.items())), indent=1))
print(json.dumps({k: (v if not isinstance(v, dict) else {"summary": {m: v["summary"][m] for m in ("recall", "held_rate", "handed_rate", "silent_miss_rate", "unnecessary_rate", "unsafe_per_claim", "unsafe_strict_per_claim", "handoff_runs")}, "break_even": v["break_even"], "p": {m: c["p_signflip"] for m, c in v["vs_B1"].items()}}) for k, v in res.items()}, indent=1))
