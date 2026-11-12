# Rules: end of an employment relationship in Switzerland (dismissal)

These rules say which documents a legal-protection insurer requests before it
assesses an employee's dispute about the end of an employment relationship.
They come from the Swiss Code of Obligations (CO, SR 220), consolidated
version of 1 October 2026. The German text of the CO is authoritative; German
terms are given in brackets where the English translation is unclear.

There are three dispute types. Each type has a defining event, conditions to
decide, steps, documents, presumptions and stops. A document is needed when its
step is reached and its condition holds. Every needed document is mandatory.
When a stop applies, the process ends and no further document of that type is
needed.

A presumption fills a fact the file does not mention. Only the presumptions
listed below exist. Any other fact the file does not mention is unresolved: it
is neither true nor false, and a document whose need depends on it is held
until the fact is answered. No presumption applies to a fact the file raises
but leaves open.

## Type 1: Notice by the employer during a protected period (art. 336c)

After the probation period has expired, the employer may not give notice
during the protected periods of art. 336c para. 1 ("Sperrfristen"). Notice
given during such a period is void ("nichtig", art. 336c para. 2). Notice given
before such a period began, with the notice period still running when it
began, is suspended and resumes only after the period ends (art. 336c para. 2);
if a specific end-point applies, such as the end of a month, the resumed notice
period is extended to the next end-point (art. 336c para. 3).

Defining event: the employer gave the employee notice of termination.

### Conditions

1. `employer_gave_notice`: Did the employer give the employee notice of
   termination of the employment relationship? Not: a resignation by the
   employee, or a fixed-term relationship that ended by running out.
   (art. 336c para. 1)
2. `notice_after_probation`: Was the notice given after the probation period
   had expired? Not: notice given while the probation period was still
   running, even if the employee was ill, pregnant or in service at the time.
   (art. 336c para. 1)
3. `probation_varied`: Does the file say that a written individual agreement,
   a standard employment contract or a collective employment contract set a
   probation period other than the first month of employment? Not: an oral
   arrangement about probation, or a remark only that the employee was still
   new. (art. 335b para. 2)
4. `incapacity_illness_accident`: Was the employee, through no fault of their
   own, wholly or partly prevented from working by illness or accident on the
   day notice was given or while the notice period was still running? Not:
   incapacity the employee caused through their own fault, incapacity that
   ended before notice was given, or illness that began only after the notice
   period had ended. (art. 336c para. 1 let. b)
5. `compulsory_service`: Was the employee performing Swiss compulsory military
   service, civil defence service or alternative civilian service on the day
   notice was given or while the notice period was running, or, for such a
   service lasting more than eleven days, did either of those fall within the
   four weeks before or after it? Not: voluntary service, service in a foreign
   army, or a service of eleven days or less that did not overlap the notice
   day or the notice period. (art. 336c para. 1 let. a)
6. `pregnancy_or_birth`: Was the employee pregnant, or within sixteen weeks
   after giving birth, on the day notice was given or while the notice period
   was running? Not: pregnancy of the employee's partner; the further leave
   periods of art. 336c para. 1 let. cbis to cquinquies, which these rules do
   not cover. (art. 336c para. 1 let. c)
7. `notice_before_protected_period`: Was the notice given before the
   protected period began, with the notice period not yet expired when it
   began? Not: notice given on a day that already fell inside the protected
   period (that notice is void, not suspended). (art. 336c para. 2)
8. `notice_period_varied`: Does the file say that a written individual
   employment contract, a standard employment contract or a collective
   employment contract sets notice periods different from the statutory ones
   (one month in the first year of service, two months in the second to ninth
   years, three months thereafter)? Not: a notice period that only the
   termination letter states, with no written contract term behind it.
   (art. 335c para. 2)

### Stops

- If the employer gave no notice (`employer_gave_notice` is no), the process
  ends: art. 336c restrains only a termination by the employer.
- If the employer gave notice but not after the probation period had expired
  (`notice_after_probation` is no), the process ends: the protection of
  art. 336c para. 1 applies only after the probation period has expired.

### Steps and documents

1. Establish whether the employer gave notice (always).
2. Check that the probation period had expired when notice was given (when the
   employer gave notice).
3. Record the notice, the start of employment and the probation terms (when
   the employer gave notice after the probation period). Documents:
   - Notice of termination: issuer, addressee, date of the notice, date the
     employee received it, stated end of employment. Always. (art. 336c
     para. 2: whether the notice is void turns on the day it was given.)
   - Employment contract or other record of the start of employment: parties,
     start date, probation clause if any, notice-period clause if any. Always.
     (art. 335b para. 1: the probation period is the first month of the
     employment relationship, so it runs from the start date.)
   - Written probation clause (individual agreement, standard or collective
     contract): length of the probation period and the written instrument that
     sets it. Only when `probation_varied` is yes. (art. 335b para. 2)
4. Illness or accident (when `incapacity_illness_accident` is yes): Medical
   certificate of incapacity for work: cause (illness or accident), full or
   partial incapacity, first and last day, date issued. (art. 336c para. 1
   let. b)
5. Compulsory service (when `compulsory_service` is yes): Official
   confirmation of compulsory service: kind of service, first and last day.
   (art. 336c para. 1 let. a)
6. Pregnancy or birth (when `pregnancy_or_birth` is yes): Medical confirmation
   of pregnancy or record of the birth: the pregnancy and its dates, or the
   date of birth. (art. 336c para. 1 let. c)
7. Then one of two branches:
   - when `notice_before_protected_period` is yes: compute the suspended and
     extended notice period (art. 336c para. 2 and 3). Document: Written
     notice-period clause (individual, standard or collective contract):
     length of the notice period, its end-point, the written instrument that
     sets it. Only when `notice_period_varied` is yes. (art. 336c para. 3)
   - when `notice_before_protected_period` is no: check whether the notice
     fell inside a protected period and is void (art. 336c para. 2). No
     document.
8. Both branches end in one assessment of the effect of the notice (void,
   suspended or valid).

Steps 4, 5 and 6 are each taken or skipped on their own; all of them lead on
to step 7.

### Presumptions

- `probation_varied` not mentioned: taken as no. Art. 335b para. 1: "the
  probation period is considered to be the first month of an employment
  relationship" ("als Probezeit gilt der erste Monat"); other terms require a
  written agreement or a standard or collective contract (para. 2).
- `notice_period_varied` not mentioned: taken as no. Art. 335c para. 1 fixes
  the notice periods (one, two or three months by years of service, to the end
  of a month); para. 2 allows others only by written contract.

## Type 2: Wrongful (abusive) notice by the employer (arts. 336 to 336b)

Notice is wrongful ("missbräuchlich"; the English translation says
"unlawful") when given for one of the reasons in art. 336. The party who gave
wrongful notice owes compensation, set by the court and capped at six months'
salary (art. 336a para. 2). To claim it, the employee must object to the
notice in writing to the employer no later than the end of the notice period
(art. 336b para. 1), and must bring the claim before a court within 180 days of
the end of the employment relationship; otherwise the claim is lost
("verwirkt", forfeited; the English translation says "prescribes", art. 336b
para. 2). The party giving notice must state the reasons in writing if the
other party asks (art. 335 para. 2).

Defining event: the employer gave the employee notice of termination.

### Conditions

1. `employer_gave_notice`: Did the employer give the employee notice of
   termination of the employment relationship? Not: a resignation by the
   employee, or a fixed-term relationship that ended by running out.
   (art. 336b para. 2)
2. `notice_period_ended`: Has the notice period (from the notice to the end of
   the employment relationship) already ended? Not: the employee's last
   working day where they were released from work while the notice period was
   still running. (art. 336b para. 1)
3. `objection_submitted`: Did the employee send the employer a written
   objection to the notice before the notice period ended? Not: an oral
   protest, or a written objection sent only after the notice period had
   ended. (art. 336b para. 1)
4. `more_than_180_days`: Have more than 180 days passed since the employment
   relationship ended? Not: 180 days counted from the notice or from the last
   day actually worked rather than from the end of the employment
   relationship. (art. 336b para. 2)
5. `action_in_time`: Did the employee bring the compensation claim before a
   court within 180 days of the end of the employment relationship? Not: a
   demand letter to the employer, or a court claim filed only after the 180
   days. (art. 336b para. 2)
6. `reasons_requested`: Did the employee ask the employer to state the reasons
   for the notice in writing? Not: reasons the employer gave without being
   asked, or a request made only orally to a colleague rather than to the
   employer. (art. 335 para. 2)
7. `retaliation_for_claims`: Does the employee say the notice was given
   because they had asserted, in good faith, claims arising from the
   employment relationship? Not: complaints that are not claims under the
   employment relationship, or a mere coincidence in time that the employee
   does not link to the notice. (art. 336 para. 1 let. d)
8. `employee_representative`: Was the employee, when notice was given, an
   elected employee representative on the staff council of the business or on
   a body linked to the business? Not: trade-union membership or union
   activity without an elected mandate (art. 336 para. 2 let. a, not covered
   here). (art. 336 para. 2 let. b)

### Stops

- If the employer gave no notice (`employer_gave_notice` is no), the process
  ends: only the party on whom notice was served may bring the compensation
  claim (art. 336b para. 2).
- If the notice period has ended (`notice_period_ended` is yes) and the
  employee did not send a written objection before it ended
  (`objection_submitted` is no), the process ends: compensation requires that
  objection (art. 336b para. 1).
- If more than 180 days have passed since the employment ended
  (`more_than_180_days` is yes) and no court claim was brought within them
  (`action_in_time` is no), the process ends: the claim is lost (art. 336b
  para. 2).

The stops are checked in this order.

### Steps and documents

1. Establish whether the employer gave notice (always).
2. Check whether the objection window has closed without a written objection
   (when the employer gave notice).
3. Check the 180-day time limit for the court claim (when the employer gave
   notice and the objection stop does not apply).
4. Record the notice, the notice period, the objection and any court claim
   (when no stop applies). Documents:
   - Notice of termination: issuer, addressee, date of the notice, stated end
     of employment. Always. (art. 336b para. 1: the objection window ends with
     the notice period.)
   - Employment contract or other record of the start of employment: parties,
     start date, notice-period clause if any. Always. (art. 335c para. 1: the
     notice period depends on the years of service and any written variation.)
   - Copy of the written objection with proof of when it was sent: the
     objection, addressed to the employer, date sent or received, proof of
     sending or receipt. Only when `objection_submitted` is yes. (art. 336b
     para. 1)
   - Copy of the court claim with its filing date: court, compensation claim,
     filing date. Only when `action_in_time` is yes. (art. 336b para. 2)
5. Establish the reason the employer gave for the notice (art. 336 para. 1).
   Document: Employer's written statement of reasons: the reasons, the date.
   Only when `reasons_requested` is yes. (art. 335 para. 2)
6. Retaliation for asserting claims (when `retaliation_for_claims` is yes):
   Correspondence in which the employee asserted claims before the notice:
   the claims, dates before the notice, the employer's response if any.
   (art. 336 para. 1 let. d)
7. Elected employee representative (when `employee_representative` is yes):
   Proof of election as employee representative: the body, the election, a
   term of mandate covering the notice date. (art. 336 para. 2 let. b)
8. Assess the compensation claim (when no stop applies). Document: Salary
   statements (pay slips): monthly salary, period covered. Always. (art. 336a
   para. 2: compensation is capped at six months' salary.)

Steps 6 and 7 are each taken or skipped on their own; all of them lead on to
step 8.

### Presumptions

None. No fact of this type is presumed.

## Type 3: Dismissal with immediate effect by the employer (arts. 337 and 337c)

Either party may end the employment relationship with immediate effect at any
time for good cause ("wichtige Gründe") and must give the reasons in writing if
the other party asks (art. 337 para. 1). Good cause is any circumstance that
makes continuing the relationship in good faith unconscionable for the party
giving notice (art. 337 para. 2). Being prevented from working through no
fault of one's own is never good cause (art. 337 para. 3). Where the employer
dismisses with immediate effect without good cause, the employee is entitled
to what they would have earned had the relationship ended after the required
notice period or at the end of its agreed term (art. 337c para. 1), reduced by
what they saved or earned from other work (art. 337c para. 2); the court may
add compensation of up to six months' salary (art. 337c para. 3).

Defining event: the employer dismissed the employee with immediate effect.

### Conditions

1. `dismissed_immediately`: Did the employer end the employment relationship
   with immediate effect, without a notice period? Not: ordinary notice with a
   notice period, however short, or release from work while a notice period
   runs. (art. 337c para. 1)
2. `reasons_requested`: Did the employee ask the employer to state the reasons
   for the immediate dismissal in writing? Not: reasons the employer gave
   without being asked. (art. 337 para. 1)
3. `incapacity_cause`: Does the employer give as the cause of the dismissal
   the employee's absence from work, and does the employee say the absence was
   due to illness or accident through no fault of their own? Not: a dismissal
   for conduct at work, or an absence the employee does not attribute to
   illness or accident. (art. 337 para. 3)
4. `fixed_term`: Was the employment relationship agreed for a fixed term, with
   an agreed end date, rather than for an unlimited period? Not: an
   open-ended contract that only states a probation period or a notice period.
   (art. 337c para. 1)
5. `notice_period_varied`: Does the file say that a written individual
   employment contract, a standard employment contract or a collective
   employment contract sets notice periods different from the statutory ones
   (one month in the first year of service, two months in the second to ninth
   years, three months thereafter)? Not: a notice period that only the
   termination letter states, with no written contract term behind it.
   (art. 335c para. 2)
6. `other_earnings`: Has the employee earned income from other work during
   the time the notice period or the agreed term would still have run? Not:
   unemployment benefits or other payments that are not earnings from work.
   (art. 337c para. 2)

### Stops

- If the employer did not dismiss with immediate effect
  (`dismissed_immediately` is no), the process ends: the entitlement of
  art. 337c para. 1 arises only from such a dismissal.

### Steps and documents

1. Establish whether the employer dismissed with immediate effect (always).
2. Record the dismissal, the contract and the salary (when the employer
   dismissed with immediate effect). Documents, always:
   - Letter or message dismissing with immediate effect: issuer, addressee,
     date, that employment ends with immediate effect. (art. 337c para. 1)
   - Employment contract or other record of its terms: parties, start date,
     agreed end date if fixed-term, notice-period clause if any. (art. 337c
     para. 1: damages run to the end of the notice period or the agreed term.)
   - Salary statements (pay slips): monthly salary, period covered. (art. 337c
     para. 1: damages equal what the employee would have earned.)
3. Establish the cause the employer relies on (art. 337 para. 2). Documents:
   - Employer's written statement of reasons: the reasons, the date. Only
     when `reasons_requested` is yes. (art. 337 para. 1)
   - Medical certificate of incapacity for work: cause (illness or accident),
     full or partial incapacity, first and last day, date issued. Only when
     `incapacity_cause` is yes. (art. 337 para. 3)
4. Then one of two branches:
   - when `fixed_term` is yes: measure damages to the agreed end of the fixed
     term (art. 337c para. 1). No further document.
   - when `fixed_term` is no: measure damages to the end of the required
     notice period (art. 337c para. 1). Document: Written notice-period clause
     (individual, standard or collective contract): length of the notice
     period, its end-point, the written instrument that sets it. Only when
     `notice_period_varied` is yes. (art. 335c para. 2)
5. Both branches end in the assessment of damages and compensation (art. 337c
   para. 3). Document: Proof of earnings from other work since the dismissal:
   employer or client, period, amounts earned. Only when `other_earnings` is
   yes. (art. 337c para. 2)

### Presumptions

- `notice_period_varied` not mentioned: taken as no. Art. 335c para. 1 fixes
  the notice periods (one, two or three months by years of service, to the end
  of a month); para. 2 allows others only by written contract.
