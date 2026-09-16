# The confirmatory run is withheld, because its result is determined before it is run

The primary outcome cannot come out positive on this scope. Not "is unlikely to" — cannot, for structural reasons
that are computed from the two frozen artifacts without running a single case. Spending 30 held-out cases to
observe a predetermined zero would waste the only clean data left and would dress a structural fact as an
empirical finding.

## The computation

Withdrawal happens on each side only when *every* source of a document is closed.

On the **contract** side, a document is released when every decision requiring it is settled. On the **B5** side, a
document is released when every graph node whose obligations supply it goes inactive. Both are deterministic given
the artifacts.

| probe | documents the contract releases | documents B5 can release | intersection | max achievable recall |
|---|---|---|---|---|
| `e03` the notice does use the prescribed form | 0 | 3 | 0 | **0.000** |
| `e06` the tenant did challenge in time | 1 | 0 | 0 | **0.000** |
| `e07` the tenant did not challenge in time | 6 | 1 | 0 | **0.000** |

On `e07`, the probe the preregistration selected, the contract releases
`comparable_rents_evidence`, `cost_increase_statement`, `previous_rent_statement`, `property_management_statement`,
`renovation_cost_statement`, `tenant_correspondence`. B5 can release `conciliation_request`. The sets do not
intersect at all.

## Why they do not intersect

Every document the contract releases belongs to **D12**, the substantive abusiveness review under OR 269 and 269a
— comparable rents, cost-increase statements, renovation accounts, the previous rent, the managing agent's
statement. Settling that one decision is what frees them.

**The induced graph has no node for that review.** Its downstream half is procedural: the decision to challenge,
the conciliation request, the hearing, agreement or its absence, the authorization to sue, the court filing. It
models the *forum* in which abusiveness would be argued and never models the *determination* itself, although the
corpus contains the passages and the induction had them.

So the graph's releasable document is a procedural artefact the contract never required, and the contract's
releasable documents are evidentiary materials the graph never demanded from a node that can close. The two sides
are disjoint by construction.

This is the third consequence of the divergence recorded in `INDEPENDENT_INDUCTION_DIVERGENCE.md`. It first cost a
metric, then an experiment's design, and now the experiment itself.

## The compounding defect

The obligation compiler covers the graph thinly. Across the development cases, **8 of 13 nodes emit no obligation
at all** and therefore demand nothing whatever their activation; `rent_increase_notified` alone produces 10 of 18
chains, and `rent_increase_official_form` appears in 13 of them. A node that demands nothing releases nothing when
it closes, so sparse coverage caps withdrawal independently of which branch an intervention settles.

This also explains the static picture: B5 requests 2–3 documents where the contract requires about 10, at precision
1.000 and recall 0.20. It is not wrong about what it asks for. It asks for very little, because most of its process
carries no evidentiary obligation.

## What is being reported instead

1. The static floor check on clean development cases, which the saturation finding already says cannot separate
   methods, reported as a floor and not as a comparison.
2. The pre-fix development baseline, where the direct arm's apparent responsiveness turns out to be 76% spurious.
3. The branch-consistency fix and its effect, which visibly unfreezes the process arm.
4. These three structural defects, each found by measurement rather than by inspection: no applicability gate,
   contradictory branch verdicts (fixed), and sparse obligation coverage.

No claim is made that the method withdraws documents correctly. The evidence for that claim does not exist, and
this document records why it could not have been obtained from the experiment as designed.

## What would be needed

The confirmatory scenarios stay unread and usable. Making the claim testable requires induction and compilation to
cover the substantive determinations, not only the procedural path — concretely, a node for the OR 269/269a review
with obligations attached, and obligation coverage across nodes rather than concentrated at the entry. Those are
method changes, they belong on development data, and after them the preregistration must be rewritten with the
changes logged before the held-out set is touched.

Deciding this before spending the held-out data, rather than after, is the only reason that data is still worth
anything.
