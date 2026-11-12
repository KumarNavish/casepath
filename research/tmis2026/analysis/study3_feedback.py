"""Study 3, analyses asked for by outside feedback on the paper (F1-F5). POST HOC: not part of ANALYSIS_PLAN_STUDY3.md,
decided after the results were known; every number here is descriptive and changes no hypothesis's status. No model
calls, no network.

    python3 study3_feedback.py                                  # writes study3_feedback.json and study3_feedback.md
    python3 study3_feedback.py --alt-reference REF.json [...]   # F5: also score every design against REF.json
                                                                  (one or more files; written into the same outputs)

Everything is read from stored outputs through analysis/study3.py (Study: loading, derivations, failed-output rule,
scoring, clusters, contrasts, the fresh2 guard) and analysis/study3_review.py (claim outcomes, the response cache and
its readings, the product's used values and findings, the exact one-sided sign-flip test), imported, not copied.
F4 (i) also reads the product package at the tested commit (its evaluator, presumptions and quotation check,
casepath/read/evidence.py), extracted read-only by study3.package_dir. A missing key raises; nothing is filled in.

F1  Two kinds of file. Tenancy: type S (nothing open, defining event not denied) and type O (a fact raised and left
    open, or the defining event denied or left open), from the reference's designed fact states. Theft: S =
    changed-fact pairs, O = unresolved-fact pairs. Every design on both; CasePath against the baselines, descriptive.
F2  Expected strict unsafe errors (and all deviations) per claim as a straight line in the share q of type-O claims;
    crossovers; family-bootstrap bands for CasePath and the frontier single prompt (figure: fig_feedback.py).
F3  The five hypotheses under the frozen order, the final draft's order, the first draft's order (with its tenancy
    non-inferiority hypothesis, margin 0.10, computed from stored outputs) and Holm's correction.
F4  Error against cost: CasePath with the first k = 1, 2, 3 readings of the stored checklist-only runs, and
    Self-consistency with m = 1 ... 15 of the 15 stored samples; budget-matched contrasts.
F5  Re-scoring hook: every design against an alternative tenancy reference.
"""
from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMIS = HERE.parent
sys.path.insert(0, str(HERE))
import study3 as s3  # noqa: E402
import study3_review as R  # noqa: E402

s2 = s3.s2
DATA, LABEL = "fresh2", "confirm"
OUT = HERE / "study3_feedback"
LABEL_POSTHOC = "POST HOC (outside feedback): not part of ANALYSIS_PLAN_STUDY3.md; descriptive"
SPEC = R.SPEC
TOL = 1e-12
ALPHA = SPEC["statistics"]["alpha"]
TEN_BASELINES = ("casepath_checklist", "ric", "self_consistency", "model_executes_rules", "react", "ric_frontier")
THEFT_BASELINES = ("casepath_checklist", "core", "ric", "self_consistency", "model_executes_rules", "react", "ric_original",
                   "ric_frontier", "ric_original_frontier")
LINE_DESIGNS = ("casepath", "ric", "ric_frontier", "self_consistency", "model_executes_rules")
SC_M = (1, 3, 5, 7, 9, 11, 13, 15)
Q_GRID = [i / 100 for i in range(101)]
STATES = ("required_now", "held", "not_needed", "supplied_sufficient", "supplied_insufficient")


def need(d, *path):
    return R.need(d, *path)


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs)


# ======================================================================= F1: two kinds of file
def claim_type(ref):
    """'O' when the reference's designed fact states hold a fact raised and left open, or the defining event is denied
    (implicit flag false) or left open; otherwise 'S' (every deciding fact stated or unmentioned, the defining event
    true: stated or unmentioned and presumed)."""
    if any(s == "open" for s in ref["fact_states"].values()):
        return "O"
    if any(v is False for v in (ref.get("implicit_flags") or {}).values()):
        return "O"
    return "S"


def type_summary(rows):
    """Claim-run means and family means (a family's value: the mean over its claim-runs of this type; the type's value:
    the mean over families with at least one such claim) of strict unsafe errors, all deviations and the exact share."""
    if not rows:
        return {"claim_runs": 0}
    ex = [R.claim_outcome(r)["exact"] for r in rows]
    fam = defaultdict(list)
    for r, e in zip(rows, ex):
        fam[r["cluster"]].append((r["strict_unsafe"], r["all_dev"], e))
    fm = lambda i: mean(mean(x[i] for x in v) for v in fam.values())
    return {"claim_runs": len(rows), "claims": len({r["case"] for r in rows}), "families": len(fam),
            "strict_unsafe_claim_run_mean": mean(r["strict_unsafe"] for r in rows),
            "all_dev_claim_run_mean": mean(r["all_dev"] for r in rows), "exact_share_claim_run": mean(ex),
            "strict_unsafe_family_mean": fm(0), "all_dev_family_mean": fm(1), "exact_share_family_mean": fm(2)}


def type_clusters(rows, field):
    return s2.by_cluster(rows, "cluster", lambda rs: mean(r[field] for r in rs))


def contrast(fa, fb, name, hib=False):
    c = s3.run_contrast(fa, fb, name, hib, "signflip")
    return {k: c[k] for k in ("a_value", "b_value", "diff", "diff_ci", "clusters", "nonzero_clusters", "p", "min_p", "favours")}


def f1(study):
    D = study.D["tenancy"]
    types = {c: claim_type(D.reference(c)) for c in study.cases["tenancy"]}
    cnt = Counter(types.values())
    assert sum(cnt.values()) == len(types) and set(cnt) <= {"S", "O"}
    detail = Counter()
    for c, t in types.items():
        ref = D.reference(c)
        detail[(t, "open fact" if ref["open_fact"] else "defining event denied" if any(v is False for v in ref["implicit_flags"].values())
                else "nothing open or denied")] += 1
    ten = {"counts": dict(cnt), "partition_checked": True, "composition": {f"{k[0]}: {k[1]}": v for k, v in sorted(detail.items())},
           "by_design": {}, "contrasts": {}}
    for d in SPEC["designs"]:
        if "tenancy" not in d["regimes"]:
            continue
        rows = study.tenancy_rows(d["key"])
        ten["by_design"][d["key"]] = {t: type_summary([r for r in rows if types[r["case"]] == t]) for t in ("S", "O")}
    for b in TEN_BASELINES:
        out = {}
        for t in ("S", "O"):
            ra = [r for r in study.tenancy_rows("casepath") if types[r["case"]] == t]
            rb = [r for r in study.tenancy_rows(b) if types[r["case"]] == t]
            out[t] = {m: contrast(type_clusters(ra, m), type_clusters(rb, m), f"F1|ten|{b}|{t}|{m}") for m in ("strict_unsafe", "all_dev")}
            ea = s2.by_cluster(ra, "cluster", lambda rs: mean(R.claim_outcome(r)["exact"] for r in rs))
            eb = s2.by_cluster(rb, "cluster", lambda rs: mean(R.claim_outcome(r)["exact"] for r in rs))
            out[t]["exact_share"] = contrast(ea, eb, f"F1|ten|{b}|{t}|exact", hib=True)
        ten["contrasts"][b] = out
    theft = {"counts": {"S (changed-fact pairs)": sum(p["kind"] == "on" for p in study.pairs),
                        "O (unresolved-fact pairs)": sum(p["kind"] == "unresolved" for p in study.pairs)},
             "by_design": {}, "contrasts": {}}
    for d in SPEC["designs"]:
        if "theft" not in d["regimes"]:
            continue
        on, un = study.theft_rows(d["key"])
        theft["by_design"][d["key"]] = {
            "S": {"pair_runs": len(on), "errors_per_pair": mean(r["errors"] for r in on),
                  "errors_fact_mean": mean(study.clusters(d["key"], "theft", "errors").values())},
            "O": {"pair_runs": len(un), "unchanged_share": mean(bool(r["stable"]) for r in un),
                  "premature_share": mean(bool(r["premature"]) for r in un), "held_share": mean(bool(r["held"]) for r in un)}}
    _, una = study.theft_rows("casepath")
    for b in THEFT_BASELINES:
        _, unb = study.theft_rows(b)
        cl = lambda rows, f: s2.by_cluster(rows, "condition", lambda rs: mean(bool(r[f]) for r in rs))
        theft["contrasts"][b] = {
            "S errors": contrast(study.clusters("casepath", "theft", "errors"), study.clusters(b, "theft", "errors"), f"F1|th|{b}|S"),
            "O unchanged share": contrast(cl(una, "stable"), cl(unb, "stable"), f"F1|th|{b}|O|stable", hib=True),
            "O premature share": contrast(cl(una, "premature"), cl(unb, "premature"), f"F1|th|{b}|O|premature")}
    return {"tenancy": ten, "theft": theft, "types": types,
            "method": ("Tenancy types from the reference's designed fact states only (claim_type). Family means: a family's "
                       "value is the mean over its claim-runs of the type; the type's value is the mean over the families "
                       "that have such claims (as the paper's subset rows). Contrasts: CasePath minus the comparator over "
                       "those families, 95% paired cluster-bootstrap interval (10,000 resamples, spec seed), exact two-sided "
                       "sign-flip p; descriptive. Theft: S = the 72 changed-fact pairs (nine changed-fact clusters, the "
                       "registered measure), O = the 48 unresolved-fact pairs (six clusters: the conditions that have an "
                       "unresolved sentence; smallest attainable p 0.031).")}


# ======================================================================= F2: expected error against the share of type O
def line(m_s, m_o, q):
    return (1 - q) * m_s + q * m_o


def crossover(a, b):
    """a, b: (mean on S, mean on O). The share q in [0, 1] at which the two lines are equal; None if parallel or outside."""
    da, db = a[0] - b[0], (a[1] - a[0]) - (b[1] - b[0])
    if abs(db) < TOL:
        return None
    q = -da / db
    return q if -TOL <= q <= 1 + TOL else None


def type_bootstrap(cells, B, seed, grid=Q_GRID):
    """cells: {family: {'S': (sum, n), 'O': (sum, n)}}. Resample families with replacement; per resample the pooled
    claim-run means on S and O and the line on the grid; a resample without S or O claims is drawn again. Returns the
    2.5 and 97.5 percentiles per grid point, and the number of redraws."""
    g = random.Random(seed)
    fams = sorted(cells)
    lines, redraws = [], 0
    while len(lines) < B:
        pick = [g.choice(fams) for _ in fams]
        tot = {"S": [0.0, 0], "O": [0.0, 0]}
        for f in pick:
            for t, (sm, n) in cells[f].items():
                tot[t][0] += sm
                tot[t][1] += n
        if not tot["S"][1] or not tot["O"][1]:
            redraws += 1
            continue
        ms, mo = tot["S"][0] / tot["S"][1], tot["O"][0] / tot["O"][1]
        lines.append([line(ms, mo, q) for q in grid])
    lo, hi = [], []
    for i in range(len(grid)):
        v = sorted(x[i] for x in lines)
        lo.append(s2.quantile(v, 0.025))
        hi.append(s2.quantile(v, 0.975))
    return lo, hi, redraws


def f2(study, f1res):
    types = f1res["types"]
    q_test = sum(t == "O" for t in types.values()) / len(types)
    out = {"q_test": q_test, "measures": {}}
    for field, key in (("strict_unsafe", "strict_unsafe"), ("all_dev", "all_dev")):
        means = {}
        for d in LINE_DESIGNS:
            x = f1res["tenancy"]["by_design"][d]
            means[d] = {"claim_run": (x["S"][f"{key}_claim_run_mean"], x["O"][f"{key}_claim_run_mean"]),
                        "family": (x["S"][f"{key}_family_mean"], x["O"][f"{key}_family_mean"])}
        cross = {}
        for a, b in itertools.combinations(LINE_DESIGNS, 2):
            cross[f"{a} vs {b}"] = {k: crossover(means[a][k], means[b][k]) for k in ("claim_run", "family")}
        bands = {}
        if field == "strict_unsafe":
            for d in ("casepath", "ric_frontier"):
                cells = defaultdict(lambda: {"S": [0.0, 0], "O": [0.0, 0]})
                for r in study.tenancy_rows(d):
                    c = cells[r["cluster"]][types[r["case"]]]
                    c[0] += r[field]
                    c[1] += 1
                cells = {f: {t: tuple(v) for t, v in x.items()} for f, x in cells.items()}
                lo, hi, redraws = type_bootstrap(cells, s2.B, f"{s2.SEED}|F2|{d}")
                bands[d] = {"lo": lo, "hi": hi, "redraws": redraws}
        at_test = {d: line(*means[d]["claim_run"], q_test) for d in LINE_DESIGNS}
        stored = {d: need(study.design_summary(d, "tenancy"), "measures",
                          "strict_unsafe_per_claim" if field == "strict_unsafe" else "all_deviations_per_claim") for d in LINE_DESIGNS}
        for d in LINE_DESIGNS:
            assert abs(at_test[d] - stored[d]) < 1e-9, (d, at_test[d], stored[d])
        out["measures"][field] = {"means": means, "crossovers": cross, "bands": bands, "at_test_share": at_test}
    out["method"] = ("E(q) = (1 - q) x mean on type S + q x mean on type O, with claim-run means (at the test's own share "
                     "this reproduces the registered per-claim value; checked) and, beside it, family means. Crossover: "
                     "the q in [0, 1] where two lines meet (None: parallel or outside 0-1). Band: 10,000 family-bootstrap "
                     "resamples (24 families with replacement; pooled claim-run means on S and O per resample; a resample "
                     "without either type is drawn again), percentile 2.5-97.5 per q, for CasePath and the frontier single "
                     "prompt.")
    return out


# ======================================================================= F3: other orders and Holm
ORDERS = {
    "frozen order (registered)": ["H1", "H2", "H3", "H4", "H5"],
    "final draft before the reorder": ["H1", "H2", "H4", "H5", "H3"],
    "first draft": ["H1", "H4", "H3-NI (first draft)", "H5"],
}


def fixed_sequence_status(order, tests):
    """tests: {id: (p, favours_casepath_or_None_for_NI)}. Fixed sequence at ALPHA; a 'fewer' hypothesis also needs the
    difference to favour CasePath."""
    out, open_ = {}, True
    for h in order:
        if not open_:
            out[h] = "not tested"
            continue
        p, fav = tests[h]
        ok = p < ALPHA and fav is not False
        out[h] = "confirmed" if ok else "not confirmed"
        open_ = ok
    return out


def holm_status(ids, tests):
    adj = s2.holm([tests[h][0] for h in ids])
    return {h: ("confirmed" if a < ALPHA and tests[h][1] is not False else "not confirmed", a) for h, a in zip(ids, adj)}


def f3(study, res3, review):
    hyp = {h["id"]: h for h in res3["hypotheses"]}
    t = {}
    for hid in ("H1", "H2", "H3"):
        x = hyp[hid]["tests"][0]
        t[hid] = (x["p"], x["favours"] == "a")
    h4 = hyp["H4"]["tests"]
    t["H4"] = (max(x["p"] for x in h4), all(x["favours"] == "a" for x in h4))
    h5 = hyp["H5"]["tests"][0]
    fa, fb = study.clusters("casepath", "theft", "errors"), study.clusters("ric_frontier", "theft", "errors")
    exact_ni = R.signflip_onesided_ni([fa[k] - fb[k] for k in sorted(fa)], h5["margin"])
    rv = next(c for c in review["R5"]["contrasts"] if c["name"].startswith("H5"))
    assert abs(exact_ni - rv["facts_signflip_ni_p_onesided"]) < 1e-12
    ni_old = s3.run_contrast(study.clusters("casepath", "tenancy", "strict_unsafe"),
                             study.clusters("ric_frontier", "tenancy", "strict_unsafe"),
                             "firstdraft|H3NI", False, "noninferiority", 0.10)
    t["H3-NI (first draft)"] = (ni_old["p"], None)
    out = {"p": {}, "procedures": {}, "h4_self_consistency": {}}
    for variant, p5 in (("H5 bootstrap p", h5["p"]), ("H5 exact sign-flip p", exact_ni)):
        tt = {**t, "H5": (p5, None)}
        proc = {name: fixed_sequence_status(order, tt) for name, order in ORDERS.items()}
        proc["Holm over the five registered hypotheses"] = holm_status(["H1", "H2", "H3", "H4", "H5"], tt)
        out["procedures"][variant] = proc
        out["p"][variant] = {k: v[0] for k, v in tt.items()}
    sc = next(x for x in h4 if x["b"] == "self_consistency")
    out["h4_self_consistency"] = {"test": "exact two-sided sign-flip over the nine changed-fact clusters",
                                  "smallest_p": sc["min_p"], "p": sc["p"], "clusters": sc["clusters"],
                                  "nonzero_clusters": sc["nonzero_clusters"], "could_have_passed": sc["min_p"] < ALPHA}
    out["first_draft_h3_ni"] = {"margin": 0.10, "a_value": ni_old["a_value"], "b_value": ni_old["b_value"], "diff": ni_old["diff"],
                                "diff_ci": ni_old["diff_ci"], "p": ni_old["p"],
                                "definition": "first draft (STUDY3_DESIGN.md at 71eaa9eb): CasePath's strict unsafe errors per claim "
                                              "not higher than Rules in context, frontier, by 0.10 or more; paired cluster bootstrap "
                                              "over the 24 families, p = share of resamples reaching the margin"}
    out["method"] = ("p values: H1-H3 the registered exact sign-flip p; H4 the largest of its three registered p (all three "
                     "must hold, so the family passes at alpha only if the largest does); H5 either the registered bootstrap "
                     "non-inferiority p or the exact one-sided sign-flip non-inferiority p over the nine changed facts "
                     "(study3_review R5). A 'fewer' hypothesis is confirmed only when the difference favours CasePath. "
                     "Holm: study2.holm over the five p values; confirmed when the adjusted p < 0.05. Orders: frozen "
                     "(ANALYSIS_PLAN_STUDY3.md); final draft before the reorder (commit 984d2991); first draft (71eaa9eb), "
                     "whose tenancy hypothesis was a non-inferiority test against the frontier model (margin 0.10), "
                     "computed here from the stored plans with study3.run_contrast.")
    return out


# ======================================================================= F4 (i): CasePath with k readings
_EV = None


def evidence_module():
    global _EV
    if _EV is None:
        pkg = s3.package_dir(SPEC["product_evaluator"]["tenancy"]["package"])
        spec = importlib.util.spec_from_file_location("casepath_evidence_frozen", Path(pkg) / "casepath" / "read" / "evidence.py")
        _EV = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_EV)
    return _EV


def fact_value(definition, raw):
    """team._fact_value at the tested commit: the admitted value of a raw answer, or None."""
    if raw is None:
        return None
    kind = definition["type"]
    if kind == "enum":
        return raw if raw in definition["values"] else None
    if kind == "boolean":
        f = raw.strip().lower()
        return True if f in {"true", "yes", "ja"} else False if f in {"false", "no", "nein"} else None
    return raw


def one_reading(conds, defs, locate):
    """team._reading's admission of one reading's answers: {fact: (status, value, open)}; open is True for an open
    answer whose words are found, False for an answer that is not an open with found words, None for an open answer
    whose words are not found. A condition answered twice with different judgments is unknown."""
    judged = defaultdict(set)
    for r in conds:
        judged[r["id"]].add((r["verdict"], r.get("value")))
    rows = {f: ("unknown", None, False) for f, s in judged.items() if len(s) > 1}
    for r in conds:
        f = r["id"]
        if f in rows or f not in defs:
            continue
        hit = bool(r.get("quote")) and locate(r["quote"])
        if r["verdict"] in ("open", "not_stated"):
            rows[f] = ("unknown", None, (True if hit else None) if r["verdict"] == "open" else False)
            continue
        d = defs[f]
        raw = r["verdict"] if d["type"] == "boolean" else (r.get("value") if r["verdict"] == "true" else None)
        v = fact_value(d, raw)
        rows[f] = ("established", v, False) if v is not None and hit else ("unknown", None, False)
    return rows


def split_readings(responses, n_facts):
    """Reading responses in call order -> readings: a response answering more than half the facts opens a reading; a
    smaller one is the requote of the reading before it and replaces its answers for those facts. Returns
    [(answers, [response indices])]."""
    out = []
    for i, conds in enumerate(responses):
        ids = {c["id"] for c in conds}
        if len(ids) > n_facts / 2 or not out:
            out.append((list(conds), [i]))
        else:
            prev, idx = out[-1]
            out[-1] = ([c for c in prev if c["id"] not in ids] + list(conds), idx + [i])
    return out


def combine_k(rd, k, fid):
    """The recorded row of one fact from the first k admitted readings, as team.read_facts and team.confirm_facts
    combine them (k = 1: the first reading alone). status established only when every one of the k readings gives the
    same value ('agreed')."""
    first = rd[0].get(fid) or ("unknown", None, None)
    opens = [first[2]] + [r.get(fid, (None, None, None))[2] for r in rd[1:k]]
    fv = first[1] if first[0] == "established" else None
    if k == 1:
        return {"status": first[0], "value": fv, "agreed": first[0] == "established", "open_readings": opens}
    rows = [r[fid] for r in rd[1:k] if fid in r]
    vals = [v for s, v, _ in rows if s == "established"]
    if len(rows) < k - 1:
        sec = "conflict" if vals and any(v != vals[0] for v in vals) else "partial" if vals else "unknown"
    elif vals and len(vals) == len(rows) and all(v == vals[0] for v in vals):
        sec = "established"
    elif vals and any(v != vals[0] for v in vals):
        sec = "conflict"
    else:
        sec = "partial" if vals else "unknown"
    v2 = vals[0] if vals else None
    if sec == "conflict":
        return {"status": "conflicting", "value": None, "open_readings": opens}
    if sec == "partial":
        return {"status": "unknown", "value": None, "readings": [fv, v2], "open_readings": opens}
    if fv is not None and sec == "established":
        if fv == v2:
            return {"status": "established", "value": fv, "agreed": True, "open_readings": opens}
        return {"status": "conflicting", "value": None, "open_readings": opens}
    if fv is not None or sec == "established":
        return {"status": "unknown", "value": None, "readings": [fv, v2], "open_readings": opens}
    return {"status": "unknown", "value": None, "open_readings": opens}


def plan_with_k(entry, k, W, wf, readings):
    """The checklist the product's evaluator gives when a value needs the agreement of the first k readings: routing
    facts and document findings as stored, presumptions by the product's own rule (workflows.presumed and the routing
    presumption), exact deferral (workflows.evaluate, checked=True)."""
    defs = {f["id"]: f for f in wf["facts"]}
    stored = entry["product_extra"]["facts"]
    rec, facts = {}, {}
    for f in defs:
        s = stored.get(f) or {}
        if s.get("by") == "routing" and s.get("status") == "established":
            facts[f] = s["value"]
            rec[f] = {"status": "established", "verdict": "accepted", "value": s["value"]}
            continue
        row = combine_k(readings, k, f)
        rec[f] = row
        if row["status"] == "established" and row.get("agreed"):
            facts[f] = row["value"]
    for f, item in W.presumed(wf, {f: {**r, "citations": []} for f, r in rec.items()}).items():
        if facts.get(f) is None:
            facts[f] = item["value"]
    for f, s in stored.items():
        if s.get("status") == "presumed" and s.get("by") == "routing" and W.open_without_raise(rec.get(f), s["value"]):
            facts.setdefault(f, s["value"])
    findings = {d: {"status": j["status"], "verdict": "accepted"} for d, j in (entry["product_extra"].get("document_judgments") or {}).items()
                if j["status"] in {"present", "unusable"} and j.get("verdict") == "accepted"}
    ev = W.evaluate(wf, facts, findings, checked=True)
    return {"family": wf["id"], "deferred": False,
            "requests": sorted(r["document"] for r in ev["documents"] if r["required"] == "yes" and r["status"] in {"missing", "unusable"}),
            "holds": sorted(r["document"] for r in ev["documents"] if r["required"] == "depends")}


def case_files(study, regime, case):
    if regime == "tenancy":
        return [{"id": s["artifact_id"], "text": s["text"]} for s in study.D["tenancy"].sources(case)]
    return [{"id": "case", "text": study.D["theft"].texts()[case]["text"]}]


def f4_readings(study, cache):
    EV = evidence_module()
    ledger = {}
    for r in study.inputs.ledger("runs/product/ledger_dev_gpt-6-luna.jsonl"):
        ledger.setdefault(r["key"], float(r.get("usd") or 0))
    design = "casepath_checklist"
    out = {}
    T = study.D["theft"].texts()
    for regime in ("tenancy", "theft"):
        W, cat = study.evaluator(regime, SPEC["product_evaluator"][regime])
        plans = {k: {} for k in (1, 2, 3)}
        cost = {k: [] for k in (1, 2, 3)}
        check = Counter()
        for c in study.cases[regime]:
            ev = EV.Evidence(case_files(study, regime, c))
            locate = lambda q: any(ev.locate(fid, q) for fid in ev.files)
            for k in (1, 2, 3):
                plans[k][c] = []
            for r, e in enumerate(study.entries[(design, regime)][c]):
                keys = list(dict.fromkeys((e or {}).get("keys") or []))
                total = sum(ledger.get(x, 0.0) for x in keys)
                fam = ((e or {}).get("plan") or {}).get("family")
                if e is None or not fam:
                    for k in (1, 2, 3):
                        plans[k][c].append(study.plans[(design, regime)][c][r])
                        cost[k].append(total)
                    check["not evaluated (failed or not routed): stored plan kept"] += 1
                    continue
                wf = cat.get(fam)
                resp_keys = [x for x in keys if cache.reading(x) is not None]
                groups = split_readings([cache.reading(x) for x in resp_keys], len(wf["facts"]))
                if len(groups) != 3:
                    raise AssertionError(f"{c} run {r}: {len(groups)} readings")
                defs = {f["id"]: f for f in wf["facts"]}
                rd = [one_reading(g, defs, locate) for g, _ in groups]
                for k in (1, 2, 3):
                    p = plan_with_k(e, k, W, wf, rd)
                    plans[k][c].append(s3.to_names(p, study.inv) if regime == "theft" else p)
                    dropped = sum(ledger.get(resp_keys[i], 0.0) for g in groups[k:] for i in g[1])
                    cost[k].append(total - dropped)
                check["evaluated"] += 1
                check["k = 3 reproduces the stored checklist"] += R.same_checklist(plans[3][c][-1], e.get("plan_workflow_only"))
        res = {"check": dict(check), "by_k": {}}
        for k in (1, 2, 3):
            res["by_k"][k] = {**score_plans(study, regime, plans[k], f"F4|k{k}"), "cost_per_case_run": mean(cost[k])}
        res["_plans"] = plans
        out[regime] = res
    return out


def score_plans(study, regime, plans, name):
    """Registered measures of a design given as {case: [plan per run]} (any number of runs)."""
    if regime == "tenancy":
        rows = []
        for c in study.cases["tenancy"]:
            ref = study.D["tenancy"].reference(c)
            fam = ref["family_id"]
            for i, p in enumerate(plans[c]):
                row = R.scored(ref, p)
                row.update(case=c, run=i, cluster=fam)
                rows.append(row)
        s = study.tenancy_summary(rows)
        return {"runs_per_case": len(next(iter(plans.values()))), "strict_unsafe_per_claim": s["strict_unsafe_per_claim"],
                "all_deviations_per_claim": s["all_deviations_per_claim"], "correct_hold_share": s["correct_hold_share"],
                "held_required_now_per_claim": s["held_required_now_per_claim"], "spurious_holds_per_claim": s["spurious_holds_per_claim"],
                "premature_per_claim": s["premature_per_claim"], "silent_skip_per_claim": s["silent_skip_per_claim"],
                "_clusters": s2.by_cluster(rows, "cluster", s2.TEN_METRIC["strict_unsafe"])}
    n = len(next(iter(plans.values())))
    pairing = [(i, i) for i in range(n)]
    on = s2.theft_rows(None, [p for p in study.pairs if p["kind"] == "on"], plans, pairing=pairing)
    un = s2.theft_rows(None, [p for p in study.pairs if p["kind"] == "unresolved"], plans, pairing=pairing)
    s = s2.theft_summary(on, un)
    return {"runs_per_case": n, "errors_per_pair": s["errors_per_pair"], "wrong_per_pair": s["wrong_per_pair"],
            "missed_per_pair": s["missed_per_pair"], "unresolved_unchanged_share": s["unresolved"]["stable_rate"],
            "unresolved_premature_share": s["unresolved"]["premature_rate"],
            "unresolved_held_share": mean(bool(r["held"]) for r in un),
            "_clusters": s2.by_cluster(on, "condition", lambda rs: mean(r["errors"] for r in rs))}


# ======================================================================= F4 (ii): Self-consistency with m samples
def disjoint_votes(samples, m):
    """Disjoint votes of m consecutive samples from the stored samples (study3.majority: requested when more than half
    request it, so a tie is not requested). floor(len / m) votes."""
    return [s3.majority(samples[i * m:(i + 1) * m]) for i in range(len(samples) // m)]


def f4_selfconsistency(study):
    out = {}
    for regime in ("tenancy", "theft"):
        st = study.store("self_consistency", regime)
        n_per_run = int(st["samples_per_run"])
        src = st["samples"]
        raw = study.inputs.json(s3.fmt(src["path"], **study.fill()))
        total = n_per_run * study.runs("self_consistency", regime)
        samples = {}
        for c in study.cases[regime]:
            samples[c] = [(raw.get(s3.fmt(src["key"], **study.fill(case=c, sample=i))) or {}).get(src.get("field", "plan"))
                          for i in range(total)]
            if regime == "theft":
                samples[c] = [s3.to_names(p, study.inv) for p in samples[c]]
        per_sample = need(study.design_summary("self_consistency", regime), "cost", "cost_per_case_run") / n_per_run
        res = {"samples_per_case": total, "cost_per_sample": per_sample, "by_m": {}}
        for m in SC_M:
            plans = {c: disjoint_votes(v, m) for c, v in samples.items()}
            res["by_m"][m] = {**score_plans(study, regime, plans, f"F4|sc{m}"), "votes_per_case": total // m,
                              "cost_per_case_run": m * per_sample}
        reg = study.plans[("self_consistency", regime)]
        five = {c: disjoint_votes(v, 5) for c, v in samples.items()}
        assert all(R.same_checklist(a, b) for c in five for a, b in zip(five[c], reg[c])), "m = 5 does not reproduce the registered votes"
        out[regime] = res
    return out


def f4_budget(study, fr, sc):
    out = {}
    for regime in ("tenancy", "theft"):
        measure = "strict_unsafe" if regime == "tenancy" else "errors"
        costs = {d: need(study.design_summary(d, regime), "cost", "cost_per_case_run") for d in ("casepath", "casepath_checklist")}
        rows = {}
        for target, a in (("checklist only", "casepath_checklist"), ("full product", "casepath")):
            m = next((m for m in SC_M if sc[regime]["by_m"][m]["cost_per_case_run"] >= costs[a] - TOL), None)
            if m is None:
                rows[target] = {"reached": False, "cost_target": costs[a],
                                "cost_of_15_samples": sc[regime]["by_m"][15]["cost_per_case_run"]}
                continue
            fa = study.clusters(a, regime, measure)
            fb = sc[regime]["by_m"][m]["_clusters"]
            rows[target] = {"reached": True, "m": m, "cost_target": costs[a], "cost_sc": sc[regime]["by_m"][m]["cost_per_case_run"],
                            "a": a, "contrast": contrast(fa, fb, f"F4|budget|{regime}|{a}|{m}")}
            if a == "casepath_checklist":
                rows[target]["contrast_full_product"] = contrast(study.clusters("casepath", regime, measure), fb,
                                                                 f"F4|budget|{regime}|casepath|{m}")
        out[regime] = rows
    return out


# ======================================================================= F5: alternative tenancy reference
class AltTenancy:
    """The tenancy data module with document states replaced by an alternative reference; every other field (and so
    the subsets, families and languages) stays the registered reference's."""

    def __init__(self, base, alt):
        self.base, self.alt = base, alt

    def __getattr__(self, name):
        return getattr(self.base, name)

    def reference(self, cid):
        ref = dict(self.base.reference(cid))
        if cid not in self.alt:
            raise KeyError(f"alternative reference has no claim {cid}")
        states = self.alt[cid]
        if set(states) != set(ref["document_states"]):
            raise KeyError(f"{cid}: alternative documents differ from the registered ones: "
                           f"{sorted(set(states) ^ set(ref['document_states']))}")
        bad = {d: s for d, s in states.items() if s not in STATES}
        if bad:
            raise ValueError(f"{cid}: unknown document states {bad}")
        ref["document_states"] = dict(states)
        return ref


F5_CONTRASTS = [("H2", "strict_unsafe", "ric"), ("H3", "strict_unsafe", "ric_frontier"), ("S2a", "strict_unsafe", "self_consistency"),
                ("S2b", "strict_unsafe", "model_executes_rules"), ("S2c", "strict_unsafe", "react"),
                ("S2d", "all_deviations", "self_consistency"), ("S2e", "all_deviations", "model_executes_rules"),
                ("S2f", "all_deviations", "react"), ("S3a", "all_deviations", "ric"), ("S3b", "all_deviations", "ric_frontier")]


def rescore(study, alt, name="alternative"):
    """F5: agreement of an alternative reference with the registered one and the registered tenancy contrasts against it."""
    D = study.D
    alt_study = s3.Study(SPEC, DATA, LABEL, {"tenancy": AltTenancy(D["tenancy"], alt), "theft": D["theft"]}, inputs=study.inputs,
                         evaluator_loader=study.evaluator_loader)
    agree = defaultdict(Counter)
    per_subset = defaultdict(lambda: [0, 0])
    for c in study.cases["tenancy"]:
        reg = D["tenancy"].reference(c)["document_states"]
        a = alt_study.D["tenancy"].reference(c)["document_states"]
        sub = next(s for s in R.SUBSETS if study.in_subset(c, s))
        for d, s in reg.items():
            agree[s][a[d]] += 1
            for k in ("all", sub):
                per_subset[k][0] += 1
                per_subset[k][1] += s == a[d]
    contrasts = []
    for cid, measure, b in F5_CONTRASTS:
        cname = f"primary|{cid}|{b}" if cid.startswith("H") else f"secondary|{cid}"  # the registered names: same resamples
        c_reg = study.contrast_of("tenancy", measure, "casepath", b, "signflip", None, cname)
        c_alt = alt_study.contrast_of("tenancy", measure, "casepath", b, "signflip", None, cname)
        contrasts.append({"id": cid, "measure": measure, "b": b,
                          "registered": {k: c_reg[k] for k in ("a_value", "b_value", "diff", "diff_ci", "p", "clusters", "nonzero_clusters")},
                          "alternative": {k: c_alt[k] for k in ("a_value", "b_value", "diff", "diff_ci", "p", "clusters", "nonzero_clusters")}})
    for c in contrasts:
        c["verdict"] = verdict(c["registered"], c["alternative"])
    return {"name": name, "agreement_by_state": {s: dict(v) for s, v in sorted(agree.items())},
            "agreement_by_subset": {k: {"documents": n, "same_state": m, "share": m / n} for k, (n, m) in per_subset.items()},
            "identical_to_registered": all(m == n for n, m in per_subset.values()),
            "by_design": design_scores(alt_study), "contrasts": contrasts}


def design_scores(st):
    """Strict unsafe errors and all deviations per claim for every tenancy design: overall (mean over the 24 families)
    and on each registered subset (family means over the families with claims in it, as the paper's subset rows)."""
    out = {}
    for d in SPEC["designs"]:
        if "tenancy" not in d["regimes"]:
            continue
        row = {}
        for sub in (None,) + R.SUBSETS:
            for m in ("strict_unsafe", "all_deviations"):
                cl = st.clusters(d["key"], "tenancy", m, sub)
                row[f"{m}|{sub or 'all claims'}"] = mean(cl.values())
        out[d["key"]] = row
    return out


def verdict(reg, alt):
    """How a contrast fares under another reference, in words: 'reverses' when the sign flips, 'not significant' when
    p >= alpha, 'holds' when the difference keeps at least 90% of its registered size, otherwise 'holds, shrinks'
    (or 'holds, grows' when it is more than 10% larger)."""
    if alt["diff"] * reg["diff"] < 0:
        return "reverses" + (" (p < 0.05)" if alt["p"] < ALPHA else " (not significant)")
    if alt["p"] >= ALPHA:
        return "same sign, not significant"
    r = abs(alt["diff"]) / abs(reg["diff"]) if reg["diff"] else float("inf")
    return "holds" if 0.9 <= r <= 1.1 else ("holds, shrinks" if r < 0.9 else "holds, grows")


CLEANROOM = [
    ("clean room: registered reference as given to the comparison", "cleanroom/registered_reference.json"),
    ("clean room: evaluator A", "cleanroom/evaluator_a/reference.json"),
    ("clean room: evaluator B", "cleanroom/evaluator_b/reference.json"),
    ("reading A1: a denied defining event does not stop the process", "cleanroom/evaluator_b/reference_alt_A1.json"),
    ("reading A2: an open defining event is presumed to have occurred", "cleanroom/evaluator_b/reference_alt_A2.json"),
    ("reading A3: optional documents are requested", "cleanroom/evaluator_b/reference_alt_A3.json"),
    ("reading A4: a family-home condition excludes arrears", "cleanroom/evaluator_b/reference_alt_A4.json"),
    ("readings A1-A4 together", "cleanroom/evaluator_b/reference_alt_all.json"),
]


def load_alt(path):
    data = json.loads(Path(path).read_text())
    return {c: (v["document_states"] if isinstance(v, dict) and "document_states" in v else v) for c, v in data.items()}


# ======================================================================= report
def fmt(x, nd=3):
    return "–" if x is None else f"{x:.{nd}f}"


def pct(x):
    return "–" if x is None else f"{100 * x:.1f}%"


def pv(p):
    return "–" if p is None else ("< 0.0001" if p < 0.0001 else f"{p:.4f}")


def table(head, rows):
    return R.table(head, rows)


def crow(c):
    return [fmt(c["a_value"]), fmt(c["b_value"]), fmt(c["diff"]), f"[{fmt(c['diff_ci'][0])}, {fmt(c['diff_ci'][1])}]",
            f"{c['clusters']} / {c['nonzero_clusters']}", pv(c["p"])]


def markdown(res):
    L = {d["key"]: d["label"] for d in SPEC["designs"]}
    md = [f"# Study 3, analyses asked for by outside feedback (data `{DATA}`, run label `{LABEL}`)", "",
          "Generated by `analysis/study3_feedback.py` with the functions of `analysis/study3.py` and `analysis/study3_review.py`. "
          "No model calls. **Post hoc: these analyses are not part of ANALYSIS_PLAN_STUDY3.md, were decided after the "
          "results were known, are descriptive and change no hypothesis's status.**", ""]
    x = res["F1"]
    t = x["tenancy"]
    md += ["## F1. Files with every fact stated against files with an open or denied fact", "",
           "This shows every design's errors separately on claims where nothing is open or denied (S) and on claims with an "
           "open fact or a denied or open defining event (O), and the same split on theft (changed-fact and unresolved-fact pairs).", "",
           x["method"], "",
           f"Tenancy: S {t['counts']['S']} claims, O {t['counts']['O']} claims (partition checked). Composition: "
           + "; ".join(f"{k} {v}" for k, v in t["composition"].items()) + ".", ""]
    rows = []
    for d, v in t["by_design"].items():
        for ty in ("S", "O"):
            y = v[ty]
            rows.append([L[d], ty, y["claims"], y["families"], fmt(y["strict_unsafe_family_mean"]), fmt(y["strict_unsafe_claim_run_mean"]),
                         fmt(y["all_dev_family_mean"]), fmt(y["all_dev_claim_run_mean"]), pct(y["exact_share_family_mean"]),
                         pct(y["exact_share_claim_run"])])
    md += [table(["Design", "Type", "Claims", "Families", "Strict unsafe (family mean)", "(claim-run mean)", "All deviations (family mean)",
                  "(claim-run mean)", "Exact checklist (family mean)", "(claim-run)"], rows), ""]
    rows = []
    for b, v in t["contrasts"].items():
        for ty in ("S", "O"):
            for m, lab in (("strict_unsafe", "strict unsafe"), ("all_dev", "all deviations"), ("exact_share", "exact share")):
                rows.append([f"CasePath − {L[b]}", ty, lab] + crow(v[ty][m]))
    md += [table(["Contrast", "Type", "Measure", "CasePath", "Comparator", "Difference", "95% interval", "families / non-zero", "sign-flip p"], rows), ""]
    th = x["theft"]
    md += [f"Theft: {th['counts']['S (changed-fact pairs)']} changed-fact pairs (S), {th['counts']['O (unresolved-fact pairs)']} "
           "unresolved-fact pairs (O).", ""]
    md += [table(["Design", "S: wrong + missed per pair", "O: left unchanged", "O: premature request", "O: open condition's documents held"],
                 [[L[d], fmt(v["S"]["errors_per_pair"]), pct(v["O"]["unchanged_share"]), pct(v["O"]["premature_share"]),
                   pct(v["O"]["held_share"])] for d, v in th["by_design"].items()]), ""]
    rows = []
    for b, v in th["contrasts"].items():
        for k, c in v.items():
            rows.append([f"CasePath − {L[b]}", k] + crow(c))
    md += [table(["Contrast", "Measure", "CasePath", "Comparator", "Difference", "95% interval", "clusters / non-zero", "sign-flip p"], rows), ""]
    # F2
    x = res["F2"]
    md += ["## F2. Expected error against the share of open-or-denied files", "",
           "This shows how each design's expected strict unsafe errors per claim change with the share of type-O claims, and "
           "where the lines cross.", "", x["method"], "", f"The test's own share of type O: {fmt(x['q_test'])}.", ""]
    for field, lab in (("strict_unsafe", "Strict unsafe errors per claim"), ("all_dev", "All deviations per claim")):
        y = x["measures"][field]
        md += [f"**{lab}.**", "", table(["Design", "S (claim-run)", "O (claim-run)", "S (family)", "O (family)", "at the test's share"],
                                         [[L[d], fmt(v["claim_run"][0]), fmt(v["claim_run"][1]), fmt(v["family"][0]), fmt(v["family"][1]),
                                           fmt(y["at_test_share"][d])] for d, v in y["means"].items()]), ""]
        md += [table(["Lines", "Crossover share (claim-run means)", "(family means)"],
                     [[" vs ".join(L[x] for x in k.split(" vs ")),
                       "no crossover in 0–1" if v["claim_run"] is None else fmt(v["claim_run"]),
                       "no crossover in 0–1" if v["family"] is None else fmt(v["family"])] for k, v in y["crossovers"].items()]), ""]
    # F3
    x = res["F3"]
    md += ["## F3. The hypotheses under other orders and under Holm's correction", "",
           "This shows which hypotheses would have been confirmed under other orders of the fixed sequence and under Holm's "
           "order-free correction, from the registered p values.", "", x["method"], ""]
    ids = ["H1", "H2", "H3", "H4", "H5", "H3-NI (first draft)"]
    for variant, proc in x["procedures"].items():
        md += [f"**With {variant}** (p: " + ", ".join(f"{h} {pv(p)}" for h, p in x["p"][variant].items()) + ").", ""]
        rows = []
        for h in ids:
            row = [h]
            for name, st in proc.items():
                if name.startswith("Holm"):
                    row.append(f"{st[h][0]} (adjusted p {pv(st[h][1])})" if h in st else "not in this procedure")
                else:
                    row.append(st.get(h, "not in this order"))
            rows.append(row)
        md += [table(["Hypothesis"] + list(proc), rows), ""]
    h = x["h4_self_consistency"]
    f = x["first_draft_h3_ni"]
    md += [f"H4, Self-consistency contrast: {h['test']}; smallest p it could return {pv(h['smallest_p'])} (registered output); "
           f"p returned {pv(h['p'])} ({h['nonzero_clusters']} of {h['clusters']} clusters non-zero). The hypothesis could have "
           f"passed: {'yes' if h['could_have_passed'] else 'no'}.", "",
           f"First draft's tenancy hypothesis: {f['definition']}. CasePath {fmt(f['a_value'])}, frontier {fmt(f['b_value'])}, "
           f"difference {fmt(f['diff'])} [{fmt(f['diff_ci'][0])}, {fmt(f['diff_ci'][1])}], p {pv(f['p'])}.", ""]
    # F4
    x = res["F4"]
    md += ["## F4. Error against cost, budget-matched", "",
           "This shows errors and cost per case for CasePath with one, two and three readings and for Self-consistency with "
           "1 to 15 samples, and CasePath against Self-consistency at a matched budget.", "", x["method"], ""]
    for regime in ("tenancy", "theft"):
        y = x["readings"][regime]
        md += [f"**{regime.capitalize()}, CasePath (checklist only) with k readings.** Check: " + "; ".join(f"{k}: {v}" for k, v in y["check"].items()) + ".", ""]
        if regime == "tenancy":
            md += [table(["k", "Strict unsafe per claim", "All deviations", "Correct-hold share", "Held req.-now", "Spurious holds",
                          "Premature", "Silent skips", "USD per case-run"],
                         [[k, fmt(v["strict_unsafe_per_claim"]), fmt(v["all_deviations_per_claim"]), pct(v["correct_hold_share"]),
                           fmt(v["held_required_now_per_claim"]), fmt(v["spurious_holds_per_claim"]), fmt(v["premature_per_claim"]),
                           fmt(v["silent_skip_per_claim"]), fmt(v["cost_per_case_run"], 5)] for k, v in y["by_k"].items()]), ""]
        else:
            md += [table(["k", "Wrong + missed per pair", "Wrong", "Missed", "Unresolved: unchanged", "premature", "held", "USD per text-run"],
                         [[k, fmt(v["errors_per_pair"]), fmt(v["wrong_per_pair"]), fmt(v["missed_per_pair"]), pct(v["unresolved_unchanged_share"]),
                           pct(v["unresolved_premature_share"]), pct(v["unresolved_held_share"]), fmt(v["cost_per_case_run"], 5)]
                          for k, v in y["by_k"].items()]), ""]
        z = x["self_consistency"][regime]
        md += [f"**{regime.capitalize()}, Self-consistency with m samples** ({z['samples_per_case']} stored samples per case; "
               f"USD {fmt(z['cost_per_sample'], 6)} per sample).", ""]
        if regime == "tenancy":
            md += [table(["m", "Votes per case", "Strict unsafe per claim", "All deviations", "Correct-hold share", "USD per case-run"],
                         [[m, v["votes_per_case"], fmt(v["strict_unsafe_per_claim"]), fmt(v["all_deviations_per_claim"]),
                           pct(v["correct_hold_share"]), fmt(v["cost_per_case_run"], 5)] for m, v in z["by_m"].items()]), ""]
        else:
            md += [table(["m", "Votes per case", "Wrong + missed per pair", "Unresolved: unchanged", "premature", "USD per text-run"],
                         [[m, v["votes_per_case"], fmt(v["errors_per_pair"]), pct(v["unresolved_unchanged_share"]),
                           pct(v["unresolved_premature_share"]), fmt(v["cost_per_case_run"], 5)] for m, v in z["by_m"].items()]), ""]
        b = x["budget"][regime]
        for target, v in b.items():
            if not v["reached"]:
                md += [f"Budget of the {target} (USD {fmt(v['cost_target'], 5)}): not reached by 15 samples "
                       f"(USD {fmt(v['cost_of_15_samples'], 5)}); no contrast.", ""]
                continue
            c = v["contrast"]
            md += [f"Budget of the {target} (USD {fmt(v['cost_target'], 5)}): Self-consistency with m = {v['m']} "
                   f"(USD {fmt(v['cost_sc'], 5)}). {L[v['a']]} minus it: {fmt(c['a_value'])} − {fmt(c['b_value'])} = {fmt(c['diff'])} "
                   f"[{fmt(c['diff_ci'][0])}, {fmt(c['diff_ci'][1])}], {c['clusters']} clusters ({c['nonzero_clusters']} non-zero), "
                   f"sign-flip p {pv(c['p'])}" + (f"; the full product minus it: {fmt(v['contrast_full_product']['diff'])} "
                                                f"[{fmt(v['contrast_full_product']['diff_ci'][0])}, {fmt(v['contrast_full_product']['diff_ci'][1])}], "
                                                f"p {pv(v['contrast_full_product']['p'])}" if "contrast_full_product" in v else "") + ". Descriptive.", ""]
    # F5
    x = res["F5"]
    md += ["## F5. Re-scoring against other tenancy references (sensitivity to the reading of the rule text)", "",
           "This scores every design against the clean-room references and against references written under the readings of "
           "the rule text that the evaluators rejected, and shows whether the tenancy result holds, shrinks or reverses. "
           "Post hoc; sensitivity to the reading of the rule text.", "", x["usage"], ""]
    if x["absent_files"]:
        md += ["Files not present when this ran (not scored): " + ", ".join(f"`{f}`" for f in x["absent_files"]) + ".", ""]
    md += [table(["Reference", "Same state as registered (of 1,024)", "ordinary", "denied event", "open event", "Identical"],
                 [[i["name"], i["agreement_by_subset"]["all"]["same_state"], i["agreement_by_subset"]["ordinary"]["same_state"],
                   i["agreement_by_subset"]["denied_event"]["same_state"], i["agreement_by_subset"]["open_event"]["same_state"],
                   "yes" if i["identical_to_registered"] else "no"] for i in x["results"]]), ""]
    keys = ["strict_unsafe|all claims", "strict_unsafe|ordinary", "strict_unsafe|denied_event", "strict_unsafe|open_event",
            "all_deviations|all claims"]
    md += ["**Reading x design: strict unsafe errors per claim** (family means; overall, then the three registered subsets, "
           "membership fixed by the registered reference; last column all deviations per claim overall).", ""]
    rows = []
    for i in x["results"]:
        for d, v in i["by_design"].items():
            rows.append([i["name"], L[d]] + [fmt(v[k]) for k in keys])
    md += [table(["Reference", "Design", "Strict: all", "ordinary", "denied event", "open event", "All deviations: all"], rows), ""]
    md += ["**Reading x contrast** (CasePath minus comparator, family clusters, 95% cluster-bootstrap interval with the "
           "registered resamples, exact sign-flip p; verdict against the registered reference).", ""]
    rows = []
    for i in x["results"]:
        for c in i["contrasts"]:
            al = c["alternative"]
            rows.append([i["name"], c["id"], c["measure"], L[c["b"]], fmt(al["diff"]),
                         f"[{fmt(al['diff_ci'][0])}, {fmt(al['diff_ci'][1])}]", pv(al["p"]), c["verdict"]])
    md += [table(["Reference", "Contrast", "Measure", "Comparator", "Difference", "95% interval", "p", "Against the registered result"], rows), ""]
    md += ["**In words.**", ""]
    for i in x["results"]:
        v = {c["id"]: c["verdict"] for c in i["contrasts"]}
        md.append(f"- {i['name']}: H2 {v['H2']}; H3 {v['H3']}; same-model secondary contrasts: "
                  + ", ".join(f"{k} {v[k]}" for k in ("S2a", "S2b", "S2c", "S2d", "S2e", "S2f", "S3a", "S3b")) + ".")
    md += [""]
    return "\n".join(md)


def strip(x):
    """Drop private working fields (keys starting with '_') before writing."""
    if isinstance(x, dict):
        return {str(k): strip(v) for k, v in x.items() if not str(k).startswith("_")}
    if isinstance(x, (list, tuple)):
        return [strip(v) for v in x]
    return x


def perturbed(study, seed=f"{s2.SEED}|F5|perturbed", share=0.1):
    """The registered reference with a seeded share of documents moved to another state (for the hook's check)."""
    g = random.Random(seed)
    out = {}
    for c in study.cases["tenancy"]:
        st = dict(study.D["tenancy"].reference(c)["document_states"])
        for d in sorted(st):
            if g.random() < share:
                st[d] = g.choice([s for s in STATES if s != st[d]])
        out[c] = st
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--alt-reference", nargs="*", default=[], help="alternative tenancy reference(s), JSON claim -> document -> state")
    a = ap.parse_args(argv)
    s3.configure(SPEC)
    res3 = json.loads((HERE / f"study3_results_{DATA}_{LABEL}.json").read_text())
    review = json.loads((HERE / "study3_review.json").read_text())
    study = s3.Study(SPEC, DATA, LABEL, s3.load_data(DATA))
    for d in SPEC["designs"]:
        for reg in d["regimes"]:
            assert study.load(d["key"], reg), f"{d['key']}/{reg} not loaded"
    cache = R.Cache()
    res = {"label": LABEL_POSTHOC, "posthoc": True, "preregistered": False, "data": DATA, "run_label": LABEL,
           "statistics": {"bootstrap_resamples": s2.B, "seed": s2.SEED}}
    res["F1"] = f1(study)
    res["F2"] = f2(study, res["F1"])
    res["F3"] = f3(study, res3, review)
    fr = f4_readings(study, cache)
    sc = f4_selfconsistency(study)
    res["F4"] = {"readings": fr, "self_consistency": sc, "budget": f4_budget(study, fr, sc),
                 "single_points": {reg: {d: {"cost_per_case_run": need(study.design_summary(d, reg), "cost", "cost_per_case_run"),
                                             "errors": need(study.design_summary(d, reg), "measures",
                                                            "strict_unsafe_per_claim" if reg == "tenancy" else "errors_per_pair")}
                                         for d in ("ric", "ric_frontier", "casepath", "casepath_checklist")} for reg in ("tenancy", "theft")},
                 "method": (
                     "(i) CasePath, checklist only (cost-efficient model, three runs): for each stored case-run its three readings "
                     "are taken from the response cache (a response answering more than half the workflow's facts opens a "
                     "reading, a smaller one is its requote), each answer admitted as the product does (value, and a quotation "
                     "found word for word by the product's own Evidence.locate at the tested commit), and the first k readings "
                     "combined as team.read_facts / team.confirm_facts combine them: a value counts only when all k give it. "
                     "Routing facts and document findings are kept as stored; presumptions follow the product's rule "
                     "(workflows.presumed, open rule 'any'); the checklist is the product evaluator's (exact deferral). The "
                     "check row shows how often k = 3 reproduces the stored checklist. Cost per case-run = the ledger cost of "
                     "the case-run's calls minus the readings after the k-th (with their requotes). "
                     "(ii) Self-consistency: the 15 stored samples per case (Rules in context, cost-efficient model) in "
                     "consecutive disjoint groups of m; floor(15 / m) votes per case, each scored as a run (votes per case: "
                     "m = 1: 15, 3: 5, 5: 3, 7: 2, 9-15: 1); study3.majority (requested when more than half the samples "
                     "request it; a tie is not requested); m = 5 reproduces the registered votes (checked). Cost = m x the "
                     "registered cost per sample. (iii) Budget-matched: the smallest m whose cost is at least the "
                     "product's; paired contrast with the registered clusters (24 families; nine changed facts), a design's "
                     "cluster value being the mean over its runs or votes; descriptive.")}
    res["F4_plans_check"] = {reg: {k: sum(1 for c in study.cases[reg] for p in fr[reg]["_plans"][k][c]) for k in (1, 2, 3)}
                             for reg in ("tenancy", "theft")}
    # F5: registered reference (must reproduce), a perturbed copy, and any given files
    items = [("registered reference (check)", {c: study.D["tenancy"].reference(c)["document_states"] for c in study.cases["tenancy"]}),
             ("perturbed copy of the registered reference (10% of documents moved, seeded; check)", perturbed(study))]
    absent = []
    for label, rel in CLEANROOM:
        path = TMIS / rel
        if path.exists():
            items.append((label, load_alt(path)))
        else:
            absent.append(rel)
    items += [(str(p), load_alt(p)) for p in a.alt_reference]
    f5 = []
    for name, alt in items:
        r = rescore(study, alt, name)
        f5.append(r)
    stored = {**{h["id"]: h["tests"][0] for h in res3["hypotheses"] if h["regime"] == "tenancy"},
              **{c["id"]: c["result"] for c in res3["secondary"]["contrasts"]}}
    for c in f5[0]["contrasts"]:
        for k in ("a_value", "b_value", "diff", "p", "diff_ci"):
            assert c["registered"][k] == c["alternative"][k] == stored[c["id"]][k], ("registered reference does not reproduce", c["id"], k)
    res["F5"] = {"results": f5, "absent_files": absent, "usage": (
        "python3 analysis/study3_feedback.py --alt-reference A.json B.json: each file maps claim id -> document id -> state "
        "(required_now, held, not_needed, supplied_sufficient, supplied_insufficient), or claim id -> {document_states: ...} "
        "as the stored references; every claim and every document of the registered reference must be present. Subsets, "
        "families and everything else stay the registered reference's; every design's stored plans are rescored with "
        "study2.ten_row, and the registered tenancy contrasts (H2, H3, S2a-S2f, S3a, S3b) are recomputed with study3's "
        "own contrast. The registered reference itself reproduces every stored number (checked).")}
    res["inputs"] = dict(sorted(study.inputs.hashes.items()))
    out = strip(res)
    out["F1"].pop("types")
    OUT.with_suffix(".json").write_text(json.dumps(out, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    OUT.with_suffix(".md").write_text(markdown(res) + "\n")
    print("written", OUT.with_suffix(".json"), "and", OUT.with_suffix(".md"))
    return res


if __name__ == "__main__":
    main()
