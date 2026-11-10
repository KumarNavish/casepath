"""Source-grounded workflow catalogue: validation, routing and step evaluation.

A workflow is data, never code. Every fact, step, branch and document
requirement names the source it came from (a process diagram cell, a guidance
section or a case example). Routing either selects a workflow from the
catalogue, asks for the facts it needs, or says plainly that the case is
unmapped. Nothing here invents a Mobiliar procedure: an empty catalogue routes
every case to ``unmapped``.

Conditions use three-valued logic. An unknown fact never counts as yes or no.
Evaluation defers exactly: the workflow is walked under every completion of the
open facts (each true and false), so a step or document needed under every
answer is needed now, one needed under some answers waits for the questions
whose answers change it, and one needed under none is left out. With no open
fact this is the plain walk.
"""
from dataclasses import dataclass
import itertools
import json
from pathlib import Path
import re

FORMAT = "casepath.workflow/1"
ID = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,79}$")
FACT_TYPES = {"enum", "boolean", "text", "date"}
STATUSES = {"draft", "reviewed"}
SOURCE_KINDS = {"process_diagram", "process_guidance", "case_example", "expert_review", "knowledge", "case_edit"}


# A presumption fills a fact the case files leave unstated, from a named source: "unstated" for a silence rule,
# "routed" for the event a case type presupposes once a case is routed to it. A stated value always wins.
PRESUMPTION_APPLIES = {"unstated", "routed"}


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
        shows = document.get("must_show", [])
        if not isinstance(shows, list) or any(not isinstance(i, str) or not i.strip() for i in shows) or len(set(shows)) != len(shows):
            raise CatalogueError(f"document {document['id']}: must_show is a list of distinct, non-empty items")
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
    for field in data.get("summary", []):
        if not ID.match(str(field.get("id"))) or not field.get("label"):
            raise CatalogueError("each summary field needs an id and a label")
        _refs(field, sources, f"summary field {field.get('id')}")
    for item in data.get("presumptions", []):
        fact = facts.get(item.get("fact"))
        if fact is None:
            raise CatalogueError(f"presumption: unknown fact {item.get('fact')!r}")
        if item.get("applies") not in PRESUMPTION_APPLIES or not item.get("text"):
            raise CatalogueError(f"presumption for {fact['id']!r}: applies must be one of {sorted(PRESUMPTION_APPLIES)} and text is required")
        _check_condition({"fact": fact["id"], "is": item.get("value")}, facts, f"presumption for {fact['id']}")
        _refs({"source_refs": [item.get("source_ref")]}, sources, f"presumption for {fact['id']}")
    if len({p["fact"] for p in data.get("presumptions", [])}) != len(data.get("presumptions", [])):
        raise CatalogueError("at most one presumption per fact")
    for kind in ("open_questions", "notes"):
        for item in data.get(kind, []):
            if not item.get("text"):
                raise CatalogueError(f"each of {kind} needs text")
            _refs(item, sources, kind)
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

    def routable(self):
        """The workflows routing chooses from: example workflows only when the catalogue has nothing else."""
        latest = self.latest()
        real = [w for w in latest if not w.get("example")]
        return real or latest

    def routing_facts(self):
        """Facts that decide which workflow applies, merged across the catalogue."""
        merged = {}
        for workflow in self.routable():
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


def _satisfying(condition):
    """The fact values a plain condition (``is``, or ``all`` of them) states, so a presumed routing fact can carry its value."""
    if isinstance(condition, dict) and "all" in condition:
        out = {}
        for child in condition["all"]:
            out.update(_satisfying(child))
        return out
    if isinstance(condition, dict) and "is" in condition and "fact" in condition:
        return {condition["fact"]: condition["is"]}
    return {}


def route(catalogue, facts):
    """Select a workflow from routing facts, or say why none was selected.

    A workflow whose condition the facts leave open can still apply. When exactly one workflow can apply (no other
    workflow's condition holds or is open, and no fallback stands beside it), it is selected and the routing facts its
    condition needs are recorded as presumed from routing (``presumed``). The case is handed over only when no workflow
    can apply or several remain."""
    selected, unknown = [], []
    known = {k for k, v in facts.items() if v is not None}
    for workflow in catalogue.routable():
        if workflow.get("fallback") or workflow.get("applies_when") is None:
            continue  # a workflow without a routing condition is chosen by a person, never by routing
        verdict = evaluate_condition(workflow["applies_when"], facts)
        if verdict is True:
            selected.append(workflow)
        elif verdict is None:
            unknown.append(workflow)
    fallback = [w for w in catalogue.routable() if w.get("fallback")]
    if len(selected) == 1:
        return {"status": "selected", "workflow": ref(selected[0]), "candidates": [], "needs": []}
    if len(selected) > 1:
        return {"status": "ambiguous", "workflow": None, "candidates": [ref(w) for w in selected], "needs": []}
    if len(unknown) == 1 and not fallback:
        only = unknown[0]
        open_facts = sorted(condition_facts(only["applies_when"]) - known)
        values = _satisfying(only["applies_when"])
        return {"status": "selected", "workflow": ref(only), "candidates": [], "needs": [],
                "presumed": [{"fact": f, "value": values.get(f)} for f in open_facts]}
    if unknown:
        needs = sorted(set().union(*(condition_facts(w["applies_when"]) for w in unknown)) - known)
        return {"status": "needs_facts", "workflow": None, "candidates": [ref(w) for w in unknown + fallback], "needs": needs}
    if len(fallback) == 1:
        return {"status": "fallback", "workflow": ref(fallback[0]), "candidates": [], "needs": []}
    return {"status": "unmapped", "workflow": None, "candidates": [], "needs": []}


def _join(steps, edges):
    """The step every branch reaches next, when each branch is one plain step."""
    joins = set()
    for edge in edges:
        branch = steps[edge["to"]]
        onward = branch.get("next", [])
        if len(onward) != 1 or onward[0].get("when", True) is not True or branch.get("documents") or branch.get("outcome"):
            return None
        joins.add(onward[0]["to"])
    return joins.pop() if len(joins) == 1 else None


def _document_status(document, findings, checked):
    finding = findings.get(document["id"])
    if finding is not None:
        return finding["status"], finding.get("files", []), finding.get("citations", [])
    return ("missing" if checked else "unchecked"), [], []


def _walk(workflow, facts, findings=None, *, checked=False):
    """Walk the workflow from its start with the established facts, stopping at the first open branch.

    ``findings`` maps document ids to accepted document findings
    (``present`` or ``unusable``). ``checked`` says whether a completed run
    has looked for documents, so an absent finding means ``missing`` rather
    than ``unchecked``.
    """
    findings = findings or {}
    steps = {s["id"]: s for s in workflow["steps"]}
    fact_defs = {f["id"]: f for f in workflow["facts"]}
    path, waiting, gaps, outcome, unmet = [], [], [], None, []
    current, via, seen, last_edge = workflow["start"], None, set(), None
    while True:
        step = steps[current]
        if current in seen:
            when = (last_edge or {}).get("when")
            # A gate that sends the case back names the conditions that failed.
            if isinstance(when, dict) and "any" in when:
                failing = sorted({f for c in when["any"] if evaluate_condition(c, facts) is True for f in condition_facts(c)})
                unmet = [{"fact": f, "question": fact_defs[f]["question"], "value": facts.get(f), "source_refs": fact_defs[f]["source_refs"]}
                         for f in failing]
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
        if chosen is None and blocked:
            join = _join(steps, edges)
            if join is not None:
                # Every branch rejoins one step later without asking for anything,
                # so an open answer here does not hold the case up.
                row["either"] = sorted(blocked)
                current, via = join, None
                continue
        if chosen is None:
            row["state"] = "current"
            waiting = [{"fact": f, "question": fact_defs[f]["question"], "source_refs": fact_defs[f]["source_refs"]}
                       for f in sorted(blocked)]
            if not blocked:
                gaps.append({"kind": "no_transition", "text": f"No transition from “{step['title']}” matches the established facts.",
                             "source_refs": step["source_refs"]})
            break
        current, via, last_edge = chosen["to"], chosen.get("label"), chosen
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
        # A suggestion from not-yet-active Knowledge is checked but never counted as missing.
        need = "suggested" if document.get("suggested") else "optional" if document.get("optional") else "yes" if required else "depends"
        checklist.append({"document": document["id"], "title": document["title"], "why": document["why"],
                          "step": step_id, "required": need,
                          "condition_facts": sorted(condition_facts(document.get("required_when"))) if required is None else [],
                          "status": status, "files": files, "citations": citations,
                          "source_refs": document["source_refs"]})
    next_actions = [{"kind": "answer", "fact": w["fact"], "text": w["question"]} for w in waiting]
    # An unmet condition on a fact nobody has established is a question to answer, not a value to resolve.
    next_actions += [{"kind": "answer", "fact": u["fact"], "text": u["question"]} if u["value"] is None else
                     {"kind": "resolve", "fact": u["fact"], "text": u["question"], "value": u["value"]} for u in unmet]
    next_actions += [{"kind": "obtain", "document": c["document"], "text": c["title"], "why": c["why"]}
                     for c in checklist if c["status"] in {"missing", "unusable"} and c["required"] not in {"suggested", "optional"}]
    current_row = next((row for row in path if row["state"] == "current"), None)
    return {"workflow": ref(workflow), "path": path, "current": current_row, "waiting_for": waiting, "unmet": unmet,
            "outcome": outcome, "documents": checklist, "next_actions": next_actions,
            "gaps": gaps + [{"kind": "open_question", **q} for q in workflow.get("open_questions", [])],
            "reached": sorted(reached)}


# At most 2**8 = 256 completions: a 150-step workflow then evaluates in under 50 ms, and the live view evaluates on
# every state change. The largest workflows in use decide on at most 7 facts; above the cap the walk stops at the first
# open branch and says so.
MAX_OPEN_FACTS = 8


def _used_facts(workflow):
    used = set()
    for step in workflow["steps"]:
        for edge in step.get("next", []):
            used |= condition_facts(edge.get("when", True))
    for document in workflow["documents"]:
        used |= condition_facts(document.get("required_when", True))
    return used


OTHER = "__any_other_value__"


def _domain(workflow, fact):
    """The answers an open fact can take: yes and no, an enum's values, or the values the workflow's conditions name plus
    any other value."""
    if fact["type"] == "boolean":
        return [True, False]
    if fact["type"] == "enum":
        return list(fact["values"])
    named = []

    def visit(condition):
        if not isinstance(condition, dict):
            return
        for key in ("all", "any"):
            for child in condition.get(key, ()):
                visit(child)
        if "not" in condition:
            visit(condition["not"])
        if condition.get("fact") == fact["id"]:
            for value in condition.get("in", [condition["is"]] if "is" in condition else []):
                if value not in named:
                    named.append(value)
    for step in workflow["steps"]:
        for edge in step.get("next", []):
            visit(edge.get("when"))
    for document in workflow["documents"]:
        visit(document.get("required_when"))
    return named + [OTHER]


def _count(domains):
    total = 1
    for d in domains:
        total *= len(d)
    return total


def evaluate(workflow, facts, findings=None, *, checked=False):
    """Evaluate the workflow with the established facts, deferring exactly on the open ones.

    ``findings`` maps document ids to accepted document findings (``present`` or
    ``unusable``). ``checked`` says whether a completed run has looked for
    documents, so an absent finding means ``missing`` rather than ``unchecked``.

    With no open fact the result is the plain walk. Otherwise the walk runs under
    every completion of the open facts the workflow uses (yes and no, an enum's values): a document needed under
    every completion is listed as it would be if the facts were known; one needed
    under some is listed as ``depends`` with the questions whose answers change it;
    one needed under none is left out. Steps beyond the open question are listed in
    ``beyond``: ``reached`` under every completion, ``pending`` under some.
    ``waiting_for`` names exactly the open facts whose answer changes a step or a
    document. Above ``MAX_OPEN_FACTS`` open facts the plain walk is returned and
    ``deferral`` says so.
    """
    findings = findings or {}
    base = _walk(workflow, facts, findings, checked=checked)
    open_facts = sorted(f for f in _used_facts(workflow) if facts.get(f) is None)
    if not open_facts:
        return base
    if len(open_facts) > MAX_OPEN_FACTS:
        base["deferral"] = {"mode": "first_open_branch", "open_facts": open_facts,
                            "reason": f"{len(open_facts)} open facts exceed the limit of {MAX_OPEN_FACTS}; the walk stops at the first open branch"}
        return base
    fact_defs = {f["id"]: f for f in workflow["facts"]}
    domains = [_domain(workflow, fact_defs[f]) for f in open_facts]
    asked_known = _known_facts(workflow)
    domains = [d + [UNSET] if f in asked_known else d for f, d in zip(open_facts, domains)]  # it may also stay unknown
    if _count(domains) > 2 ** MAX_OPEN_FACTS:
        base["deferral"] = {"mode": "first_open_branch", "open_facts": open_facts,
                            "reason": "too many answers to compare; the walk stops at the first open branch"}
        return base
    fast = _Reach(workflow)
    combos = list(itertools.product(*domains))
    completions = []  # (answer values, ordered path, items needed as a bit set, document needs)
    bit = {}  # ("step", id) or ("document", id) -> its bit

    def bits(items):
        mask = 0
        for item in items:
            if item not in bit:
                bit[item] = 1 << len(bit)
            mask |= bit[item]
        return mask
    for values in itertools.product(*domains):
        answer = {f: v for f, v in zip(open_facts, values) if v is not UNSET}
        path, needs = fast.reach({**facts, **answer})
        completions.append((values, path, bits([("step", x) for x in path] + [("document", d) for d in needs]), needs))
    total = len(completions)
    common = every = completions[0][2]
    for c in completions[1:]:
        common &= c[2]
        every |= c[2]
    # What each open fact changes, in one pass per fact: within each group of completions that differ only in that
    # fact's answer, an item needed in some but not all members is changed by it.
    changed_by = {}
    for i, fact in enumerate(open_facts):
        groups = {}
        for values, _p, items, _n in completions:
            key = values[:i] + values[i + 1:]
            seen = groups.get(key)
            groups[key] = (items, items) if seen is None else (seen[0] | items, seen[1] & items)
        mask = 0
        for union, inter in groups.values():
            mask |= union & ~inter
        changed_by[fact] = mask

    def changes(kind, key):
        b = bit.get((kind, key), 0)
        return sorted(f for f in open_facts if changed_by[f] & b)

    def has(mask, kind, key):
        return bool(mask & bit.get((kind, key), 0))

    def questions(names):
        return [{"fact": f, "question": fact_defs[f]["question"], "source_refs": fact_defs[f]["source_refs"]} for f in names]

    # The plain walk's path holds only steps every completion reaches. A rejoin over branches that do not cover every
    # answer can pass a step some completion never reaches; the path then stops before it, at the open question.
    path = []
    for row in base["path"]:
        if not has(common, "step", row["step"]):
            break
        path.append(row)
    current = base["current"]
    if len(path) < len(base["path"]):
        last = dict(path[-1])
        last.pop("either", None)
        last["state"] = "current"
        path[-1] = last
        current = last
    on_path = {r["step"] for r in path}
    titles = {s["id"]: s for s in workflow["steps"]}
    deciding = set()
    beyond, order = [], []
    for _v, steps_in_order, _i, _n in completions:
        for step_id in steps_in_order:
            if step_id not in on_path and step_id not in order:
                order.append(step_id)
    for step_id in order:
        step = titles[step_id]
        entry = {"step": step_id, "title": step["title"], "role": step.get("role"),
                 "state": "reached" if has(common, "step", step_id) else "pending"}
        if entry["state"] == "pending":
            entry["depends_on"] = changes("step", step_id)
            deciding |= set(entry["depends_on"])
        beyond.append(entry)
    full = {}

    def full_walk(index):
        if index not in full:
            values = completions[index][0]
            answer = {f: v for f, v in zip(open_facts, values) if v is not UNSET}
            full[index] = {d["document"]: d for d in _walk(workflow, {**facts, **answer}, findings, checked=checked)["documents"]}
        return full[index]

    checklist = []
    for document in workflow["documents"]:
        if not has(every, "document", document["id"]):
            continue
        b = bit[("document", document["id"])]
        first = next(i for i, c in enumerate(completions) if c[2] & b)
        row = dict(full_walk(first)[document["id"]])
        if not has(common, "document", document["id"]):
            facts_here = changes("document", document["id"])
            deciding |= set(facts_here)
            row.update(required="depends", condition_facts=facts_here, questions=questions(facts_here))
        else:
            needs = {c[3][document["id"]] for c in completions}
            row["required"] = "yes" if "yes" in needs else row["required"]
        checklist.append(row)
    # The outcome stays the plain walk's: a case is not at its end while a question that changes its process is open.
    outcome = base["outcome"] if len(path) == len(base["path"]) else None
    waiting = questions(sorted(deciding))
    next_actions = [{"kind": "answer", "fact": w["fact"], "text": w["question"]} for w in waiting]
    next_actions += [a for a in base["next_actions"] if a["kind"] in {"answer", "resolve"} and a["fact"] not in deciding]
    next_actions += [{"kind": "obtain", "document": c["document"], "text": c["title"], "why": c["why"]}
                     for c in checklist if c["status"] in {"missing", "unusable"} and c["required"] not in {"suggested", "optional", "depends"}]
    reached = sorted(on_path | {b["step"] for b in beyond if b["state"] == "reached"})
    return {**base, "path": path, "current": current, "outcome": outcome, "waiting_for": waiting, "documents": checklist,
            "next_actions": next_actions, "beyond": beyond, "reached": reached,
            "deferral": {"mode": "exact", "open_facts": open_facts, "completions": total}}


UNSET = object()  # an answer that leaves a fact unknown, for facts a condition asks to be known or not


def _known_facts(workflow):
    found = set()

    def visit(condition):
        if not isinstance(condition, dict):
            return
        for key in ("all", "any"):
            for child in condition.get(key, ()):
                visit(child)
        if "not" in condition:
            visit(condition["not"])
        if "known" in condition:
            found.add(condition.get("fact"))
    for step in workflow["steps"]:
        for edge in step.get("next", []):
            visit(edge.get("when"))
    for document in workflow["documents"]:
        visit(document.get("required_when"))
    return found


class _Reach:
    """The plain walk's path and the documents it lists, without building rows: the same rules as ``_walk``."""

    def __init__(self, workflow):
        self.steps = {s["id"]: s for s in workflow["steps"]}
        self.start = workflow["start"]
        self.documents = workflow["documents"]
        self.attached = {d for s in workflow["steps"] for d in s.get("documents", [])}

    def reach(self, facts):
        steps, current, seen, path = self.steps, self.start, set(), []
        while True:
            step = steps[current]
            if current in seen:
                path.append(current)
                break
            seen.add(current)
            path.append(current)
            if step.get("outcome") or not step.get("next"):
                break
            chosen, blocked = None, False
            for edge in step["next"]:
                verdict = evaluate_condition(edge.get("when", True), facts)
                if verdict is True:
                    chosen = edge
                    break
                if verdict is None:
                    blocked = bool(condition_facts(edge["when"]) - {k for k, v in facts.items() if v is not None})
                    break
            if chosen is None and blocked:
                join = _join(steps, step["next"])
                if join is not None:
                    current = join
                    continue
            if chosen is None:
                break
            current = chosen["to"]
        on_path = set()
        for x in set(path):
            on_path.update(steps[x].get("documents", ()))
        needs = {}
        for document in self.documents:
            if document["id"] in self.attached and document["id"] not in on_path:
                continue
            required = evaluate_condition(document.get("required_when", True), facts)
            if required is False:
                continue
            needs[document["id"]] = ("suggested" if document.get("suggested") else "optional" if document.get("optional")
                                     else "yes" if required else "depends")
        return path, needs


def presumed(workflow, recorded):
    """The workflow's presumptions that apply: each names a fact for which the files gave no quotation at all.

    ``recorded`` maps fact ids to what the case work holds for them (``status`` and ``citations``). A fact that was
    established, found conflicting, or recorded as unknown with a quotation keeps its own state."""
    out = {}
    for item in workflow.get("presumptions", []):
        row = recorded.get(item["fact"])
        if row is None or (row.get("status") == "unknown" and not row.get("citations")):
            out[item["fact"]] = item
    return out
