# Transfer preregistration — termination

Written before any termination case is run. The frozen method is applied to a second scope with **no tuning**:
same modules, same model, same temperature, same prompts, same scoring. Only the corpus, the contract, the graph
and the catalogue are scope-specific, and all four are built by the same procedures.

## Why this exists

The confirmatory result rests on one scope. If it is a property of the method it should appear on a second scope
built the same way; if it is a property of rent increase it should not. Either outcome is reported.

## What was built, and by which procedure

| | |
|---|---|
| corpus | +44 passages fetched for the termination articles, same extraction identity; 130 total |
| contract | the independent termination spine put through the **same verbatim-quote gate**: 91 of 106 quotes verified (85.8%), 21 of 21 decisions retained |
| document layer | three independent authors from the gated spine, admitted on 2 of 3, catalogue-restricted — 0 off-catalogue proposals, 54% unanimity |
| graph | induced from the 139 propositions scoped to the contract's authorities; 24 nodes, 18 conditional transitions |

The 85.8% verification rate is worth recording against my own earlier retraction: measured before the corpus
covered the cited articles this same contract scored 50.6%, which is why that figure was retracted as an artifact
of coverage rather than reported as fabrication.

## Probe, chosen structurally before running

Computed from the contract alone: settling **DEC-09 (extension excluded)** releases 3 documents —
`bank_statement`, `payment_deadline_warning_letter`, `rent_payment_records`. No other single decision releases more
than 1. The graph's matching predicate is **e05, "an exclusion applies"**, which closes 4 nodes and 1 obligation.

The intervention is a minimal factual addition establishing a statutory extension exclusion. Expected withdrawal is
3 documents per case where the contract leaves that decision open — half the rent-increase probe's 6, which is the
ceiling this scope offers.

## Primary outcome

**Withdrawal recall above each arm's own random-drop baseline**, comparing `b5_induced_graph` against
`b1_direct`, bootstrapped over scenarios.

The volume control is primary here, not an afterthought. On rent increase the uncontrolled figure overstated the
pipeline roughly fourfold, and the arms request different amounts on this scope too.

**Supported** if `b5`'s excess over its own random baseline has an interval excluding zero *and* exceeds
`b1`'s. **Refuted** if `b5`'s interval includes or lies below zero. **Uninformative** if fewer than 15 pairs have a
non-empty expected withdrawal.

## Stated in advance

Rent increase found `b1_direct` **anti-correlated** with correct withdrawals — its interval lay entirely below
zero. Whether that reproduces here is the single most interesting thing this transfer can show, and it is not
required for support.

No amendment after the first termination result is read.

---

## Amendment T1 — 2026-09-16 — enlarge the sample; no arm outcome has been computed

**The uninformative condition triggered.** On 24 pairs (3 per scenario), **13** have a non-empty expected
withdrawal against a threshold of 15. Under the plan above, no primary comparison may be reported.

**State of my own knowledge when making this amendment.** I have computed the reference sets and their properties
— pair count, unanimity, expected-withdrawal sizes per scenario — and nothing else. I have **not** run
`transfer_analysis.py`, and no withdrawal recall, precision, retention or control figure exists for any termination
arm. The only arm output I have seen is the per-unit *request count* printed by the run log (b5 requests about 17
of 18 catalogue documents), which is a property of the request, not of its correctness.

**Why the sample, not the design, is at fault.** The non-empty rate is 13/24 ≈ 54%, and it is not uniform: two of
the eight scenarios — `T5_conflicting_notices` and `T6_two_notices` — yield **zero** expected withdrawal in every
case, because they are service-defect disputes in which no extension question arises for `DEC-09` to settle. The
other six average 2.8. Three cases per scenario was simply too few.

**The amendment.** Extend from 3 cases per scenario to all **50** termination cases, which at the observed 54%
rate gives roughly 27 non-empty pairs. This changes the number of cases per scenario and **not** the scenario mix,
the probe, the arms, the metric, the contract, the graph, or the criteria. The two structurally-zero scenarios stay
in and will continue to contribute zeros, which is correct — they are part of the scope.

**Why this is a power decision and not fishing.** The criterion it responds to is about whether the data can
support an estimate, and its own wording says a trigger "would mean the intervention does not bite on these
scenarios, which is a property of the scenarios, not evidence about the arms". Adding cases within the same eight
scenarios tests that property with more data; it cannot select a scenario mix that favours any arm, and no arm
outcome was available to select on.

If the enlarged sample still yields fewer than 15 non-empty pairs, the transfer is reported as uninformative and
no comparison is given. One read after that, and no further amendment.
