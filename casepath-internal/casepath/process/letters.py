"""The handler's letters and the file note, written from the stored result, the item list and the event log alone.

Deterministic: no model. A letter is the form the workflow names for the action kind (Protekta's wording, from the
development dossiers), filled from what the case asserts and what the handler changed (a line unticked is not asked).
A form with no draft says why ("kein Entwurf: …").
"""
import re
from datetime import date

from .clock import as_of, parse_date


def _day(value):
    d = parse_date(value) if value else None
    return d.strftime("%d.%m.%Y") if d else None


def line_state(events):
    """The handler's last word on each letter line: True ticked, False unticked."""
    state = {}
    for e in events or ():
        if e.get("kind") == "letter.line" and e.get("item_id"):
            state[e["item_id"]] = bool(e.get("included"))
    return state


def asked(items, events, kind):
    """The items of one kind that go into the letter: ticked by default unless unticked, offered ones only if ticked."""
    lines = line_state(events)
    out = []
    for i in items:
        if i["kind"] != kind:
            continue
        default = i.get("ask") == "now" or (kind == "hint" and i.get("stated_as") != "put_to_handler")
        if kind == "document" and (i.get("status") == "present" or not i.get("ask") or i.get("part_of")):
            continue
        if lines.get(i["item_id"], default):
            out.append(i)
    return out


def context(case, items, events, follow_up, files=(), today=None):
    label = lambda i: (i.get("label") or {}).get("de") or i.get("value") or i["key"]
    facts = {i["key"]: i for i in items if i["kind"] == "fact"}
    docs = asked(items, events, "document")
    missing = [i for i in items if i["kind"] == "document" and i.get("ask") == "now" and i.get("status") != "present"]
    present = [i for i in items if i["kind"] == "document" and i.get("status") == "present"]
    parties = [i for i in items if i["kind"] == "party"]
    summary = next((i["value"] for i in items if i["kind"] == "summary" and i.get("value")), None)
    ref = re.search(r"\d{4}\.\d{4}\.\d{4}", f"{case.get('title', '')} {case.get('intake', '')}")
    sent = [d for d in (parse_date((facts.get(f"handlung_a{n}") or {}).get("value")) for n in (1, 4, 5, 6, 7)) if d]
    return {
        "referenz": ref.group(0) if ref else case.get("id", "")[-8:].upper(),
        "anrede": "Sehr geehrte Damen und Herren",  # the name and form of address are the handler's to add
        "liste": "\n".join(f"– {label(i)}" for i in docs) or "– (keine weiteren Unterlagen)",
        "fragen": "\n".join(["Weiter bitten wir Sie um die Beantwortung folgender Fragen:"] + [f"– {i['value']}" for i in asked(items, events, "letter_question")])
                  if asked(items, events, "letter_question") else "",
        "fragen_oder_offen": "\n".join(f"– {i['value']}" for i in asked(items, events, "letter_question")) or "\n".join(f"– {label(i)}" for i in missing) or "– (offener Punkt)",
        "hinweise": "\n\n".join(i["value"] for i in asked(items, events, "hint")),
        "frist": _day((follow_up or {}).get("due")) or "…",
        "anliegen": summary or "Ihr Anliegen betreffend den Mangel an der Mietsache.",
        "empfehlung": "uns die noch fehlenden Unterlagen zuzustellen, damit wir das weitere Vorgehen festlegen können." if missing
                      else "das weitere Vorgehen mit uns zu besprechen.",
        "anlass": "das Telefongespräch" if (facts.get("anruf_offen") or {}).get("value") is True else "Ihre Nachricht",
        "erwartet": ("die noch fehlenden Unterlagen: " + ", ".join(label(i) for i in docs)) if docs else "Ihre Rückmeldung",
        "letzter_kontakt": max(sent).strftime("%d.%m.%Y") if sent else "…",
        "verlangt": "\n".join(f"– {label(i)}" for i in missing) or "– (Unterlagen gemäss unserem Schreiben)",
        "vorhanden": ", ".join(label(i) for i in present) or "gemäss Akten",
        "gegenpartei": next((p["value"] for p in parties if p.get("value") and "mieter" not in str(p.get("label") or "").lower()), "…"),
        "heute": (today or as_of(files)).strftime("%d.%m.%Y"),
    }


def render(kind, forms, ctx):
    """The draft for one action kind: the frame (reference, greeting, closing) around the form's parts; parts that come out
    empty (no questions, no hints) are left out. Returns (text, None) or (None, reason) when the kind has no draft."""
    form = (forms or {}).get(kind)
    if not form:
        return None, "für diese Handlung ist kein Formular hinterlegt"
    if form.get("none"):
        return None, form["none"]
    frame = forms.get("_frame") or {"head": [], "tail": []}
    fill = lambda text: text.format(**ctx)
    body = [fill(p) for p in form["parts"]]
    lines = [fill(p) for p in frame["head"]] + [b for part in body if part.strip() for b in (part, "")] + [fill(p) for p in frame["tail"]][1:]
    return "\n".join(lines).strip(), None


def file_note(case, items, events, follow_up, files=(), runs_done=None):
    """One paragraph for the case system: received, decided and why, sent, awaited. Only from what is stored."""
    label = lambda i: (i.get("label") or {}).get("de") or i["key"]
    received = [f.get("name") for f in files or () if f.get("name")]
    decided = []
    for i in items:
        if i["kind"] == "fact" and i.get("verdict") == "set_by_handler":
            decided.append(f"{label(i)}: {_value(i.get('value'))} (durch die Fallbearbeitung)")
    unticked = [label(i) for i in items if i["kind"] == "document" and line_state(events).get(i["item_id"]) is False]
    action = next((i for i in items if i["kind"] == "next_action"), None)
    reason = (action or {}).get("reason")
    sent = [e for e in events or () if e.get("kind") == "letter.copied"]
    docs = asked(items, events, "document")
    due = _day((follow_up or {}).get("due"))
    parts = []
    if received:
        parts.append(f"Eingegangen: {', '.join(received)}.")
    if decided:
        parts.append(f"Entschieden: {'; '.join(decided)}.")
    if action:
        parts.append(f"Nächster Schritt: {action.get('value')}" + (f", weil {reason}" if reason else "") + ".")
    if unticked:
        parts.append(f"Nicht verlangt (von der Fallbearbeitung gestrichen): {', '.join(unticked)}.")
    if sent:
        parts.append(f"Versandt: Schreiben vom {_day(sent[-1].get('at'))}" + (" (angepasst)" if sent[-1].get("edited") else "") + ".")
    if docs or due:
        parts.append("Erwartet: " + (", ".join(label(i) for i in docs) if docs else "Rückmeldung") + (f" bis {due}" if due else "") + ".")
    return " ".join(parts)


def _value(v):
    return {True: "ja", False: "nein"}.get(v, v)
