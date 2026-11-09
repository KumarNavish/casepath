"""Explanatory analyses for the tenancy runs (no model calls; cached results only)."""
import json, os, sys
# Bind the model before the client is imported (its default model is read at import), and allow
# cached responses only: an uncached call raises BudgetExceeded instead of reaching the API.
TAG = sys.argv[1] if len(sys.argv) > 1 else "gpt-6.1-terra"
os.environ["TMIS_MODEL"] = f"openai/{TAG}"
os.environ["TMIS_BUDGET_USD"] = "0"
from collections import Counter, defaultdict
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "harness"))
import llm
from tenancy_data import claim_ids, reference, sources
from tenancy_methods import run_b1, run_b2, run_cp
from tenancy_score import unscored
from casepath_tenancy import casepath_plan_exact, proposal_items, validate_interpretation, templates, plan_from_verified_exact

ROUTING = {"lease_termination_dispute": "termination_received", "rent_increase_dispute": "claim_received"}
cids = claim_ids("test")
out = {"deferral_causes": Counter(), "citations": {}, "verifier": Counter(), "routing_presumption": Counter(),
       "routing_presumption_all": Counter(), "verifier_by_kind": defaultdict(Counter), "by_type": defaultdict(Counter)}


def cached(run_method, cid, r):
    """The method's cached result, or None if the design was not run with this model."""
    try:
        return run_method(cid, r)["raw"]["result"]
    except llm.BudgetExceeded:
        return None


def exact_rate(rows, srcs):
    text = {s["artifact_id"]: s["text"] for s in srcs}
    n = ok = 0
    for row in rows:
        for c in row.get("citations", []):
            n += 1
            ok += bool(c["quote"]) and c["quote"] in text.get(c["artifact_id"], "")
    return n, ok


cit = defaultdict(lambda: [0, 0])
for cid in cids:
    ref = reference(cid)
    R = set(ref["request_set"]) - unscored(cid)
    srcs = sources(cid)
    for r in range(3):
        b1, b2 = (cached(f, cid, r) for f in (run_b1, run_b2))
        if b1:
            n, ok = exact_rate(b1["documents"], srcs); cit["B1"][0] += n; cit["B1"][1] += ok
        if b2:
            n, ok = exact_rate(b2["conditions"] + b2["supplied_documents"], srcs); cit["B2"][0] += n; cit["B2"][1] += ok
        o = run_cp(cid, r)
        it = o["interpret"]["result"]
        if not it:
            continue
        n, ok = exact_rate(it["conditions"] + it["documents"], srcs); cit["CP-proposal"][0] += n; cit["CP-proposal"][1] += ok
        prop = {**it, "steps": [], "knowledge_candidates": []}
        ver = o["verify"]["result"] if o["verify"] else None
        if ver:
            out["verifier"]["runs"] += 1
            kinds = {f"condition:{c['flag']}": f"condition_{c['verdict']}" for c in it["conditions"]}
            for chk in ver["checks"]:
                out["verifier"]["checked"] += 1
                out["verifier"]["rejected"] += not chk["accepted"]
                kind = kinds.get(chk["item_id"], chk["item_id"].split(":")[0])  # category, condition_<verdict>, document
                out["verifier_by_kind"][kind]["checked"] += 1
                out["verifier_by_kind"][kind]["rejected"] += not chk["accepted"]
            verdicts = {f"condition:{c['flag']}": c["verdict"] for c in it["conditions"]}
            for chk in ver["checks"]:
                if chk["item_id"] in verdicts and not chk["accepted"]:
                    out["verifier"][f"rejected_{verdicts[chk['item_id']]}"] += 1
            out["verifier"]["family_rejected"] += not ver["family_supported"]
        plan = casepath_plan_exact(cid, prop, ver, srcs)
        fam = ref["family"]
        rp_all = out["routing_presumption_all"]  # every run (handoffs included), for the break-even analysis
        rp_all["runs"] += 1; rp_all["nR"] += len(R)
        if plan.get("deferred"):
            out["deferral_causes"]["claim_deferred"] += len(R)
            out["by_type"][fam]["claim_deferred"] += len(R)
            rp_all["handed"] += len(R)
        else:
            held = (set(plan["holds"]) - set(plan["requests"])) & R
            routing_open = ROUTING.get(fam) in set(plan.get("questions", []))
            for d in held:
                cause = "routing_fact" if routing_open else "other_condition"
                out["deferral_causes"][cause] += 1
                out["by_type"][fam][cause] += 1
            # post-hoc counterfactual: presume the routing fact once the family is admitted
            try:
                verified = validate_interpretation(templates(), srcs, prop, ver)
                flag = ROUTING.get(fam)
                if flag:
                    for c in verified["conditions"]:
                        if c["flag"] == flag and c["verdict"] == "unresolved":
                            c["verdict"] = "true"
                    if flag not in {c["flag"] for c in verified["conditions"]}:
                        verified["conditions"].append({"flag": flag, "verdict": "true", "summary": "", "citations": []})
                p2 = plan_from_verified_exact(cid, verified, srcs)
                P2, H2 = set(p2["requests"]) - unscored(cid), set(p2["holds"]) - unscored(cid)
                out["routing_presumption"]["tp"] += len(P2 & R); out["routing_presumption"]["fp"] += len(P2 - R)
                out["routing_presumption"]["defer"] += len((H2 - P2) & R); out["routing_presumption"]["miss"] += len(R - P2 - H2)
                out["routing_presumption"]["nR"] += len(R); out["routing_presumption"]["nP"] += len(P2)
                rp_all["tp"] += len(P2 & R); rp_all["fp"] += len(P2 - R)
                rp_all["held"] += len((H2 - P2) & R); rp_all["miss"] += len(R - P2 - H2)
            except ValueError:
                pass
        out["deferral_causes"]["required_total"] += len(R)
        out["by_type"][fam]["required"] += len(R)
out["citations"] = {k: {"citations": v[0], "exact": v[1], "exact_rate": v[1] / v[0] if v[0] else None} for k, v in cit.items()}
res = {k: (dict(v) if isinstance(v, Counter) else {kk: dict(vv) for kk, vv in v.items()} if isinstance(v, defaultdict) else v)
       for k, v in out.items()}
(HERE / f"tenancy_extra_{TAG}.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
