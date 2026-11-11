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


def reference_day(files, today=None):
    """Today, or for a file cut at a decision point, the latest date among its kept documents."""
    cut = [f for f in files if "cut_of" in (f.get("extraction") or {})]
    if not cut:
        return today or date.today()
    days = [d for f in cut for s in (f["extraction"].get("segments") or []) if (d := parse_date(s.get("date")))]
    return max(days) if days else (today or date.today())


def follow_up(next_in_days, files, events, today=None):
    """{"due", "reference", "set_by"}: the proposed date, or the one a person set; None without a proposal or a set date."""
    ref = reference_day(files, today)
    set_by_hand = [e for e in events if e.get("kind") == "followup.set" and e.get("date")]
    if set_by_hand:
        return {"due": set_by_hand[-1]["date"], "reference": ref.isoformat(), "set_by": set_by_hand[-1].get("expert")}
    if not next_in_days:
        return None
    return {"due": (ref + timedelta(days=int(next_in_days))).isoformat(), "reference": ref.isoformat(), "set_by": None}


if __name__ == "__main__":
    assert parse_date("Mi. 28.08.2024 14:51") == date(2024, 8, 28)
    assert parse_date("9. August 2024") == date(2024, 8, 9)
    assert parse_date("2024-09-06") == date(2024, 9, 6)
    assert parse_date("Juni 23") is None
    cut = [{"extraction": {"cut_of": {}, "segments": [{"date": "14.08.2024"}, {"date": "Mi. 28.08.2024 0"}, {"date": ""}]}}]
    assert reference_day(cut) == date(2024, 8, 28)
    assert follow_up(21, cut, [])["due"] == "2024-09-18"
    assert follow_up(21, cut, [{"kind": "followup.set", "date": "2024-09-30", "expert": "x"}])["due"] == "2024-09-30"
    print("ok")
