"""The handler's truth of a benchmark suite: saved results scored, and the truth checked against the rules (no model)."""
import contextlib
import io
import json
from pathlib import Path
import re
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

    def test_an_assessment_whose_only_gaps_are_the_handlers_is_ok_with_its_gaps_named_apart_from_an_incomplete_one(self):
        """Where the truth names neither a recommendation nor answers. Where it names them, the assessment is expected to give
        them and its declared gaps no longer make it «ok» (MEASURE §2: the substantive part is not the handler's by default)."""
        from casepath.process import area, letters
        assess = {**NOISE, "action": "A5", "ask_now": []}
        own = handler.letter_form(assess)["handler_gaps"]
        self.assertEqual(set(own), {"rights", "im_fall", "empfehlung"})  # the reasons (here the legal basis too) and the recommendation
        self.assertEqual(set(handler.letter_form({**assess, "area": "mietmangel-handler"})["handler_gaps"]), {"im_fall", "empfehlung"})
        # the letter the product renders carries exactly those gaps: the form's declaration and the letter agree
        items = [{"item_id": "key_point:x", "kind": "key_point", "key": "x", "value": "applies", "follows": "Ein Anspruch besteht.",
                  "legal_basis": "Art. 1 OR", "label": {"de": "x"}}]
        text = letters.render("A5", area.workflow("allgemein")["forms"], letters.context({"id": "c", "title": "t", "intake": {}}, items, [], {}))[0]
        gaps = re.findall(r"\[bitte ergänzen: ([^\]]+)\]", text)
        self.assertTrue(gaps and all(any(g in v for v in own.values()) for g in gaps), gaps)
        row = {"case": "X02", "workflow": "allgemein", "action": "A5", "now": [], "letter_lines": 9, "deadlines": []}
        ok = handler.score_row(assess, {**row, "letter_gap_texts": gaps})
        self.assertEqual((ok["letter"], ok["letter_why"], ok["letter_own_gaps"]), ("handler", [], len(gaps)))
        self.assertEqual(handler.score_row(assess, {**row, "letter_gaps": 2})["letter"], "handler")  # a count within the declared places
        odd = handler.score_row(assess, {**row, "letter_gap_texts": gaps + ["Antwort auf diese Frage"]})
        self.assertEqual((odd["letter"], odd["letter_why"], odd["letter_own_gaps"]), (False, ["1 gap"], len(gaps)))  # an unexpected gap
        self.assertEqual(handler.score_row(assess, {**row, "letter_gaps": 4})["letter_why"], ["4 gaps"])  # more than its places: not read as its own
        empty = handler.score_row(assess, {**row, "letter_lines": 0, "letter_gaps": 2})
        self.assertEqual((empty["letter"], empty["letter_why"]), (False, ["0 lines"]))  # no lines is never ok
        cases = [{**c, "truth_handler": assess if c["id"].startswith("X02") else c["truth_handler"]} for c in self.cases]
        out = handler.render(handler.score_saved([RESULTS[0], {**row, "letter_gap_texts": gaps}], cases))
        self.assertIn(f"X02 area ok action ok documents 0/0 extra 0 present asked 0 letter ok, {len(gaps)} gaps for the handler deadline -", out)
        self.assertIn("allgemein: none", out)
        self.assertEqual(handler.score_row(NOISE, {**RESULTS[1], "letter_gaps": 1})["letter"], False)  # a first request declares none
        # the truth names what a complete assessment gives: the same gaps are gaps like any other, and the line says why
        for named, reason in (({"recommendation": ["frist_beseitigung", "schadenersatz"]}, "the truth names recommendation"),
                              ({"answers": 2}, "the truth names answers"),
                              ({"recommendation": ["frist_beseitigung"], "answers": 1}, "the truth names recommendation and answers")):
            scored = handler.score_row({**assess, **named}, {**row, "letter_gap_texts": gaps})
            self.assertEqual((scored["letter"], scored["letter_why"], scored["letter_own_gaps"]), (False, [f"{len(gaps)} gaps", reason], 0))
        self.assertEqual(handler.score_row({**assess, "answers": 0}, {**row, "letter_gap_texts": gaps})["letter"], "handler")  # no question to answer
        self.assertEqual(handler.score_row({**assess, "recommendation": ["frist_beseitigung"]}, {**row, "letter_gaps": 0})["letter"], True)
        workflows = handler.areas()
        for bad in ({"recommendation": []}, {"recommendation": ["Frist setzen"]}, {"answers": -1}, {"answers": "zwei"}):
            with self.assertRaises(BenchmarkError):
                handler.check_truth({"id": "X09-x", "truth_handler": {**NOISE, **bad}}, workflows)
        self.assertEqual(handler.check_truth({"id": "X09-x", "truth_handler": {**NOISE, "recommendation": ["frist_beseitigung"], "answers": 2}},
                                             workflows)["answers"], 2)

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


class ExpertEditTests(unittest.TestCase):
    """The benchmark's expert corrections (quality/evaluate.py, expert_edits) activate shared Knowledge only after a replay of
    its current version, as a person must (docs/HANDLER_BAR.md, L3); the activation is never asked of the edit form."""

    class Api:
        def __init__(self, replay=None):
            self.calls, self.replay = [], replay

        def call(self, method, path, body=None):
            from casepath.quality.evaluate import ApiError
            self.calls.append((path, body))
            if path.endswith("/edits"):
                return {"knowledge": {"id": "know-1", "status": "candidate"} if body.get("use_for_similar") else None}
            if path.endswith("/replay") and self.replay:
                raise ApiError(self.replay, "refused")
            return {"status": "active"} if path.endswith("/activate") else {"replayed": True}

    def test_a_correction_to_activate_is_posted_as_a_candidate_replayed_then_activated(self):
        from casepath.quality.evaluate import expert_edits
        edit = {"op": "add_document", "args": {"title": "Lüftungsprotokoll"}, "reason": "", "use_for_similar": True, "activate": True}
        api = self.Api()
        self.assertEqual(expert_edits(api, "case_1", [edit]), [{"op": "add_document", "accepted": True, "knowledge": "active", "replayed": True}])
        self.assertEqual([p for p, _ in api.calls], ["/api/cases/case_1/edits", "/api/knowledge/know-1/replay", "/api/knowledge/know-1/activate"])
        self.assertNotIn("activate", api.calls[0][1])
        before_gate = self.Api(replay=404)  # a deployment without the replay route: activated directly, and said so
        self.assertEqual(expert_edits(before_gate, "case_1", [edit])[0]["replayed"], False)
        refused = self.Api(replay=500)
        self.assertEqual(expert_edits(refused, "case_1", [edit])[0]["accepted"], False)  # never activated without its replay
        self.assertNotIn("/api/knowledge/know-1/activate", [p for p, _ in refused.calls])
        plain = self.Api()
        self.assertEqual(expert_edits(plain, "case_1", [{**edit, "use_for_similar": False, "activate": False}]),
                         [{"op": "add_document", "accepted": True, "knowledge": None}])
        self.assertEqual(len(plain.calls), 1)


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
