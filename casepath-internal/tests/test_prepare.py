import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from casepath_internal import reading
from casepath_internal.prepare import load_prepared, prepare_case
from casepath_internal.store import CaseStore
from casepath_internal.synthetic import render_digital, render_scanned
from tests.test_synthetic import CASE, document


class Reader:
    """Reads page images like the model would."""
    def __init__(self):
        self.pages = []

    def respond_json(self, *, name, instructions, input, schema, effort="medium"):
        from casepath_internal.azure_model import ModelResult
        pages = schema["properties"]["pages"]["items"]["properties"]["page"]["enum"]
        self.pages += pages
        return ModelResult(value={"pages": [{"page": p, "text": f"Seite {p}: Antwort der Verwaltung"} for p in pages]},
                           usage={}, deployment="d", response_id="r", attempts=1, seconds=0)


class PreparedCaseTests(unittest.TestCase):
    def test_a_prepared_case_is_read_without_any_pdf_library_and_deleted_completely(self):
        scanned = render_scanned(document(layout="scan"), CASE)
        digital = render_digital(document(), CASE)
        with tempfile.TemporaryDirectory() as root:
            manifest = prepare_case("Dossier 1", [("Scan.pdf", scanned), ("Brief.pdf", digital)], Path(root) / "prepared", intake={"source": "prepared"})
            scan_row = manifest["files"][0]
            self.assertTrue(scan_row["page_images"] and scan_row["extraction"]["pages_without_text"])
            self.assertTrue((Path(root) / "prepared" / next(iter(scan_row["page_images"].values()))).exists())
            store = CaseStore(Path(root) / "data")
            self.addCleanup(store.close)
            case = load_prepared(store, lambda rel: (Path(root) / "prepared" / rel).read_bytes(), "anna", intake={"import_path": "/x"})
            self.assertEqual((case["title"], case["intake"]["import_path"]), ("Dossier 1", "/x"))
            row = store.list_files(case["id"], with_text=True)[0]
            with mock.patch.object(reading, "Renderer", side_effect=AssertionError("no PDF renderer may be used")):
                reader = Reader()
                extraction = reading.prepare_file(reader, store, row)
            self.assertEqual(reader.pages, scan_row["extraction"]["pages_without_text"])
            self.assertEqual(extraction["pages_without_text"], [])
            self.assertIn("Antwort der Verwaltung", extraction["text"])
            images = list(row["extraction"]["page_images"].values())
            self.assertTrue(all((Path(root) / "data" / "files" / d[:2] / d).exists() for d in images))
            store.delete_case(case["id"], "anna")
            self.assertFalse(any((Path(root) / "data" / "files" / d[:2] / d).exists() for d in images))  # page images go with the case
