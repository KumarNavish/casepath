"""The Versandpaket (web/bundle.py): deterministic bytes, one folder per recipient, the exact text in each .docx, the
manifest naming every member with its SHA-256. Model-free."""
import hashlib
import io
import json
import re
import unittest
import zipfile

from casepath.web import bundle

LETTER = "Unsere Referenz: 4321.6011.0001\n\nSehr geehrte Frau Exempel\n\nVielen Dank für Ihre Unterlagen.\n\nFreundliche Grüsse"
DRAFT = {"form": "A10", "kind": "A10", "title": "Mandatsanfrage an die Kanzlei", "text": LETTER,
         "also": [{"kind": "A10_kostengutsprache", "title": "Kostengutsprache", "text": "Kostengutsprache für die Abklärung"},
                  {"kind": "A10_kunde", "title": "Information der Kundschaft zum Mandat", "text": "Für die weitere Wahrung Ihrer Interessen …"},
                  {"kind": "vorlage:x", "title": "Vorlage für Ihr Schreiben an die Vermieterschaft", "name": "Mängelrüge: Frist?",
                   "text": "Sehr geehrte Damen und Herren", "template": True}],
         "recipients": [{"to": "kanzlei", "recipient": "Sehr geehrte Damen und Herren · Kanzlei Muster", "forms": ["A10", "A10_kostengutsprache", "vorlage:x"]},
                        {"to": "kunde", "recipient": "Sehr geehrte Frau Exempel · Frau Sara Exempel", "forms": ["A10_kunde"]}]}
APPROVAL = {"version": "a" * 64, "form": "A10", "title": "Mandatsanfrage an die Kanzlei", "expert": "N. Kumar", "at": "2026-11-15T09:00:00+00:00",
            "recipients": DRAFT["recipients"], "respond_by": None, "chosen": None, "options_sha256": None, "run_id": "run_1", "files_digest": "f" * 64}


def texts(docx_bytes):
    xml = zipfile.ZipFile(io.BytesIO(docx_bytes)).read("word/document.xml").decode()
    return [t.replace("&amp;", "&") for t in re.findall(r'<w:t xml:space="preserve">([^<]*)</w:t>', xml)]


class BundleTests(unittest.TestCase):
    def test_the_same_approval_gives_the_same_bytes_with_fixed_dates_inside_and_out(self):
        one, manifest = bundle.build(DRAFT, APPROVAL, "Aktennotiz", ["Rückmeldung"], follow_up="2026-12-15", parity_sha="p" * 64)
        two, _ = bundle.build(DRAFT, APPROVAL, "Aktennotiz", ["Rückmeldung"], follow_up="2026-12-15", parity_sha="p" * 64)
        self.assertEqual(one, two)
        archive = zipfile.ZipFile(io.BytesIO(one))
        self.assertEqual(archive.namelist(), sorted(archive.namelist()))
        self.assertTrue(all(i.date_time == bundle.STAMP for i in archive.infolist()))
        for name in archive.namelist():
            if name.endswith(".docx"):
                inner = zipfile.ZipFile(io.BytesIO(archive.read(name)))
                self.assertTrue(all(i.date_time == bundle.STAMP for i in inner.infolist()), name)
        self.assertEqual(bundle.docx("Text"), bundle.docx("Text"))
        self.assertNotEqual(bundle.docx("Text"), bundle.docx("Text."))

    def test_one_folder_per_recipient_the_exact_text_and_a_manifest_of_every_member(self):
        blob, manifest = bundle.build(DRAFT, APPROVAL, "Aktennotiz der Fassung", ["Rückmeldung"], follow_up="2026-12-15")
        archive = zipfile.ZipFile(io.BytesIO(blob))
        self.assertEqual(sorted(archive.namelist()), ["Aktennotiz.txt", "Beilagen.txt", "Kanzlei/Brief.docx", "Kanzlei/Kostengutsprache.docx",
                                                      "Kanzlei/Mängelrüge- Frist-.docx", "Kundschaft/Information der Kundschaft zum Mandat.docx",
                                                      "Wiedervorlage.txt", "manifest.json"])
        self.assertEqual(texts(archive.read("Kanzlei/Brief.docx")), [line for line in LETTER.split("\n") if line])
        self.assertEqual(texts(archive.read("Kundschaft/Information der Kundschaft zum Mandat.docx")), ["Für die weitere Wahrung Ihrer Interessen …"])
        self.assertEqual(archive.read("Wiedervorlage.txt").decode(), "Wiedervorlage 15.12.2026\nErwartet: Rückmeldung\n")
        self.assertEqual(archive.read("Aktennotiz.txt").decode(), "Aktennotiz der Fassung\n")
        self.assertIn("Kundschaft (Sehr geehrte Frau Exempel · Frau Sara Exempel): Information der Kundschaft zum Mandat", archive.read("Beilagen.txt").decode())
        stored = json.loads(archive.read("manifest.json"))
        self.assertEqual(stored, manifest)
        self.assertEqual((stored["format"], stored["version"], stored["approved_by"], stored["run_id"]),
                         ("casepath.versandpaket/1", "a" * 64, "N. Kumar", "run_1"))
        for part in stored["parts"]:
            self.assertEqual(part["sha256"], hashlib.sha256(archive.read(part["name"])).hexdigest(), part["name"])
        self.assertEqual(bundle.member(blob, "A10_kunde")[0], "Information der Kundschaft zum Mandat.docx")
        self.assertIsNone(bundle.member(blob, "A12"))
        dated = bundle.build(DRAFT, {**APPROVAL, "respond_by": "2026-11-22"}, "", [])[0]
        self.assertEqual(zipfile.ZipFile(io.BytesIO(dated)).read("Wiedervorlage.txt").decode(), "Antwort erwartet bis 22.11.2026\nErwartet: Rückmeldung\n")

    def test_the_file_name_carries_the_reference_or_the_case_and_the_approval_day(self):
        self.assertEqual(bundle.file_name({"title": "D11-Analogon A (synthetisch) 4321.6011.0001"}, "2026-11-15T09:00:00+00:00"),
                         "Versandpaket_4321.6011.0001_15.11.2026.zip")
        self.assertEqual(bundle.file_name({"title": "Schimmel im Bad / Kramgasse"}, "2026-11-15T09:00:00+00:00"),
                         "Versandpaket_Schimmel-im-Bad-Kramgasse_15.11.2026.zip")


if __name__ == "__main__":
    unittest.main()
