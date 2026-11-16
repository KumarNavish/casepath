"""A case's own process: the base workflow, the Knowledge that applies, and edits.

The base workflow comes from the catalogue. Active Knowledge adds the document
needs, questions and steps learned in earlier cases; candidate Knowledge is added as a
suggestion that is checked but never counted as missing. Edits by a case worker
(or by the Process builder, with its reason) change the case's process only: they
add documents, questions or whole steps the case needs, so a case's process is
discovered from the case rather than only followed.
Every addition names its origin, and the result is validated like any workflow.
"""
import re
from copy import deepcopy
from datetime import timedelta

from . import incoming
from .clock import as_of, parse_date

from .workflows import CatalogueError, condition_facts, evaluate, evaluate_condition, validate_workflow

EXTRA_SOURCES = [{"id": "knowledge", "kind": "knowledge", "title": "CasePath Knowledge learned from earlier cases"},
                 {"id": "edit", "kind": "case_edit", "title": "Changes made to this case's process"}]
EDIT_OPS = {"add_document", "remove_document", "set_required_when", "add_question", "add_step", "set_transition", "rename_step", "set_fact",
            "add_entry",  # add_entry: the handler's own entry of the running account (account.handler_entry); the process is unchanged
            # none of these three changes the process either; each is refused until its slice fills its branch in apply_edit:
            "add_dispatch",  # a letter dispatched to one recipient, an entry of the account (Slice B; written by the store only)
            "settle_request",  # a request of the account settled by the handler (Slice C)
            "set_party"}  # a party as the handler names it (Slice C)


def fact_value(definition, value):
    """A case worker's value for a fact, in the fact's own type; EditError when it does not fit."""
    kind = definition.get("type")
    if kind == "boolean":
        folded = str(value).strip().lower()
        if folded in {"true", "ja", "yes"}:
            return True
        if folded in {"false", "nein", "no"}:
            return False
        raise EditError("a yes or no is required")
    if kind == "enum" and value not in definition.get("values", ()):
        raise EditError("the value is not one of the fact's values")
    if value in (None, ""):
        raise EditError("a value is required")
    return value


def fact_overrides(graph, edits):
    """Facts a case worker set: {fact: (value, edit_id)}; the latest active edit wins."""
    definitions = {f["id"]: f for f in graph["facts"]}
    out = {}
    for edit in edits:
        if edit.get("op") == "set_fact" and edit.get("status", "active") == "active" and edit["args"].get("fact") in definitions:
            try:
                out[edit["args"]["fact"]] = (fact_value(definitions[edit["args"]["fact"]], edit["args"].get("value")), edit["id"])
            except EditError:
                continue
    return out


class EditError(ValueError):
    pass


def party_overrides(edits):
    """The parties a case worker named (op «set_party», Slice C): {role: {name, salutation, edit, by, at}}, the latest active
    edit per role (kunde, gegenpartei). The party items, the letters' greeting and recipient and the list title follow."""
    out = {}
    for edit in edits or ():
        args = edit.get("args") or {}
        if edit.get("op") == "set_party" and edit.get("status", "active") == "active" and args.get("role") in ("kunde", "gegenpartei") \
                and str(args.get("name") or "").strip():
            out[args["role"]] = {"name": str(args["name"]).strip(), "salutation": args.get("salutation") or None, "edit": edit.get("id"),
                                 "by": edit.get("by"), "at": edit.get("at")}
    return out


class Derived(EditError):
    """A fact code computes, set by hand: refused with what it follows from (C9)."""


# what a derived fact follows from, in the handler's words: where to correct it instead (C9)
DERIVED_FROM = {"action_A1": "die Schreiben von Protekta im Verlauf", "last_action_A2": "die Telefonnotizen im Verlauf",
                "requests_count": "die Anforderungen im Verlauf", "replied_since_request": "die Antworten der Kundschaft im Verlauf",
                "silent_after_requests": "die Anforderungen mit Frist und die Antworten im Verlauf",
                "closing_announced": "die Statusanfrage im Verlauf und ihre Frist", "documents_complete": "die Unterlagen (Dokumenten-Checkliste)",
                "assess_needs_present": "die Unterlagen (Dokumenten-Checkliste)", "nothing_to_ask": "die Unterlagen und die offenen Fragen",
                "no_stage_fact_open": "die offenen Fragen des Schritts", "one_stage_fact_open": "die offenen Fragen des Schritts",
                "cost_claim_open": "die Kostennoten und Zahlungen im Verlauf", "settled": "die Vereinbarung und die Zahlung im Verlauf"}


def conjunction(pairs):
    """[{fact, value}] from a model or a form → a condition (None when empty)."""
    parts = [{"fact": p["fact"], "is": p["value"]} for p in pairs or []]
    return None if not parts else parts[0] if len(parts) == 1 else {"all": parts}


def _combine(first, second):
    present = [c for c in (first, second) if c not in (None, True)]
    return True if not present else present[0] if len(present) == 1 else {"all": present}


def _attach(graph, step_id, document_id):
    steps = {s["id"]: s for s in graph["steps"]}
    if step_id is not None:
        if step_id not in steps:
            raise EditError(f"unknown step {step_id!r}")
        steps[step_id].setdefault("documents", []).append(document_id)


def _insert_step(graph, step_id, before, title, why, ref, legal_basis=None, suggested=False):
    """Put a new step in front of `before`: every way into `before` now leads through the new step."""
    if before not in {s["id"] for s in graph["steps"]}:
        raise EditError(f"unknown step {before!r}")
    for step in graph["steps"]:
        if step["id"] != before:
            for edge in step.get("next", []):
                if edge["to"] == before:
                    edge["to"] = step_id
    if graph["start"] == before:
        graph["start"] = step_id
    graph["steps"].append({"id": step_id, "title": title.strip(), "role": "Fallbearbeitung", "why": (why or "").strip(),
                           **({"legal_basis": legal_basis.strip()} if legal_basis else {}), **({"suggested": True} if suggested else {}),
                           "source_refs": [ref], "documents": [], "next": [{"to": before, "label": None, "when": True}]})


def practice_count(item):
    """A practice rule's count as the handler sees it ("in 6 von 7 Fällen verlangt"), from its first evidence; None."""
    m = re.search(r"(\d+) von (\d+)", str(((item.get("evidence") or [{}])[0] or {}).get("text") or ""))
    return f"in {m.group(1)} von {m.group(2)} Fällen verlangt" if m else None


def _apply_knowledge(graph, item, facts_known):
    content, ref = item["content"], f"knowledge#{item['id']}@v{item['version']}"
    count = practice_count(item)
    used = {f["id"] for f in graph["facts"]}
    condition = item.get("applies_when")
    try:
        validate_condition_facts(condition, used)
    except EditError as error:
        return {"item": item["id"], "applied": False, "reason": str(error)}
    if condition and evaluate_condition(condition, facts_known) is False:
        return {"item": item["id"], "applied": False, "reason": "Its condition does not hold for this case."}
    suggested = item["status"] != "active"
    if item["kind"] == "document_need" and content.get("replaces") in {d["id"] for d in graph["documents"]}:
        # The process already names this document, but only on a later step: the item makes it a need of the whole
        # case (asked for at intake), so the case shows one row, not two.
        document = next(d for d in graph["documents"] if d["id"] == content["replaces"])
        if suggested:
            return {"item": item["id"], "applied": False, "reason": "A suggestion does not change the process's own needs."}
        for step in graph["steps"]:
            step["documents"] = [d for d in step.get("documents", []) if d != document["id"]]
        document.update(title=content["title"], why=content["why"], source_refs=document["source_refs"] + [ref],
                        knowledge=item["id"], **({"required_when": condition} if condition else {}), **({"practice": count} if count else {}))
        document.pop("optional", None)
        return {"item": item["id"], "applied": True, "document": document["id"], "replaced": True}
    if item["kind"] == "document_need":
        document_id = f"k-{item['id']}"
        graph["documents"].append({"id": document_id, "title": content["title"], "why": content["why"],
                                   "required_when": _combine(condition, content.get("required_when")),
                                   "source_refs": [ref], "suggested": suggested, "knowledge": item["id"], **({"practice": count} if count else {}),
                                   **({"includes": [d for d in content["includes"] if d in {x["id"] for x in graph["documents"]}]}
                                      if content.get("includes") else {})})
        step = content.get("step") if content.get("step") in {s["id"] for s in graph["steps"]} else None
        _attach(graph, step, document_id)
        return {"item": item["id"], "applied": True, "document": document_id, "suggested": suggested}
    if item["kind"] == "question":
        fact_id = f"k-{item['id']}"
        graph["facts"].append({"id": fact_id, "question": content["question"], "type": content.get("type", "text"),
                               **({"values": content["values"]} if content.get("values") else {}),
                               "source_refs": [ref], "knowledge": item["id"]})
        return {"item": item["id"], "applied": True, "fact": fact_id, "suggested": suggested}
    if item["kind"] == "step":
        step_id = f"k-{item['id']}"
        _insert_step(graph, step_id, content["before"], content["title"], content.get("why"), ref, content.get("legal_basis"), suggested)
        return {"item": item["id"], "applied": True, "step": step_id, "suggested": suggested}
    return {"item": item["id"], "applied": True, "note": content.get("text"), "suggested": suggested}


def validate_condition_facts(condition, fact_ids):
    if condition in (None, True):
        return
    for key in ("all", "any"):
        for child in condition.get(key, ()):
            validate_condition_facts(child, fact_ids)
    if "not" in condition:
        validate_condition_facts(condition["not"], fact_ids)
    if "fact" in condition and condition["fact"] not in fact_ids:
        raise EditError(f"the condition names a fact this process does not have ({condition['fact']})")


def apply_edit(graph, edit):
    op, args, ref = edit["op"], edit["args"], f"edit#{edit['id']}"
    steps = {s["id"]: s for s in graph["steps"]}
    documents = {d["id"]: d for d in graph["documents"]}
    facts = {f["id"] for f in graph["facts"]}
    if op not in EDIT_OPS:
        raise EditError(f"unknown edit {op!r}")
    if op == "add_document":
        document_id = f"e-{edit['id']}"
        condition = args.get("required_when")
        validate_condition_facts(condition, facts)
        graph["documents"].append({"id": document_id, "title": args["title"].strip(), "why": args["why"].strip(),
                                   "required_when": condition if condition is not None else True,
                                   "source_refs": [ref], "edit": edit["id"], **({"suggested": True} if args.get("suggested") else {}),
                                   **({"legal_basis": args["legal_basis"]} if args.get("legal_basis") else {})})
        _attach(graph, args.get("step"), document_id)
    elif op == "remove_document":
        if args["document"] not in documents:
            raise EditError("unknown document")
        graph["documents"] = [d for d in graph["documents"] if d["id"] != args["document"]]
        for step in graph["steps"]:
            step["documents"] = [d for d in step.get("documents", []) if d != args["document"]]
    elif op == "set_required_when":
        if args["document"] not in documents:
            raise EditError("unknown document")
        validate_condition_facts(args.get("required_when"), facts)
        document = documents[args["document"]]
        document["required_when"] = args.get("required_when") if args.get("required_when") is not None else True
        document["source_refs"] = document["source_refs"] + [ref]
    elif op == "add_question":
        fact_id = f"q-{edit['id']}"
        fact = {"id": fact_id, "question": args["question"].strip(), "type": args.get("type", "boolean"), "source_refs": [ref],
                **({"suggested": True} if args.get("suggested") else {})}
        if fact["type"] == "enum":
            fact["values"] = list(args["values"])
        graph["facts"].append(fact)
        if args.get("gates_document"):
            if args["gates_document"] not in documents:
                raise EditError("unknown document")
            document = documents[args["gates_document"]]
            gate = {"fact": fact_id, "is": args.get("gate_value", True)}
            document["required_when"] = _combine(document.get("required_when", True), gate)
            document["source_refs"] = document["source_refs"] + [ref]
    elif op == "add_step":
        _insert_step(graph, f"s-{edit['id']}", args.get("before"), args["title"], args.get("why"), ref, args.get("legal_basis"),
                     bool(args.get("suggested")))
    elif op == "set_transition":
        step = steps.get(args["step"])
        if step is None or not 0 <= args["index"] < len(step.get("next", [])) or args["to"] not in steps:
            raise EditError("unknown step or transition")
        validate_condition_facts(args.get("when"), facts)
        step["next"][args["index"]] = {**step["next"][args["index"]], "to": args["to"],
                                       "when": args.get("when", step["next"][args["index"]].get("when", True))}
        step["source_refs"] = step["source_refs"] + [ref]
    elif op == "add_entry":  # an entry of the case's running account, not a change to the process; see account.handler_entries
        from .account import FormError, check_form
        try:
            check_form(args)
        except FormError as error:
            raise EditError(str(error)) from None
    elif op == "add_dispatch":  # a letter dispatched to one recipient: an entry of the account (account.dispatch_entries), not
        # a change to the process; written only by the store's dispatch_once (the edits route refuses it, Slice C)
        from .account import PARTIES, _iso
        if not isinstance(args.get("n"), int) or not _iso(args.get("date")) or not args.get("version") or args.get("to") not in PARTIES:
            raise EditError("a dispatch needs its number, its day, the approved version and its recipient")
    elif op == "settle_request":  # a request of the account the handler settles: an entry correction (account.apply_corrections)
        if not re.fullmatch(r"r\d+\.\d+", str(args.get("request") or "")):
            raise EditError("a request is named by its id («r3.0»)")
        if args.get("how") not in ("erledigt", "nicht_mehr_noetig", "beantwortet"):
            raise EditError("settled as erledigt, nicht_mehr_noetig or beantwortet")
        if args.get("how") == "beantwortet" and not isinstance(args.get("entry"), int):
            raise EditError("«beantwortet» names the entry that answered it")
    elif op == "set_party":  # a party as the handler names it: the party items, the letters' greeting and the list title follow
        if args.get("role") not in ("kunde", "gegenpartei"):
            raise EditError("a party is the customer (kunde) or the other side (gegenpartei)")
        if not str(args.get("name") or "").strip() or len(str(args["name"])) > 120:
            raise EditError("the party's name, up to 120 characters")
        if args.get("salutation") not in (None, "", "Frau", "Herr"):
            raise EditError("salutation: Frau, Herr or none")
    elif op == "set_fact":  # changes the facts the case is evaluated with, not the process; see fact_overrides
        definition = next((f for f in graph["facts"] if f["id"] == args.get("fact")), None)
        if definition is None:
            raise EditError("unknown fact")
        fact_value(definition, args.get("value"))
    elif op == "rename_step":
        if args["step"] not in steps:
            raise EditError("unknown step")
        steps[args["step"]]["title"] = args["title"].strip()
        steps[args["step"]]["source_refs"] = steps[args["step"]]["source_refs"] + [ref]
    return graph


def build(base, *, knowledge=(), edits=(), facts_known=None, case_id=None):
    """Return the case's process and what each Knowledge item and edit did.

    Knowledge learned from this case is not applied back to it: the case's own
    findings and edits govern it, and only later cases count as reuse.
    """
    graph = deepcopy(base)
    graph["sources"] = [s for s in graph["sources"] if s["id"] not in {"knowledge", "edit"}] + deepcopy(EXTRA_SOURCES)
    applied = []
    for item in knowledge:
        if item["family"] != base["id"] or item["status"] not in {"active", "candidate"}:
            continue
        if case_id is not None and (item.get("origin") or {}).get("case_id") == case_id:
            continue
        trial = deepcopy(graph)
        try:
            result = _apply_knowledge(trial, item, facts_known or {})
            validate_workflow(trial)
        except (EditError, CatalogueError, KeyError, TypeError) as error:
            result = {"item": item["id"], "applied": False, "reason": str(error)}
        else:
            if result["applied"]:
                graph = trial
        applied.append({**result, "version": item["version"]})  # the version this case used
    edit_results = []
    for edit in edits:
        if edit.get("status", "active") != "active":
            continue
        trial = deepcopy(graph)
        try:
            apply_edit(trial, edit)
            validate_workflow(trial)
        except (EditError, CatalogueError, KeyError, TypeError) as error:
            edit_results.append({"edit": edit["id"], "applied": False, "reason": str(error)})
            continue
        graph = trial
        edit_results.append({"edit": edit["id"], "applied": True})
    merged = merge_restated(graph)
    validate_workflow(graph)
    return graph, {"knowledge": applied, "edits": edit_results, "merged": merged}


QUANTIFIERS = {"sämtliche", "bisherige", "allfällige", "alle", "weitere", "kopie", "kopien", "ihr", "ihre", "ihren", "die", "der", "das"}
FUNCTION_WORDS = QUANTIFIERS | {"und", "oder", "inkl", "mit", "von", "vom", "des", "dem", "den", "zum", "zur", "für", "über", "bzw", "sowie", "allenfalls"}


def content(title):
    """The content words of a title, outside parentheses, cut to six letters so inflections meet."""
    text = re.sub(r"\([^)]*\)", " ", title or "")
    return {w.lower()[:6] for w in re.findall(r"[A-Za-zÄÖÜäöüß]{3,}", text) if w.lower() not in FUNCTION_WORDS}


def head(title):
    """The document a title names: its first noun, skipping quantifiers ("Sämtliche Korrespondenz …" → "korrespondenz")."""
    for word in re.findall(r"[A-Za-zÄÖÜäöüß]+", title or ""):
        if word[0].isupper() and word.lower() not in QUANTIFIERS:
            return word.lower()
    return None


def merge_restated(graph):
    """A need an edit adds that restates a need of the process or of Knowledge becomes one row with both origins.

    Two needs are the same when they share the head noun and one's content words are a subset of the other's.
    ponytail: title words only; a model-side "same as" link would catch paraphrases this misses.
    """
    kept = {head(d["title"]): d for d in graph["documents"] if not d.get("edit") and head(d["title"])}
    merged = []
    for document in [d for d in graph["documents"] if d.get("edit")]:
        same = kept.get(head(document["title"]))
        if same is None or document.get("suggested"):
            continue
        mine, theirs = content(document["title"]), content(same["title"])
        if not (mine <= theirs or theirs <= mine):  # same head noun, different document ("… mit der Versicherung")
            continue
        same["source_refs"] = same["source_refs"] + [r for r in document["source_refs"] if r not in same["source_refs"]]
        if document.get("legal_basis") and not same.get("legal_basis"):
            same["legal_basis"] = document["legal_basis"]
        graph["documents"] = [d for d in graph["documents"] if d is not document]
        for step in graph["steps"]:
            step["documents"] = [d for d in step.get("documents", []) if d != document["id"]]
        merged.append({"document": document["id"], "into": same["id"]})
    return merged


ALL_OF = {"sämtliche", "sämtlichen", "alle", "bisherige", "bisherigen"}


def open_ended(graph):
    """Needs for all of something ("Sämtliche Korrespondenz …", or marked open_ended): a file can never show them complete."""
    return {d["id"] for d in graph["documents"]
            if d.get("open_ended") or (re.findall(r"[A-Za-zÄÖÜäöüß]+", d["title"]) or [""])[0].lower() in ALL_OF}


def whole_findings(graph, findings):
    """The findings the evaluator sees, and the part of an open-ended need already in the file: such a need stays asked."""
    ends = open_ended(graph)
    partial = {k: v for k, v in findings.items() if k in ends and v["status"] == "present"}
    return {k: v for k, v in findings.items() if k not in partial}, partial


def mark_partial(evaluation, partial):
    for row in evaluation["documents"]:
        if row["document"] in partial:
            row["partial"] = {"files": partial[row["document"]].get("files", []), "citations": partial[row["document"]].get("citations", [])}
    return evaluation


COOPERATION = {"requests": {"1": 21, "6": 25, "7": 7}, "min_requests": 2, "insurer": ["protekta", "rechtsschutz"]}


def received_after(files, day, insurer=()):
    """Whether anything came in after a day: a document of the file dated later whose sender is not the insurer, or, in a
    live (not cut) case, a file without documents added later. None when nothing is known about the files."""
    if files is None:
        return None
    for f in files:
        extraction = f.get("extraction") or {}
        segments = extraction.get("segments") or []
        for s in segments:
            d = parse_date(s.get("date"))
            if d and d > day and not any(w in str(s.get("sender") or "").lower() for w in insurer):
                return True
        if not segments and "cut_of" not in extraction and (d := parse_date(str(f.get("created_at") or "")[:10])) and d > day:
            return True
    return False


def derive_facts(graph, facts, findings, evaluate, *, partial=None, files=None, today=None, incoming_dates=None, account=None):
    """Facts a workflow marks "derived": computed from other facts and the findings, never read or set by hand.

    action_A1 / requests_count: from the handler's earlier actions as read from the file ("A1 2024-08-28; A4 …").
    replied_since_request: something came in from the customer after the last request (A1, A4, A6, A7).
    silent_after_requests: lack of cooperation is silence, not incompleteness: at least two requests that set a deadline
    (A1, A6, A7; a question back, A4, never counts), the last deadline passed on the day the case is looked at, and
    nothing received since; unknown files never make it true. documents_complete: every document the evaluation needs
    now is present; an open-ended need partly present does not hold it up. no_stage_fact_open / one_stage_fact_open:
    the stage's points only the customer can answer. assess_needs_present: the documents an area names as needed for
    any assessment. missing_after_two_requests (older workflows): asked at least twice and still incomplete.
    nothing_to_ask: no document of the evaluation is asked now (items.ask_of) and no question to the customer is open, so
    the clarifying stage is complete without a first request.
    cost_claim_open: a cost claim came in (incoming items) and is still open (``incoming_dates``: the document dates of items read
    without their own, incoming.document_dates); it keeps the case from closing, as does settled.
    ``evaluate(facts)`` is the plain evaluation; it is called once without the derived facts.
    ``account``: the case's running account (account.build) when the run recorded one: then the number of requests,
    an answer since the last request and lack of cooperation are read from its requests ledger, not counted.
    """
    kinds = {f["id"]: f["derived"] for f in graph["facts"] if f.get("derived")}
    if not kinds:
        return facts
    rules = {**COOPERATION, **(graph.get("cooperation") or {})}
    history = str(facts.get("bisherige_handlungen") or "")
    # Each earlier action of the insurer: its own dated fact (handlung_a1 …, one quote each) or the accepted history line.
    dated = [(m.group(1), str(v)[:10]) for k, v in facts.items() if v and (m := re.fullmatch(r"handlung_a(\d{1,2})", k))]
    dated += [(code, day) for code, day in re.findall(r"\bA(\d{1,2})\s+(\d{4}-\d{2}-\d{2})", history)]
    done = sorted({c for c, _ in dated} | set(re.findall(r"\bA(\d{1,2})\b", history)))
    requests = max(sum(1 for n in re.findall(r"\bA(\d{1,2})\b", history) if n in {"1", "4"}),
                   sum(1 for k in ("handlung_a1", "handlung_a4") if facts.get(k)))
    when = sorted({(d, c) for c, day in dated if (d := parse_date(day))})
    asked = [(d, c) for d, c in when if c in {"1", "4", "6", "7"}]
    bearing = [(d, c) for d, c in when if c in rules["requests"]]
    look = as_of(files or (), today)
    out = {k: v for k, v in facts.items() if k not in kinds}
    from . import account as ledger
    for fact, kind in kinds.items():
        if account and kind in {"requests_count", "replied_since_request", "silent_after_requests"}:
            out[fact] = ledger.derived(account, kind, rules, look)
            continue
        if kind == "action_A1":
            out[fact] = "1" in done
        elif kind == "closing_announced":  # the clock: after a status inquiry announcing closure (A7), the case closes
            out[fact] = "7" in done
        elif kind == "last_action_A2":  # the last thing done was a phone call (its note in the file)
            last = max(dated, key=lambda x: x[1])[0] if dated else None  # by date, whatever order the reader listed them in
            out[fact] = last == "2"
        elif kind == "requests_count":
            out[fact] = "0" if requests == 0 else "1" if requests == 1 else "2+"
        elif kind == "replied_since_request":
            out[fact] = bool(asked) and received_after(files, asked[-1][0], rules["insurer"]) is True
        elif kind == "silent_after_requests":
            last = bearing[-1] if bearing else None
            out[fact] = (len(bearing) >= rules["min_requests"] and look > last[0] + timedelta(days=rules["requests"][last[1]])
                         and received_after(files, last[0], rules["insurer"]) is False)
        elif kind == "cost_claim_open":  # a cost claim that came in and no payment or confirmation after it
            out[fact] = incoming.cost_open(graph, facts, incoming_dates)
    for fact, kind in kinds.items():
        if kind == "settled":  # settled by the file or the area's own facts, nothing further wished, no claim or payment open
            settled = graph.get("settled") or {}
            done = out.get("erledigt_gemeldet") is True or (settled.get("when") is not None and evaluate_condition(settled["when"], out) is True)
            claims = settled.get("claims_open_when")
            out[fact] = (done and out.get("weiteres_gewuenscht") is not True and (claims is None or evaluate_condition(claims, out) is not True)
                         and out.get("kosten_offen") is not True)
    evaluation = evaluate(out)
    needed = [d for d in evaluation["documents"] if d["required"] == "yes"]
    complete = bool(needed) and all(d["status"] == "present" or d["document"] in (partial or {}) for d in needed)
    present = set(findings) | set(partial or {})
    for fact, kind in kinds.items():
        if kind == "documents_complete":
            out[fact] = complete
        elif kind == "missing_after_two_requests":
            out[fact] = requests >= 2 and not complete
        elif kind == "one_stage_fact_open":
            out[fact] = len(open_stage_facts(graph, out, evaluation)) == 1
        elif kind == "no_stage_fact_open":
            out[fact] = not open_stage_facts(graph, out, evaluation)
        elif kind == "assess_needs_present":
            out[fact] = all(d in present and (findings.get(d) or {}).get("status", "present") == "present" for d in graph.get("assess_needs", []))
        elif kind == "nothing_to_ask":  # a first request would ask for nothing: the file holds what the stage needs, no question is open
            from .items import ask_of, open_customer_questions
            docs = {d["id"]: d for d in graph["documents"]}
            rows = [{**r, **({"partial": True} if r["document"] in (partial or {}) else {})} for r in evaluation["documents"]]
            out[fact] = (not any(ask_of(graph, docs.get(r["document"], {}), r, files) == "now" for r in rows)
                         and not open_customer_questions(graph, out))
    return out


def open_stage_facts(graph, facts, evaluation):
    """The facts of the current stage that only the customer can settle and that are still open: those its documents and
    transitions depend on and the process marks as asked of the customer, neither the handler's decisions nor computed."""
    step = next((s for s in graph["steps"] if s["id"] == ((evaluation or {}).get("current") or {}).get("step")), None)
    if not step:
        return []
    used = set()
    for edge in step.get("next", []):
        used |= condition_facts(edge.get("when", True))
    for document in graph["documents"]:
        if document["id"] in step.get("documents", []):
            used |= condition_facts(document.get("required_when", True))
    definitions = {f["id"]: f for f in graph["facts"]}
    return sorted(f for f in used if f in definitions and definitions[f].get("ask_customer") and not definitions[f].get("handler_only")
                  and not definitions[f].get("derived") and facts.get(f) is None)


def check_edit(base_graph, edit):
    """Validate one proposed edit against the current case process before saving it (by applying it to a copy: an op
    whose branch in apply_edit still refuses, add_dispatch, is refused here too). A fact code computes is not set by hand
    (Derived, «wird berechnet; korrigieren Sie, woraus er folgt: …»); an edit stored before this check keeps applying."""
    if edit.get("op") == "set_fact":
        definition = next((f for f in base_graph.get("facts") or () if f["id"] == (edit.get("args") or {}).get("fact")), None)
        if definition and definition.get("derived"):
            raise Derived("wird berechnet; korrigieren Sie, woraus er folgt: "
                          + DERIVED_FROM.get(str(definition["derived"]), "der Verlauf und die Unterlagen"))
    trial = deepcopy(base_graph)
    apply_edit(trial, {**edit, "id": edit.get("id", "pending")})
    validate_workflow(trial)
    return trial


def diff(before, after):
    """What an edit changed in the evaluation: documents, current step and actions."""
    old = {d["document"]: d for d in before["documents"]}
    new = {d["document"]: d for d in after["documents"]}
    return {
        "documents_added": [new[k] for k in new if k not in old],
        "documents_removed": [old[k] for k in old if k not in new],
        "documents_changed": [{"document": k, "before": old[k]["status"], "after": new[k]["status"],
                               "required_before": old[k]["required"], "required_after": new[k]["required"]}
                              for k in new if k in old and (old[k]["status"], old[k]["required"]) != (new[k]["status"], new[k]["required"])],
        "current_step": {"before": before["current"] and before["current"]["step"], "after": after["current"] and after["current"]["step"]},
        "outcome": {"before": before["outcome"] and before["outcome"]["id"], "after": after["outcome"] and after["outcome"]["id"]},
        "next_actions_before": before["next_actions"], "next_actions_after": after["next_actions"],
    }


def evaluate_case(graph, facts, findings, checked):
    return evaluate(graph, facts, findings, checked=checked)
