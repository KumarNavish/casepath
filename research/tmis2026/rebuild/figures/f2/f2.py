"""Figure 2, "The journey of one sentence": draws f2.svg/.pdf/.png (two lanes, kept) and f2_a.* (one lane, rejected).

Input: f2_data.json (written by extract.py from stored files). No model call.
Above the rule: what models produced (blue): the quoted words and each reading's verdict, as stored.
Below the rule: what code computed (ink, and the state colours): the quotation found word for word in the file, the
agreement of the three readings, the rule node that the fact decides (the diamond of Figure 3, with the fact's value
inside), and the one document line it governs. Records: the core (checklist-only scope); no model adds lines there.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
import style as S  # noqa: E402
from matplotlib.patches import Circle, Polygon  # noqa: E402

D = json.loads((HERE / "f2_data.json").read_text())
PAPER, INK, TEAL, AMBER, BLUE = S.WHITE, S.INK, S.TEAL, S.AMBER, S.BLUE
STATE = {"request": "requested", "hold": "held"}
W = 5.5
FS = S.SIZE_LABEL
THIN = 0.35                    # the readings' lines: thinner than any letter stroke of the sentences


def canvas(h):
    return S.canvas(W, h)


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
    lines = {}
    for (x0, x1, y, a, b) in words:
        if b > s and a < e:
            l0, l1 = lines.get(y, (x0, x1))
            lines[y] = (min(l0, x0), max(l1, x1))
    for y, (x0, x1) in sorted(lines.items(), reverse=True):   # one stroke per text line
        yy = y - 0.03 - 0.016 * k
        ax.plot([x0, x1 + 0.02], [yy, yy], color=color, lw=0.6, solid_capstyle="butt", zorder=2)
        end = (x1 + 0.02, yy)
    return end


def reading_mark(ax, x, y, verdict, r=0.034):
    if verdict == "true":
        ax.add_patch(Circle((x, y), r, fc=BLUE, ec="none", zorder=4))
    elif verdict == "false":
        ax.add_patch(Circle((x, y), r, fc=PAPER, ec=BLUE, lw=0.8, zorder=4))
    else:  # open: a hollow amber ring (open is amber everywhere)
        ax.add_patch(Circle((x, y), r, fc=PAPER, ec=AMBER, lw=1.3, zorder=4))


def diamond(ax, x, y, fact, r=0.085):
    """The "fact decides" node of Figure 3 (f3.py::diamond): hollow ink diamond with the value inside
    (filled dot = true, hollow = false); amber diamond with "?" when the fact is open."""
    pts = [(x, y + r), (x + r, y), (x, y - r), (x - r, y)]
    if fact.get("status") != "established":
        ax.add_patch(Polygon(pts, closed=True, fc=AMBER, ec=AMBER, lw=1.1, zorder=5))
        ax.text(x, y - 0.004, "?", ha="center", va="center", fontsize=7.5 if r > 0.07 else 7, color="white", fontweight="bold", zorder=6)
    else:
        ax.add_patch(Polygon(pts, closed=True, fc=PAPER, ec=INK, lw=1.1, zorder=5))
        ax.add_patch(Circle((x, y), 0.032 * r / 0.085, fc=INK if fact["value"] else PAPER, ec=INK, lw=0.9, zorder=6))


def sq(ax, x, y, state):
    S.checklist_mark(ax, x, y, state)


def tick(ax, x, y):
    ax.plot([x - 0.022, x - 0.006, x + 0.024], [y + 0.002, y - 0.016, y + 0.022], color=INK, lw=0.9,
            solid_capstyle="round", solid_joinstyle="round", zorder=4)


def below(ax, side, y, xs, lanes):
    """Code's part of one lane, at height y. `lanes`: the x of the three reading lines that come down."""
    Sd = D[side]
    xa, xr, xl = xs
    dy = 0.075
    for j, xx in enumerate(lanes):
        rd = Sd["readings"][Sd.get("mark_order", [0, 1, 2])[2 - j]]
        yy = y + dy * (j - 1)                                     # rightmost line -> top tick: no crossing
        ax.plot([xx, xx, xa - 0.05], [RULE_Y[0], yy, yy], color=INK, lw=THIN, zorder=1)
        if rd["found_in_file"]:
            tick(ax, xa, yy)
    # all three agree: one bracket joins them; the admitted fact enters the one rule node it decides
    ax.plot([xa + 0.05, xa + 0.08, xa + 0.08, xa + 0.05], [y + dy, y + dy, y - dy, y - dy], color=INK, lw=0.7)
    ax.plot([xa + 0.08, xr - 0.085], [y, y], color=INK, lw=0.7, zorder=2)
    diamond(ax, xr, y, Sd["fact_stored"])
    # its one outgoing document line, as in Figure 3: path taken (ink) or path open (amber, dashed)
    open_ = Sd["fact_stored"]["status"] != "established"
    lc = STATE[Sd["line"]]
    ax.plot([xr + 0.085, xl - 0.05], [y, y], color=AMBER if open_ else INK, lw=1.4,
            ls=(0, (3, 1.6)) if open_ else "-", zorder=2)
    sq(ax, xl, y, lc)
    if Sd["question"]:
        ax.add_patch(Circle((xl, y - S.MARK / 2 - 0.04), 0.02, fc=AMBER, ec="none", zorder=4))


def above(ax, side, y_top, xread, lanes, width):
    """The sentence with one blue underline per reading under the words it quoted; the readings stacked at xread;
    from each reading a blue line runs right to its lane and down to the rule."""
    Sd = D[side]
    words = words_layout(ax, Sd["sentence"], 0.08, y_top, width, lh=0.21)
    ends = [underline(ax, words, Sd["sentence"], rd["quote"], k) for k, rd in enumerate(Sd["readings"])]
    ymid = (words[0][2] + words[-1][2]) / 2
    # stack the reading marks in the vertical order of their quotation's end, so that no two leaders cross
    order = sorted(range(3), key=lambda k: -ends[k][1])
    Sd["mark_order"] = order
    for pos, k in enumerate(order):
        rd, end, xx = Sd["readings"][k], ends[k], lanes[2 - pos]   # top mark -> rightmost line: no crossing
        yk = ymid + 0.085 * (1 - pos)
        reading_mark(ax, xread, yk, rd["verdict"], r=0.026)
        ax.plot([end[0], xread - 0.04], [end[1], yk], color=BLUE, lw=THIN, zorder=1)
        ax.plot([xread + 0.035, xx, xx], [yk, yk, RULE_Y[0]], color=BLUE, lw=THIN, zorder=1)
    return ymid


RULE_Y = [1.9]


def legend(ax, y, items, x=0.1):
    assert len(items) <= 5
    for draw, label in items:
        dx = draw(x, y)
        t = ax.text(x + dx + 0.05, y, label, va="center", ha="left", fontsize=S.SIZE_LABEL)
        x += dx + 0.05 + S.text_width(ax, t) + S.UNIT


def legend_items(ax):
    def quoted(x, y):
        ax.plot([x, x + 0.16], [y - 0.035, y - 0.035], color=BLUE, lw=0.6)
        ax.plot([x, x + 0.16], [y - 0.05, y - 0.05], color=BLUE, lw=0.6)
        return 0.16

    def readings(x, y):
        reading_mark(ax, x + 0.026, y, "true", 0.026)
        reading_mark(ax, x + 0.1, y, "open", 0.026)
        return 0.126

    def found(x, y):
        tick(ax, x + 0.025, y)
        return 0.05

    def facts(x, y):
        diamond(ax, x + 0.06, y, {"status": "established", "value": True}, r=0.06)
        diamond(ax, x + 0.2, y, {"status": "unknown"}, r=0.06)
        return 0.26

    def lines(x, y):
        S.checklist_mark(ax, x + S.MARK / 2, y, "requested")
        S.checklist_mark(ax, x + S.MARK / 2 + S.PITCH, y, "held")
        return S.MARK + S.PITCH

    return [(quoted, "quoted"), (readings, "reading true / open"), (found, "quote found"),
            (facts, "fact true / open"), (lines, "requested / held")]


def draw_two_lanes(stem):
    H = 3.3
    fig, ax = canvas(H)
    RULE = RULE_Y[0] = 1.65
    ax.plot([0, W], [RULE, RULE], color=INK, lw=S.LW)
    ax.text(3.42, RULE + 0.06, "models read", color=BLUE, fontsize=S.SIZE_LABEL, va="bottom")
    ax.text(3.42, RULE - 0.06, "code decides", color=INK, fontsize=S.SIZE_LABEL, va="top")
    xread, width = 2.78, 2.55
    lanes = {"a": (3.12, 3.17, 3.22), "b": (2.92, 2.97, 3.02)}
    rows = {"a": 1.23, "b": 0.7}
    xs = (3.42, 4.1, 4.95)
    ya = above(ax, "a", 3.1, xread, lanes["a"], width)
    yb = above(ax, "b", 2.5, xread, lanes["b"], width)
    for side, ym in (("a", ya), ("b", yb)):
        below(ax, side, rows[side], xs, lanes[side])
    # the two mechanism words, once each
    ax.text(xread + 0.07, ya + 0.085 + 0.05, "3 readings", color=S.INK, fontsize=S.SIZE_LABEL, va="bottom", ha="left")
    ax.text(xs[0] + 0.14, rows["a"] + 0.04, "all agree", color=S.INK, fontsize=S.SIZE_LABEL, va="bottom", ha="left")
    legend(ax, 0.2, legend_items(ax))
    save(fig, stem)


def draw_one_lane(stem):
    """Rejected construction: the open sentence alone; the partner (stated) appears nowhere."""
    H = 2.75
    fig, ax = canvas(H)
    RULE = RULE_Y[0] = 1.45
    ax.plot([0, W], [RULE, RULE], color=INK, lw=S.LW)
    lanes = (2.95, 3.0, 3.05)
    yb = above(ax, "b", 2.45, 2.78, lanes, 2.55)
    below(ax, "b", 0.95, (3.42, 4.1, 4.95), lanes)
    legend(ax, 0.2, legend_items(ax))
    save(fig, stem)


def save(fig, stem):
    S.save(fig, HERE, stem)


if __name__ == "__main__":
    draw_two_lanes("f2")
    draw_one_lane("f2_a")
