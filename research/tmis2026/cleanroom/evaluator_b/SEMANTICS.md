# Evaluator B: semantics applied

Source: only `../bundle/TASK.md`, `SCHEMA.md`, `rules.json`, `claims.json`. Run: `python3 evaluate.py`
(defaults `../bundle/rules.json`, `../bundle/claims.json`, writes `reference.json` in the current folder).

Method. For each claim every fact becomes true, false or open (cases 1-4). For every combination of answers to the
open facts the program walks the process graph from the start step, following a transition when its condition holds
(case 8), and decides per document whether it is needed: its step is reached and, for a conditional document, its
flag is active. Needed under every combination: requested (`required_now`, or `supplied_*` if supplied); under none:
`not_needed`; under some only: `held`.

1. **Fact not mentioned.** Branch fact: false. "a branch fact that the claim never mentions is presumed absent".
   Defining event: true (case 3). `denied` is false in all cases ("the claim states that the fact does not hold").
2. **Fact raised and left open.** Open; each answer is explored. "a fact that the claim raises but leaves open is
   unresolved, and the documents that depend on it are held behind a question." A document depends on it when the
   answer changes whether that document is needed.
3. **Defining event denied.** Defining events: `termination_received` ("for a termination dispute, that a
   termination notice was received") and `claim_received` ("for a rent dispute, that a rent-increase notification
   was received"). In `rules.json` these are the guards of the only exit from intake ("termination received",
   "claim received"). If the event is denied, that transition does not fire. No later step is reached, and all
   documents are `not_needed`. If it is not mentioned, it is true: "is presumed to have occurred". The defect
   dispute names no defining event, so all of its facts are branch facts.
4. **Defining event left open.** Every step after intake depends on it, so every document that would otherwise be
   needed is `held` (case 2).
5. **Steps reached whatever the answer, and steps reached under some answers only.** On an always-reached step,
   mandatory documents are requested now. Conditional ones follow their own flag. On a step reached only under some
   answers, the documents are `held`. Example: `dh_safety` when `health_effects` is open. Steps are reached only
   through "the documents ... held behind a question", "Apply ... evidence only when that branch is active", and
   "Reconstruct ... only when that branch is active".
6. **Optional and conditional documents.** Conditional: needed only when "scenario flag 'X' is active", that is when
   fact X is true, and its step is reached. This follows "Treat medical, inspection, heating, moisture-log, and
   deposit evidence as conditional; do not assume a cause or remedy before its branch is supported". Optional:
   never requested, so always `not_needed`: "Request only missing material that can resolve an active decision" /
   "request only missing evidence that changes one of those decisions" (my choice, see A3).
7. **Supplied documents.** If the document is needed with certainty: `supplied_sufficient` or `supplied_insufficient`
   per `as_designed`. If it is not needed or held, the state stays `not_needed` or `held`. TASK.md defines
   `supplied_*` as "it is needed", which those documents are not (my choice, see A5). In this data no supplied
   document is not needed or held, so this choice changes nothing.
8. **Matching fact names.** A document condition "scenario flag 'X' is active" is fact `X` (exact name). Transition
   conditions:
   - "health effects alleged" = `health_effects`
   - "technical inspection needed" = `specialist_needed`
   - "deposit route considered without specialist" = `deposit_considered` and not `specialist_needed`
   - "deposit route remains relevant" = `deposit_considered`
   - "termination received" = `termination_received`
   - "arrears termination" = `arrears`
   - "family-home ordinary termination" = `family_home`
   - "extension relevant" = `extension_relevant`
   - "claim received" = `claim_received`
   - "reference-rate reason selected" = `reference_rate`
   - "renovation reason selected" = `renovation`

   The "no ..." conditions are default branches. "no immediate health escalation", "no further specialist or deposit
   branch", "no special precondition branch", "no extension branch" and "no specialist calculation branch" are each
   taken when no fact-guarded sibling from the same step is taken. All other conditions record the handler's own
   work: "timeline drafted", "outcome recorded", "inspection result available" and the like. They are treated as
   satisfied. Several fact-guarded branches from one step can be taken together, for example arrears and
   family-home.

## Ambiguities

- **A1. Defining event denied.** Options: (a) the gating transition fails, so nothing after intake is needed; (b) the
  documents are still requested, for example because non-receipt is itself contested. The silence clause covers only
  the case where the event is not mentioned. I chose (a): the catalogue makes intake → deadline conditional on
  "termination received" / "claim received". Affects 24 claims (12 termination, 12 rent). Under (b), 159 documents
  would be `required_now` instead of `not_needed`.
- **A2. Defining event left open.** Options: (a) every dependent document is `held`; (b) the event is presumed to
  have occurred. I chose (a), from the words "raises but leaves open ... held behind a question". Affects 9 claims
  (5 termination, 4 rent). Under (b), 63 documents would be `required_now` instead of `held`.
- **A3. Optional documents.** Options: (a) never requested, `not_needed`; (b) requested like mandatory when their
  step is reached. The five states have no "optional", and the prose says to request only material that changes a
  decision. I chose (a). This applies to all 96 claims, one optional document each. The outcome differs for 72
  claims: under (b), 63 documents would be `required_now` and 9 would be `held`.
- **A4. "family-home ordinary termination" when arrears is also true.** Options: (a) fact `family_home` alone; (b)
  `family_home` and not `arrears`, reading "ordinary" as excluding an arrears termination. I chose (a): the
  condition catalogue has no fact for the termination type. Affects 5 claims and 5 `spouse_notice_copy` documents.
  Under (b), 3 would become `not_needed` instead of `required_now`, and 2 `not_needed` instead of `held`.
- **A5. Supplied document that is not needed or held.** Options: (a) keep `not_needed` / `held`; (b) report it as
  `supplied_*`. I chose (a), following the state definition "it is needed". Affects 0 claims and 0 documents in this
  data.
- **A6. "deposit route considered without specialist".** Options: (a) `deposit_considered` and not
  `specialist_needed`; (b) `deposit_considered` alone. I chose (a), from the word "without". Affects 0 documents,
  because `dh_deposit` is also reached through `dh_specialist` on "deposit route remains relevant".
- **A7. Procedural transition conditions** ("timeline drafted", "inspection result available", ...). Options: (a)
  satisfied, because they record the handler's own work and are not claim facts; (b) unknown, so later steps are
  held. I chose (a). It applies to all 96 claims. Under (b), almost every document would be held. The
  mandatory-document class implies that these steps are expected to be reached.
- **A8. Conflict in the text, noted.** The silence clause names defining events only for termination and rent
  disputes, but it is copied into the defect rule as well. The defect dispute has no defining event, so all of its
  facts are branch facts. Affects the 52 defect claims, with no alternative applicable.
