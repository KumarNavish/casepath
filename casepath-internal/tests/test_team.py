import copy
import json
from pathlib import Path
import unittest

from casepath.process import casegraph, knowledge as kb
from casepath.agents.team import CaseTeam, TeamError
from tests.scripted import ScriptedModel, delegate, learn, report

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "example-defect.json").read_text())
QUOTE = "Ich habe den Vermieter am 2. März schriftlich informiert."
VENT = "Ich lüfte dreimal täglich, trotzdem kommt der Schimmel zurück."
FILES = [
    {"id": "f1", "name": "message.eml", "kind": "email", "text": f"Subject: Schimmel im Bad\n\n{QUOTE} {VENT}"},
    {"id": "f2", "name": "photo.jpg", "kind": "image", "text": "", "note": "Kept as an original."},
]
CASE = {"title": "Schimmel im Bad", "intake": {}}


def standard_script(*, finder_calls, result_fields, builder_calls=(), retry_turns=()):
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
        [("record_fact", {"part": None, "fact": "landlord_notified", "status": "established", "value": "ja", "citations": [{"file": "f1", "quote": QUOTE}]}),
         report("claim_reader")],
        [delegate("document_finder")],
        [*finder_calls, report("document_finder")],
        *retry_turns,
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
                {"text": "You told your landlord in writing.", "kind": "statement", "basis": ["fact:landlord_notified"]},
                {"text": "Please send the notice letter.", "kind": "request", "basis": ["document:notice_letter"]},
                {"text": "Kind regards", "kind": "formal", "basis": []}]},
                "learn": [learn(title="Ventilation record", why="Shows the tenant ventilated.",
                                citations=[{"file": "f1", "quote": VENT}])]})
        model = ScriptedModel(script)
        result = CaseTeam(model).run(case=CASE, files=FILES, workflow=FIXTURE)
        self.assertIn("record_fact", model.tools[0])  # the lead is a fixed plan: the first call is the claim reader's
        self.assertNotIn("record_document", model.tools[0])
        self.assertIn("record_document", model.tools[5])
        self.assertEqual(set(model.tool_choices), {"required"})
        self.assertEqual([t["date"] for t in result["brief"]["timeline"]], ["2 March"])
        fact, = result["facts"]
        self.assertEqual((fact["value"], fact["verdict"]), (True, "accepted"))
        self.assertEqual(result["evaluation"]["outcome"]["id"], "reported")
        statuses = {d["document"]: d["status"] for d in result["evaluation"]["documents"]}
        self.assertEqual(statuses, {"customer_message": "present", "photo": "missing", "notice_letter": "missing"})
        self.assertEqual([c["supported"] for c in result["reply"]["clauses"]], [True, True, True])
        self.assertEqual(result["reply"]["status"], "draft_not_sent")
        self.assertEqual(result["questions"], {"landlord_notified": "Was the landlord told?"})
        self.assertEqual(len(result["learning"]), 1)
        agents = {e["agent"] for e in result["events"] if e["kind"] == "agent.start"}
        self.assertEqual(agents, {"lead", "claim_reader", "process_builder", "document_finder", "source_checker", "result_checker"})

    def test_the_process_forms_live_from_the_findings(self):
        script = standard_script(
            finder_calls=[("record_document", {"document": "customer_message", "status": "present", "files": ["f1"],
                                               "citations": [{"file": "f1", "quote": "Subject: Schimmel im Bad"}], "note": ""})],
            result_fields={})
        result = CaseTeam(ScriptedModel(script)).run(case=CASE, files=FILES, workflow=FIXTURE)
        states = [e for e in result["events"] if e["kind"] == "process.state"]
        first, last = states[0], states[-1]
        self.assertEqual(first["graph"]["start"], FIXTURE["start"])  # the shape comes once, with the first state
        self.assertTrue(all("graph" not in s for s in states[1:]))
        self.assertEqual(first["path"][-1]["state"], "current")  # before any finding the case waits at its first question
        self.assertEqual([r["step"] for r in last["path"]], [r["step"] for r in result["evaluation"]["path"]])
        self.assertTrue(all(r["confirmed"] for r in last["path"] if r["state"] != "current"))
        self.assertEqual(last["outcome"], "reported")
        # The recorded fact moves the path before the source checker confirms it; the confirmation follows.
        located = next(i for i, s in enumerate(states) if s["cause"].get("kind") == "fact.located")
        accepted = next(i for i, s in enumerate(states) if s["cause"].get("kind") == "fact.accepted")
        self.assertLess(located, accepted)
        self.assertEqual(states[located]["outcome"], "reported")
        self.assertEqual([(r["step"], r["confirmed"]) for r in states[located]["path"][:2]], [("intake", True), ("notice", False)])
        docs = {d["document"]: d for d in last["documents"]}
        self.assertEqual((docs["customer_message"]["status"], docs["customer_message"]["verdict"]), ("present", "accepted"))
        # Once the document finder has looked, a need it did not find is missing, as in the result's checklist.
        final = {d["document"]: d["status"] for d in result["evaluation"]["documents"]}
        self.assertEqual({k: v["status"] for k, v in docs.items()}, final)
        before = next(s for s in states if s["cause"].get("kind") == "document.recorded")
        self.assertIn("open", {d["status"] for d in before["documents"]})
        self.assertTrue(all(d["step"] in {r["step"] for r in last["path"]} or d["step"] is None for d in last["documents"]))
        self.assertNotIn("quote", json.dumps(states))  # ids and states only; the quotes stay in the finding events

    def test_rejected_finding_is_not_used(self):
        script = standard_script(finder_calls=[], result_fields={"reply": {"needed": True, "subject": "", "clauses": [
            {"text": "You told your landlord.", "kind": "statement", "basis": ["fact:landlord_notified"]}]}})
        script = standard_script(finder_calls=[], retry_turns=[[report("claim_reader")]], result_fields={"reply": {"needed": True, "subject": "", "clauses": [
            {"text": "You told your landlord.", "kind": "statement", "basis": ["fact:landlord_notified"]}]}})
        result = CaseTeam(ScriptedModel(script, verdicts={"fact:landlord_notified": "uncertain"})).run(case=CASE, files=FILES, workflow=FIXTURE)
        retry = [e for e in result["events"] if e["kind"] == "delegate" and e["to"] == "claim_reader"][-1]
        self.assertIn("landlord_notified", retry["instruction"])  # one targeted retry before the result
        self.assertEqual(result["facts"][0]["verdict"], "rejected")
        self.assertEqual(result["evaluation"]["current"]["step"], "notice")
        self.assertFalse(result["reply"]["clauses"][0]["supported"])

    def test_an_agent_must_report_on_its_last_turn(self):
        from casepath.agents.team import CaseWork, run_agent
        work = CaseWork(case=CASE, files=FILES, base_workflow=FIXTURE)
        model = ScriptedModel([[("list_files", {})], [("list_files", {})], [report("document_finder")]])
        run_agent(model, work, "document_finder", "Find.", max_turns=3)
        self.assertEqual(model.tool_choices, ["required", "required", {"type": "function", "name": "report"}])
        with self.assertRaises(TeamError) as caught:
            run_agent(ScriptedModel([[("list_files", {})]] * 2), work, "document_finder", "Find.", max_turns=2)
        self.assertEqual(caught.exception.reason, "turn_limit")

    def test_a_case_needs_its_own_step_and_it_can_become_knowledge(self):
        from casepath.process.workflows import evaluate
        edit = {"id": "e1", "op": "add_step", "case_id": "c1", "args": {"before": "assess", "title": "Einsprache schreiben",
                "why": "Die Kündigung fällt in die Sperrfrist.", "legal_basis": "Art. 336c OR"}, "status": "active"}
        graph, provenance = casegraph.build(FIXTURE, edits=[edit])
        self.assertTrue(provenance["edits"][0]["applied"])
        step = next(s for s in graph["steps"] if s["id"] == "s-e1")
        self.assertEqual((step["legal_basis"], step["next"][0]["to"]), ("Art. 336c OR", "assess"))
        path = [p["step"] for p in evaluate(graph, {"landlord_notified": True}, {}, checked=True)["path"]]
        self.assertLess(path.index("s-e1"), path.index("assess"))  # the case passes through its own step
        item = kb.set_status(kb.from_edit("example-defect", edit, graph, by="expert"), "active", by="expert")
        later, used = casegraph.build(FIXTURE, knowledge=[item], case_id="c2")
        self.assertTrue(used["knowledge"][0]["applied"])
        self.assertIn(f"k-{item['id']}", {s["id"] for s in later["steps"]})

    def test_learning_with_personal_details_is_withheld(self):
        from casepath.agents.team import personal_details
        names = {"Brunner", "Kramgasse"}
        self.assertFalse(personal_details({"title": "Lüftungsprotokoll", "why": "Zeigt, wie die Mieterin gelüftet hat."}, names))
        self.assertTrue(personal_details({"title": "Brief an Frau Brunner"}, names))
        self.assertTrue(personal_details({"why": "Rückruf unter 031 555 12 34"}, names))
        self.assertTrue(personal_details({"note": "Police 8017.0833.0054"}, set()))

    def test_a_second_reading_surfaces_disagreement_and_fills_gaps(self):
        from casepath.agents.team import CaseWork, confirm_facts
        work = CaseWork(case=CASE, files=FILES, base_workflow=FIXTURE)
        cite = [{"file": "f1", "quote": QUOTE}]
        same = ScriptedModel([], second_reading=[{"fact": "landlord_notified", "status": "established", "value": "yes", "citations": cite}])
        self.assertEqual(confirm_facts(same, work)["added"], 1)  # the first reading had not recorded it
        self.assertEqual(work.facts["landlord_notified"]["value"], True)
        work.facts["landlord_notified"]["verdict"] = "accepted"
        other = ScriptedModel([], second_reading=[{"fact": "landlord_notified", "status": "established", "value": "no", "citations": cite}])
        self.assertEqual(confirm_facts(other, work)["differed"], 1)
        row = work.facts["landlord_notified"]
        self.assertEqual((row["status"], row["second_value"]), ("conflicting", False))
        self.assertNotIn("landlord_notified", work.accepted_facts())  # a person settles it

    def test_every_fact_a_condition_uses_is_read_twice(self):
        """Facts that only decide whether a document is needed are read a second time too, with the same agreement rule."""
        from casepath.agents.team import CaseWork, confirm_facts, gating_facts
        data = copy.deepcopy(FIXTURE)
        data["facts"].append({"id": "photos_taken", "type": "boolean", "question": "Did the tenant take photos?", "source_refs": ["fixture#p"]})
        next(d for d in data["documents"] if d["id"] == "photo")["required_when"] = {"fact": "photos_taken", "is": True}
        work = CaseWork(case=CASE, files=FILES, base_workflow=data)
        self.assertEqual(sorted(f["id"] for f in gating_facts(work)), ["landlord_notified", "photos_taken"])
        cite = [{"file": "f1", "quote": VENT}]
        work.facts["photos_taken"] = {"fact": "photos_taken", "status": "established", "value": True, "citations": cite,
                                      "verdict": None, "by": "claim_reader"}
        other = ScriptedModel([], second_reading=[{"fact": "photos_taken", "status": "established", "value": "no", "citations": cite}])
        self.assertEqual(confirm_facts(other, work)["differed"], 1)
        self.assertEqual(work.facts["photos_taken"]["status"], "conflicting")

    def test_two_readings_of_a_name_with_and_without_its_address_agree(self):
        from casepath.agents.team import same_reading
        text, date = {"type": "text"}, {"type": "date"}
        self.assertTrue(same_reading(text, "Garage Kälin Occasionen AG", "Garage Kälin Occasionen AG, Zürcherstrasse 140, 8645 Jona."))
        self.assertTrue(same_reading(text, "2 % pro Jahr", "2 % pro Jahr; jeweils am 31. Dezember fällig"))
        self.assertFalse(same_reading(text, "Garage Kälin Occasionen AG", "Auto Brunner GmbH"))
        self.assertFalse(same_reading(date, "2025-03-31", "2025-04-30"))

    def test_process_builder_changes_need_a_basis(self):
        unsupported = ("propose_change", {"op": "add_document", "title": "Lease", "why": "Shows the tenancy.", "question": "", "step": None,
                                          "required_when": [], "legal_basis": "", "basis_knowledge": None, "citations": [], "reason": "Usually needed."})
        supported = ("propose_change", {"op": "add_document", "title": "Ventilation record", "why": "The tenant says they ventilate.",
                                        "question": "", "step": "assess", "required_when": [{"fact": "landlord_notified", "value": "yes"}],
                                        "legal_basis": "", "basis_knowledge": None, "citations": [{"file": "f1", "quote": VENT}], "reason": "The customer raises it."})
        script = standard_script(builder_calls=[unsupported, supported], finder_calls=[], result_fields={})
        result = CaseTeam(ScriptedModel(script)).run(case=CASE, files=FILES, workflow=FIXTURE)
        edit, = result["agent_edits"]
        self.assertEqual(edit["args"]["title"], "Ventilation record")
        row = next(d for d in result["evaluation"]["documents"] if d["document"] == "e-pb1")
        self.assertEqual(row["required"], "suggested")  # an agent's addition waits for a person
        self.assertNotIn("e-pb1", [a.get("document") for a in result["evaluation"]["next_actions"]])

    def test_a_document_the_law_requires_is_required_even_when_the_files_never_mention_it(self):
        lease = ("propose_change", {"op": "add_document", "title": "Mietvertrag", "why": "Zeigt das Mietverhältnis.", "question": "",
                                    "step": "assess", "required_when": [], "legal_basis": "Art. 253 OR", "basis_knowledge": None,
                                    "citations": [], "reason": "Das Mietverhältnis ist zu belegen."})
        hunch = ("propose_change", {"op": "add_document", "title": "Hausratversicherung", "why": "Vielleicht hilfreich.", "question": "",
                                    "step": "assess", "required_when": [], "legal_basis": "allgemein üblich", "basis_knowledge": None,
                                    "citations": [], "reason": "Oft dabei."})
        script = standard_script(builder_calls=[lease, hunch], finder_calls=[], result_fields={})
        result = CaseTeam(ScriptedModel(script)).run(case=CASE, files=FILES, workflow=FIXTURE)
        edit, = result["agent_edits"]  # a need with neither an article, a quote nor Knowledge is refused
        row = next(d for d in result["evaluation"]["documents"] if d["document"] == "e-pb1")
        self.assertEqual((row["title"], row["required"], row["status"]), ("Mietvertrag", "yes", "missing"))
        self.assertIn({"kind": "obtain", "document": "e-pb1", "text": "Mietvertrag", "why": "Zeigt das Mietverhältnis."},
                      result["evaluation"]["next_actions"])
        self.assertEqual(next(d for d in result["process"]["documents"] if d["id"] == "e-pb1")["legal_basis"], "Art. 253 OR")
        live = [e for e in result["events"] if e["kind"] == "process.state"][-1]
        self.assertEqual(next(d for d in live["documents"] if d["document"] == "e-pb1")["legal_basis"], "Art. 253 OR")

    def test_agents_add_at_most_six_items(self):
        def question(n):
            return ("propose_change", {"op": "add_question", "title": "", "why": "", "question": f"Question {n}?", "step": None,
                                       "required_when": [], "legal_basis": "", "basis_knowledge": None, "citations": [{"file": "f1", "quote": VENT}], "reason": "Raised."})
        script = standard_script(builder_calls=[question(n) for n in range(8)], finder_calls=[], result_fields={})
        result = CaseTeam(ScriptedModel(script)).run(case=CASE, files=FILES, workflow=FIXTURE)
        self.assertEqual(len(result["agent_edits"]), 6)


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
        from casepath.process.workflows import evaluate
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
        from casepath.process.workflows import evaluate
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
        script[7].insert(1, ("record_fact", {"part": None, "fact": "frist", "status": "established", "value": "2025-03-15",
                                             "citations": [{"file": "f1", "quote": "Bitte beheben Sie den Mangel bis zum 15. März 2025."}]}))
        result = CaseTeam(ScriptedModel(script)).run(case=CASE, files=files, workflow=workflow)
        self.assertEqual(result["case_summary"], [{"field": "gegenpartei", "label": "Gegenpartei", "text": "Immo Aare AG, Bern"}])
        self.assertEqual(result["deadlines"], [{"fact": "frist", "question": "Welche Frist gilt?", "date": "2025-03-15"}])


class HandlerFlowTests(unittest.TestCase):
    def test_the_builder_is_skipped_when_the_workflow_names_each_stages_action(self):
        workflow = copy.deepcopy(FIXTURE)
        workflow["steps"][0]["action"] = {"kind": "A1", "title": "Unterlagen anfordern"}
        script = [turn for turn in standard_script(finder_calls=[], result_fields={})
                  if not any(name in {"open_process", "view_knowledge"} or args.get("agent") == "process_builder"
                             for name, args in turn)]
        script = [t for t in script if not (len(t) == 1 and t[0][0] == "report" and "questions" in t[0][1])]
        # one claim-reader delegation: drop the second delegate and fold its fact turn into the first reading
        second = next(i for i, t in enumerate(script) if i > 0 and t == [delegate("claim_reader", "Record the facts.")])
        facts_turn = script.pop(second + 1)
        script.pop(second)
        brief_report = next(i for i, t in enumerate(script) if t and t[0][0] == "report" and t[0][1].get("request"))
        script.insert(brief_report, [c for c in facts_turn if c[0] != "report"])
        model = ScriptedModel(script)
        result = CaseTeam(model).run(case=CASE, files=FILES, workflow=workflow)
        openings = [json.loads(i[0]["content"]) for i in model.inputs if i and isinstance(i[0].get("content"), str) and i[0]["content"].startswith("{")]
        checker = [o for o in openings if "evaluate" in o]
        self.assertTrue(checker and "get_findings" in checker[0])  # the result checker is handed what it used to fetch
        agents = {e["agent"] for e in result["events"] if e["kind"] == "agent.start"}
        self.assertNotIn("process_builder", agents)
        self.assertIn("agent.skipped", {e["kind"] for e in result["events"]})
        starts = [e for e in result["events"] if e["kind"] == "agent.start" and e["agent"] == "claim_reader"]
        self.assertEqual(len(starts), 1)  # one reading briefs the case and records the facts
        self.assertEqual(result["facts"][0]["fact"], "landlord_notified")


class TooLongTurnTests(unittest.TestCase):
    def test_a_turn_over_the_output_limit_is_asked_again_shorter_once(self):
        class TooLong(RuntimeError):
            reason = "max_output_tokens"

        class OnceTooLong(ScriptedModel):
            failed = False

            def respond(self, **kw):
                if not self.failed:
                    self.failed = True
                    raise TooLong("The model stopped before finishing its turn.")
                return super().respond(**kw)

        script = standard_script(finder_calls=[], result_fields={})
        model = OnceTooLong(script)
        result = CaseTeam(model).run(case=CASE, files=FILES, workflow=FIXTURE)
        self.assertIn("turn.too_long", {e["kind"] for e in result["events"]})
        self.assertTrue(any("shorter turns" in str(m.get("content")) for m in model.inputs[0]))

        class AlwaysTooLong(ScriptedModel):
            def respond(self, **kw):
                raise TooLong("The model stopped before finishing its turn.")
        with self.assertRaises(TooLong):
            CaseTeam(AlwaysTooLong(script)).run(case=CASE, files=FILES, workflow=FIXTURE)


class AgentModelTests(unittest.TestCase):
    def test_an_agent_runs_on_its_own_model_when_one_is_configured(self):
        main, other = ScriptedModel([]), ScriptedModel([])
        main.agents = {"claim_reader": other}
        team = CaseTeam(main)
        self.assertIs(team.model_for("claim_reader"), other)
        self.assertIs(team.model_for("result_checker"), main)
        self.assertIs(CaseTeam(ScriptedModel([])).model_for("claim_reader").__class__, ScriptedModel)
        from casepath.config import load_settings
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            env = {"CASEPATH_DATA_DIR": tmp, "CASEPATH_DEV_USER": "u", "CASEPATH_AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
                   "CASEPATH_AZURE_OPENAI_DEPLOYMENT": "big", "CASEPATH_AGENT_MODELS": "claim_reader=small, document_finder = small"}
            self.assertEqual(dict(load_settings(env).model.agent_deployments), {"claim_reader": "small", "document_finder": "small"})
            self.assertEqual(load_settings({**env, "CASEPATH_AGENT_MODELS": ""}).model.agent_deployments, ())


class FitReportTests(unittest.TestCase):
    def test_a_report_with_a_missing_field_and_an_overlong_text_is_fitted_not_rejected(self):
        from casepath.agents.schema import arr, fit_to_schema, obj, text, validate_result
        schema = obj(summary=text(10, minLength=1), points=arr(text(5), maxItems=2), reply=obj(needed={"type": "boolean"}, subject=text(20)))
        fitted = fit_to_schema({"summary": "a long summary", "points": ["abcdefg", "b", "c"], "extra": 1}, schema)
        validate_result(fitted, schema)
        self.assertEqual(fitted, {"summary": "a long sum", "points": ["abcde", "b"], "reply": {"needed": False, "subject": ""}})
