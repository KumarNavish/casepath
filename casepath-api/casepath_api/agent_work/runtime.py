"""Six-role execution through one tool dispatcher and persisted work contract.

External workers see the same role-scoped tools as the reference worker. A tool
result is not authoritative claim truth: existing CasePath gates still own it.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any
import re
import uuid

from pydantic import ValidationError

from .authority import ClaimAuthority, AuthorityError, SourceChanged
from . import evidential_channel
from .contracts import (Role, ROLE_ORDER, ROLE_LABELS, Operation, SourceSpan, GateResult,
                        TOOL_MODELS, ROLE_TOOLS, canonical, digest)
from .store import WorkStore, WorkStoreError, ConflictError, ReconciliationRequired, WorkCancelled



def _source_ref_candidates(source: dict) -> str:
    """The claim loop's own source-ref digest for one listed source."""
    from casepath_api.claim_loop import digest_value
    return "source-ref." + digest_value(dict(source))

class GateRejected(ValueError):
    pass


class WorkBlocked(RuntimeError):
    pass


class ToolRuntime:
    def __init__(self, store: WorkStore, authority: ClaimAuthority, run_id: str, owner: str, role: Role, worker_kind="reference"):
        self.store, self.authority = store, authority
        self.run_id, self.owner, self.role, self.worker_kind = run_id, owner, role, worker_kind
        self.run = store.get_run(run_id)
        self.claim_id = self.run["claim_id"]
        self.context = self.run["request"]["context"]
        started = [e for e in store.events(run_id) if e["role"]==role.value and e["operation"]=="AGENT_STARTED"]
        self.parent_event = started[-1]["sequence"] if started else None
        self.emitted: list[dict] = []
        self.changed: list[dict] = []

    def _event(self, operation, kind, object_id, message, *, status="observed", before=None, after=None, sources=(), links=(), gate=None):
        self.emitted.append(dict(role=self.role.value, operation=operation.value, object_kind=kind, object_id=object_id,
                                 status=status, message=message, before=before, after=after,
                                 sources=[s.model_dump(mode="json") if isinstance(s, SourceSpan) else s for s in sources],
                                 links=list(links), worker_kind=self.worker_kind, parent_event=self.parent_event,
                                 gate=gate.model_dump(mode="json") if isinstance(gate, GateResult) else gate))

    def _put(self, kind, object_id, value):
        self.changed.append({"id": object_id, "kind": kind, "value": value})

    def _get(self, object_id):
        changed = next((o for o in reversed(self.changed) if o["id"] == object_id), None)
        if changed:
            return changed["value"]
        try:
            return self.store.object(self.run_id, object_id)["value"]
        except WorkStoreError as exc:
            if str(exc) == "work object is unavailable":
                raise GateRejected("the referenced work product is unavailable") from exc
            raise

    def _all(self, kind):
        return self.store.objects(self.run_id, kind)

    def _gate(self, object_id, accepted, scope, reason, authority_hash=None):
        gate = GateResult(gate_id=scope, accepted=accepted, scope=scope, reason=reason, authority_sha256=authority_hash)
        self._event(Operation.GATE_ACCEPTED if accepted else Operation.GATE_REJECTED, "gate", object_id,
                    reason, status="accepted" if accepted else "rejected", gate=gate)

    def call(self, name: str, arguments: dict, call_id: str) -> dict:
        """One call identity has one result. Neither worker can invoke arbitrary code."""
        if not isinstance(arguments, dict) or len(canonical(arguments)) > 32_000:
            raise WorkBlocked("tool arguments exceed the bounded contract")
        existing = self.store.begin_call(self.run_id, self.owner, self.role, call_id, name, arguments)
        if existing is not None:
            return existing
        self.emitted, self.changed = [], []
        try:
            # Exact calls returned above are replay, not new post-completion work.
            if any(o["value"]["role"] == self.role.value for o in self._all("role_completion")):
                raise GateRejected("this role has completed; new work requires a new review")
            if name not in ROLE_TOOLS[self.role]:
                raise GateRejected("this role is not permitted to use the requested tool")
            parsed = TOOL_MODELS[name].model_validate(arguments)
            handler = getattr(self, "_tool_" + name, None)
            if handler is None:
                raise GateRejected("tool implementation is unavailable")
            output = handler(parsed)
            response = {"ok": True, "tool": name, "result": output}
        except (GateRejected, ValidationError, SourceChanged, AuthorityError) as exc:
            # Do not persist provider prose, hidden reasoning, unexpected fields,
            # or raw validation dumps (which may contain sensitive arguments).
            reason = "The proposal does not satisfy the typed tool schema." if isinstance(exc, ValidationError) else str(exc)
            self.changed = []
            self._gate("call:" + call_id, False, "work_contract", reason[:450])
            response = {"ok": False, "tool": name, "error": reason[:450], "claim_state_changed": None if name == "prepare_handling_process" else False,
                        "requires_reconciliation": name == "prepare_handling_process"}
        # An unknown exception is not converted to 'no state change'. The pending
        # call remains unfinished and the run requires explicit reconciliation.
        return self.store.complete_call(self.run_id, self.owner, self.role, call_id, response, self.emitted, self.changed)

    def _check_packet(self):
        now = self.authority.context(self.claim_id)
        if now["binding_sha256"] != self.context["binding_sha256"] or now["source_roster_sha256"] != self.context["source_roster_sha256"]:
            raise SourceChanged("the incoming packet changed; existing work is not current")
        return now

    def _read(self, source_id):
        self._check_packet()
        source = self.authority.read_source(self.claim_id, source_id)
        if source.get("claim_id") != self.claim_id:
            raise SourceChanged("opened source belongs to another claim")
        if sha256(source["text"].encode()).hexdigest() != source["text_sha256"]:
            raise SourceChanged("source text no longer matches its extraction hash")
        self._put("opened_source", "source:" + source_id, source)
        self._event(Operation.SOURCE_OPENED, "source", source_id,
                    "Opened " + source["filename"][:300], after={k: source[k] for k in ("source_id", "source_sha256", "text_sha256", "extraction", "complete", "filename", "media_type")})
        return source

    def _tool_list_sources(self, args):
        self._check_packet()
        sources = self.authority.list_sources(self.claim_id)
        self._event(Operation.SOURCE_LISTED, "packet", self.claim_id, f"Listed {len(sources)} original sources", after={"count": len(sources)})
        return {"sources": sources}

    def _tool_read_customer_message(self, args):
        sources = self.authority.list_sources(self.claim_id)
        message = next((s for s in sources if s["role"] == "customer_message"), None)
        if message is None:
            raise GateRejected("the incoming message is unavailable")
        return self._read(message["source_id"])

    def _tool_open_source(self, args):
        return self._read(args.source_id)

    def _tool_select_source_span(self, args):
        self._check_packet()
        try:
            source = self._get("source:" + args.source_id)
        except WorkStoreError as exc:
            raise GateRejected("open the source before selecting a span") from exc
        text = source["text"]
        if not args.quote.strip():
            raise GateRejected("the selected quotation is not the exact source substring")
        start, end, canonicalized = args.start, args.end, False
        if end > len(text) or text[start:end] != args.quote:
            found = text.find(args.quote)
            if found < 0 or text.find(args.quote, found + 1) >= 0:
                raise GateRejected("the selected quotation is not one unique exact source substring")
            start, end, canonicalized = found, found + len(args.quote), True
        span = SourceSpan(source_id=args.source_id, source_sha256=source["source_sha256"], text_sha256=source["text_sha256"],
                          start=start, end=end, quote=args.quote, extraction=source["extraction"])
        span_id = "span:" + digest(span.model_dump(mode="json"))
        self._put("span", span_id, span.model_dump(mode="json"))
        self._event(Operation.SOURCE_SPAN_SELECTED, "span", span_id, "Selected an exact source passage", sources=[span],
                    after={"source_id": args.source_id, "start": start, "end": end, "offsets_canonicalized": canonicalized}, links=["source:" + args.source_id])
        return {"span_id": span_id, "source": span.model_dump(mode="json"), "offsets_canonicalized": canonicalized}

    def _assertion(self, args, revise=False):
        self._check_packet()
        try:
            span = SourceSpan.model_validate(self._get(args.span_id))
        except (ValueError, WorkStoreError) as exc:
            raise GateRejected("the referenced source span is unavailable") from exc
        if args.text != span.quote:
            raise GateRejected("this bounded facts role admits only the verbatim reported statement, not a paraphrase or conclusion")
        object_id = "assertion:" + args.assertion_id
        before = None
        if revise:
            previous = self.store.object(self.run_id, object_id)
            if previous["sha256"] != args.previous_sha256:
                raise GateRejected("the assertion changed before revision")
            before = previous["value"]
        else:
            if any(o["id"] == object_id for o in self._all("assertion")):
                raise GateRejected("use the revision tool for an existing assertion")
        value = {"assertion_id": args.assertion_id, "text": args.text, "status": "reported", "source": span.model_dump(mode="json"), "span_id": args.span_id}
        self._event(Operation.ASSERTION_REVISED if revise else Operation.ASSERTION_PROPOSED, "assertion", object_id,
                    "Recorded a source statement, not an established fact", status="proposed", before=before, after=value,
                    sources=[span], links=[args.span_id])
        self._gate(object_id, True, "exact_source_link", "Quotation and source locator match. Factual and legal truth are not certified.")
        self._put("assertion", object_id, value)
        return {"object_id": object_id, "sha256": digest(value), "status": "reported"}

    def _tool_propose_assertion(self, args):
        return self._assertion(args)

    def _tool_revise_assertion(self, args):
        return self._assertion(args, revise=True)

    def _tool_flag_conflict(self, args):
        if args.left_id == args.right_id:
            raise GateRejected("two distinct statements are required")
        left, right = self._get("assertion:" + args.left_id), self._get("assertion:" + args.right_id)
        value = {"left_id": args.left_id, "right_id": args.right_id, "status": args.label}
        object_id = "conflict:" + digest(value)
        self._event(Operation.CONTRADICTION_FOUND, "potential_conflict", object_id, "Two statements flagged for review; no contradiction is certified",
                    status="proposed", after=value, sources=[left["source"], right["source"]], links=["assertion:" + args.left_id, "assertion:" + args.right_id])
        self._put("potential_conflict", object_id, value)
        return value

    def _tool_plan_handoffs(self, args):
        assertions = self._all("assertion")
        if not assertions:
            raise GateRejected("there is no accepted source statement to hand off")
        value = {"roles": [r.value for r in ROLE_ORDER], "input_assertions": [o["id"] for o in assertions],
                 "dependency": "source integrity before process mapping; process before evidence; audit last"}
        self._event(Operation.PLAN_PROPOSED, "plan", "execution_plan", "Planned source checking, process mapping, evidence planning, and final audit",
                    status="accepted", after=value, links=value["input_assertions"])
        self._put("plan", "execution_plan", value)
        return value

    def _tool_verify_source_links(self, args):
        assertions = self._all("assertion")
        opened = {}
        for obj in assertions:
            span = SourceSpan.model_validate(obj["value"]["source"])
            source = opened.get(span.source_id)
            if source is None:
                source = opened[span.source_id] = self._read(span.source_id)
            if source["source_sha256"] != span.source_sha256 or source["text_sha256"] != span.text_sha256 or source["text"][span.start:span.end] != span.quote:
                raise SourceChanged("source support changed during the integrity check")
            self._gate(obj["id"], True, "exact_source_link", "Exact quote, original-file hash, and extraction offsets were checked again.")
        value = {"checked_assertions": [o["id"] for o in assertions],
                 "assertion_hashes": {o["id"]: o["sha256"] for o in assertions},
                 "source_count": len(opened), "factual_truth_certified": False}
        self._put("source_check", "source_integrity", value)
        return value

    def _tool_prepare_handling_process(self, args):
        self._get("execution_plan")
        integrity = self._get("source_integrity")
        if not integrity["checked_assertions"]:
            raise GateRejected("source checking has not completed")
        # Write an intent before calling the unchanged authoritative service.
        self.store.append(self.run_id, self.owner, role=self.role.value, operation=Operation.AUTHORITY_CALL_STARTED,
                          object_kind="authority", object_id="prepare", status="started", message="Requested existing gated handling-process setup",
                          worker_kind=self.worker_kind, parent_event=self.parent_event, after={"idempotency_prefix": self.run_id, "expected_context": self.context})
        prepared = self.authority.prepare(self.claim_id, self.run_id, self.context)
        snapshot = self.authority.snapshot(self.claim_id)
        if prepared["state_sha256"] != snapshot["state_sha256"]:
            raise SourceChanged("process setup did not match its confirmed state")
        self._put("authority_snapshot", "authority_snapshot", snapshot)
        self._event(Operation.AUTHORITY_CONFIRMED, "authority", "prepare", "Existing CasePath gates confirmed the handling state",
                    status="accepted", after={"state_sha256": snapshot["state_sha256"], "revision": snapshot["revision"], "setup_changed": prepared["setup_changed"]})
        self._gate("authority_snapshot", True, "existing_authority_match", "The process is the accepted existing CasePath state, not browser-authored truth.", snapshot["state_sha256"])
        if prepared["setup_changed"]:
            self._event(Operation.CLAIM_REPLANNED, "claim_state", self.claim_id, "Handling process and initial evidence requirements were established",
                        status="observed", before=prepared["before_context"], after={"state_sha256": snapshot["state_sha256"], "readiness": snapshot["readiness"]})
        # A later run can observe a genuine state change made through the
        # original evidence/correction path. This does not claim this worker
        # caused that earlier change or invent its commit time.
        for previous in self.store.list_runs(self.claim_id, 150):
            if previous["run_id"]==self.run_id or previous["status"]!="completed":
                continue
            old = next((o["value"] for o in self.store.objects(previous["run_id"],"authority_snapshot")), None)
            if old and old["state_sha256"] != snapshot["state_sha256"]:
                self._event(Operation.CLAIM_REPLANNED,"observed_claim_change",self.claim_id,
                            "Observed an authoritative claim change since the previous review", status="observed",
                            before={"run_id":previous["run_id"],"state_sha256":old["state_sha256"],"readiness":old["readiness"]},
                            after={"state_sha256":snapshot["state_sha256"],"readiness":snapshot["readiness"],"caused_by_this_worker":False})
                previous_items={i["evidence_item_id"]:i for i in old["evidence"]}
                for item in snapshot["evidence"]:
                    prior=previous_items.get(item["evidence_item_id"])
                    if prior and any(prior.get(k)!=item.get(k) for k in ("evidence_class","mandatory_now","current_path")):
                        self._event(Operation.DOCUMENT_STATE_CHANGED,"observed_evidence_change","obligation:"+item["evidence_item_id"],
                                    "Observed changed evidence state: "+str(item.get("title",item["evidence_item_id"]))[:260],
                                    before=prior,after={**item,"caused_by_this_worker":False})
            break
        return {"state_sha256": snapshot["state_sha256"], "revision": snapshot["revision"], "setup_changed": prepared["setup_changed"],
                "nodes": [{"node_id": n["node_id"], "title": n.get("title")} for n in snapshot["process"]["nodes"]],
                "branches": [{"object_id": b["object_id"], "state": b.get("state")} for b in snapshot["branches"]]}

    def _snapshot(self):
        snapshot = getattr(self, "_accepted_snapshot", None)
        if snapshot is None:
            snapshot = self._get("authority_snapshot")
            self._accepted_snapshot = snapshot
        current = getattr(self.authority, "snapshot_is_current", None)
        unchanged = current(self.claim_id, snapshot["state_sha256"]) if current else (
            self.authority.snapshot(self.claim_id)["state_sha256"] == snapshot["state_sha256"]
        )
        if not unchanged:
            raise SourceChanged("the claim changed after the process snapshot")
        return snapshot

    def _tool_inspect_process(self, args):
        snapshot = self._snapshot()
        self._event(Operation.PROCESS_INSPECTED, "process", "process", "Inspected the current authoritative handling graph",
                    after={"state_sha256": snapshot["state_sha256"], "node_count": len(snapshot["process"]["nodes"])})
        return {"nodes": snapshot["process"]["nodes"], "branches": snapshot["branches"], "current_overlay": snapshot["process"].get("current_overlay", {})}

    def _tool_propose_process_node(self, args):
        snapshot = self._snapshot()
        node = next((n for n in snapshot["process"]["nodes"] if n["node_id"] == args.object_id), None)
        if node is None:
            raise GateRejected("the node is not admitted by the existing process authority")
        self._event(Operation.PROCESS_NODE_PROPOSED, "process_node", "node:" + args.object_id,
                    "Mapped process step: " + str(node.get("title", args.object_id))[:300], status="proposed", after=node)
        self._gate("node:" + args.object_id, True, "existing_authority_match", "The node matches the existing accepted process object.", snapshot["state_sha256"])
        self._put("process_node", "node:" + args.object_id, node)
        return {"object_id": "node:" + args.object_id, "node": node}

    def _tool_propose_branch(self, args):
        snapshot = self._snapshot()
        branch = next((b for b in snapshot["branches"] if b["object_id"] == args.object_id), None)
        if branch is None:
            raise GateRejected("the branch is not admitted by the existing process authority")
        source = "node:" + branch["from_node_id"]
        self._get(source)
        self._event(Operation.BRANCH_PROPOSED, "branch", "branch:" + args.object_id, "Mapped a conditional handling path",
                    status="proposed", after=branch, links=[source])
        self._gate("branch:" + args.object_id, True, "existing_authority_match", "The branch and its state match the existing handling graph.", snapshot["state_sha256"])
        if branch.get("state") == "selected":
            self._event(Operation.BRANCH_ACTIVATED, "branch", "branch:" + args.object_id, "This branch is the current authoritative path", status="observed", after=branch, links=[source])
        if branch.get("state") == "rejected":
            self._event(Operation.BRANCH_REJECTED, "branch", "branch:" + args.object_id, "The existing authority explicitly rejected this branch", status="observed", after=branch, links=[source])
        self._put("branch", "branch:" + args.object_id, branch)
        return branch

    def _tool_inspect_evidence_state(self, args):
        snapshot = self._snapshot()
        self._event(Operation.PROCESS_INSPECTED, "evidence_state", "evidence_state", "Inspected process-derived evidence requirements",
                    after={"pending_evidence_count": snapshot["readiness"]["pending_evidence_count"]})
        return {"requirements": snapshot["evidence"], "checklist": snapshot["checklist"]}

    def _evidence(self, object_id):
        snapshot = self._snapshot()
        item = next((i for i in snapshot["evidence"] if i["evidence_item_id"] == object_id), None)
        if item is None:
            raise GateRejected("the requirement is not present in the authoritative evidence state")
        raw = next((i for i in snapshot["checklist"] if i["item_id"] == object_id), {})
        nodes = [n for n in (raw.get("node_ids") or [raw.get("node_id")]) if n]
        return snapshot, {**item, "process_node_ids": nodes, "why": raw.get("why"), "legal_basis_ids": raw.get("legal_basis_ids", [])}

    def _tool_propose_evidence_requirement(self, args):
        snapshot, item = self._evidence(args.object_id)
        for node in item["process_node_ids"]:
            self._get("node:" + node)
        self._event(Operation.OBLIGATION_PROPOSED, "obligation", "obligation:" + args.object_id,
                    "Mapped evidence need: " + str(item.get("title", args.object_id))[:300], status="proposed", after=item,
                    links=["node:" + n for n in item["process_node_ids"]])
        self._gate("obligation:" + args.object_id, True, "existing_authority_match", "The requirement and timing match the current process-dependent checklist.", snapshot["state_sha256"])
        self._put("obligation", "obligation:" + args.object_id, item)
        return item

    def _requirement_source_ids(self, requirement_id):
        """The sources THIS requirement's accepted evidence actually cites.

        The obligation carries source-ref digests rather than source ids, so the ids are recovered by
        recomputing the claim loop's own ref digest over each source the authority lists for this claim.
        """
        try:
            item = self._get("obligation:" + requirement_id)
        except WorkStoreError:
            return set()
        refs = {r for r in (item.get("source_ref_ids") or ()) if isinstance(r, str)}
        if not refs:
            return set()
        wanted = set()
        try:
            for source in self.authority.list_sources(self.claim_id):
                sid = source.get("source_id")
                if sid and {_source_ref_candidates(source)} & refs:
                    wanted.add(sid)
        except Exception:
            return set()
        return wanted

    def _requirement_spans(self, requirement_id):
        """Only the spans evidentially tied to THIS requirement.

        This used to return every span the run had selected, so one returned artifact anywhere could lift
        the cap on every requirement in the claim — a run-level shortcut the research method never had. The
        rule is per requirement: a receipt may rest only on evidence cited by that requirement. When the
        tie cannot be established the spans are treated as absent, which caps rather than admits.
        """
        wanted = self._requirement_source_ids(requirement_id)
        if not wanted:
            return []
        return [obj["value"] for obj in self._all("span")
                if obj["value"].get("source_id") in wanted]

    def _channel_gate(self, object_id, item):
        """Cap a receipt by the channel of the evidence supporting it (see evidential_channel)."""
        proposed = item.get("evidence_class")
        decision = evidential_channel.gate_evidence_class(proposed, self._requirement_spans(object_id))
        if not decision["capped"]:
            return item, decision
        self._gate("document:" + object_id, False, "exact_source_link", decision["reason"][:500])
        return {**item, "evidence_class": decision["final_class"],
                "evidential_channel_gate": {k: decision[k] for k in ("proposed_class", "final_class", "support_channels", "reason")}}, decision

    def _tool_propose_document_requirement(self, args):
        item = self._get("obligation:" + args.object_id)
        item, decision = self._channel_gate(args.object_id, item)
        self._event(Operation.DOCUMENT_REQUIREMENT_PROPOSED, "document_requirement", "document:" + args.object_id,
                    "Recorded the existing evidence request and when it is needed", status="accepted", after=item,
                    links=["obligation:" + args.object_id])
        self._put("document_requirement", "document:" + args.object_id, item)
        return item

    def _tool_link_requirement_to_source(self, args):
        item = self._get("obligation:" + args.requirement_id)
        if args.process_node_id not in item["process_node_ids"]:
            raise GateRejected("this source/process linkage is absent from the accepted checklist")
        node = self._get("node:" + args.process_node_id)
        value = {"requirement_id": args.requirement_id, "process_node_id": args.process_node_id,
                 "relation": "required_by_process", "source_ref_ids": item.get("source_ref_ids", []),
                 "rule_ids": item["legal_basis_ids"], "rule_explanation": item.get("why") or node.get("why"),
                 "customer_assertion_proves_requirement": False}
        object_id = "link:" + digest(value)
        self._event(Operation.SOURCE_LINK_ADDED, "process_requirement_link", object_id,
                    "Linked the requirement to its actual process decision and recorded rule references", status="accepted", after=value,
                    links=["obligation:" + args.requirement_id, "node:" + args.process_node_id])
        self._put("process_requirement_link", object_id, value)
        return value

    def _require_products(self, kind, expected):
        """Exact identities and values, not matching counts or a plausible sample."""
        actual = {obj["id"]: obj["value"] for obj in self._all(kind)}
        title = {"process_node":"process step", "branch":"handling branch", "obligation":"evidence requirement",
                 "document_requirement":"document requirement", "process_requirement_link":"process-to-evidence link"}[kind]
        if set(actual) != set(expected):
            raise GateRejected("This review has a missing or extra " + title + ". Complete the saved claim's full work roster.")
        if any(digest(actual[key]) != digest(value) for key, value in expected.items()):
            raise GateRejected("This review's " + title + " differs from the saved claim. Refresh before proceeding.")
        return len(expected)

    def _process_coverage(self, snapshot):
        return {
            "process_nodes": self._require_products("process_node", {
                "node:" + node["node_id"]: node for node in snapshot["process"]["nodes"]}),
            "branches": self._require_products("branch", {
                "branch:" + branch["object_id"]: branch for branch in snapshot["branches"]}),
        }

    def _evidence_coverage(self, snapshot):
        obligations, documents, links = {}, {}, {}
        checklist = {item["item_id"]: item for item in snapshot["checklist"]}
        nodes = {node["node_id"]: node for node in snapshot["process"]["nodes"]}
        for source in snapshot["evidence"]:
            key = source["evidence_item_id"]
            raw = checklist.get(key)
            if raw is None:
                raise GateRejected("an evidence requirement has no authoritative checklist entry")
            node_ids = [n for n in (raw.get("node_ids") or [raw.get("node_id")]) if n]
            if not node_ids or len(node_ids) != len(set(node_ids)) or any(n not in nodes for n in node_ids):
                raise GateRejected("an evidence requirement has an invalid process relationship")
            item = {**source, "process_node_ids": node_ids, "why": raw.get("why"),
                    "legal_basis_ids": raw.get("legal_basis_ids", [])}
            obligations["obligation:" + key] = item
            documents["document:" + key] = item
            for node_id in node_ids:
                value = {"requirement_id": key, "process_node_id": node_id,
                         "relation": "required_by_process", "source_ref_ids": source.get("source_ref_ids", []),
                         "rule_ids": item["legal_basis_ids"],
                         "rule_explanation": item.get("why") or nodes[node_id].get("why"),
                         "customer_assertion_proves_requirement": False}
                links["link:" + digest(value)] = value
        return {"obligations": self._require_products("obligation", obligations),
                "document_requirements": self._require_products("document_requirement", documents),
                "process_requirement_links": self._require_products("process_requirement_link", links)}

    def _source_check_coverage(self):
        check = self._get("source_integrity")
        assertions = {obj["id"]: obj["sha256"] for obj in self._all("assertion")}
        if not assertions or set(check["checked_assertions"]) != set(assertions) or check.get("assertion_hashes") != assertions:
            raise GateRejected("the source check does not cover the exact current assertions")
        return len(assertions)

    def _tool_audit_readiness(self, args):
        self._check_packet()
        snapshot = self._snapshot()
        coverage = {**self._process_coverage(snapshot), **self._evidence_coverage(snapshot)}
        coverage["source_assertions"] = self._source_check_coverage()
        source_check = self._get("source_integrity")
        unresolved = len(self._all("potential_conflict"))
        limited_sources = [o["value"]["source_id"] for o in self._all("opened_source") if not o["value"]["complete"]]
        value = {**snapshot["readiness"], "state_sha256": snapshot["state_sha256"],
                 "source_statements_checked": len(source_check["checked_assertions"]), "potential_conflicts": unresolved,
                 "authority": "existing_casepath", "work_review_needed": unresolved > 0 or bool(limited_sources),
                 "limited_source_extractions": limited_sources,
                 "claim_approval_performed": False, "work_coverage": coverage,
                 "coverage_contract": "casepath.work-coverage/1.0.0"}
        self._event(Operation.GATE_ACCEPTED, "readiness", "readiness", "Checked the assembled work against the current authoritative claim state",
                    status="accepted", after=value,
                    gate=GateResult(gate_id="authority_unchanged", accepted=True, scope="authority_unchanged",
                                    reason="The recorded state, process, and requirement roster match. This is not legal or model-quality certification.", authority_sha256=snapshot["state_sha256"]))
        self._put("readiness", "readiness", value)
        return value

    def _tool_propose_next_action(self, args):
        self._check_packet()
        snapshot = self._snapshot()
        readiness = self._get("readiness")
        if readiness["state_sha256"] != snapshot["state_sha256"]:
            raise SourceChanged("the readiness audit no longer binds the current claim")
        self._event(Operation.ACTION_PROPOSED, "next_action", "next_action", "Recorded the current safe next action; nothing was sent or settled",
                    status="accepted", after={"action": readiness["next_action"], "readiness": readiness["state"], "blocker": readiness["blocker"]},
                    links=["readiness"])
        self._put("next_action", "next_action", {"action": readiness["next_action"], "scope": readiness["scope"]})
        return {"next_action": readiness["next_action"]}

    def _tool_finish_work(self, args):
        self._check_packet()
        coverage = {}
        if self.role in (Role.PROCESS, Role.EVIDENCE, Role.AUDIT):
            snapshot = self._snapshot()
            coverage.update(self._process_coverage(snapshot))
            if self.role in (Role.EVIDENCE, Role.AUDIT):
                coverage.update(self._evidence_coverage(snapshot))
        if self.role in (Role.SOURCES, Role.AUDIT):
            coverage["source_assertions"] = self._source_check_coverage()
        requirements = {Role.FACTS: "assertion", Role.ORCHESTRATION: "plan", Role.SOURCES: "source_check",
                        Role.PROCESS: "process_node", Role.EVIDENCE: "obligation", Role.AUDIT: "readiness"}
        if not self._all(requirements[self.role]):
            raise GateRejected("the role has not produced its required checked work")
        if self.role == Role.FACTS:
            opened = {o["value"]["source_id"] for o in self._all("opened_source")}
            expected = {s["source_id"] for s in self.authority.list_sources(self.claim_id)}
            if opened != expected:
                raise GateRejected("open every source in the packet before completing the facts role")
        if self.role == Role.AUDIT:
            self._get("next_action")
        limits = [o["value"]["source_id"] for o in self._all("opened_source") if not o["value"]["complete"]] if self.role == Role.FACTS else []
        self._put("role_completion", "complete:" + self.role.value,
                  {"role": self.role.value, "required_kind": requirements[self.role],
                   "limited_source_extractions": limits, "coverage": coverage,
                   "coverage_contract": "casepath.work-coverage/1.0.0"})
        self._event(Operation.AGENT_COMPLETED, "role", self.role.value, ROLE_LABELS[self.role] + " completed its recorded work", status="completed")
        return {"role": self.role.value, "completed": True}


class ReferenceWorker:
    kind = "reference"

    def run(self, runtime: ToolRuntime):
        count = 0
        def call(tool, **args):
            nonlocal count
            count += 1
            if count > 240:
                raise WorkBlocked("reference role exceeded its tool budget")
            value = runtime.call(tool, args, "reference." + runtime.role.value + "." + str(count))
            if not value["ok"]:
                raise WorkBlocked(value["error"])
            return value["result"]
        role = runtime.role
        if role == Role.FACTS:
            roster = call("list_sources")["sources"]
            if len(roster) > 25:
                raise WorkBlocked("packet exceeds the reference role's source cap")
            for index, descriptor in enumerate(roster):
                source = call("read_customer_message") if descriptor["role"] == "customer_message" else call("open_source", source_id=descriptor["source_id"])
                text = source["text"]
                # Extract actual passages, without inferring dates, legal effect,
                # positive evidence, or causation from the wording.
                matches = list(re.finditer(r"[^\n.!?;]{35,500}(?:[.!?;]|$)", text))[:2]
                if not matches and text.strip():
                    start = len(text) - len(text.lstrip())
                    matches = [(start, min(len(text), start + 400))]
                for n, match in enumerate(matches):
                    start, end = match if isinstance(match, tuple) else match.span()
                    quote = text[start:end]
                    span = call("select_source_span", source_id=source["source_id"], start=start, end=end, quote=quote)
                    call("propose_assertion", assertion_id=f"reported.{index}.{n}", span_id=span["span_id"], text=quote, status="reported")
        elif role == Role.ORCHESTRATION:
            call("plan_handoffs")
        elif role == Role.SOURCES:
            call("verify_source_links")
        elif role == Role.PROCESS:
            process = call("prepare_handling_process")
            call("inspect_process")
            for node in process["nodes"]:
                call("propose_process_node", object_id=node["node_id"])
            for branch in process["branches"]:
                call("propose_branch", object_id=branch["object_id"])
        elif role == Role.EVIDENCE:
            evidence = call("inspect_evidence_state")
            for item in evidence["requirements"]:
                result = call("propose_evidence_requirement", object_id=item["evidence_item_id"])
                call("propose_document_requirement", object_id=item["evidence_item_id"])
                for node in result["process_node_ids"]:
                    call("link_requirement_to_source", requirement_id=item["evidence_item_id"], process_node_id=node)
        elif role == Role.AUDIT:
            call("audit_readiness")
            call("propose_next_action")
        call("finish_work")


class AgentWorkExecutor:
    def __init__(self, store: WorkStore, authority: ClaimAuthority, facts_worker=None):
        self.store, self.authority = store, authority
        self.facts_worker = facts_worker

    def execute(self, run_id):
        owner = uuid.uuid4().hex
        if not self.store.acquire(run_id, owner):
            return self.store.get_run(run_id)
        run = self.store.get_run(run_id)
        role = None
        try:
            for role in ROLE_ORDER:
                self.store.heartbeat(run_id, owner)
                completed = {o["value"]["role"] for o in self.store.objects(run_id, "role_completion")}
                if role.value in completed:
                    continue
                prior = ROLE_ORDER[ROLE_ORDER.index(role) - 1] if role != ROLE_ORDER[0] else None
                if prior and prior.value not in completed:
                    raise WorkBlocked("the upstream role has not completed")
                kind = "external" if role == Role.FACTS and run["request"]["facts_worker"] == "external_facts" else "reference"
                parent_event = self.store.events(run_id)[-1]["sequence"]
                if prior:
                    products = [{"object_id": o["id"], "sha256": o["sha256"]} for o in self.store.objects(run_id) if o["kind"] not in {"opened_source", "role_completion"}]
                    handoff = self.store.append(run_id, owner, role=prior.value, operation=Operation.HANDOFF_STARTED, object_kind="handoff",
                                               object_id=prior.value + "->" + role.value, status="started", message=ROLE_LABELS[prior] + " handed checked work to " + ROLE_LABELS[role], worker_kind="kernel",
                                               parent_event=parent_event, after={"from_role": prior.value, "to_role": role.value, "products": products})
                    accepted_handoff = self.store.append(run_id, owner, role=role.value, operation=Operation.HANDOFF_COMPLETED, object_kind="handoff",
                                      object_id=prior.value + "->" + role.value, status="completed", message="Upstream work identities were loaded and verified",
                                      worker_kind="kernel", parent_event=handoff["sequence"], after={"product_count": len(products)})
                    parent_event=accepted_handoff["sequence"]
                self.store.append(run_id, owner, role=role.value, operation=Operation.AGENT_STARTED, object_kind="role", object_id=role.value,
                                  status="started", message=ROLE_LABELS[role] + " started", worker_kind=kind, parent_event=parent_event)
                runtime = ToolRuntime(self.store, self.authority, run_id, owner, role, kind)
                if kind == "external":
                    if self.facts_worker is None:
                        raise WorkBlocked("no external facts worker is configured; no model call was made")
                    expected = run["request"].get("worker_config_sha256")
                    if not expected or digest(self.facts_worker.config.public()) != expected:
                        raise WorkBlocked("the external worker differs from the frozen run configuration")
                    self.facts_worker.run(runtime)
                else:
                    ReferenceWorker().run(runtime)
                if role in {Role.PROCESS, Role.EVIDENCE, Role.AUDIT}:
                    saved = self.store.object(run_id, "authority_snapshot")["value"]
                    if self.authority.snapshot(run["claim_id"])["state_sha256"] != saved["state_sha256"]:
                        raise SourceChanged("the claim changed during the review")
            readiness = self.store.object(run_id, "readiness")["value"]
            self.store.finish(run_id, owner, "completed", "All six roles completed. Claim readiness remains governed by the existing authority.",
                              after={"readiness": readiness, "completed_roles": [r.value for r in ROLE_ORDER]})
        except WorkCancelled:
            try:
                self.store.finish(run_id, owner, "cancelled", "Review stopped at a safe checkpoint")
            except ConflictError:
                pass
        except (WorkBlocked, GateRejected, AuthorityError, WorkStoreError, ValueError) as exc:
            try:
                if role:
                    self.store.append(run_id, owner, role=role.value, operation=Operation.AGENT_BLOCKED, object_kind="role", object_id=role.value,
                                      status="blocked", message=str(exc)[:450] if isinstance(exc, (WorkBlocked, GateRejected, AuthorityError, WorkStoreError)) else "Existing authority did not accept this operation", worker_kind="kernel")
                self.store.finish(run_id, owner, "blocked", str(exc)[:450] if isinstance(exc, (WorkBlocked, GateRejected, AuthorityError, WorkStoreError)) else "An existing authority check rejected this run; inspect the saved record.",
                                  after={"requires_reconciliation": bool(self.store.pending_calls(run_id)), "pending_calls": self.store.pending_calls(run_id)})
            except ConflictError:
                pass  # A late executor cannot overwrite a different owner.
        except BaseException as exc:
            # Preserve pending call records. An exception after an effect may
            # have an unknown outcome; do not label it a safe rejected action.
            try:
                self.store.finish(run_id, owner, "blocked", "Execution stopped with an unresolved operation. Inspect the saved work; no automatic retry.",
                                  after={"exception_type": type(exc).__name__, "outcome": "unconfirmed"})
            except ConflictError:
                pass
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
        return self.store.get_run(run_id)
