"""What the case list says about each case: a title from the case itself, and where it stands in the handler's words.

Model-free; from the item list, the follow-up date, the case's events and files. A historic file cut at a decision
point is looked at as of its own day and listed apart, so its dates never count as overdue among live cases.
"""
from datetime import date, timedelta
import re

from ..process.clock import parse_date
from ..process.letters import customer

RUNNING_DAYS = 21  # a customer's deadline or a set date this close is what the row says
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


def display_title(case, items, short_title, renamed=False):
    """After preparation, the area and the parties («Darlehen · Lea Brunner ./. Max Beispiel»), or the area and the
    request's first words when a party is unknown; a title a person gave, or a case not yet prepared, keeps its own."""
    if renamed or not short_title or not any(i["kind"] in {"next_action", "summary", "party"} for i in items or ()):
        return case["title"]
    parties = [i for i in items if i["kind"] == "party"]
    own = customer(parties)
    role = lambda p: (p.get("label") or {}).get("de") if isinstance(p.get("label"), dict) else str(p.get("label") or "")
    other = next((p for p in parties if p is not own and _name(p) and not HANDLED_ELSEWHERE.search(f"{role(p)} {p.get('value')}")), None)
    if _name(own) and other:
        return f"{short_title} · {_name(own)} ./. {_name(other)}"
    request = next((str(i.get("value") or "") for i in items if i["kind"] == "summary" and i.get("value")), "")
    words = request.split()
    return f"{short_title} · {' '.join(words[:6])}{' …' if len(words) > 6 else ''}" if words else f"{short_title} · {case['title']}"


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


def stand(*, closed, run_status, new_files, items, follow_up, events, completed_at, files, today=None):
    """Where a case stands, in the handler's words, with the rank by which the list orders it (what needs the handler
    first) and the date that goes with it: {kind, text, rank, date}."""
    ref = as_of(files) or today or date.today()
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
            return row("waiting", f"wartet auf {waiting_for(action)} bis {_day(due)}", 8, due)
        if due:
            return row("due", f"Wiedervorlage fällig {_day(due)}", 2, due)
        return row("closed", "erledigt", 9)
    running = sorted(((parse_date(i["value"]), i) for i in items if i["kind"] == "deadline" and i.get("direction") != "ab"
                     and (i.get("party") or "kunde") == "kunde" and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(i.get("value") or ""))
                     and (i.get("origin") == "law" or i.get("set_by_others")) and ref <= parse_date(i["value"]) <= ref + timedelta(days=RUNNING_DAYS)),
                     key=lambda row: row[0])
    if running:
        day, item = running[0]
        return row("frist", f"{'Termin' if item.get('set_by_others') else 'Frist'} {_day(day)}", 1, day)
    contact = None if as_of(files) else next((i for i in items if i["kind"] == "contact"), None)  # a test cut has no first contact due
    if contact and parse_date(contact.get("value")):
        day = parse_date(contact["value"])
        return row("contact", f"Erstkontakt {'überfällig seit' if day < ref else 'bis'} {_day(day)}", 1.5 if day < ref else 3, day)
    return row("prepared", "vorbereitet", 4, due)
