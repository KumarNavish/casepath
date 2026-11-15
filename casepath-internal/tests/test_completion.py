"""The decision carried through (process/completion.py, web/actions.py, the queue in web/listing.py): an approval holds only
for the exact version and premise approved, its Versandpaket is stored in the same request, a dispatch is the handler's
attributed confirmation per recipient that writes the account, acknowledgement and fulfilment come from evidence, the
queue says what needs judgment, what is ready, what waits and what failed. A copy is never a sending, a payment
instruction never a payment, a deadline letter never the deadline kept.

Scripted and model-free, on S-D11A (tests/episode.py, synthetic) and the synthetic fixtures of the other tests."""
from datetime import date, timedelta
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import tempfile
import threading
import unittest
import zipfile

from fastapi.testclient import TestClient

from casepath.agents import core
from casepath.config import load_settings
from casepath.process import account, area, completion, items as item_rules, letters, screen
from casepath.process.clock import follow_up
from casepath.web import listing
from casepath.web.app import create_app
from casepath.web.store import CaseStore
from tests import episode

WF = area.workflow("mietmangel-handler")
FORMS = WF["forms"]
EP = episode.EPISODE
USER = "N. Kumar"
GAP = re.compile(r"\[bitte ergänzen: [^\]]*\]")


# -- the log as the service writes it (synthetic) ---------------------------------------------------------------------------

def approved(form, version="v1", at="2026-11-15T09:00:00+00:00", to=("kunde",), forms=None, also=(), respond_by=None, deadline=None,
             premise=None, title=None, text="Brief", by=USER, **fields):
    """An «action.approved» event as web/actions.py records it."""
    rows = [{"to": r, "recipient": f"Sehr geehrte Damen und Herren · {r}", "title": completion.FOLDERS.get(r, r),
             "forms": (forms or {}).get(r) or ([form, *also] if i == 0 else []), "titles": {form: title or form}} for i, r in enumerate(to)]
    return {"kind": "action.approved", "event_id": f"ev-ap-{version}", "expert": by, "at": at, "version": version, "form": form,
            "action_kind": re.match(r"A\d+", form).group(0) if re.match(r"A\d+", form) else form, "title": title or form, "recipients": rows,
            "respond_by": respond_by, "premise": premise or {}, "text_sha256": completion.sha(text),
            "also": [{"kind": k, "sha256": "0" * 64} for k in also], **({"deadline": deadline} if deadline else {}), **fields}


def saved(version="v1", at="2026-11-15T09:00:01+00:00"):
    return {"kind": "bundle.saved", "event_id": f"ev-bs-{version}", "expert": USER, "at": at, "version": version, "sha256": "1" * 64, "bytes": 10}


def sent(version="v1", day="2026-11-15", recipient="kunde", channel="email", edit="ed1", at="2026-11-15T10:00:00+00:00", **fields):
    return {"kind": "action.dispatched", "event_id": f"ev-di-{edit}", "expert": USER, "at": at, "version": version, "recipient": recipient,
            "edit_id": edit, "date": day, "channel": channel, **fields}


def copied(form, at="2026-11-15T10:00:00+00:00", measure=True, **fields):
    return {"kind": "letter.copied", "event_id": f"ev-co-{form}-{at}", "expert": USER, "at": at, "form": form,
            **({"measure": True, "text_sha256": fields.pop("text_sha256", "0" * 64)} if measure else {}), **fields}


def dispatch_edit(form="A5", day="2026-09-08", n=9001, eid="d1", asks=(), answers=(), version="v1", status="active", to="kunde"):
    """An «add_dispatch» edit as the store writes it (completion.dispatch_args)."""
    _, kind, code = completion.record_of(form)
    return {"id": eid, "op": "add_dispatch", "status": status, "by": USER, "at": f"{day}T10:00:00+00:00",
            "args": {"version": version, "form": form, "recipient": to, "to": to, "n": n, "date": day, "channel": "email", "kind": kind,
                     "code": code, "title": (FORMS.get(form) or {}).get("title") or form, "asks": list(asks), "answers": list(answers)}}


def phase_b():
    """S-D11A after the replies of d+35: (result, files) of the scripted update."""
    if not hasattr(phase_b, "cached"):
        prior, _ = episode.prepared(EP)
        files = [EP.dossier] + EP.files_b
        outcome, _ = episode.updated(prior, files, EP.turns_b())
        assert outcome["status"] == "completed", outcome.get("error")
        phase_b.cached = (outcome["result"], files)
    return phase_b.cached


def letter_of(state, listed, events, files, day=None):
    """The prepared letter as the case view shows it (letters.draft and completion.prepare), on the day the case is looked at."""
    act = next(i for i in listed if i["kind"] == "next_action")
    clock = follow_up(act.get("next_in_days"), files, events, since=act.get("since"), until=act.get("until"), step=act.get("action"))
    return completion.prepare(letters.draft({**state, "case": state.get("case") or episode.case_row()}, listed, events, clock, files, FORMS), {}, listed), clock


def stand_of(listed, follow=None, events=(), completion_=None, files=(), today=None, closed=False, run_status="completed", new_files=0, run_kind=None):
    return listing.stand(closed=closed, run_status=run_status, new_files=new_files, items=listed, follow_up=follow, events=list(events),
                         completed_at="2026-11-01T08:00:00", files=list(files), today=today, run_kind=run_kind, completion=completion_)


# -- the service on S-D11A: one template store, copied for each test -------------------------------------------------------

TEMPLATE = {}


def template():
    """A data directory holding S-D11A after the scripted update of the two replies (Phase B), built once."""
    if "dir" not in TEMPLATE:
        root = Path(tempfile.mkdtemp(prefix="cp-b-template-"))
        (root / "catalogue").mkdir()
        app = create_app(load_settings({"CASEPATH_DATA_DIR": str(root / "data"), "CASEPATH_WORKFLOW_CATALOGUE": str(root / "catalogue"),
                                        "CASEPATH_DEV_USER": USER}), model_factory=lambda: None)
        store, runs = app.state.store, app.state.runs
        case = episode.seed_phase_a(store, runs, EP)
        episode.add_replies(store, case["id"])
        runs.model_factory = lambda token=None: episode.update_model(store, case["id"], EP.turns_b(), EP.reply_names)
        run = episode.wait(store, runs.update(case["id"], USER)["id"])
        assert run["status"] == "completed", run.get("error")
        source, study = episode.seed_frozen_copy(store, runs)
        runs.shutdown()
        store.close()
        TEMPLATE.update(dir=root, case=case["id"], study=study["id"])
    return TEMPLATE


class Service(unittest.TestCase):
    """S-D11A on the case service, after the replies; no tests of its own."""

    def setUp(self):
        t = template()
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        shutil.copytree(t["dir"], self.root, dirs_exist_ok=True)
        self.case, self.study = t["case"], t["study"]
        self.client = self.app()

    def app(self, user=USER):
        return TestClient(create_app(load_settings({"CASEPATH_DATA_DIR": str(self.root / "data"), "CASEPATH_WORKFLOW_CATALOGUE": str(self.root / "catalogue"),
                                                    "CASEPATH_DEV_USER": user}), model_factory=lambda: None))

    def tearDown(self):
        self.client.app.state.runs.shutdown()
        self.client.app.state.store.close()
        self.directory.cleanup()

    @property
    def store(self):
        return self.client.app.state.store

    def view(self, client=None):
        return (client or self.client).get(f"/api/cases/{self.case}").json()

    def decide(self, fact, value):
        r = self.client.post(f"/api/cases/{self.case}/edits", json={"op": "set_fact", "args": {"fact": fact, "value": value}, "reason": "",
                                                                     "reason_code": "none", "recheck": False})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["edit"]

    def fill(self, client=None, op="op-fill-1"):
        """The handler writes what only the handler can write into each gap of the letter (saved per part)."""
        draft = self.view(client)["draft"]
        parts = [{"part": p["part"], "base_sha256": p["base_sha256"], "text": GAP.sub("wie besprochen", p["text"])} for p in draft["parts"] if GAP.search(p["text"])]
        if not parts:
            return draft
        r = (client or self.client).put(f"/api/cases/{self.case}/drafts/{draft['form']}", json={"parts": parts, "parent_id": draft.get("draft_id"), "op_id": op})
        self.assertEqual(r.status_code, 200, r.text)
        return self.view(client)["draft"]

    def ready(self):
        """Deckung confirmed, the prospects sufficient, the gaps filled: the A5 as it can be approved."""
        self.decide("deckung", "bestätigt")
        self.decide("aussichten", "genügend")
        return self.fill()

    def approve(self, draft=None, op="op-approve-1", expect=200):
        draft = draft or self.view()["draft"]
        r = self.client.post(f"/api/cases/{self.case}/actions/approve", json={"form": draft["form"], "version": draft["version"], "op_id": op})
        self.assertEqual(r.status_code, expect, r.text)
        return r.json()

    def dispatch(self, version, day=None, op="op-dispatch-1", expect=200, **body):
        r = self.client.post(f"/api/cases/{self.case}/actions/dispatch", json={"version": version, "date": day or date.today().isoformat(),
                                                                             "channel": "email", "op_id": op, **body})
        self.assertEqual(r.status_code, expect, r.text)
        return r.json()

    def events(self, kind=None):
        return [e for e in self.store.list_case_events(self.case) if kind is None or e["kind"] == kind]

    def row(self):
        return next(c for c in self.client.get("/api/cases").json()["cases"] if c["id"] == self.case)


# -- 1, 2: a copy is measurement; a legacy copy is contact only --------------------------------------------------------------

class CopyTests(unittest.TestCase):
    def test_a_copy_is_measured_and_never_counts_as_sent(self):
        from tests.test_package import SETTLED, build
        # the steering's probe: three copies of the settlement's letters after a confirmed agreement, no IBAN, nothing paid
        probe = [copied("A11_iban"), copied("A11_auszahlung", at="2026-11-15T10:01:00+00:00"), copied("A11_eingang", at="2026-11-15T10:02:00+00:00")]
        for events in (probe, [{**e, "measure": None} for e in probe]):  # measured or by a browser before this release alike
            listed, items, _ = build(SETTLED, history="A1 2026-09-01; A5 2026-10-01; A8 2026-10-10", events=events,
                                     set_by_hand={"eingang_erledigt_bis": "2026-11-06", "vergleich_bestaetigt": "ja"})
            nxt = listed["next_action:0"]
            self.assertEqual((nxt["action"], nxt["form"]), ("A11", "A11_iban"))  # no «Dossier abschliessen»
            self.assertNotIn("Zahlungseingang bestätigt", nxt.get("reason") or "")
            self.assertFalse(nxt["settlement"]["iban"])
        # an A5 copied is not «erledigt», a copy naming no form is not the step
        a5 = [{"kind": "next_action", "key": "0", "item_id": "next_action:0", "action": "A5", "label": {"de": "Rechtliche Einschätzung"}}]
        for events in ([copied("A5")], [copied(None)], [copied("A5", measure=False)]):
            row = stand_of(a5, "2026-12-20", events, today=date(2026, 11, 15))
            self.assertEqual((row["bucket"], row["text"]), ("urteil", "vorbereitet"))
        # a template copied writes no «Versandt»; «Frist wahren» copied is not the deadline kept
        note = letters.file_note({"title": "x"}, [], [copied(None, also="vorlage:einsprache"), copied("A13")], None, [])
        self.assertNotIn("Versandt", note)
        deadline = {"item_id": "deadline:einsprache_strafbefehl"}
        self.assertFalse(item_rules.wahrt([copied("A13", deadline=deadline["item_id"]), copied(None, also="vorlage:einsprache")], deadline,
                                          {"id": "einsprache"}))
        self.assertFalse(completion.contacted([copied("A1")]))  # a measured copy is not even contact
        self.assertEqual(completion.dispatches([copied("A1"), copied("A1", measure=False)]), [])

    def test_a_legacy_copy_counts_as_contact_only_and_offers_versandt_am(self):
        from tests.test_cover import TENANT, view
        legacy = {"kind": "letter.copied", "at": "2026-11-13T10:00:00", "form": "A1"}  # no «measure»: a browser before this release
        here = dict(segments=[{"date": "12.11.2026", "kind": "Schadenmeldung", "sender": "Lea Beispiel"}], as_of=None, created="2026-11-13T09:12:00")
        _, listed, _ = view(TENANT, events=[legacy], **here)
        self.assertNotIn("contact:erstkontakt", listed)  # contact: no «Erstkontakt überfällig»
        self.assertIn("contact:erstkontakt", view(TENANT, events=[{**legacy, "measure": True}], **here)[1])  # a measured copy is no contact
        ctx = letters._context_contact({"title": "x"}, [], [legacy], [], date(2026, 11, 15))
        self.assertEqual(ctx["wahren_eingang"], "Vielen Dank für Ihre Nachricht.")
        self.assertTrue(completion.contacted([legacy]))
        self.assertEqual(completion.sent_letters([legacy]), [])  # never sent, so never fulfilled or settled
        # of the current form after the prepared run, without an approval: «kopiert, Versand nicht bestätigt», ready to send
        draft = {"form": "A1", "kind": "A1", "text": "Brief", "recipients": [{"to": "kunde", "recipient": "x", "forms": ["A1"]}], "version": "v1"}
        st = completion.state({}, [], draft, [legacy], [], today=date(2026, 11, 15), prepared_at="2026-11-12T08:00:00")
        self.assertEqual((st["bucket"], st["status"], st["state"]), ("versandbereit", "kopiert, Versand nicht bestätigt", "entwurf"))
        self.assertEqual((st["bar"]["kind"], st["bar"]["label"], st["bar"]["earliest"]), ("approve", "Freigeben", "2026-11-13"))
        self.assertIsNone(completion.state({}, [], draft, [legacy], [], prepared_at="2026-11-14T08:00:00")["legacy_copy"])  # before the run
        self.assertEqual(stand_of([], "2026-12-01", [legacy], st)["bucket"], "versandbereit")
        # approved on a later day, «Versandt am» allows the day of the copy
        later = approved("A1", at="2026-11-15T09:00:00+00:00", text="Brief")
        self.assertEqual(completion.earliest(later, [legacy, later], "A1"), "2026-11-13")
        self.assertEqual(completion.earliest(later, [later], "A1"), "2026-11-15")


class LegacyServiceTests(Service):
    def test_the_legacy_copys_day_is_allowed_for_versandt_am_and_it_never_fulfils(self):
        draft = self.ready()
        earlier = date.today() - timedelta(days=2)
        with self.store._lock:  # the case was prepared three days ago, a browser before this release copied its letter two days ago
            self.store._db.execute("update runs set created_at=? where case_id=? and status='completed'", (f"{date.today() - timedelta(days=3)}T08:00:00+00:00", self.case))
        logged = self.store.append_case_event(self.case, {"kind": "letter.copied", "form": "A5", "expert": USER})
        with self.store._lock:
            self.store._db.execute("update events set data=? where event_id=?",
                                   (json.dumps({**logged, "at": f"{earlier}T08:00:00+00:00"}, ensure_ascii=False), logged["event_id"]))
        st = self.view()["completion"]
        self.assertEqual((st["bucket"], st["status"], st["bar"]["label"]), ("versandbereit", "kopiert, Versand nicht bestätigt", "Freigeben"))
        self.assertEqual(self.row()["stand"]["text"], "kopiert, Versand nicht bestätigt")
        self.approve(self.view()["draft"])
        self.dispatch(draft["version"], day=(earlier - timedelta(days=1)).isoformat(), expect=422)  # before the copy: refused
        self.dispatch(draft["version"], day=earlier.isoformat())  # the day of the copy: allowed
        self.assertEqual(self.events("action.dispatched")[-1]["date"], earlier.isoformat())
        self.assertFalse(self.view()["completion"]["fulfilled"])


# -- 3, 4: the version -------------------------------------------------------------------------------------------------------

class VersionTests(unittest.TestCase):
    def test_the_version_changes_with_text_recipient_attachments_and_date_and_not_with_an_unrelated_rerun(self):
        rows = [{"to": "kunde", "recipient": "Sehr geehrte Frau Exempel · Frau Sara Exempel"}]
        parts = [{"part": "head", "text": "Guten Tag"}, {"part": "p0", "text": "Vielen Dank."}]
        also = [{"kind": "vorlage:maengelruege", "text": "Vorlage", "template": True}]
        base = completion.version_of("A5", rows, parts, also, None)
        self.assertEqual(base, completion.version_of("A5", [dict(r) for r in rows], [dict(p) for p in parts], [dict(a) for a in also], None))
        changed = {"text": completion.version_of("A5", rows, parts[:1] + [{"part": "p0", "text": "Vielen Dank!"}], also, None),
                   "recipient": completion.version_of("A5", [{"to": "kunde", "recipient": "Sehr geehrte Damen und Herren · Name nicht in der Akte"}], parts, also, None),
                   "attachment": completion.version_of("A5", rows, parts, [{**also[0], "text": "Vorlage, ergänzt"}], None),
                   "date": completion.version_of("A5", rows, parts, also, "2026-12-01"), "form": completion.version_of("A6", rows, parts, also, None)}
        self.assertEqual(len({base, *changed.values()}), 6)
        # an unrelated re-run renders the same letter: the same version, so an approval of it holds
        listed = lambda result: build_view(result)
        a, b = episode.prepared(EP)[0], episode.prepared(EP)[0]
        self.assertNotEqual(id(a), id(b))
        self.assertEqual(listed(a["result"]), listed(b["result"]))

    def test_the_frozen_reply_date_keeps_the_approval_until_too_little_time_is_left(self):
        result, files = phase_b()
        day = EP.day(34)
        state, listed = episode.view(result, [EP.dossier], day)  # d+34: the pending letter sets the customer a date ({frist})
        events = []
        draft, clock = letter_of(state, listed, events, episode.looked_at([EP.dossier], day))
        self.assertTrue(draft["respond_by"])
        approval = approved(draft["form"], version=draft["version"], at=f"{day}T09:00:00+00:00", respond_by=draft["respond_by"],
                            text=draft["text"], recipients=None)
        approval["recipients"] = [{k: r[k] for k in ("to", "recipient", "forms")} for r in draft["recipients"]]
        self.assertGreater((date.fromisoformat(draft["respond_by"]) - day).days, 7)  # the pending letter's period
        for later, holds in ((1, True), (3, True), (4, False)):  # held while the form's period less three days is left
            look = day + timedelta(days=later)
            state, listed = episode.view(result, [EP.dossier], look)
            now, _ = letter_of(state, listed, [approval], episode.looked_at([EP.dossier], look))
            self.assertEqual(now["respond_by"] == draft["respond_by"], holds, later)  # the letter keeps the frozen date while it holds
            reasons = completion.validity(approval, now, state["facts"], today=look)
            self.assertEqual(reasons == [], holds, (later, reasons))
            if not holds:
                self.assertEqual(reasons[0], "Datum")


def build_view(result):
    state, listed = episode.view(result, [EP.dossier], EP.day(34))
    return letter_of(state, listed, [], episode.looked_at([EP.dossier], EP.day(34)))[0]["version"]


# -- 5 to 8: approval and its validity --------------------------------------------------------------------------------------

class ApprovalTests(Service):
    def test_approval_needs_the_current_version_no_gap_every_required_part_and_the_decisions(self):
        self.decide("deckung", "bestätigt")
        draft = self.view()["draft"]
        self.assertEqual(draft["form"], "A5")
        refused = lambda body, status: self.client.post(f"/api/cases/{self.case}/actions/approve", json=body)
        r = refused({"form": "A5", "version": "0" * 64, "op_id": "op-v-1"}, 409)
        self.assertEqual((r.status_code, r.json()["detail"]), (409, "Der Entwurf hat sich seit dem Laden geändert; bitte neu laden."))
        r = refused({"form": "A5", "version": draft["version"], "op_id": "op-g-1"}, 422)
        self.assertEqual(r.status_code, 422)
        self.assertRegex(r.json()["detail"], r"^Noch \d+ Lücken? im Brief$")
        draft = self.fill()
        r = refused({"form": "A5", "version": draft["version"], "op_id": "op-d-1"}, 422)  # an assessment needs the prospects, in every area
        self.assertEqual((r.status_code, r.json()["detail"]), (422, "Zuerst entscheiden: Erfolgsaussichten"))
        self.decide("aussichten", "genügend")
        draft = self.view()["draft"]
        self.client.post(f"/api/cases/{self.case}/files", files={"file": ("Nachtrag.txt", "Noch eine Nachricht der Kundin.".encode(), "text/plain")})
        view = self.view()
        self.assertTrue(view["draft_stale"])
        r = refused({"form": "A5", "version": view["draft"]["version"], "op_id": "op-s-1"}, 422)
        self.assertEqual((r.status_code, r.json()["detail"]), (422, "Neue Unterlagen sind noch nicht gelesen."))
        self.assertEqual(self.events("action.approved"), [])  # nothing recorded on a refusal
        # the required parts, the decisions of the assessment and a clash, as the service checks them (completion.refusal)
        letter = {"form": "A10_kunde", "text": "Information ohne die Pflichtsätze", "version": "v", "required": [{"id": "x", "title": "Freie Anwaltswahl",
                                                                                                          "marker": "frei wählen und vorschlagen", "basis": "Art. 167 AVO"}]}
        self.assertEqual(completion.refusal({}, letter, "v"), (422, "Pflichtteil fehlt: Freie Anwaltswahl (Art. 167 AVO)"))
        self.assertEqual(completion.refusal({}, {**letter, "required": []}, "v", ["Deckung", "Empfehlung"]), (422, "Zuerst entscheiden: Deckung, Empfehlung"))
        self.assertEqual(completion.refusal({}, {**letter, "required": [], "conflicts": [{"part": "p5"}]}, "v"),
                         (422, "Ihr Text betraf einen geänderten Absatz: bitte prüfen"))
        self.assertEqual(completion.refusal({"intake": {"study": {"source_case": "c"}}}, letter, "v"), (409, "Eine Studienkopie wird nicht freigegeben."))
        self.assertEqual(completion.open_decisions({"kind": "A5", "form": "A5", "needs": ["deckung"]}, {"deckung": "bestätigt"},
                                                   {"blocking": [{"kind": "decision", "key": "empfehlung"}]}), ["Erfolgsaussichten", "Empfehlung"])

    def test_undoing_the_cover_decision_after_approval_makes_it_stale(self):
        cover = self.decide("deckung", "bestätigt")
        self.decide("aussichten", "genügend")
        draft = self.fill()
        self.approve(draft)
        self.assertEqual(self.row()["stand"]["bucket"], "versandbereit")
        self.client.post(f"/api/edits/{cover['id']}/undo")
        view = self.view()
        self.assertEqual(view["completion"]["stale"][0], "Entscheid geändert")
        self.assertEqual(view["completion"]["status"], "Freigabe veraltet: Entscheid geändert")
        self.assertEqual(view["screen"]["head"]["stale"], "Freigabe veraltet: Entscheid geändert")
        row = self.row()
        self.assertEqual((row["stand"]["bucket"], row["stand"]["text"]), ("urteil", "Freigabe veraltet: Entscheid geändert"))

    def test_a_premise_change_with_identical_text_makes_the_approval_stale(self):
        self.decide("deckung", "bestätigt")
        prospects = self.decide("aussichten", "genügend")
        draft = self.fill()
        self.approve(draft)
        self.client.post(f"/api/edits/{prospects['id']}/undo")
        view = self.view()
        self.assertEqual(view["draft"]["version"], draft["version"])  # the same text
        self.assertEqual(view["completion"]["stale"], ["Entscheid geändert"])
        # a fact the assessment rests on changes while the letter stays word for word the same
        approval = self.events("action.approved")[-1]
        assessment = {"premise": {"mangel_besteht": True}}
        facts = {"deckung": "bestätigt", "aussichten": "genügend", "mangel_besteht": True}
        record = {**approval, "premise": completion.premise(view["draft"], facts, assessment)}
        self.assertEqual(completion.validity(record, view["draft"], facts, assessment), [])
        self.assertEqual(completion.validity(record, view["draft"], {**facts, "mangel_besteht": False}, assessment), ["Voraussetzung geändert"])

    def test_an_approval_of_another_form_is_stale(self):
        draft = {"form": "A5", "kind": "A5", "text": "Brief", "version": "v2", "recipients": [], "needs": []}
        st = completion.state({}, [], draft, [approved("A6", version="v1"), saved("v1")], [], today=date(2026, 11, 15),
                              facts={"aussichten": "genügend"})
        self.assertEqual((st["state"], st["stale"], st["status"]), ("freigegeben", ["Schritt geändert"], "Freigabe veraltet: Schritt geändert"))
        self.assertEqual(st["bar"]["label"], "Erneut freigeben")


# -- 9, 10: the handler's text per part ---------------------------------------------------------------------------------------

class DraftTests(Service):
    def test_a_draft_edit_survives_reload_handoff_and_restart_and_a_second_writer_gets_409(self):
        draft = self.view()["draft"]
        part = next(p for p in draft["parts"] if p["part"] == "p0")
        body = {"parts": [{"part": "p0", "base_sha256": part["base_sha256"], "text": part["text"] + " Ergänzt von Hand."}], "parent_id": draft.get("draft_id"),
                "op_id": "op-edit-1"}
        first = self.client.put(f"/api/cases/{self.case}/drafts/{draft['form']}", json=body)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertIn("Ergänzt von Hand.", self.view()["draft"]["text"])  # reload
        again = self.client.put(f"/api/cases/{self.case}/drafts/{draft['form']}", json=body)  # the same operation sent twice
        self.assertEqual(again.json()["id"], first.json()["id"])
        other = self.app("L. Muster")
        try:
            self.assertIn("Ergänzt von Hand.", self.view(other)["draft"]["text"])  # handoff
            stale = other.put(f"/api/cases/{self.case}/drafts/{draft['form']}", json={**body, "op_id": "op-edit-2", "parent_id": None})
            self.assertEqual((stale.status_code, stale.json()["detail"]), (409, f"Inzwischen von {USER} geändert: neu laden"))
        finally:
            other.app.state.runs.shutdown()
        self.client.app.state.runs.shutdown()
        self.store.close()  # restart: a new store on the same directory
        self.client = self.app()
        view = self.view()
        self.assertIn("Ergänzt von Hand.", view["draft"]["text"])
        self.assertEqual(view["draft"]["saved"]["p0"]["by"], USER)
        self.assertEqual(CaseStore(self.root / "data").latest_drafts(self.case)[draft["form"]]["parts"]["p0"]["text"], body["parts"][0]["text"])

    def test_a_correction_merges_by_part_keeps_the_handlers_and_flags_a_clash(self):
        base = [("head", "Guten Tag"), ("p0", "Vielen Dank."), ("p5", "Bitte reichen Sie uns noch nach:\n– Belege zu: Stromkosten"), ("tail", "Grüsse")]
        row = lambda part, base_text, text: {"id": "dr1", "by": USER, "at": "x", "base_sha256": completion.sha(base_text), "base": base_text, "text": text}
        mine = {"parts": {"p0": row("p0", "Vielen Dank.", "Vielen Dank für Ihre Geduld."), "p5": row("p5", base[2][1], base[2][1] + "\n– Fotos")}}
        parts, clashes = completion.merge(base, mine)
        self.assertEqual([p["text"] for p in parts][1:3], ["Vielen Dank für Ihre Geduld.", base[2][1] + "\n– Fotos"])  # the handler's text stands
        self.assertEqual(clashes, [])
        new = [("head", "Guten Tag Frau Exempel"), ("p0", "Vielen Dank."), ("tail", "Grüsse")]  # a correction: the residual is gone (P-retract)
        parts, clashes = completion.merge(new, mine)
        self.assertEqual([p["text"] for p in parts], ["Guten Tag Frau Exempel", "Vielen Dank für Ihre Geduld.", "Grüsse"])  # untouched: the new base
        self.assertEqual([(c["part"], c.get("gone")) for c in clashes], [("p5", True)])
        both = [("head", "Guten Tag"), ("p0", "Vielen herzlichen Dank."), base[2], ("tail", "Grüsse")]  # changed on both sides
        parts, clashes = completion.merge(both, mine)
        self.assertEqual([(c["part"], c["mine"], c["new"]) for c in clashes], [("p0", "Vielen Dank für Ihre Geduld.", "Vielen herzlichen Dank.")])
        self.assertEqual(parts[1]["text"], "Vielen herzlichen Dank.")  # the letter shows the new text until the handler decides
        # resolved: keeping mine on the new base, taking the new text, and keeping a part that went
        kept = {"parts": {**mine["parts"], "p0": row("p0", "Vielen herzlichen Dank.", "Vielen Dank für Ihre Geduld.")}}
        self.assertEqual(completion.merge(both, kept)[0][1]["text"], "Vielen Dank für Ihre Geduld.")
        taken = {"parts": {**mine["parts"], "p0": row("p0", "Vielen herzlichen Dank.", "Vielen herzlichen Dank.")}}
        self.assertEqual((completion.merge(both, taken)[0][1]["text"], completion.merge(both, taken)[1]), ("Vielen herzlichen Dank.", []))
        reinstated = {"parts": {**mine["parts"], "p5": row("p5", "", base[2][1] + "\n– Fotos")}}
        parts, clashes = completion.merge(new, reinstated)
        self.assertEqual(([p["part"] for p in parts], clashes), (["head", "p0", "p5", "tail"], []))

    def test_both_resolve_actions_through_the_service(self):
        draft = self.view()["draft"]
        p = next(x for x in draft["parts"] if x["part"].startswith("p"))
        # the handler edits a part, then the case changes it (Deckung confirmed: the assessment is prepared instead)
        body = {"parts": [{"part": p["part"], "base_sha256": p["base_sha256"], "text": p["text"] + " Mit Gruss."}], "parent_id": draft.get("draft_id"), "op_id": "op-c-1"}
        self.assertEqual(self.client.put(f"/api/cases/{self.case}/drafts/{draft['form']}", json=body).status_code, 200)
        base = self.store.latest_drafts(self.case)[draft["form"]]["parts"][p["part"]]
        self.store.add_draft(self.case, draft["form"], [{"part": p["part"], "base_sha256": completion.sha("früher"), "base": "früher", "text": "Mein Satz."}],
                             USER, parent_id=self.store.latest_drafts(self.case)[draft["form"]]["id"])
        view = self.view()
        clash = view["draft"]["conflicts"]
        self.assertEqual([(c["part"], c["mine"]) for c in clash], [(p["part"], "Mein Satz.")])
        for keep, expected in (("mine", "Mein Satz."), ("new", p["text"])):
            if keep == "new":
                self.store.add_draft(self.case, draft["form"], [{"part": p["part"], "base_sha256": completion.sha("früher"), "base": "früher", "text": "Mein Satz."}],
                                     USER, parent_id=self.store.latest_drafts(self.case)[draft["form"]]["id"])
            r = self.client.post(f"/api/cases/{self.case}/drafts/{draft['form']}/resolve", json={"part": p["part"], "keep": keep})
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual((r.json()["conflicts"], next(x["text"] for x in r.json()["parts"] if x["part"] == p["part"])), ([], expected))
        self.assertTrue(base)


# -- 11, 12: the Versandpaket ------------------------------------------------------------------------------------------------

class BundleTests(Service):
    def test_approval_saves_one_deterministic_bundle_per_recipient_with_the_exact_text_enclosures_note_and_next_date(self):
        draft = self.ready()
        out = self.approve(draft)
        again = self.approve(draft, op="op-approve-2")  # the same version approved again: its record, no second package
        self.assertEqual(again["approval"]["event_id"], out["approval"]["event_id"])
        self.assertEqual(len(self.events("bundle.saved")), 1)
        r = self.client.get(f"/api/cases/{self.case}/actions/{draft['version']}/bundle")
        self.assertEqual(r.headers["cache-control"], "private, no-store")
        self.assertEqual(r.headers["content-disposition"], f'attachment; filename="Versandpaket_{EP.reference}_{date.today():%d.%m.%Y}.zip"')
        self.assertEqual(r.content, self.store.blob(out["bundle"]["sha256"]))
        archive = zipfile.ZipFile(io.BytesIO(r.content))
        names = sorted(archive.namelist())
        self.assertEqual(names, sorted(["Kundschaft/Brief.docx", "Kundschaft/Mängelrüge mit Frist zur Beseitigung.docx", "Beilagen.txt",
                                        "Aktennotiz.txt", "Wiedervorlage.txt", "manifest.json"]))
        self.assertTrue(all(i.date_time == (1980, 1, 1, 0, 0, 0) for i in archive.infolist()))
        letter = zipfile.ZipFile(io.BytesIO(archive.read("Kundschaft/Brief.docx"))).read("word/document.xml").decode()
        self.assertEqual("\n".join(re.findall(r'<w:t xml:space="preserve">([^<]*)</w:t>', letter)).replace("&amp;", "&"),
                         "\n".join(line for line in draft["text"].split("\n") if line.strip()))
        self.assertIn("Kundschaft (Sehr geehrte Frau Exempel · Frau Sara Exempel): Rechtliche Einschätzung; Mängelrüge mit Frist zur Beseitigung",
                      archive.read("Beilagen.txt").decode())
        self.assertIn("Zum Versand freigegeben am", archive.read("Aktennotiz.txt").decode())
        self.assertEqual(archive.read("Wiedervorlage.txt").decode().split("\n")[0], f"Wiedervorlage {date.today() + timedelta(days=90):%d.%m.%Y}")
        manifest = json.loads(archive.read("manifest.json"))
        self.assertEqual((manifest["format"], manifest["version"], manifest["form"], manifest["approved_by"]),
                         ("casepath.versandpaket/1", draft["version"], "A5", USER))
        self.assertEqual({p["name"]: p["sha256"] for p in manifest["parts"]}["Kundschaft/Brief.docx"],
                         hashlib.sha256(archive.read("Kundschaft/Brief.docx")).hexdigest())
        docx = self.client.get(f"/api/cases/{self.case}/actions/{draft['version']}/docx/vorlage:maengelruege")
        self.assertEqual(docx.content, archive.read("Kundschaft/Mängelrüge mit Frist zur Beseitigung.docx"))

    def test_the_approval_records_the_chosen_options_and_their_file(self):
        draft = {"form": "A5", "kind": "A5", "title": "Rechtliche Einschätzung", "text": "Brief", "version": "v", "parts": [{"part": "p0", "text": "Brief"}],
                 "recipients": [{"to": "kunde", "recipient": "x", "title": "Kundschaft", "forms": ["A5"], "titles": {"A5": "Rechtliche Einschätzung"}}]}
        assessment = {"chosen": ["frist_beseitigung", "schadenersatz"], "options_sha256": "a" * 64}
        record = completion.approval_record(draft, {"deckung": "bestätigt"}, assessment, run_id="run_1", files_digest="f" * 64, op_id="op")
        self.assertEqual((record["chosen"], record["options_sha256"], record["run_id"], record["files_digest"]),
                         (["frist_beseitigung", "schadenersatz"], "a" * 64, "run_1", "f" * 64))
        from casepath.web import bundle
        _, manifest = bundle.build(draft, {**record, "expert": USER, "at": "2026-11-15T09:00:00+00:00"}, "Notiz", [])
        self.assertEqual((manifest["chosen"], manifest["options_sha256"]), (assessment["chosen"], assessment["options_sha256"]))


# -- 13 to 16: the dispatch and what follows from it ------------------------------------------------------------------------

class DispatchTests(Service):
    def test_dispatch_is_attributed_idempotent_per_recipient_and_writes_the_account_entry_of_its_form(self):
        draft = self.ready()
        self.approve(draft)
        today = date.today().isoformat()
        self.dispatch(draft["version"], day=today)
        self.dispatch(draft["version"], day=today, op="op-dispatch-2")  # twice: one entry
        self.dispatch(draft["version"], day=today, op="op-dispatch-1")  # the same operation: its first result
        edits = [e for e in self.store.list_edits(self.case) if e["op"] == "add_dispatch"]
        self.assertEqual(len(edits), 1)
        self.assertEqual(len(self.events("action.dispatched")), 1)
        dispatched = self.events("action.dispatched")[0]
        self.assertEqual((dispatched["expert"], dispatched["recipient"], dispatched["channel"], dispatched["date"]), (USER, "kunde", "email", today))
        state = core.evaluate(WF, [], self.store.list_edits(self.case), self.store.latest_run(self.case, "completed")["result"], self.case)
        entry = next(e for e in state["account"]["entries"] if e.get("dispatch"))
        self.assertEqual((entry["kind"], entry["code"], entry["from"], entry["to"], entry["date"]), ("einschaetzung", "5", "versicherer", "kunde", today))
        codes = [a["code"] for a in state["account"]["actions"] if a["n"] == entry["n"]]
        self.assertEqual(codes, ["5"])  # its own code: no A2 (the phone code), never its kind's
        self.assertEqual(state["facts"]["handlung_a5"], today)
        kinds = account.kinds_of(state["process"])
        for form, code in (("A4", ["4"]), ("A8", ["8"]), ("A11_iban", []), ("A11_nachfragen", []), ("A10_kunde", []), ("A12_still", ["12"])):
            role, kind, own = completion.record_of(form)
            self.assertEqual(account.code_of({"from": "versicherer", "to": role if role != "payer" else "gegenpartei", "kind": kind, "code": own,
                                              "dispatch": {"version": "v"}}, kinds), code, form)
        undone = self.client.post(f"/api/edits/{edits[0]['id']}/undo")
        self.assertEqual(undone.status_code, 200)
        self.assertEqual(self.view()["completion"]["state"], "freigegeben")  # undone: the recipient is open again
        self.assertEqual(completion.dispatches(self.events()), [])

    def test_a_dispatch_and_a_handler_entry_never_share_a_number(self):
        numbers, errors = [], []

        def entry(i):
            try:
                numbers.append(self.store.add_numbered_edit(self.case, "add_entry", {"kind": "notiz", "party": "kunde", "date": "2026-11-15",
                                                                                      "said": f"Notiz {i}"}, USER, "Eintrag")["args"]["n"])
            except Exception as error:  # noqa: BLE001
                errors.append(error)

        def send(i):
            try:
                edit, _ = self.store.dispatch_once(self.case, f"v{i}", "kunde", {"version": f"v{i}", "recipient": "kunde", "to": "kunde",
                                                                                 "date": "2026-11-15", "form": "A5"}, USER, "Versandt",
                                                   {"kind": "action.dispatched", "version": f"v{i}", "recipient": "kunde"})
                numbers.append(edit["args"]["n"])
            except Exception as error:  # noqa: BLE001
                errors.append(error)
        threads = [threading.Thread(target=entry if i % 2 else send, args=(i,)) for i in range(16)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(sorted(numbers), list(range(9001, 9017)))
        r = self.client.post(f"/api/cases/{self.case}/entries", json={"kind": "notiz", "party": "kunde", "date": "2026-11-15", "said": "Noch eine."})
        self.assertEqual(r.json()["entry"]["n"], 9017)

    def test_a_stale_version_dispatched_is_flagged_not_refused(self):
        draft = self.ready()
        self.approve(draft)
        part = next(p for p in draft["parts"] if p["part"] == "p0")
        self.client.put(f"/api/cases/{self.case}/drafts/A5", json={"parts": [{"part": "p0", "base_sha256": part["base_sha256"], "text": "Danke."}],
                                                                   "parent_id": draft["draft_id"], "op_id": "op-late-edit"})
        view = self.view()
        self.assertEqual(view["completion"]["status"], "Freigabe veraltet: Text geändert")
        self.dispatch(draft["version"])  # the handler may have sent the approved text: accepted
        self.assertEqual(self.events("action.dispatched")[-1]["stale"], ["Text geändert"])
        st = self.view()["completion"]
        self.assertEqual((st["bucket"], st["status"]), ("urteil", "versandt mit früherem Stand – prüfen: Text geändert"))
        verlauf = [r for r in self.view()["verlauf"] if r.get("dispatch")]
        self.assertEqual(verlauf[0]["notes"][0]["text"], "versandt mit früherem Stand: Text geändert")


class AnswersTests(unittest.TestCase):
    def test_only_answered_questions_are_closed_and_a_conditional_answers_fact_is_asked(self):
        result, files = phase_b()
        assessment = {"questions": [{"item_id": "customer_question:0", "text": "Muss ich weiterhin die volle Miete bezahlen?", "state": "beantwortet", "entry": 13},
                                    {"item_id": "customer_question:1", "text": "Darf ich die Miete hinterlegen?", "state": "bedingt", "entry": 13},
                                    {"item_id": "customer_question:2", "text": "Werden mir die Stromkosten für den Bautrockner ersetzt?", "state": "bedingt",
                                     "entry": 15}],
                      "asks": [{"key": "residual:claim.0", "what": "Belege zu: Stromkosten für den Bautrockner", "kind": "claim", "ref": 0},
                               {"key": "fact:mangel_besteht", "what": "Besteht der Mangel weiterhin?", "kind": "fact", "ref": "mangel_besteht"}]}
        approval = approved("A5", version="v5", title="Rechtliche Einschätzung")
        args = completion.dispatch_args(approval, "kunde", "2026-09-08", "email", [], [], assessment)
        self.assertEqual(args["answers"], [{"what": "Muss ich weiterhin die volle Miete bezahlen?", "answers": 13}])
        self.assertEqual([(a["what"], a["kind"]) for a in args["asks"]], [("Belege zu: Stromkosten für den Bautrockner", "claim"),
                                                                          ("Besteht der Mangel weiterhin?", "fact")])
        taken = [{"kind": "item.corrected", "item_id": "customer_question:2"}]  # the handler took a drafted answer (SLICE_A A12)
        self.assertEqual(len(completion.dispatch_args(approval, "kunde", "2026-09-08", "email", [], taken, assessment)["answers"]), 2)
        edit = dispatch_edit(asks=args["asks"], answers=args["answers"])
        state = core.evaluate(WF, [], [edit], result, "c", files=files)
        rows = {r["id"]: r for r in state["account"]["requests"]}
        self.assertEqual(rows["r15.0"]["answered"], None)  # the conditional answer: the question stays open
        self.assertEqual((rows["r13.0"]["answered"] or {}).get("n"), 9001)  # answered by the dispatch, naming the customer's entry
        self.assertEqual([r["what"] for r in state["account"]["requests"] if r["entries"][0] == 9001],
                         ["Belege zu: Stromkosten für den Bautrockner", "Besteht der Mangel weiterhin?"])  # what it asked, owed by the customer


class FulfilmentTests(unittest.TestCase):
    ASK = {"what": "Belege zu: Stromkosten für den Bautrockner", "of": "kunde", "kind": "claim", "ref": 0}

    def account_with(self, reply):
        """The dispatch's entry and a reply of the customer after it (``reply``: what it answers, its file)."""
        dispatch = {"n": 9001, "date": "2026-09-08", "from": "versicherer", "to": "kunde", "kind": "einschaetzung", "code": "5", "citations": [],
                    "asks": [{**self.ASK, "by": None, "repeats": None, "warns": False, "citations": []}], "answers": [], "terms": [], "paid": [],
                    "next": [], "what": "Rechtliche Einschätzung", "dispatch": {"version": "v1"}}
        answer = {"n": 16, "date": "2026-09-28", "from": "kunde", "to": "versicherer", "kind": "antwort", "file": "fs", "citations": [{"file": "fs"}],
                  "asks": [], "answers": [{"what": reply, "answers": 9001, "citations": [{"file": "fs"}]}], "terms": [], "paid": [],
                  "next": [], "what": "Antwort"}
        acc = account.build([dispatch, answer] if reply is not None else [dispatch], WF)
        return next(e for e in acc["entries"] if e.get("dispatch")), acc

    def test_fulfilment_needs_evidence_in_a_reply_file(self):
        files = [{"id": "fs", "name": "Belege Stromkosten.eml", "extraction": {}},
                 {"id": "ft", "name": episode.BILL, "extraction": {"attached_to": "Belege Stromkosten.eml"}}]
        claim = lambda documented, receipt_file: {"brief": {"claims": [{"what": "Stromkosten für den Bautrockner", "documented": documented,
                                                                       "receipt": [{"file": receipt_file, "quote": "Betrag: CHF 85.40"}]}]}}
        cases = {"refusal": ("Für die Stromkosten habe ich keine Belege.", claim(False, None)),  # closed by words today (C refuses it)
                 "mixed": ("Fotos anbei, Belege zu den Stromkosten folgen", claim(False, None)),
                 "delivery without word overlap": ("Stromabrechnung anbei.", claim(True, "ft")),  # the bill attached to the reply
                 "bare word match": ("Belege zu den Stromkosten für den Bautrockner", claim(False, None)),
                 "receipt elsewhere": ("Belege zu den Stromkosten", claim(True, "fa"))}  # documented, but not by a file of the reply
        out = {}
        for label, (reply, result) in cases.items():
            entry, acc = self.account_with(reply)
            out[label] = completion.fulfilment(entry, acc, files, result)
        self.assertTrue(out["delivery without word overlap"]["fulfilled"])
        for label in ("refusal", "mixed", "bare word match", "receipt elsewhere"):
            self.assertFalse(out[label]["fulfilled"], label)
            self.assertTrue(out[label]["acknowledged"], label)
        self.assertEqual(out["bare word match"]["unbelegt"][0]["what"], self.ASK["what"])  # an answer without evidence
        entry, acc = self.account_with(None)
        self.assertFalse(completion.fulfilment(entry, acc, files, claim(True, "ft"))["fulfilled"])  # no reply: nothing met
        st_args = dict(today=date(2026, 9, 30), result=claim(False, None))
        draft = {"form": "A7", "kind": "A7", "text": "Brief", "version": "v7", "recipients": [], "needs": []}
        entry, acc = self.account_with("Belege zu den Stromkosten für den Bautrockner")
        events = [approved("A5", version="v1"), saved("v1"), sent("v1", day="2026-09-08", edit="d1")]
        st = completion.state({}, [], draft, events, [dispatch_edit()], account=acc, files=files, **st_args)
        self.assertEqual((st["bucket"], st["status"]), ("urteil", "Antwort ohne Beleg – prüfen"))
        entry, acc = self.account_with("Stromabrechnung anbei.")
        st = completion.state({}, [], draft, events, [dispatch_edit()], account=acc, files=files, **{**st_args, "result": claim(True, "ft")})
        self.assertEqual((st["fulfilled"], st["bucket"]), (True, None))  # fulfilled: the next step decides the row


# -- 17 to 19: waiting, the clock and the last contact ---------------------------------------------------------------------

class WaitingTests(unittest.TestCase):
    def view_on(self, plus, edits):
        result, files = phase_b()
        day = EP.a5_day + timedelta(days=plus)
        state, listed = episode.view(result, files, day, episode.decided(("deckung", "bestätigt"), ("aussichten", "genügend")) + edits)
        act = next(i for i in listed if i["kind"] == "next_action")
        clock = follow_up(act.get("next_in_days"), files, [], today=day, since=act.get("since"), until=act.get("until"), step=act.get("action"))
        return state, listed, act, clock, day

    def test_after_dispatch_the_case_waits_until_its_date_and_then_the_next_step_is_prepared(self):
        _, listed, act, clock, day = self.view_on(0, [])
        self.assertEqual(act["action"], "A5")
        state, listed, act, clock, day = self.view_on(10, [dispatch_edit(day=EP.a5_day.isoformat())])
        self.assertEqual((act["action"], act.get("since")), ("A7", EP.a5_day.isoformat()))
        self.assertEqual(clock["due"], (EP.a5_day + timedelta(days=90)).isoformat())  # A5 → 90 days → A7, without the letter in the file
        row = stand_of(listed, clock["due"], today=day)
        self.assertEqual((row["bucket"], row["text"]), ("wartet", f"wartet auf Kundschaft bis {EP.a5_day + timedelta(days=90):%d.%m.%Y}"))
        state, listed, act, clock, day = self.view_on(91, [dispatch_edit(day=EP.a5_day.isoformat())])
        self.assertEqual(act["action"], "A7")
        self.assertTrue(act["reason"].startswith(f"keine Antwort seit unserer Einschätzung vom {EP.a5_day:%d.%m.%Y}"))
        row = stand_of(listed, clock["due"], today=day)
        self.assertEqual((row["bucket"], row["text"]), ("urteil", "überfällig: Statusanfrage mit Abschlussankündigung vorbereitet"))
        text = letters.render("A7", FORMS, letters.context({"title": EP.title}, listed, [], clock, episode.looked_at(phase_b()[1], day),
                                                            facts=state["facts"]))[0]
        self.assertIn(f"seit unserem letzten Kontakt vom {EP.a5_day:%d.%m.%Y}", text)  # «letzter Kontakt» is the dispatch day

    def test_a_dispatch_moves_a_run_prepared_before_the_account(self):
        result = {"facts": [{"fact": "rechtsgebiet", "status": "established", "verdict": "accepted", "value": "Mietrecht / Mangel", "citations": []}],
                  "documents": [], "brief": {"request": "Schimmel", "parties": [], "timeline": []}}
        files = [{"id": "f1", "name": "Meldung.eml", "extraction": {"cut_of": {"as_of": "2026-11-20"}, "segments": []}}]
        before = core.evaluate(WF, [], [], result, "c", files=files)
        self.assertIsNone(before["account"])
        self.assertEqual(account.dispatch_facts([dispatch_edit("A1", day="2026-11-15")], WF), {"handlung_a1": "2026-11-15"})
        after = core.evaluate(WF, [], [dispatch_edit("A1", day="2026-11-15")], result, "c", files=files)
        self.assertEqual(after["facts"]["handlung_a1"], "2026-11-15")
        listed = item_rules.build_items(after, result, files)
        act = next(i for i in listed if i["kind"] == "next_action")
        self.assertNotEqual(act["action"], "A1")  # the first request went out: its follow-up is prepared
        self.assertEqual(act.get("since"), "2026-11-15")
        self.assertEqual(account.dispatch_facts([dispatch_edit("A1", day="2026-11-15", status="undone")], WF), {})
        self.assertEqual(account.dispatch_facts([dispatch_edit("A10_kunde", day="2026-11-15")], WF), {})  # no code, no action fact

    def test_the_last_contact_is_the_latest_either_way(self):
        kontakt = {"kind": "stand", "key": "kontakt", "item_id": "stand:kontakt", "value": "28.09.2026 · Antwort von der Kundschaft"}
        ctx = letters._context_contact({"title": "x"}, [kontakt], [], [], date(2026, 12, 1), facts={"handlung_a5": "2026-09-08"})
        self.assertEqual(ctx["letzter_kontakt"], "28.09.2026")  # the account's last contact: the customer's reply after our letter
        events = [approved("A5", version="v1"), sent("v1", day="2026-09-08")]
        letter_in = [{"extraction": {"segments": [{"date": "15.09.2026", "sender": "Sara Exempel", "recipient": "Protekta Rechtsschutz"}]}}]
        ctx = letters._context_contact({"title": "x"}, [], events, letter_in, date(2026, 12, 1), facts={"handlung_a1": "2026-08-02"})
        self.assertEqual(ctx["letzter_kontakt"], "15.09.2026")  # without an account: the latest of dispatch, actions and documents to us
        ctx = letters._context_contact({"title": "x"}, [], events, [], date(2026, 12, 1), facts={"handlung_a1": "2026-08-02"})
        self.assertEqual((ctx["letzter_kontakt"], ctx["wahren_eingang"]), ("08.09.2026", "Vielen Dank für Ihre Nachricht."))


# -- 21, 22: settlement and closing -----------------------------------------------------------------------------------------

class SettlementTests(unittest.TestCase):
    def test_settlement_steps_complete_only_from_evidence(self):
        from tests.test_package import IBAN, SETTLED, TEXT, build
        hand = {"eingang_erledigt_bis": "2026-11-06", "vergleich_bestaetigt": "ja"}
        step = lambda events=(), facts=(), text=TEXT: build(SETTLED + list(facts), history="A1 2026-09-01; A5 2026-10-01; A8 2026-10-10",
                                                            text=text, events=list(events), set_by_hand=hand)[0]["next_action:0"]
        letter = lambda form, version, day, edit: [approved(form, version=version, at=f"{day}T09:00:00+00:00"), sent(version, day=day, edit=edit)]
        asked = letter("A11_iban", "v-iban", "2026-11-02", "e1")
        nxt = step(asked)
        self.assertEqual((nxt["form"], nxt["reason"], nxt.get("since")), ("A11_iban", "Bankverbindung erfragt am 02.11.2026 bis 16.11.2026", "2026-11-02"))
        with_iban = TEXT + f"\n[page 6]\nMein Konto: IBAN {IBAN}, lautend auf Lea Beispiel\n"
        self.assertEqual(step(asked, text=with_iban)["form"], "A11_auszahlung")  # the IBAN in the file
        announced = asked + letter("A11_auszahlung", "v-pay", "2026-11-03", "e2")
        nxt = step(announced, text=with_iban)
        self.assertEqual((nxt["form"], nxt["reason"]), ("A11_eingang", "Auszahlung angekündigt am 03.11.2026; Eingang bei der Kundschaft erfragen"))
        confirmed = announced + letter("A11_eingang", "v-in", "2026-11-04", "e3")
        nxt = step(confirmed, text=with_iban)  # a receipt asked for, no payment shown: it waits, never closes
        self.assertEqual((nxt["action"], nxt["form"]), ("A11", "A11_eingang"))
        self.assertIn("Zahlungseingang erfragt am 04.11.2026", nxt["reason"])
        # the payment shown (and its arrival dealt with: «bereits erledigt» on 06.11.): confirmed to the customer, then closing
        paid = [("eingang_zahlung", "Immo Verwaltung AG: Zahlung CHF 800.00 am 2026-11-05", 7, "CHF 800.00 überwiesen")]
        nxt = step(announced, paid, text=with_iban)
        self.assertEqual((nxt["form"], nxt["reason"]), ("A11_eingang", "Auszahlung angekündigt am 03.11.2026; Zahlung laut Akte eingegangen"))
        nxt = step(confirmed, paid, text=with_iban)
        self.assertEqual((nxt["action"], nxt["form"], nxt["reason"]), ("A12", "A12_erledigt", "Zahlungseingang bestätigt"))
        undone = confirmed + [{"kind": "correction.undone", "edit_id": "e3", "at": "2026-11-05T09:00:00+00:00"}]
        self.assertEqual(step(undone, paid, text=with_iban)["form"], "A11_eingang")  # the confirmation undone: not confirmed


class ClosingTests(unittest.TestCase):
    def test_erledigt_only_on_closing_steps_and_a_reopen_undoes_closed(self):
        closing = [{"kind": "next_action", "key": "0", "item_id": "next_action:0", "action": "A12", "label": {"de": "Dossier schliessen"}}]
        closed = [{"kind": "case.closed", "at": "2026-11-15T10:00:00", "form": "erledigt"}]
        self.assertEqual(stand_of(closing, None, closed, closed=True)["bucket"], "erledigt")
        reopened = closed + [{"kind": "case.reopened", "at": "2026-11-16T10:00:00", "file": "f9"}]
        row = stand_of(closing, None, reopened, closed=True, today=date(2026, 11, 16))
        self.assertNotEqual(row["bucket"], "erledigt")
        self.assertFalse(listing.is_closed(reopened))
        self.assertTrue(listing.is_closed(reopened + [{"kind": "case.closed", "at": "2026-11-17T10:00:00"}]))
        a5 = [{"kind": "next_action", "key": "0", "item_id": "next_action:0", "action": "A5", "label": {"de": "Rechtliche Einschätzung"}}]
        self.assertEqual(stand_of(a5, "2026-12-20", [sent("v1")], today=date(2026, 11, 15))["bucket"], "urteil")  # a letter sent closes nothing


# -- 23, 24, 25: the queue, the follow-up, «Frist wahren» ---------------------------------------------------------------

class QueueTests(unittest.TestCase):
    TODAY = date(2026, 11, 15)

    def test_the_queue_buckets_and_legacy_copies(self):
        prepared = [{"kind": "next_action", "key": "0", "item_id": "next_action:0", "action": "A5", "label": {"de": "Rechtliche Einschätzung"}}]
        follow = [{"kind": "next_action", "key": "0", "item_id": "next_action:0", "action": "A7", "since": "2026-09-08", "follow_up": "A7",
                   "label": {"de": "Statusanfrage mit Abschlussankündigung"}}]
        ready = {"bucket": "versandbereit", "status": "freigegeben, Versand offen", "date": "2026-11-14"}
        rows = {
            "prepared": stand_of(prepared, "2026-12-20", today=self.TODAY),
            "decision": stand_of(prepared, "2026-12-20", completion_={"decision": "Deckung"}, today=self.TODAY),
            "stale": stand_of(prepared, "2026-12-20", completion_={"bucket": "urteil", "status": "Freigabe veraltet: Entscheid geändert"}, today=self.TODAY),
            "ready": stand_of(prepared, "2026-12-20", completion_=ready, today=self.TODAY),
            "legacy": stand_of(prepared, "2026-12-20", completion_={"bucket": "versandbereit", "status": "kopiert, Versand nicht bestätigt"}, today=self.TODAY),
            "waiting": stand_of(follow, "2026-12-07", today=self.TODAY),
            "overdue": stand_of(follow, "2026-11-10", today=self.TODAY),
            "failed update": stand_of([], None, run_status="failed", run_kind="update"),
            "interrupted update": stand_of([], None, run_status="interrupted", run_kind="update"),
            "failed preparation": stand_of([], None, run_status="failed"),
            "package missing": stand_of(prepared, "2026-12-20", completion_={"bucket": "fehlgeschlagen", "status": "Versandpaket fehlt"}, today=self.TODAY),
            "closed": stand_of([{**prepared[0], "action": "A12"}], None, [{"kind": "case.closed"}], closed=True, today=self.TODAY),
            "arrived": stand_of(prepared, "2026-12-20", new_files=2, completion_=ready, today=self.TODAY),
        }
        said = {k: (v["bucket"], v["text"]) for k, v in rows.items()}
        self.assertEqual(said, {
            "prepared": ("urteil", "vorbereitet"), "decision": ("urteil", "Entscheid: Deckung"),
            "stale": ("urteil", "Freigabe veraltet: Entscheid geändert"), "ready": ("versandbereit", "freigegeben, Versand offen"),
            "legacy": ("versandbereit", "kopiert, Versand nicht bestätigt"), "waiting": ("wartet", "wartet auf Kundschaft bis 07.12.2026"),
            "overdue": ("urteil", "überfällig: Statusanfrage mit Abschlussankündigung vorbereitet"),
            "failed update": ("fehlgeschlagen", "Aktualisierung fehlgeschlagen"), "interrupted update": ("fehlgeschlagen", "Aktualisierung unterbrochen"),
            "failed preparation": ("fehlgeschlagen", "Vorbereitung fehlgeschlagen"), "package missing": ("fehlgeschlagen", "Versandpaket fehlt"),
            "closed": ("erledigt", "erledigt"), "arrived": ("urteil", "neue Unterlagen")})
        self.assertEqual(rows["ready"]["date"], "2026-11-14")  # the oldest approval first
        self.assertLess(rows["stale"]["rank"], rows["prepared"]["rank"])
        self.assertEqual(rows["waiting"]["date"], "2026-12-07")
        # a stale approval is never «Versandbereit»
        rows_ = [{k: r[k] for k in ("to", "recipient")} for r in approved("A5")["recipients"]]
        draft = {"form": "A5", "kind": "A5", "text": "Brief", "version": "v2", "recipients": rows_, "needs": []}
        st = completion.state({}, [], draft, [approved("A5", version="v1"), saved("v1")], [], today=self.TODAY, facts={"aussichten": "genügend"})
        self.assertEqual((st["bucket"], st["status"]), ("urteil", "Freigabe veraltet: Text geändert"))
        st = completion.state({}, [], draft, [approved("A5", version="v2", text="Brief"), saved("v2")], [], today=self.TODAY, facts={"aussichten": "genügend"})
        self.assertEqual((st["bucket"], st["status"], st["date"]), ("versandbereit", "freigegeben, Versand offen", "2026-11-15"))
        st = completion.state({}, [], draft, [approved("A5", version="v2", text="Brief")], [], today=self.TODAY, facts={"aussichten": "genügend"})
        self.assertEqual((st["bucket"], st["status"]), ("fehlgeschlagen", "Versandpaket fehlt"))

    def test_a_hand_set_follow_up_lapses_with_its_step(self):
        files = [{"extraction": {"cut_of": {"as_of": "2026-11-15"}, "segments": []}}]
        hand = [{"kind": "followup.set", "date": "2026-12-01", "step": "A5", "at": "2026-11-15T08:00:00+00:00", "expert": USER}]
        self.assertEqual(follow_up(28, files, hand, step="A5")["due"], "2026-12-01")
        self.assertEqual(follow_up(28, files, hand, step="A7")["due"], "2026-12-13")  # another step: the clock's date
        later = hand + [approved("A5", version="v1", at="2026-11-15T09:00:00+00:00"), sent("v1", at="2026-11-15T10:00:00+00:00")]
        self.assertEqual(follow_up(28, files, later, step="A5")["due"], "2026-12-13")  # set before the dispatch: lapsed
        again = later + [{**hand[0], "date": "2026-12-03", "at": "2026-11-15T11:00:00+00:00"}]
        self.assertEqual(follow_up(28, files, again, step="A5")["due"], "2026-12-03")
        legacy = [{"kind": "followup.set", "date": "2026-12-02", "at": "2026-11-15T08:00:00+00:00"}]  # set by a browser before this release
        self.assertEqual(follow_up(28, files, legacy, step="A1")["due"], "2026-12-02")
        frist = [approved("A7", version="v7", at="2026-11-15T09:00:00+00:00", respond_by="2026-11-22"), sent("v7", day="2026-11-15")]
        self.assertEqual(follow_up(14, files, frist, since="2026-11-15", step="A12")["due"], "2026-11-22")  # the date the letter set

    def test_after_a13_is_dispatched_the_deadline_leads_until_kept_or_passed(self):
        from tests.test_redesign import TRAFFIC, view
        deadline = "deadline:einsprache_strafbefehl"
        approval = approved("A13", version="v13", also=("vorlage:einsprache",), deadline=deadline, at="2026-11-15T08:00:00+00:00")
        state, items, listed, files = view("verkehr", TRAFFIC, "2026-11-15", events=[approval, saved("v13")])
        self.assertEqual(listed["next_action:0"]["action"], "A13")  # approved, not sent: still to be done
        alone = approved("A13", version="v12", deadline=deadline, at="2026-11-15T08:00:00+00:00")
        state, items, listed, files = view("verkehr", TRAFFIC, "2026-11-15", events=[alone, saved("v12"), sent("v12")])
        self.assertEqual(listed["next_action:0"]["action"], "A13")  # the template did not travel with it
        state, items, listed, files = view("verkehr", TRAFFIC, "2026-11-15", events=[approval, saved("v13"), sent("v13")])
        self.assertEqual(listed["next_action:0"]["action"], "A1")  # dispatched: the stage's own action
        lead = screen.lead(items, date(2026, 11, 15), area.workflow("verkehr")["urgent"])
        self.assertEqual(lead["item_id"], deadline)  # the deadline still leads the card
        row = stand_of(items, None, [approval, sent("v13")], today=date(2026, 11, 15), files=files)
        self.assertIn(row["text"], ("dringend", "Frist läuft"))
        state, items, listed, files = view("verkehr", TRAFFIC, "2026-11-18", events=[approval, saved("v13"), sent("v13")])
        self.assertNotIn(stand_of(items, None, [approval, sent("v13")], today=date(2026, 11, 18), files=files)["text"], ("dringend", "Frist läuft"))


# -- 26 to 30: the mandate package, study copies, the note, the head, the bar ------------------------------------------------

class PackageTests(unittest.TestCase):
    def test_the_mandate_package_is_dispatched_per_recipient(self):
        from tests.test_package import MANDATE, TIMELINE, build
        listed, items, files = build(MANDATE, history="A1 2026-09-01; A5 2026-10-01", timeline=TIMELINE)
        state = {"case": {"id": "c", "title": "x"}, "evaluation": None, "process": None, "facts": {}}
        draft = {"form": "A10", "kind": "A10", "title": FORMS["A10"]["title"], "text": "Mandatsanfrage", "base_parts": [("p0", "Mandatsanfrage")],
                 "also": [{"kind": k, "title": FORMS[k]["title"], "text": FORMS[k]["title"], "base_parts": [("p0", FORMS[k]["title"])]}
                          for k in letters.accompanying("A10", FORMS, items)]}
        completion.prepare(draft, {}, items)
        self.assertEqual([(r["to"], r["forms"]) for r in draft["recipients"]],
                         [("kanzlei", ["A10", "A10_kostengutsprache", "A10_zusammenfassung"]), ("kunde", ["A10_kunde"])])
        self.assertTrue(state)
        approval = {**approved("A10", version=draft["version"], to=("kanzlei", "kunde"), title=FORMS["A10"]["title"]),
                    "recipients": [{k: r[k] for k in ("to", "recipient", "title", "forms", "titles")} for r in draft["recipients"]]}
        firm = completion.dispatch_args(approval, "kanzlei", "2026-11-15", "email", items, [])
        customer = completion.dispatch_args(approval, "kunde", "2026-11-15", "post", items, [])
        self.assertEqual((firm["form"], firm["kind"], firm["code"]), ("A10", "mandat", "10"))
        self.assertEqual((customer["form"], customer["kind"], customer["code"], customer["title"]),
                         ("A10_kunde", "andere", None, FORMS["A10_kunde"]["title"]))
        events = [approval, saved(draft["version"]), sent(draft["version"], recipient="kanzlei", edit="e1")]
        st = completion.state({}, items, draft, events, [], today=date(2026, 11, 15), facts={"deckung": "bestätigt", "vorgehen": "Mandat an Anwaltskanzlei"})
        self.assertEqual((st["state"], [r["to"] for r in st["pending"]]), ("freigegeben", ["kunde"]))  # the customer's «Versandt am» stays
        self.assertEqual({r["to"]: bool(r["dispatched"]) for r in st["bar"]["recipients"]}, {"kanzlei": True, "kunde": False})
        tabs = completion.tab_states(st, events)
        self.assertEqual((tabs["A10"]["label"], tabs["A10_kunde"]["label"]), ("versandt am 15.11.2026", "freigegeben"))
        note = letters.file_note({"title": "x"}, items, events, None, files, package=[(k, FORMS[k]["title"]) for k in ["A10", *letters.accompanying("A10", FORMS, items)]])
        self.assertIn("Mandatsanfrage an die Kanzlei – versandt am 15.11.2026", note)
        self.assertIn("Information der Kundschaft zum Mandat – freigegeben", note)
        self.assertIn("Versandt: Mandatsanfrage an die Kanzlei an die Kanzlei am 15.11.2026 (E-Mail, N. Kumar)", note)


class StudyTests(Service):
    def test_study_copies_refuse_drafts_approval_and_dispatch(self):
        before = (len(self.store.list_case_events(self.study)), self.store.latest_drafts(self.study))
        view = self.client.get(f"/api/cases/{self.study}").json()
        self.assertEqual(view["completion"]["bar"]["kind"], "study")  # copied and measured as frozen, never approved or sent
        draft = view["draft"]
        attempts = {"draft": self.client.put(f"/api/cases/{self.study}/drafts/{draft['form']}",
                                             json={"parts": [{"part": "p0", "base_sha256": "0" * 64, "text": "x"}], "op_id": "op-study-1"}),
                    "approve": self.client.post(f"/api/cases/{self.study}/actions/approve", json={"form": draft["form"], "version": draft["version"],
                                                                                                 "op_id": "op-study-2"}),
                    "dispatch": self.client.post(f"/api/cases/{self.study}/actions/dispatch", json={"version": draft["version"], "date": "2026-11-15",
                                                                                                   "channel": "post", "op_id": "op-study-3"})}
        self.assertEqual({k: r.status_code for k, r in attempts.items()}, {"draft": 409, "approve": 409, "dispatch": 409})
        self.assertEqual(attempts["approve"].json()["detail"], "Eine Studienkopie wird nicht freigegeben.")
        self.assertEqual((len(self.store.list_case_events(self.study)), self.store.latest_drafts(self.study)), before)  # nothing recorded


class NoteTests(unittest.TestCase):
    def test_the_file_note_says_versandt_only_after_dispatch_and_names_the_adoption(self):
        adoption = {"kind": "item.corrected", "item_id": "point:empfehlung", "event_id": "ev-x", "chosen": ["frist_beseitigung", "schadenersatz"],
                    "titles": ["Frist zur Beseitigung setzen", "Kosten belegen und Ersatz verlangen"], "at": "2026-11-15T08:00:00+00:00"}
        items = [{"kind": "fact", "key": "aussichten", "item_id": "fact:aussichten", "value": "genügend", "verdict": "set_by_handler",
                  "label": {"de": "Hat das Vorgehen genügend Aussicht auf Erfolg?"}},
                 {"kind": "fact", "key": "deckung", "item_id": "fact:deckung", "value": "bestätigt", "verdict": "set_by_handler", "label": {"de": "Deckung"}}]
        approval = approved("A5", version="v1", title="Rechtliche Einschätzung", at="2026-11-15T09:00:00+00:00")
        files = [{"name": "AW Rueckfrage.eml", "created_at": "2026-11-14T08:00:00+00:00"}]
        note = letters.file_note({"title": "x"}, items, [adoption, approval], None, files)
        self.assertIn("Entschieden: Deckung: bestätigt (durch die Fallbearbeitung); Empfehlung übernommen: Frist zur Beseitigung setzen · "
                      "Kosten belegen und Ersatz verlangen; Aussichten genügend.", note)
        self.assertIn(f"Zum Versand freigegeben am 15.11.2026 ({USER}): Rechtliche Einschätzung.", note)
        self.assertNotIn("Versandt", note)
        events = [adoption, approval, saved("v1", at="2026-11-15T09:00:01+00:00"), sent("v1", asks=["Belege zu: Stromkosten für den Bautrockner"])]
        note = letters.file_note({"title": "x"}, items, events, {"due": "2027-02-13"}, files + [{"name": "Neu.eml", "created_at": "2026-11-16T08:00:00+00:00"}])
        self.assertIn(f"Versandt: Rechtliche Einschätzung an die Kundschaft am 15.11.2026 (E-Mail, {USER}).", note)
        self.assertIn("Erwartet: Belege zu: Stromkosten für den Bautrockner; Wiedervorlage 13.02.2027.", note)
        self.assertNotIn("Zum Versand freigegeben", note)
        self.assertTrue(note.startswith("Eingegangen: Neu.eml."))  # since the last Versandpaket
        undone = events + [{"kind": "correction.undone", "edit_id": "ed1", "at": "2026-11-15T11:00:00+00:00"}]
        self.assertNotIn("Versandt:", letters.file_note({"title": "x"}, items, undone, None, files))


class HeadTests(unittest.TestCase):
    def test_the_head_block_is_one_changed_line_then_one_meaning_line(self):
        changes = {"ledger": ["2 Nachrichten der Kundschaft vom 05.09.2026", "Rückfrage vom 17.08.2026 beantwortet", "3 Fragen",
                              "Stromkosten geltend gemacht", "zugesagt bis 30.09.2026: Belege"],
                   "entries": ["05.09.2026 · Kundschaft → Protekta · Antwort: Antwort auf die Rückfrage"], "added": [], "changed": ["Deckung"], "removed": []}
        assessment = {"summary": {"answered": 1, "conditional": 2, "open": 0, "proposal": ["Frist zur Beseitigung setzen"], "residual": 1}}
        fresh = {"fresh": True, "state": "entwurf", "decision": "Deckung", "bar": {"gaps": 0}}
        head = screen.head_block(changes, assessment, fresh, {"kind": "A5", "title": "Rechtliche Einschätzung"})
        self.assertEqual(head["changed"], "2 Nachrichten der Kundschaft vom 05.09.2026 · Rückfrage vom 17.08.2026 beantwortet")
        self.assertLessEqual(len(head["changed"]), 90)
        self.assertEqual(head["changed_all"][:5], changes["ledger"])  # the ledger first, every line on click
        self.assertEqual(head["meaning"], "Einschätzung vorbereitet (1 Frage beantwortet, 2 bedingt); kann nach dem Deckungsentscheid freigegeben werden.")
        self.assertIsNone(head["stale"])
        self.assertIsNone(screen.head_block(changes, assessment, {**fresh, "fresh": False}, {}))  # nothing new since the last approval
        stale = screen.head_block(None, None, {"fresh": False, "state": "freigegeben", "stale": ["Entscheid geändert"]}, {"title": "Brief"})
        self.assertEqual((stale["stale"], stale["changed"]), ("Freigabe veraltet: Entscheid geändert", None))
        long = screen.head_block({"ledger": ["x" * 120]}, None, {"fresh": True, "state": "entwurf", "bar": {}}, {"title": "Brief"})
        self.assertEqual(len(long["changed"]), 90)


class BarTests(unittest.TestCase):
    def test_the_bar_after_approval_leads_with_copy_and_presets_today_and_the_channel(self):
        draft = {"form": "A5", "kind": "A5", "text": "Brief", "version": "v1", "needs": [],
                 "recipients": [{"to": "kunde", "recipient": "Sehr geehrte Frau Exempel · Frau Sara Exempel", "title": "Kundschaft", "forms": ["A5"]}]}
        files = [{"name": "Akte.txt", "kind": "text", "created_at": "2026-11-01T08:00:00"}, {"name": "AW Rueckfrage.eml", "kind": "email",
                                                                                               "created_at": "2026-11-14T08:00:00"}]
        events = [approved("A5", version="v1", text="Brief"), saved("v1")]
        st = completion.state({}, [], draft, events, [], today=date(2026, 11, 15), files=files, facts={"aussichten": "genügend"})
        bar = st["bar"]
        self.assertEqual((bar["kind"], bar["label"], bar["earliest"]), ("dispatch", "Brief kopieren", "2026-11-15"))
        self.assertEqual([(r["to"], r["date"], r["channel"], r["dispatched"]) for r in bar["recipients"]], [("kunde", "2026-11-15", "email", None)])
        self.assertEqual(completion.default_channel(files[:1]), "post")  # the customer's last message by post: «Post»
        before = completion.state({}, [], draft, [], [], today=date(2026, 11, 15), files=files, facts={"aussichten": "genügend"})
        self.assertEqual((before["bar"]["kind"], before["bar"]["label"]), ("approve", "Freigeben"))
        after = completion.state({}, [], draft, events + [sent("v1")], [], today=date(2026, 11, 15), files=files, facts={"aussichten": "genügend"})
        self.assertEqual((after["state"], after["bar"]["kind"], after["bar"]["line"]), ("versandt", "dispatched", "versandt am 15.11.2026"))


if __name__ == "__main__":
    unittest.main()
