"""Section 4 figures: fig_pipeline (drawn), fig_hero and fig_gestures (crops of real screens). No model calls.

    python3 fig_s4.py [--png DIR]

fig_pipeline is drawn from the product's own names at commit 6a72159c (`casepath/agents/team.py` PLAN and AGENTS,
`agents/core.py` route, `process/workflows.py`). Three kinds of box only: a model reading or agent (white, thin
outline), a code check that can reject a value (white, thick outline), and code that decides (the theme's one accent
tint, thick outline). Width: the full text block (acmsmall has one column, so single-column and full text width are the
same 5.4 in); the step names then print at the theme's label size without abbreviation.

fig_hero and fig_gestures place crops of unedited captures (`paper/figures/ui_used/s4/`, made by
`paper/figures/ui/s4/source/*.js` from the product served at 6a72159c on synthetic claims). Pixels are embedded
unresampled by matplotlib's `interpolation="none"`; each crop is one rectangle of one capture; nothing is retouched.
"""
from pathlib import Path
import sys

import numpy as np
from PIL import Image

import figtheme as th
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

HERE = Path(__file__).resolve().parent
FIG = HERE.parent / "paper" / "figures"
UI = FIG / "ui_used" / "s4"
PREVIEW = None


def _save(fig, name):
    th.save(fig, FIG / f"{name}.pdf", PREVIEW)


# ------------------------------------------------------------------------------------------------ pipeline
def box(ax, x, y, w, h, kind, title, note=None):
    """kind: 'model' (reading or agent), 'check' (code that can reject a value), 'decide' (code decides)."""
    fc = th.ACCENT if kind == "decide" else "white"
    lw = th.THIN if kind == "model" else th.THICK
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.035", fc=fc, ec=th.INK, lw=lw, zorder=2))
    if note:
        th.text(ax, x + 0.07, y + h - 0.105, title, "label", bold=kind != "check", zorder=3)
        th.text(ax, x + 0.07, y + h - 0.105 - 0.135, note, "note", va="top", linespacing=1.15, zorder=3)
    else:
        th.text(ax, x + w / 2, y + h / 2, title, "label", ha="center", bold=kind != "check", zorder=3, linespacing=1.15)


def arrow(ax, a, b, color=th.INK, ls="-"):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>,head_length=3.2,head_width=1.8", color=color, lw=th.THIN,
                                 shrinkA=0, shrinkB=0, linestyle=ls, zorder=1))


def fig_pipeline():
    W, H = th.WIDTH, 4.62
    fig, ax = th.canvas(H, W)
    # legend: the three kinds of box
    ly = H - 0.13
    x = 0.04
    for kind, lab in (("model", "model reading or agent"), ("check", "code check: can reject a value"),
                      ("decide", "code decides")):
        ax.add_patch(FancyBboxPatch((x, ly - 0.055), 0.20, 0.11, boxstyle="round,pad=0,rounding_size=0.02",
                                    fc=th.ACCENT if kind == "decide" else "white", ec=th.INK,
                                    lw=th.THIN if kind == "model" else th.THICK))
        th.text(ax, x + 0.27, ly, lab, "note")
        x += 0.27 + th.width(ax, lab, "note") + 0.30

    L, LW = 0.04, 1.42           # left column: the agents and readings, in the order a case passes through
    C1, CW = 1.72, 1.02          # first code column
    C2 = 2.98                    # second code column
    D, DW = 4.24, 1.12           # decisions
    hh = 0.40                    # box height

    # 1 routing
    y1 = H - 0.36 - hh
    box(ax, L, y1, LW, hh, "model", "Router", "reads the routing facts")
    box(ax, C1, y1, CW, hh, "check", "quotation found\nin the file")
    box(ax, D, y1, DW, hh, "decide", "workflow chosen\nby its condition")
    arrow(ax, (L + LW, y1 + hh / 2), (C1, y1 + hh / 2)); arrow(ax, (C1 + CW, y1 + hh / 2), (D, y1 + hh / 2))

    # 2 brief and process
    y2 = y1 - 0.18 - hh
    box(ax, L, y2, LW, hh, "model", "Claim reader", "brief: request, parties, timeline")
    box(ax, C1, y2, 2 * CW + 0.24, hh, "model", "Process builder",
        "adds needs, questions or steps: suggestions only")
    arrow(ax, (L + LW, y2 + hh / 2), (C1, y2 + hh / 2))
    arrow(ax, (L + 0.30, y1), (L + 0.30, y2 + hh))

    # 3 readings -> admission -> presumptions
    y3 = y2 - 0.20 - 0.62
    rh, rg = 0.17, 0.055
    for i in range(3):
        yy = y3 + 0.62 - (i + 1) * rh - i * rg
        box(ax, L, yy, LW, rh, "model", f"Reading {i + 1}")
        arrow(ax, (L + LW, yy + rh / 2), (C1, y3 + 0.31 + (1 - i) * 0.07))
    th.text(ax, L, y3 - 0.075, "true, false, open or not stated, with a quotation", "note", va="top")
    box(ax, C1, y3 + 0.11, CW, hh, "check", "quotation found\nin the file")
    box(ax, C2, y3 + 0.11, CW, hh, "check", "all readings\nagree")
    box(ax, D, y3 + 0.11, DW, hh, "decide", "presumptions\nfor unstated facts")
    arrow(ax, (C1 + CW, y3 + 0.31), (C2, y3 + 0.31)); arrow(ax, (C2 + CW, y3 + 0.31), (D, y3 + 0.31))
    th.text(ax, C1, y3 + 0.03, "otherwise the fact stays unresolved", "note", va="top")
    arrow(ax, (L + 0.30, y2), (L + 0.30, y3 + 0.62))

    # the line after which no agent can change a deciding fact
    yl = y3 - 0.29
    th.line(ax, [L, W - 0.04], [yl, yl], color=th.INK, ls=(0, (3, 2)))
    th.text(ax, C1, yl - 0.075, "below the line, no agent can record or change a deciding fact", "note", va="top")

    # 4 documents
    y4 = yl - 0.22 - hh
    box(ax, L, y4, LW, hh, "model", "Document finder", "matches each need to a file")
    box(ax, C1, y4, CW, hh, "model", "second\njudgment")
    box(ax, C2, y4, CW, hh, "check", "same file, each\nitem quoted")
    arrow(ax, (L + LW, y4 + hh / 2), (C1, y4 + hh / 2)); arrow(ax, (C1 + CW, y4 + hh / 2), (C2, y4 + hh / 2))
    th.text(ax, C2, y4 - 0.05, "otherwise unusable: stays requested", "note", va="top")
    arrow(ax, (L + 0.30, y3 - 0.17), (L + 0.30, y4 + hh))

    # 5 source checker
    y5 = y4 - 0.26 - hh
    box(ax, L, y5, LW, hh, "model", "Source checker", "judges each item from its quotes")
    th.text(ax, L + LW + 0.10, y5 + hh / 2, "doubt about an agreed deciding fact is only a flag", "note")
    arrow(ax, (L + 0.30, y4), (L + 0.30, y5 + hh))

    # 6 result checker and evaluation
    y6 = y5 - 0.20 - hh
    box(ax, L, y6, LW, hh, "model", "Result checker", "summary, reply draft, proposals")
    box(ax, D, y6, DW, hh, "decide", "evaluation with\nexact deferral")
    arrow(ax, (L + 0.30, y5), (L + 0.30, y6 + hh))
    arrow(ax, (D, y6 + hh / 2), (L + LW, y6 + hh / 2))
    th.text(ax, (L + LW + D) / 2, y6 + hh / 2 + 0.06, "reads the evaluated checklist", "note", ha="center", va="bottom")
    # facts and documents feed evaluation
    xf = D + DW / 2
    th.line(ax, [xf, xf], [y3 + 0.11, y6 + hh + 0.01])
    arrow(ax, (xf, y6 + hh + 0.06), (xf, y6 + hh))
    th.line(ax, [C2 + CW, xf], [y4 + hh / 2, y4 + hh / 2])
    th.text(ax, xf + 0.06, (y3 + 0.11 + yl) / 2, "admitted\nfacts", "note", va="center", linespacing=1.1)
    th.text(ax, xf + 0.06, y4 + hh / 2 - 0.13, "accepted\ndocuments", "note", va="center", linespacing=1.1)
    th.text(ax, D + DW, y6 - 0.07, "checklist: request · hold with a question · present", "note", ha="right", va="top")
    _save(fig, "fig_pipeline")


# ------------------------------------------------------------------------------------------------ screens
def crop(name, box=None):
    img = Image.open(UI / f"{name}.png").convert("RGB")
    return np.asarray(img.crop(box) if box else img)


def place(ax, img, x, top, s, frame=True):
    """One crop, left edge x, top edge `top`, s inches per capture pixel. Returns (x0, y0, x1, y1)."""
    w, h = img.shape[1] * s, img.shape[0] * s
    ax.imshow(img, extent=(x, x + w, top - h, top), interpolation="none", zorder=1, aspect="auto")
    if frame:
        ax.add_patch(th.Rectangle((x, top - h), w, h, fc="none", ec=th.NEUTRAL, lw=th.THIN, zorder=2))
    return x, top - h, x + w, top


LABEL_GREY = "#707070"   # the small panel labels of fig_hero


def fig_hero():
    """Two columns (the claim states / leaves open the health effect), two panels each: the claim paragraph in the
    claim reader's source view and the result checker's "Next steps". Captured at narrower viewports (claim reader
    1068 px, result checker 722 px wide, deviceScaleFactor 2) so that the interface wraps its own text to 400 CSS px;
    every crop is the same 798 x n px rectangle shape (1 px of card border dropped on the left), and both columns are
    printed at one scale so that the 15 px list text prints at about 7 pt."""
    cols = [("stated", "The claim states the health effect"), ("open", "The claim leaves the health effect open")]
    crops = {v: {"claim": crop(f"{v}-claim400")[12:, 2:800],          # drop the edge of the line above the paragraph
                 "steps": crop(f"{v}-steps400")[:, 2:800]} for v, _ in cols}
    W, gap, m = th.WIDTH, 0.12, 0.02
    cw = (W - 2 * m - gap) / 2
    s = cw / 798
    hc = max(crops[v]["claim"].shape[0] for v, _ in cols) * s
    hs = max(crops[v]["steps"].shape[0] for v, _ in cols) * s
    H = 0.20 + 0.17 + hc + 0.22 + hs + 0.03
    fig, ax = th.canvas(H, W)
    for j, (v, title) in enumerate(cols):
        x = m + j * (cw + gap)
        top = H - 0.04
        th.text(ax, x, top - 0.07, title, "label", bold=True)
        th.text(ax, x, top - 0.25, "claim reader \u00b7 source view", "note", color=LABEL_GREY)
        place(ax, crops[v]["claim"], x, top - 0.32, s)
        y2 = top - 0.32 - hc - 0.10
        th.text(ax, x, y2, "result checker \u00b7 where the case stands", "note", color=LABEL_GREY)
        place(ax, crops[v]["steps"], x, y2 - 0.07, s)
    print("fig_hero: list text 15 css px prints at %.2f pt, claim text 16 css px at %.2f pt" % (30 * s * 72, 32 * s * 72))
    _save(fig, "fig_hero")


GEST_S = 1 / 410


def fig_gestures():
    s = GEST_S
    W = th.WIDTH
    item, line = crop("g1-item"), crop("g1-line", (0, 0, 1600, 40))
    form = crop("g3-form", (0, 0, 1100, 1248))
    before, after = crop("g2-before", (1841, 200, 2822, 898)), crop("g2-after", (1841, 200, 2822, 690))
    H = 0.30 + (item.shape[0] + line.shape[0]) * s + 0.12 + 0.30 + form.shape[0] * s + 0.08
    fig, ax = th.canvas(H, W)
    x0, top = 0.04, H - 0.06
    th.text(ax, x0, top - 0.07, "(a) Mark an item correct or not correct (result checker)", "label", bold=True)
    A = place(ax, item, x0, top - 0.17, s, frame=False)
    B = place(ax, line, x0, A[1] - 0.05, s, frame=False)
    top = B[1] - 0.14
    th.text(ax, x0, top - 0.07, "(b) Change the process, with a reason (process builder)", "label", bold=True)
    F = place(ax, form, x0, top - 0.17, s)
    xr = F[2] + 0.22
    th.text(ax, xr, top - 0.07, "(c) Settle a point that needs judgement (overview)", "label", bold=True)
    th.text(ax, xr, top - 0.24, "before", "note")
    P = place(ax, before, xr, top - 0.31, s)
    th.text(ax, xr, P[1] - 0.10, "after “Done” on the open question", "note")
    place(ax, after, xr, P[1] - 0.17, s)
    _save(fig, "fig_gestures")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--png" in args:
        PREVIEW = args[args.index("--png") + 1]
        Path(PREVIEW).mkdir(parents=True, exist_ok=True)
    only = [a for a in args if a.startswith("fig_")]
    for f in only or ["fig_pipeline", "fig_hero", "fig_gestures"]:
        globals()[f]()
    print("written to", FIG)
