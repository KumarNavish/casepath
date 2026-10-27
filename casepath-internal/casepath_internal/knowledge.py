"""Knowledge that evolves: proposals, versions, activation and use statistics.

An item is a document need, a question or a note learned for one case family.
It starts as a candidate: candidates are applied to new cases as suggestions
and checked there, which builds the evidence for a person to activate them.
Refinements create a new version with the change recorded. Use statistics
come only from completed runs: an applied document need found in the files
counts as confirmed; one the result checker reports as not holding counts as
contradicted. Items contradicted more often than confirmed are flagged for
review. A person activates or retires; nothing is deleted.
"""
from copy import deepcopy

from .store import new_id, now

KINDS = {"document_need", "question", "note"}


class KnowledgeError(ValueError):
    pass


def _content(kind, content):
    if kind not in KINDS:
        raise KnowledgeError("unknown Knowledge kind")
    if kind == "document_need" and not (content.get("title") and content.get("why")):
        raise KnowledgeError("a document need needs a title and why it is needed")
    if kind == "question" and not content.get("question"):
        raise KnowledgeError("a question needs its wording")
    if kind == "note" and not content.get("text"):
        raise KnowledgeError("a note needs text")
    return {k: v for k, v in content.items() if v not in (None, "", [])}


def new_item(family, kind, content, *, applies_when=None, applies_when_text="", origin, evidence=(), status="candidate"):
    at = now()
    return {"id": new_id("know"), "family": family, "kind": kind, "content": _content(kind, content),
            "applies_when": applies_when, "applies_when_text": applies_when_text, "status": status, "version": 1,
            "origin": origin, "evidence": list(evidence),
            "stats": {"uses": 0, "confirmed": 0, "not_found": 0, "contradicted": 0, "cases": []},
            "history": [{"version": 1, "change": "created", "by": origin.get("by"), "case_id": origin.get("case_id"), "at": at}],
            "review_suggested": False, "created_at": at, "updated_at": at}


def refine(item, *, content=None, applies_when=None, applies_when_text=None, by, case_id=None, reason=""):
    updated = deepcopy(item)
    if content is not None:
        updated["content"] = _content(item["kind"], {**item["content"], **content})
    if applies_when is not None:
        updated["applies_when"] = applies_when
    if applies_when_text is not None:
        updated["applies_when_text"] = applies_when_text
    updated["version"] += 1
    updated["history"].append({"version": updated["version"], "change": reason or "refined", "by": by,
                               "case_id": case_id, "at": now(), "previous": {"content": item["content"], "applies_when": item["applies_when"]}})
    updated["updated_at"] = now()
    return updated


def set_status(item, status, *, by, reason=""):
    if status not in {"active", "retired", "candidate"}:
        raise KnowledgeError("unknown status")
    if item["status"] == status:
        return item
    updated = deepcopy(item)
    updated["status"] = status
    updated["history"].append({"version": item["version"], "change": f"{status}: {reason}".rstrip(": "), "by": by, "at": now()})
    updated["updated_at"] = now()
    return updated


def record_outcome(item, *, case_id, run_id, document_status=None, contradicted=False, reason=""):
    """Update use statistics after a completed run that applied this item."""
    updated = deepcopy(item)
    stats = updated["stats"]
    stats["uses"] += 1
    if case_id not in stats["cases"]:
        stats["cases"].append(case_id)
    if document_status in {"present", "unusable"}:
        stats["confirmed"] += 1
    elif document_status == "missing":
        stats["not_found"] += 1
    if contradicted:
        stats["contradicted"] += 1
        updated["history"].append({"version": item["version"], "change": f"contradicted: {reason}".rstrip(": "),
                                   "by": "result_checker", "case_id": case_id, "run_id": run_id, "at": now()})
    updated["review_suggested"] = stats["contradicted"] >= 2 and stats["contradicted"] > stats["confirmed"]
    updated["updated_at"] = now()
    return updated


def from_edit(family, edit, graph, *, by):
    """Turn a case worker's edit into Knowledge for similar cases."""
    args = edit["args"]
    origin = {"kind": "case_edit", "by": by, "case_id": edit["case_id"], "edit_id": edit["id"]}
    if edit["op"] == "add_document":
        step = args.get("step")
        return new_item(family, "document_need", {"title": args["title"], "why": args["why"], "step": step,
                                                   "required_when": args.get("required_when")},
                        applies_when=args.get("applies_when"), applies_when_text=args.get("applies_when_text", ""), origin=origin)
    if edit["op"] == "add_question":
        return new_item(family, "question", {"question": args["question"], "type": args.get("type", "boolean"),
                                              "values": args.get("values")}, origin=origin)
    raise KnowledgeError("only added documents and questions can become Knowledge")
