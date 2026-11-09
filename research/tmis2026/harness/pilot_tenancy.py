import json, sys
from concurrent.futures import ThreadPoolExecutor
import llm
from tenancy_data import claim_ids, reference, intake
from tenancy_methods import run_b1, run_b2, run_cp
from tenancy_score import score

dev = claim_ids("dev")
fam = {}
for c in dev:
    f = reference(c)["family"]; has = bool(intake(c)["attachments"])
    fam.setdefault((f, has), []).append(c)
pick = []
for f in ["defect_mold_heating", "lease_termination_dispute", "rent_increase_dispute"]:
    pick += (fam.get((f, True), [])[:1] + fam.get((f, False), [])[:1])
print("pilot claims", pick)
before = llm.spent()
jobs = [(m, c) for c in pick for m in ("B1", "B2", "CP")]
fn = {"B1": run_b1, "B2": run_b2, "CP": run_cp}
with ThreadPoolExecutor(8) as ex:
    outs = list(ex.map(lambda mc: (mc, fn[mc[0]](mc[1], 0)), jobs))
for (m, c), o in outs:
    plan = o.get("plan")
    s = score(c, plan)
    extra = ""
    if m == "CP":
        s2 = score(c, o.get("plan_no_verifier"))
        extra = f" | no-verifier tp/fp/fn={s2['tp']}/{s2['fp']}/{s2['fn']}"
        if plan and plan.get("deferred"): extra += f" DEFERRED: {plan.get('deferral_reason')}"
    err = (o.get("raw") or o.get("interpret") or {}).get("error")
    print(f"{m:3s} {c} fam_ok={s['family_ok']} tp/fp/fn={s['tp']}/{s['fp']}/{s['fn']} holds={s['holds']} held_req={s['held_required']}{extra} err={err}")
print("pilot cost USD", round(llm.spent() - before, 4))
