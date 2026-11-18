"""The question back after a partial answer, for live cases.

The customer answered our request in part (account.partial_reply): the letter thanks for what came, by name, and asks
exactly what is still open, each line as it was asked, with the reply date of the backbone's own question back. The
backbone's form thanks for «Ihre Unterlagen» and asks «zu folgendem Punkt», whatever came and however much is open.

The two sentences are data (areas/live/rueckfrage.json, which the frozen study does not load) and review elements
(«backbone:teilantwort.<part>»); they are not reviewed.
"""
import functools
import json

from .. import house

FILE = house.active().catalogue / "live" / "rueckfrage.json"
PREFIX = "teilantwort."


@functools.lru_cache(maxsize=None)
def data():
    return json.loads(FILE.read_text(encoding="utf-8"))


def _day(iso):
    iso = str(iso or "")
    return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}" if len(iso) >= 10 else iso


def form(base, part):
    """The backbone's question-back form with its first two parts replaced: what came, what is open; its last part (the
    reply date) stays. ``part``: account.partial_reply."""
    texts = {p["id"]: p["text"] for p in data()["parts"]}
    received = "; ".join(dict.fromkeys(str(w["what"] if isinstance(w, dict) else w) for w in part.get("received") or ()))
    open_ = "\n".join(f"– {o['what']}" for o in part.get("open") or ())
    parts = [texts["erhalten"].replace("{datum}", _day(part.get("date"))).replace("{erhalten}", received),
             texts["offen"].replace("{offen}", open_)]
    several = len(part.get("open") or ()) > 1
    return {**base, "title": "Rückfrage zu den offenen Punkten" if several else base.get("title"), "parts": parts + list((base.get("parts") or [])[-1:])}


def asks(part, role, respond_by):
    """What the letter asks, as the account's asks of its dispatch: each open request again, as it was asked."""
    return [{"what": o["what"], "of": role, "by": respond_by, **{k: o[k] for k in ("kind", "ref", "key") if o.get(k) is not None}}
            for o in (part or {}).get("open") or ()]


def element_ids():
    return [f"backbone:{PREFIX}{p['id']}" for p in data()["parts"]]
