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
from casepath.process import completion, knowledge as kb
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

    def approve(self, case_id, op):
        draft = self.client.get(f"/api/cases/{case_id}").json()["draft"]
        r = self.client.post(f"/api/cases/{case_id}/actions/approve", json={"form": draft["form"], "version": draft["version"], "op_id": op})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["approval"]

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



class LandingTests(Gate):
    """A correction teaches, and a rule change lands where it changes something (docs/HANDLER_WORK.md)."""

    def add(self, case_id, title, step="klaeren", code="2"):
        r = self.client.post(f"/api/cases/{case_id}/edits", json={"op": "add_document", "args": {"title": title, "why": "Wird gebraucht.", "step": step},
                                                                  "reason": "", "reason_code": code, "recheck": False})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    def strike(self, case_id, document, code="3"):
        r = self.client.post(f"/api/cases/{case_id}/edits", json={"op": "remove_document", "args": {"document": document}, "reason": "", "reason_code": code,
                                                                  "recheck": False})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    def test_a_released_rule_is_in_the_log_of_each_case_it_changes_and_an_unsent_approval_is_stale(self):
        a, b = self.prepared("Fall A (synthetisch)"), self.prepared("Fall B (synthetisch)")
        approval = self.approve(b["id"], "op-land-1")
        self.assertEqual(approval["stand"]["workflow"]["id"], WID)  # «Stand bei Freigabe»: the rules the approval was given on
        self.assertTrue(all(ref.startswith("knowledge#") and "@v" in ref for ref in approval["stand"]["knowledge"]))
        self.assertEqual(self.client.get(f"/api/cases/{b['id']}").json()["completion"]["stale"], [])
        item = self.candidate(a["id"])
        self.assertEqual([e for e in self.store.list_case_events(b["id"]) if e["kind"] == "knowledge.changed"], [])  # a candidate lands nowhere
        self.client.post(f"/api/knowledge/{item['id']}/activate", json={"reason": "Nachgespielt."})
        landed, = [e for e in self.store.list_case_events(b["id"]) if e["kind"] == "knowledge.changed"]
        self.assertEqual((landed["item"], landed["version"], landed["verb"], landed["added"], landed["expert"]),
                         (item["id"], 1, "released", ["Lüftungsprotokoll"], "dev"))
        view = self.client.get(f"/api/cases/{b['id']}").json()
        self.assertIn("Regel geändert", view["completion"]["stale"])
        row, = [r for r in view["verlauf"] if r["title"] == "Regel"]
        self.assertEqual((row["who"], row["what"]), ("Wissen · dev", "Regel freigegeben: «Lüftungsprotokoll» (Fassung 1) · neu verlangt: Lüftungsprotokoll"))
        # the case the rule came from already asked the document: nothing changed there, so nothing is written there
        self.assertEqual([e for e in self.store.list_case_events(a["id"]) if e["kind"] == "knowledge.changed"], [])
        self.client.post(f"/api/knowledge/{item['id']}/retire", json={"reason": "Doch nicht."})
        self.assertEqual([(e["verb"], e["dropped"]) for e in self.store.list_case_events(b["id"]) if e["kind"] == "knowledge.changed"],
                         [("released", 0), ("retired", 1)])
        self.assertEqual([e["cases_touched"] for kind in ("knowledge.released", "knowledge.retired") for e in self.store.list_workspace_events(kind)], [1, 1])

    def test_the_same_document_added_in_three_cases_becomes_a_proposal_and_three_different_ones_do_not(self):
        cases = [self.prepared(f"Fall {n} (synthetisch)") for n in "ABCDEF"]
        for case, title in zip(cases[:3], ("Fotos der Küche", "Heizkostenabrechnung", "Zeugenliste")):  # the same step, three different documents
            self.assertIsNone(self.add(case["id"], title)["knowledge"])
        self.assertIsNone(self.add(cases[3]["id"], "Lüftungsprotokoll")["knowledge"])
        self.assertIsNone(self.add(cases[4]["id"], "lüftungsprotokoll ", step="eingang")["knowledge"])  # the same by its name, on another step
        learned = self.add(cases[5]["id"], "Lüftungsprotokoll")["knowledge"]
        self.assertEqual((learned["kind"], learned["status"], learned["content"]["title"], learned["replay"]["because"]),
                         ("document_need", "candidate", "Lüftungsprotokoll", "wiederholt"))

    def test_a_struck_document_teaches_and_generally_so_is_never_silently_dropped(self):
        a, b, c = (self.prepared(f"Fall {n} (synthetisch)") for n in "ABC")
        need = next(d for d in self.client.get(f"/api/cases/{a['id']}").json()["process"]["documents"] if d.get("knowledge"))
        self.assertIsNone(self.strike(a["id"], need["id"])["knowledge"])  # «hier nicht relevant»: this case only
        self.assertIsNone(self.strike(b["id"], need["id"])["knowledge"])
        learned = self.strike(c["id"], need["id"])["knowledge"]  # the third case: said in general, for a person to decide
        self.assertEqual((learned["kind"], learned["status"], learned["content"]["document"], learned["replay"]["because"]),
                         ("note", "candidate", need["id"], "wiederholt"))
        self.assertIn(f"«{need['title']}» wird von der Fallbearbeitung als nicht nötig gestrichen", learned["content"]["text"])
        asked_by = self.store.get_knowledge(need["knowledge"])  # each strike counts against the item that asks it, once per case
        self.assertEqual((asked_by["stats"]["contradicted"], asked_by["review_suggested"]), (3, True))
        # «gilt generell so» on a fact of the case cannot be a rule: said back, never dropped without a word
        r = self.client.post(f"/api/cases/{a['id']}/edits", json={"op": "set_fact", "args": {"fact": "maengelruege_schriftlich", "value": "ja"}, "reason": "",
                                                                  "reason_code": "4", "recheck": False})
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual((r.json()["knowledge"], r.json()["only_here"]),
                         (None, "Gilt in diesem Fall. Als Regel für ähnliche Fälle lässt sich das hier nicht vorschlagen."))

    def test_one_strike_in_the_letter_takes_the_document_out_of_the_case(self):
        handler = SCRIPT[SCRIPT.index('on("[data-line-reason]"'):]
        handler = handler[:handler.index("\n  });")]
        self.assertIn('op: "remove_document"', handler)
        self.assertIn('code === "3" || code === "4"', handler)
        self.assertIn("Für ähnliche Fälle vorgeschlagen", SCRIPT)


class StandTests(Gate):
    """«Stand bei Freigabe»: the approval keeps what it was given on, the package says it in words, and a recall finds
    every letter that rests on a rule."""

    def test_the_package_keeps_the_rules_requirements_and_facts_the_letter_was_approved_on(self):
        import io
        import json
        import zipfile
        a = self.prepared("Fall A (synthetisch)")
        approval = self.approve(a["id"], "op-stand-1")
        self.assertEqual(sorted(approval["stand"]), ["facts_sha256", "items_sha256", "knowledge", "workflow"])  # the event keeps no case content
        blob = self.client.get(f"/api/cases/{a['id']}/actions/{approval['version']}/bundle").content
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            page = archive.read("Stand bei Freigabe.txt").decode("utf-8")
            manifest = json.loads(archive.read("manifest.json"))
        record = manifest["stand"]
        self.assertEqual({k: record[k] for k in approval["stand"]}, approval["stand"])
        self.assertIn("Stand bei Freigabe.txt", [p["name"] for p in manifest["parts"]])
        asked = {x["what"]: x["from"] for x in record["asked"]}
        self.assertIn("Wissen", asked.values())  # a need a Knowledge item asks, named as such
        self.assertIn("Prozess", asked.values())
        self.assertEqual({p["wording"] for p in record["parts"]}, {"Formular"})  # nothing reworded by the handler
        self.assertEqual([r["ref"] for r in record["knowledge_titles"]], approval["stand"]["knowledge"])
        for line in (f"Prozess: {WID} · Fassung ", "Wissen (Regeln, auf denen der Fall beruht):", "Der Brief verlangt:", "- Unterlage: ",
                     "Feststellungen, wie der Fall sie bei der Freigabe hielt:", "Daraus berechnet (nach der Regel des Prozesses):",
                     f"Anforderungen (SHA-256): {approval['stand']['items_sha256']}"):
            self.assertIn(line, page)

    def test_a_recall_finds_every_letter_that_rests_on_a_rule_and_says_whether_it_went_out(self):
        a, b = self.prepared("Fall A (synthetisch)"), self.prepared("Fall B (synthetisch)")
        approval = self.approve(a["id"], "op-recall-1")
        seed = approval["stand"]["knowledge"][0].split("#", 1)[1].split("@")[0]
        found = self.client.get("/api/recall", params={"knowledge": seed}).json()
        self.assertEqual((found["letters"], found["sent"], found["cases"]), (1, 0, 1))
        row, = found["rows"]
        self.assertEqual((row["case"], row["form"], row["version"], row["approved_by"], row["sent"]), (a["id"], "A1", approval["version"], "dev", []))
        self.assertEqual(self.client.get("/api/recall", params={"knowledge": seed, "version": 99}).json()["letters"], 0)  # another version of the rule
        self.assertEqual(self.client.get("/api/recall", params={"workflow_version": approval["stand"]["workflow"]["version"]}).json()["letters"], 1)
        element = approval["relies"][0]
        self.assertEqual(self.client.get("/api/recall", params={"element": element}).json()["letters"], 1)  # by a reviewed element it rests on
        sent = self.client.post(f"/api/cases/{a['id']}/actions/dispatch", json={"version": approval["version"], "date": completion.swiss_today().isoformat(), "channel": "email",
                                                                                 "op_id": "op-recall-2"})
        self.assertEqual(sent.status_code, 200, sent.text)
        self.assertEqual(self.client.get("/api/recall", params={"knowledge": seed}).json()["sent"], 1)
        self.assertEqual(self.client.get("/api/recall").status_code, 422)  # exactly one question
        self.assertIn("Briefe, die darauf beruhen", SCRIPT)

if __name__ == "__main__":
    unittest.main()
