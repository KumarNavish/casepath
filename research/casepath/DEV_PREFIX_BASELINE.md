# Development observation: before the branch-consistency fix, every arm failed, in two different ways

Measured on 7 in-scope cases, each in two variants — one edited so the date of receipt is settled, one edited so
the substantive rent question is settled. The reference contract says these two variants require different
documents. The question is whether an arm's request differs the same way.

Run under the interpreter *before* the branch-consistency fix, and with interventions authored against the
contract rather than against the graph's own predicates. Both limitations are real and both are recorded in
`ENTRY_PREDICATE_DEFECT.md`. This is development data and carries no confirmatory weight.

## Responsiveness

| arm | identical on both variants | differing | mean symmetric difference |
|---|---|---|---|
| b1_direct | 1 of 7 | 6 | 2.43 |
| b3_graph_then_list | 2 of 7 | 5 | 2.43 |
| b5_induced_graph | **6 of 7** | 1 | **0.14** |

The process arm gave the same answer to two materially different cases almost every time.

## Correctness of the difference

Responsiveness is not correctness, and the second table is why both are needed.

| arm | documents the contract says differ | arm made differ, correctly | spuriously | recall | precision |
|---|---|---|---|---|---|
| b1_direct | 36 | 4 | 13 | 0.111 | 0.235 |
| b3_graph_then_list | 36 | 5 | 12 | 0.139 | **0.294** |
| b5_induced_graph | 36 | 0 | 1 | **0.000** | 0.000 |

Every arm failed, and the two failures are not the same failure.

**The direct baseline moved, mostly wrongly.** Roughly three of every four documents it changed between the two
variants were documents the contract says should not have changed, and it caught one in nine of those that should
have. Its apparent sensitivity to the case is largely resampling noise. This matters for how the first table
should be read: a method that varies more is not thereby tracking the case, and a reviewer shown only
responsiveness would have drawn the opposite conclusion from the right one.

**The process arm did not move at all.** Zero correct, and near-zero incorrect. Diagnosed to two causes, one
repaired: alternative branches out of the same step were decided independently, so the reader could mark a claim
and its negation both true and keep every branch alive; and the interventions targeted contract decisions the
graph has no predicate for. The first is fixed at commit `c43bc22` and the fix visibly unfreezes the arm — on the
first re-run case the request moved from 3 documents to 7 where before it was 9 and 9. The second is repaired by
targeting predicates the graph decides.

## What this licenses

Nothing about the method's merit. It establishes the floor the repaired system has to clear, and it records that
the direct baseline's variation is mostly noise — which is the reason the primary outcome is scored against the
contract's expected change rather than against how much an arm's answer moved.
