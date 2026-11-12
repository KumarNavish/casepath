"""Build rules.json, RULES.md and workflow/*.json for the tenancy regime.

The rule set is authored here as data. Every rule quotes a passage from a
stored snapshot (sources/sr220-en.txt, with the German of sources/sr220-de.txt
beside it where cited); tools/check.py verifies the quotations.

Run: python3 -I -B tools/build.py  (from the regime directory or anywhere).
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
VERSION = "2026-11-12"
EN, DE = "sr220-en", "sr220-de"


def R(locator, passage, basis, inference=None, de=None, also=None):
    rule = {"source_id": EN, "locator": locator, "passage": passage, "basis": basis}
    if inference:
        rule["inference"] = inference
    if de:
        rule["passage_de"] = {"source_id": DE, "passage": de}
    if also:
        rule["also"] = also  # further passages the rule relies on, each checked like the main one
    return rule


def F(id, question, not_this, rule, always_stated=False):
    f = {"id": id, "question": question, "not_this": not_this, "type": "boolean", "rule": rule}
    if always_stated:
        f["always_stated"] = True
    return f


def S(id, title, reached_when, rule):
    return {"id": id, "title": title, "reached_when": reached_when, "rule": rule}


def D(id, title, step, needed_when, must_show, rule, mandatory=True):
    return {"id": id, "title": title, "step": step, "needed_when": needed_when, "mandatory": mandatory,
            "must_show": must_show, "rule": rule}


def is_(fact, value=True):
    return {"fact": fact, "is": value}


def all_(*conds):
    return {"all": list(conds)}


def any_(*conds):
    return {"any": list(conds)}


# ---------------------------------------------------------------- passages used more than once
P259A1 = ("Where defects arise in the object which are not attributable to the tenant or lessee and which he is not "
          "obliged to remedy at his own expense, or where he is prevented from using the object as contractually agreed, "
          "he may require that the landlord or lessor:")
P259A1_DE = ("Entstehen an der Sache Mängel, die der Mieter weder zu verantworten noch auf eigene Kosten zu beseitigen hat, "
             "oder wird der Mieter im vertragsgemässen Gebrauch der Sache gestört, so kann er verlangen, dass der Vermieter:")
P259D = ("Where the object is rendered unfit or less fit for its designated use, the tenant or lessee may require the "
         "landlord or lessor to reduce the rent proportionately from the time when the landlord or lessor became aware of "
         "the defect until the defect is remedied.")
P259D_DE = ("Wird die Tauglichkeit der Sache zum vorausgesetzten Gebrauch beeinträchtigt oder vermindert, so kann der Mieter "
            "vom Vermieter verlangen, dass er den Mietzins vom Zeitpunkt, in dem er vom Mangel erfahren hat, bis zur Behebung "
            "des Mangels entsprechend herabsetzt.")
P259E = ("Where the defect has caused damage to the tenant or lessee, the landlord or lessor is liable in damages unless he "
         "can prove that he was not at fault.")
P259E_DE = ("Hat der Mieter durch den Mangel Schaden erlitten, so muss ihm der Vermieter dafür Ersatz leisten, wenn er nicht "
            "beweist, dass ihn kein Verschulden trifft.")
P259H1 = ("The landlord becomes entitled to the rent paid on deposit if the tenant or lessee does not bring claims against "
          "him before the conciliation authority within 30 days of the due date for the first rent payment paid into deposit.")
P259H1_DE = ("Hinterlegte Mietzinse fallen dem Vermieter zu, wenn der Mieter seine Ansprüche gegenüber dem Vermieter nicht "
             "innert 30 Tagen seit Fälligkeit des ersten hinterlegten Mietzinses bei der Schlichtungsbehörde geltend gemacht hat.")
P273_1 = ("A party wishing to challenge termination must bring the matter before the conciliation authority within 30 days "
          "of receiving the notice of termination.")
P273_1_DE = ("Will eine Partei die Kündigung anfechten, so muss sie das Begehren innert 30 Tagen nach Empfang der Kündigung "
             "der Schlichtungsbehörde einreichen.")
P266N = ("Notice of termination given by the landlord and any notification of a time limit for payment accompanied by a "
         "warning of termination in the event of non-payment (Art. 257d) must be served separately on the tenant and on his "
         "spouse or registered partner.")
P266N_DE = ("Die Kündigung durch den Vermieter sowie die Ansetzung einer Zahlungsfrist mit Kündigungsandrohung (Art. 257d) "
            "sind dem Mieter und seinem Ehegatten, seiner eingetragenen Partnerin oder seinem eingetragenen Partner separat "
            "zuzustellen.")
P271A1A = ("Notice of termination served by the landlord may be challenged in particular where it is given:\n"
           "a. because the tenant is asserting claims arising under the lease in good faith;")
P271A1A_DE = ("Die Kündigung durch den Vermieter ist insbesondere anfechtbar, wenn sie ausgesprochen wird:\n"
              "a. weil der Mieter nach Treu und Glauben Ansprüche aus dem Mietverhältnis geltend macht;")
P257D2 = ("In the event of non-payment within the time limit the landlord or lessor may terminate the contract with "
          "immediate effect or, for leases of residential and commercial premises, subject to at least 30 days’ notice "
          "ending on the last day of a calendar month.")
P257D2_DE = ("Bezahlt der Mieter innert der gesetzten Frist nicht, so kann der Vermieter fristlos, bei Wohn- und "
             "Geschäftsräumen mit einer Frist von mindestens 30 Tagen auf Ende eines Monats kündigen.")
P272_1 = ("The tenant may request the extension of a fixed-term or open-ended lease where termination of the lease would "
          "cause a degree of hardship for him or his family that cannot be justified by the interests of the landlord.")
P272_1_DE = ("Der Mieter kann die Erstreckung eines befristeten oder unbefristeten Mietverhältnisses verlangen, wenn die "
             "Beendigung der Miete für ihn oder seine Familie eine Härte zur Folge hätte, die durch die Interessen des "
             "Vermieters nicht zu rechtfertigen wäre.")
P270B1 = ("Within 30 days of receiving notice of a rent increase, the tenant may challenge it before the conciliation "
          "authority as unfair within the meaning of Articles 269 and 269a.")
P270B1_DE = ("Der Mieter kann eine Mietzinserhöhung innert 30 Tagen, nachdem sie ihm mitgeteilt worden ist, bei der "
             "Schlichtungsbehörde als missbräuchlich im Sinne der Artikel 269 und 269a anfechten.")
P269D1B = ("He must give notice of and reasons for the rent increase at least ten days before the beginning of the notice "
           "period for termination using a form approved by the canton.")
P269D1B_DE = ("Er muss dem Mieter die Mietzinserhöhung mindestens zehn Tage vor Beginn der Kündigungsfrist auf einem vom "
              "Kanton genehmigten Formular mitteilen und begründen.")
P269D2C = "c. notice of the increase is accompanied by notice to terminate or a threat of termination."
P269D2C_DE = "c. mit der Mitteilung die Kündigung androht oder ausspricht."


# ---------------------------------------------------------------- passages added in reconciliation
P257G1 = ("On learning of defects which he himself is not obliged to remedy, the tenant or lessee must inform the "
          "landlord or lessor.")
P257G1_DE = "Der Mieter muss Mängel, die er nicht selber zu beseitigen hat, dem Vermieter melden."
P257G2 = "Failure to notify renders the tenant or lessee liable for any damage incurred by the landlord or lessor as a result."
P257G2_DE = "Unterlässt der Mieter die Meldung, so haftet er für den Schaden, der dem Vermieter daraus entsteht."
P259B = "Where the landlord is aware of a defect and fails to remedy it within a reasonable time, the tenant may:"
P259B_DE = "Kennt der Vermieter einen Mangel und beseitigt er ihn nicht innert angemessener Frist, so kann der Mieter:"
P266M1 = "Where the leased property serves as the family residence"
P266M1_DE = "Dient die gemietete Sache als Wohnung der Familie"
P266M3 = "The same provisions apply mutatis mutandis to registered partners."
P273_5 = ("Where the competent authority rejects a request made by the tenant relating to challenging termination, it must "
          "examine ex officio whether the lease may be extended.")
P273_5_DE = ("Weist die zuständige Behörde ein Begehren des Mieters betreffend Anfechtung der Kündigung ab, so prüft sie von "
             "Amtes wegen, ob das Mietverhältnis erstreckt werden kann.")
P271_2 = "On request, reasons for giving notice must be stated."
P271_2_DE = "Die Kündigung muss auf Verlangen begründet werden."
P269D5 = "In the case of a rent increase in accordance with an agreement under Article 269c, it is sufficient that notice be given in writing."
P269D5_DE = "Für die Mitteilung von Mietzinserhöhungen, die in einer Vereinbarung nach Artikel 269c vorgesehen sind, genügt die schriftliche Form."
P269D2A = "The rent increase is void where:\na. it is not communicated using the prescribed form;"
P269D2A_DE = "Die Mietzinserhöhung ist nichtig, wenn der Vermieter:\na. sie nicht mit dem vorgeschriebenen Formular mitteilt;"
P266L1 = "Notice to terminate leases of residential and commercial premises must be given in writing."
P266L1_DE = "Vermieter und Mieter von Wohn- und Geschäftsräumen müssen schriftlich kündigen."
HEADING_266N = ("[marginal heading: End of lease / Required form of notice for residential and commercial premises / "
                "Family residence / Notice given by the landlord]")


def A(locator, passage, de=None):
    """A further passage a rule relies on (checked like the main passage)."""
    out = {"source_id": EN, "locator": locator, "passage": passage}
    if de:
        out["passage_de"] = {"source_id": DE, "passage": de}
    return out


# ---------------------------------------------------------------- type 1: defect
defect = {
    "id": "defect_mold_heating",
    "title": "Defect of the rented dwelling (mould, damp, heating)",
    "defining_event": "defect_present",
    "facts": [
        F("defect_present",
          "Does the claim state that the rented dwelling has a defect (for example mould, damp, or heating that fails) "
          "or that the tenant is disturbed in using the dwelling as agreed, without the claim itself saying that the tenant "
          "alone caused the defect or must remedy it at his own expense?",
          "A defect the claim itself attributes wholly to the tenant, or says he must remedy at his own expense, is no. "
          "A cause the claim calls shared or disputed is open, not no; a landlord's allegation that the tenant caused it, "
          "which the claim disputes, does not make this no.",
          R("Art. 259a para. 1", P259A1, "states", de=P259A1_DE,
            inference="The German text is authoritative: 'im vertragsgemässen Gebrauch der Sache gestört' (disturbed in "
                      "the contractual use) is wider than the English 'prevented from using'; the question follows the German.")),
        F("landlord_unaware",
          "Does the claim state that the landlord does not yet know of the defect (the tenant has not reported it and the "
          "landlord has not learned of it in another way)?",
          "A landlord who learned of the defect from the caretaker, the property manager or an inspection, although the "
          "tenant never wrote: that landlord knows, so the answer is no.",
          R("Art. 257g para. 2", P257G2, "follows",
            "A failure to notify is what the landlord raises (para. 2 attaches liability to it); the tenant's remedies turn "
            "on the landlord being aware of the defect (art. 259b), so a landlord who does not yet know is the exceptional "
            "case that removes the proof of the landlord's knowledge.", de=P257G2_DE,
            also=[A("Art. 259b", P259B, P259B_DE)])),
        F("notice_oral_only",
          "Does the claim state that the landlord learned of the defect only orally, so that no written notice, written "
          "acknowledgement or inspection record of it exists?",
          "A tenant who told the landlord by telephone and later confirmed it by letter, e-mail or text message: a written "
          "trace exists, so the answer is no.",
          R("Art. 257g para. 1", P257G1, "follows",
            "The duty to inform prescribes no form (German: 'melden'), so the landlord may have been informed orally, and "
            "then no written proof of his knowledge can be produced.", de=P257G1_DE)),
        F("damages_claimed",
          "Does the tenant claim compensation from the landlord for damage the defect caused to the tenant (for example "
          "damaged furniture or clothing, or extra costs)?",
          "A reduction of the rent for the reduced use of the dwelling (art. 259d), which is not compensation for damage.",
          R("Art. 259e", P259E, "states", de=P259E_DE)),
        F("deposit_intended",
          "Does the claim state that the tenant intends to pay the rent on deposit with the office designated by the "
          "canton instead of to the landlord, or has begun to do so?",
          "Withholding or reducing the rent without paying it to a deposit office; the rental security paid at the start "
          "of the lease.",
          R("Art. 259a para. 2", "In addition, a tenant of immovable property may pay rent on deposit rather than to the "
            "landlord.", "states", de="Der Mieter einer unbeweglichen Sache kann zudem den Mietzins hinterlegen.")),
        F("rent_deposited",
          "Does the claim state that at least one rent payment has already been paid into deposit with the office "
          "designated by the canton?",
          "A deposit that is announced or planned but not yet made; the rental security paid at the start of the lease.",
          R("Art. 259h para. 1", P259H1, "follows",
            "Once rent has been deposited, claims must be brought before the conciliation authority within 30 days of the "
            "due date of the first deposited rent, so whether a deposit has been made decides whether that must be shown.",
            de=P259H1_DE)),
    ],
    "steps": [
        S("dh_scope", "Establish the defect and the agreed use of the dwelling", is_("defect_present"),
          R("Art. 256 para. 1",
            "The landlord or lessor is required to make the object available on the agreed date in a condition fit for its "
            "designated use and to maintain it in that condition.", "follows",
            "Whether the dwelling is defective is measured against its designated use, so the defect and the agreed use "
            "are established once a defect is stated.",
            de="Der Vermieter ist verpflichtet, die Sache zum vereinbarten Zeitpunkt in einem zum vorausgesetzten Gebrauch "
               "tauglichen Zustand zu übergeben und in demselben zu erhalten.")),
        S("dh_notice", "Establish how and when the landlord learned of the defect",
          all_(is_("defect_present"), is_("landlord_unaware", False)),
          R("Art. 259b", P259B, "follows",
            "The tenant's remedies under art. 259b depend on the landlord's knowledge, so when the landlord learned of the "
            "defect is established.", de=P259B_DE)),
        S("dh_damage", "Establish the damage claimed", all_(is_("defect_present"), is_("damages_claimed")),
          R("Art. 259e", P259E, "follows",
            "The landlord is liable for damage the defect caused, so a claim for damages requires the damage to be "
            "established.", de=P259E_DE)),
        S("dh_deposit", "Check the preconditions and the time limit of the rent deposit",
          all_(is_("defect_present"), is_("deposit_intended")),
          R("Art. 259g para. 1", "He must notify the landlord in writing of his intention to pay rent on deposit.",
            "follows", "Paying rent on deposit is subject to written steps toward the landlord, so they are checked when "
            "a deposit is intended or made.", de="Er muss die Hinterlegung dem Vermieter schriftlich ankündigen.")),
    ],
    "documents": [
        D("lease_contract", "Lease contract", "dh_scope", True,
          ["parties", "rented dwelling", "agreed use of the dwelling"],
          R("Art. 256 para. 1",
            "The landlord or lessor is required to make the object available on the agreed date in a condition fit for its "
            "designated use and to maintain it in that condition.", "evidence",
            "The landlord's duty is measured by the designated use; the lease records the rented dwelling and its agreed use.",
            de="Der Vermieter ist verpflichtet, die Sache zum vereinbarten Zeitpunkt in einem zum vorausgesetzten Gebrauch "
               "tauglichen Zustand zu übergeben und in demselben zu erhalten.")),
        D("defect_record", "Record of the defect (dated photographs, inspection or expert report)", "dh_scope", True,
          ["the defect and where it is", "date observed", "how the use of the dwelling is affected"],
          R("Art. 259a para. 1", P259A1, "evidence",
            "The tenant's rights arise where a defect arises or the agreed use is disturbed; dated photographs or an "
            "inspection report ordinarily prove that the defect exists, where it is and since when.", de=P259A1_DE)),
        D("knowledge_proof",
          "Proof of when the landlord learned of the defect (tenant's dated notice, landlord's or manager's acknowledgement, "
          "or inspection record)", "dh_notice", is_("notice_oral_only", False),
          ["how and when the landlord learned of the defect", "the defect reported", "who was informed"],
          R("Art. 259b", P259B, "evidence",
            "The remedies depend on the landlord being aware of the defect, and a reduction runs from the time he became "
            "aware (art. 259d); a dated written notice, a written acknowledgement or an inspection record ordinarily "
            "proves when that was. Where the claim states that the landlord was told only orally, no such record exists "
            "and none is requested.", de=P259B_DE,
            also=[A("Art. 259d", P259D, P259D_DE)])),
        D("damage_evidence", "Proof of the damage (invoices, receipts, photographs of damaged items)", "dh_damage", True,
          ["damaged items or costs", "amount", "connection to the defect"],
          R("Art. 259e", P259E, "evidence",
            "Liability covers damage the defect caused; invoices, receipts and photographs of damaged items ordinarily "
            "prove the damage and its amount.", de=P259E_DE)),
        D("deposit_deadline_notice", "Tenant's written time limit to the landlord and written announcement of the deposit",
          "dh_deposit", True,
          ["repair requested", "time limit set", "announcement that rent will be deposited", "date and addressee"],
          R("Art. 259g para. 1",
            "A tenant of immovable property requesting that a defect be remedied must, in writing, set the landlord a "
            "reasonable time limit within which to comply with such request", "evidence",
            "The time limit (and the announcement of the deposit) must be in writing, so the tenant's letter itself is the "
            "proof that they were given and when.",
            de="Verlangt der Mieter einer unbeweglichen Sache vom Vermieter die Beseitigung eines Mangels, so muss er ihm "
               "dazu schriftlich eine angemessene Frist setzen")),
        D("deposit_receipt",
          "Receipt of the deposit office for the deposited rent and the tenant's application to the conciliation authority",
          "dh_deposit", is_("rent_deposited"),
          ["amount deposited", "due date of the first deposited rent",
           "date the claims were brought before the conciliation authority (or that they have not yet been)"],
          R("Art. 259h para. 1", P259H1, "evidence",
            "The deposited rent passes to the landlord unless claims are brought before the conciliation authority within "
            "30 days of the due date of the first deposited rent; the deposit office's receipt shows that due date and the "
            "application shows whether and when the claims were brought.", de=P259H1_DE)),
    ],
    "presumptions": [],
    "stops": [
        {"when": is_("defect_present", False),
         "rule": R("Art. 259a para. 1", P259A1, "follows",
                   "The tenant's rights in this type arise only where a defect not attributable to the tenant arises or the "
                   "agreed use is disturbed; where the claim states neither, or attributes the defect wholly to the tenant, "
                   "no such right is engaged and the process ends. A shared or disputed cause is open and does not stop.",
                   de=P259A1_DE)},
    ],
}

# ---------------------------------------------------------------- type 2: termination
termination = {
    "id": "lease_termination_dispute",
    "title": "Termination of the lease by the landlord",
    "defining_event": "notice_received",
    "facts": [
        F("notice_received",
          "Has the landlord given the tenant notice terminating the lease of the dwelling, and has it reached the tenant?",
          "No: only a file stating that no notice of termination has been given at all (also a lease of limited duration "
          "that simply ends on its agreed date, a termination only announced or threatened, a notice given by the tenant). "
          "A notice the landlord says was sent and the tenant says never reached him is open, not no.",
          R("Art. 273 para. 1", P273_1, "follows",
            "The challenge and its 30-day period run from receipt of a notice of termination, so a received notice is the "
            "event that opens this type; disputed receipt leaves the event open.", de=P273_1_DE)),
        F("family_residence",
          "Does the claim state that the tenant is married or in a registered partnership and that the rented dwelling "
          "serves as the family home?",
          "A tenant living with a partner who is neither spouse nor registered partner; spouses who do not use the "
          "dwelling as their family home.",
          R("Art. 266m para. 1", P266M1, "follows",
            "Arts. 266m and 266n stand under the marginal heading 'Family residence' (Wohnung der Familie); art. 266m "
            "para. 1 states the condition, para. 3 extends it to registered partners, and art. 266n requires the "
            "landlord's notice to be served separately on the spouse or registered partner. The condition therefore is a "
            "family home of spouses or registered partners.", de=P266M1_DE,
            also=[A("Art. 266m para. 3", P266M3, "Die gleiche Regelung gilt bei eingetragenen Partnerschaften sinngemäss."),
                  A("Art. 266n", P266N, P266N_DE)])),
        F("arrears_termination",
          "Does the notice or the claim state that the landlord terminated because the tenant did not pay overdue rent or "
          "accessory charges within a time limit the landlord had set?",
          "Arrears that the claim mentions while the notice is given for another reason (for example the landlord's own "
          "use); a dispute about a rent increase.",
          R("Art. 257d para. 2", P257D2, "states", de=P257D2_DE)),
        F("asserted_claims",
          "Does the claim state that the landlord gave notice because the tenant had, in good faith, asserted claims under "
          "the lease (for example demanded repair of a defect or contested the rent)?",
          "Claims the tenant asserted that the claim does not connect with the notice; a notice the claim attributes to "
          "another reason, such as the landlord's own use.",
          R("Art. 271a para. 1 let. a", P271A1A, "states", de=P271A1A_DE)),
        F("extension_requested",
          "Does the tenant seek an extension of the lease because having to leave by the end date would be a hardship for "
          "the tenant or the tenant's family?",
          "A tenant who only contests the validity of the notice and does not ask for more time; a request for more time "
          "that the claim does not base on hardship.",
          R("Art. 272 para. 1", P272_1, "states", de=P272_1_DE)),
    ],
    "steps": [
        S("lt_form", "Check the form of the notice, the notice period and the challenge deadline", is_("notice_received"),
          R("Art. 266o", "Notice of termination is void if it does not conform to Articles 266l–266n.", "follows",
            "A received notice is void if it does not conform to arts. 266l–266n, so its form and service are checked first.",
            de="Die Kündigung ist nichtig, wenn sie den Artikeln 266l–266n nicht entspricht.")),
        S("lt_family", "Check separate service on the spouse or registered partner",
          all_(is_("notice_received"), is_("family_residence")),
          R("Art. 266n", P266N, "follows",
            "The passage states the duty of separate service; the family-home condition under which the step is reached "
            "comes from the marginal heading 'Family residence' and art. 266m para. 1 (see family_residence).",
            de=P266N_DE, also=[A("Art. 266m para. 1", P266M1, P266M1_DE)])),
        S("lt_arrears", "Check the payment time limit that preceded the notice and the payments made within it",
          all_(is_("notice_received"), is_("arrears_termination")),
          R("Art. 257d para. 1",
            "Where, having accepted the property, the tenant or lessee is in arrears with payments of rent or accessory "
            "charges, the landlord or lessor may set a time limit for payment", "follows",
            "A termination for arrears presupposes a time limit for payment set beforehand (in writing: 'schriftlich' in "
            "the German, missing from the English), so that time limit is checked.",
            de="Ist der Mieter nach der Übernahme der Sache mit der Zahlung fälliger Mietzinse oder Nebenkosten im "
               "Rückstand, so kann ihm der Vermieter schriftlich eine Zahlungsfrist setzen")),
        S("lt_good_faith", "Check whether the notice can be challenged as contrary to good faith", is_("notice_received"),
          R("Art. 271 para. 1", "Notice of termination may be challenged where it contravenes the principle of good faith.",
            "follows",
            "Any received notice can be challenged on this ground, so the step is reached whenever a notice was received; "
            "the documents it needs depend on the grounds the claim states.",
            de="Die Kündigung ist anfechtbar, wenn sie gegen den Grundsatz von Treu und Glauben verstösst.")),
        S("lt_extension", "Assess an extension of the lease",
          all_(is_("notice_received"), is_("arrears_termination", False)),
          R("Art. 272a para. 1 let. a",
            "No extension is granted where notice of termination is given:\n"
            "a. because the tenant is in default on his payments (Art. 257d);", "follows",
            "An extension can be at issue after any received notice, whether the tenant requests it or the authority "
            "examines it ex officio after rejecting a challenge (art. 273 para. 5); this passage excludes it where notice "
            "was given for arrears.",
            de="Die Erstreckung ist ausgeschlossen bei Kündigungen:\na. wegen Zahlungsrückstand des Mieters (Art. 257d);",
            also=[A("Art. 273 para. 5", P273_5, P273_5_DE)])),
    ],
    "documents": [
        D("lease_contract", "Lease contract", "lt_form", True,
          ["parties", "rented dwelling", "duration (limited or indefinite)", "agreed notice periods and termination dates"],
          R("Art. 266a para. 1",
            "The parties may give notice to terminate a lease of indefinite duration by observing the legally prescribed "
            "notice periods and termination dates, except where they have agreed a longer notice period or a different "
            "termination date.", "evidence",
            "Whether the notice respects the notice period and termination date depends on what the parties agreed; the "
            "lease records the duration and any agreed periods and dates.",
            de="Die Parteien können das unbefristete Mietverhältnis unter Einhaltung der gesetzlichen Fristen und Termine "
               "kündigen, sofern sie keine längere Frist oder keinen anderen Termin vereinbart haben.")),
        D("termination_notice", "Landlord's notice of termination", "lt_form", True,
          ["sender and addressee", "date", "termination date", "given in writing",
           "whether the form approved by the canton is used"],
          R("Art. 266l para. 2",
            "The landlord must give notice of termination using a form approved by the canton which informs the tenant how "
            "he must proceed if he wishes to contest the termination or apply for an extension of the lease.", "evidence",
            "The landlord's notice must be given on a form approved by the canton (and in writing, art. 266l para. 1); "
            "only the notice itself shows whether it was.",
            de="Der Vermieter muss mit einem Formular kündigen, das vom Kanton genehmigt ist und das angibt, wie der Mieter "
               "vorzugehen hat, wenn er die Kündigung anfechten oder eine Erstreckung des Mietverhältnisses verlangen will.",
            also=[A("Art. 266l para. 1", P266L1, P266L1_DE)])),
        D("proof_of_receipt", "Proof of the date the notice was received", "lt_form", True,
          ["date of receipt", "how it was delivered (registered-mail tracking, envelope or acknowledgement)"],
          R("Art. 273 para. 1", P273_1, "evidence",
            "The challenge must be brought within 30 days of receiving the notice; proof of the date of receipt is needed "
            "to check that period.", de=P273_1_DE)),
        D("spouse_service",
          "Proof of separate service on the spouse or registered partner (the spouse's own copy with envelope or tracking), "
          "or the spouse's statement that no separate copy was received", "lt_family", True,
          ["addressed to the spouse or registered partner", "served separately from the tenant's copy", "date",
           "where the notice followed a payment time limit (art. 257d): the separately served copy of that time limit"],
          R("Art. 266n", P266N, "evidence",
            "Separate service on the spouse or registered partner is required (a notice that does not conform is void, "
            "art. 266o); the spouse's own copy ordinarily proves it was made, and the spouse's statement records that it "
            "was not.", de=P266N_DE)),
        D("payment_demand",
          "Landlord's written payment time limit with warning of termination, and the tenant's record of payments made "
          "within it", "lt_arrears", True,
          ["amount in arrears", "time limit set and date it was received", "warning that the lease will be terminated",
           "payments made within the time limit (bank or postal records)"],
          R("Art. 257d para. 2", P257D2, "evidence",
            "Termination is open to the landlord only after non-payment within the time limit; the landlord's written "
            "time limit shows the limit and the warning, and the tenant's payment records show whether payment was made "
            "within it.", de=P257D2_DE,
            also=[A("Art. 257d para. 1",
                    "the landlord or lessor may set a time limit for payment and notify him that in the event of "
                    "non-payment the landlord or lessor will terminate the lease on expiry of that time limit. The minimum "
                    "time limit is ten days, and 30 days for leases of residential or commercial premises.",
                    "so kann ihm der Vermieter schriftlich eine Zahlungsfrist setzen und ihm androhen, dass bei unbenütztem "
                    "Ablauf der Frist das Mietverhältnis gekündigt werde. Diese Frist beträgt mindestens zehn Tage, bei "
                    "Wohn- und Geschäftsräumen mindestens 30 Tage.")])),
        D("claims_and_reasons", "Correspondence on the tenant's claims and the landlord's reasons for the notice",
          "lt_good_faith", is_("asserted_claims"),
          ["claims the tenant asserted (for example a repair demand or a rent challenge), with dates",
           "the reasons the landlord gave for the notice (on the notice, or given on request)",
           "conciliation or court documents on those claims, if any"],
          R("Art. 271a para. 1 let. a", P271A1A, "evidence",
            "The notice may be challenged where it was given because the tenant asserted claims; the tenant's dated "
            "letters show which claims were asserted and when, and the landlord's stated reasons (which must be given on "
            "request, art. 271 para. 2) show the ground he relies on.", de=P271A1A_DE,
            also=[A("Art. 271 para. 2", P271_2, P271_2_DE)])),
        D("hardship_evidence", "Evidence of the tenant's personal, family and financial circumstances", "lt_extension",
          is_("extension_requested"),
          ["household members", "financial circumstances", "personal or health circumstances"],
          R("Art. 272 para. 2 let. c",
            "c. the personal, family and financial circumstances of the parties, as well as their conduct;", "evidence",
            "In weighing an extension the authority has particular regard to the parties' personal, family and financial "
            "circumstances; documents of the tenant's circumstances ordinarily prove them. They are requested where the "
            "tenant seeks an extension. Not requesting them when the authority would examine an extension only ex officio "
            "(art. 273 para. 5) is this rule set's choice; that paragraph does not say so.",
            de="c. die persönlichen, familiären und wirtschaftlichen Verhältnisse der Parteien und deren Verhalten;")),
    ],
    "presumptions": [],
    "stops": [
        {"when": is_("notice_received", False),
         "rule": R("Art. 273 para. 1", P273_1, "follows",
                   "The challenge runs from receipt of a notice of termination; where the claim states that the landlord "
                   "gave no notice of termination there is nothing to challenge and the process ends. A notice whose "
                   "receipt is disputed is open and does not stop. Not covered: a lease of limited duration ending without "
                   "notice, where an extension may be requested under art. 273 para. 2 let. b; that is outside this type.",
                   de=P273_1_DE)},
    ],
}

# ---------------------------------------------------------------- type 3: rent increase
rent = {
    "id": "rent_increase_dispute",
    "title": "Rent increase",
    "defining_event": "increase_applied",
    "facts": [
        F("increase_applied",
          "Does the claim state that the landlord has announced, demanded or charged a higher rent for the dwelling, by a "
          "notice, a letter, an invoice or otherwise (whether or not on an official form)?",
          "A landlord's plan to raise the rent that has not been announced, demanded or charged; the initial rent agreed "
          "for a new lease; new accessory charges or reduced services without a higher rent.",
          R("Art. 269d para. 2 let. a", P269D2A, "follows",
            "An increase not communicated on the prescribed form is void, so an increase the landlord applies or "
            "announces without a proper notice is still a rent-increase dispute; the type opens with any announced, "
            "demanded or charged increase.", de=P269D2A_DE)),
        F("graduated_rent",
          "Does the claim state that the increase is a step fixed in advance in the lease, by which the rent rises "
          "periodically by fixed amounts (graduated rent)?",
          "An increase under an index clause; an increase the lease does not fix in advance.",
          R("Art. 270d", "Without prejudice to the right to challenge the initial rent, the tenant may not challenge "
            "periodical rent increases.", "follows",
            "A periodical increase agreed under art. 269c cannot be challenged as unfair, so the documents for testing "
            "unfairness are not needed; the agreement's validity and the notice remain to be checked. This holds only for "
            "a valid agreement (art. 269c); the rule set does not route an invalid one back to the unfairness check.",
            de="Unter Vorbehalt der Anfechtung des Anfangsmietzinses kann der Mieter gestaffelte Mietzinse nicht anfechten.")),
        F("index_clause",
          "Does the claim state that the increase applies a clause of the lease linking the rent to an index (such as the "
          "Swiss consumer price index)?",
          "An increase the landlord justifies by general inflation or by cost increases without an index clause in the "
          "lease.",
          R("Art. 270c",
            "Without prejudice to the right to challenge the initial rent, a party may argue before the conciliation "
            "authority only that the rent increase or reduction requested by the other party is not justified by a "
            "corresponding change in the index.", "follows",
            "Under an index clause the only argument is whether the index changed correspondingly, so documents of cost "
            "increases are not needed.",
            de="Unter Vorbehalt der Anfechtung des Anfangsmietzinses kann eine Partei vor der Schlichtungsbehörde nur "
               "geltend machen, dass die von der andern Partei verlangte Erhöhung oder Herabsetzung des Mietzinses durch "
               "keine entsprechende Änderung des Indexes gerechtfertigt sei.")),
        F("cost_or_services_reason",
          "Does the increase notice give, as its reason, higher costs for the landlord (for example higher mortgage "
          "interest or operating costs) or additional services or works by the landlord (for example a renovation)?",
          "An increase justified only by rents customary in the locality (art. 269a let. a) or by inflation on the risk "
          "capital (art. 269a let. e).",
          R("Art. 269a let. b",
            "b. they are justified by increases in costs or by additional services provided by the landlord;", "follows",
            "Where the notice relies on cost increases or additional services, whether the increase is justified by them "
            "bears on whether it is unfair (art. 269a: 'in general' not unfair, German 'in der Regel'). Always stated: an "
            "increase notice must give reasons (art. 269d para. 1), and cost reasons and other reasons (such as local "
            "customary rents, art. 269a let. a) are both ordinary, so neither is a default.",
            de="b. durch Kostensteigerungen oder Mehrleistungen des Vermieters begründet sind;"), always_stated=True),
        F("termination_with_increase",
          "Does the claim state that, together with the rent increase, the landlord gave notice of termination?",
          "A threat of termination without a notice of termination (it shows on the increase notice or its covering "
          "letter, which is requested anyway); a notice of termination given separately at another time.",
          R("Art. 269d para. 2 let. c", P269D2C, "follows",
            "The passage voids an increase accompanied by a notice or a threat of termination; this fact covers the notice "
            "only, because only a notice is a separate document to request (a threat is read from the increase notice).",
            de=P269D2C_DE)),
    ],
    "steps": [
        S("ri_form", "Check the form, reasons and timing of the increase", is_("increase_applied"),
          R("Art. 269d para. 1", P269D1B, "follows",
            "An increase must be notified with reasons, in time and on the approved form, so these are checked first; for "
            "a graduated-rent step, written form suffices instead of the form (art. 269d para. 5).", de=P269D1B_DE,
            also=[A("Art. 269d para. 5", P269D5, P269D5_DE)])),
        S("ri_graduated", "Check the graduated-rent agreement",
          all_(is_("increase_applied"), is_("graduated_rent")),
          R("Art. 269c",
            "An agreement to increase the rent periodically by fixed amounts is valid only where:\n"
            "a. the lease is contracted for at least three years;\n"
            "b. the rent is increased no more than once a year; and\n"
            "c. the amount by which it is increased is fixed in francs.", "states",
            de="Die Vereinbarung, dass sich der Mietzins periodisch um einen bestimmten Betrag erhöht, ist nur gültig, "
               "wenn:\na. der Mietvertrag für mindestens drei Jahre abgeschlossen wird;\nb. der Mietzins höchstens einmal "
               "jährlich erhöht wird; und\nc. der Betrag der Erhöhung in Franken festgelegt wird.")),
        S("ri_index", "Check the index clause",
          all_(is_("increase_applied"), is_("graduated_rent", False), is_("index_clause")),
          R("Art. 269b",
            "An agreement to link rent to an index is valid only where the lease is contracted for at least five years and "
            "the benchmark is the Swiss consumer prices index.", "states",
            de="Die Vereinbarung, dass der Mietzins einem Index folgt, ist nur gültig, wenn der Mietvertrag für mindestens "
               "fünf Jahre abgeschlossen und als Index der Landesindex der Konsumentenpreise vorgesehen wird.")),
        S("ri_reason", "Check whether the increase is justified by its stated reasons",
          all_(is_("increase_applied"), is_("graduated_rent", False), is_("index_clause", False)),
          R("Art. 270b para. 1", P270B1, "follows",
            "An increase that is neither a graduated step (art. 270d) nor index-linked (art. 270c) can be challenged as "
            "unfair under arts. 269 and 269a, so its reasons are tested.", de=P270B1_DE)),
        S("ri_threat", "Check the notice of termination given with the increase",
          all_(is_("increase_applied"), is_("termination_with_increase")),
          R("Art. 269d para. 2 let. c", P269D2C, "states", de=P269D2C_DE)),
    ],
    "documents": [
        D("lease_contract", "Lease contract", "ri_form", True,
          ["parties", "rented dwelling", "termination dates", "any graduated-rent or index clause"],
          R("Art. 269d para. 1",
            "The landlord may at any time increase the rent with effect from the next termination date.", "evidence",
            "The increase can take effect only from the next termination date; the lease records the termination dates "
            "(and any graduated-rent or index clause, arts. 269b–269c).",
            de="Der Vermieter kann den Mietzins jederzeit auf den nächstmöglichen Kündigungstermin erhöhen.")),
        D("rent_increase_notice", "Landlord's rent increase notice (with any covering letter)", "ri_form", True,
          ["old and new rent", "date from which the increase applies", "reasons given",
           "whether the form approved by the canton is used (for a graduated-rent step, whether it is in writing: "
           "art. 269d para. 5)",
           "any threat of termination in it or in the covering letter",
           "for an index-linked increase: the old and new index values",
           "if the landlord gave no notice at all, that absence is itself the finding (art. 269d para. 2 let. a)"],
          R("Art. 269d para. 2 let. a–b",
            "The rent increase is void where:\na. it is not communicated using the prescribed form;\nb. no reasons are "
            "given;", "evidence",
            "An increase is void without the prescribed form or without reasons; only the notice itself shows the form "
            "used and the reasons given, and where no notice exists its absence is the point to establish.",
            de="Die Mietzinserhöhung ist nichtig, wenn der Vermieter:\na. sie nicht mit dem vorgeschriebenen Formular "
               "mitteilt;\nb. sie nicht begründet;", also=[A("Art. 269d para. 5", P269D5, P269D5_DE)])),
        D("proof_of_receipt", "Proof of the date the notice was received", "ri_form", True,
          ["date of receipt", "how it was delivered (registered-mail tracking, envelope or acknowledgement)"],
          R("Art. 270b para. 1", P270B1, "evidence",
            "The challenge runs 30 days from receiving the notice (German: from its being communicated); proof of the "
            "date of receipt is needed to check that period, and it also shows when the notice was given relative to the "
            "ten-day rule of art. 269d para. 1.", de=P270B1_DE,
            also=[A("Art. 269d para. 1", P269D1B, P269D1B_DE)])),
        D("cost_breakdown",
          "Landlord's breakdown of the cost increases or additional services, with the supporting invoices, interest "
          "notices or cost statements", "ri_reason", is_("cost_or_services_reason"),
          ["costs or works relied on", "amounts", "share passed on to the rent", "supporting invoices or statements"],
          R("Art. 269a let. b",
            "b. they are justified by increases in costs or by additional services provided by the landlord;", "evidence",
            "A rent justified by cost increases or additional services is in general not unfair; the underlying invoices, "
            "interest notices or cost statements, with the landlord's breakdown, ordinarily show whether the increase is "
            "so justified.",
            de="b. durch Kostensteigerungen oder Mehrleistungen des Vermieters begründet sind;")),
        D("termination_notice", "Landlord's notice of termination", "ri_threat", True,
          ["sender and addressee", "date", "termination date", "connection to the rent increase"],
          R("Art. 269d para. 2 let. c", P269D2C, "evidence",
            "The increase is void if accompanied by a notice of termination; the notice shows whether it accompanied the "
            "increase.", de=P269D2C_DE)),
    ],
    "presumptions": [],
    "stops": [
        {"when": is_("increase_applied", False),
         "rule": R("Art. 270b para. 1", P270B1, "follows",
                   "The tenant's challenge and the voidness rules attach to an increase; where the claim states that the "
                   "landlord has neither announced nor demanded nor charged a higher rent there is nothing to challenge or "
                   "check and the process ends.", de=P270B1_DE)},
    ],
}

# ---------------------------------------------------------------- workflow edges (implement reached_when)
EDGES = {
    "defect_mold_heating": {
        "start": "dh_intake",
        "steps": [
            ("dh_intake", "Is a defect stated?", [], [("defect stated", "dh_scope", is_("defect_present")),
                                                       ("no defect stated", "dh_stop", is_("defect_present", False))],
             "defect_present"),
            ("dh_stop", None, [], [], "stop"),
            ("dh_scope", None, None, [("", "dh_notice_gate", True)], None),
            ("dh_notice_gate", "Is it stated that the landlord does not yet know of the defect?", [],
             [("landlord does not yet know", "dh_damage_gate", is_("landlord_unaware")),
              ("landlord knows", "dh_notice", is_("landlord_unaware", False))], "landlord_unaware"),
            ("dh_notice", None, None, [("", "dh_damage_gate", True)], None),
            ("dh_damage_gate", "Are damages claimed?", [],
             [("damages claimed", "dh_damage", is_("damages_claimed")),
              ("no damages claimed", "dh_deposit_gate", is_("damages_claimed", False))], "damages_claimed"),
            ("dh_damage", None, None, [("", "dh_deposit_gate", True)], None),
            ("dh_deposit_gate", "Is a rent deposit intended or made?", [],
             [("deposit intended or made", "dh_deposit", is_("deposit_intended")),
              ("no deposit", "dh_end", is_("deposit_intended", False))], "deposit_intended"),
            ("dh_deposit", None, None, [("", "dh_end", True)], None),
            ("dh_end", None, [], [], "end"),
        ],
    },
    "lease_termination_dispute": {
        "start": "lt_intake",
        "steps": [
            ("lt_intake", "Was a notice of termination given and received?", [],
             [("notice received", "lt_form", is_("notice_received")),
              ("no notice given", "lt_stop", is_("notice_received", False))], "notice_received"),
            ("lt_stop", None, [], [], "stop"),
            ("lt_form", None, None, [("", "lt_family_gate", True)], None),
            ("lt_family_gate", "Is the dwelling the family home of spouses or registered partners?", [],
             [("family home", "lt_family", is_("family_residence")),
              ("not a family home", "lt_arrears_gate", is_("family_residence", False))], "family_residence"),
            ("lt_family", None, None, [("", "lt_arrears_gate", True)], None),
            ("lt_arrears_gate", "Was notice given for arrears?", [],
             [("arrears", "lt_arrears", is_("arrears_termination")),
              ("not arrears", "lt_good_faith", is_("arrears_termination", False))], "arrears_termination"),
            ("lt_arrears", None, None, [("", "lt_good_faith", True)], None),
            ("lt_good_faith", None, None,
             [("notice not for arrears: extension can be at issue", "lt_extension", is_("arrears_termination", False)),
              ("notice for arrears: no extension", "lt_end", is_("arrears_termination"))], None),
            ("lt_extension", None, None, [("", "lt_end", True)], None),
            ("lt_end", None, [], [], "end"),
        ],
    },
    "rent_increase_dispute": {
        "start": "ri_intake",
        "steps": [
            ("ri_intake", "Was a rent increase announced, demanded or charged?", [],
             [("increase applied or announced", "ri_form", is_("increase_applied")),
              ("no increase", "ri_stop", is_("increase_applied", False))], "increase_applied"),
            ("ri_stop", None, [], [], "stop"),
            ("ri_form", None, None, [("", "ri_basis_gate", True)], None),
            ("ri_basis_gate", "Is the increase a graduated-rent step?", [],
             [("graduated rent", "ri_graduated", is_("graduated_rent")),
              ("not graduated rent", "ri_index_gate", is_("graduated_rent", False))], "graduated_rent"),
            ("ri_graduated", None, None, [("", "ri_threat_gate", True)], None),
            ("ri_index_gate", "Is the increase index-linked?", [],
             [("index clause", "ri_index", is_("index_clause")),
              ("no index clause", "ri_reason", is_("index_clause", False))], "index_clause"),
            ("ri_index", None, None, [("", "ri_threat_gate", True)], None),
            ("ri_reason", None, None, [("", "ri_threat_gate", True)], None),
            ("ri_threat_gate", "Was a notice of termination given with the increase?", [],
             [("notice of termination with the increase", "ri_threat", is_("termination_with_increase")),
              ("no notice of termination with it", "ri_end", is_("termination_with_increase", False))],
             "termination_with_increase"),
            ("ri_threat", None, None, [("", "ri_end", True)], None),
            ("ri_end", None, [], [], "end"),
        ],
    },
}

TYPES = [defect, termination, rent]
SOURCES = [
    {"id": EN, "title": "Swiss Code of Obligations (SR 220), Title Eight: Leases, official English translation, "
                        "consolidated version of 1 October 2026 (Fedlex); not authoritative"},
    {"id": DE, "title": "Obligationenrecht (SR 220), Achter Titel: Die Miete, authoritative German text, consolidated "
                        "version of 1 October 2026 (Fedlex)"},
]


# How to read steps and stops: one general paragraph, the same words in all three regimes (rule_text.md and rules.json).
STOPS_READING = ("Steps are taken in the order given. A document belongs to a step and is decided when that step is "
                 "reached. A stop ends the process at its step: no later step is reached, and no document of a later "
                 "step is requested or left waiting. Documents of steps reached before the stop keep the state they had; "
                 "a document requested there remains requested.")

# The intake convention of SPEC.md item 6a: one rule, basis "convention", fixed words, no passage.
CONVENTION_TEXT = ("A fact that the file does not mention is taken as not alleged, and the rules are applied as if it "
                   "were absent. Silence never ends a process: where a fact's absence would end it, the unmentioned fact "
                   "is unresolved. The defining event is never presumed: if the file does not mention it, it is "
                   "unresolved. A fact that the file raises and leaves unsettled is open.")
CONVENTION_SOURCE = {"id": "benchmark-convention", "kind": "benchmark_convention",
                     "title": "Intake convention of this benchmark (SPEC.md item 6a); a convention, not law; cites no passage"}
CONVENTION = {"id": "intake-convention", "basis": "convention", "text": CONVENTION_TEXT,
              "source_id": CONVENTION_SOURCE["id"],
              "applies_to": "every branch fact of every type (value: false), except the defining event, a fact whose "
                            "value false triggers a stop, and a fact marked always_stated",
              "precedence": "a presumption a cited passage supports (under a type's presumptions) takes precedence; "
                            "this rule set has none"}
# The tested product's validate_workflow accepts only these source kinds: process_diagram, process_guidance,
# case_example, expert_review, knowledge, case_edit. "benchmark_convention" is not among them and the product may not
# change in steps 1-2, so the workflow lists the convention's source with the nearest accepted kind and records the
# intended kind beside it (an extra key the validator ignores). Set to "benchmark_convention" once the product accepts it.
WORKFLOW_CONVENTION_KIND = "process_guidance"


def stop_on_false(t):
    """Facts whose value false triggers a stop (silence must never end a process)."""
    out = set()
    for stop in t["stops"]:
        def visit(c):
            if isinstance(c, dict):
                for k in ("all", "any"):
                    for x in c.get(k, ()):
                        visit(x)
                if c.get("is") is False:
                    out.add(c["fact"])
        visit(stop["when"])
    return out


def convention_applies(t, f):
    return (f["id"] != t["defining_event"] and f["id"] not in stop_on_false(t) and not f.get("always_stated")
            and f["id"] not in {p["fact"] for p in t["presumptions"]})


def ref(rule):
    """A workflow source reference for a rule: source#locator."""
    loc = rule["locator"].replace("Art. ", "art-").replace(" para. ", "-p").replace(" let. ", "-").replace(" ", "")
    return f"{rule['source_id']}#{loc}"


def workflow(t):
    spec = EDGES[t["id"]]
    facts = {f["id"]: f for f in t["facts"]}
    steps = {s["id"]: s for s in t["steps"]}
    docs_by_step = {}
    for d in t["documents"]:
        docs_by_step.setdefault(d["step"], []).append(d["id"])
    stop_rule = t["stops"][0]["rule"]
    out_steps = []
    for sid, title, docs, edges, kind in spec["steps"]:
        row = {"id": sid, "role": "system" if kind not in (None,) else "claim_handler"}
        if kind == "stop":
            row.update(title="Stop: the defining event is denied", outcome="stopped", source_refs=[ref(stop_rule)])
        elif kind == "end":
            row.update(title="Document requests complete", outcome="closed",
                       source_refs=[ref(facts[t["defining_event"]]["rule"])])
        elif kind is None:
            s = steps[sid]
            row.update(title=s["title"], source_refs=[ref(s["rule"])], role="claim_handler")
            if docs_by_step.get(sid):
                row["documents"] = docs_by_step[sid]
        else:  # a gate on one fact
            row.update(title=title, source_refs=[ref(facts[kind]["rule"])])
        if edges:
            row["next"] = [{**({"label": lab} if lab else {}), "to": to, "when": when} for lab, to, when in edges]
        out_steps.append(row)
    documents = []
    for d in t["documents"]:
        doc = {"id": d["id"], "title": d["title"], "must_show": d["must_show"], "source_refs": [ref(d["rule"])],
               "why": d["rule"].get("inference", ""), "legal_basis": f"SR 220 {d['rule']['locator']}"}
        if d["needed_when"] is not True:
            doc["required_when"] = d["needed_when"]
        documents.append(doc)
    type_ids = [x["id"] for x in TYPES]
    return {
        "format": "casepath.workflow/1",
        "id": t["id"],
        "version": VERSION,
        "title": t["title"] + " (rules from SR 220)",
        "status": "reviewed",
        "example": False,
        "applies_when": {"fact": "dispute_family", "is": t["id"]},
        "sources": [{"id": s["id"], "kind": "knowledge", "title": s["title"]} for s in SOURCES]
                   + [{"id": CONVENTION_SOURCE["id"], "kind": WORKFLOW_CONVENTION_KIND,
                       "intended_kind": CONVENTION_SOURCE["kind"], "title": CONVENTION_SOURCE["title"]}],
        "facts": [{"id": "dispute_family", "type": "enum", "values": type_ids,
                   "question": "Which tenancy dispute does the claim concern: a defect of the dwelling (mould, damp, "
                               "heating), a termination of the lease by the landlord, or a rent increase?",
                   "source_refs": [ref(facts[t["defining_event"]]["rule"])]}]
                 + [{"id": f["id"], "type": "boolean", "question": f["question"], "source_refs": [ref(f["rule"])],
                     **({"always_stated": True} if f.get("always_stated") else {})}
                    for f in t["facts"]],
        "start": spec["start"],
        "steps": out_steps,
        "documents": documents,
        "outcomes": [{"id": "closed", "title": "Document requests complete",
                      "source_refs": [ref(facts[t["defining_event"]]["rule"])]},
                     {"id": "stopped", "title": "Process ended: the defining event is denied",
                      "source_refs": [ref(stop_rule)]}],
        # statutory presumptions (none here) first; then the convention on every branch fact without one
        "presumptions": [{"fact": p["fact"], "value": p["value"], "applies": p["applies"], "text": p["rule"]["passage"],
                          "source_ref": ref(p["rule"])} for p in t["presumptions"]]
                        + [{"fact": f["id"], "value": False, "applies": "unstated",
                            "text": "Convention of this benchmark (not law): " + CONVENTION_TEXT,
                            "source_ref": CONVENTION_SOURCE["id"] + "#" + CONVENTION["id"]}
                           for f in t["facts"] if convention_applies(t, f)],
        "open_questions": [],
        "notes": [{"text": "Convention of this benchmark (not law): " + CONVENTION_TEXT + " The defining event "
                           f"({t['defining_event']}) and any always-stated fact carry no presumption.",
                   "source_refs": [CONVENTION_SOURCE["id"] + "#" + CONVENTION["id"]]}],
    }


PREFIX = {"defect_mold_heating": "D", "lease_termination_dispute": "T", "rent_increase_dispute": "R"}


def rules_md(doc):
    def cond(c):
        if c is True:
            return "always"
        if "all" in c:
            return " and ".join(cond(x) for x in c["all"])
        if "any" in c:
            return "(" + " or ".join(cond(x) for x in c["any"]) + ")"
        return f"{c['fact']}={'yes' if c['is'] else 'no'}"

    def cell(s):
        return s.replace("\n", " / ").replace("|", "\\|")

    lines = [f"# Tenancy rule set ({doc['version']})", "",
             "Generated from `rules.json` by `tools/build.py`. One clause per row. Passages are verbatim from the stored "
             "snapshots (`sources/sr220-en.txt`; German, which is authoritative, from `sources/sr220-de.txt`). Line breaks "
             "inside a passage are shown as ` / `. Development material; nothing here is a result.", "",
             "Basis: `states` = the passage states the rule; `follows` = it follows by the named step; `evidence` = the "
             "passage creates a condition and the document ordinarily proves it.", "",
             "Presumptions supported by a passage: none.", "",
             "## Convention of this benchmark (not law)", "",
             "| # | Kind | Clause | Basis | Passage |", "|---|---|---|---|---|",
             f"| C01 | convention (`{doc['convention']['id']}`) | {doc['convention']['text']} Applies to: "
             f"{doc['convention']['applies_to']}. | convention | none (cites no passage) |", ""]
    for t in doc["types"]:
        lines += [f"## {t['title']} (`{t['id']}`)", "", f"Defining event: `{t['defining_event']}`.", "",
                  "| # | Kind | Clause | Condition | Citation | Basis | Passage (EN) | Passage (DE) | Inference |",
                  "|---|---|---|---|---|---|---|---|---|"]
        n = 0

        def row(kind, clause, condition, rule):
            nonlocal n
            n += 1
            de = rule.get("passage_de", {}).get("passage", "")
            loc, en = rule["locator"], rule["passage"]
            for a in rule.get("also", []):
                loc += f"; also {a['locator']}"
                en += f" — also ({a['locator']}): {a['passage']}"
                if a.get("passage_de"):
                    de += f" — ({a['locator']}): {a['passage_de']['passage']}"
            lines.append(f"| {PREFIX[t['id']]}{n:02d} | {kind} | {cell(clause)} | {cell(condition)} | SR 220 {loc} "
                         f"| {rule['basis']} | {cell(en)} | {cell(de)} | {cell(rule.get('inference', ''))} |")
        for f in t["facts"]:
            row("fact", f"`{f['id']}`{' (always stated; no presumption)' if f.get('always_stated') else ''}: "
                f"{f['question']} Not this: {f['not_this']}", "", f["rule"])
        for s in t["steps"]:
            row("step", f"`{s['id']}`: {s['title']}", cond(s["reached_when"]), s["rule"])
        for d in t["documents"]:
            row("document", f"`{d['id']}`: {d['title']} (step `{d['step']}`, mandatory: {d['mandatory']}; must show: "
                f"{'; '.join(d['must_show'])})", cond(d["needed_when"]), d["rule"])
        for s in t["stops"]:
            row("stop", "The process ends", cond(s["when"]), s["rule"])
        lines.append("")
    return "\n".join(lines) + "\n"


def rule_text(doc):
    """The prose given to every prompt-based design, generated from rules.json so it cannot drift."""
    L = ["# Tenancy rules: which documents to request", "",
         "These rules come from the Swiss Code of Obligations (SR 220), Title Eight (Leases), consolidated version of "
         "1 October 2026. Article numbers refer to that Code. They apply to a residential tenant's dispute of one of "
         "three types: " + ", ".join(t["title"].lower() for t in doc["types"]) + ".", "",
         "How to apply them:", "",
         "- Each type has deciding questions. Answer each from the claim and its attachments: yes, no, open (the claim "
         "raises the matter and leaves it unsettled), or not mentioned.",
         "- A step is reached when its condition holds; a document is requested when its step is reached and its own "
         "condition holds. A step or document whose condition depends on an unresolved or open answer waits for that "
         "answer.",
         "- If the claim states that the type's defining event did not happen, the process ends and no document is "
         "requested.", "",
         "## How to read steps and stops", "", doc["reading_of_stops"], "",
         "## Convention of this benchmark (not law)", "",
         "This is a convention of this benchmark, not a rule of law; it cites no legal text. " + doc["convention"]["text"],
         "", "Under each question below, \"If not mentioned\" says how the convention applies to it.", ""]
    for n, t in enumerate(doc["types"], 1):
        num = {f["id"]: i for i, f in enumerate(t["facts"], 1)}

        def cond(c):
            if c is True:
                return "always"
            if "all" in c:
                return " and ".join(cond(x) for x in c["all"])
            if "any" in c:
                return "either " + " or ".join(cond(x) for x in c["any"])
            return f"question {num[c['fact']]} is {'yes' if c['is'] else 'no'}"

        def basis(r):
            loc = f"art. {r['locator'][5:]}" + "".join(f", with art. {a['locator'][5:]}" for a in r.get("also", []))
            return loc + (f": {r['inference']}" if r.get("inference") else f": “{r['passage']}”")
        L += [f"## {n}. {t['title']}", "", "Deciding questions:", ""]
        for f in t["facts"]:
            if f["id"] == t["defining_event"]:
                head, unm = "Defining event", "unresolved (the defining event is never presumed)."
            elif f.get("always_stated"):
                head, unm = "Always stated", "unresolved (this fact has no ordinary default)."
            elif f["id"] in stop_on_false(t):
                head, unm = "Branch", "unresolved (its absence would end the process)."
            else:
                head, unm = "Branch", "taken as no."
            L += [f"{num[f['id']]}. {head} ({f['rule']['locator'].replace('Art.', 'art.')}): {f['question']}",
                  f"   Not this: {f['not_this']}", f"   If not mentioned: {unm}"]
        L.append("")
        for st in t["stops"]:
            L += [f"Stop: if {cond(st['when'])}, the process ends ({basis(st['rule'])})", ""]
        L += ["Steps and documents:", ""]
        for stp in t["steps"]:
            L.append(f"- **{stp['title']}**, reached when {cond(stp['reached_when'])} ({basis(stp['rule'])})")
            for d in t["documents"]:
                if d["step"] == stp["id"]:
                    extra = "" if d["needed_when"] is True else f", if {cond(d['needed_when'])}"
                    L.append(f"  - Request **{d['title']}**{extra}. It must show: {'; '.join(d['must_show'])} "
                             f"({basis(d['rule'])})")
        L.append("")
    return "\n".join(L)


def main():
    doc = {"regime": "tenancy", "version": VERSION,
           "sources": [{"id": s["id"], "title": s["title"], "snapshot": f"sources/{s['id']}.txt"} for s in SOURCES],
           "convention": {**CONVENTION, "source": CONVENTION_SOURCE},
           "reading_of_stops": STOPS_READING,
           "types": TYPES}
    (HERE / "rules.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (HERE / "RULES.md").write_text(rules_md(doc), encoding="utf-8")
    (HERE / "rule_text.md").write_text(rule_text(doc), encoding="utf-8")
    (HERE / "workflow").mkdir(exist_ok=True)
    for t in TYPES:
        (HERE / "workflow" / f"{t['id']}.json").write_text(
            json.dumps(workflow(t), indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
