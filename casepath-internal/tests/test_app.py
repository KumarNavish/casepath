import json
from pathlib import Path
import tempfile
import time
import unittest

from fastapi.testclient import TestClient

from casepath.web.app import create_app
from casepath.config import load_settings
from casepath.quality.scorecard import ScorecardLeak, guard, scorecard
from casepath.web.store import CaseStore
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
        [("record_fact", {"part": None, "fact": "landlord_notified", "status": "established", "value": "yes",
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

    def test_the_case_report_carries_each_finding_with_its_source(self):
        import io
        import re
        import zipfile
        client = self.client()
        case, file = self.new_case(client, "Schimmel im Bad")
        def document(**params):
            response = client.get(f"/api/cases/{case['id']}/report.docx", params=params)
            return response, re.sub(r"<[^>]+>", " ", zipfile.ZipFile(io.BytesIO(response.content)).read("word/document.xml").decode())
        self.assertIn("noch nicht vorbereitet", document()[1])
        self.run_with(client, case["id"], ScriptedModel(team_script(file["id"], finder_calls=[finder(file["id"], "customer_message", QUOTE)])))
        response, text = document()
        self.assertEqual(response.status_code, 200)
        self.assertIn("Fallbericht.docx", response.headers["content-disposition"])
        for expected in ("Fallbericht: Schimmel im Bad", "Stand im Prozess", "Dokumenten-Checkliste", "Belegte Fakten", "belegt",
                         "nichts wurde versendet", "message.eml", "fehlt"):
            self.assertIn(expected, text)
        self.assertEqual(text.count(QUOTE), 2)  # the fact and the document each name their exact passage
        self.assertIn("Case report", document(lang="en")[1])

    def test_sign_in_is_required(self):
        self.assertEqual(self.client(CASEPATH_DEV_USER="").get("/api/cases").status_code, 503)
        gateway = self.client(CASEPATH_DEV_USER="", CASEPATH_IDENTITY_HEADER="x-identity")
        self.assertEqual(gateway.get("/api/cases").status_code, 401)
        self.assertEqual(gateway.get("/api/cases", headers={"x-identity": "u1"}).status_code, 200)

    def test_a_gateway_token_names_the_user_and_must_carry_the_access_role(self):
        import base64

        def token(claims):
            body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
            return f"Bearer e30.{body}.sig"
        gateway = self.client(CASEPATH_DEV_USER="", CASEPATH_IDENTITY_HEADER="x-identity", CASEPATH_IDENTITY_FORMAT="jwt",
                              CASEPATH_IDENTITY_USER_CLAIM="preferred_username", CASEPATH_IDENTITY_ROLES_CLAIM="realm_access.roles",
                              CASEPATH_REQUIRED_ROLE="casepath-user")
        allowed = {"x-identity": token({"preferred_username": "u123", "realm_access": {"roles": ["casepath-user"]}})}
        self.assertEqual(gateway.get("/api/me", headers=allowed).json(), {"user": "u123"})
        other = {"x-identity": token({"preferred_username": "u456", "realm_access": {"roles": ["other"]}})}
        self.assertEqual(gateway.get("/api/cases", headers=other).status_code, 403)
        self.assertEqual(gateway.get("/api/cases", headers={"x-identity": "not a token"}).status_code, 401)
        from casepath.config import SettingsError
        with self.assertRaises(SettingsError):  # a role cannot be checked on a plain user id
            load_settings({**self.env, "CASEPATH_DEV_USER": "", "CASEPATH_IDENTITY_HEADER": "x-identity", "CASEPATH_REQUIRED_ROLE": "r"})

    def test_a_pilot_is_open_to_its_named_group_only(self):
        pilot = self.client(CASEPATH_DEV_USER="", CASEPATH_IDENTITY_HEADER="X-Forwarded-Email",
                            CASEPATH_ALLOWED_USERS="anna.muster@example.ch, Beat.Beispiel@example.ch")
        self.assertEqual(pilot.get("/api/me", headers={"X-Forwarded-Email": "beat.beispiel@example.ch"}).json(), {"user": "beat.beispiel@example.ch"})
        self.assertEqual(pilot.get("/api/cases", headers={"X-Forwarded-Email": "someone.else@example.ch"}).status_code, 403)

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

    def test_case_worker_feedback_is_kept_per_item_and_only_counted_in_the_scorecard(self):
        client = self.client()
        case, uploaded = self.new_case(client, "Feedback")
        run = self.run_with(client, case["id"], ScriptedModel(team_script(uploaded["id"])))
        url = f"/api/runs/{run['id']}/feedback"
        self.assertEqual(client.put(url, json={"target": "fact:landlord_notified", "verdict": "correct"}).status_code, 200)
        client.put(url, json={"target": "answer", "verdict": "correct"})
        client.put(url, json={"target": "answer", "verdict": "wrong", "note": "Die Frist ist falsch gelesen."})
        client.put(url, json={"target": "summary:0", "verdict": "wrong"})
        client.put(url, json={"target": "summary:0", "verdict": None})
        events = client.get(f"/api/cases/{case['id']}/events").json()["events"]
        self.assertEqual([e["kind"] for e in events][-4:], ["item.confirmed", "item.corrected", "item.corrected", "correction.undone"])
        self.assertEqual((events[-3]["item_id"], events[-3]["reason"], events[-3]["note_present"]), ("answer:0", "none", True))
        self.assertTrue(all(e["schema"] == "casepath.study.event/1" and e["parity_sha"] and e["frozen_run_id"] == run["id"] for e in events))
        self.assertEqual(client.post(f"/api/cases/{case['id']}/events", json={"kind": "note.added", "item_id": "fact:frist",
                                                                            "fields": {"text": "Datum prüfen", "reason": "5"}}).status_code, 201)
        self.assertEqual(client.post(f"/api/cases/{case['id']}/events", json={"kind": "made.up"}).status_code, 422)
        self.assertEqual(client.post(f"/api/cases/{case['id']}/events", json={"kind": "reveal"}).status_code, 422)
        own = client.post(f"/api/cases/{case['id']}/own-answer", json={"step": "notice", "documents": ["photo"], "action_kind": "request"})
        self.assertEqual([e["kind"] for e in own.json()["events"]], ["unaided.saved", "unaided.frozen", "reveal"])
        self.assertEqual(len(own.json()["events"][1]["answer_sha256"]), 64)
        self.assertEqual(client.post(f"/api/cases/{case['id']}/own-answer", json={"step": "intake"}).status_code, 409)
        changed = client.post(f"/api/cases/{case['id']}/edits", json={"op": "set_fact", "args": {"fact": "landlord_notified", "value": "nein"},
                                                                     "reason": "", "reason_code": "1", "recheck": False})
        self.assertEqual(changed.status_code, 201, changed.text)
        changed = changed.json()
        self.assertNotEqual(changed["diff"]["outcome"]["before"], changed["diff"]["outcome"]["after"])
        facts = {i["key"]: i for i in client.get(f"/api/cases/{case['id']}").json()["items"] if i["kind"] == "fact"}
        self.assertEqual((facts["landlord_notified"]["value"], facts["landlord_notified"]["origin"]), (False, f"edit#{changed['edit']['id']}"))
        corrected = [e for e in client.get(f"/api/cases/{case['id']}/events").json()["events"] if e.get("edit_id") == changed["edit"]["id"]][0]
        self.assertEqual((corrected["kind"], corrected["reason"], corrected["before"], corrected["after"]), ("item.corrected", "1", True, False))
        client.post(f"/api/edits/{changed['edit']['id']}/undo")
        facts = {i["key"]: i for i in client.get(f"/api/cases/{case['id']}").json()["items"] if i["kind"] == "fact"}
        self.assertEqual(facts["landlord_notified"]["origin"], "workflow")
        self.assertEqual(client.put(url, json={"target": "Der Vermieter", "verdict": "wrong"}).status_code, 422)
        self.assertEqual(client.put(url, json={"target": "answer", "verdict": "maybe"}).status_code, 422)
        rows = client.get(f"/api/cases/{case['id']}").json()["feedback"]
        self.assertEqual({(r["target"], r["verdict"]) for r in rows}, {("fact:landlord_notified", "correct"), ("answer", "wrong")})
        card = scorecard(client.app.state.store, "salt")["runs"][0]
        self.assertEqual(card["feedback"], {"fact": {"correct": 1, "wrong": 0}, "answer": {"correct": 0, "wrong": 1}})
        self.assertNotIn("Frist", json.dumps(card))

    def test_deleting_a_case_removes_what_was_derived_from_it(self):
        client = self.client()
        case, uploaded = self.new_case(client, "To delete")
        run = self.run_with(client, case["id"], ScriptedModel(team_script(uploaded["id"], learn_rows=[
            learn(title="Lüftungsprotokoll", why="Zeigt, wie gelüftet wurde.", citations=[{"file": uploaded["id"], "quote": VENT}])])))
        client.put(f"/api/runs/{run['id']}/feedback", json={"target": "answer", "verdict": "correct"})
        store = client.app.state.store
        self.assertEqual(len(store.list_knowledge()), 1)
        digest = store.get_file(uploaded["id"])["sha256"]
        removed = client.delete(f"/api/cases/{case['id']}").json()
        self.assertEqual((removed["runs"], removed["files"], removed["knowledge"]), (1, 1, 1))
        self.assertEqual(client.get(f"/api/cases/{case['id']}").status_code, 404)
        self.assertEqual(store.list_knowledge(), [])
        self.assertFalse((Path(self.directory.name) / "files" / digest[:2] / digest).exists())
        self.assertEqual(client.delete(f"/api/cases/{case['id']}").status_code, 404)
        record, = store.deletions()  # what remains says only that the case existed, when, who deleted it and how much went
        self.assertEqual((record["case_id"], record["deleted_by"], record["reason"], record["removed"]["runs"]), (case["id"], "dev", "request", 1))
        self.assertNotIn("To delete", json.dumps(record))

    def test_retention_deletes_cases_unchanged_for_too_long(self):
        store = CaseStore(self.directory.name)
        old, recent = store.create_case("old", {}, "dev"), store.create_case("recent", {}, "dev")
        store._db.execute("update cases set updated_at='2014-01-01T00:00:00+00:00' where id=?", (old["id"],))
        self.assertEqual(store.purge("2015-01-01T00:00:00+00:00", dry_run=True), {"due": 1, "deleted": 0, "busy": 0})
        self.assertEqual(store.purge("2015-01-01T00:00:00+00:00")["deleted"], 1)
        self.assertEqual([c["id"] for c in store.list_cases()], [recent["id"]])
        self.assertEqual(store.deletions()[0]["reason"], "retention")

    def test_restart_marks_unfinished_runs(self):
        store = CaseStore(self.directory.name)
        case = store.create_case("x", {}, "dev")
        run = store.create_run(case["id"], "dev")
        self.client()
        self.assertEqual(CaseStore(self.directory.name).get_run(run["id"])["status"], "interrupted")


    def test_a_large_pdf_is_offered_in_parts_and_each_part_is_a_small_pdf(self):
        from unittest import mock
        from tests.test_cut import pages_with_a_heavy_first_page
        client = self.client()
        case = client.post("/api/cases", json={"title": "Gross"}).json()
        data = pages_with_a_heavy_first_page(3)
        pdf = client.post(f"/api/cases/{case['id']}/files", files={"file": ("akte.pdf", data, "application/pdf")}).json()
        url = f"/api/files/{pdf['id']}/original"
        self.assertEqual(client.get(url).content, data)  # under the limit: the whole file
        with mock.patch("casepath.web.app.SERVED_WHOLE_BYTES", 100_000):
            index = client.get(url)
            self.assertIn("text/html", index.headers["content-type"])
            self.assertIn('?pages=1-1"', index.text)
            part = client.get(url + "?pages=2-3")
            self.assertEqual(part.headers["content-type"], "application/pdf")
            self.assertLess(len(part.content), 5_000)
            self.assertEqual(client.get(url + "?pages=7").status_code, 422)

    def test_a_cut_is_a_new_pdf_without_the_later_pages(self):
        from tests.test_cut import pages_with_a_heavy_first_page
        client = self.client()
        case = client.post("/api/cases", json={"title": "Akte"}).json()
        client.post(f"/api/cases/{case['id']}/files", files={"file": ("akte.pdf", pages_with_a_heavy_first_page(3), "application/pdf")})
        cut_case = client.post(f"/api/cases/{case['id']}/cut", json={"pages": "2-3"}).json()
        cut_file, = client.get(f"/api/cases/{cut_case['id']}").json()["files"]
        data = client.get(f"/api/files/{cut_file['id']}/original").content
        self.assertLess(len(data), 5_000)
        self.assertNotIn(b"Seite 1", data)  # the dropped page is not hidden in the file, it is gone
        self.assertIn(b"Seite 3", client.get(f"/api/files/{cut_file['id']}/original?pages=3").content)  # original numbering
        self.assertEqual(client.get(f"/api/files/{cut_file['id']}/original?pages=1").status_code, 422)

    def test_replay_shows_what_a_knowledge_proposal_would_change_on_stored_runs_without_a_model(self):
        from casepath.quality.replay import replay
        client = self.client()
        case, file = self.new_case(client, "Replay")
        self.run_with(client, case["id"], ScriptedModel(team_script(file["id"])))
        store, catalogue = client.app.state.store, client.app.state.catalogue
        unchanged, = replay(store, catalogue, (), {case["id"]})
        self.assertEqual(unchanged["changed"], {})
        proposal = [{"id": "kn_test", "family": "example-defect", "kind": "document_need", "status": "proposed", "version": 1,
                     "origin": {}, "applies_when": None, "content": {"title": "Wohnungsabnahmeprotokoll", "why": "Zeigt den Zustand."}}]
        row, = replay(store, catalogue, proposal, {case["id"]})
        self.assertIn("k-kn_test", row["after"]["needs"])
        self.assertNotIn("k-kn_test", row["before"]["needs"])
        self.assertTrue(row["changed"])

    def test_a_correction_marked_generally_so_becomes_a_proposal_with_its_replayed_effect(self):
        client = self.client()
        case, file = self.new_case(client, "Generell")
        self.run_with(client, case["id"], ScriptedModel(team_script(file["id"])))
        client.app.state.runs.model_factory = lambda: None
        body = {"op": "add_document", "args": {"title": "Wohnungsabnahmeprotokoll", "why": "Zeigt den Zustand bei Einzug.", "step": "assess"},
                "reason": "", "reason_code": "4", "recheck": False}
        changed = client.post(f"/api/cases/{case['id']}/edits", json=body).json()
        proposal = changed["knowledge"]
        self.assertEqual(proposal["status"], "candidate")  # proposed, never active by itself
        self.assertEqual((proposal["replay"]["because"], proposal["replay"]["cases"]), ("gilt generell", 1))
        plain = client.post(f"/api/cases/{case['id']}/edits", json={**body, "reason_code": "3", "args": {**body["args"], "title": "Anderes"}}).json()
        self.assertIsNone(plain["knowledge"])  # a correction for this case only stays in the case

    def test_the_auswertung_is_content_free_and_the_app_reports_its_manifest(self):
        client = self.client()
        case, file = self.new_case(client, "Auswertung Fall mit Namen")
        self.run_with(client, case["id"], ScriptedModel(team_script(file["id"])))
        client.post(f"/api/cases/{case['id']}/events", json={"kind": "case.opened"})
        client.post(f"/api/cases/{case['id']}/events", json={"kind": "item.exposed", "item_id": "document:notice_letter"})
        client.post(f"/api/cases/{case['id']}/events", json={"kind": "source.opened", "item_id": "document:notice_letter"})
        page = client.get("/api/auswertung").json()
        card, = page["cases"]
        self.assertEqual((card["accepted_unchanged"], card["sources_opened"], card["interventions"]), ({"document": 1}, 1, 0))
        self.assertTrue(card["case"].startswith("h_") and case["id"] not in json.dumps(page) and "Namen" not in json.dumps(page))
        profile = client.get("/api/run-profile").json()
        self.assertEqual((profile["runs"], set(profile["median_seconds"])), (1, {"lesen", "prozess", "fakten", "unterlagen", "pruefung"}))
        self.assertEqual(client.get("/api/run-profile", params={"pages": 3}).json()["band"], "alle")  # fewer than three of that size
        manifest = client.get("/api/manifest").json()
        self.assertEqual(manifest["format"], "casepath.parity/1")
        self.assertIn("source_tree_sha256", manifest)

    def test_a_study_copy_shows_the_frozen_run_and_refuses_to_start_when_its_items_differ(self):
        client = self.client()
        case, file = self.new_case(client, "Studienfall")
        self.run_with(client, case["id"], ScriptedModel(team_script(file["id"])))
        self.assertEqual(client.post(f"/api/cases/{case['id']}/study-copy", json={"expert": "E1"}).status_code, 409)  # not frozen yet
        frozen = client.post(f"/api/cases/{case['id']}/freeze").json()
        copy = client.post(f"/api/cases/{case['id']}/study-copy", json={"expert": "E1"}).json()
        shown = client.get(f"/api/cases/{copy['id']}").json()
        self.assertEqual((shown["run"]["id"], shown["items_sha256"]), (frozen["frozen_run_id"], frozen["items_sha256"]))
        self.assertTrue(client.get(f"/api/cases/{copy['id']}/study-check").json()["ok"])
        self.assertEqual(client.post(f"/api/cases/{copy['id']}/runs").status_code, 409)  # never a run of its own
        from unittest import mock
        self.assertEqual(client.post(f"/api/cases/{copy['id']}/events", json={"kind": "session.started"}).status_code, 409)  # no fixed salt
        mock.patch.dict("os.environ", {"CASEPATH_SCORECARD_SALT": "kept-inside"}).start()
        self.addCleanup(mock.patch.stopall)
        self.assertEqual(client.post(f"/api/cases/{copy['id']}/events", json={"kind": "session.started"}).status_code, 201)
        client.put(f"/api/cases/{copy['id']}/workflow", json={"workflow_id": "example-defect"})
        client.post(f"/api/cases/{copy['id']}/edits", json={"op": "set_fact", "args": {"fact": "landlord_notified", "value": "nein"},
                                                         "reason": "", "reason_code": "1", "recheck": False})
        check = client.get(f"/api/cases/{copy['id']}/study-check").json()
        self.assertFalse(check["ok"])  # the copy's items moved away from the frozen run
        self.assertEqual(client.post(f"/api/cases/{copy['id']}/events", json={"kind": "session.started"}).status_code, 409)
        plan = client.get("/api/study/plan", params={"expert": "E2", "position": 1}).json()
        self.assertEqual([(s["case"], s["own_answer_first"]) for s in plan["steps"]], [(case["id"], True)])  # one frozen case here
        self.assertFalse(plan["ready"])  # no practice case and not three cases: the study cannot open

    def test_a_finished_run_cannot_be_stopped(self):
        client = self.client()
        case, file = self.new_case(client, "Anhalten")
        run = self.run_with(client, case["id"], ScriptedModel(team_script(file["id"])))
        self.assertEqual(client.post(f"/api/runs/{run['id']}/stop").status_code, 409)
        self.assertEqual(client.post(f"/api/cases/{case['id']}/events", json={"kind": "note.added", "text": "x"}).status_code, 422)  # extras go in "fields"
        self.assertEqual(client.post(f"/api/cases/{case['id']}/events", json={"kind": "note.added", "fields": {"text": "x"}}).status_code, 201)

    def test_a_paused_run_shows_what_it_established_never_an_empty_case(self):
        client = self.client()
        case, file = self.new_case(client, "Angehalten")
        store = client.app.state.store
        run = store.create_run(case["id"], "dev")
        partial = {"paused": True, "brief": {"request": "Schimmel im Bad", "parties": [], "timeline": [], "summary": "", "not_enclosed": []},
                   "facts": [{"fact": "landlord_notified", "status": "established", "value": True, "verdict": "accepted",
                              "citations": [{"file": file["id"], "quote": "informiert"}]}], "documents": [], "usage": [], "events": []}
        store.update_run(run["id"], status="paused", result=partial, workflow_id="example-defect", workflow_version="2026-01-01")
        shown = client.get(f"/api/cases/{case['id']}")
        self.assertEqual(shown.status_code, 200)
        body = shown.json()
        self.assertIsNotNone(body["process"])  # never "noch kein Prozess"
        self.assertEqual(body["run"]["status"], "paused")
        facts = {i["key"]: i for i in body["items"] if i["kind"] == "fact"}
        self.assertEqual(facts["landlord_notified"]["value"], True)
        self.assertTrue(body["items_sha256"])  # built from what exists
        self.assertFalse([i for i in body["items"] if i["kind"] == "answer"])  # no assessment yet

    def test_weiter_continues_a_paused_run_without_redoing_its_finished_steps(self):
        client = self.client()
        case, file = self.new_case(client, "Weiter")
        store = client.app.state.store
        paused = store.create_run(case["id"], "dev")
        store.update_run(paused["id"], status="paused", workflow_id="example-defect", workflow_version="2026-01-01",
                         result={"paused": True, "brief": {"request": "Check the mould defect.", "parties": [], "timeline": [], "summary": "Read.",
                                                           "not_enclosed": []},
                                 "facts": [], "documents": [], "usage": [{"agent": "claim_reader", "input_tokens": 10, "output_tokens": 2}],
                                 "events": [], "done": ["0:claim_reader"]})
        rest = team_script(file["id"])[2:]  # the brief was made before the stop: no turn for it
        client.app.state.runs.model_factory = lambda: ScriptedModel(rest)
        started = client.post(f"/api/runs/{paused['id']}/continue")
        self.assertEqual(started.status_code, 202)
        done = self.wait(client, started.json()["id"])
        self.assertEqual(done["status"], "completed", done.get("error"))
        self.assertEqual(done["routing"]["status"], "resumed")
        self.assertEqual(done["result"]["brief"]["request"], "Check the mould defect.")
        self.assertEqual(client.post(f"/api/runs/{paused['id']}/continue").status_code, 409)  # only the latest paused run
        self.assertEqual(done["result"]["resumed_from"], paused["id"])
        card, = client.get("/api/auswertung").json()["cases"]
        self.assertEqual(card["tokens_noncached"], sum(u.get("input_tokens", 0) for u in done["result"]["usage"]))  # counted once
        self.assertEqual(client.get("/api/run-profile").json()["runs"], 0)  # neither the paused nor the continued run times a stage

    def test_anderer_prozess_while_paused_keeps_the_reading_and_redoes_what_depends_on_the_process(self):
        catalogue = Path(self.directory.name) / "catalogue"
        catalogue.mkdir()
        base = json.loads((FIXTURES / "example-defect.json").read_text())
        (catalogue / "example-defect.json").write_text(json.dumps(base))
        (catalogue / "example-other.json").write_text(json.dumps({**base, "id": "example-other", "title": "Other process"}))
        client = self.client(CASEPATH_WORKFLOW_CATALOGUE=str(catalogue))
        case, file = self.new_case(client, "Anderer Prozess")
        store = client.app.state.store
        paused = store.create_run(case["id"], "dev")
        store.update_run(paused["id"], status="paused", workflow_id="example-defect", workflow_version="2026-01-01",
                         result={"paused": True, "brief": {"request": "Check the mould defect.", "parties": [], "timeline": [], "summary": "Read.",
                                                           "not_enclosed": []},
                                 "facts": [{"fact": "landlord_notified", "status": "established", "value": True, "verdict": "accepted", "citations": []}],
                                 "documents": [], "usage": [], "events": [], "done": ["0:claim_reader", "1:process_builder"]})
        client.put(f"/api/cases/{case['id']}/workflow", json={"workflow_id": "example-other"})
        rest = team_script(file["id"])[2:]  # the brief stays; the process and everything after it are done again
        client.app.state.runs.model_factory = lambda: ScriptedModel(rest)
        done = self.wait(client, client.post(f"/api/runs/{paused['id']}/continue").json()["id"])
        self.assertEqual(done["status"], "completed", done.get("error"))
        self.assertEqual(done["workflow_id"], "example-other")
        self.assertEqual(done["result"]["brief"]["request"], "Check the mould defect.")

    def test_verwerfen_brings_back_the_last_finished_result_or_an_unprepared_case(self):
        client = self.client()
        store = client.app.state.store
        partial = {"paused": True, "brief": None, "facts": [], "documents": [], "usage": [], "events": [], "done": []}
        fresh, _ = self.new_case(client, "Nie fertig")
        stopped = store.create_run(fresh["id"], "dev")
        store.update_run(stopped["id"], status="paused", workflow_id="example-defect", workflow_version="2026-01-01", result=partial)
        self.assertEqual(client.post(f"/api/runs/{stopped['id']}/discard").json()["status"], "discarded")
        bare = client.get(f"/api/cases/{fresh['id']}").json()
        self.assertEqual(bare["run"]["status"], "discarded")
        self.assertFalse([i for i in bare["items"] if i["kind"] == "fact" and i.get("value") is not None])  # not yet prepared: nothing read
        case, file = self.new_case(client, "Fertig, dann angehalten")
        finished = self.run_with(client, case["id"], ScriptedModel(team_script(file["id"])))
        again = store.create_run(case["id"], "dev")
        store.update_run(again["id"], status="paused", workflow_id="example-defect", workflow_version="2026-01-01", result=partial)
        self.assertEqual(client.get(f"/api/cases/{case['id']}").json()["run"]["id"], again["id"])
        client.post(f"/api/runs/{again['id']}/discard")
        shown = client.get(f"/api/cases/{case['id']}").json()
        self.assertEqual(shown["run"]["status"], "discarded")  # the latest run, set aside
        self.assertEqual(client.get(f"/api/cases/{case['id']}/events").json()["events"][-1]["kind"], "run.discarded")
        self.assertEqual(store.get_run(again["id"])["status"], "discarded")  # kept, never deleted
        self.assertTrue(shown["process"] and finished["id"])

    def test_the_chosen_process_is_announced_before_any_agent_reads_the_case(self):
        client = self.client()
        case, file = self.new_case(client, "Prozess zuerst")
        run = self.run_with(client, case["id"], ScriptedModel(team_script(file["id"])))
        kinds = [(e["kind"], e.get("agent")) for e in run["events"]]
        decided = kinds.index(("routing.decided", "lead"))
        first_reading = next(i for i, k in enumerate(kinds) if k == ("agent.start", "claim_reader"))
        self.assertLess(decided, first_reading)
        self.assertEqual(run["events"][decided]["workflow"], "example-defect")

    def test_speed_trials_are_named_with_every_run_in_the_manifest_the_profile_and_the_study_check(self):
        trial = self.client(CASEPATH_SPEED_TRIALS="result_without_files")
        case, file = self.new_case(trial, "Versuch")
        run = self.run_with(trial, case["id"], ScriptedModel(team_script(file["id"])))
        self.assertEqual(run["result"]["speed_trials"], ["result_without_files"])
        self.assertEqual(trial.get("/api/manifest").json()["speed_trials"], ["result_without_files"])
        self.assertEqual(trial.get("/api/run-profile").json()["runs"], 1)
        plain = self.client()  # the same store, no trial: the trial's run is not mixed into its timing
        self.assertEqual(plain.get("/api/run-profile").json()["runs"], 0)
        self.assertEqual(plain.get("/api/manifest").json()["speed_trials"], [])
        plain.post(f"/api/cases/{case['id']}/freeze")  # frozen without trials
        copy = plain.post(f"/api/cases/{case['id']}/study-copy", json={"expert": "E1"}).json()
        self.assertTrue(plain.get(f"/api/cases/{copy['id']}/study-check").json()["ok"])
        self.assertFalse(trial.get(f"/api/cases/{copy['id']}/study-check").json()["ok"])  # a deployment with a trial the freeze did not name

    def test_a_case_on_the_handler_workflow_carries_its_draft_and_its_file_note(self):
        from tests.test_handler_workflow import intake
        catalogue = Path(self.directory.name) / "catalogue"
        catalogue.mkdir()
        (catalogue / "osm-mold.json").write_text(json.dumps(intake()))  # the handler's workflow joins when it supersedes the intake
        client = self.client(CASEPATH_WORKFLOW_CATALOGUE=str(catalogue))
        case = client.post("/api/cases", json={"title": "Schimmel"}).json()
        client.post(f"/api/cases/{case['id']}/files", files={"file": ("message.eml", EMAIL, "message/rfc822")})
        store = client.app.state.store
        run = store.create_run(case["id"], "dev")
        fact = lambda f, v: {"fact": f, "status": "established", "verdict": "accepted", "value": v, "citations": []}
        store.update_run(run["id"], status="completed", workflow_id="mietmangel-handler", workflow_version=None, finished_at="2026-11-12T10:00:00+00:00",
                         result={"facts": [fact("rechtsgebiet", "Mietrecht / Mangel"), fact("maengelruege_schriftlich", "ja")], "documents": [],
                                 "brief": {"request": "Schimmel im Bad.", "parties": [], "timeline": []},
                                 "deadlines": [{"fact": "frist_vermieter", "date": "2024-01-15", "question": "Frist der Vermieterschaft"}]})
        shown = client.get(f"/api/cases/{case['id']}").json()
        self.assertEqual(shown["draft"]["kind"], "A1")
        self.assertIn("Um die Versicherungsdeckung prüfen", shown["draft"]["text"])
        self.assertTrue(shown["file_note"].startswith("Eingegangen: message.eml."))
        row = next(r for r in client.get("/api/cases").json()["cases"] if r["id"] == case["id"])
        self.assertEqual((row["next_date"], row["next_date_kind"]), ("2024-01-15", "frist"))  # a stored deadline before the follow-up comes first

    def test_a_new_file_is_announced_and_a_second_preparation_shows_what_changed(self):
        client = self.client()
        case, file = self.new_case(client, "Ankunft")
        self.run_with(client, case["id"], ScriptedModel(team_script(file["id"])))
        self.assertEqual(client.get(f"/api/cases/{case['id']}").json()["new_files"], [])
        time.sleep(1.1)  # stored times are to the second
        client.post(f"/api/cases/{case['id']}/files", files={"file": ("notice.eml", b"Subject: Notice\n\nI told the landlord.", "message/rfc822")})
        shown = client.get(f"/api/cases/{case['id']}").json()
        self.assertEqual(shown["new_files"], ["notice.eml"])
        self.assertIsNone(shown["changes"])  # one preparation so far: nothing to compare
        second = self.run_with(client, case["id"], ScriptedModel(team_script(file["id"], finder_calls=[
            finder(file["id"], "customer_message", "Subject: Schimmel im Bad")])))
        self.assertEqual(second["status"], "completed")
        after = client.get(f"/api/cases/{case['id']}").json()
        self.assertEqual(after["new_files"], [])
        self.assertEqual(set(after["changes"]), {"added", "changed", "removed"})
        self.assertTrue(after["changes"]["changed"] or after["changes"]["added"])  # the customer message is now found

    def test_andere_handlung_changes_the_draft_and_the_date_and_is_logged_with_its_reason(self):
        from tests.test_handler_workflow import intake
        catalogue = Path(self.directory.name) / "catalogue"
        catalogue.mkdir()
        (catalogue / "osm-mold.json").write_text(json.dumps(intake()))
        client = self.client(CASEPATH_WORKFLOW_CATALOGUE=str(catalogue))
        case = client.post("/api/cases", json={"title": "Andere Handlung"}).json()
        client.post(f"/api/cases/{case['id']}/files", files={"file": ("message.eml", EMAIL, "message/rfc822")})
        store = client.app.state.store
        run = store.create_run(case["id"], "dev")
        fact = lambda f, v: {"fact": f, "status": "established", "verdict": "accepted", "value": v, "citations": []}
        store.update_run(run["id"], status="completed", workflow_id="mietmangel-handler", finished_at="2026-11-12T10:00:00+00:00",
                         result={"facts": [fact("rechtsgebiet", "Mietrecht / Mangel")], "documents": [],
                                 "brief": {"request": "Schimmel im Bad.", "parties": [], "timeline": []}})
        before = client.get(f"/api/cases/{case['id']}").json()
        kinds = {o["kind"]: o for o in before["action_options"]}
        self.assertEqual(before["draft"]["kind"], "A1")
        self.assertEqual(before["draft"]["needs"], [])  # the first request does not wait for the cover decision (it registers provisionally)
        self.assertTrue({"A1", "A5", "A6"} <= set(kinds))  # this stage, its follow-up and the next stage
        self.assertEqual(client.post(f"/api/cases/{case['id']}/action", json={"kind": "A10", "reason_code": "1"}).status_code, 422)  # not near
        self.assertEqual(client.post(f"/api/cases/{case['id']}/action", json={"kind": "A5", "reason_code": "5"}).status_code, 201)
        after = client.get(f"/api/cases/{case['id']}").json()
        self.assertEqual(after["draft"]["kind"], "A5")
        self.assertEqual(after["draft"]["needs"], ["deckung"])  # the assessment does
        self.assertIn("Grundsätzlich hat die Mieterschaft", after["draft"]["text"])
        self.assertNotEqual(after["follow_up"]["due"], before["follow_up"]["due"])  # A5's own days, not A1's
        log = client.get(f"/api/cases/{case['id']}/events").json()["events"]
        self.assertEqual((log[-1]["kind"], log[-1]["item_id"], log[-1]["chosen"], log[-1]["reason"]), ("item.corrected", "next_action:0", "A5", "5"))
        if "A2" in kinds:  # a kind without a draft says why
            client.post(f"/api/cases/{case['id']}/action", json={"kind": "A2", "reason_code": "1"})
            self.assertTrue(client.get(f"/api/cases/{case['id']}").json()["draft"]["none"])

    def test_files_dropped_on_the_case_list_make_a_case_named_from_the_mail_and_start_its_preparation(self):
        client = self.client()
        created = client.post("/api/cases/from-files", files=[("files", ("message.eml", EMAIL, "message/rfc822")),
                                                              ("files", ("Foto.jpg", b"\xff\xd8\xff\xe0 not much", "image/jpeg"))])
        self.assertEqual(created.status_code, 201, created.text)
        body = created.json()
        self.assertEqual(body["case"]["title"], "Schimmel im Bad")  # the first e-mail's subject
        self.assertEqual([f["name"] for f in body["files"]], ["message.eml", "Foto.jpg"])
        self.assertIsNotNone(body["run"])  # preparation started at once
        self.assertEqual(client.get(f"/api/cases/{body['case']['id']}").json()["run"]["id"], body["run"]["id"])
        named = client.post("/api/cases/from-files", files=[("files", ("Mietvertrag Kramgasse.pdf", b"%PDF-1.4 x", "application/pdf"))]).json()
        self.assertEqual(named["case"]["title"], "Mietvertrag Kramgasse")  # no e-mail: the first file's name
        self.assertEqual(client.put(f"/api/cases/{named['case']['id']}/title", json={"title": "Mangel Kramgasse 5"}).json()["title"], "Mangel Kramgasse 5")
        self.assertEqual(client.put(f"/api/cases/{named['case']['id']}/title", json={"title": ""}).status_code, 422)
        self.assertEqual(client.post("/api/cases/from-files", files=[("files", ("leer.txt", b"", "text/plain"))]).status_code, 422)
        listed = {c["id"]: c for c in client.get("/api/cases").json()["cases"]}
        self.assertIn("closed", listed[named["case"]["id"]])


class RoutingTests(unittest.TestCase):
    def test_an_example_workflow_never_competes_with_real_ones(self):
        import copy
        from casepath.process.workflows import Catalogue, route

        example = Catalogue.load(FIXTURES).get("example-defect")
        real = {**copy.deepcopy(example), "id": "real-defect", "example": False}
        self.assertEqual(route(Catalogue((example,)), {"legal_area": "tenancy_defect"})["workflow"]["id"], "example-defect")
        decision = route(Catalogue((example, real)), {"legal_area": "tenancy_defect"})
        self.assertEqual((decision["status"], decision["workflow"]["id"]), ("selected", "real-defect"))


class ContractTests(unittest.TestCase):
    def test_the_saved_contract_matches_the_api(self):
        from casepath.web.app import CONTRACT, case_api_contract

        def shape(spec):  # operations, parameters and request fields; free of library-version details
            rows = set()
            for path, methods in spec["paths"].items():
                for method, op in methods.items():
                    params = tuple(sorted(p["name"] for p in op.get("parameters", [])))
                    body = (op.get("requestBody") or {}).get("content", {})
                    ref = next(iter(body.values()), {}).get("schema", {}).get("$ref", "")
                    fields = tuple(sorted(spec["components"]["schemas"][ref.split("/")[-1]]["properties"])) if ref else ()
                    rows.add((path, method, params, fields))
            return rows
        self.assertEqual(shape(json.loads(case_api_contract())), shape(json.loads(CONTRACT.read_text())),
                         "the API changed: run python -m casepath contract --write and review the diff")


class GuardTests(unittest.TestCase):
    def test_free_text_cannot_leave(self):
        self.assertEqual(guard({"status": "completed", "n": 3, "file": "h_0123456789ab"}),
                         {"status": "completed", "n": 3, "file": "h_0123456789ab"})
        for leak in ({"note": "Der Vermieter hat nie geantwortet"}, {"Name Of Tenant": 1}, ["Elin Ziegler"]):
            with self.assertRaises(ScorecardLeak):
                guard(leak)


if __name__ == "__main__":
    unittest.main()
