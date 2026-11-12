# Evaluator A: tenancy semantics

Program: `evaluate.py` (run `PYTHONDONTWRITEBYTECODE=1 python3 -I evaluate.py catalogue.json designs.json reference.json`).
Each step and document condition in `rule_text.md` is encoded as a boolean expression and evaluated in
three-valued (Kleene) logic over yes / no / unresolved answers.

## Fact states

- `stated_true` -> yes; `denied` -> no.
- `raised_and_left_open` -> unresolved: "A fact that the file raises and leaves unsettled is open." and "A step or
  document whose condition depends on an unresolved or open answer waits for that answer."
- `not_mentioned` -> the question's own "If not mentioned" line: "taken as no" for every branch question;
  "unresolved (the defining event is never presumed)" for the three defining events; "unresolved (this fact has no
  ordinary default)" for `cost_or_services_reason`. The general convention ("A fact that the file does not mention is
  taken as not alleged ... Silence never ends a process") agrees: the only stop is on the defining event.

## Defining event

- Denied: "If the claim states that the type's defining event did not happen, the process ends and no document is
  requested." Every step requires question 1 = yes, so every document is `not_needed`.
- Open or not mentioned: every document whose step requires question 1 = yes is `hold`, waiting for the defining event
  (plus any other unresolved fact its condition still depends on).

## Steps and documents

- A document's need = (its step's condition) AND (its own condition): "a document is requested when its step is
  reached and its own condition holds."
- Reached under every answer (condition true): `request`. Reached under some answers only (condition unresolved):
  `hold`, `waits_for` = the unresolved facts the three-valued result depends on (a conjunct already false decides
  the result by itself, so its unresolved siblings are not listed). Condition false: `not_needed`.
- `waits_for` lists facts in catalogue order.
- Steps without documents (graduated-rent agreement, index clause) produce nothing.

## Optional and conditional documents

The tenancy text marks no document optional; every document is requested when its conditions hold. Conditional
documents ("if question N is yes/no") are handled as above.

## Supplied documents

- Needed and supplied: `present_sufficient` / `present_insufficient` as designed ("Supplied, needed, and the copy is
  sufficient" / "... insufficient, so it must be requested again").
- Supplied but held or not needed: state stays `hold` / `not_needed` (the present_* states require "needed").
  No design in this set actually produces this case.

## Stops

"A stop ends the process at its step: no later step is reached". The only stop (question 1 = no) is already a
conjunct of every step's condition, so evaluating step conditions applies it.

## Ambiguities

1. Supplied document that is not needed or held. Options: keep `not_needed`/`hold`, or report it as present.
   Chosen: keep, because the table defines present_* as "Supplied, needed". (No effect on this design set.)
2. `cost_or_services_reason` is labelled "Always stated" yet its default is "unresolved". Chosen: unresolved when
   not mentioned, as its "If not mentioned" line says; this holds `cost_breakdown` only when the justification
   step is itself reached.
3. Rent deposit: question 6 = yes while question 5 is not yes. The text places `deposit_receipt` under the step
   reached only when question 5 is yes; chosen literally (not_needed / hold on question 5), no inference that a
   made deposit implies an intended one.
4. Lease termination: `hardship_evidence` belongs to a step reached only when question 3 (arrears) is no; with
   arrears open, the document holds on `arrears_termination` (and on `extension_requested` if that is open too).
   The ex-officio extension (art. 273 para. 5) is not used to request it: "Not requesting them when the authority
   would examine an extension only ex officio ... is this rule set's choice".
5. Rent increase: the termination step (question 5) is independent of the graduated/index branches; it is
   evaluated on its own condition only.
