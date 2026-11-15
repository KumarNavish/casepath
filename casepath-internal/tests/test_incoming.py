"""What comes in and is still unanswered creates its own action, at whatever stage the case is (casepath/process/incoming.py).

Scripted and model-free: the facts are what a reader would have recorded with their quotes."""
import copy
import json
import unittest

from casepath.agents import core
from casepath.process import area, incoming, letters
from casepath.process.clock import capped, follow_up, own_deadlines
from casepath.process.items import build_items
from casepath.process.workflows import CatalogueError
from tests.test_areas import INCOMING_FACTS

MANDATE = [("rechtsgebiet", "Mietrecht / Mangel"), ("deckung", "bestätigt"), ("vorgehen", "Mandat an Anwaltskanzlei"),
           ("handlung_a1", "2024-01-10"), ("handlung_a2", "2024-04-02")]
HISTORY = "A1 2024-01-10; A10 2024-03-01; A2 2024-04-02"  # first request, mandate, phone note
CLAIM = ("eingang_kostenforderung", "Kanzlei Muster: Zwischenhonorarnote vom 2024-05-02 über CHF 3'200, im Rahmen der Kostengutsprache",
         "Wir erlauben uns, Ihnen für unsere Bemühungen bis 30. April 2024 CHF 3'200 in Rechnung zu stellen.")
REPORT = ("eingang_mitwirkung", "Kanzlei Muster: Mandat niedergelegt am 2024-05-15, Unterlagen verweigert und Vorstrafe verschwiegen",
          "Trotz mehrfacher Aufforderung hat uns die Klientin die Lohnabrechnungen nicht eingereicht und uns eine Vorstrafe verschwiegen.")
CASE = {"id": "c", "title": "Mandat (synthetisch) 1234.5678.9012", "intake": {}}
WARNED = ("mahnung_androhung", "Protekta: Aufforderung vom 2024-05-20, Unterlagen bis 2024-06-03, sonst Leistungseinstellung",
          "Erhalten wir die Unterlagen bis 3. Juni 2024 nicht, stellen wir unsere Leistungen ein.")  # the written demand (cover.py)


def fact(fid, value, quote=None):
    return {"fact": fid, "status": "established", "verdict": "accepted", "value": value,
            "citations": [{"file": "f1", "page": 2, "quote": quote}] if quote else []}


def prepared(facts, history=HISTORY, as_of="2024-06-20", edits=(), wid="mietmangel-handler"):
    rows = [fact(*f) for f in facts] + ([fact("bisherige_handlungen", history)] if history else [])
    files = [{"name": "Akte.pdf", "extraction": {"cut_of": {"as_of": as_of}, "segments": [{"date": "02.04.2024", "sender": "Protekta"}]}}]
    result = {"facts": rows, "documents": [], "brief": {"request": "Schimmel im Bad.", "parties": [], "timeline": []}}
    state = core.evaluate(area.workflow(wid), [], list(edits), result, "c", files=files)
    items = build_items(state, result, files)
    return state, items, {i["item_id"]: i for i in items}["next_action:0"], files


def decided(value):
    return [{"id": "e1", "op": "set_fact", "args": {"fact": "leistungen_einstellen", "value": value}, "status": "active"}]


def draft(nxt, items):
    forms = area.workflow("mietmangel-handler")["forms"]
    return letters.render(nxt.get("form") or nxt["action"], forms, letters.context(CASE, items, [], {"due": "2024-07-20"}))


class IncomingTests(unittest.TestCase):
    def test_a_an_unanswered_cost_claim_of_the_firm_is_checked_and_paid_not_a_pending_letter(self):
        state, items, nxt = prepared(MANDATE)[:3]
        self.assertEqual((state["evaluation"]["current"]["step"], nxt["action"]), ("mandat", "A2"))  # without it: the mandate's follow-up
        state, items, nxt = prepared(MANDATE + [CLAIM])[:3]
        self.assertEqual(state["evaluation"]["current"]["step"], "mandat")  # the stage does not move
        self.assertEqual((nxt["action"], nxt["value"], nxt["form"]), ("A11", "Kostenforderung prüfen und begleichen", "A11_kosten"))
        self.assertTrue(nxt["reason"].startswith("Kostenforderung vom 02.05.2024 eingegangen, noch offen – Kanzlei Muster: Zwischenhonorarnote über"))
        self.assertIn("CHF 3'200, im Rahmen der Kostengutsprache", nxt["reason"])  # as read, never computed
        self.assertEqual(nxt["evidence"][0]["quote"], CLAIM[2])  # its source one click away
        self.assertEqual(nxt["incoming"], {"kind": "kostenforderung", "fact": "eingang_kostenforderung", "date": "2024-05-02", "value": CLAIM[1]})
        self.assertEqual(draft(nxt, items), (None, "für eine Bestätigung an die Kanzlei ist kein Formular hinterlegt; geprüft und bezahlt wird im Zahlungssystem"))
        self.assertTrue(state["facts"]["kosten_offen"])

    def test_b_a_payment_after_the_claim_answers_it_and_a_later_claim_opens_it_again(self):
        state, _, nxt, _ = prepared(MANDATE + [CLAIM], history=HISTORY + "; A11 2024-05-20")
        self.assertNotEqual(nxt["action"], "A11")
        self.assertNotIn("incoming", nxt)
        self.assertFalse(state["facts"]["kosten_offen"])
        later = ("eingang_kostenforderung", "Bezirksgericht Beispiel: Kostenvorschuss CHF 1'500, Verfügung vom 2024-06-10", "Kostenvorschuss von CHF 1'500")
        state, _, nxt, _ = prepared(MANDATE + [later], history=HISTORY + "; A11 2024-05-20")
        self.assertEqual((nxt["action"], nxt["incoming"]["date"]), ("A11", "2024-06-10"))
        state, _, nxt, _ = prepared(MANDATE + [CLAIM], history=HISTORY, edits=[{"id": "e2", "op": "set_fact", "status": "active",
                                                                               "args": {"fact": "eingang_erledigt_bis", "value": "2024-05-02"}}])
        self.assertNotEqual(nxt["action"], "A11")  # the handler marked it done

    def test_c_a_settlement_paid_does_not_close_while_a_cost_claim_is_open_and_then_closes_without_a_letter(self):
        settled = MANDATE + [("einigung", True), ("zahlung_erhalten", True),
                             ("eingang_zahlung", "Vermieterin: CHF 5'000 an die Klientin bezahlt am 2024-06-01", "CHF 5'000 überwiesen"),
                             ("eingang_kostenforderung", "Kanzlei Muster: Schlussrechnung vom 2024-06-05 über CHF 4'100", "Schlussrechnung CHF 4'100")]
        state, items, nxt, _ = prepared(settled, history=HISTORY + "; A11 2024-06-03")  # the payment confirmed, the final note not yet
        self.assertIsNone(state["evaluation"]["outcome"])
        self.assertEqual(state["evaluation"]["current"]["step"], "abwicklung")
        self.assertEqual((nxt["action"], nxt["incoming"]["kind"]), ("A11", "kostenforderung"))
        state, items, nxt, _ = prepared(settled, history=HISTORY + "; A11 2024-06-03; A11 2024-06-15")
        self.assertEqual(state["evaluation"]["outcome"]["id"], "zahlung")
        self.assertEqual((nxt["action"], nxt["form"]), ("A12", "A12_erledigt"))
        self.assertIsNone(draft(nxt, items)[0])  # closing without a letter
        self.assertNotIn("incoming", nxt)

    def test_d_the_firm_reports_non_cooperation_and_the_handler_decides_whether_benefits_end(self):
        self.assertEqual(prepared(MANDATE + [REPORT])[2]["form"], "A6_androhung")  # without a written demand in the file: the demand first (cover.py)
        state, items, nxt, _ = prepared(MANDATE + [REPORT, WARNED])
        self.assertEqual((nxt["action"], nxt["value"], nxt["form"]), ("A12", "Leistungen einstellen?", "A12_mitwirkung_entscheid"))
        self.assertEqual(draft(nxt, items), (None, "erst nach Ihrem Entscheid «Leistungen einstellen?»"))  # nothing drafted yet
        self.assertEqual(area.workflow("mietmangel-handler")["forms"]["A12_mitwirkung_entscheid"]["needs"], ["leistungen_einstellen"])
        question = {i["item_id"]: i for i in items}["fact:leistungen_einstellen"]
        self.assertEqual((question["value"], question["values"]), (None, ["ja", "nein"]))  # a plain question, [Ja] [Nein]
        self.assertIsNone(state["evaluation"]["outcome"])
        self.assertEqual(nxt["evidence"][0]["quote"], REPORT[2])  # the firm's report one click away

        state, items, nxt, _ = prepared(MANDATE + [REPORT], edits=decided("ja"))
        self.assertEqual((nxt["action"], nxt["form"]), ("A12", "A12_mitwirkung_kanzlei"))
        self.assertEqual(state["evaluation"]["outcome"]["id"], "mitwirkung")
        text, none = draft(nxt, items)
        self.assertIsNone(none)
        self.assertIn("Die von Ihnen beauftragte Kanzlei hat uns mit Schreiben vom 15.05.2024 mitgeteilt, dass Sie bei der Bearbeitung Ihres "
                      f"Falles nicht mitgewirkt haben: «{REPORT[2]}»", text)  # what the report says was withheld, in its words
        # the clause by the edition of the conditions (private 01.2026 unless the handler says otherwise, cover.py)
        self.assertIn("Damit haben Sie Ihre Pflicht zur Mitwirkung gemäss den Allgemeinen Versicherungsbedingungen (Art. M Ziff. 1 und 4) verletzt.", text)
        other = [{"id": "e9", "op": "set_fact", "args": {"fact": "avb_ausgabe", "value": "andere Ausgabe"}, "status": "active"}]
        state, items, nxt, _ = prepared(MANDATE + [REPORT], edits=decided("ja") + other)
        text = draft(nxt, items)[0]
        self.assertIn("Damit haben Sie Ihre Pflicht zur Mitwirkung gemäss den Allgemeinen Versicherungsbedingungen ([bitte ergänzen: Ziffer der Allgemeinen Bedingungen]) verletzt.", text)
        self.assertTrue(letters.has_gap(text))  # another edition: copying is blocked until the clause is filled in
        self.assertNotRegex(text, r"Ziff(er)?\.? \d|Art\. \d")  # no invented clause

        state, items, nxt, _ = prepared(MANDATE + [REPORT], edits=decided("nein"))
        self.assertEqual((nxt["action"], nxt["form"]), ("vorgehen", "vorgehen_neu"))  # back to the way to proceed
        self.assertIn("Leistungen nicht eingestellt", nxt["reason"])
        self.assertIsNone(state["evaluation"]["outcome"])
        self.assertIsNone(draft(nxt, items)[0])
        self.assertEqual(area.workflow("mietmangel-handler")["forms"]["vorgehen_neu"]["needs"], ["vorgehen"])
        later = prepared(MANDATE + [REPORT], history=HISTORY + "; A10 2024-06-01", edits=decided("nein"))[2]
        self.assertNotEqual(later["action"], "vorgehen")  # a new mandate answers it

    def test_e_an_offer_of_the_other_side_is_the_handlers_stance_with_no_draft(self):
        own = [("rechtsgebiet", "Mietrecht / Mangel"), ("deckung", "bestätigt"), ("vorgehen", "Selbst führen"),
               ("eingang_angebot", "Anwalt der Vermieterin: Vergleichsangebot CHF 1'500 per Saldo, Schreiben vom 2024-05-10",
                "offerieren wir Ihrer Mandantin per Saldo aller Ansprüche CHF 1'500")]
        state, items, nxt, _ = prepared(own, history="A1 2024-01-10; A8 2024-04-20")
        self.assertEqual(state["evaluation"]["current"]["step"], "gegenpartei")
        self.assertEqual((nxt["action"], nxt["form"]), ("A9", "A9"))
        self.assertEqual(draft(nxt, items), (None, "die Stellungnahme zu einem Angebot entscheidet die Fallbearbeitung"))
        self.assertIn("CHF 1'500", nxt["evidence"][0]["quote"])
        self.assertNotIn("incoming", prepared(own, history="A1 2024-01-10; A8 2024-04-20; A9 2024-05-14")[2])  # answered

    def test_f_the_customers_statutory_deadline_still_leads_while_an_incoming_item_is_open(self):
        claim = ("eingang_kostenforderung", "Kanzlei Muster: Kostenvorschuss vom 2026-11-10 über CHF 1'200", "Kostenvorschuss von CHF 1'200")
        facts = [("rechtsgebiet", "Mietrecht / Kündigung"), ("kuendigung_erhalten", "2026-11-03"), claim]
        state, items, nxt, files = prepared(facts, history="A1 2026-11-05", as_of="2026-11-14", wid="miete-kuendigung")  # it came after our request
        self.assertEqual(nxt["action"], "A11")
        own = own_deadlines(items, files)
        self.assertEqual((own[0]["key"], own[0]["value"]), ("anfechtung", "2026-12-03"))
        due = capped(follow_up(nxt["next_in_days"], files, []), items, 7, files)
        self.assertEqual((due["due"], due["capped"]["reason"]), ("2026-11-26", "vor Ablauf der gesetzlichen Frist"))

    def test_g_several_open_items_come_in_priority_order_and_a_file_without_any_is_unchanged(self):
        report = ("eingang_bericht", "Kanzlei Muster: Bericht zum Stand vom 2024-05-20, Verhandlung angesetzt", "Die Verhandlung ist angesetzt.")
        nxt = prepared(MANDATE + [report, CLAIM])[2]
        self.assertEqual((nxt["action"], [t["kind"] for t in nxt["then"]]), ("A11", ["bericht"]))
        self.assertEqual(nxt["then"][0]["action"], "Aktennotiz zum Bericht der Kanzlei")
        nxt = prepared(MANDATE + [report, CLAIM, REPORT, WARNED])[2]
        self.assertEqual((nxt["form"], [t["kind"] for t in nxt["then"]]), ("A12_mitwirkung_entscheid", ["kostenforderung", "bericht"]))
        nxt = prepared(MANDATE + [report])[2]
        self.assertEqual((nxt["action"], nxt["form"]), ("A2", "A2_bericht"))  # a report alone: a file note, no stage change
        state, items, nxt, _ = prepared([("rechtsgebiet", "Mietrecht / Mangel")], history=None)  # a fresh case
        self.assertEqual(nxt["action"], "A1")
        self.assertNotIn("incoming", nxt)
        new = {i["key"]: i["value"] for i in items if i["kind"] == "fact" and i["key"] in INCOMING_FACTS}
        self.assertEqual(new, {**{k: None for k in INCOMING_FACTS}, "kosten_offen": False})

    def test_the_reader_gains_one_question_per_item_and_the_validator_refuses_a_kind_it_cannot_carry(self):
        wf = area.workflow("mietmangel-handler")
        read = lambda w: {f["id"] for f in w["facts"] if not f.get("handler_only") and not f.get("derived")}
        self.assertEqual(read(wf) & INCOMING_FACTS, {"eingang_kostenforderung", "eingang_bericht", "eingang_mitwirkung", "eingang_angebot",
                                                   "eingang_zahlung", "eingang_kostenforderung_2", "eingang_kostenforderung_3",
                                                   "eingang_angebot_2", "eingang_zahlung_2"})  # at most three items per kind
        for w in area.shipped():  # backbone facts: every area reads them; observed counts stay with the observed area
            self.assertEqual(len(w["incoming"]), 5)
            if w["id"] != "mietmangel-handler":
                self.assertNotIn("von 7", json.dumps(w["incoming"], ensure_ascii=False))
        self.assertTrue(all(k["note"] == "in 1 von 7 Dossiers beobachtet" or k["note"].startswith("in 1 von 7 Dossiers beobachtet:")
                            for k in wf["incoming"]))
        for change in (lambda b: b["incoming"][0]["action"].__setitem__("form", "A99"),
                       lambda b: b["incoming"][1].__setitem__("priority", 1),
                       lambda b: b["incoming"][2].__setitem__("fact", "kosten_offen"),
                       lambda b: b["incoming"][3].__setitem__("from", ["nachbar"])):
            bb = copy.deepcopy(area.backbone())
            change(bb)
            with self.assertRaises(CatalogueError):
                area.validate_backbone(bb)


VOUCHER = ("eingang_angebot", "Sonnenweit Reisen AG: Reisegutschein über CHF 1'820, einlösbar bis 2027-09-30, E-Mail vom 2026-09-23",
           "Sie erhalten von uns einen Reisegutschein im Wert von CHF 1'820.–")


def fresh(facts, created="2026-11-03", history=None, wid="allgemein", segments=None):
    """A case as it comes in: its files added on the day it was reported, no cut, the facts as a reader would record them."""
    rows = [fact(*f) for f in facts] + ([fact("bisherige_handlungen", history)] if history else [])
    files = [{"id": "f1", "name": "Meldung.pdf", "created_at": f"{created}T09:00:00+00:00", "extraction": {"segments": segments or []}}]
    result = {"facts": rows, "documents": [], "brief": {"request": "Reise annulliert.", "parties": [], "timeline": []}}
    state = core.evaluate(area.workflow(wid), [], [], result, "c", files=files)
    items = build_items(state, result, files)
    return state, items, {i["item_id"]: i for i in items}


class IncomingOrderTests(unittest.TestCase):
    """An item calls for an action only when it came after the insurer's last own step, or after the report while the
    insurer has taken none; before that it is a fact of the case, and at intake the stage's own action leads."""

    def test_a_voucher_the_other_side_gave_before_the_report_is_a_fact_of_the_case_and_the_first_request_stands(self):
        base = fresh([("rechtsgebiet", "Übriges Recht")])[2]["next_action:0"]
        state, items, by = fresh([("rechtsgebiet", "Übriges Recht"), VOUCHER])
        nxt = by["next_action:0"]
        self.assertEqual((nxt["action"], nxt["value"]), (base["action"], base["value"]))
        self.assertEqual(nxt["action"], "A1")  # the first request, never «answer the other side's offer»
        self.assertNotIn("incoming", nxt)
        self.assertNotIn("then", nxt)
        line = by["stand:eingang:eingang_angebot"]  # shown in «Der Fall», with its source
        self.assertEqual((line["label"]["de"], line["open"]), ("Angebot der Gegenpartei", False))
        self.assertTrue(line["value"].startswith("vom 23.09.2026 liegt vor – Sonnenweit Reisen AG: Reisegutschein über CHF 1'820"))
        self.assertTrue(line["value"].endswith("(vor der Meldung des Falls am 03.11.2026)"))
        self.assertEqual(line["evidence"][0]["quote"], VOUCHER[2])
        self.assertIn("Angebot der Gegenpartei: vom 23.09.2026 liegt vor", letters.file_note(CASE, items, [], None))  # and in the file note
        # the same in another area: a deduction the administrator announced before the report, even if read as an offer
        announced = ("eingang_angebot", "Lötscher Immobilien GmbH: Abrechnung folgt, sobald die Rechnung vorliegt, Schreiben vom 2026-06-12",
                     "Sobald die Rechnung vorliegt, erhalten Sie eine Abrechnung")
        base = fresh([("rechtsgebiet", "Mietrecht / Kaution und Rückgabe")], created="2026-10-02", wid="miete-kaution")[2]["next_action:0"]
        nxt = fresh([("rechtsgebiet", "Mietrecht / Kaution und Rückgabe"), announced], created="2026-10-02", wid="miete-kaution")[2]["next_action:0"]
        self.assertEqual((nxt["action"], "incoming" in nxt, "then" in nxt), (base["action"], False, False))
        self.assertEqual(nxt["action"], "A1")

    def test_old_letters_of_the_other_side_in_a_file_read_mid_course_never_replace_the_stages_action(self):
        history = "A1 2024-01-10; A5 2024-03-01"  # our first request and assessment; the other side's e-mails lie long before
        own = [("rechtsgebiet", "Mietrecht / Mangel"), ("deckung", "bestätigt"), ("vorgehen", "Selbst führen")]
        base = prepared(own, history=history)[2]
        old = ("eingang_angebot", "Verwaltung: Entschädigung nur auf schriftliches Gesuch mit Betrag, E-Mail vom 2023-11-02", "nur auf schriftliches Gesuch")
        state, items, nxt, _ = prepared(own + [old], history=history)
        self.assertEqual((nxt["action"], nxt.get("form")), (base["action"], base.get("form")))
        self.assertNotIn("incoming", nxt)
        line = {i["item_id"]: i for i in items}["stand:eingang:eingang_angebot"]
        self.assertIn("(vor dem letzten Schritt von Protekta, A5 vom 01.03.2024)", line["value"])
        undated = ("eingang_angebot", "Verwaltung: Kosten und Reduktion werden geprüft, sobald die Ursache bekannt ist", "sobald die Ursache bekannt ist")
        state, items, nxt, _ = prepared(own + [undated], history=history)  # no date of its own, none of its document: order unknown
        self.assertEqual(nxt["action"], base["action"])
        line = {i["item_id"]: i for i in items}["stand:eingang:eingang_angebot"]
        self.assertEqual((line["open"], line["value"].endswith("(Zeitpunkt prüfen)")), (True, True))
        later = ("eingang_angebot", "Anwalt der Vermieterin: Vergleichsangebot CHF 1'500 per Saldo, Schreiben vom 2024-05-10", "CHF 1'500 per Saldo")
        self.assertEqual(prepared(own + [later], history=history)[2]["action"], "A9")  # after our last step: it calls for its action
        self.assertEqual(incoming.read_item(VOUCHER[1])[0].isoformat(), "2026-09-23")  # its own date, not the date it is valid until

    def test_at_intake_the_assessment_leads_and_an_offer_that_came_after_our_request_follows_it_and_is_named_in_it(self):
        from tests.test_stage_rules import COMPLETE, DEFECT, view
        offer = ("eingang_angebot", "Vermieterin: Mietzinsreduktion von CHF 200 für drei Monate, Schreiben vom 2024-02-01", "Reduktion von CHF 200")
        wants = DEFECT + [("deckung", "bestätigt"), ("weiteres_vorgehen", True), offer]
        state, listed, nxt = view(wants, "A1 2024-01-10", COMPLETE)
        self.assertEqual((state["evaluation"]["current"]["step"], nxt["action"]), ("beurteilen", "A5"))  # the assessment is prepared
        self.assertNotIn("incoming", nxt)
        self.assertEqual([(t["kind"], t["date"], t["action"]) for t in nxt["then"]],
                         [("angebot", "2024-02-01", "Antwort auf das Angebot der Gegenpartei")])  # «danach»
        text = letters.render("A5", area.workflow("mietmangel-handler")["forms"], letters.context(CASE, list(listed.values()), [], {}))[0]
        self.assertIn("In Ihrem Fall: Angebot der Gegenpartei vom 01.02.2024 liegt vor: Vermieterin: Mietzinsreduktion von CHF 200 für drei Monate", text)
        self.assertNotIn("stand:eingang:eingang_angebot", listed)  # it calls for an action: not a mere fact
        state, listed, nxt = view(wants, "A1 2024-01-10; A5 2024-01-20", COMPLETE)  # the assessment went out before it: it leads now
        self.assertEqual((nxt["action"], nxt["incoming"]["kind"]), ("A9", "angebot"))
        state, listed, nxt = view(DEFECT + [("deckung", "bestätigt"), ("weiteres_vorgehen", True)], "A1 2024-01-10", COMPLETE)
        self.assertNotIn("then", nxt)

    def test_the_running_account_says_when_the_case_was_reported_and_whom_an_item_was_addressed_to(self):
        entry = lambda n, day, frm, to, kind="andere": {"n": n, "date": day, "from": frm, "to": to, "kind": kind}
        offer = lambda day: {"date": day, "kind": {"from": ["gegenpartei"]}}
        ledger = {"entries": [entry(1, "2026-09-23", "gegenpartei", "kunde", "angebot"), entry(2, "2026-11-03", "kunde", "versicherer", "meldung")]}
        ref = incoming.reference({}, ledger)
        self.assertEqual((ref["kind"], ref["date"].isoformat()), ("report", "2026-11-03"))
        self.assertEqual(incoming.timing(offer("2026-09-23"), ref, ledger), "fact")  # before the report
        self.assertEqual(incoming.timing(offer("2026-11-03"), ref, ledger), "unknown")  # the same day: order not established
        later = {"entries": ledger["entries"] + [entry(3, "2026-11-08", "gegenpartei", "kunde", "angebot")]}
        self.assertEqual(incoming.timing(offer("2026-11-08"), ref, later), "unknown")  # addressed to the customer, not sent in
        sent = {"entries": later["entries"] + [entry(4, "2026-11-09", "kunde", "versicherer", "unterlagen")]}
        self.assertEqual(incoming.timing(offer("2026-11-08"), ref, sent), "call")  # the customer sent it in as new
        to_us = {"entries": ledger["entries"] + [entry(3, "2026-11-08", "gegenpartei", "versicherer", "angebot")]}
        self.assertEqual(incoming.timing(offer("2026-11-08"), ref, to_us), "call")  # addressed to the insurer
        step = incoming.reference({"bisherige_handlungen": "A1 2026-11-05"}, ledger)  # once the insurer acted, its last step counts
        self.assertEqual((step["kind"], incoming.timing(offer("2026-11-04"), step, ledger), incoming.timing(offer("2026-11-08"), step, later)),
                         ("step", "fact", "call"))
        self.assertIsNone(incoming.reference({}, None, [], None))  # nothing to go by: every item's order is unknown
        self.assertEqual(incoming.timing(offer("2026-11-08"), None), "unknown")

    def test_what_counts_as_each_kind_reaches_the_reader_and_the_checker_with_the_nearest_thing_that_does_not(self):
        from casepath.agents import team
        for w in area.shipped():
            defs = {f["id"]: f for f in w["facts"]}
            for kind in w["incoming"]:
                for fid in incoming.slots(kind):
                    self.assertTrue(defs[fid].get("not_this"), fid)
                    self.assertEqual(team.fact_view(defs[fid])["not_this"], defs[fid]["not_this"])  # the reader's and the second reading's view
        defs = {f["id"]: f for f in area.workflow("allgemein")["facts"]}
        offer = defs["eingang_angebot"]
        self.assertIn("eine bestimmte Leistung (Betrag, Handlung oder Termin), die die Kundschaft so annehmen kann", offer["question"])
        for word in ("Einladung, ein Gesuch zu stellen", "Forderung zu beziffern", "Versprechen, die Sache zu prüfen", "Bedingung", "Ablehnung", "Eingangsbestätigung"):
            self.assertIn(word, offer["not_this"])
            self.assertIn(word, defs["eingang_angebot_2"]["not_this"])
        self.assertIn("Zahlungsaufforderung mit Betrag oder eine Honorarnote", defs["eingang_kostenforderung"]["question"])
        self.assertIn("Ankündigung, dass Kosten entstehen", defs["eingang_kostenforderung_3"]["not_this"])
        self.assertIn("nicht geliefert oder Tatsachen verschwiegen", defs["eingang_mitwirkung"]["question"])
        self.assertIn("Unterlagen noch ausstehen", defs["eingang_mitwirkung"]["not_this"])
        self.assertIn("tatsächlich bezahlt", defs["eingang_zahlung"]["question"])
        self.assertIn("Versprechen", defs["eingang_zahlung_2"]["not_this"])
        self.assertIn("Eingangsbestätigung", defs["eingang_bericht"]["not_this"])


if __name__ == "__main__":
    unittest.main()
