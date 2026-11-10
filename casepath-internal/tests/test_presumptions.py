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

    def test_a_defining_event_the_files_raise_and_leave_open_is_not_presumed(self):
        work = CaseWork(case=CASE, files=FILES, base_workflow=with_presumption(applies="routed", value=True))
        cite = [{"file": "f1", "quote": QUOTE}]
        # every reading quoted a passage for it and none found a value ("I do not know whether the notice was sent")
        work.facts["landlord_notified"] = {"fact": "landlord_notified", "status": "unknown", "value": None, "citations": cite,
                                           "verdict": "not_checked"}
        self.assertEqual(work.accepted_facts(), {})  # held for a person, as the workflow's own clause says
        work.facts["landlord_notified"]["citations"] = []  # not raised: the event is presumed
        self.assertEqual(work.accepted_facts(), {"landlord_notified": True})
        # the routing presumption follows the same rule
        plain = CaseWork(case=CASE, files=FILES, base_workflow=FIXTURE)
        plain.routing_presumed = {"legal_area": "tenancy_defect"}
        plain.facts["legal_area"] = {"fact": "legal_area", "status": "unknown", "value": None, "citations": cite}
        self.assertNotIn("legal_area", plain.presumptions())
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

    def test_the_default_open_rule_holds_a_doubt_one_reading_did_not_see(self):
        from casepath.agents import team
        from casepath.process import workflows
        from tests.scripted import ModelResult, ScriptedModel
        answers = {"casepath_read_facts": "open", "casepath_confirm_facts": "open", "casepath_confirm_facts_2": "not_stated"}
        def run(applies):
            work = CaseWork(case=CASE, files=FILES, base_workflow=with_presumption(applies=applies))
            work.readings = 3
            model = ScriptedModel([])
            model.respond_json = lambda **kw: ModelResult(
                value={"conditions": [{"id": "landlord_notified", "verdict": answers[kw["name"]], "value": None,
                                       "quote": QUOTE if answers[kw["name"]] == "open" else ""}]},
                usage={"input_tokens": 5}, deployment="d", response_id="x", attempts=1, seconds=0)
            team.read_facts(model, work)
            team.confirm_facts(model, work)
            self.assertEqual(work.facts["landlord_notified"]["open_readings"], [True, True, False])
            return "landlord_notified" in work.presumptions()
        self.assertEqual(workflows.OPEN_RULE, "any")
        for applies in ("unstated", "routed"):
            self.assertFalse(run(applies), applies)  # held: the doubt two readings quoted stands
            previous, workflows.OPEN_RULE = workflows.OPEN_RULE, "all"
            try:
                self.assertTrue(run(applies), applies)  # the other rule would presume it
            finally:
                workflows.OPEN_RULE = previous

    def test_an_open_answer_whose_words_are_not_found_is_no_answer(self):
        from casepath.agents import team
        from tests.scripted import ModelResult, ScriptedModel
        calls = []
        def answer(**kw):
            calls.append(kw["name"])
            quote = "Dieser Satz steht in keiner Datei." if kw["name"] == "casepath_confirm_facts" else QUOTE
            verdict = "not_stated" if kw["name"] == "casepath_confirm_facts_2" else "open"
            return ModelResult(value={"conditions": [{"id": "landlord_notified", "verdict": verdict, "value": None,
                                                      "quote": quote if verdict == "open" else ""}]},
                               usage={"input_tokens": 5}, deployment="d", response_id="x", attempts=1, seconds=0)
        work = CaseWork(case=CASE, files=FILES, base_workflow=with_presumption())
        work.readings = 3
        model = ScriptedModel([])
        model.respond_json = answer
        team.read_facts(model, work)
        team.confirm_facts(model, work)
        # the unfound open words were asked for once more (the same answer came back): that reading counts as no answer
        self.assertEqual(calls.count("casepath_confirm_facts"), 2)
        self.assertEqual(work.facts["landlord_notified"]["open_readings"], [True, None, False])
        self.assertNotIn("landlord_notified", work.presumptions())  # one found open answer holds it under the default

    def test_the_two_open_rules_on_recorded_answers(self):
        from casepath.process.workflows import open_without_raise, raised_open
        row = lambda *opens: {"status": "unknown", "citations": [1], "open_readings": list(opens)}
        for opens, any_, all_ in (((True, False, False), True, False), ((True, True, True), True, True),
                                  ((True, None, True), True, True),  # a failed reading clears nothing
                                  ((False, False, False), False, False), ((None, None, None), False, False)):
            self.assertEqual((raised_open(row(*opens), "any"), raised_open(row(*opens), "all")), (any_, all_), opens)
        self.assertTrue(raised_open({"status": "unknown", "citations": [1]}))  # a row stored before open answers were kept
        self.assertTrue(open_without_raise({**row(True, True, True), "readings": [False, None, None]}, False))  # R8

    def test_a_fact_is_raised_only_by_open_answers_whose_words_are_found_under_either_rule(self):
        from casepath.agents import team
        from casepath.agents.team import confirm_facts
        from casepath.process import workflows
        from tests.scripted import ModelResult
        from tests.scripted import ScriptedModel
        cite = [{"file": "f1", "quote": QUOTE}]
        open_quoted = {"fact": "landlord_notified", "status": "unknown", "value": None, "citations": cite}
        open_silent = {"fact": "landlord_notified", "status": "unknown", "value": None, "citations": []}
        # rule "any": one reading's open answer raises the fact; rule "all": every reading's must
        for rule, mixed in (("any", False), ("all", True)):
            for first, second, presumed in ((open_quoted, open_silent, mixed), (open_silent, open_quoted, mixed),
                                            (open_quoted, open_quoted, False), (open_silent, open_silent, True)):
                previous, workflows.OPEN_RULE = workflows.OPEN_RULE, rule
                try:
                    work = CaseWork(case=CASE, files=FILES, base_workflow=with_presumption())
                    work.readings = 2
                    work.facts["landlord_notified"] = {**first, "citations": work.located(first["citations"])[0],
                                                       "verdict": "not_checked", "by": "claim_reader"}
                    confirm_facts(ScriptedModel([], second_reading=[second]), work)
                    self.assertEqual("landlord_notified" in work.presumptions(), presumed, (rule, first, second))
                    self.assertEqual(workflows.raised_open(work.facts["landlord_notified"], "any"), first is open_quoted or second is open_quoted)
                finally:
                    workflows.OPEN_RULE = previous
        # A not_stated answer raises nothing, even when it quotes a related sentence.
        for verdict, presumed in (("not_stated", True), ("open", False)):
            work = CaseWork(case=CASE, files=FILES, base_workflow=with_presumption())
            model = ScriptedModel([])
            model.respond_json = lambda **kw: ModelResult(
                value={"conditions": [{"id": "landlord_notified", "verdict": verdict, "value": None, "quote": QUOTE}]},
                usage={"input_tokens": 5}, deployment="d", response_id="x", attempts=1, seconds=0)
            team.read_facts(model, work)
            team.confirm_facts(model, work)
            self.assertEqual(work.facts["landlord_notified"]["status"], "unknown")
            self.assertEqual("landlord_notified" in work.presumptions(), presumed, verdict)
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
        for applies, value in (("routed", True), ("unstated", True)):  # the reading found another value than the presumed one
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

    def test_one_reading_that_finds_the_presumed_value_does_not_block_the_presumption(self):
        from casepath.agents.team import confirm_facts, read_facts
        from tests.scripted import ScriptedModel
        happened = [{"fact": "landlord_notified", "status": "established", "value": "yes", "citations": [{"file": "f1", "quote": QUOTE}]}]
        silent = [{"fact": "landlord_notified", "status": "unknown", "value": None, "citations": []}]
        work = CaseWork(case=CASE, files=FILES, base_workflow=with_presumption(applies="routed", value=True))
        model = ScriptedModel([], first_reading=happened, second_reading=silent)
        read_facts(model, work)
        confirm_facts(model, work)
        self.assertEqual(work.accepted_facts(), {"landlord_notified": True})  # the defining event, as presumed

    def test_a_failed_or_silent_second_reading_does_not_clear_a_passage_that_raises_the_fact(self):
        from casepath.agents.azure_model import ModelError
        from casepath.agents.team import confirm_facts
        from tests.scripted import ScriptedModel

        class Failing:
            def respond_json(self, **kw):
                raise ModelError("timeout", "no answer")
        cite = [{"file": "f1", "quote": QUOTE}]
        for model in (Failing(), ScriptedModel([], second_reading=[])):  # failed, or ran without answering this condition
            work = CaseWork(case=CASE, files=FILES, base_workflow=with_presumption())
            work.facts["landlord_notified"] = {"fact": "landlord_notified", "status": "unknown", "value": None,
                                               "citations": work.located(cite)[0], "verdict": "not_checked", "by": "claim_reader"}
            confirm_facts(model, work)
            self.assertNotIn("landlord_notified", work.presumptions())  # the doubt the files raise stays open

    def test_one_reading_that_finds_the_presumed_value_supports_an_unstated_presumption_too(self):
        from casepath.agents.team import confirm_facts, read_facts
        from tests.scripted import ScriptedModel
        none = [{"fact": "landlord_notified", "status": "established", "value": "no", "citations": [{"file": "f1", "quote": QUOTE}]}]
        silent = [{"fact": "landlord_notified", "status": "unknown", "value": None, "citations": []}]
        work = CaseWork(case=CASE, files=FILES, base_workflow=with_presumption(applies="unstated", value=False))
        model = ScriptedModel([], first_reading=none, second_reading=silent)
        read_facts(model, work)
        confirm_facts(model, work)
        self.assertEqual(work.accepted_facts(), {"landlord_notified": False})


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
