# Reconciliation of the citation check (theft rule set, SPEC.md item 7)

Writer's reply to `CITATION_CHECK.md` (not edited). One line per item the second reader did not simply agree with (21 "agree with change", 2 "disagree", and the workflow-only `claim_type`), then the reader's notes and the `rule_text.md` omissions. The coordinator's five decisions are applied; the text contradicted none of them, and the choices made under decision 3 and decision 5 are stated below. New passages, all from the same public documents and verified with `tools/verify_sources.py`: CSS AVB Ziff. 4, Ziff. 8 lit. c (whole), Ziff. 20 Einleitung, Ziff. 23.3 Ausschlüsse (second dash), lit. a Ausschluss, lit. b Ausschluss, Ziff. 24 Einleitung, Ziff. 26 lit. b; claim form p. 1 (online notification), 3.7 columns, and section 4 (Polizeimeldung, Anzeigedatum, Polizeiposten). The form declaration is no longer cited. Rebuilt with `tools/build.py`; `tools/check.py`: ALL CHECKS PASSED.

## Verdict items

| # | rule id | reader's point | what I did | why |
|---|---|---|---|---|
| 1 | theft_at_home / fact `theft_at_home` | The passage is cut after "nachgewiesene"; "merely missing" would answer yes | Accepted: the full sentence of Ziff. 23.3 Abs. 1 is quoted. `not_this` adds "Items merely missing where no trace, witness or circumstance points to a theft (that is open, not true)". Context: the "Verlieren, Verlegen … Veruntreuung" exclusion and lit. a/b with their exclusions | Decision 4. The proof clause belongs to the covered event's definition. |
| 2 | theft_at_home / `household_perpetrator` | `not_this` leaves the decisive moment open | Accepted: "lived in the same household … at the time"; `not_this` "a person who had moved out of the household before the theft" | Reader's wording |
| 3 | theft_at_home / `burglary_or_robbery` | Lit. a's "Fahrzeuge sind keine Behältnisse" is missing | Accepted, and also lit. b's "Schäden, verursacht durch Taschen- und Trickdiebstahl.": both are in the question, in `not_this`, and as context passages (snapshot updated) | Decision 4 |
| 4 | theft_at_home / `lock_change` | Cost cover reaches only costs caused by an insured event (Ziff. 20 Einleitung) | Accepted: "costs, caused by the theft, …"; Ziff. 20 Einleitung as context; `not_this` "a lock change made for another reason" | Reader's wording |
| 5 | theft_at_home / `traces_changed` | The duty is the policyholder's | Accepted: "by the policyholder or on their behalf"; `not_this` adds "traces changed by the thief or by events outside the policyholder's control"; the "Bei Diebstahl hat der Versicherungsnehmer ferner:" introduction as context | Reader's wording |
| 6 | theft_at_home / `vouchers_unobtainable` | All-or-nothing, while the passage works voucher by voucher | Accepted: the question asks "for all of the … items"; `original_vouchers.must_show` reads "the original voucher for each stolen or damaged item whose voucher can be obtained without considerable cost"; the inference says the limit applies per voucher | Decision 3 |
| 7 | theft_at_home / `instruction_due` (**disagree**) | The conjunction makes the file state the ordinary "no danger" part, so silence drops the duty | Accepted: split into `measures_pending` ("still to be taken (not yet carried out)", VVG 38a Abs. 1) and `imminent_danger` (true is the exception; unmentioned means none, by the convention; VVG 38a Abs. 1 Satz 2) | Decision 1. Under 6b polarity, true for `imminent_danger` is what the claimant raises. |
| 8 | theft_at_home / step `h_instruction` | Inherits the defect | Accepted: reached when `measures_pending` = true and `imminent_danger` = false; the gate's other edge is `measures_pending` = false or `imminent_danger` = true | Follows item 7 |
| 9 | theft_at_home / document `claim_form` | Oral or online notice is allowed; the signature does not rest on art. 38 | Accepted: renamed `notification_record`, "Record of the claim notification: the CSS form … or CSS's record of an online, written or oral notification"; `must_show` "that and when CSS was notified of the theft"; no signature item. Context: Ziff. 8 lit. a, Ziff. 4 ("kann diese auch mündlich erfolgen"), and the form's "Alternativ … online unter css.ch/schaden melden" | Decision 2. The signature item is dropped rather than made optional, because no passage requires it. |
| 10 | theft_at_home / `police_consent` | "Written confirmation" imports practice; the police report is the document lit. f names | Accepted: title and inference name the police report (which CSS may request, lit. f) or a written police confirmation, and say that either one satisfies the need; still mandatory | Reader's wording |
| 11 | theft_at_home / `stolen_items_list` | The form's 3.7 table is itself the list, and the list and the vouchers are treated unequally under the same "auf Verlangen" | Accepted, both options: the document is "the claim form's table in section 3.7, or a separate list". Like the vouchers, it rests on Ziff. 8 lit. c (basis follows) and is requested at intake (mandatory: true), with the form's 3.7 heading and columns as context | Decision 3; see the decision below |
| 12 | theft_at_home / `original_vouchers` | The duty is contractual (lit. c), not the form's request; plus the per-voucher limit | Accepted: the passage is Ziff. 8 lit. c ("auf Verlangen, … Originalbelege beizubringen"), basis follows, with the inference that CSS makes the request in its claim form; context: form 3.7 and VVG 39 Abs. 2 Ziff. 1; `must_show` is per voucher | Decision 3 |
| 13 | simple_theft_away / fact `theft_away` | Damaged items are missed; a theft from a car broken into away from home could be read as burglary and wrongly end the type | Accepted: "stolen or damaged by a theft outside the insured location that was neither …"; the vehicle and pickpocket exclusions are in the question, in `not_this` and as context; `not_this` also says that burglary or robbery away from home is outside both types | Decision 4 |
| 14 | simple_theft_away / `away_cover_missing` | The policy settles it; the convention presumption presumes cover without a text | Accepted: `always_stated: true` (no presumption); passage Ziff. 24 Einleitung ("sofern diese vom Versicherungsnehmer gewünscht und in der Police aufgeführt worden sind"), with 23.3 lit. c as context. `insurance_policy` is moved to the cover-check step `a_cover`, so the policy is requested as soon as a simple theft away is stated and settles the fact | Decision 5. Ziff. 24 Einleitung makes the cover an option chosen by the policyholder, so neither value is the ordinary case: always_stated |
| 15 | simple_theft_away / `traces_changed` | As item 5 | Accepted (shared wording) | As item 5 |
| 16 | simple_theft_away / `vouchers_unobtainable` | As item 6 | Accepted | As item 6 |
| 17 | simple_theft_away / `instruction_due` (**disagree**) | As item 7 | Accepted (split) | As item 7 |
| 18 | simple_theft_away / step `a_instruction` | As item 8 | Accepted | As item 8 |
| 19 | simple_theft_away / `claim_form` | As item 9 | Accepted (`notification_record`) | As item 9 |
| 20 | simple_theft_away / `insurance_policy` | Ziff. 24 Einleitung is the better passage; add the insured location | Accepted: passage Ziff. 24 Einleitung (evidence), 24.2 as context; `must_show` adds "the insured location" and "its absence" of the cover; the document now belongs to step `a_cover` | Decision 5 |
| 21 | simple_theft_away / `police_consent` | As item 10 | Accepted | As item 10 |
| 22 | simple_theft_away / `stolen_items_list` | As item 11 | Accepted | As item 11 |
| 23 | simple_theft_away / `original_vouchers` | As item 12 | Accepted | As item 12 |
| 24 | workflow-only fact `claim_type` | Not in `rules.json` or `rule_text.md`; "other" is undefined | Accepted: top-level `routing` entry in `rules.json` (question, values, `not_this`: "A burglary or robbery away from the insured location (covered, if at all, by the basic cover during travel, Ziff. 26 lit. b) and any other peril: other"). Passage: Ziff. 23.3 Abs. 1, with 24.2 and Ziff. 26 lit. b as context. `rule_text.md` has a section "Which claim type applies" and an "Outside both types" paragraph; the workflows take `claim_type` from this entry; `check.py` verifies it | Decision 5 |

## Reader's notes and optional points

| item | reader's point | what I did |
|---|---|---|
| convention `applies_to` (cosmetic) | "(none in this set)" should be "(none besides the defining events)" | Accepted |
| step `h_police` (note) | Reached also for pure vandalism; say so | Accepted: a type note in `rules.json` (`notes`), in `RULES.md` and in `rule_text.md` says the text does not settle whether "bei Diebstahl" covers vandalism, and the set does not narrow it |
| step `a_cover`, stop `a_stop_no_cover` (optional) | Add Ziff. 24 Einleitung | Accepted: Ziff. 24 Einleitung is now the passage, with 23.3 lit. c as context |
| fact `bicycle` (optional) | Say whether an e-bike counts | Not taken (see the end of this file) |
| form declaration locator | Imprecise ("Abschnitt 6, Unterschrift") | Moot: the declaration is no longer cited |
| police report vs form section 4 | The form's section 4 records the police notification and is unused | Used: section 4 ("Polizeimeldung", "Anzeigedatum", "Polizeiposten") is context for the police step and for `police_report`, whose `must_show` now has "when" and "the police station". The report itself stays on request, since the form asks only for its particulars |
| `rule_text.md` omissions 1-4 | The follows inference, the context passages, `claim_type` and the outside-both-types scope are not printed; a document's "needed when" is printed without its step condition | All four fixed: every rule line prints its context passages and any inference; the routing and scope sections are added; a document's "needed when" now prints the step condition and the document condition together |
| old base | (follows item 9) | Old rule 047 (the signed declaration) is re-classed from "kept" to "dropped: broader than its passage". The counts are now kept 15, broader 4, no passage 4, other insurer 31, outside 46 |

## Decision 3: what the handler does at intake, and how `optional` reads

From the text: the valued list and the original vouchers are due "auf Verlangen" (Ziff. 8 lit. c). The handler is the insurer, so its request is the act being decided. CSS makes that request in its own claim form for every stolen or damaged item: section 3.7, "Beschädigte oder gestohlene Sachen (bitte Originalkaufbelege beilegen)", with the columns Gegenstand / Gekauft bei / Kaufdatum / Ersatzwert, or "Gemäss separater Liste". At intake both are therefore **requested** (mandatory: true), within the per-voucher cost limit.

The police report "kann durch die CSS einverlangt werden" (lit. f), and no CSS document requests it at intake: the form asks only for the report's particulars in section 4. It is therefore **not requested at intake** (mandatory: false; `optional: true` in the workflow).

`rules.json` (`reading_of_optional`) and `rule_text.md` ("Documents requested at intake and documents only on request") tell the reference evaluator to mark such a document "not needed" unless the file contains it, in which case it is assessed as present and sufficient or insufficient; its absence is never a gap.

## New counts and check

Types 2. Facts 16: theft_at_home 9, simple_theft_away 7. Steps 16. Documents 15 per type, 8 in the catalogue. Presumptions 0, plus 12 convention presumptions in the workflows. `always_stated`: `burglary_or_robbery`, `away_cover_missing`. Stops 4. Rules by basis: states 33, follows 11, evidence 7 (51), plus convention 1. Routing fact 1.

`tools/check.py`: ALL CHECKS PASSED. Its 6b walks cover 6561 assignments for theft_at_home and 729 for simple_theft_away. It notes that theft_at_home now uses 9 facts, one more than the product's exact-deferral limit of 8 open facts; that limit is reached only if the defining event and all 8 other facts are left open at once. Both workflows pass the product's `validate_workflow` with `kind: process_guidance` plus `intended_kind`.

## Not accepted (for the reader's second look)

None of the 24 verdict items. One optional note was not taken:

- **`bicycle`, whether an e-bike counts.** The fact's passage is the form heading "Fahrrad (bitte Originalkaufbelege beilegen)". The form offers only "Herren- /Damenfahrrad" and "Kinderfahrrad" and names no e-bike. Ziff. 18 lit. g ("Fahrräder und E-Bikes …") defines insured items, not the form's request. The question therefore keeps the form's word "bicycle" and does not decide e-bikes either way.

## Closing

Reader's second look of 2026-11-12 (appended to `CITATION_CHECK.md`): all 24 points resolved, both readers agree. Applied with it: note C (the example in `outside_both_types` is now "a hotel room or rented holiday flat broken into during a trip") and the e-bike recommendation (`bicycle.not_this`: a stated e-bike leaves the fact open; `generator_note`: do not draw e-bikes as bicycles). Workflows set to status "reviewed"; `tools/check.py`: ALL CHECKS PASSED. SHA-256: `rules.json` 1cb1102f7bb6129abb4473223cd7d13b6bb527614a27de2e4bb63f937d1c56a0; `rule_text.md` 1d1b4f545e4c4eb450a3f34d4b6f69df89c27e3fc8aa7a81ff276f55100a4063; `workflow/theft_at_home.json` 89aa189b4be61787940925adc92dd71006451e832ba2a5c7d37258022481533b; `workflow/simple_theft_away.json` 7cb0ac6471504aa09486bee74f21a0bc04c8f658bab0d6c39394694733023c5e.

Clarification after review (2026-11-12): one general paragraph on reading steps and stops added to rule_text.md and rules.json; no rule changed. New SHA-256 (workflows byte-identical to before the clarification):

- rules.json 511737ee14dab965692c2880743bd476853882feb278c8bfe0a93e6192a5cb3b
- rule_text.md 99873eb918359b1c87e130d99136a4fc5bf305ab040a427c876ff7c4f6b2e11f
- workflow/simple_theft_away.json 7cb0ac6471504aa09486bee74f21a0bc04c8f658bab0d6c39394694733023c5e
- workflow/theft_at_home.json 89aa189b4be61787940925adc92dd71006451e832ba2a5c7d37258022481533b

## Revision after first use (development, 2026-11-12)

DEVELOPMENT material, post hoc. The rule set's first use (the clean arm of the lint test, `lint/REPORT.md`, gpt-6-luna,
59 theft files) was diagnosed from the stored readings in `lint/DIAGNOSIS.md` (written by `lint/diagnose.py`;
judgments in `lint/diagnosis_review.json`). Only wording that Part A showed to be ours is changed; each change is a
general rule, written in `tools/build.py` and rebuilt. The fixes were designed on the same 59 files they are checked on
(in-sample, development). The rule set as the lint runs read it is kept in `rev0/`.

Not changed: no document, `needed_when`, `mandatory` or `must_show` item; no fact id, step, condition, presumption or
stop; the convention of SPEC 6a; the routing values. `lint/verify_rev1.py` (`lint/VERIFY_REV1.json`): rules' and
workflows' logic equal to `rev0/`; every stored final reference keeps its manifest hash; the product's evaluator
recomputes all 59 final references unchanged; the clean-room comparison on the 60 designs still gives 450 of 450
document states equal to both evaluators. The source snapshots (`sources/*.txt`, `SOURCES.json`) are byte-identical
after the rebuild. `tools/check.py`: ALL CHECKS PASSED. `generator/test_generator.py`: 15 tests OK. (The theft
workflows give the product the question with its `not_this` appended, so `not_this` changes reach the product.)

### H1. Routing fact `claim_type` (`routing.not_this`)

- **Old not_this:** "A burglary or robbery away from the insured location (covered, if at all, by the basic cover
  during travel, Ziff. 26 lit. b) and any other peril: other. Neither type applies to them."
- **New not_this:** the same two sentences, followed by: "Breaking into a vehicle is not a burglary (a vehicle is not a
  container), and pickpocketing or trick theft is not a robbery: a theft from a vehicle broken into, and pickpocketing
  or trick theft, away from the insured location are simple thefts away (simple_theft_away). Whether the policy
  includes the supplementary insurance for simple theft away, and whether an exclusion applies (for example a thief
  who lives in the policyholder's household), is decided within the claim type, not by this question."
  (The question itself is unchanged. Context passages added: Ziff. 23.3 lit. a Ausschluss, lit. b Ausschluss, Ziff. 24
  Einleitung, Ziff. 23.3 Ausschlüsse erster Strich.)
- **Evidence (Part A):** 11 of 51 non-denied theft files failed routing; 10 were answered "other". Seven are thefts from
  a car or camper van broken into away from home (the_0cd1b047049a, the_12ee892d56f4, the_819379d12c03, the_9355c558630a,
  the_c50e0bd7b054, the_d37fc3c54b4b, the_d9579f891719): the router quoted the smashed window or the forced lock and,
  with "a burglary ... away ...: other" in front of it and without the policy's own rule that a vehicle is not a
  container (stated in `theft_away` and in `outside_both_types`, but not in the routing question the router is
  given), answered other. One is a handbag taken from a restaurant chair in a file stating that the supplementary
  cover was not taken (the_dd72ec4e53dd), one a theft at home by a flatmate (the_248aa95805a8, "Es war meine
  Mitbewohnerin"): in both the question did not say that cover and exclusions are decided inside the type, where the
  rule set decides them (stop `a_stop_no_cover`, stop `h_stop_excluded`). 19 errors (18 requests missed, 1 hold
  missed). The two remaining non-denied failures (the_32a656cb56cf,
  the_d76f5df60f83) have a designed-open defining event that is itself the routing question; not a wording defect, not
  changed.
- **Passages:** css-avb Ziff. 23.3 lit. a, Ausschluss: «Schäden, verursacht durch das Aufbrechen eines Fahrzeuges.
  Fahrzeuge sind keine Behältnisse.»; Ziff. 23.3 lit. b, Ausschluss: «Schäden, verursacht durch Taschen- und
  Trickdiebstahl.»; Ziff. 24.2: «Schäden am Hausrat durch Diebstahl, der weder als Einbruchdiebstahl noch als
  Beraubung gilt und sich ausserhalb des versicherten Standortes ereignet, ...»; Ziff. 24, Einleitung: «Die CSS
  versichert die nachfolgend beschriebenen Gefahren, sofern diese vom Versicherungsnehmer gewünscht und in der Police
  aufgeführt worden sind:»; Ziff. 23.3, Ausschlüsse, erster Strich: «Schäden, verursacht durch Personen, die mit dem
  Versicherungsnehmer im gleichen Haushalt leben.»
- **Why no broader and no narrower:** the added sentences repeat the policy's own definitions (already in `theft_away`,
  `burglary_or_robbery` and `outside_both_types`) and the rule set's own placement of the cover check and the
  household exclusion inside the types. A burglary or robbery away from home stays "other"; nothing moves into a type
  that its defining event does not cover.

### H2. `theft_at_home.household_perpetrator` (not_this)

- **Old:** "A guest, neighbour, tradesman or cleaner, or a person who had moved out of the household before the theft;
  a suspicion the file raises but does not settle is open, not true."
- **New:** the same, followed by: "A thief the file only calls unknown or unidentified, with nothing in the file
  pointing to a member of the household, does not raise this question."
- **Evidence (Part A):** the_506c9909edc4 (fact not mentioned): two readings of three answered open, quoting the
  police record's "Täterschaft unbekannt.", so no presumption filled the fact and the product held three documents
  (3 holds where the file settles the fact). The not_this's "a suspicion the file raises ... is open" was applied to a
  thief who is merely unknown. One file; the change is a reading rule for every file with an unknown thief.
- **Passage:** css-avb Ziff. 23.3, Ausschlüsse, erster Strich: «Schäden, verursacht durch Personen, die mit dem
  Versicherungsnehmer im gleichen Haushalt leben.»
- **Why no broader and no narrower:** the condition is unchanged; a file that points to a household member, or raises
  a suspicion against one, is still open or true as before.

### H3. `measures_pending` (not_this, both types)

- **Old:** "Measures already carried out; the notification of the claim itself; steps to find the thief or recover the
  items."
- **New:** "Measures already carried out; the notification of the claim itself; steps only to find the thief. Steps
  still to be taken to get the stolen items back or to stop them being used or sold do reduce the loss and are not
  excluded."
- **Evidence (Part A):** the fact is admitted in 3 of the 9 files the runs read where it is stated true. The three
  admitted measures stop the thief using the item (blocking a phone by IMEI, blocking a credit card, locking a laptop
  through its account). The six not admitted are steps to get the item back: registering a bicycle's frame number on
  stolen-bike lists "in case it turns up" (3 files, presumed false), reporting a serial number to the maker so the item
  is noticed at a repair (2 files, held), going with the police to secure a bicycle offered for sale (1 file, held).
  The old not_this excluded exactly these. The writer and the blind check saw only the question (bundles carry no
  not_this), so the designs count them as measures. The fact changes no document (no document hangs on the instruction
  step and the product defers only on facts that change a document): 0 errors; the change aligns the wording with the
  passage and the admission rate with the designs.
- **Passage:** VVG Art. 38a Abs. 1: «Der Anspruchsberechtigte ist verpflichtet, nach Eintritt des befürchteten
  Ereignisses tunlichst für Minderung des Schadens zu sorgen. Er muss, wenn nicht Gefahr im Verzug liegt, über die zu
  ergreifenden Massnahmen die Weisung des Versicherungsunternehmens einholen und befolgen.»
- **Why no broader and no narrower:** the old exclusion of steps to recover the items had no passage: getting stolen
  items back, or stopping their use or sale, reduces the loss ("Minderung des Schadens"). Steps that serve only to
  find the thief stay excluded, as do measures already carried out and the notification itself (unchanged).

### Considered and not changed

- Six denied-event files were routed to the other theft type (the_1dfba8facf5e, the_6634ab23ee99, the_685edf55333b,
  the_86b4e22a87e7: "not at home, but on holiday / in Bern / in Zürich / in Konstanz"; the_86e739ec9184,
  the_a529fff2269d: "at home"). Under the rule text these files are claims of the other type, so the product's routing
  is what the rules give and the reference's stop is right only inside the drawn type: 24 of the 67 errors. That is a
  benchmark-design point (the two types' defining events are complementary, so denying one usually states the other),
  not wording; left for the planner.
- Needed but not allowed in this revision: `stolen_items_list` asks "where and when it was bought" for each item and
  `original_vouchers` the voucher for each item, which cannot exist for a gift, an heirloom or a spare key bunch; the
  product read them literally (3 requests that should not be made, and 4 more where the file plausibly is
  insufficient). A `must_show` change; left for the planner.

### Hashes after the revision

- rules.json f366a1cf4d0bc7d1e43dc665d21531afdb19d9e77410dc169b30b263c4b991b2
- rule_text.md 4a6fbe444d13deb4498e4806a9e1ad175cfdb467800f753e5c138aa0e872f937
- workflow/theft_at_home.json cd19a336c5e8fcd57c3da5e2effd0fff9894bea6fb53b31340eb03dd01976ed2
- workflow/simple_theft_away.json 320a346001d595ff9c564314ef47fe50c26992071f48c7d60bf15eea1bad21f2

## Revision 2 after first use (development, 2026-11-12): must_show items

DEVELOPMENT material, post hoc. The diagnosis of the first use (`lint/DIAGNOSIS.md`, `lint/diagnosis_review.json`)
attributes 12 clean-arm errors over the three regimes to conditional or per-item `must_show` wordings. Revision 2
applies one rule-writing guideline, SPEC.md item 6c, to every `must_show` item of this rule set:

> A `must_show` item names one thing that is visible on the document. An item that applies only under a condition
> starts with that condition in the fixed form "Only if the file states that <condition>: <thing>." and ends "Otherwise
> this item does not apply."; the condition is the one the generator applies (`generator/items/<regime>.json`,
> `applies_when`) or, where the generator leaves it to the story, the circumstance itself. No item asks "whether"; no
> item is satisfied by an absence (where a document may show either of two things, the item names the statement that
> must be visible). A need condition belongs in `needed_when`, not in an item.

The product's workflow format (`casepath.workflow/1`, `validate_workflow` at the tested commit) takes `must_show` only
as a list of distinct non-empty strings, with no condition per item, so the fixed wording carries the condition.

Edited in `tools/build.py` (table `MUST_SHOW_REV2`, which also writes `MUST_SHOW_WORDING.json`: old wording -> new, read
by the generator for designs that name an item by its earlier wording) and rebuilt. The state the `_rev1` runs read is
kept in `rev1/` (`rules.json`, `rule_text.md`, `workflow/`); the generator's item notes of that state in
`generator/items/rev1/theft.json`.

Not changed: no document, title, step, `needed_when`, `mandatory`; no fact, question, `not_this`, presumption or stop;
which items are conditional and when they apply (`generator/items/theft.json`: only `item` keys renamed).
`lint/verify_rev2.py` (`lint/VERIFY_REV2.json`) confirms: rules.json and every workflow equal `rev1/` except the
must_show wording, read through `MUST_SHOW_WORDING.json`; every stored `dev/theft/final/*/reference.json` and `design.json`
still has its manifest hash; the product's evaluator recomputes every final reference unchanged with the revised
workflows; the clean-room comparison on the 60 designs gives the same document states as both evaluators for all
documents; for every design and item the notes give the same conditional / applies / checkable_as as before; every
writer bundle is the same once item texts are mapped. `tools/check.py` passes and now enforces the fixed form, no
"whether" and no absence wording (it reports the old wording in `rev1/` as failing). `generator/test_generator.py`:
all tests pass.

Changed items (5 rows (9 item instances: four documents are in both claim types)):

1. **notification_record** (theft_at_home, simple_theft_away)
   - Old: "that and when CSS was notified of the theft"
   - New: "the date (day, month and year) on which the theft was notified to CSS"
   - Cited passage (the document's rule, basis evidence): VVG Art. 38 Abs. 1: "Ist das befürchtete Ereignis eingetreten, so muss der Anspruchsberechtigte, sobald er von diesem Ereignisse und seinem Anspruche aus der Versicherung Kenntnis erlangt, das Versicherungsunternehmen benachrichtigen."
   - Why: 'that and when' makes the document's only item hard to leave out and to see missing (6 round-1 files designed missing, read sufficient). Now names the one thing the generator's checkable_as requires: the calendar date of the notification to CSS.
2. **insurance_policy** (simple_theft_away)
   - Old: "the supplementary insurance for simple theft away (Ziff. 24.2), or its absence"
   - New: "the supplementary insurance for simple theft away (Ziff. 24.2), listed among the policy's covers as included or as not included"
   - Cited passage (the document's rule, basis evidence): Ziff. 24, Einleitung, S. 8: "Die CSS versichert die nachfolgend beschriebenen Gefahren, sofern diese vom Versicherungsnehmer gewünscht und in der Police aufgeführt worden sind:"
   - Why: 'or its absence' lets a silent policy count as showing the item. Now names the listing that must be visible, as the generator's checkable_as already did.
3. **stolen_items_list** (theft_at_home, simple_theft_away)
   - Old: "where and when it was bought"
   - New: "for each item, where and when it was bought, or, for an item that was not bought, that it was a gift or inherited and when"
   - Cited passage (the document's rule, basis follows): Ziff. 8 lit. c, S. 3: "auf Verlangen, ein Verzeichnis der vom Schaden betroffenen Sachen mit Wertangaben zu erstellen und Originalbelege beizubringen;"
   - Also cited on the document: Abschnitt 3.7, Spalten, S. 2: "Gegenstand Gekauft bei Kaufdatum Ersatzwert /Reparaturkosten Gemäss separater Liste"
   - Why: Cannot be shown for an item that was not bought (the_9b58c5abd02f, an inherited watch; the_d70abf016562, a gift). Now says what the list shows for such an item, as the generator's checkable_as already did ('gift' or 'inherited', with the occasion). The form's columns 'Gekauft bei / Kaufdatum' are the passage.
4. **original_vouchers** (theft_at_home, simple_theft_away)
   - Old: "the original voucher for each stolen or damaged item whose voucher can be obtained without considerable cost"
   - New: "an original purchase voucher for each stolen or damaged item, except an item for which the file states that its voucher cannot be obtained without considerable cost"
   - Cited passage (the document's rule, basis follows): Ziff. 8 lit. c, S. 3: "auf Verlangen, ein Verzeichnis der vom Schaden betroffenen Sachen mit Wertangaben zu erstellen und Originalbelege beizubringen;"
   - Also cited on the document: VVG Art. 39 Abs. 2 Ziff. 1: "Der Vertrag kann verfügen: 1. dass der Anspruchsberechtigte bestimmte Belege, deren Beschaffung ihm ohne erhebliche Kosten möglich ist, insbesondere auch ärztliche Bescheinigungen, beizubringen hat;"
   - Why: 'whose voucher can be obtained without considerable cost' is not visible on a voucher; readers judged it differently (the_0d6569d32db1, the_281214c010bb, the_eb579978f91b, the_e0b1e1d56fb2). Now: one voucher per item, except items the file states cannot be documented without considerable cost, the voucher-by-voucher limit of VVG Art. 39 Abs. 2 Ziff. 1 stated as what the reader checks.
5. **bicycle_voucher** (theft_at_home, simple_theft_away)
   - Old: "the bicycle, if its voucher can be obtained without considerable cost"
   - New: "the bicycle it is for (make, model or type)"
   - Cited passage (the document's rule, basis follows): Ziff. 8 lit. c, S. 3: "auf Verlangen, ein Verzeichnis der vom Schaden betroffenen Sachen mit Wertangaben zu erstellen und Originalbelege beizubringen;"
   - Also cited on the document: Abschnitt 3.9, S. 3: "Fahrrad (bitte Originalkaufbelege beilegen)"
   - Why: The 'if' clause is a need condition (needed_when: bicycle and not vouchers_unobtainable), not content. Now names what the voucher shows, as the generator's checkable_as already did.

### Considered and not changed

- `insurance_policy` (away) "its sum insured": names one visible amount and is kept. Note for the planner: the generator's checkable_as asks for the sum insured for household contents, while Ziff. 24.2 caps simple theft away at "der in der Police vereinbarten Versicherungssumme" for that cover; the two readings differ and neither is changed here (item notes stay as they are).
- `police_report` "that the theft was reported to the police and when", `police_consent` "that the police consented": statements visible on the police document. Kept.
- `bicycle_voucher` and `original_vouchers` "where and when ... was bought": a voucher always records a purchase. Kept.

### Hashes after revision 2

- rules.json af60c0b4bae1887f0d21b9aabbb138c9c36a95c97a8a2bca9d7ef517ada34782
- rule_text.md a04dff19fab3ca196854935e08e9680e692813fd573ce001a13cc9ef2199288a
- MUST_SHOW_WORDING.json 960a06f46f1da5e7e12f97c324c26f4778df35c9da682b6738171cb8196aa064
- workflow/simple_theft_away.json fe5d1bce4f79559e204da9522345eae867cab115e57c67504220db4fccd5476a
- workflow/theft_at_home.json 767d0e17a42d52935e4ec5a9ba1f2c22070f10f8c7ac3ebf8d8453832f00ea30

State before revision 2 (`rev1/`, equal to the hashes after revision 1 above):

- rev1/rules.json f366a1cf4d0bc7d1e43dc665d21531afdb19d9e77410dc169b30b263c4b991b2
- rev1/rule_text.md 4a6fbe444d13deb4498e4806a9e1ad175cfdb467800f753e5c138aa0e872f937
- rev1/workflow/simple_theft_away.json 320a346001d595ff9c564314ef47fe50c26992071f48c7d60bf15eea1bad21f2
- rev1/workflow/theft_at_home.json cd19a336c5e8fcd57c3da5e2effd0fff9894bea6fb53b31340eb03dd01976ed2

## Revision 3 after the second look (development, 2026-11-12)

DEVELOPMENT material. The second reader's "Second look, revisions 1 and 2" (end of `CITATION_CHECK.md`) is applied as
the reader worded it; the planner accepted every disagreement and ruling. Edited in `tools/build.py` (table
`MUST_SHOW_REV3`; `MUST_SHOW_WORDING.json` now lists every earlier wording of each item) and rebuilt. The state before
is kept in `rev2/` (`rules.json`, `rule_text.md`, `MUST_SHOW_WORDING.json`, `workflow/`) and
`generator/items/rev2/theft.json`.

**Parity of words (all regimes).** `rule_text.md` now carries a section "Which claim type applies (routing)" with the
routing question exactly as the workflows give it, its values and, where it has one, its not_this text, generated by
`build.py`. `tools/check.py` fails when any workflow fact's wording (the routing fact included, with its values, and
both parts of a question that carries "(Not this: ...)") does not occur in `rule_text.md` (on `rev2/` it reports the
routing question missing for tenancy and dismissal).

Changes:

1. **insurance_policy** (simple_theft_away), cover item (R2-2), agreed by the second reader as worded.
   - Old: "the supplementary insurance for simple theft away (Ziff. 24.2), listed among the policy's covers as included or as not included"
   - New: "the complete list of the covers included in the policy (the supplementary insurance for simple theft away, Ziff. 24.2, is insured only if it is on that list)"
   - Passage: Ziff. 24, Einleitung: "Die CSS versichert die nachfolgend beschriebenen Gefahren, sofern diese vom Versicherungsnehmer gewünscht und in der Police aufgeführt worden sind:". Item note: `checkable_as` now asks for the complete list and no "not included" entry.
2. **insurance_policy** (simple_theft_away), sum insured (ruling b), agreed by the second reader as worded.
   - Old: "its sum insured"
   - New: "Only if the file states that the policy includes the supplementary insurance for simple theft away (Ziff. 24.2): the sum insured agreed for that cover. Otherwise this item does not apply."
   - Passage: Ziff. 24.2: "Schäden am Hausrat durch Diebstahl, der weder als Einbruchdiebstahl noch als Beraubung gilt und sich ausserhalb des versicherten Standortes ereignet, sind bis zu der in der Police vereinbarten Versicherungssumme mitversichert." Item note: now conditional, `applies_when` away_cover_missing stated false, `checkable_as` the sum of that cover (no longer the household-contents sum).
3. **stolen_items_list** (both types), acquisition (R2-3), agreed by the second reader as worded.
   - Old: "for each item, where and when it was bought, or, for an item that was not bought, that it was a gift or inherited and when"
   - New: "for each item, where and when it was bought, or, for an item that was not bought, how and when it was acquired (for example as a gift or by inheritance)"
   - Passage: Ziff. 8 lit. c ("ein Verzeichnis der vom Schaden betroffenen Sachen mit Wertangaben zu erstellen"), with the form's columns (Abschnitt 3.7, Spalten: "Gegenstand Gekauft bei Kaufdatum Ersatzwert /Reparaturkosten Gemäss separater Liste"). Item note: `checkable_as` widened the same way.
4. **Routing** in `rule_text.md`: question, values and not_this now each stated (they were there as one sentence; values added).

**Checks.** `tools/check.py`: all checks passed (with the parity check). `generator/test_generator.py`: 19 tests OK.
`lint/verify_rev3.py` (`lint/VERIFY_REV3.json`): every final reference and design keeps its manifest hash and is
recomputed unchanged; clean-room agreement unchanged (450 of 450); rules and workflows equal `rev2/` outside the
must_show wording and the named changes (none outside must_show).

**Files touched.** See `dev/REPAIR_R4.md`. The items-list change only widens what shows the item: no designed state changes. Policies (simple_theft_away, 9 supplied): a script check of the texts against the revised `checkable_as` finds the cover's sum wherever the cover is included (5 files) and a cover list in 8; the_d9579f891719 now misses a second item and is dropped by the standing rule (rewritten in round 2); completeness of the list needs a reading, so 7 policies are re-checked in repair round 4. **the_dd72ec4e53dd is not changed**: its designed missing item was the sum insured, which under ruling (b) no longer applies (the file states the cover is not included); its designed state and its reference (present_insufficient) would change. Left for the planner.

### Hashes after revision 3

- rules.json 07bcf54f05a6942e65cd3ffdf9eaaacaa98aca0e0d956268437b7137290850e2
- rule_text.md 1aba2d4ef87699bde5f931c3c4b76f15320f51df7ac3da6ee2b0f4e18deedf67
- MUST_SHOW_WORDING.json 339fff28a14aeb147fc746aa5c3c4d1b3e864de2d3b5aef15e4eba3b40ece4f5
- workflow/simple_theft_away.json a185af6bacbb7867106beb9f2e94f02a709265138f291b7e580c5d00faf8a170
- workflow/theft_at_home.json 846c298a63a2a5665af71e395f159089b1b63ca999eeb2a9258af4dd62e33464
