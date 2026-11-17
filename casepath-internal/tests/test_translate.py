"""Reading in another language: what CasePath shows is translated beside the answer, never in it."""
import json
import re
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from casepath.config import load_settings
from casepath.web import translate
from casepath.web.app import create_app
from casepath.web.store import CaseStore

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "casepath/web/ui/assets/casepath.js").read_text(encoding="utf-8")
MEMORY = json.loads((ROOT / "casepath/web/i18n/en.json").read_text(encoding="utf-8"))


def memory(entries):
    folder = tempfile.mkdtemp()
    (Path(folder) / "en.json").write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return folder


class Result:
    def __init__(self, value, tokens=100):
        self.value, self.usage = value, {"total_tokens": tokens}


class FakeModel:
    """Translates by putting «EN:» before each line, so a test sees what was asked and what came back."""
    def __init__(self):
        self.calls = []

    def respond_json(self, *, name, instructions, input, schema, effort="medium"):
        rows = json.loads(input)
        self.calls.append([r["t"] for r in rows])
        return Result({"items": [{"n": r["n"], "t": "EN:" + r["t"]} for r in rows]})


class MemoryTests(unittest.TestCase):
    def test_numbers_and_dates_are_slots_so_one_entry_serves_every_count_and_day(self):
        self.assertEqual(translate.pattern("3 von 15 Bausteinen geprüft"), ("{0} von {1} Bausteinen geprüft", ["3", "15"]))
        self.assertEqual(translate.pattern("Wiedervorlage 15.02.2027")[0], "Wiedervorlage {0}")
        t = translate.Translator(None, memory_dir=memory({"{0} von {1} Bausteinen geprüft": "{0} of {1} elements checked",
                                                          "Am {0}. März {1} gekündigt": "Terminated on {0} March {1}"}))
        self.assertEqual(t.known("3 von 15 Bausteinen geprüft", "en"), "3 of 15 elements checked")
        self.assertEqual(t.known("7 von 9 Bausteinen geprüft", "en"), "7 of 9 elements checked")
        self.assertEqual(t.known("Am 4. März 2026 gekündigt", "en"), "Terminated on 4 March 2026")
        self.assertIsNone(t.known("Etwas ganz anderes", "en"))

    def test_a_text_put_together_from_parts_is_translated_part_by_part(self):
        t = translate.Translator(None, memory_dir=memory({"Entscheid": "Decision", "Erfolgsaussichten": "Prospects of success", "Deckung": "Cover"}))
        self.assertEqual(t.known("Entscheid: Erfolgsaussichten", "en"), "Decision: Prospects of success")
        self.assertEqual(t.known("Deckung · Sara Exempel", "en"), "Cover · Sara Exempel")

    def test_a_form_of_address_is_translated_around_any_name(self):
        t = translate.Translator(None, memory_dir=memory({}))
        self.assertEqual(t.known("Sehr geehrte Frau Zgraggen", "en"), "Dear Ms Zgraggen")
        self.assertEqual(t.known("Sehr geehrter Herr von Allmen,", "en"), "Dear Mr von Allmen,")
        self.assertIsNone(t.known("Frau", "en"))

    def test_the_answer_is_not_changed_and_carries_each_translation_beside_it(self):
        t = translate.Translator(None, memory_dir=memory({"Deckung": "Cover", "Sehr geehrte Frau Exempel": "Dear Ms Exempel",
                                                          "Vielen Dank für Ihre Unterlagen.": "Thank you for your documents."}))
        letter = "Sehr geehrte Frau Exempel\n\nVielen Dank für Ihre Unterlagen.\nSara Exempel"
        payload = {"id": "Deckung", "case_id": "Deckung", "word": "Deckung", "draft": {"text": letter}}
        before = json.dumps(payload, ensure_ascii=False)
        t.annotate(payload, "en")
        tr = payload.pop("_tr")
        self.assertEqual(json.dumps(payload, ensure_ascii=False), before)  # nothing in the answer moved
        self.assertEqual(tr["Deckung"], "Cover")
        self.assertEqual(tr["Sehr geehrte Frau Exempel"], "Dear Ms Exempel")  # a letter line by line
        self.assertEqual(tr[letter], "Dear Ms Exempel\n\nThank you for your documents.\nSara Exempel")  # and whole; a name stays
        self.assertNotIn("_tr", t.annotate({"word": "Deckung"}, "de"))  # the working language is never translated

    def test_what_a_reader_was_shown_untranslated_is_kept_for_the_memory_but_never_an_id_or_a_file_name(self):
        t = translate.Translator(None, memory_dir=memory({}))
        t.annotate({"id": "case_1", "name": "Nachtrag.eml", "label": "Neu", "summary": "Die Kundschaft hat geantwortet"}, "en")
        self.assertEqual(set(t.missed["en"]), {"Neu", "Die Kundschaft hat geantwortet"})

    def test_the_shipped_memory_keeps_every_slot_of_its_originals(self):
        slots = lambda text: sorted(re.findall(r"\{[^{}]*\}", text))  # noqa: E731
        self.assertGreater(len(MEMORY), 3000)
        self.assertEqual([k for k, v in MEMORY.items() if slots(k) != slots(v)], [])
        self.assertEqual([k for k, v in MEMORY.items() if not v.strip() or v == k], [])


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.store = CaseStore(Path(tempfile.mkdtemp()))
        self.addCleanup(self.store.close)
        self.model = FakeModel()

    def translator(self, **more):
        return translate.Translator(self.store, mode="model", model_factory=lambda *a: self.model, memory_dir=memory({"Deckung": "Cover"}), **more)

    def wait(self, t):
        for _ in range(100):
            if t._worker is None or not t._worker.is_alive():
                return
            time.sleep(0.02)

    def test_the_model_translates_what_the_memory_lacks_once_and_the_case_keeps_it(self):
        case = self.store.create_case("Fall", {}, "t")
        t = self.translator()
        first = t.annotate({"word": "Deckung", "summary": "Die Kundschaft hat geantwortet"}, "en", case_id=case["id"])
        self.assertEqual(first["_tr"], {"Deckung": "Cover"})
        self.assertEqual(first["_tr_wait"], 1)  # on its way
        self.wait(t)
        again = t.annotate({"summary": "Die Kundschaft hat geantwortet"}, "en", case_id=case["id"])
        self.assertEqual(again["_tr"], {"Die Kundschaft hat geantwortet": "EN:Die Kundschaft hat geantwortet"})
        self.assertNotIn("_tr_wait", again)
        self.assertEqual(self.model.calls, [["Die Kundschaft hat geantwortet"]])  # asked once, the memory's word never
        self.assertEqual(t.spent(), 100)
        self.store.delete_case(case["id"], "t")  # its translations go with the case
        self.assertIsNone(self.store.translation("en", translate.sha("Die Kundschaft hat geantwortet")))

    def test_the_daily_budget_stops_the_model_and_the_memory_alone_never_calls_it(self):
        t = self.translator(token_budget=100)
        t.annotate({"summary": "Erster Satz der Akte"}, "en")
        self.wait(t)
        out = t.annotate({"summary": "Zweiter Satz der Akte"}, "en")  # the budget is spent: nothing is queued
        self.wait(t)
        self.assertNotIn("_tr_wait", out)
        self.assertEqual(len(self.model.calls), 1)
        quiet = translate.Translator(self.store, mode="memory", model_factory=lambda *a: self.model, memory_dir=memory({}))
        self.assertNotIn("_tr_wait", quiet.annotate({"summary": "Dritter Satz der Akte"}, "en"))
        self.assertEqual(len(self.model.calls), 1)


class ApiTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.mkdtemp()
        self.app = create_app(load_settings({"CASEPATH_DATA_DIR": folder, "CASEPATH_DEV_USER": "t"}), model_factory=lambda: None)
        self.client = TestClient(self.app)

    def test_a_reader_of_english_gets_translations_beside_the_answer_and_a_reader_of_german_the_answer_alone(self):
        german = self.client.get("/api/workflows").json()
        english = self.client.get("/api/workflows", headers={"x-casepath-lang": "en"}).json()
        self.assertNotIn("_tr", german)
        tr = english.pop("_tr")
        self.assertEqual(english, german)
        self.assertEqual(tr.get("Mietmangel"), MEMORY["Mietmangel"])
        self.assertNotIn("_tr", self.client.get("/api/workflows", headers={"x-casepath-lang": "fr"}).json())  # not offered

    def test_a_page_is_translated_on_request_and_the_missing_texts_are_for_reviewers(self):
        got = self.client.post("/api/translate", json={"lang": "en", "texts": ["Mietmangel", "Ein Satz, den niemand kennt"]}).json()
        self.assertEqual(got["_tr"], {"Mietmangel": MEMORY["Mietmangel"]})
        self.assertEqual(got["_tr_wait"], 0)  # no model in this deployment: nothing is on its way
        missing = self.client.get("/api/translate/missing").json()
        self.assertIn("Ein Satz, den niemand kennt", [t["text"] for t in missing["texts"]])
        self.assertEqual(self.client.get("/api/health").json()["translate"]["mode"], "memory")
        self.assertEqual(self.client.post("/api/translate", json={"lang": "xx", "texts": []}).status_code, 422)


class PageTests(unittest.TestCase):
    def test_text_is_shown_translated_and_everything_stored_or_sent_stays_the_original(self):
        self.assertIn("const esc = (value) => raw(tr(value));", SCRIPT)
        self.assertIn('if (reading()) headers["x-casepath-lang"] = LANG;', SCRIPT)
        # a value put into a field, an id, an address is never translated
        self.assertEqual(re.findall(r'(?:value|href|data-item|data-orig|data-text)="\$\{esc\(', SCRIPT), [])
        # the letter: read translated, edited and sent as written
        self.assertIn("""readingLetter() ? 'data-reading="1"'""", SCRIPT)
        self.assertIn("el.dataset.reading ? ((S.blockEdits || {})[el.dataset.orig] ?? el.dataset.orig)", SCRIPT)
        self.assertIn('id="letter-original"', SCRIPT)
        self.assertIn("const text = doc.text || \"\";", SCRIPT)  # what is copied comes from the case, not from the screen

    def test_the_language_changes_in_place(self):
        self.assertIn("let LANG = ", SCRIPT)
        self.assertIn("async function setLang(next)", SCRIPT)
        self.assertIn('data-lang="${l}"', SCRIPT)
        self.assertNotIn('href="?lang=', SCRIPT)  # no reload


if __name__ == "__main__":
    unittest.main()
