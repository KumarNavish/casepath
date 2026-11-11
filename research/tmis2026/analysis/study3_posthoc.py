"""Study 3, post hoc (not part of ANALYSIS_PLAN_STUDY3.md; decided after the results were known). No model calls.

    python3 study3_posthoc.py      # writes study3_posthoc.json and study3_posthoc.md

Two analyses, and nothing else:

1. ReAct sensitivity. ReAct returned 40 failed outputs (23 tenancy, 17 theft), which the plan scores as empty plans.
   Here they are left out. Theft: a changed-fact pair-run is dropped, for both designs, when either of ReAct's two
   texts of that pair (unchanged and changed) failed in that run. Tenancy: a claim-run is dropped, for both designs,
   when ReAct's output for that claim and run failed. Same clusters (nine changed facts; 24 families), same cluster
   values (mean over the remaining rows), same tests and the same bootstrap settings as the planned contrasts:
   H4's ReAct contrast (H4.3) and the two planned tenancy contrasts against ReAct (S2c strict unsafe errors, S2f all
   deviations per claim).
2. H4's Self-consistency contrast (H4.1), cluster by cluster: the nine changed-fact values of both designs and their
   difference, with the sign-flip p recomputed from them, so that the reader can see why p is 0.0625.

Everything is computed with the functions of analysis/study3.py (which imports study2.py), not copies of them. Plans
are read from runs/study3/confirm through the same Study class and the same data guard as the planned analysis.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import study3 as s3  # noqa: E402

s2 = s3.s2
DATA, LABEL = "fresh2", "confirm"
OUT = HERE / "study3_posthoc"
LABEL_POSTHOC = "POST HOC: not part of ANALYSIS_PLAN_STUDY3.md"


def contrast(fa, fb, name, measure):
    hib = SPEC["measures"][measure]["higher_is_better"]
    c = s3.run_contrast(fa, fb, name, hib, "signflip")
    c["significant_at_0.05"] = s3.significant(c, SPEC["statistics"]["alpha"])
    return c


def mean(key):
    return lambda rs: sum(r[key] for r in rs) / len(rs)


def theft_react_sensitivity(study):
    on_pairs = [p for p in study.pairs if p["kind"] == "on"]
    runs = study.runs("react", "theft")
    order = [(p, r) for p in on_pairs for r in range(runs)]  # the order of study3.Study.theft_rows
    react_plans = study.plans[("react", "theft")]
    failed = lambda text, r: react_plans[text][r] is None
    keep = [not (failed(p["off"], r) or failed(p["variant"], r)) for p, r in order]
    rows = {}
    for d in ("casepath", "react"):
        on, _ = study.theft_rows(d)
        assert len(on) == len(order), "row order differs from study3.Study.theft_rows"
        for (p, r), row in zip(order, on):
            assert (row["condition"], row["run"]) == (p["condition"], r)
        rows[d] = [row for row, k in zip(on, keep) if k]
    cl = SPEC["regimes"]["theft"]["cluster"]
    fa = s2.by_cluster(rows["casepath"], cl, mean("errors"))
    fb = s2.by_cluster(rows["react"], cl, mean("errors"))
    planned = next(t for h in RES["hypotheses"] if h["id"] == "H4" for t in h["tests"] if t["b"] == "react")
    out = {"id": "H4.3 without ReAct's failed outputs", "regime": "theft", "measure": "errors",
           "a": "casepath", "b": "react", "pair_runs_total": len(order), "pair_runs_kept": sum(keep),
           "pair_runs_dropped": len(order) - sum(keep),
           "react_failed_texts": sum(p is None for v in react_plans.values() for p in v),
           "per_cluster_kept_pair_runs": {c: sum(1 for row in rows["react"] if row[cl] == c) for c in sorted(fa)},
           "result": contrast(fa, fb, "posthoc|H4.3|react_failed_out", "errors"),
           "planned": {k: planned[k] for k in ("a_value", "b_value", "diff", "diff_ci", "p", "clusters", "nonzero_clusters")}}
    out["react_errors_per_pair_kept"] = sum(r["errors"] for r in rows["react"]) / len(rows["react"])
    out["casepath_errors_per_pair_kept"] = sum(r["errors"] for r in rows["casepath"]) / len(rows["casepath"])
    return out


def tenancy_react_sensitivity(study):
    rr = study.tenancy_rows("react")
    react_plans = study.plans[("react", "tenancy")]
    drop = {(r["case"], r["run"]) for r in rr if react_plans[r["case"]][r["run"]] is None}
    rows = {d: [r for r in study.tenancy_rows(d) if (r["case"], r["run"]) not in drop] for d in ("casepath", "react")}
    out = []
    planned = {c["id"]: c["result"] for c in RES["secondary"]["contrasts"]}
    for cid, measure, fn in (("S2c", "strict_unsafe", s2.TEN_METRIC["strict_unsafe"]), ("S2f", "all_deviations", mean("all_dev"))):
        fa = s2.by_cluster(rows["casepath"], "cluster", fn)
        fb = s2.by_cluster(rows["react"], "cluster", fn)
        p = planned[cid]
        out.append({"id": f"{cid} without ReAct's failed outputs", "regime": "tenancy", "measure": measure,
                    "a": "casepath", "b": "react", "claim_runs_total": len(rr), "claim_runs_dropped": len(drop),
                    "claim_runs_kept": len(rr) - len(drop),
                    "families_with_a_dropped_claim_run": len({r["cluster"] for r in rr if (r["case"], r["run"]) in drop}),
                    "result": contrast(fa, fb, f"posthoc|{cid}|react_failed_out", measure),
                    "planned": {k: p[k] for k in ("a_value", "b_value", "diff", "diff_ci", "p", "clusters", "nonzero_clusters")}})
    return out


def h4_self_consistency_clusters(study):
    fa = study.clusters("casepath", "theft", "errors")
    fb = study.clusters("self_consistency", "theft", "errors")
    keys = sorted(set(fa) & set(fb))
    rows = [{"changed_fact": k, "casepath": fa[k], "self_consistency": fb[k], "difference": fa[k] - fb[k]} for k in keys]
    diffs = [r["difference"] for r in rows]
    planned = next(t for h in RES["hypotheses"] if h["id"] == "H4" for t in h["tests"] if t["b"] == "self_consistency")
    p = s3.signflip_p(diffs)
    assert abs(p - planned["p"]) < 1e-12, "recomputed p differs from the stored result"
    return {"id": "H4.1 by changed fact", "rows": rows, "favouring_casepath": sum(d < -1e-12 for d in diffs),
            "favouring_self_consistency": sum(d > 1e-12 for d in diffs), "zero": sum(abs(d) <= 1e-12 for d in diffs),
            "mean_difference": sum(diffs) / len(diffs), "signflip_p": p, "planned_p": planned["p"],
            "note": "Exact two-sided sign-flip test over 2^9 = 512 sign patterns: p is the share of patterns whose "
                    "absolute sum of differences is at least the observed one."}


def fmt(x, nd=3):
    return "–" if x is None else f"{x:.{nd}f}"


def pv(x):
    return "< 0.0001" if x < 0.0001 else f"{x:.4f}"


def markdown(res):
    L = {d["key"]: d["label"] for d in SPEC["designs"]}
    md = [f"# Study 3, post-hoc analyses (data `{res['data']}`, run label `{res['run_label']}`)", "","Generated by `analysis/study3_posthoc.py` with the functions of "
          "`analysis/study3.py`. No model calls. **These analyses are post hoc. They are not part of the "
          "pre-registered plan and do not change any hypothesis's status.**", "",
          "## 1. ReAct's failed outputs left out", "",
          "The plan scores a failed output as an empty plan. Here, a theft pair-run is dropped for both designs when either "
          "of ReAct's two texts failed in that run; a tenancy claim-run is dropped for both designs when ReAct's output failed. "
          "Same clusters, cluster values, tests and bootstrap settings as the planned contrasts.", "",
          "| Contrast | Rows kept | A | B | A value | B value | A − B | 95% interval | clusters / non-zero | p | planned A − B | planned p |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    items = [res["react_sensitivity"]["theft"]] + res["react_sensitivity"]["tenancy"]
    for it in items:
        c, p = it["result"], it["planned"]
        kept = (f"{it['pair_runs_kept']} of {it['pair_runs_total']} pair-runs" if "pair_runs_kept" in it
                else f"{it['claim_runs_kept']} of {it['claim_runs_total']} claim-runs")
        md.append(f"| {it['id']} ({SPEC['measures'][it['measure']]['label']}) | {kept} | {L[it['a']]} | {L[it['b']]} | "
                  f"{fmt(c['a_value'])} | {fmt(c['b_value'])} | {fmt(c['diff'])} | [{fmt(c['diff_ci'][0])}, {fmt(c['diff_ci'][1])}] | "
                  f"{c['clusters']} / {c['nonzero_clusters']} | {pv(c['p'])} | {fmt(p['diff'])} | {pv(p['p'])} |")
    t = res["react_sensitivity"]["theft"]
    md += ["", f"Theft: {t['react_failed_texts']} failed ReAct texts remove {t['pair_runs_dropped']} of {t['pair_runs_total']} "
           f"changed-fact pair-runs; kept pair-runs per changed fact: "
           + ", ".join(f"{k} {v}" for k, v in t["per_cluster_kept_pair_runs"].items()) + ".", ""]
    h = res["h4_self_consistency_by_fact"]
    md += ["## 2. H4's Self-consistency contrast, changed fact by changed fact", "",
           "| Changed fact | CasePath | Self-consistency | Difference |", "|---|---|---|---|"]
    md += [f"| {r['changed_fact']} | {fmt(r['casepath'])} | {fmt(r['self_consistency'])} | {fmt(r['difference'])} |" for r in h["rows"]]
    md += [f"| mean | | | {fmt(h['mean_difference'])} |", "",
           f"Differences favouring CasePath: {h['favouring_casepath']}; favouring Self-consistency: "
           f"{h['favouring_self_consistency']}; zero: {h['zero']}. Exact sign-flip p = {h['signflip_p']:.4f} "
           f"(stored result {h['planned_p']:.4f}). {h['note']}", ""]
    return "\n".join(md)


def main():
    global SPEC, RES
    SPEC = json.loads(s3.SPEC.read_text())
    RES = json.loads((HERE / f"study3_results_{DATA}_{LABEL}.json").read_text())
    s3.configure(SPEC)
    study = s3.Study(SPEC, DATA, LABEL, s3.load_data(DATA))
    for d in ("casepath", "react", "self_consistency"):
        for reg in ("tenancy", "theft"):
            assert study.load(d, reg), f"{d}/{reg} not loaded"
    res = {"label": LABEL_POSTHOC, "data": DATA, "run_label": LABEL, "posthoc": True,
           "react_sensitivity": {"theft": theft_react_sensitivity(study), "tenancy": tenancy_react_sensitivity(study)},
           "h4_self_consistency_by_fact": h4_self_consistency_clusters(study),
           "statistics": {"bootstrap_resamples": s2.B, "seed": s2.SEED, "test": "exact two-sided sign flip"},
           "inputs": dict(sorted(study.inputs.hashes.items()))}
    OUT.with_suffix(".json").write_text(json.dumps(res, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    OUT.with_suffix(".md").write_text(markdown(res) + "\n")
    print("written", OUT.with_suffix(".json"), "and", OUT.with_suffix(".md"))


if __name__ == "__main__":
    main()
