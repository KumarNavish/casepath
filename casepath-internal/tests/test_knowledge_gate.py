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


class ExactPreviewTests(Gate):
    """The replay previews exactly what activation then does (the audit of 84115b9: a refining candidate was replayed
    beside the item it refines, while activation merges it into that item; nine requirements were previewed, eight came)."""

    def needs(self, case_id):
        return sorted(d["id"] for d in self.client.get(f"/api/cases/{case_id}").json()["process"]["documents"])

    def test_preview_and_activation_agree_on_a_refining_candidate(self):
        a, b = self.prepared("Fall A (synthetisch)"), self.prepared("Fall B (synthetisch)")
        origin = {"kind": "case", "by": "result_checker", "case_id": a["id"]}
        need = self.store.save_knowledge(kb.set_status(kb.new_item(WID, "document_need", {"title": "Wohnungsabnahmeprotokoll", "why": "Zeigt den Zustand."},
                                                                   origin=origin), "active", by="dev", reason="Test"))
        self.assertIn(f"k-{need['id']}", self.needs(b["id"]))  # in force for every case of the area
        # the refinement narrows it to another area's cases: merged into the need, it no longer applies here
        refining = kb.new_item(WID, "document_need", {"title": "Wohnungsabnahmeprotokoll", "why": "Nur bei Auszug."},
                               applies_when={"fact": "rechtsgebiet", "is": "Mietrecht / Kündigung"}, origin=origin)
        refining = self.store.save_knowledge({**refining, "refines": need["id"]})
        played = self.client.post(f"/api/knowledge/{refining['id']}/replay").json()["replay"]
        self.assertEqual((played["version"], played["target"], played["target_version"]), (1, need["id"], 1))
        predicted = {row["case"]: row["after"]["needs"] for row in played["changed"]}
        before = {c["id"]: self.needs(c["id"]) for c in (a, b)}
        # case B loses the need, previewed as activation merges it (beside the active need, nothing would have changed);
        # case A, where the need was learned, never had it
        self.assertEqual(sorted(predicted), [b["id"]])
        self.assertEqual(sorted(predicted[b["id"]]), [d for d in before[b["id"]] if d != f"k-{need['id']}"])
        merged = self.client.post(f"/api/knowledge/{refining['id']}/activate", json={"reason": "Nachgespielt."})
        self.assertEqual((merged.status_code, merged.json()["id"], merged.json()["version"]), (200, need["id"], 2))
        for case in (a, b):  # what activation did is what the replay showed, case by case
            self.assertEqual(self.needs(case["id"]), sorted(predicted.get(case["id"], before[case["id"]])))

    def test_a_refinement_replayed_on_an_older_version_of_its_item_is_replayed_again(self):
        a = self.prepared("Fall A (synthetisch)")
        origin = {"kind": "case", "by": "result_checker", "case_id": a["id"]}
        need = self.store.save_knowledge(kb.set_status(kb.new_item(WID, "document_need", {"title": "Wohnungsabnahmeprotokoll", "why": "Zeigt den Zustand."},
                                                                   origin=origin), "active", by="dev", reason="Test"))
        refining = self.store.save_knowledge({**kb.new_item(WID, "document_need", {"title": "Wohnungsabnahmeprotokoll", "why": "Mit Fotos."}, origin=origin),
                                              "refines": need["id"]})
        self.client.post(f"/api/knowledge/{refining['id']}/replay")
        self.store.save_knowledge(kb.refine(self.store.get_knowledge(need["id"]), content={"why": "Zeigt den Zustand bei Mietbeginn."}, by="dev"))
        stale = self.client.post(f"/api/knowledge/{refining['id']}/activate", json={})
        self.assertEqual((stale.status_code, stale.json()["detail"]), (409, "Zuerst nachspielen: der verfeinerte Eintrag hat sich seither geändert"))
        self.assertEqual(self.store.get_knowledge(need["id"])["version"], 2)  # nothing applied
        self.assertEqual(self.client.post(f"/api/knowledge/{refining['id']}/replay").json()["replay"]["target_version"], 2)
        self.assertEqual(self.client.post(f"/api/knowledge/{refining['id']}/activate", json={}).json()["version"], 3)
        self.assertIn("r.target_version === target.version", SCRIPT)  # «Wissen» offers «Nachspielen» again in that case


if __name__ == "__main__":
    unittest.main()
