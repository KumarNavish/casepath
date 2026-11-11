import json
import tempfile
import unittest
from pathlib import Path

from casepath.agents import core
from casepath.process import workflows

SEED = Path(workflows.__file__).with_name("workflow_seed") / "mietmangel-handler.json"


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
            self.assertEqual([w["id"] for w in catalogue.routable()], ["mietmangel-handler"])
            self.assertIsNotNone(catalogue.get("osm-mold"))
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(workflows.Catalogue.load(tmp).workflows, ())

    def test_the_stage_follows_what_was_done_what_arrived_and_the_handlers_cover_decision(self):
        wf = workflows.validate_workflow(json.loads(SEED.read_text()))
        base = [fact("rechtsgebiet", "Mietrecht / Mangel"), fact("maengelruege_schriftlich", "ja"), fact("will_schadenersatz", "nein"),
                fact("streit_mietzins", "nein")]
        state = core.evaluate(wf, [], [], {"facts": base, "documents": [document("mietvertrag")]}, "c")
        self.assertEqual(state["evaluation"]["current"]["step"], "klaeren")
        self.assertFalse(state["facts"]["a1_versandt"])
        from casepath.process.items import build_items
        listed = {i["item_id"]: i for i in build_items(state, {"facts": base})}
        self.assertEqual(listed["next_action:0"]["action"], "A1")
        self.assertIn("letter_question:mangel_seit", listed)
        self.assertNotIn("hint:dokumentieren", listed)  # only when a reduction is wanted
        self.assertNotIn("hint:ruege_einschreiben", listed)  # a written notice was sent: no hint to send one
        done = base + [fact("bisherige_handlungen", "A1 2024-08-28; A4 2024-09-10")]
        state = core.evaluate(wf, [], [], {"facts": done, "documents": [document(d) for d in ("mietvertrag", "maengelruege", "fotos")]}, "c")
        self.assertTrue(state["facts"]["a1_versandt"])
        self.assertEqual(state["facts"]["anforderungen"], "2+")
        self.assertTrue(state["facts"]["unterlagen_vollstaendig"])
        self.assertEqual(state["evaluation"]["current"]["step"], "klaeren")  # cover is still the handler's to decide
        self.assertIn("deckung", {w["fact"] for w in state["evaluation"]["waiting_for"]})
        covered = done + [fact("deckung", "bestätigt")]
        state = core.evaluate(wf, [], [], {"facts": covered, "documents": [document(d) for d in ("mietvertrag", "maengelruege", "fotos")]}, "c")
        self.assertEqual(state["evaluation"]["current"]["step"], "beurteilen")


if __name__ == "__main__":
    unittest.main()
