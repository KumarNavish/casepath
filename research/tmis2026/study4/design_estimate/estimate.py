"""Development estimate from Study 3's stored readings; post hoc; not a result.

What would a change to how CasePath combines its three readings buy? Every number here is computed from readings that
are already stored (the product's response cache); no model or network call is made. The combining rules below were
chosen after these data were seen (including the per-reading table of the denied-event claims), and they are scored
on the same data: in-sample, so the numbers are an upper bound on what a redesign would show on new data.

    python3 study4/design_estimate/estimate.py     # writes ESTIMATE.json and ESTIMATE.md next to this file

Reused by import, not re-implemented:
  analysis/study3.py            Study (loading, failed-output rule, theft id mapping, tenancy rows via study2.ten_row,
                                theft rows via study2.theft_row, clusters, run_contrast)
  analysis/study3_feedback.py   F4 machinery: split_readings (readings and requotes), one_reading (admission of one
                                reading by exact quotation with the product's own Evidence.locate at the tested commit),
                                combine_k (the tested combination), plan_with_k (presumptions with the open rule "any",
                                the product's evaluator with exact deferral), case_files, evidence_module, DEFINING
  analysis/study3_review.py     Cache (stored readings), truth_of / fact_category (R3's fact-value table), same_checklist
  study4/baseline_check/analyse.py  spec_with_new (designs A and B), in_sub, ten_block, theft_block, contrast (per-case
                                sign-flip and the registered cluster contrast)
A variant enters plan_with_k by replacing study3_feedback.combine_k for the duration of one call (the function plan_with_k
looks up by name); the evaluator is wrapped only to record the facts it was given (for the wrong-value count).
"""
from __future__ import annotations

import copy
import json
import sys
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
TMIS = HERE.parents[1]
sys.path.insert(0, str(TMIS / "study4" / "baseline_check"))
import analyse as A  # noqa: E402

F, P, s3, s2 = A.F, A.P, A.s3, A.s2
R = F.R
HEADER = "Development estimate from Study 3's stored readings; post hoc; not a result"
DESIGNS = {"casepath_checklist": "CasePath, checklist only, cost-efficient (three runs)",
           "casepath_frontier_checklist": "CasePath, checklist only, frontier (one run)"}
COMPARATORS = {"casepath_checklist": ["hold_prompt"], "casepath_frontier_checklist": ["hold_prompt_frontier", "mer_hold_frontier"]}
CMP_LABEL = {"hold_prompt": "A, cost-efficient", "hold_prompt_frontier": "A, frontier", "mer_hold_frontier": "B, frontier"}
REPORT_SUBSETS = ["all", "S", "O: open branch fact only", "O: denied defining event", "O: open defining event", "ordinary"]
CONTRAST_SUBSETS = ["all", "S", "O: open branch fact only", "O: denied defining event", "O: open defining event"]
SUBSET_SHORT = {"all": "all", "S": "every fact stated (S)", "O: open branch fact only": "open branch fact only",
                "O: denied defining event": "denied event", "O: open defining event": "open event", "ordinary": "ordinary"}

VARIANTS = {
    "V0": ("tested: all three must agree",
           "study3_feedback.combine_k with k = 3, unchanged: a fact's value is admitted only when every one of the three "
           "readings admits it (a value with a quotation found word for word in the files) and they give the same value. "
           "Values that differ make the fact 'conflicting'; anything else leaves it 'unknown'. Presumptions then apply "
           "by the product's rule (workflows.presumed, open rule 'any': a fact that any reading answered 'open' with words "
           "found in the files is raised and left open, and no presumption fills it; nor does one when the first or second "
           "reading admitted a different value)."),
    "V1": ("majority on the defining event only",
           "For the workflow's defining event (the fact of its 'routed' presumption: termination_received, "
           "claim_received; theft has none, so V1 = V0 there): when at least two of the three readings admit the same "
           "value (with a located quotation), that value is admitted, whatever the third reading says. Otherwise, and for "
           "every other fact, as V0."),
    "V2": ("majority on every deciding fact",
           "For every fact the readings decide (all workflow facts except those set by routing): when at least two of the "
           "three readings admit the same value, that value is admitted, whatever the third says (a different value, "
           "'open', 'not stated', or a quotation not found). Otherwise as V0."),
    "V3": ("a quoted denial of the defining event counts",
           "For the defining event: if at least one reading admits false (answer false with a quotation found in the "
           "files) and no reading admits true, the event is admitted false. If one reading admits true and another "
           "admits false, it stays 'conflicting' (unresolved) as in V0. Otherwise as V0; every other fact as V0."),
    "V4": ("V1, and two values outweigh one 'open'",
           "As V1 for the defining event. For every other fact: when two readings admit the same value, no reading admits "
           "a different value, and the remaining reading answered 'open' (with or without words found), that value is "
           "admitted. Difference from the tested open rule 'any': under 'any', one 'open' answer with words found both "
           "prevents agreement and blocks every presumption, so the fact is held even when the other two readings "
           "quote the same value; under V4 that single 'open' is outvoted by two quoted values. A fact with at most one "
           "quoted value keeps the tested rule: any located 'open' still blocks the presumption and the fact is held. "
           "A dissent that is 'not stated' or an unlocated quotation is not changed (as V0)."),
    "V5": ("first reading alone (k = 1)",
           "study3_feedback.combine_k with k = 1: the first reading's admitted values; presumptions by the same rule from "
           "the first reading's 'open' answer. For reference (one reading's cost)."),
}
EXTRA = {
    "V6": ("a denial by two readings counts; every other fact as V4",
           "Chosen after the denied-event reading table (the readings never answered 'open' or 'not stated' on a denied "
           "event; they disagreed only true against false). For the defining event: admitted false when at least two "
           "readings admit false (whatever the third admits); admitted true only when all three admit true (as V0); "
           "otherwise as V0 (conflicting values are held). Asymmetric: a majority for the event's occurrence does not "
           "override a quoted denial. Every other fact: two quoted values outweigh one 'open' (V4's rule)."),
    "V7": ("any quoted denial counts; every other fact as V4",
           "For the defining event: admitted false when at least one reading admits false, even if other readings admit "
           "true (a quoted denial outweighs a quoted occurrence); admitted true only when all three admit true; "
           "otherwise as V0. Every other fact as V4."),
}


# ======================================================================= per-reading rows and the variants
def routed_fact(wf):
    ids = [p["fact"] for p in wf.get("presumptions") or [] if p.get("applies") == "routed"]
    assert len(ids) <= 1, ids
    return ids[0] if ids else None


def admitted(rd, fid):
    """Per reading (first three): the admitted value or None, and the open flag of one_reading (True: open, words
    found; None: open, words not found; False: anything else)."""
    out = []
    for r in rd[:3]:
        s, v, o = r.get(fid, ("unknown", None, False))
        out.append((v if s == "established" else None, o))
    return out


def established(row, v):
    return {"status": "established", "value": v, "agreed": True, "open_readings": row.get("open_readings")}


def majority(adm):
    c = Counter(v for v, _ in adm if v is not None)
    if not c:
        return None
    v, n = c.most_common(1)[0]
    return v if n >= 2 else None


def two_over_open(adm):
    """Two readings admit the same value, none admits another, the rest answered 'open'."""
    vals = [v for v, _ in adm if v is not None]
    if len(vals) < 2 or len(set(map(json.dumps, vals))) != 1:
        return None
    rest = [o for v, o in adm if v is None]
    return vals[0] if rest and all(o in (True, None) for o in rest) else None


def denial_event(base, adm, need):
    vals = [v for v, _ in adm if v is not None]
    if vals.count(False) >= need:
        return established(base, False)
    return base


def make_combine(variant, defining):
    orig = F.combine_k

    def comb(rd, k, fid):
        if variant == "V5":
            return orig(rd, 1, fid)
        base = orig(rd, 3, fid)
        adm = admitted(rd, fid)
        ev = fid == defining
        if variant == "V0":
            return base
        if variant in ("V1", "V4") and ev:
            m = majority(adm)
            return established(base, m) if m is not None else base
        if variant == "V2":
            m = majority(adm)
            return established(base, m) if m is not None else base
        if variant == "V3" and ev:
            vals = [v for v, _ in adm if v is not None]
            return established(base, False) if False in vals and True not in vals else base
        if variant in ("V6", "V7") and ev:
            return denial_event(base, adm, 2 if variant == "V6" else 1)
        if variant in ("V4", "V6", "V7") and not ev:
            m = two_over_open(adm)
            return established(base, m) if m is not None else base
        return base
    return comb


@contextmanager
def combining(variant, defining):
    old = F.combine_k
    F.combine_k = make_combine(variant, defining) if variant != "V0" else old
    try:
        yield
    finally:
        F.combine_k = old


class Recorder:
    """The product's evaluator module, with evaluate() recording the facts and findings it is given."""

    def __init__(self, W):
        self._W, self.last = W, None

    def __getattr__(self, name):
        return getattr(self._W, name)

    def evaluate(self, wf, facts, findings, **kw):
        self.last = (dict(facts), dict(findings))
        return self._W.evaluate(wf, facts, findings, **kw)


def checklist(W, wf, facts, findings):
    ev = W.evaluate(wf, facts, findings, checked=True)
    return {"family": wf["id"], "deferred": False,
            "requests": sorted(r["document"] for r in ev["documents"] if r["required"] == "yes" and r["status"] in {"missing", "unusable"}),
            "holds": sorted(r["document"] for r in ev["documents"] if r["required"] == "depends")}


# ======================================================================= raw answers on the defining event
def raw_kind(answers, locate):
    if not answers:
        return "no answer", None
    if len({(a["verdict"], a.get("value")) for a in answers}) > 1:
        return "answered twice, differently", answers[0].get("quote")
    a = answers[0]
    q = a.get("quote")
    hit = bool(q) and locate(q)
    v = a["verdict"]
    if v in ("true", "false"):
        return f"{v}, quotation {'found' if hit else 'not found'}", q
    if v == "open":
        return f"open, words {'found' if hit else 'not found'}", q
    if v == "not_stated":
        return "not stated", q
    return f"other ({v})", q


# ======================================================================= replay
def replay(study, design, regime, cache, variants, collect):
    EV = F.evidence_module()
    W, cat = study.evaluator(regime, F.SPEC["product_evaluator"][regime])
    Wr = Recorder(W)
    plans = {v: {} for v in variants}
    facts_used = {v: {} for v in variants}
    cnt = Counter()
    for c in study.cases[regime]:
        ev = EV.Evidence(F.case_files(study, regime, c))
        locate = lambda q: any(ev.locate(fid, q) for fid in ev.files)
        for v in variants:
            plans[v][c], facts_used[v][c] = [], []
        for r, e in enumerate(study.entries[(design, regime)][c]):
            stored = study.plans[(design, regime)][c][r]
            fam = ((e or {}).get("plan") or {}).get("family")
            keep = e is None or not fam or (e.get("plan") or {}).get("deferred")
            groups = None
            if not keep:
                wf = cat.get(fam)
                keys = [x for x in dict.fromkeys(e.get("keys") or []) if cache.reading(x) is not None]
                groups = F.split_readings([cache.reading(x) for x in keys], len(wf["facts"]))
                if len(groups) < 3:
                    keep = True
                    cnt[f"{len(groups)} readings in the cache: stored plan kept"] += 1
            if keep:
                for v in variants:
                    plans[v][c].append(stored)
                    facts_used[v][c].append(None)
                cnt["stored plan kept (failed, handed over or not routed)"] += 1 if groups is None else 0
                continue
            defs = {f["id"]: f for f in wf["facts"]}
            rd = [F.one_reading(g, defs, locate) for g, _ in groups]
            defining = routed_fact(wf)
            for v in variants:
                with combining(v, defining):
                    p = F.plan_with_k(e, 3, Wr, wf, rd)
                facts, findings = Wr.last
                if regime == "tenancy":
                    p["requests"] = sorted(set(p["requests"]) | set((e.get("plan") or {}).get("added_requests", [])))
                    p["holds"] = sorted(set(p["holds"]) | set((e.get("plan") or {}).get("added_holds", [])))
                    plans[v][c].append(p)
                else:
                    plans[v][c].append(s3.to_names(p, study.inv))
                # which used values were admitted (vs presumed or routed)
                adm = {}
                with combining(v, defining):
                    for f in defs:
                        row = F.combine_k(rd, 3, f)
                        st = (e["product_extra"]["facts"].get(f) or {})
                        if st.get("by") == "routing" and st.get("status") == "established":
                            adm[f] = "admitted"
                        elif row["status"] == "established" and row.get("agreed") and st.get("verdict") != "rejected":
                            adm[f] = "admitted"
                facts_used[v][c].append({"family": fam, "facts": facts, "findings": findings, "admitted": adm, "rd": rd,
                                         "entry": e, "wf": wf})
            cnt["replayed"] += 1
            if "V0" in variants:
                cnt["V0 reproduces the stored scored checklist"] += R.same_checklist(plans["V0"][c][-1], stored)
            if collect is not None and regime == "tenancy" and defining:
                raw = []
                for g, _ in groups[:3]:
                    raw.append(raw_kind([a for a in g if a["id"] == defining], locate))
                collect.append({"case": c, "run": r, "defining": defining, "raw": raw, "rd": rd, "family": fam})
    return plans, facts_used, dict(cnt)


# ======================================================================= scoring
def variant_spec(spec, design, vkeys):
    base = next(d for d in spec["designs"] if d["key"] == design)
    for v in vkeys:
        d = copy.deepcopy(base)
        d["key"] = f"{design}#{v}"
        d["label"] = f"{base['label']}, {v}"
        spec["designs"].append(d)


def install(study, design, v, regime, plans):
    key = f"{design}#{v}"
    assert study.load(key, regime), (key, regime)
    study.plans[(key, regime)] = plans
    study._rows.pop((key, regime), None)
    return key


def fact_values(study, design, used):
    """R3's table for the values the evaluator was given: per designed fact x claim-run, admitted / presumed right or
    wrong against the designed value (R.truth_of, R.fact_category). Routing fact excluded (not in fact_states)."""
    D = study.D["tenancy"]
    tab = Counter()
    by_state = defaultdict(Counter)
    for c in study.cases["tenancy"]:
        ref = D.reference(c)
        truth = R.truth_of(ref)
        for u in used[c]:
            for f, state in ref["fact_states"].items():
                if u is None or u["family"] != ref["family"]:
                    cat_ = "absent"
                else:
                    val = u["facts"].get(f)
                    if val is None:
                        cat_ = "unresolved"
                    else:
                        kind = "admitted" if u["admitted"].get(f) else "presumed"
                        cat_ = R.fact_category(kind, val, truth[f], state)
                tab[cat_] += 1
                by_state[state][cat_] += 1
    return {"fact_claim_runs": sum(tab.values()), **dict(sorted(tab.items())),
            "by_designed_state": {k: dict(sorted(v.items())) for k, v in sorted(by_state.items())}}


def ten_summary(study, key):
    rows = study.tenancy_rows(key)
    return {s: A.ten_block([r for r in rows if A.in_sub(study, s, r["case"])]) for s in REPORT_SUBSETS}


def theft_summary(study, key):
    on, un = study.theft_rows(key)
    return A.theft_block(on, un)


def contrasts(study, a, b):
    out = []
    ra, rb = study.tenancy_rows(a), study.tenancy_rows(b)
    for s in CONTRAST_SUBSETS:
        fa = [r for r in ra if A.in_sub(study, s, r["case"])]
        fb = [r for r in rb if A.in_sub(study, s, r["case"])]
        for m in ("strict_unsafe", "all_dev"):
            out.append({"regime": "tenancy", "subset": s, "measure": m,
                        **A.contrast(study, fa, fb, "case", m, "cluster", f"S4DE|ten|{a}|{b}|{s}|{m}")})
    (ona, una), (onb, unb) = study.theft_rows(a), study.theft_rows(b)
    for m, xa, xb in (("errors", ona, onb), ("stable", una, unb), ("premature", una, unb)):
        out.append({"regime": "theft", "subset": "changed-fact pairs" if m == "errors" else "unresolved pairs", "measure": m,
                    **A.contrast(study, xa, xb, "pair_id", m, "condition", f"S4DE|th|{a}|{b}|{m}")})
    return out


# ======================================================================= what no combining rule can remove
def designed_value(ref, f):
    if ref["fact_states"].get(f) == "open":
        return None
    return R.truth_of(ref)[f]


def designed_findings(ref):
    m = {"supplied_sufficient": "present", "supplied_insufficient": "unusable"}
    return {d: {"status": m[s], "verdict": "accepted"} for d, s in ref["document_states"].items() if s in m}


def oracle_facts(W, wf, u, ref):
    """The best any combining rule could do with these readings: per fact the designed outcome when some reading
    supports it (a reading admitted the designed value; for a designed open fact, a reading answered 'open' or two
    readings admitted different values; for a fact designed absent or unmentioned, the workflow's presumption when one
    applies to it, else a reading's admitted value), otherwise the value the tested product used. Routing facts as
    stored. Returns (facts, facts whose designed outcome no reading supports)."""
    rd = u["rd"]
    pres = {p["fact"]: p["value"] for p in wf.get("presumptions") or []}
    facts, unsupported = dict(u["facts"]), []
    stored = u["entry"]["product_extra"]["facts"]
    for f in (x["id"] for x in wf["facts"]):
        s = stored.get(f) or {}
        if s.get("by") == "routing" and s.get("status") == "established":
            continue
        if f not in ref["fact_states"]:
            continue
        want = designed_value(ref, f)
        adm = admitted(rd, f)
        vals = [v for v, _ in adm if v is not None]
        state = ref["fact_states"][f]
        if state == "open":
            ok = any(o is not None and o is not False for _, o in adm) or any(o is None for _, o in adm) or len(set(map(json.dumps, vals))) > 1
        elif state in ("absent", "unmentioned"):
            ok = want in vals or pres.get(f) == want
        else:
            ok = want in vals
        if ok:
            facts[f] = want
        else:
            unsupported.append(f)
    return facts, unsupported


def residual(study, design, used_v0):
    """Sequential attribution of the tested product's tenancy deviations (all deviations, per document):
    (0) tested; (1) best combining rule (oracle_facts); (2) every fact at its designed value (what remains after (1)
    because no reading supported the designed outcome is 'readings all wrong'); (3) also the designed document findings
    (the change is 'document judgments'); what remains after (3) is the evaluator and workflow against the reference.
    Claim-runs routed to another family, failed or not replayed keep their stored plan at every step ('routing / no
    replay')."""
    D = study.D["tenancy"]
    W, _ = study.evaluator("tenancy", F.SPEC["product_evaluator"]["tenancy"])
    tot = Counter()
    per_kind = defaultdict(Counter)
    unsupported_facts = Counter()
    for c in study.cases["tenancy"]:
        ref = D.reference(c)
        sub = P.subset_of(study, c)[1] or "S"
        for r, u in enumerate(used_v0[c]):
            stored = study.plans[(design, "tenancy")][c][r]
            s0 = R.scored(ref, stored)
            if u is None or u["family"] != ref["family"]:
                why = "routing (another family) or no replay"
                tot[why] += s0["all_dev"]
                per_kind[sub][why] += s0["all_dev"]
                continue
            wf = u["wf"]
            p0 = checklist(W, wf, u["facts"], u["findings"])
            of, unsup = oracle_facts(W, wf, u, ref)
            unsupported_facts.update(f"{'defining event' if f == routed_fact(wf) else 'branch fact'} / {ref['fact_states'][f]}" for f in unsup)
            p1 = checklist(W, wf, of, u["findings"])
            df = dict(of)
            for f in ref["fact_states"]:
                if f in {x["id"] for x in wf["facts"]}:
                    df[f] = designed_value(ref, f)
            p2 = checklist(W, wf, df, u["findings"])
            p3 = checklist(W, wf, df, designed_findings(ref))
            d0 = R.scored(ref, p0)["all_dev"]
            d1, d2, d3 = (R.scored(ref, p)["all_dev"] for p in (p1, p2, p3))
            for k, x in (("tested", d0), ("best combining rule", d1), ("facts as designed", d2), ("facts and findings as designed", d3)):
                tot[k] += x
                per_kind[sub][k] += x
    out = {"steps": dict(tot), "by_subset": {k: dict(v) for k, v in sorted(per_kind.items())},
           "facts_no_reading_supports": dict(sorted(unsupported_facts.items()))}
    t = tot
    out["attribution"] = {
        "removable by a combining rule (tested - best rule)": t["tested"] - t["best combining rule"],
        "readings all wrong (best rule - facts as designed)": t["best combining rule"] - t["facts as designed"],
        "document judgments (facts as designed - also findings as designed)": t["facts as designed"] - t["facts and findings as designed"],
        "evaluator / workflow against the reference (remaining)": t["facts and findings as designed"],
        "routing (another family) or no replay": t["routing (another family) or no replay"],
        "total tested deviations": t["tested"] + t["routing (another family) or no replay"]}
    return out


# ======================================================================= denied-event reading table
def denied_table(study, items):
    D = study.D["tenancy"]
    per = Counter()
    pattern = Counter()
    combos = Counter()
    examples = defaultdict(list)
    n = 0
    for it in items:
        if P.subset_of(study, it["case"])[1] != "O: denied defining event":
            continue
        ref = D.reference(it["case"])
        if it["family"] != ref["family"]:
            continue
        n += 1
        kinds = []
        for gi, (k, q) in enumerate(it["raw"]):
            kinds.append(k)
            per[k] += 1
            if q and len(examples[k]) < 3 and q not in [x["quote"] for x in examples[k]]:
                examples[k].append({"claim": it["case"], "run": it["run"], "reading": gi + 1, "quote": q})
        pattern[" | ".join(sorted(kinds))] += 1
        adm = admitted(it["rd"], it["defining"])
        nf = sum(v is False for v, _ in adm)
        nt = sum(v is True for v, _ in adm)
        no = sum(o is True for _, o in adm)
        combos[f"quoted false {nf}, quoted true {nt}, open with words found {no}"] += 1
    return {"claim_runs": n, "readings": dict(per.most_common()), "patterns": dict(pattern.most_common()),
            "admitted_counts": dict(combos.most_common()), "examples": dict(examples)}


# ======================================================================= main
def main():
    spec = A.spec_with_new()
    allv = list(VARIANTS) + list(EXTRA)
    for d in DESIGNS:
        variant_spec(spec, d, allv)
    s3.configure(spec)
    study = s3.Study(spec, "fresh2", "confirm", s3.load_data("fresh2"))
    for d in list(DESIGNS) + ["hold_prompt", "hold_prompt_frontier", "mer_hold_frontier"]:
        for reg in ("tenancy", "theft"):
            assert study.load(d, reg), (d, reg)
    cache = R.Cache()
    res = {"header": HEADER, "posthoc": True, "in_sample": True,
           "note": ("The combining rules were chosen after these data (and the denied-event reading table) were seen and "
                    "are scored on the same data: the numbers are an upper bound on what a redesign would show on new "
                    "data. No reference answer is used by any rule; reference answers are used only to score."),
           "variants": {k: {"name": a, "rule": b} for k, (a, b) in {**VARIANTS, **EXTRA}.items()},
           "designs": {}, "checks": {}}
    stored_r3 = json.loads((TMIS / "analysis" / "study3_review.json").read_text())
    for d, label in DESIGNS.items():
        out = {"label": label, "tenancy": {}, "theft": {}, "fact_values": {}, "contrasts": {}}
        items = []
        used_all = {}
        for reg in ("tenancy", "theft"):
            plans, used, cnt = replay(study, d, reg, cache, allv, items if reg == "tenancy" else None)
            res["checks"][f"{d}/{reg}"] = cnt
            for v in allv:
                key = install(study, d, v, reg, plans[v])
                if reg == "tenancy":
                    out["tenancy"][v] = ten_summary(study, key)
                    out["fact_values"][v] = fact_values(study, d, used[v])
                else:
                    out["theft"][v] = theft_summary(study, key)
            if reg == "tenancy":
                used_all = used
        out["stored_tested"] = {"tenancy": ten_summary(study, d)["all"], "theft": theft_summary(study, d)}
        if d == "casepath_checklist":
            r3 = (stored_r3.get("R3") or {}).get(d) or {}
            res["checks"][f"{d}/R3 admitted wrong (stored review) vs V0"] = [r3.get("admitted_wrong"), out["fact_values"]["V0"].get("admitted wrong", 0)]
            res["checks"][f"{d}/R3 presumed wrong (stored review) vs V0"] = [r3.get("presumed_wrong"), out["fact_values"]["V0"].get("presumed wrong", 0)]
        out["denied_event_readings"] = denied_table(study, items)
        out["residual"] = residual(study, d, used_all["V0"])
        for v in allv:
            key = f"{d}#{v}"
            cs = {}
            if v != "V0":
                cs["V0"] = contrasts(study, key, f"{d}#V0")
            for b in COMPARATORS[d]:
                cs[b] = contrasts(study, key, b)
            out["contrasts"][v] = cs
        out["comparators"] = {b: {"tenancy": ten_summary(study, b), "theft": theft_summary(study, b)} for b in COMPARATORS[d]}
        res["designs"][d] = out
    res["inputs"] = dict(sorted(study.inputs.hashes.items()))
    (HERE / "ESTIMATE.json").write_text(json.dumps(res, indent=1, sort_keys=True, ensure_ascii=False, default=float) + "\n")
    (HERE / "ESTIMATE.md").write_text(markdown(res) + "\n")
    print("written", HERE / "ESTIMATE.json", "and", HERE / "ESTIMATE.md")


# ======================================================================= markdown
def f2(x):
    return "-" if x is None else f"{x:.2f}"


def pv(p):
    return "-" if p is None else f"{p:.3f}" if p >= 0.001 else "<0.001"


def table(head, rows):
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(map(str, r)) + " |" for r in rows]


def markdown(res):
    md = [f"# {HEADER}", "",
          "**Post hoc and in-sample.** The combining rules below were chosen after Study 3's stored readings (including "
          "the denied-event reading table) were seen and are scored on the same data, so every number is an upper "
          "bound on what a redesign would show on new data. No model or network call; nothing here is a result. "
          "Produced by `estimate.py`; all numbers are in `ESTIMATE.json`.", "",
          "Each variant recombines the three stored readings of each case-run of the checklist-only product and "
          "re-runs the product's own evaluator at the tested commit (routing and document findings as stored). "
          "Scoring is Study 3's registered scoring (via `study4/baseline_check/analyse.py`). No rule uses a reference "
          "answer.", "", "## Variants", ""]
    for k, v in res["variants"].items():
        md.append(f"- **{k} {v['name']}.** {v['rule']}")
    md += ["", "## Checks", ""]
    for k, v in res["checks"].items():
        md.append(f"- {k}: {json.dumps(v)}")
    for d, out in res["designs"].items():
        md += ["", f"## {out['label']}", ""]
        dt = out["denied_event_readings"]
        md += [f"### What the readings answered on the defining event, denied-event claims ({dt['claim_runs']} claim-runs routed to the right family)", ""]
        md += table(["answer of one reading", "readings"], list(dt["readings"].items()))
        md += ["", "Per claim-run (admitted answers):", ""]
        md += table(["admitted answers of the three readings", "claim-runs"], list(dt["admitted_counts"].items()))
        md += ["", "Examples (verbatim quotations):", ""]
        for k, ex in dt["examples"].items():
            for e in ex:
                md.append(f"- *{k}* ({e['claim']}, run {e['run']}, reading {e['reading']}): \"{e['quote']}\"")
        md += ["", "### Tenancy (96 claims) and theft (128 texts)", "",
               "Tenancy: strict unsafe errors / all deviations per claim-run. Theft: wrong + missed changes per pair; "
               "unresolved pairs left unchanged / changed prematurely. Wrong values: designed facts x claim-runs given "
               "an admitted (or presumed) value that is not the designed one.", ""]
        rows = []
        for v in res["variants"]:
            t = out["tenancy"][v]
            th = out["theft"][v]
            fv = out["fact_values"][v]
            rows.append([v] + [f"{f2(t[s]['strict_unsafe'])} / {f2(t[s]['all_dev'])}" for s in REPORT_SUBSETS] +
                        [f2(t["all"]["spurious_hold_per_claim"]), f2(t["all"]["held_req_per_claim"]),
                         f2(t["all"]["correct_hold_share"]),
                         f"{f2(th['errors_per_pair'])} ({f2(th['wrong_per_pair'])} + {f2(th['missed_per_pair'])})",
                         f"{f2(th['unchanged_share'])} / {f2(th['premature_share'])}",
                         f"{fv.get('admitted wrong', 0)} / {fv.get('presumed wrong', 0)} of {fv['fact_claim_runs']}"])
        for b, cb in out["comparators"].items():
            t, th = cb["tenancy"], cb["theft"]
            rows.append([CMP_LABEL[b]] + [f"{f2(t[s]['strict_unsafe'])} / {f2(t[s]['all_dev'])}" for s in REPORT_SUBSETS] +
                        [f2(t["all"]["spurious_hold_per_claim"]), f2(t["all"]["held_req_per_claim"]), f2(t["all"]["correct_hold_share"]),
                         f"{f2(th['errors_per_pair'])} ({f2(th['wrong_per_pair'])} + {f2(th['missed_per_pair'])})",
                         f"{f2(th['unchanged_share'])} / {f2(th['premature_share'])}", "-"])
        md += table(["variant"] + [SUBSET_SHORT[s] for s in REPORT_SUBSETS] +
                    ["spurious holds", "held required now", "correct-hold share", "theft errors (wrong + missed)",
                     "unresolved: unchanged / premature", "admitted / presumed wrong values"], rows)
        md += ["", "### Paired contrasts (variant minus comparator; difference of per-case means; p: sign-flip over cases / over registered clusters)", ""]
        crow = []
        for v, cs in out["contrasts"].items():
            for b, lst in cs.items():
                for c in lst:
                    if c["regime"] == "tenancy" and c["subset"] not in ("all", "O: denied defining event", "O: open branch fact only", "S"):
                        continue
                    if c["regime"] == "theft" and c["measure"] != "errors":
                        continue
                    crow.append([v, "V0" if b == "V0" else CMP_LABEL[b], c["regime"], SUBSET_SHORT.get(c["subset"], c["subset"]), c["measure"],
                                 f"{c['a_value']:.2f} vs {c['b_value']:.2f}", f"{c['diff_case_mean']:+.2f}",
                                 f"{c['a_lower_cases']}/{c['a_higher_cases']}", pv(c["p_cases"]), pv(c["p_clusters"])])
        md += table(["variant", "against", "regime", "subset", "measure", "values", "difference", "cases lower/higher", "p cases", "p clusters"], crow)
        rs = out["residual"]
        md += ["", "### What no combining rule can remove (tested product, tenancy, all deviations, counted per document)", "",
               "Sequential: tested -> best combining rule (per fact the designed outcome wherever some reading supports "
               "it) -> every fact at its designed value -> also the designed document findings. Claim-runs routed to "
               "another family (or not replayed) keep their stored plan.", ""]
        md += table(["part", "deviations"], list(rs["attribution"].items()))
        md += ["", "Steps by subset:", ""]
        md += table(["subset"] + ["tested", "best combining rule", "facts as designed", "facts and findings as designed", "routing (another family) or no replay"],
                    [[k] + [v.get(x, 0) for x in ("tested", "best combining rule", "facts as designed", "facts and findings as designed", "routing (another family) or no replay")]
                     for k, v in rs["by_subset"].items()])
        md += ["", "Facts whose designed outcome no reading supports (fact x claim-run): " + json.dumps(rs["facts_no_reading_supports"])]
    return "\n".join(md)


if __name__ == "__main__":
    main()
