"""Figure 6 drawing. Reads f6_data.json (compute.py), rerun_drift.json (rerun_drift.py) and the two workflow copies.
Writes f6.svg, f6.pdf, f6.png (kept, construction a) and f6_b_rejected.svg/.png (construction b).

    python3 f6.py
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import Rectangle, Circle, Polygon, FancyBboxPatch  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

HERE = Path(__file__).resolve().parent
D = json.loads((HERE / "f6_data.json").read_text(encoding="utf-8"))
RD_UNUSED = json.loads((HERE / "rerun_drift.json").read_text(encoding="utf-8"))
WB = json.loads((HERE / "simple_theft_away.before.json").read_text(encoding="utf-8"))
WA = json.loads((HERE / "simple_theft_away.after.json").read_text(encoding="utf-8"))

for f in font_manager.findSystemFonts():
    if "Inter" in f and "Display" not in f:
        font_manager.fontManager.addfont(f)
plt.rcParams.update({"font.family": "Inter", "svg.fonttype": "none", "pdf.fonttype": 42})

PAPER, INK, SAND = "#FBF8F1", "#1F2A44", "#C9BFA8"
REQ, HOLD, EARLY, DROP, MODEL = "#008571", "#D9962B", "#B5482F", "#4B4A9C", "#4A8FD6"
STATE_COLOUR = {"request": REQ, "hold": HOLD}

# catalogue order shared by both theft types (first three identical, so police_report sits on one row)
ORDER = ["notification_record", "insurance_policy", "police_report", "police_consent", "stolen_items_list",
         "original_vouchers", "bicycle_voucher", "lock_change_invoice"]


def new_axes(W, H):
    fig = plt.figure(figsize=(W, H), facecolor=PAPER)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")
    return fig, ax


def t(ax, x, y, s, **kw):
    kw.setdefault("fontsize", 7)
    kw.setdefault("color", INK)
    kw.setdefault("va", "center")
    ax.text(x, y, s, **kw)


# ------------------------------------------------------------------------------------------------ workflow strip
def workflow_strip(ax, x0, y, wf, w, label, mark_edit=False):
    """The simple_theft_away graph as one row: steps on a line (branches as bumps that rejoin), documents as small
    squares under their step (solid = required, dashed = optional). Stop steps are short ticks downward."""
    order = ["a_event", "a_cover", "a_notify", "a_police", "a_traces", "a_instruction_check", "a_instruction", "a_loss"]
    bump = {"a_traces", "a_instruction"}
    steps = {s["id"]: s for s in wf["steps"]}
    docs = {d["id"]: d for d in wf["documents"]}
    branch = {s["id"] for s in wf["steps"] if len(s.get("next", [])) > 1}
    xs, k = {}, 0
    main = [s for s in order if s not in bump]
    dx = w / (len(main) - 1)
    for s in main:
        xs[s] = x0 + k * dx
        k += 1
    xs["a_traces"] = (xs["a_police"] + xs["a_instruction_check"]) / 2
    xs["a_instruction"] = (xs["a_instruction_check"] + xs["a_loss"]) / 2
    pos = {s: (xs[s], y + (0.13 if s in bump else 0)) for s in order}
    for s in order:
        for e in steps[s].get("next", []):
            if e["to"] in pos:
                p, q = pos[s], pos[e["to"]]
                ax.add_line(Line2D([p[0], q[0]], [p[1], q[1]], color=INK, lw=0.8, zorder=2))
    for s in order:
        x, yy = pos[s]
        if s in branch:
            r = 0.045
            ax.add_patch(Polygon([(x, yy + r), (x + r, yy), (x, yy - r), (x - r, yy)], fc=PAPER, ec=INK, lw=0.9, zorder=4))
        else:
            ax.add_patch(Circle((x, yy), 0.022, fc=PAPER, ec=INK, lw=0.9, zorder=4))
        for i, d in enumerate(steps[s].get("documents", [])):
            dy = yy - (0.105 if s not in bump else -0.075)
            n = len(steps[s].get("documents", []))
            dxd = (i - (n - 1) / 2) * 0.075
            opt = docs[d].get("optional")
            edited = d == "police_report"
            ax.add_patch(Rectangle((x + dxd - 0.028, dy - 0.028), 0.056, 0.056, fc=PAPER, ec=INK,
                                   lw=1.3 if edited else 0.8, ls=(0, (1.6, 1.1)) if opt else "-", zorder=4))
            if edited and mark_edit:
                ax.add_patch(Circle((x + dxd, dy), 0.058, fc="none", ec=INK, lw=1.0, zorder=5))
    t(ax, x0 - 0.12, y, label, ha="right", fontweight="semibold")


# ------------------------------------------------------------------------------------------------ file grid
def file_order():
    rows = D["detail"]
    key = {("simple_theft_away", True): 0, ("simple_theft_away", False): 1, ("theft_at_home", True): 2, ("theft_at_home", False): 3}
    return sorted(rows, key=lambda f: (key[(f["type"], f["routed"] is not None)], f["file"]))


def line_mark(l):
    cs = l["stored_before"] != l["stored_after"]
    cr = l["ref_before"] != l["ref_after"]
    if l["stored_before"] == "unrouted":
        return ("missed", l["ref_after"]) if cr else ("unrouted", None)
    if cs and cr and l["stored_after"] == l["ref_after"]:
        return ("exact", l["stored_after"])
    if cs and not cr:
        return ("collateral", l["stored_after"])
    if cs:
        return ("other", l["stored_after"])
    if cr:
        return ("missed", l["ref_after"])
    return ("same", None)


def draw_mark(ax, x, y, kind, state, s=0.052):
    if kind == "same":
        ax.add_patch(Circle((x, y), 0.009, fc=SAND, ec="none", zorder=3))
    elif kind == "unrouted":
        ax.add_patch(Circle((x, y), 0.013, fc="none", ec=SAND, lw=0.6, zorder=3))
    elif kind == "exact":
        ax.add_patch(Rectangle((x - s / 2, y - s / 2), s, s, fc=STATE_COLOUR[state], ec="none", zorder=4))
    elif kind in ("collateral", "other"):
        ax.add_patch(Rectangle((x - s / 2, y - s / 2), s, s, fc=STATE_COLOUR[state], ec="none", zorder=4))
        ax.add_patch(Circle((x, y), s * 0.95, fc="none", ec=EARLY, lw=1.1, zorder=5))
    elif kind == "missed":
        ax.add_patch(Rectangle((x - s / 2, y - s / 2), s, s, fc="none", ec=STATE_COLOUR[state], lw=1.1, zorder=4))


def file_grid(ax, x0, ytop, dx=0.1, dy=0.062, gap_rows=0.22):
    files = file_order()
    pos = {}
    first_home = next(i for i, f in enumerate(files) if f["type"] == "theft_at_home")
    for i, f in enumerate(files):
        r, c = (0, i) if i < first_home else (1, i - first_home)
        X = x0 + c * dx
        Y0 = ytop - r * (len(ORDER) * dy + gap_rows)
        docs = {l["document"]: l for l in f["lines"]}
        for j, d in enumerate(ORDER):
            if d in docs:
                kind, st = line_mark(docs[d])
                draw_mark(ax, X, Y0 - j * dy, kind, st)
        pos[f["file"]] = (X, Y0)
    return files, pos


def prompt_grid(ax, x0, ytop, n, per_row=14, dx=0.104, dy=0.104):
    for i in range(n):
        r, c = divmod(i, per_row)
        ax.add_patch(Circle((x0 + c * dx, ytop - r * dy), 0.028, fc=MODEL, ec="none", zorder=4))


def hatched(ax, x, y, w, h, text):
    ax.add_patch(Rectangle((x, y), w, h, fc="none", ec=SAND, lw=0.8, hatch="/////", zorder=1))
    plt.rcParams["hatch.color"] = SAND
    plt.rcParams["hatch.linewidth"] = 0.4
    ax.add_patch(FancyBboxPatch((x + w / 2 - 0.62, y + h / 2 - 0.1), 1.24, 0.2, boxstyle="round,pad=0,rounding_size=0.03",
                                fc=PAPER, ec="none", zorder=2))
    t(ax, x + w / 2, y + h / 2, text, ha="center", zorder=3)


# ------------------------------------------------------------------------------------------------ figure a
DX, DY, GAP = 0.08, 0.056, 0.2  # file column pitch, line pitch, gap between the two type blocks (inches)


def blocks():
    """File order and (block, column) per file: block 0 = simple theft away (routed, then not routed), 1 = at home."""
    files = file_order()
    first_home = next(i for i, f in enumerate(files) if f["type"] == "theft_at_home")
    return files, [(0, i) if i < first_home else (1, i - first_home) for i in range(len(files))]


def calls_rows(ax, x0, ytop, filled):
    """One call mark per file at the file's matrix column; an empty sand baseline where no call is made."""
    files, bc = blocks()
    for b in (0, 1):
        n = sum(1 for bb, _ in bc if bb == b)
        y = ytop - b * 0.1
        if filled:
            for (bb, c) in bc:
                if bb == b:
                    ax.add_patch(Circle((x0 + c * DX, y), 0.022, fc=MODEL, ec="none", zorder=4))
        else:
            ax.add_line(Line2D([x0 - 0.02, x0 + (n - 1) * DX + 0.02], [y, y], color=SAND, lw=0.6, ls=(0, (1, 2))))


def draw_a(stem):
    plt.rcParams["hatch.color"] = SAND
    plt.rcParams["hatch.linewidth"] = 0.4
    W, H = 5.5, 3.6
    fig, ax = new_axes(W, H)
    M = D["measures"]
    files, bc = blocks()
    xl, xr = 0.5, 3.05            # left edge of the CasePath matrix and of the prompt frame (same size)
    width = 28 * DX               # widest block has 29 files
    # shared rule edit across the top
    workflow_strip(ax, 1.0, H - 0.3, WB, 3.2, "before")
    workflow_strip(ax, 1.0, H - 0.72, WA, 3.2, "after", mark_edit=True)
    pol_x = 1.0 + 3.2 * 3 / 5
    t(ax, pol_x - 0.12, H - 0.95, '"optional": true → false', fontsize=7, family="DejaVu Sans Mono", ha="left")
    ax.add_line(Line2D([0.08, W - 0.08], [H - 1.07, H - 1.07], color=SAND, lw=0.6))
    # design headers, calls, matrices
    yh, yc, ym = H - 1.22, H - 1.42, H - 1.74
    t(ax, xl - 0.42, yh, "CasePath", ha="left", fontweight="semibold", fontsize=8)
    t(ax, xr, yh, "single prompt", ha="left", fontweight="semibold", fontsize=8)
    calls_rows(ax, xl, yc, filled=False)
    calls_rows(ax, xr, yc, filled=True)
    t(ax, xl + width + 0.02, yh, "0 calls", ha="right", fontsize=7)
    t(ax, xr + width + 0.02, yh, f"{M['files']} calls", ha="right", fontsize=7)
    ax.add_line(Line2D([2.93, 2.93], [0.62, H - 1.12], color=SAND, lw=0.6))
    for f, (b, c) in zip(files, bc):
        X = xl + c * DX
        Y0 = ym - b * (len(ORDER) * DY + GAP)
        docs = {l["document"]: l for l in f["lines"]}
        for j, d in enumerate(ORDER):
            if d in docs:
                kind, st = line_mark(docs[d])
                draw_mark(ax, X, Y0 - j * DY, kind, st, s=0.046)
    t(ax, xl - 0.07, ym - 2 * DY, "police\nreport", ha="right", fontsize=7, linespacing=1.0)
    groups = Counter((f["type"], f["routed"] is not None) for f in files)
    for b, (tp, name) in enumerate((("simple_theft_away", "theft away"), ("theft_at_home", "theft at home"))):
        ya = ym - b * (len(ORDER) * DY + GAP) - len(ORDER) * DY + 0.015
        n1, n2 = groups[(tp, True)], groups[(tp, False)]
        for lo, hi, lab, col, ha in ((0, n1 - 1, f"{name} · {n1} files", INK, "center"),
                                     (n1, n1 + n2 - 1, f"not routed · {n2}", SAND, "right")):
            x1, x2 = xl + lo * DX - 0.025, xl + hi * DX + 0.025
            ax.add_line(Line2D([x1, x2], [ya, ya], color=col, lw=0.6))
            t(ax, (x1 + x2) / 2 if ha == "center" else x2, ya - 0.065, lab, ha=ha, fontsize=7)
    # the prompt's matrix: same size and place, not yet measured
    top = ym + DY / 2 + 0.02
    bottom = ym - (len(ORDER) * DY + GAP) - (len(ORDER) - 1) * DY - DY / 2 - 0.02
    ax.add_patch(Rectangle((xr - 0.04, bottom), width + 0.08, top - bottom, fc="none", ec=SAND, lw=0.8, hatch="/////"))
    ax.add_patch(FancyBboxPatch((xr + width / 2 - 0.55, (top + bottom) / 2 - 0.09), 1.1, 0.18,
                                boxstyle="round,pad=0,rounding_size=0.03", fc=PAPER, ec="none", zorder=2))
    t(ax, xr + width / 2, (top + bottom) / 2, "not yet measured", ha="center", zorder=3)
    # count line and short legend
    t(ax, 0.08, 0.5, f"{M['lines_changed']} of {M['lines_total']} lines changed · 0 model calls", ha="left",
      fontweight="semibold")
    items = [("exact", "request", "changed as required"), ("collateral", "request", "changed, should not"),
             ("missed", "hold", "should change, did not"), ("same", None, "unchanged"), ("unrouted", None, "not routed")]
    XS = [0.2, 1.4, 2.6, 3.95, 4.7]
    for x, (kind, st, lab) in zip(XS, items):
        draw_mark(ax, x, 0.3, kind, st, s=0.046)
        t(ax, x + 0.09, 0.3, lab, ha="left")
    gy = 0.12
    r = 0.035
    ax.add_patch(Polygon([(0.2, gy + r), (0.2 + r, gy), (0.2, gy - r), (0.2 - r, gy)], fc=PAPER, ec=INK, lw=0.9))
    t(ax, 0.29, gy, "fact decides", ha="left")
    ax.add_patch(Circle((1.4, gy), 0.02, fc=PAPER, ec=INK, lw=0.9))
    t(ax, 1.49, gy, "step", ha="left")
    ax.add_patch(Rectangle((2.6 - 0.025, gy - 0.025), 0.05, 0.05, fc=PAPER, ec=INK, lw=0.8))
    t(ax, 2.69, gy, "required", ha="left")
    ax.add_patch(Rectangle((3.25 - 0.025, gy - 0.025), 0.05, 0.05, fc=PAPER, ec=INK, lw=0.8, ls=(0, (1.6, 1.1))))
    t(ax, 3.34, gy, "optional", ha="left")
    ax.add_patch(Circle((3.95, gy), 0.058, fc="none", ec=INK, lw=1.0))
    t(ax, 4.06, gy, "edited", ha="left")
    ax.add_patch(Circle((4.7, gy), 0.022, fc=MODEL, ec="none"))
    t(ax, 4.79, gy, "model call", ha="left")
    for ext in ("svg", "pdf", "png"):
        fig.savefig(HERE / f"{stem}.{ext}", dpi=300 if ext == "png" else None, facecolor=PAPER)
    plt.close(fig)


# ------------------------------------------------------------------------------------------------ figure b (rejected)
def draw_b(stem):
    """Rejected: every line's state before -> after as a transition table (counts), prompt as a matching empty table."""
    W, H = 5.5, 2.4
    fig, ax = new_axes(W, H)
    trans = Counter()
    for f in D["detail"]:
        for l in f["lines"]:
            trans[(l["stored_before"], l["stored_after"])] += 1
    states = ["request", "hold", "on_file", "optional", "not_needed", "unrouted"]
    x0, y0, cw, rh = 0.9, H - 0.45, 0.42, 0.24
    t(ax, 0.08, H - 0.12, "CasePath: line state before (rows) → after (columns), 56 files", ha="left", fontweight="semibold")
    for j, s in enumerate(states):
        t(ax, x0 + j * cw, y0 + 0.12, s.replace("_", " "), ha="center", fontsize=7)
        t(ax, x0 - 0.12, y0 - (j + 0.5) * rh, s.replace("_", " "), ha="right", fontsize=7)
    for i, a in enumerate(states):
        for j, b in enumerate(states):
            n = trans.get((a, b), 0)
            if n:
                col = REQ if (a != b and b == "request") else INK
                t(ax, x0 + j * cw, y0 - (i + 0.5) * rh, str(n), ha="center", fontsize=7.5, color=col,
                  fontweight="semibold" if a != b else "normal")
    xr = 3.75
    t(ax, xr, H - 0.12, "A prompt: 56 calls", ha="left", fontweight="semibold")
    hatched(ax, xr, 0.4, 1.6, 1.5, "not yet measured")
    for ext in ("svg", "png"):
        fig.savefig(HERE / f"{stem}.{ext}", dpi=300 if ext == "png" else None, facecolor=PAPER)
    plt.close(fig)


if __name__ == "__main__":
    draw_a("f6")
    draw_b("f6_b_rejected")
