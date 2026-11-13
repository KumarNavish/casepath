"""Figure 1, "One changed sentence": f1.svg/.pdf/.png (kept construction a) and f1_b.* (rejected b).

Input: f1_data.json (extract.py, from stored files; the core's checklists) and, for the amber underline, the words the
three stored readings quoted as open (../f2/f2_data.json). No model call. House style: ../common/style.py.
Each claim: a small page mark (one bar per sentence, the changed sentence in ink), its changed sentence, and its
checklist strip (the 27 needs of the workflow in workflow order, state as stored; dots = the stored questions, one per
open fact a held line waits for, under the hold whose rule names it). One frame marks the one need that changed; its
label abridges the stored document title, and the word under the dot abridges the stored fact question.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
import style as S  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle, Circle  # noqa: E402

D = json.loads((HERE / "f1_data.json").read_text())
OPEN_QUOTE = json.loads((HERE.parent / "f2" / "f2_data.json").read_text())["b"]["readings"][0]["quote"]
STATE = {"request": "requested", "hold": "held", "not_needed": "left"}
LINE_LABEL = "assignment of claims against third parties"   # abridged from the stored title of d15
Q_LABEL = "third party at fault?"                          # abridged from the stored question of g042

W, H = 5.5, 2.35
MARK, PITCH = 0.074, 0.09      # larger marks for the hero strips (gap kept at the house ratio)
X0 = 5.38 - PITCH * 26         # strip ends at the right margin
YA, YB = 1.78, 0.92
DOT, DOT_STEP = 0.024, 0.06
TEXT_X, TEXT_W = 0.42, X0 - 0.42 - 0.3


def page_mark(ax, side, x0, y_mid, w=0.2, chars=60, lh=0.0105):
    pad = 0.02
    unit = (w - 2 * pad) / chars
    segs, idx, y = [], 0, 0.0
    for para in side["paragraphs"]:
        col = 0
        for s in para:
            n = len(s) + 1
            while n > 0:
                take = min(n, chars - col)
                segs.append((col * unit, y, take * unit - unit, idx == D["changed_sentence_index"]))
                col += take
                n -= take
                if col >= chars:
                    col, y = 0, y - lh
            idx += 1
        y -= lh * (1.5 if col else 0.5)
    hgt = -y + 2 * pad
    top = y_mid + hgt / 2
    ax.add_patch(Rectangle((x0, top - hgt), w, hgt, fc=S.WHITE, ec=S.SAND, lw=0.5, zorder=1))
    for (x, yy, ww, ch) in segs:
        hh = 0.006 if ch else 0.003
        ax.add_patch(Rectangle((x0 + pad + x, top - pad + yy - hh / 2), max(ww, 0.002), hh,
                               fc=S.INK if ch else S.SAND, ec="none", zorder=2))


def sentence(ax, text, x, y_mid, width, mark=None, lh=0.155):
    """The sentence, wrapped to `width` inches, centred on y_mid; words inside `mark` get an amber underline."""
    r = ax.figure.canvas.get_renderer()
    sp = S.text_width(ax, ax.text(0, -5, "a a")) - S.text_width(ax, ax.text(0, -5, "aa"))
    placed, xx, line = [], x, 0
    for wd in text.split(" "):
        t = ax.text(xx, 0, wd, fontsize=S.SIZE_LABEL, va="baseline", ha="left", color=S.INK, zorder=3)
        ww = S.text_width(ax, t)
        if xx + ww > x + width and xx > x:
            xx, line = x, line + 1
        placed.append((t, xx, ww, line))
        xx += ww + sp
    n = line + 1
    top = y_mid + (n - 1) * lh / 2 - 0.03
    s0 = text.index(mark) if mark else -1
    pos = 0
    under = {}
    for (t, x0, ww, ln) in placed:
        y = top - ln * lh
        t.set_position((x0, y))
        a = text.index(t.get_text(), pos)
        pos = a + len(t.get_text())
        if mark and s0 <= a < s0 + len(mark):
            l0, l1 = under.get(ln, (x0, x0 + ww))
            under[ln] = (min(l0, x0), max(l1, x0 + ww))
    for ln, (l0, l1) in under.items():
        y = top - ln * lh - 0.035
        ax.plot([l0, l1], [y, y], color=S.AMBER, lw=1.2, solid_capstyle="butt", zorder=2)


def strip(ax, rows, y):
    for i, r in enumerate(rows):
        S.checklist_mark(ax, X0 + PITCH * i, y, STATE[r["state"]], s=MARK)
    seen = {}
    for i, r in enumerate(rows):
        for q in r["questions"]:
            seen.setdefault(q, []).append(i)
    stack = {}
    for q, cols in seen.items():
        k = stack.get(tuple(cols), 0)
        stack[tuple(cols)] = k + 1
        cx = X0 + PITCH * sum(cols) / len(cols)
        ax.add_patch(Circle((cx, y - MARK / 2 - 0.045 - DOT_STEP * k), DOT, fc=S.AMBER, ec="none", zorder=3))


def legend(ax, x, y):
    items = [("requested", "requested"), ("held", "held"), ("dot", "question"), ("left", "not needed")]
    for key, label in items:
        if key == "dot":
            ax.add_patch(Circle((x + DOT, y), DOT, fc=S.AMBER, ec="none"))
            dx = 2 * DOT
        else:
            S.checklist_mark(ax, x + MARK / 2, y, key, s=MARK)
            dx = MARK
        t = ax.text(x + dx + 0.05, y, label, va="center", ha="left", fontsize=S.SIZE_LABEL)
        x += dx + 0.05 + S.text_width(ax, t) + S.UNIT
    return x


def draw_a(stem):
    fig, ax = S.canvas(W, H)
    rows_a, rows_b = D["a"]["rows"], D["b"]["rows"]
    i15 = [r["doc"] for r in rows_a].index(D["checklist_lines_changed"][0])
    for side, y, rows in (("a", YA, rows_a), ("b", YB, rows_b)):
        page_mark(ax, D[side], 0.1, y)
        sentence(ax, D["sentence_" + side], TEXT_X, y, TEXT_W, mark=OPEN_QUOTE if side == "b" else None)
        strip(ax, rows, y)
    x = X0 + PITCH * i15
    ax.add_patch(FancyBboxPatch((x - PITCH / 2 + 0.004, YB - MARK / 2 - 0.085), PITCH - 0.008,
                                YA - YB + MARK + 0.13, boxstyle="round,pad=0,rounding_size=0.03",
                                fc="none", ec=S.INK, lw=S.LW, zorder=4))
    ax.text(x, YA + MARK / 2 + 0.07, LINE_LABEL, ha="center", va="bottom", fontsize=S.SIZE_LABEL, color=S.INK)
    ax.text(x, YB - MARK / 2 - 0.2, Q_LABEL, ha="center", va="top", fontsize=S.SIZE_LABEL, color=S.INK)
    legend(ax, X0 - MARK / 2, 0.16)
    S.save(fig, HERE, stem)


def draw_b(stem):
    """Rejected construction: one fused strip; each need is a pair of marks (A over B)."""
    fig, ax = S.canvas(W, H)
    y = 1.3
    for i, (ra, rb) in enumerate(zip(D["a"]["rows"], D["b"]["rows"])):
        x = X0 + PITCH * i
        S.checklist_mark(ax, x, y + 0.045, STATE[ra["state"]], s=MARK)
        S.checklist_mark(ax, x, y - 0.045, STATE[rb["state"]], s=MARK)
        if ra["state"] != rb["state"]:
            ax.add_patch(FancyBboxPatch((x - PITCH / 2, y - 0.1), PITCH, 0.2,
                                        boxstyle="round,pad=0,rounding_size=0.02", fc="none", ec=S.INK, lw=S.LW))
    sentence(ax, D["sentence_a"], TEXT_X, y + 0.45, TEXT_W)
    sentence(ax, D["sentence_b"], TEXT_X, y - 0.45, TEXT_W, mark=OPEN_QUOTE)
    legend(ax, X0 - MARK / 2, 0.2)
    S.save(fig, HERE, stem)


if __name__ == "__main__":
    draw_a("f1")
    draw_b("f1_b")
