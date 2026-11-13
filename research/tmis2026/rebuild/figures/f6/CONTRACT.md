# Figure 6: A rule changes (gate-1 draft)

## 1. Contract
**The reader should see that** after one edited rule line, code recomputes every stored checklist of the regime from the
stored readings with no model call and changes only the lines the edit reaches, while a prompt must read every file
again, **because** CasePath stores one reading per fact and the rules are data.

- Intervention: one line of `simple_theft_away.json`, police report `"optional": true` → `false` (AVB Ziff. 8 lit. f
  lets the insurer call for a police report; making it always required is an edit a claims organisation would plausibly
  make). No new fact. Edited copy in this folder; nothing under `study4/` changed.
- Prediction: only police-report lines of routed simple-theft-away files whose step is reached and whose report is not
  on file change, to request (or to hold where the step itself is held).
- Comparator: the reference recomputed from each file's design under the same two rule versions, same evaluator.
- Falsifier: a changed line on any other document, or a changed line in a theft-at-home file, or any model call.

## 2. Measured (left; `compute.py` → `f6_data.json`; theft, 56 files, clean arm, revision 3)
- Stored replay reproduces the stored plan in 46 of 46 routed files; designed replay equals `reference.json` on 421 of
  421 lines (checks in `f6_data.json`).
- Files whose checklist changed: **15 of 56**. Lines changed: **15 of 421** (all optional → request; all police report).
- Reference: 15 lines in 15 files should change (14 optional → request, 1 optional → hold).
- Changed as the reference: **14 of 15** changed lines (same new state).
- Collateral (changed, reference unchanged): **1 of 421** lines, on the edited document: the_fefc066e8269, police
  report on file but the stored finding was rejected by the source checker, so after the edit it is requested. Lines
  changed on any other document: **0**.
- Missed (reference changed, stored did not): **1**: the_d76f5df60f83, which the product did not route (no checklist).
  10 of 56 files (74 lines) were not routed and cannot change.
- Model calls: **0**. How known: `compute.py` imports no model client and opens no connection; it reads stored records
  (gzip JSON) and calls the pure function `workflows.evaluate`. The stored runs it reuses cost 581 calls once.

## 3. Formal / not yet measured (right, revision 2)
- **Formal**: a single prompt stores no per-fact reading, so after any edit it must read every file again: one call per
  file, **56 calls**, drawn as one blue dot per file at that file's matrix column; CasePath's call row is drawn empty
  ("0 calls"). One call per case-run confirmed in the cost-efficient model's ledger under `study4/baseline_check/runs/`.
- **Not yet measured**: the prompt's changed lines after this edit: the same files × lines matrix, same size and place,
  as a hatched sand frame.
- Planner's decision: re-read drift (`rerun_drift.json`, kept as data) belongs to Figure 7 and is not drawn here.

## 4. Two constructions
- **a (kept, `f6.svg`)**: workflow strip before/after with the one changed node; every file as a column of its
  checklist lines (catalogue order fixed, so the police-report row lines up across files); changed lines coloured by new
  state; the prompt side as 56 call dots against CasePath's empty call row, and the same matrix as a hatched frame. Gain: the reader sees
  where change lands (one row, one block) and where it does not (the other workflow, other rows). Distortion: tiny
  marks; workflow strip omits the two stop steps and the conditions of the last step's documents.
- **b (rejected, `f6_b_rejected.svg`)**: a before→after transition table of line states (counts). Gain: exact counts of
  every state. Distortion: loses which file and which document changed, and the graph; "only the reached lines" is not
  visible, only inferable. a is truer.

## 5. Calibration (images opened)
- `assets/calibration/e65934cc-flow.jpg` (sha256 2c8c92f8…7cd7e) and `assets/calibration/58b095f5-fip.png`
  (sha256 e6279162…74ea79).
- Transfer: Flow matching puts the computational budget beside the intermediate states in aligned rows, which here is
  the matched files grid beside the calls a prompt spends. FIP separates the space that changes from the one that must
  stay fixed: the edited row versus all other rows and the untouched workflow.

## 6. Encoding
| Mark | Meaning | Evidence |
|---|---|---|
| Strip, drawn once for both designs | the workflow before / after; diamond = fact decides, circle = step, square = document (solid required, dashed optional) | workflow JSON copies |
| Ink ring | the one edited node | diff of the copies (line 379) |
| Grid column | one file; dot = one checklist line, rows in fixed catalogue order | f6_data.json |
| Sand dot / sand ring | line unchanged / line of a file not routed (no checklist) | replay, stored plan |
| Teal square | changed to request, as the reference changes | replay vs reference |
| Teal square, rust ring | changed, should not | replay vs reference |
| Amber outline square | should change (to hold), did not | reference |
| Blue dot | one model call; dotted sand rule = no call | formal; ledger |
| Hatched sand frame | not yet measured | none |

## 7. Caption (≤ 45 words)
One line made the police report required. From stored readings, code recomputed all 56 checklists, no model call; only police-report lines changed. One extra request: a report on file, finding rejected; one missed hold: a file never routed. A prompt reads every file again.

Files: `f6.svg`, `f6.pdf`, `f6.png` (5.5 × 4.0 in), `f6.py`, `compute.py`, `rerun_drift.py`, `f6_data.json`,
`rerun_drift.json`, `simple_theft_away.before.json`, `simple_theft_away.after.json`.

## 8. Self-review (self-assessed, revision 2 after the planner's decisions)
Scores: insight 4, fidelity 5, intuition 4, hierarchy 4, originality 4, composition 4, annotation 4, aesthetics 4,
readiness 4, comprehensibility 4. Inspected at print size (5.5 × 3.6 in) and at 4× on the edited node.
- Weakest point: the matrix marks are small (0.046 in); the 15 teal squares read as one row, but the two exceptions
  depend on the legend and caption to be understood.
- The workflow strip omits the two stop steps and the conditions of the last step's documents (schematic).
- One edit in one regime is one instance, not the planned rule-change experiment (a set of edits).

## 9. A rule edit that adds a new fact (for the planner)
CasePath must then read that fact in every file whose type uses it: by default 3 readings per file (plus a requote
call where a quotation is not found). For a new fact in simple_theft_away that is 3 × 27 = 81 calls (21 routed + 6 not
routed), or 63 for the routed files only; a prompt needs 1 call per file it re-runs (27 to 56). So for a new fact
CasePath costs more calls than a prompt, each answering one fact; the zero-call claim holds only for edits that use
facts already read. Not checked: whether the tested commit can re-read a single fact without a full run.
