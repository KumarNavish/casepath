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
REASONS = ("Entscheid geändert", "Voraussetzung geändert", "Neue Unterlagen", "Pflichtteil fehlt", "Schritt geändert", "Empfänger geändert",
           "Beilagen geändert", "Datum", "Text geändert")
REPLY = "Rückmeldung"
SHA_EMPTY = hashlib.sha256(b"").hexdigest()


def sha(text):
    return hashlib.sha256(str(text or "").encode()).hexdigest()


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
        other = next((p for p in parties if p is not own and not re.search(r"kanzlei|anwalt|versicher|protekta|rechtsschutz", f"{label(p)} {p['value']}", re.I)), None)
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
    greeting = letters.greeting(parties) if role == "kunde" else "Sehr geehrte Damen und Herren"
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
    for a in draft.get("also") or ():
        if a.get("text") is None:
            continue
        a_parts, a_conflicts = merge(a.get("base_parts") or [("text", a["text"])], saved.get(a["kind"]))
        a.update(parts=a_parts, conflicts=a_conflicts, draft_id=(saved.get(a["kind"]) or {}).get("id"), text=joined(a_parts) if a_parts else a["text"])
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
    not answered, the prospects for an assessment (in every area), and the assessment's blocking decisions."""
    defined = {f["id"] for f in (process or {}).get("facts") or ()} if process else None
    out = []
    for fact in (draft or {}).get("needs") or ():
        if (defined is None or fact in defined) and _answered(facts, fact) is None:
            out.append(DECISION_WORDS.get(fact, fact))
    if str((draft or {}).get("kind") or "") == "A5" and str((draft or {}).get("form") or "").startswith("A5") and _answered(facts, "aussichten") is None:
        out.append("Erfolgsaussichten")
    for b in (assessment or {}).get("blocking") or ():
        if b.get("kind") == "decision":
            out.append(DECISION_WORDS.get(b.get("key"), b.get("text") or b.get("key")))
    return list(dict.fromkeys(out))


def premise(draft, facts, assessment=None):
    """What the letter rests on, as it stands now: the assessment's premise and each decision the form needs (and the
    prospects for an assessment), {fact: value}."""
    out = {k: _norm((facts or {}).get(k)) if k in (facts or {}) else _norm(v) for k, v in ((assessment or {}).get("premise") or {}).items()}
    for fact in list((draft or {}).get("needs") or ()) + (["aussichten"] if str((draft or {}).get("kind") or "") == "A5" else []):
        out[fact] = _norm((facts or {}).get(fact))
    return out


def changed_premise(stored, facts):
    """The facts of a stored premise whose value is no longer the same: [fact]."""
    return [k for k, v in (stored or {}).items() if _norm(v) != _norm((facts or {}).get(k))]


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
                    "deadline": a.get("deadline"), "respond_by": a.get("respond_by")})
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
    return not (due and at) or (due - (today or date.today())).days >= (due - at).days - 3


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

def asks(form, kind, listed, events, assessment=None, respond_by=None, role="kunde"):
    """What the letter asks of its recipient, as the account's asks of the dispatch: an assessment the assessment's asks
    (the residual lines ticked and the missing fact of each conditional answer); a first request or a question back the
    letter's asked lines; a pending or status letter a reply by its date. Each {what, of, by, kind, ref, key, warns}."""
    form = str(form or "")
    if kind == "A5" and form.startswith("A5") and form != "A5_aussichtslos":
        return [{"what": a.get("what"), "of": role, "by": respond_by, "kind": a.get("kind"), "ref": a.get("ref"), "key": a.get("key")}
                for a in (assessment or {}).get("asks") or () if a.get("what")]
    if form in ("A1", "A4"):
        docs = [{"what": (i.get("label") or {}).get("de") or i.get("value"), "of": role, "by": respond_by, "kind": "document", "ref": i["key"]}
                for i in letters.asked(listed, events, "document")] if form == "A1" else []
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
    return [{"what": q.get("text"), "answers": q.get("entry")} for q in (assessment or {}).get("questions") or ()
            if q.get("text") and isinstance(q.get("entry"), int) and (q.get("state") == "beantwortet" or q.get("item_id") in taken)]


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
    fulfilled, partial}. Per ask, against the entries of its addressee dated after it: a claim line is met when the
    claim is documented by a receipt located in a file of such an entry; a document when account.held names such a file;
    a fact when it is established with a quote from such a file; a request carried over when its row is closed and, for a
    document, held as above; a reply by any such entry with its file. An ask whose row was closed by words alone is
    «Antwort ohne Beleg – prüfen»; a refusal or a promise meets nothing."""
    from . import account
    held = held or account.held
    result = result or {}
    later = [e for e in (acc or {}).get("entries") or () if e.get("from") == entry.get("to") and e.get("date") and e["date"] > entry.get("date", "")
             and not e.get("dispatch")]
    reply_files = set().union(*[_entry_files(e, files) for e in later]) if later else set()
    later_n = {e["n"] for e in later}
    rows = {r["id"]: r for r in (acc or {}).get("requests") or ()}
    claims = ((result.get("brief") or {}).get("claims")) or []
    needs = {d["id"]: d for d in (process or {}).get("documents") or ()}
    met, open_, unbelegt = [], [], []
    for i, ask in enumerate(entry.get("asks") or ()):
        kind, ref, ok = ask.get("kind"), ask.get("ref"), False
        if kind == "claim":
            claim = claims[ref] if isinstance(ref, int) and 0 <= ref < len(claims) else None
            receipt = ((claim or {}).get("receipt") or [None])
            receipt = receipt[0] if isinstance(receipt, list) else receipt
            ok = bool(claim and claim.get("documented") and (receipt or {}).get("file") in reply_files)
        elif kind == "document":
            found = held({"what": ask.get("what"), "need": ref, "title": (needs.get(ref) or {}).get("title")}, [f for f in files or () if f.get("id") in reply_files])
            ok = bool(found and found.get("file") in reply_files)
        elif kind == "fact":
            ok = any(f.get("fact") == ref and f.get("status") == "established" and f.get("verdict") == "accepted"
                     and any(c.get("file") in reply_files for c in f.get("citations") or ()) for f in result.get("facts") or ())
        elif kind == "request":
            row = rows.get(ref) or {}
            closed = bool(row.get("answered"))
            doc = any(_head(d.get("title")) and _head(d.get("title")) == _head(row.get("what")) for d in needs.values())
            found = held({"what": row.get("what"), "request": ref}, [f for f in files or () if f.get("id") in reply_files]) if doc else None
            ok = closed and (not doc or bool(found and found.get("file") in reply_files))
        elif kind == "reply":
            ok = bool(later and reply_files)
        own = rows.get(f"r{entry['n']}.{i}") or {}
        if ok:
            met.append(ask)
        elif (own.get("answered") or {}).get("n") in later_n:
            unbelegt.append(ask)  # closed by words, nothing in a file: an answer without evidence
        else:
            open_.append(ask)
    total = len(entry.get("asks") or ())
    return {"acknowledged": bool(later), "replies": sorted(later_n), "met": met, "open": open_, "unbelegt": unbelegt,
            "fulfilled": bool(later) and total > 0 and len(met) == total, "partial": 0 < len(met) < total}


# -- the state --------------------------------------------------------------------------------------------------------------

def _day(value):
    d = parse_date(value)
    return d.strftime("%d.%m.%Y") if d else ""


def _bundle(events, version):
    return next((e for e in reversed(events or ()) if e.get("kind") == "bundle.saved" and e.get("version") == version), None)


def default_channel(files):
    """The channel of the customer's last message: an e-mail file (.eml, .msg) gives «email», anything else «post»."""
    newest = max(files or (), key=lambda f: str(f.get("created_at") or ""), default=None)
    if not newest:
        return "post"
    return "email" if newest.get("kind") == "email" or str(newest.get("name") or "").lower().endswith((".eml", ".msg")) else "post"


def earliest(approval, events, form):
    """The first day the approved letter can have gone out: its approval day, a copy of the same text, or a copy of the
    same form by a browser before this release, whichever came first."""
    days = [str(approval.get("at") or "")[:10]]
    days += [str(e.get("at") or "")[:10] for e in events or () if e.get("kind") == "letter.copied" and e.get("measure")
             and e.get("text_sha256") and e.get("text_sha256") == approval.get("text_sha256")]
    days += [str(e.get("at") or "")[:10] for e in events or () if is_legacy(e) and not e.get("also") and e.get("form") in (None, form)]
    return min(d for d in days if d) if any(days) else None


def validity(approval, draft, facts, assessment=None, process=None, unread=(), files=(), events=(), today=None):
    """Why an approval no longer holds, recomputed now: [reasons] (empty: it holds). It holds only while its version is
    the current one, its form the prepared one, its premise as stored, no decision is open, every required part is in
    the letter, no file arrived unread after it (a later «trotzdem verwenden» counts) and enough time is left before the
    reply date it froze (the form's period less three days)."""
    out = []
    if not draft or approval.get("form") != (draft.get("form") or draft.get("kind")):
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
    for fact in changed_premise(approval.get("premise"), facts):
        out.append("Entscheid geändert" if fact in DECISION_FACTS else "Voraussetzung geändert")
    if open_decisions(draft, facts, assessment, process):
        out.append("Entscheid geändert")
    if any(b.get("kind") == "gap" for b in (assessment or {}).get("blocking") or ()):
        out.append("Text geändert")
    if draft and missing_required(draft):
        out.append("Pflichtteil fehlt")
    arrived = [str(f.get("created_at") or "") for f in files or () if f.get("id") in set(unread or ()) and str(f.get("created_at") or "") > str(approval.get("at") or "")]
    if arrived and not any(e.get("kind") == "letter.unblocked" and str(e.get("at") or "") >= max(arrived) for e in events or ()):
        out.append("Neue Unterlagen")
    if not enough_time(approval.get("respond_by"), approval.get("at"), today):
        out.append("Datum")
    return sorted(set(out), key=REASONS.index)


def state(case, listed, draft, events, edits, account=None, assessment=None, files=(), today=None, facts=None, process=None, unread=(),
          result=None, prepared_at=None, follow_up=None, held=None):
    """Where the prepared letter stands after the decision, recomputed on every read: {state (entwurf | freigegeben |
    versandt), version, form, approved {by, at, version, form, respond_by, bundle}, dispatched [{recipient, date, channel,
    by}], pending, valid, stale [reasons], premise_changed [questions], last (the last letter dispatched: {form, title,
    dispatched, acknowledged, fulfilled, partial, open, unbelegt}), acknowledged, fulfilled, partial, waiting_until,
    legacy_copy, decision, bucket, status, date, bar}. ``bucket``/``status`` are set only where the letter decides the
    case list's row (listing.stand decides the rest)."""
    today = today or date.today()
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
    if approval and not same and not ({r.get("to") for r in approval.get("recipients") or ()} - done_for(approval)):
        approval = None  # the latest approval went out to every recipient: the letter prepared now is a new one
    out = {"state": "entwurf", "version": version, "form": form, "approved": None, "dispatched": [], "pending": [], "valid": False, "stale": [],
           "premise_changed": [], "last": None, "acknowledged": False, "fulfilled": False, "partial": False, "waiting_until": None,
           "legacy_copy": None, "decision": None, "bucket": None, "status": None, "date": None, "recipients": draft.get("recipients") or []}
    needed = open_decisions(draft, facts, assessment, process) if draft.get("text") else []
    out["decision"] = needed[0] if needed else None
    questions = {i["key"]: (i.get("label") or {}).get("de") or i["key"] for i in listed or () if i.get("kind") == "fact"}
    if approval:
        mine = [d for d in sent if d["version"] == approval.get("version")]
        bundle = _bundle(events, approval.get("version"))
        out["approved"] = {"by": approval.get("expert"), "at": approval.get("at"), "version": approval.get("version"), "form": approval.get("form"),
                           "title": approval.get("title"), "respond_by": approval.get("respond_by"),
                           "bundle": {"sha256": bundle.get("sha256"), "bytes": bundle.get("bytes")} if bundle else None}
        out["dispatched"] = [{"recipient": d["recipient"], "date": d["date"], "channel": d["channel"], "by": d["by"], "edit": d["edit"]} for d in mine]
        out["pending"] = [r for r in approval.get("recipients") or () if r.get("to") not in {d["recipient"] for d in mine}]
        out["state"] = "freigegeben" if out["pending"] else "versandt"
        out["stale"] = validity(approval, draft, facts, assessment, process, unread, files, events, today)
        out["valid"] = not out["stale"]
    # the last letter that went out: what it asked, whether the addressee answered, what is met by evidence
    went = [a for a in every if any(d["version"] == a.get("version") for d in sent)]
    last = went[-1] if went else None
    if last:
        entry = next((e for e in (account or {}).get("entries") or () if (e.get("dispatch") or {}).get("version") == last.get("version")), None)
        how = fulfilment(entry, account, files, result, process, held) if entry and account else {}
        mine = [d for d in sent if d["version"] == last.get("version")]
        changed = changed_premise(last.get("premise"), facts)
        out["last"] = {"form": last.get("form"), "title": last.get("title"), "version": last.get("version"), "respond_by": last.get("respond_by"),
                       "dispatched": [{"recipient": d["recipient"], "date": d["date"], "channel": d["channel"], "by": d["by"]} for d in mine],
                       "asks": [a.get("what") for a in (entry or {}).get("asks") or ()], **{k: how.get(k) for k in ("acknowledged", "fulfilled", "partial")},
                       "open": [a.get("what") for a in how.get("open") or ()], "unbelegt": [a.get("what") for a in how.get("unbelegt") or ()],
                       "met": [a.get("what") for a in how.get("met") or ()]}
        out["premise_changed"] = [questions.get(k, k) for k in changed]
        gone = _undone(events)
        out["last"]["stale"] = sorted({r for e in events or () if e.get("kind") == "action.dispatched" and e.get("version") == last.get("version")
                                       and e.get("edit_id") not in gone for r in e.get("stale") or ()}, key=lambda r: REASONS.index(r) if r in REASONS else 99)
        out.update(acknowledged=bool(how.get("acknowledged")), fulfilled=bool(how.get("fulfilled")), partial=bool(how.get("partial")))
        if not how.get("acknowledged"):
            out["waiting_until"] = last.get("respond_by") or (follow_up or {}).get("due")
    out["legacy_copy"] = legacy_copy(events, form, prepared_at) if draft.get("text") and not out["approved"] else None
    # the case list's row, where the letter decides it; what the last letter sent says, only while nothing newer is approved
    current_last = last is not None and (approval is None or approval is last)
    if approval and not out["approved"]["bundle"] and out["state"] == "freigegeben":
        out.update(bucket="fehlgeschlagen", status="Versandpaket fehlt")
    elif out["state"] == "freigegeben" and out["stale"]:
        out.update(bucket="urteil", status=f"Freigabe veraltet: {out['stale'][0]}")
    elif out["state"] == "freigegeben":
        out.update(bucket="versandbereit", status="freigegeben, Versand offen", date=str(approval.get("at") or "")[:10])
    elif out["legacy_copy"]:
        out.update(bucket="versandbereit", status="kopiert, Versand nicht bestätigt", date=str(out["legacy_copy"]["at"] or "")[:10])
    elif current_last and (out["premise_changed"] or out["last"]["stale"]):
        what = out["premise_changed"] or out["last"]["stale"]
        out.update(bucket="urteil", status=f"versandt mit früherem Stand – prüfen: {', '.join(what)}")
    elif current_last and out["acknowledged"] and out["last"]["asks"]:
        if out["partial"]:
            out.update(bucket="urteil", status="teilweise erfüllt")
        elif out["last"]["unbelegt"] and not out["fulfilled"]:
            out.update(bucket="urteil", status="Antwort ohne Beleg – prüfen")
        elif not out["fulfilled"]:
            out.update(bucket="urteil", status="Antwort eingegangen")
    out["bar"] = bar(out, draft, approval, events, files, today)
    return out


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
    file note; a stale approval «Erneut freigeben»; after the dispatch «versandt am …» per recipient."""
    channel = default_channel(files)
    day = today.isoformat()
    if not draft.get("text"):
        return {"kind": "none"}
    rows = []
    shown = approval if st["approved"] else None
    for r in (shown.get("recipients") if shown else st["recipients"]) or ():
        done = next((d for d in st["dispatched"] if d["recipient"] == r.get("to")), None)
        rows.append({"to": r.get("to"), "title": r.get("title") or FOLDERS.get(r.get("to"), r.get("to")), "recipient": r.get("recipient"),
                     "dispatched": done, "date": day, "channel": channel})
    first = earliest(shown, events, st["form"]) if shown else (str(st["legacy_copy"]["at"])[:10] if st["legacy_copy"] else None)
    if st["state"] == "entwurf":
        return {"kind": "approve", "label": "Freigeben", "recipients": rows, "earliest": first, "legacy": st["legacy_copy"], "channel": channel,
                "decision": st["decision"], "conflicts": len(all_conflicts(draft)), "gaps": gaps(draft)}
    if st["state"] == "freigegeben" and st["stale"]:
        return {"kind": "stale", "label": "Erneut freigeben", "stale": f"Freigabe veraltet: {st['stale'][0]}", "reasons": st["stale"],
                "recipients": rows, "earliest": first, "version": shown.get("version"), "channel": channel}
    if st["state"] == "freigegeben":
        return {"kind": "dispatch", "label": "Brief kopieren", "recipients": rows, "earliest": first, "version": shown.get("version"),
                "channel": channel, "bundle": bool(st["approved"]["bundle"])}
    return {"kind": "dispatched", "recipients": rows, "version": shown.get("version") if shown else None,
            "line": " · ".join(f"versandt am {_day(r['dispatched']['date'])}" for r in rows if r["dispatched"])}


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


def approval_record(draft, premise_, assessment=None, run_id=None, files_digest=None, op_id=None, deadline=None):
    """The fields of «action.approved»: the version and what it consists of, the premise (``premise_``: premise() now)
    and the options chosen."""
    return {"version": draft["version"], "form": draft.get("form") or draft.get("kind"), "action_kind": draft.get("kind"), "title": draft.get("title"),
            "recipients": [{k: r[k] for k in ("to", "recipient", "title", "forms", "titles")} for r in draft.get("recipients") or ()],
            "respond_by": draft.get("respond_by"), "premise": premise_,
            "chosen": (assessment or {}).get("chosen"), "options_sha256": (assessment or {}).get("options_sha256"),
            "text_sha256": sha(draft.get("text")), "also": [{"kind": a["kind"], "sha256": sha(a["text"])} for a in draft.get("also") or () if a.get("text")],
            "parts": [[p["part"], sha(p["text"])] for p in draft.get("parts") or ()], "run_id": run_id, "files_digest": files_digest, "op_id": op_id,
            **({"deadline": deadline} if deadline else {})}


def next_look(process, form, stage, day, respond_by=None):
    """The day the case is looked at again once the letter goes out on ``day``: the reply date it sets, else the clock's
    follow-up of its code at this stage (an assessment: 90 days), else None."""
    if respond_by:
        return respond_by
    code = record_of(form)[2]
    rule = next((r for r in (process or {}).get("clock") or () if code and code in r.get("after", ()) and (r.get("stages") is None or stage in r["stages"])), None)
    d = parse_date(day)
    return (d + timedelta(days=int(rule["days"]))).isoformat() if rule and d else None


def dispatch_args(approval, recipient, date_, channel, listed, events, assessment=None):
    """The «add_dispatch» edit of one recipient of an approved version: the account's entry of its form, what it asks and
    which questions it answers (its number is drawn by the store)."""
    row = next((r for r in approval.get("recipients") or () if r.get("to") == recipient), None) or {}
    forms = row.get("forms") or [approval.get("form")]
    form = approval.get("form") if approval.get("form") in forms else forms[0]
    _, kind, code = record_of(form)
    main = form == approval.get("form")
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
            out.append(f"Zum Versand freigegeben am {_day(a.get('at'))} ({a.get('expert')}): {a.get('title')}")
    for d in sent:
        out.append(f"Versandt: {d['title'] or 'Schreiben'} an {TO_WORDS.get(d['recipient'], d['recipient'])} am {_day(d['date'])} "
                   f"({CHANNELS.get(d['channel'], d['channel'])}, {d['by']})")
    return out
