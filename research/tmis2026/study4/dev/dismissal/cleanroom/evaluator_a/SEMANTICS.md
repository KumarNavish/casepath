# Evaluator A: dismissal semantics

Program: `evaluate.py` (run `PYTHONDONTWRITEBYTECODE=1 python3 -I evaluate.py catalogue.json designs.json reference.json`).
Each "Taken when" and "Needed only when" condition is encoded as written (including the nested `not (...)` stop
guards) and evaluated in three-valued (Kleene) logic over yes / no / unresolved.

## Fact states

- `stated_true` -> yes; `denied` -> no; `raised_and_left_open` -> unresolved ("A fact that the file raises and leaves
  unsettled is open.").
- `not_mentioned` follows each type's Presumptions list ("A presumption fills a fact the file does not mention"):
  - "not mentioned means taken as no": T1 notice_during_probation, probation_varied, incapacity_illness_accident,
    compulsory_service, pregnancy_or_birth, notice_period_varied; T2 agreed_to_continue, reasons_requested,
    retaliation_for_claims, employee_representative; T3 reasons_requested, incapacity_cause, notice_period_varied,
    other_earnings.
  - "Not mentioned leaves the fact unresolved, because its absence would end the process": T2 action_in_time,
    objection_submitted.
  - "No presumption; always stated in the file": T1 notice_before_protected_period; T2 notice_period_ended,
    more_than_180_days; T3 fixed_term -> unresolved if a design leaves them unmentioned.
  - Defining events (employer_gave_notice, dismissed_immediately) "never presumed" -> unresolved.

## Defining event

- No: first stop; every document is on a step requiring it yes -> all `not_needed`.
- Open / not mentioned: those documents `hold`, waiting for it.

## Steps and documents

"A document is needed when its step is taken and its own condition holds; every needed document is mandatory."
Need = step condition AND document condition. True -> `request`; unresolved -> `hold` with `waits_for` = the
unresolved facts the three-valued result depends on (catalogue order); false -> `not_needed`. "Needed always" =
needed whenever its step is taken.

## Optional and conditional documents

No document is optional ("every needed document is mandatory"). Conditional documents ("Needed only when X is yes")
hold while X is unresolved.

## Supplied documents

Needed and supplied -> present_* as designed. Supplied but held / not needed -> stays `hold` / `not_needed` (present
requires "needed"); no design in this set produces that case.

## Stops

"Documents of steps reached before the stop keep the state they had". Each later step's "Taken when" already contains
the stop as `not (...)`, so: T1 step 2 documents stay requested when the probation stop applies; T2 step 2 documents
(notice, contract, written_objection if objection yes) stay when the objection-lapse stop applies, and court_filing
(step 4) stays when the 180-day stop applies. An unresolved stop condition makes the later documents hold on the
facts it depends on.

## Ambiguities

1. T2 `action_in_time` not mentioned: unresolved by the explicit presumption, so `court_filing` (needed only when
   action_in_time is yes) holds on it even when more_than_180_days is no and the stop cannot apply. Chose the literal
   presumption over treating it as "no" in that branch.
2. T2 `objection_submitted` not mentioned while notice_period_ended is no: the stop cannot apply, but
   written_objection still holds on objection_submitted (literal presumption).
3. T1 `notice_before_protected_period` not mentioned: unresolved, but it matters only where a protected period is
   yes or open ("Not asked where no protected period is raised"); Kleene evaluation drops it otherwise.
4. T1 notice_period_terms belongs only to step 6 (suspended notice); it is not needed where the notice fell inside a
   protected period (step 7) or no period is raised, even if notice_period_varied is yes.
5. T3 notice_period_terms belongs to step 5 (fixed_term no); with fixed_term open it holds on fixed_term (and on
   notice_period_varied if that is open too).
