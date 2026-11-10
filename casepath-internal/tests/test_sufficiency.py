import copy
import json
from pathlib import Path
import unittest

from casepath.agents.team import CaseWork, _record_document, _tool_specs
from casepath.process.workflows import CatalogueError, validate_workflow

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "example-defect.json").read_text())
LETTER = "Wir bestätigen den Eingang Ihrer Mängelanzeige vom 2. März 2025 betreffend Schimmel im Bad."
FILES = [{"id": "f1", "name": "letter.pdf", "kind": "pdf", "text": f"Immo AG\n\n{LETTER}"}]
CASE = {"title": "Schimmel im Bad", "intake": {}}


def workflow():
    data = copy.deepcopy(FIXTURE)
    notice = next(d for d in data["documents"] if d["id"] == "notice_letter")
    notice["must_show"] = ["the date of the notice", "the defect it reports"]
    return validate_workflow(data)


def record(work, **args):
    base = {"document": "notice_letter", "status": "present", "files": ["f1"], "citations": [{"file": "f1", "quote": LETTER}],
            "note": "", "shows": []}
    return _record_document(work, "document_finder", {**base, **args})


class SufficiencyTests(unittest.TestCase):
    def test_must_show_is_validated(self):
        for bad in ("a string", [""], ["x", "x"]):
            data = copy.deepcopy(workflow())
            data["documents"][2]["must_show"] = bad
            with self.assertRaises(CatalogueError):
                validate_workflow(data)

    def test_present_needs_a_quote_for_every_item(self):
        work = CaseWork(case=CASE, files=FILES, base_workflow=workflow())
        result = record(work, shows=[{"item": "the date of the notice", "citations": [{"file": "f1", "quote": "vom 2. März 2025"}]}])
        self.assertEqual(result["status"], "unusable")
        self.assertIn("the defect it reports", work.documents["notice_letter"]["note"])

    def test_a_quote_not_in_the_file_does_not_count(self):
        work = CaseWork(case=CASE, files=FILES, base_workflow=workflow())
        result = record(work, shows=[{"item": "the date of the notice", "citations": [{"file": "f1", "quote": "vom 2. März 2025"}]},
                                     {"item": "the defect it reports", "citations": [{"file": "f1", "quote": "Wasserschaden in der Küche"}]}])
        self.assertEqual(result["status"], "unusable")

    def test_every_item_quoted_makes_it_present(self):
        work = CaseWork(case=CASE, files=FILES, base_workflow=workflow())
        result = record(work, shows=[{"item": "the date of the notice", "citations": [{"file": "f1", "quote": "vom 2. März 2025"}]},
                                     {"item": "the defect it reports", "citations": [{"file": "f1", "quote": "betreffend Schimmel im Bad"}]}])
        self.assertEqual(result["status"], "present")
        self.assertEqual([s["item"] for s in work.documents["notice_letter"]["shows"]], ["the date of the notice", "the defect it reports"])

    def test_needs_without_must_show_behave_as_before(self):
        work = CaseWork(case=CASE, files=FILES, base_workflow=FIXTURE)
        args = {"document": "notice_letter", "status": "present", "files": ["f1"], "citations": [{"file": "f1", "quote": LETTER}], "note": ""}
        self.assertEqual(_record_document(work, "document_finder", args)["status"], "present")
        schema = next(t for t in _tool_specs(work, ["record_document"]) if t["name"] == "record_document")
        self.assertNotIn("shows", schema["parameters"]["properties"])  # the tool is unchanged where no need lists items
        with_items = CaseWork(case=CASE, files=FILES, base_workflow=workflow())
        schema = next(t for t in _tool_specs(with_items, ["record_document"]) if t["name"] == "record_document")
        self.assertIn("shows", schema["parameters"]["properties"])


if __name__ == "__main__":
    unittest.main()
