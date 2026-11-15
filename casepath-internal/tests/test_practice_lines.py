"""The first request of the area observed in practice keeps the lines practice supports, as observed.

In an area whose lines carry practice counts (the tenancy-defect area), the first request's ticked lines are exactly
those practice supports; a line from another mechanism (a key point's advice, a template for the customer's own letter, a
cover question) is offered unticked. Proof: the first request rendered for synthetic tenancy-defect cases under the
current process and under the frozen one from before the areas were split (2026-11-12.5), compared line by line. In an
area written from the law alone (the loan area) advice is still ticked when its condition holds.
"""
import copy
import json
import re
import unittest
from pathlib import Path

from casepath.agents import core
from casepath.process import area, letters, workflows
from casepath.process.items import build_items
from casepath.quality.handler import knowledge

FROZEN = json.loads((Path(__file__).parent / "fixtures" / "areas" / "mietmangel-handler.2026-11-12.5.json").read_text())
CASE = {"id": "case_example", "title": "Schimmel (synthetisch) 1234.5678.9012", "intake": {}}
FILES = [{"name": "Schadenmeldung.pdf", "extraction": {"cut_of": {"as_of": "2025-02-07"}, "segments": [{"date": "18.10.2024"}]}}]


def fact(fid, value):
    return {"fact": fid, "status": "established", "verdict": "accepted", "value": value, "citations": []}


def present(did):
    return {"document": did, "status": "present", "verdict": "accepted", "files": ["f"], "citations": []}


AREA = fact("rechtsgebiet", "Mietrecht / Mangel")
# The synthetic tenancy-defect cases of the existing tests, each with different facts established
CASES = {
    "written notice, no damages, rent not disputed": ([AREA, fact("maengelruege_schriftlich", True), fact("will_schadenersatz", False),
                                                       fact("streit_mietzins", False)], [present("mietvertrag")]),
    "defect reported, form open": ([AREA, fact("mangel_gemeldet", True)], []),
    "written notice in the file": ([AREA, fact("maengelruege_schriftlich", True)], [present("maengelruege")]),
    "reduction wanted, defect reported": ([AREA, fact("will_reduktion", True), fact("mangel_gemeldet", True)], []),
    "no written notice, reduction and repair wanted, defect persists": (
        [AREA, fact("maengelruege_schriftlich", False), fact("will_reduktion", True), fact("will_beseitigung", True), fact("mangel_besteht", True)], []),
}

# The differences in ticked lines introduced deliberately since the frozen process, each pinned by its own test:
# 1. the correspondence line reads «Weitere Korrespondenz … (über die vorliegenden Schreiben hinaus)» when part of it is
#    in the file (test_key_points), where it read «Sämtliche Korrespondenz …»;
# 2. the greeting (test_letters), compared apart from the lines;
# 3. a line for a date or hearing a court, an authority or the other side set, from the file («Wir haben vermerkt: …»);
# 4. a statutory deadline line («Gesetzliche Frist …», «Möglicherweise läuft …», «Termin der Gegenpartei …»).
ALLOWED = ("correspondence", "greeting", "set date", "deadline")
FURTHER = re.compile(r"^– Weitere (.+) \(über die vorliegenden Schreiben hinaus\)$")


def ticked(workflow, facts, documents):
    """The first request's ticked lines: documents, questions, hints (text and article), as the letter gives them."""
    result = {"facts": facts, "documents": documents, "brief": {"request": "Schimmel.", "parties": [], "timeline": []}}
    state = core.evaluate(workflow, knowledge(workflow), [], result, "c", files=FILES)
    items = build_items(state, result, FILES)
    action = next(i for i in items if i["kind"] == "next_action")
    ctx = letters.context(CASE, items, [], {"due": "2025-03-01"}, files=FILES, evaluation=state["evaluation"], process=state["process"])
    hints = [(i["value"], i.get("legal_basis")) for i in items if i["kind"] == "hint" and i.get("stated_as") != "put_to_handler"]
    deadlines = [letters.statutory(i) for i in items if i["kind"] == "deadline" and i.get("origin") == "law" and not i.get("missing")]
    dates = [x for x in (letters.set_date_line(i) for i in items if i["kind"] == "deadline") if x]
    return {"action": action["action"], "documents": ctx["liste"].splitlines(),
            "questions": [i["value"] for i in items if i["kind"] == "letter_question" and i.get("ask") != "proposed"],
            "hints": hints, "deadlines": deadlines, "set dates": dates, "greeting": ctx["anrede"], "letter": ctx["hinweise"]}


def allowed(old, new):
    """The current lines with the allowed differences taken back to the frozen form: [(kind, line)]."""
    docs = [f"– Sämtliche {m.group(1)}" if (m := FURTHER.match(d)) else d for d in new["documents"]]
    return {"action": new["action"], "documents": docs, "questions": new["questions"], "hints": new["hints"],
            "extra": new["deadlines"] + new["set dates"]}


class PracticeFirstRequestTests(unittest.TestCase):
    def setUp(self):
        self.old = workflows.validate_workflow(copy.deepcopy(FROZEN))
        self.new = area.workflow("mietmangel-handler")

    def test_the_ticked_lines_of_the_first_request_are_those_of_the_frozen_process_but_for_the_named_differences(self):
        self.assertEqual(ALLOWED, ("correspondence", "greeting", "set date", "deadline"))
        for name, (facts, documents) in CASES.items():
            with self.subTest(case=name):
                old, new = ticked(self.old, facts, documents), ticked(self.new, facts, documents)
                self.assertEqual((old["action"], new["action"]), ("A1", "A1"))
                kept = allowed(old, new)
                self.assertEqual(kept["documents"], old["documents"])
                self.assertEqual(kept["questions"], old["questions"])
                self.assertEqual(kept["hints"], old["hints"])  # each hint's text and article, in order
                self.assertEqual(old["deadlines"] + old["set dates"], [])  # the frozen process had no statutory deadlines
                self.assertTrue(all(line.startswith(("Gesetzliche Frist", "Möglicherweise läuft", "Termin der Gegenpartei", "Wir haben vermerkt:"))
                                    for line in kept["extra"]), kept["extra"])

    def test_the_fault_on_the_deployed_product_does_not_return(self):
        facts, documents = CASES["no written notice, reduction and repair wanted, defect persists"]
        new = ticked(self.new, facts, documents)
        self.assertEqual([k for _, k in new["hints"]], ["Art. 257g OR", "Art. 259d OR"])
        self.assertIn("die Mängelrüge erfolgt zu Beweiszwecken idealerweise per Einschreiben (Art. 257g OR).", new["letter"])
        self.assertIn("bitte dokumentieren Sie ihn fortlaufend (z.B. mit Fotos) (Art. 259d OR).", new["letter"])
        self.assertNotIn("Herabsetzung des Mietzinses ab dem Zeitpunkt", new["letter"])
        self.assertNotIn("hinterlegen", new["letter"])
        # the advice that says the same as an observed hint is not added a second time; the deposit is offered only
        result = {"facts": facts, "documents": documents, "brief": {"request": "", "parties": [], "timeline": []}}
        listed = {i["item_id"]: i for i in build_items(core.evaluate(self.new, knowledge(self.new), [], result, "c", files=FILES), result, FILES)}
        self.assertNotIn("hint:kp-meldung", listed)
        self.assertNotIn("hint:kp-reduktion", listed)
        self.assertEqual(listed["hint:kp-hinterlegung"]["stated_as"], "put_to_handler")  # «Weitere Vorschläge»
        self.assertEqual(listed["letter_question:ursache_datum"]["ask"], "proposed")  # the cover question: offered

    def test_a_line_practice_shows_in_the_areas_data_is_ticked(self):
        wf = copy.deepcopy(self.new)
        next(p for p in wf["key_points"] if p["id"] == "hinterlegung")["source_refs"] = ["practice#5of7"]
        facts, documents = CASES["no written notice, reduction and repair wanted, defect persists"]
        result = {"facts": facts, "documents": documents, "brief": {"request": "", "parties": [], "timeline": []}}
        listed = {i["item_id"]: i for i in build_items(core.evaluate(wf, [], [], result, "c", files=FILES), result, FILES)}
        self.assertEqual(listed["hint:kp-hinterlegung"]["stated_as"], "established")


class LawOnlyAdviceTests(unittest.TestCase):
    def test_in_the_loan_area_the_advice_is_ticked_when_its_condition_holds(self):
        wf = area.workflow("vertrag-darlehen")
        self.assertFalse(wf["area"]["practice"])
        result = {"facts": [fact("rechtsgebiet", "Vertragsrecht / Darlehen"), fact("rueckforderung_schriftlich", False)], "documents": [],
                  "brief": {"request": "Darlehen nicht zurückbezahlt.", "parties": [], "timeline": []}}
        state = core.evaluate(wf, [], [], result, "c")
        items = build_items(state, result)
        listed = {i["item_id"]: i for i in items}
        self.assertEqual(listed["key_point:schriftlich_fordern"]["value"], "applies")
        self.assertEqual(listed["hint:kp-schriftlich_fordern"]["stated_as"], "established")
        self.assertNotIn("hint:aufforderung", listed)  # it stands for the area's hint that says the same
        text = letters.render("A1", wf["forms"], letters.context(CASE, items, [], {"due": "2026-12-05"}, evaluation=state["evaluation"], process=state["process"]))[0]
        self.assertIn("Sie können das Darlehen schriftlich zurückfordern", text)
        self.assertIn("(Art. 318 OR).", text)


if __name__ == "__main__":
    unittest.main()
