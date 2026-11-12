# Citation check: dismissal rule set (version 2026-11-12.3)

Second reader (four-eyes, SPEC.md step 2a item 7). I did not write this rule set. Standard applied: SPEC.md "Rule sets from public text (step 2a)", items 1 to 7, including 6a and 6b. Files read: `rules.json`, `RULES.md`, `rule_text.md`, `sources/SOURCES.json`, `sources/co-sr220-en.txt`, `sources/co-sr220-de.txt`, `workflow/*.json`, `tools/check.py`. I did not read other regimes or earlier analyses. I made no network calls. I edited no file except this one.

## Mechanical checks (what actually ran)

- `python3 -I tools/check.py` from this folder ends `ALL CHECKS PASSED` (exit 0). It reports 76 rules: 22 facts, 23 steps, 22 documents, 3 presumptions, 6 stops. It also reports, as expected, that the frozen validator rejects the source kind `benchmark_convention`.
- Snapshot integrity: sha256 of both raw XML files and both snapshots match `SOURCES.json`.
- My own script (scratch only) checked all 76 passages. Every English passage is in `co-sr220-en.txt` character for character, every `passage_de` is in `co-sr220-de.txt`, and none is over 60 words. Against the raw XML (tags stripped), the only misses come from footnote markup inside the sentence (for example a footnote after "elf" in art. 336c para. 1 let. a) and from `336<i>a</i>`. The wording is the same, so the snapshots are faithful.
- **Four rules have no `passage_de`.** Type 1 document `notice_period_terms` (art. 336c para. 3), type 2 document `employment_contract` (art. 335c para. 1), and both presumptions on `notice_period_varied` (art. 335c para. 1). SPEC item 1 makes the German text decide, so each of these needs its German passage.
- The convention text in `rules.json` equals SPEC 6a's quoted block exactly. It appears verbatim as a block quote in `rule_text.md`, and in each workflow's convention presumptions after the prefix "Convention of this benchmark (not law): ".

## Translation spot-check against the German text (test 1)

| Locator | English | German | Drift that changes a rule? |
|---|---|---|---|
| 336c(1) intro | "the employer may not terminate" | "darf ... nicht kündigen" | Small. "kündigen" means ordinary notice. "terminate" also reads on termination with immediate effect (art. 337), and `employer_gave_notice` does not exclude that (see the table). |
| 336c(1) let. b | "for up to 30 days in the first year ..." | "im ersten Dienstjahr während 30 Tagen ..." | None. The **rule** drops this clause (see `incapacity_illness_accident`). |
| 336c(1) let. c | "pregnancy of an employee and the sixteen weeks following birth" | "Schwangerschaft und in den 16 Wochen nach der Niederkunft einer Arbeitnehmerin" | None. |
| 336c(2) | "void" / "suspended" | "nichtig" / "unterbrochen ... fortgesetzt" | None. |
| 335b(2) | "may not exceed three months" | "darf jedoch auf höchstens drei Monate verlängert werden" | None. |
| 335c(2) | "varied by written individual ... contract" | "durch schriftliche Abrede ... abgeändert" | None. |
| 335(2) / 337(1) | "state his reasons in writing if ... requests" | "schriftlich begründen, wenn ... verlangt" | None. |
| 336 intro | "unlawful" | "missbräuchlich" | **Yes, in what it implies.** "Unlawful" suggests the notice is invalid. Under arts. 336a and 336b an abusive notice is effective and gives rise only to compensation. `rule_text.md` says "wrongful ('missbräuchlich')", which is right. |
| 336(2) let. b | "the employer cannot cite just cause" | "der Arbeitgeber nicht beweisen kann, dass er einen begründeten Anlass ... hatte" | **Yes.** The German puts a burden of *proof* on the employer, where the English says only "cite". "Begründeter Anlass" is also a different and weaker standard than "wichtiger Grund" (art. 337 "good cause"), while the English "just cause" invites the two to be confused. |
| 336b(1) | "submit his objection ... to the party giving such notice" | "beim Kündigenden schriftlich Einsprache erheben" | Not in the passage. The **question** of `objection_submitted` says "send", which is weaker than "beim Kündigenden erheben" (lodge with the employer). |
| 336b(2) s. 2 | "The claim prescribes if not brought before the courts" | "Wird nicht ... eine Klage anhängig gemacht, ist der Anspruch verwirkt" | **Yes.** "Prescribes" (Verjährung) must be pleaded and can be interrupted. "Verwirkt" means forfeited, which applies by itself. "Anhängig gemacht" (made pending) is not the same as "brought before the courts". The stop is sound only on the German. |
| 337(3) | "an employee being prevented from working through no fault of his own" | "die unverschuldete Verhinderung des Arbeitnehmers an der Arbeitsleistung" | None. The **rule** narrows it to illness or accident (see `incapacity_cause`). |
| 337c(1) | "agreed duration" | "Ablauf der bestimmten Vertragszeit" | None. |
| 337c(2) | "saved ... earned by performing other work or would have earned" | "erspart hat und ... verdient oder zu verdienen absichtlich unterlassen hat" | None. The **rule** keeps only "earned". |

## Rule-by-rule table

Kinds: F fact, S step, D document need, P presumption, X stop, C convention. Verdicts: agree, agree with change (AWC), disagree.

### Type 1: protected_period_notice (art. 336c)

| Rule id | Kind | Basis | Verdict | Reason (one sentence) | Proposed wording / change |
|---|---|---|---|---|---|
| employer_gave_notice | F | states | AWC | Passage and locator are right, but the English "terminate" (German "kündigen") leaves a dismissal with immediate effect (art. 337) answered yes, and `not_this` does not exclude it. | not_this: "A resignation by the employee, a fixed-term relationship that ended by running out, or a dismissal with immediate effect (art. 337)." |
| notice_during_probation | F | states | AWC | The passage states the converse ("After the probation period has expired"), so the rule is the one-step inference that the bar does not reach notice given during probation: basis must be `follows`. The question also ignores art. 335b para. 3 (probation extended by illness, accident or legal obligation), which is in a cited article. | basis `follows`; inference "The bar applies only after the probation period has expired, so notice given during it is outside the bar." Question: "Was the notice given while the probation period, including any extension under art. 335b para. 3, was still running?" Add 335b(3) as a second cited passage. |
| probation_varied | F | states | agree | Verbatim; question matches para. 2 (written instrument, other than the first month); `not_this` (oral arrangement) is the nearest uncovered case. | Note only: it is worded about the file ("Does the file say"), unlike the world-facts beside it; harmless. |
| incapacity_illness_accident | F | states | **disagree** | Broader than let. b: the passage limits the bar to 30, 90 or 180 days by year of service, the question drops that limit, and a first-year employee ill for 60 days, given notice on day 45, is answered yes where the letter plainly does not apply; the timing ("on the day ... or while the notice period was still running") comes from para. 2, not let. b. | Question: "Was the employee, through no fault of their own, wholly or partly prevented from working by illness or accident on the day notice was given or while the notice period was running, within the first 30 days of that incapacity in the first year of service, 90 days in the second to fifth, or 180 days from the sixth year?" Locator "CO art. 336c para. 1 let. b and para. 2"; quote the duration clause in the passage. |
| compulsory_service | F | states | AWC | Content matches let. a (including the eleven-day and four-week rule), but the timing relation to notice comes from para. 2. | Locator "CO art. 336c para. 1 let. a and para. 2". `not_this` could add the overseas aid service of let. d, which is not covered. |
| pregnancy_or_birth | F | states | AWC | Content matches let. c and `not_this` honestly names cbis–cquinquies; the timing again comes from para. 2. | Locator "CO art. 336c para. 1 let. c and para. 2". |
| notice_before_protected_period | F | states | AWC | Para. 2 does give two ordinary alternatives (void or suspended), so `always_stated` is sound, but only where a protected period is raised: in a file without one, "the protected period" has no referent and the generator cannot sensibly state it. | Add: "Asked only when a protected period (let. a, b or c) is raised; otherwise not applicable." The generator states it only in those files. |
| notice_period_varied | F | states | agree | Verbatim 335c(2); the statutory periods in the question are 335c(1); `not_this` is sensible. | none |
| a_intake | S | follows | agree | One step: the bar restrains an employer's notice, so the process starts there. | none |
| a_probation | S | states | agree | The passage states the after-probation condition that this step checks. | (See a_notice for the documents.) |
| a_notice | S | follows | AWC | The inference is fine, but this step carries `employment_contract` and `probation_terms` (start date, probation length), the documents that decide `notice_during_probation`, and it is reached only after that fact has been settled false; the documents arrive after the decision they serve. | Attach `employment_contract` and `probation_terms` to `a_probation`, or reach `a_notice` before the probation branch. |
| a_incapacity | S | states | agree | Matches let. b (subject to the fact's correction). | none |
| a_service | S | states | agree | Matches let. a. | none |
| a_pregnancy | S | states | agree | Matches let. c. | none |
| a_suspension | S | states | agree | Para. 2 second half states it verbatim. | Optionally add para. 3 to the locator (end-point extension). |
| a_void | S | states | agree | Para. 2 first half states it verbatim. | none |
| a_assess | S | follows | agree | Reconvergence after void/suspended/no period is one valid step from para. 2. | none |
| termination_letter | D | evidence | AWC | Voidness turns on the day notice was given and received; the letter proves it, but the cited text sets no written form for notice, so the letter may not exist (oral notice), and an e-mail, message or witness record proves the same day. | Title "Notice of termination (letter, message or other record of the notice and its receipt)". |
| employment_contract | D | evidence | agree | The start date fixes the first month of probation (335b(1)), and the contract or another record of the start date ordinarily proves it. | none |
| probation_terms | D | evidence | agree | 335b(2) creates the condition, and the written clause proves the length. | (Placement: see a_notice.) |
| medical_certificate | D | evidence | agree | It proves incapacity and its dates, which let. b requires. Note that it does not prove "no fault of his own"; once the cap is added, the year of service comes from `employment_contract`. | none |
| service_confirmation | D | evidence | agree | The official service order or confirmation shows kind, dates and length (eleven-day threshold). | none |
| pregnancy_certificate | D | evidence | agree | A medical confirmation or birth record dates the let. c period. | none |
| notice_period_terms | D | evidence | **disagree** | Its condition is `notice_period_varied`, which is created by art. 335c para. 2, but the cited passage is 336c para. 3 (an end-point extension), which neither creates the written-variation condition nor names the document; it also has no `passage_de`. | Cite CO art. 335c para. 2 "These notice periods may be varied by written individual, standard or collective employment contract" with DE "Diese Fristen dürfen durch schriftliche Abrede, Normalarbeitsvertrag oder Gesamtarbeitsvertrag abgeändert werden", as type 3 already does; keep 336c(3) as a second passage for the end-point. |
| P probation_varied=false | P | follows | AWC | 335b(1) supplies the default *consequence* (first month) when there is no written variation, but not the step "the file states none, therefore none exists"; that step holds only because the question asks what the file says, so it is the question's wording plus the convention, not the text. | Inference: "The statute fixes the probation period at the first month unless a written term varies it; the fact asks whether the file states such a term, so a file that states none answers no and the statutory default governs." |
| P notice_period_varied=false | P | follows | AWC | Same reasoning as the previous row; also missing `passage_de`. | Same inference pattern; add DE "Das Arbeitsverhältnis kann im ersten Dienstjahr mit einer Kündigungsfrist von einem Monat ... je auf das Ende eines Monats gekündigt werden." |
| a_stop_no_notice | X | follows | agree | On a denied defining event, 336c(1) restrains only an employer's notice; with none, para. 2 has nothing to void or suspend, so the stop is sound on the text alone. | none |
| a_stop_probation | X | follows | AWC | Sound on 336c(1) alone (the conditional "After ... has expired" leaves notice during probation outside the bar), provided `notice_during_probation` already accounts for the 335b(3) extension, which the rule set does not model. | Tie to the corrected `notice_during_probation` question; cite 335b(3) as well. |

### Type 2: wrongful_termination (arts. 335, 336, 336a, 336b)

| Rule id | Kind | Basis | Verdict | Reason (one sentence) | Proposed wording / change |
|---|---|---|---|---|---|
| employer_gave_notice | F | states | AWC | 336b(2) states that the *party served* may claim, not that the employer gave notice (336(1) covers notice by either party), so "employer" is a scoping choice, and `not_this` omits dismissal with immediate effect, which art. 336 (a "Kündigung") does not govern. | basis `follows` (or add 336(2) intro "notice of termination given by the employer"); not_this add "or a dismissal with immediate effect (art. 337)". |
| notice_period_ended | F | states | agree | Para. 1's deadline makes "ended / not yet ended" two ordinary alternatives, so `always_stated` is right. | Note: the end may move under 336c(2)/(3) and 335c(3) (see completeness). |
| objection_submitted | F | states | AWC | "Send ... before the notice period ended" is broader than "beim Kündigenden ... längstens bis zum Ende ... Einsprache erheben": a letter posted on the last day and received after it is answered yes, though on the German the objection must be lodged with the employer by then. Para. 2 also requires the objection to be "gültig" (valid). | "Did the employee lodge a written objection to the notice with the employer no later than the end of the notice period?" |
| more_than_180_days | F | states | agree | Two ordinary alternatives counted from the end of the employment relationship; `always_stated` and `not_this` are right. | none |
| action_in_time | F | states | AWC | Follows the English "brought before the courts", while the authoritative text says "Klage anhängig gemacht" (made pending), a procedural term that a lay reader cannot map onto a filing; the question can be answered no for a claim made pending in a way other than a court filing. | "Did the employee make the compensation claim pending (anhängig) before a court within 180 days of the end of the employment relationship?"; what makes a claim pending (in practice also a conciliation request, Civil Procedure Code art. 62 para. 1) needs a cited passage before it enters the rules. |
| reasons_requested | F | states | agree | Verbatim 335(2); `not_this` is sensible (the text sets no form for the request). | none |
| retaliation_for_claims | F | states | AWC | The passage requires notice given *because* of claims asserted in good faith; the question asks what the employee *says*, which makes "open" hard to tell from "stated" and differs from every other fact. | "Was the notice given because the employee had asserted, in good faith, claims arising from the employment relationship?" |
| employee_representative | F | states | agree | The status condition matches 336(2) let. b; the second limb (employer's proof) belongs to the step, not to this fact. | none |
| b_intake | S | follows | agree | Valid one step from 336b(2). | none |
| b_objection_check | S | states | agree | 336b(1) states the deadline. | none |
| b_limit_check | S | states | agree | 336b(2) states the 180 days. | none |
| b_notice | S | follows | AWC | Same structural fault as `a_notice`: `written_objection` and `court_filing`, the proof of `objection_submitted` and `action_in_time`, sit at a step reached only after the gates have routed on those facts. | Attach `written_objection` to `b_objection_check` and `court_filing` to `b_limit_check`. |
| b_grounds | S | follows | agree | Art. 336 makes abuse depend on the reason, so establishing the reason is one step. | Note the "unlawful"/"missbräuchlich" drift: an abusive notice still ends the relationship. |
| b_retaliation | S | states | agree | Let. d verbatim. | none |
| b_representative | S | states | AWC | On the German, the employer must *prove* a "begründeter Anlass" (a lower standard than art. 337's good cause); the English "cannot cite just cause" hides both the burden and the standard. | Title "Examine the protection of an elected employee representative (the employer must prove a justified reason, 'begründeter Anlass')"; quote the DE in rule_text. |
| b_compensation | S | states | agree | 336a(2) states the cap. | none |
| termination_letter | D | evidence | AWC | The objection window and the 180 days run from the notice and the end of employment, but notice has no written form in the cited text, and must_show lacks the date of receipt, from which the notice period runs. | Add "date the employee received it" and the title change from type 1. |
| employment_contract | D | evidence | AWC | The inference is fine, but `passage_de` is missing, and the end of the notice period also depends on whether notice fell in probation (seven days, 335b(1)), which `must_show` omits. | Add DE of 335c(1); must_show add "probation clause, if any". |
| written_objection | D | evidence | agree | 336b(1) creates the condition, and a copy with proof of sending or receipt proves form and date. | must_show already allows "date ... received"; prefer receipt. |
| court_filing | D | evidence | AWC | The filed claim proves pendency, but on "anhängig gemacht" another filing (in practice a conciliation request) may prove it as well, and the cited text alone cannot settle which. | Title "Proof that the claim was made pending, with its date"; see action_in_time. |
| written_reasons | D | evidence | agree | 335(2) creates the duty, and the written statement is the record of the reason. | Note: where the employer ignored the request, the mandatory document cannot exist. |
| claims_correspondence | D | evidence | agree | Correspondence ordinarily records claims asserted and when; claims asserted orally would need another record. | none |
| representative_mandate | D | evidence | agree | An election record or mandate confirmation proves body and term. | none |
| salary_evidence | D | evidence | agree | Pay slips prove the salary on which the six-month cap is set. | none |
| b_stop_no_notice | X | follows | agree | On a denied defining event, only the party served may claim under 336b(2); where the employer served no notice the employee is not that party and has no claim, so the stop is sound for this employee-side type. | none |
| b_stop_no_objection | X | follows | AWC | Para. 1 states only the duty ("must"); the consequence comes from the conditional in para. 2 s. 1 ("Where the objection has been properly submitted ... may bring his claim"), which should be the cited passage. | Cite 336b(2) s. 1 "Where the objection has been properly submitted and the parties cannot reach agreement on the continuation of the employment relationship, the party on whom notice was served may bring his claim for compensation." with its DE. |
| b_stop_time_limit | X | states | AWC | The stop is sound only on the German "verwirkt" (forfeiture applies by itself); the English "prescribes" alone would not end the process, because prescription must be pleaded and can be interrupted. | Inference: "The German text (authoritative) says the claim is forfeited ('verwirkt'), not merely time-barred, so it ends the process." |

### Type 3: immediate_dismissal (arts. 337, 337c)

| Rule id | Kind | Basis | Verdict | Reason (one sentence) | Proposed wording / change |
|---|---|---|---|---|---|
| dismissed_immediately | F | states | agree | 337c(1) opens with this event; the question and `not_this` (ordinary notice, garden leave) are well drawn. | none |
| reasons_requested | F | states | agree | 337(1) verbatim. | none |
| incapacity_cause | F | states | **disagree** | Narrower than 337(3): the passage covers any prevention from working through no fault of the employee ("unverschuldete Verhinderung"), and an absence for a non-voluntary legal obligation or a summons is answered no and is even excluded by `not_this`. | "Does the employer give as the cause of the dismissal the employee's absence from work, and does the employee say they were prevented from working through no fault of their own (for instance illness, accident or a non-voluntary legal obligation)?"; not_this "A dismissal for conduct at work, or an absence the employee does not say was without fault." |
| fixed_term | F | states | AWC | 337c(1) gives two measures, notice period or agreed duration, and no default between them; who raises a fixed term depends on which end comes later, so the convention's "no" is not supported by 6b, and the always-requested contract shows the term anyway. | Mark `always_stated: true` and drop the convention presumption; or cite a passage that makes open-ended the default (none is among the cited articles). |
| notice_period_varied | F | states | agree | Same as type 1. | none |
| other_earnings | F | states | AWC | Para. 2 also deducts amounts saved and earnings intentionally forgone; the fact keeps only actual earnings, which is acceptable as a scope, but `not_this` should say so. | not_this: "Unemployment benefits; savings from the termination and work intentionally forgone (also deductible under para. 2, not covered here)." |
| c_intake | S | follows | agree | One step from 337c(1). | none |
| c_dismissal | S | follows | agree | Measure of damages under 337c(1) needs dismissal date, contract, salary. | none |
| c_cause | S | follows | agree | 337(2) makes justification depend on the circumstance relied on. | none |
| c_fixed_term | S | states | agree | 337c(1) "expiry of its agreed duration". | none |
| c_notice_period | S | states | agree | 337c(1) "after the required notice period". | Note: the required period is seven days during probation (335b(1)), not modelled. |
| c_damages | S | states | agree | It cites the para. 3 cap, while its document rests on para. 2; acceptable. | Optionally locator "art. 337c paras. 2 and 3". |
| termination_letter | D | evidence | agree | "Letter or message" already allows non-letter forms. | none |
| employment_contract | D | evidence | AWC | It proves the start date, end date and notice clause, but where dismissal fell in probation the required notice is seven days (335b(1)), and the probation clause is not in `must_show`. | must_show add "probation clause, if any". |
| salary_evidence | D | evidence | agree | Pay slips prove lost earnings and the salary for the para. 3 cap. | none |
| written_reasons | D | evidence | agree | 337(1) creates the duty, and the statement records the cause. | none |
| medical_certificate | D | evidence | AWC | It proves illness or accident only; once `incapacity_cause` is widened, another non-fault hindrance is proved by other papers (official summons, service order). | Title "Proof of the hindrance (medical certificate, or official order for a legal obligation)". |
| notice_period_terms | D | evidence | agree | Correctly cites 335c(2) with DE. | none |
| other_earnings_evidence | D | evidence | agree | Pay slips or contracts prove amounts earned in the period. | none |
| P notice_period_varied=false | P | follows | AWC | As in type 1: the inference imports "the file states none, so none exists", and DE is missing. | Same rewording as type 1. |
| c_stop_no_immediate_dismissal | X | follows | agree | On a denied defining event, 337c(1) is conditional on an immediate dismissal by the employer; without one, nothing under this article remains, so the stop is sound. | none |

### Convention and system gate

| Rule id | Kind | Basis | Verdict | Reason (one sentence) | Proposed wording / change |
|---|---|---|---|---|---|
| intake_convention | C | convention | agree | Words equal SPEC 6a exactly; it is declared "Convention of this benchmark (not law)" in rules.json, rule_text.md and all three workflows; no workflow presumption sits on a defining event (employer_gave_notice ×2, dismissed_immediately), on a fact whose false value triggers a stop (objection_submitted, action_in_time) or on an always_stated fact (notice_before_protected_period, notice_period_ended, more_than_180_days). | Cosmetic: the convention note in `wrongful_termination.json` claims that the statutory defaults of 335b/335c take precedence, but that type has none; the notes in the other two workflows print empty lists ("No presumption:  (false would end the process); always stated: ."). |
| a_gate_any_period (workflow only; not counted) | gate | (336c para. 2) | agree | 336c(2) gives an effect only where a protected period exists, so "none raised → assess" is sound; it routes and never ends the process, so the convention's false values on the three period facts lead to "assess", not to a stop. | none |

## Polarity and statutory presumptions (tests 5 and 6), in brief

- `notice_during_probation`: polarity is right (true is what the employer raises to escape the bar; false is ordinary). Its basis should be `follows`, not `states`.
- `always_stated`: `notice_period_ended` and `more_than_180_days` are sound. `notice_before_protected_period` is sound only within files that raise a protected period.
- `fixed_term`: the convention "no" is not supported by the cited text or by 6b. Recommend `always_stated`.
- Statutory presumptions (335b(1), 335c(1)): the statute supplies the default consequence when no written variation exists. It does not supply "unmentioned, therefore none exists". That step holds only because both facts are worded "Does the file say …", so in substance the presumption is the convention under a statutory label. It is harmless here, because neither false value triggers a stop, but the inference should say what carries it.

## Completeness within the cited articles (test 8), most important first

1. **Art. 336b para. 2 s. 1.** A claim also requires that the objection be valid ("gültig") and that the parties did not agree to continue the relationship. Neither is a fact; an agreement to continue defeats the claim.
2. **Art. 335b para. 3.** Probation is extended by illness, accident or a non-voluntary legal obligation. This decides `notice_during_probation`, and with it the probation stop, in exactly the files where `incapacity_illness_accident` is raised early in the employment.
3. **Art. 336c para. 1 let. b, duration limit.** The limit of 30, 90 or 180 days by year of service is quoted nowhere and asked nowhere (see the disagreement above).
4. **Art. 336c para. 1 let. cbis–cquinquies and let. d.** These are the extended maternity leave, the leave of art. 329f para. 3, carer's leave (329i), the leave of 329gbis, and overseas aid service. Each is a protected period with its own proof document (leave records, an order from the federal authority).
5. **Other abuse grounds in art. 336.** Para. 1 let. a, b, c and e and para. 2 let. a and c are not modelled; a file that alleges them gets no ground step and no document request. For example, let. e (compulsory service) would need `service_confirmation`, and let. c of para. 2 (mass redundancy without consultation) carries the two-month cap of art. 336a para. 3.
6. **Art. 335b para. 1, seven-day notice during probation.** This sets the end of the notice period (type 2 objection deadline) and the "required notice period" for type 3 damages. No probation fact or probation clause is requested in types 2 and 3.
7. **Art. 336c paras. 2–3 inside type 2.** A protected period suspends and extends the notice period, which moves the art. 336b para. 1 objection deadline. Type 2 never asks about one, so `notice_period_ended` may be answered yes too early.
8. **Art. 335c para. 3.** The notice period is extended by untaken other-parent leave (art. 329g). This also moves the end of the notice period (types 2 and 3). The English says "paternity leave", the German "Urlaub des andern Elternteils".
9. **Art. 336 para. 3.** A representative's protection continues after a transfer under art. 333. This bears on `representative_mandate` ("term of the mandate covering the notice date").
10. **Art. 335c para. 2 second half.** Notice periods below one month are allowed only by a collective contract and only in the first year. A `notice_period_terms` document can show a variation that is invalid, which `must_show` does not test.

## rule_text.md compared with rules.json (test 9)

The conditions, `not_this` lines, stops, steps, documents and presumptions in `rule_text.md` are a faithful rendering of `rules.json`, and I found no rule missing and no step added. The intro paragraphs say slightly more than the rules:

- Type 2 intro correctly glosses "verwirkt, forfeited". This is the German reading that the time-limit stop needs, but it sits beside a stop line that still quotes "prescribes".
- Type 3 intro mentions "what they saved" and the para. 3 compensation, which no fact or document carries. This is harmless but suggests coverage that does not exist.
- Type 2 intro says notice is wrongful "for one of the reasons in art. 336" without saying that only let. d and para. 2 let. b are modelled. A model may look for other grounds that have no documents.

Nothing in the prose gives a model an answer key beyond the rules. The 336(2) let. b German burden ("beweisen", "begründeter Anlass") is missing from the prose; it should be quoted, because the English misleads.

## Counts

| Kind | agree | agree with change | disagree | total |
|---|---|---|---|---|
| Facts | 9 | 11 | 2 | 22 |
| Steps | 20 | 3 | 0 | 23 |
| Document needs | 15 | 6 | 1 | 22 |
| Presumptions | 0 | 3 | 0 | 3 |
| Stops | 3 | 3 | 0 | 6 |
| Convention | 1 | 0 | 0 | 1 |
| **All 77 rules** | **48** | **26** | **3** | 77 |

(The workflow gate `a_gate_any_period` was also checked and agreed; it is not counted, because it is not a rule in `rules.json`.)

## The five findings that matter most

1. **`incapacity_illness_accident` is broader than art. 336c para. 1 let. b (disagree).** It drops the 30/90/180-day limit by year of service. The timing words in all three type 1 period facts come from para. 2, but the locators name only the letter.
2. **Art. 336b para. 2 is read through the English.** "Prescribes" stands for "verwirkt" (the stop is sound only on the German), and "brought before the courts" stands for "anhängig gemacht". The no-objection stop should cite the conditional in para. 2 s. 1. That sentence's two further conditions, a valid objection and no agreement to continue, are not modelled.
3. **`incapacity_cause` is narrower than art. 337 para. 3 (disagree).** It limits "unverschuldete Verhinderung" to illness or accident, and its `not_this` excludes cases the passage plainly covers.
4. **Documents arrive after the decision they serve.** In type 1, the probation documents sit at `a_notice`, which is reached only after `notice_during_probation` is settled. In type 2, `written_objection` and `court_filing` sit at `b_notice`, after the objection and limit gates. The probation stop also ignores the art. 335b para. 3 extension.
5. **Citation defects.** Type 1 `notice_period_terms` cites art. 336c para. 3, which does not create its condition (disagree; cite 335c(2)). Four rules lack the German passage. The two "statutory" presumptions rest their unmentioned-means-none step on the question's wording, not on the text. `fixed_term`'s convention "no" has no textual default and should be `always_stated`.

## Can a reader with the statute open verify this without legal training?

Mostly yes. Without legal training a reader can verify:

- every passage, character for character, in the snapshots;
- every locator;
- that each `states` rule says what its passage says;
- the `follows` steps, which are all short;
- the stop logic;
- the presumption bookkeeping;
- the convention placement.

They could not verify, without help, the points where the English and the authoritative German differ in legal meaning:

- "verwirkt" against "prescribes", and why it matters for a stop;
- "anhängig gemacht" (what makes a claim pending);
- "begründeter Anlass" against "wichtiger Grund", and the burden in "beweisen";
- "missbräuchlich" against "unlawful" (an abusive notice remains effective).

They also could not verify:

- whether each `evidence` document is what "ordinarily" proves the condition (for example, whether notice may be oral, which the cited text does not say);
- how the 30/90/180-day limit and the probation extension are counted in practice.

These points need either a short gloss quoted from the German text in `rule_text.md` or a cited passage from another public act (for example, the Civil Procedure Code for pendency).

## Second look (2026-11-12, rule set version 2026-11-12.4)

I read `RECONCILIATION.md`, the rebuilt `rules.json`, `RULES.md`, `rule_text.md`, the workflows and the new CPC snapshots (`cpc-sr272-en.txt`, `cpc-sr272-de.txt`, art. 62). I made no network calls and no commits. I edited only this file.

What ran:

- **`python3 -I tools/check.py`** passes (ALL CHECKS PASSED). It reports 3 types, 23 facts, 22 steps, 22 document needs, 0 statutory presumptions, 14 convention presumptions and 7 stops.
- **Product probes.** I used the product evaluator through `check.py`'s loader, from scripts in my scratch folder, to see what the reference does on a few paths. The results are quoted where they matter below.

### 1. The 29 earlier points

| # | Rule (type) | Status | Note |
|---|---|---|---|
| 1 | employer_gave_notice (1) | resolved | not_this names art. 337. |
| 2 | notice_during_probation (1) | resolved | Basis `follows`; 335b(3) is in the question and cited as `also`, with DE. |
| 3 | incapacity_illness_accident (1) | resolved | Passage is the whole of let. b with the cap; locator "let. b; para. 2". See section 2 on answerability. |
| 4 | compulsory_service (1) | resolved | Locator includes para. 2; not_this names let. d. |
| 5 | pregnancy_or_birth (1) | resolved | |
| 6 | notice_before_protected_period (1) | resolved | |
| 7 | a_notice (1) | resolved | Step removed; documents at `a_probation`. |
| 8 | termination_letter (1) | resolved | |
| 9 | notice_period_terms (1) | resolved | 335c(2) with DE; 336c(3) as `also`. |
| 10 | P probation_varied (1) | resolved | Now under the convention, declared as such. |
| 11 | P notice_period_varied (1) | resolved | |
| 12 | a_stop_probation (1) | resolved | |
| 13 | employer_gave_notice (2) | resolved | |
| 14 | objection_submitted (2) | resolved | |
| 15 | action_in_time (2) | resolved | The question follows the German; the passage stays English with DE beside it, which is acceptable. |
| 16 | retaliation_for_claims (2) | resolved | |
| 17 | b_notice (2) | resolved | Placement is fixed. The new need condition raises a separate problem; see section 2. |
| 18 | b_representative (2) | resolved | |
| 19 | termination_letter (2) | resolved | |
| 20 | employment_contract (2) | resolved | |
| 21 | court_filing (2) | resolved | CPC art. 62 cited. The need condition raises a separate problem; see section 2. |
| 22 | b_stop_no_objection (2) | resolved | Cites 336b(2) s. 1; the inference names "gültig". |
| 23 | b_stop_time_limit (2) | resolved | |
| 24 | incapacity_cause (3) | resolved | |
| 25 | fixed_term (3) | resolved | `always_stated`, no presumption. |
| 26 | other_earnings (3) | resolved | |
| 27 | employment_contract (3) | resolved | |
| 28 | medical_certificate → incapacity_proof (3) | resolved | Minor note on the shared id in section 2. |
| 29 | P notice_period_varied (3) | resolved | |

**29 of 29 resolved.** Section 2 raises new issues on rules 17 and 21 and on the new rules.

### 2. What I had not seen

- **Documents moved to the gate steps (items 7 and 17).** This is sound. Every document that settles a gate fact now sits at the gate step. `check.py` confirms that an open `notice_during_probation`, `objection_submitted` or `action_in_time` produces a request for its document.

- **The extra need conditions on `written_objection` ("objection_submitted is yes OR notice_period_ended is yes") and `court_filing` ("action_in_time is yes OR more_than_180_days is yes").** These are an encoding device, not something the cited text supports.
  - The text supports the objection (or the filing) deciding the claim once the period has ended (or the 180 days have passed). It does not support requesting a document the file says does not exist.
  - The probe shows the device does exactly that. Take a file that states "notice period ended, no objection was made". It requests `written_objection` and then ends at `b_stop_no_objection`. Likewise, "180 days passed, no claim made pending" requests `court_filing` and then ends at `b_stop_time_limit`.
  - Both inferences say the document is requested "even where the file leaves the objection [filing] open". That is true but incomplete, so the label is **not honest as it stands**.
  - Proposed fix: either narrow the condition so that a stated "no" does not request the document, if the product's condition language can do that without turning "open" into a hold; or add to each inference: "It is also requested where the file states that no objection was lodged [no claim was made pending]; this is a device of the encoding so that an open fact yields a request, and the process then ends at b_stop_no_objection [b_stop_time_limit]."
  - With the added sentence I agree.

- **The two statutory presumptions removed, both facts under the convention (items 10, 11 and 29).** I agree. This is the honest form. The statutory default (first month; 335c(1) periods) still sits correctly in the inferences of `employment_contract`, and none of these facts triggers a stop.

- **`incapacity_proof` shared by two types (item 28).** Acceptable.
  - In type 1 the title is "Medical certificate of incapacity for work", which is right, because only illness or accident counts under let. b.
  - In type 3 the title and `must_show` are broader. One catalogue id therefore has two definitions, and an evaluator reading "the catalogue" may treat it as one document.
  - Recommendation, not a disagreement: give the catalogue entry the general type 3 title in both types and keep the type-specific `must_show`.

- **The illness fact kept as one question with the 30/90/180-day limit.** It is faithful to let. b, and the passage is now the whole of let. b. On whether a model can answer it from a lay claim:
  - It can only when the claim gives the start of employment, the start of the illness and the notice date. Many lay claims give these loosely ("I had worked there two years, I was off sick from March").
  - Where they don't, the fact becomes **open**. The probe shows that with it open, `incapacity_proof` is "depends" (held), not requested. So the certificate that would settle the cap is held exactly where it is needed. Decision 4 already applies to the probation, objection and filing facts but does not reach this gate fact.
  - Where a claimant states the illness had run past the cap, the fact is false and the certificate is never requested, so the claimant's own count cannot be checked.
  - A split ("illness raised" opening the step and requesting the certificate, then "within the protected length" decided from it) would avoid both. The cost is one fact over the size limit, and I accept the writer's reasons.
  - Verdict: agree. This is a recorded limit, not an error: the illness branch will show more holds than the other two period facts.

- **New fact `agreed_to_continue`, step `b_continuation_check`, stop `b_stop_continued` (art. 336b(2) s. 1).** Agree with all three.
  - The passage is verbatim, with DE. "einigen sich die Parteien nicht über die Fortsetzung" is a condition of the claim, so an agreement to continue defeats it in one step. The stop is sound on the cited text alone.
  - Polarity is right: true is what the employer would raise, and false is ordinary. The convention presumption (false) is allowed, because false does not by itself end the process.
  - `not_this` ("talks that ended without agreement; an agreement only about a payment or the end date") draws the right line.

- **"anhängig gemacht" linked to CPC art. 62(1) "Rechtshängigkeit".** The inference is sound. It is the one general provision on when a case becomes pending, and the words share the root ("hängig"). In `court_filing` it is labelled as an inference (basis `evidence`, with the link spelled out in `inference`). Two things fall short:
  - `rule_text.md` (type 2 summary and "Where the translation was not followed") states it as fact: "which under CPC art. 62 para. 1 happens when …".
  - It should read "read with CPC art. 62 para. 1 (an inference across the two acts: the CO says 'anhängig gemacht', the CPC defines 'Rechtshängigkeit')". This is minor, but a lay verifier cannot see the two terms are linked unless told it is a link.

- **`incapacity_cause` widened.** Agree. The question, `not_this` and `incapacity_proof` (type 3) now match "unverschuldete Verhinderung".

- **Art. 335b(3) on the probation fact and stop.** Agree. It is in the question and in the stop's inference, and cited as `also` with DE.

- **Section "Where the translation was not followed".** Accurate on all four points, and the questions do follow the German. It is complete for the points that change a rule, with two small omissions:
  - 336c(1) "terminate" vs "kündigen" is not listed, although `not_this` now handles it.
  - 335c(3) "paternity leave" vs "Urlaub des andern Elternteils" is not listed, but nothing cites that paragraph.

  The only accuracy point is the CPC link stated as fact (see above).

- **The changed 6b stop check.** The new rule: a stop counts as reached through silence only if some true/false answer to the unmentioned facts would avoid every stop. That is the right test of "silence never ends a process". If every answer still ends the process, silence did not end it.
  - It does let silence choose **which** stop is reached. Take "180 days passed, no claim pending" with `agreed_to_continue` unmentioned: the convention's false gives `b_stop_time_limit`, while true would give `b_stop_continued`.
  - That is harmless for "never ends a process". But if the study scores the stop's identity or its documents (`court_filing` is requested on the time-limit path, not on the continuation path), the convention decides it. That follows from 6a and should be stated, not counted as a defect.
  - The test enumerates only true and false. Open values are handled by the product's hold, which the separate open-fact check covers. I see no stop that silence alone causes.

### 3. Completeness points 4–10, left out

The writer says each is "named in the relevant `not_this` or summary where it touches a rule". I checked: that is true for 4, 5 and 10, not for 6 to 9.

| # | Point | Says nothing wrong without it? |
|---|---|---|
| 4 | 336c let. cbis–cquinquies, d | **Yes.** Named in `pregnancy_or_birth` and `compulsory_service`; the type 1 summary says only let. a–c are covered. |
| 5 | Other grounds of art. 336 | **Yes.** The type 2 summary says only let. d and para. 2 let. b are covered; `employee_representative` names para. 2 let. a. |
| 6 | Seven-day probation notice in types 2 and 3 | **Mostly.** The probation clause is now requested (`must_show`), so the documents are right. But both `notice_period_varied` questions define "the statutory ones" as the 335c(1) periods only, which is incomplete during probation. Recommended: add "(seven days during probation, art. 335b para. 1)". Not blocking. |
| 7 | 336c(2) suspension inside type 2 | **No, it can mislead into a stop.** `notice_period_ended` and `more_than_180_days` drive two stops. A notice period suspended by illness, service or pregnancy ends later than the date on the letter, and nothing tells the reader so. A model reading the letter's end date answers "ended", and the file can wrongly end at `b_stop_no_objection`. 336c(2) is already cited in this rule set, so no new law is needed. Proposed `not_this` for `notice_period_ended`: "… ; the end date stated in the notice where a protected period has suspended the notice period (art. 336c para. 2) or untaken leave has extended it (art. 335c para. 3); the period then ends later." Add the matching clause to `more_than_180_days` ("the end of the employment relationship as moved by such a suspension"). |
| 8 | 335c(3) | Folded into 7. Rare on its own; acceptable once 7's `not_this` names it. |
| 9 | 336(3) | **Mostly.** `employee_representative` ("when notice was given, an elected … representative") is answered no for a representative whose mandate ended by a transfer (art. 333) but whose protection continues. That is narrower than the text, though rare and not stated wrongly. Recommended `not_this` addition: "a representative whose mandate ended through a transfer of the employment relationship, whose protection continues (art. 336 para. 3, not covered here)". Not blocking. |
| 10 | 335c(2), second half | **Yes.** The document is needed either way, and its validity is assessment, not a document need. |

### 4. Still not agreed

1. **`written_objection` and `court_filing` (type 2), their need conditions.** These request a document that the file says does not exist on the path to a stop (probe confirmed), while the inference says only "where the file leaves it open". I agree once the inference names this as an encoding device and states the stop-path request, or once the condition is narrowed.
2. **`notice_period_ended` (and, with it, `more_than_180_days`), type 2.** Without a `not_this` naming the 336c(2) suspension (and 335c(3)), the question invites the letter's end date. That can produce a wrong `b_stop_no_objection` or `b_stop_time_limit`. I agree with the wording above.

Recommended but not blocking:

- label the CPC link as an inference in `rule_text.md`;
- one catalogue title for `incapacity_proof`;
- the seven-day parenthetical (point 6);
- the 336(3) `not_this` (point 9);
- record that the illness fact will be held more often than the other period facts, and that silence can choose between two type 2 stops.

**Ready to be marked reviewed?** Not yet. It is ready as soon as the two wording changes above are made. Neither needs a new source or a structural change.
