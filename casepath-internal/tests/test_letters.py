import json
import re
import unittest
from pathlib import Path

from casepath.agents import core
from casepath.process import letters, workflows
from casepath.process.items import build_items

SEED = Path(workflows.__file__).with_name("workflow_seed") / "mietmangel-handler.json"
WF = workflows.validate_workflow(json.loads(SEED.read_text()))
CASE = {"id": "case_example", "title": "Schimmel im Bad (synthetisch) 1234.5678.9012", "intake": {}}


def fact(fid, value):
    return {"fact": fid, "status": "established", "verdict": "accepted", "value": value, "citations": []}


def prepared(extra=()):
    facts = [fact("rechtsgebiet", "Mietrecht / Mangel"), fact("maengelruege_schriftlich", "ja"), fact("will_schadenersatz", "nein"),
             fact("streit_mietzins", "nein"), fact("handlung_a1", "2024-03-12"), *extra]
    result = {"facts": facts, "documents": [], "brief": {"request": "Schimmel im Badezimmer seit dem Winter.", "parties": [], "timeline": []}}
    state = core.evaluate(WF, [], [], result, "c")
    looked = [{"name": "Schadenmeldung.pdf", "extraction": {"cut_of": {"as_of": "2024-04-20"}, "segments": [{"date": "12.03.2024"}]}}]
    return state, build_items(state, result, looked)  # looked at on a fixed day, so the text never depends on today


class LetterTests(unittest.TestCase):
    def test_every_action_kind_renders_its_form_with_every_part_and_no_empty_placeholder(self):
        state, items = prepared()
        ctx = letters.context(CASE, items, [], {"due": "2024-04-12"})
        for kind, form in WF["forms"].items():
            if kind.startswith("_"):
                continue
            text, reason = letters.render(kind, WF["forms"], ctx)
            if form.get("none"):
                self.assertIsNone(text)
                self.assertTrue(reason)  # "kein Entwurf: <reason>"
                continue
            self.assertNotIn("{", text, kind)
            self.assertNotIn("…", text, kind)
            self.assertNotIn("\n\n\n", text, kind)  # no empty line where a part was
            self.assertIn("Unsere Referenz: 1234.5678.9012", text)
            self.assertIn("Für Ihre Kenntnisnahme und Bemühungen danken wir Ihnen bestens.", text)
            for part in form["parts"]:
                fixed = [bit for bit in re.split(r"\{[a-z_]+\}", part) if len(bit.strip()) > 12]
                for bit in fixed:  # every fixed sentence of the form is in the draft
                    self.assertIn(bit.strip().split("\n")[0], text, f"{kind}: {bit[:40]}")
        a6, _ = letters.render("A6", WF["forms"], ctx)
        self.assertIn("Ohne Ihre Rückmeldung bis 12.04.2024", a6)

    def test_a_document_the_handler_unticked_is_neither_asked_nor_awaited(self):
        state, items = prepared()
        doc = next(i for i in items if i["kind"] == "document" and i.get("ask") == "now" and i.get("status") != "present")
        unticked = [{"kind": "letter.line", "item_id": doc["item_id"], "included": False}]
        ctx = letters.context(CASE, items, unticked, {"due": "2024-04-12"})
        a1, _ = letters.render("A1", WF["forms"], ctx)
        title = doc["label"]["de"]
        self.assertNotIn(f"– {title}", a1)
        note = letters.file_note(CASE, items, unticked, {"due": "2024-04-12"}, files=[{"name": "Schadenmeldung.pdf"}])
        self.assertIn(f"Nicht verlangt (von der Fallbearbeitung gestrichen): {title}", note)
        self.assertNotIn(f"Erwartet: {title}", note)

    def test_the_file_note_is_the_same_paragraph_every_time(self):
        state, items = prepared()
        events = [{"kind": "letter.copied", "at": "2024-03-12T10:00:00+00:00", "edited": True}]
        note = letters.file_note(CASE, items, events, {"due": "2024-04-02"}, files=[{"name": "Schadenmeldung.pdf"}])
        self.assertEqual(note, letters.file_note(CASE, items, events, {"due": "2024-04-02"}, files=[{"name": "Schadenmeldung.pdf"}]))
        self.assertTrue(note.startswith("Eingegangen: Schadenmeldung.pdf."))
        self.assertIn("Versandt: Schreiben vom 12.03.2024 (angepasst).", note)
        self.assertEqual(note, "Eingegangen: Schadenmeldung.pdf. Nächster Schritt: Dossier pendent halten mit Frist, weil keine Antwort "
                               "seit A1 vom 12.03.2024 (39 Tage). Versandt: Schreiben vom 12.03.2024 (angepasst). "
                               "Erwartet: Mietvertrag, Fotos des Mangels bis 02.04.2024.")


if __name__ == "__main__":
    unittest.main()


class GapTests(unittest.TestCase):
    def test_what_only_the_reading_or_the_handler_can_say_is_a_marked_gap_never_an_invented_sentence(self):
        state, items = prepared()
        with_summary = letters.context(CASE, items, [], {"due": "2024-04-12"})
        bare = letters.context(CASE, [i for i in items if i["kind"] != "summary"], [], {"due": "2024-04-12"})
        a5, _ = letters.render("A5", WF["forms"], with_summary)
        self.assertIn("In Ihrem Fall: Schimmel im Badezimmer seit dem Winter.", a5)  # the stored request
        self.assertIn("[bitte ergänzen: die Empfehlung an die Kundschaft]", a5)  # the recommendation is the handler's
        self.assertTrue(letters.has_gap(a5))
        a8, _ = letters.render("A8", WF["forms"], bare)
        self.assertIn("[bitte ergänzen: was in diesem Fall vorliegt]", a8)  # no stored text: a gap, not a made-up paragraph
        for kind in ("A1", "A4", "A6", "A7", "A10", "A12"):  # filled from what the case asserts: no gap
            self.assertFalse(letters.has_gap(letters.render(kind, WF["forms"], with_summary)[0]), kind)
