"""The costs a customer claims, each with a stable identity and an explicit current version.

A claim is one row of the brief's ``claims``; its identity is its place there («c1», «c2» …: rows are never removed or
reordered), so «residual:claim.0», a dispatch's ask and a receipt's check keep meaning the same claim. A later statement
about a claim does one of four things, decided here by code from what the reader recorded (never by a model call):

- **amend** it: a new current version (amount, period, party, number, role), the earlier one kept in ``history`` with
  the passage that stated it;
- **withdraw** it: the claim stays in the record, no longer asked, documented or advised on;
- **add** a further claim: another cost, or the same kind of cost for another period or under another number;
- leave **one specific question**: the same cost stated differently with nothing that says which holds («unclear», the
  candidate named beside the claim it may replace), which the handler settles (edit «set_claim»).

Words locate a candidate, they never decide: the relation the reader names (``relation``, ``claim``), the scope it
records and the day the statement was made do. A statement made before the current version's is an earlier one whatever
day it was uploaded: it joins the history and changes nothing."""
import re

from .clock import parse_date

RELATIONS = ("new", "amends", "withdraws")
CURRENT, WITHDRAWN, UNCLEAR, MERGED, DISMISSED = "current", "withdrawn", "unclear", "merged", "dismissed"
SCOPE = ("amount", "role", "expense", "expense_kind", "party", "period", "transaction")  # what a version states
VERSIONED = SCOPE + ("citations", "stated")
SETTLED_AS = ("amendment", "additional", "dismissed")  # the handler's answers to an unclear statement (edit «set_claim»)


def claim_id(i):
    return f"c{i + 1}"


def words(what):
    """The 5+-letter words of a claim's name: «Stromkosten Bautrockner» is «Stromkosten für den Bautrockner»."""
    return {w for w in re.findall(r"\w{5,}", str(what or "").casefold())}


def normalized(claims):
    """Every claim with its id, version, state and history (a claim recorded before these fields: version 1, current)."""
    return [{**c, "id": c.get("id") or claim_id(i), "version": c.get("version") or 1, "state": c.get("state") or CURRENT,
             "history": [dict(h) for h in c.get("history") or ()]} for i, c in enumerate(claims or ())]


def live(claim):
    """Whether a claim is asked now (its current version counts): not withdrawn, unclear, merged or dismissed."""
    return (claim or {}).get("state", CURRENT) == CURRENT


def number(claim):
    """The claim's amount as a number, or None."""
    from .options import amount_of
    return amount_of(claim.get("amount")) if (claim or {}).get("amount") else None


def chf(value):
    return f"CHF {value:.2f}".replace(".00", "") if value is not None else None


def stated_day(citations, entries):
    """The day a statement was made: the date of the account's entry of the document its passage stands in (the page's
    entry where a file holds several), ISO; None when the file has no dated entry or its entries disagree."""
    for c in citations or ():
        rows = [e for e in entries or () if e.get("file") and e.get("file") == c.get("file") and e.get("date")]
        if c.get("page") is not None and len({e["date"] for e in rows}) > 1:
            rows = [e for e in rows if e.get("page") == c.get("page")] or rows
        days = {str(e["date"])[:10] for e in rows}
        if len(days) == 1:
            return days.pop()
    return None


def _period(claim):
    p = claim.get("period") if isinstance(claim.get("period"), dict) else {}
    start, end = parse_date(p.get("from")), parse_date(p.get("to"))
    return (start or end, end or start) if (start or end) else None


def _number_of(text):
    return re.sub(r"\W", "", str(text or "")).casefold()


def separate(a, b):
    """Whether two statements are about different costs although they are named alike: periods that do not overlap, a
    period that began only after the other was claimed, or different invoice, receipt or meter numbers."""
    pa, pb = _period(a), _period(b)
    if pa and pb and (pa[1] < pb[0] or pb[1] < pa[0]):
        return True
    for claimed, later in ((a, pb), (b, pa)):  # a cost claimed before a period began is not that period's cost
        said = parse_date(claimed.get("stated"))
        if later and not _period(claimed) and said and said < later[0]:
            return True
    ta, tb = _number_of(a.get("transaction")), _number_of(b.get("transaction"))
    return bool(ta and tb and ta != tb)


def agrees(a, b):
    """Whether a statement says of a claim what its current version says (a restatement): the same amount within a
    franc, the same role, nothing that makes it another cost."""
    x, y = number(a), number(b)
    same_amount = x is None or y is None or abs(x - y) <= 1.0
    return same_amount and (a.get("role") or "requested") == (b.get("role") or "requested") and not separate(a, b)


def _earlier(statement, claim):
    """Whether a statement was made before the claim's current version was (both days known)."""
    a, b = parse_date(statement.get("stated")), parse_date(claim.get("stated"))
    return bool(a and b and a < b)


def _snapshot(claim):
    return {"version": claim.get("version") or 1, **{k: claim.get(k) for k in VERSIONED}}


def _amend(target, statement):
    """A new current version of ``target`` from a later statement: what the statement records replaces what the claim
    held; what it leaves out stays. The earlier version keeps its passage."""
    before = _snapshot(target)
    target["history"] = list(target.get("history") or ()) + [{**before, "until": "amended"}]
    for k in SCOPE:
        if statement.get(k) not in (None, "", {}):
            target[k] = statement[k]
    target.update(citations=list(statement.get("citations") or ()), stated=statement.get("stated"), version=before["version"] + 1,
                  checked=bool(target.get("checked") or statement.get("checked")) and (target.get("role") or "requested") != "refunded")
    return before


def _withdraw(target, statement):
    before = _snapshot(target)
    target["history"] = list(target.get("history") or ()) + [{**before, "until": "withdrawn"}]
    target.update(state=WITHDRAWN, checked=False, version=before["version"] + 1,
                  withdrawn={"stated": statement.get("stated"), "citations": list(statement.get("citations") or ())})
    return before


def _change(kind, claim, statement, before=None):
    return {"kind": kind, "claim": claim["id"], "what": claim.get("what"), "before": (before or {}).get("amount"),
            "after": statement.get("amount") or claim.get("amount"), "stated": statement.get("stated"),
            "citations": list(statement.get("citations") or ())[:1]}


def merge(claims, found, entries=()):
    """The claims after an update's statements (``found``: the reader's located claims, each with ``relation`` and
    ``claim`` where it names them; ``entries``: the account's entries, for the day a statement was made): (claims, changes).
    ``changes``: [{kind: amended | withdrawn | added | earlier | unclear, claim, what, before, after, stated, citations}]."""
    out, changes = normalized(claims), []
    by_id = {c["id"]: c for c in out}
    for c in out:  # the day each claim's current version was stated, where the account dates its document
        if not c.get("stated"):
            c["stated"] = stated_day(c.get("citations"), entries)
    for raw in found or ():
        s = {k: v for k, v in raw.items() if k not in ("relation", "claim")}
        s["stated"] = s.get("stated") or stated_day(s.get("citations"), entries)
        relation = raw.get("relation") if raw.get("relation") in ("amends", "withdraws") else None
        named = by_id.get(str(raw.get("claim") or "").strip())
        alike = [c for c in out if c["state"] in (CURRENT, UNCLEAR) and (c["what"].casefold() == str(s.get("what") or "").casefold()
                                                                          or (words(s.get("what")) and words(s.get("what")) == words(c["what"])))]
        if relation and (named is None or not live(named)):  # a relation without a claim it can name: the one claim named alike
            named = alike[0] if len(alike) == 1 and live(alike[0]) else None
        if relation and named is not None:
            if _earlier(s, named):  # said before the current version was: history, whatever day it was uploaded
                named["history"] = named["history"] + [{"version": None, **{k: s.get(k) for k in VERSIONED}, "until": "earlier"}]
                changes.append(_change("earlier", named, s))
            elif relation == "withdraws":
                changes.append(_change("withdrawn", named, s, _withdraw(named, s)))
            elif not (agrees(named, s) and all(s.get(k) in (None, "", {}) or s.get(k) == named.get(k) for k in SCOPE)):
                changes.append(_change("amended", named, s, _amend(named, s)))
            continue
        named_alike = [c for c in alike if live(c)]
        if any(agrees(c, s) and not _earlier(s, c) for c in named_alike):
            continue  # said again
        # the claim it may be about: the first one named alike that it is not plainly another cost than (period, number)
        same = next((c for c in named_alike if not separate(c, s)), None)
        if same is None:  # another cost: nothing named alike, or only for other periods or under other numbers
            row = {**s, "id": claim_id(len(out)), "version": 1, "state": CURRENT, "history": []}
            out.append(row)
            by_id[row["id"]] = row
            changes.append(_change("added", row, s))
        elif _earlier(s, same):
            if not agrees(same, s):
                same["history"] = same["history"] + [{"version": None, **{k: s.get(k) for k in VERSIONED}, "until": "earlier"}]
                changes.append(_change("earlier", same, s))
        elif any(c["state"] == UNCLEAR and c.get("of") == same["id"] and agrees(c, s) for c in out):
            continue  # the same unclear statement again
        else:  # the same cost stated differently, and nothing says which holds: one question, beside the claim
            row = {**s, "id": claim_id(len(out)), "version": 1, "state": UNCLEAR, "of": same["id"], "history": [], "checked": False}
            out.append(row)
            by_id[row["id"]] = row
            changes.append(_change("unclear", same, s, _snapshot(same)))
    return out, changes


def effective(claims, edits=()):
    """The claims with the handler's answers to unclear statements in force (edit «set_claim» {claim, as}): «amendment»
    makes the statement the new version of the claim it may replace, «additional» its own claim, «dismissed» neither. Each
    answer applies once; applying them again changes nothing."""
    out = normalized(claims)
    by_id = {c["id"]: c for c in out}
    for e in edits or ():
        args = e.get("args") or {}
        row = by_id.get(args.get("claim"))
        if e.get("op") != "set_claim" or e.get("status", "active") != "active" or row is None or row["state"] != UNCLEAR:
            continue
        target = by_id.get(row.get("of"))
        if args.get("as") == "amendment" and target is not None:
            _amend(target, row)
            row["state"] = MERGED
        elif args.get("as") == "additional":
            row.update(state=CURRENT, checked=True)
        elif args.get("as") == "dismissed":
            row["state"] = DISMISSED
        else:
            continue
        row["settled"] = {"as": args.get("as"), "by": e.get("by"), "at": e.get("at"), "edit": e.get("id")}
    return out


def contested(claims):
    """{claim id: the unclear statement that may replace it}: while it stands, no receipt settles that claim."""
    return {c["of"]: c for c in normalized(claims) if c["state"] == UNCLEAR and c.get("of")}


def line(claim):
    """A claim as the update's reader sees it, one line: «c1 · v2 · Stromkosten für den Bautrockner · CHF 120 · requested
    · gesagt am 2026-10-05 · Zeitraum … · Nr. …»."""
    p = claim.get("period") if isinstance(claim.get("period"), dict) else {}
    parts = [claim["id"], f"v{claim.get('version') or 1}", str(claim.get("what") or ""), str(claim.get("amount") or "ohne Betrag"),
             claim.get("role") or "requested"]
    if claim.get("state") not in (None, CURRENT):
        parts.append({WITHDRAWN: "zurückgezogen", UNCLEAR: f"unklar zu {claim.get('of')}", MERGED: "übernommen", DISMISSED: "verworfen"}[claim["state"]])
    if claim.get("stated"):
        parts.append(f"gesagt am {claim['stated']}")
    if p.get("from") or p.get("to"):
        parts.append(f"Zeitraum {p.get('from') or '?'} bis {p.get('to') or '?'}")
    if claim.get("transaction"):
        parts.append(f"Nr. {claim['transaction']}")
    return " · ".join(parts)
