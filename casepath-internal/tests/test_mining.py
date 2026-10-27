import unittest

from casepath_internal import mining
from casepath_internal.azure_model import ModelResult

FILES = [{"id": "f1", "name": "dossier.pdf", "kind": "pdf",
          "text": "[page 1]\nIch melde hiermit den Schimmel im Badezimmer meiner Wohnung schriftlich.\n\n[page 2]\nWir bestätigen die Kostengutsprache für die Abklärung durch einen Fachmann.",
          "segments": [{"first_page": 1, "last_page": 1, "kind": "Mängelrüge", "date": "03.02.2025", "title": "Mängelrüge"},
                       {"first_page": 2, "last_page": 2, "kind": "Brief Protekta", "date": "20.02.2025", "title": "Kostengutsprache"}]}]


class Fake:
    def respond_json(self, *, name, instructions, input, schema, effort="medium"):
        if name == "casepath_case_course":
            value = {"events": [
                {"date": "03.02.2025", "iso_date": "2025-02-03", "actor": "versicherte Person", "action": "Mängelrüge an Vermieter", "document_kind": "Mängelrüge",
                 "file": "f1", "quote": "Ich melde hiermit den Schimmel im Badezimmer meiner Wohnung schriftlich."},
                {"date": "20.02.2025", "iso_date": "2025-02-20", "actor": "Protekta", "action": "Kostengutsprache für Abklärung", "document_kind": "Brief",
                 "file": "f1", "quote": "Wir bestätigen die Kostengutsprache für die Abklärung durch einen Fachmann."},
                {"date": "?", "iso_date": None, "actor": "Andere", "action": "Erfunden", "document_kind": "", "file": "f1", "quote": "Dieser Satz steht nirgends in der Akte drin."}],
                "protekta_actions": [{"date": "20.02.2025", "action": "Kostengutsprache"}], "deadlines": [], "outcome": {"status": "offen", "description": ""}}
        else:
            value = {"groups": [{"category": "Mängelrüge", "members": ["Mängelrüge an Vermieter"]},
                                {"category": "Kostengutsprache", "members": ["Kostengutsprache für Abklärung"]}]}
        return ModelResult(value=value, usage={}, deployment="d", response_id="r", attempts=1, seconds=0)


class MiningTests(unittest.TestCase):
    def test_course_keeps_only_quoted_events_and_pattern_is_content_free(self):
        course = mining.case_course(Fake(), FILES)
        self.assertEqual(course["dropped_events"], 1)
        mapping = mining.group_actions(Fake(), [e["action"] for e in course["events"]])
        rows = mining.pattern([course, course], mapping)
        self.assertEqual([r["category"] for r in rows], ["Mängelrüge", "Kostengutsprache"])
        self.assertEqual((rows[1]["cases"], rows[1]["of"], rows[1]["median_days"]), (2, 2, 17))
        self.assertNotIn("Badezimmer", str(rows))


if __name__ == "__main__":
    unittest.main()
