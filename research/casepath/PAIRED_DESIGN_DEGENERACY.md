# The paired design does not escape the degeneracy it was built to escape

This is the correction that reframes the paper. It was found by an adversarial review panel and verified against
committed artifacts.

## The claim that fails

We diagnosed the static checklist task as degenerate (one distinct ground-truth checklist across 30 cases; a
case-ignoring modal predictor at F1 1.000) and built a **paired branch-intervention design** to escape it, arguing
that scoring *change* is immune to a constant level. That argument is wrong, and our own data refutes it.

## The diagnostic we failed to run

**A constant-output oracle.** Ignore the case entirely; always withdraw the modal expected-release set (5
documents), computed from ground truth alone.

| | withdrawal recall |
|---|---|
| **constant-withdrawal oracle (ignores the case)** | **0.947** (125/132) |
| b5_induced_graph, gpt-5.6-terra — our best arm | 0.591 — **62% of the oracle** |
| b5_induced_graph, gemini-2.5-flash | 0.189 — 20% |
| b5_induced_graph, haiku / deepseek | 0.000 — 0% |
| b1_direct, all four models | 0.038–0.045 — **4–5%** |

**No arm reaches two thirds of a predictor that does not read the case.** The dynamic task is degenerate in exactly
the way we condemned the static task for being, and we did not check.

## Why: both sides are near-constant

**The target is near-constant.** Across 28 pairs there are **3 distinct expected-release sets**, and the modal one
accounts for 90 of 132 expected releases (68.2%).

**The winning arm is constant.** Distinct request sets across the 28 pairs:

| arm / model | distinct request sets | distinct withdrawal sets |
|---|---|---|
| b5_induced_graph / gpt-5.6-terra | **1 / 28** | 2 / 28 |
| b5_induced_graph / gemini-2.5-flash | **1 / 28** | **1 / 28** |
| b5_induced_graph / deepseek-v3.2 | 1 / 28 | 2 / 28 |
| b5_induced_graph / claude-haiku-4.5 | 2 / 28 | 2 / 28 |
| b1_direct / gpt-5.6-terra | 21 / 28 | 15 / 28 |
| b3_graph_then_list / gpt-5.6-terra | 16 / 28 | 18 / 28 |

The pipeline emits **one document set for every case**. Its "+0.119 excess" is a fixed output partially matching a
near-fixed target. The arms that actually vary with the case — `b1_direct` at 17–22 distinct sets of 28 — score
*worst*, because varying against a near-constant target is penalised.

**So the headline sign reversal is between two constant functions that picked different constants.** With one
distinct withdrawal set per model, the effective sample for the reversal claim is **one decision per model**, not
28 pairs or 6 scenarios. The reported intervals, which resample scenarios, do not represent that.

**And the two "anti-correlated" cells have recall exactly 0.000** — a floor effect. An arm that withdraws almost
nothing scores below its own random baseline by construction; that is not evidence of anti-correlation.

## The volume control does not catch this

Our per-arm random-drop baseline corrects for *how many* items an arm drops. It cannot detect that an arm drops
**the same items every time**. A constant arm and a case-responsive arm with identical drop counts receive identical
corrections. The control is necessary and insufficient.

**The diagnostics that do catch it**, both cheap and both computable from any run log:
1. **Distinct-output count** — `|distinct outputs| / n`. Below ~0.2 the system is not reading the case.
2. **Constant-output oracle** — the best achievable by ignoring the input. If no system beats it, the task cannot
   support a claim.

## A second confound, independently fatal

**The ground truth was authored by the model that wins.** `runners/conf_ref.py` and `runners/term_ref.py` both call
`model="openai/gpt-5.6-terra"`. Every reference set — the target every arm is scored against — was produced by the
same model that produces the only positive result. Every "adjudicator unanimity" figure (93%, 88%, 66%) is
self-consistency across three temperature-0 samples of **one** model, not agreement among independent judges.

This is not recoverable by re-analysis. It requires re-adjudicating with a different model, which the exhausted
compute budget does not permit, and it must be stated as a limitation that bounds the entire rent-increase result.

## What survives, and what the paper now claims

**Withdrawn:** that the compiled pipeline carries signal; that direct prediction is anti-correlated; that the
paired design escapes degeneracy. All three rested on the above.

**Strengthened, and now the paper's thesis:** the obvious evaluation of a structured legal-requirement system is
degenerate in *four* compounding ways — a near-constant label, a near-constant system output, a volume artifact
worth 4.7×, and an adjudicator drawn from the systems under test. We fell into all four while explicitly hunting
the first, and the diagnostics that expose them are three cheap numbers nobody reports: distinct-output count,
constant-output oracle, and adjudicator provenance.

That is a stronger and more useful contribution than the method claim, and unlike the method claim it is what the
evidence supports.
