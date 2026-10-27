import io
import json
import tempfile
import unittest
from unittest import mock

from pypdf import PdfWriter

from casepath_internal import reading
from casepath_internal.azure_model import ModelError, ModelResult
from casepath_internal.extract import extract
from casepath_internal.store import CaseStore
from casepath_internal.synthetic import render_digital, render_scanned
from tests.test_synthetic import CASE, document

LETTER_LINE = "Wir haben Ihre Meldung erhalten und werden den Schimmel im Badezimmer prüfen lassen."


def dossier():
    """A five-page file: two digital pages, then three scanned ones."""
    writer = PdfWriter()
    from pypdf import PdfReader
    parts = [render_digital(document(title="Mängelrüge Schimmel", blocks=[{"type": "paragraph", "label": "", "text": "Ich melde hiermit den Schimmel im Badezimmer meiner Wohnung. " * 40}]), CASE),
             render_scanned(document(title="Antwort der Verwaltung", layout="scan", blocks=[{"type": "paragraph", "label": "", "text": LETTER_LINE * 25}]), CASE)]
    digital, scanned = (PdfReader(io.BytesIO(data)).pages[0] for data in parts)
    for page in (digital, digital, scanned, scanned, scanned):
        writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


class Reader:
    """Reads page images and outlines page windows like the model would; can fail on chosen pages."""

    def __init__(self, unreadable=()):
        self.calls, self.unreadable = [], set(unreadable)

    def respond_json(self, *, name, instructions, input, schema, effort="medium"):
        self.calls.append(name)
        if name == "casepath_transcribe":
            pages = schema["properties"]["pages"]["items"]["properties"]["page"]["enum"]
            images = [c for c in input[0]["content"] if c["type"] == "input_image"]
            assert len(images) == len(pages) and images[0]["image_url"].startswith("data:image/png;base64,")
            if self.unreadable & set(pages):
                raise ModelError("http_400", "The model endpoint answered 400.")
            value = {"pages": [{"page": p, "text": f"Antwort der Verwaltung\n{LETTER_LINE}\n[geschwärzt]"} for p in pages]}
        else:
            given = [p["page"] for p in json.loads(input[0]["content"])["pages"]]
            documents = [
                {"first_page": 1, "last_page": 2, "continues": False, "kind": "Mängelrüge", "date": "03.02.2025", "sender": "Mieterin",
                 "recipient": "Verwaltung", "title": "Mängelrüge Schimmel", "summary": "Die Mieterin meldet Schimmel im Badezimmer.",
                 "quote": "Ich melde hiermit den Schimmel im Badezimmer meiner Wohnung."},
                {"first_page": 3, "last_page": 5, "continues": False, "kind": "Antwort der Verwaltung", "date": "07.02.2025",
                 "sender": "Verwaltung", "recipient": "Mieterin", "title": "Antwort der Verwaltung",
                 "summary": "Die Verwaltung bestätigt den Eingang und lässt prüfen.", "quote": LETTER_LINE},
                {"first_page": 4, "last_page": 4, "continues": False, "kind": "overlap", "date": "", "sender": "", "recipient": "",
                 "title": "Overlapping", "summary": "", "quote": "nothing like this exists in the file"}]
            rows = []
            for d in documents:
                pages = [p for p in given if d["first_page"] <= p <= d["last_page"]]
                if pages:
                    rows.append({**d, "first_page": pages[0], "last_page": pages[-1], "continues": pages[0] != d["first_page"]})
            value = {"documents": rows}
        return ModelResult(value=value, usage={}, deployment="d", response_id="r", attempts=1, seconds=0)


class ReadingTests(unittest.TestCase):
    def setUp(self):
        self.data = dossier()
        self.row = extract("dossier.pdf", "application/pdf", self.data)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = CaseStore(directory.name)
        self.addCleanup(self.store.close)
        case = self.store.create_case("x", {}, "u")
        self.file = self.store.add_file(case["id"], "dossier.pdf", self.row["media_type"], self.row["kind"], self.data, self.row, "u")["id"]

    def test_scanned_pages_are_transcribed_and_the_dossier_is_split(self):
        self.assertEqual((self.row["pages"], self.row["pages_without_text"]), (5, [3, 4, 5]))
        model, events = Reader(), []
        extraction = reading.prepare_file(model, self.store, self.store.get_file(self.file, True), on_event=events.append, workers=3)
        self.assertEqual(extraction["pages_without_text"], [])
        self.assertEqual(extraction["pages_transcribed"], self.row["pages_without_text"])
        self.assertIn("[geschwärzt]", extraction["text"])
        self.assertIn("read from the page image", extraction["note"])
        self.assertEqual([s["kind"] for s in extraction["segments"]], ["Mängelrüge", "Antwort der Verwaltung"])
        self.assertTrue(all(s["anchored"] for s in extraction["segments"]))
        self.assertEqual(extraction["segments"][0]["summary"], "Die Mieterin meldet Schimmel im Badezimmer.")
        self.assertIn("reading.segmented", [e["kind"] for e in events])
        calls = list(model.calls)
        reading.prepare_file(model, self.store, self.store.get_file(self.file, True))
        self.assertEqual(model.calls, calls)  # stored: nothing is read twice

    def test_a_document_across_windows_is_joined(self):
        self.store.update_extraction(self.file, reading.merge_pages(self.row, {3: LETTER_LINE, 4: LETTER_LINE, 5: LETTER_LINE}))
        with mock.patch.object(reading, "windows", lambda pages: [pages[:3], pages[3:]]):
            segments = reading.segment(Reader(), self.store.get_file(self.file, True), workers=2)
        self.assertEqual([(s["first_page"], s["last_page"]) for s in segments], [(1, 2), (3, 5)])
        self.assertEqual(segments[1]["summary"].count("bestätigt den Eingang"), 2)

    def test_pages_the_model_cannot_read_stay_listed_and_are_tried_again(self):
        events = []
        extraction = reading.prepare_file(Reader(unreadable={5}), self.store, self.store.get_file(self.file, True), on_event=events.append)
        self.assertEqual((extraction["pages_transcribed"], extraction["pages_without_text"]), ([3, 4], [5]))
        self.assertIn({"agent": "claim_reader", "kind": "reading.unread", "file": self.file, "pages": 1}, events)
        self.assertEqual(extraction["segments"][-1]["last_page"], 4)
        extraction = reading.prepare_file(Reader(), self.store, self.store.get_file(self.file, True))
        self.assertEqual((extraction["pages_transcribed"], extraction["pages_without_text"]), ([3, 4, 5], []))
        self.assertEqual(extraction["segments"][-1]["last_page"], 5)

    def test_a_file_the_model_cannot_read_at_all_fails_with_the_reason(self):
        with self.assertRaises(ModelError):
            reading.prepare_file(Reader(unreadable={3, 4, 5}), self.store, self.store.get_file(self.file, True))

    def test_windows_keep_page_order_within_a_budget(self):
        pages = [(n, "x" * 20000) for n in range(1, 8)]
        groups = reading.windows(pages, budget=45000, page_cap=30000)
        self.assertEqual([[n for n, _ in g] for g in groups], [[1, 2], [3, 4], [5, 6], [7]])


if __name__ == "__main__":
    unittest.main()
