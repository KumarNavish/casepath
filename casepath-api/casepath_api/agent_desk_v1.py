"""Handler desk over the existing claim journal and verified review work.

The delegate journal shares claim_loop_events, under its own namespace. It
records mandate controls and handler approvals, never facts or claim outcomes.
Process decisions use the single causal engine and its existing journal events.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import datetime
import json
from threading import RLock
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from .agent_work.authority import AuthorityError
from .agent_work.projection import summarize
from .agent_work.store import ConflictError, WorkStoreError
from .causal_workspace_v1 import PROCESS_EDIT, CausalWorkspaceService, effective_assessment, fragment_snapshot, preview_material, working_graph
from .causal_process_v1 import evaluate
from .claim_workspace_v1 import ClaimWorkspaceError, WORKSPACE_SESSION_ID, utc_now
from .claim_loop_router import _idempotency_key
from .claim_loop_store import ClaimLoopStoreError
from .workspace_corpus import canonical_json_bytes, digest_value

CONTRACT = "casepath.agent-desk-claim/1.0.0"
EVENT_CONTRACT = "casepath.agent-delegate-event/1.0.0"
FAMILY_HOME = "clm_f69b1747447bc221"
GROUPS = [("needs_you", "Needs you"), ("working", "Agent working"),
          ("waiting", "Waiting on someone else"), ("quiet", "Quiet"), ("closed", "Closed")]
MANDATE = {"unattended": ["Read bound sources", "Extract source passages", "Derive process and document requirements", "Prepare requests"],
           "requires_handler": ["Validate process steps and relationships", "Change the working process", "Approve draft requests", "Any action leaving CasePath"]}
CONDITION_PROMPTS = {"family_home": "Is this a family home?", "arrears": "Are rent arrears involved?",
    "extension_relevant": "Should an extension be considered?", "retaliation_screen": "Does the timing raise a good-faith concern?",
    "health_effects": "Are health effects reported?", "specialist_needed": "Is a technical inspection needed?",
    "deposit_considered": "Should a rent deposit be considered?", "termination_received": "Has the termination notice been received?",
    "claim_received": "Has the claim been received?", "reference_rate": "Is the reference rate a reason for the change?",
    "renovation": "Is renovation a reason for the change?"}


def _sealed(value, field="projection_sha256"):
    return {**value, field: digest_value(value)}


def _fingerprint_row(signature, row):
    """Bind raw SQLite scalars without JSON-escaping nested persisted JSON."""
    from struct import pack
    for key in row.keys():
        name = key.encode("utf-8")
        signature.update(len(name).to_bytes(8, "big"))
        signature.update(name)
        value = row[key]
        if value is None:
            marker, encoded = b"n", b""
        elif isinstance(value, bytes):
            marker, encoded = b"b", value
        elif isinstance(value, str):
            marker, encoded = b"s", value.encode("utf-8")
        elif isinstance(value, int):
            marker, encoded = b"i", str(value).encode("ascii")
        elif isinstance(value, float):
            marker, encoded = b"f", pack("!d", value)
        else:
            raise ValueError("unsupported persisted desk scalar")
        signature.update(marker)
        signature.update(len(encoded).to_bytes(8, "big"))
        signature.update(encoded)


class DelegateJournal:
    def __init__(self, workspace):
        self.workspace = workspace
        self.journal = workspace.store.journal

    @staticmethod
    def initial(claim_id):
        return _sealed({"claim_id": claim_id, "revision": 0, "paused": False,
                        "decisions": [], "last_event_sha256": None}, "state_sha256")

    def rows(self, db, claim_id):
        return db.execute("SELECT * FROM claim_loop_events WHERE session_id=? AND loop_id=? ORDER BY sequence",
                          (WORKSPACE_SESSION_ID, "delegate." + claim_id)).fetchall()

    def replay(self, claim_id, rows):
        state = self.initial(claim_id)
        for sequence, row in enumerate(rows, 1):
            try:
                event = json.loads(row["event_json"])
                material = {k: v for k, v in event.items() if k not in {"event_sha256", "resulting_state_sha256"}}
                command = event["command"]
                timestamp = datetime.fromisoformat(event["created_at"])
                fields = {"contract", "session_id", "loop_id", "sequence", "previous_event_sha256", "event_type", "idempotency_key", "command_sha256", "command", "created_at", "event_sha256", "resulting_state_sha256"}
                if (set(event) != fields or not isinstance(command, dict)
                    or not isinstance(command.get("actor"), str) or not isinstance(command.get("reason"), str)
                    or event["contract"] != EVENT_CONTRACT or event["session_id"] != WORKSPACE_SESSION_ID
                    or event["loop_id"] != "delegate." + claim_id or event["sequence"] != sequence
                    or event["previous_event_sha256"] != state["last_event_sha256"]
                    or event["event_type"] not in {"AGENT_MANDATE_PAUSED", "AGENT_MANDATE_RESUMED", "AGENT_HANDLER_DECISION_RECORDED"}
                    or command["expected_agent_revision"] != state["revision"]
                    or command["expected_agent_state_sha256"] != state["state_sha256"]
                    or not command["actor"].strip() or not command["reason"].strip() or timestamp.tzinfo is None
                    or digest_value(command) != event["command_sha256"]
                    or digest_value(material) != event["event_sha256"]
                    or any(row[key] != event[key] for key in ("session_id", "loop_id", "sequence", "idempotency_key", "command_sha256", "event_sha256", "created_at"))):
                    raise ValueError("delegate journal chain is invalid")
                parent = self.workspace.store.state_at_revision(claim_id, command["expected_revision"])
                if parent["state_sha256"] != command["expected_state_sha256"]:
                    raise ValueError("delegate event has no validated claim parent")
                required = {"actor", "reason", "expected_revision", "expected_state_sha256", "expected_agent_revision", "expected_agent_state_sha256"}
                if event["event_type"] == "AGENT_HANDLER_DECISION_RECORDED":
                    required.add("decision")
                    decision = command["decision"]
                    assessment = effective_assessment(parent) or {}
                    decision_fields = {"question_id", "kind", "answer_id", "assessment_sha256", "preview_sha256"}
                    allowed_fields = decision_fields | ({"draft_event_sha256"} if decision.get("kind") == "draft_approval" else {"conflict_sha256"})
                    if (not decision_fields.issubset(decision) or set(decision) - allowed_fields
                        or decision["kind"] not in {"source_conflict", "draft_approval"}
                        or decision["assessment_sha256"] != assessment.get("assessment_sha256")
                        or len(decision["preview_sha256"]) != 64
                        or any(c not in "0123456789abcdef" for c in decision["preview_sha256"])):
                        raise ValueError("delegate decision is invalid")
                    if decision["kind"] == "source_conflict":
                        conflicts = {"conflict:" + str(index) for index, _ in enumerate(assessment.get("conflicts", []))}
                        if decision["question_id"] not in conflicts or decision["answer_id"] not in {"keep_open", "explained"}:
                            raise ValueError("delegate conflict decision is outside the claim")
                        conflict = assessment["conflicts"][int(decision["question_id"].split(":", 1)[1])]
                        if "conflict_sha256" in decision and decision["conflict_sha256"] != digest_value(conflict):
                            raise ValueError("delegate conflict decision scope differs")
                    elif decision["question_id"] != "draft:request" or decision["answer_id"] not in {"approve", "revise"}:
                        raise ValueError("delegate draft approval is invalid")
                    elif "draft_event_sha256" in decision:
                        drafts = self.workspace.store.drafts_at_revision(claim_id, parent["revision"])
                        current = [draft for draft in drafts if draft.get("source_assessment_sha256") == assessment["assessment_sha256"]]
                        if not current or decision["draft_event_sha256"] != current[-1]["event_sha256"]:
                            raise ValueError("delegate draft decision scope differs")
                if set(command) != required or len(command["actor"]) > 80 or len(command["reason"]) > 1000:
                    raise ValueError("delegate command is invalid")
                material_state = {k: deepcopy(v) for k, v in state.items() if k != "state_sha256"}
                material_state.update(revision=sequence, last_event_sha256=event["event_sha256"])
                if event["event_type"] != "AGENT_HANDLER_DECISION_RECORDED":
                    material_state["paused"] = event["event_type"] == "AGENT_MANDATE_PAUSED"
                else:
                    material_state["decisions"].append({**command["decision"], "actor": command["actor"],
                        "reason": command["reason"], "timestamp": event["created_at"], "event_sha256": event["event_sha256"]})
                state = _sealed(material_state, "state_sha256")
                if state["state_sha256"] != event["resulting_state_sha256"]:
                    raise ValueError("delegate journal state hash differs")
            except (KeyError, TypeError, json.JSONDecodeError) as exc:
                raise ValueError("delegate journal is invalid") from exc
        return state

    def state(self, claim_id):
        with self.journal.connect() as db:
            return self.replay(claim_id, self.rows(db, claim_id))

    def append(self, claim_id, event_type, command, idempotency_key):
        command_hash = digest_value(command)
        with self.journal.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = self.rows(db, claim_id)
            prior = next((r for r in rows if r["idempotency_key"] == idempotency_key), None)
            if prior:
                event = json.loads(prior["event_json"])
                if prior["command_sha256"] != command_hash or event["event_type"] != event_type:
                    raise ValueError("idempotency key was reused with different input")
                state = self.replay(claim_id, rows[:prior["sequence"]])
                return state, event, True
            state = self.replay(claim_id, rows)
            current = self.workspace.store.recover(claim_id)
            if current["revision"] != command["expected_revision"] or current["state_sha256"] != command["expected_state_sha256"]:
                raise ValueError("claim revision is stale; reload before saving")
            if state["revision"] != command["expected_agent_revision"] or state["state_sha256"] != command["expected_agent_state_sha256"]:
                raise ValueError("agent revision is stale; reload before saving")
            event = {"contract": EVENT_CONTRACT, "session_id": WORKSPACE_SESSION_ID, "loop_id": "delegate." + claim_id,
                     "sequence": state["revision"] + 1, "previous_event_sha256": state["last_event_sha256"],
                     "event_type": event_type, "idempotency_key": idempotency_key, "command_sha256": command_hash,
                     "command": command, "created_at": utc_now()}
            event["event_sha256"] = digest_value(event)
            # Validate the proposed event with the same reducer used on restart.
            fake = {**event, "event_json": ""}
            next_material = {k: deepcopy(v) for k, v in state.items() if k != "state_sha256"}
            next_material.update(revision=event["sequence"], last_event_sha256=event["event_sha256"])
            if event_type == "AGENT_HANDLER_DECISION_RECORDED":
                next_material["decisions"].append({**command["decision"], "actor": command["actor"], "reason": command["reason"],
                    "timestamp": event["created_at"], "event_sha256": event["event_sha256"]})
            else:
                next_material["paused"] = event_type == "AGENT_MANDATE_PAUSED"
            next_state = _sealed(next_material, "state_sha256")
            event["resulting_state_sha256"] = next_state["state_sha256"]
            fake["event_json"] = canonical_json_bytes(event).decode()
            self.replay(claim_id, [*rows, fake])
            db.execute("INSERT INTO claim_loop_events(session_id,loop_id,sequence,idempotency_key,command_sha256,event_sha256,event_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
                       tuple(event[k] for k in ("session_id", "loop_id", "sequence", "idempotency_key", "command_sha256", "event_sha256")) + (fake["event_json"], event["created_at"]))
            db.commit()
            return next_state, event, False


class AgentDeskServiceV1:
    def __init__(self, workspace, work):
        self.workspace, self.work = workspace, work
        self.process = CausalWorkspaceService(workspace)
        self.delegate = DelegateJournal(workspace)
        self._lock = RLock()
        self._desk_lock = RLock()
        self._source_cache = {}
        self._draft_cache = {}
        self._assessment_cache = {}
        self._question_cache = {}
        self._desk_cache = None
        self._desk_row_cache = {}
        self.work.reference_completion = self._prepare_draft
        self.work.reference_finished = self._reference_finished
        with self.work.store.transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS work_desk_requests(idempotency_key TEXT PRIMARY KEY,request_sha256 TEXT NOT NULL,plan_json TEXT NOT NULL)")

    def _source(self, claim_id, artifact_id):
        key = (claim_id, artifact_id)
        # Source hashes are checked even when the bounded PDF extraction is cached.
        raw, metadata = self.workspace.corpus.artifact(claim_id, artifact_id)
        from hashlib import sha256
        if sha256(raw).hexdigest() != metadata["sha256"]:
            raise ValueError("source bytes differ from the claim binding")
        if key not in self._source_cache:
            self._source_cache[key] = self.work.authority.read_source(claim_id, artifact_id)
        return self._source_cache[key]

    def _citations(self, claim_id, rows):
        citations = []
        for item in rows:
            artifact_id = item.get("artifact_id") or item.get("source_id")
            quote = item.get("quote") or item.get("source_quote")
            if not artifact_id or not quote:
                continue
            try:
                source = self._source(claim_id, artifact_id)
                start = source["text"].find(quote)
                if start < 0:
                    continue
                citations.append({"artifact_id": artifact_id, "source_sha256": source["source_sha256"],
                    "text_sha256": source["text_sha256"], "quote": quote, "start": start, "end": start + len(quote),
                    "page": item.get("page"), "url": f"/api/claim-loops/v1/workspace/claims/{claim_id}/artifacts/{artifact_id}"})
            except (AuthorityError, ValueError):
                continue
        return citations

    def _questions(self, state, *, cite=True):
        cache_key = (state["state_sha256"], cite)
        if not cite and cache_key in self._question_cache:
            return deepcopy(self._question_cache[cache_key])
        claim_id = state["claim_id"]
        assessment = self._assessment(state)
        if not assessment:
            return []
        graph = working_graph(self.workspace.corpus, state)
        evaluation = assessment if state.get("causal_process") is not None else evaluate(graph)
        questions = []
        accountable = state["owner"] or "Unassigned handler"
        def add(question_id, kind, prompt, answers, proposal, reason, counter, docs=(), source_rows=(), **extra):
            value = {"question_id": question_id, "kind": kind, "prompt": prompt, "why": reason, "decider": accountable,
                     "proposal": {"answer_id": proposal, "reason": reason}, "counter_reading": counter,
                     "answers": [{"answer_id": key, "label": label, "description": description} for key, label, description in answers],
                     "sources": self._citations(claim_id, source_rows) if cite else [], "affected_document_types": list(docs),
                     "previewable": True, "pane": "process", **extra}
            questions.append(_sealed(value, "question_sha256"))
        for index, conflict in enumerate(assessment.get("conflicts", [])):
            values = [str(row["value"]) for row in conflict.get("sources", [])]
            fact = conflict.get("fact", "the reported events").replace("_", " ")
            prompt = "How should we handle the conflicting termination dates?" if fact == "termination end date" else "How should we handle conflicting statements about " + fact + "?"
            add("conflict:" + str(index), "source_conflict", prompt,
                [("keep_open", "Keep both readings open", "Continue the missing-evidence review; no source fact is certified."),
                 ("explained", "Record my counter-reading", "Record why the difference matters; source conflict remains visible.")],
                "keep_open", conflict.get("message", "The sources differ.") + (" " + " / ".join(values) if values else ""),
                "Different documents may describe different recipients or events; the difference alone does not establish a defect.",
                source_rows=conflict.get("sources", []), pane="sources")
        for flag, condition in graph["conditions"].items():
            relevant = [doc["document_type"] for doc in evaluation["documents"] if flag in doc.get("condition_flags", [])]
            if not relevant:
                continue
            verdict = condition["verdict"]
            if condition.get("worker") == "handler_correction" and verdict != "unresolved":
                continue
            label = flag.replace("_", " ")
            add("condition:" + flag, "condition", CONDITION_PROMPTS.get(flag, "Does " + label + " apply to this claim?"),
                [("true", "Yes, it applies", "Keep the dependent route applicable."), ("false", "No, it does not apply", "Remove requirements that depend only on this condition."),
                 ("unresolved", "Keep it unresolved", "Keep the question open until a source establishes it.")],
                verdict, "The reported passage supports this route; handler confirmation is required." if verdict != "unresolved" else "The admitted sources do not establish this condition.",
                "A report can be incomplete. Confirm its meaning before changing dependent requirements.", relevant,
                [{"source_id": condition.get("source_id"), "quote": condition.get("quote") or condition.get("candidate_quote")}])
        for node in evaluation["nodes"]:
            original = next(n for n in graph["nodes"] if n["node_id"] == node["node_id"])
            if node["activation"] == "false" or original["validation"]["status"] == "validated":
                continue
            add("node:" + node["node_id"], "step_validation", "Can this process step be used: " + node["label"] + "?",
                [("validated", "Validate this step", "Approve the bounded step; this does not complete or decide the claim."),
                 ("disputed", "Dispute this step", "Record that this step needs a process correction."),
                 ("unvalidated", "Leave it unvalidated", "Keep handler review open.")], "validated",
                "The working process proposes this step; only the handler can validate it.",
                "The generic process may not fit this claim's sources or current condition.", original["document_types"])
        for edge in evaluation["edges"]:
            original = next(e for e in graph["edges"] if e["edge_id"] == edge["edge_id"])
            if edge["activation"] == "false" or original["validation"]["status"] == "validated":
                continue
            names = {n["node_id"]: n["label"] for n in graph["nodes"]}
            add("edge:" + edge["edge_id"], "relationship_validation", "Should " + names[edge["source_node_id"]] + " govern " + names[edge["target_node_id"]] + "?",
                [("validated", "Validate this relationship", "Confirm this dependency in the working process."),
                 ("disputed", "Dispute this relationship", "Keep the dependency under review."), ("unvalidated", "Leave it unvalidated", "Keep review open.")],
                "validated", "The process proposes this dependency; the handler owns its validation.",
                "The destination may need an independent prerequisite or a different condition.")
        for node in evaluation["nodes"]:
            if node.get("inconsistent_completion"):
                add("completion:" + node["node_id"], "inconsistent_completion", "Reopen " + node["label"] + " after its prerequisites changed?",
                    [("reopen", "Reopen the step", "Remove the inconsistent completion and review its prerequisites.")], "reopen",
                    "The saved completion no longer agrees with the current prerequisites.", "The completion may remain supported by a source that has not been reviewed yet.", node.get("document_types", []))
        draft = self._draft_at_state(state)
        if draft["latest"] and any(doc["request"] for doc in evaluation["documents"]):
            add("draft:request", "draft_approval", "Approve the current missing-evidence request as a local draft?",
                [("approve", "Approve this draft", "Record handler approval. The request remains not sent."),
                 ("revise", "Revise the draft", "Keep this request for revision; the request remains not sent.")], "approve",
                "The process determines which documents to request. Handler approval is needed before any external action.",
                "The recipient may already hold part of the requested material; review the scope and wording.",
                [doc["document_type"] for doc in evaluation["documents"] if doc["request"]], pane="draft", draft=draft["latest"])
        if not cite:
            self._question_cache[cache_key] = deepcopy(questions)
            if len(self._question_cache) > 256:
                self._question_cache.pop(next(iter(self._question_cache)))
        return questions

    def _assessment(self, state):
        key = (state.get("causal_process") or {}).get("graph_sha256") or (state.get("intake_assessment") or {}).get("assessment_sha256") or state["state_sha256"]
        if key not in self._assessment_cache:
            self._assessment_cache[key] = effective_assessment(state)
            if len(self._assessment_cache) > 256:
                self._assessment_cache.pop(next(iter(self._assessment_cache)))
        return self._assessment_cache[key]

    def _draft_at_state(self, state):
        if not state["intake_assessment"]:
            return {"items": [], "latest": None}
        cached = self._draft_cache.get(state["state_sha256"])
        if cached is not None:
            return deepcopy(cached)
        items = self.workspace.store.drafts_at_revision(state["claim_id"], state["revision"])
        assessment_hash = (self._assessment(state) or {}).get("assessment_sha256")
        current = [d for d in items if d.get("source_assessment_sha256") == assessment_hash]
        result = {"items": items, "latest": current[-1] if current else None}
        self._draft_cache[state["state_sha256"]] = deepcopy(result)
        if len(self._draft_cache) > 256:
            self._draft_cache.pop(next(iter(self._draft_cache)))
        return result

    def _run(self, claim_id):
        states = {state["claim_id"]: state for state in self.workspace.states()}
        runs = self.work.store.list_runs(claim_id, 1)
        return self._packets(states, runs).get(claim_id)

    def _packets(self, states, runs):
        """Reuse the queue's tamper-sensitive read-only replay, not full UI views."""
        from .workspace_claim_loop_v1 import WORKSPACE_CLAIM_LOOP_SESSION_ID, WorkspaceClaimLoopServiceV1
        loops = {claim_id: WorkspaceClaimLoopServiceV1._loop_id(state["intake_assessment"]["assessment_sha256"])
                 for claim_id, state in states.items() if state.get("intake_assessment") and any(r["claim_id"] == claim_id for r in runs)}
        stores = defaultdict(list)
        facade = self.work.authority._loop()
        with self.workspace.store.journal.connect() as db:
            existing_loops = {r["loop_id"] for r in db.execute("SELECT DISTINCT loop_id FROM claim_loop_events WHERE session_id=?", (WORKSPACE_CLAIM_LOOP_SESSION_ID,))}
        for loop_id in loops.values():
            if loop_id in existing_loops:
                stores[facade._authority_store_for_loop(loop_id)].append(loop_id)
        source_states = {}
        for store, loop_ids in stores.items():
            source_states.update(store.state_bytes_prefixes_read_only(
                session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID, loop_ids=tuple(loop_ids)))
        packets = {}
        for run in runs:
            snapshot = self.work.store.snapshot(run["run_id"])
            summary = summarize(self.work.store, run, snapshot)
            summary["recovery"] = self.work.recovery(snapshot)
            job = self.work._jobs.get(run["run_id"])
            if job is not None and not job.done() and summary["recovery"]["can_resume"]:
                summary["recovery"] = {"can_resume": False, "reason": "scheduled_here"}
            saved = next((o["value"] for o in snapshot["objects"] if o["kind"] == "authority_snapshot"), None)
            currentness = "not_yet_checked"
            state = states[run["claim_id"]]
            if saved:
                source = source_states.get(loops.get(run["claim_id"]))
                if not source:
                    currentness = "unconfirmed"
                else:
                    source_state = json.loads(source[0])
                    current_hash = digest_value({"workspace": state["state_sha256"], "source_loop": source_state["state_sha256"]}) if state.get("causal_process") is not None else source_state["state_sha256"]
                    descriptors = [{"source_id": a["artifact_id"], "source_sha256": a["sha256"], "filename": a["file_name"],
                        "media_type": a["media_type"], "size_bytes": a["size_bytes"], "role": a["role"]} for a in state["binding"]["observable_artifacts"]]
                    context = snapshot["run"]["request"]["context"]
                    matches = context["binding_sha256"] == state["binding"]["binding_sha256"] and context["source_roster_sha256"] == digest_value(descriptors)
                    currentness = "current" if matches and current_hash == saved["state_sha256"] else "historical"
            summary["currentness"] = currentness
            summary["authority_snapshot_currentness"] = currentness
            summary["currentness_scope"] = "authority_state"
            if (currentness == "historical" and saved and matches
                and self._current_after_automatic_draft(state, saved, source_state["state_sha256"])):
                summary["currentness"] = "current"
                summary["currentness_scope"] = "reviewed_sources_and_process"
                summary["currentness_note"] = "The reviewed sources and process are unchanged; only automatic local draft preparation advanced the workspace."
            packets[run["claim_id"]] = {"summary": summary, "objects": snapshot["objects"],
                "events": snapshot["events"], "source_count": snapshot["run"]["request"]["context"]["source_count"]}
        return packets

    def _current_after_automatic_draft(self, state, saved, source_loop_sha256):
        """A desk equivalence only; original authority/tool gates stay exact."""
        prior_hash = saved.get("workspace_state_sha256")
        revision = saved.get("revision")
        if (not prior_hash or type(revision) is not int or revision >= state["revision"]
            or digest_value({"workspace": prior_hash, "source_loop": source_loop_sha256}) != saved.get("state_sha256")):
            return False
        graph = state.get("causal_process") or {}
        process = saved.get("process") or {}
        assessment = self._assessment(state) or {}
        if (graph.get("graph_sha256") != process.get("graph_sha256")
            or assessment.get("assessment_sha256") != process.get("assessment_sha256")):
            return False
        parent = self.workspace.store.state_at_revision(state["claim_id"], revision)
        if (parent["state_sha256"] != prior_hash or parent["binding"] != state["binding"]
            or (parent.get("causal_process") or {}).get("graph_sha256") != graph.get("graph_sha256")):
            return False
        suffix = [event for event in self.process._events(state["claim_id"], state["revision"]) if event["sequence"] > revision]
        return bool(suffix) and all(event["event_type"] == "WORKSPACE_DRAFT_RECORDED"
            and event["idempotency_key"].startswith("desk.auto-draft.")
            and not event["command"]["draft"].get("edited_by_handler", True)
            and event["command"]["draft"]["source_assessment_sha256"] == process["assessment_sha256"] for event in suffix)

    def _coverage(self, state, packet):
        roster = state["binding"]["observable_artifacts"]
        opened = [o["value"] for o in (packet or {}).get("objects", []) if o["kind"] == "opened_source"]
        by_id = {o["source_id"]: o for o in opened}
        limited = [{"artifact_id": o["source_id"], "label": o.get("filename", o["source_id"]),
                    "reason": o.get("coverage_note") or "Only extracted text was read; images and unavailable pages remain unchecked."}
                   for o in opened if not o.get("complete", False)]
        unread = sum(row["artifact_id"] not in by_id for row in roster)
        original = (packet or {}).get("source_count")
        return {"scope": "original_bound_intake", "total_sources": len(roster), "read_sources": len(opened), "unreadable_sources": len(limited),
                "unread_sources": unread, "arrived_since": max(0, len(roster) - original) if isinstance(original, int) else None,
                "limited_sources": limited,
                "note": f"{len(opened)} of {len(roster)} original bound sources read." + (f" {len(limited)} have limited text coverage." if limited else "") + (" Remaining sources have not been read by this review." if unread else "")}

    def _activity(self, claim_id, packet):
        if not packet:
            return []
        events = packet.get("events") or self.work.store.events(packet["summary"]["run_id"])
        types = {"SOURCE_OPENED", "AGENT_STARTED", "AGENT_COMPLETED", "HANDOFF_COMPLETED", "RUN_COMPLETED", "RUN_INTERRUPTED", "RUN_PAUSE_REQUESTED", "RUN_BLOCKED", "RUN_FAILED", "READINESS_AUDITED", "PROPOSAL_RECORDED"}
        selected = [e for e in events if e["operation"] in types]
        activity = [{"sequence": e["sequence"], "timestamp": e["timestamp"], "type": e["operation"],
                 "label": e["message"], "role": e.get("role"),
                 "sources": [{"artifact_id": s["source_id"], "quote": s["quote"], "start": s["start"], "end": s["end"], "page": s.get("page"),
                    "source_sha256": s["source_sha256"], "text_sha256": s["text_sha256"],
                    "url": f"/api/claim-loops/v1/workspace/claims/{claim_id}/artifacts/{s['source_id']}"} for s in e.get("sources", [])]}
                for e in selected[-12:]]
        with self.delegate.journal.connect() as db:
            drafts = db.execute("SELECT sequence,created_at,event_json FROM claim_loop_events WHERE session_id=? AND loop_id=? AND idempotency_key LIKE 'desk.auto-draft.%' ORDER BY sequence DESC LIMIT 1",
                (WORKSPACE_SESSION_ID, "workspace." + claim_id)).fetchall()
        if drafts:
            event = json.loads(drafts[0]["event_json"])
            if event["event_type"] == "WORKSPACE_DRAFT_RECORDED":
                activity.append({"sequence": drafts[0]["sequence"], "timestamp": drafts[0]["created_at"], "type": "DRAFT_PREPARED",
                    "label": "Prepared the missing-evidence request for handler review; not sent", "role": "CasePath agent", "sources": []})
        return sorted(activity, key=lambda e: e["timestamp"])[-12:]

    def _scoped_decisions(self, claim_id, control):
        decisions = deepcopy(control["decisions"])
        missing = [d for d in decisions if d["kind"] == "draft_approval" and not d.get("draft_event_sha256")
                   or d["kind"] == "source_conflict" and not d.get("conflict_sha256")]
        if missing:
            with self.delegate.journal.connect() as db:
                events = {json.loads(r["event_json"])["event_sha256"]: json.loads(r["event_json"]) for r in self.delegate.rows(db, claim_id)}
            for decision in missing:
                command = events[decision["event_sha256"]]["command"]
                parent = self.workspace.store.state_at_revision(claim_id, command["expected_revision"])
                if decision["kind"] == "draft_approval":
                    draft = self._draft_at_state(parent)["latest"]
                    decision["draft_event_sha256"] = draft["event_sha256"] if draft else None
                else:
                    conflicts = (self._assessment(parent) or {}).get("conflicts", [])
                    index = int(decision["question_id"].split(":", 1)[1])
                    decision["conflict_sha256"] = digest_value(conflicts[index])
        return decisions

    def _prepare_draft(self, claim_id, run_id=None):
        """Accepted process review or completed work can prepare local wording."""
        with self._lock:
            if self.delegate.state(claim_id)["paused"]:
                return
            state = self.workspace.store.recover(claim_id)
            assessment = self._assessment(state)
            if not assessment or state["workflow_state"] != "in_review" or not any(d["request"] for d in assessment["documents"]):
                return
            drafts = self._draft_at_state(state)
            if drafts["latest"]:
                return
            key = "desk.auto-draft." + digest_value({"claim_id": claim_id, "assessment_sha256": assessment["assessment_sha256"]})
            try:
                self.workspace.record_draft(claim_id, expected_revision=state["revision"], expected_state_sha256=state["state_sha256"],
                    idempotency_key=key, replaces_event_sha256=drafts["items"][-1]["event_sha256"] if drafts["items"] else None)
            except ClaimWorkspaceError:
                # A concurrent handler edit wins. No draft is claimed until a
                # journal event exists; the next reviewed arrival can retry.
                return

    def process_accepted(self, claim_id, result, *, dispatch=True):
        """Follow the latest accepted causal edit without changing its receipt."""
        if (result.get("contract") != "casepath.causal-process-result/1.0.0"
            or result.get("claim_id") != claim_id
            or result.get("result_sha256") != digest_value({k: v for k, v in result.items() if k != "result_sha256"})):
            raise ValueError("accepted process receipt differs")
        with self._lock:
            if self._latest_process_edit(claim_id) != result["event_sha256"]:
                return {"started": False, "reason": "superseded_process_edit"}
            if self.delegate.state(claim_id)["paused"]:
                return {"started": False, "reason": "paused_by_handler"}
            self._prepare_draft(claim_id)
            return self._continue(claim_id, key="desk.continue." + result["event_sha256"], dispatch=dispatch,
                                  accepted_process_event_sha256=result["event_sha256"])

    def _latest_process_edit(self, claim_id):
        event = self._latest_process_event(claim_id)
        return event["event_sha256"] if event else None

    def _latest_process_event(self, claim_id):
        state = self.workspace.store.recover(claim_id)
        edits = [event for event in self.process._events(claim_id, state["revision"]) if event["event_type"] == PROCESS_EDIT]
        return edits[-1] if edits else None

    def _reference_finished(self, claim_id, run_id):
        """After an actual terminal checkpoint, follow only the latest accepted edit."""
        with self._lock:
            snapshot = self.work.store.snapshot(run_id)
            run = snapshot["run"]
            if (run["request"]["facts_worker"] != "reference" or snapshot["pending_calls"]
                or run["status"] not in {"completed", "cancelled", "blocked", "failed", "interrupted"}
                or self.delegate.state(claim_id)["paused"]):
                return
            latest = self._latest_process_event(claim_id)
            if latest is None or latest["sequence"] <= run["request"]["context"]["revision"]:
                return
            self._prepare_draft(claim_id)
            self._continue(claim_id, key="desk.continue." + latest["event_sha256"],
                           accepted_process_event_sha256=latest["event_sha256"])

    def claim(self, claim_id, *, state=None, learning=True, cite=True, control=None, packet=None, packet_supplied=False):
        state = state or self.workspace.store.recover(claim_id)
        control = control or self.delegate.state(claim_id)
        packet = packet if packet_supplied else self._run(claim_id)
        summary = packet["summary"] if packet else None
        questions = self._questions(state, cite=cite)
        assessment = self._assessment(state)
        decisions = self._scoped_decisions(claim_id, control)
        latest_draft = self._draft_at_state(state)["latest"]
        conflict_hashes = {"conflict:" + str(i): digest_value(c) for i, c in enumerate((assessment or {}).get("conflicts", []))}
        reviewed = {d["question_id"]: d for d in decisions if
                    (d["kind"] == "source_conflict" and d.get("conflict_sha256") == conflict_hashes.get(d["question_id"])) or
                    (d["kind"] == "draft_approval" and latest_draft and d.get("draft_event_sha256") == latest_draft["event_sha256"])}
        conflicts = []
        for question in questions:
            if question["kind"] == "source_conflict":
                conflicts.append({**question, "review": reviewed.get(question["question_id"]),
                                  "truth_status": "unresolved", "sources": question["sources"]})
        questions = [q for q in questions if q["question_id"] not in reviewed]
        if control["paused"]:
            agent_state = "paused" if not summary or summary["status"] != "running" else "working"
        elif summary and summary["status"] in {"queued", "running"}:
            agent_state = "working"
        elif summary and summary["status"] in {"failed", "blocked", "unconfirmed", "interrupted"}:
            agent_state = "failed" if summary["status"] in {"failed", "blocked"} else "unknown"
        elif questions:
            agent_state = "waiting_for_you"
        elif summary and summary["status"] == "completed" and summary["currentness"] == "current":
            agent_state = "done"
        else:
            agent_state = "unknown"
        recovery_required = bool(not control["paused"] and summary and summary["status"] in {"interrupted", "unconfirmed"})
        recovery_ask = None
        if recovery_required:
            recovery = summary.get("recovery") or {}
            if recovery.get("can_resume") is True and summary.get("facts_worker") == "reference":
                recovery_ask = "Review the saved checkpoint before resuming the interrupted review."
            elif recovery.get("reason") in {"pending_operation", "provider_attempt_recorded"}:
                recovery_ask = "Inspect the unfinished operation and reconcile its outcome before retrying."
            else:
                recovery_ask = "Inspect the saved work; the review's execution status needs verification."
        material = {"contract": CONTRACT, "claim_id": claim_id, "workspace_revision": state["revision"],
            "workspace_state_sha256": state["state_sha256"], "agent_revision": control["revision"], "agent_state_sha256": control["state_sha256"],
            "owner": {"accountable": state["owner"], "delegate": "CasePath agent"}, "mandate": deepcopy(MANDATE),
            "state": agent_state, "pause_requested": control["paused"], "questions": questions, "decisions": decisions,
            "recovery_required": recovery_required, "recovery_ask": recovery_ask,
            "conflicts": conflicts,
            "coverage": self._coverage(state, packet), "activity": self._activity(claim_id, packet), "run": summary,
            "process_status": assessment.get("process_status") if assessment else None,
            "learning": {"fragments": self.process.fragments(working_graph(self.workspace.corpus, state)["family"]) if learning and assessment else [],
                         "memories": self.workspace.reviewed_memories(claim_id)["items"] if learning and assessment else [],
                         "uses": ([o for o in self.workspace.store.handler_observations_at_revision(claim_id, state["revision"]) if o.get("memory_sha256")]
                            + [{"kind": "fragment_use", "fragment_sha256": e["command"]["operation"]["fragment_sha256"], "claim_id": claim_id,
                                "revision": e["sequence"], "event_sha256": e["event_sha256"], "actor": e["command"]["actor"], "reason": e["command"]["reason"]}
                               for e in self.process._events(claim_id, state["revision"]) if e["event_type"] == PROCESS_EDIT and e["command"]["operation"].get("type") == "fragment.apply"]) if learning else [],
                         "automatic_learning": False}, "authority": "claim_loop_events", "claim_decision_authorized": False}
        return _sealed(material)

    def desk(self):
        # Concurrent browser polls share one verified cache fill instead of
        # independently replaying the same 150-claim prefix.
        with self._desk_lock:
            return self._desk_projection()

    def _desk_projection(self):
        # Every persisted byte is fingerprinted before reusing an already
        # validated projection. A changed prefix always takes the replay path.
        from hashlib import sha256
        import time
        from .workspace_claim_loop_v1 import WORKSPACE_CLAIM_LOOP_SESSION_ID, WorkspaceClaimLoopServiceV1
        signature = sha256()
        corpus_token = str(self.workspace.corpus.observed_runtime_identity_token()).encode()
        signature.update(corpus_token)
        journal_fingerprints = defaultdict(list)
        knowledge_fingerprints = []
        with self.delegate.journal.connect() as db:
            for row in db.execute("SELECT * FROM claim_loop_events ORDER BY session_id,loop_id,sequence"):
                row_hash = self.workspace.store._row_fingerprint(row)
                signature.update(row_hash)
                journal_fingerprints[(row["session_id"], row["loop_id"])].append(row_hash)
                if "MEMORY" in row["event_json"] or "FRAGMENT" in row["event_json"]:
                    knowledge_fingerprints.append(row_hash)
        work_fingerprints = defaultdict(sha256)
        run_claims = {}
        latest_rows = {}
        with self.work.store.connect() as db:
            # All tables and the selected latest roster share one SQLite read
            # boundary. A concurrent new run appears on the next projection.
            db.execute("BEGIN")
            for table, order in (("work_runs", "run_id"), ("work_events", "run_id,sequence"), ("work_objects", "run_id,object_id"), ("work_calls", "run_id,role,call_id"), ("work_pause_requests", "run_id")):
                signature.update(table.encode("ascii"))
                count = 0
                for row in db.execute(f"SELECT * FROM {table} ORDER BY {order}"):
                    count += 1
                    row_signature = sha256()
                    _fingerprint_row(row_signature, row)
                    if table == "work_runs" and row["status"] == "running":
                        row_signature.update(str((row["lease_until"] or 0) <= time.time()).encode())
                    if table == "work_runs":
                        run_claims[row["run_id"]] = row["claim_id"]
                        latest = latest_rows.get(row["claim_id"])
                        if latest is None or (row["created_at"], row["run_id"]) > (latest["created_at"], latest["run_id"]):
                            latest_rows[row["claim_id"]] = dict(row)
                        job = self.work._jobs.get(row["run_id"])
                        row_signature.update(str(job is not None and not job.done()).encode())
                    row_hash = row_signature.digest()
                    signature.update(row_hash)
                    work_fingerprints[run_claims[row["run_id"]]].update(table.encode("ascii") + row_hash)
                signature.update(count.to_bytes(8, "big"))
            db.commit()
        fingerprint = signature.digest()
        if self._desk_cache is not None and self._desk_cache[0] == fingerprint:
            return json.loads(self._desk_cache[1])
        groups = {key: [] for key, _ in GROUPS}
        unstarted = 0
        with self.delegate.journal.connect() as db:
            control_rows = db.execute("SELECT * FROM claim_loop_events WHERE session_id=? AND loop_id LIKE 'delegate.%' ORDER BY loop_id,sequence", (WORKSPACE_SESSION_ID,)).fetchall()
        by_claim = defaultdict(list)
        for row in control_rows:
            by_claim[row["loop_id"][len("delegate."):]].append(row)
        latest_runs = [self.work.store._decode_run(row) for row in latest_rows.values()]
        states = self.workspace.states()
        claim_ids = {state["claim_id"] for state in states}
        source_claims = {WorkspaceClaimLoopServiceV1._loop_id(state["intake_assessment"]["assessment_sha256"]): state["claim_id"]
                         for state in states if state.get("intake_assessment")}
        global_signature = sha256(corpus_token)
        for row_hash in knowledge_fingerprints:
            global_signature.update(row_hash)
        claim_signatures = defaultdict(sha256)
        for (session_id, loop_id), row_hashes in journal_fingerprints.items():
            claim_id = None
            if session_id == WORKSPACE_SESSION_ID and loop_id.startswith(("workspace.", "delegate.")):
                claim_id = loop_id.split(".", 1)[1]
            elif session_id == WORKSPACE_CLAIM_LOOP_SESSION_ID:
                claim_id = source_claims.get(loop_id)
            selected = claim_signatures[claim_id] if claim_id in claim_ids else global_signature
            selected.update(session_id.encode() + b"\0" + loop_id.encode() + b"\0")
            for row_hash in row_hashes:
                selected.update(row_hash)
        for claim_id, work_signature in work_fingerprints.items():
            selected = claim_signatures[claim_id] if claim_id in claim_ids else global_signature
            selected.update(work_signature.digest())
        global_hash = global_signature.digest()
        row_signatures = {claim_id: sha256(global_hash + claim_signatures[claim_id].digest()).digest() for claim_id in claim_ids}
        dirty = {state["claim_id"]: state for state in states
                 if self._desk_row_cache.get(state["claim_id"], (None,))[0] != row_signatures[state["claim_id"]]}
        run_packets = self._packets(dirty, [run for run in latest_runs if run["claim_id"] in dirty])
        for state in states:
            if state["claim_id"] not in dirty:
                row = json.loads(self._desk_row_cache[state["claim_id"]][1])
                groups[row["group"]].append(row)
                unstarted += not row["review_started"]
                continue
            control = self.delegate.replay(state["claim_id"], by_claim[state["claim_id"]])
            agent = self.claim(state["claim_id"], state=state, learning=False, cite=False,
                control=control, packet=run_packets.get(state["claim_id"]), packet_supplied=True)
            if not agent["run"]:
                unstarted += 1
            group = "working" if agent["state"] == "working" else "waiting" if agent["state"] == "waiting_for_others" else "needs_you" if agent["recovery_required"] or agent["questions"] or agent["state"] in {"paused", "failed"} else "quiet"
            question = agent["questions"][0] if agent["questions"] else None
            claim = self.workspace.corpus.claim(state["claim_id"])
            drafts = self._draft_at_state(state)
            approved = any(d.get("kind") == "draft_approval" and drafts["latest"] and d.get("draft_event_sha256") == drafts["latest"]["event_sha256"] and d.get("answer_id") == "approve" for d in agent["decisions"])
            subject = claim["customer_message"]["subject"]
            assessment = self._assessment(state) or {}
            active_conflicts = [q for q in agent["questions"] if q["kind"] == "source_conflict"]
            ask = question["prompt"] if question else None
            if active_conflicts:
                conflict_index = int(active_conflicts[0]["question_id"].split(":", 1)[1])
                conflict = assessment["conflicts"][conflict_index]
                values = [str(source["value"]) for source in conflict.get("sources", [])]
                ask = "Review the " + "/".join(values) + " conflict" if values else "Review the different source readings"
                deadline = assessment.get("candidate_deadline") or {}
                if deadline.get("date") is None and deadline.get("question"):
                    ask += "; receipt dates are still needed to establish the deadline."
                else:
                    ask += "."
                if drafts["latest"]:
                    labels = [item["label"] for item in drafts["latest"].get("requested", [])]
                    scope = ", ".join(labels[:2]) + (" and other requested evidence" if len(labels) > 2 else "")
                    ask += " Review the " + ("approved" if approved else "prepared") + " request" + (" for " + scope if scope else " wording") + " (not sent)."
                else:
                    ask += " The missing-evidence request has not been prepared yet."
            if agent["recovery_required"]:
                ask = agent["recovery_ask"]
            row = {"claim_id": state["claim_id"], "subject": subject, "title": subject, "reference": state["claim_id"],
                "owner": state["owner"], "accountable": state["owner"], "delegate": "CasePath agent", "agent_state": agent["state"], "group": group,
                "ask": ask or ("Resume the delegated review when you are ready." if agent["pause_requested"] else "Review the saved failure before continuing." if agent["state"] == "failed" else "Deterministic review has not started." if not agent["run"] else (agent["run"].get("last_message") or "Saved review work is available.")),
                "why": "The persisted review needs a recovery check." if agent["recovery_required"] else question["why"] if question else state["principal_blocker"], "decider": state["owner"] or "Unassigned handler", "question_count": len(agent["questions"]),
                "workspace_revision": state["revision"], "workspace_state_sha256": state["state_sha256"],
                "latest_activity": agent["activity"][-1] if agent["activity"] else None, "coverage": agent["coverage"],
                "review_started": agent["run"] is not None,
                "recovery_required": agent["recovery_required"], "recovery_ask": agent["recovery_ask"],
                "run_id": agent["run"]["run_id"] if agent["run"] else None, "run_status": agent["run"]["status"] if agent["run"] else None,
                "deadline": assessment.get("candidate_deadline"),
                "draft_status": "approved_not_sent" if approved else "draft_not_sent" if drafts["latest"] else "not_prepared", "process_status": agent["process_status"], "claim_decision_authorized": False}
            groups[group].append(row)
            self._desk_row_cache[state["claim_id"]] = (row_signatures[state["claim_id"]], canonical_json_bytes(row))
        for rows in groups.values():
            rows.sort(key=lambda row: (row["claim_id"] != FAMILY_HOME, row["subject"]))
        material = {"contract": "casepath.agent-desk/1.0.0", "groups": [{"id": key, "label": label, "count": len(groups[key]), "claims": groups[key]} for key, label in GROUPS],
                    "counts": {key: len(rows) for key, rows in groups.items()}, "total": sum(map(len, groups.values())),
                    "unstarted_count": unstarted, "authority": "claim_loop_events", "includes_invented_activity": False}
        result = _sealed(material)
        self._desk_cache = (fingerprint, canonical_json_bytes(result))
        return result

    def _continue(self, claim_id, *, key=None, dispatch=True, accepted_process_event_sha256=None, accepted_delegate_event=None):
        def blocked_reason():
            control = self.delegate.state(claim_id)
            if control["paused"]:
                return "paused_by_handler"
            if accepted_process_event_sha256 is not None and self._latest_process_edit(claim_id) != accepted_process_event_sha256:
                return "superseded_process_edit"
            if accepted_delegate_event is not None:
                command = accepted_delegate_event["command"]
                current = self.workspace.store.recover(claim_id)
                if (control["last_event_sha256"] != accepted_delegate_event["event_sha256"]
                    or current["revision"] != command["expected_revision"]
                    or current["state_sha256"] != command["expected_state_sha256"]):
                    return "superseded_agent_decision"
            return None
        reason = blocked_reason()
        if reason:
            return {"started": False, "reason": reason}
        runs = self.work.store.list_runs(claim_id, 1)
        if runs and self.work.store.pending_calls(runs[0]["run_id"]):
            # An executing local read may finish before checkpoint cancellation.
            # An expired or terminal operation has an unknown outcome instead.
            import time
            active_reference = (runs[0]["status"] == "running"
                and runs[0]["request"]["facts_worker"] == "reference"
                and (runs[0].get("lease_until") or 0) > time.time())
            if not active_reference:
                return {"started": False, "reason": "recorded_operation_requires_reconciliation"}
        if runs and runs[0]["status"] in {"queued", "running", "interrupted"}:
            if runs[0]["request"].get("facts_worker") != "reference":
                return {"started": False, "reason": "existing_external_work_requires_review"}
            latest = self._latest_process_event(claim_id) if accepted_process_event_sha256 is not None else None
            if latest is not None and latest["sequence"] > runs[0]["request"]["context"]["revision"]:
                reason = blocked_reason()
                if reason:
                    return {"started": False, "reason": reason}
                snapshot = self.work.supersede_reference(claim_id, runs[0]["run_id"], latest["event_sha256"])
                packet = self._packets({claim_id: self.workspace.store.recover(claim_id)}, [snapshot["run"]])[claim_id]
                if snapshot["pending_calls"] and snapshot["run"]["status"] in {"cancelled", "completed", "blocked", "failed"}:
                    return {"started": False, "run": packet["summary"], "reason": "recorded_operation_requires_reconciliation"}
                if snapshot["run"]["status"] not in {"cancelled", "completed", "blocked", "failed"}:
                    return {"started": False, "run": packet["summary"], "reason": "latest_process_review_queued"}
                # Queued/interrupted cancellation has already committed its
                # terminal event. Finish may also have won the stop race; its
                # validated terminal receipt permits the same guarded handoff.
            else:
                packet = self.work.run(claim_id, runs[0]["run_id"])
                if packet["summary"]["recovery"]["can_resume"] and dispatch:
                    reason = blocked_reason()
                    if reason:
                        return {"started": False, "reason": reason}
                    packet = self.work.resume(claim_id, runs[0]["run_id"])
                return {"started": False, "run": packet["summary"], "reason": "existing_run"}
        if runs and (not key or accepted_process_event_sha256 is not None):
            packet = self._packets({claim_id: self.workspace.store.recover(claim_id)}, runs)[claim_id]
            if packet["summary"]["status"] == "completed" and packet["summary"]["currentness"] == "current":
                return {"started": False, "run": packet["summary"], "reason": "already_reviewed"}
        context = self.work.context(claim_id)
        reason = blocked_reason()
        if reason:
            return {"started": False, "reason": reason}
        key = key or "desk.review." + context["context_sha256"]
        previous = self.work.store.find_request(claim_id, key)
        packet = self.work.run(claim_id, previous["run_id"]) if previous else self.work.start(claim_id, idempotency_key=key,
                    expected_context_sha256=context["context_sha256"], facts_worker="reference", dispatch=dispatch)
        return {"started": previous is None, "run": packet["summary"], "reason": "deterministic_reference"}

    def start(self, *, limit=6, idempotency_key=None):
        with self._lock:
            idempotency_key = idempotency_key or f"desk.arrival.synthetic150.{limit}"
            request_hash = digest_value({"limit": limit, "mode": "deterministic_reference"})
            with self.work.store.connect() as db:
                prior = db.execute("SELECT * FROM work_desk_requests WHERE idempotency_key=?", (idempotency_key,)).fetchone()
            if prior:
                if prior["request_sha256"] != request_hash:
                    raise ValueError("idempotency key was reused for a different desk-start request")
                plan = json.loads(prior["plan_json"])
                if digest_value(plan["items"]) != plan["sha256"]:
                    raise ValueError("desk-start request plan is invalid")
            else:
                candidates = []
                states = sorted(self.workspace.states(), key=lambda s: (s["claim_id"] != FAMILY_HOME, s["workflow_state"] != "in_review", s["claim_id"]))
                for state in states:
                    if self.delegate.state(state["claim_id"])["paused"]:
                        continue
                    context = self.work.context(state["claim_id"])
                    candidates.append({"claim_id": state["claim_id"], "expected_context_sha256": context["context_sha256"],
                                       "key": "desk.review." + digest_value({"request": idempotency_key, "claim_id": state["claim_id"]})})
                    if len(candidates) >= limit:
                        break
                plan = {"items": candidates, "sha256": digest_value(candidates)}
                with self.work.store.transaction() as db:
                    db.execute("INSERT INTO work_desk_requests VALUES(?,?,?)", (idempotency_key, request_hash, canonical_json_bytes(plan).decode()))
            selected, paused, reasons = {}, set(), {}
            for item in plan["items"]:
                claim_id = item["claim_id"]
                if self.delegate.state(claim_id)["paused"]:
                    paused.add(claim_id)
                    continue
                existing = self.work.store.find_request(claim_id, item["key"])
                latest = self.work.store.list_runs(claim_id, 1)
                if existing:
                    if (existing["request"]["requested_context_sha256"] != item["expected_context_sha256"]
                        or existing["request"]["facts_worker"] != "reference"):
                        raise ValueError("desk-start run differs from its persisted request plan")
                    selected[claim_id], reasons[claim_id] = existing, "idempotent_desk_arrival"
                elif latest:
                    selected[claim_id], reasons[claim_id] = latest[0], "existing_review"
            states = {claim_id: self.workspace.store.recover(claim_id) for claim_id in selected}
            packets = self._packets(states, list(selected.values()))
            results = []
            for item in plan["items"]:
                claim_id = item["claim_id"]
                if claim_id in paused or self.delegate.state(claim_id)["paused"]:
                    results.append({"claim_id": claim_id, "started": False, "reason": "paused_by_handler"})
                    continue
                if claim_id in packets:
                    result = {"started": False, "reason": reasons[claim_id], "run": packets[claim_id]["summary"]}
                else:
                    packet = self.work.start(claim_id, idempotency_key=item["key"], expected_context_sha256=item["expected_context_sha256"], facts_worker="reference")
                    result = {"started": True, "reason": "deterministic_reference", "run": packet["summary"]}
                if result.get("run", {}).get("status") == "completed":
                    self._prepare_draft(claim_id, result["run"]["run_id"])
                results.append({"claim_id": claim_id, **result})
            return _sealed({"contract": "casepath.agent-desk-start/1.0.0", "results": results,
                            "replayed": prior is not None, "provider_calls": 0, "mode": "deterministic_reference"})

    def control(self, claim_id, *, action, actor, reason, expected_revision, expected_state_sha256, expected_agent_revision, expected_agent_state_sha256, idempotency_key):
        if action not in {"pause", "resume"} or not actor.strip() or not reason.strip():
            raise ValueError("A handler and reason are required")
        command = {"actor": actor, "reason": reason, "expected_revision": expected_revision, "expected_state_sha256": expected_state_sha256,
                   "expected_agent_revision": expected_agent_revision, "expected_agent_state_sha256": expected_agent_state_sha256}
        with self._lock:
            _, event, replayed = self.delegate.append(claim_id, "AGENT_MANDATE_PAUSED" if action == "pause" else "AGENT_MANDATE_RESUMED", command, idempotency_key)
            runs = self.work.store.list_runs(claim_id, 1)
            continuation = None
            superseded = replayed and self.delegate.state(claim_id)["last_event_sha256"] != event["event_sha256"]
            if not superseded and action == "pause" and runs and runs[0]["status"] in {"queued", "running", "interrupted"}:
                self.work.pause(claim_id, runs[0]["run_id"])
            elif not superseded and action == "resume":
                continuation = self._continue(claim_id)
            return _sealed({"contract": "casepath.agent-control-result/1.0.0", "event_sha256": event["event_sha256"],
                "replayed": replayed, "agent": self.claim(claim_id), "continuation": continuation})

    def _decision(self, claim_id, question_id, answer_id, actor, reason, expected_revision, expected_state_sha256):
        state = self.workspace.store.state_at_revision(claim_id, expected_revision)
        if state["state_sha256"] != expected_state_sha256:
            raise ValueError("decision workspace prefix differs")
        question = next((q for q in self._questions(state) if q["question_id"] == question_id), None)
        if not question or answer_id not in {a["answer_id"] for a in question["answers"]}:
            raise ValueError("Choose an answer to a current bounded question")
        if not actor.strip():
            raise ValueError("A reviewing handler is required")
        if answer_id != question["proposal"]["answer_id"] and not reason.strip():
            raise ValueError("A different answer requires a reason")
        return state, question, reason.strip() or question["proposal"]["reason"]

    @staticmethod
    def _operation(question_id, answer_id):
        kind, target = question_id.split(":", 1)
        if kind == "condition":
            return {"type": "conditions.set", "flag": target, "verdict": answer_id}
        if kind in {"node", "edge"}:
            return {"type": kind + ".validate", kind + "_id": target, "status": "rejected" if answer_id == "disputed" else answer_id}
        if kind == "completion":
            return {"type": "node.complete", "node_id": target, "completed": False}
        return None

    def _decision_preview(self, state, question, answer_id, actor, reason, *, causal=None):
        value = {k: v for k, v in (causal or {}).items() if k not in {"contract", "preview_sha256"}}
        if causal is None:
            assessment = effective_assessment(state)
            graph = working_graph(self.workspace.corpus, state)
            control = self.delegate.state(state["claim_id"])
            value.update(claim_id=state["claim_id"], workspace_revision=state["revision"], workspace_state_sha256=state["state_sha256"],
                agent_revision=control["revision"], agent_state_sha256=control["state_sha256"], operation=None,
                graph=graph, evaluation=evaluate(graph), effective_assessment=assessment,
                impact={"changed_document_types": [], "unchanged_document_types": [d["document_type"] for d in assessment["documents"]],
                    "changed_node_ids": [], "unchanged_node_ids": [n["node_id"] for n in graph["nodes"]],
                    "summary": "Record handler review; facts, deadlines and claim outcome remain unchanged."}, not_sent=True)
        value.update(contract="casepath.agent-decision-preview/1.0.0", question=question, answer_id=answer_id,
                     actor=actor, reason=reason, causal=causal)
        return _sealed(_sealed(value, "preview_sha256"), "response_sha256")

    def preview_decision(self, claim_id, *, question_id, answer_id, actor, reason, expected_revision, expected_state_sha256):
        state, question, reason = self._decision(claim_id, question_id, answer_id, actor, reason, expected_revision, expected_state_sha256)
        operation = self._operation(question_id, answer_id)
        causal = None
        if operation:
            causal = self.process.preview(claim_id, operation=operation, actor=actor, reason=reason,
                       expected_revision=expected_revision, expected_state_sha256=expected_state_sha256)
        elif self.workspace.store.recover(claim_id)["state_sha256"] != expected_state_sha256:
            raise ValueError("decision revision is stale")
        return self._decision_preview(state, question, answer_id, actor, reason, causal=causal)

    def apply_decision(self, claim_id, *, question_id, answer_id, actor, reason, expected_revision, expected_state_sha256, preview_sha256, idempotency_key, dispatch=True):
        state, question, reason = self._decision(claim_id, question_id, answer_id, actor, reason, expected_revision, expected_state_sha256)
        operation = self._operation(question_id, answer_id)
        with self._lock:
            if operation:
                causal = preview_material(self.workspace.corpus, state, operation, actor, reason, self.process._fragment(state, operation))
                preview = self._decision_preview(state, question, answer_id, actor, reason, causal=causal)
                if preview["preview_sha256"] != preview_sha256:
                    raise ValueError("decision impact preview differs")
                result = self.process.apply(claim_id, operation=operation, actor=actor, reason=reason, expected_revision=expected_revision,
                    expected_state_sha256=expected_state_sha256, preview_sha256=causal["preview_sha256"], idempotency_key=idempotency_key)
            else:
                # Exact retries reconstruct the bound preview, even after draft preparation advanced the claim.
                with self.delegate.journal.connect() as db:
                    existing = next((json.loads(r["event_json"]) for r in self.delegate.rows(db, claim_id) if r["idempotency_key"] == idempotency_key), None)
                if existing:
                    command = existing["command"]
                    if any(command.get(k) != v for k, v in {"actor": actor, "reason": reason, "expected_revision": expected_revision, "expected_state_sha256": expected_state_sha256}.items()) or command["decision"]["question_id"] != question_id or command["decision"]["answer_id"] != answer_id or command["decision"]["preview_sha256"] != preview_sha256:
                        raise ValueError("idempotency key was reused with different input")
                else:
                    preview = self.preview_decision(claim_id, question_id=question_id, answer_id=answer_id, actor=actor, reason=reason,
                        expected_revision=expected_revision, expected_state_sha256=expected_state_sha256)
                    if preview["preview_sha256"] != preview_sha256:
                        raise ValueError("decision impact preview differs")
                    command = {"actor": actor, "reason": reason, "expected_revision": expected_revision, "expected_state_sha256": expected_state_sha256,
                        "expected_agent_revision": preview["agent_revision"], "expected_agent_state_sha256": preview["agent_state_sha256"],
                        "decision": {"question_id": question_id, "kind": question["kind"], "answer_id": answer_id,
                            "assessment_sha256": effective_assessment(state)["assessment_sha256"], "preview_sha256": preview_sha256}}
                    if question["kind"] == "draft_approval":
                        command["decision"]["draft_event_sha256"] = question["draft"]["event_sha256"]
                    else:
                        command["decision"]["conflict_sha256"] = digest_value((self._assessment(state) or {})["conflicts"][int(question_id.split(":", 1)[1])])
                _, event, replayed = self.delegate.append(claim_id, "AGENT_HANDLER_DECISION_RECORDED", command, idempotency_key)
                result = {"event_sha256": event["event_sha256"], "replayed": replayed, "process": self.process.view(claim_id),
                          "impact": {"changed_document_types": [], "unchanged_document_types": [d["document_type"] for d in effective_assessment(state)["documents"]]}, "not_sent": True}
            # Direct editor and bounded answers share the same delegate hook.
            continuation = self.process_accepted(claim_id, result, dispatch=dispatch) if operation else self._continue(
                claim_id, key="desk.continue." + result["event_sha256"], dispatch=dispatch, accepted_delegate_event=event)
            receipt = result
            response = {k: v for k, v in result.items() if k != "result_sha256"}
            if receipt.get("result_sha256"):
                response["causal_result"] = receipt
            return _sealed({**response, "contract": "casepath.agent-decision-result/1.0.0", "question": question,
                "process": self.process.view(claim_id), "answer_id": answer_id,
                "agent": self.claim(claim_id), "continuation": continuation}, "response_sha256")

    def preview_lesson(self, claim_id, *, name, node_ids, actor, reason, expected_revision, expected_state_sha256):
        state = self.process._parent(claim_id, expected_revision, expected_state_sha256)
        if self.workspace.store.recover(claim_id)["state_sha256"] != state["state_sha256"]:
            raise ValueError("lesson revision is stale")
        graph = working_graph(self.workspace.corpus, state)
        fragment = fragment_snapshot(graph, name=name, node_ids=node_ids, actor=actor, reason=reason,
                    fragment_id="preview", version=1, source_revision=expected_revision)
        value = {"contract": "casepath.agent-lesson-preview/1.0.0", "claim_id": claim_id, "name": name, "node_ids": node_ids,
                 "actor": actor, "reason": reason, "workspace_revision": expected_revision, "workspace_state_sha256": expected_state_sha256,
                 "scope": {"family": graph["family"], "node_ids": node_ids, "boundary_relationships": fragment["boundary_edges"],
                           "documents": [d["document_type"] for d in fragment["document_catalog"]]},
                 "conflicts": [], "fragment_preview": fragment, "approval_required": True, "automatic_learning": False}
        return _sealed(value, "preview_sha256")

    def apply_lesson(self, claim_id, *, preview_sha256, idempotency_key, **body):
        # Existing fragment save gives exact journal retries and validation; preview is read-only.
        parent = self.process._parent(claim_id, body["expected_revision"], body["expected_state_sha256"])
        graph = working_graph(self.workspace.corpus, parent)
        fragment = fragment_snapshot(graph, name=body["name"], node_ids=body["node_ids"], actor=body["actor"], reason=body["reason"],
            fragment_id="preview", version=1, source_revision=body["expected_revision"])
        value = {"contract": "casepath.agent-lesson-preview/1.0.0", "claim_id": claim_id, "name": body["name"], "node_ids": body["node_ids"],
            "actor": body["actor"], "reason": body["reason"], "workspace_revision": body["expected_revision"], "workspace_state_sha256": body["expected_state_sha256"],
            "scope": {"family": graph["family"], "node_ids": body["node_ids"], "boundary_relationships": fragment["boundary_edges"],
                      "documents": [d["document_type"] for d in fragment["document_catalog"]]}, "conflicts": [],
            "fragment_preview": fragment, "approval_required": True, "automatic_learning": False}
        if digest_value(value) != preview_sha256:
            raise ValueError("lesson preview differs from the selected scope")
        return self.process.save_fragment(claim_id, **body, idempotency_key=idempotency_key)


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Parent(_Request):
    actor: str = Field(min_length=1, max_length=80)
    reason: str = Field(default="", max_length=1000)
    expected_revision: StrictInt = Field(ge=1)
    expected_state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Control(_Parent):
    action: Literal["pause", "resume"]
    expected_agent_revision: StrictInt = Field(ge=0)
    expected_agent_state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Decision(_Parent):
    question_id: str = Field(min_length=1, max_length=200)
    answer_id: str = Field(min_length=1, max_length=80)


class ApplyDecision(Decision):
    preview_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Lesson(_Parent):
    name: str = Field(min_length=1, max_length=100)
    node_ids: list[str] = Field(min_length=1, max_length=100)


class ApplyLesson(Lesson):
    preview_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class DeskStart(_Request):
    limit: StrictInt = Field(default=6, ge=1, le=20)


def create_agent_desk_router(service_getter):
    router = APIRouter(prefix="/api/claim-loops/v1/workspace")
    def invoke(fn):
        try:
            return fn(service_getter())
        except (ClaimWorkspaceError, ClaimLoopStoreError, WorkStoreError, AuthorityError, ValueError) as exc:
            raise HTTPException(404 if "does not exist" in str(exc) or "not found" in str(exc) else 409, str(exc)) from exc
    @router.get("/desk")
    def desk():
        return invoke(lambda s: s.desk())
    @router.post("/desk/start", status_code=202)
    def start(body: DeskStart, request: Request, key: Annotated[str, Depends(_idempotency_key)]):
        from urllib.parse import urlsplit
        if request.headers.get("X-CasePath-Agent-Work") != "1":
            raise HTTPException(403, "Explicit same-origin work request required")
        origin = request.headers.get("origin")
        if origin and (urlsplit(origin).netloc != request.url.netloc or urlsplit(origin).scheme != request.url.scheme):
            raise HTTPException(403, "Cross-origin work requests are not accepted")
        return invoke(lambda s: s.start(**body.model_dump(), idempotency_key=key))
    @router.get("/claims/{claim_id}/agent")
    def agent(claim_id: str):
        return invoke(lambda s: s.claim(claim_id))
    @router.post("/claims/{claim_id}/agent/control")
    def control(claim_id: str, body: Control, key: Annotated[str, Depends(_idempotency_key)]):
        return invoke(lambda s: s.control(claim_id, **body.model_dump(), idempotency_key=key))
    @router.post("/claims/{claim_id}/agent/decisions/preview")
    def preview(claim_id: str, body: Decision):
        return invoke(lambda s: s.preview_decision(claim_id, **body.model_dump()))
    @router.post("/claims/{claim_id}/agent/decisions/apply")
    def apply(claim_id: str, body: ApplyDecision, key: Annotated[str, Depends(_idempotency_key)]):
        return invoke(lambda s: s.apply_decision(claim_id, **body.model_dump(), idempotency_key=key))
    @router.post("/claims/{claim_id}/agent/lessons/preview")
    def preview_lesson(claim_id: str, body: Lesson):
        return invoke(lambda s: s.preview_lesson(claim_id, **body.model_dump()))
    @router.post("/claims/{claim_id}/agent/lessons/apply")
    def apply_lesson(claim_id: str, body: ApplyLesson, key: Annotated[str, Depends(_idempotency_key)]):
        return invoke(lambda s: s.apply_lesson(claim_id, **body.model_dump(), idempotency_key=key))
    return router
