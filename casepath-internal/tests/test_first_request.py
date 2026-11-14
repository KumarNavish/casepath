"""The first request asks; a letter never renders empty; a deadline whose trigger is not settled stays; what a fact is not.

Rules from the out-of-the-box run on synthetic cases (scripted, no model): an empty first request, a deadline lost with a
rejected or conflicting trigger date, near-misses in what a fact means, a document the other side has not issued, a
statutory period read into a deadline fact, and the practice count as a need's tag.
"""
import json
import unittest

from casepath.agents import core
from casepath.agents.team import CaseWork, _dispatch, _record_fact, confirm_facts, run_source_checker
from casepath.process import area, letters
from casepath.process.items import build_items
from tests.scripted import ScriptedModel

CASE = {"id": "case_x", "title": "Synthetischer Fall 1111.2222.3333", "intake": {}}


def fact(fid, value, **extra):
    return {"fact": fid, "status": "established", "verdict": "accepted", "value": value, "citations": [], **extra}


def present(did):
    return {"document": did, "status": "present", "verdict": "accepted", "files": ["f"], "citations": []}


def prepared(wid, facts, documents=(), files=None):
    wf = area.workflow(wid)
    result = {"facts": [fact("rechtsgebiet", wf["applies_when"]["is"])] + list(facts), "documents": list(documents),
              "brief": {"request": "", "parties": [], "timeline": []}}
    state = core.evaluate(wf, [], [], result, "c", files=files)
    items = build_items(state, result, files)
    return wf, state, items, {i["item_id"]: i for i in items}


def draft(wf, state, items, events=()):
    action = next(i for i in items if i["kind"] == "next_action")
    kind = action.get("form") or action["action"]
    return letters.render(kind, wf["forms"], letters.context(CASE, items, list(events), {"due": "2026-12-05"},
                                                             evaluation=state["evaluation"], process=state["process"]))


# A loan whose file holds everything the clarifying stage needs, with every question to the customer answered.
LOAN_COMPLETE = [fact("schriftlich", True), fact("termin_vereinbart", False), fact("zins", "zinslos"), fact("rueckforderung_schriftlich", True),
                 fact("aufforderung", "2026-08-21")]
LOAN_DOCS = [present(d) for d in ("darlehensvertrag", "auszahlungsbeleg", "kuendigung_rueckforderung", "korrespondenz")]


class EmptyLetterTests(unittest.TestCase):
    def test_no_form_of_any_area_renders_empty_when_there_is_nothing_to_ask(self):
        for wf in area.shipped():
            for ctx in (letters.context(CASE, [], [], None), {k: "" for k in letters.context(CASE, [], [], None)}):
                for kind, form in wf["forms"].items():
                    if kind.startswith("_"):
                        continue
                    with self.subTest(area=wf["id"], kind=kind):
                        text, reason = letters.render(kind, wf["forms"], ctx)
                        self.assertTrue((text and text.strip()) or (text is None and reason and reason.strip()))
            self.assertEqual(letters.render("A1", wf["forms"], letters.context(CASE, [], [], None)), (None, wf["forms"]["A1"]["empty"]))

    def test_with_nothing_to_ask_the_clarifying_stage_is_complete_and_the_assessment_follows(self):
        wf, state, items, listed = prepared("vertrag-darlehen", LOAN_COMPLETE, LOAN_DOCS)
        self.assertIs(state["facts"]["nichts_anzufordern"], True)
        self.assertEqual(state["evaluation"]["current"]["step"], "beurteilen")
        self.assertIn("Nichts anzufordern", [r.get("via") for r in state["evaluation"]["path"]])
        self.assertEqual(listed["next_action:0"]["action"], "A5")  # the assessment, waiting for the cover decision
        klaeren = next(s for s in wf["steps"] if s["id"] == "klaeren")
        self.assertTrue(next(e for e in klaeren["next"] if e.get("label") == "Nichts anzufordern")["without_action"])
        # one open question to the customer: the first request is still the next action, and it asks
        wf, state, items, listed = prepared("vertrag-darlehen", LOAN_COMPLETE[:2] + LOAN_COMPLETE[3:], LOAN_DOCS)
        self.assertIs(state["facts"]["nichts_anzufordern"], False)
        self.assertEqual(listed["next_action:0"]["action"], "A1")
        # a first request already sent: the stage's own rules govern, not this way out
        wf, state, items, listed = prepared("vertrag-darlehen", LOAN_COMPLETE + [fact("handlung_a1", "2026-09-01")], LOAN_DOCS)
        self.assertNotIn("Nichts anzufordern", [r.get("via") for r in state["evaluation"]["path"]])

    def test_without_documents_the_first_request_asks_the_questions_and_announces_no_empty_list(self):
        wf, state, items, listed = prepared("vertrag-darlehen", [fact("schriftlich", True), fact("termin_vereinbart", False),
                                                                 fact("rueckforderung_schriftlich", True)], LOAN_DOCS)
        text, none = draft(wf, state, items)
        self.assertIsNone(none)
        self.assertNotIn("brauchen wir insbesondere noch", text)
        self.assertNotIn("allfällige weitere relevante Unterlagen", text)
        self.assertIn("Weiter bitten wir Sie um die Beantwortung folgender Fragen:", text)
        self.assertIn(f"– {listed['letter_question:zins']['value']}", text)
        self.assertIn(f"– {listed['letter_question:aufforderung']['value']}", text)
        self.assertIn("Art. 318 OR", text)  # the hint and the deadline line

    def test_offered_lines_alone_never_make_a_letter(self):
        facts = [f for f in LOAN_COMPLETE if f["fact"] != "schriftlich"]  # every question answered but the offered one
        wf, state, items, listed = prepared("vertrag-darlehen", facts, LOAN_DOCS)
        self.assertIs(state["facts"]["nichts_anzufordern"], True)  # an offered question does not hold the stage
        self.assertEqual(listed["next_action:0"]["action"], "A5")
        # a first request whose one asked line the handler unticked: the offered lines left do not make a letter
        facts = [f for f in facts if f["fact"] != "zins"]
        wf, state, items, listed = prepared("vertrag-darlehen", facts, LOAN_DOCS)
        self.assertEqual((listed["letter_question:zins"]["ask"], listed["letter_question:schriftlich"]["ask"]), ("now", "proposed"))
        render = lambda events: letters.render("A1", wf["forms"], letters.context(CASE, items, events, None, evaluation=state["evaluation"],
                                                                                   process=state["process"]))
        unticked = [{"kind": "letter.line", "item_id": "letter_question:zins", "included": False}]
        self.assertEqual(render(unticked), (None, wf["forms"]["A1"]["empty"]))
        text, _ = render(unticked + [{"kind": "letter.line", "item_id": "letter_question:schriftlich", "included": True}])
        self.assertIn(listed["letter_question:schriftlich"]["value"], text)  # once the handler ticks it, it is asked


class UnsettledTriggerTests(unittest.TestCase):
    def test_a_rejected_trigger_date_shows_the_deadline_as_possible_and_asks_the_date(self):
        rejected = {**fact("aufforderung", "2026-08-21"), "verdict": "rejected"}
        wf, state, items, listed = prepared("vertrag-darlehen", [fact("termin_vereinbart", False), rejected])
        row = listed["deadline:rueckzahlung"]
        self.assertEqual((row["value"], row["stated_as"], row["candidate"]), ("prüfen", "possible", "2026-10-02"))
        self.assertIn("Datum prüfen", row["rule"])
        self.assertEqual(listed["letter_question:aufforderung"]["ask"], "now")
        text, _ = draft(wf, state, items)
        self.assertIn("Möglicherweise läuft ein Termin der Gegenpartei «Rückzahlung des Darlehens ohne vereinbarten Termin»", text)
        self.assertIn("02.10.2026", text)
        self.assertIn(f"– {listed['letter_question:aufforderung']['value']}", text)

    def test_a_conflicting_trigger_date_keeps_the_deadline_and_an_offered_question_is_asked(self):
        conflicting = {"fact": "rueckgabe", "status": "conflicting", "verdict": "not_checked", "value": "2026-05-29",
                       "second_value": "2026-05-31", "citations": []}
        wf, state, items, listed = prepared("miete-kaution", [fact("mietende", "2026-05-31"), conflicting])
        row = listed["deadline:maengelmeldung"]
        self.assertEqual((row["value"], row["stated_as"]), ("prüfen", "possible"))
        self.assertNotIn("candidate", row)  # «sofort» gives no date, only «prüfen»
        self.assertIn("zwei Lesungen", row["rule"])
        self.assertEqual(listed["letter_question:rueckgabe"]["ask"], "now")  # offered by default; here the date is asked
        self.assertEqual(listed["deadline:kaution_bank"]["value"], "2027-05-31")  # the settled one as before


class NearMissTests(unittest.TestCase):
    TEXT = ("Darlehensvertrag. Es kann von beiden Parteien jederzeit mit einer Frist von sechs Wochen schriftlich gekündigt werden. "
            "Hiermit kündige ich das Darlehen und fordere Dich auf, mir den Betrag zurückzuzahlen. Hoi, wie läuft es mit dem Geld?")

    def work(self):
        return CaseWork(case=CASE, files=[{"id": "f1", "name": "akte.txt", "kind": "text", "text": self.TEXT}],
                        base_workflow=area.workflow("vertrag-darlehen"))

    def test_the_nearest_thing_that_does_not_count_reaches_the_reader_the_second_reading_and_the_checker(self):
        work = self.work()
        facts = {f["id"]: f for f in _dispatch(work, "claim_reader", "open_process", {})["process"]["facts"]}
        self.assertIn("wie läuft es mit dem Geld", facts["aufforderung"]["not_this"])
        self.assertIn("Kündigungsklausel", facts["termin_vereinbart"]["not_this"])
        self.assertNotIn("not_this", facts["darlehenssumme"])  # only where a near-miss is plausible: no empty field

        class Recording(ScriptedModel):
            def respond_json(self, *, name, instructions, input, schema, effort="medium"):
                self.seen = getattr(self, "seen", []) + [(name, instructions, input[0]["content"])]
                return super().respond_json(name=name, instructions=instructions, input=input, schema=schema, effort=effort)
        model = Recording([])
        confirm_facts(model, work)
        name, instructions, content = model.seen[-1]
        self.assertIn("not_this", instructions)
        self.assertIn("Nachfrage im Chat", json.dumps(json.loads(content)["facts"], ensure_ascii=False))  # a deciding fact, read twice
        _record_fact(work, "claim_reader", {"fact": "aufforderung", "status": "established", "value": "2026-08-21", "part": None,
                                            "citations": [{"file": "f1", "quote": "Hoi, wie läuft es mit dem Geld?"}]})
        run_source_checker(model, work)
        name, instructions, content = model.seen[-1]
        claim = next(i["claim"] for i in json.loads(content)["items"] if i["item"] == "fact:aufforderung")
        self.assertIn("(not: eine beiläufige Nachfrage", claim)
        self.assertIn('"not:"', instructions)
        self.assertEqual(sum(1 for n, _, _ in model.seen), 2)  # no extra model call

    def test_every_deadline_trigger_and_the_loan_deciding_facts_name_their_near_miss(self):
        for wf in area.shipped():
            facts = {f["id"]: f for f in wf["facts"]}
            for d in wf["deadlines"]:
                with self.subTest(area=wf["id"], trigger=d["trigger"]):
                    self.assertTrue(facts[d["trigger"]].get("not_this"))
        loan = {f["id"]: f for f in area.workflow("vertrag-darlehen")["facts"]}
        for fid in ("termin_vereinbart", "kuendigungsfrist", "aufforderung", "rueckforderung_schriftlich"):
            self.assertTrue(loan[fid].get("not_this"), fid)

    def test_a_notice_clause_is_not_an_agreed_date_the_agreed_period_runs_from_the_notice(self):
        d = area.workflow("vertrag-darlehen")["deadlines"][0]
        self.assertEqual(area.compute_deadline(d, "2026-08-21", {"termin_vereinbart": False, "kuendigungsfrist": "sechs Wochen"})[0], "2026-10-02")
        self.assertEqual(area.compute_deadline(d, "2025-02-10", {"termin_vereinbart": False, "kuendigungsfrist": "3 Monate"})[0], "2025-05-12")
        self.assertEqual(area.compute_deadline(d, "2025-06-02", {"termin_vereinbart": False})[0], "2025-07-14")  # Art. 318 OR: six weeks
        self.assertEqual(area.compute_deadline(d, "2025-06-02", {"termin_vereinbart": False, "kuendigungsfrist": "nach Absprache"})[0], "prüfen")
        self.assertIsNone(area.compute_deadline(d, "2025-06-02", {"termin_vereinbart": True}))  # a fixed date: no period runs

    def test_a_statutory_period_is_never_read_into_the_deadline_fact_nor_shown_as_a_rejected_reading(self):
        work = self.work()
        answer = _record_fact(work, "claim_reader", {"fact": "frist", "status": "established", "value": "6 weeks from 2026-08-21", "part": None,
                                                     "citations": [{"file": "f1", "quote": "Hiermit kündige ich das Darlehen"}]})
        self.assertFalse(answer["accepted"])
        self.assertIn("Rückzahlung des Darlehens", answer["reason"])
        self.assertNotIn("frist", work.facts)
        self.assertFalse([e for e in work.events if e["kind"] == "fact.rejected"])
        # a run stored before: the period read into «frist» and rejected is not listed as a rejected fact
        stored = {**fact("frist", "1 years from 2026-05-31"), "verdict": "rejected"}
        wf, state, items, listed = prepared("miete-kaution", [fact("mietende", "2026-05-31"), stored])
        self.assertEqual((listed["fact:frist"]["value"], listed["fact:frist"]["verdict"], listed["fact:frist"]["stated_as"]), (None, None, "unknown"))
        self.assertEqual(listed["deadline:kaution_bank"]["value"], "2027-05-31")  # the computed deadline is its own item


class OtherSideTests(unittest.TestCase):
    def test_a_document_the_other_side_has_not_issued_is_not_asked_its_question_is(self):
        base = [fact("mietende", "2026-05-31"), fact("forderung_vermieter", True)]  # a deduction announced
        _, _, _, unknown = prepared("miete-kaution", base)
        self.assertEqual(unknown["document:forderungen"]["ask"], "later")
        self.assertEqual(unknown["letter_question:abrechnung_erhalten"]["value"],
                         "Haben Sie von der Vermieterschaft eine Abrechnung oder bezifferte Forderung erhalten?")
        self.assertEqual(unknown["letter_question:abrechnung_erhalten"]["ask"], "now")
        _, _, _, no = prepared("miete-kaution", base + [fact("abrechnung_erhalten", False)])
        self.assertNotIn("document:forderungen", no)
        _, _, _, yes = prepared("miete-kaution", base + [fact("abrechnung_erhalten", True)])
        self.assertEqual(yes["document:forderungen"]["ask"], "now")
        for wid, did, fid in (("arbeit-kuendigung", "begruendung", "grund_genannt"), ("miete-kuendigung", "begruendung", "grund_genannt"),
                              ("allgemein", "fristschreiben", "frist"), ("miete-kaution", "rueckgabeprotokoll", "abnahmeprotokoll")):
            with self.subTest(area=wid, document=did):
                _, _, _, listed = prepared(wid, [])
                self.assertEqual((listed[f"document:{did}"]["ask"], listed[f"letter_question:{fid}"]["ask"]), ("later", "now"))


class PracticeTagTests(unittest.TestCase):
    def test_a_practice_need_carries_its_count_as_its_tag(self):
        from casepath.quality.handler import knowledge
        wf = area.workflow("mietmangel-handler")
        result = {"facts": [fact("rechtsgebiet", "Mietrecht / Mangel"), fact("maengelruege_schriftlich", True)],
                  "documents": [present("maengelruege")], "brief": {"request": "", "parties": [], "timeline": []}}
        listed = {i["item_id"]: i for i in build_items(core.evaluate(wf, knowledge(wf), [], result, "c"), result)}
        korr = listed["document:k-know-seed-mold-korrespondenz--mietmangel-handler"]
        self.assertEqual((korr["practice"], korr["ask"]), ("in 6 von 7 Fällen verlangt", "now"))  # asked although part is in the file
        self.assertEqual(listed["document:mietvertrag"]["practice"], "in 6 von 7 Fällen verlangt")
        self.assertEqual(listed["document:fotos"]["practice"], "in 4 von 7 Fällen verlangt")
        _, _, _, loan = prepared("vertrag-darlehen", [])
        self.assertNotIn("practice", loan["document:darlehensvertrag"])  # from the law alone: no count


if __name__ == "__main__":
    unittest.main()
