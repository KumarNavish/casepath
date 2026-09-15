# Writer-swap of the decisive split — pre-registration

Written while the swapped episodes were still being generated and before any arm was run on them.

## 1. Why

The most attackable choice in this work is that the evaluated model wrote its own benchmark episodes. The
existing control covers thirteen families and only two of the three domains, because the second writer was
stopped part-way through an alphabetical queue. That weakness is disclosed in the paper, and this run
removes it for the split that carries the primary result.

## 2. The design

The **identical twenty-one latent specifications** of the decisive split, all forty-two episodes, rewritten
from the same paragraph briefs by `anthropic/claude-sonnet-5`. The latents, the gold labels, the evaluator,
the arms and the analysis are untouched; only the prose differs. Gold never depends on wording.

Arms: the zero-model controls plus `direct-end-to-end`, `full`, `ctes` and `ctes-abl-satisfaction`. The
last is included because it is the rule the decisive split showed to be load-bearing, so the swap tests the
attribution as well as the headline. `openai/gpt-5.4-mini` remains the arm model, at temperature 0, three
turns, two requests per turn, no retries.

## 3. Hypotheses, fixed in advance

- **D5 (primary).** On the swapped episodes, `state_accuracy(ctes) − state_accuracy(full)` is positive with
  a family-paired 95% interval excluding zero.
  *Confirmed* if both hold.
- **D6 (agreement).** The D5 point estimate lies inside the decisive split's own interval, [+0.095, +0.205].
  *Confirmed* if it does. This is the stronger and more falsifiable of the two: a writer effect large enough
  to matter would move the estimate outside a window this narrow.
- **D7 (attribution holds).** `ctes-abl-satisfaction` records more premature-readiness episodes than `ctes`.
  *Confirmed* if it does.

## 4. What a failure would mean, stated before seeing it

If D5 fails, the headline is writer-dependent and the paper must say so and retract the generality of the
claim. If D5 holds but D6 fails, the effect is real but its size depends on who wrote the prose, and the
paper must report a range rather than a point. If D7 fails, the mechanism attribution is writer-dependent
and section 6.2 must be qualified.

The split is read once. No re-run, no added episodes, no metric change.
