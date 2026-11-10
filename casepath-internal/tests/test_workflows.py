import copy
import itertools
import json
from pathlib import Path
import tempfile
import unittest

from casepath.process import workflows
from casepath.process.workflows import Catalogue, CatalogueError, evaluate, evaluate_condition, route, validate_workflow

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
        # Exact deferral: the documents of the branch the answer decides are listed as depending on it, with its question.
        self.assertEqual([d["document"] for d in result["documents"]], ["customer_message", "photo", "notice_letter"])
        self.assertEqual(result["documents"][0]["status"], "unchecked")
        self.assertEqual(result["documents"][0]["required"], "yes")
        for row in result["documents"][1:]:
            self.assertEqual(row["required"], "depends")
            self.assertEqual([q["fact"] for q in row["questions"]], ["landlord_notified"])
        self.assertEqual([b["state"] for b in result["beyond"]], ["pending", "pending"])
        self.assertEqual(result["deferral"]["mode"], "exact")
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


class ConvergenceAndOptionalTests(unittest.TestCase):
    def test_converging_branches_do_not_block_and_optional_is_not_missing(self):
        data = copy.deepcopy(FIXTURE)
        data["facts"].append({"id": "channel", "type": "enum", "values": ["login", "guest"], "question": "Login?", "source_refs": ["fixture#c"]})
        data["steps"][0]["next"] = [{"to": "via_login", "when": {"fact": "channel", "is": "login"}},
                                    {"to": "via_guest", "when": {"fact": "channel", "is": "guest"}}]
        data["steps"] += [{"id": "via_login", "title": "Login", "source_refs": ["fixture#l"], "next": [{"to": "notice", "when": True}]},
                          {"id": "via_guest", "title": "Guest", "source_refs": ["fixture#g"], "next": [{"to": "notice", "when": True}]}]
        data["documents"][1]["optional"] = True
        data["notes"] = [{"text": "Uploads are checked at every step.", "source_refs": ["fixture#n"]}]
        validate_workflow(data)
        result = evaluate(data, {"landlord_notified": True}, {}, checked=True)
        self.assertEqual(result["outcome"]["id"], "reported")
        self.assertEqual(result["path"][0]["either"], ["channel"])
        photo = next(d for d in result["documents"] if d["document"] == "photo")
        self.assertEqual(photo["required"], "optional")
        self.assertNotIn("photo", [a.get("document") for a in result["next_actions"]])


class GateTests(unittest.TestCase):
    def test_a_failed_gate_names_its_unmet_conditions(self):
        data = copy.deepcopy(FIXTURE)
        data["facts"].append({"id": "details", "type": "boolean", "question": "Are personal details known?", "source_refs": ["fixture#p"]})
        assess = next(s for s in data["steps"] if s["id"] == "assess")
        assess.pop("outcome")
        assess["next"] = [{"to": "done", "when": {"all": [{"fact": "details", "is": True}]}},
                          {"to": "assess", "when": {"any": [{"fact": "details", "is": False}]}}]
        data["steps"].append({"id": "done", "title": "Report", "source_refs": ["fixture#d"], "outcome": "reported"})
        result = evaluate(data, {"landlord_notified": True, "details": False}, {}, checked=True)
        self.assertEqual(result["current"]["step"], "assess")
        self.assertEqual([(a["kind"], a["fact"]) for a in result["next_actions"] if a["kind"] == "resolve"], [("resolve", "details")])

    def test_a_loop_on_missing_details_asks_for_them(self):
        data = copy.deepcopy(FIXTURE)
        data["facts"].append({"id": "party", "type": "text", "question": "Who is the other party?", "source_refs": ["fixture#p"]})
        assess = next(s for s in data["steps"] if s["id"] == "assess")
        assess.pop("outcome")
        assess["next"] = [{"to": "done", "when": {"all": [{"fact": "party", "known": True}]}},
                          {"to": "assess", "when": {"any": [{"fact": "party", "known": False}]}}]
        data["steps"].append({"id": "done", "title": "Report", "source_refs": ["fixture#d"], "outcome": "reported"})
        result = evaluate(data, {"landlord_notified": True}, {}, checked=True)
        self.assertEqual(result["current"]["step"], "assess")
        self.assertIn(("answer", "party"), [(a["kind"], a.get("fact")) for a in result["next_actions"]])
        self.assertNotIn("resolve", [a["kind"] for a in result["next_actions"]])
        self.assertEqual(evaluate(data, {"landlord_notified": True, "party": "Immo AG"}, {}, checked=True)["outcome"]["id"], "reported")


TENANCY = Path(__file__).parent / "fixtures" / "tenancy"


class ExactDeferralTests(unittest.TestCase):
    """Evaluation under every completion of the open facts (synthetic tenancy workflows converted from the public
    CasePath rule templates)."""

    @staticmethod
    def flags(workflow):
        return [f["id"] for f in workflow["facts"] if f["type"] == "boolean"]

    def test_known_facts_give_the_plain_walk(self):
        from casepath.process.workflows import _walk
        cases = [(FIXTURE, {"legal_area": "tenancy_defect", "landlord_notified": v}) for v in (True, False)]
        for path in sorted(TENANCY.glob("*.json")):
            workflow = json.loads(path.read_text())
            names = self.flags(workflow)
            for values in itertools.product((True, False), repeat=len(names)):
                cases.append((workflow, {"dispute_family": workflow["id"], **dict(zip(names, values))}))
        for workflow, facts in cases:
            for checked in (True, False):
                self.assertEqual(evaluate(workflow, facts, {}, checked=checked), _walk(workflow, facts, {}, checked=checked))

    def test_every_assignment_matches_its_completions(self):
        """A document is required now exactly when every completion requires it, depends when some do, absent when none do."""
        from casepath.process.workflows import _walk
        for path in sorted(TENANCY.glob("*.json")):
            workflow = json.loads(path.read_text())
            names = self.flags(workflow)
            for values in itertools.product((True, False, None), repeat=len(names)):
                facts = {"dispute_family": workflow["id"], **{n: v for n, v in zip(names, values) if v is not None}}
                open_ = [n for n, v in zip(names, values) if v is None]
                result = evaluate(workflow, facts, {}, checked=True)
                listed = {d["document"]: d["required"] for d in result["documents"]}
                runs = [_walk(workflow, {**facts, **dict(zip(open_, bits))}, {}, checked=True)
                        for bits in itertools.product((True, False), repeat=len(open_))]
                for document in workflow["documents"]:
                    hits = sum(any(d["document"] == document["id"] for d in run["documents"]) for run in runs)
                    if hits == 0:
                        self.assertNotIn(document["id"], listed)
                    elif hits < len(runs):
                        self.assertEqual(listed[document["id"]], "depends", (path.name, facts, document["id"]))
                    else:
                        self.assertNotEqual(listed[document["id"]], "depends", (path.name, facts, document["id"]))
                deciding = {w["fact"] for w in result["waiting_for"]}
                self.assertLessEqual(deciding, set(open_))

    def test_an_open_health_fact_keeps_the_medical_report_with_its_question(self):
        workflow = json.loads((TENANCY / "defect_mold_heating.json").read_text())
        facts = {"dispute_family": "defect_mold_heating", "mold": True, "heating": False, "specialist_needed": False,
                 "deposit_considered": False}
        result = evaluate(workflow, facts, {}, checked=True)
        rows = {d["document"]: d for d in result["documents"]}
        self.assertEqual(rows["medical_confirmation"]["required"], "depends")
        self.assertEqual([q["fact"] for q in rows["medical_confirmation"]["questions"]], ["health_effects"])
        self.assertEqual(rows["lease_contract"]["required"], "yes")  # needed whatever the answer
        self.assertEqual([w["fact"] for w in result["waiting_for"]], ["health_effects"])
        self.assertIn("lease_contract", [a.get("document") for a in result["next_actions"]])
        self.assertIsNone(result["outcome"])

    def test_too_many_open_facts_fall_back_to_the_first_open_branch(self):
        from casepath.process import workflows as wf
        workflow = json.loads((TENANCY / "defect_mold_heating.json").read_text())
        limit = wf.MAX_OPEN_FACTS
        try:
            wf.MAX_OPEN_FACTS = 1
            result = evaluate(workflow, {"dispute_family": "defect_mold_heating"}, {}, checked=True)
        finally:
            wf.MAX_OPEN_FACTS = limit
        self.assertEqual(result["deferral"]["mode"], "first_open_branch")
        self.assertEqual(result["current"]["step"], "dh_intake")
