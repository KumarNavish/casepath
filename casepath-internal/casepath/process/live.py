"""Letters for steps the process leaves without a form («Kein Entwurf»), where what they say stands without a new
judgment, for live cases.

The backbone names such a step and says the handler writes the letter if one is wanted. Where the content is settled by
the case's state alone (a matter the file shows as done is closed with a short letter), the letter is prepared like any
other; ``optional`` says the step may also end without it («Erledigt»). The forms are data (areas/live/formulare.json,
which the frozen study does not load) and review elements («backbone:live.<form>.<part>»); they are not reviewed.
"""
import functools
import json
import re

from .. import house

FILE = house.active().catalogue / "live" / "formulare.json"
PREFIX = "live."


@functools.lru_cache(maxsize=None)
def _data():
    return json.loads(FILE.read_text(encoding="utf-8"))


def forms():
    return _data()["forms"]


def form(kind, base):
    """The process's form of ``kind`` with the live parts in place of «Kein Entwurf»; ``base`` unchanged where the
    process has a text of its own or no live form exists."""
    own = forms().get(kind)
    if not own or not (base or {}).get("none") or (base or {}).get("parts"):
        return base
    return {**{k: v for k, v in base.items() if k != "none"}, "to": own["to"], "parts": [p["text"] for p in own["parts"]],
            **({"optional": True} if own.get("optional") else {})}


def element_ids(kind):
    return [f"backbone:{PREFIX}{kind}.{p['id']}" for p in (forms().get(kind) or {}).get("parts") or ()]


# -- one question, then the letter: the answer to an offer of the other side ----------------------------------------------
# The backbone leaves «Antwort auf das Angebot» to the handler («Kein Entwurf»). The judgment is one of three answers; once
# it is given («offer.stance», attributed, per offer) the letter to the other side is prepared like any other.

def stances():
    return _data()["stances"]


def stance_of(events, incoming):
    """The handler's answer to the open offer ``incoming`` (the next action's): the latest «offer.stance» given for the
    offer of that day ({id, by, at}), or None; an empty one takes the answer back."""
    if (incoming or {}).get("kind") != "angebot":
        return None
    found = None
    for e in events or ():
        if e.get("kind") == "offer.stance" and e.get("offer") == incoming.get("date"):
            found = {"id": e.get("stance"), "by": e.get("expert"), "at": e.get("at")} if e.get("stance") else None
    return found


def stance_question(incoming, chosen=None):
    """The one question of an open offer, as the card asks it: {key, question, answers [{label, stance, then}], chosen}."""
    own = stances()["angebot"]
    return {"key": "angebot", "question": own["question"], "chosen": (chosen or {}).get("id"), "offer": (incoming or {}).get("date"),
            "answers": [{"label": a["label"], "stance": a["id"], "then": a["then"]} for a in own["answers"]]}


def call_sheet(incoming):
    """What the handler has in front of them for the call about an offer: the offer in the file's words and the questions
    the answer to the other side depends on (data: stances.angebot.call). None for anything but an offer."""
    if (incoming or {}).get("kind") != "angebot":
        return None
    offer = re.sub(r"\b(\d{4})-(\d{2})-(\d{2})\b", r"\3.\2.\1", str(incoming.get("value") or ""))
    return {"offer": offer, "questions": list(stances()["angebot"].get("call") or ())}


def stance_form(base, chosen, incoming):
    """The form of the answer chosen, in place of «Kein Entwurf»: its parts with the offer's day; ``base`` when none is."""
    answer = next((a for a in stances()["angebot"]["answers"] if a["id"] == (chosen or {}).get("id")), None)
    if not answer:
        return base
    own = forms()[answer["letter"]]
    day = str((incoming or {}).get("date") or "")
    named = f"{day[8:10]}.{day[5:7]}.{day[:4]}" if len(day) == 10 else "[bitte ergänzen: Datum des Angebots]"
    return {**{k: v for k, v in (base or {}).items() if k != "none"}, "title": own["title"], "to": own["to"], "anrede": own.get("anrede"),
            "parts": [p["text"].replace("{angebot_vom}", named) for p in own["parts"]], "live": answer["letter"]}


# -- what a customer's question asks, named by the reader (the trial «reader_intents») ------------------------------------
# The area matches a question's intent by word stems (options.intent). On real wording the stems miss: a question tagged
# with a key point then waits as «Absicht unklar». Under the trial the reader names the intent by its meaning, as it names
# the key points; code keeps every guard (the intent must belong to a key point the question is tagged with, a negation or
# a failing point still holds it).

INTENTS = house.active().catalogue / "live" / "absichten.json"
NO_INTENT = "none"


@functools.lru_cache(maxsize=None)
def _intents():
    return json.loads(INTENTS.read_text(encoding="utf-8"))["areas"]


def intents(area_id, answers):
    """Per key point the intents a question about it may ask: {point id: [{intent, meaning}]}, for the answer rows of the
    area that have a meaning written (``answers``: the options file's rows); {} for an area without."""
    meanings = _intents().get(area_id) or {}
    out = {}
    for a in answers or ():
        if a.get("intent") in meanings:
            for point in a.get("points") or ():
                out.setdefault(point, []).append({"intent": a["intent"], "meaning": meanings[a["intent"]]})
    return out


def named_intent(question, rows):
    """The answer row the reader named for a question (``question['intent']``), among the rows of its key points; None
    when it named none, or one that belongs to none of them."""
    given = (question or {}).get("intent")
    return next((r for r in rows or () if given and r.get("intent") == given), None)
