#!/usr/bin/env python3
"""Regenerate the per-concept figure from the preserved held-out report.

    python3 evidence/build_figures.py

Writes fig_family_results.pdf. Every plotted value is read from
evidence/PAIRED_V5_REPRODUCED_RESULT.json; nothing is typed here.

The figure it replaces was inherited from an earlier release: it carried that line's vocabulary
in its title and encoded four arms as four bar shades, which are indistinguishable when the paper
is printed in grayscale. This version encodes the comparison by shape and position instead of
hue, so it survives grayscale, and it shows the claim the text makes: where the source semantics
fits, CasePath is exact and the comparators are not; where it fails, it fails completely while
the comparators do well.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

HERE = Path(__file__).resolve().parent
DOC = HERE.parent

CASEPATH = "b5_process_compiled"
COMPARATORS = [("b1_direct", "Direct"),
               ("b3_representation_then_list", "Graph as context"),
               ("b6_evidence_first", "Evidence-first")]
LABEL = {
    "PR_bicycle_claimed": "Bicycle among stolen items",
    "PR_declined": "Insurer declination",
    "PR_goods_recovered": "Recovery of stolen goods",
    "PR_nachfrist_set": "Written demand with period",
    "PR_scheduled_valuable_1000": "Scheduled valuable",
    "PR_sim_card_stolen": "SIM-card theft",
    "PR_repair_over_500": "Repair above consent threshold",
    "PR_expert_procedure_requested": "Formal expert procedure",
    "PR_third_party_causer": "Identifiable third-party causer",
}

INK = "#1a1a18"
ACCENT = "#1f3f7a"
MUTED = "#8c8c86"
LIGHT = "#d8d7d2"


def main() -> None:
    report = json.loads((HERE / "PAIRED_V5_REPRODUCED_RESULT.json").read_text())
    scores = report["scores"]
    cp = scores[CASEPATH]["family_pair_f1"]
    rows = []
    for concept, value in cp.items():
        others = [scores[key]["family_pair_f1"][concept] for key, _ in COMPARATORS]
        rows.append({"concept": concept, "label": LABEL[concept], "casepath": value,
                     "lo": min(others), "hi": max(others), "others": others})
    # Order by CasePath score, then by how far the comparators sit above it: the two failures
    # land at the bottom next to the comparators that solved them.
    rows.sort(key=lambda r: (r["casepath"], -max(r["others"])))

    fig, ax = plt.subplots(figsize=(6.4, 3.3))
    ys = range(len(rows))
    for y, r in zip(ys, rows):
        ax.plot([r["lo"], r["hi"]], [y, y], color=LIGHT, lw=5, solid_capstyle="round", zorder=1)
        for v in r["others"]:
            ax.plot([v], [y], marker="|", ms=9, mew=1.4, color=MUTED, zorder=2)
        ax.plot([r["casepath"]], [y], marker="o", ms=8.5, color=ACCENT,
                markeredgecolor="white", mew=1.2, zorder=3)

    ax.set_yticks(list(ys))
    ax.set_yticklabels([r["label"] for r in rows], fontsize=8.5, color=INK)
    ax.set_xlim(-0.04, 1.06)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticklabels(["0", "0.25", "0.50", "0.75", "1.0"], fontsize=8.5, color=INK)
    ax.set_xlabel("Mean pair $F_1$ within the branch concept, held-out contexts",
                  fontsize=8.5, color=INK)
    ax.tick_params(axis="both", length=0, pad=4)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(LIGHT)
    ax.grid(axis="x", color=LIGHT, lw=0.6, zorder=0)
    ax.set_axisbelow(True)
    ax.set_ylim(-0.6, len(rows) - 0.4)

    exact = sum(1 for r in rows if r["casepath"] == 1.0)
    zero = sum(1 for r in rows if r["casepath"] == 0.0)

    # The legend sits above the axes: every row of the plot carries data, and the caption already
    # states the counts, so nothing is annotated inside the frame.
    handles = [Line2D([], [], marker="o", ms=7, color=ACCENT, ls="none", markeredgecolor="white",
                      label="CasePath"),
               Line2D([], [], marker="|", ms=9, mew=1.4, color=MUTED, ls="none",
                      label="each comparator"),
               Line2D([], [], color=LIGHT, lw=5, solid_capstyle="round",
                      label="comparator range")]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.0, 1.01, 1.0, 0.1), mode="expand",
              ncol=3, frameon=False, fontsize=8.5, handletextpad=0.6, borderaxespad=0.0)

    fig.tight_layout(pad=0.4)
    out = DOC / "fig_family_results.pdf"
    fig.savefig(out, format="pdf", bbox_inches="tight", pad_inches=0.02,
                metadata={"CreationDate": None})
    plt.close(fig)
    print(f"wrote {out.name}: {len(rows)} concepts, CasePath exact on {exact}, zero on {zero}")
    for r in rows:
        print(f"  {r['label']:<32} CasePath {r['casepath']:.3f}   comparators "
              f"{r['lo']:.3f}-{r['hi']:.3f}")


if __name__ == "__main__":
    main()
