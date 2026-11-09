"""Oracle check for the fresh tenancy references (no model calls).

Independently of generate.py, rebuild each claim's verified judgments from its true scenario and
fact states under the silence policy (stated true -> true; absent -> presumed false; routing fact ->
presumed true; raised and left open -> unresolved), attach the supplied files as the loader serves
them with their recorded sufficiency, run the production engine with exact deferral, and require
every reference (document states, request set, held set, answered request set) to be reproduced.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / "harness"))
from tenancy_fresh import claim_ids, intake, reference, sources  # noqa: E402
from casepath_tenancy import plan_from_verified_exact  # noqa: E402

REQ = {"needed_now", "needed_later"}


def run(cid, ref, answered):
    truth = {**ref["implicit_flags"], **ref["scenario"]}
    conds = []
    for f, s in ref["fact_states"].items():
        assert s != "stated_true" or truth[f], (cid, f)          # a stated fact is true
        assert s != "absent" or not truth[f], (cid, f)           # an unmentioned branch fact is false
        if s == "open":
            v = ("true" if truth[f] else "false") if answered else "unresolved"
            assert ref["open_fact"] == {"flag": f, "true_value": truth[f]}, cid
        else:
            v = "true" if s in ("stated_true", "unmentioned") else "false"
        conds.append({"flag": f, "verdict": v, "summary": "", "citations": []})
    srcs = sources(cid)
    docs = [{"document_type": a["document_type"], "artifact_id": a["artifact_id"],
             "assessment": "sufficient" if a["sufficient"] else "insufficient", "summary": "", "citations": [],
             "independently_verified": True} for a in ref["attachments"]]
    assert {a["artifact_id"] for a in ref["attachments"]} == {a["artifact_id"] for a in intake(cid)["attachments"]}, cid
    verified = {"category": {"family": ref["family"], "summary": "", "citations": []}, "conditions": conds,
                "documents": docs, "steps": [], "item_rejections": []}
    plan = plan_from_verified_exact(cid, verified, srcs)
    supplied = {a["document_type"] for a in ref["attachments"]}
    states = {}
    for d, r in plan["document_states"].items():
        states[d] = ("supplied_insufficient" if d in supplied else "required_now") if r in REQ else \
            "held" if r == "held_behind_question" else "supplied_sufficient" if r == "established" else "not_needed"
    return states


bad, n = [], 0
for cid in claim_ids("test"):
    ref = reference(cid)
    s = run(cid, ref, False)
    a = run(cid, ref, True)
    n += 1
    ok = (s == ref["document_states"]
          and sorted(d for d, x in s.items() if x in ("required_now", "supplied_insufficient")) == ref["request_set"]
          and sorted(d for d, x in s.items() if x == "held") == ref["held_set"]
          and a == ref["answered"]["document_states"])
    if not ok:
        bad.append(cid)
print(json.dumps({"claims": n, "references_reproduced": n - len(bad), "mismatches": bad}))
sys.exit(1 if bad or not n else 0)
