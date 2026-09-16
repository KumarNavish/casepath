# The same process graph gives opposite answers under different reasoners

Same 28 held-out pairs, same frozen induced graph, same reference contract, same code, same prompts, same
temperature. **Only the model doing the case interpretation and compilation changes.**

| model | arm | recall | own random baseline | **excess** | 95% CI | |
|---|---|---|---|---|---|---|
| gpt-5.6-terra | b1_direct | 0.038 | 0.099 | **−0.061** | [−0.096, −0.026] | **anti-correlated** |
| | b5_induced_graph | 0.591 | 0.472 | **+0.119** | [+0.108, +0.125] | **signal** |
| claude-haiku-4.5 | b1_direct | 0.038 | 0.035 | +0.003 | [−0.011, +0.016] | none |
| | b5_induced_graph | 0.000 | 0.077 | **−0.077** | [−0.092, −0.070] | **anti-correlated** |
| gemini-2.5-flash | b1_direct | 0.038 | 0.037 | +0.001 | [−0.010, +0.012] | none |
| | b5_induced_graph | 0.189 | 0.080 | **+0.109** | [+0.107, +0.112] | **signal** |
| deepseek-v3.2 | b1_direct | 0.045 | 0.035 | +0.010 | [−0.026, +0.041] | none |
| | b5_induced_graph | 0.000 | 0.034 | **−0.034** | [−0.037, −0.031] | **anti-correlated** |

## The two headline numbers both fail to replicate

**`b1_direct` is anti-correlated on 1 of 4 models.** The striking rent-increase finding — that direct prediction's
withdrawals point away from the correct ones — is specific to `gpt-5.6-terra`. On the other three its interval
spans zero: uninformative, not actively wrong.

**`b5_induced_graph` carries signal on 2 of 4.** On `gpt-5.6-terra` (+0.119) and `gemini-2.5-flash` (+0.109) the
compiled chain is informative. On `claude-haiku-4.5` (−0.077) and `deepseek-v3.2` (−0.039) it is **anti-correlated**
— the same artifact, driving the same code, withdraws the wrong documents.

The spread on one identical artifact is **+0.119 to −0.077**, and the intervals do not overlap.

## This is not a failure of the runs

Checked before drawing any conclusion:

| model | b5 errors | mean documents requested | mean chains | predicate verdicts (true / false / unresolved) |
|---|---|---|---|---|
| gpt-5.6-terra | **0** | 7.4 | 34.0 | 27 / 28 / 467 |
| claude-haiku-4.5 | **0** | 12.6 | 67.6 | 32 / 28 / 462 |
| gemini-2.5-flash | **0** | 6.5 | 31.0 | 32 / 29 / 461 |
| deepseek-v3.2 | **0** | 6.5 | 39.0 | 30 / 29 / 463 |

Zero errors anywhere. Every model resolves 10–12% of predicates and leaves the rest unresolved — near-identical
rates. The pipeline executed the same way in all four; what differs is *which* documents each asks for and releases.
`claude-haiku-4.5` compiles roughly twice as many chains and requests twice as many documents as the others, and
still withdraws nothing correct.

## What this means, stated carefully

A source-grounded process representation **does not by itself confer correct retraction behaviour**. The
representation is frozen and identical; the outcome is determined by the reasoner that interprets a case against
it. Reporting a single-model result for a method of this kind — as the confirmatory read did, and as this
literature commonly does — measures the pairing of method and model, and attributes the result to the method.

The finding is not that the method fails. On two of four reasoners it produces the only informative withdrawal
behaviour observed anywhere in this work. The finding is that **which reasoner you pair it with decides the sign of
the result**, and that no single-model experiment can see this.

## Consequence for the claims

The confirmatory result stands as reported *for `gpt-5.6-terra` on rent increase*, and must be stated with that
scope. Neither of the two headline effects is a property of the method:

- "direct prediction is anti-correlated with correct withdrawals" → **one model of four**
- "the compiled chain carries signal" → **two models of four, anti-correlated on the other two**

Combined with the termination transfer failing on the original model, the positive claim is bounded by one scope
and two reasoners, and the boundary is not currently predictable in advance except by running.
