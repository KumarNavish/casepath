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
        # as the real models take it: a conversation, a list of turns (a bare string failed on the pilot, 17.11.2026)
        assert isinstance(input, list) and all(isinstance(turn, dict) and turn.get("role") == "user" for turn in input), "input is a list of turns"
        list(input)  # the Messages model copies the conversation
        rows = json.loads(input[0]["content"])
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
        t = self.translator(token_budget=800)  # a batch is estimated at about 700 tokens and more: one fits, a second would pass the day's ceiling
        t.annotate({"summary": "Erster Satz der Akte"}, "en")
        self.wait(t)
        out = t.annotate({"summary": "Zweiter Satz der Akte"}, "en")  # the budget is spent: nothing is queued
        self.wait(t)
        self.assertNotIn("_tr_wait", out)
        self.assertEqual(len(self.model.calls), 1)
        quiet = translate.Translator(self.store, mode="memory", model_factory=lambda *a: self.model, memory_dir=memory({}))
        self.assertNotIn("_tr_wait", quiet.annotate({"summary": "Dritter Satz der Akte"}, "en"))
        self.assertEqual(len(self.model.calls), 1)


class RealModelTests(unittest.TestCase):
    """The call as the deployed models take it (a fake transport, no network): the Messages model and the chat model."""

    def test_the_messages_model_and_the_chat_model_translate_a_batch(self):
        import httpx
        from casepath.agents.anthropic_model import AnthropicMessagesModel
        from casepath.agents.chat_model import ChatCompletionsModel
        host = "https://adb-1.2.azuredatabricks.net"
        asked = []

        def messages(request):
            body = json.loads(request.content)
            asked.append(json.loads(body["messages"][0]["content"] if isinstance(body["messages"][0]["content"], str) else body["messages"][0]["content"][0]["text"]))
            return httpx.Response(200, json={"id": "m", "stop_reason": "tool_use", "content": [{"type": "tool_use", "id": "tu", "name": body["tools"][0]["name"],
                                  "input": {"items": [{"n": 0, "t": "The customer has replied"}, {"n": 1, "t": "Dear Ms Exempel"}]}}],
                                  "usage": {"input_tokens": 120, "output_tokens": 30}})

        def chat(request):
            return httpx.Response(200, json={"id": "c", "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(
                {"items": [{"n": 0, "t": "The customer has replied"}, {"n": 1, "t": "Dear Ms Exempel"}]})}}], "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}})
        t = translate.Translator(None, memory_dir=memory({}))
        lines = ["Die Kundschaft hat geantwortet", "Sehr geehrte Frau Exempel"]
        base = {"CASEPATH_MODEL_PROVIDER": "databricks", "DATABRICKS_HOST": host, "CASEPATH_MODEL": "m"}
        model = AnthropicMessagesModel(load_settings({**base, "CASEPATH_MODEL_API": "messages"}).model, lambda: "t", transport=httpx.MockTransport(messages))
        rows, tokens = t.translate(lines, "en", model)
        self.assertEqual(rows, ["The customer has replied", "Dear Ms Exempel"])
        self.assertEqual(tokens, 150)
        self.assertEqual(asked[0], [{"n": 0, "t": lines[0]}, {"n": 1, "t": lines[1]}])  # the lines went out as one user turn
        model = ChatCompletionsModel(load_settings(base).model, lambda: "t", transport=httpx.MockTransport(chat))
        rows, tokens = t.translate(lines, "en", model)
        self.assertEqual(rows, ["The customer has replied", "Dear Ms Exempel"])
        self.assertGreater(tokens, 0)


class ShownOnlyTests(unittest.TestCase):
    """The model translates what a page shows and asks for, never a whole answer."""

    def test_an_answer_never_starts_a_translation_and_the_pages_request_does(self):
        model = FakeModel()
        folder = tempfile.mkdtemp()
        app = create_app(load_settings({"CASEPATH_DATA_DIR": folder, "CASEPATH_DEV_USER": "t", "CASEPATH_TRANSLATE": "model"}), model_factory=lambda *a: model)
        client = TestClient(app)
        cid = client.post("/api/cases", json={"title": "Ein Fall, den das Gedächtnis nicht kennt"}).json()["id"]
        got = client.get(f"/api/cases/{cid}", headers={"x-casepath-lang": "en"}).json()
        self.assertNotIn("_tr_wait", got)
        self.assertEqual(model.calls, [])  # reading a case costs nothing
        asked = client.post("/api/translate", json={"lang": "en", "texts": ["Ein Fall, den das Gedächtnis nicht kennt"], "case_id": cid}).json()
        self.assertEqual(asked["_tr_wait"], 1)
        for _ in range(100):
            again = client.post("/api/translate", json={"lang": "en", "texts": ["Ein Fall, den das Gedächtnis nicht kennt"], "case_id": cid}).json()
            if again["_tr"]:
                break
            time.sleep(0.02)
        self.assertEqual(again["_tr"], {"Ein Fall, den das Gedächtnis nicht kennt": "EN:Ein Fall, den das Gedächtnis nicht kennt"})
        self.assertEqual(model.calls, [["Ein Fall, den das Gedächtnis nicht kennt"]])
        self.assertEqual(client.get("/api/health").json()["translate"]["spent_today"], 100)

    def test_the_page_asks_for_what_it_showed_untranslated_each_text_once(self):
        self.assertIn("function wantTranslation(text)", SCRIPT)
        self.assertIn('if (!translates() || text.length < 3 || text.length > 700 || TR_ASKED.has(text)', SCRIPT)
        # the memory is asked too (at no cost): a name the page shortened itself is known to it; the model only where allowed
        self.assertIn('const translates = () => S.translateMode === "memory" || S.translateMode === "model";', SCRIPT)
        self.assertIn('api("/api/translate", { method: "POST"', SCRIPT)


class OnceForTheCasesInScopeTests(unittest.TestCase):
    """The model translates for the named legal areas only; ahead of the readers, once, and what it gave is kept."""

    def setUp(self):
        self.model = FakeModel()
        self.folder = tempfile.mkdtemp()
        self.app = create_app(load_settings({"CASEPATH_DATA_DIR": self.folder, "CASEPATH_DEV_USER": "t", "CASEPATH_TRANSLATE": "model",
                                             "CASEPATH_TRANSLATE_AREAS": "Mietmangel"}), model_factory=lambda *a: self.model)
        self.client = TestClient(self.app)
        self.inside = self.client.post("/api/cases", json={"title": "Schimmel im Bad, den kein Gedächtnis kennt"}).json()["id"]
        self.outside = self.client.post("/api/cases", json={"title": "Ein Arbeitszeugnis, das kein Gedächtnis kennt"}).json()["id"]
        self.app.state.store.select_workflow(self.inside, "mietmangel-handler", "1", "t")
        self.app.state.store.select_workflow(self.outside, "arbeitszeugnis", "1", "t")

    def settle(self):
        for _ in range(200):
            if not self.client.get("/api/translate/cases").json()["waiting"]:
                return
            time.sleep(0.02)

    def test_a_case_outside_the_named_areas_is_never_sent_to_the_model(self):
        asked = self.client.post("/api/translate", json={"lang": "en", "texts": ["Ein Arbeitszeugnis, das kein Gedächtnis kennt"], "case_id": self.outside}).json()
        self.assertEqual(asked["_tr_wait"], 0)
        self.assertEqual(self.client.post("/api/translate", json={"lang": "en", "texts": ["Ein Satz ohne Fall, den niemand kennt"]}).json()["_tr_wait"], 0)
        self.assertEqual(self.model.calls, [])
        inside = self.client.post("/api/translate", json={"lang": "en", "texts": ["Schimmel im Bad, den kein Gedächtnis kennt"], "case_id": self.inside}).json()
        self.assertEqual(inside["_tr_wait"], 1)
        self.settle()

    def test_counting_costs_nothing_and_translating_ahead_is_done_once(self):
        count = self.client.post("/api/translate/cases", json={"lang": "en"}).json()      # dry_run is the default
        self.assertEqual((count["cases"], count["queued"], count["areas"]), (1, 0, ["mietmangel"]))
        self.assertGreater(count["lines"], 0)
        self.assertGreater(count["estimate_tokens"], 0)
        # the estimate is set against a measured run: a full batch of case text (40 lines, about 4,600 characters) cost about 5,800 tokens
        self.assertTrue(5200 <= translate.Translator.estimate(["x" * 116] * 40) <= 6400)
        self.assertEqual(self.model.calls, [])
        started = self.client.post("/api/translate/cases", json={"lang": "en", "dry_run": False}).json()
        self.assertGreater(started["queued"], 0)
        self.settle()
        sent = [line for call in self.model.calls for line in call]
        self.assertIn("Schimmel im Bad, den kein Gedächtnis kennt", sent)
        self.assertNotIn("Ein Arbeitszeugnis, das kein Gedächtnis kennt", sent)
        self.assertEqual(len(sent), len(set(sent)))                                        # each line once
        again = self.client.post("/api/translate/cases", json={"lang": "en"}).json()
        self.assertEqual(again["lines"], 0)                                                # kept: nothing is left to translate
        calls = len(self.model.calls)
        self.client.post("/api/translate/cases", json={"lang": "en", "dry_run": False})
        self.settle()
        self.assertEqual(len(self.model.calls), calls)                                     # and nothing is translated twice

    def test_what_was_translated_once_serves_a_deployment_that_has_the_model_switched_off_again(self):
        self.client.post("/api/translate/cases", json={"lang": "en", "dry_run": False})
        self.settle()
        quiet = TestClient(create_app(load_settings({"CASEPATH_DATA_DIR": self.folder, "CASEPATH_DEV_USER": "t"}), model_factory=lambda: None))
        got = quiet.get(f"/api/cases/{self.inside}", headers={"x-casepath-lang": "en"}).json()
        self.assertEqual(got["_tr"].get("Schimmel im Bad, den kein Gedächtnis kennt"), "EN:Schimmel im Bad, den kein Gedächtnis kennt")


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
        health = self.client.get("/api/health").json()["translate"]
        self.assertEqual((health["mode"], health["error"], health["spent_today"], health["budget"]), ("memory", None, 0, 300000))
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
