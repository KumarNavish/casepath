"""What a handler's screens say about a case, decided once, from the item list: the case list and every tab read it.

One truth: the next step, the documents still missing, the deadlines and the status come from here for the Übersicht,
the Unterlagen and the Prozess tab and the case list alike, so their counts and words agree. Each thing is said once on
the Übersicht: the card head states the action, why, the one deadline that leads and the one decision that blocks this
step; «Der Fall» leaves out what the head states. Model-free.
"""
import re

from . import urgent
from .clock import parse_date

DAY = re.compile(r"\b\d{2}\.\d{2}\.\d{4}\b")
STEPS = (("einigung", "Einigung"), ("iban", "Bankverbindung"), ("auszahlung", "Auszahlung ankündigen"), ("eingang", "Eingang"), ("abschluss", "Abschluss"))
LATE_STAGES = {"gegenpartei", "mandat", "abwicklung"}  # stages a cover decision is settled by: the case got there through it
FEE_NOTE = "A11_kosten"


def day(value):
    d = parse_date(value)
    return d.strftime("%d.%m.%Y") if d else None


def label(item):
    return (item.get("label") or {}).get("de") or item.get("what") or item.get("key") or ""


def missing(items, events):
    """The documents still asked, as the letter asks them (the handler's ticks count): one list for every tab."""
    from .letters import asked
    return asked(items, events, "document")


HOLIDAY_NOTE = re.compile(r";?\s*(kantonale )?Feiertage nicht berücksichtigt")


def shown_rule(item):
    """A deadline's rule as the screen shows it: how it is counted, without the calculation's standing note about holidays."""
    return HOLIDAY_NOTE.sub("", str(item.get("rule") or "")).strip(" ;") or None


def days_word(n):
    return "abgelaufen" if n < 0 else "heute" if n == 0 else "noch 1 Tag" if n == 1 else f"noch {n} Tage"


def lead(items, look, rule, stage=None):
    """The card head's deadline line, or None: the most urgent deadline of the customer or the insurer (or a date set for
    them) that is open and ends within the rule's ``lead_days``, else the latest passed and not kept. Once the case is at
    a stage reached through the way to proceed (the other side, a mandate, the handling), a statutory deadline that passed
    lies behind the process and does not lead; a date the account still holds open does."""
    if stage in LATE_STAGES:
        items = [i for i in items if not (i.get("origin") == "law" and (urgent.days_left(i, look) if urgent.dated(i) else 0) < 0)]
    item = urgent.lead(items, look, int((rule or {}).get("lead_days", 30)))
    if not item:
        return None
    n = urgent.days_left(item, look)
    named = item.get("set_by_others") and not item.get("account") and item.get("what")
    src = next((e for e in item.get("evidence") or () if e.get("file")), None)
    return {"item_id": item["item_id"], "date": day(item["value"]), "days": n, "word": days_word(n),
            "kind": "Termin" if named else "Frist", "title": label(item), "urgency": urgent.urgency(item, look, rule),
            "basis": item.get("legal_basis"), "rule": shown_rule(item), "missed": item.get("missed"),
            "by": item.get("source") and f"laut {item['source']}" or item.get("by") if item.get("set_by_others") else None,
            "source": src}


def frist_row(item, look):
    """One deadline, once, compactly: its date or what is missing, its title, how close; an open condition as «nur bei …»."""
    n = urgent.days_left(item, look)
    state = days_word(n) if n is not None else item.get("due_text") or ("Datum fehlt" if item.get("missing") else "prüfen")
    when = day(item["value"]) if urgent.dated(item) else None
    pair = [line for line in (item.get("set_date") or {}).get("lines") or () if not (when and when in line)]  # its own date is the row's
    who = (f"für {item['for']}" if item.get("account") and item.get("for") and item.get("party") not in ("kunde", "versicherer")
           else "für die Gegenpartei" if item.get("party") == "gegenpartei" else None)
    return {"item_id": item["item_id"], "date": day(item["value"]) if urgent.dated(item) else None, "title": label(item), "state": state,
            "late": n is not None and n < 0, "soon": n is not None and 0 <= n <= 14, "condition": urgent.condition_text(item),
            "basis": item.get("legal_basis"), "rule": shown_rule(item), "who": who, "pair": pair,
            "source": next((e for e in item.get("evidence") or () if e.get("file")), None)}


def fristen(items, look, skip=(), stated_days=(), stage=None):
    """«Fristen» in «Der Fall»: every deadline once, by date (the undated after), without what the card head states. Once
    the case is past the way to proceed, a statutory deadline that passed is listed as such, not marked as late."""
    rows = [i for i in items if i["kind"] == "deadline" and not i.get("concerns") and i["item_id"] not in skip
            and not (urgent.dated(i) and day(i["value"]) in stated_days)]
    rows.sort(key=lambda i: (0, i["value"], bool(urgent.condition_text(i))) if urgent.dated(i) else (1, label(i)))
    out = []
    for i, row in ((i, frist_row(i, look)) for i in rows):  # deadlines ending the same day are one row: the date once
        if stage in LATE_STAGES and i.get("origin") == "law":
            row["late"] = False
        same = next((o for o in out if row["date"] and (o["date"], o["state"]) == (row["date"], row["state"])), None)
        if same:  # each deadline keeps its own title and condition in «parts»; the row says them after the one date
            same.setdefault("parts", [{k: same[k] for k in ("item_id", "title", "condition")}]).append({k: row[k] for k in ("item_id", "title", "condition")})
            same["title"] += f" · {row['condition']}: {row['title']}" if row["condition"] and row["condition"] != same["condition"] else f" · {row['title']}"
            same["also"] = same.get("also", []) + [row["item_id"]]
            continue
        out.append(row)
    return out


def without_date(text, date):
    """A reason without the date the deadline line states: the clause that holds it goes («…, zahlbar bis 30.11.2026»)."""
    text = str(text or "")
    if not date or date not in text:
        return text
    at = text.index(date)
    cut = max(text.rfind(", ", 0, at), text.rfind(" – ", 0, at), text.rfind("; ", 0, at))
    return (text[:cut] + text[at + len(date):] if cut >= 0 else text.replace(date, "")).strip(" ,;–")


def account_lines(items, look, act, stated, lead_id=None):
    """«Als Nächstes» in «Der Fall»: the account's lines (what is agreed, what is open with whom), each open request with
    the date it is due by (so that date is not a second «Fristen» line), without what the card head states (its date, the
    deadline that leads) and without the agreement while the payout's progress line stands for it. Returns the lines and
    the account dates they carry."""
    dated = {str(i["key"])[len("konto-"):]: i for i in items if i["kind"] == "deadline" and i.get("account") and str(i["key"]).startswith("konto-")}
    lines, carried = [], set()
    for line in items:
        if line["kind"] != "stand" or line["key"] == "kontakt" or (line["key"] == "vereinbart" and (act.get("settlement") or act.get("owed"))):
            continue
        if not line.get("rows"):
            if not any(d in str(line.get("value") or "") for d in stated):
                lines.append({k: line.get(k) for k in ("item_id", "label", "value", "open", "evidence", "handler")})
            continue
        rows = []
        for row in line["rows"]:
            due = dated.get(str(row.get("request")))
            if (due and due["item_id"] == lead_id) or any(d in row["text"] for d in stated):
                if due:
                    carried.add(due["item_id"])
                continue  # the card head says it
            text = row["text"]
            if due:
                n = urgent.days_left(due, look)
                text += f" · bis {day(due['value'])}" + (" (abgelaufen)" if n is not None and n < 0 else "") if urgent.dated(due) else f" · {due.get('due_text') or 'Frist laut Akte, Datum prüfen'}"
                carried.add(due["item_id"])
            rows.append({**row, "text": text})
        if rows:
            lines.append({**{k: line.get(k) for k in ("item_id", "label", "open", "evidence", "party", "more")}, "rows": rows})
    return lines, carried


def answered(items, fact):
    row = next((i for i in items if i["kind"] == "fact" and i["key"] == fact), None) or {}
    value = row.get("value")
    return None if value in (None, "", "offen") else value


def fact_question(items, fact):
    row = next((i for i in items if i["kind"] == "fact" and i["key"] == fact), None) or {}
    return re.sub(r"\s*\((Entscheid|CasePath)[^)]*\)?", "", label(row)).strip()


def decision(items, draft, stage, routing=None, assessment=None):
    """The one open decision that blocks this step, with its answers, or None. A decision the stage already settles is
    never asked again (cover at the mandate, the way to proceed once the case is past it); the cover check never at intake.
    ``assessment``: the prepared action's decision brief (assessment.build); not read yet."""
    act = next((i for i in items if i["kind"] == "next_action"), None) or {}
    needs = list((draft or {}).get("needs") or ())
    other = (routing or {}).get("other_topic")
    if other:
        return {"key": "process", "question": f"Prozess bestätigen: der Fall betrifft auch «{other.get('topic')}»", "answers": [{"label": "Prozess wählen", "choose": True}],
                "source": (other.get("citations") or [None])[0]}
    for fact in needs:
        if answered(items, fact) is not None or not any(i["kind"] == "fact" and i["key"] == fact for i in items):
            continue
        if fact == "deckung":
            if stage in LATE_STAGES or stage in ("eingang", "klaeren"):
                continue  # settled by the stage the case reached, or not asked at intake (registration is provisional)
            summary = next((i for i in items if i["kind"] == "cover" and i["key"] == "summary"), None)
            return {"key": "deckung", "question": "Deckung", "detail": (summary or {}).get("value", "").replace("Deckung: ", ""),
                    "answers": [{"label": "bestätigen", "decide": "deckung", "value": "bestätigt"}, {"label": "ablehnen", "decline": True}]}
        if fact == "vorgehen" and stage != "vorgehen":
            continue
        values = next((i.get("values") for i in items if i["kind"] == "fact" and i["key"] == fact), None) or ["ja", "nein"]
        words = {"bestätigt": "bestätigen", "abgelehnt": "ablehnen", "ja": "Ja", "nein": "Nein", True: "Ja", False: "Nein"}
        return {"key": fact, "question": fact_question(items, fact),
                "answers": [{"label": words.get(v, str(v)), "decide": fact, "value": v} for v in values if v != "offen"]}
    prospects = next((i for i in items if i["kind"] == "check" and i["key"] == "aussichten"), None)
    if prospects and act.get("action") == "A5" and answered(items, "aussichten") is None:
        if stage not in LATE_STAGES and answered(items, "deckung") is None and stage not in ("eingang", "klaeren"):
            summary = next((i for i in items if i["kind"] == "cover" and i["key"] == "summary"), None)
            return {"key": "deckung", "question": "Deckung", "detail": (summary or {}).get("value", "").replace("Deckung: ", ""),
                    "answers": [{"label": "bestätigen", "decide": "deckung", "value": "bestätigt"}, {"label": "ablehnen", "decline": True}]}
        return {"key": "aussichten", "question": "Erfolgsaussichten", "law": prospects.get("law"),
                "answers": [{"label": "genügend", "decide": "aussichten", "value": "genügend"}, {"label": "nicht genügend", "decide": "aussichten", "value": "nicht genügend"}]}
    if act.get("form") == FEE_NOTE or (draft or {}).get("form") == FEE_NOTE:
        claim = act.get("incoming") or {}
        return {"key": "kostennote", "question": "Kostennote",
                "answers": [{"label": "Zahlung freigeben", "decide": "eingang_erledigt_bis", "value": claim.get("date") or None, "pay": True},
                            {"label": "Rückfrage", "document": "A11_rueckfrage"}, {"label": "Teilweise ablehnen", "document": "A11_teilablehnung"}]}
    return None


def progress(items):
    """The payout as one line: «✓ Einigung · ✓ Bankverbindung · ● Auszahlung nachfragen · ○ Eingang · ○ Abschluss»."""
    act = next((i for i in items if i["kind"] == "next_action"), None) or {}
    seq = act.get("settlement")
    if not seq:
        return None
    owed = bool(act.get("owed"))
    current = "auszahlung" if owed else seq.get("step") or "einigung"
    done = set(seq.get("done") or ())
    if seq.get("terms"):
        done.add("einigung")
    if seq.get("iban"):
        done.add("iban")
    order = [sid for sid, _ in STEPS]
    out = []
    for sid, title in STEPS:
        name = "Auszahlung nachfragen" if sid == "auszahlung" and owed else title
        state = "now" if sid == current else "done" if sid in done or order.index(sid) < order.index(current) else "next"
        out.append({"step": sid, "label": name, "state": state})
    return out


def weil(items, via=None):
    """The card's one line «Weil …»: what led to this step, in words (its own reason, else the way the case came to this
    stage: «Kundschaft hat geantwortet»); its source and articles one click away. None when nothing led to it."""
    act = next((i for i in items if i["kind"] == "next_action"), None) or {}
    if act.get("reason"):
        return act["reason"][:1].upper() + act["reason"][1:]
    if act.get("action") in ("A1", "request"):
        return "Die Meldung ist eingegangen"
    if act.get("closing"):
        return act["closing"][:1].upper() + act["closing"][1:]
    return via[:1].upper() + via[1:] if via and via != "Stand gemäss Akten" else None


LETTER_TO = {"Kundschaft": "Brief an die Kundschaft", "Anwaltskanzlei": "Brief an die Kanzlei", "Gegenpartei": "Brief an die Gegenpartei"}


def letter_title(draft):
    """The letter's tab by whom it goes to («Brief an die Kundschaft»); the form's title where its recipient is not one of these."""
    to = str((draft or {}).get("to") or "")
    return next((title for who, title in LETTER_TO.items() if to.startswith(who)), None) or (draft or {}).get("title") or "Brief"


def documents(draft, events, since=None):
    """What goes out, each its own tab, with a tick once copied since the case was last prepared."""
    if not draft:
        return []
    copied = {(e.get("also") or e.get("form")) for e in events or () if e.get("kind") == "letter.copied" and str(e.get("at") or "") >= str(since or "")}
    out = []
    if draft.get("text"):
        out.append({"kind": draft.get("form") or draft.get("kind"), "main": True, "title": letter_title(draft),
                    "copied": (draft.get("form") or draft.get("kind")) in copied})
    for a in draft.get("also") or ():
        if a.get("text"):
            title = a["title"]
            if a.get("template"):
                title = re.sub(r"^Vorlage für Ihr Schreiben an ", "Vorlage an ", title)
            out.append({"kind": a["kind"], "main": False, "title": title, "name": a.get("name"), "copied": a["kind"] in copied, "template": bool(a.get("template"))})
    twins = {t for t in (o["title"] for o in out) if sum(1 for o in out if o["title"] == t) > 1}
    for row in out:  # two templates to the same addressee: each by what it is («Vorlage: Einsprache gegen die Kündigung»)
        if row.get("template") and row.get("name") and row["title"] in twins:
            row["title"] = f"Vorlage: {row['name']}"
    return out


def key_points(items, letter_text):
    """The legal points «Der Fall» names: only those the letter does not already state (its consequence, its advice or the
    article it rests on), at most three."""
    text = str(letter_text or "")
    out = []
    for p in items:
        if p["kind"] != "key_point" or p.get("value") not in ("applies", "open") or not p.get("shown"):
            continue
        said = [str(x or "")[:48] for x in (p.get("follows"), p.get("advice"), p.get("legal_basis"))]
        if any(s and s in text for s in said):
            continue
        out.append({"item_id": p["item_id"], "text": label(p), "open": p.get("value") == "open", "basis": p.get("legal_basis"),
                    "law": p.get("law"), "follows": p.get("follows"), "check": p.get("check")})
    return out[:3]


def cover_line(items, stage, decided_by=None):
    """«Deckung» in «Der Fall», one line, once decided or settled by the stage; nothing at intake."""
    if stage in ("eingang", "klaeren", None):
        return None
    summary = next((i for i in items if i["kind"] == "cover" and i["key"] == "summary"), None)
    if not summary:
        return None
    value = answered(items, "deckung")
    if value == "bestätigt":
        return {"text": "bestätigt" + (f" · {decided_by}" if decided_by else ""), "state": "ok"}
    if value == "abgelehnt":
        return {"text": "abgelehnt" + (f": {summary.get('reason')}" if summary.get("reason") else ""), "state": "flag"}
    if stage in LATE_STAGES:
        return {"text": "mit dem Vorgehen gegeben", "state": "ok"}
    return {"text": summary["value"].replace("Deckung: ", ""), "state": "open"}


def build(items, draft, events, look, rule, stage=None, via=None, routing=None, since=None, decided_by=None, assessment=None, completion=None):
    """The screen model of one case: the card head and «Der Fall», each thing said once. ``assessment``: the decision brief
    (assessment.build), which the decision reads; ``completion``: where the prepared letter stands after the decision
    (completion.state); not read yet."""
    act = next((i for i in items if i["kind"] == "next_action"), None) or {}
    head_lead = lead(items, look, rule, stage)
    reason = without_date(weil(items, via), (head_lead or {}).get("date")) or None
    stated = set(DAY.findall(" ".join(x for x in (reason or "", (head_lead or {}).get("date") or "") if x)))
    skip = {x for x in ((head_lead or {}).get("item_id"), act.get("deadline")) if x}
    stand, carried = account_lines(items, look, act, stated, (head_lead or {}).get("item_id"))
    # the stage's own short lines (the mandate, the payout's agreement and account), without what the head states; the cost
    # check's lines belong to the fee note's decision
    lines = [{k: i.get(k) for k in ("item_id", "value", "evidence")} for i in items if i["kind"] == "stage_line" and i.get("shown")
             and not str(i["key"]).startswith("kg-") and not any(d in str(i.get("value") or "") for d in stated)]
    rows = fristen(items, look, skip | carried, stated, stage)
    letter = (draft or {}).get("text") or ""
    lines_in_letter = sum(1 for i in missing(items, events) if f"– {label(i)}" in letter)
    gone = missing(items, events)
    return {"title": (act.get("label") or {}).get("de") or act.get("value"), "weil": reason,
            "danach": [t.get("action") or t.get("title") for t in act.get("then") or () if t.get("action") or t.get("title")],
            "lead": head_lead, "decision": decision(items, draft, stage, routing, assessment=assessment), "progress": progress(items),
            "documents": documents(draft, events, since), "fristen": rows, "fristen_elsewhere": bool(head_lead or carried),
            "stand": stand, "lines": lines, "points": key_points(items, letter),
            "cover": cover_line(items, stage, decided_by),
            "missing": len(gone), "missing_ids": [i["item_id"] for i in gone], "missing_in_letter": lines_in_letter == len(gone) and bool(gone),
            "urgency": (head_lead or {}).get("urgency")}
