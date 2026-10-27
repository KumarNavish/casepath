import json
from pathlib import Path
import tempfile
import time
import types
import unittest

from fastapi.testclient import TestClient

from casepath_internal.app import create_app
from casepath_internal.config import load_settings
from casepath_internal.scorecard import ScorecardLeak, guard, scorecard
from casepath_internal.store import CaseStore
from tests.test_model_agent import ScriptedModel

FIXTURES = Path(__file__).parent / "fixtures"
QUOTE = "Ich habe den Vermieter am 2. März schriftlich informiert."
EMAIL = ("From: tenant@example.org\r\nSubject: Schimmel im Bad\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n"
         + QUOTE + "\r\n").encode()
FINISH = {"summary": "Mould reported; landlord told.", "answer": "Evidence is incomplete.", "open_points": [],
          "reply": {"needed": True, "subject": "Re: Schimmel", "clauses": [{"text": "You told your landlord.", "basis": ["fact:landlord_notified"]}]},
          "lessons": [{"text": "Ask for the written notice.", "applies_when": "defect cases", "citations": [{"file": "FILE", "quote": QUOTE}]}]}


class AppTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.env = {"CASEPATH_DATA_DIR": self.directory.name, "CASEPATH_WORKFLOW_CATALOGUE": str(FIXTURES), "CASEPATH_DEV_USER": "dev"}

    def tearDown(self):
        self.directory.cleanup()

    def client(self, model=None, **env):
        settings = load_settings({**self.env, **env})
        return TestClient(create_app(settings, model_factory=lambda: model))

    def test_sign_in_is_required(self):
        client = self.client(CASEPATH_DEV_USER="")
        self.assertEqual(client.get("/api/cases").status_code, 503)
        gateway = self.client(CASEPATH_DEV_USER="", CASEPATH_IDENTITY_HEADER="x-identity")
        self.assertEqual(gateway.get("/api/cases").status_code, 401)
        self.assertEqual(gateway.get("/api/cases", headers={"x-identity": "u1"}).status_code, 200)

    def test_case_run_end_to_end(self):
        client = self.client()
        case = client.post("/api/cases", json={"title": "Schimmel im Bad"}).json()
        uploaded = client.post(f"/api/cases/{case['id']}/files", files={"file": ("message.eml", EMAIL, "message/rfc822")}).json()
        self.assertEqual(uploaded["kind"], "email")
        self.assertNotIn("text", uploaded["extraction"])
        self.assertEqual(client.get(f"/api/files/{uploaded['id']}/original").content, EMAIL)
        client.put(f"/api/cases/{case['id']}/workflow", json={"workflow_id": "example-defect"})
        before = client.get(f"/api/cases/{case['id']}").json()
        self.assertEqual(before["evaluation"]["current"]["step"], "notice")
        finish = json.loads(json.dumps(FINISH).replace("FILE", uploaded["id"]))
        model = ScriptedModel([
            [("record_fact", {"fact": "landlord_notified", "status": "established", "value": "yes",
                              "citations": [{"file": uploaded["id"], "quote": QUOTE}]})],
            [("finish", finish)],
        ])
        model.settings = types.SimpleNamespace(deployment="example-deployment")
        client.app.state.runs.model_factory = lambda: model
        run = client.post(f"/api/cases/{case['id']}/runs").json()
        self.assertEqual(client.post(f"/api/cases/{case['id']}/runs").status_code in (202, 409), True)
        for _ in range(100):
            state = client.get(f"/api/runs/{run['id']}").json()
            if state["status"] not in ("queued", "running"):
                break
            time.sleep(0.05)
        self.assertEqual(state["status"], "completed", state.get("error"))
        self.assertEqual(state["result"]["evaluation"]["outcome"]["id"], "reported")
        self.assertTrue(state["events"])
        after = client.get(f"/api/cases/{case['id']}").json()
        self.assertEqual(after["evaluation"]["outcome"]["id"], "reported")
        candidates = client.get("/api/knowledge", params={"status": "candidate"}).json()["knowledge"]
        self.assertEqual(len(candidates), 1)
        published = client.post(f"/api/knowledge/{candidates[0]['id']}/publish").json()
        self.assertEqual(published["status"], "published")
        card = scorecard(CaseStore(self.directory.name), "salt")
        row, = card["runs"]
        self.assertEqual((row["status"], row["outcome"], row["documents"]["notice_letter"]), ("completed", "reported", "missing"))
        self.assertNotIn("Schimmel", json.dumps(card))

    def test_unconfigured_model_fails_with_a_reason(self):
        client = self.client()
        case = client.post("/api/cases", json={"title": "x"}).json()
        client.post(f"/api/cases/{case['id']}/files", files={"file": ("m.txt", b"some text here", "text/plain")})
        run = client.post(f"/api/cases/{case['id']}/runs").json()
        for _ in range(100):
            state = client.get(f"/api/runs/{run['id']}").json()
            if state["status"] not in ("queued", "running"):
                break
            time.sleep(0.05)
        self.assertEqual(state["status"], "failed")
        self.assertTrue(state["error"].startswith("model_not_configured"))

    def test_restart_marks_unfinished_runs(self):
        store = CaseStore(self.directory.name)
        case = store.create_case("x", {}, "dev")
        run = store.create_run(case["id"], "dev")
        self.client()
        self.assertEqual(CaseStore(self.directory.name).get_run(run["id"])["status"], "interrupted")


class GuardTests(unittest.TestCase):
    def test_free_text_cannot_leave(self):
        self.assertEqual(guard({"status": "completed", "n": 3, "file": "h_0123456789ab"}),
                         {"status": "completed", "n": 3, "file": "h_0123456789ab"})
        for leak in ({"note": "Der Vermieter hat nie geantwortet"}, {"Name Of Tenant": 1}, ["Elin Ziegler"]):
            with self.assertRaises(ScorecardLeak):
                guard(leak)


if __name__ == "__main__":
    unittest.main()
