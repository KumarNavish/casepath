"""Letters for steps the process leaves without a form («Kein Entwurf»), where what they say stands without a new
judgment, for live cases.

The backbone names such a step and says the handler writes the letter if one is wanted. Where the content is settled by
the case's state alone (a matter the file shows as done is closed with a short letter), the letter is prepared like any
other; ``optional`` says the step may also end without it («Erledigt»). The forms are data (areas/live/formulare.json,
which the frozen study does not load) and review elements («backbone:live.<form>.<part>»); they are not reviewed.
"""
import functools
import json
from pathlib import Path

FILE = Path(__file__).parent / "areas" / "live" / "formulare.json"
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
