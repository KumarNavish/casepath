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

## 3. Confirmatory read — one read, 28 pairs across 6 held-out scenarios

Adjudicator unanimity 93%. 25 of 28 pairs have a non-empty expected withdrawal, so the preregistered
uninformative condition does not trigger. The contract releases a mean of 4.7 documents.

| arm | expected | correct | false | **withdrawal recall** | precision | retention | documents requested |
|---|---|---|---|---|---|---|---|
| b1_direct | 132 | 5 | 35 | 0.038 | 0.125 | 0.573 | 5.3 |
| b3_graph_then_list | 132 | 16 | 28 | 0.121 | 0.364 | 0.641 | 5.5 |
| b5_induced_graph | 132 | **78** | 52 | **0.591** | **0.600** | 0.544 | 10.0 |

| preregistered comparison | Δ recall | 95% CI | retention Δ | verdict |
|---|---|---|---|---|
| **primary (A3)** b3 − b1 | +0.083 | [+0.018, +0.151] | +0.068 | **SUPPORTED** |
| **secondary** (original primary, `ee6f266`) b5 − b1 | +0.553 | [+0.459, +0.613] | −0.029 | passes the same criteria |

### The volume control, which changes what these numbers mean

`b5_induced_graph` requests 10.0 documents where the others request ~5.4, and the reference set is 10.0. An arm
that asks for more has more to drop, so a raw withdrawal recall is not comparable across arms. Each arm is
therefore compared against **itself dropping the same number of its own requested documents at random** (300 draws
per pair, bootstrapped over scenarios):

| arm | recall | own random baseline | **excess over random** | 95% CI | |
|---|---|---|---|---|---|
| b1_direct | 0.038 | 0.099 | **−0.061** | [−0.096, −0.026] | **anti-correlated** |
| b3_graph_then_list | 0.121 | 0.110 | +0.011 | [−0.017, +0.038] | no signal |
| b5_induced_graph | 0.591 | 0.473 | **+0.118** | **[+0.106, +0.126]** | **real signal** |

Three things follow, and the second is a correction to the headline above.

**Direct prediction is worse than chance.** Its interval lies entirely below zero. It is not merely failing to
track the process — the documents it stops requesting are *anti-correlated* with the documents the process
releases. Re-predicting from a changed narrative moves the checklist away from the right answer.

**The preregistered primary is supported for the wrong reason.** `b3_graph_then_list` beats `b1_direct` because
b1 is anti-correlated, not because b3 is informative: b3's excess over its own random baseline is +0.011 with an
interval spanning zero. Handing the model the graph stops it making anti-correlated withdrawals; it does not make
its withdrawals *informative*. Reporting the +0.083 without this control would have been misleading, and the
preregistered verdict is recorded with that qualification attached.

**The obligation compiler is the only arm whose withdrawals carry information.** +0.118 above its own random
baseline, interval [+0.106, +0.126], tight and far from zero. The deterministic chain — node closes, obligation
lapses, capability is no longer needed, document is released — is what produces the signal.

### This reverses the development result, and amendment A3 was a mistake

| arm | development recall | confirmatory recall | documents requested, dev → conf |
|---|---|---|---|
| b1_direct | 0.000 | 0.038 | 4.4 → 5.3 |
| b3_graph_then_list | **0.148** | 0.121 | 4.2 → 5.5 |
| b5_induced_graph | 0.033 | **0.591** | 3.9 → **10.0** |

On development the compiler looked useless and I amended the preregistered primary away from it (A3). On held-out
data it is the only arm that works. The mechanism is visible in the last column: the development scenarios are all
**form-defect** disputes, which activate nodes carrying no evidentiary obligation, so the compiler had almost
nothing to compile or release — it requested 3.9 documents. The confirmatory scenarios are **substantive
rent-calculation** disputes (miscalculation, reference rate, renovation, ancillary charges), which activate the
nodes that do carry obligations, and it requests 10.0.

The four development scenarios were unrepresentative of the scope in exactly the way that mattered. A3 was
declared before the held-out data was read and is therefore in the record rather than hidden, and the original
primary it demoted is reported above — which is the whole reason preregistration is worth doing. But the amendment
was wrong, and it was wrong because development data can be unrepresentative in ways a split on scenarios does not
prevent.

b5 wins on **all six** held-out scenarios individually (0.481–0.630), so this is not one scenario carrying the
result.

### Honest cost

`b5_induced_graph` has the **worst retention** of the three (0.544 against 0.573 and 0.641). It withdraws
aggressively and drops documents it should have kept. It satisfies the preregistered tolerance (−0.029, within
−0.050) but the trade is real: it is right about *what* to release far more often, and it releases too much.

## 4. What the verification gate caught

Of 58 quotes proposed for the reference contract, 44 verified verbatim against the Fedlex passage each was
attributed to. One failure was a fabrication of a kind reading cannot catch: `vmwg-art-19a-20251001-de`, cited at
a consolidation date Fedlex does not serve, for an article that exists at no consolidation, with a fluent and
sourceless quote. See `CITATION_FIDELITY.md`, which also retracts a cross-scope fabrication rate that turned out
to be an artifact of how the other contracts store their citations.
