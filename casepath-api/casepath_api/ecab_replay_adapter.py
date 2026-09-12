from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from .claim_loop_contracts import EvidenceAction, FoundationModel
from .foundation.common import digest_text, digest_value, is_sha256


ECAB_FACTUAL_HISTORY_TOOL_ID = "casepath.tool.ecab-factual-history-replay/1.0.0"


class ECABReplayContractError(ValueError):
    """Raised when a future replay span crosses the neutral adapter boundary."""


class ECABFactualHistorySpanV1(FoundationModel):
    """Sanitized, outcome-free input to a future ECAB replay worker.

    This DTO deliberately contains neither adjudicative labels nor decision
    outcomes.  It is a pure wire boundary; it performs no acquisition or I/O.
    """

    contract: Literal["casepath.ecab-factual-history-span/1.0.0"] = (
        "casepath.ecab-factual-history-span/1.0.0"
    )
    event_index: int = Field(ge=0)
    previous_event_sha256: str | None
    action_id: str
    action_sha256: str
    source_id: str
    source_sha256: str
    source_version: str
    page: Literal[1] = 1
    sanitized_page_text: str
    text_start: int = Field(ge=0)
    text_end: int = Field(gt=0)
    observed_at: str
    event_sha256: str

    @model_validator(mode="after")
    def validate_span(self) -> ECABFactualHistorySpanV1:
        if not is_sha256(self.action_sha256) or not is_sha256(self.source_sha256):
            raise ValueError("replay action/source hashes must be SHA-256")
        if self.previous_event_sha256 is not None and not is_sha256(
            self.previous_event_sha256
        ):
            raise ValueError("previous replay event hash must be SHA-256")
        if (self.event_index == 0) != (self.previous_event_sha256 is None):
            raise ValueError("replay event chain boundary is invalid")
        if self.text_end > len(self.sanitized_page_text):
            raise ValueError("replay span exceeds its sanitized page")
        excerpt = self.sanitized_page_text[self.text_start : self.text_end]
        if not excerpt or not excerpt.strip():
            raise ValueError("replay span must contain non-empty sanitized text")
        payload = self.model_dump(mode="json", exclude={"event_sha256"})
        if digest_value(payload) != self.event_sha256:
            raise ValueError("replay event self-hash mismatch")
        return self


class ECABMappedReplayEventV1(FoundationModel):
    contract: Literal["casepath.ecab-mapped-replay-event/1.0.0"] = (
        "casepath.ecab-mapped-replay-event/1.0.0"
    )
    event_index: int = Field(ge=0)
    source_event_sha256: str
    action_id: str
    action_sha256: str
    source_id: str
    source_sha256: str
    source_version: str
    sanitized_content: str
    text_start: int = Field(ge=0)
    text_end: int = Field(gt=0)
    sanitized_excerpt: str = Field(min_length=1)
    span_sha256: str
    observed_at: str
    artifact_source_version: str
    artifact_page_count: Literal[1] = 1
    mapped_event_sha256: str

    @model_validator(mode="after")
    def validate_mapping(self) -> ECABMappedReplayEventV1:
        if (
            not is_sha256(self.source_event_sha256)
            or not is_sha256(self.source_sha256)
            or not is_sha256(self.span_sha256)
        ):
            raise ValueError("mapped replay source hashes must be SHA-256")
        if (
            self.source_version != self.artifact_source_version
            or self.text_end > len(self.sanitized_content)
            or self.sanitized_content[self.text_start : self.text_end]
            != self.sanitized_excerpt
            or digest_text(self.sanitized_content) != self.source_sha256
            or digest_text(self.sanitized_excerpt) != self.span_sha256
        ):
            raise ValueError("mapped replay span binding is invalid")
        payload = self.model_dump(mode="json", exclude={"mapped_event_sha256"})
        if digest_value(payload) != self.mapped_event_sha256:
            raise ValueError("mapped replay event self-hash mismatch")
        return self


def build_ecab_factual_history_span_v1(**values: Any) -> ECABFactualHistorySpanV1:
    """Test/worker constructor that completes the immutable event hash in memory."""

    payload = {
        "contract": "casepath.ecab-factual-history-span/1.0.0",
        **values,
    }
    return ECABFactualHistorySpanV1.model_validate(
        {**payload, "event_sha256": digest_value(payload)}
    )


def map_ecab_factual_history_span_v1(
    *,
    action: EvidenceAction,
    span: ECABFactualHistorySpanV1,
    record_version: str,
    expected_event_index: int,
    expected_previous_event_sha256: str | None,
) -> ECABMappedReplayEventV1:
    """Map one sanitized span into a raw, non-authoritative evidence event."""

    span = ECABFactualHistorySpanV1.model_validate(span.model_dump(mode="json"))
    action = EvidenceAction.model_validate(action.model_dump(mode="json"))
    if action.bounded_tool_id != ECAB_FACTUAL_HISTORY_TOOL_ID:
        raise ECABReplayContractError("action is not bound to the ECAB replay tool")
    if span.action_id != action.action_id or span.action_sha256 != action.action_sha256:
        raise ECABReplayContractError("replay span is bound to another action")
    if span.source_version != record_version:
        raise ECABReplayContractError("replay span record version is stale")
    if (
        span.event_index != expected_event_index
        or span.previous_event_sha256 != expected_previous_event_sha256
    ):
        raise ECABReplayContractError("replay event is out of canonical order")
    if digest_text(span.sanitized_page_text) != span.source_sha256:
        raise ECABReplayContractError("replay source content hash mismatch")
    excerpt = span.sanitized_page_text[span.text_start : span.text_end]
    mapped_payload = {
        "contract": "casepath.ecab-mapped-replay-event/1.0.0",
        "event_index": span.event_index,
        "source_event_sha256": span.event_sha256,
        "action_id": action.action_id,
        "action_sha256": action.action_sha256,
        "source_id": span.source_id,
        "source_sha256": span.source_sha256,
        "source_version": span.source_version,
        "sanitized_content": span.sanitized_page_text,
        "text_start": span.text_start,
        "text_end": span.text_end,
        "sanitized_excerpt": excerpt,
        "span_sha256": digest_text(excerpt),
        "observed_at": span.observed_at,
        "artifact_source_version": span.source_version,
        "artifact_page_count": 1,
    }
    return ECABMappedReplayEventV1.model_validate(
        {
            **mapped_payload,
            "mapped_event_sha256": digest_value(mapped_payload),
        }
    )


__all__ = [
    "ECAB_FACTUAL_HISTORY_TOOL_ID",
    "ECABFactualHistorySpanV1",
    "ECABMappedReplayEventV1",
    "ECABReplayContractError",
    "build_ecab_factual_history_span_v1",
    "map_ecab_factual_history_span_v1",
]
