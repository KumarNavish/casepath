"""Study 2 analysis, exactly as ANALYSIS_PLAN_STUDY2.md specifies (no model calls).

Usage: python3 study2.py            # writes analysis/study2_results.json if fresh plans exist; otherwise exits 0
Inputs (written by harness/v2; read only):
  runs/v2/plans_<exp>_<model>_fresh_<split>.json   keyed "<design>|<case>|<run>" -> {"plan": {...}, ...}
      tenancy designs CPv2p, B1v2p, CPv1; theft designs CPv2p, Rv2p, R, CPv1. For theft the runner calls story 4
      'dev' and stories 5-7 'heldout'; both files are read and merged (the primary analysis uses all four stories).
  runs/v2/ledger_<model>.jsonl                     cost rows (rows whose case is a fresh case)
  runs/v2/evolve_dryrun_theft_gpt-6-luna_fresh_train4_eval5,6,7*.json   evolution experiment (section 7),
      one file per run, each with {"evaluation": {arm: {"rows": [{"pair_id", "wrong", "missed"}]}}}
  runs/v2/ablation_<model>_fresh.json  (optional; written by harness/v2) offline ablation variants:
      {"tenancy": {"<variant>": {"<claim_id>|<run>": <plan>}}, "theft": {"<variant>": {"<text_id>|<run>": <plan>}}}
      with plans in the runner's plan format (requests / holds / deferred). Variant names as in section 6:
      no_presumption, kleene, original_pack, two_readings. CPv2p tenancy entries carrying 'plan_no_presumption'
      are used as the no_presumption variant when the file does not provide it.

Scoring conventions fixed here (see the docstrings of ten_row / theft rows):
- Tenancy reference states required_now and supplied_insufficient are both "required now" (both are requests).
- A document both requested and held counts as requested. A failed output (or a missing run of a design that ran)
  is an empty plan.
- A whole-claim handoff (deferred) hands over every required-now document; reference-held documents of a handed
  claim are counted as handed over (held), not as silent skips, and are not unsafe errors.
- Requested and held documents outside the reference's document set count as unnecessary requests / spurious holds.
- Shares (requested share, correct-hold share) are ratios of sums within a cluster and overall.
"""
from __future__ import annotations

import glob
import itertools
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMIS = HERE.parent
sys.path.insert(0, str(TMIS / "harness"))
sys.path.insert(0, str(TMIS / "fresh"))
RUNS = TMIS / "runs" / "v2"
K = 3
B = 10000
SEED = 20261110
EMPTY = {"requests": [], "holds": []}
MODELS = ("gpt-6-luna", "gpt-6.1-terra")
REQ_NOW = {"required_now", "supplied_insufficient"}


# ======================================================================= statistics
def quantile(vals, q):
    h = (len(vals) - 1) * q
    lo = math.floor(h)
    hi = min(lo + 1, len(vals) - 1)
    return vals[lo] + (h - lo) * (vals[hi] - vals[lo])


def signflip_p(diffs):
    """Exact two-sided sign-flip test on per-cluster differences."""
    obs = abs(sum(diffs))
    extreme = sum(abs(sum(s * d for s, d in zip(signs, diffs))) >= obs - 1e-12
                  for signs in itertools.product((1, -1), repeat=len(diffs)))
    return extreme / 2 ** len(diffs)


def paired_bootstrap(diffs_by_cluster: dict, name: str):
    """Resample clusters jointly; statistic = mean over resampled clusters of (a - b)."""
    g = random.Random(f"{SEED}|{name}")
    keys = sorted(diffs_by_cluster)
    vals = []
    for _ in range(B):
        s = [diffs_by_cluster[g.choice(keys)] for _ in keys]
        vals.append(sum(s) / len(s))
    vals.sort()
    return vals


def contrast(a_by_cluster: dict, b_by_cluster: dict, name: str, higher_is_better=False, margin=None):
    """Paired contrast over shared clusters: values, difference (a - b), 95% interval, exact two-sided sign-flip p,
    cluster counts, smallest attainable p and, with a margin, the non-inferiority p of a against b:
    share of bootstrap resamples whose difference is at least as bad as the margin."""
    keys = sorted(set(a_by_cluster) & set(b_by_cluster))
    d = {k: a_by_cluster[k] - b_by_cluster[k] for k in keys}
    diffs = [d[k] for k in keys]
    boot = paired_bootstrap(d, name)
    diff = sum(diffs) / len(diffs)
    nz = sum(abs(x) > 1e-12 for x in diffs)
    out = {"a_value": sum(a_by_cluster[k] for k in keys) / len(keys), "b_value": sum(b_by_cluster[k] for k in keys) / len(keys),
           "diff": diff, "diff_ci": [quantile(boot, 0.025), quantile(boot, 0.975)], "clusters": len(keys),
           "nonzero_clusters": nz, "p_signflip": signflip_p(diffs), "min_p_signflip": 2.0 / 2 ** len(keys),
           "min_p_signflip_given_nonzero": min(1.0, 2.0 / 2 ** nz), "higher_is_better": higher_is_better,
           "favours": "none" if abs(diff) < 1e-12 else ("a" if (diff > 0) == higher_is_better else "b")}
    if margin is not None:
        bad = (lambda x: x <= -margin) if higher_is_better else (lambda x: x >= margin)
        out.update({"margin": margin, "p_noninferiority": sum(bad(x) for x in boot) / B, "min_p_noninferiority": 1.0 / B,
                    "p_noninferiority_resolution": "0 means no resample reached the margin (resolution 1/10000)"})
    return out


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = run
    return adj


# ======================================================================= tenancy measures (section 4)
TEN_COUNTS = ("req_now", "requested", "held_req", "handed", "missed", "ref_held", "correct_hold", "premature",
              "silent_skip", "handed_held", "unnecessary", "spurious_hold")


def ten_row(ref: dict, plan: dict | None) -> dict:
    """Score one claim-run against the fresh reference (section 4)."""
    plan = plan or EMPTY
    states = ref["document_states"]
    req_now = {d for d, s in states.items() if s in REQ_NOW}
    ref_held = {d for d, s in states.items() if s == "held"}
    P = set(plan.get("requests", []))
    H = set(plan.get("holds", [])) - P
    r = dict.fromkeys(TEN_COUNTS, 0)
    r["req_now"], r["ref_held"] = len(req_now), len(ref_held)
    if plan.get("deferred"):  # whole claim handed to a person
        r["requested"] = len(P & req_now)
        r["handed"] = len(req_now - P)
        r["premature"] = len(P & ref_held)
        r["handed_held"] = len(ref_held - P)
        r["unnecessary"] = len(P - req_now - ref_held)
    else:
        r["requested"] = len(P & req_now)
        r["held_req"] = len(H & req_now)
        r["missed"] = len(req_now - P - H)
        r["correct_hold"] = len(H & ref_held)
        r["premature"] = len(P & ref_held)
        r["silent_skip"] = len(ref_held - P - H)
        r["unnecessary"] = len(P - req_now - ref_held)
        r["spurious_hold"] = len(H - req_now - ref_held)
    r["deferred"] = int(bool(plan.get("deferred")))
    r["strict_unsafe"] = r["unnecessary"] + r["missed"] + r["handed"] + r["premature"] + r["silent_skip"]
    return r


def ten_summary(rows: list[dict]) -> dict:
    S = lambda k: sum(r[k] for r in rows)
    n = len(rows)
    return {"claim_runs": n, **{k: S(k) for k in TEN_COUNTS}, "handoffs": S("deferred"),
            "strict_unsafe_per_claim": S("strict_unsafe") / n, "unnecessary_per_claim": S("unnecessary") / n,
            "missed_per_claim": S("missed") / n, "handed_per_claim": S("handed") / n, "premature_per_claim": S("premature") / n,
            "silent_skip_per_claim": S("silent_skip") / n,
            "requested_share": S("requested") / S("req_now") if S("req_now") else None,
            "held_required_now_per_claim": S("held_req") / n, "spurious_holds_per_claim": S("spurious_hold") / n,
            "correct_hold_share": S("correct_hold") / S("ref_held") if S("ref_held") else None}


TEN_METRIC = {"strict_unsafe": lambda rs: sum(r["strict_unsafe"] for r in rs) / len(rs),
              "requested_share": lambda rs: sum(r["requested"] for r in rs) / max(1, sum(r["req_now"] for r in rs))}


# ======================================================================= theft measures
def theft_atoms(pair, off, var):
    from theft_data import best_realization
    from theft_score import delta
    pred = delta(set(off["requests"]), set(var["requests"]))
    sel, _ = best_realization(pred, pair["reference"])
    return sorted(set(pred) - set(sel)), sorted(set(sel) - set(pred))


def theft_row(pair, off, var):
    from theft_score import score_pair
    s = score_pair(pair, off or EMPTY, var or EMPTY)
    if pair["kind"] == "on":
        s["errors"] = s["wrong"] + s["missed"]
        w, m = theft_atoms(pair, off or EMPTY, var or EMPTY)
        s["atoms"] = [("w", a) for a in w] + [("m", a) for a in m]
    return s


def theft_summary(on_rows, un_rows):
    c, w, m = (sum(r[k] for r in on_rows) for k in ("correct", "wrong", "missed"))
    pr = c / (c + w) if c + w else 0.0
    rc = c / (c + m) if c + m else 0.0
    out = {"pair_runs": len(on_rows), "correct": c, "wrong": w, "missed": m, "errors_per_pair": (w + m) / len(on_rows) if on_rows else None,
           "wrong_per_pair": w / len(on_rows) if on_rows else None, "missed_per_pair": m / len(on_rows) if on_rows else None,
           "f1": 2 * pr * rc / (pr + rc) if pr + rc else 0.0}
    if un_rows:
        out["unresolved"] = {"pair_runs": len(un_rows), "premature_rate": sum(r["premature"] for r in un_rows) / len(un_rows),
                             "other_changes_per_pair": sum(r["other_changes"] for r in un_rows) / len(un_rows),
                             "stable_rate": sum(r["stable"] for r in un_rows) / len(un_rows)}
    return out


def dedup_errors(on_rows):
    """Sensitivity: an error atom shared by several pairs of one story and run (their common off plan) counts once."""
    share = defaultdict(int)
    for r in on_rows:
        for a in r["atoms"]:
            share[(r["story"], r["run"], a)] += 1
    for r in on_rows:
        r["errors_dedup"] = sum(1 / share[(r["story"], r["run"], a)] for a in r["atoms"])


# ======================================================================= data access
def jaccard(a, b):
    a, b = set(a), set(b)
    return 1.0 if not a and not b else len(a & b) / len(a | b)


def retest(plans):
    ok = [p for p in plans if p]
    prs = list(itertools.combinations(ok, 2))
    return sum(jaccard(a["requests"], b["requests"]) for a, b in prs) / len(prs) if prs else None


def load_plans(exp: str, model: str) -> dict:
    """{design: {case: [plan or None per run]}} merged over the fresh split files; None = failed output."""
    raw = {}
    for split in ("dev", "heldout"):
        p = RUNS / f"plans_{exp}_{model}_fresh_{split}.json"
        if p.exists():
            raw.update(json.loads(p.read_text()))
    out = defaultdict(lambda: defaultdict(lambda: [None] * K))
    for key, entry in raw.items():
        design, case, run = key.rsplit("|", 2)
        out[design][case][int(run)] = (entry or {}).get("plan")
    return {d: dict(v) for d, v in out.items()}


def tenancy_rows(D, plans_by_case: dict) -> list[dict]:
    rows = []
    for cid in D.claim_ids("test"):
        ref = D.reference(cid)
        for r, plan in enumerate(plans_by_case.get(cid, [None] * K)):
            row = ten_row(ref, plan)
            row.update(case=cid, run=r, cluster=ref["family_id"], open_fact=ref["open_fact"] is not None)
            rows.append(row)
    return rows


def theft_rows(T, pairs, plans_by_text: dict, pairing=None) -> list[dict]:
    rows = []
    for p in pairs:
        for r1, r2 in (pairing or [(r, r) for r in range(K)]):
            off = (plans_by_text.get(p["off"]) or [None] * K)[r1]
            var = (plans_by_text.get(p["variant"]) or [None] * K)[r2]
            s = theft_row(p, off, var)
            s.update(run=r1, story=p["story"], condition=p["condition"])
            rows.append(s)
    return rows


def by_cluster(rows, key, fn):
    g = defaultdict(list)
    for r in rows:
        g[r[key]].append(r)
    return {k: fn(v) for k, v in g.items()}


# ======================================================================= analysis
def analyse(plans: dict, D_ten, D_theft, ledgers: dict, evolve: list, ablation: dict) -> dict:
    """plans: {(exp, model): {design: {case: [plans]}}}. Returns the full results object."""
    res = {"tenancy": {}, "theft": {}, "contrasts": {}, "secondary": {}}
    ten_rows, th_on, th_un = {}, {}, {}
    pairs = D_theft.pairs()
    on_pairs = [p for p in pairs if p["kind"] == "on"]
    un_pairs = [p for p in pairs if p["kind"] == "unresolved"]
    T = D_theft.texts()
    for (exp, model), designs in plans.items():
        for design, by_case in designs.items():
            if exp == "tenancy":
                rows = tenancy_rows(D_ten, by_case)
                ten_rows[(design, model)] = rows
                summ = ten_summary(rows)
                summ["open_fact_claims"] = ten_summary([r for r in rows if r["open_fact"]])
                summ["failed_outputs"] = sum(p is None for c in D_ten.claim_ids("test") for p in by_case.get(c, [None] * K))
                rt = [x for x in (retest(by_case.get(c, [])) for c in D_ten.claim_ids("test")) if x is not None]
                summ["test_retest_jaccard"] = sum(rt) / len(rt) if rt else None
                res["tenancy"][f"{design}|{model}"] = summ
            else:
                on = theft_rows(T, on_pairs, by_case)
                un = theft_rows(T, un_pairs, by_case)
                dedup_errors(on)
                th_on[(design, model)], th_un[(design, model)] = on, un
                summ = theft_summary(on, un)
                summ["errors_dedup_per_pair"] = sum(r["errors_dedup"] for r in on) / len(on)
                allp = theft_rows(T, on_pairs, by_case, pairing=[(a, b) for a in range(K) for b in range(K)])
                summ["errors_per_pair_all_pairings"] = sum(r["errors"] for r in allp) / len(allp)
                summ["failed_outputs"] = sum(p is None for t in T for p in by_case.get(t, [None] * K))
                rt = [x for x in (retest(by_case.get(t, [])) for t in T) if x is not None]
                summ["test_retest_jaccard"] = sum(rt) / len(rt) if rt else None
                res["theft"][f"{design}|{model}"] = summ

    mean = lambda key: (lambda rs: sum(r[key] for r in rs) / len(rs))
    ten_c = lambda d, m, metric="strict_unsafe": by_cluster(ten_rows[(d, m)], "cluster", TEN_METRIC[metric])
    th_c = lambda d, m, key="errors": by_cluster(th_on[(d, m)], "condition", mean(key))
    have = lambda kind, d, m: (d, m) in (ten_rows if kind == "tenancy" else th_on)

    # ---- primary (section 5)
    L, Tr = "gpt-6-luna", "gpt-6.1-terra"
    spec = {"A": ("theft", ("CPv2p", L), ("Rv2p", L), None),
            "B": ("tenancy", ("CPv2p", L), ("B1v2p", L), None),
            "C": ("theft", ("CPv2p", L), ("R", Tr), 0.25),
            "D": ("tenancy", ("CPv2p", L), ("B1v2p", Tr), 0.10)}
    prim = {}
    for name, (kind, a, b, margin) in spec.items():
        if not (have(kind, *a) and have(kind, *b)):
            continue
        fa, fb = (th_c(*a), th_c(*b)) if kind == "theft" else (ten_c(*a), ten_c(*b))
        c = contrast(fa, fb, f"primary|{name}", margin=margin)
        c.update(kind=kind, a=list(a), b=list(b), metric="wrong+missed per pair" if kind == "theft" else "strict unsafe per claim",
                 p_primary=c["p_noninferiority"] if margin is not None else c["p_signflip"],
                 test="non-inferiority (paired cluster bootstrap)" if margin is not None else "two-sided exact sign-flip")
        prim[name] = c
    if len(prim) == 4:
        for n, q in zip(prim, holm([prim[n]["p_primary"] for n in prim])):
            prim[n]["p_holm"] = q
    res["contrasts"] = prim

    # ---- secondary (section 6)
    sec = {}
    def add(name, kind, a, b, metric="strict_unsafe", margin=None, higher=False, key="errors"):
        if not (have(kind, *a) and have(kind, *b)):
            return
        fa, fb = (th_c(*a, key), th_c(*b, key)) if kind == "theft" else (ten_c(*a, metric), ten_c(*b, metric))
        c = contrast(fa, fb, f"secondary|{name}", higher_is_better=higher, margin=margin)
        c.update(kind=kind, a=list(a), b=list(b), metric=key if kind == "theft" else metric)
        sec[name] = c
    add("A_terra", "theft", ("CPv2p", Tr), ("Rv2p", Tr))
    add("B_terra", "tenancy", ("CPv2p", Tr), ("B1v2p", Tr))
    add("theft_CPv2p_terra_vs_R_terra", "theft", ("CPv2p", Tr), ("R", Tr))
    add("A_original_pack_luna", "theft", ("CPv2p", L), ("R", L))
    for m in MODELS:
        add(f"requested_share_{m}", "tenancy", ("CPv2p", m), ("B1v2p", m), metric="requested_share", margin=0.05, higher=True)
    add("ablation_tenancy_CPv1_vs_CPv2p_luna", "tenancy", ("CPv1", L), ("CPv2p", L))
    add("ablation_theft_CPv1_vs_CPv2p_luna", "theft", ("CPv1", L), ("CPv2p", L))
    for name in ("A", "C"):  # sensitivities of the theft primary contrasts
        if name in prim:
            a, b = tuple(prim[name]["a"]), tuple(prim[name]["b"])
            add(f"{name}_dedup", "theft", a, b, key="errors_dedup")
    res["secondary"]["contrasts"] = sec

    # ablation variants computed offline by harness/v2 (and plan_no_presumption carried in CPv2p tenancy entries)
    abl = {}
    for kind, variants in (ablation or {}).items():
        for variant, plans_ in variants.items():
            by_case = defaultdict(lambda: [None] * K)
            for key, plan in plans_.items():
                case, run = key.rsplit("|", 1)
                by_case[case][int(run)] = plan
            if kind == "tenancy":
                rows = tenancy_rows(D_ten, by_case)
                abl[f"tenancy|{variant}"] = ten_summary(rows)
                if have("tenancy", "CPv2p", L):
                    abl[f"tenancy|{variant}"]["vs_CPv2p"] = contrast(
                        by_cluster(rows, "cluster", TEN_METRIC["strict_unsafe"]), ten_c("CPv2p", L), f"ablation|{variant}")
            else:
                on = theft_rows(T, on_pairs, by_case)
                abl[f"theft|{variant}"] = theft_summary(on, theft_rows(T, un_pairs, by_case))
                if have("theft", "CPv2p", L):
                    abl[f"theft|{variant}"]["vs_CPv2p"] = contrast(by_cluster(on, "condition", mean("errors")), th_c("CPv2p", L),
                                                                   f"ablation|theft|{variant}")
    res["secondary"]["ablation"] = abl

    # cost per case (fresh cases only) and the cross-model cost ratios of C and D
    cost = {}
    fresh_cases = set(D_ten.claim_ids("test")) | set(T)
    for model, rows in ledgers.items():
        agg = defaultdict(lambda: {"cost": 0.0, "calls": 0, "units": set()})
        for r in rows:
            tag = r.get("tag") or {}
            if tag.get("case") not in fresh_cases or tag.get("exp") not in ("v2-tenancy", "v2-theft", "theft"):
                continue
            design = str(tag.get("method", "")).split("-")[0]
            if tag["exp"] == "theft":  # Study 1 methods reused unchanged: R, and CP (= CPv1) interpret/verify
                design = {"CP": "CPv1"}.get(design, design)
            a = agg[(tag["exp"].replace("v2-", ""), design)]
            a["cost"] += float(r.get("cost") or 0); a["calls"] += 1; a["units"].add((tag["case"], r.get("run")))
        for (exp, design), a in agg.items():
            cost[f"{exp}|{design}|{model}"] = {"cost_usd": a["cost"], "calls": a["calls"], "case_runs": len(a["units"]),
                                               "cost_per_case_run": a["cost"] / len(a["units"])}
    ratio = lambda num, den: (cost[num]["cost_per_case_run"] / cost[den]["cost_per_case_run"]) if num in cost and den in cost else None
    res["secondary"]["cost"] = {"by_design": cost, "ratio_C": ratio(f"theft|CPv2p|{L}", f"theft|R|{Tr}"),
                                "ratio_D": ratio(f"tenancy|CPv2p|{L}", f"tenancy|B1v2p|{Tr}")}

    # ---- evolution experiment (section 7)
    if evolve:
        arms = defaultdict(list)
        for run, e in enumerate(evolve):
            for arm, v in e["evaluation"].items():
                for row in v["rows"]:
                    cond = row["pair_id"].split("-on-", 1)[1]
                    arms[arm].append({"condition": cond, "errors": row["wrong"] + row["missed"], "run": run})
        ev = {"runs": len(evolve), "arms": {a: {"pair_runs": len(r), "errors_per_pair": sum(x["errors"] for x in r) / len(r)}
                                            for a, r in arms.items()}}
        if "CP_after_V5" in arms and "R_after_memory" in arms:
            ev["after_contrast"] = contrast(by_cluster(arms["CP_after_V5"], "condition", mean("errors")),
                                            by_cluster(arms["R_after_memory"], "condition", mean("errors")), "evolution|after")
        ev["repairs"] = [e.get("train_log") for e in evolve]
        res["secondary"]["evolution"] = ev
    return res


def main():
    present = {(exp, m): load_plans(exp, m) for exp in ("tenancy", "theft") for m in MODELS
               if any((RUNS / f"plans_{exp}_{m}_fresh_{s}.json").exists() for s in ("dev", "heldout"))}
    if not present:
        print("no fresh plans yet: nothing written")
        return
    import tenancy_fresh, theft_fresh
    ledgers = {m: [json.loads(l) for l in (RUNS / f"ledger_{m}.jsonl").read_text().splitlines()]
               for m in MODELS if (RUNS / f"ledger_{m}.jsonl").exists()}
    evolve = [json.loads(Path(p).read_text()) for p in sorted(
        glob.glob(str(RUNS / "evolve_dryrun_theft_gpt-6-luna_fresh_train4_eval5,6,7*.json"))
        + glob.glob(str(RUNS / "evolve_theft_gpt-6-luna_fresh_train4_eval567*.json")))]  # name the runner actually used
    abl_path = RUNS / "ablation_gpt-6-luna_fresh.json"
    ablation = json.loads(abl_path.read_text()) if abl_path.exists() else {}
    # the ablation runner wrote one file per experiment in the plans format "<variant>|<case>|<run>": {"plan": ...}
    VARIANT = {"CPv2p-nopres": "no_presumption", "CPv2p-kleene": "kleene", "CPv2p-2read": "two_readings",
               "CPv2p-origpack": "original_pack", "CPv2p-origpack-full": "original_pack_full"}
    for exp, fname in (("tenancy", "ablations_tenancy_gpt-6-luna_fresh_heldout.json"),
                       ("theft", "ablations_theft_gpt-6-luna_fresh_heldout.json"),
                       ("theft", "ablations_theft_origpack_gpt-6-luna_fresh_heldout.json")):
        if (RUNS / fname).exists():
            abl_path = RUNS / fname
            for key, entry in json.loads((RUNS / fname).read_text()).items():
                if key.startswith("_"):
                    continue
                variant, case_run = key.split("|", 1)
                ablation.setdefault(exp, {}).setdefault(VARIANT.get(variant, variant), {})[case_run] = (entry or {}).get("plan")
    cp = present.get(("tenancy", "gpt-6-luna"), {}).get("CPv2p")
    if cp is not None and "no_presumption" not in ablation.get("tenancy", {}):
        raw = {}
        for split in ("dev", "heldout"):
            p = RUNS / f"plans_tenancy_gpt-6-luna_fresh_{split}.json"
            if p.exists():
                raw.update({k: v.get("plan_no_presumption") for k, v in json.loads(p.read_text()).items()
                            if k.startswith("CPv2p|") and v and "plan_no_presumption" in v})
        if raw:
            ablation.setdefault("tenancy", {})["no_presumption"] = {k.split("|", 1)[1]: v for k, v in raw.items()}
    res = analyse(present, tenancy_fresh, theft_fresh, ledgers, evolve, ablation)
    res["inputs"] = {"plans": [f"{e}|{m}" for e, m in present], "evolution_runs": len(evolve), "ablation_file": abl_path.exists()}
    (HERE / "study2_results.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    print("written", HERE / "study2_results.json")


if __name__ == "__main__":
    main()
