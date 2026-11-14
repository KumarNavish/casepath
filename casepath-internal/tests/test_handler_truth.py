"""The handler's truth of a benchmark suite: saved results scored, and the truth checked against the rules (no model)."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from casepath.quality import handler
from casepath.quality.benchmark import FORMAT, BenchmarkError, load_suite
from casepath.quality.evaluate import main as evaluate_main


def letter(title, kind="letter"):
    return {"kind": kind, "title": title, "date": "2026-03-02", "sender": "Mia Muster\nBeispielweg 1\n3000 Bern",
            "recipient": "Max Beispiel\nMusterweg 2\n3000 Bern", "layout": "plain", "features": [],
            "blocks": [{"type": "paragraph", "label": "", "text": "Ich fordere das Darlehen zurück."}]}


LOAN = {"area": "vertrag-darlehen", "action": "A1",
        "facts": {"schriftlich": True, "termin_vereinbart": False, "aufforderung": "2026-03-02"},
        "ask_now": ["auszahlungsbeleg", "korrespondenz"], "present": ["darlehensvertrag", "kuendigung_rueckforderung"],
        "offered": [], "not_needed": [], "depends": {}, "deadline": [{"id": "rueckzahlung", "date": "2026-04-13"}], "notes": ""}
NOISE = {"area": "allgemein", "action": "A1", "facts": {}, "ask_now": ["korrespondenz"], "present": ["beweismittel"],
         "offered": [], "not_needed": [], "depends": {"vertrag_entscheid": "vertrag", "fristschreiben": "frist"}, "deadline": [], "notes": ""}


def write_suite(directory, loan=LOAN):
    for cid, truth, docs in (("X01-loan-demand", loan, [letter("Darlehensvertrag", "contract"), letter("Kündigung des Darlehens")]),
                             ("X02-noise-upstairs", NOISE, [letter("Lärmprotokoll", "note")])):
        Path(directory, cid).mkdir()
        Path(directory, cid, "case.json").write_text(json.dumps({"format": FORMAT, "id": cid, "title": "t", "scenario": "s",
                                                                 "documents": docs, "truth": {}, "truth_handler": truth}))


RESULTS = [
    {"case": "X01", "workflow": "vertrag-darlehen", "action": "A1", "now": ["auszahlungsbeleg", "darlehensvertrag", "inserat"], "offered": [],
     "letter_lines": 4, "letter_gaps": 0, "follow_up": "2026-03-23", "deadlines": [{"id": "rueckzahlung", "date": "2026-04-14"}],
     "seconds": 41.5, "tokens": {"non_cached": 1200, "output": 300}},
    {"case": "X02", "workflow": "allgemein", "action": "A1", "now": ["korrespondenz", "fristschreiben", "vertrag_entscheid"], "offered": [],
     "letter_lines": 3, "letter_gaps": 1, "follow_up": None, "deadlines": [], "seconds": 30, "tokens": {"non_cached": 800, "output": 200}},
]


class ScoreSavedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        write_suite(self.tmp.name)
        self.cases = load_suite(self.tmp.name)

    def test_each_check_is_scored_and_the_failures_are_grouped_by_area(self):
        scored = dict((cid, s) for cid, _, s in handler.score_saved(RESULTS, self.cases))
        loan, noise = scored["X01"], scored["X02"]
        self.assertEqual((loan["area"], loan["action"], loan["hit"], loan["expected"]), (True, True, ["auszahlungsbeleg"], 2))
        self.assertEqual((loan["extra"], loan["present_asked"], loan["letter"], loan["deadline"]), (["inserat"], ["darlehensvertrag"], True, "wrong"))
        self.assertEqual((noise["hit"], noise["extra"], noise["letter"], noise["deadline"]), (["korrespondenz"], [], False, None))
        text = handler.render(handler.score_saved(RESULTS, self.cases))
        self.assertIn("X01 area ok action ok documents 1/2 extra 1 present asked 1 letter ok deadline wrong", text)
        self.assertIn("vertrag-darlehen: X01 not asked korrespondenz, X01 extra inserat, X01 present asked darlehensvertrag, X01 deadline rueckzahlung", text)
        self.assertIn("allgemein: X02 letter incomplete (1 gap)", text)
        self.assertIn("X02 area ok action ok documents 1/1 extra 0 present asked 0 letter FAIL (1 gap) deadline -", text)
        empty = handler.score_row(NOISE, {**RESULTS[1], "letter_lines": 0, "letter_gaps": 0, "letter_missing": ["Fragen"]})
        self.assertEqual((empty["letter"], empty["letter_why"]), (False, ["0 lines", "missing Fragen"]))  # why, not only that
        total = next(line for line in text.splitlines() if line.startswith("total"))
        self.assertEqual(total.split(), ["total", "2/2", "2/2", "2/3", "1", "1", "1/2", "0/1", "0/0", "71.5", "2000/500"])
        self.assertNotIn("Darlehen zurück", text)  # ids and counts only

    def test_a_case_without_a_row_and_dates_where_the_trigger_is_missing(self):
        text = handler.render(handler.score_saved(RESULTS[1:], self.cases))
        self.assertIn("X01 no saved result", text)
        missing = {"id": "rueckzahlung", "date": "trigger_missing"}
        self.assertEqual(handler.deadline_verdict(missing, {}), "right")
        self.assertEqual(handler.deadline_verdict(missing, {"rueckzahlung": "prüfen"}), "right")
        self.assertEqual(handler.deadline_verdict(missing, {"rueckzahlung": "2026-04-13"}), "wrong")  # an invented date
        self.assertEqual(handler.deadline_verdict({"id": "a", "date": "prüfen"}, {}), "missing")

    def test_the_command_prints_the_table(self):
        path = Path(self.tmp.name) / "results.json"
        path.write_text(json.dumps(RESULTS))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            evaluate_main(["score-saved", str(path), self.tmp.name])
        self.assertIn("failed checks by area:", out.getvalue())

    def test_a_truth_naming_an_unknown_document_is_refused(self):
        bad = {**LOAN, "ask_now": ["mietvertrag"]}
        with self.assertRaises(BenchmarkError):
            handler.check_truth({"id": "X09-x", "truth_handler": bad}, handler.areas())
        with self.assertRaises(BenchmarkError):  # a key point the area does not have
            handler.check_truth({"id": "X09-x", "truth_handler": {**LOAN, "key_points": ["sperrfrist"]}}, handler.areas())

    def test_the_key_points_on_the_card_are_scored_where_the_truth_names_them(self):
        truth = {**LOAN, "key_points": ["ohne_termin"]}
        shown = handler.score_row(truth, {**RESULTS[0], "key_points": ["ohne_termin"]})
        self.assertEqual((shown["points"]["hit"], shown["points"]["want"], shown["points_ok"]), (["ohne_termin"], 1, True))
        # only a point shown as applying counts; one the facts do not meet, shown as applying, is a failure of its own
        asked = handler.score_row(truth, {**RESULTS[0], "key_points": [{"id": "ohne_termin", "state": "open"}, {"id": "beweis", "state": "applies"}]})
        self.assertEqual((asked["points"]["hit"], asked["points"]["extra"], asked["points_ok"]), ([], ["beweis"], False))
        self.assertIsNone(handler.score_row(LOAN, {**RESULTS[0], "key_points": ["ohne_termin"]})["points"])  # an older truth names none
        self.assertIsNone(handler.score_row(truth, RESULTS[0])["points"])  # a row that does not report them
        with tempfile.TemporaryDirectory() as tmp:
            write_suite(tmp, truth)
            rows = [{**RESULTS[0], "key_points": [{"id": "beweis", "state": "applies"}]}, RESULTS[1]]
            text = handler.render(handler.score_saved(rows, load_suite(tmp)))
        self.assertIn("X01 area ok action ok documents 1/2 extra 1 present asked 1 letter ok deadline wrong key points 0/1!", text)
        self.assertIn("X01 key point not shown ohne_termin, X01 key point shown beweis", text)
        self.assertEqual(next(line for line in text.splitlines() if line.startswith("total")).split()[8], "0/1")


class SelfCheckTests(unittest.TestCase):
    def test_the_rules_with_a_perfect_reading_agree_with_the_truth_or_name_the_difference(self):
        workflows = handler.areas()
        with tempfile.TemporaryDirectory() as tmp:
            write_suite(tmp)
            rows = {cid: (got, diff) for cid, _, got, diff in handler.self_check(load_suite(tmp), workflows)}
        self.assertEqual(rows["X01"][1], {})
        self.assertEqual(rows["X01"][0]["deadlines"], [("rueckzahlung", "2026-04-13")])  # six weeks, same weekday
        self.assertEqual((rows["X02"][1], rows["X02"][0]["later"]), ({}, ["fristschreiben", "vertrag_entscheid"]))
        with tempfile.TemporaryDirectory() as tmp:
            write_suite(tmp, {**LOAN, "ask_now": ["korrespondenz"], "deadline": [{"id": "rueckzahlung", "date": "trigger_missing"}]})
            diff = handler.self_check(load_suite(tmp), workflows)[0][3]
        self.assertEqual(diff, {"now": {"rules_only": ["auszahlungsbeleg"], "truth_only": []}, "deadlines": ["rueckzahlung"]})
        self.assertEqual(rows["X01"][0]["key_points"], ["ohne_termin"])  # the points whose condition the facts meet
        with tempfile.TemporaryDirectory() as tmp:
            write_suite(tmp, {**LOAN, "key_points": ["beweis"]})
            diff = handler.self_check(load_suite(tmp), workflows)[0][3]
        self.assertEqual(diff, {"key_points": {"rules_only": ["ohne_termin"], "truth_only": ["beweis"]}})


if __name__ == "__main__":
    unittest.main()
