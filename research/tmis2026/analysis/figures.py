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
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle

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
    x = x - 0.035 if ha == "right" else x
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




# ------------------------------------------------------------------ Fig. 1: what each design records (schematic)
def fig_hero():
    """Schematic. Claim, rule and question are the paper's running example. The figure shows what each
    design records, not what it outputs: on the real unresolved-watch pairs every design held the receipt.
    Layout is modular: stages are columns (claim | judgment | rule | executed outcome), so later stages
    (rule verification and repair against sources; repair from handler corrections) can be inserted as
    further columns or as a box attached to the rule column without moving the rest."""
    W, H = TW, 3.20
    fig, ax = canvas(W, H)
    # stage columns (x, width)
    cC, cJ, cR, cE = (0.0, 1.34), (1.50, 1.04), (2.70, 1.30), (4.16, 1.24)
    yh = 3.08
    T(ax, cC[0], yh, "Claim", 7.6, INK, weight="bold")
    status(ax, W, yh, "schematic", ha="right")
    # ---- claim (fixed, shared by both designs)
    hl = {"bbox": dict(boxstyle="square,pad=0.08", fc="#f8e2a6", ec="none")}
    card(ax, cC[0], 1.62, cC[1], 1.30)
    T(ax, cC[0] + 0.07, 2.78, "\u201c\u2026a laptop and a watch", 7.0)
    T(ax, cC[0] + 0.07, 2.64, "were stolen. The watch", 7.0)
    runs(ax, cC[0] + 0.07, 2.50, [("may be separately", hl)], 7.0)
    runs(ax, cC[0] + 0.07, 2.36, [("scheduled", hl), (" in the policy,", {})], 7.0)
    T(ax, cC[0] + 0.07, 2.22, "but I have not found the", 7.0)
    T(ax, cC[0] + 0.07, 2.08, "policy schedule yet.\u201d", 7.0)
    T(ax, cC[0] + 0.07, 1.86, "the same claim for", 6.2, MUTED, style="italic")
    T(ax, cC[0] + 0.07, 1.74, "both designs", 6.2, MUTED, style="italic")
    # ---- model applies the rules: one generation (top band)
    yb, hb = 2.42, 0.50
    T(ax, cJ[0], yh, "Model applies the rules", 7.6, MODEL, weight="bold")
    card(ax, cJ[0], yb, W - cJ[0], hb, ec=MODEL, lw=0.8, r=0.05)
    T(ax, cJ[0] + 0.09, yb + hb - 0.13, "one generation", 7.2, MODEL, weight="bold")
    T(ax, cJ[0] + 0.09, yb + hb - 0.28, "reads the claim and the rules in its prompt", 6.6, INK)
    T(ax, cJ[0] + 0.09, yb + 0.09, "judgment and rule application are not recorded separately", 6.4, MODEL,
      style="italic")
    xo = cR[0] + 0.70
    T(ax, xo, yb + hb - 0.13, "records", 6.4, MUTED, style="italic")
    token(ax, xo, yb + hb - 0.29, "checklist", "rule", size=6.6)
    token(ax, xo + 0.62, yb + hb - 0.29, "free-text reason", "rule", size=6.6)
    arrow(ax, cC[0] + cC[1], 2.66, cJ[0] - 0.02, 2.66, color=MUTED)
    # ---- code executes the rules: three aligned worlds (lower band)
    yl = 2.18
    T(ax, cJ[0], yl, "Code executes the rules", 7.6, CODE, weight="bold")
    for (x, _), h in zip((cJ, cR, cE), ("judgment + quotation", "rule + source passage", "request that follows")):
        T(ax, x, yl - 0.16, h, 6.4, MUTED, style="italic")
    T(ax, W, yl, "records all three", 6.4, CODE, style="italic", ha="right")
    rows = [(1.60, "true", "quote: schedule lists it"), (1.02, "false", "quote: schedule omits it"),
            (0.36, "unresolved", "\u201cmay be separately\nscheduled\u201d")]
    band_lo, band_hi = 0.04, 0.70
    ax.add_patch(Rectangle((cJ[0] - 0.06, band_lo), W - cJ[0] + 0.06, band_hi - band_lo, fc="#fbf2d9", ec="none", zorder=0))
    # rule: one object spanning the three worlds, with its source passage
    rt, rb = 1.92, 0.10
    card(ax, cR[0], rb, cR[1], rt - rb, ec=CODE, lw=0.8)
    T(ax, cR[0] + 0.07, rt - 0.12, "If the watch is", 6.8)
    T(ax, cR[0] + 0.07, rt - 0.25, "separately insured", 6.8, weight="bold")
    runs(ax, cR[0] + 0.07, rt - 0.38, [("above CHF 1,000", {"weight": "bold"}), (", its", {})], 6.8)
    T(ax, cR[0] + 0.07, rt - 0.51, "value is established by", 6.8)
    e = token(ax, cR[0] + 0.07, rt - 0.70, "receipt", "rule", size=6.5)
    T(ax, e + 0.05, rt - 0.70, "or", 6.6)
    token(ax, cR[0] + 0.07, rt - 0.88, "expert valuation", "rule", size=6.5)
    T(ax, cR[0] + 0.07, rb + 0.22, "source: policy terms,", 6.1, MUTED, style="italic")
    T(ax, cR[0] + 0.07, rb + 0.10, "cited passage", 6.1, MUTED, style="italic")
    # fan-out from the claim to the judgment of each world
    fx, fy = cC[0] + cC[1] + 0.06, 1.10
    ax.plot([cC[0] + cC[1] / 2, cC[0] + cC[1] / 2, fx], [1.62, fy, fy], color=MUTED, lw=0.7)
    for i, (yc, val, quote) in enumerate(rows):
        arrow(ax, fx, fy, cJ[0] - 0.03, yc + 0.09, color=MUTED, lw=0.7)
        col, tc = {"true": (REQ, "white"), "false": (SKIP, INK), "unresolved": (HELD, INK)}[val]
        chip(ax, cJ[0], yc + 0.09, val, col, 7.0, tc)
        T(ax, cJ[0], yc - 0.10 - (0.05 if "\n" in quote else 0), quote, 6.2, MUTED, style="italic", linespacing=1.0)
        # judgment -> rule -> request
        ax.plot([cJ[0] + cJ[1] - 0.02, cR[0]], [yc, yc], color=CODE, lw=0.7)
        arrow(ax, cR[0] + cR[1], yc, cE[0] - 0.04, yc, color=CODE, lw=0.7)
        if val == "true":
            T(ax, cE[0], yc + 0.15, "request the receipt", 6.9, REQ, weight="bold")
            e = token(ax, cE[0], yc - 0.03, "receipt", "requested", size=6.5)
            token(ax, e + 0.05, yc - 0.03, "expert val.", "skip", size=6.5)
        elif val == "false":
            T(ax, cE[0], yc + 0.15, "skip both", 6.9, "#77766f", weight="bold")
            e = token(ax, cE[0], yc - 0.03, "receipt", "skip", size=6.5)
            token(ax, e + 0.05, yc - 0.03, "expert val.", "skip", size=6.5)
        else:
            T(ax, cE[0], yc + 0.24, "hold both and ask", 6.9, "#8a6400", weight="bold")
            e = token(ax, cE[0], yc + 0.07, "receipt", "held", size=6.5)
            token(ax, e + 0.05, yc + 0.07, "expert val.", "held", size=6.5)
            T(ax, cE[0], yc - 0.11, "\u201cWas the watch separately", 6.5, style="italic")
            T(ax, cE[0], yc - 0.23, "insured?\u201d", 6.5, style="italic")
        if i < 2:
            ax.plot([cJ[0] - 0.06, cR[0] - 0.02], [yc - 0.30, yc - 0.30], color=GRID, lw=0.5)
            ax.plot([cR[0] + cR[1] + 0.02, W], [yc - 0.30, yc - 0.30], color=GRID, lw=0.5)
    T(ax, cC[0], 0.28, "on the claim as written,", 6.2, "#8a6400", style="italic")
    T(ax, cC[0], 0.16, "the condition is unresolved", 6.2, "#8a6400", style="italic")
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
            ax.add_patch(Circle((x, y), 0.036, fc=fc, ec=ec, lw=0.7, zorder=3))
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
FATE_EPS = 0.1   # error probability per condition (macro propEps)
SEMANTICS = [("kleene", "Strong Kleene"), ("exact", "Exact deferral"), ("closed", "Open read as false"),
             ("eager", "Open read as true")]


def fate_data(eps=FATE_EPS):
    """The exact computation of scicore/s1_propagation.py (all 150 claims, every judgment vector): each
    condition is judged wrongly with probability eps; rho = 1 makes every error 'unresolved', rho = 0 a
    confident wrong verdict. Per 100 required documents; unnecessary requests in excess of eps = 0."""
    s1 = {(r["eps"], r["rho"]): r for r in
          json.loads((HERE.parent / "scicore" / "out_local" / "s1_propagation.json").read_text())}
    base, n = s1[(0.0, 1.0)], s1[(0.0, 1.0)]["required_total"]
    per100 = {}
    for kind, rho in (("unresolved", 1.0), ("wrong", 0.0)):
        r = s1[(eps, rho)]
        per100[kind] = {s: {"deferred": 100 * r[f"{s}_deferred"] / n, "missed": 100 * r[f"{s}_missed"] / n,
                            "unnecessary": 100 * (r[f"{s}_unnecessary"] - base[f"{s}_unnecessary"]) / n,
                            "deferred_beyond_exact": 100 * (r[f"{s}_deferred"] - r["exact_deferred"]) / n}
                        for s, _ in SEMANTICS}
    return {"per100": per100, "required": n, "claims": base["claims"], "eps": eps}


def fig_fate():
    """Exact computation. Aligned small multiples: rows = kind of judgment error x semantics, columns =
    outcome, one shared scale. Unresolved judgments form a staircase (the semantics decide the outcome);
    confident wrong verdicts form a stripe (every semantics gives the same errors)."""
    F = fate_data()
    P = F["per100"]
    W, H = TW, 2.34
    fig, ax = canvas(W, H)
    kinds = [("unresolved", "Unresolved", "the judgment is left open", "set by the semantics", "#8a6400"),
             ("wrong", "Confidently wrong", "true judged false or the", "the same in all four", MISS)]
    outs = [("deferred", "Held", "behind a question"), ("missed", "Missed", "unsafe error"),
            ("unnecessary", "Unnecessary", "request; unsafe error")]
    xcol = [2.30, 3.46, 4.40]
    scale = 0.85 / 15.0
    rh, gap = 0.150, 0.16
    yh = 2.06
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
    y = yh - 0.38
    for kind, name, sub, fate, fcol in kinds:
        for i, (s, sname) in enumerate(SEMANTICS):
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
        T(ax, 0, yc + 0.14, name, 7.2, INK, weight="bold")
        if kind == "wrong":
            T(ax, 0, yc + 0.005, "true judged false, or", 6.3, MUTED, style="italic")
            T(ax, 0, yc - 0.11, "false judged true", 6.3, MUTED, style="italic")
            T(ax, 0, yc - 0.24, "\u2192 " + fate, 6.3, fcol)
        else:
            T(ax, 0, yc + 0.005, sub, 6.3, MUTED, style="italic")
            T(ax, 0, yc - 0.13, "\u2192 " + fate, 6.3, fcol)
        ax.plot([1.15, 1.15], [y + rh * 0.45, y - 3 * rh - rh * 0.45], color=MUTED, lw=0.6)
        y -= 4 * rh + gap
    ex = P["unresolved"]["kleene"]["deferred_beyond_exact"]
    T(ax, 0, 0.17, f"Per 100 required documents; each condition judged wrongly with probability {F['eps']:.1f}; all "
      f"{F['claims']} claims, {F['required']:,} required documents.", 6.2, MUTED, style="italic")
    T(ax, 0, 0.05, f"Hatched: {ex:.1f} documents strong Kleene evaluation holds although every completion "
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
    """Measured. Unit marks: each design row holds 100 marks, one per required document (largest-remainder
    rounding of the measured shares), filled column by column so each outcome is one contiguous run.
    Unnecessary requests sit outside the 100 as hollow marks (per 100 required documents)."""
    D = outcomes_data()
    W, H = TW, 3.50
    fig, ax = canvas(W, H)
    pitch, ms, gap5 = 0.041, 0.033, 0.020
    x0 = 1.74                                   # first unit mark
    xmiss = x0 + 50 * pitch + 9 * gap5 + 0.03   # exact missed share (rounding can hide it in the marks)
    xu = xmiss + 0.28                           # unnecessary marks
    rowh, dr = 0.172, 0.0215
    kinds = ["requested", "held", "handed", "missed"]

    def mx(base, c):
        return base + c * pitch + (c // 5) * gap5

    from matplotlib.backends.backend_agg import RendererAgg
    rend = RendererAgg(W * fig.dpi, H * fig.dpi, fig.dpi)
    ly = H - 0.10
    lx = 0.0
    for kind, name in (("requested", "requested"), ("held", "held behind a question"), ("handed", "handed over to a person"),
                       ("missed", "missed"), ("unnecessary", "unnecessary request (outside the 100)")):
        unit(ax, lx + 0.03, ly, kind, s=ms)
        lx = T(ax, lx + 0.085, ly, name, 6.8).get_window_extent(renderer=rend).x1 / fig.dpi + 0.13
    T(ax, 0, ly - 0.17, "Each row: 100 marks = 100 required documents, in columns of two; a gap every 10.", 6.3, MUTED,
      style="italic")
    status(ax, W, ly - 0.17, "measured: tenancy claims, three runs", ha="right")
    y = ly - 0.43
    for tag, analysis, mname in MODELS:
        T(ax, 0, y, analysis, 7.4, INK, weight="bold")
        T(ax, x0, y, mname, 7.0, INK, family="Linux Libertine Mono O")
        T(ax, xmiss, y, "missed", 6.0, MUTED, style="italic")
        T(ax, xu, y, "unnecessary per 100", 6.0, MUTED, style="italic")
        y -= 0.19
        group_y = {}
        for role, key, name in OUTCOME_DESIGNS:
            v = D[(tag, key)]
            group_y.setdefault(role, []).append(y)
            T(ax, x0 - 0.07, y, name, 6.7, INK, ha="right")
            if v is None:
                T(ax, x0, y, "not run with this model", 6.4, MUTED, style="italic")
                y -= rowh
                continue
            seq = [k for k, n in zip(kinds, v["units"]) for _ in range(n)]
            for i, kind in enumerate(seq):
                unit(ax, mx(x0, i // 2), y + (dr if i % 2 == 0 else -dr), kind, s=ms)
            T(ax, xmiss, y, f"{v['pct'][3]:.1f}%", 6.0, MISS if v["pct"][3] >= 0.05 else MUTED)
            nu = round(v["unnec_per100"])
            for i in range(nu):
                unit(ax, mx(xu + 0.02, i // 2), y + (dr if i % 2 == 0 else -dr), "unnecessary", s=ms)
            ncol = (nu + 1) // 2
            xl = mx(xu + 0.02, ncol) + (0.01 if nu else 0)
            T(ax, xl, y, f"{v['unnec_per100']:.1f}", 6.4, UNNEC if nu else MUTED)
            y -= rowh
        for role, ys in group_y.items():
            col = MODEL if role == "model" else CODE
            ax.plot([0.02, 0.02], [ys[0] + 0.07, ys[-1] - 0.07], color=col, lw=2.0, solid_capstyle="butt")
            T(ax, 0.075, (ys[0] + ys[-1]) / 2, "model applies" if role == "model" else "code executes", 6.0, col,
              rotation=90, ha="center", va="center")
        y -= 0.10
    save(fig, "fig_outcomes")


# ------------------------------------------------------------------ Fig. 5: every wrong theft change, with its address (measured)
IMPLICATED = ["overlay_rule_042", "overlay_rule_003", "overlay_rule_084", "overlay_rule_074", "overlay_rule_010"]
RULE_SHORT = {"overlay_rule_042": "Assign third-party claims", "overlay_rule_003": "Preserve traces and items",
              "overlay_rule_084": "SIM-card misuse losses", "overlay_rule_074": "Listed valuables \u2265 CHF 1,000",
              "overlay_rule_010": "Date, place, circumstances", "overlay_rule_004": "Mitigate loss after event"}
ISSUE_SHORT = {"condition_broader_than_source": "condition broader than source",
               "condition_narrower_than_source": "condition narrower than source",
               "route_joint_where_alternatives": "both documents where either suffices",
               "route_asks_more_than_source": "route asks more than source",
               "route_missing_alternative": "route misses an alternative"}
IMPLICATED_SHORT = {"route_joint": "both documents where either suffices", "route_more": "route asks more than source",
                    "condition_missing": "condition missing: always applies", "condition_broad": "condition broader than source"}
DOC_TRACE = [("Written assignment to the insurer", "written assignment of claims"),
             ("Insurer's consent to alteration", "insurer's consent, alteration"),
             ("Police consent to the removal", "police consent, traces"),
             ("Bank statement showing the misuse", "bank statement + police report"),
             ("Expert's valuation of the scheduled valuable", "expert valuation"),
             ("Insurer's instruction (Weisung", "insurer's instruction"),
             ("The experts' findings", "experts' findings")]


def trace_data(tag="gpt-6.1-terra"):
    """Every wrong change on the held-out changed-fact theft pairs (three runs), for CasePath and Rules in
    context. CasePath's are attributed to the rules whose requirement produced them (the logic of
    theft_error_origin.py, which wrote error_causes.json); Rules in context records no rule."""
    root = HERE.parent
    if str(root / "harness") not in _sys.path:
        _sys.path.insert(0, str(root / "harness"))
    import theft_methods as tm
    from theft_data import pairs, best_realization
    from theft_score import delta
    P = json.loads((root / "runs" / f"plans_theft_{tag}.json").read_text())

    def short(atom):
        for prefix, s in DOC_TRACE:
            if atom[1:].startswith(prefix):
                return s
        raise KeyError(atom)

    cp, rc = [], []
    for p in pairs():
        if p["split"] != "heldout" or p["kind"] != "on":
            continue
        for r in range(3):
            a, b = P[f"CP|{p['off']}|{r}"], P[f"CP|{p['variant']}|{r}"]
            nu0, nu1 = a["judgments"], b["judgments"]
            changed = {g for g in tm.GUARDS if nu0[g] != nu1[g]}
            pred = delta(set(tm.plan(nu0)["requests"]), set(tm.plan(nu1)["requests"]))
            assert pred == delta(set(a["plan"]["requests"]), set(b["plan"]["requests"]))  # recorded plans agree
            sel, _ = best_realization(pred, p["reference"])
            for atom in sorted(set(pred) - set(sel)):
                prod = (tm.trace(nu1) if atom[0] == "+" else tm.trace(nu0)).get(atom[1:], [])
                rules = sorted({o["rule"] for o in prod if o["guard"] in changed or o["guard"] is None})
                cp.append({"run": r, "sign": atom[0], "doc": short(atom), "rules": rules, "condition": p["condition"]})
            ra = (P.get(f"R|{p['off']}|{r}") or {}).get("plan") or {"requests": []}
            rb = (P.get(f"R|{p['variant']}|{r}") or {}).get("plan") or {"requests": []}
            pred = delta(set(ra["requests"]), set(rb["requests"]))
            sel, _ = best_realization(pred, p["reference"])
            for atom in sorted(set(pred) - set(sel)):
                rc.append({"run": r, "sign": atom[0], "doc": short(atom), "condition": p["condition"]})
    res = load(f"results_{tag}.json")["theft"]
    assert len(cp) == res["CP"]["on"]["wrong"] and len(rc) == res["R"]["on"]["wrong"]
    rv = load("rule_verification.json")
    return {"cp": cp, "rc": rc, "verifier": rv,
            "flagged": sum(1 for v in rv["results"].values() if v["result"] and v["result"]["verdict"] == "flag"),
            "rules_total": len(rv["results"])}


def fig_trace():
    """Measured. One mark per wrong change. CasePath's marks hang from the rule that produced them
    (rule -> verifier flag -> document -> marks); Rules in context's marks are aligned only by the
    document they changed, because no rule is recorded for them."""
    D = trace_data()
    cp, rc, rv = D["cp"], D["rc"], D["verifier"]
    assert all(len(m["rules"]) == 1 for m in cp)
    by_rule = {}
    for m in cp:
        by_rule.setdefault(m["rules"][0], []).append(m)
    rules = sorted(by_rule, key=lambda k: -len(by_rule[k]))
    rules += [k for k in IMPLICATED if k not in rules]          # implicated rules without wrong changes
    rows = []
    for k in rules:
        docs = []
        for m in by_rule.get(k, []):
            if m["doc"] not in docs:
                docs.append(m["doc"])
        rows += [(k, d) for d in docs] or [(k, None)]
    seen = {d for _, d in rows}
    rows += [(None, d) for d in sorted({m["doc"] for m in rc} - seen)]
    W = TW
    rowh = 0.235
    nblocks = len({k for k, _ in rows})
    H = 0.56 + rowh * len(rows) + 0.06 * (nblocks - 1) + 0.40
    fig, ax = canvas(W, H)
    xr, wr, xv, xd, xc, xi = 0.0, 1.66, 1.72, 2.16, 3.34, 4.42   # rule, verifier, document, CasePath, Rules in context
    pitch, ms = 0.064, 0.048
    yh = H - 0.11
    T(ax, xr, yh, "Extracted rule", 7.4, INK, weight="bold")
    T(ax, xr, yh - 0.15, "and its defect", 6.2, MUTED, style="italic")
    T(ax, xv, yh, "Verifier", 7.4, INK, weight="bold")
    T(ax, xd, yh, "Document", 7.4, INK, weight="bold")
    T(ax, xd, yh - 0.15, "changed wrongly", 6.2, MUTED, style="italic")
    T(ax, xc, yh, "CasePath", 7.4, CODE, weight="bold")
    T(ax, xc, yh - 0.15, f"{len(cp)} wrong changes", 6.2, MUTED, style="italic")
    T(ax, xi, yh, "Rules in context", 7.4, MODEL, weight="bold")
    T(ax, xi, yh - 0.15, f"{len(rc)}; no rule recorded", 6.2, MUTED, style="italic")
    y = yh - 0.40
    prev = "start"
    blocks = []
    for k, d in rows:
        if k != prev:
            if prev != "start":
                y -= 0.06
            blocks.append([k, y, y])
            prev = k
        blocks[-1][2] = y
        if d:
            T(ax, xd, y, d, 6.6, INK)
            for col, lst in ((xc, [m for m in by_rule.get(k, []) if m["doc"] == d] if k else []),
                             (xi, [m for m in rc if m["doc"] == d])):
                lst = sorted(lst, key=lambda m: (m["sign"] == "-", m["run"]))
                for i, m in enumerate(lst):
                    unit(ax, col + 0.03 + i * pitch, y, "unnecessary" if m["sign"] == "+" else "missed", s=ms)
                if lst:
                    T(ax, col + 0.03 + len(lst) * pitch, y, f"{len(lst)}", 6.3, MUTED)
        else:
            T(ax, xd, y, "none", 6.4, MUTED, style="italic")
        ax.plot([xd, W], [y - rowh / 2, y - rowh / 2], color=GRID, lw=0.4, zorder=0)
        y -= rowh
    for k, y0, y1 in blocks:
        top, bot = y0 + rowh * 0.44, y1 - rowh * 0.44
        ym = (top + bot) / 2
        if k is None:
            card(ax, xr, bot, wr, top - bot, ec=FAINT, ls=(0, (2, 1.5)))
            T(ax, xr + 0.07, ym, "no rule produced it", 6.6, MUTED, style="italic")
            continue
        res = rv["results"][k]["result"]
        flag = res["verdict"] == "flag"
        defect = IMPLICATED_SHORT[rv["implicated"][k]] if k in rv["implicated"] else \
            ISSUE_SHORT.get(res["issues"][0]["kind"], res["issues"][0]["kind"].replace("_", " "))
        card(ax, xr, bot, wr, top - bot, ec=INK if k in IMPLICATED else FAINT, lw=0.7 if k in IMPLICATED else 0.6)
        runs(ax, xr + 0.06, ym + 0.048, [(f"rule {k[-3:]}  ", {"weight": "bold"}), (RULE_SHORT[k], {})], 6.6)
        T(ax, xr + 0.06, ym - 0.052, defect, 6.0, MUTED, style="italic")
        ax.plot([xr + wr, xd - 0.05], [ym, ym], color=CODE, lw=0.8, zorder=1)    # the address
        chip(ax, xv + 0.02, ym, "flagged" if flag else "passed", "#4a4946" if flag else SKIP, 6.0, "white" if flag else INK)
    unit(ax, 0.03, 0.30, "unnecessary", s=ms)
    T(ax, 0.09, 0.30, "added wrongly (an unnecessary request)", 6.2, MUTED)
    unit(ax, 2.16 + 0.03, 0.30, "missed", s=ms)
    T(ax, 2.16 + 0.09, 0.30, "withdrawn wrongly (a missed document)", 6.2, MUTED)
    n5 = sum(1 for m in cp if m["rules"][0] in IMPLICATED)
    T(ax, 0, 0.12, f"Bold outline: the {len(IMPLICATED)} implicated rules ({n5} of {len(cp)} CasePath errors). The verifier "
      f"flagged them and {D['flagged'] - len(IMPLICATED)} of the other {D['rules_total'] - len(IMPLICATED)} rules.",
      6.2, MUTED, style="italic")
    status(ax, W, 0.30, "measured: gpt-6.1-terra, theft, 3 runs", ha="right")
    save(fig, "fig_trace")


# ------------------------------------------------------------------ Fig. 6: the comparison depends on the model (measured)
def models_data():
    o = load("original_study.json")["table"]
    out = []
    # ordered by capability as described in the paper: cost-efficient, original study's model, frontier
    for tag, label, sub in (("gpt-6-luna", "gpt-6-luna", "cost-efficient; 3 runs"),
                            ("gpt-5.6-terra", "gpt-5.6-terra", "original study; 1 run"),
                            ("gpt-6.1-terra", "gpt-6.1-terra", "frontier; 3 runs")):
        if tag == "gpt-5.6-terra":
            row = {"R": {"wpp": o["R"]["wrong_per_pair"], "wrong": o["R"]["wrong"], "ci": None, "dedup": None},
                   "CP": {"wpp": o["CP-oneroute"]["wrong_per_pair"], "wrong": o["CP-oneroute"]["wrong"], "ci": None,
                          "dedup": None}, "single": True}
        else:
            th = load(f"results_{tag}.json")["theft"]
            row = {k: {"wpp": th[k]["on"]["wrong_per_pair"], "wrong": th[k]["on"]["wrong"],
                       "ci": th[k]["on"]["wrong_per_pair_ci"], "dedup": th[k]["sensitivity_offplan_dedup"]["wrong_per_pair"]}
                   for k in ("R", "CP")}
            row["single"] = False
        row.update(tag=tag, label=label, sub=sub)
        out.append(row)
    return out


def fig_models():
    """Measured. Three models on one axis; wrong changes per pair for the two designs; the off-plan
    deduplication (each repeated error counted once) as an open marker joined to the raw value."""
    M = models_data()
    W, H = TW, 2.30
    fig = plt.figure(figsize=(W, H))
    ax = fig.add_axes([0.10, 0.20, 0.56, 0.68])
    xs = [0, 1, 2]
    for d, col, mk, dx in (("R", MODEL, "o", -0.07), ("CP", CODE, "s", 0.07)):
        pts = [(x + dx, r[d]) for x, r in zip(xs, M)]
        ax.plot([p[0] for p in pts], [p[1]["wpp"] for p in pts], color=col, lw=1.0, zorder=2, alpha=0.9)
        for (x, v), r in zip(pts, M):
            if v["ci"]:
                ax.plot([x, x], v["ci"], color=col, lw=0.8, zorder=1, alpha=0.55, solid_capstyle="butt")
            ax.scatter([x], [v["wpp"]], marker=mk, s=26, color=col if not r["single"] else "white", edgecolors=col,
                       linewidths=1.0, zorder=4)
            if v["dedup"] is not None and abs(v["dedup"] - v["wpp"]) > 1e-9:
                ax.annotate("", xy=(x, v["dedup"]), xytext=(x, v["wpp"]),
                            arrowprops=dict(arrowstyle="-|>,head_length=0.25,head_width=0.12", color=col, lw=0.7,
                                            ls=(0, (2, 1.4)), shrinkA=3, shrinkB=2), zorder=3)
                ax.scatter([x], [v["dedup"]], marker=mk, s=18, color="white", edgecolors=col, linewidths=0.8, zorder=4)
            side = -1 if d == "R" else 1
            ax.text(x + side * 0.09, v["wpp"] + (0.06 if d == "R" or (v["dedup"] is not None and abs(v["dedup"] - v["wpp"]) > 1e-9) else -0.07), f"{v['wpp']:.2f}", fontsize=6.4,
                    color=col, ha="right" if side < 0 else "left", va="center")
            if v["dedup"] is not None and abs(v["dedup"] - v["wpp"]) > 1e-9:
                ax.text(x + side * 0.09, v["dedup"], f"{v['dedup']:.2f}", fontsize=6.0, color=col, style="italic",
                        ha="right" if side < 0 else "left", va="center")
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{r['label']}\n{r['sub']}" for r in M], fontsize=6.6)
    for lab in ax.get_xticklabels():
        lab.set_linespacing(1.1)
    ax.set_xlim(-0.55, 2.55)
    ax.set_ylim(0, 1.7)
    ax.set_yticks([0, 0.5, 1.0, 1.5])
    ax.set_ylabel("Wrong changes per pair\n\u2190 lower is better", fontsize=7.2, linespacing=1.15)
    ax.grid(axis="y", color=GRID, lw=0.5); ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.spines["left"].set_color(MUTED); ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(colors=MUTED, length=2)
    ax.text(2.55, 1.66, "model capability →", fontsize=6.2, color=MUTED, ha="right", va="top", style="italic")
    # direct labels and key (right margin)
    k = fig.add_axes([0.69, 0.20, 0.31, 0.68]); k.axis("off"); k.set_xlim(0, 1); k.set_ylim(0, 1)
    ys = [0.95, 0.81]
    for (name, col, mk, sub), yk in zip((("Rules in context", MODEL, "o", "model applies the rules"),
                                          ("CasePath", CODE, "s", "code executes the rules")), ys):
        k.scatter([0.04], [yk], marker=mk, s=26, color=col, edgecolors=col, linewidths=1.0)
        k.text(0.10, yk + 0.005, name, fontsize=7.2, color=col, weight="bold", va="center")
        k.text(0.10, yk - 0.065, sub, fontsize=6.2, color=MUTED, style="italic", va="center")
    k.scatter([0.04], [0.60], marker="o", s=26, color="white", edgecolors=INK, linewidths=1.0)
    k.text(0.10, 0.60, "single run (original study)", fontsize=6.4, color=INK, va="center")
    k.scatter([0.04], [0.47], marker="o", s=18, color="white", edgecolors=INK, linewidths=0.8)
    k.annotate("", xy=(0.04, 0.485), xytext=(0.04, 0.56), arrowprops=dict(arrowstyle="-", color=INK, lw=0.6,
                                                                       ls=(0, (2, 1.4))))
    k.text(0.10, 0.47, "each repeated error counted once", fontsize=6.4, color=INK, va="center")
    k.text(0.10, 0.40, "(sensitivity analysis)", fontsize=6.0, color=MUTED, va="center", style="italic")
    k.plot([0.0, 0.08], [0.29, 0.29], color=INK, lw=0.8, alpha=0.55)
    k.text(0.10, 0.29, "95% bootstrap interval", fontsize=6.4, color=INK, va="center")
    k.text(0.10, 0.22, "(clustered by changed fact)", fontsize=6.0, color=MUTED, va="center", style="italic")
    k.text(0.0, 0.07, "Theft cases, 27 changed-fact pairs;\nprimary analysis: gpt-6.1-terra.", fontsize=6.0,
           color=MUTED, va="center", style="italic", linespacing=1.1)
    fig.text(0.995, 0.975, "measured", fontsize=6.3, color=MUTED, ha="right", va="top", style="italic",
             bbox=dict(boxstyle="round,pad=0.18,rounding_size=0.06", fc="white", ec=FAINT, lw=0.5))
    save(fig, "fig_models")


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
