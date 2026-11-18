"""Letters the customer sends in their own name: templates per area, offered with the insurer's letter.

In two of seven studied files the insurer drafted a letter the customer sent himself (a notice of defect with a deadline,
a letter to the landlord), and the most useful advice to a customer is often such a letter. Each area module may list
them (``customer_letters``): an id, a title, to whom it goes, the condition on facts under which it helps (``when``),
its parts (each legal statement with the articles it rests on, each article a law entry with its verbatim passage; a
part with no legal content says ``"plain": true``), the gaps the customer fills in (``fill``), the deadline the letter
sets (``sets``), the statutory deadline by which it must arrive (``must_arrive``: a deadline of the module), and how it
is sent (``send``) and further advice (``advice``), each either resting on law (an article whose passage contains the
words the instruction relies on, ``requires``) or said as prudence («Wir empfehlen …»).

A template is offered with the legal assessment (A5) when its condition holds, and with the first request (A1) too when
time is short (its statutory deadline within ``SHORT_DAYS`` days, or not computable). It is always marked as a template
for the customer, never as sent by the insurer; its gaps are «[einsetzen: …]», for the customer to fill, never invented.
The insurer's own letter refers to it in one sentence. Model-free.
"""
from datetime import date, timedelta
import re

from .. import house
from .clock import parse_date
from .workflows import CatalogueError, condition_facts, evaluate_condition, holds_unless_done

SHORT_DAYS = 30  # a statutory deadline of the customer within this many days: the template goes with the first request
FILL = "[einsetzen: "
KINDS = {"letter", "instruction"}
SPECIAL = {"absender", "empfaenger", "heute", "frist", "frist_bis"}
# words that state a legal rule, a right or a duty: a part that holds one needs an article with its passage
LEGAL = re.compile(r"\b(Art\.|muss|müssen|verpflichtet|Anspruch|berechtigt|Recht auf|nichtig|missbräuchlich|verwirkt|verjährt|gesetzlich)", re.I)
INSURER = re.compile(rf"\b({re.escape(house.active().name)}|Rechtsschutzversicherung|unsere Versicherte)", re.I)


def filler(what):
    return f"{FILL}{what}]"


def _refs(row):
    refs = row.get("law") or []
    return refs if isinstance(refs, list) else [refs]


def _check_refs(refs, law, name):
    for ref in refs:
        key = str(ref).split("#", 1)[1] if str(ref).startswith("law#") else None
        if not key or not str((law.get(key) or {}).get("passage") or "").strip():
            raise CatalogueError(f"{name}: {ref!r} must name a law entry with its verbatim passage")


def _supported(row, law, name, what):
    """An instruction to the customer: resting on law (each word it relies on is in a cited passage) or said as prudence
    («Wir empfehlen …», never «muss»)."""
    if not str(row.get("text") or "").strip():
        raise CatalogueError(f"{name}: {what} needs its text")
    if row.get("basis") == "prudence":
        if "empfehlen" not in row["text"] or re.search(r"\b(muss|müssen)\b", row["text"]):
            raise CatalogueError(f"{name}: {what} said as prudence is advice («Wir empfehlen …»), never a duty")
        return
    refs = _refs(row)
    if not refs:
        raise CatalogueError(f"{name}: {what} rests on an article with its passage or is said as prudence")
    _check_refs(refs, law, name)
    passages = " ".join(str((law.get(str(r).split("#", 1)[1]) or {}).get("passage") or "") for r in refs).lower()
    for word in row.get("requires") or []:
        if word.lower() not in passages:
            raise CatalogueError(f"{name}: {what} says «{word}», which the cited law does not support")


def supported(row, law, name, what):
    """An instruction resting on law (each word it relies on in a cited passage) or said as prudence: the check every
    sentence that tells the customer what to do passes (a template's, a deadline's «wahren»)."""
    return _supported(row, law, name, what)


def validate(module, law, where, fact_ids):
    """A customer letter needs a condition on facts, an article with a passage for every legal statement, and no
    instruction to the customer that the cited law does not support. ``law``: the entries the module may cite;
    ``fact_ids``: the facts of the module and the backbone (placeholders name them)."""
    letters = module.get("customer_letters", [])
    if not isinstance(letters, list):
        raise CatalogueError(f"{where}: customer_letters must be a list")
    deadlines = {d.get("id") for d in module.get("deadlines", [])}
    seen = set()
    for row in letters:
        name = f"{where}: customer letter {row.get('id')!r}" if isinstance(row, dict) else f"{where}: a customer letter"
        if not isinstance(row, dict) or any(not row.get(k) for k in ("id", "title", "to", "to_dative", "when", "parts")):
            raise CatalogueError(f"{name} needs id, title, to, to_dative, when and parts")
        if row["id"] in seen or not re.fullmatch(r"[a-z][a-z0-9_-]*", row["id"]):
            raise CatalogueError(f"{name}: its id must be unique, lower case")
        seen.add(row["id"])
        if row.get("kind", "letter") not in KINDS:
            raise CatalogueError(f"{name}: kind is letter or instruction")
        if not isinstance(row["when"], dict) or not condition_facts(row["when"]):
            raise CatalogueError(f"{name}: the condition names facts of the case")
        fills = row.get("fill") or {}
        for part in row["parts"]:
            text = str((part or {}).get("text") or "")
            if not text.strip():
                raise CatalogueError(f"{name}: a part needs its text")
            if INSURER.search(text):
                raise CatalogueError(f"{name}: a template is the customer's own letter, never the insurer's")
            if part.get("plain") is True:
                if LEGAL.search(text):
                    raise CatalogueError(f"{name}: «{text[:60]}» states law: it needs an article with its passage")
            else:
                refs = _refs(part)
                if not refs:
                    raise CatalogueError(f"{name}: «{text[:60]}» is a legal statement without an article and its passage")
                _check_refs(refs, law, name)
            for slot in re.findall(r"\{([a-z_0-9]+)\}", text):
                if slot not in SPECIAL and slot not in fact_ids and slot not in fills:
                    raise CatalogueError(f"{name}: placeholder {{{slot}}} is neither a fact nor a gap with its label (fill)")
        if row.get("sets"):
            sets = row["sets"]
            if not (isinstance(sets.get("days"), int) or isinstance(sets.get("weeks"), int)) or not sets.get("text"):
                raise CatalogueError(f"{name}: the deadline it sets needs days or weeks and its words")
            if sets.get("basis") == "prudence":  # a period the letter proposes (a reply in ten days): no duty, no article
                if re.search(r"\b(muss|müssen)\b", sets["text"]):
                    raise CatalogueError(f"{name}: a period the letter only proposes states no duty")
            else:
                _supported(sets, law, name, "the deadline it sets")
        if row.get("must_arrive"):
            arrive = row["must_arrive"]
            if arrive.get("deadline") not in deadlines:
                raise CatalogueError(f"{name}: must_arrive names a deadline of the module")
            _supported(arrive, law, name, "the date it must arrive by")
        if not row.get("send"):
            raise CatalogueError(f"{name}: says how it is sent")
        _supported(row["send"], law, name, "how it is sent")
        for advice in row.get("advice") or []:
            _supported(advice, law, name, "an advice")
    return letters


# Rendering -----------------------------------------------------------------------------------------------------------

def _day(value):
    d = value if isinstance(value, date) else parse_date(value)
    return d.strftime("%d.%m.%Y") if d else None


def _cites(graph, refs):
    law = (graph or {}).get("law") or {}
    return [law[str(r).split("#", 1)[1]]["cite"] for r in refs if str(r).split("#", 1)[-1] in law]


MONTHS = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember")


def _month(value):
    """A date known to the month («2026-07») as the customer writes it: «Juli 2026»; None for anything else."""
    m = re.fullmatch(r"(\d{4})-(\d{2})", str(value or "").strip())
    return f"{MONTHS[int(m.group(2)) - 1]} {m.group(1)}" if m and 1 <= int(m.group(2)) <= 12 else None


def _value(graph, facts, slot, fills):
    value = (facts or {}).get(slot)
    if value not in (None, "") and not isinstance(value, bool):
        definition = next((f for f in (graph or {}).get("facts") or () if f["id"] == slot), {})
        return (_day(value) or _month(value) or str(value)) if definition.get("type") == "date" else str(value)
    if slot in fills:
        return filler(fills[slot])
    definition = next((f for f in (graph or {}).get("facts") or () if f["id"] == slot), {})
    return filler(re.sub(r"\s*\(.*$", "", str(definition.get("question") or slot)).rstrip("?"))


def _statutory(deadlines, letter):
    """The customer's statutory deadline the letter must meet: the deadline item of the module, or None."""
    arrive = letter.get("must_arrive") or {}
    return next((d for d in deadlines or () if d.get("key") == arrive.get("deadline")), None)


def sets_date(letter, today):
    sets = letter.get("sets") or {}
    if not sets:
        return None
    return today + timedelta(days=sets.get("days", 0), weeks=sets.get("weeks", 0))


def render(graph, letter, facts, sender, recipient, deadlines, today):
    """The template as the customer receives it: a heading that says it is theirs to send, the letter (or the short
    instruction), and the advice with its articles. Gaps are «[einsetzen: …]», never invented."""
    fills = letter.get("fill") or {}
    recipient = letter.get("empfaenger") or recipient  # a letter to an authority goes to it, never to the other side named in it
    due = _statutory(deadlines, letter)
    due_day = _day(due.get("value")) if due else None
    own = {"absender": sender or filler("Ihr Vor- und Nachname"), "empfaenger": recipient or filler("Name der Empfängerin oder des Empfängers"),
           "heute": _day(today), "frist": _day(sets_date(letter, today)) or "", "frist_bis": due_day or filler("Datum")}
    fill = lambda text: re.sub(r"\{([a-z_0-9]+)\}", lambda m: own[m.group(1)] if m.group(1) in own else _value(graph, facts, m.group(1), fills), text)
    body = []
    for part in letter["parts"]:
        text = fill(part["text"]).strip()
        cites = _cites(graph, _refs(part))
        body.append(f"{text[:-1]} ({', '.join(cites)})." if cites and text.endswith(".") else f"{text} ({', '.join(cites)})" if cites else text)
    advice = []
    if letter.get("must_arrive"):
        arrive = letter["must_arrive"]
        sofort = next((d for d in (graph or {}).get("deadlines") or () if d["id"] == arrive["deadline"]), {}).get("period") == "sofort"
        when = (f"spätestens am {due_day}" if due_day else "also ohne Aufschub" if sofort
                else "das massgebende Datum steht nicht fest; bitte klären Sie es umgehend mit uns")
        advice.append(f"{fill(arrive['text']).rstrip('.')}, {when} ({', '.join(_cites(graph, _refs(arrive)))}).")
    if letter.get("sets"):
        sets = letter["sets"]
        basis = _cites(graph, _refs(sets))
        advice.append(f"Die Frist im Schreiben ({sets['text']}) ist auf den {own['frist']} gesetzt, wenn Sie es heute senden; senden Sie es später, "
                      f"verschieben Sie das Datum entsprechend" + (f" ({', '.join(basis)})." if basis else "."))
    for row in [letter["send"]] + list(letter.get("advice") or []):
        basis = _cites(graph, _refs(row))
        text = fill(row["text"]).rstrip(".")
        advice.append(f"{text} ({', '.join(basis)})." if basis else f"{text}.")
    if letter.get("kind") == "instruction":
        head = [f"{letter['title']} (von Ihnen selbst zu erklären; kein Schreiben von {house.active().name})", ""]
        lines = head + [f"– {b}" for b in body] + ["", "Hinweise:"] + [f"– {a}" for a in advice]
        return "\n".join(lines)
    registered = "eingeschrieben" in letter["send"]["text"].lower()
    lines = [f"Vorlage für Ihr Schreiben an {letter['to']} (in Ihrem eigenen Namen zu senden; kein Schreiben von {house.active().name})", "",
             own["absender"], filler("Ihre Adresse"), "", own["empfaenger"], filler("Adresse"), "",
             f"{filler('Ort')}, {own['heute']}", ""]
    if registered:
        lines += ["Einschreiben", ""]
    lines += [f"{fill(letter.get('subject') or letter['title'])}", "", house.active().letters.greeting, ""]
    for b in body:
        lines += [b, ""]
    lines += [house.active().letters.closing, "", own["absender"], "", "—", "Hinweise zur Vorlage:"] + [f"– {a}" for a in advice]
    return "\n".join(lines)


def heading(letter):
    """The quiet line under the insurer's letter: «Vorlage für Ihr Schreiben an die Vermieterschaft»."""
    if letter.get("kind") == "instruction":
        return letter["title"]
    return f"Vorlage für Ihr Schreiben an {letter['to']}"


def evaluate(graph, facts, deadlines, sender=None, recipient=None, today=None):
    """The templates whose condition holds on the case's facts: [{id, title, heading, to, to_dative, text, short, due,
    offered_with, cites}]. ``deadlines``: the case's deadline items (the module's computed ones by key)."""
    today = today or date.today()
    statutory = {d["id"]: d for d in (graph or {}).get("deadlines") or ()}
    out = []
    for letter in (graph or {}).get("customer_letters") or ():
        if evaluate_condition(letter["when"], facts or {}) is not True and not holds_unless_done(letter["when"], facts or {}):
            continue  # a step the file does not show as taken (an objection) is read as not taken, as for its deadline
        due = _statutory(deadlines, letter)
        due_day = parse_date(due.get("value")) if due else None
        sofort = (statutory.get((letter.get("must_arrive") or {}).get("deadline")) or {}).get("period") == "sofort"
        short = bool(letter.get("must_arrive")) and (sofort or (due is not None and (due_day is None or (due_day - today).days <= SHORT_DAYS)))
        cites = list(dict.fromkeys(c for part in letter["parts"] for c in _cites(graph, _refs(part))))
        out.append({"id": letter["id"], "title": letter["title"], "heading": heading(letter), "to": letter["to"], "to_dative": letter["to_dative"],
                    "kind": letter.get("kind", "letter"), "text": render(graph, letter, facts, sender, recipient, deadlines, today),
                    "short": short, "due": due_day.isoformat() if due_day else None, "cites": cites,
                    "deadline": (letter.get("must_arrive") or {}).get("deadline"), "posted": bool((letter.get("must_arrive") or {}).get("posted")),
                    "offered_with": ["A5", "A1"] if short else ["A5"]})
    return out


def referral(item):
    """The one sentence the insurer's letter refers to the template with; never its title in quotation marks. Where the
    deadline is kept by posting, not by arrival (``must_arrive.posted``), it says so."""
    if item.get("template_kind") == "instruction":
        text = f"Wie Sie dabei vorgehen, beschreibt die beigelegte Anleitung"
    else:
        text = f"Für Ihr Schreiben an {item['to']} legen wir Ihnen eine Vorlage bei, die Sie prüfen, ergänzen und in Ihrem eigenen Namen senden"
    day = _day(item.get("due"))
    if day and item.get("posted"):
        return text + f"; die Frist endet am {day}."
    return text + (f"; es muss {item['to_dative']} spätestens am {day} zugehen." if day and item.get("template_kind") != "instruction"
                   else f"; spätestens am {day}." if day else ".")


def with_letter(items, events, kind):
    """The templates that go out with one of the insurer's letters: those offered with it, and one whose sentence was
    offered as a line of the first request (an area observed in practice) and that the handler ticked."""
    last = {}
    for e in events or ():
        if e.get("kind") == "letter.line" and e.get("item_id"):
            last[e["item_id"]] = bool(e.get("included"))
    return [i for i in items or () if i.get("kind") == "customer_letter"
            and (kind in (i.get("offered_with") or ()) or kind == "A1" and last.get(f"hint:cl-{i['key']}"))]


def referrals(items, kind):
    """The sentences for one of the insurer's letters (A1 or A5): one per template offered with it. A template a jurist
    marked «Änderung nötig» (``review``) stays to be copied on its own, but the letter does not refer to it by itself."""
    return [referral(i) for i in items or () if i.get("kind") == "customer_letter" and kind in (i.get("offered_with") or ()) and not i.get("review")]
