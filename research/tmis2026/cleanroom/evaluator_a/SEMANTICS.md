# Semantics applied by evaluator A

Inputs: `../bundle/rules.json`, `../bundle/claims.json` only. Program: `python3 evaluate.py` (stdlib, deterministic).
Method: each open fact is enumerated over true/false; for each answer combination the reached steps are computed
from the transitions, and a document is needed if it is mandatory or conditional (with its flag true) on a reached
step. Needed under every combination -> `required_now`; under none -> `not_needed`; under some -> `held`.

1. **Fact not mentioned.** Branch facts are false: "a branch fact that the claim never mentions is presumed absent".
   The defining event is true: "the dispute's defining event (...) is presumed to have occurred". Denied facts are
   false; stated facts are true.
2. **Fact raised and left open.** Unknown, enumerated: "a fact that the claim raises but leaves open is unresolved,
   and the documents that depend on it are held behind a question". Only documents whose need actually changes with
   the answer are `held`.
3. **Defining event denied** (`termination_received`, `claim_received`). The first transition out of intake has
   that condition ("termination received", "claim received", `optional_path: false`); if it is false no later
   step is reached, and every document of the type sits on a later step, so all are `not_needed`. The text says
   only that the event "is presumed to have occurred" when the claim says nothing, and does not say what follows when it is denied: my choice (see Ambiguities A2).
4. **Defining event left open.** Treated like any open fact (the third silence clause, "a fact that the claim
   raises but leaves open is unresolved"): every non-optional document on a step after intake whose condition is
   not already decided false is `held`. Choice: see A1.
5. **Steps reached whatever the answer vs. only under some answers.** By enumeration. E.g. `dh_scope` is reached
   via "health effects alleged" -> `dh_safety` -> `dh_scope` or via "no immediate health escalation", so the lease
   contract is `required_now` even when `health_effects` is open, while `medical_confirmation` (on `dh_safety`) is
   `held`. The documents "that depend on" the open fact are only those whose need changes with its answer.
6. **Optional and conditional documents.** Conditional: needed iff "scenario flag 'X' is active" (X true) and its
   step is reached ("Apply ... evidence only when that branch is active"; "do not assume a cause or remedy before
   its branch is supported"). Optional: never `required_now`/`held`, always `not_needed` ("Request only missing
   material that can resolve an active decision"; an optional document is by its class not required). Choice: A3.
7. **Supplied documents.** If the document is needed now: `supplied_sufficient` / `supplied_insufficient` per the
   given marking (insufficient "must be requested again"). If it would be `held` or `not_needed`, it keeps that
   state, because `supplied_*` is defined as "The tenant supplied it, it is needed". In this data no supplied
   document falls in that case (0 claims, 0 documents). Choice: A4.
8. **Matching fact names.** Document conditions: "scenario flag 'X' is active" names the fact X verbatim.
   Transitions (hand-mapped in `EDGE_CONDITIONS`, by wording): "health effects alleged" = health_effects; "no
   immediate health escalation" = not health_effects; "technical inspection needed" = specialist_needed; "deposit
   route considered without specialist" = deposit_considered and not specialist_needed; "deposit route remains
   relevant" = deposit_considered; "no further specialist or deposit branch" = neither; "termination received" =
   termination_received; "arrears termination" = arrears; "family-home ordinary termination" = family_home; "no
   special precondition branch" = neither arrears nor family_home; "extension relevant" / "no extension branch" =
   extension_relevant / its negation; "claim received" = claim_received; "reference-rate reason selected" =
   reference_rate; "renovation reason selected" = renovation; "no specialist calculation branch" = neither.
   `retaliation_screen` has no transition; it only conditions `prior_rights_correspondence` on the always-reached
   `lt_abuse`. All other transition conditions ("timeline drafted", "outcome recorded", "inspection result
   available", ...) are completion labels of a step and are treated as satisfied. The defect workflow names no
   defining event, so all five of its facts are branch facts.

## Ambiguities

- **A1. Defining event raised and left open.** Options: (a) held behind the question (third silence clause); (b)
  presumed to have occurred, reading the middle clause "is presumed to have occurred" as unconditional. Chose (a):
  the clause is a *silence* policy and the presumption is about what the claim does not say; an explicitly open
  fact is "unresolved". Affects 9 claims (5 termination, 4 rent); 63 document entries become `held` (all
  mandatory documents and any conditional ones whose flag is true or open).
- **A2. Defining event denied.** The text does not say. Options: (a) gating transition false, nothing downstream
  reached, all `not_needed`; (b) `optional_path: false` means the step sequence runs regardless, so documents are
  required as if the event occurred; (c) hold everything for a clarifying question. Chose (a): the transition
  condition literally is the event, and a claim denying the event has no notice to verify. Affects 24 claims
  (12 termination, 12 rent), 240 document entries, all `not_needed`.
- **A3. Optional documents.** Options: (a) `not_needed`; (b) `required_now` (or `held`) when their step is
  reached. Chose (a): "optional" is not required and the states define `required_now` as "must be requested". Under
  (b) 72 entries would change (52 defect `caretaker_correspondence` -> required_now; 11 termination
  `landlord_correspondence` -> required_now and 5 -> held; 4 rent `landlord_correspondence` -> held). Affects all 96
  claims (one optional document each).
- **A4. Supplied document that is held or not needed.** Options: keep `held`/`not_needed`, or report
  `supplied_*`. Chose to keep, since `supplied_*` requires "it is needed". Affects 0 claims / 0 documents here.
- **A5. Arrears and family-home branches both active.** The graph offers `lt_type` -> `lt_arrears` and
  `lt_type` -> `lt_family` with no path between them, so a single path visits only one. Options: (a) fork: every
  branch whose condition holds is active; (b) exclusive choice (which would leave one branch's documents unrequested
  with no rule for which). Chose (a), following "Apply arrears, family-home, ... evidence only when that branch is
  active" per branch. Affects 5 termination claims (both true or open, event not denied). Same reading for
  reference-rate + renovation in rent (1 claim, event denied, no effect) and specialist + deposit in defect (17
  claims; no effect, since `dh_deposit` is reachable either way).
- **A6. "family-home ordinary termination".** No fact gives the termination type other than `arrears`. Options:
  (a) branch active iff `family_home`; (b) iff `family_home` and not `arrears` (an arrears termination being not
  ordinary). Chose (a): the document condition is just "scenario flag 'family_home' is active". Affects the 6
  termination claims with family_home true or open and the event not denied (5 of them overlap A5).
- **A7. `claim_received` as the rent dispute's defining event.** The text names the event "a rent-increase
  notification was received"; the catalogue has `claim_received`, which is the condition of the first transition
  ("claim received"), in the same position as "termination received". Options: (a) it is the defining event;
  (b) it is something else (e.g. the handler received the claim) and the defining event is unrepresented and
  presumed. Chose (a). Affects all 16 rent claims (12 denied, 4 open; none not_mentioned, so the presumption
  itself never applies to rent claims here).
- **A8. Completion-label transition conditions** ("safety advice recorded", "inspection result available", ...)
  are treated as satisfied, not as facts that could block a step. Affects no state in this data, since no fact
  corresponds to them.
- **A9. Mandatory documents and "Request only missing material that can resolve an active decision".** Chose:
  every mandatory document on a reached step counts as decision-relevant and is `required_now` unless supplied.
  The alternative (judging relevance per claim) cannot be decided from the given facts. Affects every claim whose
  defining event is not denied or open (63 claims).
