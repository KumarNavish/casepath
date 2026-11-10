"""Outlook .msg e-mails and e-mail attachments: read in the standard library, each attachment a file of the case."""
import datetime
from email.message import EmailMessage
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from casepath.read import msg
from casepath.web.app import create_app
from casepath.config import load_settings
from casepath.read.extract import attachments, extract
from tests.msgfile import build_msg, message
from tests.test_pdfread import text_and_scan_pdf

FIXTURES = Path(__file__).parent / "fixtures"
SENT = datetime.datetime(2025, 3, 4, 9, 30, tzinfo=datetime.timezone.utc)


def outlook_message():
    forwarded = message(subject="WG: Antwort der Verwaltung", body="Siehe unten.", header_size=24,
                        attachments=[("Notiz.txt", "Die Verwaltung lässt den Schimmel prüfen.".encode())])
    return build_msg(subject="Schimmel im Bad – Mängelrüge", body="Grüezi\r\n\r\nIm Anhang die Mängelrüge vom 3. März.\r\nFreundliche Grüsse",
                     sender_name="Lea Brunner", sender_address="lea@example.ch", to="schaden@example-rechtsschutz.ch", sent=SENT,
                     attachments=[("Mängelrüge.pdf", text_and_scan_pdf()), ("Weiterleitung", forwarded)])


class OutlookTests(unittest.TestCase):
    def test_a_message_its_attachments_and_an_attached_message(self):
        read = msg.read(outlook_message())
        self.assertEqual((read["from"], read["to"], read["subject"]), ("Lea Brunner <lea@example.ch>", "schaden@example-rechtsschutz.ch",
                                                                       "Schimmel im Bad – Mängelrüge"))
        self.assertEqual(read["date"], "Tue, 04 Mar 2025 09:30:00 +0000")
        self.assertEqual(read["body"], "Grüezi\n\nIm Anhang die Mängelrüge vom 3. März.\nFreundliche Grüsse")
        pdf, forwarded = read["attachments"]
        self.assertEqual((pdf["name"], pdf["data"]), ("Mängelrüge.pdf", text_and_scan_pdf()))  # larger than a mini stream
        self.assertEqual(forwarded["name"], "WG: Antwort der Verwaltung.eml")
        self.assertEqual([a["name"] for a in forwarded["attachments"]], ["Notiz.txt"])

    def test_an_html_only_body_is_read_as_text(self):
        data = build_msg(subject="Termin", html="<html><head><style>p{}</style></head><body><p>Besichtigung am&nbsp;<b>12. Mai</b></p><p>Gruss</p></body></html>")
        self.assertEqual(msg.read(data)["body"], "Besichtigung am 12. Mai\n\nGruss")

    def test_a_msg_file_is_an_email_of_the_case(self):
        result = extract("Mängelrüge.msg", "application/octet-stream", outlook_message())
        self.assertEqual((result["kind"], result["media_type"]), ("email", "application/vnd.ms-outlook"))
        self.assertTrue(result["text"].startswith("From: Lea Brunner <lea@example.ch>\nTo: schaden@example-rechtsschutz.ch\nDate: "))
        self.assertIn("Subject: Schimmel im Bad – Mängelrüge\n\nGrüezi", result["text"])
        self.assertEqual(result["attachments"], ["Mängelrüge.pdf", "WG: Antwort der Verwaltung.eml"])
        self.assertEqual([name for name, _ in attachments("Mängelrüge.msg", None, outlook_message())],
                         ["Mängelrüge.pdf", "WG: Antwort der Verwaltung.eml", "Notiz.txt"])

    def test_a_damaged_message_is_reported_not_guessed(self):
        result = extract("kaputt.msg", None, outlook_message()[:1200])
        self.assertFalse(result["readable"])
        self.assertEqual(attachments("kaputt.msg", None, outlook_message()[:1200]), [])


class AttachmentUploadTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        settings = load_settings({"CASEPATH_DATA_DIR": self.directory.name, "CASEPATH_WORKFLOW_CATALOGUE": str(FIXTURES), "CASEPATH_DEV_USER": "dev"})
        self.client = TestClient(create_app(settings, model_factory=lambda: None))
        self.addCleanup(self.client.close)
        self.case = self.client.post("/api/cases", json={"title": "Schimmel"}).json()

    def files(self):
        return {f["name"]: f for f in self.client.get(f"/api/cases/{self.case['id']}").json()["files"]}

    def test_an_outlook_message_brings_its_attachments_as_files(self):
        uploaded = self.client.post(f"/api/cases/{self.case['id']}/files", files={"file": ("Meldung.msg", outlook_message(), "application/vnd.ms-outlook")})
        self.assertEqual(uploaded.status_code, 201, uploaded.text)
        self.assertEqual(len(uploaded.json()["attachments"]), 3)
        files = self.files()
        self.assertEqual(set(files), {"Meldung.msg", "Mängelrüge.pdf", "WG: Antwort der Verwaltung.eml", "Notiz.txt"})
        pdf = files["Mängelrüge.pdf"]
        self.assertEqual((pdf["kind"], pdf["extraction"]["attached_to"], pdf["extraction"]["pages_without_text"]), ("pdf", "Meldung.msg", [2]))

    def test_an_eml_attachment_is_read_too(self):
        email = EmailMessage()
        email["From"], email["Subject"] = "lea@example.ch", "Mängelrüge"
        email.set_content("Im Anhang.")
        email.add_attachment(text_and_scan_pdf(), maintype="application", subtype="pdf", filename="Mängelrüge.pdf")
        self.client.post(f"/api/cases/{self.case['id']}/files", files={"file": ("Meldung.eml", email.as_bytes(), "message/rfc822")})
        files = self.files()
        self.assertEqual(files["Mängelrüge.pdf"]["extraction"]["attached_to"], "Meldung.eml")
        self.assertTrue(files["Mängelrüge.pdf"]["extraction"]["readable"])


if __name__ == "__main__":
    unittest.main()
