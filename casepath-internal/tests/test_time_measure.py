"""The person's own active time on a case and the share of a letter that is their wording: recorded only where the
deployment allows the person's own switch, and counted so that a night between two openings is never work."""
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from casepath.config import SettingsError, load_settings
from casepath.process import completion
from casepath.quality.auswertung import _handling, _letter_change, _median, _span, operations
from casepath.web.app import create_app


def at(minute, second=0, day=16):
    return f"2026-11-{day:02d}T09:{minute:02d}:{second:02d}+00:00"


def ev(kind, minute, second=0, day=16, **more):
    return {"kind": kind, "at": at(minute, second, day), **more}


class HandlingTests(unittest.TestCase):
    def test_active_time_is_the_sum_of_the_spans_the_person_was_at_work(self):
        events = [ev("case.opened", 0), ev("item.exposed", 1), ev("idle.started", 3), ev("idle.ended", 10), ev("action.approved", 12),
                  ev("idle.started", 12, 30)]
        self.assertEqual(_handling(events), 3 * 60 + 2 * 60 + 30)

    def test_a_span_never_ended_stops_at_its_last_event_so_a_night_is_not_counted(self):
        events = [ev("case.opened", 0), ev("item.corrected", 4), ev("case.opened", 5, day=17), ev("letter.copied", 6, day=17)]
        self.assertEqual(_handling(events), 4 * 60 + 60)  # the browser was closed after the correction; the next morning: one minute

    def test_nothing_measured_is_no_time(self):
        self.assertIsNone(_handling([ev("item.corrected", 1), ev("action.approved", 2)]))
        self.assertIsNone(_handling([]))

    def test_the_letter_change_counts_words_not_length(self):
        base = "Wir empfehlen Ihnen, der Vermieterschaft eine Frist von 30 Tagen zu setzen."
        same_length = "Wir empfehlen Ihnen, der Verwaltung sofort eine Mahnung per Post zu senden."
        draft = lambda text: {"parts": [{"part": "p1", "base": "Sehr geehrte Frau Exempel", "text": "Sehr geehrte Frau Exempel"}, {"part": "p2", "base": base, "text": text}]}
        self.assertEqual(completion.changed_words(draft(base)), {"total": 16, "changed": 0})
        words = completion.changed_words(draft(same_length))
        self.assertEqual(words["total"], 16)
        self.assertGreaterEqual(words["changed"], 6)  # a sentence replaced by one of the same length is a change
        self.assertEqual(_letter_change([{"kind": "action.approved", "words": {"total": 200, "changed": 14}}]), 0.07)
        self.assertEqual(_letter_change([{"kind": "letter.copied", "change_ratio": 0.2}]), 0.2)  # a frozen copy: its own measure
        self.assertIsNone(_letter_change([]))


class SwitchTests(unittest.TestCase):
    def app(self, **env):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        (root / "catalogue").mkdir()
        app = create_app(load_settings({"CASEPATH_DATA_DIR": str(root / "data"), "CASEPATH_WORKFLOW_CATALOGUE": str(root / "catalogue"),
                                        "CASEPATH_DEV_USER": "A. Handler", **env}), model_factory=lambda: None)
        self.addCleanup(app.state.store.close)
        self.addCleanup(app.state.runs.shutdown)
        return TestClient(app), app.state.store

    def test_nothing_is_recorded_where_the_deployment_does_not_allow_the_switch(self):
        client, store = self.app()
        cid = client.post("/api/cases", json={"title": "Schimmel", "intake": {}}).json()["id"]
        self.assertNotIn("time_measure", client.get("/api/me").json())
        r = client.post(f"/api/cases/{cid}/events", json={"kind": "case.opened", "item_id": None, "fields": {}})
        self.assertEqual((r.status_code, r.json()["detail"]), (409, "Die Zeitmessung ist für diese Installation nicht eingeschaltet."))
        self.assertEqual(store.list_case_events(cid), [])

    def test_with_the_switch_allowed_the_persons_events_are_taken(self):
        client, store = self.app(CASEPATH_TIME_MEASURE="session")
        cid = client.post("/api/cases", json={"title": "Schimmel", "intake": {}}).json()["id"]
        self.assertTrue(client.get("/api/me").json()["time_measure"])
        for kind in ("case.opened", "idle.started", "idle.ended"):
            self.assertEqual(client.post(f"/api/cases/{cid}/events", json={"kind": kind, "item_id": None, "fields": {}}).status_code, 201)
        self.assertEqual([e["kind"] for e in store.list_case_events(cid)], ["case.opened", "idle.started", "idle.ended"])
        with self.assertRaises(SettingsError):
            load_settings({"CASEPATH_TIME_MEASURE": "immer"})


class OperationsTests(unittest.TestCase):
    """The operation's measures rest on recorded moments only; an impossible order counts for nothing."""

    class Store:
        def __init__(self, cases, events, edits, prepared):
            self.cases, self.events, self.edits, self.prepared = cases, events, edits, prepared

        def list_cases(self):
            return self.cases

        def list_case_events(self, case_id):
            return self.events.get(case_id, [])

        def list_edits(self, case_id):
            return self.edits.get(case_id, [])

        def first_prepared(self, case_id):
            return self.prepared.get(case_id)

    def test_medians_ages_and_shares(self):
        at = lambda day, hour=8: f"2026-11-{day:02d}T{hour:02d}:00:00+00:00"  # noqa: E731
        cases = [{"id": "a", "created_at": at(1)}, {"id": "b", "created_at": at(10)}, {"id": "c", "created_at": "2026-07-01T08:00:00+00:00"},
                 {"id": "s", "created_at": at(1), "intake": {"study": True}}]
        events = {"a": [{"kind": "action.approved", "at": at(2), "words": {"total": 120, "changed": 0}}, {"kind": "action.dispatched", "at": at(3)},
                        {"kind": "case.closed", "at": at(5)}, {"kind": "case.reopened", "at": at(6)}, {"kind": "case.closed", "at": at(9)}],
                  "b": [{"kind": "action.approved", "at": at(11), "words": {"total": 80, "changed": 12}}, {"kind": "action.dispatched", "at": at(11)}],
                  "c": [{"kind": "action.dispatched", "at": "2026-06-01T08:00:00+00:00"}]}  # sent before it existed: a seeded history
        edits = {"a": [{"op": "set_fact", "args": {"fact": "deckung", "value": "bestätigt"}, "at": at(2)}],
                 "b": [{"op": "set_fact", "args": {"fact": "deckung", "value": "abgelehnt"}, "at": at(12)}]}
        prepared = {"a": at(1, 9), "b": at(10, 8).replace("08:00:00", "08:04:00")}
        o = operations(self.Store(cases, events, edits, prepared), now=at(17))
        self.assertEqual((o["cases"], o["open"]), (3, 2))                                     # the study copy is left out
        self.assertEqual(o["first_preparation_seconds"], {"median": 1920.0, "cases": 2})      # 60 min and 4 min
        self.assertEqual(o["first_letter_days"], {"median": 1.5, "cases": 2})                 # 2 days and 1 day; the impossible one counts for nothing
        self.assertEqual(o["cover_decision_days"], {"median": 1.5, "cases": 2})
        self.assertEqual(o["cycle_days"], {"median": 8.0, "cases": 1})                        # to the closing that stands
        self.assertEqual((o["opened_30_days"], o["closed_30_days"], o["closed_ever"], o["reopened"]), (2, 1, 1, 1))
        self.assertEqual(o["aging"], {"days_0_7": 1, "days_8_30": 0, "days_31_90": 0, "days_over_90": 1})
        self.assertEqual((o["letters_approved"], o["letters_approved_as_written"], o["cover_decided"], o["cover_refused"]), (2, 1, 2, 1))
        self.assertEqual((_median([]), _median([3, 1, 2]), _span(at(2), at(1)), _span(None, at(1)), _span(at(1), at(1))), (None, 2, None, None, None))


if __name__ == "__main__":
    unittest.main()
