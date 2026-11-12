# Diagnosis of the clean-arm errors (Study 4, step 2d follow-up)

**DEVELOPMENT material, post hoc, not a result.** Stored clean-arm runs on gpt-6-luna (one run per file) at the tested commit; no model call was made for this diagnosis. Written by `lint/diagnose.py` from the stored records and cached reading responses, the files' designs and references, the rule sets the runs read (`rules/<regime>/rev0/`) and the product's own evaluator; the judgments that need a reading of the text are in `lint/diagnosis_review.json`.

## Attribution rule

```
(one cause per error; an error is a (file, document, kind) of lint/analyse.py's part (d) scoring):

1. Routing. The run was handed over unrouted (deferred) or routed to another type: every error of the file is a routing
   error, split by whether the file's defining event is stated false (denied-event file).
2-4. The file was routed to its type. Three replays through the product's evaluator (workflows.evaluate with checked=True,
   the inputs built as the product builds them: accepted established facts plus applicable presumptions; findings =
   documents present or unusable with an accepted verdict):
   D  = designed fact states + designed attachment states (exactly as generator/reference.py builds the reference);
   PD = the product's fact states + designed attachment states;
   DP = designed fact states + the product's document findings;
   PP = the product's facts and findings (must reproduce the stored plan; checked).
   If D already differs from reference.json for the document: cause 4 (workflow differs from reference).
   Else if PD shows the error and DP does not: cause 2 (fact reading). Else if DP shows the error and PD does not:
   cause 3 (document judgment). If both show it: each alone suffices; counted under cause 2 and flagged "also document".
   If neither shows it but PP does: the two together; counted under cause 2 and flagged "joint".
   The fact named for cause 2 is the fact whose correction alone (product state replaced by the designed state, all other
   product states kept, designed attachments) removes the error; where several do, the first in workflow order is named
   and the others listed; where none alone does, "several facts jointly".
   What the product did with the fact, from its recorded state and the three stored reading responses:
   - admitted the wrong value: established (all readings agreed, quotations located) a value other than the designed one;
   - readings disagreed and it held although the file states the fact: designed stated, product unresolved, and at least
     one reading gave the designed value or answered open (sub-pattern: the three verdicts);
   - read a stated fact as not stated: designed stated, and no reading gave a value or answered open (a presumption,
     where the fact has one, then filled the other value);
   - read an open fact as settled: designed open, product established a value or a presumption filled it;
   - read an unmentioned fact as open: designed not mentioned, product unresolved (a reading gave a value or answered
     open, so no presumption filled it).
5. Scoring convention: a need outside the type's catalogue (a process-builder addition) or an optional document. (On
   these runs the process builder added nothing and no optional document produced an error; the class is kept for the
   rule's completeness and for the revised re-run.)
6. Text and recorded state plausibly disagree: a cause-2 error is moved here when (a) the file was kept as read and the
   blind check changed this fact's state (design.json facts_designed) and the product's reading matches the original
   design, or (b) diagnosis_review.json records, after reading the file text, that the passage the readings quoted
   plausibly states what the product read (the judgment and its reason are listed).
```

Replay checks: tenancy: replay_reproduces_stored_plan 53, designed_replay_equals_reference 314; theft: replay_reproduces_stored_plan 40, designed_replay_equals_reference 304; dismissal: replay_reproduces_stored_plan 46, designed_replay_equals_reference 336. The product's evaluator, fed the stored facts and findings, reproduces every stored plan of the 139 correctly routed files, and fed the designed states it reproduces every reference document state: no error is of cause 4.

## Errors by regime, cause and kind

UR = request that should not be made, MR = request missed, UH = hold where the file settles the fact, MH = hold missed.

| Regime | Cause | UR | MR | UH | MH | Errors |
|---|---|---|---|---|---|---|
| tenancy | routing failure, other file | 0 | 4 | 0 | 0 | 4 |
| tenancy | fact reading | 0 | 0 | 7 | 0 | 7 |
| tenancy | supplied-document judgment | 9 | 0 | 0 | 0 | 9 |
| tenancy | text and recorded state plausibly disagree | 0 | 1 | 0 | 0 | 1 |
| theft | routing failure, denied-event file | 8 | 0 | 16 | 0 | 24 |
| theft | routing failure, other file | 0 | 18 | 0 | 6 | 24 |
| theft | fact reading | 0 | 0 | 5 | 0 | 5 |
| theft | supplied-document judgment | 5 | 0 | 0 | 0 | 5 |
| theft | text and recorded state plausibly disagree | 4 | 0 | 5 | 0 | 9 |
| dismissal | routing failure, denied-event file | 2 | 0 | 3 | 0 | 5 |
| dismissal | routing failure, other file | 0 | 4 | 6 | 0 | 10 |
| dismissal | fact reading | 0 | 1 | 18 | 0 | 19 |
| dismissal | supplied-document judgment | 8 | 0 | 0 | 0 | 8 |
| dismissal | text and recorded state plausibly disagree | 0 | 4 | 0 | 0 | 4 |
| all_regimes | routing failure, denied-event file | 10 | 0 | 19 | 0 | 29 |
| all_regimes | routing failure, other file | 0 | 26 | 6 | 6 | 38 |
| all_regimes | fact reading | 0 | 1 | 30 | 0 | 31 |
| all_regimes | supplied-document judgment | 22 | 0 | 0 | 0 | 22 |
| all_regimes | text and recorded state plausibly disagree | 4 | 5 | 5 | 0 | 14 |

## Whose defect

Owner classes as stated in `diagnosis_review.json` (notes). Denominator: all clean-arm errors of the regime.

| Regime | Errors | rule wording | must_show wording | product | benchmark design | text vs recorded state | scoring convention |
|---|---|---|---|---|---|---|---|
| tenancy | 21 | 6 (29%) | 3 (14%) | 11 (52%) | 0 (0%) | 1 (5%) | 0 (0%) |
| theft | 67 | 22 (33%) | 3 (4%) | 4 (6%) | 29 (43%) | 9 (13%) | 0 (0%) |
| dismissal | 46 | 11 (24%) | 6 (13%) | 20 (43%) | 5 (11%) | 4 (9%) | 0 (0%) |
| all_regimes | 134 | 39 (29%) | 12 (9%) | 35 (26%) | 34 (25%) | 14 (10%) | 0 (0%) |

## The ten fact/document pairs with the most errors

Fact-reading errors (cause 2, and cause 6 where the fact is named). Quotations are from the stored reading responses.

1. **tenancy lease_termination_dispute.asserted_claims -> claims_and_reasons**: 2 errors in 2 file(s); kinds {'unwarranted_hold': 2}; designed {'stated_true': 2}; product: readings disagreed and it held although the file states the fact.
   - ten_00bf58d82a2b (designed stated_true), a reading answered open: "Ich bin ziemlich sicher, warurn mir die Hagenbuch Betriebs AG die Wohnung gekundigt hat: weil ich mich gewehrt habe."
   - ten_0c74f4037e13 (designed stated_true), a reading answered true: "I am convinced the real reason for the notice is my complaint from 15 January 2026."
2. **theft theft_at_home.household_perpetrator -> insurance_policy**: 2 errors in 2 file(s); kinds {'unwarranted_hold': 2}; designed {'not_mentioned': 1, 'stated_true': 1}; product: read an unmentioned fact as open, readings disagreed and it held although the file states the fact.
   - the_506c9909edc4 (designed not_mentioned), a reading answered open: "Täterschaft unbekannt."
   - the_656f9aad39e5 (designed stated_true), a reading answered true: "die seit dem Frühling 2025 bei mir zur Untermiete wohnte und mit mir die Wohnung teilte"
3. **theft theft_at_home.household_perpetrator -> notification_record**: 2 errors in 2 file(s); kinds {'unwarranted_hold': 2}; designed {'not_mentioned': 1, 'stated_true': 1}; product: read an unmentioned fact as open, readings disagreed and it held although the file states the fact.
   - the_506c9909edc4 (designed not_mentioned), a reading answered open: "Täterschaft unbekannt."
   - the_656f9aad39e5 (designed stated_true), a reading answered true: "die seit dem Frühling 2025 bei mir zur Untermiete wohnte und mit mir die Wohnung teilte"
4. **theft theft_at_home.household_perpetrator -> stolen_items_list**: 2 errors in 2 file(s); kinds {'unwarranted_hold': 2}; designed {'not_mentioned': 1, 'stated_true': 1}; product: read an unmentioned fact as open, readings disagreed and it held although the file states the fact.
   - the_506c9909edc4 (designed not_mentioned), a reading answered open: "Täterschaft unbekannt."
   - the_656f9aad39e5 (designed stated_true), a reading answered true: "die seit dem Frühling 2025 bei mir zur Untermiete wohnte und mit mir die Wohnung teilte"
5. **tenancy defect_mold_heating.defect_present -> damage_evidence**: 1 errors in 1 file(s); kinds {'unwarranted_hold': 1}; designed {'stated_true': 1}; product: readings disagreed and it held although the file states the fact.
   - ten_270f84d8acff (designed stated_true), a reading answered true: "Die Wand ist bis heute bis auf Kniehöhe nass, der Verputz brockelt, und es riecht modrig."
6. **tenancy defect_mold_heating.defect_present -> defect_record**: 1 errors in 1 file(s); kinds {'unwarranted_hold': 1}; designed {'stated_true': 1}; product: readings disagreed and it held although the file states the fact.
   - ten_270f84d8acff (designed stated_true), a reading answered true: "Die Wand ist bis heute bis auf Kniehöhe nass, der Verputz brockelt, und es riecht modrig."
7. **tenancy defect_mold_heating.defect_present -> knowledge_proof**: 1 errors in 1 file(s); kinds {'unwarranted_hold': 1}; designed {'stated_true': 1}; product: readings disagreed and it held although the file states the fact.
   - ten_270f84d8acff (designed stated_true), a reading answered true: "Die Wand ist bis heute bis auf Kniehöhe nass, der Verputz brockelt, und es riecht modrig."
8. **tenancy defect_mold_heating.defect_present -> lease_contract**: 1 errors in 1 file(s); kinds {'unwarranted_hold': 1}; designed {'stated_true': 1}; product: readings disagreed and it held although the file states the fact.
   - ten_270f84d8acff (designed stated_true), a reading answered true: "Die Wand ist bis heute bis auf Kniehöhe nass, der Verputz brockelt, und es riecht modrig."
9. **tenancy rent_increase_dispute.index_clause -> cost_breakdown**: 1 errors in 1 file(s); kinds {'unwarranted_hold': 1}; designed {'stated_true': 1}; product: readings disagreed and it held although the file states the fact.
   - ten_a743587360f3 (designed stated_true), a reading answered open: "Soweit ich das verstehe, kommt das von der Klausel in meinem Vertrag"
   - ten_a743587360f3 (designed stated_true), a reading answered true: "kommt das von der Klausel in meinem Vertrag, nach der sich die Miete am Landesindx der Konsumentenpreise ausrichtet."
10. **theft theft_at_home.burglary_or_robbery -> lock_change_invoice**: 1 errors in 1 file(s); kinds {'unwarranted_hold': 1}; designed {'stated_false': 1}; product: readings disagreed and it held although the file states the fact.
   - the_2412f755f636 (designed stated_false), a reading answered false: "Aufgebrochen wurde nichts, der Dieb ist einfach hineingespaziert."

Patterns behind the fact-reading errors (every cause-2 error, and cause-6 errors that name a fact):

| Regime | Fact | What the readings did | Owner | Errors |
|---|---|---|---|---|
| theft | household_perpetrator | verdicts open 2, true 1 | text vs recorded state | 5 |
| tenancy | defect_present | every reading gave the designed value; 3 quotation(s) not found word for word (found in neither the uploaded nor the clean text: the reading altered the words (a corrected noisy character, a capital letter, joined words)) | product | 4 |
| dismissal | employer_gave_notice | every reading gave the designed value; 1 quotation(s) not found word for word (the reading altered the words (a capital letter at the start of a quoted part sentence, or other wording)) | product | 4 |
| theft | household_perpetrator | verdicts not_stated 1, open 2 | rule wording | 3 |
| dismissal | several facts | several facts jointly | product | 3 |
| dismissal | dismissed_immediately | every reading gave the designed value; 1 quotation(s) not found word for word (found in neither the uploaded nor the clean text: the reading altered the words (a corrected noisy character, a capital letter, joined words)) | product | 3 |
| dismissal | employer_gave_notice | every reading gave the designed value; 2 quotation(s) not found word for word (2 of them found in the clean text: the reading corrected the scan noise) | product | 2 |
| dismissal | notice_period_ended | every reading gave the designed value; 3 quotation(s) not found word for word (2 of them found in the clean text: the reading corrected the scan noise) | product | 2 |
| tenancy | asserted_claims | verdicts open 1, true 2 | rule wording | 1 |
| tenancy | asserted_claims | verdicts open 2, true 1 | rule wording | 1 |
| tenancy | index_clause | verdicts open 1, true 2 | product | 1 |
| theft | burglary_or_robbery | every reading gave the designed value; 1 quotation(s) not found word for word (found in neither the uploaded nor the clean text: the reading altered the words (a corrected noisy character, a capital letter, joined words)) | product | 1 |
| theft | theft_away | every reading gave the designed value; 1 quotation(s) not found word for word (the reading altered the words (a capital letter at the start of a quoted part sentence, or other wording)) | product | 1 |
| dismissal | reasons_requested | every reading gave the designed value; 1 quotation(s) not found word for word (1 of them found in the clean text: the reading corrected the scan noise) | product | 1 |
| dismissal | incapacity_illness_accident | verdicts not_stated 3 | product | 1 |
| dismissal | more_than_180_days | every reading gave the designed value; 1 quotation(s) not found word for word (the reading altered the words (a capital letter at the start of a quoted part sentence, or other wording)) | product | 1 |
| dismissal | retaliation_for_claims | verdicts open 1, true 2 | rule wording | 1 |
| dismissal | notice_before_protected_period | verdicts false 2, true 1 | product | 1 |

## Dismissal at share level 0

15 files, 24 errors (1.60 per file); by kind {'unneeded_request': 5, 'missed_request': 1, 'unwarranted_hold': 18}; by cause {'document_judgment': 3, 'text_state_disagree': 1, 'fact_reading': 12, 'routing_not_denied': 3, 'routing_denied': 5}; by owner {'product': 13, 'text vs recorded state': 1, 'must_show wording': 2, 'rule wording': 3, 'benchmark design': 5}.

| File | Errors | Kinds | Causes |
|---|---|---|---|
| dis_32d79153a27f | 5 | {'unwarranted_hold': 5} | fact_reading; fact_reading:employer_gave_notice (every reading gave the designed value; 1 quotation(s) not found word for word (the reading altered the words (a capital letter at the start of a quoted part sentence, or other wording))) |
| dis_ff1e9056d2c3 | 5 | {'unneeded_request': 2, 'unwarranted_hold': 3} | routing_denied |
| dis_408b774aa7db | 4 | {'unwarranted_hold': 3, 'unneeded_request': 1} | document_judgment; fact_reading; fact_reading:notice_period_ended (every reading gave the designed value; 3 quotation(s) not found word for word (2 of them found in the clean text: the reading corrected the scan noise)) |
| dis_b7f5c9e07c99 | 3 | {'unwarranted_hold': 3} | fact_reading:dismissed_immediately (every reading gave the designed value; 1 quotation(s) not found word for word (found in neither the uploaded nor the clean text: the reading altered the words (a corrected noisy character, a capital letter, joined words))) |
| dis_c50430dbdfa1 | 3 | {'unwarranted_hold': 3} | routing_not_denied |
| dis_07997bac9677 | 1 | {'unneeded_request': 1} | document_judgment |
| dis_0ddd28b452d1 | 1 | {'missed_request': 1} | text_state_disagree |
| dis_373612fa5345 | 1 | {'unneeded_request': 1} | document_judgment |
| dis_fcbd44dfcef3 | 1 | {'unwarranted_hold': 1} | fact_reading:notice_before_protected_period (verdicts false 2, true 1) |

Why dismissal is worst at share level 0 (no designed open fact): 24 errors in 15 files, 18 of them holds where the file settles the fact, and 16 of the 24 sit in four files. 11 holds come from three files in which every reading gave the designed value but one or more quotations were not found word for word in the uploaded text, so the product left the fact unresolved: dis_32d79153a27f (the defining event employer_gave_notice; one reading began its quotation with a capital 'We are terminating' where the letter has 'we are terminating'), dis_b7f5c9e07c99 (the defining event dismissed_immediately; one reading quoted 'mmediate' for the scan-noised 'irnmediate') and dis_408b774aa7db (notice_period_ended; two readings corrected the scan noise in 'läuft noc'). A held defining event holds every document of the type, which is why two files give 8 holds. 3 holds are the routing of dis_c50430dbdfa1 (rule wording), 3 holds and 2 requests are the denied-event file dis_ff1e9056d2c3 routed to wrongful_termination (benchmark design: its denial is an ordinary notice, the defining event of types 1 and 2), and 1 hold is a misreading (dis_fcbd44dfcef3, one reading of three took 'Ich war schon krank, als die Kündigung kam' as notice before the protected period). Level 0 is not harder by design; the excess is the concentration of these four files (with 15 files in the level, each error adds 0.07 errors per file).

## Theft: measures_pending

| File | Type | Product | Readings (verdict: quotation) |
|---|---|---|---|
| the_003fbcb4d365 | simple_theft_away | established True | true: Das hole ich in den nachsten Tagen nach; true: Das hole ich in den nachsten Tagen nach; true: Das hole ich in den nachsten Tagen nach, damit ihn wenigstns niemand problemlos weiterverkaufe kann. |
| the_1024620d6055 | simple_theft_away | established True | true: Das Handy über die IMEI-Nummer beim Anbieter sperren zu lassen.; true: Das Handy über die IMEI-Nummer beim Anbieter sperren zu lassen.; true: Eines muss ich noch erledigen und bin noch nicht dazu gekommen: Das Handy über die IMEI-Nummer beim Anbieter sperren zu lassen. |
| the_12e3d532c09d | simple_theft_away | presumed False | not_stated: ; false: register the frame number on one of the online stolen-bike lists and send the photo to the second-hand bike shops in town, in case it turns up.; false: in case it turns up. |
| the_12ee892d56f4 | simple_theft_away | not read (routed None) |  |
| the_27cd334c5026 | simple_theft_away | presumed False | not_stated: ; not_stated: ; not_stated:  |
| the_32a656cb56cf | simple_theft_away | not read (routed None) |  |
| the_57501c7d1230 | theft_at_home | unknown None | true: das ist für morgen Nachmittag abgemacht. Passiert ist das also noch nicht.; not_stated: ; true: Passiert ist das also noch nicht. |
| the_656f9aad39e5 | theft_at_home | established True | true: das habe ich noch nicht gemacht; true: das habe ich noch nicht gemacht; true: Die muss ich jetzt sperren lassen, das habe ich noch nicht gemacht |
| the_9355c558630a | simple_theft_away | not read (routed None) |  |
| the_9b58c5abd02f | theft_at_home | unknown None | not_stated: ; true: Das habe ich noch nicht gemacht, ich muss zuerst die Nummer heraussuchen.; true: Das habe ich noch nicht gemacht, ich muss zuerst die Nummer heraussuchen. |
| the_d76f5df60f83 | simple_theft_away | not read (routed None) |  |
| the_dd72ec4e53dd | simple_theft_away | not read (routed None) |  |
| the_e0b1e1d56fb2 | theft_at_home | unknown None | not_stated: ; true: Das habe ich noch nicht gemacht, kommt aber diese Woche.; true: Das habe ich noch nicht gemacht, kommt aber diese Woche. |
| the_fefc066e8269 | simple_theft_away | presumed False | not_stated: ; not_stated: ; not_stated:  |

measures_pending causes none of the 67 theft errors: no document hangs on the instruction step (h_instruction / a_instruction), and the product defers only on facts that change a document, so an unresolved measures_pending holds nothing. Its low admission where stated true (3 of 9 files the runs read: 2 of 5 simple_theft_away, 1 of 4 theft_at_home) comes from what the pending measures are. Admitted: blocking a phone by its IMEI, blocking a credit card, marking a laptop as stolen and locking it through its user account (all three stop the thief using the item). Not admitted: registering a bicycle's frame number on stolen-bike lists 'in case it turns up' (3 files: not stated or false, presumed false), reporting a camera's or laptop's serial number to the maker so that it is noticed at a repair (2 files: one reading of three not stated, held), going with the police to secure a bicycle found for sale (1 file: held). The question's not_this excludes 'steps to find the thief or recover the items', and the theft workflows append the not_this to the question the product reads; the writer and the blind check saw the question only (writer bundles and blind-check inputs carry no not_this), so the designs count recovery steps as measures to reduce the loss and the product, following our not_this, does not. The exclusion of steps to recover the items has no passage: VVG Art. 38a Abs. 1 asks the claimant to reduce the loss ('für Minderung des Schadens zu sorgen'), which getting stolen items back does. That is a defect of our wording (narrower than the passage), fixed in Part B; it changes no document and no reference.

## Routing failures

### tenancy: 3 non-denied, 3 denied-event

| File | Type | Routing answer | Quotation | Errors | Owner | Cause |
|---|---|---|---|---|---|---|
| ten_b4d4cb05336f | rent_increase_dispute | lease_termination_dispute | Was mich am meisten schockiert hat, steht im Begleitbrief: Herr Daniel Meier kündigt mir darin gleichzeitig die Wohnung an der Hauptstrasse 25 in Bern, auf Ende Juni 2026. | 0 | rule wording | Rent increase accompanied by a notice of termination in the covering letter. The rule set decides that case inside the rent-increase type (fact termination_with_increase, art. 269d para. 2 let. c); the routing question does not say so, and the router took the termination. |
| ten_c2a72cbf1698 | defect_mold_heating | None | (no quotation; value null) | 3 | rule wording | The routing question names the defect type as 'a defect of the dwelling (mould, damp, heating)'; the file's defect is noise and vibration from a bar in the building, a disturbance of the agreed use that the type's defining event covers (art. 259a para. 1, 'disturbed in using the dwelling as agreed'). The parenthesis reads as a closed list, so the router gave no value. |
| ten_e4858b3af131 | rent_increase_dispute | lease_termination_dispute | I'd like to know whether I can fight the termination, and whether I have to pay the higher rent while that's being sorted out. | 1 | rule wording | As ten_b4d4cb05336f: a graduated-rent step together with a notice of termination; the router took the termination ('whether I can fight the termination'). |

| File | Type | Product did | Errors | Empty plan right under the rule text? | Why |
|---|---|---|---|---|---|
| ten_429b182434cf | rent_increase_dispute | unrouted (no routing value) | 0 | yes | The file states the rent was never raised (wants a reduction of the initial rent). No type's defining event holds; the rule text gives no process, so an empty plan is right. |
| ten_776e0e61986b | defect_mold_heating | unrouted | 0 | yes | The file states there is no defect; the dispute is a refused sublet, which no type covers. Empty plan right. |
| ten_c1e4987669e8 | lease_termination_dispute | unrouted | 0 | yes | The file states no notice was given (only a phone remark about a possible sale). No type applies. Empty plan right. |

### theft: 11 non-denied, 8 denied-event

| File | Type | Routing answer | Quotation | Errors | Owner | Cause |
|---|---|---|---|---|---|---|
| the_0cd1b047049a | simple_theft_away | other | When we came back about five hours later the passenger window was smashed and the rucksack was gone. | 0 | rule wording | Theft from a car broken into away from home. The claim_type question's 'Not this' sends 'a burglary or robbery away from the insured location' to other, but the question does not carry the policy's own definition that breaking into a vehicle is not a burglary (Ziff. 23.3 lit. a, Ausschluss: 'Fahrzeuge sind keine Behältnisse'); the router read the smashed window as a burglary away and answered other. |
| the_12ee892d56f4 | simple_theft_away | other | war die Scheibe auf der Beifahrerseite eingeschlagen, die Tasche weg und die Skibox aufgedrückt und leer. | 4 | rule wording | As the_0cd1b047049a (car window smashed, ski box forced). |
| the_248aa95805a8 | theft_at_home | other | Das Schlimme ist, wer es war. Es war meine Mitbewohnerin Nicole Wyss. | 0 | rule wording | Theft at home by a flatmate. The rule set decides the household exclusion inside theft_at_home (fact household_perpetrator, stop h_stop_excluded); the claim_type question does not say that an exclusion does not move the claim out of its type, and the router answered other quoting 'Es war meine Mitbewohnerin'. |
| the_32a656cb56cf | simple_theft_away | None | (no quotation; value null) | 1 | benchmark design | The defining event is designed open: the file says the bicycle may have been taken at the station or from the shed at home. That is exactly the routing question (at home or away), so no routing answer can be given from the text; the router gave none. The reference assumes the type the design drew. Not a wording defect. |
| the_819379d12c03 | simple_theft_away | other | the rear side window was smashed in and the bag had gone. | 3 | rule wording | As the_0cd1b047049a (rear side window smashed; the file's own form says 'theft of household contents away from home (from a parked car)'). |
| the_9355c558630a | simple_theft_away | other | Am 24. Juni 2026 standen wir auf einem Campingplatz bei Locarno und sind am Nachmittag ins Städtchen gegangen. Das Wohnmobil war abgeschlossen. Als wir um sechs zurückkamen, war das Türschloss aufgebrochen und drinnen alles durchwühlt. | 3 | rule wording | As the_0cd1b047049a (camper van door lock broken open on a camp site). |
| the_c50e0bd7b054 | simple_theft_away | other | Ich hatte mein Auto am Nachmittag in einer Seitenstrasse beim Bahnhof abgestellt und abgeschlossen und war zwei Stunden an einer Sitzung. Als ich zurückkam, war die hintere Seitenscheibe eingeschlagen und meine Arbeitstasche vom Rücksitz verschwunden: Laptop, Tablet, Kamera und eine Lederjacke, zus… | 1 | rule wording | As the_0cd1b047049a (car window smashed; the file's form says 'Diebstahl auswärts (aus abgeschlossenem Personenwagen)'). |
| the_d37fc3c54b4b | simple_theft_away | other | Als ich zurückkam, war die Scheibe der Beifahrertür eingeschlagen und meine Tasche vom Beifahrersitz weg, mit dem Tablet, dem Kopfhörer und meiner Brille. | 3 | rule wording | As the_0cd1b047049a (passenger door window smashed). |
| the_d76f5df60f83 | simple_theft_away | other | On Saturday 5 September 2026 I was at the lake festival in Lucerne with my friend Peter Imhof. Around 11 at night, in the crowd near the fireworks, a man barged into me so hard that I fell over. | 4 | benchmark design | The defining event is designed open: the file says it cannot tell whether the man knocked the claimant down to rob her (robbery away: outside both types, 'other') or a pickpocket used a collision (simple theft away). That is the routing question itself; 'other' is one of the two readings the file leaves open. |
| the_d9579f891719 | simple_theft_away | other | I parked in a public car park near the zoo around ten and locked the car. | 4 | rule wording | As the_0cd1b047049a (car window smashed in a car park). |
| the_dd72ec4e53dd | simple_theft_away | other | Wir sassen am Mittag auf einer Restaurantterrasse am Rhein, die Handtasche hing an meiner Stuhllehne. Als ich zahlen wollte, war sie weg. | 1 | rule wording | A handbag taken from a chair on a restaurant terrace, and the file states that the supplementary cover for simple theft away was not taken. The question gives no definition of simple theft (pickpocketing and trick theft are simple thefts, Ziff. 23.3 lit. b, Ausschluss) and does not say that a missing cover is decided inside the type (Ziff. 24 Einleitung, stop away_cover_missing); the router answered other. Which of the two gaps decided it cannot be told from the stored answer. |

| File | Type | Product did | Errors | Empty plan right under the rule text? | Why |
|---|---|---|---|---|---|
| the_1dfba8facf5e | theft_at_home | routed to simple_theft_away and planned it | 4 | no | Designed as theft_at_home with the event denied: the file says the theft happened on holiday, not at home. Under the rule text that is a simple theft away (type 2), so the product's routing is what the rules give; the reference's stop (nothing needed) is right only inside the drawn type. The 4 errors are scored against a reference the rule text does not give. |
| the_5ee356013cfc | simple_theft_away | routed to other | 0 | yes | A robbery away from home: outside both types by the rule text ('routing answers other'). Empty plan right. |
| the_6634ab23ee99 | theft_at_home | routed to simple_theft_away | 4 | no | As the_1dfba8facf5e: a camera bag stolen in Bern, not at home. |
| the_685edf55333b | theft_at_home | routed to simple_theft_away | 4 | no | As the_1dfba8facf5e: laptop stolen in Zürich at a work meeting. |
| the_86b4e22a87e7 | theft_at_home | routed to simple_theft_away | 4 | no | As the_1dfba8facf5e: items stolen while shopping in Konstanz. |
| the_86e739ec9184 | simple_theft_away | routed to theft_at_home | 4 | no | Designed as simple_theft_away with the event denied: the file says the items were stolen at home. Under the rule text that is type 1; the product's routing is what the rules give. |
| the_a529fff2269d | simple_theft_away | routed to theft_at_home | 4 | no | As the_86e739ec9184: a break-in at the claimant's flat. |
| the_c7620535798b | simple_theft_away | routed to other | 0 | yes | A robbery at knifepoint away from home: outside both types. Empty plan right. |

### dismissal: 4 non-denied, 8 denied-event

| File | Type | Routing answer | Quotation | Errors | Owner | Cause |
|---|---|---|---|---|---|---|
| dis_14b7db92a192 | protected_period_notice | None | (no quotation; value null) | 2 | rule wording | Ordinary notice; the dispute is the contractual notice period (notice_period_varied true), every protected-period fact is denied. The routing value is worded as an outcome ('notice during a protected period'), while the type's own conditions decide whether a protected period, the probation period or the notice period affect an ordinary notice. The router gave no value. The two notice types share their defining event (employer_gave_notice), which no wording can separate in a file that raises matters of both (see the planner note). |
| dis_1bf62841defb | protected_period_notice | None | (no quotation; value null) | 1 | rule wording | As dis_14b7db92a192 (dispute about the contractual two-month notice period; pregnancy denied). |
| dis_bf38c7dfb616 | protected_period_notice | wrongful_termination | handed me a letter saying my employment was being terminated. | 4 | rule wording | Ordinary notice with a written probation clause and a contractual notice period; no protected period raised. The router chose abusive notice, the only value naming an ordinary notice without a protected period. |
| dis_c50430dbdfa1 | protected_period_notice | wrongful_termination | Frau Meier hat mir am 12. Juli 2026 gekündigt, per SMS und am nächsten Tag noch mit einem kurzen Brief. Begründung: Es "passe einfach nicht". | 3 | rule wording | Notice by text message while the employee was ill and still in the probation period (type 1 stop). The router chose abusive notice, quoting the employer's reason ('passe einfach nicht'); the routing value does not say that illness or probation at the time of notice belongs to type 1. |

| File | Type | Product did | Errors | Empty plan right under the rule text? | Why |
|---|---|---|---|---|---|
| dis_05af0871cd70 | wrongful_termination | unrouted | 0 | yes | No notice given (hints, reduced hours). No type's defining event holds. Empty plan right. |
| dis_0f89215979d2 | protected_period_notice | unrouted | 0 | yes | No notice; a proposed termination agreement. No type applies. Empty plan right. |
| dis_4ee0866843c9 | protected_period_notice | unrouted | 0 | yes | No notice given. Empty plan right. |
| dis_5215d587db4b | wrongful_termination | unrouted | 0 | yes | No notice given (shift change). Empty plan right. |
| dis_827bbd04ddc9 | immediate_dismissal | unrouted | 0 | no | Designed as immediate_dismissal with the event denied by stating an ordinary notice with a notice period. An ordinary notice is the defining event of types 1 and 2 (employer_gave_notice), so the rule text gives one of those processes, not an empty plan. The product's empty plan matches the reference (0 errors) but not the rule text. |
| dis_930a1b5e1bdc | protected_period_notice | unrouted | 0 | yes | No notice given (pressure to change job). Empty plan right. |
| dis_fea630e08ab3 | protected_period_notice | unrouted | 0 | yes | No notice given. Empty plan right. |
| dis_ff1e9056d2c3 | immediate_dismissal | routed to wrongful_termination and planned it | 5 | no | As dis_827bbd04ddc9: the denial is an ordinary notice, which is the defining event of types 1 and 2; routing to wrongful_termination is one of the two readings the rule text allows. The 5 errors are scored against the immediate_dismissal stop. |

## Frontier partial run (tenancy, 39 files): routing failures and the failed run

| File | Type | Denied event | Routing | Answer | Errors |
|---|---|---|---|---|---|
| ten_429b182434cf | rent_increase_dispute | True | needs_facts | None | 0 |
| ten_580485dac025 | rent_increase_dispute | False | needs_facts | None | 3 |
| ten_5aecbb73131b | rent_increase_dispute |  | failed run: schema_mismatch: The model answer did not match its schema: $.facts: array length outside bounds (2 items; allowed 0 to 1) | - |  |
| ten_776e0e61986b | defect_mold_heating | True | needs_facts | None | 0 |
| ten_8572ddc89110 | rent_increase_dispute | True | needs_facts | None | 0 |
| ten_8c54d4a61b0a | rent_increase_dispute | True | needs_facts | None | 0 |

Frontier partial run (gpt-6.1-terra, clean, tenancy, the first 39 files in manifest order): 5 routing failures, all unrouted. Four are denied-event files (ten_429b182434cf, ten_776e0e61986b, ten_8572ddc89110, ten_8c54d4a61b0a): no type's defining event holds and the empty plan is what the rule text gives (0 errors each). One is ten_580485dac025, whose defining event increase_applied is designed open (the file leaves open whether a higher rent was announced or demanded), so the routing question has no answer in the text (benchmark design; the cost-efficient model routed it). The failed run, ten_5aecbb73131b, is a product failure: the routing answer gave two facts where its schema allows one, and the run stopped. The three tenancy files that the cost-efficient model routed wrongly for wording reasons (ten_c2a72cbf1698, ten_b4d4cb05336f, ten_e4858b3af131) are outside the 39 files run.

## Limits

- DEVELOPMENT, post hoc, not a result. One run per file on the cost-efficient model; 176 files (59 tenancy, 59 theft, 58 dismissal); small counts per cause.
- The cause attribution is mechanical (replays through the product's evaluator); the owner classification is partly a reading of the files by the same session that proposes the wording fixes (diagnosis_review.json). A second reader should check both.
- A hold or request can have two sufficient causes; such errors are counted once under fact reading and flagged ('also document', 'joint').
- The routing reading's own reasoning is not stored; for 'other' and null answers the cause is inferred from the question wording and the quotation the router gave.
- Reading verdicts come from the cached responses as lint/analyse.py parses them (a requote retry replaces the first answer).

