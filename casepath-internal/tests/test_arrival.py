"""The arrival of a reply (Slice C, C1-C5 and C11): one deliberate import stores the files, refuses what the case already
holds and, where the deployment starts updates by itself, starts one bounded update that reads only what came in; a
failed, stopped or interrupted update keeps the case in the queue with what was prepared before, offers the update again
and recovers without reading anything twice or duplicating an entry.

On S-D11A (tests/episode.py), the synthetic analog of D11, through the case service; scripted and model-free."""
from contextlib import contextmanager
import json
from pathlib import Path
import re
import tempfile
import threading
import time
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from casepath.agents import core
from casepath.agents.runner import RunService
from casepath.config import load_settings
from casepath.read.extract import extract
from casepath.web import listing
from casepath.web.app import create_app
from tests import episode

NS = episode.EPISODE
SCRIPT = (Path(__file__).parents[1] / "casepath" / "web" / "ui" / "assets" / "casepath.js").read_text()
LEASE_ONLY = "Kündigung: Der Vertrag kann unter Einhaltung einer Frist von drei Monaten"  # a sentence of Phase A's dossier only


def recorded(model):
    """The scripted model with the name of every structured call it answers kept in ``model.calls`` (the reader's and the
    finder's turns as «turn»)."""
    model.calls = []
    respond, respond_json = model.respond, model.respond_json

    def turn(**kw):
        model.calls.append("turn")
        return respond(**kw)

    def structured(**kw):
        model.calls.append(kw.get("name"))
        return respond_json(**kw)
    model.respond, model.respond_json = turn, structured
    return model


class Arrival(unittest.TestCase):
    """A workspace with the shipped areas; ``env`` sets the deployment (auto-update off by default)."""
    env = {}

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.data = str(Path(self.directory.name) / "data")
        self.client = TestClient(create_app(load_settings({"CASEPATH_DATA_DIR": self.data, "CASEPATH_DEV_USER": "dev", **self.env}),
                                            model_factory=lambda: None))
        self.store, self.runs = self.client.app.state.store, self.client.app.state.runs
        self.models = []

    def tearDown(self):
        self.client.app.state.runs.shutdown()
        self.client.app.state.store.close()
        self.directory.cleanup()

    def seeded(self, ns=NS):
        """S-D11A as it stood on d+34: prepared by the scripted team (Phase A)."""
        return episode.seed_phase_a(self.store, self.runs, ns)

    def script_updates(self, case_id, *scripts, pause=0.0):
        """The run service's model: each update in turn gets the next script, its file ids mapped to the case's unread
        files by name ([(turns, names)]); a model that is not a script (P-fail) is given as it is."""
        queue = list(scripts)

        def factory(token=None):
            item = queue.pop(0)
            if not isinstance(item, tuple):
                return item
            model = recorded(episode.update_model(self.store, case_id, item[0], item[1], pause=pause))
            self.models.append(model)
            return model
        self.runs.model_factory = factory

    def upload(self, case_id, files, field="files"):
        return self.client.post(f"/api/cases/{case_id}/files", files=[(field, (name, data, "message/rfc822")) for name, data in files])

    def runs_of(self, case_id, kind=None):
        rows = self.store._all("select id from runs where case_id=? order by created_at, rowid", case_id)
        out = [self.store.get_run(r["id"]) for r in rows]
        return [r for r in out if kind is None or r["kind"] == kind]

    def row(self, case_id):
        return next(c for c in self.client.get("/api/cases").json()["cases"] if c["id"] == case_id)

    def view(self, case_id):
        return self.client.get(f"/api/cases/{case_id}").json()

    def entries(self, run):
        """The numbers of a run's account entries, in number order (the record keeps them by date)."""
        return sorted(e["n"] for e in ((run.get("result") or {}).get("record") or {}).get("entries") or ())


class AutoOn(Arrival):
    env = {"CASEPATH_AUTO_UPDATE": "1"}


class OneImportTests(AutoOn):
    def test_one_upload_of_two_files_starts_one_bounded_update_that_reads_only_them(self):
        case = self.seeded()
        base = self.store.latest_run(case["id"], "completed")
        self.script_updates(case["id"], (NS.turns_b(), NS.reply_names))
        with mock.patch.object(core, "update", wraps=core.update) as spied:
            answer = self.upload(case["id"], NS.replies)
            self.assertEqual(answer.status_code, 201, answer.text)
            body = answer.json()
            self.assertEqual((body["auto"], body["run"]["kind"], body["run"]["builds_on"]), ("gestartet", "update", base["id"]))
            self.assertEqual(([f["name"] for f in body["files"]], body["skipped"]), (["AW Rueckfrage.eml", "Nachtrag.eml"], []))
            run = episode.wait(self.store, body["run"]["id"])
        self.assertEqual(run["status"], "completed", run.get("error"))
        self.assertEqual(len(self.runs_of(case["id"], "update")), 1)  # one import, one update
        # bounded: the update's own cap (CASEPATH_UPDATE_TOKEN_BUDGET, 200 000 by default) within the run's
        self.assertEqual(spied.call_args.args[0]["options"]["token_budget"], 200_000)
        # read only what came in: the reader's turn and the finder's, the second reading, the source check; no routing
        model, = self.models
        self.assertEqual(model.calls, ["turn", "turn", "casepath_confirm_facts", "casepath_source_check"])
        given = json.dumps(model.inputs, ensure_ascii=False)
        self.assertIn("Der Schimmel ist immer noch da.", given)
        self.assertNotIn(LEASE_ONLY, given)  # nothing of the earlier files' text
        self.assertEqual(run["result"]["update"]["files"], [f["id"] for f in body["files"]])
        self.assertEqual(sorted(run["result"]["update"]["entries"]), [13, 14, 15])
        started = [e for e in self.store.list_case_events(case["id"]) if e["kind"] == "update.started"]
        self.assertEqual([(e["auto"], e["run"]) for e in started], [(True, run["id"])])
        view = self.view(case["id"])
        self.assertEqual((view["new_files"], view["draft_stale"], view["prepared_run"]["kind"]), ([], False, "update"))


class WhyNotTests(Arrival):
    def test_auto_update_off_over_the_cap_or_with_a_run_active_says_why_and_keeps_the_button(self):
        case = self.seeded()
        off = self.upload(case["id"], NS.replies[:1]).json()  # the deployment's default: off
        self.assertEqual((off["auto"], off["run"]), ("aus", None))
        view = self.view(case["id"])
        self.assertEqual((view["update"]["available"], view["update"]["auto"]), (True, "aus"))
        self.assertEqual(self.runs_of(case["id"], "update"), [])
        # the same workspace with updates starting by themselves, up to one unread page
        self.client.app.state.runs.shutdown()
        self.client.app.state.store.close()
        self.client = TestClient(create_app(load_settings({"CASEPATH_DATA_DIR": self.data, "CASEPATH_DEV_USER": "dev", "CASEPATH_AUTO_UPDATE": "1",
                                                           "CASEPATH_AUTO_UPDATE_MAX_PAGES": "1"}), model_factory=lambda: None))
        self.store, self.runs = self.client.app.state.store, self.client.app.state.runs
        big = self.upload(case["id"], NS.replies[1:]).json()  # now two unread pages, one allowed
        self.assertEqual((big["auto"], big["run"]), ("zu_gross", None))
        view = self.view(case["id"])
        self.assertEqual((view["update"]["available"], view["update"]["auto"], view["update"]["max_pages"]), (True, "zu_gross", 1))
        busy = self.store.update_run(self.store.create_run(case["id"], "dev", kind="update",
                                                           builds_on=self.store.latest_run(case["id"], "completed")["id"])["id"], status="running")
        late = self.upload(case["id"], [("Spaet.eml", episode.eml("a@example.ch", "b@example.ch", NS.day(36), "08:00", "Nachtrag", "Noch etwas."))]).json()
        self.assertEqual((late["auto"], late["run"]), ("lauf_aktiv", None))
        self.store.update_run(busy["id"], status="failed", error="transport: test")
        fresh = self.client.post("/api/cases", json={"title": "Noch nicht vorbereitet"}).json()
        blocked = self.upload(fresh["id"], NS.replies[:1]).json()
        self.assertEqual((blocked["auto"], blocked["run"]), ("no_assessment", None))  # the reason «Aktualisieren» is blocked
        # the titles «Aktualisieren» carries for each reason (web/ui/assets/casepath.js autoTitle); a blocked one its message
        for title in ("Automatische Aktualisierung ist ausgeschaltet", "Automatisch nur bis ${u.max_pages} Seiten: bitte selbst starten",
                      "Ein Lauf ist im Gang", "return u.text"):
            self.assertIn(title, SCRIPT)
        self.assertIn('id="update-run" title="${esc(autoTitle(u))}"', SCRIPT)


class DuplicateTests(Arrival):
    def test_a_file_already_in_the_case_is_refused_and_a_duplicate_attachment_is_skipped(self):
        case = self.seeded()
        first = self.upload(case["id"], NS.replies[:1]).json()
        held = first["files"][0]
        count = len(self.store.list_files(case["id"]))
        dup = NS.perturbations["P-dup"]
        with mock.patch("casepath.web.app.extract", wraps=extract) as reading:
            again = self.upload(case["id"], [(dup.name, dup.data)])
            self.assertEqual(reading.call_count, 0)  # refused before any reading
        self.assertEqual(again.status_code, 409)
        day = episode.dotted(__import__("datetime").datetime.fromisoformat(held["created_at"]).astimezone(
            __import__("zoneinfo").ZoneInfo("Europe/Zurich")).date())
        self.assertEqual(again.json()["detail"], f"Bereits in der Akte: «AW Rueckfrage.eml» vom {day}")
        self.assertEqual(len(self.store.list_files(case["id"])), count)
        self.assertEqual(self.client.post(f"/api/cases/{case['id']}/files", files={"file": (dup.name, dup.data, "message/rfc822")}).status_code, 409)
        mixed = self.upload(case["id"], [(dup.name, dup.data), NS.replies[1]]).json()  # one new, one held: the new one is kept
        self.assertEqual([f["name"] for f in mixed["files"]], ["Nachtrag.eml"])
        self.assertEqual([(s["name"], s["same_as"], s["in_case"]) for s in mixed["skipped"]], [("AW Rueckfrage.eml", held["id"], "AW Rueckfrage.eml")])
        # an attachment the case holds: its e-mail is kept, the attachment skipped and remembered on it
        receipts = NS.branches["B-receipts"]
        (mail_name, mail), = receipts.files()
        bill = self.upload(case["id"], [(episode.BILL, receipts.core_files()[1]["extraction"]["text"].encode())]).json()["files"][0]
        self.assertEqual(bill["name"], episode.BILL)
        came = self.upload(case["id"], [(mail_name, mail)]).json()
        self.assertEqual([f["name"] for f in came["files"]], [mail_name])
        self.assertEqual([(s["name"], s["same_as"], s["attachment"]) for s in came["skipped"]], [(episode.BILL, bill["id"], mail_name)])
        stored = self.store.get_file(came["files"][0]["id"])
        self.assertEqual(stored["extraction"]["same_as"], [bill["id"]])
        self.assertEqual([f["name"] for f in self.store.list_files(case["id"])].count(episode.BILL), 1)
        self.assertIn("Anhang bereits in der Akte: «${s.name}» (übersprungen)", SCRIPT)
        # a new case from files keeps a file given twice once
        made = self.client.post("/api/cases/from-files", files=[("files", (n, d, "message/rfc822")) for n, d in [NS.replies[0], NS.replies[0]]]).json()
        self.assertEqual(([f["name"] for f in made["files"]], [s["name"] for s in made["skipped"]]), (["AW Rueckfrage.eml"], ["AW Rueckfrage.eml"]))
        self.assertEqual(len(self.store.list_files(made["case"]["id"])), 1)


class FollowOnTests(AutoOn):
    def setUp(self):
        super().setUp()
        # on a slow machine hashing the source tree takes longer than a short update: the run service must not do it
        # between starting the follow-on and logging it (the log line then came after the follow-on had finished)
        def slow(*args, **kwargs):
            time.sleep(2.5)
            return "0" * 64, 0
        patcher = mock.patch("casepath.parity.source_tree", side_effect=slow)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_file_arriving_during_an_update_gets_one_more_update(self):
        case = self.seeded()
        retract = NS.perturbations["P-retract"]
        first_turns, _ = retract.turns(first=16)
        self.script_updates(case["id"], (NS.turns_b(), NS.reply_names), (first_turns, {"fd": retract.files[0][0]}), pause=0.15)
        body = self.upload(case["id"], NS.replies).json()
        first = body["run"]
        for _ in range(400):  # the update has built its job (its first event), so the next file is new to it
            if self.store.get_run(first["id"])["events"]:
                break
            time.sleep(0.01)
        late = self.upload(case["id"], retract.files[:1]).json()
        self.assertEqual((late["auto"], late["run"]), ("lauf_aktiv", None))
        self.assertEqual(episode.wait(self.store, first["id"])["status"], "completed")
        for _ in range(400):
            updates = self.runs_of(case["id"], "update")
            if len(updates) == 2 and updates[1]["status"] not in ("queued", "running"):
                break
            time.sleep(0.02)
        one, two = self.runs_of(case["id"], "update")
        self.assertEqual((two["status"], two["builds_on"]), ("completed", one["id"]))
        self.assertEqual(two["result"]["update"]["files"], [late["files"][0]["id"]])  # only the file that came during the first
        self.assertEqual(two["result"]["update"]["entries"], [16])
        started = [(e["run"], e.get("follows")) for e in self.store.list_case_events(case["id"]) if e["kind"] == "update.started"]
        self.assertEqual(started, [(one["id"], None), (two["id"], one["id"])])
        time.sleep(0.3)
        self.assertEqual(len(self.runs_of(case["id"], "update")), 2)  # once: nothing follows the follow-on


class FailedTests(AutoOn):
    def test_a_failed_update_keeps_its_last_prepared_step_in_the_list_and_retries_the_update_only(self):
        case = self.seeded()
        before = self.row(case["id"])
        self.script_updates(case["id"], NS.perturbations["P-fail"].model(), (NS.turns_b(), NS.reply_names))
        body = self.upload(case["id"], NS.replies).json()
        failed = episode.wait(self.store, body["run"]["id"])
        self.assertEqual((failed["status"], failed["result"]), ("failed", None))
        self.assertTrue(failed["error"].startswith("transport:"))
        time.sleep(0.3)
        self.assertEqual(len(self.runs_of(case["id"], "update")), 1)  # never retried by itself
        with mock.patch.object(listing, "stand", wraps=listing.stand) as stand:
            row = self.row(case["id"])
        given = next(c.kwargs for c in stand.call_args_list if c.kwargs["files"] and c.kwargs["files"][0]["case_id"] == case["id"])
        self.assertEqual((given["run_status"], given["run_kind"], given["new_files"]), ("failed", "update", 2))
        self.assertTrue(given["items"])  # the last completed run's items
        self.assertEqual((row["next_action"], row["due"], row["new_files"]), (before["next_action"], before["due"], 2))
        if "bucket" in row["stand"]:  # with Slice B's queue: the failed update is its own group
            self.assertEqual((row["stand"]["bucket"], row["stand"]["text"]), ("fehlgeschlagen", "Aktualisierung fehlgeschlagen"))
        view = self.view(case["id"])
        self.assertEqual((view["run"]["status"], view["run"]["kind"], view["draft_stale"]), ("failed", "update", True))
        self.assertEqual(view["status"], row["stand"])  # the case and the list agree
        self.assertIn('id="retry-update">${T("Update again", "Erneut aktualisieren")}', SCRIPT)
        retried = episode.wait(self.store, self.client.post(f"/api/cases/{case['id']}/update").json()["id"])
        self.assertEqual((retried["status"], retried["kind"]), ("completed", "update"), retried.get("error"))
        self.assertEqual(self.entries(retried), list(range(1, 16)))  # no entry twice: the failed run kept nothing
        self.assertEqual(len(self.runs_of(case["id"], "full")), 1)  # the update only, no new preparation


class RestartTests(Arrival):
    def scan(self, case_id):
        """A scanned page of a new file, read before the restart (its reading was saved with the file)."""
        text = "[page 1]\n[Foto] Stromzähler im Keller, abgelesen am 1. September 2026."
        row = {"media_type": "application/pdf", "kind": "pdf", "text": text, "pages": 1, "readable": True, "note": None,
               "pages_without_text": [], "pages_transcribed": [1]}
        return self.store.add_file(case_id, "Zaehler.pdf", "application/pdf", "pdf", b"%PDF-1.4 synthetic scan", row, "dev")["id"]

    def restart(self, factory, **options):
        """The service started again on the same store (P-restart): a run service on the reopened store."""
        self.client.app.state.runs.shutdown()
        store = episode.reopen(self.store)
        self.client.app.state.store = store
        self.store = store
        return RunService(store, self.client.app.state.catalogue, factory, auto_update=True, **options)

    def test_an_interrupted_update_is_resumed_once_and_nothing_is_read_twice(self):
        case = self.seeded()
        replies = episode.add_replies(self.store, case["id"])
        scan = self.scan(case["id"])
        left = NS.perturbations["P-restart"].leave(self.store, case["id"])
        models = []
        factory = lambda token=None: models.append(recorded(episode.update_model(self.store, case["id"], NS.turns_b(), NS.reply_names))) or models[-1]
        runs = self.restart(factory)
        self.addCleanup(runs.shutdown)
        self.assertEqual(self.store.get_run(left["id"])["status"], "interrupted")
        self.assertTrue(self.store.get_run(left["id"])["error"].startswith("interrupted: Der Dienst wurde neu gestartet"))
        resumed, = runs.resumed
        done = episode.wait(self.store, resumed)
        self.assertEqual((done["status"], done["kind"]), ("completed", "update"), done.get("error"))
        self.assertEqual(self.entries(done), list(range(1, 16)))  # the interrupted run kept no entry: each once
        self.assertEqual(sorted(done["result"]["update"]["files"]), sorted(replies + [scan]))  # what the last preparation did not read
        self.assertNotIn(LEASE_ONLY, json.dumps(models[0].inputs, ensure_ascii=False))
        self.assertNotIn("casepath_transcribe", models[0].calls)  # the page read before the restart is not read again
        self.assertFalse([e for e in done["events"] if e.get("kind") in ("reading.scanned", "reading.progress")])
        self.assertEqual(self.store.get_file(scan)["extraction"]["pages_transcribed"], [1])
        logged = [(e["run"], e["resumed"], e["auto"]) for e in self.store.list_case_events(case["id"]) if e["kind"] == "update.started"]
        self.assertEqual(logged, [(resumed, left["id"], True)])
        # once: the update started again is not started a second time, whatever comes after
        self.store.add_file(case["id"], "Noch.txt", "text/plain", "text", b"Noch ein Nachtrag.", extract("Noch.txt", "text/plain", b"Noch ein Nachtrag."), "dev")
        self.store.update_run(resumed, status="running")
        again = self.restart(factory)
        self.addCleanup(again.shutdown)
        self.assertEqual((again.resumed, self.store.get_run(resumed)["status"]), ([], "interrupted"))

    def test_where_the_model_is_called_as_the_person_an_interrupted_update_waits_for_them(self):
        case = self.seeded()
        episode.add_replies(self.store, case["id"])
        left = NS.perturbations["P-restart"].leave(self.store, case["id"])
        runs = self.restart(lambda token=None: None, model_as_user=True)
        self.addCleanup(runs.shutdown)
        self.assertEqual((runs.resumed, self.store.get_run(left["id"])["status"]), ([], "interrupted"))
        self.assertIn('T("Update interrupted", "Aktualisierung unterbrochen")', SCRIPT)


class AdmissionTests(AutoOn):
    """An update reads the inputs admitted when it was created; after a restart it is resumed with those only, and a file
    that came later waits with «Aktualisieren» and its reason (the audit of 84115b9: a resume had been checked with the
    page cap off, so two interrupted reply pages and a later 21-page file ran as 23 unread pages under a 20-page cap)."""

    def large(self, case_id, pages=21):
        """A file of ``pages`` pages that came after the update was admitted."""
        text = "\n\n".join(f"[page {n}]\nGutachten der Fachperson, Seite {n}: Feuchtigkeit gemessen." for n in range(1, pages + 1))
        row = {"media_type": "application/pdf", "kind": "pdf", "text": text, "pages": pages, "readable": True, "note": None, "segments": []}
        return self.store.add_file(case_id, "Gutachten.pdf", "application/pdf", "pdf", text.encode(), row, "dev")["id"]

    def restarted(self, case_id):
        """The service started again on the same data (P-restart): a new app on the reopened store, whose run service marks
        the unfinished update interrupted and starts what it may start again (its model waits until the app is up)."""
        self.client.app.state.runs.shutdown()
        self.client.app.state.store.close()
        here = {}

        def factory(token=None):
            for _ in range(500):
                if "store" in here:
                    break
                time.sleep(0.01)
            model = recorded(episode.update_model(here["store"], case_id, NS.turns_b(), NS.reply_names))
            self.models.append(model)
            return model
        self.client = TestClient(create_app(load_settings({"CASEPATH_DATA_DIR": self.data, "CASEPATH_DEV_USER": "dev", **self.env}),
                                            model_factory=factory))
        self.store, self.runs = self.client.app.state.store, self.client.app.state.runs
        here["store"] = self.store
        return here

    def test_a_resumed_update_reads_only_what_it_admitted_and_a_later_large_file_waits(self):
        case = self.seeded()
        replies = episode.add_replies(self.store, case["id"])
        with mock.patch.object(self.runs._pool, "submit"):  # created with its inputs admitted; the service stops before it runs
            left = self.runs.update(case["id"], "dev", auto=True, max_pages=20)
        admitted = next(e for e in self.store.get_run(left["id"])["events"] if e["kind"] == "update.admitted")
        self.assertEqual((sorted(admitted["files"]), admitted["pages"]), (sorted(replies), 2))
        big = self.large(case["id"])  # 21 pages more: 23 unread pages under a cap of 20
        self.restarted(case["id"])
        self.assertEqual(self.store.get_run(left["id"])["status"], "interrupted")
        resumed, = self.runs.resumed
        done = episode.wait(self.store, resumed)
        self.assertEqual((done["status"], done["kind"]), ("completed", "update"), done.get("error"))
        self.assertEqual(sorted(done["result"]["update"]["files"]), sorted(replies))  # the admitted inputs, nothing more
        self.assertNotIn(big, done["result"]["read_files"])
        again = next(e for e in done["events"] if e["kind"] == "update.admitted")
        self.assertEqual((sorted(again["files"]), again["pages"]), (sorted(replies), 2))
        self.assertNotIn("Gutachten der Fachperson", json.dumps(self.models[0].inputs, ensure_ascii=False))
        time.sleep(0.3)
        self.assertEqual([r["id"] for r in self.runs_of(case["id"], "update")], [left["id"], resumed])  # no update of the large file
        view = self.view(case["id"])  # the large file waits for the handler, «Aktualisieren» with its reason
        self.assertEqual(view["new_files"], ["Gutachten.pdf"])
        self.assertEqual((view["update"]["available"], view["update"]["auto"], view["update"]["max_pages"]), (True, "zu_gross", 20))

    def test_an_interrupted_update_without_its_admitted_inputs_is_resumed_only_within_the_cap(self):
        case = self.seeded()
        episode.add_replies(self.store, case["id"])
        left = NS.perturbations["P-restart"].leave(self.store, case["id"])  # an update made before updates recorded their inputs
        self.large(case["id"])
        self.restarted(case["id"])
        self.assertEqual((self.runs.resumed, self.store.get_run(left["id"])["status"]), ([], "interrupted"))
        self.assertEqual(self.view(case["id"])["update"]["auto"], "zu_gross")


class StoppedTests(Arrival):
    def test_a_stopped_update_shows_the_run_it_built_on_in_the_list_and_the_case(self):
        case = self.seeded()
        base = self.store.latest_run(case["id"], "completed")
        self.upload(case["id"], NS.replies)
        self.script_updates(case["id"], (NS.turns_b(), NS.reply_names))
        started = self.client.post(f"/api/cases/{case['id']}/update").json()
        self.runs.stop(started["id"])  # before its first model turn
        self.assertEqual(episode.wait(self.store, started["id"])["status"], "discarded")
        view = self.view(case["id"])
        self.assertEqual((view["prepared_run"]["id"], view["status"]["kind"]), (base["id"], "arrived"))
        self.assertEqual(self.row(case["id"])["stand"]["kind"], "arrived")


class ReopenTests(Arrival):
    def test_an_arrival_after_closing_reopens_the_case(self):
        case = self.seeded()
        close = lambda: self.client.post(f"/api/cases/{case['id']}/events", json={"kind": "case.closed", "fields": {"form": "erledigt"}})
        self.assertEqual(close().status_code, 201)
        first = self.upload(case["id"], NS.replies[:1]).json()
        reopened = [e for e in self.store.list_case_events(case["id"]) if e["kind"] == "case.reopened"]
        self.assertEqual([e["file"] for e in reopened], [first["files"][0]["id"]])
        self.upload(case["id"], NS.replies[1:])  # still open: no second reopening
        self.assertEqual(len([e for e in self.store.list_case_events(case["id"]) if e["kind"] == "case.reopened"]), 1)
        close()
        later = self.upload(case["id"], NS.perturbations["P-retract"].files[:1]).json()
        reopened = [e for e in self.store.list_case_events(case["id"]) if e["kind"] == "case.reopened"]
        self.assertEqual([e["file"] for e in reopened][-1], later["files"][0]["id"])
        # the case screen checks what arrived before «closed»
        body = re.search(r"function caseState\(\) \{(.*?)\n\}", SCRIPT, re.S).group(1)
        self.assertLess(body.index("arrived"), body.index('return "closed"'))


if __name__ == "__main__":
    unittest.main()
