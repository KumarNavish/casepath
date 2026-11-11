import json
from pathlib import Path
import tempfile
import unittest

from casepath.agents import core
from casepath.process import knowledge as kb
from casepath.process.workflows import Catalogue
from tests.scripted import ScriptedModel, report

FIXTURES = Path(__file__).parent / "fixtures"
QUOTE = "Ich habe den Vermieter am 2. März schriftlich informiert."
VENT = "Ich lüfte dreimal täglich, trotzdem kommt der Schimmel zurück."


def job(knowledge=(), **case):
    text = f"{QUOTE} {VENT}"
    return {"format": core.JOB,
            "case": {"id": "case_1", "title": "Fall 1", "intake": {}, "workflow_id": "example-defect", "workflow_version": None, **case},
            "files": [{"id": "f1", "name": "message.txt", "kind": "text", "media_type": "text/plain", "sha256": "abc",
                       "extraction": {"text": text, "pages": None, "readable": True, "note": ""}}],
            "workflows": list(Catalogue.load(FIXTURES).workflows), "knowledge": list(knowledge), "edits": [], "options": {"read_scans": True}}


def item(family, status, title):
    origin = {"kind": "case", "by": "test", "case_id": "case_0"}
    return {**kb.new_item(family, "document_need", {"title": title, "why": "Shows it.", "step": None}, origin=origin), "status": status}


def script():
    return ScriptedModel([
        [report("claim_reader", request="Check the mould defect.")],
        [("open_process", {}), report("process_builder")],
        [("record_fact", {"part": None, "fact": "landlord_notified", "status": "established", "value": "yes",
                          "citations": [{"file": "f1", "quote": QUOTE}]}), report("claim_reader")],
        [("record_document", {"document": "notice_letter", "status": "absent", "files": [], "citations": [], "note": ""}),
         report("document_finder")],
        [report("result_checker", learn=[{"action": "new", "target": None, "kind": "document_need", "title": "Lüftungsprotokoll",
                                          "why": "Zeigt das Lüften.", "question": "", "note": "", "step": None, "applies_when": [],
                                          "applies_when_text": "", "reason": "Die Vermieterin wendet falsches Lüften ein.",
                                          "citations": [{"file": "f1", "quote": VENT}]}])],
    ])


class CoreContractTests(unittest.TestCase):
    def test_a_job_in_json_gives_an_outcome_in_json_without_any_store(self):
        active, candidate, other = item("example-defect", "active", "Mietvertrag"), item("example-defect", "candidate", "Rechnung"), item("other", "active", "Police")
        events = []
        with tempfile.TemporaryDirectory() as blobs:
            outcome = core.prepare(json.loads(json.dumps(job([active, candidate, other]))), script(), core.DirectoryBlobs(blobs),
                                   on_event=events.append)
        self.assertEqual(json.loads(json.dumps(outcome)), outcome)  # all of it travels as JSON
        self.assertEqual((outcome["format"], outcome["status"], outcome["workflow"]["id"]), (core.OUTCOME, "completed", "example-defect"))
        applied = {a["item"] for a in outcome["result"]["provenance"]["knowledge"] if a["applied"]}
        self.assertEqual(applied, {active["id"]})  # only active Knowledge of the case's family reaches the agents
        self.assertEqual([o["item"] for o in outcome["knowledge_outcomes"]], [active["id"]])
        proposal, = outcome["knowledge_proposals"]
        self.assertEqual((proposal["item"]["status"], proposal["item"]["content"]["title"]), ("candidate", "Lüftungsprotokoll"))
        self.assertTrue(any(e.get("kind") == "agent.start" for e in events))
        self.assertIn("instruction_like", outcome["extractions"]["f1"])  # the reading comes back for the case service to save

        evaluated = core.evaluate(Catalogue.load(FIXTURES).get("example-defect"), [active], [], outcome["result"], "case_1")
        self.assertEqual(evaluated["evaluation"]["outcome"]["id"], outcome["result"]["evaluation"]["outcome"]["id"])

    def test_a_run_stops_when_its_token_budget_is_spent(self):
        with tempfile.TemporaryDirectory() as blobs:
            capped = {**job([]), "options": {**job([]).get("options", {}), "token_budget": 40}}
            stopped = core.prepare(json.loads(json.dumps(capped)), script(), core.DirectoryBlobs(blobs))
            unlimited = core.prepare(json.loads(json.dumps({**capped, "options": {**capped["options"], "token_budget": 0}})), script(),
                                     core.DirectoryBlobs(blobs))
        self.assertEqual(stopped["status"], "failed")
        self.assertTrue(stopped["error"].startswith("token_budget: The run used its budget of 40 tokens"))
        self.assertEqual(unlimited["status"], "completed")

    def test_failures_come_back_as_outcomes_with_a_reason(self):
        with tempfile.TemporaryDirectory() as blobs:
            failed = core.prepare(job(), None, core.DirectoryBlobs(blobs))
        self.assertEqual(failed["status"], "failed")
        self.assertTrue(failed["error"].startswith("model_not_configured"))
        with self.assertRaises(core.JobError):
            core.prepare({"format": "something else"}, None, None)


if __name__ == "__main__":
    unittest.main()
