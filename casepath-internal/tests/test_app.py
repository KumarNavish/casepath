import json
from pathlib import Path
import tempfile
import time
import unittest

from fastapi.testclient import TestClient

from casepath_internal.app import create_app
from casepath_internal.config import load_settings
from casepath_internal.scorecard import ScorecardLeak, guard, scorecard
from casepath_internal.store import CaseStore
from tests.scripted import ScriptedModel, delegate, learn, report

FIXTURES = Path(__file__).parent / "fixtures"
QUOTE = "Ich habe den Vermieter am 2. März schriftlich informiert."
VENT = "Ich lüfte dreimal täglich, trotzdem kommt der Schimmel zurück."
LEASE = "Der Mietvertrag vom 1. April 2021 liegt bei."
EMAIL = ("From: tenant@example.org\r\nSubject: Schimmel im Bad\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n"
         f"{QUOTE} {VENT} {LEASE}\r\n").encode()


def team_script(file_id, *, finder_calls=(), learn_rows=()):
    return [
        [delegate("claim_reader", "Brief the case.")],
        [report("claim_reader", request="Check the mould defect.")],
        [delegate("process_builder")],
        [("open_process", {}), report("process_builder")],
        [delegate("claim_reader", "Record the facts.")],
        [("record_fact", {"fact": "landlord_notified", "status": "established", "value": "yes",
                          "citations": [{"file": file_id, "quote": QUOTE}]}), report("claim_reader")],
        [delegate("document_finder")],
        [*finder_calls, report("document_finder")],
        [delegate("result_checker")],
        [report("result_checker", learn=list(learn_rows))],
        [("complete", {"summary": "Prepared."})],
    ]


def finder(file_id, document, quote):
    return ("record_document", {"document": document, "status": "present", "files": [file_id],
                                "citations": [{"file": file_id, "quote": quote}], "note": ""})


class AppTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.env = {"CASEPATH_DATA_DIR": self.directory.name, "CASEPATH_WORKFLOW_CATALOGUE": str(FIXTURES), "CASEPATH_DEV_USER": "dev"}

    def tearDown(self):
        self.directory.cleanup()

    def client(self, **env):
        return TestClient(create_app(load_settings({**self.env, **env}), model_factory=lambda: None))

    def wait(self, client, run_id):
        for _ in range(200):
            state = client.get(f"/api/runs/{run_id}").json()
            if state["status"] not in ("queued", "running"):
                return state
            time.sleep(0.02)
        self.fail("run did not finish")

    def new_case(self, client, title):
        case = client.post("/api/cases", json={"title": title}).json()
        uploaded = client.post(f"/api/cases/{case['id']}/files", files={"file": ("message.eml", EMAIL, "message/rfc822")}).json()
        client.put(f"/api/cases/{case['id']}/workflow", json={"workflow_id": "example-defect"})
        return case, uploaded

    def run_with(self, client, case_id, model):
        client.app.state.runs.model_factory = lambda: model
        state = self.wait(client, client.post(f"/api/cases/{case_id}/runs").json()["id"])
        self.assertEqual(state["status"], "completed", state.get("error"))
        return state

    def test_sign_in_is_required(self):
        self.assertEqual(self.client(CASEPATH_DEV_USER="").get("/api/cases").status_code, 503)
        gateway = self.client(CASEPATH_DEV_USER="", CASEPATH_IDENTITY_HEADER="x-identity")
        self.assertEqual(gateway.get("/api/cases").status_code, 401)
        self.assertEqual(gateway.get("/api/cases", headers={"x-identity": "u1"}).status_code, 200)

    def test_learning_reuse_and_edits_across_cases(self):
        client = self.client()
        # Case A: the team runs, and the result checker proposes a document need.
        case_a, file_a = self.new_case(client, "Case A")
        self.assertEqual(client.get(f"/api/files/{file_a['id']}/original").content, EMAIL)
        run_a = self.run_with(client, case_a["id"], ScriptedModel(team_script(file_a["id"], learn_rows=[
            learn(title="Ventilation record", why="Mould returns despite ventilation.", step="assess",
                  citations=[{"file": file_a["id"], "quote": VENT}])])))
        self.assertEqual(run_a["result"]["evaluation"]["outcome"]["id"], "reported")
        self.assertTrue(any(e["agent"] == "document_finder" for e in run_a["events"]))
        item, = client.get("/api/knowledge", params={"status": "candidate"}).json()["knowledge"]
        self.assertEqual((item["content"]["title"], item["origin"]["case_id"]), ("Ventilation record", case_a["id"]))
        active = client.post(f"/api/knowledge/{item['id']}/activate", json={"reason": "Seen often."}).json()
        self.assertEqual(active["status"], "active")

        # Case B: the learned need is part of its process, and the run confirms it.
        case_b, file_b = self.new_case(client, "Case B")
        need = f"k-{item['id']}"
        before = client.get(f"/api/cases/{case_b['id']}").json()
        self.assertIn(need, {d["id"] for d in before["process"]["documents"]})
        run_b = self.run_with(client, case_b["id"], ScriptedModel(team_script(file_b["id"], finder_calls=[finder(file_b["id"], need, VENT)])))
        row = next(d for d in run_b["result"]["evaluation"]["documents"] if d["document"] == need)
        self.assertEqual(row["status"], "present")
        stats = client.get(f"/api/knowledge/{item['id']}").json()
        self.assertEqual((stats["item"]["stats"]["uses"], stats["item"]["stats"]["confirmed"]), (1, 1))
        self.assertEqual(stats["uses"][0]["outcome"], "present")

        # An employee adds a need for similar cases; the existing files are re-checked for it.
        store = client.app.state.store
        refused = client.post(f"/api/cases/{case_b['id']}/edits", json={"op": "add_document", "args": {"title": "Lease", "why": "x", "step": "nowhere"},
                                                                          "reason": "Needed."})
        self.assertEqual(refused.status_code, 422)
        self.assertEqual(store.list_edits(case_b["id"]), [])
        recheck_finder = lambda: {"document": "e-" + store.list_edits(case_b["id"])[-1]["id"], "status": "present",
                                  "files": [file_b["id"]], "citations": [{"file": file_b["id"], "quote": LEASE}], "note": ""}
        client.app.state.runs.model_factory = lambda: ScriptedModel([[("record_document", recheck_finder), report("document_finder")]])
        body = {"op": "add_document", "args": {"title": "Lease", "why": "Shows who rents the flat.", "step": "assess"},
                "reason": "Protekta needs the lease for defect claims.", "use_for_similar": True, "activate": True}
        changed = client.post(f"/api/cases/{case_b['id']}/edits", json=body).json()
        added, = changed["diff"]["documents_added"]
        self.assertEqual((added["title"], added["status"]), ("Lease", "missing"))
        self.assertEqual(changed["knowledge"]["status"], "active")
        recheck = self.wait(client, changed["recheck"]["id"])
        self.assertEqual(recheck["status"], "completed", recheck.get("error"))
        after = client.get(f"/api/cases/{case_b['id']}").json()
        self.assertEqual(next(d for d in after["evaluation"]["documents"] if d["document"] == added["document"])["status"], "present")

        # The next case of the family gets the employee's need too; undo removes it from case B only.
        case_c, _ = self.new_case(client, "Case C")
        titles = {d["title"] for d in client.get(f"/api/cases/{case_c['id']}").json()["process"]["documents"]}
        self.assertTrue({"Lease", "Ventilation record"} <= titles)
        undone = client.post(f"/api/edits/{changed['edit']['id']}/undo").json()
        self.assertEqual(undone["diff"]["documents_removed"][0]["document"], added["document"])

        card = scorecard(CaseStore(self.directory.name), "salt")
        self.assertEqual(len(card["runs"]), 2)
        self.assertNotIn("Schimmel", json.dumps(card))
        self.assertNotIn("Ventilation", json.dumps(card))

    def test_unconfigured_model_fails_with_a_reason(self):
        client = self.client()
        case = client.post("/api/cases", json={"title": "x"}).json()
        client.post(f"/api/cases/{case['id']}/files", files={"file": ("m.txt", b"some text here", "text/plain")})
        state = self.wait(client, client.post(f"/api/cases/{case['id']}/runs").json()["id"])
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
