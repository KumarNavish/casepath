"""The most urgent thing leads: a deadline the customer must meet, ending soon, is the prepared action («Frist wahren»).

A deadline the customer must meet is a statutory one of the customer, or a date a court, an authority or the other side
set for the customer; never an obligation of the other side, never a date the insurer set itself. When one is not yet
met (its condition holds, reading a step the file does not show as not taken) and ends within the backbone's threshold
(``urgent.days``), the prepared action is the backbone's ``urgent.kind``: a short message to the customer saying what must
be done by when and where (from the deadline's data, ``wahren``, and the file), that acting now protects their rights,
that cover is examined in parallel, with the template for the customer's own letter attached where the area has one.
The stage's own action follows («danach»). It never fires for a deadline whose condition the file establishes as not met
(such a deadline is not listed at all), nor for one that has passed. Within ``urgent.dringend`` days it is «dringend».

Deadlines are stated plainly, here for every letter: «Die Frist für die Einsprache gegen den Strafbefehl endet am
16.11.2026 (Art. 354 Abs. 1 StPO).» Model-free.
"""
import re

from .clock import parse_date

ISO = re.compile(r"\d{4}-\d{2}-\d{2}")
SET_BY_OTHERS = {"gegenpartei", "behoerde"}  # who may set a date the customer must meet (the insurer's own asks are not)
ARTICLE = {"vorschlag": "den", "begehren": "das", "einwände": "die", "einwand": "den"}  # by the head noun's end; else «die»


def day(value):
    d = parse_date(value)
    return d.strftime("%d.%m.%Y") if d else None


def dated(item):
    return bool(ISO.fullmatch(str(item.get("value") or "")))


def customers(item):
    """Whether a deadline item is one the customer must meet: statutory and the customer's, or a date a court, an
    authority or the other side set for the customer (read from the file, or held by the running account)."""
    if item.get("kind") != "deadline" or item.get("direction") == "ab":
        return False
    if item.get("account"):
        return item.get("party") == "kunde" and item.get("set_by") in SET_BY_OTHERS
    if item.get("origin") == "law":
        return item.get("party", "kunde") == "kunde"
    return bool(item.get("set_by_others"))


def ours(item):
    """A date the insurer must meet: one the running account holds for Protekta (a reply the customer or a firm asks for)."""
    return item.get("kind") == "deadline" and bool(item.get("account")) and item.get("party") == "versicherer"


def open_condition(item):
    """A deadline that depends on a fact the file leaves open (beyond «not yet done»): shown once, compactly, never leads."""
    return bool(item.get("condition"))


def days_left(item, look):
    d = parse_date(item.get("value")) if dated(item) else None
    return (d - look).days if d else None


def find(items, rule, look, stage):
    """The deadline that makes «Frist wahren» the prepared action, or None: the customer's, dated, without an open
    condition, not passed, ending within ``rule["days"]`` of the day the case is looked at, at a stage the rule names."""
    if not rule or stage not in (rule.get("stages") or ()):
        return None
    rows = [(n, i["value"], i) for i in items if customers(i) and not open_condition(i) and not i.get("possible")
            and (n := days_left(i, look)) is not None and 0 <= n <= int(rule.get("days", 10))]
    return min(rows, key=lambda r: (r[0], r[1]))[2] if rows else None


def lead(items, look, within=30):
    """The one deadline the card head shows: the most urgent of the customer's or the insurer's (statutory, set by a court,
    an authority or the other side, or held by the account for the customer or for us) that is open and ends within
    ``within`` days; else the latest that has passed. Never one that depends on an open fact, never the other side's."""
    rows = [(days_left(i, look), i) for i in items if (customers(i) or ours(i) or (i.get("account") and i.get("party") == "kunde"))
            and dated(i) and not open_condition(i) and not i.get("concerns")]
    coming = [(n, i) for n, i in rows if 0 <= n <= within]
    if coming:
        return min(coming, key=lambda r: (r[0], r[1]["value"]))[1]
    passed = [(n, i) for n, i in rows if n < 0]
    return max(passed, key=lambda r: (r[0], r[1]["value"]))[1] if passed else None


def urgency(item, look, rule):
    """«dringend» within the rule's ``dringend`` days, «Frist» within its ``days``, else None (and «abgelaufen» once passed)."""
    n = days_left(item, look)
    if n is None:
        return None
    if n < 0:
        return "abgelaufen"
    return "dringend" if n <= int((rule or {}).get("dringend", 3)) else "Frist" if n <= int((rule or {}).get("days", 10)) else None


def phrase(title):
    """«die Einsprache gegen den Strafbefehl …», «den Rechtsvorschlag …», «das Erstreckungsbegehren …»: a deadline's
    title with its article, a leading adjective in lower case («die schriftliche Einsprache …»)."""
    words = str(title or "").split()
    if not words:
        return "die Frist"
    if len(words) > 1 and re.fullmatch(r"[A-ZÄÖÜ][a-zäöüß]+e", words[0]) and words[1][:1].isupper():  # «Schriftliche Einsprache»
        words[0] = words[0].lower()
    noun = next((w for w in words if w[:1].isupper()), words[0]).lower()
    article = next((a for end, a in ARTICLE.items() if noun.endswith(end)), "die")
    return f"{article} {' '.join(words)}"


def basis_text(basis):
    """An article as the letter cites it, without brackets inside brackets: «(kantonales Recht, Entzug nach Art. 16 SVG)»."""
    return re.sub(r"\s*\(([^()]*)\)", r", \1", str(basis or "")).strip()


def sentence(item, with_basis=True):
    """A deadline as a letter states it, plainly: what ends when, with its article; never a rule's condition, never a
    title in quotation marks. ``sentence`` in the deadline's data words it where the rule below reads badly."""
    title = (item.get("label") or {}).get("de") or item.get("what") or "die Frist"
    when = day(item.get("value"))
    basis = f" ({basis_text(item['legal_basis'])})" if with_basis and item.get("legal_basis") else ""
    if item.get("sentence") and when:
        return item["sentence"].replace("{datum}", when).rstrip(".") + basis + "."
    if not when:
        if item.get("due_text") and item.get("due_text") != "Datum fehlt":
            return f"Die Frist für {phrase(title)}: {item['due_text']}{basis}."
        return f"Für {phrase(title)} läuft eine Frist; bitte handeln Sie umgehend{basis}."
    if item.get("direction") == "ab":
        return f"Frühestens ab {when}: {title}{basis}."
    if title.startswith("Verjährung "):
        return f"Die Verjährungsfrist {title[len('Verjährung '):]} endet am {when}{basis}."
    if re.match(r"(Bedenkfrist|Höchstfrist|Frist)\b", title):
        return f"Die {title} endet am {when}{basis}."
    if title.startswith("Fälligkeit "):
        return f"Die {title} tritt am {when} ein{basis}."
    return f"Die Frist für {phrase(title)} endet am {when}{basis}."


def condition_text(item):
    """An open condition, compactly, for «Fristen»: «nur bei einer Ordnungsbusse» (a «solange …» about a step not yet
    taken is what the list assumes and is left out)."""
    text = re.sub(r",?\s*solange\b.*$", "", str(item.get("condition") or "")).strip(" ,")
    return text or None


def cites(graph, refs):
    law = (graph or {}).get("law") or {}
    return [law[str(r).split("#", 1)[1]]["cite"] for r in refs or () if str(r).split("#", 1)[-1] in law]


def what_to_do(item, graph, facts):
    """What the customer does, where, as the deadline's data says it (``wahren``), each sentence with its articles; the
    place from the file where its fact names one that fits («die Staatsanwaltschaft Beispielkanton»)."""
    data = item.get("wahren") or {}
    if not data.get("tun"):
        return ""
    where = data.get("wo") or ""
    named = str((facts or {}).get((data.get("wo_fact") or {}).get("fact") or "") or "")
    if named and re.search((data.get("wo_fact") or {}).get("match") or r"(?!)", named, re.I):
        where = f"der {named}" if not re.match(r"(der|die|dem|den|das)\b", named, re.I) else named
    out = []
    for row in [{"text": data["tun"], "law": data.get("law")}] + list(data.get("dazu") or ()):
        text = str(row["text"]).replace("{wo}", where).rstrip(".")
        c = cites(graph, row.get("law"))
        out.append(f"{text} ({', '.join(c)})." if c else f"{text}.")
    return " ".join(out)


def consequence(item):
    """What follows when the deadline is missed, as the deadline's data says it (with its article)."""
    return str(item.get("missed") or "").strip()


def reason(item):
    """The card's «Weil» line for «Frist wahren»: the consequence, without its article (that is one click away)."""
    text = re.sub(r"\s*\([^()]*Art\.[^()]*\)", "", consequence(item)).strip().rstrip(".")
    return text or f"{sentence(item, with_basis=False).rstrip('.')}"
