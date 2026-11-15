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
        bad["points"] += [{"n": 1, "date": "2025-04-01", "kind": "A13", "to": "nachbar", "documents": ["fotos", "fotos", "Other:Liste"],
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

    def test_i_deleting_a_case_deletes_its_labels(self):
        desk = phased.Desk()
        try:
            case_id = desk.prepare(self.case)
            desk.store.save_labels(case_id, {**points.check(self.labels), "case": case_id}, "test")
            desk.store.delete_case(case_id, "test")
            self.assertEqual(desk.store.list_labels(), [])
        finally:
            desk.close()


if __name__ == "__main__":
    unittest.main()
