"""Shared house style for the rebuild figures (coordinator's rules, 2026-11-13, revision 2).

White ground, ink text and lines, the brief's state colours, one label size and one number size, marks and gaps on
one grid, a checklist mark primitive and a legend helper. No grey, no pink. Import with

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common")); import style as S
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch  # noqa: E402

# ------------------------------------------------------------------ colour
WHITE = "#FFFFFF"
INK = "#1F2A44"
SAND = "#C9BFA8"
TEAL = "#008571"     # requested now (validator: below the chroma floor; kept by decision, see f4/CONTRACT.md)
AMBER = "#D9962B"    # held (the open fact becomes the hold)
RUST = "#B5482F"     # requested too early, or requested though not needed
INDIGO = "#4B4A9C"   # dropped: neither requested nor held
BLUE = "#4A8FD6"     # a model's reading and its quoted words

STATE = {"requested": TEAL, "held": AMBER, "early": RUST, "dropped": INDIGO, "left": None}
LABEL = {"requested": "requested", "held": "held", "early": "requested too early or not needed",
         "dropped": "dropped", "left": "left alone"}

# ------------------------------------------------------------------ type and grid (inches, points)
FONT = "Inter"
SIZE_LABEL = 7.5     # every word in a figure
SIZE_NUMBER = 7.0    # tick labels and the few numbers
MARK = 0.052         # side of a checklist mark
PITCH = 0.064        # mark-to-mark distance (gap = PITCH - MARK)
UNIT = 0.16          # the spacing step between elements: gaps are 1, 2 or 3 units
LW = 0.7             # one line width for axes and outlines

plt.rcParams.update({
    "font.family": FONT, "font.size": SIZE_LABEL, "text.color": INK, "axes.edgecolor": INK, "axes.labelcolor": INK,
    "xtick.color": INK, "ytick.color": INK, "xtick.labelsize": SIZE_NUMBER, "ytick.labelsize": SIZE_NUMBER,
    "axes.labelsize": SIZE_LABEL, "axes.linewidth": LW, "xtick.major.width": LW, "ytick.major.width": LW,
    "xtick.major.size": 3, "ytick.major.size": 3, "axes.spines.top": False, "axes.spines.right": False,
    "svg.fonttype": "none", "pdf.fonttype": 42, "savefig.dpi": 300, "figure.facecolor": WHITE,
    "axes.facecolor": WHITE,
})


def canvas(w, h):
    """A figure with one full-size axes in inches (x right, y up)."""
    fig = plt.figure(figsize=(w, h), facecolor=WHITE)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w), ax.set_ylim(0, h), ax.axis("off")
    return fig, ax


def checklist_mark(ax, cx, cy, state, s=MARK, outline=None, zorder=3):
    """One checklist line: a rounded square filled with its state's colour; 'left' (or a None colour) is a sand
    outline. outline= overrides the outline colour (e.g. INK for an unfilled ink mark)."""
    fc = STATE.get(state, state)
    r = s * 0.22
    if fc is None:
        ax.add_patch(FancyBboxPatch((cx - s / 2 + LW / 144, cy - s / 2 + LW / 144), s - LW / 72, s - LW / 72,
                                    boxstyle=f"round,pad=0,rounding_size={r}", fc="none",
                                    ec=outline or SAND, lw=LW, zorder=zorder))
    else:
        ax.add_patch(FancyBboxPatch((cx - s / 2, cy - s / 2), s, s, boxstyle=f"round,pad=0,rounding_size={r}",
                                    fc=fc, ec="none", zorder=zorder))


def text_width(ax, t):
    bb = t.get_window_extent(renderer=ax.figure.canvas.get_renderer())
    return bb.width / ax.figure.dpi


def legend(ax, x, y, items, gap=2 * UNIT):
    """One row. items: (state or (kind, colour), label). kind: 'mark' (default), 'dot', 'dash-arrow', 'ink', 'ink-outline'.
    At most five entries."""
    assert len(items) <= 5, "at most five legend entries"
    for key, label in items:
        kind, col = (key if isinstance(key, tuple) else ("mark", key))
        if kind == "mark":
            checklist_mark(ax, x + MARK / 2, y, col)
            dx = MARK
        elif kind == "ink":
            checklist_mark(ax, x + MARK / 2, y, INK)
            dx = MARK
        elif kind == "ink-outline":
            checklist_mark(ax, x + MARK / 2, y, "left", outline=INK)
            dx = MARK
        elif kind == "dot":
            ax.add_patch(Circle((x + 0.03, y), 0.03, fc=col, ec="none"))
            dx = 0.06
        elif kind == "dash-arrow":
            ax.annotate("", xy=(x + 0.26, y), xytext=(x, y),
                        arrowprops=dict(arrowstyle="-|>,head_length=0.35,head_width=0.18", color=col, lw=1.0,
                                        ls=(0, (3, 2)), shrinkA=0, shrinkB=0))
            dx = 0.26
        t = ax.text(x + dx + 0.05, y, label, va="center", ha="left", fontsize=SIZE_LABEL)
        x += dx + 0.05 + text_width(ax, t) + gap
    return x


def save(fig, folder, stem):
    folder = Path(folder)
    fig.savefig(folder / f"{stem}.png", dpi=300, facecolor=WHITE)
    fig.savefig(folder / f"{stem}.svg", facecolor=WHITE)
    fig.savefig(folder / f"{stem}.pdf", facecolor=WHITE)


def save_png(fig, folder, stem):
    fig.savefig(Path(folder) / f"{stem}.png", dpi=300, facecolor=WHITE)
