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


CELL = 0.064


def row_y(i):
    gap = (0.08 if i >= 1 else 0) + (0.08 if i >= 2 else 0)
    return 3.46 - i * 0.355 - gap


def label(ax, d, y):
    ax.text(1.30, y + 0.20, d["name"], ha="right", va="center", fontsize=7.5,
            fontweight="semibold" if d["key"] == "casepath" else "normal")
    ax.text(1.30, y + 0.07, f"{MODEL[d['model']]} model, {d['runs']} run{'s' if d['runs'] > 1 else ''}",
            ha="right", va="center", fontsize=7)


def grid(ax, x0, y0, seq, cell=CELL, rows=5, dots=False):
    for k, c in enumerate(seq):
        col, r = divmod(k, rows)
        x, y = x0 + col * cell, y0 + (rows - 1 - r) * cell
        ax.add_patch(Rectangle((x, y), cell * 0.84, cell * 0.84, fc=COL[c], ec="none", lw=0))
        if dots and c == "held":
            ax.add_patch(Rectangle((x + cell * 0.31, y + cell * 0.31), cell * 0.22, cell * 0.22, fc=INK, ec="none", lw=0))


def draw_a():
    fig = plt.figure(figsize=(5.5, 4.2))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 5.5), ax.set_ylim(0, 4.2), ax.axis("off")
    XO, XS, XN = 1.40, 2.80, 4.22
    n_open = D[0]["open"]["denominator_document_runs"] // D[0]["runs"]
    n_set = D[0]["settled"]["denominator_document_runs"] // D[0]["runs"]
    heads = [(XO, "Depends on an open fact", "right: hold with one question", f"{n_open} documents, 32 claims"),
             (XS, "Settled by the file", "right: request now", f"{n_set} documents, 63 claims"),
             (XN, "Needs nothing", "extra, per the same 100", "mostly: event denied")]
    for x, a, b, c in heads:
        ax.text(x, 4.11, a, fontsize=7.5, fontweight="semibold", va="center")
        ax.text(x, 3.99, b, fontsize=7, va="center")
        ax.text(x, 3.87, c, fontsize=7, va="center")
    for i, d in enumerate(D):
        y = row_y(i)
        label(ax, d, y)
        o = lr(d["open"]["per100"], OPEN_ORDER)
        grid(ax, XO, y, [k for k in OPEN_ORDER for _ in range(o[k])], dots=(d["key"] == "casepath"))
        s = lr(d["settled"]["per100"], SET_ORDER)
        grid(ax, XS, y, [k for k in SET_ORDER for _ in range(s[k])])
        nn = d["not_needed"]
        h, r = round(nn["needless_holds_per100_settled"]), round(nn["needless_requests_per100_settled"])
        seq = ["held_needlessly"] * h + ["requested_needlessly"] * r
        cols = max(1, -(-len(seq) // 5))
        ax.add_patch(Rectangle((XN - 0.022, y - 0.022), cols * CELL + 0.035, 5 * CELL + 0.035, fc="none", ec=SAND, lw=0.7))
        grid(ax, XN, y, seq)
    # legend, two rows
    def key(x, y, c, t, dot=False):
        ax.add_patch(Rectangle((x, y - 0.027), 0.054, 0.054, fc=c, ec="none", lw=0))
        if dot:
            ax.add_patch(Rectangle((x + 0.017, y - 0.010), 0.02, 0.02, fc=INK, ec="none", lw=0))
        ax.text(x + 0.085, y, t, fontsize=7, va="center")
    key(0.10, 0.27, AMBER, "held")
    key(0.55, 0.27, TEAL, "requested now")
    key(1.40, 0.27, RUST, "requested too early, or not needed")
    key(3.30, 0.27, INDIGO, "dropped: neither requested nor held")
    key(0.10, 0.10, AMBER, "held; its question names the open fact (CasePath only: its questions are fact ids)", dot=True)
    key(4.35, 0.10, INK, "claim handed over")
    ax.add_patch(Rectangle((3.42 + 0.0, 0.10 - 0.03), 0.0, 0.0))
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
