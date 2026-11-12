# Evaluator B: semantics used for the theft regime

Sources read: only `cleanroom_bundle/{TASK.md, SCHEMA.md, rule_text.md, catalogue.json, designs.json, BUNDLE_MANIFEST.json}`.
Program: `evaluate.py` (generic engine + the rule text encoded as data). Output: `reference.json` (60 files, 450 documents).

## Fact values

- `stated_true` is true and `denied` is false.
- **Raised and left open.** The fact is unresolved: "A fact that the file raises and leaves unsettled is open." Examples are an open bicycle or `vouchers_unobtainable`, and an open defining event.
- **Not mentioned.** This regime has no per-type presumption list, so the convention applies exactly as written: "A fact that the file does not mention is taken as not alleged, and the rules are applied as if it were absent. Silence never ends a process: where a fact's absence would end it, the unmentioned fact is unresolved."
  - The program tests, for each unmentioned fact, whether its absence (false) could make a stop apply where its presence would not. Only for the defining events is that the case.
  - Every other unmentioned fact is therefore false. That includes `burglary_or_robbery` and `away_cover_missing`, which are said to be "always stated or open in a file; no presumption" but are nevertheless unmentioned in some designs (A3).
- **Defining event** (`theft_at_home`, `theft_away`).
  - Not mentioned or open: unresolved ("The defining event is never presumed: if the file does not mention it, it is unresolved").
  - Denied: the first stop applies at the first step ("this claim type does not apply: when theft_at_home = false"), so every document is `not_needed`.
  - Open (the_32a656cb56cf, the_d76f5df60f83): documents that would be needed if the event is true are `hold`, waiting for the defining event. Documents not needed under either answer are `not_needed`.

## Steps, stops, documents

- I walk the steps in the order given and take each one when its "reached when" condition holds.
- A document is needed when its step is reached and its own "needed when" condition holds.
- **Stops.** "A stop ends the process at its step: no later step is reached, and no document of a later step is requested or left waiting."
  - I attach each stop to the step that checks its fact: the event stops to `h_event` and `a_event`, the household exclusion to `h_exclusion`, and the missing away cover to `a_cover`.
  - Documents of the stop's own step stay decided. So in type 2 the policy (step `a_cover`, "needed when theft_away = true") is still requested when the away cover is missing; its must_show includes "or its absence". "Documents of steps reached before the stop keep the state they had."
- **Unresolved facts.** I complete each unresolved fact both ways and compute the document's state under each completion.
  - The same state under every completion (the step is reached under every answer, or under none): that state.
  - Otherwise (reached or needed under some answers only): `hold`. `waits_for` lists the unresolved facts that change the state when flipped alone.
- **Optional document** (`police_report`, "not requested at intake; only if CSS asks for it later (optional)").
  - The rule text says: "At intake the handler does not request it; a reference evaluator marks it 'not needed' unless the file contains it, in which case it is assessed as present and sufficient or insufficient. Its absence is never a gap."
  - So, when its need condition holds: `present_sufficient` or `present_insufficient` if supplied, `not_needed` if not supplied.
  - When its need condition fails (an applicable stop): `not_needed` even if supplied (A1).
- **Conditional mandatory documents.** A conditional mandatory document is needed only when its condition holds and is otherwise `not_needed`. That covers `police_consent`, `original_vouchers`, `bicycle_voucher` and `lock_change_invoice`. `lock_change_invoice` requires `burglary_or_robbery = true`. "The valued list and the original vouchers ... are requested at intake (mandatory: true)."

## Supplied documents

- Needed and supplied: `present_sufficient` or `present_insufficient`, as designed. Needed and not supplied: `request`, or `not_needed` for the optional police report.
- Supplied but not needed under this reading: `not_needed`. The states table requires "Supplied, needed" for `present_*`. Example: the insurance policy supplied in the_0cd1b047049a is `present_sufficient`, because `a_cover` is reached there. A notification record supplied after a stop would be `not_needed`.
- Supplied but held: `hold`, because its need still turns on an unresolved fact.

## Ambiguities

- **A1. A police report supplied in a file where its step is not reached.**
  - Options: (a) assess it as present, as the literal "unless the file contains it" says; (b) `not_needed`, because the claim type does not apply or is excluded.
  - Choice: (b). The sentence describes the optional document within its step ("needed when theft_at_home = true and household_perpetrator = false"). The stop rule says no document of a later step is decided.
  - Effect: no design supplies a police report after a stop, so it changes nothing here. Where its need turns on an unresolved fact, a supplied report would be `hold`.
- **A2. Does a police report satisfy `police_consent`?** The title says "the police report recording it, or a written confirmation by the police". I treated `police_consent` as a separate document, satisfied only by an attachment of that document. A supplied `police_report` copy is not taken to show the consent, because its must_show does not include consent. Example: the_1024620d6055 and the_9355c558630a have changed traces and a police report attached, so `police_consent` is `request`.
- **A3. An "always stated or open" fact that is not mentioned** (`burglary_or_robbery`, `away_cover_missing`). I applied the convention, so the fact is taken as absent (false). Its absence never ends a process. In these designs it never decides a document: `away_cover_missing` is unmentioned only where the away event is denied, and every unmentioned `burglary_or_robbery` sits with `lock_change` false or unmentioned, or behind the household-exclusion stop.
- **A4. Which step each stop belongs to.** The text does not attach stops to steps. I attached each to the step whose title checks its fact (see above). This matters for the type-2 insurance policy when the away cover is missing: it stays requested or present.
- **A5. Contents of `waits_for`.** It lists only the pivotal unresolved facts, in catalogue order.
