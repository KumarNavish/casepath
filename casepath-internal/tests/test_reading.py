import io
import tempfile
import unittest

from pypdf import PdfWriter

from casepath_internal import reading
from casepath_internal.azure_model import ModelResult
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
    def __init__(self):
        self.calls = []

    def respond_json(self, *, name, instructions, input, schema, effort="medium"):
        self.calls.append(name)
        if name == "casepath_transcribe":
            pages = schema["properties"]["pages"]["items"]["properties"]["page"]["enum"]
            images = [c for c in input[0]["content"] if c["type"] == "input_image"]
            assert len(images) == len(pages) and images[0]["image_url"].startswith("data:image/png;base64,")
            value = {"pages": [{"page": p, "text": f"Antwort der Verwaltung\n{LETTER_LINE}\n[geschwärzt]"} for p in pages]}
        else:
            value = {"documents": [
                {"first_page": 1, "last_page": 2, "kind": "Mängelrüge", "date": "03.02.2025", "sender": "Mieterin", "recipient": "Verwaltung",
                 "title": "Mängelrüge Schimmel", "quote": "Ich melde hiermit den Schimmel im Badezimmer meiner Wohnung."},
                {"first_page": 3, "last_page": 5, "kind": "Antwort der Verwaltung", "date": "07.02.2025", "sender": "Verwaltung", "recipient": "Mieterin",
                 "title": "Antwort der Verwaltung", "quote": LETTER_LINE},
                {"first_page": 4, "last_page": 4, "kind": "overlap", "date": "", "sender": "", "recipient": "", "title": "Overlapping", "quote": "nothing like this exists in the file"}]}
        return ModelResult(value=value, usage={}, deployment="d", response_id="r", attempts=1, seconds=0)


class ReadingTests(unittest.TestCase):
    def test_scanned_pages_are_transcribed_and_the_dossier_is_split(self):
        data = dossier()
        row = extract("dossier.pdf", "application/pdf", data)
        self.assertEqual((row["pages"], row["pages_without_text"]), (5, [3, 4, 5]))
        self.assertTrue(row["pages_without_text"])
        with tempfile.TemporaryDirectory() as directory:
            store = CaseStore(directory)
            case = store.create_case("x", {}, "u")
            saved = store.add_file(case["id"], "dossier.pdf", row["media_type"], row["kind"], data, row, "u")
            model, events = Reader(), []
            extraction = reading.prepare_file(model, store, store.get_file(saved["id"], True), on_event=events.append)
            self.assertEqual(extraction["pages_without_text"], [])
            self.assertEqual(extraction["pages_transcribed"], row["pages_without_text"])
            self.assertIn("[geschwärzt]", extraction["text"])
            self.assertIn("read from the page image", extraction["note"])
            self.assertEqual([s["kind"] for s in extraction["segments"]], ["Mängelrüge", "Antwort der Verwaltung"])
            self.assertTrue(all(s["anchored"] for s in extraction["segments"]))
            self.assertIn("reading.segmented", [e["kind"] for e in events])
            calls = list(model.calls)
            reading.prepare_file(model, store, store.get_file(saved["id"], True))
            self.assertEqual(model.calls, calls)  # stored: nothing is read twice


if __name__ == "__main__":
    unittest.main()
