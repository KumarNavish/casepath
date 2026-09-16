# The static checklist task is saturated on intake messages, and why that reshapes the claim

Measured on 15 real rent-increase cases against the source-built reference contract.

## The measurement

| | |
|---|---|
| cases | 15 |
| distinct reference checklists | **2** |
| cases sharing the modal checklist | **14 of 15** |
| mean checklist size | 9.5 of 11 contract documents |
| mean open decisions | 10.5 of 12 |
| adjudicator unanimity per decision | 84% |

Fourteen of fifteen cases require the identical ten documents. A predictor that ignores the case entirely and
emits the modal list scores 0.97 F1 on this corpus. **The static task cannot separate any two methods here**, and
any gap reported on it would be noise dressed as a result.

## Why — and why it is not a defect in the contract

The contract is not degenerate. Sampling open-sets at random over its twelve decisions reaches **19 distinct
checklists**, so the contract expresses real variation. The variation does not reach real cases because of how
document requirements are distributed across decisions:

| requiring decisions | document |
|---|---|
| 8 | rent_increase_official_form |
| 6 | lease_contract |
| 6 | landlord_correspondence |
| 2 | envelope_copy, registered_mail_receipt |
| 1 | tenant_correspondence (D3) |
| 1 | comparable_rents_evidence, cost_increase_statement, previous_rent_statement, property_management_statement, renovation_cost_statement (all D12) |

Five of eleven documents are required by six or more decisions. Closing one of those decisions changes nothing,
because five others still demand the same document. Only **D3** (when the notification was received) and **D12**
(whether the rent is substantively abusive) own documents no other decision requires.

And those are exactly the decisions a first customer message does not settle. Across the 15 cases the adjudicators
settled D11 nine times, D5 and D6 four times each — and D3 and D12 once each. Every frequently-settled decision is
one whose documents are shared. The checklist therefore sits still.

This is a property of the domain, not of the method or the corpus. A first-contact message states a grievance; it
does not resolve the receipt date or the substantive rent calculation. Redundant evidentiary requirements are
normal in procedural law — one document serves many determinations — and redundancy is precisely what makes a
static checklist insensitive to the case.

## What follows

Three things, and the first two are concessions.

1. **No static-checklist claim can be made on this corpus.** Any F1 comparison between arms on these 15 cases is
   uninformative, and reporting one as evidence would be misleading regardless of which direction it fell. It is
   reported below as a floor check — does a method reach the ceiling everything else reaches — and nothing more.

2. **Scope admission must screen for checklist variation, not only for source sufficiency.** The frozen admission
   protocol tests whether authoritative sources support a process. It does not test whether the induced
   requirements differ across real cases. A scope can pass source sufficiency and still be untestable statically.
   This is a gap in the protocol, found by running it.

3. **The discriminating evidence is dynamic.** The question that separates a process-derived checklist from a
   predicted one is not *which documents* but *what happens when a fact arrives*. A direct predictor has no
   mechanism for withdrawal: it re-predicts, and any change is incidental. A process-derived checklist withdraws a
   document exactly when every node that required it closes, and can say which one.

The branch-intervention design tests that directly, and it targets D3 and D12 — the two decisions whose closure is
observable in the document set. This was not chosen to flatter the method: they are the only decisions in the
contract where withdrawal is measurable at all, which is the same structural fact that saturates the static task.

## Honest statement of the limitation

Targeting the two decisions with unique documents means the causal result speaks to those two branches of this
scope, not to the scope as a whole. A second scope with a flatter document-to-decision mapping is needed before the
dynamic claim can be stated generally. That is a load-bearing limitation and belongs in the paper, not a footnote.


---

# It is two scopes, not one

Termination was built independently — its own spine, its own gate pass, its own voted document layer, its own
catalogue of 18 — and measured the same way on 49 cases across 8 scenarios.

| scope | cases | distinct reference checklists | mean reference set | catalogue |
|---|---|---|---|---|
| rent increase | 30 | **1** | 10.0 | 11 |
| termination | 49 | **1** | 17.0 | 18 |

Termination is the more saturated of the two: the contract requires 17 of its 18 documents in every case measured.
Both scopes **fail C8**, the observed-branch-closure criterion added as amendment A1 after rent increase exposed
the gap — and A1 was written before termination existed, so this is the criterion catching a second case rather
than being fitted to one.

The cause is the same in both. A document is released only when *every* decision requiring it is settled, most
documents are required by several decisions, and a first-contact message settles the redundant decisions rather
than the discriminating ones. This is not an artifact of one contract's granularity: two contracts built by the
same procedure from different acts, with different decision counts (12 and 21) and different catalogues, land in
the same place.

**Consequence for the benchmark, not just for this paper.** A static document-checklist task over intake messages
in Swiss tenancy cannot separate methods, and a benchmark built that way would report noise however carefully it
was scored. What separates methods is what happens when a fact arrives — which is why the intervention design is
the measurement here and the static table is reported only as a floor.
