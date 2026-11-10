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
        [("record_fact", {"fact": "landlord_notified", "status": "established", "value": "yes",
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

    def test_the_only_workflow_that_can_apply_is_prepared_with_its_routing_fact_presumed(self):
        with tempfile.TemporaryDirectory() as blobs:
            outcome = core.prepare(job([], workflow_id=None), script(), core.DirectoryBlobs(blobs))
        self.assertEqual((outcome["status"], outcome["routing"]["status"], outcome["workflow"]["id"]), ("completed", "selected", "example-defect"))
        presumed = next(f for f in outcome["result"]["facts"] if f["fact"] == "legal_area")
        self.assertEqual((presumed["status"], presumed["value"], presumed["by"]), ("presumed", "tenancy_defect", "routing"))
        self.assertEqual(presumed["citations"], [])  # presumed, never shown as established from the files

    def test_routing_accepts_more_than_one_other_topic_and_keeps_the_first_quoted(self):
        model = script()
        model.other_topic = [{"topic": "Rent arrears", "file": "f1", "quote": VENT}, {"topic": "Deposit", "file": "f1", "quote": QUOTE}]
        with tempfile.TemporaryDirectory() as blobs:
            outcome = core.prepare(job([], workflow_id=None), model, core.DirectoryBlobs(blobs))
        self.assertEqual(outcome["status"], "completed")  # two topics no longer fail the run
        self.assertEqual(outcome["routing"]["other_topic"]["topic"], "Rent arrears")

    def test_a_routing_quotation_not_found_is_asked_for_once_more(self):
        model = script()
        model.routing = [{"fact": "legal_area", "value": "tenancy_defect", "citations": [{"file": "f1", "quote": "Ich habe ... informiert."}]}]
        model.retries["casepath_route"] = {"facts": [{"fact": "legal_area", "value": "tenancy_defect", "citations": [{"file": "f1", "quote": QUOTE}]}],
                                           "other_topic": []}
        catalogue = Catalogue.load(FIXTURES)
        other = {**catalogue.get("example-defect"), "id": "example-loan", "applies_when": {"fact": "legal_area", "is": "loan"}}
        with tempfile.TemporaryDirectory() as blobs:
            outcome = core.prepare({**job([], workflow_id=None), "workflows": [catalogue.get("example-defect"), other]}, model,
                                   core.DirectoryBlobs(blobs))
        self.assertEqual((outcome["routing"]["status"], outcome["workflow"]["id"]), ("selected", "example-defect"))
        cited = next(f for f in outcome["routing"]["facts"] if f["fact"] == "legal_area")
        self.assertEqual(cited["citations"][0]["quote"], QUOTE)

    def test_the_one_workflow_left_is_not_taken_when_the_files_name_another_matter_or_a_routing_answer_cannot_be_quoted(self):
        other = script()
        other.other_topic = [{"topic": "A loan", "file": "f1", "quote": VENT}]
        unquoted = script()
        unquoted.routing = [{"fact": "legal_area", "value": "loan", "citations": [{"file": "f1", "quote": "Never written in the file"}]}]
        unquoted.retries["casepath_route"] = {"facts": unquoted.routing, "other_topic": []}
        for model in (other, unquoted):
            with tempfile.TemporaryDirectory() as blobs:
                outcome = core.prepare(job([], workflow_id=None), model, core.DirectoryBlobs(blobs))
            self.assertEqual((outcome["routing"]["status"], outcome["workflow"]), ("needs_facts", None))
            self.assertFalse(any(f.get("presumed") for f in outcome["routing"]["facts"]))

    def test_a_recheck_keeps_the_routing_presumption(self):
        workflow = json.loads(json.dumps(Catalogue.load(FIXTURES).get("example-defect")))
        next(d for d in workflow["documents"] if d["id"] == "customer_message")["required_when"] = {"fact": "legal_area", "is": "tenancy_defect"}
        prepared_job = {**job([], workflow_id=None), "workflows": [workflow]}
        with tempfile.TemporaryDirectory() as blobs:
            outcome = core.prepare(json.loads(json.dumps(prepared_job)), script(), core.DirectoryBlobs(blobs))
        rows = lambda ev: {d["document"]: (d["required"], d["status"]) for d in ev["documents"]}
        before = rows(outcome["result"]["evaluation"])
        self.assertEqual(before["customer_message"][0], "yes")  # needed because the routing fact is presumed
        prior = {"id": "run_1", "workflow_id": "example-defect", "workflow_version": workflow["version"], "result": outcome["result"]}
        again = core.recheck({**prepared_job, "case": {**prepared_job["case"], "workflow_id": "example-defect"}}, prior, [], script())
        self.assertEqual(rows(again["result"]["evaluation"]), before)

    def test_a_recheck_judges_a_present_document_twice_and_names_its_own_limits(self):
        with tempfile.TemporaryDirectory() as blobs:
            outcome = core.prepare(json.loads(json.dumps(job([]))), script(), core.DirectoryBlobs(blobs))
        prior = {"id": "run_1", "workflow_id": "example-defect", "workflow_version": None, "result": outcome["result"]}
        finder = ScriptedModel([[("record_document", {"document": "notice_letter", "status": "present", "files": ["f1"],
                                                      "citations": [{"file": "f1", "quote": QUOTE}], "note": ""})]] + [[("list_files", {})]] * 12)
        finder.confirm_documents = [{"document": "notice_letter", "status": "unusable", "file": "f1", "shows": []}]
        again = core.recheck(job([]), prior, ["notice_letter"], finder)
        row = next(d for d in again["result"]["documents"] if d["document"] == "notice_letter")
        self.assertEqual(row["status"], "unusable")  # the second judgment did not confirm it
        self.assertIn("turn_limit", [w["kind"] for w in again["result"]["warnings"]])

    def test_a_failed_routing_retry_keeps_the_first_answer(self):
        from casepath.agents.azure_model import ModelError
        model = script()
        model.routing = [{"fact": "legal_area", "value": "tenancy_defect", "citations": [{"file": "f1", "quote": "not in the file at all"}]}]
        original = model.respond_json

        def failing_retry(**kw):
            if kw["name"] == "casepath_route" and len(kw["input"]) > 1:
                raise ModelError("timeout", "no answer")
            return original(**kw)
        model.respond_json = failing_retry
        with tempfile.TemporaryDirectory() as blobs:
            outcome = core.prepare(job([], workflow_id=None), model, core.DirectoryBlobs(blobs))
        self.assertEqual((outcome["status"], outcome["error"]), ("completed", None))  # the run goes on with the first answer
        self.assertEqual(outcome["routing"]["status"], "needs_facts")  # whose unquoted value does not count

    def reroute_job(self):
        defect = Catalogue.load(FIXTURES).get("example-defect")
        loan = {**json.loads(json.dumps(defect)), "id": "example-loan", "title": "Loan", "applies_when": {"fact": "legal_area", "is": "loan"}}
        return {**job([], workflow_id=None), "workflows": [defect, loan], "options": {"read_scans": True, "scope": "checklist"}}

    def test_a_routing_fact_the_readings_contradict_routes_once_more(self):
        model = ScriptedModel([], routing=[{"fact": "legal_area", "value": "tenancy_defect", "citations": [{"file": "f1", "quote": QUOTE}]}],
                              first_reading=[{"fact": "legal_area", "status": "established", "value": "loan", "citations": [{"file": "f1", "quote": VENT}]}])
        with tempfile.TemporaryDirectory() as blobs:
            outcome = core.prepare(self.reroute_job(), model, core.DirectoryBlobs(blobs))
        self.assertEqual((outcome["status"], outcome["workflow"]["id"]), ("completed", "example-loan"))
        self.assertEqual(outcome["routing"]["rerouted"]["routed_to"]["id"], "example-defect")

    def test_when_nothing_fits_the_admitted_value_the_case_is_handed_over_with_the_conflict(self):
        model = ScriptedModel([], routing=[{"fact": "legal_area", "value": "tenancy_defect", "citations": [{"file": "f1", "quote": QUOTE}]}],
                              first_reading=[{"fact": "legal_area", "status": "established", "value": "other", "citations": [{"file": "f1", "quote": VENT}]}])
        with tempfile.TemporaryDirectory() as blobs:
            outcome = core.prepare(self.reroute_job(), model, core.DirectoryBlobs(blobs))
        self.assertEqual((outcome["status"], outcome["workflow"], outcome["routing"]["status"]), ("completed", None, "needs_facts"))
        self.assertEqual(outcome["routing"]["conflict"]["admitted"][0]["value"], "other")

    def test_a_fallback_workflow_is_prepared(self):
        fallback = {**Catalogue.load(FIXTURES).get("example-defect"), "id": "general", "fallback": True, "applies_when": None}
        with tempfile.TemporaryDirectory() as blobs:
            outcome = core.prepare({**job([], workflow_id=None), "workflows": [fallback]}, script(), core.DirectoryBlobs(blobs))
        self.assertEqual((outcome["status"], outcome["routing"]["status"], outcome["workflow"]["id"]), ("completed", "fallback", "general"))

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
