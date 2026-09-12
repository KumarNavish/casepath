from __future__ import annotations

import base64
import binascii
import json
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import Field, StrictInt, model_validator

from .foundation.common import digest_text, digest_value, is_sha256
from .foundation.contracts import FoundationModel


DOCUMENT_LIFECYCLE_ADAPTER_ID = "casepath.document-lifecycle-shadow/1.0.0"
DOCUMENT_LIFECYCLE_ROUTE = "/api/shadow/document-lifecycle/v1/replay"
Relation = Literal["support", "contest"]
SourceKind = Literal["claim", "event", "document"]


class DocumentLifecycleShadowError(ValueError):
    pass


class UnresolvedTimestamp(DocumentLifecycleShadowError):
    pass


def aware_instant(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise UnresolvedTimestamp("timestamp_is_absent")
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise UnresolvedTimestamp("timestamp_is_malformed") from exc
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise UnresolvedTimestamp("timestamp_timezone_is_missing")
    return instant.astimezone(timezone.utc)


def normalized_instant(value: str) -> str:
    return aware_instant(value).isoformat().replace("+00:00", "Z")


class LifecycleReceiptEnvelopeV1(FoundationModel):
    channel: str = Field(min_length=1, max_length=120)
    sender: str = Field(min_length=1, max_length=240)
    observed_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_observed_at(self) -> "LifecycleReceiptEnvelopeV1":
        aware_instant(self.observed_at)
        return self


class LifecycleSourceV1(FoundationModel):
    contract: Literal["casepath.document-lifecycle-source/1.0.0"] = (
        "casepath.document-lifecycle-source/1.0.0"
    )
    source_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    source_version: str = Field(min_length=1, max_length=200)
    source_kind: SourceKind
    content_sha256: str
    content_b64: str = Field(min_length=1, max_length=2_000_000)
    decoded_text: str = Field(min_length=1, max_length=1_000_000)
    observed_at: str
    receipt_envelope: LifecycleReceiptEnvelopeV1 | None = None

    @model_validator(mode="after")
    def validate_source(self) -> "LifecycleSourceV1":
        observed = aware_instant(self.observed_at)
        if not is_sha256(self.content_sha256):
            raise ValueError("source_hash_is_invalid")
        try:
            raw = base64.b64decode(self.content_b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("source_base64_is_not_canonical") from exc
        try:
            decoded = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValueError("source_is_not_strict_utf8") from exc
        if base64.b64encode(raw).decode("ascii") != self.content_b64:
            raise ValueError("source_base64_is_not_canonical")
        if decoded != self.decoded_text or sha256(raw).hexdigest() != self.content_sha256:
            raise ValueError("source_bytes_text_or_hash_differ")
        if self.receipt_envelope is not None:
            if aware_instant(self.receipt_envelope.observed_at) != observed:
                raise ValueError("source_and_receipt_observed_at_differ")
        return self


class LifecycleObligationV1(FoundationModel):
    obligation_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    title: str = Field(min_length=1, max_length=500)
    provider_keys: tuple[str, ...] = Field(min_length=1)
    scope_key: str = Field(min_length=1, max_length=300)
    timing_key: str = Field(min_length=1, max_length=300)
    accepted_evidence_types: tuple[str, ...] = Field(min_length=1)
    anchor_source_id: str = Field(min_length=1, max_length=128)
    quote_anchor: str = Field(min_length=1, max_length=2_000)
    quote_start: StrictInt = Field(ge=0)
    quote_end: StrictInt = Field(gt=0)

    @model_validator(mode="after")
    def validate_obligation(self) -> "LifecycleObligationV1":
        if self.quote_end <= self.quote_start:
            raise ValueError("obligation_quote_span_is_invalid")
        if len(set(self.provider_keys)) != len(self.provider_keys):
            raise ValueError("obligation_provider_roster_has_duplicates")
        return self


class LifecycleBindingV1(FoundationModel):
    binding_id: str = Field(pattern=r"^binding\.[0-9a-f]{64}$")
    source_id: str
    evidence_id: str
    obligation_id: str
    relation: Relation
    active: bool = True
    retracted_by: str | None = None
    proposed_by: str
    semantic_status: Literal["fallible_source_relative_interpretation"] = (
        "fallible_source_relative_interpretation"
    )


class LifecycleCommitmentV1(FoundationModel):
    commitment_id: str = Field(pattern=r"^commitment\.[0-9a-f]{64}$")
    source_id: str
    obligation_id: str
    available_at_original: str | None
    available_at_utc: str | None
    timestamp_status: Literal["aware", "unresolved"]
    active: bool = True
    cancelled_by: str | None = None
    proposed_by: str


class LifecycleStateV1(FoundationModel):
    contract: Literal["casepath.document-lifecycle-state/1.0.0"] = (
        "casepath.document-lifecycle-state/1.0.0"
    )
    sources: tuple[LifecycleSourceV1, ...] = ()
    bindings: tuple[LifecycleBindingV1, ...] = ()
    commitments: tuple[LifecycleCommitmentV1, ...] = ()
    observed_event_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_state_rosters(self) -> "LifecycleStateV1":
        for values, name in (
            (self.sources, "source_id"),
            (self.bindings, "binding_id"),
            (self.commitments, "commitment_id"),
        ):
            ids = [getattr(value, name) for value in values]
            if len(ids) != len(set(ids)):
                raise ValueError(f"state_{name}_roster_has_duplicates")
        if len(self.observed_event_ids) != len(set(self.observed_event_ids)):
            raise ValueError("state_event_roster_has_duplicates")
        return self


class LifecycleEventV1(FoundationModel):
    contract: Literal["casepath.document-lifecycle-event/1.0.0"] = (
        "casepath.document-lifecycle-event/1.0.0"
    )
    event_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    received: bool
    observed_at: str
    text_sha256: str
    text_b64: str = Field(min_length=1, max_length=1_000_000)
    text: str = Field(min_length=1, max_length=500_000)
    documents: tuple[LifecycleSourceV1, ...] = ()

    @model_validator(mode="after")
    def validate_event(self) -> "LifecycleEventV1":
        aware_instant(self.observed_at)
        if not is_sha256(self.text_sha256):
            raise ValueError("event_hash_is_invalid")
        try:
            raw = base64.b64decode(self.text_b64, validate=True)
            decoded = raw.decode("utf-8", errors="strict")
        except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
            raise ValueError("event_bytes_are_invalid") from exc
        if (
            base64.b64encode(raw).decode("ascii") != self.text_b64
            or decoded != self.text
            or sha256(raw).hexdigest() != self.text_sha256
        ):
            raise ValueError("event_bytes_text_or_hash_differ")
        if not self.received and self.documents:
            raise ValueError("unreceived_event_cannot_carry_documents")
        if any(source.source_kind != "document" for source in self.documents):
            raise ValueError("event_document_has_wrong_source_kind")
        return self


class LifecycleProposalReceiptV1(FoundationModel):
    contract: Literal["casepath.document-lifecycle-proposal-receipt/1.0.0"] = (
        "casepath.document-lifecycle-proposal-receipt/1.0.0"
    )
    producer_kind: Literal["model", "deterministic_parser", "test_fixture"]
    record_id: str
    producer_id: str
    producer_revision: str
    input_sha256: str
    rendered_prompt_sha256: str
    source_prefix_sha256: str
    output_sha256: str
    adapter_payload_sha256: str
    input_tokens: StrictInt = Field(ge=0)
    output_tokens: StrictInt = Field(ge=0)
    status: str
    finish_reason: str
    failure: str | None
    run_fingerprint_sha256: str
    producer_identity: dict[str, Any]
    producer_identity_sha256: str
    runtime: dict[str, Any]
    settings: dict[str, Any]
    cost_usd: float | None = Field(default=None, ge=0)
    cost_basis: Literal[
        "paid_api_cash_spend", "reported_total_monetary_compute_cost", "unavailable"
    ]
    receipt_sha256: str

    @model_validator(mode="after")
    def validate_cost_basis(self) -> "LifecycleProposalReceiptV1":
        if self.cost_basis == "unavailable" and self.cost_usd is not None:
            raise ValueError("unavailable_cost_must_not_have_usd_value")
        if self.cost_basis != "unavailable" and self.cost_usd is None:
            raise ValueError("reported_cost_basis_requires_usd_value")
        return self

    @model_validator(mode="after")
    def validate_receipt(self) -> "LifecycleProposalReceiptV1":
        hashes = (
            self.input_sha256,
            self.rendered_prompt_sha256,
            self.source_prefix_sha256,
            self.output_sha256,
            self.adapter_payload_sha256,
            self.run_fingerprint_sha256,
            self.producer_identity_sha256,
            self.receipt_sha256,
        )
        if not all(is_sha256(value) for value in hashes):
            raise ValueError("proposal_receipt_hash_is_invalid")
        if self.producer_identity_sha256 != digest_value(self.producer_identity):
            raise ValueError("proposal_producer_identity_hash_differs")
        material = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if self.receipt_sha256 != digest_value(material):
            raise ValueError("proposal_receipt_identity_differs")
        return self


class DocumentLifecycleShadowRequestV1(FoundationModel):
    contract: Literal["casepath.document-lifecycle-shadow-request/1.0.0"] = (
        "casepath.document-lifecycle-shadow-request/1.0.0"
    )
    operation_id: str
    obligations: tuple[LifecycleObligationV1, ...] = Field(min_length=1)
    previous_state: LifecycleStateV1
    expected_parent_state_sha256: str
    event: LifecycleEventV1
    source_prefix_sha256: str
    raw_proposed_output: str = Field(min_length=1, max_length=200_000)
    proposal_receipt: LifecycleProposalReceiptV1
    max_requests: StrictInt = Field(default=2, ge=1, le=10)

    @model_validator(mode="after")
    def validate_request_rosters(self) -> "DocumentLifecycleShadowRequestV1":
        obligation_ids = [value.obligation_id for value in self.obligations]
        if len(obligation_ids) != len(set(obligation_ids)):
            raise ValueError("obligation_roster_has_duplicates")
        if not is_sha256(self.expected_parent_state_sha256):
            raise ValueError("parent_state_hash_is_invalid")
        if not is_sha256(self.source_prefix_sha256):
            raise ValueError("source_prefix_hash_is_invalid")
        return self


def lifecycle_state_sha256(state: LifecycleStateV1) -> str:
    return digest_value(state.model_dump(mode="json"))


def lifecycle_adapter_payload_sha256(
    previous_state: LifecycleStateV1,
    obligations: tuple[LifecycleObligationV1, ...],
    event: LifecycleEventV1,
) -> str:
    return digest_value(
        {
            "contract": "casepath.document-lifecycle-adapter-payload/1.0.0",
            "previous_state": previous_state.model_dump(mode="json"),
            "obligations": [value.model_dump(mode="json") for value in obligations],
            "event": event.model_dump(mode="json"),
        }
    )


def _binding_id(evidence_id: str, obligation_id: str, relation: Relation) -> str:
    return "binding." + digest_value(
        {"evidence_id": evidence_id, "obligation_id": obligation_id, "relation": relation}
    )


def _commitment_id(source_id: str, obligation_id: str) -> str:
    return "commitment." + digest_value(
        {"source_id": source_id, "obligation_id": obligation_id}
    )


def _canonical_evidence_ids(sources: list[LifecycleSourceV1]) -> dict[str, str]:
    first_id_by_hash: dict[str, str] = {}
    result: dict[str, str] = {}
    for source in sources:
        if source.source_kind == "document":
            canonical = first_id_by_hash.setdefault(
                source.content_sha256, source.source_id
            )
            result[source.source_id] = canonical
    return result


def new_lifecycle_state(
    *,
    sources: tuple[LifecycleSourceV1, ...],
    bindings: tuple[tuple[str, str, Relation], ...] = (),
) -> LifecycleStateV1:
    canonical = _canonical_evidence_ids(list(sources))
    values = []
    for source_id, obligation_id, relation in bindings:
        evidence_id = canonical.get(source_id, source_id)
        values.append(
            LifecycleBindingV1(
                binding_id=_binding_id(evidence_id, obligation_id, relation),
                source_id=source_id,
                evidence_id=evidence_id,
                obligation_id=obligation_id,
                relation=relation,
                proposed_by="initial_public_scaffold",
            )
        )
    return LifecycleStateV1(sources=sources, bindings=tuple(values))


def _parse_operations(raw: str) -> list[dict[str, Any]]:
    text = raw.strip()
    for suffix in ("<|im_end|>", "<|endoftext|>"):
        if text.endswith(suffix):
            text = text[: -len(suffix)].rstrip()
    if text.startswith("```") and text.endswith("```"):
        text = text[text.find("\n") + 1 : -3].strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DocumentLifecycleShadowError("proposal_is_not_one_json_object") from exc
    if isinstance(value, dict) and set(value) == {"delta"}:
        value = value["delta"]
    if not isinstance(value, dict):
        raise DocumentLifecycleShadowError("proposal_is_not_an_object")
    aliases = {
        "bindings": "bind",
        "withdrawn": "withdraw",
        "promises": "promise",
        "cancelled": "cancel",
    }
    value = dict(value)
    for old, new in aliases.items():
        if old in value and new not in value:
            value[new] = value.pop(old)
    allowed = {"bind", "withdraw", "promise", "cancel", "reason", "explanation"}
    if set(value) - allowed:
        raise DocumentLifecycleShadowError("proposal_operation_schema_is_unknown")
    if not all(isinstance(value.get(kind), list) for kind in ("bind", "withdraw", "promise", "cancel")):
        raise DocumentLifecycleShadowError("proposal_requires_four_operation_lists")
    return [
        {"kind": kind, "index": index, "row": row}
        for kind in ("bind", "withdraw", "promise", "cancel")
        for index, row in enumerate(value[kind])
    ]


def _bind_row(row: Any) -> tuple[str, str, Relation]:
    if isinstance(row, dict) and set(row) == {"document_id", "obligation_id", "relation"}:
        row = [row["document_id"], row["obligation_id"], row["relation"]]
    if not isinstance(row, list) or len(row) != 3:
        raise ValueError("binding_requires_document_obligation_relation")
    document_id, obligation_id, relation = row
    relation = {"satisfies": "support", "opposes": "contest", "contradicts": "contest"}.get(
        relation, relation
    )
    if not all(isinstance(value, str) and value for value in (document_id, obligation_id)):
        raise ValueError("binding_identity_is_invalid")
    if relation not in {"support", "contest"}:
        raise ValueError("binding_relation_is_invalid")
    return document_id, obligation_id, relation


def _withdraw_row(row: Any) -> tuple[str, str | None]:
    if isinstance(row, dict) and set(row) in (
        {"document_id"},
        {"document_id", "obligation_id"},
    ):
        return row["document_id"], row.get("obligation_id")
    if isinstance(row, str):
        return row, None
    if isinstance(row, list) and len(row) in {1, 2}:
        return row[0], row[1] if len(row) == 2 else None
    raise ValueError("withdrawal_requires_document_and_optional_obligation")


def _promise_row(row: Any) -> tuple[str, str, str | None]:
    if isinstance(row, dict) and set(row) == {
        "source_id",
        "obligation_id",
        "available_after",
    }:
        row = [row["source_id"], row["obligation_id"], row["available_after"]]
    if not isinstance(row, list) or len(row) != 3:
        raise ValueError("promise_requires_source_obligation_available_at")
    source_id, obligation_id, available_at = row
    if not all(isinstance(value, str) and value for value in (source_id, obligation_id)):
        raise ValueError("promise_fields_are_invalid")
    if available_at is not None and (
        not isinstance(available_at, str) or not available_at
    ):
        raise ValueError("promise_deadline_is_invalid")
    return source_id, obligation_id, available_at


def _cancel_row(row: Any) -> tuple[str, str | None]:
    if isinstance(row, dict) and set(row) in (
        {"source_id"},
        {"source_id", "obligation_id"},
    ):
        return row["source_id"], row.get("obligation_id")
    if isinstance(row, str):
        return row, None
    if isinstance(row, list) and len(row) in {1, 2}:
        return row[0], row[1] if len(row) == 2 else None
    raise ValueError("cancellation_requires_source_and_optional_obligation")


def _operation_result(
    operation: dict[str, Any],
    status: Literal["admitted", "admitted_unresolved_time", "deduplicated", "quarantined"],
    reason: str,
    effect: dict[str, Any] | None = None,
) -> dict[str, Any]:
    material = {
        "kind": operation["kind"],
        "index": operation["index"],
        "row_sha256": digest_value(operation["row"]),
        "status": status,
        "reason": reason,
        "effect": effect,
    }
    return {**material, "operation_result_sha256": digest_value(material)}


def _views(
    obligations: tuple[LifecycleObligationV1, ...],
    bindings: list[LifecycleBindingV1],
    commitments: list[LifecycleCommitmentV1],
) -> list[dict[str, Any]]:
    rows = []
    for obligation in obligations:
        active = [
            value
            for value in bindings
            if value.obligation_id == obligation.obligation_id and value.active
        ]
        support = sorted({value.evidence_id for value in active if value.relation == "support"})
        contest = sorted({value.evidence_id for value in active if value.relation == "contest"})
        withdrawn = sorted(
            {
                value.evidence_id
                for value in bindings
                if value.obligation_id == obligation.obligation_id
                and value.relation == "support"
                and not value.active
            }
        )
        pending = sorted(
            value.commitment_id
            for value in commitments
            if value.obligation_id == obligation.obligation_id and value.active
        )
        state = (
            "contested"
            if contest
            else "received"
            if support
            else "pending"
            if pending
            else "withdrawn"
            if withdrawn
            else "open"
        )
        rows.append(
            {
                "obligation_id": obligation.obligation_id,
                "state": state,
                "evidence_document_ids": support,
                "contesting_document_ids": contest,
                "withdrawn_document_ids": withdrawn,
                "pending_commitment_ids": pending,
            }
        )
    return rows


def _actions(
    obligations: tuple[LifecycleObligationV1, ...],
    bindings: list[LifecycleBindingV1],
    commitments: list[LifecycleCommitmentV1],
    observed_at: str,
    max_requests: int,
) -> dict[str, Any]:
    now = aware_instant(observed_at)
    views = {value["obligation_id"]: value for value in _views(obligations, bindings, commitments)}
    eligible: list[dict[str, Any]] = []
    waits: list[dict[str, Any]] = []
    for obligation in obligations:
        view = views[obligation.obligation_id]
        if view["state"] == "received":
            continue
        active = [
            value
            for value in commitments
            if value.obligation_id == obligation.obligation_id and value.active
        ]
        if view["state"] == "pending":
            known = [value for value in active if value.available_at_utc is not None]
            unresolved = [value.commitment_id for value in active if value.available_at_utc is None]
            if unresolved and not known:
                waits.append(
                    {
                        "obligation_id": obligation.obligation_id,
                        "until_original": None,
                        "until_utc": None,
                        "reason": "pending_deadline_unresolved",
                        "commitment_ids": unresolved,
                    }
                )
                continue
            earliest = min(known, key=lambda value: aware_instant(value.available_at_utc))
            if now < aware_instant(earliest.available_at_utc):
                waits.append(
                    {
                        "obligation_id": obligation.obligation_id,
                        "until_original": earliest.available_at_original,
                        "until_utc": earliest.available_at_utc,
                        "reason": "pending_not_due",
                        "commitment_ids": sorted(value.commitment_id for value in active),
                    }
                )
                continue
            kind = "follow_up_overdue"
        elif view["state"] == "contested":
            kind = "request_conflict_resolution"
        else:
            kind = "request"
        eligible.append(
            {
                "obligation_id": obligation.obligation_id,
                "kind": kind,
                "providers": list(obligation.provider_keys),
                "scope": obligation.scope_key,
                "timing": obligation.timing_key,
            }
        )
    return {
        "requests": eligible[:max_requests],
        "eligible_requests": eligible,
        "waits": waits,
        "documents_complete": all(value["state"] == "received" for value in views.values()),
    }


def apply_document_lifecycle_shadow(
    request: DocumentLifecycleShadowRequestV1,
) -> dict[str, Any]:
    receipt = request.proposal_receipt
    if receipt.output_sha256 != digest_text(request.raw_proposed_output):
        raise DocumentLifecycleShadowError("proposal_output_hash_differs")
    if receipt.source_prefix_sha256 != request.source_prefix_sha256:
        raise DocumentLifecycleShadowError("proposal_source_prefix_hash_differs")
    adapter_payload_sha256 = lifecycle_adapter_payload_sha256(
        request.previous_state, request.obligations, request.event
    )
    if receipt.adapter_payload_sha256 != adapter_payload_sha256:
        raise DocumentLifecycleShadowError("proposal_adapter_payload_hash_differs")

    obligation_ids = {value.obligation_id for value in request.obligations}
    sources = list(request.previous_state.sources)
    bindings = list(request.previous_state.bindings)
    commitments = list(request.previous_state.commitments)
    event_ids = list(request.previous_state.observed_event_ids)
    source_by_id = {value.source_id: value for value in sources}
    source_results: list[dict[str, Any]] = []
    admitted_current_document_ids: set[str] = set()
    event_source_admitted = False

    if request.event.received:
        event_source = LifecycleSourceV1(
            source_id=request.event.event_id,
            source_version="event-v1",
            source_kind="event",
            content_sha256=request.event.text_sha256,
            content_b64=request.event.text_b64,
            decoded_text=request.event.text,
            observed_at=request.event.observed_at,
        )
        for source in (event_source, *request.event.documents):
            existing = source_by_id.get(source.source_id)
            if existing is not None:
                if (
                    existing.content_sha256 == source.content_sha256
                    and existing.source_kind == source.source_kind
                    and existing.source_version == source.source_version
                    and aware_instant(existing.observed_at)
                    == aware_instant(source.observed_at)
                ):
                    source_results.append(
                        {"source_id": source.source_id, "status": "deduplicated", "reason": "same_id_same_bytes"}
                    )
                    if source.source_id == request.event.event_id:
                        event_source_admitted = True
                    if source.source_kind == "document":
                        admitted_current_document_ids.add(source.source_id)
                else:
                    source_results.append(
                        {"source_id": source.source_id, "status": "quarantined", "reason": "source_id_identity_mismatch"}
                    )
                continue
            if source.source_kind == "document" and aware_instant(source.observed_at) != aware_instant(
                request.event.observed_at
            ):
                source_results.append(
                    {"source_id": source.source_id, "status": "quarantined", "reason": "document_event_observed_at_mismatch"}
                )
                continue
            sources.append(source)
            source_by_id[source.source_id] = source
            if source.source_id == request.event.event_id:
                event_source_admitted = True
            if source.source_kind == "document":
                admitted_current_document_ids.add(source.source_id)
            source_results.append(
                {"source_id": source.source_id, "status": "admitted", "reason": "exact_bytes_and_time_admitted"}
            )
        if event_source_admitted and request.event.event_id not in event_ids:
            event_ids.append(request.event.event_id)

    try:
        operations = _parse_operations(request.raw_proposed_output)
        parse_error = None
    except DocumentLifecycleShadowError as exc:
        operations = []
        parse_error = str(exc)

    parent_matches = request.expected_parent_state_sha256 == lifecycle_state_sha256(
        request.previous_state
    )
    proposal_usable = (
        receipt.status == "success"
        and (
            receipt.finish_reason == "eos"
            if receipt.producer_kind == "model"
            else receipt.finish_reason in {"complete", "eos"}
        )
        and receipt.failure is None
        and parse_error is None
    )
    operation_results: list[dict[str, Any]] = []
    canonical = _canonical_evidence_ids(sources)
    current_document_ids = admitted_current_document_ids
    proposal_id = receipt.receipt_sha256

    for operation in operations:
        if not parent_matches:
            operation_results.append(
                _operation_result(operation, "quarantined", "stale_parent_state")
            )
            continue
        if not proposal_usable:
            operation_results.append(
                _operation_result(operation, "quarantined", "proposal_receipt_not_successful")
            )
            continue
        if not request.event.received:
            operation_results.append(
                _operation_result(operation, "quarantined", "event_not_received")
            )
            continue
        if not event_source_admitted:
            operation_results.append(
                _operation_result(
                    operation, "quarantined", "current_event_source_not_admitted"
                )
            )
            continue
        try:
            if operation["kind"] == "bind":
                source_id, obligation_id, relation = _bind_row(operation["row"])
                if obligation_id not in obligation_ids:
                    raise ValueError("unknown_obligation_id")
                if source_id not in source_by_id or source_by_id[source_id].source_kind != "document":
                    raise ValueError("unknown_document_id")
                evidence_id = canonical[source_id]
                current_canonical = {canonical[value] for value in current_document_ids}
                if evidence_id not in current_canonical:
                    raise ValueError("binding_is_not_from_current_document_bytes")
                binding_id = _binding_id(evidence_id, obligation_id, relation)
                existing = next((value for value in bindings if value.binding_id == binding_id), None)
                if existing is not None and existing.active:
                    operation_results.append(
                        _operation_result(
                            operation,
                            "deduplicated",
                            "exact_bytes_binding_already_active",
                            {"binding_id": binding_id, "evidence_id": evidence_id},
                        )
                    )
                    continue
                if existing is not None:
                    raise ValueError("retracted_binding_requires_explicit_revalidation")
                value = LifecycleBindingV1(
                    binding_id=binding_id,
                    source_id=source_id,
                    evidence_id=evidence_id,
                    obligation_id=obligation_id,
                    relation=relation,
                    proposed_by=proposal_id,
                )
                bindings.append(value)
                if relation == "support":
                    commitments = [
                        value
                        if value.obligation_id != obligation_id or not value.active
                        else value.model_copy(update={"active": False, "cancelled_by": proposal_id})
                        for value in commitments
                    ]
                operation_results.append(
                    _operation_result(
                        operation,
                        "admitted",
                        "binding_admitted_as_fallible_interpretation",
                        {"binding_id": binding_id, "evidence_id": evidence_id},
                    )
                )
            elif operation["kind"] == "withdraw":
                source_id, obligation_id = _withdraw_row(operation["row"])
                if source_id not in canonical:
                    raise ValueError("unknown_document_id")
                evidence_id = canonical[source_id]
                targets = [
                    value
                    for value in bindings
                    if value.evidence_id == evidence_id
                    and value.active
                    and (obligation_id is None or value.obligation_id == obligation_id)
                ]
                if obligation_id is not None and obligation_id not in obligation_ids:
                    raise ValueError("unknown_obligation_id")
                if not targets:
                    raise ValueError("withdrawal_target_is_not_active")
                target_ids = {value.binding_id for value in targets}
                bindings = [
                    value.model_copy(update={"active": False, "retracted_by": proposal_id})
                    if value.binding_id in target_ids
                    else value
                    for value in bindings
                ]
                operation_results.append(
                    _operation_result(
                        operation,
                        "admitted",
                        "scoped_binding_retraction_admitted",
                        {"binding_ids": sorted(target_ids), "evidence_id": evidence_id},
                    )
                )
            elif operation["kind"] == "promise":
                source_id, obligation_id, available_at = _promise_row(operation["row"])
                if source_id != request.event.event_id:
                    raise ValueError("promise_source_is_not_current_event")
                if obligation_id not in obligation_ids:
                    raise ValueError("unknown_obligation_id")
                commitment_id = _commitment_id(source_id, obligation_id)
                try:
                    normalized = normalized_instant(available_at)
                    timestamp_status: Literal["aware", "unresolved"] = "aware"
                    status: Literal["admitted", "admitted_unresolved_time"] = "admitted"
                    reason = "source_obligation_commitment_admitted"
                except UnresolvedTimestamp:
                    normalized = None
                    timestamp_status = "unresolved"
                    status = "admitted_unresolved_time"
                    reason = "promise_deadline_timezone_unresolved"
                value = LifecycleCommitmentV1(
                    commitment_id=commitment_id,
                    source_id=source_id,
                    obligation_id=obligation_id,
                    available_at_original=available_at,
                    available_at_utc=normalized,
                    timestamp_status=timestamp_status,
                    proposed_by=proposal_id,
                )
                existing = next(
                    (item for item in commitments if item.commitment_id == commitment_id),
                    None,
                )
                if existing is not None and existing.active:
                    if (
                        existing.available_at_original == available_at
                        and existing.available_at_utc == normalized
                    ):
                        operation_results.append(
                            _operation_result(
                                operation,
                                "deduplicated",
                                "source_obligation_commitment_already_active",
                                {"commitment_id": commitment_id},
                            )
                        )
                        continue
                    raise ValueError("source_obligation_commitment_conflicts")
                if existing is None:
                    commitments.append(value)
                else:
                    commitments[commitments.index(existing)] = value
                operation_results.append(
                    _operation_result(
                        operation,
                        status,
                        reason,
                        {
                            "commitment_id": commitment_id,
                            "available_at_original": available_at,
                            "available_at_utc": normalized,
                        },
                    )
                )
            else:
                source_id, obligation_id = _cancel_row(operation["row"])
                targets = [
                    value
                    for value in commitments
                    if value.source_id == source_id
                    and value.active
                    and (obligation_id is None or value.obligation_id == obligation_id)
                ]
                if obligation_id is not None and obligation_id not in obligation_ids:
                    raise ValueError("unknown_obligation_id")
                if not targets:
                    raise ValueError("cancellation_target_is_not_active")
                target_ids = {value.commitment_id for value in targets}
                commitments = [
                    value.model_copy(update={"active": False, "cancelled_by": proposal_id})
                    if value.commitment_id in target_ids
                    else value
                    for value in commitments
                ]
                operation_results.append(
                    _operation_result(
                        operation,
                        "admitted",
                        "scoped_commitment_cancellation_admitted",
                        {"commitment_ids": sorted(target_ids)},
                    )
                )
        except (KeyError, TypeError, ValueError) as exc:
            operation_results.append(
                _operation_result(operation, "quarantined", str(exc))
            )

    state = LifecycleStateV1(
        sources=tuple(sources),
        bindings=tuple(bindings),
        commitments=tuple(commitments),
        observed_event_ids=tuple(event_ids),
    )
    views = _views(request.obligations, bindings, commitments)
    actions = _actions(
        request.obligations,
        bindings,
        commitments,
        request.event.observed_at,
        request.max_requests,
    )
    source_inventory = []
    canonical = _canonical_evidence_ids(sources)
    for source in sorted(sources, key=lambda value: value.source_id):
        evidence_id = canonical.get(source.source_id)
        source_inventory.append(
            {
                "source_id": source.source_id,
                "source_version": source.source_version,
                "source_kind": source.source_kind,
                "content_sha256": source.content_sha256,
                "size_bytes": len(base64.b64decode(source.content_b64)),
                "observed_at_original": source.observed_at,
                "observed_at_utc": normalized_instant(source.observed_at),
                "canonical_evidence_id": evidence_id,
                "exact_byte_duplicate": bool(evidence_id and evidence_id != source.source_id),
            }
        )
    material: dict[str, Any] = {
        "contract": "casepath.document-lifecycle-shadow-response/1.0.0",
        "adapter_id": DOCUMENT_LIFECYCLE_ADAPTER_ID,
        "operation_id": request.operation_id,
        "mode": "shadow_non_authoritative",
        "canonical_authority": "existing_intake_grammar_claim_loop_reducer_and_premise_corrections",
        "canonical_state_mutated": False,
        "semantic_boundary": "attributable_exact_sources_do_not_certify_entailment",
        "producer_kind": receipt.producer_kind,
        "adapter_payload_sha256": adapter_payload_sha256,
        "adapter_payload_matches_receipt": True,
        "producer_source_prefix_verification": (
            "externally_reported_match_only_not_reconstructed"
        ),
        "parent_state_matches": parent_matches,
        "proposal_status": (
            "quarantined_parse_error"
            if parse_error
            else "quarantined_receipt_status"
            if not proposal_usable
            else "processed"
        ),
        "proposal_error": parse_error,
        "raw_proposed_output": request.raw_proposed_output,
        "proposal_receipt": receipt.model_dump(mode="json"),
        "source_admission_results": source_results,
        "operation_results": operation_results,
        "source_inventory": source_inventory,
        "state": state.model_dump(mode="json"),
        "state_sha256": lifecycle_state_sha256(state),
        "obligation_view": views,
        "next_actions": actions,
    }
    return {**material, "response_sha256": digest_value(material)}


def create_document_lifecycle_shadow_router() -> APIRouter:
    router = APIRouter(tags=["document-lifecycle-shadow"])

    @router.post(DOCUMENT_LIFECYCLE_ROUTE)
    def replay_document_lifecycle(
        body: DocumentLifecycleShadowRequestV1,
    ) -> dict[str, Any]:
        try:
            return apply_document_lifecycle_shadow(body)
        except (DocumentLifecycleShadowError, TypeError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc

    # V2 has an independent contract and reducer; mounting it here preserves the
    # application's existing single document-lifecycle router entry point.
    from .document_lifecycle_shadow_v2 import create_document_lifecycle_shadow_v2_router

    router.include_router(create_document_lifecycle_shadow_v2_router())

    return router


__all__ = [
    "DOCUMENT_LIFECYCLE_ADAPTER_ID",
    "DOCUMENT_LIFECYCLE_ROUTE",
    "DocumentLifecycleShadowError",
    "DocumentLifecycleShadowRequestV1",
    "LifecycleEventV1",
    "LifecycleObligationV1",
    "LifecycleProposalReceiptV1",
    "LifecycleReceiptEnvelopeV1",
    "LifecycleSourceV1",
    "LifecycleStateV1",
    "UnresolvedTimestamp",
    "apply_document_lifecycle_shadow",
    "aware_instant",
    "create_document_lifecycle_shadow_router",
    "lifecycle_state_sha256",
    "lifecycle_adapter_payload_sha256",
    "new_lifecycle_state",
    "normalized_instant",
]
