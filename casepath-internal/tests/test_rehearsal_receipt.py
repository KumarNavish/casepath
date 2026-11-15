"""Receipts of the episode's measurements hold ids, counts and enums only (quality/scorecard.py, SAFE and guard), and no date;
and the one diagnostic run on the pilot (deploy/databricks/rehearse.py) does nothing without its confirm phrase.

``casepath.rehearsal/1`` is what deploy/preview/rehearse_episode.mjs writes for one developer rehearsal of the D11 episode on
a synthetic analog (MEASURE §1): label, build, episode, condition, session; per step its time, clicks, decisions and
confirmations (counted apart, by the rule declared before scoring), text edits, characters typed, context switches,
documents opened whole and passages opened from a source chip, page and inner scrolls; the declared external steps
with their time; the word-level edit ratio between the prepared and the approved text with the substantive and stylistic
changes and the ratio by letter slot; the case's events by kind.

A rehearsal's receipts are checked by this test too: CASEPATH_REHEARSAL_RECEIPTS names a folder whose *.json files must
each be a valid receipt (skipped when unset).

``casepath.diagnose/1`` is what the diagnostic run writes (MEASURE §3). Its script is run here against a stand-in for the
app's API that answers as the episode's interfaces are designed (DESIGN §6, SLICE_A A8, SLICE_C C7), on synthetic data:
no request leaves, no model is called."""
import copy
import io
import json
import os
from pathlib import Path
import re
import runpy
import tempfile
import unittest
from unittest import mock

from casepath.quality.scorecard import ScorecardLeak, guard

CELL = Path(__file__).resolve().parents[1] / "deploy" / "databricks" / "rehearse.py"

FORMAT = "casepath.rehearsal/1"
LABEL = "developer_rehearsal.synthetic_analog.handler_savings_unverified"
SCRIPTED = "scripted_path.synthetic_analog.no_handler_time"  # the script took the steps: the path's counts, never a handler's time
CONDITIONS = {"b0", "b1", "n"}
STEP = {"n", "name", "ms", "clicks", "decisions", "confirmations", "edits", "chars", "switches", "opened_whole", "passages", "scrolls"}
SLOTS = {"im_fall", "zu_fragen", "empfehlung", "nachzureichen", "other"}
DATE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{2,4}")


def check_rehearsal(receipt):
    """The receipt if it is a valid casepath.rehearsal/1 receipt; ValueError (or ScorecardLeak) naming what is not."""
    if not isinstance(receipt, dict) or receipt.get("format") != FORMAT:
        raise ValueError(f"format: {FORMAT}")
    body = {k: v for k, v in receipt.items() if k != "format"}  # the format names itself with a slash
    keys = {"label", "build", "episode", "condition", "session", "steps", "external", "edit", "events", "duplicate_refused", "wall_ms",
            "model_tokens"}
    if set(body) != keys:
        raise ValueError(f"fields: {sorted(keys)}, not {sorted(body)}")
    guard(body)
    if DATE.search(json.dumps(body)):
        raise ScorecardLeak("a date is case content: a receipt holds none")
    if body["label"] not in (LABEL, SCRIPTED) or body["condition"] not in CONDITIONS or body["episode"] not in {"e1", "e2"} or body["session"] not in {1, 2}:
        raise ValueError("label, condition (b0, b1, n), episode (e1, e2) and session (1, 2) as declared")
    unmeasured = {"clicks", "edits", "chars", "opened_whole", "passages"} if body["condition"] == "b0" else set()  # no browser in B0
    for i, step in enumerate(body["steps"]):
        if set(step) != STEP or step["n"] != i + 1 or set(step["scrolls"]) != {"page", "inner"}:
            raise ValueError(f"steps[{i}]: {sorted(STEP)}, numbered from 1, scrolls {{page, inner}}")
        counts = [(k, step[k]) for k in STEP - {"name", "scrolls"}] + [(f"scrolls.{k}", v) for k, v in step["scrolls"].items()]
        if any(not (v is None and k.split(".")[0] in unmeasured | {"scrolls"} and body["condition"] == "b0") and (type(v) is not int or v < 0)
               for k, v in counts):
            raise ValueError(f"steps[{i}]: counts and milliseconds are whole numbers from 0 (in B0, what no browser measures is null)")
    if any(set(x) != {"name", "ms"} for x in body["external"]):
        raise ValueError("external: [{name, ms}]")
    edit = body["edit"]
    if set(edit) != {"ratio_words", "substantive", "stylistic", "slots"} or set(edit["slots"]) - SLOTS or (
            body["condition"] != "b0" and None in (edit["ratio_words"], edit["substantive"], edit["stylistic"])):
        raise ValueError(f"edit: ratio_words, substantive, stylistic and slots by {sorted(SLOTS)}")
    if body["duplicate_refused"] not in (True, False, None):
        raise ValueError("duplicate_refused: whether the second drop of the reply was refused (None in the baseline)")
    if body["model_tokens"] != 0:
        raise ValueError("model_tokens: a rehearsal runs scripted, 0 tokens")
    return receipt


def example():
    """A receipt as rehearse_episode.mjs writes it for condition N on E2 in session 1 (synthetic numbers)."""
    step = lambda n, name, ms, clicks=0, decisions=0, confirmations=0, **more: {
        "n": n, "name": name, "ms": ms, "clicks": clicks, "decisions": decisions, "confirmations": confirmations, "edits": 0, "chars": 0,
        "switches": 0, "opened_whole": 0, "passages": 0, "scrolls": {"page": 0, "inner": 0}, **more}
    return {"format": FORMAT, "label": LABEL, "build": "3f2a9c1b7d4e", "episode": "e2", "condition": "n", "session": 1,
            "steps": [step(1, "open_from_queue", 2100, 1), step(2, "drop_reply", 1800, 1), step(3, "drop_duplicate", 900, 1),
                      step(4, "wait_update", 6400), step(5, "read_head", 9200, passages=1),
                      step(6, "deckung", 2300, 1, 1), step(7, "empfehlung", 4100, 1, 1), step(8, "edits", 15800, 2, edits=3, chars=41),
                      step(9, "freigeben", 1200, 1, 1), step(10, "brief_kopieren", 700, 1, 0, 1),
                      step(11, "versandt_am", 1100, 1, 0, 1, switches=1)],
            "external": [{"name": "paste_email", "ms": 9000}, {"name": "attach_template", "ms": 12000}, {"name": "send", "ms": 3000},
                         {"name": "paste_note", "ms": 8000}, {"name": "set_diary", "ms": 15000}],
            "edit": {"ratio_words": 0.04, "substantive": 0, "stylistic": 2, "slots": {"im_fall": 0.0, "zu_fragen": 0.06, "empfehlung": 0.0,
                                                                                      "nachzureichen": 0.0, "other": 0.02}},
            "events": {"action.approved": 1, "bundle.saved": 1, "letter.copied": 1, "action.dispatched": 1, "update.started": 1},
            "duplicate_refused": True, "wall_ms": 112000, "model_tokens": 0}


class RehearsalReceiptTests(unittest.TestCase):
    def test_a_receipt_of_ids_counts_and_enums_passes(self):
        receipt = check_rehearsal(example())
        self.assertEqual(sum(s["decisions"] for s in receipt["steps"]), 3)  # Deckung, Empfehlung, Freigeben
        self.assertEqual(sum(s["confirmations"] for s in receipt["steps"]), 2)  # Brief kopieren, Versandt am: counted apart

    def test_case_content_free_text_and_dates_are_refused(self):
        for change in ({"label": "Entwickler-Probe, synthetisch"}, {"build": "D11 Steiner"}, {"events": {"Brief kopieren": 1}},
                       {"steps": [{**example()["steps"][0], "name": "Muss ich weiterhin die volle Miete bezahlen?"}]},
                       {"external": [{"name": "send", "ms": 9000, "to": "kundin@example.ch"}]},
                       {"steps": [{**example()["steps"][0], "name": "open_2026-11-15"}]}):
            with self.assertRaises((ValueError, ScorecardLeak), msg=str(change)):
                check_rehearsal({**example(), **change})

    def test_the_baseline_leaves_unmeasured_what_no_browser_measures(self):
        b0 = example()
        b0.update(condition="b0", build="none", duplicate_refused=None, events={},
                  edit={"ratio_words": None, "substantive": None, "stylistic": None, "slots": {}},
                  steps=[{**s, "clicks": None, "edits": None, "chars": None, "opened_whole": None, "passages": None,
                          "scrolls": {"page": None, "inner": None}} for s in example()["steps"]])
        check_rehearsal(b0)
        with self.assertRaises(ValueError):  # with CasePath every count is measured
            check_rehearsal({**b0, "condition": "n"})
        with self.assertRaises(ValueError):  # time is measured in the baseline too
            check_rehearsal({**b0, "steps": [{**b0["steps"][0], "ms": None}]})

    def test_the_declared_fields_and_enums_are_required(self):
        for change in ({"condition": "with_casepath"}, {"session": 3}, {"model_tokens": 1200},
                       {"edit": {**example()["edit"], "slots": {"brief": 0.1}}}, {"steps": [{**example()["steps"][0], "n": 2}]}):
            with self.assertRaises(ValueError, msg=str(change)):
                check_rehearsal({**example(), **change})
        missing = example()
        del missing["events"]
        with self.assertRaises(ValueError):
            check_rehearsal(missing)

    @unittest.skipUnless(os.environ.get("CASEPATH_REHEARSAL_RECEIPTS"), "no rehearsal receipts named (CASEPATH_REHEARSAL_RECEIPTS)")
    def test_the_receipts_of_a_rehearsal(self):
        found = sorted(Path(os.environ["CASEPATH_REHEARSAL_RECEIPTS"]).glob("*.json"))
        self.assertTrue(found, "no receipt in the folder")
        for path in found:
            with self.subTest(receipt=path.name):
                check_rehearsal(json.loads(path.read_text(encoding="utf-8")))


TREE = "3f2a9c1b7d4e"
LABELS = {"format": "casepath.labels/1", "dossier": "D11", "case": "case_d11",
          "decisions": [{"fact": "deckung", "value": "bestätigt", "from": "2026-09-08"}],
          "points": [{"n": 1, "date": "2026-08-02", "kind": "A1", "to": "kunde", "documents": ["mietvertrag"], "questions": 1, "date_set": None,
                      "internal": False},
                     {"n": 2, "date": "2026-08-17", "kind": "A4", "to": "kunde", "documents": [], "questions": 2, "date_set": None, "internal": False},
                     {"n": 3, "date": "2026-09-08", "kind": "A5", "to": "kunde", "documents": ["other:stromkosten"], "questions": 0, "date_set": None,
                      "internal": False},
                     {"n": 4, "date": "2026-12-29", "kind": "A7", "to": "kunde", "documents": [], "questions": 0, "date_set": "2027-01-05",
                      "internal": False}]}
# D11's shape in the labels template's rows (synthetic): the claim with four photos, the first request, the reply with
# forwarded mail, a screenshot, a receipt and the old lease, the question back, two replies on one day, the assessment, the
# status inquiry; 28 pages
ROWS = [(1, 1, "2026-08-01", "kunde"), (2, None, None, "kunde"), (6, 2, "2026-08-02", "versicherer"), (7, 3, "2026-08-14", "kunde"),
        (8, None, "2026-07-20", "kunde"), (12, None, None, "gegenpartei"), (13, None, None, "andere"), (15, None, "2019-04-01", "gegenpartei"),
        (20, 4, "2026-08-17", "versicherer"), (21, 5, "2026-09-05", "kunde"), (23, None, None, "kunde"), (24, 6, "2026-09-05", "kunde"),
        (26, 7, "2026-09-08", "versicherer"), (28, 8, "2026-12-29", "versicherer")]
TEMPLATE = {"documents": [{"n": n, "date": d, "from": f, "page": p, "file": "Akte.pdf", **({} if n else {"entry": False})} for p, n, d, f in ROWS]}


def labels_hash(labels):
    import hashlib
    return hashlib.sha256(json.dumps(labels, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


class FakeApp:
    """The pilot's API as the episode's interfaces design it, on synthetic data; every request is recorded."""

    def __init__(self, full_usage=60_000, duplicate=409, auto="aus", tree=TREE):
        self.calls, self.full_usage, self.duplicate, self.auto, self.tree = [], full_usage, duplicate, auto, tree
        self.uploads = []

    def run(self, run_id, kind, usage):
        return {"id": run_id, "kind": kind, "status": "completed", "created_at": "2026-11-15T10:00:00+00:00", "finished_at": "2026-11-15T10:03:05+00:00",
                "result": {"usage": usage, "record": {"dropped": 2 if kind == "update" else 1, "elsewhere": 0},
                           **({"update": {"entries": [5, 6], "facts": ["mangel_besteht", "reaktion_vermieter", "will_schadenersatz"],
                                          "ledger": {"closed": [{"id": "r4.0", "how": "answered", "held": None}], "refused": [], "partial": [],
                                                     "promised": [], "unspecified": []}},
                               "brief": {"dropped_tags": 0, "questions": [],
                                         "claims": [{"what": "Stromkosten", "amount": "CHF 85", "checked": True, "documented": False}]}}
                              if kind == "update" else {})}}

    def call(self, method, path, body=None):
        self.calls.append((method, path))
        if path == "/api/manifest":
            return {"source_tree_sha256": self.tree + "0" * 52}
        if path == "/api/replay-points":
            return {"rows": [{"dossier": "D11", "case": "case_d11", "n": 3}, {"dossier": "D3", "case": "case_d3", "n": 1}]}
        if path == "/api/cases/case_d11/labels":
            return copy.deepcopy(LABELS)
        if path == "/api/cases/case_d11":
            return {"files": [{"id": "file_1", "name": "Akte.pdf", "kind": "pdf", "extraction": {"pages": 28}}]}
        if path == "/api/cases/case_d11/labels-template":
            return copy.deepcopy(TEMPLATE)
        if path == "/api/cases/case_d11/cut":
            self.cut = body
            return {"id": "case_base"}
        if path == "/api/cases/case_base/runs":
            return {"id": "run_full", "status": "queued"}
        if path == "/api/runs/run_full":
            return self.run("run_full", "full", [{"agent": "claim_reader", "input_tokens": self.full_usage, "cached_tokens": 0, "output_tokens": 9000},
                                                 {"agent": "reader", "input_tokens": 1500, "cached_tokens": 0, "output_tokens": 300}])
        if path == "/api/cases/case_base/update":
            return {"id": "run_update", "status": "queued"}
        if path == "/api/runs/run_update":
            return self.run("run_update", "update", [{"agent": "claim_reader", "input_tokens": 30_000, "cached_tokens": 12_000, "output_tokens": 5000},
                                                     {"agent": "source_checker", "input_tokens": 4000, "cached_tokens": 0, "output_tokens": 600}])
        if path == "/api/cases/case_base":
            if method == "DELETE":
                return {"deleted": "case_base"}
            return {"items": [{"kind": "next_action", "action": "A5"}], "draft": {"text": "Brief ohne Lücke."},
                    "assessment": {"questions": [{"item_id": "customer_question:0", "state": "beantwortet", "about": ["hinterlegung"], "intent": "weiter_zahlen"},
                                                 {"item_id": "customer_question:1", "state": "bedingt", "about": ["hinterlegung"], "intent": "hinterlegen"},
                                                 {"item_id": "customer_question:2", "state": "prüfen", "about": ["schadenersatz"], "intent": "ersatz",
                                                  "reason": "Verneinung: Zuordnung prüfen"}],
                                   "blocking": [{"kind": "decision", "key": "empfehlung", "text": "Empfehlung"}],
                                   "proposal": ["frist_beseitigung", "schadenersatz"],
                                   "residual": [{"key": "residual:claim.0", "line": "Belege zu: Stromkosten für den Bautrockner"}]}}
        if path == "/api/cases/case_base/edits" or path == "/api/cases/case_base/labels":
            return {}
        if path == "/api/replay-points?case=case_base":
            return {"rows": [{"dossier": "D11", "case": "case_base", "n": 3, "kind": "A5", "kind_ok": True, "ready": False,
                              "documents": {"label": 1, "hits": [], "missed": ["other:stromkosten"], "extras": []},
                              "accept": {"recipient": {"label": "kunde", "form": ["kunde"], "ok": True},
                                         "residual": {"label": 1, "hits": ["other:stromkosten"], "missed": [], "extras": [], "ok": True},
                                         "questions": {"beantwortet": 1, "bedingt": 1, "offen": 0, "pruefen": 1, "label": None, "ok": None},
                                         "substantive": {"present": True, "gaps": 0, "status": "unverified", "verdict": None},
                                         "authority": {"needs": ["deckung", "aussichten"], "missing": ["aussichten"], "ok": False}}}]}
        if path.startswith("/api/runs/") and path.endswith("/stop"):
            return {"stopping": True}
        raise AssertionError(f"unexpected request {method} {path}")

    def raw(self, path):
        self.calls.append(("GET", path))
        return b"%PDF-1.4 synthetic " + path.encode()

    def upload(self, case_id, files):
        self.calls.append(("POST", f"/api/cases/{case_id}/files"))
        self.uploads.append([name for name, _ in files])
        if len(self.uploads) == 1:
            return 201, {"files": [{"id": f"file_{i}"} for i, _ in enumerate(files, 2)], "skipped": [], "auto": self.auto,
                         "run": {"id": "run_update"} if self.auto == "gestartet" else None}
        return self.duplicate, {}


class DiagnoseRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cell = runpy.run_path(str(CELL))  # no dbutils: only its functions

    def setUp(self):
        self.volume = tempfile.TemporaryDirectory()
        self.addCleanup(self.volume.cleanup)
        self.phrase = f"diagnose D11 {TREE} {labels_hash(LABELS)[:12]}"

    def diagnose(self, app, **kw):
        return self.cell["diagnose"](app, self.volume.name, TREE, labels_hash(LABELS)[:12], kw.pop("keep", False), poll=0, **kw)

    def test_a_without_its_confirm_phrase_it_makes_no_request(self):
        env = {"CASEPATH_EVAL_IDENTITY_HEADER": "Authorization", "CASEPATH_EVAL_IDENTITY": "Bearer x"}
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("a request was made")) as urlopen:
            for phrase in ("", "diagnose D11", f"diagnose D11 {TREE}", f"diagnose D12 {TREE} {'0' * 12}", f"deploy abc1234 3 {TREE}",
                           f"diagnose D11 {TREE.upper()} {'0' * 12}", f"diagnose D11 {TREE} {'0' * 12} now"):
                with self.assertRaisesRegex(AssertionError, "confirm must read", msg=phrase):
                    self.cell["main"](phrase, "https://app.example", self.volume.name, env)
            with self.assertRaisesRegex(AssertionError, "fill in APP and VOLUME"):
                self.cell["main"](self.phrase, self.cell["APP"], self.volume.name, env)
            with self.assertRaisesRegex(AssertionError, "the identity the app expects"):
                self.cell["main"](self.phrase, "https://app.example", self.volume.name, {})

            class Dbutils:
                class widgets:
                    get = staticmethod(lambda name: "")
            with self.assertRaisesRegex(AssertionError, "confirm must read"):
                runpy.run_path(str(CELL), init_globals={"dbutils": Dbutils()})  # the notebook cell as it runs, with an empty parameter
            self.assertEqual(urlopen.call_count, 0)
        self.assertEqual(os.listdir(self.volume.name), [])

    def test_b_another_build_or_other_labels_do_nothing(self):
        app = FakeApp(tree="aaaaaaaaaaaa")
        with self.assertRaisesRegex(AssertionError, "not the one approved: nothing done"):
            self.diagnose(app)
        self.assertEqual(app.calls, [("GET", "/api/manifest")])
        with self.assertRaisesRegex(AssertionError, "labels are not the ones approved"):
            self.cell["diagnose"](FakeApp(), self.volume.name, TREE, "0" * 12, False, poll=0)
        self.assertEqual(os.listdir(self.volume.name), [])

    def test_c_the_run_takes_its_steps_in_order_and_its_receipt_is_content_free(self):
        app = FakeApp()
        receipt = self.diagnose(app)
        self.assertEqual((receipt["status"], receipt["stopped"], receipt["base"], receipt["duplicate_refused"]), ("done", None, "case_base", True))
        self.assertEqual(app.cut, {"pages": "1-20", "as_of": "2026-09-08", "file": "file_1"})  # the pages known before the replies
        self.assertEqual(app.uploads, [["Antwort-1.pdf", "Antwort-2.pdf"], ["Antwort-1.pdf"]])  # one import, then one again
        self.assertIn(("GET", "/api/files/file_1/original?pages=21-23"), app.calls)
        self.assertIn(("GET", "/api/files/file_1/original?pages=24-25"), app.calls)
        order = [path for _, path in app.calls]
        steps = ["/api/cases/case_d11/cut", "/api/cases/case_base/runs", "/api/cases/case_base/files", "/api/cases/case_base/update",
                 "/api/cases/case_base/edits", "/api/cases/case_base/labels", "/api/replay-points?case=case_base"]
        self.assertEqual([p for p in order if p in steps], steps[:2] + [steps[2], steps[2]] + steps[3:])
        self.assertEqual(app.calls[-1], ("DELETE", "/api/cases/case_base"))
        full, update = receipt["runs"]
        self.assertEqual((full["kind"], full["seconds"], full["non_cached"], full["pages_read"]), ("full", 185, 61_500, 1))
        self.assertEqual((update["kind"], update["usage"]["claim_reader"]["non_cached"], update["output"]), ("update", 18_000, 5600))
        case = receipt["case"]
        self.assertEqual(case["questions"]["states"], {"beantwortet": 1, "bedingt": 1, "offen": 0, "pruefen": 1})
        self.assertEqual((case["questions"]["guard_rows"], case["questions"]["tagged"]), ([3], 3))
        self.assertEqual((case["claims"], case["ledger"]["closed"], case["update"]["new_entries"], case["update"]["dropped"]),
                         ({"found": 1, "checked": 1, "amount_kept": 1, "documented": 0}, 1, 2, 1))
        self.assertEqual((case["decision"], case["proposal"], case["residual"], case["gaps"], case["next_action"]),
                         (["empfehlung"], ["frist_beseitigung", "schadenersatz"], {"keys": ["residual:claim.0"], "count": 1}, 0, "a5"))
        self.assertEqual(receipt["n3"]["accept"]["residual"]["hits"], ["other:stromkosten"])
        self.assertEqual((receipt["decisions"], receipt["missing"]), (["deckung"], []))
        body = {k: v for k, v in receipt.items() if k != "format"}
        self.assertEqual(guard(body), body)  # quality/scorecard.py's guard: ids, counts and enums only
        text = json.dumps(receipt, ensure_ascii=False)
        self.assertIsNone(re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{2,4}", text))
        for word in ("Stromkosten für", "Bautrockner", "CHF", "Akte.pdf", "Lücke", "Verneinung", "D11"):
            self.assertNotIn(word, text)
        stored = json.loads((Path(self.volume.name) / "diagnose" / f"D11-{labels_hash(LABELS)[:12]}.json").read_text())
        self.assertEqual(stored, receipt)
        again = FakeApp()
        with mock.patch("sys.stdout", new_callable=io.StringIO) as printed:
            self.assertEqual(self.diagnose(again), receipt)  # no second run
        self.assertIn("already run", printed.getvalue())
        self.assertEqual(again.calls, [("GET", "/api/manifest"), ("GET", "/api/replay-points"), ("GET", "/api/cases/case_d11/labels")])

    def test_d_a_preparation_over_its_cap_stops_the_run_before_the_arrival(self):
        app = FakeApp(full_usage=230_000)
        receipt = self.diagnose(app)
        self.assertEqual((receipt["status"], receipt["stopped"]), ("stopped", {"step": "prepare", "reason": "over_soft_cap"}))
        self.assertEqual((app.uploads, receipt["case"]), ([], None))
        self.assertNotIn(("POST", "/api/cases/case_base/update"), app.calls)
        self.assertEqual(app.calls[-1], ("DELETE", "/api/cases/case_base"))
        guard({k: v for k, v in receipt.items() if k != "format"})

    def test_e_a_duplicate_not_refused_stops_the_run_and_no_update_is_spent(self):
        app = FakeApp(duplicate=201, auto="gestartet")
        receipt = self.diagnose(app, keep=True)
        self.assertEqual((receipt["status"], receipt["stopped"], receipt["duplicate_refused"]),
                         ("stopped", {"step": "arrival", "reason": "duplicate_accepted"}, False))
        self.assertIn(("POST", "/api/runs/run_update/stop"), app.calls)  # the update the import started is stopped
        self.assertNotIn(("DELETE", "/api/cases/case_base"), app.calls)  # kept for the inside review
        self.assertTrue(receipt["kept"])

    def test_f_the_import_is_one_request_with_every_reply_and_the_identity(self):
        captured = []

        class Answer:
            def __init__(self, body):
                self.body = body

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return self.body

        def urlopen(request, timeout):
            captured.append(request)
            return Answer(b'{"files": [], "auto": "aus"}')
        api = self.cell["Api"]("https://app.example/", {"Authorization": "Bearer x"})
        with mock.patch("urllib.request.urlopen", urlopen):
            status, answer = api.upload("case_base", [("Antwort-1.pdf", b"%PDF one"), ("Antwort-2.pdf", b"%PDF two")])
        request, = captured
        self.assertEqual((status, answer["auto"], request.full_url, request.get_method()), (201, "aus", "https://app.example/api/cases/case_base/files", "POST"))
        self.assertEqual(request.get_header("Authorization"), "Bearer x")
        self.assertTrue(request.get_header("Content-type").startswith("multipart/form-data; boundary="))
        self.assertEqual(request.data.count(b'name="files"'), 2)

    def test_h_the_read_only_mode_names_the_hashes_for_the_approval(self):
        app = FakeApp()
        with mock.patch("sys.stdout", new_callable=io.StringIO) as printed:
            out = self.cell["hashes"](app)
        self.assertEqual(printed.getvalue().strip(), f"approval reads: {self.phrase}")
        self.assertEqual((out["build"], out["case"]), (TREE, "case_d11"))
        self.assertEqual([m for m, _ in app.calls], ["GET", "GET", "GET"])  # it only reads

    def test_g_the_pages_come_from_the_labels_template(self):
        n3, base, replies = self.cell["plan"](LABELS, TEMPLATE, {"name": "Akte.pdf", "extraction": {"pages": 28}})
        self.assertEqual((n3["n"], base, replies), (3, list(range(1, 21)), [[21, 22, 23], [24, 25]]))  # the old lease rides with its e-mail
        self.assertEqual(self.cell["spans"]([1, 2, 3, 7, 9, 10]), "1-3,7,9-10")
        no_reply = copy.deepcopy(TEMPLATE)
        no_reply["documents"] = [r for r in no_reply["documents"] if r["page"] < 21 or r["page"] > 25]
        with self.assertRaises(self.cell["Stop"]):
            self.cell["plan"](LABELS, no_reply, {"name": "Akte.pdf", "extraction": {"pages": 28}})


if __name__ == "__main__":
    unittest.main()
