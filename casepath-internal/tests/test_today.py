"""The daily pass and «Heute»: what moved by time alone is written into the case's log as CasePath's, and the reader is
told what happened on their cases since they last looked. Synthetic, no model."""
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from casepath.config import load_settings
from casepath.process import completion
from casepath.read.extract import extract
from casepath.web.app import create_app
from tests.test_outbox import MAIL, TOLD


class TodayTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "catalogue").mkdir()
        self.apps = []
        self.a = self.person("A. Handler")
        store = self.store = self.apps[0].state.store
        case = store.create_case("Schimmel im Bad (synthetisch)", {}, "A. Handler")
        row = extract("Meldung Lea Brunner.eml", "message/rfc822", MAIL)
        mail = store.add_file(case["id"], "Meldung Lea Brunner.eml", row["media_type"], row["kind"], MAIL, row, "A. Handler")["id"]
        fact = lambda f, v, quote=None: {"fact": f, "status": "established", "verdict": "accepted", "value": v,
                                          "citations": [{"file": mail, "quote": quote}] if quote else []}
        run = store.create_run(case["id"], "A. Handler")
        store.update_run(run["id"], status="completed", workflow_id="mietmangel-handler", finished_at="2026-11-12T10:00:00+00:00",
                         result={"facts": [fact("rechtsgebiet", "Mietrecht / Mangel"), fact("maengelruege_schriftlich", "ja", TOLD)], "documents": [],
                                 "brief": {"request": "Lea Brunner möchte Hilfe, weil im Badezimmer immer wieder Schimmel auftritt.",
                                           "parties": [{"role": "Mieterin (VN)", "name": "Frau Lea Brunner"}], "timeline": []}})
        self.case = case["id"]

    def person(self, name):
        app = create_app(load_settings({"CASEPATH_DATA_DIR": str(self.root / "data"), "CASEPATH_WORKFLOW_CATALOGUE": str(self.root / "catalogue"),
                                        "CASEPATH_DEV_USER": name}), model_factory=lambda: None)
        self.apps.append(app)
        return TestClient(app)

    def tearDown(self):
        for app in self.apps:
            app.state.runs.shutdown()
            app.state.store.close()
        self.directory.cleanup()

    def moved(self):
        return [e for e in self.store.list_case_events(self.case) if e["kind"] == "system.moved"]

    def test_the_pass_notes_only_what_moved_by_time_alone(self):
        tick = self.apps[0].state.tick
        first = tick()
        self.assertEqual((first["cases"], first["moved"]), (1, 0))  # the first look: nothing to compare with
        self.assertEqual(tick()["moved"], 0)  # nothing changed: nothing is written
        # the case's remembered state is made an older one, as if the follow-up had not been due at the pass before
        remembered = self.store.get_tick(self.case)
        self.store.set_tick(self.case, "older", {**remembered["state"], "stand": "wartet auf Kundschaft bis 01.12.2026", "bucket": "wartet"})
        self.assertEqual(tick()["moved"], 1)
        event = self.moved()[0]
        self.assertEqual((event["expert"], event["trigger"], event["before"]["stand"], event["after"]["stand"]),
                         ("CasePath", "tick", "wartet auf Kundschaft bis 01.12.2026", remembered["state"]["stand"]))
        # a change a person made is theirs, not something CasePath noticed
        self.store.set_tick(self.case, "older-again", {**remembered["state"], "stand": "anders"})
        self.a.put(f"/api/cases/{self.case}/identity", json={"reference": "4321.7000.0042"})
        self.assertEqual(tick()["moved"], 0)
        self.assertEqual(len(self.moved()), 1)
        self.assertEqual(self.a.get("/api/health").json()["tick"]["cases"], 1)

    def test_heute_says_what_happened_since_the_last_visit_on_my_cases(self):
        b = self.person("B. Kollegin")
        since = "2026-11-12T09:00:00+00:00"
        mine = self.a.get("/api/today", params={"since": since}).json()
        self.assertEqual([(e["what"], e["by"]) for e in mine["events"]], [("fertig vorbereitet", "CasePath")])  # the preparation finished since
        draft = self.a.get(f"/api/cases/{self.case}").json()["draft"]
        r = b.post(f"/api/cases/{self.case}/actions/approve", json={"form": draft["form"], "version": draft["version"], "op_id": "op-approve-1"})
        self.assertEqual(r.status_code, 200, r.text)
        mine = self.a.get("/api/today", params={"since": since}).json()
        self.assertEqual([(e["what"], e["by"]) for e in mine["events"]][0], ("freigegeben", "B. Kollegin"))  # what a colleague did on my case
        self.assertEqual(mine["events"][0]["case"], self.case)
        theirs = b.get("/api/today", params={"since": since}).json()  # she owns no case: all she may open; her own gesture is not news to her
        self.assertEqual([e["what"] for e in theirs["events"]], ["fertig vorbereitet"])
        later = (completion.swiss_today() + timedelta(days=1)).isoformat() + "T00:00:00+00:00"
        self.assertEqual(self.a.get("/api/today", params={"since": later}).json()["events"], [])
        self.assertEqual(self.a.get("/api/today").json()["events"], [])  # a first visit: the counts only
        self.assertEqual(self.a.get("/api/today", params={"since": "gestern"}).json()["since"], None)


if __name__ == "__main__":
    unittest.main()
