"""Build the theft rule set from public text: snapshots, rules.json, RULES.md, rule_text.md and workflow/*.json.

Run with `python3 -I tools/build.py` from anywhere. Every clause is written once here, with its source, locator,
verbatim passage and basis; the outputs are generated from these tables. The statute snapshot (sources/vvg.txt) is
made by tools/statute.py from the Fedlex XML; the insurers' snapshots hold only the quoted passages below.
After building, run tools/verify_sources.py (passages against the downloaded public documents) and tools/check.py.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sources"
VERSION = "2026-11-12"

# ---------------------------------------------------------------------------------------------------------- sources
SOURCES = [
    {"id": "vvg",
     "title": "Bundesgesetz über den Versicherungsvertrag (Versicherungsvertragsgesetz, VVG) vom 2. April 1908, SR 221.229.1",
     "publisher": "Swiss Federal Chancellery, Fedlex",
     "version": "consolidated version in force since 1 January 2024 (Stand am 1. Januar 2024); the latest consolidation Fedlex lists on 2026-11-12",
     "language": "de", "authoritative": True,
     "url": "https://www.fedlex.admin.ch/eli/cc/24/719_735_717/20240101/de",
     "download_url": "https://fedlex.data.admin.ch/filestore/fedlex.data.admin.ch/eli/cc/24/719_735_717/20240101/de/xml/fedlex-data-admin-ch-eli-cc-24-719_735_717-20240101-de-xml-14.xml",
     "retrieved": "2026-11-12T11:46:16Z",
     "raw_file": "vvg-20240101-de.xml",
     "raw_sha256": "8b98e586f17c8ddb5eb01e71e0ad5217fdc9c15b0c0b1c0decb04eeb93fa219a",
     "snapshot": "vvg.txt", "snapshot_kind": "cited articles (Art. 38, 38a, 39), re-flowed by tools/statute.py",
     "licence": "Federal enactments are not protected by copyright (Art. 5 para. 1 lit. a URG, SR 231.1).",
     "repository_provenance": "Study 1 source fedlex2024vvg (data/casepath-theft-pairs/SOURCES.md), same consolidated version.",
     "public_today": "yes: the passages quoted here occur in the Fedlex XML of the version in force, retrieved 2026-11-12."},
    {"id": "css-avb",
     "title": "Hausratversicherung, Allgemeine Versicherungsbedingungen (AVB), Form. 519d-01.24-eff",
     "publisher": "CSS Versicherung AG",
     "version": "Ausgabe 02.2024",
     "language": "de", "authoritative": True,
     "url": "https://www.css.ch/content/dam/css/de/documents/privatkunden/richtig-versichert/avb/519_d_avb_hausratversicherung.pdf",
     "retrieved": "2026-11-12T11:46:18Z",
     "raw_file": "css-avb-hausrat.pdf",
     "raw_sha256": "cce8948157d794094847da343b09b9bdce1e4789e4bcd8d3511c06f952426c1d",
     "snapshot": "css-avb.txt", "snapshot_kind": "quoted passages only",
     "licence": "Copyright CSS Versicherung AG. Only short attributed quotations are kept (Art. 25 URG); the document itself is not in the repository.",
     "repository_provenance": "Study 1 source css2024hausratavb (data/casepath-theft-pairs/SOURCES.md, sources/sources.bib); the file served on 2026-11-12 has the SHA-256 recorded there (byte-identical).",
     "public_today": "yes: byte-identical to the copy recorded for Study 1; every quoted passage occurs in it (tools/verify_sources.py)."},
    {"id": "css-form",
     "title": "Schadenanzeige Hausrat / Gebäude (claim notification form), Form. 15d-09.26-pdf",
     "publisher": "CSS Versicherung AG",
     "version": "Form. 15d-09.26 (PDF modified 2026-10-16); Study 1 used the earlier edition 15d-08.26 from the same URL",
     "language": "de", "authoritative": True,
     "url": "https://www.css.ch/content/dam/css/de/documents/privatkunden/richtig-versichert/formulare/15_d_formular_schadenanzeige_hausrat.pdf",
     "retrieved": "2026-11-12T11:46:19Z",
     "raw_file": "css-schadenanzeige.pdf",
     "raw_sha256": "adde3d2a9b6c6e050b3d8733c572d518b935195cf84a112f6364251cc453295a",
     "snapshot": "css-form.txt", "snapshot_kind": "quoted passages only",
     "licence": "Copyright CSS Versicherung AG. Only short attributed quotations are kept (Art. 25 URG); the document itself is not in the repository.",
     "repository_provenance": "Study 1 source css2026schadenanzeige (edition 15d-08.26, SHA-256 262da3f4...). The URL now serves edition 15d-09.26; all 17 Study 1 passages of the form occur in it word for word.",
     "public_today": "yes for the current edition 15d-09.26, which is the one cited; the Study 1 edition 15d-08.26 is no longer served at the URL."},
]
CONSIDERED = [
    {"id": "svv2022hausratavb", "title": "SVV, Allgemeine Bedingungen (AVB) für die Hausratversicherung, Version 01.04.2022 (non-binding model)",
     "status": "fetched 2026-11-12 from the Study 1 URL; byte-identical to the recorded copy (SHA-256 6d5e431b...). Not used: the rule set applies one insurer's conditions so that no clause is applied outside its own contract."},
    {"id": "generali2026haushaltavb", "title": "Generali, AVB Haushaltversicherung, Ausgabe 2026",
     "status": "not fetched, not used (one insurer only). Its public URL is recorded in data/casepath-theft-pairs/sources/sources.bib."},
    {"id": "axa2021haushaltavb", "title": "AXA, AVB Haushaltversicherung, Ausgabe 10.2021",
     "status": "not fetched, not used (one insurer only). URL recorded in sources.bib."},
    {"id": "simpego2024homeavb", "title": "Simpego, Haushaltversicherung Home AVB, Ausgabe Dezember 2024",
     "status": "not fetched, not used (one insurer only). URL recorded in sources.bib."},
    {"id": "zgb-art-8", "title": "Swiss Civil Code (SR 210) Art. 8, burden of proof",
     "status": "considered for presumptions and not used: it allocates the burden of proving an alleged fact, and says nothing about what a fact the file does not mention is taken to be."},
]

# ------------------------------------------------------------------------------------- insurers' quoted passages
# (source id, locator, text, Study 1 passage id or None for a passage added from the same public document)
QUOTES = [
    ("css-avb", "Ziff. 4, S. 2", "Wird bei einer Mitteilung kein Formerfordernis angeführt, kann diese auch mündlich erfolgen.", None),
    ("css-avb", "Ziff. 8 lit. a, S. 3", "die CSS umgehend zu benachrichtigen;", "theft-source-0107"),
    ("css-avb", "Ziff. 8 lit. c, S. 3", "die für die Begründung des Entschädigungsanspruchs und des Umfangs der Entschädigungspflicht nötigen Angaben zu machen und auf Verlangen, ein Verzeichnis der vom Schaden betroffenen Sachen mit Wertangaben zu erstellen und Originalbelege beizubringen;", "theft-source-0134, extended to the whole of lit. c"),
    ("css-avb", "Ziff. 8 lit. d, S. 3", "während und nach dem Schadenereignis nach Möglichkeit für die Erhaltung und Rettung der versicherten Sachen und für die Minderung des Schadens zu sorgen und dabei die Anordnungen der CSS zu befolgen;", "theft-source-0170"),
    ("css-avb", "Ziff. 8, Einleitung zu lit. f-h, S. 3", "Bei Diebstahl hat der Versicherungsnehmer ferner:", "theft-source-0028"),
    ("css-avb", "Ziff. 8 lit. f, S. 3", "die Polizeibehörde umgehend zu benachrichtigen, eine amtliche Untersuchung zu beantragen und ohne Zustimmung der Polizei die Tatspuren nicht zu entfernen oder zu verändern. Ein entsprechender Polizeirapport kann durch die CSS einverlangt werden;", "theft-source-0043"),
    ("css-avb", "Ziff. 15, S. 3", "Sofern die CSS aus diesem Vertrag Leistungen erbracht hat, für welche der Versicherungsnehmer gegenüber Dritten Ansprüche geltend machen könnte, hat der Versicherungsnehmer diese Ansprüche bis zur Höhe der erbrachten Leistungen an die CSS abzutreten.", "theft-source-0055"),
    ("css-avb", "Ziff. 20, Einleitung, S. 4", "Für die nachstehenden Kosten (Vermögensschäden), die durch ein versichertes Schadenereignis infolge von Feuer, Elementarereignissen, Erdbeben und vulkanischen Eruptionen, Wasser oder Diebstahl am versicherten Standort entstehen, beträgt die Deckung im Rahmen der freiwilligen Hausratversicherung gesamthaft 20% der Versicherungssumme der freiwilligen Hausrat-Grundversicherung, mindestens CHF 10 000.", None),
    ("css-avb", "Ziff. 20 lit. d, S. 5", "Mitversichert sind die effektiven Kosten für das Ändern oder Ersetzen von Schlüsseln, Magnetkarten oder von Schlössern an dem in der Police bezeichneten Standort und an den vom Versicherungsnehmer gemieteten Banksafes und dazugehörenden Schlüsseln.", None),
    ("css-avb", "Ziff. 20 lit. d, Ausschluss, S. 5", "Kosten bei einfachem Diebstahl (zu Hause oder auswärts).", "theft-source-0062"),
    ("css-avb", "Ziff. 23, Einleitung, S. 5", "Die CSS versichert die nachfolgend beschriebenen Gefahren und Schäden, sofern diese vom Versicherungsnehmer gewünscht und in der Police aufgeführt worden sind:", "theft-source-0160"),
    ("css-avb", "Ziff. 23.3 Abs. 1, S. 7", "Versichert sind durch Spuren, Zeugen oder nach den Umständen schlüssig nachgewiesene Schäden am Hausrat, auch wenn dabei nichts entwendet wurde, durch Einbruch, Beraubung und einfacher Diebstahl (inkl. Vandalismus) am Versicherungsort.", "theft-source-0025"),
    ("css-avb", "Ziff. 23.3, Ausschlüsse, erster Strich, S. 7", "Schäden, verursacht durch Personen, die mit dem Versicherungsnehmer im gleichen Haushalt leben.", "theft-source-0014"),
    ("css-avb", "Ziff. 23.3, Ausschlüsse, zweiter Strich, S. 7", "Schäden durch Verlieren, Verlegen oder infolge von Veruntreuung.", None),
    ("css-avb", "Ziff. 23.3 lit. a, S. 7", "Einbruchdiebstahl ist Diebstahl durch Täter, die gewaltsam in ein Gebäude oder in den Raum eines Gebäudes eindringen und/oder darin ein Behältnis aufbrechen sowie Diebstahl durch Aufschliessen mit den richtigen Schlüsseln oder Codes, sofern sich der Täter diese durch Einbruchdiebstahl oder Beraubung angeeignet hat.", "theft-source-0022"),
    ("css-avb", "Ziff. 23.3 lit. a, Ausschluss, S. 7", "Schäden, verursacht durch das Aufbrechen eines Fahrzeuges. Fahrzeuge sind keine Behältnisse.", None),
    ("css-avb", "Ziff. 23.3 lit. b, S. 7", "Beraubung ist Diebstahl unter Androhung und/oder Anwendung von Gewalt gegen den Versicherungsnehmer und die mit ihm im gleichen Haushalt lebenden Personen sowie Diebstahl bei Unfähigkeit zum Widerstand infolge Ohnmacht, Unfall oder Tod.", "theft-source-0138"),
    ("css-avb", "Ziff. 23.3 lit. b, Ausschluss, S. 7", "Schäden, verursacht durch Taschen- und Trickdiebstahl.", None),
    ("css-avb", "Ziff. 23.3 lit. c, S. 7", "Einfacher Diebstahl am Versicherungsort ist Diebstahl, der weder als Einbruchdiebstahl noch als Beraubung gilt. Für den einfachen Diebstahl auswärts ist eine separate Zusatzversicherung abzuschliessen.", "theft-source-0054 + theft-source-0024"),
    ("css-avb", "Ziff. 24, Einleitung, S. 8", "Die CSS versichert die nachfolgend beschriebenen Gefahren, sofern diese vom Versicherungsnehmer gewünscht und in der Police aufgeführt worden sind:", None),
    ("css-avb", "Ziff. 24.2, S. 8", "Schäden am Hausrat durch Diebstahl, der weder als Einbruchdiebstahl noch als Beraubung gilt und sich ausserhalb des versicherten Standortes ereignet, sind bis zu der in der Police vereinbarten Versicherungssumme mitversichert.", "theft-source-0162"),
    ("css-avb", "Ziff. 26 lit. b, S. 10", "Auswärts auf der ganzen Welt für Hausrat, der sich während einer Reise, ohne dass sich dabei der gewöhnliche Aufenthaltsort des Versicherungsnehmers in der Schweiz ändert, vorübergehend an beliebigen anderen Orten befindet, im Rahmen der freiwilligen Hausratsversicherung bis CHF 50 000 für Schäden aus Feuer, Elementarschaden, Erdbeben und vulkanischen Eruptionen, Diebstahl (ohne einfachen Diebstahl) und Wasser", "theft-source-0153, extended"),
    ("css-avb", "Ziff. 29 lit. a, S. 11", "Der Versicherungsnehmer muss die Schadenhöhe beweisen.", "theft-source-0140"),
    ("css-form", "Seite 1, Einleitung, S. 1", "Alternativ können Sie uns den Schaden auch online unter css.ch/schaden melden.", None),
    ("css-form", "Abschnitt 3.5, S. 2", "Wer hat den Schaden verursacht?", "theft-source-0114"),
    ("css-form", "Abschnitt 3.7 Gegenstände, S. 2", "Beschädigte oder gestohlene Sachen (bitte Originalkaufbelege beilegen)", "theft-source-0176"),
    ("css-form", "Abschnitt 3.7, Spalten, S. 2", "Gegenstand Gekauft bei Kaufdatum Ersatzwert /Reparaturkosten Gemäss separater Liste", None),
    ("css-form", "Abschnitt 3.9, S. 3", "Fahrrad (bitte Originalkaufbelege beilegen)", "theft-source-0071"),
    ("css-form", "Abschnitt 4, Überschrift, S. 3", "Polizeimeldung", None),
    ("css-form", "Abschnitt 4.1, Anzeigedatum, S. 3", "Anzeigedatum", None),
    ("css-form", "Abschnitt 4, Polizeiposten, S. 3", "Polizeiposten", None),
]


def Q(locator_prefix, sub=None, source="css-avb"):
    """A citation to a quoted passage (or to a verbatim part of it)."""
    for sid, loc, text, _ in QUOTES:
        if sid == source and loc.startswith(locator_prefix):
            passage = sub or text
            assert passage in text, (locator_prefix, passage)
            return {"source_id": sid, "locator": loc, "passage": passage}
    raise KeyError(locator_prefix)


def V(locator, passage):
    return {"source_id": "vvg", "locator": locator, "passage": passage}


def rule(cite, basis, inference=None, context=None):
    out = dict(cite, basis=basis)
    if inference:
        out["inference"] = inference
    if context:
        out["context"] = context
    return out


V38 = V("VVG Art. 38 Abs. 1", "Ist das befürchtete Ereignis eingetreten, so muss der Anspruchsberechtigte, sobald er von diesem Ereignisse und seinem Anspruche aus der Versicherung Kenntnis erlangt, das Versicherungsunternehmen benachrichtigen.")
V38A = V("VVG Art. 38a Abs. 1", "Der Anspruchsberechtigte ist verpflichtet, nach Eintritt des befürchteten Ereignisses tunlichst für Minderung des Schadens zu sorgen. Er muss, wenn nicht Gefahr im Verzug liegt, über die zu ergreifenden Massnahmen die Weisung des Versicherungsunternehmens einholen und befolgen.")
V38A2 = V("VVG Art. 38a Abs. 1 Satz 2", "Er muss, wenn nicht Gefahr im Verzug liegt, über die zu ergreifenden Massnahmen die Weisung des Versicherungsunternehmens einholen und befolgen.")
V39 = V("VVG Art. 39 Abs. 2 Ziff. 1", "Der Vertrag kann verfügen: 1. dass der Anspruchsberechtigte bestimmte Belege, deren Beschaffung ihm ohne erhebliche Kosten möglich ist, insbesondere auch ärztliche Bescheinigungen, beizubringen hat;")

POLICE = "die Polizeibehörde umgehend zu benachrichtigen, eine amtliche Untersuchung zu beantragen"
TRACES = "ohne Zustimmung der Polizei die Tatspuren nicht zu entfernen oder zu verändern"
REPORT = "Ein entsprechender Polizeirapport kann durch die CSS einverlangt werden"
SIMPLE = "Einfacher Diebstahl am Versicherungsort ist Diebstahl, der weder als Einbruchdiebstahl noch als Beraubung gilt."
AWAY_COVER = "Für den einfachen Diebstahl auswärts ist eine separate Zusatzversicherung abzuschliessen."
ON_REQUEST = "auf Verlangen, ein Verzeichnis der vom Schaden betroffenen Sachen mit Wertangaben zu erstellen und Originalbelege beizubringen;"
DEFS = [Q("Ziff. 23.3 lit. a, S."), Q("Ziff. 23.3 lit. a, Ausschluss"), Q("Ziff. 23.3 lit. b, S."), Q("Ziff. 23.3 lit. b, Ausschluss")]
FORM_ITEMS = [Q("Abschnitt 3.7 Gegenstände", source="css-form"), Q("Abschnitt 3.7, Spalten", source="css-form")]
FORM_POLICE = [Q("Abschnitt 4, Überschrift", source="css-form"), Q("Abschnitt 4.1", source="css-form"), Q("Abschnitt 4, Polizeiposten", source="css-form")]
BURGLARY_WORDS = ("a burglary (the thief forcibly entered the building or a room of it, or broke open a container in it, or "
                  "unlocked it with the correct keys or codes that the thief had obtained by burglary or robbery; a vehicle is not "
                  "a container) or a robbery (theft under threat or use of violence against the policyholder or a member of the "
                  "household, or while they could not resist because of unconsciousness, accident or death; pickpocketing and trick "
                  "theft are not robbery)")
NOT_BURGLARY = ("Breaking into a vehicle is not a burglary (a vehicle is not a container), and pickpocketing or trick theft is "
                "not a robbery: both are simple thefts.")
INTAKE_REQUEST = ("The contract makes the valued list and the original vouchers due on CSS's request ('auf Verlangen'). The handler is "
                  "the insurer, so the request is the act being decided; CSS makes it in its own claim form, which asks for every "
                  "stolen or damaged item with where and when it was bought and its value, 'bitte Originalkaufbelege beilegen', or a "
                  "separate list. At intake the handler therefore requests them.")


# ------------------------------------------------------------------------------------------- facts shared by types
def shared_facts():
    return [
        {"id": "traces_changed",
         "question": "Does the file state that traces of the theft (for example pry marks, a broken lock, window or container) have been removed or altered, or are to be removed or altered, by the policyholder or on their behalf, for example by repair or cleaning?",
         "not_this": "Traces that exist and are left as they were, or were only photographed; the police examining the scene; traces changed by the thief or by events outside the policyholder's control.",
         "rule": rule(Q("Ziff. 8 lit. f", TRACES), "states", context=[Q("Ziff. 8, Einleitung")])},
        {"id": "bicycle",
         "question": "Is a bicycle among the stolen or damaged items?",
         "not_this": "A motor scooter or motorcycle; bicycle parts or accessories alone.",
         "rule": rule(Q("Abschnitt 3.9", source="css-form"), "states")},
        {"id": "vouchers_unobtainable",
         "question": "Does the file state that the original purchase vouchers for all of the stolen or damaged items cannot be obtained, or only at considerable cost (not even as a duplicate from the seller)?",
         "not_this": "Only some vouchers cannot be obtained (then the others are still needed); the vouchers have not been attached yet or not been looked for; finding them is merely inconvenient.",
         "rule": rule(V39, "follows",
                      "The contract may require only vouchers whose procurement is possible without considerable cost; where no voucher can be obtained without considerable cost, none may be required. The limit applies voucher by voucher, so where only some are unobtainable the document is still needed for the others (see original_vouchers, must_show).")},
        {"id": "measures_pending",
         "question": "Does the file state that measures to reduce the loss are still to be taken (not yet carried out)?",
         "not_this": "Measures already carried out; the notification of the claim itself; steps to find the thief or recover the items.",
         "rule": rule(V38A, "states")},
        {"id": "imminent_danger",
         "question": "Does the file state that the measures could not wait for the insurer's instruction because of imminent danger (Gefahr im Verzug)?",
         "not_this": "The claimant simply acted quickly or found it convenient, without a danger of further loss before the insurer could be asked.",
         "rule": rule(V38A2, "states")},
    ]


def T(fact, value=True):
    return {"fact": fact, "is": value}


def ALL(*conds):
    out = []
    for c in conds:
        if c is True:
            continue
        out += c["all"] if isinstance(c, dict) and "all" in c else [c]
    return out[0] if len(out) == 1 else {"all": out}


INSTRUCTION = ALL(T("measures_pending"), T("imminent_danger", False))


def tail_steps(p, base):
    """Steps after the gate(s): notification, police, traces, instruction, loss. `base` = condition to reach them."""
    return [
        {"id": f"{p}_notify", "title": "Record the claim notification", "reached_when": base,
         "rule": rule(V38, "states", context=[Q("Ziff. 8 lit. a")]), "next": [(f"{p}_police", True, None)]},
        {"id": f"{p}_police", "title": "Check that the police were notified and an official investigation requested", "reached_when": base,
         "rule": rule(Q("Ziff. 8 lit. f", POLICE), "states", context=[Q("Ziff. 8, Einleitung")] + FORM_POLICE),
         "next": [(f"{p}_traces", T("traces_changed"), "traces removed or altered"),
                  (f"{p}_instruction_check", T("traces_changed", False), "traces untouched")]},
        {"id": f"{p}_traces", "title": "Check the police's consent to removing or altering the traces",
         "reached_when": ALL(base, T("traces_changed")),
         "rule": rule(Q("Ziff. 8 lit. f", TRACES), "states"), "next": [(f"{p}_instruction_check", True, None)]},
        {"id": f"{p}_instruction_check", "title": "Check whether the insurer's instruction on loss-reduction measures is to be obtained", "reached_when": base,
         "rule": rule(V38A2, "states"),
         "next": [(f"{p}_instruction", INSTRUCTION, "measures pending, no imminent danger"),
                  (f"{p}_loss", {"any": [T("measures_pending", False), T("imminent_danger")]}, "no instruction to obtain")]},
        {"id": f"{p}_instruction", "title": "Obtain and follow the insurer's instruction on the measures to be taken",
         "reached_when": ALL(base, INSTRUCTION),
         "rule": rule(V38A2, "states", context=[Q("Ziff. 8 lit. d")]), "next": [(f"{p}_loss", True, None)]},
        {"id": f"{p}_loss", "title": "Establish the stolen or damaged items and their value", "reached_when": base,
         "rule": rule(Q("Ziff. 29 lit. a"), "states"), "next": []},
    ]


def shared_documents(p, policy_step, policy_rule, policy_shows):
    return [
        {"id": "notification_record", "title": "Record of the claim notification: the CSS form 'Schadenanzeige Hausrat / Gebäude', or CSS's record of an online, written or oral notification",
         "step": f"{p}_notify", "needed_when": True, "mandatory": True,
         "must_show": ["that and when CSS was notified of the theft"],
         "rule": rule(V38, "evidence", "The passage makes notifying the insurer a duty; CSS requires no form for it (oral notice suffices, Ziff. 4; its form offers online notification), so any record of the notification, the claim form or CSS's own record of an online, written or oral notice, ordinarily shows that and when the insurer was notified.",
                      context=[Q("Ziff. 8 lit. a"), Q("Ziff. 4"), Q("Seite 1", source="css-form")])},
        {"id": "insurance_policy", "title": "The insurance policy (Police)", "step": policy_step, "needed_when": True, "mandatory": True,
         "must_show": policy_shows, "rule": policy_rule},
        {"id": "police_report", "title": "Police report on the theft (Polizeirapport)", "step": f"{p}_police", "needed_when": True, "mandatory": False,
         "must_show": ["that the theft was reported to the police and when", "the police station", "that an official investigation was requested"],
         "rule": rule(Q("Ziff. 8 lit. f", REPORT), "states", context=FORM_POLICE)},
        {"id": "police_consent", "title": "The police's consent to removing or altering the traces (the police report recording it, or a written confirmation by the police)",
         "step": f"{p}_traces", "needed_when": True, "mandatory": True,
         "must_show": ["that the police consented", "which traces the consent covered"],
         "rule": rule(Q("Ziff. 8 lit. f", TRACES), "evidence",
                      "The passage makes the police's consent the condition for removing or altering traces; the police report, the document the same clause names and CSS may request, or a written confirmation by the police is the document that can show the consent. Either one satisfies this need.")},
        {"id": "stolen_items_list", "title": "List of the stolen or damaged items with their values (the claim form's table in section 3.7, or a separate list)",
         "step": f"{p}_loss", "needed_when": True, "mandatory": True,
         "must_show": ["each stolen or damaged item", "where and when it was bought", "its value"],
         "rule": rule(Q("Ziff. 8 lit. c", ON_REQUEST), "follows", INTAKE_REQUEST, context=FORM_ITEMS)},
        {"id": "original_vouchers", "title": "Original purchase vouchers for the stolen or damaged items (Originalbelege)",
         "step": f"{p}_loss", "needed_when": T("vouchers_unobtainable", False), "mandatory": True,
         "must_show": ["the original voucher for each stolen or damaged item whose voucher can be obtained without considerable cost", "where and when the item was bought", "the price paid"],
         "rule": rule(Q("Ziff. 8 lit. c", ON_REQUEST), "follows", INTAKE_REQUEST + " The limit of VVG Art. 39 Abs. 2 Ziff. 1 applies voucher by voucher.", context=FORM_ITEMS + [V39])},
        {"id": "bicycle_voucher", "title": "Original purchase voucher for the bicycle",
         "step": f"{p}_loss", "needed_when": ALL(T("bicycle"), T("vouchers_unobtainable", False)), "mandatory": True,
         "must_show": ["the bicycle, if its voucher can be obtained without considerable cost", "where and when it was bought", "the price paid"],
         "rule": rule(Q("Ziff. 8 lit. c", ON_REQUEST), "follows", "As for original_vouchers: the contract makes original vouchers due on CSS's request, and CSS's claim form asks for the bicycle's voucher in its own section ('Fahrrad (bitte Originalkaufbelege beilegen)').",
                      context=[Q("Abschnitt 3.9", source="css-form"), V39])},
    ]


# ----------------------------------------------------------------------------------------------------- type 1: home
HOME_BASE = ALL(T("theft_at_home"), T("household_perpetrator", False))
home = {
    "id": "theft_at_home",
    "title": "Theft at the insured location (CSS AVB Ziff. 23.3)",
    "defining_event": "theft_at_home",
    "facts": [
        {"id": "theft_at_home",
         "question": "Does the file state that household contents at the insured location (the Versicherungsort of the policy) were stolen or damaged by a burglary, a robbery or a simple theft (including vandalism), even if nothing was taken?",
         "not_this": "Items merely missing where no trace, witness or circumstance points to a theft (that is open, not true); items lost, misplaced or misappropriated; a theft away from the insured location (the other claim type, Ziff. 24.2, or outside both types).",
         "rule": rule(Q("Ziff. 23.3 Abs. 1"), "states", context=[Q("Ziff. 23.3, Ausschlüsse, zweiter")] + DEFS)},
        {"id": "household_perpetrator",
         "question": "Does the file state that the theft or damage was caused by a person who lived in the same household as the policyholder at the time?",
         "not_this": "A guest, neighbour, tradesman or cleaner, or a person who had moved out of the household before the theft; a suspicion the file raises but does not settle is open, not true.",
         "rule": rule(Q("Ziff. 23.3, Ausschlüsse, erster"), "states")},
        {"id": "burglary_or_robbery",
         "question": f"Was the theft {BURGLARY_WORDS}, and so not a simple theft?",
         "not_this": "A theft through a door or window left open or unlocked, without force and without violence against a person: that is a simple theft. " + NOT_BURGLARY,
         "always_stated": True,
         "rule": rule(Q("Ziff. 23.3 lit. c", SIMPLE), "states", context=DEFS)},
        {"id": "lock_change",
         "question": "Does the claim include costs, caused by the theft, of changing or replacing keys, magnetic cards or locks at the location named in the policy, or at a bank safe the policyholder rents?",
         "not_this": "A lock change made for another reason; emergency doors, glazing or locks put in after the event; the repair of a damaged door or window.",
         "rule": rule(Q("Ziff. 20 lit. d, S."), "states", context=[Q("Ziff. 20, Einleitung")])},
        *shared_facts(),
    ],
    "steps": [
        {"id": "h_event", "title": "Check that the reported event is a theft at the insured location", "reached_when": True,
         "rule": rule(Q("Ziff. 23.3 Abs. 1"), "states"),
         "next": [("h_exclusion", T("theft_at_home"), "theft at the insured location"), ("h_stop_no_event", T("theft_at_home", False), "no such event")]},
        {"id": "h_exclusion", "title": "Check the exclusion of damage caused by household members", "reached_when": T("theft_at_home"),
         "rule": rule(Q("Ziff. 23.3, Ausschlüsse, erster"), "states"),
         "next": [("h_stop_excluded", T("household_perpetrator"), "caused by a household member"), ("h_notify", T("household_perpetrator", False), "not excluded")]},
        *tail_steps("h", HOME_BASE),
    ],
    "documents": [],
    "presumptions": [],
    "stops": [
        {"id": "h_stop_no_event", "title": "Not a theft at the insured location: this claim type does not apply", "when": T("theft_at_home", False),
         "rule": rule(Q("Ziff. 23.3 Abs. 1"), "follows", "The clause covers damage by these events at the insured location; where the file states that no such event occurred, the steps of this claim type do not apply.")},
        {"id": "h_stop_excluded", "title": "Excluded: caused by a person living in the policyholder's household", "when": ALL(T("theft_at_home"), T("household_perpetrator")),
         "rule": rule(Q("Ziff. 23.3, Ausschlüsse, erster"), "states")},
    ],
}
home["documents"] = shared_documents(
    "h", "h_notify",
    rule(Q("Ziff. 23, Einleitung"), "evidence", "The clause makes cover depend on the peril being listed in the policy; the policy is the document that shows whether theft is listed and which location is insured."),
    ["theft (Ziff. 23.3) among the insured perils", "the insured location"]) + [
    {"id": "lock_change_invoice", "title": "Invoice for changing or replacing the keys, magnetic cards or locks",
     "step": "h_loss", "needed_when": ALL(T("lock_change"), T("burglary_or_robbery")), "mandatory": True,
     "must_show": ["the effective cost", "which keys, cards or locks were changed, and where"],
     "rule": rule(Q("Ziff. 20 lit. d, S."), "evidence",
                  "The clause covers the effective cost of the change, and the claimant must prove the amount (Ziff. 29 lit. a); the invoice of the locksmith or supplier is the document that ordinarily shows that cost. Costs after a simple theft are excluded (Ziff. 20 lit. d, Ausschluss), so the invoice is needed only after a burglary or robbery.",
                  context=[Q("Ziff. 20 lit. d, Ausschluss"), Q("Ziff. 29 lit. a")])},
]

# ----------------------------------------------------------------------------------------------------- type 2: away
AWAY_BASE = ALL(T("theft_away"), T("away_cover_missing", False))
away = {
    "id": "simple_theft_away",
    "title": "Simple theft away from the insured location (CSS AVB Ziff. 24.2)",
    "defining_event": "theft_away",
    "facts": [
        {"id": "theft_away",
         "question": f"Does the file state that household contents were stolen or damaged by a theft outside the insured location that was neither {BURGLARY_WORDS}?",
         "not_this": "A theft at the insured location (the other claim type, Ziff. 23.3); a burglary or robbery away from home (outside both types); items lost, left behind or misplaced. " + NOT_BURGLARY,
         "rule": rule(Q("Ziff. 24.2"), "states", context=DEFS)},
        {"id": "away_cover_missing",
         "question": "Does the policy, or the file, show that the policy does not include the separate supplementary insurance for simple theft away from home (einfacher Diebstahl auswärts)?",
         "not_this": "Another supplementary cover being missing. The claimant's narrative will rarely settle this; the policy does (insurance_policy).",
         "always_stated": True,
         "rule": rule(Q("Ziff. 24, Einleitung"), "states", context=[Q("Ziff. 23.3 lit. c", AWAY_COVER)])},
        *shared_facts(),
    ],
    "steps": [
        {"id": "a_event", "title": "Check that the reported event is a simple theft away from the insured location", "reached_when": True,
         "rule": rule(Q("Ziff. 24.2"), "states"),
         "next": [("a_cover", T("theft_away"), "simple theft away"), ("a_stop_no_event", T("theft_away", False), "no such event")]},
        {"id": "a_cover", "title": "Check in the policy that it includes the supplementary insurance for simple theft away", "reached_when": T("theft_away"),
         "rule": rule(Q("Ziff. 24, Einleitung"), "states", context=[Q("Ziff. 23.3 lit. c", AWAY_COVER)]),
         "next": [("a_stop_no_cover", T("away_cover_missing"), "no supplementary cover"), ("a_notify", T("away_cover_missing", False), "cover included")]},
        *tail_steps("a", AWAY_BASE),
    ],
    "documents": [],
    "presumptions": [],
    "stops": [
        {"id": "a_stop_no_event", "title": "Not a simple theft away from the insured location: this claim type does not apply", "when": T("theft_away", False),
         "rule": rule(Q("Ziff. 24.2"), "follows", "The clause covers damage by this kind of theft outside the insured location; where the file states that no such theft occurred, the steps of this claim type do not apply.")},
        {"id": "a_stop_no_cover", "title": "No cover: the supplementary insurance for simple theft away was not taken out", "when": ALL(T("theft_away"), T("away_cover_missing")),
         "rule": rule(Q("Ziff. 24, Einleitung"), "follows", "Supplementary covers apply only where they are listed in the policy, and simple theft away needs such a separate supplementary insurance (Ziff. 23.3 lit. c); where the policy does not include it, there is no cover for the event and the process for this claim type ends.",
                      context=[Q("Ziff. 23.3 lit. c", AWAY_COVER)])},
    ],
}
away["documents"] = shared_documents(
    "a", "a_cover",
    rule(Q("Ziff. 24, Einleitung"), "evidence", "Supplementary covers apply only where they are listed in the policy; the policy is the document that shows whether the supplementary insurance for simple theft away was agreed, for which sum, and which location is insured (so that 'outside the insured location' can be checked).",
         context=[Q("Ziff. 24.2")]),
    ["the supplementary insurance for simple theft away (Ziff. 24.2), or its absence", "its sum insured", "the insured location"])

ROUTING = {
    "fact": "claim_type", "type": "enum", "values": ["theft_at_home", "simple_theft_away", "other"],
    "question": "Which claim is this: theft or theft-related damage at the insured location (theft_at_home), a simple theft away from it (simple_theft_away), or anything else (other)?",
    "not_this": "A burglary or robbery away from the insured location (covered, if at all, by the basic cover during travel, Ziff. 26 lit. b) and any other peril: other. Neither type applies to them.",
    "rule": rule(Q("Ziff. 23.3 Abs. 1"), "states", context=[Q("Ziff. 24.2"), Q("Ziff. 26 lit. b")]),
}
OPTIONAL_READING = ("mandatory: false (workflow 'optional: true') marks a document the contract makes due only on CSS's request where no "
                    "CSS document makes that request at intake: the police report ('kann durch die CSS einverlangt werden'; the claim "
                    "form asks only for the report's particulars). At intake the handler does not request it; a reference evaluator "
                    "marks it 'not needed' unless the file contains it, in which case it is assessed as present and sufficient or "
                    "insufficient. Its absence is never a gap. The valued list and the original vouchers are also due 'auf Verlangen', "
                    "but CSS makes that request in its own claim form, so they are requested at intake (mandatory: true).")
TYPE_NOTES = {"theft_at_home": ["The police step (Ziff. 8 lit. f, 'Bei Diebstahl') is also reached when the file reports only vandalism or damage with nothing taken: the text does not say whether 'bei Diebstahl' covers that case, and the rule set does not narrow it."],
              "simple_theft_away": []}
OUTSIDE = ("A burglary or robbery away from the insured location (for example a holiday flat or hotel room "
           "broken into, or a robbery on a trip). Ziff. 26 lit. b covers it, if at all, under the basic cover during travel; "
           "neither type applies, and routing answers 'other'. A theft from a vehicle broken into away from home is a simple "
           "theft away (a vehicle is not a container), so it belongs to type 2.")

TYPES = [home, away]

CONVENTION_TEXT = ("A fact that the file does not mention is taken as not alleged, and the rules are applied as if it were absent. "
                   "Silence never ends a process: where a fact's absence would end it, the unmentioned fact is unresolved. "
                   "The defining event is never presumed: if the file does not mention it, it is unresolved. "
                   "A fact that the file raises and leaves unsettled is open.")
CONVENTION = {"id": "intake_convention", "text": CONVENTION_TEXT,
              "applies_to": "every branch fact (value false, applies unstated) except the defining event, a fact whose value false triggers a stop (none besides the defining events) and a fact marked always_stated; a presumption a passage supports would take precedence (this rule set has none)",
              "rule": {"source_id": "benchmark-convention", "locator": "SPEC.md item 6a", "basis": "convention"}}

# --------------------------------------------------------------------------------------- settled points, left out
SETTLED = [
    ("Third party (old rule 042; Study 3 condition g042)",
     "Left out. In the CSS conditions the only third-party clause is Ziff. 15: \"Sofern die CSS aus diesem Vertrag Leistungen erbracht hat, für welche der Versicherungsnehmer gegenüber Dritten Ansprüche geltend machen könnte, hat der Versicherungsnehmer diese Ansprüche bis zur Höhe der erbrachten Leistungen an die CSS abzutreten.\" Its condition is that CSS has already paid, which an intake file never shows, and its consequence is an assignment, not a document. The passage does not say whether an unidentified thief is a third party against whom claims 'could' be asserted, so no condition may turn on identification. The claim form asks \"Wer hat den Schaden verursacht?\" (Abschnitt 3.5): a question on the form, answerable with 'unknown'; it names no document. Generali's recourse clause (old rule 042's second limb) belongs to another insurer's contract and is not used."),
    ("Traces (old rules 003 and 005; Study 3 condition g003)",
     "Two different clauses use the word. (a) Ziff. 23.3 covers damage \"durch Spuren, Zeugen oder nach den Umständen schlüssig nachgewiesen\": traces are one of three alternative means of proof, and the circumstances alone can suffice, so no document and no condition turns on whether traces exist; the defining event is the event, not its proof. (b) Ziff. 8 lit. f forbids removing or altering traces without the police's consent: the condition is removal or alteration (done or intended), never the mere existence of traces (fact traces_changed)."),
    ("Consents (old rule 003, D26/D27)",
     "Settled from the words for the police's consent: Ziff. 8 lit. f requires it for any removal or alteration of traces and states no exception, so the mitigation and public-interest exceptions of other clauses are not read into it (document police_consent). The insurer's consent to changes of damaged items (VVG Art. 38b) and the 'help services' arm (Simpego only) are left out: the insurer's consent is the insurer's own act, not a document a claimant supplies; CSS Ziff. 8 lit. e forbids such changes without naming any consent; and the Simpego text is another insurer's."),
    ("Insurer's instruction (old rule 004.a, D25)",
     "Settled from the words of VVG Art. 38a Abs. 1: the duty is to obtain the insurer's instruction \"über die zu ergreifenden Massnahmen\", \"wenn nicht Gefahr im Verzug liegt\". It concerns measures to reduce the loss that are still to be taken, does not arise from the notification itself, and lapses under imminent danger. Two facts carry it: measures_pending (true = measures still to be taken) and imminent_danger (true = the exception a claimant would raise; unmentioned = none). The step h_instruction / a_instruction is reached when measures are pending and no danger is raised. No document is attached: the instruction is the insurer's own (the old D25 is not used)."),
    ("Police report (old rules 002, 049)",
     "Settled: CSS Ziff. 8 lit. f makes notifying the police a duty on every theft but says the report \"kann durch die CSS einverlangt werden\", and no CSS document requests it at intake (the claim form asks only for the report's particulars in section 4: Polizeimeldung, Anzeigedatum, Polizeiposten). So the handler does not request it at intake (mandatory: false; see the reading of optional documents)."),
    ("Notification record (old rules 001, 047)",
     "The duty in VVG Art. 38 Abs. 1 is to notify; CSS requires no form (Ziff. 4: \"Wird bei einer Mitteilung kein Formerfordernis angeführt, kann diese auch mündlich erfolgen.\") and its form offers online notification. The document is therefore any record of the notification (notification_record), with no signature item."),
    ("Valued list and original vouchers (old rules 013, 014)",
     "Both rest on the same contract clause, Ziff. 8 lit. c (\"auf Verlangen, ein Verzeichnis ... mit Wertangaben zu erstellen und Originalbelege beizubringen\"), the clause VVG Art. 39 Abs. 2 Ziff. 1 refers to, and are treated alike. The handler is the insurer, so the request is the act being decided; CSS makes it in its own claim form for every stolen or damaged item (section 3.7, with its columns, 'bitte Originalkaufbelege beilegen', or a separate list). At intake both are therefore requested (mandatory: true). The cost limit of Art. 39 applies voucher by voucher: original_vouchers must show the vouchers that can be obtained without considerable cost, and the whole need falls away only when the file states that none can."),
]
LEFT_OUT = [
    ("Insurer's consent to changing damaged items (VVG Art. 38b; CSS Ziff. 8 lit. e)", "the consent is the insurer's own act, not a claimant document; CSS names no consent."),
    ("The claim form's signature and declaration", "not required by the notification duty (VVG Art. 38 Abs. 1; CSS Ziff. 4 allows oral notice)."),
    ("Recovered items: notify CSS (Ziff. 8 lit. h), repay compensation (Ziff. 29 lit. e)", "a step without a document that changes nothing in the intake checklist; repayment arises only after payment."),
    ("Measures to find the thief (Ziff. 8 lit. g)", "a duty \"nach Anleitung der Polizei oder der CSS\" with no document."),
    ("Third-party claims (Ziff. 15)", "applies only after CSS has paid (see the settled points)."),
    ("SIM-card misuse (Ziff. 24.5)", "the two exclusion sentences name no document; the old rule's bank statement had no passage."),
    ("Jewellery and watch limits, safe storage (Ziff. 23.3 lit. d)", "limits of the amount, no document named; the watch sentence is broken across a page in the PDF."),
    ("Alarm system and deductible (Ziff. 28 lit. e)", "affects the deductible only; no document named."),
    ("Emergency glazing, doors and locks; blocking fees; mitigation costs (Ziff. 20 lit. c, f, g)", "cost items beyond the size of the rule set; lit. g turns on CSS's own order."),
    ("Other insurances (form Abschnitt 6.1, Ziff. 25 lit. d)", "the form asks the question itself (insurer and policy number); no separate document is named."),
    ("Payment details, due date, partial payment, limitation, termination, underinsurance, deductible, breach consequences", "not steps or documents of the intake, or no document named."),
    ("All Generali, AXA, Simpego and SVV passages", "another insurer's contract; the rule set applies one insurer's conditions."),
]

# Disposition of the old base (rule_review/lint/final/reviewed_rules.json, 100 rules incl. 004.a and 020.a).
# K kept (rewritten, narrowed to the passage); B dropped: broader than its passage; P dropped: no passage supports the
# document or condition it demands; S dropped: another insurer's contract; O dropped: outside the intake or the size.
OLD = {
    "001": ("K", "notification_record, VVG Art. 38 Abs. 1"),
    "002": ("K", "police step; police_report only on request, as Ziff. 8 lit. f says"),
    "003": ("K", "narrowed to traces removed or altered (traces_changed, police_consent); damaged-items and help-services arms dropped"),
    "004": ("B", "applies identification and recovery measures and the insurer's instruction (D25) to every event; Ziff. 8 lit. g names no document"),
    "004.a": ("K", "instruction step (measures_pending, imminent_danger), without the D25 document"),
    "005": ("K", "defining event; the proof clause no longer drives any document"),
    "006": ("K", "classification: burglary_or_robbery, theft_away"),
    "007": ("K", "type simple_theft_away and its cover stop"),
    "008": ("K", "type theft_at_home"),
    "009": ("O", "jewellery classification (amount); passage broken across a page in the PDF"),
    "010": ("P", "demands D14 (causer section) on every claim; the passage is a question on the form and names no document"),
    "011": ("B", "demands proof documents on every claim from burden-of-proof sentences that name none"),
    "012": ("O", "information on request (VVG Art. 39 Abs. 1): no document"),
    "013": ("K", "stolen_items_list, requested through CSS's claim form"),
    "014": ("K", "original_vouchers, requested through CSS's claim form, with the VVG Art. 39 limit per voucher"),
    "015": ("K", "bicycle_voucher; Generali's photo and estimate (another insurer) dropped"),
    "016": ("S", "Generali valuables insurance"),
    "017": ("S", "Generali / Simpego bodily injury"),
    "018": ("P", "other-insurance documents on every claim; the form only asks the question"),
    "019": ("O", "multiple insurance notice and limit: no document"),
    "020": ("S", "expert procedure (AXA / Generali / SVV)"),
    "020.a": ("O", "assistance in determining the loss: no document"),
    "021": ("S", ""), "022": ("S", ""), "023": ("S", ""), "024": ("S", ""), "025": ("S", ""),
    "026": ("O", "valuation"), "027": ("O", "underinsurance"), "028": ("O", "first-risk"), "029": ("O", "jewellery limit"),
    "030": ("O", "deductible"), "031": ("O", "alarm system, deductible; no document"),
    "032": ("O", "breach consequences"), "033": ("O", "breach consequences"), "034": ("O", "breach consequences"), "035": ("O", "fraud"),
    "036": ("O", "due date"), "037": ("O", "payment postponed"), "038": ("O", "payment postponed"),
    "039": ("S", "Generali deadline"),
    "040": ("O", "recovered items: no document"), "041": ("O", "repayment after payment"),
    "042": ("B", "third party: reads on every theft by an unidentified thief; Ziff. 15 applies only after payment"),
    "043": ("S", "SVV"), "044": ("O", "limitation"), "045": ("O", "after payment"),
    "046": ("O", "payment details (form fields)"), "047": ("B", "requires the signed declaration of the claim form; the notification duty needs no form (Ziff. 4 allows oral notice)"),
    "048": ("O", "limitation"), "049": ("K", "police_report on request"), "050": ("K", "exclusion used in the lock-change rule"),
    "051": ("S", "AXA"), "052": ("S", "Generali"), "053": ("S", "SVV"),
    "054": ("K", "household-member exclusion (stop)"),
    "055": ("O", "limitation"), "056": ("O", "termination"),
    "057": ("K", "'Bei Diebstahl' introduction of the police step"),
    "058": ("O", "allocation among claimants"), "059": ("S", "SVV"), "060": ("O", "payment details"), "061": ("O", "place of performance"),
    "062": ("O", "policy number (form field)"), "063": ("O", "breach"), "064": ("O", "breach"),
    "065": ("S", "SVV"), "066": ("S", "SVV"), "067": ("S", "Simpego"), "068": ("S", "Generali"), "069": ("O", "contract content"),
    "070": ("S", "SVV"), "071": ("O", "assignment of claims"), "072": ("O", "written notice: not required by the CSS conditions"),
    "073": ("O", "cover variant of Ziff. 26"), "074": ("S", "Simpego"),
    "075": ("O", "termination"), "076": ("O", "termination"), "077": ("O", "termination"),
    "078": ("S", "AXA"), "079": ("S", "AXA"), "080": ("O", "mitigation costs ordered by CSS"), "081": ("O", "mitigation costs ordered by CSS"),
    "082": ("S", "Generali"), "083": ("S", "Generali"),
    "084": ("P", "SIM card: demands a bank statement (D33) that no passage names"),
    "085": ("O", "due date"), "086": ("S", "SVV"), "087": ("S", "SVV"),
    "088": ("P", "SIM card: report within 24 hours; demands documents no passage names"),
    "089": ("O", "reference to VVG Art. 46c"), "090": ("S", "Simpego"), "091": ("S", "SVV"),
    "092": ("O", "advance payments"), "093": ("O", "advance payments"), "094": ("O", "scope sentence"),
    "095": ("O", "form field"), "096": ("S", "Generali"), "097": ("S", "Generali"), "098": ("S", "Generali / VVG deadline"),
}
OLD_LABEL = {"K": "kept, rewritten to its passage", "B": "dropped: broader than its passage", "P": "dropped: no passage supports what it demands",
             "S": "dropped: another insurer's contract", "O": "dropped: outside the intake checklist or the size of the set"}


# ------------------------------------------------------------------------------------------------------ writers
def strip(item):
    return {k: v for k, v in item.items() if k != "next"}


def rules_json():
    types = []
    for t in TYPES:
        types.append({"id": t["id"], "title": t["title"], "defining_event": t["defining_event"], "notes": TYPE_NOTES[t["id"]],
                      "facts": [dict(f, type="boolean") for f in t["facts"]],
                      "steps": [strip(s) for s in t["steps"]],
                      "documents": t["documents"], "presumptions": t["presumptions"], "stops": t["stops"]})
    return {"regime": "theft", "version": VERSION,
            "scope": "Claims under a CSS household-contents policy (AVB Ausgabe 02.2024) for theft of household contents; the Insurance Contract Act (VVG) as in force since 1 January 2024.",
            "sources": [{k: s[k] for k in ("id", "title", "publisher", "version", "url", "language", "authoritative")} for s in SOURCES]
            + [{"id": "benchmark-convention", "title": "Convention of this benchmark (not law): Study 4 SPEC.md item 6a", "kind": "benchmark_convention"}],
            "convention": CONVENTION, "routing": ROUTING, "reading_of_optional": OPTIONAL_READING,
            "outside_both_types": OUTSIDE, "types": types}


def snapshots():
    heads = {s["id"]: s for s in SOURCES}
    for sid in ("css-avb", "css-form"):
        s = heads[sid]
        lines = [f"# {s['publisher']}: {s['title']}, {s['version']}",
                 f"# Public URL: {s['url']} (retrieved {s['retrieved']})",
                 "# Quoted passages only (Art. 25 URG); the document is the issuer's copyright and is not stored here.",
                 "# Format: [locator] (Study 1 passage id, or 'added' for a passage not among the Study 1 passages), then the passage on one line."]
        for qsid, loc, text, s1 in QUOTES:
            if qsid == sid:
                lines += ["", f"[{loc}] ({s1 or 'added from the same public document'})", text]
        (SRC / f"{sid}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources_json():
    out = []
    for s in SOURCES:
        row = dict(s)
        row["snapshot_sha256"] = sha(SRC / s["snapshot"])
        out.append(row)
    doc = {"regime": "theft", "built": VERSION, "sources": out, "considered_not_used": CONSIDERED,
           "convention_source": {"id": "benchmark-convention", "kind": "benchmark_convention", "title": "Convention of this benchmark (not law): Study 4 SPEC.md item 6a"},
           "raw_downloads": "sources/raw/ (git-ignored; full documents are not tracked)"}
    (SRC / "SOURCES.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def cite_md(r):
    s = f"{r['source_id']} {r['locator']}: «{r['passage']}»"
    for c in r.get("context", []):
        s += f"<br>context: {c['source_id']} {c['locator']}: «{c['passage']}»"
    return s


def cond_md(c):
    if c is True:
        return "always"
    if "all" in c:
        return " and ".join(cond_md(x) for x in c["all"])
    if "any" in c:
        return "(" + " or ".join(cond_md(x) for x in c["any"]) + ")"
    return f"{c['fact']} = {str(c['is']).lower()}"


def esc(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def rules_md():
    L = ["# Theft rule set from public text (Study 4, step 2a)", "",
         f"Version {VERSION}. Generated by `tools/build.py`; `rules.json` is the same content. Scope: claims under a CSS household-contents policy (AVB Ausgabe 02.2024), with the Insurance Contract Act (VVG, SR 221.229.1, in force since 1 January 2024). One insurer's conditions only, so that no clause is applied outside its own contract. Development material, not a result.", "",
         "Basis: **states** = the passage states the rule; **follows** = it follows by the step in 'inference'; **evidence** = the passage creates the condition and the rule names the document that ordinarily proves it. *mandatory: false* = the passage makes the document due only when CSS asks for it. 'Context' passages are further verbatim quotations the clause relies on (definitions, exclusions, limits).", "",
         "## Sources", "", "| id | document | version | public URL | public today |", "|---|---|---|---|---|"]
    for s in SOURCES:
        L.append(f"| {s['id']} | {esc(s['publisher'])}: {esc(s['title'])} | {esc(s['version'])} | {s['url']} | {esc(s['public_today'])} |")
    L += ["", "Considered and not used: " + "; ".join(f"{c['title']} ({c['status']})" for c in CONSIDERED), "",
          "## Convention of this benchmark (not law)", "", f"> {CONVENTION_TEXT}", "",
          "Rule `intake_convention`, basis `convention`, source `benchmark-convention` (SPEC.md items 6a, 6b). No passage supports a presumption in this rule set, so `presumptions` is empty in both types. The workflows encode the convention as an 'unstated' presumption (value false) on every branch fact except the defining events and the two facts marked `always_stated`: `burglary_or_robbery` (within a theft at home, burglary or robbery and simple theft are both ordinary) and `away_cover_missing` (the supplementary cover is an option, 'sofern ... gewünscht und in der Police aufgeführt', Ziff. 24 Einleitung; the policy settles it). No fact's value false triggers a stop besides the defining events; the two stops on a branch fact (household member, missing supplementary cover) are reached only when the fact is true. Polarity (6b): every branch fact is worded so that true is the circumstance a party would raise; `imminent_danger` is the exception a claimant raises against the instruction duty.", "",
          "## Routing, scope and the reading of optional documents", "",
          "| kind | id | clause | basis | citation and verbatim passage |", "|---|---|---|---|---|",
          f"| routing fact | {ROUTING['fact']} | {esc(ROUTING['question'])} Values: {', '.join(ROUTING['values'])}.<br>*not this:* {esc(ROUTING['not_this'])} | {ROUTING['rule']['basis']} | {esc(cite_md(ROUTING['rule']))} |", "",
          f"Outside both types: {OUTSIDE}", "", f"Reading of optional documents: {OPTIONAL_READING}", ""]
    for t in TYPES:
        L += [f"## Type `{t['id']}`: {t['title']}", "", f"Defining event: `{t['defining_event']}`.", ""] + [f"Note: {n}" for n in TYPE_NOTES[t['id']]] + ["",
              "| kind | id | clause | basis | citation and verbatim passage | inference |", "|---|---|---|---|---|---|"]
        for f in t["facts"]:
            L.append(f"| fact | {f['id']} | {esc(f['question'])}<br>*not this:* {esc(f['not_this'])} | {f['rule']['basis']} | {esc(cite_md(f['rule']))} | {esc(f['rule'].get('inference', ''))} |")
        for s in t["steps"]:
            L.append(f"| step | {s['id']} | {esc(s['title'])}<br>reached when: {cond_md(s['reached_when'])} | {s['rule']['basis']} | {esc(cite_md(s['rule']))} | {esc(s['rule'].get('inference', ''))} |")
        for d in t["documents"]:
            L.append(f"| document | {d['id']} | {esc(d['title'])}<br>step {d['step']}; needed when: {cond_md(d['needed_when'])}; mandatory: {str(d['mandatory']).lower()}<br>must show: {esc('; '.join(d['must_show']))} | {d['rule']['basis']} | {esc(cite_md(d['rule']))} | {esc(d['rule'].get('inference', ''))} |")
        for s in t["stops"]:
            L.append(f"| stop | {s['id']} | {esc(s['title'])}<br>when: {cond_md(s['when'])} | {s['rule']['basis']} | {esc(cite_md(s['rule']))} | {esc(s['rule'].get('inference', ''))} |")
        L.append("")
    L += ["## Open points of the earlier reviews, settled from the words or left out", ""]
    L += [f"- **{a}.** {b}" for a, b in SETTLED]
    L += ["", "## Left out (no passage, no document, another insurer, or beyond the size)", ""]
    L += [f"- {a}: {b}" for a, b in LEFT_OUT]
    counts = {}
    for k, (c, _) in OLD.items():
        counts[c] = counts.get(c, 0) + 1
    L += ["", "## Disposition of the old rule base", "",
          "Old base: `rule_review/lint/final/reviewed_rules.json` (the 98 extracted rules plus the splits 004.a and 020.a). " + "; ".join(f"{OLD_LABEL[c]}: {counts.get(c, 0)}" for c in "KBPSO") + ".", "",
          "| old rule | disposition | note |", "|---|---|---|"]
    for k in sorted(OLD, key=lambda x: (x.split(".")[0], x)):
        c, note = OLD[k]
        L.append(f"| overlay_rule_{k} | {OLD_LABEL[c]} | {esc(note)} |")
    (ROOT / "RULES.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def cite_txt(r):
    out = f"Source: {r['source_id']} {r['locator']}: «{r['passage']}»"
    for c in r.get("context", []):
        out += f"; with {c['source_id']} {c['locator']}: «{c['passage']}»"
    if r.get("inference"):
        out += f" ({r['basis']}: {r['inference']})"
    return out


def rule_text_md():
    L = ["# Theft claims under CSS household-contents insurance: rules", "",
         "These rules apply to claims for theft of household contents under a CSS household-contents policy (AVB Ausgabe 02.2024) and the Swiss Insurance Contract Act (VVG). Each rule quotes the passage it rests on. A fact is answered true, false, open (the file raises it and leaves it unsettled) or not stated. The handler is the insurer (CSS).", "",
         "## Convention of this benchmark (not law)", "",
         "The following rule is a convention of this benchmark, not of the law; no article states it:", "", f"> {CONVENTION_TEXT}", "",
         "## Which claim type applies", "",
         f"{ROUTING['question']} Not this: {ROUTING['not_this']} {cite_txt(ROUTING['rule'])}", "",
         f"Outside both types: {OUTSIDE}", "",
         "## Documents requested at intake and documents only on request", "", OPTIONAL_READING, ""]
    for n, t in enumerate(TYPES, 1):
        steps = {s["id"]: s for s in t["steps"]}
        L += [f"## Type {n}: {t['title']}", "", f"Defining event: {t['defining_event']}.", ""]
        L += [f"Note: {x}" for x in TYPE_NOTES[t["id"]]] + ([""] if TYPE_NOTES[t["id"]] else [])
        L += ["### Facts", ""]
        for f in t["facts"]:
            L.append(f"- **{f['id']}**" + (" (always stated or open in a file; no presumption)" if f.get("always_stated") else "") + f": {f['question']} Not this: {f['not_this']} {cite_txt(f['rule'])}")
        L += ["", "### Stops", ""]
        for s in t["stops"]:
            L.append(f"- {s['title']}: when {cond_md(s['when'])}. {cite_txt(s['rule'])}")
        L += ["", "### Steps, in order", ""]
        for s in t["steps"]:
            L.append(f"- **{s['title']}** ({s['id']}), reached when {cond_md(s['reached_when'])}. {cite_txt(s['rule'])}")
        L += ["", "### Documents", ""]
        for d in t["documents"]:
            due = "mandatory" if d["mandatory"] else "not requested at intake; only if CSS asks for it later (optional)"
            when = cond_md({"all": [steps[d["step"]]["reached_when"], d["needed_when"]]} if d["needed_when"] is not True else steps[d["step"]]["reached_when"])
            L.append(f"- **{d['title']}** ({d['id']}): step {d['step']}; needed when {when}; {due}; must show: {'; '.join(d['must_show'])}. {cite_txt(d['rule'])}")
        L.append("")
    (ROOT / "rule_text.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def stop_on_false(t):
    """Facts whose value false appears in a stop condition."""
    found = set()

    def visit(c):
        if isinstance(c, dict):
            for k in ("all", "any"):
                for x in c.get(k, ()):
                    visit(x)
            if c.get("is") is False:
                found.add(c["fact"])
    for st in t["stops"]:
        visit(st["when"])
    return found


def no_presumption(t):
    return {t["defining_event"]} | stop_on_false(t) | {f["id"] for f in t["facts"] if f.get("always_stated")}


def refs(r):
    out = [f"{r['source_id']}#{r['locator']}"]
    out += [f"{c['source_id']}#{c['locator']}" for c in r.get("context", [])]
    return out


def workflow(t):
    fact_ids = [f["id"] for f in t["facts"]]
    facts = [{"id": "claim_type", "type": "enum", "values": ROUTING["values"],
              "question": f"{ROUTING['question']} (Not this: {ROUTING['not_this']})", "source_refs": refs(ROUTING["rule"])}]
    facts += [{"id": f["id"], "type": "boolean", "question": f"{f['question']} (Not this: {f['not_this']})", "source_refs": refs(f["rule"])} for f in t["facts"]]
    steps = []
    for s in t["steps"]:
        row = {"id": s["id"], "title": s["title"], "role": "claim_handler", "source_refs": refs(s["rule"]),
               "documents": [d["id"] for d in t["documents"] if d["step"] == s["id"]],
               "next": [dict({"to": to, "when": when}, **({"label": label} if label else {})) for to, when, label in s["next"]]}
        if not row["documents"]:
            del row["documents"]
        if not row["next"]:
            del row["next"]
            row["outcome"] = "intake_complete"
        steps.append(row)
    outcomes = [{"id": "intake_complete", "title": "Intake checklist complete", "source_refs": refs(t["steps"][-1]["rule"])}]
    for s in t["stops"]:
        steps.append({"id": s["id"], "title": s["title"], "role": "claim_handler", "source_refs": refs(s["rule"]), "outcome": s["id"]})
        outcomes.append({"id": s["id"], "title": s["title"], "source_refs": refs(s["rule"])})
    docs = []
    for d in t["documents"]:
        row = {"id": d["id"], "title": d["title"], "must_show": d["must_show"], "source_refs": refs(d["rule"]),
               "why": f"{d['rule']['basis']}: {d['rule']['source_id']} {d['rule']['locator']}: «{d['rule']['passage']}»" + (f" {d['rule']['inference']}" if d['rule'].get('inference') else "")}
        if d["needed_when"] is not True:
            row["required_when"] = d["needed_when"]
        if not d["mandatory"]:
            row["optional"] = True
        docs.append(row)
    presumptions = [{"fact": f, "value": False, "applies": "unstated", "source_ref": "benchmark-convention#intake_convention",
                     "text": "Convention of this benchmark (not law): " + CONVENTION_TEXT} for f in fact_ids if f not in no_presumption(t)]
    sources = [{"id": s["id"], "kind": "knowledge", "title": f"{s['publisher']}: {s['title']}, {s['version']}"} for s in SOURCES]
    sources.append({"id": "benchmark-convention", "kind": "process_guidance", "intended_kind": "benchmark_convention",
                    "title": "Convention of this benchmark (not law): Study 4 SPEC.md item 6a"})
    return {"format": "casepath.workflow/1", "id": t["id"], "version": VERSION, "title": f"Household insurance theft claim: {t['title']}",
            "status": "draft", "example": False, "applies_when": {"fact": "claim_type", "is": t["id"]},
            "sources": sources, "facts": facts, "start": t["steps"][0]["id"], "steps": steps, "documents": docs,
            "outcomes": outcomes, "presumptions": presumptions, "open_questions": [],
            "notes": [{"text": "Generated from rules.json by tools/build.py; every fact, step, document and stop cites a verbatim passage of a public source (RULES.md).", "source_refs": ["css-avb#Ziff. 23.3 Abs. 1, S. 7"]}]}


def main():
    snapshots()
    sources_json()
    (ROOT / "rules.json").write_text(json.dumps(rules_json(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    rules_md()
    rule_text_md()
    (ROOT / "workflow").mkdir(exist_ok=True)
    for t in TYPES:
        (ROOT / "workflow" / f"{t['id']}.json").write_text(json.dumps(workflow(t), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("built", ROOT)


if __name__ == "__main__":
    main()
