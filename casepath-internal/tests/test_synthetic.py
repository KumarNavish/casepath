import json
from pathlib import Path
import tempfile
import unittest

from pypdf import PdfReader

from casepath_internal import synthetic
from casepath_internal.azure_model import ModelResult
from casepath_internal.extract import extract
from casepath_internal.scorecard import guard
from casepath_internal.schema import validate_result

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "example-defect.json").read_text())
REFERENCE = ["Sehr geehrte Frau Muster, wir bestätigen den Eingang Ihrer Mängelrüge vom 3. Mai betreffend Schimmel im Badezimmer. "
             "Bitte kontaktieren Sie uns unter 031 555 12 34 oder anna.muster@example.ch. Police 8017.0833.0054."]


def document(**fields):
    base = {"kind": "letter", "title": "Mängelrüge Schimmel Badezimmer", "date": "2025-02-03", "sender": "Lea Brunner\nKramgasse 5\n3011 Bern",
            "recipient": "Immo Aare AG\nPostfach\n3001 Bern", "language": "de", "layout": "letterhead", "features": ["signature", "page_numbers"],
            "blocks": [{"type": "paragraph", "label": "", "text": "Sehr geehrte Damen und Herren, im Badezimmer meiner Wohnung bildet sich seit "
                        "Wochen trotz regelmässigem Lüften schwarzer Schimmel an der Aussenwand. " * 6},
                       {"type": "field", "label": "Mietobjekt", "text": "3-Zimmerwohnung, 2. OG links"},
                       {"type": "redaction", "label": "", "text": "Telefonnummer der Mieterin"},
                       {"type": "signature", "label": "", "text": "Lea Brunner"}], "meets_needs": ["customer_message"]}
    return {**base, **fields}


CASE = {"title": "Schimmel im Bad, Kramgasse", "customer": "Lea Brunner",
        "documents": [document(), document(title="Antwort der Verwaltung", layout="scan", date="2025-02-20", kind="letter",
                                           features=["stamp"], blocks=[{"type": "paragraph", "label": "", "text": "Wir prüfen die Angelegenheit. " * 30},
                                                                       {"type": "stamp", "label": "", "text": "EINGEGANGEN 21. FEB. 2025"}],
                                           meets_needs=["notice_letter"]),
                      document(title="Weiterleitung", layout="email", date="2025-03-01", kind="email")],
        "truth": {"facts": [{"fact": "landlord_notified", "value": "yes"}], "present": ["customer_message", "notice_letter"],
                  "outcome": "reported", "notes": "Synthetic test case."}}


class FakeModel:
    def __init__(self, answers):
        self.answers = list(answers)

    def respond_json(self, *, name, instructions, input, schema, effort="medium"):
        value = self.answers.pop(0)
        validate_result(value, schema)
        return ModelResult(value=value, usage={}, deployment="d", response_id="r", attempts=1, seconds=0)


class SyntheticTests(unittest.TestCase):
    def test_generated_case_matches_its_schema_and_profile_hides_identifiers(self):
        profile = {"family_hint": "Mietmangel", "situation": "Tenant reports mould; landlord replies late.",
                   "documents": [{"kind": "letter", "purpose": "defect notice", "sender_role": "tenant", "recipient_role": "landlord",
                                  "language": "de", "pages": 1, "day_offset": 0, "layout": "letterhead", "features": ["signature"], "register": "formal"}],
                   "messiness": ["the reply crosses a reminder"], "identifiers": ["Anna Muster", "8017.0833.0054"]}
        model = FakeModel([profile, CASE])
        made = synthetic.make_profile(model, [{"name": "ref.pdf", "kind": "pdf", "text": REFERENCE[0]}])
        case = synthetic.generate_case(model, made, FIXTURE, variation="landlord never answers")
        self.assertEqual(case["truth"]["outcome"], "reported")

    def test_copy_guard_blocks_reused_text_and_identifiers(self):
        self.assertTrue(synthetic.copy_guard(REFERENCE, CASE, identifiers=["Anna Muster"])["ok"])
        copied = json.loads(json.dumps(CASE))
        copied["documents"][0]["blocks"][0]["text"] = REFERENCE[0]
        verdict = synthetic.copy_guard(REFERENCE, copied)
        self.assertFalse(verdict["ok"])
        self.assertGreater(verdict["shared_ngrams"], 5)
        leaked = json.loads(json.dumps(CASE))
        leaked["documents"][1]["sender"] = "Anna Muster, Verwaltung"
        self.assertEqual(synthetic.copy_guard(REFERENCE, leaked, identifiers=["Anna Muster"])["identifiers_reused"], 1)
        numbered = json.loads(json.dumps(CASE))
        numbered["documents"][2]["blocks"][0]["text"] += " Police 8017.0833.0054"
        self.assertFalse(synthetic.copy_guard(REFERENCE, numbered)["ok"])
        guard(synthetic.copy_guard(REFERENCE, CASE))

    def test_rendered_dossier_reads_like_a_case_file(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = synthetic.render_case(CASE, directory)
            self.assertEqual([f["date"] for f in manifest["files"]], sorted(f["date"] for f in manifest["files"]))
            digital = (Path(directory) / "documents" / manifest["files"][0]["file"]).read_bytes()
            read = extract("letter.pdf", "application/pdf", digital)
            self.assertIn("Badezimmer meiner Wohnung", read["text"])
            self.assertNotIn("Telefonnummer der Mieterin", read["text"])
            scanned = (Path(directory) / "documents" / manifest["files"][1]["file"]).read_bytes()
            scan = extract("scan.pdf", "application/pdf", scanned)
            self.assertFalse(scan["readable"])
            self.assertIn("no text layer", scan["note"])
            dossier = PdfReader(str(Path(directory) / "dossier.pdf"))
            self.assertGreaterEqual(len(dossier.pages), 3)
            saved = json.loads((Path(directory) / "case.json").read_text())
            self.assertTrue(saved["synthetic"])

    def test_judge_scores_without_content(self):
        model = FakeModel([{"real": "A", "confidence": 0.6, "tells": ["too_clean"]}] * 10)
        card = synthetic.judge_pairs(model, REFERENCE, ["Synthetic text " * 40], pairs=10)
        self.assertEqual(card["pairs"], 10)
        self.assertTrue(0 <= card["accuracy"] <= 1)
        guard(card)


if __name__ == "__main__":
    unittest.main()
