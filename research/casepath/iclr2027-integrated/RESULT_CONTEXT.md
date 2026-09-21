# CasePath — result context for the final authorship pass

Every number below is live in the manuscript as a generated macro traced to a preserved evidence
file. Nothing here is an estimate. Rewrite the presentation freely; do not restate a number from
memory, and do not assert anything in the "not supported" lists.

---

## The one idea the paper should leave behind

A document is required because an **active obligation** needs a **fact** that some **evidence
capability** can establish, and a **document route** can supply. Change the case fact and the
justified checklist changes with it. A predictor that maps case text to a document list cannot
represent that dependency, so it asks for the right-looking document for the wrong reason.

Chain: authoritative source → process node → obligation → required fact → evidence capability →
document route → justified next action. Three-valued: every source condition is true, false or
**unresolved**, and unresolved yields a question, never that branch's documents.

---

## Study A — branch interventions (the competitive result)

36 matched case pairs over 9 branch concepts, 4 neutral contexts each, from 197 exact passages of
Swiss insurance law and public household policies. Within a pair only one branch-defining sentence
changes. A reference contract authored from the sources before any system ran fixes the justified
signed changes. 9 development pairs; **27 held-out pairs read exactly once** after the method,
benchmark, analysis code and success criteria were hash-frozen.

Scored on the **signed change** between the two checklists, not either checklist alone.

| Method | Prec | Recall | F1 | Exact | Predicted | Spurious | Missed |
|---|---|---|---|---|---|---|---|
| **CasePath** | **0.615** | 0.727 | **0.667** | **12/27** | 39 | **15** | 9 |
| Direct | 0.481 | 0.758 | 0.588 | 9/27 | 52 | 27 | 8 |
| Graph as context | 0.431 | 0.939 | 0.590 | 4/27 | 72 | 41 | 2 |
| Evidence-first | 0.235 | 0.485 | 0.317 | 2/27 | 68 | 52 | 17 |

33 reference changes. All four arms share model, provider restriction, temperature 0, source
snapshot, catalogue and case texts. Matched on inputs, **not** on compute.

**Falsifiers, run before evaluation.** A leave-one-family-out constant predictor scores max
held-out micro-F1 **0.0**; the 9 target signatures are distinct. Holding CasePath's outputs fixed
and reassigning them to wrong branch families collapses F1 from 0.667 to at most **0.083** over
5,008 reassignments.

**The preregistered gate FAILS and this is reported.** F1 margins +0.078 and +0.076 fall short of
0.10; precision 0.615 short of 0.70; Holm-adjusted family-swap p = 0.797 / 0.797 / 0.129. Five of
eight conditions pass, three fail. The supported claim is **selectivity and traceability, not
statistical dominance**. State once; do not relitigate.

**Per-concept.** Exact on 4 concepts, zero on 2 (third-party causer, formal expert procedure).
Failures are systematic: alternative routes over-requested, conditions at wrong granularity,
adjacent guard activating the wrong confirmation document.

### Mechanism: the errors differ in kind, not only in count

A document is *branch-governed* if it appears in any unit's `gold_branch_documents` or any pair's
`acceptable_signed_deltas` (12 documents).

| Method | Spurious | governed, this pair | governed, elsewhere | not governed | added | withdrawn |
|---|---|---|---|---|---|---|
| CasePath | 15 | 3 | 3 | 9 | 15 | 0 |
| Direct | 27 | 0 | 0 | 27 | 16 | 11 |
| Graph as context | 41 | 0 | 0 | 41 | 18 | 23 |
| Evidence-first | 52 | 0 | 0 | 52 | 22 | 30 |

**All 120 comparator unjustified changes move documents no branch governs.** Between two cases
differing by one sentence, their checklists move documents that sentence cannot touch. CasePath
makes 9 such changes, not 27/41/52. All 33 justified changes are additions, so the comparators' 64
withdrawals are all unjustified.

**Not supported:** that the class disappears for CasePath (9 of 15 remain in it); that non-governed
documents are universally required baselines (untestable — no full per-unit reference checklist);
that zero withdrawals follow from monotonicity (the extractor changed >1 guard on **21 of 27**
pairs). One invariant *is* verified: no pair predicted a change without a changed guard.

---

## Study B — 150 complete tenancy claims

150 synthetic claims, 28 families, 3 domains. 60 development / 11 families; **90 protected / 17
disjoint families**. 5 learned arms share one compiled public representation, observable packet, 2
calls per cell, medium reasoning, 4,096 completion tokens, no tools, no resampling. 2 dependent
controls reuse CasePath's own assessments. 1,050 cells, all recorded. USD 89.66 total.

### The registered primary analysis failed

Every generated artefact failed native evaluation: the public compiler's condition names are not
bound in the native reference scenario. The frozen policy penalises all 1,050 cells; **0 of 12**
protected-split practical targets met; **zero** observable quality cells. State once, precisely,
without dressing it up. These zeros are policy penalties, not evidence that requested documents
were wrong.

### The scope intervention — the strongest Study B result

Retrospective, fixed-assessment, **no new inference**, dependent controls only (CasePath, compiled
equivalent, local-scope ablation). 66 of 90 protected cells observed; the 24 failures still carry
penalties. Requires each obligation to satisfy its **enclosing** process conditions, not only its
own local guard.

Protected families:

| | CasePath | Compiled equivalent | Local-scope ablation |
|---|---|---|---|
| valid-chain precision | **0.732** | 0.732 | **0.318** |
| required-node precision | 0.536 | 0.536 | 0.256 |
| required-node recall | 0.544 | 0.544 | 0.526 |
| critical-evidence recall | 0.645 | 0.645 | 0.627 |
| unnecessary fraction | 0.268 | 0.268 | 0.682 |
| total requests | **385** | 385 | **853** |
| valid requests | **384** | 384 | 376 |

**This is the paper's sharpest evidence.** The ablation issues 853 requests to recover 376 valid
ones; the full controller issues 385 to recover 384. Recall barely moves. **Inherited scope is not
a precision–recall trade: it withdraws demands no active obligation supported, and the supported
obligations survive.** Conservative paired benefit on chain precision +0.103 after penalties.

The **compiled equivalent matches CasePath exactly** on every metric — a negative control that
kills the obvious alternative reading that the benefit comes from storing a graph. It comes from
the semantics.

Development split repeats it: both controllers recover 259 valid requests at identical recall
(0.635) while total requests fall from 592 to 275.

### The request-only diagnostic (secondary)

Post-hoc, separately specified, scores literal request lists against original reference sets. 558
observed, 492 penalised. CasePath F1 0.677 vs 0.458 for the strongest comparator on protected
families. **But conservative contrasts are negative against all four learned alternatives** (vs
Process-context: conventional +0.219, conservative −0.673). Supports better realized output under
this budget; **does not** establish paired superiority. Keep secondary.

### The provenance-inheritance zero is an artifact, not a finding

`provenance_chain_inheritance_rate` = 0.000 in all three arms. A hit requires a produced
`SourceLocator` to equal a reference locator across **all twelve** fields including text offsets
and canonical hashes. The controller does emit provenance: 3,104 locator objects across 120
completed cells, all `locator_kind: json_pointer` into the structured policy artifact, text fields
null. 0 hits against 738 expectations, identical in three arms. It records differing source
granularity, not a failure to inherit. **Not supported:** that inheritance in fact succeeds.

### Integrity caveats that must survive any rewrite

The producer terminated without its complete I/O audit, so historical non-access to protected
targets is **not established retrospectively**; and the target containers have since been released,
so this corpus **cannot serve as newly hidden confirmation**. All 150 observable inputs were
inspected during product development. State once, in the main text.

---

## Hard constraints

1. **Title and abstract are locked** — already submitted. `submitted_frontmatter.tex`, verbatim.
   The abstract's headline is 15 false-positive changes vs at least 27, and evidence planning that
   is "selective, traceable, and auditable". Every section should serve that promise.
2. **Main text ≤ 9 pages.** References, appendices, ethics, reproducibility and AI-use statements
   are excluded. Currently exactly 9. Adding prose requires cutting prose.
3. **Anonymous.** No author, employer, agent or own-repository token in any source or in PDF
   metadata.
4. **Every reported number is a generated macro.** Editing a number in the `.tex` is not possible;
   regenerate via the `evidence/build_*.py` scripts. `verify_release.py` fails if any macro, table
   or figure does not reproduce byte for byte.
5. **Never assert anything in a "not supported" list above.** The two studies are never pooled:
   different populations, implementations and endpoints.
6. Studies A and B use different implementations. Study A's planner unions mapped routes and does
   not judge adequacy; Study B's controller adds acquisition permission and route sufficiency.

## Where things live

- `main.tex` → frontmatter, introduction, method, benchmark, paired_results, native_study, related,
  release, discussion, statements, appendix_studya, appendix_native
- Numbers: `numbers.tex`, `native_final_numbers.tex`, `assessed_state_numbers.tex`,
  `error_origin_numbers.tex`
- Figures: process principle (schematic), family results, scope control, native case
- Evidence: `evidence/` and `evidence/native150/`, each hash-pinned
- One-command check: `python3 research/casepath/verify_release.py` (11 checks, all passing)
