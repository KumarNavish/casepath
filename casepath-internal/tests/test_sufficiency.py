import copy
import json
from pathlib import Path
import unittest

from casepath.agents.team import CaseWork, _record_document, _tool_specs
from casepath.process.workflows import CatalogueError, validate_workflow

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "example-defect.json").read_text())
LETTER = "Wir bestätigen den Eingang Ihrer Mängelanzeige vom 2. März 2025 betreffend Schimmel im Bad."
FILES = [{"id": "f1", "name": "letter.pdf", "kind": "pdf", "text": f"Immo AG\n\n{LETTER}"},
         {"id": "f2", "name": "message.eml", "kind": "email", "text": "Der Schimmel im Bad ist seit Januar da."}]
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

    def test_quotes_count_only_from_the_files_named_for_the_document(self):
        work = CaseWork(case=CASE, files=FILES, base_workflow=workflow())
        result = record(work, shows=[{"item": "the date of the notice", "citations": [{"file": "f1", "quote": "vom 2. März 2025"}]},
                                     {"item": "the defect it reports", "citations": [{"file": "f2", "quote": "Der Schimmel im Bad"}]}])
        self.assertEqual(result["status"], "unusable")
        self.assertIn("the defect it reports", work.documents["notice_letter"]["note"])

    def test_a_document_only_mentioned_in_a_message_stays_missing(self):
        work = CaseWork(case=CASE, files=FILES, base_workflow=workflow())
        result = record(work, status="mentioned_only", files=["f2"], citations=[{"file": "f2", "quote": "Der Schimmel im Bad ist seit Januar da."}])
        self.assertEqual(result["status"], "missing")
        self.assertIn("Only mentioned in message.eml", work.documents["notice_letter"]["note"])
        self.assertNotIn("notice_letter", work.findings())

    def test_present_needs_a_quote_from_the_file_named_as_the_document(self):
        work = CaseWork(case=CASE, files=FILES, base_workflow=FIXTURE)
        result = _record_document(work, "document_finder", {"document": "notice_letter", "status": "present", "files": ["f1"],
                                                             "citations": [{"file": "f2", "quote": "Der Schimmel im Bad ist seit Januar da."}], "note": ""})
        self.assertFalse(result["accepted"])
        self.assertNotIn("notice_letter", work.documents)

    def test_the_source_checker_checks_each_item_and_that_the_file_is_the_document(self):
        from casepath.agents.team import run_source_checker
        from tests.scripted import ScriptedModel
        work = CaseWork(case=CASE, files=FILES, base_workflow=workflow())
        record(work, shows=[{"item": "the date of the notice", "citations": [{"file": "f1", "quote": "vom 2. März 2025"}]},
                            {"item": "the defect it reports", "citations": [{"file": "f1", "quote": "betreffend Schimmel im Bad"}]}])
        model = ScriptedModel([], verdicts={"show:notice_letter#1": "uncertain"})
        captured = []
        original = model.respond_json
        model.respond_json = lambda **kw: captured.append(kw) or original(**kw)
        run_source_checker(model, work)
        row = work.documents["notice_letter"]
        self.assertEqual((row["status"], row["verdict"]), ("unusable", "accepted"))  # still a request, never present
        self.assertIn("the defect it reports", row["note"])
        claims = {i["item"]: i["claim"] for i in json.loads(captured[0]["input"][0]["content"])["items"]}
        self.assertIn("letter.pdf is", claims["document:notice_letter"])
        self.assertIn("not a message or another document that only mentions", claims["document:notice_letter"])
        self.assertEqual(claims["show:notice_letter#1"], "“Notice letter” shows: the defect it reports.".replace("Notice letter", work.document_defs["notice_letter"]["title"]))

    def test_needs_without_must_show_behave_as_before(self):
        work = CaseWork(case=CASE, files=FILES, base_workflow=FIXTURE)
        args = {"document": "notice_letter", "status": "present", "files": ["f1"], "citations": [{"file": "f1", "quote": LETTER}], "note": ""}
        self.assertEqual(_record_document(work, "document_finder", args)["status"], "present")
        schema = next(t for t in _tool_specs(work, ["record_document"]) if t["name"] == "record_document")
        self.assertNotIn("shows", schema["parameters"]["properties"])  # the tool is unchanged where no need lists items
        with_items = CaseWork(case=CASE, files=FILES, base_workflow=workflow())
        schema = next(t for t in _tool_specs(with_items, ["record_document"]) if t["name"] == "record_document")
        self.assertIn("shows", schema["parameters"]["properties"])
        # An item is named exactly as the need lists it: a translated or reworded name could never be matched.
        item = schema["parameters"]["properties"]["shows"]["items"]["properties"]["item"]
        self.assertEqual(item["enum"], ["the date of the notice", "the defect it reports"])


if __name__ == "__main__":
    unittest.main()
