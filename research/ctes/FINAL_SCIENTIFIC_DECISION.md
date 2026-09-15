# Final scientific decision

**The contribution is the channel cap**: an evidence-acquisition agent derives how much support a source
can lend from the channel the source arrived on, not from its content or the model's judgement. It is one
typed constraint over signal the product already records, it costs nothing at inference time, and it is the
component the evidence attributes to.

**What the evidence supports.**
1. The hearsay failure is real and scales with model weakness: model-declared arms produce 4–80 hearsay
   receipts per split (Opus 3–5; gpt-5.4-mini 11–80). CTES produces **zero in all six configurations**.
2. Premature readiness: direct produces 1–12 episodes per split; CTES produces 0 in five of six and 1 once.
3. On the primary frozen utility CTES is the best arm in 5 of 6 configurations, and beats the direct planner
   with a family-level interval excluding zero in 4 of 6.
4. Removing only the cap (identical call, atoms, calculus) costs +0.424 [0.062, 0.924] on the untouched
   hidden split and +0.950 [0.750, 1.183] in the transfer domain, where the ablation suffers 8 premature
   readiness episodes and a negative utility. The mechanism, not the pipeline, carries the safety result.
5. Fixed-core transfer to a third domain required **zero** changed lines of algorithm, configuration or
   prompt; only the episodes' own knowledge changed.
6. The gain is not bought with acquisitions: CTES issues fewer requests than direct in every split
   (36 vs 46 hidden, 23 vs 32 transfer) at comparable inference cost.

**What it does not support.** Superiority over process-first + deterministic verifier is not established at
family-level significance (4 of 6 intervals include zero). Against a strong direct planner in the transfer
domain the utility difference is within noise. These are reported, not smoothed.

**Status against the METHOD_READY gate.** Scientific, evaluation, generality and product boxes are met with
artifacts. Two empirical boxes are not: significance against `full`, and an untouched-first-look hidden
split for the final method version. I therefore do not emit the terminal token; the honest statement is that
the method, arena, evaluation, and product integration exist and reinforce each other, one comparison is
underpowered, and the hidden split was read a second time for the final method version.

**Cheapest next step to close them**: extend the arena by ~12 families per split (episode writing costs
~$0.02 each through the cheap model) and run the full matrix on the small model at ~$2 per split, then a
single Opus confirmation. Nothing about the method needs to change.
