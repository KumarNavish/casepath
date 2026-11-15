"""The running account of a case: one short entry per document of the file, and what follows from the entries by code.

The reader returns, for each document of the file (phone notes included), one entry: its date, from and to, the kind
of step (the backbone's closed list ``record.kinds``), whether it is a phone note, one line on what it is, and the
elements the document states: what it asks (what, of whom, by when, and the earlier entry it repeats), what it
delivers or answers (and the earlier entry it answers), the terms offered or agreed (what, amount, who pays, by when),
what was paid, and the next step it states with its date. Every element carries a quote located in that document
(``check``): an element whose quote is not found there is dropped and counted, an entry whose own quote is not found
is dropped whole.

From the entries, by code (``build``):
- the requests ledger: each thing asked, by whom, of whom, first and last asked, by when, how often, whether
  answered, by which entry, and whether the answer matches what was asked (``confirmed``);
- the agreement as it stands: the latest agreed terms, earlier terms and offers kept as history, and whether paid;
- who owes what now: open requests by the party asked, and an agreed payment not made;
- the insurer's actions taken (A1 … A12 with their dates), which replace the action facts read one by one (``facts``);
- silence and lack of cooperation, read from the ledger rather than from counters (``silence``, ``derived``).

A run stored before the account has no entries: nothing here applies, nothing is invented. Model-free.
"""
import re
from datetime import date, timedelta

from .clock import parse_date
from .workflows import CatalogueError

PARTIES = ("kunde", "versicherer", "kanzlei", "gegenpartei", "behoerde", "andere")
INSURER = "versicherer"
PARTY_TITLES = {"kunde": "Kundschaft", "versicherer": "Protekta", "kanzlei": "Kanzlei", "gegenpartei": "Gegenpartei",
                "behoerde": "Gericht/Behörde", "andere": "Andere"}
# who owes, as the «Stand» names them
AT = {"kunde": "bei der Kundschaft", "versicherer": "bei uns", "kanzlei": "bei der Kanzlei", "gegenpartei": "bei der Gegenpartei",
      "behoerde": "bei Gericht/Behörde", "andere": "bei Dritten"}
WITH = {"kunde": "der Kundschaft", "versicherer": "Protekta", "kanzlei": "der Kanzlei", "gegenpartei": "der Gegenpartei",
        "behoerde": "Gericht/Behörde", "andere": "Dritten"}
ELEMENTS = ("asks", "answers", "terms", "paid", "next")
SHOWN_PER_PARTY = 3  # open items per party in «Stand»; the rest behind «… n weitere», which opens the Verlauf on them
MAX_ENTRIES_PER_CALL = 10
REQUEST_DAYS = 21  # a request without its own date expects an answer within three weeks (the backbone's cooperation rule)


def validate(backbone):
    """Fail closed on a record the account cannot read: the six parties, kinds with a title, codes of action kinds."""
    record = backbone.get("record")
    if record is None:
        return
    if set(record.get("parties") or ()) != set(PARTIES):
        raise CatalogueError(f"backbone: record.parties must be exactly {list(PARTIES)}")
    actions = {k[1:] for k in backbone.get("action_kinds") or ()}
    kinds = record.get("kinds") or {}
    if "andere" not in kinds or "telefon" not in kinds:
        raise CatalogueError("backbone: record.kinds needs «telefon» and «andere»")
    for kind, row in kinds.items():
        codes = [row.get("code"), row.get("again"), *(row.get("code_to") or {}).values()]
        if not re.fullmatch(r"[a-z_]{3,30}", kind) or not row.get("title") or any(c is not None and c not in actions for c in codes):
            raise CatalogueError(f"backbone: record kind {kind!r} needs a title and codes of the backbone's action kinds")
        if set(row.get("code_to") or {}) - set(PARTIES):
            raise CatalogueError(f"backbone: record kind {kind!r}: code_to names parties of the record")
    if record.get("phone_code") not in actions:
        raise CatalogueError("backbone: record.phone_code must be an action kind")


def kinds_of(graph):
    return ((graph or {}).get("record") or {}).get("kinds") or {}


def entries_of(result):
    """The located entries of a stored result; [] for a run made before the account."""
    return [e for e in ((result or {}).get("record") or {}).get("entries") or () if isinstance(e, dict) and e.get("n") is not None]


# -- checking the reader's entries --------------------------------------------------------------------------------

DATE_ONLY = re.compile(r"(?:(?:bis|am|per|spätestens|spaetestens|by|on)\s+)?(\d{4}-\d{2}-\d{2}(?:[T ][\d:.]+Z?)?|\d{1,2}\.\s?\d{1,2}\.\s?\d{4}"
                       r"|\d{1,2}\.?\s+[A-Za-zäÄ]+\s+\d{4})\.?", re.I)


def _iso(value):
    """A date as YYYY-MM-DD from a value that is only a date (2025-03-12, 12.03.2025, 12. März 2025, «bis 12.03.2025»);
    None for anything else, also for a period with a start date in it («innert 14 Tagen ab 3. März 2025»)."""
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    m = DATE_ONLY.fullmatch(value)
    if not m:
        return None
    try:
        d = parse_date(re.sub(r"\.\s(?=\d)", ".", m.group(1)))
    except ValueError:
        return None
    return d.isoformat() if d else None


# who a party is, as a reader may also write it (a near word, an abbreviation, a role); first match wins
PARTY_WORDS = (("gegenpartei", ("gegen", "vermiet", "arbeitgeber", "verwaltung", "opposing", "other side", "schuldner", "gläubiger")),
               ("behoerde", ("gericht", "behörde", "behoerde", "amt", "court", "authority", "schlichtung", "staatsanwalt")),
               ("kanzlei", ("kanzlei", "anwalt", "anwält", "rechtsanw", "law firm", "lawyer", "advokatur")),
               ("versicherer", ("versicherer", "protekta", "rechtsschutz", "insurer", "versicherung")),
               ("kunde", ("kund", "versichert", "insured", "customer", "klient", "mandant", "mieter", "arbeitnehmer")))
PARTY_SHORT = {"vn": "kunde", "gp": "gegenpartei", "ra": "kanzlei", "ak": "kanzlei", "wir": "versicherer", "uns": "versicherer"}


def party_of(value, default="andere"):
    """One of PARTIES for what a reader wrote: the party itself, a near word («Vermieterin», «RA», «VN»), else «andere»;
    ``default`` for nothing at all."""
    v = str(value or "").strip().lower()
    if not v:
        return default
    if v in PARTIES:
        return v
    short = next((PARTY_SHORT[w] for w in re.findall(r"\w+", v) if w in PARTY_SHORT), None)
    if short:
        return short
    return next((party for party, words in PARTY_WORDS if any(w in v for w in words)), "andere")


def _party(value):
    return party_of(value)


# the kind of step, as a reader may also write it: a near word maps to the record's kind; unknown is «andere»
KIND_WORDS = (("telefon", ("telefon", "anruf", "phone", "call")), ("mahnung", ("mahnung", "erinnerung", "reminder")),
              ("kostenforderung", ("rechnung", "honorar", "kostennote", "invoice", "kostenforderung", "vorschuss")),
              ("zahlungsbestaetigung", ("zahlungsbest", "quittung", "receipt")), ("zahlung", ("zahlung", "überweis", "ueberweis", "payment")),
              ("gegenangebot", ("gegenangebot", "gegenvorschlag", "counter")), ("annahme", ("annahme", "akzept", "accept", "einverst")),
              ("angebot", ("angebot", "vergleichsvorschlag", "offerte", "offer", "vergleich")),
              ("entscheid", ("entscheid", "urteil", "verfügung", "verfuegung", "beschluss", "decision", "judgment")),
              ("termin", ("termin", "vorladung", "verhandlung", "hearing")), ("abschlussankuendigung", ("abschlussank", "statusanfrage")),
              ("kostengutsprache", ("gutsprache",)), ("mandat", ("mandat",)), ("abschluss", ("abschluss", "schliess", "closing")),
              ("bericht", ("bericht", "report")), ("einschaetzung", ("einschätzung", "einschaetzung", "beurteilung", "assessment")),
              ("anforderung", ("anforderung", "aufforderung", "request", "nachforderung")),
              ("unterlagen", ("unterlagen", "belege", "dokumente", "documents")), ("antwort", ("antwort", "stellungnahme", "reply", "answer")),
              ("meldung", ("meldung", "schadenmeldung", "claim")), ("schreiben_gegenpartei", ("schreiben an die gegenpartei",)))


def kind_of(value, kinds):
    """The record kind for what a reader wrote: the kind itself, its title, a near word, else «andere»."""
    v = str(value or "").strip().lower()
    if v in kinds:
        return v
    by_title = next((k for k, row in kinds.items() if str(row.get("title") or "").lower() == v), None)
    if by_title:
        return by_title
    return next((k for k, words in KIND_WORDS if k in kinds and any(w in v for w in words)), "andere")


PERIOD_WORDS = re.compile(r"(\d{1,3})\s*(tag|tage|tagen|days?|woche|wochen|weeks?|monat|monate|monaten|months?)\b", re.I)


def _plus(start, n, unit):
    unit = unit.lower()
    if unit.startswith(("monat", "month")):
        month = start.month - 1 + n
        year, month = start.year + month // 12, month % 12 + 1
        last = (date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)).day
        return date(year, month, min(start.day, last))
    return start + timedelta(days=n * (7 if unit.startswith(("woche", "week")) else 1))


def due_of(element, entry_date=None):
    """(date or None, text or None, computed): by when, as the reader gave it. A date field (``by_date``) or a «by» that is
    only a date gives the date; a period («innert 14 Tagen ab Erhalt») gives the date counted from the document's own
    date, marked computed; any other text is kept as text."""
    own = _iso(element.get("by_date")) or _iso(element.get("by"))
    text = _clip(element.get("by"), 120) or None
    if own:
        return own, (text if text and not _iso(text) else None), False
    m = PERIOD_WORDS.search(text or "")
    try:
        start = parse_date(entry_date) if entry_date else None
    except ValueError:
        start = None
    if m and start and not re.search(r"\d{1,2}\.\d{1,2}\.\d{4}|\d{4}-\d{2}-\d{2}", text):
        return _plus(start, int(m.group(1)), m.group(2)).isoformat(), text, True
    return None, text, False


def _clip(text, n):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text if len(text) <= n else text[:n - 1].rstrip() + "…"


def check(raw, locate, kinds, elsewhere=None, issues=None):
    """One entry of the reader, as the account keeps it: (entry or None, elements dropped).

    ``locate(quote)`` returns the located citation within this entry's own document (its page range as code knows it),
    or None. The entry's own quote must be found there, or the entry is dropped (it counts as one). An element whose
    quote is not found there but ``elsewhere(quote)`` finds it in the same file is kept, marked with the page where it
    was found («andere Stelle»); one found nowhere is dropped and counted. ``issues`` collects, per element not found in
    its document, its kind and the reason: «elsewhere» (kept) or «not_found» (dropped)."""
    issues = [] if issues is None else issues
    n = raw.get("n")
    own = locate(raw.get("quote"))
    if not own:
        far = elsewhere(raw.get("quote")) if elsewhere else None
        issues.append({"n": n, "kind": "entry", "reason": "elsewhere" if far else "not_found", "kept": False,
                       **({"page": far.get("page")} if far else {})})
        return None, 1 + sum(len(raw.get(k) or ()) for k in ELEMENTS)
    dropped = 0
    day = _iso(raw.get("date"))
    sender = party_of(raw.get("from"))
    entry = {"n": int(n), "file": raw.get("file"), "page": own.get("page") if raw.get("page") is None else raw.get("page"),
             "date": day, "from": sender, "to": party_of(raw.get("to"), default=sender),  # a file note is to no one: to itself
             "kind": kind_of(raw.get("kind"), kinds), "phone": bool(raw.get("phone")),
             "what": _clip(raw.get("what"), 160), "citations": [own]}
    for key in ELEMENTS:
        kept = []
        for element in raw.get(key) or ():
            hit, far = locate(element.get("quote")), None
            if not hit and elsewhere:
                far = elsewhere(element.get("quote"))
            if not hit and not far:
                dropped += 1
                issues.append({"n": n, "kind": key, "reason": "not_found", "kept": False})
                continue
            row = {"citations": [hit or far]}
            if far:
                row["elsewhere"] = {"page": far.get("page")}
                issues.append({"n": n, "kind": key, "reason": "elsewhere", "kept": True, "page": far.get("page")})
            due, due_text, computed = due_of(element, day) if key in ("asks", "terms", "next") else (None, None, False)
            dated = {"by": due, **({"by_text": due_text} if due_text else {}), **({"by_computed": True} if computed else {})}
            if key == "asks":
                row.update(what=_clip(element.get("what"), 120), of=_party(element.get("of")), **dated,
                           repeats=element.get("repeats") if isinstance(element.get("repeats"), int) else None, warns=bool(element.get("warns")))
            elif key == "answers":
                row.update(what=_clip(element.get("what"), 120), answers=element.get("answers") if isinstance(element.get("answers"), int) else None)
            elif key == "terms":
                row.update(what=_clip(element.get("what"), 120), amount=_clip(element.get("amount"), 40) or None,
                           payer=_party(element.get("payer")), **dated, agreed=bool(element.get("agreed")))
            elif key == "paid":
                row.update(amount=_clip(element.get("amount"), 40) or None, payer=_party(element.get("payer")), date=_iso(element.get("date")))
            else:
                row.update(what=_clip(element.get("what"), 120), who=_party(element.get("who")), **dated)
            kept.append(row)
        entry[key] = kept
    return entry, dropped


# -- coverage: pages of the file with no entry ------------------------------------------------------------------------

GAP_PAGES = 3  # a run of more pages than this between two entries' first pages, or before the first or after the last, is a gap
DATED = re.compile(r"\b\d{1,2}\.\s?\d{1,2}\.\s?(?:\d{4}|\d{2})\b|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}\.\s+(?:Januar|Februar|März|Maerz|"
                   r"April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+\d{4}", re.I)


def gaps(entries, pages):
    """The page ranges with no entry: [{file, from, to, pages}]. ``pages``: {file: [(page, text)]}. A range is a run of more
    than GAP_PAGES pages with text that lies before the first entry's first page, between two entries' first pages or
    after the last, and has a date on one of its pages (a dated letter, e-mail, note or invoice may stand there). A file
    whose entries name no page is one document; a file without pages is not counted."""
    out = []
    for fid, rows in pages.items():
        text = {p: t for p, t in rows if p is not None and str(t or "").strip()}
        if not text:
            continue
        mine = [e for e in entries or () if e.get("file") == fid]
        firsts = sorted({e["page"] for e in mine if isinstance(e.get("page"), int)})
        if mine and not firsts:
            continue
        numbers = sorted(text)
        bounds = [numbers[0] - 1] + firsts + [numbers[-1] + 1]
        for a, b in zip(bounds, bounds[1:]):
            run = [p for p in numbers if a < p < b]
            if len(run) > GAP_PAGES and any(DATED.search(text[p]) for p in run):
                out.append({"file": fid, "from": run[0], "to": run[-1], "pages": len(run)})
    return out


def coverage(entries, pages):
    """Pages covered against pages of the file: {pages, covered, gaps}."""
    total = sum(1 for rows in pages.values() for p, t in rows if p is not None and str(t or "").strip())
    found = gaps(entries, pages)
    return {"pages": total, "covered": total - sum(g["pages"] for g in found), "gaps": found}


def gap_text(gap):
    return f"S. {gap['from']}–{gap['to']} ohne Eintrag" if gap["to"] > gap["from"] else f"S. {gap['from']} ohne Eintrag"


def pages_of(files):
    """{file id: [(page, text)]} from stored files (``extraction.text`` with its [page n] marks)."""
    out = {}
    for f in files or ():
        raw = str((f.get("extraction") or {}).get("text") or "")
        out[f.get("id")] = [(int(m.group(1)), m.group(2)) for m in re.finditer(r"\[page (\d+)\]\n(.*?)(?=\n\n\[page \d+\]\n|\Z)", raw, re.S)]
    return out


# -- the account ----------------------------------------------------------------------------------------------------

WORD = re.compile(r"[A-Za-zÄÖÜäöüß]{3,}")
STOP = {"und", "oder", "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "von", "vom", "mit", "für", "bis", "zur",
        "zum", "ihre", "ihren", "ihr", "sämtliche", "alle", "kopie", "kopien", "weitere", "allfällige", "noch", "bitte", "uns", "wir",
        "betreffend", "über", "sowie", "inkl", "the", "and"}


def words(text):
    return {w.lower()[:6] for w in WORD.findall(str(text or "")) if w.lower() not in STOP}


def overlap(a, b):
    wa, wb = words(a), words(b)
    return len(wa & wb) / min(len(wa), len(wb)) if wa and wb else 0.0


def amount(text):
    """The number in an amount as written («CHF 3'000.–», «3 000», «Fr. 2'500.50»); None without one."""
    m = re.search(r"\d{1,3}(?:[’' ]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?", str(text or ""))
    if not m:
        return None
    digits = re.sub(r"[’' ]", "", m.group(0)).replace(",", ".")
    try:
        return float(digits)
    except ValueError:
        return None


def _key(e):
    return (e.get("date") or "9999-12-31", e["n"])


def _best(candidates, what):
    scored = sorted(((overlap(what, r["what"]), i, r) for i, r in enumerate(candidates)), key=lambda x: (-x[0], x[1]))
    return scored[0] if scored else (0.0, 0, None)


def code_of(entry, kinds, earlier_announced=False, phone_code="2"):
    """The insurer's action kinds an entry of the insurer is: its kind's code (to this party), a phone note's code."""
    if entry.get("from") != INSURER:
        return []
    row = kinds.get(entry.get("kind")) or {}
    code = (row.get("code_to") or {}).get(entry.get("to")) or row.get("code")
    if code and earlier_announced and row.get("again"):
        code = row["again"]
    codes = [c for c in [code] if c]
    if entry.get("phone") and phone_code not in codes:
        codes.append(phone_code)
    return codes


def build(entries, graph=None):
    """The account from the located entries: {entries, requests, terms, agreement, paid, owes, actions, last_contact}.
    None without entries."""
    entries = sorted([e for e in entries or () if e.get("n") is not None], key=_key)
    if not entries:
        return None
    record = (graph or {}).get("record") or {}
    kinds, phone_code = record.get("kinds") or {}, record.get("phone_code") or "2"
    by_n = {e["n"]: e for e in entries}
    requests = []
    for e in entries:
        for a in e.get("asks") or ():
            prior = None
            if a.get("repeats") in by_n:  # the reader names the entry it repeats
                same = [r for r in requests if a["repeats"] in r["entries"] and r["of"] == a["of"]]
                prior = _best(same, a["what"])[2]
            if prior is None:  # by code: the same asker, the same party asked, the same thing (or the one open thing, in a reminder)
                same = [r for r in requests if r["by"] == e["from"] and r["of"] == a["of"] and r["answered"] is None]
                score, _, row = _best(same, a["what"])
                if score >= 0.5 or (e.get("kind") == "mahnung" and len(same) == 1):
                    prior = row
            if prior is not None:
                if a.get("by"):
                    prior.update(due_n=e["n"], due_computed=bool(a.get("by_computed")))
                prior.update(times=prior["times"] + 1, last=e.get("date") or prior["last"], due=a.get("by") or prior["due"],
                             due_text=a.get("by_text") or prior.get("due_text"))
                prior["entries"].append(e["n"])
                prior["citations"] = prior["citations"] + a["citations"]
                prior["warned"] += int(bool(a.get("warns")))
                if prior["answered"] is not None and a.get("repeats") is not None:
                    prior["answered"] = None  # asked again after an answer: the answer did not settle it
                continue
            requests.append({"id": f"r{len(requests) + 1}", "by": e["from"], "of": a["of"], "what": a["what"], "first": e.get("date"),
                             "last": e.get("date"), "due": a.get("by"), "times": 1, "warned": int(bool(a.get("warns"))),
                             "entries": [e["n"]], "citations": list(a["citations"]), "answered": None, "phone": bool(e.get("phone")),
                             "due_n": e["n"] if a.get("by") else None, "due_text": a.get("by_text"), "due_computed": bool(a.get("by_computed"))})
        for x in e.get("answers") or ():
            open_ = [r for r in requests if r["of"] == e["from"] and r["answered"] is None and r["entries"][0] != e["n"]]
            matched, how = [], "entry"
            if x.get("answers") in by_n:  # the entry says which earlier entry it answers
                named = [r for r in open_ if x["answers"] in r["entries"]]
                score, _, row = _best(named, x["what"])
                matched = [row] if row is not None and (score > 0 or len(named) == 1) else named  # an answer to a letter answers it
            if not matched:  # by code: what is delivered matches what was asked of the sender
                score, _, row = _best(open_, x["what"])
                matched, how = ([row], "code") if row is not None and score >= 0.5 else ([], how)
            for r in matched:
                r["answered"] = {"n": e["n"], "date": e.get("date"), "how": how, "what": x["what"], "citations": x["citations"],
                                 **({"elsewhere": x["elsewhere"]} if x.get("elsewhere") else {}),
                                 "confirmed": overlap(x["what"], r["what"]) >= 0.34}
    # terms offered and agreed, in time order; an acceptance without terms of its own accepts the latest terms of another party
    terms = []
    for e in entries:
        own = e.get("terms") or []
        if e.get("kind") == "annahme" and terms:  # an acceptance accepts the latest terms: what it does not state, it takes from them
            if not own:
                last = terms[-1]
                own = [{**{k: last[k] for k in ("what", "amount", "payer", "by")}, "agreed": True,
                        "citations": e["citations"] + last["citations"], "accepts": last["n"]}]
            else:
                filled = []
                for t in own:
                    same = [x for x in terms if amount(x.get("amount")) == amount(t.get("amount"))] or ([terms[-1]] if amount(t.get("amount")) is None else [])
                    if same:
                        last = same[-1]
                        t = {**t, "what": t.get("what") or last.get("what"), "amount": t.get("amount") or last.get("amount"),
                             "payer": last.get("payer") if t.get("payer") in (None, "andere") else t["payer"], "by": t.get("by") or last.get("by"),
                             "accepts": last["n"], "citations": t["citations"] + last["citations"][:1]}
                    filled.append(t)
                own = filled
        for t in own:
            terms.append({**t, "n": e["n"], "date": e.get("date"), "from": e["from"], "phone": bool(e.get("phone")), "kind": e.get("kind"),
                          "agreed": bool(t.get("agreed")) or e.get("kind") == "annahme"})
    agreed = [t for t in terms if t["agreed"]]
    agreement = agreed[-1] if agreed else None
    paid = [{**p, "n": e["n"], "entry_date": e.get("date")} for e in entries for p in e.get("paid") or ()]
    payment = None
    if agreement:
        since = agreement.get("date") or ""
        want = amount(agreement.get("amount"))
        payment = next((p for p in paid if (p.get("date") or p.get("entry_date") or "") >= since
                        and (want is None or amount(p.get("amount")) in (None, want))
                        and p.get("payer") in (agreement.get("payer"), "andere", None)), None)
    owes = {p: [] for p in PARTIES}
    for r in requests:
        if r["answered"] is None:
            owes[r["of"]].append({"kind": "request", "request": r["id"], "what": r["what"], "since": r["first"], "times": r["times"],
                                  "due": r["due"], "by": r["by"], "of": r["of"], "warned": r["warned"], "citations": r["citations"]})
    if agreement and payment is None and agreement.get("payer") in owes:
        owes[agreement["payer"]].append({"kind": "payment", "what": agreement.get("what"), "amount": agreement.get("amount"),
                                         "due": agreement.get("by"), "citations": agreement["citations"]})
    actions, announced = [], False
    for e in entries:
        for code in code_of(e, kinds, announced, phone_code):
            actions.append({"code": code, "date": e.get("date"), "n": e["n"]})
        if e.get("from") == INSURER and e.get("kind") == "abschlussankuendigung":
            announced = True
    contacts = [e for e in entries if e.get("date") and e["from"] != e["to"]]
    return {"entries": entries, "requests": requests, "terms": terms, "agreement": agreement, "superseded": [t for t in terms if t is not agreement],
            "paid": paid, "payment": payment, "owes": owes, "actions": actions, "last_contact": contacts[-1] if contacts else None}


def from_result(result, graph=None):
    return build(entries_of(result), graph)


# -- the account in the process: action history, agreement facts, silence -------------------------------------------

HISTORY_FACTS = re.compile(r"handlung_a\d{1,2}|bisherige_handlungen")


def facts(acc, graph):
    """The facts the account sets: the insurer's actions taken (the history line and each kind's latest date, replacing
    what was read one fact at a time), and, where the process asks them, whether an agreement was reached and paid."""
    if not acc:
        return {}
    defined = {f["id"] for f in (graph or {}).get("facts") or ()}
    dated = sorted({(a["date"], a["code"]) for a in acc["actions"] if a["date"]})
    out = {}
    if "bisherige_handlungen" in defined and dated:
        out["bisherige_handlungen"] = "; ".join(f"A{c} {d}" for d, c in dated)
    for d, c in dated:
        if f"handlung_a{c}" in defined:
            out[f"handlung_a{c}"] = d  # sorted by date: the latest stays
    if acc["agreement"]:
        if "einigung" in defined:
            out["einigung"] = True
        if "zahlung_erhalten" in defined:
            out["zahlung_erhalten"] = acc["payment"] is not None
    return out


def merge(facts_in, acc, graph):
    """The case's facts with the account's: the action history is the account's alone; the agreement facts fill only
    what neither the reading nor the handler settled."""
    if not acc:
        return facts_in
    own = facts(acc, graph)
    out = {k: v for k, v in facts_in.items() if not HISTORY_FACTS.fullmatch(k)}
    for k, v in own.items():
        if HISTORY_FACTS.fullmatch(k) or out.get(k) is None:
            out[k] = v
    return out


def _after(acc, day, party):
    """Whether an entry from this party is dated after a day."""
    return any(e["from"] == party and e.get("date") and parse_date(e["date"]) > day for e in acc["entries"])


def silence(acc, rules, look, stage=None):
    """The clock's follow-up that is due because nobody answered, from the ledger: the insurer's last action, the party
    it was for has sent nothing since (what others sent does not end that silence), and the day the case is looked at is
    past the rule's days. The same shape as clock.silence; None otherwise."""
    if not acc or not rules:
        return None
    mine = [(parse_date(a["date"]), a["code"], a["n"]) for a in acc["actions"] if a["date"]]
    if not mine:
        return None
    sent, code, n = max(mine, key=lambda x: (x[0], x[2]))
    to = next((e["to"] for e in acc["entries"] if e["n"] == n), "kunde")
    if _after(acc, sent, to) or (to == INSURER):
        return None
    rule = next((r for r in rules if code in r["after"] and (stage is None or r.get("stages") is None or stage in r["stages"])), None)
    if rule and (look - sent).days > rule["days"]:
        return {**rule, "last": f"A{code}", "since": sent.isoformat(), "as_of": look.isoformat(), "silent_days": (look - sent).days,
                "ledger": True}
    return None


def derived(acc, kind, rules, look):
    """A derived fact the ledger decides (requests_count, replied_since_request, silent_after_requests); None for others."""
    asks = [(parse_date(e["date"]), e) for e in acc["entries"] if e["from"] == INSURER and e.get("date")
            and any(a["of"] == "kunde" for a in e.get("asks") or ())]
    if kind == "requests_count":
        n = len(asks)
        return "0" if n == 0 else "1" if n == 1 else "2+"
    if kind == "replied_since_request":
        return bool(asks) and _after(acc, asks[-1][0], "kunde")
    if kind == "silent_after_requests":  # asked at least twice, the last date passed, nothing from the customer since
        days = rules["requests"].get("1", REQUEST_DAYS)
        for r in acc["requests"]:
            last = parse_date(r["last"])
            if r["by"] != INSURER or r["of"] != "kunde" or r["answered"] is not None or not last or r["times"] < rules["min_requests"]:
                continue
            due = parse_date(r["due"]) if r["due"] and parse_date(r["due"]) >= last else last + timedelta(days=days)
            if look > due and not _after(acc, last, "kunde"):
                return True
        return False
    return None


def payout_due(acc, look):
    """The agreed payment not made whose date has passed: {amount, payer, due, ...}; None otherwise."""
    if not acc or not acc["agreement"] or acc["payment"] is not None:
        return None
    due = parse_date(acc["agreement"].get("by"))
    return acc["agreement"] if due and look > due else None


# -- what the handler sees -------------------------------------------------------------------------------------------

def day(value):
    d = parse_date(value)
    return d.strftime("%d.%m.%Y") if d else None


def _terms_text(t):
    """«Gegenpartei zahlt CHF 3'000 (Entschädigung) bis 30.04.2025»: who pays what by when, as read."""
    what = t.get("amount") or t.get("what") or "Vereinbarung"
    if t.get("amount") and t.get("what") and not words(t["what"]) <= words(t["amount"]):
        what = f"{t['amount']} ({t['what']})"
    payer = PARTY_TITLES.get(t.get("payer")) if t.get("payer") not in (None, "andere") else None
    text = f"{payer} zahlt {what}" if payer and t.get("amount") else what
    return text + (f" bis {day(t['by'])}" if t.get("by") else "")


def _source(t):
    return ("Telefon" if t.get("phone") else "Schreiben") + (f" vom {day(t['date'])}" if t.get("date") else "")


def _request_text(r, with_by=False):
    """One open request on one line, no brackets: «Belege der Reparaturkosten · seit 01.03.2025 · 3× verlangt von der
    Kanzlei · mit Androhung»; a customer's own question «… · Frage der Kundschaft vom 10.01.2025»."""
    first = r["since"] if "since" in r else r.get("first")
    if r.get("by") == "kunde" and r.get("of") in (INSURER, None):
        return f"{r['what']} · Frage der Kundschaft" + (f" vom {day(first)}" if first else "")
    asked = f"{r.get('times', 1)}× verlangt" + (f" von {WITH[r['by']]}" if with_by and r.get("by") else "")
    meta = [f"seit {day(first)}" if first else "", asked, "mit Androhung" if r.get("warned") else ""]
    return " · ".join([r["what"]] + [x for x in meta if x])


def first_report_only(acc):
    return not acc or len(acc["entries"]) <= 1 or all(e.get("kind") == "meldung" for e in acc["entries"])


def stand(acc, look, graph=None):
    """The «Stand» lines of «Der Fall», one each, only when there is something to say: what is agreed, what is open at
    the customer, at the other side or the firm, at the insurer, and the last contact. [{id, text, open, citations, entries}].
    Nothing for a case with only a first report, or none at all."""
    if first_report_only(acc):
        return []
    lines = []
    a = acc["agreement"]
    if a:
        due = parse_date(a.get("by"))
        state = (f"bezahlt am {day(acc['payment'].get('date') or acc['payment'].get('entry_date'))}" if acc["payment"]
                 else "überfällig" if due and look > due else "offen")
        was = [t for t in acc["superseded"] if (t.get("date") or "") <= (a.get("date") or "") and amount(t.get("amount")) not in (None, amount(a.get("amount")))]
        before = f"; ersetzt {was[-1].get('amount')} ({_source(was[-1])})" if was else ""
        payer = f" von {WITH[a['payer']]}" if a.get("payer") not in (None, "andere") else ""
        short = f"{a.get('amount') or a.get('what') or 'Vereinbarung'}{payer}" + (f" bis {day(a['by'])}" if a.get("by") else "") + f" · {state}"
        lines.append({"id": "vereinbart", "label": "Vereinbart", "text": short, "detail": f"{_terms_text(a)} · {state} · {_source(a)}{before}",
                      "open": acc["payment"] is None, "citations": a["citations"][:2] + ([c for c in was[-1]["citations"][:1]] if was else []),
                      "entries": [a["n"]] + ([was[-1]["n"]] if was else [])})
    for party in ("kunde", "gegenpartei", "kanzlei", "behoerde", "versicherer"):
        rows = [o for o in acc["owes"][party] if o["kind"] == "request"]
        if not rows:
            continue
        ledger = {r["id"]: r for r in acc["requests"]}
        shown = [{"text": _request_text(o, with_by=o["by"] != INSURER), "citations": o["citations"][:1],
                  "entries": list(ledger[o["request"]]["entries"]), "request": o["request"]} for o in rows[:SHOWN_PER_PARTY]]
        more = len(rows) - len(shown)
        label = "Offen bei uns" if party == INSURER else f"Offen {AT[party]}"
        lines.append({"id": f"offen_{party}", "label": label, "party": party, "rows": shown, "more": more,
                      "text": "; ".join(r["text"] for r in shown) + (f"; … {more} weitere" if more else ""), "open": True,
                      "citations": [c for r in shown for c in r["citations"]],
                      "entries": sorted({n for o in rows for n in ledger[o["request"]]["entries"]})})
    last = acc["last_contact"]
    if last:
        if last.get("phone"):
            what = f"Telefon mit {WITH[last['to'] if last['from'] == INSURER else last['from']]}"
        elif last["from"] == INSURER:
            what = f"{kinds_title(last.get('kind'), graph) or 'Schreiben'} an {WITH[last['to']]}"
        else:
            what = f"{kinds_title(last.get('kind'), graph) or 'Schreiben'} von {WITH[last['from']]}"
        lines.append({"id": "kontakt", "label": "Letzter Kontakt", "text": f"{day(last['date'])} · {what}", "open": False,
                      "citations": last["citations"][:1], "entries": [last["n"]]})
    return lines


def kinds_title(kind, graph=None):
    row = kinds_of(graph).get(kind) or {}
    return row.get("title")


def _where(element):
    """« · andere Stelle, S. 34» for an element whose quote was found outside its document's pages."""
    page = (element.get("elsewhere") or {}).get("page")
    return f" · andere Stelle, S. {page}" if element.get("elsewhere") else ""


def _by(element):
    """« bis 21.02.2025», « bis 21.02.2025 (berechnet: innert 14 Tagen)» or « (innert 14 Tagen ab Erhalt)»."""
    if element.get("by"):
        return f" bis {day(element['by'])}" + (f" (berechnet: {element['by_text']})" if element.get("by_computed") and element.get("by_text") else "")
    return f" ({element['by_text']})" if element.get("by_text") else ""


def rows(acc, graph=None):
    """The Verlauf: one row per entry in time order: date, who to whom, what, and what it asked, answered, agreed or paid,
    with open requests and an open agreement marked; ``open_of``: the parties whose open items the row carries."""
    if not acc:
        return []
    kinds = kinds_of(graph)
    open_ids = {r["id"] for r in acc["requests"] if r["answered"] is None}
    out = []
    for e in acc["entries"]:
        notes, is_open, open_of = [], False, set()
        for r in acc["requests"]:
            if e["n"] not in r["entries"]:
                continue
            own = _best([a for a in e.get("asks") or ()], r["what"])[2] or {}
            by = _by(own) + _where(own)
            done = f" · beantwortet (Nr. {r['answered']['n']})" if r["answered"] and r["entries"][-1] == e["n"] else ""
            if r["entries"][0] == e["n"] and r["by"] == "kunde" and r["of"] == INSURER:
                text = f"Frage an Protekta: {r['what']}{_where(own)}"
            elif r["entries"][0] == e["n"]:
                text = f"verlangt von {WITH[r['of']]}: {r['what']}{by}"
            else:
                text = f"erneut verlangt ({r['entries'].index(e['n']) + 1}.): {r['what']}{by}" + (" · mit Folgen gewarnt" if any(a.get("warns") for a in e.get("asks") or ()) else "")
            notes.append({"kind": "asked", "text": text + done, "open": r["id"] in open_ids})
            if r["id"] in open_ids:
                is_open = True
                open_of.add(r["of"])
        for r in acc["requests"]:
            if r["answered"] and r["answered"]["n"] == e["n"]:
                notes.append({"kind": "answered", "text": f"beantwortet: {r['what']}" + (f" (zu Nr. {r['entries'][-1]})" if r["entries"] else "")
                              + _where(r["answered"]), "open": False})
        for t in acc["terms"]:
            if t["n"] == e["n"]:
                current = t is acc["agreement"]
                word = "vereinbart" if t["agreed"] else "angeboten"
                notes.append({"kind": "agreed" if t["agreed"] else "offered", "text": f"{word}: {_terms_text(t)}" + ("" if current or not t["agreed"] else " (ersetzt)") + _where(t),
                              "open": current and acc["payment"] is None})
                if current and acc["payment"] is None:
                    is_open = True
                    open_of.add(t.get("payer") or "andere")
        for p in e.get("paid") or ():
            notes.append({"kind": "paid", "text": f"bezahlt: {p.get('amount') or ''}" + (f" am {day(p['date'])}" if p.get("date") else "") + _where(p), "open": False})
        for x in e.get("next") or ():
            notes.append({"kind": "next", "text": f"nächster Schritt: {x['what']}" + (f" (bis {day(x['by'])})" if x.get("by") else f" ({x['by_text']})" if x.get("by_text") else "") + _where(x),
                          "open": False})
        out.append({"n": e["n"], "date": e.get("date"), "from": e["from"], "to": e["to"], "from_title": PARTY_TITLES[e["from"]],
                    "to_title": PARTY_TITLES[e["to"]], "kind": e.get("kind"), "kind_title": (kinds.get(e.get("kind")) or {}).get("title") or e.get("kind"),
                    "phone": bool(e.get("phone")), "what": e.get("what"), "notes": notes, "open": is_open, "open_of": sorted(open_of),
                    "citations": e["citations"] + [c for k in ELEMENTS for el in e.get(k) or () for c in el["citations"]][:4]})
    return out


# -- what the account holds for a prescribed letter and for «Fristen» ---------------------------------------------------

def warnings(acc):
    """The written demands to the customer that warn of the consequences, as the account holds them, oldest first:
    [{by, by_title, date, due, what, n, own, citations}]; ``own``: the insurer's own. A phone note is not written."""
    out = []
    for e in (acc or {}).get("entries") or ():
        if e.get("phone"):
            continue
        for a in e.get("asks") or ():
            if a.get("of") == "kunde" and a.get("warns"):
                out.append({"by": e["from"], "by_title": PARTY_TITLES[e["from"]], "date": e.get("date"), "due": a.get("by"),
                            "due_text": a.get("by_text"), "what": a.get("what"), "n": e["n"], "own": e["from"] == INSURER,
                            "citations": a["citations"][:1] or e["citations"][:1]})
    return sorted(out, key=lambda w: (w["date"] or "9999", w["n"]))


def open_items(acc, party):
    """What is asked of a party and not delivered, from the ledger: [{what, first, by, times, warned}] in the order asked."""
    return [{"what": r["what"], "first": r["first"], "by": r["by"], "times": r["times"], "warned": r["warned"]}
            for r in (acc or {}).get("requests") or () if r["of"] == party and r["answered"] is None and r["by"] != party]


def open_dates(acc):
    """The dates by which someone must act that the account holds and that are still open: an unanswered request's date,
    an offer's date while nothing followed it, an agreed payment not made, a stated next step whose party has not acted
    since. [{key, date, what, set_by, for, source, n, computed, citations}], one per date and obligation."""
    if not acc:
        return []
    by_n = {e["n"]: e for e in acc["entries"]}
    out = []

    def add(key, when, what, set_by, for_, n, citations, computed=False, text=None):
        e = by_n.get(n) or {}
        if any(x["date"] == when and x["for"] == for_ and overlap(x["what"], what) >= 0.5 for x in out):
            return
        out.append({"key": key, "date": when, "what": what, "set_by": set_by, "for": for_, "n": n, "computed": computed,
                    "text": text, "source": _source({"phone": e.get("phone"), "date": e.get("date")}), "citations": citations[:1]})

    for r in acc["requests"]:
        if r["answered"] is None and r["due"]:
            n = r.get("due_n") or r["entries"][-1]
            add(f"konto-{r['id']}", r["due"], r["what"], r["by"], r["of"], n, r["citations"][-1:], r.get("due_computed"), r.get("due_text"))
    later_terms = lambda t: any((x.get("date") or "") > (t.get("date") or "") for x in acc["terms"] if x is not t)
    for t in acc["terms"]:
        if not t.get("by"):
            continue
        if t is acc["agreement"] and acc["payment"] is None:
            add(f"konto-t{t['n']}", t["by"], f"Zahlung {t.get('amount') or t.get('what') or ''}".strip(), t["from"], t.get("payer") or "andere",
                t["n"], t["citations"], t.get("by_computed"), t.get("by_text"))
        elif not t["agreed"] and acc["agreement"] is None and not later_terms(t):
            to = (by_n.get(t["n"]) or {}).get("to") or "andere"
            add(f"konto-t{t['n']}", t["by"], f"Antwort auf das Angebot: {_terms_text({**t, 'by': None})}", t["from"], to,
                t["n"], t["citations"], t.get("by_computed"), t.get("by_text"))
    for e in acc["entries"]:
        for i, x in enumerate(e.get("next") or ()):
            if x.get("by") and not (e.get("date") and _after(acc, parse_date(e["date"]), x.get("who"))):
                add(f"konto-x{e['n']}-{i}", x["by"], x["what"], e["from"], x.get("who") or "andere", e["n"], x["citations"],
                    x.get("by_computed"), x.get("by_text"))
    return sorted(out, key=lambda x: x["date"])


def note(acc, look, graph=None):
    """The account in the file note: one sentence per «Stand» line."""
    return " ".join(f"{line['label']}: {line.get('detail') or line['text']}." for line in stand(acc, look, graph))
