# B6: does the obvious fix get the whole result?

The strongest remaining objection was that the method is ordinary engineering wearing a typed
representation. This answers it with an experiment rather than a paragraph.

## What was built

`full-artifact-gate` keeps every part of the strongest baseline — same model, same prompt, same
byte-identical request, its own model-generated states, its own process decomposition, its own verifier,
its own request planner, its own readiness mechanism — and adds one deterministic post-process:

1. a document may be `received` or `insufficient` **only if that exact document has been returned**,
   otherwise the state resets to `missing`, or `pending` where the plan recorded a pending delivery;
2. a downgrade withdraws a declared readiness, and repoints an orphaned `proceed` at up to two of the
   reopened documents.

Per document, never per run. It reads only identities already in the baseline's own actor JSON, so it
gains no information the baseline lacked — it gains *enforcement* of the rule the baseline was merely told.
It receives none of the method's atom extraction, state calculus, channel ordering or commitment demotion.

Diagnostic read on the decisive split, which had already been read once, so this comparison is exploratory
by construction and labelled so. Forty-two episodes, twenty-one families, `gpt-5.4-mini`.

## Result: pre-registered Case B

| arm | state acc. | readiness acc. | premature | missed | requests | critical evidence | output failures | hearsay receipts |
|---|---|---|---|---|---|---|---|---|
| **method** | **0.765** | 0.802 | 3 | 22 | 179 | 31.83 | **0** | 0 |
| **B6, obvious fix** | 0.667 | **0.841** | 6 | 8 | **154** | 22.33 | 5 | **0** |
| direct end-to-end | 0.659 | 0.802 | 17 | 5 | 184 | 24.83 | 2 | 56 |
| strongest baseline | 0.651 | 0.873 | 4 | 6 | 149 | 22.33 | 5 | 48 |
| request everything | 0.586 | 0.817 | 0 | 23 | 240 | 31.17 | 0 | 0 |

**The obvious fix works, on the thing it was designed for.** B6 takes hearsay receipts from 48 to **zero**,
the same as the method. Anyone claiming the method is needed to stop an agent booking a party's report as a
received document is wrong: twenty lines of deterministic post-processing on the strongest baseline does it.

**It does not get the state-accuracy result.** Family-paired, method minus B6:

| | all 42 episodes | clean only (39) |
|---|---|---|
| state accuracy | +0.099 [+0.036, +0.171], 15/6, p = 0.0000 | **+0.067 [+0.017, +0.119], 14/6, p = 0.0088** |

The clean-only column is the honest one. B6 inherits the baseline's schema brittleness — 5 output failures
against the method's 0 — and a failed turn scores zero state accuracy, so a third of the raw gap is the
harness. What survives is **+0.067**, against +0.147 for the same method over the *ungated* baseline.

**So the obvious fix accounts for roughly half of what the method was previously credited with.** That is
the single most important correction this experiment produces, and it is a correction against the method.

## What this obliges, under the pre-registration

Case B was: *B6 fixes readiness but not state estimation; the paper then has two separable contributions
and must identify the operation responsible for the second.* That is what happened, with one refinement —
B6 fixes hearsay receipts outright and is, if anything, **better** than the method on readiness accuracy
(+0.040 in B6's favour, 4/9, p = 0.40) at **lower burden** (0.81 fewer requests per family, p = 0.019).

The contribution therefore narrows to one thing:

> Constructing the evidence state from typed local atoms by a deterministic calculus, rather than asking
> the model for the state directly, yields **+0.067 [+0.017, +0.119]** state accuracy over the strongest
> baseline *after that baseline has been given the same deterministic artifact rule*, and it does so at a
> cost of 0.81 more document requests per family.

Within that residual, the method's own single-rule ablations attribute about 0.033 to the demotion of
party-reported delivery commitments, leaving the remainder to the typed extraction and aggregation itself.

## What the paper must stop claiming

- That the artifact-required satisfaction rule is the contribution. It is the *lesson*, and it is
  reproducible by an engineer in an afternoon. B6 proves it.
- That the method's advantage over the strongest baseline is +0.147. Against a baseline that has had the
  obvious fix applied it is +0.067.
- That the method improves readiness. B6 is better on readiness accuracy and cheaper.

## What survives, and is now sharper

- The typed local state construction buys evidence-state accuracy that the obvious fix does not, on a
  comparison where both arms are forbidden from crediting a party report.
- The method produced zero output failures across the run where both baseline variants produced five,
  which is a property of returning atoms rather than a whole plan.
- The method acquires materially more critical evidence (+0.226, 16/1, p = 0.0000), and pays for it.
