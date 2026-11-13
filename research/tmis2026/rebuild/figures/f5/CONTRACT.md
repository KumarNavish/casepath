# Figure 5: As cases get real (draft for gate 1)

## Contract
**The reader should see that** stored data measure each design's error at one point on each of the three axes
(files of 77 to 367 words, one catalogue of three claim types, one third of files with an open fact), and that the
planned ranges are empty, **because** the registered test (Study 4) has not run, so whether a design that reads
one fact at a time and decides in code holds its level where a single prompt does not is still unanswered.

- Intervention / prediction (for Study 4, not tested here): longer files, larger catalogues, more open facts; the
  thesis predicts CasePath's error stays flat while the strongest prompt's rises.
- Comparator: the same nine designs, the same measure (all deviations per file, so needless holds count).
- Falsifier (future): CasePath's error rising with any axis as fast as the strongest prompt's.
- Status: ink levels **measured** (`f5_data.json`, Study 3 sealed tenancy, `study3.Study.tenancy_rows` all_dev);
  dashed regions **not yet measured** (planned ranges from the brief and STUDY4_COSTED_PLAN.md).

## What was decided and why
- **Length terciles are measured but not drawn as lines.** The 96 claims sorted by length put 21 of the 24
  denied-event claims in the shortest tercile and none in the longest (composition in `f5_data.json`). Tercile lines
  fall steeply with length for the prompts (Rules in context 4.8 to 0.8) only because denials are short. A line
  would read as a length effect; it is a claim-kind effect. Values are kept in the JSON.
- **F2 share lines are not drawn.** `study3_feedback` F2 is E(q) = (1 - q) S + q O: linear by construction between
  two subgroup means, with O including denied events (not open facts). Drawn, it would look like a measured sweep.
  Leaving the panel at one measured value is truer.
- **Rules panel shows one measured value per design** (Study 3 gave every design one catalogue of 3 claim types).
  The planner's brief says "nothing measured" there; this is one point, not a slope. Planner to decide.
- Length here = words of message body plus attachment text: 77 to 367 (0 to 2 attachments). The draft paper's "77 to
  320 words" spans both regimes under another count; to be reconciled.

## Two constructions
- **a, tercile lines (rejected, `f5_a.png`).** Error at the median length of each tercile, joined. Gain: uses all
  measured length data. Distortion: a steep "length effect" that is the denied-event claims.
- **b, measured levels and empty frames (kept, `f5.png`).** Each design's error as one level over exactly the measured
  span (77 to 367 words; 3 types; 33%), inside the planned frame; the unmeasured part a dashed empty region. Gain: the
  amount answered is visible at a glance, and no slope is implied. Distortion: hides the (confounded) tercile values.

## Calibration (images opened)
- FIP (`58b095f5-fip.png`, e6279162...ea79): show where variation is allowed beside where it is fixed. Transfer:
  measured span beside the empty planned span on the same axis.
- Flow matching (`e65934cc-flow.jpg`, 2c8c92f8...cd7e): identical scales across small multiples. Transfer: one shared
  y-axis for all three panels.

## Encoding
| Element | Meaning | Evidence |
|---|---|---|
| y | all deviations per file (claim-run mean) | study3 all_dev |
| ink level, panel 1 | design's error, drawn over 77 to 367 words only | f5_data.json overall, length min/max |
| ink tick, panel 2 | same value at 3 claim types (the one catalogue) | harness/product/workflows/fresh-serial-sync |
| ink tick, panel 3 | same value at 32 of 96 files with an open fact | reference open_fact |
| line weight | CasePath heavy, strongest prompt medium, others thin (identity only) | |
| dashed ink outline | planned range of the registered test, not run: empty | brief, costed plan |
| sand leader | label to its level | |

## Caption (43 words)
Study 3 measures each design at one point on each axis: files of 77 to 367 words, one catalogue of three claim
types, a third of files with an open fact. The registered test's ranges (dashed) are empty; the question is
unanswered.

## Self-review (self-assessed)
Insight 3, fidelity 5, intuition 4, hierarchy 4, originality 3, composition 4, annotation 4, aesthetic 4,
readiness 4, comprehensibility 3 (not tested). Weighted about 77; status `needs_independent_review`.
Weakest point: the three panels repeat the same nine numbers; a reader may take the identical levels for three
measurements. The caption says it is one measurement.

Palette: brief values with the coordinator's change of 2026-11-13 (request now #008571, reading blue #4A8FD6), in `../f4/theme.py`.

## Revision 1 (supersedes the above where they differ)
- Designs and order follow Figure 4's two model blocks (CasePath core in place of the full product). Overall error
  per file: core (c) 0.733, prompt that may hold (c) 0.889, Model executes rules (c) 1.493, Rules in context (c) 2.330,
  self-consistency 2.312, ReAct 2.003; core (f) 0.698, prompt that may hold (f) 0.583, Model executes rules (f) 0.542,
  Rules in context (f) 2.087.
- Length panel: short marks at the median length (172 words), as in the other panels, plus one thin bracket on the
  axis for the measured span 77 to 367 words (message plus attachments). No line across length.
- Direct labels only for CasePath core (c) and the strongest prompt (prompt that may hold, frontier); one shared label
  for the other eight. "Not yet measured" labels padded off the frames.
- Teal is not used in this figure; the chroma-floor warning for #008571 is recorded in f4/CONTRACT.md.

### Caption (43 words)
Study 3 measures each design at one point per axis: 77 to 367 words (message plus attachments; bracket), one
catalogue of three claim types, a third of files with an open fact. The registered test's ranges (dashed) are empty:
the question is unanswered.

## Revision 2 (redrawn from scratch; r1 kept as f5_r1.*, f5_plot_r1.py)
- Three panels, cost-efficient model, two designs: CasePath (core, 0.733 errors per file) and the prompt that may hold
  (0.889). Solid dot = the one measured value at its true x (median length 172 words, message plus attachments; one
  regime; 33% of files with an open fact). Dashed arrow = the predicted direction (CasePath level, prompt upward), one
  length and one angle in every panel, no value. x ticks only at the planned levels (330, 800, 2,500 words; 1, 3, 4
  regimes; 0, 10, 25, 50%). No frames, no "not yet measured" text.
- Two constructions: a, dot + dashed arrow (kept); b, dots alone (`f5_b.png`; rejected: the hypothesis then lives
  only in the caption and the panels look like a finished result at one point).
- Risk recorded: an arrow's slope can be read as a predicted size. Alternative if the cold reader does so: replace each
  arrow by a small direction glyph beside the dot ("→" / "↗") with no length.
- Inside the figure: 15 words (titles 7, y label 3, two labels 5); legend 2 entries.
- Caption (42 words): Each design has one measured point today (dot): Study 3's short files (median 172 words), one
  regime's rules, a third of files with an open fact. Arrows show what the registered test predicts, not data:
  CasePath level, the prompt rising. Cost-efficient model.
