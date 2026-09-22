#!/usr/bin/env python3
"""Rebuild the paper's figures from preserved evidence.

    python3 evidence/build_figures.py

Seven figures, each a plot on measured data.

  fig_process_principle   what one branch condition does to the chain            (Study A)
  fig_family_results      where the branch semantics holds and where it fails    (Study A)
  fig_scope_control       what inherited scope buys, case by case                (Study B)
  fig_selectivity         which document each branch governs, and where each
                          system's held-out changes actually land                (Study A)
  fig_falsifiers          what the result survives, and what it does not         (Study A)
  fig_error_origin        why the unjustified changes differ in kind             (Study A)
  fig_native_case         where a chain stops, on one recorded case              (Study B)

Style. Drawn the way SciencePlots is meant to be used: `plt.style.context`, the style's own figure
proportions, `autoscale(tight=True)`, one framed-or-frameless legend from the style, axis labels,
and nothing else on the canvas. Grids come from the style's own `grid` variant when a dense panel
needs them, never hand-drawn. No colour, line width, tick or font size is set here that the style
already sets; where a dense panel needs smaller type, `font.size` is lowered once inside the
context so the whole type scale moves together. Whatever a reader would otherwise need an
annotation for is either in the data or in the caption.

Figures are authored at the manuscript's own text width, so `\\includegraphics` does not rescale the
type. Every plotted value is read from a preserved evidence file; nothing is typed here. Output is
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

STYLE = ["science", "no-latex"]
GRID = ["science", "grid", "no-latex"]
plt.rcParams.update({"pdf.fonttype": 42, "ps.fonttype": 42, "svg.hashsalt": "casepath-paper"})

HERE = Path(__file__).resolve().parent
DOC = HERE.parent
BENCH = DOC.parent / "branch-benchmark"
TEXT = 5.5   # the manuscript's text width, so nothing is rescaled on inclusion
GOLDEN = 0.75  # the style's own 4:3 proportion

CASEPATH = "b5_process_compiled"
COMPARATORS = [("b1_direct", "Direct"),
               ("b3_representation_then_list", "Graph as context"),
               ("b6_evidence_first", "Evidence-first")]
CONCEPT = {
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
OFF_ROW = "outside this vocabulary"


def save(fig, name: str) -> None:
    fig.savefig(DOC / name, metadata={"CreationDate": None}, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def short(document: str) -> str:
    hits = [v for k, v in DOCUMENT.items() if k in document]
    if len(hits) != 1:
        raise SystemExit(f"document label is not unique: {document!r} -> {hits}")
    return hits[0]


def held_out() -> tuple[dict, dict, set]:
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
    return pairs, rows, governed


# --------------------------------------------------------------------------- figures

def process_principle() -> None:
    """What one branch condition does to the chain, on one benchmark intervention.

    The pair differs by a single sentence. The curve is how many items the reference contract
    keeps live at each link: the true branch carries one obligation through to a request, and
    widens where two document routes can establish the same fact. A false condition carries
    nothing past the condition itself; an unresolved one carries a question instead.
    """
    benchmark = json.loads((BENCH / "benchmark" / "BENCHMARK_V3.json").read_text())
    pair = next(p for p in benchmark["pairs"]
                if p["scenario"] == "PR_scheduled_valuable_1000" and p["context_index"] == 0)
    requirements = pair["expected_added_requirements"]
    if len(requirements) != 1 or pair["expected_withdrawn"]:
        raise SystemExit("this figure assumes one added requirement and no withdrawal")
    routes = sum(len(r["acceptable_routes"]) for r in requirements)
    chain = ["Condition", "Obligation", "Fact", "Route", "Request"]
    n = len(requirements)
    # The question is an output, not a link, so it sits past a gap and no line crosses into it.
    x = [0, 1, 2, 3, 4, None, 5.6]
    live = {"true": [1, n, n, routes, n, None, 0],
            "false": [1, 0, 0, 0, 0, None, 0],
            "unresolved": [1, 0, 0, 0, 0, None, 1]}

    with plt.style.context(STYLE):
        fig, ax = plt.subplots(figsize=(TEXT * 0.86, TEXT * 0.86 * GOLDEN * 0.58))
        for state, marker in (("true", "o"), ("false", "s"), ("unresolved", "^")):
            ax.plot(x, live[state], marker=marker, label=state)
        ax.set_xticks([0, 1, 2, 3, 4, 5.6], chain + ["Question"])
        ax.set_yticks(range(routes + 1))
        # Headroom for a one-row legend, so it never sits on the data.
        ax.set(ylabel="Items the sources keep live", ylim=(-0.15, routes + 1.25),
               xlim=(-0.2, 5.8))
        ax.legend(title="Branch condition", loc="upper left", ncol=3)
        save(fig, "fig_process_principle.pdf")


def family_results() -> None:
    """Where the branch semantics holds and where it fails, concept by concept."""
    report = json.loads((HERE / "PAIRED_V5_REPRODUCED_RESULT.json").read_text())
    scores = report["scores"]
    rows = sorted(({"label": FAMILY[c], "casepath": v,
                    "others": [scores[k]["family_pair_f1"][c] for k, _ in COMPARATORS]}
                   for c, v in scores[CASEPATH]["family_pair_f1"].items()),
                  key=lambda r: (r["casepath"], -max(r["others"])))
    with plt.style.context(STYLE):
        plt.rcParams.update({"font.size": 9})
        fig, ax = plt.subplots(figsize=(TEXT, TEXT * 0.37))
        ax.plot([r["casepath"] for r in rows], range(len(rows)), marker="o", ls="none",
                label="CasePath", zorder=3)
        for index, (marker, (_, label)) in enumerate(zip(("s", "^", "v"), COMPARATORS)):
            ax.plot([r["others"][index] for r in rows], range(len(rows)), marker=marker,
                    ls="none", mfc="none", label=label, zorder=2)
        ax.set_yticks(range(len(rows)), [r["label"] for r in rows])
        ax.set(xlabel="Mean pair $F_1$ within the branch concept", xlim=(-0.04, 1.04),
               ylim=(-0.6, len(rows) - 0.4))
        ax.legend(title="Method", loc="lower left", bbox_to_anchor=(0.0, 1.0, 1.0, 0.1),
                  mode="expand", ncol=4)
        save(fig, "fig_family_results.pdf")


def scope_control() -> None:
    """What inherited scope buys, case by case: the same evidence, at a third of the demand."""
    rows = json.loads((HERE / "native150/ASSESSED_STATE_ROWS.json").read_text())
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

    with plt.style.context(STYLE):
        fig, ax = plt.subplots(figsize=(TEXT * 0.60, TEXT * 0.60 * GOLDEN * 0.80))
        ax.plot([0, top], [0, top], color="k", lw=0.5, zorder=1)
        cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]
        for (arm, marker, label), colour in zip(
                (("CASEPATH_CONTROL", "o", "Inherited scope"),
                 ("LOCAL_SCOPE_ABLATION", "s", "Local guard only")), cycle):
            xs, ys, sizes = zip(*[(x, y, 6 + 9 * n) for (x, y), n in sorted(points[arm].items())])
            ax.scatter(xs, ys, s=sizes, marker=marker, label=label, edgecolors=colour,
                       facecolors="none" if marker == "s" else colour,
                       zorder=3 if marker == "o" else 2)
        ax.set(xlabel="Documents requested on the case", ylabel="Requests with a valid chain",
               xlim=(0, top), ylim=(0, top))
        ax.legend(title="Obligation scope", loc="upper left")
        save(fig, "fig_scope_control.pdf")


def selectivity() -> None:
    """The dependency, and where each system's changes land on it."""
    pairs, rows, governed = held_out()
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
    with plt.style.context(GRID):
        plt.rcParams.update({"font.size": 7})
        fig, axes = plt.subplots(1, 3, figsize=(TEXT, TEXT * 0.58), sharey=True,
                                 gridspec_kw={"wspace": 0.08})
        for ax, (title, counts) in zip(axes, panels):
            ax.set_title(title)
            for sign, marker, colour in (("+", "o", None), ("-", "x", "k")):
                cells = [(c, d, n) for (c, d, s), n in sorted(counts.items()) if s == sign]
                if not cells:
                    continue
                offset = 0.16 if any(s == "-" for (_, _, s) in counts) else 0.0
                ax.scatter([column[c] + (offset if sign == "+" else -offset) for c, _, _ in cells],
                           [row[d] for _, d, _ in cells],
                           s=[5 + 7 * n for _, _, n in cells], marker=marker, color=colour,
                           label="added" if sign == "+" else "withdrawn", zorder=3)
            ax.set_xticks(range(len(order)), [CONCEPT[k] for k in order],
                          rotation=40, ha="right", rotation_mode="anchor")
            ax.set(xlim=(-0.7, len(order) - 0.3), ylim=(-0.7, len(ylabels) - 0.3))
            ax.minorticks_off()
        axes[0].set_yticks(range(len(ylabels)), list(reversed(ylabels)))
        axes[2].legend(title="Signed change", loc="upper right")
        save(fig, "fig_selectivity.pdf")


def falsifiers() -> None:
    """What the result survives, and what it does not."""
    null = json.loads((HERE / "WRONG_PAIRING_NULL.json").read_text())
    report = json.loads((HERE / "PAIRED_V5_REPRODUCED_RESULT.json").read_text())
    spectrum = sorted(Counter(null["null"]).items())
    with plt.style.context(STYLE):
        fig, (left, right) = plt.subplots(1, 2, figsize=(TEXT, TEXT * 0.34),
                                          gridspec_kw={"wspace": 0.62})
        left.bar([v for v, _ in spectrum], [n for _, n in spectrum], width=0.02,
                 label="wrong family")
        left.axvline(null["observed_micro_f1"], ls="--", label="correct family")
        left.set(xlabel="Micro $F_1$ after reassignment", ylabel="Reassignments",
                 xlim=(-0.05, 0.75))
        left.legend(title=f"{len(null['null']):,} assignments")

        ticks = []
        for y, (key, label) in enumerate(reversed(COMPARATORS)):
            test = report["family_swap_tests"][key]
            right.plot(sorted(test["family_differences"]), [y] * len(test["family_differences"]),
                       marker="o", ls="none", mfc="none")
            right.plot([test["observed_mean_difference"]], [y], marker="|", ms=10, color="k")
            ticks.append(f"{label.split()[0]}\n$p$ = {test['holm_adjusted_p']:.2f}")
        right.axvline(0, color="k", lw=0.5)
        right.set_yticks(range(len(COMPARATORS)), ticks)
        right.set(xlabel="$F_1$ difference per concept", xlim=(-1.1, 1.1),
                  ylim=(-0.6, len(COMPARATORS) - 0.4))
        right.minorticks_off()
        save(fig, "fig_falsifiers.pdf")


def error_origin() -> None:
    """The unjustified changes differ in kind: the comparators' never touch a governed branch."""
    data = json.loads((HERE / "SPURIOUS_ORIGIN.json").read_text())
    if data["reference_changes_by_direction"]["withdrawn"] != 0:
        raise SystemExit("this figure assumes the reference never withdraws a document")
    order = [(CASEPATH, "CasePath")] + COMPARATORS
    with plt.style.context(STYLE):
        fig, ax = plt.subplots(figsize=(TEXT * 0.82, TEXT * 0.82 * 0.42))
        ys = range(len(order))
        on = [data["arms"][k]["required_in_one_unit"] + data["arms"][k]["governed_elsewhere"]
              for k, _ in order]
        # Every withdrawal is unjustified: the reference contract only ever adds.
        off = [data["arms"][k]["added"] - o for (k, _), o in zip(order, on)]
        back = [-data["arms"][k]["withdrawn"] for k, _ in order]
        ax.barh(ys, on, height=0.6, label="added, on a governed branch")
        ax.barh(ys, off, left=on, height=0.6, label="added, on no branch")
        ax.barh(ys, back, height=0.6, label="withdrawn, never justified")
        ax.axvline(0, color="k", lw=0.5)
        ax.set_yticks(ys, [label for _, label in order])
        ax.set(xlabel="Unjustified signed changes on the held-out pairs",
               ylim=(-0.6, len(order) - 0.4))
        ax.invert_yaxis()
        # Four full-width bars leave no room inside, so the legend goes above them.
        ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2)
        save(fig, "fig_error_origin.pdf")


def recorded_case() -> None:
    """One recorded case: the chain either reaches a document or stops at an unresolved scope."""
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
    for request in requests:
        chain = request["chains"][0]
        if not all(chain[k] for k in ("scope_id", "obligation_id", "fact_id", "capability_id",
                                      "route_id", "document_id")):
            raise SystemExit(f"incomplete chain for {request['document_id']}")

    labels = [d.replace("_", " ") for d in held] + \
             [r["document_id"].replace("_", " ") for r in requests]
    with plt.style.context(STYLE):
        plt.rcParams.update({"font.size": 8})
        fig, ax = plt.subplots(figsize=(TEXT * 0.9, TEXT * 0.9 * 0.46))
        xs: list = []
        ys: list = []
        for i, _ in enumerate(requests):
            xs += list(range(len(stages))) + [None]
            ys += [len(held) + i] * len(stages) + [None]
        ax.plot(xs, ys, marker="o", label="requested now")
        ax.plot([0] * len(held), range(len(held)), marker="^", ls="none",
                label="held behind a question")
        ax.set_xticks(range(len(stages)), stages)
        ax.set_yticks(range(len(labels)), labels)
        ax.set(xlim=(-0.3, len(stages) - 0.7), ylim=(-0.7, len(labels) - 0.3))
        ax.legend(title="Controller decision", loc="lower right")
        save(fig, "fig_native_case.pdf")


# --------------------------------------------------------------------------- audit

def audit() -> None:
    style = ("SciencePlots science+no-latex, or science+grid+no-latex for the dot matrix. The "
             "style sets every colour, line width, tick and type size; a dense panel lowers "
             "font.size once inside the context so the whole type scale moves together. Nothing "
             "is drawn on the canvas but the data, the axes and one legend.")
    sources = {
        "fig_process_principle.pdf": (
            "branch-benchmark/benchmark/BENCHMARK_V3.json",
            "/pairs/[pair_id=theft-01-01]/{expected_added_requirements,expected_withdrawn}",
            "one frozen benchmark intervention: the added requirement and its acceptable routes "
            "are read from the reference contract; the three condition states are the method's "
            "semantics, not a measurement"),
        "fig_family_results.pdf": (
            "PAIRED_V5_REPRODUCED_RESULT.json", "/scores/*/family_pair_f1",
            "held-out Study A measurement"),
        "fig_scope_control.pdf": (
            "native150/ASSESSED_STATE_ROWS.json",
            "/*/native_counts/evidence/{requested_documents,valid_chain_documents}, protected "
            "split",
            "separate retrospective current-case scope intervention; restricted to the cases "
            "observed in both arms, which is two fewer than CasePath's own observed set"),
        "fig_selectivity.pdf": (
            ("branch-benchmark/benchmark/BENCHMARK_V3.json",
             "branch-benchmark/predictions/heldout/casepath.json",
             "branch-benchmark/predictions/heldout/comparators.json",
             "PAIRED_V5_REPRODUCED_RESULT.json"),
            "/pairs/*/acceptable_signed_deltas, /*/predicted_signed_delta, and "
            "/scores/b5_process_compiled/family_pair_f1 for the column order",
            "frozen reference contract and the preserved held-out predictions; the reference "
            "panel is what the sources justify, not a system output"),
        "fig_falsifiers.pdf": (
            ("WRONG_PAIRING_NULL.json", "PAIRED_V5_REPRODUCED_RESULT.json"),
            "/null, /observed_micro_f1, and /family_swap_tests/*",
            "preregistered falsifiers, including the family-swap contrast that does not reach "
            "significance"),
        "fig_error_origin.pdf": (
            "SPURIOUS_ORIGIN.json", "/arms/*, /reference_changes_by_direction",
            "descriptive partition of the held-out Study A spurious changes"),
        "fig_native_case.pdf": (
            "native150/RECORDED_CASE_TRACE.json", "/requests, /conditional_documents, /questions",
            "recorded development prediction; not a native acceptance claim"),
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
    family_results()
    scope_control()
    selectivity()
    falsifiers()
    error_origin()
    recorded_case()
    audit()
    print("wrote 7 SciencePlots figures and FIGURE_AUDIT.json")
