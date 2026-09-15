# Submission split — final pre-registration

Written **before** any actor was run on this split. Its episodes existed; no arm had seen them.

## 1. What this split is for

Two questions, neither answerable from splits already read:

1. **Does the advantage survive a change of the reasoning model underneath it?** Every earlier number came
   from one actor model family. That is the easiest remaining attack.
2. **Does it survive the obvious fix, confirmatorily?** B6 was read diagnostically on an already-read
   split. Here it is pre-registered.

## 2. The split

Sixty episodes over **thirty families** appearing in no development, confirmatory, decisive or writer-swap
set. Ten families per domain. Thirty-three German, twenty-seven English.

**Thirty is not a convenient number.** The residual effect after B6 is +0.0667 with a family-level standard
deviation of 0.1211, so 80% power needs 27 families; 30 detects 0.0632. Twenty-one families would have been
underpowered for this comparison at 0.0756.

**Writers are assigned per family, before any actor ran, and do not track the actor.** Fifteen families to
`openai/gpt-5.4-mini` and fifteen to `anthropic/claude-sonnet-5`, fixed by seed. Every actor model sees the
same mixture, so no actor systematically matches its writer. Writer is recorded per episode and enters the
analysis as a nuisance variable.

The shortcut audit admits the split: every zero-model control is far below threshold.

## 3. What is frozen

| file | sha256 |
|---|---|
| `evidential_channel_v1.py` | `bb355763b7b79c5134844ddef57f6cf419d16a0a4820561ca221daae92e18394` |
| `artifact_gate_v1.py` (B6) | `c3b3dcfeef17f711187fff9087d1542389e33147a042fbc022ae8a65115b543e` |
| `arms.py` | `2916ca8c2ae50180838ab90ad3305b49cbaf7be7251b8df1d3b0146688378256` |
| `evaluation.py` | `96fb4225f2834c24ad64c776693d2b144bc1fc400fcef3a26d223adf04cd6ff5` |
| `runner.py` | `4f1200737cce22975b77491f40a2ed52263c484e8fb50b4636187c163bfcb919` |
| `analyze.py` | `01d6ae5ea33fc3414823bf3af41f6120be69fa6e5217256876141b5eb5a74627` |
| `latents.json` | `3b24b1f5aabf01f0ac42229ef97466523932532229e1403f5716beb0100c667c` |
| `cases_submission.json` | `e7040b5e33b8e2a53e3ef9472720ee1d9536e094b24436399e64cc93de43b739` |

`arms.py`, `evaluation.py` and `analyze.py` remain byte-identical to every run in this project.

## 4. Actor models

Nothing changes between them but the transport's model name and provider pin.

| role | model |
|---|---|
| economical | `openai/gpt-5.4-mini` |
| strong, same provider | `openai/gpt-5.6-terra` |
| strong, different provider | `anthropic/claude-sonnet-5` |

Arms: the zero-model controls plus `direct-end-to-end`, `full`, `full-artifact-gate`, `ctes` and
`ctes-abl-satisfaction`. Temperature 0, three turns, two requests per turn, no retries, no plan repair.

## 5. Hypotheses

Family-paired differences, 5000-sample bootstrap 95% intervals, as everywhere else.

- **S1 (primary).** Per actor model, `state_accuracy(ctes) − state_accuracy(full-artifact-gate)` is
  positive. *The method survives the obvious fix* if the interval excludes zero **on at least two of the
  three actor models**, and the pooled estimate across models excludes zero.
- **S2 (generalization).** The sign of S1 is the same on all three actor models. A single model on which
  the method loses is reported as a heterogeneous effect and **not averaged away**.
- **S3 (the lesson is not the method).** On every actor model, `full-artifact-gate` records
  substantially fewer hearsay receipts than `full`. This is expected to hold trivially and is stated so
  that the paper's claim "the obvious fix solves the hearsay error" is confirmatory rather than diagnostic.
- **S4 (mechanism).** On every actor model, `ctes-abl-satisfaction` records more premature-readiness
  episodes than `ctes`.

Holm correction across {S1 pooled, S2}. S3 and S4 are descriptive.

## 6. Decision rules, fixed now

- If S1 fails on two or more actor models, the residual does not generalize and the paper says the
  contribution is model-specific. I will not pool it away.
- If S1 holds only for the economical model, the honest claim is that the method compensates for a weaker
  reasoner, which is a narrower and still publishable claim — and it must be stated that way, in the
  abstract.
- If the effect reverses on any model, that model gets its own row in the main table and its own sentence.

## 7. Practical trade-off, chosen before the data

The composite utility is abandoned: two splits showed it does not separate, and it rewards a
never-deciding arm. It is replaced by a **burden-constrained correctness** analysis, chosen now:

> Among arms meeting the same minimum decision-safety threshold, compare state accuracy at matched
> evidence burden; and report the Pareto frontier over (state accuracy, premature readiness, requests).

The threshold and the frontier axes are fixed here, before any submission-split number exists.

## 8. Stopping rule

Read once per actor model. No re-runs, no added episodes, no metric substitution.
