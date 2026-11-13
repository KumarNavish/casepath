"""Figure 6 (house style, rebuild/figures/common/style.py). Reads f6_data.json (compute.py) and the two workflow copies.
Writes f6.svg/.pdf/.png. The rejected construction b is drawn by f6_draft2.py; rerun_drift.json is kept as data for
Figure 7 and is not drawn here.

    python3 f6.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
import style as S  # noqa: E402
from matplotlib.patches import Circle, Polygon, Rectangle, FancyBboxPatch  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

D = json.loads((HERE / "f6_data.json").read_text(encoding="utf-8"))
WB = json.loads((HERE / "simple_theft_away.before.json").read_text(encoding="utf-8"))
WA = json.loads((HERE / "simple_theft_away.after.json").read_text(encoding="utf-8"))
U, P = S.UNIT, S.PITCH
ORDER = ["notification_record", "insurance_policy", "police_report", "police_consent", "stolen_items_list",
         "original_vouchers", "bicycle_voucher", "lock_change_invoice"]


# ------------------------------------------------------------------------------------------ workflow (before / after)
def workflow_strip(ax, x0, y, wf, w, mark_edit=False):
    """simple_theft_away as one row: steps on a line, branches as bumps that rejoin; documents as small squares under
    their step (solid = required, dashed = optional). Stop steps omitted (schematic)."""
    order = ["a_event", "a_cover", "a_notify", "a_police", "a_traces", "a_instruction_check", "a_instruction", "a_loss"]
    bump = {"a_traces", "a_instruction"}
    steps = {s["id"]: s for s in wf["steps"]}
    docs = {d["id"]: d for d in wf["documents"]}
    branch = {s["id"] for s in wf["steps"] if len(s.get("next", [])) > 1}
    main = [s for s in order if s not in bump]
    xs = {s: x0 + k * w / (len(main) - 1) for k, s in enumerate(main)}
    xs["a_traces"] = (xs["a_police"] + xs["a_instruction_check"]) / 2
    xs["a_instruction"] = (xs["a_instruction_check"] + xs["a_loss"]) / 2
    pos = {s: (xs[s], y + (U if s in bump else 0)) for s in order}
    for s in order:
        for e in steps[s].get("next", []):
            if e["to"] in pos:
                p, q = pos[s], pos[e["to"]]
                ax.add_line(Line2D([p[0], q[0]], [p[1], q[1]], color=S.INK, lw=S.LW, zorder=2))
    q = S.MARK
    for s in order:
        x, yy = pos[s]
        if s in branch:
            r = 0.04
            ax.add_patch(Polygon([(x, yy + r), (x + r, yy), (x, yy - r), (x - r, yy)], fc=S.WHITE, ec=S.INK, lw=S.LW, zorder=4))
        else:
            ax.add_patch(Circle((x, yy), 0.02, fc=S.WHITE, ec=S.INK, lw=S.LW, zorder=4))
        ds = steps[s].get("documents", [])
        for i, d in enumerate(ds):
            dx = (i - (len(ds) - 1) / 2) * P
            if s in bump:
                dx, dy = 0.6 * U, yy
            else:
                dy = yy - 0.75 * U
            if mark_edit and d == "police_report":
                # the edit itself: the document's mark before (dashed, optional) -> after (solid, required), ringed
                xa, xb = x + dx - 0.11, x + dx + 0.11
                ax.add_patch(Rectangle((xa - q / 2, dy - q / 2), q, q, fc=S.WHITE, ec=S.INK, lw=S.LW, ls=(0, (1.5, 1.0)), zorder=4))
                ax.annotate("", xy=(xb - q / 2 - 0.02, dy), xytext=(xa + q / 2 + 0.02, dy),
                            arrowprops=dict(arrowstyle="-|>,head_length=0.3,head_width=0.15", color=S.INK, lw=S.LW,
                                            shrinkA=0, shrinkB=0))
                ax.add_patch(Rectangle((xb - q / 2, dy - q / 2), q, q, fc=S.WHITE, ec=S.INK, lw=1.1, zorder=4))
                ax.add_patch(FancyBboxPatch((xa - q / 2 - 0.035, dy - q / 2 - 0.035), xb - xa + q + 0.07, q + 0.07,
                                            boxstyle="round,pad=0,rounding_size=0.06", fc="none", ec=S.INK, lw=1.0, zorder=5))
                ax.text((xa + xb) / 2, dy - 1.0 * U, '"optional": true → false', va="center", ha="center",
                        fontsize=S.SIZE_LABEL, family="DejaVu Sans Mono")
                continue
            ax.add_patch(Rectangle((x + dx - q / 2, dy - q / 2), q, q, fc=S.WHITE, ec=S.INK, lw=S.LW,
                                   ls=(0, (1.5, 1.0)) if docs[d].get("optional") else "-", zorder=4))
    return pos


# ------------------------------------------------------------------------------------------ matrix
def files_in_order():
    key = {("simple_theft_away", True): 0, ("simple_theft_away", False): 1, ("theft_at_home", True): 2, ("theft_at_home", False): 3}
    files = sorted(D["detail"], key=lambda f: (key[(f["type"], f["routed"] is not None)], f["file"]))
    first_home = next(i for i, f in enumerate(files) if f["type"] == "theft_at_home")
    return files, [(0, i) if i < first_home else (1, i - first_home) for i in range(len(files))]


def kind(l):
    cs = l["stored_before"] != l["stored_after"]
    cr = l["ref_before"] != l["ref_after"]
    if cs and cr and l["stored_after"] == l["ref_after"]:
        return "exact"
    if cs:
        return "should_not"
    if cr:
        return "missed"
    return "quiet"


def mark(ax, x, y, k):
    if k == "exact":
        S.checklist_mark(ax, x, y, "requested")
    elif k == "should_not":
        S.checklist_mark(ax, x, y, "early")
    elif k == "missed":
        S.checklist_mark(ax, x, y, "left", outline=S.AMBER)
    else:
        ax.add_patch(Circle((x, y), 0.008, fc=S.SAND, ec="none", zorder=3))


BLOCK = (len(ORDER) - 1) * P + 1.5 * U   # theft away has 7 catalogue lines, theft at home 8   # height of one type block plus the gap below it


def matrix(ax, x0, ytop):
    files, bc = files_in_order()
    for f, (b, c) in zip(files, bc):
        docs = {l["document"]: l for l in f["lines"]}
        for j, d in enumerate(ORDER):
            if d in docs:
                mark(ax, x0 + c * P, ytop - b * BLOCK - j * P, kind(docs[d]))
    return files, bc


def main():
    W, H = 5.5, 3.05
    fig, ax = S.canvas(W, H)
    M = D["measures"]
    # the rule edit, shared by both designs (top row before, bottom row after)
    workflow_strip(ax, 0.85, H - 1.6 * U, WA, 3.6, mark_edit=True)   # drawn once; the edit shown at its node
    # two designs, same geometry
    files, bc = files_in_order()
    width = 28 * P
    xl, xr = 0.55, 3.15
    yh = H - 5.0 * U
    yc = yh - 1.5 * U
    ym = yc - 2 * U
    ax.text(xl - S.MARK / 2, yh, "CasePath · 0 calls", va="center", fontweight="semibold", fontsize=S.SIZE_LABEL)
    ax.text(xr - S.MARK / 2, yh, f"single prompt · {M['files']} calls", va="center", fontweight="semibold",
            fontsize=S.SIZE_LABEL)
    for b in (0, 1):
        n = sum(1 for bb, _ in bc if bb == b)
        y = yc - b * P
        for bb, c in bc:
            if bb == b:
                ax.add_patch(Circle((xr + c * P, y), 0.022, fc=S.BLUE, ec="none"))
    ax.text(xl - S.MARK / 2, yc - P / 2, "one column per file, one mark per line", va="center", fontsize=S.SIZE_LABEL)
    matrix(ax, xl, ym)
    top = ym + S.MARK / 2 + 0.01
    bottom = ym - BLOCK - (len(ORDER) - 1) * P - S.MARK / 2 - 0.01
    ax.add_patch(FancyBboxPatch((xr - S.MARK / 2 - 0.01, bottom), width + S.MARK + 0.02, top - bottom,
                                boxstyle="round,pad=0,rounding_size=0.03", fc=S.WHITE, ec=S.SAND, lw=S.LW,
                                ls=(0, (3, 2.5))))
    ax.text(xr + width / 2, (top + bottom) / 2, "not yet measured", ha="center", va="center", fontsize=S.SIZE_LABEL)
    ax.text(xl - S.MARK / 2, bottom - 1.2 * U, f"{M['lines_changed']} of {M['lines_total']} lines changed", va="center",
            fontsize=S.SIZE_LABEL)
    # legend: three change marks and the model call
    y = 0.9 * U
    x = S.legend(ax, xl - S.MARK / 2, y, [("requested", "changed as required"), ("early", "changed, should not")],
                 gap=1.5 * U)
    S.checklist_mark(ax, x + S.MARK / 2, y, "left", outline=S.AMBER)
    t = ax.text(x + S.MARK + 0.05, y, "should change, did not", va="center", fontsize=S.SIZE_LABEL)
    x += S.MARK + 0.05 + S.text_width(ax, t) + 1.5 * U
    S.legend(ax, x, y, [(("dot", S.BLUE), "model call")])
    S.save(fig, HERE, "f6")


if __name__ == "__main__":
    main()
