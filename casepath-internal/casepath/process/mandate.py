"""The mandate package and the check of a mandated firm's cost claim.

At a mandate the insurer sends, on one day, a short mandate request to the law firm, the cost guarantee, the file by a
transfer link and an information to the customer; the firm receives the raw file and no summary. Here the prepared
action is that package: the request (form A10), the cost guarantee (A10_kostengutsprache: its scope chosen by the handler
from the backbone's options, out of court by default; an amount only if the handler enters one), a one-page case summary
for the firm (A10_zusammenfassung, built here) and the customer's information (A10_kunde, cover.json). Each is copied on
its own.

The summary is built from what CasePath has already established, no model call: parties with their roles, the request in
one sentence, the facts in time order, the legal key points that apply with their articles, what the file holds by kind
of document, what is still open, deadlines and set dates, and what the customer wants. Every line carries its source (a
page of the file, an article, or the handler's decision); a section the file is silent on says so; nothing is invented.

Before a firm's cost claim is paid, ``cost_check`` lists what the file shows about the guarantee: given on (date) with
its scope, an extension requested or granted, the firm's reports, the claim's amount and period, and whether the work
claimed lies within the scope, always as a question for the handler, never as a conclusion. Model-free.
"""
import functools
import re

from .clock import as_of, parse_date

MAX_LINES = 46  # one page in the insurer's plain letter style
NOT_IN_FILE = "nicht in der Akte"
SECTIONS = ("Parteien", "Anliegen", "Sachverhalt", "Rechtliche Kernpunkte", "In der Akte", "Noch offen", "Fristen und Termine",
            "Ziel der Kundschaft")
CAPS = {"Parteien": 5, "Sachverhalt": 10, "Rechtliche Kernpunkte": 4, "In der Akte": 8, "Noch offen": 6, "Fristen und Termine": 4,
        "Ziel der Kundschaft": 4}
PAGE = re.compile(r"\[page (\d+)\]")
COURT = re.compile(r"gericht|schlichtung|klage|prozess|verhandlung|instanz|rechtsöffnung", re.I)
EXTENSION = re.compile(r"[^.\n]*(?:Erweiterung der Kostengutsprache|Kostengutsprache\s+(?:\w+\s+){0,3}erweiter|erweiter\w*\s+(?:\w+\s+){0,3}Kostengutsprache)[^.\n]*", re.I)


@functools.lru_cache(maxsize=None)
def _guarantee_form():
    from .area import backbone
    return backbone()["forms"]["A10_kostengutsprache"]


def scope(facts):
    """(value, scope row) the cost guarantee covers: the handler's choice, else the backbone's default (out of court)."""
    form = _guarantee_form()
    value = (facts or {}).get(form["fact"])
    value = value if value in form["scopes"] else form["default"]
    return value, form["scopes"][value]


def amount_text(value):
    """The amount the handler entered, as the letter states it: digits with the Swiss thousands mark; None when none."""
    raw = str(value or "").strip()
    digits = re.sub(r"[^\d.,]", "", raw.replace("'", "").replace("’", ""))
    if not digits:
        return None
    whole, _, cents = digits.replace(",", ".").partition(".")
    grouped = re.sub(r"(?<=\d)(?=(\d{3})+$)", "'", whole)
    return f"{grouped}.{cents[:2].ljust(2, '0')}" if cents else f"{grouped}.–"


# Sources ---------------------------------------------------------------------------------------------------------------

def _names(files):
    return {f.get("id"): f.get("name") or f.get("id") for f in files or ()}


def source(evidence, files):
    """«S. 3» (one file) or «Akte.pdf S. 3»; None without a page or file."""
    if not evidence:
        return None
    e = evidence[0]
    names = _names(files)
    many = len(names) > 1
    name = names.get(e.get("file"))
    if e.get("page"):
        return f"{name} S. {e['page']}" if many and name else f"S. {e['page']}"
    return name


def _pages(f):
    text = str((f.get("extraction") or {}).get("text") or f.get("text") or "")
    parts = PAGE.split(text)
    if len(parts) == 1:
        return [(None, text)] if text else []
    return [(int(parts[i]), parts[i + 1]) for i in range(1, len(parts) - 1, 2)]


def locate(needle, files):
    """Where a short text (a name) first stands in the files' text: [{file, page, quote}] or []."""
    needle = str(needle or "").strip()
    if len(needle) < 3:
        return []
    for f in files or ():
        for page, text in _pages(f):
            at = text.find(needle)
            if at >= 0:
                line = text[text.rfind("\n", 0, at) + 1: (text.find("\n", at) if text.find("\n", at) >= 0 else len(text))].strip()
                return [{"file": f.get("id"), "page": page, "quote": line[:160]}]
    return []


def _segments(files):
    return [(f, s) for f in files or () for s in ((f.get("extraction") or {}).get("segments") or [])]


def _seg_source(f, s, files):
    first, last = s.get("first_page"), s.get("last_page")
    pages = f"S. {first}" if first and (not last or last == first) else f"S. {first}–{last}" if first else None
    return (f"{f.get('name')} {pages}" if len(files or ()) > 1 and pages else pages or f.get("name"))


def _short(text, n=150):
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[: n - 2].rstrip() + " …"


# The summary for the firm ----------------------------------------------------------------------------------------------

def summary(items, files, today=None):
    """[(section, [{text, source}])] in the order a firm reads a case; a section the file is silent on holds one line
    marked as such (source None, ``gap`` True). Each other line names its source."""
    label = lambda i: (i.get("label") or {}).get("de") or ""
    by = lambda kind: [i for i in items if i["kind"] == kind]
    facts = {i["key"]: i for i in by("fact")}
    out = {s: [] for s in SECTIONS}

    for p in by("party"):
        if p.get("value"):
            ev = p.get("evidence") or locate(p["value"], files)
            out["Parteien"].append({"text": f"{label(p) or 'Partei'}: {p['value']}", "source": source(ev, files)})
    other = (facts.get("gegenpartei") or {})
    if other.get("value") and not any(other["value"] in l["text"] for l in out["Parteien"]):
        out["Parteien"].append({"text": f"Gegenpartei: {other['value']}", "source": source(other.get("evidence") or locate(other["value"], files), files)})

    request = next((i.get("value") for i in by("summary") if i.get("value")), None)
    if request:
        claim = next(((f, s) for f, s in _segments(files) if "meldung" in str(s.get("kind") or "").lower()), None)
        ev = locate(request[:40], files)
        src = source(ev, files) or (f"Schadenmeldung, {_seg_source(*claim, files)}" if claim else
                                    (files[0].get("name") if len(files or ()) == 1 else None))  # a single file: the claim itself
        first = re.split(r"(?<=[^\d\s.])\.\s+(?=[A-ZÄÖÜ])", request.strip())[0].rstrip(".")  # one sentence; «20. Oktober» is no end
        out["Anliegen"].append({"text": _short(first + ".", 220), "source": src})

    timeline = []
    for t in by("timeline"):
        text = str(t.get("value") or "").strip()
        m = re.match(r"(\d{4}-\d{2}-\d{2})\s+(.*)", text)
        day = parse_date(m.group(1)) if m else None
        timeline.append((day.isoformat() if day else "9999", f"{day.strftime('%d.%m.%Y')} {m.group(2)}" if day else text, t.get("evidence") or []))
    for _, text, ev in sorted(timeline, key=lambda r: r[0]):
        out["Sachverhalt"].append({"text": _short(text), "source": source(ev, files)})

    for p in by("key_point"):
        if p.get("value") == "applies":
            src = source(p.get("evidence"), files)
            out["Rechtliche Kernpunkte"].append({"text": label(p), "source": "; ".join(x for x in (p.get("legal_basis"), src) if x)})

    kinds = {}
    for f, s in _segments(files):
        kind = str(s.get("kind") or "").strip() or "Dokument"
        kinds.setdefault(kind, []).append(_seg_source(f, s, files))
    for kind, where in kinds.items():
        out["In der Akte"].append({"text": f"{kind}" + (f" ({len(where)})" if len(where) > 1 else ""), "source": ", ".join(w for w in where if w)})
    if not kinds:
        for d in by("document"):
            if d.get("status") == "present":
                out["In der Akte"].append({"text": label(d), "source": source(d.get("evidence"), files)})

    for d in by("document"):
        if d.get("status") != "present" and (d.get("ask") == "now" or d.get("required") == "yes") and not d.get("part_of"):
            out["Noch offen"].append({"text": f"Fehlt: {label(d)}", "source": "Prüfung der Akte"})
    for p in by("key_point"):
        if p.get("value") == "open":
            out["Noch offen"].append({"text": f"Zu klären: {label(p)}", "source": p.get("legal_basis")})

    for d in by("deadline"):
        day = parse_date(d.get("value"))
        what = d.get("what") or label(d)
        when = day.strftime("%d.%m.%Y") if day else "Datum prüfen"
        if d.get("set_by_others"):
            out["Fristen und Termine"].append({"text": f"{when}: {what}" + (f" ({d['by']})" if d.get("by") else ""),
                                               "source": source(d.get("evidence"), files) or d.get("source")})
        elif d.get("origin") == "law":
            trigger = facts.get(str(d.get("trigger") or "")) or {}
            out["Fristen und Termine"].append({"text": f"{'ab' if d.get('direction') == 'ab' else 'bis'} {when}: {what}",
                                               "source": d.get("legal_basis") + (f"; Auslöser {source(trigger.get('evidence'), files)}" if source(trigger.get("evidence"), files) else "")})

    goal = facts.get("ziel") or {}
    if goal.get("value"):
        out["Ziel der Kundschaft"].append({"text": _short(goal["value"]), "source": source(goal.get("evidence"), files)})
    for key, f in facts.items():
        m = re.match(r"Will die Kundschaft (.+?)\??$", label(f))
        if key.startswith("will_") and f.get("value") is True and m:
            out["Ziel der Kundschaft"].append({"text": m.group(1)[:1].upper() + m.group(1)[1:], "source": source(f.get("evidence"), files) or "Angabe der Kundschaft"})
    for q in by("customer_question"):
        out["Ziel der Kundschaft"].append({"text": f"Frage: «{_short(q.get('value'), 120)}»", "source": source(q.get("evidence"), files)})

    rows = []
    for section in SECTIONS:
        lines = [l for l in out[section] if l["text"].strip()]
        cap = CAPS.get(section, 3)
        if len(lines) > cap:
            lines = lines[:cap - 1] + [{"text": f"… {len(lines) - cap + 1} weitere in der Akte", "source": "Akte", "more": True}]
        rows.append((section, lines or [{"text": f"{NOT_IN_FILE} festgestellt", "source": None, "gap": True}]))
    return rows


def render_summary(rows, reference=None, today=None):
    """The summary as one page of text: each line with its source in brackets, «Fundstelle nicht ermittelt» where a line
    has none (a statement whose page was not found), «nicht in der Akte» where a section is empty."""
    head = ["Zusammenfassung für die Kanzlei" + (f" · Unsere Referenz {reference}" if reference else ""),
            f"Stand {today.strftime('%d.%m.%Y')} · aus der Akte erstellt; jede Angabe mit ihrer Fundstelle" if today else
            "Aus der Akte erstellt; jede Angabe mit ihrer Fundstelle"]
    lines = list(head)
    for section, rows_ in rows:
        lines += ["", section]
        for r in rows_:
            if r.get("gap"):
                lines.append(f"– {r['text']}")
            else:
                lines.append(f"– {r['text']} ({r['source'] or 'Fundstelle nicht ermittelt'})")
    return "\n".join(lines[: MAX_LINES + 2])


# The letters' placeholders ---------------------------------------------------------------------------------------------

def _customer(items):
    from .letters import customer
    return customer([i for i in items if i["kind"] == "party"])


FIRM_OR_INSURER = re.compile(r"kanzlei|anwalt|anwält|advokatur|rechtsanw|protekta|rechtsschutz|versicherer|versicherung", re.I)


def role_word(party):
    """A party's role as a letter names it, without the file's markers: «Mieterin (VN)» → «Mieterin»."""
    label = (party.get("label") or {}).get("de") if isinstance(party.get("label"), dict) else party.get("label")
    return re.sub(r"\s*\((?:VN|GP|versicherte Person)\)\s*", " ", str(label or "")).strip(" ,") or None


def other_side(items, who):
    """The other side by its role, as the file names it: the reader's fact first, else a party that is neither the
    customer nor a firm or an insurer (the mandated firm is never the other side); None when the file names none."""
    facts = {i["key"]: i.get("value") for i in items if i["kind"] == "fact"}
    named = facts.get("gegenpartei")
    if named and not FIRM_OR_INSURER.search(str(named)):
        party = next((p for p in items if p["kind"] == "party" and p.get("value") and str(p["value"]) in str(named)), None)
        return named, role_word(party) if party else None
    for p in items:
        if p["kind"] == "party" and p is not who and p.get("value") and not FIRM_OR_INSURER.search(f"{role_word(p) or ''} {p['value']}"):
            return p["value"], role_word(p)
    return None, None


def letter_context(case, items, files, today=None):
    from .letters import gap
    facts = {i["key"]: i.get("value") for i in items if i["kind"] == "fact"}
    who = _customer(items) or {}
    other, other_role = other_side(items, who)
    value, row = scope(facts)
    amount = amount_text(facts.get("kostengutsprache_betrag"))
    ref = re.search(r"\d{4}\.\d{4}\.\d{4}", f"{case.get('title', '')} {case.get('intake', '')}")
    day = today or as_of(files)
    lines = {i["key"]: i for i in items if i["kind"] == "stage_line"}
    claim, given = lines.get("kg-forderung") or {}, lines.get("kg-gutsprache") or {}
    return {
        "mandat_kunde": (f"{who.get('value')}" + (f" ({role_word(who)})" if role_word(who) and role_word(who).lower() not in {"kundschaft", "kunde", "kundin"} else ""))
                        if who.get("value") else gap("Name der Kundschaft"),
        "mandat_gegenpartei": (f"{other}" + (f" ({other_role})" if other_role else "")) if other else gap("Gegenpartei"),
        "mandat_auftrag": row["auftrag"],
        "mandat_kurz": (f"{who.get('value')} gegen {other}" if who.get("value") and other else
                        f"unserer Versicherten {who.get('value')}" if who.get("value") else "unserer Versicherten"),
        "kg_umfang": row["text"],
        "kg_betrag": amount or "",
        "zusammenfassung": render_summary(summary(items, files, day), ref.group(0) if ref else None, day) if items else "",
        # the fee note: what the file shows, gaps where it is silent (the handler fills them, nothing is invented)
        "forderung_bezug": " ".join(x for x in ((f"vom {claim['date_text']}" if claim.get("date_text") else ""),
                                                (f"über {claim['amount']}" if claim.get("amount") else "")) if x) or gap("Datum und Betrag der Forderung"),
        "kg_bezug": f"vom {given['date_text']}" if given.get("date_text") else gap("Datum der Kostengutsprache"),
        "kg_umfang_text": given.get("scope_text") or gap("Umfang der Kostengutsprache"),
        "teil_betrag": gap("übernommener Betrag und welche Positionen"),
        "teil_grund": gap("welche Positionen nicht und weshalb (Umfang der Kostengutsprache)"),
    }


# The check of a firm's cost claim ---------------------------------------------------------------------------------------

def is_firm_claim(open_item):
    """A cost claim of the mandated firm (not of a court) is the open item."""
    if not open_item or open_item["kind"]["id"] != "kostenforderung":
        return False
    head = str(open_item.get("value") or "").split(":", 1)[0]
    return not re.search(r"gericht|schlichtungsbeh|betreibungsamt", head, re.I)


def _search(files, pattern, skip=None):
    for f in files or ():
        for page, text in _pages(f):
            for m in pattern.finditer(text):
                sentence = " ".join(m.group(0).split())
                if skip and skip.search(sentence):
                    continue
                return {"file": f.get("id"), "page": page, "quote": sentence[:160]}, sentence
    return None, None


def cost_check(facts, rows, files, open_item, dated=None, graph=None):
    """The compact check before a firm's cost claim is paid: [{id, text, citations, …}], each line from the file with
    its source or marked «nicht in der Akte»; the last line is a question for the handler, never a conclusion."""
    from . import incoming
    from .workflows import done_actions
    cites = lambda fact: ((rows or {}).get(fact) or {}).get("citations") or []
    out = []
    days = sorted(d for x in done_actions(facts or {}).get("10", []) if (d := parse_date(x)))
    chosen = (facts or {}).get(_guarantee_form()["fact"])
    value, row = scope(facts)
    history = cites("bisherige_handlungen")
    if days:
        found, _ = (None, None) if chosen else _search(files, re.compile(r"[^.\n]*Kostengutsprache[^.\n]*(?:aussergerichtlich|Schlichtung|erster Instanz)[^.\n]*", re.I))
        scope_text = row["text"] if chosen or found else None
        if found:  # the scope as the guarantee in the file states it
            value = next((k for k, r in _guarantee_form()["scopes"].items() if r.get("court") and str(r["court"]).lower() in found["quote"].lower()), "aussergerichtlich")
            scope_text = _guarantee_form()["scopes"][value]["text"]
        out.append({"id": "kg-gutsprache", "text": f"Kostengutsprache erteilt am {days[-1].strftime('%d.%m.%Y')} · Umfang: "
                    + (scope_text or NOT_IN_FILE) + (" (Entscheid der Fallbearbeitung)" if chosen else ""),
                    "citations": [found] if found else history[:1], "date_text": days[-1].strftime("%d.%m.%Y"), "scope_text": scope_text,
                    "scope": value if scope_text else None})
    else:
        out.append({"id": "kg-gutsprache", "text": f"Kostengutsprache: {NOT_IN_FILE}", "citations": [], "scope": None})
    ext, sentence = _search(files, EXTENSION, skip=re.compile(r"vorgängige Kontaktaufnahme", re.I))
    if ext:
        granted = re.search(r"erweitern wir|wird erweitert|wurde erweitert|erteilen wir", sentence, re.I)
        out.append({"id": "kg-erweiterung", "text": f"Erweiterung der Kostengutsprache: {'erteilt' if granted else 'beantragt'}", "citations": [ext]})
    else:
        out.append({"id": "kg-erweiterung", "text": f"Erweiterung der Kostengutsprache: {NOT_IN_FILE}", "citations": []})
    reports = sorted(((parse_date(s.get("date")), f, s) for f, s in _segments(files)
                      if re.search(r"bericht", str(s.get("kind") or ""), re.I) and not re.search(r"protekta", str(s.get("sender") or ""), re.I)),
                     key=lambda r: (r[0] is None, r[0]))
    reports = [r for r in reports if r[0]]
    if reports:
        day, f, s = reports[-1]
        out.append({"id": "kg-berichte", "text": f"Berichte der Kanzlei: {len(reports)}, zuletzt vom {day.strftime('%d.%m.%Y')}",
                    "citations": [{"file": f.get("id"), "page": s.get("first_page"), "quote": s.get("title") or s.get("kind")}]})
    else:
        rows_ = [r for r in incoming.items(graph or {"incoming": []}, facts or {}, dated) if r["kind"]["id"] == "bericht" and r.get("date")] if graph else []
        if rows_:
            last = rows_[-1]
            out.append({"id": "kg-berichte", "text": f"Berichte der Kanzlei: {len(rows_)}, zuletzt vom {parse_date(last['date']).strftime('%d.%m.%Y')}",
                        "citations": cites(last["fact"])[:1]})
        else:
            out.append({"id": "kg-berichte", "text": f"Berichte der Kanzlei: {NOT_IN_FILE}", "citations": []})
    text = str(open_item.get("value") or "")
    from .settlement import AMOUNT
    amount = AMOUNT.search(text)
    period = re.search(r"(?:Zeitraum|Periode|für die Zeit|Leistungen)\s+(?:vom\s+)?(\d{1,2}\.\d{1,2}\.(?:\d{4})?\s*(?:bis|–|-)\s*\d{1,2}\.\d{1,2}\.\d{4}"
                       r"|\d{4}-\d{2}-\d{2}\s*(?:bis|–|-)\s*\d{4}-\d{2}-\d{2})", text)
    day = parse_date(open_item.get("date"))
    day_text = day.strftime("%d.%m.%Y") if day else None
    out.append({"id": "kg-forderung", "text": (f"Forderung vom {day_text}: " if day_text else "Forderung: ")
                + (f"CHF {amount.group(1).strip()}" if amount else f"Betrag {NOT_IN_FILE}") + " · "
                + (f"Zeitraum {period.group(1)}" if period else f"Zeitraum {NOT_IN_FILE}"),
                "citations": cites(open_item["fact"])[:1], "amount": f"CHF {amount.group(1).strip()}" if amount else None,
                "date_text": day_text})
    court_word = COURT.search(text)
    scope_row = next((r for r in out if r["id"] == "kg-gutsprache"), {})
    if scope_row.get("scope") == "aussergerichtlich":
        question = "Gerichtliche Schritte abgerechnet? Kostengutsprache umfasst nur aussergerichtliche Bemühungen"
    elif scope_row.get("scope"):
        question = f"Abgerechnete Schritte im Rahmen der Kostengutsprache ({scope_row['scope_text']})?"
    else:
        question = "Abgerechnete Leistungen im Rahmen einer Kostengutsprache? Deren Umfang ist nicht in der Akte"
    out.append({"id": "kg-frage", "text": "? " + question + (f" (die Forderung nennt «{court_word.group(0)}»)" if court_word else ""), "citations": []})
    return out
