"""The Verlauf: one table of the case in time order. The report is its first row; then every document of the file, every
entry the handler made (a call, a conversation, a note) and every gesture the handler made in CasePath (a decision, a
document struck or added, a letter copied, a date set, the case closed), each where it happened.

With the running account the documents are its entries; a case without one (not yet prepared, or prepared before the
account) shows its files, the first as the report. Model-free; from the item list, the files, the case's events and edits.
"""
from .clock import parse_date

# what a handler did, in the handler's words; the gestures the screen logs for measuring only (an item seen, a source
# opened) are not the handler's work and are not listed
GESTURES = {"item.corrected", "item.dismissed", "item.added", "correction.undone", "letter.copied", "letter.line", "followup.set",
            "case.closed", "note.added", "filenote.copied", "case.historic", "case.renamed", "letter.unblocked", "point.settled",
            "entry.changed", "entry.removed", "run.discarded"}
REASON_WORDS = {"1": "steht anders in den Akten", "2": "steht nicht in den Akten", "3": "hier nicht relevant", "4": "gilt generell so",
                "5": "weiss ich von ausserhalb der Akten", "6": "Formulierung"}


def _day(value):
    d = parse_date(value)
    return d.strftime("%d.%m.%Y") if d else ""


def _value(v):
    return {True: "ja", False: "nein", None: "—"}.get(v, v) if isinstance(v, (bool, type(None))) else str(v)


def _label(items, item_id):
    item = next((i for i in items or () if i.get("item_id") == item_id), None)
    return ((item or {}).get("label") or {}).get("de") or (item or {}).get("value") or (item_id or "").split(":", 1)[-1]


def gesture(e, items, process, edits):
    """One gesture as a row's words: (what, detail, undo edit id or None); None for a kind that is not listed."""
    kind, item_id = e.get("kind"), e.get("item_id")
    reason = REASON_WORDS.get(str(e.get("reason") or ""))
    because = f" · {reason}" if reason else ""
    active = {x["id"] for x in edits or () if x.get("status", "active") == "active"}
    undo = e.get("edit_id") if e.get("edit_id") in active else None
    if kind == "item.corrected" and item_id == "next_action:0" and e.get("chosen"):
        title = ((process or {}).get("action_kinds") or {}).get(e["chosen"], {}).get("title") or e["chosen"]
        return f"Andere Handlung gewählt: {title}", reason, None
    if kind == "item.corrected" and e.get("op") == "set_fact":
        fact = next((f for f in (process or {}).get("facts") or () if f["id"] == str(item_id or "").split(":", 1)[-1]), {})
        question = str(fact.get("question") or _label(items, item_id)).split(" (")[0]
        detail = (f"vorher {_value(e['before'])}" if e.get("before") is not None else "") + because
        return f"{question}: {_value(e.get('after'))}", detail.strip(" ·") or None, undo
    if kind == "item.corrected":
        return f"Korrigiert: {_label(items, item_id)}", reason, undo
    if kind == "item.dismissed":
        return f"Nicht nötig: {_label(items, item_id)}", reason, undo
    if kind == "item.added":
        return f"Ergänzt: {_label(items, item_id)}" if item_id else "Ergänzt", reason, undo
    if kind == "correction.undone":
        return "Änderung rückgängig gemacht", None, None
    if kind == "letter.copied":
        form = e.get("also") or e.get("form")
        title = (((process or {}).get("forms") or {}).get(form) or {}).get("title") if form and not str(form).startswith("vorlage:") else None
        return f"Brief kopiert{': ' + title if title else ''}", "angepasst" if e.get("edited") else None, None
    if kind == "letter.line":
        return ("Briefzeile aufgenommen" if e.get("included") else "Briefzeile gestrichen") + f": {_label(items, item_id)}", reason, None
    if kind == "followup.set":
        return f"Wiedervorlage gesetzt: {_day(e.get('date'))}", f"vorher {_day(e.get('before'))}" if e.get("before") else None, None
    if kind == "case.closed":
        return "Erledigt" if e.get("form") == "erledigt" else "Erledigt, mit Vorbehalt", e.get("text"), None
    if kind == "note.added":
        return "Anmerkung", e.get("text"), None
    if kind == "filenote.copied":
        return "Aktennotiz kopiert", None, None
    if kind == "case.historic":
        return "Als historische Akte geführt" if e.get("historic") else "Als laufender Fall geführt", None, None
    if kind == "case.renamed":
        return "Fall umbenannt", e.get("text"), None
    if kind == "letter.unblocked":
        return "Entwurf trotz neuer, ungelesener Dateien verwendet", ", ".join(e.get("files") or ()) or None, None
    if kind == "point.settled":
        return f"Erledigt: {_label(items, item_id)}", None, None
    if kind == "entry.changed":
        return "Eigenen Eintrag geändert", e.get("text"), None
    if kind == "entry.removed":
        return "Eigenen Eintrag entfernt", e.get("text"), None
    if kind == "run.discarded":
        return "Angehaltene Vorbereitung verworfen", None, None
    return None


def rows(items, files=(), events=(), edits=(), process=None):
    """The Verlauf's rows, oldest first: {key, kind ("report" | "document" | "entry" | "gesture"), number, date, at, who, title,
    what, notes, open, open_of, evidence, handler, undo}. Documents stand on their own date; a gesture on the day it was made,
    after the documents of that day."""
    out = []
    entries = [i for i in items or () if i.get("kind") == "entry"]
    documents = [i for i in entries if not i.get("handler")]
    report = next((i for i in documents if i.get("step_kind") == "meldung"), documents[0] if documents else None)
    for i in entries:
        own = i.get("handler")
        who = f"{i.get('from_title')} → {i.get('to_title')}"
        out.append({"key": i["item_id"], "kind": "entry" if own else "report" if i is report else "document", "number": i.get("number"),
                    "date": i.get("date"), "at": (own or {}).get("at"), "who": who, "title": (i.get("label") or {}).get("de"),
                    "what": i.get("value"), "notes": i.get("notes") or [], "open": bool(i.get("open")), "open_of": i.get("open_of") or [],
                    "evidence": i.get("evidence") or [], "phone": bool(i.get("phone")),
                    **({"handler": own} if own else {}), **({"waiting": True} if i.get("waiting") else {})})
    if not documents:  # no account: the files themselves, the first as the report
        for n, f in enumerate(files or ()):
            segment = next((s for s in ((f.get("extraction") or {}).get("segments") or ()) if parse_date(s.get("date"))), {})
            day = parse_date(segment.get("date")) or parse_date(str(f.get("created_at") or "")[:10])
            out.append({"key": f"file:{f.get('id')}", "kind": "report" if n == 0 else "document", "number": None,
                        "date": day.isoformat() if day else None, "at": f.get("created_at"), "who": "", "title": "Meldung" if n == 0 else "Datei",
                        "what": f.get("name"), "notes": [], "open": False, "open_of": [], "evidence": [{"file": f.get("id"), "page": None, "quote": None}],
                        "phone": False})
    for e in events or ():
        if e.get("kind") not in GESTURES:
            continue
        said = gesture(e, items, process, edits)
        if said is None:
            continue
        what, detail, undo = said
        out.append({"key": f"event:{e.get('event_id') or e.get('seq')}", "kind": "gesture", "number": None, "date": str(e.get("at") or "")[:10],
                    "at": e.get("at"), "who": f"Fallbearbeitung · {e.get('expert') or ''}".rstrip(" ·"), "title": "Bearbeitung",
                    "what": what, "notes": [{"kind": "gesture", "text": detail, "open": False}] if detail else [], "open": False, "open_of": [],
                    "evidence": [], "phone": False, **({"undo": undo} if undo else {})})
    # in time order: by day; on one day the documents first (by their place), then what was done (by its time)
    rank = {"report": 0, "document": 1, "entry": 1, "gesture": 2}
    out.sort(key=lambda r: (r["date"] or "9999-12-31", rank[r["kind"]], r["number"] if r["number"] is not None else 0, str(r["at"] or "")))
    if out and out[0]["kind"] != "report":  # the report is row 1, whatever its date says
        first = next((r for r in out if r["kind"] == "report"), None)
        if first:
            out.remove(first)
            out.insert(0, first)
    return out
