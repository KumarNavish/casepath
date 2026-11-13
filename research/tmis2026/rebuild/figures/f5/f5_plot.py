"""Figure 5, revision 2: as cases get real. Reads f5_data.json only.

    python3 -I f5_plot.py    # f5.{png,svg,pdf} (kept: a, dot + predicted arrow), f5_b.png (rejected: dots alone)

Cost-efficient model, two designs: CasePath (core) and the prompt that may hold.
Solid dot = the one measured value per design (all deviations per file, Study 3 sealed tenancy), at its true x:
median file length 172 words (message plus attachments); one regime's rules; 32 of 96 files with an open fact (33%).
Dashed arrow = the direction the registered hypothesis predicts (CasePath level, the prompt upward); its length and
end carry no value. x ticks only at the planned levels of the registered test.
"""
import json
import math
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "common"))
import style as S  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

J = json.loads((HERE / "f5_data.json").read_text())
D = {d["key"]: d for d in J["designs"]}
CP, PR = D["casepath_checklist"], D["hold_prompt"]
X_LEN = J["length"]["tercile_medians"][1]              # 172 words
X_SHARE = 100 * J["open_share"]["share"]               # 33.3 %
PANELS = [("longer files", "log", (110, 3200), [330, 800, 2500], ["330", "800", "2,500"], X_LEN),
          ("more rules", "lin", (0.6, 4.4), [1, 3, 4], ["1", "3", "4"], 1),
          ("more open facts", "lin", (-3, 55), [0, 10, 25, 50], ["0", "10", "25", "50%"], X_SHARE)]
YMAX = 1.6
W, H = 5.5, 2.35


def arrow(ax, scale, x0, y0, up, frac=0.30):
    """A short dashed arrow from the dot: a fixed fraction of the axis width; rise is a fixed angle, no value."""
    lo, hi = ax.get_xlim()
    if scale == "log":
        x1 = math.exp(math.log(x0) + frac * (math.log(hi) - math.log(lo)))
    else:
        x1 = x0 + frac * (hi - lo)
    y1 = y0 + (0.38 * frac / 0.30 if up else 0.0)
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="-|>,head_length=0.35,head_width=0.18", color=S.INK, lw=1.0,
                                ls=(0, (3, 2)), shrinkA=4, shrinkB=0), zorder=2)
    return x1, y1


def draw(with_arrows=True):
    fig = plt.figure(figsize=(W, H))
    L, B, w, h, gap = 0.09, 0.30, 0.255, 0.60, 0.045
    axes = [fig.add_axes([L + i * (w + gap), B, w, h]) for i in range(3)]
    for i, (ax, (title, scale, xl, ticks, tl, x)) in enumerate(zip(axes, PANELS)):
        if scale == "log":
            ax.set_xscale("log")
        ax.set_xlim(*xl)
        ax.set_xticks(ticks, tl)
        ax.minorticks_off()
        ax.set_ylim(0, YMAX)
        ax.set_yticks([0, 0.5, 1.0, 1.5], ["0", "0.5", "1", "1.5"] if i == 0 else [""] * 4)
        ax.set_title(title, fontsize=S.SIZE_LABEL, fontweight="semibold", loc="left", pad=6)
        for d, up in ((CP, False), (PR, True)):
            if with_arrows:
                arrow(ax, scale, x, d["overall"], up, frac=0.17)
            ax.plot(x, d["overall"], "o", ms=5.5, color=S.INK, zorder=3)
        if i == 2:
            ax.text(x + 4, CP["overall"] - 0.17, "CasePath", fontsize=S.SIZE_LABEL, va="center",
                    fontweight="semibold")
            ax.text(x + 2, PR["overall"] + 0.30, "prompt that may hold", fontsize=S.SIZE_LABEL, va="center", ha="center")
    axes[0].set_ylabel("errors per file")
    lg = fig.add_axes([0, 0, 1, 0.12])
    lg.set_xlim(0, W), lg.set_ylim(0, 0.12 * H), lg.axis("off")
    items = [(("dot", S.INK), "measured")]
    if with_arrows:
        items.append((("dash-arrow", S.INK), "predicted, to be tested"))
    S.legend(lg, 0.50, 0.12, items)
    return fig


if __name__ == "__main__":
    S.save(draw(True), HERE, "f5")
    S.save_png(draw(False), HERE, "f5_b")
    print("CasePath", round(CP["overall"], 3), "prompt that may hold", round(PR["overall"], 3), "x", X_LEN, round(X_SHARE, 1))
