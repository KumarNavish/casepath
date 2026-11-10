"""Admission variants on RECORDED gpt-6-luna CPv2' responses (no model calls).

(a) no verifier: one interpretation call; every item the interpreter cites with a locatable quotation is admitted.
(b) V3: the evidence-bearing verifier (current CPv2').
(c) two readings agree: a true/false condition verdict is admitted only if the interpretation of run r and the
    independent interpretation of run (r+1) mod 3 give the same verdict, each with a quotation the normalised
    matcher locates; otherwise the judgment is unresolved (its citations kept, so a cited open fact stays a
    question). No verifier call. Category and document assessments are taken from run r, as in (a).
Usage: TMIS_MODEL=openai/gpt-6-luna TMIS_BUDGET_USD=0 python3 admission_variants.py
"""
import copy
import json
import sys

import common
import tenancy_v2 as tv
import theft_v2
from casepath_api.autonomous_policy_v1 import proposal_items, validate_interpretation

TAG = common.TAG
sys.argv = [sys.argv[0], TAG]
sys.path.insert(0, str(common.TMIS / "analysis"))
from analyze import summ, tenancy_row  # noqa: E402
from tenancy_score import unscored  # noqa: E402
from tenancy_data import reference, sources  # noqa: E402
from theft_score import pooled, score_pair  # noqa: E402
import theft_data  # noqa: E402

K = 3
TP = json.loads((common.OUT / f"plans_tenancy_{TAG}_original_dev.json").read_text())
HP = json.loads((common.OUT / f"plans_theft_{TAG}_original_dev.json").read_text())


def allok(proposal):
    return {"family_supported": True, "issues": [], "checks": [{"item_id": i, "accepted": True, "reason": ""} for i in proposal_items(proposal)]}


def two_readings(c, r):
    o, other = TP.get(f"CPv2p|{c}|{r}") or {}, TP.get(f"CPv2p|{c}|{(r + 1) % K}") or {}
    if "replay" not in o:
        return o.get("plan")  # handoff or failed output: unchanged
    prop = copy.deepcopy(o["replay"]["proposal"])
    second = {row["flag"]: row for row in ((other.get("replay") or {}).get("proposal") or {}).get("conditions", [])}
    for row in prop["conditions"]:
        if row["verdict"] in {"true", "false"}:
            s = second.get(row["flag"])
            if not (row["citations"] and s and s["verdict"] == row["verdict"] and s["citations"]):
                row["verdict"] = "unresolved"
    srcs = sources(c)
    try:
        return tv.plan_v2(None, c, validate_interpretation(tv.PACK, srcs, prop, allok(prop)), prop, srcs)
    except ValueError as error:
        return tv.handoff(str(error))


def tenancy():
    cases = sorted({k.split("|")[1] for k in TP if k.startswith("CPv2p|")})
    out = {}
    for name in ("a_no_verifier", "b_v3", "c_two_readings"):
        rows = []
        for c in cases:
            R = set(reference(c)["request_set"]) - unscored(c)
            for r in range(K):
                o = TP.get(f"CPv2p|{c}|{r}") or {}
                plan = (o.get("plan_no_verifier") or o.get("plan")) if name == "a_no_verifier" else o.get("plan") if name == "b_v3" else two_readings(c, r)
                rows.append(tenancy_row(c, plan, R))
        s = summ(rows)
        n = s["n"]
        out[name] = {"requested": s["tp"] / n, "held": s["held"] / n, "handed_over": s["handed"] / n, "missed": s["miss"] / n,
                     "unnecessary": s["fp"] / n, "strict_unsafe": s["unsafe_strict_per_claim"], "failed": s["failed_outputs"], "n": n}
    return out


def theft():
    tp = theft_v2.DEFAULT
    pairs = [p for p in theft_data.pairs() if p["story"] in (0, 1, 2)]
    empty = {"requests": [], "holds": []}

    def nu(t, r):
        return (HP.get(f"CPv2p|{t}|{r}") or {}).get("judgments_no_verifier")

    def plan(name, t, r):
        o = HP.get(f"CPv2p|{t}|{r}") or {}
        if name == "a_no_verifier":
            return o.get("plan_no_verifier") or empty
        if name == "b_v3":
            return o.get("plan") or empty
        a, b = nu(t, r), nu(t, (r + 1) % K)
        if a is None:
            return empty
        agreed = {g: (v if v in {"true", "false"} and b and b.get(g) == v else "unresolved") for g, v in a.items()}
        return tp.plan_exact(agreed)

    out = {}
    for name in ("a_no_verifier", "b_v3", "c_two_readings"):
        rows = [score_pair(p, plan(name, p["off"], r), plan(name, p["variant"], r)) for r in range(K) for p in pairs]
        on = pooled(rows)
        un = [x for x in rows if x["kind"] == "unresolved"]
        out[name] = {"wrong": on["wrong"], "missed": on["missed"], "f1": round(on["f1"], 3), "pair_runs": on["pairs"],
                     "wrong_plus_missed_per_pair": (on["wrong"] + on["missed"]) / on["pairs"],
                     "unchanged_when_open": sum(x["stable"] for x in un) / len(un), "premature_when_open": sum(x["premature"] for x in un) / len(un)}
    return out


def costs():
    rows = [json.loads(l) for l in common.llm.LEDGER.read_text().splitlines()]
    agg = {}
    for r in rows:
        m = (r["tag"].get("exp"), r["tag"].get("method"))
        if m[1] and m[1].startswith("CPv2p-"):
            a = agg.setdefault(m, [0, 0.0])
            a[0] += 1
            a[1] += float(r.get("cost") or 0)
    return {f"{e}|{m}": {"calls": n, "usd_per_call": c / n} for (e, m), (n, c) in agg.items()}


if __name__ == "__main__":
    res = {"tenancy": tenancy(), "theft": theft(), "cost_per_call": costs()}
    print(json.dumps(res, indent=1))
    common.dump(common.OUT / f"admission_variants_{TAG}.json", res)
