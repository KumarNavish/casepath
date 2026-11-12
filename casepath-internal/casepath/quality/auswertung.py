"""Auswertung: what ordinary use of CasePath shows, per case, from the event log and the runs (no questionnaire).

Content-free and pseudonymous: case ids are hashed with a salt, only counts, ratios, durations, item kinds and reason
codes leave the store, and every value passes the scorecard guard. The parity manifest ties the numbers to the code,
workflow and Knowledge versions.
"""
from collections import Counter
from datetime import datetime

from .scorecard import guard, hashed

CORRECTIONS = {"item.corrected", "item.dismissed", "item.added"}


def _seconds(a, b):
    return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds()


def _handling(events):
    """Seconds from the case's first opening to its closing (or last event), idle spans excluded."""
    opened = next((e["at"] for e in events if e["kind"] == "case.opened"), None)
    if not opened:
        return None
    end = next((e["at"] for e in events if e["kind"] == "case.closed"), events[-1]["at"])
    idle, since = 0.0, None
    for e in events:
        if e["kind"] == "idle.started":
            since = e["at"]
        elif e["kind"] == "idle.ended" and since:
            idle, since = idle + _seconds(since, e["at"]), None
    return max(0, round(_seconds(opened, end) - idle))


def case_card(store, case, salt, corrected_before):
    events = store.list_case_events(case["id"])
    fixes = [e for e in events if e["kind"] in CORRECTIONS and e.get("item_id")]
    exposed = {e["item_id"] for e in events if e["kind"] == "item.exposed" and e.get("item_id")}
    unchanged = Counter(i.split(":")[0] for i in exposed - {e["item_id"] for e in fixes})
    letters = [e for e in events if e["kind"] == "letter.copied"]
    run = store.latest_run(case["id"], "completed") or {}
    usage = (run.get("result") or {}).get("usage") or []
    same_again = sum(1 for e in fixes if e["item_id"] in corrected_before)
    corrected_before.update(e["item_id"] for e in fixes)
    return {"case": hashed(case["id"], salt),
            "accepted_unchanged": dict(unchanged), "interventions": len(fixes),
            "interventions_by_kind": dict(Counter(e["item_id"].split(":")[0] for e in fixes)),
            "interventions_by_reason": dict(Counter(str(e.get("reason") or "none") for e in fixes)),
            "letter_changed_ratio": letters[-1].get("change_ratio") if letters else None,
            "handling_seconds": _handling(events) if events else None,
            "sources_opened": sum(1 for e in events if e["kind"] == "source.opened"),
            "same_correction_again": same_again,
            "run_seconds": round(_seconds(run["created_at"], run["finished_at"])) if run.get("created_at") and run.get("finished_at") else None,
            "tokens_noncached": sum((u.get("input_tokens") or 0) - (u.get("cached_tokens") or 0) for u in usage) or None}


def auswertung(store, salt, manifest=None):
    cases = sorted(store.list_cases(), key=lambda c: c.get("created_at") or "")
    seen = set()  # a correction made again in a later case, on the same item: what Knowledge should have prevented
    cards = [case_card(store, c, salt, seen) for c in cases]
    used = [c for c in cards if c["interventions"] or c["accepted_unchanged"] or c["sources_opened"]]
    total = {"cases": len(cards), "cases_used": len(used),
             "interventions_per_used_case": round(sum(c["interventions"] for c in used) / len(used), 2) if used else None,
             "same_correction_again": sum(c["same_correction_again"] for c in cards)}
    return guard({"format": "casepath.auswertung.v1", "total": total, "cases": cards, **({"manifest_sha256": manifest} if manifest else {})})
