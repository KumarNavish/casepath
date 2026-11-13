"""Figure 3 drawing. Reads f3_data.json (written by compute.py). Writes f3.svg, f3.pdf, f3.png (kept, construction a)
and f3_b_rejected.svg/.png (construction b).

    python3 f3.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Polygon, Circle  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

HERE = Path(__file__).resolve().parent
D = json.loads((HERE / "f3_data.json").read_text(encoding="utf-8"))

for f in font_manager.findSystemFonts():
    if "Inter" in f and "Display" not in f:
        font_manager.fontManager.addfont(f)
plt.rcParams.update({"font.family": "Inter", "svg.fonttype": "none", "pdf.fonttype": 42})

# one visual system (FIGURE_BRIEF.md); teal and model blue moved one step after the palette validator (see CONTRACT.md)
PAPER, INK, SAND = "#FBF8F1", "#1F2A44", "#C9BFA8"
REQ, HOLD, EARLY, DROP, MODEL = "#008571", "#D9962B", "#B5482F", "#4B4A9C", "#4A8FD6"
PT = 1 / 72  # inch per point

QUOTE = "«Ob er das inzwischen gemacht hat oder ob alles noch so ist wie am Parkplatz, weiss ich nicht.»"
QUOTE_EN = "Whether he has had it repaired yet, or all is still as it was at the car park, I do not know."

DOCS = {"police_consent": "police consent", "stolen_items_list": "list of stolen items"}


def chip_style(reading, doc):
    """Fill, edge, text colour, dash, for one checklist line under one reading. Derived from f3_data.json:
    request/hold/not_on_list from the product's evaluator, and the error classes from comparing with 'open'."""
    st = D["readings"][reading]["documents"][doc]["state"]
    open_st = D["readings"]["open"]["documents"][doc]["state"]
    if st == "hold":
        return dict(fc=HOLD, ec=HOLD, tc="white", ls="-")
    if st == "request" and open_st == "hold":   # requested although the file leaves its condition open
        return dict(fc=EARLY, ec=EARLY, tc="white", ls="-")
    if st == "request":
        return dict(fc=REQ, ec=REQ, tc="white", ls="-")
    if st == "not_on_list" and open_st == "hold":  # neither asked nor held although the open fact may need it
        return dict(fc="none", ec=DROP, tc=DROP, ls=(0, (2.2, 1.4)))
    return dict(fc="none", ec=SAND, tc=INK, ls="-")


def chip(ax, x, y, text, s, w=0.92, h=0.2, fs=7.5, mark_q=False):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0,rounding_size=0.05",
                                fc=s["fc"], ec=s["ec"], lw=1.1, ls=s["ls"], zorder=4))
    ax.text(x, y - 0.005, text, ha="center", va="center", fontsize=fs, color=s["tc"], zorder=5,
            fontweight="medium", linespacing=1.05)


def diamond(ax, x, y, reading, r=0.085):
    pts = [(x, y + r), (x + r, y), (x, y - r), (x - r, y)]
    if reading == "open":
        ax.add_patch(Polygon(pts, closed=True, fc=HOLD, ec=HOLD, lw=1.1, zorder=5))
        ax.text(x, y - 0.004, "?", ha="center", va="center", fontsize=7.5, color="white", fontweight="bold", zorder=6)
    else:
        ax.add_patch(Polygon(pts, closed=True, fc=PAPER, ec=INK, lw=1.1, zorder=5))
        ax.add_patch(Circle((x, y), 0.032, fc=INK if reading == "true" else PAPER, ec=INK, lw=0.9, zorder=6))


def step(ax, x, y, r=0.032):
    ax.add_patch(Circle((x, y), r, fc=PAPER, ec=INK, lw=1.0, zorder=5))


EDGE = {"taken": dict(color=INK, lw=1.4, ls="-"), "open": dict(color=HOLD, lw=1.4, ls=(0, (3, 1.6))),
        "not": dict(color=SAND, lw=0.9, ls="-")}


def edge(ax, p, q, kind, arrow=True):
    st = EDGE[kind]
    ax.annotate("", xy=q, xytext=p, zorder=3,
                arrowprops=dict(arrowstyle="-|>" if arrow else "-", color=st["color"], lw=st["lw"], ls=st["ls"],
                                shrinkA=4.5, shrinkB=4.5, mutation_scale=6))


def column(ax, cx, top, reading):
    x0 = cx - 0.3
    P = (x0, top)
    T = (x0 + 0.4, top - 0.4)
    J = (x0, top - 0.8)
    L = (x0, top - 1.12)
    branch_kind = {"true": ("taken", "not"), "false": ("not", "taken"), "open": ("open", "open")}[reading]
    edge(ax, P, T, branch_kind[0])
    edge(ax, T, J, branch_kind[0])
    edge(ax, P, J, branch_kind[1])
    edge(ax, J, L, "taken")
    edge(ax, (x0, top + 0.24), (x0, top + 0.1), "taken")
    diamond(ax, *P, reading)
    step(ax, *T)
    step(ax, *J)
    step(ax, *L)
    chip(ax, T[0] + 0.1 + 0.31, T[1], "police\nconsent", chip_style(reading, "police_consent"), w=0.62, h=0.32)
    chip(ax, L[0], L[1] - 0.17, DOCS["stolen_items_list"], chip_style(reading, "stolen_items_list"), w=1.08)
    # the question the checklist asks: one per open fact it waits for (from the evaluator's waiting_for)
    n_q = len(D["readings"][reading]["waiting_for"])
    if n_q:
        ax.text(T[0] + 0.41, T[1] - 0.25, "1 question" if n_q == 1 else f"{n_q} questions", ha="center", va="center",
                fontsize=7, color=HOLD, fontweight="semibold")


def header(ax, cx, y, reading):
    words = {"true": "read as true", "false": "read as false", "open": "kept open"}[reading]
    ax.text(cx, y, words, ha="center", va="center", fontsize=8, color=INK, fontweight="semibold")


def legend(ax, y, x0=0.18):
    items = [("chip", dict(fc=REQ, ec=REQ, ls="-"), "requested now"),
             ("chip", dict(fc=HOLD, ec=HOLD, ls="-"), "held, one question"),
             ("chip", dict(fc=EARLY, ec=EARLY, ls="-"), "requested too early"),
             ("chip", dict(fc="none", ec=DROP, ls=(0, (2.2, 1.4))), "dropped")]
    XS = [x0, x0 + 1.32, x0 + 2.64, x0 + 3.96]
    for x, (_, s, lab) in zip(XS, items):
        ax.add_patch(FancyBboxPatch((x, y - 0.05), 0.22, 0.1, boxstyle="round,pad=0,rounding_size=0.03",
                                    fc=s["fc"], ec=s["ec"], lw=1.1, ls=s["ls"]))
        ax.text(x + 0.28, y, lab, ha="left", va="center", fontsize=7, color=INK)
    y2 = y - 0.2
    for x, (kind, lab) in zip(XS, (("taken", "path taken"), ("open", "path open"), ("not", "path not taken"))):
        st = EDGE[kind]
        ax.add_line(Line2D([x, x + 0.22], [y2, y2], color=st["color"], lw=st["lw"], ls=st["ls"]))
        ax.text(x + 0.28, y2, lab, ha="left", va="center", fontsize=7, color=INK)
    # fact value by form
    x = XS[3]
    ax.add_patch(Circle((x + 0.05, y2), 0.032, fc=INK, ec=INK, lw=0.9))
    ax.add_patch(Circle((x + 0.15, y2), 0.032, fc=PAPER, ec=INK, lw=0.9))
    ax.text(x + 0.28, y2, "fact true / false", ha="left", va="center", fontsize=7, color=INK)


def quote(ax, y, W):
    ax.text(W / 2, y, QUOTE, ha="center", va="center", fontsize=7.5, color=MODEL, style="italic")
    ax.text(W / 2, y - 0.15, QUOTE_EN, ha="center", va="center", fontsize=7, color=INK)


def draw_a(path_stem):
    W, H = 5.5, 3.0
    fig = plt.figure(figsize=(W, H), facecolor=PAPER)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")
    ax.set_facecolor(PAPER)
    quote(ax, H - 0.14, W)
    cols = {"true": 0.95, "false": 2.75, "open": 4.55}
    for r, cx in cols.items():
        header(ax, cx, H - 0.5, r)
        column(ax, cx, H - 0.88, r)
    # the fact once, beside the first diamond
    ax.text(cols["true"] - 0.3 - 0.13, H - 0.88, "traces\naltered?", ha="right", va="center", fontsize=7, color=INK,
            linespacing=1.05)
    for x in (1.85, 3.65):
        ax.add_line(Line2D([x, x], [0.6, H - 0.42], color=SAND, lw=0.6))
    legend(ax, 0.42)
    for ext in ("svg", "pdf", "png"):
        fig.savefig(HERE / f"{path_stem}.{ext}", dpi=300 if ext == "png" else None, facecolor=PAPER)
    plt.close(fig)


def draw_b(path_stem):
    """Rejected construction: the fragment once (neutral), the three checklists as a matrix beside it."""
    W, H = 5.5, 2.6
    fig = plt.figure(figsize=(W, H), facecolor=PAPER)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")
    quote(ax, H - 0.14, W)
    cx, top = 1.4, H - 0.65
    P, T, J, L = (cx, top), (cx - 0.42, top - 0.42), (cx, top - 0.84), (cx, top - 1.18)
    for p, q in ((P, T), (T, J), (P, J), (J, L)):
        edge(ax, p, q, "not")
    pts = [(P[0], P[1] + 0.085), (P[0] + 0.085, P[1]), (P[0], P[1] - 0.085), (P[0] - 0.085, P[1])]
    ax.add_patch(Polygon(pts, closed=True, fc=PAPER, ec=INK, lw=1.1, zorder=5))
    for s in (T, J, L):
        step(ax, *s)
    ax.text(T[0] - 0.1, T[1], "police consent", ha="right", va="center", fontsize=7, color=INK)
    ax.text(L[0] + 0.1, L[1], "list of stolen items", ha="left", va="center", fontsize=7, color=INK)
    xs = {"true": 2.9, "false": 3.85, "open": 4.8}
    for r, x in xs.items():
        ax.text(x, top + 0.12, {"true": "true", "false": "false", "open": "open"}[r], ha="center", fontsize=8,
                color=INK, fontweight="semibold")
        chip(ax, x, T[1], DOCS["police_consent"], chip_style(r, "police_consent"), w=0.86)
        chip(ax, x, L[1], DOCS["stolen_items_list"], chip_style(r, "stolen_items_list"), w=0.86, fs=6.8)
        ax.add_line(Line2D([2.35, 5.3], [T[1], T[1]], color=SAND, lw=0.4, zorder=1))
        ax.add_line(Line2D([2.35, 5.3], [L[1], L[1]], color=SAND, lw=0.4, zorder=1))
    legend(ax, 0.35)
    for ext in ("svg", "png"):
        fig.savefig(HERE / f"{path_stem}.{ext}", dpi=300 if ext == "png" else None, facecolor=PAPER)
    plt.close(fig)


if __name__ == "__main__":
    pass  # draft-1 construction a superseded by f3.py (house style); kept for construction b
    draw_b("f3_b_rejected")
