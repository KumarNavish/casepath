"""Receipts of the episode's measurements hold ids, counts and enums only (quality/scorecard.py, SAFE and guard), and no date;
the rehearsal times both conditions by one rule and judges edits per part without guessing; and the one diagnostic run on
the pilot (deploy/databricks/rehearse.py) does nothing without its confirm phrase.

``casepath.rehearsal/1`` is what deploy/preview/rehearse_episode.mjs writes for one rehearsal of the D11 episode on a
synthetic analog (MEASURE §1): label, build, episode, condition, session; per step its time, clicks, decisions and
confirmations (counted apart, by the rule declared before scoring), text edits, characters typed, context switches,
documents opened whole and passages opened from a source chip, page and inner scrolls; the declared external steps with
their time; the edits judged per part of the letter (substantive, stylistic or «zu beurteilen», with their reasons; the
change ratio beside them, deciding nothing); the case's events by kind; the timing rule, every interruption taken out of a
step as an entry of its own, and any asymmetry between the conditions, stated.

Time is one rule for B0 and N: from the prompt that names a step to the Enter that ends it, silent reading counted in full,
a declared interruption taken out and listed. Receipts timed by different rules are never compared (``comparable``).

A rehearsal's receipts are checked by this test too: CASEPATH_REHEARSAL_RECEIPTS names a folder whose *.json files must
each be a valid receipt (skipped when unset). The script's own timing and edit verdicts are checked by running it with
MODE=selftest (skipped without node).

``casepath.diagnose/1`` is what the diagnostic run writes (MEASURE §3). Its script is run here against a stand-in for the
app's API that answers as the episode's interfaces are designed (DESIGN §6, SLICE_A A8, SLICE_C C7), on synthetic data:
no request leaves, no model is called. Its cut, D11's earlier state and its two arrivals, is made of whole documents of the
labels template (with or without account entries), every page in exactly one part, and sealed into the confirm phrase; the plan it prints names the separate
approvals the run needs and its stop threshold, which is never a budget."""
import copy
import io
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from casepath.quality.scorecard import ScorecardLeak, guard

CELL = Path(__file__).resolve().parents[1] / "deploy" / "databricks" / "rehearse.py"
REHEARSAL = Path(__file__).resolve().parents[1] / "deploy" / "preview" / "rehearse_episode.mjs"

FORMAT = "casepath.rehearsal/1"
LABEL = "developer_rehearsal.synthetic_analog.handler_savings_unverified"
SCRIPTED = "scripted_path.synthetic_analog.no_handler_time"  # the script took the steps: the path's counts, never a handler's time
CONDITIONS = {"b0", "b1", "n"}
STEP = {"n", "name", "ms", "clicks", "decisions", "confirmations", "edits", "chars", "switches", "opened_whole", "passages", "scrolls"}
SLOTS = {"im_fall", "zu_fragen", "empfehlung", "nachzureichen", "other"}
VERDICTS = {"substantive", "stylistic", "zu_beurteilen"}
RULES = {"wall_minus_declared_interruptions", "machine"}
DATE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{2,4}")


def check_rehearsal(receipt):
    """The receipt if it is a valid casepath.rehearsal/1 receipt; ValueError (or ScorecardLeak) naming what is not."""
    if not isinstance(receipt, dict) or receipt.get("format") != FORMAT:
        raise ValueError(f"format: {FORMAT}")
    body = {k: v for k, v in receipt.items() if k != "format"}  # the format names itself with a slash
    keys = {"label", "build", "episode", "condition", "session", "steps", "external", "edit", "events", "duplicate_refused", "timing",
            "wall_ms", "model_tokens"}
    if set(body) != keys:
        raise ValueError(f"fields: {sorted(keys)}, not {sorted(body)}")
    guard(body)
    if DATE.search(json.dumps(body)):
        raise ScorecardLeak("a date is case content: a receipt holds none")
    if body["label"] not in (LABEL, SCRIPTED) or body["condition"] not in CONDITIONS or body["episode"] not in {"e1", "e2"} or body["session"] not in {1, 2}:
        raise ValueError("label, condition (b0, b1, n), episode (e1, e2) and session (1, 2) as declared")
    timing = body["timing"]
    if (set(timing) != {"rule", "interruptions", "asymmetry"} or timing["rule"] not in RULES
            or (timing["rule"] == "machine") != (body["label"] == SCRIPTED)
            or any(set(x) != {"at", "ms"} or type(x["ms"]) is not int or x["ms"] < 0 for x in timing["interruptions"])
            or not isinstance(timing["asymmetry"], list)):
        raise ValueError("timing: rule (machine only for the scripted path, else wall_minus_declared_interruptions), interruptions [{at, ms}], asymmetry")
    if timing["rule"] == "machine" and "machine_time_not_handler_time" not in timing["asymmetry"]:
        raise ValueError("timing: a scripted path states that its time is the machine's")
    if body["condition"] == "b0" and "counts_not_measured_without_a_browser" not in timing["asymmetry"]:
        raise ValueError("timing: the baseline states that what no browser measures is not counted")
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
    if set(edit) != {"ratio_words", "substantive", "stylistic", "zu_beurteilen", "parts", "slots"} or set(edit["slots"]) - SLOTS:
        raise ValueError(f"edit: ratio_words, substantive, stylistic, zu_beurteilen, parts and slots by {sorted(SLOTS)}")
    if body["condition"] != "b0":
        if None in (edit["ratio_words"], edit["substantive"], edit["stylistic"], edit["zu_beurteilen"]):
            raise ValueError("edit: every count is measured with CasePath")
        if any(set(x) != {"part", "verdict", "reasons"} or x["verdict"] not in VERDICTS for x in edit["parts"]):
            raise ValueError("edit.parts: [{part, verdict (substantive, stylistic, zu_beurteilen), reasons}]: no text")
        if any(edit[v] != sum(1 for x in edit["parts"] if x["verdict"] == v) for v in VERDICTS):
            raise ValueError("edit: the counts are the parts' verdicts")
    if body["duplicate_refused"] not in (True, False, None):
        raise ValueError("duplicate_refused: whether the second drop of the reply was refused (None in the baseline)")
    if body["model_tokens"] != 0:
        raise ValueError("model_tokens: a rehearsal runs scripted, 0 tokens")
    return receipt


def comparable(b0, n):
    """The two conditions' active times, (B0 ms, N ms), only when both are timed by the same rule; ValueError otherwise."""
    rules = {check_rehearsal(b0)["timing"]["rule"], check_rehearsal(n)["timing"]["rule"]}
    if rules != {"wall_minus_declared_interruptions"}:
        raise ValueError(f"not comparable: timed by {sorted(rules)}")
    total = lambda r: sum(s["ms"] for s in r["steps"]) + sum(x["ms"] for x in r["external"])
    return total(b0), total(n)


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
            "edit": {"ratio_words": 0.04, "substantive": 1, "stylistic": 1, "zu_beurteilen": 1,
                     "parts": [{"part": "p3", "verdict": "substantive", "reasons": ["state"]},
                               {"part": "p1", "verdict": "stylistic", "reasons": ["courtesy_or_function_words"]},
                               {"part": "p6", "verdict": "zu_beurteilen", "reasons": ["content_words_changed"]}],
                     "slots": {"im_fall": 0.0, "zu_fragen": 0.06, "empfehlung": 0.0, "nachzureichen": 0.0, "other": 0.02}},
            "events": {"action.approved": 1, "bundle.saved": 1, "letter.copied": 1, "action.dispatched": 1, "update.started": 1},
            "duplicate_refused": True, "timing": {"rule": "wall_minus_declared_interruptions", "interruptions": [{"at": "step:5", "ms": 240000}],
                                                  "asymmetry": []},
            "wall_ms": 112000, "model_tokens": 0}


def baseline():
    """The same episode's B0 receipt (synthetic numbers): no browser, so its counts are null and the receipt says so."""
    b0 = example()
    b0.update(condition="b0", build="none", duplicate_refused=None, events={},
              edit={"ratio_words": None, "substantive": None, "stylistic": None, "zu_beurteilen": None, "parts": [], "slots": {}},
              steps=[{**s, "clicks": None, "edits": None, "chars": None, "opened_whole": None, "passages": None,
                      "scrolls": {"page": None, "inner": None}} for s in example()["steps"]],
              timing={"rule": "wall_minus_declared_interruptions", "interruptions": [], "asymmetry": ["counts_not_measured_without_a_browser"]})
    return b0


class RehearsalReceiptTests(unittest.TestCase):
    def test_a_receipt_of_ids_counts_and_enums_passes(self):
        receipt = check_rehearsal(example())
        self.assertEqual(sum(s["decisions"] for s in receipt["steps"]), 3)  # Deckung, Empfehlung, Freigeben
        self.assertEqual(sum(s["confirmations"] for s in receipt["steps"]), 2)  # Brief kopieren, Versandt am: counted apart

    def test_case_content_free_text_and_dates_are_refused(self):
        for change in ({"label": "Entwickler-Probe, synthetisch"}, {"build": "D11 Steiner"}, {"events": {"Brief kopieren": 1}},
                       {"steps": [{**example()["steps"][0], "name": "Muss ich weiterhin die volle Miete bezahlen?"}]},
                       {"external": [{"name": "send", "ms": 9000, "to": "kundin@example.ch"}]},
                       {"steps": [{**example()["steps"][0], "name": "open_2026-11-15"}]},
                       {"edit": {**example()["edit"], "parts": [{"part": "p3", "verdict": "substantive", "reasons": ["state"],
                                                                 "final": "Das Angebot ist abzulehnen."}]}}):
            with self.assertRaises((ValueError, ScorecardLeak), msg=str(change)):
                check_rehearsal({**example(), **change})

    def test_the_baseline_leaves_unmeasured_what_no_browser_measures_and_says_so(self):
        check_rehearsal(baseline())
        with self.assertRaises(ValueError):  # with CasePath every count is measured
            check_rehearsal({**baseline(), "condition": "n"})
        with self.assertRaises(ValueError):  # time is measured in the baseline too
            check_rehearsal({**baseline(), "steps": [{**baseline()["steps"][0], "ms": None}]})
        with self.assertRaises(ValueError):  # the asymmetry is stated, never hidden
            check_rehearsal({**baseline(), "timing": {**baseline()["timing"], "asymmetry": []}})

    def test_both_conditions_are_timed_by_one_rule_or_not_compared(self):
        self.assertEqual(comparable(baseline(), example()), (sum(s["ms"] for s in example()["steps"]) + 47000,) * 2)
        scripted = {**example(), "label": SCRIPTED, "timing": {"rule": "machine", "interruptions": [],
                                                               "asymmetry": ["machine_time_not_handler_time", "external_steps_not_taken"]}}
        check_rehearsal(scripted)
        with self.assertRaisesRegex(ValueError, "not comparable"):  # a machine's time is never set against a person's
            comparable(baseline(), scripted)
        for timing in ({"rule": "machine", "interruptions": [], "asymmetry": ["machine_time_not_handler_time"]},  # a person's rehearsal
                       {"rule": "active_with_idle_cap", "interruptions": [], "asymmetry": []},  # a rule that caps silent reading
                       {"rule": "wall_minus_declared_interruptions", "interruptions": [{"at": "step:5"}], "asymmetry": []}):
            with self.assertRaises(ValueError, msg=str(timing)):
                check_rehearsal({**example(), "timing": timing})

    def test_the_declared_fields_and_enums_are_required(self):
        for change in ({"condition": "with_casepath"}, {"session": 3}, {"model_tokens": 1200},
                       {"edit": {**example()["edit"], "slots": {"brief": 0.1}}}, {"steps": [{**example()["steps"][0], "n": 2}]},
                       {"edit": {**example()["edit"], "substantive": 2}},  # the counts are the parts' verdicts
                       {"edit": {**example()["edit"], "parts": [{"part": "p3", "verdict": "probably_stylistic", "reasons": []}]}}):
            with self.assertRaises(ValueError, msg=str(change)):
                check_rehearsal({**example(), **change})
        missing = example()
        del missing["events"]
        with self.assertRaises(ValueError):
            check_rehearsal(missing)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_the_scripts_own_timing_is_symmetric_and_its_edits_are_judged_per_part(self):
        """deploy/preview/rehearse_episode.mjs with MODE=selftest: its own timing rule and edit adjudication on fixed inputs."""
        done = subprocess.run(["node", str(REHEARSAL)], env={**os.environ, "MODE": "selftest"}, capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        out = json.loads(done.stdout)
        self.assertEqual(out["timing"]["silent_five_minutes"], {"b0": 300000, "n": 300000})  # silent reading counts in full in both
        self.assertEqual(out["timing"]["interrupted"], {"b0": 180000, "n": 180000})  # a declared interruption leaves both alike
        verdict = lambda name: (out["edits"][name]["verdict"], out["edits"][name]["reasons"])
        self.assertEqual(verdict("accept_to_refuse"), ("substantive", ["state"]))  # «anzunehmen» → «abzulehnen»
        self.assertEqual(verdict("remedied_to_persisting"), ("substantive", ["state"]))  # «behoben» → «fortbestehend»
        self.assertEqual(verdict("courtesy"), ("stylistic", ["courtesy_or_function_words"]))  # «Vielen Dank» → «Besten Dank»
        self.assertEqual(verdict("punctuation")[0], "stylistic")
        for name in ("greeting", "date_notation", "amount_notation"):  # the same recipient, day and amount, written otherwise
            self.assertEqual(verdict(name)[0], "stylistic", name)
        for name, reason in (("negation", "negation"), ("date", "date"), ("amount", "amount"), ("recipient", "recipient"),
                             ("required", "required_part"), ("answer_removed", "answer_added_or_removed"), ("option", "option"),
                             ("condition", "condition")):
            self.assertEqual(verdict(name)[0], "substantive", name)
            self.assertIn(reason, verdict(name)[1], name)
        self.assertEqual(verdict("content_word"), ("zu_beurteilen", ["content_words_changed"]))  # a person decides, never a guess
        self.assertEqual(verdict("word_order"), ("zu_beurteilen", ["word_order_changed"]))
        letter = out["letter"]
        self.assertEqual((letter["substantive"], letter["stylistic"], letter["zu_beurteilen"]), (1, 1, 0))
        self.assertEqual(letter["parts"], [{"part": "para.1", "verdict": "stylistic", "reasons": ["courtesy_or_function_words"]},
                                           {"part": "para.2", "verdict": "substantive", "reasons": ["state"]}])  # ids and reasons, no text
        self.assertEqual(out["action"], [{"part": "letter", "verdict": "substantive", "reasons": ["action"]}])

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
TEMPLATE = {"documents": [{"n": n, "date": d, "from": f, "page": p, "file": "Akte.pdf", "insurer": f == "versicherer", **({} if n else {"entry": False})}
                          for p, n, d, f in ROWS]}
# D11's stored reading has no account entries (the bridge's outline): its template lists the reader's segments only, each
# sender as written. Synthetic and shaped as the outline: 15 segments on 30 pages, a lease long before, undated photos, a
# receipt and a screenshot, the insurer's first answer not recognised as the insurer's, two customer e-mails of one day.
SEGMENTS = [(1, "2019-04-01", "Immo Muster AG"), (6, "2026-07-31", "Lea Exempel"), (7, "2026-08-01", "Schadenteam"),
            (8, "2026-08-13", "Lea Exempel"), (16, None, "Immo Muster AG"), (17, None, "Baumarkt Beispiel"), (18, None, "Lea Exempel"),
            (19, None, "Lea Exempel"), (20, None, "Lea Exempel"), (21, None, None), (22, "2026-08-16", "Protekta Rechtsschutz"),
            (23, "2026-09-04", "Lea Exempel"), (26, "2026-09-04", "Lea Exempel"), (28, "2026-09-07", "Protekta Rechtsschutz"),
            (30, "2026-12-28", "Protekta Rechtsschutz")]
SEGMENT_TEMPLATE = {"documents": [{"n": None, "date": d, "from": f, "page": p, "file": "Akte.pdf", "insurer": f == "Protekta Rechtsschutz",
                                   "entry": False} for p, d, f in SEGMENTS]}
# D11's file as the pilot's stored reading gives it (the shape the console's «shape D11» printed there; synthetic here, the
# labels' own days): printed with the newest on top. The status inquiry, the assessment with an undated enclosure, the two
# replies of one day, the question back, the first reply with an older paper sent along, the first answer not recognised
# as the insurer's, the claim last; 15 segments on 28 pages, no account entry, every sender as written.
REVERSED = [(1, "2026-12-29", "Protekta Rechtsschutz"), (3, "2026-09-08", "Protekta Rechtsschutz"), (5, None, "Lea Exempel"),
            (6, "2026-09-05", "Lea Exempel"), (8, "2026-09-05", "Lea Exempel"), (11, "2026-08-17", "Protekta Rechtsschutz"), (12, None, "Lea Exempel"),
            (13, "2026-08-14", "Lea Exempel"), (15, "2026-07-20", "Immo Muster AG"), (16, None, "Lea Exempel"), (17, "2026-08-02", "Schadenteam"),
            (18, None, "Lea Exempel"), (19, None, "Baumarkt Beispiel"), (20, None, "Lea Exempel"), (21, "2026-08-01", "Lea Exempel")]
REVERSED_TEMPLATE = {"documents": [{"n": None, "date": d, "from": f, "page": p, "file": "Akte.pdf", "insurer": f == "Protekta Rechtsschutz",
                                    "entry": False} for p, d, f in REVERSED]}
SEGMENT_LABELS = {**LABELS, "points": [{**point, "date": day} for point, day in
                                       zip(LABELS["points"], ("2026-08-01", "2026-08-16", "2026-09-07", "2026-12-28"))]}


def labels_hash(labels):
    import hashlib
    return hashlib.sha256(json.dumps(labels, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


class FakeApp:
    """The pilot's API as the episode's interfaces design it, on synthetic data; every request is recorded."""

    def __init__(self, full_usage=60_000, duplicate=409, auto="aus", tree=TREE, template=None):
        self.calls, self.full_usage, self.duplicate, self.auto, self.tree = [], full_usage, duplicate, auto, tree
        self.uploads, self.template = [], template or TEMPLATE
        self.latest = None  # the base case's latest run, as the case view gives it («run»)

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
            return copy.deepcopy(self.template)
        if path == "/api/cases/case_d11/cut":
            self.cut = body
            return {"id": "case_base"}
        if path == "/api/cases/case_base/runs":
            self.latest = {"id": "run_full", "kind": "full", "status": "queued"}
            return {"id": "run_full", "status": "queued"}
        if path == "/api/runs/run_full":
            return self.run("run_full", "full", [{"agent": "claim_reader", "input_tokens": self.full_usage, "cached_tokens": 0, "output_tokens": 9000},
                                                 {"agent": "reader", "input_tokens": 1500, "cached_tokens": 0, "output_tokens": 300}])
        if path == "/api/cases/case_base/update":
            self.latest = {"id": "run_update", "kind": "update", "status": "queued"}
            return {"id": "run_update", "status": "queued"}
        if path == "/api/runs/run_update":
            return self.run("run_update", "update", [{"agent": "claim_reader", "input_tokens": 30_000, "cached_tokens": 12_000, "output_tokens": 5000},
                                                     {"agent": "source_checker", "input_tokens": 4000, "cached_tokens": 0, "output_tokens": 600}])
        if path == "/api/cases/case_base":
            if method == "DELETE":
                return {"deleted": "case_base"}
            return {"run": self.latest, "items": [{"kind": "next_action", "action": "A5"}], "draft": {"text": "Brief ohne Lücke."},
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
            if self.auto == "gestartet":
                self.latest = {"id": "run_update", "kind": "update", "status": "queued"}
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
        self.cut = self.cell["plan"](LABELS, TEMPLATE, {"name": "Akte.pdf", "extraction": {"pages": 28}})
        self.phrase = f"diagnose D11 {TREE} {labels_hash(LABELS)[:12]} {self.cell['sealed'](self.cut)}"

    def diagnose(self, app, **kw):
        with mock.patch("sys.stdout", new_callable=io.StringIO) as printed:
            out = self.cell["diagnose"](app, self.volume.name, TREE, labels_hash(LABELS)[:12], kw.pop("plan", self.cell["sealed"](self.cut)),
                                        kw.pop("keep", False), poll=0, **kw)
        self.printed = printed.getvalue()
        return out

    def test_a_without_its_confirm_phrase_it_makes_no_request(self):
        env = {"CASEPATH_EVAL_IDENTITY_HEADER": "Authorization", "CASEPATH_EVAL_IDENTITY": "Bearer x"}
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("a request was made")) as urlopen:
            for phrase in ("", "diagnose D11", f"diagnose D11 {TREE}", f"diagnose D12 {TREE} {'0' * 12} {'0' * 12}", f"deploy abc1234 3 {TREE}",
                           f"diagnose D11 {TREE.upper()} {'0' * 12} {'0' * 12}", f"diagnose D11 {TREE} {'0' * 12} {'0' * 12} now",
                           f"diagnose D11 {TREE} {'0' * 12}"):  # the last: the cut unnamed, as the phrase read before the plan was sealed
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
            self.cell["diagnose"](FakeApp(), self.volume.name, TREE, "0" * 12, self.cell["sealed"](self.cut), False, poll=0)
        other = FakeApp()
        with self.assertRaisesRegex(AssertionError, "the cut is not the approved plan: nothing done"):
            self.diagnose(other, plan="0" * 12)
        self.assertFalse([path for _, path in other.calls if path.endswith("/cut")])
        self.assertEqual(os.listdir(self.volume.name), [])

    def test_c_the_run_takes_its_steps_in_order_and_its_receipt_is_content_free(self):
        app = FakeApp()
        receipt = self.diagnose(app)
        self.assertEqual((receipt["status"], receipt["stopped"], receipt["base"], receipt["duplicate_refused"]), ("done", None, "case_base", True))
        self.assertEqual(app.cut, {"pages": "1-20", "as_of": "2026-09-08", "file": "file_1"})  # the pages known before the replies
        self.assertEqual((receipt["plan"], receipt["cut"]), (self.cell["sealed"](self.cut), {"point": 3, "pages": 20, "left_out": 3}))
        self.assertIn("a stop, never a budget or an allowance", self.printed)
        self.assertIn(f"Navish's separate typed approval of the deployment of build {TREE} to the pilot and of this run's tokens", self.printed)
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
        self.assertEqual(self.diagnose(again), receipt)  # no second run
        self.assertIn("already run", self.printed)
        self.assertEqual(again.calls, [("GET", "/api/manifest"), ("GET", "/api/replay-points"), ("GET", "/api/cases/case_d11/labels")])

    def test_d_a_preparation_over_its_cap_stops_the_run_before_the_arrival(self):
        app = FakeApp(full_usage=230_000)
        receipt = self.diagnose(app)
        self.assertEqual((receipt["status"], receipt["stopped"]), ("stopped", {"step": "prepare", "reason": "past_the_stop_threshold"}))
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

    def test_h_the_read_only_mode_prints_the_plan_and_the_phrase_that_approves_exactly_it(self):
        app = FakeApp()
        with mock.patch("sys.stdout", new_callable=io.StringIO) as printed:
            out = self.cell["hashes"](app)
        lines = printed.getvalue().strip().splitlines()
        self.assertEqual(lines[-1], f"approval reads: {self.phrase}")
        self.assertEqual(lines[1], "  the earlier state: pages 1-20 (9 rows of the labels template), looked at on the day of point 3")
        self.assertIn("  the arrival, as the labels template lists it: 2 documents not the insurer's, pages 21-23, 24-25 (5 pages) as one import, "
                      "then one of them again", lines)
        self.assertIn("  left out: pages 26-28 (2 rows of the labels template, from the replies' day on)", lines)
        self.assertTrue(any("stops if it failed or its non-cached input passed 200,000 tokens: a stop, never a budget or an allowance" in x for x in lines))
        self.assertTrue(any("Navish's separate typed approval of the deployment of build" in x and "and of this run's tokens" in x for x in lines))
        self.assertEqual((out["build"], out["case"], out["plan"]), (TREE, "case_d11", self.cell["sealed"](self.cut)))
        self.assertEqual({m for m, _ in app.calls}, {"GET"})  # it only reads

    def test_g_the_cut_is_made_of_whole_documents_of_the_labels_template(self):
        """The earlier state and the two arrivals of D11, each page of the file in exactly one part; a template that does not
        give that cut stops the run before it does anything."""
        pdf = {"name": "Akte.pdf", "extraction": {"pages": 28}}
        cut = self.cell["plan"](LABELS, TEMPLATE, pdf)
        self.assertEqual((cut["n3"]["n"], cut["base"], cut["arrival"], cut["later"]), (3, list(range(1, 21)), [[21, 22, 23], [24, 25]], [26, 27, 28]))
        self.assertEqual((cut["entries"], cut["rows"]), ([5, 6], {"base": 9, "arrival": 3, "later": 2}))  # the reply's photo rides with it
        self.assertEqual(sorted(cut["base"] + cut["later"] + [p for a in cut["arrival"] for p in a]), list(range(1, 29)))
        self.assertEqual(self.cell["spans"]([1, 2, 3, 7, 9, 10]), "1-3,7,9-10")
        cases = {"no_reply_found": [r for r in TEMPLATE["documents"] if not 21 <= r["page"] <= 25],
                 "arrival_not_as_in_the_outline": [r for r in TEMPLATE["documents"] if r["page"] != 24],  # one reply where D11 has two
                 "pages_not_in_exactly_one_part": [r for r in TEMPLATE["documents"] if r["page"] != 1]}  # a first page in no document
        for reason, rows in cases.items():
            with self.assertRaises(self.cell["Stop"]) as stop:
                self.cell["plan"](LABELS, {"documents": rows}, pdf)
            self.assertEqual(stop.exception.args, ("cut", reason))
        with self.assertRaisesRegex(AssertionError, "arrival_not_as_in_the_outline: nothing done"):
            self.cell["hashes"](FakeApp(template={"documents": cases["arrival_not_as_in_the_outline"]}))
        moved = copy.deepcopy(TEMPLATE)
        moved["documents"][11]["page"] = 25  # the second reply starts a page later: another cut, another seal
        self.assertEqual(self.cell["plan"](LABELS, moved, pdf)["arrival"], [[21, 22, 23, 24], [25]])
        self.assertNotEqual(self.cell["sealed"](self.cell["plan"](LABELS, moved, pdf)), self.cell["sealed"](cut))
        inside = copy.deepcopy(TEMPLATE)
        inside["documents"][4]["page"] = 9  # an enclosure moved inside the earlier state: the same cut, the same seal
        self.assertEqual(self.cell["sealed"](self.cell["plan"](LABELS, inside, pdf)), self.cell["sealed"](cut))

    def test_i_a_template_of_segments_only_gives_the_same_cut(self):
        """D11's stored reading has no account entries: the template is the reader's segments, senders as written. The two
        e-mails of one day are two documents, undated photos and a receipt ride with the letter before them, and a document
        of another left out although known on the assessment's day stops the run."""
        pdf = {"name": "Akte.pdf", "extraction": {"pages": 30}}
        cut = self.cell["plan"](SEGMENT_LABELS, SEGMENT_TEMPLATE, pdf)
        self.assertEqual((cut["base"], cut["arrival"], cut["later"]), (list(range(1, 23)), [[23, 24, 25], [26, 27]], [28, 29, 30]))
        self.assertEqual((cut["entries"], cut["rows"]), ([None, None], {"base": 11, "arrival": 2, "later": 2}))
        rows = SEGMENT_TEMPLATE["documents"]
        undated = copy.deepcopy(rows)
        undated[12]["date"] = None  # the second e-mail's day not read: it joins the first, one reply where D11 has two
        landlord = copy.deepcopy(rows)
        landlord[14].update(date="2026-09-07", insurer=False, **{"from": "Immo Muster AG"})  # known on the assessment's day, left out
        reminder = copy.deepcopy(rows)
        reminder[13]["date"] = "2026-09-05"  # the insurer wrote again before the assessment: not the episode's outline
        for reason, changed in (("arrival_not_as_in_the_outline", undated), ("another_document_before_the_assessment", landlord),
                                ("another_document_before_the_assessment", reminder)):
            with self.assertRaises(self.cell["Stop"]) as stop:
                self.cell["plan"](SEGMENT_LABELS, {"documents": changed}, pdf)
            self.assertEqual(stop.exception.args, ("cut", reason))

    def test_j_a_file_printed_with_the_newest_on_top_gives_the_cut_from_its_later_pages(self):
        """D11's stored file lists its documents latest first. Read as oldest first, every next document was «older than
        the one it follows», so an enclosure of it: one document of the whole file, and no reply found. Latest first, every
        dated row is its own document; the earlier state is the later pages; and the replies must be followed at once by
        the question they answer, since a date cannot tell their own enclosure from an older document there."""
        pdf = {"name": "Akte.pdf", "extraction": {"pages": 28}}
        rows = REVERSED_TEMPLATE["documents"]
        self.assertTrue(self.cell["newest_first"](rows))
        self.assertFalse(self.cell["newest_first"](TEMPLATE["documents"]))
        self.assertFalse(self.cell["newest_first"](SEGMENT_TEMPLATE["documents"]))
        cut = self.cell["plan"](LABELS, REVERSED_TEMPLATE, pdf)
        self.assertEqual((cut["later"], cut["arrival"], cut["base"]), ([1, 2, 3, 4, 5], [[6, 7], [8, 9, 10]], list(range(11, 29))))
        self.assertEqual((cut["entries"], cut["rows"], cut["newest_first"]), ([None, None], {"base": 10, "arrival": 2, "later": 3}, True))
        self.assertFalse(self.cut["newest_first"])
        self.assertIn("  the file lists its documents latest first: the earlier state is its later pages, what is left out its first",
                      self.cell["plan_lines"](cut, TREE, "0" * 12))
        self.assertNotIn("latest first", "\n".join(self.cell["plan_lines"](self.cut, TREE, "0" * 12)))
        app = FakeApp(template=REVERSED_TEMPLATE)  # the run on it: the earlier state is cut from the later pages
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            receipt = self.cell["diagnose"](app, self.volume.name, TREE, labels_hash(LABELS)[:12], self.cell["sealed"](cut), False, poll=0)
        self.assertEqual((receipt["status"], app.cut, receipt["cut"]), ("done", {"pages": "11-28", "as_of": "2026-09-08", "file": "file_1"},
                                                                       {"point": 3, "pages": 18, "left_out": 5}))
        self.assertIn(("GET", "/api/files/file_1/original?pages=6-7"), app.calls)
        self.assertIn(("GET", "/api/files/file_1/original?pages=8-10"), app.calls)
        between = copy.deepcopy(rows)
        between.insert(5, {"n": None, "date": "2026-07-01", "from": "Immo Muster AG", "page": 10, "file": "Akte.pdf", "insurer": False, "entry": False})
        undated = copy.deepcopy(rows)
        undated[4]["date"] = None  # the earlier reply's day not read: it rides with the later one, one reply where D11 has two
        for reason, changed in (("arrival_not_followed_by_its_question", between), ("arrival_not_as_in_the_outline", undated)):
            with self.assertRaises(self.cell["Stop"]) as stop:
                self.cell["plan"](LABELS, {"documents": changed}, pdf)
            self.assertEqual(stop.exception.args, ("cut", reason))


CONSOLE = Path(__file__).resolve().parents[1] / "deploy" / "databricks" / "rehearse_console.js"
# Runs the console script outside a browser: the stand-in's address as its base, a file as its localStorage, no waiting
# between polls. Prints {result | refused | error, said}.
RUNNER = r"""
const fs = require("fs");
const [file, base, storeFile, mode, arg] = process.argv.slice(2);
require(file);
const read = () => (fs.existsSync(storeFile) ? JSON.parse(fs.readFileSync(storeFile, "utf8")) : {});
const store = { getItem: (k) => (k in read() ? read()[k] : null), setItem: (k, v) => fs.writeFileSync(storeFile, JSON.stringify({ ...read(), [k]: v })) };
const said = [];
const real = globalThis.fetch;
globalThis.fetch = async (url, init = {}) => {
  const line = `${init.method || "GET"} ${String(url).slice(base.length)}`;
  if (process.env.DIE && line.startsWith(process.env.DIE)) process.exit(0);  // the tab is lost before this request leaves
  const response = await real(url, init);
  if (process.env.DIE_AFTER && line.startsWith(process.env.DIE_AFTER)) process.exit(0);  // …or after the app answered it
  return response;
};
(async () => {
  const out = { said };
  try {
    if (mode === "plan") {
      const { labels, template, pdf } = JSON.parse(arg);
      const { plan, sealed } = globalThis.casepathDiagnose.parts;
      try { const cut = plan(labels, template, pdf); out.result = { cut, sealed: await sealed(cut) }; }
      catch (stop) { out.stop = [stop.step, stop.reason]; }
    } else {
      out.result = await globalThis.casepathDiagnose(arg, { base, store, say: (line) => said.push(line), poll: 0, stale: Number(process.env.STALE || 0) });
    }
  } catch (error) { out[{ Refused: "refused", Interrupted: "interrupted" }[error.constructor.name] || "error"] = String(error.message); }
  process.stdout.write(JSON.stringify(out));
})();
"""


class Served:
    """A FakeApp behind HTTP on this machine, for the console script: every request reaches the same stand-in the cell is
    tested with, and is recorded by it in the same words."""

    def __init__(self, app):
        import http.server
        import threading
        fake = self.app = app

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def answer(self, status, body, kind="application/json"):
                data = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def handle_one(self, method):
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                try:
                    upload = re.fullmatch(r"/api/cases/([a-z0-9_]+)/files", self.path)
                    if method == "POST" and upload:
                        assert self.headers.get("Content-Type", "").startswith("multipart/form-data"), "an import is one multipart request"
                        names = re.findall(rb'name="files"; filename="([^"]+)"', body)
                        status, out = fake.upload(upload.group(1), [(n.decode(), b"") for n in names])
                        return self.answer(status, out)
                    if method == "GET" and "/original?" in self.path:
                        return self.answer(200, fake.raw(self.path), "application/pdf")
                    return self.answer(200, fake.call(method, self.path, json.loads(body) if body else None))
                except PermissionError:
                    return self.answer(401, {"detail": "Sign-in required."})
                except AssertionError as error:
                    return self.answer(500, {"detail": str(error)})

            do_GET = lambda self: self.handle_one("GET")
            do_POST = lambda self: self.handle_one("POST")
            do_DELETE = lambda self: self.handle_one("DELETE")

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class ConsoleDiagnoseTests(unittest.TestCase):
    """The console's script (deploy/databricks/rehearse_console.js) is the cell, step for step: against the same stand-in
    it makes the same requests in the same order and gives the same receipt, plan and seal."""

    @classmethod
    def setUpClass(cls):
        cls.cell = runpy.run_path(str(CELL))

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.runner = Path(self.folder.name) / "runner.cjs"
        self.runner.write_text(RUNNER)
        self.cut = self.cell["plan"](LABELS, TEMPLATE, {"name": "Akte.pdf", "extraction": {"pages": 28}})
        self.plan = self.cell["sealed"](self.cut)
        self.phrase = f"diagnose D11 {TREE} {labels_hash(LABELS)[:12]} {self.plan}"

    def node(self, mode, arg, served=None, store="store.json", **env):
        out = subprocess.run(["node", str(self.runner), str(CONSOLE), served.url if served else "http://127.0.0.1:9", str(Path(self.folder.name) / store), mode, arg],
                             capture_output=True, text=True, timeout=120, env={**os.environ, **env})
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout) if out.stdout else None  # None: the tab was lost (DIE, DIE_AFTER)

    def both(self, phrase=None, keep=False, **kw):
        """(the cell's receipt and its stand-in, the console's answer and its stand-in), each on a fresh stand-in."""
        plan = self.cell["sealed"](self.cell["plan"](LABELS, kw.get("template") or TEMPLATE, {"name": "Akte.pdf", "extraction": {"pages": 28}}))
        theirs = FakeApp(**kw)
        with tempfile.TemporaryDirectory() as volume, mock.patch("sys.stdout", new_callable=io.StringIO) as printed:
            receipt = self.cell["diagnose"](theirs, volume, TREE, labels_hash(LABELS)[:12], plan, keep, poll=0)
        self.printed = printed.getvalue()
        served = Served(FakeApp(**kw))
        self.addCleanup(served.close)
        answer = self.node("run", (phrase or f"diagnose D11 {TREE} {labels_hash(LABELS)[:12]} {plan}") + (" keep" if keep else ""), served,
                           store=f"store-{len(os.listdir(self.folder.name))}.json")
        return receipt, theirs, answer, served.app

    def test_a_the_run_is_the_cells_request_for_request_and_its_receipt_the_same(self):
        receipt, theirs, answer, ours = self.both()
        self.assertEqual(answer.get("error"), None)
        self.assertEqual(answer["result"], receipt)
        self.assertEqual(ours.calls, theirs.calls)  # the same requests in the same order
        self.assertEqual((ours.uploads, ours.cut), (theirs.uploads, theirs.cut))
        self.assertEqual(answer["said"][0], self.printed.strip())  # the plan, word for word
        self.assertEqual(json.loads(answer["said"][1]), receipt)
        guard({k: v for k, v in answer["result"].items() if k != "format"})

    def test_b_every_branch_of_the_run_ends_as_the_cell_ends_it(self):
        for kw, keep in (({"auto": "gestartet"}, False), ({"full_usage": 230_000}, False), ({"duplicate": 201, "auto": "gestartet"}, True),
                         ({"duplicate": 201}, False), ({"template": REVERSED_TEMPLATE}, True)):
            receipt, theirs, answer, ours = self.both(keep=keep, **kw)
            self.assertEqual((answer.get("error"), answer["result"], ours.calls), (None, receipt, theirs.calls), sorted(kw))
            if "template" in kw:  # the file printed newest first: the plan says so, word for word as the cell's, and cuts the later pages
                self.assertEqual((answer["said"][0], ours.cut["pages"], receipt["status"]), (self.printed.strip().split("\n{")[0], "11-28", "done"))
                self.assertIn("latest first", answer["said"][0])

    def test_c_the_plan_and_its_seal_are_the_cells_for_entries_and_for_segments(self):
        pdf30 = {"name": "Akte.pdf", "extraction": {"pages": 30}}
        pdf28 = {"name": "Akte.pdf", "extraction": {"pages": 28}}
        between = copy.deepcopy(REVERSED_TEMPLATE["documents"])
        between.insert(5, {"n": None, "date": "2026-07-01", "from": "Immo Muster AG", "page": 10, "file": "Akte.pdf", "insurer": False, "entry": False})
        answer = self.node("plan", json.dumps({"labels": LABELS, "template": {"documents": between}, "pdf": pdf28}))
        self.assertEqual(answer.get("stop"), ["cut", "arrival_not_followed_by_its_question"])
        for labels, template, pdf in ((LABELS, TEMPLATE, pdf28), (SEGMENT_LABELS, SEGMENT_TEMPLATE, pdf30), (LABELS, REVERSED_TEMPLATE, pdf28)):
            cut = self.cell["plan"](labels, template, pdf)
            answer = self.node("plan", json.dumps({"labels": labels, "template": template, "pdf": pdf}))
            self.assertEqual((answer["result"]["cut"], answer["result"]["sealed"]), (cut, self.cell["sealed"](cut)))
        rows = SEGMENT_TEMPLATE["documents"]
        undated, landlord = copy.deepcopy(rows), copy.deepcopy(rows)
        undated[12]["date"] = None
        landlord[14].update(date="2026-09-07", insurer=False, **{"from": "Immo Muster AG"})
        for reason, changed in (("arrival_not_as_in_the_outline", undated), ("another_document_before_the_assessment", landlord)):
            answer = self.node("plan", json.dumps({"labels": SEGMENT_LABELS, "template": {"documents": changed}, "pdf": pdf30}))
            self.assertEqual(answer.get("stop"), ["cut", reason])

    def test_d_the_read_only_mode_names_the_same_phrase_and_makes_only_reads(self):
        theirs = FakeApp()
        with mock.patch("sys.stdout", new_callable=io.StringIO) as printed:
            expected = self.cell["hashes"](theirs)
        served = Served(FakeApp())
        self.addCleanup(served.close)
        answer = self.node("run", "hashes D11", served)
        self.assertEqual((answer["result"], answer["said"][0]), (expected, printed.getvalue().strip()))
        self.assertTrue(answer["said"][0].endswith(f"approval reads: {self.phrase}"))
        self.assertEqual((served.app.calls, {m for m, _ in served.app.calls}), (theirs.calls, {"GET"}))
        self.assertFalse(os.path.exists(Path(self.folder.name) / "store.json"))  # nothing kept: nothing was run

    def test_e_without_its_phrase_or_on_another_build_labels_or_cut_nothing_is_done(self):
        served = Served(FakeApp())
        self.addCleanup(served.close)
        for phrase in ("", "diagnose D11", f"diagnose D11 {TREE}", f"diagnose D12 {TREE} {'0' * 12} {'0' * 12}", f"diagnose D11 {TREE.upper()} {'0' * 12} {'0' * 12}",
                       f"diagnose D11 {TREE} {'0' * 12} {'0' * 12} now", f"diagnose D11 {TREE} {'0' * 12}"):
            self.assertIn("confirm must read", self.node("run", phrase, served)["refused"], phrase)
        self.assertEqual(served.app.calls, [])  # refused before any request
        other = Served(FakeApp(tree="aaaaaaaaaaaa"))
        self.addCleanup(other.close)
        self.assertIn("not the one approved: nothing done", self.node("run", self.phrase, other)["refused"])
        self.assertEqual(other.app.calls, [("GET", "/api/manifest")])
        self.assertIn("labels are not the ones approved", self.node("run", f"diagnose D11 {TREE} {'0' * 12} {self.plan}", served)["refused"])
        self.assertIn("the cut is not the approved plan", self.node("run", f"diagnose D11 {TREE} {labels_hash(LABELS)[:12]} {'0' * 12}", served)["refused"])
        self.assertFalse([path for _, path in served.app.calls if path.endswith("/cut")])
        self.assertFalse(os.path.exists(Path(self.folder.name) / "store.json"))

    def test_f_a_run_made_is_not_made_again_in_the_same_browser_profile(self):
        served = Served(FakeApp())
        self.addCleanup(served.close)
        first = self.node("run", self.phrase, served)["result"]
        again = Served(FakeApp())
        self.addCleanup(again.close)
        answer = self.node("run", self.phrase, again)
        self.assertEqual(answer["result"], first)
        self.assertIn("already run", answer["said"][0])
        self.assertEqual(again.app.calls, [("GET", "/api/manifest"), ("GET", "/api/replay-points"), ("GET", "/api/cases/case_d11/labels")])

    def test_h_a_lost_tab_is_taken_up_where_it_stands_and_no_step_is_repeated(self):
        """The tab is lost at each point of the run where tokens are at stake; the same phrase typed again ends the run
        with the cell's receipt (plus «resumed»), and the stand-in saw one cut, one preparation, one import and its
        second upload, one update: never two."""
        with tempfile.TemporaryDirectory() as volume, mock.patch("sys.stdout", new_callable=io.StringIO):
            expected = self.cell["diagnose"](FakeApp(), volume, TREE, labels_hash(LABELS)[:12], self.plan, False, poll=0)
        once = ("/api/cases/case_d11/cut", "/api/cases/case_base/runs", "/api/cases/case_base/update", "/api/cases/case_base/edits", "/api/cases/case_base")
        for n, lost in enumerate(({"DIE": "GET /api/runs/run_full"},  # waiting for the preparation
                                  {"DIE_AFTER": "POST /api/cases/case_base/runs"},  # the preparation started, its id not kept
                                  {"DIE": "GET /api/files/file_1/original"},  # the preparation recorded, the arrival not begun
                                  {"DIE_AFTER": "POST /api/cases/case_base/files"},  # the arrival went in, nothing kept of it
                                  {"DIE": "GET /api/runs/run_update"},  # waiting for the update
                                  {"DIE_AFTER": "POST /api/cases/case_base/update"},  # the update started, its id not kept
                                  {"DIE": "POST /api/cases/case_base/labels"})):  # the decisions set, the replay not read
            served = Served(FakeApp())
            self.addCleanup(served.close)
            store = f"lost-{n}.json"
            self.assertIsNone(self.node("run", self.phrase, served, store=store, **lost), lost)
            kept = json.loads(json.loads((Path(self.folder.name) / store).read_text())[f"casepath.diagnose/D11-{labels_hash(LABELS)[:12]}"])
            self.assertEqual(kept["status"], "started", lost)
            answer = self.node("run", self.phrase, served, store=store)
            self.assertEqual(answer.get("error"), None, lost)
            # the arrival went in and its answer was never seen: the import is offered again and refused as held (which is
            # the duplicate's test), and what the import answered («auto») stays unknown
            unseen = "POST /api/cases/case_base/files" in lost.values()
            self.assertEqual(answer["result"], {**expected, "resumed": 1, **({"auto": None} if unseen else {})}, lost)
            self.assertIn("no step is repeated", answer["said"][1])
            posts = [path for method, path in served.app.calls if method in ("POST", "DELETE")]
            for path in once:
                self.assertEqual(posts.count(path), 1, (lost, path))  # the cut, the preparation, the update, the decision, the removal: once
            self.assertEqual(served.app.uploads, [["Antwort-1.pdf", "Antwort-2.pdf"], ["Antwort-1.pdf", "Antwort-2.pdf"] if unseen else ["Antwort-1.pdf"]], lost)

    def test_i_a_run_taken_in_another_tab_is_left_alone_and_another_phrase_does_not_take_it_up(self):
        served = Served(FakeApp())
        self.addCleanup(served.close)
        self.assertIsNone(self.node("run", self.phrase, served, DIE="GET /api/runs/run_full"))
        before = list(served.app.calls)
        busy = self.node("run", self.phrase, served, STALE="60000")  # its last sign of life is a moment old
        self.assertIn("being taken in another tab", busy["refused"])
        other = self.node("run", self.phrase + " keep", served)  # the same run, approved with «keep»: another phrase
        self.assertIn("approved with another phrase", other["refused"])
        self.assertFalse([c for c in served.app.calls[len(before):] if c[0] != "GET"])  # neither made anything but reads

    def test_j_a_sign_in_that_ran_out_leaves_the_run_started_and_keeps_its_base_case(self):
        class Expiring(FakeApp):
            def call(self, method, path, body=None):
                if path == "/api/runs/run_full" and not getattr(self, "expired", False):
                    self.expired = True
                    self.calls.append((method, path))
                    raise PermissionError
                return super().call(method, path, body)
        served = Served(Expiring())
        self.addCleanup(served.close)
        first = self.node("run", self.phrase, served)
        self.assertIn("interrupted (http_401): the run stays started", first["interrupted"])
        self.assertNotIn(("DELETE", "/api/cases/case_base"), served.app.calls)  # the base case is kept, to be taken up
        answer = self.node("run", self.phrase, served)
        self.assertEqual((answer["result"]["status"], answer["result"]["resumed"]), ("done", 1))
        self.assertEqual([p for m, p in served.app.calls if m == "POST" and p == "/api/cases/case_base/runs"], ["/api/cases/case_base/runs"])

    def test_k_the_shape_says_why_no_plan_can_be_made_without_a_date_a_name_or_a_text(self):
        served = Served(FakeApp())
        self.addCleanup(served.close)
        answer = self.node("run", "shape D11", served)
        shape = answer["result"]
        self.assertEqual((shape["assessment_point"], shape["pdfs"], shape["pages"], shape["rows_of_this_pdf"], shape["rows_without_page"]), (3, 1, 28, 14, 0))
        self.assertEqual([p["kind"] for p in shape["points"]], ["A1", "A4", "A5", "A7"])
        self.assertEqual(shape["rows"][8:12], [[20, "entry", "=p2", True, "versicherer"], [21, "entry", "p2..p3", False, "kunde"],
                                               [23, "segment", None, False, "kunde"], [24, "entry", "p2..p3", False, "kunde"]])
        # the two replies as the cut needs them: not the insurer's, between the question back and the assessment
        self.assertEqual([d for d in shape["documents"] if d[4] == "p2..p3" and not d[3]], [[21, 3, 2, False, "p2..p3", "entry"], [24, 2, 1, False, "p2..p3", "entry"]])
        text = json.dumps(answer, ensure_ascii=False)
        self.assertIsNone(DATE.search(text))
        for word in ("Akte.pdf", "Lea", "Immo", "bestätigt", "Stromkosten"):
            self.assertNotIn(word, text)
        self.assertEqual({m for m, _ in served.app.calls}, {"GET"})
        self.assertFalse(os.path.exists(Path(self.folder.name) / "store.json"))
        newest = Served(FakeApp(template=REVERSED_TEMPLATE))  # the pilot's shape: the same codes in the same order, and now documents
        self.addCleanup(newest.close)
        seen = self.node("run", "shape D11", newest)["result"]
        self.assertEqual([r[1:] for r in seen["rows"]],
                         [["segment", "=p4", True, "text"], ["segment", "=p3", True, "text"], ["segment", None, False, "text"], ["segment", "p2..p3", False, "text"],
                          ["segment", "p2..p3", False, "text"], ["segment", "=p2", True, "text"], ["segment", None, False, "text"], ["segment", "p1..p2", False, "text"],
                          ["segment", "<p1", False, "text"], ["segment", None, False, "text"], ["segment", "=p1", False, "text"], ["segment", None, False, "text"],
                          ["segment", None, False, "text"], ["segment", None, False, "text"], ["segment", "<p1", False, "text"]])
        self.assertEqual((seen["newest_first"], len(seen["documents"]), shape["newest_first"]), (True, 9, False))
        segments = Served(FakeApp(template=SEGMENT_TEMPLATE))  # senders as written: «text», never the words
        self.addCleanup(segments.close)
        rows = self.node("run", "shape D11", segments)["result"]["rows"]
        self.assertEqual({r[4] for r in rows}, {"text", None})

    def test_l_a_run_stopped_at_the_threshold_is_continued_from_its_kept_base_case_without_a_second_preparation(self):
        """The preparation passed its stop threshold and the run stopped, as it must. Whether the arrival and the update
        are still made on the base case that was kept is a decision of its own, with its own phrase: «continue D11 …»."""
        onward = self.phrase.replace("diagnose", "continue", 1)
        served = Served(FakeApp(full_usage=230_000))
        self.addCleanup(served.close)
        stopped = self.node("run", self.phrase + " keep", served)["result"]
        self.assertEqual((stopped["status"], stopped["stopped"], stopped["kept"]), ("stopped", {"step": "prepare", "reason": "past_the_stop_threshold"}, True))
        self.assertEqual(self.node("run", self.phrase + " keep", served)["result"], stopped)  # its own phrase again: already run
        before = len(served.app.calls)
        answer = self.node("run", onward, served)
        receipt = answer["result"]
        self.assertEqual(answer.get("error"), None)
        self.assertEqual((receipt["status"], receipt["stopped"], receipt["continued_after"], receipt["base"]), ("done", None, "past_the_stop_threshold", "case_base"))
        self.assertIn("the preparation is not made again", answer["said"][1])
        self.assertEqual([r["kind"] for r in receipt["runs"]], ["full", "update"])
        self.assertEqual(receipt["runs"][0], stopped["runs"][0])  # the preparation as it was recorded: not run again
        self.assertEqual((receipt["case"]["next_action"], receipt["duplicate_refused"], receipt["decisions"]), ("a5", True, ["deckung"]))
        made = [path for method, path in served.app.calls[before:] if method != "GET"]
        self.assertEqual(made, ["/api/cases/case_base/files", "/api/cases/case_base/files", "/api/cases/case_base/update", "/api/cases/case_base/edits",
                                "/api/cases/case_base/labels"])  # the arrival, its second upload, one update, the decision, the labels: no cut, no preparation, no removal
        self.assertEqual([p for m, p in served.app.calls if p in ("/api/cases/case_d11/cut", "/api/cases/case_base/runs")],
                         ["/api/cases/case_d11/cut", "/api/cases/case_base/runs"])
        guard({k: v for k, v in receipt.items() if k != "format"})
        self.assertEqual(self.node("run", onward, served)["result"], receipt)  # continued once: a done run is not continued again
        self.assertEqual([p for m, p in served.app.calls if m == "POST" and p == "/api/cases/case_base/update"], ["/api/cases/case_base/update"])

    def test_m_nothing_else_is_continued_and_a_continuation_that_loses_its_tab_is_taken_up(self):
        onward = self.phrase.replace("diagnose", "continue", 1)
        empty = Served(FakeApp())
        self.addCleanup(empty.close)
        self.assertIn("no run was made here", self.node("run", onward, empty, store="none.json")["refused"])
        self.assertEqual({m for m, _ in empty.app.calls}, {"GET"})
        done = self.node("run", self.phrase, empty, store="done.json")["result"]
        self.assertEqual(self.node("run", onward, empty, store="done.json"), {"said": [], "refused": "the run made here did not stop at the preparation's threshold on this plan: nothing done"}, done["status"])
        gone = Served(FakeApp(full_usage=230_000))  # stopped at the threshold, its base case not kept: it was deleted
        self.addCleanup(gone.close)
        self.node("run", self.phrase, gone, store="gone.json")
        self.assertIn("base case was not kept", self.node("run", onward, gone, store="gone.json")["refused"])
        lost = Served(FakeApp(full_usage=230_000))
        self.addCleanup(lost.close)
        self.node("run", self.phrase + " keep", lost, store="lost.json")
        self.assertIsNone(self.node("run", onward, lost, store="lost.json", DIE="GET /api/runs/run_update"))  # the tab is lost while the update runs
        answer = self.node("run", onward, lost, store="lost.json")
        self.assertEqual((answer["result"]["status"], answer["result"]["continued_after"], answer["result"]["resumed"]), ("done", "past_the_stop_threshold", 1))
        posts = [p for m, p in lost.app.calls if m == "POST"]
        self.assertEqual((posts.count("/api/cases/case_base/update"), posts.count("/api/cases/case_base/runs"), lost.app.uploads),
                         (1, 1, [["Antwort-1.pdf", "Antwort-2.pdf"], ["Antwort-1.pdf"]]))

    def test_n_the_detail_of_the_base_case_is_codes_only_and_read_only(self):
        served = Served(FakeApp())
        self.addCleanup(served.close)
        self.assertIn("no run with a base case was made here", self.node("run", "detail D11", served)["refused"])
        self.node("run", self.phrase + " keep", served)
        before = len(served.app.calls)
        answer = self.node("run", "detail D11", served)
        detail = answer["result"]
        self.assertEqual((detail["base"], detail["run"], detail["next_action"], detail["gaps"]), ("case_base", "done", "a5", 0))
        self.assertEqual(detail["questions"], [
            {"row": 0, "state": "beantwortet", "about": ["hinterlegung"], "points": [], "intent": "weiter_zahlen", "taken": False, "of_the_account": False, "request": None},
            {"row": 0, "state": "bedingt", "about": ["hinterlegung"], "points": [], "intent": "hinterlegen", "taken": False, "of_the_account": False, "request": None},
            {"row": 0, "state": "pruefen", "about": ["schadenersatz"], "points": [], "intent": "ersatz", "taken": False, "of_the_account": False, "request": None}])
        self.assertEqual((detail["residual"], detail["blocking"], detail["proposal"]),
                         (["residual:claim.0"], [["decision", "empfehlung"]], ["frist_beseitigung", "schadenersatz"]))
        guard({k: v for k, v in detail.items()})  # ids, counts and enums only, by the receipts' own guard
        text = json.dumps(answer, ensure_ascii=False)
        self.assertIsNone(DATE.search(text))
        for word in ("Stromkosten", "Bautrockner", "Lücke", "Verneinung", "Brief ohne", "Akte.pdf", "CHF"):
            self.assertNotIn(word, text)
        self.assertEqual({m for m, _ in served.app.calls[before:]}, {"GET"})

    def test_g_the_script_calls_only_the_page_it_is_pasted_into_and_names_no_address_or_identity(self):
        text = CONSOLE.read_text()
        self.assertNotRegex(text, r"https?://")  # no address: relative requests on the page's own origin
        self.assertIn('credentials: "same-origin"', text)
        for word in ("Authorization", "Bearer", "token =", "cookie", "X-Forwarded"):
            self.assertNotIn(word, text)


if __name__ == "__main__":
    unittest.main()
