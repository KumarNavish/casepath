# Evaluator B: semantics used for the tenancy regime

Sources read: only `cleanroom_bundle/{TASK.md, SCHEMA.md, rule_text.md, catalogue.json, designs.json, BUNDLE_MANIFEST.json}`.
Program: `evaluate.py` (generic engine + the rule text encoded as data). Output: `reference.json` (60 files, 354 documents).

## Fact values

- `stated_true` = yes. `denied` = no.
- **Raised and left open**: unresolved. The rule text says: "A step or document whose condition depends on an unresolved or open answer waits for that answer."
- **Not mentioned**: decided by each question's own line "If not mentioned", which "says how the convention applies to it":
  - "taken as no": the branch questions of all three types;
  - "unresolved (the defining event is never presumed)": `defect_present`, `notice_received`, `increase_applied`;
  - "unresolved (this fact has no ordinary default)": `cost_or_services_reason`, the question marked "Always stated" (A1).
- **Denied defining event**: "If the claim states that the type's defining event did not happen, the process ends and no document is requested". The stop reads "if question 1 is no, the process ends". So every document is `not_needed`.
- **Open or unmentioned defining event** (ten_580485dac025, ten_ba90f9b8b195): unresolved, so the first step's documents are `hold`, waiting for the defining event. Later-step documents are `hold` if they would be needed when the event is yes, and `not_needed` if they would not be needed under any answer.

## Steps, stops, documents

- I take the steps in the order given, each one "when its condition holds". "A document is requested when its step is reached and its own condition holds." Documents prefixed "Request X, if question N is yes/no" carry that question as their own condition.
- **Stops**. Each type has one stop, on question 1. I place it at the first step, whose condition is question 1 = yes. "A stop ends the process at its step: no later step is reached, and no document of a later step is requested or left waiting."
- **Unresolved facts**. I complete every unresolved fact both ways and compute the document state under each completion.
  - Same state under every completion: that state. A step reached under every answer gives `request`, `present_sufficient` or `present_insufficient`. A step reached under no answer gives `not_needed`.
  - States differ (a step reached under some answers only, or the document's own condition is unresolved): `hold`. `waits_for` lists the unresolved facts that change the state when flipped alone. This follows "A step or document whose condition depends on an unresolved or open answer waits for that answer."
- **Optional and conditional documents**. The rule text marks no document optional. Every listed document is requested when its step and condition hold. A conditional document whose condition is no is `not_needed`. One whose condition is open or unresolved is `hold`.
  - Example: `knowledge_proof` "if question 3 is no". Here "Where the claim states that the landlord was told only orally, no such record exists and none is requested."

## Supplied documents

- Needed and supplied: `present_sufficient` or `present_insufficient` as designed. Needed and not supplied: `request`.
- Supplied but not needed: `not_needed`. The `present_*` states require "Supplied, needed".
- Supplied but held: `hold`. The copy does not answer the open question on which the need depends.
- Neither of the last two cases changes a result in these designs.

## Ambiguities

- **A1. `cost_or_services_reason` not mentioned.**
  - The general convention would take an unmentioned fact as absent unless its absence ends the process, and its absence ends nothing here. The question itself says "If not mentioned: unresolved (this fact has no ordinary default)".
  - Choice: the question's own line. The text says these lines say "how the convention applies to it".
  - Effect in these designs: none. Wherever it is unmentioned, the "justified" step is not reached because the increase is graduated or index-linked.
- **A2. Placement of the stop.** The stop is not attached to a step by name. I attached it to the first step (reached when question 1 is yes). The alternative, a separate step before it, gives the same result.
- **A3. Rent-increase step order.** Two increase steps can both be reached in one file: the "termination with the increase" step and one of graduated, index or justified. They are independent, and no stop sits between them. All reached steps' documents are decided.
- **A4. `waits_for` names only the pivotal unresolved facts**, not every unresolved fact of the file. An example is ten_0c74f4037e13: `payment_demand` and `hardship_evidence` both wait for `arrears_termination` only.
