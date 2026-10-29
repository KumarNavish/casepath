import copy
import json
from pathlib import Path
import unittest

from casepath_internal import casegraph, knowledge as kb
from casepath_internal.agents import CaseTeam, TeamError
from tests.scripted import ScriptedModel, delegate, learn, report

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "example-defect.json").read_text())
QUOTE = "Ich habe den Vermieter am 2. März schriftlich informiert."
VENT = "Ich lüfte dreimal täglich, trotzdem kommt der Schimmel zurück."
FILES = [
    {"id": "f1", "name": "message.eml", "kind": "email", "text": f"Subject: Schimmel im Bad\n\n{QUOTE} {VENT}"},
    {"id": "f2", "name": "photo.jpg", "kind": "image", "text": "", "note": "Kept as an original."},
]
CASE = {"title": "Schimmel im Bad", "intake": {}}


def standard_script(*, finder_calls, result_fields, builder_calls=()):
    return [
        [delegate("claim_reader", "Brief the case.")],
        [("read_file", {"file": "f1", "from_page": None, "to_page": None})],
        [report("claim_reader", request="Check the mould defect.", parties=[{"role": "tenant", "name": "Example Tenant"}],
                timeline=[{"date": "2 March", "event": "Landlord told", "citations": [{"file": "f1", "quote": QUOTE}]},
                          {"date": "?", "event": "Invented", "citations": [{"file": "f1", "quote": "Never written here at all"}]}])],
        [delegate("process_builder")],
        [("open_process", {}), ("view_knowledge", {})],
        [*builder_calls, report("process_builder", questions=[{"fact": "landlord_notified", "plain": "Was the landlord told?"}])],
        [delegate("claim_reader", "Record the facts.")],
        [("record_fact", {"fact": "landlord_notified", "status": "established", "value": "ja", "citations": [{"file": "f1", "quote": QUOTE}]}),
         report("claim_reader")],
        [delegate("document_finder")],
        [*finder_calls, report("document_finder")],
        [delegate("result_checker")],
        [("evaluate", {}), report("result_checker", **result_fields)],
        [("complete", {"summary": "Prepared."})],
    ]


class TeamTests(unittest.TestCase):
    def test_each_agent_works_in_its_own_context(self):
        script = standard_script(
            finder_calls=[("record_document", {"document": "customer_message", "status": "present", "files": ["f1"],
                                               "citations": [{"file": "f1", "quote": "Subject: Schimmel im Bad"}], "note": ""}),
                          ("record_document", {"document": "notice_letter", "status": "absent", "files": [], "citations": [], "note": ""})],
            result_fields={"reply": {"needed": True, "subject": "Re: Schimmel", "clauses": [
                {"text": "You told your landlord in writing.", "basis": ["fact:landlord_notified"]},
                {"text": "Please send the notice letter.", "basis": ["document:notice_letter"]}]},
                "learn": [learn(title="Ventilation record", why="Shows the tenant ventilated.",
                                citations=[{"file": "f1", "quote": VENT}])]})
        model = ScriptedModel(script)
        result = CaseTeam(model).run(case=CASE, files=FILES, workflow=FIXTURE)
        self.assertEqual(model.tools[0], ["delegate", "complete"])
        self.assertIn("record_fact", model.tools[1])
        self.assertNotIn("record_document", model.tools[1])
        self.assertIn("record_document", model.tools[9])
        self.assertEqual([t["date"] for t in result["brief"]["timeline"]], ["2 March"])
        fact, = result["facts"]
        self.assertEqual((fact["value"], fact["verdict"]), (True, "accepted"))
        self.assertEqual(result["evaluation"]["outcome"]["id"], "reported")
        statuses = {d["document"]: d["status"] for d in result["evaluation"]["documents"]}
        self.assertEqual(statuses, {"customer_message": "present", "photo": "missing", "notice_letter": "missing"})
        self.assertEqual([c["supported"] for c in result["reply"]["clauses"]], [True, True])
        self.assertEqual(result["reply"]["status"], "draft_not_sent")
        self.assertEqual(result["questions"], {"landlord_notified": "Was the landlord told?"})
        self.assertEqual(len(result["learning"]), 1)
        agents = {e["agent"] for e in result["events"] if e["kind"] == "agent.start"}
        self.assertEqual(agents, {"lead", "claim_reader", "process_builder", "document_finder", "source_checker", "result_checker"})

    def test_rejected_finding_is_not_used(self):
        script = standard_script(finder_calls=[], result_fields={"reply": {"needed": True, "subject": "", "clauses": [
            {"text": "You told your landlord.", "basis": ["fact:landlord_notified"]}]}})
        result = CaseTeam(ScriptedModel(script, verdicts={"fact:landlord_notified": "uncertain"})).run(case=CASE, files=FILES, workflow=FIXTURE)
        self.assertEqual(result["facts"][0]["verdict"], "rejected")
        self.assertEqual(result["evaluation"]["current"]["step"], "notice")
        self.assertFalse(result["reply"]["clauses"][0]["supported"])

    def test_guards_and_limits(self):
        model = ScriptedModel([[delegate("document_finder")], [("complete", {"summary": "x"})]] + [[delegate("source_checker")]] * 20)
        with self.assertRaises(TeamError) as caught:
            CaseTeam(model, max_lead_turns=4).run(case=CASE, files=FILES, workflow=FIXTURE)
        self.assertEqual(caught.exception.reason, "turn_limit")

    def test_process_builder_changes_need_a_basis(self):
        unsupported = ("propose_change", {"op": "add_document", "title": "Lease", "why": "Shows the tenancy.", "question": "", "step": None,
                                          "required_when": [], "basis_knowledge": None, "citations": [], "reason": "Usually needed."})
        supported = ("propose_change", {"op": "add_document", "title": "Ventilation record", "why": "The tenant says they ventilate.",
                                        "question": "", "step": "assess", "required_when": [{"fact": "landlord_notified", "value": "yes"}],
                                        "basis_knowledge": None, "citations": [{"file": "f1", "quote": VENT}], "reason": "The customer raises it."})
        script = standard_script(builder_calls=[unsupported, supported], finder_calls=[], result_fields={})
        result = CaseTeam(ScriptedModel(script)).run(case=CASE, files=FILES, workflow=FIXTURE)
        edit, = result["agent_edits"]
        self.assertEqual(edit["args"]["title"], "Ventilation record")
        row = next(d for d in result["evaluation"]["documents"] if d["document"] == "e-pb1")
        self.assertEqual(row["required"], "suggested")  # an agent's addition waits for a person
        self.assertNotIn("e-pb1", [a.get("document") for a in result["evaluation"]["next_actions"]])

    def test_agents_add_at_most_three_items(self):
        def question(n):
            return ("propose_change", {"op": "add_question", "title": "", "why": "", "question": f"Question {n}?", "step": None,
                                       "required_when": [], "basis_knowledge": None, "citations": [{"file": "f1", "quote": VENT}], "reason": "Raised."})
        script = standard_script(builder_calls=[question(n) for n in range(5)], finder_calls=[], result_fields={})
        result = CaseTeam(ScriptedModel(script)).run(case=CASE, files=FILES, workflow=FIXTURE)
        self.assertEqual(len(result["agent_edits"]), 3)


class KnowledgeReuseTests(unittest.TestCase):
    def test_active_knowledge_shapes_the_next_case(self):
        item = kb.set_status(kb.new_item("example-defect", "document_need",
                                         {"title": "Ventilation record", "why": "Shows ventilation.", "step": "assess"},
                                         applies_when={"fact": "landlord_notified", "is": True},
                                         origin={"kind": "case", "by": "result_checker", "case_id": "c0"}), "active", by="reviewer")
        graph, provenance = casegraph.build(FIXTURE, knowledge=[item])
        self.assertTrue(provenance["knowledge"][0]["applied"])
        document = next(d for d in graph["documents"] if d.get("knowledge") == item["id"])
        self.assertFalse(document["suggested"])
        script = standard_script(
            finder_calls=[("record_document", {"document": f"k-{item['id']}", "status": "present", "files": ["f1"],
                                               "citations": [{"file": "f1", "quote": VENT}], "note": ""})],
            result_fields={"learn": [learn(action="refine", target=item["id"], title="Ventilation record (dated)",
                                           why="Dated entries show when.", citations=[{"file": "f1", "quote": VENT}])]})
        result = CaseTeam(ScriptedModel(script)).run(case=CASE, files=FILES, workflow=FIXTURE, knowledge=[item])
        row = next(d for d in result["evaluation"]["documents"] if d["document"] == f"k-{item['id']}")
        self.assertEqual((row["status"], row["required"]), ("present", "yes"))
        self.assertEqual(result["learning"][0]["action"], "refine")

    def test_candidates_are_suggestions_and_lifecycle(self):
        item = kb.new_item("example-defect", "document_need", {"title": "Ventilation record", "why": "Shows ventilation."},
                           origin={"kind": "case", "by": "result_checker", "case_id": "c0"})
        graph, _ = casegraph.build(FIXTURE, knowledge=[item])
        from casepath_internal.workflows import evaluate
        row = next(d for d in evaluate(graph, {}, {}, checked=True)["documents"] if d["document"] == f"k-{item['id']}")
        self.assertEqual((row["required"], row["status"]), ("suggested", "missing"))
        self.assertNotIn(f"k-{item['id']}", [a.get("document") for a in evaluate(graph, {}, {}, checked=True)["next_actions"]])
        used = kb.record_outcome(item, case_id="c1", run_id="r1", document_status="present")
        twice = kb.record_outcome(kb.record_outcome(used, case_id="c2", run_id="r2", contradicted=True),
                                  case_id="c3", run_id="r3", contradicted=True)
        self.assertEqual((twice["stats"]["uses"], twice["stats"]["confirmed"], twice["stats"]["contradicted"]), (3, 1, 2))
        self.assertTrue(twice["review_suggested"])
        refined = kb.refine(item, content={"title": "Dated ventilation record"}, by="reviewer", case_id="c3")
        self.assertEqual((refined["version"], refined["content"]["title"]), (2, "Dated ventilation record"))
        self.assertEqual(refined["history"][-1]["previous"]["content"]["title"], "Ventilation record")

    def test_bad_items_and_edits_are_skipped_not_fatal(self):
        bad = kb.new_item("example-defect", "document_need", {"title": "X", "why": "Y"}, applies_when={"fact": "gone", "is": True},
                          origin={"kind": "case", "case_id": "c0"})
        graph, provenance = casegraph.build(FIXTURE, knowledge=[bad], edits=[{"id": "e1", "op": "remove_document", "args": {"document": "nope"}}])
        self.assertFalse(provenance["knowledge"][0]["applied"])
        self.assertFalse(provenance["edits"][0]["applied"])
        self.assertEqual(len(graph["documents"]), len(FIXTURE["documents"]))


class EditTests(unittest.TestCase):
    def test_edits_change_the_checklist_and_can_be_undone(self):
        from casepath_internal.workflows import evaluate
        facts, checked = {"landlord_notified": True}, True
        before = evaluate(casegraph.build(FIXTURE)[0], facts, {}, checked=checked)
        edits = [{"id": "e1", "op": "add_document", "args": {"title": "Ventilation record", "why": "Mould despite ventilation.", "step": "assess"}},
                 {"id": "e2", "op": "set_required_when", "args": {"document": "photo", "required_when": {"fact": "landlord_notified", "is": False}}},
                 {"id": "e3", "op": "add_question", "args": {"question": "Is the flat on the ground floor?", "type": "boolean",
                                                             "gates_document": "notice_letter"}}]
        graph, provenance = casegraph.build(FIXTURE, edits=edits)
        self.assertTrue(all(e["applied"] for e in provenance["edits"]))
        after = evaluate(graph, facts, {}, checked=checked)
        change = casegraph.diff(before, after)
        self.assertEqual([d["document"] for d in change["documents_added"]], ["e-e1"])
        self.assertEqual({d["document"] for d in change["documents_removed"]}, {"photo"})
        self.assertIn({"document": "notice_letter", "before": "missing", "after": "missing", "required_before": "yes",
                       "required_after": "depends"}, change["documents_changed"])
        undone = [dict(e, status="undone") if e["id"] == "e1" else e for e in edits]
        self.assertNotIn("e-e1", {d["document"] for d in evaluate(casegraph.build(FIXTURE, edits=undone)[0], facts, {}, checked=True)["documents"]})

    def test_invalid_edits_are_refused(self):
        graph, _ = casegraph.build(FIXTURE)
        for edit in ({"op": "add_document", "args": {"title": "X", "why": "Y", "step": "nowhere"}},
                     {"op": "set_transition", "args": {"step": "notice", "index": 5, "to": "assess"}},
                     {"op": "set_required_when", "args": {"document": "photo", "required_when": {"fact": "unknown_fact", "is": True}}},
                     {"op": "delete_everything", "args": {}}):
            with self.assertRaises((casegraph.EditError, Exception)):
                casegraph.check_edit(graph, edit)

    def test_edit_becomes_knowledge(self):
        edit = {"id": "e1", "case_id": "c1", "op": "add_document", "args": {"title": "Ventilation record", "why": "Mould despite ventilation."}}
        item = kb.from_edit("example-defect", edit, FIXTURE, by="employee")
        self.assertEqual((item["status"], item["origin"]["kind"], item["content"]["title"]), ("candidate", "case_edit", "Ventilation record"))


if __name__ == "__main__":
    unittest.main()


class HandlerDeliverableTests(unittest.TestCase):
    def test_case_summary_and_deadlines(self):
        workflow = copy.deepcopy(FIXTURE)
        workflow["summary"] = [{"id": "gegenpartei", "label": "Gegenpartei", "source_refs": ["fixture#s"]}]
        workflow["facts"].append({"id": "frist", "type": "date", "deadline": True, "question": "Welche Frist gilt?", "source_refs": ["fixture#f"]})
        files = [{"id": "f1", "name": "m.eml", "kind": "email", "text": f"Subject: Schimmel\n\n{QUOTE} Bitte beheben Sie den Mangel bis zum 15. März 2025."}]
        script = standard_script(finder_calls=[], result_fields={"case_summary": [{"field": "gegenpartei", "text": "Immo Aare AG, Bern"}]})
        script[7].insert(1, ("record_fact", {"fact": "frist", "status": "established", "value": "2025-03-15",
                                             "citations": [{"file": "f1", "quote": "Bitte beheben Sie den Mangel bis zum 15. März 2025."}]}))
        result = CaseTeam(ScriptedModel(script)).run(case=CASE, files=files, workflow=workflow)
        self.assertEqual(result["case_summary"], [{"field": "gegenpartei", "label": "Gegenpartei", "text": "Immo Aare AG, Bern"}])
        self.assertEqual(result["deadlines"], [{"fact": "frist", "question": "Welche Frist gilt?", "date": "2025-03-15"}])
