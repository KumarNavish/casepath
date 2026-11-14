import json
import tempfile
import unittest
from pathlib import Path

from casepath.agents import core
from casepath.process import area, workflows



def intake():
    return {"format": "casepath.workflow/1", "id": "osm-mold", "version": "1", "title": "Intake", "status": "draft",
            "sources": [{"id": "d", "kind": "process_diagram", "title": "D"}],
            "applies_when": {"fact": "rechtsgebiet", "is": "Mietrecht / Mangel"},
            "facts": [{"id": "rechtsgebiet", "type": "enum", "values": ["Mietrecht / Mangel"], "question": "?", "source_refs": ["d#1"]}],
            "start": "a", "steps": [{"id": "a", "title": "A", "source_refs": ["d#1"], "documents": [], "next": []}], "documents": []}


def fact(fid, value):
    return {"fact": fid, "status": "established", "verdict": "accepted", "value": value, "citations": []}


def document(did):
    return {"document": did, "status": "present", "verdict": "accepted", "files": ["f"], "citations": []}


class HandlerWorkflowTests(unittest.TestCase):
    def test_the_handler_workflow_joins_and_replaces_the_intake_in_routing(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "osm-mold.json").write_text(json.dumps(intake()))
            catalogue = workflows.Catalogue.load(tmp)
            self.assertNotIn("osm-mold", [w["id"] for w in catalogue.routable()])  # the handler's workflow replaces the intake
            self.assertIn("mietmangel-handler", [w["id"] for w in catalogue.routable()])
            self.assertIsNotNone(catalogue.get("osm-mold"))
        with tempfile.TemporaryDirectory() as tmp:  # out of the box: every shipped area, nothing unmapped
            self.assertEqual(len(workflows.Catalogue.load(tmp).routable()), 10)
            self.assertEqual(len(workflows.Catalogue.load(None).routable()), 10)
            (Path(tmp) / "catalogue.json").write_text(json.dumps({"format": "casepath.catalogue/1", "shipped_areas": False}))
            self.assertEqual(workflows.Catalogue.load(tmp).workflows, ())  # a catalogue may opt out

    def test_the_stage_follows_what_was_done_what_arrived_and_the_handlers_cover_decision(self):
        wf = workflows.validate_workflow(area.workflow("mietmangel-handler"))
        base = [fact("rechtsgebiet", "Mietrecht / Mangel"), fact("maengelruege_schriftlich", "ja"), fact("will_schadenersatz", "nein"),
                fact("streit_mietzins", "nein")]
        state = core.evaluate(wf, [], [], {"facts": base, "documents": [document("mietvertrag")]}, "c")
        self.assertEqual(state["evaluation"]["current"]["step"], "klaeren")
        self.assertFalse(state["facts"]["a1_versandt"])
        from casepath.process.items import build_items
        listed = {i["item_id"]: i for i in build_items(state, {"facts": base})}
        self.assertEqual(listed["next_action:0"]["action"], "A1")
        self.assertIn("letter_question:mangel_seit", listed)
        self.assertEqual(listed["letter_question:mangel_seit"]["ask"], "now")  # Protekta asks it (4 of 7)
        self.assertNotIn("letter_question:maengelruege_schriftlich", listed)  # known here: not asked
        bare = [fact("rechtsgebiet", "Mietrecht / Mangel"), fact("mangel_gemeldet", True)]
        state2 = core.evaluate(wf, [], [], {"facts": bare, "documents": []}, "c")
        listed2 = {i["item_id"]: i for i in build_items(state2, {"facts": bare})}
        self.assertEqual(listed2["letter_question:will_schadenersatz"]["ask"], "proposed")  # asked in 0 of 5: offered
        self.assertIn("hint:ruege_einschreiben", listed2)  # notified, form unknown: the hint to repeat it in writing
        self.assertEqual(listed2["document:maengelruege"]["ask"], "now")  # notice not in the file: asked (practice 3 of 5)
        mentioned = {"facts": bare, "brief": {"not_enclosed": [{"title": "Bericht der Fachperson", "mentioned": "E-Mail vom 12.06.2023",
                                                                 "citations": []}]}}
        line = {i["item_id"]: i for i in build_items(state2, mentioned)}["document:mention-0"]
        mine = [{"id": "ed_1", "op": "add_document", "args": {"title": "Wohnungsabnahmeprotokoll", "why": "Steht nicht in den Akten", "step": "klaeren"}}]
        added = core.evaluate(wf, [], mine, {"facts": bare, "documents": []}, "c")
        row = next(i for i in build_items(added, {"facts": bare}) if i["kind"] == "document" and i["label"]["de"] == "Wohnungsabnahmeprotokoll")
        self.assertEqual(row["ask"], "now")  # the handler's own addition is ticked at once; only the agents' guesses are offered
        rejected = {"document": "mietvertrag", "status": "unusable", "verdict": "rejected", "files": ["f"], "citations": [], "note": "x"}
        disputed = core.evaluate(wf, [], [], {"facts": bare, "documents": [rejected]}, "c")
        row = {i["item_id"]: i for i in build_items(disputed, {"facts": bare, "documents": [rejected]})}["document:mietvertrag"]
        self.assertEqual((row["ask"], row["reason"]), ("proposed", "Die Prüfung widerspricht dem Befund «fehlt/unbrauchbar»"))
        expert = core.evaluate(wf, [], [], {"facts": bare + [fact("fachperson_beigezogen", True)], "documents": []}, "c")
        self.assertEqual({i["item_id"]: i for i in build_items(expert, {"facts": bare})}["document:fachbericht"]["ask"], "proposed")
        self.assertEqual((line["ask"], line["reason"]), ("proposed", "in E-Mail vom 12.06.2023 erwähnt, lag nicht bei"))
        twice = {"facts": bare, "brief": {"not_enclosed": [{"title": "Mietvertrag vom 1.4.2020", "mentioned": "", "citations": []}]}}
        self.assertNotIn("document:mention-0", {i["item_id"] for i in build_items(state2, twice)})  # already a need
        self.assertEqual(listed["hint:dokumentieren"]["stated_as"], "put_to_handler")  # offered while a reduction is not established
        self.assertNotIn("hint:ruege_einschreiben", listed)  # a written notice was sent: no hint to send one
        self.assertEqual((listed["fact:a1_versandt"]["value"], listed["fact:a1_versandt"]["stated_as"]), (False, "computed"))  # derived, listed
        done = base + [fact("bisherige_handlungen", "A1 2024-08-28; A4 2024-09-10")]
        state = core.evaluate(wf, [], [], {"facts": done, "documents": [document(d) for d in ("mietvertrag", "maengelruege", "fotos")]}, "c")
        self.assertTrue(state["facts"]["a1_versandt"])
        self.assertEqual(state["facts"]["anforderungen"], "2+")
        self.assertTrue(state["facts"]["unterlagen_vollstaendig"])
        self.assertEqual(state["evaluation"]["current"]["step"], "klaeren")  # cover is still the handler's to decide
        self.assertIn("deckung", {w["fact"] for w in state["evaluation"]["waiting_for"]})
        called = base + [fact("bisherige_handlungen", "A1 2024-02-20; A2 2024-03-18")]
        state = core.evaluate(wf, [], [], {"facts": called, "documents": [document("mietvertrag")]}, "c")
        nxt = {i["item_id"]: i for i in build_items(state, {"facts": called})}["next_action:0"]
        self.assertEqual((nxt["action"], nxt["next_in_days"]), ("A6", 25))  # after a call that leaves it open: pending with a deadline
        separate = base + [fact("handlung_a1", "2024-03-12"), fact("handlung_a2", "2024-03-18")]  # the history line was rejected
        state = core.evaluate(wf, [], [], {"facts": separate, "documents": [document("mietvertrag")]}, "c")
        self.assertEqual((state["facts"]["a1_versandt"], state["facts"]["anruf_offen"]), (True, True))
        self.assertEqual({i["item_id"]: i for i in build_items(state, {"facts": separate})}["next_action:0"]["action"], "A6")
        quiet = base + [fact("handlung_a1", "2024-09-11"), fact("handlung_a5", "2024-10-18")]  # an assessment, then silence
        state = core.evaluate(wf, [], [], {"facts": quiet, "documents": [document("mietvertrag")]}, "c")
        looked = [{"extraction": {"cut_of": {"as_of": "2025-02-07"}, "segments": [{"date": "18.10.2024"}]}}]
        nxt = {i["item_id"]: i for i in build_items(state, {"facts": quiet}, looked)}["next_action:0"]
        self.assertEqual((nxt["action"], nxt["next_in_days"]), ("A7", 7))
        self.assertIn("keine Antwort seit A5", nxt["reason"])
        early = [{"extraction": {"cut_of": {"as_of": "2024-11-01"}, "segments": [{"date": "18.10.2024"}]}}]
        self.assertNotEqual({i["item_id"]: i for i in build_items(state, {"facts": quiet}, early)}["next_action:0"]["action"], "A7")
        arrived = [document(d) for d in ("mietvertrag", "maengelruege", "fotos")]
        one_open = [fact("rechtsgebiet", "Mietrecht / Mangel"), fact("maengelruege_schriftlich", "ja"), fact("will_schadenersatz", "nein"),
                    fact("handlung_a1", "2024-03-12")]  # streit_mietzins is the stage's one open point
        state = core.evaluate(wf, [], [], {"facts": one_open, "documents": arrived}, "c")
        self.assertTrue(state["facts"]["ein_punkt_offen"])
        looked = [{"extraction": {"cut_of": {"as_of": "2024-03-25"}, "segments": [{"date": "22.03.2024"}]}}]  # documents came on 22.03
        listed = {i["item_id"]: i for i in build_items(state, {"facts": one_open}, looked)}
        self.assertEqual(listed["next_action:0"]["action"], "A4")
        self.assertEqual([i["key"] for i in listed.values() if i["kind"] == "letter_question" and i.get("ask") == "now"], ["streit_mietzins"])
        two_open = [f for f in one_open if f["fact"] != "will_schadenersatz"]
        state = core.evaluate(wf, [], [], {"facts": two_open, "documents": arrived}, "c")
        self.assertFalse(state["facts"]["ein_punkt_offen"])
        self.assertNotEqual({i["item_id"]: i for i in build_items(state, {"facts": two_open}, looked)}["next_action:0"]["action"], "A4")
        newest_first = base + [fact("bisherige_handlungen", "A2 2024-03-18; A1 2024-02-20")]
        self.assertTrue(core.evaluate(wf, [], [], {"facts": newest_first, "documents": []}, "c")["facts"]["anruf_offen"])
        covered = done + [fact("deckung", "bestätigt")]
        state = core.evaluate(wf, [], [], {"facts": covered, "documents": [document(d) for d in ("mietvertrag", "maengelruege", "fotos")]}, "c")
        self.assertEqual(state["evaluation"]["current"]["step"], "beurteilen")


if __name__ == "__main__":
    unittest.main()
