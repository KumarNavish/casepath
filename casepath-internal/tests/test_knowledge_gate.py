"""Shared Knowledge is activated only after a replay of its current version (HANDLER_BAR L3, docs/HANDLER_BAR.md:130;
Slice C, C12): the edit form makes a candidate and no longer activates; «Nachspielen» replays the item's version on the
stored cases without a model and keeps what it would change on the item; «Freigeben» is refused until that replay is of
the version being activated. Who may activate is unchanged.

Scripted and model-free: cases of the handler's workflow with stored results."""
from pathlib import Path
import re
import tempfile
import unittest

from fastapi.testclient import TestClient

from casepath.config import load_settings
from casepath.process import knowledge as kb
from casepath.read.extract import extract
from casepath.web.app import create_app

SCRIPT = (Path(__file__).parents[1] / "casepath" / "web" / "ui" / "assets" / "casepath.js").read_text()
WID = "mietmangel-handler"


class Gate(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.client = TestClient(create_app(load_settings({"CASEPATH_DATA_DIR": str(Path(self.directory.name) / "data"), "CASEPATH_DEV_USER": "dev"}),
                                            model_factory=lambda: None))  # no model at all: nothing here may need one
        self.store = self.client.app.state.store

    def tearDown(self):
        self.client.app.state.runs.shutdown()
        self.store.close()
        self.directory.cleanup()

    def prepared(self, title):
        """A case of the handler's workflow with a stored, completed run (no model)."""
        case = self.store.create_case(title, {"synthetic": True}, "dev")
        text = f"{title}: Im Bad wächst Schimmel; die Verwaltung reagiert nicht.".encode()
        row = extract("Meldung.txt", "text/plain", text)
        self.store.add_file(case["id"], "Meldung.txt", row["media_type"], row["kind"], text, row, "dev")
        run = self.store.create_run(case["id"], "dev")
        fact = {"fact": "rechtsgebiet", "status": "established", "verdict": "accepted", "value": "Mietrecht / Mangel", "citations": []}
        self.store.update_run(run["id"], status="completed", workflow_id=WID, finished_at="2026-11-12T10:00:00+00:00",
                              result={"facts": [fact], "documents": [], "brief": {"request": "Schimmel im Bad.", "parties": [], "timeline": []}})
        return case

    def candidate(self, case_id):
        """A document need a handler saved «für ähnliche Fälle» in one case: a candidate, with the replay of its version."""
        body = {"op": "add_document", "args": {"title": "Lüftungsprotokoll", "why": "Zeigt, wie gelüftet wurde.", "step": "klaeren"},
                "reason": "Bei Schimmel immer verlangen.", "use_for_similar": True, "recheck": False}
        made = self.client.post(f"/api/cases/{case_id}/edits", json=body)
        self.assertEqual(made.status_code, 201, made.text)
        return made.json()["knowledge"]


class GateTests(Gate):
    def test_the_edit_form_cannot_activate_knowledge(self):
        a, b = self.prepared("Fall A (synthetisch)"), self.prepared("Fall B (synthetisch)")
        body = {"op": "add_document", "args": {"title": "Lüftungsprotokoll", "why": "Zeigt, wie gelüftet wurde.", "step": "klaeren"},
                "reason": "Bei Schimmel immer verlangen.", "use_for_similar": True, "activate": True, "recheck": False}
        refused = self.client.post(f"/api/cases/{a['id']}/edits", json=body)
        self.assertEqual((refused.status_code, refused.json()["detail"]), (422, "Freigabe im Wissen erst nach dem Nachspielen"))
        self.assertEqual(self.store.list_edits(a["id"]), [])  # nothing saved: neither the edit nor an item
        self.assertEqual([k for k in self.store.list_knowledge() if k["origin"].get("kind") == "case_edit"], [])
        item = self.candidate(a["id"])  # «für ähnliche Fälle» still makes a candidate, now with its replay
        self.assertEqual((item["status"], item["version"], item["replay"]["version"]), ("candidate", 1, 1))
        self.assertEqual(item["replay"]["cases"], 2)
        self.assertEqual([r["case"] for r in item["replay"]["changed"]], [b["id"]])  # its own case is not changed by it
        # the edit form offers no activation
        self.assertNotIn('name="activate"', SCRIPT)
        self.assertNotIn("Ab sofort bei neuen Fällen anwenden", SCRIPT)
        self.assertNotIn("activate: form.activate", SCRIPT)

    def test_activation_needs_a_replay_of_the_current_version(self):
        case = self.prepared("Fall A (synthetisch)")
        never = self.store.save_knowledge(kb.new_item(WID, "document_need", {"title": "Wohnungsabnahmeprotokoll", "why": "Zeigt den Zustand."},
                                                      origin={"kind": "case", "by": "result_checker", "case_id": case["id"]}))
        refused = self.client.post(f"/api/knowledge/{never['id']}/activate", json={"reason": "Oft gesehen."})
        self.assertEqual((refused.status_code, refused.json()["detail"]), (409, "Zuerst nachspielen: die Wirkung dieser Fassung ist nicht bekannt"))
        self.assertEqual(self.store.get_knowledge(never["id"])["status"], "candidate")
        replayed = self.client.post(f"/api/knowledge/{never['id']}/replay").json()
        self.assertEqual(replayed["replay"]["version"], 1)
        # an older version's replay does not count: the item was refined since
        refined = self.store.save_knowledge(kb.refine(self.store.get_knowledge(never["id"]), content={"why": "Zeigt den Zustand bei Mietbeginn."}, by="dev"))
        self.assertEqual((refined["version"], refined["replay"]["version"]), (2, 1))
        self.assertEqual(self.client.post(f"/api/knowledge/{never['id']}/activate", json={"reason": "Oft gesehen."}).status_code, 409)
        self.client.post(f"/api/knowledge/{never['id']}/replay")
        active = self.client.post(f"/api/knowledge/{never['id']}/activate", json={"reason": "Oft gesehen."})
        self.assertEqual((active.status_code, active.json()["status"], active.json()["version"]), (200, "active", 2))
        # a refinement: the refining item's own replay counts, and activating it merges into the item it refines
        refining = kb.new_item(WID, "document_need", {"title": "Wohnungsabnahmeprotokoll", "why": "Mit Fotos des Zustands."},
                               origin={"kind": "case", "by": "result_checker", "case_id": case["id"]})
        refining = self.store.save_knowledge({**refining, "refines": never["id"]})
        self.assertEqual(self.client.post(f"/api/knowledge/{refining['id']}/activate", json={}).status_code, 409)
        self.client.post(f"/api/knowledge/{refining['id']}/replay")
        merged = self.client.post(f"/api/knowledge/{refining['id']}/activate", json={})
        self.assertEqual((merged.status_code, merged.json()["id"], merged.json()["version"]), (200, never["id"], 3))
        self.assertEqual(self.store.get_knowledge(refining["id"])["status"], "retired")

    def test_a_replay_is_computed_without_a_model_and_shown_before_activation(self):
        a, b = self.prepared("Fall A (synthetisch)"), self.prepared("Fall B (synthetisch)")
        item = self.candidate(a["id"])
        need = f"k-{item['id']}"
        before = {d["id"] for d in self.client.get(f"/api/cases/{b['id']}").json()["process"]["documents"]}
        self.assertNotIn(need, before)  # a candidate shapes no case
        again = self.client.post(f"/api/knowledge/{item['id']}/replay")  # the app has no model at all
        self.assertEqual(again.status_code, 200, again.text)
        replay = again.json()["replay"]
        self.assertEqual((replay["version"], replay["cases"], replay["by"]), (1, 2, "dev"))
        changed, = replay["changed"]
        self.assertEqual((changed["case"], changed["title"]), (b["id"], "Fall B (synthetisch)"))
        self.assertIn("needs", changed["changed"])
        logged = [e for e in self.store.list_workspace_events("knowledge.replayed") if e["item"] == item["id"]]
        self.assertEqual([(e["version"], e["cases"], e["changed"]) for e in logged][-1], (1, 2, 1))
        self.assertEqual(self.client.post(f"/api/knowledge/{item['id']}/activate", json={"reason": "Nachgespielt."}).json()["status"], "active")
        after = {d["id"] for d in self.client.get(f"/api/cases/{b['id']}").json()["process"]["documents"]}
        self.assertIn(need, after)
        # «Wissen» shows «Nachspielen» for an item without a current replay, then what it changes, then «Freigeben»
        card = re.search(r"function replayLine\(k, all, caseName\) \{(.*?)\n\}", SCRIPT, re.S).group(1)
        self.assertIn("ändert ${n} von ${total} Fällen", card)
        self.assertIn('T("Replay", "Nachspielen")', SCRIPT)
        self.assertIn("replayCurrent(k, data.knowledge)", SCRIPT)


if __name__ == "__main__":
    unittest.main()
