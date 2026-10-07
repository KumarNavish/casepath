"""Editable, deterministic process projection. This module admits no evidence.

Applicability describes the planned path; readiness also requires a completed
predecessor and every explicit prerequisite. Document presence never establishes
document sufficiency. Human validation concerns one structure, not its sources.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .assessment_grammar_v1 import _and, _not, _or
from .workspace_corpus import digest_value


CONTRACT = "casepath.causal-process/1.0.0"
VERDICTS = {"true", "false", "unresolved"}
RELATIONS = {"enables", "requires", "causes", "blocks", "invalidates", "branches_to",
             "conditionally_activates", "completes", "supersedes"}
FLOW = RELATIONS - {"blocks", "invalidates", "supersedes", "requires"}
VALIDATION = {"unvalidated", "validated", "rejected", "revised"}
TRUE = {"const": "true"}
NODE_FIELDS = {"node_id", "label", "meaning", "kind", "condition", "document_types", "entry",
               "completed", "validation", "provenance", "authority", "responsibility", "terminal"}
EDGE_FIELDS = {"edge_id", "source_node_id", "target_node_id", "relation", "condition", "label",
               "validation", "provenance"}
DOCUMENT_FIELDS = {"document_type", "label", "condition", "condition_flag", "requirement_class",
                   "held_files", "authority", "reason"}
GRAPH_FIELDS = {"contract", "family", "claim_id", "revision", "nodes", "edges", "conditions",
                "document_catalog", "assessment_context", "history", "fragment_instances"}


def _text(value: Any, label: str, limit: int = 2000) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{label} must be nonempty text of at most {limit} characters")


def _expression(expression: Any, flags: Mapping[str, Any], depth: int = 0,
                budget: list[int] | None = None) -> set[str]:
    """Closed expression grammar. Unknown flags and operators are never true."""
    budget = [128] if budget is None else budget
    budget[0] -= 1
    if not isinstance(expression, dict) or len(expression) != 1 or depth > 8 or budget[0] < 0:
        raise ValueError("condition must be one bounded expression")
    operation, value = next(iter(expression.items()))
    if operation == "const":
        if not isinstance(value, str) or value not in VERDICTS:
            raise ValueError("condition constant must be true, false or unresolved")
        return set()
    if operation == "flag":
        if not isinstance(value, str) or value not in flags:
            raise ValueError("condition refers to an unknown flag")
        return {value}
    if operation == "not":
        return _expression(value, flags, depth + 1, budget)
    if operation in {"all", "any"} and isinstance(value, list) and 1 <= len(value) <= 12:
        return set().union(*(_expression(item, flags, depth + 1, budget) for item in value))
    raise ValueError("unsupported condition expression")


def _verdict(expression: Mapping[str, Any], flags: Mapping[str, Any]) -> str:
    operation, value = next(iter(expression.items()))
    if operation == "const":
        return value
    if operation == "flag":
        return flags[value]["verdict"]
    if operation == "not":
        return _not(_verdict(value, flags))
    values = [_verdict(item, flags) for item in value]
    if operation == "all":
        return _and(*values)
    return "true" if "true" in values else "unresolved" if "unresolved" in values else "false"


def _unresolved_literal(expression: Mapping[str, Any], flags: Mapping[str, Any]) -> bool:
    """Find explicit unknowns that still matter under the current case facts."""
    if _verdict(expression, flags) != "unresolved":
        return False
    operation, value = next(iter(expression.items()))
    if operation == "const":
        return value == "unresolved"
    if operation == "flag":
        return False
    if operation == "not":
        return _unresolved_literal(value, flags)
    return any(_unresolved_literal(item, flags) for item in value)


def _entity_defaults(row: dict[str, Any], *, edge: bool = False) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("process entity must be an object")
    row = deepcopy(row)
    row.setdefault("condition", deepcopy(TRUE))
    row.setdefault("validation", {"status": "unvalidated"})
    row.setdefault("provenance", {"kind": "manual", "source": "handler"})
    if edge:
        row.setdefault("relation", "enables")
        if not isinstance(row["relation"], str):
            raise ValueError("relationship type must be text")
        row.setdefault("label", row["relation"].replace("_", " "))
    else:
        row.setdefault("meaning", row.get("label", ""))
        row.setdefault("kind", "action")
        row.setdefault("document_types", [])
        row.setdefault("entry", False)
        row.setdefault("completed", False)
        row.setdefault("authority", None)
        row.setdefault("responsibility", "claim_handler")
        row.setdefault("terminal", False)
    return row


def _topological(graph: Mapping[str, Any]) -> list[str]:
    ids = [row["node_id"] for row in graph["nodes"]]
    incoming = {key: 0 for key in ids}
    outgoing = {key: [] for key in ids}
    for edge in graph["edges"]:
        source, target = edge["source_node_id"], edge["target_node_id"]
        if source not in incoming or target not in incoming:
            raise ValueError("relationship has a dangling node reference")
        incoming[target] += 1
        outgoing[source].append(target)
    ordered, queue = [], [key for key in ids if incoming[key] == 0]
    while queue:
        key = queue.pop(0)
        ordered.append(key)
        for target in outgoing[key]:
            incoming[target] -= 1
            if incoming[target] == 0:
                queue.append(target)
    if len(ordered) != len(ids):
        raise ValueError("process relationships must not contain cycles")
    return ordered


def validate_graph(graph: Mapping[str, Any]) -> None:
    """Reject malformed or unbounded graphs before any mutation is persisted."""
    if graph.get("contract") != CONTRACT:
        raise ValueError("unsupported causal process contract")
    _text(graph.get("family"), "family", 120)
    _text(graph.get("claim_id"), "claim_id", 120)
    if type(graph.get("revision")) is not int or graph["revision"] < 0:
        raise ValueError("invalid graph revision")
    conditions = graph.get("conditions")
    if not isinstance(conditions, dict) or len(conditions) > 100:
        raise ValueError("invalid condition catalog")
    for name, condition in conditions.items():
        _text(name, "condition name", 120)
        if (not isinstance(condition, dict) or not isinstance(condition.get("verdict"), str)
                or condition["verdict"] not in VERDICTS):
            raise ValueError("condition verdict must be true, false or unresolved")
    for field, key, limit in (("nodes", "node_id", 100), ("edges", "edge_id", 300),
                              ("document_catalog", "document_type", 100)):
        rows = graph.get(field)
        if not isinstance(rows, list) or len(rows) > limit:
            raise ValueError(f"{field} exceeds its supported limit")
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(f"invalid {field} entry")
            _text(row.get(key), key, 120)
            if row[key] in seen:
                raise ValueError(f"duplicate {key}")
            seen.add(row[key])
            _text(row.get("label"), "label", 500)
            _expression(row["condition"], conditions)
    documents = {row["document_type"] for row in graph["document_catalog"]}
    for node in graph["nodes"]:
        if set(node) - NODE_FIELDS:
            raise ValueError("unsupported node field")
        _text(node["meaning"], "node meaning", 8000)
        _text(node["responsibility"], "responsibility", 120)
        if not isinstance(node["kind"], str) or node["kind"] not in {"state", "action", "decision", "prerequisite", "outcome"}:
            raise ValueError("unsupported process node kind")
        if any(type(node[field]) is not bool for field in ("entry", "completed", "terminal")):
            raise ValueError("entry, completed and terminal must be booleans")
        refs = node["document_types"]
        if not isinstance(refs, list) or any(not isinstance(item, str) for item in refs):
            raise ValueError("node document references must be a list")
        if len(refs) != len(set(refs)) or set(refs) - documents:
            raise ValueError("node has duplicate or unknown document references")
    for edge in graph["edges"]:
        if set(edge) - EDGE_FIELDS or not isinstance(edge["relation"], str) or edge["relation"] not in RELATIONS:
            raise ValueError("unsupported relationship")
        for key in ("source_node_id", "target_node_id"):
            _text(edge.get(key), key, 120)
    for row in graph["nodes"] + graph["edges"]:
        if (not isinstance(row["validation"], dict) or not isinstance(row["validation"].get("status"), str)
                or row["validation"]["status"] not in VALIDATION):
            raise ValueError("invalid validation state")
        if not isinstance(row["provenance"], dict):
            raise ValueError("process provenance must be an object")
    for document in graph["document_catalog"]:
        if (set(document) - DOCUMENT_FIELDS or not isinstance(document["requirement_class"], str)
                or document["requirement_class"] not in {"mandatory", "conditional", "optional"}):
            raise ValueError("unsupported document definition")
        if not isinstance(document["held_files"], list) or len(document["held_files"]) > 100:
            raise ValueError("invalid held document list")
        for item in document["held_files"]:
            if not isinstance(item, dict) or not isinstance(item.get("artifact_id"), str):
                raise ValueError("held documents require artifact references")
    if not isinstance(graph.get("history"), list) or len(graph["history"]) > 2000:
        raise ValueError("graph history limit reached")
    if not isinstance(graph.get("assessment_context"), dict):
        raise ValueError("assessment context must be an object")
    _topological(graph)


def seal_graph(graph: Mapping[str, Any]) -> dict[str, Any]:
    """Copy and normalize a graph; never alias reusable definition snapshots."""
    result = {key: deepcopy(value) for key, value in graph.items() if key in GRAPH_FIELDS}
    result.setdefault("contract", CONTRACT)
    result.setdefault("revision", 0)
    result.setdefault("conditions", {})
    result.setdefault("assessment_context", {})
    result.setdefault("history", [])
    result.setdefault("edges", [])
    result.setdefault("document_catalog", [])
    result["nodes"] = [_entity_defaults({key: value for key, value in row.items() if key in NODE_FIELDS})
                       for row in result.get("nodes", [])]
    result["edges"] = [_entity_defaults({key: value for key, value in row.items() if key in EDGE_FIELDS}, edge=True)
                       for row in result["edges"]]
    for document in result["document_catalog"]:
        document.setdefault("condition", deepcopy(TRUE))
        document["condition_flag"] = document["condition"].get("flag") if isinstance(document["condition"], dict) else None
        document.setdefault("requirement_class", "mandatory")
        document.setdefault("held_files", [])
        document.setdefault("authority", None)
        document.setdefault("reason", "Required by the linked process step.")
    validate_graph(result)
    result["graph_sha256"] = digest_value(result)
    return result


def _catalog_condition(label: str) -> dict[str, Any] | None:
    names = {"health effects alleged": "health_effects", "technical inspection needed": "specialist_needed",
             "deposit route remains relevant": "deposit_considered", "termination received": "termination_received",
             "arrears termination": "arrears", "family-home ordinary termination": "family_home",
             "extension relevant": "extension_relevant", "claim received": "claim_received",
             "reference-rate reason selected": "reference_rate", "renovation reason selected": "renovation"}
    negative = {"no immediate health escalation": "health_effects", "no extension branch": "extension_relevant"}
    both_false = {"no further specialist or deposit branch": ("specialist_needed", "deposit_considered"),
                  "no special precondition branch": ("arrears", "family_home"),
                  "no specialist calculation branch": ("reference_rate", "renovation")}
    if label in names:
        return {"flag": names[label]}
    if label in negative:
        return {"not": {"flag": negative[label]}}
    if label in both_false:
        return {"all": [{"not": {"flag": name}} for name in both_false[label]]}
    if label == "deposit route considered without specialist":
        return {"all": [{"flag": "deposit_considered"}, {"not": {"flag": "specialist_needed"}}]}
    return None


def build_graph(corpus: Any, claim_id: str, assessment: Mapping[str, Any]) -> dict[str, Any]:
    """Seed only from the current product policy and the supplied assessment."""
    steps = {row["node_id"]: row for row in assessment["steps"]}
    templates = [row for row in corpus.static_policy()["templates"]
                 if any(node["node_id"] in steps for node in row["process_catalog"]["nodes"])]
    if len(templates) != 1:
        raise ValueError("assessment does not identify one process family")
    template, documents = templates[0], []
    catalog = template["process_catalog"]
    saved_docs = {row["document_type"]: row for row in assessment["documents"]}
    for row in catalog["documents"]:
        saved = saved_docs[row["document_type"]]
        flag = saved.get("condition_flag")
        documents.append({key: deepcopy(saved[key]) for key in DOCUMENT_FIELDS if key in saved})
        documents[-1]["condition"] = {"flag": flag} if flag else deepcopy(TRUE)
        documents[-1]["reason"] = row["assertion"]
    nodes = []
    for index, row in enumerate(catalog["nodes"]):
        nodes.append({"node_id": row["node_id"], "label": row["label"], "meaning": row["assertion"],
                      "kind": "outcome" if row["terminal"] else "action", "entry": index == 0,
                      "completed": steps[row["node_id"]]["state"] == "done",
                      "responsibility": row["responsibility"], "terminal": row["terminal"],
                      "document_types": [doc["document_type"] for doc in catalog["documents"]
                                         if row["node_id"] in doc["required_at_node_ids"]],
                      "authority": deepcopy(steps[row["node_id"]].get("authority")),
                      "provenance": {"kind": "inferred", "source": "static_policy", "family": template["domain"]}})
    edges = []
    # These labels are operational completion transitions, not factual verdicts.
    completion_labels = {"safety advice recorded", "timeline drafted", "notice position recorded",
                         "causation status recorded", "evidence gaps identified", "inspection result available",
                         "deposit safeguards assessed", "outcome recorded", "deadline position recorded",
                         "formal review complete", "arrears preconditions assessed", "family service assessed",
                         "hardship factors recorded", "evidence collection closed", "baseline reconstructed",
                         "cost evidence screened", "assessment recorded", "resolution recorded"}
    for row in catalog["transitions"]:
        condition = _catalog_condition(row["condition"])
        if condition is None and row["condition"] not in completion_labels:
            raise ValueError("unknown catalog transition condition")
        edges.append({"edge_id": row["edge_id"], "source_node_id": row["source_node_id"],
                      "target_node_id": row["target_node_id"], "label": row["condition"],
                      "relation": "branches_to" if condition is not None else "enables",
                      "condition": condition or deepcopy(TRUE),
                      "provenance": {"kind": "inferred", "source": "static_policy", "assertion": row["assertion"]}})
    context = {key: deepcopy(value) for key, value in assessment.items()
               if key not in {"conditions", "steps", "documents", "next_step", "assessment_sha256"}}
    return seal_graph({"family": template["domain"], "claim_id": claim_id, "nodes": nodes, "edges": edges,
                       "conditions": deepcopy(assessment["conditions"]), "document_catalog": documents,
                       "assessment_context": context})


def _document_definition_sha256(document: Mapping[str, Any]) -> str:
    return digest_value({key: value for key, value in document.items() if key != "held_files"})


def _document_review_state(document: Mapping[str, Any]) -> str:
    identity = _document_definition_sha256(document)
    current = [item for item in document["held_files"] if item.get("document_definition_sha256") == identity]
    if any(item.get("review") == "sufficient" for item in current):
        return "sufficient"
    if any(item.get("review") == "insufficient" for item in current):
        return "insufficient"
    return "review_needed" if document["held_files"] else "missing"


def refresh_document(graph: Mapping[str, Any], document_type: str, receipt: Mapping[str, Any],
                     actor: str, reason: str) -> dict[str, Any]:
    """Record a server-checked source review; this is not a public edit operation.

    The caller must verify the artifact, bytes and quote against the claim's
    original source. Sufficiency is the named human's assessment of this one
    document requirement, and does not admit claim facts or authorize a decision.
    """
    graph = seal_graph(graph)
    _text(actor, "reviewing handler", 80)
    _text(reason, "review reason", 1000)
    _text(document_type, "document type", 120)
    required = {"artifact_id", "file_name", "sha256", "media_type", "source_quote", "review", "reviewed_by", "note"}
    if not isinstance(receipt, dict) or set(receipt) != required:
        raise ValueError("source review requires one checked receipt")
    for key in ("artifact_id", "file_name", "media_type", "note"):
        _text(receipt[key], key)
    sha = receipt["sha256"]
    if not isinstance(sha, str) or len(sha) != 64 or any(letter not in "0123456789abcdef" for letter in sha):
        raise ValueError("source receipt requires a SHA-256 identity")
    if receipt["reviewed_by"] != actor:
        raise ValueError("source review actor differs from its receipt")
    if not isinstance(receipt["review"], str) or receipt["review"] not in {"received", "sufficient", "insufficient"}:
        raise ValueError("unsupported source review")
    if not isinstance(receipt["source_quote"], str) or len(receipt["source_quote"]) > 8000:
        raise ValueError("invalid checked source quote")
    if receipt["review"] == "sufficient":
        _text(receipt["source_quote"], "checked source quote", 8000)
    result = deepcopy(graph)
    document = next((row for row in result["document_catalog"] if row["document_type"] == document_type), None)
    if document is None:
        raise ValueError("source review refers to an unknown document requirement")
    before = deepcopy(document)
    checked = {**deepcopy(receipt), "document_definition_sha256": _document_definition_sha256(document)}
    document["held_files"] = [item for item in document["held_files"] if item["artifact_id"] != receipt["artifact_id"]] + [checked]
    result["revision"] += 1
    result["history"].append({"revision": result["revision"],
                               "operation": {"type": "document.review", "document_type": document_type,
                                             "artifact_id": receipt["artifact_id"], "review": receipt["review"],
                                             "actor": actor, "reason": reason},
                               "before": before, "after": deepcopy(document),
                               "previous_graph_sha256": graph["graph_sha256"]})
    return seal_graph(result)


def evaluate(graph: Mapping[str, Any], conditions: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Derive applicability, execution readiness, questions and document routes."""
    graph = seal_graph(graph)
    flags = deepcopy(graph["conditions"])
    if conditions is not None:
        if set(conditions) - set(flags):
            raise ValueError("unknown condition override")
        for key, value in conditions.items():
            verdict = value.get("verdict") if isinstance(value, dict) else value
            if not isinstance(verdict, str) or verdict not in VERDICTS:
                raise ValueError("invalid condition override")
            flags[key] = {"verdict": verdict, "worker": "handler_sandbox", "quote": None,
                          "candidate_quote": None, "source_id": None}
    nodes = {row["node_id"]: deepcopy(row) for row in graph["nodes"]}
    edges = deepcopy(graph["edges"])
    incoming = {key: [] for key in nodes}
    for edge in edges:
        edge["condition_verdict"] = _verdict(edge["condition"], flags)
        incoming[edge["target_node_id"]].append(edge)
    for key in _topological(graph):
        node, path, ready_paths = nodes[key], "false", []
        dependencies = _expression(node["condition"], flags)
        blocked, unresolved, derived_complete = [], [], False
        if node["entry"]:
            path, ready_paths = "true", [True]
        for edge in incoming[key]:
            source = nodes[edge["source_node_id"]]
            rejected = edge["validation"]["status"] == "rejected"
            active = "false" if rejected else _and(source["activation"], edge["condition_verdict"])
            relation = edge["relation"]
            edge["condition_flags"] = sorted(set(source["condition_flags"]) | _expression(edge["condition"], flags))
            if not rejected and active != "false":
                dependencies.update(edge["condition_flags"])
            if relation in {"causes", "completes"}:
                active = _and(active, "true" if source["effective_completed"] and not source["inconsistent_completion"] else "false")
            edge["activation"] = active
            if relation in FLOW:
                path = _or(path, active)
                if active == "true":
                    ready_paths.append(source["effective_completed"] and not source["inconsistent_completion"])
                if relation == "completes" and active == "true":
                    derived_complete = True
            if relation == "requires" and not rejected and edge["condition_verdict"] != "false":
                if edge["condition_verdict"] == "unresolved" or source["activation"] == "unresolved":
                    unresolved.append(source["node_id"])
                if not source["effective_completed"] or source["inconsistent_completion"] or active != "true":
                    blocked.append(source["node_id"])
            if relation == "blocks" and active == "true":
                blocked.append(source["node_id"])
            if relation in {"blocks", "invalidates", "supersedes"} and active == "unresolved":
                unresolved.append(source["node_id"])
        activation = _and(path, _verdict(node["condition"], flags))
        if node["validation"]["status"] == "rejected":
            activation = "false"
        suppressors = [edge for edge in incoming[key] if edge["relation"] in {"invalidates", "supersedes"}
                       and edge["activation"] == "true"]
        if suppressors:
            activation = "false"
        elif unresolved and activation == "true" and not blocked:
            activation = "unresolved"
        completed = node["completed"] or derived_complete
        if activation == "false":
            state = "inactive"
        elif activation == "unresolved":
            state = "unresolved"
        elif blocked or not any(ready_paths):
            state = "blocked"
        else:
            state = "ready"
        missing_documents = [doc["document_type"] for doc in graph["document_catalog"]
                             if doc["document_type"] in node["document_types"]
                             and doc["requirement_class"] != "optional" and _document_review_state(doc) != "sufficient"
                             and _verdict(doc["condition"], flags) != "false"]
        inconsistent = completed and (state != "ready" or bool(missing_documents))
        if completed and not inconsistent:
            state = "completed"
        node.update(activation=activation, execution_state=state, effective_completed=completed,
                    inconsistent_completion=inconsistent, blocked_by=list(dict.fromkeys(blocked)),
                    unresolved_dependencies=list(dict.fromkeys(unresolved)), condition_flags=sorted(dependencies),
                    missing_document_types=missing_documents)
        if state == "blocked" and not blocked:
            node["blocked_by"] = [edge["source_node_id"] for edge in incoming[key]
                                  if edge["relation"] in FLOW and edge["activation"] != "false"
                                  and not nodes[edge["source_node_id"]]["effective_completed"]]
    ordered = [nodes[row["node_id"]] for row in graph["nodes"]]
    ready = [row for row in ordered if row["execution_state"] == "ready"]
    focus = ready[0]["node_id"] if ready else None
    documents = []
    for definition in graph["document_catalog"]:
        review_state = _document_review_state(definition)
        linked = [node for node in ordered if definition["document_type"] in node["document_types"]]
        applicability = "false"
        for node in linked:
            applicability = _or(applicability, node["activation"])
        applicability = _and(applicability, _verdict(definition["condition"], flags))
        if applicability == "false":
            route = "not_needed"
        elif applicability == "unresolved":
            route = "held_behind_question"
        elif review_state == "sufficient":
            route = "established"
        elif review_state == "review_needed":
            route = "held_not_reviewed"
        elif definition["requirement_class"] == "optional":
            route = "optional"
        elif any(node["execution_state"] in {"ready", "completed"} for node in linked if node["activation"] == "true"):
            route = "needed_now"
        else:
            route = "needed_later"
        documents.append({**deepcopy(definition), "required_at_node_ids": [node["node_id"] for node in linked],
                          "active_node_ids": [node["node_id"] for node in linked if node["activation"] == "true"],
                          "condition_flags": sorted(_expression(definition["condition"], flags) |
                                                    set().union(*(set(node["condition_flags"]) for node in linked))),
                          "review_state": review_state, "review_scope": "document_requirement",
                          "activation": applicability, "route_state": route,
                          "request": route in {"needed_now", "needed_later"},
                          "reason": definition["reason"] if applicability == "true" else
                          "The process condition is unresolved." if applicability == "unresolved" else
                          "No applicable process step requires this document."})
    unresolved_flags = set()
    for row in ordered + edges + documents:
        if row.get("activation") == "unresolved":
            unresolved_flags |= {flag for flag in row["condition_flags"]
                                 if flags[flag]["verdict"] == "unresolved"}
    context = deepcopy(graph["assessment_context"])
    questions = [card for card in context.get("question_cards", [])
                 if card.get("id") not in flags and any(doc["document_type"] in card.get("document_types", [])
                                                       and doc["activation"] != "false" for doc in documents)]
    for flag in sorted(unresolved_flags):
        linked_docs = [doc["document_type"] for doc in documents if doc["activation"] == "unresolved"
                       and flag in doc["condition_flags"]]
        questions.append({"id": flag, "question": f"Does {flag.replace('_', ' ')} apply?",
                          "if_yes": "The dependent process route can apply.",
                          "if_no": "The dependent route is reconsidered.", "document_types": linked_docs,
                          "source_quote": flags[flag].get("candidate_quote")})
    def pending_dependencies(start: str, *, readiness: bool = False) -> dict[str, Any]:
        affected, pending = {start}, [start]
        while pending:
            source = pending.pop()
            for edge in edges:
                target = edge["target_node_id"]
                if edge["source_node_id"] == source and edge["activation"] != "false" and target not in affected:
                    affected.add(target)
                    pending.append(target)
        linked_docs = [doc["document_type"] for doc in documents if
                       (doc["activation"] == "unresolved" or readiness and doc["activation"] == "true")
                       and set(doc["required_at_node_ids"]) & affected
                       and not set(doc["active_node_ids"]) - affected]
        return {"affected_node_ids": [node["node_id"] for node in ordered if node["node_id"] in affected],
                "document_types": linked_docs}

    for node in ordered:
        if node["activation"] == "unresolved" and _unresolved_literal(node["condition"], flags):
            questions.append({"id": f"process:{node['node_id']}", "node_id": node["node_id"],
                              "question": f"What establishes whether '{node['label']}' applies?",
                              "if_yes": "Confirm the condition and review its dependent steps.",
                              "if_no": "The affected route remains unresolved.",
                              **pending_dependencies(node["node_id"]), "source_quote": None})
    for edge in edges:
        if (edge["activation"] != "false" and nodes[edge["target_node_id"]]["activation"] != "false"
                and _unresolved_literal(edge["condition"], flags)):
            source, target = nodes[edge["source_node_id"]], nodes[edge["target_node_id"]]
            questions.append({"id": f"edge:{edge['edge_id']}", "edge_id": edge["edge_id"],
                              "question": f"When should '{source['label']}' {edge['relation'].replace('_', ' ')} '{target['label']}'?",
                              "if_yes": "Confirm the relationship condition and review its consequences.",
                              "if_no": "The affected relationship remains unresolved.",
                              **pending_dependencies(target["node_id"], readiness=edge["relation"] == "requires"), "source_quote": None})
    for document in documents:
        if document["activation"] == "unresolved" and _unresolved_literal(document["condition"], flags):
            questions.append({"id": f"document:{document['document_type']}",
                              "question": f"What establishes whether '{document['label']}' is required?",
                              "if_yes": "Confirm the document condition before requesting it.",
                              "if_no": "This document requirement remains unresolved.",
                              "document_types": [document["document_type"]], "source_quote": None})
    inconsistent_ids = [row["node_id"] for row in ordered if row["inconsistent_completion"]]
    active_nodes = [node for node in ordered if node["activation"] == "true"]
    if inconsistent_ids:
        process_status = "needs_review"
    elif questions or any(node["activation"] == "unresolved" for node in ordered):
        process_status = "unresolved"
    elif active_nodes and all(node["effective_completed"] for node in active_nodes):
        process_status = "complete"
    elif ready:
        process_status = "in_progress"
    elif any(node["execution_state"] == "blocked" for node in ordered):
        process_status = "blocked"
    else:
        process_status = "needs_review"
    if inconsistent_ids:
        next_step = f"Review the completed step: {nodes[inconsistent_ids[0]]['label']}."
    elif ready:
        next_step = ready[0]["label"]
    elif questions:
        next_step = questions[0]["question"]
    elif any(node["execution_state"] == "blocked" for node in ordered):
        next_step = "Resolve the outstanding process prerequisites."
    elif process_status == "complete":
        next_step = "Process complete. Review the claim outcome separately."
    else:
        next_step = "Review the process outcome." if any(node["effective_completed"] for node in ordered) else "Review the process route."
    steps = [{"node_id": row["node_id"], "label": row["label"], "activation": row["activation"],
              "state": "done" if row["execution_state"] == "completed" else "active" if row["node_id"] == focus
              else "held_behind_question" if row["activation"] == "unresolved" else "not_reached",
              "execution_state": row["execution_state"], "authority": row["authority"],
              "condition_chips": [{"label": edge["label"], "verdict": edge["condition_verdict"],
                                   "condition_flag": edge["condition"].get("flag"), "quote": None, "candidate_quote": None}
                                  for edge in incoming[row["node_id"]]]} for row in ordered]
    assessment = {**context, "conditions": flags, "documents": documents, "steps": steps,
                  "question_cards": questions, "next_step": next_step, "process_status": process_status,
                  "process_graph_sha256": graph["graph_sha256"]}
    return {**graph, **assessment, "contract": CONTRACT, "nodes": ordered, "edges": edges,
            "assessment_sha256": digest_value(assessment), "focus_node_id": focus,
            "inconsistent_completed_node_ids": inconsistent_ids}


def _undo_entry(graph: Mapping[str, Any]) -> dict[str, Any] | None:
    compensated = set()
    for entry in reversed(graph["history"]):
        operation = entry.get("operation", {})
        kind = operation.get("type", entry.get("type"))
        if kind == "process.undo":
            compensated.add(operation["target_revision"])
        elif kind == "document.review":
            continue
        elif kind == "fragment.apply":
            # Legacy imports have no before snapshot; never cross that boundary.
            return None
        elif entry.get("revision") not in compensated:
            return entry if "before" in entry and "after" in entry else None
    return None


def undo_target(graph: Mapping[str, Any]) -> dict[str, Any] | None:
    """Expose the exact graph edit eligible for a compensating preview."""
    entry = _undo_entry(graph)
    if entry is None:
        return None
    operation = entry["operation"]
    item = entry["after"] or entry["before"] or {}
    return {"target_revision": entry["revision"], "operation_type": operation["type"],
            "label": item.get("label") or operation.get("flag") or "Process change"}


def _undo_edit(graph, operation):
    target = _undo_entry(graph)
    if (type(operation["target_revision"]) is not int or target is None
            or operation["target_revision"] != target["revision"]):
        raise ValueError("only the last process edit can be undone")
    result = deepcopy(graph)
    prior, saved = target["before"], target["after"]
    original = target["operation"]
    kind = original["type"]
    actor = operation.get("actor", "Handler")
    def semantic(item):
        return {key: value for key, value in (item or {}).items()
                if key not in {"validation", "provenance", "held_files"}}
    def restore(field, key, identity, before, after):
        rows = result[field]
        current = next((row for row in rows if row[key] == identity), None)
        if field == "document_catalog" and after is not None:
            after = seal_graph({**graph, "nodes": [], "edges": [],
                                "document_catalog": [after]})["document_catalog"][0]
        if semantic(current) != semantic(after):
            raise ValueError("the edited fields changed; reload before undoing")
        if before is None:
            if current and current.get("held_files"):
                raise ValueError("undo would remove later source reviews; keep the document")
            rows[:] = [row for row in rows if row[key] != identity]
        else:
            value = deepcopy(before)
            if current and "held_files" in current:
                value["held_files"] = deepcopy(current["held_files"])
            if current is None:
                rows.append(value)
            else:
                rows[rows.index(current)] = value
    if kind.startswith(("node.", "edge.")):
        entity = kind.split(".")[0]
        key = entity + "_id"
        identity = (saved or prior)[key]
        restore(entity + "s", key, identity, prior, saved)
        relationships = target.get("relationship_changes", {})
        for edge in relationships.get("added", []):
            restore("edges", "edge_id", edge["edge_id"], None, edge)
        for edge in relationships.get("removed", []):
            restore("edges", "edge_id", edge["edge_id"], edge, None)
    elif kind == "conditions.set":
        flag = original["flag"]
        if result["conditions"].get(flag) != saved:
            raise ValueError("the edited condition changed; reload before undoing")
        result["conditions"][flag] = deepcopy(prior)
    elif kind == "document.set":
        restore("document_catalog", "document_type", (saved or prior)["document_type"], prior, saved)
    else:
        raise ValueError("this process edit has no scoped undo")
    # Re-evaluate the restored scope without reusing an earlier validation.
    change = impact(graph, result)
    affected_nodes = set(change["affected_node_ids"])
    affected_edges = set(change["changed_edge_ids"])
    if kind.startswith("node."):
        affected_nodes.add((saved or prior)["node_id"])
    if kind.startswith("edge."):
        affected_edges.add((saved or prior)["edge_id"])
    if kind == "document.set":
        affected_nodes.update(node["node_id"] for node in result["nodes"]
                              if (saved or prior)["document_type"] in node["document_types"])
    for rows, key, affected in ((result["nodes"], "node_id", affected_nodes),
                                (result["edges"], "edge_id", affected_edges)):
        for item in rows:
            if item[key] in affected:
                item["validation"] = {"status": "revised", "previous_status": item["validation"]["status"], "actor": actor}
                item["provenance"] = {**item["provenance"], "modified_by": actor}
    result["revision"] += 1
    result["history"].append({"revision": result["revision"], "operation": deepcopy(operation),
                               "compensates_revision": target["revision"],
                               "previous_graph_sha256": graph["graph_sha256"]})
    return seal_graph(result)


def apply_edit(graph: Mapping[str, Any], operation: Mapping[str, Any]) -> dict[str, Any]:
    """Apply one atomic edit; the caller journals the returned immutable value."""
    graph = seal_graph(graph)
    if not isinstance(operation, dict) or not isinstance(operation.get("type"), str):
        raise ValueError("invalid process edit")
    operation = deepcopy(operation)
    kind = operation["type"]
    metadata = {"type", "actor", "reason", "at"}
    schemas = {
        "node.add": {"node"}, "node.update": {"node_id", "changes"}, "node.remove": {"node_id"},
        "node.validate": {"node_id", "status"}, "node.complete": {"node_id", "completed"},
        "edge.add": {"edge"}, "edge.update": {"edge_id", "changes"}, "edge.remove": {"edge_id"},
        "edge.validate": {"edge_id", "status"}, "conditions.set": {"flag", "verdict"},
        "document.set": {"document"}, "process.undo": {"target_revision"},
    }
    supplied = set(operation) - metadata
    optional = {"after_node_id"} if kind == "node.add" else set()
    if kind not in schemas or not schemas[kind].issubset(supplied) or supplied - schemas[kind] - optional:
        raise ValueError("unsupported or malformed process edit")
    for key in ("actor", "reason", "at"):
        if key in operation:
            _text(operation[key], key)
    if kind == "process.undo":
        return _undo_edit(graph, operation)
    actor = operation.get("actor", "Handler")
    result, before, after = deepcopy(graph), None, None
    relationship_changes = {"added": [], "removed": []}
    if kind.startswith(("node.", "edge.")):
        entity, action = kind.split(".")
        key, rows = f"{entity}_id", result[f"{entity}s"]
        fields = NODE_FIELDS if entity == "node" else EDGE_FIELDS
        if action == "add":
            item = operation[entity]
            if not isinstance(item, dict) or set(item) - (fields - {"validation", "provenance", "completed", "authority"}):
                raise ValueError("unsupported new process fields")
            item = _entity_defaults(item, edge=entity == "edge")
            item["provenance"] = {"kind": "manual", "source": actor}
            rows.append(item)
            after = deepcopy(item)
            if "after_node_id" in operation:
                source = operation["after_node_id"]
                if not isinstance(source, str) or not any(row["node_id"] == source for row in graph["nodes"]):
                    raise ValueError("unknown predecessor node")
                edge = _entity_defaults({"edge_id": f"after_{digest_value([source, item.get('node_id')])[:20]}",
                                         "source_node_id": source, "target_node_id": item.get("node_id"),
                                         "relation": "enables", "provenance": {"kind": "manual", "source": actor}}, edge=True)
                result["edges"].append(edge)
                relationship_changes["added"].append(deepcopy(edge))
        else:
            item = next((row for row in rows if row[key] == operation[key]), None)
            if item is None:
                raise ValueError(f"unknown {entity}")
            before = deepcopy(item)
            if action == "remove":
                rows.remove(item)
                if entity == "node":
                    relationship_changes["removed"] = [deepcopy(edge) for edge in result["edges"]
                                                       if operation[key] in (edge["source_node_id"], edge["target_node_id"])]
                    result["edges"] = [edge for edge in result["edges"]
                                       if operation[key] not in (edge["source_node_id"], edge["target_node_id"])]
            elif action == "update":
                changes = operation["changes"]
                editable = fields - {key, "completed", "validation", "provenance", "authority"}
                if not isinstance(changes, dict) or not changes or set(changes) - editable:
                    raise ValueError("unsupported process changes")
                item.update(deepcopy(changes))
                if entity == "node" and any(item[key] != before[key] for key in ("meaning", "kind")):
                    item["completed"] = False
                if item != before:
                    item["validation"] = {"status": "revised", "previous_status": before["validation"]["status"], "actor": actor}
                    item["provenance"] = {**item["provenance"], "modified_by": actor}
            elif action == "validate":
                if not isinstance(operation["status"], str) or operation["status"] not in {"validated", "rejected", "unvalidated"}:
                    raise ValueError("unsupported validation status")
                item["validation"] = {"status": operation["status"], "actor": actor}
            elif action == "complete":
                if type(operation["completed"]) is not bool:
                    raise ValueError("completion must be a boolean")
                item["completed"] = operation["completed"]
            if action != "remove":
                after = deepcopy(item)
    elif kind == "conditions.set":
        flag, verdict = operation["flag"], operation["verdict"]
        if (not isinstance(flag, str) or flag not in result["conditions"]
                or not isinstance(verdict, str) or verdict not in VERDICTS):
            raise ValueError("unsupported condition or verdict")
        before = deepcopy(result["conditions"][flag])
        after = {"verdict": verdict, "worker": "handler_correction", "actor": actor,
                 "quote": None, "candidate_quote": None, "source_id": None}
        result["conditions"][flag] = after
    else:
        document = operation["document"]
        if not isinstance(document, dict) or set(document) - (DOCUMENT_FIELDS - {"held_files", "authority", "condition_flag"}):
            raise ValueError("unsupported document fields")
        _text(document.get("document_type"), "document_type", 120)
        item = next((row for row in result["document_catalog"] if row["document_type"] == document["document_type"]), None)
        before = deepcopy(item)
        if item is None:
            result["document_catalog"].append(deepcopy(document))
            after = deepcopy(document)
        else:
            item.update(deepcopy(document))
            after = deepcopy(item)
        for node in result["nodes"]:
            if document["document_type"] in node["document_types"] and before != after:
                node["validation"] = {"status": "revised", "previous_status": node["validation"]["status"], "actor": actor}
    result["revision"] += 1
    result["history"].append({"revision": result["revision"], "operation": operation,
                               "before": before, "after": after, "relationship_changes": relationship_changes,
                               "previous_graph_sha256": graph["graph_sha256"]})
    return seal_graph(result)


def impact(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    """Explain both changed outputs and outputs whose requirement stayed stable."""
    before, after = evaluate(before), evaluate(after)
    output: dict[str, Any] = {"before_graph_sha256": before["graph_sha256"], "after_graph_sha256": after["graph_sha256"]}
    for entity, key in (("node", "node_id"), ("edge", "edge_id")):
        old = {row[key]: row for row in before[f"{entity}s"]}
        new = {row[key]: row for row in after[f"{entity}s"]}
        ids = list(dict.fromkeys([*old, *new]))
        changed = [name for name in ids if old.get(name) != new.get(name)]
        output[f"changed_{entity}_ids"] = changed
        output[f"unchanged_{entity}_ids"] = [name for name in ids if name not in changed]
        output[f"removed_{entity}_ids"] = [name for name in old if name not in new]
        output[f"added_{entity}_ids"] = [name for name in new if name not in old]
        output[f"{entity}_changes"] = [{key: name, "label": (new.get(name) or old[name])["label"],
                                       "before": old.get(name), "after": new.get(name)} for name in changed]
    old_docs = {row["document_type"]: row for row in before["documents"]}
    new_docs = {row["document_type"]: row for row in after["documents"]}
    doc_ids = list(dict.fromkeys([*old_docs, *new_docs]))
    requirement = lambda doc: (doc.get("activation"), doc.get("route_state"), doc.get("request")) if doc else None
    requirement_changes = [name for name in doc_ids if requirement(old_docs.get(name)) != requirement(new_docs.get(name))]
    output["changed_requirement_document_types"] = requirement_changes
    output["unchanged_requirement_document_types"] = [name for name in doc_ids if name not in requirement_changes]
    definitions_before = {row["document_type"]: row for row in before["document_catalog"]}
    definitions_after = {row["document_type"]: row for row in after["document_catalog"]}
    definition_changes = []
    for name in doc_ids:
        old, new = definitions_before.get(name, {}), definitions_after.get(name, {})
        fields = sorted(key for key in (DOCUMENT_FIELDS - {"held_files"}) if old.get(key) != new.get(key))
        if fields:
            definition_changes.append({"document_type": name, "fields": fields, "before": old or None, "after": new or None})
    output["document_definition_changes"] = definition_changes
    changed_docs = [name for name in doc_ids if old_docs.get(name) != new_docs.get(name)]
    output["changed_document_types"] = changed_docs
    output["unchanged_document_types"] = [name for name in doc_ids if name not in changed_docs]
    required = lambda row: row is not None and row["activation"] == "true"
    output["added_document_types"] = [name for name in doc_ids if required(new_docs.get(name)) and not required(old_docs.get(name))]
    output["removed_document_types"] = [name for name in doc_ids if required(old_docs.get(name)) and not required(new_docs.get(name))]
    output["document_changes"] = [{"document_type": name, "label": (new_docs.get(name) or old_docs[name])["label"],
                                   "before": old_docs.get(name), "after": new_docs.get(name)} for name in changed_docs]
    source_changes = []
    for name in doc_ids:
        old, new = old_docs.get(name, {}), new_docs.get(name, {})
        fields = [key for key in ("required_at_node_ids", "held_files") if old.get(key) != new.get(key)]
        if fields:
            source_changes.append({"document_type": name, "fields": fields,
                                   "before": {key: old.get(key) for key in fields},
                                   "after": {key: new.get(key) for key in fields}})
    output["document_source_changes"] = [change["document_type"] for change in source_changes]
    output["document_source_change_details"] = source_changes
    output["next_action_changed"] = before["next_step"] != after["next_step"]
    output["next_action"] = {"before": before["next_step"], "after": after["next_step"]}
    old_questions = {row["id"] for row in before["question_cards"]}
    new_questions = {row["id"] for row in after["question_cards"]}
    output["reopened_question_ids"] = sorted(new_questions - old_questions)
    output["resolved_question_ids"] = sorted(old_questions - new_questions)
    output["inconsistent_completed_node_ids"] = after["inconsistent_completed_node_ids"]
    affected = set(output["changed_node_ids"])
    all_edges = before["edges"] + after["edges"]
    affected.update(edge["target_node_id"] for edge in all_edges if edge["edge_id"] in output["changed_edge_ids"])
    directly_changed = set(affected)
    pending = list(affected)
    while pending:
        source = pending.pop()
        for edge in all_edges:
            if edge["source_node_id"] == source and edge["target_node_id"] not in affected:
                affected.add(edge["target_node_id"])
                pending.append(edge["target_node_id"])
    node_order = list(dict.fromkeys(row["node_id"] for row in before["nodes"] + after["nodes"]))
    output["affected_node_ids"] = [key for key in node_order if key in affected]
    output["affected_downstream_node_ids"] = [key for key in node_order if key in affected - directly_changed]
    output["unchanged_affected_node_ids"] = [key for key in output["unchanged_node_ids"] if key in affected]
    output["summary"] = {"changed_steps": len(output["changed_node_ids"]), "changed_relationships": len(output["changed_edge_ids"]),
                         "added_documents": len(output["added_document_types"]), "removed_documents": len(output["removed_document_types"]),
                         "changed_document_definitions": len(definition_changes),
                         "unchanged_requirements": len(output["unchanged_requirement_document_types"]),
                         "unchanged_documents": len(output["unchanged_document_types"])}
    return output
