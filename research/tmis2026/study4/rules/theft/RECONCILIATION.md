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
