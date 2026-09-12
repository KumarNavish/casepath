"""Native-byte document lifecycle shadow with non-authoritative suggestions.

Physical artifacts and derived views are deterministic state. Model bindings,
coverage, request suppression, and supersession remain explicitly fallible;
they never establish accepted completion or global case readiness.
"""

from __future__ import annotations

import base64
import binascii
from hashlib import sha256
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import Field, StrictInt, model_validator

from .document_lifecycle_shadow_v1 import aware_instant, normalized_instant
from .foundation.common import digest_text, digest_value, is_sha256
from .foundation.contracts import FoundationModel


DOCUMENT_LIFECYCLE_V2_ADAPTER_ID = "casepath.document-lifecycle-shadow/2.0.0"
DOCUMENT_LIFECYCLE_V2_ROUTE = "/api/shadow/document-lifecycle/v2/replay"
PhysicalMediaType = Literal[
    "application/pdf",
    "image/jpeg",
    "image/png",
    "text/plain",
    "text/plain; charset=utf-8",
    "message/rfc822",
]
ViewMediaType = Literal["image/jpeg", "image/png", "text/plain"]
BindingRelation = Literal["compatible", "incompatible", "unresolved"]
ReportedCoverage = Literal["none", "partial", "complete", "unresolved"]


class DocumentLifecycleShadowV2Error(ValueError):
    pass


def _verified_content(
    *,
    content_b64: str,
    content_sha256: str,
    size_bytes: int,
    media_type: str,
    decoded_text: str | None,
) -> bytes:
    if not is_sha256(content_sha256):
        raise ValueError("content_hash_is_invalid")
    try:
        raw = base64.b64decode(content_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("content_base64_is_not_canonical") from exc
    if base64.b64encode(raw).decode("ascii") != content_b64:
        raise ValueError("content_base64_is_not_canonical")
    if len(raw) != size_bytes or sha256(raw).hexdigest() != content_sha256:
        raise ValueError("content_bytes_size_or_hash_differ")

    if media_type == "application/pdf":
        if not raw.startswith(b"%PDF-"):
            raise ValueError("pdf_magic_differs")
    elif media_type == "image/png":
        if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("png_magic_differs")
    elif media_type == "image/jpeg":
        if not raw.startswith(b"\xff\xd8\xff"):
            raise ValueError("jpeg_magic_differs")
    else:
        if raw.startswith((b"%PDF-", b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff")):
            raise ValueError("binary_content_cannot_be_declared_as_text")
        try:
            value = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValueError("text_content_is_not_strict_utf8") from exc
        if decoded_text != value:
            raise ValueError("decoded_text_differs_from_original_bytes")
    if media_type in {"application/pdf", "image/png", "image/jpeg"}:
        if decoded_text is not None:
            raise ValueError("binary_content_cannot_carry_decoded_text")
    return raw


class LifecyclePhysicalArtifactV2(FoundationModel):
    contract: Literal["casepath.lifecycle-physical-artifact/2.0.0"] = (
        "casepath.lifecycle-physical-artifact/2.0.0"
    )
    artifact_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
    source_version: str = Field(min_length=1, max_length=200)
    media_type: PhysicalMediaType
    content_b64: str = Field(min_length=1, max_length=20_000_000)
    content_sha256: str
    size_bytes: StrictInt = Field(gt=0, le=15_000_000)
    decoded_text: str | None = Field(default=None, max_length=5_000_000)
    observed_at: str

    @model_validator(mode="after")
    def validate_artifact(self) -> "LifecyclePhysicalArtifactV2":
        aware_instant(self.observed_at)
        _verified_content(
            content_b64=self.content_b64,
            content_sha256=self.content_sha256,
            size_bytes=self.size_bytes,
            media_type=self.media_type,
            decoded_text=self.decoded_text,
        )
        return self


class LifecycleDerivedViewV2(FoundationModel):
    contract: Literal["casepath.lifecycle-derived-view/2.0.0"] = (
        "casepath.lifecycle-derived-view/2.0.0"
    )
    view_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
    parent_artifact_id: str
    parent_artifact_sha256: str
    media_type: ViewMediaType
    content_b64: str = Field(min_length=1, max_length=20_000_000)
    content_sha256: str
    size_bytes: StrictInt = Field(gt=0, le=15_000_000)
    decoded_text: str | None = Field(default=None, max_length=5_000_000)
    page_index: StrictInt | None = Field(default=None, ge=0)
    derivation_method: str = Field(min_length=1, max_length=240)
    derivation_sha256: str
    observed_at: str

    @model_validator(mode="after")
    def validate_view(self) -> "LifecycleDerivedViewV2":
        aware_instant(self.observed_at)
        if not is_sha256(self.parent_artifact_sha256):
            raise ValueError("view_parent_hash_is_invalid")
        _verified_content(
            content_b64=self.content_b64,
            content_sha256=self.content_sha256,
            size_bytes=self.size_bytes,
            media_type=self.media_type,
            decoded_text=self.decoded_text,
        )
        material = self.model_dump(mode="json", include={
            "parent_artifact_id",
            "parent_artifact_sha256",
            "media_type",
            "content_sha256",
            "size_bytes",
            "page_index",
            "derivation_method",
            "observed_at",
        })
        if self.derivation_sha256 != digest_value(material):
            raise ValueError("view_derivation_identity_differs")
        return self


class LifecycleObligationV2(FoundationModel):
    obligation_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    description: str = Field(min_length=1, max_length=2_000)
    provider_keys: tuple[str, ...] = Field(min_length=1)
    scope_key: str = Field(min_length=1, max_length=500)
    timing_key: str = Field(min_length=1, max_length=500)
    warrant_refs: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_obligation(self) -> "LifecycleObligationV2":
        if len(set(self.provider_keys)) != len(self.provider_keys):
            raise ValueError("obligation_provider_roster_has_duplicates")
        if len(set(self.warrant_refs)) != len(self.warrant_refs):
            raise ValueError("obligation_warrant_roster_has_duplicates")
        return self


class LifecycleSourceReferenceV2(FoundationModel):
    public_ref: str = Field(pattern=r"^[tp][0-9]+$")
    view_id: str
    view_content_sha256: str
    text_start: StrictInt | None = Field(default=None, ge=0)
    text_end: StrictInt | None = Field(default=None, gt=0)
    exact_text_sha256: str | None = None

    @model_validator(mode="after")
    def validate_reference(self) -> "LifecycleSourceReferenceV2":
        if not is_sha256(self.view_content_sha256):
            raise ValueError("source_ref_view_hash_is_invalid")
        if self.public_ref.startswith("t"):
            if self.text_start is None or self.text_end is None:
                raise ValueError("text_ref_requires_span")
            if self.text_end <= self.text_start:
                raise ValueError("text_ref_span_is_invalid")
            if self.exact_text_sha256 is None or not is_sha256(self.exact_text_sha256):
                raise ValueError("text_ref_exact_text_hash_is_invalid")
        elif any(value is not None for value in (
            self.text_start, self.text_end, self.exact_text_sha256
        )):
            raise ValueError("image_ref_cannot_carry_text_span")
        return self


class LifecycleProposalBindingV2(FoundationModel):
    obligation_id: str
    source_artifact_id: str
    source_refs: tuple[LifecycleSourceReferenceV2, ...] = Field(min_length=1)
    relation: BindingRelation
    reported_coverage: ReportedCoverage
    reported_facts: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_binding(self) -> "LifecycleProposalBindingV2":
        refs = [(value.public_ref, value.view_id) for value in self.source_refs]
        if len(refs) != len(set(refs)):
            raise ValueError("proposal_source_ref_roster_has_duplicates")
        if any(not value.strip() for value in self.reported_facts):
            raise ValueError("reported_fact_is_empty")
        return self


class LifecycleProposalReceiptV2(FoundationModel):
    contract: Literal["casepath.lifecycle-proposal-receipt/2.0.0"] = (
        "casepath.lifecycle-proposal-receipt/2.0.0"
    )
    producer_kind: Literal["model", "deterministic_parser", "test_fixture"]
    record_id: str
    producer_id: str
    producer_revision: str
    input_sha256: str
    rendered_prompt_sha256: str
    source_prefix_sha256: str
    output_sha256: str
    proposal_projection_sha256: str
    upstream_completion_sha256: str
    run_fingerprint_sha256: str
    producer_identity_sha256: str
    processor_input_fingerprint: str | None = None
    status: str
    finish_reason: str
    failure: str | None = None
    receipt_sha256: str

    @model_validator(mode="after")
    def validate_receipt(self) -> "LifecycleProposalReceiptV2":
        hashes = [
            self.input_sha256,
            self.rendered_prompt_sha256,
            self.source_prefix_sha256,
            self.output_sha256,
            self.proposal_projection_sha256,
            self.upstream_completion_sha256,
            self.run_fingerprint_sha256,
            self.producer_identity_sha256,
            self.receipt_sha256,
        ]
        if self.processor_input_fingerprint is not None:
            hashes.append(self.processor_input_fingerprint)
        if not all(is_sha256(value) for value in hashes):
            raise ValueError("proposal_receipt_hash_is_invalid")
        material = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if self.receipt_sha256 != digest_value(material):
            raise ValueError("proposal_receipt_identity_differs")
        return self


class LifecycleEventV2(FoundationModel):
    contract: Literal["casepath.lifecycle-native-event/2.0.0"] = (
        "casepath.lifecycle-native-event/2.0.0"
    )
    event_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
    observed_at: str
    physical_artifacts: tuple[LifecyclePhysicalArtifactV2, ...] = Field(min_length=1)
    derived_views: tuple[LifecycleDerivedViewV2, ...] = ()
    delivered_request_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_event(self) -> "LifecycleEventV2":
        event_time = aware_instant(self.observed_at)
        artifact_ids = [value.artifact_id for value in self.physical_artifacts]
        view_ids = [value.view_id for value in self.derived_views]
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("event_artifact_roster_has_duplicates")
        if len(view_ids) != len(set(view_ids)):
            raise ValueError("event_view_roster_has_duplicates")
        if len(self.delivered_request_ids) != len(set(self.delivered_request_ids)):
            raise ValueError("event_delivery_roster_has_duplicates")
        for artifact in self.physical_artifacts:
            if aware_instant(artifact.observed_at) > event_time:
                raise ValueError("future_artifact_cannot_enter_event")
        for view in self.derived_views:
            if aware_instant(view.observed_at) > event_time:
                raise ValueError("future_view_cannot_enter_event")
        return self


class LifecycleInterpretationV2(FoundationModel):
    interpretation_id: str = Field(pattern=r"^interpretation\.[0-9a-f]{64}$")
    obligation_id: str
    source_artifact_id: str
    source_refs: tuple[LifecycleSourceReferenceV2, ...]
    relation: BindingRelation
    reported_coverage: ReportedCoverage
    reported_facts: tuple[str, ...]
    proposed_by_receipt_sha256: str
    semantic_status: Literal["fallible_source_relative_interpretation"] = (
        "fallible_source_relative_interpretation"
    )
    accepted_complete: Literal[False] = False
    active: bool = True
    superseded_by_receipt_sha256: str | None = None

    @model_validator(mode="after")
    def validate_supersession(self) -> "LifecycleInterpretationV2":
        if self.active == (self.superseded_by_receipt_sha256 is not None):
            raise ValueError("interpretation_supersession_state_is_invalid")
        if self.superseded_by_receipt_sha256 is not None and not is_sha256(
            self.superseded_by_receipt_sha256
        ):
            raise ValueError("interpretation_supersession_receipt_is_invalid")
        return self


class LifecycleEventReceiptV2(FoundationModel):
    contract: Literal["casepath.lifecycle-event-receipt/2.0.0"] = (
        "casepath.lifecycle-event-receipt/2.0.0"
    )
    event_id: str
    observed_at_original: str
    observed_at_utc: str
    parent_state_sha256: str
    event_sha256: str
    admitted_artifact_ids: tuple[str, ...]
    admitted_view_ids: tuple[str, ...]
    delivered_request_ids: tuple[str, ...]
    proposal_receipt_sha256: str
    receipt_sha256: str

    @model_validator(mode="after")
    def validate_receipt(self) -> "LifecycleEventReceiptV2":
        for value in (
            self.parent_state_sha256,
            self.event_sha256,
            self.proposal_receipt_sha256,
            self.receipt_sha256,
        ):
            if not is_sha256(value):
                raise ValueError("event_receipt_hash_is_invalid")
        material = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if self.receipt_sha256 != digest_value(material):
            raise ValueError("event_receipt_identity_differs")
        return self


class LifecycleStateV2(FoundationModel):
    contract: Literal["casepath.document-lifecycle-state/2.0.0"] = (
        "casepath.document-lifecycle-state/2.0.0"
    )
    obligations_sha256: str
    physical_artifacts: tuple[LifecyclePhysicalArtifactV2, ...] = ()
    derived_views: tuple[LifecycleDerivedViewV2, ...] = ()
    interpretations: tuple[LifecycleInterpretationV2, ...] = ()
    proposal_receipts: tuple[LifecycleProposalReceiptV2, ...] = ()
    event_receipts: tuple[LifecycleEventReceiptV2, ...] = ()
    issued_request_ids: tuple[str, ...] = ()
    current_request_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_state(self) -> "LifecycleStateV2":
        if not is_sha256(self.obligations_sha256):
            raise ValueError("state_obligations_hash_is_invalid")
        rosters = (
            ([value.artifact_id for value in self.physical_artifacts], "artifact"),
            ([value.view_id for value in self.derived_views], "view"),
            ([value.interpretation_id for value in self.interpretations], "interpretation"),
            ([value.receipt_sha256 for value in self.proposal_receipts], "proposal_receipt"),
            ([value.event_id for value in self.event_receipts], "event"),
            (list(self.issued_request_ids), "issued_request"),
            (list(self.current_request_ids), "current_request"),
        )
        for values, name in rosters:
            if len(values) != len(set(values)):
                raise ValueError("state_%s_roster_has_duplicates" % name)
        for earlier, later in zip(self.event_receipts, self.event_receipts[1:]):
            if aware_instant(later.observed_at_original) <= aware_instant(
                earlier.observed_at_original
            ):
                raise ValueError("state_events_are_reordered_or_backdated")
        artifact_by_id = {value.artifact_id: value for value in self.physical_artifacts}
        view_by_id = {value.view_id: value for value in self.derived_views}
        receipt_ids = {value.receipt_sha256 for value in self.proposal_receipts}
        if not set(self.current_request_ids).issubset(set(self.issued_request_ids)):
            raise ValueError("state_current_request_was_never_issued")
        for view in self.derived_views:
            parent = artifact_by_id.get(view.parent_artifact_id)
            if parent is None or parent.content_sha256 != view.parent_artifact_sha256:
                raise ValueError("state_view_parent_identity_differs")
            if aware_instant(view.observed_at) < aware_instant(parent.observed_at):
                raise ValueError("state_view_predates_parent")
        for interpretation in self.interpretations:
            if interpretation.source_artifact_id not in artifact_by_id:
                raise ValueError("state_interpretation_source_is_unknown")
            if interpretation.proposed_by_receipt_sha256 not in receipt_ids:
                raise ValueError("state_interpretation_receipt_is_unknown")
            if (
                interpretation.superseded_by_receipt_sha256 is not None
                and interpretation.superseded_by_receipt_sha256 not in receipt_ids
            ):
                raise ValueError("state_interpretation_supersession_receipt_is_unknown")
            for ref in interpretation.source_refs:
                view = view_by_id.get(ref.view_id)
                if view is None or view.parent_artifact_id != interpretation.source_artifact_id:
                    raise ValueError("state_interpretation_view_parent_differs")
                _validate_source_reference(ref, view)
        return self


class DocumentLifecycleShadowRequestV2(FoundationModel):
    contract: Literal["casepath.document-lifecycle-shadow-request/2.0.0"] = (
        "casepath.document-lifecycle-shadow-request/2.0.0"
    )
    operation_id: str = Field(min_length=1, max_length=240)
    obligations: tuple[LifecycleObligationV2, ...] = Field(min_length=1)
    previous_state: LifecycleStateV2
    expected_parent_state_sha256: str
    event: LifecycleEventV2
    source_prefix_sha256: str
    raw_proposed_output: str = Field(min_length=1, max_length=200_000)
    proposal_bindings: tuple[LifecycleProposalBindingV2, ...] = ()
    supersede_interpretation_ids: tuple[str, ...] = ()
    proposal_receipt: LifecycleProposalReceiptV2
    max_requests: StrictInt = Field(default=2, ge=1, le=10)

    @model_validator(mode="after")
    def validate_request(self) -> "DocumentLifecycleShadowRequestV2":
        obligation_ids = [value.obligation_id for value in self.obligations]
        if len(obligation_ids) != len(set(obligation_ids)):
            raise ValueError("obligation_roster_has_duplicates")
        if len(self.supersede_interpretation_ids) != len(
            set(self.supersede_interpretation_ids)
        ):
            raise ValueError("supersession_roster_has_duplicates")
        if not is_sha256(self.expected_parent_state_sha256):
            raise ValueError("parent_state_hash_is_invalid")
        if not is_sha256(self.source_prefix_sha256):
            raise ValueError("source_prefix_hash_is_invalid")
        if digest_value([value.model_dump(mode="json") for value in self.obligations]) != (
            self.previous_state.obligations_sha256
        ):
            raise ValueError("obligation_roster_differs_from_parent_state")
        return self


def obligations_sha256_v2(obligations: tuple[LifecycleObligationV2, ...]) -> str:
    return digest_value([value.model_dump(mode="json") for value in obligations])


def new_lifecycle_state_v2(
    obligations: tuple[LifecycleObligationV2, ...],
) -> LifecycleStateV2:
    return LifecycleStateV2(obligations_sha256=obligations_sha256_v2(obligations))


def lifecycle_state_sha256_v2(state: LifecycleStateV2) -> str:
    return digest_value(state.model_dump(mode="json"))


def derivation_sha256_v2(
    *,
    parent_artifact_id: str,
    parent_artifact_sha256: str,
    media_type: ViewMediaType,
    content_sha256: str,
    size_bytes: int,
    page_index: int | None,
    derivation_method: str,
    observed_at: str,
) -> str:
    return digest_value({
        "parent_artifact_id": parent_artifact_id,
        "parent_artifact_sha256": parent_artifact_sha256,
        "media_type": media_type,
        "content_sha256": content_sha256,
        "size_bytes": size_bytes,
        "page_index": page_index,
        "derivation_method": derivation_method,
        "observed_at": observed_at,
    })


def proposal_projection_sha256_v2(
    bindings: tuple[LifecycleProposalBindingV2, ...],
    supersede_interpretation_ids: tuple[str, ...] = (),
) -> str:
    return digest_value({
        "bindings": [value.model_dump(mode="json") for value in bindings],
        "supersede_interpretation_ids": list(supersede_interpretation_ids),
    })


def _request_id(obligation: LifecycleObligationV2) -> str:
    return "request." + digest_value(obligation.model_dump(mode="json"))


def _interpretation_id(binding: LifecycleProposalBindingV2) -> str:
    return "interpretation." + digest_value(binding.model_dump(mode="json"))


def _validate_source_reference(
    ref: LifecycleSourceReferenceV2,
    view: LifecycleDerivedViewV2,
) -> None:
    if ref.view_content_sha256 != view.content_sha256:
        raise DocumentLifecycleShadowV2Error("proposal_ref_view_hash_differs")
    if ref.public_ref.startswith("t"):
        if view.decoded_text is None or view.media_type != "text/plain":
            raise DocumentLifecycleShadowV2Error("text_ref_does_not_target_text_view")
        exact = view.decoded_text[ref.text_start : ref.text_end]
        if digest_text(exact) != ref.exact_text_sha256:
            raise DocumentLifecycleShadowV2Error("proposal_ref_text_span_differs")
    elif view.media_type not in {"image/png", "image/jpeg"}:
        raise DocumentLifecycleShadowV2Error("image_ref_does_not_target_image_view")


def _admit_sources(
    state: LifecycleStateV2,
    event: LifecycleEventV2,
) -> tuple[
    list[LifecyclePhysicalArtifactV2],
    list[LifecycleDerivedViewV2],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    artifacts = list(state.physical_artifacts)
    views = list(state.derived_views)
    artifact_by_id = {value.artifact_id: value for value in artifacts}
    view_by_id = {value.view_id: value for value in views}
    canonical_by_hash = {value.content_sha256: value.artifact_id for value in artifacts}
    artifact_receipts: list[dict[str, Any]] = []
    view_receipts: list[dict[str, Any]] = []

    for artifact in event.physical_artifacts:
        existing = artifact_by_id.get(artifact.artifact_id)
        if existing is not None:
            if existing != artifact:
                raise DocumentLifecycleShadowV2Error("artifact_id_identity_mismatch")
            status = "deduplicated"
        else:
            artifacts.append(artifact)
            artifact_by_id[artifact.artifact_id] = artifact
            status = "admitted"
        canonical_id = canonical_by_hash.setdefault(
            artifact.content_sha256, artifact.artifact_id
        )
        material = {
            "artifact_id": artifact.artifact_id,
            "status": status,
            "content_sha256": artifact.content_sha256,
            "size_bytes": artifact.size_bytes,
            "media_type": artifact.media_type,
            "canonical_artifact_id": canonical_id,
            "exact_byte_duplicate": canonical_id != artifact.artifact_id,
        }
        artifact_receipts.append({**material, "receipt_sha256": digest_value(material)})

    for view in event.derived_views:
        parent = artifact_by_id.get(view.parent_artifact_id)
        if parent is None or parent.content_sha256 != view.parent_artifact_sha256:
            raise DocumentLifecycleShadowV2Error("view_parent_identity_differs")
        if aware_instant(view.observed_at) < aware_instant(parent.observed_at):
            raise DocumentLifecycleShadowV2Error("view_predates_parent")
        existing = view_by_id.get(view.view_id)
        if existing is not None:
            if existing != view:
                raise DocumentLifecycleShadowV2Error("view_id_identity_mismatch")
            status = "deduplicated"
        else:
            views.append(view)
            view_by_id[view.view_id] = view
            status = "admitted"
        material = {
            "view_id": view.view_id,
            "status": status,
            "content_sha256": view.content_sha256,
            "size_bytes": view.size_bytes,
            "media_type": view.media_type,
            "parent_artifact_id": view.parent_artifact_id,
            "parent_artifact_sha256": view.parent_artifact_sha256,
            "derivation_sha256": view.derivation_sha256,
        }
        view_receipts.append({**material, "receipt_sha256": digest_value(material)})
    return artifacts, views, artifact_receipts, view_receipts


def _obligation_views(
    obligations: tuple[LifecycleObligationV2, ...],
    interpretations: list[LifecycleInterpretationV2],
) -> list[dict[str, Any]]:
    rank = {"none": 0, "unresolved": 1, "partial": 2, "complete": 3}
    rows = []
    for obligation in obligations:
        related = [
            value for value in interpretations
            if value.obligation_id == obligation.obligation_id and value.active
        ]
        compatible = [value for value in related if value.relation == "compatible"]
        coverage = max(
            (value.reported_coverage for value in compatible),
            key=lambda value: rank[value],
            default="none",
        )
        suggested_state = (
            "complete"
            if coverage == "complete"
            else "partial"
            if coverage == "partial"
            else "open"
        )
        rows.append({
            "obligation_id": obligation.obligation_id,
            "certified_state": "open",
            "suggested_state": suggested_state,
            "accepted_complete": False,
            "reported_coverage": coverage,
            "binding_validation": "structural_parent_and_pointer_only",
            "interpretation_ids": sorted(value.interpretation_id for value in related),
            "compatible_interpretation_ids": sorted(
                value.interpretation_id for value in compatible
            ),
            "rejected_source_interpretation_ids": sorted(
                value.interpretation_id
                for value in related
                if value.relation == "incompatible"
            ),
            "reported_source_artifact_ids": sorted({
                value.source_artifact_id for value in related
            }),
        })
    return rows


def _next_actions(
    obligations: tuple[LifecycleObligationV2, ...],
    obligation_views: list[dict[str, Any]],
    max_requests: int,
) -> dict[str, Any]:
    by_id = {value["obligation_id"]: value for value in obligation_views}
    eligible = []
    suppressed = []
    for value in obligations:
        view = by_id[value.obligation_id]
        row = {
            "request_id": _request_id(value),
            "obligation_id": value.obligation_id,
            "request_text": value.description,
            "providers": list(value.provider_keys),
            "scope": value.scope_key,
            "timing": value.timing_key,
        }
        if view["suggested_state"] == "complete":
            suppressed.append({
                "request_id": row["request_id"],
                "obligation_id": value.obligation_id,
                "reason": "fallible_reported_complete_compatible_binding",
            })
        else:
            row["kind"] = "request"
            eligible.append(row)
    return {
        "requests": eligible[:max_requests],
        "eligible_requests": eligible,
        "suppressed_requests": suppressed,
        "suggested_documents_complete": all(
            value["suggested_state"] == "complete" for value in obligation_views
        ),
        "certified_documents_complete": False,
        "documents_complete": False,
    }


def apply_document_lifecycle_shadow_v2(
    request: DocumentLifecycleShadowRequestV2,
) -> dict[str, Any]:
    parent_sha256 = lifecycle_state_sha256_v2(request.previous_state)
    if request.expected_parent_state_sha256 != parent_sha256:
        raise DocumentLifecycleShadowV2Error("parent_state_hash_differs")
    if request.source_prefix_sha256 != request.proposal_receipt.source_prefix_sha256:
        raise DocumentLifecycleShadowV2Error("proposal_source_prefix_hash_differs")
    if digest_text(request.raw_proposed_output) != request.proposal_receipt.output_sha256:
        raise DocumentLifecycleShadowV2Error("proposal_output_hash_differs")
    if proposal_projection_sha256_v2(
        request.proposal_bindings, request.supersede_interpretation_ids
    ) != (
        request.proposal_receipt.proposal_projection_sha256
    ):
        raise DocumentLifecycleShadowV2Error("proposal_projection_hash_differs")
    if request.proposal_receipt.status != "success" or (
        request.proposal_receipt.finish_reason
        not in ({"eos"} if request.proposal_receipt.producer_kind == "model" else {"eos", "complete"})
    ) or request.proposal_receipt.failure is not None:
        raise DocumentLifecycleShadowV2Error("proposal_receipt_is_not_successful")

    previous_events = request.previous_state.event_receipts
    if request.event.event_id in {value.event_id for value in previous_events}:
        raise DocumentLifecycleShadowV2Error("event_id_was_already_observed")
    if previous_events and aware_instant(request.event.observed_at) <= aware_instant(
        previous_events[-1].observed_at_original
    ):
        raise DocumentLifecycleShadowV2Error("event_is_reordered_or_backdated")
    issued = set(request.previous_state.issued_request_ids)
    if not set(request.event.delivered_request_ids).issubset(issued):
        raise DocumentLifecycleShadowV2Error("delivered_request_was_not_previously_issued")

    artifacts, views, artifact_receipts, view_receipts = _admit_sources(
        request.previous_state, request.event
    )
    artifact_by_id = {value.artifact_id: value for value in artifacts}
    view_by_id = {value.view_id: value for value in views}
    obligation_ids = {value.obligation_id for value in request.obligations}
    interpretations = list(request.previous_state.interpretations)
    interpretation_results: list[dict[str, Any]] = []
    supersession_results: list[dict[str, Any]] = []
    for interpretation_id in request.supersede_interpretation_ids:
        existing = next(
            (
                value
                for value in interpretations
                if value.interpretation_id == interpretation_id
            ),
            None,
        )
        if existing is None:
            raise DocumentLifecycleShadowV2Error("supersession_target_is_unknown")
        if not existing.active:
            raise DocumentLifecycleShadowV2Error("supersession_target_is_not_active")
        index = interpretations.index(existing)
        interpretations[index] = existing.model_copy(update={
            "active": False,
            "superseded_by_receipt_sha256": request.proposal_receipt.receipt_sha256,
        })
        material = {
            "interpretation_id": interpretation_id,
            "status": "superseded",
            "superseded_by_receipt_sha256": request.proposal_receipt.receipt_sha256,
            "accepted_complete": False,
        }
        supersession_results.append({
            **material,
            "receipt_sha256": digest_value(material),
        })
    for binding in request.proposal_bindings:
        if binding.obligation_id not in obligation_ids:
            raise DocumentLifecycleShadowV2Error("proposal_obligation_is_unknown")
        if binding.source_artifact_id not in artifact_by_id:
            raise DocumentLifecycleShadowV2Error("proposal_source_artifact_is_unknown")
        for ref in binding.source_refs:
            view = view_by_id.get(ref.view_id)
            if view is None:
                raise DocumentLifecycleShadowV2Error("proposal_view_is_unknown")
            if view.parent_artifact_id != binding.source_artifact_id:
                raise DocumentLifecycleShadowV2Error("proposal_view_parent_differs")
            _validate_source_reference(ref, view)
        interpretation_id = _interpretation_id(binding)
        existing = next(
            (value for value in interpretations if value.interpretation_id == interpretation_id),
            None,
        )
        if existing is None:
            interpretations.append(LifecycleInterpretationV2(
                interpretation_id=interpretation_id,
                obligation_id=binding.obligation_id,
                source_artifact_id=binding.source_artifact_id,
                source_refs=binding.source_refs,
                relation=binding.relation,
                reported_coverage=binding.reported_coverage,
                reported_facts=binding.reported_facts,
                proposed_by_receipt_sha256=request.proposal_receipt.receipt_sha256,
            ))
            status = "admitted"
        else:
            status = "deduplicated"
        material = {
            "interpretation_id": interpretation_id,
            "status": status,
            "semantic_status": "fallible_source_relative_interpretation",
            "reported_coverage": binding.reported_coverage,
            "accepted_complete": False,
        }
        interpretation_results.append({
            **material,
            "receipt_sha256": digest_value(material),
        })

    proposal_receipts = list(request.previous_state.proposal_receipts)
    if request.proposal_receipt.receipt_sha256 in {
        value.receipt_sha256 for value in proposal_receipts
    }:
        raise DocumentLifecycleShadowV2Error("proposal_receipt_was_already_observed")
    proposal_receipts.append(request.proposal_receipt)

    event_material = {
        "contract": "casepath.lifecycle-event-receipt/2.0.0",
        "event_id": request.event.event_id,
        "observed_at_original": request.event.observed_at,
        "observed_at_utc": normalized_instant(request.event.observed_at),
        "parent_state_sha256": parent_sha256,
        "event_sha256": digest_value(request.event.model_dump(mode="json")),
        "admitted_artifact_ids": tuple(value.artifact_id for value in request.event.physical_artifacts),
        "admitted_view_ids": tuple(value.view_id for value in request.event.derived_views),
        "delivered_request_ids": request.event.delivered_request_ids,
        "proposal_receipt_sha256": request.proposal_receipt.receipt_sha256,
    }
    event_receipt = LifecycleEventReceiptV2(
        **event_material,
        receipt_sha256=digest_value(event_material),
    )
    obligation_views = _obligation_views(request.obligations, interpretations)
    actions = _next_actions(request.obligations, obligation_views, request.max_requests)
    state = LifecycleStateV2(
        obligations_sha256=request.previous_state.obligations_sha256,
        physical_artifacts=tuple(artifacts),
        derived_views=tuple(views),
        interpretations=tuple(interpretations),
        proposal_receipts=tuple(proposal_receipts),
        event_receipts=(*previous_events, event_receipt),
        issued_request_ids=tuple(dict.fromkeys((
            *request.previous_state.issued_request_ids,
            *(value["request_id"] for value in actions["requests"]),
        ))),
        current_request_ids=tuple(value["request_id"] for value in actions["requests"]),
    )
    state_sha256 = lifecycle_state_sha256_v2(state)
    delivery_receipts = []
    for request_id in request.event.delivered_request_ids:
        material = {
            "request_id": request_id,
            "event_id": request.event.event_id,
            "observed_at": request.event.observed_at,
            "artifact_ids": [value.artifact_id for value in request.event.physical_artifacts],
        }
        delivery_receipts.append({**material, "receipt_sha256": digest_value(material)})
    response_material: dict[str, Any] = {
        "contract": "casepath.document-lifecycle-shadow-response/2.0.0",
        "adapter_id": DOCUMENT_LIFECYCLE_V2_ADAPTER_ID,
        "operation_id": request.operation_id,
        "mode": "shadow_non_authoritative",
        "canonical_state_mutated": False,
        "authority_boundary": (
            "model_bindings_are_fallible_source_relative_interpretations_only"
        ),
        "source_prefix_verification": "receipt_match_only_not_semantic_truth",
        "parent_state_sha256": parent_sha256,
        "parent_state_matches": True,
        "physical_artifact_receipts": artifact_receipts,
        "derived_view_receipts": view_receipts,
        "request_delivery_receipts": delivery_receipts,
        "interpretation_results": interpretation_results,
        "supersession_results": supersession_results,
        "proposal_receipt": request.proposal_receipt.model_dump(mode="json"),
        "obligation_view": obligation_views,
        "next_actions": actions,
        "state": state.model_dump(mode="json"),
        "state_sha256": state_sha256,
        "event_receipt": event_receipt.model_dump(mode="json"),
    }
    transition_material = {
        "operation_id": request.operation_id,
        "parent_state_sha256": parent_sha256,
        "state_sha256": state_sha256,
        "event_receipt_sha256": event_receipt.receipt_sha256,
        "proposal_receipt_sha256": request.proposal_receipt.receipt_sha256,
        "canonical_state_mutated": False,
    }
    response_material["transition_receipt"] = {
        **transition_material,
        "receipt_sha256": digest_value(transition_material),
    }
    return {
        **response_material,
        "response_sha256": digest_value(response_material),
    }


def create_document_lifecycle_shadow_v2_router() -> APIRouter:
    router = APIRouter(tags=["document-lifecycle-shadow"])

    @router.post(DOCUMENT_LIFECYCLE_V2_ROUTE)
    def replay_document_lifecycle_v2(
        body: DocumentLifecycleShadowRequestV2,
    ) -> dict[str, Any]:
        try:
            return apply_document_lifecycle_shadow_v2(body)
        except (DocumentLifecycleShadowV2Error, TypeError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc

    return router


__all__ = [
    "DOCUMENT_LIFECYCLE_V2_ADAPTER_ID",
    "DOCUMENT_LIFECYCLE_V2_ROUTE",
    "DocumentLifecycleShadowRequestV2",
    "DocumentLifecycleShadowV2Error",
    "LifecycleDerivedViewV2",
    "LifecycleEventV2",
    "LifecycleObligationV2",
    "LifecyclePhysicalArtifactV2",
    "LifecycleProposalBindingV2",
    "LifecycleProposalReceiptV2",
    "LifecycleSourceReferenceV2",
    "LifecycleStateV2",
    "apply_document_lifecycle_shadow_v2",
    "create_document_lifecycle_shadow_v2_router",
    "derivation_sha256_v2",
    "lifecycle_state_sha256_v2",
    "new_lifecycle_state_v2",
    "obligations_sha256_v2",
    "proposal_projection_sha256_v2",
]
