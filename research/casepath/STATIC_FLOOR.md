# Static floor check — six arms, and why no claim is drawn from it

8 clean development cases, all six arms matched on model, temperature, catalogue, held documents and scope.

| arm | F1 | precision | recall | documents requested | unjustified | chain rate | grounded rate |
|---|---|---|---|---|---|---|---|
| b1_direct | 0.605 | 1.000 | 0.438 | 4.4 | 0.00 | 0.000 | 0.000 |
| b2_retrieval | 0.601 | 1.000 | 0.438 | 4.4 | 0.00 | 0.000 | 0.000 |
| b3_graph_then_list | **0.635** | 1.000 | 0.475 | 4.8 | 0.00 | 0.000 | 0.000 |
| b3t_summary_then_list | 0.601 | 1.000 | 0.438 | 4.4 | 0.00 | 0.000 | 0.000 |
| b6_prior_composition | 0.618 | 1.000 | 0.450 | 4.5 | 0.00 | 0.000 | 0.000 |
| b5_induced_graph | 0.488 | 0.925 | 0.338 | 3.8 | 0.38 | **0.400** | **0.300** |
| **modal-list oracle** | **1.000** | **1.000** | **1.000** | 10.0 | 0.00 | — | — |

## What it shows

**Nothing separates the methods.** Five of six arms sit within 0.034 F1 of one another. The minimal obvious fix —
compose the checklist from prior cases, no law, no graph — scores 0.618, between retrieval and the graph arm. A
retrieval baseline and a prose summary of the graph score identically to direct prediction, to three decimals.

**All of them lose to a trivial oracle.** There is one distinct reference checklist across the eight cases, so a
predictor that ignores the case entirely and emits the modal ten documents scores a perfect 1.000. No method here
beats not looking.

This is the saturation documented in `STATIC_TASK_SATURATION.md`, now measured across the full baseline matrix. A
paper that reported the 0.635 as the graph arm "winning" would be reporting noise on a task where the correct
answer is the same every time.

**Every arm is precise and partial.** Precision is 1.000 for five arms: they are not wrong about what they ask
for, they ask for about four of the ten documents the contract requires. The reference set is a completion set —
everything needed to close every still-open decision — so recall against it measures how much an arm asks for, not
how well it triages.

**Only one arm offers anything to check.** `b5_induced_graph` is alone in producing justification chains: 40% of
reference documents arrive with a chain, and 30% with a chain resting on an authority the reference contract also
relies on. It also pays for this, with the lowest F1 and the only unjustified requests. Every other arm scores
zero on chains by construction, which is the honest reading — they offer no justification to check, rather than
one that fails.

## Consequence

The static table is reported as a floor check and carries no comparative claim. The discriminating measurement is
the branch intervention, which scores *change* rather than level and is therefore unaffected by the saturation
that makes this table uninformative.
