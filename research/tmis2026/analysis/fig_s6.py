"""Section 6 figures: fig_main and fig_cost (Study 3, data fresh2, run label confirm). No model calls.

    python3 fig_s6.py [--png DIR] [fig_main] [fig_cost]

fig_main: every design in every cell of model x data set, as a 2 x 2 small multiple (rows: tenancy, strict unsafe errors
per claim; theft, wrong + missed changes per pair; columns: the cost-efficient and the frontier model, read from each
design's model in the results file). Each row of panels shares one row order (the fixed ORDER) and one x scale; a design
that did not run in a cell leaves its row empty. Dot = the design's mean (the mean of its cluster values, as in the
analysis); bar = 95% cluster-bootstrap interval of that mean, computed here from the stored plans with the analysis's
own resampling (study2.paired_bootstrap with the spec's resamples and seed; the clusters are the 24 families and the
nine changed facts). The values are checked against the results file. CasePath is the only saturated colour; the
frontier-model product row (checklist only, one run) has an open marker and no bar. Two-valued rows are left out.

fig_cost: what each design buys per dollar. Two panels (tenancy above, theft below): x = cost per case from the results
file (log axis), y = the same errors and intervals as fig_main, from zero. Same colours and markers as fig_main;
labels placed by hand (NUDGE) so that none overlaps. Two-valued rows are left out (no model calls, no cost).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import figtheme as th
import study3 as s3

HERE = Path(__file__).resolve().parent
FIG = HERE.parent / "paper" / "figures"
RES = json.loads((HERE / "study3_results_fresh2_confirm.json").read_text())
SPEC = json.loads(s3.SPEC.read_text())
PREVIEW = None

CP = th.REQUESTED            # the one saturated colour: CasePath
OTHER = "#6f6c67"            # every other design: one muted ink
LIGHT = "#a9a6a0"            # notes and empty rows
GREY_TEXT = "#6f6c67"        # heading of the agents that cannot decide

# one fixed order for every Study 3 figure: CasePath and its parts, same-model baselines, frontier-model rows last
ORDER = [("casepath", "CasePath"), ("casepath_checklist", "CasePath, checklist only"),
         ("core", "Core (two readings, outside the product)"),
         ("ric", "Rules in context"), ("self_consistency", "Self-consistency"),
         ("model_executes_rules", "Model executes rules"), ("react", "ReAct"),
         ("ric_original", "Rules in context, original rules"),
         ("ric_frontier", "Rules in context, frontier model"),
         ("ric_original_frontier", "Rules in context, original rules, frontier model"),
         ("casepath_frontier_checklist", "CasePath, checklist only,\non the frontier model (one run)")]
FRONTIER = {k for k, d in RES["designs"].items() if d["model"] == "gpt-6.1-terra"}


def _save(fig, name):
    th.save(fig, FIG / f"{name}.pdf", PREVIEW)


def design_intervals():
    """{regime: {design: (mean, lo, hi)}} from the stored plans, with the analysis's own functions and settings."""
    s3.configure(SPEC)
    study = s3.Study(SPEC, "fresh2", "confirm", s3.load_data("fresh2"))
    out = {}
    for regime, measure, key in (("tenancy", "strict_unsafe", "strict_unsafe_per_claim"), ("theft", "errors", "errors_per_pair")):
        out[regime] = {}
        for d, _ in ORDER:
            if regime not in RES["designs"][d]["regimes"]:
                continue
            cl = study.clusters(d, regime, measure)
            mean = sum(cl.values()) / len(cl)
            stored = RES["designs"][d]["regimes"][regime]["measures"][key]
            assert abs(mean - stored) < 1e-9, (d, regime, mean, stored)
            boot = s3.s2.paired_bootstrap(cl, f"fig_main|{regime}|{d}")
            out[regime][d] = (mean, s3.s2.quantile(boot, 0.025), s3.s2.quantile(boot, 0.975))
    return out


# fig_main as a 2 x 2 small multiple: rows = data set, columns = model. Each row of panels shares one row order (the
# fixed ORDER, restricted to the designs that ran on that data set) and one x scale, so a design reads across models.
MAIN_ROWS = [("casepath", "casepath", "CasePath"), ("casepath_checklist", "casepath_frontier_checklist", "CasePath, checklist only"),
             ("core", None, "Core (two readings, outside the product)"), ("ric", "ric_frontier", "Rules in context"),
             ("self_consistency", None, "Self-consistency"), ("model_executes_rules", None, "Model executes rules"),
             ("react", None, "ReAct"), ("ric_original", "ric_original_frontier", "Rules in context, original rules")]
ONE_RUN = {"casepath_frontier_checklist"}     # one run per case: no interval, open marker
CASEPATH = {"casepath", "casepath_checklist", "casepath_frontier_checklist"}


def fig_main():
    """Every design in every cell of model x data set: dot = mean over clusters, bar = 95% cluster-bootstrap interval;
    the one-run frontier product row has an open marker and no bar."""
    import matplotlib.pyplot as plt
    th.setup()
    iv = design_intervals()
    regimes = (("tenancy", "Tenancy", "strict unsafe errors per claim"), ("theft", "Theft", "wrong + missed changes per pair"))
    columns = (("gpt-6-luna", "Cost-efficient model"), ("gpt-6.1-terra", "Frontier model"))
    rows = {}
    for regime, _, _ in regimes:
        rows[regime] = [r for r in MAIN_ROWS if r[0] in iv[regime] or (r[1] and r[1] in iv[regime])]
    for (d_ce, d_fr, _) in MAIN_ROWS:      # the column a design sits in is its model, read from the results file
        assert RES["designs"][d_ce]["model"] == columns[0][0]
        assert d_fr is None or d_fr == "casepath" or RES["designs"][d_fr]["model"] == columns[1][0]
    row = 0.19
    lab_w, gap, right = 1.92, 0.30, 0.22
    pw = (th.WIDTH - lab_w - gap - right) / 2
    head, xlab_h, between = 0.36, 0.36, 0.26   # column heads above; x label below each row of panels
    ph = {r: len(rows[r]) * row for r, _, _ in regimes}
    H = head + ph["tenancy"] + xlab_h + between + ph["theft"] + xlab_h
    fig = plt.figure(figsize=(th.WIDTH, H))
    ytop = H - head
    for ri, (regime, title, xlabel) in enumerate(regimes):
        rr = rows[regime]
        n = len(rr)
        y0 = ytop - ph[regime]
        hi = max(v[2] for v in iv[regime].values())
        xmax = 0.5 * (int(hi / 0.5) + 1)
        fig.text(0.02 / th.WIDTH, (ytop + 0.16) / H, title, fontsize=th.TITLE, fontweight=th.BOLD, ha="left", va="bottom")
        for ci, (model, mtitle) in enumerate(columns):
            x0 = lab_w + ci * (pw + gap)
            ax = fig.add_axes([x0 / th.WIDTH, y0 / H, pw / th.WIDTH, ph[regime] / H])
            ax.set_ylim(n - 0.5, -0.5)
            ax.set_xlim(0, xmax)
            ax.set_xticks([k * 0.5 for k in range(int(xmax / 0.5) + 1)])
            ax.set_xticklabels([f"{k * 0.5:g}" for k in range(int(xmax / 0.5) + 1)])
            for s in ("top", "right", "left"):
                ax.spines[s].set_visible(False)
            ax.tick_params(axis="y", length=0)
            ax.tick_params(axis="x", length=2.5, pad=2)
            ax.set_yticks(range(n))
            if ci == 0:
                ax.set_yticklabels([lab for _, _, lab in rr])
                for t, r in zip(ax.get_yticklabels(), rr):
                    if r[0] in CASEPATH:
                        t.set_color(CP)
                        if r[0] == "casepath":
                            t.set_fontweight(th.BOLD)
            else:
                ax.set_yticklabels([""] * n)
            if ri == 0:
                fig.text(x0 / th.WIDTH, (ytop + 0.16) / H, mtitle, fontsize=th.TITLE, fontweight=th.BOLD, ha="left", va="bottom")
            for j in range(n):
                ax.axhline(j, color=th.NEUTRAL, lw=th.THIN * 0.6, alpha=0.5, zorder=0)
            ref = None
            for j, r in enumerate(rr):
                d = r[ci] if ci == 0 else r[1]
                if ci == 1 and d == "casepath":
                    d = None                    # the full product did not run on the frontier model
                if d is None or d not in iv[regime]:
                    continue                    # not run on this model: the row stays empty
                mean, lo, hi_ = iv[regime][d]
                col = CP if d in CASEPATH else OTHER
                if d in ("casepath", "casepath_frontier_checklist"):
                    ref = mean
                if d in ONE_RUN:
                    ax.scatter([mean], [j], s=30, marker="o", facecolors="white", edgecolors=col, linewidths=th.THICK, zorder=3)
                    ax.text(mean + 0.06 * xmax, j, f"{mean:.2f}, one run", fontsize=th.NOTE, color=col, va="center", ha="left")
                    continue
                ax.plot([lo, hi_], [j, j], color=col, lw=th.THICK, solid_capstyle="round", zorder=2)
                ax.scatter([mean], [j], s=30, marker="o", facecolors=col, edgecolors=col, linewidths=th.THICK, zorder=3)
                ax.text(hi_ + 0.035 * xmax, j, f"{mean:.2f}", fontsize=th.NOTE, color=col, va="center", ha="left")
            if ref is not None:                  # the product's value as a faint reference down the panel
                ax.axvline(ref, color=CP, lw=th.THIN, alpha=0.35, zorder=1)
        fig.text((lab_w + pw + gap / 2) / th.WIDTH, (y0 - xlab_h + 0.02) / H, xlabel, fontsize=th.LABEL, ha="center",
                 va="bottom")
        ytop = y0 - xlab_h - between
    _save(fig, "fig_main")


# fig_cost: short labels (the caption names them in full); offsets in points, chosen by hand so that no label overlaps
COST_LABEL = {"casepath": "CasePath", "casepath_checklist": "checklist only", "core": "Core",
              "ric": "Rules in context", "self_consistency": "Self-consistency", "model_executes_rules": "Model executes rules",
              "react": "ReAct", "ric_original": "Rules in context, original rules",
              "ric_frontier": "Rules in context, frontier", "ric_original_frontier": "Rules in context, original rules, frontier",
              "casepath_frontier_checklist": "checklist only, on the frontier model (one run)"}
# Label placement, by hand: (dx, dy, ha) in points from the point, or ("at", x, y, ha, leader) in data coordinates
# (x in USD, y in errors), with a thin leader line to the point when leader is True.
NUDGE = {"tenancy": {"casepath": (-7, 0, "right"), "casepath_checklist": (-7, 0, "right"),
                     "ric": ("at", 0.00072, 3.3, "left", False), "self_consistency": (-7, 0, "right"),
                     "model_executes_rules": (7, 0, "left"), "react": (7, 0, "left"), "ric_frontier": (7, 0, "left"),
                     "casepath_frontier_checklist": ("at", 0.0225, 0.95, "right", True)},
         "theft": {"casepath": (-7, 0, "right"), "casepath_checklist": (6, -9, "left"), "core": (-7, 0, "right"),
                   "ric": (7, 3, "left"), "self_consistency": (-7, 0, "right"), "model_executes_rules": (7, 2, "left"),
                   "react": (7, -3, "left"), "ric_original": ("at", 0.00074, 1.02, "left", False),
                   "ric_frontier": ("at", 0.0047, 1.12, "left", False),
                   "ric_original_frontier": ("at", 0.0026, 0.28, "right", True),
                   "casepath_frontier_checklist": ("at", 0.0386, 1.45, "right", False)}}


def fig_cost():
    """Errors against cost per case: one point per design (log cost axis), 95% interval as a vertical line."""
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FixedLocator, NullLocator
    th.setup()
    iv = design_intervals()
    H = 5.0
    fig = plt.figure(figsize=(th.WIDTH, H))
    left, right = 0.52, 0.12
    panels = (("tenancy", "Tenancy", "strict unsafe errors per claim", "USD per claim"),
              ("theft", "Theft", "wrong + missed changes per pair", "USD per text"))
    ph, gapv, bottom = 1.72, 0.62, 0.46
    for i, (regime, title, ylab, xlab) in enumerate(panels):
        y0 = bottom + (1 - i) * (ph + gapv)
        ax = fig.add_axes([left / th.WIDTH, y0 / H, (th.WIDTH - left - right) / th.WIDTH, ph / H])
        for s_ in ("top", "right"):
            ax.spines[s_].set_visible(False)
        ax.set_xscale("log")
        ax.set_xlim(0.0004, 0.06)
        ticks = [0.0005, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05]
        ax.xaxis.set_major_locator(FixedLocator(ticks))
        ax.xaxis.set_minor_locator(NullLocator())
        ax.set_xticklabels([f"{t:g}" for t in ticks])
        hi = max(v[2] for v in iv[regime].values())
        ax.set_ylim(0, 0.5 * (int(hi / 0.5) + 1))
        ax.set_yticks([k * 0.5 for k in range(int(hi / 0.5) + 2)])
        ax.set_yticklabels([f"{k * 0.5:g}" for k in range(int(hi / 0.5) + 2)])
        ax.tick_params(length=2.5, pad=2)
        ax.set_ylabel(ylab, labelpad=3)
        ax.set_xlabel(xlab + " (log scale)", labelpad=3)
        ax.text(0.0004, ax.get_ylim()[1] * 1.04, title, fontsize=th.TITLE, fontweight=th.BOLD, ha="left", va="bottom")
        for d, _ in ORDER:
            if d not in iv[regime]:
                continue
            mean, lo, hi_ = iv[regime][d]
            x = RES["designs"][d]["regimes"][regime]["cost"]["cost_per_case_run"]
            col = CP if d == "casepath" else OTHER
            ax.plot([x, x], [lo, hi_], color=col, lw=th.THICK, solid_capstyle="round", zorder=2, alpha=0.9)
            ax.scatter([x], [mean], s=30, marker="o", facecolors="white" if d in FRONTIER else col, edgecolors=col,
                       linewidths=th.THICK, zorder=3)
            nd = NUDGE[regime][d]
            style = dict(fontsize=th.NOTE, color=CP if d == "casepath" else th.INK, zorder=4,
                         fontweight=th.BOLD if d == "casepath" else "normal", va="center")
            if nd[0] == "at":
                _, tx, ty, ha, leader = nd
                ax.annotate(COST_LABEL[d], (x, mean), xytext=(tx, ty), textcoords="data", ha=ha, **style,
                            arrowprops=dict(arrowstyle="-", color=LIGHT, lw=th.THIN, shrinkA=1, shrinkB=4) if leader else None)
            else:
                dx, dy, ha = nd
                ax.annotate(COST_LABEL[d], (x, mean), xytext=(dx, dy), textcoords="offset points", ha=ha, **style)
    _save(fig, "fig_cost")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--png" in args:
        PREVIEW = args[args.index("--png") + 1]
        Path(PREVIEW).mkdir(parents=True, exist_ok=True)
    only = [a for a in args if a.startswith("fig_")]
    for f in only or ["fig_main", "fig_cost"]:
        globals()[f]()
    print("written to", FIG)
