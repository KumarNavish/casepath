# Clean-room references for the development designs (2026-11-12)

Development material, not a result. Two blind evaluator sessions (AI sessions,
no person checked them) each wrote an evaluator for the three regimes from
`cleanroom_bundle/` alone: the prose rule text, the document catalogue and the
designed fact states. They saw no workflow, no `rules.json`, no engine output
and not each other. Their programs and notes are in
`<regime>/cleanroom/evaluator_a/` and `evaluator_b/`.

| Regime | Files | Document decisions | Engine = A | Engine = B | A = B (bytes) | Holds, same waited-for fact |
|---|---|---|---|---|---|---|
| Tenancy | 60 | 354 | 354 | 354 | yes | 17 of 17 |
| Theft | 60 | 450 | 450 | 450 | yes | 13 of 13 |
| Dismissal | 60 | 436 | 436 | 436 | yes | 49 of 49 |

Numbers from `CLEANROOM_COMPARISON.json` (the engine's reference is the
product's evaluator at the tested commit under the intake convention).

What the evaluators read differently without any effect on these designs, to
be settled in the rule text before any freeze:

- An always-stated fact that a design nevertheless leaves unmentioned:
  evaluator A took it as unresolved, evaluator B as absent under the general
  convention. The generator leaves such a fact unmentioned only where its step
  cannot be reached, so no document depends on it.
- Whether "its absence would end the process" is judged per file or per fact
  (dismissal, `objection_submitted` and `action_in_time`): both evaluators
  followed the per-fact line of the type's own presumption list.
- A supplied optional document after a stop, and a supplied document that is
  not needed: both took "not needed"; no design has the case.

Breaches reported by the evaluators: evaluator A tried once to list the shared
parent folder and was refused; evaluator B listed its own three output folders
with a glob, wrote three temporary files to a scratch folder and deleted them.
Neither saw the other's work by their reports.
