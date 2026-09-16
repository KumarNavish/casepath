# Transfer to termination — not supported

One read, 49 pairs across 8 scenarios, under `TRANSFER_PREREGISTRATION.md` and its amendment T1.

| arm | expected | correct | false | recall | own random baseline | **excess** | 95% CI | retention | requested |
|---|---|---|---|---|---|---|---|---|---|
| b1_direct | 77 | 5 | 80 | 0.065 | 0.050 | +0.015 | [−0.011, +0.051] | 0.723 | 6.4 |
| b3_graph_then_list | 77 | 6 | 70 | 0.078 | 0.059 | +0.019 | [−0.008, +0.057] | 0.756 | 6.3 |
| b5_induced_graph | 77 | **0** | 6 | 0.000 | 0.012 | **−0.012** | [−0.024, +0.000] | 0.992 | 16.0 |

**PREREGISTERED VERDICT: NOT SUPPORTED.** No arm's interval excludes zero. The effect found on rent increase does
not appear on termination.

The rent-increase finding that `b1_direct` is *anti-correlated* also does not reproduce: here its interval spans
zero.

## Why, and it was visible in advance

The scope's ceiling was computed before the run and recorded in the preregistration: settling `DEC-09` releases 3
documents and no other single decision releases more than 1, against 6 for the rent-increase probe. Measured, the
contract released a mean of **1.57** documents per pair, non-empty on 22 of 49.

Against that, `b5_induced_graph` requests **16.0 of the 18** catalogue documents and retains **0.992** of what it
should keep — it withdrew 6 documents in total across 49 pairs, none of them correct. The compiled requirement set
barely moves because the probe `e05` closes 4 nodes carrying 1 obligation between them. There was almost nothing
for the mechanism to release, and it released almost nothing.

So the arm behaved consistently with its design and the design had no room to act. That is a real limitation of the
method on this scope, not a measurement artifact: a process-derived checklist can only retract where the process
attaches obligations to the branch that closes.

## What this costs the paper

The positive result now rests on **one scope of two**. Termination was not a weak attempt — it was built by the
same procedures, with its own gated contract (91 of 106 quotes verbatim, 21 of 21 decisions retained), its own
voted catalogue-restricted document layer, its own induced graph, and a probe chosen structurally in advance. It
still produced nothing.

Two readings are available and the evidence does not yet separate them:

1. The method works where the process attaches evidentiary obligations densely to branches that real facts close,
   and rent increase is such a scope while termination is not. This is a scope-selection criterion, and it is
   testable in advance from the contract alone — the ceiling computation above predicted this outcome.
2. The rent-increase result is scope-specific in a way not yet understood, and one positive scope is not evidence
   of a method.

The honest position is that the paper cannot claim a general method on this evidence. What it can claim is the
measurement apparatus, the two replicated negative findings, and a narrow positive result with its boundary
condition stated and a test for that boundary given.
