"""Synthetic case files told in phases, prepared by the scripted team (no model) and kept in a case store.

A fixture (tests/fixtures/replay/*.json) holds the file's pages and segments, what a reader records for each document
(the account entries), the facts with their quotes and the documents the finder matches, for the whole file and for
each cut that ends a phase. ``prepare`` runs the team on the whole file or on a cut (the pages of the phases so far,
«Stand am» set as the cut route sets it) and stores the run as the run service does."""
import json
from pathlib import Path
import tempfile

from casepath.agents import core
from casepath.agents.runner import RunService
from casepath.process import knowledge as kb
from casepath.process.workflows import Catalogue
from casepath.read import cut
from casepath.web.store import CaseStore
from tests.scripted import ScriptedModel, claim, report

FIXTURES = Path(__file__).parent / "fixtures" / "replay"
FIELDS = ("first_page", "last_page", "kind", "date", "sender", "recipient", "title")
ELEMENT_FIELDS = {"asks": ("what", "of", "by", "by_date", "repeats", "warns", "quote"), "answers": ("what", "answers", "quote"),
                  "terms": ("what", "amount", "payer", "by", "by_date", "agreed", "quote"), "paid": ("amount", "payer", "date", "quote"),
                  "next": ("what", "who", "by", "by_date", "quote")}


def load(name):
    return json.loads((FIXTURES / f"{name}.json").read_text())


def extraction(case):
    """The whole file as the reader stores it: text with page marks, its documents as segments."""
    text = "\n\n".join(f"[page {n}]\n{body}" for n, body in enumerate(case["pages"], 1))
    return {"text": text, "pages": len(case["pages"]), "readable": True, "note": "",
            "segments": [{**dict(zip(FIELDS, row)), "summary": ""} for row in case["segments"]]}


def entry(raw, file_id):
    """One account entry as a reader sends it to record_steps, with every field of each element."""
    row = {"n": raw["n"], "file": file_id, "page": raw["page"], "date": raw["date"], "from": raw["from"], "to": raw["to"], "kind": raw["kind"],
           "phone": bool(raw.get("phone")), "what": raw["what"], "quote": raw["quote"]}
    for key, fields in ELEMENT_FIELDS.items():
        row[key] = [{f: element.get(f, False if f in ("warns", "agreed") else None) for f in fields} for element in raw.get(key) or ()]
    return row


def reader_brief(brief, file_id):
    """What the reader reports of a brief, each question, claim and dated event with the sentence it comes from: questions
    [text, quote, key points it is about?], claims [what, quote, amount?], timeline [date, event, quote]. A claim is reported
    as the reader's schema has it (tests/scripted.py claim: its role, what it is about); a receipt is recorded on its own
    entry, never on the claim (NEEDS_A §3). The team keeps of the report what its reader records (agents/team.py,
    _located_brief), each with its quote located."""
    cite = lambda quote: [{"file": file_id, "quote": quote}] if quote else []
    out = {"request": brief.get("request", ""), "parties": [{"role": r, "name": n} for r, n in brief.get("parties", [])],
           "timeline": [{"date": d, "event": e, "citations": cite(q)} for d, e, q in brief.get("timeline", [])]}
    if brief.get("questions"):
        out["questions"] = [{"question": q[0], "citations": cite(q[1]), "about": list(q[2]) if len(q) > 2 else []} for q in brief["questions"]]
    if brief.get("claims"):
        out["claims"] = [claim(c[0], c[1], amount=c[2] if len(c) > 2 and c[2] else None, file=file_id) for c in brief["claims"]]
    return out


def turns(case, reading, file_id, pages=None):
    """The scripted team's turns: the reader records the entries of the pages given and the reading's facts and reports
    the reading's brief (the case's where the reading has none); the finder records each need found (with its quote) or
    absent; the result checker reports."""
    keep = set(pages or range(1, len(case["pages"]) + 1))
    entries = [entry(e, file_id) for e in case["entries"] if e["page"] in keep]
    cite = lambda quotes: [{"file": file_id, "quote": q} for q in ([quotes] if isinstance(quotes, str) else quotes)]
    facts = [("record_fact", {"part": None, "fact": f, "status": "established", "value": v, "citations": cite(q)}) for f, v, q in reading["facts"]]
    found = [("record_document", {"document": d, "status": "present", "files": [file_id], "citations": cite(q), "note": ""})
             for d, q in reading.get("found", [])]
    absent = [("record_document", {"document": d, "status": "absent", "files": [], "citations": [], "note": ""}) for d in reading.get("absent", [])]
    brief = reading.get("brief") or case.get("brief") or {}
    return [
        [("list_files", {})],
        [("record_steps", {"entries": entries[i:i + 10]}) for i in range(0, len(entries), 10)] + facts,
        [report("claim_reader", **reader_brief(brief, file_id))],
        found + absent + [report("document_finder")] if found or absent else [report("document_finder")],
        *[[report("result_checker", answer="Vorbereitet.")]] * 3,
    ]


class Desk:
    """A case store with the shipped areas and the build's seeded Knowledge, as a fresh deployment has them."""

    def __init__(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = CaseStore(self.directory.name)
        self.catalogue = Catalogue.load(None)
        kb.seed(self.store, {w["id"] for w in self.catalogue.workflows})
        self.runs = RunService(self.store, self.catalogue, lambda: None)

    def close(self):
        self.runs.shutdown()
        self.store.close()
        self.directory.cleanup()

    def prepare(self, case, reading=None, pages=None, as_of=None, decisions=()):
        """A case holding the whole file (or the pages of a cut, «Stand am» ``as_of``), prepared once by the scripted team;
        the handler's decisions in force stored as the case's set_fact edits. Returns the case id."""
        workflow = self.catalogue.get(case["workflow"])
        row = self.store.create_case(case["title"] + (f" · Stand am {as_of}" if as_of else ""), {}, "test")
        self.store.select_workflow(row["id"], workflow["id"], workflow["version"], "test")
        whole = extraction(case)
        stored = {**cut.cut_extraction(whole, sorted(pages)), "cut_of": {"case": None, "file": None, "as_of": as_of}} if pages else whole
        file_id = self.store.add_file(row["id"], case["name"], "application/pdf", "pdf", b"%PDF-1.4 synthetic", stored, "test")["id"]
        for d in decisions:
            self.store.add_edit(row["id"], "set_fact", {"fact": d["fact"], "value": d["value"]}, "test", "Entscheid der Fallbearbeitung")
        model = ScriptedModel(turns(case, reading or case, file_id, pages))
        job = self.runs.job(row["id"])
        outcome = core.prepare(job, model, core.StoreBlobs(self.store))
        assert outcome["status"] == "completed", outcome.get("error")
        run = self.store.create_run(row["id"], "test")
        self.runs.save(run["id"], row["id"], outcome)
        return row["id"]
