import io
import unittest
import zipfile

from casepath.web import report


def text_of(docx):
    with zipfile.ZipFile(io.BytesIO(docx)) as z:
        return z.read("word/document.xml").decode()


class ReportLabelTests(unittest.TestCase):
    def build(self, lang):
        case = {"id": "case_0000000000000001", "title": "Fall"}
        need = {"document": "e-pb1", "title": "Mietvertrag", "required": "suggested", "status": "missing", "citations": [],
                "questions": [{"fact": "f", "question": "Gibt es einen schriftlichen Vertrag?"}]}
        state = {"run": {"result": {"facts": [{"fact": "f", "status": "established", "value": True, "verdict": "accepted", "citations": [],
                                               "flag": {"kind": "source_checker_doubt", "reason": "Zitat zu knapp"}}],
                                    "documents": [], "warnings": [{"kind": "turn_limit", "agent": "document_finder", "text": "x"}],
                                    "evaluation": {"documents": [need]}}},
                 "process": {"documents": [{"id": "e-pb1", "legal_basis": "Art. 253 OR", "edit": "pb1"}], "facts": [{"id": "f", "question": "Vertrag?"}]}}
        return text_of(report.build(case, state, [], lang=lang))

    def test_a_suggestion_with_a_legal_basis_is_not_shown_as_a_legal_requirement(self):
        de, en = self.build("de"), self.build("en")
        self.assertNotIn("nach Gesetz verlangt", de)
        self.assertNotIn("required by law", en)
        self.assertIn("für diesen Fall vorgeschlagen; Grundlage: Art. 253 OR; gilt, falls: Gibt es einen schriftlichen Vertrag?", de)
        self.assertIn("suggested for this case; basis: Art. 253 OR", en)

    def test_the_checkers_doubt_and_the_warnings_are_in_the_report(self):
        de, en = self.build("de"), self.build("en")
        self.assertIn("die Prüfung zweifelt: Zitat zu knapp", de)
        self.assertIn("the check doubts it: Zitat zu knapp", en)
        self.assertIn("Hinweise zur Vorbereitung", de)
        self.assertIn("documents it did not reach stay requested", en)


class ProductTextTests(unittest.TestCase):
    def test_notes_the_product_writes_carry_a_code_and_the_stopped_result_is_in_both_languages(self):
        import json
        from pathlib import Path
        from casepath.agents.team import CaseWork, _record_document, finalize
        fixture = json.loads((Path(__file__).parent / "fixtures" / "example-defect.json").read_text())
        files = [{"id": "f1", "name": "message.eml", "kind": "email", "text": "Ich habe den Vermieter am 2. März schriftlich informiert."}]
        work = CaseWork(case={"title": "x", "intake": {}}, files=files, base_workflow=fixture)
        _record_document(work, "document_finder", {"document": "notice_letter", "status": "mentioned_only", "files": ["f1"],
                                                    "citations": [{"file": "f1", "quote": "Ich habe den Vermieter am 2. März"}], "note": ""})
        self.assertEqual(work.documents["notice_letter"]["note_codes"], [{"code": "mentioned_only", "items": ["message.eml"]}])
        work.result = None
        result = finalize(work)
        self.assertEqual(result["answer_code"], "result_checker_stopped")
        state = {"run": {"result": result}, "process": work.graph}
        self.assertIn("Nicht abgeschlossen", text_of(report.build({"id": "case_00000001", "title": "x"}, state, [], lang="de")))
        self.assertIn("Not finished", text_of(report.build({"id": "case_00000001", "title": "x"}, state, [], lang="en")))


class NotCheckedTests(unittest.TestCase):
    def test_a_need_the_finder_did_not_reach_shows_as_missing_and_not_checked(self):
        need = {"document": "d1", "title": "Mietvertrag", "required": "yes", "status": "missing", "not_checked": True, "citations": []}
        state = {"run": {"result": {"facts": [], "documents": [], "warnings": [], "evaluation": {"documents": [need]}}}, "process": {"documents": []}}
        self.assertIn("fehlt (nicht geprüft)", text_of(report.build({"id": "case_00000001", "title": "x"}, state, [], lang="de")))


class StopNoteTests(unittest.TestCase):
    def test_a_stop_note_is_true_for_the_part_that_stopped(self):
        need = {"document": "d1", "title": "x", "required": "yes", "status": "missing", "citations": []}
        state = {"run": {"result": {"facts": [], "documents": [], "evaluation": {"documents": [need]},
                                    "warnings": [{"kind": "turn_limit", "agent": "result_checker", "text": "x"}]}}, "process": {"documents": []}}
        text = text_of(report.build({"id": "case_00000001", "title": "x"}, state, [], lang="en"))
        self.assertIn("The summary stopped early; no reply draft was prepared.", text)
        self.assertNotIn("not checked", text.split("Notes on the preparation")[1].split("Where the case stands")[0])


class RoutingNoteTests(unittest.TestCase):
    def test_a_reroute_and_a_hand_over_are_in_the_report(self):
        cite = [{"file": "f1", "quote": "Es geht um ein Darlehen."}]
        conflict = {"routed_to": {"id": "tenancy", "version": 1}, "admitted": [{"fact": "legal_area", "value": "loan", "citations": cite}]}
        for key, text_en in (("rerouted", "contradicted the first routing (tenancy); the case was routed again"),
                             ("conflict", "contradict the routing (tenancy); a person chooses the process")):
            state = {"run": {"result": {"facts": [], "documents": [], "warnings": [], "evaluation": {"documents": []},
                                        "routing": {key: conflict}}}, "process": {"documents": []}}
            en = text_of(report.build({"id": "case_00000001", "title": "x"}, state, [{"id": "f1", "name": "brief.pdf"}], lang="en"))
            self.assertIn(text_en, en)
            self.assertIn("legal_area = loan (admitted by the readings: «Es geht um ein Darlehen.» — brief.pdf)", en)
            self.assertIn("Lesungen", text_of(report.build({"id": "case_00000001", "title": "x"}, state, [], lang="de")))
        state = {"run": {"result": {"facts": [], "documents": [], "evaluation": {"documents": []},
                                    "warnings": [{"kind": "routing_contradicted", "agent": "source_checker", "facts": []}]}}, "process": {"documents": []}}
        self.assertIn("contradict the chosen process", text_of(report.build({"id": "case_00000001", "title": "x"}, state, [], lang="en")))
