"""The cover decision prepared, and the insurer's letters whose content the law prescribes.

The data is the house's cover file (its profile's ``conditions.cover``; shipped: ``areas/cover.json``, format
casepath.cover/1). It holds the cover points in the order a handler checks them, each with its clause in each edition
of the house's general conditions (a verbatim passage of at most 50 words, confirmed against the stored text of the
edition, ``conditions.texts``, by the tests), whether the customer's file or the policy answers it, and
what to look up; the few facts these points add to every area (composed in by area.compose); the forms whose parts are
required, each part naming its basis; the rule for the end of benefits for lack of cooperation; and the first contact
the insurer promises publicly.

Model-free. What only the policy can say is never assumed: a point the policy answers stays open until the handler ticks
it; "allgemein drei Monate" is the product page's general statement, used only to compute an aid and always said so.
The decision on cover stays the handler's (``deckung``).

    python -m casepath cover [--sources <folder with the saved fedlex and web pages>]
"""
import argparse
import copy
from datetime import date, timedelta
import functools
import json
from pathlib import Path
import re
import sys

from .. import house
from . import account
from .clock import as_of, parse_date
from .workflows import CatalogueError, done_actions

COVER_FORMAT = "casepath.cover/1"
PATH = house.active().conditions.cover
TEXTS = house.active().conditions.texts
MAX_WORDS = 50
STATES = {  # state: (counted as, words on the screen)
    "akte": ("akte", "aus der Akte geklärt"), "kein_hinweis": ("akte", "kein Hinweis in der Akte"),
    "police_ok": ("police_ok", "in der Police bestätigt"), "police": ("police", "in der Police prüfen"),
    "kunde": ("kunde", "bei der Kundschaft erfragt"), "offen": ("offen", "noch offen"), "hinweis": ("hinweis", "Hinweis"),
}
SUMMARY = [("akte", "aus der Akte geklärt"), ("police_ok", "in der Police geprüft"), ("police", "in der Police prüfen"),
           ("kunde", "bei der Kundschaft erfragt"), ("offen", "offen"), ("hinweis", "Hinweis")]


def gap(what):
    return f"[bitte ergänzen: {what}]"


@functools.lru_cache(maxsize=None)
def _data():
    data = house.in_own_name(json.loads(PATH.read_text(encoding="utf-8")))
    validate(data)
    return data


def data():
    return copy.deepcopy(_data())


# Validation --------------------------------------------------------------------------------------------------------------

def validate(data):
    """Fail closed: every clause and law entry carries a passage of at most 50 words, every point names its clauses in
    both editions, every required form part names its basis, and a law basis must be verified."""
    if not isinstance(data, dict) or data.get("format") != COVER_FORMAT:
        raise CatalogueError(f"cover format must be {COVER_FORMAT}")
    for key, row in data["avb"].items():
        edition = key.split(":", 1)[0]
        if edition not in data["editions"] or not row.get("cite") or not row.get("passage"):
            raise CatalogueError(f"cover: clause {key!r} needs an edition, a cite and its passage")
        if len(row["passage"].split()) > MAX_WORDS:
            raise CatalogueError(f"cover: the passage of {key!r} is longer than {MAX_WORDS} words")
    for key, row in data["law"].items():
        if any(not str(row.get(f) or "").strip() for f in ("cite", "sr", "article", "passage")) or not isinstance(row.get("verified"), bool):
            raise CatalogueError(f"cover: law entry {key!r} needs cite, sr, article, passage and verified")
        if row["sr"] not in data["laws"] or len(row["passage"].split()) > MAX_WORDS:
            raise CatalogueError(f"cover: law entry {key!r} names an unknown law or its passage is too long")
    seen = set()
    facts = {f["id"] for f in data["facts"]}
    for f in data["facts"]:  # the nearest thing that does not count as the fact, as in an area module (area.validate_module)
        if "not_this" in f and not (isinstance(f["not_this"], str) and 10 <= len(f["not_this"].strip()) <= 300):
            raise CatalogueError(f"cover: fact {f['id']}: not_this is one line of 10 to 300 characters")
    for point in data["points"]:
        if point["id"] in seen or point.get("source") not in {"akte", "police", "beides"}:
            raise CatalogueError(f"cover: point {point.get('id')!r} needs its own id and a source (akte, police, beides)")
        seen.add(point["id"])
        for edition in data["editions"]:
            for short in point["clauses"].get(edition, []):
                if f"{edition}:{short}" not in data["avb"]:
                    raise CatalogueError(f"cover: point {point['id']} names clause {edition}:{short}, which has no passage")
        for fact in [point.get("tick"), point.get("tick_unternehmen"), point.get("date")]:
            if fact and fact not in facts:
                raise CatalogueError(f"cover: point {point['id']} names an unknown fact {fact!r}")
    ids = [a.get("id") for a in data["areas"]]
    if not all(isinstance(i, str) and re.fullmatch(r"[a-z][a-z0-9-]*", i) for i in ids) or len(ids) != len(set(ids)):
        raise CatalogueError("cover: each area mapping needs its own id (lower case), the review names it")
    for area in data["areas"]:
        for part in ("eigenschaft", "rechtsgebiet", "grenzen"):
            for edition, shorts in (area.get(part) or {}).items():
                if any(f"{edition}:{s}" not in data["avb"] for s in shorts):
                    raise CatalogueError(f"cover: area {area['prefix']!r} names a clause without passage")
    reasons = next(f for f in data["facts"] if f["id"] == "deckung_grund")["values"]
    if set(reasons) != seen | {"anderer Grund"}:
        raise CatalogueError("cover: deckung_grund must offer every point and «anderer Grund»")
    check_forms({k: flat_form(v) for k, v in data["forms"].items()}, data)
    from . import review  # an open question attached to an element names one the jurist reviews
    review.check_questions(data.get("open_questions"), review.cover_ids(data), "cover")
    return data


def flat_form(form):
    """A form as the letters render it: its parts as text, the required parts listed beside them."""
    parts, required = [], []
    for part in form["parts"]:
        if isinstance(part, dict):
            parts.append(part["text"])
            required.append(part["required"])
        else:
            parts.append(part)
    return {**{k: v for k, v in form.items() if k != "parts"}, "parts": parts, "required": required}


def required_parts(data=None):
    """{form: [required part]} as cover.json defines them: what no area module may remove."""
    data = data or _data()
    return {kind: [p["required"] for p in form["parts"] if isinstance(p, dict)] for kind, form in data["forms"].items()}


def check_forms(forms, data=None):
    """Every required part of a cover form is still in the form, and names a basis: a verified law passage or a clause of
    both editions. An area module that drops or rewords a required part is refused."""
    data = data or _data()
    for kind, wanted in required_parts(data).items():
        form = forms.get(kind)
        if form is None:
            raise CatalogueError(f"form {kind}: missing, but it carries required parts")
        text = "\n".join(p for p in form.get("parts", []) if isinstance(p, str))
        for part in wanted:
            if not part.get("basis") or not part.get("marker") or not part.get("title"):
                raise CatalogueError(f"form {kind}: required part {part.get('id')!r} needs a title, a marker and its basis")
            if part["marker"] not in text:
                raise CatalogueError(f"form {kind}: the required part «{part['title']}» was removed or reworded")
            for ref in part["basis"]:
                source, _, key = ref.partition("#")
                if source == "law":
                    row = data["law"].get(key)
                    if not row or row.get("verified") is not True:
                        raise CatalogueError(f"form {kind}: required part {part['id']!r} rests on {ref}, which is not a verified passage")
                elif source == "avb":
                    slot = data["letter_clauses"].get(key) or {}
                    if any(f"{e}:{s}" not in data["avb"] for e in data["editions"] for s in slot.get(e, [])) or set(slot) != set(data["editions"]):
                        raise CatalogueError(f"form {kind}: required part {part['id']!r} names {ref} without a clause in each edition")
                else:
                    raise CatalogueError(f"form {kind}: unknown basis {ref!r}")
    return forms


# Composition (area.compose adds these to every area) ---------------------------------------------------------------------

def facts_for(module):
    """The cover facts for one area. Where the area itself asks the customer for a date that stands for the cause, the
    cause date is only offered in the first request (not asked twice)."""
    rows = copy.deepcopy(_data()["facts"])
    clash = {f["id"] for f in rows} & {f["id"] for f in module.get("facts", [])}
    if clash:
        raise CatalogueError(f"area {module.get('id')}: a fact repeats a cover fact: {', '.join(sorted(clash))}")
    candidate = _data()["cause_from"].get(module.get("id"))
    own = next((f for f in module.get("facts", []) if f["id"] == candidate), None)
    if own and own.get("ask_customer") or own and any(d.get("trigger") == candidate for d in module.get("deadlines", [])):
        next(f for f in rows if f["id"] == "ursache_datum")["ask_customer"] = "offered"
    return rows


def sources():
    return copy.deepcopy(_data()["sources"])


def forms():
    return {k: flat_form(v) for k, v in copy.deepcopy(_data()["forms"]).items()}


def strip(workflow):
    """A composed workflow without what the cover adds (for comparing with a workflow from before)."""
    out = copy.deepcopy(workflow)
    own = {f["id"] for f in _data()["facts"]}
    out["facts"] = [f for f in out["facts"] if f["id"] not in own]
    out["sources"] = [s for s in out["sources"] if s["id"] not in {x["id"] for x in _data()["sources"]}]
    out["forms"] = {k: v for k, v in out.get("forms", {}).items() if k not in _data()["forms"]}
    return out


# Editions and clauses ----------------------------------------------------------------------------------------------------

def edition(facts):
    """The conditions that apply: "privat" (the default), "unternehmen", or None for another edition."""
    value = (facts or {}).get(_data()["edition_fact"])
    if value is None:
        return _data()["default_edition"]
    return next((k for k, e in _data()["editions"].items() if e["value"] == value), None)


def clauses(shorts_by_edition, ed):
    """[{cite, passage, key}] for one edition; for another edition one entry that says the clause is to be checked."""
    if ed is None:
        return [{"cite": "Ziffer prüfen", "key": None,
                 "passage": f"Andere Ausgabe der {house.active().conditions.name_inflected}: Ziffer und Wortlaut in der geltenden Ausgabe prüfen."}]
    return [{**_data()["avb"][f"{ed}:{s}"], "key": f"{ed}:{s}"} for s in (shorts_by_edition or {}).get(ed, [])]


def cite_list(rows):
    """"Art. M Ziff. 1 und 4" from M.1 and M.4; one article named once."""
    cites = [r["cite"] for r in rows]
    if not cites:
        return ""
    head = re.match(r"(Art\. \S+ Ziff\.) (\S+)$", cites[0])
    if head and all(re.match(re.escape(head.group(1)) + r" \S+$", c) for c in cites):
        numbers = [c.rsplit(" ", 1)[1] for c in cites]
        return f"{head.group(1)} {' und '.join([', '.join(numbers[:-1]), numbers[-1]]) if len(numbers) > 1 else numbers[0]}"
    return ", ".join(dict.fromkeys(cites))


def letter_clause(slot, ed):
    """The clause a letter names, by edition; a marked gap for another edition."""
    if ed is None:
        return gap(f"Ziffer der {house.active().conditions.name_inflected}")
    return cite_list(clauses(_data()["letter_clauses"][slot], ed))


def area_row(rechtsgebiet):
    value = str(rechtsgebiet or "")
    return next(a for a in _data()["areas"] if value.startswith(a["prefix"]))


# Dates -------------------------------------------------------------------------------------------------------------------

def add_months(start, months):
    year, month = start.year + (start.month - 1 + months) // 12, (start.month - 1 + months) % 12 + 1
    last = (date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)).day
    return date(year, month, min(start.day, last))


def day_text(d):
    return d.strftime("%d.%m.%Y") if d else ""


def _iso_or_none(value):
    raw = str(value or "")
    return parse_date(raw) if re.fullmatch(r"\s*(\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{4})\s*", raw) else None


def cause(workflow, facts):
    """(date, fact, how): the cause date the file states (ursache_datum), else the area's own date that stands for it
    (to be checked), else (None, None, None)."""
    own = _iso_or_none(facts.get("ursache_datum"))
    if own:
        return own, "ursache_datum", None
    candidate = _data()["cause_from"].get((workflow or {}).get("id"))
    if candidate and _iso_or_none(facts.get(candidate)):
        question = next((f.get("question") for f in (workflow or {}).get("facts", []) if f["id"] == candidate), candidate)
        return _iso_or_none(facts.get(candidate)), candidate, f"Datum aus «{question}» übernommen: als Ursache prüfen"
    return None, None, None


def add_working_days(start, n):
    day = start
    while n > 0:
        day += timedelta(days=1)
        if day.weekday() < 5:
            n -= 1
    return day


# The insurer's own record that the report came in: its receipt or its registration of the claim.
RECEIPT = re.compile(r"eingangsbest|empfangsbest|registrier|erfasst|dossiereröffnung|eröffnung des dossiers|eingang (?:der|ihrer) (?:schaden)?meldung", re.I)
INSURER = re.compile(house.active().named_in(), re.I)


def report_date(files, created=None):
    """The day the case came in to the insurer as the product can know it: the insurer's own receipt or registration of
    the report when the file holds one (its date, earlier or later), else the day the case was created in CasePath, else
    the day its first file was added. A letter of the customer is not the day it came in. (date, how) or (None, None)."""
    segments = [s for f in files or () for s in ((f.get("extraction") or {}).get("segments") or [])]
    receipts = [d for s in segments if RECEIPT.search(f"{s.get('kind') or ''} {s.get('title') or ''}")
                and (INSURER.search(str(s.get("sender") or "")) or re.search(r"eingangsbest|registrier", f"{s.get('kind') or ''}", re.I))
                and (d := parse_date(s.get("date")))]
    if receipts:
        return min(receipts), "Eingangsbestätigung der Versicherung"
    opened = parse_date(str(created or "")[:10])
    if opened:
        return opened, "Eröffnung des Falls"
    added = [d for f in files or () if (d := parse_date(str(f.get("created_at") or "")[:10]))]
    if added:
        return min(added), "Eingang der ersten Datei"
    return None, None


def first_contact(facts, files, today=None, created=None, historic=False):
    """By when the insurer contacts the customer (three working days from the day the case came in, weekends skipped,
    public holidays not counted); None for a historic file, once a first request or another contact of the insurer is in
    the case's history, or without a day it came in."""
    rule = _data()["first_contact"]
    done = done_actions(facts or {})
    if historic or any(c in done for c in rule["contacts"]):
        return None
    start, how = report_date(files, created)
    if start is None:
        return None
    due = add_working_days(start, rule["working_days"])
    look = as_of(files or (), today)
    public = _data()["public"][rule["public"]]
    return {"due": due.isoformat(), "from": start.isoformat(), "how": how, "late": look > due,
            "rule": f"{rule['working_days']} Arbeitstage ab {how} vom {day_text(start)}; {rule['note']}",
            "basis": f"«{public['passage']}» ({public['title']})"}


# Evaluation --------------------------------------------------------------------------------------------------------------

def _evidence(rows, fact):
    row = next((r for r in rows or () if r.get("fact") == fact and r.get("status") == "established"), None)
    return [{"file": c.get("file"), "page": c.get("page"), "quote": c.get("quote")} for c in (row or {}).get("citations") or ()]


def _insured_name(parties):
    for p in parties or ():
        role = str(p.get("role") or p.get("label") or "").lower()
        if any(w in role for w in ("versichert", "kund", "mieter", "tenant", "customer", "insured", "arbeitnehmer")) and "vermiet" not in role:
            role = re.sub(r"\s*\((?:VN|GP)\)\s*", " ", str(p.get("role") or p.get("label") or "")).strip()  # «Mieterin (VN)» once
            return f"{p.get('name') or p.get('value')}" + (f" ({role})" if role else "")
    return None


def evaluate(workflow, facts, rows=None, files=None, parties=None, today=None):
    """The cover points of one case, in order: each with its state, what decided it, its clauses in the edition that
    applies, and for policy points what to look up and the dates that help. Plus the summary line."""
    facts = facts or {}
    ed = edition(facts)
    area = area_row(facts.get("rechtsgebiet"))
    ursache, cause_fact, cause_how = cause(workflow, facts)
    begin = _iso_or_none(facts.get("police_beginn"))
    public = _data()["public"]["wartefrist"]
    out = []
    for p in _data()["points"]:
        source = p.get(f"source_{ed}", p["source"]) if ed else p["source"]
        tick = p.get(f"tick_{ed}", p.get("tick")) if ed else p.get("tick")
        shorts = dict(p["clauses"])
        extra = {"eigenschaft": area.get("eigenschaft"), "rechtsgebiet": area.get("rechtsgebiet"), "grenzen": area.get("grenzen")}.get(p["id"]) or {}
        if p["id"] == "eigenschaft" and ed == "unternehmen":
            extra = {}
        merged = {e: list(dict.fromkeys(list(shorts.get(e, [])) + list(extra.get(e, [])))) for e in _data()["editions"]}
        row = {"id": p["id"], "title": p["title"], "question": p["question"], "source": source, "tick": tick,
               "tick_value": facts.get(tick) if tick else None, "date_fact": p.get("date"), "clauses": clauses(merged, ed),
               "state": None, "text": "", "aid": "", "note": p.get(f"note_{ed}") if ed else None, "facts": [], "lookup": p.get("lookup")}
        ticked = row["tick_value"]

        def by_policy(open_text, aid=""):
            if ticked is True or (isinstance(ticked, str) and ticked not in {"andere"}):
                return "police_ok", "in der Police bestätigt", ""
            if ticked is False:
                return "hinweis", "laut Police nicht erfüllt", ""
            return "police", open_text, aid

        if p["id"] == "vertrag":
            row["state"], row["text"], row["aid"] = by_policy(p["lookup"], f"Police am {day_text(ursache)} (Ursache) in Kraft?" if ursache else "")
        elif p["id"] == "person":
            name = _insured_name(parties)
            row["state"], row["text"], row["aid"] = by_policy(p["lookup"], f"laut Akte: {name}" if name else "")
        elif p["id"] == "eigenschaft":
            if source == "police":
                row["state"], row["text"], row["aid"] = by_policy(p["lookup"])
            elif facts.get("rechtsgebiet") and area.get("capacity"):
                row.update(state="akte", text=area["capacity"], facts=["rechtsgebiet"])
                row["aid"] = area.get("capacity_check") or ""
            elif facts.get("rechtsgebiet"):
                row.update(state="offen", text="Eigenschaft nach dem Anliegen bestimmen", facts=["rechtsgebiet"])
            else:
                row.update(state="offen", text="Rechtsgebiet noch nicht bestimmt")
        elif p["id"] == "rechtsgebiet":
            label = (area.get("label_unternehmen") if ed == "unternehmen" else None) or area.get("label")
            if not facts.get("rechtsgebiet"):
                row.update(state="offen", text="Rechtsgebiet noch nicht bestimmt")
            else:
                row["facts"] = ["rechtsgebiet"]
                what = f"«{label}» in der Police eingeschlossen?" if label else "Rechtsgebiet in der Police prüfen"
                row["state"], row["text"], row["aid"] = by_policy(what)
        elif p["id"] == "zeitraum":
            row["facts"] = [cause_fact] if cause_fact else []
            if ursache is None:
                row.update(state="kunde", text="Datum der Ursache fehlt: in der ersten Anforderung erfragt")
            elif begin is None:
                row.update(state="police", text=f"Ursache am {day_text(ursache)}",
                           aid=f"Antrag vor dem {day_text(ursache)} gestellt und Police an diesem Tag in Kraft?")
            elif ursache < begin:
                row.update(state="hinweis", text=f"Ursache am {day_text(ursache)} liegt vor dem Beginn des Versicherungsschutzes am {day_text(begin)}")
            else:
                row.update(state="police_ok", text=f"Ursache am {day_text(ursache)}, nach dem Beginn am {day_text(begin)}")
            if cause_how:
                row["note"] = "; ".join(x for x in (row["note"], cause_how) if x)
        elif p["id"] == "wartefrist":
            row["facts"] = [cause_fact] if cause_fact else []
            general = ed == "privat"
            exempt = area.get("label") in public["without"]
            row["lookup"] = "gemäss Police; allgemein drei Monate" if general else "Wartefrist gemäss Police"
            if ursache is None:  # the date is asked once (under the period of the contract); the policy is looked up anyway
                row.update(state="police", text=row["lookup"], aid="Datum der Ursache fehlt (in der ersten Anforderung erfragt)")
            elif ticked == "keine":
                row.update(state="police_ok", text="laut Police keine Wartefrist")
            elif begin is None:
                row.update(state="police", text=row["lookup"],
                           aid=(f"bei drei Monaten: Police spätestens am {day_text(add_months(ursache, -3))} in Kraft" if general or ticked == "drei Monate" else ""))
            else:
                end = add_months(begin, 3)
                if ticked == "drei Monate" or (ticked is None and general and not exempt):
                    stated = ticked == "drei Monate"
                    if ursache < end:
                        row.update(state="hinweis", text=f"Ursache am {day_text(ursache)} liegt in der {'Wartefrist der Police' if stated else 'allgemeinen Wartefrist'} "
                                                        f"von drei Monaten ab {day_text(begin)} (bis {day_text(end - timedelta(days=1))})"
                                                        + ("" if stated else "; Wartefrist in der Police prüfen"))
                    else:
                        row.update(state="police_ok" if stated else "police", text=f"Ursache am {day_text(ursache)} nach drei Monaten ab {day_text(begin)}"
                                   + ("" if stated else "; Wartefrist in der Police prüfen"))
                else:
                    row.update(state="police", text=row["lookup"], aid=f"Beginn {day_text(begin)}, Ursache {day_text(ursache)}: Ende der Wartefrist nach Police berechnen")
        elif p["id"] == "gebiet":
            row["state"], row["text"], row["aid"] = by_policy(p["lookup"])
        elif p["id"] == "ausschluss":
            row["facts"] = ["ausschluss_hinweis"]
            value = facts.get("ausschluss_hinweis")
            row.update(state="hinweis", text=str(value)) if value else row.update(state="kein_hinweis", text="kein Hinweis auf eine Deckungseinschränkung in der Akte")
        elif p["id"] == "pflichten":
            row["facts"] = ["vorab_schritte"]
            value = facts.get("vorab_schritte")
            if value:
                row.update(state="hinweis", text=str(value),
                           note="Ein Nachteil tritt nur bei Verschulden und Einfluss auf das Ereignis oder die Leistung ein (Art. 45 Abs. 1 VVG): prüfen, nicht folgern.")
            else:
                row.update(state="kein_hinweis", text="kein Schritt ohne Genehmigung in der Akte")
            reported, _ = report_date(files)
            if reported and ursache:
                row["aid"] = f"Meldung am {day_text(reported)}, {max(0, (reported - ursache).days)} Tage nach der Ursache"
        elif p["id"] == "grenzen":
            row["state"], row["text"], row["aid"] = by_policy(area.get("grenzen_text") or p["lookup"])
        if p["id"] == "wartefrist" and general:
            row["note"] = (f"«{public['passage']}» ({public['title']}); ohne Wartefrist: {', '.join(public['without'])}; "
                           "entfällt bei nahtlosem Wechsel vom Vorversicherer")
        row["count"], row["state_text"] = STATES[row["state"]]
        out.append(row)
    return {"edition": ed, "edition_value": facts.get(_data()["edition_fact"]) or _data()["editions"][_data()["default_edition"]]["value"],
            "points": out, "summary": summary(out), "decision": facts.get("deckung"), "reason": facts.get("deckung_grund"),
            "cause": ursache.isoformat() if ursache else None}


def summary(points):
    counts = {}
    for p in points:
        counts[p["count"]] = counts.get(p["count"], 0) + 1
    parts = [f"{counts[k]} {'Hinweise' if k == 'hinweis' and counts[k] > 1 else words}" for k, words in SUMMARY if counts.get(k)]
    return "Deckung: " + " · ".join(parts)


# Items -------------------------------------------------------------------------------------------------------------------

def _item(kind, key, label, **fields):
    return {"item_id": f"{kind}:{key}", "kind": kind, "key": key, "system": "casepath", "label": {"de": label, "en": label},
            "verdict": None, "node": None, "chain": False, "origin": "cover", **fields}


def items(graph, facts, result, files, action=None, stage=None, today=None, created=None, historic=False, ledger=None):
    """The cover points (kind "cover", key = the point's id), the checks a prescribed letter rests on (kind "check") and the
    first contact (kind "contact"). Hashed like every item: kind, key, value (the state) and stated_as."""
    rows = (result or {}).get("facts") or []
    parties = ((result or {}).get("brief") or {}).get("parties") or []
    cover = evaluate(graph, facts, rows, files, parties, today)
    out = [_item("cover", "summary", cover["summary"], value=cover["summary"], stated_as="computed", evidence=[],
                 edition=cover["edition"], edition_value=cover["edition_value"], decision=cover["decision"], reason=cover["reason"])]
    for p in cover["points"]:
        evidence = [e for f in p["facts"] for e in _evidence(rows, f)]
        out.append(_item("cover", p["id"], p["question"], value=p["state"], stated_as="computed", evidence=evidence, title=p["title"],
                         source=p["source"], state_text=p["state_text"], text=p["text"], aid=p["aid"], note=p["note"], lookup=p["lookup"],
                         clauses=p["clauses"], legal_basis=cite_list(p["clauses"]), tick=p["tick"], tick_value=p["tick_value"],
                         date_fact=p["date_fact"], date_value=facts.get(p["date_fact"]) if p["date_fact"] else None, facts=p["facts"]))
    out += checks(graph, facts, rows, action, stage, ledger)
    contact = first_contact(facts, files, today, created, historic)
    if contact:
        out.append(_item("contact", "erstkontakt", "Erstkontakt mit der Kundschaft", value=contact["due"], stated_as="computed", evidence=[],
                         rule=contact["rule"], stated=contact["from"], late=contact["late"], legal_basis=contact["basis"]))
    return out


def law_row(key):
    row = _data()["law"][key]
    return {"cite": row["cite"], "passage": row["passage"], "verified": row["verified"]}


def warned(facts, ledger=None):
    """The insurer's own written demand with the consequences stated, as the file shows it: (its date or None, the
    reading) or None. From the running account where it holds one (the latest), else from the fact read."""
    own = [w for w in account.warnings(ledger) if w["own"]]
    if own:
        w = own[-1]
        return parse_date(w["date"]), _warning_text(w)
    value = facts.get("mahnung_androhung")
    if not value or str(value).strip().lower() in {"keine", "nein", "-", "none"}:
        return None
    return parse_date(str(value)), str(value)


def _warning_text(w):
    """«Kanzlei, Schreiben vom 12.03.2025: Belege der Reparaturkosten bis 26.03.2025»."""
    due = f" bis {day_text(parse_date(w['due']))}" if w.get("due") else f" ({w['due_text']})" if w.get("due_text") else ""
    when = f"Schreiben vom {day_text(parse_date(w['date']))}" if w.get("date") else "Schreiben ohne Datum"
    return f"{house.active().name if w['own'] else w['by_title']}, {when}: {w.get('what') or 'Aufforderung'}{due}"


def warning_state(facts, ledger=None):
    """What the file holds before an end of benefits: (value, lines, evidence). «vorhanden»: the insurer's own written
    demand with the consequences; «andere»: only one by someone else (the mandated firm), shown as such with «ob das
    genügt: prüfen», which does not count as the insurer's own; «fehlt»: none in the file."""
    all_ = account.warnings(ledger)
    own = warned(facts, ledger)
    others = [w for w in all_ if not w["own"]]
    lines = ([_warning_text(w) for w in all_ if w["own"]] or ([own[1]] if own else [])) + \
            [f"{_warning_text(w)} · Aufforderung durch {'die Kanzlei' if w['by'] == 'kanzlei' else w['by_title']}, nicht durch {house.active().name} · ob das genügt: prüfen"
             for w in others]
    evidence = [{"file": c.get("file"), "page": c.get("page"), "quote": c.get("quote")} for w in all_ for c in w["citations"]]
    if own:
        return "vorhanden", lines, evidence
    if others:
        return "andere", lines, evidence
    return "fehlt", ["nicht in der Akte: zuerst die Aufforderung mit Frist und Androhung"], evidence


def is_ending(action, stage):
    rule = _data()["cooperation"]
    if not action:
        return False
    form = action.get("form")
    return form in rule["endings"] or (action.get("kind") == "A12" and stage == rule["ending_stage"] and form in (None, "A12", rule["warned_ending_form"]))


def checks(graph, facts, rows, action, stage, ledger=None):
    """What a prescribed letter rests on, shown before it: the written demand with its consequences before an end of
    benefits (with the note that a disadvantage needs fault and causal effect), consent before a settlement when an offer
    is open, and the decision on prospects at the assessment."""
    out = []
    ed = edition(facts)
    form, kind = (action or {}).get("form"), (action or {}).get("kind")
    demand = _data()["cooperation"]["demand"]
    if is_ending(action, stage) or form == demand["form"]:
        state, lines, evidence = warning_state(facts, ledger)
        own = [w for w in account.warnings(ledger) if w["own"]]
        out.append(_item("check", "androhung", "Schriftliche Aufforderung mit Androhung der Säumnisfolgen vor der Leistungseinstellung",
                         value=state, stated_as="computed", evidence=evidence or _evidence(rows, "mahnung_androhung"),
                         text="; ".join(lines), lines=lines,
                         warnings=[{k: w[k] for k in ("by", "by_title", "date", "due", "what", "own")} for w in account.warnings(ledger)],
                         own_date=(own[-1]["date"] if own else None),
                         # what is asked of the customer and not delivered, from the requests ledger, in neutral words
                         open_requests=account.open_items(ledger, "kunde", account.OWED_TO_US),
                         legal_basis=law_row("vvg-39.2.2")["cite"], law=[law_row("vvg-39.2.2")],
                         note={"text": "Ein Nachteil wegen verletzter Obliegenheit tritt nur bei Verschulden und Einfluss auf das Ereignis "
                                       "oder die Leistung ein: als Prüfung, nicht als Schluss.", "law": law_row("vvg-45.1")},
                         decide="leistungen_einstellen", decided=facts.get("leistungen_einstellen")))
    if kind == "A9" or form == "A9" or (graph and facts.get("eingang_angebot") and stage == "gegenpartei"):
        rows_ = clauses(_data()["letter_clauses"]["vergleich"], ed)
        out.append(_item("check", "vergleich", f"Ein Vergleich braucht die Zustimmung von {house.active().name}", value="hinweis", stated_as="computed",
                         evidence=[], text="Vor Abschluss eines Vergleiches muss die Kundschaft oder ihr Anwalt die Zustimmung einholen.",
                         legal_basis=cite_list(rows_), clauses=rows_))
    if kind == "A5" or stage == "beurteilen" or form == "A5_aussichtslos":
        out.append(_item("check", "aussichten", "Erfolgsaussichten (Entscheid der Fallbearbeitung)", value=facts.get("aussichten"),
                         stated_as="computed", evidence=[], decide="aussichten",
                         text="Bei «nicht genügend» wird die Einschätzung zur Ablehnung mit Begründung und Hinweis auf das Schiedsverfahren.",
                         legal_basis=law_row("avo-169.2")["cite"], law=[law_row("avo-169.2"), law_row("avo-169.3")]))
    return out


# The prepared action -----------------------------------------------------------------------------------------------------

def adjust(planned, facts, stage, ledger=None):
    """The prepared action, where a prescribed letter changes it: the assessment becomes the refusal for lack of prospects
    when the handler judged them insufficient; an end of benefits for lack of cooperation is preceded by the written demand
    with the consequences stated (Art. 39 Abs. 2 Ziff. 2 VVG) unless the file shows one or the handler decided to end the
    benefits all the same; once warned, the clarifying stage's ending names the demand."""
    if not planned:
        return planned
    rule = _data()["cooperation"]
    from . import refusal
    if refusal.applies(facts) and stage == rule["ending_stage"] and planned.get("kind") == "A12":
        return refusal.planned(planned)  # a refused cover is told as such, never as missing cooperation (process/refusal.py)
    if planned.get("kind") == "A5" and planned.get("skip_if") is not True and facts.get("aussichten") == "nicht genügend":
        return {**planned, "form": "A5_aussichtslos", "title": _data()["forms"]["A5_aussichtslos"]["title"]}
    if planned.get("skip_if") is True or not is_ending(planned, stage):
        return planned
    if warned(facts, ledger) is None and facts.get("leistungen_einstellen") is not True:
        others = warning_state(facts, ledger)[0] == "andere"
        reason = (f"vor einer Leistungseinstellung fehlt die schriftliche Aufforderung mit Frist und Androhung der Säumnisfolgen durch {house.active().name}; "
                  "die Akte hat nur eine Aufforderung der Kanzlei (Art. 39 Abs. 2 Ziff. 2 VVG)" if others else
                  "vor einer Leistungseinstellung fehlt in der Akte die schriftliche Aufforderung mit Frist und Androhung der Säumnisfolgen (Art. 39 Abs. 2 Ziff. 2 VVG)")
        return {**rule["demand"], "follow_up": None, "skip_if": None, "demand_for": planned.get("form") or "A12",
                # why this step, for the card's reason line: the step exists because something is missing
                "because": f"schriftliche Aufforderung mit Androhung durch {house.active().name} fehlt (nur durch die Kanzlei)" if others
                else "schriftliche Aufforderung mit Androhung fehlt",
                "reason": f"{planned['reason']}; {reason}" if planned.get("reason") else reason[0].upper() + reason[1:]}
    if planned.get("kind") == "A12" and stage == rule["ending_stage"] and planned.get("form") in (None, "A12") and warned(facts, ledger):
        return {**planned, "form": rule["warned_ending_form"]}
    return planned


# Letters -----------------------------------------------------------------------------------------------------------------

def missing_lines(items, by=None, fallback=True):
    """What is asked of the customer and not delivered, in neutral words from the requests ledger, each with the date it
    was first asked for: ["– Belege der Reparaturkosten (erstmals verlangt am 01.03.2025)"]. Only what the insurer or the
    mandated firm asked (``by``: one of them): a claim or demand of the other side against the customer is never something
    the customer owes us. Without an account, the documents the case still needs. Never a third party's statement about
    the customer: that stays in «Der Fall»."""
    check = next((i for i in items if i["kind"] == "check" and i["key"] == "androhung"), None) or {}
    askers = {by} & set(account.OWED_TO_US) if by else set(account.OWED_TO_US)
    asked = [f"– {r['what']}" + (f" (erstmals verlangt am {day_text(parse_date(r['first']))})" if r.get("first") else "")
             for r in check.get("open_requests") or () if r.get("by") in askers]
    if asked or not fallback:
        return asked
    return [f"– {(i.get('label') or {}).get('de') or i['key']}" for i in items if i["kind"] == "document" and (i.get("ask") == "now" or i.get("required") == "yes")
            and i.get("status") != "present" and not i.get("part_of")]  # at an ending nothing is asked any more: what is required


def letter_context(items):
    """The placeholders the cover forms use: clauses by edition, the gaps only the handler can fill, the demand's date."""
    facts = {i["key"]: i.get("value") for i in items if i["kind"] == "fact"}
    ed = edition(facts)
    check = next((i for i in items if i["kind"] == "check" and i["key"] == "androhung"), None) or {}
    found = (parse_date(check["own_date"]), None) if check.get("own_date") else warned(facts)
    came = (next((i for i in items if i["kind"] == "next_action"), None) or {}).get("incoming") or {}
    firm = came.get("kind") == "mitwirkung"  # the firm's report: only what the ledger shows was asked; else a gap the handler fills
    missing = missing_lines(items, None, fallback=False) if firm else missing_lines(items, account.INSURER)
    asked = [d for n in (1, 4, 6, 7) if (d := parse_date(facts.get(f"handlung_a{n}")))]
    listed = "\n".join(missing) if missing else f"– {gap('was noch fehlt')}"
    if firm:  # the firm's report: what is missing in neutral words, never the firm's own words
        anlass = ("Die von Ihnen beauftragte Kanzlei hat uns mitgeteilt"
                  + (f" (Schreiben vom {day_text(parse_date(came.get('date')))})" if came.get("date") else "")
                  + ", dass für die Bearbeitung Ihres Falles folgende Unterlagen oder Angaben fehlen:\n" + listed)
    else:
        anlass = ((f"Mit Schreiben vom {day_text(max(asked))} haben wir Sie um folgende Unterlagen und Angaben gebeten:" if asked
                   else "Wir haben Sie um folgende Unterlagen und Angaben gebeten:") + "\n" + listed)
    return {
        "avb_ziffer": letter_clause("mitwirkung", ed),
        "avb_mitwirkung": letter_clause("mitwirkung", ed),
        "avb_aussicht": letter_clause("aussicht", ed),
        "avb_schied": letter_clause("schied", ed),
        "avb_anwalt": letter_clause("anwalt", ed),
        "avb_vergleich": letter_clause("vergleich", ed),
        "schiedsfrist": _data()["schiedsfrist"].get(ed) if ed else gap(f"Frist für das Schiedsverfahren gemäss den {house.active().conditions.name_inflected}"),
        "aussicht_gruende": gap("Begründung, weshalb das Vorgehen keine genügende Aussicht auf Erfolg hat"),
        "aussicht_loesung": gap("die vorgeschlagene Erledigung"),
        "androhung_anlass": anlass,
        "androhung_datum": day_text(found[0]) if found and found[0] else gap("Datum der Aufforderung mit Androhung"),
    }


def required_for(kind, facts=None):
    """The required parts of one form as the screen checks them before copying: title, marker, basis in words."""
    ed, words = edition(facts or {}), house.active().conditions
    out = []
    for part in required_parts().get(kind, []):
        basis = []
        for ref in part["basis"]:
            source, _, key = ref.partition("#")
            basis.append(_data()["law"][key]["cite"] if source == "law" else f"{letter_clause(key, ed)} {words.short}" if ed else words.name)
        out.append({"id": part["id"], "title": part["title"], "marker": part["marker"], "basis": "; ".join(basis)})
    return out


def missing_required(text, required):
    """The required parts no longer in a letter's text: copying is refused while any is missing."""
    return [r for r in required or () if r["marker"] not in (text or "")]


def accompanying(kind):
    """The cover forms that go out with an action's letter (the customer's information with a mandate)."""
    return [k for k, f in _data()["forms"].items() if f.get("accompanies") == kind]


# Confirming the passages -------------------------------------------------------------------------------------------------

LINE_WORDS = {"oder", "und", "bzw", "sowie", "bis"}


def normalise(text):
    """One line of words: a structured text's paragraphs ("[tag|path] text") or a PDF's text with its line-end hyphens
    joined ("Rechts-\\n massnahmen" → "Rechtsmassnahmen", but "Melde-\\n oder" stays "Melde- oder"), soft hyphens dropped."""
    if re.search(r"^\s*\[[^\]|]+\|[^\]]*\]", text, re.M):
        text = "\n".join(m.group(1) for m in re.finditer(r"^\s*\[[^\]|]+\|[^\]]*\] ?(.*)$", text, re.M))
    text = re.sub(r"­\s*", "", text)
    text = re.sub(r"(\w)-\n\s*([a-zäöüß]+)", lambda m: f"{m[1]}- {m[2]}" if m[2] in LINE_WORDS else f"{m[1]}{m[2]}", text)
    return " ".join(text.split())


@functools.lru_cache(maxsize=None)
def edition_text(ed):
    return normalise((TEXTS / _data()["editions"][ed]["text"]).read_text(encoding="utf-8"))


def confirm_avb():
    """{clause key: True|False}: each passage found word for word in its edition's stored text."""
    return {key: " ".join(row["passage"].split()) in edition_text(key.split(":", 1)[0]) for key, row in _data()["avb"].items()}


def confirm_law(folder):
    """{law key: True|False} against the saved fedlex HTML in a folder laid out as its index (only the laws found)."""
    from .area import official_articles
    texts = {sr: official_articles(Path(folder) / row["file"]) for sr, row in _data()["laws"].items() if (Path(folder) / row["file"]).is_file()}
    return {key: " ".join(row["passage"].split()) in (texts[row["sr"]].get(row["article"]) or "")
            for key, row in _data()["law"].items() if row["sr"] in texts}


def confirm_public(folder):
    """{key: True|False} for the public pages' passages, against the saved page text."""
    out = {}
    for key, row in _data()["public"].items():
        path = Path(folder) / row["file"]
        if path.is_file():
            out[key] = row["passage"] in " ".join(path.read_text(encoding="utf-8").split())
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m casepath cover", description="check the cover points and their passages")
    parser.add_argument("--sources", help="folder with the saved fedlex HTML and web pages (as in its index.tsv)")
    args = parser.parse_args(argv)
    try:
        d = data()
    except CatalogueError as error:
        sys.exit(f"cover invalid: {error}")
    avb = confirm_avb()
    print(f"{len(d['points'])} Deckungspunkte: " + "; ".join(f"{p['title']} ({p['source']})" for p in d["points"]))
    print(f"{house.active().conditions.name}: {sum(avb.values())} von {len(avb)} Passagen im gespeicherten Text gefunden"
          + (f"; nicht gefunden: {', '.join(k for k, ok in avb.items() if not ok)}" if not all(avb.values()) else ""))
    if args.sources:
        law, public = confirm_law(args.sources), confirm_public(args.sources)
        wrong = [k for k, ok in law.items() if ok != d["law"][k]["verified"]] + [k for k, ok in public.items() if ok != d["public"][k]["verified"]]
        print(f"Gesetz: {sum(law.values())} von {len(law)} Passagen am amtlichen Text gefunden; Webseiten: {sum(public.values())} von {len(public)}"
              + (f"; Kennzeichnung «verified» stimmt nicht bei {', '.join(wrong)}" if wrong else ""))
    else:
        print(f"Gesetz: {sum(r['verified'] for r in d['law'].values())} von {len(d['law'])} Passagen als geprüft gekennzeichnet (--sources prüft sie)")


if __name__ == "__main__":
    main()
