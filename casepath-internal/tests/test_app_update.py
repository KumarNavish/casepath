"""The case service around «Aktualisieren» and the handler's own entries (casepath/web/app.py): an update run stored with
its kind and the run it builds on, its own tokens and seconds, never mixed with full runs in the run profile; the draft
held back while new files are unread; the handler's entries written, changed and removed, each logged; the Verlauf as
one table; and the event route that accepts every item kind the screen shows.

Scripted and model-free."""
import json
from pathlib import Path
import re
import tempfile
import time
import unittest

from fastapi.testclient import TestClient

from casepath.config import load_settings
from casepath.process.items import ITEM_KINDS, SCREEN_KINDS
from casepath.web.app import create_app
from tests.scripted import ScriptedModel, report

FIXTURES = Path(__file__).parent / "fixtures"
FILE_A = ("Von: Lea Beispiel\nGesendet: Dienstag, 1. September 2026 09:12\nBetreff: Schimmel im Schlafzimmer\n\nIn meiner Wohnung an der "
          "Probegasse 7 wächst seit Juli Schimmel. Die Vermieterin Muster Immobilien AG repariert nichts.\n\n"
          "Protekta Rechtsschutz, Bern, 1. Oktober 2026: Wir erteilen der Kanzlei Muster Kostengutsprache für die Abklärung der Sach- und "
          "Rechtslage sowie aussergerichtliche Bemühungen.")
FILE_B = ("Kanzlei Muster\nZürich, 5. November 2026\n\nZwischenhonorar: Für unsere Bemühungen bis 31. Oktober 2026 stellen wir Ihnen "
          "CHF 3'200 in Rechnung. Zahlbar innert 30 Tagen.")
ENTRY = {"phone": False, "asks": [], "answers": [], "terms": [], "paid": [], "next": [], "page": None}


def full_script(fa):
    entries = [{**ENTRY, "n": 1, "file": fa, "date": "2026-09-01", "from": "kunde", "to": "versicherer", "kind": "meldung", "what": "Meldung Schimmel",
                "quote": "Betreff: Schimmel im Schlafzimmer"},
               {**ENTRY, "n": 2, "file": fa, "date": "2026-10-01", "from": "versicherer", "to": "kanzlei", "kind": "kostengutsprache",
                "what": "Kostengutsprache an Kanzlei Muster", "quote": "Protekta Rechtsschutz, Bern, 1. Oktober 2026"}]
    return ScriptedModel([
        [("record_steps", {"entries": entries}),
         ("record_fact", {"part": None, "fact": "rechtsgebiet", "status": "established", "value": "Mietrecht / Mangel",
                          "citations": [{"file": fa, "quote": "wächst seit Juli Schimmel"}]}),
         report("claim_reader", request="Schimmel; die Kanzlei Muster klärt ab.")],
        [report("document_finder")], [report("result_checker", answer="Vorbereitet.")]])


def update_script(fb):
    return ScriptedModel([
        [("record_steps", {"entries": [{**ENTRY, "n": 3, "file": fb, "date": "2026-11-05", "from": "kanzlei", "to": "versicherer", "kind": "kostenforderung",
                                         "what": "Zwischenhonorar CHF 3'200", "quote": "Zürich, 5. November 2026"}]}),
         ("record_fact", {"part": None, "fact": "eingang_kostenforderung", "status": "established",
                          "value": "Kanzlei Muster: Zwischenhonorar vom 2026-11-05 über CHF 3'200",
                          "citations": [{"file": fb, "quote": "stellen wir Ihnen CHF 3'200 in Rechnung"}]}),
         report("claim_reader", summary="Die Kanzlei stellt ihr Zwischenhonorar in Rechnung.")],
        [report("document_finder")]])


class Service(unittest.TestCase):
    """A workspace with the shipped areas and the example workflow; no tests of its own."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        catalogue = Path(self.directory.name) / "catalogue"
        catalogue.mkdir()
        (catalogue / "example-defect.json").write_text((FIXTURES / "example-defect.json").read_text())  # the shipped areas join by default
        self.client = TestClient(create_app(load_settings({"CASEPATH_DATA_DIR": str(Path(self.directory.name) / "data"),
                                                           "CASEPATH_WORKFLOW_CATALOGUE": str(catalogue), "CASEPATH_DEV_USER": "dev"}),
                                            model_factory=lambda: None))
        self.store = self.client.app.state.store

    def tearDown(self):
        self.client.app.state.runs.shutdown()
        self.store.close()
        self.directory.cleanup()

    def wait(self, run_id):
        for _ in range(300):
            run = self.client.get(f"/api/runs/{run_id}").json()
            if run["status"] not in ("queued", "running"):
                return run
            time.sleep(0.02)
        self.fail("run did not finish")

    def upload(self, case_id, name, text):
        return self.client.post(f"/api/cases/{case_id}/files", files={"file": (name, text.encode(), "text/plain")}).json()

    def prepared_case(self, workflow="mietmangel-handler"):
        case = self.client.post("/api/cases", json={"title": "Mietmangel, Mandat (synthetisch) 4321.5555.0001"}).json()
        fa = self.upload(case["id"], "Akte.txt", FILE_A)
        self.client.put(f"/api/cases/{case['id']}/workflow", json={"workflow_id": workflow})
        for fact, value in (("deckung", "bestätigt"), ("vorgehen", "Mandat an Anwaltskanzlei")):
            self.store.add_edit(case["id"], "set_fact", {"fact": fact, "value": value}, "dev", "Entscheid")
        self.client.app.state.runs.model_factory = lambda: full_script(fa["id"])
        run = self.wait(self.client.post(f"/api/cases/{case['id']}/runs").json()["id"])
        self.assertEqual(run["status"], "completed", run.get("error"))
        return case, run


class UpdateServiceTests(Service):
    def test_an_update_reads_only_the_new_file_and_is_stored_as_an_update_on_the_run_it_builds_on(self):
        case, base = self.prepared_case()
        self.assertEqual((base["kind"], base["builds_on"]), ("full", None))
        view = self.client.get(f"/api/cases/{case['id']}").json()
        self.assertEqual((view["new_files"], view["update"]["available"], view["draft_stale"]), ([], False, False))
        self.assertEqual(self.client.post(f"/api/cases/{case['id']}/update").status_code, 409)  # nothing new to read
        fb = self.upload(case["id"], "Zwischenhonorar.txt", FILE_B)
        view = self.client.get(f"/api/cases/{case['id']}").json()
        self.assertEqual([f["name"] for f in view["arrived"]], ["Zwischenhonorar.txt"])
        self.assertTrue(view["arrived"][0]["added"])
        self.assertEqual((view["update"]["available"], view["draft_stale"]), (True, True))  # the draft is held back until it ran
        listed = next(c for c in self.client.get("/api/cases").json()["cases"] if c["id"] == case["id"])
        self.assertEqual((listed["new_files"], listed["stand"]["kind"]), (1, "arrived"))
        self.client.app.state.runs.model_factory = lambda: update_script(fb["id"])
        started = self.client.post(f"/api/cases/{case['id']}/update").json()
        self.assertEqual((started["kind"], started["builds_on"]), ("update", base["id"]))
        run = self.wait(started["id"])
        self.assertEqual(run["status"], "completed", run.get("error"))
        result = run["result"]
        self.assertEqual(result["update"]["builds_on"], base["id"])
        self.assertEqual(result["update"]["files"], [fb["id"]])
        self.assertEqual(result["update"]["entries"], [3])
        self.assertEqual({u["agent"] for u in result["usage"]}, {"claim_reader", "document_finder", "source_checker"})  # its own tokens
        self.assertNotIn("learned", {k for k in result if k == "learned" and result[k] != base["result"].get("learned")})
        self.assertTrue(run["finished_at"] and run["created_at"])  # its own seconds
        view = self.client.get(f"/api/cases/{case['id']}").json()
        self.assertEqual((view["new_files"], view["draft_stale"]), ([], False))
        nxt = next(i for i in view["items"] if i["kind"] == "next_action")
        self.assertEqual((nxt["action"], nxt["value"]), ("A11", "Kostenforderung prüfen und begleichen"))
        self.assertEqual(view["changes"]["entries"], ["05.11.2026 · Kanzlei → Protekta · Kostenforderung: Zwischenhonorar CHF 3'200"])
        self.assertIn("Kostenforderung", view["changes"]["changed"])  # what came in, by its kind's title
        self.assertEqual(view["prepared_run"]["kind"], "update")
        # a full run and an update are never mixed in the run profile
        update = self.client.get("/api/run-profile", params={"kind": "update"}).json()
        full = self.client.get("/api/run-profile", params={"kind": "full", "pages": 1}).json()
        self.assertEqual((update["runs"], update["kind"], full["runs"], full["kind"]), (1, "update", 1, "full"))
        self.assertIsNotNone(update["median_total"])

    def test_a_run_made_before_the_account_needs_a_full_preparation_once(self):
        case = self.client.post("/api/cases", json={"title": "Schimmel"}).json()
        email = self.upload(case["id"], "message.txt", "Ich habe den Vermieter am 2. März schriftlich informiert.")
        self.client.put(f"/api/cases/{case['id']}/workflow", json={"workflow_id": "example-defect"})
        self.client.app.state.runs.model_factory = lambda: ScriptedModel([[report("claim_reader")], [report("process_builder")],
                                                                           [report("claim_reader")], [report("document_finder")], [report("result_checker")]])
        self.assertEqual(self.wait(self.client.post(f"/api/cases/{case['id']}/runs").json()["id"])["status"], "completed")
        self.upload(case["id"], "Nachtrag.txt", "Fotos folgen.")
        view = self.client.get(f"/api/cases/{case['id']}").json()
        self.assertEqual((view["update"]["available"], view["update"]["reason"], view["update"]["needs_full"]), (False, "full_needed", True))
        refused = self.client.post(f"/api/cases/{case['id']}/update")
        self.assertEqual(refused.status_code, 409)
        self.assertIn("einmal ganz neu vorbereiten", refused.json()["detail"])
        self.assertTrue(email["id"])

    def test_a_stopped_update_keeps_nothing_and_the_case_shows_the_run_it_built_on(self):
        case, base = self.prepared_case()
        fb = self.upload(case["id"], "Zwischenhonorar.txt", FILE_B)
        runs = self.client.app.state.runs
        runs.model_factory = lambda: update_script(fb["id"])
        started = self.client.post(f"/api/cases/{case['id']}/update").json()
        runs.stop(started["id"])  # before its first model turn
        run = self.wait(started["id"])
        self.assertEqual(run["status"], "discarded")
        self.assertTrue(run["error"].startswith("stopped:"))
        view = self.client.get(f"/api/cases/{case['id']}").json()
        self.assertEqual((view["prepared_run"]["id"], view["new_files"]), (base["id"], ["Zwischenhonorar.txt"]))
        listed = next(c for c in self.client.get("/api/cases").json()["cases"] if c["id"] == case["id"])
        self.assertEqual(listed["stand"]["kind"], "arrived")  # not «nicht vorbereitet»: a run set aside does not count

    def test_trotzdem_verwenden_unblocks_the_draft_until_another_file_comes(self):
        case, _ = self.prepared_case()
        self.upload(case["id"], "Zwischenhonorar.txt", FILE_B)
        self.assertTrue(self.client.get(f"/api/cases/{case['id']}").json()["draft_stale"])
        logged = self.client.post(f"/api/cases/{case['id']}/events", json={"kind": "letter.unblocked", "fields": {"files": ["Zwischenhonorar.txt"]}})
        self.assertEqual(logged.status_code, 201)
        self.assertFalse(self.client.get(f"/api/cases/{case['id']}").json()["draft_stale"])
        time.sleep(1.1)  # the store keeps seconds
        self.upload(case["id"], "Nachtrag.txt", "Noch ein Schreiben.")
        self.assertTrue(self.client.get(f"/api/cases/{case['id']}").json()["draft_stale"])


class EntryServiceTests(Service):
    FORM = {"kind": "telefon", "party": "kanzlei", "name": "RA Muster", "date": "2026-11-15", "said": "Bericht folgt bis Ende Monat.",
            "next": {"what": "Bericht schicken", "by": "2026-11-30"}}

    def test_an_entry_is_written_changed_and_removed_each_logged_and_the_case_recomputed_at_once(self):
        case, _ = self.prepared_case()
        before = {i["item_id"] for i in self.client.get(f"/api/cases/{case['id']}").json()["items"]}
        made = self.client.post(f"/api/cases/{case['id']}/entries", json=self.FORM)
        self.assertEqual(made.status_code, 201, made.text)
        n = made.json()["entry"]["n"]
        self.assertEqual(n, 9001)
        view = self.client.get(f"/api/cases/{case['id']}").json()
        own = next(i for i in view["items"] if i["item_id"] == f"entry:{n}")
        self.assertEqual((own["handler"]["by"], own["handler"]["source"], own["evidence"]), ("dev", "Fallbearbeitung", []))
        self.assertIn(f"entry:{n}", {i["item_id"] for i in view["items"]} - before)
        stand = next(i for i in view["items"] if i["item_id"] == "stand:kontakt")
        self.assertEqual(stand["value"], "15.11.2026 · Telefon mit der Kanzlei")
        dated = [i for i in view["items"] if i["kind"] == "deadline" and i.get("account")]
        self.assertEqual([(d["value"], d["what"]) for d in dated], [("2026-11-30", "Bericht schicken")])
        self.assertIn("Erfasst durch die Fallbearbeitung: Telefon mit der Kanzlei (RA Muster) am 15.11.2026: Bericht folgt bis Ende Monat", view["file_note"])
        changed = self.client.put(f"/api/cases/{case['id']}/entries/{n}", json={**self.FORM, "said": "Bericht folgt bis 5.12.", "next": {"what": "Bericht schicken", "by": "2026-12-05"}})
        self.assertEqual(changed.status_code, 200, changed.text)
        view = self.client.get(f"/api/cases/{case['id']}").json()
        self.assertEqual([(d["value"]) for d in view["items"] if d["kind"] == "deadline" and d.get("account")], ["2026-12-05"])
        edits = [e for e in view["edits"] if e["op"] == "add_entry"]
        self.assertEqual([e["status"] for e in edits], ["replaced", "active"])
        self.assertEqual(self.client.delete(f"/api/cases/{case['id']}/entries/{n}").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/cases/{case['id']}/entries/{n}").status_code, 404)
        view = self.client.get(f"/api/cases/{case['id']}").json()
        self.assertNotIn(f"entry:{n}", {i["item_id"] for i in view["items"]})
        kinds = [e["kind"] for e in self.client.get(f"/api/cases/{case['id']}/events").json()["events"] if e["kind"].startswith("entry.")]
        self.assertEqual(kinds, ["entry.added", "entry.changed", "entry.removed"])
        # the next entry never takes a removed one's number; the Verlauf names the change and the removal
        self.assertEqual(self.client.post(f"/api/cases/{case['id']}/entries", json=self.FORM).json()["entry"]["n"], 9002)
        gestures = [r["what"] for r in self.client.get(f"/api/cases/{case['id']}").json()["verlauf"] if r["kind"] == "gesture"]
        self.assertEqual(gestures, ["Eigenen Eintrag geändert", "Eigenen Eintrag entfernt"])

    def test_the_form_is_refused_in_the_handlers_words_and_never_through_the_edit_route(self):
        case, _ = self.prepared_case()
        bad = self.client.post(f"/api/cases/{case['id']}/entries", json={**self.FORM, "said": "", "next": None})
        self.assertEqual((bad.status_code, bad.json()["detail"]), (422, "Was besprochen wurde, fehlt"))
        self.assertEqual(self.client.post(f"/api/cases/{case['id']}/entries", json={**self.FORM, "kind": "brief"}).status_code, 422)
        sideways = self.client.post(f"/api/cases/{case['id']}/edits", json={"op": "add_entry", "args": {**self.FORM, "n": 9001}, "reason": "x"})
        self.assertEqual(sideways.status_code, 422)


class VerlaufTests(Service):
    def test_an_intake_case_shows_its_report_first_then_every_gesture_and_no_ihre_aenderungen(self):
        case = self.client.post("/api/cases", json={"title": "Schimmel"}).json()
        self.upload(case["id"], "Meldung.txt", "Im Bad wächst Schimmel.")
        store = self.store
        run = store.create_run(case["id"], "dev")
        store.update_run(run["id"], status="completed", workflow_id="mietmangel-handler", finished_at="2026-11-12T10:00:00+00:00",
                         result={"facts": [], "documents": [], "brief": {"request": "Schimmel im Bad.", "parties": [], "timeline": []}})
        self.client.post(f"/api/cases/{case['id']}/edits", json={"op": "set_fact", "args": {"fact": "deckung", "value": "bestätigt"},
                                                                  "reason": "", "reason_code": "none", "recheck": False})
        self.client.post(f"/api/cases/{case['id']}/events", json={"kind": "followup.set", "item_id": "followup:0", "fields": {"date": "2026-12-01"}})
        rows = self.client.get(f"/api/cases/{case['id']}").json()["verlauf"]
        self.assertEqual((rows[0]["kind"], rows[0]["what"], rows[0]["title"]), ("report", "Meldung.txt", "Meldung"))
        self.assertEqual([r["what"] for r in rows if r["kind"] == "gesture"],
                         ["Ist die Versicherungsdeckung gegeben?: bestätigt", "Wiedervorlage gesetzt: 01.12.2026"])
        self.assertTrue(next(r for r in rows if r["kind"] == "gesture")["undo"])  # a decision still in force can be undone here
        script = (Path(__file__).parents[1] / "casepath" / "web" / "ui" / "assets" / "casepath.js").read_text()
        self.assertNotIn("Ihre Änderungen", script)  # every gesture is in the Verlauf, not on the Übersicht


class ItemKindTests(Service):
    def test_the_event_route_accepts_every_item_kind_the_item_list_holds_and_the_screen_marks(self):
        case, _ = self.prepared_case()
        self.client.post(f"/api/cases/{case['id']}/entries", json=EntryServiceTests.FORM)
        items = self.client.get(f"/api/cases/{case['id']}").json()["items"]
        shown = {i["kind"] for i in items}
        self.assertTrue({"stand", "stage_line", "entry"} <= shown | {"stage_line"})
        for item_id in sorted({i["item_id"] for i in items}):
            response = self.client.post(f"/api/cases/{case['id']}/events", json={"kind": "item.exposed", "item_id": item_id, "fields": {"view": "overview"}})
            self.assertEqual(response.status_code, 201, (item_id, response.text))
        for kind in sorted(ITEM_KINDS | SCREEN_KINDS):  # also the kinds this case does not show
            self.assertEqual(self.client.post(f"/api/cases/{case['id']}/events", json={"kind": "item.exposed", "item_id": f"{kind}:x"}).status_code, 201, kind)
        self.assertEqual(self.client.post(f"/api/cases/{case['id']}/events", json={"kind": "item.exposed", "item_id": "nonsense:x"}).status_code, 422)
        # every literal «kind:» the screen writes into data-item is a kind the route accepts
        script = (Path(__file__).parents[1] / "casepath" / "web" / "ui" / "assets" / "casepath.js").read_text()
        literal = set(re.findall(r'data-item="([a-z_]+):', script)) | set(re.findall(r'data-item="\$\{esc\(p\.cover \? "([a-z_]+):', script))
        self.assertTrue(literal)
        self.assertLessEqual(literal, set(ITEM_KINDS | SCREEN_KINDS))


if __name__ == "__main__":
    unittest.main()
