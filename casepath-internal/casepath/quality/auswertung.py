"""Auswertung: what ordinary use of CasePath shows, per case, from the event log and the runs (no questionnaire).

Content-free and pseudonymous: case ids are hashed with a salt, only counts, ratios, durations, item kinds and reason
codes leave the store, and every value passes the scorecard guard. The parity manifest ties the numbers to the code,
workflow and Knowledge versions.
"""
from collections import Counter
from datetime import datetime, timezone

from .scorecard import guard, hashed

CORRECTIONS = {"item.corrected", "item.dismissed", "item.added"}
DAY = 86400


def _seconds(a, b):
    return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds()


def _handling(events):
    """The person's active seconds on the case, where they switched the measurement on: the sum of the spans from an
    opening of the case (or a return from idle) to the next idle start (a minute without input, the window hidden, the
    case left). A span that was never ended (the browser was closed) ends at the last thing recorded in it, so a night
    between two openings is never counted. None where nothing was measured."""
    total, start, last, any_ = 0.0, None, None, False
    for e in events:
        kind = e["kind"]
        if kind in ("case.opened", "idle.ended"):
            if start is not None and last is not None:  # the span before was never ended: it ends at its last event
                total += max(0.0, _seconds(start, last))
            start, last, any_ = e["at"], e["at"], True
        elif kind == "idle.started":
            if start is not None:
                total += max(0.0, _seconds(start, e["at"]))
            start, last = None, None
        elif start is not None:
            last = e["at"]
    if start is not None and last is not None:
        total += max(0.0, _seconds(start, last))
    return round(total) if any_ else None


def _letter_change(events):
    """The share of the latest approved letter that is the handler's own wording (words changed of words, counted at the
    approval); for a letter copied without approval (the frozen study) the measure its copy recorded."""
    approved = [e for e in events if e["kind"] == "action.approved" and (e.get("words") or {}).get("total")]
    if approved:
        words = approved[-1]["words"]
        return round(words["changed"] / words["total"], 3)
    letters = [e for e in events if e["kind"] == "letter.copied"]
    return letters[-1].get("change_ratio") if letters else None


def _run_seconds(run):
    """How long the run took; None when its times are missing or its finish lies before its start (a run stored with a
    given finish time, such as a seeded or imported one): a negative duration is no duration."""
    if not (run.get("created_at") and run.get("finished_at")):
        return None
    seconds = round(_seconds(run["created_at"], run["finished_at"]))
    return seconds if seconds >= 0 else None


def case_card(store, case, salt, corrected_before):
    events = store.list_case_events(case["id"])
    fixes = [e for e in events if e["kind"] in CORRECTIONS and e.get("item_id")]
    exposed = {e["item_id"] for e in events if e["kind"] == "item.exposed" and e.get("item_id")}
    unchanged = Counter(i.split(":")[0] for i in exposed - {e["item_id"] for e in fixes})
    run = store.latest_run(case["id"], "completed") or {}
    usage = (run.get("result") or {}).get("usage") or []
    same_again = sum(1 for e in fixes if e["item_id"] in corrected_before)
    corrected_before.update(e["item_id"] for e in fixes)
    return {"case": hashed(case["id"], salt),
            "accepted_unchanged": dict(unchanged), "interventions": len(fixes),
            "interventions_by_kind": dict(Counter(e["item_id"].split(":")[0] for e in fixes)),
            "interventions_by_reason": dict(Counter(str(e.get("reason") or "none") for e in fixes)),
            "letter_changed_ratio": _letter_change(events),
            "handling_seconds": _handling(events) if events else None,
            "sources_opened": sum(1 for e in events if e["kind"] == "source.opened"),
            "same_correction_again": same_again,
            "run_seconds": _run_seconds(run),
            "tokens_noncached": sum((u.get("input_tokens") or 0) - (u.get("cached_tokens") or 0) for u in usage) or None}


def _median(values):
    values = sorted(values)
    if not values:
        return None
    mid = len(values) // 2
    return values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2


def _span(start, end):
    """Seconds from one recorded moment to a later one; None where either is missing, the order is impossible (a case
    seeded with a history older than itself) or both fall in the same second (a case stored together with its history:
    nothing was waited for, so nothing is measured)."""
    if not (start and end):
        return None
    try:
        seconds = _seconds(start, end)
    except ValueError:
        return None
    return seconds if seconds >= 1 else None


def operations(store, now=None):
    """How the operation runs, in the measures claims handling knows (docs/SWISS_PRACTICE.md names the source of each):
    how long a case waits for its first prepared step, its first letter and its cover decision, how long it takes to
    close, how old the open cases are, what was opened and closed in the last 30 days, how many closed cases were opened
    again, how often a prepared letter was approved as written, and how many cover decisions refuse. From the cases, the
    runs and the event log; study copies are left out. Counts and durations only; each median says how many cases it
    rests on, so a small number is read as one."""
    now = now or datetime.now(timezone.utc).isoformat(timespec="seconds")
    cases = [c for c in store.list_cases() if not (c.get("intake") or {}).get("study")]
    prepared, letter, cover, cycle = [], [], [], []
    aging = {"days_0_7": 0, "days_8_30": 0, "days_31_90": 0, "days_over_90": 0}
    opened = closed = reopened = ever_closed = approved = unchanged = decided = refused = still_open = 0
    for c in cases:
        created, events = c.get("created_at"), store.list_case_events(c["id"])
        try:  # a case's age counts from its first second on
            age = max(0.0, _seconds(created, now)) if created else None
        except ValueError:
            age = None
        opened += 1 if age is not None and age <= 30 * DAY else 0
        first = _span(created, store.first_prepared(c["id"]))
        if first is not None:
            prepared.append(first)
        sent = next((e["at"] for e in events if e["kind"] == "action.dispatched"), None)
        if _span(created, sent) is not None:
            letter.append(_span(created, sent) / DAY)
        edits = [e for e in store.list_edits(c["id"]) if e.get("op") == "set_fact" and (e.get("args") or {}).get("fact") == "deckung"]
        if edits:
            decided += 1
            refused += 1 if str((edits[-1].get("args") or {}).get("value")) == "abgelehnt" else 0
            if _span(created, edits[0].get("at")) is not None:
                cover.append(_span(created, edits[0]["at"]) / DAY)
        state = [e for e in events if e["kind"] in ("case.closed", "case.reopened")]
        reopened += sum(1 for e in state if e["kind"] == "case.reopened")
        ever_closed += 1 if any(e["kind"] == "case.closed" for e in state) else 0
        if state and state[-1]["kind"] == "case.closed":
            if _span(created, state[-1]["at"]) is not None:
                cycle.append(_span(created, state[-1]["at"]) / DAY)
            closed += 1 if (_span(state[-1]["at"], now) or 0) <= 30 * DAY else 0
        else:
            still_open += 1
            if age is not None:
                days = age / DAY
                aging["days_0_7" if days <= 7 else "days_8_30" if days <= 30 else "days_31_90" if days <= 90 else "days_over_90"] += 1
        for e in events:
            if e["kind"] == "action.approved" and (e.get("words") or {}).get("total"):
                approved += 1
                unchanged += 1 if not e["words"].get("changed") else 0
    measure = lambda values, digits: {"median": None if not values else round(_median(values), digits), "cases": len(values)}  # noqa: E731
    return {"cases": len(cases), "open": still_open,
            "first_preparation_seconds": measure(prepared, 0), "first_letter_days": measure(letter, 1),
            "cover_decision_days": measure(cover, 1), "cycle_days": measure(cycle, 1),
            "opened_30_days": opened, "closed_30_days": closed, "closed_ever": ever_closed, "reopened": reopened, "aging": aging,
            "letters_approved": approved, "letters_approved_as_written": unchanged,
            "cover_decided": decided, "cover_refused": refused}


def auswertung(store, salt, manifest=None):
    cases = sorted(store.list_cases(), key=lambda c: c.get("created_at") or "")
    seen = set()  # a correction made again in a later case, on the same item: what Knowledge should have prevented
    cards = [case_card(store, c, salt, seen) for c in cases]
    used = [c for c in cards if c["interventions"] or c["accepted_unchanged"] or c["sources_opened"]]
    total = {"cases": len(cards), "cases_used": len(used),
             "interventions_per_used_case": round(sum(c["interventions"] for c in used) / len(used), 2) if used else None,
             "same_correction_again": sum(c["same_correction_again"] for c in cards)}
    return guard({"format": "casepath.auswertung.v1", "total": total, "operations": operations(store), "cases": cards,
                  **({"manifest_sha256": manifest} if manifest else {})})
