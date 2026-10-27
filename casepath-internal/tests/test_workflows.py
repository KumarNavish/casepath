import copy
import json
from pathlib import Path
import tempfile
import unittest

from casepath_internal import workflows
from casepath_internal.workflows import Catalogue, CatalogueError, evaluate, evaluate_condition, route, validate_workflow

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "example-defect.json").read_text())


class ConditionTests(unittest.TestCase):
    def test_three_valued_logic(self):
        facts = {"a": True, "b": None}
        self.assertTrue(evaluate_condition({"fact": "a", "is": True}, facts))
        self.assertIsNone(evaluate_condition({"fact": "b", "is": True}, facts))
        self.assertFalse(evaluate_condition({"all": [{"fact": "a", "is": False}, {"fact": "b", "is": True}]}, facts))
        self.assertIsNone(evaluate_condition({"all": [{"fact": "a", "is": True}, {"fact": "b", "is": True}]}, facts))
        self.assertTrue(evaluate_condition({"any": [{"fact": "b", "is": True}, {"fact": "a", "is": True}]}, facts))
        self.assertIsNone(evaluate_condition({"not": {"fact": "b", "is": True}}, facts))
        self.assertFalse(evaluate_condition({"fact": "b", "known": True}, facts))


class ValidationTests(unittest.TestCase):
    def test_fixture_is_valid(self):
        validate_workflow(copy.deepcopy(FIXTURE))

    def broken(self, change):
        data = copy.deepcopy(FIXTURE)
        change(data)
        with self.assertRaises(CatalogueError):
            validate_workflow(data)

    def test_every_rule_needs_a_listed_source(self):
        self.broken(lambda d: d["steps"][0].pop("source_refs"))
        self.broken(lambda d: d["documents"][0].__setitem__("source_refs", ["elsewhere#1"]))

    def test_conditions_must_name_known_facts_and_values(self):
        self.broken(lambda d: d["steps"][1]["next"][0].__setitem__("when", {"fact": "nope", "is": True}))
        self.broken(lambda d: d.__setitem__("applies_when", {"fact": "legal_area", "is": "rent"}))

    def test_unreachable_steps_are_rejected(self):
        self.broken(lambda d: d["steps"][0].__setitem__("next", []))


class EvaluationTests(unittest.TestCase):
    def test_unknown_fact_stops_at_its_branch(self):
        result = evaluate(FIXTURE, {"legal_area": "tenancy_defect"})
        self.assertEqual(result["current"]["step"], "notice")
        self.assertEqual([w["fact"] for w in result["waiting_for"]], ["landlord_notified"])
        self.assertEqual([d["document"] for d in result["documents"]], ["customer_message"])
        self.assertEqual(result["documents"][0]["status"], "unchecked")
        self.assertEqual(result["next_actions"][0]["kind"], "answer")
        self.assertEqual(result["gaps"][0]["kind"], "open_question")

    def test_branch_and_conditional_documents(self):
        findings = {"photo": {"status": "present", "files": ["f2"], "citations": []}}
        told = evaluate(FIXTURE, {"landlord_notified": True}, findings, checked=True)
        self.assertEqual(told["outcome"]["id"], "reported")
        statuses = {d["document"]: d["status"] for d in told["documents"]}
        self.assertEqual(statuses, {"customer_message": "missing", "photo": "present", "notice_letter": "missing"})
        self.assertEqual([a["document"] for a in told["next_actions"]], ["customer_message", "notice_letter"])
        not_told = evaluate(FIXTURE, {"landlord_notified": False}, findings, checked=True)
        self.assertEqual(not_told["outcome"]["id"], "advice")
        self.assertNotIn("notice_letter", {d["document"] for d in not_told["documents"]})


class RoutingTests(unittest.TestCase):
    def catalogue(self, *extra):
        with tempfile.TemporaryDirectory() as directory:
            for index, row in enumerate((FIXTURE,) + extra):
                Path(directory, f"{index}.json").write_text(json.dumps(row))
            return Catalogue.load(directory)

    def test_route_selects_asks_or_says_unmapped(self):
        catalogue = self.catalogue()
        self.assertEqual(route(catalogue, {"legal_area": "tenancy_defect"})["status"], "selected")
        asked = route(catalogue, {})
        self.assertEqual((asked["status"], asked["needs"]), ("needs_facts", ["legal_area"]))
        self.assertEqual(route(catalogue, {"legal_area": "other"})["status"], "unmapped")
        self.assertEqual(route(Catalogue.load(None), {"legal_area": "loan"})["status"], "unmapped")

    def test_source_supported_fallback(self):
        fallback = copy.deepcopy(FIXTURE)
        fallback.update(id="example-fallback", fallback=True, applies_when=None)
        result = route(self.catalogue(fallback), {"legal_area": "other"})
        self.assertEqual((result["status"], result["workflow"]["id"]), ("fallback", "example-fallback"))

    def test_routing_facts_merge_values(self):
        self.assertEqual([f["id"] for f in self.catalogue().routing_facts()], ["legal_area"])

    def test_duplicate_versions_are_rejected(self):
        with self.assertRaises(CatalogueError):
            self.catalogue(copy.deepcopy(FIXTURE))


if __name__ == "__main__":
    unittest.main()
