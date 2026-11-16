"""The insurer's decision points replayed from one stored run (casepath/quality/points.py): the labels format, the template
for whoever writes the labels, the replay table through the API and the command line, content-free unless detail is
asked for, and how long it takes. Scripted and model-free.

tests/fixtures/replay/mandate_course.json: a synthetic tenancy defect over twenty-one documents (first request, a reminder
with a deadline, the reply, a phone note, the assessment, a mandate, the firm's reports, two fee notes and their payment,
an offer accepted by phone, the payout, its confirmation, the closing), with labels for ten of the insurer's actions."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import re
import tempfile
import time
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from casepath.config import load_settings
from casepath.quality import points
from casepath.web.app import create_app
from tests import phased

KORRESPONDENZ = "k-know-seed-mold-korrespondenz--mietmangel-handler"
DATES = re.compile(r"\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{2,4}")
CONTENT = ("Aebi", "Aarhof", "Weber", "Graf", "Lindenweg", "Bern", "CHF", "2'400", "Schimmel", "Mietvertrag für", "PRK311")


def made_up(case="case_made_up_0001"):
    """A labels file for a made-up case: two decisions, a first request, a phone note and an assessment."""
    return {"format": "casepath.labels/1", "dossier": "D3", "case": case,
            "decisions": [{"fact": "deckung", "value": "bestätigt", "from": "2025-03-01"}],
            "points": [{"n": 2, "date": "2025-03-05", "kind": "A2", "to": "kunde", "documents": [], "questions": 0, "date_set": None, "internal": True},
                       {"n": 1, "date": "2025-01-10", "kind": "A1", "to": "kunde", "documents": ["mietvertrag", "fotos", "other:schadenliste"],
                        "questions": 2, "date_set": "2025-01-31", "internal": False},
                       {"n": 3, "date": "2025-03-07", "kind": "A5", "to": "kunde", "documents": [], "questions": 0, "date_set": None, "internal": False}]}


class LabelsFormatTests(unittest.TestCase):
    def test_a_made_up_labels_file_is_read_in_time_order(self):
        labels = points.check(made_up())
        self.assertEqual([p["n"] for p in labels["points"]], [1, 2, 3])
        process = {"facts": [{"id": "deckung", "type": "enum", "values": ["offen", "bestätigt", "abgelehnt"], "handler_only": True},
                             {"id": "mangel_seit", "type": "date"}],
                   "documents": [{"id": "mietvertrag"}, {"id": "fotos"}], "action_kinds": {f"A{i}": {} for i in range(13)}}
        self.assertEqual(points.check(made_up(), process, "case_made_up_0001")["dossier"], "D3")

    def test_every_problem_is_named_at_once(self):
        bad = made_up()
        bad.update(format="casepath.labels/0", dossier="Nina Aebi", extra=1)
        bad["decisions"] += [{"fact": "mangel_seit", "value": "2024-10", "from": "2025-02-01"}, {"fact": "deckung", "value": "vielleicht", "from": "x"}]
        bad["points"] += [{"n": 1, "date": "2025-04-01", "kind": "A14", "to": "nachbar", "documents": ["fotos", "fotos", "Other:Liste"],
                           "questions": -1, "date_set": "2025-03-01", "internal": "nein"},
                          {"n": 5, "date": "2025-04-02", "kind": "A2", "to": "kanzlei", "documents": ["k-unbekannt"], "questions": 0,
                           "date_set": "2025-03-01", "internal": False}]
        process = {"facts": [{"id": "deckung", "type": "enum", "values": ["offen", "bestätigt", "abgelehnt"], "handler_only": True},
                             {"id": "mangel_seit", "type": "date"}], "documents": [{"id": "mietvertrag"}, {"id": "fotos"}], "action_kinds": {}}
        with self.assertRaises(points.LabelsError) as caught:
            points.check(bad, process, "case_other")
        problems = caught.exception.problems
        for part in ("unknown fields ['extra']", "format: must be", "dossier: a short pseudonym", "case: these labels are for",
                     "decisions[1].fact: 'mangel_seit' is not a decision", "decisions[2].from", "decisions[2].value",
                     "points[3].n", "points[3].kind", "points[3].to", "points[3].documents: a list of need ids, each once", "points[3].questions",
                     "points[3].date_set: before", "points[3].internal", "points[4].documents: 'k-unbekannt'", "points[4].date_set: before",
                     "points[4].internal: true or false; a phone note (A2) is internal"):
            self.assertTrue(any(part in p for p in problems), part)
        self.assertFalse(any(p.startswith(("points[0]", "points[1]", "points[2]")) for p in problems))  # other:<word> and the rest are fine

    def test_documents_may_name_anything_else_as_other_and_a_point_needs_every_field(self):
        labels = made_up()
        labels["points"][1]["documents"] = ["other:Mietzinsquittungen"]
        with self.assertRaises(points.LabelsError):
            points.check(labels)  # lower case, one word
        labels["points"][1]["documents"] = ["other:mietzinsquittungen"]
        points.check(labels)
        del labels["points"][0]["internal"]
        with self.assertRaises(points.LabelsError):
            points.check(labels)

    def test_the_expanded_truth_is_optional_and_checked_where_it_is_given(self):
        """A labels file of the narrow score stays valid; a point may add how many questions the letter answered, the dates
        it stated, and a verdict on its substance with the role of whoever gave it."""
        labels = made_up()
        labels["points"][2].update(answered=1, deadlines=[{"id": "anfechtung", "date": "2025-04-07"}, {"id": "verjaehrung", "date": "prüfen"}],
                                   substantive={"by_role": "jurist", "verdict": "incomplete", "questions": ["correct", "incomplete"]})
        self.assertEqual(points.check(labels)["points"][2]["answered"], 1)
        bad = copy.deepcopy(labels)
        bad["points"][2].update(answered=-1, deadlines=[{"id": "Frist", "date": "bald"}], substantive={"by_role": "developer", "verdict": "fine"})
        bad["points"][0]["extra"] = True
        with self.assertRaises(points.LabelsError) as caught:
            points.check(bad)
        problems = caught.exception.problems
        for part in ("points[0]: n, date, kind", "points[2].answered", "points[2].deadlines: 'Frist' needs a date",
                     "points[2].deadlines: 'Frist' is not a deadline", "points[2].substantive: by_role"):
            self.assertTrue(any(part in p for p in problems), (part, problems))
        process = {"facts": [{"id": "deckung", "type": "enum", "values": ["offen", "bestätigt", "abgelehnt"], "handler_only": True}],
                   "documents": [{"id": "mietvertrag"}, {"id": "fotos"}], "action_kinds": {f"A{i}": {} for i in range(13)},
                   "deadlines": [{"id": "anfechtung"}]}
        with self.assertRaises(points.LabelsError) as caught:
            points.check(labels, process, "case_made_up_0001")
        self.assertEqual([p for p in caught.exception.problems if "deadlines" in p], ["points[2].deadlines: 'verjaehrung' is not a deadline of this process"])


class AcceptRuleTests(unittest.TestCase):
    """The rules of the expanded acceptance, declared before any result (quality/points.py)."""

    def test_the_recipient_is_read_from_the_forms_addressee_line(self):
        self.assertEqual(points.recipients("Kundschaft"), ["kunde"])
        self.assertEqual(points.recipients("Gegenpartei, als Entwurf zuerst an die Kundschaft"), ["gegenpartei", "kunde"])
        self.assertEqual(points.recipients("Anwaltskanzlei"), ["kanzlei"])
        self.assertEqual(points.recipients(None), ["andere"])

    def test_other_is_hit_by_a_word_that_starts_with_it_and_a_need_by_its_line_or_its_whole(self):
        lines = [{"key": "residual:claim.0", "line": "Belege zu: Stromkosten für den Bautrockner"},
                 {"key": "residual:document.maengelruege", "line": "Mängelrüge"}]
        process = {"documents": [{"id": KORRESPONDENZ, "includes": ["maengelruege"]}, {"id": "maengelruege"}]}
        verdict = lambda wanted: points.residual_verdict(wanted, lines, process)
        self.assertEqual(verdict(["other:stromkosten", "maengelruege"]),
                         {"label": 2, "hits": ["other:stromkosten", "maengelruege"], "missed": [], "extras": [], "ok": True})
        self.assertEqual(verdict(["other:strom"])["hits"], ["other:strom"])  # the start of a word
        loud = [{"key": "residual:claim.0", "line": "BELEGE ZU: STROMKOSTEN"}]
        self.assertEqual(points.residual_verdict(["other:stromkosten"], loud, process)["hits"], ["other:stromkosten"])  # case-folded
        self.assertEqual(verdict(["other:kosten"])["missed"], ["other:kosten"])  # inside a word is not a hit
        self.assertEqual(verdict(["other:stromkosten"])["extras"], ["residual:document.maengelruege"])
        self.assertEqual(verdict([KORRESPONDENZ])["hits"], [])  # a whole is not asked by one of its parts
        whole = points.residual_verdict(["maengelruege"], [{"key": f"residual:document.{KORRESPONDENZ}", "line": "Korrespondenz"}], process)
        self.assertEqual((whole["hits"], whole["extras"]), (["maengelruege"], []))  # a part named inside an asked whole is asked

    def test_a_stated_date_counts_exactly_and_a_wrong_one_is_critical(self):
        deadline = {"kind": "deadline", "key": "anfechtung", "value": "2026-12-10", "origin": "law"}
        text = "Die Frist für die Anfechtung endet am 10.12.2026."
        right = points.deadline_check({"deadlines": [{"id": "anfechtung", "date": "2026-12-10"}]}, [deadline], text)
        self.assertEqual((right["stated"], right["right"], right["ok"], right["critical"]), (1, 1, True, 0))
        wrong = points.deadline_check({"deadlines": [{"id": "anfechtung", "date": "2026-12-11"}]}, [deadline], text)
        self.assertEqual((wrong["wrong"], wrong["ok"], wrong["critical"]), (["anfechtung"], False, 1))  # one day off: no tolerance
        unstated = points.deadline_check({"deadlines": [{"id": "anfechtung", "date": "2026-12-10"}]}, [deadline], "Kein Datum.")
        self.assertEqual((unstated["missing"], unstated["ok"]), (["anfechtung"], False))
        self.assertIsNone(points.deadline_check({}, [deadline], text)["ok"])  # no label: nothing to judge

    def test_who_gave_a_verdict_decides_whether_substance_counts_as_verified(self):
        shown = {"items": [{"kind": "customer_question", "value": "Q?", "answer": "A.", "item_id": "customer_question:0"}],
                 "action": {"action": "A5", "form": "A5"}}
        drafted = {"form": "A5", "to": "Kundschaft", "needs": [], "parts": ["{zu_fragen}"], "text": "Brief ohne Lücke."}
        point = {"date": "2025-03-07", "to": "kunde", "documents": []}
        status = lambda role: points.accept({**point, "substantive": {"by_role": role, "verdict": "correct"}}, shown, drafted, [], {})["substantive"]["status"]
        self.assertEqual([status("jurist"), status("process_owner"), status("developer")], ["verified", "verified", "developer_check"])
        out = points.accept(point, shown, drafted, [{"fact": "aussichten", "value": "genügend", "from": "2025-03-07"}], {})
        self.assertEqual((out["substantive"]["status"], out["substantive"]["present"], out["authority"]), ("unverified", True,
                         {"needs": ["aussichten"], "missing": [], "ok": True}))
        self.assertEqual((out["questions"]["beantwortet"], out["questions"]["offen"]), (1, 0))
        closed = points.accept(point, shown, {**drafted, "parts": ["{im_fall}"]}, [], {})  # a form that answers no question
        self.assertEqual((closed["questions"]["offen"], closed["authority"]["missing"]), (1, ["aussichten"]))
        nothing = points.accept(point, shown, {**drafted, "text": None}, [], {})
        self.assertEqual((nothing["draft"], nothing["recipient"], nothing["substantive"]["present"]), (False, None, False))


class CoverageTests(unittest.TestCase):
    def test_whether_the_document_answered_had_an_entry_an_enclosure_counts_with_its_letter(self):
        from datetime import date
        from casepath.quality import asof
        from tests.test_asof import entry, file_of
        segments = [{"first_page": 1, "last_page": 1, "date": "10.01.2025", "sender": "Kundin"},
                    {"first_page": 2, "last_page": 2, "date": "01.04.2021", "sender": "Vermieterin"},  # the lease, enclosed
                    {"first_page": 3, "last_page": 3, "date": "20.03.2025", "sender": "Vermieterin"},  # a letter the reader gave no entry
                    {"first_page": 4, "last_page": 4, "date": "25.03.2025", "sender": "Protekta Rechtsschutz"}]
        files = [file_of(4, segments)]
        entries = [entry(1, 1, "2025-01-10", "kunde", "versicherer"), entry(2, 4, "2025-03-25", "versicherer", "kunde")]
        run = {"id": "r", "result": {"process": {"facts": []}, "facts": [], "documents": [], "record": {"entries": entries}}}
        early = points.coverage(entries, files, asof.rebuild(run, files, "2025-02-01"), date(2025, 2, 1))
        self.assertEqual((early["incoming"], early["own"]), (True, None))
        late = points.coverage(entries, files, asof.rebuild(run, files, "2025-03-25"), date(2025, 3, 25))
        self.assertEqual((late["incoming"], late["own"]), (False, True))  # what was answered had no entry: a gap of the reading


class ReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case = phased.load("mandate_course")
        cls.desk = phased.Desk()
        cls.case_id = cls.desk.prepare(cls.case)  # one scripted run of the whole file
        cls.labels = {**copy.deepcopy(cls.case["labels"]), "case": cls.case_id}
        app = create_app(load_settings({"CASEPATH_DATA_DIR": cls.desk.directory.name, "CASEPATH_DEV_USER": "dev"}), model_factory=lambda: None,
                         store=cls.desk.store, catalogue=cls.desk.catalogue)
        cls.app, cls.client = app, TestClient(app)
        cls.saved = cls.client.post(f"/api/cases/{cls.case_id}/labels", json=cls.labels)
        cls.table = cls.client.get("/api/replay-points").json()
        cls.rows = {r["n"]: r for r in cls.table["rows"]}

    @classmethod
    def tearDownClass(cls):
        cls.app.state.runs.shutdown()
        cls.desk.close()

    def test_a_the_labels_are_checked_against_the_cases_process_and_kept_in_the_store(self):
        self.assertEqual(self.saved.status_code, 201, self.saved.text)
        self.assertEqual(self.client.get(f"/api/cases/{self.case_id}/labels").json()["dossier"], "S1")
        wrong = copy.deepcopy(self.labels)
        wrong["points"][0]["documents"].append("unterlagen")
        refused = self.client.post(f"/api/cases/{self.case_id}/labels", json=wrong)
        self.assertEqual(refused.status_code, 422)
        self.assertIn("'unterlagen' is not a need of this process", refused.text)
        self.assertEqual(self.client.get(f"/api/cases/{self.case_id}/labels").json(), points.check(self.labels))  # the first stays

    def test_b_the_template_lists_the_documents_in_time_order_with_the_insurers_own_marked(self):
        shown = self.client.get(f"/api/cases/{self.case_id}/labels-template").json()
        self.assertIn("INSIDE THE INSURER ONLY", shown["note"])
        days = [d["date"] for d in shown["documents"]]
        self.assertEqual(days, sorted(days))
        own = [(d["n"], d["action"]) for d in shown["documents"] if d["insurer"]]
        self.assertEqual([a for _, a in own], [["A1"], ["A6"], ["A2"], ["A5"], ["A10"], ["A11"], ["A2"], ["A11"], ["A11"], ["A12"]])
        self.assertEqual([d["page"] for d in shown["documents"] if d.get("entry") is False], [5, 6, 7])  # the enclosures, without an entry
        skeleton = shown["labels"]
        self.assertEqual([(p["date"], p["kind"], p["internal"]) for p in skeleton["points"]],
                         [(p["date"], p["kind"], p["internal"]) for p in self.case["labels"]["points"]])  # minutes, not hours
        self.assertIn(KORRESPONDENZ, [n["id"] for n in shown["needs"]])
        self.assertEqual(shown["decisions"]["deckung"], ["offen", "bestätigt", "abgelehnt"])
        lines = points.template_lines(shown)
        self.assertTrue(lines[0].startswith("INSIDE THE INSURER ONLY"))
        self.assertTrue(any(line.startswith("*   2  2025-01-10  versicherer → kunde  anforderung") for line in lines))

    def test_c_each_point_is_compared_with_what_casepath_prepared_on_its_day(self):
        first = self.rows[1]
        self.assertEqual((first["kind"], first["kind_ok"], len(first["documents"]["hits"]), first["documents"]["extras"], first["date"]["diff"]),
                         ("A1", True, 4, [], 0))
        self.assertTrue(first["ready"])
        self.assertEqual((self.rows[2]["kind"], self.rows[2]["date"]["diff"], self.rows[2]["ready"]), ("A6", 2, True))  # silence after the request
        self.assertEqual([self.rows[n]["kind"] for n in range(5, 11)], ["A10", "A11", "A2", "A11", "A11", "A12"])
        self.assertTrue(all(self.rows[n]["ready"] for n in (5, 6, 7, 8, 9, 10)))

    def test_d_a_miss_carries_its_diagnosis(self):
        letter = self.rows[4]  # the assessment also asked the rent payments, which wait for an open fact
        self.assertEqual((letter["kind_ok"], letter["ready"], letter["documents"]["missed"], letter["documents"]["extras"]),
                         (True, False, ["mietzinszahlungen"], [KORRESPONDENZ]))
        why = letter["why"]
        self.assertEqual((why["stage"], why["rule"]), ("beurteilen", "stage:beurteilen"))
        self.assertEqual(why["documents"]["missed"], {"mietzinszahlungen": "later:depends"})
        self.assertIn("streit_mietzins", why["waiting"])
        self.assertEqual(why["facts"]["deckung"], "bestaetigt")
        self.assertEqual(why["rebuilt"]["undecided"], ["weiteres_vorgehen"])  # quoted from the phone note and the later reply
        self.assertEqual((why["entry"]["incoming"], why["entry"]["own"]), (True, True))
        call = self.rows[3]  # the handler's phone note: internal, counted apart
        self.assertEqual((call["internal"], call["kind"], call["ready"], call["why"]["rule"]), (True, "A5", False, "stage:beurteilen"))

    def test_e_the_summary_table(self):
        s = self.table["summary"]
        self.assertEqual((s["points"], s["letters"], s["internal"], s["ready"], s["ready_internal"]), (10, 8, 2, 7, 1))
        self.assertEqual(s["kind_right"], {"A1": [1, 1], "A5": [1, 1], "A6": [1, 1], "A10": [1, 1], "A11": [3, 3], "A12": [1, 1]})
        self.assertEqual(s["kind_right_internal"], {"A2": [1, 2]})
        self.assertEqual((s["documents"], s["dates"]), ({"asked": 8, "of": 9, "extras": 1}, {"within": 3, "of": 3}))
        self.assertEqual(self.table["model_calls"], 0)
        self.assertLess(self.table["seconds"], 10)

    def test_f_the_table_is_content_free_unless_detail_is_asked(self):
        text = json.dumps(self.table, ensure_ascii=False)
        self.assertIsNone(DATES.search(text), DATES.search(text) and DATES.search(text).group(0))
        for word in CONTENT:
            self.assertNotIn(word, text)
        self.assertEqual(self.table["lines"][2], "S1 " + self.case_id + " #3 A2 (internal) → A5 wrong · date - · not ready")
        self.assertTrue(self.table["lines"][3].startswith("   why: stage beurteilen · rule stage:beurteilen · waiting "))
        detail = self.client.get("/api/replay-points", params={"detail": "true"}).json()
        inside = json.dumps(detail, ensure_ascii=False)
        self.assertIn("2025-04-04", inside)  # the dates, inside only
        self.assertIn("Kann ich den Mietzins schon jetzt reduzieren?", inside)  # what is open, in its own words
        self.assertEqual(self.client.get("/api/replay-points", params={"case": "case_none"}).json()["rows"], [])

    def test_g_the_command_line_reads_and_keeps_labels_and_prints_the_table(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, {"CASEPATH_DATA_DIR": self.desk.directory.name}):
            path = Path(folder) / "labels.json"
            path.write_text(json.dumps(self.labels, ensure_ascii=False))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                points.main(["--labels", str(path), "--case", self.case_id])
            printed = out.getvalue()
            self.assertIn("ready (letters) 7/8 (88 %)", printed)
            self.assertIn("computed in", printed)
            self.assertIsNone(DATES.search(printed))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                points.template_main([self.case_id])
            self.assertTrue(out.getvalue().startswith("INSIDE THE INSURER ONLY"))

    def test_h_seven_labelled_files_in_well_under_a_minute(self):
        desk = phased.Desk()
        try:
            for _ in range(7):
                case_id = desk.prepare(self.case)
                desk.store.save_labels(case_id, {**points.check(self.labels), "case": case_id}, "test")
            started = time.perf_counter()
            out = points.table(desk.store, desk.catalogue)
            self.assertEqual((out["summary"]["points"], out["summary"]["ready"]), (70, 49))
            self.assertLess(time.perf_counter() - started, 60)
        finally:
            desk.close()

    def test_i_a_labelled_cut_of_a_labelled_case_is_not_counted_with_its_dossier(self):
        """A diagnostic that keeps its base case leaves a cut of the dossier, labelled to replay one point. The whole table
        counts the dossier once; the cut is replayed when it is named."""
        desk = phased.Desk()
        try:
            case_id = desk.prepare(self.case)
            desk.store.save_labels(case_id, {**points.check(self.labels), "case": case_id}, "test")
            before = points.table(desk.store, desk.catalogue)
            cut = desk.prepare(self.case)
            for f in desk.store.list_files(cut):
                desk.store.update_extraction(f["id"], {**f["extraction"], "cut_of": {"case": case_id, "file": "file_x", "as_of": None}})
            desk.store.save_labels(cut, {**points.check(self.labels), "case": cut}, "test")
            whole = points.table(desk.store, desk.catalogue)
            self.assertEqual((whole["summary"]["points"], whole["cut_copies"], {r["case"] for r in whole["rows"]}),
                             (before["summary"]["points"], 1, {case_id}))
            self.assertIn("left out: 1 labelled case(s) cut from another labelled case (a diagnostic's kept base case; replayed when named)", whole["lines"])
            named = points.table(desk.store, desk.catalogue, {cut})
            self.assertEqual(({r["case"] for r in named["rows"]}, named["cut_copies"]), ({cut}, 0))
            self.assertEqual(before["cut_copies"], 0)
            self.assertNotIn("left out", "\n".join(before["lines"]))
        finally:
            desk.close()

    def test_j_the_narrow_score_is_named_and_the_stated_limits_are_repeated(self):
        lines = self.table["lines"]
        self.assertIn("historische Handlung (eng; Wiedervorlage ±7 Tage, keine Frist-Toleranz): Handlungsart 8/8 · bereit 7/8", lines)
        self.assertIn(points.STATED_LIMITS, lines)
        for part in ("16/35", "11 of them", "7/50", "not comparable", "28 of the 50", "not independent validation"):
            self.assertIn(part, points.STATED_LIMITS)
        self.assertEqual(self.table["summary"]["narrow"], {"kind_ok": 8, "ready": 7, "of": 8})
        accept = self.table["summary"]["accept"]
        self.assertEqual((accept["of"], accept["no_draft"]), (8, 3))  # the payments have no letter of CasePath's (the closing has its short one, process/live.py)
        # the assessment's form waits for the cover decision (labelled) and the prospects (not labelled): «decision pending»
        self.assertEqual(self.rows[4]["accept"]["authority"], {"needs": ["deckung", "aussichten"], "missing": ["aussichten"], "ok": False})
        self.assertNotIn("accept", self.rows[3])  # a phone note has no letter

    def test_i_deleting_a_case_deletes_its_labels(self):
        desk = phased.Desk()
        try:
            case_id = desk.prepare(self.case)
            desk.store.save_labels(case_id, {**points.check(self.labels), "case": case_id}, "test")
            desk.store.delete_case(case_id, "test")
            self.assertEqual(desk.store.list_labels(), [])
        finally:
            desk.close()


class ReplyAssessmentTests(unittest.TestCase):
    """S-D11A (tests/fixtures/replay/reply_assessment.json), the shape of D11 with its four labelled points and the expanded
    truth of the assessment: answered 1, the electricity-cost receipts as the one document asked, no verdict on substance.
    Pinned on the integrated episode; each change against the product before its slices is named where it is pinned."""

    @classmethod
    def setUpClass(cls):
        cls.case = phased.load("reply_assessment")
        cls.desk = phased.Desk()
        cls.case_id = cls.desk.prepare(cls.case)
        labels = {**copy.deepcopy(cls.case["labels"]), "case": cls.case_id}
        cls.desk.store.save_labels(cls.case_id, points.check_case(cls.desk.store, cls.desk.catalogue, cls.case_id, labels), "test")
        cls.table = points.table(cls.desk.store, cls.desk.catalogue, accept_lines=True)
        cls.rows = {r["n"]: r for r in cls.table["rows"]}

    @classmethod
    def tearDownClass(cls):
        cls.desk.close()

    def test_a_the_narrow_score_of_the_four_points(self):
        self.assertEqual([(r["label"], r["kind"], r["ready"]) for r in self.table["rows"]],
                         [("A1", "A1", False), ("A4", "A4", True), ("A5", "A5", False), ("A7", "A7", True)])  # the partial answer gets its question back
        self.assertEqual(self.rows[3]["documents"]["missed"], ["other:stromkosten"])  # the narrow rule never hits another document
        self.assertIn("historische Handlung (eng; Wiedervorlage ±7 Tage, keine Frist-Toleranz): Handlungsart 4/4 · bereit 2/4", self.table["lines"])

    def test_b_the_assessment_is_accepted_by_its_own_rules(self):
        accept = self.rows[3]["accept"]
        self.assertEqual((accept["form"], accept["draft"], accept["recipient"]["ok"]), ("A5", True, True))
        # slice A answers by intent (before: keyword answers, 1 answered and 2 open): Q1 answered, Q2 and Q3 conditional
        self.assertEqual({k: accept["questions"][k] for k in ("beantwortet", "bedingt", "offen", "pruefen", "label", "ok")},
                         {"beantwortet": 1, "bedingt": 2, "offen": 0, "pruefen": 0, "label": 1, "ok": True})
        # slice A asks the receipts of the claimed cost, not the stage's generic list (before: the Knowledge correspondence
        # and «quittungen» as extras, the receipts missed); slice C splits the first request's combined ask into its items
        # (C10a), and the reply delivered the lease and the correspondence only, so the list of damaged items and the
        # description of the facts are asked again (r2.2, r2.3): the remainder, never the whole list
        self.assertEqual(accept["residual"], {"label": 1, "hits": ["other:stromkosten"], "missed": [], "ok": False,
                                              "extras": ["residual:request.r2.2", "residual:request.r2.3"]})
        self.assertEqual(accept["substantive"], {"present": True, "gaps": 0, "status": "unverified", "verdict": None})  # before: 4 gaps
        self.assertEqual(accept["authority"]["missing"], ["aussichten"])  # the labels hold no prospects decision: «decision pending»
        self.assertEqual(accept["deadlines"]["label"], 0)
        line = next(x for x in self.table["lines"] if x.startswith("   accept:") and "residual 1/1" in x)
        self.assertIn("+2 extra residual:request.r2.2,residual:request.r2.3", line)
        self.assertIn("decision pending (aussichten)", line)
        s = self.table["summary"]["accept"]
        # no point's residual is as labelled now (before: one, the A7's): every letter after the reply carries the two open
        # items of the first request (C10a), the A7 also the claim's receipts; the substance is present on all four (before 3)
        self.assertEqual((s["recipient"], s["questions"], s["residual"], s["present"], s["decision_pending"]), (4, [1, 1], 0, 4, 1))

    def test_c_the_exposure_to_the_whole_file(self):
        self.assertEqual([self.rows[n]["exposure"]["request_uncited"] for n in (1, 2, 3, 4)], [1, 1, 1, 1])
        self.assertEqual(self.rows[1]["exposure"]["parties_named_later"], 1)
        self.assertEqual(self.table["summary"]["exposure"]["points"], 4)
        self.assertTrue(any(x.startswith("exposure to the whole-file brief (not an effect): 4 of 4 points · parties named later 1")
                            for x in self.table["lines"]))
        self.assertIn("whole-file brief parties_named_later 1 request_uncited 1", self.table["lines"][2])  # the first point's diagnosis

    def test_d_a_table_before_and_after_names_each_point_whose_kind_or_ready_changed(self):
        after = copy.deepcopy(self.table)
        after["rows"][1].update(kind="A5", kind_ok=False, ready=False)  # the question back: a different action prepared
        after["rows"][2]["ready"] = True
        after["summary"]["ready"] = 2
        self.assertEqual(points.change_lines(self.table, after), [
            f"S-D11A {self.case_id} #2 A4: kind A4 → A5, ready yes → no",
            f"S-D11A {self.case_id} #3 A5: kind A5 → A5, ready no → yes",
            "2 of 4 points changed kind or ready · ready (letters) 2/4 before, 2/4 after"])
        self.assertEqual(points.change_lines(self.table, self.table)[-1], "0 of 4 points changed kind or ready · ready (letters) 2/4 before, 2/4 after")
        with tempfile.TemporaryDirectory() as folder:
            paths = [Path(folder) / "before.json", Path(folder) / "after.json"]
            for path, out in zip(paths, (self.table, after)):
                path.write_text(json.dumps(out, ensure_ascii=False))
            printed = io.StringIO()
            with contextlib.redirect_stdout(printed):
                points.main(["--compare", *map(str, paths)])  # no store: two saved tables
        self.assertEqual(printed.getvalue().splitlines(), points.change_lines(self.table, after))

    def test_e_the_command_line_prints_each_acceptance_on_request_and_stays_content_free(self):
        with mock.patch.dict(os.environ, {"CASEPATH_DATA_DIR": self.desk.directory.name}):
            plain, accepted = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(plain):
                points.main(["--case", self.case_id])
            with contextlib.redirect_stdout(accepted):
                points.main(["--case", self.case_id, "--accept"])
        self.assertNotIn("   accept:", plain.getvalue())
        self.assertEqual(accepted.getvalue().count("   accept:"), 4)
        for text in (accepted.getvalue(), json.dumps(self.table, ensure_ascii=False)):
            self.assertIsNone(DATES.search(text))
            self.assertFalse([w for w in ("Steiner", "Sonnmatt", "Brunnmatt", "Lerchenweg", "Stromkosten für", "CHF") if w in text])


if __name__ == "__main__":
    unittest.main()
