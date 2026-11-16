"""The handler's clock: the date a case is next looked at, and what is expected by then.

A prepared action carries "next_in_days" from practice; the follow-up date counts from the case's reference day, which
is today for a live case and the latest dated document for a historic file cut at a decision point. A person can set the
date by hand (event "followup.set"); that date governs. Calendar days only: the date is a proposal, never a legal deadline.
"""
import re
from datetime import date, timedelta

GERMAN_MONTHS = {m: i + 1 for i, m in enumerate(["januar", "februar", "märz", "april", "mai", "juni", "juli", "august",
                                                  "september", "oktober", "november", "dezember"])}


def parse_date(text):
    """The first full date in a segment's date text: 2024-08-14, 14.08.2024, 14. August 2024. None when there is none."""
    text = str(text or "").lower()
    if m := re.search(r"(\d{4})-(\d{2})-(\d{2})", text):
        return date(int(m[1]), int(m[2]), int(m[3]))
    if m := re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text):
        return date(int(m[3]), int(m[2]), int(m[1]))
    if m := re.search(r"(\d{1,2})\.?\s+([a-zä]+)\s+(\d{4})", text):
        if m[2] in GERMAN_MONTHS:
            return date(int(m[3]), GERMAN_MONTHS[m[2]], int(m[1]))
    return None


def as_of(files, today=None):
    """The day the case is looked at: the cut's "as_of" (for a historic file), otherwise today."""
    for f in files or ():
        day = parse_date(((f.get("extraction") or {}).get("cut_of") or {}).get("as_of"))
        if day:
            return day
    return today or date.today()


def silence(rules, facts, files, today=None, stage=None):
    """The follow-up that is due because nobody answered: the insurer's last outgoing action expects an answer, nothing
    dated arrived after it, and the day the case is looked at is past the expected date. None otherwise.

    rules: [{"after": ["1", "4"], "days": 21, "then": "A6", "deadline_days": 25, "source": "practice#…"}, …]
    """
    from .workflows import done_actions  # the history: the dated action facts and the history line ("A8 2024-04-20")
    dated = [(code, d) for code, days in done_actions(facts or {}).items() for x in days if (d := parse_date(x))]
    if not rules or not dated:
        return None
    code, sent = max(dated, key=lambda x: x[1])
    latest = max((d for f in files or () for s in ((f.get("extraction") or {}).get("segments") or []) if (d := parse_date(s.get("date")))),
                 default=sent)
    if latest > sent:  # something dated came in after our last letter: not silence
        return None
    rule = next((r for r in rules if code in r["after"] and (stage is None or r.get("stages") is None or stage in r["stages"])), None)
    day = as_of(files, today)
    if rule and (day - sent).days > rule["days"]:
        return {**rule, "last": f"A{code}", "since": sent.isoformat(), "as_of": day.isoformat(), "silent_days": (day - sent).days}
    return None


def reference_day(files, today=None):
    """Today, or for a file cut at a decision point, the latest date among its kept documents."""
    cut = [f for f in files if "cut_of" in (f.get("extraction") or {})]
    if not cut:
        return today or date.today()
    looked = [d for f in cut if (d := parse_date((f["extraction"].get("cut_of") or {}).get("as_of")))]
    if looked:  # the day the case is looked at: an action proposed then counts from then
        return max(looked)
    days = [d for f in cut for s in (f["extraction"].get("segments") or []) if (d := parse_date(s.get("date")))]
    return max(days) if days else (today or date.today())


def cut_day(files):
    """The «Stand am» of a historic file cut at a decision point, or None for a live case."""
    return next((d for f in files or () if (d := parse_date(((f.get("extraction") or {}).get("cut_of") or {}).get("as_of")))), None)


def newest_document(files):
    """The date of the newest dated document in the file (its read segments), or None."""
    return max((d for f in files or () for s in ((f.get("extraction") or {}).get("segments") or []) if (d := parse_date(s.get("date")))),
               default=None)


HISTORIC_MONTHS = 12  # a file whose newest document is older than this on the day the case was created is a historic file


def months_before(day, months):
    year, month = day.year + (day.month - 1 - months) // 12, (day.month - 1 - months) % 12 + 1
    last = (date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)).day
    return date(year, month, min(day.day, last))


def historic(files, created=None, events=(), today=None):
    """Whether the case is a historic file, looked at for testing rather than worked as a live case: {"newest", "how",
    "as_of"} or None. A cut with a «Stand am» before the day the case was created is one (how "cut"); so is a file whose
    newest dated document is more than twelve months older than that day (how "old"). A person's word (event
    ``case.historic``, the latest) moves a case into the group or out of it (how "person")."""
    created_day = parse_date(str(created or "")[:10]) or today or date.today()
    newest, cut = newest_document(files), cut_day(files)
    marks = [e for e in events or () if e.get("kind") == "case.historic" and isinstance(e.get("historic"), bool)]
    row = lambda how: {"newest": (newest or cut).isoformat() if (newest or cut) else None, "how": how,
                       "as_of": cut.isoformat() if cut else None}
    if marks:
        return row("person") if marks[-1]["historic"] else None
    if cut and cut < created_day:
        return row("cut")
    if newest and newest < months_before(created_day, HISTORIC_MONTHS):
        return row("old")
    return None


def last_dispatch(events):
    """The latest letter the handler confirmed as sent and did not undo: {date, at, form, respond_by}, or None."""
    from .completion import sent_letters
    sent = sent_letters(events)
    return max(sent, key=lambda s: (str(s.get("date") or ""), str(s.get("at") or ""))) if sent else None


def _set_counts(event, step, sent, events):
    """Whether a date a person set («followup.set») counts now: one set after the latest dispatch, for the step prepared
    now (or for no step in particular); or one set for the step that went out, before its dispatch and after the dispatch
    before it: the date its Versandpaket filed as the Wiedervorlage, which the wait after it keeps."""
    at = str(event.get("at") or "")
    if not sent or at > str(sent.get("at") or ""):
        return step is None or event.get("step") in (None, step)
    if not sent.get("action_kind") or event.get("step") != sent.get("action_kind"):
        return False
    from .completion import sent_letters
    before = [str(s.get("at") or "") for s in sent_letters(events) if s.get("version") != sent.get("version") and str(s.get("at") or "") < str(sent.get("at") or "")]
    return at > max(before, default="")


def follow_up(next_in_days, files, events, today=None, since=None, until=None, step=None, filed_days=None):
    """{"due", "reference", "set_by"}: the proposed date, or the one a person set; None without a proposal or a set date.
    ``since``: the day of the last action the case's history shows at or after its stage floor, which the date counts from.
    ``until``: a date the party waited for gave itself («Unterlagen folgen bis …»): the case is looked at again then.
    ``step``: the prepared action's kind; a date a person set for another step, or before the latest dispatch, lapses
    with it, except one set for the step that went out: its Versandpaket filed that date, and the wait keeps it. After a dispatch the date counts from the dispatch day; a letter that set the customer a date (its frozen
    ``respond_by``) is looked at again on that date. A cut counts from its «Stand am», never from an older document or
    action. ``filed_days``: the days after its dispatch the Versandpaket of the letter that went out filed as its
    Wiedervorlage (completion.filed_days); the wait counted from that dispatch keeps that date, so the case says the day
    the handler entered in the claims system."""
    ref = parse_date(since) if since and parse_date(since) else reference_day(files, today)
    cut = cut_day(files)
    if cut and ref < cut:
        ref = cut
    sent = last_dispatch(events)
    set_by_hand = [e for e in events if e.get("kind") == "followup.set" and e.get("date") and _set_counts(e, step, sent, events)]
    if set_by_hand:
        return {"due": set_by_hand[-1]["date"], "reference": ref.isoformat(), "set_by": set_by_hand[-1].get("expert")}
    if until and parse_date(until):
        return {"due": parse_date(until).isoformat(), "reference": ref.isoformat(), "set_by": None, "awaits": True}
    if not next_in_days:
        return None
    if sent and since and parse_date(since) == parse_date(sent.get("date")) and parse_date(sent.get("respond_by")):
        # what is prepared counts from the letter that went out, and that letter told the customer by when: then
        return {"due": parse_date(sent["respond_by"]).isoformat(), "reference": ref.isoformat(), "set_by": None, "respond_by": True}
    if sent and filed_days and since and parse_date(since) == parse_date(sent.get("date")):
        return {"due": (parse_date(sent["date"]) + timedelta(days=int(filed_days))).isoformat(), "reference": ref.isoformat(), "set_by": None, "filed": True}
    return {"due": (ref + timedelta(days=int(next_in_days))).isoformat(), "reference": ref.isoformat(), "set_by": None}


def own_deadlines(items, files=(), today=None):
    """The customer's own statutory deadlines still open, earliest first: dated, to be met ("bis"), not the other side's."""
    day = reference_day(list(files or ()), today)
    rows = [i for i in items or () if i.get("kind") == "deadline" and i.get("origin") == "law" and i.get("party", "kunde") == "kunde"
            and i.get("direction", "bis") == "bis" and parse_date(i.get("value"))]
    return sorted([i for i in rows if parse_date(i["value"]) >= day], key=lambda i: i["value"])


def capped(follow, items, margin, files=(), today=None):
    """The follow-up never later than the earliest open own deadline less a margin (not before the reference day); a
    date a person set stands. Says why when it moved it."""
    open_ = own_deadlines(items, files, today)
    if not follow or follow.get("set_by") or not open_:
        return follow
    limit = max(parse_date(open_[0]["value"]) - timedelta(days=int(margin or 0)), reference_day(list(files or ()), today))
    if parse_date(follow["due"]) <= limit:
        return follow
    return {**follow, "due": limit.isoformat(), "capped": {"deadline": open_[0]["item_id"], "date": open_[0]["value"],
                                                          "reason": "vor Ablauf der gesetzlichen Frist"}}


if __name__ == "__main__":
    assert parse_date("Mi. 28.08.2024 14:51") == date(2024, 8, 28)
    assert parse_date("9. August 2024") == date(2024, 8, 9)
    assert parse_date("2024-09-06") == date(2024, 9, 6)
    assert parse_date("Juni 23") is None
    cut = [{"extraction": {"cut_of": {}, "segments": [{"date": "14.08.2024"}, {"date": "Mi. 28.08.2024 0"}, {"date": ""}]}}]
    assert reference_day(cut) == date(2024, 8, 28)
    assert follow_up(21, cut, [])["due"] == "2024-09-18"
    assert follow_up(7, [{"extraction": {"cut_of": {"as_of": "2025-02-07"}, "segments": [{"date": "18.10.2024"}]}}], [])["due"] == "2025-02-14"
    assert follow_up(7, old_cut := [{"extraction": {"cut_of": {"as_of": "2025-02-07"}, "segments": [{"date": "18.10.2023"}]}}], [], since="2023-10-18")["due"] == "2025-02-14"
    assert historic(old_cut, "2026-11-14T08:00:00")["how"] == "cut"
    assert historic([{"extraction": {"segments": [{"date": "01.10.2025"}]}}], "2026-11-14T08:00:00")["newest"] == "2025-10-01"
    assert historic([{"extraction": {"segments": [{"date": "20.11.2025"}]}}], "2026-11-14T08:00:00") is None
    assert follow_up(21, cut, [{"kind": "followup.set", "date": "2024-09-30", "expert": "x"}])["due"] == "2024-09-30"
    rules = [{"after": ["5"], "days": 90, "then": "A7", "deadline_days": 7}]
    looked = [{"extraction": {"cut_of": {"as_of": "2025-02-07"}, "segments": [{"date": "18.10.2024"}]}}]
    assert silence(rules, {"handlung_a5": "2024-10-18"}, looked)["then"] == "A7"
    assert silence(rules, {"handlung_a5": "2024-10-18"}, [{"extraction": {"cut_of": {"as_of": "2024-11-01"}, "segments": []}}]) is None
    assert silence(rules, {"handlung_a5": "2024-10-18"}, [{"extraction": {"cut_of": {"as_of": "2025-02-07"}, "segments": [{"date": "20.11.2024"}]}}]) is None
    print("ok")
