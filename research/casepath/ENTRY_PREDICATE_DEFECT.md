# The induced graph has no gate on its own entry, and the first causal test measured that

The first branch-intervention run produced an arresting pattern: across six paired cases the process arm emitted
the identical eight documents every time, while the direct baseline varied from zero to five. A system that never
changes its answer is either broken or insensitive, and it was worth finding out which before reporting anything.

## What the diagnosis found

The induced graph decides exactly nine predicates:

| edge | condition |
|---|---|
| e02 / e03 | the notice does / does not use the prescribed cantonal form |
| e04 | the increase is due to cost increases or value-enhancing improvements |
| e06 / e07 | the tenant does / does not challenge within 30 days |
| e09 | the tenant requests supporting documents at the hearing |
| e12 / e13 | agreement is / is not reached at conciliation |
| e14 | the landlord files within the 30-day deadline |

On the paired cases, e02 resolved `true`, e03 `false`, and **all seven others stayed `unresolved`** — identically
under both interventions. Zero of nine predicates differed between a case edited to fix the receipt date and the
same case edited to say the increase had been withdrawn.

The reason is structural. The interventions were authored against the *reference contract*, which asks whether an
increase exists, when it was received, and whether it is substantively abusive. The graph has no predicate for any
of those. Its entry node `rent_increase_notified` is a start node with no incoming condition: **the graph assumes
a rent increase was notified and offers no way to falsify that assumption.** An edit saying the increase was
withdrawn lands on nothing. Everything downstream stays `unresolved`, `unresolved` never collapses to inactive by
design, and so every document stays required.

## Two separate faults, and only one is the method's

**The measurement was mismatched.** Interventions defined on contract decisions cannot test a graph that
partitions the process differently — the same divergence recorded in `INDEPENDENT_INDUCTION_DIVERGENCE.md`, now
biting the experiment rather than the metric. A test the method cannot respond to is not evidence about the
method. Repaired by authoring interventions on predicates the graph actually decides, which also map to contract
decisions through shared authorities: e03 (prescribed form) reaches D4–D7, e06/e07 (30-day challenge) reach D3
and D12.

**The graph genuinely lacks an applicability gate.** This one is real and is not repaired by changing the test.
Synthesis produced a process that branches richly downstream while taking its own entry for granted. Swiss law
does condition it — OR 253a and 253b decide whether the abusive-rent provisions reach this object and this lease
at all, and the reference contract makes exactly that its first decision, D1. The induction had those passages
available and built no node from them.

That is a defect worth stating plainly, because it is the failure mode a deployed system would suffer: a process
graph that cannot represent "this scope does not apply here" will keep demanding documents for a dispute the
claimant does not have. It also explains an earlier observation that looked like adjudicator noise — out-of-scope
termination cases scored against this contract produced the full modal document list, for the same reason.

## What was corrected, and what was not

Corrected: the intervention targets, and a field-name bug in the justification metric that read `authority_id`
from propositions which name their passage `source_id`. With that fixed, 9 of 12 contract decisions have a graph
counterpart through shared authorities — the artifacts overlap considerably more than the first reading suggested.

Not corrected: the missing entry gate. Repairing it means changing synthesis to require an applicability
predicate wherever the sources condition the scope's reach, then re-inducing. That is a method change, it belongs
on development data only, and the confirmatory scenarios stay unread while it happens. Until it is made and
re-measured, no claim is available about how the method behaves when a case falls outside its scope.
