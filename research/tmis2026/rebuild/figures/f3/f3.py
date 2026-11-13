"""Figure 3 (house style, rebuild/figures/common/style.py). Reads f3_data.json (compute.py). Writes f3.svg/.pdf/.png.
The rejected construction b is drawn by f3_draft1.py (first-draft style).

    python3 f3.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
import style as S  # noqa: E402
from matplotlib.patches import Polygon, Circle  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

D = json.loads((HERE / "f3_data.json").read_text(encoding="utf-8"))
QUOTE = "«Ob er das inzwischen gemacht hat oder ob alles noch so ist wie am Parkplatz, weiss ich nicht.»"
QUOTE_EN = "Whether he has had it repaired yet, or all is still as it was at the car park, I do not know."
U = S.UNIT
DOC = 2 * S.MARK + 0.02      # a document line drawn as an enlarged checklist mark (0.124 in)


def state(reading, doc):
    """Checklist state of one line under one reading, from the product's evaluator (f3_data.json); the error classes
    are judged against the open reading."""
    st = D["readings"][reading]["documents"][doc]["state"]
    open_st = D["readings"]["open"]["documents"][doc]["state"]
    if st == "hold":
        return "held"
    if st == "request":
        return "early" if open_st == "hold" else "requested"
    if st == "not_on_list" and open_st == "hold":
        return "dropped"
    return "left"


EDGE = {"taken": dict(color=S.INK, lw=1.2, ls="-"), "open": dict(color=S.AMBER, lw=1.2, ls=(0, (3, 2))),
        "not": dict(color=S.SAND, lw=S.LW, ls="-")}


def edge(ax, p, q, kind):
    st = EDGE[kind]
    ax.annotate("", xy=q, xytext=p, zorder=2,
                arrowprops=dict(arrowstyle="-|>,head_length=0.35,head_width=0.18", color=st["color"], lw=st["lw"],
                                ls=st["ls"], shrinkA=4, shrinkB=4))


def diamond(ax, x, y, reading, r=0.075):
    pts = [(x, y + r), (x + r, y), (x, y - r), (x - r, y)]
    if reading == "open":
        ax.add_patch(Polygon(pts, closed=True, fc=S.AMBER, ec="none", zorder=4))
        ax.text(x, y - 0.004, "?", ha="center", va="center", fontsize=S.SIZE_LABEL * min(1, r / 0.075 * 1.1), color=S.WHITE,
                fontweight="bold", zorder=5)
    else:
        ax.add_patch(Polygon(pts, closed=True, fc=S.WHITE, ec=S.INK, lw=1.0, zorder=4))
        ax.add_patch(Circle((x, y), r * 0.35, fc=S.INK if reading == "true" else S.WHITE, ec=S.INK, lw=0.8, zorder=5))


def step(ax, x, y):
    ax.add_patch(Circle((x, y), 0.026, fc=S.WHITE, ec=S.INK, lw=S.LW + 0.2, zorder=4))


def column(ax, cx, top, reading, labels):
    P, T, J, L = (cx, top), (cx + 2 * U, top - 2 * U), (cx, top - 4 * U), (cx, top - 6 * U)
    a, b = {"true": ("taken", "not"), "false": ("not", "taken"), "open": ("open", "open")}[reading]
    edge(ax, (cx, top + 1.5 * U), (cx, top + 0.4 * U), "taken")
    edge(ax, P, T, a)
    edge(ax, T, J, a)
    edge(ax, P, J, b)
    edge(ax, J, L, "taken")
    diamond(ax, *P, reading)
    for s in (T, J, L):
        step(ax, *s)
    mx = T[0] + U + DOC / 2
    S.checklist_mark(ax, mx, T[1], state(reading, "police_consent"), s=DOC)
    S.checklist_mark(ax, L[0] + U + DOC / 2, L[1], state(reading, "stolen_items_list"), s=DOC)
    ax.text(mx + DOC / 2 + 0.06, T[1], "police\nconsent", va="center", fontsize=S.SIZE_LABEL, linespacing=1.0)
    ax.text(L[0] + U + DOC + 0.06, L[1], "stolen\nitems", va="center", fontsize=S.SIZE_LABEL, linespacing=1.0)
    ax.text(cx + 0.3, top + 2.6 * U, {"true": "read as true", "false": "read as false", "open": "kept open"}[reading],
            ha="center", va="center", fontsize=S.SIZE_LABEL, fontweight="semibold")
    if labels:
        ax.text(cx - U, top, "traces\naltered?", va="center", ha="right", fontsize=S.SIZE_LABEL, linespacing=1.0)


def main():
    W, H = 5.5, 2.6
    fig, ax = S.canvas(W, H)
    ax.text(W / 2, H - 0.8 * U, QUOTE, ha="center", va="center", fontsize=7, color=S.BLUE, style="italic")
    ax.text(W / 2, H - 1.7 * U, QUOTE_EN, ha="center", va="center", fontsize=7, color=S.INK)
    top = H - 6.2 * U
    for i, (r, cx) in enumerate((("true", 1.05), ("false", 2.65), ("open", 4.25))):
        column(ax, cx, top, r, labels=(i == 0))
    # legend: the fact's three values, then four line states with the shared marks
    y = 1.3 * U
    x0 = 0.15
    for k, r in enumerate(("true", "false", "open")):
        diamond(ax, x0 + 0.05 + k * 0.15, y, r, r=0.05)
    t = ax.text(x0 + 0.44, y, "fact true / false / open", va="center", fontsize=S.SIZE_LABEL)
    x = x0 + 0.42 + S.text_width(ax, t) + 1.2 * U
    S.legend(ax, x, y, [("requested", "requested"), ("held", "held, one question"), ("early", "too early"),
                        ("dropped", "dropped")], gap=1.2 * U)
    S.save(fig, HERE, "f3")


if __name__ == "__main__":
    main()
