"""Figure 4 drawing from f4_data.json (no computation of results here).

    python3 -I f4_plot.py     # f4.svg/.pdf/.png (kept: construction a), f4_b.png (rejected: construction b)

a: unit picture. Per design and panel, 100 marks in a 5 x 20 grid, filled column by column in fate order; counts
   are the per-100 shares rounded by largest remainder (exact values in f4_data.json). Right of the settled grid,
   inside a sand outline (reference: not needed), the extra actions on documents the file does not need, on the
   same per-100-settled scale.
b: aligned bars of the errors only, per 100 (exact values), on a common zero.
"""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from theme import AMBER, INDIGO, INK, PAPER, RUST, SAND, TEAL, plt, save  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

D = json.loads((HERE / "f4_data.json").read_text())["designs"]
COL = {"held": AMBER, "too_early": RUST, "dropped": INDIGO, "handed": INK, "requested": TEAL,
       "held_needlessly": AMBER, "requested_needlessly": RUST}
OPEN_ORDER = ["held", "too_early", "dropped", "handed"]
SET_ORDER = ["requested", "held_needlessly", "dropped", "handed"]
MODEL = {"cost-efficient": "cost-efficient", "frontier": "frontier"}


def lr(shares, order, total=100):
    """Largest-remainder rounding of shares (sum 100) to integer marks."""
    v = [shares.get(k, 0.0) for k in order]
    base = [int(x) for x in v]
    rest = total - sum(base)
    for i in sorted(range(len(v)), key=lambda i: -(v[i] - base[i]))[:rest]:
        base[i] += 1
    return dict(zip(order, base))


CELL = 0.056
PITCH = 0.335
BLOCK_GAP = 0.20


def row_y(i):
    """Rows top to bottom; a block header gap before the first row of each model block."""
    blocks = sum(1 for d in D[:i + 1] if d is D[0] or d["model"] != D[D.index(d) - 1]["model"])
    return 3.66 - i * PITCH - blocks * BLOCK_GAP


def grid(ax, x0, y0, seq, cell=CELL, rows=5):
    for k, c in enumerate(seq):
        col, r = divmod(k, rows)
        x, y = x0 + col * cell, y0 + (rows - 1 - r) * cell
        ax.add_patch(Rectangle((x, y), cell * 0.84, cell * 0.84, fc=COL[c], ec="none", lw=0))


def draw_a():
    fig = plt.figure(figsize=(5.5, 4.2))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 5.5), ax.set_ylim(0, 4.2), ax.axis("off")
    XO, XS, XN = 1.40, 2.80, 4.20
    for x, t in ((XO, "depends on an open fact"), (XS, "settled by the file"), (XN, "nothing needed")):
        ax.text(x, 4.10, t, fontsize=7.5, fontweight="semibold", va="center")
    for i, d in enumerate(D):
        y = row_y(i)
        if i == 0 or d["model"] != D[i - 1]["model"]:
            ax.text(0.10, y + 5 * CELL + 0.09, f"{d['model']} model", fontsize=7, style="italic", va="center")
            ax.plot([0.10, 5.40], [y + 5 * CELL + 0.035] * 2, color=SAND, lw=0.6)
        ax.text(1.30, y + 2.5 * CELL, d["name"], ha="right", va="center", fontsize=7.5,
                fontweight="semibold" if d["role"] == "the product" else "normal")
        o = lr(d["open"]["per100"], OPEN_ORDER)
        grid(ax, XO, y, [k for k in OPEN_ORDER for _ in range(o[k])])
        st = lr(d["settled"]["per100"], SET_ORDER)
        grid(ax, XS, y, [k for k in SET_ORDER for _ in range(st[k])])
        nn = d["not_needed"]
        h, r = round(nn["needless_holds_per100_settled"]), round(nn["needless_requests_per100_settled"])
        seq = ["held_needlessly"] * h + ["requested_needlessly"] * r
        cols = max(1, -(-len(seq) // 5))
        ax.add_patch(Rectangle((XN - 0.02, y - 0.02), cols * CELL + 0.03, 5 * CELL + 0.03, fc="none", ec=SAND, lw=0.7))
        grid(ax, XN, y, seq)
    x = 0.10
    for c, t in [(AMBER, "held"), (TEAL, "requested now"), (RUST, "requested too early, or not needed"),
                 (INDIGO, "dropped: neither"), (INK, "claim handed over")]:
        ax.add_patch(Rectangle((x, 0.10 - 0.027), 0.054, 0.054, fc=c, ec="none", lw=0))
        ax.text(x + 0.085, 0.10, t, fontsize=7, va="center")
        x += 0.24 + 0.050 * len(t)
    return fig


def draw_b():
    fig, axes = plt.subplots(1, 3, figsize=(5.5, 3.6), sharey=True, gridspec_kw={"width_ratios": [1.3, 0.8, 0.8]})
    ys = [-row_y(i) for i in range(len(D))]
    for ax, title in zip(axes, ["open fact: errors per 100", "settled: errors per 100", "not needed: extra per 100 settled"]):
        ax.set_title(title, fontsize=7.5, loc="left", color=INK)
    for d, y in zip(D, ys):
        x = 0
        for k in ["too_early", "dropped", "handed"]:
            v = d["open"]["per100"].get(k, 0)
            axes[0].barh(y, v, left=x, height=0.25, color=COL[k]); x += v
        x = 0
        for k in ["held_needlessly", "dropped", "handed"]:
            v = d["settled"]["per100"].get(k, 0)
            axes[1].barh(y, v, left=x, height=0.25, color=COL[k]); x += v
        nn = d["not_needed"]
        axes[2].barh(y, nn["needless_holds_per100_settled"], height=0.25, color=AMBER)
        axes[2].barh(y, nn["needless_requests_per100_settled"], left=nn["needless_holds_per100_settled"], height=0.25, color=RUST)
    axes[0].set_yticks(ys, [f"{d['name']} · {d['model'][:4]}." for d in D], fontsize=7)
    axes[0].set_xlim(0, 70), axes[1].set_xlim(0, 20), axes[2].set_xlim(0, 40)
    for ax in axes:
        ax.set_facecolor(PAPER)
    fig.subplots_adjust(left=0.30, right=0.98, top=0.9, bottom=0.08, wspace=0.12)
    return fig


if __name__ == "__main__":
    fa = draw_a()
    save(fa, "f4", HERE)
    save(fa, "f4_a", HERE, png_only=True)
    fb = draw_b()
    save(fb, "f4_b", HERE, png_only=True)
    print("ok")
