#!/usr/bin/env python3
"""Rebuild the paper's figures from preserved evidence.

    python3 evidence/build_figures.py

Five figures, each answering one question:

  fig_family_results      where the branch semantics holds and where it fails        (Study A)
  fig_error_origin        why the unjustified changes differ in kind, not only count (Study A)
  fig_scope_control       what inherited scope actually buys                         (Study B)
  fig_process_principle   why a checklist predictor cannot represent the dependency  (diagram)
  fig_native_case         what the chain looks like on one recorded case             (diagram)

Style, stated precisely. The three plots are drawn under SciencePlots `science` + `no-latex` and
keep what that style provides: the boxed frame, inward major and minor ticks on all four sides,
`axes.linewidth` 0.5, frameless legends, the serif face, and the `science` colour cycle, from which
every series colour here is taken. The only departures are the two a categorical axis requires:
minor ticks are disabled on the category axis, where they would mark nothing, and a light x grid is
added so long bars stay readable. Figure widths are set to the text width; heights follow the
style's 4:3.

The last two are diagrams, not plots. They have no axes, so the style reaches only their
typography. `FIGURE_AUDIT.json` records that distinction rather than implying they are plots.

Every plotted value is read from the evidence files; nothing is typed here. Output is
byte-deterministic, so `verify_release.py` can require the figures to regenerate unchanged.
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
WIDTH = 6.7  # the manuscript's text width

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
MARKERS = ("s", "^", "X")
GREY = "#9a9a94"       # the comparator range and the unjustified remainder
FAINT = "#dcdcd7"      # grid and bar remainder


def cycle() -> list[str]:
    """The science style's own colour cycle, so series colours come from the style."""
    with plt.style.context(STYLE):
        return plt.rcParams["axes.prop_cycle"].by_key()["color"]


def categorical(ax) -> None:
    """The one concession a category axis needs: no minor ticks where nothing is subdivided."""
    ax.tick_params(axis="y", which="minor", left=False, right=False)
    ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.grid(axis="x", color=FAINT, lw=0.5)
    ax.set_axisbelow(True)


def save(fig, name: str) -> None:
    fig.savefig(DOC / name, metadata={"CreationDate": None}, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


# --------------------------------------------------------------------------- plots

def family_results() -> None:
    """Where the branch semantics holds and where it fails, concept by concept."""
    report = json.loads((HERE / "PAIRED_V5_REPRODUCED_RESULT.json").read_text())
    scores = report["scores"]
    rows = []
    for concept, value in scores[CASEPATH]["family_pair_f1"].items():
        others = [scores[k]["family_pair_f1"][concept] for k, _ in COMPARATORS]
        rows.append({"label": LABEL[concept], "casepath": value, "others": others})
    rows.sort(key=lambda r: (r["casepath"], -max(r["others"])))
    colours = cycle()
    with plt.style.context(STYLE):
        fig, ax = plt.subplots(figsize=(WIDTH, WIDTH * 0.46))
        for y, r in enumerate(rows):
            ax.plot([min(r["others"]), max(r["others"])], [y, y], color=FAINT, lw=2.5,
                    solid_capstyle="round", zorder=1)
            for v, marker, colour in zip(r["others"], MARKERS, colours[1:4]):
                ax.plot([v], [y], marker=marker, ms=4.2, mew=0.8, markerfacecolor="white",
                        color=colour, ls="none", zorder=2)
            ax.plot([r["casepath"]], [y], marker="o", ms=6, color=colours[0],
                    markeredgecolor="white", mew=0.8, zorder=3)
        ax.set_yticks(range(len(rows)), [r["label"] for r in rows])
        ax.set(xlim=(-0.03, 1.03), ylim=(-0.6, len(rows) - 0.4))
        ax.set_xlabel("Mean pair $F_1$ within the branch concept, held-out contexts")
        categorical(ax)
        handles = [Line2D([], [], marker="o", ms=5.5, color=colours[0], ls="none", label="CasePath")]
        handles += [Line2D([], [], marker=m, ms=4.4, color=c, ls="none", markerfacecolor="white",
                           label=lab)
                    for (_, lab), m, c in zip(COMPARATORS, MARKERS, colours[1:4])]
        ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(-0.42, 1.01, 1.42, 0.1),
                  mode="expand", ncol=4, handletextpad=0.35, borderaxespad=0.0)
        save(fig, "fig_family_results.pdf")


def error_origin() -> None:
    """The unjustified changes differ in kind: the comparators' never touch a governed branch."""
    data = json.loads((HERE / "SPURIOUS_ORIGIN.json").read_text())
    order = [("b5_process_compiled", "CasePath"), ("b1_direct", "Direct"),
             ("b3_representation_then_list", "Graph as context"),
             ("b6_evidence_first", "Evidence-first")]
    colours = cycle()
    with plt.style.context(STYLE):
        fig, ax = plt.subplots(figsize=(WIDTH, WIDTH * 0.34))
        for y, (key, label) in enumerate(reversed(order)):
            a = data["arms"][key]
            governed = a["required_in_one_unit"] + a["governed_elsewhere"]
            ungoverned = a["not_branch_governed"]
            ax.barh(y, governed, height=0.5, color=colours[0], zorder=2)
            ax.barh(y, ungoverned, left=governed, height=0.5, color=FAINT,
                    edgecolor=GREY, lw=0.4, zorder=2)
            if governed:
                ax.text(governed / 2, y, str(governed), ha="center", va="center", color="white",
                        fontsize=7.5)
            ax.text(governed + ungoverned + 0.8, y, str(ungoverned), ha="left", va="center",
                    fontsize=8)
        ax.set_yticks(range(len(order)), [lab for _, lab in reversed(order)])
        ax.set(xlim=(0, 57), ylim=(-0.6, len(order) - 0.4))
        ax.set_xlabel("Unjustified signed changes on the held-out pairs")
        categorical(ax)
        ax.legend(handles=[
            Line2D([], [], color=colours[0], lw=5, label="on a branch the benchmark governs"),
            Line2D([], [], color=FAINT, lw=5, label="on no branch at all")],
            loc="lower left", bbox_to_anchor=(-0.20, 1.01, 1.20, 0.1), mode="expand", ncol=2,
            handletextpad=0.5, borderaxespad=0.0)
        save(fig, "fig_error_origin.pdf")


def scope_control() -> None:
    """What inherited scope buys: the same evidence recovered, at less than half the demand."""
    report = json.loads((HERE / "native150/ASSESSED_STATE_REPORT.json").read_text())
    splits = [("public_dev", "Development"), ("hidden_test", "Protected families")]
    colours = cycle()
    with plt.style.context(STYLE):
        fig, (left, right) = plt.subplots(1, 2, figsize=(WIDTH, WIDTH * 0.37),
                                          gridspec_kw={"width_ratios": [1.45, 1]})
        y, ticks, names = 0, [], []
        for split, name in splits:
            arms = report["splits"][split]["arms"]
            for arm, arm_label in (("LOCAL_SCOPE_ABLATION", "Local only"),
                                   ("CASEPATH_CONTROL", "Full scope")):
                a = arms[arm]
                cells = a["raw_count_contributing_cells"]
                req = a["raw_native_counts"]["evidence/requested_documents"] / cells
                valid = a["raw_native_counts"]["evidence/valid_chain_documents"] / cells
                ax_colour = colours[0] if arm == "CASEPATH_CONTROL" else GREY
                left.barh(y, valid, height=0.52, color=ax_colour, zorder=2)
                left.barh(y, req - valid, left=valid, height=0.52, color=FAINT,
                          edgecolor=GREY, lw=0.4, zorder=2)
                left.text(valid / 2, y, f"{valid:.1f}", ha="center", va="center", color="white",
                          fontsize=7.5)
                waste = req - valid
                left.text(req + 0.35, y, "none wasted" if waste < 0.05 else f"+{waste:.1f}",
                          ha="left", va="center", fontsize=8)
                ticks.append(y); names.append(arm_label)
                y += 1
            y += 0.7
        left.set_yticks(ticks, names)
        left.set(xlim=(0, 17.5), ylim=(-0.7, y - 1.0))
        left.set_xlabel("Document requests per case")
        left.set_xticks([0, 5, 10, 15])
        categorical(left)
        for idx, (_, name) in enumerate(splits):
            left.text(-5.6, ticks[2 * idx] + 0.5, name, fontsize=8, color=GREY,
                      rotation=90, va="center", ha="center")
        left.legend(handles=[
            Line2D([], [], color=colours[0], lw=5, label="valid requests"),
            Line2D([], [], color=FAINT, lw=5, label="unjustified")],
            loc="lower left", bbox_to_anchor=(-0.28, 1.01, 1.28, 0.1), mode="expand", ncol=2,
            handletextpad=0.5, borderaxespad=0.0)

        metrics = [("critical_evidence_recall", "Critical-evidence\nrecall"),
                   ("valid_chain_precision", "Valid-chain\nprecision")]
        arms = report["splits"]["hidden_test"]["arms"]
        for row, (key, name) in enumerate(metrics):
            lo = arms["LOCAL_SCOPE_ABLATION"]["metrics"][key]["value"]
            hi = arms["CASEPATH_CONTROL"]["metrics"][key]["value"]
            right.plot([lo, hi], [row, row], color=FAINT, lw=2.5, solid_capstyle="round", zorder=1)
            right.plot([lo], [row], marker="s", ms=4.5, color=GREY, markerfacecolor="white",
                       mew=0.8, zorder=2)
            right.plot([hi], [row], marker="o", ms=6, color=colours[0], markeredgecolor="white",
                       mew=0.8, zorder=3)
            right.text(lo, row - 0.28, f"{lo:.3f}", ha="center", va="top", fontsize=7.5)
            right.text(hi, row + 0.24, f"{hi:.3f}", ha="center", va="bottom", fontsize=7.5,
                       color=colours[0])
        right.set_yticks(range(len(metrics)), [n for _, n in metrics])
        right.set(xlim=(0, 1.03), ylim=(-0.75, len(metrics) - 0.35))
        right.set_xlabel("Protected families")
        right.set_xticks([0, 0.5, 1.0], ["0", "0.5", "1.0"])
        categorical(right)
        save(fig, "fig_scope_control.pdf")


# --------------------------------------------------------------------------- diagrams

def principle() -> None:
    """The chain, and what each of the three condition states does to it. A diagram, not a plot."""
    colours = cycle()
    with plt.style.context(STYLE):
        fig, ax = plt.subplots(figsize=(WIDTH, WIDTH * 0.335))
        ax.set(xlim=(0, 1), ylim=(0, 1))
        ax.axis("off")
        ax.text(0, .97, "A source rule requires evidence of a scheduled valuable's value",
                fontsize=10, va="top")
        xs = [.075, .275, .47, .665, .89]
        for x, head in zip(xs, ["Case condition", "Obligation", "Required fact",
                                "Evidence capability", "Document / action"]):
            ax.text(x, .77, head, ha="center", fontsize=8, color=GREY)
        ax.plot([0, 1], [.71, .71], color=FAINT, lw=.7)
        for x, val in zip(xs, ["True", "Establish\nvalue", "Value of\nthe item",
                               "Reliable\nvaluation", "Receipt or\nexpert valuation"]):
            ax.text(x, .56, val, ha="center", va="center", fontsize=9, color=colours[0])
        for a, b in zip(xs, xs[1:]):
            ax.annotate("", xy=(b - (.10 if b == xs[-1] else .071), .56), xytext=(a + .071, .56),
                        arrowprops={"arrowstyle": "->", "color": colours[0], "lw": .8})
        for y, state, obligation, action in [
                (.31, "False", "Inactive", "No request on this branch"),
                (.09, "Unresolved", "Not yet active", "Ask whether the item is scheduled")]:
            ax.text(xs[0], y, state, ha="center", va="center", fontsize=9)
            ax.text(xs[1], y, obligation, ha="center", va="center", fontsize=9)
            ax.annotate("", xy=(xs[1] - .071, y), xytext=(xs[0] + .071, y),
                        arrowprops={"arrowstyle": "->", "color": GREY, "lw": .7})
            ax.plot([.39, .45], [y, y], color=GREY, lw=.7)
            ax.text(.475, y, action, va="center", fontsize=9)
        save(fig, "fig_process_principle.pdf")


def recorded_case() -> None:
    """One recorded prediction: missing is not the same as required. A diagram, not a plot."""
    ev = json.loads((HERE / "native150/RECORDED_CASE_STATES.json").read_text())
    assert ev["guards"]["arrears"]["value"] is True
    assert ev["guards"]["family_home"]["value"] is None
    assert ev["documents"]["payment_deadline_letter"]["presence"] == "missing"
    assert ev["documents"]["spouse_notice_copy"]["presence"] == "missing"
    assert "payment_deadline_letter" in ev["documents_now"]
    assert "spouse_notice_copy" in ev["documents_conditional"]
    colours = cycle()
    with plt.style.context(STYLE):
        fig, ax = plt.subplots(figsize=(WIDTH, WIDTH * 0.45))
        ax.set(xlim=(0, 1), ylim=(0, 1))
        ax.axis("off")
        ax.text(0, .97, "Both documents are missing; only one is a request", fontsize=10, va="top")
        cols = [.34, .76]
        for x, head in zip(cols, ["Arrears procedure", "Family-home protection"]):
            ax.text(x, .81, head, ha="center", fontsize=9.5)
        rows = [(.66, "Case condition", "Arrears: true", "Family home: unresolved"),
                (.51, "Obligation", "Cure notice with warning", "Separate spouse notice"),
                (.36, "Evidence state", "Missing", "Missing"),
                (.20, "Plan", "Request now", "Hold, ask first")]
        for y, label, first, second in rows:
            ax.text(0, y, label, fontsize=8.5, color=GREY, va="center")
            for x, value in zip(cols, [first, second]):
                colour = (colours[0] if x == cols[0] else colours[2]) if y == .20 else "black"
                ax.text(x, y, value, fontsize=9, ha="center", va="center", color=colour)
        for x in cols:
            for a, b in ((.615, .555), (.465, .405), (.315, .245)):
                ax.annotate("", xy=(x, b), xytext=(x, a),
                            arrowprops={"arrowstyle": "->", "lw": .7, "color": GREY})
        ax.plot([0, 1], [.10, .10], color=FAINT, lw=.7)
        ax.text(0, .045, "An unresolved condition is answered before its documents are demanded.",
                fontsize=9, va="center")
        save(fig, "fig_native_case.pdf")


# --------------------------------------------------------------------------- audit

def audit() -> None:
    plots = "SciencePlots science+no-latex: frame, inward major and minor ticks, style colour " \
            "cycle, frameless legend. Minor ticks off on the category axis; light x grid added."
    diagram = "Diagram, not a plot: no axes, so only the style's typography and colours apply."
    sources = {
        "fig_family_results.pdf": ("PAIRED_V5_REPRODUCED_RESULT.json", "/scores/*/family_pair_f1",
                                   "held-out Study A measurement", plots),
        "fig_error_origin.pdf": ("SPURIOUS_ORIGIN.json", "/arms/*",
                                 "descriptive partition of the held-out Study A spurious changes",
                                 plots),
        "fig_scope_control.pdf": ("native150/ASSESSED_STATE_REPORT.json",
                                  "/splits/*/arms/{CASEPATH_CONTROL,LOCAL_SCOPE_ABLATION}/"
                                  "{metrics,raw_native_counts,raw_count_contributing_cells}",
                                  "separate retrospective current-case scope intervention; counts "
                                  "are divided by each arm's contributing cells, which differ by "
                                  "two on the protected split", plots),
        "fig_native_case.pdf": ("native150/RECORDED_CASE_STATES.json", "/",
                                "recorded development prediction; not a native acceptance claim",
                                diagram),
        "fig_process_principle.pdf": (None, None, "authored teaching schematic; no measured values",
                                      diagram),
    }
    rows = []
    for name, (source, pointer, meaning, style) in sources.items():
        rows.append({"figure": name,
                     "sha256": hashlib.sha256((DOC / name).read_bytes()).hexdigest(),
                     "evidence_file": source,
                     "evidence_sha256": hashlib.sha256((HERE / source).read_bytes()).hexdigest()
                     if source else None,
                     "json_pointer_pattern": pointer, "scope": meaning, "style": style})
    (HERE / "FIGURE_AUDIT.json").write_text(json.dumps({"figures": rows}, indent=2) + "\n")


if __name__ == "__main__":
    family_results()
    error_origin()
    scope_control()
    principle()
    recorded_case()
    audit()
    print("wrote 3 SciencePlots plots and 2 diagrams, and FIGURE_AUDIT.json")
