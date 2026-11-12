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
