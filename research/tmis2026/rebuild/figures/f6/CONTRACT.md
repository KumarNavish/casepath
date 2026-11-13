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

## 3. Formal / not yet measured / measured (right)
- **Formal**: a single prompt stores no per-fact reading, so after any edit it must read every file again: one call per
  file, **56 calls** (one call per case-run confirmed in the cost-efficient model's ledger under `study4/baseline_check/runs/`: 672 calls
  for 224 cases × 3 runs).
- **Not yet measured**: the prompt's exact and collateral changes after this edit (hatched empty box).
- **Measured, labelled for what it is** (`rerun_drift.py` → `rerun_drift.json`; Study 3 fresh2 files, stored runs, same
  file, same rules, no edit): share of checklist lines that differ between two runs.
  Prompt that may hold, theft: 829 of 12,672 line comparisons (6.5 %; 341 of 384 run pairs differ); tenancy 258 of
  3,072 (8.4 %). CasePath itself, if it reads again: theft 748 of 12,672 (5.9 %), tenancy 187 of 3,072 (6.1 %). Shown
  beside them: CasePath's collateral under the edit, 1 of 421 (0.2 %, Study 4 dev files: different files, not matched).
  CasePath's re-read drift is drawn so the figure does not imply that CasePath's readings are stable; the gain comes from
  not reading again.

## 4. Two constructions
- **a (kept, `f6.svg`)**: workflow strip before/after with the one changed node; every file as a column of its
  checklist lines (catalogue order fixed, so the police-report row lines up across files); changed lines coloured by new
  state; the prompt panel as 56 call dots, a hatched empty box, and the measured re-read drift. Gain: the reader sees
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
| Diamond / circle / square in strip | fact decides / step / document (solid required, dashed optional) | workflow JSON copies |
| Grid column | one file; dot = one checklist line, rows in fixed catalogue order | f6_data.json |
| Sand dot | line unchanged | replay |
| Sand ring | line of a file the product did not route (no checklist) | stored plan |
| Teal square | changed to request, as the reference changes | replay vs reference |
| Teal square, rust ring | changed though the reference does not (collateral) | replay vs reference |
| Amber outline square | should have become a hold, did not | reference |
| Brackets | file groups by type and routing | design, stored plan |
| Blue dot | one model call | formal; ledger |
| Hatched box | not yet measured | none |
| Bar length | share of lines changed that no rule asked for, linear, 7 % = 1.3 in | rerun_drift.json, f6_data.json |
| Blue filled / hollow bar | prompt / CasePath reading again (model readings) | rerun_drift.json |
| Ink bar | CasePath after the edit (code only) | f6_data.json |

## 7. Caption (≤ 45 words)
One rule line made the police report required. From stored readings, code recomputed all 56 theft checklists with no
model call: 15 lines changed, all police reports; 14 as the edited rule requires. A prompt must read all 56 files again;
what that changes is not yet measured.

Files: `f6.svg`, `f6.pdf`, `f6.png` (5.5 × 4.0 in), `f6.py`, `compute.py`, `rerun_drift.py`, `f6_data.json`,
`rerun_drift.json`, `simple_theft_away.before.json`, `simple_theft_away.after.json`.

## 8. Self-review (self-assessed)
Scores: insight 4, fidelity 4, intuition 3, hierarchy 3, originality 4, composition 3, annotation 4, aesthetics 3,
readiness 4, comprehensibility 3.
- Weakest point: the right-hand bars mix file sets (Study 3 re-reads versus Study 4 edit) and the reader can take the
  0.2 % against 6.5 % as a matched contrast. It is not; the footnote says so, but the bar layout invites it. Option for
  the planner: drop the ink bar and keep only the two re-read bars.
- Size 5.5 × 4.0 in (within 4.2 in). Text is heavier than the house rule wants (the legend carries the
  counts); a cold reader may need it, so it stays for now.
- One edit on one regime is one instance, not the rule-change experiment (a set of edits); it must not be read as that.

## 9. A rule edit that adds a new fact (for the planner)
CasePath must then read that fact in every file whose type uses it: by default 3 readings per file (plus a requote
call where a quotation is not found). For a new fact in simple_theft_away that is 3 × 27 = 81 calls (21 routed + 6 not
routed), or 63 for the routed files only; a prompt needs 1 call per file it re-runs (27 to 56). So for a new fact
CasePath costs more calls than a prompt, each answering one fact; the zero-call claim holds only for edits that use
facts already read. Not checked: whether the tested commit can re-read a single fact without a full run.
