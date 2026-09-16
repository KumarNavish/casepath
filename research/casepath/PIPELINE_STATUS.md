# Where the work stands — 2026-09-16, after the held-out read

## The result

**A frozen, source-grounded process representation does not by itself confer correct retraction behaviour. The
reasoner interpreting it decides the sign.**

Same 28 held-out pairs, same graph, same contract, same code, same prompts, same temperature — only the model
changes. Withdrawal recall above each arm's own random-drop baseline:

| model | b1_direct | b5_induced_graph |
|---|---|---|
| gpt-5.6-terra | **−0.061** [−0.096, −0.026] anti-corr | **+0.119** [+0.108, +0.125] signal |
| claude-haiku-4.5 | +0.003 none | **−0.077** [−0.092, −0.070] anti-corr |
| gemini-2.5-flash | +0.001 none | **+0.109** [+0.107, +0.112] signal |
| deepseek-v3.2 | +0.013 none | **−0.039** [−0.043, −0.030] anti-corr |

Spread on one identical artifact: **+0.119 to −0.077**, non-overlapping intervals, zero execution errors, and
near-identical predicate-resolution rates across all four. Neither headline effect is a property of the method:
direct prediction is anti-correlated on 1 of 4 models, the compiled chain carries signal on 2 of 4.

Transfer to a second scope (termination, 49 pairs) produced **no arm with signal**, and the ceiling that explains
it was computed from the contract before the run.

The paper is therefore a measurement and negative-results paper, not a method paper.

## What is settled

| | |
|---|---|
| Authority corpus | 86 passages, OR / VMWG / ZPO / VVG, one extraction identity, every passage hashed |
| Reference contract | 12 decisions, 11 documents, 44 of 58 quotes verbatim-verified, voted document layer |
| Corpus | 10 scenarios × exactly 5 cases = 50 clean cases, 0 leakage between splits |
| Static task | saturated — one distinct checklist; six arms within 0.034 F1; all lose to a trivial oracle |
| Held-out read | done, once, under a script committed before the data existed |
| Product | runs the four pipeline modules and adds no logic of its own; full trace verified end to end |
| Artifact check | `verify_artifacts.py` passes: 0 hash mismatches, 44/44 quotes verbatim, 0 cases leaked |

## Three defects found by measurement

1. **No applicability gate.** The graph's entry node has no incoming condition, so the process cannot be told the
   scope does not apply. Still open.
2. **Contradictory branch verdicts.** Alternatives out of one step were decided independently, so a claim and its
   negation could both hold and nothing could ever be withdrawn. Fixed at `c43bc22`.
3. **Sparse obligation coverage.** 8 of 13 nodes emitted no obligation. Synthesis now requires a determination node
   for every substantive standard and obligations wherever a party must show something; the re-induced graph gains
   the substantive-review node the first lacked. Its evaluation is incomplete and it was excluded from the held-out
   read.

## Three errors of mine, all corrected in the record

1. Computed that the primary outcome was structurally impossible and committed a document acting on it. The
   computation pooled each node's document supply across cases when the compiler recomputes it per case. Refuted by
   data; corrected at `df63478`.
2. Nearly reported a cross-scope citation-fabrication rate of 25–60% that was an artifact of contracts storing
   sources and quotes as unmapped parallel lists. Retracted before publication at `b6c9195`.
3. Amended the preregistered primary away from the compiler on development evidence that was unrepresentative —
   all four development scenarios were form-defect disputes, which activate nodes carrying no evidentiary
   obligation. The amendment was declared before the read, so the original primary survives in the record.

## What remains before submission

- Manuscript assembly from these documents and the committed tables.
- The full test suite has not been run to completion since the interpreter change.
- Transfer: contracts exist for termination, theft and legal expenses; none has been run through the pipeline.
- The applicability-gate defect is unrepaired, and the re-induced graph is unevaluated.
