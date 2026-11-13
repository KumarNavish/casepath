"""Figure 1, "One changed sentence": f1.svg/.pdf/.png (kept construction a), f1_b.* (rejected b) and
f1_rails.png (the variant with rails, for the rails decision).

Input: f1_data.json (extract.py, from stored files; the core's checklists). No model call. House style:
../common/style.py. Every mark is from that file: page bars = the claim's sentences (length in characters; the changed
sentence in ink), squares = the 27 document needs of the workflow in workflow order with the state the stored checklist
gives, dots = the stored questions, one per open fact a held line waits for, under the hold whose rule names it.
"""
import json
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
import style as S  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle, Circle  # noqa: E402

D = json.loads((HERE / "f1_data.json").read_text())
STATE = {"request": "requested", "hold": "held", "not_needed": "left"}

W, H = 5.5, 2.75
X0 = 3.42                      # first need of the strip
YA, YB = 2.2, 0.98             # strip heights of claim A (stated) and claim B (left open)
DOT = 0.016                    # question dot radius
DOT_STEP = 0.048


def page(ax, side, x0, y_top, w=0.72, chars=78, lh=0.025):
    """Measured page miniature: one bar per sentence, wrapped at `chars` characters per line. Returns the y of the
    changed sentence's first bar."""
    pad = 0.045
    unit = (w - 2 * pad) / chars
    y = y_top - pad - lh / 2
    idx, segs = 0, []
    for para in side["paragraphs"]:
        col = 0
        for s in para:
            n = len(s) + 1
            changed = idx == D["changed_sentence_index"]
            while n > 0:
                take = min(n, chars - col)
                segs.append((x0 + pad + col * unit, y, take * unit - unit * 0.6, changed))
                col += take
                n -= take
                if col >= chars:
                    col, y = 0, y - lh
            idx += 1
        y -= lh * (1.6 if col else 0.6)
    bottom = y + lh * 0.6 - pad
    ax.add_patch(Rectangle((x0, bottom), w, y_top - bottom, fc=S.WHITE, ec=S.SAND, lw=S.LW, zorder=1))
    for (x, yy, ww, ch) in segs:
        h = 0.014 if ch else 0.009
        ax.add_patch(Rectangle((x, yy - h / 2), max(ww, 0.004), h, fc=S.INK if ch else S.SAND, ec="none", zorder=2))
    return max(s[1] for s in segs if s[3])


def sentence(ax, text, x, y_top, width_chars=34):
    ax.text(x, y_top, "\n".join(textwrap.wrap(text, width_chars)), va="top", ha="left", fontsize=S.SIZE_LABEL,
            linespacing=1.45, color=S.INK, zorder=3)


def strip(ax, rows, y):
    for i, r in enumerate(rows):
        S.checklist_mark(ax, X0 + S.PITCH * i, y, STATE[r["state"]])
    # questions: one dot per open fact a held line waits for; a shared fact sits once, between its two holds
    seen = {}
    for i, r in enumerate(rows):
        for q in r["questions"]:
            seen.setdefault(q, []).append(i)
    stack = {}
    for q, cols in seen.items():
        k = stack.get(tuple(cols), 0)
        stack[tuple(cols)] = k + 1
        cx = X0 + S.PITCH * sum(cols) / len(cols)
        ax.add_patch(Circle((cx, y - S.MARK / 2 - 0.04 - DOT_STEP * k), DOT, fc=S.AMBER, ec="none", zorder=3))


def draw_a(stem, rails):
    fig, ax = S.canvas(W, H)
    rows_a, rows_b = D["a"]["rows"], D["b"]["rows"]
    i15 = [r["doc"] for r in rows_a].index(D["checklist_lines_changed"][0])
    if rails:   # variant: a hairline per unchanged need, joining its two positions
        for i, (ra, rb) in enumerate(zip(rows_a, rows_b)):
            if i != i15:
                x = X0 + S.PITCH * i
                ax.plot([x, x], [YA - 0.24, YB + S.MARK / 2 + 0.05], color=S.SAND, lw=0.3, zorder=1)
    for side, y, rows in (("a", YA, rows_a), ("b", YB, rows_b)):
        top = y + 0.5
        yc = page(ax, D[side], 0.1, top)
        sentence(ax, D["sentence_" + side], 1.0, yc + 0.055)
        strip(ax, rows, y)
    # the one changed need: one frame across both claims
    x = X0 + S.PITCH * i15
    ax.add_patch(FancyBboxPatch((x - S.PITCH / 2 + 0.003, YB - 0.12), S.PITCH - 0.006, YA - YB + 0.17,
                                boxstyle="round,pad=0,rounding_size=0.025", fc="none", ec=S.INK, lw=S.LW, zorder=4))
    S.legend(ax, X0, 0.2, [("requested", "requested"), ("held", "held"), (("dot", S.AMBER), "question"),
                           ("left", "not needed")], gap=S.UNIT)
    if stem:
        S.save(fig, HERE, stem)
    else:
        S.save_png(fig, HERE, "f1_rails")


def draw_b(stem):
    """Rejected construction: one page, one fused strip; each need is a pair of marks (A over B)."""
    fig, ax = S.canvas(W, H)
    y = 1.45
    for i, (ra, rb) in enumerate(zip(D["a"]["rows"], D["b"]["rows"])):
        x = X0 + S.PITCH * i
        S.checklist_mark(ax, x, y + 0.032, STATE[ra["state"]])
        S.checklist_mark(ax, x, y - 0.032, STATE[rb["state"]])
        if ra["state"] != rb["state"]:
            ax.add_patch(FancyBboxPatch((x - S.PITCH / 2, y - 0.075), S.PITCH, 0.15,
                                        boxstyle="round,pad=0,rounding_size=0.02", fc="none", ec=S.INK, lw=S.LW))
    page(ax, D["a"], 0.1, y + 0.55)
    sentence(ax, D["sentence_a"], 1.0, y + 0.55)
    sentence(ax, D["sentence_b"], 1.0, y - 0.1)
    S.legend(ax, X0, 0.2, [("requested", "requested"), ("held", "held"), ("left", "not needed")], gap=S.UNIT)
    S.save(fig, HERE, stem)


if __name__ == "__main__":
    draw_a("f1", rails=False)
    draw_a(None, rails=True)
    draw_b("f1_b")
