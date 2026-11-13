"""Figure 1, "One changed sentence": draws f1.svg/.pdf/.png (kept construction a) and f1_b.* (rejected b).

Input: f1_data.json (written by extract.py from stored files). No model call. Every mark is from that file:
page bars = the claim's sentences (length in characters), squares = the 27 document needs of the workflow in
workflow order with the state the stored checklist gives, circles = the stored questions attached to the hold
whose rule names them, dashed blue square = the stored suggestion a model added outside the rules.
"""
import json
import sys
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle, Circle  # noqa: E402

HERE = Path(__file__).resolve().parent
D = json.loads((HERE / "f1_data.json").read_text())

PAPER, INK, SAND = "#FBF8F1", "#1F2A44", "#C9BFA8"
TEAL, AMBER, BLUE = "#00846F", "#D9962B", "#3A7DD6"   # re-stepped by the validator (see CONTRACT.md)
FILL = {"request": TEAL, "hold": AMBER}

plt.rcParams.update({"font.family": "Inter", "font.size": 7, "svg.fonttype": "none", "pdf.fonttype": 42,
                     "text.color": INK})

W, H = 5.5, 2.95
MARK, PITCH, X0 = 0.064, 0.081, 2.98


def canvas():
    fig = plt.figure(figsize=(W, H), facecolor=PAPER)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")
    ax.set_facecolor(PAPER)
    return fig, ax


def page(ax, side, x0, y_top, w=0.80, chars=78, lh=0.027, highlight=INK):
    """Measured page miniature: one bar per sentence, wrapped at `chars` characters per line."""
    pad = 0.05
    unit = (w - 2 * pad) / chars
    y = y_top - pad - lh / 2
    idx = 0
    segs = []
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
                    col = 0
                    y -= lh
            idx += 1
        y -= lh * (1.6 if col else 0.6)
    bottom = y + lh * 0.6 - pad
    ax.add_patch(Rectangle((x0, bottom), w, y_top - bottom, fc="white", ec=SAND, lw=0.6, zorder=1))
    for (x, yy, ww, ch) in segs:
        ax.add_patch(Rectangle((x, yy - (0.008 if ch else 0.005)), max(ww, 0.004), 0.016 if ch else 0.010,
                               fc=highlight if ch else SAND, ec="none", zorder=2))
    ys = [s[1] for s in segs if s[3]]
    xs = [s[0] + s[2] for s in segs if s[3]]
    return (max(xs), sum(ys) / len(ys)), bottom


def sentence(ax, text, x, y, width_chars=33):
    lines = textwrap.wrap(text, width_chars)
    ax.text(x, y, "\n".join(lines), va="center", ha="left", fontsize=7.5, linespacing=1.35, color=INK, zorder=3)


def square(ax, cx, cy, state, s=MARK):
    if state == "not_needed":
        ax.add_patch(FancyBboxPatch((cx - s / 2, cy - s / 2), s, s, boxstyle="round,pad=0,rounding_size=0.012",
                                    fc="none", ec=SAND, lw=0.8, zorder=3))
    else:
        ax.add_patch(FancyBboxPatch((cx - s / 2, cy - s / 2), s, s, boxstyle="round,pad=0,rounding_size=0.012",
                                    fc=FILL[state], ec="none", zorder=3))


def suggested(ax, cx, cy, s=MARK):
    ax.add_patch(FancyBboxPatch((cx - s / 2, cy - s / 2), s, s, boxstyle="round,pad=0,rounding_size=0.012",
                                fc="none", ec=BLUE, lw=0.9, ls=(0, (2, 1.2)), zorder=3))


def questions(ax, rows, y):
    """One amber circle per stored question, under the hold(s) whose rule names it; shared facts drawn once."""
    seen = {}
    for i, r in enumerate(rows):
        for q in r["questions"]:
            seen.setdefault(q, []).append(i)
    stack = {}
    for q, cols in seen.items():
        cx = X0 + PITCH * (sum(cols) / len(cols))
        k = stack.get(tuple(cols), 0)
        stack[tuple(cols)] = k + 1
        cy = y - 0.085 - 0.058 * k
        if len(cols) > 1:
            ax.plot([X0 + PITCH * cols[0], X0 + PITCH * cols[-1]], [cy + 0.04, cy + 0.04], color=AMBER, lw=0.7,
                    solid_capstyle="round", zorder=2)
            for c in cols:
                ax.plot([X0 + PITCH * c] * 2, [cy + 0.04, y - MARK / 2 - 0.004], color=AMBER, lw=0.7, zorder=2)
        ax.add_patch(Circle((cx, cy), 0.021, fc=AMBER, ec="none", zorder=3))
    return seen


def legend(ax, y):
    items = [("sq", "request", "requested now"), ("sq", "hold", "held"), ("q", None, "question"),
             ("sq", "not_needed", "not needed"), ("sug", None, "suggested by a model, outside the rules")]
    x = 0.08
    for kind, st, label in items:
        if kind == "sq":
            square(ax, x, y, st, s=0.06)
        elif kind == "q":
            ax.add_patch(Circle((x, y), 0.021, fc=AMBER, ec="none"))
        else:
            suggested(ax, x, y, s=0.06)
        t = ax.text(x + 0.06, y, label, va="center", ha="left", fontsize=7, color=INK)
        bb = t.get_window_extent(renderer=ax.figure.canvas.get_renderer())
        x += 0.06 + bb.width / ax.figure.dpi + 0.16


def draw_a(stem):
    fig, ax = canvas()
    ya, yb = 2.36, 1.04
    rows_a, rows_b = D["a"]["rows"], D["b"]["rows"]
    n = len(rows_a)
    xs = [X0 + PITCH * i for i in range(n)]
    xsug = X0 + PITCH * (n - 1) + 0.24
    # rails: same need, same position, in both claims
    for i, x in enumerate(xs):
        same = rows_a[i]["state"] == rows_b[i]["state"]
        ax.plot([x, x], [ya - 0.30, yb + MARK / 2 + 0.03], color=SAND if same else INK,
                lw=0.35 if same else 0.9, zorder=1)
    ax.plot([xsug, xsug], [ya - 0.30, yb + MARK / 2 + 0.03], color=BLUE, lw=0.5, ls=(0, (2, 2)), zorder=1)
    ax.text(xsug + 0.035, (ya + yb) / 2 - 0.1, "≠", ha="left", va="center", fontsize=8, color=BLUE)
    for side, y, rows in (("a", ya, rows_a), ("b", yb, rows_b)):
        for x, r in zip(xs, rows):
            square(ax, x, y, r["state"])
        questions(ax, rows, y)
        for _ in D[side]["suggested_by_model"]:
            suggested(ax, xsug, y)
        # page miniature and the sentence itself
        (sx, sy), _ = page(ax, D[side], 0.05, y + 0.5)
        tx = 0.98
        sentence(ax, D["sentence_" + side], tx, y + 0.05)
        ax.plot([sx + 0.01, tx - 0.04], [sy, y + 0.05], color=INK, lw=0.5, zorder=2)
    # the changed line: frame its column in both claims
    i15 = [r["doc"] for r in rows_a].index(D["checklist_lines_changed"][0])
    ax.add_patch(FancyBboxPatch((xs[i15] - 0.042, yb - 0.17), 0.084, ya - yb + 0.25,
                                boxstyle="round,pad=0,rounding_size=0.03", fc="none", ec=INK, lw=0.7, zorder=4))
    legend(ax, 0.2)
    save(fig, stem)


def draw_b(stem):
    """Rejected construction: one fused checklist strip; each need is one square split between the two claims."""
    fig, ax = canvas()
    y = 1.5
    rows_a, rows_b = D["a"]["rows"], D["b"]["rows"]
    for i, (ra, rb) in enumerate(zip(rows_a, rows_b)):
        x = X0 + PITCH * i
        for st, dy in ((ra["state"], 0.035), (rb["state"], -0.035)):
            square(ax, x, y + dy, st, s=0.06)
        if ra["state"] != rb["state"]:
            ax.add_patch(Rectangle((x - 0.05, y - 0.08), 0.1, 0.16, fc="none", ec=INK, lw=0.7))
    (sx, sy), _ = page(ax, D["a"], 0.05, y + 0.55)
    sentence(ax, D["sentence_a"], 0.98, y + 0.45)
    sentence(ax, D["sentence_b"], 0.98, y - 0.4)
    legend(ax, 0.2)
    save(fig, stem)


def save(fig, stem):
    for ext in ("svg", "pdf", "png"):
        fig.savefig(HERE / f"{stem}.{ext}", dpi=300 if ext == "png" else None, facecolor=PAPER)
    plt.close(fig)


if __name__ == "__main__":
    draw_a("f1")
    draw_b("f1_b")
    if "--zoom" in sys.argv:
        from PIL import Image
        im = Image.open(HERE / "f1.png")
        w, h = im.size
        im.crop((int(w * 0.5), int(h * 0.05), w, int(h * 0.75))).resize((int(w * 0.5) * 2, int(h * 0.7) * 2)).save(
            HERE / "f1_zoom.png")
