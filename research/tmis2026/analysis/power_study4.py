"""Planning calculation for a Study 4 replication from Study 3's stored outputs. POST HOC, not a result: no hypothesis
of Study 3 changes status, and nothing here is evidence about CasePath. No model calls, no network.

    python3 power_study4.py            # writes power_study4.json and power_study4.md

The replication analysed here uses many independent cases (each case its own story), analysed with per-case pairing:
for each case, the difference between two designs' error counts (a design's value on a case = the mean over its runs
on the case), tested by an exact (n <= 12) or Monte Carlo sign-flip test over cases, two-sided alpha 0.05.

Inputs are read only through analysis/study3.py (Study: loading, failed-output rule, scoring) as analysis/
study3_feedback.py and analysis/study3_review.py load them; claim types come from study3_feedback.claim_type and the
spec's subsets (study3.Study.in_subset); the lint variants' per-pair rows come from lint_followup.theft_variant (its
own scoring call, captured, not re-implemented). The statistics below (normal-approximation sample sizes, resampling
of the observed per-case differences, a vectorised sign-flip test) are planning arithmetic only.

P1  Per-case paired differences (CasePath minus comparator): n, mean, SD, share < 0 / = 0 / > 0, share of cases where
    both designs have no error; the cluster structure of the differences (tenancy: family; theft: changed fact x story).
P2  Independent cases needed for 80% and 90% power (two-sided alpha 0.05) to detect the observed difference and half of
    it: normal approximation, and a simulation (resample the observed differences, shifted for the half target; 2,000
    simulated studies; sign-flip test) reported in place of the normal value where the two disagree by more than 20%.
P3  Non-inferiority where every fact is stated (type S, 40 claims): margins 0.10, 0.15, 0.25, one-sided alpha 0.05,
    true difference = observed and = 0.
P4  Share sweep (tenancy): N cases per regime, four levels (0%, 10%, 25%, 50% of files with an open fact) of N/4 cases
    each; power of the pooled test, the 50% level alone and non-inferiority at the 0% level (margin 0.15).
"""
from __future__ import annotations

import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import study3_feedback as F  # noqa: E402
import study3_review as R  # noqa: E402

s3, s2 = F.s3, F.s2
OUT = HERE / "power_study4"
HEADER = "Planning calculation from Study 3's stored outputs; post hoc; not a result"
ALPHA = 0.05
POWERS = (0.80, 0.90)
SIMS = 2000          # simulated studies per power evaluation
FLIPS = 1000         # Monte Carlo sign patterns per simulated study (exact enumeration when n <= EXACT_N)
EXACT_N = 12
SIM_N_CAP = 1000     # simulation search only where the normal n is at most this
DISAGREE = 0.20
SEED = 20261112
TOL = 1e-9
NI_MARGINS = (0.10, 0.15, 0.25)
SWEEP_N = (80, 120, 160, 240)
SWEEP_SHARES = (0.0, 0.10, 0.25, 0.50)
SWEEP_MARGIN = 0.15
Z = statistics.NormalDist().inv_cdf

LABELS = {"casepath": "CasePath", "casepath_checklist": "CasePath, checklist only", "ric": "Rules in context",
          "ric_frontier": "Rules in context, frontier", "self_consistency": "Self-consistency",
          "model_executes_rules": "Model executes rules", "react": "ReAct",
          "ric_original_frontier": "Rules in context, original rules, frontier",
          "casepath_frontier_checklist": "CasePath, checklist only, frontier (one run)"}
TEN_CONTRASTS = [("casepath", "ric"), ("casepath", "self_consistency"), ("casepath", "model_executes_rules"),
                 ("casepath", "react"), ("casepath", "ric_frontier"), ("casepath_frontier_checklist", "ric_frontier")]
THEFT_CONTRASTS = [("casepath", "ric"), ("casepath", "self_consistency"), ("casepath", "model_executes_rules"),
                   ("casepath", "react"), ("casepath", "ric_frontier"), ("casepath", "ric_original_frontier"),
                   ("casepath_frontier_checklist", "ric_frontier"), ("casepath_frontier_checklist", "ric_original_frontier")]
SAME_MODEL = {"ric", "self_consistency", "model_executes_rules", "react"}
TEN_MEASURES = {"strict_unsafe": "strict unsafe errors per claim", "all_dev": "all deviations per claim (unsafe + wrong holds)"}
SUBSETS = ["all", "S", "O", "O: open branch fact only", "O: denied defining event", "O: open defining event"]
LINT_VARIANTS = {"a": "in-sample flags, all flagged conditions open", "b": "in-sample flags, case-type conditions true",
                 "c_a": "out-of-sample flags, all flagged conditions open", "c_b": "out-of-sample flags, case-type conditions true"}
SWEEP_COMPARATORS = ("ric", "model_executes_rules", "ric_frontier")


# ======================================================================= loading (as study3_feedback.main)
def load_study():
    s3.configure(F.SPEC)
    study = s3.Study(F.SPEC, F.DATA, F.LABEL, s3.load_data(F.DATA))
    for d in F.SPEC["designs"]:
        for reg in d["regimes"]:
            assert study.load(d["key"], reg), f"{d['key']}/{reg} not loaded"
    return study


def subset_of(study, cid):
    """The six-way reading of the 96 claims: S / O, and O split into open defining event, denied defining event and
    open branch fact only (spec subsets open_event, denied_event, open_branch_fact; checked to partition O)."""
    t = F.claim_type(study.D["tenancy"].reference(cid))
    if t == "S":
        return "S", None
    hits = [name for name, sub in (("O: open defining event", "open_event"), ("O: denied defining event", "denied_event"),
                                   ("O: open branch fact only", "open_branch_fact")) if study.in_subset(cid, sub)]
    assert len(hits) == 1, (cid, hits)
    return "O", hits[0]


def per_case(rows, key, field):
    g = defaultdict(list)
    for r in rows:
        g[r[key]].append(r[field])
    return {k: sum(v) / len(v) for k, v in g.items()}, g


def within_var(groups):
    """Mean over cases of the sample variance over a design's runs (0 for one run)."""
    v = [statistics.variance(x) for x in groups.values() if len(x) > 1]
    return sum(v) / len(v) if v else None


# ======================================================================= summaries and cluster structure
def describe(d, both_zero=None):
    d = np.asarray(d, float)
    n = len(d)
    out = {"n": n, "mean": float(d.mean()), "sd": float(d.std(ddof=1)) if n > 1 else None,
           "share_lt0": float((d < -TOL).mean()), "share_eq0": float((np.abs(d) <= TOL).mean()), "share_gt0": float((d > TOL).mean())}
    if both_zero is not None:
        out["share_both_zero"] = float(np.mean(both_zero))
    return out


def oneway(vals, groups):
    """Between-cluster SD (of cluster means), pooled within-cluster SD, ANOVA ICC (unbalanced k0), clusters."""
    g = defaultdict(list)
    for v, k in zip(vals, groups):
        g[k].append(v)
    a, N = len(g), len(vals)
    means = {k: sum(v) / len(v) for k, v in g.items()}
    grand = sum(vals) / N
    ssb = sum(len(v) * (means[k] - grand) ** 2 for k, v in g.items())
    ssw = sum((x - means[k]) ** 2 for k, v in g.items() for x in v)
    msb, msw = ssb / (a - 1), ssw / (N - a) if N > a else float("nan")
    k0 = (N - sum(len(v) ** 2 for v in g.values()) / N) / (a - 1)
    sb2 = max(0.0, (msb - msw) / k0)
    tot = sb2 + msw
    return {"clusters": a, "sd_between_cluster_means": statistics.stdev(means.values()) if a > 1 else None,
            "sd_within_pooled": math.sqrt(msw), "var_component_between": sb2, "var_component_within": msw,
            "icc": sb2 / tot if tot > 0 else None, "mean_cluster_size": N / a,
            "design_effect": 1 + (N / a - 1) * (sb2 / tot) if tot > 0 else None}


def twoway(cells):
    """cells: {(fact, story): value}, complete grid, one value per cell. Two-way ANOVA without replication."""
    facts = sorted({f for f, _ in cells})
    stories = sorted({s for _, s in cells})
    assert len(cells) == len(facts) * len(stories)
    a, b = len(facts), len(stories)
    grand = sum(cells.values()) / len(cells)
    fm = {f: sum(cells[(f, s)] for s in stories) / b for f in facts}
    sm = {s: sum(cells[(f, s)] for f in facts) / a for s in stories}
    ssf = b * sum((fm[f] - grand) ** 2 for f in facts)
    sss = a * sum((sm[s] - grand) ** 2 for s in stories)
    sse = sum((cells[(f, s)] - fm[f] - sm[s] + grand) ** 2 for f in facts for s in stories)
    msf, mss, mse = ssf / (a - 1), sss / (b - 1), sse / ((a - 1) * (b - 1))
    vf, vs = max(0.0, (msf - mse) / b), max(0.0, (mss - mse) / a)
    tot = vf + vs + mse
    return {"changed_facts": a, "stories": b, "sd_changed_fact_means": statistics.stdev(fm.values()),
            "sd_story_means": statistics.stdev(sm.values()), "sd_residual": math.sqrt(mse),
            "var_component_changed_fact": vf, "var_component_story": vs, "var_component_residual": mse,
            "share_changed_fact": vf / tot if tot else None, "share_story": vs / tot if tot else None,
            "share_residual": mse / tot if tot else None}


# ======================================================================= sign-flip test (vectorised) and power
def signs(n, rng):
    if n <= EXACT_N:
        m = ((np.arange(2 ** n)[:, None] >> np.arange(n)) & 1).astype(float)
        return 1 - 2 * m, True
    return rng.choice((-1.0, 1.0), size=(FLIPS, n)), False


def reject(X, S, exact, sided="two"):
    """X: (sims, n) simulated differences; S: (patterns, n) sign patterns (the identity is in the exact set; the Monte
    Carlo p counts the observed pattern once). sided 'two': p(|T*| >= |T|); 'lower': p(T* <= T). Returns (reject, T)."""
    out_r, out_t = [], []
    for i in range(0, len(X), 500):
        x = X[i:i + 500]
        t = x.sum(1)
        ts = x @ S.T
        if sided == "two":
            cnt = (np.abs(ts) >= np.abs(t)[:, None] - TOL).sum(1)
        else:
            cnt = (ts <= t[:, None] + TOL).sum(1)
        p = cnt / S.shape[0] if exact else (1 + cnt) / (1 + S.shape[0])
        out_r.append(p < ALPHA)
        out_t.append(t)
    return np.concatenate(out_r), np.concatenate(out_t)


class Sim:
    """Common random numbers across n: one (SIMS x n_max) resample of the base values and one sign set per n."""

    def __init__(self, base, n_max, seed, sided="two", direction=-1):
        self.base, self.sided, self.direction = np.asarray(base, float), sided, direction
        rng = np.random.default_rng(seed)
        self.idx = rng.integers(0, len(self.base), size=(SIMS, n_max))
        self.rng = rng
        self.cache = {}

    def power(self, n):
        if n not in self.cache:
            X = self.base[self.idx[:, :n]]
            S, exact = signs(n, np.random.default_rng((SEED, n)))
            r, t = reject(X, S, exact, self.sided)
            # two-sided: rejection in the direction of the target (sign of the base mean); lower: rejection of H0
            ok = r if self.sided == "lower" else r & (np.sign(t) == self.direction)
            self.cache[n] = float(ok.mean())
        return self.cache[n]

    def n_for(self, goal, start, n_max):
        lo, hi = 1, None
        n = max(2, min(start, n_max))
        if self.power(n) >= goal:
            hi = n
        else:
            lo = n
            while hi is None:
                n = min(n_max, n * 2)
                if self.power(n) >= goal:
                    hi = n
                elif n == n_max:
                    return None
                else:
                    lo = n
        while hi - lo > 1:
            m = (lo + hi) // 2
            if self.power(m) >= goal:
                hi = m
            else:
                lo = m
        return hi


def n_normal(sd, delta, power, one_sided=False):
    if sd is None or abs(delta) < TOL:
        return None
    z = Z(1 - ALPHA) if one_sided else Z(1 - ALPHA / 2)
    return math.ceil((z + Z(power)) ** 2 * sd ** 2 / delta ** 2)


def power_block(d, seed):
    """Sample sizes for the observed mean and half of it (normal and simulation)."""
    d = np.asarray(d, float)
    mu, sd = float(d.mean()), float(d.std(ddof=1))
    out = {}
    for tname, target in (("observed", mu), ("half", mu / 2)):
        rec = {"target_mean": target}
        base = d if tname == "observed" else d - mu + target
        sim = None
        for pw in POWERS:
            nn = n_normal(sd, target, pw)
            k = f"{int(pw * 100)}"
            rec[f"n{k}_normal"] = nn
            ns = None
            if nn is not None and nn <= SIM_N_CAP:
                if sim is None:
                    sim = Sim(base, 2 * SIM_N_CAP, seed_of(seed, tname), direction=-1 if target < 0 else 1)
                ns = sim.n_for(pw, nn, 2 * SIM_N_CAP)
                rec[f"power_sim_at_n{k}_normal"] = sim.power(max(2, nn))
            rec[f"n{k}_sim"] = ns
            rec[f"n{k}_disagree"] = nn is not None and nn <= SIM_N_CAP and (ns is None or abs(ns - nn) / nn > DISAGREE)
            rec[f"n{k}"] = ns if rec[f"n{k}_disagree"] else nn
        out[tname] = rec
    return out


def seed_of(*parts):
    import hashlib
    return int(hashlib.sha256("|".join(map(str, (SEED,) + parts)).encode()).hexdigest()[:15], 16)


# ======================================================================= P1/P2 tenancy
def tenancy(study):
    sub = {c: subset_of(study, c) for c in study.cases["tenancy"]}
    counts = defaultdict(int)
    for t, o in sub.values():
        counts[t] += 1
        if o:
            counts[o] += 1
    assert counts["S"] == 40 and counts["O"] == 56, dict(counts)
    fam = {c: study.D["tenancy"].reference(c)[F.SPEC["regimes"]["tenancy"]["cluster"]] for c in study.cases["tenancy"]}
    vals, within, runs = {}, {}, {}
    for d in {x for pair in TEN_CONTRASTS for x in pair} | {"casepath_checklist"}:
        rows = study.tenancy_rows(d)
        for m in TEN_MEASURES:
            vals[(d, m)], runs[(d, m)] = per_case(rows, "case", m)
            within[(d, m)] = within_var(runs[(d, m)])
    # check against study3_feedback's type summaries (claim-run means of each type)
    fb = json.loads((HERE / "study3_feedback.json").read_text())["F1"]["tenancy"]["by_design"]
    for d in {x for pair in TEN_CONTRASTS for x in pair}:
        for t in ("S", "O"):
            for m, key in (("strict_unsafe", "strict_unsafe_claim_run_mean"), ("all_dev", "all_dev_claim_run_mean")):
                mine = statistics.mean(v for c, v in vals[(d, m)].items() if sub[c][0] == t)
                assert abs(mine - fb[d][t][key]) < 1e-9, (d, t, m, mine, fb[d][t][key])

    def keep(c, s):
        return s == "all" or sub[c][0] == s or sub[c][1] == s
    out = []
    for a, b in TEN_CONTRASTS:
        for m in TEN_MEASURES:
            for s in SUBSETS:
                cs = [c for c in study.cases["tenancy"] if keep(c, s)]
                d = [vals[(a, m)][c] - vals[(b, m)][c] for c in cs]
                bz = [vals[(a, m)][c] == 0 and vals[(b, m)][c] == 0 for c in cs]
                rec = {"regime": "tenancy", "a": a, "b": b, "measure": m, "subset": s, **describe(d, bz),
                       "a_mean": statistics.mean(vals[(a, m)][c] for c in cs), "b_mean": statistics.mean(vals[(b, m)][c] for c in cs)}
                if s in ("all", "S", "O"):
                    rec["clusters_family"] = oneway(d, [fam[c] for c in cs])
                rec["power"] = power_block(d, seed_of("ten", a, b, m, s))
                rec["_diffs"] = d
                out.append(rec)
    return out, vals, within, runs, sub, dict(counts)


# ======================================================================= P1/P2 theft
def theft(study, lint):
    vals, meta, within = {}, {}, {}
    for d in {x for pair in THEFT_CONTRASTS for x in pair}:
        on, _ = study.theft_rows(d)
        vals[d], g = per_case(on, "pair_id", "errors")
        within[d] = within_var(g)
        for r in on:
            meta[r["pair_id"]] = (r["condition"], r["story"])
    fb = json.loads((HERE / "study3_feedback.json").read_text())["F1"]["theft"]["by_design"]
    for d in vals:
        assert abs(statistics.mean(vals[d].values()) - fb[d]["S"]["errors_per_pair"]) < 1e-9, d
    pairs = sorted(meta)
    assert len(pairs) == 72
    contrasts = list(THEFT_CONTRASTS)
    for v, pv in lint.items():
        vals[f"lint_{v}"] = pv
        assert set(pv) == set(pairs)
        contrasts += [(f"lint_{v}", "ric_frontier"), (f"lint_{v}", "ric_original_frontier")]
    out = []
    for a, b in contrasts:
        d = [vals[a][p] - vals[b][p] for p in pairs]
        bz = [vals[a][p] == 0 and vals[b][p] == 0 for p in pairs]
        rec = {"regime": "theft", "a": a, "b": b, "measure": "errors", "subset": "changed-fact pairs", **describe(d, bz),
               "a_mean": statistics.mean(vals[a].values()), "b_mean": statistics.mean(vals[b].values()),
               "clusters_changed_fact": oneway(d, [meta[p][0] for p in pairs]),
               "clusters_story": oneway(d, [meta[p][1] for p in pairs]),
               "crossed": twoway({meta[p]: x for p, x in zip(pairs, d)}),
               "power": power_block(d, seed_of("theft", a, b)), "_diffs": d}
        out.append(rec)
    return out, within


def lint_pairs(study):
    """Per-pair wrong + missed for the frontier checklist-only product under the lint variants, from
    lint_followup.theft_variant with its own scoring call (theft_diagnosis.score) captured; checked against the
    stored by-fact values in lint_followup.json."""
    try:
        import lint_followup as LF
        import theft_diagnosis as TD
    except Exception as exc:  # reported
        return {}, f"not recoverable: import failed ({exc})"
    stored = json.loads((HERE / "lint_followup.json").read_text())
    model, design = "gpt-6.1-terra", "casepath_frontier_checklist"
    oos = stored["development_flags"][model]["flags"]
    out = {}
    for v in ("tested",) + tuple(LINT_VARIANTS):
        cap = []
        orig = TD.score

        def grab(*a, **k):
            r = orig(*a, **k)
            cap.append(r)
            return r
        with R.patched(TD, "score", grab):
            res = LF.theft_variant(design, model, v, oos if v.startswith("c_") else None)
        on = cap[0][0]
        pv, _ = per_case(on, "pair_id", "errors")
        bf = TD.by_fact(on)
        want = stored["part2_theft"][model][v]["by_fact_raw"]
        assert all(abs(bf[c] - want[c]) < 1e-9 for c in want), ("lint variant does not reproduce", v)
        assert res["by_fact_raw"] == bf
        out[v] = pv
    tested = out.pop("tested")
    st_vals, _ = per_case(study.theft_rows(design)[0], "pair_id", "errors")
    assert all(abs(tested[p] - st_vals[p]) < 1e-9 for p in st_vals), "tested variant differs from Study 3's stored rows"
    return out, "recovered: lint_followup.theft_variant per-pair rows (captured), reproduce lint_followup.json by fact and Study 3's stored rows (tested)"


# ======================================================================= P3 non-inferiority on S
def noninferiority(ten):
    out = []
    for rec in ten:
        if rec["subset"] != "S":
            continue
        d = np.asarray(rec["_diffs"], float)
        mu, sd = float(d.mean()), float(d.std(ddof=1))
        for assume, delta in (("observed", mu), ("zero", 0.0)):
            for m in NI_MARGINS:
                r = {"a": rec["a"], "b": rec["b"], "measure": rec["measure"], "assume": assume, "true_diff": delta,
                     "margin": m, "sd": sd}
                sim = None
                for pw in POWERS:
                    k = f"{int(pw * 100)}"
                    nn = None if delta >= m else n_normal(sd, m - delta, pw, one_sided=True)
                    r[f"n{k}_normal"] = nn
                    ns = None
                    if nn is not None and nn <= SIM_N_CAP:
                        if sim is None:
                            sim = Sim(d - mu + delta - m, 2 * SIM_N_CAP, seed_of("ni", rec["a"], rec["b"], rec["measure"], assume, m),
                                      sided="lower")
                        ns = sim.n_for(pw, nn, 2 * SIM_N_CAP)
                    r[f"n{k}_sim"] = ns
                    dis = nn is not None and nn <= SIM_N_CAP and (ns is None or abs(ns - nn) / nn > DISAGREE)
                    r[f"n{k}_disagree"] = dis
                    r[f"n{k}"] = ns if dis else nn
                out.append(r)
    return out


# ======================================================================= P4 share sweep
def sweep(vals, sub):
    cases = list(sub)
    S = [c for c in cases if sub[c][0] == "S"]
    obf = [c for c in cases if sub[c][1] == "O: open branch fact only"]
    den = [c for c in cases if sub[c][1] == "O: denied defining event"]
    ingredients = {"open branch fact only": obf, "open branch fact + denied event (23:24, the test's proportion)": obf + den}
    out = []
    for b in SWEEP_COMPARATORS:
        for m in TEN_MEASURES:
            dS = np.array([vals[("casepath", m)][c] - vals[(b, m)][c] for c in S])
            for iname, oc in ingredients.items():
                dO = np.array([vals[("casepath", m)][c] - vals[(b, m)][c] for c in oc])
                for N in SWEEP_N:
                    k = N // 4
                    rng = np.random.default_rng(seed_of("sweep", b, m, iname, N))
                    levels = []
                    for sh in SWEEP_SHARES:
                        no = int(sh * k + 0.5)
                        x = np.concatenate([dO[rng.integers(0, len(dO), (SIMS, no))], dS[rng.integers(0, len(dS), (SIMS, k - no))]], axis=1)
                        levels.append((sh, no, x))
                    pooled = np.concatenate([x for _, _, x in levels], axis=1)
                    Sg, ex = signs(N, rng)
                    r1, t1 = reject(pooled, Sg, ex)
                    x50 = levels[-1][2]
                    Sg, ex = signs(k, rng)
                    r2, t2 = reject(x50, Sg, ex)
                    x0 = levels[0][2] - SWEEP_MARGIN
                    r3, _ = reject(x0, Sg, ex, sided="lower")
                    exp_pool = float(np.mean([(no * dO.mean() + (k - no) * dS.mean()) / k for _, no, _ in levels]))
                    exp50 = (levels[-1][1] * dO.mean() + (k - levels[-1][1]) * dS.mean()) / k
                    out.append({"b": b, "measure": m, "open_ingredient": iname, "N": N, "per_level": k,
                                "open_cases_per_level": {f"{int(sh * 100)}%": no for sh, no, _ in levels},
                                "expected_diff_pooled": exp_pool, "expected_diff_50": float(exp50), "expected_diff_0": float(dS.mean()),
                                "power_pooled_casepath_better": float((r1 & (t1 < 0)).mean()),
                                "power_pooled_comparator_better": float((r1 & (t1 > 0)).mean()),
                                "power_50_casepath_better": float((r2 & (t2 < 0)).mean()),
                                "power_50_comparator_better": float((r2 & (t2 > 0)).mean()),
                                "power_ni_0_margin_0.15": float(r3.mean())})
    return out, {"S": len(S), "open branch fact only": len(obf), "denied defining event": len(den)}


# ======================================================================= type I error of the sign-flip test
SIZE_N = (10, 20, 40, 100)


def size_check(contrasts):
    """Rejection rate when the true mean difference is zero (two-sided superiority) or exactly the margin 0.15
    (one-sided non-inferiority), resampling Study 3's differences centred on that value: the test's validity rests on
    symmetry, which these skewed, zero-inflated differences lack."""
    out = []
    for rec in contrasts:
        if rec["subset"] not in ("all", "S", "changed-fact pairs") or (rec["regime"] == "theft" and rec["a"].startswith("lint_")):
            continue
        d = np.asarray(rec["_diffs"], float)
        c = d - d.mean()
        r = {"regime": rec["regime"], "a": rec["a"], "b": rec["b"], "measure": rec["measure"], "subset": rec["subset"],
             "share_eq0": rec["share_eq0"]}
        rng = np.random.default_rng(seed_of("size", rec["regime"], rec["a"], rec["b"], rec["measure"], rec["subset"]))
        for n in SIZE_N:
            X = c[rng.integers(0, len(c), (SIMS, n))]
            S, ex = signs(n, rng)
            r[f"two_sided_n{n}"] = float(reject(X, S, ex)[0].mean())
            r[f"ni_one_sided_n{n}"] = float(reject(X, S, ex, sided="lower")[0].mean())  # (c + m) - m = c
        out.append(r)
    return out


# ======================================================================= one-run adjustment
def one_run_note(ten, runs, sub):
    """The frontier checklist-only product has one run per case; the others three. If it had three runs, the variance of
    its per-case value would fall by (2/3) x its within-case run variance (unknown; bracketed by the frontier single
    prompt's and the cost-efficient checklist-only product's)."""
    out = []
    for rec in ten:
        if rec["a"] != "casepath_frontier_checklist" or rec["subset"] not in ("all", "S", "O"):
            continue
        m = rec["measure"]
        cs = [c for c in sub if rec["subset"] == "all" or sub[c][0] == rec["subset"]]
        for proxy in ("ric_frontier", "casepath_checklist"):
            w = within_var({c: runs[(proxy, m)][c] for c in cs})
            var3 = rec["sd"] ** 2 - (2 / 3) * w
            sd3 = math.sqrt(var3) if var3 > 0 else None  # None: the proxy's run variance cannot be this design's
            out.append({"subset": rec["subset"], "measure": m, "proxy_within_run_variance": proxy, "within_var": w,
                        "sd_one_run": rec["sd"], "sd_if_three_runs": sd3,
                        "n80_obs_one_run": n_normal(rec["sd"], rec["mean"], 0.8), "n80_obs_three_runs": n_normal(sd3, rec["mean"], 0.8) if sd3 else None})
    return out


# ======================================================================= report
def f(x, nd=3):
    return "–" if x is None else f"{x:.{nd}f}"


def nfmt(x):
    return "–" if x is None else (">2000" if x == "cap" else str(x))


def lab(k):
    if k.startswith("lint_"):
        return f"Frontier checklist only, lint {k[5:]} ({LINT_VARIANTS[k[5:]]}, one run)"
    return LABELS[k]


def table(head, rows):
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(map(str, r)) + " |" for r in rows]


def nshow(p, k):
    v = p[f"n{k}"]
    if v is None:
        return "∞" if p[f"n{k}_normal"] is None else (">2000" if p[f"n{k}_disagree"] else nfmt(v))
    return f"{v}{'*' if p[f'n{k}_disagree'] else ''}"


def markdown(res):
    L = [f"# Power for a Study 4 replication", "", f"**{HEADER}.**", "",
         "Generated by `analysis/power_study4.py` from the stored plans of `runs/study3/confirm` (scored by `analysis/study3.py` "
         "through the loaders of `study3_feedback.py` / `study3_review.py`). No model calls. These numbers plan a future study; "
         "they are not evidence about CasePath and change no Study 3 result.", "",
         "## Method", ""] + [f"- {x}" for x in res["method"]] + [""]
    L += ["## Key contrasts (all cases; n = independent cases for two-sided alpha 0.05)", "",
          "Difference = CasePath minus comparator (negative favours CasePath). n columns: normal approximation, replaced by the "
          "simulation where the two disagree by more than 20% (marked *); ∞ = no difference to detect; >2000 = simulation "
          "did not reach the power by n = 2000.", ""]
    rows = []
    for rec in res["contrasts"]:
        if rec["subset"] not in ("all", "S", "changed-fact pairs"):
            continue
        p, h = rec["power"]["observed"], rec["power"]["half"]
        rows.append([rec["regime"], TEN_MEASURES.get(rec["measure"], "wrong + missed per pair"), rec["subset"], lab(rec["a"]), lab(rec["b"]),
                     f(rec["mean"]), f(rec["sd"]), f"{rec['share_lt0']:.2f}/{rec['share_eq0']:.2f}/{rec['share_gt0']:.2f}",
                     nshow(p, 80), nshow(p, 90), nshow(h, 80), nshow(h, 90)])
    L += table(["Regime", "Measure", "Cases", "A", "B", "Mean diff", "SD", "<0 / =0 / >0", "n80 obs", "n90 obs", "n80 half", "n90 half"], rows) + [""]
    L += ["## All tenancy contrasts by claim type", ""]
    rows = []
    for rec in res["contrasts"]:
        if rec["regime"] != "tenancy":
            continue
        p, h = rec["power"]["observed"], rec["power"]["half"]
        rows.append([TEN_MEASURES[rec["measure"]].split(" per")[0], rec["subset"], lab(rec["a"]), lab(rec["b"]), rec["n"], f(rec["a_mean"]), f(rec["b_mean"]),
                     f(rec["mean"]), f(rec["sd"]), f"{rec['share_lt0']:.2f}/{rec['share_eq0']:.2f}/{rec['share_gt0']:.2f}",
                     f"{rec['share_both_zero']:.2f}", nshow(p, 80), nshow(p, 90), nshow(h, 80), nshow(h, 90)])
    L += table(["Measure", "Subset", "A", "B", "n", "A mean", "B mean", "Mean diff", "SD", "<0/=0/>0", "both 0", "n80 obs", "n90 obs", "n80 half", "n90 half"], rows) + [""]
    L += ["## Theft contrasts (72 changed-fact pairs)", "", f"Lint variants: {res['lint_status']}.", ""]
    rows = []
    for rec in res["contrasts"]:
        if rec["regime"] != "theft":
            continue
        p, h = rec["power"]["observed"], rec["power"]["half"]
        rows.append([lab(rec["a"]), lab(rec["b"]), f(rec["a_mean"]), f(rec["b_mean"]), f(rec["mean"]), f(rec["sd"]),
                     f"{rec['share_lt0']:.2f}/{rec['share_eq0']:.2f}/{rec['share_gt0']:.2f}", f"{rec['share_both_zero']:.2f}",
                     nshow(p, 80), nshow(p, 90), nshow(h, 80), nshow(h, 90)])
    L += table(["A", "B", "A mean", "B mean", "Mean diff", "SD", "<0/=0/>0", "both 0", "n80 obs", "n90 obs", "n80 half", "n90 half"], rows) + [""]
    L += ["## Normal approximation against simulation", "",
          "Every n with a normal value of at most 1,000 was also found by simulation (2,000 simulated studies, resampling the "
          "observed per-case differences; sign-flip test, exact up to 12 cases, otherwise 1,000 random sign patterns). Rows "
          "where they differ by more than 20%:", ""]
    rows = []
    for rec in res["contrasts"]:
        for t in ("observed", "half"):
            p = rec["power"][t]
            for k in ("80", "90"):
                if p[f"n{k}_disagree"]:
                    rows.append([rec["regime"], rec["measure"], rec["subset"], lab(rec["a"]), lab(rec["b"]), t, k, p[f"n{k}_normal"], nfmt(p[f"n{k}_sim"])])
    L += table(["Regime", "Measure", "Subset", "A", "B", "Target", "Power %", "n normal", "n simulation"], rows) if rows else ["None."]
    L += ["", "## Cluster structure of the per-case differences", "",
          "Study 3's cases were crossed with families (tenancy) and with changed facts and stories (theft). A replication with "
          "independent cases draws all of this variance afresh for every case; the SD used above is the marginal SD over "
          "Study 3's cases, which includes it. A large between-cluster share means the replication's mean difference will "
          "depend on which families or changed facts it samples.", "", "Tenancy (families):", ""]
    rows = []
    for rec in res["contrasts"]:
        c = rec.get("clusters_family")
        if c:
            rows.append([rec["measure"], rec["subset"], lab(rec["a"]), lab(rec["b"]), f(rec["sd"]), c["clusters"], f(c["sd_between_cluster_means"]),
                         f(c["sd_within_pooled"]), f(c["icc"], 2)])
    L += table(["Measure", "Subset", "A", "B", "SD total", "Families", "SD of family means", "SD within family", "ICC"], rows)
    L += ["", "Theft (changed fact x story, 9 x 8, one pair per cell):", ""]
    rows = []
    for rec in res["contrasts"]:
        if rec["regime"] == "theft":
            c, cf, cs = rec["crossed"], rec["clusters_changed_fact"], rec["clusters_story"]
            rows.append([lab(rec["a"]), lab(rec["b"]), f(rec["sd"]), f(c["sd_changed_fact_means"]), f(cf["sd_within_pooled"]),
                         f(c["sd_story_means"]), f(cs["sd_within_pooled"]), f(c["sd_residual"]),
                         f"{c['share_changed_fact']:.2f}/{c['share_story']:.2f}/{c['share_residual']:.2f}"])
    L += table(["A", "B", "SD total", "SD of fact means", "SD within fact", "SD of story means", "SD within story", "SD residual",
                "Variance share fact/story/residual"], rows)
    L += ["", "## Non-inferiority where every fact is stated (type S, 40 claims)", "",
          "H0: CasePath minus comparator >= margin; one-sided alpha 0.05; n = independent S cases. '–' = the assumed true "
          "difference is at or above the margin (cannot be shown). * = simulation (one-sided sign-flip, differences shifted to "
          "the assumed mean) replaces the normal value.", ""]
    rows = []
    for r in res["noninferiority"]:
        rows.append([r["measure"], lab(r["a"]), lab(r["b"]), r["assume"], f(r["true_diff"]), f(r["sd"]), r["margin"],
                     nshow(r, 80) if r["n80_normal"] is not None else "–", nshow(r, 90) if r["n90_normal"] is not None else "–"])
    L += table(["Measure", "A", "B", "True diff", "Value", "SD", "Margin", "n80", "n90"], rows)
    L += ["", "## Share sweep (tenancy)", "",
          "N cases per regime, four levels of N/4 cases each (0%, 10%, 25%, 50% with an open fact; open counts rounded half "
          "up); each level its own cases. Per-case differences drawn from Study 3's S claims and, for the open cases, from "
          "the open-branch-fact claims (main) or from open-branch-fact and denied-event claims at the test's 23:24 "
          "(sensitivity). 2,000 simulated studies. Power = rejection in CasePath's favour (superiority, two-sided 0.05) and "
          "rejection of 'CasePath worse by 0.15 or more' (non-inferiority at 0%, one-sided 0.05). Theft has no comparable "
          "stated/open split on the same measure, so no sweep is given for it.", "",
          f"Ingredient sizes: {res['sweep_ingredients']}.", ""]
    rows = []
    for r in res["sweep"]:
        rows.append([r["measure"], lab(r["b"]), r["open_ingredient"].split(" (")[0], r["N"], f(r["expected_diff_pooled"]),
                     f"{r['power_pooled_casepath_better']:.2f}", f(r["expected_diff_50"]), f"{r['power_50_casepath_better']:.2f}",
                     f"{r['power_50_comparator_better']:.2f}", f(r["expected_diff_0"]), f"{r['power_ni_0_margin_0.15']:.2f}"])
    L += table(["Measure", "Comparator", "Open ingredient", "N", "E diff pooled", "Power pooled", "E diff 50%", "Power 50%",
                "Power 50% (comparator better)", "E diff 0%", "Power NI 0% (0.15)"], rows)
    L += ["", "## Type I error of the sign-flip test on these distributions", "",
          "Rejection rate (nominal 0.05) when Study 3's per-case differences are recentred on the null value (zero for the "
          "two-sided superiority test; the margin for the one-sided non-inferiority test, where the recentred differences "
          "are the same), 2,000 simulated studies. The sign-flip test assumes the differences are symmetric about the null "
          "value; a recentred zero-inflated distribution is not, so its rate can stray from 0.05.", ""]
    rows = [[r["regime"], r["measure"], r["subset"], lab(r["a"]), lab(r["b"]), f"{r['share_eq0']:.2f}"]
            + [f"{r[f'two_sided_n{n}']:.3f}" for n in SIZE_N] + [f"{r[f'ni_one_sided_n{n}']:.3f}" for n in SIZE_N] for r in res["size_check"]]
    L += table(["Regime", "Measure", "Cases", "A", "B", "Ties"] + [f"two-sided n={n}" for n in SIZE_N] + [f"one-sided n={n}" for n in SIZE_N], rows)
    L += ["", "## The one-run frontier product", "",
          "CasePath, checklist only, on the frontier model has one run per case; every other design three. Its per-case "
          "value therefore carries the full run-to-run variance. If a replication ran it three times, the SD of the "
          "differences would shrink by (2/3) x its within-case run variance, which Study 3 cannot estimate; bracketed here by "
          "the frontier single prompt's and the cost-efficient checklist-only product's within-case run variance. '–' = the proxy's "
          "run variance exceeds 1.5 x the observed variance of the differences, so it cannot be this design's.", ""]
    rows = [[r["measure"], r["subset"], r["proxy_within_run_variance"], f(r["within_var"]), f(r["sd_one_run"]), f(r["sd_if_three_runs"]),
             nfmt(r["n80_obs_one_run"]), nfmt(r["n80_obs_three_runs"])] for r in res["one_run"]]
    L += table(["Measure", "Subset", "Within-run variance from", "Within var", "SD (one run)", "SD (three runs)", "n80 obs (one run)", "n80 obs (three runs)"], rows)
    L += ["", "## Limits", ""] + [f"- {x}" for x in res["limits"]]
    return "\n".join(L) + "\n"


def main():
    study = load_study()
    lint, lint_status = lint_pairs(study)
    ten, ten_vals, within, runs, sub, counts = tenancy(study)
    th, th_within = theft(study, lint)
    ni = noninferiority(ten)
    sw, sizes = sweep(ten_vals, sub)
    res = {"header": HEADER, "posthoc": True, "preregistered": False, "result": False, "data": F.DATA, "run_label": F.LABEL,
           "settings": {"alpha": ALPHA, "powers": POWERS, "simulations": SIMS, "monte_carlo_sign_patterns": FLIPS,
                        "exact_signflip_up_to_n": EXACT_N, "simulation_search_if_normal_n_at_most": SIM_N_CAP,
                        "simulation_search_cap": 2 * SIM_N_CAP, "disagreement_threshold": DISAGREE, "seed": SEED,
                        "ni_margins": NI_MARGINS, "sweep_N": SWEEP_N, "sweep_shares": SWEEP_SHARES, "sweep_ni_margin": SWEEP_MARGIN},
           "tenancy_counts": counts, "lint_status": lint_status,
           "contrasts": ten + th, "noninferiority": ni, "sweep": sw, "sweep_ingredients": sizes,
           "one_run": one_run_note(ten, runs, sub),
           "size_check": size_check(ten + th),
           "within_case_run_variance": {"tenancy": {f"{d}|{m}": v for (d, m), v in within.items()}, "theft": th_within},
           "inputs": dict(sorted(study.inputs.hashes.items()))}
    res["method"] = [
        "Per-case value of a design = mean over its stored runs on the case (three runs; one for the frontier checklist-only "
        "product and its lint variants), scored by study3.Study (study2.ten_row; theft: study2.theft_rows, wrong + missed on "
        "the 72 changed-fact pairs). Means reproduce study3_feedback.json F1 (checked).",
        "Claim types: study3_feedback.claim_type (S 40, O 56); O split by the spec's subsets: open defining event "
        "(open_event, 9), denied defining event (denied_event, 24), open branch fact only (open_branch_fact, 23).",
        "Normal approximation: n = (z_{1-alpha/2} + z_power)^2 SD^2 / delta^2 (superiority), (z_{1-alpha} + z_power)^2 SD^2 / "
        "(margin - delta)^2 (non-inferiority), SD = sample SD of Study 3's per-case differences.",
        "Simulation: per target, 2,000 simulated studies resample the observed per-case differences with replacement "
        "(shifted by a constant to the target mean for the half-difference and non-inferiority targets), with common "
        "random numbers across n; sign-flip test exact up to 12 cases, else 1,000 random sign patterns, p = (1 + count) / "
        "1,001; superiority counts rejections in the target's direction; n found by doubling and bisection up to 2,000.",
        "Cluster structure: one-way ANOVA by family (tenancy) and by changed fact and by story (theft), and a two-way "
        "changed fact x story ANOVA without replication (variance components truncated at zero).",
        "Lint variants: " + lint_status + ".",
    ]
    res["limits"] = limits(res)
    out = {k: v for k, v in res.items()}
    out["contrasts"] = [{k: v for k, v in r.items() if k != "_diffs"} | {"differences": [round(x, 6) for x in r["_diffs"]]} for r in res["contrasts"]]
    OUT.with_suffix(".json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=list) + "\n")
    OUT.with_suffix(".md").write_text(markdown(res))
    print("written", OUT.with_suffix(".json"), "and", OUT.with_suffix(".md"))
    return res


def limits(res):
    L = []
    zi = [r for r in res["contrasts"] if r["subset"] in ("all", "S", "changed-fact pairs") and r["share_eq0"] >= 0.5]
    if zi:
        L.append("Zero-inflated differences: " + "; ".join(f"{r['regime']} {r['measure']} {r['subset']} {lab(r['a'])} vs {lab(r['b'])}: "
                                                          f"{r['share_eq0']:.0%} of cases tie ({r['share_both_zero']:.0%} both zero)" for r in zi)
                 + ". The sign-flip test gets its power only from non-tied cases; shifting such differences to a half-size target "
                   "(simulation) removes the ties and is optimistic.")
    L.append("Floor effects: on S claims most designs make few strict unsafe errors, so the S mean differences are small and "
             "rest on few non-zero cases; their SDs and means are estimated from 40 claims in 24 families.")
    L.append("Study 3's cases are not independent: per-case SDs are marginal over crossed clusters (families; changed facts x "
             "stories). A replication that samples different families or changed facts will see a different mean difference; "
             "where the between-cluster share is large the observed mean is a weak guide to the replication's.")
    L.append("Observed differences used as the true effect are selected (post hoc) and noisy; the 'half' target is the more "
             "prudent planning value.")
    L.append("The frontier checklist-only product has one run: its per-case value includes the whole run-to-run variance, so "
             "its SD is larger than a three-run replication would have (see the one-run section), and its mean is one draw.")
    L.append("Small n: with many tied cases the two-sided sign-flip test's rejection rate under a recentred null reaches "
             "0.10-0.20 at n = 10 and 0.07-0.12 at n = 20 for some tenancy contrasts (type I error section); sample sizes "
             "below about 40 cases rest on a few non-tied Study 3 cases and should not be used as planned sizes. The "
             "non-inferiority simulations that give n of 5-17 for the frontier checklist-only product on S claims are of "
             "this kind (75% of its S cases tie).")
    L.append("Lint variants: (a) and (b) give identical per-pair values, as do (c_a) and (c_b), as in lint_followup.json.")
    L.append("The theft measure exists only on changed-fact pairs, each built from a shared off text of a story; a replication "
             "with each case its own story removes the story sharing that Study 3 had.")
    return L


if __name__ == "__main__":
    main()
