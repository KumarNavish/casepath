"""The way out of an approved letter (web/outbox.py): the address a case's own files hold for a recipient, the subject,
the handler's correction, and one follow-up date in the package, the note and the case. Synthetic files, no model."""
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from casepath.config import load_settings
from casepath.process import completion
from casepath.read.extract import extract
from casepath.web import outbox
from casepath.web.app import create_app

USER = "N. Kumar"
MAIL = ("From: Lea Brunner <lea.brunner@example.ch>\r\nTo: schaden@example-rechtsschutz.ch\r\nDate: Mon, 10 Feb 2025 09:14:00 +0100\r\n"
        "Subject: Schimmel im Badezimmer, Kramgasse 5\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nGuten Tag\r\n\r\n"
        "Im Badezimmer meiner Wohnung bildet sich seit Dezember schwarzer Schimmel. Ich habe die Verwaltung am 3. Februar schriftlich "
        "informiert.\r\n\r\nFreundliche Grüsse\r\nLea Brunner\r\n").encode()
TOLD = "Ich habe die Verwaltung am 3. Februar schriftlich informiert."


def blocks(text, name="Akte.pdf"):
    return outbox.mail_headers([{"id": "f1", "name": name, "extraction": {"text": text}}])


class AddressTests(unittest.TestCase):
    def test_an_address_is_proposed_only_from_a_mail_the_recipient_sent(self):
        thread = ("Von: Immo Aare AG <verwaltung@immo-aare.example>\nGesendet: 12.02.2025\nBetreff: AW: Schimmel\n\nSehr geehrte Frau Brunner\n\n"
                  "Von: Lea Brunner <lea.brunner@example.ch>\nGesendet: 10.02.2025\nBetreff: Schimmel im Badezimmer\n\nmelden Sie sich bei info@other.example")
        found = outbox.proposed("Frau Lea Brunner", blocks(thread))
        self.assertEqual((found["address"], found["subject"], found["line"]), ("lea.brunner@example.ch", "Schimmel im Badezimmer", "Von: Lea Brunner <lea.brunner@example.ch>"))
        self.assertEqual(outbox.proposed("Immo Aare AG", blocks(thread))["address"], "verwaltung@immo-aare.example")
        self.assertIsNone(outbox.proposed("Herr Peter Muster", blocks(thread)))  # another person: nothing, never the nearest address
        self.assertIsNone(outbox.proposed("Frau Lea Brunner", blocks("Bitte schreiben Sie an lea.brunner@example.ch")))  # running text is no header
        self.assertIsNone(outbox.proposed("", blocks(thread)))

    def test_the_subject_leads_with_the_claim_number_and_answers_the_recipients_mail(self):
        self.assertEqual(outbox.subject("4321.6011.0001", "Unterlagen und Angaben anfordern", "WG: AW: Schimmel im Bad"), "4321.6011.0001 AW: Schimmel im Bad")
        self.assertEqual(outbox.subject("4321.6011.0001", "Rechtliche Einschätzung"), "4321.6011.0001 Rechtliche Einschätzung")
        self.assertEqual(outbox.subject(None, "Rechtliche Einschätzung"), "Rechtliche Einschätzung")
        self.assertEqual(outbox.subject("4321.6011.0001", "x", "Ihr Fall 4321.6011.0001"), "AW: Ihr Fall 4321.6011.0001")  # the number once
        self.assertEqual(outbox.subject("4321.6011.0001", "Titel", pattern="{betreff} ({referenz})"), "Titel (4321.6011.0001)")

    def test_only_an_address_is_an_address(self):
        self.assertTrue(outbox.valid_address("lea.brunner@example.ch"))
        for bad in ("lea", "lea@", "a b@example.ch", "lea@example", "x@example.ch, y@example.ch"):
            self.assertFalse(outbox.valid_address(bad), bad)


class ServiceTests(unittest.TestCase):
    """An intake case on the handler's process with a stored result: the first request is prepared."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        (root / "catalogue").mkdir()
        self.client = TestClient(create_app(load_settings({"CASEPATH_DATA_DIR": str(root / "data"), "CASEPATH_WORKFLOW_CATALOGUE": str(root / "catalogue"),
                                                           "CASEPATH_DEV_USER": USER}), model_factory=lambda: None))
        store = self.store = self.client.app.state.store
        case = store.create_case("Schimmel im Bad (synthetisch)", {"synthetic": True}, USER)
        row = extract("Meldung Lea Brunner.eml", "message/rfc822", MAIL)
        mail = store.add_file(case["id"], "Meldung Lea Brunner.eml", row["media_type"], row["kind"], MAIL, row, USER)["id"]
        fact = lambda f, v, quote=None: {"fact": f, "status": "established", "verdict": "accepted", "value": v,
                                          "citations": [{"file": mail, "quote": quote}] if quote else []}
        run = store.create_run(case["id"], USER)
        store.update_run(run["id"], status="completed", workflow_id="mietmangel-handler", finished_at="2026-11-12T10:00:00+00:00",
                         result={"facts": [fact("rechtsgebiet", "Mietrecht / Mangel"), fact("maengelruege_schriftlich", "ja", TOLD)], "documents": [],
                                 "brief": {"request": "Lea Brunner möchte Hilfe, weil im Badezimmer immer wieder Schimmel auftritt.",
                                           "parties": [{"role": "Mieterin (VN)", "name": "Frau Lea Brunner"}], "timeline": []}})
        self.case = case["id"]

    def tearDown(self):
        self.client.app.state.runs.shutdown()
        self.store.close()
        self.directory.cleanup()

    def view(self):
        return self.client.get(f"/api/cases/{self.case}").json()

    def approve(self, draft, op="op-approve-1"):
        r = self.client.post(f"/api/cases/{self.case}/actions/approve", json={"form": draft["form"], "version": draft["version"], "op_id": op})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["approval"]

    def test_the_address_is_shown_with_its_line_recorded_with_the_approval_and_corrected_by_the_handler(self):
        view = self.view()
        row = view["completion"]["handover"][0]
        self.assertEqual((row["to"], row["address"]["value"], row["address"]["source"]["name"], row["address"]["source"]["line"], row["subject"]),
                         ("kunde", "lea.brunner@example.ch", "Meldung Lea Brunner.eml", "From: Lea Brunner <lea.brunner@example.ch>",
                          "AW: Schimmel im Badezimmer, Kramgasse 5"))
        approval = self.approve(view["draft"])
        self.assertEqual(approval["recipients"][0]["address"], "lea.brunner@example.ch")  # what the handler saw beside «Freigeben»
        refused = self.client.post(f"/api/cases/{self.case}/handover/address", json={"to": "kunde", "address": "keine Adresse"})
        self.assertEqual((refused.status_code, refused.json()["detail"]), (422, "Bitte eine E-Mail-Adresse eingeben."))
        self.assertEqual(self.client.post(f"/api/cases/{self.case}/handover/address", json={"to": "kunde", "address": "lea@example.org"}).status_code, 201)
        row = self.view()["completion"]["handover"][0]
        self.assertEqual((row["address"]["value"], row["address"]["source"], row["address"]["set_by"]), ("lea@example.org", None, USER))
        self.assertTrue(self.view()["completion"]["valid"])  # the approved text is the same text: the approval holds
        logged = [e for e in self.store.list_case_events(self.case) if e["kind"] == "handover.address"]
        self.assertEqual([(e["expert"], e["to"], e["address"]) for e in logged], [(USER, "kunde", "lea@example.org")])
        self.assertEqual(self.client.post(f"/api/cases/{self.case}/handover/address", json={"to": "kunde", "address": ""}).status_code, 201)
        self.assertEqual(self.view()["completion"]["handover"][0]["address"]["value"], "")  # taken away: none is proposed again

    def test_the_package_the_note_and_the_case_say_one_follow_up_date(self):
        view = self.view()
        draft, before = view["draft"], view["follow_after_dispatch"]
        self.assertEqual((draft["form"], before["days"]), ("A1", 28))
        self.approve(draft)
        blob = self.client.get(f"/api/cases/{self.case}/actions/{draft['version']}/bundle").content
        filed = json.loads(zipfile.ZipFile(io.BytesIO(blob)).read("manifest.json"))["follow_up"]["due"]
        self.assertEqual(filed, before["due"])
        today = completion.swiss_today().isoformat()
        r = self.client.post(f"/api/cases/{self.case}/actions/dispatch", json={"version": draft["version"], "date": today, "channel": "email", "op_id": "op-dispatch-1"})
        self.assertEqual(r.status_code, 200, r.text)
        after = self.view()
        row = next(c for c in self.client.get("/api/cases").json()["cases"] if c["id"] == self.case)
        self.assertEqual((after["follow_up"]["due"], after["completion"]["waiting_until"], row["stand"]["date"], row["due"]["date"]), (filed,) * 4)
        self.assertEqual(after["completion"]["waits"], f"wartet auf Kundschaft bis {filed[8:10]}.{filed[5:7]}.{filed[:4]}")


if __name__ == "__main__":
    unittest.main()
