# Why CasePath makes fewer unjustified changes

**For the manuscript rewrite. Evidence and drop-in text; no `.tex` file was edited to produce it.**

Regenerate with `python3 analyze_spurious_origin.py` → `SPURIOUS_ORIGIN.json`,
`table_spurious_origin.tex`. Reads only released files; the per-pair reference realisation is the
frozen scorer's own choice, and the script asserts its totals equal the preserved report's
spurious counts (15 / 27 / 41 / 52).

## The finding

Aggregate counts say CasePath makes fewer unjustified changes. This says they are a **different
kind** of error, which is what turns the number into an explanation.

Each held-out pair intervenes on exactly one branch concept, and every reference atom in this
benchmark belongs to exactly one concept (12 atoms, no overlap), so each spurious change can be
attributed to the intervened branch, another branch, or no branch at all.

| Method | intervened branch | another branch | no branch | added | withdrawn | distinct docs |
|---|---|---|---|---|---|---|
| **CasePath** | 3 | 3 | 9 | 15 | **0** | 5 |
| Direct | 0 | 0 | 27 | 16 | 11 | 9 |
| Graph as context | 0 | 0 | 41 | 18 | 23 | 8 |
| Evidence-first | 0 | 0 | 52 | 22 | 30 | 11 |

**Every one of the comparators' 120 spurious changes moves a document that no branch governs.**
Not one is a branch error. The documents they move are the ones every household-theft claim needs
regardless of any branch: the claim notification form, the payment instruction, the itemised list
of stolen objects, the double-insurance declaration. Direct moves the claim notification form 8
times; Graph moves the itemised list 11 times.

So the comparators are not slightly worse at branch reasoning. Between two cases differing by one
sentence, their checklists wobble in documents the sentence cannot touch. CasePath's plan is a
projection of active rules, so a document can only move when a guard moves, and that entire error
class disappears. Its 15 errors concentrate in 5 distinct documents, 6 of them inside the branch
vocabulary — the right kind of document, the wrong choice.

## The withdrawal result, stated honestly

All 33 justified changes on this split are additions. No withdrawal is ever correct here, so the
comparators' **64 withdrawals are all unjustified** — 53% of their spurious changes. Withdrawing a
document the claim still needs is the more damaging error: the handler stops asking for something
the case requires.

**State the caveat once, in the same breath.** CasePath's zero withdrawals are a structural
property, not a measured surprise: a branch turning on can only add documents to a projection of
active rules. The honest claim is that the architecture cannot commit this error class, and that on
this split committing it is always wrong. The matching limitation, which belongs in the limitations
paragraph and nowhere else: **the held-out split contains no justified withdrawal, so it does not
test whether a system correctly removes a document when a branch turns off.**

## Drop-in paragraph

> \paragraph{The errors are a different kind, not just fewer.}
> Each pair intervenes on one branch concept, and every reference document in the benchmark belongs
> to exactly one concept, so each unjustified change can be attributed to the intervened branch, to
> another branch, or to no branch at all (Table~\ref{tab:spurious-origin}). Every one of the
> comparators' 120 unjustified changes moves a document that no branch governs: the claim
> notification form, the payment instruction, the itemised list of stolen objects. Between two cases
> that differ by one sentence, their checklists move documents the sentence cannot touch. Because
> \casepath projects its plan from active rules, a document can only move when a guard moves, and
> that error class does not arise; its remaining errors concentrate in five documents, six of the
> fifteen inside the branch vocabulary. The direction is as sharp: every justified change here is an
> addition, and the comparators nonetheless withdraw 64 documents, none of them correctly, while a
> projection of active rules cannot withdraw on a branch that turns on.

## Claim boundary

**May be claimed from this analysis.**
1. Every one of the comparators' 120 unjustified signed changes on the held-out split moves a
   document that no branch concept governs (27 / 41 / 52, all off-vocabulary).
2. CasePath's 15 unjustified changes span 5 distinct documents; 6 of the 15 lie inside the branch
   vocabulary (3 on the intervened branch, 3 on another).
3. All 33 justified changes on this split are additions, so each of the comparators' 64 withdrawals
   is unjustified.
4. Therefore the selectivity difference is a difference in error *class*, not only in error count.

**May not be claimed.**
1. Not a statistical test, and it does not revive the failed broad-superiority gate. It partitions
   the same frozen outputs the report already scored.
2. CasePath's zero withdrawals are structural: a projection of active rules cannot withdraw on a
   branch that turns on. State it as an architectural property, never as a measured surprise.
3. The split contains no justified withdrawal, so nothing here shows that CasePath correctly
   removes a document when a branch turns off. That belongs in limitations, once.
4. "Off-vocabulary" means outside the 12 reference atoms, not outside the 33-document catalogue.
   These are legitimate claim documents being moved for no branch reason, not invented documents.
5. Held-out contexts only; it says nothing about unseen rules, policies or domains.

**Provenance.** `analyze_spurious_origin.py` → `SPURIOUS_ORIGIN.json`, `table_spurious_origin.tex`.
Inputs are released files only. The script asserts its per-arm totals equal the preserved report's
spurious counts and refuses to run if any reference atom spans two concepts. No inference, no new
model call, no change to any frozen artefact.

## Why this serves the submitted abstract

The abstract promises evidence planning that is "selective, traceable, and auditable", and its
headline is 15 false-positive changes against at least 27. This analysis supplies the *reason*:
selectivity is not a better score on the same error distribution, it is the removal of an error
class that unconstrained generation produces by default. It is the mechanism step between the
structure and the benefit, and it needs no new inference, no new model call and no new run.
