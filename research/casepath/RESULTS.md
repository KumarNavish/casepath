# Results

All numbers come from committed intermediates and reproduce by running
`research/casepath/development_analysis.py` and `research/casepath/confirmatory_analysis.py`, neither of which
makes a network call.

## Setup

50 real Swiss tenancy claims in 10 scenarios of exactly 5 cases, split before any held-out case was read: 4
scenarios (20 cases) development, 6 scenarios (30 cases) confirmatory. Ground truth is a reference contract built
from Swiss federal sources by agents that never saw the induced graph, under a verbatim-quote gate, with a voted
document layer. Per case, three adjudicators mark each of its 12 decisions live / dead / unknown; unknown keeps a
decision open.

Intervals bootstrap over **scenarios**, 5000 draws, seed 20260916.

## 1. The static task is saturated — reported as a floor check only

Six arms on clean development originals:

| arm | F1 | precision | recall | documents requested | chain rate | grounded rate |
|---|---|---|---|---|---|---|
| b1_direct | 0.605 | 1.000 | 0.438 | 4.4 | 0.000 | 0.000 |
| b2_retrieval | 0.601 | 1.000 | 0.438 | 4.4 | 0.000 | 0.000 |
| b3_graph_then_list | 0.635 | 1.000 | 0.475 | 4.8 | 0.000 | 0.000 |
| b3t_summary_then_list | 0.601 | 1.000 | 0.438 | 4.4 | 0.000 | 0.000 |
| b6_prior_composition | 0.618 | 1.000 | 0.450 | 4.5 | 0.000 | 0.000 |
| b5_induced_graph | 0.488 | 0.925 | 0.338 | 3.8 | 0.400 | 0.300 |
| **modal-list oracle** | **1.000** | 1.000 | 1.000 | 10.0 | — | — |

One distinct reference checklist across the cases. A predictor that ignores the case and emits the modal list
scores a perfect 1.000, and five of six arms sit within 0.034 F1 of one another — including the minimal obvious
fix, which uses no law and no graph. **No comparative claim is drawn from this table.** Details and the cause in
`STATIC_FLOOR.md` and `STATIC_TASK_SATURATION.md`.

Two things it does establish. Every arm is precise and partial — precision 1.000 for five of six, asking about
four of the ten documents the contract requires, because the reference set is a completion set rather than a
triage list. And only `b5_induced_graph` produces justification chains at all.

## 2. Branch intervention — development

14 paired cases, 3 scenarios. Each pair is a case and the same case with a minimal factual addition establishing
that the tenant did not challenge within 30 days. The contract releases a mean of 4.6 documents when that settles.

| arm | expected withdrawals | correct | false | **withdrawal recall** | precision | retention |
|---|---|---|---|---|---|---|
| b1_direct | 61 | **0** | 11 | **0.000** | 0.000 | 0.792 |
| b3_graph_then_list | 61 | 9 | 7 | **0.148** | 0.562 | 0.851 |
| b5_induced_graph | 61 | 2 | 6 | 0.033 | 0.250 | 0.824 |

| comparison | Δ recall | 95% CI | |
|---|---|---|---|
| b3_graph_then_list − b1_direct | **+0.148** | **[+0.038, +0.267]** | excludes zero |
| b5_induced_graph − b1_direct | +0.033 | [+0.000, +0.133] | includes zero |

**Direct prediction withdrew correctly zero times in 61 opportunities** while making 11 withdrawals — it changes
its answer, but the change does not track what the new fact settled. The source-grounded graph is what fixes that.
The deterministic obligation compiler does not add to it and costs recall, buying retention, fewer false
withdrawals, and the only auditable chains.

## 3. Confirmatory read

*(Pending — 28 pairs across 6 held-out scenarios, 25 with a non-empty expected withdrawal, adjudicator unanimity
93%. The preregistered uninformative condition does not trigger. The primary comparison, amended and declared in
`PREREGISTRATION.md` A3 before the data was read, is `b3_graph_then_list` against `b1_direct`; the original
primary `b5_induced_graph` against `b1_direct` is reported alongside as a secondary.)*

## 4. What the verification gate caught

Of 58 quotes proposed for the reference contract, 44 verified verbatim against the Fedlex passage each was
attributed to. One failure was a fabrication of a kind reading cannot catch: `vmwg-art-19a-20251001-de`, cited at
a consolidation date Fedlex does not serve, for an article that exists at no consolidation, with a fluent and
sourceless quote. See `CITATION_FIDELITY.md`, which also retracts a cross-scope fabrication rate that turned out
to be an artifact of how the other contracts store their citations.
