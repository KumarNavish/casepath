"""Provider-neutral work products. These records do not replace claim authority."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

VERSION = "casepath.agent-work/1.0.0"
MAX_EVENT_BYTES = 128_000


class Role(StrEnum):
    FACTS = "canonical_facts"
    ORCHESTRATION = "orchestrator_plan"
    SOURCES = "document_source_integrity"
    PROCESS = "process_decision_mapping"
    EVIDENCE = "evidence_checklist"
    AUDIT = "final_claim_brief_audit"


ROLE_ORDER = tuple(Role)
ROLE_LABELS = dict(zip(ROLE_ORDER, ("Facts", "Orchestration", "Source integrity", "Process", "Evidence", "Audit / readiness")))


class Operation(StrEnum):
    RUN_QUEUED = "RUN_QUEUED"
    RUN_STARTED = "RUN_STARTED"
    RUN_COMPLETED = "RUN_COMPLETED"
    RUN_INTERRUPTED = "RUN_INTERRUPTED"
    RUN_BLOCKED = "RUN_BLOCKED"
    RUN_FAILED = "RUN_FAILED"
    AGENT_STARTED = "AGENT_STARTED"
    AGENT_COMPLETED = "AGENT_COMPLETED"
    AGENT_BLOCKED = "AGENT_BLOCKED"
    SOURCE_LISTED = "SOURCE_LISTED"
    SOURCE_OPENED = "SOURCE_OPENED"
    SOURCE_SPAN_SELECTED = "SOURCE_SPAN_SELECTED"
    ASSERTION_PROPOSED = "ASSERTION_PROPOSED"
    ASSERTION_REVISED = "ASSERTION_REVISED"
    CONTRADICTION_FOUND = "CONTRADICTION_FOUND"
    WORK_PRODUCT_RECORDED = "WORK_PRODUCT_RECORDED"
    PLAN_PROPOSED = "PLAN_PROPOSED"
    PROCESS_INSPECTED = "PROCESS_INSPECTED"
    PROCESS_NODE_PROPOSED = "PROCESS_NODE_PROPOSED"
    BRANCH_PROPOSED = "BRANCH_PROPOSED"
    BRANCH_REJECTED = "BRANCH_REJECTED"
    BRANCH_ACTIVATED = "BRANCH_ACTIVATED"
    OBLIGATION_PROPOSED = "OBLIGATION_PROPOSED"
    DOCUMENT_REQUIREMENT_PROPOSED = "DOCUMENT_REQUIREMENT_PROPOSED"
    DOCUMENT_STATE_CHANGED = "DOCUMENT_STATE_CHANGED"
    SOURCE_LINK_ADDED = "SOURCE_LINK_ADDED"
    ACTION_PROPOSED = "ACTION_PROPOSED"
    GATE_ACCEPTED = "GATE_ACCEPTED"
    GATE_REJECTED = "GATE_REJECTED"
    HANDOFF_STARTED = "HANDOFF_STARTED"
    HANDOFF_COMPLETED = "HANDOFF_COMPLETED"
    CLAIM_REPLANNED = "CLAIM_REPLANNED"
    AUTHORITY_CALL_STARTED = "AUTHORITY_CALL_STARTED"
    AUTHORITY_CONFIRMED = "AUTHORITY_CONFIRMED"
    PROVIDER_REQUEST_STARTED = "PROVIDER_REQUEST_STARTED"
    PROVIDER_RESPONSE_RECEIVED = "PROVIDER_RESPONSE_RECEIVED"
    PROVIDER_OUTCOME_UNKNOWN = "PROVIDER_OUTCOME_UNKNOWN"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return sha256(canonical(value)).hexdigest()


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class SourceSpan(StrictModel):
    source_id: str = Field(min_length=1, max_length=180)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    text_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    start: int = Field(ge=0, strict=True)
    end: int = Field(ge=1, strict=True)
    quote: str = Field(min_length=1, max_length=4000)
    extraction: Literal["message_body", "utf8", "pdf_text", "office_text", "image_metadata"]
    scope: Literal["source_statement_not_established_fact"] = "source_statement_not_established_fact"

    @model_validator(mode="after")
    def span_length(self):
        if self.end - self.start != len(self.quote):
            raise ValueError("span offsets must count Unicode code points in the exact extraction")
        return self


class GateResult(StrictModel):
    gate_id: str = Field(min_length=1, max_length=100)
    accepted: bool = Field(strict=True)
    scope: Literal["exact_source_link", "existing_authority_match", "work_contract", "authority_unchanged"]
    reason: str = Field(min_length=1, max_length=500)
    authority_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class WorkEvent(StrictModel):
    contract: Literal[VERSION] = VERSION
    claim_id: str = Field(min_length=1, max_length=180)
    run_id: str = Field(pattern=r"^work\.[a-f0-9]{32}$")
    sequence: int = Field(ge=1, strict=True)
    role: Role | None = None
    operation: Operation
    object_kind: str = Field(min_length=1, max_length=60)
    object_id: str = Field(min_length=1, max_length=240)
    status: Literal["queued", "started", "observed", "proposed", "accepted", "rejected", "completed", "blocked", "unknown"]
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    sources: tuple[SourceSpan, ...] = ()
    links: tuple[str, ...] = ()
    parent_event: int | None = Field(default=None, ge=1, strict=True)
    timestamp: str
    gate: GateResult | None = None
    message: str = Field(min_length=1, max_length=500)
    worker_kind: Literal["reference", "external", "kernel"]
    previous_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    event_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("timestamp")
    @classmethod
    def zoned_timestamp(cls, value):
        if datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is None:
            raise ValueError("timestamp requires a timezone")
        return value

    @model_validator(mode="after")
    def identity(self):
        body = self.model_dump(mode="json", exclude={"event_sha256"})
        if len(canonical(body)) > MAX_EVENT_BYTES or digest(body) != self.event_sha256:
            raise ValueError("event content identity differs")
        if self.parent_event is not None and self.parent_event >= self.sequence:
            raise ValueError("an event cannot depend on its future")
        if self.operation in {Operation.GATE_ACCEPTED, Operation.GATE_REJECTED}:
            if self.gate is None or self.gate.accepted != (self.operation == Operation.GATE_ACCEPTED):
                raise ValueError("gate event differs from gate result")
        if self.operation == Operation.SOURCE_SPAN_SELECTED and not self.sources:
            raise ValueError("selected source span is absent")
        operation, after = self.operation, self.after or {}
        if operation not in {Operation.RUN_QUEUED, Operation.RUN_STARTED, Operation.RUN_COMPLETED,
                             Operation.RUN_BLOCKED, Operation.RUN_FAILED, Operation.RUN_INTERRUPTED} and self.role is None:
            raise ValueError("semantic work requires one of the six roles")
        if operation in {Operation.AGENT_STARTED, Operation.AGENT_COMPLETED, Operation.AGENT_BLOCKED}:
            if self.object_id != self.role.value:
                raise ValueError("role event identity differs")
        if operation == Operation.SOURCE_OPENED:
            required = {"source_id","source_sha256","text_sha256","extraction","complete","filename","media_type"}
            if set(after)!=required or after["source_id"] != self.object_id or type(after["complete"]) is not bool:
                raise ValueError("opened-source event lacks its typed read result")
            for key in ("source_sha256","text_sha256"):
                if not isinstance(after[key],str) or len(after[key])!=64 or set(after[key])-set("0123456789abcdef"):
                    raise ValueError("opened source has invalid identity")
        if operation in {Operation.ASSERTION_PROPOSED,Operation.ASSERTION_REVISED}:
            if set(after)!={"assertion_id","text","status","source","span_id"} or after["status"]!="reported":
                raise ValueError("assertion event must be an exact reported statement")
            source=SourceSpan.model_validate(after["source"])
            if after["text"] != source.quote or tuple(self.sources)!=(source,) or self.object_id!="assertion:"+after["assertion_id"]:
                raise ValueError("assertion and its exact source differ")
        if operation == Operation.PLAN_PROPOSED and after.get("roles") != [r.value for r in ROLE_ORDER]:
            raise ValueError("plan must use exactly the six existing roles")
        if operation == Operation.PROCESS_NODE_PROPOSED:
            if not isinstance(after.get("node_id"),str) or self.object_id!="node:"+after["node_id"]:
                raise ValueError("process node identity differs")
        if operation in {Operation.OBLIGATION_PROPOSED, Operation.DOCUMENT_REQUIREMENT_PROPOSED, Operation.DOCUMENT_STATE_CHANGED}:
            if (after.get("evidence_class") not in {"received","missing","insufficient","conditional","irrelevant","unknown"}
                    or type(after.get("mandatory_now")) is not bool or not after.get("evidence_item_id")):
                raise ValueError("evidence event lacks the typed authoritative state")
        if operation == Operation.WORK_PRODUCT_RECORDED:
            if set(after)!={"value","value_sha256"} or not isinstance(after["value"],dict) or digest(after["value"])!=after["value_sha256"]:
                raise ValueError("persisted work product has invalid content identity")
        if operation == Operation.CONTRADICTION_FOUND and after.get("status")!="potential_conflict_requires_review":
            raise ValueError("conflict flags cannot certify an unsupported contradiction")
        return self


class Empty(StrictModel):
    pass


class OpenSource(StrictModel):
    source_id: str = Field(min_length=1, max_length=180)


class SelectSpan(StrictModel):
    source_id: str = Field(min_length=1, max_length=180)
    start: int = Field(ge=0, strict=True)
    end: int = Field(ge=1, strict=True)
    quote: str = Field(min_length=1, max_length=4000)


class Assertion(StrictModel):
    assertion_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,100}$")
    span_id: str = Field(min_length=1, max_length=160)
    text: str = Field(min_length=1, max_length=4000)
    status: Literal["reported"] = "reported"


class Revision(Assertion):
    previous_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class Conflict(StrictModel):
    left_id: str = Field(min_length=1, max_length=100)
    right_id: str = Field(min_length=1, max_length=100)
    label: Literal["potential_conflict_requires_review"] = "potential_conflict_requires_review"


class ObjectProposal(StrictModel):
    object_id: str = Field(min_length=1, max_length=240)


class LinkProposal(StrictModel):
    requirement_id: str = Field(min_length=1, max_length=240)
    process_node_id: str = Field(min_length=1, max_length=240)


TOOL_MODELS = {
    "read_customer_message": Empty,
    "list_sources": Empty,
    "open_source": OpenSource,
    "select_source_span": SelectSpan,
    "propose_assertion": Assertion,
    "revise_assertion": Revision,
    "flag_conflict": Conflict,
    "plan_handoffs": Empty,
    "verify_source_links": Empty,
    "prepare_handling_process": Empty,
    "inspect_process": Empty,
    "propose_process_node": ObjectProposal,
    "propose_branch": ObjectProposal,
    "inspect_evidence_state": Empty,
    "propose_evidence_requirement": ObjectProposal,
    "propose_document_requirement": ObjectProposal,
    "link_requirement_to_source": LinkProposal,
    "propose_next_action": Empty,
    "audit_readiness": Empty,
    "finish_work": Empty,
}
COMMON = {"list_sources", "open_source", "select_source_span", "finish_work"}
ROLE_TOOLS = {
    Role.FACTS: COMMON | {"read_customer_message", "propose_assertion", "revise_assertion", "flag_conflict"},
    Role.ORCHESTRATION: COMMON | {"plan_handoffs"},
    Role.SOURCES: COMMON | {"verify_source_links"},
    Role.PROCESS: COMMON | {"prepare_handling_process", "inspect_process", "propose_process_node", "propose_branch"},
    Role.EVIDENCE: COMMON | {"inspect_process", "inspect_evidence_state", "propose_evidence_requirement", "propose_document_requirement", "link_requirement_to_source"},
    Role.AUDIT: COMMON | {"inspect_process", "inspect_evidence_state", "audit_readiness", "propose_next_action"},
}
TOOL_DESCRIPTION = {
    "read_customer_message": "Read the exact customer message text and its source identity. A report is not an established fact.",
    "list_sources": "List the original claim packet's sources. This does not open any source.",
    "open_source": "Open a source from this claim. Returns exact bounded text, its hash, and its extraction scope.",
    "select_source_span": "Select an exact verbatim substring in a source already opened. Offsets count Unicode code points.",
    "propose_assertion": "Propose the exact selected quotation as a reported assertion. Text must equal the selected span. No legal conclusion is admitted.",
    "revise_assertion": "Replace a reported quotation using an exact new span and the current assertion hash.",
    "flag_conflict": "Flag two different reported assertions for review, without establishing which is true.",
    "finish_work": "Complete this role only after its required work products pass the deterministic contract.",
}


def tool_definitions(role: Role) -> list[dict[str, Any]]:
    return [{"type": "function", "function": {"name": name,
             "description": TOOL_DESCRIPTION.get(name, name.replace("_", " ").capitalize() + " through the existing authority."),
             "parameters": TOOL_MODELS[name].model_json_schema()}}
            for name in sorted(ROLE_TOOLS[role])]
