"""The ways to proceed of an area once the customer has answered: the options a legal assessment (A5) may recommend, the
answers to the questions customers ask about the area's rules, and the sentences about the case that go with them.

An area may have an options file (``areas/options/<area>.json``, format ``casepath.options/1``). It lies outside the
composed workflow, with its own version and hash, so no area module changes and the frozen expert study keeps its items.
It holds:

- ``law``: its own rows (cite, SR number, article, passage, ``verified``), each passage found word for word in the saved
  official text (``verify``, the check of area modules; ``python -m casepath areas --sources <folder>``). A part of an
  advice, an answer or a condition cites rows of the file or of the area (its module and the backbone), and only rows
  checked against the official text (``verified: true``);
- ``implies``: a fact the file settles by another («schriftlich gemeldet» is «gemeldet»), applied before the assessment's
  evaluation only (``implied``); the case's facts and items are untouched;
- ``wishes``: what the customer may want, a yes/no fact each, with the words the letter says it in;
- ``case_lines``: the sentences «In Ihrem Fall» may state about a fact of the case, ``wording``: the sentences that join
  the parts, ``sofern``: per fact, the phrase a recommendation resting on a presumed value begins with;
- ``answers``: per key point and intent (the word stems a question about it holds), the parts of the answer, each with
  its article and the words of the passage it relies on (``requires``), or said as prudence («Wir empfehlen …», never a
  duty), and its state: «beantwortet», or «bedingt» with its next step;
- ``options``: the ways to proceed per wish, each with what triggers it, its conditions («vorher»: a step that must have
  happened; «anspruch»: an element of the right, proven later; each with its fact, or none: «nicht geprüft»), its advice,
  the documents it needs, what would change it, its practice count from the module and whether it may be proposed.

An option holds only on facts the run established and the source checker accepted (or the handler set); a presumed value
holds «unter Vorbehalt», a contradictory reading never. Nothing here computes an amount, a reduction or a deadline.
Model-free.
"""
import functools
import hashlib
import json
from pathlib import Path
import re

from . import area, customer_letters
from .workflows import CatalogueError, _check_condition as check_condition, evaluate_condition

FORMAT = "casepath.options/1"
DIR = Path(__file__).with_name("areas") / "options"
MAX_PASSAGE_WORDS = 80  # a whole paragraph: a deposit's conditions are one sentence too long for a module's 40 words
KINDS = ("vorher", "anspruch")
STATES = ("beantwortet", "bedingt")
NEXT = ("discuss", "residual")
PLACEHOLDERS = {"wuensche", "daten", "datum", "posten", "frage", "wert", "bedingung", "betrag"}
WORDING = ("wish", "replies_all", "replies_some", "claims", "claim_amount", "claim_line", "join", "conditional", "discuss")
PLURAL = ("replies_all", "replies_some")
NEGATIONS = {"nicht", "kein", "keine", "keinen", "keiner", "keinem", "nie", "niemals", "ohne"}
MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
NOT_RECORDED = "nicht erfasst"
REVIEW = {"geprueft": "geprüft", "aenderung": "in Prüfung", "frage": "Frage offen"}
UNREVIEWED = "nicht juristisch geprüft"
REVIEW_ORDER = ("Frage offen", "in Prüfung", UNREVIEWED, "geprüft")  # the weakest first


# Loading ------------------------------------------------------------------------------------------------------------

def path(area_id):
    return DIR / f"{area_id}.json"


@functools.lru_cache(maxsize=None)
def _raw(area_id):
    p = path(area_id) if area_id and re.fullmatch(r"[a-z][a-z0-9_-]*", str(area_id)) else None
    return p.read_bytes() if p is not None and p.is_file() else None


@functools.lru_cache(maxsize=None)
def _loaded(area_id):
    raw = _raw(area_id)
    if raw is None:
        return None
    workflow = area.workflow(area_id)
    if workflow is None:
        raise CatalogueError(f"options {area_id}: no area of that id")
    return validate(json.loads(raw.decode("utf-8")), workflow)


def load(area_id):
    """The area's validated options file, or None when the area has none. Read and checked once."""
    return _loaded(area_id) if area_id else None


def sha256(area_id):
    """The options file's SHA-256, as an approval records it; None without a file."""
    raw = _raw(area_id) if area_id else None
    return hashlib.sha256(raw).hexdigest() if raw is not None else None


def areas():
    """The ids of the areas that have an options file."""
    return sorted(p.stem for p in DIR.glob("*.json"))


# Law ------------------------------------------------------------------------------------------------------------------

def law_of(data, workflow):
    """Every row a part may cite: the area's (module and backbone) and the file's own."""
    return {**((workflow or {}).get("law") or {}), **(data.get("law") or {})}


def _keys(refs):
    return [str(r).split("#", 1)[1] for r in refs or () if str(r).startswith("law#")]


def rows(refs, data, workflow):
    law = law_of(data, workflow)
    return [{"key": k, "cite": law[k]["cite"], "passage": law[k]["passage"], "verified": bool(law[k].get("verified")),
             "sr": law[k]["sr"], "article": law[k]["article"]} for k in _keys(refs) if k in law]


def cite(refs, data, workflow):
    """The articles of a part as a letter names them: «Art. 259d OR, Art. 259g Abs. 1 OR»."""
    return ", ".join(dict.fromkeys(r["cite"] for r in rows(refs, data, workflow)))


def verify(data, texts):
    """Each of the file's own law rows whose passage occurs word for word in its article of the official text:
    {key: True|False} (the check of area modules, area.verify)."""
    return area.verify({"law": data.get("law") or {}}, texts)


# Validation -----------------------------------------------------------------------------------------------------------

def _placeholders(text, where):
    for name in re.findall(r"\{([a-z_]+)\}", str(text)):
        if name not in PLACEHOLDERS:
            raise CatalogueError(f"{where}: placeholder {{{name}}} is not one of {', '.join(sorted(PLACEHOLDERS))}")


def _part(part, law, where, *, sentence, points=None):
    """One part of an answer or an advice: resting on verified law (each word it relies on in a cited passage), said as
    prudence (never a duty; an answer's prudence part says «empfehlen» itself, an advice's follows «Wir empfehlen Ihnen,»
    in the letter), or plain (stating no law). A part may hold a key point's own sentence (``follows``)."""
    if not isinstance(part, dict):
        raise CatalogueError(f"{where}: a part is an object")
    if part.get("follows"):
        if part["follows"] not in (points or {}):
            raise CatalogueError(f"{where}: follows names {part['follows']!r}, which is no key point of the area")
        text = points[part["follows"]]["follows"]
    else:
        text = str(part.get("text") or "")
    if not text.strip():
        raise CatalogueError(f"{where}: a part needs its text")
    if part.get("basis") == "prudence":
        if re.search(r"\b(muss|müssen)\b", text) or (sentence and "empfehlen" not in text):
            raise CatalogueError(f"{where}: «{text[:50]}» said as prudence is advice («Wir empfehlen …»), never a duty")
        return
    if part.get("plain") is True:
        if customer_letters.LEGAL.search(text):
            raise CatalogueError(f"{where}: «{text[:50]}» states law: it needs an article with its passage")
        return
    keys = _keys(part.get("law"))
    if not keys or len(keys) != len(part.get("law") or ()):
        raise CatalogueError(f"{where}: «{text[:50]}» rests on an article with its passage or is said as prudence")
    for key in keys:
        row = law.get(key)
        if not row or not str(row.get("passage") or "").strip():
            raise CatalogueError(f"{where}: law#{key} must name a law entry with its verbatim passage")
        if row.get("verified") is not True:
            raise CatalogueError(f"{where}: law#{key} is not checked against the official text; it cannot be cited")
    passages = " ".join(law[k]["passage"] for k in keys).lower()
    for word in part.get("requires") or ():
        if str(word).lower() not in passages:
            raise CatalogueError(f"{where}: «{text[:50]}» says «{word}», which the cited law does not support")


def _fact_condition(row, facts, where):
    cond = {k: row[k] for k in ("fact", "is", "in", "known") if k in row}
    check_condition(cond, facts, where)
    return cond


def element_ids(data):
    """The elements a jurist reviews in the file (review.py): each option, each answer, each sentence about the case and
    each joining sentence."""
    return ([f"empfehlung.{o['id']}" for o in data.get("options") or ()]
            + [f"antwort.{a['points'][0]}.{a['intent']}" for a in data.get("answers") or ()]
            + [f"fall.{c['id']}" for c in data.get("case_lines") or ()] + [f"wortlaut.{k}" for k in data.get("wording") or {}])


def _count(observed):
    m = re.fullmatch(r"(\d+) von (\d+)", str((observed or {}).get("count") or ""))
    return (int(m.group(1)), int(m.group(2))) if m else None


def validate(data, workflow):
    """Fail closed on an options file the area cannot carry: its format and version, its own law rows (each with its
    verbatim passage, checked against the official text before an advice, answer or condition cites it), every word a
    part relies on in a cited passage, facts and values of the workflow, a «sofern» phrase for every fact a condition
    names, a stated advice for every element of a right the file does not check, documents of the module, answers for
    key points of the area, practice counts equal to the module's, and open questions about elements of the file."""
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise CatalogueError(f"options file format must be {FORMAT}")
    where = f"options {data.get('area')}"
    if data.get("area") != workflow.get("id"):
        raise CatalogueError(f"{where}: names area {data.get('area')!r}, not {workflow.get('id')!r}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}\.\d+", str(data.get("version") or "")) or data.get("status") not in ("draft", "reviewed"):
        raise CatalogueError(f"{where}: needs a version (YYYY-MM-DD.n) and a status (draft or reviewed)")
    for key in ("law", "wishes", "case_lines", "wording", "sofern", "answers", "options"):
        if key not in data:
            raise CatalogueError(f"{where}: missing {key!r}")
    facts = {f["id"]: f for f in workflow["facts"]}
    laws = workflow.get("laws") or {}
    for key, row in data["law"].items():
        if key in (workflow.get("law") or {}):
            raise CatalogueError(f"{where}: law entry {key!r} is already a row of the area; give the file's own row its own key")
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", key) or not isinstance(row, dict):
            raise CatalogueError(f"{where}: law entry {key!r} is malformed")
        for field in ("cite", "sr", "article", "passage"):
            if not str(row.get(field) or "").strip():
                raise CatalogueError(f"{where}: law entry {key!r} needs {field} (a cited article needs its verbatim passage)")
        if row["sr"] not in laws:
            raise CatalogueError(f"{where}: law entry {key!r} names SR {row['sr']}, which the backbone does not list")
        if len(row["passage"].split()) > MAX_PASSAGE_WORDS:
            raise CatalogueError(f"{where}: the passage of {key!r} is longer than {MAX_PASSAGE_WORDS} words")
        if not isinstance(row.get("verified"), bool):
            raise CatalogueError(f"{where}: law entry {key!r} must say verified true or false")
        if (row["sr"], row["article"]) not in area.cited_articles(row["cite"], laws):
            raise CatalogueError(f"{where}: law entry {key!r}: its cite does not name Art. {row['article']}")
    law = law_of(data, workflow)
    for i, rule in enumerate(data.get("implies") or ()):
        here = f"{where}: implication {i + 1}"
        if not isinstance(rule, dict) or not rule.get("when") or not isinstance(rule.get("then"), dict):
            raise CatalogueError(f"{here} needs when and then")
        check_condition(rule["when"], facts, here)
        then = rule["then"]
        if set(then) != {"fact", "is"}:
            raise CatalogueError(f"{here}: then sets one fact to one value")
        check_condition(then, facts, here)
    wishes = {}
    for w in data["wishes"]:
        if (facts.get(w.get("fact")) or {}).get("type") != "boolean" or not str(w.get("text") or "").strip() or w["fact"] in wishes:
            raise CatalogueError(f"{where}: a wish names a yes/no fact of the area once, with its words")
        wishes[w["fact"]] = w
    seen = set()
    for c in data["case_lines"]:
        here = f"{where}: case line {c.get('id')!r}"
        if not re.fullmatch(r"[a-z][a-z0-9_]*", str(c.get("id") or "")) or c["id"] in seen or not str(c.get("text") or "").strip():
            raise CatalogueError(f"{here} needs its own id and its text")
        seen.add(c["id"])
        _fact_condition(c, facts, here)
        _placeholders(c["text"], here)
    for key in WORDING:
        value = data["wording"].get(key)
        texts = list(value.values()) if key in PLURAL and isinstance(value, dict) else [value]
        if key in PLURAL and (not isinstance(value, dict) or set(value) != {"one", "many"}):
            raise CatalogueError(f"{where}: wording {key} says it for one message and for many (one, many)")
        if not all(isinstance(t, str) and t.strip() for t in texts):
            raise CatalogueError(f"{where}: wording {key} is missing")
        for t in texts:
            _placeholders(t, f"{where}: wording {key}")
    if set(data["wording"]) - set(WORDING):
        raise CatalogueError(f"{where}: unknown wording {sorted(set(data['wording']) - set(WORDING))}")
    for fact, phrase in data["sofern"].items():
        if fact not in facts or not str(phrase or "").strip():
            raise CatalogueError(f"{where}: sofern names a fact of the area with its phrase ({fact!r})")
    points = {p["id"]: p for p in workflow.get("key_points") or ()}
    intents = {}
    for a in data["answers"]:
        here = f"{where}: answer {a.get('intent')!r}"
        if not a.get("points") or any(p not in points for p in a["points"]):
            raise CatalogueError(f"{here}: answers name key points of the area ({a.get('points')!r})")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", str(a.get("intent") or "")) or a["intent"] in intents:
            raise CatalogueError(f"{here}: an intent has its own id")
        intents[a["intent"]] = a
        if not a.get("stems") or not all(isinstance(s, str) and s.strip() == s and s == s.lower() and s for s in a["stems"] + list(a.get("with") or [])):
            raise CatalogueError(f"{here}: stems (and with) are lower-case word beginnings")
        if a.get("state") not in STATES:
            raise CatalogueError(f"{here}: its state is beantwortet or bedingt")
        if a["state"] == "bedingt" and (a.get("next") or {}).get("kind") not in NEXT:
            raise CatalogueError(f"{here}: a conditional answer names its next step (discuss or residual)")
        if not a.get("parts"):
            raise CatalogueError(f"{here} needs its parts")
        for n, part in enumerate(a["parts"]):
            _part(part, law, f"{here}, part {n + 1}", sentence=True, points=points)
    options = {}
    for o in data["options"]:
        here = f"{where}: option {o.get('id')!r}"
        if not re.fullmatch(r"[a-z][a-z0-9_]*", str(o.get("id") or "")) or o["id"] in options or not str(o.get("title") or "").strip():
            raise CatalogueError(f"{here} needs its own id and a title")
        options[o["id"]] = o
        if o.get("wish") not in wishes:
            raise CatalogueError(f"{here}: its wish is one of the file's wishes")
        for cond in o.get("when") or ():
            _fact_condition(cond, facts, f"{here}, when")
        if o.get("asked") is not None and o["asked"] not in intents:
            raise CatalogueError(f"{here}: asked names an intent of the answers")
        if not isinstance(o.get("propose"), bool):
            raise CatalogueError(f"{here}: says whether it may be proposed (propose true or false)")
        for n, cond in enumerate(o.get("conditions") or ()):
            ch = f"{here}, condition {n + 1}"
            if cond.get("kind") not in KINDS or not str(cond.get("text") or "").strip():
                raise CatalogueError(f"{ch}: a condition is «vorher» or «anspruch», with its text")
            _part({"law": cond.get("law"), "requires": cond.get("requires"), "text": cond["text"]}, law, ch, sentence=False)
            if cond.get("fact"):
                _fact_condition(cond, facts, ch)
                if cond["fact"] not in data["sofern"]:
                    raise CatalogueError(f"{ch}: its fact {cond['fact']!r} needs a «sofern» phrase")
            elif cond["kind"] == "anspruch":  # an element of the right the file does not check: the advice states it
                articles = {(r["sr"], r["article"]) for r in rows(cond["law"], data, workflow)}
                stated = " ".join(str(p.get("text") or "") for p in o.get("advice") or ()
                                  if articles & {(r["sr"], r["article"]) for r in rows(p.get("law"), data, workflow)}).lower()
                if not all(str(w).lower() in stated for w in cond.get("requires") or ()):
                    raise CatalogueError(f"{ch}: «{cond['text']}» is not checked; an advice part citing the same article must state it")
        for fact in [o["wish"]] + [c["fact"] for c in o.get("when") or ()]:
            if fact not in data["sofern"]:
                raise CatalogueError(f"{here}: its trigger {fact!r} needs a «sofern» phrase")
        if not o.get("advice"):
            raise CatalogueError(f"{here} needs its advice")
        for n, part in enumerate(o["advice"]):
            _part(part, law, f"{here}, advice {n + 1}", sentence=False, points=points)
        documents = {d["id"] for d in workflow["documents"]}
        for need in o.get("needs") or ():
            if need.get("document") not in documents:
                raise CatalogueError(f"{here}: needs names a document of the module ({need.get('document')!r})")
        for entry in o.get("changes_if") or ():
            kind, _, name = str(entry).partition(":")
            if not name and entry not in facts:
                raise CatalogueError(f"{here}: changes_if names a fact of the area ({entry!r})")
            if name and not ((kind == "need" and name in documents) or (kind == "condition" and name.isdigit() and int(name) < len(o.get("conditions") or ()))):
                raise CatalogueError(f"{here}: changes_if {entry!r} names no need or condition of the option")
        if o.get("observed") is not None:
            observed = o["observed"]
            m = re.fullmatch(r"stages\.([a-z_]+)\.suggestions\[(\d+)\]", str(observed.get("from") or ""))
            step = next((s for s in workflow["steps"] if m and s["id"] == m.group(1)), None)
            recorded = ((step or {}).get("suggestions") or [])[int(m.group(2))] if step and int(m.group(2)) < len((step or {}).get("suggestions") or []) else None
            if not _count(observed) or not recorded or recorded.get("observed") != observed["count"]:
                raise CatalogueError(f"{here}: observed {observed.get('count')!r} is not the module's count at {observed.get('from')!r}")
    for a in data["answers"]:
        nxt = a.get("next") or {}
        if nxt.get("kind") == "residual" and nxt.get("option") not in options:
            raise CatalogueError(f"{where}: answer {a['intent']!r}: its next step names an option of the file")
    ids = set(element_ids(data))
    from . import review
    raw = area.AREAS / f"{workflow['id']}.json"
    module_ids = set(review.module_ids(area.load(raw))) if raw.is_file() else set()
    for q in data.get("open_questions") or ():
        about = q.get("about") if isinstance(q.get("about"), list) else [q.get("about")]
        if not str(q.get("text") or "").strip() or not about or any(a not in ids and a != review.WHOLE for a in about):
            raise CatalogueError(f"{where}: the open question «{str(q.get('text'))[:60]}» is about {q.get('about')!r}, which is no element here")
        if q.get("linked") is not None and q["linked"] not in module_ids:
            raise CatalogueError(f"{where}: the open question «{str(q.get('text'))[:60]}» links {q['linked']!r}, which is no element of the module")
    return data


# The case's facts as the assessment reads them --------------------------------------------------------------------------

def implied(facts, data):
    """The facts with the file's implications applied to a copy: a fact the file settles by another, where it is still
    unknown («schriftlich gemeldet» ⇒ «gemeldet»). A value the case holds is never overridden."""
    out = dict(facts or {})
    for rule in (data or {}).get("implies") or ():
        then = rule["then"]
        if out.get(then["fact"]) is None and evaluate_condition(rule["when"], out) is True:
            out[then["fact"]] = then["is"]
    return out


def facts_named(data):
    """Every fact the file's ways to proceed rest on: their triggers, conditions and what would change them, and the
    facts of its implications (an empty set without a file)."""
    from .workflows import condition_facts
    out = set()
    for o in (data or {}).get("options") or ():
        out.add(o["wish"])
        out |= {c["fact"] for c in o.get("when") or ()} | {c["fact"] for c in o.get("conditions") or () if c.get("fact")}
        out |= {e for e in o.get("changes_if") or () if ":" not in e}
    for rule in (data or {}).get("implies") or ():
        out |= condition_facts(rule["when"]) | {rule["then"]["fact"]}
    return out


def implied_by(fact, facts, data):
    """The facts an implied value of ``fact`` rests on (the conditions of the implication that gave it), or []."""
    for rule in (data or {}).get("implies") or ():
        if rule["then"]["fact"] == fact and (facts or {}).get(fact) is None and evaluate_condition(rule["when"], facts or {}) is True:
            from .workflows import condition_facts
            return sorted(condition_facts(rule["when"]))
    return []


# Intents ------------------------------------------------------------------------------------------------------------

def answers_for(data, point_ids):
    """The file's answer rows for these key points, in the file's order."""
    wanted = set(point_ids or ())
    return [a for a in (data or {}).get("answers") or () if wanted & set(a["points"])]


def intent(question, answers):
    """The intent a question asks, among answer rows: one whose stem the lower-cased question holds (and one of its
    ``with`` words, where given); of several, the longest stem wins, the first on a tie. None when none matches."""
    q = str(question or "").lower()
    best = None
    for n, a in enumerate(answers or ()):
        if a.get("with") and not any(w in q for w in a["with"]):
            continue
        for stem in a["stems"]:
            if stem in q and (best is None or len(stem) > best[0]):
                best = (len(stem), n, a)
    return best[2] if best else None


# Amounts ------------------------------------------------------------------------------------------------------------

NUMBER = r"\d{1,3}(?:['’]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?"
AMOUNT = re.compile(rf"(?:\b(?:CHF|SFr\.?|Fr\.)\s?({NUMBER}))|(?:\b({NUMBER})(?:\.[–-]|\s?(?:CHF|Franken)\b))|\b(\d{{1,3}}(?:['’]\d{{3}})+(?:[.,]\d{{1,2}})?)")


def _number(text):
    try:
        return float(re.sub(r"['’]", "", text).replace(",", "."))
    except ValueError:
        return None


def amounts(text):
    """Every amount written in a text: «CHF 85», «Fr. 85.–», «85.–», «1'200.50», «85 Franken»; never a date («05.09.2026»)
    or a bare number."""
    out = set()
    for m in AMOUNT.finditer(str(text or "")):
        value = _number(next(g for g in m.groups() if g))
        if value is not None:
            out.add(value)
    return out


def amount_of(text):
    """The number of an amount as the reader wrote it («rund CHF 85» → 85.0), or None."""
    found = amounts(text)
    if found:
        return sorted(found)[0]
    m = re.search(NUMBER, str(text or ""))
    return _number(m.group(0)) if m else None


# Review state of an element ------------------------------------------------------------------------------------------

def review_state(area_id, element, marks):
    """«geprüft», «nicht juristisch geprüft» (never marked, or changed since the mark), «Frage offen» or «in Prüfung», from
    the jurists' marks that hold for the content as it is now (review.Model.current)."""
    mark = (marks or {}).get(f"{area_id}:{element}")
    return REVIEW.get((mark or {}).get("mark"), UNREVIEWED)


def weakest(states):
    states = list(states)
    return next((s for s in REVIEW_ORDER if s in states), UNREVIEWED)


# Options --------------------------------------------------------------------------------------------------------------

def practice(option):
    """«Praxis: 2 von 7» or «Praxis: nicht erfasst»."""
    return f"Praxis: {(option.get('observed') or {}).get('count') or NOT_RECORDED}"


def _condition_state(cond, facts, weak):
    fact = cond.get("fact")
    if not fact:
        return "nicht geprüft"
    value = facts.get(fact)
    if value is None:
        return "widersprüchlich" if (weak or {}).get(fact) == "conflicting" else "offen"
    holds = evaluate_condition({k: cond[k] for k in ("fact", "is", "in", "known") if k in cond}, facts)
    if holds is False:
        return "nicht erfüllt"
    return "vermutet" if (weak or {}).get(fact) else "erfüllt"


def _weak(weak):
    """``weak`` as {fact: "presumed" | "conflicting"}: a set of fact ids counts as presumed."""
    if isinstance(weak, dict):
        return weak
    return {f: "presumed" for f in weak or ()}


def evaluate(data, facts, weak=(), flags=None, marks=None, intents=(), area_id=None):
    """Each option on the case's facts (the file's implications applied): {id, title, wish, state: holds | open | fails,
    conditions [{text, kind, fact, state, law}], triggers [{fact, state}], weak [facts], review, observed, propose, held}.
    A trigger (the wish, ``when``, a question with the intent ``asked``) false fails it, unknown leaves it open. A «vorher»
    condition decides holds, open or fails by its fact, and without a fact («nicht geprüft») leaves the option open; an
    «anspruch» condition without a fact is «nicht geprüft» and the option may hold (the advice states it). A presumed value
    is «vermutet»: the option holds with it, «unter Vorbehalt»; a contradictory reading leaves it open."""
    if not data:
        return []
    weak = _weak(weak)
    facts = implied(facts, data)
    area_id = area_id or data.get("area")
    asked = set(intents or ())
    out = []
    for o in data["options"]:
        triggers = []
        for cond in [{"fact": o["wish"], "is": True}] + list(o.get("when") or ()):
            triggers.append({"fact": cond["fact"], "state": _condition_state(cond, facts, weak)})
        conditions = [{"text": c["text"], "kind": c["kind"], "fact": c.get("fact"), "state": _condition_state(c, facts, weak),
                       "law": c.get("law") or [], "expects": {k: c[k] for k in ("is", "in", "known") if k in c}} for c in o.get("conditions") or ()]
        states = [t["state"] for t in triggers] + [c["state"] for c in conditions]
        if "nicht erfüllt" in states or (o.get("asked") and o["asked"] not in asked):
            state = "fails"
        elif any(t["state"] in ("offen", "widersprüchlich") for t in triggers) or any(
                c["state"] in ("offen", "widersprüchlich") or (c["kind"] == "vorher" and c["state"] == "nicht geprüft") for c in conditions):
            state = "open"
        else:
            state = "holds"
        held = bool(flags is not None and getattr(flags, "option", None) and flags.option(o["id"]))
        out.append({"id": o["id"], "title": o["title"], "wish": o["wish"], "state": state, "triggers": triggers, "conditions": conditions,
                    "weak": [x["fact"] for x in triggers + conditions if x["state"] == "vermutet" and x["fact"]],
                    "review": review_state(area_id, f"empfehlung.{o['id']}", marks), "observed": (o.get("observed") or {}).get("count") or NOT_RECORDED,
                    "practice": practice(o), "propose": bool(o.get("propose")), "held": held, "why_not": o.get("why_not")})
    return out


def proposal(data, facts, evaluated):
    """One option per wish the customer has (its fact true, in the file's order of wishes): of that wish's options that
    hold, may be proposed and are not under a jurist's «Änderung nötig» or «Frage», the one practice shows most often,
    else the first in the file. A wish whose options are all open proposes nothing (its ``changes_if`` say what would)."""
    if not data:
        return []
    facts = implied(facts, data)
    order = {o["id"]: n for n, o in enumerate(data["options"])}
    counts = {o["id"]: (_count(o.get("observed")) or (0, 0))[0] for o in data["options"]}
    out = []
    for w in data["wishes"]:
        if facts.get(w["fact"]) is not True:
            continue
        ready = [e for e in evaluated if e["wish"] == w["fact"] and e["state"] == "holds" and e["propose"] and not e["held"]]
        ready.sort(key=lambda e: (-counts[e["id"]], order[e["id"]]))
        if ready:
            out.append(ready[0]["id"])
    return out


def option(data, option_id):
    return next((o for o in (data or {}).get("options") or () if o["id"] == option_id), None)


# Texts ------------------------------------------------------------------------------------------------------------------

def _with_cite(text, refs, data, workflow):
    """A part's sentence with its articles before its own full stop: «… kündigen (Art. 257d Abs. 1 OR).»"""
    text = str(text).strip()
    named = cite(refs, data, workflow)
    if not named:
        return text if text.endswith((".", "»", "?")) else f"{text}."
    return f"{text[:-1]} ({named})." if text.endswith(".") else f"{text} ({named})."


def answer_parts(data, workflow, intent_row, *, template=False, residual=True):
    """The sentences of an answer, each with its articles: a part about the enclosed template only when it goes with the
    letter (``template``), the pointer to what is still missing only when something is (``residual``)."""
    points = {p["id"]: p for p in (workflow or {}).get("key_points") or ()}
    out = []
    for part in intent_row["parts"]:
        if part.get("with_template") and not template:
            continue
        if part.get("with_residual") and not residual:
            continue
        text = points[part["follows"]]["follows"] if part.get("follows") else part["text"]
        out.append(_with_cite(text, [] if part.get("basis") == "prudence" or part.get("plain") else part.get("law"), data, workflow))
    return out


def answer_text(data, workflow, intent_row, *, template=False, residual=True, ask=None):
    """An answer as the letter says it: its parts, and for a conditional answer whose point waits for an answer of the
    customer the question that settles it (``ask``)."""
    parts = answer_parts(data, workflow, intent_row, template=template, residual=residual) if intent_row else []
    if ask:
        parts.append(data["wording"]["conditional"].replace("{frage}", ask.rstrip()))
    return " ".join(parts)


def advice_text(data, workflow, option_id, *, template=False, weak=(), facts=None):
    """An option's advice as it follows «Wir empfehlen Ihnen, »: its parts in order, each law part with its articles; a
    part about the enclosed template only when it goes with the letter; resting on a presumed value, it begins with the
    fact's «sofern» phrase. No full stop: the letter ends the sentence."""
    o = option(data, option_id)
    text = ""
    for part in o["advice"]:
        if part.get("with_template") and not template:
            continue
        piece = part["text"]
        if not (part.get("basis") == "prudence" or part.get("plain")):
            named = cite(part.get("law"), data, workflow)
            piece = f"{piece} ({named})" if named else piece
        text += piece
    text = text.strip()
    if weak:
        phrases = list(dict.fromkeys(data["sofern"][f] for f in weak if f in data["sofern"]))
        if phrases:
            text = f"sofern {' und '.join(phrases)}, {text}"
    return text


def month_year(value):
    """«Juli 2026» for «2026-07»; «05.09.2026» for a day; the value itself otherwise."""
    s = str(value or "")
    if re.fullmatch(r"\d{4}-\d{2}", s):
        return f"{MONTHS[int(s[5:7]) - 1]} {s[:4]}"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return f"{s[8:10]}.{s[5:7]}.{s[:4]}"
    return s


def joined(words):
    """«A», «A und B», «A, B und C»."""
    words = [w for w in words if w]
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " und " + words[-1] if words else ""
