"""Figure 2, "The journey of one sentence": draws f2.svg/.pdf/.png (two lanes, kept) and f2_a.* (one lane, rejected).

Input: f2_data.json (written by extract.py from stored files). No model call.
Above the rule: what models produced (blue): the quoted words and each reading's verdict, as stored.
Below the rule: what code computed (ink, and the state colours): the quotation found word for word in the file, the
agreement of the three readings, the fact's value, the workflow rule that names the fact, the checklist line.
Exception drawn as the record shows it: the full product stores one extra line a model suggested (blue, dashed).
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Circle, Polygon  # noqa: E402

HERE = Path(__file__).resolve().parent
D = json.loads((HERE / "f2_data.json").read_text())

PAPER, INK, SAND = "#FBF8F1", "#1F2A44", "#C9BFA8"
TEAL, AMBER, BLUE = "#008571", "#D9962B", "#4A8FD6"   # coordinator palette update (FIGURE_BRIEF.md)
STATE = {"request": TEAL, "hold": AMBER}
plt.rcParams.update({"font.family": "Inter", "font.size": 7, "svg.fonttype": "none", "pdf.fonttype": 42,
                     "text.color": INK})

W = 5.5
FS = 7.5


def canvas(h):
    fig = plt.figure(figsize=(W, h), facecolor=PAPER)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax


def words_layout(ax, text, x0, y_top, width, lh=0.15):
    """Place the sentence word by word (wrapped at `width` inches); return each word's (x0, x1, baseline y, char span)."""
    r = ax.figure.canvas.get_renderer()
    dpi = ax.figure.dpi
    space = ax.text(0, 0, "a a", fontsize=FS)
    w_aa = space.get_window_extent(r).width / dpi
    space.set_text("aa")
    w_space = w_aa - space.get_window_extent(r).width / dpi
    space.remove()
    out, x, y, pos = [], x0, y_top, 0
    for wd in text.split(" "):
        t = ax.text(x, y, wd, fontsize=FS, va="baseline", ha="left", color=INK, zorder=3)
        ww = t.get_window_extent(r).width / dpi
        if x + ww > x0 + width and x > x0:
            x, y = x0, y - lh
            t.set_position((x, y))
        start = text.index(wd, pos)
        out.append((x, x + ww, y, start, start + len(wd)))
        pos = start + len(wd)
        x += ww + w_space
    return out


def underline(ax, words, text, quote, k, color=BLUE):
    """Blue underline under the words the reading quoted (k-th reading, stacked); returns the end point."""
    s = text.index(quote)
    e = s + len(quote)
    end = None
    for (x0, x1, y, a, b) in words:
        if b > s and a < e:
            yy = y - 0.03 - 0.016 * k
            ax.plot([x0, x1 + 0.03], [yy, yy], color=color, lw=0.9, solid_capstyle="butt", zorder=2)
            end = (x1 + 0.03, yy)
    return end


def reading_mark(ax, x, y, verdict, r=0.034):
    if verdict == "true":
        ax.add_patch(Circle((x, y), r, fc=BLUE, ec="none", zorder=4))
    elif verdict == "false":
        ax.add_patch(Circle((x, y), r, fc=PAPER, ec=BLUE, lw=1.0, zorder=4))
    else:  # open
        ax.add_patch(Circle((x, y), r, fc=PAPER, ec=BLUE, lw=1.0, ls=(0, (1.6, 1.0)), zorder=4))


def value_mark(ax, x, y, fact, r=0.045):
    if fact["status"] == "established":
        ax.add_patch(Circle((x, y), r, fc=INK if fact["value"] else PAPER, ec=INK, lw=1.0, zorder=4))
    else:
        ax.add_patch(Circle((x, y), r, fc=AMBER, ec="none", zorder=4))


def sq(ax, x, y, fc=None, ec=None, s=0.075, ls="-"):
    ax.add_patch(FancyBboxPatch((x - s / 2, y - s / 2), s, s, boxstyle="round,pad=0,rounding_size=0.014",
                                fc=fc or "none", ec=ec or "none", lw=0.9, ls=ls, zorder=4))


def tick(ax, x, y):
    ax.plot([x - 0.022, x - 0.006, x + 0.024], [y + 0.002, y - 0.016, y + 0.022], color=INK, lw=0.9,
            solid_capstyle="round", solid_joinstyle="round", zorder=4)


def below(ax, side, y, xs, lanes):
    """Code's part of one lane, at height y. `lanes`: the x of the three reading lines that come down."""
    S = D[side]
    xa, xv, xr, xl = xs
    dy = 0.075
    for j, xx in enumerate(lanes):
        rd = S["readings"][S.get("mark_order", [0, 1, 2])[j]]
        yy = y + dy * (1 - j)
        ax.plot([xx, xx, xa - 0.05], [RULE_Y[0], yy, yy], color=INK, lw=0.6, zorder=1)
        if rd["found_in_file"]:
            tick(ax, xa, yy)
    # all three agree: one bracket joins them into the fact's value
    ax.plot([xa + 0.05, xa + 0.08, xa + 0.08, xa + 0.05], [y + dy, y + dy, y - dy, y - dy], color=INK, lw=0.7)
    ax.plot([xa + 0.08, xv - 0.05], [y, y], color=INK, lw=0.7, zorder=2)
    value_mark(ax, xv, y, S["fact_stored"])
    # the workflow rule that names the fact: diamond = the condition "fact is true", square = the need it gates
    open_ = S["fact_stored"]["status"] != "established"
    col = AMBER if open_ else INK
    ax.plot([xv + 0.05, xr - 0.06], [y, y], color=col, lw=0.9, ls=(0, (2, 1.4)) if open_ else "-", zorder=2)
    d = 0.06
    ax.add_patch(Polygon([(xr - d, y), (xr, y + d), (xr + d, y), (xr, y - d)], closed=True,
                         fc=AMBER if open_ else INK, ec="none", zorder=4))
    lc = STATE[S["line"]]
    ax.plot([xr + d, xl - 0.05], [y, y], color=lc, lw=0.9, ls=(0, (2, 1.4)) if open_ else "-", zorder=2)
    sq(ax, xl, y, fc=lc)
    if S["question"]:
        ax.add_patch(Circle((xl, y - 0.1), 0.022, fc=AMBER, ec="none", zorder=4))
        ax.plot([xl, xl], [y - 0.04, y - 0.08], color=AMBER, lw=0.7)


def above(ax, side, y_top, xread, lanes, width):
    """The sentence with one blue underline per reading under the words it quoted; the readings stacked at xread;
    from each reading a blue line runs right to its lane and down to the rule."""
    S = D[side]
    words = words_layout(ax, S["sentence"], 0.08, y_top, width, lh=0.21)
    ends = [underline(ax, words, S["sentence"], rd["quote"], k) for k, rd in enumerate(S["readings"])]
    ymid = (words[0][2] + words[-1][2]) / 2
    # stack the reading marks in the vertical order of their quotation's end, so that no two leaders cross
    order = sorted(range(3), key=lambda k: -ends[k][1])
    S["mark_order"] = order
    for pos, k in enumerate(order):
        rd, end, xx = S["readings"][k], ends[k], lanes[pos]
        yk = ymid + 0.085 * (1 - pos)
        reading_mark(ax, xread, yk, rd["verdict"], r=0.03)
        ax.plot([end[0], xread - 0.04], [end[1], yk], color=BLUE, lw=0.5, zorder=1)
        ax.plot([xread + 0.035, xx, xx], [yk, yk, RULE_Y[0]], color=BLUE, lw=0.6, zorder=1)
    return ymid


RULE_Y = [1.9]


def legend(ax, y, items):
    r = ax.figure.canvas.get_renderer()
    x = 0.08
    for draw, label in items:
        draw(x, y)
        t = ax.text(x + 0.07, y, label, va="center", ha="left", fontsize=7)
        x += 0.07 + t.get_window_extent(r).width / ax.figure.dpi + 0.16


def legend_items(ax):
    return [(lambda x, y: ax.plot([x - 0.04, x + 0.04], [y - 0.01, y - 0.01], color=BLUE, lw=0.9), "quoted words"),
            (lambda x, y: reading_mark(ax, x, y, "true", 0.03), "reading: true"),
            (lambda x, y: reading_mark(ax, x, y, "open", 0.03), "reading: open"),
            (lambda x, y: tick(ax, x, y), "quote found in the file"),
            (lambda x, y: value_mark(ax, x, y, {"status": "established", "value": True}, 0.035), "fact true"),
            (lambda x, y: value_mark(ax, x, y, {"status": "unknown"}, 0.035), "fact open")], \
           [(lambda x, y: ax.add_patch(Polygon([(x - 0.045, y), (x, y + 0.045), (x + 0.045, y), (x, y - 0.045)],
                                               fc=INK)), "rule of the workflow"),
            (lambda x, y: sq(ax, x, y, fc=TEAL, s=0.06), "requested now"),
            (lambda x, y: sq(ax, x, y, fc=AMBER, s=0.06), "held"),
            (lambda x, y: ax.add_patch(Circle((x, y), 0.022, fc=AMBER)), "question"),
            (lambda x, y: sq(ax, x, y, ec=BLUE, s=0.06, ls=(0, (2, 1.2))), "suggested by a model, outside the rules")]


def draw_two_lanes(stem):
    H = 3.55
    fig, ax = canvas(H)
    RULE = RULE_Y[0] = 1.9
    ax.plot([0, W], [RULE, RULE], color=INK, lw=0.8)
    ax.text(3.42, RULE + 0.06, "models read", color=BLUE, fontsize=7, va="bottom")
    ax.text(3.42, RULE - 0.06, "code decides", color=INK, fontsize=7, va="top")
    xread, width = 2.78, 2.55
    lanes = {"a": (3.12, 3.17, 3.22), "b": (2.92, 2.97, 3.02)}
    rows = {"a": 1.48, "b": 0.93}
    xs = (3.42, 3.85, 4.35, 4.9)
    ya = above(ax, "a", 3.35, xread, lanes["a"], width)
    yb = above(ax, "b", 2.75, xread, lanes["b"], width)
    for side, ym in (("a", ya), ("b", yb)):
        below(ax, side, rows[side], xs, lanes[side])
        # the stored extra line: a model, reading the whole file, suggested it; it lands beside the checklist
        xm = xs[3] + 0.3
        for _ in D[side]["suggested_by_model"]:
            ax.add_patch(Circle((xm, ym), 0.03, fc=BLUE, ec="none", zorder=4))
            ax.plot([xm, xm], [ym - 0.04, rows[side] + 0.045], color=BLUE, lw=0.6, ls=(0, (2, 1.6)), zorder=1)
            sq(ax, xm, rows[side], ec=BLUE, ls=(0, (2, 1.2)))
    a, b = legend_items(ax)
    legend(ax, 0.45, a)
    legend(ax, 0.2, b)
    save(fig, stem)


def draw_one_lane(stem):
    """Rejected construction: the open sentence alone; the partner (stated) appears nowhere."""
    H = 2.75
    fig, ax = canvas(H)
    RULE = RULE_Y[0] = 1.45
    ax.plot([0, W], [RULE, RULE], color=INK, lw=0.8)
    lanes = (2.95, 3.0, 3.05)
    yb = above(ax, "b", 2.45, 2.78, lanes, 2.55)
    below(ax, "b", 0.95, (3.42, 3.85, 4.35, 4.9), lanes)
    a, b = legend_items(ax)
    legend(ax, 0.3, a)
    save(fig, stem)


def save(fig, stem):
    for ext in ("svg", "pdf", "png"):
        fig.savefig(HERE / f"{stem}.{ext}", dpi=300 if ext == "png" else None, facecolor=PAPER)
    plt.close(fig)


if __name__ == "__main__":
    draw_two_lanes("f2")
    draw_one_lane("f2_a")
