# Where the unjustified changes fall

**Revision 2, after parent review. Verified counts and bounded wording. No `.tex` file edited.**

Regenerate with `python3 analyze_spurious_origin.py` → `SPURIOUS_ORIGIN.json`,
`table_spurious_origin.tex`. Released files only, no inference. The script asserts its per-arm
totals equal the preserved report's spurious counts (15 / 27 / 41 / 52) and fails otherwise.

Revision 1 claimed the comparators' error class "disappears" for CasePath, and read the zero
withdrawals as monotonicity from a single branch turning on. Both were overstated. The review was
right on all three points; what follows is what the benchmark's own fields actually support.

## Verified partition

A document is **branch-governed** if it appears in any unit's `gold_branch_documents` or in any
pair's `acceptable_signed_deltas` (12 documents). Each spurious change is then:

| Method | Spurious | governed, required in one unit of this pair | governed, elsewhere only | not branch-governed | added | withdrawn | distinct docs |
|---|---|---|---|---|---|---|---|
| CasePath | 15 | 3 | 3 | **9** | 15 | 0 | 5 |
| Direct | 27 | 0 | 0 | 27 | 16 | 11 | 9 |
| Graph as context | 41 | 0 | 0 | 41 | 18 | 23 | 8 |
| Evidence-first | 52 | 0 | 0 | 52 | 22 | 30 | 11 |

**The claim this supports.** All 120 unjustified changes made by the three comparators move
documents that are not branch-governed anywhere in this benchmark. CasePath makes 9 such changes
rather than 27, 41 or 52, and 6 of its 15 land on branch-governed documents, 3 of them on a document
this very pair governs. The class is **reduced, not eliminated**.

**What `not branch-governed` does not mean.** It means outside the 12-document union above. It does
**not** establish that the document is a universally required baseline, and it does not establish
that no source branch governs it. The benchmark fixes branch documents and signed deltas; it
contains no full per-unit reference checklist, so stable-baseline status cannot be tested from it.
Any wording asserting "documents every claim needs anyway" is unsupported and must not be used.

## Direction, and the monotonicity bound

All 33 justified changes on this split are additions, so each withdrawal any system makes is
unjustified: 11, 23 and 30 for the comparators, 64 in total. CasePath withdraws none.

**The bound.** The reference intervention edits one sentence, but the controller's extractor changed
more than one guard on **21 of 27 pairs** (guards changed per pair: 0 on 3, 1 on 3, 2 on 12, 3 on 3,
4 on 3, 5 on 3). The assessed-state transition is therefore not a single branch turning on, and zero
withdrawals cannot be derived from monotonicity over a fixed rule set. It is an observed count on
this split, and nothing stronger should be written.

**One invariant that is verified.** No pair produced a predicted change without a changed guard: the
3 pairs whose extractor changed no guard predicted no change at all.

## Claim boundary

**Supported.**
1. All 120 comparator spurious changes are not branch-governed anywhere in this benchmark.
2. CasePath makes 9 such changes; 6 of its 15 are branch-governed, 3 on the pair's own branch.
3. All 33 justified changes are additions; the comparators' 64 withdrawals are all unjustified;
   CasePath made none on this split.
4. No predicted change occurred on any pair whose extractor changed no guard.

**Not supported.**
1. That the error class disappears for CasePath. It does not; 9 of 15 remain in it.
2. That non-governed documents are universally required baselines, or ungoverned by any source
   branch. Untestable from this benchmark.
3. That zero withdrawals follow from monotonicity. 21 of 27 pairs change more than one guard.
4. Any statistical claim. This partitions frozen outputs the report already scored; it does not
   revive the failed broad-superiority gate.
5. Anything about unseen rules, policies or domains. Held-out contexts only.

## Benchmark field inconsistency found

Amendment V3 added the bicycle purchase voucher to `expected_added` and `acceptable_signed_deltas`
but not to `gold_branch_documents` or `branch_document_universe`, which still list 11 documents.
Scoring uses the amended fields, and the voucher never appears as a spurious atom, so **no reported
number changes** and the partition above is identical under either definition. The two auxiliary
fields are nonetheless stale with respect to the amendment. Worth a release note; not a result.
