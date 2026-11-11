"""Figure added after review: fig_families (Study 3, tenancy; data fresh2, run label confirm). No model calls.

    python3 fig_review.py [--png DIR]

fig_families: the 24 family differences behind H2 and H3 (strict unsafe errors per claim, CasePath minus comparator,
family mean over claims and runs), one row per family ordered by the difference against the frontier model. Two
markers per row: filled = against Rules in context on the same model, hollow = against Rules in context on the frontier
model (the theme's fill grammar: hollow = frontier model). Rows of families that contain denied-event or open-event
claims sit on the pale accent band and name their composition. Values come from analysis/study3_review.json (R6) and
are checked against the clusters of analysis/study3.py. Themed by figtheme.py, like fig_s6.py; direct labels, no legend
box. Not pre-registered: an analysis added after review.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import figtheme as th

HERE = Path(__file__).resolve().parent
FIG = HERE.parent / "paper" / "figures"
PREVIEW = None
DISPUTE = {"defect_mold_heating": "defect", "lease_termination_dispute": "termination", "rent_increase_dispute": "rent increase"}


def rows():
    res = json.loads((HERE / "study3_review.json").read_text())
    fam = res["R6"]["families"]
    if len(fam) != 24:
        raise ValueError(f"expected 24 families, found {len(fam)}")
    import study3 as s3
    spec = json.loads(s3.SPEC.read_text())
    s3.configure(spec)
    study = s3.Study(spec, "fresh2", "confirm", s3.load_data("fresh2"))
    a = study.clusters("casepath", "tenancy", "strict_unsafe")
    for b, k in (("ric", "diff_ric"), ("ric_frontier", "diff_ric_frontier")):
        fb = study.clusters(b, "tenancy", "strict_unsafe")
        for r in fam:
            assert abs(r[k] - (a[r["family_id"]] - fb[r["family_id"]])) < 1e-12, (b, r["family_id"])
    return sorted(fam, key=lambda r: (r["diff_ric_frontier"], r["diff_ric"], r["family_id"]))


def label(r):
    comp = []
    if r["denied_event"]:
        comp.append(f"{r['denied_event']} denied")
    if r["open_event"]:
        comp.append(f"{r['open_event']} open")
    if r["ordinary"] and comp:
        comp.insert(0, f"{r['ordinary']} ordinary")
    return DISPUTE[r["family"]] + (f" ({', '.join(comp)})" if comp else "")


def fig_families():
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    th.setup()
    R = rows()
    n = len(R)
    row = 0.17
    top, bottom = 0.40, 0.42
    H = top + n * row + bottom
    lab_w, right = 1.95, 0.15
    fig = plt.figure(figsize=(th.WIDTH, H))
    ax = fig.add_axes([lab_w / th.WIDTH, bottom / H, (th.WIDTH - lab_w - right) / th.WIDTH, (n * row) / H])
    lo = min(min(r["diff_ric"], r["diff_ric_frontier"]) for r in R)
    hi = max(max(r["diff_ric"], r["diff_ric_frontier"]) for r in R)
    x0, x1 = float(int(lo) - 1), float(int(hi) + 1)
    ax.set_xlim(x0, x1)
    ax.set_ylim(n - 0.5, -0.5)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", length=2.5, pad=2)
    ax.set_xticks(range(int(x0), int(x1) + 1))
    ax.set_xlabel("CasePath minus Rules in context: strict unsafe errors per claim (family mean)", labelpad=3)
    ax.set_yticks(range(n))
    ax.set_yticklabels([label(r) for r in R])
    for j, r in enumerate(R):
        if r["denied_event"] or r["open_event"]:
            ax.add_patch(Rectangle((x0, j - 0.5), x1 - x0, 1.0, fc=th.ACCENT, ec="none", zorder=0, clip_on=False))
    ax.axvline(0, color=th.NEUTRAL, lw=th.THIN, zorder=1)
    for j, r in enumerate(R):
        a, b = r["diff_ric"], r["diff_ric_frontier"]
        ax.plot([a, b], [j, j], color=th.NEUTRAL, lw=th.THIN, zorder=2)
        # equal (or nearly equal) values: the two markers are nudged apart vertically so that neither hides the other
        dy = 0.17 if abs(a - b) < 0.06 else 0.0
        ax.scatter([a], [j + dy], s=22, marker="o", facecolors=th.INK, edgecolors=th.INK, linewidths=th.THICK * 0.8, zorder=3)
        ax.scatter([b], [j - dy], s=22, marker="o", facecolors="white", edgecolors=th.INK, linewidths=th.THICK * 0.8, zorder=4)
    # direct labels on the first row (no legend box)
    a, b = R[0]["diff_ric"], R[0]["diff_ric_frontier"]
    # each label sits straight above its marker, on the side away from the other, so the leaders are vertical and
    # neither label crosses the other's leader
    left, right = (b, a) if b <= a else (a, b)
    for x, text, ha in ((left, "against the frontier model" if left == b else "against the same model", "right"),
                        (right, "against the same model" if right == a else "against the frontier model", "left")):
        ax.annotate(text, (x, 0), xytext=(x, -1.25), ha=ha, va="bottom", fontsize=th.NOTE, annotation_clip=False,
                    arrowprops=dict(arrowstyle="-", color=th.NEUTRAL, lw=th.THIN, shrinkA=0, shrinkB=4,
                                    relpos=(1.0, 0.0) if ha == "right" else (0.0, 0.0)))
    th.save(fig, FIG / "fig_families.pdf", PREVIEW)


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--png" in args:
        PREVIEW = args[args.index("--png") + 1]
        Path(PREVIEW).mkdir(parents=True, exist_ok=True)
    fig_families()
    print("written", FIG / "fig_families.pdf")
