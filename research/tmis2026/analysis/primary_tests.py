"""Pre-specified primary contrasts H1-H5 per model, with Holm correction.

ANALYSIS_PLAN.md fixes gpt-6.1-terra as the primary model; gpt-6-luna is the
pre-registered model-sensitivity analysis. Holm-adjusted p-values are reported
within the primary family (terra, five tests, exactly as planned), within luna,
and across all ten tests. Each row also carries the paired cluster-bootstrap 95%
interval of the difference, the cluster counts, the minimum attainable two-sided
p-value and the direction of the effect (computed in analyze.py)."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TAGS = ("gpt-6.1-terra", "gpt-6-luna")
PRIMARY = [("H1", "tenancy", "H1", "H1 unsafe errors, CP-exact vs B1"),
           ("H2", "tenancy", "H2", "H2 deferrals, CP vs B1"),
           ("H3", "theft", "H3_vs_R", "H3 wrong changes, CP vs R"),
           ("H4", "theft", "H4_vs_R", "H4 premature or changed, CP vs R"),
           ("H5", "tenancy", "H5", "H5 test-retest, CP-exact vs B1")]
# Contrasts the plan promises beyond the five Holm-corrected ones, and post-hoc sensitivities.
SECONDARY = [("H1_strict", "tenancy", "H1_strict", "H1 sensitivity (post hoc): handed-over documents counted as missed"),
             ("H1_vs_SC3", "tenancy", "H1_vs_SC3", "H1 against majority-of-3 rules in context"),
             ("H2b", "tenancy", "H2b_deferred", "H2 second part: CP-exact vs CP deferrals"),
             ("H2b_unsafe", "tenancy", "H2b_unsafe", "H2 second part: CP-exact vs CP unsafe errors"),
             ("H3_D", "theft", "H3_vs_D", "H3 wrong changes, CP vs D (planned comparator)"),
             ("H3_SC3", "theft", "H3_vs_R-SC3", "H3 wrong changes, CP vs majority-of-3 R"),
             ("H3_dedup", "theft", "H3dedup_vs_R", "H3 sensitivity (post hoc): off-plan errors counted once per story x run"),
             ("H3_dedup_D", "theft", "H3dedup_vs_D", "H3 sensitivity (post hoc) against D"),
             ("H4_D", "theft", "H4_vs_D", "H4 premature or changed, CP vs D (planned comparator)"),
             ("H5_theft_R", "theft", "H5_vs_R", "H5 test-retest on theft texts, CP vs R (planned)"),
             ("H5_theft_D", "theft", "H5_vs_D", "H5 test-retest on theft texts, CP vs D (planned)")]


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i]); adj = [0.0] * len(ps); run = 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i])); adj[i] = run
    return adj


def row(key, c, label):
    return {"key": key, "test": label, "a": c["a"], "b": c["b"], "metric": c["metric"], "p": c["p_signflip"],
            "a_value": c["a_value"], "b_value": c["b_value"], "diff": c.get("diff", c.get("diff_mean_over_conditions")),
            "diff_ci": c["diff_ci"], "clusters": c["clusters"], "nonzero_clusters": c["nonzero_clusters"],
            "min_p_design": c["min_p_design"], "min_p_given_nonzero": c["min_p_given_nonzero"],
            "direction": c["direction"], "favours": c["favours"]}


out, every = {}, []
for tag in TAGS:
    res = json.loads((HERE / f"results_{tag}.json").read_text())
    named = {"tenancy": res["tenancy"]["_named"], "theft": res["theft"]["_named"]}
    rows = [row(k, named[exp][n], lab) for k, exp, n, lab in PRIMARY]
    for r, q in zip(rows, holm([r["p"] for r in rows])):
        r["p_holm"] = q  # within this model's five tests (for terra: the pre-registered primary family)
        if r["key"] == "H5":
            r["retest_diff"] = r["diff"]
    out[tag] = rows
    every += rows
    out[tag + "|secondary"] = [row(k, named[exp][n], lab) for k, exp, n, lab in SECONDARY if n in named[exp]]
for r, q in zip(every, holm([r["p"] for r in every])):
    r["p_holm_all10"] = q
(HERE / "primary_tests.json").write_text(json.dumps(out, indent=1))
print(json.dumps({t: [(r["key"], round(r["p"], 5), round(r["p_holm"], 5), round(r["p_holm_all10"], 5)) for r in out[t]] for t in TAGS}, indent=1))
