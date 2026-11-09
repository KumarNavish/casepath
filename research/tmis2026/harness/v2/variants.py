"""Development diagnostics on RECORDED responses only (TMIS_BUDGET_USD=0; any uncached call fails).

Tenancy: the defining-event presumption as specified (uncited unresolved only) versus a variant
  'V2b': the defining event is presumed unless the claim states it did not occur (a cited 'false');
  branch facts keep the specified rule. Both on the same recorded CPv2 calls.
Theft: the same recorded judgments executed on (a) the V1 pack (quarantine as specified) and
  (b) the V1 pack without quarantine (repaired rules admitted, failed rules executed unchanged).
  For (b) the guards CasePath v2 did not judge (those of quarantined rules) take the recorded CPv1
  judgment of the same text and run.
Usage: TMIS_MODEL=openai/<model> TMIS_BUDGET_USD=0 python3 variants.py <model_tag>
"""
import copy
import json
import sys

import common
import presume
import tenancy_v2 as tv
import theft_v2
from tenancy_data import claim_ids, reference, sources
from casepath_api.autonomous_policy_v1 import validate_interpretation, proposal_items

TAG = sys.argv[1]
sys.argv = [sys.argv[0], TAG]
sys.path.insert(0, str(common.TMIS / "analysis"))
from analyze import summ, tenancy_row  # noqa: E402
from tenancy_score import unscored  # noqa: E402
from theft_score import score_pair, pooled  # noqa: E402
import theft_data  # noqa: E402

P = json.loads((common.OUT / f"plans_tenancy_{TAG}_original_dev.json").read_text())
runs = sorted({int(k.split("|")[2]) for k in P if k.startswith("CPv2|")})
cases = sorted({k.split("|")[1] for k in P if k.startswith("CPv2|")})


SPEC_APPLY = presume.apply


def apply_v2b(verified, raw, pack):
    out, records = SPEC_APPLY(verified, raw, pack)
    family = out["category"]["family"]
    flag = presume.DEFINING.get(family)
    if flag:
        for row in out["conditions"]:
            if row["flag"] == flag and row["verdict"] == "unresolved":
                row.update(verdict="true", presumption="v2b-defining-event")
                records.append({"flag": flag, "verdict": "true", "clause_id": "v2b"})
    return out, records


rows = {"spec": [], "v2b": []}
for c in cases:
    R = set(reference(c)["request_set"]) - unscored(c)
    for r in runs:
        try:
            o = tv.run_cpv2(tv.common.data("tenancy"), c, r)
        except Exception:  # an uncached (failed) call: score the recorded plan
            o = P.get(f"CPv2|{c}|{r}") or {}
        rows["spec"].append(tenancy_row(c, o.get("plan"), R))
        if "replay" not in o:
            rows["v2b"].append(tenancy_row(c, o.get("plan"), R))
            continue
        verified, raw = o["replay"]["verified"], o["replay"]["proposal"]
        saved = presume.apply
        presume.apply = apply_v2b
        try:
            plan = tv.plan_v2(None, c, verified, raw, sources(c))
        finally:
            presume.apply = saved
        rows["v2b"].append(tenancy_row(c, plan, R))
res = {"tenancy": {}}
for k, rs in rows.items():
    s = summ(rs)
    n = s["n"]
    res["tenancy"][k] = {"requested": s["tp"] / n, "held": s["held"] / n, "handed_over": s["handed"] / n,
                         "missed": s["miss"] / n, "unnecessary": s["fp"] / n, "strict_unsafe": s["unsafe_strict_per_claim"], "n": n}

T = json.loads((common.OUT / f"plans_theft_{TAG}_original_dev.json").read_text())
pack_open = copy.deepcopy(theft_v2.PACK)
pack_open["quarantined_rules"] = []
variants = {"v1_pack_quarantine": theft_v2.TheftPack(theft_v2.PACK), "v1_pack_no_quarantine": theft_v2.TheftPack(pack_open)}
pairs = [p for p in theft_data.pairs() if p["story"] == 0]
res["theft"] = {}
for name, tp in variants.items():
    out = []
    for r in sorted({int(k.split("|")[2]) for k in T if k.startswith("CPv2|")}):
        def nu(t):
            a = (T.get(f"CPv2|{t}|{r}") or {}).get("judgments") or {}
            b = (T.get(f"CPv1|{t}|{r}") or {}).get("judgments") or {}
            return {g: a.get(g, b.get(g, "unresolved")) for g in tp.guards}
        for p in pairs:
            out.append(score_pair(p, tp.plan_exact(nu(p["off"])), tp.plan_exact(nu(p["variant"]))))
    on = pooled(out)
    un = [x for x in out if x["kind"] == "unresolved"]
    res["theft"][name] = {"wrong": on["wrong"], "missed": on["missed"], "f1": round(on["f1"], 3), "pair_runs": on["pairs"],
                          "unchanged_when_open": sum(x["stable"] for x in un) / len(un)}
print(json.dumps(res, indent=1))
common.dump(common.OUT / f"variants_{TAG}_original_dev.json", res)
