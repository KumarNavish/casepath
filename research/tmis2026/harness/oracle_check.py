"""Oracle check: true flags through the real engine must reproduce reference requests."""
import json
from tenancy_data import claim_ids, reference
from casepath_tenancy import plan_from_verified

rows, mism = 0, []
for split in ("dev", "test"):
    for cid in claim_ids(split):
        ref = reference(cid)
        verified = {"category": {"family": ref["family"], "summary": "", "citations": []},
                    "conditions": [{"flag": f, "verdict": "true" if v else "false", "summary": "", "citations": []}
                                   for f, v in {**ref["implicit_flags"], **ref["scenario"]}.items()],
                    "documents": [], "steps": [], "item_rejections": []}
        plan = plan_from_verified(cid, verified, [])
        rows += 1
        if set(plan["requests"]) != set(ref["request_set"]):
            mism.append((cid, sorted(set(plan["requests"]) - set(ref["request_set"])),
                         sorted(set(ref["request_set"]) - set(plan["requests"]))))
print("claims", rows, "mismatches", len(mism))
for m in mism[:10]:
    print(m)
