# Where the work stands — 2026-09-16, after the held-out read

## The result

On 28 paired cases across 6 held-out scenarios, with each arm compared against **itself dropping the same number
of its own requested documents at random**:

| arm | withdrawal recall | own random baseline | excess | 95% CI | |
|---|---|---|---|---|---|
| direct prediction | 0.038 | 0.099 | **−0.061** | [−0.096, −0.026] | **worse than chance** |
| graph → ask the model for a checklist | 0.121 | 0.110 | +0.011 | [−0.017, +0.038] | no signal |
| **full pipeline** | **0.591** | 0.473 | **+0.118** | **[+0.106, +0.126]** | **real signal** |

Deriving documents through active process obligations produces withdrawals that carry information about what the
process actually released. Direct prediction produces withdrawals that are *anti-correlated* with them. Giving a
model the graph and letting it write the checklist removes the anti-correlation without creating signal — the
compiled chain is what does the work, on all six scenarios individually.

The cost is retention: the compiler has the worst of the three at 0.544 against 0.573 and 0.641. It is right about
what to release far more often, and it releases too much.

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
