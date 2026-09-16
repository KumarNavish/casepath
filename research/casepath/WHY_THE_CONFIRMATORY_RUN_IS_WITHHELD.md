> **SUPERSEDED.** The confirmatory run was subsequently executed and read once; see `RESULTS.md` §2. This document
> is retained because it contains an error I made and corrected — a false proof that the primary outcome was
> structurally impossible — and the correction is part of the record. Its current decision section is obsolete.

# Withholding the confirmatory run — the original argument was wrong, and the corrected one is weaker

**This document previously claimed that the primary outcome was structurally impossible: that B5's maximum
achievable withdrawal recall was 0.000 on every probe, computable in advance. That claim was wrong, and the
development data refute it. The error and the corrected position are both below, because the wrong version was
committed and acted on.**

## The error

The ceiling was computed by pooling, across the cases already run, the set of documents each graph node's
obligations supply — then asking which documents would be released if a given set of nodes went inactive. A
document was counted releasable only if *every* node supplying it closed.

The compiler does not work that way. It recompiles per case, so a node's supply set is not fixed: pooling took the
**union** across cases and attributed to every node every document it had ever supplied in any case. That makes
release look impossible when in a particular case the node supplies less. The pooled map is an upper bound on
supply and therefore a lower bound on release, and I read it as if it were exact.

Measured on 9 development pairs, B5 withdrew `cost_increase_statement` and `renovation_cost_statement` correctly —
documents the pooled computation said it could never release.

## The corrected position

The ceiling is not zero. It is low, and the measured performance is low.

**e07, the tenant did not challenge within 30 days — 9 development pairs.** The reference contract withdraws a
mean of 4.56 documents, non-empty on 8 of 9, so the probe bites.

| arm | withdrawal recall | withdrawal precision | retention |
|---|---|---|---|
| b1_direct | 0.024 | 0.143 | 0.838 |
| b3_graph_then_list | **0.122** | 0.500 | 0.844 |
| b5_induced_graph | 0.073 | **0.600** | **0.900** |

B5 − B1 on recall: **+0.049, 95% CI [+0.000, +0.133]**, bootstrapped over 2 scenarios. The interval includes zero
and two scenarios cannot support an interval anyway.

Per pair, B5 withdrew nothing at all on 5 of 9. Across all 9 it made 2 correct withdrawals against 41 expected.
Its most common withdrawal is `conciliation_request`, four times — correct as process reasoning, since no
challenge means no conciliation, but the contract never required that document, so it scores as a false
withdrawal every time.

**The claim is not supported by development data.** B5 has the best precision and retention of the three arms and
the second-best recall, behind `b3_graph_then_list`, which has no compiler at all. Nothing here separates the arms.

## What actually stands

The disjointness argument was overstated but not empty. The contract's releasable documents belong overwhelmingly
to D12, the substantive abusiveness review, and the induced graph has no node for that determination — its
downstream half models the forum, not the question. That is why B5's withdrawals land on procedural artefacts the
contract never asked for. This remains the best explanation of the low recall; what it does not license is the word
"impossible".

The obligation-coverage defect also stands: 8 of 13 nodes emit no obligation whatever their activation, and one
node produces 10 of 18 chains.

## Current decision on the held-out set

Still not run, but for a different and weaker reason. On development the effect is small, its interval includes
zero, and the arm ordering does not favour the method. A preregistered null is a legitimate result and would be
worth reporting — but the two induction defects above are known, specific, and being repaired on development data
now. Spending the held-out set to measure a system with known repairable defects, when the repair is in progress,
would waste it.

The decision is therefore: read the held-out set once, after the repaired method is evaluated on development and
the preregistration is rewritten with the changes logged — **or** read it to report a preregistered null if the
repairs do not change the development picture. Either way it is read once, and the six confirmatory scenarios
remain unread until then.
