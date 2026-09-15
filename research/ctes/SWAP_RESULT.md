# Writer swap of the decisive split — result

The most attackable choice in this work was that the evaluated model wrote its own benchmark episodes. The
earlier control covered thirteen families and only two of three domains. This one covers all twenty-one
families and all forty-two episodes of the split that carries the primary result.

**Design.** The identical twenty-one latent specifications, rewritten from the same paragraph briefs by
`anthropic/claude-sonnet-5`. Latents, gold labels, evaluator, arms and analysis untouched; only the prose
differs. Arm model remains `openai/gpt-5.4-mini`. Read once, under `PRE_REGISTRATION.md` fixed while the
episodes were still being written.

## All three pre-registered hypotheses confirmed

| | result |
|---|---|
| **D5** state accuracy of the method over the strongest baseline stays positive with an interval excluding zero | **confirmed**: +0.162, 95% CI [+0.116, +0.209], **20 of 21 families won, 1 lost**, p = 0.000 |
| **D6** the swapped estimate falls inside the decisive split's own interval | **confirmed**: 0.162 lies in [0.095, 0.205]; the two estimates are 0.147 and 0.162 |
| **D7** the satisfaction rule still carries premature readiness | **confirmed**: 3 episodes for the method, 8 with that rule disabled |

Full arm table on the swapped episodes:

| arm | state accuracy | premature readiness | hearsay receipts |
|---|---|---|---|
| method, satisfaction rule off | 0.798 | 8 | 0 |
| **method** | **0.788** | **3** | **0** |
| direct end-to-end | 0.673 | 18 | 57 |
| domain compiler | 0.643 | 27 | 0 |
| **strongest baseline** | **0.626** | 5 | 34 |
| random | 0.608 | 12 | 0 |
| static checklist | 0.608 | 39 | 0 |
| keyword router | 0.605 | 28 | 0 |
| request everything | 0.586 | 0 | 0 |

Against the other baselines under the new writer: +0.115 [+0.060, +0.170] over direct end-to-end, 17
families won and 4 lost; +0.202 [+0.153, +0.252] over the request-everything control, 21 won and none lost.

## What this closes, and what it does not

**Closed.** The writer does not produce the result. Every episode was rewritten by a different model family
from the same latents, and the primary effect moved from +0.147 to +0.162 — inside its own confidence
interval, and in the direction that makes the original estimate conservative rather than flattering. The
mechanism attribution survives too. The paper no longer needs to disclose a writer-swap control that covers
a third of the families and two of three domains, because the full control exists.

**Also settled: the cheap writer is not the weaker writer.** This gives the clean version of a comparison
the earlier artifacts got wrong. Identical latents, identical verifier, forty-two episodes each: the
motif-violation rate is **0.333 per episode for `gpt-5.4-mini` and 0.310 for `claude-sonnet-5`**, a
difference of 0.024. The expensive writer remains cleaner on return-scope semantics (2 flags against 10),
as it was before. On the one rule that carries cross-verifier signal the two are indistinguishable.

**Not closed.** Every arm still runs on one model family. Two writers do not make a writer population, and
a third writer could still differ. The composite utility and the symmetric readiness score remain nulls;
this run does not revisit either.

**Cost.** $5.79 in total: $2.96 to rewrite forty-two episodes with the expensive writer, $0.28 to verify
them, $2.55 to run nine arms over three turns.
