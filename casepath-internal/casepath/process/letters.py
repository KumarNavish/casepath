"""The handler's letters and the file note, written from the stored result, the item list and the event log alone.

Deterministic: no model. A letter is the form the workflow names for the action kind (Protekta's wording, from the
development dossiers), filled from what the case asserts and what the handler changed (a line unticked is not asked).
A form with no draft says why ("kein Entwurf: …").
"""
import re
from datetime import date

import json
from pathlib import Path

from .clock import as_of, parse_date

# Protekta's forms, from the handler's workflow seed: the letters of any workflow that brings none of its own.
SEED_FORMS = json.loads((Path(__file__).with_name("workflow_seed") / "mietmangel-handler.json").read_text())["forms"]


def _day(value):
    d = parse_date(value) if value else None
    return d.strftime("%d.%m.%Y") if d else None


GAP = "[bitte ergänzen: "


def gap(what):
    return f"{GAP}{what}]"


def has_gap(text):
    return GAP in (text or "")


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


def request_list(items, events, evaluation, process):
    """The first request's document lines, as the handler sees them: a whole names its parts ("insbesondere …"), a
    conditional need says its condition ("falls …"), a document the file mentions but lacks says so."""
    lines = line_state(events)
    by_key = {i["key"]: i for i in items if i["kind"] == "document"}
    ev_docs = (evaluation or {}).get("documents") or []
    ticked = lambda key, default: lines.get(f"document:{key}", default)
    ask = [d for d in ev_docs if (by_key.get(d["document"]) or {}).get("ask") == "now" and d.get("status") != "present" and ticked(d["document"], True)]
    ask += [d for d in ev_docs if (by_key.get(d["document"]) or {}).get("ask") == "later" and ticked(d["document"], False)]
    ask += [d for d in ev_docs if (by_key.get(d["document"]) or {}).get("ask") == "proposed" and ticked(d["document"], False)]
    ask += [{"document": i["key"], "title": f"{i['label']['de']} ({i['reason']})"} for i in items
            if i["kind"] == "document" and i["key"].startswith("mention-") and lines.get(i["item_id"], i.get("ask") != "proposed")]
    includes = {d["id"]: d.get("includes") or [] for d in (process or {}).get("documents") or []}
    part_of = lambda key: any(key in includes.get(w["document"], []) for w in ask)
    parts = lambda w: [d for d in ask if d["document"] in includes.get(w["document"], [])]
    out = []
    for d in ask:
        if part_of(d["document"]):
            continue
        line = f"– {d['title']}"
        if parts(d):
            line += ", insbesondere " + ", ".join(x["title"] for x in parts(d))
        if d.get("required") == "depends" and d.get("questions"):
            line += " (falls " + " / ".join(q["question"].rstrip("?") for q in d["questions"]) + ")"
        out.append(line)
    return out


INSURED = ("versichert", "vn", "kund", "mieter", "tenant", "customer", "insured")


def greeting(parties):
    """The greeting Protekta's letters use ("Sehr geehrte Frau …" / "Sehr geehrter Herr …"), only when the file states the
    insured person's salutation and name; otherwise the generic one. A salutation is never guessed from a first name."""
    for p in parties or ():
        role, name = str(p.get("label") or "").lower(), str(p.get("value") or "").strip()
        if not any(word in role for word in INSURED) or "vermiet" in role:
            continue
        m = re.fullmatch(r"(Frau|Herr)\s+(?:[A-ZÄÖÜ][\w.-]*\s+)*([A-ZÄÖÜ][\w-]+)", name)
        if m:
            return f"Sehr geehrte Frau {m.group(2)}" if m.group(1) == "Frau" else f"Sehr geehrter Herr {m.group(2)}"
    return "Sehr geehrte Damen und Herren"


def context(case, items, events, follow_up, files=(), today=None, evaluation=None, process=None):
    label = lambda i: (i.get("label") or {}).get("de") or i.get("value") or i["key"]
    facts = {i["key"]: i for i in items if i["kind"] == "fact"}
    docs = asked(items, events, "document")
    missing = [i for i in items if i["kind"] == "document" and i.get("ask") == "now" and i.get("status") != "present"]
    present = [i for i in items if i["kind"] == "document" and i.get("status") == "present"]
    parties = [i for i in items if i["kind"] == "party"]
    summary = next((i["value"] for i in items if i["kind"] == "summary" and i.get("value")), None)
    ref = re.search(r"\d{4}\.\d{4}\.\d{4}", f"{case.get('title', '')} {case.get('intake', '')}")
    sent = [d for d in (parse_date((facts.get(f"handlung_a{n}") or {}).get("value")) for n in (1, 4, 5, 6, 7)) if d]
    lines = line_state(events)
    questions = [i for i in items if i["kind"] == "letter_question" and lines.get(i["item_id"], i.get("ask") != "proposed")]
    hints = [i for i in items if i["kind"] == "hint" and lines.get(i["item_id"], i.get("stated_as") != "put_to_handler")]
    listed = request_list(items, events, evaluation, process) if evaluation else [f"– {label(i)}" for i in docs]
    return {
        "referenz": ref.group(0) if ref else case.get("id", "")[-8:].upper(),
        "referenz_kopf": f"Unsere Referenz: {ref.group(0)}\n\n" if ref else "",
        "registrierung": (f"Vielen Dank für die Anmeldung Ihres Anliegens. Ihr Dossier ist unter der Referenz {ref.group(0)} provisorisch "
                          "registriert; bitte geben Sie diese bei jeder Mitteilung an.") if ref
                         else "Vielen Dank für die Anmeldung Ihres Anliegens. Ihr Dossier ist bei uns provisorisch registriert.",
        "anrede": greeting(parties),
        "liste": "\n".join(listed),
        "fragen": "\n".join(["Weiter bitten wir Sie um die Beantwortung folgender Fragen:"] + [f"– {i['value']}" for i in questions]) if questions else "",
        "fragen_oder_offen": "\n".join(f"– {i['value']}" for i in asked(items, events, "letter_question")) or "\n".join(f"– {label(i)}" for i in missing) or "– (offener Punkt)",
        "hinweise": "\n".join(["Betreffend die geschilderte Situation erlauben wir uns bereits folgende Hinweise:"]
                              + [f"{i['value']}" + (f" ({i['legal_basis']})" if i.get("legal_basis") else "") for i in hints]) if hints else "",
        "frist": _day((follow_up or {}).get("due")) or "…",
        # What only the reading or the handler can say: the stored text when there is one, otherwise a marked gap that
        # blocks copying the letter until it is filled or removed; never an invented sentence.
        "anliegen": summary or gap("was in diesem Fall vorliegt"),
        "empfehlung": gap("die Empfehlung an die Kundschaft"),
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
    if kind == "A1" and not ctx.get("liste"):
        return "", None  # nothing to ask for: no first request
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


def action_options(graph, evaluation, forms):
    """The action kinds of the current stage and its neighbours (the steps it comes from and leads to): what a handler
    may pick instead of the prepared action, each with its days until the follow-up and whether it has a draft."""
    steps = {s["id"]: s for s in graph.get("steps", [])}
    here = ((evaluation or {}).get("current") or {}).get("step") or ((evaluation or {}).get("path") or [{}])[-1].get("step")
    near = [here] + [e["to"] for e in (steps.get(here) or {}).get("next", [])] + [s["id"] for s in steps.values()
                                                                                  if any(e["to"] == here for e in s.get("next", []))]
    out = {}
    for sid in near:
        action = (steps.get(sid) or {}).get("action") or {}
        for kind, days in [(action.get("kind"), action.get("next_in_days")), (action.get("follow_up"), None)] + \
                          [(v.get("kind"), v.get("next_in_days")) for v in action.get("instead", [])]:
            if kind and kind not in out and kind != "A0":  # the receipt is sent by Protekta's online form, not chosen
                form = (forms or {}).get(kind) or {}
                out[kind] = {"kind": kind, "title": form.get("title") or kind, "next_in_days": days, "has_draft": bool(form) and not form.get("none")}
    for rule in graph.get("clock", []):  # a follow-up's days come from the clock when no stage names them
        if rule["then"] in out and out[rule["then"]]["next_in_days"] is None:
            out[rule["then"]]["next_in_days"] = rule.get("deadline_days")
    return list(out.values())


def chosen_action(events):
    """The kind a handler picked instead of the prepared action ("andere Handlung"), latest first; None when none."""
    picks = [e for e in events or () if e.get("kind") == "item.corrected" and e.get("item_id") == "next_action:0" and e.get("chosen")]
    return picks[-1]["chosen"] if picks else None
