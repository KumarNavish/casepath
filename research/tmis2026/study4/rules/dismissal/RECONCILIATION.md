# Reconciliation: dismissal rule set, version 2026-11-12.3 → 2026-11-12.4

This file answers the second reader's `CITATION_CHECK.md` under SPEC.md step 2a item 7. It was written by the author of the rule set; `CITATION_CHECK.md` itself was not edited.

The coordinator's six decisions on the reader's main findings were applied. None of them conflicts with the cited text. Decision 5 offered two routes for the presumptions; the text does not support re-basing them, so they moved under the convention.

All changes are made in `tools/build.py`, which generates `rules.json`, `RULES.md`, `rule_text.md` and `workflow/*.json`. `tools/check.py` then passes in full (see the end of this file).

## Summary

- **Reader's verdicts:** 48 agree, 26 agree with change, 3 disagree.
- **The 29 non-agree items:**
  - 23 accepted as proposed;
  - 6 changed differently, in a way meant to meet the objection;
  - 0 not accepted.

## New source

- **Civil Procedure Code (SR 272), art. 62.** The reader asked for a cited passage on what makes a claim pending ("anhängig gemacht", CO art. 336b para. 2) before that point enters the rules.
  - Fetched from Fedlex as XML, English and German, consolidated version applicable from 2026-07-01.
  - Raw sha256: en `884fa4d0…415a`, de `fe97ce8d…01f5`.
  - Snapshots: `sources/cpc-sr272-en.txt` and `sources/cpc-sr272-de.txt`. Both are recorded in `SOURCES.json`.
  - Cited in `court_filing` and in the type 2 summary.

## One line per item

Kinds: F fact, S step, D document need, P presumption, X stop.

| # | Rule id (type) | Reader's point | What I did | Why |
|---|---|---|---|---|
| 1 | `employer_gave_notice` F (1) | "terminate" also reads on immediate dismissal; `not_this` does not exclude it | **Accepted.** not_this: "A resignation by the employee, a fixed-term relationship that ended by running out, or a dismissal with immediate effect (art. 337, a separate type)." | German "kündigen" is ordinary notice; immediate dismissal is type 3. |
| 2 | `notice_during_probation` F (1) | Passage states the converse, so basis should be `follows`; question ignores art. 335b(3) | **Accepted.** Basis `follows`, with the proposed inference plus one clause on 335b(3). Question now counts any extension under art. 335b(3). Art. 335b(3) is added as a second cited passage (`also`) with its German. | The bar is conditional on probation having expired; 335b(3) fixes when it expires. |
| 3 | `incapacity_illness_accident` F (1) | **Disagree:** broader than let. b, because the 30/90/180-day limit was dropped; timing comes from para. 2 | **Accepted** (single-fact form, coordinator decision 1). The question now carries the limit ("still within its protected length: up to 30 days in the first year of service, 90 days in the second to fifth years, 180 days from the sixth year"). The passage is now the whole of let. b, limit included, with its German. Locator is "let. b; para. 2", and para. 2's suspension clause is cited as `also`. The proof documents are the medical certificate (dates) and the employment contract (start date, which gives the year of service). | See the note below on why one fact and not three. |
| 4 | `compulsory_service` F (1) | Timing comes from para. 2; `not_this` could name let. d | **Accepted.** Locator "let. a; para. 2", para. 2 cited as `also`; not_this adds the overseas aid project (let. d, not covered). | Same as 3. |
| 5 | `pregnancy_or_birth` F (1) | Timing comes from para. 2 | **Accepted.** Locator "let. c; para. 2", para. 2 cited as `also`. | Same as 3. |
| 6 | `notice_before_protected_period` F (1) | `always_stated` is sound only where a protected period is raised | **Accepted.** The question opens "Where a protected period (…) is raised:"; not_this adds "Not asked where no protected period is raised." The workflow gate `a_gate_any_period` already routes past it when none is raised. | The fact has no referent without a protected period. |
| 7 | `a_notice` S (1) | Contract and probation documents arrive after the probation decision they serve | **Changed differently** (the reader's first option, taken further). Step `a_notice` is removed. `termination_letter`, `employment_contract` and `probation_terms` now sit at `a_probation`, the step that decides `notice_during_probation`, renamed "Record the notice, the start of employment and the probation terms, and check that the probation period had expired when notice was given". With the probation fact open, the product now **requests** the letter and the contract rather than holding them (checked: `GATE_DOCS` in check.py). | Coordinator decision 4: a document that settles a gate fact is needed at that gate. |
| 8 | `termination_letter` D (1) | No written form in the cited text; other records prove the same day | **Accepted.** Title "Notice of termination (letter, message or other record of the notice and its receipt)"; the inference says the text sets no written form. | — |
| 9 | `notice_period_terms` D (1) | **Disagree:** cites 336c(3), which does not create the written-variation condition; no German | **Accepted.** Now cites CO art. 335c para. 2 with its German; 336c(3) is kept as `also` (with its German) for the end-point. | 335c(2) creates the condition that the clause proves. |
| 10 | P `probation_varied`=no (1) | 335b(1) gives the default consequence, not "the file states none, therefore none exists" | **Changed differently.** The statutory presumption is removed and `probation_varied` falls under the intake convention (value no when unmentioned), declared as a convention, not law. The statutory default stays in the rules through `employment_contract`'s inference (335b(1)). | The text does not carry "not mentioned means none" (coordinator decision 5, second route). The reader's proposed inference would still have rested that step on the question's wording. |
| 11 | P `notice_period_varied`=no (1) | Same; also no German | **Changed differently,** as item 10. The German of 335c(1) is now quoted wherever 335c(1) is cited (type 2 `employment_contract`). | As item 10. |
| 12 | `a_stop_probation` X (1) | Sound only if the probation fact accounts for the 335b(3) extension | **Accepted.** Tied to the corrected fact (item 2); 335b(3) is cited as `also`, and the inference names the extension. | — |
| 13 | `employer_gave_notice` F (2) | 336b(2) names the party served, not the employer; `not_this` omits immediate dismissal | **Accepted.** Basis `follows`, inference: "in this employee-side regime that is the employee, so the notice is the employer's"; not_this as item 1. | — |
| 14 | `objection_submitted` F (2) | "Send" is weaker than "beim Kündigenden … Einsprache erheben"; para. 2 requires a valid objection | **Accepted.** Question: "Did the employee lodge a written objection to the notice with the employer (German: "beim Kündigenden schriftlich Einsprache erheben") no later than the end of the notice period?" not_this adds "an objection addressed to someone other than the employer". Validity is carried by the stop, which now cites para. 2's "gültig" (item 22). | The German decides. |
| 15 | `action_in_time` F (2) | Follows "brought before the courts" rather than "Klage anhängig gemacht"; pendency needs a cited passage | **Accepted.** Question: "Did the employee make the compensation claim pending (German: "Klage anhängig gemacht") within 180 days …?" CPC art. 62(1) is now fetched and cited ("A case becomes pending when an application for conciliation, an action … is filed"). It is used in `court_filing` and in the summary. | The reader's condition (a cited passage first) is met. |
| 16 | `retaliation_for_claims` F (2) | Asks what the employee *says*, unlike the other facts | **Accepted.** "Was the notice given because the employee had asserted, in good faith, claims arising from the employment relationship?" | Matches let. d. |
| 17 | `b_notice` S (2) | `written_objection` and `court_filing` sit after the gates that route on them | **Changed differently** (as proposed, plus a needed-when change). Step `b_notice` is removed. Letter, contract and `written_objection` sit at `b_objection_check`; `court_filing` sits at `b_limit_check`. `written_objection` is needed when an objection is said to exist **or the notice period has ended**; `court_filing` when the claim is said to be pending **or 180 days have passed**. So an open objection or filing fact produces a request for the document that settles it, not a hold (checked). | Coordinator decision 4. A need that depends only on the fact it proves would have held, not requested, under the product's exact deferral. |
| 18 | `b_representative` S (2) | German puts a burden of proof on the employer and a lower standard ("begründeter Anlass") | **Accepted.** Title "… (the employer must prove a justified reason, "begründeter Anlass")". Both languages are quoted, and the point is listed under "Where the translation was not followed". | — |
| 19 | `termination_letter` D (2) | Written form not required; `must_show` lacks the date of receipt | **Accepted.** Title as item 8; must_show adds "date the employee received it". | — |
| 20 | `employment_contract` D (2) | No German; 7-day probation notice not reflected | **Accepted.** German of 335c(1) added; must_show adds "probation clause, if any". | — |
| 21 | `court_filing` D (2) | On "anhängig gemacht" another filing (conciliation request) may prove pendency | **Accepted.** Title "Proof that the claim was made pending: the conciliation request or statement of claim, with the confirmation of receipt". Cites CPC art. 62 para. 1, with para. 2 (confirmation of receipt) and CO 336b(2) as `also`. must_show: authority, compensation claim, filing date, confirmation of receipt. | CPC art. 62 settles which filings make a case pending. |
| 22 | `b_stop_no_objection` X (2) | The consequence is in para. 2 s. 1's conditional, not in para. 1's duty | **Accepted.** Cites "Where the objection has been properly submitted and the parties cannot reach agreement on the continuation of the employment relationship, the party on whom notice was served may bring his claim for compensation." with the German ("Ist die Einsprache gültig erfolgt …"). The inference names "gültig". **Added from the same sentence** (coordinator decision 2): fact `agreed_to_continue`, step `b_continuation_check` and stop `b_stop_continued` (an agreement to continue ends the process). These three new rules need the reader's look. | — |
| 23 | `b_stop_time_limit` X (2) | Sound only on the German "verwirkt" | **Accepted.** Inference: "The German text, which is authoritative, says the claim is forfeited ("verwirkt") unless an action is made pending ("anhängig gemacht") within 180 days; forfeiture applies by itself, unlike the English "prescribes", so the process ends." Listed under "Where the translation was not followed". | — |
| 24 | `incapacity_cause` F (3) | **Disagree:** narrower than 337(3) ("unverschuldete Verhinderung"); `not_this` excludes covered cases | **Accepted.** The question uses the reader's wording ("prevented from working through no fault of their own (for instance illness, accident or a non-voluntary legal obligation)"); not_this: "A dismissal for conduct at work, or an absence the employee does not say was without their fault." | Coordinator decision 3. |
| 25 | `fixed_term` F (3) | No textual default between notice period and agreed term; the convention's "no" is unsupported | **Accepted.** `always_stated: true`, no presumption. | Coordinator decision 5. |
| 26 | `other_earnings` F (3) | Para. 2 also deducts savings and forgone earnings; `not_this` should say so | **Accepted.** not_this: "Unemployment benefits; savings resulting from the termination and work intentionally forgone (also deductible under para. 2, not covered here)." The type 3 summary says only earnings from other work are covered. | — |
| 27 | `employment_contract` D (3) | Probation clause missing from `must_show` (7-day notice) | **Accepted.** must_show adds "probation clause, if any". | — |
| 28 | `medical_certificate` D (3) | Once widened, other hindrances are proved by other papers | **Changed differently** (id). Title as proposed: "Proof of the hindrance from working (medical certificate, or official order or summons for a non-voluntary legal obligation)"; must_show "cause of the hindrance; first and last day; date issued". The catalogue id is renamed `medical_certificate` → `incapacity_proof`, shared with type 1 (title there "Medical certificate of incapacity for work"). | Keeps the catalogue at 14 documents instead of adding a 15th. |
| 29 | P `notice_period_varied`=no (3) | As item 11 | **Changed differently,** as items 10 and 11: moved under the convention. | As item 10. |

### Why item 3 uses one fact, not three

The coordinator offered two forms: split the limit into facts a file states, or keep one fact worded as "within the protected period" and add the documents a handler needs to check it. I chose one fact.

- **Code cannot do the arithmetic.** The workflow format allows only boolean and enum facts, and the product's condition language has no date or number arithmetic. Code could not combine "year of service" with "days of incapacity elapsed".
- **A split would break the size limit.** It needs at least three facts: incapacity at the time, a year-of-service band (two booleans or an enum the rule schema does not allow), and days elapsed. Type 1 would go from 8 to 11 facts, above SPEC's 10.
- **A model can answer the single fact.** A lay claim usually says how long the person had worked and how long they had been ill, and a model can read the three bands from the question.
- **The proof documents are already requested.** The medical certificate gives the dates and the contract gives the start date, so a handler can check the answer.

## Also changed (agreed items with notes, and cosmetic points)

- `a_suspension`: art. 336c para. 3 is added as `also`, as the reader suggested.
- Convention notes in the workflows:
  - the claim that statutory defaults take precedence is gone (there are none now);
  - empty lists are no longer printed;
  - each note names the facts left unresolved and the facts always stated.
- Every rule and every `also` passage now carries its German. `check.py` fails a rule without it, and the four rules that lacked German now have it.
- Decision 6: `RULES.md` and `rule_text.md` both have a section "Where the translation was not followed" listing four points:
  - verwirkt / anhängig gemacht (336b(2));
  - begründeter Anlass and the burden of proof (336(2)(b));
  - missbräuchlich (336(1));
  - "beim Kündigenden erheben" (336b(1)).

  The questions follow the German. RULES.md shows English and German for every passage.
- Type summaries in `rule_text.md`:
  - type 2 says an abusive notice stays effective, and that only let. d and para. 2 let. b are covered;
  - type 1 states the 30/90/180-day limit and the probation extension;
  - type 3 no longer suggests that savings are covered.

## Completeness points (reader's test 8)

Taken up:

- 1: valid objection and agreement to continue (item 22);
- 2: the art. 335b(3) extension (items 2 and 12);
- 3: the 30/90/180-day limit (item 3).

Not taken up, to keep the size limits; each is out of scope and named in the relevant `not_this` or summary where it touches a rule:

- 4: art. 336c let. cbis–cquinquies and d;
- 5: the other abuse grounds of art. 336;
- 6: the seven-day probation notice in types 2 and 3 (the probation clause is now in must_show);
- 7: protected periods inside type 2;
- 8: art. 335c(3);
- 9: art. 336(3);
- 10: art. 335c(2), second half.

## Items for the reader's second look

**No item is "not accepted".** The six items changed differently than proposed:

- **7 and 17 (document placement):** steps `a_notice` and `b_notice` are removed, the documents moved to the gate steps, and `written_objection` / `court_filing` are needed once the period has ended or the 180 days have passed.
- **10, 11 and 29:** the statutory presumptions are removed and the facts moved under the convention.
- **28:** the document id is renamed to `incapacity_proof`.

**New rules** the reader has not seen:

- fact `agreed_to_continue`;
- step `b_continuation_check`;
- stop `b_stop_continued`;
- the CPC art. 62 citations in `court_filing`.

**One inference to look at specifically:** `court_filing` links the CO's "anhängig gemacht" to the CPC's "Rechtshängigkeit" (art. 62 para. 1). The two acts use different words, and the link is an inference, not a quotation.

## Result

`python3 -I tools/check.py` ends with ALL CHECKS PASSED. It ran:

- every English and German passage (main and `also`) verbatim and inside its cited article, paragraph and letter, at most 60 words;
- every snapshot article cited;
- source hashes;
- all three workflows through the product's `validate_workflow`;
- the complete-assignment walk (2^8, 2^9 and 2^6 assignments);
- the one-open-fact hold check;
- the convention placement;
- the 6b walk with each branch fact true, false or unmentioned (2187, 6561 and 243 assignments);
- the open-fact presumption check;
- the new gate-document request check;
- the size limits.

Counts: 3 types, 23 facts (8 + 9 + 6), 22 steps, 22 document needs from a 14-document catalogue, 0 statutory presumptions, 14 convention presumptions, 7 stops. That is 74 cited rules (37 `states`, 15 `follows`, 22 `evidence`) and 1 convention rule.

## After the reader's second look (version 2026-11-12.5)

The reader's second look is appended to `CITATION_CHECK.md`. It resolves all 29 points, agrees with the new rules and with the revised silence test, and leaves two items open. Both were applied in the reader's own proposed wording, together with the reader's small recommendations.

1. **`written_objection` and `court_filing` (type 2): need condition narrowed.**
   - Each document is now needed only when its own fact is yes (`objection_submitted`, `action_in_time`).
   - When that fact is unmentioned or open, the document is held behind the question, which is the product's ordinary behaviour. When it is stated no, nothing is requested and the stop applies.
   - The disjuncts "or the notice period has ended" and "or 180 days have passed" are removed, together with the sentences that explained them.
   - **This reverses part of the planner's decision 4,** after the reader's run of the product showed that the disjunct requested a document the file says does not exist on the path to a stop. A claimant knows whether they objected or filed, so the first act on an unsettled fact is the question.
   - The gate-document request check in `check.py` now covers only documents whose need does not depend on the claimant's own knowledge: the notice, the contract and the probation terms. Its description says so.
2. **`notice_period_ended` and `more_than_180_days`: `not_this` extended.**
   - A protected period under art. 336c para. 2, or untaken leave of the other parent under art. 335c para. 3, pushes the end of the notice period past the date on the letter. If the file raises either, the fact is open.
   - Art. 335c is already stored in full in the snapshot (para. 3 included), so the snapshot needed no change.
   - **Correction of my earlier statement:** completeness points 6, 8 and 9 were *not* named in a `not_this` or summary line, as the reader found. They now are:
     - 6: seven days during probation (art. 335b para. 1), added to the "statutory ones" wording of `notice_period_varied`;
     - 8: art. 335c para. 3, in the two `not_this` lines above;
     - 9: art. 336 para. 3, in `employee_representative`'s `not_this`.
3. **Small recommendations:**
   - `incapacity_proof` has one catalogue title in both types, "Proof of the hindrance from working (medical certificate, or official order or summons for a non-voluntary legal obligation)". Type 1's `must_show` stays specific: medical certificate, illness or accident.
   - The seven-day probation notice is in the statutory-periods wording.
   - The art. 336 para. 3 `not_this` is added.
   - In `rule_text.md`, the link from "anhängig gemacht" to CPC art. 62 para. 1 is labelled as an inference across the two acts, in both the type 2 summary and "Where the translation was not followed". `court_filing`'s inference in `rules.json` says the same.
4. **"Known behaviour" section added to `RULES.md`.** It records:
   - the reader's stated limit: with the illness fact open, the proof of incapacity is held, not requested;
   - the narrowed type 2 document needs;
   - that silence, while never ending a process, can choose which type 2 stop ends it.
5. **Workflows set to status "reviewed".** Rebuilt, and `python3 -I tools/check.py` passes with the full walks: 2^8, 2^9 and 2^6 complete assignments, plus 6b walks over 2187, 6561 and 243 assignments.
   - A product probe on type 2, with the notice period ended: objection unmentioned → `written_objection` held ("depends"); stated no → not requested, stop `b_stop_no_objection`; stated yes → requested.

Counts are unchanged: 3 types, 23 facts, 22 steps, 22 document needs from 14 catalogue documents, 0 statutory presumptions, 14 convention presumptions, 7 stops, 74 cited rules plus 1 convention rule.

Closing line: reader's second look of 2026-11-12 recorded in `CITATION_CHECK.md`; the edits in this section were made after it, in the reader's own proposed wording. SHA-256 at the time of marking reviewed:
- rules.json 75bbd5f426a8cdb182b30259b585dbfef08ec0b825379838d48c766da586aef8
- rule_text.md 421a24b7b0750fdd799fbe2ac198366a71e089391f6a7bb167a029437dbe80a9
- workflow/protected_period_notice.json a772d1e0674b236c5cc6da0877319dbff83ebbfe24892dfa5f6f889f9046a276
- workflow/wrongful_termination.json 14b701c961ea33a810d5b5140755330515c53b932f994f9e3586292ef95e3731
- workflow/immediate_dismissal.json 5d1be3813ce84534f3328318efa4cbaffc2306cee4b82640d076a8812965be63

Clarification after review (2026-11-12): one general paragraph on reading steps and stops added to rule_text.md and rules.json; no rule changed. New SHA-256 (workflows byte-identical to before the clarification):

- rules.json 2338aff4ad096f614d0656432fb39523d0b839fc2b61bf90e67c9ce83a7989a1
- rule_text.md 174b57f06ee1d5498c54bb670e100a7117da49e246460a8dbf9f0f92528a83a3
- workflow/immediate_dismissal.json 5d1be3813ce84534f3328318efa4cbaffc2306cee4b82640d076a8812965be63
- workflow/protected_period_notice.json a772d1e0674b236c5cc6da0877319dbff83ebbfe24892dfa5f6f889f9046a276
- workflow/wrongful_termination.json 14b701c961ea33a810d5b5140755330515c53b932f994f9e3586292ef95e3731

## Revision after first use (development, 2026-11-12)

DEVELOPMENT material, post hoc. The rule set's first use (the clean arm of the lint test, `lint/REPORT.md`, gpt-6-luna,
58 dismissal files) was diagnosed from the stored readings in `lint/DIAGNOSIS.md` (written by `lint/diagnose.py`;
judgments in `lint/diagnosis_review.json`). Only wording that Part A showed to be ours is changed; each change is a
general rule, written in `tools/build.py` and rebuilt. The fixes were designed on the same 58 files they are checked on
(in-sample, development). The rule set as the lint runs read it is kept in `rev0/`.

Not changed: no document, `needed_when`, `mandatory` or `must_show` item; no fact id, step, condition, presumption or
stop; the convention of SPEC 6a; the routing values (type ids). `lint/verify_rev1.py` (`lint/VERIFY_REV1.json`):
rules' and workflows' logic equal to `rev0/`; every stored final reference keeps its manifest hash; the product's
evaluator recomputes all 58 final references unchanged; the clean-room comparison on the 60 designs still gives 436 of
436 document states equal to both evaluators. `tools/check.py`: ALL CHECKS PASSED. `generator/test_generator.py`: 15
tests OK. (The dismissal workflows give the product the question only, not `not_this`.)

### D1. Routing question (workflow fact `dispute_family`) and type 1's title

- **Old question:** "Which employment-termination dispute does the claim concern: notice during a protected period,
  abusive notice, or dismissal with immediate effect?"
- **New question:** "Which employment-termination dispute does the claim concern? protected_period_notice: an ordinary
  notice of termination by the employer where the claim concerns whether it is valid or when the employment ends,
  because of the probation period, an incapacity through illness or accident, compulsory service, pregnancy or birth,
  or the notice period (CO arts. 335b, 335c, 336c). wrongful_termination: an ordinary notice by the employer that the
  claim contests as abusive (given for an improper reason, such as retaliation for claims or an employee
  representative's mandate), or against which the employee objects or claims compensation (CO arts. 336-336b).
  immediate_dismissal: a dismissal with immediate effect, without a notice period (CO arts. 337-337c)."
- **Old title (type 1):** "Notice of termination by the employer during a protected period (CO art. 336c)". **New:**
  "Notice of termination by the employer: probation, protected periods and notice period (CO arts. 335b, 335c, 336c)".
  The router sees the titles beside the values and is told that a value naming a specific matter applies only to it.
- **Evidence (Part A):** all 4 non-denied routing failures (of 50 non-denied files) are type-1 files, 4 of its 18
  non-denied files: dis_14b7db92a192 and dis_1bf62841defb (ordinary notice, dispute about the contractual notice
  period, every protected period denied or absent) got no routing value; dis_bf38c7dfb616 (ordinary notice, written
  probation clause and notice period) and dis_c50430dbdfa1 (notice by text message while ill and in the probation
  period) were routed to wrongful_termination. The old value named one outcome of type 1 ("notice during a protected
  period"), while type 1's own conditions decide probation (art. 335b), the protected periods (art. 336c) and the
  notice period (art. 335c para. 2) of an ordinary notice. 10 errors (6 holds where the file settles the fact, 4
  requests missed).
- **Passages:** CO art. 336c para. 1 (introduction): "After the probation period has expired, the employer may not
  terminate the employment relationship" (German "Nach Ablauf der Probezeit darf der Arbeitgeber das Arbeitsverhältnis
  nicht kündigen"), the passage of type 1's defining event and of `notice_during_probation`; CO art. 335c para. 2:
  "These notice periods may be varied by written individual, standard or collective employment contract"
  (`notice_period_varied`); CO art. 336 para. 1 let. d: "because the other party asserts claims under the employment
  relationship in good faith" (type 2); CO art. 337c para. 1: "Where the employer dismisses the employee with immediate
  effect without good cause, the employee is entitled to damages" (type 3).
- **Why no broader and no narrower:** each value is described by the matters its type's own conditions decide, with
  the articles those conditions cite; no type gains a matter it has no condition for. The routing fact's source
  reference (arts. 335-337c) is unchanged.
- **Limit for the planner:** types 1 and 2 share their defining event (`employer_gave_notice`). A file that raises
  matters of both (for example illness at the time of notice and an objection for abuse) is not separated by any
  wording; separating them needs a defining event of its own per type, which is a fact and design change this
  revision may not make.

### D2. `wrongful_termination.retaliation_for_claims` (question)

- **Old:** "Was the notice given because the employee had asserted, in good faith, claims arising from the employment
  relationship?"
- **New:** the same, followed by: "The employee's own account of the employer's reason counts as stating it, also where
  the employee gives it as a conviction or belief; it is open only where the claim itself says the reason is unknown,
  uncertain or one of several possibilities."
- **Evidence (Part A):** of the 5 files in which the fact is stated true, 3 had a reading answering "open" on a firm
  statement of the employee's belief: "Ich bin überzeugt, dass ich die Kündigung bekommen habe, weil ich meinen Lohn
  eingefordert habe" (one of three), "I'm convinced I lost my job because I stood up for myself" (two of three), "Why do
  I think I was let go? Because I asked for what I'm due." (one of three). 1 hold where the file settles the fact
  (dis_fb44c47f6ec7), and it is one of two facts behind a second hold (dis_408b774aa7db). The same gap appears in
  tenancy (`asserted_claims`).
- **Passage:** CO art. 336 para. 1 let. d: "because the other party asserts claims under the employment relationship in
  good faith" (German "weil die andere Partei nach Treu und Glauben Ansprüche aus dem Arbeitsverhältnis geltend macht").
- **Why no broader and no narrower:** the condition ("because", "in good faith", "claims under the employment
  relationship") is unchanged; the sentence says only how the employee's statement of the employer's reason is read at
  intake. A coincidence in time without a stated link stays outside (`not_this`, unchanged).

### Considered and not changed

- The defining events held in dis_32d79153a27f, dis_b7f5c9e07c99, dis_188837a70acc and the held `notice_period_ended` in
  dis_408b774aa7db (14 holds in all, 3 of them together with a second fact; two more files, 2 holds, the same way): every reading gave the designed value, but a quotation was not found word for
  word (a capital letter at the start of a quoted part sentence, or scan noise the reading corrected). The product's
  quotation rule, not the wording.
- `incapacity_illness_accident` in dis_3f2fbc0b6128 (1 request missed): all three readings answered "not stated" for an
  illness the file states clearly (six days before the notice). The question asks in the same breath whether the
  incapacity was "still within its protected length" (30, 90 or 180 days by year of service), which the file does not
  state; the readings may have stopped there. One file; left as a product reading, flagged for the second reader.
- Two denied-event files deny the immediate dismissal by stating an ordinary notice (dis_827bbd04ddc9 unrouted,
  dis_ff1e9056d2c3 routed to wrongful_termination, 5 errors). An ordinary notice is the defining event of types 1 and
  2, so the rule text gives one of those processes, not the stop the reference records; a benchmark-design point,
  left for the planner.
- Needed but not allowed in this revision: `employment_contract.must_show` lists "probation clause, if any;
  notice-period clause, if any", and the product read the conditional items as required for contracts that have no
  such clause (6 requests that should not be made). A `must_show` change; left for the planner.

### Hashes after the revision

- rules.json 96b89ea6d2aaaf2efe7a0061eec14e7a3cb91ba04a015855e6362515d12081e2
- rule_text.md ab1ecb117c7a21feee853a119a7962ff19d8830219fa1a1d9b74f8583996a2d5
- workflow/protected_period_notice.json 06e836f2bc66031ef6db2ced25bf05b7a817d1cef4c0eab25c0e2a0cbe5408a5
- workflow/wrongful_termination.json ac190d8f2178b60c03d8c6a10bb3e32ca9bbd779cc52577f05508fa1724a8a9f
- workflow/immediate_dismissal.json 2c691bbc6f9eeb875019e93a373cfdb4c8904263e55e1f9f070e7f9f23ec16c3

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
`generator/items/rev1/dismissal.json`.

Not changed: no document, title, step, `needed_when`, `mandatory`; no fact, question, `not_this`, presumption or stop;
which items are conditional and when they apply (`generator/items/dismissal.json`: only `item` keys renamed).
`lint/verify_rev2.py` (`lint/VERIFY_REV2.json`) confirms: rules.json and every workflow equal `rev1/` except the
must_show wording, read through `MUST_SHOW_WORDING.json`; every stored `dev/dismissal/final/*/reference.json` and `design.json`
still has its manifest hash; the product's evaluator recomputes every final reference unchanged with the revised
workflows; the clean-room comparison on the 60 designs gives the same document states as both evaluators for all
documents; for every design and item the notes give the same conditional / applies / checkable_as as before; every
writer bundle is the same once item texts are mapped. `tools/check.py` passes and now enforces the fixed form, no
"whether" and no absence wording (it reports the old wording in `rev1/` as failing). `generator/test_generator.py`:
all tests pass.

Changed items (4 rows (8 item instances: the contract's probation and notice-period items are in all three types)):

1. **employment_contract** (protected_period_notice, wrongful_termination, immediate_dismissal)
   - Old: "probation clause, if any"
   - New: "Only if the file states that a written agreement or contract sets a probation period other than the first month of employment: the probation clause. Otherwise this item does not apply."
   - Cited passage (the document's rule, basis evidence): CO art. 335b para. 1: "the probation period is considered to be the first month of an employment relationship" (German: "als Probezeit gilt der erste Monat eines Arbeitsverhältnisses")
   - Condition: fact `probation_varied` ("Does the file say that a written individual agreement, a standard employment contract or a collective employment contract set a probation period other than the first month of employment?"), CO art. 335b para. 2: "Different terms may be envisaged by an individual written agreement, a standard employment contract or a collective employment contract; however, the probation period may not exceed three months." (German: "Durch schriftliche Abrede, Normalarbeitsvertrag oder Gesamtarbeitsvertrag können abweichende Vereinbarungen getroffen werden; die Probezeit darf jedoch auf höchstens drei Monate verlängert werden.")
   - Why: 'if any' lets an absence satisfy the item; the product read it as required in 7 files (dis_064eeecaeb0d and others). Now the fixed form with the generator's condition (probation_varied stated true). In wrongful_termination and immediate_dismissal the type has no such fact, so the condition never holds there, as in the generator.
2. **employment_contract** (protected_period_notice, wrongful_termination, immediate_dismissal)
   - Old: "notice-period clause, if any"
   - New: "Only if the file states that a written contract sets notice periods different from the statutory ones: the notice-period clause. Otherwise this item does not apply."
   - Cited passage (the document's rule, basis evidence): CO art. 335b para. 1: "the probation period is considered to be the first month of an employment relationship" (German: "als Probezeit gilt der erste Monat eines Arbeitsverhältnisses")
   - Condition: fact `notice_period_varied` ("Does the file say that a written individual employment contract, a standard employment contract or a collective employment contract sets notice periods different from the statutory ones (seven days during probation, art. 335b para. 1; one month in the first year of service, two months in the second to ninth years, three months thereafter)?"), CO art. 335c para. 2: "These notice periods may be varied by written individual, standard or collective employment contract" (German: "Diese Fristen dürfen durch schriftliche Abrede, Normalarbeitsvertrag oder Gesamtarbeitsvertrag abgeändert werden")
   - Why: As the probation clause; the generator's condition is notice_period_varied stated true (no such fact in wrongful_termination).
3. **employment_contract** (immediate_dismissal)
   - Old: "agreed end date, if fixed-term"
   - New: "Only if the file states that the employment was agreed for a fixed term: the agreed end date. Otherwise this item does not apply."
   - Cited passage (the document's rule, basis evidence): CO art. 337c para. 1: "the employee is entitled to damages in the amount he would have earned had the employment relationship ended after the required notice period or on expiry of its agreed duration" (German: "so hat dieser Anspruch auf Ersatz dessen, was er verdient hätte, wenn das Arbeitsverhältnis unter Einhaltung der Kündigungsfrist oder durch Ablauf der bestimmten Vertragszeit beendigt worden wäre")
   - Condition: fact `fixed_term` ("Was the employment relationship agreed for a fixed term, with an agreed end date, rather than for an unlimited period?"), CO art. 337c para. 1: "the employee is entitled to damages in the amount he would have earned had the employment relationship ended after the required notice period or on expiry of its agreed duration" (German: "so hat dieser Anspruch auf Ersatz dessen, was er verdient hätte, wenn das Arbeitsverhältnis unter Einhaltung der Kündigungsfrist oder durch Ablauf der bestimmten Vertragszeit beendigt worden wäre")
   - Why: Condition at the end ('if fixed-term'); round 1 drew it as the missing item in files that are not fixed-term (dis_6093ca79060d, dis_925dc8cee367, both dropped). Now the fixed form with the generator's condition (fixed_term stated true).
4. **claims_correspondence** (wrongful_termination)
   - Old: "employer's response, if any"
   - New: "Only if the file states that the employer responded to those claims: the employer's response. Otherwise this item does not apply."
   - Cited passage (the document's rule, basis evidence): CO art. 336 para. 1 let. d: "because the other party asserts claims under the employment relationship in good faith" (German: "weil die andere Partei nach Treu und Glauben Ansprüche aus dem Arbeitsverhältnis geltend macht")
   - Why: 'if any' lets an absence satisfy the item. Now the fixed form; the generator leaves the condition to the story (conditional, no applies_when), and no fact records a response.

### Considered and not changed

- `pregnancy_certificate` "pregnancy confirmed and its dates, or the date of birth": one record (a confirmation or a birth record), always applies. Kept.
- `termination_letter` (immediate) "that employment ends with immediate effect": a statement visible on the letter. Kept.

### Hashes after revision 2

- rules.json cf853c508fc6000517b4bc2c9005bd9c263c3d916aa34aff0594af29875a69f3
- rule_text.md 2dd108a0c558dacf801313b4b1d68ea94b7147dd7e48d265e93f65a88ca9fa99
- MUST_SHOW_WORDING.json c6c4b03604ad50b0c9c7ecb2e096eaace93b772dc69ef6e96b8ff1195affd265
- workflow/immediate_dismissal.json 68d30cacaf306f131fcd7067bd096ee85dec09a2ac74177e3c1e1f01e0fe4495
- workflow/protected_period_notice.json bcb3b315b0e41750260b9f2db545f28167dd7a1480b528c67843246b919eac69
- workflow/wrongful_termination.json 42fb560393be78ae735520fce6cae19ca76e0ddf8781b4b4c348dc6265ae70c7

State before revision 2 (`rev1/`, equal to the hashes after revision 1 above):

- rev1/rules.json 96b89ea6d2aaaf2efe7a0061eec14e7a3cb91ba04a015855e6362515d12081e2
- rev1/rule_text.md ab1ecb117c7a21feee853a119a7962ff19d8830219fa1a1d9b74f8583996a2d5
- rev1/workflow/immediate_dismissal.json 2c691bbc6f9eeb875019e93a373cfdb4c8904263e55e1f9f070e7f9f23ec16c3
- rev1/workflow/protected_period_notice.json 06e836f2bc66031ef6db2ced25bf05b7a817d1cef4c0eab25c0e2a0cbe5408a5
- rev1/workflow/wrongful_termination.json ac190d8f2178b60c03d8c6a10bb3e32ca9bbd779cc52577f05508fa1724a8a9f
