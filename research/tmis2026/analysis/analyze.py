"""Compute every reported result from the saved plans (no model calls).

Usage: python3 analyze.py [model_tag]   (default gpt-6.1-terra)
Writes results_<tag>.json next to this file.

Scoring conventions (see DEVIATIONS.md for those decided after the analysis plan):
- Tenancy: every required document is requested, held behind a question, handed to a
  person with the whole claim (handoff: the family was not admitted), or silently missed.
  Headline unsafe errors = unnecessary requests + silent misses; the strict sensitivity
  also counts handed-over documents as missed.
- A failed output (no valid JSON) is scored as an empty plan (tenancy: every required
  document missed; theft: an empty checklist). Test-retest agreement uses the valid
  outputs only, averaged over the pairs of valid runs.
"""
from __future__ import annotations

import itertools
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "harness"))
from tenancy_data import claim_ids, reference  # noqa: E402
from tenancy_score import unscored  # noqa: E402
from theft_data import best_realization, pairs, texts  # noqa: E402
from theft_score import delta, score_pair  # noqa: E402

TAG = sys.argv[1] if len(sys.argv) > 1 else "gpt-6.1-terra"
RUNS = HERE.parent / "runs"
K = 3
B = 10000
SEED = 20261109
rng = random.Random(SEED)  # marginal per-design intervals, drawn in a fixed order
EMPTY = {"requests": [], "holds": []}


# ----------------------------------------------------------------- helpers
def jaccard(a, b):
    a, b = set(a), set(b)
    return 1.0 if not a and not b else len(a & b) / len(a | b)


def retest(plans):
    """Mean pairwise Jaccard of the request sets of the valid runs (None if fewer than two)."""
    ok = [p for p in plans if p]
    prs = list(itertools.combinations(ok, 2))
    return sum(jaccard(a["requests"], b["requests"]) for a, b in prs) / len(prs) if prs else None


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


def quantile(vals, q):
    """Linear-interpolation quantile of sorted values (symmetric in q and 1 - q)."""
    h = (len(vals) - 1) * q
    lo = math.floor(h)
    hi = min(lo + 1, len(vals) - 1)
    return vals[lo] + (h - lo) * (vals[hi] - vals[lo])


def bootstrap(clusters, stat, B=B, generator=None):
    g = generator or rng
    keys = sorted(clusters)
    vals = []
    for _ in range(B):
        sample = [clusters[g.choice(keys)] for _ in keys]
        vals.append(stat(sample))
    vals.sort()
    return [quantile(vals, 0.025), quantile(vals, 0.975)]


def paired_bootstrap(ca, cb, stat, name):
    """95% interval of stat(a) - stat(b), resampling the shared clusters jointly."""
    g = random.Random(f"{SEED}|{TAG}|{name}")
    keys = sorted(set(ca) & set(cb))
    vals = []
    for _ in range(B):
        s = [g.choice(keys) for _ in keys]
        vals.append(stat([ca[k] for k in s]) - stat([cb[k] for k in s]))
    vals.sort()
    return [quantile(vals, 0.025), quantile(vals, 0.975)]


def signflip_p(diffs):
    """Exact two-sided sign-flip test on per-cluster mean differences."""
    obs = abs(sum(diffs))
    n, extreme = len(diffs), 0
    for signs in itertools.product((1, -1), repeat=n):
        if abs(sum(s * d for s, d in zip(signs, diffs))) >= obs - 1e-12:
            extreme += 1
    return extreme / 2 ** n


def test_meta(diffs, diff, lower_is_better=True):
    """Cluster counts, attainable p-values and the direction of a paired contrast."""
    nz = sum(abs(d) > 1e-12 for d in diffs)
    direction = "a<b" if diff < -1e-12 else "a>b" if diff > 1e-12 else "a=b"
    favours = "none" if direction == "a=b" else ("a" if (direction == "a<b") == lower_is_better else "b")
    return {"clusters": len(diffs), "nonzero_clusters": nz, "min_p_design": 2.0 / 2 ** len(diffs) if diffs else 1.0,
            "min_p_given_nonzero": min(1.0, 2.0 / 2 ** nz), "direction": direction, "favours": favours,
            "lower_is_better": lower_is_better}


# ----------------------------------------------------------------- tenancy
def tenancy_row(c, plan, R):
    if plan is None:  # failed output: an empty plan, every required document missed
        return {"c": c, "avail": 0, "tp": 0, "fp": 0, "defer": 0, "held": 0, "handed": 0, "miss": len(R),
                "nR": len(R), "nP": 0, "holds": 0, "holds_nonreq": 0, "fam": 0, "claim_deferred": 0}
    Pq, H = set(plan.get("requests", [])) - unscored(c), set(plan.get("holds", [])) - unscored(c)
    if plan.get("deferred"):  # whole claim handed to a person: its required documents are handed over
        handed = len(R - Pq)
        return {"c": c, "avail": 1, "tp": len(Pq & R), "fp": len(Pq - R), "defer": handed, "held": 0, "handed": handed,
                "miss": 0, "nR": len(R), "nP": len(Pq), "holds": handed, "holds_nonreq": 0,
                "fam": int(plan.get("family") == reference(c)["family"]), "claim_deferred": 1}
    held = len((H - Pq) & R)
    return {"c": c, "avail": 1, "tp": len(Pq & R), "fp": len(Pq - R), "defer": held, "held": held, "handed": 0,
            "miss": len(R - Pq - H), "nR": len(R), "nP": len(Pq), "holds": len(H - Pq), "holds_nonreq": len(H - Pq - R),
            "fam": int(plan.get("family") == reference(c)["family"]), "claim_deferred": 0}


def summ(rs):
    S = lambda k: sum(r[k] for r in rs)
    nR, nP, n = S("nR"), S("nP"), len(rs)
    return {"unnecessary_rate": S("fp") / nP if nP else 0.0, "recall": S("tp") / nR,
            "deferral_rate": S("defer") / nR, "held_rate": S("held") / nR, "handed_rate": S("handed") / nR,
            "silent_miss_rate": S("miss") / nR,
            "unsafe_per_claim": (S("fp") + S("miss")) / n,
            "unsafe_strict_per_claim": (S("fp") + S("miss") + S("handed")) / n,
            "held_per_claim": S("held") / n, "handed_per_claim": S("handed") / n, "deferred_per_claim": S("defer") / n,
            "holds_per_claim": S("holds") / n, "holds_nonrequired_per_claim": S("holds_nonreq") / n,
            "requests_per_claim": nP / n, "availability": S("avail") / n,
            "family_accuracy": S("fam") / n, "claim_deferral": S("claim_deferred") / n,
            "fp": S("fp"), "miss": S("miss"), "defer": S("defer"), "held": S("held"), "handed": S("handed"),
            "holds_nonrequired": S("holds_nonreq"), "handoff_runs": S("claim_deferred"), "failed_outputs": n - S("avail"),
            "tp": S("tp"), "nR": nR, "nP": nP, "n": n}


TEN_METRICS = {  # pooled value over a set of rows; all lower is better
    "unsafe": lambda rs: sum(r["fp"] + r["miss"] for r in rs) / len(rs),
    "unsafe_strict": lambda rs: sum(r["fp"] + r["miss"] + r["handed"] for r in rs) / len(rs),
    "deferred": lambda rs: sum(r["defer"] for r in rs) / max(1, sum(r["nR"] for r in rs)),
    "held": lambda rs: sum(r["held"] for r in rs) / max(1, sum(r["nR"] for r in rs)),
    "fp": lambda rs: sum(r["fp"] for r in rs) / len(rs),
}


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
    out, per_claim, retest_by_claim = {}, {}, {}
    for name, runs in systems.items():
        if all(p is None for plans in runs.values() for p in plans):
            continue  # design not run with this model
        rows = []
        for c in cids:
            R = set(reference(c)["request_set"]) - unscored(c)
            for plan in runs[c]:
                rows.append(tenancy_row(c, plan, R))
        per_claim[name] = rows
        res = summ(rows)
        clusters = defaultdict(list)
        for r in rows:
            clusters[fam_of[r["c"]]].append(r)
        for metric in ("unnecessary_rate", "recall", "deferral_rate", "silent_miss_rate", "unsafe_per_claim"):
            res[metric + "_ci"] = bootstrap(clusters, lambda s, m=metric: summ([r for cl in s for r in cl])[m])
        for metric in ("held_rate", "handed_rate", "unsafe_strict_per_claim"):
            res[metric + "_ci"] = bootstrap(clusters, lambda s, m=metric: summ([r for cl in s for r in cl])[m],
                                            generator=random.Random(f"{SEED}|{TAG}|{name}|{metric}"))
        if name not in ("B1-SC3",):
            stab = {c: retest(runs[c]) for c in cids}
            stab = {c: s for c, s in stab.items() if s is not None}
            retest_by_claim[name] = stab
            res["test_retest_jaccard"] = sum(stab.values()) / len(stab) if stab else None
            res["claims_identical_across_runs"] = sum(s == 1.0 for s in stab.values()) / len(stab) if stab else None
        out[name] = res

    def contrast(a, b, metric):
        ca, cb = defaultdict(list), defaultdict(list)
        for r in per_claim[a]:
            ca[fam_of[r["c"]]].append(r)
        for r in per_claim[b]:
            cb[fam_of[r["c"]]].append(r)
        val = TEN_METRICS[metric]
        diffs = [val(ca[f]) - val(cb[f]) for f in sorted(ca)]
        allA = [r for f in ca for r in ca[f]]; allB = [r for f in cb for r in cb[f]]
        diff = val(allA) - val(allB)
        pooled = lambda s: val([r for cl in s for r in cl])
        return {"a": a, "b": b, "metric": metric, "a_value": val(allA), "b_value": val(allB), "diff": diff,
                "p_signflip": signflip_p(diffs), "diff_ci": paired_bootstrap(ca, cb, pooled, f"ten|{a}|{b}|{metric}"),
                **test_meta(diffs, diff)}

    def retest_contrast(a, b):
        ca, cb = defaultdict(list), defaultdict(list)
        for c, s in retest_by_claim[a].items():
            ca[fam_of[c]].append(s)
        for c, s in retest_by_claim[b].items():
            cb[fam_of[c]].append(s)
        mean = lambda xs: sum(xs) / len(xs)
        keys = sorted(set(ca) & set(cb))
        diffs = [mean(ca[k]) - mean(cb[k]) for k in keys]
        diff = sum(diffs) / len(diffs)  # mean over families of the family-mean differences
        stat = lambda s: mean([mean(x) for x in s])
        return {"a": a, "b": b, "metric": "retest", "a_value": stat([ca[k] for k in keys]),
                "b_value": stat([cb[k] for k in keys]), "diff": diff, "p_signflip": signflip_p(diffs),
                "diff_ci": paired_bootstrap(ca, cb, stat, f"ten|{a}|{b}|retest"), **test_meta(diffs, diff, lower_is_better=False)}

    # legacy positional list (macros tenXC{A..D}); the named dict carries every contrast
    out["_contrasts"] = [contrast(a, b, mt) for a, b, mt in
                         (("CP-exact", "B1", "unsafe"), ("CP-kleene", "B1", "deferred"),
                          ("CP-exact", "CP-kleene", "deferred"), ("CP-exact", "B1", "fp")) if a in per_claim and b in per_claim]
    named = {"H1": ("CP-exact", "B1", "unsafe"), "H1_strict": ("CP-exact", "B1", "unsafe_strict"),
             "H2": ("CP-kleene", "B1", "deferred"), "H2_held": ("CP-kleene", "B1", "held"),
             "H2b_deferred": ("CP-exact", "CP-kleene", "deferred"), "H2b_unsafe": ("CP-exact", "CP-kleene", "unsafe"),
             "fp": ("CP-exact", "B1", "fp"),
             "H1_vs_SC3": ("CP-exact", "B1-SC3", "unsafe"), "H1_strict_vs_SC3": ("CP-exact", "B1-SC3", "unsafe_strict")}
    out["_named"] = {k: contrast(*v) for k, v in named.items() if v[0] in per_claim and v[1] in per_claim}
    if "CP-exact" in retest_by_claim and "B1" in retest_by_claim:
        out["_named"]["H5"] = retest_contrast("CP-exact", "B1")
    return out, per_claim


# ----------------------------------------------------------------- theft
def wrong_atoms(pair, off_plan, var_plan):
    pred = delta(set(off_plan["requests"]), set(var_plan["requests"]))
    selected, _ = best_realization(pred, pair["reference"])
    return sorted(set(pred) - set(selected))


def summ_on(rs):
    c, w, m = (sum(r[k] for r in rs) for k in ("correct", "wrong", "missed"))
    pr = c / (c + w) if c + w else 0.0
    rc = c / (c + m) if c + m else 0.0
    return {"correct": c, "wrong": w, "wrong_add": sum(r["wrong_add"] for r in rs),
            "wrong_withdraw": sum(r["wrong_withdraw"] for r in rs), "missed": m, "precision": pr,
            "recall": rc, "f1": 2 * pr * rc / (pr + rc) if pr + rc else 0.0,
            "exact_rate": sum(r["exact"] for r in rs) / len(rs), "wrong_per_pair": w / len(rs),
            "missed_per_pair": m / len(rs), "pair_runs": len(rs)}


def theft():
    P = json.loads((RUNS / f"plans_theft_{TAG}.json").read_text())
    T = texts()
    getters = {"D": ("D", "plan"), "R": ("R", "plan"), "CP": ("CP", "plan"), "CP-noverifier": ("CP", "plan_no_verifier"),
               "CP-allroutes": ("CP", "plan_all_routes")}
    raw, plans, failed = {}, {}, {}
    for name, (m, field) in getters.items():
        if not any(k.startswith(m + "|") for k in P):
            continue  # design not run with this model
        raw[name] = {t: [(P.get(f"{m}|{t}|{r}") or {}).get(field) for r in range(K)] for t in T}
        failed[name] = sum(1 for t in T for r in range(K)  # a recorded call without a valid plan
                           if f"{m}|{t}|{r}" in P and (P[f"{m}|{t}|{r}"] or {}).get(field) is None)
        plans[name] = {t: [p if p is not None else EMPTY for p in v] for t, v in raw[name].items()}  # failed = empty plan
    for base in ("D", "R"):
        if base in plans:
            plans[base + "-SC3"] = {t: [majority(plans[base][t])] * K for t in T}
            raw[base + "-SC3"] = None
            failed[base + "-SC3"] = 0
    out = {}
    held = [p for p in pairs() if p["split"] == "heldout"]
    n_on = sum(p["kind"] == "on" for p in held)
    for name, pl in plans.items():
        rows = []
        for p in held:
            for r in range(K):
                s = score_pair(p, pl[p["off"]][r], pl[p["variant"]][r])
                s["run"] = r
                if p["kind"] == "on":
                    s["wrong_atoms"] = wrong_atoms(p, pl[p["off"]][r], pl[p["variant"]][r])
                rows.append(s)
        # (a) an error shared by several pairs of the same story and run comes from their shared off plan:
        # count each distinct wrong change once per story x run, spreading its weight over those pairs
        share = defaultdict(int)
        for s in rows:
            if s["kind"] == "on":
                for a in s["wrong_atoms"]:
                    share[(s["story"], s["run"], a)] += 1
        for s in rows:
            if s["kind"] == "on":
                s["wrong_dedup"] = sum(1 / share[(s["story"], s["run"], a)] for a in s["wrong_atoms"])
        on = [s for s in rows if s["kind"] == "on" and s["available"]]
        un = [s for s in rows if s["kind"] == "unresolved" and s["available"]]
        res = {"on": summ_on(on), "on_available": len(on) / (n_on * K), "failed_outputs": failed[name]}
        cl = defaultdict(list)
        for r in on:
            cl[r["condition"]].append(r)
        for metric in ("f1", "wrong_per_pair", "missed_per_pair"):
            res["on"][metric + "_ci"] = bootstrap(cl, lambda s, m=metric: summ_on([r for c in s for r in c])[m])
        agreed = [r for r in on if r["condition"] not in ("PR_declined", "PR_expert_procedure_requested")]
        res["on_agreed_references"] = summ_on(agreed)
        res["unresolved"] = {"pairs": len(un), "premature_rate": sum(r["premature"] for r in un) / len(un) if un else None,
                             "stable_rate": sum(r["stable"] for r in un) / len(un) if un else None,
                             "held_rate": sum(r["held"] for r in un) / len(un) if un else None,
                             "changes_per_pair": sum(r["changes"] for r in un) / len(un) if un else None}
        dd = sum(r["wrong_dedup"] for r in on)
        res["sensitivity_offplan_dedup"] = {"wrong": dd, "wrong_per_pair": dd / len(on),
                                           "shared_atoms": sum(1 for v in share.values() if v > 1),
                                           "wrong_in_shared_atoms": sum(v for v in share.values() if v > 1)}
        # (b) all nine pairings of off-run and variant-run instead of run r with run r
        if raw[name] is not None:
            on9, un9 = [], []
            for p in held:
                for r1 in range(K):
                    for r2 in range(K):
                        s = score_pair(p, pl[p["off"]][r1], pl[p["variant"]][r2])
                        (on9 if p["kind"] == "on" else un9).append(s)
            s9 = summ_on(on9)
            res["sensitivity_all_pairings"] = {"wrong_per_pair": s9["wrong_per_pair"], "missed_per_pair": s9["missed_per_pair"],
                                               "f1": s9["f1"], "stable_rate": sum(r["stable"] for r in un9) / len(un9),
                                               "premature_rate": sum(r["premature"] for r in un9) / len(un9)}
            stab = {}
            for t in T:
                if T[t]["story"] == 0:
                    continue
                s = retest(raw[name][t])
                if s is not None:
                    stab[t] = s
            res["test_retest_jaccard"] = sum(stab.values()) / len(stab)
            res["texts_identical_across_runs"] = sum(s == 1.0 for s in stab.values()) / len(stab)
            res["_retest"] = stab
        res["_rows"] = rows
        out[name] = res

    def contrast(a, b, kind, metric):
        da, db = defaultdict(list), defaultdict(list)
        for r in out[a]["_rows"]:
            if r["kind"] == kind and r["available"]:
                da[r["condition"]].append(r)
        for r in out[b]["_rows"]:
            if r["kind"] == kind and r["available"]:
                db[r["condition"]].append(r)
        f = {"wrong": lambda rs: sum(x["wrong"] for x in rs) / len(rs),
             "wrong_dedup": lambda rs: sum(x["wrong_dedup"] for x in rs) / len(rs),
             "premature_or_change": lambda rs: sum((x["premature"] or not x["stable"]) for x in rs) / len(rs)}[metric]
        conds = sorted(set(da) & set(db))
        diffs = [f(da[c]) - f(db[c]) for c in conds]
        diff = sum(diffs) / len(diffs)
        stat = lambda s: sum(f(x) for x in s) / len(s)  # mean over conditions of the per-condition rate
        return {"a": a, "b": b, "kind": kind, "metric": metric, "diff_mean_over_conditions": diff,
                "a_value": stat([da[c] for c in conds]), "b_value": stat([db[c] for c in conds]),
                "p_signflip": signflip_p(diffs), "diff_ci": paired_bootstrap(da, db, stat, f"theft|{a}|{b}|{kind}|{metric}"),
                **test_meta(diffs, diff)}

    def retest_contrast(a, b):
        cond = lambda t: T[t]["condition"] or "off"  # the three off texts form their own cluster
        ca, cb = defaultdict(list), defaultdict(list)
        for t, s in out[a]["_retest"].items():
            ca[cond(t)].append(s)
        for t, s in out[b]["_retest"].items():
            cb[cond(t)].append(s)
        mean = lambda xs: sum(xs) / len(xs)
        keys = sorted(set(ca) & set(cb))
        diffs = [mean(ca[k]) - mean(cb[k]) for k in keys]
        diff = sum(diffs) / len(diffs)
        stat = lambda s: mean([mean(x) for x in s])
        return {"a": a, "b": b, "metric": "retest", "a_value": stat([ca[k] for k in keys]), "b_value": stat([cb[k] for k in keys]),
                "diff": diff, "p_signflip": signflip_p(diffs), "diff_ci": paired_bootstrap(ca, cb, stat, f"theft|{a}|{b}|retest"),
                **test_meta(diffs, diff, lower_is_better=False)}

    # legacy positional list (macros thXC{A..D})
    out["_contrasts"] = [contrast(a, b, k, mt) for a, b, k, mt in
                         (("CP", "D", "on", "wrong"), ("CP", "R", "on", "wrong"),
                          ("CP", "D", "unresolved", "premature_or_change"), ("CP", "R", "unresolved", "premature_or_change"))
                         if a in out and b in out]
    named = {}
    for comp in ("R", "D", "R-SC3", "D-SC3"):
        if comp not in out:
            continue
        named[f"H3_vs_{comp}"] = contrast("CP", comp, "on", "wrong")
        named[f"H3dedup_vs_{comp}"] = contrast("CP", comp, "on", "wrong_dedup")
        named[f"H4_vs_{comp}"] = contrast("CP", comp, "unresolved", "premature_or_change")
        if not comp.endswith("SC3"):
            named[f"H5_vs_{comp}"] = retest_contrast("CP", comp)
    out["_named"] = named
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
                v.pop("_retest", None)
        res["theft"] = th
    except FileNotFoundError as e:
        print("theft missing", e)
    res["costs"] = costs()
    (HERE / f"results_{TAG}.json").write_text(json.dumps(res, indent=1))
    print("written", HERE / f"results_{TAG}.json")
