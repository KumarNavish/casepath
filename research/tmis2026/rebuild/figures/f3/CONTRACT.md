# Figure 3: Why "open" needs its own value (gate-1 draft)

## 1. Contract
**The reader should see that** a reading that may only say true or false must send the case down one branch, and so
either asks for the police consent too early (true) or drops it (false), while the value "open" lets code request the
list of stolen items, which both branches need after they rejoin, and hold only the police consent, with one question,
**because** the two branches of "traces altered?" meet again before the list is needed.

- Intervention and predicted change: change the reading of one fact (traces_changed) from true to false to open, with
  every other fact fixed. Only the police-consent line moves (too early → dropped → held with one question); the
  list-of-stolen-items line stays "requested now" in all three.
- Comparator: the same fragment, same file, same evaluator, under the two two-valued readings.
- Falsifier: if the product's evaluator, given the open fact, held the list of stolen items (as plain strong Kleene
  evaluation does after a rejoin, Proposition 2 in s3_rule.tex) or asked more than one question, the figure is false.
  Checked: it requests the list and waits for exactly one fact (`f3_data.json`, `waiting_for: [traces_changed]`).
- Status: **formal** (follows from the definitions; computed by the product's own `workflows.evaluate`, worktree
  `/home/user/work/casepath-sync-e`, read-only) on a **real** instance:
  - workflow: `study4/rules/theft/workflow/simple_theft_away.json` (revision 3), steps a_police → {a_traces | direct} →
    a_instruction_check → a_loss; a_instruction (no document) is contracted into the a_instruction_check → a_loss edge
    (**schematic simplification**).
  - file: `study4/dev/theft/final/the_12ee892d56f4` (development file; design leaves traces_changed open). The German
    sentence is quoted verbatim from its `text.txt`; the stored revision-3 run (`study4/lint/runs/`, clean_rev3) has all
    three readings answer open quoting exactly this sentence (**measured**, `f3_data.json: stored_run_traces_changed`).
  - Evaluation uses the file's designed facts, no document on file. Documents not needed for this file (original
    vouchers, bicycle voucher: vouchers unobtainable is stated) and before the fork (notification record, insurance
    policy: requested in all three; police report: optional) are left out to keep the fragment small.
  - The "open" column is the product's exact deferral (≤ 8 open facts), not plain strong Kleene evaluation.

## 2. Two constructions
- **a (kept, `f3.svg`)**: three matched columns, same graph geometry, one reading each. The path each reading walks is
  drawn (ink = taken, amber dashed = depends on the open fact, sand = not taken) and the document lines sit on the steps
  that need them. Gain: the reader sees *why* the line changes (which branch is walked, and that the branches rejoin
  before the list). Distortion: repeats the graph three times; the contracted a_instruction step is not shown.
- **b (rejected, `f3_b_rejected.svg`)**: the fragment once, neutral, beside a 2 × 3 matrix of checklist lines.
  Gain: compact, line-by-line comparison. Distortion: the mechanism (branch walked, rejoin) is not visible per
  reading; the reader must infer why "open" still requests the list. Hides the cause, so a is truer.

## 3. Calibration (images opened)
- `assets/calibration/58b095f5-fip.png` (sha256 e6279162…74ea79) and `assets/calibration/genomnimatte-figure.png`
  (sha256 e90b87bb…7e8f5f).
- Transfer: FIP's panel b keeps the network identical and colours only the perturbed part; here the graph is identical in
  three columns and only the fact's value and its consequences carry colour. Genomnimatte's matched rows with one
  intervention per column give the left-to-right counterfactual reading. Not copied: perspective layers, photographs.

## 4. Encoding
| Mark | Meaning | Evidence / status |
|---|---|---|
| Diamond | step whose next step depends on a fact (traces_changed) | workflow JSON, a_police |
| Filled / hollow dot in diamond | fact read true / false (form, not colour) | brief |
| Amber diamond with "?" | fact left open | stored run: 3 of 3 readings open |
| Small ink circle | step | workflow JSON |
| Ink solid arrow | path walked | evaluator `reached` |
| Amber dashed arrow | path whose walk depends on the open fact | evaluator `beyond: pending` |
| Sand thin arrow | path not walked | evaluator |
| Teal chip | requested now | evaluator `required: yes`, status missing |
| Amber chip + "1 question" | held, waiting for one fact | evaluator `required: depends`, `waiting_for` |
| Rust chip | requested although its condition is open (too early) | true-reading request vs open-reading hold |
| Indigo dashed chip | dropped: neither asked nor held | false-reading absence vs open-reading hold |
| Blue italic | the file's words as the readings quoted them | text.txt; stored readings |
| Sand vertical rules | column separators | none |

## 5. Caption (≤ 45 words)
One file, read three ways (diamond filled: true; hollow: false; amber: open). Read as true, the police consent is asked too early; as false, it is dropped. Kept open, code requests the stolen-items list, needed after the branches rejoin, and holds only the consent.


Files: `f3.svg`, `f3.pdf`, `f3.png` (5.5 × 3.0 in, 300 dpi), `f3.py`, `compute.py` (needs the lint venv), `f3_data.json`.

## 6. Self-review (self-assessed, not a cold read)
Scores 1–5: insight 4, fidelity 4, intuition 4, hierarchy 4, originality 3, composition 4, annotation 4, aesthetics 4,
readiness 4, comprehensibility 4 (self-assessed). Inspected at print size and 4× on the rejoin of the open column.
- Weakest point: "too early" and "dropped" are judged against the open reading, not against a truth the file does not
  give; a reader could ask "too early relative to what?". The legend word carries this; the caption must say it.
- Second: the rejoin step itself is an unlabelled circle; the claim needs the eye to notice that both amber paths land
  on it before the solid edge. Consider a tiny "rejoin" mark if the cold reader misses it.
- Palette: the validator (dataviz `validate_palette.js`, light) failed teal #1F7A6D (chroma floor) and model blue
  #2F5D9E vs indigo #4B4A9C (ΔE 5.7). Moved the step, kept the hue: teal **#008571**, model blue **#4A8FD6**; then all
  checks pass (amber keeps the advised relief: it always carries a direct label).

## Revision 2 (house style, coordinator 2026-11-13)
Redrawn with `common/style.py`: white ground, one label size (7.5 pt), document lines as the shared checklist mark
(enlarged to 0.124 in), dropped now filled indigo as in Figure 4, sand dividers removed. Words inside apart from the
quoted sentence and its translation: 15 (labels on the first column only); legend: 5 entries (requested; held, one
question; too early; dropped; taken / open). "Not taken" sand paths are left undefined as background; fact true/false
and diamond/circle are defined in the caption. Construction b stays as drawn by `f3_draft1.py`. Inspected at print
size and 4x on the rejoin.
