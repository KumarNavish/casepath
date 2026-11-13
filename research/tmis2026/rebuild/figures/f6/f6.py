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
RD = json.loads((HERE / "rerun_drift.json").read_text(encoding="utf-8"))
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
def workflow_strip(ax, x0, y, wf, w, label):
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
            if edited:
                ax.text(x + 0.06, dy, "police report", fontsize=7, color=INK, va="center", ha="left",
                        fontweight="semibold")
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
def draw_a(stem):
    plt.rcParams["hatch.color"] = SAND
    plt.rcParams["hatch.linewidth"] = 0.4
    W, H = 5.5, 4.0
    fig, ax = new_axes(W, H)
    M = D["measures"]
    # columns
    xl, xr = 0.55, 3.72
    t(ax, 0.08, H - 0.12, "CasePath", fontweight="semibold", fontsize=8, ha="left")
    t(ax, xr - 0.08, H - 0.12, "A prompt", fontweight="semibold", fontsize=8, ha="left")
    ax.add_line(Line2D([xr - 0.2, xr - 0.2], [0.12, H - 0.05], color=SAND, lw=0.6))
    # workflow before / after
    workflow_strip(ax, xl, H - 0.42, WB, 2.55, "before")
    workflow_strip(ax, xl, H - 0.86, WA, 2.55, "after")
    t(ax, xl + 2.55 * 3 / 5 - 0.03, H - 1.08, '"optional": true → false', fontsize=7, family="DejaVu Sans Mono",
      ha="left", color=INK)
    # file grid
    ytop = H - 1.36
    files, pos = file_grid(ax, xl - 0.02, ytop)
    # row label for the edited line and group brackets
    t(ax, xl - 0.1, ytop - 2 * 0.062, "police\nreport", ha="right", fontsize=7, linespacing=1.0)
    groups = Counter((f["type"], f["routed"] is not None) for f in files)
    for r, (tp, name) in enumerate((("simple_theft_away", "theft away (edited workflow)"), ("theft_at_home", "theft at home"))):
        a, b = 0, groups[(tp, True)] - 1
        ya = ytop - r * (len(ORDER) * 0.062 + 0.22) - len(ORDER) * 0.062 + 0.01
        for lo, hi, lab, col in ((a, b, f"{name}: {groups[(tp, True)]} files", INK),
                                 (b + 1, b + groups[(tp, False)], f"not routed: {groups[(tp, False)]}", SAND)):
            x1 = xl - 0.02 + lo * 0.1 - 0.03
            x2 = xl - 0.02 + hi * 0.1 + 0.03
            ax.add_line(Line2D([x1, x2], [ya, ya], color=col, lw=0.7))
            t(ax, (x1 + x2) / 2 if col == INK else x2, ya - 0.075, lab, ha="center" if col == INK else "right", fontsize=7)
    # measured legend with counts
    ly = 0.78
    unrouted = sum(len(f["lines"]) for f in files if f["routed"] is None)
    n_unrouted = sum(1 for f in files if f["routed"] is None)
    other_doc = sum(1 for f in files for l in f["lines"]
                    if l["stored_before"] != l["stored_after"] and l["document"] != "police_report")
    rows = [("exact", "request", f"{M['changed_and_should_same_new_state']} lines changed as the edited rule requires"),
            ("collateral", "request", f"{M.get('collateral_changed_should_not', 0)} changed, should not: report on file, stored finding rejected"),
            ("missed", "hold", f"{M.get('missed_should_change_did_not', 0)} should have become a hold, did not: file not routed"),
            ("same", None, f"{M['lines_total'] - unrouted - M['lines_changed']} unchanged; {other_doc} changed on any other document"),
            ("unrouted", None, f"{unrouted - M.get('missed_should_change_did_not', 0)} more in {n_unrouted} files not routed (no checklist)")]
    for k, (kind, st, lab) in enumerate(rows):
        yy = ly - k * 0.135
        draw_mark(ax, 0.2, yy, kind, st)
        t(ax, 0.32, yy, lab, ha="left")
    t(ax, 0.08, ly + 0.19, f"{M['files_checklist_changed']} of {M['files']} files, {M['lines_changed']} of {M['lines_total']} lines changed;"
      f"  0 model calls", ha="left", fontweight="semibold")
    # right: the prompt
    prompt_grid(ax, xr, H - 0.45, M["files"])
    t(ax, xr, H - 0.45 - 4 * 0.104 - 0.02, f"{M['files']} calls, one per file", ha="left")
    hatched(ax, xr - 0.05, H - 1.55, 1.72, 0.48, "lines changed by the edit:\nnot yet measured")
    # measured: same file read again, no edit (Study 3 files, theft)
    p = RD["designs"]["hold_prompt"]["theft"]
    c = RD["designs"]["casepath"]["theft"]
    bars = [(p["lines_different"] / p["lines_compared"], MODEL, "fill", "prompt, read again"),
            (c["lines_different"] / c["lines_compared"], MODEL, "hollow", "CasePath, read again"),
            (M.get("collateral_changed_should_not", 0) / M["lines_total"], INK, "fill", "CasePath, rule edit")]
    by, bx, scale = 1.8, xr + 0.02, 1.3 / 0.07  # 7 % of lines = 1.3 in
    t(ax, xr - 0.05, by + 0.3, "share of lines changed\nthat no rule asked for", ha="left", fontweight="semibold",
      linespacing=1.1)
    for k, (v, col, style, lab) in enumerate(bars):
        yy = by - k * 0.34
        t(ax, bx, yy + 0.1, lab, ha="left", fontsize=7)
        ax.add_patch(Rectangle((bx, yy - 0.045), max(v * scale, 0.012), 0.09, fc=col if style == "fill" else PAPER, ec=col, lw=0.9))
        t(ax, bx + v * scale + 0.05, yy, f"{100 * v:.1f} %", ha="left")
    ax.add_line(Line2D([bx, bx], [by - 2 * 0.34 - 0.1, by + 0.08], color=INK, lw=0.6))
    t(ax, xr - 0.05, by - 1.03, "read again: same file, same rules,\nno edit (Study 3 theft files,\n384 pairs of runs per design)",
      ha="left", fontsize=7, linespacing=1.1)
    # graph symbols
    gy = 0.3
    gx = xr - 0.05
    r = 0.04
    ax.add_patch(Polygon([(gx + 0.04, gy + r), (gx + 0.04 + r, gy), (gx + 0.04, gy - r), (gx + 0.04 - r, gy)], fc=PAPER, ec=INK, lw=0.9))
    t(ax, gx + 0.13, gy, "fact decides", ha="left")
    ax.add_patch(Circle((gx + 0.04, gy - 0.15), 0.022, fc=PAPER, ec=INK, lw=0.9))
    t(ax, gx + 0.13, gy - 0.15, "step", ha="left")
    ax.add_patch(Rectangle((gx + 0.82, gy - 0.028), 0.056, 0.056, fc=PAPER, ec=INK, lw=0.8))
    t(ax, gx + 0.93, gy, "required", ha="left")
    ax.add_patch(Rectangle((gx + 0.82, gy - 0.15 - 0.028), 0.056, 0.056, fc=PAPER, ec=INK, lw=0.8, ls=(0, (1.6, 1.1))))
    t(ax, gx + 0.93, gy - 0.15, "optional", ha="left")
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
