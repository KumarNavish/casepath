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
        [("record_fact", {"fact": "landlord_notified", "status": "established", "value": "ja", "citations": [{"file": "f1", "quote": QUOTE}]}),
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
        self.assertIn("record_document", model.tools[4])  # the facts are read in one structured reading, not an agent turn
        self.assertEqual(set(model.tool_choices), {"required"})
        self.assertEqual([t["date"] for t in result["brief"]["timeline"]], ["2 March"])
        fact = next(f for f in result["facts"] if f["fact"] == "landlord_notified")
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

    def test_a_deciding_fact_both_readings_agree_on_stands_and_the_checkers_doubt_is_a_flag(self):
        script = standard_script(finder_calls=[], result_fields={"reply": {"needed": True, "subject": "", "clauses": [
            {"text": "You told your landlord.", "kind": "statement", "basis": ["fact:landlord_notified"]}]}})
        result = CaseTeam(ScriptedModel(script, verdicts={"fact:landlord_notified": "uncertain"})).run(case=CASE, files=FILES, workflow=FIXTURE)
        fact = next(f for f in result["facts"] if f["fact"] == "landlord_notified")
        self.assertEqual((fact["verdict"], fact["flag"]["kind"]), ("accepted", "source_checker_doubt"))
        self.assertEqual(result["evaluation"]["outcome"]["id"], "reported")  # the checklist follows the agreed facts
        self.assertFalse(any(e["kind"] == "delegate" and e["to"] == "claim_reader" and "did not accept" in e["instruction"]
                             for e in result["events"]))  # nothing to retry

    def test_a_case_worker_edit_still_changes_what_a_locked_deciding_fact_requires(self):
        from casepath.agents.team import CaseWork, confirm_facts
        cite = [{"file": "f1", "quote": QUOTE}]
        edit = {"id": "e1", "op": "set_required_when", "status": "active",
                "args": {"document": "notice_letter", "required_when": {"fact": "landlord_notified", "is": False}}}
        work = CaseWork(case=CASE, files=FILES, base_workflow=FIXTURE, edits=[edit])
        work.facts["landlord_notified"] = {"fact": "landlord_notified", "status": "established", "value": True,
                                           "citations": work.located(cite)[0], "verdict": "accepted", "by": "claim_reader"}
        confirm_facts(ScriptedModel([], second_reading=[{"fact": "landlord_notified", "status": "established", "value": "yes", "citations": cite}]), work)
        self.assertTrue(work.facts["landlord_notified"].get("agreed"))
        self.assertNotIn("notice_letter", [d["document"] for d in work.evaluate()["documents"]])

    def test_after_the_readings_one_agent_cannot_change_a_deciding_fact(self):
        from casepath.agents.team import CaseWork, _record_fact, confirm_facts
        work = CaseWork(case=CASE, files=FILES, base_workflow=FIXTURE)
        confirm_facts(ScriptedModel([], second_reading=[]), work)
        result = _record_fact(work, "claim_reader", {"fact": "landlord_notified", "status": "established", "value": "yes",
                                                     "citations": [{"file": "f1", "quote": QUOTE}]})
        self.assertFalse(result["accepted"])
        self.assertNotIn("landlord_notified", work.accepted_facts())
        # Nor a routing fact (the workflow's selection condition): the readings read it too.
        self.assertFalse(_record_fact(work, "claim_reader", {"fact": "legal_area", "status": "established", "value": "tenancy_defect",
                                                             "citations": [{"file": "f1", "quote": QUOTE}]})["accepted"])

    def test_a_failed_reading_and_readings_that_differ_at_four_readings(self):
        from casepath.agents.azure_model import ModelError
        from casepath.agents.team import CaseWork, confirm_facts, read_facts
        from tests.scripted import ModelResult
        def answers(confirming):
            def respond(**kw):
                if kw["name"] == "casepath_read_facts":
                    verdict = "true"
                elif kw["name"] in confirming and confirming[kw["name"]] is None:
                    raise ModelError("timeout", "no answer")
                else:
                    verdict = confirming[kw["name"]]
                return ModelResult(value={"conditions": [{"id": "landlord_notified", "verdict": verdict, "value": None, "quote": QUOTE}]},
                                   usage={"input_tokens": 5}, deployment="d", response_id="x", attempts=1, seconds=0)
            return respond
        cases = (({"casepath_confirm_facts": "true", "casepath_confirm_facts_2": "false", "casepath_confirm_facts_3": None}, "conflicting"),
                 ({"casepath_confirm_facts": "true", "casepath_confirm_facts_2": "false", "casepath_confirm_facts_3": "true"}, "conflicting"),
                 ({"casepath_confirm_facts": "true", "casepath_confirm_facts_2": "true", "casepath_confirm_facts_3": None}, "unknown"))
        for confirming, status in cases:
            work = CaseWork(case=CASE, files=FILES, base_workflow=FIXTURE)
            work.readings = 4
            model = ScriptedModel([])
            model.respond_json = answers(confirming)
            read_facts(model, work)
            confirm_facts(model, work)
            self.assertEqual(work.facts["landlord_notified"]["status"], status, confirming)
            self.assertNotIn("landlord_notified", work.accepted_facts())
            if None in confirming.values():
                self.assertIn("reading_failed", [w["reason"] for w in work.limits])

    def test_the_retry_pass_cannot_overwrite_a_routing_fact_after_the_readings(self):
        from casepath.agents.team import CaseTeam, CaseWork, _record_fact, confirm_facts
        cite = [{"file": "f1", "quote": QUOTE}]
        work = CaseWork(case=CASE, files=FILES, base_workflow=FIXTURE)
        confirm_facts(ScriptedModel([]), work)
        # routing established it, every reading agreed, and the source checker did not accept it
        work.facts["legal_area"] = {"fact": "legal_area", "status": "established", "value": "tenancy_defect", "agreed": True,
                                    "citations": work.located(cite)[0], "verdict": "rejected", "by": "routing"}
        # the lead's retry pass asks the claim reader to record the rejected facts again
        recorded = []
        team = CaseTeam(ScriptedModel([]))
        team._delegate = lambda w, state, agent, instruction: recorded.append(
            _record_fact(w, agent, {"fact": "legal_area", "status": "established", "value": "loan", "citations": cite})) if agent == "claim_reader" else None
        team._retry_rejected(work, {"delegations": 0})
        self.assertEqual([r["accepted"] for r in recorded], [False])
        self.assertEqual((work.facts["legal_area"]["value"], work.facts["legal_area"]["by"]), ("tenancy_defect", "routing"))

    def test_an_agent_must_report_on_its_last_turn(self):
        from casepath.agents.team import CaseWork, run_agent
        work = CaseWork(case=CASE, files=FILES, base_workflow=FIXTURE)
        model = ScriptedModel([[("list_files", {})], [("list_files", {})], [report("document_finder")]])
        run_agent(model, work, "document_finder", "Find.", max_turns=3)
        self.assertEqual(model.tool_choices, ["required", "required", {"type": "function", "name": "report"}])
        # At its turn limit the agent ends with what it has recorded, and the work names the limit.
        work = CaseWork(case=CASE, files=FILES, base_workflow=FIXTURE)
        self.assertIsNone(run_agent(ScriptedModel([[("list_files", {})]] * 2), work, "document_finder", "Find.", max_turns=2))
        self.assertEqual([(x["agent"], x["reason"]) for x in work.limits], [("document_finder", "turn_limit")])
        # A need the finder never recorded stays requested and is marked not checked.
        rows = work.evaluate()["documents"]
        self.assertEqual({(d["status"], d.get("not_checked")) for d in rows}, {("missing", True)})
        self.assertTrue([a for a in work.evaluate()["next_actions"] if a["kind"] == "obtain"])

    def test_a_finder_that_stops_without_reporting_keeps_unrecorded_needs_requested_and_not_checked(self):
        from casepath.agents.team import CaseWork, run_agent
        from casepath.agents import core
        work = CaseWork(case=CASE, files=FILES, base_workflow=FIXTURE)
        absent = ("record_document", {"document": "notice_letter", "status": "absent", "files": [], "citations": [], "note": ""})
        model = ScriptedModel([[absent], [], []])  # records one need, then stops twice without calling a tool
        self.assertIsNone(run_agent(model, work, "document_finder", "Find."))
        self.assertEqual(work.limits[0]["reason"], "no_report")
        rows = {d["document"]: (d["status"], d.get("not_checked", False)) for d in work.evaluate()["documents"]}
        self.assertEqual(rows["notice_letter"], ("missing", False))  # recorded as absent
        self.assertEqual(rows["customer_message"], ("missing", True))  # never looked at: still requested, not checked
        # The case view evaluates the stored result the same way.
        work.result = None
        from casepath.agents.team import finalize
        result = finalize(work)
        view = core.evaluate(FIXTURE, [], [], result, "c1")["evaluation"]
        self.assertEqual({d["document"]: (d["status"], d.get("not_checked", False)) for d in view["documents"]}, rows)

    def test_a_stop_on_the_retry_pass_does_not_mark_needs_the_first_pass_looked_at(self):
        from casepath.agents.team import CaseWork, run_agent
        work = CaseWork(case=CASE, files=FILES, base_workflow=FIXTURE)
        absent = ("record_document", {"document": "notice_letter", "status": "absent", "files": [], "citations": [], "note": ""})
        run_agent(ScriptedModel([[absent, report("document_finder")]]), work, "document_finder", "Find.")
        run_agent(ScriptedModel([[("list_files", {})]] * 2), work, "document_finder", "Again.", max_turns=2)  # the retry pass stops
        self.assertFalse(any(d.get("not_checked") for d in work.evaluate()["documents"]))

    def test_a_report_that_is_too_long_is_told_its_limit(self):
        from casepath.agents.team import CaseWork, run_agent
        work = CaseWork(case=CASE, files=FILES, base_workflow=FIXTURE)
        model = ScriptedModel([[report("document_finder", summary="x" * 900)], [report("document_finder")]])
        run_agent(model, work, "document_finder", "Find.")
        told = json.loads(next(m for m in model.inputs[1] if m.get("type") == "function_call_output")["output"])
        self.assertIn("900 characters; allowed 1 to 800", told["error"])

    def test_a_call_with_missing_or_unexpected_fields_is_told_which(self):
        from casepath.agents.schema import arr, obj, text, validate_result
        schema = obj(shows=arr(obj(item=text(20), citations=arr(text(20)))))
        with self.assertRaises(ValueError) as caught:
            validate_result({"shows": [{"item": "a", "note": "b"}]}, schema)
        self.assertIn("(missing: citations) (unexpected: note)", str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            validate_result({"shows": ["a"]}, schema)
        self.assertIn("$.shows[0]: type differs from schema (expected object)", str(caught.exception))

    def test_a_turn_limit_still_gives_the_checklist_from_what_was_admitted(self):
        script = standard_script(
            finder_calls=[("record_document", {"document": "customer_message", "status": "present", "files": ["f1"],
                                               "citations": [{"file": "f1", "quote": "Subject: Schimmel im Bad"}], "note": ""})],
            result_fields={})[:-2] + [[("evaluate", {})]] * 12
        result = CaseTeam(ScriptedModel(script)).run(case=CASE, files=FILES, workflow=FIXTURE)
        statuses = {d["document"]: d["status"] for d in result["evaluation"]["documents"]}
        self.assertEqual(statuses, {"customer_message": "present", "photo": "missing", "notice_letter": "missing"})
        self.assertEqual(next(f for f in result["facts"] if f["fact"] == "landlord_notified")["verdict"], "accepted")
        self.assertIn({"kind": "turn_limit", "agent": "result_checker",
                       "text": "The result checker did not finish within its turn limit."}, result["warnings"])
        self.assertEqual(result["reply"]["clauses"], [])
        self.assertEqual(result["open_points"], [a["text"] for a in result["evaluation"]["next_actions"]])

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

    def test_a_value_counts_only_when_both_readings_give_it(self):
        from casepath.agents.team import CaseWork, confirm_facts
        work = CaseWork(case=CASE, files=FILES, base_workflow=FIXTURE)
        work.readings = 2  # two readings, as this test describes
        cite = [{"file": "f1", "quote": QUOTE}]
        # Only the second reading finds a value: it does not count; the fact stays open with the quote.
        only_second = ScriptedModel([], second_reading=[{"fact": "landlord_notified", "status": "established", "value": "yes", "citations": cite}])
        self.assertEqual(confirm_facts(only_second, work)["single"], 1)
        row = work.facts["landlord_notified"]
        self.assertEqual((row["status"], row["value"], len(row["citations"])), ("unknown", None, 1))
        self.assertNotIn("landlord_notified", work.accepted_facts())
        # Only the first reading finds a value: the same.
        work.facts["landlord_notified"] = {"fact": "landlord_notified", "status": "established", "value": True, "citations": cite,
                                           "verdict": None, "by": "claim_reader"}
        silent = ScriptedModel([], second_reading=[{"fact": "landlord_notified", "status": "unknown", "value": None, "citations": []}])
        self.assertEqual(confirm_facts(silent, work)["single"], 1)
        self.assertEqual(work.facts["landlord_notified"]["status"], "unknown")
        # Both give it: it stands, for the source checker.
        work.facts["landlord_notified"] = {"fact": "landlord_notified", "status": "established", "value": True, "citations": cite,
                                           "verdict": None, "by": "claim_reader"}
        same = ScriptedModel([], second_reading=[{"fact": "landlord_notified", "status": "established", "value": "ja", "citations": cite}])
        self.assertEqual(confirm_facts(same, work)["agreed"], 1)
        self.assertEqual((work.facts["landlord_notified"]["status"], work.facts["landlord_notified"]["value"]), ("established", True))
        # They give different values: a person settles it.
        work.facts["landlord_notified"]["verdict"] = "accepted"
        other = ScriptedModel([], second_reading=[{"fact": "landlord_notified", "status": "established", "value": "no", "citations": cite}])
        self.assertEqual(confirm_facts(other, work)["differed"], 1)
        row = work.facts["landlord_notified"]
        self.assertEqual((row["status"], row["second_value"]), ("conflicting", False))
        self.assertNotIn("landlord_notified", work.accepted_facts())

    def test_both_readings_judge_every_condition_in_the_same_form(self):
        from casepath.agents.team import CONFIRM, READ_FACTS, CaseWork, confirm_facts, read_facts
        self.assertEqual(READ_FACTS, CONFIRM)  # the same question, put the same way, twice
        self.assertIn("never false", READ_FACTS)
        self.assertIn("we do not know whether", READ_FACTS)  # a stated doubt is open
        self.assertIn("not_stated: the\nfiles do not address the matter", READ_FACTS)  # silence is a separate answer
        self.assertIn("YYYY-MM-DD", READ_FACTS)  # dates in the form the fact type accepts
        work = CaseWork(case=CASE, files=FILES, base_workflow=FIXTURE)
        work.readings = 2  # two readings, as this test describes
        model = ScriptedModel([], first_reading=[{"fact": "landlord_notified", "status": "unknown", "value": None,
                                                  "citations": [{"file": "f1", "quote": VENT}]}])
        calls = []
        original = model.respond_json
        model.respond_json = lambda **kw: calls.append(kw) or original(**kw)
        read_facts(model, work)
        confirm_facts(model, work)
        first, second = (json.loads(c["instructions"].split("Conditions:\n", 1)[1]) for c in calls)
        self.assertEqual(list(first), ["legal_area", "landlord_notified"])  # every condition, not only those explored
        self.assertEqual(list(second), list(first))  # every condition, in the same order: its own request (another name)
        self.assertNotEqual(calls[0]["name"], calls[1]["name"])
        self.assertIn("deciding which documents to request", calls[0]["instructions"])
        self.assertIn(f"The case is a {FIXTURE['title']}.", calls[0]["instructions"])
        self.assertTrue(calls[0]["input"][0]["content"].startswith("CASE:\n[file message.eml]"))  # the files are the message
        self.assertEqual({c["effort"] for c in calls}, {"low"})
        row = calls[0]["schema"]["properties"]["conditions"]["items"]["properties"]
        self.assertEqual(row["verdict"]["enum"], ["true", "false", "open", "not_stated"])
        # Both readings leave it open and quote the passage that raises it.
        self.assertEqual((work.facts["landlord_notified"]["status"], len(work.facts["landlord_notified"]["citations"])), ("unknown", 2))

    def test_a_verdict_whose_quotation_is_not_found_is_asked_for_once_more(self):
        from casepath.agents.team import CaseWork, read_facts
        work = CaseWork(case=CASE, files=FILES, base_workflow=FIXTURE)
        model = ScriptedModel([], first_reading=[{"fact": "landlord_notified", "status": "established", "value": "yes",
                                                  "citations": [{"file": "f1", "quote": "Ich habe ... informiert."}]}])
        model.retries["casepath_read_facts"] = {"conditions": [{"id": "landlord_notified", "verdict": "true", "value": None, "quote": QUOTE}]}
        read_facts(model, work)
        self.assertEqual((work.facts["landlord_notified"]["status"], work.facts["landlord_notified"]["value"]), ("established", True))

    def test_whole_runs_where_the_two_readings_differ(self):
        """The agreement rule in full team runs: the second reading does not echo the first."""
        def run(first, second):
            script = standard_script(finder_calls=[], result_fields={})
            script = [t for t in script if not (t and t[0][0] == "record_fact")]  # the readings are given below
            model = ScriptedModel(script, first_reading=first, second_reading=second)
            result = CaseTeam(model).run(case=CASE, files=FILES, workflow=FIXTURE)
            return next((f for f in result["facts"] if f["fact"] == "landlord_notified"), None), result
        yes = {"fact": "landlord_notified", "status": "established", "value": "yes", "citations": [{"file": "f1", "quote": QUOTE}]}
        no = {**yes, "value": "no"}
        open_ = {"fact": "landlord_notified", "status": "unknown", "value": None, "citations": []}
        fact, result = run([yes], [no])  # true against false: a person decides
        self.assertEqual(fact["status"], "conflicting")
        self.assertEqual(result["evaluation"]["current"]["step"], "notice")
        fact, result = run([yes], [open_])  # true against unresolved: open, both readings kept
        self.assertEqual((fact["status"], fact["readings"]), ("unknown", [True, None]))
        fact, result = run([yes], [])  # the second reading omits it: open
        self.assertEqual(fact["status"], "unknown")
        fact, result = run([yes], [yes])  # both give it
        self.assertEqual((fact["status"], fact["verdict"]), ("established", "accepted"))
        self.assertEqual(result["evaluation"]["outcome"]["id"], "reported")

    def test_a_condition_a_reading_answers_twice_differently_is_unresolved_and_a_failed_reading_is_a_warning(self):
        from casepath.agents.azure_model import ModelError, ModelResult
        from casepath.agents.team import CaseWork, _reading, confirm_facts, finalize

        class Twice:
            def respond_json(self, **kw):
                rows = [{"id": "landlord_notified", "verdict": "true", "value": None, "quote": QUOTE},
                        {"id": "landlord_notified", "verdict": "false", "value": None, "quote": QUOTE}]
                return ModelResult(value={"conditions": rows}, usage={}, deployment="d", response_id="x", attempts=1, seconds=0)
        work = CaseWork(case=CASE, files=FILES, base_workflow=FIXTURE)
        facts = [f for f in work.graph["facts"] if f["id"] == "landlord_notified"]
        schema_items = []
        original = Twice.respond_json
        Twice.respond_json = lambda self, **kw: schema_items.append(kw["schema"]["properties"]["conditions"]["maxItems"]) or original(self, **kw)
        self.assertEqual(_reading(Twice(), work, name="casepath_confirm_facts", instructions="x", facts=facts, effort="low"),
                         {"landlord_notified": ("unknown", None, [])})
        self.assertEqual(schema_items, [2])  # a repeated condition does not break the schema

        class Failing:
            def respond_json(self, **kw):
                raise ModelError("timeout", "The model did not answer in time.")
        work.facts["landlord_notified"] = {"fact": "landlord_notified", "status": "established", "value": True,
                                           "citations": work.located([{"file": "f1", "quote": QUOTE}])[0], "verdict": None, "by": "claim_reader"}
        confirm_facts(Failing(), work)
        self.assertEqual(work.facts["landlord_notified"]["status"], "unknown")  # one reading only: the value does not count
        work.result = None
        self.assertIn("reading_failed", [w["kind"] for w in finalize(work)["warnings"]])

    def test_a_value_established_at_routing_and_a_different_reading_conflict(self):
        from casepath.agents.team import CaseWork, _record_fact, read_facts
        cite = [{"file": "f1", "quote": QUOTE}]
        for path in ("reading", "agent"):
            work = CaseWork(case=CASE, files=FILES, base_workflow=FIXTURE)
            work.facts["legal_area"] = {"fact": "legal_area", "status": "established", "value": "tenancy_defect",
                                        "citations": work.located(cite)[0], "verdict": None, "by": "routing"}
            if path == "reading":
                read_facts(ScriptedModel([], first_reading=[{"fact": "legal_area", "status": "established", "value": "loan", "citations": cite}]), work)
            else:  # a long dossier is read by the agent
                _record_fact(work, "claim_reader", {"fact": "legal_area", "status": "established", "value": "loan", "citations": cite})
            row = work.facts["legal_area"]
            self.assertEqual((row["status"], row["value"], row["second_value"]), ("conflicting", "tenancy_defect", "loan"), path)

    def test_a_false_verdict_counts_when_both_readings_give_it_with_a_quote(self):
        from casepath.agents.team import CaseWork, confirm_facts, read_facts
        work = CaseWork(case=CASE, files=FILES, base_workflow=FIXTURE)
        no = [{"fact": "landlord_notified", "status": "established", "value": "no", "citations": [{"file": "f1", "quote": QUOTE}]}]
        model = ScriptedModel([], first_reading=no, second_reading=no)
        read_facts(model, work)
        confirm_facts(model, work)
        self.assertEqual((work.facts["landlord_notified"]["status"], work.facts["landlord_notified"]["value"]), ("established", False))

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

    def test_a_need_the_process_builder_adds_from_the_law_is_a_suggestion_with_its_basis(self):
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
        # It waits for the workflow, Knowledge or a handler to confirm it: shown with its basis, never counted as missing.
        self.assertEqual((row["title"], row["required"], row["status"], row["legal_basis"]), ("Mietvertrag", "suggested", "missing", "Art. 253 OR"))
        self.assertNotIn("e-pb1", [a.get("document") for a in result["evaluation"]["next_actions"]])
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
        script[7].insert(1, ("record_fact", {"fact": "frist", "status": "established", "value": "2025-03-15",
                                             "citations": [{"file": "f1", "quote": "Bitte beheben Sie den Mangel bis zum 15. März 2025."}]}))
        result = CaseTeam(ScriptedModel(script)).run(case=CASE, files=files, workflow=workflow)
        self.assertEqual(result["case_summary"], [{"field": "gegenpartei", "label": "Gegenpartei", "text": "Immo Aare AG, Bern"}])
        self.assertEqual(result["deadlines"], [{"fact": "frist", "question": "Welche Frist gilt?", "date": "2025-03-15"}])


class ChecklistScopeTests(unittest.TestCase):
    def test_a_checklist_only_run_gives_the_full_runs_checklist_from_the_same_findings(self):
        fact = [{"fact": "landlord_notified", "status": "established", "value": "yes", "citations": [{"file": "f1", "quote": QUOTE}]}]
        finder = [("record_document", {"document": "customer_message", "status": "present", "files": ["f1"],
                                       "citations": [{"file": "f1", "quote": "Subject: Schimmel im Bad"}], "note": ""}),
                  ("record_document", {"document": "notice_letter", "status": "absent", "files": [], "citations": [], "note": ""})]
        full_script = [t for t in standard_script(finder_calls=finder, result_fields={}) if not (t and t[0][0] == "record_fact")]
        full = CaseTeam(ScriptedModel(full_script, first_reading=fact, second_reading=fact)).run(case=CASE, files=FILES, workflow=FIXTURE)
        model = ScriptedModel([[*finder, report("document_finder")]], first_reading=fact, second_reading=fact)
        only = CaseTeam(model, scope="checklist").run(case=CASE, files=FILES, workflow=FIXTURE)
        rows = lambda r: [(d["document"], d["required"], d["status"]) for d in r["evaluation"]["documents"]]
        self.assertEqual(rows(only), rows(full))
        self.assertEqual(only["evaluation"]["outcome"], full["evaluation"]["outcome"])
        self.assertEqual({s["agent"] for s in only["skipped"]}, {"claim_reader", "process_builder", "result_checker", "source_checker"})
        self.assertNotIn("skipped", full)
        self.assertEqual(only["answer_code"], "checklist_only")
        self.assertFalse(any("propose_change" in tools or "evaluate" in tools for tools in model.tools))  # no builder, no result checker

    def test_a_one_file_case_skips_the_document_finder_and_says_why(self):
        fact = [{"fact": "landlord_notified", "status": "established", "value": "yes", "citations": [{"file": "f1", "quote": QUOTE}]}]
        model = ScriptedModel([], first_reading=fact, second_reading=fact)
        result = CaseTeam(model, scope="checklist").run(case=CASE, files=FILES[:1], workflow=FIXTURE)
        reasons = {s["agent"]: s["reason"] for s in result["skipped"]}
        self.assertIn("one file", reasons["document_finder"])
        self.assertEqual(model.tools, [])  # no agent turn at all: routing aside, only the two readings ran
        self.assertEqual(next(f for f in result["facts"] if f["fact"] == "landlord_notified")["verdict"], "accepted")
        self.assertIn("source_checker", reasons)  # the fact check is skipped: agreement decides
        self.assertEqual({d["status"] for d in result["evaluation"]["documents"]}, {"missing"})

    def test_the_setting_is_off_by_default_and_named_in_the_parity_manifest(self):
        from casepath.config import load_settings, SettingsError
        from casepath.parity import non_default_settings
        self.assertEqual(load_settings({}).run_scope, "full")
        self.assertNotIn("run_scope", json.dumps(non_default_settings(load_settings({}))))
        self.assertIn("run_scope", json.dumps(non_default_settings(load_settings({"CASEPATH_RUN_SCOPE": "checklist"}))))
        with self.assertRaises(SettingsError):
            load_settings({"CASEPATH_RUN_SCOPE": "fast"})


class ChecklistScopeFixupTests(unittest.TestCase):
    def test_with_active_knowledge_the_process_builder_runs_and_a_one_file_dossier_is_searched(self):
        from casepath.agents.team import CaseWork
        item = kb.set_status(kb.new_item("example-defect", "document_need", {"title": "Ventilation record", "why": "Shows ventilation.", "step": "assess"},
                                         origin={"kind": "case", "by": "test", "case_id": "c0"}), "active", by="expert")
        team = CaseTeam(ScriptedModel([]), scope="checklist")
        with_knowledge = CaseWork(case=CASE, files=FILES, base_workflow=FIXTURE, knowledge=[item])
        self.assertNotIn("process_builder", [s["agent"] for s in team._skipped(with_knowledge)])
        plain = CaseWork(case=CASE, files=FILES, base_workflow=FIXTURE)
        self.assertIn("process_builder", [s["agent"] for s in team._skipped(plain)])
        dossier = CaseWork(case=CASE, files=[{**FILES[0], "segments": [{"first_page": 1, "last_page": 2, "title": "Brief"}]}], base_workflow=FIXTURE)
        self.assertNotIn("document_finder", [s["agent"] for s in team._skipped(dossier)])
        single = CaseWork(case=CASE, files=FILES[:1], base_workflow=FIXTURE)
        self.assertIn("document_finder", [s["agent"] for s in team._skipped(single)])


class ReadingsSettingTests(unittest.TestCase):
    def test_a_value_counts_only_when_every_reading_gives_it(self):
        from casepath.agents.team import CaseWork, confirm_facts, read_facts
        cite = [{"file": "f1", "quote": QUOTE}]
        yes = [{"fact": "landlord_notified", "status": "established", "value": "yes", "citations": cite}]
        silent = [{"fact": "landlord_notified", "status": "unknown", "value": None, "citations": []}]

        class Third(ScriptedModel):  # the third reading leaves it open
            def respond_json(self, **kw):
                if kw["name"] == "casepath_confirm_facts_2":
                    self.second_reading = silent
                return super().respond_json(**kw)
        for readings, model, expected in ((3, ScriptedModel([], first_reading=yes, second_reading=yes), "established"),
                                          (3, Third([], first_reading=yes, second_reading=yes), "unknown"),
                                          (2, Third([], first_reading=yes, second_reading=yes), "established")):
            work = CaseWork(case=CASE, files=FILES, base_workflow=FIXTURE)
            work.readings = readings
            read_facts(model, work)
            confirm_facts(model, work)
            self.assertEqual(work.facts["landlord_notified"]["status"], expected, (readings, type(model).__name__))

    def test_the_setting_defaults_to_three_and_is_named_in_the_parity_manifest(self):
        from casepath.config import SettingsError, load_settings
        from casepath.parity import non_default_settings
        self.assertEqual(load_settings({}).readings, 3)
        self.assertIn("readings", json.dumps(non_default_settings(load_settings({"CASEPATH_READINGS": "2"}))))
        with self.assertRaises(SettingsError):
            load_settings({"CASEPATH_READINGS": "1"})
