"""Journal-bound editing of the working process, separate from source truth.

The immutable intake and old evidence loop remain replayable. Only explicit
process-edit events alter this working definition; every consumer derives its
current assessment from the same deterministic graph evaluation.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .causal_process_v1 import build_graph, evaluate, apply_edit, impact, validate_graph, seal_graph
from .workspace_corpus import digest_value

PROCESS_EDIT = "WORKSPACE_CAUSAL_PROCESS_EDITED_V1"
FRAGMENT_SAVED = "WORKSPACE_PROCESS_FRAGMENT_SAVED_V1"


def working_graph(corpus, state: Mapping[str, Any]) -> dict[str, Any]:
    graph = state.get("causal_process")
    if graph is not None:
        validate_graph(graph)
        if seal_graph(graph) != graph:
            raise ValueError("working process identity is invalid")
        return deepcopy(graph)
    intake = state.get("intake_assessment") or {}
    assessment = intake.get("claim_assessment")
    if not isinstance(assessment, dict):
        raise ValueError("review the claim before editing its process")
    return build_graph(corpus, state["claim_id"], {"claim_type": intake["claim_type"], **assessment})


def effective_assessment(state: Mapping[str, Any]) -> dict[str, Any] | None:
    if state.get("causal_process") is not None:
        return evaluate(state["causal_process"])
    return deepcopy((state.get("intake_assessment") or {}).get("claim_assessment"))


def _actor_reason(actor: str, reason: str) -> None:
    if not isinstance(actor, str) or not actor.strip() or len(actor) > 80:
        raise ValueError("a reviewing handler is required")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise ValueError("explain why this process should change")


def _fragment_apply(graph, fragment, actor, reason):
    if fragment.get("family") != graph["family"]:
        raise ValueError("process fragment belongs to a different claim family")
    if fragment.get("fragment_sha256") != digest_value({k: v for k, v in fragment.items() if k != "fragment_sha256"}):
        raise ValueError("process fragment identity is invalid")
    after = deepcopy(graph)
    selected = {node["node_id"] for node in fragment["nodes"]}
    existing_nodes = {node["node_id"] for node in graph["nodes"]}
    new_nodes = selected - existing_nodes
    imported_boundaries = []
    for edge in fragment.get("boundary_edges", []):
        fields = ("edge_id", "source_node_id", "target_node_id", "relation", "condition")
        present = next((row for row in graph["edges"] if row["edge_id"] == edge["edge_id"]), None)
        endpoints = {edge["source_node_id"], edge["target_node_id"]}
        if (present is None and len(endpoints & selected) == 1
                and len(endpoints & new_nodes) == 1 and endpoints - selected <= existing_nodes):
            value = deepcopy(edge)
            value["validation"] = {"status": "unvalidated", "actor": actor}
            value["provenance"] = {"kind": "reused", "source": fragment["fragment_sha256"], "actor": actor}
            imported_boundaries.append(value)
        elif present is None or any(present.get(key) != edge.get(key) for key in fields):
            raise ValueError("fragment boundary conflicts with this claim; review its dependencies first")
    # Existing boundary relationships are compatibility constraints. A new
    # imported node may bring its explicit link to an existing external node;
    # that new relationship must be reviewed in this claim.
    replacement_nodes = {}
    for node in fragment["nodes"]:
        value = deepcopy(node)
        value["completed"] = False
        value["provenance"] = {"kind": "reused", "source": fragment["fragment_sha256"], "actor": actor}
        replacement_nodes[value["node_id"]] = value
    after["nodes"] = [replacement_nodes.pop(node["node_id"], node) for node in after["nodes"]] + list(replacement_nodes.values())
    after["edges"] = [edge for edge in after["edges"] if not (
        edge["source_node_id"] in selected and edge["target_node_id"] in selected)]
    existing_ids = {edge["edge_id"] for edge in after["edges"]}
    for edge in fragment["edges"]:
        if edge["edge_id"] in existing_ids:
            raise ValueError("fragment relationship identity conflicts with this claim")
        value = deepcopy(edge)
        value["provenance"] = {"kind": "reused", "source": fragment["fragment_sha256"], "actor": actor}
        after["edges"].append(value)
    after["edges"].extend(imported_boundaries)
    catalog = {doc["document_type"]: doc for doc in after["document_catalog"]}
    for doc in fragment["document_catalog"]:
        value = deepcopy(doc)
        prior = catalog.get(value["document_type"], {})
        outside = [node for node in graph["nodes"] if node["node_id"] not in selected
                   and value["document_type"] in node["document_types"]]
        if outside and {k: v for k, v in value.items() if k != "held_files"} != {k: v for k, v in prior.items() if k != "held_files"}:
            raise ValueError("fragment changes a document shared outside the selected process; include and review those nodes first")
        # Reusable process knowledge never transports another claim's files.
        value["held_files"] = deepcopy(prior.get("held_files", []))
        catalog[value["document_type"]] = value
    after["document_catalog"] = list(catalog.values())
    for flag in fragment["condition_flags"]:
        after["conditions"].setdefault(flag, {"verdict": "unresolved", "quote": None, "source_id": None, "worker": "reused_process"})
    after["revision"] += 1
    after.setdefault("fragment_instances", []).append({key: fragment[key] for key in ("fragment_id", "version", "fragment_sha256", "source_claim_id")})
    after.setdefault("history", []).append({"type": "fragment.apply", "fragment_sha256": fragment["fragment_sha256"], "actor": actor, "reason": reason})
    return seal_graph(after)


def _document_receipt(corpus, state, operation, actor):
    import re
    from hashlib import sha256
    if set(operation) != {"type", "document_type", "artifact_id", "quote", "note", "review"}:
        raise ValueError("document review fields are invalid")
    if operation["review"] not in {"received", "sufficient", "insufficient"}:
        raise ValueError("document review must be received, sufficient or insufficient")
    note, quote = operation["note"], operation["quote"]
    if not isinstance(note, str) or not note.strip() or len(note) > 1000:
        raise ValueError("explain what the source establishes or leaves unresolved")
    if not isinstance(quote, str) or len(quote) > 4000:
        raise ValueError("document source quote is invalid")
    raw, source = corpus.artifact(state["claim_id"], operation["artifact_id"])
    if sha256(raw).hexdigest() != source["sha256"]:
        raise ValueError("document source bytes differ from their claim binding")
    if len(raw) > 16 * 1024 * 1024:
        raise ValueError("document source exceeds the supported local size")
    text = ""
    if source["media_type"].split(";")[0] == "application/pdf":
        import fitz
        with fitz.open(stream=raw, filetype="pdf") as pdf:
            if pdf.is_encrypted or len(pdf) > 100:
                raise ValueError("document cannot be reviewed by the bounded source reader")
            text = "\n".join(page.get_text("text") for page in pdf)
    elif source.get("role") == "customer_message":
        text = corpus.claim(state["claim_id"])["customer_message"]["body"]
    elif source["media_type"].startswith("text/"):
        text = raw.decode("utf-8", errors="strict")
    if quote and quote not in text:
        raise ValueError("the review quote is absent from this exact source")
    if operation["review"] == "sufficient" and (not quote.strip() or re.search(
        r"\b(?:unresolved|unknown|unclear|ungeklärt|unbekannt|cannot|can't)\b", quote, re.I
    )):
        raise ValueError("sufficient review requires an exact affirmative source passage")
    return {"artifact_id": operation["artifact_id"], "file_name": source["file_name"],
        "sha256": source["sha256"], "media_type": source["media_type"],
        "source_quote": quote, "review": operation["review"], "reviewed_by": actor, "note": note.strip()}


def preview_material(corpus, state, operation, actor, reason, fragment=None):
    _actor_reason(actor, reason)
    if not isinstance(operation, dict):
        raise ValueError("process operation must be an object")
    before = working_graph(corpus, state)
    if operation.get("type") == "document.review":
        if fragment is not None:
            raise ValueError("unexpected fragment in document review")
        from .causal_process_v1 import refresh_document
        receipt = _document_receipt(corpus, state, operation, actor)
        after = refresh_document(before, operation["document_type"], receipt, actor, reason)
    elif operation.get("type") == "fragment.apply":
        if set(operation) != {"type", "fragment_sha256"} or fragment is None or operation["fragment_sha256"] != fragment.get("fragment_sha256"):
            raise ValueError("select an available process fragment version")
        after = _fragment_apply(before, fragment, actor, reason)
    else:
        if fragment is not None:
            raise ValueError("unexpected process fragment")
        if "actor" in operation or "reason" in operation:
            raise ValueError("actor and reason belong to the review request")
        after = apply_edit(before, {**operation, "actor": actor, "reason": reason})
    evaluation = evaluate(after)
    material = {
        "contract": "casepath.causal-process-preview/1.0.0", "claim_id": state["claim_id"],
        "workspace_revision": state["revision"], "workspace_state_sha256": state["state_sha256"],
        "operation": deepcopy(operation), "actor": actor, "reason": reason,
        "graph": after, "evaluation": evaluation, "effective_assessment": evaluation,
        "impact": impact(before, after),
    }
    return {**material, "preview_sha256": digest_value(material)}


def validate_process_event(corpus, state, command):
    required = {"operation", "actor", "reason", "preview_sha256", "fragment", "request_expected_revision", "expected_state_sha256"}
    if set(command) != required or command["expected_state_sha256"] != state["state_sha256"]:
        raise ValueError("process edit is not bound to its parent state")
    preview = preview_material(corpus, state, command["operation"], command["actor"], command["reason"], command["fragment"])
    if preview["preview_sha256"] != command["preview_sha256"]:
        raise ValueError("process impact preview differs from this edit")
    return preview


def fragment_snapshot(graph, *, name, node_ids, actor, reason, fragment_id, version, source_revision):
    _actor_reason(actor, reason)
    if not isinstance(name, str) or not name.strip() or len(name) > 100:
        raise ValueError("a process fragment name is required")
    if not isinstance(node_ids, list) or not node_ids or len(node_ids) != len(set(node_ids)):
        raise ValueError("select distinct process nodes to reuse")
    selected = set(node_ids)
    nodes = [deepcopy(node) for node in graph["nodes"] if node["node_id"] in selected]
    if len(nodes) != len(selected) or any(node["validation"]["status"] != "validated" for node in nodes):
        raise ValueError("validate every selected process node before saving a fragment")
    edges = [deepcopy(edge) for edge in graph["edges"] if edge["source_node_id"] in selected and edge["target_node_id"] in selected]
    if any(edge["validation"]["status"] != "validated" for edge in edges):
        raise ValueError("validate the selected process relationships before reuse")
    # Capture cross-fragment links as compatibility constraints. Reuse never
    # silently drops an incoming prerequisite or replaces an external branch.
    boundary_edges = [deepcopy(edge) for edge in graph["edges"] if
        (edge["source_node_id"] in selected) != (edge["target_node_id"] in selected)]
    docs = {item for node in nodes for item in node["document_types"]}
    catalog = [deepcopy(doc) for doc in graph["document_catalog"] if doc["document_type"] in docs]
    for doc in catalog:
        doc["held_files"] = []
    for node in nodes:
        node["completed"] = False
    material = {
        "contract": "casepath.process-fragment/1.0.0", "fragment_id": fragment_id,
        "version": version, "name": name.strip(), "family": graph["family"],
        "source_claim_id": graph["claim_id"], "source_revision": source_revision,
        "source_graph_sha256": graph["graph_sha256"], "nodes": nodes, "edges": edges,
        "document_catalog": catalog, "boundary_edges": boundary_edges, "condition_flags": sorted(graph["conditions"]),
        "actor": actor, "reason": reason,
    }
    return {**material, "fragment_sha256": digest_value(material)}


def validate_fragment_event(corpus, state, command):
    if set(command) != {"fragment", "node_ids", "request_expected_revision", "expected_state_sha256"} or command["expected_state_sha256"] != state["state_sha256"]:
        raise ValueError("process fragment is not bound to its parent state")
    fragment = command["fragment"]
    expected = fragment_snapshot(working_graph(corpus, state), name=fragment["name"], node_ids=command["node_ids"], actor=fragment["actor"], reason=fragment["reason"], fragment_id=fragment["fragment_id"], version=fragment["version"], source_revision=state["revision"])
    if fragment != expected:
        raise ValueError("process fragment differs from its validated source")


class CausalWorkspaceService:
    def __init__(self, workspace):
        self.workspace = workspace
        self.store = workspace.store
        self.corpus = workspace.corpus

    def _parent(self, claim_id, expected_revision, expected_state_sha256):
        state = self.store.state_at_revision(claim_id, expected_revision)
        if state["state_sha256"] != expected_state_sha256:
            raise ValueError("process workspace state differs")
        return state

    def _events(self, claim_id, revision):
        from .claim_workspace_v1 import WORKSPACE_LOOP_PREFIX
        import json
        with self.store.journal.connect() as connection:
            rows = self.store._rows(connection, loop_id=WORKSPACE_LOOP_PREFIX + claim_id)
        self.store._replay_rows(rows[:revision])
        return [json.loads(row["event_json"]) for row in rows[:revision]]

    def fragments(self, family):
        from .claim_workspace_v1 import WORKSPACE_SESSION_ID, WORKSPACE_LOOP_PREFIX
        import json
        with self.store.journal.connect() as connection:
            rows = connection.execute("SELECT loop_id,sequence,event_json FROM claim_loop_events WHERE session_id=? AND event_json LIKE ? ORDER BY created_at,loop_id,sequence", (WORKSPACE_SESSION_ID, "%" + FRAGMENT_SAVED + "%")).fetchall()
        values = []
        for row in rows:
            event = json.loads(row["event_json"])
            if event["event_type"] != FRAGMENT_SAVED:
                continue
            self.store.state_at_revision(row["loop_id"][len(WORKSPACE_LOOP_PREFIX):], row["sequence"])
            fragment = event["command"]["fragment"]
            if fragment["family"] == family:
                values.append({**fragment, "saved_at": event["created_at"], "event_sha256": event["event_sha256"]})
        latest = {}
        for value in values:
            latest[value["fragment_id"]] = max(latest.get(value["fragment_id"], 0), value["version"])
        return [{**value, "latest": value["version"] == latest[value["fragment_id"]]} for value in values]

    def _fragment(self, state, operation):
        if operation.get("type") != "fragment.apply":
            return None
        graph = working_graph(self.corpus, state)
        found = next((value for value in self.fragments(graph["family"]) if value["fragment_sha256"] == operation.get("fragment_sha256")), None)
        if found is None:
            raise ValueError("process fragment version was not found")
        return {k: v for k, v in found.items() if k not in {"saved_at", "event_sha256", "latest"}}

    def view(self, claim_id, *, state=None, include_fragments=True):
        state = state or self.store.recover(claim_id)
        graph = working_graph(self.corpus, state)
        evaluation = evaluate(graph)
        adopted = state.get("causal_process") is not None
        history = []
        for event in self._events(claim_id, state["revision"]):
            if event["event_type"] == PROCESS_EDIT:
                parent = self.store.state_at_revision(claim_id, event["sequence"] - 1)
                preview = validate_process_event(self.corpus, parent, event["command"])
                history.append({"revision": event["sequence"], "event_sha256": event["event_sha256"], "created_at": event["created_at"], "actor": event["command"]["actor"], "reason": event["command"]["reason"], "operation": event["command"]["operation"], "impact": preview["impact"], "graph_sha256": preview["graph"]["graph_sha256"]})
        material = {"contract": "casepath.causal-process-view/1.0.0", "claim_id": claim_id,
            "workspace_revision": state["revision"], "workspace_state_sha256": state["state_sha256"],
            "graph": graph, "evaluation": evaluation, "effective_assessment": effective_assessment(state),
            "process_adopted": adopted, "evaluation_mode": "working" if adopted else "proposal",
            "history": history, "fragments": self.fragments(graph["family"]) if include_fragments else [],
            "authority": "claim_loop_events", "process_status": evaluation["process_status"], "claim_decision_authorized": False}
        return {**material, "view_sha256": digest_value(material)}

    def preview(self, claim_id, *, operation, actor, reason, expected_revision, expected_state_sha256):
        state = self._parent(claim_id, expected_revision, expected_state_sha256)
        if self.store.recover(claim_id)["state_sha256"] != state["state_sha256"]:
            raise ValueError("process revision is stale; reload before previewing")
        return preview_material(self.corpus, state, operation, actor, reason, self._fragment(state, operation))

    def apply(self, claim_id, *, operation, actor, reason, expected_revision, expected_state_sha256, preview_sha256, idempotency_key):
        from .claim_workspace_v1 import utc_now
        state = self._parent(claim_id, expected_revision, expected_state_sha256)
        command = {"operation": operation, "actor": actor, "reason": reason,
            "preview_sha256": preview_sha256, "fragment": self._fragment(state, operation),
            "expected_state_sha256": expected_state_sha256, "request_expected_revision": expected_revision}
        preview = validate_process_event(self.corpus, state, command)
        state, event, replayed = self.store.append(claim_id=claim_id, event_type=PROCESS_EDIT, idempotency_key=idempotency_key, command=command, timestamp=utc_now(), expected_revision=expected_revision)
        material = {"contract": "casepath.causal-process-result/1.0.0", "claim_id": claim_id,
            "event_sha256": event["event_sha256"], "replayed": replayed, "impact": preview["impact"],
            "process": self.view(claim_id, state=state, include_fragments=False)}
        return {**material, "result_sha256": digest_value(material)}

    def save_fragment(self, claim_id, *, name, node_ids, actor, reason, expected_revision, expected_state_sha256, idempotency_key, fragment_id=None):
        from .claim_workspace_v1 import utc_now
        state = self._parent(claim_id, expected_revision, expected_state_sha256)
        graph = working_graph(self.corpus, state)
        existing = [value for value in self.fragments(graph["family"]) if value["fragment_id"] == fragment_id and value["source_revision"] < expected_revision]
        if fragment_id is not None and (not existing or any(value["source_claim_id"] != claim_id for value in existing)):
            raise ValueError("update a fragment owned by this source claim")
        fragment_id = fragment_id or "fragment." + digest_value({"claim_id": claim_id, "idempotency_key": idempotency_key})[:24]
        fragment = fragment_snapshot(graph, name=name, node_ids=node_ids, actor=actor, reason=reason,
            fragment_id=fragment_id, version=max((value["version"] for value in existing), default=0) + 1, source_revision=expected_revision)
        state, event, replayed = self.store.append(claim_id=claim_id, event_type=FRAGMENT_SAVED, idempotency_key=idempotency_key,
            command={"fragment": fragment, "node_ids": node_ids, "expected_state_sha256": expected_state_sha256, "request_expected_revision": expected_revision}, timestamp=utc_now(), expected_revision=expected_revision)
        material = {"contract": "casepath.causal-process-result/1.0.0", "claim_id": claim_id, "fragment": fragment,
            "event_sha256": event["event_sha256"], "replayed": replayed, "workspace_revision": state["revision"], "workspace_state_sha256": state["state_sha256"],
            "process": self.view(claim_id, state=state, include_fragments=False)}
        return {**material, "result_sha256": digest_value(material)}
