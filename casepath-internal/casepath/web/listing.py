"""What the case list says about each case: a title from the case itself, and where it stands in the handler's words.

Model-free; from the item list, the follow-up date, the case's events and files. A historic file cut at a decision
point is looked at as of its own day and listed apart, so its dates never count as overdue among live cases.
"""
from datetime import date, timedelta
import re

from ..process import urgent
from ..process.clock import parse_date
from ..process.letters import customer

RUNNING_DAYS = 21  # a customer's deadline or a set date this close is what the row says
URGENT_DAYS = 3  # this close it is «dringend» (the backbone's urgent.dringend)
HANDLED_ELSEWHERE = re.compile(r"protekta|rechtsschutz|kanzlei|anwalt|versicherer \(|rechtsschutzversicherung", re.I)
REDACTED = re.compile(r"geschw|xxx|^[\W_]*$", re.I)
SALUTATION = re.compile(r"^(Frau|Herr|Fr\.|Hr\.)\s+")
CLOSING = {"A12_still": "keine Rückmeldung", "A12_mitwirkung": "fehlende Mitwirkung", "A12_mitwirkung_kanzlei": "fehlende Mitwirkung",
           "A12_erledigt": "Sache erledigt"}


def as_of(files):
    """The day a historic file is looked at (its cut's «Stand am»), or None for a live case."""
    return next((parse_date((f.get("extraction") or {}).get("cut_of", {}).get("as_of")) for f in files or ()
                 if ((f.get("extraction") or {}).get("cut_of") or {}).get("as_of")), None)


def _name(party):
    name = SALUTATION.sub("", str((party or {}).get("value") or "").strip())
    return None if not name or REDACTED.search(name) else name


# The place or the object of the dispute in the request: an address first, else the first noun phrase that is not a
# party, a person's wish or the insurer; at most five words, never cut inside a word.
ADDRESS = re.compile(r"\b[A-ZÄÖÜ][\wäöüß.-]*(?:gasse|strasse|straße|str\.|weg|platz|allee|ring|rain|matte|halde|quai|graben)\s+\d+[a-z]?\b")
GENERIC = {"hilfe", "unterstützung", "rat", "beratung", "frage", "fragen", "anliegen", "kundschaft", "kunde", "kundin", "versicherung", "protekta",
           "fall", "sache", "problem", "synthetische", "synthetischer", "akte", "herr", "frau", "guten", "tag", "chf", "heute", "seit", "im", "am",
           "die", "der", "das", "dem", "den", "des", "ein", "eine", "einen", "einem", "einer", "ich", "er", "sie", "es", "wir", "ihr", "mein",
           "meine", "meinen", "sein", "seine", "ihre", "ihren", "unser", "unsere", "nach", "wegen", "weil", "dass", "als", "wenn", "bitte", "sehr",
           "geehrte", "geehrter", "hallo", "januar", "februar", "märz", "april", "mai", "juni", "juli", "august", "september", "oktober",
           "november", "dezember", "montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag", "sonntag", "vn", "ag", "gmbh",
           "nachbar", "nachbarin", "nachbarn", "vermieter", "vermieterin", "vermieterschaft", "verwaltung", "arbeitgeber", "arbeitgeberin",
           "arbeitnehmer", "arbeitnehmerin", "mieter", "mieterin", "gegenpartei", "kanzlei", "anwalt", "anwältin", "verkäufer", "verkäuferin",
           "käufer", "käuferin", "unternehmer", "gläubiger", "schuldner", "borger", "darleiherin", "darleiher"}
JOIN = {"im", "in", "an", "am", "der", "des", "die", "dem", "den", "vom", "von", "zur", "zum", "für", "bei", "beim", "aus", "mit", "und", "über",
        "ihrer", "seiner", "ihres", "seines", "eines", "einer", "ihren", "seinen", "auf"}
NOUN = re.compile(r"[A-ZÄÖÜ][\wäöüß'-]+")


PEOPLE_AND_TIME = {"firma", "partei", "vater", "mutter", "bruder", "schwester", "sohn", "tochter", "bekannten", "bekannter", "bekannte",
                   "pöstler", "herrn", "ehemann", "ehefrau", "partner", "partnerin", "autolenkerin", "autolenker", "kollege", "kollegin",
                   "chef", "chefin", "sommer", "winter", "frühling", "herbst", "jahren", "jahr", "jahre", "monaten", "monat", "wochen",
                   "woche", "tagen", "uhr", "mal", "zeit", "mit"}
# words that lead to the object or the place of a dispute: «einen Occasionswagen», «auf der Autobahn», «meinem Sturz»
LEAD = {"der", "die", "das", "dem", "den", "des", "ein", "eine", "einen", "einem", "einer", "mein", "meine", "meinem", "meinen", "meiner",
        "unser", "unsere", "unserem", "unseren", "unserer", "sein", "seine", "seinem", "seinen", "ihr", "ihre", "ihrem", "ihren",
        "am", "im", "beim", "vom", "zum", "zur", "an", "in", "auf", "bei", "aus"}
AMOUNT = re.compile(r"CHF\s?\d[\d'’]*(?:\.\d{2})?")
PLACE = {"im", "an", "in", "auf", "bei", "beim", "aus"}  # not «am»: mostly a day
COMPANY_END = re.compile(r"^(AG|GmbH|SA|Sàrl|KG|Genossenschaft)$")


def dispute_object(request, names=()):
    """Where or what the dispute is about, from the request: an address («Probegasse 7»), else the first noun led by an
    article, a possessive or a preposition of place («einen Occasionswagen», «auf der Autobahn bei Beispielstadt»), with
    what is joined to it; a party, a company, a person, a month or a time is never it. At most five words, never cut
    inside a word; None when the request names nothing else."""
    text = str(request or "")
    found = ADDRESS.search(text)
    if found:
        return found.group(0)
    blocked = {w.lower() for n in names for w in re.findall(r"[\wäöüß'-]+", str(n or ""))}
    words = re.findall(r"[\wäöüß'-]+|[^\w\s]", text)
    company = set()
    for i, word in enumerate(words):  # «Garage Beispiel AG»: the capitalised run before a company form
        if COMPANY_END.match(word):
            j = i
            while j > 0 and NOUN.fullmatch(words[j - 1]):
                j -= 1
            company.update(range(j, i + 1))
    skip = GENERIC | PEOPLE_AND_TIME | blocked
    noun = lambda k: k < len(words) and k not in company and NOUN.fullmatch(words[k]) and words[k].lower() not in skip

    def phrase(i):
        out, j = [words[i]], i + 1
        while j < len(words) and len(out) < 5:  # «Sturz auf der Baustelle», «Zahlungsbefehl des Betreibungsamts»
            tail = []
            while j < len(words) and words[j].lower() in JOIN and len(out) + len(tail) < 4:
                tail.append(words[j])
                j += 1
            if tail and noun(j):
                out += tail + [words[j]]
                j += 1
                continue
            break
        return " ".join(out)

    def led():
        for i, word in enumerate(words):
            if word.lower() not in LEAD:
                continue
            if word.lower() in PLACE and i and noun(i - 1):  # «Schimmel im Badezimmer»: what is in the place comes first
                return phrase(i - 1)
            k = i + 1
            for _ in range(2):  # up to two words between: «an der», «unserem abgeschlossenen»
                if noun(k) or k >= len(words) or not re.fullmatch(r"[a-zäöüß]+", words[k]):
                    break
                k += 1
            if noun(k):
                return phrase(k)
        first = next((i for i in range(len(words)) if noun(i)), None)
        return phrase(first) if first is not None else None
    thing = led()
    amount = AMOUNT.search(text)  # a sum named before anything else is what the dispute is about («CHF 8'000»)
    if amount and (not thing or amount.start() < text.find(thing)):
        return amount.group(0)
    return thing


def display_title(case, items, short_title, renamed=False):
    """After preparation, the area and the parties («Darlehen · Lea Brunner ./. Max Beispiel»); the area and the customer
    when the other side is not known («Darlehen · Lea Brunner»); the area and the place or object of the dispute when
    neither is («Mietmangel · Probegasse 7»), else the area alone. A title a person gave, or a case not yet prepared,
    keeps its own; a raw file name is never the title of a prepared case, and a title never ends in «…»."""
    if renamed or not short_title or not any(i["kind"] in {"next_action", "summary", "party"} for i in items or ()):
        return case["title"]
    parties = [i for i in items if i["kind"] == "party"]
    own = customer(parties)
    role = lambda p: (p.get("label") or {}).get("de") if isinstance(p.get("label"), dict) else str(p.get("label") or "")
    other = next((p for p in parties if p is not own and _name(p) and not HANDLED_ELSEWHERE.search(f"{role(p)} {p.get('value')}")), None)
    if _name(own) and other:
        return f"{short_title} · {_name(own)} ./. {_name(other)}"
    if _name(own):
        return f"{short_title} · {_name(own)}"
    request = next((str(i.get("value") or "") for i in items if i["kind"] == "summary" and i.get("value")), "")
    thing = dispute_object(request, [p.get("value") for p in parties] + [short_title])  # never the area's own word again
    return f"{short_title} · {thing}" if thing else short_title


def parties_line(items):
    """The parties as the list's second line and the rail's: «Lea Beispiel ./. Muster Immobilien AG», the customer alone
    when the other side is not known; None when the file names nobody."""
    parties = [i for i in items or () if i["kind"] == "party"]
    own = customer(parties)
    role = lambda p: (p.get("label") or {}).get("de") if isinstance(p.get("label"), dict) else str(p.get("label") or "")
    other = next((p for p in parties if p is not own and _name(p) and not HANDLED_ELSEWHERE.search(f"{role(p)} {p.get('value')}")), None)
    names = [x for x in (_name(own), _name(other)) if x]
    return " ./. ".join(names) or None


def headline(case, items, short_title, renamed=False):
    """What the case is about, in the list's first line and the rail's: the area and the place or object of the dispute
    («Kündigung Miete · Testgasse 4»), the area alone when the request names neither; a title a person gave stands."""
    if renamed or not short_title or not any(i["kind"] in {"next_action", "summary", "party"} for i in items or ()):
        return case.get("display_title") or case["title"]
    parties = [i for i in items if i["kind"] == "party"]
    request = next((str(i.get("value") or "") for i in items if i["kind"] == "summary" and i.get("value")), "")
    thing = dispute_object(request, [p.get("value") for p in parties] + [short_title])
    return f"{short_title} · {thing}" if thing else short_title


def closing_reason(action):
    """The three or four words a closing gives as its reason: «keine Rückmeldung», «Sache erledigt» …"""
    return (action or {}).get("closing") or CLOSING.get((action or {}).get("form") or "", "Sache erledigt")


def next_step(action):
    """The next step as the list shows it; a closing once, with its reason: «Dossier schliessen: keine Rückmeldung»."""
    if not action:
        return None
    if action.get("action") in {"A12", "close"}:
        return f"Dossier schliessen: {closing_reason(action)}"
    return (action.get("label") or {}).get("de") or action.get("value")


def _day(d):
    return f"{d.day:02d}.{d.month:02d}."


def waiting_for(action):
    kind = (action or {}).get("action")
    return "Gegenpartei" if kind in {"A8", "A9"} else "Kanzlei" if kind in {"A10"} else "Kundschaft"


def stand(*, closed, run_status, new_files, items, follow_up, events, completed_at, files, today=None, historic=None):
    """Where a case stands, in the handler's words, with the rank by which the list orders it (what needs the handler
    first) and the date that goes with it: {kind, text, rank, date}. A historic file (``historic``: clock.historic) is
    looked at as of its own day, the cut's «Stand am» or its newest document, so nothing in it is overdue."""
    ref = as_of(files) or (parse_date((historic or {}).get("newest")) if historic else None) or today or date.today()
    row = lambda kind, text, rank, day=None: {"kind": kind, "text": text, "rank": rank, "date": day.isoformat() if day else None}
    if run_status in {"queued", "running"}:
        return row("working", "wird vorbereitet", 7)
    if run_status in {"paused", "failed", "interrupted"}:
        return row("paused", "angehalten", 6)
    if run_status != "completed":
        return row("new", "nicht vorbereitet", 5)
    if new_files:
        return row("arrived", "neue Unterlagen", 0)
    action = next((i for i in items if i["kind"] == "next_action"), None)
    due = parse_date(follow_up) if follow_up else None
    copied = any(e.get("kind") == "letter.copied" and str(e.get("at") or "") > str(completed_at or "") for e in events or ())
    if closed or copied:
        if (action or {}).get("action") in {"A12", "close"} and closed:
            return row("closed", "erledigt", 9)
        if due and due > ref:
            return row("waiting", f"wartet auf {waiting_for(action)}", 8, due)
        if due and not historic:
            return row("due", "Wiedervorlage fällig", 2, due)
        return row("closed", "erledigt", 9)
    running = sorted(((parse_date(i["value"]), i) for i in items if urgent.customers(i) and urgent.dated(i) and not urgent.open_condition(i)
                      and ref <= parse_date(i["value"]) <= ref + timedelta(days=RUNNING_DAYS)), key=lambda row: row[0])
    if running:
        day, item = running[0]
        return row("frist", "dringend" if (day - ref).days <= URGENT_DAYS else "Frist läuft", 1, day)
    contact = None if as_of(files) or historic else next((i for i in items if i["kind"] == "contact"), None)  # a historic file has no first contact due
    if contact and parse_date(contact.get("value")):
        day = parse_date(contact["value"])
        return row("contact", "Erstkontakt überfällig" if day < ref else "vorbereitet", 1.5 if day < ref else 3, day)
    return row("prepared", "vorbereitet", 4, due)


def due(items, follow_up, files, historic=None, closed=False, today=None):
    """«Fällig» in the case list: the earliest of the open deadlines of the customer or of Protekta (statutory, set by a
    court, an authority or the other side, or held by the account), the follow-up and the first contact, with its word.
    None for a closed case."""
    if closed:
        return None
    ref = as_of(files) or (parse_date((historic or {}).get("newest")) if historic else None) or today or date.today()
    rows = []
    for i in items or ():
        if i["kind"] == "deadline" and (urgent.customers(i) or urgent.ours(i) or (i.get("account") and i.get("party") == "kunde")) \
                and urgent.dated(i) and not urgent.open_condition(i) and parse_date(i["value"]) >= ref:
            rows.append((i["value"], "Termin" if i.get("set_by_others") and not i.get("account") and i.get("what") else "Frist"))
    if follow_up and parse_date(follow_up):
        rows.append((parse_date(follow_up).isoformat(), "Wiedervorlage"))
    contact = None if as_of(files) or historic else next((i for i in items or () if i["kind"] == "contact"), None)
    if contact and parse_date(contact.get("value")):
        rows.append((parse_date(contact["value"]).isoformat(), "Erstkontakt"))
    if not rows:
        return None
    when, word = min(rows)
    return {"date": when, "word": word}
