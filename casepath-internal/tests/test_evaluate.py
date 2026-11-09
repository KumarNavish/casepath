import json
from pathlib import Path
import re
import tempfile
import unittest

from casepath_internal import benchmark
from casepath_internal.evaluate import compare, evaluate_suite, same_value, dates_in
from casepath_internal.workflows import Catalogue
from tests.scripted import ScriptedModel, report

FIXTURES = Path(__file__).parent / "fixtures"
QUOTE = "Ich habe den Vermieter am 2. März schriftlich informiert."
VENT = "Ich lüfte dreimal täglich, trotzdem kommt der Schimmel zurück."


def letter():
    return {"kind": "letter", "title": "Schimmel im Bad", "date": "2025-03-04", "sender": "Mia Muster\nBeispielweg 1\n3000 Bern",
            "recipient": "Rechtsschutz\nPostfach\n3001 Bern", "layout": "plain", "features": [],
            "blocks": [{"type": "paragraph", "label": "", "text": QUOTE}, {"type": "paragraph", "label": "", "text": VENT}]}


def case(case_id, **truth):
    base = {"workflow": "example-defect", "facts": {"landlord_notified": True, "legal_area": None},
            "evidence": {"landlord_notified": QUOTE}, "outcome": "reported", "documents": {"notice_letter": "missing"},
            "case_documents": [{"label": "Lüftungsprotokoll", "match": ["ventilation"], "status": "missing"}],
            "not_required": [{"label": "Arztzeugnis", "match": ["arzt", "medical"]}],
            "next_actions": [{"label": "Notice", "match": ["notice"]}], "deadlines": [],
            "flags": {"injection": False, "conflict_facts": []}, "notes": "", "tags": ["test"]}
    return {"format": benchmark.FORMAT, "id": case_id, "title": "Schimmel", "scenario": "A tenant reports mould.",
            "documents": [letter()], "truth": {**base, **truth}}


def scripted_model():
    """One run of the team on the case's single file, wherever the store put it."""
    model = None

    def file_id():
        return re.search(r"file_[0-9a-f]{16}", json.dumps(model.inputs[-1])).group(0)

    def fact():
        return {"fact": "landlord_notified", "status": "established", "value": "yes", "citations": [{"file": file_id(), "quote": QUOTE}]}

    def proposal():
        return {"op": "add_document", "title": "Ventilation record", "why": "The tenant says they ventilate.", "question": "",
                "step": None, "required_when": [], "legal_basis": "", "basis_knowledge": None,
                "citations": [{"file": file_id(), "quote": VENT}], "reason": "The customer raises it."}

    model = ScriptedModel([
        [report("claim_reader", request="Check the mould defect.")],
        [("open_process", {}), ("propose_change", proposal), report("process_builder")],
        [("record_fact", fact), report("claim_reader")],
        [("record_document", {"document": "notice_letter", "status": "absent", "files": [], "citations": [], "note": ""}),
         report("document_finder")],
        [report("result_checker")],
    ])
    return model


class EvaluateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def suite(self, cases):
        for c in cases:
            (self.root / "suite" / c["id"]).mkdir(parents=True)
            (self.root / "suite" / c["id"] / "case.json").write_text(json.dumps(c, ensure_ascii=False))
        return benchmark.load_suite(self.root / "suite")

    def test_cases_run_through_the_api_and_every_miss_is_listed(self):
        expert = {"op": "add_document", "args": {"title": "Lüftungsprotokoll", "why": "Belegt das Lüften.", "step": None, "required_when": None},
                  "reason": "Typische Einwendung.", "use_for_similar": True, "activate": True}
        cases = self.suite([
            case("T01-defect-notice"),
            case("S01-first-of-sequence", sequence={"group": "vent", "order": 1}, expert_edits=[expert]),
            # The second case of the sequence expects the expert's Knowledge, and a wrong outcome to show a listed failure.
            case("S02-second-of-sequence", sequence={"group": "vent", "order": 2}, outcome="advice",
                 expect_knowledge={"applied": [{"label": "Lüftungsprotokoll", "match": ["lüftung"]}], "status": "missing"}),
        ])
        catalogue = Catalogue.load(FIXTURES)
        for c in cases:
            self.assertEqual(benchmark.validate_case(c, {w["id"]: w for w in catalogue.latest()}), [])
        results = evaluate_suite(cases, catalogue, FIXTURES, self.root / "out", model_factory=scripted_model, repeats=2,
                                 given_workflow=True, env={}, log=lambda line: None)
        self.assertEqual((results["summary"]["runs"], results["summary"]["completed"]), (6, 6))
        failed = [(r["case"], c["check"], c["target"]) for r in results["runs"] for c in r["checks"] if not c["passed"]]
        self.assertEqual(sorted(set(failed)), [("S02-second-of-sequence", "outcome", "outcome")])
        checks = {(c["check"], c["target"]): c for c in next(r for r in results["runs"] if r["case"] == "S02-second-of-sequence")["checks"]}
        self.assertTrue(checks[("applied", "Lüftungsprotokoll")]["passed"])  # the expert's correction in S01 shaped S02
        self.assertTrue(checks[("evidence", "landlord_notified")]["passed"])
        self.assertTrue(checks[("discovered", "Lüftungsprotokoll")]["passed"])
        self.assertTrue(checks[("not_demanded", "Arztzeugnis")]["passed"])
        self.assertEqual(results["summary"]["consistency"], 1.0)
        written = (self.root / "out" / "report.md").read_text()
        self.assertIn("| S02-second-of-sequence | 1 | requirements | outcome | outcome | advice | reported |  |", written)
        # T01 ran on its own store: no Knowledge from the sequence reached it.
        t01 = next(r for r in results["runs"] if r["case"] == "T01-defect-notice")
        self.assertFalse(any(c["check"] == "applied" for c in t01["checks"]))

        # Scoring again from the kept stores gives the same checks, without a model.
        from casepath_internal.evaluate import rescore
        again = rescore(self.root / "out", cases, catalogue, FIXTURES)
        self.assertEqual([c["passed"] for r in again["runs"] for c in r["checks"]], [c["passed"] for r in results["runs"] for c in r["checks"]])

        worse = json.loads(json.dumps(results))
        worse["runs"][0]["checks"][0]["passed"] = False
        self.assertEqual(len(compare(results, worse)["regressed"]), 1)

    def test_evidence_may_be_any_sentence_of_the_document_that_settles_the_fact(self):
        from casepath_internal.evaluate import document_of
        c = case("T01-defect-notice")
        c["documents"].append({**letter(), "title": "Antwort", "blocks": [{"type": "paragraph", "label": "", "text": "Wir prüfen den Fall."}]})
        self.assertEqual(document_of(c, VENT), 0)
        self.assertEqual(document_of(c, "Ich lüfte dreimal taglich, trotzdem kommt der Schimmel zurück"), 0)  # read from a scan
        self.assertEqual(document_of(c, "Wir prüfen den Fall."), 1)
        self.assertIsNone(document_of(c, "Ein Satz, der nirgends steht."))

    def test_synthetic_cases_can_be_seeded_for_everyone_once(self):
        from casepath_internal.store import CaseStore
        self.suite([case("T01-defect-notice"), case("T02-second-case")])
        store = CaseStore(self.root / "data")
        self.addCleanup(store.close)
        self.assertEqual(benchmark.seed(store, self.root / "suite"), 2)
        self.assertEqual(benchmark.seed(store, self.root / "suite"), 0)  # already there
        rows = store.list_cases()
        self.assertEqual(sorted(r["title"] for r in rows), ["Synthetischer Fall T01: Schimmel im Bad", "Synthetischer Fall T02: Schimmel im Bad"])
        self.assertTrue(all(r["intake"]["synthetic"] and r["file_count"] == 1 for r in rows))
        self.assertIn(QUOTE[:20], store.list_files(rows[0]["id"], with_text=True)[0]["extraction"]["text"])

    def test_values_and_dates_are_compared_as_a_case_worker_would(self):
        self.assertTrue(same_value("text", "Treuhand Sonnhalde AG", "Treuhand Sonnhalde AG, Rorschacher Strasse 140, 9000 St. Gallen"))
        self.assertTrue(same_value("text", "CHF 15'000.–", "15000 CHF"))
        self.assertFalse(same_value("text", "Treuhand Sonnhalde AG", "Immobilien Graf GmbH"))
        self.assertTrue(same_value("boolean", True, True) and not same_value("boolean", True, None))
        self.assertEqual(dates_in("bis 15. September 2025 bzw. 30.4.2025 oder 2025-01-02"), {"2025-09-15", "2025-04-30", "2025-01-02"})


if __name__ == "__main__":
    unittest.main()
