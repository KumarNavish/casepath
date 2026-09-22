#!/usr/bin/env python3
"""Rebuild the paper's figures from preserved evidence, in the SciencePlots house style.

    python3 evidence/build_figures.py

Five figures, each answering one question:

  fig_process_principle   why a checklist predictor cannot represent the dependency  (schematic)
  fig_native_case         what the chain looks like on one recorded case             (schematic)
  fig_family_results      where the branch semantics holds and where it fails        (Study A)
  fig_error_origin        why the unjustified changes differ in kind, not only count (Study A)
  fig_scope_control       what inherited scope actually buys                         (Study B)

Every plotted value is read from the evidence files; nothing is typed here. The two schematics
carry no measured values and say so in the audit. Output is byte-deterministic, so
`verify_release.py` can require the figures to regenerate unchanged.

Styling is SciencePlots `science` with `no-latex`, which gives the serif publication look without
needing a system LaTeX. Colour is used for one thing only: separating the proposed controller from
everything it is compared against. Marker shape carries the same distinction, so every figure
survives grayscale printing.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import scienceplots  # noqa: F401  (registers the styles)
from matplotlib.lines import Line2D

STYLE = ["science", "no-latex"]
plt.rcParams.update({"pdf.fonttype": 42, "ps.fonttype": 42, "svg.hashsalt": "casepath-paper"})

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
ACCENT = "#0b6e6a"
MUTED = "#6e6e68"
LIGHT = "#d9d8d3"
WARN = "#a8521f"


def save(fig, name: str) -> None:
    fig.savefig(DOC / name, metadata={"CreationDate": None}, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def bare(ax, keep_bottom: bool = True) -> None:
    ax.tick_params(length=0, pad=3, labelsize=8.5)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_visible(keep_bottom)
    if keep_bottom:
        ax.spines["bottom"].set_color(LIGHT)
    ax.grid(axis="x", color=LIGHT, lw=0.5)
    ax.set_axisbelow(True)


# --------------------------------------------------------------------------- schematics

def principle() -> None:
    """The chain, and what each of the three condition states does to it."""
    with plt.style.context(STYLE):
        fig, ax = plt.subplots(figsize=(6.7, 2.25))
        ax.set(xlim=(0, 1), ylim=(0, 1))
        ax.axis("off")
        ax.text(0, .97, "A source rule requires evidence of a scheduled valuable's value",
                fontsize=10, color=INK, va="top")
        xs = [.075, .275, .47, .665, .89]
        for x, head in zip(xs, ["Case condition", "Obligation", "Required fact",
                                "Evidence capability", "Document / action"]):
            ax.text(x, .77, head, ha="center", fontsize=8, color=MUTED)
        ax.plot([0, 1], [.71, .71], color=LIGHT, lw=.7)
        for x, val in zip(xs, ["True", "Establish\nvalue", "Value of\nthe item",
                               "Reliable\nvaluation", "Receipt or\nexpert valuation"]):
            ax.text(x, .56, val, ha="center", va="center", fontsize=9, color=ACCENT)
        for a, b in zip(xs, xs[1:]):
            ax.annotate("", xy=(b - (.10 if b == xs[-1] else .071), .56), xytext=(a + .071, .56),
                        arrowprops={"arrowstyle": "->", "color": ACCENT, "lw": .8})
        for y, state, obligation, action in [
                (.31, "False", "Inactive", "No request on this branch"),
                (.09, "Unresolved", "Not yet active", "Ask whether the item is scheduled")]:
            ax.text(xs[0], y, state, ha="center", va="center", fontsize=9, color=INK)
            ax.text(xs[1], y, obligation, ha="center", va="center", fontsize=9, color=INK)
            ax.annotate("", xy=(xs[1] - .071, y), xytext=(xs[0] + .071, y),
                        arrowprops={"arrowstyle": "->", "color": MUTED, "lw": .7})
            ax.plot([.39, .45], [y, y], color=MUTED, lw=.7)
            ax.text(.475, y, action, va="center", fontsize=9, color=INK)
        save(fig, "fig_process_principle.pdf")


def recorded_case() -> None:
    """One recorded prediction: missing is not the same as required."""
    ev = json.loads((HERE / "native150/RECORDED_CASE_STATES.json").read_text())
    assert ev["guards"]["arrears"]["value"] is True
    assert ev["guards"]["family_home"]["value"] is None
    assert ev["documents"]["payment_deadline_letter"]["presence"] == "missing"
    assert ev["documents"]["spouse_notice_copy"]["presence"] == "missing"
    assert "payment_deadline_letter" in ev["documents_now"]
    assert "spouse_notice_copy" in ev["documents_conditional"]
    with plt.style.context(STYLE):
        fig, ax = plt.subplots(figsize=(6.7, 3.0))
        ax.set(xlim=(0, 1), ylim=(0, 1))
        ax.axis("off")
        ax.text(0, .97, "Both documents are missing; only one is a request",
                fontsize=10, color=INK, va="top")
        cols = [.34, .76]
        for x, head in zip(cols, ["Arrears procedure", "Family-home protection"]):
            ax.text(x, .81, head, ha="center", fontsize=9.5, color=INK)
        rows = [(.66, "Case condition", "Arrears: true", "Family home: unresolved"),
                (.51, "Obligation", "Cure notice with warning", "Separate spouse notice"),
                (.36, "Evidence state", "Missing", "Missing"),
                (.20, "Plan", "Request now", "Hold, ask first")]
        for y, label, left, right in rows:
            ax.text(0, y, label, fontsize=8.5, color=MUTED, va="center")
            for x, value in zip(cols, [left, right]):
                colour = ACCENT if y == .20 and x == cols[0] else (WARN if y == .20 else INK)
                ax.text(x, y, value, fontsize=9, ha="center", va="center", color=colour)
        for x in cols:
            for a, b in ((.615, .555), (.465, .405), (.315, .245)):
                ax.annotate("", xy=(x, b), xytext=(x, a),
                            arrowprops={"arrowstyle": "->", "lw": .7, "color": MUTED})
        ax.plot([0, 1], [.10, .10], color=LIGHT, lw=.7)
        ax.text(0, .045, "An unresolved condition is answered before its documents are demanded.",
                fontsize=9, color=INK, va="center")
        save(fig, "fig_native_case.pdf")


# --------------------------------------------------------------------------- Study A

def family_results() -> None:
    """Where the branch semantics holds and where it fails, concept by concept."""
    report = json.loads((HERE / "PAIRED_V5_REPRODUCED_RESULT.json").read_text())
    scores = report["scores"]
    rows = []
    for concept, value in scores[CASEPATH]["family_pair_f1"].items():
        others = [scores[k]["family_pair_f1"][concept] for k, _ in COMPARATORS]
        rows.append({"label": LABEL[concept], "casepath": value, "others": others})
    rows.sort(key=lambda r: (r["casepath"], -max(r["others"])))
    with plt.style.context(STYLE):
        fig, ax = plt.subplots(figsize=(6.7, 3.1))
        for y, r in enumerate(rows):
            ax.plot([min(r["others"]), max(r["others"])], [y, y], color=LIGHT, lw=3,
                    solid_capstyle="round", zorder=1)
            for v, marker in zip(r["others"], ("s", "^", "x")):
                ax.plot([v], [y], marker=marker, ms=4.4, mew=1.0, markerfacecolor="white",
                        color=MUTED, ls="none", zorder=2)
            ax.plot([r["casepath"]], [y], marker="o", ms=7, color=ACCENT,
                    markeredgecolor="white", mew=1.0, zorder=3)
        ax.set_yticks(range(len(rows)), [r["label"] for r in rows], fontsize=8.5)
        ax.set(xlim=(-.04, 1.06), ylim=(-.6, len(rows) - .4))
        ax.set_xticks([0, .25, .5, .75, 1.0], ["0", "0.25", "0.50", "0.75", "1.0"], fontsize=8.5)
        ax.set_xlabel("Mean pair $F_1$ within the branch concept, held-out contexts", fontsize=9)
        bare(ax)
        handles = [Line2D([], [], marker="o", ms=6, color=ACCENT, ls="none", label="CasePath")]
        handles += [Line2D([], [], marker=m, ms=4.6, color=MUTED, ls="none", markerfacecolor="white",
                           label=lab) for (_, lab), m in zip(COMPARATORS, ("s", "^", "x"))]
        ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(-.42, 1.01, 1.42, .1),
                  mode="expand", ncol=4, frameon=False, fontsize=8.5, handletextpad=.35,
                  borderaxespad=0.0)
        save(fig, "fig_family_results.pdf")


def error_origin() -> None:
    """The unjustified changes differ in kind: the comparators' never touch a governed branch."""
    data = json.loads((HERE / "SPURIOUS_ORIGIN.json").read_text())
    order = [("b5_process_compiled", "CasePath"), ("b1_direct", "Direct"),
             ("b3_representation_then_list", "Graph as context"),
             ("b6_evidence_first", "Evidence-first")]
    with plt.style.context(STYLE):
        fig, ax = plt.subplots(figsize=(6.7, 2.4))
        for y, (key, label) in enumerate(reversed(order)):
            a = data["arms"][key]
            governed = a["required_in_one_unit"] + a["governed_elsewhere"]
            ungoverned = a["not_branch_governed"]
            is_cp = key == CASEPATH
            ax.barh(y, governed, height=.52, color=ACCENT if is_cp else MUTED, zorder=2)
            ax.barh(y, ungoverned, left=governed, height=.52, color=LIGHT, zorder=2)
            if governed:
                ax.text(governed / 2, y, str(governed), ha="center", va="center",
                        fontsize=8, color="white")
            ax.text(governed + ungoverned + 1.1, y, f"{ungoverned}", ha="left", va="center",
                    fontsize=8.5, color=INK)
        ax.set_yticks(range(len(order)), [lab for _, lab in reversed(order)], fontsize=9)
        ax.set(xlim=(0, 58), ylim=(-.6, len(order) - .4))
        ax.set_xlabel("Unjustified signed changes on the held-out pairs", fontsize=9)
        ax.set_xticks([0, 10, 20, 30, 40, 50])
        bare(ax)
        ax.legend(handles=[
            Line2D([], [], color=ACCENT, lw=6, label="on a branch the benchmark governs"),
            Line2D([], [], color=LIGHT, lw=6, label="on no branch at all")],
            loc="lower left", bbox_to_anchor=(-.20, 1.01, 1.20, .1), mode="expand", ncol=2,
            frameon=False, fontsize=8.5, handletextpad=.5, borderaxespad=0.0)
        save(fig, "fig_error_origin.pdf")


# --------------------------------------------------------------------------- Study B

def scope_control() -> None:
    """What inherited scope buys: the same evidence recovered, at less than half the demand."""
    report = json.loads((HERE / "native150/ASSESSED_STATE_REPORT.json").read_text())
    splits = [("public_dev", "Development"), ("hidden_test", "Protected families")]
    with plt.style.context(STYLE):
        fig, (left, right) = plt.subplots(1, 2, figsize=(6.7, 2.5),
                                          gridspec_kw={"width_ratios": [1.35, 1]})
        y = 0
        ticks, names = [], []
        for split, name in splits:
            arms = report["splits"][split]["arms"]
            for arm, arm_label in (("LOCAL_SCOPE_ABLATION", "Local only"),
                                   ("CASEPATH_CONTROL", "Full scope")):
                a = arms[arm]
                cells = a["raw_count_contributing_cells"]
                req = a["raw_native_counts"]["evidence/requested_documents"] / cells
                valid = a["raw_native_counts"]["evidence/valid_chain_documents"] / cells
                is_cp = arm == "CASEPATH_CONTROL"
                left.barh(y, valid, height=.55, color=ACCENT if is_cp else MUTED, zorder=2)
                left.barh(y, req - valid, left=valid, height=.55, color=LIGHT, zorder=2)
                left.text(valid / 2, y, f"{valid:.1f} valid", ha="center", va="center",
                          fontsize=8, color="white")
                waste = req - valid
                left.text(req + .3, y, "none wasted" if waste < .05 else f"+{waste:.1f} unjustified",
                          ha="left", va="center", fontsize=8.5,
                          color=ACCENT if waste < .05 else INK)
                ticks.append(y); names.append(arm_label)
                y += 1
            y += .7
        left.set_yticks(ticks, names, fontsize=8.5)
        left.set(xlim=(0, 21.5), ylim=(-.7, y - 1.0))
        left.set_xlabel("Document requests per case", fontsize=9)
        left.set_xticks([0, 5, 10, 15])
        bare(left)
        for idx, (_, name) in enumerate(splits):
            left.text(-7.4, ticks[2 * idx] + .5, name, fontsize=8.5, color=MUTED,
                      rotation=90, va="center", ha="center")
        left.legend(handles=[
            Line2D([], [], color=ACCENT, lw=6, label="valid, chain to an active obligation"),
            Line2D([], [], color=LIGHT, lw=6, label="unjustified")],
            loc="lower left", bbox_to_anchor=(-.30, 1.01, 1.30, .1), mode="expand", ncol=2,
            frameon=False, fontsize=8.2, handletextpad=.5, borderaxespad=0.0)

        metrics = [("critical_evidence_recall", "Critical-evidence\nrecall"),
                   ("valid_chain_precision", "Valid-chain\nprecision")]
        arms = report["splits"]["hidden_test"]["arms"]
        for row, (key, name) in enumerate(metrics):
            lo = arms["LOCAL_SCOPE_ABLATION"]["metrics"][key]["value"]
            hi = arms["CASEPATH_CONTROL"]["metrics"][key]["value"]
            right.plot([lo, hi], [row, row], color=LIGHT, lw=3, solid_capstyle="round", zorder=1)
            right.plot([lo], [row], marker="s", ms=5, color=MUTED, markerfacecolor="white",
                       mew=1.0, zorder=2)
            right.plot([hi], [row], marker="o", ms=6.5, color=ACCENT, markeredgecolor="white",
                       mew=1.0, zorder=3)
            right.text(lo, row - .30, f"{lo:.3f}", ha="center", va="top", fontsize=8, color=INK)
            right.text(hi, row + .26, f"{hi:.3f}", ha="center", va="bottom", fontsize=8,
                       color=ACCENT)
        right.set_yticks(range(len(metrics)), [n for _, n in metrics], fontsize=8.5)
        right.set(xlim=(0, 1.05), ylim=(-.75, len(metrics) - .35))
        right.set_xlabel("Protected families", fontsize=9)
        right.set_xticks([0, .5, 1.0], ["0", "0.5", "1.0"], fontsize=8.5)
        bare(right)
        save(fig, "fig_scope_control.pdf")


# --------------------------------------------------------------------------- audit

def audit() -> None:
    sources = {
        "fig_family_results.pdf": ("PAIRED_V5_REPRODUCED_RESULT.json", "/scores/*/family_pair_f1",
                                   "held-out Study A measurement"),
        "fig_error_origin.pdf": ("SPURIOUS_ORIGIN.json", "/arms/*",
                                 "descriptive partition of the held-out Study A spurious changes"),
        "fig_scope_control.pdf": ("native150/ASSESSED_STATE_REPORT.json",
                                  "/splits/*/arms/{CASEPATH_CONTROL,LOCAL_SCOPE_ABLATION}/"
                                  "{metrics,raw_native_counts,raw_count_contributing_cells}",
                                  "separate retrospective current-case scope intervention; "
                                  "counts are divided by each arm's contributing cells, which "
                                  "differ by two on the protected split"),
        "fig_native_case.pdf": ("native150/RECORDED_CASE_STATES.json", "/",
                                "recorded development prediction; not a native acceptance claim"),
        "fig_process_principle.pdf": (None, None, "authored teaching schematic; no measured values"),
    }
    rows = []
    for name, (source, pointer, meaning) in sources.items():
        rows.append({"figure": name,
                     "sha256": hashlib.sha256((DOC / name).read_bytes()).hexdigest(),
                     "evidence_file": source,
                     "evidence_sha256": hashlib.sha256((HERE / source).read_bytes()).hexdigest()
                     if source else None,
                     "json_pointer_pattern": pointer, "scope": meaning})
    (HERE / "FIGURE_AUDIT.json").write_text(
        json.dumps({"style": "SciencePlots science+no-latex", "figures": rows}, indent=2) + "\n")


if __name__ == "__main__":
    principle()
    recorded_case()
    family_results()
    error_origin()
    scope_control()
    audit()
    print("wrote 5 figures in the SciencePlots house style, and FIGURE_AUDIT.json")
