# The headline metric hides a reversal, and the reversal is against the method

Found during the submission-closure pass, by an adversarial novelty audit that recomputed the author's own
records rather than accepting the summary statistic. It is the most important finding of that pass and it
runs against the method.

## What was claimed

State accuracy, averaged over the three turns of an episode, family-paired. On that quantity the method
beats the strongest baseline by +0.147 [+0.095, +0.205] on the decisive split, pre-registered, replicated
under a second writer at +0.162, and by +0.094 over the obvious-fix baseline on the submission split.

Those numbers are correctly computed and were fixed in advance. Nothing below retracts them.

## What the same records show per turn

| split | arm | turn 0 | turn 1 | turn 2 | final-turn rank |
|---|---|---|---|---|---|
| decisive, `gpt-5.4-mini` | method | 0.864 | 0.803 | **0.745** | 4th of 13 |
| | direct end-to-end | 0.633 | 0.667 | **0.752** | **1st** |
| decisive, rewritten by a second model | method | 0.861 | 0.806 | **0.697** | 5th of 9 |
| | direct end-to-end | 0.619 | 0.660 | **0.741** | 2nd |
| submission, `gpt-5.4-mini` | method | 0.824 | 0.819 | 0.719 | 5th of 10 |
| submission, `gpt-5.6-terra` | method | 0.893 | 0.826 | **0.698** | 7th of 10 |
| | obvious-fix baseline | 0.810 | 0.776 | **0.736** | 3rd |
| confirmatory, `gpt-5.4-mini` | method | 0.754 | 0.771 | 0.754 | 1st of 10 |

**The method starts far ahead and ends behind.** Its state accuracy falls monotonically across turns on
four of five runs. The baselines rise. On the decisive split — the one carrying the pre-registered primary
result — a plain direct end-to-end planner is **more accurate at the final turn** than the method, 0.752 to
0.745. On the strong actor the obvious-fix baseline finishes ahead, 0.736 to 0.698.

The three-turn mean is dominated by a turn-0 advantage that has evaporated by the turn on which the
operational decision is actually taken.

## Why this matters more than the mean

Turn 2 is the turn where the agent decides. An evidence-acquisition system is judged on the state it holds
when it acts, not on the average of the states it held along the way. A metric averaged over turns rewards
being right early, which is the regime where the method's deterministic construction most helps and where
the baselines have least information. As documents arrive, the baselines' direct reading of them catches
up and overtakes.

The pre-registration chose the averaged metric before any of this was visible. That choice was made in good
faith and is documented, but the quantity it fixed is not the quantity a reader will care about.

## What this does to the contribution

Taken with the other two closure results, the case does not hold in its current form:

1. **Novelty.** A hostile operation-level audit across five independent search angles returned *no
   residual* on every angle, with verified prior art for the audited operation — confining a model to
   local extraction and deriving the aggregate state deterministically — including work evaluated on
   insurance claims. The empirical contrast against a no-verification variant also exists in prior work.
2. **Generalization.** On the strong actor the advantage over the obvious fix is +0.032 [−0.006, +0.068],
   p = 0.10 — not established. The advantage is largest where the reasoner is weakest.
3. **Trajectory.** The above.

The obvious-fix baseline already removes the hearsay error entirely on every actor tested (99 receipts to
0 on the economical model, 16 to 0 on the strong one) and beats the method on readiness accuracy on both.

## The honest status

**Not submission-ready, and not because of packaging.** The central empirical claim, read at the turn that
matters, does not survive its own closure tests. Declaring otherwise would be exactly the overclaim the
closure mandate forbids.

## What would have to be true instead

A defensible submission from this material would need at least one of:

- a final-turn primary endpoint, pre-registered in advance on a fresh split, on which the method wins —
  which the current records give no reason to expect;
- a contribution reframed around the regime where the effect is real: early-turn state accuracy under a
  weak reasoner, stated with that scope in the abstract and title, and a reason a reader should care about
  it;
- a different operation entirely, since the audited one is prior art.

The experiments, benchmark, product integration, pre-registrations and release machinery all stand and are
reusable. What does not stand is the claim.
