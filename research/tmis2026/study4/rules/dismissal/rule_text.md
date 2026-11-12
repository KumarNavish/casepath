# Rules: end of an employment relationship in Switzerland (dismissal)

These rules say which documents a legal-protection insurer requests before it assesses an employee's dispute about the end of an employment relationship. They come from the Swiss Code of Obligations (CO, SR 220), consolidated version of 1 October 2026. The German text of the CO is authoritative; German terms are given in brackets where the English translation is unclear.

There are three dispute types. Each type has a defining event, conditions to decide, steps, documents, presumptions and stops. A step is taken when its condition holds. A document is needed when its step is taken and its own condition holds; every needed document is mandatory. When a stop applies, the process ends and no further step of that type is taken. A presumption fills a fact the file does not mention; a statutory presumption listed under a type comes before the convention below.

## Convention of this benchmark (not law)

The following rule is a convention of this benchmark, not of the law; no article states it:

> A fact that the file does not mention is taken as not alleged, and the rules are applied as if it were absent. Silence never ends a process: where a fact's absence would end it, the unmentioned fact is unresolved. The defining event is never presumed: if the file does not mention it, it is unresolved. A fact that the file raises and leaves unsettled is open.

## Type 1: Notice of termination by the employer during a protected period (CO art. 336c)

After the probation period has expired, the employer may not give notice during the protected periods of art. 336c para. 1 ("Sperrfristen"). Notice given during such a period is void ("nichtig", art. 336c para. 2). Notice given before such a period began, with the notice period still running when it began, is suspended and resumes only after the period ends (art. 336c para. 2); if a specific end-point applies, such as the end of a month, the resumed notice period is extended to the next end-point (art. 336c para. 3).

Defining event: `employer_gave_notice`. It is never presumed.

### Conditions

1. `employer_gave_notice`: Did the employer give the employee notice of termination of the employment relationship? Not: A resignation by the employee, or a fixed-term relationship that ended by running out. (art. 336c para. 1, introduction)
2. `notice_during_probation`: Was the notice given while the probation period was still running? Not: Notice given after the probation period had expired, even shortly after it. (art. 336c para. 1, introduction)
3. `probation_varied`: Does the file say that a written individual agreement, a standard employment contract or a collective employment contract set a probation period other than the first month of employment? Not: An oral arrangement about probation, or a remark only that the employee was still new. (art. 335b para. 2)
4. `incapacity_illness_accident`: Was the employee, through no fault of their own, wholly or partly prevented from working by illness or accident on the day notice was given or while the notice period was still running? Not: Incapacity the employee caused through their own fault, incapacity that ended before notice was given, or illness that began only after the notice period had ended. (art. 336c para. 1 let. b)
5. `compulsory_service`: Was the employee performing Swiss compulsory military service, civil defence service or alternative civilian service on the day notice was given or while the notice period was running, or, for such a service lasting more than eleven days, did either of those fall within the four weeks before or after it? Not: Voluntary service, service in a foreign army, or a service of eleven days or less that did not overlap the notice day or the notice period. (art. 336c para. 1 let. a)
6. `pregnancy_or_birth`: Was the employee pregnant, or within sixteen weeks after giving birth, on the day notice was given or while the notice period was running? Not: Pregnancy of the employee's partner; the further leave periods of art. 336c para. 1 let. cbis to cquinquies, which this rule set does not cover. (art. 336c para. 1 let. c)
7. `notice_before_protected_period`: Was the notice given before the protected period began, with the notice period not yet expired when it began? Not: Notice given on a day that already fell inside the protected period (that notice is void, not suspended). (art. 336c para. 2) Always stated in the file (stated or open, never left unmentioned).
8. `notice_period_varied`: Does the file say that a written individual employment contract, a standard employment contract or a collective employment contract sets notice periods different from the statutory ones (one month in the first year of service, two months in the second to ninth years, three months thereafter)? Not: A notice period that only the termination letter states, with no written contract term behind it. (art. 335c para. 2)

### Stops

- If `employer_gave_notice` is no, the process ends. The provision restrains only a termination by the employer; where the employer gave no notice there is nothing it can make void or suspend, so this process ends. (art. 336c para. 1, introduction)
- If `employer_gave_notice` is yes and `notice_during_probation` is yes, the process ends. The bar applies only after the probation period has expired; notice given during probation is outside it, so this process ends. (art. 336c para. 1, introduction)

### Steps and documents

1. Establish whether the employer gave notice. Taken when: always. (art. 336c para. 1, introduction)
2. Check that the probation period had expired when notice was given. Taken when: `employer_gave_notice` is yes. (art. 336c para. 1, introduction)
3. Record the notice, the start of employment and the probation terms. Taken when: `employer_gave_notice` is yes and `notice_during_probation` is no. (art. 336c para. 2)
   - Notice of termination, showing: issuer; addressee; date of the notice; date the employee received it; stated end of employment. Needed always. (art. 336c para. 2: Voidness turns on the day the notice was given compared with the protected period; the notice and its date of receipt are the ordinary record of that day.)
   - Employment contract or other record of the start of employment, showing: parties; start date of employment; probation clause, if any; notice-period clause, if any. Needed always. (art. 335b para. 1: The probation period, and with it the start of the protection, runs from the start of employment; the contract or another record of the start date ordinarily shows it.)
   - Written probation clause (individual agreement, standard or collective contract), showing: length of the probation period; the written instrument that sets it. Needed only when `probation_varied` is yes. (art. 335b para. 2: A probation period other than the first month exists only under a written agreement or a standard or collective contract; that written clause proves its length and so whether notice came after it.)
4. Examine the illness or accident protected period. Taken when: `employer_gave_notice` is yes and `notice_during_probation` is no and `incapacity_illness_accident` is yes. (art. 336c para. 1 let. b)
   - Medical certificate of incapacity for work, showing: cause (illness or accident); full or partial incapacity; first and last day of incapacity; date issued. Needed always. (art. 336c para. 1 let. b: The bar applies only while the employee is prevented from working by illness or accident; a medical certificate is the ordinary proof of that incapacity and its dates, to compare with the notice.)
5. Examine the compulsory-service protected period. Taken when: `employer_gave_notice` is yes and `notice_during_probation` is no and `compulsory_service` is yes. (art. 336c para. 1 let. a)
   - Official confirmation of compulsory service, showing: kind of service (military, civil defence, alternative civilian); first and last day of service. Needed always. (art. 336c para. 1 let. a: The bar depends on the kind of service, its dates and whether it lasted more than eleven days; the official service order or confirmation ordinarily shows all three.)
6. Examine the pregnancy and maternity protected period. Taken when: `employer_gave_notice` is yes and `notice_during_probation` is no and `pregnancy_or_birth` is yes. (art. 336c para. 1 let. c)
   - Medical confirmation of pregnancy or record of the birth, showing: pregnancy confirmed and its dates, or the date of birth. Needed always. (art. 336c para. 1 let. c: The bar runs during pregnancy and sixteen weeks after the birth; a medical confirmation of the pregnancy or the birth record ordinarily dates that period.)
7. Compute the suspended and extended notice period. Taken when: `employer_gave_notice` is yes and `notice_during_probation` is no and (`incapacity_illness_accident` is yes or `compulsory_service` is yes or `pregnancy_or_birth` is yes) and `notice_before_protected_period` is yes. (art. 336c para. 2)
   - Written notice-period clause (individual, standard or collective contract), showing: notice period length; end-point of the notice (e.g. end of a month); the written instrument that sets it (individual, standard or collective contract). Needed only when `notice_period_varied` is yes. (art. 336c para. 3: Resuming and extending a suspended notice period needs its length and end-point; where a written contract varies the statutory periods, that clause is the ordinary proof of them.)
8. Check whether the notice fell inside a protected period and is void. Taken when: `employer_gave_notice` is yes and `notice_during_probation` is no and (`incapacity_illness_accident` is yes or `compulsory_service` is yes or `pregnancy_or_birth` is yes) and `notice_before_protected_period` is no. (art. 336c para. 2)
9. Assess the effect of the notice (void, suspended or valid). Taken when: `employer_gave_notice` is yes and `notice_during_probation` is no. (art. 336c para. 2)

### Presumptions

- `probation_varied` not mentioned: taken as no. art. 335b para. 1: “the probation period is considered to be the first month of an employment relationship” („als Probezeit gilt der erste Monat eines Arbeitsverhältnisses“). The statute deems the probation period to be the first month and paragraph 2 allows other terms only in writing, so where the file states no such written term the first month applies.
- `notice_period_varied` not mentioned: taken as no. art. 335c para. 1: “The employment relationship may be terminated at one month’s notice during the first year of service, at two months’ notice in the second to ninth years of service and at three months’ notice thereafter, all such notice to expire at the end of a calendar month”. Paragraph 1 fixes the notice periods by law and paragraph 2 lets them differ only by a written individual, standard or collective contract, so where the file states no such written term the statutory periods apply.
- Under the convention of this benchmark (not law), not mentioned means taken as no: `notice_during_probation`, `incapacity_illness_accident`, `compulsory_service`, `pregnancy_or_birth`.
- No presumption; always stated in the file: `notice_before_protected_period`.
- The defining event `employer_gave_notice` is never presumed.

## Type 2: Wrongful (abusive) notice of termination by the employer: objection and compensation claim (CO arts. 336-336b)

Notice is wrongful ("missbräuchlich"; the English translation says "unlawful") when given for one of the reasons in art. 336. The party who gave wrongful notice owes compensation, set by the court and capped at six months' salary (art. 336a para. 2). To claim it, the employee must object to the notice in writing to the employer no later than the end of the notice period (art. 336b para. 1), and must bring the claim before a court within 180 days of the end of the employment relationship; otherwise the claim is lost ("verwirkt", forfeited; the English translation says "prescribes", art. 336b para. 2). The party giving notice must state the reasons in writing if the other party asks (art. 335 para. 2).

Defining event: `employer_gave_notice`. It is never presumed.

### Conditions

1. `employer_gave_notice`: Did the employer give the employee notice of termination of the employment relationship? Not: A resignation by the employee, or a fixed-term relationship that ended by running out. (art. 336b para. 2)
2. `notice_period_ended`: Has the notice period (from the notice to the end of the employment relationship) already ended? Not: The employee's last working day where they were released from work while the notice period was still running. (art. 336b para. 1) Always stated in the file (stated or open, never left unmentioned).
3. `objection_submitted`: Did the employee send the employer a written objection to the notice before the notice period ended? Not: An oral protest, or a written objection sent only after the notice period had ended. (art. 336b para. 1)
4. `more_than_180_days`: Have more than 180 days passed since the employment relationship ended? Not: 180 days counted from the notice or from the last day actually worked rather than from the end of the employment relationship. (art. 336b para. 2) Always stated in the file (stated or open, never left unmentioned).
5. `action_in_time`: Did the employee bring the compensation claim before a court within 180 days of the end of the employment relationship? Not: A demand letter to the employer, or a court claim filed only after the 180 days. (art. 336b para. 2)
6. `reasons_requested`: Did the employee ask the employer to state the reasons for the notice in writing? Not: Reasons the employer gave without being asked, or a request made only orally to a colleague rather than to the employer. (art. 335 para. 2)
7. `retaliation_for_claims`: Does the employee say the notice was given because they had asserted, in good faith, claims arising from the employment relationship? Not: Complaints that are not claims under the employment relationship, or a mere coincidence in time that the employee does not link to the notice. (art. 336 para. 1 let. d)
8. `employee_representative`: Was the employee, when notice was given, an elected employee representative on the staff council of the business or on a body linked to the business? Not: Trade-union membership or union activity without an elected mandate (art. 336 para. 2 let. a, not covered here). (art. 336 para. 2 let. b)

### Stops

- If `employer_gave_notice` is no, the process ends. Only the party on whom notice was served may bring the compensation claim; where the employer gave no notice there is no such claim, so this process ends. (art. 336b para. 2)
- If `employer_gave_notice` is yes and (`notice_period_ended` is yes and `objection_submitted` is no), the process ends. Compensation under arts. 336 and 336a requires a written objection before the notice period ends; once the period has ended without one, the claim cannot be brought, so this process ends. (art. 336b para. 1)
- If `employer_gave_notice` is yes and not (`notice_period_ended` is yes and `objection_submitted` is no) and (`more_than_180_days` is yes and `action_in_time` is no), the process ends. “The claim prescribes if not brought before the courts within 180 days of the end of the employment relationship.” (art. 336b para. 2)

### Steps and documents

1. Establish whether the employer gave notice. Taken when: always. (art. 336b para. 2)
2. Check whether the objection window has closed without a written objection. Taken when: `employer_gave_notice` is yes. (art. 336b para. 1)
3. Check the 180-day time limit for the court claim. Taken when: `employer_gave_notice` is yes and not (`notice_period_ended` is yes and `objection_submitted` is no). (art. 336b para. 2)
4. Record the notice, the notice period, the objection and any court claim. Taken when: `employer_gave_notice` is yes and not (`notice_period_ended` is yes and `objection_submitted` is no) and not (`more_than_180_days` is yes and `action_in_time` is no). (art. 336b para. 1)
   - Notice of termination, showing: issuer; addressee; date of the notice; stated end of employment. Needed always. (art. 336b para. 1: The objection must be made before the end of the notice period; the notice ordinarily shows when it was given and when the employment ends, which fixes that window and the start of the 180 days.)
   - Employment contract or other record of the start of employment, showing: parties; start date of employment; notice-period clause, if any. Needed always. (art. 335c para. 1: The end of the notice period, which closes the objection window, depends on the years of service and on any written variation; the contract ordinarily shows the start date and any such clause.)
   - Copy of the written objection with proof of when it was sent, showing: objection to the notice; addressed to the employer; date sent or received; proof of sending or receipt. Needed only when `objection_submitted` is yes. (art. 336b para. 1: The claim requires a written objection to the employer before the notice period ends; a copy of the objection with proof of its date is the ordinary proof of both.)
   - Copy of the court claim with its filing date, showing: court; compensation claim; filing date. Needed only when `action_in_time` is yes. (art. 336b para. 2: The claim is lost unless brought before a court within 180 days of the end of employment; the filed claim with its filing date is the ordinary proof that it was brought in time.)
5. Establish the reason the employer gave for the notice. Taken when: `employer_gave_notice` is yes and not (`notice_period_ended` is yes and `objection_submitted` is no) and not (`more_than_180_days` is yes and `action_in_time` is no). (art. 336 para. 1, introduction)
   - Employer's written statement of reasons, showing: reasons stated by the employer; date. Needed only when `reasons_requested` is yes. (art. 335 para. 2: Where the employee asked, the employer must give its reasons in writing; that statement is the ordinary record of the reason on which art. 336 makes wrongfulness depend.)
6. Examine the claimed retaliation for asserting claims. Taken when: (`employer_gave_notice` is yes and not (`notice_period_ended` is yes and `objection_submitted` is no) and not (`more_than_180_days` is yes and `action_in_time` is no)) and `retaliation_for_claims` is yes. (art. 336 para. 1 let. d)
   - Correspondence in which the employee asserted claims before the notice, showing: claims asserted under the employment relationship; dates before the notice; employer's response, if any. Needed always. (art. 336 para. 1 let. d: This ground turns on claims asserted before the notice; the correspondence in which the employee raised them is the ordinary record of what was claimed and when.)
7. Examine the protection of an elected employee representative. Taken when: (`employer_gave_notice` is yes and not (`notice_period_ended` is yes and `objection_submitted` is no) and not (`more_than_180_days` is yes and `action_in_time` is no)) and `employee_representative` is yes. (art. 336 para. 2 let. b)
   - Proof of election as employee representative, showing: body (staff council or body linked to the business); election; term of the mandate covering the notice date. Needed always. (art. 336 para. 2 let. b: The protection applies while the employee is an elected representative; the election record or mandate confirmation ordinarily shows the body and the term.)
8. Assess the compensation claim. Taken when: `employer_gave_notice` is yes and not (`notice_period_ended` is yes and `objection_submitted` is no) and not (`more_than_180_days` is yes and `action_in_time` is no). (art. 336a para. 2)
   - Salary statements (pay slips), showing: monthly salary; period covered. Needed always. (art. 336a para. 2: Compensation is capped at six months' salary; pay slips are the ordinary proof of the salary that sets the cap.)

### Presumptions

- Under the convention of this benchmark (not law), not mentioned means taken as no: `reasons_requested`, `retaliation_for_claims`, `employee_representative`.
- Not mentioned leaves the fact unresolved, because its absence would end the process: `action_in_time`, `objection_submitted`.
- No presumption; always stated in the file: `notice_period_ended`, `more_than_180_days`.
- The defining event `employer_gave_notice` is never presumed.

## Type 3: Dismissal with immediate effect by the employer (CO arts. 337, 337c)

Either party may end the employment relationship with immediate effect at any time for good cause ("wichtige Gründe") and must give the reasons in writing if the other party asks (art. 337 para. 1). Good cause is any circumstance that makes continuing the relationship in good faith unconscionable for the party giving notice (art. 337 para. 2). Being prevented from working through no fault of one's own is never good cause (art. 337 para. 3). Where the employer dismisses with immediate effect without good cause, the employee is entitled to what they would have earned had the relationship ended after the required notice period or at the end of its agreed term (art. 337c para. 1), reduced by what they saved or earned from other work (art. 337c para. 2); the court may add compensation of up to six months' salary (art. 337c para. 3).

Defining event: `dismissed_immediately`. It is never presumed.

### Conditions

1. `dismissed_immediately`: Did the employer end the employment relationship with immediate effect, without a notice period? Not: Ordinary notice with a notice period, however short, or release from work while a notice period runs. (art. 337c para. 1)
2. `reasons_requested`: Did the employee ask the employer to state the reasons for the immediate dismissal in writing? Not: Reasons the employer gave without being asked. (art. 337 para. 1)
3. `incapacity_cause`: Does the employer give as the cause of the dismissal the employee's absence from work, and does the employee say the absence was due to illness or accident through no fault of their own? Not: A dismissal for conduct at work, or an absence the employee does not attribute to illness or accident. (art. 337 para. 3)
4. `fixed_term`: Was the employment relationship agreed for a fixed term, with an agreed end date, rather than for an unlimited period? Not: An open-ended contract that only states a probation period or a notice period. (art. 337c para. 1)
5. `notice_period_varied`: Does the file say that a written individual employment contract, a standard employment contract or a collective employment contract sets notice periods different from the statutory ones (one month in the first year of service, two months in the second to ninth years, three months thereafter)? Not: A notice period that only the termination letter states, with no written contract term behind it. (art. 335c para. 2)
6. `other_earnings`: Has the employee earned income from other work during the time the notice period or the agreed term would still have run? Not: Unemployment benefits or other payments that are not earnings from work. (art. 337c para. 2)

### Stops

- If `dismissed_immediately` is no, the process ends. The entitlement arises only where the employer dismisses with immediate effect; without such a dismissal this process has nothing to assess, so it ends. (art. 337c para. 1)

### Steps and documents

1. Establish whether the employer dismissed with immediate effect. Taken when: always. (art. 337c para. 1)
2. Record the dismissal, the contract and the salary. Taken when: `dismissed_immediately` is yes. (art. 337c para. 1)
   - Letter or message dismissing with immediate effect, showing: issuer; addressee; date; that employment ends with immediate effect. Needed always. (art. 337c para. 1: The entitlement arises from a dismissal with immediate effect; the dismissal letter or message is the ordinary record that it was immediate and of its date.)
   - Employment contract or other record of its terms, showing: parties; start date of employment; agreed end date, if fixed-term; notice-period clause, if any. Needed always. (art. 337c para. 1: Damages run to the end of the required notice period or of the agreed term; the contract ordinarily shows the start date, any agreed end date and any notice clause.)
   - Salary statements (pay slips), showing: monthly salary; period covered. Needed always. (art. 337c para. 1: Damages equal what the employee would have earned; pay slips are the ordinary proof of those earnings (and of the salary that caps compensation under para. 3).)
3. Establish the cause the employer relies on. Taken when: `dismissed_immediately` is yes. (art. 337 para. 2)
   - Employer's written statement of reasons, showing: reasons stated by the employer; date. Needed only when `reasons_requested` is yes. (art. 337 para. 1: Where the employee asked, the employer must give its reasons in writing; that statement is the ordinary record of the cause it relies on.)
   - Medical certificate of incapacity for work, showing: cause (illness or accident); full or partial incapacity; first and last day of incapacity; date issued. Needed only when `incapacity_cause` is yes. (art. 337 para. 3: Being prevented from working through no fault of one's own can never be good cause; a medical certificate is the ordinary proof that an absence was due to illness or accident and of its dates.)
4. Measure damages to the agreed end of the fixed term. Taken when: `dismissed_immediately` is yes and `fixed_term` is yes. (art. 337c para. 1)
5. Measure damages to the end of the required notice period. Taken when: `dismissed_immediately` is yes and `fixed_term` is no. (art. 337c para. 1)
   - Written notice-period clause (individual, standard or collective contract), showing: notice period length; end-point of the notice (e.g. end of a month); the written instrument that sets it (individual, standard or collective contract). Needed only when `notice_period_varied` is yes. (art. 335c para. 2: Damages run to the end of the required notice period; where a written contract varies the statutory periods, that clause is the ordinary proof of the period that applies.)
6. Assess damages and compensation. Taken when: `dismissed_immediately` is yes. (art. 337c para. 3)
   - Proof of earnings from other work since the dismissal, showing: employer or client; period; amounts earned. Needed only when `other_earnings` is yes. (art. 337c para. 2: Damages are reduced by what the employee earned from other work; pay slips or contracts for that work are the ordinary proof of the amounts and period.)

### Presumptions

- `notice_period_varied` not mentioned: taken as no. art. 335c para. 1: “The employment relationship may be terminated at one month’s notice during the first year of service, at two months’ notice in the second to ninth years of service and at three months’ notice thereafter, all such notice to expire at the end of a calendar month”. Paragraph 1 fixes the notice periods by law and paragraph 2 lets them differ only by a written individual, standard or collective contract, so where the file states no such written term the statutory periods apply.
- Under the convention of this benchmark (not law), not mentioned means taken as no: `reasons_requested`, `incapacity_cause`, `fixed_term`, `other_earnings`.
- The defining event `dismissed_immediately` is never presumed.
