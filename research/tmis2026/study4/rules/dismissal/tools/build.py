"""Build rules.json, RULES.md and workflow/*.json for the dismissal regime.

Run from anywhere: `python3 -I tools/build.py`. The rule set is written here
once, as data; every output is generated from it so the three forms cannot
drift. Every passage is checked against the snapshots by tools/check.py.
"""
import json
from pathlib import Path

REGIME_DIR = Path(__file__).resolve().parent.parent
EN, DE = "co-sr220-en", "co-sr220-de"
VERSION = "2026-11-12.3"


def R(locator, passage, basis, inference=None, de=None):
    rule = {"source_id": EN, "locator": locator, "passage": passage, "basis": basis}
    if inference:
        rule["inference"] = inference
    if de:
        rule["passage_de"] = {"source_id": DE, "passage": de}
    return rule


def T(f):
    return {"fact": f, "is": True}


def F(f):
    return {"fact": f, "is": False}


def ALL(*c):
    return {"all": list(c)}


def NOT(c):
    return {"not": c}


# ---------------------------------------------------------------- passages used more than once
P_336C_INTRO = "After the probation period has expired, the employer may not terminate the employment relationship"
D_336C_INTRO = "Nach Ablauf der Probezeit darf der Arbeitgeber das Arbeitsverhältnis nicht kündigen"
P_336C_1B = "while the employee through no fault of his own is partially or entirely prevented from working by illness or accident"
D_336C_1B = "während der Arbeitnehmer ohne eigenes Verschulden durch Krankheit oder durch Unfall ganz oder teilweise an der Arbeitsleistung verhindert ist"
P_336C_1A = ("while the other party is performing Swiss compulsory military or civil defence service or Swiss alternative civilian "
             "service or, where such service lasts for more than eleven days, during the four weeks preceding or following it")
D_336C_1A = ("während die andere Partei schweizerischen obligatorischen Militär- oder Schutzdienst oder schweizerischen Zivildienst "
             "leistet, sowie, sofern die Dienstleistung mehr als elf Tage dauert, während vier Wochen vorher und nachher")
P_336C_1C = "during the pregnancy of an employee and the sixteen weeks following birth"
D_336C_1C = "während der Schwangerschaft und in den 16 Wochen nach der Niederkunft einer Arbeitnehmerin"
P_336C_2_VOID = "Any notice of termination given during the proscribed periods stipulated in paragraph 1 is void"
D_336C_2_VOID = "Die Kündigung, die während einer der in Absatz 1 festgesetzten Sperrfristen erklärt wird, ist nichtig"
P_336C_2_SUSP = ("where such notice was given prior to the commencement of a proscribed period but the notice period has not yet "
                 "expired at that juncture, it is suspended and does not resume until the proscribed period has ended")
D_336C_2_SUSP = ("ist dagegen die Kündigung vor Beginn einer solchen Frist erfolgt, aber die Kündigungsfrist bis dahin noch nicht "
                 "abgelaufen, so wird deren Ablauf unterbrochen und erst nach Beendigung der Sperrfrist fortgesetzt")
P_336C_3 = ("Where a specific end-point, such as the end of a month or working week, has been set for termination of the employment "
            "relationship and such end-point does not coincide with the expiry of the resumed notice period, the latter is extended "
            "until the next applicable end-point.")
P_335B_1 = "the probation period is considered to be the first month of an employment relationship"
D_335B_1 = "als Probezeit gilt der erste Monat eines Arbeitsverhältnisses"
P_335B_2 = ("Different terms may be envisaged by an individual written agreement, a standard employment contract or a collective "
            "employment contract; however, the probation period may not exceed three months.")
D_335B_2 = ("Durch schriftliche Abrede, Normalarbeitsvertrag oder Gesamtarbeitsvertrag können abweichende Vereinbarungen getroffen "
            "werden; die Probezeit darf jedoch auf höchstens drei Monate verlängert werden.")
P_335C_1 = ("The employment relationship may be terminated at one month’s notice during the first year of service, at two months’ "
            "notice in the second to ninth years of service and at three months’ notice thereafter, all such notice to expire at "
            "the end of a calendar month.")
P_335C_2 = "These notice periods may be varied by written individual, standard or collective employment contract"
D_335C_2 = "Diese Fristen dürfen durch schriftliche Abrede, Normalarbeitsvertrag oder Gesamtarbeitsvertrag abgeändert werden"
P_335_2 = "The party giving notice of termination must state his reasons in writing if the other party so requests."
D_335_2 = "Der Kündigende muss die Kündigung schriftlich begründen, wenn die andere Partei dies verlangt."
P_336B_1 = ("A party seeking compensation pursuant to Articles 336 and 336a must submit his objection to the notice of termination "
            "in writing to the party giving such notice not later than the end of the notice period.")
D_336B_1 = ("Wer gestützt auf Artikel 336 und 336a eine Entschädigung geltend machen will, muss gegen die Kündigung längstens bis "
            "zum Ende der Kündigungsfrist beim Kündigenden schriftlich Einsprache erheben.")
P_336B_2_CLAIM = "the party on whom notice was served may bring his claim for compensation"
D_336B_2_CLAIM = "so kann die Partei, der gekündigt worden ist, ihren Anspruch auf Entschädigung geltend machen"
P_336B_2_180 = "The claim prescribes if not brought before the courts within 180 days of the end of the employment relationship."
D_336B_2_180 = "Wird nicht innert 180 Tagen nach Beendigung des Arbeitsverhältnisses eine Klage anhängig gemacht, ist der Anspruch verwirkt."
P_336_1D = "because the other party asserts claims under the employment relationship in good faith"
D_336_1D = "weil die andere Partei nach Treu und Glauben Ansprüche aus dem Arbeitsverhältnis geltend macht"
P_336_2B = ("while the employee is an elected employee representative on the staff council for the business or on a body linked "
            "to the business and the employer cannot cite just cause to terminate his employment")
D_336_2B = ("während der Arbeitnehmer gewählter Arbeitnehmervertreter in einer betrieblichen oder in einer dem Unternehmen "
            "angeschlossenen Einrichtung ist, und der Arbeitgeber nicht beweisen kann, dass er einen begründeten Anlass zur "
            "Kündigung hatte")
P_336_1_INTRO = "Notice of termination is unlawful where given by one party:"
D_336_1_INTRO = "Die Kündigung eines Arbeitsverhältnisses ist missbräuchlich, wenn eine Partei sie ausspricht:"
P_336A_2 = "though it must not exceed an amount equivalent to six months’ salary for the employee"
D_336A_2 = "darf aber den Betrag nicht übersteigen, der dem Lohn des Arbeitnehmers für sechs Monate entspricht"
P_337_1_REASONS = "the party doing so must give his reasons in writing at the other party’s request"
D_337_1_REASONS = "er muss die fristlose Vertragsauflösung schriftlich begründen, wenn die andere Partei dies verlangt"
P_337_2 = ("In particular, good cause is any circumstance which renders the continuation of the employment relationship in good "
           "faith unconscionable for the party giving notice.")
D_337_2 = ("Als wichtiger Grund gilt namentlich jeder Umstand, bei dessen Vorhandensein dem Kündigenden nach Treu und Glauben die "
           "Fortsetzung des Arbeitsverhältnisses nicht mehr zugemutet werden darf.")
P_337_3 = ("under no circumstances may the court hold that good cause is constituted by an employee being prevented from working "
           "through no fault of his own")
D_337_3 = ("darf aber in keinem Fall die unverschuldete Verhinderung des Arbeitnehmers an der Arbeitsleistung als wichtigen Grund "
           "anerkennen")
P_337C_1_WHO = "Where the employer dismisses the employee with immediate effect without good cause, the employee is entitled to damages"
D_337C_1_WHO = "Entlässt der Arbeitgeber den Arbeitnehmer fristlos ohne wichtigen Grund, so hat dieser Anspruch auf Ersatz"
P_337C_1_MEASURE = ("the employee is entitled to damages in the amount he would have earned had the employment relationship ended "
                    "after the required notice period or on expiry of its agreed duration")
D_337C_1_MEASURE = ("so hat dieser Anspruch auf Ersatz dessen, was er verdient hätte, wenn das Arbeitsverhältnis unter Einhaltung der "
                    "Kündigungsfrist oder durch Ablauf der bestimmten Vertragszeit beendigt worden wäre")
P_337C_2 = ("Such damages are reduced by any amounts that the employee saved as a result of the termination of the employment "
            "relationship or that he earned by performing other work")
D_337C_2 = ("Der Arbeitnehmer muss sich daran anrechnen lassen, was er infolge der Beendigung des Arbeitsverhältnisses erspart hat "
            "und was er durch anderweitige Arbeit verdient")
P_337C_3 = "compensation may not exceed the equivalent of six months’ salary for the employee"
D_337C_3 = "diese Entschädigung darf jedoch den Lohn des Arbeitnehmers für sechs Monate nicht übersteigen"

# ---------------------------------------------------------------- shared fact definitions
FACT_NOTICE_PERIOD_VARIED = {
    "id": "notice_period_varied",
    "question": "Does the file say that a written individual employment contract, a standard employment contract or a collective "
                "employment contract sets notice periods different from the statutory ones (one month in the first year of service, "
                "two months in the second to ninth years, three months thereafter)?",
    "not_this": "A notice period that only the termination letter states, with no written contract term behind it.",
    "type": "boolean",
    "rule": R("CO art. 335c para. 2", P_335C_2, "states", de=D_335C_2),
}
PRESUME_NOTICE_PERIOD = {
    "fact": "notice_period_varied", "value": False, "applies": "unstated",
    "rule": R("CO art. 335c para. 1", P_335C_1, "follows",
              "Paragraph 1 fixes the notice periods by law and paragraph 2 lets them differ only by a written individual, standard "
              "or collective contract, so where the file states no such written term the statutory periods apply."),
}
DOC_NOTICE_PERIOD_TERMS_MUST = ["notice period length", "end-point of the notice (e.g. end of a month)",
                                "the written instrument that sets it (individual, standard or collective contract)"]

# ---------------------------------------------------------------- type A: protected period (art. 336c)
A_GO = ALL(T("employer_gave_notice"), F("notice_during_probation"))
A_ANY_PERIOD = {"any": [T("incapacity_illness_accident"), T("compulsory_service"), T("pregnancy_or_birth")]}
TYPE_A = {
    "id": "protected_period_notice",
    "title": "Notice of termination by the employer during a protected period (CO art. 336c)",
    "defining_event": "employer_gave_notice",
    "facts": [
        {"id": "employer_gave_notice",
         "question": "Did the employer give the employee notice of termination of the employment relationship?",
         "not_this": "A resignation by the employee, or a fixed-term relationship that ended by running out.",
         "type": "boolean",
         "rule": R("CO art. 336c para. 1 (introduction)", P_336C_INTRO, "states", de=D_336C_INTRO)},
        {"id": "notice_during_probation",
         "question": "Was the notice given while the probation period was still running?",
         "not_this": "Notice given after the probation period had expired, even shortly after it.",
         "type": "boolean",
         "rule": R("CO art. 336c para. 1 (introduction)", P_336C_INTRO, "states", de=D_336C_INTRO)},
        {"id": "probation_varied",
         "question": "Does the file say that a written individual agreement, a standard employment contract or a collective "
                     "employment contract set a probation period other than the first month of employment?",
         "not_this": "An oral arrangement about probation, or a remark only that the employee was still new.",
         "type": "boolean",
         "rule": R("CO art. 335b para. 2", P_335B_2, "states", de=D_335B_2)},
        {"id": "incapacity_illness_accident",
         "question": "Was the employee, through no fault of their own, wholly or partly prevented from working by illness or "
                     "accident on the day notice was given or while the notice period was still running?",
         "not_this": "Incapacity the employee caused through their own fault, incapacity that ended before notice was given, or "
                     "illness that began only after the notice period had ended.",
         "type": "boolean",
         "rule": R("CO art. 336c para. 1 let. b", P_336C_1B, "states", de=D_336C_1B)},
        {"id": "compulsory_service",
         "question": "Was the employee performing Swiss compulsory military service, civil defence service or alternative civilian "
                     "service on the day notice was given or while the notice period was running, or, for such a service lasting "
                     "more than eleven days, did either of those fall within the four weeks before or after it?",
         "not_this": "Voluntary service, service in a foreign army, or a service of eleven days or less that did not overlap the notice day or the notice period.",
         "type": "boolean",
         "rule": R("CO art. 336c para. 1 let. a", P_336C_1A, "states", de=D_336C_1A)},
        {"id": "pregnancy_or_birth",
         "question": "Was the employee pregnant, or within sixteen weeks after giving birth, on the day notice was given or while "
                     "the notice period was running?",
         "not_this": "Pregnancy of the employee's partner; the further leave periods of art. 336c para. 1 let. cbis to cquinquies, which this rule set does not cover.",
         "type": "boolean",
         "rule": R("CO art. 336c para. 1 let. c", P_336C_1C, "states", de=D_336C_1C)},
        {"id": "notice_before_protected_period",
         "question": "Was the notice given before the protected period began, with the notice period not yet expired when it began?",
         "not_this": "Notice given on a day that already fell inside the protected period (that notice is void, not suspended).",
         "type": "boolean", "always_stated": True,
         "rule": R("CO art. 336c para. 2", P_336C_2_SUSP, "states", de=D_336C_2_SUSP)},
        FACT_NOTICE_PERIOD_VARIED,
    ],
    "steps": [
        {"id": "a_intake", "title": "Establish whether the employer gave notice", "reached_when": True,
         "rule": R("CO art. 336c para. 1 (introduction)", P_336C_INTRO, "follows",
                   "The bar restrains a termination by the employer, so the process starts by establishing that notice.",
                   de=D_336C_INTRO)},
        {"id": "a_probation", "title": "Check that the probation period had expired when notice was given",
         "reached_when": T("employer_gave_notice"),
         "rule": R("CO art. 336c para. 1 (introduction)", P_336C_INTRO, "states", de=D_336C_INTRO)},
        {"id": "a_notice", "title": "Record the notice, the start of employment and the probation terms",
         "reached_when": A_GO,
         "rule": R("CO art. 336c para. 2", P_336C_2_VOID, "follows",
                   "Whether the notice is void or suspended depends on the day it was given and on the protected period, so both are recorded first.",
                   de=D_336C_2_VOID)},
        {"id": "a_incapacity", "title": "Examine the illness or accident protected period",
         "reached_when": ALL(T("employer_gave_notice"), F("notice_during_probation"), T("incapacity_illness_accident")),
         "rule": R("CO art. 336c para. 1 let. b", P_336C_1B, "states", de=D_336C_1B)},
        {"id": "a_service", "title": "Examine the compulsory-service protected period",
         "reached_when": ALL(T("employer_gave_notice"), F("notice_during_probation"), T("compulsory_service")),
         "rule": R("CO art. 336c para. 1 let. a", P_336C_1A, "states", de=D_336C_1A)},
        {"id": "a_pregnancy", "title": "Examine the pregnancy and maternity protected period",
         "reached_when": ALL(T("employer_gave_notice"), F("notice_during_probation"), T("pregnancy_or_birth")),
         "rule": R("CO art. 336c para. 1 let. c", P_336C_1C, "states", de=D_336C_1C)},
        {"id": "a_suspension", "title": "Compute the suspended and extended notice period",
         "reached_when": ALL(T("employer_gave_notice"), F("notice_during_probation"), A_ANY_PERIOD, T("notice_before_protected_period")),
         "rule": R("CO art. 336c para. 2", P_336C_2_SUSP, "states", de=D_336C_2_SUSP)},
        {"id": "a_void", "title": "Check whether the notice fell inside a protected period and is void",
         "reached_when": ALL(T("employer_gave_notice"), F("notice_during_probation"), A_ANY_PERIOD, F("notice_before_protected_period")),
         "rule": R("CO art. 336c para. 2", P_336C_2_VOID, "states", de=D_336C_2_VOID)},
        {"id": "a_assess", "title": "Assess the effect of the notice (void, suspended or valid)",
         "reached_when": A_GO,
         "rule": R("CO art. 336c para. 2", P_336C_2_VOID, "follows",
                   "Paragraph 2 gives one of two effects (void or suspended) to notice and a protected period, so both branches end in one assessment of that effect.",
                   de=D_336C_2_VOID)},
    ],
    "documents": [
        {"id": "termination_letter", "title": "Notice of termination", "step": "a_notice", "needed_when": True, "mandatory": True,
         "must_show": ["issuer", "addressee", "date of the notice", "date the employee received it", "stated end of employment"],
         "rule": R("CO art. 336c para. 2", P_336C_2_VOID, "evidence",
                   "Voidness turns on the day the notice was given compared with the protected period; the notice and its date of receipt are the ordinary record of that day.",
                   de=D_336C_2_VOID)},
        {"id": "employment_contract", "title": "Employment contract or other record of the start of employment", "step": "a_notice",
         "needed_when": True, "mandatory": True,
         "must_show": ["parties", "start date of employment", "probation clause, if any", "notice-period clause, if any"],
         "rule": R("CO art. 335b para. 1", P_335B_1, "evidence",
                   "The probation period, and with it the start of the protection, runs from the start of employment; the contract or another record of the start date ordinarily shows it.",
                   de=D_335B_1)},
        {"id": "probation_terms", "title": "Written probation clause (individual agreement, standard or collective contract)",
         "step": "a_notice", "needed_when": T("probation_varied"), "mandatory": True,
         "must_show": ["length of the probation period", "the written instrument that sets it"],
         "rule": R("CO art. 335b para. 2", P_335B_2, "evidence",
                   "A probation period other than the first month exists only under a written agreement or a standard or collective contract; that written clause proves its length and so whether notice came after it.",
                   de=D_335B_2)},
        {"id": "medical_certificate", "title": "Medical certificate of incapacity for work", "step": "a_incapacity",
         "needed_when": True, "mandatory": True,
         "must_show": ["cause (illness or accident)", "full or partial incapacity", "first and last day of incapacity", "date issued"],
         "rule": R("CO art. 336c para. 1 let. b", P_336C_1B, "evidence",
                   "The bar applies only while the employee is prevented from working by illness or accident; a medical certificate is the ordinary proof of that incapacity and its dates, to compare with the notice.",
                   de=D_336C_1B)},
        {"id": "service_confirmation", "title": "Official confirmation of compulsory service", "step": "a_service",
         "needed_when": True, "mandatory": True,
         "must_show": ["kind of service (military, civil defence, alternative civilian)", "first and last day of service"],
         "rule": R("CO art. 336c para. 1 let. a", P_336C_1A, "evidence",
                   "The bar depends on the kind of service, its dates and whether it lasted more than eleven days; the official service order or confirmation ordinarily shows all three.",
                   de=D_336C_1A)},
        {"id": "pregnancy_certificate", "title": "Medical confirmation of pregnancy or record of the birth", "step": "a_pregnancy",
         "needed_when": True, "mandatory": True,
         "must_show": ["pregnancy confirmed and its dates, or the date of birth"],
         "rule": R("CO art. 336c para. 1 let. c", P_336C_1C, "evidence",
                   "The bar runs during pregnancy and sixteen weeks after the birth; a medical confirmation of the pregnancy or the birth record ordinarily dates that period.",
                   de=D_336C_1C)},
        {"id": "notice_period_terms", "title": "Written notice-period clause (individual, standard or collective contract)",
         "step": "a_suspension", "needed_when": T("notice_period_varied"), "mandatory": True,
         "must_show": DOC_NOTICE_PERIOD_TERMS_MUST,
         "rule": R("CO art. 336c para. 3", P_336C_3, "evidence",
                   "Resuming and extending a suspended notice period needs its length and end-point; where a written contract varies the statutory periods, that clause is the ordinary proof of them.")},
    ],
    "presumptions": [
        {"fact": "probation_varied", "value": False, "applies": "unstated",
         "rule": R("CO art. 335b para. 1", P_335B_1, "follows",
                   "The statute deems the probation period to be the first month and paragraph 2 allows other terms only in writing, so where the file states no such written term the first month applies.",
                   de=D_335B_1)},
        PRESUME_NOTICE_PERIOD,
    ],
    "stops": [
        {"id": "a_stop_no_notice", "when": F("employer_gave_notice"),
         "rule": R("CO art. 336c para. 1 (introduction)", P_336C_INTRO, "follows",
                   "The provision restrains only a termination by the employer; where the employer gave no notice there is nothing it can make void or suspend, so this process ends.",
                   de=D_336C_INTRO)},
        {"id": "a_stop_probation", "when": ALL(T("employer_gave_notice"), T("notice_during_probation")),
         "rule": R("CO art. 336c para. 1 (introduction)", P_336C_INTRO, "follows",
                   "The bar applies only after the probation period has expired; notice given during probation is outside it, so this process ends.",
                   de=D_336C_INTRO)},
    ],
}

# ---------------------------------------------------------------- type B: wrongful termination (arts. 336-336b)
STOP_B_OBJ = ALL(T("notice_period_ended"), F("objection_submitted"))
STOP_B_180 = ALL(T("more_than_180_days"), F("action_in_time"))
B_GO = ALL(T("employer_gave_notice"), NOT(STOP_B_OBJ), NOT(STOP_B_180))
TYPE_B = {
    "id": "wrongful_termination",
    "title": "Wrongful (abusive) notice of termination by the employer: objection and compensation claim (CO arts. 336-336b)",
    "defining_event": "employer_gave_notice",
    "facts": [
        {"id": "employer_gave_notice",
         "question": "Did the employer give the employee notice of termination of the employment relationship?",
         "not_this": "A resignation by the employee, or a fixed-term relationship that ended by running out.",
         "type": "boolean",
         "rule": R("CO art. 336b para. 2", P_336B_2_CLAIM, "states", de=D_336B_2_CLAIM)},
        {"id": "notice_period_ended",
         "question": "Has the notice period (from the notice to the end of the employment relationship) already ended?",
         "not_this": "The employee's last working day where they were released from work while the notice period was still running.",
         "type": "boolean", "always_stated": True,
         "rule": R("CO art. 336b para. 1", P_336B_1, "states", de=D_336B_1)},
        {"id": "objection_submitted",
         "question": "Did the employee send the employer a written objection to the notice before the notice period ended?",
         "not_this": "An oral protest, or a written objection sent only after the notice period had ended.",
         "type": "boolean",
         "rule": R("CO art. 336b para. 1", P_336B_1, "states", de=D_336B_1)},
        {"id": "more_than_180_days",
         "question": "Have more than 180 days passed since the employment relationship ended?",
         "not_this": "180 days counted from the notice or from the last day actually worked rather than from the end of the employment relationship.",
         "type": "boolean", "always_stated": True,
         "rule": R("CO art. 336b para. 2", P_336B_2_180, "states", de=D_336B_2_180)},
        {"id": "action_in_time",
         "question": "Did the employee bring the compensation claim before a court within 180 days of the end of the employment relationship?",
         "not_this": "A demand letter to the employer, or a court claim filed only after the 180 days.",
         "type": "boolean",
         "rule": R("CO art. 336b para. 2", P_336B_2_180, "states", de=D_336B_2_180)},
        {"id": "reasons_requested",
         "question": "Did the employee ask the employer to state the reasons for the notice in writing?",
         "not_this": "Reasons the employer gave without being asked, or a request made only orally to a colleague rather than to the employer.",
         "type": "boolean",
         "rule": R("CO art. 335 para. 2", P_335_2, "states", de=D_335_2)},
        {"id": "retaliation_for_claims",
         "question": "Does the employee say the notice was given because they had asserted, in good faith, claims arising from the employment relationship?",
         "not_this": "Complaints that are not claims under the employment relationship, or a mere coincidence in time that the employee does not link to the notice.",
         "type": "boolean",
         "rule": R("CO art. 336 para. 1 let. d", P_336_1D, "states", de=D_336_1D)},
        {"id": "employee_representative",
         "question": "Was the employee, when notice was given, an elected employee representative on the staff council of the business or on a body linked to the business?",
         "not_this": "Trade-union membership or union activity without an elected mandate (art. 336 para. 2 let. a, not covered here).",
         "type": "boolean",
         "rule": R("CO art. 336 para. 2 let. b", P_336_2B, "states", de=D_336_2B)},
    ],
    "steps": [
        {"id": "b_intake", "title": "Establish whether the employer gave notice", "reached_when": True,
         "rule": R("CO art. 336b para. 2", P_336B_2_CLAIM, "follows",
                   "The compensation claim belongs to the party on whom notice was served, so the process starts by establishing that notice.",
                   de=D_336B_2_CLAIM)},
        {"id": "b_objection_check", "title": "Check whether the objection window has closed without a written objection",
         "reached_when": T("employer_gave_notice"),
         "rule": R("CO art. 336b para. 1", P_336B_1, "states", de=D_336B_1)},
        {"id": "b_limit_check", "title": "Check the 180-day time limit for the court claim",
         "reached_when": ALL(T("employer_gave_notice"), NOT(STOP_B_OBJ)),
         "rule": R("CO art. 336b para. 2", P_336B_2_180, "states", de=D_336B_2_180)},
        {"id": "b_notice", "title": "Record the notice, the notice period, the objection and any court claim",
         "reached_when": B_GO,
         "rule": R("CO art. 336b para. 1", P_336B_1, "follows",
                   "The objection must reach the employer in writing before the notice period ends, so the notice, the period and the objection are recorded together.",
                   de=D_336B_1)},
        {"id": "b_grounds", "title": "Establish the reason the employer gave for the notice",
         "reached_when": B_GO,
         "rule": R("CO art. 336 para. 1 (introduction)", P_336_1_INTRO, "follows",
                   "Article 336 makes notice wrongful by the reason for which it was given, so the employer's reason is established before the grounds are examined.",
                   de=D_336_1_INTRO)},
        {"id": "b_retaliation", "title": "Examine the claimed retaliation for asserting claims",
         "reached_when": ALL(B_GO, T("retaliation_for_claims")),
         "rule": R("CO art. 336 para. 1 let. d", P_336_1D, "states", de=D_336_1D)},
        {"id": "b_representative", "title": "Examine the protection of an elected employee representative",
         "reached_when": ALL(B_GO, T("employee_representative")),
         "rule": R("CO art. 336 para. 2 let. b", P_336_2B, "states", de=D_336_2B)},
        {"id": "b_compensation", "title": "Assess the compensation claim",
         "reached_when": B_GO,
         "rule": R("CO art. 336a para. 2", P_336A_2, "states", de=D_336A_2)},
    ],
    "documents": [
        {"id": "termination_letter", "title": "Notice of termination", "step": "b_notice", "needed_when": True, "mandatory": True,
         "must_show": ["issuer", "addressee", "date of the notice", "stated end of employment"],
         "rule": R("CO art. 336b para. 1", P_336B_1, "evidence",
                   "The objection must be made before the end of the notice period; the notice ordinarily shows when it was given and when the employment ends, which fixes that window and the start of the 180 days.",
                   de=D_336B_1)},
        {"id": "employment_contract", "title": "Employment contract or other record of the start of employment", "step": "b_notice",
         "needed_when": True, "mandatory": True,
         "must_show": ["parties", "start date of employment", "notice-period clause, if any"],
         "rule": R("CO art. 335c para. 1", P_335C_1, "evidence",
                   "The end of the notice period, which closes the objection window, depends on the years of service and on any written variation; the contract ordinarily shows the start date and any such clause.")},
        {"id": "written_objection", "title": "Copy of the written objection with proof of when it was sent", "step": "b_notice",
         "needed_when": T("objection_submitted"), "mandatory": True,
         "must_show": ["objection to the notice", "addressed to the employer", "date sent or received", "proof of sending or receipt"],
         "rule": R("CO art. 336b para. 1", P_336B_1, "evidence",
                   "The claim requires a written objection to the employer before the notice period ends; a copy of the objection with proof of its date is the ordinary proof of both.",
                   de=D_336B_1)},
        {"id": "court_filing", "title": "Copy of the court claim with its filing date", "step": "b_notice",
         "needed_when": T("action_in_time"), "mandatory": True,
         "must_show": ["court", "compensation claim", "filing date"],
         "rule": R("CO art. 336b para. 2", P_336B_2_180, "evidence",
                   "The claim is lost unless brought before a court within 180 days of the end of employment; the filed claim with its filing date is the ordinary proof that it was brought in time.",
                   de=D_336B_2_180)},
        {"id": "written_reasons", "title": "Employer's written statement of reasons", "step": "b_grounds",
         "needed_when": T("reasons_requested"), "mandatory": True,
         "must_show": ["reasons stated by the employer", "date"],
         "rule": R("CO art. 335 para. 2", P_335_2, "evidence",
                   "Where the employee asked, the employer must give its reasons in writing; that statement is the ordinary record of the reason on which art. 336 makes wrongfulness depend.",
                   de=D_335_2)},
        {"id": "claims_correspondence", "title": "Correspondence in which the employee asserted claims before the notice",
         "step": "b_retaliation", "needed_when": True, "mandatory": True,
         "must_show": ["claims asserted under the employment relationship", "dates before the notice", "employer's response, if any"],
         "rule": R("CO art. 336 para. 1 let. d", P_336_1D, "evidence",
                   "This ground turns on claims asserted before the notice; the correspondence in which the employee raised them is the ordinary record of what was claimed and when.",
                   de=D_336_1D)},
        {"id": "representative_mandate", "title": "Proof of election as employee representative", "step": "b_representative",
         "needed_when": True, "mandatory": True,
         "must_show": ["body (staff council or body linked to the business)", "election", "term of the mandate covering the notice date"],
         "rule": R("CO art. 336 para. 2 let. b", P_336_2B, "evidence",
                   "The protection applies while the employee is an elected representative; the election record or mandate confirmation ordinarily shows the body and the term.",
                   de=D_336_2B)},
        {"id": "salary_evidence", "title": "Salary statements (pay slips)", "step": "b_compensation", "needed_when": True,
         "mandatory": True, "must_show": ["monthly salary", "period covered"],
         "rule": R("CO art. 336a para. 2", P_336A_2, "evidence",
                   "Compensation is capped at six months' salary; pay slips are the ordinary proof of the salary that sets the cap.",
                   de=D_336A_2)},
    ],
    "presumptions": [],
    "stops": [
        {"id": "b_stop_no_notice", "when": F("employer_gave_notice"),
         "rule": R("CO art. 336b para. 2", P_336B_2_CLAIM, "follows",
                   "Only the party on whom notice was served may bring the compensation claim; where the employer gave no notice there is no such claim, so this process ends.",
                   de=D_336B_2_CLAIM)},
        {"id": "b_stop_no_objection", "when": ALL(T("employer_gave_notice"), STOP_B_OBJ),
         "rule": R("CO art. 336b para. 1", P_336B_1, "follows",
                   "Compensation under arts. 336 and 336a requires a written objection before the notice period ends; once the period has ended without one, the claim cannot be brought, so this process ends.",
                   de=D_336B_1)},
        {"id": "b_stop_time_limit", "when": ALL(T("employer_gave_notice"), NOT(STOP_B_OBJ), STOP_B_180),
         "rule": R("CO art. 336b para. 2", P_336B_2_180, "states", de=D_336B_2_180)},
    ],
}

# ---------------------------------------------------------------- type C: immediate dismissal (arts. 337, 337c)
C_GO = T("dismissed_immediately")
TYPE_C = {
    "id": "immediate_dismissal",
    "title": "Dismissal with immediate effect by the employer (CO arts. 337, 337c)",
    "defining_event": "dismissed_immediately",
    "facts": [
        {"id": "dismissed_immediately",
         "question": "Did the employer end the employment relationship with immediate effect, without a notice period?",
         "not_this": "Ordinary notice with a notice period, however short, or release from work while a notice period runs.",
         "type": "boolean",
         "rule": R("CO art. 337c para. 1", P_337C_1_WHO, "states", de=D_337C_1_WHO)},
        {"id": "reasons_requested",
         "question": "Did the employee ask the employer to state the reasons for the immediate dismissal in writing?",
         "not_this": "Reasons the employer gave without being asked.",
         "type": "boolean",
         "rule": R("CO art. 337 para. 1", P_337_1_REASONS, "states", de=D_337_1_REASONS)},
        {"id": "incapacity_cause",
         "question": "Does the employer give as the cause of the dismissal the employee's absence from work, and does the employee say "
                     "the absence was due to illness or accident through no fault of their own?",
         "not_this": "A dismissal for conduct at work, or an absence the employee does not attribute to illness or accident.",
         "type": "boolean",
         "rule": R("CO art. 337 para. 3", P_337_3, "states", de=D_337_3)},
        {"id": "fixed_term",
         "question": "Was the employment relationship agreed for a fixed term, with an agreed end date, rather than for an unlimited period?",
         "not_this": "An open-ended contract that only states a probation period or a notice period.",
         "type": "boolean",
         "rule": R("CO art. 337c para. 1", P_337C_1_MEASURE, "states", de=D_337C_1_MEASURE)},
        FACT_NOTICE_PERIOD_VARIED,
        {"id": "other_earnings",
         "question": "Has the employee earned income from other work during the time the notice period or the agreed term would still have run?",
         "not_this": "Unemployment benefits or other payments that are not earnings from work.",
         "type": "boolean",
         "rule": R("CO art. 337c para. 2", P_337C_2, "states", de=D_337C_2)},
    ],
    "steps": [
        {"id": "c_intake", "title": "Establish whether the employer dismissed with immediate effect", "reached_when": True,
         "rule": R("CO art. 337c para. 1", P_337C_1_WHO, "follows",
                   "The entitlement arises from an immediate dismissal by the employer, so the process starts by establishing it.",
                   de=D_337C_1_WHO)},
        {"id": "c_dismissal", "title": "Record the dismissal, the contract and the salary", "reached_when": C_GO,
         "rule": R("CO art. 337c para. 1", P_337C_1_MEASURE, "follows",
                   "Damages are measured by the earnings up to the end of the notice period or the agreed term, so the dismissal date, the contract and the salary are recorded.",
                   de=D_337C_1_MEASURE)},
        {"id": "c_cause", "title": "Establish the cause the employer relies on", "reached_when": C_GO,
         "rule": R("CO art. 337 para. 2", P_337_2, "follows",
                   "Whether the dismissal was justified depends on the circumstance relied on, so that circumstance is established first.",
                   de=D_337_2)},
        {"id": "c_fixed_term", "title": "Measure damages to the agreed end of the fixed term",
         "reached_when": ALL(C_GO, T("fixed_term")),
         "rule": R("CO art. 337c para. 1", P_337C_1_MEASURE, "states", de=D_337C_1_MEASURE)},
        {"id": "c_notice_period", "title": "Measure damages to the end of the required notice period",
         "reached_when": ALL(C_GO, F("fixed_term")),
         "rule": R("CO art. 337c para. 1", P_337C_1_MEASURE, "states", de=D_337C_1_MEASURE)},
        {"id": "c_damages", "title": "Assess damages and compensation", "reached_when": C_GO,
         "rule": R("CO art. 337c para. 3", P_337C_3, "states", de=D_337C_3)},
    ],
    "documents": [
        {"id": "termination_letter", "title": "Letter or message dismissing with immediate effect", "step": "c_dismissal",
         "needed_when": True, "mandatory": True,
         "must_show": ["issuer", "addressee", "date", "that employment ends with immediate effect"],
         "rule": R("CO art. 337c para. 1", P_337C_1_WHO, "evidence",
                   "The entitlement arises from a dismissal with immediate effect; the dismissal letter or message is the ordinary record that it was immediate and of its date.",
                   de=D_337C_1_WHO)},
        {"id": "employment_contract", "title": "Employment contract or other record of its terms", "step": "c_dismissal",
         "needed_when": True, "mandatory": True,
         "must_show": ["parties", "start date of employment", "agreed end date, if fixed-term", "notice-period clause, if any"],
         "rule": R("CO art. 337c para. 1", P_337C_1_MEASURE, "evidence",
                   "Damages run to the end of the required notice period or of the agreed term; the contract ordinarily shows the start date, any agreed end date and any notice clause.",
                   de=D_337C_1_MEASURE)},
        {"id": "salary_evidence", "title": "Salary statements (pay slips)", "step": "c_dismissal", "needed_when": True,
         "mandatory": True, "must_show": ["monthly salary", "period covered"],
         "rule": R("CO art. 337c para. 1", P_337C_1_MEASURE, "evidence",
                   "Damages equal what the employee would have earned; pay slips are the ordinary proof of those earnings (and of the salary that caps compensation under para. 3).",
                   de=D_337C_1_MEASURE)},
        {"id": "written_reasons", "title": "Employer's written statement of reasons", "step": "c_cause",
         "needed_when": T("reasons_requested"), "mandatory": True,
         "must_show": ["reasons stated by the employer", "date"],
         "rule": R("CO art. 337 para. 1", P_337_1_REASONS, "evidence",
                   "Where the employee asked, the employer must give its reasons in writing; that statement is the ordinary record of the cause it relies on.",
                   de=D_337_1_REASONS)},
        {"id": "medical_certificate", "title": "Medical certificate of incapacity for work", "step": "c_cause",
         "needed_when": T("incapacity_cause"), "mandatory": True,
         "must_show": ["cause (illness or accident)", "full or partial incapacity", "first and last day of incapacity", "date issued"],
         "rule": R("CO art. 337 para. 3", P_337_3, "evidence",
                   "Being prevented from working through no fault of one's own can never be good cause; a medical certificate is the ordinary proof that an absence was due to illness or accident and of its dates.",
                   de=D_337_3)},
        {"id": "notice_period_terms", "title": "Written notice-period clause (individual, standard or collective contract)",
         "step": "c_notice_period", "needed_when": T("notice_period_varied"), "mandatory": True,
         "must_show": DOC_NOTICE_PERIOD_TERMS_MUST,
         "rule": R("CO art. 335c para. 2", P_335C_2, "evidence",
                   "Damages run to the end of the required notice period; where a written contract varies the statutory periods, that clause is the ordinary proof of the period that applies.",
                   de=D_335C_2)},
        {"id": "other_earnings_evidence", "title": "Proof of earnings from other work since the dismissal", "step": "c_damages",
         "needed_when": T("other_earnings"), "mandatory": True,
         "must_show": ["employer or client", "period", "amounts earned"],
         "rule": R("CO art. 337c para. 2", P_337C_2, "evidence",
                   "Damages are reduced by what the employee earned from other work; pay slips or contracts for that work are the ordinary proof of the amounts and period.",
                   de=D_337C_2)},
    ],
    "presumptions": [PRESUME_NOTICE_PERIOD],
    "stops": [
        {"id": "c_stop_no_immediate_dismissal", "when": F("dismissed_immediately"),
         "rule": R("CO art. 337c para. 1", P_337C_1_WHO, "follows",
                   "The entitlement arises only where the employer dismisses with immediate effect; without such a dismissal this process has nothing to assess, so it ends.",
                   de=D_337C_1_WHO)},
    ],
}

TYPES = [TYPE_A, TYPE_B, TYPE_C]

SOURCES = [
    {"id": EN, "title": "Swiss Code of Obligations (SR 220), consolidated version applicable from 2026-10-01, official English translation",
     "publisher": "Swiss Federal Chancellery, Fedlex", "language": "en", "authoritative": False},
    {"id": DE, "title": "Obligationenrecht (SR 220), konsolidierte Fassung vom 1. Oktober 2026, deutscher Text",
     "publisher": "Swiss Federal Chancellery, Fedlex", "language": "de", "authoritative": True},
]

# ---------------------------------------------------------------- the intake convention (SPEC.md item 6a)
# Exact words of SPEC.md item 6a; tools/check.py confirms they occur there and in rule_text.md.
CONVENTION_TEXT = ("A fact that the file does not mention is taken as not alleged, and the rules are applied as if it were "
                   "absent. Silence never ends a process: where a fact's absence would end it, the unmentioned fact is "
                   "unresolved. The defining event is never presumed: if the file does not mention it, it is unresolved. A "
                   "fact that the file raises and leaves unsettled is open.")
CONVENTION_SOURCE = {"id": "benchmark-convention", "kind": "benchmark_convention",
                     "title": "Convention of this benchmark (not law): Study 4 SPEC.md item 6a"}
CONVENTION = {
    "id": "intake_convention",
    "text": CONVENTION_TEXT,
    "applies_to": "every fact of every type except the defining event, a fact whose value false triggers a stop, and "
                  "a fact marked always_stated; a statutory presumption under the type's presumptions takes precedence",
    "rule": {"source_id": CONVENTION_SOURCE["id"], "locator": "SPEC.md item 6a", "basis": "convention"},
}
# SPEC.md 6a: the frozen validator knows no convention kind, so the workflow uses process_guidance with intended_kind.
WF_CONVENTION_KIND = "process_guidance"


def stop_on_false(t):
    """Facts whose value false can trigger a stop: some complete assignment ends in a stop with the fact false
    and in no stop with only that fact turned true."""
    import itertools
    ids = [f["id"] for f in t["facts"]]
    out = set()

    def ev(c, facts):
        if c is True:
            return True
        if "all" in c:
            return all(ev(x, facts) for x in c["all"])
        if "any" in c:
            return any(ev(x, facts) for x in c["any"])
        if "not" in c:
            return not ev(c["not"], facts)
        return facts[c["fact"]] == c["is"]
    for values in itertools.product([True, False], repeat=len(ids)):
        facts = dict(zip(ids, values))
        for f in ids:
            if facts[f] is False:
                flipped = {**facts, f: True}
                if any(ev(st["when"], facts) for st in t["stops"]) and not any(ev(st["when"], flipped) for st in t["stops"]):
                    out.add(f)
    return out


def convention_facts(t):
    """Branch facts the convention fills with 'no' (SPEC.md 6a): not the defining event, not a fact whose false
    triggers a stop, not an always_stated fact, not a fact with a statutory presumption."""
    excluded = {t["defining_event"]} | stop_on_false(t) | {f["id"] for f in t["facts"] if f.get("always_stated")} | \
        {p["fact"] for p in t["presumptions"]}
    return [f["id"] for f in t["facts"] if f["id"] not in excluded]

# Plain-words summary of each type for rule_text.md (restates the cited articles; every rule itself is generated).
SUMMARIES = {
    "protected_period_notice":
        "After the probation period has expired, the employer may not give notice during the protected periods of "
        "art. 336c para. 1 (\"Sperrfristen\"). Notice given during such a period is void (\"nichtig\", art. 336c para. 2). "
        "Notice given before such a period began, with the notice period still running when it began, is suspended and "
        "resumes only after the period ends (art. 336c para. 2); if a specific end-point applies, such as the end of a "
        "month, the resumed notice period is extended to the next end-point (art. 336c para. 3).",
    "wrongful_termination":
        "Notice is wrongful (\"missbräuchlich\"; the English translation says \"unlawful\") when given for one of the "
        "reasons in art. 336. The party who gave wrongful notice owes compensation, set by the court and capped at six "
        "months' salary (art. 336a para. 2). To claim it, the employee must object to the notice in writing to the "
        "employer no later than the end of the notice period (art. 336b para. 1), and must bring the claim before a court "
        "within 180 days of the end of the employment relationship; otherwise the claim is lost (\"verwirkt\", forfeited; "
        "the English translation says \"prescribes\", art. 336b para. 2). The party giving notice must state the reasons "
        "in writing if the other party asks (art. 335 para. 2).",
    "immediate_dismissal":
        "Either party may end the employment relationship with immediate effect at any time for good cause "
        "(\"wichtige Gründe\") and must give the reasons in writing if the other party asks (art. 337 para. 1). Good cause "
        "is any circumstance that makes continuing the relationship in good faith unconscionable for the party giving "
        "notice (art. 337 para. 2). Being prevented from working through no fault of one's own is never good cause "
        "(art. 337 para. 3). Where the employer dismisses with immediate effect without good cause, the employee is "
        "entitled to what they would have earned had the relationship ended after the required notice period or at the "
        "end of its agreed term (art. 337c para. 1), reduced by what they saved or earned from other work (art. 337c "
        "para. 2); the court may add compensation of up to six months' salary (art. 337c para. 3).",
}

# ---------------------------------------------------------------- workflow graphs (casepath.workflow/1)
# Each type's graph: the rule steps above plus system gates, stop steps and a close step.
# tools/check.py walks every complete fact assignment and confirms the graph reaches exactly
# the steps, documents and stops that rules.json says.

def gate(fact, yes, no, title):
    return {"kind": "gate", "fact": fact, "yes": yes, "no": no, "title": title}


GRAPHS = {
    "protected_period_notice": {
        "start": "a_intake",
        "edges": {
            "a_intake": [(F("employer_gave_notice"), "a_stop_no_notice", "no notice by the employer"),
                         (T("employer_gave_notice"), "a_probation", "employer gave notice")],
            "a_probation": [(T("notice_during_probation"), "a_stop_probation", "notice during probation"),
                            (F("notice_during_probation"), "a_notice", "probation expired")],
            "a_notice": [(True, "a_gate_incapacity", None)],
            "a_incapacity": [(True, "a_gate_service", None)],
            "a_service": [(True, "a_gate_pregnancy", None)],
            "a_pregnancy": [(True, "a_gate_any_period", None)],
            "a_suspension": [(True, "a_assess", None)],
            "a_void": [(True, "a_assess", None)],
            "a_assess": [(True, "a_close", None)],
        },
        "gates": {
            "a_gate_incapacity": gate("incapacity_illness_accident", "a_incapacity", "a_gate_service", "Check branch: illness or accident"),
            "a_gate_service": gate("compulsory_service", "a_service", "a_gate_pregnancy", "Check branch: compulsory service"),
            "a_gate_pregnancy": gate("pregnancy_or_birth", "a_pregnancy", "a_gate_any_period", "Check branch: pregnancy or birth"),
            "a_gate_any_period": {"kind": "cond", "when": A_ANY_PERIOD, "yes": "a_gate_timing", "no": "a_assess",
                                  "ref_fact": "notice_before_protected_period",
                                  "title": "Check branch: a protected period of let. a, b or c is raised"},
            "a_gate_timing": gate("notice_before_protected_period", "a_suspension", "a_void", "Check branch: notice before the protected period"),
        },
    },
    "wrongful_termination": {
        "start": "b_intake",
        "edges": {
            "b_intake": [(F("employer_gave_notice"), "b_stop_no_notice", "no notice by the employer"),
                         (T("employer_gave_notice"), "b_objection_check", "employer gave notice")],
            "b_objection_check": [(STOP_B_OBJ, "b_stop_no_objection", "notice period ended without a written objection"),
                                  (NOT(STOP_B_OBJ), "b_limit_check", "objection made or still possible")],
            "b_limit_check": [(STOP_B_180, "b_stop_time_limit", "180 days passed without a court claim"),
                              (NOT(STOP_B_180), "b_notice", "time limit kept or still running")],
            "b_notice": [(True, "b_grounds", None)],
            "b_grounds": [(True, "b_gate_retaliation", None)],
            "b_retaliation": [(True, "b_gate_representative", None)],
            "b_representative": [(True, "b_compensation", None)],
            "b_compensation": [(True, "b_close", None)],
        },
        "gates": {
            "b_gate_retaliation": gate("retaliation_for_claims", "b_retaliation", "b_gate_representative", "Check branch: retaliation for asserting claims"),
            "b_gate_representative": gate("employee_representative", "b_representative", "b_compensation", "Check branch: elected employee representative"),
        },
    },
    "immediate_dismissal": {
        "start": "c_intake",
        "edges": {
            "c_intake": [(F("dismissed_immediately"), "c_stop_no_immediate_dismissal", "no immediate dismissal"),
                         (T("dismissed_immediately"), "c_dismissal", "dismissed with immediate effect")],
            "c_dismissal": [(True, "c_cause", None)],
            "c_cause": [(True, "c_gate_fixed_term", None)],
            "c_fixed_term": [(True, "c_damages", None)],
            "c_notice_period": [(True, "c_damages", None)],
            "c_damages": [(True, "c_close", None)],
        },
        "gates": {
            "c_gate_fixed_term": gate("fixed_term", "c_fixed_term", "c_notice_period", "Check branch: fixed-term relationship"),
        },
    },
}

SRC = "co-sr220"


def ref(rule):
    """A source reference for the workflow: the source id and the locator, made id-safe."""
    loc = rule["locator"].replace("CO ", "").replace(" (introduction)", " intro")
    return f"{SRC}#" + "_".join(loc.replace(".", "").split())


def workflow(t):
    g = GRAPHS[t["id"]]
    facts = {f["id"]: f for f in t["facts"]}
    rule_steps = {s["id"]: s for s in t["steps"]}
    stops = {s["id"]: s for s in t["stops"]}
    wf_facts = [{"id": "dispute_family", "type": "enum",
                 "question": "Which employment-termination dispute does the claim concern: notice during a protected period, "
                             "wrongful (abusive) notice, or dismissal with immediate effect?",
                 "values": [x["id"] for x in TYPES], "source_refs": [f"{SRC}#arts_335-337c"]}]
    for f in t["facts"]:
        wf_facts.append({"id": f["id"], "type": "boolean", "question": f["question"], "source_refs": [ref(f["rule"])]})
    docs = []
    for d in t["documents"]:
        item = {"id": d["id"], "title": d["title"], "must_show": d["must_show"], "source_refs": [ref(d["rule"])],
                "why": f"{d['rule']['locator']}: {d['rule'].get('inference', '')}".strip()}
        if d["needed_when"] is not True:
            item["required_when"] = d["needed_when"]
        docs.append(item)
    steps = []
    for sid, s in rule_steps.items():
        step = {"id": sid, "title": s["title"], "role": "claim_handler", "source_refs": [ref(s["rule"])]}
        attached = [d["id"] for d in t["documents"] if d["step"] == sid]
        if attached:
            step["documents"] = attached
        step["next"] = []
        for when, to, label in g["edges"][sid]:
            edge = {"to": to, "when": when}
            if label:
                edge["label"] = label
            step["next"].append(edge)
        steps.append(step)
    for gid, gt in g["gates"].items():
        if gt["kind"] == "cond":
            steps.append({"id": gid, "title": gt["title"], "role": "system", "source_refs": [ref(facts[gt["ref_fact"]]["rule"])],
                          "next": [{"to": gt["yes"], "when": gt["when"], "label": "protected period raised"},
                                   {"to": gt["no"], "when": NOT(gt["when"]), "label": "no protected period raised"}]})
            continue
        fact = facts[gt["fact"]]
        steps.append({"id": gid, "title": gt["title"], "role": "system", "source_refs": [ref(fact["rule"])],
                      "next": [{"to": gt["yes"], "when": T(gt["fact"]), "label": gt["fact"]},
                               {"to": gt["no"], "when": F(gt["fact"]), "label": "not " + gt["fact"]}]})
    outcomes = [{"id": "assessed", "title": "Documents complete for assessment", "source_refs": [f"{SRC}#arts_335-337c"]}]
    for sid, s in stops.items():
        outcomes.append({"id": sid, "title": "Process ends: " + s["rule"]["inference"].split(";")[0] if s["rule"].get("inference")
                         else "Process ends: " + s["rule"]["passage"], "source_refs": [ref(s["rule"])]})
        steps.append({"id": sid, "title": "Stop (" + s["rule"]["locator"] + ")", "role": "system", "outcome": sid,
                      "source_refs": [ref(s["rule"])]})
    close = g["start"].split("_")[0] + "_close"
    steps.append({"id": close, "title": "Record the document state for assessment", "role": "claim_handler",
                  "outcome": "assessed", "source_refs": [f"{SRC}#arts_335-337c"]})
    statutory = {p["fact"]: p for p in t["presumptions"]}
    presumptions = []
    for f in t["facts"]:
        if f["id"] == t["defining_event"]:
            continue  # the defining event is never presumed
        p = statutory.get(f["id"])
        if p is None and f["id"] not in convention_facts(t):
            continue  # silence leaves it unresolved: false would end the process, or it is always stated
        if p is not None:  # a statutory default takes precedence over the convention
            presumptions.append({"fact": p["fact"], "value": p["value"], "applies": p["applies"], "source_ref": ref(p["rule"]),
                                 "text": f"{p['rule']['locator']}: “{p['rule']['passage']}” {p['rule']['inference']}"})
        else:
            presumptions.append({"fact": f["id"], "value": False, "applies": "unstated",
                                 "source_ref": f"{CONVENTION_SOURCE['id']}#intake_convention",
                                 "text": "Convention of this benchmark (not law): " + CONVENTION_TEXT})
    notes = [{"text": "Convention of this benchmark (not law): " + CONVENTION_TEXT + " Statutory defaults under presumptions "
                      "(CO arts. 335b para. 1 and 335c para. 1) take precedence for their facts. No presumption: "
                      + ", ".join(sorted(stop_on_false(t) - {t["defining_event"]})) + " (false would end the process); "
                      "always stated: " + ", ".join(f["id"] for f in t["facts"] if f.get("always_stated")) + ".",
              "source_refs": [f"{CONVENTION_SOURCE['id']}#intake_convention"]}]
    return {
        "format": "casepath.workflow/1",
        "id": t["id"],
        "version": "2026-11-12",
        "title": t["title"],
        "status": "draft",
        "example": False,
        "applies_when": {"fact": "dispute_family", "is": t["id"]},
        "sources": [{"id": SRC, "kind": "knowledge",
                     "title": "Swiss Code of Obligations (SR 220), consolidated version of 2026-10-01 (Fedlex); English translation, German text authoritative"},
                    {"id": CONVENTION_SOURCE["id"], "kind": WF_CONVENTION_KIND, "intended_kind": CONVENTION_SOURCE["kind"],
                     "title": CONVENTION_SOURCE["title"]}],
        "facts": wf_facts,
        "documents": docs,
        "start": g["start"],
        "steps": steps,
        "outcomes": outcomes,
        "presumptions": presumptions,
        "notes": notes,
        "open_questions": [],
    }


def cond_text(c):
    if c is True:
        return "always"
    if "all" in c:
        return " and ".join(f"({cond_text(x)})" if "all" in x or "any" in x else cond_text(x) for x in c["all"])
    if "any" in c:
        return " or ".join(cond_text(x) for x in c["any"])
    if "not" in c:
        return f"not ({cond_text(c['not'])})"
    return f"{c['fact']} = {'yes' if c['is'] else 'no'}"


def md_rule(r):
    de = r.get("passage_de", {}).get("passage")
    out = f"{r['locator']} [{r['basis']}]: “{r['passage']}”"
    if de:
        out += f" (DE: „{de}“)"
    if r.get("inference"):
        out += f" Inference: {r['inference']}"
    return out.replace("|", "\\|")


def rules_md(data):
    lines = [f"# Rule set: dismissal (version {data['version']})", "",
             "Development material for Study 4, step 2a. Every clause cites the Swiss Code of Obligations (SR 220) in the "
             "consolidated version applicable from 2026-10-01 (Fedlex). The English translation is quoted; the German text, "
             "which is authoritative, is quoted beside it. Passages are verbatim from `sources/co-sr220-en.txt` and "
             "`sources/co-sr220-de.txt`. A document is needed when its step is reached and its condition holds.", ""]
    for t in data["types"]:
        lines += [f"## {t['title']}", "", f"Type id `{t['id']}`; defining event `{t['defining_event']}`.", "",
                  "### Deciding conditions", "", "| fact | question | not this | citation |", "|---|---|---|---|"]
        for f in t["facts"]:
            lines.append(f"| `{f['id']}` | {f['question']} | {f['not_this']} | {md_rule(f['rule'])} |")
        lines += ["", "### Steps", "", "| step | reached when | citation |", "|---|---|---|"]
        for s in t["steps"]:
            lines.append(f"| `{s['id']}` {s['title']} | {cond_text(s['reached_when'])} | {md_rule(s['rule'])} |")
        lines += ["", "### Documents", "", "| document | step | needed when | must show | citation |", "|---|---|---|---|---|"]
        for d in t["documents"]:
            lines.append(f"| `{d['id']}` {d['title']} | `{d['step']}` | {cond_text(d['needed_when'])} | {'; '.join(d['must_show'])} | {md_rule(d['rule'])} |")
        lines += ["", "### Presumptions", ""]
        if t["presumptions"]:
            lines += ["| fact | value | applies | citation |", "|---|---|---|---|"]
            for p in t["presumptions"]:
                lines.append(f"| `{p['fact']}` | {'yes' if p['value'] else 'no'} | {p['applies']} | {md_rule(p['rule'])} |")
        else:
            lines.append("None from statute.")
        lines += ["", "Convention of this benchmark (not law), not a passage of law: " + CONVENTION_TEXT, "",
                  "Filled with no under the convention: " + ", ".join(f"`{x}`" for x in convention_facts(t)) + ". "
                  "No presumption because false would end the process: "
                  + (", ".join(f"`{x}`" for x in sorted(stop_on_false(t) - {t['defining_event']})) or "none") + ". "
                  "Always stated: " + (", ".join(f"`{f['id']}`" for f in t["facts"] if f.get("always_stated")) or "none") + ". "
                  f"Defining event `{t['defining_event']}`: never presumed."]
        lines += ["", "### Stops", "", "| stop | when | citation |", "|---|---|---|"]
        for s in t["stops"]:
            lines.append(f"| `{s['id']}` | {cond_text(s['when'])} | {md_rule(s['rule'])} |")
        lines.append("")
    return "\n".join(lines)


def words(c):
    """A condition in plain words for rule_text.md."""
    if c is True:
        return "always"
    if "all" in c:
        return " and ".join(f"({words(x)})" if isinstance(x, dict) and ("all" in x or "any" in x) else words(x) for x in c["all"])
    if "any" in c:
        return " or ".join(words(x) for x in c["any"])
    if "not" in c:
        return f"not ({words(c['not'])})"
    return f"`{c['fact']}` is {'yes' if c['is'] else 'no'}"


def art(locator):
    return locator.replace("CO ", "").replace(" (introduction)", ", introduction")


def rule_text(data):
    out = ["# Rules: end of an employment relationship in Switzerland (dismissal)", "",
           "These rules say which documents a legal-protection insurer requests before it assesses an employee's dispute "
           "about the end of an employment relationship. They come from the Swiss Code of Obligations (CO, SR 220), "
           "consolidated version of 1 October 2026. The German text of the CO is authoritative; German terms are given in "
           "brackets where the English translation is unclear.", "",
           "There are three dispute types. Each type has a defining event, conditions to decide, steps, documents, "
           "presumptions and stops. A step is taken when its condition holds. A document is needed when its step is taken "
           "and its own condition holds; every needed document is mandatory. When a stop applies, the process ends and no "
           "further step of that type is taken. A presumption fills a fact the file does not mention; a statutory "
           "presumption listed under a type comes before the convention below.", "",
           "## Convention of this benchmark (not law)", "",
           "The following rule is a convention of this benchmark, not of the law; no article states it:", "",
           "> " + data["convention"]["text"], ""]
    for n, t in enumerate(data["types"], 1):
        facts = {f["id"]: f for f in t["facts"]}
        d_ev = facts[t["defining_event"]]
        out += [f"## Type {n}: {t['title']}", "", SUMMARIES[t["id"]], "",
                f"Defining event: `{d_ev['id']}`. It is never presumed.", "", "### Conditions", ""]
        for i, f in enumerate(t["facts"], 1):
            always = " Always stated in the file (stated or open, never left unmentioned)." if f.get("always_stated") else ""
            out.append(f"{i}. `{f['id']}`: {f['question']} Not: {f['not_this']} ({art(f['rule']['locator'])}){always}")
        out += ["", "### Stops", ""]
        for s in t["stops"]:
            why = s["rule"].get("inference") or ("“" + s["rule"]["passage"] + "”")
            out.append(f"- If {words(s['when'])}, the process ends. {why} ({art(s['rule']['locator'])})")
        out += ["", "### Steps and documents", ""]
        for i, s in enumerate(t["steps"], 1):
            out.append(f"{i}. {s['title']}. Taken when: {words(s['reached_when'])}. ({art(s['rule']['locator'])})")
            for d in (d for d in t["documents"] if d["step"] == s["id"]):
                need = "always" if d["needed_when"] is True else "only when " + words(d["needed_when"])
                out.append(f"   - {d['title']}, showing: {'; '.join(d['must_show'])}. Needed {need}. "
                           f"({art(d['rule']['locator'])}: {d['rule']['inference']})")
        out += ["", "### Presumptions", ""]
        for p in t["presumptions"]:
            de = p["rule"].get("passage_de", {}).get("passage")
            out.append(f"- `{p['fact']}` not mentioned: taken as {'yes' if p['value'] else 'no'}. {art(p['rule']['locator'])}: "
                       f"“{p['rule']['passage'].rstrip('.')}”" + (f" („{de.rstrip('.')}“)" if de else "") + f". {p['rule']['inference']}")
        out.append("- Under the convention of this benchmark (not law), not mentioned means taken as no: "
                   + ", ".join(f"`{x}`" for x in convention_facts(t)) + ".")
        silent = sorted(stop_on_false(t) - {t["defining_event"]})
        if silent:
            out.append("- Not mentioned leaves the fact unresolved, because its absence would end the process: "
                       + ", ".join(f"`{x}`" for x in silent) + ".")
        always = [f["id"] for f in t["facts"] if f.get("always_stated")]
        if always:
            out.append("- No presumption; always stated in the file: " + ", ".join(f"`{x}`" for x in always) + ".")
        out.append(f"- The defining event `{t['defining_event']}` is never presumed.")
        out.append("")
    return "\n".join(out)


def main():
    data = {"regime": "dismissal", "version": VERSION, "sources": SOURCES + [CONVENTION_SOURCE], "convention": CONVENTION,
            "types": TYPES}
    (REGIME_DIR / "rule_text.md").write_text(rule_text(data), encoding="utf-8")
    (REGIME_DIR / "rules.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (REGIME_DIR / "RULES.md").write_text(rules_md(data), encoding="utf-8")
    for t in TYPES:
        (REGIME_DIR / "workflow" / f"{t['id']}.json").write_text(
            json.dumps(workflow(t), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("built", [t["id"] for t in TYPES])


if __name__ == "__main__":
    main()
