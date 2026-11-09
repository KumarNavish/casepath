"""Compute every reported result from the saved plans (no model calls).

Usage: python3 analyze.py [model_tag]   (default gpt-6.1-terra)
Writes results_<tag>.json next to this file.
"""
from __future__ import annotations

import itertools
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "harness"))
from tenancy_data import claim_ids, reference  # noqa: E402
from tenancy_score import unscored  # noqa: E402
from theft_data import pairs, texts  # noqa: E402
from theft_score import score_pair  # noqa: E402

TAG = sys.argv[1] if len(sys.argv) > 1 else "gpt-6.1-terra"
RUNS = HERE.parent / "runs"
K = 3
rng = random.Random(20261109)


# ----------------------------------------------------------------- helpers
def jaccard(a, b):
    a, b = set(a), set(b)
    return 1.0 if not a and not b else len(a & b) / len(a | b)


def majority(plans):
    """Self-consistency: document-wise majority over the runs."""
    ok = [p for p in plans if p]
    if not ok:
        return None
    need = len(ok) // 2 + 1
    count = lambda field: defaultdict(int, {d: sum(d in set(p.get(field, [])) for p in ok) for p in ok for d in p.get(field, [])})
    rq, hd = count("requests"), count("holds")
    req = sorted(d for d, c in rq.items() if c >= need)
    return {"requests": req, "holds": sorted(d for d, c in hd.items() if c >= need and d not in req),
            "family": ok[0].get("family"), "deferred": False}


def bootstrap(clusters, stat, B=10000):
    keys = sorted(clusters)
    vals = []
    for _ in range(B):
        sample = [clusters[rng.choice(keys)] for _ in keys]
        vals.append(stat(sample))
    vals.sort()
    return [vals[int(0.025 * B)], vals[int(0.975 * B) - 1]]


def signflip_p(diffs):
    """Exact two-sided sign-flip test on per-cluster mean differences."""
    obs = abs(sum(diffs))
    n, extreme = len(diffs), 0
    for signs in itertools.product((1, -1), repeat=n):
        if abs(sum(s * d for s, d in zip(signs, diffs))) >= obs - 1e-12:
            extreme += 1
    return extreme / 2 ** n


# ----------------------------------------------------------------- tenancy
def tenancy():
    P = json.loads((RUNS / f"plans_tenancy_{TAG}.json").read_text())
    cids = claim_ids("test")
    fam_of = {c: reference(c)["family_id"] or reference(c)["family"] for c in cids}
    getters = {
        "B1": lambda c, r: P.get(f"B1|{c}|{r}", {}).get("plan"),
        "B2": lambda c, r: P.get(f"B2|{c}|{r}", {}).get("plan"),
        "CP-kleene": lambda c, r: P.get(f"CP|{c}|{r}", {}).get("plan"),
        "CP-kleene-noverifier": lambda c, r: P.get(f"CP|{c}|{r}", {}).get("plan_no_verifier"),
        "CP-exact": lambda c, r: P.get(f"CP|{c}|{r}", {}).get("plan_exact"),
        "CP-exact-noverifier": lambda c, r: P.get(f"CP|{c}|{r}", {}).get("plan_exact_no_verifier"),
    }
    systems = {}
    for name, get in getters.items():
        systems[name] = {c: [get(c, r) for r in range(K)] for c in cids}
    systems["B1-SC3"] = {c: [majority(systems["B1"][c])] for c in cids}
    out = {}
    per_claim = {}
    for name, runs in systems.items():
        rows = []
        for c in cids:
            R = set(reference(c)["request_set"]) - unscored(c)
            for plan in runs[c]:
                if plan is None:
                    rows.append({"c": c, "avail": 0, "tp": 0, "fp": 0, "defer": 0, "miss": len(R), "nR": len(R),
                                 "nP": 0, "holds": 0, "fam": 0, "claim_deferred": 0})
                    continue
                Pq, H = set(plan.get("requests", [])) - unscored(c), set(plan.get("holds", [])) - unscored(c)
                if plan.get("deferred"):  # whole claim handed to a person: every required document is deferred
                    H = set(R)
                rows.append({"c": c, "avail": 1, "tp": len(Pq & R), "fp": len(Pq - R), "defer": len((H - Pq) & R),
                             "miss": len(R - Pq - H), "nR": len(R), "nP": len(Pq), "holds": len(H - Pq),
                             "fam": int(plan.get("family") == reference(c)["family"]),
                             "claim_deferred": int(bool(plan.get("deferred")))})
        per_claim[name] = rows

        def summ(rs):
            S = lambda k: sum(r[k] for r in rs)
            nR, nP = S("nR"), S("nP")
            return {"unnecessary_rate": S("fp") / nP if nP else 0.0, "recall": S("tp") / nR,
                    "deferral_rate": S("defer") / nR, "silent_miss_rate": S("miss") / nR,
                    "unsafe_per_claim": (S("fp") + S("miss")) / len(rs), "holds_per_claim": S("holds") / len(rs),
                    "requests_per_claim": nP / len(rs), "availability": S("avail") / len(rs),
                    "family_accuracy": S("fam") / len(rs), "claim_deferral": S("claim_deferred") / len(rs),
                    "fp": S("fp"), "miss": S("miss"), "defer": S("defer"), "tp": S("tp"), "nR": nR, "nP": nP}
        res = summ(rows)
        clusters = defaultdict(list)
        for r in rows:
            clusters[fam_of[r["c"]]].append(r)
        for metric in ("unnecessary_rate", "recall", "deferral_rate", "silent_miss_rate", "unsafe_per_claim"):
            res[metric + "_ci"] = bootstrap(clusters, lambda s, m=metric: summ([r for cl in s for r in cl])[m], B=4000)
        if name not in ("B1-SC3",):
            stab = []
            for c in cids:
                plans = [p for p in runs[c] if p]
                if len(plans) >= 2:
                    stab.append(sum(jaccard(a["requests"], b["requests"]) for a, b in itertools.combinations(plans, 2))
                                / len(list(itertools.combinations(plans, 2))))
            res["test_retest_jaccard"] = sum(stab) / len(stab) if stab else None
            res["claims_identical_across_runs"] = sum(s == 1.0 for s in stab) / len(stab) if stab else None
        out[name] = res
    # primary contrasts (cluster = family)
    def contrast(a, b, metric):
        ca, cb = defaultdict(list), defaultdict(list)
        for r in per_claim[a]:
            ca[fam_of[r["c"]]].append(r)
        for r in per_claim[b]:
            cb[fam_of[r["c"]]].append(r)
        val = lambda rs: {"unsafe": (sum(r["fp"] + r["miss"] for r in rs)) / len(rs),
                          "deferred": sum(r["defer"] for r in rs) / max(1, sum(r["nR"] for r in rs)),
                          "fp": sum(r["fp"] for r in rs) / len(rs)}[metric]
        diffs = [val(ca[f]) - val(cb[f]) for f in sorted(ca)]
        allA = [r for f in ca for r in ca[f]]; allB = [r for f in cb for r in cb[f]]
        return {"a": a, "b": b, "metric": metric, "a_value": val(allA), "b_value": val(allB),
                "diff": val(allA) - val(allB), "p_signflip": signflip_p(diffs), "clusters": len(diffs)}
    out["_contrasts"] = [contrast("CP-exact", "B1", "unsafe"), contrast("CP-kleene", "B1", "deferred"),
                         contrast("CP-exact", "CP-kleene", "deferred"), contrast("CP-exact", "B1", "fp")]
    return out, per_claim


# ----------------------------------------------------------------- theft
def theft():
    P = json.loads((RUNS / f"plans_theft_{TAG}.json").read_text())
    T = texts()
    getters = {"D": ("D", "plan"), "R": ("R", "plan"), "CP": ("CP", "plan"), "CP-noverifier": ("CP", "plan_no_verifier"),
               "CP-allroutes": ("CP", "plan_all_routes")}
    plans = {name: {t: [P.get(f"{m}|{t}|{r}", {}).get(field) for r in range(K)] for t in T}
             for name, (m, field) in getters.items()}
    for base in ("D", "R"):
        plans[base + "-SC3"] = {t: [majority(plans[base][t])] * K for t in T}
    out = {}
    held = [p for p in pairs() if p["split"] == "heldout"]
    for name, pl in plans.items():
        rows = []
        for p in held:
            for r in range(K):
                s = score_pair(p, pl[p["off"]][r], pl[p["variant"]][r])
                s["run"] = r
                rows.append(s)
        on = [s for s in rows if s["kind"] == "on" and s["available"]]
        un = [s for s in rows if s["kind"] == "unresolved" and s["available"]]

        def summ_on(rs):
            c, w, m = (sum(r[k] for r in rs) for k in ("correct", "wrong", "missed"))
            pr = c / (c + w) if c + w else 0.0
            rc = c / (c + m) if c + m else 0.0
            return {"correct": c, "wrong": w, "wrong_add": sum(r["wrong_add"] for r in rs),
                    "wrong_withdraw": sum(r["wrong_withdraw"] for r in rs), "missed": m, "precision": pr,
                    "recall": rc, "f1": 2 * pr * rc / (pr + rc) if pr + rc else 0.0,
                    "exact_rate": sum(r["exact"] for r in rs) / len(rs), "wrong_per_pair": w / len(rs),
                    "missed_per_pair": m / len(rs)}
        res = {"on": summ_on(on), "on_available": len(on) / (len(held and [p for p in held if p['kind']=='on']) * K)}
        cl = defaultdict(list)
        for r in on:
            cl[r["condition"]].append(r)
        for metric in ("f1", "wrong_per_pair", "missed_per_pair"):
            res["on"][metric + "_ci"] = bootstrap(cl, lambda s, m=metric: summ_on([r for c in s for r in c])[m], B=4000)
        agreed = [r for r in on if r["condition"] not in ("PR_declined", "PR_expert_procedure_requested")]
        res["on_agreed_references"] = summ_on(agreed)
        res["unresolved"] = {"pairs": len(un), "premature_rate": sum(r["premature"] for r in un) / len(un) if un else None,
                             "stable_rate": sum(r["stable"] for r in un) / len(un) if un else None,
                             "held_rate": sum(r["held"] for r in un) / len(un) if un else None,
                             "changes_per_pair": sum(r["changes"] for r in un) / len(un) if un else None}
        if not name.endswith("SC3"):
            stab = []
            for t in T:
                if T[t]["story"] == 0:
                    continue
                ps = [x for x in pl[t] if x]
                if len(ps) >= 2:
                    stab.append(sum(jaccard(a["requests"], b["requests"]) for a, b in itertools.combinations(ps, 2)) / 3)
            res["test_retest_jaccard"] = sum(stab) / len(stab)
            res["texts_identical_across_runs"] = sum(s == 1.0 for s in stab) / len(stab)
        res["_rows"] = rows
        out[name] = res
    # contrasts by condition cluster
    def contrast(a, b, kind, metric):
        da, db = defaultdict(list), defaultdict(list)
        for r in out[a]["_rows"]:
            if r["kind"] == kind and r["available"]:
                da[r["condition"]].append(r)
        for r in out[b]["_rows"]:
            if r["kind"] == kind and r["available"]:
                db[r["condition"]].append(r)
        f = {"wrong": lambda rs: sum(x["wrong"] for x in rs) / len(rs),
             "premature_or_change": lambda rs: sum((x["premature"] or not x["stable"]) for x in rs) / len(rs)}[metric]
        conds = sorted(set(da) & set(db))
        diffs = [f(da[c]) - f(db[c]) for c in conds]
        return {"a": a, "b": b, "kind": kind, "metric": metric, "diff_mean_over_conditions": sum(diffs) / len(diffs),
                "p_signflip": signflip_p(diffs), "clusters": len(conds)}
    out["_contrasts"] = [contrast("CP", "D", "on", "wrong"), contrast("CP", "R", "on", "wrong"),
                         contrast("CP", "D", "unresolved", "premature_or_change"),
                         contrast("CP", "R", "unresolved", "premature_or_change")]
    return out


def costs():
    rows = [json.loads(l) for l in (RUNS / "ledger.jsonl").read_text().splitlines()]
    agg = defaultdict(lambda: {"calls": 0, "cost": 0.0, "prompt": 0, "cached": 0, "completion": 0, "latency": 0.0})
    for r in rows:
        if TAG not in str(r.get("model") or ""):
            continue
        k = (r["tag"].get("exp"), r["tag"].get("method"))
        a = agg[k]
        a["calls"] += 1; a["cost"] += float(r.get("cost") or 0); a["prompt"] += r.get("prompt_tokens") or 0
        a["cached"] += r.get("cached_tokens") or 0; a["completion"] += r.get("completion_tokens") or 0
        a["latency"] += r.get("latency_s") or 0
    return {f"{e}|{m}": v for (e, m), v in agg.items()}


if __name__ == "__main__":
    res = {}
    try:
        res["tenancy"], _ = tenancy()
    except FileNotFoundError as e:
        print("tenancy missing", e)
    try:
        th = theft()
        for v in th.values():
            if isinstance(v, dict):
                v.pop("_rows", None)
        res["theft"] = th
    except FileNotFoundError as e:
        print("theft missing", e)
    res["costs"] = costs()
    (HERE / f"results_{TAG}.json").write_text(json.dumps(res, indent=1))
    print("written", HERE / f"results_{TAG}.json")
