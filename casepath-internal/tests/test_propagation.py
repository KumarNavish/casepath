"""One correction reaches everything it affects (Slice C, C6, C7, C9, and the newer steering's «one correction repairs the
whole package»): after an update the result checker's inherited fields are marked wherever they are used, the report and
the draft download included; the update says how the reply was matched; a derived fact is corrected where it comes from;
a settled request, a corrected party and a corrected fact reach the requirements, the account's obligations and dates,
the letter, its recipient and date, the case note and the queue, each change shown before and after with its basis,
while the handler's unrelated entries and decisions stay; undo restores it within its real limits.

On S-D11A (tests/episode.py), the synthetic analog of D11, through the case service; scripted and model-free."""
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
import zipfile

from fastapi.testclient import TestClient

from casepath.config import load_settings
from casepath.process import letters
from casepath.web.app import create_app
from tests import episode

NS = episode.EPISODE
SCRIPT = (Path(__file__).parents[1] / "casepath" / "web" / "ui" / "assets" / "casepath.js").read_text()
CHECKED = {"summary": "Gesamtwürdigung der Vorbereitung.", "answer": "Kurzeinschätzung der Vorbereitung.",
           "open_points": ["Offener Punkt der Vorbereitung."],
           "reply": {"needed": True, "subject": "Ihr Schadenfall", "status": "draft_not_sent", "label": "AI-generated draft",
                     "clauses": [{"text": "Antwortentwurf der Vorbereitung.", "supported": True, "kind": "formal", "basis": []}]}}


def docx_text(data):
    xml = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode()
    return re.sub(r"<[^>]+>", " ", xml.replace("<w:br/>", "\n"))


class Propagation(unittest.TestCase):
    env = {}

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.client = TestClient(create_app(load_settings({"CASEPATH_DATA_DIR": str(Path(self.directory.name) / "data"), "CASEPATH_DEV_USER": "dev",
                                                           **self.env}), model_factory=lambda: None))
        self.store, self.runs = self.client.app.state.store, self.client.app.state.runs

    def tearDown(self):
        self.runs.shutdown()
        self.store.close()
        self.directory.cleanup()

    def seeded(self, ns=NS, checked=False):
        """S-D11A on d+34 (Phase A); ``checked``: its result checker wrote an answer, open points and a reply draft."""
        case = episode.seed_phase_a(self.store, self.runs, ns)
        if checked:
            run = self.store.latest_run(case["id"], "completed")
            self.store.update_run(run["id"], result={**run["result"], **CHECKED})
        return case

    def updated(self, case_id, turns=None, names=None, files=None):
        """The files dropped (auto-update off) and «Aktualisieren» with the update's script: the completed update."""
        if files is not False:
            self.client.post(f"/api/cases/{case_id}/files", files=[("files", (n, b, "message/rfc822")) for n, b in (files or NS.replies)])
        self.runs.model_factory = lambda token=None: episode.update_model(self.store, case_id, turns or NS.turns_b(), names or NS.reply_names)
        run = episode.wait(self.store, self.client.post(f"/api/cases/{case_id}/update").json()["id"])
        self.assertEqual(run["status"], "completed", run.get("error"))
        return run

    def view(self, case_id):
        return self.client.get(f"/api/cases/{case_id}").json()

    def edit(self, case_id, op, args, reason="", code="none"):
        return self.client.post(f"/api/cases/{case_id}/edits", json={"op": op, "args": args, "reason": reason, "reason_code": code, "recheck": False})

    def row(self, case_id):
        return next(c for c in self.client.get("/api/cases").json()["cases"] if c["id"] == case_id)


class StaleTests(Propagation):
    def test_after_an_update_the_inherited_fields_are_marked_and_the_report_puts_them_under_the_stale_title(self):
        case = self.seeded(checked=True)
        prepared = self.store.latest_run(case["id"], "completed")
        before = docx_text(self.client.get(f"/api/cases/{case['id']}/report.docx").content)
        self.assertNotIn("Stand der vollständigen Vorbereitung", before)  # a full preparation's own fields are current
        self.assertIn("Kurzeinschätzung der Vorbereitung.", before)
        run = self.updated(case["id"])
        self.assertEqual(run["result"]["stale_since"], {"run": prepared["id"], "prepared_at": prepared["finished_at"], "files": 2})
        items = {i["item_id"]: i for i in self.view(case["id"])["items"]}
        for item_id in ("answer:0", "open_point:0", "reply:0"):  # marked, not hashed: the item list keeps its kinds
            self.assertEqual(items[item_id]["stale"], {"since": prepared["finished_at"], "run": prepared["id"], "files": 2}, item_id)
        self.assertNotIn("stale", items["summary:0"])  # the request the reader read is the case's, not the result checker's
        self.assertEqual(items["summary:0"]["update_summary"], NS.summary_b)
        report = docx_text(self.client.get(f"/api/cases/{case['id']}/report.docx").content)
        day = episode.dotted(__import__("datetime").date.fromisoformat(prepared["finished_at"][:10]))
        title = f"Stand der vollständigen Vorbereitung vom {day}, vor 2 neuen Dokumenten"
        self.assertIn(title, report)
        self.assertRegex(report, rf"Vorbereitet am {re.escape(day)} · aktualisiert am \d\d\.\d\d\.\d{{4}}")
        for text in ("Kurzeinschätzung der Vorbereitung.", "Offener Punkt der Vorbereitung.", "Antwortentwurf der Vorbereitung."):
            self.assertGreater(report.index(text), report.index(title), text)  # only under the stale title
        self.assertEqual(report.count("Antwortentwurf der Vorbereitung."), 1)
        # the letter the case prepares now, from the state the screen shows, is in the report as such
        draft = self.view(case["id"])["draft"]
        self.assertIn("Vorbereiteter Brief (Entwurf, nicht freigegeben)", report)
        self.assertIn(draft["text"].split("\n\n")[1], report)
        self.assertLess(report.index("Vorbereiteter Brief"), report.index(title))
        # the screen: no «Anliegen» from the result checker's answer, «Stand <Datum>» where its fields are shown
        self.assertNotIn("|| r.answer", re.search(r"function sideAnliegen\(\) \{(.*?)\n\}", SCRIPT, re.S).group(1))
        self.assertIn('T("As of", "Stand")} ${dateText(r.stale_since.prepared_at)}', SCRIPT)

    def test_an_inherited_reply_draft_is_refused_as_docx(self):
        case = self.seeded(checked=True)
        prepared = self.store.latest_run(case["id"], "completed")
        self.assertEqual(self.client.get(f"/api/runs/{prepared['id']}/draft.docx").status_code, 200)  # the preparation's own
        run = self.updated(case["id"])
        refused = self.client.get(f"/api/runs/{run['id']}/draft.docx")
        self.assertEqual((refused.status_code, refused.json()["detail"]), (409, "Der Entwurf stammt aus einer früheren Vorbereitung"))
        self.assertIn("!r.stale_since ? `<a class=\"cp-button\" href=\"/api/runs/", SCRIPT)  # no download offered for it


class LedgerTests(Propagation):
    def test_the_update_says_how_the_reply_was_matched(self):
        case = self.seeded()
        run = self.updated(case["id"])
        ledger = run["result"]["update"]["ledger"]
        self.assertEqual([(r["id"], r["n"]) for r in ledger["closed"]], [("r10.0", 13), ("r10.1", 13)])
        self.assertEqual([r["id"] for r in ledger["opened"]], ["r13.0", "r13.1", "r15.0"])  # each question its own row (C10e)
        for key in ("refused", "partial", "promised", "unspecified"):  # the keys MEASURE reads, empty here
            self.assertEqual(ledger[key], [], key)
        changes = self.view(case["id"])["changes"]
        self.assertEqual(changes["ledger"][:2], ["beantwortet: Besteht der Schimmel weiterhin? (zu Nr. 10)",
                                                 "beantwortet: Reaktion der Verwaltung auf die letzte Meldung (zu Nr. 10)"])
        self.assertIn("Frage an Protekta: Darf ich die Miete hinterlegen?", changes["ledger"])
        self.assertEqual(changes["ledger"][-1], "2 Nachrichten der Kundschaft vom 05.09.2026")
        self.assertEqual(changes["update_summary"], NS.summary_b)
        # a refusal: the handler asked the receipts on the phone; the customer has none (P-refuse)
        call = self.client.post(f"/api/cases/{case['id']}/entries", json={"kind": "telefon", "party": "kunde", "date": NS.day(36).isoformat(),
                                                                         "said": "Belege der Stromkosten verlangt.",
                                                                         "asked": {"what": "Belege zu den Stromkosten"}})
        self.assertEqual(call.status_code, 201, call.text)
        asked_in = call.json()["n"] if "n" in call.json() else call.json()["edit"]["args"]["n"]
        refuse = NS.perturbations["P-refuse"]
        run = self.updated(case["id"], refuse.turns(16, asked_in), {"fr": refuse.files[0][0]}, files=refuse.files)
        ledger = run["result"]["update"]["ledger"]
        self.assertEqual([(r["id"], r["refusal"]) for r in ledger["refused"]], [(f"r{asked_in}.0", "Belege zu den Stromkosten")])
        self.assertEqual(ledger["closed"], [])  # a refusal closes nothing
        self.assertIn("abgelehnt: Belege zu den Stromkosten", self.view(case["id"])["changes"]["ledger"])


class CorrectionTests(Propagation):
    def test_a_derived_fact_cannot_be_set_and_says_what_to_correct_instead(self):
        case = self.seeded()
        for fact, value, source in (("kunde_geantwortet", "ja", "die Antworten der Kundschaft im Verlauf"),
                                    ("unterlagen_vollstaendig", "ja", "die Unterlagen (Dokumenten-Checkliste)"),
                                    ("mitwirkung_fehlt", "nein", "die Anforderungen mit Frist und die Antworten im Verlauf")):
            refused = self.edit(case["id"], "set_fact", {"fact": fact, "value": value}, "Korrektur")
            self.assertEqual((refused.status_code, refused.json()["detail"]), (422, f"wird berechnet; korrigieren Sie, woraus er folgt: {source}"))
        self.assertEqual(self.store.list_edits(case["id"]), [])  # nothing saved
        self.assertFalse([i for i in self.view(case["id"])["items"] if i["kind"] == "fact" and "durch die Fallbearbeitung" in str(i.get("value"))])

    def test_settling_a_request_closes_it_in_stand_dates_and_letters_and_undo_reopens_it(self):
        ns = episode.analog(dated_request=True)  # the A4 sets a date: its two rows are dated obligations on d+34
        case = self.seeded(ns)
        before = self.view(case["id"])
        rows = lambda v: {r["request"]: r["text"] for i in v["items"] if i["kind"] == "stand" for r in i.get("rows") or () if r.get("request")}
        dates = lambda v: {i["key"] for i in v["items"] if i["kind"] == "deadline" and i.get("account")}
        self.assertIn("r10.0", rows(before))
        self.assertIn("konto-r10.0", dates(before))
        done = self.edit(case["id"], "settle_request", {"request": "r10.0", "how": "erledigt"})
        self.assertEqual(done.status_code, 201, done.text)
        after = self.view(case["id"])
        self.assertNotIn("r10.0", rows(after))  # «Stand»
        self.assertNotIn("konto-r10.0", dates(after))  # the account's dates
        self.assertIn("r10.1", rows(after))  # the other row stays
        self.assertNotIn("Besteht der Schimmel weiterhin?", (after["draft"] or {}).get("text") or "")  # the letter asks it no more
        change = done.json()["consequences"]
        self.assertEqual(change["basis"], "«Besteht der Schimmel weiterhin?»: erledigt (dev)")
        opened = next(c for c in change["changes"] if c["what"] == "Offen")
        self.assertTrue(any("Besteht der Schimmel weiterhin?" in x for x in opened["before"]))
        logged = [e for e in self.store.list_case_events(case["id"]) if e["kind"] == "entry.corrected"]
        self.assertEqual([(e["request"], e["how"]) for e in logged], [("r10.0", "erledigt")])
        again = self.client.post(f"/api/edits/{done.json()['edit']['id']}/undo").json()
        undone = self.view(case["id"])
        self.assertEqual((rows(undone), dates(undone), undone["items_sha256"]), (rows(before), dates(before), before["items_sha256"]))
        self.assertEqual((undone["draft"] or {}).get("text"), (before["draft"] or {}).get("text"))
        self.assertEqual(again["limits"], [])  # nothing left CasePath in between
        self.assertEqual((again["consequences"]["basis"], again["consequences"]["undone"]), ("«Besteht der Schimmel weiterhin?»: erledigt", True))
        self.assertEqual(self.edit(case["id"], "settle_request", {"request": "r3.0", "how": "erledigt"}).status_code, 422)  # answered already
        self.assertIn('data-settle="${raw(x.request)}" data-how="nicht_mehr_noetig"', SCRIPT)

    def test_a_corrected_party_reaches_greeting_letters_and_title(self):
        case = self.seeded()
        self.updated(case["id"])
        self.edit(case["id"], "set_fact", {"fact": "deckung", "value": "bestätigt"})
        before = self.view(case["id"])
        self.assertIn("\nSehr geehrte Frau Exempel\n", before["draft"]["text"])
        self.assertEqual(self.edit(case["id"], "set_party", {"role": "kunde", "name": "Sara Beispiel", "salutation": "Frau"}, "Name korrigiert").status_code, 201)
        moved = self.edit(case["id"], "set_party", {"role": "gegenpartei", "name": "Muster Verwaltungen AG"}, "Verwaltung gewechselt").json()
        after = self.view(case["id"])
        parties = {i["label"]["de"]: i["value"] for i in after["items"] if i["kind"] == "party"}
        self.assertEqual((parties["Mieterin (VN)"], parties["Verwaltung (GP)"]), ("Frau Sara Beispiel", "Muster Verwaltungen AG"))
        self.assertIn("\nSehr geehrte Frau Beispiel\n", after["draft"]["text"])  # the greeting
        self.assertIn("Muster Verwaltungen AG", after["case"]["parties"])  # the case list's title line
        self.assertIn("Muster Verwaltungen AG", self.row(case["id"])["parties"] or after["case"]["display_title"])
        ctx = letters._context_parties(after["case"], after["items"], [], [], None, facts={"gegenpartei": NS.names["gp"]})
        self.assertEqual(ctx["gegenpartei"], "Muster Verwaltungen AG")  # the letters' other side: the one the handler named
        self.assertEqual(moved["consequences"]["basis"], "Gegenpartei: Muster Verwaltungen AG (Verwaltung gewechselt; dev)")
        self.client.post(f"/api/edits/{moved['edit']['id']}/undo")
        self.assertEqual({i["label"]["de"]: i["value"] for i in self.view(case["id"])["items"] if i["kind"] == "party"}["Verwaltung (GP)"], NS.names["gp"])

    def test_one_correction_reaches_requirements_obligations_draft_note_and_queue(self):
        """P-contra («Mangel behoben») after the update and the cover decision: the package changes where it rests on the
        fact, each change shown before and after with the correction as its basis; the handler's own entry and decision
        stay; undo restores the whole package."""
        case = self.seeded()
        self.updated(case["id"])
        self.edit(case["id"], "set_fact", {"fact": "deckung", "value": "bestätigt"})
        call = self.client.post(f"/api/cases/{case['id']}/entries", json={"kind": "notiz", "party": "kunde", "date": NS.day(36).isoformat(),
                                                                         "said": "Unterlagen gesichtet."})
        self.assertEqual(call.status_code, 201, call.text)
        before = self.view(case["id"])
        contra = NS.perturbations["P-contra"]
        made = self.client.post(f"/api/cases/{case['id']}/edits", json=contra.edit)
        self.assertEqual(made.status_code, 201, made.text)
        change = made.json()["consequences"]
        self.assertEqual(change["basis"], "Besteht der Mangel aktuell noch?: ja → nein (Mangel behoben (Telefon mit der Kundin); dev)")
        moved = {c["what"]: c for c in change["changes"]}
        self.assertIn("Brieftext", moved)  # the letter: what rested on the defect still being there is gone
        self.assertTrue(any("Frist zur Beseitigung" in x for x in moved["Brieftext"]["before"]))
        self.assertFalse(any("Frist zur Beseitigung" in x for x in moved["Brieftext"]["after"]))
        self.assertIn("Aktennotiz", moved)  # the case note says what was decided
        self.assertTrue(any("Besteht der Mangel aktuell noch?: nein" in x for x in moved["Aktennotiz"]["after"]))
        after = self.view(case["id"])
        self.assertNotIn("Frist zur Beseitigung", after["draft"]["text"])
        self.assertIn("Besteht der Mangel aktuell noch?: nein", after["file_note"])
        self.assertEqual(after["status"], self.row(case["id"])["stand"])  # the queue and the case agree
        # the handler's own entry and decision stay in force
        active = {(e["op"], (e["args"] or {}).get("fact") or (e["args"] or {}).get("kind")) for e in self.store.list_edits(case["id"])}
        self.assertTrue({("set_fact", "deckung"), ("add_entry", "notiz"), ("set_fact", "mangel_besteht")} <= active)
        undo = self.client.post(f"/api/edits/{made.json()['edit']['id']}/undo").json()
        self.assertEqual({c["what"] for c in undo["consequences"]["changes"]}, {"Brieftext", "Aktennotiz"})
        self.assertEqual(undo["consequences"]["basis"], "Besteht der Mangel aktuell noch?: nein")  # what is taken back
        back = self.view(case["id"])
        self.assertEqual((back["draft"]["text"], back["file_note"], back["status"], back["items_sha256"]),
                         (before["draft"]["text"], before["file_note"], before["status"], before["items_sha256"]))
        self.assertTrue({("set_fact", "deckung"), ("add_entry", "notiz")} <= {(e["op"], (e["args"] or {}).get("fact") or (e["args"] or {}).get("kind"))
                                                                              for e in self.store.list_edits(case["id"])})
        # an undo names what it cannot reach: a letter copied after the correction stays as it was
        made = self.client.post(f"/api/cases/{case['id']}/edits", json=contra.edit).json()
        self.client.post(f"/api/cases/{case['id']}/events", json={"kind": "letter.copied", "fields": {"form": "A5"}})
        limits = self.client.post(f"/api/edits/{made['edit']['id']}/undo").json()["limits"]
        self.assertEqual(len(limits), 1)
        self.assertRegex(limits[0], r"^Brief am \d\d\.\d\d\.\d{4} kopiert: der kopierte Text bleibt, wie er war")
        self.assertIn('T("Not undone", "Nicht rückgängig")', SCRIPT)

    def test_the_edits_route_refuses_a_dispatch(self):
        case = self.seeded()
        dispatch = self.edit(case["id"], "add_dispatch", {"n": 9001, "date": "2026-09-08", "to": "kunde"}, "Versandt")
        self.assertEqual((dispatch.status_code, dispatch.json()["detail"]), (422, "Ein Versand wird mit «Versandt am» bestätigt, nicht hier."))
        source, copy = episode.seed_frozen_copy(self.store, self.runs)
        self.assertEqual(self.edit(copy["id"], "add_dispatch", {"n": 9001}, "Versandt").status_code, 422)  # on a study copy too
        self.assertEqual(self.edit(copy["id"], "settle_request", {"request": "r7", "how": "erledigt"}, "x").status_code, 409)
        self.assertEqual(self.edit(copy["id"], "set_party", {"role": "kunde", "name": "X"}, "x").status_code, 409)
        self.assertEqual(self.store.list_edits(case["id"]) + self.store.list_edits(copy["id"]), [])


if __name__ == "__main__":
    unittest.main()
