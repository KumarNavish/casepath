"""Source-grounded workflow catalogue: validation, routing and step evaluation.

A workflow is data, never code. Every fact, step, branch and document
requirement names the source it came from (a process diagram cell, a guidance
section or a case example). Routing either selects a workflow from the
catalogue, asks for the facts it needs, or says plainly that the case is
unmapped. Nothing here invents a Mobiliar procedure: an empty catalogue routes
every case to ``unmapped``.

Conditions use three-valued logic. An unknown fact never counts as yes or no;
evaluation stops at the first branch that depends on it and asks for it.
"""
from dataclasses import dataclass
import json
from pathlib import Path
import re

FORMAT = "casepath.workflow/1"
ID = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,79}$")
FACT_TYPES = {"enum", "boolean", "text", "date"}
STATUSES = {"draft", "reviewed"}
SOURCE_KINDS = {"process_diagram", "process_guidance", "case_example", "expert_review"}


class CatalogueError(ValueError):
    pass


def evaluate_condition(condition, facts):
    """Return True, False or None (unknown) for a condition over known facts."""
    if condition is True:
        return True
    if not isinstance(condition, dict) or len(condition) == 0:
        raise CatalogueError("a condition must be true or an object")
    if "all" in condition:
        values = [evaluate_condition(c, facts) for c in condition["all"]]
        return False if False in values else None if None in values else True
    if "any" in condition:
        values = [evaluate_condition(c, facts) for c in condition["any"]]
        return True if True in values else None if None in values else False
    if "not" in condition:
        value = evaluate_condition(condition["not"], facts)
        return None if value is None else not value
    fact = condition.get("fact")
    if "known" in condition:
        return (facts.get(fact) is not None) == bool(condition["known"])
    value = facts.get(fact)
    if value is None:
        return None
    if "is" in condition:
        return value == condition["is"]
    if "in" in condition:
        return value in condition["in"]
    raise CatalogueError("unsupported condition operator")


def condition_facts(condition):
    if condition is True or condition is None:
        return set()
    found = set()
    for key in ("all", "any"):
        for child in condition.get(key, ()):
            found |= condition_facts(child)
    if "not" in condition:
        found |= condition_facts(condition["not"])
    if "fact" in condition:
        found.add(condition["fact"])
    return found


def _check_condition(condition, facts, where):
    if condition is True or condition is None:
        return
    if not isinstance(condition, dict):
        raise CatalogueError(f"{where}: invalid condition")
    operators = set(condition) - {"fact"}
    if len(operators) != 1 or operators - {"all", "any", "not", "is", "in", "known"}:
        raise CatalogueError(f"{where}: a condition needs exactly one operator")
    for key in ("all", "any"):
        if key in condition:
            if not isinstance(condition[key], list) or not condition[key]:
                raise CatalogueError(f"{where}: '{key}' needs a non-empty list")
            for child in condition[key]:
                _check_condition(child, facts, where)
            return
    if "not" in condition:
        return _check_condition(condition["not"], facts, where)
    fact = facts.get(condition.get("fact"))
    if fact is None:
        raise CatalogueError(f"{where}: unknown fact {condition.get('fact')!r}")
    if "known" in condition:
        return
    values = condition["in"] if "in" in condition else [condition["is"]]
    if not isinstance(values, list) or not values:
        raise CatalogueError(f"{where}: 'in' needs a non-empty list")
    allowed = fact.get("values") if fact["type"] == "enum" else [True, False] if fact["type"] == "boolean" else None
    if allowed is not None and any(v not in allowed for v in values):
        raise CatalogueError(f"{where}: value outside the values of fact {fact['id']!r}")


def _refs(item, sources, where):
    refs = item.get("source_refs")
    if not isinstance(refs, list) or not refs:
        raise CatalogueError(f"{where}: at least one source reference is required")
    for ref in refs:
        if not isinstance(ref, str) or ref.split("#", 1)[0] not in sources:
            raise CatalogueError(f"{where}: source reference {ref!r} names no listed source")


def validate_workflow(data):
    """Fail closed on anything that cannot be traced to a listed source."""
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise CatalogueError(f"workflow format must be {FORMAT}")
    for key in ("id", "version", "title", "status", "sources", "facts", "start", "steps", "documents"):
        if key not in data:
            raise CatalogueError(f"workflow is missing {key!r}")
    if not ID.match(data["id"]) or data["status"] not in STATUSES:
        raise CatalogueError("workflow id or status is invalid")
    sources = {}
    for source in data["sources"]:
        if not ID.match(str(source.get("id"))) or source.get("kind") not in SOURCE_KINDS or not source.get("title"):
            raise CatalogueError("each source needs an id, a known kind and a title")
        sources[source["id"]] = source
    if not sources:
        raise CatalogueError("a workflow needs at least one source")
    facts = {}
    for fact in data["facts"]:
        if not ID.match(str(fact.get("id"))) or fact.get("type") not in FACT_TYPES or not fact.get("question"):
            raise CatalogueError("each fact needs an id, a type and a question")
        if fact["type"] == "enum" and (not isinstance(fact.get("values"), list) or not fact["values"]):
            raise CatalogueError(f"enum fact {fact['id']!r} needs values")
        _refs(fact, sources, f"fact {fact['id']}")
        facts[fact["id"]] = fact
    documents = {}
    for document in data["documents"]:
        if not ID.match(str(document.get("id"))) or not document.get("title") or not document.get("why"):
            raise CatalogueError("each document needs an id, a title and why it is needed")
        _refs(document, sources, f"document {document['id']}")
        _check_condition(document.get("required_when", True), facts, f"document {document['id']}")
        documents[document["id"]] = document
    outcomes = {o["id"]: o for o in data.get("outcomes", [])}
    for outcome in outcomes.values():
        _refs(outcome, sources, f"outcome {outcome['id']}")
    steps = {}
    for step in data["steps"]:
        if not ID.match(str(step.get("id"))) or not step.get("title") or step["id"] in steps:
            raise CatalogueError("each step needs a unique id and a title")
        _refs(step, sources, f"step {step['id']}")
        steps[step["id"]] = step
    if data["start"] not in steps:
        raise CatalogueError("the start step does not exist")
    for step in steps.values():
        for document in step.get("documents", []):
            if document not in documents:
                raise CatalogueError(f"step {step['id']}: unknown document {document!r}")
        if step.get("outcome") is not None and step["outcome"] not in outcomes:
            raise CatalogueError(f"step {step['id']}: unknown outcome")
        for edge in step.get("next", []):
            if edge.get("to") not in steps:
                raise CatalogueError(f"step {step['id']}: transition to an unknown step")
            _check_condition(edge.get("when", True), facts, f"step {step['id']} → {edge.get('to')}")
    _check_condition(data.get("applies_when"), facts, "applies_when")
    for question in data.get("open_questions", []):
        if not question.get("text"):
            raise CatalogueError("an open question needs text")
        _refs(question, sources, "open question")
    seen, frontier = set(), [data["start"]]
    while frontier:
        current = frontier.pop()
        if current not in seen:
            seen.add(current)
            frontier.extend(edge["to"] for edge in steps[current].get("next", []))
    unreachable = sorted(set(steps) - seen)
    if unreachable:
        raise CatalogueError(f"steps unreachable from the start: {', '.join(unreachable)}")
    return data


@dataclass(frozen=True)
class Catalogue:
    workflows: tuple

    @classmethod
    def load(cls, directory):
        if directory is None:
            return cls(())
        rows = []
        for path in sorted(Path(directory).glob("*.json")):
            try:
                rows.append(validate_workflow(json.loads(path.read_text(encoding="utf-8"))))
            except (CatalogueError, json.JSONDecodeError) as error:
                raise CatalogueError(f"{path.name}: {error}") from error
        keys = [(w["id"], w["version"]) for w in rows]
        if len(keys) != len(set(keys)):
            raise CatalogueError("a workflow id and version appear twice")
        return cls(tuple(rows))

    def get(self, workflow_id, version=None):
        rows = [w for w in self.workflows if w["id"] == workflow_id and (version is None or w["version"] == version)]
        return max(rows, key=lambda w: w["version"]) if rows else None

    def latest(self):
        ids = sorted({w["id"] for w in self.workflows})
        return [self.get(i) for i in ids]

    def routing_facts(self):
        """Facts that decide which workflow applies, merged across the catalogue."""
        merged = {}
        for workflow in self.latest():
            used = condition_facts(workflow.get("applies_when"))
            for fact in workflow["facts"]:
                if fact["id"] in used:
                    current = merged.setdefault(fact["id"], {**fact, "values": list(fact.get("values", []))})
                    for value in fact.get("values", []):
                        if value not in current["values"]:
                            current["values"].append(value)
        return list(merged.values())


def ref(workflow):
    return {"id": workflow["id"], "version": workflow["version"], "title": workflow["title"], "status": workflow["status"]}


def route(catalogue, facts):
    """Select a workflow from routing facts, or say why none was selected."""
    selected, unknown = [], []
    for workflow in catalogue.latest():
        if workflow.get("fallback") or workflow.get("applies_when") is None:
            continue
        verdict = evaluate_condition(workflow["applies_when"], facts)
        if verdict is True:
            selected.append(workflow)
        elif verdict is None:
            unknown.append(workflow)
    if len(selected) == 1:
        return {"status": "selected", "workflow": ref(selected[0]), "candidates": [], "needs": []}
    if len(selected) > 1:
        return {"status": "ambiguous", "workflow": None, "candidates": [ref(w) for w in selected], "needs": []}
    if unknown:
        needs = sorted(set().union(*(condition_facts(w["applies_when"]) for w in unknown)) - {k for k, v in facts.items() if v is not None})
        return {"status": "needs_facts", "workflow": None, "candidates": [ref(w) for w in unknown], "needs": needs}
    fallback = [w for w in catalogue.latest() if w.get("fallback")]
    if len(fallback) == 1:
        return {"status": "fallback", "workflow": ref(fallback[0]), "candidates": [], "needs": []}
    return {"status": "unmapped", "workflow": None, "candidates": [], "needs": []}


def _document_status(document, findings, checked):
    finding = findings.get(document["id"])
    if finding is not None:
        return finding["status"], finding.get("files", []), finding.get("citations", [])
    return ("missing" if checked else "unchecked"), [], []


def evaluate(workflow, facts, findings=None, *, checked=False):
    """Walk the workflow from its start with the established facts.

    ``findings`` maps document ids to accepted document findings
    (``present`` or ``unusable``). ``checked`` says whether a completed run
    has looked for documents, so an absent finding means ``missing`` rather
    than ``unchecked``.
    """
    findings = findings or {}
    steps = {s["id"]: s for s in workflow["steps"]}
    fact_defs = {f["id"]: f for f in workflow["facts"]}
    path, waiting, gaps, outcome = [], [], [], None
    current, via, seen = workflow["start"], None, set()
    while True:
        step = steps[current]
        if current in seen:
            gaps.append({"kind": "loop", "text": f"The workflow returns to “{step['title']}”; it is shown as the current step.",
                         "source_refs": step["source_refs"]})
            path.append({"step": current, "title": step["title"], "role": step.get("role"), "via": via, "state": "current"})
            break
        seen.add(current)
        row = {"step": current, "title": step["title"], "role": step.get("role"), "via": via, "state": "passed",
               "source_refs": step["source_refs"]}
        path.append(row)
        if step.get("outcome"):
            row["state"] = "terminal"
            outcome = next(o for o in workflow.get("outcomes", []) if o["id"] == step["outcome"])
            break
        edges = step.get("next", [])
        if not edges:
            row["state"] = "terminal"
            break
        chosen, blocked = None, set()
        for edge in edges:
            verdict = evaluate_condition(edge.get("when", True), facts)
            if verdict is True:
                chosen = edge
                break
            if verdict is None:
                blocked |= condition_facts(edge["when"]) - {k for k, v in facts.items() if v is not None}
                break
        if chosen is None:
            row["state"] = "current"
            waiting = [{"fact": f, "question": fact_defs[f]["question"], "source_refs": fact_defs[f]["source_refs"]}
                       for f in sorted(blocked)]
            if not blocked:
                gaps.append({"kind": "no_transition", "text": f"No transition from “{step['title']}” matches the established facts.",
                             "source_refs": step["source_refs"]})
            break
        current, via = chosen["to"], chosen.get("label")
    reached = {row["step"] for row in path}
    attached = {d for s in workflow["steps"] for d in s.get("documents", [])}
    needed = {}
    for row in path:
        for document_id in steps[row["step"]].get("documents", []):
            needed.setdefault(document_id, row["step"])
    checklist = []
    for document in workflow["documents"]:
        # A document tied to steps is needed once one of them is reached;
        # one tied to no step belongs to the whole case.
        required = evaluate_condition(document.get("required_when", True), facts)
        step_id = needed.get(document["id"])
        if (document["id"] in attached and step_id is None) or required is False:
            continue
        status, files, citations = _document_status(document, findings, checked)
        checklist.append({"document": document["id"], "title": document["title"], "why": document["why"],
                          "step": step_id, "required": "yes" if required else "depends",
                          "condition_facts": sorted(condition_facts(document.get("required_when"))) if required is None else [],
                          "status": status, "files": files, "citations": citations,
                          "source_refs": document["source_refs"]})
    next_actions = [{"kind": "answer", "fact": w["fact"], "text": w["question"]} for w in waiting]
    next_actions += [{"kind": "obtain", "document": c["document"], "text": c["title"], "why": c["why"]}
                     for c in checklist if c["status"] in {"missing", "unusable"}]
    current_row = next((row for row in path if row["state"] == "current"), None)
    return {"workflow": ref(workflow), "path": path, "current": current_row, "waiting_for": waiting,
            "outcome": outcome, "documents": checklist, "next_actions": next_actions,
            "gaps": gaps + [{"kind": "open_question", **q} for q in workflow.get("open_questions", [])],
            "reached": sorted(reached)}
