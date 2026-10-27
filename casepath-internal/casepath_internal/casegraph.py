"""A case's own process: the base workflow, the Knowledge that applies, and edits.

The base workflow comes from the catalogue. Active Knowledge adds the document
needs and questions learned in earlier cases; candidate Knowledge is added as a
suggestion that is checked but never counted as missing. Edits by a case worker
(or by the Process builder, with its reason) change the case's process only.
Every addition names its origin, and the result is validated like any workflow.
"""
from copy import deepcopy

from .workflows import CatalogueError, evaluate, evaluate_condition, validate_workflow

EXTRA_SOURCES = [{"id": "knowledge", "kind": "knowledge", "title": "CasePath Knowledge learned from earlier cases"},
                 {"id": "edit", "kind": "case_edit", "title": "Changes made to this case's process"}]
EDIT_OPS = {"add_document", "remove_document", "set_required_when", "add_question", "set_transition", "rename_step"}


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
                                   "source_refs": [ref], "edit": edit["id"]})
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
        fact = {"id": fact_id, "question": args["question"].strip(), "type": args.get("type", "boolean"), "source_refs": [ref]}
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
        applied.append(result)
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
    validate_workflow(graph)
    return graph, {"knowledge": applied, "edits": edit_results}


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
