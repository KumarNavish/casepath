# Results

Every number below is reproduced from `CANONICAL_RESULTS.json` and the committed intermediates. The analysis
scripts (`development_analysis.py`, `confirmatory_analysis.py`, `transfer_analysis.py`,
`model_generality_analysis.py`) make no network calls.

**The metric.** *Withdrawal recall above the arm's own random-drop baseline.* When a new fact settles a legal
predicate, the reference contract stops requiring certain documents. Withdrawal recall is the fraction of those an
arm stops requesting. Because an arm that requests more items has more to drop, each arm is scored against **itself
dropping the same number of its own requested items at random** (300 draws per pair). Intervals bootstrap over
**scenarios**, 5000 draws, seed 20260916. An interval above zero means the arm's choice of *which* items to drop
carries information; below zero means its withdrawals are worse than chance.

---

## 1. The static checklist task is degenerate on both scopes

| scope | cases | distinct ground-truth checklists | mean reference set | catalogue |
|---|---|---|---|---|
| rent increase | 30 | **1** | 10.0 | 11 |
| termination | 49 | **1** | 17.0 | 18 |

Six arms on rent increase (8 development originals): F1 0.605 (`b1_direct`), 0.601 (`b2_retrieval`), 0.635
(`b3_graph_then_list`), 0.601 (`b3t_summary_then_list`), 0.618 (`b6_prior_composition`), 0.488
(`b5_induced_graph`). A **modal-list oracle that ignores the case scores F1 1.000**. Five of six arms fall within
0.034 F1 of one another, including the minimal obvious fix which uses no law and no graph.

**No comparative claim is drawn from the static task.** It is reported as a floor. Both scopes fail criterion C8
(observed branch closure), which was added to the admission protocol after the first scope exposed the gap and
*before* the second scope existed.

---

## 2. Confirmatory read, rent increase, `gpt-5.6-terra` — 28 held-out pairs, 6 scenarios

| arm | recall | own random baseline | **excess** | 95% CI | |
|---|---|---|---|---|---|
| b1_direct | 0.038 | 0.099 | **−0.061** | [−0.096, −0.026] | anti-correlated |
| b3_graph_then_list | 0.121 | 0.110 | +0.011 | [−0.017, +0.038] | no signal |
| b5_induced_graph | 0.591 | 0.473 | **+0.118** | [+0.106, +0.126] | signal |

**The volume control changes the conclusion.** Uncontrolled, `b5 − b1` reads **+0.553** [+0.459, +0.613]. Four
fifths of that is volume: b5 requests 10.0 documents where the others request ~5.4. The control also changes a
sign — uncontrolled, `b3 − b1` is +0.083 with an interval excluding zero, which reads as b3 being informative; the
control shows b3 carries no signal and the gap exists only because b1 is *below* chance.

The preregistered primary (`b3 − b1`, amendment A3) is therefore **supported for the wrong reason**, and is
recorded with that qualification permanently attached.

---

## 3. The central result — the same artifact reverses sign across reasoners

Same 28 pairs, same frozen graph, same contract, same code, same prompts, same temperature. **Only the interpreting
model changes.**

| model | b1_direct excess [95% CI] | b5_induced_graph excess [95% CI] |
|---|---|---|
| gpt-5.6-terra | **−0.061** [−0.096, −0.026] *anti-corr* | **+0.119** [+0.108, +0.125] *signal* |
| claude-haiku-4.5 | +0.003 [−0.011, +0.016] *none* | **−0.077** [−0.092, −0.070] *anti-corr* |
| gemini-2.5-flash | +0.001 [−0.010, +0.012] *none* | **+0.109** [+0.107, +0.112] *signal* |
| deepseek-v3.2 | +0.010 [−0.026, +0.041] *none* | **−0.034** [−0.037, −0.031] *anti-corr* |

Spread on one identical artifact: **+0.119 to −0.077**, intervals non-overlapping.

**Not an execution failure.** Zero `b5` errors on every model. All four resolve 10–12% of predicates and leave the
rest unresolved at near-identical rates (true/false/unresolved: 27/28/467, 32/28/462, 32/29/461, 13/15/232).
`claude-haiku-4.5` compiles roughly twice as many chains (67.6 vs 31–39) and requests twice as many documents (12.6
vs 6.5–7.4), and still withdraws nothing correct.

**Neither headline effect is a property of the method.** Direct prediction is anti-correlated on **1 of 4** models.
The compiled chain carries signal on **2 of 4**, and is anti-correlated on the other two.

*Note on two figures for the same quantity:* `gpt-5.6-terra / b5` appears as +0.118 [+0.106, +0.126] in §2 and
+0.119 [+0.108, +0.125] here. These are the same measurement computed by two scripts whose random-drop simulations
draw from different RNG streams; the difference is simulation noise of order 0.001.

---

## 4. Transfer to a second scope fails

Termination, 49 pairs, 8 scenarios, one read.

| arm | recall | own random baseline | excess | 95% CI | retention | requested |
|---|---|---|---|---|---|---|
| b1_direct | 0.065 | 0.050 | +0.015 | [−0.011, +0.051] | 0.723 | 6.4 |
| b3_graph_then_list | 0.078 | 0.059 | +0.019 | [−0.008, +0.057] | 0.756 | 6.3 |
| b5_induced_graph | 0.000 | 0.012 | −0.012 | [−0.024, +0.000] | 0.992 | 16.0 |

**No arm's interval excludes zero.** `b5` requests 16 of 18 catalogue documents, retains 0.992, and withdrew 6
documents across 49 pairs, none correct.

**The failure was computable before the run.** The preregistration recorded that settling `DEC-09` releases 3
documents and no other single decision releases more than 1, against 6 for the rent-increase probe. Measured, the
contract released a mean of 1.57 documents per pair. The probe closes 4 graph nodes carrying 1 obligation between
them. There was nothing for the mechanism to release.

---

## 5. What the verification gate caught

Of 58 quotes proposed for the rent-increase reference contract, 44 verified verbatim against the Fedlex passage
each was attributed to. One failure was a fabrication reading cannot catch: `vmwg-art-19a-20251001-de`, cited at a
consolidation date Fedlex does not serve, for an article that **exists at no consolidation**, carrying a fluent,
correctly styled, sourceless quote.

`CITATION_FIDELITY.md` also records a cross-scope fabrication rate of 25–60% that was computed, found to be an
artifact of contracts storing sources and quotes as unmapped parallel lists, and **retracted before publication**.
Once the corpus covered the cited articles, the same termination contract verified at 85.8% (91 of 106).

---

## What this establishes, and what it does not

**Establishes:** that a static document-checklist benchmark in this domain cannot separate methods; that retraction
metrics require a per-arm volume control or they overstate by ~4× and can invert a sign; and that a frozen,
source-grounded process representation does **not** confer correct retraction behaviour independent of the reasoner
interpreting it.

**Does not establish:** that the method works in general. The positive effect holds on one scope of two and two
reasoners of four, and the boundary is not predictable in advance except by the ceiling computation, which
correctly predicted the transfer failure.
