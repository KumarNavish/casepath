"""Figures for the paper (vector PDF), generated from the evidence files.

The six figures of the TMIS paper (fig_hero, fig_reconverge, fig_fate,
fig_outcomes, fig_trace, fig_models) share one palette with fixed roles:
requested / held / handed over / missed / unnecessary keep the same colour (and,
for greyscale print, the same mark shape) everywhere, and so do the two ways of
applying rules (model-applied, code-executed). Every plotted number is read from
the evidence files below; schematic content is labelled as such.
Usage: python figures.py [--legacy] [--png DIR]  (no model calls)."""
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




# ====================================================================== TMIS figures (2026-11)
# One palette, fixed roles. Outcomes of a required document:
REQ = "#2f6aa8"    # requested                         (filled square)
HELD = "#efb21f"   # held behind a question; also an unresolved value (filled square, light)
HAND = "#8c8c8c"   # handed over to a person            (filled square, mid grey)
MISS = "#cf3e2a"   # missed                             (cross)
UNNEC = MISS       # unnecessary request: same hue as missed (both unsafe errors), hollow square
SKIP = "#c9c8c3"   # not needed / skipped
# Who applies the rules:
MODEL = "#8e5a9b"  # model-applied (plum)
CODE = "#1b7a70"   # code-executed (teal)
FAINT, PANEL = "#b4b3ae", "#f4f3ef"
TW = 5.4           # figure width in inches (acmsmall text width ~5.5 in)
import sys as _sys
from matplotlib.patches import FancyBboxPatch, Rectangle, Polygon
from matplotlib.lines import Line2D
import matplotlib.patheffects as _pe

PREVIEW = None     # directory for print-size PNG previews (set by --png)


def canvas(w, h):
    """A figure whose data coordinates are inches from the lower-left corner."""
    fig = plt.figure(figsize=(w, h))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w); ax.set_ylim(0, h); ax.axis("off")
    return fig, ax


def save(fig, name):
    fig.savefig(FIG / f"{name}.pdf")
    if PREVIEW:
        fig.savefig(Path(PREVIEW) / f"{name}.png", dpi=300)
    plt.close(fig)


def T(ax, x, y, s, size=7.5, color=INK, ha="left", va="center", **kw):
    return ax.text(x, y, s, fontsize=size, color=color, ha=ha, va=va, **kw)


def card(ax, x, y, w, h, ec=FAINT, fc="white", lw=0.6, r=0.04, ls="-", z=1):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", ec=ec, fc=fc, lw=lw, ls=ls,
                                zorder=z))


def status(ax, x, y, s, ha="right", size=6.3):
    """Evidence-status tag: schematic / exact computation / measured / post hoc."""
    T(ax, x, y, s, size=size, color=MUTED, ha=ha, va="center", style="italic",
      bbox=dict(boxstyle="round,pad=0.18,rounding_size=0.06", fc="white", ec=FAINT, lw=0.5))


def chip(ax, x, y, s, color, size=6.8, text="white", ha="left"):
    return T(ax, x, y, s, size=size, color=text, ha=ha, va="center",
             bbox=dict(boxstyle="round,pad=0.22,rounding_size=0.05", fc=color, ec="none"))


def unit(ax, x, y, kind, s=0.052, lw=0.55):
    """One unit mark (one document) of a given outcome kind, centred at (x, y)."""
    h = s / 2
    if kind == "requested":
        ax.add_patch(Rectangle((x - h, y - h), s, s, fc=REQ, ec="none"))
    elif kind == "held":
        ax.add_patch(Rectangle((x - h, y - h), s, s, fc=HELD, ec="none"))
    elif kind == "handed":
        ax.add_patch(Rectangle((x - h, y - h), s, s, fc=HAND, ec="none"))
    elif kind == "missed":
        d = h * 0.95
        ax.plot([x - d, x + d], [y - d, y + d], color=MISS, lw=lw * 1.6, solid_capstyle="butt")
        ax.plot([x - d, x + d], [y + d, y - d], color=MISS, lw=lw * 1.6, solid_capstyle="butt")
    elif kind == "unnecessary":
        k = s * 0.84
        ax.add_patch(Rectangle((x - k / 2, y - k / 2), k, k, fc="white", ec=UNNEC, lw=lw * 1.3))
    elif kind == "skip":
        ax.add_patch(Rectangle((x - h, y - h), s, s, fc="white", ec=SKIP, lw=lw))


def runs(ax, x, y, parts, size=7.0, va="center"):
    """Write text runs of mixed style on one line; returns the x where the line ends."""
    from matplotlib.backends.backend_agg import RendererAgg
    fig = ax.figure
    rend = RendererAgg(*(fig.get_size_inches() * fig.dpi), fig.dpi)
    for s, kw in parts:
        kw = dict(kw)
        color = kw.pop("color", INK)
        t = ax.text(x, y, s, fontsize=size, color=color, ha="left", va=va, **kw)
        x += t.get_window_extent(renderer=rend).width / fig.dpi
    return x


def token(ax, x, y, s, state, size=6.8, w=None, anchor="left"):
    """A document token. state: rule (definition), requested, held, skip, maybe (unknown)."""
    fc, ec, tc, ls = {"rule": ("white", INK, INK, "-"), "requested": (REQ, REQ, "white", "-"),
                      "held": (HELD, HELD, INK, "-"), "skip": ("white", SKIP, "#8d8c87", "-"),
                      "maybe": ("white", MODEL, MODEL, (0, (2, 1.5)))}[state]
    t = ax.text(x, y, s, fontsize=size, color=tc, ha="left", va="center", zorder=4)
    from matplotlib.backends.backend_agg import RendererAgg
    fig = ax.figure
    rend = RendererAgg(*(fig.get_size_inches() * fig.dpi), fig.dpi)
    tw = t.get_window_extent(renderer=rend).width / fig.dpi
    pad = 0.045
    bw = (w if w else tw + 2 * pad)
    if anchor == "right":
        x = x - bw
    t.set_x(x + (bw - tw) / 2)
    ax.add_patch(FancyBboxPatch((x, y - 0.065), bw, 0.13, boxstyle="round,pad=0,rounding_size=0.03", fc=fc, ec=ec,
                                lw=0.6, ls=ls, zorder=3))
    return x if anchor == "right" else x + bw


def arrow(ax, x0, y0, x1, y1, color=MUTED, lw=0.7, ls="-", head=True, z=2):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0), zorder=z,
                arrowprops=dict(arrowstyle="-|>,head_length=0.32,head_width=0.16" if head else "-", color=color, lw=lw,
                                ls=ls, shrinkA=0, shrinkB=0))




# ------------------------------------------------------------------ Fig. 1: the watch in three worlds (schematic)
def fig_hero():
    """Schematic. Claim text, rule and question are the paper's running example (Sec. 1, Fig. overview).
    Rows: the value of the one condition. The claim and the rule are drawn once and feed every row;
    the two document tokens of the rule reappear in every row, coloured by what happens to them."""
    W, H = TW, 3.0
    fig, ax = canvas(W, H)
    rows = [(2.25, "true", ["schedule lists the watch", "above CHF 1,000"]),
            (1.48, "false", ["schedule does not", "list the watch"]),
            (0.56, "unresolved", ["schedule not found:", "the claim as written"])]
    rh = [0.70, 0.70, 0.98]
    xj = 1.74                    # judgment column
    xm, wm = 2.68, 1.28          # model applies the rules
    xc = 4.08                    # code executes the rules
    band_lo, band_hi = rows[2][0] - rh[2] / 2, rows[2][0] + rh[2] / 2
    ax.add_patch(Rectangle((xj - 0.10, band_lo), W - xj + 0.10, band_hi - band_lo, fc="#fbf2d9", ec="none", zorder=0))
    # column heads
    yh = 2.86
    T(ax, 0.0, yh, "One claim, one rule", 7.6, INK, weight="bold")
    T(ax, xj, yh, "The condition is", 7.6, INK, weight="bold")
    T(ax, xm, yh, "Model applies the rules", 7.6, MODEL, weight="bold")
    T(ax, xc, yh, "Code executes the rules", 7.6, CODE, weight="bold")
    T(ax, xm, yh - 0.15, "returns one checklist", 6.4, MUTED, style="italic")
    T(ax, xc, yh - 0.15, "on the recorded judgment", 6.4, MUTED, style="italic")
    # ---- claim (fixed)
    x0, w0 = 0.0, 1.54
    card(ax, x0, 1.68, w0, 1.02)
    T(ax, x0 + 0.07, 2.58, "Claim", 6.6, MUTED, weight="bold")
    hl = {"bbox": dict(boxstyle="square,pad=0.08", fc="#f8e2a6", ec="none")}
    T(ax, x0 + 0.07, 2.42, "\u201c\u2026a laptop and a watch were", 7.0)
    runs(ax, x0 + 0.07, 2.28, [("stolen. The watch ", {}), ("may be", hl)], 7.0)
    runs(ax, x0 + 0.07, 2.14, [("separately scheduled", hl), (" in the", {})], 7.0)
    T(ax, x0 + 0.07, 2.00, "policy, but I have not found", 7.0)
    T(ax, x0 + 0.07, 1.86, "the policy schedule yet.\u201d", 7.0)
    # ---- rule (fixed)
    card(ax, x0, 0.12, w0, 1.44)
    T(ax, x0 + 0.07, 1.44, "Rule", 6.6, MUTED, weight="bold")
    T(ax, x0 + 0.07, 1.28, "If the watch is", 7.0)
    T(ax, x0 + 0.07, 1.14, "separately insured above", 7.0, weight="bold")
    runs(ax, x0 + 0.07, 1.00, [("CHF 1,000", {"weight": "bold"}), (", its value must be", {})], 7.0)
    T(ax, x0 + 0.07, 0.86, "established by", 7.0)
    e = token(ax, x0 + 0.07, 0.62, "receipt", "rule")
    T(ax, e + 0.06, 0.62, "or", 7.0)
    token(ax, e + 0.22, 0.62, "expert valuation", "rule")
    T(ax, x0 + 0.07, 0.40, "bold: the condition", 6.2, MUTED, style="italic")
    T(ax, x0 + 0.07, 0.27, "either document suffices", 6.2, MUTED, style="italic")
    # ---- fan-out: the same claim and rule feed every row
    fx, fy = 1.64, 1.62
    ax.plot([x0 + w0, fx], [fy, fy], color=MUTED, lw=0.7, solid_capstyle="butt")
    for yc, _, _ in rows:
        arrow(ax, fx, fy, xj - 0.06, yc + 0.11, color=MUTED, lw=0.7)
    # ---- rows
    for i, ((yc, val, world), hh) in enumerate(zip(rows, rh)):
        col, tc = {"true": (REQ, "white"), "false": (SKIP, INK), "unresolved": (HELD, INK)}[val]
        chip(ax, xj, yc + 0.11, val, col, 7.2, tc)
        for k, ln in enumerate(world):
            T(ax, xj, yc - 0.08 - 0.12 * k, ln, 6.3, MUTED)
        # model: one checklist (schematic)
        cx, cy = xm, yc - 0.19
        card(ax, cx, cy, 0.28, 0.38, ec=MODEL, lw=0.7, r=0.02)
        for k, yy in enumerate((cy + 0.29, cy + 0.19, cy + 0.09)):
            ax.add_patch(Rectangle((cx + 0.04, yy - 0.022), 0.044, 0.044, fc="white", ec=MODEL, lw=0.5, zorder=2))
            if k < 2:
                ax.plot([cx + 0.11, cx + 0.24], [yy, yy], color=FAINT, lw=1.0)
        wy = cy + 0.09
        tx = cx + 0.36
        if val == "true":
            ax.plot([cx + 0.11, cx + 0.24], [wy, wy], color=REQ, lw=1.6, solid_capstyle="butt")
            token(ax, tx, yc + 0.06, "receipt", "requested")
            T(ax, tx, yc - 0.12, "if applied correctly", 6.2, MUTED, style="italic")
        elif val == "false":
            T(ax, tx, yc + 0.06, "no watch document", 6.8)
            T(ax, tx, yc - 0.12, "if applied correctly", 6.2, MUTED, style="italic")
        else:
            T(ax, cx + 0.175, wy, "?", 7.4, MODEL, ha="center", weight="bold")
            e = token(ax, tx, yc + 0.24, "receipt", "maybe")
            T(ax, e + 0.05, yc + 0.24, "or nothing", 6.8, MODEL)
            T(ax, tx, yc + 0.04, "a silent guess:", 6.6, MODEL, style="italic")
            T(ax, tx, yc - 0.09, "the judgment behind", 6.6, MODEL, style="italic")
            T(ax, tx, yc - 0.22, "it is not recorded", 6.6, MODEL, style="italic")
        # code: the executed outcome on the rule's two document tokens
        if val == "true":
            T(ax, xc, yc + 0.19, "request the receipt", 7.0, REQ, weight="bold")
            e = token(ax, xc, yc + 0.01, "receipt", "requested")
            token(ax, e + 0.07, yc + 0.01, "expert valuation", "skip")
            T(ax, xc, yc - 0.17, "one route suffices", 6.2, MUTED, style="italic")
        elif val == "false":
            T(ax, xc, yc + 0.19, "skip both", 7.0, "#77766f", weight="bold")
            e = token(ax, xc, yc + 0.01, "receipt", "skip")
            token(ax, e + 0.07, yc + 0.01, "expert valuation", "skip")
            T(ax, xc, yc - 0.17, "neither is required", 6.2, MUTED, style="italic")
        else:
            T(ax, xc, yc + 0.35, "hold both and ask", 7.0, "#8a6400", weight="bold")
            e = token(ax, xc, yc + 0.17, "receipt", "held")
            token(ax, e + 0.07, yc + 0.17, "expert valuation", "held")
            T(ax, xc, yc - 0.03, "“Was the watch separately", 7.0, style="italic")
            T(ax, xc, yc - 0.16, "insured?”", 7.0, style="italic")
            T(ax, xc, yc - 0.33, "recorded: unresolved + quote", 6.2, MUTED, style="italic")
        if i < 2:
            ax.plot([xj - 0.10, W], [yc - hh / 2 - 0.03, yc - hh / 2 - 0.03], color=GRID, lw=0.5)
    T(ax, xj, band_lo + 0.07, "the designs differ only in this row", 6.3, "#8a6400", style="italic")
    status(ax, x0 + w0, yh, "schematic", ha="right")
    save(fig, "fig_hero")


# ------------------------------------------------------------------ Fig. 2: reconverging branch (engine output)
STEP_SHORT = {"dh_intake": "Capture defect", "dh_safety": "Escalate health risk", "dh_scope": "Dated defect timeline",
              "dh_notice": "Landlord notice", "dh_cause": "Keep causation open", "dh_evidence": "Objective evidence",
              "dh_response": "Landlord response", "dh_specialist": "Technical inspection",
              "dh_deposit": "Rent-deposit safeguards", "dh_resolution": "Record outcome", "dh_close": "Close or hand off"}
DOC_SHORT = {"medical_confirmation": "medical confirmation", "lease_contract": "lease", "defect_notification": "defect notice",
             "proof_of_notification": "proof of notice", "caretaker_correspondence": "caretaker letters",
             "dated_photos": "photos", "humidity_temperature_log": "humidity log",
             "heating_service_report": "heating report", "landlord_response_history": "landlord replies",
             "technical_inspection": "inspection report", "written_repair_deadline": "repair deadline"}


def reconverge_data():
    """Run the production engine (strong Kleene) and exact deferral (supervaluation) on the tenancy
    defect process (family defect_mold_heating) with health_effects unresolved, mold true and the
    other flags false; also evaluate the two completions of health_effects. No model call."""
    root = HERE.parent
    for p in (root / "harness", root.parents[1] / "casepath-api"):
        if str(p) not in _sys.path:
            _sys.path.insert(0, str(p))
    import casepath_tenancy as ct
    from casepath_api.autonomous_policy_v1 import compile_process
    from casepath_api.causal_process_v1 import evaluate
    from tenancy_data import templates
    flags = {"health_effects": "unresolved", "mold": "true", "heating": "false", "specialist_needed": "false",
             "deposit_considered": "false"}
    v = {"category": {"family": "defect_mold_heating", "summary": "s", "citations": []},
         "conditions": [{"flag": f, "verdict": x, "summary": "s", "citations": []} for f, x in flags.items()],
         "documents": [], "steps": [], "item_rejections": []}
    g, _, _ = compile_process(templates(), "fig", v)
    kl = evaluate(g)
    out = {"graph": g, "flags": flags,
           "kleene_nodes": {n["node_id"]: n["activation"] for n in kl["nodes"]},
           "kleene_docs": {d["document_type"]: d["route_state"] for d in kl["documents"]},
           "exact_docs": ct.supervaluate(g)["states"], "worlds": {}}
    for h in ("true", "false"):
        w = evaluate(g, conditions={"health_effects": h})
        out["worlds"][h] = {"nodes": {n["node_id"]: n["activation"] for n in w["nodes"]},
                            "docs": {d["document_type"]: d["route_state"] for d in w["documents"]}}
    out["classes"] = {d["document_type"]: d["requirement_class"] for d in g["document_catalog"]}
    return out


def fig_reconverge():
    """Engine output. Mirrored panels around one shared column of step labels, so every step and
    document sits at the same height in both evaluations; only the evaluation differs."""
    D = reconverge_data()
    g = D["graph"]
    nodes = {n["node_id"]: n for n in g["nodes"]}
    order = ["dh_intake", "dh_safety", "dh_scope", "dh_notice", "dh_cause", "dh_evidence", "dh_response",
             "dh_specialist", "dh_deposit", "dh_resolution", "dh_close"]
    side = {"dh_safety", "dh_specialist", "dh_deposit"}         # steps off the main spine
    W, H = TW, 3.12
    fig, ax = canvas(W, H)
    top, dy = 2.50, 0.212
    yof = {n: top - i * dy for i, n in enumerate(order)}
    xmid = W / 2
    lanes = {0: (xmid - 0.60, xmid - 0.78), 1: (xmid + 0.60, xmid + 0.78)}   # (main, side) lane per panel
    docx = {0: xmid - 0.90, 1: xmid + 0.90}
    req_docs = [d for d in DOC_SHORT if D["classes"][d] != "optional"]

    def lane(panel, n):
        return lanes[panel][1] if n in side else lanes[panel][0]

    def doc_state(panel, d):
        if D["classes"][d] == "optional":
            return "optional"
        st = D["kleene_docs" if panel == 0 else "exact_docs"][d]
        return {"needed_later": "requested", "held_behind_question": "held", "not_needed": "skip"}[st]

    # headings
    T(ax, 0, 3.02, "Strong Kleene evaluation", 7.8, INK, weight="bold")
    T(ax, 0, 2.87, "production engine, one pass with", 6.4, MUTED, style="italic")
    T(ax, 0, 2.75, "health effects = unresolved", 6.4, MUTED, style="italic")
    T(ax, W, 3.02, "Exact deferral", 7.8, INK, weight="bold", ha="right")
    T(ax, W, 2.87, "both completions, drawn as two", 6.4, MUTED, style="italic", ha="right")
    T(ax, W, 2.75, "traversals of the same graph", 6.4, MUTED, style="italic", ha="right")
    status(ax, xmid, 3.02, "engine output", ha="center")
    T(ax, xmid, 2.75, "steps of the tenancy defect process", 6.2, MUTED, ha="center", style="italic")
    for panel in (0, 1):
        # edges of the process graph (context)
        for e in g["edges"]:
            a, b = e["source_node_id"], e["target_node_id"]
            ax.plot([lane(panel, a), lane(panel, b)], [yof[a], yof[b]], color=GRID, lw=1.8, zorder=1,
                    solid_capstyle="round")
        if panel == 0:      # the unresolved value floods everything downstream of the branch
            act = D["kleene_nodes"]
            for e in g["edges"]:
                a, b = e["source_node_id"], e["target_node_id"]
                if act[b] == "unresolved" and act[a] in ("true", "unresolved"):
                    ax.plot([lane(0, a), lane(0, b)], [yof[a], yof[b]], color=HELD, lw=1.8, zorder=1.5,
                            solid_capstyle="round")
        else:               # the steps active in each completion, as two offset traversals
            for h, off, ls in (("true", 0.03, "-"), ("false", -0.03, (0, (2.2, 1.4)))):
                act = D["worlds"][h]["nodes"]
                for e in g["edges"]:
                    a, b = e["source_node_id"], e["target_node_id"]
                    if act[a] == "true" and act[b] == "true":
                        ax.plot([lane(1, a) + off, lane(1, b) + off], [yof[a], yof[b]], color=INK, lw=0.8, ls=ls,
                                zorder=2)
        for n in order:
            x, y = lane(panel, n), yof[n]
            if panel == 0:
                a = D["kleene_nodes"][n]
                fc, ec = {"true": (INK, INK), "unresolved": (HELD, "#b9860c"), "false": ("white", SKIP)}[a]
            else:
                hits = sum(D["worlds"][h]["nodes"][n] == "true" for h in ("true", "false"))
                fc, ec = [("white", SKIP), (HELD, "#b9860c"), (INK, INK)][hits]
            ax.add_patch(matplotlib.patches.Circle((x, y), 0.036, fc=fc, ec=ec, lw=0.7, zorder=3))
            # documents of this step, growing outward from the graph
            xx = docx[panel]
            for d in nodes[n].get("document_types", []):
                st = doc_state(panel, d)
                if panel == 0:
                    xx = token(ax, xx, y, DOC_SHORT[d], "skip" if st == "optional" else st, size=6.1,
                               anchor="right") - 0.04
                else:
                    xx = token(ax, xx, y, DOC_SHORT[d], "skip" if st == "optional" else st, size=6.1) + 0.04
                if st == "optional":
                    if panel == 0:
                        T(ax, xx - 0.02, y, "optional", 5.6, "#9b9a95", style="italic", ha="right")
                    else:
                        T(ax, xx + 0.0, y, "optional", 5.6, "#9b9a95", style="italic")
        # tally: one unit per document this case requires (under either completion)
        n_req = sum(doc_state(panel, d) == "requested" for d in req_docs)
        n_held = sum(doc_state(panel, d) == "held" for d in req_docs)
        yb0 = yof["dh_close"] - 0.30
        marks = ["requested"] * n_req + ["held"] * n_held
        if panel == 0:
            x0 = 0.04
            for k, m in enumerate(marks):
                unit(ax, x0 + 0.085 * k, yb0, m, s=0.07)
            T(ax, x0 + 0.085 * len(marks) + 0.0, yb0, f"{n_req} requested, {n_held} held", 6.8, INK)
        else:
            x0 = W - 0.04
            for k, m in enumerate(marks[::-1]):
                unit(ax, x0 - 0.085 * k, yb0, m, s=0.07)
            T(ax, x0 - 0.085 * len(marks) - 0.0, yb0, f"{n_req} requested, {n_held} held", 6.8, INK, ha="right")
    # shared step labels
    for n in order:
        dim = D["kleene_nodes"][n] == "false"
        T(ax, xmid, yof[n], STEP_SHORT[n], 6.6, "#9b9a95" if dim else INK, ha="center")
    T(ax, xmid, yof["dh_close"] - 0.30, f"{len(req_docs) - sum(doc_state(1, d) == 'skip' for d in req_docs)} documents "
      "required", 6.4, MUTED, ha="center", style="italic")
    # the decisive interface: the reconverging scope step
    ys = yof["dh_scope"]
    T(ax, 1.44, ys, "activation (U\u2227T)\u2228(T\u2227U) = U", 6.2, "#8a6400", ha="right", style="italic")
    T(ax, W - 1.48, ys, "true in both completions", 6.2, MUTED, style="italic")
    T(ax, W - 0.88, yof["dh_safety"], "one completion only", 6.2, "#8a6400", style="italic")
    # world key (right panel, top)
    kx, ky = W - 1.48, 2.62
    ax.plot([kx, kx + 0.18], [ky, ky], color=INK, lw=0.8)
    T(ax, kx + 0.22, ky, "health effects = true", 6.2)
    ax.plot([kx, kx + 0.18], [ky - 0.12, ky - 0.12], color=INK, lw=0.8, ls=(0, (2.2, 1.4)))
    T(ax, kx + 0.22, ky - 0.12, "health effects = false", 6.2)
    save(fig, "fig_reconverge")


# ------------------------------------------------------------------ Fig. 3: fate of each kind of judgment error (exact)
FATE_EPS = 0.1   # the operating point of the prop... macros in numbers.tex
SEMANTICS = [("kleene", "Strong Kleene", "production engine"), ("exact", "Exact deferral", "supervaluation"),
             ("closed", "Open read as false", "two-valued execution"), ("eager", "Open read as true", "two-valued execution")]


def fate_data(eps=FATE_EPS):
    """Exact expected outcomes over all 150 claims (scicore/out_local/s1_tables_*.json, the tables behind
    s1_propagation.json), for three kinds of judgment error, each hitting a judgment with probability eps:
    unresolved (any true value becomes unresolved), true judged false, false judged true. Expectations
    are exact sums over all judgment vectors, as in scicore/s1_propagation.py (same reference sets)."""
    out_dir = HERE.parent / "scicore" / "out_local"
    tables = {}
    for p in sorted(out_dir.glob("s1_tables_*.json")):
        tables.update(json.loads(p.read_text()))
    skip_photo = {"clm_e262801f9368bc12", "clm_731b214dde882f89", "clm_7ac806bd30792cfb"}  # as in s1_propagation.py

    def prob(key, truth, kind):
        p = 1.0
        for j, t in zip(key, truth):
            hit = (kind == "unresolved") or (kind == "TtoF" and t == "T") or (kind == "FtoT" and t == "F")
            wrong = "U" if kind == "unresolved" else ("F" if t == "T" else "T")
            if not hit:
                p *= 1.0 if j == t else 0.0
            else:
                p *= (1 - eps) if j == t else eps if j == wrong else 0.0
        return p

    res, n_req = {}, 0
    for kind in ("none", "unresolved", "TtoF", "FtoT"):
        agg = {s: {"unnecessary": 0.0, "missed": 0.0, "deferred": 0.0} for s, _, _ in SEMANTICS}
        n_req = 0
        for cid, t in tables.items():
            R = set(t["reference_requests"]) - ({"dated_photos"} if cid in skip_photo else set())
            n_req += len(R)
            for key, row in t["table"].items():
                p = prob(key, t["truth"], kind) if kind != "none" else float(key == "".join(t["truth"]))
                if p == 0.0:
                    continue
                for s, _, _ in SEMANTICS:
                    req, held = set(row[s][0]), set(row[s][1])
                    agg[s]["unnecessary"] += p * len(req - R)
                    agg[s]["missed"] += p * len(R - req - held)
                    agg[s]["deferred"] += p * len(R & held)
        res[kind] = agg
    # consistency with the published grid (eps, rho = 1): unresolved errors only
    s1 = {(r["eps"], r["rho"]): r for r in json.loads((out_dir / "s1_propagation.json").read_text())}
    ref = s1[(eps, 1.0)]
    for s, _, _ in SEMANTICS:
        for k in ("unnecessary", "missed", "deferred"):
            assert abs(res["unresolved"][s][k] - ref[f"{s}_{k}"]) < 1e-6, (s, k)
    per100 = {}
    for kind in ("unresolved", "TtoF", "FtoT"):
        per100[kind] = {s: {"deferred": 100 * res[kind][s]["deferred"] / n_req,
                            "missed": 100 * res[kind][s]["missed"] / n_req,
                            "unnecessary": 100 * (res[kind][s]["unnecessary"] - res["none"][s]["unnecessary"]) / n_req,
                            "deferred_beyond_exact": 100 * (res[kind][s]["deferred"] - res[kind]["exact"]["deferred"]) / n_req}
                        for s, _, _ in SEMANTICS}
    return {"per100": per100, "required": n_req, "claims": len(tables), "eps": eps}


def fig_fate():
    """Exact computation. Aligned small multiples: rows = kind of judgment error x semantics, columns =
    outcome, one shared scale. The eye sees a staircase for unresolved judgments (the semantics decide the
    outcome) and a vertical stripe for confident errors (every semantics gives the same outcome)."""
    F = fate_data()
    P = F["per100"]
    W, H = TW, 2.92
    fig, ax = canvas(W, H)
    kinds = [("unresolved", "Unresolved", "the judgment is left open", "set by the semantics"),
             ("TtoF", "Confidently wrong", "a true condition judged false", "missed in all four"),
             ("FtoT", "Confidently wrong", "a false condition judged true", "unnecessary in all four")]
    outs = [("deferred", "Held", "behind a question"), ("missed", "Missed", "unsafe error"),
            ("unnecessary", "Unnecessary", "request; unsafe error")]
    xcol = [2.32, 3.50, 4.48]
    scale = 0.85 / 15.0             # inches per document per 100 required documents, all columns
    rh, gap = 0.142, 0.13
    ytop = 2.28
    yh = 2.62
    status(ax, W, H - 0.08, "exact computation", ha="right")
    for (k, name, sub), x in zip(outs, xcol):
        T(ax, x, yh, name, 7.2, INK, weight="bold")
        if k == "deferred":
            ax.add_patch(Rectangle((x, yh - 0.19), 0.16, 0.07, fc=HELD, ec="none"))
        elif k == "missed":
            ax.add_patch(Rectangle((x, yh - 0.19), 0.16, 0.07, fc="white", ec=MISS, hatch="xxxxx", lw=0.0))
        else:
            ax.add_patch(Rectangle((x, yh - 0.19), 0.16, 0.07, fc="white", ec=UNNEC, lw=0.8))
        T(ax, x + 0.21, yh - 0.155, sub, 6.2, MUTED, style="italic")
    T(ax, 0, yh, "Kind of judgment error", 7.2, INK, weight="bold")
    T(ax, 1.22, yh, "Execution semantics", 7.2, INK, weight="bold")
    y = ytop
    for b, (kind, name, sub, fate) in enumerate(kinds):
        for i, (s, sname, ssub) in enumerate(SEMANTICS):
            yy = y - i * rh
            T(ax, 1.22, yy, sname, 6.6, INK)
            if i < 3:
                ax.plot([1.22, W - 0.05], [yy - rh / 2, yy - rh / 2], color=GRID, lw=0.4, zorder=0)
            for (k, _, _), x in zip(outs, xcol):
                v = P[kind][s][k]
                ax.plot([x, x], [yy - rh * 0.42, yy + rh * 0.42], color=FAINT, lw=0.5, zorder=1)
                if abs(v) < 0.05:
                    continue
                w = max(v, 0) * scale
                y0, hh = yy - rh * 0.34, rh * 0.68
                if k == "deferred":
                    extra = P[kind][s]["deferred_beyond_exact"] if s == "kleene" else 0.0
                    base = (v - extra) * scale
                    ax.add_patch(Rectangle((x, y0), base, hh, fc=HELD, ec="none", zorder=2))
                    if extra > 0.05:
                        ax.add_patch(Rectangle((x + base, y0), extra * scale, hh, fc="white", ec=HELD, hatch="//////",
                                               lw=0.6, zorder=2))
                elif k == "missed":
                    ax.add_patch(Rectangle((x, y0), w, hh, fc="white", ec=MISS, hatch="xxxxx", lw=0.0, zorder=2))
                    ax.add_patch(Rectangle((x, y0), w, hh, fc="none", ec=MISS, lw=0.6, zorder=2))
                else:
                    ax.add_patch(Rectangle((x, y0), w, hh, fc="white", ec=UNNEC, lw=0.8, zorder=2))
                T(ax, x + w + 0.04, yy, f"{v:.1f}", 6.4, INK)
        yc = y - 1.5 * rh
        T(ax, 0, yc + 0.13, name, 7.2, INK, weight="bold")
        T(ax, 0, yc - 0.005, sub, 6.3, MUTED, style="italic")
        T(ax, 0, yc - 0.14, "\u2192 " + fate, 6.3, {"unresolved": "#8a6400", "TtoF": MISS, "FtoT": MISS}[kind])
        ax.plot([1.15, 1.15], [y + rh * 0.45, y - 3 * rh - rh * 0.45], color=MUTED, lw=0.6)
        y -= 4 * rh + gap
    ex = P["unresolved"]["kleene"]["deferred_beyond_exact"]
    T(ax, 0, 0.20, f"Per 100 required documents, each judgment having the error with probability {F['eps']:.1f}; "
      f"all {F['claims']} claims, {F['required']:,} required documents.", 6.2, MUTED, style="italic")
    T(ax, 0, 0.07, f"Hatched: {ex:.1f} documents strong Kleene evaluation holds although every completion "
      "requires them.", 6.2, MUTED, style="italic")
    save(fig, "fig_fate")


# ------------------------------------------------------------------ Fig. 4: where 100 required documents end up (measured)
OUTCOME_DESIGNS = [("model", "B1", "Rules in context"), ("model", "B1-SC3", "Self-consistency (majority of 3)"),
                   ("model", "B2", "Model executes rules"),
                   ("code", "tv:closed", "Two-valued, open read as false"), ("code", "tv:eager", "Two-valued, open read as true"),
                   ("code", "CP-kleene", "CasePath, strong Kleene"), ("code", "CP-exact", "CasePath, exact deferral")]
MODELS = [("gpt-6.1-terra", "Primary analysis", "gpt-6.1-terra"), ("gpt-6-luna", "Secondary analysis", "gpt-6-luna")]


def largest_remainder(values, total=100):
    floors = [int(v) for v in values]
    rest = total - sum(floors)
    order = sorted(range(len(values)), key=lambda i: values[i] - floors[i], reverse=True)
    for i in order[:rest]:
        floors[i] += 1
    return floors


def outcomes_data():
    tv = load("two_valued.json")
    out = {}
    for tag, _, _ in MODELS:
        t = load(f"results_{tag}.json")["tenancy"]
        for _, key, _ in OUTCOME_DESIGNS:
            v = tv[tag][f"tenancy_{key[3:]}"] if key.startswith("tv:") else t.get(key)
            if v is None:
                out[(tag, key)] = None
                continue
            n = v["nR"]
            parts = [100 * v["tp"] / n, 100 * v["held"] / n, 100 * v["handed"] / n, 100 * v["miss"] / n]
            assert abs(sum(parts) - 100) < 1e-6, (tag, key)
            out[(tag, key)] = {"pct": parts, "units": largest_remainder(parts), "unnec_per100": 100 * v["fp"] / n,
                               "unnec_share_of_requests": v["unnecessary_rate"], "nR": n, "fp": v["fp"]}
    return out


def fig_outcomes():
    D = outcomes_data()
    W, H = TW, 3.36
    fig, ax = canvas(W, H)
    pitch, ms, gap10 = 0.0455, 0.037, 0.028
    x0 = 1.62                                   # first unit mark
    xu = x0 + 50 * pitch + 4 * gap10 + 0.14     # unnecessary marks
    rowh = 0.175
    kinds = ["requested", "held", "handed", "missed"]

    def mx(i):
        c = i % 50
        return x0 + c * pitch + (c // 10) * gap10

    # legend
    ly = H - 0.10
    lx = 0.0
    for kind, name in (("requested", "requested"), ("held", "held behind a question"), ("handed", "handed over to a person"),
                       ("missed", "missed")):
        unit(ax, lx + 0.03, ly, kind, s=ms)
        lx = T(ax, lx + 0.09, ly, name, 6.8).get_window_extent(
            renderer=matplotlib.backends.backend_agg.RendererAgg(W * 72, H * 72, 72)).x1 / 72 + 0.14
    unit(ax, lx + 0.03, ly, "unnecessary", s=ms)
    T(ax, lx + 0.09, ly, "unnecessary request (outside the 100)", 6.8)
    T(ax, 0, ly - 0.17, "Each row: 100 marks = 100 required documents; gaps every 10.", 6.3, MUTED, style="italic")
    status(ax, W, ly - 0.17, "measured, tenancy claims, three runs", ha="right")
    y = ly - 0.42
    for tag, analysis, mname in MODELS:
        T(ax, 0, y, analysis, 7.4, INK, weight="bold")
        runs(ax, 0.0 + 1.05, y, [(mname, {"family": "monospace", "color": INK})], 6.6) if False else None
        T(ax, x0, y, mname, 7.0, INK, family="Linux Libertine Mono O")
        T(ax, xu, y, "unnecessary", 6.6, MUTED, style="italic")
        y -= 0.18
        group_y = {}
        for role, key, name in OUTCOME_DESIGNS:
            v = D[(tag, key)]
            group_y.setdefault(role, []).append(y)
            T(ax, x0 - 0.08, y, name, 6.7, INK, ha="right")
            if v is None:
                T(ax, x0, y, "not run with this model", 6.4, MUTED, style="italic")
                y -= rowh
                continue
            seq = [k for k, n in zip(kinds, v["units"]) for _ in range(n)]
            for i, kind in enumerate(seq):
                yy = y + (0.026 if i < 50 else -0.026)
                unit(ax, mx(i), yy, kind, s=ms)
            nu = round(v["unnec_per100"])
            for i in range(nu):
                c, r = i % 20, i // 20
                unit(ax, xu + 0.02 + c * pitch + (c // 10) * gap10, y + (0.026 if r == 0 else -0.026), "unnecessary", s=ms)
            lab = f"{v['unnec_per100']:.1f}"
            xl = xu + 0.02 + (min(nu, 20) * pitch + (0.03 if nu > 10 else 0)) + (0.04 if nu else 0)
            T(ax, xl, y, lab, 6.4, UNNEC if nu else MUTED)
            y -= rowh
        for role, ys in group_y.items():
            col = MODEL if role == "model" else CODE
            ax.plot([0.03, 0.03], [ys[0] + 0.07, ys[-1] - 0.07], color=col, lw=2.0, solid_capstyle="butt")
            T(ax, 0.075, (ys[0] + ys[-1]) / 2, "model applies\nthe rules" if role == "model" else "code executes\nthe rules",
              6.0, col, va="center", linespacing=0.95)
        y -= 0.10
    save(fig, "fig_outcomes")


if __name__ == "__main__":
    args = _sys.argv[1:]
    if "--png" in args:
        PREVIEW = args[args.index("--png") + 1]
        Path(PREVIEW).mkdir(parents=True, exist_ok=True)
    if "--legacy" in args:
        fig_tenancy(); fig_theft(); fig_propagation()
    only = [a for a in args if a.startswith("fig_")]
    for f in only or ["fig_hero", "fig_reconverge", "fig_fate", "fig_outcomes", "fig_trace", "fig_models"]:
        if f in globals():
            globals()[f]()
    print("figures written to", FIG)
