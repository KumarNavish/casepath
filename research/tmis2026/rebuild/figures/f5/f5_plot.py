"""Figure 5 drawing from f5_data.json.

    python3 -I f5_plot.py    # f5.svg/.pdf/.png (kept: b), f5_a.png (rejected: tercile lines)

Shared y: all deviations per claim (Study 3 measure; needless holds count).
Dashed ink outline = the planned range of the registered test (Study 4), not yet run: an empty region.
Solid ink = measured on Study 3's sealed tenancy claims. Designs are identified by the label column at the right.
"""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "f4"))
from theme import AMBER, INK, PAPER, SAND, plt, save  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

J = json.loads((HERE / "f5_data.json").read_text())
DS = J["designs"]
YMAX = 2.6
RULE_CATS = ["1", "3", "8", "all"]


def short(d):
    return f"{d['name']} ({'f' if d['model'] == 'frontier' else 'c'})"


def lw(d):
    return 1.8 if d["key"] == "casepath" else (1.2 if d["role"] == "strongest prompt" else 0.7)


def empty(ax, x0, x1, label=True, ymax=YMAX):
    ax.add_patch(Rectangle((x0, 0), x1 - x0, ymax * 0.97, fc="none", ec=INK, lw=0.6, ls=(0, (3, 2.5)), zorder=1))
    if label:
        ax.text(x1, ymax * 0.03, "not yet\nmeasured ", ha="right", va="bottom", fontsize=7, style="italic", zorder=3,
                transform=ax.transData)


def frame(fig, width_right=1.42):
    L, R, B, T = 0.085, 1 - width_right / 5.5, 0.235, 0.90
    gap = 0.035
    w = (R - L - 2 * gap) / 3
    axes = [fig.add_axes([L + i * (w + gap), B, w, T - B]) for i in range(3)]
    for ax in axes:
        ax.set_facecolor(PAPER)
        ax.set_ylim(0, YMAX)
        ax.tick_params(length=2.5, pad=1.5)
    for ax in axes[1:]:
        ax.set_yticklabels([])
    axes[0].set_ylabel("errors per file (all deviations)", fontsize=7.5)
    # length
    a = axes[0]
    a.set_xscale("log")
    a.set_xlim(60, 3200)
    a.set_xticks([77, 150, 367, 2500], ["77", "150", "367", "2,500"])
    a.minorticks_off()
    a.set_xlabel("file length, words", fontsize=7.5)
    empty(a, 367, 2500)
    # rules (ordinal)
    a = axes[1]
    a.set_xlim(-0.6, 3.6)
    a.set_xticks(range(4), RULE_CATS, fontsize=7)
    a.set_xlabel("claim types given", fontsize=7.5)
    empty(a, -0.4, 3.4)
    # share
    a = axes[2]
    a.set_xlim(-4, 54)
    a.set_xticks([0, 10, 25, 33.3, 50], ["0", "10", "25", "33", "50%"])
    a.set_xlabel("files with an open fact", fontsize=7.5)
    empty(a, 0, 50)
    for ax, t in zip(axes, ["Longer files", "More rules", "More open facts"]):
        ax.set_title(t, fontsize=7.5, fontweight="semibold", loc="left", pad=4)
    return axes


def labels(fig, axes, ys):
    """Right label column at each design's measured level, nudged apart; thin sand leaders."""
    ax = axes[2]
    order = sorted(range(len(DS)), key=lambda i: ys[i])
    placed, minsep = {}, 0.155
    last = -1
    for i in order:
        y = max(ys[i], last + minsep)
        placed[i] = y
        last = y
    over = last - (YMAX - 0.05)
    if over > 0:
        for i in placed:
            placed[i] -= over
    for i, d in enumerate(DS):
        ax.annotate(short(d), xy=(33.3, ys[i]), xytext=(56, placed[i]), textcoords="data", fontsize=7, va="center",
                    fontweight="semibold" if d["key"] == "casepath" else "normal", annotation_clip=False,
                    arrowprops=dict(arrowstyle="-", color=SAND, lw=0.5, shrinkA=0, shrinkB=2))


def draw_b():
    fig = plt.figure(figsize=(5.5, 3.4))
    axes = frame(fig)
    lo, hi = J["length"]["min"], J["length"]["max"]
    ys = [d["overall"] for d in DS]
    for d, y in zip(DS, ys):
        axes[0].plot([lo, hi], [y, y], color=INK, lw=lw(d), solid_capstyle="butt", zorder=4)
        axes[1].plot([0.82, 1.18], [y, y], color=INK, lw=lw(d), solid_capstyle="butt", zorder=4)
        axes[2].plot([31.5, 35.1], [y, y], color=INK, lw=lw(d), solid_capstyle="butt", zorder=4)
    labels(fig, axes, ys)
    fig.text(0.085, 0.03, "Ink: measured on Study 3's 96 sealed tenancy claims.   Dashed: planned range of the registered test, "
             "not run.\n(c) cost-efficient model, (f) frontier model.", fontsize=7, va="bottom", linespacing=1.3)
    return fig


def draw_a():
    fig = plt.figure(figsize=(5.5, 3.2))
    axes = frame(fig)
    med = J["length"]["tercile_medians"]
    ys = [d["overall"] for d in DS]
    for d in DS:
        axes[0].plot(med, d["tercile_error"], color=INK, lw=lw(d), marker="o", ms=2.5, zorder=4)
        axes[1].plot([1], [d["overall"]], marker="_", ms=8, color=INK, mew=lw(d))
        axes[2].plot([33.3], [d["overall"]], marker="_", ms=8, color=INK, mew=lw(d))
    axes[0].set_ylim(0, 5.3)
    for ax in axes[1:]:
        ax.set_ylim(0, 5.3)
    # composition strip (share of denied-event claims per tercile)
    for m, c in zip(med, J["length"]["tercile_composition"]):
        axes[0].text(m, 5.0, f"{c.get('denied_event', 0)} denied", fontsize=7, ha="center", color=AMBER)
    labels(fig, axes, ys)
    return fig


if __name__ == "__main__":
    save(draw_b(), "f5", HERE)
    save(draw_a(), "f5_a", HERE, png_only=True)
    print("ok")
