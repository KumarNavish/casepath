"""Figure 4, revision 2: the fate of 100 requests. Reads f4_data.json only.

    python3 -I f4_plot.py     # f4.{png,svg,pdf} (kept: a, marks), f4_b.png (rejected: continuous bars)

Columns: the reference state of a document (an open fact decides; the file settles it; not needed), each scaled to
100 marks (5 x 20, filled column by column: the right fate first, then the errors, so each block reads as a bar).
Rows: CasePath core, the prompt that may hold, the plain prompt (Rules in context); per design two sub-rows, the
cost-efficient model (circle) above the frontier model (square). Colour = what the design did.
"Dropped" includes a claim handed to a person (CasePath core, cost-efficient: 0.9 of 100 settled; caption).
Counts per 100: largest remainder of the exact shares in f4_data.json.
"""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "common"))
import style as S  # noqa: E402
from matplotlib.patches import Circle, Rectangle  # noqa: E402

J = {d["key"]: d for d in json.loads((HERE / "f4_data.json").read_text())["designs"]}
ROWS = [("CasePath", "casepath_checklist", "casepath_frontier_checklist"),
        ("prompt that may hold", "hold_prompt", "hold_prompt_frontier"),
        ("plain prompt", "ric", "ric_frontier")]
COLS = ["open fact decides", "file settles", "not needed"]


def lr(v, total=100):
    keys = list(v)
    base = {k: int(v[k]) for k in keys}
    rest = total - sum(base.values())
    for k in sorted(keys, key=lambda k: -(v[k] - int(v[k])))[:rest]:
        base[k] += 1
    return base


def shares(d):
    """Per 100 in each reference column, in display order (right fate first)."""
    o = d["open"]["per100"]
    st = d["settled"]["per100"]
    nn = d["not_needed"]["counts"]
    n_nn = sum(nn.values())
    return [
        {"held": o.get("held", 0), "early": o.get("too_early", 0), "dropped": o.get("dropped", 0) + o.get("handed", 0)},
        {"requested": st.get("requested", 0), "held": st.get("held_needlessly", 0),
         "dropped": st.get("dropped", 0) + st.get("handed", 0)},
        {"left": 100 * nn.get("left_alone", 0) / n_nn, "held": 100 * nn.get("held_needlessly", 0) / n_nn,
         "early": 100 * nn.get("requested_needlessly", 0) / n_nn},
    ], n_nn


W, H = 5.5, 3.30
X0, GAP = 1.30, 0.12
GW = 20 * S.PITCH
XS = [X0 + i * (GW + GAP) for i in range(3)]
SUB = 5 * S.PITCH            # height of one sub-row of marks
TOP = H - 0.40               # top of the first row


def row_top(r, m):
    return TOP - r * (2 * SUB + S.PITCH + 0.24) - m * (SUB + S.PITCH)


def frame(ax):
    for x, t in zip(XS, COLS):
        ax.text(x, H - 0.20, t, fontsize=S.SIZE_LABEL, fontweight="semibold", va="center")
    for r, (name, kc, kf) in enumerate(ROWS):
        y_mid = row_top(r, 0) - SUB - S.PITCH / 2
        ax.text(X0 - 0.17, y_mid, name, ha="right", va="center", fontsize=S.SIZE_LABEL,
                fontweight="semibold" if r == 0 else "normal")
        for m in (0, 1):
            yc = row_top(r, m) - SUB / 2
            if m == 0:
                ax.add_patch(Circle((X0 - 0.075, yc), 0.022, fc=S.INK, ec="none"))
            else:
                ax.add_patch(Rectangle((X0 - 0.097, yc - 0.022), 0.044, 0.044, fc=S.INK, ec="none"))
    S.legend(ax, 0.10, 0.14, [("held", "held"), ("requested", "requested"), ("early", "too early or not needed"),
                              ("dropped", "dropped"), ("left", "left alone")])


def draw_a():
    fig, ax = S.canvas(W, H)
    frame(ax)
    for r, (name, kc, kf) in enumerate(ROWS):
        for m, key in enumerate((kc, kf)):
            cols, _ = shares(J[key])
            for c, sh in enumerate(cols):
                counts = lr(sh)
                seq = [k for k in sh for _ in range(counts[k])]
                for i, st in enumerate(seq):
                    col, row = divmod(i, 5)
                    S.checklist_mark(ax, XS[c] + col * S.PITCH + S.MARK / 2,
                                     row_top(r, m) - row * S.PITCH - S.MARK / 2, st)
    return fig


def draw_b():
    fig, ax = S.canvas(W, H)
    frame(ax)
    for r, (name, kc, kf) in enumerate(ROWS):
        for m, key in enumerate((kc, kf)):
            cols, _ = shares(J[key])
            for c, sh in enumerate(cols):
                x = XS[c]
                y = row_top(r, m) - SUB + 0.02
                for k, v in sh.items():
                    w = GW * v / 100
                    col = S.STATE[k]
                    ax.add_patch(Rectangle((x, y), w, SUB - 0.04, fc=col or "none", ec=S.SAND if col is None else "none",
                                           lw=S.LW))
                    x += w
    return fig


def numbers():
    out = {}
    for name, kc, kf in ROWS:
        for key in (kc, kf):
            cols, n_nn = shares(J[key])
            out[key] = {"open_per100": cols[0], "settled_per100": cols[1], "not_needed_per100": cols[2],
                        "not_needed_document_runs": n_nn,
                        "open_document_runs": J[key]["open"]["denominator_document_runs"],
                        "settled_document_runs": J[key]["settled"]["denominator_document_runs"], "runs": J[key]["runs"]}
    (HERE / "f4_plotted.json").write_text(json.dumps(out, indent=1) + "\n")
    return out


if __name__ == "__main__":
    S.save(draw_a(), HERE, "f4")
    S.save_png(draw_b(), HERE, "f4_b")
    for k, v in numbers().items():
        print(k, v["runs"], {c: round(x, 1) for c, x in v["not_needed_per100"].items()}, "of", v["not_needed_document_runs"])
