> **Superseded by the held-out read.** The conclusion below — that the process graph earns its place and the
> obligation compiler does not — is the opposite of what the confirmatory scenarios show. See `RESULTS.md` §3.
> All four development scenarios here are form-defect disputes, which activate graph nodes carrying no evidentiary
> obligation, so the compiler requested 3.9 documents and had nothing to release. On substantive rent-calculation
> scenarios it requests 10.0 and is the only arm with signal. The document is kept unedited because amendment A3
> was made on the strength of it.

# Development result: the process graph earns its place, the obligation compiler does not

12 paired development cases across 3 scenarios. Each pair is one case and the same case with a minimal factual
addition establishing that the tenant did not bring a challenge within 30 days. The reference contract, built
independently from Swiss federal sources, says which documents that settles. The question is whether an arm stops
asking for them.

## Static floor check

| arm | F1 | precision | recall | documents requested | chain rate | grounded rate |
|---|---|---|---|---|---|---|
| b1_direct | 0.620 | 1.000 | 0.458 | 4.6 | 0.000 | 0.000 |
| b3_graph_then_list | 0.582 | 0.988 | 0.425 | 4.3 | 0.000 | 0.000 |
| b5_induced_graph | 0.424 | 0.861 | 0.300 | 3.6 | 0.500 | 0.200 |
| *modal-list oracle* | *1.000* | *1.000* | *1.000* | *10.0* | — | — |

One distinct reference checklist across all 12 cases. A predictor that ignores the case and emits the modal list
scores a perfect 1.000. **Nothing in this table separates any two methods**, and no claim is drawn from it. It is
here to show that every arm is precise and partial: they ask for about four documents of the ten the contract
requires, and almost everything they ask for is right.

## Branch intervention — the discriminating test

| arm | expected withdrawals | correct | false | **recall** | precision | retention |
|---|---|---|---|---|---|---|
| b1_direct | 51 | **0** | 10 | **0.000** | 0.000 | 0.792 |
| b3_graph_then_list | 51 | 7 | 7 | **0.137** | 0.500 | 0.833 |
| b5_induced_graph | 51 | 2 | 4 | 0.039 | 0.333 | **0.857** |

| comparison | difference in withdrawal recall | 95% CI | |
|---|---|---|---|
| b3_graph_then_list − b1_direct | **+0.137** | **[+0.038, +0.267]** | **excludes zero** |
| b5_induced_graph − b1_direct | +0.039 | [+0.000, +0.133] | includes zero |

Bootstrap over scenarios, 5000 draws.

## What this says

**Direct prediction never withdraws correctly.** Not rarely — zero times in 51 opportunities across 12 cases. It
is not inert: it made 10 withdrawals, all of them documents the contract still requires. Re-predicting from a
changed narrative changes the answer, but the change is unrelated to what the change in facts actually settles.
This is the clearest result here and it is the one the paper turns on.

**The source-grounded process graph is what fixes it.** Handing the model the graph and asking for a checklist
lifts withdrawal recall to 0.137 at precision 0.500, and the difference from direct prediction survives resampling
over scenarios. The graph supplies the thing prediction lacks: a representation in which settling a fact closes a
branch, so the documents that branch demanded can be released.

**The obligation compiler does not add to that, and costs recall.** The full pipeline — obligations, facts,
capabilities, document routes — reaches 0.039, a third of what the model achieves reading the same graph
unaided. What it buys is real but narrow: the best retention of the three (0.857), the fewest false withdrawals,
and the only chains in the table — half its requests carry a justification, a fifth of them resting on an
authority the reference contract also relies on. No other arm offers anything to check.

The honest reading is that the contribution is the **source-grounded process structure**, not the deterministic
compilation on top of it. The compiler's precision discipline is bought with coverage: it can only release what
it compiled an obligation for, and coverage is thin — 8 of 13 nodes emitted no obligation at all in the graph
used here.

## Status of the claim

This is development data: 3 scenarios, 12 pairs, and the interval over 3 scenarios is weak even where it excludes
zero. The preregistered primary comparison was `b5_induced_graph` against `b1_direct`, and **it does not
separate**. The comparison that does separate, `b3_graph_then_list` against `b1_direct`, was not preregistered and
was found by looking at development data.

It therefore cannot be claimed from here. It can be preregistered and tested once on the held-out scenarios, which
remain unread — and that is what will be done.
