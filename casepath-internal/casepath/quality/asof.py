"""«Stand am» by code: the state of a case as it was known on an earlier day, rebuilt from one stored run of the whole file.

A completed run of a whole file records every element with its source: each account entry (one per document) its date
and first page, each fact its quotes with file and page, each document the finder matched its file and page, and each
page lies in a dated segment or a range «nicht gegliedert». So the case as it stood on a day t is rebuilt without a model:

- **Pages.** A page is known on t when the document it belongs to is dated before t, or dated t and not from the insurer
  (the insurer's own step of that day is what is measured). A page belongs to the last account entry at or before it in
  its file and is dated by that entry; an enclosure without an entry of its own thus belongs to the letter it came with.
  It also carries the date of every dated segment that starts after that entry's first page and at or before the page,
  and the latest date counts: a lease of 2021 enclosed in an e-mail of 2025 is known from 2025, and a later letter the
  reader gave no entry is never dated back, nor are the pages after it. A page before any entry takes its segment's date,
  an undated one the later of the dated pages around it (as incoming.document_dates bounds an undated document), and a
  page with none of these is left out.
- **The account** keeps its entries dated before t and those dated t that do not come from the insurer; an element whose
  quote stands in a page not yet known is left out. The requests ledger, the agreement, who owes what, the insurer's
  actions taken, silence and the incoming items are then rebuilt from the kept entries by the product's own code.
- **Facts** keep their quotes in known pages. With none left, a fact is unknown (``limits.later_only``). With quotes
  before and after, it keeps the earlier ones and its value where they state it: a date found in them, a name or an
  amount whose words they hold, an incoming item dated before t. A yes/no or a choice cannot be decided from words: it
  becomes unknown (``limits.undecided``). Presumptions are applied afresh to what is left, as a run applies them.
- **Documents** the finder matched stay found only with a quote in a known page; otherwise they are missing, as the
  finder records a need it looked for and did not find.
- **The brief** keeps its timeline, the documents the file mentions and the customer's questions where a quote is known;
  the result checker's texts about the whole file (answer, open points, reply, summaries) are left out.
- **Files** are cut to the known pages as «Stand am» cuts a file (read/cut.py), with ``cut_of.as_of`` = t, so the clock,
  the follow-up date, the historic mark and silence count from t exactly as for a cut.
- **The handler's decisions** in force on t (``from`` on or before t) are the case's only edits: edits made in the
  product later are not part of that day's state.

What it cannot rebuild exactly: a yes/no or a choice read from quotes on both sides of t (unknown, named); a value the
file later changed when the whole-file reading quotes only the later document (the defect repaired: unknown before,
where a reading of the cut would have read the earlier value; named as ``later_only``); an incoming kind read into fewer
slots than the file holds (only the latest report: the earlier ones are not rebuilt); the order of documents within one
day (another party's document of day t counts as known); an undated page without dated neighbours (left out, counted);
the brief's parties and request, which carry no quotes (kept as read from the whole file).

``view`` evaluates a case through the product's own path, as GET /api/cases/{id} does: runner.case_state, build_items, the
clock's follow_up and capped. ``AsOfStore`` shows that path the rebuilt case. Model-free.
"""
from datetime import date
import re

from ..agents.runner import case_state
from ..process import account, incoming, workflows
from ..process.clock import GERMAN_MONTHS, capped, follow_up, parse_date
from ..process.items import build_items
from ..read.cut import cut_extraction

PAGE = re.compile(r"\[page (\d+)\]\n(.*?)(?=\n\n\[page \d+\]\n|\Z)", re.S)  # as read/cut.py and account.pages_of split a file
DATES = re.compile(r"\d{4}-\d{2}-\d{2}|\d{1,2}\.\s?\d{1,2}\.\s?\d{4}|\d{1,2}\.?\s+[A-Za-zäÄ]+\s+\d{4}")
MONTHS = re.compile(r"(\d{4})-(\d{2})(?!-\d)|(\d{1,2})\.(\d{4})|([A-Za-zäÄ]+)\s+(\d{4})")
WORD = re.compile(r"[A-Za-zÄÖÜäöüß0-9']{3,}")
LETTER_LISTS = {"liste", "nachzureichen", "erwartet", "fragen_oder_offen"}  # a form's parts that list the documents asked


def day(value):
    """A date from a stored value (YYYY-MM-DD or a date as a document writes it), or None."""
    if isinstance(value, date):
        return value
    try:
        return parse_date(value)
    except ValueError:
        return None


def known(when, insurer, t):
    """Whether a document of this day is known on t: before t, or on t and not the insurer's own."""
    return when is not None and (when < t or (when == t and not insurer))


def _pages(file):
    """The file's numbered pages with text, in order; [] for a file without page marks."""
    return [int(n) for n, body in PAGE.findall(str((file.get("extraction") or {}).get("text") or "")) if body.strip()]


def _segment(segments, page):
    return next((s for s in segments if (s.get("first_page") or 0) <= page <= (s.get("last_page") or s.get("first_page") or 0)), None)


class Dating:
    """When each page of a case's files became known, from the run's account entries and the files' segments.

    ``rules[file][page]`` lists (day, from the insurer) for each document the page can belong to; a page is known on t
    when every one of them is (``known``). ``how[file][page]`` says where its date came from: entry, segment, neighbours
    or None (undated)."""

    def __init__(self, files, entries, insurer_words=("protekta", "rechtsschutz")):
        self.rules, self.how, self.entry_day, self.pages, self.owner_day = {}, {}, {}, {}, {}
        insurer = lambda sender: account.party_of(sender, default="andere") == account.INSURER or \
            any(w in str(sender or "").lower() for w in insurer_words)
        seg_day = lambda s: day(s.get("date")) if s and not s.get("unsegmented") else None
        for f in files:
            fid, extraction = f["id"], f.get("extraction") or {}
            segments = [s for s in extraction.get("segments") or () if s.get("first_page") is not None]
            mine = [e for e in entries if e.get("file") == fid]
            paged = sorted((e for e in mine if isinstance(e.get("page"), int)), key=lambda e: (e["page"], e["n"]))
            for e in mine:
                self.entry_day[e["n"]] = day(e.get("date")) or (seg_day(_segment(segments, e["page"])) if isinstance(e.get("page"), int) else None)
            pages, rules, how, owner_day = _pages(f), {}, {}, {}
            for p in pages or [None]:
                first = max((e["page"] for e in paged if e["page"] <= p), default=None) if p is not None else None
                if first is not None:  # the document the page belongs to: the last entry at or before it
                    owners = [e for e in paged if e["page"] == first]
                    # and every dated document that starts after that entry, up to the page: an older enclosure changes nothing,
                    # a later letter the reader gave no entry dates the pages from it on
                    between = [s for s in segments if first < s["first_page"] <= p]
                elif p is None or not paged:  # a file without page marks, or whose entries name no page, is one document
                    owners, between = mine, [s for s in segments if p is None or s["first_page"] <= p]
                else:  # a page before the first entry: its own segment
                    owners, between = [], [s for s in [_segment(segments, p)] if s]
                rows = [(self.entry_day[e["n"]], e.get("from") == account.INSURER, "entry") for e in owners]
                owner_day[p] = max((d for d, _, _ in rows if d is not None), default=None)  # the day of the entry the page belongs to
                rows += [(seg_day(s), insurer(s.get("sender")), "segment") for s in between if seg_day(s)]
                rules[p] = [(d, i) for d, i, _ in rows if d is not None]
                how[p] = next((w for d, _, w in rows if d is not None), None)
            dated = {p: max(d for d, _ in r) for p, r in rules.items() if r and p is not None}
            for p in [p for p in pages if not rules[p]]:  # bounded by the dated pages around it: the later is a day it came in by
                around = [dated[q] for q in pages if q < p and q in dated][-1:] + [dated[q] for q in pages if q > p and q in dated][:1]
                if around:
                    rules[p], how[p] = [(max(around), True)], "neighbours"
            for e in paged:  # an entry without a date of its own is as known as its first page
                self.entry_day[e["n"]] = self.entry_day[e["n"]] or max((d for d, _ in rules.get(e["page"]) or ()), default=None)
            self.rules[fid], self.how[fid], self.pages[fid], self.owner_day[fid] = rules, how, pages, owner_day

    def page_known(self, file_id, page, t):
        rules = self.rules.get(file_id) or {}
        row = rules.get(page) if page in rules else rules.get(None)  # a quote in a file without page marks: the whole file
        return bool(row) and all(known(d, i, t) for d, i in row)

    def page_day(self, file_id, page):
        row = (self.rules.get(file_id) or {}).get(page) or []
        return max((d for d, _ in row), default=None)

    def kept_pages(self, file_id, t):
        return [p for p in self.rules.get(file_id) or () if p is not None and self.page_known(file_id, p, t)]


# -- what the earlier quotes state ----------------------------------------------------------------------------------

def _dates_in(text):
    return {d for m in DATES.finditer(text) if (d := day(re.sub(r"\.\s(?=\d)", ".", m.group(0))))}


def _months_in(text):
    out = set()
    for m in MONTHS.finditer(text):
        if m.group(1):
            out.add((int(m.group(1)), int(m.group(2))))
        elif m.group(3):
            out.add((int(m.group(4)), int(m.group(3))))
        elif m.group(5) and m.group(5).lower() in GERMAN_MONTHS:
            out.add((int(m.group(6)), GERMAN_MONTHS[m.group(5).lower()]))
    return out


def stated(definition, value, quotes, t, incoming_fact=False):
    """Whether the kept quotes state a fact's value: True, or None where words cannot decide it (a yes/no, a choice, a
    value they do not hold). An incoming item stands when it is dated before t; a date when they name it; a text when
    they hold three quarters of its words."""
    kind = (definition or {}).get("type", "text")
    if isinstance(value, bool) or kind in {"boolean", "enum"} or value in (None, ""):
        return None
    text = " ".join(str(q or "") for q in quotes)
    if incoming_fact:
        own = incoming.read_item(str(value))[0]
        return True if own and own < t else None
    if m := re.fullmatch(r"(\d{4})-(\d{2})", str(value).strip()):
        return True if (int(m.group(1)), int(m.group(2))) in _months_in(text) else None
    if (d := day(str(value)[:10])) and re.match(r"\d{4}-\d{2}-\d{2}", str(value)):
        return True if d in _dates_in(text) else None
    words = {w.lower() for w in WORD.findall(str(value)) if w.lower() not in account.STOP}
    held = {w.lower() for w in WORD.findall(text)}
    return True if words and len(words & held) / len(words) >= 0.75 else None


# -- the rebuild -------------------------------------------------------------------------------------------------------

def decisions_on(decisions, t):
    """The handler's decisions in force on t, as the set_fact edits the case view applies (the latest of a fact wins)."""
    rows = sorted((d for d in decisions or () if day(d.get("from")) and day(d["from"]) <= t), key=lambda d: d["from"])
    return [{"id": f"label-{i + 1}", "case_id": None, "op": "set_fact", "args": {"fact": d["fact"], "value": d["value"]},
             "by": "labels", "reason": "Entscheid der Fallbearbeitung laut Labels", "status": "active", "at": d["from"]}
            for i, d in enumerate(rows)]


def rebuild(run, files, t, decisions=(), dating=None):
    """The run, the files and the edits as known on day t: {run, files, edits, limits, dating}.

    ``run``: the stored completed run of the whole file; ``files``: the case's files with their text (store.list_files with
    text); ``decisions``: the handler's decisions [{fact, value, from}] (labels); ``dating``: the case's Dating, when one
    is made for several days. ``limits`` names what could not be rebuilt exactly: facts with quotes on both sides of t
    whose value words cannot decide (``undecided``), facts quoted only later (``later_only``), elements of kept entries
    that quote a later document (``elements_dropped``), pages without any date (``undated_pages``)."""
    t = day(t)
    result = (run or {}).get("result") or {}
    graph = result.get("process") or {}
    insurer_words = tuple((graph.get("cooperation") or {}).get("insurer") or ("protekta", "rechtsschutz"))
    entries = account.entries_of(result)
    dating = dating or Dating(files, entries, insurer_words)
    known_page = lambda c: dating.page_known(c.get("file"), c.get("page"), t)
    limits = {"undecided": [], "later_only": [], "elements_dropped": 0, "entries_kept": 0, "entries_later": 0,
              "undated_pages": sum(1 for rows in dating.rules.values() for p, r in rows.items() if p is not None and not r)}
    # the account: entries known on t, their elements quoted in known pages
    kept = []
    for e in entries:
        if not known(dating.entry_day.get(e["n"]), e.get("from") == account.INSURER, t):
            limits["entries_later"] += 1
            continue
        row = dict(e)
        for key in account.ELEMENTS:
            elements = [x for x in e.get(key) or () if all(known_page(c) for c in x.get("citations") or ())]
            limits["elements_dropped"] += len(e.get(key) or ()) - len(elements)
            row[key] = elements
        kept.append(row)
    limits["entries_kept"] = len(kept)
    # the facts: quotes in known pages, the value where they state it
    definitions = {f["id"]: f for f in graph.get("facts") or ()}
    slots = {s for kind in graph.get("incoming") or () for s in incoming.slots(kind)}
    facts = []
    for row in result.get("facts") or ():
        if row.get("status") == "presumed":
            continue  # applied afresh below, to what is left
        cites = row.get("citations") or []
        left = [c for c in cites if known_page(c)]
        if len(left) == len(cites):
            facts.append(row)
            continue
        if row.get("status") == "unknown":
            facts.append({**row, "citations": left})
            continue
        if not left:  # nothing of it was in the file yet: unknown (an earlier value the whole file no longer quotes is lost)
            limits["later_only"].append(row["fact"])
            continue
        if row.get("status") == "established" and stated(definitions.get(row["fact"]), row.get("value"), [c.get("quote") for c in left],
                                                         t, row["fact"] in slots):
            facts.append({**row, "citations": left})
            continue
        limits["undecided"].append(row["fact"])
    for fact_id, p in workflows.presumed(graph, {f["fact"]: f for f in facts}).items() if graph else ():
        facts.append({"fact": fact_id, "status": "presumed", "value": p["value"], "citations": [], "verdict": "presumed", "by": "presumption",
                      "presumption": {"applies": p.get("applies"), "source_ref": p.get("source_ref"), "text": p.get("text")}})
    still = {f["fact"] for f in facts if f.get("status") == "established" and f.get("verdict") == "accepted"}
    # the documents the finder matched: found only with a quote in a known page
    documents = []
    for row in result.get("documents") or ():
        cites = row.get("citations") or []
        left = [c for c in cites if known_page(c)]
        if row.get("status") not in {"present", "unusable"} or len(left) == len(cites):
            documents.append(row)
        elif left:
            documents.append({**row, "citations": left, "files": sorted({c["file"] for c in left if c.get("file")}) or row.get("files", []),
                              "shows": [{**s, "citations": [c for c in s.get("citations") or () if known_page(c)]} for s in row.get("shows") or ()]})
        else:
            documents.append({"document": row["document"], "status": "missing", "files": [], "citations": [], "note": "", "by": row.get("by"),
                              "shows": [], "verdict": "not_checked"})
    brief = dict(result.get("brief") or {})
    for key in ("timeline", "not_enclosed", "questions"):
        brief[key] = [x for x in brief.get(key) or () if any(known_page(c) for c in x.get("citations") or ())]
    brief.pop("summary", None)
    record = result.get("record")
    rebuilt = {**{k: v for k, v in result.items() if k not in {"answer", "open_points", "reply", "summary", "case_summary", "learning", "events",
                                                                   "evaluation", "usage", "fitted"}},
               "facts": facts, "documents": documents, "brief": brief,
               "deadlines": [d for d in result.get("deadlines") or () if d.get("fact") in still],  # a kept fact keeps its value
               "as_of": t.isoformat()}
    if record is not None:
        rebuilt["record"] = {**{k: v for k, v in record.items() if k not in {"coverage", "issues", "hygiene"}},
                             "entries": sorted(kept, key=lambda e: (e.get("date") or "9999", e["n"]))}
    shown = []
    for f in files:
        extraction = f.get("extraction") or {}
        pages = dating.kept_pages(f["id"], t)
        mark = {"cut_of": {"case": f.get("case_id"), "file": f["id"], "as_of": t.isoformat(), "rebuilt": True}}
        if dating.pages.get(f["id"]):
            if pages:
                shown.append({**f, "extraction": {**cut_extraction(extraction, pages), **mark}})
        elif dating.page_known(f["id"], None, t):
            shown.append({**f, "extraction": {**extraction, **mark}})
    if not shown and files:  # nothing was in the file yet: the day still governs the clock
        shown.append({**files[0], "extraction": {"text": "", "pages": 0, "readable": False, "segments": [], "kept_pages": [], **{
            "cut_of": {"case": files[0].get("case_id"), "file": files[0]["id"], "as_of": t.isoformat(), "rebuilt": True}}}})
    return {"run": {**run, "result": rebuilt}, "files": shown, "edits": decisions_on(decisions, t), "limits": limits, "dating": dating,
            "as_of": t}


class AsOfStore:
    """What runner.case_state and the case view read from the store, for one case as it stood on a day: its rebuilt run,
    its cut files and the handler's decisions in force; Knowledge comes from the store itself, as for any case."""

    def __init__(self, store, case, rebuilt):
        self.store, self.case, self.rebuilt = store, {**case, "intake": {k: v for k, v in (case.get("intake") or {}).items() if k != "study"}}, rebuilt

    def get_case(self, case_id):
        return self.case

    def get_run(self, run_id, after=0):
        return self.rebuilt["run"]

    def latest_run(self, case_id, status=None):
        return self.rebuilt["run"] if status in (None, "completed") else None

    def list_knowledge(self, family=None, statuses=None):
        return self.store.list_knowledge(family, statuses)

    def list_edits(self, case_id, active_only=True):
        return list(self.rebuilt["edits"])

    def list_files(self, case_id, with_text=False):
        return [f if with_text else {**f, "extraction": {k: v for k, v in f["extraction"].items() if k != "text"}} for f in self.rebuilt["files"]]

    def list_case_events(self, case_id):
        return []


def view(store, catalogue, case_id):
    """The case as GET /api/cases/{id} evaluates it: {state, items, action, follow_up, files}; None without a process."""
    current = case_state(store, catalogue, case_id)
    run = current.get("run")
    if not current.get("process") or not run:
        return None
    events = store.list_case_events(case_id)
    stage = ((current.get("evaluation") or {}).get("current") or {}).get("step")
    files = store.list_files(case_id)
    texts = store.list_files(case_id, with_text=True) if stage in {"mandat", "abwicklung"} else None
    items = build_items(current, run.get("result"), texts or files, events)
    action = next((i for i in items if i["kind"] == "next_action"), None)
    clock = follow_up(action.get("next_in_days") if action else None, files, events, since=(action or {}).get("since"))
    clock = capped(clock, items, (current.get("process") or {}).get("deadline_margin_days"), files)
    return {"state": current, "items": items, "action": action, "follow_up": clock, "files": files}


def as_of_view(store, catalogue, case_id, t, decisions=(), run=None, files=None, dating=None):
    """The case view on day t, rebuilt from the case's latest completed run: (view or None, rebuilt)."""
    run = run or store.latest_run(case_id, "completed")
    if run is None:
        return None, None
    rebuilt = rebuild(run, files if files is not None else store.list_files(case_id, with_text=True), t, decisions, dating)
    return view(AsOfStore(store, store.get_case(case_id), rebuilt), catalogue, case_id), rebuilt


def letter_lists(forms, kind):
    """Whether the form a next action renders lists the documents asked (a first request, a reminder, the assessment)."""
    text = str((forms or {}).get(kind) or "")
    return any("{" + part + "}" in text for part in LETTER_LISTS)


def measure(shown, forms=None):
    """What a handler would have seen, as the replay compares it: the next action, its form and date, the documents asked
    now, offered and later, the letter's questions and hints."""
    if shown is None:
        return None
    items, action = shown["items"], shown["action"] or {}
    docs = lambda ask: sorted(i["key"] for i in items if i["kind"] == "document" and i.get("ask") == ask and i.get("status") != "present")
    kind = action.get("action")
    form = "A1" if kind == "request" else action.get("form") or kind  # the form the case view renders (app.get_case)
    evaluation = shown["state"].get("evaluation") or {}
    return {"action": kind, "form": form, "title": (action.get("label") or {}).get("de"), "next_in_days": action.get("next_in_days"),
            "follow_up": (shown["follow_up"] or {}).get("due"), "stage": (evaluation.get("current") or {}).get("step"),
            "outcome": (evaluation.get("outcome") or {}).get("id"),
            "now": docs("now"), "offered": docs("proposed"), "later": docs("later"),
            "parts": sorted(i["key"] for i in items if i["kind"] == "document" and i.get("ask") == "now" and i.get("part_of")),
            "questions": sorted(i["key"] for i in items if i["kind"] == "letter_question" and i.get("ask") == "now"),
            "questions_offered": sorted(i["key"] for i in items if i["kind"] == "letter_question" and i.get("ask") != "now"),
            "hints": sorted((i["key"], i.get("stated_as")) for i in items if i["kind"] == "hint"),
            "lists_documents": letter_lists(forms if forms is not None else (shown["state"].get("process") or {}).get("forms"), form)}
