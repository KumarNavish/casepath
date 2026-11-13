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
