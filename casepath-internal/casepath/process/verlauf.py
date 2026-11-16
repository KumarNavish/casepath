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
            "entry.changed", "entry.removed", "run.discarded", "action.approved", "bundle.saved", "action.dispatched", "case.reopened",
            "entry.corrected", "case.reference", "case.assigned", "handover.address", "system.moved", "offer.stance", "knowledge.changed"}
CHANNELS = {"post": "Post", "email": "E-Mail", "portal": "Portal", "andere": "andere"}
RECIPIENTS = {"kunde": "die Kundschaft", "gegenpartei": "die Gegenpartei", "kanzlei": "die Kanzlei", "behoerde": "die Behörde", "andere": "Dritte"}
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


def _who(e):
    """Who a row of the log is by: the handler; «Wissen · <who>» for a rule released or withdrawn there; CasePath for
    what the daily pass recorded by itself."""
    if e.get("kind") == "system.moved":
        return "CasePath"
    return f"{'Wissen' if e.get('kind') == 'knowledge.changed' else 'Fallbearbeitung'} · {e.get('expert') or ''}".rstrip(" ·")


def gesture(e, items, process, edits, events=()):
    """One gesture as a row's words: (what, detail, undo edit id or None); None for a kind that is not listed.
    ``events``: the case's log, for the title of an approved letter a dispatch names."""
    kind, item_id = e.get("kind"), e.get("item_id")
    reason = REASON_WORDS.get(str(e.get("reason") or ""))
    because = f" · {reason}" if reason else ""
    active = {x["id"] for x in edits or () if x.get("status", "active") == "active"}
    undo = e.get("edit_id") if e.get("edit_id") in active else None
    if kind == "action.approved":
        return f"Freigegeben: {e.get('title') or 'Schreiben'}", None, None
    if kind == "bundle.saved":
        return "Versandpaket gespeichert", None, None
    if kind == "action.dispatched":
        title = next((a.get("title") for a in events or () if a.get("kind") == "action.approved" and a.get("version") == e.get("version")), None)
        stale = f"versandt mit früherem Stand: {', '.join(e['stale'])}" if e.get("stale") else None
        return (f"Versandt: {title or 'Schreiben'} an {RECIPIENTS.get(e.get('recipient'), e.get('recipient'))} am {_day(e.get('date'))} "
                f"({CHANNELS.get(e.get('channel'), e.get('channel'))})"), stale, undo
    if kind == "case.reopened":
        return "Wieder geöffnet: neue Unterlagen", None, None
    if kind == "system.moved":  # the daily pass: what moved by time alone, as the list read before and after
        return f"CasePath: {(e.get('before') or {}).get('stand') or '—'} → {(e.get('after') or {}).get('stand') or '—'}", None, None
    if kind == "case.reference":
        return (f"Referenz: {e['text']}" if e.get("text") else "Referenz entfernt"), None, None
    if kind == "case.assigned":
        return f"Zuständig: {e.get('owner') or '—'}" + (f" · Stellvertretung: {e['deputy']}" if e.get("deputy") else ""), None, None
    if kind == "knowledge.changed":  # a rule released or withdrawn in «Wissen» changed what this case asks
        verb = "freigegeben" if e.get("verb") == "released" else "zurückgezogen"
        asks = (f" · neu verlangt: {', '.join(e['added'])}" if e.get("added") else "") + (f" · nicht mehr verlangt: {e['dropped']}" if e.get("dropped") else "")
        return f"Regel {verb}: «{e.get('title')}» (Fassung {e.get('version')}){asks}", None, None
    if kind == "offer.stance":
        words = {"annehmen": "annehmen", "ablehnen": "ablehnen", "gegenangebot": "Gegenangebot"}
        return (f"Angebot der Gegenpartei: {words.get(e.get('stance'), e.get('stance'))}" if e.get("stance") else "Antwort auf das Angebot zurückgenommen"), None, None
    if kind == "handover.address":
        to = RECIPIENTS.get(e.get("to"), e.get("to") or "")
        return (f"Adresse für {to}: {e['address']}" if e.get("address") else f"Adresse für {to} entfernt"), None, None
    if kind == "entry.corrected":
        return f"Anforderung erledigt: {e.get('what') or e.get('request') or ''}".rstrip(": "), None, undo
    if kind == "item.corrected" and item_id == "point:empfehlung" and e.get("chosen"):
        chosen = e["chosen"]
        return ("Aussichten nicht genügend" if chosen == "aussichten_nicht_genuegend"
                else f"Empfehlung übernommen: {' · '.join(e.get('titles') or chosen)}"), reason, None
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
    # a letter dispatched is one row, the handler's «Versandt», on its day: the account's entry of it adds only its notes
    sent_n = {str((x.get("args") or {}).get("n")): x["id"] for x in edits or () if x.get("op") == "add_dispatch"}
    sent_notes = {sent_n[i["key"]]: i.get("notes") or [] for i in items or () if i.get("kind") == "entry" and i.get("key") in sent_n}
    entries = [i for i in items or () if i.get("kind") == "entry" and i.get("key") not in sent_n]
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
        said = gesture(e, items, process, edits, events)
        if said is None:
            continue
        what, detail, undo = said
        sent = e.get("kind") == "action.dispatched"
        notes = ([{"kind": "gesture", "text": detail, "open": False}] if detail else []) + (sent_notes.get(e.get("edit_id"), []) if sent else [])
        out.append({"key": f"event:{e.get('event_id') or e.get('seq')}", "kind": "gesture", "number": None,
                    "date": (str(e.get("date") or "") if sent and parse_date(e.get("date")) else str(e.get("at") or ""))[:10],
                    "at": e.get("at"), "who": _who(e), "title": "Versand" if sent else "Regel" if e.get("kind") == "knowledge.changed" else "Bearbeitung",
                    "what": what, "notes": notes, "open": any(n.get("open") for n in notes), "open_of": [],
                    "evidence": [], "phone": False, **({"undo": undo} if undo else {}), **({"dispatch": True} if sent else {})})
    # in time order: by day; on one day the documents first (by their place), then what was done (by its time)
    rank = {"report": 0, "document": 1, "entry": 1, "gesture": 2}
    out.sort(key=lambda r: (r["date"] or "9999-12-31", rank[r["kind"]], r["number"] if r["number"] is not None else 0, str(r["at"] or "")))
    if out and out[0]["kind"] != "report":  # the report is row 1, whatever its date says
        first = next((r for r in out if r["kind"] == "report"), None)
        if first:
            out.remove(first)
            out.insert(0, first)
    return out
