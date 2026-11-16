"""What came in and is still unanswered: an overlay on the backbone's stages.

The stages advance on facts and the clock. A case that a law firm handles under a mandate moves by what comes in: a
cost claim to check and pay, a report, an offer of the other side, a payment, or the firm's report that the customer
does not cooperate. Each such kind is listed in the backbone (``incoming``) with the facts the reader establishes, one
item each (who sent what when, from one document, and whether the file shows it answered): the latest of the kind
(``fact``) and at most two before it (``earlier``). Most files have none, and then nothing is recorded.

Each item is its own entry. It is open until the file shows it answered, the handler marks it done (``incoming_done``:
items up to that date), or the case's history shows an action of a kind that answers it dated after it; each such
action answers one item, the oldest before it. An item read without a date of its own takes the date of the document
its quote is in (``document_dates``). An open item outranks the stage's own action and the clock, the oldest of the
most urgent kind first; the stage itself does not move, except that an open cost claim keeps the case from closing
(the derived fact ``kosten_offen``).

An item calls for an action only when it reached the case after the insurer's last own step, or, while the insurer has
taken no step yet, after the case was reported (``reference``; with the running account: an item addressed to the
insurer, or one the customer sent in after the report). An item that lies before that point is a fact of the case: it
is shown with the case and can feed a key point or the assessment, but it never replaces the stage's own action; when
its order cannot be established it is shown with «Zeitpunkt prüfen» and calls for nothing (``timing``). At the stages the
backbone names (``incoming_lead``: intake, clarifying, assessing), the stage's own action leads while it is due, and an
open item that calls for an action follows it («danach»). Model-free.
"""
import re

from .clock import parse_date
from .workflows import CatalogueError, done_actions

PARTIES = {"kanzlei", "gericht", "gegenpartei", "kunde"}
MAX_ITEMS = 3  # items read per kind: the latest and at most two before it
NONE = {"keine", "keiner", "keines", "none", "nein", "-", "—"}


def validate(backbone):
    """Fail closed on an incoming kind the backbone cannot carry."""
    facts = {f["id"]: f for f in backbone["facts"]}
    forms, seen, ranks, read = backbone["forms"], set(), set(), set()
    done = backbone.get("incoming_done")
    if backbone.get("incoming") and (facts.get(done) or {}).get("type") != "date":
        raise CatalogueError("backbone: incoming_done must name a date fact the handler sets")
    lead = (backbone.get("incoming_lead") or {}).get("stages", [])
    if not isinstance(lead, list) or set(lead) - {s["id"] for s in backbone.get("steps", [])}:
        raise CatalogueError("backbone: incoming_lead.stages must name stages of the backbone")
    for kind in backbone.get("incoming", []):
        where = f"backbone: incoming kind {kind.get('id')!r}"
        for field in ("id", "fact", "title", "what", "from", "priority", "action", "answered_by", "note", "source_refs"):
            if kind.get(field) in (None, "", []):
                raise CatalogueError(f"{where} needs {field}")
        if kind["id"] in seen or kind["priority"] in ranks:
            raise CatalogueError(f"{where}: its id and its priority must be its own")
        seen.add(kind["id"])
        ranks.add(kind["priority"])
        if len(slots(kind)) > MAX_ITEMS or any(f in read for f in slots(kind)):
            raise CatalogueError(f"{where}: at most {MAX_ITEMS} facts per kind, none shared with another kind")
        for fact in slots(kind):
            if (facts.get(fact) or {}).get("type") != "text" or facts[fact].get("handler_only") or facts[fact].get("derived"):
                raise CatalogueError(f"{where}: its facts must be text facts the reader establishes")
            read.add(fact)
        if not set(kind["from"]) <= PARTIES or not isinstance(kind.get("handler_decision"), bool):
            raise CatalogueError(f"{where}: from must name {sorted(PARTIES)} and handler_decision must be true or false")
        actions = [kind["action"]]
        decision = kind.get("decision")
        if decision:
            if not (facts.get(decision.get("fact")) or {}).get("handler_only") or not decision.get("yes") or not decision.get("no"):
                raise CatalogueError(f"{where}: a decision names a handler's fact and what follows on yes and on no")
            actions += [decision["yes"], decision["no"]]
        for action in actions:
            if not action.get("kind") or not action.get("title") or action.get("form") not in forms:
                raise CatalogueError(f"{where}: each action needs a kind, a title and a form of the backbone")
            answered = action.get("answered_by", kind["answered_by"])
            if answered != "any" and not (isinstance(answered, list) and answered and all(str(c).isdigit() for c in answered)):
                raise CatalogueError(f"{where}: answered_by is \"any\" or a list of action codes")
            # its own action must answer it, or the item could never close: a dead end
            if answered != "any" and not (re.fullmatch(r"A(\d{1,2})", action["kind"]) and action["kind"][1:] in answered):
                raise CatalogueError(f"{where}: the action {action['kind']} does not answer the item it is prepared for (a dead end)")
    return backbone


def _value(facts, fact):
    value = facts.get(fact)
    if value is None or value is False or str(value).strip().lower() in NONE | {""}:
        return None
    return str(value).strip()


ANSWERED = re.compile(r"\b(?:beglichen|bezahlt|beantwortet|erledigt)\s+(?:am\s+)?(\d{4}-\d{2}-\d{2})", re.I)


DUE = re.compile(r"(?:\bbis|\bab|spätestens|frist|gültig|einlösbar|fällig|zahlbar|innert)\b[^,;]{0,12}$", re.I)
DAY = re.compile(r"\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{4}")


def read_item(value):
    """(its own date, the date the file shows it answered): the item's date is the first date of the reading that is not
    the answered mark ("…; beglichen 2024-05-20") and not a date it names as due or valid until ("einlösbar bis
    2027-09-30", "zahlbar bis …"); the first date when every date is such. Either is None when the reading does not state it."""
    answered = ANSWERED.search(value)
    rest = ANSWERED.sub(" ", value)
    own = next((parse_date(m.group(0)) for m in DAY.finditer(rest) if not DUE.search(rest[:m.start()])), None) or parse_date(rest)
    return own, parse_date(answered.group(1)) if answered else None


def slots(kind):
    """The facts one kind is read into: the latest item first, then the earlier ones (at most MAX_ITEMS)."""
    return [kind["fact"], *kind.get("earlier", [])]


def document_dates(workflow, rows, files):
    """For each incoming fact read without a date of its own: the date of the document its first quote is in.

    The quote's page names the document (a segment of the file); its own date is used. A document without a date is
    bounded by the dated documents on either side of it in the file: the later of the two is a day the item came in by
    (whatever order the file runs in), so an action after it answers it, never earlier. A file of one document that was
    added to a live case (no cut) came in by the day it was added. Otherwise nothing: the item stays open until the
    handler marks it done. {fact: "YYYY-MM-DD"}."""
    wanted = {f for kind in workflow.get("incoming") or () for f in slots(kind)}
    by_id = {f.get("id"): f for f in files or () if f.get("id")}
    out = {}
    for row in rows or ():
        if row.get("fact") not in wanted or row.get("status") != "established" or not row.get("citations"):
            continue
        if read_item(str(row.get("value") or ""))[0]:
            continue
        cite = row["citations"][0]
        f = by_id.get(cite.get("file")) or {}
        extraction = f.get("extraction") or {}
        segments = extraction.get("segments") or []
        page = cite.get("page")
        day = None
        if segments and page is not None:
            at = next((i for i, s in enumerate(segments) if (s.get("first_page") or 0) <= page <= (s.get("last_page") or s.get("first_page") or 0)), None)
            if at is not None:
                day = parse_date(segments[at].get("date"))
                if day is None:
                    before = next((d for s in reversed(segments[:at]) if (d := parse_date(s.get("date")))), None)
                    after = next((d for s in segments[at + 1:] if (d := parse_date(s.get("date")))), None)
                    day = max(before, after) if before and after else None
        elif not segments and "cut_of" not in extraction:
            day = parse_date(str(f.get("created_at") or "")[:10])
        if day:
            out[row["fact"]] = day.isoformat()
    return out


INSURER, CUSTOMER = "versicherer", "kunde"
ACCOUNT_PARTY = {"gericht": "behoerde"}  # the incoming kinds' senders as the running account names them


def reference(facts, ledger=None, files=None, created=None):
    """The point an incoming item must come after to call for an action: {date, kind, text}, or None when the case gives
    none. The insurer's last own step (its dated history, the running account's actions included: kind «step»); while it
    has taken none, the day the case was reported (kind «report»): the account's report entry, else the customer's first
    entry to the insurer, else the day the case came in as the product knows it (cover.report_date)."""
    steps = sorted((d, code) for code, days in done_actions(facts or {}).items() for x in days if (d := parse_date(x)))
    if steps:
        day, code = steps[-1]
        return {"date": day, "kind": "step", "text": f"vor dem letzten Schritt von Protekta, A{code} vom {day.strftime('%d.%m.%Y')}"}
    entries = (ledger or {}).get("entries") or []
    reported = [d for e in entries if e.get("kind") == "meldung" and (d := parse_date(e.get("date")))] or \
        [d for e in entries if e.get("from") == CUSTOMER and e.get("to") == INSURER and (d := parse_date(e.get("date")))]
    if reported:
        day = min(reported)
    else:
        from .cover import report_date
        day = report_date(files, created)[0]
    return {"date": day, "kind": "report", "text": f"vor der Meldung des Falls am {day.strftime('%d.%m.%Y')}"} if day else None


def timing(row, ref, ledger=None):
    """Whether an item calls for an action («call»), is a fact of the case («fact»: it lies before the reference point), or
    its order cannot be established («unknown»: no date, no reference point, the same day, or, before any step of the
    insurer, an item the account shows addressed to someone else that the customer did not send in after it)."""
    day = parse_date(row["date"]) if row.get("date") else None
    if day is None or ref is None or day == ref["date"]:
        return "unknown"
    if day < ref["date"]:
        return "fact"
    entries = (ledger or {}).get("entries") or []
    if ref["kind"] == "report" and entries:
        senders = {ACCOUNT_PARTY.get(p, p) for p in row["kind"]["from"]}
        entry = next((e for e in entries if e.get("date") == row["date"] and e.get("from") in senders), None)
        sent_in = any(e.get("from") == CUSTOMER and e.get("to") == INSURER and (d := parse_date(e.get("date"))) and d >= day for e in entries)
        if entry and entry.get("to") != INSURER and not sent_in:
            return "unknown"
    return "call"


def items(workflow, facts, dated=None, order=None):
    """Every incoming item the case's facts record, each its own entry: {kind, fact, value, date, dated_by, open,
    answered, action, decided}, in priority order and, within a kind, oldest first.

    An item is answered by the file when its reading says so («beglichen 2024-05-20»), by the handler's mark
    (``incoming_done``), or by one action of the history of a kind that answers it, dated after it. Each such action
    answers one item only, the oldest open one before it, so a single payment does not settle two claims; a kind
    answered by "any" action (a report) uses none up. ``dated``: the document dates of items read without their own
    (``document_dates``). ``order``: {ref, ledger} (``reference``): each item's ``timing``; without it every item calls
    for its action, as before the rule. An item before the reference point still calls for its action when a later step
    of the insurer answered another item of its kind and so left this one over."""
    done = done_actions(facts)
    dated = dated or {}
    marked = parse_date(facts.get(workflow.get("incoming_done") or ""))
    rows = []
    for kind in sorted(workflow.get("incoming") or (), key=lambda k: k["priority"]):
        for fact in slots(kind):
            value = _value(facts, fact)
            if value is None:
                continue
            own, answered_on = read_item(value)
            day = own or parse_date(dated.get(fact))
            action, decided = kind["action"], None
            if kind.get("decision"):
                decided = facts.get(kind["decision"]["fact"])
                if decided is not None:
                    action = kind["decision"]["yes" if decided is True else "no"]
            by_hand = marked is not None and (day is None or day <= marked)
            rows.append({"kind": kind, "fact": fact, "value": value, "date": day.isoformat() if day else None,
                         "dated_by": "item" if own else "document" if day else None,
                         "answered": "file" if answered_on else "handler" if by_hand else None, "action": action, "decided": decided,
                         "answered_by": action.get("answered_by", kind["answered_by"])})
    # the history's answering actions, each used once, oldest item first
    history = sorted((d, code) for code, days in done.items() for x in days if (d := parse_date(x)))
    unused = list(history)
    for row in sorted(rows, key=lambda r: (r["date"] or "9999", r["kind"]["priority"])):
        codes, day = row["answered_by"], parse_date(row["date"]) if row["date"] else None
        if codes == "any":
            if row["answered"] is None and day and any(d > day for d, _ in history):
                row["answered"] = "history"
            continue
        if row["answered"] == "file":  # the file's own record of it: the action of that day is this item's
            hit = next((x for x in unused if x[1] in codes and x[0] == parse_date(ANSWERED.search(row["value"]).group(1))), None)
        elif row["answered"] is None and day:
            hit = next((x for x in unused if x[1] in codes and x[0] > day), None)
            if hit:
                row["answered"] = "history"
        else:
            hit = None
        if hit:
            unused.remove(hit)
            row["answered_on"] = hit[0]
    for row in rows:
        row["open"] = row["answered"] is None
        row["timing"] = timing(row, order.get("ref"), order.get("ledger")) if order is not None else "call"
        day = parse_date(row["date"]) if row["date"] else None
        if row["open"] and row["timing"] == "fact" and any(o is not row and o["kind"] is row["kind"] and o.get("answered_on") and o["answered_on"] > day for o in rows):
            # a later step of the insurer that answered another item of this kind (a payment of the other claim) did not deal
            # with this one: it is left over and still calls for its action
            row["timing"] = "call"
        if row["open"] and row["timing"] != "call" and day and (order or {}).get("customer_steps") and row["kind"]["id"] == "angebot":
            # an offer of the other side is not dealt with by talking to the customer about it: while every step of the
            # insurer since it came went to the customer (or was a file note), the offer still waits for its answer
            since = [e for e in (order.get("ledger") or {}).get("entries") or () if e.get("from") == INSURER and (d := parse_date(e.get("date"))) and d >= day]
            if since and all(e.get("to") in (CUSTOMER, INSURER) for e in since):
                row["timing"] = "call"
    return sorted(rows, key=lambda r: (r["kind"]["priority"], r["date"] is None, r["date"] or ""))


def pending(workflow, facts, dated=None, order=None):
    """The open items that call for an action, the first to act on first: by the kind's priority, then the oldest."""
    return [r for r in items(workflow, facts, dated, order) if r["open"] and r["timing"] == "call"]


def case_facts(workflow, facts, dated=None, order=None):
    """The open items that are facts of the case, not actions: those before the reference point and those whose order
    cannot be established, each once."""
    return [r for r in items(workflow, facts, dated, order) if r["open"] and r["timing"] != "call"]


def fact_line(row, ref=None):
    """An item that is a fact of the case, as «Der Fall» shows it: {label, text, open}; open (to check) when its order
    cannot be established."""
    day = parse_date(row["date"]) if row["date"] else None
    when = f"vom {day.strftime('%d.%m.%Y')} " if day else ""
    value = shown(row["value"], day if row.get("dated_by") == "item" else None)
    where = ref["text"] if row["timing"] == "fact" and ref else "Zeitpunkt prüfen"
    return {"label": row["kind"]["title"], "text": f"{when}liegt vor – {value} ({where})", "open": row["timing"] == "unknown"}


def assessment_line(row):
    """The item in the assessment's «In Ihrem Fall»: «Angebot der Gegenpartei vom 23.09.2026 liegt vor: …»."""
    day = parse_date(row["date"]) if row.get("date") else None
    value = shown(row["value"], day if row.get("dated_by") == "item" else None)
    return f"{row['kind']['title']}" + (f" vom {day.strftime('%d.%m.%Y')}" if day else "") + f" liegt vor: {value}."


def cost_open(workflow, facts, dated=None):
    """Whether an incoming item that keeps the case from closing (a cost claim) is still open."""
    return any(r["kind"].get("blocks_closing") for r in pending(workflow, facts, dated))


def shown(value, day=None):
    """What the reader read, as a handler reads it: its own date, already named in the line, left out; other dates as
    dd.mm.yyyy; at most 160 characters."""
    if day:
        value = re.sub(rf",?\s*(?:vom|am|datiert)?\s*{day.isoformat()}\b", "", value)
    value = re.sub(r"\b(\d{4})-(\d{2})-(\d{2})\b", lambda m: f"{m[3]}.{m[2]}.{m[1]}", value)
    value = re.sub(r"\s{2,}", " ", value).strip(" ,;")
    return value if len(value) <= 160 else value[:157].rstrip() + " …"


def reason(row):
    """The reason line: what came in, when, and that it is still open, with what the reader read."""
    day = parse_date(row["date"]) if row["date"] else None
    when = (f" vom {day.strftime('%d.%m.%Y')}" + (" (Datum des Schreibens in der Akte)" if row.get("dated_by") == "document" else "")) if day else ""
    value = shown(row["value"], day if row.get("dated_by") == "item" else None)
    if row["decided"] is False:
        return f"{row['kind']['title']}{when}; Leistungen nicht eingestellt: weiteres Vorgehen offen – {value}"
    return f"{row['kind']['title']}{when} eingegangen, noch offen – {value}"
