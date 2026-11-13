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
        ax.text(x, y - 0.004, "?", ha="center", va="center", fontsize=S.SIZE_LABEL, color=S.WHITE,
                fontweight="bold", zorder=5)
    else:
        ax.add_patch(Polygon(pts, closed=True, fc=S.WHITE, ec=S.INK, lw=1.0, zorder=4))
        ax.add_patch(Circle((x, y), 0.026, fc=S.INK if reading == "true" else S.WHITE, ec=S.INK, lw=0.8, zorder=5))


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
    if labels:
        ax.text(mx + DOC / 2 + 0.06, T[1], "police consent", va="center", fontsize=S.SIZE_LABEL)
        ax.text(L[0] + U + DOC + 0.06, L[1], "stolen items", va="center", fontsize=S.SIZE_LABEL)
        ax.text(cx - U, top, "traces altered?", va="center", ha="right", fontsize=S.SIZE_LABEL)


def main():
    W, H = 5.5, 2.45
    fig, ax = S.canvas(W, H)
    ax.text(W / 2, H - U, QUOTE, ha="center", va="center", fontsize=S.SIZE_LABEL, color=S.BLUE, style="italic")
    ax.text(W / 2, H - 2 * U, QUOTE_EN, ha="center", va="center", fontsize=S.SIZE_LABEL, color=S.INK)
    top = H - 5 * U
    for i, (r, cx) in enumerate((("true", 1.15), ("false", 2.85), ("open", 4.45))):
        column(ax, cx, top, r, labels=(i == 0))
    # legend: four states with the shared marks, one entry for the paths
    y = 1.5 * U
    x = S.legend(ax, 0.2, y, [("requested", "requested"), ("held", "held, one question"), ("early", "too early"),
                              ("dropped", "dropped")], gap=1.5 * U)
    for k, kind in enumerate(("taken", "open")):
        st = EDGE[kind]
        ax.add_line(Line2D([x + k * 0.3, x + k * 0.3 + 0.22], [y, y], color=st["color"], lw=st["lw"], ls=st["ls"]))
    ax.text(x + 0.57, y, "taken / open", va="center", fontsize=S.SIZE_LABEL)
    S.save(fig, HERE, "f3")


if __name__ == "__main__":
    main()
