"""What an insurer's review would stop, closed on the server: who releases shared rules and reads the evaluation, who
deletes a case, who opens a colleague's case, and a jurist's «Änderung nötig» on what a letter rests on. Synthetic."""
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from casepath.config import SettingsError, load_settings
from casepath.web.app import create_app
from tests.test_completion import Service


class Shared(unittest.TestCase):
    """One data directory, several people (each a client with its own sign-in name)."""
    ENV = {}

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "catalogue").mkdir()
        self.apps = []

    def tearDown(self):
        for app in self.apps:
            app.state.runs.shutdown()
            app.state.store.close()
        self.directory.cleanup()

    def person(self, name):
        app = create_app(load_settings({"CASEPATH_DATA_DIR": str(self.root / "data"), "CASEPATH_WORKFLOW_CATALOGUE": str(self.root / "catalogue"),
                                        "CASEPATH_DEV_USER": name, **self.ENV}), model_factory=lambda: None)
        self.apps.append(app)
        return TestClient(app)


class RoleTests(Shared):
    ENV = {"CASEPATH_REVIEWERS": "j. juristin"}

    def test_only_a_reviewer_releases_rules_and_reads_the_evaluation(self):
        handler, jurist = self.person("A. Handler"), self.person("J. Juristin")
        store = self.apps[0].state.store
        rule = store.list_knowledge()[0]  # a rule the deployment ships
        for path, method in ((f"/api/knowledge/{rule['id']}/replay", "post"), (f"/api/knowledge/{rule['id']}/activate", "post"),
                             (f"/api/knowledge/{rule['id']}/retire", "post"), ("/api/auswertung", "get"), ("/api/review/export", "get")):
            call = getattr(handler, method)
            r = call(path, json={"reason": "x"}) if method == "post" else call(path)
            self.assertEqual((r.status_code, r.json()["detail"]), (403, "Das ist den Prüferinnen und Prüfern vorbehalten."), path)
        self.assertEqual(store.get_knowledge(rule["id"])["status"], rule["status"])  # nothing changed
        self.assertEqual(jurist.get("/api/auswertung").status_code, 200)
        self.assertEqual(jurist.get("/api/review/export").status_code, 200)
        self.assertEqual(jurist.post(f"/api/knowledge/{rule['id']}/retire", json={"reason": "nicht mehr nötig"}).status_code, 200)

    def test_a_case_is_deleted_by_its_owner_the_deputy_or_a_reviewer(self):
        owner, colleague, jurist = self.person("A. Handler"), self.person("B. Kollegin"), self.person("J. Juristin")
        cid = owner.post("/api/cases", json={"title": "Schimmel", "intake": {}}).json()["id"]
        r = colleague.delete(f"/api/cases/{cid}")
        self.assertEqual((r.status_code, r.json()["detail"]), (403, "Diesen Fall löscht nur A. Handler, die Stellvertretung oder eine Prüferin, ein Prüfer."))
        self.assertEqual(owner.get(f"/api/cases/{cid}").status_code, 200)
        owner.put(f"/api/cases/{cid}/identity", json={"deputy": "B. Kollegin"})
        self.assertEqual(colleague.delete(f"/api/cases/{cid}").status_code, 200)
        other = owner.post("/api/cases", json={"title": "Zweiter", "intake": {}}).json()["id"]
        self.assertEqual(jurist.delete(f"/api/cases/{other}").status_code, 200)
        self.assertEqual([(d["case_id"], d["deleted_by"]) for d in self.apps[0].state.store.deletions()], [(cid, "B. Kollegin"), (other, "J. Juristin")])


class NeedToKnowTests(Shared):
    ENV = {"CASEPATH_CASE_ACCESS": "owner", "CASEPATH_REVIEWERS": "j. juristin"}

    def test_a_colleagues_case_opens_only_after_a_logged_takeover(self):
        owner, colleague, jurist = self.person("A. Handler"), self.person("B. Kollegin"), self.person("J. Juristin")
        cid = owner.post("/api/cases", json={"title": "Schimmel bei Familie Beispiel", "intake": {}}).json()["id"]
        owner.put(f"/api/cases/{cid}/identity", json={"reference": "4321.7000.0042"})
        store = self.apps[0].state.store
        file = store.add_file(cid, "Meldung.txt", "text/plain", "text", b"Guten Tag", {"text": "Guten Tag"}, "A. Handler")
        for path in (f"/api/cases/{cid}", f"/api/cases/{cid}/events", f"/api/files/{file['id']}/text", f"/api/files/{file['id']}/original"):
            r = colleague.get(path)
            self.assertEqual((r.status_code, r.json()["locked"]), (403, True), path)
            self.assertIn("gehört A. Handler", r.json()["detail"])
        self.assertEqual(colleague.put(f"/api/cases/{cid}/title", json={"title": "x"}).status_code, 403)
        row = next(c for c in colleague.get("/api/cases").json()["cases"] if c["id"] == cid)
        self.assertEqual(row, {"id": cid, "locked": True, "intake": {}, "title": "", "created_at": row["created_at"], "reference": "4321.7000.0042",
                               "owner": "A. Handler", "deputy": None, "mine": False})  # the number and the owner, nothing of the case
        self.assertEqual(jurist.get(f"/api/cases/{cid}").status_code, 200)  # a reviewer may
        self.assertEqual(owner.get(f"/api/cases/{cid}").status_code, 200)
        taken = colleague.post(f"/api/cases/{cid}/takeover")
        self.assertEqual((taken.status_code, taken.json()["case"]["deputy"], taken.json()["case"]["owner"]), (200, "B. Kollegin", "A. Handler"))
        self.assertEqual(colleague.get(f"/api/cases/{cid}").status_code, 200)
        logged = [e for e in store.list_case_events(cid) if e["kind"] == "case.assigned"]
        self.assertEqual([(e["expert"], e["deputy"], e["taken_over"]) for e in logged], [("B. Kollegin", "B. Kollegin", True)])

    def test_an_example_is_open_to_everyone_and_the_setting_is_one_of_two(self):
        owner, colleague = self.person("A. Handler"), self.person("B. Kollegin")
        cid = owner.post("/api/cases", json={"title": "Beispiel", "intake": {"synthetic": True}}).json()["id"]
        self.assertEqual(colleague.get(f"/api/cases/{cid}").status_code, 200)
        with self.assertRaises(SettingsError):
            load_settings({"CASEPATH_CASE_ACCESS": "alle"})


class HoldTests(Service):
    """S-D11A with its assessment prepared: a jurist's mark on the frame the letter states."""

    def test_a_change_a_jurist_asks_for_refuses_the_approval_and_a_question_is_shown_and_recorded(self):
        draft = self.ready()
        r = self.client.post("/api/review/mietmangel-handler/rahmen.rights", json={"mark": "frage", "comment": "Gilt das auch bei Untermiete?"})
        self.assertEqual(r.status_code, 201, r.text)
        held = self.view()["completion"]["held_now"]
        self.assertEqual([(h["key"], h["mark"], h["blocks"]) for h in held], [("mietmangel-handler:rahmen.rights", "Frage", False)])
        r = self.client.post("/api/review/mietmangel-handler/rahmen.rights", json={"mark": "aenderung", "comment": "Schadenersatz nur bei Verschulden."})
        self.assertEqual(r.status_code, 201, r.text)
        view = self.view()
        self.assertEqual([(h["mark"], h["blocks"]) for h in view["completion"]["held_now"]], [("Änderung nötig", True)])
        self.assertEqual(view["draft"]["version"], draft["version"])  # the letter is the same letter: the hold is on what it rests on
        refused = self.approve(draft, expect=422)
        self.assertTrue(refused["detail"].startswith("In Prüfung, bitte mit der Prüferin oder dem Prüfer klären: "), refused["detail"])
        self.assertIn("(Änderung nötig)", refused["detail"])
        self.assertEqual(self.events("action.approved"), [])
        self.client.post("/api/review/mietmangel-handler/rahmen.rights", json={"mark": "geprueft"})  # settled: the approval goes through
        self.assertEqual(self.view()["completion"]["held_now"], [])
        self.approve(draft)


if __name__ == "__main__":
    unittest.main()
