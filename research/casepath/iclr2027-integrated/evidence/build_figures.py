#!/usr/bin/env python3
"""Rebuild the paper's four figures from preserved evidence.

Measurements come from the frozen Study A report and separately declared
Study B request-only diagnostic. The opening figure is a teaching schematic;
the recorded-case figure illustrates one selected development prediction.
Run: python3 evidence/build_figures.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                     "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
                     "svg.hashsalt": "casepath-paper"})

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
ACCENT = "#087f79"
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

    fig, ax = plt.subplots(figsize=(6.7, 3.35))
    ys = range(len(rows))
    for y, r in zip(ys, rows):
        for v, marker, offset in zip(r["others"], ("s", "^", "x"), (-0.20, 0.0, 0.20)):
            ax.plot([v], [y + offset], marker=marker, ms=4.7, mew=1.0,
                    markerfacecolor="white", color="#696965", zorder=2)
        ax.plot([r["casepath"]], [y], marker="o", ms=7.5, color=ACCENT,
                markeredgecolor="white", mew=1.0, zorder=3)

    ax.set_yticks(list(ys))
    ax.set_yticklabels([r["label"] for r in rows], fontsize=9, color=INK)
    ax.set_xlim(-0.04, 1.06)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticklabels(["0", "0.25", "0.50", "0.75", "1.0"], fontsize=9, color=INK)
    ax.set_xlabel("Mean pair $F_1$ within the branch concept, held-out contexts",
                  fontsize=9, color=INK)
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
    handles = [Line2D([], [], marker="o", ms=7, color=ACCENT, ls="none", label="CasePath")]
    handles += [Line2D([], [], marker=marker, ms=5, color="#696965", ls="none",
                       markerfacecolor="white", label=label)
                for (_, label), marker in zip(COMPARATORS, ("s", "^", "x"))]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(-0.45, 1.03, 1.45, 0.1),
              mode="expand", ncol=4, frameon=False, fontsize=8.5,
              handletextpad=0.35, borderaxespad=0.0)

    fig.tight_layout(pad=0.4)
    out = DOC / "fig_family_results.pdf"
    fig.savefig(out, format="pdf", bbox_inches="tight", pad_inches=0.02,
                metadata={"CreationDate": None})
    plt.close(fig)
    print(f"wrote {out.name}: {len(rows)} concepts, CasePath exact on {exact}, zero on {zero}")
    for r in rows:
        print(f"  {r['label']:<32} CasePath {r['casepath']:.3f}   comparators "
              f"{r['lo']:.3f}-{r['hi']:.3f}")


def principle() -> None:
    """Schematic of the submitted motivating example, not a benchmark measurement."""
    fig, ax = plt.subplots(figsize=(6.7, 2.15))
    ax.set(xlim=(0, 1), ylim=(0, 1))
    ax.axis("off")
    xs = [0.075, 0.275, 0.47, 0.665, 0.89]
    ax.text(0.0, 0.96, "Source rule: a scheduled valuable requires evidence of its value",
            fontsize=10, color=INK, weight="medium", va="top")
    headings = ["Case condition", "Obligation", "Required fact", "Evidence capability", "Document / action"]
    for x, label in zip(xs, headings):
        ax.text(x, 0.76, label, ha="center", fontsize=8.5, color="#60605c")
    ax.plot([0, 1], [0.70, 0.70], color=LIGHT, lw=0.7)
    entries = ["True", "Establish\nvalue", "Value of\nthe item", "Reliable\nvaluation", "Receipt or\nexpert valuation"]
    for x, label in zip(xs, entries):
        ax.text(x, 0.56, label, ha="center", va="center", fontsize=9,
                color=ACCENT, weight="medium")
    for a, b in zip(xs, xs[1:]):
        ax.annotate("", xy=(b - (0.100 if b == xs[-1] else 0.071), 0.56), xytext=(a + 0.071, 0.56),
                    arrowprops={"arrowstyle": "->", "color": ACCENT, "lw": 0.8})
    for y, state, obligation, action in [(0.32, "False", "Inactive", "No request on this branch"),
                                        (0.09, "Unresolved", "Unresolved", "Clarify whether the item is scheduled")]:
        ax.text(xs[0], y, state, ha="center", va="center", fontsize=9, color=INK)
        ax.text(xs[1], y, obligation, ha="center", va="center", fontsize=9, color=INK)
        ax.annotate("", xy=(xs[1] - 0.071, y), xytext=(xs[0] + 0.071, y),
                    arrowprops={"arrowstyle": "->", "color": MUTED, "lw": 0.7})
        ax.plot([0.39, 0.45], [y, y], color=MUTED, lw=0.8)
        ax.text(0.475, y, action, va="center", fontsize=9, color=INK)
    fig.subplots_adjust(left=0.015, right=0.995, top=0.99, bottom=0.04)
    fig.savefig(DOC / "fig_process_principle.pdf", metadata={"CreationDate": None})
    plt.close(fig)




def scope_effect() -> None:
    """Fixed-assessment scope intervention under the separate current-case contract."""
    report = json.loads((HERE / 'native150/ASSESSED_STATE_REPORT.json').read_text())
    splits = [('all150', 'All claims'), ('hidden_test', 'Protected families'), ('public_dev', 'Development')]
    fig, (left, right) = plt.subplots(1, 2, figsize=(6.7, 2.55), gridspec_kw={'width_ratios': [1, 1.1]})
    for y, (split, _) in enumerate(splits):
        arms = report['splits'][split]['arms']
        local = arms['LOCAL_SCOPE_ABLATION']['metrics']['valid_chain_precision']['value']
        full = arms['CASEPATH_CONTROL']['metrics']['valid_chain_precision']['value']
        left.plot([local, full], [y, y], color=LIGHT, lw=2)
        left.plot(local, y, marker='s', ms=6, color=MUTED, mfc='white')
        left.plot(full, y, marker='o', ms=7, color=ACCENT)
        left.text(local, y-.15, f'{local:.3f}', ha='center', va='top', fontsize=8, color=INK)
        left.text(full, y+.13, f'{full:.3f}', ha='center', va='bottom', fontsize=8, color=INK)
    left.set_title('Reference-chain precision', loc='left', fontsize=9.5, pad=26)
    left.set(xlim=(0,1), ylim=(-.45,2.5), xlabel='All scheduled claims, including failures')
    left.set_yticks(range(3), [label for _,label in splits], fontsize=8)
    left.set_xticks([0,.25,.5,.75,1],['0','.25','.50','.75','1'])
    left.legend(handles=[Line2D([],[],color=ACCENT,marker='o',ls='none',label='Full scope'),
                         Line2D([],[],color=MUTED,marker='s',mfc='white',ls='none',label='Local only')],
                loc='lower left',bbox_to_anchor=(-.03,1.0),ncol=2,frameon=False,fontsize=8,handletextpad=.3)
    dev = report['splits']['public_dev']['arms']
    for y, arm in [(1,'CASEPATH_CONTROL'),(0,'LOCAL_SCOPE_ABLATION')]:
        counts=dev[arm]['raw_native_counts']; valid=counts['evidence/valid_chain_documents']
        total=counts['evidence/requested_documents']; extra=total-valid
        right.barh(y,valid,height=.34,color=ACCENT)
        right.barh(y,extra,left=valid,height=.34,color=LIGHT)
        right.text(8,y,f'{valid} valid',ha='left',va='center',color='white',fontsize=8)
        right.text(valid+extra/2,y+.28,f'{extra} unjustified',ha='center',va='center',fontsize=8,color=INK)
    right.set_title('Same development cases and assessments',loc='left',fontsize=9.1,pad=26)
    right.set(xlim=(0,625),ylim=(-.45,1.8),xlabel='Active document requests')
    right.set_yticks([0,1],['Local only','Full scope'],fontsize=8)
    right.set_xticks([0,200,400,600])
    for ax in (left,right):
        ax.tick_params(length=0,pad=4,labelsize=8)
        ax.grid(axis='x',color=LIGHT,lw=.5);ax.set_axisbelow(True)
        for side in ('top','left','right'):ax.spines[side].set_visible(False)
        ax.spines['bottom'].set_color(LIGHT)
    fig.subplots_adjust(left=.18,right=.99,bottom=.2,top=.7,wspace=.5)
    fig.savefig(DOC/'fig_scope_control.pdf',metadata={'CreationDate':None},bbox_inches='tight',pad_inches=.02)
    plt.close(fig)


def recorded_case() -> None:
    """Two branches of a preselected actual development prediction."""
    evidence = json.loads((HERE / 'native150/RECORDED_CASE_STATES.json').read_text())
    assert evidence['guards']['arrears']['value'] is True
    assert evidence['guards']['family_home']['value'] is None
    assert evidence['documents']['payment_deadline_letter']['presence'] == 'missing'
    assert evidence['documents']['spouse_notice_copy']['presence'] == 'missing'
    assert 'payment_deadline_letter' in evidence['documents_now']
    assert 'spouse_notice_copy' in evidence['documents_conditional']
    fig, ax = plt.subplots(figsize=(6.7, 3.25))
    ax.set(xlim=(0, 1), ylim=(0, 1)); ax.axis('off')
    ax.text(0, .97, 'A missing document becomes a request only when its obligation is active',
            fontsize=10, color=INK, va='top', weight='medium')
    cols = [.31, .74]
    for x, heading in zip(cols, ['Arrears procedure', 'Family-home protection']):
        ax.text(x, .82, heading, ha='center', fontsize=9.5, color=INK, weight='medium')
    rows = [(.69, 'Case condition', 'Arrears: true', 'Family home: unresolved'),
            (.54, 'Obligation', 'Cure notice with warning', 'Separate spouse notice'),
            (.39, 'Evidence state', 'Notice missing', 'Notice missing'),
            (.24, 'Document plan', 'Request the cure notice', 'Keep spouse notice conditional')]
    for y, label, left, right in rows:
        ax.text(0, y, label, fontsize=8.5, color='#60605c', va='center')
        for x, value in zip(cols, [left, right]):
            ax.text(x, y, value, fontsize=9, ha='center', va='center',
                    color=ACCENT if x == cols[0] and y == .24 else INK)
    for x in cols:
        for a, b in ((.645, .585), (.495, .435), (.345, .285)):
            ax.annotate('', xy=(x, b), xytext=(x, a),
                        arrowprops={'arrowstyle': '->', 'lw': .7, 'color': MUTED})
    ax.plot([0, 1], [.13, .13], color=LIGHT, lw=.7)
    ax.text(0, .075, 'The recorded next action resolves applicability before acquisition.',
            fontsize=9, color=INK, va='center')
    fig.subplots_adjust(left=.01, right=.99, top=.99, bottom=.01)
    fig.savefig(DOC / 'fig_native_case.pdf', metadata={'CreationDate': None})
    plt.close(fig)


def audit() -> None:
    sources = {
        'fig_family_results.pdf': ('PAIRED_V5_REPRODUCED_RESULT.json', '/scores/*/family_pair_f1', 'held-out Study A measurement'),
        'fig_scope_control.pdf': ('native150/ASSESSED_STATE_REPORT.json', '/splits/*/arms/{CASEPATH_CONTROL,LOCAL_SCOPE_ABLATION}/{metrics,raw_native_counts}', 'separate retrospective current-case scope intervention'),
        'fig_native_case.pdf': ('native150/RECORDED_CASE_STATES.json', '/', 'recorded development prediction; not a native acceptance claim'),
        'fig_process_principle.pdf': (None, None, 'authored teaching schematic; no measured values'),
    }
    rows = []
    for name, (source, pointer, meaning) in sources.items():
        rows.append({'figure': name, 'sha256': hashlib.sha256((DOC/name).read_bytes()).hexdigest(),
                     'evidence_file': source, 'evidence_sha256': hashlib.sha256((HERE/source).read_bytes()).hexdigest() if source else None,
                     'json_pointer_pattern': pointer, 'scope': meaning})
    (HERE / 'FIGURE_AUDIT.json').write_text(json.dumps({'figures': rows}, indent=2) + '\n')


if __name__ == '__main__':
    main()
    principle()
    scope_effect()
    recorded_case()
    audit()
