"""Figures for the analyses asked for by outside feedback (post hoc): fig_share and fig_budget. No model calls.

    python3 fig_feedback.py [--png DIR] [fig_share] [fig_budget]

fig_share (F2): expected strict unsafe errors per claim against the share q of claims with an open fact or a denied or
open defining event (type O), as straight lines from each design's claim-run means on type S and type O
(analysis/study3_feedback.json). CasePath is the only saturated colour; the other designs one muted ink, labelled at
the line's end; 95% family-bootstrap bands for CasePath and the frontier single prompt. A vertical marker at the test's
own share; a second marker at REAL_SHARE when it is set (the share observed in real files; default None, not drawn).

fig_budget (F4): errors against cost per case (log axis), tenancy and theft. CasePath, checklist only, with the first
k = 1, 2, 3 readings (one line), Self-consistency with m = 1 ... 15 samples (one line; m = 1 is the mean of single
samples from the 15 stored ones), Rules in context as registered (its own runs; a hollow diamond under the line's dots, because its value is
not the m = 1 value) and the frontier single prompt (one open circle). Only m = 1, 5, 15 and k = 1, 2, 3 are labelled;
label offsets are set by hand (BUDGET_NUDGE) and were checked for collisions with marks, lines and other labels.

Themed by figtheme.py, like fig_s6.py; direct labels, no legend box. Values come from study3_feedback.json only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import figtheme as th

HERE = Path(__file__).resolve().parent
FIG = HERE.parent / "paper" / "figures"
PREVIEW = None
REAL_SHARE = None          # set to the share of type-O files observed in real files (0-1); None: no marker
CP = th.REQUESTED
OTHER = "#6f6c67"
LIGHT = "#a9a6a0"
LABELS = {"casepath": "CasePath", "ric": "Rules in context", "ric_frontier": "Rules in context, frontier model",
          "self_consistency": "Self-consistency", "model_executes_rules": "Model executes rules"}


def load():
    res = json.loads((HERE / "study3_feedback.json").read_text())
    if res.get("posthoc") is not True:
        raise ValueError("study3_feedback.json is not labelled post hoc")
    return res


def fig_share():
    import matplotlib.pyplot as plt
    th.setup()
    res = load()
    f2 = res["F2"]
    y = f2["measures"]["strict_unsafe"]
    q_test = f2["q_test"]
    H = 3.0
    fig = plt.figure(figsize=(th.WIDTH, H))
    left, right, bottom, top = 0.48, 1.75, 0.42, 0.22
    ax = fig.add_axes([left / th.WIDTH, bottom / H, (th.WIDTH - left - right) / th.WIDTH, (H - bottom - top) / H])
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ends = {d: v["claim_run"] for d, v in y["means"].items()}
    ymax = max(max(v) for v in ends.values())
    hi_band = max(max(b["hi"]) for b in y["bands"].values())
    top_y = 0.5 * (int(max(ymax, hi_band) / 0.5) + 1)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, top_y)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1])
    ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"])
    ax.set_xlabel("share of claims with an open fact or a denied or open defining event", labelpad=3)
    ax.set_ylabel("expected strict unsafe errors per claim", labelpad=3)
    ax.tick_params(length=2.5, pad=2)
    grid = [i / 100 for i in range(101)]
    for d, col, alpha in (("ric_frontier", OTHER, 0.12), ("casepath", CP, 0.18)):
        b = y["bands"][d]
        ax.fill_between(grid, b["lo"], b["hi"], color=col, alpha=alpha, lw=0, zorder=1)
    for d in ("ric", "self_consistency", "model_executes_rules", "ric_frontier", "casepath"):
        s_, o_ = ends[d]
        col = CP if d == "casepath" else OTHER
        ax.plot([0, 1], [s_, o_], color=col, lw=th.THICK, solid_capstyle="round", zorder=3,
                ls=(0, (3, 1.6)) if d == "ric_frontier" else "-")
    # labels at the right end: spread symmetrically about their ends until none overlaps, each on a short (elbow) leader
    # from the line's end (labels start right of the elbow, so no leader crosses a label)
    order = sorted(ends, key=lambda d: ends[d][1])
    min_gap = 0.085 * top_y
    pos = {d: ends[d][1] for d in order}
    for _ in range(200):
        moved = False
        for lo_d, hi_d in zip(order, order[1:]):
            gap_ = pos[hi_d] - pos[lo_d]
            if gap_ < min_gap - 1e-9:
                push = (min_gap - gap_) / 2
                pos[lo_d] -= push
                pos[hi_d] += push
                moved = True
        if not moved:
            break
    x_end, x_elbow, x_text = 1.0, 1.03, 1.06
    for d in order:
        y_end, yy = ends[d][1], pos[d]
        ax.plot([x_end + 0.006, x_elbow, x_text - 0.008], [y_end, yy, yy], color=LIGHT, lw=th.THIN, clip_on=False,
                solid_capstyle="butt", zorder=2)
        ax.text(x_text, yy, LABELS[d], ha="left", va="center", fontsize=th.NOTE, clip_on=False,
                color=CP if d == "casepath" else th.INK, fontweight=th.BOLD if d == "casepath" else "normal")
    ax.tick_params(axis="x", pad=4)
    ax.tick_params(axis="y", pad=4)
    for q, lab in ((q_test, f"this test ({100 * q_test:.0f}%)"), (REAL_SHARE, "real files" if REAL_SHARE is None else f"real files ({100 * REAL_SHARE:.0f}%)")):
        if q is None:
            continue
        ax.axvline(q, color=th.NEUTRAL, lw=th.THIN, zorder=0)
        ax.text(q, top_y, lab, fontsize=th.NOTE, color=th.INK, ha="center", va="bottom")
    th.save(fig, FIG / "fig_share.pdf", PREVIEW)


# fig_budget label placement, by hand and checked for collisions: (dx, dy, ha, va) in points from the point
M_SHOWN = ("1", "5", "15")
BUDGET_NUDGE = {"m": {"1": (0, -5, "center", "top"), "5": (2, 5, "left", "bottom"), "15": (0, 5, "center", "bottom")},
                "k": {"1": (0, 5, "center", "bottom"), "2": (-3, -4, "right", "top"), "3": (6, 0, "left", "center")},
                "ric": (0, 6, "center", "bottom"), "ric_frontier": (0, -7, "center", "top")}
BUDGET_NUDGE_THEFT = {"m": {"1": (0, 5, "center", "bottom")}, "ric": (0, -6, "center", "top"),
                      "ric_frontier": (4, -6, "left", "top")}


def _nudge(regime, *path):
    over = BUDGET_NUDGE_THEFT if regime == "theft" else {}
    v_over, v = over, BUDGET_NUDGE
    for p in path:
        v = v[p]
        v_over = v_over.get(p, {}) if isinstance(v_over, dict) else {}
    return v_over if isinstance(v_over, tuple) else v


def fig_budget():
    """Errors against cost per case (log axis): readings k = 1, 2, 3 against self-consistency m = 1 ... 15."""
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FixedLocator, NullLocator
    th.setup()
    res = load()
    f4 = res["F4"]
    H = 4.6
    fig = plt.figure(figsize=(th.WIDTH, H))
    left, right = 0.52, 0.15
    ph, gapv, bottom = 1.55, 0.62, 0.46
    panels = (("tenancy", "Tenancy", "strict unsafe errors per claim", "strict_unsafe_per_claim", "USD per claim"),
              ("theft", "Theft", "wrong + missed changes per pair", "errors_per_pair", "USD per text"))
    note = dict(fontsize=th.NOTE, color=th.INK)
    for i, (regime, title, ylab, key, xlab) in enumerate(panels):
        y0 = bottom + (1 - i) * (ph + gapv)
        ax = fig.add_axes([left / th.WIDTH, y0 / H, (th.WIDTH - left - right) / th.WIDTH, ph / H])
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.set_xscale("log")
        ax.set_xlim(0.0004, 0.02)
        ticks = [0.0005, 0.001, 0.002, 0.005, 0.01, 0.02]
        ax.xaxis.set_major_locator(FixedLocator(ticks))
        ax.xaxis.set_minor_locator(NullLocator())
        ax.set_xticklabels([f"{t:g}" for t in ticks])
        ax.tick_params(length=2.5, pad=3)
        ax.set_ylabel(ylab, labelpad=3)
        ax.set_xlabel(xlab + " (log scale)", labelpad=3)
        ks = f4["readings"][regime]["by_k"]
        ms = f4["self_consistency"][regime]["by_m"]
        pts = f4["single_points"][regime]
        ymax = max([v[key] for v in ks.values()] + [v[key] for v in ms.values()] + [pts[d]["errors"] for d in ("ric", "ric_frontier")])
        ax.set_ylim(0, 0.5 * (int(ymax / 0.5) + 1))
        ax.text(0.0004, ax.get_ylim()[1] * 1.04, title, fontsize=th.TITLE, fontweight=th.BOLD, ha="left", va="bottom")

        def label(s_, xy, nd, **kw):
            dx, dy, ha, va = nd
            ax.annotate(s_, xy, xytext=(dx, dy), textcoords="offset points", ha=ha, va=va, **{**note, **kw})

        # Self-consistency: m = 1 ... 15 samples of the single prompt, majority vote; m = 1 is the mean of single samples
        m_sorted = sorted(ms, key=int)
        xs = [ms[m]["cost_per_case_run"] for m in m_sorted]
        ys = [ms[m][key] for m in m_sorted]
        ax.plot(xs, ys, color=OTHER, lw=th.THICK, zorder=2)
        ax.scatter(xs, ys, s=14, color=OTHER, zorder=3)
        for m, x, yv in zip(m_sorted, xs, ys):
            if m in M_SHOWN:
                label(f"m = {m}", (x, yv), _nudge(regime, "m", m))
        label("Self-consistency", (xs[-1], ys[-1]), (7, 0, "left", "center"))
        # Rules in context as registered (its own three runs): a hollow diamond under the dots, since it is not the m = 1 point
        x, yv = pts["ric"]["cost_per_case_run"], pts["ric"]["errors"]
        ax.scatter([x], [yv], s=26, marker="D", facecolors="white", edgecolors=OTHER, linewidths=th.THICK * 0.85, zorder=2.5)
        label("Rules in context", (x, yv), _nudge(regime, "ric"))
        # the frontier single prompt: one open circle
        x, yv = pts["ric_frontier"]["cost_per_case_run"], pts["ric_frontier"]["errors"]
        ax.scatter([x], [yv], s=30, marker="o", facecolors="white", edgecolors=OTHER, linewidths=th.THICK, zorder=4)
        label("Rules in context, frontier model", (x, yv), _nudge(regime, "ric_frontier"))
        # CasePath, checklist only, with the first k readings
        k_sorted = sorted(ks, key=int)
        xk = [ks[k]["cost_per_case_run"] for k in k_sorted]
        yk = [ks[k][key] for k in k_sorted]
        ax.plot(xk, yk, color=CP, lw=th.THICK, zorder=4)
        ax.scatter(xk, yk, s=20, color=CP, zorder=5)
        for k, x, yv in zip(k_sorted, xk, yk):
            label(f"k = {k}", (x, yv), _nudge(regime, "k", k), color=CP)
        label("CasePath, checklist only", (xk[0], yk[0]), (-7, 0, "right", "center"), color=CP, fontweight=th.BOLD)
    th.save(fig, FIG / "fig_budget.pdf", PREVIEW)


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--png" in args:
        PREVIEW = args[args.index("--png") + 1]
        Path(PREVIEW).mkdir(parents=True, exist_ok=True)
    only = [a for a in args if a.startswith("fig_")]
    for f in only or ["fig_share", "fig_budget"]:
        globals()[f]()
    print("written to", FIG)
