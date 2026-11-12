# Reconciliation of the tenancy rule set with CITATION_CHECK.md

Writer's response to the second reader's check (SPEC.md item 7). `CITATION_CHECK.md` is unchanged. The coordinator's
decisions on the five main findings were applied; no cited text contradicted them. Rebuilt with `tools/build.py`; `tools/check.py` passes.

Legend: **accepted** = the proposed change was applied; **changed differently** = another change meets the
objection; **kept** = wording kept, with the supporting passage.

## The 18 non-agree lines

| # | rule id (check) | reader's point | what I did | why |
|---|---|---|---|---|
| 1 | defect_present (C) | `not_this` imports art. 259 (not cited); a conceded shared cause would be "no" and stopped | **accepted**: Q now says "the tenant alone caused the defect or must remedy it at his own expense"; `not_this` says a shared or disputed cause is open, not no; art. 259 citation dropped; stop inference says the same | art. 259a para. 1 excludes only defects "not attributable to the tenant" / those he must remedy "at his own expense" |
| 2 | landlord_not_informed (D) | the statute's condition is the landlord's awareness (arts. 259b, 259d), not the tenant's notice; para. 1 is only the duty | **accepted, with an addition**: fact renamed `landlord_unaware`, reader's wording ("the landlord does not yet know of the defect …"); locator art. 257g para. 2, with art. 259b as a second checked passage (`also`). Added fact `notice_oral_only` (art. 257g para. 1) | coordinator decision 1; true-is-exceptional polarity kept (6b) |
| 3 | dh_notice (C) | reached on "tenant informed", narrower than "landlord aware"; inference restates the convention as law | **accepted**: reached when defect_present and landlord_unaware is no; reader's inference wording | art. 259b "Where the landlord is aware of a defect" |
| 4 | defect_notification (C) | landlord's knowledge has other proofs; oral notice cannot produce a mandatory "tenant's notice"; ground is 259b, not 259d | **accepted**: now `knowledge_proof` "Proof of when the landlord learned of the defect (tenant's dated notice, landlord's or manager's acknowledgement, or inspection record)", must_show "how and when the landlord learned of the defect"; locator art. 259b with art. 259d as `also`. Oral notice: the document is needed only when `notice_oral_only` is no. Stated oral-only: not requested. Raised but unsettled: held behind that question (product shows "depends"). Unmentioned: requested (convention) | coordinator decision 1. Art. 257g para. 1 ("must inform", German "melden") prescribes no form, so oral notice is lawful and leaves no written trace |
| 5 | notice_received (C) | disputed receipt would be "no" and stopped | **accepted, wording extended**: Q "Has the landlord given the tenant notice terminating the lease of the dwelling, and has it reached the tenant?"; `not_this` "No: only a file stating that no notice of termination has been given at all … A notice the landlord says was sent and the tenant says never reached him is open, not no." | coordinator decision 2; art. 273 para. 1 runs from receipt, so disputed receipt is open |
| 6 | family_residence (C) | heading-based limit is sound, but a lay reader cannot follow it; quote the heading, name art. 266m para. 1 | **changed differently (stronger)**: art. 266m added to both snapshots. The locator is now art. 266m para. 1 (passage "Where the leased property serves as the family residence"), with art. 266m para. 3 (registered partners) and art. 266n as checked `also` passages. The inference quotes the heading "Family residence" (Wohnung der Familie) | coordinator decision 5; the condition now has its own verbatim passage instead of resting on the heading alone |
| 7 | lt_family (C) | basis should be `follows`; the family-home condition comes from the heading | **accepted**: basis `follows`; inference names the heading and art. 266m para. 1 (also-passage) | as reader |
| 8 | lt_extension (C) | art. 273 para. 5: extension examined ex officio after a failed challenge; step narrower than the article | **accepted (reader's first option)**: step reached when notice_received yes and arrears_termination no; hardship_evidence needed only if extension_requested; art. 273 para. 5 added as `also` passage and named in the inference | coordinator decision 3. Art. 272a para. 1 let. a still excludes arrears notices |
| 9 | termination_notice, termination type (C) | title "…or written threat" invites taking a threat as a notice; must_show add "in writing and signed" | **accepted in part**: shared document split by narrowing. Title is now "Landlord's notice of termination" in both types; the rent type no longer requests a threat letter (see 17b). must_show "given in writing" added (art. 266l para. 1 added as `also`). "signed" **not added** | "signed" has no passage in the snapshot: art. 266l para. 1 says only "must be given in writing" |
| 10 | spouse_service (C) | a mandatory "copy served separately" cannot exist where the claim is that it was not served | **accepted**: title "Proof of separate service on the spouse or registered partner (the spouse's own copy with envelope or tracking), or the spouse's statement that no separate copy was received" | as reader |
| 11 | stop, termination (C) | sound only where no notice was given; not for disputed receipt | **accepted**: reader's inference wording; "a notice whose receipt is disputed is open and does not stop" | as 5 |
| 12 | increase_notified (C) | a higher rent charged without any notice would be stopped although void under art. 269d para. 2 | **accepted**: fact renamed `increase_applied`: "Does the claim state that the landlord has announced, demanded or charged a higher rent for the dwelling, by a notice, a letter, an invoice or otherwise …?"; locator moved to art. 269d para. 2 let. a. The notice stays a mandatory document whose absence is itself the finding (must_show line added) | coordinator decision 2 |
| 13 | cost_or_services_reason (C) | "decides whether it is unfair" overstates art. 269a ("in general"); workflow lacks the always_stated marker | **accepted**: inference "bears on whether it is unfair (art. 269a: 'in general' not unfair, German 'in der Regel')"; workflow fact now carries `always_stated: true` (extra key; validator passes) | as reader |
| 14 | ri_form (C) | art. 269d para. 5: written form suffices for a graduated step | **accepted**: inference adds the exception; art. 269d para. 5 added as `also` passage | coordinator decision 3 |
| 15 | rent_increase_notice (C) | must_show tests the cantonal form for every increase | **accepted**: must_show "whether the form approved by the canton is used (for a graduated-rent step, whether it is in writing: art. 269d para. 5)"; art. 269d para. 5 as `also` | as reader |
| 16 | proof_of_receipt, rent type (C) | art. 269d para. 1 says "give … at least ten days before", not "reach"; receipt rule is art. 270b para. 1 | **accepted**: locator art. 270b para. 1; art. 269d para. 1 as `also`, inference "shows when the notice was given relative to the ten-day rule" | as reader |
| 17 | cost_breakdown (C) | a breakdown is the landlord's assertion; the proof is the underlying record | **accepted**: title "… with the supporting invoices, interest notices or cost statements"; must_show adds "supporting invoices or statements" | as reader |
| 18 | stop, rent type (C) | sound only after the fact is widened | **accepted**: inference "where the claim states that the landlord has neither announced nor demanded nor charged a higher rent …" | as 12 |

Count: 16 accepted (items 2 and 4 with an addition), 1 changed differently (6), 1 accepted in part (9: "signed" not added). No line kept unchanged.

## Further changes (completeness findings, coordinator decision 4, optional suggestions)

| # | finding | what I did | why |
|---|---|---|---|
| 17b | split of the shared notice document (decision 4) | Rent fact `termination_threat` narrowed and renamed `termination_with_increase` ("…gave notice of termination"). Its basis changed from `states` to `follows`. A threat without a notice is now read from the increase notice, whose must_show adds "any threat of termination in it or in the covering letter". The rent type requests "Landlord's notice of termination", the same id and title as in the termination type | keeps the catalogue at 14 without a threat document; narrower than art. 269d para. 2 let. c, which SPEC item 4 allows. **New wording, needs the reader's look** |
| C3 | art. 259h para. 1: conciliation filing after a deposit | **added by merging**: `deposit_receipt` is now "Receipt of the deposit office for the deposited rent and the tenant's application to the conciliation authority"; must_show adds "due date of the first deposited rent" (reader's optional suggestion) and the filing date | one passage covers both items (claims "before the conciliation authority within 30 days of the due date for the first rent payment paid into deposit") |
| C4 | art. 271 para. 2: landlord's stated reasons | **added by merging**: `prior_claims_correspondence` became `claims_and_reasons`, "Correspondence on the tenant's claims and the landlord's reasons for the notice". It includes conciliation or court documents (reader's optional suggestion); art. 271 para. 2 is an `also` passage | art. 271a para. 1 let. a turns on "because": the tenant's claims and the landlord's stated reasons both bear on it |
| C6 | art. 257d para. 2: payment within the time limit | **added by merging**: `payment_demand` became "Landlord's written payment time limit with warning of termination, and the tenant's record of payments made within it". The locator moved from art. 257d para. 1 to para. 2 (para. 1 stays on the step, with the "schriftlich" note) | para. 2: "In the event of non-payment within the time limit …" |
| C5 | art. 271a para. 2: settlement documents | **not added** | it serves art. 271a para. 1 let. e (three-year protection after proceedings), which this rule set does not model. That fact was dropped for size in the first version |
| C7 | art. 270c: index values | **not added** | no slot left within 14; the lease's index clause and the increase notice usually state the index values. Candidate if a document is freed |
| C8 | art. 272a para. 2: offer of equivalent premises | **not added** | the landlord's defence; an offer would come from the landlord, so it does not change which documents the handler requests from the tenant before assessment, and there is no slot |
| C9 | invalid graduated or index clause (arts. 269b/269c) should route back to the unfairness check | **not done** | it would need a fact on the clause's validity, which is assessed from the lease after the documents arrive. Noted as a known limit |
| — | `not_this` lines citing articles outside the snapshot (259, 257e, 266, 270) (decision 5) | dropped those citations, kept the words; `check.py` now fails on any article cited in a question or `not_this` that is not in the snapshot | coordinator decision 5 |

Catalogue: still 14 documents, with no document dropped. The additions were made by merging into documents whose single passage covers them. Ids changed:
- `defect_notification` → `knowledge_proof`
- `prior_claims_correspondence` → `claims_and_reasons`

Facts:
- renamed: `landlord_not_informed` → `landlord_unaware`; `increase_notified` → `increase_applied`; `termination_threat` → `termination_with_increase`
- added: `notice_oral_only`

## Not accepted, for the reader's second look

1. **termination_notice (lt), "signed"** (item 9): not added to must_show. Supporting passage: art. 266l para. 1, "Notice to terminate leases of residential and commercial premises must be given in writing." The snapshot has no signature requirement.
2. **C5 settlement documents** (art. 271a para. 2): not added, because let. e is not modelled.
3. **C7, C8, C9**: not added, for the reasons given above.

New or rewritten rules the reader has not yet checked:
- `notice_oral_only` (art. 257g para. 1)
- `termination_with_increase` (17b)
- the merged documents `deposit_receipt`, `claims_and_reasons` and `payment_demand`
- `increase_applied` (now on art. 269d para. 2 let. a)
- `family_residence` (now on art. 266m para. 1)

Reader's second look of 2026-11-12: both readers agree on every rule. After that look, four further edits were made: art. 257d para. 1 cited as a further passage on payment_demand; the hardship_evidence inference reworded; index values and the valid-agreement note added; workflows marked reviewed. Hashes after these edits: rules.json 3f5bb8564c799bb493a96b80d68905bdfa4cb8258f84412bc7911be0ad8470b5; rule_text.md 6ab770facf648e08e3453f0f7a1fe653f12928eed1c3c283547bff20d775631a; workflow/defect_mold_heating.json 13f642d14588ae3608ace7f78e125a94327cf7617f947a37042a9a0ea3e5dddb; workflow/lease_termination_dispute.json a8518ecb78d3d5343e791c222cef7590dd0edf68cb807387ae6e1b7da51f00dd; workflow/rent_increase_dispute.json 5a99506e4029587fa82a180200ffea2c17d5f8e798c5fb94dc345a2f49ee6ac0.

Clarification after review (2026-11-12): one general paragraph on reading steps and stops added to rule_text.md and rules.json; no rule changed. New SHA-256 (workflows byte-identical to before the clarification):

- rules.json 5c0e05c04987acc02a88bd1e991fd55d72cc138560f3993c832dbaf893a247a3
- rule_text.md e644e52675f7e35a1c415f6e219d191de91feb6166f7855a73af313cce501e65
- workflow/defect_mold_heating.json 13f642d14588ae3608ace7f78e125a94327cf7617f947a37042a9a0ea3e5dddb
- workflow/lease_termination_dispute.json a8518ecb78d3d5343e791c222cef7590dd0edf68cb807387ae6e1b7da51f00dd
- workflow/rent_increase_dispute.json 5a99506e4029587fa82a180200ffea2c17d5f8e798c5fb94dc345a2f49ee6ac0

## Revision after first use (development, 2026-11-12)

DEVELOPMENT material, post hoc. The rule set's first use (the clean arm of the lint test, `lint/REPORT.md`, gpt-6-luna,
59 tenancy files) was diagnosed from the stored readings in `lint/DIAGNOSIS.md` (written by `lint/diagnose.py`;
judgments in `lint/diagnosis_review.json`). Only wording that Part A showed to be ours is changed; each change is a
general rule, written in `tools/build.py` (the authoring source of `rules.json`, `RULES.md`, `rule_text.md` and
`workflow/*.json`) and rebuilt. The fixes were designed on the same 59 files they are checked on (in-sample,
development). The rule set as the lint runs read it is kept in `rev0/` (`rules.json`, `rule_text.md`, `workflow/`).

Not changed: no document, `needed_when`, `mandatory` or `must_show` item; no fact id, step, condition, presumption or
stop; the convention of SPEC 6a; the routing values (the type ids). `lint/verify_rev1.py` (`lint/VERIFY_REV1.json`)
confirms that the rules' and workflows' logic is equal to `rev0/`, that every stored `dev/tenancy/final/*/reference.json`
still has its manifest hash, that the product's evaluator recomputes all 59 final references unchanged with the revised
workflows, and that the clean-room comparison on the 60 designs still gives 354 of 354 document states equal to both
evaluators. `tools/check.py`: all checks passed. `generator/test_generator.py`: 15 tests OK.

### T1. Routing question (workflow fact `dispute_family`) and the defect type's title

- **Old question:** "Which tenancy dispute does the claim concern: a defect of the dwelling (mould, damp, heating), a
  termination of the lease by the landlord, or a rent increase?"
- **New question:** "Which tenancy dispute does the claim concern: a defect of the dwelling or a disturbance of its
  agreed use that the tenant did not cause (for example mould, damp, or heating that fails), a termination of the lease
  by the landlord, or a rent increase? A rent increase that the landlord accompanied with a notice of termination is a
  rent increase dispute: the rent-increase rules examine that notice (art. 269d para. 2 let. c)."
- **Old title:** "Defect of the rented dwelling (mould, damp, heating)". **New title:** "Defect of the rented dwelling
  or disturbance of its use (for example mould, damp, heating)". The router is shown the workflow titles beside the
  routing values and is told that a value naming a specific matter applies only to that matter.
- **Evidence (Part A):** 3 of 51 non-denied tenancy files failed routing on the cost-efficient model, all three on this
  wording. ten_c2a72cbf1698 (designed type defect, defect stated: night-time noise and vibration from a bar in the
  building) got no routing value: the parenthesis "(mould, damp, heating)" reads as a closed list, narrower than the
  type's defining event, which covers any defect not caused by the tenant and any disturbance of the agreed use
  (`defect_present`); 3 errors. ten_b4d4cb05336f and ten_e4858b3af131 (designed rent increase with
  `termination_with_increase` stated true) were routed to lease_termination_dispute, quoting the termination ("I'd like
  to know whether I can fight the termination, and whether I have to pay the higher rent ..."); the rule set already
  decides that case inside the rent-increase type, the routing question did not say so; 1 error (the two types share
  some document ids, so ten_b4d4cb05336f scored 0).
- **Passages:** art. 259a para. 1 ("Where defects arise in the object which are not attributable to the tenant or
  lessee and which he is not obliged to remedy at his own expense, or where he is prevented from using the object as
  contractually agreed, ..."; German "oder wird der Mieter im vertragsgemässen Gebrauch der Sache gestört"), the
  passage of `defect_present`; art. 269d para. 2 let. c ("c. notice of the increase is accompanied by notice to
  terminate or a threat of termination."), the passage of `termination_with_increase`.
- **Why no broader and no narrower:** the defect value now names exactly what the defining event's passage names
  (defect not caused by the tenant, or disturbed agreed use), with the earlier examples kept as examples. The
  precedence sentence covers only an increase notice accompanied by a notice of termination, the condition of art. 269d
  para. 2 let. c; a notice of termination given separately stays a termination dispute.

### T2. `lease_termination_dispute.asserted_claims` (question)

- **Old:** "Does the claim state that the landlord gave notice because the tenant had, in good faith, asserted claims
  under the lease (for example demanded repair of a defect or contested the rent)?"
- **New:** the same, followed by: "The tenant's own account of the landlord's reason counts as stating it, also where
  the tenant gives it as a conviction or belief; it is open only where the claim itself says the reason is unknown,
  uncertain or one of several possibilities."
- **Evidence (Part A):** of the 6 files in which the fact is stated true, 2 had a reading answering "open" on a firm
  statement of the tenant's belief about the landlord's motive ("I am convinced the real reason for the notice is my
  complaint from 15 January 2026", two readings of three; "Ich bin ziemlich sicher, warum mir die ... AG die Wohnung
  gekündigt hat: weil ich mich gewehrt habe", one of three). The product held the fact and the correspondence
  document: 2 holds where the file settles the fact. The same gap appears in dismissal (`retaliation_for_claims`, 3 of
  5 stated-true files). The tenancy workflows pass only the question to the product (not `not_this`), so the
  clarification is in the question.
- **Passage:** art. 271a para. 1 let. a ("Notice of termination served by the landlord may be challenged in particular
  where it is given: a. because the tenant is asserting claims arising under the lease in good faith;").
- **Why no broader and no narrower:** the condition ("because ... claims ... in good faith") is unchanged; the sentence
  says only how a tenant's statement of the landlord's reason is read at intake, where the reason can only be the
  tenant's own account. A claim that leaves the reason in doubt stays open, as the convention's "raises and leaves
  unsettled" says.

### Considered and not changed

- `rent_increase_dispute.index_clause` (ten_a743587360f3, 1 hold): one reading answered open on "Soweit ich das
  verstehe, kommt das von der Klausel in meinem Vertrag"; a hedged account of a lease clause is a defensible "open",
  so this is the product's reading of a hedge, not our wording.
- `defect_present` held in ten_270f84d8acff (4 holds): all three readings answered true, but their quotations were not
  found word for word in the scan-noised text; the product's quotation rule, not the wording.
- Needed but not allowed in this revision: three `must_show` items are conditional and the product read them as
  required ("any graduated-rent or index clause" of `lease_contract`, "conciliation or court documents on those claims,
  if any" of `claims_and_reasons`, and "(with any covering letter)" in the title of `rent_increase_notice`): 3 requests
  that should not be made. Saying in each item that it is due only where the thing exists would be a `must_show`
  change; left for the planner.

### Hashes after the revision

- rules.json 7168b8ccee5a155e7926e9900c17f8ff0d2c70d7d43c0fd8d7ae3d15cddd4440
- rule_text.md 76d286d6dd0c275cc67a6488e46fb3f94e3f1e8436274a33c2a69dfdc7543faa
- workflow/defect_mold_heating.json f8a4acca431b4224ca7a045c08a61e124d6fe9c378a0bceaa3d6a450f3eb66d1
- workflow/lease_termination_dispute.json bcb52353f437fecd0f6e7cc7095db14bdeb1de5ab19a30927585f06e80d8a9e0
- workflow/rent_increase_dispute.json 8a698a764c8035e15e9d67bd9220d244baf861eb00f6852c857eb4123c422eda

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
`generator/items/rev1/tenancy.json`.

Not changed: no document, title, step, `needed_when`, `mandatory`; no fact, question, `not_this`, presumption or stop;
which items are conditional and when they apply (`generator/items/tenancy.json`: only `item` keys renamed, and the entry of the removed item dropped).
`lint/verify_rev2.py` (`lint/VERIFY_REV2.json`) confirms: rules.json and every workflow equal `rev1/` except the
must_show wording, read through `MUST_SHOW_WORDING.json`; every stored `dev/tenancy/final/*/reference.json` and `design.json`
still has its manifest hash; the product's evaluator recomputes every final reference unchanged with the revised
workflows; the clean-room comparison on the 60 designs gives the same document states as both evaluators for all
documents; for every design and item the notes give the same conditional / applies / checkable_as as before; every
writer bundle is the same once item texts are mapped. `tools/check.py` passes and now enforces the fixed form, no
"whether" and no absence wording (it reports the old wording in `rev1/` as failing). `generator/test_generator.py`:
all tests pass.

Changed items (9 rows (9 item instances): 8 reworded, 1 removed):

1. **termination_notice** (lease_termination_dispute)
   - Old: "whether the form approved by the canton is used"
   - New: "a statement of the form used: the printed title of the form approved by the canton, or a sentence on the notice that it is or is not given on that form"
   - Cited passage (the document's rule, basis evidence): Art. 266l para. 2: "The landlord must give notice of termination using a form approved by the canton which informs the tenant how he must proceed if he wishes to contest the termination or apply for an extension of the lease." (German: "Der Vermieter muss mit einem Formular kündigen, das vom Kanton genehmigt ist und das angibt, wie der Mieter vorzugehen hat, wenn er die Kündigung anfechten oder eine Erstreckung des Mietverhältnisses verlangen will.")
   - Why: Asked 'whether'; every notice shows a 'whether' (silence reads as 'no'), so a sufficient and an insufficient copy cannot be told apart. Now names the statement that must be visible.
2. **spouse_service** (lease_termination_dispute)
   - Old: "where the notice followed a payment time limit (art. 257d): the separately served copy of that time limit"
   - New: "Only if the file states that the landlord terminated because rent or accessory charges were not paid within a payment time limit (art. 257d): the copy of that payment time limit served separately on the spouse or registered partner. Otherwise this item does not apply."
   - Cited passage (the document's rule, basis evidence): Art. 266n: "Notice of termination given by the landlord and any notification of a time limit for payment accompanied by a warning of termination in the event of non-payment (Art. 257d) must be served separately on the tenant and on his spouse or registered partner." (German: "Die Kündigung durch den Vermieter sowie die Ansetzung einer Zahlungsfrist mit Kündigungsandrohung (Art. 257d) sind dem Mieter und seinem Ehegatten, seiner eingetragenen Partnerin oder seinem eingetragenen Partner separat zuzustellen.")
   - Condition: fact `arrears_termination` ("Does the notice or the claim state that the landlord terminated because the tenant did not pay overdue rent or accessory charges within a time limit the landlord had set?"), Art. 257d para. 2: "In the event of non-payment within the time limit the landlord or lessor may terminate the contract with immediate effect or, for leases of residential and commercial premises, subject to at least 30 days’ notice ending on the last day of a calendar month." (German: "Bezahlt der Mieter innert der gesetzten Frist nicht, so kann der Vermieter fristlos, bei Wohn- und Geschäftsräumen mit einer Frist von mindestens 30 Tagen auf Ende eines Monats kündigen.")
   - Why: Condition at the start in a loose form ('where ...:'); now the fixed form. The condition is the generator's (`arrears_termination` stated true) and the file fact's wording.
3. **claims_and_reasons** (lease_termination_dispute)
   - Old: "conciliation or court documents on those claims, if any"
   - New: "Only if the file states that the tenant's claims were brought before a conciliation authority or a court: the conciliation or court documents on those claims. Otherwise this item does not apply."
   - Cited passage (the document's rule, basis evidence): Art. 271a para. 1 let. a: "Notice of termination served by the landlord may be challenged in particular where it is given: a. because the tenant is asserting claims arising under the lease in good faith;" (German: "Die Kündigung durch den Vermieter ist insbesondere anfechtbar, wenn sie ausgesprochen wird: a. weil der Mieter nach Treu und Glauben Ansprüche aus dem Mietverhältnis geltend macht;")
   - Why: 'if any' lets an absence satisfy the item, and the product read it as required (ten_5822f6df0cb7). Now the fixed form; the generator leaves this condition to the story (conditional, no applies_when), and so does the wording: no fact of the rule set records a filing.
4. **deposit_receipt** (defect_mold_heating)
   - Old: "date the claims were brought before the conciliation authority (or that they have not yet been)"
   - New: "the date on which the claims were brought before the conciliation authority, or a sentence that they have not yet been brought"
   - Cited passage (the document's rule, basis evidence): Art. 259h para. 1: "The landlord becomes entitled to the rent paid on deposit if the tenant or lessee does not bring claims against him before the conciliation authority within 30 days of the due date for the first rent payment paid into deposit." (German: "Hinterlegte Mietzinse fallen dem Vermieter zu, wenn der Mieter seine Ansprüche gegenüber dem Vermieter nicht innert 30 Tagen seit Fälligkeit des ersten hinterlegten Mietzinses bei der Schlichtungsbehörde geltend gemacht hat.")
   - Why: '(or that they have not yet been)' reads as satisfied by silence; the generator already requires an explicit sentence (checkable_as). Now names the sentence that must be visible.
5. **lease_contract** (rent_increase_dispute)
   - Old: "any graduated-rent or index clause"
   - New: "Only if the file states that the increase is a graduated-rent step or applies an index clause: the lease clause that fixes the graduated steps or links the rent to an index. Otherwise this item does not apply."
   - Cited passage (the document's rule, basis evidence): Art. 269d para. 1: "The landlord may at any time increase the rent with effect from the next termination date." (German: "Der Vermieter kann den Mietzins jederzeit auf den nächstmöglichen Kündigungstermin erhöhen.")
   - Condition: fact `graduated_rent` ("Does the claim state that the increase is a step fixed in advance in the lease, by which the rent rises periodically by fixed amounts (graduated rent)?"), Art. 270d: "Without prejudice to the right to challenge the initial rent, the tenant may not challenge periodical rent increases." (German: "Unter Vorbehalt der Anfechtung des Anfangsmietzinses kann der Mieter gestaffelte Mietzinse nicht anfechten.")
   - Condition: fact `index_clause` ("Does the claim state that the increase applies a clause of the lease linking the rent to an index (such as the Swiss consumer price index)?"), Art. 270c: "Without prejudice to the right to challenge the initial rent, a party may argue before the conciliation authority only that the rent increase or reduction requested by the other party is not justified by a corresponding change in the index." (German: "Unter Vorbehalt der Anfechtung des Anfangsmietzinses kann eine Partei vor der Schlichtungsbehörde nur geltend machen, dass die von der andern Partei verlangte Erhöhung oder Herabsetzung des Mietzinses durch keine entsprechende Änderung des Indexes gerechtfertigt sei.")
   - Why: 'any ... clause' is satisfied by an absence and the product read it as required (ten_db552dbb3c23). Now the fixed form with the generator's condition (graduated_rent or index_clause stated true).
6. **rent_increase_notice** (rent_increase_dispute)
   - Old: "whether the form approved by the canton is used (for a graduated-rent step, whether it is in writing: art. 269d para. 5)"
   - New: "a statement of the form used: the printed title of the form approved by the canton, or a sentence on the notice that it is or is not given on that form"
   - Cited passage (the document's rule, basis evidence): Art. 269d para. 2 let. a–b: "The rent increase is void where: a. it is not communicated using the prescribed form; b. no reasons are given;" (German: "Die Mietzinserhöhung ist nichtig, wenn der Vermieter: a. sie nicht mit dem vorgeschriebenen Formular mitteilt; b. sie nicht begründet;")
   - Why: Asked 'whether' (ten_db552dbb3c23 round 1: designed missing, read sufficient). Now names the statement that must be visible, as the generator's checkable_as already did. The parenthesis on graduated-rent steps is dropped from the item: art. 269d para. 5 stays cited on this document (`also`) and on step ri_form, and a graduated-step notice shows the item by saying which form it uses.
7. **rent_increase_notice** (rent_increase_dispute)
   - Old: "any threat of termination in it or in the covering letter"
   - New: "Only if the file states that the landlord gave notice of termination together with the rent increase: the notice or threat of termination in the increase notice or its covering letter. Otherwise this item does not apply."
   - Cited passage (the document's rule, basis evidence): Art. 269d para. 2 let. a–b: "The rent increase is void where: a. it is not communicated using the prescribed form; b. no reasons are given;" (German: "Die Mietzinserhöhung ist nichtig, wenn der Vermieter: a. sie nicht mit dem vorgeschriebenen Formular mitteilt; b. sie nicht begründet;")
   - Condition: fact `termination_with_increase` ("Does the claim state that, together with the rent increase, the landlord gave notice of termination?"), Art. 269d para. 2 let. c: "c. notice of the increase is accompanied by notice to terminate or a threat of termination." (German: "c. mit der Mitteilung die Kündigung androht oder ausspricht.")
   - Why: 'any ...' is satisfied by an absence. Now the fixed form with the generator's condition (termination_with_increase stated true). A threat without a notice of termination still shows on the increase notice, which is requested anyway (termination_with_increase not_this); the item no longer makes its absence a content requirement.
8. **rent_increase_notice** (rent_increase_dispute)
   - Old: "for an index-linked increase: the old and new index values"
   - New: "Only if the file states that the increase applies an index clause: the old and the new index value. Otherwise this item does not apply."
   - Cited passage (the document's rule, basis evidence): Art. 269d para. 2 let. a–b: "The rent increase is void where: a. it is not communicated using the prescribed form; b. no reasons are given;" (German: "Die Mietzinserhöhung ist nichtig, wenn der Vermieter: a. sie nicht mit dem vorgeschriebenen Formular mitteilt; b. sie nicht begründet;")
   - Condition: fact `index_clause` ("Does the claim state that the increase applies a clause of the lease linking the rent to an index (such as the Swiss consumer price index)?"), Art. 270c: "Without prejudice to the right to challenge the initial rent, a party may argue before the conciliation authority only that the rent increase or reduction requested by the other party is not justified by a corresponding change in the index." (German: "Unter Vorbehalt der Anfechtung des Anfangsmietzinses kann eine Partei vor der Schlichtungsbehörde nur geltend machen, dass die von der andern Partei verlangte Erhöhung oder Herabsetzung des Mietzinses durch keine entsprechende Änderung des Indexes gerechtfertigt sei.")
   - Why: Condition at the start in a loose form ('for an ...:'); the round-1 blind check read it as required in ten_efa24ba18ce3 (the generator had treated it as optional). Now the fixed form with the generator's condition (index_clause stated true).
9. **rent_increase_notice** (rent_increase_dispute)
   - Old: "if the landlord gave no notice at all, that absence is itself the finding (art. 269d para. 2 let. a)"
   - New: removed
   - Cited passage (the document's rule, basis evidence): Art. 269d para. 2 let. a–b: "The rent increase is void where: a. it is not communicated using the prescribed form; b. no reasons are given;" (German: "Die Mietzinserhöhung ist nichtig, wenn der Vermieter: a. sie nicht mit dem vorgeschriebenen Formular mitteilt; b. sie nicht begründet;")
   - Condition: fact `increase_applied` ("Does the claim state that the landlord has announced, demanded or charged a higher rent for the dwelling, by a notice, a letter, an invoice or otherwise (whether or not on an official form)?"), Art. 269d para. 2 let. a: "The rent increase is void where: a. it is not communicated using the prescribed form;" (German: "Die Mietzinserhöhung ist nichtig, wenn der Vermieter: a. sie nicht mit dem vorgeschriebenen Formular mitteilt;")
   - Why: Removed. It names nothing visible on a document (an absent notice cannot show its own absence) and is satisfied only by an absence. The generator applied it only where increase_applied is stated false, where the type stops before the document is needed, so no file ever attached a notice it applied to (lint/VERIFY_REV2.json: 5 designs, all with the document not needed and not attached). The document's rule keeps the passage and its inference.

### Considered and not changed

- The title "Landlord's rent increase notice (with any covering letter)" keeps its "any": titles are not must_show items and 6c does not cover them (the diagnosis counts one request on it, ten_efa24ba18ce3). For the planner.
- `payment_demand` "payments made within the time limit (bank or postal records)": names a visible record; where nothing was paid the record shows no payment, which is the finding. Kept.
- `spouse_service`'s other items, and pairs such as "old and new rent", "sender and addressee", "date and addressee": one entry of the document each. Kept.
- The rule inference of `rent_increase_notice` still says that where no notice exists its absence is the point to establish: that is the rule's reasoning (art. 269d para. 2 let. a), not a content item.

### Hashes after revision 2

- rules.json b0ff1f07f988430a11ae9ab73e5d45e01dc29d4c5ecd63226fd63aa664902b79
- rule_text.md c2fe733c43d95c0acc880ecfb7f41051ae5a061c4e4297849df48d5d8e561e7a
- MUST_SHOW_WORDING.json 477d7626ec5b43ce4099b79b4aec5cdeade0c68154f5ee07af39d78dd28b26a5
- workflow/defect_mold_heating.json 4bfd015a354991c7cb77531a354c66ea6d79251b4ec991b7434065f3f12cfd1d
- workflow/lease_termination_dispute.json 9bdcaf5bfc0c3e2af96216a8dd2fb3a283d88eaee1c29a7023d53cfa2009101c
- workflow/rent_increase_dispute.json dfffd717e21c4e21091cd64d5195e104b40c8709c004f6d9948ec1b8e69a4416

State before revision 2 (`rev1/`, equal to the hashes after revision 1 above):

- rev1/rules.json 7168b8ccee5a155e7926e9900c17f8ff0d2c70d7d43c0fd8d7ae3d15cddd4440
- rev1/rule_text.md 76d286d6dd0c275cc67a6488e46fb3f94e3f1e8436274a33c2a69dfdc7543faa
- rev1/workflow/defect_mold_heating.json f8a4acca431b4224ca7a045c08a61e124d6fe9c378a0bceaa3d6a450f3eb66d1
- rev1/workflow/lease_termination_dispute.json bcb52353f437fecd0f6e7cc7095db14bdeb1de5ab19a30927585f06e80d8a9e0
- rev1/workflow/rent_increase_dispute.json 8a698a764c8035e15e9d67bd9220d244baf861eb00f6852c857eb4123c422eda

## Revision 3 after the second look (development, 2026-11-12)

DEVELOPMENT material. The second reader's "Second look, revisions 1 and 2" (end of `CITATION_CHECK.md`) is applied as
the reader worded it; the planner accepted every disagreement and ruling. Edited in `tools/build.py` (table
`MUST_SHOW_REV3`; `MUST_SHOW_WORDING.json` now lists every earlier wording of each item) and rebuilt. The state before
is kept in `rev2/` (`rules.json`, `rule_text.md`, `MUST_SHOW_WORDING.json`, `workflow/`) and
`generator/items/rev2/tenancy.json`.

**Parity of words (all regimes).** `rule_text.md` now carries a section "Which type applies (routing)" with the
routing question exactly as the workflows give it, its values and, where it has one, its not_this text, generated by
`build.py`. `tools/check.py` fails when any workflow fact's wording (the routing fact included, with its values, and
both parts of a question that carries "(Not this: ...)") does not occur in `rule_text.md` (on `rev2/` it reports the
routing question missing for tenancy and dismissal).

Changes:

1. **rent_increase_notice**, form item (R2-6), agreed by the second reader as worded.
   - Old: "a statement of the form used: the printed title of the form approved by the canton, or a sentence on the notice that it is or is not given on that form"
   - New: "a statement of the form used: the printed title of the form approved by the canton, or a sentence on the notice that it is or is not given on that form; for an increase the file states is a graduated-rent step, a written notice suffices instead (art. 269d para. 5)"
   - Passage: Art. 269d para. 5: "In the case of a rent increase in accordance with an agreement under Article 269c, it is sufficient that notice be given in writing." (cited on the document as `also`). Item note: `checkable_as` adds the same exception.
2. **rent_increase_notice**, title (ruling a), agreed by the second reader as worded.
   - Old: "Landlord's rent increase notice (with any covering letter)". New: "Landlord's rent increase notice". Id, need and mandatory flag unchanged. The covering letter matters only as the carrier of a notice or threat of termination (art. 269d para. 2 let. c: "c. notice of the increase is accompanied by notice to terminate or a threat of termination."), which the document's threat item (revision 2, R2-7) names.
3. **Routing question** in `rule_text.md` (parity), agreed by the second reader as worded: the reader's note on R1-2 (prompt-based designs saw only the titles).

**Checks.** `tools/check.py`: all checks passed (with the parity check). `generator/test_generator.py`: 19 tests OK.
`lint/verify_rev3.py` (`lint/VERIFY_REV3.json`): every final reference and design keeps its manifest hash and is
recomputed unchanged; clean-room agreement unchanged (354 of 354); rules and workflows equal `rev2/` outside the
must_show wording and the named changes (title: rent_increase_dispute.rent_increase_notice).

**Files touched.** None changes its designed state. The exception widens what shows the form item and applies only where the file states a graduated-rent step: of the seven supplied increase notices, ten_e4858b3af131 is the only one (designed missing "reasons given", unaffected), and ten_db552dbb3c23 (designed missing the form item) does not state a graduated step. No repair round for tenancy.

### Hashes after revision 3

- rules.json 48ae10805115ca60e19826fbcd6df924f1e82b575756c85dbf736d1f5199310f
- rule_text.md 97fd79def5cccaf50d3c727eca36eaa961cb459b615fa86759446c60a783e7be
- MUST_SHOW_WORDING.json a2989658d6f1a3fa759a24784b40ec418c715038d007d39cae09feafd08a25d2
- workflow/defect_mold_heating.json 4bfd015a354991c7cb77531a354c66ea6d79251b4ec991b7434065f3f12cfd1d
- workflow/lease_termination_dispute.json 9bdcaf5bfc0c3e2af96216a8dd2fb3a283d88eaee1c29a7023d53cfa2009101c
- workflow/rent_increase_dispute.json a6c94599b27458a8ea8d3d45e84879aaefcf1c1954b68c14038c651684d4a63f
