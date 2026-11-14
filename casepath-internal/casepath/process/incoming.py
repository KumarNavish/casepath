"""What came in and is still unanswered: an overlay on the backbone's stages.

The stages advance on facts and the clock. A case that a law firm handles under a mandate moves by what comes in: a
cost claim to check and pay, a report, an offer of the other side, a payment, or the firm's report that the customer
does not cooperate. Each such kind is listed in the backbone (``incoming``) with the fact the reader establishes (who
sent what when, from one document, the latest of its kind), the action it calls for and its priority among several.

An item is open while the case's history shows no action of the kind that answers it dated after it, and the handler
has not marked it done (``incoming_done``: incoming items up to that date are done). An open item outranks the stage's
own action and the clock; the stage itself does not move, except that an open cost claim keeps the case from closing
(the derived fact ``kosten_offen``). Model-free.
"""
from .clock import parse_date
from .workflows import CatalogueError, done_actions

PARTIES = {"kanzlei", "gericht", "gegenpartei", "kunde"}
NONE = {"keine", "keiner", "keines", "none", "nein", "-", "—"}


def validate(backbone):
    """Fail closed on an incoming kind the backbone cannot carry."""
    facts = {f["id"]: f for f in backbone["facts"]}
    forms, seen, ranks = backbone["forms"], set(), set()
    done = backbone.get("incoming_done")
    if backbone.get("incoming") and (facts.get(done) or {}).get("type") != "date":
        raise CatalogueError("backbone: incoming_done must name a date fact the handler sets")
    for kind in backbone.get("incoming", []):
        where = f"backbone: incoming kind {kind.get('id')!r}"
        for field in ("id", "fact", "title", "what", "from", "priority", "action", "answered_by", "note", "source_refs"):
            if kind.get(field) in (None, "", []):
                raise CatalogueError(f"{where} needs {field}")
        if kind["id"] in seen or kind["priority"] in ranks:
            raise CatalogueError(f"{where}: its id and its priority must be its own")
        seen.add(kind["id"])
        ranks.add(kind["priority"])
        if (facts.get(kind["fact"]) or {}).get("type") != "text" or facts[kind["fact"]].get("handler_only") or facts[kind["fact"]].get("derived"):
            raise CatalogueError(f"{where}: its fact must be a text fact the reader establishes")
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
    return backbone


def _value(facts, fact):
    value = facts.get(fact)
    if value is None or value is False or str(value).strip().lower() in NONE | {""}:
        return None
    return str(value).strip()


def _answered_after(codes, day, done):
    """Whether the history shows an action of these codes ("any": of any code) dated after the day."""
    for code, days in done.items():
        if codes != "any" and code not in codes:
            continue
        if any((d := parse_date(x)) and day and d > day for x in days):
            return True
    return False


def items(workflow, facts):
    """Every incoming item the case's facts record: {kind, fact, value, date, open, action, decided}, in priority order."""
    done = done_actions(facts)
    marked = parse_date(facts.get(workflow.get("incoming_done") or ""))
    rows = []
    for kind in sorted(workflow.get("incoming") or (), key=lambda k: k["priority"]):
        value = _value(facts, kind["fact"])
        if value is None:
            continue
        day = parse_date(value)
        action, decided = kind["action"], None
        if kind.get("decision"):
            decided = facts.get(kind["decision"]["fact"])
            if decided is not None:
                action = kind["decision"]["yes" if decided is True else "no"]
        answered = action.get("answered_by", kind["answered_by"])
        # marked done by the handler up to a date; an item without a date of its own is done by any mark
        by_hand = marked is not None and (day is None or day <= marked)
        rows.append({"kind": kind, "fact": kind["fact"], "value": value, "date": day.isoformat() if day else None,
                     "open": not by_hand and not _answered_after(answered, day, done), "action": action, "decided": decided})
    return rows


def pending(workflow, facts):
    """The open items, the first to act on first."""
    return [r for r in items(workflow, facts) if r["open"]]


def cost_open(workflow, facts):
    """Whether an incoming item that keeps the case from closing (a cost claim) is still open."""
    return any(r["kind"].get("blocks_closing") for r in pending(workflow, facts))


def reason(row):
    """The reason line: what came in, when, and that it is still open, with what the reader read."""
    day = parse_date(row["date"]) if row["date"] else None
    when = f" vom {day.strftime('%d.%m.%Y')}" if day else ""
    value = row["value"] if len(row["value"]) <= 160 else row["value"][:157].rstrip() + " …"
    if row["decided"] is False:
        return f"{row['kind']['title']}{when}; Leistungen nicht eingestellt: weiteres Vorgehen offen ({value})"
    return f"{row['kind']['title']}{when} eingegangen, noch offen ({value})"
