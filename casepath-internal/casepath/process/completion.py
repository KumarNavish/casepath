"""What carries the handler's decision on a prepared letter through, and where it stands. Model-free.

- The action version (``version_of``): a hash of the form, its recipients, the final text by part, the enclosures and the
  reply date. «Freigeben» approves exactly that version; the approval holds only while the version, the form, its
  premise, the decisions, the required parts and the files read are as approved (``validity``, recomputed on every read).
- The handler's own text is kept per part of the letter (``merge``): a part the handler did not edit takes the new base, an
  edited part whose base did not change keeps the edit, a part changed on both sides (or gone while edited) is a conflict
  the handler resolves; no paragraph position is ever used.
- «Versandt am» is the handler's attributed confirmation of the external sending, per recipient (``FORM_RECORD``: the
  record kind and code of its form, written into the account by account.dispatch_entries), with what it asked (``asks``)
  and the questions it answered (``answers``); nothing else ever counts as sent.
- After the dispatch, acknowledgement and fulfilment come from evidence only (``fulfilment``): a receipt located in a file
  of a later reply of the addressee, a document such a file holds (account.held), a fact quoted from it; a refusal, a
  promise or a row closed by words fulfils nothing.
- A copy (``letter.copied``) is measurement; a copy from a browser before this release (no ``measure``) counts only as
  contact, never as sent, fulfilled or settled (``legacy_copy``, ``contacted``).
"""
import hashlib
import json
import re
from datetime import date, timedelta

from .. import house
from . import cover, letters
from .account import INSURER, PARTIES, PARTY_TITLES, _head
from .clock import parse_date

# The dispatch of each form as the account records it: (recipient, record kind, code). A form variant takes its kind's row
# (A12_still → A12, A6_androhung → A6), any other form goes to the customer as «andere» without a code. A dispatch never
# carries code 11 (it would answer a cost claim) and never its kind's code: an «anforderung» to the other side is no A8.
FORM_RECORD = {
    "A1": ("kunde", "anforderung", "1"),
    "A4": ("kunde", "anforderung", "4"),
    "A5": ("kunde", "einschaetzung", "5"),
    "A6": ("kunde", "abschlussankuendigung", "6"),
    "A7": ("kunde", "abschlussankuendigung", "7"),
    "A8": ("gegenpartei", "schreiben_gegenpartei", "8"),
    "A9": ("gegenpartei", "schreiben_gegenpartei", "9"),
    "A10": ("kanzlei", "mandat", "10"),
    "A10_kunde": ("kunde", "andere", None),
    "A11_iban": ("kunde", "anforderung", None),
    "A11_auszahlung": ("gegenpartei", "andere", None),
    "A11_eingang": ("kunde", "andere", None),
    "A11_nachfragen": ("payer", "anforderung", None),
    "A11_rueckfrage": ("kanzlei", "antwort", None),
    "A11_teilablehnung": ("kanzlei", "antwort", None),
    "A12": ("kunde", "abschluss", "12"),
    "A13": ("kunde", "andere", "13"),
}
FOLDERS = {"kunde": "Kundschaft", "gegenpartei": "Gegenpartei", "kanzlei": "Kanzlei", "behoerde": "Behörde", "andere": "Andere"}
CHANNELS = {"post": "Post", "email": "E-Mail", "portal": "Portal", "andere": "andere"}
TO_WORDS = {"kunde": "die Kundschaft", "gegenpartei": "die Gegenpartei", "kanzlei": "die Kanzlei", "behoerde": "die Behörde", "andere": "Dritte"}
DECISION_WORDS = {"deckung": "Deckung", "empfehlung": "Empfehlung", "aussichten": "Erfolgsaussichten", "vorgehen": "Vorgehen"}
DECISION_FACTS = {"deckung", "aussichten", "vorgehen", "leistungen_einstellen", "vergleich_bestaetigt"}  # the handler's own decisions
# the reasons an approval no longer holds, the cause before its consequences
REASONS = ("Entscheid geändert", "Voraussetzung geändert", "Grundlage in Prüfung", "Regel geändert", "Neue Unterlagen", "Pflichtteil fehlt", "Schritt geändert",
           "Empfänger geändert", "Beilagen geändert", "Datum", "Text geändert")
HELD_MARKS = {"aenderung": "Änderung nötig", "frage": "Frage"}  # a jurist's mark that holds an element the letter rests on
COVER, BACKBONE = "cover", "backbone"  # the review's files besides the area modules (process/review.py)
REPLY = "Rückmeldung"
SHA_EMPTY = hashlib.sha256(b"").hexdigest()


def sha(text):
    return hashlib.sha256(str(text or "").encode()).hexdigest()


def swiss_day(at):
    """The Swiss day of a stored time (UTC, ISO), as YYYY-MM-DD: an approval at 23:30 UTC was given on the next day in
    Switzerland; the stored day where the zone data is missing or the value is a day already."""
    from datetime import datetime
    text = str(at or "")
    if len(text) <= 10:
        return text
    try:
        from zoneinfo import ZoneInfo
        return datetime.fromisoformat(text).astimezone(ZoneInfo("Europe/Zurich")).date().isoformat()
    except Exception:  # noqa: BLE001  no zone data, or no time in it
        return text[:10]


def swiss_today():
    """Today in Swiss time (the handler's day: a letter sent at 00:30 is sent «today» there, while the server's clock in
    UTC still says yesterday); the server's day where the zone data is missing."""
    from datetime import datetime, timezone
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(timezone.utc).astimezone(ZoneInfo("Europe/Zurich")).date()
    except Exception:  # noqa: BLE001  no zone data: the server's day
        return date.today()


FOLLOW_ON = "A5_nachtrag"  # options.FOLLOW_ON: the short letter that follows an assessment when what it asked came


def record_of(form):
    """(recipient, record kind, code) of a dispatch of ``form`` (FORM_RECORD)."""
    form = str(form or "")
    if form in FORM_RECORD:
        return FORM_RECORD[form]
    kind = re.match(r"A\d{1,2}", form)
    return FORM_RECORD.get(kind.group(0) if kind else "", ("kunde", "andere", None))


# -- recipients, the handler's text per part, the version -----------------------------------------------------------------

def _party_name(listed, role):
    parties = [i for i in listed or () if i.get("kind") == "party" and str(i.get("value") or "").strip()]
    label = lambda p: str((p.get("label") or {}).get("de") if isinstance(p.get("label"), dict) else p.get("label") or "").lower()
    redacted = lambda v: bool(re.search(r"geschw|xxx", str(v), re.I))
    if role == "kunde":
        own = letters.customer(parties)
        return (own or {}).get("value") if own and not redacted(own.get("value")) else None
    if role == "kanzlei":
        firm = next((p for p in parties if re.search(r"kanzlei|anwalt|anwält|advokatur", f"{label(p)} {p['value']}", re.I)), None)
        return (firm or {}).get("value")
    if role == "gegenpartei":
        fact = next((i.get("value") for i in listed or () if i.get("kind") == "fact" and i.get("key") == "gegenpartei" and i.get("value")), None)
        own = letters.customer(parties)
        other = next((p for p in parties if p is not own and not re.search("kanzlei|anwalt|versicher|" + house.active().named_in(), f"{label(p)} {p['value']}", re.I)), None)
        return fact or (other or {}).get("value")
    return None


def role_of(form, listed=()):
    """The party a form's letter goes to; «payer» (the chase of a payment) is the party that owes it."""
    role = record_of(form)[0]
    if role == "payer":
        owed = next((i.get("owed") for i in listed or () if i.get("kind") == "next_action" and i.get("owed")), None) or {}
        role = owed.get("payer") if owed.get("payer") in PARTIES and owed.get("payer") != INSURER else "gegenpartei"
    return role


def recipient_line(role, listed):
    """The recipient as the version names it: the greeting line and the name the file states («Name nicht in der Akte»)."""
    parties = [i for i in listed or () if i.get("kind") == "party"]
    greeting = letters.greeting(parties) if role == "kunde" else house.active().letters.greeting
    return f"{greeting} · {_party_name(listed, role) or 'Name nicht in der Akte'}"


def recipients(draft, listed=()):
    """Who the prepared letter goes to, the letter's recipient first: [{to, recipient, title, forms}]; an enclosure goes to
    its own form's recipient, a template for the customer's own letter with the letter."""
    if not draft or not draft.get("text"):
        return []
    main = draft.get("form") or draft.get("kind")
    first = role_of(main, listed)
    rows = {}

    def add(role, kind, title):
        row = rows.setdefault(role, {"to": role, "recipient": recipient_line(role, listed), "title": FOLDERS.get(role, PARTY_TITLES.get(role, role)),
                                     "forms": [], "titles": {}})
        row["forms"].append(kind)
        row["titles"][kind] = title
    add(first, main, draft.get("title"))
    for a in draft.get("also") or ():
        if a.get("text"):
            add(first if a.get("template") else role_of(a["kind"], listed), a["kind"], a.get("name") or a.get("title"))
    return list(rows.values())


def _order(part):
    if part == "head":
        return (0, 0)
    if part == "tail":
        return (2, 0)
    m = re.fullmatch(r"p(\d+)", str(part))
    return (1, int(m.group(1))) if m else (1, 0)


def merge(base_parts, saved=None):
    """The text of one letter or enclosure as the handler left it, by part id (never by position): (parts, conflicts).
    ``base_parts``: [(part, text)] as rendered now; ``saved``: the form's latest save (store.latest_drafts). A part the
    handler did not edit takes the new base; an edited part whose base did not change keeps the edit; a part changed on
    both sides, or gone while edited, is a conflict {part, mine, new, before} and shows the new text until resolved."""
    rows = (saved or {}).get("parts") or {}
    meta = lambda r: {k: r.get(k) for k in ("id", "by", "at")} if r else None
    parts, conflicts, present = [], [], set()
    for part, text in base_parts or ():
        present.add(part)
        digest, row = sha(text), rows.get(part)
        if not row or row["text"] == row["base"] or row["text"] == text:
            parts.append({"part": part, "text": text, "base": text, "base_sha256": digest, "edited": False, "saved": meta(row)})
        elif row["base_sha256"] == digest:
            parts.append({"part": part, "text": row["text"], "base": text, "base_sha256": digest, "edited": True, "saved": meta(row)})
        else:
            conflicts.append({"part": part, "mine": row["text"], "new": text, "before": row["base"], "saved": meta(row)})
            parts.append({"part": part, "text": text, "base": text, "base_sha256": digest, "edited": False, "saved": meta(row), "conflict": True})
    for part, row in rows.items():
        if part in present or not str(row["text"]).strip() or row["text"] == row["base"]:
            continue
        if row["base_sha256"] == SHA_EMPTY:  # kept by the handler after its part went: it stands where its id puts it
            parts.append({"part": part, "text": row["text"], "base": "", "base_sha256": SHA_EMPTY, "edited": True, "saved": meta(row)})
        else:
            conflicts.append({"part": part, "mine": row["text"], "new": "", "before": row["base"], "saved": meta(row), "gone": True})
    parts.sort(key=lambda p: _order(p["part"]))
    return parts, conflicts


def joined(parts):
    """A letter's text from its merged parts (letters.join_parts); a template is its one part as it is."""
    if len(parts) == 1 and parts[0]["part"] == "text":
        return parts[0]["text"]
    return letters.join_parts([(p["part"], p["text"]) for p in parts if str(p["text"]).strip() or p["part"] in ("head", "tail")])


def line_parts(parts):
    """The part each line of ``joined(parts)`` comes from (None for the empty line between two parts), so the browser
    maps an edit of the letter back to its part: [part id or None], one per line of the joined text."""
    if len(parts) == 1 and parts[0]["part"] == "text":
        return ["text"] * len(str(parts[0]["text"]).split("\n"))
    lines = []
    for p in parts:
        if not (str(p["text"]).strip() or p["part"] in ("head", "tail")):
            continue
        own = [(line, p["part"]) for line in str(p["text"]).split("\n")]
        lines += own if p["part"] in ("head", "tail") else own + [("", None)]
    while lines and not lines[0][0].strip():  # as join_parts' strip(): no empty line at either end
        lines.pop(0)
    while lines and not lines[-1][0].strip():
        lines.pop()
    return [part for _, part in lines]


def version_of(form, recipients_, parts, also, respond_by):
    """The action version: the form, its recipients (role and line), the final text by part, the enclosures (forms and
    templates, by their text's SHA-256) and the reply date. Run ids and the files' digest are not part of it."""
    payload = {"form": form, "recipients": [[r["to"], r["recipient"]] for r in recipients_],
               "parts": [[p["part"], p["text"]] for p in parts],
               "also": sorted([a["kind"], sha(a["text"])] for a in also if not a.get("template")),
               "attachments": sorted([a["kind"], sha(a["text"])] for a in also if a.get("template")),
               "respond_by": respond_by}
    return sha(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def prepare(draft, saved=None, listed=()):
    """The prepared letter as the handler left it, in place: each part (and each enclosure) merged with the handler's
    saved text; ``text``, ``parts``, ``conflicts``, ``saved`` (who saved each part), ``draft_id`` (the latest save, the
    parent of the next), ``recipients`` and ``version``. Returns ``draft``."""
    if not draft or ("parts" in draft and "base_parts" not in draft):  # nothing to prepare, or prepared already
        return draft
    saved = saved or {}
    form = draft.get("form") or draft.get("kind")
    parts, conflicts = merge(draft.get("base_parts") or [], saved.get(form)) if draft.get("text") is not None else ([], [])
    draft.update(parts=parts, conflicts=conflicts, draft_id=(saved.get(form) or {}).get("id"),
                 saved={p["part"]: p["saved"] for p in parts if p.get("saved")})
    if parts:
        draft["text"] = joined(parts)
        draft["line_parts"] = line_parts(parts)
    for a in draft.get("also") or ():
        if a.get("text") is None:
            continue
        a_parts, a_conflicts = merge(a.get("base_parts") or [("text", a["text"])], saved.get(a["kind"]))
        a.update(parts=a_parts, conflicts=a_conflicts, draft_id=(saved.get(a["kind"]) or {}).get("id"), text=joined(a_parts) if a_parts else a["text"],
                 line_parts=line_parts(a_parts) if a_parts else None)
    draft["recipients"] = recipients(draft, listed)
    also = [a for a in draft.get("also") or () if a.get("text")]
    draft["version"] = version_of(form, draft["recipients"], parts, also, draft.get("respond_by")) if draft.get("text") else None
    draft.pop("base_parts", None)  # the parts carry their base now
    for a in draft.get("also") or ():
        a.pop("base_parts", None)
    return draft


def all_conflicts(draft):
    return list((draft or {}).get("conflicts") or []) + [c for a in (draft or {}).get("also") or () for c in a.get("conflicts") or []]


def gaps(draft):
    """The handler's gaps still in the letter and its enclosures."""
    texts = [(draft or {}).get("text") or ""] + [a.get("text") or "" for a in (draft or {}).get("also") or ()]
    return sum(t.count(letters.GAP) for t in texts)


def missing_required(draft):
    """The parts the law or the conditions require that the letter or an enclosure no longer holds."""
    out = cover.missing_required((draft or {}).get("text"), (draft or {}).get("required"))
    for a in (draft or {}).get("also") or ():
        if a.get("text"):
            out += cover.missing_required(a["text"], a.get("required"))
    return out


# -- the decisions the letter rests on --------------------------------------------------------------------------------------

def _answered(facts, fact):
    value = (facts or {}).get(fact)
    return None if value in (None, "", "offen") else value


def _norm(value):
    if isinstance(value, str) and value.strip().lower() in {"ja", "true", "yes"}:
        return True
    if isinstance(value, str) and value.strip().lower() in {"nein", "false", "no"}:
        return False
    return None if value in ("", "offen") else value


def open_decisions(draft, facts, assessment=None, process=None):
    """The decisions still to make before the letter can be approved, in the handler's words: each of the form's needs
    not answered, the prospects for an assessment (in every area), and the assessment's blocking decisions. Where the
    assessment lists its decisions, in its order, the order the card asks them (the cover while the A5 rests on it, the
    recommendation, the prospects), so the queue and the head name the decision the card shows next."""
    defined = {f["id"] for f in (process or {}).get("facts") or ()} if process else None
    out = []
    for fact in (draft or {}).get("needs") or ():
        if (defined is None or fact in defined) and _answered(facts, fact) is None:
            out.append(DECISION_WORDS.get(fact, fact))
    if str((draft or {}).get("kind") or "") == "A5" and str((draft or {}).get("form") or "").startswith("A5") and _answered(facts, "aussichten") is None:
        out.append("Erfolgsaussichten")
    order = [DECISION_WORDS.get(b.get("key"), b.get("text") or b.get("key")) for b in (assessment or {}).get("blocking") or () if b.get("kind") == "decision"]
    out = list(dict.fromkeys(out + order))
    return [w for w in dict.fromkeys(order) if w in out] + [w for w in out if w not in order]


DECIDED_WORDS = {"bestätigt": "bestätigt", "abgelehnt": "abgelehnt", True: "ja", False: "nein", "ja": "ja", "nein": "nein"}


def decided(draft, facts, assessment=None, edits=(), process=None):
    """The decisions of this step the handler already took, in the order the card asks them: each with its answer, who
    gave it and when, and the edit that carries it (undoing that edit asks the decision again). Only the handler's own
    decisions (a set_fact in force on one of the step's decisions; the recommendation adopted): what a stage settles by
    itself is no row. With ``open_decisions`` this is the whole set, so the card can show all of it at once."""
    draft = draft or {}
    defined = {f["id"] for f in (process or {}).get("facts") or ()} if process else None
    keys = [f for f in draft.get("needs") or () if defined is None or f in defined]
    if str(draft.get("kind") or "") == "A5" and str(draft.get("form") or "").startswith("A5"):
        keys = ["deckung"] + [k for k in keys if k != "deckung"] + ["aussichten"]
    own = {}
    for e in edits or ():  # the latest set_fact in force per fact
        if e.get("op") == "set_fact" and (e.get("status") or "active") == "active" and (e.get("args") or {}).get("fact"):
            own[e["args"]["fact"]] = e
    rows = []
    for key in dict.fromkeys(keys):
        value, edit = _answered(facts, key), own.get(key)
        if value is None or edit is None or key not in DECISION_FACTS:
            continue
        said = DECIDED_WORDS.get(value, str(value))
        rows.append({"key": key, "word": DECISION_WORDS.get(key, key), "value": said, "edit": edit.get("id"), "by": edit.get("by"), "at": edit.get("at")})
    adopted = (assessment or {}).get("adopted")
    if adopted and adopted.get("valid") and (assessment or {}).get("assessment"):  # a decision of the assessment's own step only
        at = next((n for n, r in enumerate(rows) if r["key"] == "aussichten"), len(rows))  # the card asks it before the prospects
        rows.insert(at, {"key": "empfehlung", "word": "Empfehlung", "value": "übernommen", "by": adopted.get("by"), "at": adopted.get("at")})
    return rows


def facts_read(facts, process=None):
    """The case's facts as the assessment reads them: with the area's implications applied where slice A's options file
    gives them («schriftlich gemeldet» ⇒ «gemeldet», options.implied); the case's facts as they are without it. The same
    reading at the approval and on every later read, whichever step the plan is at by then."""
    facts = dict(facts or {})
    try:
        from . import options  # slice A's
    except ImportError:
        return facts
    data = options.load((process or {}).get("id")) if (process or {}).get("id") else None
    return options.implied(facts, data) if data else facts


def _premise_value(fact, read, assessment=None):
    """A fact the letter rests on, as it reads now (``read``: facts_read), else as the assessment's premise gives it."""
    return _norm(read[fact] if fact in read else ((assessment or {}).get("premise") or {}).get(fact))


def premise(draft, facts, assessment=None, process=None):
    """What the letter rests on, as it stands now: the assessment's premise and each decision the form needs (and the
    prospects for an assessment), {fact: value}."""
    read = facts_read(facts, process)
    out = {k: _premise_value(k, read, assessment) for k in (assessment or {}).get("premise") or {}}
    for fact in list((draft or {}).get("needs") or ()) + (["aussichten"] if str((draft or {}).get("kind") or "") == "A5" else []):
        out[fact] = _premise_value(fact, read, assessment)
    return out


def changed_premise(stored, facts, assessment=None, process=None):
    """The facts of a stored premise whose value is no longer the same: [fact], each read now as ``premise`` read it when
    it was stored."""
    read = facts_read(facts, process)
    return [k for k, v in (stored or {}).items() if _norm(v) != _premise_value(k, read, assessment)]


def relied_elements(draft, assessment=None, process=None, listed=(), events=()):
    """The reviewed legal content the letter rests on, as the jurists' review names it («<file>:<element>»,
    process/review.py): the assessment frame its form uses (rahmen.<key>), the documents and questions it asks
    (unterlage.<id>, frage.<fact>), the templates it encloses (vorlage.<id>), the required parts it carries
    (cover:schreiben.<form>.<part>), and for an assessment the options adopted, the answers given, the case lines and the
    connecting wording it states (empfehlung.<id>, antwort.<point>.<intent>, fall.<id>, wortlaut.<key>). The assessment's
    own list (``assessment['elements']``) is taken as it is where it gives one. A mark «Änderung nötig» or «Frage» on one
    of them after the approval makes the approval stale, even when the letter's bytes stay the same."""
    if not draft or not draft.get("text"):
        return []
    wid = (process or {}).get("id")
    a = assessment or {}
    out = []

    def own(element):
        if wid and element:
            out.append(f"{wid}:{element}")
    form = draft.get("form") or draft.get("kind")
    for part in _frame_parts(form):  # the area's assessment frame the backbone's form takes («@rights»), as composed into it
        own(f"rahmen.{part}")
    for r in draft.get("required") or ():
        out.append(f"{COVER}:schreiben.{form}.{r.get('id')}")
    for x in draft.get("also") or ():
        if not x.get("text"):
            continue
        if x.get("template"):
            tid = str(x["kind"]).split(":", 1)[-1]
            if f"{wid}:nachtrag.vorlage.{tid}" not in (a.get("elements") or ()):  # the follow-on's own template is its element
                own(f"vorlage.{tid}")
        for r in x.get("required") or ():
            out.append(f"{COVER}:schreiben.{x['kind']}.{r.get('id')}")
    if form in ("A11_teilablehnung", "A12_mitwirkung_kanzlei"):
        out.append(f"{BACKBONE}:schreiben.{form}")
    from . import partial, refusal
    if form == refusal.FORM:  # the refusal of cover rests on each of its own parts
        out += refusal.element_ids()
    if form == "A4" and (next((i for i in listed or () if i.get("kind") == "next_action"), None) or {}).get("partial"):
        out += partial.element_ids()
    from . import live
    if form in live.forms() and not (draft.get("required") or ()):
        out += live.element_ids(form)
    if draft.get("live"):  # the answer to an offer, as the handler chose it
        out += live.element_ids(draft["live"])
    for ask in asks(form, draft.get("kind"), listed, events, assessment):
        if ask.get("kind") == "document" and ask.get("ref"):
            own(f"unterlage.{ask['ref']}")
        elif ask.get("kind") == "fact" and ask.get("ref"):
            own(f"frage.{ask['ref']}")
        elif ask.get("kind") == "claim":
            own("wortlaut.claim_line")
    if a.get("elements"):
        out += [str(e) for e in a["elements"]]
    elif a.get("assessment"):  # only an assessment states them: a reminder or a status inquiry in the same case rests on none
        for option in a.get("chosen") or () if isinstance(a.get("chosen"), list) else ():
            own(f"empfehlung.{option}")
        if isinstance(a.get("chosen"), list) and len(a["chosen"]) > 1:
            own("wortlaut.join")
        for q in a.get("questions") or ():
            if q.get("state") in ("beantwortet", "bedingt") and q.get("intent"):
                for point in q.get("points") or ():
                    own(f"antwort.{point}.{q['intent']}")
        for line in a.get("in_case") or ():
            key = str(line.get("key") or "")
            if key.startswith("fall."):
                own(key)
            elif key in ("wish", "claims"):
                own(f"wortlaut.{key}")
    return sorted(set(out))


def _frame_parts(form):
    """The area frame parts («@<key>») the backbone's form of ``form`` takes: [key]."""
    from . import area
    parts = (((area._shipped()[0] or {}).get("forms") or {}).get(form) or {}).get("parts") or ()
    return [p[1:] for p in parts if isinstance(p, str) and p.startswith("@")]


def marks_of(relies, marks):
    """The jurists' marks on the elements a letter rests on, as they stand when it is approved or checked: {key: mark id}."""
    return {k: (marks or {})[k].get("id") for k in relies or () if ((marks or {}).get(k) or {}).get("id")}


def held_marks(relies, marks, seen=None, titles=None):
    """The elements the letter rests on that a jurist marked «Änderung nötig» or «Frage» since it was approved or checked
    (``seen``: marks_of then; a mark is new when its id is not the one seen): [{key, mark, title, reviewer, at}];
    ``marks``: the marks that hold for the content as it is now (review.Model.current); ``titles``: {key: its title}."""
    out = []
    for key in relies or ():
        m = (marks or {}).get(key) or {}
        if m.get("mark") in HELD_MARKS and m.get("id") != (seen or {}).get(key):
            out.append({"key": key, "mark": HELD_MARKS[m["mark"]], "title": (titles or {}).get(key) or key.split(":", 1)[-1],
                        "reviewer": m.get("reviewer"), "at": m.get("at")})
    return out


# -- the log: approvals, packages, dispatches, copies -----------------------------------------------------------------------

def approvals(events):
    return [e for e in events or () if e.get("kind") == "action.approved"]


def _undone(events):
    return {e.get("edit_id") for e in events or () if e.get("kind") == "correction.undone" and e.get("edit_id")}


def dispatches(events, edits=None):
    """The dispatches in force, oldest first: [{version, recipient, date, channel, by, at, edit, event}]; one whose edit
    was undone is not (the log's «correction.undone», or ``edits``: the case's edits, an «add_dispatch» no longer active)."""
    gone = _undone(events) | {e["id"] for e in edits or () if e.get("op") == "add_dispatch" and e.get("status", "active") != "active"}
    return [{"version": e.get("version"), "recipient": e.get("recipient"), "date": e.get("date"), "channel": e.get("channel"), "by": e.get("expert"),
             "at": e.get("at"), "edit": e.get("edit_id"), "event": e.get("event_id")}
            for e in events or () if e.get("kind") == "action.dispatched" and e.get("edit_id") not in gone]


def sent_letters(events, edits=None):
    """Each letter dispatched in force, with what its approval says: [{form, also (kinds), title, version, recipient,
    date, channel, by, at, deadline, respond_by, edit}]."""
    by_version = {}
    for a in approvals(events):
        by_version[a.get("version")] = a
    out = []
    for d in dispatches(events, edits):
        a = by_version.get(d["version"]) or {}
        row = next((r for r in a.get("recipients") or () if r.get("to") == d["recipient"]), None) or {}
        first = (row.get("forms") or [a.get("form")])[0]
        out.append({**d, "form": a.get("form"), "title": (row.get("titles") or {}).get(first) or a.get("title"),
                    "forms": row.get("forms") or [a.get("form")], "also": [x.get("kind") for x in a.get("also") or ()],
                    "deadline": a.get("deadline"), "respond_by": a.get("respond_by"), "action_kind": a.get("action_kind")})
    return out


def is_legacy(e):
    return e.get("kind") == "letter.copied" and not e.get("measure")


def contacted(events):
    """Whether a letter of the insurer reached the customer as far as CasePath knows: a dispatch in force, or a copy made
    by a browser before this release (contact only: never sent, fulfilled or settled)."""
    return bool(dispatches(events)) or any(is_legacy(e) for e in events or ())


def legacy_copy(events, form, since=None):
    """The latest copy of this form by a browser before this release, after ``since`` (the prepared run): {at, form}."""
    rows = [e for e in events or () if is_legacy(e) and not e.get("also") and (not e.get("form") or e.get("form") == form)
            and str(e.get("at") or "") > str(since or "")]
    return {"at": rows[-1].get("at"), "form": rows[-1].get("form")} if rows else None


def enough_time(respond_by, approved_at, today=None):
    """Whether a frozen reply date still leaves the customer the form's period less three days."""
    due, at = parse_date(respond_by), parse_date(str(approved_at or "")[:10])
    return not (due and at) or (due - (today or swiss_today())).days >= (due - at).days - 3


def frozen_respond_by(events, form, today=None, edits=None):
    """The reply date an open approval of this form froze (its letter says it), or None: the latest approval of the form
    not yet dispatched to all its recipients, while it leaves enough time (else the date is computed afresh, and the
    approval is «veraltet: Datum»)."""
    sent = {(d["version"], d["recipient"]) for d in dispatches(events, edits)}
    for a in reversed(approvals(events)):
        if a.get("form") != form:
            continue
        pending = [r for r in a.get("recipients") or () if (a.get("version"), r.get("to")) not in sent]
        ok = pending and a.get("respond_by") and enough_time(a.get("respond_by"), a.get("at"), today)
        return a.get("respond_by") if ok else None
    return None


# -- what a dispatch asks and answers ---------------------------------------------------------------------------------------

def blocks_of(ask, assessment=None):
    """Why an assessment asks this (SLICE_A: ``blocks`` on each ask, {question, option, condition}): the customer's
    question whose answer waits for it, the option whose claim or condition it bears on and the condition itself. Where
    the assessment does not say, it is read from the brief: a claim line from the conditional answer that points to the
    residual and the option needing it; a missing fact from the conditional answer that asks it and the option
    conditions that name it; a document from the adopted option needing it. None for a request carried over (it waits
    for itself)."""
    a = assessment or {}
    if ask.get("blocks"):  # slice A names the customer's question by its item id: the dispatch keeps its words and the id
        given = dict(ask["blocks"])
        q = next((q for q in a.get("questions") or () if q.get("item_id") and q.get("item_id") == given.get("question")), None)
        option = next((o for o in a.get("options") or () if o.get("id") and o.get("id") == given.get("option")), None)
        return {**given, **({"question": q.get("text"), "question_id": q["item_id"]} if q and q.get("text") else {}),
                **({"option_title": option.get("title")} if option and option.get("title") and not given.get("option_title") else {})}
    kind, ref = ask.get("kind"), ask.get("ref")
    waiting = [q for q in a.get("questions") or () if q.get("state") == "bedingt"]
    chosen = [o for o in a.get("options") or () if o.get("chosen") or o.get("id") in (a.get("chosen") or [] if isinstance(a.get("chosen"), list) else [])]
    unchecked = lambda o: next((c.get("text") for c in o.get("conditions") or () if c.get("kind") == "anspruch" and c.get("state") == "nicht geprüft"), None)
    if kind == "claim":
        q = next((q for q in waiting if (q.get("next") or {}).get("kind") == "residual"), None)
        option = next((o for o in a.get("options") or () if o.get("id") == ((q or {}).get("next") or {}).get("option")), None) \
            or next((o for o in chosen if o.get("needs")), None)
        return {"question": (q or {}).get("text"), "option": (option or {}).get("id"), "option_title": (option or {}).get("title"),
                "condition": unchecked(option or {})}
    if kind == "fact":
        q = next((q for q in waiting if ((q.get("ask") or {}).get("fact")) == ref), None)
        option, condition = next(((o, c.get("text")) for o in a.get("options") or () for c in o.get("conditions") or () if c.get("fact") == ref), (None, None))
        return {"question": (q or {}).get("text"), "option": (option or {}).get("id"), "option_title": (option or {}).get("title"), "condition": condition}
    if kind == "document":
        option = next((o for o in chosen if ref in (o.get("needs") or ())), None)
        return {"question": None, "option": (option or {}).get("id"), "option_title": (option or {}).get("title"), "condition": None} if option else None
    return None


def asks(form, kind, listed, events, assessment=None, respond_by=None, role="kunde"):
    """What the letter asks of its recipient, as the account's asks of the dispatch: an assessment the assessment's asks
    (the residual lines ticked and the missing fact of each conditional answer), each with the judgment it is asked for
    (``blocks``: the question, option and condition); a first request or a question back the letter's asked lines; a
    pending or status letter a reply by its date. Each {what, of, by, kind, ref, key, warns, blocks}."""
    form = str(form or "")
    if form == FOLLOW_ON:  # the follow-on asks only what it says (a remainder), never the assessment's list again
        return [{"what": a.get("what"), "of": role, "by": respond_by, "kind": a.get("kind"), "ref": a.get("ref"), "key": a.get("key"),
                 **({"blocks": b} if (b := blocks_of(a, assessment)) else {})} for a in ((assessment or {}).get("follow_on") or {}).get("asks") or ()]
    assessing = kind == "A5" and form.startswith("A5") and form != "A5_aussichtslos"
    if assessing and (assessment or {}).get("letter"):  # the assessment writes the letter's residual: its asks are the letter's
        return [{"what": a.get("what"), "of": role, "by": respond_by, "kind": a.get("kind"), "ref": a.get("ref"), "key": a.get("key"),
                 **({"blocks": b} if (b := blocks_of(a, assessment)) else {})}
                for a in (assessment or {}).get("asks") or () if a.get("what")]
    act = next((i for i in listed or () if i.get("kind") == "next_action"), None) or {}
    if form == "A4" and act.get("partial"):  # the question back after a partial answer asks exactly what is still open
        from . import partial
        return partial.asks(act["partial"], role, respond_by)
    if form in ("A1", "A4") or assessing:  # an assessment without one asks, like the first request, the documents still missing
        docs = [{"what": (i.get("label") or {}).get("de") or i.get("value"), "of": role, "by": respond_by, "kind": "document", "ref": i["key"]}
                for i in letters.asked(listed, events, "document")] if form == "A1" or assessing else []
        if assessing:
            return [a for a in docs if a["what"]]
        lines = letters.line_state(events)
        questions = [{"what": i.get("value"), "of": role, "by": respond_by, "kind": "fact", "ref": i["key"]} for i in listed or ()
                     if i.get("kind") == "letter_question" and lines.get(i["item_id"], i.get("ask") != "proposed")]
        return [a for a in docs + questions if a["what"]]
    if form.startswith(("A6", "A7")):
        return [{"what": REPLY, "of": role, "by": respond_by, "kind": "reply", "ref": None, **({"warns": True} if "androhung" in form else {})}]
    return []


def answers(kind, form, assessment=None, events=()):
    """The customer's questions the letter answers: those the assessment answers, or the handler took an answer for
    (SLICE_A A12), each naming the customer's entry that asked it; a conditional answer stays open."""
    if kind != "A5" or not str(form or "").startswith("A5"):
        return []
    taken = {e.get("item_id") for e in events or () if e.get("kind") == "item.corrected" and str(e.get("item_id") or "").startswith("customer_question:")}
    only = set(((assessment or {}).get("follow_on") or {}).get("questions") or ()) if form == FOLLOW_ON else None  # a follow-on: those it takes up
    return [{"what": q.get("text"), "answers": q.get("entry")} for q in (assessment or {}).get("questions") or ()
            if q.get("text") and isinstance(q.get("entry"), int) and (q.get("state") == "beantwortet" or q.get("item_id") in taken)
            and (only is None or q.get("item_id") in only)]


def addressed(kind, form, assessment=None, events=()):
    """Every customer question the letter takes up, for the file note and «Als Nächstes»: [{what, state, reason}], answered
    («beantwortet», or an answer the handler took) or answered on a condition («bedingt», ``reason``: what it rests on or
    waits for). Unlike ``answers`` (what closes the question in the account), a conditional answer counts: the letter
    answers it, and what it waits for is the customer's open ask, never something open at the insurer."""
    if kind != "A5" or not str(form or "").startswith("A5"):
        return []
    taken = {e.get("item_id") for e in events or () if e.get("kind") == "item.corrected" and str(e.get("item_id") or "").startswith("customer_question:")}
    only = set(((assessment or {}).get("follow_on") or {}).get("questions") or ()) if form == FOLLOW_ON else None
    return [{"what": q["text"], "state": "beantwortet" if q.get("state") == "beantwortet" or q.get("item_id") in taken else "bedingt",
             "reason": q.get("reason") if q.get("state") == "bedingt" and q.get("item_id") not in taken else None}
            for q in (assessment or {}).get("questions") or ()
            if q.get("text") and (q.get("state") in ("beantwortet", "bedingt") or q.get("item_id") in taken)
            and (only is None or q.get("item_id") in only)]


def taken_up(events, edits=None):
    """The customer questions the letters sent (in force) took up, as their dispatch recorded them (``addressed``)."""
    by_event = {e.get("event_id"): e for e in events or () if e.get("kind") == "action.dispatched"}
    return [a for s in sent_letters(events, edits) for a in (by_event.get(s.get("event")) or {}).get("answered") or ()]


def answered_line(title, rows):
    """«Beantwortet in «Titel»: «…»; bedingt: «…» (was es braucht)», or None without rows."""
    plain = [f"«{r['what']}»" for r in rows or () if r.get("state") == "beantwortet"]
    cond = [f"«{r['what']}»" + (f" ({r['reason']})" if r.get("reason") else "") for r in rows or () if r.get("state") != "beantwortet"]
    if not plain and not cond:
        return None
    return f"Beantwortet in «{title}»: " + "; ".join(plain + ([f"bedingt: {', '.join(cond)}"] if cond else []))


def without_answered(rows, questions):
    """The rows of «Offen bei uns» without the questions a letter took up (a row starts with the question's words)."""
    words = [q.get("what") for q in questions or () if q.get("what")]
    return [r for r in rows or () if not any(str(r.get("text") or "").startswith(w) for w in words)]


# -- fulfilment by evidence -------------------------------------------------------------------------------------------------

def _entry_files(entry, files):
    """The files of an entry: its own and those attached to it (an e-mail's attachments)."""
    fid = entry.get("file")
    if not fid:
        return set()
    name = next((f.get("name") for f in files or () if f.get("id") == fid), None)
    return {fid} | {f["id"] for f in files or () if name and (f.get("extraction") or {}).get("attached_to") == name}


def fulfilment(entry, acc, files, result=None, process=None, held=None):
    """How a dispatch (its account entry) stands after it, from evidence only: {acknowledged, replies, met, open, unbelegt,
    refused, promised, evidence, fulfilled, partial}. Per ask, against the entries of its addressee after it (dated after
    it, or dated its day and answering it by its number: account.replies_to): a
    claim line is met when the claim is documented by a receipt located in a file of such an entry; a document when
    account.held names such a file; a fact when it is established with a quote from such a file; a request carried over
    when its row is closed and, for a document, held as above; a reply by any such entry with its file. An ask whose row
    was closed by words alone is «Antwort ohne Beleg – prüfen»; a refusal (the row's ``refused``, slice C) or a promise
    (``promised``) meets nothing; ``evidence``: {ask key: the file that meets it}."""
    from . import account
    held = held or account.held
    result = result or {}
    # after the dispatch: dated after it, or dated its day and answering it by its number (account.replies_to)
    later = [e for e in (acc or {}).get("entries") or () if e.get("from") == entry.get("to") and not e.get("dispatch")
             and account.replies_to(e, entry.get("date"), entry.get("n"))]
    reply_files = set().union(*[_entry_files(e, files) for e in later]) if later else set()
    later_n = {e["n"] for e in later}
    rows = {r["id"]: r for r in (acc or {}).get("requests") or ()}
    claims = ((result.get("brief") or {}).get("claims")) or []
    needs = {d["id"]: d for d in (process or {}).get("documents") or ()}
    met, open_, unbelegt, refused, promised, evidence = [], [], [], [], [], {}
    moot, unclear = [], []
    from . import claims as claim_model
    claims = claim_model.normalized(claims)
    contested = claim_model.contested(claims)
    for i, ask in enumerate(entry.get("asks") or ()):
        kind, ref, ok, where = ask.get("kind"), ask.get("ref"), False, None
        claim = claims[ref] if kind == "claim" and isinstance(ref, int) and 0 <= ref < len(claims) else None
        if claim is not None and claim["state"] == claim_model.WITHDRAWN:
            # the customer withdrew the cost: its receipts are no longer owed, whatever the letter asked when it went out
            moot.append({**ask, "why": "Forderung zurückgezogen", "stated": (claim.get("withdrawn") or {}).get("stated")})
            continue
        if claim is not None and claim["id"] in contested:
            # the same cost stated differently, unsettled: nothing documents it until the handler says which holds
            other = contested[claim["id"]]
            unclear.append({**ask, "claim": claim["id"], "statement": other["id"], "amounts": [claim.get("amount"), other.get("amount")]})
            continue
        if kind == "claim":
            in_reply = [f for f in files or () if f.get("id") in reply_files]
            judged, found = _held_claim(held, ask, ref, in_reply, claims, (acc or {}).get("entries"))
            if judged:  # slice C decides from what the reading records of the receipt (expense, party, period, amount's role)
                ok, where = bool(found and found.get("file") in reply_files), (found or {}).get("file")
            else:  # until then: the claim documented by a receipt located in a file of the reply
                claim = claims[ref] if isinstance(ref, int) and 0 <= ref < len(claims) else None
                receipt = ((claim or {}).get("receipt") or [None])
                receipt = receipt[0] if isinstance(receipt, list) else receipt
                ok = bool(claim and claim.get("documented") and (receipt or {}).get("file") in reply_files)
                where = (receipt or {}).get("file") if ok else None
            if not ok and claim is not None:
                # the rest that was asked came: with the receipts already in the case it adds up to what is claimed
                whole = account.documented(claim, files, (acc or {}).get("entries"))
                mine = [f for f in (whole or {}).get("files") or () if f in reply_files]
                if whole and whole.get("how") == "receipts" and mine:
                    ok, where = True, mine[0]
            if not ok and claim is not None:  # a receipt for the same cost that covers part of the amount: what is documented so far
                part = documented_part(claim, in_reply, (acc or {}).get("entries"))
                if part:
                    ask = {**ask, "part": part}
        elif kind == "document":
            found = held({"what": ask.get("what"), "need": ref, "title": (needs.get(ref) or {}).get("title")}, [f for f in files or () if f.get("id") in reply_files])
            ok = bool(found and found.get("file") in reply_files)
            where = (found or {}).get("file") if ok else None
        elif kind == "fact":
            row = next((f for f in result.get("facts") or () if f.get("fact") == ref and f.get("status") == "established" and f.get("verdict") == "accepted"
                        and any(c.get("file") in reply_files for c in f.get("citations") or ())), None)
            ok = row is not None
            where = next((c.get("file") for c in (row or {}).get("citations") or () if c.get("file") in reply_files), None)
        elif kind == "request":
            row = rows.get(ref) or {}
            closed = bool(row.get("answered"))
            doc = any(_head(d.get("title")) and _head(d.get("title")) == _head(row.get("what")) for d in needs.values())
            found = held({"what": row.get("what"), "request": ref}, [f for f in files or () if f.get("id") in reply_files]) if doc else None
            ok = closed and (not doc or bool(found and found.get("file") in reply_files))
            where = (found or {}).get("file") if ok and found else None
        elif kind == "reply":
            ok = bool(later and reply_files)
            where = sorted(reply_files)[0] if ok else None
        own = rows.get(f"r{entry['n']}.{i}") or {}
        if ok:
            met.append(ask)
            evidence[ask.get("key") or ask.get("what")] = where
        elif own.get("refused") and (own["refused"].get("n") in later_n or not own["refused"].get("n")):
            refused.append({**ask, "refused": own["refused"]})  # the addressee said no («keine Belege»): nothing is met
        elif own.get("promised") and own["promised"].get("n") in later_n:
            promised.append({**ask, "promised": own["promised"]})  # promised, not delivered: the wait goes on to its day
        elif (own.get("answered") or {}).get("n") in later_n:
            unbelegt.append(ask)  # closed by words, nothing in a file: an answer without evidence
        else:
            open_.append(ask)
    total = len(entry.get("asks") or ()) - len(moot)  # what is still owed of it
    return {"acknowledged": bool(later), "replies": sorted(later_n), "met": met, "open": open_, "unbelegt": unbelegt, "refused": refused,
            "promised": promised, "evidence": evidence, "fulfilled": bool(later) and total > 0 and len(met) == total,
            "partial": 0 < len(met) < total, "moot": moot, "unclear": unclear,
            "remainder": [a for a in open_ + unbelegt if a.get("part")]}


def claim_wishes(process):
    """The wishes of the area's ways that name the claimed costs («will_schadenersatz»): what a withdrawn claim takes back."""
    from . import options
    data = options.load((process or {}).get("id"))
    return {o["wish"] for o in (data or {}).get("options") or () if any(n.get("names_claim") for n in o.get("needs") or ())}


def documented_part(claim, files, entries):
    """What a receipt in ``files`` documents of a claim when it covers only part of its amount: {amount, of, rest, file, n,
    expense}, for a receipt the reading recorded for the same cost that is set aside for its amount alone and is lower
    than the claim's; None otherwise (no receipt, another cost, or nothing to compare)."""
    from . import account
    from .claims import number
    why, total = [], number(claim)
    if total is None or account.documented(claim, files, entries, None, why):
        return None
    rows = [w for w in why if w.get("recorded") and len(w.get("why") or ()) == 1 and str(w["why"][0]).startswith("Betrag weicht ab")
            and len(w.get("amounts") or ()) == 1]
    have = round(sum(w["amounts"][0] for w in rows), 2)  # every recorded receipt of this cost counts towards it
    if not rows or have >= total:
        return None
    best = max(rows, key=lambda w: w["amounts"][0])
    return {"amount": have, "of": total, "rest": round(total - have, 2), "file": best.get("file"), "n": best.get("n"), "expense": best.get("expense"),
            "files": [w.get("file") for w in rows]}


def _held_claim(held, ask, ref, files, claims, entries):
    """Slice C's verdict on a claim line (account.held with the claim and the account's entries: a receipt delivers it
    only when what the reading records about it agrees with the claim), as (judged, {file, how, n, basis} or None);
    (False, None) where account.held does not judge claims yet (the stub before slice C), so the caller decides."""
    import inspect
    try:
        params = inspect.signature(held).parameters
    except (TypeError, ValueError):
        return False, None
    if "entries" not in params:
        return False, None
    return True, held({"what": ask.get("what"), "ask": {"kind": "claim", "ref": ref}}, files, claims=claims, entries=entries, why=[])


def _judgment(ask):
    """The judgment an ask was made for, in the handler's words: «Frage «…»», else the option and its condition."""
    b = ask.get("blocks") or {}
    if b.get("question"):
        return f"«{b['question']}»"
    if b.get("option_title") or b.get("option"):
        return str(b.get("option_title") or b.get("option")) + (f" ({b['condition']})" if b.get("condition") else "")
    return None


def consequence(how, entry=None, changed=(), held=()):
    """What a reply to a dispatched letter means for the work, from evidence only (``how``: fulfilment), as one of:

    - ``resolved``: every ask is met and at least one was asked for a judgment (``blocks``): that judgment can be made
      now, and the resulting assessment or action is what comes next; waiting for the follow-up date has no reason left;
    - ``contradiction``: a fact the letter rests on changed after it went out (``changed``) or a jurist since holds an
      element it rests on (``held``): the judgment is reopened («versandt mit früherem Stand – prüfen»);
    - ``refused``: the addressee refused an ask: there is nothing left to wait for, the judgment is made without it;
    - ``unbelegt``: an ask answered by words without evidence («Antwort ohne Beleg – prüfen»);
    - ``partial``: some asks met, the rest still owed: the remainder is all that is asked, the wait goes on for it;
    - ``fulfilled``: every ask met, none blocked a judgment (a reply, a status answer): the next step decides;
    - ``unrelated``: the addressee wrote after it, but nothing meets, answers, refuses or promises an ask: the wait stays
      as it was, quiet;
    - ``waiting``: nothing came since: the wait stays;
    - ``unclear``: a cost the letter asked the receipts of was since stated differently and nothing says which holds: one
      question for the handler, before anything else;
    - ``remainder``: a receipt documents part of a claimed amount (the claim was corrected upwards, or the receipt covers
      less): a short letter asks only the rest;
    - ``withdrawn``: what it asked is no longer owed (the customer withdrew the cost): no letter, the wait goes on.

    Returns {kind, judgments [{ask, judgment, blocks, file}], remainder [ask], refused [ask], reason_to_wait (bool),
    text}."""
    how = how or {}
    met = list(how.get("met") or ())
    judgments = [{"ask": a.get("what"), "judgment": _judgment(a), "blocks": a.get("blocks"), "kind": a.get("kind"), "ref": a.get("ref"),
                  "file": (how.get("evidence") or {}).get(a.get("key") or a.get("what"))} for a in met if a.get("blocks")]
    remainder = list(how.get("open") or ()) + list(how.get("promised") or ())
    out = {"judgments": judgments, "remainder": remainder, "refused": list(how.get("refused") or ()), "reason_to_wait": bool(remainder),
           "moot": list(how.get("moot") or ()), "unclear": list(how.get("unclear") or ())}
    if how.get("unclear"):  # one specific question before anything else moves: which statement of the cost holds
        u = how["unclear"][0]
        return {**out, "kind": "unclear", "reason_to_wait": False,
                "text": "Kostenangabe klären: " + " oder ".join(str(a) for a in u.get("amounts") or () if a)}
    if changed or held:
        what = list(changed) + [f"{h['title']} ({h['mark']})" for h in held]
        return {**out, "kind": "contradiction", "reason_to_wait": False, "text": f"versandt mit früherem Stand – prüfen: {', '.join(what)}"}
    if how.get("moot") and not (met or remainder or how.get("unbelegt") or how.get("refused")):
        # everything it asked is no longer owed (the customer withdrew the cost): no letter, the wait to its date goes on
        return {**out, "kind": "withdrawn", "reason_to_wait": True, "text": None}
    if not how.get("acknowledged"):
        return {**out, "kind": "waiting", "text": None}
    if how.get("remainder"):
        # a receipt covers part of what is claimed: only the rest is asked, in a short letter, not waited for in silence
        asked = [{"ask": a.get("what"), "judgment": _judgment(a), "blocks": a.get("blocks"), "file": a["part"].get("file"), "part": a["part"],
                  "ref": a.get("ref")} for a in how["remainder"]]
        return {**out, "kind": "remainder", "judgments": asked, "reason_to_wait": False, "text": "teilweise belegt: Rest nachfragen"}
    if how.get("refused"):
        return {**out, "kind": "refused", "reason_to_wait": bool(remainder),
                "text": "abgelehnt: " + ", ".join(a.get("what") or "" for a in how["refused"])}
    if how.get("unbelegt"):
        return {**out, "kind": "unbelegt", "text": "Antwort ohne Beleg – prüfen"}
    if how.get("fulfilled") and judgments:
        said = ", ".join(dict.fromkeys(j["judgment"] for j in judgments if j["judgment"])) or "die Einschätzung"
        return {**out, "kind": "resolved", "reason_to_wait": False, "text": f"erfüllt: jetzt zu beurteilen {said}"}
    if how.get("fulfilled"):
        return {**out, "kind": "fulfilled", "reason_to_wait": False, "text": "erfüllt"}
    if met:
        return {**out, "kind": "partial", "text": "teilweise erfüllt: offen " + ", ".join(a.get("what") or "" for a in remainder)}
    return {**out, "kind": "unrelated", "text": None}


# -- the state --------------------------------------------------------------------------------------------------------------

def _day(value):
    d = parse_date(value)
    return d.strftime("%d.%m.%Y") if d else ""


def _bundle(events, approval):
    """The Versandpaket stored with an approval («bundle.saved» naming it), or, for a version, the latest one stored."""
    if isinstance(approval, dict):
        own = next((e for e in reversed(events or ()) if e.get("kind") == "bundle.saved" and approval.get("event_id")
                    and e.get("approval") == approval.get("event_id")), None)
        return own or next((e for e in reversed(events or ()) if e.get("kind") == "bundle.saved" and not e.get("approval")
                            and e.get("version") == approval.get("version") and str(e.get("at") or "") >= str(approval.get("at") or "")), None)
    return next((e for e in reversed(events or ()) if e.get("kind") == "bundle.saved" and e.get("version") == approval), None)


def reconciled(events, version):
    """The latest «Abgleich erledigt» of a dispatched version: the premise and the marks the handler checked it against
    (``action.reconciled``), or None."""
    return next((e for e in reversed(events or ()) if e.get("kind") == "action.reconciled" and e.get("version") == version), None)


def default_channel(files):
    """The channel of the customer's last message: an e-mail file (.eml, .msg) gives «email», anything else «post»."""
    newest = max(files or (), key=lambda f: str(f.get("created_at") or ""), default=None)
    if not newest:
        return "post"
    return "email" if newest.get("kind") == "email" or str(newest.get("name") or "").lower().endswith((".eml", ".msg")) else "post"


def earliest(approval, events, form):
    """The first day the approved letter can have gone out: its approval day, a copy of the same text, or a copy of the
    same form by a browser before this release, whichever came first."""
    days = [swiss_day(approval.get("at"))]
    days += [swiss_day(e.get("at")) for e in events or () if e.get("kind") == "letter.copied" and e.get("measure")
             and e.get("text_sha256") and e.get("text_sha256") == approval.get("text_sha256")]
    days += [swiss_day(e.get("at")) for e in events or () if is_legacy(e) and not e.get("also") and e.get("form") in (None, form)]
    return min(d for d in days if d) if any(days) else None


def arrived_after(approval, files, events=()):
    """The files that came into the case after an approval was given (not among the files it was given on, ``file_ids``;
    for an older record, created after it), while the handler has not said since that they do not change it («trotzdem
    verwenden», ``letter.unblocked``, after the newest of them): [file]. Read or not: what came between the review and
    the sending is not what was reviewed, until the letter is approved again."""
    approval = approval or {}
    known = approval.get("file_ids")
    at = str(approval.get("at") or "")
    came = [f for f in files or () if (f.get("id") not in known if known is not None else str(f.get("created_at") or "") > at)]
    newest = max((str(f.get("created_at") or "") for f in came), default="")
    if came and any(e.get("kind") == "letter.unblocked" and str(e.get("at") or "") >= newest for e in events or ()):
        return []
    return came


def validity(approval, draft, facts, assessment=None, process=None, unread=(), files=(), events=(), today=None, marks=None, partial=False,
             stand_now=None):
    """Why an approval no longer holds, recomputed now: [reasons] (empty: it holds). It holds only while its version is
    the current one, its form the prepared one, its premise as stored, no decision is open, every required part is in
    the letter, nothing the letter rests on was marked by a jurist since («Änderung nötig» or «Frage»: ``marks``, the
    marks that hold now), no file came into the case after it (``arrived_after``; a later «trotzdem verwenden» counts)
    and enough time is left before the reply date it froze (the form's period less three days). ``unread`` is kept for
    the callers; any file after the approval counts, read or not. ``partial``: a package already sent to one recipient
    (the plan moved on with that dispatch): the rest of it is the version approved, so only what it rests on counts
    (premise, marks, arrivals, the date), never the letter prepared now."""
    out = []
    if partial:
        pass
    elif not draft or approval.get("form") != (draft.get("form") or draft.get("kind")):
        out.append("Schritt geändert")
    elif approval.get("version") != draft.get("version"):
        now = {"recipients": [[r["to"], r["recipient"]] for r in draft.get("recipients") or ()], "text": sha(draft.get("text")),
               "also": sorted([a["kind"], sha(a["text"])] for a in draft.get("also") or () if a.get("text"))}
        was = {"recipients": [[r.get("to"), r.get("recipient")] for r in approval.get("recipients") or ()], "text": approval.get("text_sha256"),
               "also": sorted([a.get("kind"), a.get("sha256")] for a in approval.get("also") or ())}
        named = [w for k, w in (("recipients", "Empfänger geändert"), ("text", "Text geändert"), ("also", "Beilagen geändert")) if now[k] != was[k]]
        if (draft.get("respond_by") or None) != (approval.get("respond_by") or None):
            named.append("Datum")
        out += named or ["Text geändert"]
    for fact in changed_premise(approval.get("premise"), facts, assessment, process):
        out.append("Entscheid geändert" if fact in DECISION_FACTS else "Voraussetzung geändert")
    if not partial and open_decisions(draft, facts, assessment, process):
        out.append("Entscheid geändert")
    if not partial and any(b.get("kind") == "gap" for b in (assessment or {}).get("blocking") or ()):
        out.append("Text geändert")
    if not partial and draft and missing_required(draft):
        out.append("Pflichtteil fehlt")
    if held_marks(approval.get("relies"), marks, approval.get("relies_marks")):
        out.append("Grundlage in Prüfung")
    if rule_changed(approval, stand_now):  # a rule released or withdrawn since changed what this case asks (``stand_now``: stand() now)
        out.append("Regel geändert")
    if arrived_after(approval, files, events):
        out.append("Neue Unterlagen")
    if not enough_time(approval.get("respond_by"), approval.get("at"), today):
        out.append("Datum")
    return sorted(set(out), key=REASONS.index)


def state(case, listed, draft, events, edits, account=None, assessment=None, files=(), today=None, facts=None, process=None, unread=(),
          result=None, prepared_at=None, follow_up=None, held=None, marks=None, titles=None, saves=0):
    """Where the prepared letter stands after the decision, recomputed on every read: {state (entwurf | freigegeben |
    versandt), version, form, approved {by, at, version, form, respond_by, bundle}, dispatched [{recipient, date, channel,
    by}], pending, valid, stale [reasons], held [elements a jurist holds], premise_changed [questions], last (the last
    letter dispatched: {form, title, dispatched, asks, acknowledged, fulfilled, partial, open, unbelegt, refused, met,
    stale, consequence}), acknowledged, fulfilled, partial, waiting_until, legacy_copy, decision, bucket, status, date,
    effort, bar}. ``bucket``/``status`` are set only where the letter decides the case list's row (listing.stand decides
    the rest). ``marks``: the jurists' marks that hold now (review.Model.current), ``titles`` their elements' titles."""
    today = today or swiss_today()
    facts = facts or {}
    edits = edits or []
    draft = draft or {}
    form = draft.get("form") or draft.get("kind")
    version = draft.get("version")
    sent = dispatches(events, edits)
    every = approvals(events)
    same = [a for a in every if version and a.get("version") == version]
    approval = same[-1] if same else (every[-1] if every else None)
    done_for = lambda a: {d["recipient"] for d in sent if d["version"] == a.get("version")}
    rest = None  # a package sent to some of its recipients while the plan moved on: the others are still to confirm
    if approval and not same:
        to_all = {r.get("to") for r in approval.get("recipients") or ()}
        if not (to_all - done_for(approval)):
            approval = None  # the latest approval went out to every recipient: the letter prepared now is a new one
        elif done_for(approval):
            rest, approval = approval, None
    out = {"state": "entwurf", "version": version, "form": form, "approved": None, "dispatched": [], "pending": [], "valid": False, "stale": [],
           "held": [], "premise_changed": [], "last": None, "acknowledged": False, "fulfilled": False, "partial": False, "waiting_until": None,
           "legacy_copy": None, "decision": None, "bucket": None, "status": None, "date": None, "recipients": draft.get("recipients") or [], "rest": None}
    if rest:
        stale = validity(rest, draft, facts, assessment, process, unread, files, events, today, marks, partial=True, stand_now=stand(process, listed))
        out["rest"] = {"version": rest.get("version"), "form": rest.get("form"), "title": rest.get("title"), "earliest": earliest(rest, events, rest.get("form")),
                       "pending": [r for r in rest.get("recipients") or () if r.get("to") not in done_for(rest)],
                       "dispatched": [{"recipient": d["recipient"], "date": d["date"], "channel": d["channel"]} for d in sent if d["version"] == rest.get("version")],
                       "stale": stale}
    needed = open_decisions(draft, facts, assessment, process) if draft.get("text") else []
    out["decision"] = needed[0] if needed else None
    questions = {i["key"]: (i.get("label") or {}).get("de") or i["key"] for i in listed or () if i.get("kind") == "fact"}
    if approval:
        mine = [d for d in sent if d["version"] == approval.get("version")]
        bundle = _bundle(events, approval)
        out["approved"] = {"by": approval.get("expert"), "at": approval.get("at"), "version": approval.get("version"), "form": approval.get("form"),
                           "title": approval.get("title"), "respond_by": approval.get("respond_by"), "event": approval.get("event_id"),
                           "text_sha256": approval.get("text_sha256"),
                           "bundle": {"sha256": bundle.get("sha256"), "bytes": bundle.get("bytes")} if bundle else None}
        out["dispatched"] = [{"recipient": d["recipient"], "date": d["date"], "channel": d["channel"], "by": d["by"], "edit": d["edit"]} for d in mine]
        out["pending"] = [r for r in approval.get("recipients") or () if r.get("to") not in {d["recipient"] for d in mine}]
        out["state"] = "freigegeben" if out["pending"] else "versandt"
        out["stale"] = validity(approval, draft, facts, assessment, process, unread, files, events, today, marks, stand_now=stand(process, listed))
        out["held"] = held_marks(approval.get("relies"), marks, approval.get("relies_marks"), titles)
        out["arrived"] = [f.get("name") for f in arrived_after(approval, files, events)]
        out["valid"] = not out["stale"]
    # the last letter that went out: what it asked, whether the addressee answered, what is met by evidence, what it means
    went = [a for a in every if any(d["version"] == a.get("version") for d in sent)]
    last = went[-1] if went else None
    if last:
        entry = next((e for e in (account or {}).get("entries") or () if (e.get("dispatch") or {}).get("version") == last.get("version")), None)
        how = fulfilment(entry, account, files, result, process, held) if entry and account else {}
        mine = [d for d in sent if d["version"] == last.get("version")]
        checked = reconciled(events, last.get("version"))  # «Abgleich erledigt»: what the handler checked the sent letter against
        changed = changed_premise((checked or {}).get("premise") if checked else last.get("premise"), facts, assessment, process)
        if how.get("moot"):  # the customer withdrew the cost after the letter went out: the letter was right when sent, nothing to reconcile
            changed = [k for k in changed if k not in claim_wishes(process)]
        holding = held_marks(last.get("relies"), marks, (checked or {}).get("relies_marks") if checked else last.get("relies_marks"), titles)
        meaning = consequence(how, entry, [questions.get(k, k) for k in changed], holding)
        read = facts_read(facts, process)
        out["last"] = {"form": last.get("form"), "title": last.get("title"), "version": last.get("version"), "respond_by": last.get("respond_by"),
                       "action_kind": last.get("action_kind"),
                       "dispatched": [{"recipient": d["recipient"], "date": d["date"], "channel": d["channel"], "by": d["by"]} for d in mine],
                       "asks": [a.get("what") for a in (entry or {}).get("asks") or ()], **{k: how.get(k) for k in ("acknowledged", "fulfilled", "partial")},
                       "open": [a.get("what") for a in how.get("open") or ()], "unbelegt": [a.get("what") for a in how.get("unbelegt") or ()],
                       "refused": [a.get("what") for a in how.get("refused") or ()], "promised": [a.get("what") for a in how.get("promised") or ()],
                       "met": [a.get("what") for a in how.get("met") or ()], "held": holding, "consequence": meaning,
                       "reconciled": {"by": checked.get("expert"), "at": checked.get("at")} if checked else None,
                       # what «Abgleich erledigt» records: the sent letter's premise as it reads now (read as validity reads it)
                       "premise_now": {k: _premise_value(k, read, assessment) for k in last.get("premise") or {}}}
        out["premise_changed"] = [questions.get(k, k) for k in changed]
        gone = _undone(events)
        out["last"]["stale"] = sorted({r for e in events or () if e.get("kind") == "action.dispatched" and e.get("version") == last.get("version")
                                       and e.get("edit_id") not in gone and not checked for r in e.get("stale") or ()},
                                      key=lambda r: REASONS.index(r) if r in REASONS else 99)
        out.update(acknowledged=bool(how.get("acknowledged")), fulfilled=bool(how.get("fulfilled")), partial=bool(how.get("partial")))
        if meaning["reason_to_wait"] or meaning["kind"] in ("waiting", "unrelated"):
            out["waiting_until"] = last.get("respond_by") or (follow_up or {}).get("due")
    out["legacy_copy"] = legacy_copy(events, form, prepared_at) if draft.get("text") and not out["approved"] else None
    # the case list's row, where the letter decides it; what the last letter sent says, only while nothing newer is approved
    current_last = last is not None and (approval is None or approval is last)
    meaning = (out["last"] or {}).get("consequence") or {}
    act = next((i for i in listed or () if i.get("kind") == "next_action"), None) or {}
    rest_to = ", ".join(TO_WORDS.get(r.get("to"), r.get("to")).split(" ", 1)[-1] for r in (out["rest"] or {}).get("pending") or ())
    if approval and not out["approved"]["bundle"] and out["state"] == "freigegeben":
        out.update(bucket="fehlgeschlagen", status="Versandpaket fehlt")
    elif out["rest"] and out["rest"]["stale"]:
        out.update(bucket="urteil", status=f"Freigabe veraltet: {out['rest']['stale'][0]} (Versand an {rest_to} offen)")
    elif out["rest"]:
        out.update(bucket="versandbereit", status=f"freigegeben, Versand an {rest_to} offen", date=swiss_day(rest.get("at")))
    elif out["state"] == "freigegeben" and out["stale"]:
        out.update(bucket="urteil", status=f"Freigabe veraltet: {out['stale'][0]}")
    elif out["state"] == "freigegeben":
        out.update(bucket="versandbereit", status="freigegeben, Versand offen", date=swiss_day(approval.get("at")))
    elif out["legacy_copy"]:
        out.update(bucket="versandbereit", status="kopiert, Versand nicht bestätigt", date=swiss_day(out["legacy_copy"]["at"]))
    elif current_last and out["last"]["stale"] and meaning.get("kind") != "contradiction":
        out.update(bucket="urteil", status=f"versandt mit früherem Stand – prüfen: {', '.join(out['last']['stale'])}")
    elif current_last and meaning.get("kind") == "contradiction":
        out.update(bucket="urteil", status=meaning["text"])
    elif current_last and meaning.get("kind") == "resolved":
        # the evidence asked for came: the judgment it was asked for is next, prepared where the plan already turned to it
        ready = act.get("action") and (act.get("consequence") or act.get("action") == last.get("action_kind"))
        out.update(bucket="urteil", status="erfüllt: " + ("Nachtrag vorbereitet" if ready and act.get("form") == FOLLOW_ON
                                                         else "Einschätzung vorbereitet" if ready and act.get("action") == "A5"
                                                         else f"{(act.get('label') or {}).get('de') or act.get('action')} vorbereitet" if ready
                                                         else "Einschätzung ergänzen" if last.get("action_kind") == "A5" else "nächsten Schritt vorbereiten"))
    elif current_last and meaning.get("kind") == "unclear":
        out.update(bucket="urteil", status=meaning["text"])  # one question first: which statement of the cost holds
    elif current_last and meaning.get("kind") == "remainder":
        out.update(bucket="urteil", status="teilweise belegt: " + ("Rückfrage zum Rest vorbereitet" if act.get("form") == FOLLOW_ON else "Rest nachfragen"))
    elif current_last and meaning.get("kind") in ("refused", "unbelegt"):
        out.update(bucket="urteil", status=meaning["text"])
    elif current_last and meaning.get("kind") == "partial" and meaning.get("judgments"):
        out.update(bucket="urteil", status=meaning["text"])
    elif current_last and meaning.get("kind") == "partial":
        out.update(status=meaning["text"])  # the remainder is still owed: the wait goes on, quietly (listing.stand: «Wartet»)
    out["effort"] = effort(out, draft, approval, events, edits, prepared_at, saves)
    out["bar"] = bar(out, draft, approval, events, files, today)
    return out


def effort(st, draft, approval, events, edits, since=None, saves=0):
    """What the handler still does and did for this letter, so it is counted as effort, never hidden: ``external``, the
    steps outside CasePath (sending to each recipient with its enclosures, filing the file note in the claims system,
    entering the follow-up in the diary), each with what CasePath knows of it («bestätigt» from «Versandt am», «kopiert»
    from a copy of the file note, else «offen»: CasePath cannot see the claims system); ``confirmations`` (approvals,
    dispatches, «trotzdem verwenden», reconciliations) and ``corrections`` (edits of the letter's text: ``saves``, the
    handler's saves of it; lines unticked or added, facts and answers corrected, undos) since the case was last prepared."""
    since = str(since or "")
    later = [e for e in events or () if str(e.get("at") or "") > since]
    external = []
    if approval:
        for r in approval.get("recipients") or ():
            done = next((d for d in st.get("dispatched") or () if d["recipient"] == r.get("to")), None)
            forms = r.get("forms") or []
            external.append({"step": "senden", "what": f"Brief an {TO_WORDS.get(r.get('to'), r.get('to'))}"
                             + (f" mit {len(forms) - 1} Beilage{'' if len(forms) == 2 else 'n'}" if len(forms) > 1 else ""),
                             "state": f"bestätigt am {_day(done['date'])}" if done else "offen"})
        filed = [e for e in events or () if e.get("kind") == "filenote.copied" and str(e.get("at") or "") >= str(approval.get("at") or "")]
        external.append({"step": "ablegen", "what": "Aktennotiz im Schadensystem", "state": "kopiert" if filed else "offen"})
        external.append({"step": "eintragen", "what": "Wiedervorlage im Schadensystem", "state": "offen"})
    kinds = lambda *ks: sum(1 for e in later if e.get("kind") in ks)
    return {"external": external, "external_open": sum(1 for x in external if x["state"] == "offen"),
            "confirmations": kinds("action.approved", "action.dispatched", "letter.unblocked", "action.reconciled"),
            "corrections": kinds("item.corrected", "item.dismissed", "item.added", "letter.line", "correction.undone", "entry.added",
                                 "entry.changed", "entry.removed", "followup.set") + int(saves or 0),
            "copies": kinds("letter.copied", "filenote.copied")}


def tab_states(st, events):
    """Each document's tab state {kind: {state, label}}: «freigegeben» (or «Freigabe veraltet») once its version is
    approved, «versandt am …» once its recipient's dispatch is confirmed; a document without one is «Entwurf»."""
    version = (st.get("approved") or {}).get("version")
    approval = next((a for a in reversed(approvals(events)) if version and a.get("version") == version), None)
    sent = {d["recipient"]: d for d in st.get("dispatched") or ()}
    out = {}
    for r in (approval or {}).get("recipients") or ():
        went = sent.get(r.get("to"))
        for kind in r.get("forms") or ():
            out[kind] = ({"state": "versandt", "label": f"versandt am {_day(went['date'])}"} if went
                         else {"state": "veraltet", "label": "Freigabe veraltet"} if st.get("stale")
                         else {"state": "freigegeben", "label": "freigegeben"})
    return out


def bar(st, draft, approval, events, files, today):
    """The card's action bar: before approval «Freigeben»; after it «Brief kopieren» first, then «Versandt am» per
    recipient (today and the channel of the customer's last message preset, the first day allowed), the package and the
    file note; a stale approval «Erneut freigeben»; after the dispatch «versandt am …» per recipient. Whatever is
    prepared, a letter that went out and rests on something changed since carries «Abgleich erledigt» (``reconcile``)."""
    channel = default_channel(files)
    day = today.isoformat()
    last = st.get("last") or {}
    meaning = last.get("consequence") or {}
    extra = {"reconcile": last.get("version"), "changed": meaning.get("text") if meaning.get("kind") == "contradiction"
             else f"versandt mit früherem Stand – prüfen: {', '.join(last['stale'])}"} \
        if last and (meaning.get("kind") == "contradiction" or last.get("stale")) else {}
    rest = st.get("rest")
    if rest:  # the package's other recipients keep their «Versandt am», on the version approved
        extra["rest"] = {"version": rest["version"], "earliest": rest.get("earliest"), "stale": rest.get("stale"), "channel": channel,
                         "recipients": [{"to": r.get("to"), "title": r.get("title") or FOLDERS.get(r.get("to"), r.get("to")), "recipient": r.get("recipient"),
                                         "dispatched": None, "date": day, "channel": channel} for r in rest.get("pending") or ()]}
    if not draft.get("text"):
        return {"kind": "none", **extra}
    rows = []
    shown = approval if st["approved"] else None
    for r in (shown.get("recipients") if shown else st["recipients"]) or ():
        done = next((d for d in st["dispatched"] if d["recipient"] == r.get("to")), None)
        rows.append({"to": r.get("to"), "title": r.get("title") or FOLDERS.get(r.get("to"), r.get("to")), "recipient": r.get("recipient"),
                     "dispatched": done, "date": day, "channel": channel})
    first = earliest(shown, events, st["form"]) if shown else (swiss_day(st["legacy_copy"]["at"]) if st["legacy_copy"] else None)
    if st["state"] == "entwurf":
        return {"kind": "approve", "label": "Freigeben", "recipients": rows, "earliest": first, "legacy": st["legacy_copy"], "channel": channel,
                "decision": st["decision"], "conflicts": len(all_conflicts(draft)), "gaps": gaps(draft), **extra}
    if st["state"] == "freigegeben" and st["stale"]:
        return {"kind": "stale", "label": "Erneut freigeben", "stale": f"Freigabe veraltet: {st['stale'][0]}", "reasons": st["stale"],
                "recipients": rows, "earliest": first, "version": shown.get("version"), "channel": channel, **extra}
    if st["state"] == "freigegeben":
        return {"kind": "dispatch", "label": "Brief kopieren", "recipients": rows, "earliest": first, "version": shown.get("version"),
                "channel": channel, "bundle": bool(st["approved"]["bundle"]), **extra}
    return {"kind": "dispatched", "recipients": rows, "version": shown.get("version") if shown else None,
            "line": " · ".join(f"versandt am {_day(r['dispatched']['date'])}" for r in rows if r["dispatched"]), **extra}


# -- the approval's record ---------------------------------------------------------------------------------------------------

def refusal(case, draft, version, decisions=(), draft_stale=False):
    """Why «Freigeben» is refused now, as (status, message) in the order the handler meets them, or None. ``decisions``:
    the decisions still open (open_decisions)."""
    if ((case or {}).get("intake") or {}).get("study"):
        return 409, "Eine Studienkopie wird nicht freigegeben."
    if not draft or not draft.get("text") or version != draft.get("version"):
        return 409, "Der Entwurf hat sich seit dem Laden geändert; bitte neu laden."
    if draft_stale:
        return 422, "Neue Unterlagen sind noch nicht gelesen."
    n = gaps(draft)
    if n:
        return 422, f"Noch {n} Lücke{'' if n == 1 else 'n'} im Brief"
    lost = missing_required(draft)
    if lost:
        return 422, "Pflichtteil fehlt: " + ", ".join(f"{r['title']} ({r['basis']})" for r in lost)
    if decisions:
        return 422, "Zuerst entscheiden: " + ", ".join(decisions)
    if all_conflicts(draft):
        return 422, "Ihr Text betraf einen geänderten Absatz: bitte prüfen"
    return None


def frozen_meaning(draft, listed, events, assessment=None):
    """What an approved version means per recipient, frozen with it: {to: {asks, answers, addressed}}: what its letter asks
    (each with the judgment it waits for), the questions it answers and those it takes up (completion.addressed), as
    dispatch_args would record them now. A dispatch of this version records these, whatever a later draft asks."""
    form, kind, out = draft.get("form") or draft.get("kind"), draft.get("kind"), {}
    for r in draft.get("recipients") or ():
        main = form in (r.get("forms") or [form])
        out[r["to"]] = {"asks": asks(form, kind, listed, events, assessment, draft.get("respond_by"), r["to"]) if main else [],
                        "answers": answers(kind, form, assessment, events) if main else [],
                        "addressed": addressed(kind, form, assessment, events) if main else []}
    return out


def changed_words(draft):
    """How much of the approved letter is the handler's own wording: {total, changed}, the words of the final text and
    those among them that the prepared text (each part's base) did not have in that place (inserted or replaced; words
    only taken out count as one each). Counted by word, so a long sentence replaced by one of the same length counts."""
    import difflib
    base = " ".join(str(p.get("base") or "") for p in draft.get("parts") or ()).split()
    final = " ".join(str(p.get("text") or "") for p in draft.get("parts") or ()).split()
    changed = sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, base, final, autojunk=False).get_opcodes() if tag != "equal")
    return {"total": len(final), "changed": changed}


def stand(process, listed):
    """«Stand bei Freigabe», as the approval's event keeps it (no case content): what the case's requirements were built
    from when a letter was approved, so that a rule changed since is seen and a recall can find the letter: {workflow
    {id, version}, knowledge [«knowledge#<id>@v<n>» of every Knowledge item the case's process carries], items_sha256
    (the documents asked now, offered and later, the letter's questions and the next action, as the replay compares
    them), facts_sha256 (every established fact with its value)}. Model-free, from the case's own process and items."""
    process, listed = process or {}, list(listed or ())
    refs = sorted({r for group in ("documents", "facts", "steps") for node in process.get(group) or () for r in node.get("source_refs") or ()
                   if str(r).startswith("knowledge#")})
    pick = lambda kind, ask: sorted(i["key"] for i in listed if i["kind"] == kind and i.get("ask") == ask)
    action = next((i for i in listed if i["kind"] == "next_action"), {})
    shape = {"needs": sorted(i["key"] for i in listed if i["kind"] == "document"), "now": pick("document", "now"), "offered": pick("document", "proposed"),
             "later": pick("document", "later"), "questions": pick("letter_question", "now"), "next_action": action.get("action")}
    facts = {i["key"]: i.get("value") for i in listed if i["kind"] == "fact" and i.get("value") not in (None, "", "offen")}
    return {"workflow": {"id": process.get("id"), "version": process.get("version")}, "knowledge": refs,
            "items_sha256": sha(json.dumps(shape, ensure_ascii=False, sort_keys=True)),
            "facts_sha256": sha(json.dumps(facts, ensure_ascii=False, sort_keys=True, default=str))}


def stand_record(process, listed, draft=None, files=()):
    """«Stand bei Freigabe», as the Versandpaket keeps it (the case's own record, with its content): ``stand`` and, in
    words, what a third person needs to say why the letter went out as it did: the Knowledge items by title and
    version, each document and question the letter asks with where the need comes from (the process, a Knowledge item,
    the handler) and its legal basis, each established fact with its value and its source (the file and page it was
    read from, or the handler who set it), and each part of the letter as the form's wording or the handler's own."""
    process, listed = process or {}, list(listed or ())
    names = {f.get("id"): f.get("name") for f in files or ()}
    titles = {}
    for group in ("documents", "facts", "steps"):
        for node in process.get(group) or ():
            for r in node.get("source_refs") or ():
                if str(r).startswith("knowledge#"):
                    titles.setdefault(r, node.get("title") or node.get("question") or node.get("id"))
    word = lambda i: (i.get("label") or {}).get("de") or i.get("title") or i["key"]

    def origin(i):
        o = str(i.get("origin") or "")
        return "Wissen" if o.startswith("knowledge") else "Fallbearbeitung" if o.startswith("edit") else "Prozess"

    def source(i):
        if i.get("verdict") == "set_by_handler" or (i.get("handler") or {}).get("by"):
            return {"by": "Fallbearbeitung"}
        if i.get("stated_as") == "computed" or i.get("verdict") == "derived":
            return {"by": "berechnet"}  # follows from the case's own record (its letters, dates and answers), by the process's rule
        e = next(iter(i.get("evidence") or ()), None)
        return {"by": "Akte", "file": names.get(e.get("file"), e.get("file")), "page": e.get("page")} if e else {"by": "ohne Quelle"}
    return {**stand(process, listed),
            "knowledge_titles": [{"ref": r, "title": titles.get(r)} for r in sorted(titles)],
            "asked": [{"kind": "Unterlage" if i["kind"] == "document" else "Frage", "what": word(i), "from": origin(i),
                       **({"legal_basis": i["legal_basis"]} if i.get("legal_basis") else {})}
                      for i in listed if i["kind"] in ("document", "letter_question") and i.get("ask") == "now"],
            "facts": [{"fact": i["key"], "question": word(i), "value": i.get("value"), "source": source(i)}
                      for i in listed if i["kind"] == "fact" and i.get("value") not in (None, "", "offen")],
            "parts": [{"part": p.get("part"), "wording": "Fallbearbeitung" if p.get("edited") else "Formular"} for p in (draft or {}).get("parts") or ()]}


def stand_text(record, approval=None):
    """The record as one plain page of the Versandpaket («Stand bei Freigabe.txt»)."""
    r, a = record or {}, approval or {}
    lines = ["Stand bei Freigabe", ""]
    if a.get("expert") or a.get("at"):
        lines += [f"Freigegeben von {a.get('expert') or '—'} am {a.get('at') or '—'}", ""]
    lines += [f"Prozess: {(r.get('workflow') or {}).get('id')} · Fassung {(r.get('workflow') or {}).get('version')}", "", "Wissen (Regeln, auf denen der Fall beruht):"]
    lines += [f"- {k.get('title') or '—'} ({k['ref']})" for k in r.get("knowledge_titles") or ()] or ["- keine"]
    lines += ["", "Der Brief verlangt:"]
    lines += [f"- {x['kind']}: {x['what']} · aus: {x['from']}" + (f" · {x['legal_basis']}" if x.get("legal_basis") else "") for x in r.get("asked") or ()] or ["- nichts"]
    lines += ["", "Feststellungen, wie der Fall sie bei der Freigabe hielt:"]
    said = lambda v: "ja" if v is True else "nein" if v is False else v
    read = [f for f in r.get("facts") or () if (f.get("source") or {}).get("by") != "berechnet"]
    for f in read:
        s = f.get("source") or {}
        where = f"{s.get('file')}" + (f", S. {s['page']}" if s.get("page") else "") if s.get("by") == "Akte" else s.get("by")
        lines.append(f"- {f.get('question')}: {said(f.get('value'))} · Quelle: {where}")
    lines += [] if read else ["- keine"]
    derived = [f for f in r.get("facts") or () if (f.get("source") or {}).get("by") == "berechnet"]
    if derived:
        lines += ["", "Daraus berechnet (nach der Regel des Prozesses):"] + [f"- {f.get('question')}: {said(f.get('value'))}" for f in derived]
    own = [p["part"] for p in r.get("parts") or () if p.get("wording") == "Fallbearbeitung"]
    lines += ["", f"Wortlaut: {len(r.get('parts') or ())} Teile, davon von der Fallbearbeitung geändert: {len(own)}" + (f" ({', '.join(str(x) for x in own)})" if own else ""),
              "", f"Anforderungen (SHA-256): {r.get('items_sha256')}", f"Feststellungen (SHA-256): {r.get('facts_sha256')}"]
    return "\n".join(lines) + "\n"


def rule_changed(approval, now):
    """Whether a rule changed under an approval: the Knowledge the case's process carries is another than at the approval
    (an item released, withdrawn or in a new version) and the case's requirements are other than they were. An approval
    from before the record was kept (no ``stand``) is never stale for it."""
    was = (approval or {}).get("stand")
    return bool(was and now and was.get("knowledge") != now.get("knowledge") and was.get("items_sha256") != now.get("items_sha256"))


def approval_record(draft, premise_, assessment=None, run_id=None, files_digest=None, op_id=None, deadline=None, relies=(), marks=None,
                    file_ids=None, meaning=None, addresses=None, stand_=None):
    """The fields of «action.approved»: the version and what it consists of, the premise (``premise_``: premise() now),
    the options chosen, the reviewed legal content it rests on (``relies``: relied_elements) with the jurists' marks on it
    as they stand (``marks``: the marks that hold now), the files of the case it was given on (``file_ids``) and what it
    means per recipient (``meaning``: frozen_meaning), which its dispatch records."""
    return {"version": draft["version"], "form": draft.get("form") or draft.get("kind"), "action_kind": draft.get("kind"), "title": draft.get("title"),
            "words": changed_words(draft),
            # ``addresses``: the mail address shown beside «Freigeben» per recipient (found in the file or set by the handler)
            "recipients": [{**{k: r[k] for k in ("to", "recipient", "title", "forms", "titles")},
                            **({"address": str(addresses.get(r["to"]) or "")} if addresses is not None else {})} for r in draft.get("recipients") or ()],
            "respond_by": draft.get("respond_by"), "premise": premise_,
            "chosen": (assessment or {}).get("chosen"), "options_sha256": (assessment or {}).get("options_sha256"),
            "text_sha256": sha(draft.get("text")), "also": [{"kind": a["kind"], "sha256": sha(a["text"])} for a in draft.get("also") or () if a.get("text")],
            "parts": [[p["part"], sha(p["text"])] for p in draft.get("parts") or ()], "run_id": run_id, "files_digest": files_digest, "op_id": op_id,
            "relies": list(relies or ()), "relies_marks": marks_of(relies, marks), **({"file_ids": list(file_ids)} if file_ids is not None else {}),
            **({"meaning": meaning} if meaning is not None else {}),
            **({"stand": stand_} if stand_ else {}),  # «Stand bei Freigabe» (stand): workflow, Knowledge versions, requirements, facts
            **({"deadline": deadline} if deadline else {})}


def expected(form, kind, listed, events, assessment, process, stage, day, respond_by=None, fallback=None, set_date=None):
    """What the letter ``form`` (action ``kind``) asks, in words, and when the case looks at it again once it goes out on
    ``day`` (the approval's day): (awaited, follow_up), the follow-up {due, days, if_sent} counted from the dispatch, the
    reply date the letter sets, else ``fallback`` (the case's follow-up). ``set_date``: a date the handler set for this
    step ({due, set}): it comes first, as it does for the wait after the dispatch (clock.follow_up). The Versandpaket's
    Wiedervorlage, the file note's «Erwartet» and the date beside «Freigeben» are all written from it, so all say the same."""
    awaited = [a["what"] for a in asks(form, kind, listed, events, assessment, respond_by)]
    if set_date:
        return awaited, {"due": set_date, "set": True}
    look, days = next_look(process, form, stage, day, respond_by), look_days(process, form, stage)
    return awaited, ({"due": look, "days": days, "if_sent": day} if look and not respond_by and days else look or fallback)


def look_days(process, form, stage):
    """The days after the letter's dispatch the clock looks at the case again (its code's rule at this stage), or None."""
    code = record_of(form)[2]
    rule = next((r for r in (process or {}).get("clock") or () if code and code in r.get("after", ()) and (r.get("stages") is None or stage in r["stages"])), None)
    return int(rule["days"]) if rule else None


def filed_days(process, events, stage):
    """The days after its dispatch that the Versandpaket of the latest letter sent filed as the Wiedervorlage (expected:
    the clock's rule of its code at the stage of its action kind, else at ``stage``), or None: a letter that set a reply
    date, or one the clock has no rule for. The wait after the dispatch keeps this (clock.follow_up)."""
    from .clock import last_dispatch
    sent = last_dispatch(events)
    if not sent or sent.get("respond_by"):
        return None
    own = (((process or {}).get("action_kinds") or {}).get(sent.get("action_kind")) or {}).get("stage")
    return look_days(process, sent.get("form"), own or stage)


def next_look(process, form, stage, day, respond_by=None):
    """The day the case is looked at again once the letter goes out on ``day``: the reply date it sets, else the clock's
    follow-up of its code at this stage (an assessment: 90 days), else None."""
    if respond_by:
        return respond_by
    days, d = look_days(process, form, stage), parse_date(day)
    return (d + timedelta(days=days)).isoformat() if days and d else None


def dispatch_args(approval, recipient, date_, channel, listed, events, assessment=None):
    """The «add_dispatch» edit of one recipient of an approved version: the account's entry of its form, what it asks and
    which questions it answers (its number is drawn by the store): as the version was approved (its ``meaning``), never
    as a later draft has it; an approval recorded before that field is read from the case as it stands."""
    row = next((r for r in approval.get("recipients") or () if r.get("to") == recipient), None) or {}
    forms = row.get("forms") or [approval.get("form")]
    form = approval.get("form") if approval.get("form") in forms else forms[0]
    _, kind, code = record_of(form)
    main = form == approval.get("form")
    frozen = (approval.get("meaning") or {}).get(recipient)
    if frozen is not None:
        return {"version": approval.get("version"), "form": form, "recipient": recipient, "to": recipient if recipient in PARTIES else "andere",
                "date": date_, "channel": channel, "kind": kind, "code": code if code != "11" else None,
                "title": approval.get("title") if main else (row.get("titles") or {}).get(form) or form, "line": row.get("recipient"),
                "asks": list(frozen.get("asks") or ()), "answers": list(frozen.get("answers") or ())}
    return {"version": approval.get("version"), "form": form, "recipient": recipient, "to": recipient if recipient in PARTIES else "andere",
            "date": date_, "channel": channel, "kind": kind, "code": code if code != "11" else None,
            "title": approval.get("title") if main else (row.get("titles") or {}).get(form) or form, "line": row.get("recipient"),
            "asks": asks(form, approval.get("action_kind"), listed, events, assessment, approval.get("respond_by"), recipient) if main else [],
            "answers": answers(approval.get("action_kind"), form, assessment, events) if main else []}


def note_lines(events, edits=None, titles=None):
    """The file note's lines on the letter: «Zum Versand freigegeben am … (Person)» while approved and not sent, and per
    recipient «Versandt: <Titel> an <Empfänger> am <Datum> (<Kanal>, <Person>)», only from a dispatch in force."""
    out = []
    sent = sent_letters(events, edits)
    for a in approvals(events):
        mine = [d for d in sent if d["version"] == a.get("version")]
        pending = [r for r in a.get("recipients") or () if r.get("to") not in {d["recipient"] for d in mine}]
        if pending and a is approvals(events)[-1]:
            out.append(f"Zum Versand freigegeben am {_day(swiss_day(a.get('at')))} ({a.get('expert')}): {a.get('title')}")
    for d in sent:
        out.append(f"Versandt: {d['title'] or 'Schreiben'} an {TO_WORDS.get(d['recipient'], d['recipient'])} am {_day(d['date'])} "
                   f"({CHANNELS.get(d['channel'], d['channel'])}, {d['by']})")
    return out


# -- what a reply prepares (the plan's hook, items.build_items: slice A calls it beside its premise assessment) -------------

def consequence_action(graph, here, state, result, files, events):
    """The action a reply prepares, for the plan, or None. When every ask of the last letter that went out is met by
    evidence in a reply's file and one of them was asked for a judgment (``blocks``), the stage's own action is due again
    (for an assessment: the assessment, now with that evidence), with the reason naming what came and what can now be
    judged; the letter's follow-up date is then no reason to wait any more. Nothing for a reply that meets nothing, part
    of the asks only (the wait goes on for the rest), or a refusal (the handler judges without it). ``here``: the stage
    the plan is at; ``state``: the case's state (its account and facts). Model-free."""
    acc = (state or {}).get("account")
    sent = sorted(sent_letters(events), key=lambda d: (str(d.get("date") or ""), str(d.get("at") or "")))
    planned = (here or {}).get("action") or {}
    if not sent or acc is None or not planned:
        return None
    last = sent[-1]
    if planned.get("kind") != last.get("action_kind"):
        return None  # the case moved on to another stage: its own plan governs
    entry = next((e for e in acc.get("entries") or () if (e.get("dispatch") or {}).get("version") == last.get("version")
                  and (e.get("dispatch") or {}).get("recipient") == last.get("recipient")), None)
    if entry is None:
        return None
    meaning = consequence(fulfilment(entry, acc, files, result, graph))
    if meaning["kind"] not in ("resolved", "remainder"):
        return None
    came = ", ".join(dict.fromkeys(j["ask"] for j in meaning["judgments"] if j.get("ask")))
    judged = ", ".join(dict.fromkeys(j["judgment"] for j in meaning["judgments"] if j.get("judgment")))
    # where the area says what follows its assessment (options.follow_on), the letter is that short follow-on: what came,
    # what it settles, the next step; never the assessment written out again
    from . import options
    short = planned["kind"] == "A5" and str(last.get("form") or "").startswith("A5") and options.follow_on(options.load((graph or {}).get("id")))
    follow = {"form": options.FOLLOW_ON, "title": short["title"]} if short else {"title": planned.get("title")}
    if meaning["kind"] == "remainder":
        if not short:
            return None
        part = meaning["judgments"][0]["part"]
        reason = f"teilweise belegt: {_chf(part['amount'])} von {_chf(part['of'])}; Rest nachfragen"
    else:
        reason = f"eingegangen: {came}" + (f"; jetzt zu beurteilen: {judged}" if judged else "")
    return {"kind": planned["kind"], **follow, "next_in_days": planned.get("next_in_days"), "follow_up": planned.get("follow_up"),
            "skip_if": None, "reason": reason,
            "consequence": {"version": last.get("version"), "kind": meaning["kind"], "judgments": meaning["judgments"],
                            "sent": last.get("date"), "title": last.get("title")}}


def _chf(value):
    from .claims import chf
    return chf(value)
