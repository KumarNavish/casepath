"""Figures for the paper (vector PDF), generated from the evidence files.

Palette: validated categorical slots (blue, orange, aqua) in fixed order;
hatching gives a second encoding for grayscale print."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("pdf")
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE = Path(__file__).resolve().parent
FIG = HERE.parent / "paper" / "figures"
FIG.mkdir(parents=True, exist_ok=True)
for f in font_manager.findSystemFonts():
    if "Biolinum" in f or "Libertine" in f:
        font_manager.fontManager.addfont(f)
plt.rcParams.update({"font.family": "Linux Biolinum O", "font.size": 7.5, "axes.titlesize": 8, "axes.labelsize": 7.5,
                     "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7, "axes.linewidth": 0.6,
                     "xtick.major.width": 0.6, "ytick.major.width": 0.6, "pdf.fonttype": 42, "hatch.linewidth": 0.5})
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
W = 5.3  # acmsmall text width in inches


def clean(ax, xgrid=True):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(axis="y", length=0, colors=INK)
    ax.tick_params(axis="x", colors=MUTED)
    if xgrid:
        ax.grid(axis="x", color=GRID, linewidth=0.5)
        ax.set_axisbelow(True)


def load(name):
    p = HERE / name
    return json.loads(p.read_text()) if p.exists() else None


# ------------------------------------------------------------------ Figure: tenancy outcomes
def fig_tenancy():
    rows = [("B1", "Rules in context"), ("B1-SC3", "Rules in context, majority of 3"), ("B2", "Model executes rules"),
            ("CP-kleene", "CasePath, product engine (Kleene)"), ("CP-exact", "CasePath, exact deferral"),
            ("CP-exact-noverifier", "CasePath, exact deferral, no verifier")]
    panels = [(tag, name) for tag, name in (("gpt-6.1-terra", "gpt-6.1-terra"), ("gpt-6-luna", "gpt-6-luna"))
              if load(f"results_{tag}.json") and "tenancy" in load(f"results_{tag}.json")]
    fig, axes = plt.subplots(1, len(panels), figsize=(W, 2.15), sharey=True, squeeze=False)
    for ax, (tag, title) in zip(axes[0], panels):
        t = load(f"results_{tag}.json")["tenancy"]
        shown = rows  # identical rows in every panel so shared labels stay aligned
        ys = list(range(len(shown)))[::-1]
        for y, (k, lab) in zip(ys, shown):
            if k not in t:
                ax.text(2, y, "not run with this model", va="center", ha="left", color=MUTED, fontsize=6.3, style="italic")
                continue
            v = t[k]
            req, hld, hnd, mis = v["recall"], v["held_rate"], v["handed_rate"], v["silent_miss_rate"]
            ax.barh(y, 100 * req, color=BLUE, height=0.62, edgecolor="white", linewidth=0.8)
            ax.barh(y, 100 * hld, left=100 * req, color=AQUA, height=0.62, hatch="////", edgecolor="white", linewidth=0.8)
            ax.barh(y, 100 * hnd, left=100 * (req + hld), color=MUTED, height=0.62, hatch="....", edgecolor="white", linewidth=0.8)
            ax.barh(y, 100 * mis, left=100 * (req + hld + hnd), color=ORANGE, height=0.62, hatch="xxxx", edgecolor="white", linewidth=0.8)
            ax.text(100 * req - 1.5, y, f"{100 * req:.0f}", va="center", ha="right", color="white", fontsize=6.5)
            if hld > 0.06:
                ax.text(100 * (req + hld) - 1.5, y, f"{100 * hld:.0f}", va="center", ha="right", color=INK, fontsize=6.5)
            ax.text(103, y, f"{100 * v['unnecessary_rate']:.1f}", va="center", ha="left", color=INK, fontsize=6.5)
        ax.set_yticks(ys)
        ax.set_yticklabels([lab for _, lab in shown])
        ax.set_xlim(0, 112)
        ax.set_xticks([0, 25, 50, 75, 100])
        ax.set_xlabel("Share of required documents (%)")
        ax.set_title(title, loc="left", color=INK)
        ax.text(103, len(shown) - 0.35, "Unnec.\n(%)", fontsize=6, color=MUTED, va="bottom")
        clean(ax)
    from matplotlib.patches import Patch
    handles = [Patch(facecolor=BLUE, label="Requested"), Patch(facecolor=AQUA, hatch="////", edgecolor="white", label="Held behind a question"),
               Patch(facecolor=MUTED, hatch="....", edgecolor="white", label="Handed to a person (whole claim)"),
               Patch(facecolor=ORANGE, hatch="xxxx", edgecolor="white", label="Silently missed")]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.55, -0.02), columnspacing=1.0,
               handletextpad=0.4)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(FIG / "fig_tenancy.pdf")
    plt.close(fig)


# ------------------------------------------------------------------ Figure: theft across models
def fig_theft():
    o = load("original_study.json")["table"]  # gpt-5.6-terra, preregistered single run, as frozen (all routes)
    orig = {"D": (o["D"]["wrong_per_pair"], o["D"]["missed_per_pair"]), "R": (o["R"]["wrong_per_pair"], o["R"]["missed_per_pair"]),
            "CP": (o["CP-allroutes"]["wrong_per_pair"], o["CP-allroutes"]["missed_per_pair"])}
    models = [("gpt-5.6-terra (original study, 1 run)", None, "D", "none"), ("gpt-6.1-terra (3 runs)", "gpt-6.1-terra", "o", "full"),
              ("gpt-6-luna (3 runs)", "gpt-6-luna", "s", "full")]
    designs = [("D", "Direct"), ("R", "Rules in context"), ("CP", "CasePath")]
    fig, axes = plt.subplots(1, 3, figsize=(W, 2.0), sharey=True)
    ys = {"D": 2, "R": 1, "CP": 0}
    offs = {0: 0.27, 1: -0.03, 2: -0.23}  # the original single run sits apart, above the two three-run markers
    colors = [MUTED, BLUE, ORANGE]
    for i, (mlabel, tag, marker, fill) in enumerate(models):
        res = load(f"results_{tag}.json") if tag else None
        for key, _ in designs:
            if tag is None:
                wrong, missed, unstable = orig[key][0], orig[key][1], None
            else:
                if not res or "theft" not in res or key not in res["theft"]:
                    continue
                v = res["theft"][key]
                wrong, missed = v["on"]["wrong_per_pair"], v["on"]["missed_per_pair"]
                unstable = 100 - 100 * v["unresolved"]["stable_rate"]
            y = ys[key] + offs[i]
            kw = dict(marker=marker, s=22, linewidths=0.9, edgecolors=colors[i],
                      facecolors=(colors[i] if fill == "full" else "white"), zorder=3)
            axes[0].scatter(wrong, y, **kw)
            axes[1].scatter(missed, y, **kw)
            if unstable is not None:
                axes[2].scatter(unstable, y, **kw)
    axes[0].set_xlabel("Wrong changes per pair\n\u2190 lower is better")
    axes[1].set_xlabel("Missed changes per pair\n\u2190 lower is better")
    axes[2].set_xlabel("Unresolved pairs with a change (%)\n\u2190 lower is better")
    for y in (0.5, 1.5):  # separate the designs
        for ax in axes:
            ax.axhline(y, color=GRID, linewidth=0.5, zorder=1)
    axes[0].set_yticks([2, 1, 0])
    axes[0].set_yticklabels([d for _, d in designs])
    axes[0].set_xlim(0, 1.7); axes[1].set_xlim(0, 0.7); axes[2].set_xlim(0, 75)
    for ax in axes:
        clean(ax)
        ax.set_ylim(-0.6, 2.6)
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], marker=mk, linestyle="none", markersize=5.5, markeredgewidth=0.9, markeredgecolor=colors[i],
                      markerfacecolor=(colors[i] if fl == "full" else "white"), label=lab)
               for i, (lab, _, mk, fl) in enumerate(models)]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.55, -0.03), handletextpad=0.2)
    fig.tight_layout(rect=(0, 0.13, 1, 1))
    fig.savefig(FIG / "fig_theft.pdf")
    plt.close(fig)


# ------------------------------------------------------------------ Figure: semantics under judgment errors
def fig_propagation():
    s1 = json.loads((HERE.parent / "scicore" / "out_local" / "s1_propagation.json").read_text())
    g = {(r["eps"], r["rho"]): r for r in s1}
    eps = 0.2
    base = g[(0.0, 1.0)]
    sems = [("exact", "Exact"), ("kleene", "Kleene"), ("closed", "Open\nas false"), ("eager", "Open\nas true")]
    panels = [(1.0, "All judgment errors are 'unresolved'"), (0.5, "Half unresolved, half wrong"), (0.0, "All errors are wrong verdicts")]
    fig, axes = plt.subplots(1, 3, figsize=(W, 1.95), sharey=True)
    n = base["required_total"] / 100.0
    for ax, (rho, title) in zip(axes, panels):
        r = g[(eps, rho)]
        for i, (s, lab) in enumerate(sems):
            unn = (r[f"{s}_unnecessary"] - base[f"{s}_unnecessary"]) / n
            mis = r[f"{s}_missed"] / n
            dfr = r[f"{s}_deferred"] / n
            ax.bar(i, unn, color=ORANGE, width=0.66, edgecolor="white", linewidth=0.8)
            ax.bar(i, mis, bottom=unn, color="#b44a20", hatch="xxxx", width=0.66, edgecolor="white", linewidth=0.8)
            ax.bar(i, dfr, bottom=unn + mis, color=AQUA, hatch="////", width=0.66, edgecolor="white", linewidth=0.8)
        ax.set_xticks(range(4))
        ax.set_xticklabels([lab for _, lab in sems], fontsize=6.5)
        ax.set_title(title, loc="left", fontsize=7, color=INK)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.spines["left"].set_color(MUTED); ax.spines["bottom"].set_color(MUTED)
        ax.grid(axis="y", color=GRID, linewidth=0.5); ax.set_axisbelow(True)
        ax.tick_params(axis="x", length=0)
    axes[0].set_ylabel("Per 100 required documents")
    from matplotlib.patches import Patch
    handles = [Patch(facecolor=ORANGE, label="Unnecessary requests"), Patch(facecolor="#b44a20", hatch="xxxx", edgecolor="white", label="Silent misses"),
               Patch(facecolor=AQUA, hatch="////", edgecolor="white", label="Deferrals")]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.55, -0.03))
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    fig.savefig(FIG / "fig_propagation.pdf")
    plt.close(fig)


if __name__ == "__main__":
    fig_tenancy(); fig_theft(); fig_propagation()
    print("figures written to", FIG)
