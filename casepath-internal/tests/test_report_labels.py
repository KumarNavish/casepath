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
        self.assertIn("marked as not checked", en)
