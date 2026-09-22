#!/usr/bin/env python3
"""Rebuild the paper's figures from preserved evidence.

    python3 evidence/build_figures.py

Seven figures. Every one is a plot on measured data: there is no schematic left in the paper.

  fig_process_principle   the three condition states, on one real intervention       (Study A)
  fig_selectivity         which document each branch governs, and where each system's
                          held-out changes actually land                               (Study A)
  fig_family_results      where the branch semantics holds and where it fails         (Study A)
  fig_scope_control       what inherited scope buys, case by case                     (Study B)
  fig_native_case         where a chain stops, on one recorded case                   (Study B)
  fig_error_origin        why the unjustified changes differ in kind, not only count  (Study A)
  fig_falsifiers          what the result survives, and what it does not              (Study A)

Style. Every figure is drawn inside SciencePlots `science` + `no-latex` and keeps what the style
provides: the boxed frame, inward major and minor ticks on all four sides, `axes.linewidth` 0.5,
frameless legends, the serif face and the style's own seven-colour cycle, from which every colour
here -- including the two greys -- is taken. Deliberate departures, and only these: minor ticks are
turned off on a categorical axis, where they would subdivide nothing; a faint grid is drawn where
a reader has to carry a value across a wide panel; and the figure width is the manuscript's text
width rather than the style's single-column default.

Every plotted value is read from a preserved evidence file; nothing is typed here. Output is
byte-deterministic, so `verify_release.py` can require the figures to regenerate unchanged.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
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
BENCH = DOC.parent / "branch-benchmark"
WIDTH = 6.7  # the manuscript's text width

CASEPATH = "b5_process_compiled"
COMPARATORS = [("b1_direct", "Direct"),
               ("b3_representation_then_list", "Graph as context"),
               ("b6_evidence_first", "Evidence-first")]
CONCEPT = {  # the short form the three-panel grid has room for
    "PR_bicycle_claimed": "Bicycle",
    "PR_declined": "Declination",
    "PR_expert_procedure_requested": "Expert procedure",
    "PR_goods_recovered": "Recovery",
    "PR_nachfrist_set": "Written demand",
    "PR_repair_over_500": "Repair consent",
    "PR_scheduled_valuable_1000": "Scheduled valuable",
    "PR_sim_card_stolen": "SIM card",
    "PR_third_party_causer": "Third party",
}
FAMILY = {  # the longer form the per-concept figure has room for
    "PR_bicycle_claimed": "Bicycle among stolen items",
    "PR_declined": "Insurer declination",
    "PR_expert_procedure_requested": "Formal expert procedure",
    "PR_goods_recovered": "Recovery of stolen goods",
    "PR_nachfrist_set": "Written demand with period",
    "PR_repair_over_500": "Repair above consent threshold",
    "PR_scheduled_valuable_1000": "Scheduled valuable",
    "PR_sim_card_stolen": "SIM-card theft",
    "PR_third_party_causer": "Identifiable third-party causer",
}
# A unique fragment of each branch document, and the short form the axis has room for.
DOCUMENT = {
    "Bicycle purchase voucher": "Bicycle purchase voucher",
    "Detailed cost estimate": "Bicycle cost estimate",
    "Expert's valuation": "Expert valuation of the valuable",
    "Receipt for the scheduled": "Receipt for the valuable",
    "Insurer's declination": "Insurer's declination",
    "Insurer's prior consent": "Prior consent to the repair",
    "Insurer's written demand": "Written demand under warning",
    "Report of the SIM-card": "SIM-card theft report",
    "Report to the insurer that": "Recovery report",
    "Written appointment": "Written expert appointment",
    "Written assignment": "Assignment of third-party claims",
    "Completed claim-form": "Claim-form section on the causer",
}
OFF_ROW = "any document outside\nthis vocabulary"


def colours() -> list[str]:
    """The science style's own cycle. C5 and C6 are its dark and light greys."""
    with plt.style.context(STYLE):
        return plt.rcParams["axes.prop_cycle"].by_key()["color"]


def flat(ax, axis: str) -> None:
    """The one concession a categorical axis needs: no minor ticks where nothing is subdivided."""
    ax.tick_params(axis=axis, which="minor", **({"left": False, "right": False} if axis == "y"
                                                else {"top": False, "bottom": False}))
    getattr(ax, f"{axis}axis").set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_axisbelow(True)


def save(fig, name: str) -> None:
    fig.savefig(DOC / name, metadata={"CreationDate": None}, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def short(document: str) -> str:
    hits = [v for k, v in DOCUMENT.items() if k in document]
    if len(hits) != 1:
        raise SystemExit(f"document label is not unique: {document!r} -> {hits}")
    return hits[0]


def held_out() -> tuple[dict, dict, dict]:
    """The frozen benchmark and the preserved held-out predictions, keyed for plotting."""
    benchmark = json.loads((BENCH / "benchmark" / "BENCHMARK_V3.json").read_text())
    casepath = json.loads((BENCH / "predictions" / "heldout" / "casepath.json").read_text())
    comparators = json.loads((BENCH / "predictions" / "heldout" / "comparators.json").read_text())
    rows = {CASEPATH: casepath}
    for key, _ in COMPARATORS:
        rows[key] = [r for r in comparators if r["arm"] == key]
    pairs = {p["pair_id"]: p for p in benchmark["pairs"]
             if p["pair_id"] in {r["pair_id"] for r in casepath}}
    governed = {d for u in benchmark["units"] for d in u["gold_branch_documents"]}
    for pair in benchmark["pairs"]:
        for option in pair["acceptable_signed_deltas"]:
            governed.update(atom.lstrip("+-") for atom in option)
    return pairs, rows, {"governed": governed}


# --------------------------------------------------------------------------- figures

def selectivity() -> None:
    """The dependency, and where each system's changes land on it.

    Rows are the documents some branch governs, columns the branch concepts. The reference panel
    is what the sources justify when that concept's condition turns true; the other two are what
    the system actually changed on the held-out contexts. The bottom row collects every change to
    a document no branch governs, which is the whole of the comparators' error.
    """
    pairs, rows, sets = held_out()
    governed = sets["governed"]
    report = json.loads((HERE / "PAIRED_V5_REPRODUCED_RESULT.json").read_text())

    reference: Counter = Counter()
    for pair in pairs.values():
        for option in pair["acceptable_signed_deltas"]:
            for atom in option:
                reference[(pair["scenario"], short(atom.lstrip("+-")), "+")] += 1

    order = sorted(CONCEPT, key=lambda c: (-report["scores"][CASEPATH]["family_pair_f1"][c], c))
    ylabels, seen = [], set()
    for concept in order:
        for document in sorted({d for (c, d, _) in reference if c == concept}):
            if document not in seen:
                seen.add(document)
                ylabels.append(document)
    if len(ylabels) != len(governed):
        raise SystemExit(f"{len(ylabels)} labelled rows for {len(governed)} governed documents")
    ylabels.append(OFF_ROW)
    row = {label: len(ylabels) - 1 - i for i, label in enumerate(ylabels)}
    column = {concept: i for i, concept in enumerate(order)}

    def grid(arm: str) -> Counter:
        counts: Counter = Counter()
        for r in rows[arm]:
            for atom in r["predicted_signed_delta"] or []:
                document = atom[1:]
                key = short(document) if document in governed else OFF_ROW
                counts[(r["scenario"], key, atom[0])] += 1
        return counts

    panels = [("What the sources justify", reference),
              ("CasePath", grid(CASEPATH)),
              ("Graph as context", grid("b3_representation_then_list"))]
    c = colours()
    with plt.style.context(STYLE):
        fig, axes = plt.subplots(1, 3, figsize=(WIDTH, WIDTH * 0.46), sharey=True,
                                 gridspec_kw={"wspace": 0.09})
        for ax, (title, counts) in zip(axes, panels):
            ax.set_title(title, fontsize="small", pad=4)
            ax.axhline(0.5, color=c[6], lw=0.5, zorder=1)
            both = {(cn, dc) for (cn, dc, _) in counts} & {
                (cn, dc) for (cn, dc, sg) in counts if sg == "-"} & {
                (cn, dc) for (cn, dc, sg) in counts if sg == "+"}
            for (concept, document, sign), n in sorted(counts.items()):
                # A cell can hold both directions; split it so neither hides the other.
                offset = 0.0 if (concept, document) not in both else (0.19 if sign == "+" else -0.19)
                ax.plot([column[concept] + offset], [row[document]], marker="o", ls="none",
                        ms=2.1 * n ** 0.5 + 1.4, mew=0.7,
                        color=c[0] if sign == "+" else c[3],
                        markerfacecolor=c[0] if sign == "+" else "white", zorder=3)
            strays = sum(n for (_, document, _), n in counts.items() if document == OFF_ROW)
            if strays:
                ax.text(-0.45, -1.28, f"{strays} changes", ha="left", va="bottom",
                        fontsize="x-small", color=c[5])
            ax.set(xlim=(-0.7, len(order) - 0.3), ylim=(-1.45, len(ylabels) - 0.5))
            ax.set_xticks(range(len(order)), [CONCEPT[k] for k in order],
                          rotation=34, ha="right", rotation_mode="anchor", fontsize="xx-small")
            ax.grid(color=c[6], lw=0.35, zorder=0)
            flat(ax, "x")
            flat(ax, "y")
        axes[0].set_yticks(range(len(ylabels)), list(reversed(ylabels)), fontsize="xx-small")
        axes[0].get_yticklabels()[0].set_color(c[5])
        axes[1].legend(handles=[
            Line2D([], [], marker="o", ms=4, ls="none", color=c[0], label="document added"),
            Line2D([], [], marker="o", ms=4, ls="none", color=c[3], markerfacecolor="white",
                   label="document withdrawn")],
            loc="lower center", bbox_to_anchor=(0.5, 1.13), ncol=2, fontsize="x-small",
            handletextpad=0.3, columnspacing=1.2, borderaxespad=0.0)
        save(fig, "fig_selectivity.pdf")


def process_principle() -> None:
    """The three condition states, on one real benchmark intervention.

    The pair differs by one sentence. When the branch condition holds, the reference contract
    activates an obligation whose fact can be established by either of two document routes, so one
    request is justified. When it does not hold, nothing on this branch is justified. When the
    sources leave it unresolved, the chain stops at the condition and the controller asks.
    """
    benchmark = json.loads((BENCH / "benchmark" / "BENCHMARK_V3.json").read_text())
    pair = next(p for p in benchmark["pairs"]
                if p["scenario"] == "PR_scheduled_valuable_1000" and p["context_index"] == 0)
    requirements = pair["expected_added_requirements"]
    routes = sum(len(r["acceptable_routes"]) for r in requirements)
    if len(requirements) != 1 or pair["expected_withdrawn"]:
        raise SystemExit("this figure assumes one added requirement and no withdrawal")

    stages = ["Branch\ncondition", "Obligation", "Required\nfact", "Document\nroute",
              "Justified\nrequest"]
    live = {"true": len(stages), "false": 1, "unresolved": 1}
    note = {"true": f"{routes} acceptable routes, {len(requirements)} request",
            "false": "nothing justified on this branch",
            "unresolved": "a question, not a document"}
    c = colours()
    tone = {"true": c[0], "false": c[5], "unresolved": c[2]}
    with plt.style.context(STYLE):
        fig, ax = plt.subplots(figsize=(WIDTH, WIDTH * 0.215))
        for y, state in enumerate(("unresolved", "false", "true")):
            reach = live[state]
            ax.plot(range(reach), [y] * reach, color=tone[state], lw=1.1, zorder=2)
            ax.plot(range(reach), [y] * reach, marker="o", ms=3.4, ls="none", color=tone[state],
                    zorder=3)
            if reach < len(stages):
                ax.plot([reach - 1 + 0.42], [y], marker="x", ms=4.2, mew=1.1, ls="none",
                        color=tone[state], zorder=3)
            ax.text(reach - 1 + (0.62 if reach < len(stages) else 0.18), y, note[state],
                    va="center", fontsize="x-small", color=tone[state])
        ax.set_xticks(range(len(stages)), stages, fontsize="x-small")
        ax.set_yticks(range(3), ["unresolved", "false", "true"], fontsize="x-small")
        for label, state in zip(ax.get_yticklabels(), ("unresolved", "false", "true")):
            label.set_color(tone[state])
        ax.tick_params(axis="y", length=0)
        ax.set_ylabel("the branch condition is", fontsize="x-small")
        ax.set(xlim=(-0.3, len(stages) + 1.75), ylim=(-0.6, 2.45))
        ax.text(-0.3, 2.60, "One sentence changes: " + pair["changed_statement_true"],
                fontsize="x-small", va="bottom", color=c[5])
        ax.grid(axis="x", color=c[6], lw=0.35, zorder=0)
        flat(ax, "x")
        flat(ax, "y")
        save(fig, "fig_process_principle.pdf")


def family_results() -> None:
    """Where the branch semantics holds and where it fails, concept by concept."""
    report = json.loads((HERE / "PAIRED_V5_REPRODUCED_RESULT.json").read_text())
    scores = report["scores"]
    rows = []
    for concept, value in scores[CASEPATH]["family_pair_f1"].items():
        others = [scores[k]["family_pair_f1"][concept] for k, _ in COMPARATORS]
        rows.append({"label": FAMILY[concept], "casepath": value, "others": others})
    rows.sort(key=lambda r: (r["casepath"], -max(r["others"])))
    c = colours()
    with plt.style.context(STYLE):
        fig, ax = plt.subplots(figsize=(WIDTH, WIDTH * 0.46))
        for y, r in enumerate(rows):
            ax.plot([min(r["others"]), max(r["others"])], [y, y], color=c[6], lw=1.8,
                    alpha=0.65, solid_capstyle="round", zorder=1)
            for v, marker, colour in zip(r["others"], ("s", "^", "X"), c[1:4]):
                ax.plot([v], [y], marker=marker, ms=4.2, mew=0.8, markerfacecolor="white",
                        color=colour, ls="none", zorder=2)
            ax.plot([r["casepath"]], [y], marker="o", ms=6, color=c[0],
                    markeredgecolor="white", mew=0.8, zorder=3)
        ax.set_yticks(range(len(rows)), [r["label"] for r in rows])
        ax.set(xlim=(-0.03, 1.03), ylim=(-0.6, len(rows) - 0.4))
        ax.set_xlabel("Mean pair $F_1$ within the branch concept, held-out contexts")
        ax.grid(axis="x", color=c[6], lw=0.5)
        flat(ax, "y")
        handles = [Line2D([], [], marker="o", ms=5.5, color=c[0], ls="none", label="CasePath")]
        handles += [Line2D([], [], marker=m, ms=4.4, color=col, ls="none", markerfacecolor="white",
                           label=label)
                    for (_, label), m, col in zip(COMPARATORS, ("s", "^", "X"), c[1:4])]
        ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(-0.42, 1.01, 1.42, 0.1),
                  mode="expand", ncol=4, handletextpad=0.35, borderaxespad=0.0)
        save(fig, "fig_family_results.pdf")


def scope_control() -> None:
    """What inherited scope buys, case by case: the same evidence, at a third of the demand."""
    rows = json.loads((HERE / "native150/ASSESSED_STATE_ROWS.json").read_text())
    report = json.loads((HERE / "native150/ASSESSED_STATE_REPORT.json").read_text())
    by_case: dict[str, dict] = defaultdict(dict)
    for r in rows:
        if r["split"] == "hidden_test" and r["evaluation_status"] == "observed":
            by_case[r["case_id"]][r["arm"]] = r["native_counts"]
    paired = [v for _, v in sorted(by_case.items())
              if {"CASEPATH_CONTROL", "LOCAL_SCOPE_ABLATION"} <= set(v)]
    points = {arm: Counter((v[arm]["evidence/requested_documents"],
                            v[arm]["evidence/valid_chain_documents"]) for v in paired)
              for arm in ("LOCAL_SCOPE_ABLATION", "CASEPATH_CONTROL")}
    top = max(x for arm in points for x, _ in points[arm]) + 1

    c = colours()
    with plt.style.context(STYLE):
        fig, (left, right) = plt.subplots(1, 2, figsize=(WIDTH, WIDTH * 0.40),
                                          gridspec_kw={"width_ratios": [1.3, 1], "wspace": 0.28})
        left.plot([0, top], [0, top], color=c[6], lw=0.7, zorder=1)
        left.text(top * 0.60, top * 0.60, "every request valid", fontsize="x-small", color=c[5],
                  rotation=45, rotation_mode="anchor", ha="center", va="bottom")
        for arm, colour, marker, label in (
                ("LOCAL_SCOPE_ABLATION", c[5], "s", "Local guard only"),
                ("CASEPATH_CONTROL", c[0], "o", "Inherited scope")):
            for (x, y), n in sorted(points[arm].items()):
                left.plot([x], [y], marker=marker, ms=2.0 * n ** 0.5 + 2.2, ls="none",
                          color=colour, markerfacecolor=colour if arm.startswith("CASE") else "white",
                          mew=0.8, alpha=0.9, zorder=3 if arm.startswith("CASE") else 2,
                          label=label if (x, y) == min(points[arm]) else None)
        left.set(xlim=(0, top), ylim=(0, top))
        left.set_xticks(range(0, top, 4))
        left.set_yticks(range(0, top, 4))
        left.set_xlabel("Documents requested on the case")
        left.set_ylabel("Requests with a valid chain")
        left.grid(color=c[6], lw=0.35, zorder=0)
        left.legend(loc="upper left", fontsize="x-small", handletextpad=0.3, borderaxespad=0.3)
        left.text(0.98, 0.04, f"{len(paired)} protected cases", transform=left.transAxes,
                  ha="right", va="bottom", fontsize="x-small", color=c[5])

        arms = report["splits"]["hidden_test"]["arms"]
        metrics = [("critical_evidence_recall", "Critical-evidence recall"),
                   ("required_node_precision", "Required-node precision"),
                   ("valid_chain_precision", "Valid-chain precision")]
        for y, (key, name) in enumerate(reversed(metrics)):
            lo = arms["LOCAL_SCOPE_ABLATION"]["metrics"][key]["value"]
            hi = arms["CASEPATH_CONTROL"]["metrics"][key]["value"]
            right.annotate("", xy=(hi, y), xytext=(lo, y),
                           arrowprops={"arrowstyle": "-|>", "color": c[6], "lw": 2.2,
                                       "shrinkA": 2, "shrinkB": 2})
            right.plot([lo], [y], marker="s", ms=4.5, color=c[5], markerfacecolor="white",
                       mew=0.8, zorder=3)
            right.plot([hi], [y], marker="o", ms=5.5, color=c[0], markeredgecolor="white",
                       mew=0.8, zorder=3)
            right.text(min(lo, hi), y + 0.22, name, fontsize="x-small", va="bottom", ha="left")
            # One delta column, so a metric that barely moves stays legible next to one that does.
            right.text(1.06, y, f"{hi - lo:+.3f}", ha="left", va="center", fontsize="x-small",
                       color=c[0] if hi - lo > 0.1 else c[5])
        right.set(xlim=(0.14, 1.0), ylim=(-0.6, len(metrics) - 0.25), yticks=[])
        right.set_xticks([0.25, 0.5, 0.75, 1.0], ["0.25", "0.5", "0.75", "1.0"])
        right.set_xlabel("Protected families")
        right.text(1.06, len(metrics) - 0.35, "change", fontsize="x-small", color=c[5],
                   ha="left", va="center")
        right.grid(axis="x", color=c[6], lw=0.35, zorder=0)
        flat(right, "y")
        save(fig, "fig_scope_control.pdf")


def recorded_case() -> None:
    """One recorded case: the chain either reaches a document or stops at an unresolved scope.

    Both highlighted documents are absent from the file. One is demanded, because its obligation's
    scope resolved true; the other is not, because its scope is unresolved and the controller asks
    first. Missing is not the same as required, and the chain is where the difference is decided.
    """
    trace = json.loads((HERE / "native150/RECORDED_CASE_TRACE.json").read_text())
    states = json.loads((HERE / "native150/RECORDED_CASE_STATES.json").read_text())
    missing = sorted(d for d, v in states["documents"].items() if v["presence"] == "missing")
    if len(missing) != 2 or not (set(missing) & set(states["documents_now"])
                                 and set(missing) & set(states["documents_conditional"])):
        raise SystemExit("this figure needs one missing document on each side of the scope test")

    stages = ["Scope", "Obligation", "Required\nfact", "Evidence\ncapability", "Document\nroute",
              "Request"]
    requests = sorted(trace["requests"], key=lambda r: r["document_id"])
    held = sorted(trace["conditional_documents"])
    if len(trace["questions"]) != len(held):
        raise SystemExit("one held document per unresolved question is assumed by this figure")
    c = colours()
    with plt.style.context(STYLE):
        fig, ax = plt.subplots(figsize=(WIDTH, WIDTH * 0.40))
        for i, request in enumerate(requests):
            y = len(held) + len(requests) - 1 - i
            chain = request["chains"][0]
            if not all(chain[k] for k in ("scope_id", "obligation_id", "fact_id",
                                          "capability_id", "route_id", "document_id")):
                raise SystemExit(f"incomplete chain for {request['document_id']}")
            lit = request["document_id"] in missing
            ax.plot(range(len(stages)), [y] * len(stages), color=c[0], lw=1.3 if lit else 0.8,
                    zorder=3 if lit else 2)
            ax.plot(range(len(stages)), [y] * len(stages), marker="o", ms=3.2 if lit else 2.6,
                    ls="none", color=c[0], zorder=4 if lit else 3)
            ax.text(len(stages) - 1 + 0.18, y, request["document_id"].replace("_", " "),
                    va="center", fontsize="x-small", color=c[0] if lit else "black")
        for i, document in enumerate(held):
            y = len(held) - 1 - i
            lit = document in missing
            ax.plot([0], [y], marker="o", ms=4.6 if lit else 4.0, ls="none", color=c[2],
                    markerfacecolor="white", mew=1.1 if lit else 0.8, zorder=4)
            ax.plot([0, 0.42], [y, y], color=c[2], lw=1.1 if lit else 0.8, ls=(0, (1.6, 1.4)),
                    zorder=3)
            ax.text(len(stages) - 1 + 0.18, y, document.replace("_", " "), va="center",
                    fontsize="x-small", color=c[2] if lit else c[5])
        ax.text(0.58, (len(held) - 1) / 2,
                "scope unresolved \u2014 the controller asks first",
                va="center", fontsize="x-small", color=c[2])
        ax.axhline(len(held) - 0.5, color=c[6], lw=0.5, zorder=1)

        # The punchline: the two absent documents, one on each side of the scope test.
        top = len(held) + len(requests) - 1 - requests.index(
            next(r for r in requests if r["document_id"] in missing))
        bottom = len(held) - 1 - held.index(next(d for d in held if d in missing))
        edge = len(stages) + 1.62
        for y in (top, bottom):
            ax.plot([edge - 0.06, edge], [y, y], color=c[5], lw=0.6, zorder=3)
        ax.plot([edge, edge], [bottom, top], color=c[5], lw=0.6, zorder=3)
        ax.text(edge + 0.08, (top + bottom) / 2, "both absent\nfrom the file", va="center",
                fontsize="x-small", color=c[5], linespacing=1.5)

        ax.set_xticks(range(len(stages)), stages, fontsize="x-small")
        ax.set_yticks([len(held) + (len(requests) - 1) / 2, (len(held) - 1) / 2],
                      [f"{len(requests)} requested\nnow", f"{len(held)} held behind\na question"],
                      fontsize="x-small")
        ax.tick_params(axis="y", length=0)
        for label, colour in zip(ax.get_yticklabels(), (c[0], c[2])):
            label.set_color(colour)
        ax.set(xlim=(-0.35, len(stages) + 3.15), ylim=(-0.7, len(held) + len(requests) - 0.3))
        ax.grid(axis="x", color=c[6], lw=0.35, zorder=0)
        flat(ax, "x")
        flat(ax, "y")
        save(fig, "fig_native_case.pdf")


def error_origin() -> None:
    """The unjustified changes differ in kind: the comparators' never touch a governed branch."""
    data = json.loads((HERE / "SPURIOUS_ORIGIN.json").read_text())
    if data["reference_changes_by_direction"]["withdrawn"] != 0:
        raise SystemExit("this figure assumes the reference never withdraws a document")
    order = [(CASEPATH, "CasePath")] + COMPARATORS
    c = colours()
    with plt.style.context(STYLE):
        fig, ax = plt.subplots(figsize=(WIDTH, WIDTH * 0.32))
        for i, (key, label) in enumerate(order):
            a = data["arms"][key]
            y = len(order) - 1 - i
            on = a["required_in_one_unit"] + a["governed_elsewhere"]
            # Every withdrawal is unjustified: the reference contract only ever adds.
            off_added = a["added"] - on
            ax.barh(y, on, height=0.5, color=c[0], zorder=3)
            ax.barh(y, off_added, left=on, height=0.5, color=c[6], edgecolor=c[5], lw=0.4,
                    zorder=3)
            ax.barh(y, -a["withdrawn"], height=0.5, color="white", edgecolor=c[3], lw=0.7,
                    hatch="////", zorder=3)
            if on:
                ax.text(on / 2, y, str(on), ha="center", va="center", color="white",
                        fontsize="x-small")
            ax.text(on + off_added + 0.7, y, str(off_added), ha="left", va="center",
                    fontsize="x-small")
            if a["withdrawn"]:
                ax.text(-a["withdrawn"] - 0.7, y, str(a["withdrawn"]), ha="right", va="center",
                        fontsize="x-small", color=c[3])
        ax.axvline(0, color=c[5], lw=0.6, zorder=4)
        ax.set_yticks(range(len(order)), [label for _, label in reversed(order)])
        ax.set(xlim=(-34, 27), ylim=(-0.6, len(order) - 0.4))
        ax.set_xticks([-30, -20, -10, 0, 10, 20], ["30", "20", "10", "0", "10", "20"])
        ax.set_xlabel("withdrawn  $\\longleftarrow$   unjustified signed changes, held-out pairs"
                      "   $\\longrightarrow$  added")
        ax.grid(axis="x", color=c[6], lw=0.35, zorder=0)
        flat(ax, "y")
        ax.legend(handles=[
            Line2D([], [], color=c[0], lw=5, label="on a branch the benchmark governs"),
            Line2D([], [], color=c[6], lw=5, label="on no branch at all"),
            Line2D([], [], color=c[3], lw=1.2, label="withdrawal (never justified here)")],
            loc="lower left", bbox_to_anchor=(0.0, 1.02, 1.0, 0.1), mode="expand", ncol=3,
            handletextpad=0.5, borderaxespad=0.0, fontsize="x-small")
        save(fig, "fig_error_origin.pdf")


def falsifiers() -> None:
    """What the result survives, and what it does not.

    Left: hold CasePath's held-out outputs fixed and give them to the wrong branch family. The
    whole null mass sits at or below one twelfth; the observed score does not. Right: the
    preregistered family-swap contrast, which does not reach significance and is reported as such.
    """
    null = json.loads((HERE / "WRONG_PAIRING_NULL.json").read_text())
    report = json.loads((HERE / "PAIRED_V5_REPRODUCED_RESULT.json").read_text())
    spectrum = Counter(null["null"])
    c = colours()
    with plt.style.context(STYLE):
        fig, (left, right) = plt.subplots(1, 2, figsize=(WIDTH, WIDTH * 0.34),
                                          gridspec_kw={"width_ratios": [1.15, 1], "wspace": 0.26})
        for value, n in sorted(spectrum.items()):
            left.bar([value], [n], width=0.016, color=c[5], zorder=3)
            left.text(value, n + 110, f"{n:,}", ha="center", fontsize="x-small", color=c[5])
        observed = null["observed_micro_f1"]
        left.axvline(observed, color=c[0], lw=1.0, zorder=4)
        left.plot([observed], [0], marker="^", ms=5, color=c[0], clip_on=False, zorder=5)
        left.text(observed - 0.02, 4700, f"observed {observed:.3f}\n$p$ = "
                  f"{null['p_ge_plus1']:.4f}", ha="right", va="top", fontsize="x-small",
                  color=c[0], linespacing=1.4)
        left.set(xlim=(-0.045, 0.78), ylim=(0, 5000))
        left.set_xlabel(f"Micro $F_1$ over {len(null['null']):,} wrong-family reassignments")
        left.set_ylabel("Reassignments")
        left.set_yticks([0, 2000, 4000], ["0", "2,000", "4,000"])
        left.grid(axis="y", color=c[6], lw=0.35, zorder=0)

        swaps = report["family_swap_tests"]
        for y, (key, label) in enumerate(reversed(COMPARATORS)):
            test = swaps[key]
            for difference in sorted(test["family_differences"]):
                right.plot([difference], [y], marker="o", ms=3.4, ls="none", mew=0.7,
                           color=c[0] if difference > 0 else c[3], markerfacecolor="white",
                           zorder=3)
            right.plot([test["observed_mean_difference"]], [y], marker="|", ms=11, mew=1.6,
                       color=c[5], zorder=4)
            right.text(1.04, y, f"Holm $p$ = {test['holm_adjusted_p']:.3f}", fontsize="x-small",
                       va="center", ha="left", color=c[5])
        right.axvline(0, color=c[5], lw=0.6, zorder=2)
        right.set_yticks(range(len(COMPARATORS)), [label for _, label in reversed(COMPARATORS)],
                         fontsize="x-small")
        right.set(xlim=(-1.08, 1.02), ylim=(-0.55, len(COMPARATORS) - 0.35))
        right.set_xticks([-1, -0.5, 0, 0.5, 1], ["$-$1", "", "0", "", "1"])
        right.set_xlabel("Per-concept $F_1$ difference, CasePath $-$ comparator")
        right.grid(axis="x", color=c[6], lw=0.35, zorder=0)
        right.legend(handles=[
            Line2D([], [], marker="|", ms=9, mew=1.6, ls="none", color=c[5], label="mean"),
            Line2D([], [], marker="o", ms=3.4, ls="none", color=c[0], markerfacecolor="white",
                   label="CasePath ahead"),
            Line2D([], [], marker="o", ms=3.4, ls="none", color=c[3], markerfacecolor="white",
                   label="behind")],
            loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3, fontsize="x-small",
            handletextpad=0.25, columnspacing=1.0, borderaxespad=0.0)
        flat(right, "y")
        save(fig, "fig_falsifiers.pdf")


# --------------------------------------------------------------------------- audit

def audit() -> None:
    style = ("SciencePlots science+no-latex: boxed frame, inward major and minor ticks, "
             "axes.linewidth 0.5, frameless legend, serif face, and every colour taken from the "
             "style's own cycle. Departures: minor ticks off on categorical axes; a faint grid; "
             "text-width figure size.")
    sources = {
        "fig_process_principle.pdf": (
            "branch-benchmark/benchmark/BENCHMARK_V3.json",
            "/pairs/[pair_id=theft-01-01]/{changed_statement_true,"
            "expected_added_requirements,expected_withdrawn}",
            "one frozen benchmark intervention: the changed sentence, its added requirement and "
            "its acceptable routes are read from the reference contract; the three condition "
            "states are the method's semantics, not a measurement"),
        "fig_selectivity.pdf": (
            ("branch-benchmark/benchmark/BENCHMARK_V3.json",
             "branch-benchmark/predictions/heldout/casepath.json",
             "branch-benchmark/predictions/heldout/comparators.json",
             "PAIRED_V5_REPRODUCED_RESULT.json"),
            "/pairs/*/acceptable_signed_deltas, /*/predicted_signed_delta, and "
            "/scores/b5_process_compiled/family_pair_f1 for the column order",
            "frozen reference contract and the preserved held-out predictions; the reference "
            "panel is what the sources justify, not a system output"),
        "fig_family_results.pdf": (
            "PAIRED_V5_REPRODUCED_RESULT.json", "/scores/*/family_pair_f1",
            "held-out Study A measurement"),
        "fig_scope_control.pdf": (
            "native150/ASSESSED_STATE_ROWS.json",
            "/*/native_counts/evidence/{requested_documents,valid_chain_documents} on the "
            "protected split, and ASSESSED_STATE_REPORT.json /splits/hidden_test/arms/*/metrics",
            "separate retrospective current-case scope intervention; the scatter is restricted to "
            "the cases observed in both arms, which is two fewer than CasePath's own observed set"),
        "fig_native_case.pdf": (
            "native150/RECORDED_CASE_TRACE.json", "/requests, /conditional_documents, /questions",
            "recorded development prediction; not a native acceptance claim"),
        "fig_error_origin.pdf": (
            "SPURIOUS_ORIGIN.json", "/arms/*, /reference_changes_by_direction",
            "descriptive partition of the held-out Study A spurious changes"),
        "fig_falsifiers.pdf": (
            "WRONG_PAIRING_NULL.json",
            "/null, /observed_micro_f1, /p_ge_plus1, and PAIRED_V5_REPRODUCED_RESULT.json "
            "/family_swap_tests/*",
            "preregistered falsifiers, including the family-swap contrast that does not reach "
            "significance"),
    }
    def resolve(name: str) -> Path:
        return BENCH.parent / name if name.startswith("branch-benchmark/") else HERE / name

    rows = []
    for name, (source, pointer, meaning) in sources.items():
        files = (source,) if isinstance(source, str) else source
        rows.append({"figure": name,
                     "sha256": hashlib.sha256((DOC / name).read_bytes()).hexdigest(),
                     "evidence_file": source if isinstance(source, str) else list(files),
                     "evidence_sha256": {f: hashlib.sha256(resolve(f).read_bytes()).hexdigest()
                                         for f in files},
                     "json_pointer_pattern": pointer, "scope": meaning, "style": style})
    (HERE / "FIGURE_AUDIT.json").write_text(json.dumps({"figures": rows}, indent=2) + "\n")


if __name__ == "__main__":
    process_principle()
    selectivity()
    family_results()
    scope_control()
    recorded_case()
    error_origin()
    falsifiers()
    audit()
    print("wrote 7 SciencePlots figures and FIGURE_AUDIT.json")
