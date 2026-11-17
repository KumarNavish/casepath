"""What CasePath shows, in the reader's language.

Cases are worked in German. A reader who switches the page to English gets what CasePath says and writes in English.
Nothing in a case changes for that: the API answers as always and carries, under "_tr", the translation of each text
the answer contains. The page shows the translation where it shows the text and keeps the original for everything it
saves, copies or sends, so a letter goes out as written and a value is stored as entered.

A translation comes from, in this order:

1. the memory shipped with the product (casepath/web/i18n/<language>.json): the product's own wording, the legal
   areas' catalogues and the examples. Numbers and dates are placeholders ({0}, {1} …), so one entry serves every count
   and every day;
2. what this deployment's model translated before (the store's table «translations», deleted with its case);
3. the model, where the deployment allows it (CASEPATH_TRANSLATE=model): in the background, a bounded batch at a time,
   inside a daily token budget (CASEPATH_TRANSLATE_TOKENS). The answer says how many texts are still on their way
   ("_tr_wait"); the page asks again and the text changes when it is there.

Without the model (the default, and every preview) a text the memory does not know stays in its original language.
"""
import hashlib
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

SOURCE = "de"  # the language cases are worked in
LANGUAGES = ("en",)  # what a reader may switch to
NUMBER = re.compile(r"\d+(?:[.,:'’/\-]\d+)*")
SLOT = re.compile(r"\{(\d+)\}")
LETTER = re.compile(r"[^\W\d_]")
# Keys whose values are never wording: identifiers, addresses of things, times.
SKIP = re.compile(r"(^|_)(id|ids|sha256|sha|hash|href|url|path|at|by|seq|version|media_type|op|token|email|owner|deputy|reference)$")
# Keys whose single words are wording (a title, a label), so a miss is worth a translation.
WORDING = {"title", "short_title", "label", "headline", "word", "text", "question", "why", "reason", "summary", "note", "lead",
           "meaning", "changed", "detail", "what", "action", "subject", "stand", "status_line", "next", "weil", "name_shown"}
ROLE_MARK = re.compile(r"\s*\((?:VN|GP)\)")
FILE = re.compile(r"\.[A-Za-z0-9]{2,5}$")
MEMORY_DIR = Path(__file__).with_name("i18n")
BATCH_TEXTS, BATCH_CHARS = 40, 6000

INSTRUCTIONS = (
    "You translate texts from a Swiss legal-protection insurer's case work into {language} for a colleague who reads "
    "{language}. Each item is one line of a case: a fact, a question, a step, a line of a letter or of a document. "
    "Translate each item on its own, plainly and naturally, as a careful human translator would. Keep names of people "
    "and companies, numbers, dates, amounts, reference numbers, file names and citations of law (for example "
    "«Art. 259d OR») exactly as they are. Keep leading dashes and bullets. A text that is already in {language}, or "
    "that is only a name, comes back unchanged. Answer with every item, by its number."
)
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["items"],
          "properties": {"items": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["n", "t"],
                                                              "properties": {"n": {"type": "integer"}, "t": {"type": "string"}}}}}}
NAMES = {"en": "English", "de": "German"}


def pattern(text):
    """The text with each number as a slot, and the numbers: «3 von 15» → («{0} von {1}», ["3", "15"])."""
    values = []

    def slot(match):
        values.append(match.group(0))
        return "{%d}" % (len(values) - 1)
    return NUMBER.sub(slot, text), values


def fill(translation, values):
    try:
        return SLOT.sub(lambda m: values[int(m.group(1))], translation)
    except IndexError:
        return None


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def wording(value):
    return len(value) > 1 and bool(LETTER.search(value))


def texts(payload, key=""):
    """Every text of an answer with whether a miss is worth translating: (text, worth)."""
    if isinstance(payload, dict):
        for k, v in payload.items():
            if k.startswith("_tr") or SKIP.search(k):
                continue
            yield from texts(v, k)
    elif isinstance(payload, (list, tuple)):
        for v in payload:
            yield from texts(v, key)
    elif isinstance(payload, str) and wording(payload):
        worth = (" " in payload.strip() or key in WORDING) and not FILE.search(payload.strip())
        yield payload, worth
        short = ROLE_MARK.sub("", payload)  # a party's role is shown without its mark («Mieterin (VN)» as «Mieterin»)
        if short != payload and wording(short):
            yield short, worth


class Translator:
    def __init__(self, store=None, *, mode="memory", model_factory=None, token_budget=300_000, memory_dir=None):
        self.store, self.mode, self.model_factory, self.token_budget = store, mode, model_factory, token_budget
        self.memory = {}
        for language in LANGUAGES:
            file = Path(memory_dir or MEMORY_DIR) / f"{language}.json"
            self.memory[language] = json.loads(file.read_text(encoding="utf-8")) if file.exists() else {}
        self.missed = {language: {} for language in LANGUAGES}  # text → how often asked (for whoever fills the memory)
        self._lock = threading.Lock()
        self._queue = {}  # (language, text) → case_id
        self._worker = None
        self.error = None

    # ---- one text ----
    def known(self, text, language, depth=0):
        """The translation of one line, or None."""
        memory = self.memory.get(language) or {}
        line = text.strip()
        if not line:
            return None
        hit = memory.get(line)
        if hit is None:
            shape, values = pattern(line)
            hit = memory.get(shape) if values else None
            hit = fill(hit, values) if hit is not None else None
        if hit is None and self.store is not None and self.mode != "off":
            hit = self.store.translation(language, sha(line))
        if hit is None and depth < 2:  # put together from parts («Entscheid: …», «… · …»): each part where it is known
            for sep in (" · ", ": ", "; ", " – "):
                if sep in line:
                    parts = [(part, self.known(part, language, depth + 1) if wording(part) else None) for part in line.split(sep)]
                    if any(t is not None for _, t in parts):
                        hit = sep.join(t if t is not None else part for part, t in parts)
                        break
        if hit is None:
            return None
        return text[:len(text) - len(text.lstrip())] + hit + text[len(text.rstrip()):]

    def lines(self, text, language):
        """A text of several lines, line by line; None where no line is known."""
        if "\n" not in text:
            return self.known(text, language)
        parts = [(line, self.known(line, language)) for line in text.split("\n")]
        return "\n".join(t if t is not None else line for line, t in parts) if any(t is not None for _, t in parts) else None

    # ---- an answer ----
    def annotate(self, payload, language, *, case_id=None, token=None, model=True):
        """Adds "_tr" (text → translation) for every text of the answer that has one, and "_tr_wait" where the model is
        still translating some. The answer itself is not changed."""
        if language not in LANGUAGES or self.mode == "off" or not isinstance(payload, dict):
            return payload
        out, wait = {}, []
        for text, worth in texts(payload):
            if text in out:
                continue
            whole = self.lines(text, language)
            if whole is not None and whole != text:
                out[text] = whole
            for line in (text.split("\n") if "\n" in text else ()):
                t = self.known(line, language) if wording(line) else None
                if t is not None and t != line:
                    out[line] = t
            for line in (text.split("\n") if "\n" in text else (text,)):
                if worth and wording(line) and self.known(line, language) is None:
                    self.missed[language][line.strip()] = self.missed[language].get(line.strip(), 0) + 1
                    wait.append(line.strip())
        payload["_tr"] = out
        if wait and model and self.mode == "model":
            queued = self.ask(wait, language, case_id=case_id, token=token)
            if queued:
                payload["_tr_wait"] = queued
        return payload

    # ---- the model, in the background ----
    def spent(self):
        return self.store.translation_spent(datetime.now(timezone.utc).date().isoformat()) if self.store is not None else 0

    def ask(self, lines, language, *, case_id=None, token=None):
        """Queues what the model should translate; returns how many texts are on their way (0: none will come)."""
        if self.mode != "model" or self.model_factory is None or self.store is None or self.spent() >= self.token_budget:
            return 0
        with self._lock:
            for line in lines:
                self._queue.setdefault((language, line), case_id)
            waiting = len(self._queue)
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._work, args=(token,), name="casepath-translate", daemon=True)
                self._worker.start()
        return waiting

    def _work(self, token):
        try:
            model = self.model_factory(token) if token else self.model_factory()
        except TypeError:
            model = self.model_factory()
        model = getattr(model, "reading", None) or model
        if model is None:
            with self._lock:
                self._queue.clear()
            return
        while True:
            with self._lock:
                language = next((lang for lang, _ in self._queue), None)
                batch, size = [], 0
                for (lang, line), case_id in list(self._queue.items()):
                    if lang != language or len(batch) >= BATCH_TEXTS or size + len(line) > BATCH_CHARS and batch:
                        continue
                    batch.append((line, case_id))
                    size += len(line)
            if not batch or self.spent() >= self.token_budget:
                with self._lock:
                    self._queue.clear()
                return
            try:
                rows, tokens = self.translate([line for line, _ in batch], language, model)
                self.store.translations_put(language, [(sha(line), t, case_id) for (line, case_id), t in zip(batch, rows) if t], tokens)
                self.error = None
            except Exception as error:  # noqa: BLE001  a failed batch is dropped; the texts stay as written and are asked again later
                self.error = type(error).__name__
            with self._lock:
                for line, _ in batch:
                    self._queue.pop((language, line), None)

    def translate(self, lines, language, model):
        """One call: the lines in, their translations out in the same order (None where the model left one out)."""
        result = model.respond_json(name="translation", instructions=INSTRUCTIONS.format(language=NAMES.get(language, language)),
                                    input=json.dumps([{"n": n, "t": line} for n, line in enumerate(lines)], ensure_ascii=False),
                                    schema=SCHEMA, effort="low")
        got = {row.get("n"): row.get("t") for row in (result.value or {}).get("items", []) if isinstance(row, dict)}
        usage = result.usage or {}
        tokens = int(usage.get("total_tokens") or (usage.get("input_tokens", 0) + usage.get("output_tokens", 0)) or 0)
        return [got.get(n) if isinstance(got.get(n), str) and got.get(n).strip() else None for n in range(len(lines))], tokens
