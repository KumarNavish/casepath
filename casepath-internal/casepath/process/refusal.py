"""The letter that tells the customer cover is refused («Deckungsablehnung»), for live cases.

When the handler refused cover (fact «deckung» = «abgelehnt», with the cover point that is not met), the prepared action
is this letter: what was checked, the decision with the point of the conditions that decides it (its clause in the
edition that applies), the handler's own explanation of the case (a gap only the handler can fill), the offer to look
again at new documents, and the note on running deadlines. The backbone routes a refused cover to the closing for
missing cooperation and prepared the demand with a threat of consequences, which is the wrong letter.

The form's data is areas/live/deckung.json, which the frozen study does not load. Its wording is derived, not reviewed:
each part is a review element («cover:ablehnung.<part>»), and a letter in this form is approved only when a jurist has
marked every part «geprüft» (released()).
"""
import functools
import json
from pathlib import Path

FORM = "A12_deckung"
FILE = Path(__file__).parent / "areas" / "live" / "deckung.json"
PREFIX = "ablehnung."


@functools.lru_cache(maxsize=None)
def data():
    return json.loads(FILE.read_text(encoding="utf-8"))


def applies(facts):
    return (facts or {}).get("deckung") == "abgelehnt"


def planned(action):
    """The prepared action of a refused cover: the closing's kind (A12) in this form, with its own title and reason."""
    d = data()
    return {**(action or {}), "kind": "A12", "form": FORM, "title": d["title"], "follow_up": None, "skip_if": None, "next_in_days": None,
            "reason": "die Deckung ist abgelehnt (Entscheid der Fallbearbeitung)"}


def point_line(facts):
    """The cover point that decides the refusal, in the letter's words: its title and its clause in the edition that
    applies («…» (Ziff. A1.3 der Allgemeinen Bedingungen)); a gap where the handler named no point or «anderer Grund»."""
    from . import cover
    reason = (facts or {}).get("deckung_grund")
    point = next((p for p in cover._data()["points"] if p["id"] == reason), None)
    if point is None:
        return cover.gap("der Punkt der Allgemeinen Bedingungen, der nicht erfüllt ist")
    ed = cover.edition(facts or {})
    rows = cover.clauses(point.get("clauses") or {}, ed) if ed else []
    cite = f" ({cover.cite_list(rows)} der Allgemeinen Bedingungen)" if rows else " (Allgemeine Bedingungen)"
    return f"«{point['title']}»{cite}"


def form(facts):
    """The form as letters.render takes it: {title, to, parts}, the point and the explanation filled or left as gaps."""
    from . import cover
    d = data()
    fill = {"{deckung_punkt}": point_line(facts), "{deckung_begruendung}": cover.gap("weshalb dieser Punkt in diesem Fall nicht erfüllt ist")}
    parts = []
    for p in d["parts"]:
        text = p["text"]
        for key, value in fill.items():
            text = text.replace(key, value)
        parts.append(text)
    return {"title": d["title"], "to": d["to"], "parts": parts}


def element_ids():
    """The review elements a letter in this form rests on, as «<file>:<element>» (process/review.py)."""
    return [f"cover:{PREFIX}{p['id']}" for p in data()["parts"]]


def unreleased(marks):
    """The parts of the form no jurist has marked «geprüft» (``marks``: review.Model.current): [{key, title}]. A letter
    in this form is not approved while any is left."""
    titles = {f"cover:{PREFIX}{p['id']}": p["title"] for p in data()["parts"]}
    return [{"key": k, "title": f"Deckungsablehnung: {titles[k]}"} for k in element_ids() if ((marks or {}).get(k) or {}).get("mark") != "geprueft"]
