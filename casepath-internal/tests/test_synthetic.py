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
    """Answers in order, or per call name when given a dict of callables (for calls made in parallel)."""

    def __init__(self, answers):
        self.answers = answers if isinstance(answers, dict) else list(answers)
        self.inputs = []

    def respond_json(self, *, name, instructions, input, schema, effort="medium"):
        self.inputs.append((name, input))
        value = self.answers[name](input) if isinstance(self.answers, dict) else self.answers.pop(0)
        validate_result(value, schema)
        return ModelResult(value=value, usage={}, deployment="d", response_id="r", attempts=1, seconds=0)


class SyntheticTests(unittest.TestCase):
    def test_a_case_is_planned_then_written_document_by_document(self):
        profile = {"family_hint": "Mietmangel", "situation": "Tenant reports mould; landlord replies late.",
                   "documents": [{"kind": "letter", "purpose": "defect notice", "sender_role": "tenant", "recipient_role": "landlord",
                                  "language": "de", "pages": 1, "day_offset": 0, "layout": "letterhead", "features": ["signature"], "register": "formal"}],
                   "messiness": ["the reply crosses a reminder"], "identifiers": ["Anna Muster", "8017.0833.0054"]}
        plan = {**{k: CASE[k] for k in ("title", "customer", "truth")},
                "documents": [{**{k: d[k] for k in d if k != "blocks"}, "pages": 1, "content": f"Document {i}."} for i, d in enumerate(CASE["documents"])]}
        model = FakeModel({"casepath_profile": lambda _: profile, "casepath_synthetic_plan": lambda _: plan,
                           "casepath_synthetic_document": lambda ask: {"blocks": CASE["documents"][json.loads(ask[0]["content"])["write"]]["blocks"]}})
        files = [{"id": "f1", "name": "ref.pdf", "kind": "pdf", "pages": 3, "pages_transcribed": [2, 3],
                  "text": "[page 1]\n" + REFERENCE[0] + "\n\n[page 2]\nAntwort der Verwaltung.\n\n[page 3]\nWeiter.",
                  "segments": [{"first_page": 1, "last_page": 1, "kind": "Mängelrüge", "date": "03.05.2025"},
                               {"first_page": 2, "last_page": 3, "kind": "Antwort", "date": "20.05.2025"}]}]
        made = synthetic.make_profile(model, files)
        sent = json.loads(model.inputs[0][1][0]["content"])
        self.assertEqual([(d["kind"], d["pages"]) for d in sent["documents"]], [("Mängelrüge", 1), ("Antwort", 2)])
        self.assertEqual(sent["pages_scanned"], 2)
        case = synthetic.generate_case(model, made, FIXTURE, variation="landlord never answers", workers=3)
        self.assertEqual(case["truth"]["outcome"], "reported")
        self.assertEqual([d["blocks"] for d in case["documents"]], [d["blocks"] for d in CASE["documents"]])
        self.assertNotIn("content", case["documents"][0])
        written = [json.loads(i[0]["content"]) for n, i in model.inputs if n == "casepath_synthetic_document"]
        self.assertTrue(all(len(w["plan"]) == 3 and "Anna Muster" in w["blocked_identifiers"] for w in written))

    def test_real_documents_come_from_the_reading_split(self):
        files = [{"id": "f1", "name": "d.pdf", "kind": "pdf", "text": "[page 1]\nEins.\n\n[page 2]\nZwei.\n\n[page 3]\nDrei.",
                  "segments": [{"first_page": 1, "last_page": 2, "kind": "Brief", "date": ""}, {"first_page": 3, "last_page": 3, "kind": "Foto", "date": ""}]}]
        self.assertEqual([r["text"] for r in synthetic.documents_of(files)], ["Eins. Zwei.", "Drei."])

    def test_results_are_scored_against_the_synthetic_truth(self):
        truth = {"facts": [{"fact": "landlord_notified", "value": "yes"}, {"fact": "legal_area", "value": "tenancy_defect"},
                           {"fact": "x", "value": None}], "present": ["customer_message", "notice_letter"], "outcome": "reported"}
        result = {"facts": [{"fact": "landlord_notified", "status": "established", "value": True, "verdict": "accepted"}]}
        evaluation = {"documents": [{"document": "customer_message", "status": "present"}, {"document": "notice_letter", "status": "missing"},
                                    {"document": "photo", "status": "present"}], "outcome": {"id": "reported"}}
        card = synthetic.score_against_truth(truth, result, evaluation)
        self.assertEqual(card["facts"], {"correct": 1, "wrong": 0, "not_found": 1})
        self.assertEqual(card["documents"], {"found": 1, "missed": 1, "found_but_absent": 1})
        self.assertTrue(card["outcome_match"])
        guard(card)

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
        sides = [json.loads(i[0]["content"]) for _, i in model.inputs]
        self.assertTrue(all(len(s["A"]) == len(s["B"]) for s in sides))  # same length: length is no tell
        guard(card)

    def test_page_judge_sees_two_page_images(self):
        real, fake = synthetic.render_digital(document(), CASE), synthetic.render_scanned(document(layout="scan"), CASE)
        model = FakeModel([{"real": "B", "confidence": 0.5, "tells": ["scan_quality"]}] * 4)
        card = synthetic.judge_pages(model, [(real, 1)], [(fake, 1)], pairs=4)
        images = [c for c in model.inputs[0][1][0]["content"] if c["type"] == "input_image"]
        self.assertEqual((card["mode"], card["pairs"], len(images)), ("pages", 4, 2))
        guard(card)


if __name__ == "__main__":
    unittest.main()
