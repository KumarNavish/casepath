# Citation check: tenancy rule set (four-eyes, second reader)

Checked: `rules.json` (version 2026-11-12), `rule_text.md`, `RULES.md` (not read line by line; generated from the same data), `sources/SOURCES.json`, `sources/sr220-en.txt`, `sources/sr220-de.txt`, `workflow/*.json`, against SPEC.md "Rule sets from public text (step 2a)" items 1–7, 6a, 6b. The second reader did not write the rule set.

What actually ran:

- `python3 -I -B tools/check.py` from `study4/rules/tenancy/`: exit 0, "all checks passed" (51 rules: convention 1, evidence 18, follows 21, states 11; workflows validate).
- sha256 of both snapshots and both raw XML files equal the values in SOURCES.json. The snapshots were compared with the stored raw XML (no re-fetch was needed; no network call was made). The raw German XML confirms that art. 266n stands under "2. Wohnung der Familie / b. Kündigung durch den Vermieter", and that art. 266m para. 1 (not in the snapshot) begins "Dient die gemietete Sache als Wohnung der Familie".
- A scratch script checked every English and German passage of the 50 cited rules. It confirmed that each passage appears character for character in the snapshot inside the named article and paragraph, starts at the named letter, and has at most 60 words. All 100 checks passed.
- The convention text in `rules.json` is equal, string for string, to the block quote in SPEC.md 6a.

Verdicts: A = agree, C = agree with change, D = disagree.

## 1. Rule-by-rule table

### Convention

| rule id | kind | basis | verdict | reason | proposed wording |
|---|---|---|---|---|---|
| intake-convention | convention | convention | A | The words equal SPEC 6a exactly. It is declared "a convention, not law", cites no passage, and sits under `convention`, not `presumptions`. The workflow presumptions are only on branch facts: none is on a defining event, a stop-on-false fact or the one `always_stated` fact (cost_or_services_reason). | none |

### Type 1: defect_mold_heating

| rule id | kind | basis | verdict | reason | proposed wording |
|---|---|---|---|---|---|
| defect_present | fact (defining) | states | C | The passage excludes only defects "not attributable to the tenant" and those he must remedy "at his own expense". The `not_this` imports art. 259 ("minor cleaning or repairs"), which is not cited or snapshotted. A mould file in which the tenant concedes a shared cause (drying laundry plus poor insulation) would be answered "no" and stopped, although the passage does not plainly exclude it. | Q: "…without the claim itself saying that the tenant alone caused the defect or must remedy it at his own expense?" not_this: "A defect the claim itself attributes wholly to the tenant or says he must remedy at his own expense; a cause the claim calls shared or disputed is open, not no." |
| landlord_not_informed | fact | follows | D | The statute's condition is the landlord's awareness, not the tenant's notification: arts. 259b ("is aware") and 259d ("became aware"). The fact asks only whether the tenant informed. A file where the caretaker saw the mould, or the landlord inspected, but the tenant never wrote would be answered "yes", and the awareness step would be skipped. Para. 1 states only the duty to inform; it is para. 2 that makes a failure to notify something the landlord raises; the inference also imports art. 259d. | Q: "Does the claim state that the landlord does not yet know of the defect (the tenant has not reported it and the landlord has not learned of it otherwise)?" Locator: Art. 257g para. 2 ("Failure to notify renders the tenant … liable…"), with art. 259b as the passage for the step effect. |
| damages_claimed | fact | states | A | Art. 259e states the liability for damage the defect caused. The question asks for exactly that claim and excludes rent reduction. | none |
| deposit_intended | fact | states | A | Art. 259a para. 2 states the deposit right for immovable property, and a dwelling is immovable. `not_this` rightly excludes withholding without a deposit and the rental security. | none |
| rent_deposited | fact | follows | A | The inference (once rent is deposited, the 30-day period runs from the due date of the first deposited rent) is one step from art. 259h para. 1. | none |
| dh_scope | step | follows | A | One step from art. 256 para. 1: fitness is measured against the designated use. | none |
| dh_notice | step | follows | C | Art. 259b conditions the remedies on the landlord being aware. The step is reached on "tenant has informed", which is narrower than "landlord aware" (see landlord_not_informed). The inference also restates the intake convention ("unless the claim states…") as if it were law. | reached_when: defect_present true and landlord_unaware false (renamed fact). Inference: "The tenant's remedies under art. 259b depend on the landlord's knowledge, so when the landlord learned of the defect is established." |
| dh_damage | step | follows | A | One step from art. 259e. | none |
| dh_deposit | step | follows | A | Art. 259g para. 1 makes the deposit subject to written steps toward the landlord, so checking them follows. | none |
| lease_contract (dh) | document | evidence | A | The lease is the ordinary proof of the object and its agreed use. The "designated use" (vorausgesetzter Gebrauch) can also follow from circumstances, but the lease remains the first proof. | none |
| defect_record | document | evidence | A | Dated photographs or an inspection report prove that the defect exists, where it is and since when. An expert report proves cause better, but none of these proves "not attributable to the tenant", and the rule does not claim that. | none |
| defect_notification | document | evidence | C | The cited condition (art. 259d) is when the landlord became aware. The tenant's notice is one proof of that; the landlord's or manager's acknowledgement or an inspection record proves it as well or better. A tenant who informed orally (which `not_this` counts as informed) cannot produce a "tenant's notice" that is mandatory. Art. 259d concerns reduction only, which no fact in this type asks about; art. 259b grounds the need for all remedies. | Title: "Proof of when the landlord learned of the defect (tenant's dated notice, landlord's or manager's acknowledgement, or inspection record)". must_show: "how and when the landlord learned of the defect". Locator: Art. 259b (with 259d). |
| damage_evidence | document | evidence | A | Invoices, receipts and photographs are the ordinary proof of damage and its amount. | none |
| deposit_deadline_notice | document | evidence | A | Art. 259g para. 1 requires the time limit and the announcement in writing ("schriftlich" in both languages), so the letter is the proof. | none |
| deposit_receipt | document | evidence | A | The receipt shows which rent was deposited. Note: the 30-day period runs from the due date of the first deposited rent, not from the deposit date, so must_show "rent period it covers" is the operative item. | (optional) must_show "due date of the first deposited rent" |
| stop (defect_present false) | stop | follows | A | On art. 259a para. 1 alone it is sound: where the claim itself states that no defect or disturbance exists, or that the tenant caused it, no art. 259a right is engaged. It is sound only once defect_present is narrowed as proposed; otherwise a conceded shared cause ends the process. | none beyond the fact change |

### Type 2: lease_termination_dispute

| rule id | kind | basis | verdict | reason | proposed wording |
|---|---|---|---|---|---|
| notice_received | fact (defining) | follows | C | The inference is one step from art. 273 para. 1. However, "Has the tenant received…" will be answered "no" where the tenant says the registered letter never reached him and the landlord says it was sent; receipt is then disputed, and the stop ends a file that may be time-critical. | not_this add: "A notice the landlord says was sent and the tenant says never reached him is open, not no." |
| family_residence | fact | follows | C | The limitation to a family home rests on the marginal heading "Family residence / Notice given by the landlord" ("Wohnung der Familie"). That heading stands in the snapshot directly above the passage, and the adjacent art. 266m para. 1 (raw XML, not snapshotted) states the condition expressly ("Dient die gemietete Sache als Wohnung der Familie"). The step is therefore sound, and without it the condition would be broader (every married tenant). A lay reader cannot see why a heading binds, so the heading should be quoted verbatim and art. 266m para. 1 named. Polarity is acceptable: true is what the tenant raises to void the notice (art. 266o). | Inference: "…the marginal heading of art. 266n, '[…] / Family residence / Notice given by the landlord' (Wohnung der Familie), and art. 266m para. 1 ('Dient die gemietete Sache als Wohnung der Familie') limit separate service to a dwelling that is the family home." |
| arrears_termination | fact | states | A | Art. 257d para. 2 states the termination after non-payment within the time limit. Polarity is right: the landlord raises it to exclude an extension (art. 272a para. 1 let. a) and to disapply art. 271a para. 1 let. d–e (para. 3 let. b). The question is correctly limited to a prior time limit, so an ordinary notice merely motivated by arrears is "no". | none |
| asserted_claims | fact | states | A | Art. 271a para. 1 let. a, including "in good faith". `not_this` names the nearest case (claims not linked to the notice). | none |
| extension_requested | fact | states | A | Art. 272 para. 1. The fact is right as worded; the gap lies in the step (see lt_extension). | none |
| lt_form | step | follows | A | One step from art. 266o. The title also names the notice period and the deadline, and those are grounded by the documents' own rules (arts. 266a, 273). | none |
| lt_family | step | states | C | The passage states the service duty but not the family-home condition under which the step is reached. That condition comes from the heading, so the basis is `follows`, as it is for the fact. | basis: follows; inference as for family_residence. |
| lt_arrears | step | follows | A | One step from art. 257d para. 1. | none |
| lt_good_faith | step | follows | A | Art. 271 para. 1 applies to every notice, so the step is always reached. | none |
| lt_extension | step | follows | C | Art. 273 para. 5 (cited article) obliges the authority to examine an extension ex officio when it rejects a tenant's challenge. An extension can therefore be assessed without a request, and the step is narrower than the article. The inference also rests on two passages (arts. 272 para. 1 and 272a para. 1 let. a), not one. | Inference to name art. 273 para. 5. Either reach the step when notice_received true and arrears_termination false, with hardship_evidence mandatory only if extension_requested, or record the narrowing explicitly in `not_this` of extension_requested. |
| lease_contract (lt) | document | evidence | A | Art. 266a para. 1: the lease records the duration and any agreed periods and dates. Statutory and local-custom periods are not in it, but it is still the ordinary proof. | none |
| termination_notice (lt) | document | evidence | C | The title "…or written threat of termination" is carried over from the rent type. In this type a threat is expressly not a notice (`not_this` of notice_received), and a model may accept a threat letter as the notice. | Title: "Landlord's notice of termination". must_show add: "in writing and signed". |
| proof_of_receipt (lt) | document | evidence | A | Art. 273 para. 1 runs from receipt. The tracking, envelope or acknowledgement is the ordinary proof. | none |
| spouse_service | document | evidence | C | The condition is separate service on the spouse. Where the claim is precisely that the spouse was not served, no "copy served separately" exists, so a mandatory request for it cannot be met. The finding is its absence. | Title: "Proof of separate service on the spouse or registered partner (the spouse's own copy with envelope or tracking), or the spouse's statement that no separate copy was received". |
| payment_demand | document | evidence | A | Art. 257d para. 1 (German "schriftlich", rightly flagged). The letter shows the time limit, its length and the warning. | none |
| prior_claims_correspondence | document | evidence | A | The tenant's dated letters show which claims were asserted and when. Claims raised in conciliation would be shown by the conciliation file, which "correspondence" may not cover. | (optional) title "…or conciliation records" |
| hardship_evidence | document | evidence | A | Art. 272 para. 2 let. c names exactly these circumstances. | none |
| stop (notice_received false) | stop | follows | C | It is sound where the claim states that no notice was given; the out-of-scope fixed-term case is honestly flagged. It is not sound where only receipt is disputed (see notice_received). | Inference: "…where the claim states that the landlord gave no notice of termination there is nothing to challenge and the process ends; a notice whose receipt is disputed is open." |

### Type 3: rent_increase_dispute

| rule id | kind | basis | verdict | reason | proposed wording |
|---|---|---|---|---|---|
| increase_notified | fact (defining) | follows | C | Take a file where "the landlord simply began invoicing a higher rent, with no notice at all". It may be answered "no" and stopped, yet that increase is void under art. 269d para. 2 let. a (cited in this type), and it is the tenant's rent-increase dispute. | Q: "Does the claim state that the landlord has communicated, demanded or charged a higher rent for the dwelling, by a notice or otherwise (whether or not on an official form)?" |
| graduated_rent | fact | follows | A | Art. 270d bars a challenge to graduated rents; polarity is right (the landlord raises it). Limit: art. 270d covers only a valid art. 269c agreement, and if ri_graduated finds the agreement invalid, no path leads back to the unfairness documents. | none (limit noted) |
| index_clause | fact | follows | A | Art. 270c restricts the argument to the change in the index. The same limit applies as for graduated_rent (an invalid clause under art. 269b). | none |
| cost_or_services_reason | fact | follows | C | `always_stated` is sound: costs and local-rent reasons are both ordinary, and art. 269d para. 1 requires reasons. But "decides whether it is unfair" overstates art. 269a, which says "in particular … not generally unfair" (in der Regel); unfairness itself is defined in art. 269, which is not cited. The workflow fact does not carry the `always_stated` marker (format limit), only the generic note. | Inference: "…whether the increase is justified by them bears on whether it is unfair (art. 269a let. b: 'in general' not unfair)." |
| termination_threat | fact | states | A | Art. 269d para. 2 let. c; the German "mit der Mitteilung … androht oder ausspricht" matches. | none |
| ri_form | step | follows | C | Art. 269d para. 5 (cited article) says that for a graduated increase under art. 269c, written form suffices. Checking every increase for the cantonal form flags a lawful graduated step as void. | Inference add: "except a graduated-rent step, for which written form suffices (art. 269d para. 5)". |
| ri_graduated | step | states | A | Art. 269c states the three validity conditions. | none |
| ri_index | step | states | A | Art. 269b states the validity conditions. | none |
| ri_reason | step | follows | A | One step from arts. 270b para. 1, 270c and 270d. | none |
| ri_threat | step | states | A | Art. 269d para. 2 let. c. | none |
| lease_contract (ri) | document | evidence | A | Art. 269d para. 1: the lease records the termination dates and any clause. | none |
| rent_increase_notice | document | evidence | C | Art. 269d para. 2 let. a–b is right, but must_show tests the cantonal form for every increase (see ri_form, para. 5). | must_show: "whether the form approved by the canton is used (for a graduated-rent step, whether it is in writing: art. 269d para. 5)". |
| proof_of_receipt (ri) | document | evidence | C | Art. 269d para. 1 says "give notice … at least ten days before"; it does not say "reach". The receipt rule is in art. 270b para. 1 ("Within 30 days of receiving notice"). | Locator: Art. 270b para. 1 as the primary passage; the art. 269d para. 1 inference becomes "shows when the notice was given". |
| cost_breakdown | document | evidence | C | A breakdown is the landlord's own assertion. What ordinarily proves cost increases or added services is the underlying record (mortgage interest notices, invoices for the works, operating-cost statements). | Title: "Landlord's breakdown of the cost increases or additional services, with the supporting invoices, interest notices or cost statements". |
| termination_notice (ri) | document | evidence | A | Art. 269d para. 2 let. c: the letter shows whether the threat accompanied the increase. | none |
| stop (increase_notified false) | stop | follows | C | On art. 270b alone it is a valid step: there is no challenge without a communicated increase. But art. 269d para. 2 (cited in this type) makes an increase not communicated on the form void, so a file about an uncommunicated increase that is still charged must not end. Sound only after the fact is widened. | Inference: "…where the claim states that the landlord has neither communicated nor demanded nor charged a higher rent, there is nothing to check and the process ends." |

## 2. Translation spot-check (German decides)

Twenty passages were compared: 256(1), 257d(1), 257d(2), 259a(1), 259d, 259g(1), 259h(1), 266a(1), 266l(1)-(2), 266n, 269a let. b, 269d(1), 269d(2), 270b(1), 270c, 270d, 271a(1)a, 272(1), 272a(1)a, 273(1).

- Already flagged by the writer and handled correctly: art. 257d para. 1, where "schriftlich" is missing in the English (payment_demand inference); and art. 259a para. 1, where "gestört" is wider than "prevented" (defect_present follows the German).
- Minor, not rule-changing: art. 257d para. 1 omits "fälliger" (due); art. 269d para. 1 has "next termination date" for "nächstmöglichen Kündigungstermin"; art. 259d has "unfit or less fit" for "beeinträchtigt oder vermindert". None changes a condition in this set.
- No other drift found that changes a rule.

## 3. Polarity (6b)

- landlord_not_informed: the polarity is right; the landlord raises a failure to notify. Art. 257g para. 2 is the better locator for that, because it attaches the consequence. But the fact tests the wrong condition: notification instead of the landlord's awareness (arts. 259b, 259d). See the table.
- cost_or_services_reason: `always_stated` is justified, because two ordinary alternatives (costs or services; local or market rents) both occur. It correctly has no presumption.
- arrears_termination: correct. True is the landlord's ground that excludes an extension.
- family_residence: correct polarity. The heading-based limitation is sound: the marginal heading is part of the stored text, and art. 266m para. 1 confirms it. Without it the rule would be broader. The writer should quote the heading verbatim and name art. 266m para. 1 so that a non-jurist can follow it.

## 4. Completeness within the cited articles (most important first)

1. Art. 273 para. 5: an extension is examined ex officio when a challenge fails. Hardship documents can be needed without an extension request (lt_extension).
2. Art. 269d para. 5: for a graduated increase, written form suffices. The form check and the must_show are wrong for that branch.
3. Art. 259h para. 1: after a deposit, the tenant must bring claims before the conciliation authority within 30 days, or the landlord receives the rent. The tenant's application to the conciliation authority (or proof that one was filed) is not requested.
4. Art. 271 para. 2: the landlord must state reasons on request. The landlord's statement of reasons is the document that settles asserted_claims and arrears_termination, and it is not requested.
5. Art. 271a para. 2: the article itself names "documents showing that he reached a settlement with the landlord" (written proof of an out-of-court settlement, which triggers the three-year protection). This is not modelled; at minimum it is a document candidate under lt_good_faith.
6. Art. 257d para. 2: termination requires non-payment within the time limit. Proof of payment or non-payment (the tenant's bank or payment records) is not requested; the payment demand alone does not show it.
7. Art. 270c: under an index clause, the only arguable point is the index change. The step ri_index requests no document showing the index values used (old and new consumer price index).
8. Art. 272a para. 2 (and para. 1 let. b–d): an extension is generally excluded where the landlord offers equivalent premises. The landlord's offer letter is not modelled.
9. Arts. 269b/269c with 270c/270d: if the clause is invalid (lease under 5 or 3 years), the increase becomes challengeable as unfair, but the workflow never routes back to ri_reason or cost_breakdown.
10. Art. 266n: the payment time limit (art. 257d) must also be served separately on the spouse. This is covered in spouse_service must_show; it is listed only to confirm it is not a gap.

## 5. Prose (`rule_text.md`) against `rules.json`

- Every question, `not_this`, step title, document title, must_show item, condition and stop in `rules.json` appears verbatim in the prose. The convention appears verbatim, labelled "not law".
- Omitted: the inferences of the facts, including the German-drift notes and the heading reasoning for family_residence. They are not operative, because the questions already follow the German. The prose never says that documents are mandatory (all are), only "Request"; that is equivalent here.
- Added: lines 7–9 (four answer values; "a step or document whose condition depends on an unresolved or open answer waits for that answer"; "the process ends and no document is requested"). These are workflow semantics, not rules from the text, but they match the convention and the stops.
- Wording that could mislead a model:
  - The termination type's document "Landlord's notice of termination or written threat of termination" invites accepting a threat as a notice.
  - The `not_this` lines cite arts. 259, 257e, 266 and 270, which are not in the snapshot, so a reader with the snapshot cannot check them.
  - The dh_notice inference ("unless the claim states that the landlord has not been informed…") presents the intake convention as a legal inference.

## 6. Counts

| kind | agree | agree with change | disagree | total |
|---|---|---|---|---|
| fact | 9 | 5 | 1 | 15 |
| step | 10 | 4 | 0 | 14 |
| document (type rows) | 12 | 6 | 0 | 18 |
| stop | 1 | 2 | 0 | 3 |
| convention | 1 | 0 | 0 | 1 |
| **total** | **33** | **17** | **1** | **51** |

Presumptions: none in `rules.json` (correct: no passage supports one), so there are no presumption rows. The workflow's convention presumptions were checked under item 6.

## 7. The five findings that matter most

1. **The landlord's knowledge is tested as the tenant's notice** (landlord_not_informed: D; dh_notice and defect_notification: C). Arts. 259b and 259d turn on the landlord being aware. Where the landlord learned otherwise, the step is skipped. Where the notice was oral, the mandatory "tenant's notice" cannot be produced.
2. **Two of the three denied-event stops reach files the passage does not exclude.**
   - Rent: an increase charged without any notice is answered "not communicated" and stopped, though it is void under art. 269d para. 2 and is the dispute.
   - Termination: disputed receipt ("never reached me") is answered "no" and stopped instead of being open.
   - The defect stop is sound once a conceded shared cause is treated as open.
3. **Art. 273 para. 5 is ignored.** An extension is examined ex officio when a challenge fails, so lt_extension, gated only on a tenant request, is narrower than the cited article.
4. **Art. 269d para. 5 is ignored.** A graduated-rent step needs only written form, yet ri_form and rent_increase_notice test the cantonal form for every increase.
5. **Documents the cited articles plainly call for are missing**:
   - after a deposit, the conciliation filing (art. 259h para. 1);
   - the landlord's stated reasons for the notice (art. 271 para. 2);
   - written settlement documents (art. 271a para. 2);
   - proof of payment or non-payment within the time limit (art. 257d para. 2).

   In addition, cost_breakdown asks for the landlord's assertion rather than the documents that prove it.

## 8. Can a reader with the statute open verify this set without legal training?

Mostly yes. Every passage is verbatim and correctly located, so the `states` rules and the mechanical checks can be verified by anyone, and most `evidence` rules need only common sense about what a document shows. A lay reader could not verify these points:

- The family-home limitation of art. 266n. It needs the knowledge that a marginal heading is part of the enacted text, plus art. 266m, which is not snapshotted.
- The `follows` inferences that quietly combine two articles: landlord_not_informed with art. 259d, lt_extension with arts. 272 and 272a, ri_reason with arts. 270c and 270d.
- Whether "receipt" of a notice can be deemed (the disputed-receipt stop).
- The `not_this` references to articles outside the snapshot (259, 257e, 266, 270).
- The weight of "in der Regel / in particular" in art. 269a.
- Completeness, because it requires reading each cited article in full against the workflow, which the rule set does not invite. The German-drift checks also require reading German.

---

## Second look (2026-11-12)

Read: `RECONCILIATION.md`, the rebuilt `rules.json`, `rule_text.md`, the snapshots (now with art. 266m), and `workflow/*.json`. `RULES.md` was not read line by line; it is generated from the same data.

What ran:

- `python3 -I -B tools/check.py`: exit 0, "all checks passed". It reports 52 rules: convention 1, evidence 18, follows 24, states 9.
- New snapshot hashes equal SOURCES.json. Art. 266m in both snapshots matches the stored raw XML (EN and DE).
- The scratch verbatim/locator script now also covers the `also` passages: 124 of 124 passages are found in the named article, paragraph and letter, each at most 60 words.
- The string comparison of `rules.json` with `rule_text.md` finds no difference. Every question, `not_this`, title, must_show, step, document and stop inference appears verbatim, and the convention appears verbatim.
- The workflow presumptions are on branch facts only:
  - landlord_unaware, notice_oral_only, damages_claimed, deposit_intended, rent_deposited;
  - family_residence, arrears_termination, asserted_claims, extension_requested;
  - graduated_rent, index_clause, termination_with_increase.

  None is on a defining event, a stop-on-false fact or cost_or_services_reason, which now carries `always_stated: true` in the workflow.

### 1. The 18 earlier points

| # | rule (earlier verdict) | status | note |
|---|---|---|---|
| 1 | defect_present (C) | resolved | Uses "alone" and "at his own expense". A shared or disputed cause is open. The art. 259 import is gone. |
| 2 | landlord_not_informed (D), now landlord_unaware | resolved | The fact asks about knowledge, not notification. Locator art. 257g para. 2, with art. 259b as `also`. |
| 3 | dh_notice (C) | resolved | Reached on landlord_unaware = no. The inference no longer restates the convention. |
| 4 | defect_notification (C), now knowledge_proof | resolved | Other proofs are admitted. Art. 259b is the locator, with art. 259d as `also`. The oral-only case is handled by notice_oral_only. |
| 5 | notice_received (C) | resolved | Disputed receipt is open, not no. |
| 6 | family_residence (C) | resolved | Stronger than proposed: the condition now has its own verbatim passage (art. 266m para. 1). |
| 7 | lt_family (C) | resolved | Basis `follows`; art. 266m para. 1 as `also`. |
| 8 | lt_extension (C) | resolved | Reached without a request; art. 273 para. 5 as `also`. One inference sentence in hardship_evidence still overreaches (see the list at the end). |
| 9 | termination_notice, termination type (C) | resolved | The threat is gone from the title and "given in writing" is added. On "signed", see part 3. |
| 10 | spouse_service (C) | resolved | Title admits the spouse's statement of non-receipt. |
| 11 | stop, termination (C) | resolved | Stops only where no notice was given at all. |
| 12 | increase_notified (C), now increase_applied | resolved | Covers an increase announced, demanded or charged. |
| 13 | cost_or_services_reason (C) | resolved | "bears on … 'in general'"; the workflow marker is present. |
| 14 | ri_form (C) | resolved | The art. 269d para. 5 exception is in the inference and as `also`. |
| 15 | rent_increase_notice (C) | resolved | The para. 5 exception is in must_show. |
| 16 | proof_of_receipt, rent type (C) | resolved | Locator art. 270b para. 1. |
| 17 | cost_breakdown (C) | resolved | Supporting invoices and statements are now required. |
| 18 | stop, rent type (C) | resolved | Narrowed to "neither announced nor demanded nor charged". Optional: add art. 269d para. 2 let. a as `also`, since the inference now invokes "the voidness rules" without citing them. Not blocking. |

Resolved 18, not resolved 0.

### 2. Rules not seen before (nine tests)

| rule id | kind | basis | verdict | reason | proposed wording |
|---|---|---|---|---|---|
| landlord_unaware | fact | follows | A | Test 3: in a file where the caretaker saw the mould and the tenant never wrote, the answer is no, as it should be. Polarity: true is what the landlord raises, and para. 2 attaches the consequence, so it is right. The inference uses two passages, and both are declared (`also` art. 259b). | none |
| knowledge_proof | document | evidence | A | Arts. 259b and 259d make the landlord's awareness the condition. The document now admits every ordinary proof of that awareness. | none |
| notice_oral_only | fact | follows | A | Art. 257g para. 1 ("must inform", "melden") prescribes no form. Within the same snapshot, arts. 259g para. 1, 266l para. 1 and 257d para. 1 (DE) say "in writing" or "schriftlich" where the law wants it, so reading 257g as form-free is one valid step. Polarity: an oral-only notice is the exception the tenant raises to excuse a missing record, and a written trace is the ordinary case. "Unmentioned means requested" is therefore right: the need is created by art. 259b (landlord aware), and this fact only removes it. Two limits are noted, not blocking: (a) the question also counts an inspection record, which the tenant often cannot know about, so a "yes" needs the claim to say plainly that nothing was put in writing; (b) a stated deposit (art. 259g) implies a written time limit, which is itself a written trace, so the two facts can contradict each other. | none |
| increase_applied | fact (defining) | follows | A | Art. 269d para. 2 let. a voids an increase not communicated on the form, so an increase charged without notice is still the dispute. One step. Test 3: a landlord's private plan that was never announced is "no"; an increase invoiced without notice is "yes". | none |
| termination_with_increase | fact | follows | A | It is narrower than art. 269d para. 2 let. c (notice only, no threat), which SPEC item 4 allows. A threat is still caught by rent_increase_notice must_show ("any threat of termination in it or in the covering letter"). Basis `follows` is correct. Polarity: true is what the tenant raises. | none |
| deposit_receipt (merged with the conciliation filing) | document | evidence | A | Art. 259h para. 1 alone covers every must_show item: the due date of the first deposited rent, and claims "before the conciliation authority within 30 days". One passage is enough. | none |
| claims_and_reasons (merged) | document | evidence | A | The tenant's claims and the conciliation or court documents rest on art. 271a para. 1 let. a. The landlord's reasons need art. 271 para. 2, which is carried as `also`, so a second passage is needed and is present. Note: the landlord's reasons are requested only when asserted_claims is yes; that is narrower than art. 271 para. 2 and allowed. | none |
| payment_demand (merged with proof of payment) | document | evidence | C | The locator moved to art. 257d para. 2. That paragraph covers "payments made within the time limit", but must_show also asks for "time limit set and date it was received" and "warning that the lease will be terminated". Those conditions (and the 30-day minimum and "schriftlich") are in para. 1, which now sits only on the step, so the document no longer rests on a passage covering everything it must show. | Add `also`: Art. 257d para. 1 ("the landlord or lessor may set a time limit for payment and notify him that in the event of non-payment the landlord or lessor will terminate the lease on expiry of that time limit. The minimum time limit is ten days, and 30 days for leases of residential or commercial premises." / DE with "schriftlich"). |
| family_residence on art. 266m para. 1 | fact | follows | A | The condition now has a verbatim passage. The passage belongs to art. 266m (notice by the tenant); carrying it over to art. 266n rests on the shared heading "Family residence", which stands in both snapshots above both articles. That step is valid, and a lay reader can now see it. Para. 3 (registered partners) is correctly added. | none |
| stop, termination (narrowed) | stop | follows | A | It stops only where the claim says no notice was given at all; disputed receipt is open. This is sound on art. 273 para. 1. | none |
| stop, defect (narrowed) | stop | follows | A | "Alone" and "at his own expense" track art. 259a para. 1. A shared or disputed cause is open. Sound. | none |
| hardship_evidence (rewritten inference) | document | evidence | C | The added sentence "an ex officio examination (art. 273 para. 5) does not by itself call for them" is not in the cited text. Art. 273 para. 5 says only that the authority examines an extension; whether that examination needs these documents is a design choice of this rule set, and the sentence presents it as law. | "They are requested where the tenant seeks an extension; this rule set does not request them for an ex officio examination under art. 273 para. 5 alone (a choice of this rule set, not of the text)." |

### 3. The five points the writer did not accept

1. **"signed" on the notice of termination.** I agree to leave it out. Art. 266l para. 1 says only "in writing"; a signature requirement would come from general rules on written form that the set does not cite. The set says nothing wrong without it.
2. **Settlement documents (art. 271a para. 2).** I agree. The paragraph serves only let. e (three-year protection), which is not modelled, and nothing in the set denies it. The conciliation or court documents now in claims_and_reasons partly cover it anyway.
3. **Index values (art. 270c).** I agree to leave out a separate document; the set says nothing wrong, because index_clause states only that cost documents are not needed. Non-blocking suggestion at no slot cost: add "the index values used (old and new)" to rent_increase_notice must_show.
4. **The landlord's offer of equivalent premises (art. 272a para. 2).** I agree. It is "as a general rule", a landlord's defence, and nothing in the set contradicts it. Note: the reason given in RECONCILIATION.md speaks of "what the insurer requests", which is a slip (this regime has no insurer); it is not in the rule set.
5. **Routing back when a graduated or index clause is invalid.** I agree to leave it out as a known limit. The graduated_rent inference ("A periodical increase agreed under art. 269c cannot be challenged") is correct only for a valid agreement, and the question does not test validity, so for an invalid clause the set under-requests. Non-blocking: the inference should say "a valid agreement under art. 269c (checked at ri_graduated); if it is invalid, this rule set does not route back to the unfairness documents."

### 4. Still not agreed

- **payment_demand.** It needs art. 257d para. 1 as an `also` passage: the time limit, warning and writing it must show are not in para. 2.
- **hardship_evidence (inference).** "An ex officio examination … does not by itself call for them" states a design choice as if it were law; reword as proposed above.

Neither change alters the workflow, the documents or any condition. The set is ready to be marked reviewed once these two wording changes are made and `check.py` passes again.
