# NS3 — recorded checklist reuse

Base: approved NS2 `125af0f1e7c1d26e4c3c1d7d79e610cea57b33f2`.
Planner authority: PR #21 comments 6315405780 and 6317005838.

Earlier checklist opens a vertical process view and three connected cards:
the selected step's exact source, the reused checklist, and the recorded effect.
The connection requires the verified operation, its journal reuse receipt,
current workflow, exact version, definition and knowledge hashes. It cannot
borrow a different version's text. Documents, result, exact source and checklist
links open their existing views. Step choice survives reload and browser history.

The BEFORE and NOW excerpts come from earlier and later outcome.recorded events
for this same case. The scope is explicitly the whole case. Every one of the
nine histories has these two outcomes. Their legal-test IDs and statuses are
unchanged; the view says so. It shows their actual first sentences, with the
complete recorded summary on hover and the full result one click away. It does
not attribute the wording update to an expert or claim a changed legal decision.

The recorded reuse effect is three document checks reused, with this case's
facts reassessed. No reviewer edit or expert-review metadata exists in these
records. Those labels and shields are omitted. Missing evidence is not invented.
The W6 Knowledge page keeps its recorded checklist content and uses the shared
Mulish, white, grey and crimson navigation treatment.

## NS2 approval refinements

- dh_cause now reads “Is it outside the tenant’s responsibility?” as directed
  in 6317005838, superseding the previous glossary entry.
- Node checks require all linked tests to be supported and the step completed.
  A failed test produces a crimson cross; unresolved tests do not get a check.
  The selected node retains its ring. The Law column starts with each failed
  test's glossary label in crimson.
- Node boxes have equal heights. The local chain starts 28px below the row and
  has a 12px notch under the selected node. Freed space enlarges the source view.
- The source header stays visible; the text viewport is fitted to whole line
  heights and the selected passage scrolls to a line boundary. A source is named
  once per passage group. Source checker lists each verified pin once even when
  several operations checked it; all operations remain in History. Text zoom
  recalculates the fitted viewport.
- `forSeefeldstrasse`, `On2026…` and `toTaylor` are already present in the immutable
  case-4 source. Artifact: `src_92c11d41231a40d9f8e9b93661774e37`; text SHA:
  `e067ac002b3782f410b25c0c8ebe8732247b05a7f1bc5845aab2101d76ad4660`.
  They are preserved. The browser checks the complete preview against the original
  text after the expressly hidden header; no renderer whitespace is lost.

## Fidelity

Matched to 03: vertical numbered process, selected crimson ring/question,
dashed earlier-answer box and crimson current-answer box, three source/checklist/
effect cards with connecting arrows, subtle green recorded-effect cue, document
link and grey notice. Matched to the revised 02: equal nodes, selected notch,
failed-test label, grouped passages and larger exact source view.

Deliberate: case 1 has six steps and four source groups; case 4 has two steps.
Both answers are real recorded outcomes, and their legal tests are unchanged.
There are no expert-review shields, reviewer edits, invented missing items or
unsupported before/after decisions. Long exact quotations use a scrollable
excerpt with Open exact passage. The comparison is labelled as whole-case;
the source card is labelled for the selected step. Dates and email fields are
shown only when recorded. The existing wordmark remains. No Add source,
settings or decision-edit controls are introduced.

Pending: planner review and W8. NS4 is optional and requires recorded alternatives
and their consequences; the inspected nine DAGs contain no such alternatives.

No paid inference, original-nine rerun, hosted writes, merge or deployment.

## Validation

511 focused tests and 28 existing desktop browser checks pass. Both sealed
GET-only browser suites cover all nine cases. Memory checks exercise node
selection, same-case answers, source/checklist/result/document links and
reload/Back/Forward. Process checks cover every node, complete preview text,
whole-line clipping, equal heights and 28px chain gap, all five role views,
draft, reasoning, zoom and full source. Captured views have no box overlaps
or horizontal overflow; memory footer and source controls stay in-frame.
Served JS/CSS/Mulish match the committed bytes. No browser errors or writes.

The whole-case comparison remains separate from the selected-step source
chain: no node-level earlier decision or reviewer edit is recorded.
