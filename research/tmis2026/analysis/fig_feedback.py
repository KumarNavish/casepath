"""Figures for the analyses asked for by outside feedback (post hoc): fig_share and fig_budget. No model calls.

    python3 fig_feedback.py [--png DIR] [fig_share] [fig_budget]

fig_share (F2): expected strict unsafe errors per claim against the share q of claims with an open fact or a denied or
open defining event (type O), as straight lines from each design's claim-run means on type S and type O
(analysis/study3_feedback.json). CasePath is the only saturated colour; the other designs one muted ink, labelled at
the line's end; 95% family-bootstrap bands for CasePath and the frontier single prompt. A vertical marker at the test's
own share; a second marker at REAL_SHARE when it is set (the share observed in real files; default None, not drawn).

fig_budget (F4): errors against cost per case (log axis), tenancy and theft. CasePath, checklist only, with the first
k = 1, 2, 3 readings (one line), Self-consistency with m = 1 ... 15 samples (one line), Rules in context and the
frontier single prompt as single points (hollow = frontier model, as fig_s6). Points labelled with k or m.

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
    # labels at the right end, spaced so that none overlaps
    order = sorted(ends, key=lambda d: ends[d][1])
    min_gap = 0.075 * top_y
    placed = []
    for d in order:
        yy = ends[d][1]
        if placed and yy - placed[-1] < min_gap:
            yy = placed[-1] + min_gap
        placed.append(yy)
        ax.annotate(LABELS[d], (1, ends[d][1]), xytext=(1.02, yy), textcoords="data", ha="left", va="center",
                    fontsize=th.NOTE, color=CP if d == "casepath" else th.INK, fontweight=th.BOLD if d == "casepath" else "normal",
                    annotation_clip=False,
                    arrowprops=dict(arrowstyle="-", color=LIGHT, lw=th.THIN, shrinkA=0, shrinkB=0) if abs(yy - ends[d][1]) > 1e-9 else None)
    for q, lab in ((q_test, f"this test ({100 * q_test:.0f}%)"), (REAL_SHARE, "real files" if REAL_SHARE is None else f"real files ({100 * REAL_SHARE:.0f}%)")):
        if q is None:
            continue
        ax.axvline(q, color=th.NEUTRAL, lw=th.THIN, zorder=0)
        ax.text(q, top_y, lab, fontsize=th.NOTE, color=th.INK, ha="center", va="bottom")
    th.save(fig, FIG / "fig_share.pdf", PREVIEW)


def fig_budget():
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
        ax.tick_params(length=2.5, pad=2)
        ax.set_ylabel(ylab, labelpad=3)
        ax.set_xlabel(xlab + " (log scale)", labelpad=3)
        ks = f4["readings"][regime]["by_k"]
        ms = f4["self_consistency"][regime]["by_m"]
        pts = f4["single_points"][regime]
        ymax = max([v[key] for v in ks.values()] + [v[key] for v in ms.values()] + [pts[d]["errors"] for d in ("ric", "ric_frontier")])
        ax.set_ylim(0, 0.5 * (int(ymax / 0.5) + 1))
        ax.text(0.0004, ax.get_ylim()[1] * 1.04, title, fontsize=th.TITLE, fontweight=th.BOLD, ha="left", va="bottom")
        xs = [ms[m]["cost_per_case_run"] for m in sorted(ms, key=int)]
        ys = [ms[m][key] for m in sorted(ms, key=int)]
        ax.plot(xs, ys, color=OTHER, lw=th.THICK, zorder=2)
        ax.scatter(xs, ys, s=14, color=OTHER, zorder=3)
        for j, (m, x, yv) in enumerate(zip(sorted(ms, key=int), xs, ys)):
            up = j % 2 == 0  # alternate above and below so that neighbouring labels do not touch
            ax.annotate(f"m={m}", (x, yv), xytext=(0, 5 if up else -5), textcoords="offset points", ha="center",
                        va="bottom" if up else "top", fontsize=th.NOTE, color=th.INK)
        ax.annotate("Self-consistency", (xs[-1], ys[-1]), xytext=(6, -2), textcoords="offset points", ha="left", va="top",
                    fontsize=th.NOTE, color=th.INK)
        xk = [ks[k]["cost_per_case_run"] for k in sorted(ks, key=int)]
        yk = [ks[k][key] for k in sorted(ks, key=int)]
        ax.plot(xk, yk, color=CP, lw=th.THICK, zorder=4)
        ax.scatter(xk, yk, s=20, color=CP, zorder=5)
        for k, x, yv in zip(sorted(ks, key=int), xk, yk):
            last = str(k) == str(max(ks, key=int))
            ax.annotate(f"k={k}", (x, yv), xytext=(6, 0) if last else (0, -6), textcoords="offset points",
                        ha="left" if last else "center", va="center" if last else "top", fontsize=th.NOTE, color=CP)
        ax.annotate("CasePath, checklist only", (xk[0], yk[0]), xytext=(-6, 0), textcoords="offset points", ha="right", va="center",
                    fontsize=th.NOTE, color=CP, fontweight=th.BOLD)
        for d, lab, hollow in (("ric", "Rules in context", False), ("ric_frontier", "Rules in context, frontier", True)):
            x, yv = pts[d]["cost_per_case_run"], pts[d]["errors"]
            ax.scatter([x], [yv], s=30, marker="o", facecolors="white" if hollow else OTHER, edgecolors=OTHER, linewidths=th.THICK, zorder=4)
            ax.annotate(lab, (x, yv), xytext=(5, -7), textcoords="offset points", ha="left", va="top", fontsize=th.NOTE, color=th.INK)
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
