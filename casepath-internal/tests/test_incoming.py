"""What comes in and is still unanswered creates its own action, at whatever stage the case is (casepath/process/incoming.py).

Scripted and model-free: the facts are what a reader would have recorded with their quotes."""
import copy
import json
import unittest

from casepath.agents import core
from casepath.process import area, letters
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
        self.assertTrue(nxt["reason"].startswith("Kostenforderung vom 02.05.2024 eingegangen, noch offen (Kanzlei Muster: Zwischenhonorarnote"))
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
        state, items, nxt, _ = prepared(MANDATE + [REPORT])
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
        self.assertIn("Damit haben Sie Ihre Pflicht zur Mitwirkung gemäss den Allgemeinen Versicherungsbedingungen ([bitte ergänzen: Ziffer der AVB]) verletzt.", text)
        self.assertTrue(letters.has_gap(text))  # copying is blocked until the clause is filled in
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
        facts = [("rechtsgebiet", "Mietrecht / Kündigung"), ("kuendigung_erhalten", "2026-11-03"), CLAIM]
        state, items, nxt, files = prepared(facts, history=None, as_of="2026-11-14", wid="miete-kuendigung")
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
        nxt = prepared(MANDATE + [report, CLAIM, REPORT])[2]
        self.assertEqual((nxt["form"], [t["kind"] for t in nxt["then"]]), ("A12_mitwirkung_entscheid", ["kostenforderung", "bericht"]))
        nxt = prepared(MANDATE + [report])[2]
        self.assertEqual((nxt["action"], nxt["form"]), ("A2", "A2_bericht"))  # a report alone: a file note, no stage change
        state, items, nxt, _ = prepared([("rechtsgebiet", "Mietrecht / Mangel")], history=None)  # a fresh case
        self.assertEqual(nxt["action"], "A1")
        self.assertNotIn("incoming", nxt)
        new = {i["key"]: i["value"] for i in items if i["kind"] == "fact" and i["key"] in INCOMING_FACTS}
        self.assertEqual(new, {**{k: None for k in INCOMING_FACTS}, "kosten_offen": False})

    def test_the_reader_gains_one_question_per_kind_and_the_validator_refuses_a_kind_it_cannot_carry(self):
        wf = area.workflow("mietmangel-handler")
        read = lambda w: {f["id"] for f in w["facts"] if not f.get("handler_only") and not f.get("derived")}
        self.assertEqual(read(wf) & INCOMING_FACTS, {"eingang_kostenforderung", "eingang_bericht", "eingang_mitwirkung", "eingang_angebot",
                                                   "eingang_zahlung"})
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


if __name__ == "__main__":
    unittest.main()
