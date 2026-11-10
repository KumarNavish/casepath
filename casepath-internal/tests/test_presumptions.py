import copy
import json
from pathlib import Path
import unittest

from casepath.process import workflows
from casepath.agents.team import CaseWork
from casepath.process.workflows import CatalogueError, validate_workflow

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "example-defect.json").read_text())
QUOTE = "Ich habe den Vermieter am 2. März schriftlich informiert."
FILES = [{"id": "f1", "name": "message.eml", "kind": "email", "text": f"Subject: Schimmel im Bad\n\n{QUOTE}"}]
CASE = {"title": "Schimmel im Bad", "intake": {}}


def with_presumption(applies="unstated", value=False):
    data = copy.deepcopy(FIXTURE)
    data["presumptions"] = [{"fact": "landlord_notified", "value": value, "applies": applies, "source_ref": "fixture#silence",
                             "text": "A notice the customer does not mention is presumed not given."}]
    return validate_workflow(data)


class PresumptionFormatTests(unittest.TestCase):
    def test_a_workflow_without_presumptions_is_unchanged(self):
        self.assertNotIn("presumptions", FIXTURE)
        work = CaseWork(case=CASE, files=FILES, base_workflow=FIXTURE)
        self.assertEqual(work.presumptions(), {})
        self.assertEqual(work.accepted_facts(), {})

    def test_presumptions_are_validated(self):
        for broken in ({"fact": "nope"}, {"value": "maybe"}, {"applies": "always"}, {"source_ref": "elsewhere#1"}, {"text": ""}):
            data = copy.deepcopy(with_presumption())
            data["presumptions"][0].update(broken)
            with self.assertRaises(CatalogueError):
                validate_workflow(data)
        data = copy.deepcopy(with_presumption())
        data["presumptions"].append(dict(data["presumptions"][0]))
        with self.assertRaises(CatalogueError):
            validate_workflow(data)


class PresumptionUseTests(unittest.TestCase):
    def test_an_unstated_fact_is_presumed_with_its_source(self):
        work = CaseWork(case=CASE, files=FILES, base_workflow=with_presumption())
        self.assertEqual(work.accepted_facts(), {"landlord_notified": False})
        self.assertEqual(work.evaluate()["outcome"]["id"], "advice")
        self.assertEqual(work.presumptions()["landlord_notified"]["source_ref"], "fixture#silence")

    def test_unknown_without_a_quote_is_presumed_but_a_cited_open_fact_is_not(self):
        work = CaseWork(case=CASE, files=FILES, base_workflow=with_presumption())
        work.facts["landlord_notified"] = {"fact": "landlord_notified", "status": "unknown", "value": None, "citations": [], "verdict": "not_checked"}
        self.assertEqual(work.accepted_facts(), {"landlord_notified": False})
        work.facts["landlord_notified"]["citations"] = [{"file": "f1", "quote": QUOTE}]
        self.assertEqual(work.accepted_facts(), {})
        self.assertEqual([w["fact"] for w in work.evaluate()["waiting_for"]], ["landlord_notified"])

    def test_a_stated_value_overrides_the_presumption(self):
        work = CaseWork(case=CASE, files=FILES, base_workflow=with_presumption(value=False))
        work.facts["landlord_notified"] = {"fact": "landlord_notified", "status": "established", "value": True,
                                           "citations": [{"file": "f1", "quote": QUOTE}], "verdict": "accepted"}
        self.assertEqual(work.accepted_facts(), {"landlord_notified": True})
        self.assertEqual(work.presumptions(), {})

    def test_a_rejected_or_conflicting_fact_is_never_presumed(self):
        for row in ({"status": "established", "value": True, "verdict": "rejected"}, {"status": "conflicting", "value": True, "verdict": "not_checked"}):
            work = CaseWork(case=CASE, files=FILES, base_workflow=with_presumption())
            work.facts["landlord_notified"] = {"fact": "landlord_notified", "citations": [{"file": "f1", "quote": QUOTE}], **row}
            self.assertEqual(work.accepted_facts(), {})

    def test_a_routing_presumption_fills_the_defining_event(self):
        work = CaseWork(case=CASE, files=FILES, base_workflow=with_presumption(applies="routed", value=True))
        self.assertEqual(work.accepted_facts(), {"landlord_notified": True})
        self.assertEqual(workflows.presumed(work.graph, {})["landlord_notified"]["applies"], "routed")

    def test_a_quote_that_leaves_the_defining_event_open_does_not_block_its_presumption(self):
        work = CaseWork(case=CASE, files=FILES, base_workflow=with_presumption(applies="routed", value=True))
        cite = [{"file": "f1", "quote": QUOTE}]
        work.facts["landlord_notified"] = {"fact": "landlord_notified", "status": "unknown", "value": None, "citations": cite,
                                           "verdict": "not_checked"}
        self.assertEqual(work.accepted_facts(), {"landlord_notified": True})
        # The files state that it did not occur: the stated value stands, not the presumption.
        work.facts["landlord_notified"] = {"fact": "landlord_notified", "status": "established", "value": False, "citations": cite,
                                           "verdict": "accepted"}
        self.assertEqual(work.accepted_facts(), {"landlord_notified": False})
        # Two readings that disagree go to a person.
        work.facts["landlord_notified"] = {"fact": "landlord_notified", "status": "conflicting", "value": False, "citations": cite,
                                           "verdict": "not_checked"}
        self.assertEqual(work.accepted_facts(), {})

    def test_an_unstated_presumption_still_yields_to_a_quote_that_leaves_the_fact_open(self):
        work = CaseWork(case=CASE, files=FILES, base_workflow=with_presumption(applies="unstated", value=True))
        work.facts["landlord_notified"] = {"fact": "landlord_notified", "status": "unknown", "value": None,
                                           "citations": [{"file": "f1", "quote": QUOTE}], "verdict": "not_checked"}
        self.assertEqual(work.accepted_facts(), {})

    def test_a_fact_counts_as_raised_only_when_both_readings_quote_a_passage_that_raises_it(self):
        from casepath.agents.team import confirm_facts
        from tests.scripted import ScriptedModel
        cite = [{"file": "f1", "quote": QUOTE}]
        open_quoted = {"fact": "landlord_notified", "status": "unknown", "value": None, "citations": cite}
        open_silent = {"fact": "landlord_notified", "status": "unknown", "value": None, "citations": []}
        for second, presumed in ((open_silent, True), (open_quoted, False)):
            work = CaseWork(case=CASE, files=FILES, base_workflow=with_presumption())
            work.facts["landlord_notified"] = {**open_quoted, "citations": work.located(cite)[0], "verdict": "not_checked", "by": "claim_reader"}
            confirm_facts(ScriptedModel([], second_reading=[second]), work)
            self.assertEqual("landlord_notified" in work.presumptions(), presumed, second)
        # A value found by one reading still holds the fact open: the presumption does not replace it.
        work = CaseWork(case=CASE, files=FILES, base_workflow=with_presumption())
        work.facts["landlord_notified"] = {"fact": "landlord_notified", "status": "established", "value": True,
                                           "citations": work.located(cite)[0], "verdict": None, "by": "claim_reader"}
        confirm_facts(ScriptedModel([], second_reading=[open_silent]), work)
        self.assertEqual(work.accepted_facts(), {})

    def test_a_value_from_one_reading_blocks_every_presumption_and_stays_in_the_result(self):
        from casepath.agents.team import confirm_facts, finalize, read_facts
        from tests.scripted import ScriptedModel
        deny = [{"fact": "landlord_notified", "status": "established", "value": "no", "citations": [{"file": "f1", "quote": QUOTE}]}]
        silent = [{"fact": "landlord_notified", "status": "unknown", "value": None, "citations": []}]
        for applies, value in (("routed", True), ("unstated", False), ("unstated", True)):
            work = CaseWork(case=CASE, files=FILES, base_workflow=with_presumption(applies=applies, value=value))
            model = ScriptedModel([], first_reading=deny, second_reading=silent)
            read_facts(model, work)
            confirm_facts(model, work)
            self.assertEqual(work.presumptions(), {}, applies)
            self.assertEqual(work.accepted_facts(), {}, applies)  # open, for a person
            work.result = None
            row = next(f for f in finalize(work)["facts"] if f["fact"] == "landlord_notified")
            self.assertEqual((row["status"], row["readings"]), ("unknown", [False, None]))
            self.assertIn("a person decides", row["verdict_reason"])
        # The routing presumption yields in the same way.
        work = CaseWork(case=CASE, files=FILES, base_workflow=FIXTURE)
        work.routing_presumed = {"legal_area": "tenancy_defect"}
        work.facts["legal_area"] = {"fact": "legal_area", "status": "unknown", "value": None, "citations": [], "readings": ["loan", None]}
        self.assertNotIn("legal_area", work.presumptions())


class ReplyTests(unittest.TestCase):
    def test_a_clause_resting_only_on_a_presumption_is_not_supported(self):
        from casepath.agents.team import finalize
        work = CaseWork(case=CASE, files=FILES, base_workflow=with_presumption())
        clause = {"text": "Sie haben den Vermieter nicht informiert.", "kind": "statement", "basis": ["fact:landlord_notified"]}
        work.result = {"summary": "s", "answer": "a", "open_points": [], "case_summary": [], "learn": [],
                       "reply": {"needed": True, "subject": "x", "clauses": [clause]}}
        out = finalize(work)
        self.assertFalse(out["reply"]["clauses"][0]["supported"])
        self.assertIn("presumed", [f["status"] for f in out["facts"]])
        work.facts["landlord_notified"] = {"fact": "landlord_notified", "status": "established", "value": False,
                                           "citations": [{"file": "f1", "quote": QUOTE}], "verdict": "accepted"}
        self.assertTrue(finalize(work)["reply"]["clauses"][0]["supported"])


class CaseViewTests(unittest.TestCase):
    def test_the_case_view_keeps_presumed_facts_like_the_run(self):
        from casepath.agents import core
        workflow = with_presumption()
        work = CaseWork(case=CASE, files=FILES, base_workflow=workflow)
        work.facts["landlord_notified"] = {"fact": "landlord_notified", "status": "unknown", "value": None, "citations": [], "verdict": "not_checked"}
        run_view = work.evaluate()
        facts = list(work.facts.values()) + [{"fact": k, "status": "presumed", "value": p["value"], "citations": [], "verdict": "presumed"}
                                             for k, p in work.presumptions().items()]
        state = core.evaluate(workflow, [], [], {"facts": facts, "documents": []}, "c1")
        self.assertEqual((state["evaluation"]["outcome"] or {}).get("id"), (run_view["outcome"] or {}).get("id"))
        self.assertEqual(state["evaluation"]["outcome"]["id"], "advice")
        self.assertEqual(state["facts"], {"landlord_notified": False})

    def test_a_stated_accepted_value_overrides_a_presumed_row_in_the_case_view(self):
        from casepath.agents import core
        facts = [{"fact": "landlord_notified", "status": "presumed", "value": False, "citations": [], "verdict": "presumed"},
                 {"fact": "landlord_notified", "status": "established", "value": True, "citations": [], "verdict": "accepted"}]
        state = core.evaluate(with_presumption(), [], [], {"facts": facts, "documents": []}, "c1")
        self.assertEqual(state["facts"], {"landlord_notified": True})


if __name__ == "__main__":
    unittest.main()
