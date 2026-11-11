"""Study 3, analyses added after review (R1-R11). NOT pre-registered: not part of ANALYSIS_PLAN_STUDY3.md, decided after
the results and an independent referee report were known. No model calls, no network.

    python3 study3_review.py      # writes study3_review.json and study3_review.md

Everything is computed from stored outputs: the plans and entries of runs/study3/confirm (read through study3.Study,
so the same loading, derivations, failed-output rule, scoring and fresh2 guard apply), the product's response cache
(runs/product/cache, read only, to see the individual readings and to tell the claim reader's brief from its reading),
the ledgers (cost, call latency, prompt tokens), the designed fact states of fresh2/tenancy (references) and the
reference engine of fresh2/tenancy/build.py (engine_plan, state_name; imported, not copied). Statistics reuse
study2/study3 (signflip_p, paired_bootstrap, quantile, by_cluster, contrast). Settings: 10,000 resamples and the
spec's seed, with a fixed per-analysis seed string; 200 draws for R4. A missing key raises (KeyError); nothing is
filled in silently.

The pure computations (claim outcomes, reweighting and its bootstrap, the fact-outcome classification, combination of
readings, reference under flipped facts, two-way resampling, test inversion, the denied-event classification, the
checklist comparison and the cost split) are module functions, tested in test_study3_review.py on constructed inputs.
"""
from __future__ import annotations

import json
import random
import re
import sys
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMIS = HERE.parent
sys.path.insert(0, str(HERE))
import study3 as s3  # noqa: E402

s2 = s3.s2
DATA, LABEL = "fresh2", "confirm"
OUT = HERE / "study3_review"
LABEL_REVIEW = "ADDED AFTER REVIEW: not pre-registered, not part of ANALYSIS_PLAN_STUDY3.md"
CACHE = TMIS / "runs" / "product" / "cache"
RUN = TMIS / "runs" / "study3" / "confirm"
SUBSETS = ("ordinary", "denied_event", "open_event")
TOL = 1e-12
R4_DRAWS = 200
R4_QS = (0.05, 0.10, 0.20)
MIXES = {"test mix (63/24/9 of 96)": None, "all ordinary": (1.0, 0.0, 0.0),
         "90% ordinary, 5% denied, 5% open": (0.90, 0.05, 0.05), "80% ordinary, 10% denied, 10% open": (0.80, 0.10, 0.10)}
SPEC = json.loads(s3.SPEC.read_text())


def need(d, *path):
    """d[path[0]][path[1]]...; raises KeyError naming the full path."""
    cur = d
    for i, k in enumerate(path):
        if not isinstance(cur, (dict, list)) or (isinstance(cur, dict) and k not in cur):
            raise KeyError("missing key " + "/".join(map(str, path[:i + 1])))
        cur = cur[k]
    return cur


def pct_range(vals):
    v = sorted(vals)
    return {"mean": sum(v) / len(v), "p2_5": s2.quantile(v, 0.025), "p97_5": s2.quantile(v, 0.975)}


# ======================================================================= R1: claim-level outcomes
def claim_outcome(row):
    """One scored claim-run (study2.ten_row): exactly the reference checklist (requests and holds, not handed over),
    at least one strict unsafe error, at least one wrong hold (a required-now document held, or a hold the reference
    neither requires nor holds)."""
    wrong_hold = row["held_req"] + row["spurious_hold"]
    return {"exact": int(not row["deferred"] and row["strict_unsafe"] == 0 and wrong_hold == 0),
            "any_unsafe": int(row["strict_unsafe"] > 0), "any_wrong_hold": int(wrong_hold > 0)}


def claim_shares(rows):
    if not rows:
        return {"claim_runs": 0}
    o = [claim_outcome(r) for r in rows]
    n = len(o)
    return {"claim_runs": n, "exact_share": sum(x["exact"] for x in o) / n,
            "any_unsafe_share": sum(x["any_unsafe"] for x in o) / n,
            "any_wrong_hold_share": sum(x["any_wrong_hold"] for x in o) / n,
            "handed_over": sum(r["deferred"] for r in rows)}


def r1(study):
    ten, theft = {}, {}
    for d in SPEC["designs"]:
        k = d["key"]
        if "tenancy" in d["regimes"]:
            rows = study.tenancy_rows(k)
            out = {"all claims": claim_shares(rows)}
            for s in SUBSETS:
                out[s] = claim_shares([r for r in rows if study.in_subset(r["case"], s)])
            ten[k] = out
        if "theft" in d["regimes"]:
            on, un = study.theft_rows(k)
            theft[k] = {"changed_pair_runs": len(on), "no_wrong_or_missed_share": sum(r["errors"] == 0 for r in on) / len(on),
                        "unresolved_pair_runs": len(un), "unresolved_unchanged_share": sum(bool(r["stable"]) for r in un) / len(un)}
    return {"tenancy": ten, "theft": theft,
            "definitions": {"exact": "requests = the reference's required-now set and holds = its held set, claim not handed over",
                            "any_unsafe": "strict unsafe errors > 0 (unnecessary + missed + handed over + premature + silent skips)",
                            "any_wrong_hold": "held a required-now document, or held a document the reference neither requires nor holds",
                            "theft_changed": "changed-fact pair-run with no wrong and no missed change (frozen scorer)",
                            "theft_unresolved": "unresolved-fact pair-run whose requests did not change"}}


# ======================================================================= R2: other mixes of claim types
def subset_means(rows, subset_of, value):
    g = defaultdict(list)
    for r in rows:
        g[subset_of(r)].append(value(r))
    return {s: sum(v) / len(v) for s, v in g.items()}


def reweighted(means, weights):
    """sum_s w_s * mean_s over the subsets with positive weight; raises if a weighted subset has no mean."""
    return sum(w * means[s] for s, w in weights.items() if w > 0)


def reweight_bootstrap(cells, weights, B, seed):
    """cells: {family: {subset: (sum of the claim-run values, number of claim-runs)}}. A resample draws families with
    replacement; a subset's mean is the pooled mean over the drawn families' claim-runs in it; the statistic is the
    weighted sum of the subset means. A resample in which a weighted subset is empty is drawn again (counted)."""
    g = random.Random(seed)
    fams = sorted(cells)
    vals, redraws = [], 0
    while len(vals) < B:
        pick = [g.choice(fams) for _ in fams]
        tot = defaultdict(lambda: [0.0, 0])
        for f in pick:
            for s, (sm, n) in cells[f].items():
                tot[s][0] += sm
                tot[s][1] += n
        if any(w > 0 and tot[s][1] == 0 for s, w in weights.items()):
            redraws += 1
            continue
        vals.append(sum(w * tot[s][0] / tot[s][1] for s, w in weights.items() if w > 0))
    vals.sort()
    return vals, redraws


def r2(study):
    counts = {s: sum(study.in_subset(c, s) for c in study.cases["tenancy"]) for s in SUBSETS}
    n = sum(counts.values())
    mixes = {name: dict(zip(SUBSETS, w)) if w else {s: counts[s] / n for s in SUBSETS} for name, w in MIXES.items()}
    sub = lambda r: next(s for s in SUBSETS if study.in_subset(r["case"], s))
    per_design = {}
    for d in SPEC["designs"]:
        if "tenancy" not in d["regimes"]:
            continue
        m = subset_means(study.tenancy_rows(d["key"]), sub, lambda r: r["strict_unsafe"])
        per_design[d["key"]] = {"subset_means": m, "by_mix": {k: reweighted(m, w) for k, w in mixes.items()}}
    contrasts = {}
    for b in ("ric", "ric_frontier"):
        ra = {(r["case"], r["run"]): r for r in study.tenancy_rows("casepath")}
        cells = defaultdict(lambda: defaultdict(lambda: [0.0, 0]))
        for r in study.tenancy_rows(b):
            a = ra[(r["case"], r["run"])]
            c = cells[r["cluster"]][sub(r)]
            c[0] += a["strict_unsafe"] - r["strict_unsafe"]
            c[1] += 1
        cells = {f: {s: tuple(v) for s, v in x.items()} for f, x in cells.items()}
        out = {}
        for k, w in mixes.items():
            point = per_design["casepath"]["by_mix"][k] - per_design[b]["by_mix"][k]
            boot, redraws = reweight_bootstrap(cells, w, s2.B, f"{s2.SEED}|R2|{b}|{k}")
            out[k] = {"diff": point, "ci": [s2.quantile(boot, 0.025), s2.quantile(boot, 0.975)], "redraws": redraws}
        contrasts[f"casepath - {b}"] = out
    return {"claims_per_subset": counts, "mixes": mixes, "by_design": per_design, "contrasts": contrasts,
            "method": ("Overall strict unsafe errors per claim = sum over the three subsets of weight x the subset's mean per "
                       "claim-run. Interval: 10,000 paired cluster-bootstrap resamples of the 24 families (with replacement); in "
                       "each resample the subset means of the CasePath-minus-comparator differences are pooled over the drawn "
                       "families' claim-runs and reweighted; percentile 2.5-97.5. A resample with no claim of a weighted subset "
                       "is drawn again (count reported).")}


# ======================================================================= R3: fact-level accuracy
def product_value(f):
    """What the evaluator used for one stored product fact: ('admitted', v) | ('presumed', v) | ('unresolved', None) |
    ('conflicting', None) | ('not accepted', None) | ('absent', None)."""
    if f is None:
        return ("absent", None)
    st = f["status"]
    if st == "established":
        return ("admitted", f["value"]) if f.get("verdict") == "accepted" else ("not accepted", None)
    if st == "presumed":
        return ("presumed", f["value"])
    if st == "conflicting":
        return ("conflicting", None)
    if st == "unknown":
        return ("unresolved", None)
    raise ValueError(f"unknown fact status {st}")


def fact_category(kind, value, truth, designed):
    """Column of the fact table. For a designed open fact the right outcome is 'unresolved'; an admitted or presumed value
    is compared with the fact's recorded true value."""
    if kind in ("admitted", "presumed"):
        return f"{kind} {'right' if bool(value) == bool(truth) else 'wrong'}"
    return kind


def combine_readings(responses, fact_ids):
    """The raw readings of one case-run from its reading responses, in call order. A response that answers every fact
    of the workflow opens a reading; one that answers fewer is the requote of the reading before it and replaces those
    facts (as team._reading does). Per reading: {fact: verdict}, the first answer per fact counting."""
    readings = []
    for conds in responses:
        ids = {c["id"] for c in conds}
        row = {}
        for c in conds:
            row.setdefault(c["id"], c["verdict"])
        if set(fact_ids) <= ids or not readings:
            readings.append(row)
        else:
            readings[-1].update(row)
    return readings


def agreement(verdicts, truth):
    """For the raw verdicts of the readings on one boolean fact: 'all agree wrong' when every reading gives the same
    value (true/false) and it is not the truth; 'all agree right'; otherwise 'not unanimous'."""
    vals = set(verdicts)
    if len(verdicts) and len(vals) == 1 and next(iter(vals)) in ("true", "false"):
        return "all agree right" if (next(iter(vals)) == "true") == bool(truth) else "all agree wrong"
    return "not unanimous"


class Cache:
    """The product's response cache, read only: per key the parsed message content (None if not a JSON object)."""

    def __init__(self, root=CACHE):
        self.root, self.memo, self.missing = Path(root), {}, set()

    def content(self, key):
        if key not in self.memo:
            p = self.root / f"{key}.json"
            if not p.exists():
                self.missing.add(key)
                self.memo[key] = None
                return None
            body = json.loads(json.loads(p.read_text())["body"].strip())
            text = need(body, "choices", 0, "message").get("content") or ""
            try:
                self.memo[key] = json.loads(text) if text.lstrip().startswith("{") else None
            except ValueError:
                self.memo[key] = None
        return self.memo[key]

    def reading(self, key):
        c = self.content(key)
        return c["conditions"] if isinstance(c, dict) and isinstance(c.get("conditions"), list) else None


def truth_of(ref):
    t = {**ref["scenario"], **ref["implicit_flags"]}
    if ref["open_fact"]:
        t[ref["open_fact"]["flag"]] = ref["open_fact"]["true_value"]
    return t


def r3_design(study, design, cache):
    D = study.D["tenancy"]
    table = defaultdict(Counter)        # (role, state, wording) -> category counts
    agree = defaultdict(Counter)        # (role, state) -> {agreement x category}
    nread = Counter()
    for cid in study.cases["tenancy"]:
        ref = D.reference(cid)
        truth = truth_of(ref)
        routing = set(ref["implicit_flags"])
        for e in study.entries[(design, "tenancy")][cid]:
            facts = ((e or {}).get("product_extra") or {}).get("facts") or {}
            fam = ((e or {}).get("plan") or {}).get("family")
            reads = None
            if e is not None and fam == ref["family"]:
                resp = [x for x in (cache.reading(k) for k in dict.fromkeys(e.get("keys") or [])) if x is not None]
                reads = combine_readings(resp, list(facts) or list(ref["fact_states"]))
                nread[len(reads)] += 1
            for f, state in ref["fact_states"].items():
                kind, val = product_value(facts.get(f)) if fam == ref["family"] else ("absent", None)
                cat = fact_category(kind, val, truth[f], state)
                role = "defining event" if f in routing else "branch fact"
                table[(role, state, (ref.get("expression") or {}).get(f, "-"))][cat] += 1
                if reads:
                    a = agreement([r[f] for r in reads if f in r], truth[f]) if all(f in r for r in reads) else "not unanimous"
                    agree[(role, state)][f"{a} / {cat}"] += 1
    rows = [{"role": k[0], "designed_state": k[1], "wording": k[2], "n": sum(v.values()), **dict(sorted(v.items()))}
            for k, v in sorted(table.items())]
    agr = [{"role": k[0], "designed_state": k[1], **dict(sorted(v.items()))} for k, v in sorted(agree.items())]
    wrong_all = sum(v for x in agree.values() for kk, v in x.items() if kk.startswith("all agree wrong"))
    wrong_admitted_all = sum(v for x in agree.values() for kk, v in x.items() if kk == "all agree wrong / admitted wrong")
    adm_wrong = sum(r.get("admitted wrong", 0) for r in rows)
    return {"table": rows, "readings_agreement": agr, "readings_per_case_run": dict(sorted(nread.items())),
            "admitted_wrong": adm_wrong, "presumed_wrong": sum(r.get("presumed wrong", 0) for r in rows),
            "all_readings_agree_on_wrong_value": wrong_all, "admitted_wrong_with_all_readings_agreeing": wrong_admitted_all,
            "fact_claim_runs": sum(r["n"] for r in rows)}


def r3(study, cache):
    out = {d: r3_design(study, d, cache) for d in ("casepath", "casepath_checklist")}
    out["notes"] = [
        "Product value = what the evaluator used: an established fact with verdict 'accepted' (admitted), a presumption, "
        "or nothing (unresolved: no reading gave a value; conflicting: readings gave different values; not accepted; "
        "absent: the case-run was routed to another workflow or failed). Truth = the designed true value "
        "(scenario, defining event, open fact's recorded value). For a designed open fact the right outcome is unresolved.",
        "Readings: the reading responses of each case-run in the response cache (calls whose answer is a 'conditions' "
        "object), combined as team._reading does: a response that answers fewer facts than the workflow has is the "
        "requote of the reading before it. Agreement uses the raw verdicts (true / false / open / not_stated) before the "
        "quotation check.",
        "Theft: the nine changed conditions cannot be mapped to the product's workflow facts from the harness. The "
        "reviewed workflow's facts are rule guards (g001 ...), one per distinct rule condition, and no file of the harness "
        "maps a benchmark condition (PR_...) to guards (analysis/theft_error_origin.py leaves COND_GUARD empty). A mapping "
        "would have to be made by hand from the condition texts, which is a new coding decision; it was not made."]
    return out


# ======================================================================= R4: wrong presumptions
_BUILD = None


def build_module():
    global _BUILD
    if _BUILD is None:
        sys.path.insert(0, str(TMIS / "fresh2" / "tenancy"))
        sys.path.insert(0, str(TMIS / "harness"))
        import build  # noqa: E402  (the fresh2 builder: engine_plan, state_name)
        _BUILD = build
    return _BUILD


def engine_states(ref, true_facts=(), build=None, fact_states=None, attachments=None):
    """Document states of the reference engine (build.engine_plan, exact deferral, under the silence policy) for a claim
    whose facts in true_facts are stated true; fact_states / attachments replace the reference's when given."""
    build = build or build_module()
    states = dict(fact_states or ref["fact_states"])
    for f in true_facts:
        states[f] = "stated_true"
    c = {"claim_id": ref["claim_id"], "family": ref["family"], "fact_states": states,
         "open_value": (ref["open_fact"] or {}).get("true_value")}
    atts = ref["attachments"] if attachments is None else attachments
    plan = build.engine_plan(c, atts)
    by = {a["document_type"]: a for a in atts}
    return {d: build.state_name(r, by.get(d)) for d, r in plan["document_states"].items()}


def subsets_of(xs):
    xs = sorted(xs)
    out = [()]
    for x in xs:
        out += [s + (x,) for s in out]
    return [tuple(sorted(s)) for s in out]


def draw_flips(absent_by_claim, q, rng):
    """One draw: each unmentioned (absent) branch fact of each claim is true with probability q, in sorted order."""
    return {c: tuple(f for f in sorted(fs) if rng.random() < q) for c, fs in sorted(absent_by_claim.items())}


def r4(study, designs=("casepath", "ric", "ric_frontier", "self_consistency", "model_executes_rules")):
    D = study.D["tenancy"]
    refs = {c: D.reference(c) for c in study.cases["tenancy"]}
    absent = {c: [f for f, s in r["fact_states"].items() if s == "absent"] for c, r in refs.items()}
    table = {c: {sub: engine_states(refs[c], sub) for sub in subsets_of(absent[c])} for c in refs}
    q0 = sum(table[c][()] != refs[c]["document_states"] for c in refs)
    if q0:
        raise AssertionError(f"q = 0 does not reproduce {q0} stored references")
    plans = {d: study.plans[(d, "tenancy")] for d in designs}
    for d in designs:
        assert study.load(d, "tenancy")

    def score(flips):
        out = {}
        for d in designs:
            tot = n = 0
            for c in refs:
                ref = {"document_states": table[c][flips[c]]}
                for p in plans[d][c]:
                    tot += s2.ten_row(ref, p)["strict_unsafe"]
                    n += 1
            out[d] = tot / n
        return out
    base = score({c: () for c in refs})
    stored = {d: need(study.design_summary(d, "tenancy"), "measures", "strict_unsafe_per_claim") for d in designs}
    for d in designs:
        assert abs(base[d] - stored[d]) < 1e-9, (d, base[d], stored[d])
    res = {"q0_reproduces_stored_references": True, "claims": len(refs),
           "absent_branch_facts": sum(len(v) for v in absent.values()),
           "claims_with_an_absent_branch_fact": sum(bool(v) for v in absent.values()),
           "claims_whose_reference_can_change": sum(any(table[c][s] != table[c][()] for s in table[c]) for c in refs),
           "q0": base, "by_q": {}}
    for q in R4_QS:
        rng = random.Random(f"{s2.SEED}|R4|{q}")
        per = defaultdict(list)
        changed = []
        for _ in range(R4_DRAWS):
            fl = draw_flips(absent, q, rng)
            changed.append(sum(table[c][fl[c]] != table[c][()] for c in refs))
            sc = score(fl)
            for d in designs:
                per[d].append(sc[d])
            for d in designs[1:]:
                per[f"casepath - {d}"].append(sc["casepath"] - sc[d])
        res["by_q"][str(q)] = {"draws": R4_DRAWS, "claims_with_changed_reference": pct_range(changed),
                               **{k: pct_range(v) for k, v in per.items()}}
    res["method"] = ("Each unmentioned branch fact (fact state 'absent': 139 facts, all false by design) is drawn true with "
                     "probability q, independently, 200 seeded draws per q. For a drawn-true fact the reference is the "
                     "engine's (fresh2/tenancy/build.py engine_plan, exact deferral, silence policy) with that fact stated "
                     "true; every design's stored checklists are kept and rescored with study2.ten_row. Strict unsafe "
                     "errors per claim = mean over claim-runs. Check: with no fact drawn (q = 0) the engine reproduces all "
                     "96 stored references exactly and the rescoring reproduces the stored values.")
    return res


# ======================================================================= R5: theft inference and the unit
def twoway_bootstrap(cells, B, seed):
    """cells: {(story, fact): difference}. A draw resamples stories and facts independently with replacement; the
    statistic is the mean of the cell differences over the drawn story x fact grid (multiplicities kept)."""
    g = random.Random(seed)
    stories = sorted({s for s, _ in cells})
    facts = sorted({f for _, f in cells})
    vals = []
    for _ in range(B):
        S = [g.choice(stories) for _ in stories]
        F = [g.choice(facts) for _ in facts]
        vals.append(sum(cells[(s, f)] for s in S for f in F) / (len(S) * len(F)))
    vals.sort()
    return vals


def signflip_ci(diffs, alpha=0.05, step=0.0005, tol=1e-6):
    """Confidence set by inverting the exact two-sided sign-flip test: the shifts delta for which the test of the
    differences minus delta is not rejected (p >= alpha). Evaluated on a grid of the given step from min(d) to max(d)
    (outside it every shifted difference has one sign, p = 2/2^n), each end refined by bisection to tol.
    Returns (lower, upper, contiguous on the grid)."""
    lo_, hi_ = min(diffs), max(diffs)
    p = lambda dl: s3.signflip_p([x - dl for x in diffs])
    n = int(round((hi_ - lo_) / step)) + 1
    grid = [lo_ + i * step for i in range(n)] + [hi_]
    ok = [p(x) >= alpha for x in grid]
    if not any(ok):
        return None, None, True
    first, last = ok.index(True), len(ok) - 1 - ok[::-1].index(True)
    contiguous = all(ok[first:last + 1])

    def edge(a, b):  # a not accepted, b accepted
        while abs(b - a) > tol:
            m = (a + b) / 2
            a, b = (a, m) if p(m) >= alpha else (m, b)
        return b
    lower = edge(grid[first - 1], grid[first]) if first > 0 else grid[first]
    upper = edge(grid[last + 1], grid[last]) if last < len(grid) - 1 else grid[last]
    return lower, upper, contiguous


def signflip_onesided_ni(diffs, margin):
    """Exact one-sided sign-flip p for non-inferiority (H0: mean difference >= margin): share of sign patterns of
    (d - margin) whose sum is at most the observed sum."""
    import itertools
    x = [d - margin for d in diffs]
    obs = sum(x)
    return sum(sum(s * v for s, v in zip(sg, x)) <= obs + TOL for sg in itertools.product((1, -1), repeat=len(x))) / 2 ** len(x)


R5_CONTRASTS = [("H1", "ric", "signflip"), ("H4 Self-consistency", "self_consistency", "signflip"),
                ("H4 Model executes rules", "model_executes_rules", "signflip"), ("H4 ReAct", "react", "signflip"),
                ("H5 (non-inferiority, margin 0.25)", "ric_frontier", "noninferiority"),
                ("S4a superiority against the frontier model", "ric_frontier", "signflip")]


def r5(study, res3):
    stored = {}
    for h in res3["hypotheses"]:
        for t in h["tests"]:
            if t is not None and h["regime"] == "theft":
                stored[(h["id"], t["b"])] = t
    s4a = next(c["result"] for c in res3["secondary"]["contrasts"] if c["id"] == "S4a")
    out = []
    for name, b, test in R5_CONTRASTS:
        reg = stored[("H5", b)] if name.startswith("H5") else s4a if name.startswith("S4a") else \
            stored[("H1" if name == "H1" else "H4", b)]
        on_a, _ = study.theft_rows("casepath")
        on_b, _ = study.theft_rows(b)
        cell = lambda rows: {k: sum(v) / len(v) for k, v in _group(rows, lambda r: (r["story"], r["condition"]), "errors").items()}
        ca, cb = cell(on_a), cell(on_b)
        cells = {k: ca[k] - cb[k] for k in ca}
        fa, fb = study.clusters("casepath", "theft", "errors"), study.clusters(b, "theft", "errors")
        fd = [fa[k] - fb[k] for k in sorted(fa)]
        sa = s2.by_cluster(on_a, "story", lambda rs: sum(r["errors"] for r in rs) / len(rs))
        sb = s2.by_cluster(on_b, "story", lambda rs: sum(r["errors"] for r in rs) / len(rs))
        sd = [sa[k] - sb[k] for k in sorted(sa)]
        diff = sum(fd) / len(fd)
        assert abs(diff - reg["diff"]) < 1e-9 and abs(sum(sd) / len(sd) - diff) < 1e-9
        tw = twoway_bootstrap(cells, s2.B, f"{s2.SEED}|R5|twoway|{b}")
        lo, hi, contig = signflip_ci(fd)
        slo, shi, scontig = signflip_ci(sd)
        row = {"name": name, "a": "casepath", "b": b, "diff": diff,
               "registered": {"test": reg["test"], "p": reg["p"], "percentile_bootstrap_ci": reg["diff_ci"], "clusters": reg["clusters"]},
               "facts_signflip_p": s3.signflip_p(fd), "stories": len(sd), "stories_nonzero": sum(abs(x) > TOL for x in sd),
               "stories_signflip_p": s3.signflip_p(sd), "stories_min_p": 2 / 2 ** len(sd),
               "twoway_ci": [s2.quantile(tw, 0.025), s2.quantile(tw, 0.975)],
               "facts_inverted_ci": [lo, hi], "facts_inverted_ci_contiguous": contig,
               "stories_inverted_ci": [slo, shi], "stories_inverted_ci_contiguous": scontig,
               "fact_differences": dict(zip(sorted(fa), fd)), "story_differences": dict(zip(sorted(sa), sd))}
        if test == "noninferiority":
            row["facts_signflip_ni_p_onesided"] = signflip_onesided_ni(fd, 0.25)
            row["stories_signflip_ni_p_onesided"] = signflip_onesided_ni(sd, 0.25)
        out.append(row)
    sc = next(r for r in out if r["b"] == "self_consistency")
    d = sorted(sc["fact_differences"].items(), key=lambda kv: kv[1])
    pos = [(k, v) for k, v in d if v > TOL]
    neg = [(k, v) for k, v in d if v < -TOL]
    obs = abs(sum(v for _, v in d))
    import itertools
    vals = [v for _, v in d]
    ext = sum(abs(sum(s * x for s, x in zip(sg, vals))) >= obs - TOL for sg in itertools.product((1, -1), repeat=len(vals)))
    para = (f"The nine changed-fact differences (CasePath minus Self-consistency) are "
            + ", ".join(f"{k} {v:+.3f}" for k, v in d) + f"; mean {sum(vals) / 9:+.3f}. "
            f"{len(neg)} are negative and {len(pos)} positive" + (f" ({', '.join(k for k, _ in pos)})" if pos else "") + ". "
            "The percentile bootstrap resamples these nine values with replacement and asks how the mean varies if the "
            "nine were a sample from a population like themselves: because almost all of them are negative, few resamples "
            "have a mean at or above zero, so the 95% interval "
            f"[{sc['registered']['percentile_bootstrap_ci'][0]:+.3f}, {sc['registered']['percentile_bootstrap_ci'][1]:+.3f}] "
            "excludes zero. The exact test asks a different question: under the null each difference is as likely to have "
            "the opposite sign, and p is the share of the 2^9 = 512 sign patterns whose absolute sum is at least the "
            f"observed {obs:.3f}. {ext} patterns reach it (p = {ext}/512 = {ext / 512:.4f}): the differences are unequal in "
            "size, so flipping the signs of a few small ones still leaves sums as large as the observed one, while the "
            "magnitude-blind percentile interval with nine clusters is known to be too narrow. The inverted sign-flip "
            f"interval, [{sc['facts_inverted_ci'][0]:+.3f}, {sc['facts_inverted_ci'][1]:+.3f}], includes zero, in agreement "
            "with the exact test.")
    return {"contrasts": out, "h4_self_consistency_paragraph": para,
            "method": {"registered": "as stored in study3_results_fresh2_confirm.json (nine changed-fact clusters; percentile "
                                     "cluster-bootstrap interval, 10,000 resamples)",
                       "stories": "exact two-sided sign-flip test over the eight stories (story value = mean over its nine "
                                  "changed-fact pairs and three runs); 2^8 = 256 patterns, smallest p 0.0078",
                       "twoway": "10,000 draws; stories (8) and changed facts (9) resampled independently with replacement; "
                                 "statistic = mean of the cell differences (cell = story x fact, mean over three runs) over "
                                 "the drawn 8 x 9 grid; percentile 2.5-97.5",
                       "inverted": "the set of shifts delta for which the exact two-sided sign-flip test of (differences - "
                                   "delta) gives p >= 0.05; grid of step 0.0005 from the smallest to the largest cluster "
                                   "difference, ends refined by bisection to 1e-6; contiguity checked on the grid",
                       "noninferiority": "for H5 also the exact one-sided sign-flip p of (differences - 0.25), "
                                         "H0: mean difference >= 0.25"}}


def _group(rows, key, field):
    g = defaultdict(list)
    for r in rows:
        g[key(r)].append(r[field])
    return g


# ======================================================================= R6: family-level tenancy differences
def r6(study):
    fam = {}
    for c in study.cases["tenancy"]:
        ref = study.D["tenancy"].reference(c)
        x = fam.setdefault(ref["family_id"], {"family": ref["family"], **{s: 0 for s in SUBSETS}})
        x[next(s for s in SUBSETS if study.in_subset(c, s))] += 1
    a = study.clusters("casepath", "tenancy", "strict_unsafe")
    rows = []
    for f, x in fam.items():
        rows.append({"family_id": f, **x, "casepath": a[f],
                     "ric": study.clusters("ric", "tenancy", "strict_unsafe")[f],
                     "ric_frontier": study.clusters("ric_frontier", "tenancy", "strict_unsafe")[f]})
    for r in rows:
        r["diff_ric"] = r["casepath"] - r["ric"]
        r["diff_ric_frontier"] = r["casepath"] - r["ric_frontier"]
    rows.sort(key=lambda r: (r["diff_ric_frontier"], r["diff_ric"], r["family_id"]))
    return {"families": rows, "measure": "strict unsafe errors per claim, family mean over claims and runs (as H2 and H3)"}


# ======================================================================= R7: full product against checklist only
def same_checklist(p, q):
    norm = lambda x: (sorted((x or {}).get("requests", [])), sorted((x or {}).get("holds", [])), bool((x or {}).get("deferred")))
    return norm(p) == norm(q)


def used_facts(entry):
    out = {}
    for k, f in (((entry or {}).get("product_extra") or {}).get("facts") or {}).items():
        kind, v = product_value(f)
        out[k] = v if kind in ("admitted", "presumed") else None
    return out


def used_findings(entry):
    return {d: j["status"] if j["status"] in ("present", "unusable") and j.get("verdict") == "accepted" else "not on file"
            for d, j in (((entry or {}).get("product_extra") or {}).get("document_judgments") or {}).items()}


def stage_differences(ea, eb, used=None):
    """Which stage differs between two stored product entries of the same case and run: routing (status or routed
    workflow), a fact's value used by the evaluator (only the facts in `used`, those the workflow's conditions name,
    when given), a document's accepted status, needs added by an agent."""
    pa, pb = (ea or {}).get("plan") or {}, (eb or {}).get("plan") or {}
    ra = (((ea or {}).get("product_extra") or {}).get("routing") or {})
    rb = (((eb or {}).get("product_extra") or {}).get("routing") or {})
    out = []
    if pa.get("family") != pb.get("family") or ra.get("status") != rb.get("status"):
        out.append("routing")
    fa, fb = used_facts(ea), used_facts(eb)
    if any(fa.get(k) != fb.get(k) for k in set(fa) | set(fb) if used is None or k in used):
        out.append("fact value")
    da, db = used_findings(ea), used_findings(eb)
    if any(da.get(k, "not on file") != db.get(k, "not on file") for k in set(da) | set(db)):
        out.append("document status")
    if sorted(pa.get("added_requests", []) + pa.get("added_holds", [])) != sorted(pb.get("added_requests", []) + pb.get("added_holds", [])):
        out.append("needs added by an agent")
    return out


def classify_calls(calls):
    """calls: [(agent, is_reading, usd)] in call order for one case-run. Components: the claim reader's brief (its calls
    before its first reading), its first reading, its re-recording after that; the confirming readings (booked to the
    source checker) and the source checker's own check; every other agent as itself."""
    out = defaultdict(lambda: [0, 0.0])
    seen_reading = False
    for agent, is_reading, usd in calls:
        if agent == "claim_reader":
            if is_reading:
                comp = "claim reader: first reading" if not seen_reading else "claim reader: first reading (requote)"
                seen_reading = True
            else:
                comp = "claim reader: brief" if not seen_reading else "claim reader: re-recording after the check"
        elif agent == "source_checker":
            comp = "source checker: confirming readings" if is_reading else "source checker: fact and document check"
        else:
            comp = agent
        out[comp][0] += 1
        out[comp][1] += usd
    return {k: tuple(v) for k, v in out.items()}




def cost_split(study, design, regime, cache, ledger):
    by_key = {}
    for r in ledger:
        by_key.setdefault(r.get("key"), r)
    comp = defaultdict(lambda: [0, 0.0])
    n = aligned = 0
    total_all = 0.0
    for v in study.entries[(design, regime)].values():
        for e in v:
            if e is None:
                continue
            n += 1
            keys = list(dict.fromkeys(e.get("keys") or []))
            total_all += sum(float(by_key[k].get("usd") or 0) for k in keys if k in by_key)
            names = e.get("agents") or []
            if len(keys) != len(names):
                continue
            aligned += 1
            calls = [(a, cache.reading(k) is not None, float(by_key[k].get("usd") or 0) if k in by_key else 0.0)
                     for a, k in zip(names, keys)]
            for c, (cnt, usd) in classify_calls(calls).items():
                comp[c][0] += cnt
                comp[c][1] += usd
    tot = sum(x[1] for x in comp.values())
    return {"case_runs": n, "case_runs_attributed": aligned, "cost_per_case_run_all": total_all / n,
            "attributed_cost_per_attributed_case_run": tot / aligned,
            "components": {c: {"calls_per_attributed_case_run": x[0] / aligned, "cost_per_attributed_case_run": x[1] / aligned,
                               "share_of_attributed_cost": x[1] / tot} for c, x in sorted(comp.items())}}


def r7(study, cache):
    res = {"identical": {}, "stages": {}}
    for regime in ("tenancy", "theft"):
        W, cat = study.evaluator(regime, SPEC["product_evaluator"][regime])
        used = {}
        for c in study.cases[regime]:
            for p in study.plans[("casepath", regime)][c]:
                fam = (p or {}).get("family")
                if fam and fam not in used:
                    used[fam] = set(W._used_facts(cat.get(fam)))
        A, B = study.entries[("casepath", regime)], study.entries[("casepath_checklist", regime)]
        PA, PB = study.plans[("casepath", regime)], study.plans[("casepath_checklist", regime)]
        groups = defaultdict(lambda: [0, 0])
        stages, first = Counter(), Counter()
        examples = []
        for c in study.cases[regime]:
            if regime == "tenancy":
                g = next(s for s in SUBSETS if study.in_subset(c, s))
            else:
                g = {"off": "off text", "on": "changed-fact text", "unres": "unresolved-fact text"}[c.split("-")[1]]
            for r in range(3):
                same = same_checklist(PA[c][r], PB[c][r])
                for k in ("all", g):
                    groups[k][0] += 1
                    groups[k][1] += same
                if not same:
                    fam = (PA[c][r] or {}).get("family")
                    st = stage_differences(A[c][r], B[c][r], used.get(fam))
                    for s in st:
                        stages[s] += 1
                    first[st[0] if st else "none of these"] += 1
                    if len(examples) < 5:
                        examples.append({"case": c, "run": r, "stages": st})
        res["identical"][regime] = {k: {"case_runs": v[0], "identical": v[1], "share": v[1] / v[0]} for k, v in groups.items()}
        res["stages"][regime] = {"differing_case_runs": groups["all"][0] - groups["all"][1],
                                 "stage_differs (not exclusive)": dict(stages),
                                 "first_differing_stage": dict(first),
                                 "examples": examples}
    from_res = json.loads((HERE / "study3_results_fresh2_confirm.json").read_text())
    res["cost"] = {}
    for regime in ("tenancy", "theft"):
        full = cost_split(study, "casepath", regime, cache, study.inputs.ledger("runs/product/ledger_dev_gpt-6-luna.jsonl"))
        chk = cost_split(study, "casepath_checklist", regime, cache, study.inputs.ledger("runs/product/ledger_dev_gpt-6-luna.jsonl"))
        comps = full["components"]
        stored_full = need(from_res, "designs", "casepath", "regimes", regime, "cost", "cost_per_case_run")
        stored_chk = need(from_res, "designs", "casepath_checklist", "regimes", regime, "cost", "cost_per_case_run")
        cc = chk["components"]
        not_made = sorted(k for k in comps if k not in cc)
        shared = sorted(k for k in comps if k in cc)
        res["cost"][regime] = {
            "full": full, "checklist_only": chk,
            "components_the_checklist_only_run_did_not_call": not_made,
            "share_of_full_cost_in_components_checklist_only_did_not_call": sum(comps[k]["share_of_attributed_cost"] for k in not_made),
            "shared_components_cost_full": sum(comps[k]["cost_per_attributed_case_run"] for k in shared),
            "shared_components_cost_checklist_only": sum(cc[k]["cost_per_attributed_case_run"] for k in shared),
            "brief_share_of_full_cost": comps.get("claim reader: brief", {}).get("share_of_attributed_cost", 0.0),
            "registered_can_decide_share_of_attributed": (
                need(from_res, "designs", "casepath", "regimes", regime, "cost", "by_group_per_case_run", "can decide the checklist")
                / (need(from_res, "designs", "casepath", "regimes", regime, "cost", "by_group_per_case_run", "can decide the checklist")
                   + need(from_res, "designs", "casepath", "regimes", regime, "cost", "by_group_per_case_run", "the rest"))),
            "stored_cost_per_case_run": {"full": stored_full, "checklist_only": stored_chk, "ratio": stored_chk / stored_full},
            "registered_groups_per_case_run": need(from_res, "designs", "casepath", "regimes", regime, "cost", "by_group_per_case_run")}
    res["cost_note"] = ("Components are attributed on the case-runs whose stored agent list lines up with their distinct call "
                        "keys (as study3.py does); a call is a reading when its cached answer is a 'conditions' object. The "
                        "registered split books the brief to the claim reader and the confirming readings and the check to "
                        "the source checker, all in 'can decide the checklist'. The checklist-only run makes the routing, "
                        "the first reading, the confirming readings and, where the case has documents, the document finder and a "
                        "documents-only source check; it skips the brief, the process builder and the result checker. On theft "
                        "(one text, no attached document) it called neither the document finder nor the check.")
    return res


# ======================================================================= R8: single prompts on denied-event claims
NOTICE = re.compile(r"(notice|notification|written|writing|\bform\b|termination letter|letter of termination|k[üu]ndigung|"
                    r"mitteilung|formular|schriftlich|anzeige)", re.I)
RECEIPT = re.compile(r"(receiv|arriv|deliver|since|yet|still|already|erhalten|zugestellt|eingetroffen|angekommen|"
                     r"inzwischen|seither|bereits|noch|bekommen|when)", re.I)


def acknowledges_event_open(plan):
    """Rule: the plan acknowledges that the defining event has not (yet) occurred when one of its questions mentions the
    notice in writing (notice, notification, written, form, Kündigung, Mitteilung, schriftlich, Formular, Anzeige) together
    with its receipt or arrival (received, arrived, delivered, since, yet, still, erhalten, zugestellt, inzwischen ...)."""
    return any(NOTICE.search(q) and RECEIPT.search(q) for q in (plan or {}).get("questions", []) or [])


def r8(study):
    out = {}
    den = [c for c in study.cases["tenancy"] if study.in_subset(c, "denied_event")]
    for d, key in (("ric", "B1v2p"), ("ric_frontier", "B1v2p")):
        cnt = Counter()
        ex = []
        for c in den:
            ref = study.D["tenancy"].reference(c)
            for r, p in enumerate(study.plans[(d, "tenancy")][c]):
                if p is None:
                    cnt["failed output"] += 1
                    continue
                ack = acknowledges_event_open(p)
                req = bool(p.get("requests"))
                hold = bool(set(p.get("holds", [])) - set(p.get("requests", [])))
                why = "yes" if ack else ("no (no question at all)" if not p.get("questions") else "no (questions on other matters)")
                cnt[f"acknowledges={why}, requests={'yes' if req else 'no'}, holds={'yes' if hold else 'no'}"] += 1
                cnt["requests the notice itself"] += any(x in p.get("requests", []) for x in ("termination_notice", "rent_increase_notice"))
                if ack and req and len(ex) < 3 and all(e["family"] != ref["family"] or e["case"] != c for e in ex):
                    q = next(q for q in p["questions"] if NOTICE.search(q) and RECEIPT.search(q))
                    ex.append({"case": c, "run": r, "family": ref["family"], "question": q, "requests": len(p["requests"])})
        out[d] = {"claim_runs": len(den) * 3, "counts": dict(sorted(cnt.items())), "examples": ex}
    return {"by_design": out, "rule": " ".join(acknowledges_event_open.__doc__.split()),
            "stored_fields": "The single prompts' stored outputs hold requests, holds, questions, family and 'established'; "
                             "they hold no reasons, so the classification uses the questions only."}


# ======================================================================= R9: reviewed rules and the single prompts on theft
def rule_documents(rule):
    docs = set()
    for f in rule.get("facts", []):
        for cap in f.get("evidence", []):
            for r in cap.get("routes") or []:
                docs |= set(r["documents"])
    for r in (rule.get("confirming_evidence") or {}).get("routes") or []:
        docs |= set(r["documents"])
    return docs


def changed_rules():
    orig = {r["rule_id"]: r for r in json.loads((TMIS / "rule_review" / "bundle" / "rules.json").read_text())["rules"]}
    rev = {r["rule_id"]: r for r in json.loads((TMIS / "rule_review" / "final" / "reviewed_rules.json").read_text())["rules"]}
    out = {}
    for rid in sorted(set(orig) | set(rev)):
        a, b = orig.get(rid), rev.get(rid)
        if a != b:
            out[rid] = sorted(rule_documents(a or {}) | rule_documents(b or {}))
    return out


def r9(study):
    ch = changed_rules()
    touched = defaultdict(list)
    for rid, docs in ch.items():
        for d in docs:
            touched[d].append(rid)
    res = {"changed_rules": {k: len(v) for k, v in ch.items()}, "by_model": {}}
    for model, rev, orig, ledger_rev, ledger_orig in (
            ("gpt-6-luna", "ric", "ric_original", "runs/v2/cp4/ledger_dev_gpt-6-luna.jsonl", "runs/v2/ledger_gpt-6-luna.jsonl"),
            ("gpt-6.1-terra", "ric_frontier", "ric_original_frontier", "runs/v2/cp4/ledger_dev_gpt-6.1-terra.jsonl",
             "runs/v2/ledger_gpt-6.1-terra.jsonl")):
        x = {}
        for tag, d in (("reviewed", rev), ("original", orig)):
            on, un = study.theft_rows(d)
            docs = Counter()
            for r in on:
                for kind, atom in r["atoms"]:
                    docs[(kind, atom)] += 1
            x[tag] = {"errors_per_pair": sum(r["errors"] for r in on) / len(on),
                      "by_fact": study.clusters(d, "theft", "errors"),
                      "unresolved_unchanged_by_fact": {k: sum(bool(r["stable"]) for r in v) / len(v)
                                                       for k, v in _rows_by(un, "condition").items()},
                      "atoms": docs}
        atoms = set(x["reviewed"]["atoms"]) | set(x["original"]["atoms"])
        delta = sorted(((k, x["reviewed"]["atoms"][k] - x["original"]["atoms"][k]) for k in atoms), key=lambda kv: (-abs(kv[1]), kv[0]))
        top = [{"error": {"w": "wrong", "m": "missed"}[k[0]], "change": k[1][0], "document": k[1][1:],
                "reviewed": x["reviewed"]["atoms"][k], "original": x["original"]["atoms"][k], "change_in_count": dv,
                "changed_rules_naming_it": touched.get(k[1][1:], [])} for k, dv in delta[:12]]
        tot = lambda tag, kind: sum(v for k, v in x[tag]["atoms"].items() if k[0] == kind)
        cases = set(study.cases["theft"])
        tokens = {}
        for tag, rel, method in (("reviewed", ledger_rev, "Rv2p"), ("original", ledger_orig, "R")):
            rows = [r for r in study.inputs.ledger(rel) if (r.get("tag") or {}).get("method") == method
                    and (r.get("tag") or {}).get("case") in cases and (method != "R" or (r.get("tag") or {}).get("exp") == "theft")]
            seen, toks = set(), []
            for r in rows:
                if r["key"] in seen:
                    continue
                seen.add(r["key"])
                toks.append(r["prompt_tokens"])
            toks.sort()
            tokens[tag] = {"calls": len(toks), "median_prompt_tokens": s2.quantile(toks, 0.5) if toks else None,
                           "mean_prompt_tokens": sum(toks) / len(toks) if toks else None}
        share = lambda dv: sum(abs(v) for k, v in delta if touched.get(k[1][1:])) / max(1e-12, sum(abs(v) for _, v in delta))
        res["by_model"][model] = {
            "designs": {"reviewed": rev, "original": orig},
            "errors_per_pair": {t: x[t]["errors_per_pair"] for t in x},
            "wrong_atoms": {t: tot(t, "w") for t in x}, "missed_atoms": {t: tot(t, "m") for t in x},
            "by_fact": {f: {"reviewed": x["reviewed"]["by_fact"][f], "original": x["original"]["by_fact"][f],
                            "change": x["reviewed"]["by_fact"][f] - x["original"]["by_fact"][f]} for f in sorted(x["reviewed"]["by_fact"])},
            "unresolved_unchanged_by_fact": {f: {"reviewed": x["reviewed"]["unresolved_unchanged_by_fact"][f],
                                                 "original": x["original"]["unresolved_unchanged_by_fact"][f]}
                                             for f in sorted(x["reviewed"]["unresolved_unchanged_by_fact"])},
            "largest_document_changes": top,
            "share_of_absolute_change_on_documents_named_by_a_changed_rule": share(None),
            "prompt_tokens": tokens}
    res["note"] = ("Error atoms are the frozen scorer's wrong and missed signed changes (+ added, - withdrawn) per "
                   "changed-fact pair-run, counted over 216 pair-runs. A document is 'named by a changed rule' when it is in "
                   "a route of a rule that differs between rule_review/bundle/rules.json and rule_review/final/"
                   "reviewed_rules.json (RECONCILIATION.md lists the changes). Prompt tokens: ledger prompt_tokens of the "
                   "distinct calls on the fresh2 theft texts (Rv2p = reviewed rules, R = original rules).")
    return res


def _rows_by(rows, key):
    g = defaultdict(list)
    for r in rows:
        g[r[key]].append(r)
    return g


# ======================================================================= R10: time per case
def r10(study):
    out = {}
    for d in ("casepath", "casepath_checklist"):
        for regime in ("tenancy", "theft"):
            secs = sorted(e["seconds"] for v in study.entries[(d, regime)].values() for e in v if e is not None)
            out[f"{d}, {regime}"] = {"measure": "elapsed seconds per case-run (stored 'seconds')", "case_runs": len(secs),
                                     "median": s2.quantile(secs, 0.5), "p90": s2.quantile(secs, 0.9)}
    for d, rel_ten, rel_th in (("ric", "runs/v2/ledger_gpt-6-luna.jsonl", "runs/v2/cp4/ledger_dev_gpt-6-luna.jsonl"),
                               ("ric_frontier", "runs/v2/ledger_gpt-6.1-terra.jsonl", "runs/v2/cp4/ledger_dev_gpt-6.1-terra.jsonl")):
        for regime, rel, match in (("tenancy", rel_ten, {"exp": "v2-tenancy", "method": "B1v2p"}), ("theft", rel_th, {"method": "Rv2p"})):
            cases = set(study.cases[regime])
            per = defaultdict(float)
            seen = set()
            for r in study.inputs.ledger(rel):
                t = r.get("tag") or {}
                if t.get("case") not in cases or any(t.get(k) != v for k, v in match.items()) or r["key"] in seen:
                    continue
                seen.add(r["key"])
                per[(t["case"], r["run"])] += float(r["latency_s"])
            secs = sorted(per.values())
            out[f"{d}, {regime}"] = {"measure": "model call latency per case-run (ledger latency_s of its one call; sum if several)",
                                     "case_runs": len(secs), "median": s2.quantile(secs, 0.5), "p90": s2.quantile(secs, 0.9)}
    return {"by_design": out, "note": (
        "Product rows: 'seconds' stored per case-run by harness/study3/worker.py, the wall-clock time of the product "
        "subprocess for one case-run (its HTTP run through the API, all its model calls in sequence, plus waiting for the "
        "API) while 20 case-runs ran in parallel (--workers 20 in RUNLOG.jsonl). Calls answered from the response cache "
        "(shared between settings, and on resumed invocations) take no model time, so these times are lower bounds for "
        "an uncached run. Single-prompt rows: the ledger's latency_s, the duration of the one model call; no stored "
        "time includes preparing the prompt or scoring. The two measures are not the same quantity.")}


# ======================================================================= R11: two-valued and strong Kleene
@contextmanager
def patched(module, name, value):
    old = getattr(module, name)
    setattr(module, name, value)
    try:
        yield
    finally:
        setattr(module, name, old)


def product_fact_states(entry, flags):
    """The product's used fact values as designed fact states for the reference engine: true -> stated_true, false ->
    stated_false, no value -> open (the engine's verdict 'unresolved')."""
    u = used_facts(entry)
    return {f: "open" if u.get(f) is None else ("stated_true" if u[f] else "stated_false") for f in flags}


def r11(study):
    T = study.plans[("casepath", "theft")]
    F = study.plans[("two_valued_false", "theft")]
    n = same = 0
    for c in study.cases["theft"]:
        for r in range(3):
            n += 1
            same += sorted((T[c][r] or {}).get("requests", [])) == sorted((F[c][r] or {}).get("requests", []))
    theft = {"text_runs": n, "identical_requests": same,
             "statement": f"Theft: unresolved = false gives exactly CasePath's requests in {same} of {n} text-runs."}
    build = build_module()
    import casepath_tenancy as ct
    TP = study.plans[("casepath", "tenancy")]
    TF = study.plans[("two_valued_false", "tenancy")]
    cnt = Counter()
    for c in study.cases["tenancy"]:
        ref = study.D["tenancy"].reference(c)
        for r, e in enumerate(study.entries[("casepath", "tenancy")][c]):
            cnt["claim_runs"] += 1
            p = TP[c][r]
            if e is None or p is None or p.get("deferred") or not (e.get("product_extra") or {}).get("facts"):
                cnt["no evaluated checklist (failed or handed over)"] += 1
                continue
            cnt["evaluated"] += 1
            open_ = any(v is None for k, v in used_facts(e).items() if k != "dispute_family")
            cnt["with a workflow fact left without a value"] += open_
            diff_false = not same_checklist(p, TF[c][r])
            cnt["exact differs from unresolved = false"] += diff_false
            fam = p["family"]
            flags = build.FAMILY_FLAGS[fam]
            fs = product_fact_states(e, flags)
            find = used_findings(e)
            atts = [{"artifact_id": a["artifact_id"], "document_type": a["document_type"],
                     "sufficient": find.get(a["document_type"]) == "present", "omitted_field": None}
                    for a in ref["attachments"] if find.get(a["document_type"]) in ("present", "unusable")]
            cnt["product findings without a matching attachment (left out)"] += sum(
                1 for d, s in find.items() if s in ("present", "unusable") and d not in {a["document_type"] for a in ref["attachments"]})
            rr = {**ref, "family": fam}
            ex = engine_states(rr, (), build, fs, atts)
            with patched(build, "plan_from_verified_exact", ct.plan_from_verified):
                kl = engine_states(rr, (), build, fs, atts)
            to_plan = lambda st: {"requests": sorted(d for d, s in st.items() if s in s2.REQ_NOW),
                                  "holds": sorted(d for d, s in st.items() if s == "held")}
            diff_kleene = not same_checklist(to_plan(ex), to_plan(kl))
            cnt["exact differs from strong Kleene (harness, same facts)"] += diff_kleene
            cnt["harness exact equals the product's workflow checklist"] += same_checklist(to_plan(ex), e.get("plan_workflow_only"))
            if open_:
                cnt["of these: exact differs from unresolved = false"] += diff_false
                cnt["of these: exact differs from strong Kleene"] += diff_kleene
    return {"theft": theft, "tenancy": dict(cnt), "method": (
        "(a) the product's stored checklist against 'Two-valued, unresolved = false' (study3.two_valued: the product's own "
        "evaluator at the frozen commit on the same admitted facts and presumptions). (b) The product's evaluator offers "
        "exact deferral only (casepath/process/workflows.py at the frozen commit has no strong Kleene mode), so strong "
        "Kleene uses harness/casepath_tenancy.py (plan_from_verified, the casepath_api engine) on the product's stored "
        "fact values (used value true/false, otherwise unresolved) and its accepted document findings, against the same "
        "harness's exact deferral (plan_from_verified_exact) on the same input, through fresh2/tenancy/build.py "
        "engine_plan. A product finding is passed only where the claim has an attachment of that document type. The row "
        "'harness exact equals the product's workflow checklist' shows how closely the harness reproduces the product.")}


# ======================================================================= report
def fmt(x, nd=3):
    return "–" if x is None else f"{x:.{nd}f}"


def pct(x):
    return "–" if x is None else f"{100 * x:.1f}%"


def table(head, rows):
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(map(str, r)) + " |" for r in rows])


def markdown(res):
    L = {d["key"]: d["label"] for d in SPEC["designs"]}
    md = [f"# Study 3, analyses added after review (data `{DATA}`, run label `{LABEL}`)", "",
          "Generated by `analysis/study3_review.py` with the functions of `analysis/study3.py`. No model calls. "
          "**These analyses were added after review. They are not pre-registered, are not part of ANALYSIS_PLAN_STUDY3.md "
          "and change no hypothesis's status.**", ""]
    # R1
    x = res["R1"]
    md += ["## R1. Claim-level outcomes", "",
           "This shows, per design and subset, how many claim-runs got the whole checklist exactly right, how many had at "
           "least one strict unsafe error and how many at least one wrong hold, and the same at pair level for theft.", ""]
    rows = []
    for k, v in x["tenancy"].items():
        for s, y in v.items():
            rows.append([L[k], s, y["claim_runs"], pct(y.get("exact_share")), pct(y.get("any_unsafe_share")),
                         pct(y.get("any_wrong_hold_share")), y.get("handed_over", "–")])
    md += [table(["Design", "Claims", "Claim-runs", "Exact checklist", "≥1 strict unsafe error", "≥1 wrong hold", "Handed over"], rows), ""]
    md += [table(["Design", "Changed-fact pair-runs", "No wrong or missed change", "Unresolved pair-runs", "Left unchanged"],
                 [[L[k], v["changed_pair_runs"], pct(v["no_wrong_or_missed_share"]), v["unresolved_pair_runs"],
                   pct(v["unresolved_unchanged_share"])] for k, v in x["theft"].items()]), ""]
    md += ["Definitions: " + "; ".join(f"{k}: {v}" for k, v in x["definitions"].items()) + ".", ""]
    # R2
    x = res["R2"]
    md += ["## R2. Tenancy under other mixes of claim types", "",
           "This shows the overall strict unsafe errors per claim of every design when the three subsets are reweighted to "
           "stated prevalences, and CasePath's difference from both Rules-in-context designs under each mix.", "",
           "Subset means per claim-run, reweighted. " + x["method"], ""]
    mixes = list(x["mixes"])
    md += [table(["Design"] + mixes, [[L[k]] + [fmt(v["by_mix"][m]) for m in mixes] for k, v in x["by_design"].items()]), ""]
    md += [table(["Contrast"] + mixes, [[k] + [f"{fmt(v[m]['diff'])} [{fmt(v[m]['ci'][0])}, {fmt(v[m]['ci'][1])}]" for m in mixes]
                                         for k, v in x["contrasts"].items()]), ""]
    md += ["Redraws (a resample without a claim of a weighted subset): " + "; ".join(
        f"{k}, {m}: {v[m]['redraws']}" for k, v in x["contrasts"].items() for m in mixes) + ".", ""]
    # R3
    x = res["R3"]
    md += ["## R3. Fact-level accuracy of the product's values (tenancy)", "",
           "This compares, fact by fact, the value the product used with the designed state of the fact, and counts how "
           "often all readings agreed on a wrong value.", ""] + [f"- {n}" for n in x["notes"]] + [""]
    cols = ["admitted right", "admitted wrong", "presumed right", "presumed wrong", "unresolved", "conflicting", "not accepted", "absent"]
    for d in ("casepath", "casepath_checklist"):
        y = x[d]
        md += [f"**{L[d]}** ({y['fact_claim_runs']} fact x claim-runs; readings per case-run: "
               + ", ".join(f"{k}: {v}" for k, v in y["readings_per_case_run"].items()) + ").", ""]
        md += [table(["Role", "Designed state", "Wording", "n"] + cols,
                     [[r["role"], r["designed_state"], r["wording"], r["n"]] + [r.get(c, 0) for c in cols] for r in y["table"]]), ""]
        md += [f"Admitted wrong values: {y['admitted_wrong']}; wrong presumptions: {y['presumed_wrong']}. All readings "
               f"agreed on a wrong value in {y['all_readings_agree_on_wrong_value']} fact x claim-runs, of which "
               f"{y['admitted_wrong_with_all_readings_agreeing']} were admitted.", ""]
        keys = sorted({k for r in y["readings_agreement"] for k in r if k not in ("role", "designed_state")})
        md += [table(["Role", "Designed state"] + keys, [[r["role"], r["designed_state"]] + [r.get(k, 0) for k in keys]
                                                          for r in y["readings_agreement"]]), ""]
    # R4
    x = res["R4"]
    md += ["## R4. Sensitivity to wrong presumptions (tenancy)", "",
           "This shows how strict unsafe errors per claim change for each design when some unmentioned branch facts are "
           "in truth true, with every stored checklist unchanged.", "", x["method"], "",
           f"Unmentioned branch facts: {x['absent_branch_facts']} in {x['claims_with_an_absent_branch_fact']} claims; "
           f"{x['claims_whose_reference_can_change']} claims have a reference that some flip changes. q = 0 reproduces the "
           f"stored references: {x['q0_reproduces_stored_references']}.", ""]
    keys = [k for k in x["by_q"][str(R4_QS[0])] if k not in ("draws", "claims_with_changed_reference")]
    rows = [[L.get(k, k.replace("casepath - ", "CasePath − ").replace(k.split(' - ')[-1], L.get(k.split(' - ')[-1], ''))),
             fmt(x["q0"].get(k))] + [f"{fmt(x['by_q'][str(q)][k]['mean'])} [{fmt(x['by_q'][str(q)][k]['p2_5'])}, "
                                     f"{fmt(x['by_q'][str(q)][k]['p97_5'])}]" for q in R4_QS] for k in keys]
    md += [table(["Design / difference", "q = 0"] + [f"q = {q}" for q in R4_QS], rows), ""]
    md += ["Claims whose reference changed per draw (mean [2.5, 97.5]): " + "; ".join(
        f"q = {q}: {fmt(x['by_q'][str(q)]['claims_with_changed_reference']['mean'], 1)} "
        f"[{fmt(x['by_q'][str(q)]['claims_with_changed_reference']['p2_5'], 1)}, "
        f"{fmt(x['by_q'][str(q)]['claims_with_changed_reference']['p97_5'], 1)}]" for q in R4_QS) + ".", ""]
    # R5
    x = res["R5"]
    md += ["## R5. Theft inference: sensitivity to the unit", "",
           "This shows each theft contrast under the registered analysis and under stories as clusters, two-way resampling "
           "and a confidence interval from inverting the exact sign-flip test.", ""]
    md += [f"- {k}: {v}" for k, v in x["method"].items()] + [""]
    rows = []
    for c in x["contrasts"]:
        rg = c["registered"]
        rows.append([c["name"], f"{L[c['a']]} − {L[c['b']]}", fmt(c["diff"]),
                     f"p {rg['p']:.4f} ({rg['test']}); [{fmt(rg['percentile_bootstrap_ci'][0])}, {fmt(rg['percentile_bootstrap_ci'][1])}]",
                     f"{c['facts_signflip_p']:.4f}", f"[{fmt(c['facts_inverted_ci'][0])}, {fmt(c['facts_inverted_ci'][1])}]"
                     + ("" if c["facts_inverted_ci_contiguous"] else " (not contiguous)"),
                     f"{c['stories_signflip_p']:.4f} ({c['stories_nonzero']} of {c['stories']} non-zero)",
                     f"[{fmt(c['stories_inverted_ci'][0])}, {fmt(c['stories_inverted_ci'][1])}]",
                     f"[{fmt(c['twoway_ci'][0])}, {fmt(c['twoway_ci'][1])}]",
                     (f"facts {c['facts_signflip_ni_p_onesided']:.4f}; stories {c['stories_signflip_ni_p_onesided']:.4f}"
                      if "facts_signflip_ni_p_onesided" in c else "–")])
    md += [table(["Contrast", "A − B", "Difference", "(a) registered: p; percentile interval", "(a') sign-flip p, 9 facts",
                  "(d) inverted interval, 9 facts", "(b) sign-flip p, 8 stories", "inverted interval, 8 stories",
                  "(c) two-way interval", "non-inferiority, exact one-sided p (margin 0.25)"], rows), ""]
    md += ["**Why H4's Self-consistency interval excludes zero while p = 0.0625.** " + x["h4_self_consistency_paragraph"], ""]
    # R6
    x = res["R6"]
    md += ["## R6. Family-level tenancy differences", "",
           "This lists the 24 family differences behind H2 and H3 with each family's subset composition (data of "
           "`paper/figures/fig_families.pdf`).", "", f"Measure: {x['measure']}.", ""]
    md += [table(["Family", "Dispute", "Ordinary", "Denied", "Open", "CasePath", "Rules in context", "Frontier",
                  "CasePath − RiC", "CasePath − RiC frontier"],
                 [[r["family_id"], r["family"], r["ordinary"], r["denied_event"], r["open_event"], fmt(r["casepath"]),
                   fmt(r["ric"]), fmt(r["ric_frontier"]), fmt(r["diff_ric"]), fmt(r["diff_ric_frontier"])] for r in x["families"]]), ""]
    # R7
    x = res["R7"]
    md += ["## R7. Full product against checklist only", "",
           "This counts the case-runs in which the full product and the checklist-only setting produced identical scored "
           "checklists, names the stage that differs where they do not, and reconciles the cost split.", ""]
    for regime in ("tenancy", "theft"):
        md += [table([f"{regime.capitalize()}: group", "Case-runs", "Identical", "Share"],
                     [[k, v["case_runs"], v["identical"], pct(v["share"])] for k, v in x["identical"][regime].items()]), ""]
        st = x["stages"][regime]
        md += [f"Differing case-runs: {st['differing_case_runs']}. Stage differs (not exclusive): "
               + (", ".join(f"{k} {v}" for k, v in st["stage_differs (not exclusive)"].items()) or "none") + ". First differing stage (order: routing, fact value, document status, added needs): "
               + (", ".join(f"{k} {v}" for k, v in st["first_differing_stage"].items()) or "none") + ".", ""]
    md += [x["cost_note"], ""]
    for regime in ("tenancy", "theft"):
        c = x["cost"][regime]
        md += [f"**{regime.capitalize()}.** Full product: {c['full']['case_runs_attributed']} of {c['full']['case_runs']} case-runs attributed, "
               f"USD {fmt(c['full']['attributed_cost_per_attributed_case_run'], 5)} per attributed case-run. Checklist only: "
               f"{c['checklist_only']['case_runs_attributed']} of {c['checklist_only']['case_runs']}, USD "
               f"{fmt(c['checklist_only']['attributed_cost_per_attributed_case_run'], 5)}.", ""]
        comps = sorted(set(c["full"]["components"]) | set(c["checklist_only"]["components"]))
        md += [table(["Component", "Full: calls", "Full: USD", "Full: share", "Checklist only: calls", "Checklist only: USD", "Not called by checklist only"],
                     [[k, fmt(c["full"]["components"].get(k, {}).get("calls_per_attributed_case_run"), 2),
                       fmt(c["full"]["components"].get(k, {}).get("cost_per_attributed_case_run"), 5),
                       pct(c["full"]["components"].get(k, {}).get("share_of_attributed_cost")),
                       fmt(c["checklist_only"]["components"].get(k, {}).get("calls_per_attributed_case_run"), 2),
                       fmt(c["checklist_only"]["components"].get(k, {}).get("cost_per_attributed_case_run"), 5),
                       "yes" if k in c["components_the_checklist_only_run_did_not_call"] else "no"] for k in comps]), ""]
        md += [f"Stored cost per case-run: full {fmt(c['stored_cost_per_case_run']['full'], 5)}, checklist only "
               f"{fmt(c['stored_cost_per_case_run']['checklist_only'], 5)} (ratio {pct(c['stored_cost_per_case_run']['ratio'])}).", "",
               f"Reconciliation: the registered split put {pct(c['registered_can_decide_share_of_attributed'])} of the full run's cost in 'can "
               f"decide the checklist', including the claim reader's brief ({pct(c['brief_share_of_full_cost'])} of the cost), "
               f"which the checklist-only run does not make. The components the checklist-only run did not call at all ("
               f"{', '.join(c['components_the_checklist_only_run_did_not_call'])}) take "
               f"{pct(c['share_of_full_cost_in_components_checklist_only_did_not_call'])} of the full run's cost. The components "
               f"both make cost USD {fmt(c['shared_components_cost_full'], 5)} per case-run in the full run and "
               f"{fmt(c['shared_components_cost_checklist_only'], 5)} in the checklist-only run, which is why checklist only costs "
               f"{pct(c['stored_cost_per_case_run']['ratio'])} of a full run rather than "
               f"{pct(1 - c['share_of_full_cost_in_components_checklist_only_did_not_call'])}.", ""]
    # R8
    x = res["R8"]
    md += ["## R8. What the single prompts did on denied-event claims", "",
           "This classifies the single prompts' outputs on the 24 denied-event claims by whether they acknowledge that the "
           "notice has not been received and whether they still request documents.", "", x["stored_fields"], "",
           x["rule"], ""]
    for d, y in x["by_design"].items():
        md += [f"**{L[d]}** ({y['claim_runs']} claim-runs): " + "; ".join(f"{k}: {v}" for k, v in y["counts"].items()) + ".", ""]
        md += [f"- {e['family']} ({e['case']}, run {e['run']}, {e['requests']} requests): \"{e['question']}\"" for e in y["examples"]] + [""]
    # R9
    x = res["R9"]
    md += ["## R9. Reviewed against original rules for Rules in context (theft)", "",
           "This compares the single prompt's errors under the original and the reviewed rules by changed fact and by "
           "document, and relates the largest changes to the rules the review changed.", "", x["note"], "",
           "Rules that differ: " + ", ".join(f"{k} ({v} documents)" for k, v in x["changed_rules"].items()) + ".", ""]
    for model, y in x["by_model"].items():
        md += [f"**{model}** ({L[y['designs']['reviewed']]} vs {L[y['designs']['original']]}): errors per pair "
               f"{fmt(y['errors_per_pair']['reviewed'])} vs {fmt(y['errors_per_pair']['original'])}; wrong atoms "
               f"{y['wrong_atoms']['reviewed']} vs {y['wrong_atoms']['original']}; missed atoms {y['missed_atoms']['reviewed']} vs "
               f"{y['missed_atoms']['original']}; prompt tokens (median) {fmt(y['prompt_tokens']['reviewed']['median_prompt_tokens'], 0)} vs "
               f"{fmt(y['prompt_tokens']['original']['median_prompt_tokens'], 0)} ({y['prompt_tokens']['reviewed']['calls']} and "
               f"{y['prompt_tokens']['original']['calls']} calls). Share of the absolute change in error atoms on documents named by a "
               f"changed rule: {pct(y['share_of_absolute_change_on_documents_named_by_a_changed_rule'])}.", ""]
        md += [table(["Changed fact", "Reviewed", "Original", "Change", "Unresolved left unchanged: reviewed", "original"],
                     [[f, fmt(v["reviewed"]), fmt(v["original"]), fmt(v["change"]),
                       pct(y["unresolved_unchanged_by_fact"].get(f, {}).get("reviewed")),
                       pct(y["unresolved_unchanged_by_fact"].get(f, {}).get("original"))] for f, v in y["by_fact"].items()]), ""]
        md += [table(["Error", "Change", "Document", "Reviewed", "Original", "Δ count", "Changed rules naming it"],
                     [[t["error"], t["change"], t["document"][:90], t["reviewed"], t["original"], t["change_in_count"],
                       ", ".join(t["changed_rules_naming_it"]) or "–"] for t in y["largest_document_changes"]]), ""]
    # R10
    x = res["R10"]
    md += ["## R10. Time per case", "", "This gives the time per case-run, median and 90th percentile, as far as the "
           "stored outputs record it.", "", x["note"], ""]
    md += [table(["Design, regime", "Measure", "Case-runs", "Median s", "90th percentile s"],
                 [[k.replace(k.split(",")[0], L[k.split(",")[0]]), v["measure"], v["case_runs"], fmt(v["median"], 1), fmt(v["p90"], 1)]
                  for k, v in x["by_design"].items()]), ""]
    # R11
    x = res["R11"]
    md += ["## R11. Exact deferral against two-valued and strong Kleene evaluation", "",
           "This confirms that on theft treating unresolved facts as false gives CasePath's requests, and counts the tenancy "
           "claim-runs where exact deferral changed the checklist.", "", x["theft"]["statement"], "", x["method"], ""]
    md += [table(["Tenancy count", "Claim-runs"], [[k, v] for k, v in x["tenancy"].items()]), ""]
    md += ["## Inputs", "", f"Files read: {len(res['inputs'])}; response-cache files missing: {res['cache_missing']}.", ""]
    return "\n".join(md)


def main():
    s3.configure(SPEC)
    res3 = json.loads((HERE / f"study3_results_{DATA}_{LABEL}.json").read_text())
    study = s3.Study(SPEC, DATA, LABEL, s3.load_data(DATA))
    for d in SPEC["designs"]:
        for reg in d["regimes"]:
            assert study.load(d["key"], reg), f"{d['key']}/{reg} not loaded"
    cache = Cache()
    res = {"label": LABEL_REVIEW, "added_after_review": True, "preregistered": False, "data": DATA, "run_label": LABEL,
           "statistics": {"bootstrap_resamples": s2.B, "seed": s2.SEED, "r4_draws": R4_DRAWS}}
    for name, fn in (("R1", lambda: r1(study)), ("R2", lambda: r2(study)), ("R3", lambda: r3(study, cache)),
                     ("R4", lambda: r4(study)), ("R5", lambda: r5(study, res3)), ("R6", lambda: r6(study)),
                     ("R7", lambda: r7(study, cache)), ("R8", lambda: r8(study)), ("R9", lambda: r9(study)),
                     ("R10", lambda: r10(study)), ("R11", lambda: r11(study))):
        res[name] = fn()
        print(name, "done", flush=True)
    res["cache_missing"] = len(cache.missing)
    res["inputs"] = dict(sorted(study.inputs.hashes.items()))
    OUT.with_suffix(".json").write_text(json.dumps(res, indent=1, sort_keys=True, ensure_ascii=False, default=_jsonable) + "\n")
    OUT.with_suffix(".md").write_text(markdown(res) + "\n")
    print("written", OUT.with_suffix(".json"), "and", OUT.with_suffix(".md"))
    return res


def _jsonable(x):
    if isinstance(x, Counter):
        return dict(x)
    if isinstance(x, tuple):
        return list(x)
    raise TypeError(type(x))


if __name__ == "__main__":
    main()
