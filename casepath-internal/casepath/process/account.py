"""The running account of a case: one short entry per document of the file, and what follows from the entries by code.

The reader returns, for each document of the file (phone notes included), one entry: its date, from and to, the kind
of step (the backbone's closed list ``record.kinds``), whether it is a phone note, one line on what it is, and the
elements the document states: what it asks (what, of whom, by when, and the earlier entry it repeats), what it
delivers or answers (and the earlier entry it answers), the terms offered or agreed (what, amount, who pays, by when),
what was paid, and the next step it states with its date. Every element carries a quote located in that document
(``check``): an element whose quote is not found there is dropped and counted, an entry whose own quote is not found
is dropped whole.

From the entries, by code (``build``):
- the requests ledger: each thing asked (its id «r<n>.<i>»: the entry that first asks it and the ask's place there), by
  whom, of whom, first and last asked, by when, how often, whether answered, by which entry, and whether the answer
  matches what was asked (``confirmed``);
- the agreement as it stands: the latest agreed terms, earlier terms and offers kept as history, and whether paid;
- who owes what now: open requests by the party asked, and an agreed payment not made;
- the insurer's actions taken (A1 … A12 with their dates), which replace the action facts read one by one (``facts``);
- silence and lack of cooperation, read from the ledger rather than from counters (``silence``, ``derived``).

The handler's own entries (``handler_entry``): a phone call, a conversation, a note or an e-mail outside the file,
entered in a short form and kept as the case's edits (op «add_entry»). Each is an entry like any other, from the insurer
to the party it was with, with «Fallbearbeitung» and the user as its source instead of a quote, numbered from
``HANDLER_BASE`` so a reader's number never meets it. It counts at once: the account, «Stand», the dates and the next
action are recomputed from it without a model.

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
TO = {"kunde": "die Kundschaft", "versicherer": "Protekta", "kanzlei": "die Kanzlei", "gegenpartei": "die Gegenpartei",  # «an …» (accusative)
      "behoerde": "Gericht/Behörde", "andere": "Dritte"}
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


def kept(result):
    """Whether a stored run recorded the running account (a run of process 2026-11-15.1 or later), even with no entry."""
    return isinstance((result or {}).get("record"), dict)


# -- the handler's own entries ------------------------------------------------------------------------------------------

HANDLER_BASE = 9000  # the handler's entries are numbered 9001, 9002 …: never a number a reader gives a document
FORM_KINDS = {"telefon": "Telefon", "gespraech": "Gespräch", "notiz": "Notiz", "email": "E-Mail ausserhalb der Akte"}
FORM_PARTIES = ("kunde", "gegenpartei", "kanzlei", "behoerde", "andere")
HANDLER_SOURCE = "Fallbearbeitung"


class FormError(ValueError):
    """A handler's entry the form cannot keep, with what is wrong in the handler's words."""


def _amount_text(value):
    """An amount as the handler typed it; plain digits get «CHF» before them («2500» → «CHF 2'500»)."""
    text = _clip(value, 40)
    if re.fullmatch(r"\d[\d'’ ]*(?:[.,]\d{1,2})?", text):
        whole, _, cents = re.sub(r"[’' ]", "", text).replace(",", ".").partition(".")
        whole = re.sub(r"(?<=\d)(?=(\d{3})+$)", "'", whole)
        return f"CHF {whole}" + (f".{cents}" if cents else "")
    return text


def check_form(form):
    """The handler's entry as the form sends it, checked and trimmed: {kind, party, name, date, said, agreed, asked, next}.
    A structured part counts only when its «what» (agreed: or its amount) is filled; every date is a day (YYYY-MM-DD or
    TT.MM.JJJJ). Raises FormError, in the handler's words, for anything else."""
    form = form if isinstance(form, dict) else {}
    kind = str(form.get("kind") or "")
    if kind not in FORM_KINDS:
        raise FormError("Art des Eintrags: Telefon, Gespräch, Notiz oder E-Mail ausserhalb der Akte")
    party = str(form.get("party") or "kunde")
    if party not in FORM_PARTIES:
        raise FormError("Mit wem: Kundschaft, Gegenpartei, Kanzlei, Behörde oder andere")
    day = _iso(form.get("date"))
    if not day:
        raise FormError("Datum des Eintrags fehlt")

    def by(row, label):
        if not str(row.get("by") or "").strip():
            return None
        due = _iso(row.get("by"))
        if not due:
            raise FormError(f"{label}: «bis» ist kein Datum")
        return due

    def part(key):
        row = form.get(key)
        return row if isinstance(row, dict) else {}
    agreed, asked, nxt = part("agreed"), part("asked"), part("next")
    out = {"kind": kind, "party": party, "name": _clip(form.get("name"), 120), "date": day, "said": str(form.get("said") or "").strip()[:2000],
           "agreed": None, "asked": None, "next": None}
    if _clip(agreed.get("what"), 120) or _clip(agreed.get("amount"), 40):
        payer = agreed.get("payer") or (party if party == "gegenpartei" else None)  # agreed with the other side: it pays, unless said
        if payer is not None and payer not in PARTIES:
            raise FormError("Vereinbart: wer zahlt?")
        out["agreed"] = {"what": _clip(agreed.get("what"), 120) or "Einigung", "amount": _amount_text(agreed.get("amount")) or None,
                         "payer": payer, "by": by(agreed, "Vereinbart")}
    if _clip(asked.get("what"), 120):
        of = asked.get("of") or party
        if of not in PARTIES or of == INSURER:
            raise FormError("Verlangt: von wem?")
        out["asked"] = {"what": _clip(asked.get("what"), 120), "of": of, "by": by(asked, "Verlangt")}
    if _clip(nxt.get("what"), 120):
        who = nxt.get("who") or party  # what the one it was with does next, unless the handler names another
        if who not in PARTIES:
            raise FormError("Nächster Schritt: wer?")
        out["next"] = {"what": _clip(nxt.get("what"), 120), "who": who, "by": by(nxt, "Nächster Schritt")}
    if not out["said"] and not any(out[k] for k in ("agreed", "asked", "next")):
        raise FormError("Was besprochen wurde, fehlt")
    return out


def handler_entry(form, n, by=None, at=None, edit=None):
    """The account's entry for a handler's checked form (check_form): from the insurer to the party it was with (a note:
    to itself, a file note), «Telefonnotiz» or, with something agreed, «Annahme»; no quote: its source is the handler."""
    party, kind = form["party"], form["kind"]
    to = INSURER if kind == "notiz" else party
    terms = [{"what": t["what"], "amount": t["amount"], "payer": t["payer"], "by": t["by"], "agreed": True, "citations": []}
             for t in [form.get("agreed")] if t]
    asks = [{"what": a["what"], "of": a["of"], "by": a["by"], "repeats": None, "warns": False, "citations": []} for a in [form.get("asked")] if a]
    nxt = [{"what": x["what"], "who": x["who"], "by": x["by"], "citations": []} for x in [form.get("next")] if x]
    said = re.sub(r"\s+", " ", form.get("said") or "").strip()
    what = said or "; ".join(x for x in [(terms and f"vereinbart: {_terms_text(terms[0])}"), (asks and f"verlangt: {asks[0]['what']}"),
                                         (nxt and f"nächster Schritt: {nxt[0]['what']}")] if x)
    return {"n": int(n), "file": None, "page": None, "date": form["date"], "from": INSURER, "to": to,
            "kind": "annahme" if terms else "telefon", "phone": kind == "telefon", "what": _clip(what, 160), "said": form.get("said") or "",
            "citations": [], "asks": asks, "answers": [], "terms": terms, "paid": [], "next": nxt,
            "handler": {"by": by, "at": at, "kind": kind, "party": party, "name": form.get("name") or "", "edit": edit,
                        "form": {k: form.get(k) for k in ("kind", "party", "name", "date", "said", "agreed", "asked", "next")}}}


def handler_entries(edits):
    """The handler's entries in force: one per active «add_entry» edit (a changed entry is a new edit with the same
    number, the old one «replaced»; a removed one «removed»), oldest first."""
    out = []
    for e in edits or ():
        if e.get("op") != "add_entry" or e.get("status", "active") != "active":
            continue
        args = e.get("args") or {}
        try:
            form = check_form(args)
        except FormError:
            continue
        if isinstance(args.get("n"), int) and args["n"] > HANDLER_BASE:
            out.append(handler_entry(form, args["n"], by=e.get("by"), at=e.get("at"), edit=e.get("id")))
    return out


NUMBERED = ("add_entry", "add_dispatch")  # the handler's entries and the dispatches draw their numbers from one sequence


def next_number(edits):
    """The number of the next handler's entry or dispatch: after every number either ever had in the case (a removed or
    replaced one's included), from HANDLER_BASE."""
    used = [(e.get("args") or {}).get("n") for e in edits or () if e.get("op") in NUMBERED]
    return max([n for n in used if isinstance(n, int)] + [HANDLER_BASE]) + 1


def next_handler_number(edits):
    """The number of the handler's next entry (next_number)."""
    return next_number(edits)


def with_handler(entries, edits):
    """A run's entries with the handler's entries in force (their own numbers: none can meet a reader's)."""
    return list(entries or ()) + handler_entries(edits)


def dispatch_facts(edits, graph=None):
    """For a run prepared before the account (from_result is None): the action facts the dispatches in force set,
    {handlung_a<code>: the dispatch date}, which core.evaluate merges, so the clock and the last contact move from them.
    Nothing until Slice B records dispatches."""
    return {}


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
MONTH_END = re.compile(r"\bende\s+(?:(des|dieses|diesen|laufenden|nächsten|naechsten|kommenden|folgenden)\s+)*monats?\b", re.I)
CHECK_DATE = "Frist laut Akte, Datum prüfen"  # a date the file sets that no rule can read: said so, never guessed


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
    end = MONTH_END.search(text or "")
    if end and start:  # «bis Ende Monat»: the last day of the document's month, «Ende nächsten Monats» the next one's
        later = int(bool(re.search(r"nächst|naechst|kommend|folgend", end.group(0), re.I)))
        first = date(start.year + (start.month + later) // 12, (start.month + later) % 12 + 1, 1)
        return (first - timedelta(days=1)).isoformat(), text, True
    return None, text, False


def stored(element, entry_date):
    """An element of a stored entry as the account reads it. A run stored before the reader gave ``by_date`` kept only
    its words in «by» (a date written out, «innert 14 Tagen», «bis Ende Monat»): a written date is that date, a period
    is counted from the entry's own date and marked computed, anything else has no date and is marked to check
    (``by_check``). An element already read so, or without a «by», is returned as it is."""
    raw = element.get("by")
    if not raw or element.get("by_text") or element.get("by_computed") or re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(raw)):
        return element
    due, text, computed = due_of({"by": raw}, entry_date)
    return {**element, "by": due, **({"by_text": text} if text and (computed or not due) else {}),
            **({"by_computed": True} if computed else {}), **({"by_check": True} if not due else {})}


def _stored_entry(e):
    return {**e, **{k: [stored(x, e.get("date")) for x in e.get(k) or ()] for k in ("asks", "terms", "next")}}


def _clip(text, n):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text if len(text) <= n else text[:n - 1].rstrip() + "…"


SENDER_LINE = re.compile(r"^\s*(?:Von|From|Absender)\s*:\s*(.+)$", re.M | re.I)
TO_LINE = re.compile(r"^\s*(?:An|To)\s*:\s*(.+)$", re.M | re.I)


def _on_its_pages(entry, page_text):
    """C10g, read once: an entry's day is to check («Datum prüfen», date_check) only when it is written nowhere on the
    pages its quotes are on, an e-mail's header lines included (a forwarded message keeps its own date); its sender (or
    addressee) is to check («Absender prüfen», from_check / to_check) when every sender line there names a party and none
    is the one the reader gave."""
    pages = {c.get("page") for c in entry["citations"]} | {c.get("page") for k in ELEMENTS for x in entry.get(k) or () for c in x.get("citations") or ()}
    text = "\n".join(page_text(entry.get("file"), p) or "" for p in sorted(pages, key=lambda p: (p is None, p or 0)))
    if not text.strip():
        return entry
    if entry.get("date") and entry["date"] not in written_dates(text):
        entry["date_check"] = True
    for key, line in (("from", SENDER_LINE), ("to", TO_LINE)):
        named = [party_of(m.split("<")[0]) for m in line.findall(text)]
        if named and "andere" not in named and entry[key] not in named:
            entry[f"{key}_check"] = True
    return entry


def check(raw, locate, kinds, elsewhere=None, issues=None, page_text=None):
    """One entry of the reader, as the account keeps it: (entry or None, elements dropped).

    ``locate(quote)`` returns the located citation within this entry's own document (its page range as code knows it),
    or None. The entry's own quote must be found there, or the entry is dropped (it counts as one). An element whose
    quote is not found there but ``elsewhere(quote)`` finds it in the same file is kept, marked with the page where it
    was found («andere Stelle»); one found nowhere is dropped and counted. ``issues`` collects, per element not found in
    its document, its kind and the reason: «elsewhere» (kept) or «not_found» (dropped). ``page_text(file, page)``: the
    text of a page of the file (the whole file for None), to check the entry's day and sender there (_on_its_pages)."""
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
            if key == "answers" and isinstance(element.get("request"), str) and re.fullmatch(r"r\d+\.\d+", element["request"]):
                row["request"] = element["request"]  # the row it answers, by the id case_so_far gave it (C8)
            kept.append(row)
        entry[key] = kept
    receipt = _receipt_record(raw.get("receipt"), locate, elsewhere, n, issues)  # what a receipt in this document records (C10c)
    if receipt is not None:
        entry["receipt"] = receipt
    elif isinstance(raw.get("receipt"), dict):
        dropped += 1
    return (_on_its_pages(entry, page_text) if page_text else entry), dropped


def _receipt_record(raw, locate, elsewhere, n, issues):
    """A reader's record of a receipt or bill in the entry's document (Slice A's reading, C10c): {expense, party, payer,
    period {from, to}, transaction, amount, role, citations}. Kept only with its quote located there; its amount only when
    the quote writes it, its days only when written there, its role only one of RECEIPT_ROLES. None otherwise."""
    if not isinstance(raw, dict):
        return None
    hit = locate(raw.get("quote")) or (elsewhere(raw.get("quote")) if elsewhere else None)
    if not hit:
        issues.append({"n": n, "kind": "receipt", "reason": "not_found", "kept": False})
        return None
    quote = str(hit.get("quote") or raw.get("quote") or "")
    period = raw.get("period") if isinstance(raw.get("period"), dict) else {}
    written = written_dates(quote)
    days = {k: _iso(period.get(k)) for k in ("from", "to") if _iso(period.get(k)) in written}
    number = amount(raw.get("amount"))
    return {"expense": _clip(raw.get("expense"), 80) or None, "party": _clip(raw.get("party"), 80) or None,
            "payer": _clip(raw.get("payer"), 80) or None, "period": days or None, "transaction": _clip(raw.get("transaction"), 40) or None,
            "amount": _clip(raw.get("amount"), 40) if number is not None and number in money(quote) else None,
            "role": raw.get("role") if raw.get("role") in RECEIPT_ROLES else None, "citations": [hit]}


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
    if (entry.get("phone") or entry.get("handler")) and phone_code not in codes:  # the handler's own entry is a file note (A2)
        codes.append(phone_code)
    return codes


GENERIC_DOCUMENTS = {"unterl", "dokume", "belege", "nachwe", "angabe", "papier", "sachen"}  # «die Unterlagen» as a whole


def promised(requests, e, x):
    """The open requests a stated next step of the party asked gives a date to («Unterlagen folgen bis 15.12.»): the one
    whose words it shares, else all of that party's open requests when it names documents as a whole or only one is
    open. A request asked in the same entry is not one."""
    if not x.get("by") or not x.get("who"):
        return []
    open_ = [r for r in requests if r["of"] == x["who"] and r["answered"] is None and r["entries"][0] != e["n"]]
    score, _, row = _best(open_, x.get("what"))
    if row is not None and score >= 0.5:
        return [row]
    return open_ if open_ and (len(open_) == 1 or words(x.get("what")) & GENERIC_DOCUMENTS) else []


# -- the account's checks (Slice C, C10): a live case's account; a frozen study copy keeps the rules it was frozen with ---

SPLIT = re.compile(r",\s+|;\s+|\s+und\s+|\s+sowie\s+")
LEAD = {"die", "der", "das", "den", "dem", "des", "ein", "eine", "einen", "einem", "eines", "ihr", "ihre", "ihren", "ihrem", "ihres", "mein",
        "meine", "meinen", "unser", "unsere", "alle", "allfällige", "sämtliche", "weitere", "kopie", "kopien", "noch", "auch", "zudem", "nur",
        "ausserdem", "bitte"}
NEGATION = re.compile(r"\b(?:kein|keine|keinen|keinem|keiner|keines|nicht|nie)\b", re.I)
PROMISE_WORDS = re.compile(r"nachreich|\bwerde\b|\bfolgt\b|\bfolgen\b|\bsobald\b|später|\bdemnächst\b", re.I)
DELIVERY_WORDS = re.compile(r"\banbei\b|\bim anhang\b|beilieg|beigelegt|\bsende ihnen\b|übermittl|zugestellt", re.I)
DELIVERY_ASKED = re.compile(r"send|zustell|schick|einreich|nachreich|beileg|beifüg|übermittl|zukommen", re.I)
COMPLETION_WORDS = re.compile(r"überwiesen|bezahlt|beglichen|gutgeschrieben|eingegangen|erhalten|\bvaluta\b", re.I)
INSTRUCTION_WORDS = re.compile(r"\bbitte\b|zahlbar|\bwird\b|\bwerden\b|veranlass|ankündig", re.I)
# words that say how something is asked or answered, never what: left out when an answer is scored against a request
FUNCTION_WORDS = {"auf", "aus", "bei", "nach", "ich", "sie", "mir", "mich", "sich", "ihnen", "ist", "sind", "war", "hat", "haben", "habe", "wird",
                  "werden", "kann", "können", "muss", "müssen", "soll", "darf", "wie", "was", "wer", "wann", "warum", "weil", "dass", "wenn", "nicht",
                  "kein", "keine", "keinen", "letzte", "anbei", "beilie", "beigel", "folgen", "folgt", "nachre", "zugest", "sende", "senden", "erhalt",
                  "bereit", "schon", "immer", "heute", "gerne", "dieser", "diese", "dieses", "nur", "auch", "zudem", "ausser", "möchte", "wurde", "wurden"}
MONTH_NUMBERS = {"januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4, "mai": 5, "juni": 6, "juli": 7, "august": 8, "september": 9,
                 "oktober": 10, "november": 11, "dezember": 12, "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8,
                 "sep": 9, "oct": 10, "nov": 11, "dec": 12}
WRITTEN_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b|\b(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{4})\b|\b(\d{1,2})\.?\s+([A-Za-zÄäÖöÜü]{3,9})\.?\s+(\d{4})\b")
FLAGS = {"amount": "Betrag nicht im Zitat – prüfen", "date": CHECK_DATE, "consent": "Zustimmung der Kundschaft (nicht der Gegenpartei)",
         "unspecified": "Antwort ohne Zuordnung – prüfen", "third": "Forderung Dritter – prüfen", "entry_date": "Datum prüfen",
         "sender": "Absender prüfen"}
COUNTERPARTY = "gegenpartei"
CUSTOMER_SIDE = {"kunde", "versicherer", "kanzlei"}


def written_dates(text):
    """The days a text writes (05.09.2026, 5. September 2026, 2026-09-05, an e-mail's «Sat, 05 Sep 2026»), as ISO days."""
    out = set()
    for m in WRITTEN_DATE.finditer(str(text or "")):
        try:
            if m.group(1):
                d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            elif m.group(4):
                d = date(int(m.group(6)), int(m.group(5)), int(m.group(4)))
            else:
                month = MONTH_NUMBERS.get(m.group(8).lower()) or MONTH_NUMBERS.get(m.group(8).lower()[:3])
                if not month:
                    continue
                d = date(int(m.group(9)), month, int(m.group(7)))
        except ValueError:
            continue
        out.add(d.isoformat())
    return out


def written_amounts(text):
    """The amounts a text writes («CHF 3'000.–», «85.40», «1 200»), its days left out (a day is not an amount)."""
    rest = WRITTEN_DATE.sub(" ", str(text or ""))
    out = set()
    for m in re.finditer(r"\d{1,3}(?:[’' ]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?", rest):
        try:
            out.add(float(re.sub(r"[’' ]", "", m.group(0)).replace(",", ".")))
        except ValueError:
            continue
    return out


def content(text):
    """The words that say what is asked or answered (``words`` without the words of asking and answering)."""
    return {w for w in words(text) if w not in FUNCTION_WORDS}


def score(answer, request):
    """How much of a request an answer names: |answer ∩ request| / |request|, over their content words; 0 without any."""
    asked = content(request)
    return len(content(answer) & asked) / len(asked) if asked else 0.0


def _listed(part):
    """A list item: it names something (its first word after an article or a quantifier is a noun) and keeps a content word."""
    tokens = re.findall(r"[A-Za-zÄÖÜäöüß]+", part)
    lead = next((t for t in tokens if t.lower() not in LEAD), None)
    return bool(lead) and lead[0].isupper() and bool(content(part))


def items_of(what, questions=False):
    """A combined ask (or answer) split into its items on «, », «; », « und », « sowie », when every part is a list item
    that keeps a content word; a question (``questions`` False) is one thing asked."""
    text = str(what or "")
    if "?" in text and not questions:
        return [text]
    parts = [p.strip(" .:;") for p in SPLIT.split(text)]
    parts = [p for p in parts if p]
    return parts if len(parts) > 1 and all(_listed(p) for p in parts) else [text]


def _quote(element):
    return " ".join(str(c.get("quote") or "") for c in element.get("citations") or ())


def is_question(row):
    """A question asked for information, which a «no» answers (not a document asked in the form of a question)."""
    text = f"{row.get('what') or ''} {_quote(row)}"
    return "?" in text and not DELIVERY_ASKED.search(text)


def typed_parts(x):
    """An answer element split into its parts, each typed alone (C10b): «refusal» (a negation), «promise» (a promise word
    and no delivery word) or «answer»; each part with the words of the element's quote it rests on, and the day a promise
    names. «Fotos anbei, Belege zu den Stromkosten folgen» is one delivery and one promise."""
    quote = _quote(x)
    quotes = items_of(quote, questions=True) if quote else []
    out = []
    for what in items_of(x.get("what"), questions=True):
        pick = max(quotes, key=lambda q: len(content(q) & content(what))) if quotes else ""
        if not pick or not content(pick) & content(what):
            pick = quote
        text = f"{what} {pick}"
        kind = "refusal" if NEGATION.search(text) else "promise" if PROMISE_WORDS.search(text) and not DELIVERY_WORDS.search(text) else "answer"
        days = sorted(written_dates(pick))
        out.append({"what": what, "quote": pick, "type": kind, **({"by": days[-1]} if kind == "promise" and days else {})})
    return out


def _dated(element, entry):
    """An element's day kept only where its quote writes it (or, counted from the entry, the period it states); otherwise
    «Frist laut Akte, Datum prüfen» (by_check): a flagged element dates nothing."""
    if not element.get("by") or element.get("by_check"):
        return element
    quote = _quote(element)
    if element.get("by_computed"):
        ok = not entry.get("date_check") and bool(PERIOD_WORDS.search(quote) or MONTH_END.search(quote))
    else:
        ok = element["by"] in written_dates(quote)
    return element if ok else {**element, "by": None, "by_text": CHECK_DATE, "by_check": True, "by_computed": False, "by_dropped": element["by"]}


def _amounted(element):
    """An element's amount kept only where its quote writes it; otherwise «Betrag nicht im Zitat – prüfen»: a flagged
    element agrees and pays nothing."""
    number = amount(element.get("amount"))
    if element.get("amount") and (number is None or number not in written_amounts(_quote(element))):
        return {**element, "amount": None, "amount_check": element["amount"], "flag": FLAGS["amount"]}
    return element


PAYER_RECEIVES = {"gegenpartei": {"kunde", "versicherer", "kanzlei"}, "andere": {"kunde", "versicherer", "kanzlei"},
                  "behoerde": {"kunde", "versicherer", "kanzlei"}, "kunde": {"gegenpartei", "andere", "versicherer"},
                  "versicherer": {"kunde", "kanzlei", "gegenpartei"}, "kanzlei": {"kunde", "gegenpartei"}}


def _payment(p, entry):
    """A payment (C10i), not an instruction or an announcement: its amount written in its quote, a word that it is done and
    none that it is asked or still to come, its payer named, and the entry from the payer or the one paid (a phone note of
    ours: the party we spoke with)."""
    quote = _quote(p)
    speaker = entry["to"] if entry.get("phone") and entry["from"] == INSURER else entry["from"]
    return (bool(p.get("amount")) and not p.get("amount_check") and bool(COMPLETION_WORDS.search(quote)) and not INSTRUCTION_WORDS.search(quote)
            and p.get("payer") not in (None, "andere") and speaker in {p["payer"]} | PAYER_RECEIVES.get(p["payer"], set())
            and not entry.get("flagged"))


def _asker(a, entry):
    """Who asks (C10j): the entry's sender, unless it is the one asked: then the party the quote names (a demand of the
    other side reported by the customer), else a third party, never someone owed by us («Forderung Dritter – prüfen»)."""
    if a.get("of") != entry["from"]:
        return entry["from"], False
    text = _quote(a).lower()
    short = next((PARTY_SHORT[w] for w in re.findall(r"\w+", text) if w in PARTY_SHORT and PARTY_SHORT[w] != entry["from"]), None)
    named = short or next((party for party, said in PARTY_WORDS if party != entry["from"] and any(w in text for w in said)), None)
    return (named, False) if named else ("andere", True)


def _valued(entry):
    """An entry as the checked account reads it: its elements' values kept only where their quotes write them, payments
    told from instructions (an instruction or announcement becomes a next step), the asker of a reported demand, and its
    answers split into typed parts."""
    e = dict(entry)
    e["flagged"] = bool(e.get("from_check") or e.get("to_check"))
    if e.get("handler") or e.get("dispatch"):  # entered by a person or recorded at dispatch: its source is that person, not a quote
        return {**e, "asks": [{**a, "asker": e["from"]} for a in e.get("asks") or ()],
                "answers": [{**x, "parts": typed_parts(x)} for x in e.get("answers") or ()]}
    asks = []
    for a in e.get("asks") or ():
        a = _dated(dict(a), e)
        asker, third = _asker(a, e)
        asks.append({**a, "asker": asker, **({"third": True} if third else {})})
    nxt = [_dated(dict(x), e) for x in e.get("next") or ()]
    paid = []
    for p in e.get("paid") or ():
        p = _amounted(dict(p))
        if _payment(p, e):
            paid.append(p)
            continue
        day = p.get("date") if p.get("date") in written_dates(_quote(p)) else None
        nxt.append({"what": " ".join(x for x in ("Zahlung", p.get("amount") or p.get("amount_check") or "", "angekündigt") if x), "who": p.get("payer") or e["from"],
                    "by": day, "citations": p["citations"], "announced": True, **({"flag": p["flag"]} if p.get("flag") else {})})
    e.update(asks=asks, next=nxt, paid=paid, terms=[_dated(_amounted(dict(t)), e) for t in e.get("terms") or ()],
             answers=[{**x, "parts": typed_parts(x)} for x in e.get("answers") or ()])
    return e


def _same_documents(entries, kinds, phone_code):
    """C10e: an entry with the same day, sender, addressee, kind and own quote as an earlier one is that document read
    again (no row, no count); a reader's entry of ours with the addressee and the action of a dispatch in force, dated
    within three days of it, is that dispatch as quoted in a later reply: its quote joins the dispatch's entry and nothing
    of it counts again. Returns (entries, [{n, into, why}])."""
    out, seen, merged = [], {}, []
    dispatches = [e for e in entries if e.get("dispatch")]
    for e in entries:
        read = not e.get("handler") and not e.get("dispatch")  # a reader's entry; a person's entry or a dispatch is its own
        if read and e["from"] == INSURER and e.get("date"):
            mine = set(code_of(e, kinds, False, phone_code)) - {phone_code}
            day = parse_date(e["date"])
            sent = next((d for d in dispatches if d["to"] == e["to"] and d.get("date") and mine
                         and set([d["code"]] if d.get("code") else code_of(d, kinds, False, phone_code)) - {phone_code} == mine
                         and abs((parse_date(d["date"]) - day).days) <= 3), None)
            if sent is not None:
                sent["citations"] = list(sent.get("citations") or []) + list(e.get("citations") or [])
                sent.setdefault("quoted", []).append(e["n"])
                merged.append({"n": e["n"], "into": sent["n"], "why": "dispatch"})
                continue
        own = ((e.get("citations") or [{}])[0] or {}).get("quote")
        key = (e.get("date"), e["from"], e["to"], e.get("kind"), own)
        if own and read and key in seen:
            merged.append({"n": e["n"], "into": seen[key], "why": "same"})
            continue
        if own and read:
            seen.setdefault(key, e["n"])
        out.append(e)
    return out, merged


def _side(party):
    return "versicherer" if party in ("versicherer", "kanzlei") else party


def _offer_of_the_other_side(x):
    """Terms the other side offers: in its own letter, or reported by the firm or another (its payer the other side)."""
    return x["from"] == COUNTERPARTY or (COUNTERPARTY not in (x["from"], x.get("to")) and x.get("payer") == COUNTERPARTY)


def _agrees(t, terms):
    """C10h: agreed terms are an agreement when both sides are on them: terms agreed by or with the other side (its
    letter, a phone note of ours or the firm's with it), the handler's own entry of agreed terms, or an assent of the
    customer's side to terms from or with the other side on the same amount. An assent passed only between the customer
    and us on the other side's offer is «Zustimmung der Kundschaft»: the other side does not know it yet."""
    if t.get("flag") or t.get("flagged"):
        return False
    if t.get("handler") or COUNTERPARTY in (t["from"], t.get("to")):
        return True
    same = [x for x in terms if x is not t and (x.get("date") or "") <= (t.get("date") or "") and x["n"] != t["n"]
            and (x["n"] == t.get("accepts") or (amount(x.get("amount")) is not None and amount(x.get("amount")) == amount(t.get("amount"))))]
    counter = [x for x in same if COUNTERPARTY in (x["from"], x.get("to")) or x.get("payer") == COUNTERPARTY]
    if not counter:
        return False
    return not ({t["from"], t.get("to")} <= {"kunde", "versicherer"} and all(_offer_of_the_other_side(x) for x in counter))


def _build_checked(entries, graph=None):
    """The account of a live case, its consequential distinctions checked by code (C10): a combined ask split into its
    items (partial and full), each answer's parts typed (a refusal or a promise closes nothing) and matched by how much of
    the request they name, only rows asked by the answer's addressee unless it names the asking entry or row, a letter-
    level answer over several rows unspecified, a repeat only from a later day, a document read twice or a quoted dispatch
    counted once, values kept only where their quotes write them, an agreement only with both sides on it, a payment only
    as such and summed per payer, the other side's demand never owed to us."""
    entries = sorted([_stored_entry(e) for e in entries or () if e.get("n") is not None], key=_key)
    if not entries:
        return None
    record = (graph or {}).get("record") or {}
    kinds, phone_code = record.get("kinds") or {}, record.get("phone_code") or "2"
    entries, merged = _same_documents(entries, kinds, phone_code)
    entries = [_valued(e) for e in entries]
    by_n = {e["n"]: e for e in entries}
    requests, unspecified, refused = [], [], []
    for e in entries:
        i = 0
        for a in e.get("asks") or ():
            for what in items_of(a["what"]):
                asker, prior = a["asker"], None
                if a.get("repeats") in by_n:  # the reader names the entry it repeats
                    same = [r for r in requests if a["repeats"] in r["entries"] and r["of"] == a["of"]]
                    prior = _best(same, what)[2]
                if prior is None:  # by code: the same asker, the same party asked, the same thing (or the one open thing, in a reminder)
                    same = [r for r in requests if r["by"] == asker and r["of"] == a["of"] and r["answered"] is None]
                    found, _, row = _best(same, what)
                    if found >= 0.5 or (e.get("kind") == "mahnung" and len(same) == 1):
                        prior = row
                later = prior is not None and e.get("date") and prior["last"] and e["date"] > prior["last"]
                if prior is not None and not later and e.get("date") and prior["last"]:  # C10e: a repeat only from a later day
                    if content(what) != content(prior["what"]):
                        prior = None  # another thing asked the same day: its own row
                    else:
                        prior["citations"] = prior["citations"] + a["citations"]  # the same ask again that day: one row, no count
                        i += 1
                        continue
                if prior is not None:
                    if a.get("by"):
                        prior.update(due_n=e["n"], due_computed=bool(a.get("by_computed")))
                    prior.update(times=prior["times"] + (1 if later else 0), last=e.get("date") or prior["last"], due=a.get("by") or prior["due"],
                                 due_text=a.get("by_text") or prior.get("due_text"))
                    prior["entries"].append(e["n"])
                    prior["citations"] = prior["citations"] + a["citations"]
                    prior["warned"] += int(bool(a.get("warns")))
                    if prior["answered"] is not None and a.get("repeats") is not None:
                        prior["answered"] = None  # asked again after an answer: the answer did not settle it
                    i += 1
                    continue
                named = {k: a[k] for k in ("kind", "key", "ref") if a.get(k) is not None}  # a dispatch's ask (Slice B): what it asks
                requests.append({"id": f"r{e['n']}.{i}", "by": asker, "of": a["of"], "what": what, "first": e.get("date"), "last": e.get("date"),
                                 "due": a.get("by"), "times": 1, "warned": int(bool(a.get("warns"))), "entries": [e["n"]], "citations": list(a["citations"]),
                                 "answered": None, "phone": bool(e.get("phone")), "due_n": e["n"] if a.get("by") else None, "due_text": a.get("by_text"),
                                 "due_computed": bool(a.get("by_computed")), **({"third": True} if a.get("third") else {}),
                                 **({"by_check": True} if a.get("by_check") else {}), **({"ask": named} if named else {})})
                i += 1
        for j, x in enumerate(e.get("answers") or ()):
            open_ = [r for r in requests if r["of"] == e["from"] and r["answered"] is None and r["entries"][0] != e["n"]]
            if x.get("request"):  # the answer names the row it answers (C8)
                candidates, how = [r for r in open_ if r["id"] == x["request"]], "request"
            elif x.get("answers") in by_n:  # the entry it answers
                candidates, how = [r for r in open_ if x["answers"] in r["entries"]], "entry"
            else:  # C10d: only rows asked by the party the answer is addressed to
                candidates, how = [r for r in open_ if _side(r["by"]) == _side(e["to"])], "code"
            for part in x["parts"]:
                ranked = sorted(((score(part["what"], r["what"]), k, r) for k, r in enumerate(candidates) if r["answered"] is None), key=lambda s: (-s[0], s[1]))
                found, _, row = ranked[0] if ranked else (0.0, 0, None)
                named = how in ("request", "entry")
                if row is None or (not named and found < 0.5):
                    continue
                if e.get("flagged") or (how == "entry" and len(ranked) >= 2 and found == 0):  # «Antwort ohne Zuordnung – prüfen»
                    unspecified.append({"n": e["n"], "date": e.get("date"), "what": part["what"], "entry": x.get("answers"), "rows": [r["id"] for _, _, r in ranked],
                                        "citations": x["citations"]})
                    continue
                kind = part["type"]
                if kind == "refusal" and is_question(row):
                    kind = "answer"  # «nein» answers a question asked for information; it delivers nothing asked
                mark = {"n": e["n"], "date": e.get("date"), "what": part["what"], "citations": x["citations"]}
                if kind == "refusal":
                    row["refused"] = mark
                    refused.append({**mark, "request": row["id"]})
                elif kind == "promise":
                    row.update(promised={**mark, "i": None, "by": part.get("by"), "phone": bool(e.get("phone")), "answer": j,
                                         "handler": {"kind": e["handler"].get("kind")} if e.get("handler") else None})
                    if part.get("by"):
                        row.update(due=part["by"], due_n=e["n"], due_text=None, due_computed=False)
                elif found >= 0.5 or (named and len(ranked) == 1):  # a letter-level answer to a one-row entry: its evidence is checked (held)
                    row["answered"] = {**mark, "how": how if found < 0.5 or named else "code", "file": e.get("file"), "from": e["from"],
                                       **({"elsewhere": x["elsewhere"]} if x.get("elsewhere") else {}), "confirmed": found >= 0.5, "score": round(found, 2)}
                    row.pop("partial", None)
                elif found > 0:  # 0 < score < 0.5: part of what was asked; the rest stays open
                    rest = [w for w in re.findall(r"[A-Za-zÄÖÜäöüß]{3,}", row["what"]) if w.lower()[:6] in content(row["what"]) - content(part["what"])]
                    row["partial"] = {**mark, "rest": " ".join(dict.fromkeys(rest))}
        for k, x in enumerate(e.get("next") or ()):  # the party asked says by when it delivers: the request's date is that one, not asked again
            dated = []
            for what in (items_of(x.get("what"), questions=True) if x.get("by") else ()):  # «VN schickt Mietvertrag und Mängelrüge»: each item's row
                dated += [r for r in promised(requests, e, {**x, "what": what}) if r not in dated]
            if not dated and not x.get("by") and x.get("who"):  # a promise without a day: on the row it names, «zugesagt, ohne Datum»
                open_ = [r for r in requests if r["of"] == x["who"] and r["answered"] is None and r["entries"][0] != e["n"]]
                found, _, row = _best(open_, x.get("what"))
                if row is not None and score(x.get("what"), row["what"]) >= 0.5 and not row.get("promised"):
                    row["promised"] = {"n": e["n"], "i": k, "date": e.get("date"), "by": None, "phone": bool(e.get("phone")),
                                       "handler": {"kind": e["handler"].get("kind")} if e.get("handler") else None}
                    row["citations"] = row["citations"] + x["citations"]
            for r in dated:
                r.update(due=x["by"], due_n=e["n"], due_text=x.get("by_text"), due_computed=bool(x.get("by_computed")),
                         promised={"n": e["n"], "i": k, "date": e.get("date"), "by": x["by"], "phone": bool(e.get("phone")),
                                   "handler": {"kind": e["handler"].get("kind")} if e.get("handler") else None})
                r["citations"] = r["citations"] + x["citations"]
    _settle(requests, entries, by_n)  # the handler's settlements (apply_corrections)
    # terms offered and agreed, in time order; an acceptance without terms of its own accepts the latest terms of another party
    terms = []
    for e in entries:
        own = e.get("terms") or []
        if e.get("kind") == "annahme" and terms:
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
            terms.append({**t, "n": e["n"], "date": e.get("date"), "from": e["from"], "to": e["to"], "phone": bool(e.get("phone")), "kind": e.get("kind"),
                          "agreed": bool(t.get("agreed")) or e.get("kind") == "annahme", **({"flagged": True} if e.get("flagged") else {}),
                          **({"handler": {k: e["handler"].get(k) for k in ("by", "at", "kind")}} if e.get("handler") else {})})
    agreed = [t for t in terms if t["agreed"] and _agrees(t, terms)]
    consent = [t for t in terms if t["agreed"] and t not in agreed and not t.get("flag")]
    agreement = agreed[-1] if agreed else None
    paid = [{**p, "n": e["n"], "entry_date": e.get("date")} for e in entries for p in e.get("paid") or ()]
    payment, partly = None, None
    if agreement:
        since, want = agreement.get("date") or "", amount(agreement.get("amount"))
        payer = agreement.get("payer") if agreement.get("payer") not in (None, "andere") else None
        made = [p for p in paid if (p.get("date") or p.get("entry_date") or "") >= since and (payer is None or p.get("payer") == payer)]
        total = sum(amount(p.get("amount")) or 0 for p in made)
        if made and (want is None or total >= want - 0.005):
            payment = made[-1]
        elif made:
            partly = {"paid": total, "of": want, "payer": payer, "n": [p["n"] for p in made], "citations": [c for p in made for c in p["citations"][:1]]}
    owes = {p: [] for p in PARTIES}
    for r in requests:
        if r["answered"] is None:
            owes[r["of"]].append({"kind": "request", "request": r["id"], "what": r["what"], "since": r["first"], "times": r["times"],
                                  "due": r["due"], "by": r["by"], "of": r["of"], "warned": r["warned"], "citations": r["citations"],
                                  **({"promised": r["promised"]} if r.get("promised") else {}), **({"refused": r["refused"]} if r.get("refused") else {}),
                                  **({"partial": r["partial"]} if r.get("partial") else {}), **({"third": True} if r.get("third") else {})})
    if agreement and payment is None and agreement.get("payer") in owes:
        owes[agreement["payer"]].append({"kind": "payment", "what": agreement.get("what"), "amount": agreement.get("amount"),
                                         "due": agreement.get("by"), "citations": agreement["citations"], **({"partly": partly} if partly else {})})
    actions, announced = [], False
    for e in entries:
        for code in code_of(e, kinds, announced, phone_code):
            actions.append({"code": code, "date": e.get("date"), "n": e["n"]})
        if e.get("from") == INSURER and e.get("kind") == "abschlussankuendigung":
            announced = True
    contacts = [e for e in entries if e.get("date") and e["from"] != e["to"]]
    return {"entries": entries, "requests": requests, "terms": terms, "agreement": agreement, "superseded": [t for t in terms if t is not agreement],
            "paid": paid, "payment": payment, "owes": owes, "actions": actions, "last_contact": contacts[-1] if contacts else None,
            "checked": True, "merged": merged, "unspecified": unspecified, "refused": refused, "consent": consent, "partly_paid": partly}


def build(entries, graph=None, checked=True):
    """The account from the located entries: {entries, requests, terms, agreement, paid, owes, actions, last_contact}.
    None without entries. A request's id is stable, «r<n>.<i>»: the entry that first asks it and the ask's place among
    that entry's asks, so a later or back-dated entry never renumbers it. ``checked``: the consequential distinctions are
    checked by code (_build_checked: promise and delivery, partial and full, offer and agreement, the other side's demand
    and the customer's obligation, instruction and payment); False: the rules a frozen study copy was frozen with (ids by
    position in time order, «r1», «r2» …, and none of these checks)."""
    if checked:
        return _build_checked(entries, graph)
    entries = sorted([_stored_entry(e) for e in entries or () if e.get("n") is not None], key=_key)
    if not entries:
        return None
    record = (graph or {}).get("record") or {}
    kinds, phone_code = record.get("kinds") or {}, record.get("phone_code") or "2"
    by_n = {e["n"]: e for e in entries}
    requests = []
    for e in entries:
        for i, a in enumerate(e.get("asks") or ()):
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
            requests.append({"id": f"r{e['n']}.{i}" if checked else f"r{len(requests) + 1}", "by": e["from"], "of": a["of"], "what": a["what"],
                             "first": e.get("date"), "last": e.get("date"), "due": a.get("by"), "times": 1, "warned": int(bool(a.get("warns"))),
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
        for i, x in enumerate(e.get("next") or ()):  # the party asked says by when it delivers: the request's date is that one, not asked again
            for r in promised(requests, e, x):
                r.update(due=x["by"], due_n=e["n"], due_text=x.get("by_text"), due_computed=bool(x.get("by_computed")),
                         promised={"n": e["n"], "i": i, "date": e.get("date"), "by": x["by"], "phone": bool(e.get("phone")),
                                   "handler": {"kind": e["handler"].get("kind")} if e.get("handler") else None})
                r["citations"] = r["citations"] + x["citations"]
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
                          "agreed": bool(t.get("agreed")) or e.get("kind") == "annahme",
                          **({"handler": {k: e["handler"].get(k) for k in ("by", "at", "kind")}} if e.get("handler") else {})})
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
                                  "due": r["due"], "by": r["by"], "of": r["of"], "warned": r["warned"], "citations": r["citations"],
                                  **({"promised": r["promised"]} if r.get("promised") else {})})
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


def from_result(result, graph=None, edits=(), checked=True):
    """The account of a stored run, with the handler's entries in force (``edits``); None for a run made before the
    account: the handler's entries then wait for a full preparation, and nothing is invented. ``checked`` False: a frozen
    study copy's account, by the rules it was frozen with (build)."""
    if not kept(result):
        return None
    entries = with_handler(entries_of(result), edits)
    return build(apply_corrections(entries, edits) if checked else entries, graph, checked=checked)


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
            if acc.get("checked") and not r["due"]:  # C10f: only a request that set a date; a dateless question back (A4) never counts
                continue
            due = parse_date(r["due"]) if r["due"] and parse_date(r["due"]) >= last else last + timedelta(days=days)
            if look > due and not _after(acc, last, "kunde"):
                return True
        return False
    return None


def awaited(acc, party, look):
    """The latest date a party said it delivers by, for what it still owes, not yet past: {date, what, n}; None."""
    rows = [r for r in (acc or {}).get("requests") or () if r.get("promised") and r["answered"] is None and r["of"] == party
            and parse_date(r["due"]) and parse_date(r["due"]) >= look]
    if not rows and (acc or {}).get("checked"):  # C10b: a promised date passed with nothing come: «zugesagt bis …, nicht eingegangen»
        late = [r for r in acc["requests"] if r.get("promised") and (r["promised"].get("by") or None) and r["answered"] is None
                and r["of"] == party and parse_date(r["due"]) and parse_date(r["due"]) < look]
        if late:
            r = max(late, key=lambda r: r["due"])
            return {"date": r["due"], "what": r["what"], "n": r["promised"]["n"], "overdue": True,
                    "text": f"zugesagt bis {day(r['due'])}, nicht eingegangen: {r['what']}"}
    if not rows:
        return None
    r = max(rows, key=lambda r: r["due"])
    return {"date": r["due"], "what": r["what"], "n": r["promised"]["n"]}


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


def _chf(value):
    """3000.0 → «3'000», 85.4 → «85.40»."""
    whole, cents = divmod(round(float(value or 0) * 100), 100)
    return re.sub(r"(?<=\d)(?=(\d{3})+$)", "'", str(int(whole))) + (f".{int(cents):02d}" if cents else "")


def _terms_text(t):
    """«Gegenpartei zahlt CHF 3'000 (Entschädigung) bis 30.04.2025»: who pays what by when, as read."""
    what = t.get("amount") or t.get("what") or "Vereinbarung"
    if t.get("amount") and t.get("what") and not words(t["what"]) <= words(t["amount"]):
        what = f"{t['amount']} ({t['what']})"
    payer = PARTY_TITLES.get(t.get("payer")) if t.get("payer") not in (None, "andere") else None
    text = f"{payer} zahlt {what}" if payer and t.get("amount") else what
    return text + (f" bis {day(t['by'])}" if t.get("by") else "")


def _source(t):
    own = (t.get("handler") or {}).get("kind")  # the handler's own entry: as the handler named it
    return (FORM_KINDS.get(own) or ("Telefon" if t.get("phone") else "Schreiben")) + (f" vom {day(t['date'])}" if t.get("date") else "")


def _request_text(r, with_by=False):
    """One open request on one line, no brackets: «Belege der Reparaturkosten · seit 01.03.2025 · 3× verlangt von der
    Kanzlei · mit Androhung»; a customer's own question «… · Frage der Kundschaft vom 10.01.2025»."""
    first = r["since"] if "since" in r else r.get("first")
    if r.get("by") == "kunde" and r.get("of") in (INSURER, None):
        return f"{r['what']} · Frage der Kundschaft" + (f" vom {day(first)}" if first else "")
    asked = f"{r.get('times', 1)}× verlangt" + (f" von {WITH[r['by']]}" if with_by and r.get("by") else "")
    promise = r.get("promised")  # a date the party asked gave later («Unterlagen folgen bis …»)
    meta = [f"seit {day(first)}" if first else "", asked, "mit Androhung" if r.get("warned") else "",
            f"zugesagt bis {day(promise['by'])} ({_source(promise)})" if promise and day(promise.get("by")) else "",
            "zugesagt, ohne Datum" if promise and not promise.get("by") else "",  # C10b: a promise is not a delivery
            f"abgelehnt: {r['refused']['what']}" if r.get("refused") else "",
            f"teilweise: {r['partial']['what']} – offen: {r['partial']['rest']}" if r.get("partial") else "",
            FLAGS["third"] if r.get("third") else ""]
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
        partly = acc.get("partly_paid")  # C10i: payments of the payer summed, the rest still owed
        state = (f"bezahlt am {day(acc['payment'].get('date') or acc['payment'].get('entry_date'))}" if acc["payment"]
                 else f"teilweise bezahlt: CHF {_chf(partly['paid'])} von CHF {_chf(partly['of'])}" if partly and partly.get("of")
                 else "überfällig" if due and look > due else "offen")
        was = [t for t in acc["superseded"] if (t.get("date") or "") <= (a.get("date") or "") and amount(t.get("amount")) not in (None, amount(a.get("amount")))]
        before = f"; ersetzt {was[-1].get('amount')} ({_source(was[-1])})" if was else ""
        payer = f" von {WITH[a['payer']]}" if a.get("payer") not in (None, "andere") else ""
        short = f"{a.get('amount') or a.get('what') or 'Vereinbarung'}{payer}" + (f" bis {day(a['by'])}" if a.get("by") else "") + f" · {state}"
        lines.append({"id": "vereinbart", "label": "Vereinbart", "text": short, "detail": f"{_terms_text(a)} · {state} · {_source(a)}{before}",
                      "open": acc["payment"] is None, "citations": a["citations"][:2] + ([c for c in was[-1]["citations"][:1]] if was else []),
                      "entries": [a["n"]] + ([was[-1]["n"]] if was else []), **({"handler": a["handler"]} if a.get("handler") else {})})
    for t in acc.get("consent") or ():  # C10h: the customer's assent passed to us only: not yet an agreement
        lines.append({"id": "zustimmung", "label": "Zustimmung", "text": f"{FLAGS['consent']}: {_terms_text(t)} ({_source(t)})", "open": True,
                      "citations": t["citations"][:1], "entries": [t["n"]]})
    ledger = {r["id"]: r for r in acc["requests"]}
    claimed = [o for o in acc["owes"]["kunde"] if o["kind"] == "request" and (o["by"] == "gegenpartei" or o.get("third"))]
    for party in ("kunde", "gegenpartei", "kanzlei", "behoerde", "versicherer", "forderung"):
        if party == "forderung":  # what the other side demands of the customer: the dispute, never something owed to us
            rows = claimed
        else:
            rows = [o for o in acc["owes"][party] if o["kind"] == "request" and not (party == "kunde" and (o["by"] == "gegenpartei" or o.get("third")))]
        if not rows:
            continue
        shown = [{"text": _request_text(o, with_by=party != "forderung" and o["by"] != INSURER),
                  "citations": o["citations"][:1], "entries": list(ledger[o["request"]]["entries"]), "request": o["request"],
                  **({"handler": o["promised"]["handler"]} if (o.get("promised") or {}).get("handler") else {})} for o in rows[:SHOWN_PER_PARTY]]
        more = len(rows) - len(shown)
        label = "Offen bei uns" if party == INSURER else "Forderung der Gegenpartei" if party == "forderung" else f"Offen {AT[party]}"
        party = "kunde" if party == "forderung" else party
        lines.append({"id": "forderung_gegenpartei" if label.startswith("Forderung") else f"offen_{party}", "label": label, "party": party,
                      "rows": shown, "more": more,
                      "text": "; ".join(r["text"] for r in shown) + (f"; … {more} weitere" if more else ""), "open": True,
                      "citations": [c for r in shown for c in r["citations"]],
                      "entries": sorted({n for o in rows for n in ledger[o["request"]]["entries"]})})
    last = acc["last_contact"]
    if last:
        if (last.get("handler") or {}).get("kind") in FORM_KINDS:  # the handler's own entry, as the handler named it
            what = f"{FORM_KINDS[last['handler']['kind']]} mit {WITH[last['to']]}"
        elif last.get("phone"):
            what = f"Telefon mit {WITH[last['to'] if last['from'] == INSURER else last['from']]}"
        elif last["from"] == INSURER:
            what = f"{kinds_title(last.get('kind'), graph) or 'Schreiben'} an {TO[last['to']]}"
        else:
            what = f"{kinds_title(last.get('kind'), graph) or 'Schreiben'} von {WITH[last['from']]}"
        lines.append({"id": "kontakt", "label": "Letzter Kontakt", "text": f"{day(last['date'])} · {what}", "open": False,
                      "citations": last["citations"][:1], "entries": [last["n"]],
                      **({"handler": {k: last["handler"].get(k) for k in ("by", "at", "kind")}} if last.get("handler") else {})})
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
    # the number shown is the entry's place in time order: a reader's numbers, an update's and the handler's read as one list
    shown = {e["n"]: i for i, e in enumerate(acc["entries"], 1)}
    nr = lambda n: shown.get(n, n)
    out = []
    for e in acc["entries"]:
        notes, is_open, open_of = [], False, set()
        for r in acc["requests"]:
            if e["n"] not in r["entries"]:
                continue
            own = _best([a for a in e.get("asks") or ()], r["what"])[2] or {}
            by = _by(own) + _where(own)
            done = f" · beantwortet (Nr. {nr(r['answered']['n'])})" if r["answered"] and r["entries"][-1] == e["n"] else ""
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
                notes.append({"kind": "answered", "text": f"beantwortet: {r['what']}" + (f" (zu Nr. {nr(r['entries'][-1])})" if r["entries"] else "")
                              + _where(r["answered"]), "open": False})
                if r["answered"].get("unheld"):  # C10c: answered, but no file of the reply holds it
                    notes.append({"kind": "unheld", "text": r["answered"]["unheld"], "open": True})
            for key, kind, text in (("refused", "refused", lambda m: f"abgelehnt: {m['what']}"),
                                    ("partial", "partial", lambda m: f"teilweise: {m['what']} – offen: {m['rest']}")):
                if (r.get(key) or {}).get("n") == e["n"] and r["answered"] is None:  # C10a, C10b: the row stays open
                    notes.append({"kind": kind, "text": text(r[key]) + f" (zu Nr. {nr(r['entries'][0])})", "open": True})
        for u in acc.get("unspecified") or ():
            if u["n"] == e["n"]:
                notes.append({"kind": "unspecified", "text": f"{FLAGS['unspecified']}: {u['what']}", "open": True})
        if acc.get("checked"):  # what code found to check on this entry (a study copy shows none of it)
            flags = [FLAGS["entry_date"] if e.get("date_check") else "", FLAGS["sender"] if e.get("from_check") or e.get("to_check") else ""]
            flags += [f"{FLAGS['amount']}: {x['amount_check']}" for k in ("terms", "paid") for x in e.get(k) or () if x.get("amount_check")]
            flags += [f"zitiert in Nr. {', '.join(str(nr(n)) for n in e['quoted'])}" if e.get("quoted") else ""]
            notes += [{"kind": "check", "text": f, "open": False} for f in flags if f]
        for t in acc["terms"]:
            if t["n"] == e["n"] and any(t is c for c in acc.get("consent") or ()):  # C10h: assent passed to us only
                notes.append({"kind": "consent", "text": f"{FLAGS['consent']}: {_terms_text(t)}", "open": True})
                continue
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
            notes.append({"kind": "next", "text": f"nächster Schritt: {x['what']}" + (f" ({PARTY_TITLES[x['who']]})" if e.get("handler") and x.get("who") in PARTY_TITLES and x["who"] != e["to"] else "")
                          + (f" (bis {day(x['by'])})" if x.get("by") else f" ({x['by_text']})" if x.get("by_text") else "") + _where(x),
                          "open": False})
        for r in acc["requests"]:  # a date the party asked gave here for what is still open
            if (r.get("promised") or {}).get("n") == e["n"] and r["answered"] is None:
                when = f"zugesagt bis {day(r['due'])}" if acc.get("checked") is None or r["promised"].get("by") else "zugesagt, ohne Datum"
                notes.append({"kind": "promised", "text": f"{when}: {r['what']} (zu Nr. {nr(r['entries'][0])})", "open": True})
        own = e.get("handler")
        out.append({"n": e["n"], "number": nr(e["n"]), "date": e.get("date"), "from": e["from"], "to": e["to"], "from_title": PARTY_TITLES[e["from"]],
                    "to_title": PARTY_TITLES[e["to"]], "kind": e.get("kind"),
                    "kind_title": FORM_KINDS.get((own or {}).get("kind")) or (kinds.get(e.get("kind")) or {}).get("title") or e.get("kind"),
                    "phone": bool(e.get("phone")), "what": e.get("what"), "notes": notes, "open": is_open, "open_of": sorted(open_of),
                    "citations": e["citations"] + [c for k in ELEMENTS for el in e.get(k) or () for c in el["citations"]][:4],
                    # the handler's own entry: entered by a person, its source the handler, its form to change or remove it
                    **({"handler": {"by": own.get("by"), "at": own.get("at"), "kind": own.get("kind"), "party": own.get("party"),
                                    "name": own.get("name"), "said": e.get("said"), "form": own.get("form"), "source": HANDLER_SOURCE}} if own else {})})
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


OWED_TO_US = ("versicherer", "kanzlei")  # who may ask the customer for something the customer owes the insurer


def open_items(acc, party, askers=None):
    """What is asked of a party and not delivered, from the ledger: [{what, first, by, times, warned, request}] in the
    order asked, ``request`` the row's id. ``askers``: only what these parties asked (a letter to the customer takes what
    the insurer or the mandated firm asked, never a claim of the other side against the customer)."""
    return [{"what": r["what"], "first": r["first"], "by": r["by"], "times": r["times"], "warned": r["warned"], "request": r["id"]}
            for r in (acc or {}).get("requests") or () if r["of"] == party and r["answered"] is None and r["by"] != party
            and (askers is None or r["by"] in askers)]


def _head(title):
    """The first word that names a document need («Mietvertrag inkl. …» → «mietve»), as ``words`` cuts it."""
    return next((w.lower()[:6] for w in WORD.findall(str(title or "")) if w.lower() not in STOP), None)


def _alike(a, b):
    """Two words cut to six letters name the same thing («fotos» and «foto»)."""
    return len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a))


def answering_files(row, files, entries=None):
    """The files of the entry that answered a row: its own file, the files attached to it (``extraction.attached_to``),
    files of entries of the same day from the same sender, and the files its e-mail already held (``extraction.same_as``:
    an attachment skipped as a duplicate). File ids, its own first."""
    answer = (row or {}).get("answered") or {}
    by_id = {f["id"]: f for f in files or ()}
    own = answer.get("file") or next((c.get("file") for c in answer.get("citations") or () if c.get("file")), None)
    if own not in by_id:
        return []
    mail = by_id[own]
    ids = [own] + [f["id"] for f in by_id.values() if f["id"] != own and (f.get("extraction") or {}).get("attached_to") == mail.get("name")
                   and (not f.get("created_at") or not mail.get("created_at") or abs((_seconds(f["created_at"]) or 0) - (_seconds(mail["created_at"]) or 0)) <= 120)]
    if answer.get("date"):
        ids += [e["file"] for e in entries or () if e.get("file") in by_id and e.get("date") == answer["date"] and e.get("from") == answer.get("from")]
    ids += [i for i in (mail.get("extraction") or {}).get("same_as") or () if i in by_id]
    return list(dict.fromkeys(ids))


def _seconds(value):
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except ValueError:
        return None


# -- claims and their receipts (C10c): a shared word or amount is a candidate, never proof ---------------------------------
#
# A receipt delivers a claim line («Belege zu: Stromkosten für den Bautrockner») only when what the reading records about
# it agrees with the claim: the expense, the party, the period, the transaction, and the role of its amount (requested,
# promised, disputed, paid, refunded). The reading's own records serve where they exist (a claim's ``expense``, ``party``,
# ``period``, ``transaction``, ``role``; an entry's ``receipt`` record, Slice A); otherwise the reader's line on the
# document, its file's name and documents, and the values its located quotes write. Deterministic, no model call.

RECEIPT_ROLES = ("requested", "promised", "disputed", "paid", "refunded")
DOCUMENTING = {"requested", "paid"}  # billed to the customer or paid: the cost was incurred
ROLE_WORDS = (("refunded", re.compile(r"vergüt|zurück\s?erstatt|rückerstatt|\berstatte[tn]?\b|gutschrift|gutgeschrieben|zurückbezahlt|rückzahlung", re.I)),
              ("disputed", re.compile(r"bestreit|bestritten|beanstand|nicht einverstanden|strittig|einsprache", re.I)),
              ("promised", re.compile(r"nachreich|\bfolgt\b|\bfolgen\b|\bwerde\b|später|demnächst|sobald", re.I)),
              ("paid", re.compile(r"bezahlt|beglichen|überwiesen|quittung|kassenbon|zahlungsbestätigung|abgebucht|lastschrift|\bbar\b", re.I)),
              ("requested", re.compile(r"rechnung|abrechnung|zahlbar|fällig|\bbetrag\b|forderung|mahnung", re.I)))
ROLE_KINDS = {"kostenforderung": "requested", "zahlungsbestaetigung": "paid", "zahlung": "paid"}
ROLE_TEXT = {"requested": "verlangt", "promised": "angekündigt", "disputed": "bestritten", "paid": "bezahlt", "refunded": "erstattet"}
COST_WORDS = ("abrechnungen", "abrechnung", "rechnungen", "rechnung", "quittungen", "quittung", "belege", "beleg", "kosten", "gebühren",
              "gebühr", "betrag", "verbrauch", "auslagen", "spesen")
NOT_EXPENSE = set(COST_WORDS) | {"zusatz", "total", "chf", "franken", "mwst", "ersatz", "betreff", "zahlung", "nummer", "datum", "anbei",
                                 "stand", "summe", "pdf", "txt", "eml", "png", "jpg", "zähler", "monat", "monate", "tage", "seite"}
SAME_EXPENSE = (("energ", "strom"), ("elektri", "strom"), ("kwh", "strom"))  # one expense, other words: by its first letters
MONEY = re.compile(r"(?:CHF|Fr\.|SFr\.?|EUR)\s*(\d{1,3}(?:[’' ]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)|"
                   r"(\d{1,3}(?:[’' ]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)\s*(?:CHF|Franken|\.–|\.-)", re.I)
ROUGH = re.compile(r"\b(?:rund|ca\.?|circa|etwa|ungefähr|ungefaehr|knapp|gut)\b", re.I)


def expense_stems(text):
    """The words that name what a cost is for, each cut to its first letters: «Stromkosten für den Bautrockner» →
    {strom, bautro}, «Abrechnung Energieverbrauch» → {strom}; the words of billing (Kosten, Rechnung, Beleg …) left out."""
    out = set()
    for raw in re.findall(r"[A-Za-zÄÖÜäöüß]{3,}", str(text or "")):
        w = raw.lower()
        if w in STOP or w in FUNCTION_WORDS or w in NOT_EXPENSE:
            continue
        for part in COST_WORDS:
            if w.endswith(part) and len(w) - len(part) >= 3:
                w = w[:-len(part)]
                w = w[:-1] if w.endswith(("ungs", "heits", "keits", "ions", "tats")) else w
                break
        if w in NOT_EXPENSE or len(w) < 3:
            continue
        w = next((same for head, same in SAME_EXPENSE if w.startswith(head)), w)
        out.add(w[:6])
    return out


def _covered(stem, stems):
    return any(stem == t or (len(stem) >= 4 and len(t) >= 4 and (stem.startswith(t) or t.startswith(stem))) for t in stems)


def money(text):
    """The amounts a text writes as money («CHF 85.40», «Fr. 1'200.–», «85.– »); without a currency, every amount."""
    found = set()
    for m in MONEY.finditer(str(text or "")):
        try:
            found.add(float(re.sub(r"[’' ]", "", m.group(1) or m.group(2)).replace(",", ".")))
        except ValueError:
            continue
    return found or written_amounts(text)


def role_of(text, kind=None):
    """The role an amount has where it is written: refunded, disputed, promised, paid or requested (billed); None."""
    return next((role for role, pattern in ROLE_WORDS if pattern.search(str(text or ""))), None) or ROLE_KINDS.get(kind)


def _period(value):
    if isinstance(value, dict) and (value.get("from") or value.get("to")):
        return (_iso(value.get("from")) or _iso(value.get("to")), _iso(value.get("to")) or _iso(value.get("from")))
    return None


def claim_profile(claim):
    """What the reading records about a claim: its expense (``expense``, else its words), amount and whether it is
    rounded («rund CHF 85»), party, period, transaction and the role of its amount (a claim asks: requested)."""
    quote = " ".join(str(c.get("quote") or "") for c in claim.get("citations") or ())
    number = amount(claim.get("amount"))
    return {"stems": expense_stems(claim.get("expense") or claim.get("what")), "expense": claim.get("expense") or claim.get("what"),
            "amount": number, "rough": bool(ROUGH.search(f"{quote} {claim.get('amount') or ''}")), "party": claim.get("party"),
            "period": _period(claim.get("period")), "transaction": claim.get("transaction"), "role": claim.get("role") or "requested"}


def receipt_profile(entry, f=None):
    """What the reading records about a receipt in a file: the entry's own ``receipt`` record where the reader made one
    (Slice A), else the reader's line on the document (``what``), its file's name and documents, and the values its
    located quotes write (money, days, the role of the amount, from its words or its kind). None without anything."""
    entry = entry or {}
    rec = entry.get("receipt") if isinstance(entry.get("receipt"), dict) else {}
    quotes = " ".join([str(c.get("quote") or "") for c in entry.get("citations") or ()]
                      + [_quote(x) for k in ELEMENTS for x in entry.get(k) or ()] + ([_quote(rec)] if rec else []))
    titles = [str((f or {}).get("name") or "")] + [str(s.get("title") or "") for s in ((f or {}).get("extraction") or {}).get("segments") or ()
                                                   if not entry.get("page") or not s.get("first_page") or s["first_page"] <= entry["page"] <= (s.get("last_page") or s["first_page"])]
    described = rec.get("expense") or " ".join([str(entry.get("what") or "")] + titles)
    if not described.strip() and not quotes.strip():
        return None
    recorded = {amount(rec["amount"])} if rec.get("amount") and amount(rec.get("amount")) is not None else set()
    amounts = recorded or (money(quotes) | {amount(x.get("amount")) for k in ("paid", "terms") for x in entry.get(k) or ()
                                            if x.get("amount") and not x.get("amount_check")})
    days = sorted(written_dates(quotes))
    return {"stems": expense_stems(described), "expense": rec.get("expense") or str(entry.get("what") or "") or titles[0],
            "amounts": {a for a in amounts if a is not None}, "party": rec.get("party"), "payer": rec.get("payer"),
            "period": _period(rec.get("period")) or ((days[0], days[-1]) if days else None), "transaction": rec.get("transaction"),
            "role": rec.get("role") if rec.get("role") in RECEIPT_ROLES else role_of(quotes, entry.get("kind")) or ("paid" if entry.get("paid") else None),
            "to": entry.get("to"), "file": entry.get("file") or (f or {}).get("id"), "n": entry.get("n")}


def receipt_agrees(claim, receipt):
    """Whether a receipt documents a claim (C10c): {agrees, candidate, why}. A candidate shares an expense word or an
    amount with the claim; it agrees only when the claim's expense is named whole and nothing recorded contradicts it: the
    amount (within its rounding), the role of the receipt's amount (billed or paid, never refunded, disputed or only
    announced), the period, the party, the transaction, and its addressee (the customer's side)."""
    c, r = claim_profile(claim), receipt
    why, shared = [], {s for s in c["stems"] if _covered(s, r["stems"])}
    tolerance = (lambda a: max(1.0, 0.05 * a)) if c["rough"] else (lambda a: max(0.5, 0.01 * a))
    same_amount = c["amount"] is not None and any(abs(a - c["amount"]) <= tolerance(c["amount"]) for a in r["amounts"])
    candidate = bool(shared) or same_amount
    if not c["stems"] or shared != c["stems"]:
        why.append(f"andere Ausgabe: {_clip(r['expense'], 60)}" if not shared else
                   f"Ausgabe nur teilweise: {_clip(r['expense'], 60)}")
    if c["amount"] is not None and r["amounts"] and not same_amount:
        why.append(f"Betrag weicht ab: CHF {_chf(sorted(r['amounts'], key=lambda a: abs(a - c['amount']))[0])} statt CHF {_chf(c['amount'])}")
    if r["role"] and r["role"] not in DOCUMENTING:
        why.append(f"Betrag {ROLE_TEXT[r['role']]}, nicht belegt")
    if c["period"] and r["period"] and (r["period"][1] < c["period"][0] or c["period"][1] < r["period"][0]):
        why.append(f"anderer Zeitraum: {day(r['period'][0])} bis {day(r['period'][1])}")
    if c["party"] and r["party"] and not (expense_stems(c["party"]) & expense_stems(r["party"])):
        why.append(f"andere Partei: {_clip(r['party'], 40)}")
    if c["transaction"] and r["transaction"] and re.sub(r"\W", "", str(c["transaction"])).lower() != re.sub(r"\W", "", str(r["transaction"])).lower():
        why.append(f"andere Nummer: {_clip(r['transaction'], 30)}")
    payer = r["payer"] if r.get("payer") in PARTIES else r.get("to") if r.get("to") in PARTIES else None  # billed to whom (a party)
    if payer and payer not in CUSTOMER_SIDE:
        why.append(f"an {TO[payer]} gerichtet")
    return {"agrees": candidate and not why, "candidate": candidate, "why": why}


def claim_of(row, claims):
    """The claim a row asks the receipts of: the one its ask names (a dispatch's ask «claim» with its index, Slice B), else
    the claim whose expense the row's words name whole («Belege zu: Stromkosten für den Bautrockner»). (index, claim) or
    None."""
    claims = list(claims or ())
    ask = row.get("ask") or {}
    ref = row.get("claim", ask.get("ref") if ask.get("kind") == "claim" else None)
    if isinstance(ref, int) and 0 <= ref < len(claims):
        return ref, claims[ref]
    asked = expense_stems(re.sub(r"^\s*(?:Belege|Quittungen|Rechnungen|Nachweise?)\s+(?:zu|für|von|der|des)\s*:?\s*", "", str(row.get("what") or ""), flags=re.I))
    best = [(i, c) for i, c in enumerate(claims) if claim_profile(c)["stems"] and claim_profile(c)["stems"] <= {s[:6] for s in asked}]
    return best[0] if best else None


def receipts_in(file_ids, files, entries=None):
    """The receipts the reading recorded in these files: one per entry of the file (a dossier holds several), else one
    for the file itself (its name and documents)."""
    by_id = {f["id"]: f for f in files or ()}
    out = []
    for fid in file_ids:
        mine = [e for e in entries or () if e.get("file") == fid and not e.get("handler") and not e.get("dispatch")]
        for e in mine or [{"file": fid}]:
            profile = receipt_profile(e, by_id.get(fid))
            if profile:
                out.append(profile)
    return out


def documented(claim, files, entries=None, file_ids=None, why=None):
    """A claim's receipt among the case's files (or ``file_ids``): {file, how: «receipt», n, basis} for the first receipt
    whose recorded details agree with the claim (receipt_agrees), else None; ``why`` collects each candidate set aside
    with its reasons ([{file, n, expense, why}]). For Slice A's residual and Slice B's fulfilment alike."""
    ids = list(file_ids) if file_ids is not None else [f["id"] for f in files or ()]
    for r in receipts_in(ids, files, entries):
        check = receipt_agrees(claim, r)
        if check["agrees"]:
            return {"file": r["file"], "how": "receipt", "n": r.get("n"),
                    "basis": {"expense": r["expense"], "amounts": sorted(r["amounts"]), "role": r["role"], "period": r["period"]}}
        if check["candidate"] and why is not None:
            why.append({"file": r["file"], "n": r.get("n"), "expense": r["expense"], "why": check["why"]})
    return None


def held(row, files, findings=None, claims=None, need=None, entries=None, why=None):
    """C10c: the file that holds what a row of the account asked (a document need or a claim line): {file, how}, or None.
    The files looked in are those of the entry that answered the row (answering_files); a row without an answer (a
    dispatch's ask, Slice B) is looked for in the files given. A claim line is held only by a receipt whose recorded
    details agree with the claim (documented: a shared word or amount is a candidate, never proof; ``why`` collects the
    candidates set aside). A file holds a document need when a document of it (its title or kind) or its name names the
    need's first word («segment», «name»), or an accepted finding of the document finder for that need cites it
    («finding»). ``need``: the process's document need the row asks (else the row's own ``need`` and ``title``, else its
    words). What the answer says alone never delivers. Dispatch rows (Slice B) are rows like any other."""
    files = list(files or ())
    ids = answering_files(row, files, entries) if (row or {}).get("answered") else [f["id"] for f in files]
    if not ids:
        return None
    by_id = {f["id"]: f for f in files}
    claimed = claim_of(row, claims) if claims else None
    if claimed is not None:  # a claim line: a receipt that agrees with the claim, nothing less
        return documented(claimed[1], files, entries, ids, why)
    need = need or ({"id": row.get("need"), "title": row.get("title")} if row.get("need") else None)
    title = (need or {}).get("title") or row.get("what")
    head = _head(re.sub(r"^\s*(?:Belege|Kopie|Kopien)\s+(?:zu|von|der|des)\s*:?\s*", "", str(title or ""), flags=re.I)) or _head(title)
    found = findings.values() if isinstance(findings, dict) else findings or ()
    for fid in ids:
        f = by_id[fid]
        named = [f.get("name")] + [x for s in (f.get("extraction") or {}).get("segments") or () for x in (s.get("title"), s.get("kind"))]
        if head and any(_alike(head, w) for text in named for w in words(text)):
            return {"file": fid, "how": "name" if any(_alike(head, w) for w in words(f.get("name"))) else "segment"}
        for row_found in found:
            if (need and need.get("id") and row_found.get("document") != need.get("id")) or row_found.get("verdict") not in ("accepted", None) \
                    or row_found.get("status") not in ("present", None) or row_found.get("account"):
                continue
            if fid in (row_found.get("files") or []) or any(c.get("file") == fid for c in row_found.get("citations") or ()):
                return {"file": fid, "how": "finding"}
    return None


def delivered(acc, needs, files=None, findings=None, claims=None):
    """The document needs the account shows delivered: a request of the insurer or the mandated firm to the customer,
    answered by an entry whose words name the need (its first word), with that answer's quote. {need id: finding}, in the
    shape of the document finder's accepted findings; an open-ended need («Sämtliche …») is never settled this way. A
    checked account (C10c) delivers a need only when a file of the answering entry holds it (held): otherwise the need
    stays missing, and the row says «laut Antwort vom … beigelegt, nicht in der Akte» (``answered.unheld``); a claim line
    answered is marked held by its receipt, or not held with the candidates set aside and why."""
    if (acc or {}).get("checked"):
        return _delivered_held(acc, needs, files or (), findings, claims)
    out = {}
    for r in (acc or {}).get("requests") or ():
        if r["answered"] is None or r["of"] != "kunde" or r["by"] not in OWED_TO_US:
            continue
        said = words(f"{r['answered'].get('what') or ''} {r['what']}") if r["answered"].get("confirmed") else words(r["answered"].get("what"))
        for d in needs or ():
            head = _head(d.get("title"))
            if not head or d["id"] in out or re.match(r"\s*(sämtlich|alle|bisherig)", str(d.get("title") or ""), re.I) or head not in said:
                continue
            cites = list(r["answered"].get("citations") or [])[:1]
            out[d["id"]] = {"document": d["id"], "status": "present", "verdict": "accepted", "files": [c.get("file") for c in cites if c.get("file")],
                            "citations": cites, "note": f"laut Verlauf zugestellt am {day(r['answered'].get('date')) or 'ohne Datum'}", "account": True}
    return out


def _delivered_held(acc, needs, files, findings, claims):
    out = {}
    for r in acc["requests"]:
        if r["answered"] is None or r["of"] != "kunde" or r["by"] not in OWED_TO_US or r["answered"].get("settled"):
            continue
        sent = f"laut Antwort vom {day(r['answered'].get('date')) or 'ohne Datum'} beigelegt, nicht in der Akte"
        if claims and claim_of(r, claims) is not None:  # a claim line: its receipt, checked against the claim
            aside = []
            got = held(r, files, findings, claims, entries=acc["entries"], why=aside)
            if got:
                r["answered"]["held"] = got
            else:
                r["answered"]["unheld"] = f"{sent}: {r['what']}"
                if aside:
                    r["answered"]["aside"] = aside
            continue
        said = words(f"{r['answered'].get('what') or ''} {r['what']}")
        for d in needs or ():
            head = _head(d.get("title"))
            if not head or d["id"] in out or re.match(r"\s*(sämtlich|alle|bisherig)", str(d.get("title") or ""), re.I) or head not in said:
                continue
            got = held(r, files, findings, None, need=d, entries=acc["entries"])
            if got is None:  # a word in the answer alone never delivers: the need stays missing
                r["answered"]["unheld"] = f"{sent}: {d.get('title')}"
                continue
            r["answered"]["held"] = got
            cites = list(r["answered"].get("citations") or [])[:1]
            out[d["id"]] = {"document": d["id"], "status": "present", "verdict": "accepted", "files": [got["file"]], "citations": cites,
                            "note": f"laut Verlauf zugestellt am {day(r['answered'].get('date')) or 'ohne Datum'}", "account": True, "held": got}
    return out


SETTLE = {"erledigt": "erledigt", "nicht_mehr_noetig": "nicht mehr nötig", "beantwortet": "beantwortet"}


def apply_corrections(entries, edits):
    """The handler's settlements of open requests in force (edit op «settle_request» {request: «r<n>.<i>», how: erledigt |
    nicht_mehr_noetig | beantwortet, entry?}), carried by the entry that first asked the row, for build to apply: the row
    is closed by the handler («erledigt», «nicht mehr nötig», «beantwortet durch Nr. n»), unless it is asked again after
    the settlement. Undone with the edit, like every correction."""
    settled = {}
    for e in edits or ():
        if e.get("op") != "settle_request" or e.get("status", "active") != "active":
            continue
        args = e.get("args") or {}
        m = re.fullmatch(r"r(\d+)\.(\d+)", str(args.get("request") or ""))
        if not m or args.get("how") not in SETTLE:
            continue
        settled.setdefault(int(m.group(1)), []).append({"request": args["request"], "how": args["how"], "entry": args.get("entry"),
                                                        "by": e.get("by"), "at": e.get("at"), "edit": e.get("id")})
    return [{**x, "settled": settled[x["n"]]} if x.get("n") in settled else x for x in entries or ()]


def _settle(requests, entries, by_n):
    """Apply the handler's settlements (apply_corrections) to the rows they name, when the row is still open and was not
    asked again after the settlement's day."""
    rows = {r["id"]: r for r in requests}
    for e in entries:
        for s in e.get("settled") or ():
            r = rows.get(s["request"])
            if r is None or r["answered"] is not None or (r.get("last") and str(s.get("at") or "")[:10] < r["last"]):
                continue
            answer = by_n.get(s.get("entry")) if s["how"] == "beantwortet" else None
            r["answered"] = {"n": answer["n"] if answer else None, "date": (answer or {}).get("date") or str(s.get("at") or "")[:10] or None,
                             "how": s["how"], "what": SETTLE[s["how"]], "citations": [], "confirmed": False, "settled": True,
                             "handler": {"by": s.get("by"), "at": s.get("at"), "edit": s.get("edit")}}


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
                    "text": text, "source": _source({"phone": e.get("phone"), "date": e.get("date"), "handler": e.get("handler")}),
                    "citations": citations[:1]})

    promises = {}  # what the party asked said it delivers by a date: one line per date it gave, set by that party
    for r in acc["requests"]:
        if r["answered"] is None and (r["due"] or r.get("due_text")):  # a date the file sets in words no rule reads: to check
            n = r.get("due_n") or r["entries"][-1]
            if r.get("promised"):
                promises.setdefault((n, r["due"], r["of"]), []).append(r)
                continue
            add(f"konto-{r['id']}", r["due"], r["what"], r["by"], r["of"], n, r["citations"][-1:], r.get("due_computed"), r.get("due_text"))
    for (n, due, of), rs in promises.items():
        add(f"konto-{rs[0]['id']}", due, ", ".join(r["what"] for r in rs) + " (zugesagt)", of, of, n, rs[0]["citations"][-1:],
            rs[0].get("due_computed"), rs[0].get("due_text"))
    became = {(r["promised"]["n"], r["promised"].get("i")) for rs in promises.values() for r in rs}
    later_terms = lambda t: any((x.get("date") or "") > (t.get("date") or "") for x in acc["terms"] if x is not t)
    for t in acc["terms"]:
        if not t.get("by") and not t.get("by_text"):
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
            if (e["n"], i) in became:  # the step is the date of the requests it answers for, said once
                continue
            if (x.get("by") or x.get("by_text")) and not (e.get("date") and _after(acc, parse_date(e["date"]), x.get("who"))):
                add(f"konto-x{e['n']}-{i}", x["by"], x["what"], e["from"], x.get("who") or "andere", e["n"], x["citations"],
                    x.get("by_computed"), x.get("by_text"))
    return sorted(out, key=lambda x: x["date"] or "9999")


def note(acc, look, graph=None):
    """The account in the file note: one sentence per «Stand» line."""
    return " ".join(f"{line['label']}: {line.get('detail') or line['text']}." for line in stand(acc, look, graph))
