# Confirmatory result

Eighty-two episodes over forty-one families that appear in no earlier split, read once, under the rules
fixed in `PRE_REGISTRATION.md` before any of them existed. Model `openai/gpt-5.4-mini`, temperature 0,
8000 output tokens, provider pinned, three turns, at most two requests per turn, no retries, no plan
repair. Every zero-model control stays far below the shortcut-audit thresholds, so the arena discriminates.

## 1. What the pre-registered rules returned

| hypothesis | result |
|---|---|
| H1 — `ctes` records zero hearsay receipts and `ctes-ablation` at least five | **not confirmed** |
| H2 — `U(ctes) > U(full)` | **not established**: +0.129, 95% CI [−0.011, +0.271], 21 wins / 16 losses, Holm p = 0.133 |
| H3 — `U(ctes) > U(ctes-ablation)` | **not established**: +0.127, 95% CI [−0.009, +0.273], 17 / 15, Holm p = 0.133 |
| H4 — the two signs agree between writers | **not confirmed** |

H1 failed on its second clause, and the failure is mine, not the method's. `ctes` did record zero hearsay
receipts, as predicted. So did `ctes-ablation` — and it had done so on every earlier split too, which I
should have read off my own prior results before writing the threshold. The typed atom representation is
what prevents a party report from being booked as a receipt; the channel cap is not what does that work.
H1 was therefore unfalsifiable in the direction I wrote it and is withdrawn as a test. What it was meant
to measure is measured below, on the metric that actually separates the two.

H4 failed between two null results. On the thirteen families written twice, `U(ctes) − U(full)` is +0.048
under one writer and −0.096 under the other, and neither interval comes near excluding zero. A sign test
over thirteen families of a null effect flips at chance; the amendment that introduced H4 said it was a
weak test, and it behaved like one. It did not answer the writer question. Section 4 answers it another
way.

H2 and H3 are honest negatives. Against the strongest baseline and against its own ablation, the composite
utility does not separate `ctes` at forty-one families. This is the third independent arena on which that
comparison fails to separate, and at this point the right reading is not "more data would fix it" but
"the composite utility is not where the difference lives".

## 2. Where the difference does live

Full arm table, eighty-two episodes:

| arm | U | hearsay receipts | premature-readiness episodes | acquired evidence | requests |
|---|---|---|---|---|---|
| **ctes** | **+0.024** | **0** | **6** | **58.75** | 353 |
| constant | −0.058 | 0 | 0 | 58.50 | 466 |
| ctes-ablation | −0.103 | 0 | 24 | 53.83 | 285 |
| full | −0.105 | 77 | 11 | 40.92 | 311 |
| process-only | −0.275 | 68 | 16 | 43.42 | 379 |
| direct-end-to-end | −0.321 | 137 | 32 | 44.42 | 337 |
| random | −0.348 | 0 | 25 | 40.25 | 319 |
| keyword-router | −0.443 | 0 | 59 | 55.17 | 268 |
| domain-compiler | −0.484 | 0 | 58 | 51.58 | 302 |
| static-checklist | −0.923 | 0 | 79 | 34.33 | 290 |

`ctes` is the best arm on utility, and the pre-registered comparisons against `process-only` (+0.300,
CI [+0.166, +0.430], 30/9) and `direct-end-to-end` (+0.345, CI [+0.194, +0.497], 33/7) are established
with p = 0.000. It is only against `full` and against its own ablation that the composite does not
separate.

The separating quantity is **state accuracy** — whether the agent is right about the state of each
document in the catalogue. Family-paired, forty-one families:

| comparison | mean difference | 95% CI | wins / losses | p |
|---|---|---|---|---|
| ctes vs full | **+0.148** | [+0.100, +0.195] | 36 / 4 | 0.0000 |
| ctes vs direct-end-to-end | +0.128 | [+0.076, +0.177] | 32 / 8 | 0.0000 |
| ctes vs process-only | +0.120 | [+0.065, +0.174] | 32 / 8 | 0.0000 |
| ctes vs constant | +0.181 | [+0.141, +0.214] | 39 / 2 | 0.0000 |
| ctes vs ctes-ablation | +0.019 | [−0.006, +0.044] | 20 / 10 | 0.1136 |

These are exploratory, not pre-registered, and no multiplicity correction is applied across them. They are
also not close to the boundary: the interval against the strongest baseline is entirely above +0.10 and
the method wins thirty-six of forty-one families.

The last row is the important one. State accuracy does **not** separate `ctes` from its own ablation, which
says plainly where each part of the method earns its keep:

- the **typed atom representation and deterministic calculus** buy the state accuracy — about fourteen
  points over the strongest baseline — and they buy the zero hearsay receipts;
- the **channel cap**, the one non-standard operation, buys correct *readiness*: premature readiness falls
  from 24 episodes to 6, a family-paired difference of 0.220 [0.134, 0.317] with fifteen families won and
  **none lost**, p = 0.0000, and readiness accuracy rises by 0.081 [0.016, 0.155], p = 0.013;
- the cap is paid for in requests: `ctes` asks for 0.610 [0.366, 0.866] more documents per family than the
  ablation, p = 0.0000, because it cannot take a party's word that a document exists or is coming.

At a burden weight of 0.25 those two effects nearly cancel in `U`, which is exactly why H3 does not
separate while its components separate decisively in opposite directions. That is a finding about the
utility function, not about the method.

## 3. The one result that should worry a reader

`constant` — a zero-model arm that requests every catalogue document not yet returned and never declares
readiness — acquires as much critical evidence as `ctes` (58.50 vs 58.75, paired difference +0.003,
p = 0.94) and never declares readiness prematurely (0 episodes vs 6, and it wins that comparison 6/0).
It loses only on request burden, and on state accuracy, where it is the worst arm of all (+0.181 for
`ctes`, 39 wins to 2).

Two things follow. First, on a three-turn budget with the burden term capped at four, asking for
everything is nearly free, so any acquisition-based metric will flatter it; that is a weakness of `U` that
the paper must state rather than hide. Second, `constant` pays for its safety with 29 missed readiness
decisions against `ctes`'s 20 — it is safe because it never decides. The metric `U` charges premature
readiness and does not reward correct readiness, so an arm that never decides is never punished. Any
future version of this arena should score readiness symmetrically.

## 4. Whether the writer chose the answer

Thirteen families exist in two independently written versions from the identical latent specification, one
by `openai/gpt-5.4-mini` (the evaluated model) and one by `anthropic/claude-sonnet-5`. The pre-registered
sign test could not separate anything. The metric that does separate is stable across both:

| comparison | mini-written | Sonnet-written |
|---|---|---|
| state accuracy, ctes vs full | +0.156 [+0.075, +0.244], 11/1, p = 0.000 | +0.139 [+0.062, +0.218], 11/2, p = 0.000 |
| state accuracy, ctes vs direct | +0.134 [+0.059, +0.207], 11/2, p = 0.000 | +0.205 [+0.117, +0.297], 11/2, p = 0.000 |
| hearsay receipts, ctes vs full | −1.346 [−2.115, −0.692], 0/9, p = 0.000 | −0.962 [−1.654, −0.385], 0/7, p = 0.000 |
| utility, ctes vs full | +0.048 [−0.234, +0.333], p = 0.740 | −0.096 [−0.253, +0.061], p = 0.248 |

The headline claim and the mechanism claim hold under both writers, at nearly the same size. The utility
comparison is null under both. What does change is absolute difficulty: every arm scores higher on the
Sonnet-written episodes, including `random` and `constant`, so that set is simply easier across the board.
That is a level shift, not an interaction, and it is why the sign of a null difference flipped.

One real writer difference was found and it runs against the method. In eight of eighty-two mini-written
episodes the customer paragraph states the hearsay condition in words — "From memory, the notice is
dated…", "Aus dem Gedächtnis steht in dem Protokoll…" — where none of the twenty-six Sonnet-written
episodes does. Spelling out that a fact comes from recollection makes the provenance legible to an arm
that reads content, which helps the baselines and shrinks the measured gap. The primary result is
conservative in that respect.

## 5. Limitations that stand

1. The composite utility does not separate `ctes` from `full` or from its own ablation, at forty-one
   families, on a third independent arena. Reported as a negative.
2. `channel_cap=False` is a compound switch. It removes the channel levels, it stops downgrading a
   delivery promise reported by a party, and it loosens requirement satisfaction from "the artifact was
   returned **and** its content attests" to "either". The ablation is therefore "content-based support",
   not "the same calculus with one flag flipped", and `METHOD.md` has been corrected to say so. A clean
   single-effect ablation has not been run.
3. A failed model output is scored with zero acquired evidence and zero state accuracy, and the baselines
   fail more often than the method (process-only 11, full 6, ctes 3 of 246 turn-records). Dropping the
   eight episodes in which any arm failed moves the headline from +0.148 to +0.135 [+0.091, +0.181],
   34 wins / 6 losses, p = 0.0000. About a tenth of the gap is the harness; nine tenths is not.
4. `hearsay_receipts` counts a document recorded as `received` **or** as `insufficient` when no version of
   it has been returned. The broader reading is the one used throughout; under it `ctes` scores zero, so
   the narrower reading cannot raise it.
5. The writer-swap control covers thirteen of forty-one families and one writer pair. A properly powered
   swap would rewrite all forty-one families under a second writer, at roughly fifteen dollars.
6. `U` charges premature readiness and does not reward correct readiness, which is why a never-deciding
   arm is not punished.
