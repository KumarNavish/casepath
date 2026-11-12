"""Score the fair-baseline designs with Study 3's registered scorers. POST HOC, development data. No model calls.

    python3 analyse.py        # writes REPORT.json (REPORT.md is written by hand from it)

Scoring is imported, not re-implemented: analysis/study3.py (Study: loading, failed output = empty plan, theft id
mapping, tenancy rows via study2.ten_row, theft rows via study2.theft_row / theft_score, clusters, run_contrast with the
spec's bootstrap and exact cluster sign-flip), analysis/study3_feedback.claim_type and analysis/power_study4.subset_of
(the S / O split and its three O parts). The new designs enter as extra entries of an in-memory copy of
analysis/study3_spec.json (the file is not changed).

Added here (statistics only): per-case paired differences (a case = a tenancy claim or a theft pair; a design's value
on a case = the mean over its runs), the sign-flip p over cases (exact on the non-zero differences when there are at
most 22, otherwise Monte Carlo with 200,000 seeded sign patterns, p = (1 + count) / (1 + patterns)), and beside it the
registered cluster contrast (families / changed facts; exact sign-flip over clusters).
"""
from __future__ import annotations

import copy
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
TMIS = HERE.parents[1]
sys.path.insert(0, str(TMIS / "analysis"))
import power_study4 as P  # noqa: E402

F, s3, s2 = P.F, P.F.s3, P.F.s2
REL = "study4/baseline_check/runs"
NEW = {
    "hold_prompt": ("Prompt with hold option (A), luna", "gpt-6-luna", 3, "A-luna", "A"),
    "hold_prompt_frontier": ("Prompt with hold option (A), terra", "gpt-6.1-terra", 1, "A-terra", "A"),
    "mer_hold_frontier": ("Model executes rules with hold option (B), terra", "gpt-6.1-terra", 1, "B-terra", "B"),
}
OLD = ["casepath", "casepath_checklist", "casepath_frontier_checklist", "ric", "ric_frontier", "model_executes_rules", "self_consistency", "react"]
CONTRASTS = [("casepath", "hold_prompt"), ("casepath_checklist", "hold_prompt"), ("casepath_frontier_checklist", "hold_prompt_frontier"),
             ("casepath_frontier_checklist", "mer_hold_frontier"), ("casepath", "hold_prompt_frontier"), ("casepath", "mer_hold_frontier")]
SUBSETS = ["all", "ordinary", "denied_event", "open_event", "S", "O", "O: open branch fact only", "O: denied defining event",
           "O: open defining event"]
KINDS = ["unnecessary", "missed", "premature", "silent_skip", "held_req", "spurious_hold", "handed"]
MC = 200_000
SEED = 20261112


def spec_with_new():
    spec = copy.deepcopy(F.SPEC)
    for key, (label, model, runs, stem, prefix) in NEW.items():
        spec["designs"].append({
            "key": key, "label": label, "model": model, "regimes": ["tenancy", "theft"], "runs": runs,
            "store": {reg: {"path": f"{REL}/plans_{stem}-{reg}.json", "key": prefix + "|{case}|{run}", "field": "plan"}
                      for reg in ("tenancy", "theft")},
            "cost": {"method": "none"}})
    return spec


def in_sub(study, sub, cid):
    if sub == "all":
        return True
    if sub in study.spec["tenancy_subsets"]:
        return study.in_subset(cid, sub)
    t, o = P.subset_of(study, cid)
    return t == sub or o == sub


def ten_block(rows):
    n = len(rows)
    S = lambda k: sum(r[k] for r in rows)
    out = {"claim_runs": n, "claims": len({r["case"] for r in rows}),
           "strict_unsafe": S("strict_unsafe") / n, "all_dev": S("all_dev") / n,
           **{f"{k}_per_claim": S(k) / n for k in KINDS},
           "correct_hold_share": S("correct_hold") / S("ref_held") if S("ref_held") else None,
           "ref_held": S("ref_held"), "correct_hold": S("correct_hold"),
           "requested_share": S("requested") / S("req_now") if S("req_now") else None}
    return out


def theft_block(on, un):
    n, m = len(on), len(un)
    return {"pair_runs": n, "errors_per_pair": sum(r["errors"] for r in on) / n,
            "wrong_per_pair": sum(r["wrong"] for r in on) / n, "missed_per_pair": sum(r["missed"] for r in on) / n,
            "unresolved_pair_runs": m, "unchanged_share": sum(bool(r["stable"]) for r in un) / m,
            "premature_share": sum(bool(r["premature"]) for r in un) / m, "held_share": sum(bool(r["held"]) for r in un) / m}


def signflip_cases(d):
    d = np.asarray([x for x in d if abs(x) > 1e-12], float)
    if len(d) == 0:
        return 1.0, 0, "no non-zero difference"
    if len(d) <= 22:
        return float(s3.signflip_p(list(d))), len(d), "exact"
    rng = np.random.default_rng(SEED)
    obs = abs(d.sum())
    cnt = 0
    for i in range(0, MC, 20_000):
        S = rng.choice((-1.0, 1.0), size=(20_000, len(d)))
        cnt += int((np.abs(S @ d) >= obs - 1e-12).sum())
    return (1 + cnt) / (1 + MC), len(d), f"Monte Carlo {MC}"


def per_case(rows, key, field):
    g = defaultdict(list)
    for r in rows:
        g[r[key]].append(float(r[field]))
    return {k: sum(v) / len(v) for k, v in g.items()}


def contrast(study, rows_a, rows_b, key, field, cluster_key, name):
    va, vb = per_case(rows_a, key, field), per_case(rows_b, key, field)
    cases = sorted(set(va) & set(vb))
    d = [va[c] - vb[c] for c in cases]
    p, nz, how = signflip_cases(d)
    ca = s2.by_cluster(rows_a, cluster_key, lambda rs: sum(float(r[field]) for r in rs) / len(rs))
    cb = s2.by_cluster(rows_b, cluster_key, lambda rs: sum(float(r[field]) for r in rs) / len(rs))
    c = s3.run_contrast(ca, cb, name, False, "signflip")
    return {"cases": len(cases), "a_value": sum(va[c] for c in cases) / len(cases), "b_value": sum(vb[c] for c in cases) / len(cases),
            "diff_case_mean": sum(d) / len(d), "nonzero_cases": nz, "p_cases": p, "p_cases_method": how,
            "a_lower_cases": sum(x < -1e-12 for x in d), "a_higher_cases": sum(x > 1e-12 for x in d),
            "clusters": c["clusters"], "diff_cluster_mean": c["diff"], "diff_cluster_ci95": c["diff_ci"], "p_clusters": c["p"],
            "min_p_clusters": c["min_p"]}


def main():
    spec = spec_with_new()
    s3.configure(spec)
    study = s3.Study(spec, "fresh2", "confirm", s3.load_data("fresh2"))
    designs = OLD + list(NEW)
    status = {}
    for d in designs:
        for reg in ("tenancy", "theft"):
            ok = study.load(d, reg)
            st = study.status[(d, reg)]
            status[f"{d}/{reg}"] = {k: st.get(k) for k in ("status", "runs", "file", "missing_entries", "failed_outputs", "reason")}
            assert ok, (d, reg, st)
    res = {"label": "POST HOC, development data (Study 3's fresh2); study4/SPEC.md step 1; not a result", "status": status,
           "tenancy": {}, "theft": {}, "contrasts": {"tenancy": [], "theft": []}}
    for d in designs:
        rows = study.tenancy_rows(d)
        res["tenancy"][d] = {s: ten_block([r for r in rows if in_sub(study, s, r["case"])]) for s in SUBSETS}
        on, un = study.theft_rows(d)
        res["theft"][d] = theft_block(on, un)
    for a, b in CONTRASTS:
        ra, rb = study.tenancy_rows(a), study.tenancy_rows(b)
        for s in SUBSETS:
            fa = [r for r in ra if in_sub(study, s, r["case"])]
            fb = [r for r in rb if in_sub(study, s, r["case"])]
            for m in ("strict_unsafe", "all_dev"):
                c = contrast(study, fa, fb, "case", m, "cluster", f"S4BC|ten|{a}|{b}|{s}|{m}")
                res["contrasts"]["tenancy"].append({"a": a, "b": b, "subset": s, "measure": m, **c})
        (ona, una), (onb, unb) = study.theft_rows(a), study.theft_rows(b)
        for m, xa, xb in (("errors", ona, onb), ("stable", una, unb), ("premature", una, unb), ("held", una, unb)):
            c = contrast(study, xa, xb, "pair_id", m, "condition", f"S4BC|th|{a}|{b}|{m}")
            res["contrasts"]["theft"].append({"a": a, "b": b, "measure": m, **c})
    # per-case outputs of the new designs, for examples
    ex = {}
    for d, (_, _, runs, stem, prefix) in NEW.items():
        for reg in ("tenancy", "theft"):
            raw = json.loads((TMIS / REL / f"plans_{stem}-{reg}.json").read_text())
            ex[f"{d}/{reg}"] = {"entries": len(raw), "failed": sorted(k for k, v in raw.items() if v.get("plan") is None),
                                "failed_errors": sorted({str(v.get("error"))[:60] for v in raw.values() if v.get("plan") is None})}
    res["failed_outputs"] = ex
    res["inputs"] = dict(sorted(study.inputs.hashes.items()))
    (HERE / "REPORT.json").write_text(json.dumps(res, indent=1, sort_keys=True, ensure_ascii=False, default=float) + "\n")
    print("written", HERE / "REPORT.json")


if __name__ == "__main__":
    main()
