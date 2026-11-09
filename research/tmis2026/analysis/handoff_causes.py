"""Why did CasePath hand whole tenancy claims to a person? (no model calls; cached results only)

For every run whose plan is a whole-claim handoff (validate_interpretation raised), the cause
is classified from the recorded interpretation and verification, in the order the product
checks them. Usage: python3 handoff_causes.py <model_tag>; writes handoff_causes.json (all tags).
"""
import json, os, sys
from collections import defaultdict
TAG = sys.argv[1] if len(sys.argv) > 1 else "gpt-6.1-terra"
os.environ["TMIS_MODEL"] = f"openai/{TAG}"  # bind the client before import
os.environ["TMIS_BUDGET_USD"] = "0"  # cached responses only
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "harness"))
import llm  # noqa: E402,F401
from tenancy_data import claim_ids, reference  # noqa: E402
from tenancy_methods import run_cp  # noqa: E402
from tenancy_score import unscored  # noqa: E402
from casepath_tenancy import proposal_items  # noqa: E402

P = json.loads((HERE.parent / "runs" / f"plans_tenancy_{TAG}.json").read_text())


def cause(plan, it, ver):
    """Name the first admission check the run failed."""
    reason = plan.get("deferral_reason", "")
    if reason == "claim category is outside verified rule scope":
        if it["category"]["family"] == "unsupported":
            return "interpreter_unsupported"
        if ver is None:
            return "other_scope"
        accepted = {c["item_id"]: c["accepted"] for c in ver["checks"]}
        if not ver["family_supported"] and not accepted.get("category", True):
            return "verifier_family_and_category_rejected"
        if not ver["family_supported"]:
            return "verifier_family_not_supported"
        if not accepted.get("category", True):
            return "verifier_category_rejected"
        return "other_scope"
    if reason == "interpretation citation is not an exact claim source span":
        return "citation_not_verbatim"
    if reason in ("duplicate interpretation item",):
        return "duplicate_items"
    return "other:" + reason


res = {}
for variant, field, use_verifier in (("CP", "plan_exact", True), ("CP-noverifier", "plan_exact_no_verifier", False)):
    agg = defaultdict(lambda: {"runs": 0, "required_documents": 0, "claims": set(), "interpreter_family_correct": 0})
    for cid in claim_ids("test"):
        R = set(reference(cid)["request_set"]) - unscored(cid)
        for r in range(3):
            plan = (P.get(f"CP|{cid}|{r}") or {}).get(field)
            if not plan or not plan.get("deferred"):
                continue
            o = run_cp(cid, r)
            it = o["interpret"]["result"]
            ver = (o["verify"] or {}).get("result") if use_verifier else None
            try:
                proposal_items({**it, "steps": [], "knowledge_candidates": []})
                k = cause(plan, it, ver)
            except ValueError:
                k = "duplicate_items"
            a = agg[k]
            a["runs"] += 1; a["required_documents"] += len(R); a["claims"].add(cid)
            a["interpreter_family_correct"] += it["category"]["family"] == reference(cid)["family"]
    res[variant] = {k: {**v, "claims": len(v["claims"])} for k, v in sorted(agg.items())}
# B1 hands a claim over by choosing the family 'unsupported'
agg = {"runs": 0, "required_documents": 0, "claims": set()}
for cid in claim_ids("test"):
    R = set(reference(cid)["request_set"]) - unscored(cid)
    for r in range(3):
        plan = (P.get(f"B1|{cid}|{r}") or {}).get("plan")
        if plan and plan.get("deferred"):
            agg["runs"] += 1; agg["required_documents"] += len(R); agg["claims"].add(cid)
res["B1"] = {"model_chose_unsupported": {**agg, "claims": len(agg["claims"])}} if agg["runs"] else {}
path = HERE / "handoff_causes.json"
allres = json.loads(path.read_text()) if path.exists() else {}
allres[TAG] = res
path.write_text(json.dumps(dict(sorted(allres.items())), indent=1))
print(json.dumps(res, indent=1))
