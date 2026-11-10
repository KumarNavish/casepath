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

from .workflows import CatalogueError, evaluate, evaluate_condition, validate_workflow

EXTRA_SOURCES = [{"id": "knowledge", "kind": "knowledge", "title": "CasePath Knowledge learned from earlier cases"},
                 {"id": "edit", "kind": "case_edit", "title": "Changes made to this case's process"}]
EDIT_OPS = {"add_document", "remove_document", "set_required_when", "add_question", "add_step", "set_transition", "rename_step"}


class EditError(ValueError):
    pass


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


def _apply_knowledge(graph, item, facts_known):
    content, ref = item["content"], f"knowledge#{item['id']}@v{item['version']}"
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
                        knowledge=item["id"], **({"required_when": condition} if condition else {}))
        document.pop("optional", None)
        return {"item": item["id"], "applied": True, "document": document["id"], "replaced": True}
    if item["kind"] == "document_need":
        document_id = f"k-{item['id']}"
        graph["documents"].append({"id": document_id, "title": content["title"], "why": content["why"],
                                   "required_when": _combine(condition, content.get("required_when")),
                                   "source_refs": [ref], "suggested": suggested, "knowledge": item["id"]})
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


def check_edit(base_graph, edit):
    """Validate one proposed edit against the current case process before saving it."""
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
