# Evaluator B: semantics used for the dismissal regime

Sources read: only `cleanroom_bundle/{TASK.md, SCHEMA.md, rule_text.md, catalogue.json, designs.json, BUNDLE_MANIFEST.json}`.
Program: `evaluate.py` (generic engine + the rule text encoded as data). Output: `reference.json` (60 files, 436 documents).

## Fact values

Each fact becomes yes, no or unresolved.

- `stated_true` = yes. `denied` = no.
- **Raised and left open**: always unresolved. The convention says: "A fact that the file raises and leaves unsettled is open."
- **Not mentioned, ordinary fact**: taken as no, following each type's presumption list ("not mentioned means taken as no: ...") and the convention "A fact that the file does not mention is taken as not alleged, and the rules are applied as if it were absent."
- **Not mentioned, listed as "unresolved, because its absence would end the process"** (type 2: `action_in_time`, `objection_submitted`): unresolved in every file. The convention says: "Silence never ends a process: where a fact's absence would end it, the unmentioned fact is unresolved." See Ambiguity A1.
- **Not mentioned, "No presumption; always stated in the file"** (`notice_before_protected_period`, `notice_period_ended`, `more_than_180_days`, `fixed_term`): the general convention applies. The fact is taken as no unless its absence could end the process. For these four facts it could not, so they are taken as no. In these designs the case arises only where the outcome does not depend on it (no protected period raised, an earlier stop, or the defining event denied). See A4.
- **Defining event**: "The defining event is never presumed: if the file does not mention it, it is unresolved." So it is unresolved when not mentioned or open. When it is denied, the first stop applies at step 1 ("If `employer_gave_notice` is no, the process ends"; "If `dismissed_immediately` is no ..."), and every document of the type is `not_needed`. No design leaves a dismissal defining event open or unmentioned. Had one done so, every document of step 2 and later would be `hold` waiting for the defining event, together with any other pivotal facts.

The program checks the presumption lists against the convention. Every "taken as no" fact is one whose absence cannot end the process. Each listed "unresolved" fact is one whose absence can end it.

## Steps, stops, documents

- I take a step when its "Taken when" condition holds, and walk the steps in order ("Steps are taken in the order given").
- "A document is needed when its step is taken and its own condition holds; every needed document is mandatory." "Needed always" means the document's own condition is true. "Needed only when X is yes" means its condition is X = yes.
- **Stops.** "A stop ends the process at its step: no later step is reached, and no document of a later step is requested or left waiting. Documents of steps reached before the stop keep the state they had; a document requested there remains requested." I place each stop at the step that examines its fact:
  - type 1: the defining-event stop at step 1, the probation stop at step 2 ("check that the probation period had expired");
  - type 2: the defining-event stop at step 1, the objection stop at step 2 ("check the written objection"), the agreement stop at step 3, the 180-day stop at step 4;
  - type 3: the stop at step 1.

  Documents of the stop's own step are still decided. The later step conditions in the rule text already exclude the stopped branches, so this placement agrees with them. See A2.
- **Unresolved facts.** I complete every unresolved fact both ways and decide each document under every combination.
  - Needed under all of them (the step is reached under every answer): needed.
  - Needed under none: `not_needed`. This includes documents of steps that every answer stops before: "no document of a later step is requested or left waiting".
  - Needed under some (the step is reached under some answers, or the document's own condition is unresolved): `hold`. `waits_for` names exactly the unresolved facts that can change the answer when flipped alone, in catalogue order. TASK.md defines hold as: "Whether it is needed depends on a fact the file leaves unresolved."
- **Optional or conditional documents.** The rule text has no optional documents: "every needed document is mandatory". A conditional document whose condition is no is `not_needed`. One whose condition is unresolved is `hold`.

## Supplied documents

- Needed and supplied as `sufficient`: `present_sufficient`. Needed and supplied as `insufficient`: `present_insufficient`. Needed and not supplied: `request`.
- Supplied but `not_needed` under this reading: `not_needed`. The states table defines `present_*` as "Supplied, needed", and nothing in the rule text makes a supplied copy needed.
- Supplied but `hold`: `hold`. Whether it is needed is still undecided, and the copy does not settle the fact it waits for. See A3.

## Ambiguities

- **A1. Is an unmentioned `action_in_time` or `objection_submitted` unresolved in every file, or only where its absence would end the process in that file?**
  - Options: (a) unresolved in every file, as the type-2 presumption line states without qualification ("Not mentioned leaves the fact unresolved, because its absence would end the process: `action_in_time`, `objection_submitted`"); (b) per file, from the convention's "where a fact's absence would end it". Under (b), `objection_submitted` would be no when `notice_period_ended` is no, and `action_in_time` would be no when `more_than_180_days` is no.
  - Choice: (a). The type-specific presumption is the more specific text and states no condition. The convention's sentence can be read the same way, as a property of the fact.
  - Effect: `written_objection` and `court_filing` are `hold` in files where (b) would make them `not_needed`. Examples: dis_408b774aa7db, dis_894859471634, dis_fb44c47f6ec7, dis_188837a70acc.
- **A2. Which step does each stop belong to?** The stops are listed separately from the steps. I attach each stop to the step that "checks" its fact. The consequential case is the probation stop in type 1. Placed at step 2, the notice and contract stay requested when notice came during probation ("Documents of steps reached before the stop keep the state they had"). The alternative is to place it at step 1, which would make them `not_needed`. Step 2's wording "check that the probation period had expired" decides it for step 2.
- **A3. A supplied document that is held or not needed.** The rule text is silent. I chose `hold` and `not_needed` rather than a `present_*` state, because `present_*` requires "needed".
- **A4. An "always stated" fact that is nevertheless not mentioned.** The rule text says this never happens, yet the designs contain it. I applied the general convention (taken as absent, unless its absence would end the process). It decides no document in these designs.
- **A5. Which facts to name in `waits_for`.** I named only the facts that are pivotal for that document, not every unresolved fact of the file and not facts of the step's condition that cannot change the result.
