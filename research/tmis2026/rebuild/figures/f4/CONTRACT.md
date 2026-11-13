# Figure 4: The fate of 100 open facts (draft for gate 1)

## Contract
**The reader should see that** of 100 requests whose need hangs on a fact the file leaves open, CasePath and the
prompts told they may hold keep about 97 waiting with a question, while the Study 3 prompts ask for half or more too
early; and that CasePath pays with holds the file does not need (mostly where the claim denies its defining event),
**because** a hold is the right fate only where the need depends on the open fact, so the partner panel must
show what each design does where the file settles the need.

- Intervention / prediction: give a design an explicit hold value. Prediction: the "too early" (rust) block shrinks
  to a few marks. Observed: Rules in context 50 to 65 too early, the prompt that may hold 2 to 2.3, CasePath 2.7.
- Comparator: the same 86 open-dependent and 481 settled documents, the same scorer, for every design.
- Falsifier: CasePath's rust block as large as a prompt's, or a needless-hold block it hides. Neither is the case. But
  the figure does **not** separate CasePath from the strongest prompt on open facts (97.3 against 97.7 held).
- Status: every mark is **measured** (`f4_data.json`, from `analysis/study3.py` rows checked line by line against
  `study2.ten_row`). Grouping into 5 x 20 grids and largest-remainder rounding are **formal**. Question dots:
  **measured** for CasePath only (questions are fact ids: the open-fact id is in `plan.questions` in 251 of 251
  held document-runs). Free-text questions of the other designs are **not yet measured** (no registered scorer).

Unit: one document of one claim-run. Runs pooled: CasePath, Rules in context (both models), self-consistency,
Model executes rules (cost-efficient), ReAct and the cost-efficient prompt that may hold have 3 runs (258 open / 1,443
settled document-runs); the frontier prompt that may hold and frontier Model executes rules have 1 run (86 / 481).
The 86 open-dependent documents come from 32 claims in 3 families: 63 from 9 claims whose defining event is open, 23
from 23 claims with an open branch fact. A failed output is an empty plan (registered rule).

## Two constructions
- **a, unit picture (kept, `f4.png`).** 100 marks per design and panel, coloured by fate; a third sand-outlined box
  holds the extra actions on documents the file does not need, on the same per-100-settled scale. Gain: the whole is
  visible, so a reader sees that errors are rare for three designs and frequent for the rest, and that CasePath's
  partner cost sits in the third box. Distortion: 100 marks suggest 100 independent documents (they are 86 documents
  in 32 claims, mostly 9 claims); rounding moves a mark (97.3 becomes 97).
- **b, aligned error bars (rejected, `f4_b.png`).** Errors only, per 100, on a common zero, one axis per panel. Gain:
  exact values. Distortion: three different x-scales make 3 settled errors look like 30 open ones, and the right
  share disappears from view. a is truer: one unit for all panels, nothing hidden.

## Calibration (images opened)
- Flow matching (`assets/calibration/e65934cc-flow.jpg`, sha256 2c8c92f8...cd7e): matched rows with identical
  columns, so a row-to-row difference is the only thing that moves. Transfer: one row per design, identical grids.
- FIP (`assets/calibration/58b095f5-fip.png`, sha256 e6279162...ea79): separate the space that changes from the one
  that must stay fixed. Transfer: open (where a hold is right) beside settled (where a hold is an error).
- Not copied: density imagery, 3D surfaces.

## Encoding
| Element | Meaning | Evidence |
|---|---|---|
| row | one design and model, order: product; strongest prompt; others (same in f5, f7) | DESIGNS in f4_data.py |
| grid 1 (5 x 20) | 100 document-runs whose reference is "hold" | ten_row correct_hold / premature / silent_skip / handed_held |
| grid 2 | 100 whose reference is "request now" | requested / held_req / missed / handed |
| sand box | documents the reference does not need; marks = extra actions per 100 settled | spurious_hold, unnecessary |
| amber | held | brief state colour |
| teal | requested now | brief |
| rust | requested too early (grid 1) or not needed (box) | brief; extension to "not needed" flagged to planner |
| indigo | dropped: neither requested nor held | brief |
| ink square | whole claim handed to a person | product deferrals only |
| ink dot in amber | its question names the open fact | CasePath only |
| gap between rows 1, 2, 3 | grouping (product / strongest prompt / others), no quantity | |

## Caption (44 words)
Of 100 requests whose need hangs on an open fact, CasePath and the prompts told they may hold keep about 97 waiting
with a question; earlier prompts ask for half too early. CasePath's price: holds where the file needs nothing, mostly
when the claim denies its event.

## Self-review (self-assessed, not a reader test)
Insight 4, fidelity 4, intuition 4, hierarchy 4, originality 3, composition 4, annotation 3, aesthetic 4,
readiness 4, comprehensibility 3 (not tested). Weighted about 76: below the method's bar; status `needs_independent_review`.
Weakest point: the 100 open-dependent marks rest on 86 documents from 32 claims (63 from 9 claims); the unit picture
looks more general than that. Second: the free-text questions of the prompts are not scored, so the dot appears only
for CasePath.

Palette: brief values with the coordinator's change of 2026-11-13 (request now #008571, reading blue #4A8FD6), in `../f4/theme.py`.
