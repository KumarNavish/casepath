"""The house: the insurer whose case handlers CasePath works for, named in one place.

A house profile (format ``casepath.house/1``, one JSON file) holds what belongs to one insurer and to no other: its
name as letters and the running account write it, its legal name, the words by which a file's sender line shows it,
how its claim numbers look, how it names its policy conditions and where the cover points with their clauses live,
the language and the lines its letters use, and where its workflow catalogue and its seeded knowledge are. What is the
same for every Swiss legal-protection insurer (the law, the handler's journey) is not in a profile; docs/HOUSE.md says
which is which.

``CASEPATH_HOUSE`` names a profile shipped in this folder (``protekta``, the default: nothing needs to be set) or is the
path of a profile file. It is read once per process, at first use, and every module asks ``active()``; a profile that
is incomplete is refused there, before anything is rendered. Paths in a profile are relative to the profile file.

Shipped data (the areas, the cover points, the seeded knowledge, the translation memory) names the built-in house. It
is left as it is on disk; ``in_own_name`` is how another house reads it.
"""
from __future__ import annotations

from dataclasses import dataclass
import functools
import json
import os
from pathlib import Path
import re

FORMAT = "casepath.house/1"
SHIPPED = Path(__file__).parent  # the profiles that come with CasePath, one file per house id
BUILT_IN = "protekta"  # the house CasePath serves when nothing is configured
VARIABLE = "CASEPATH_HOUSE"


class HouseError(ValueError):
    pass


@dataclass(frozen=True)
class Conditions:
    """The house's policy conditions: how texts name them and where the cover check reads them."""
    short: str  # after a clause: «Art. M Ziff. 1 AVB»
    name: str  # standing alone: «Allgemeine Bedingungen»
    name_inflected: str  # after «der» and «den»: «Ziffer der Allgemeinen Bedingungen», «gemäss den Allgemeinen Bedingungen»
    cover: Path  # the cover points with the clause of each edition (format casepath.cover/1)
    texts: Path  # the stored text of each edition, against which the quoted passages are confirmed


@dataclass(frozen=True)
class Writing:
    """The language the agents write in, as their instructions say it."""
    case_work: str  # everything a handler reads
    photos: str  # the description of a photo


@dataclass(frozen=True)
class Letters:
    """The lines a letter built by code opens and closes with (a form of the catalogue carries its own closing)."""
    greeting: str  # when the file names no person
    greeting_ms: str  # «{name}»: the family name, when the file states «Frau»
    greeting_mr: str  # «{name}»: the family name, when the file states «Herr»
    greeting_by_name: str  # «{name}»: the full name, when the file states no salutation
    closing: str


@dataclass(frozen=True)
class Profile:
    id: str
    name: str  # as letters, the running account and the screens write it
    legal_name: str
    recognised_by: tuple  # lower-case words that show this insurer in a file's sender or recipient line
    claim_number: str  # a regular expression: how a claim number looks in a title or a file
    conditions: Conditions
    writing: Writing
    letters: Letters
    catalogue: Path  # the backbone, the areas, the options and the live forms
    knowledge_seed: Path  # the knowledge a fresh deployment starts with

    def named_in(self, *more):
        """A pattern (as text) that finds this insurer in a sender line: its words, then any further alternatives."""
        return "|".join([re.escape(w) for w in self.recognised_by] + list(more))

    def for_the_page(self):
        """What the page needs where its own texts name the insurer or its policy conditions."""
        return {"id": self.id, "name": self.name, "legal_name": self.legal_name,
                "conditions": {"short": self.conditions.short, "name_inflected": self.conditions.name_inflected}}


FIELDS = {"format": str, "id": str, "name": str, "legal_name": str, "recognised_by": list, "claim_number": str,
          "conditions": {"short": str, "name": str, "name_inflected": str, "cover": str, "texts": str},
          "writing": {"case_work": str, "photos": str},
          "letters": {"greeting": str, "greeting_ms": str, "greeting_mr": str, "greeting_by_name": str, "closing": str},
          "catalogue": str, "knowledge_seed": str}


def _checked(data, fields, path, where=""):
    """Every field there, of its kind and not empty; no field this build does not know. Fails closed, naming the field."""
    if not isinstance(data, dict):
        raise HouseError(f"house profile {path}: {where or 'the profile'} must be an object")
    for key, kind in fields.items():
        name = f"{where}{key}"
        if key not in data:
            raise HouseError(f"house profile {path}: the required field «{name}» is missing")
        if isinstance(kind, dict):
            _checked(data[key], kind, path, f"{name}.")
        elif not isinstance(data[key], kind) or not data[key]:
            raise HouseError(f"house profile {path}: «{name}» must be a non-empty {'list' if kind is list else 'text'}")
    unknown = sorted(set(data) - set(fields))
    if unknown:
        raise HouseError(f"house profile {path}: unknown field «{where}{unknown[0]}»")
    return data


def load(source):
    """The profile a name or a path stands for, checked: a shipped house by its id, or a profile file."""
    path = SHIPPED / f"{source}.json" if re.fullmatch(r"[a-z0-9-]+", str(source)) else Path(os.path.abspath(source))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        shipped = ", ".join(sorted(p.stem for p in SHIPPED.glob("*.json")))
        raise HouseError(f"house profile {path}: no such file ({VARIABLE} is a shipped house: {shipped}; or the path of a profile)") from None
    except json.JSONDecodeError as error:
        raise HouseError(f"house profile {path}: not valid JSON ({error})") from None
    _checked(data, FIELDS, path)
    if data["format"] != FORMAT:
        raise HouseError(f"house profile {path}: «format» must be {FORMAT}")
    words = data["recognised_by"]
    if not all(isinstance(w, str) and w and w == w.lower() for w in words):
        raise HouseError(f"house profile {path}: «recognised_by» holds lower-case words")
    try:
        re.compile(data["claim_number"])
    except re.error as error:
        raise HouseError(f"house profile {path}: «claim_number» is not a regular expression ({error})") from None
    for key in ("greeting_ms", "greeting_mr", "greeting_by_name"):
        if "{name}" not in data["letters"][key]:
            raise HouseError(f"house profile {path}: «letters.{key}» must hold {{name}}")
    here = lambda value: Path(os.path.normpath(path.parent / value))
    conditions = Conditions(**{**data["conditions"], "cover": here(data["conditions"]["cover"]), "texts": here(data["conditions"]["texts"])})
    catalogue, seed = here(data["catalogue"]), here(data["knowledge_seed"])
    # the stored texts of the conditions are only read to confirm passages, so they may be absent where CasePath runs
    for name, place, found in (("catalogue", catalogue, catalogue.is_dir()), ("knowledge_seed", seed, seed.is_dir()),
                               ("conditions.cover", conditions.cover, conditions.cover.is_file())):
        if not found:
            raise HouseError(f"house profile {path}: «{name}» points to {place}, which is not there")
    return Profile(id=data["id"], name=data["name"], legal_name=data["legal_name"], recognised_by=tuple(words),
                   claim_number=data["claim_number"], conditions=conditions, writing=Writing(**data["writing"]),
                   letters=Letters(**data["letters"]), catalogue=catalogue, knowledge_seed=seed)


@functools.lru_cache(maxsize=None)
def built_in():
    """The house the shipped data is written for."""
    return load(BUILT_IN)


@functools.lru_cache(maxsize=None)
def active():
    """The house this process works for: read once, the built-in one unless CASEPATH_HOUSE says otherwise."""
    chosen = (os.environ.get(VARIABLE) or "").strip()
    return built_in() if chosen in ("", BUILT_IN) else load(chosen)


def in_own_name(data):
    """Shipped data as the active house reads it: where a text names the built-in house, it names this one, and the
    built-in house's sender words become this house's. Texts, lists and objects alike, keys included. For the built-in
    house the data comes back as it is, untouched."""
    own, shipped = active(), built_in()
    if own is shipped:
        return data

    def renamed(value):
        if isinstance(value, str):
            return value.replace(shipped.name, own.name)
        if isinstance(value, list):
            return list(own.recognised_by) if value == list(shipped.recognised_by) else [renamed(v) for v in value]
        if isinstance(value, dict):
            return {renamed(k): renamed(v) for k, v in value.items()}
        return value
    return renamed(data)
