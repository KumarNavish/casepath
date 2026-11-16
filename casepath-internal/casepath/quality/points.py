"""The insurer's real decision points in a case file, and what CasePath would have prepared at each, from one stored run.

    python -m casepath labels-template <case id>                       inside the insurer only: the file's documents
    python -m casepath replay-points [--case ID …] [--labels FILE …] [--detail] [--accept] [--json]
    python -m casepath replay-points --compare <before.json> <after.json>

A labels file (``casepath.labels/1``, docs/HANDLER_BAR.md) names, for one case file, the handler's own decisions with the
day from which each held, and each of the insurer's actions in the file (a point): its day, its action kind (A0–A13),
to whom, the documents it asked (the workflow's need ids, Knowledge needs by their ids, ``other:<word>`` for anything
else), how many questions, the date it set, and whether it was internal (a phone note, A2). Labels are written by the
insurer's side and kept in the case store; real labels never go into Git.

For every labelled point the case is rebuilt as it stood on the point's day (quality/asof.py: the account entries, facts
and found documents known then, the handler's decisions then in force, «Stand am» = that day) and evaluated by the case
view's own path. The point compares the action kind; for a letter the documents CasePath's letter asks now against the
label's (a part named inside an asked whole counts as asked and is never an extra), the number of questions, and the
follow-up date against the date the label sets. «bereit»: the kind right and, for a letter, at least 80 % of the label's
documents asked with at most one extra, and the date within 7 days where the label sets one. This narrow score is kept
as it was and named in the summary «historische Handlung (eng; Wiedervorlage ±7 Tage, keine Frist-Toleranz)»: the
seven-day tolerance is one for the follow-up date, never for a legal deadline. Each miss gets a diagnosis by code: the
stage, the rule that chose the action, the deciding facts on that day, what was open (incoming items, requests by the
party asked), whether the documents that decided had an account entry at all, and what the rebuild could not settle.

The expanded acceptance (``accept``, a block of its own, never folded into «bereit») reads the letter rendered on the
point's day, by rules declared before any result:

- recipient: the form's addressees as account parties, against the label's ``to``;
- questions: the customer's questions the letter answers, conditionally answers, leaves open or leaves to be checked
  (beantwortet, bedingt, offen, prüfen; all open when the form answers none), against the optional label ``answered``;
- residual: what the letter still asks, by key, against the label's documents; a need id is hit by its own line (or by
  the whole it is part of), ``other:<word>`` by a line whose key or text holds ``<word>`` as the start of a word,
  case-folded (``other:stromkosten`` is hit by «Belege zu: Stromkosten …»); right when nothing is missed and nothing extra;
- deadlines: the dates the letter states (letters.stated_in_letter) against the optional label ``deadlines``
  [{id, date}], exactly (handler.deadline_verdict), no tolerance; a wrong stated date is a critical error;
- substantive: «present» when no gap remains; «verified» only with a verdict of the agreed jurist reviewer or of the
  process owner within the formative session (label ``substantive`` with ``by_role`` jurist or process_owner), a
  developer's verdict is a «developer check», otherwise «unverified»; citations and action matching never stand in;
- authority: the form's decisions (``needs``) and, for an assessment, the prospects (``aussichten``) are among the
  handler's decisions in force on the day; otherwise «decision pending».

What the rebuild carries from the whole file anyway is counted per point as exposure, not as an effect (asof.py,
``limits.brief``). Every report repeats the stated limits of the measurement on the real dossiers (``STATED_LIMITS``).

The output is content-free by default (case and dossier ids, point numbers, action kinds, need, stage and fact ids,
counts and day differences; no names, quotes or dates), so it can leave the insurer; ``--detail`` adds the values and
dates, for use inside only. ``--compare BEFORE AFTER`` names every point whose kind or «bereit» changed between two saved
tables (``--json``), for a read before and after a deploy. No model is called.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import time

from ..agents.runner import case_state
from ..process import account, casegraph, letters
from ..process.workflows import condition_facts, evaluate_condition
from . import asof
from .handler import MARKERS, deadline_verdict

FORMAT = "casepath.labels/1"
ACTION = re.compile(r"^A(?:[0-9]|1[0-3])$")
OTHER = re.compile(r"^other:[a-z0-9äöüß_-]{1,40}$")
DOSSIER = re.compile(r"^[A-Za-z0-9_-]{1,20}$")
CASE_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
INTERNAL = {"A2"}  # a phone note: the handler's own record, no letter
READY_SHARE, READY_EXTRAS, READY_DAYS = 0.8, 1, 7
INSIDE = ("INSIDE THE INSURER ONLY: this listing holds the dates and parties of a case file. Mark the decision points in "
          "«labels» and keep the file inside; it never goes into Git.")
POINT = {"n", "date", "kind", "to", "documents", "questions", "date_set", "internal"}
POINT_OPTIONAL = {"answered", "deadlines", "substantive"}  # the expanded truth of a point, where it is labelled
VERDICTS = {"correct", "incorrect", "incomplete"}
ROLES = {"jurist": "verified", "process_owner": "verified", "developer": "developer_check"}  # who may verify substance (MEASURE §1)
STATES = ("beantwortet", "bedingt", "offen", "pruefen")
NARROW = "historische Handlung (eng; Wiedervorlage ±7 Tage, keine Frist-Toleranz)"
# The limits stated with the measurement on the bridge's stored readings of the seven development dossiers before the
# episode release (no date here: the table is content-free and holds none); every report repeats them.
STATED_LIMITS = (
    "stated limits (bridge, stored readings of the seven development dossiers, before the episode release): 16/35 letter actions as the "
    "handler's, 11 of them meeting the narrow ready rule; the earlier 7/50 used other inputs and another denominator and "
    "is not comparable; D6 supplies 28 of the 50 points; the seven dossiers and their 50 correlated points are not "
    "independent validation")
TO_PARTY = (("kundschaft", "kunde"), ("kunde", "kunde"), ("gegenpartei", "gegenpartei"), ("kanzlei", "kanzlei"),
            ("behörde", "behoerde"), ("versicherer", "versicherer"))


class LabelsError(ValueError):
    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


# -- the labels format -----------------------------------------------------------------------------------------------

def check(labels, process=None, case_id=None):
    """A labels file as the replay reads it, points in time order; LabelsError naming every problem otherwise. With the
    case's ``process`` (its workflow, Knowledge and edits), decisions must be the handler's own facts with a value they
    take, kinds action kinds of the process and documents its need ids or ``other:<word>``."""
    problems = []
    if not isinstance(labels, dict):
        raise LabelsError(["labels: a JSON object is required"])
    extra = set(labels) - {"format", "dossier", "case", "decisions", "points", "note"}
    if extra:
        problems.append(f"labels: unknown fields {sorted(extra)}")
    if labels.get("format") != FORMAT:
        problems.append(f"format: must be {FORMAT}")
    if not DOSSIER.match(str(labels.get("dossier") or "")):
        problems.append("dossier: a short pseudonym of letters, digits, - or _ («D3»), never a name")
    if not CASE_ID.match(str(labels.get("case") or "")):
        problems.append("case: the case id in the store")
    elif case_id is not None and labels["case"] != case_id:
        problems.append(f"case: these labels are for {labels['case']}, not {case_id}")
    if labels.get("note") is not None and not isinstance(labels.get("note"), str):
        problems.append("note: a text")
    definitions = {f["id"]: f for f in (process or {}).get("facts") or ()}
    needs = {d["id"] for d in (process or {}).get("documents") or ()}
    kinds = set((process or {}).get("action_kinds") or ())
    decisions = labels.get("decisions")
    if not isinstance(decisions, list):
        problems.append("decisions: a list ([] when the handler decided nothing)")
        decisions = []
    for i, d in enumerate(decisions):
        where = f"decisions[{i}]"
        if not isinstance(d, dict) or set(d) != {"fact", "value", "from"}:
            problems.append(f"{where}: fact, value and from")
            continue
        if not ISO.match(str(d["from"])) or asof.day(d["from"]) is None:
            problems.append(f"{where}.from: a date YYYY-MM-DD")
        if process is not None:
            definition = definitions.get(d["fact"])
            if definition is None or not definition.get("handler_only"):
                problems.append(f"{where}.fact: {d['fact']!r} is not a decision of the handler in this process")
            else:
                try:
                    casegraph.fact_value(definition, d["value"])
                except casegraph.EditError as error:
                    problems.append(f"{where}.value: {error}")
    points = labels.get("points")
    if not isinstance(points, list) or not points:
        problems.append("points: a list of at least one point")
        points = []
    seen = set()
    deadlines = {d["id"] for d in (process or {}).get("deadlines") or () if isinstance(d, dict) and d.get("id")}
    for i, p in enumerate(points):
        where = f"points[{i}]"
        if not isinstance(p, dict) or not POINT <= set(p) <= POINT | POINT_OPTIONAL:  # every label file of the narrow score stays valid
            problems.append(f"{where}: n, date, kind, to, documents, questions, date_set and internal; optionally answered, deadlines "
                            "and substantive")
            continue
        problems += optional_problems(p, where, deadlines if process is not None else None)
        if type(p["n"]) is not int or p["n"] < 1 or p["n"] in seen:
            problems.append(f"{where}.n: a number from 1, once each")
        seen.add(p["n"])
        if not ISO.match(str(p["date"])) or asof.day(p["date"]) is None:
            problems.append(f"{where}.date: a date YYYY-MM-DD")
        if not ACTION.match(str(p["kind"])) or (kinds and p["kind"] not in kinds):
            problems.append(f"{where}.kind: an action kind A0–A13")
        if p["to"] not in account.PARTIES:
            problems.append(f"{where}.to: one of {', '.join(account.PARTIES)}")
        if not isinstance(p["documents"], list) or len(set(map(str, p["documents"]))) != len(p["documents"]):
            problems.append(f"{where}.documents: a list of need ids, each once")
        else:
            for d in p["documents"]:
                if not isinstance(d, str) or not (OTHER.match(d) or (d in needs if process is not None else re.match(r"^[a-z0-9][a-z0-9_.:-]{0,99}$", d))):
                    problems.append(f"{where}.documents: {d!r} is not a need of this process; use other:<word> for anything else")
        if type(p["questions"]) is not int or p["questions"] < 0:
            problems.append(f"{where}.questions: a count from 0")
        if p["date_set"] is not None and (not ISO.match(str(p["date_set"])) or asof.day(p["date_set"]) is None):
            problems.append(f"{where}.date_set: a date YYYY-MM-DD or null")
        elif p["date_set"] is not None and asof.day(p["date"]) and asof.day(p["date_set"]) < asof.day(p["date"]):
            problems.append(f"{where}.date_set: before the point's own day")
        if not isinstance(p["internal"], bool) or (p["kind"] in INTERNAL and p["internal"] is not True):
            problems.append(f"{where}.internal: true or false; a phone note (A2) is internal")
    if problems:
        raise LabelsError(problems)
    return {**labels, "points": sorted(points, key=lambda p: (p["date"], p["n"]))}


def optional_problems(p, where, deadlines=None):
    """The expanded truth of a point, where labelled: ``answered`` (how many of the customer's questions the handler's letter
    answered), ``deadlines`` [{id, date}] (the dates it stated: a date, or prüfen, trigger_missing, not_applicable) and
    ``substantive`` {by_role: jurist | process_owner | developer, verdict: correct | incorrect | incomplete, questions?:
    [verdict per question]}. ``deadlines`` (with the case's process): the process's deadline ids."""
    out = []
    if "answered" in p and (type(p["answered"]) is not int or p["answered"] < 0):
        out.append(f"{where}.answered: a count from 0")
    if "deadlines" in p:
        rows = p["deadlines"]
        if not isinstance(rows, list) or any(not isinstance(d, dict) or set(d) != {"id", "date"} for d in rows):
            out.append(f"{where}.deadlines: a list of {{id, date}}")
        else:
            for d in rows:
                if not (d["date"] in MARKERS or (ISO.match(str(d["date"])) and asof.day(d["date"]))):
                    out.append(f"{where}.deadlines: {d['id']!r} needs a date YYYY-MM-DD or one of {', '.join(sorted(MARKERS))}")
                if not re.match(r"^[a-z0-9][a-z0-9_.:-]{0,79}$", str(d["id"])) or (deadlines is not None and d["id"] not in deadlines):
                    out.append(f"{where}.deadlines: {d['id']!r} is not a deadline of this process")
    if "substantive" in p:
        s = p["substantive"]
        if (not isinstance(s, dict) or not {"by_role", "verdict"} <= set(s) <= {"by_role", "verdict", "questions"} or s["by_role"] not in ROLES
                or s["verdict"] not in VERDICTS or not isinstance(s.get("questions", []), list)
                or any(v not in VERDICTS for v in s.get("questions", []))):
            out.append(f"{where}.substantive: by_role ({', '.join(ROLES)}), verdict ({', '.join(sorted(VERDICTS))}) and optionally questions, "
                       "a verdict per question")
    return out


def check_case(store, catalogue, case_id, labels):
    """Labels checked against the case's own process, as the case view builds it."""
    state = case_state(store, catalogue, case_id)
    if state.get("process") is None or not state.get("run"):
        raise LabelsError(["the case has no completed run on a process: prepare it once first"])
    return check(labels, state["process"], case_id)


# -- the template for whoever writes the labels ------------------------------------------------------------------------

def template(store, catalogue, case_id):
    """The file's documents in time order from the stored run (n, date, from, to, kind, first page), the insurer's own
    marked with the action kind they are, documents of the file without an entry listed too, the needs and the handler's
    decisions the process knows, and labels to complete: one point per insurer document."""
    state = case_state(store, catalogue, case_id)
    run = state.get("run")
    if not run or state.get("process") is None:
        raise LabelsError(["the case has no completed run on a process: prepare it once first"])
    graph, result = state["process"], run.get("result") or {}
    kinds, phone = account.kinds_of(graph), (graph.get("record") or {}).get("phone_code") or "2"
    files = store.list_files(case_id)
    names = {f["id"]: f.get("name") for f in files}
    entries = sorted(account.entries_of(result), key=lambda e: (e.get("date") or "9999", e["n"]))
    rows, points, announced = [], [], False
    for e in entries:
        codes = [f"A{c}" for c in account.code_of(e, kinds, announced, phone)]
        own = e.get("from") == account.INSURER
        rows.append({"n": e["n"], "date": e.get("date"), "from": e.get("from"), "to": e.get("to"), "kind": e.get("kind"), "phone": bool(e.get("phone")),
                     "file": names.get(e.get("file")), "page": e.get("page"), "insurer": own, **({"action": codes} if own else {})})
        if own and e.get("kind") == "abschlussankuendigung":
            announced = True
        if own and e.get("date"):
            kind = next((c for c in codes if c not in INTERNAL), codes[0] if codes else "A2")
            points.append({"n": len(points) + 1, "date": e["date"], "kind": kind, "to": e.get("to") or "kunde", "documents": [], "questions": 0,
                           "date_set": None, "internal": kind in INTERNAL})
    starts = {(e.get("file"), e.get("page")) for e in entries}
    for f in files:  # a document of the file the reader gave no entry: listed, so a point there is not missed
        for s in (f.get("extraction") or {}).get("segments") or ():
            first, last = s.get("first_page"), s.get("last_page") or s.get("first_page")
            if first is None or s.get("unsegmented") or any(fid == f["id"] and isinstance(p, int) and first <= p <= last for fid, p in starts):
                continue
            day = asof.day(s.get("date"))  # no entry: the segment's own sender and recipient, as the reader stored them
            rows.append({"n": None, "date": day.isoformat() if day else None, "from": s.get("sender"), "to": s.get("recipient"), "kind": s.get("kind"),
                         "phone": False, "file": names.get(f["id"]), "page": first,
                         "insurer": account.party_of(s.get("sender"), default="andere") == account.INSURER, "entry": False})
    rows.sort(key=lambda r: (r["date"] or "9999", r["n"] is None, r["n"] or 0))
    decisions = {f["id"]: f.get("values") or f.get("type") for f in graph["facts"] if f.get("handler_only")}
    return {"note": INSIDE, "case": case_id, "documents": rows, "needs": [{"id": d["id"], "title": d["title"]} for d in graph["documents"]],
            "decisions": decisions, "labels": {"format": FORMAT, "dossier": "", "case": case_id, "decisions": [], "points": points}}


def template_lines(out):
    """The template as a person reads it: the note, one line per document, the needs and decisions, the labels to complete."""
    lines = [out["note"], "", f"{out['case']}: the documents of the file in time order (* the insurer's own, - no account entry)"]
    for r in out["documents"]:
        n = "-" if r["n"] is None else str(r["n"])
        lines.append(f"{'*' if r['insurer'] else ' '} {n:>3}  {r['date'] or '?':10}  {r['from'] or '?'} → {r['to'] or '-'}  {r['kind'] or ''}"
                     + (" (Telefon)" if r["phone"] else "") + f"  {r['file']} S. {r['page']}" + (f"  {'/'.join(r['action'])}" if r.get("action") else ""))
    lines += ["", "needs (documents of a point): " + ", ".join(d["id"] for d in out["needs"]) + ", other:<word>",
              "decisions (from the day each held): " + "; ".join(f"{k} {v}" for k, v in out["decisions"].items()), "",
              "labels to complete (documents, questions, date_set; drop what is not a decision point):"]
    labels = out["labels"]
    head = json.dumps({k: v for k, v in labels.items() if k != "points"}, ensure_ascii=False)
    lines.append(head[:-1] + ', "points": [\n  ' + ",\n  ".join(json.dumps(p, ensure_ascii=False) for p in labels["points"]) + "\n]}")
    return lines


# -- one point ---------------------------------------------------------------------------------------------------------

def kind_of(action):
    """CasePath's next action as an action kind: a request for documents is a first request (A1), a closing A12."""
    return {"request": "A1", "close": "A12"}.get(action, action)


def wholes(process):
    """{part: whole} from the needs that include others (a Mängelrüge within all correspondence)."""
    return {part: d["id"] for d in (process or {}).get("documents") or () for part in d.get("includes") or ()}


def compare(point, got, process):
    """The point against what CasePath prepared: {kind, kind_ok, documents, questions, date, ready}."""
    kind = kind_of((got or {}).get("action"))
    letter = not point["internal"]
    asked = set(got["now"]) if got and got.get("lists_documents") and letter else set()
    whole = wholes(process)
    wanted = point["documents"]
    hits = [d for d in wanted if d in asked or whole.get(d) in asked]  # named on its own line or inside an asked whole
    extras = sorted(k for k in asked if k not in wanted and whole.get(k) not in asked)  # a part of an asked whole is never an extra
    due, label_date = asof.day((got or {}).get("follow_up")), asof.day(point["date_set"])
    diff = (due - label_date).days if due and label_date else None
    docs_ok = (not wanted or len(hits) / len(wanted) >= READY_SHARE) and len(extras) <= READY_EXTRAS
    date_ok = label_date is None or (diff is not None and abs(diff) <= READY_DAYS)
    return {"kind": kind, "kind_ok": kind == point["kind"],
            "documents": {"label": len(wanted), "hits": hits, "missed": [d for d in wanted if d not in hits], "extras": extras},
            "questions": {"label": point["questions"], "got": len((got or {}).get("questions") or ()) if letter else 0},
            "date": {"set": label_date is not None, "got": bool(due), "diff": diff, "ok": date_ok},
            "ready": kind == point["kind"] and (not letter or docs_ok) and date_ok}


def recipients(to):
    """The parties a form's addressee line names, in its order («Gegenpartei, als Entwurf zuerst an die Kundschaft» →
    gegenpartei, kunde); «andere» when it names none of them."""
    text = str(to or "").lower()
    found = sorted({(text.find(word), party) for word, party in TO_PARTY if word in text})
    out = list(dict.fromkeys(party for _, party in found))
    return out or ["andere"]


def question_states(items, drafted):
    """{beantwortet, bedingt, offen, pruefen: count} over the customer's questions, as the letter of the day leaves them: the
    state the question carries (``answer_state``), else answered where the item states an answer; all open when the
    letter's form answers none."""
    asked = [i for i in items if i["kind"] == "customer_question" and i.get("value")]
    answers = any("{zu_fragen}" in p for p in (drafted or {}).get("parts") or ())

    def state(i):
        own = str(i.get("answer_state") or "").replace("ü", "ue")
        return "offen" if not answers else own if own in STATES else "beantwortet" if i.get("answer") or i.get("answered_by") else "offen"
    return {s: sum(1 for i in asked if state(i) == s) for s in STATES}


def residual_lines(items, drafted):
    """What the letter of the day still asks of the customer, as [{key, line}]: the assessment's residual where the case
    view gives one, else the documents a form that lists documents asks (``residual:document.<need>``)."""
    given = ((drafted or {}).get("assessment") or {}).get("residual")
    if given is not None:
        return [{"key": str(r.get("key")), "line": str(r.get("line") or "")} for r in given]
    parts = " ".join((drafted or {}).get("parts") or ())
    if not drafted or not drafted.get("text") or not any("{" + p + "}" in parts for p in asof.LETTER_LISTS):
        return []
    return [{"key": f"residual:document.{i['key']}", "line": str((i.get("label") or {}).get("de") or i["key"])}
            for i in letters.asked(items, [], "document")]


def residual_verdict(wanted, lines, process):
    """The label's documents against the residual lines: {label, hits, missed, extras (keys), ok}, by the rule declared in
    the module's text."""
    whole = wholes(process)
    need = lambda line: line["key"][len("residual:document."):] if line["key"].startswith("residual:document.") else None
    asked = {need(line) for line in lines} - {None}

    def hit(d, line):
        if d.startswith("other:"):
            word = d.split(":", 1)[1].casefold()
            return bool(re.search(r"(?<![0-9a-zäöüß])" + re.escape(word), f"{line['key']} {line['line']}".casefold()))
        return need(line) is not None and (need(line) == d or need(line) == whole.get(d))
    hits = [d for d in wanted if any(hit(d, line) for line in lines)]
    extras = sorted(line["key"] for line in lines if not any(hit(d, line) for d in wanted) and whole.get(need(line)) not in asked)
    return {"label": len(wanted), "hits": hits, "missed": [d for d in wanted if d not in hits], "extras": extras,
            "ok": len(hits) == len(wanted) and not extras}


def deadline_check(point, items, text):
    """The dates the letter states against the label's ``deadlines``: {stated, label, right, wrong, missing, ok, critical}."""
    stated = {}
    for i in items:
        d = asof.day(i.get("value")) if letters.stated_in_letter(i) else None
        if d and text and d.strftime("%d.%m.%Y") in text:
            stated[i["key"]] = d.isoformat()
    wanted = point.get("deadlines") or []
    verdicts = [(d["id"], deadline_verdict(d, stated)) for d in wanted]
    wrong = [k for k, v in verdicts if v == "wrong"]
    return {"stated": len(stated), "label": len(wanted), "right": sum(1 for _, v in verdicts if v == "right"), "wrong": wrong,
            "missing": [k for k, v in verdicts if v == "missing"], "ok": all(v == "right" for _, v in verdicts) if wanted else None,
            "critical": len(wrong)}


def accept(point, shown, drafted, decisions, process):
    """The expanded acceptance of one letter point, from the letter rendered on its day (the module's text declares each
    rule): {form, draft, recipient, questions, residual, deadlines, substantive, authority}. Ids, enums and counts only.
    Without a draft (an action CasePath writes no letter for) only the questions, the deadlines and the verdict are read."""
    items = (shown or {}).get("items") or []
    text = (drafted or {}).get("text")
    drafted = drafted if text is not None else None
    states = question_states(items, drafted)
    answered = point.get("answered")
    gaps = str(text or "").count(letters.GAP)
    verdict = point.get("substantive") or {}
    out = {"form": asof.form_of((shown or {}).get("action")), "draft": drafted is not None,
           "questions": {**states, "label": answered, "ok": None if answered is None else states["beantwortet"] == answered},
           "deadlines": deadline_check(point, items, text),
           "substantive": {"present": drafted is not None and gaps == 0, "gaps": gaps, "status": ROLES.get(verdict.get("by_role"), "unverified"),
                           "verdict": verdict.get("verdict")}}
    if drafted is None:
        return {**out, "recipient": None, "residual": None, "authority": None}
    to = recipients(drafted.get("to"))
    needs = list(dict.fromkeys(list(drafted.get("needs") or []) + (["aussichten"] if drafted.get("form") == "A5" else [])))
    held = {e["args"]["fact"] for e in asof.decisions_on(decisions, asof.day(point["date"]))}
    missing = [n for n in needs if n not in held]
    return {**out, "recipient": {"label": point["to"], "form": to, "ok": point["to"] in to},
            "residual": residual_verdict(point["documents"], residual_lines(items, drafted), process),
            "authority": {"needs": needs, "missing": missing, "ok": not missing}}


def _slug(value):
    value = str(value).lower().translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_")[:40] or "set"


def shown_value(definition, value, detail):
    """A fact's value as the table may show it: in content-free mode yes, no, open, an enum value of the process (its
    words as an id) or «set»; with detail the value itself."""
    if value is None:
        return "open"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if detail:
        return str(value)[:80]
    if (definition or {}).get("values") and value in definition["values"]:
        return _slug(value)
    return "set"


def rule_of(action, graph, here, facts, evaluation):
    """What chose the next action, by code: an open incoming item, an agreed payment due, silence on the clock, a decision
    the handler must take, the stage's own action, its follow-up or a variant, an outcome, or documents to ask."""
    action = action or {}
    step = next((s for s in graph["steps"] if s["id"] == here), {})
    planned = step.get("action") or {}
    kind = action.get("action")
    if action.get("incoming"):
        return f"incoming:{action['incoming']['kind']}"
    if action.get("owed"):
        return "payout_due"
    if str(action.get("reason") or "").startswith("keine Antwort seit"):
        m = re.search(r"A\d{1,2}", action["reason"])
        return f"silence:{m.group(0) if m else '?'}"
    if action.get("choices") or (step.get("decision") or {}).get("fact") == kind:
        return f"decision:{kind}"
    if kind == "close":
        return f"outcome:{(evaluation.get('outcome') or {}).get('id')}"
    if kind == "request":
        return "documents"
    variant = next((v for v in planned.get("instead") or () if evaluate_condition(v["when"], facts) is True), None)
    if variant and variant.get("kind") == kind:
        return f"variant:{here}"
    if planned.get("kind") == kind:
        return f"stage:{here}"
    if planned.get("follow_up") == kind:
        return f"follow_up:{here}"
    return "other" if kind else "none"


def deciding(graph, here):
    """The facts that decide where the case stands and what its stage does: the stage's ways out, its action's skip and
    variants, the handler decisions that place a case further on."""
    step = next((s for s in graph["steps"] if s["id"] == here), {})
    out = set()
    for edge in step.get("next") or ():
        out |= condition_facts(edge.get("when", True))
    action = step.get("action") or {}
    out |= condition_facts(action.get("skip_if") or True)
    for variant in action.get("instead") or ():
        out |= condition_facts(variant.get("when") or True)
    for decision in (graph.get("floor") or {}).get("decisions") or ():
        out |= condition_facts(decision.get("when") or True)
    return sorted(out)


def coverage(entries, files, rebuilt, t):
    """Whether the documents that decided had an account entry at all in the stored run: the latest document of another
    party known on the day (what the handler answered) and the insurer's own document of the day (the point itself, None
    when the file holds none); and how many known pages lie in no entry's document."""
    docs, dating = [], rebuilt["dating"]
    for f in files:
        for s in (f.get("extraction") or {}).get("segments") or ():
            first, last, day = s.get("first_page"), s.get("last_page") or s.get("first_page"), asof.day(s.get("date"))
            if first is None or s.get("unsegmented") or day is None:
                continue
            insurer = account.party_of(s.get("sender"), default="andere") == account.INSURER
            owner = (dating.owner_day.get(f["id"]) or {}).get(first)  # an enclosure no later than the entry before it is that entry's
            entry = any(e.get("file") == f["id"] and isinstance(e.get("page"), int) and first <= e["page"] <= last for e in entries) or \
                bool(owner and day <= owner)
            # known as the page dating says (an old enclosure only from the letter it came with), on the day it became known
            docs.append((dating.page_day(f["id"], first) or day, insurer, entry, dating.page_known(f["id"], first, t), day))
    known = [d for d in docs if not d[1] and d[3]]
    last = max((d[0] for d in known), default=None)
    own = [d for d in docs if d[1] and d[4] == t]
    kept = account.entries_of(rebuilt["run"]["result"])
    gaps = account.gaps(kept, account.pages_of(rebuilt["files"]))
    return {"incoming": None if last is None else all(d[2] for d in known if d[0] == last), "own": any(d[2] for d in own) if own else None,
            "pages_without_entry": sum(g["pages"] for g in gaps)}


def diagnose(point, got, shown, rebuilt, files, detail=False):
    """Why a point is not ready, by code: {stage, outcome, rule, held, facts, open, entry, documents, rebuilt}."""
    t = asof.day(point["date"])
    if shown is None:
        return {"stage": None, "rule": "no_process", "facts": {}, "open": {}, "entry": {}, "documents": {}, "rebuilt": {}}
    state = shown["state"]
    graph, evaluation, facts = state["process"], state.get("evaluation") or {}, state.get("facts") or {}
    here = ((evaluation.get("current") or {}).get("step") or ((evaluation.get("path") or [{}])[-1]).get("step"))
    definitions = {f["id"]: f for f in graph["facts"]}
    ledger = state.get("account") or {}
    requests = [r for r in ledger.get("requests") or () if r.get("answered") is None]
    action = shown["action"] or {}
    pending = ([action["incoming"]] if action.get("incoming") else []) + list(action.get("then") or ())
    open_ = {"incoming": [r["kind"] for r in pending],
             "requests": {party: sum(1 for r in requests if r["of"] == party) for party in account.PARTIES if any(r["of"] == party for r in requests)}}
    if detail:
        open_["incoming_values"] = [{"kind": r["kind"], "date": r.get("date"), "value": r.get("value") or r.get("action")} for r in pending]
        open_["requests_what"] = [{"of": r["of"], "what": r["what"], "since": r["first"], "due": r.get("due")} for r in requests]
    items = {i["key"]: i for i in shown["items"] if i["kind"] == "document"}
    whole = wholes(graph)

    def need_state(d):
        if d.startswith("other:"):
            return "outside_process"
        i = items.get(d)
        if i is None:
            return "not_needed_now" if d in {x["id"] for x in graph["documents"]} else "not_a_need"
        if i.get("status") == "present":
            return "present"
        state_ = {"now": "asked", "proposed": "offered", "later": "later"}.get(i.get("ask"), "not_asked")
        return f"{state_}:{i.get('required')}" + (f":in:{whole[d]}" if whole.get(d) else "")
    row = compare(point, got, graph)
    documents = {"missed": {d: need_state(d) for d in row["documents"]["missed"]},
                 "extras": {d: f"{items[d].get('required')}:{items[d].get('status')}" for d in row["documents"]["extras"] if d in items}}
    limits = rebuilt["limits"] if rebuilt else {}
    waiting = [w["fact"] for w in evaluation.get("waiting_for") or ()]
    decide = deciding(graph, here)
    asked = {i["key"] for i in shown["items"] if i["kind"] == "letter_question" and i.get("ask") == "now"}
    out = {"stage": here, "outcome": (evaluation.get("outcome") or {}).get("id"),
           "rule": rule_of(action, graph, here, facts, evaluation), "held": (evaluation.get("current") or {}).get("held_for"),
           "waiting": waiting, "facts": {f: shown_value(definitions.get(f), facts.get(f), detail) for f in decide},
           "open": open_, "entry": coverage(account.entries_of(rebuilt["whole"]), files, rebuilt, t) if rebuilt else {},
           "documents": documents,
           # what the rebuild could not settle, where it bears on this point: a fact quoted on both sides of the day, one
           # whose quotes all lie later (its earlier value, if it had one, is lost), pages without a date
           "rebuilt": {"undecided": limits.get("undecided", []),
                       "later_only": [f for f in limits.get("later_only", []) if f in set(decide) | set(waiting) | asked],
                       "undated_pages": limits.get("undated_pages", 0), "elements_dropped": limits.get("elements_dropped", 0),
                       "brief": dict(limits.get("brief") or {})}}  # what reached the day from the whole file: exposure, not effect
    if detail:
        out["next"] = {"title": (action.get("label") or {}).get("de"), "reason": action.get("reason"), "next_in_days": action.get("next_in_days"),
                       "follow_up": (shown.get("follow_up") or {}).get("due"), "since": action.get("since")}
    return out


# -- all labelled points -----------------------------------------------------------------------------------------------

def replay_case(store, catalogue, labels, detail=False):
    """Every point of one labelled case: [{dossier, case, n, label kind, internal, ...compare, why?}]."""
    case_id = labels["case"]
    run = store.latest_run(case_id, "completed")
    rows = []
    if run is None:
        return [{"dossier": labels["dossier"], "case": case_id, "n": p["n"], "label": p["kind"], "internal": p["internal"], "error": "no_run"}
                for p in labels["points"]]
    files = store.list_files(case_id, with_text=True)
    graph = (run.get("result") or {}).get("process") or {}
    dating = asof.Dating(files, account.entries_of(run.get("result")), tuple((graph.get("cooperation") or {}).get("insurer") or ("protekta", "rechtsschutz")))
    for p in labels["points"]:
        shown, rebuilt = asof.as_of_view(store, catalogue, case_id, p["date"], labels["decisions"], run=run, files=files, dating=dating)
        rebuilt["whole"] = run.get("result") or {}  # the stored run of the whole file: whether a document had an entry at all
        got = asof.measure(shown)
        process = (shown or {}).get("state", {}).get("process")
        row = {"dossier": labels["dossier"], "case": case_id, "n": p["n"], "label": p["kind"], "to": p["to"], "internal": p["internal"],
               **compare(p, got, process), "exposure": dict(rebuilt["limits"].get("brief") or {})}
        if not p["internal"]:  # the expanded acceptance, from the letter rendered on the point's day
            row["accept"] = accept(p, shown, asof.letter(shown), labels["decisions"], process)
        if detail:
            row["detail"] = {"date": p["date"], "date_set": p["date_set"], "follow_up": (got or {}).get("follow_up"), "form": (got or {}).get("form"),
                             "title": (got or {}).get("title"), "asked": (got or {}).get("now"), "offered": (got or {}).get("offered")}
        if not row["ready"]:
            row["why"] = diagnose(p, got, shown, rebuilt, files, detail)
        rows.append(row)
    return rows


def summary(rows):
    """The table over all points: points, ready, kind right by action kind, documents and extras of letters, dates."""
    letters = [r for r in rows if not r["internal"] and "error" not in r]
    inner = [r for r in rows if r["internal"] and "error" not in r]

    def by_kind(group):  # {label kind: [right, of]} in the order of the action kinds
        kinds = sorted({r["label"] for r in group}, key=lambda k: int(k[1:]) if ACTION.match(k) else 99)
        return {k: [sum(1 for r in group if r["label"] == k and r["kind_ok"]), sum(1 for r in group if r["label"] == k)] for k in kinds}
    with_docs = [r for r in letters if r["documents"]["label"]]
    dated = [r for r in rows if "error" not in r and r["date"]["set"]]
    accepted = [r["accept"] for r in letters if r.get("accept")]
    drafted = [a for a in accepted if a["draft"]]
    labelled = lambda key: [a for a in accepted if a[key].get("ok") is not None]
    exposed = [r["exposure"] for r in rows if r.get("exposure")]
    return {"points": len(rows), "letters": len(letters), "internal": len(inner), "errors": sum(1 for r in rows if "error" in r),
            "ready": sum(1 for r in letters if r["ready"]), "ready_internal": sum(1 for r in inner if r["ready"]),
            "kind_right": by_kind(letters), "kind_right_internal": by_kind(inner),
            "narrow": {"kind_ok": sum(1 for r in letters if r["kind_ok"]), "ready": sum(1 for r in letters if r["ready"]), "of": len(letters)},
            "documents": {"asked": sum(len(r["documents"]["hits"]) for r in with_docs), "of": sum(r["documents"]["label"] for r in with_docs),
                          "extras": sum(len(r["documents"]["extras"]) for r in letters)},
            "questions": {"same": sum(1 for r in letters if r["questions"]["got"] == r["questions"]["label"]), "of": len(letters)},
            "dates": {"within": sum(1 for r in dated if r["date"]["ok"]), "of": len(dated)},
            "accept": {"of": len(accepted), "no_draft": len(accepted) - len(drafted), "recipient": sum(1 for a in drafted if a["recipient"]["ok"]),
                       "questions": [sum(1 for a in labelled("questions") if a["questions"]["ok"]), len(labelled("questions"))],
                       "residual": sum(1 for a in drafted if a["residual"]["ok"]),
                       "deadlines": [sum(1 for a in labelled("deadlines") if a["deadlines"]["ok"]), len(labelled("deadlines"))],
                       "deadlines_wrong": sum(a["deadlines"]["critical"] for a in accepted),
                       "present": sum(1 for a in accepted if a["substantive"]["present"]),
                       "substantive": {s: sum(1 for a in accepted if a["substantive"]["status"] == s) for s in ("verified", "developer_check", "unverified")},
                       "decision_pending": sum(1 for a in drafted if not a["authority"]["ok"])},
            "exposure": {"points": sum(1 for e in exposed if any(e.values())), "of": len(exposed),
                         **{k: sum(e.get(k, 0) for e in exposed) for k in ("parties_named_later", "request_uncited", "form_renders_brief",
                                                                            "knowledge_from_same_case", "agent_edits_applied")}}}


def table(store, catalogue, case_ids=None, detail=False, accept_lines=False):
    """Every labelled point of the store's labelled cases (or of those named): {rows, summary, lines, seconds, detail};
    ``accept_lines``: each letter point's expanded acceptance as a line of its own under it."""
    started = time.perf_counter()
    rows = []
    for labels in store.list_labels():
        if case_ids and labels["case"] not in case_ids:
            continue
        rows += replay_case(store, catalogue, labels, detail)
    out = {"rows": rows, "summary": summary(rows), "detail": detail, "model_calls": 0, "accept_lines": accept_lines}
    out["seconds"] = round(time.perf_counter() - started, 2)
    out["lines"] = render(out)
    return out


# -- the lines ---------------------------------------------------------------------------------------------------------

def _days(n):
    return "-" if n is None else f"{n:+d}"


def line(r):
    """One point, content-free: «D3 case_… #2 A6 → A6 ok · docs 2/2 +0 · questions 0/0 · date +1d · ready»."""
    head = f"{r['dossier']} {r['case']} #{r['n']} {r['label']}{' (internal)' if r['internal'] else ''}"
    if "error" in r:
        return f"{head} → {r['error']}"
    parts = [f"{head} → {r['kind'] or 'none'} {'ok' if r['kind_ok'] else 'wrong'}"]
    if not r["internal"]:
        d = r["documents"]
        parts.append(f"docs {len(d['hits'])}/{d['label']} +{len(d['extras'])}" + (f" missed {','.join(d['missed'])}" if d["missed"] else "")
                     + (f" extra {','.join(d['extras'])}" if d["extras"] else ""))
        parts.append(f"questions {r['questions']['got']}/{r['questions']['label']}")
    parts.append(f"date {_days(r['date']['diff'])}d" if r["date"]["set"] else "date -")
    parts.append("ready" if r["ready"] else "not ready")
    return " · ".join(parts)


def why_line(w):
    """The diagnosis of one miss on one line."""
    facts = " ".join(f"{k}={v}" for k, v in w.get("facts", {}).items())
    open_ = w.get("open") or {}
    entry = w.get("entry") or {}
    yes = lambda v: "-" if v is None else "yes" if v else "no"
    docs = w.get("documents") or {}
    parts = [f"stage {w.get('stage')}" + (f" (outcome {w['outcome']})" if w.get("outcome") else ""), f"rule {w.get('rule')}"]
    if w.get("held"):
        parts.append(f"held for {w['held']}")
    if w.get("waiting"):
        parts.append(f"waiting {','.join(w['waiting'])}")
    if facts:
        parts.append(f"facts {facts}")
    parts.append(f"open incoming {','.join(open_.get('incoming') or ()) or '-'} requests "
                 + (",".join(f"{p}:{n}" for p, n in (open_.get("requests") or {}).items()) or "-"))
    if docs.get("missed"):
        parts.append("missed " + ",".join(f"{d}={s}" for d, s in docs["missed"].items()))
    if docs.get("extras"):
        parts.append("extra " + ",".join(f"{d}={s}" for d, s in docs["extras"].items()))
    if entry:
        parts.append(f"entry incoming {yes(entry.get('incoming'))} own {yes(entry.get('own'))}"
                     + (f" pages_without_entry {entry['pages_without_entry']}" if entry.get("pages_without_entry") else ""))
    rebuilt = w.get("rebuilt") or {}
    if rebuilt.get("undecided") or rebuilt.get("later_only") or rebuilt.get("undated_pages"):
        parts.append(f"rebuild undecided {','.join(rebuilt.get('undecided') or ()) or '-'} later_only {','.join(rebuilt.get('later_only') or ()) or '-'}"
                     f" undated_pages {rebuilt.get('undated_pages', 0)}")
    brief = rebuilt.get("brief") or {}
    if any(brief.values()):  # what the day showed from the whole file: exposure, not an effect on this point
        parts.append("whole-file brief " + " ".join(f"{k} {v}" for k, v in brief.items() if v))
    return "   why: " + " · ".join(parts)


def accept_line(a):
    """The expanded acceptance of one point on one line, content-free."""
    q, r, d, s, auth = a["questions"], a["residual"], a["deadlines"], a["substantive"], a["authority"]
    labelled = "" if q["label"] is None else f" (labelled {q['label']}: {'same' if q['ok'] else 'differs'})"
    substance = ("present" if s["present"] else f"{s['gaps']} gaps" if a["draft"] else "no draft") + ", " + s["status"].replace("_", " ")
    parts = [f"to {','.join(a['recipient']['form'])} {'ok' if a['recipient']['ok'] else 'wrong'}" if a["draft"] else f"no draft ({a['form']})",
             f"questions answered {q['beantwortet']} conditional {q['bedingt']} open {q['offen']} to check {q['pruefen']}{labelled}"]
    if a["draft"]:
        parts.append(f"residual {len(r['hits'])}/{r['label']} +{len(r['extras'])}" + (f" missed {','.join(r['missed'])}" if r["missed"] else "")
                     + (f" extra {','.join(r['extras'])}" if r["extras"] else ""))
    parts.append((f"deadlines {d['right']}/{d['label']}" + (f" WRONG {','.join(d['wrong'])}" if d["wrong"] else "")) if d["label"]
                 else f"deadlines stated {d['stated']}")
    parts.append(f"substance {substance}")
    if a["draft"]:
        parts.append("authority ok" if auth["ok"] else f"decision pending ({','.join(auth['missing'])})")
    return "   accept: " + " · ".join(parts)


def render(out):
    lines = []
    for r in out["rows"]:
        lines.append(line(r))
        if out.get("accept_lines") and r.get("accept"):
            lines.append(accept_line(r["accept"]))
        if r.get("why"):
            lines.append(why_line(r["why"]))
            if out["detail"] and r["why"].get("next"):
                lines.append("   detail: " + json.dumps({**r["why"]["next"], **(r.get("detail") or {}), "open": r["why"]["open"]}, ensure_ascii=False))
    s = out["summary"]
    share = lambda a, b: f"{a}/{b}" + (f" ({round(100 * a / b)} %)" if b else "")
    a, e, n = s["accept"], s["exposure"], s["narrow"]
    lines += ["", f"points {s['points']} · letters {s['letters']} · internal {s['internal']}" + (f" · errors {s['errors']}" if s["errors"] else ""),
              f"ready (letters) {share(s['ready'], s['letters'])} · internal ready {s['ready_internal']}/{s['internal']}",
              "kind right by action kind: " + (", ".join(f"{k} {a}/{b}" for k, (a, b) in s["kind_right"].items()) or "-")
              + (" · internal " + ", ".join(f"{k} {a}/{b}" for k, (a, b) in s["kind_right_internal"].items()) if s["kind_right_internal"] else ""),
              f"letters: documents asked {share(s['documents']['asked'], s['documents']['of'])} · extras {s['documents']['extras']}"
              f" · questions as labelled {s['questions']['same']}/{s['questions']['of']}",
              f"dates within {READY_DAYS} days {share(s['dates']['within'], s['dates']['of'])}",
              f"{NARROW}: Handlungsart {n['kind_ok']}/{n['of']} · bereit {n['ready']}/{n['of']}",
              f"accept (the letter of the day): no draft {a['no_draft']}/{a['of']} · recipient {a['recipient']}/{a['of'] - a['no_draft']}"
              f" · questions as labelled {a['questions'][0]}/{a['questions'][1]}"
              f" · residual {a['residual']}/{a['of'] - a['no_draft']} · deadlines {a['deadlines'][0]}/{a['deadlines'][1]} (wrong, critical: {a['deadlines_wrong']})"
              f" · no gap {a['present']}/{a['of']} · substance verified {a['substantive']['verified']}, developer check "
              f"{a['substantive']['developer_check']}, unverified {a['substantive']['unverified']} · decision pending {a['decision_pending']}",
              f"exposure to the whole-file brief (not an effect): {e['points']} of {e['of']} points · parties named later {e['parties_named_later']}"
              f" · request uncited {e['request_uncited']} · form renders the brief {e['form_renders_brief']} · Knowledge from the same case"
              f" {e['knowledge_from_same_case']} · agent edits applied {e['agent_edits_applied']}",
              STATED_LIMITS,
              f"computed in {out.get('seconds', 0)} s, no model" if "seconds" in out else "no model"]
    return lines


def changes(before, after):
    """Every point whose action kind or «bereit» differs between two tables of the same labels (a read before and after a
    deploy): [(dossier, case, n, label, before row or None, after row or None)]."""
    key = lambda r: (r["dossier"], r["case"], r["n"])
    old, new = {key(r): r for r in before["rows"]}, {key(r): r for r in after["rows"]}
    state = lambda r: None if r is None else (r.get("error"),) if "error" in r else (r["kind"], r["ready"])
    return [(*k, (new.get(k) or old.get(k))["label"], old.get(k), new.get(k)) for k in sorted(old.keys() | new.keys(), key=str)
            if state(old.get(k)) != state(new.get(k))]


def change_lines(before, after):
    """The changes as lines, content-free: «D11 case_… #3 A5: kind A6 → A5, ready no → no», then the totals."""
    shown = lambda r, field: "-" if r is None else r.get("error", "") if "error" in r else (r[field] or "none") if field == "kind" \
        else ("yes" if r[field] else "no")
    out = [f"{d} {c} #{n} {label}: kind {shown(o, 'kind')} → {shown(w, 'kind')}, ready {shown(o, 'ready')} → {shown(w, 'ready')}"
           for d, c, n, label, o, w in changes(before, after)]
    b, a = before["summary"], after["summary"]
    return out + [f"{len(out)} of {len(after['rows'])} points changed kind or ready · ready (letters) {b['ready']}/{b['letters']} before, "
                  f"{a['ready']}/{a['letters']} after"]


# -- the command line --------------------------------------------------------------------------------------------------

def _store():
    from ..config import load_settings
    from ..process.workflows import Catalogue
    from ..web.store import CaseStore

    settings = load_settings()
    return CaseStore(settings.data_dir), Catalogue.load(settings.catalogue_dir)


def template_main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m casepath labels-template",
                                     description="the file's documents in time order, for marking the insurer's decision points (inside only)")
    parser.add_argument("case", help="the case id in the store")
    parser.add_argument("--json", action="store_true", help="the template as JSON")
    args = parser.parse_args(argv)
    from ..web.store import NotFound

    store, catalogue = _store()
    try:
        out = template(store, catalogue, args.case)
    except LabelsError as error:
        sys.exit(str(error))
    except NotFound:
        sys.exit(f"no case {args.case} in the case store")
    finally:
        store.close()
    print(json.dumps(out, ensure_ascii=False, indent=1) if args.json else "\n".join(template_lines(out)))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m casepath replay-points", description=__doc__.splitlines()[0])
    parser.add_argument("--case", action="append", help="only this case (repeatable)")
    parser.add_argument("--labels", action="append", default=[], help="a casepath.labels/1 file to check and keep in the case store first (repeatable)")
    parser.add_argument("--detail", action="store_true", help="values and dates in the diagnosis: inside the insurer only")
    parser.add_argument("--accept", action="store_true", help="each letter point's expanded acceptance on a line of its own")
    parser.add_argument("--json", action="store_true", help="the table as JSON")
    parser.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"),
                        help="two saved tables (--json, or GET /api/replay-points): each point whose kind or ready changed; no store needed")
    args = parser.parse_args(argv)
    if args.compare:
        before, after = (json.loads(Path(p).read_text(encoding="utf-8")) for p in args.compare)
        print("\n".join(change_lines(before, after)))
        return
    from ..web.store import NotFound

    store, catalogue = _store()
    try:
        for path in args.labels:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
            try:
                labels = check_case(store, catalogue, str(raw.get("case")), raw)
            except LabelsError as error:
                sys.exit(f"{path}: {error}")
            except NotFound:
                sys.exit(f"{path}: no case {raw.get('case')} in the case store")
            store.save_labels(labels["case"], labels, "replay-points")
        out = table(store, catalogue, set(args.case or ()) or None, detail=args.detail, accept_lines=args.accept)
    finally:
        store.close()
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print("\n".join(out["lines"]))
