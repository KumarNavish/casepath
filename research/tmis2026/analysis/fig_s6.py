"""Section 6 figures: fig_main and fig_agents (Study 3, data fresh2, run label confirm). No model calls.

    python3 fig_s6.py [--png DIR]

fig_main: CasePath against every design on both regimes. Left tenancy (strict unsafe errors per claim), right theft
(wrong + missed changes per pair), one shared row order. Dot = the design's mean (the mean of its cluster values, as in
the analysis); bar = 95% cluster-bootstrap interval of that mean, computed here from the stored plans with the
analysis's own resampling (study2.paired_bootstrap with the spec's resamples and seed; the clusters are the 24 families
and the nine changed facts). The values are checked against the results file. CasePath is the only saturated colour;
designs on the frontier model have an open marker. Two-valued rows are left out (they are in the open-facts table).

fig_agents: the full product's cost per case by agent on each regime, as horizontal bars from zero, coloured by whether
the agent can decide the checklist (spec: deciding_agents); a last row stacks the whole per-case cost. Reference lines:
the checklist-only cost per case and the frontier single prompt's cost per case. All values from the results file.
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
         ("casepath_frontier_checklist", "CasePath, checklist only, frontier model (one run)")]
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


def fig_main():
    import matplotlib.pyplot as plt
    th.setup()
    iv = design_intervals()
    n = len(ORDER)
    row = 0.205
    H = 0.46 + n * row + 0.42
    fig = plt.figure(figsize=(th.WIDTH, H))
    lab_w = 2.12                              # inches for the row labels
    gap, right = 0.30, 0.10
    pw = (th.WIDTH - lab_w - gap - right) / 2
    bottom, top = 0.42, 0.46
    axes = []
    panels = (("tenancy", "Tenancy", "strict unsafe errors per claim"), ("theft", "Theft", "wrong + missed changes per pair"))
    for i, (regime, title, xlabel) in enumerate(panels):
        x0 = lab_w + i * (pw + gap)
        ax = fig.add_axes([x0 / th.WIDTH, bottom / H, pw / th.WIDTH, (H - bottom - top) / H])
        axes.append(ax)
        ax.set_ylim(n - 0.5, -0.5)
        hi = max(v[2] for v in iv[regime].values())
        step = 0.5
        xmax = step * (int(hi / step) + 1)
        ax.set_xlim(0, xmax)
        ax.set_xticks(range(int(xmax) + 1))
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.tick_params(axis="y", length=0)
        ax.tick_params(axis="x", length=2.5, pad=2)
        ax.set_xlabel(xlabel, labelpad=3)
        ax.text(0, -0.5 - 0.95, title, fontsize=th.TITLE, fontweight=th.BOLD, ha="left", va="bottom",
                transform=ax.transData, clip_on=False)
        ax.set_yticks(range(n))
        ax.set_yticklabels([lab for _, lab in ORDER] if i == 0 else [""] * n)
        if i == 0:
            for t, (d, _) in zip(ax.get_yticklabels(), ORDER):
                if d == "casepath":
                    t.set_fontweight(th.BOLD)
                    t.set_color(CP)
        # the CasePath value as a faint reference down the panel
        cpv = iv[regime]["casepath"][0]
        ax.axvline(cpv, color=CP, lw=th.THIN, alpha=0.35, zorder=1)
        for j, (d, _) in enumerate(ORDER):
            if d not in iv[regime]:
                ax.text(0.98 * xmax, j, "theft only", fontsize=th.NOTE, color=LIGHT, va="center", ha="right")
                continue
            mean, lo, hi_ = iv[regime][d]
            col = CP if d == "casepath" else OTHER
            ax.plot([lo, hi_], [j, j], color=col, lw=th.THICK, solid_capstyle="round", zorder=2)
            open_ = d in FRONTIER
            ax.scatter([mean], [j], s=30, marker="o", facecolors="white" if open_ else col, edgecolors=col,
                       linewidths=th.THICK, zorder=3)
            ax.text(hi_ + 0.025 * xmax, j, f"{mean:.2f}", fontsize=th.NOTE, color=col, va="center", ha="left")
    # bracket separating the frontier-model rows
    jf = min(j for j, (d, _) in enumerate(ORDER) if d in FRONTIER) - 0.5
    for ax in axes:
        ax.axhline(jf, color=th.NEUTRAL, lw=th.THIN, zorder=0)
    _save(fig, "fig_main")


AGENT_ROWS = [("router", "Router"), ("claim_reader", "Claim reader"), ("source_checker", "Source checker"),
              ("document_finder", "Document finder"), ("process_builder", "Process builder"),
              ("result_checker", "Result checker")]


def fig_agents():
    import matplotlib.pyplot as plt
    th.setup()
    deciding = set(SPEC["deciding_agents"])
    dec = [a for a in AGENT_ROWS if a[0] in deciding]
    rest = [a for a in AGENT_ROWS if a[0] not in deciding]
    # rows: a group heading, its agents; the second heading, its agents; then the whole cost per case
    layout, y = [], 0.0
    for head, group, col in (("can decide the checklist", dec, CP), ("cannot decide the checklist", rest, GREY_TEXT)):
        layout.append(("head", y, head, col)); y += 0.85
        for a, lab in group:
            layout.append(("agent", y, lab, a)); y += 1
        y += 0.25
    layout.append(("total", y + 0.15, "All calls of a case", None))
    ymax = y + 0.15
    row = 0.20
    H = 0.70 + (ymax + 1.2) * row + 0.44
    fig = plt.figure(figsize=(th.WIDTH, H))
    lab_w, gap, right = 1.42, 0.30, 0.16
    pw = (th.WIDTH - lab_w - gap - right) / 2
    bottom, top = 0.44, 0.70
    for i, (regime, title, unit) in enumerate((("tenancy", "Tenancy", "USD per claim"), ("theft", "Theft", "USD per text"))):
        c = RES["designs"]["casepath"]["regimes"][regime]["cost"]
        groups = c["by_group_per_case_run"]
        total = c["cost_per_case_run"]
        check = RES["designs"]["casepath_checklist"]["regimes"][regime]["cost"]["cost_per_case_run"]
        front = RES["designs"]["ric_frontier"]["regimes"][regime]["cost"]["cost_per_case_run"]
        x0 = lab_w + i * (pw + gap)
        ax = fig.add_axes([x0 / th.WIDTH, bottom / H, pw / th.WIDTH, (H - bottom - top) / H])
        ax.set_ylim(ymax + 0.6, -0.5)
        xmax = total * 1.22
        ax.set_xlim(0, xmax)
        for s_ in ("top", "right", "left"):
            ax.spines[s_].set_visible(False)
        ax.tick_params(axis="y", length=0)
        ax.tick_params(axis="x", length=2.5, pad=2)
        ax.set_xlabel(unit, labelpad=3)
        ax.xaxis.set_major_locator(plt.MaxNLocator(3))
        ax.text(0, -2.15, title, fontsize=th.TITLE, fontweight=th.BOLD, ha="left", va="bottom", clip_on=False)
        ax.set_yticks([l[1] for l in layout])
        ax.set_yticklabels([l[2] for l in layout] if i == 0 else [""] * len(layout))
        if i == 0:
            for t, l in zip(ax.get_yticklabels(), layout):
                if l[0] == "head":
                    t.set_color(l[3]); t.set_fontweight(th.BOLD); t.set_fontsize(th.NOTE)
        h = 0.62
        for kind, yy, lab, a in layout:
            if kind == "agent":
                v = c["by_agent"][a]["cost_per_case_run"]
                ax.barh(yy, v, height=h, color=CP if a in deciding else th.NEUTRAL, edgecolor="none", zorder=2)
                ax.text(v + 0.015 * xmax, yy, f"{v:.4f}", fontsize=th.NOTE, va="center", ha="left", zorder=4,
                        bbox=dict(boxstyle="square,pad=0.18", fc="white", ec="none"))
            elif kind == "total":
                left = 0.0
                for g, col in (("can decide the checklist", CP), ("the rest", th.NEUTRAL),
                               ("not attributed (agent list does not line up)", "white")):
                    v = groups.get(g, 0.0)
                    if v:
                        ax.barh(yy, v, left=left, height=h, color=col, edgecolor=th.NEUTRAL if col == "white" else "none",
                                lw=th.THIN, zorder=2)
                        left += v
                ax.text(total + 0.015 * xmax, yy, f"{total:.4f}", fontsize=th.NOTE, va="center", ha="left", zorder=4,
                        bbox=dict(boxstyle="square,pad=0.18", fc="white", ec="none"))
        # reference lines: the checklist-only and the frontier single prompt's cost per case, labelled at the top
        for v, ls in ((check, (0, (3, 2))), (front, (0, (1, 1.4)))):
            ax.plot([v, v], [-0.45, ymax + 0.45], color=th.INK, lw=th.THIN, ls=ls, zorder=1)
        # the line further left takes the upper label, so no line crosses the other's label
        refs = sorted(((check, "checklist only"), (front, "frontier single prompt")))
        for (v, lab), yl in zip(refs, (-1.25, -0.55)):
            ax.plot([v, v], [yl + 0.1, -0.45], color=th.INK, lw=th.THIN, clip_on=False,
                    ls=(0, (3, 2)) if lab == "checklist only" else (0, (1, 1.4)))
            ax.text(v + 0.01 * xmax, yl, lab, fontsize=th.NOTE, ha="left", va="bottom", clip_on=False)
    _save(fig, "fig_agents")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--png" in args:
        PREVIEW = args[args.index("--png") + 1]
        Path(PREVIEW).mkdir(parents=True, exist_ok=True)
    only = [a for a in args if a.startswith("fig_")]
    for f in only or ["fig_main", "fig_agents"]:
        globals()[f]()
    print("written to", FIG)
