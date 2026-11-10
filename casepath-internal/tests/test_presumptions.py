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


if __name__ == "__main__":
    unittest.main()
