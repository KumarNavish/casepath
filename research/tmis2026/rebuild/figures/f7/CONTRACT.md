# Figure 7: The price (draft for gate 1)

## Contract
**The reader should see that** on Study 3's tenancy claims the full product costs about 20 times the same-model
prompt and twice the frontier prompt that may hold, which has fewer deviations; that its checklist-only core costs
4 times the prompt for the same error; and how often the same file gives the same checklist again, **because** a lower
error that costs many times more, or changes from run to run, is not useful.

- Intervention / prediction: more readings or samples per file. Self-consistency 1 to 15 samples: cost x15, error
  2.33 to 2.28 (flat). CasePath core 1 to 3 readings: cost x1.2, all deviations 0.55 to 0.74 (rises: disagreeing
  readings add needless holds; strict errors fall 0.52 to 0.34, not drawn).
- Comparator: same 96 claims, same measure, cost from ledgers.
- Falsifier: CasePath on the lower-left frontier. It is not: on all deviations the frontier prompt that may hold
  (0.58, USD 0.0063) and frontier Model executes rules (0.54, 0.0062) lie below and left of the full product (0.73, 0.0134).
- Status: all marks **measured** (`f7_data.json`). Ten runs: **not yet measured** (Study 4).

## Sources
Error: `study3.Study.tenancy_rows` all_dev (checked equal to the registered value for Study 3 designs). Cost: Study 3
designs from `analysis/study3_results_fresh2_confirm.json` (ledger join over stored call keys, a cached call at its
first paid cost); fair-prompt designs from `study4/baseline_check/runs/ledger_*.jsonl` (method A/B, fresh2, tenancy
claim ids, each key once, over 96 x runs). Budget curves: `analysis/study3_feedback.json` F4 (post hoc). Repeat:
designs with 3 stored runs; a checklist line per document (request / hold / neither) plus "handed over".

## Two constructions
- **a, scatter + repeat dots (kept, `f7.png`).** Gain: error against cost reads as one trade-off; budget curves show
  what more spending buys. Distortion: log cost compresses the 20x gap; label placement is manual.
- **b, aligned rows (rejected, `f7_b.png`).** Four dot columns per design. Gain: same order as f4 and f5. Distortion:
  auto-limited axes exaggerate small gaps; error and cost no longer read together.

## Calibration (images opened)
- Flow matching (`e65934cc-flow.jpg`, 2c8c92f8...cd7e): put the work beside its computational cost. Transfer: the
  budget curves (samples, readings) beside the single-run marks.
- FIP (`58b095f5-fip.png`, e6279162...ea79): the changing space beside the fixed one. Transfer: the run-again panel
  beside the cost panel.

## Encoding
| Element | Meaning | Evidence |
|---|---|---|
| x (left) | USD per file, log | ledgers |
| y (left) | all deviations per file | study3 all_dev |
| circle / square | cost-efficient / frontier model | |
| large mark, bold label | the product (full, core) | |
| thin ink line with dots | stored budget curve (F4): self-consistency m = 1..15; CasePath core k = 1..3 readings | study3_feedback F4 |
| right, dot 1 | share of 96 claims with an identical checklist in runs 0, 1, 2 | f7_data repeat |
| right, dot 2 | mean differing lines between two runs | f7_data repeat |
| sand stem | from zero to the dot | |

## Caption (44 words)
On Study 3's tenancy claims the full product costs 20 times the same-model prompt and twice the frontier prompt
that may hold, which errs less; its core costs 4 times. Run again, CasePath repeats 72% of checklists exactly. Three
runs, not ten.

## Self-review (self-assessed)
Insight 4, fidelity 4, intuition 4, hierarchy 3, originality 3, composition 3, annotation 4, aesthetic 3,
readiness 4, comprehensibility 3 (not tested). Weighted about 72; status `needs_revision`.
Weakest point: tenancy only (theft's error is a different measure); the scatter's lower cluster is crowded and its
labels needed a leader.

Palette: brief values with the coordinator's change of 2026-11-13 (request now #008571, reading blue #4A8FD6), in `../f4/theme.py`.
Lines differing as a share of a claim's checklist lines (11.7 on average): CasePath full 5.7%, core 5.0%, prompt that may hold (c) 7.7%, Rules in context (c) 7.9%, (f) 4.6%, self-consistency 4.1%, Model executes rules (c) 9.7%, ReAct 16.3%. No large gap.

## Revision 1 (supersedes the above where they differ)
- Designs in Figure 4's order, plus the registered full product. Weight marks the two designs to find first (CasePath
  core; prompt that may hold): bold label, larger mark; no colour.
- Labels: no collisions at print size or 4x; the lower cluster's labels sit at fixed data positions with sand leaders.
- Readings path labelled at its ends ("1 reading", "3"): one reading 0.545 deviations at USD 0.00244; three 0.736 at
  0.00296 (= the stored core).
- Right panel rows in Figure 4's cost-efficient order, then Rules in context (f) and CasePath full (c), the other two
  designs with three stored runs. Axes: "same checklist in 3 runs, %" and "lines that differ between 2 runs, %"
  (share of a claim's 11.7 checklist lines). Values: core 73% / 5.0%; prompt that may hold (c) 58% / 7.7%; Model
  executes rules (c) 50% / 9.7%; Rules in context (c) 50% / 7.9%; self-consistency 66% / 4.1%; ReAct 34% / 16.3%;
  Rules in context (f) 81% / 4.6%; CasePath full 72% / 5.7%.
- Teal is not used in this figure; the chroma-floor warning for #008571 is recorded in f4/CONTRACT.md.

### Caption (45 words)
On Study 3's claims CasePath's core costs four times the same-model prompt that may hold, with fewer
deviations; the frontier prompt errs less at twice the cost. One reading errs less than three. Run again, 5 to 8% of
lines change; three runs, not ten.

## Revision 2 (redrawn from scratch; r1 kept as f7_r1.*, f7_plot_r1.py)
- Left: four points, CasePath (core) and the prompt that may hold per model (circle cost-efficient, square
  frontier), log USD per file, errors per file (all deviations) from 0. Arrow per model from the prompt to CasePath.
  Cost-efficient: USD 0.00067, 0.889 to USD 0.00296, 0.733 (4.4 times the cost, 0.16 fewer errors). Frontier: USD
  0.00632, 0.583 to USD 0.0214, 0.698 (3.4 times, 0.12 more errors).
- Right: the 96 claims as a 4 x 24 grid per design, cost-efficient model, claim-id order (same claim, same place in
  both grids); ink filled = same checklist in all three stored runs, ink outline = not. CasePath 70/96, prompt that
  may hold 56/96.
- Two constructions: a, grids (kept); b, three stored checklists of the median file as strips (`f7_b.png`). Rule:
  the claim whose mean differing lines over the three run pairs is closest to the design's median (ties: first claim
  id). The median is 0 for both designs (claim f2cl_03fdd7ee632bb267), so the strips are identical: true for the
  median, but it hides the 26 and 40 claims that change. Rejected.
- Inside the figure: 13 words (axis labels 6, models 2, design names 5) and 2 counts; no legend.
- Caption (45 words): Arrows lead from the prompt that may hold to CasePath: on the cost-efficient model 4.4 times the
  cost buys 0.16 fewer errors per file; on the frontier model 3.4 times buys 0.12 more. Run three times, CasePath
  repeats 70 of 96 checklists, the prompt 56.
