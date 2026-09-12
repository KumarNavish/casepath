from __future__ import annotations

from datetime import datetime
from enum import Enum
import math
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from .foundation.common import canonical_json_bytes, digest_text, digest_value, is_sha256
from .foundation.contracts import FoundationModel


_INTERNAL_EVENT_PREFIX = "@casepath-claim-loop."


def claim_loop_internal_event_key_v1(
    *,
    session_id: str,
    loop_id: str,
    client_idempotency_key: str,
    request_type: str,
    request_sha256: str,
    event_kind: str,
) -> str:
    """Derive a non-public journal key from an exact parent request."""

    if not is_sha256(request_sha256):
        raise ValueError("parent client request identity must be a SHA-256 digest")
    if not all(
        (session_id, loop_id, client_idempotency_key, request_type, event_kind)
    ):
        raise ValueError("internal event key domain is incomplete")
    return _INTERNAL_EVENT_PREFIX + digest_value(
        {
            "contract": "casepath.claim-loop-internal-event-key/1.0.0",
            "session_id": session_id,
            "loop_id": loop_id,
            "client_idempotency_key": client_idempotency_key,
            "request_type": request_type,
            "request_sha256": request_sha256,
            "event_kind": event_kind,
        }
    )


class ClaimLoopPhase(str, Enum):
    COMPILED = "compiled"
    AWAITING_OBSERVATION = "awaiting_observation"
    DISPATCHING = "dispatching"
    REPLANNING = "replanning"
    DECISION_READY = "decision_ready"
    ABSTAINED = "abstained"


class ObligationStatus(str, Enum):
    ACTIVE = "active"
    CONDITIONAL = "conditional"
    SATISFIED = "satisfied"
    CONTRADICTED = "contradicted"
    BLOCKED = "blocked"


class SufficiencyStatus(str, Enum):
    INSUFFICIENT = "insufficient"
    DECISION_READY = "decision_ready"
    ABSTAIN = "abstain"


class ToolResultStatus(str, Enum):
    OBSERVED = "observed"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class ClaimSourceRef(FoundationModel):
    contract: Literal["casepath.claim-source-reference/1.0.0"] = (
        "casepath.claim-source-reference/1.0.0"
    )
    source_id: str = Field(min_length=1, max_length=200)
    source_sha256: str
    source_version: str = Field(min_length=1, max_length=160)
    locator_kind: Literal["text_quote", "metadata_field"]
    page: int | None = Field(default=None, ge=1)
    sanitized_excerpt: str | None = Field(default=None, min_length=1, max_length=4000)
    text_start: int | None = Field(default=None, ge=0)
    text_end: int | None = Field(default=None, ge=0)
    field: str | None = Field(default=None, min_length=1, max_length=200)
    value: str | int | float | bool | None = None
    span_sha256: str
    adapter_id: str = Field(min_length=1, max_length=200)

    @field_validator("source_sha256", "span_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError("source hashes must be lowercase SHA-256 digests")
        return value

    @model_validator(mode="after")
    def validate_locator(self) -> ClaimSourceRef:
        if self.locator_kind == "text_quote":
            if (
                self.page is None
                or self.sanitized_excerpt is None
                or self.text_start is None
                or self.text_end is None
                or self.text_end <= self.text_start
            ):
                raise ValueError(
                    "text_quote requires page, excerpt and a nonempty exact span"
                )
            if self.field is not None or self.value is not None:
                raise ValueError("text_quote cannot carry metadata fields")
        elif (
            self.field is None
            or self.value is None
            or self.text_start is not None
            or self.text_end is not None
        ):
            raise ValueError("metadata_field requires only field and value")
        return self


class ClaimObservation(FoundationModel):
    contract: Literal["casepath.claim-observation/1.0.0"] = (
        "casepath.claim-observation/1.0.0"
    )
    observation_id: str = Field(min_length=1, max_length=200)
    fact_id: str = Field(min_length=1, max_length=200)
    evidence_item_id: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1, max_length=4000)
    fact_state: Literal["known", "unknown", "conflicting"]
    normalized_value: str | None = Field(default=None, max_length=120)
    explanation: str = Field(min_length=1, max_length=4000)
    evidence_status: Literal[
        "provided_sufficient", "provided_insufficient", "unavailable"
    ]
    source_refs: tuple[ClaimSourceRef, ...] = Field(min_length=1, max_length=20)
    observed_at: str = Field(min_length=1, max_length=80)
    observation_sha256: str

    @field_validator("observation_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError("observation_sha256 must be a lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def validate_self_hash(self) -> ClaimObservation:
        payload = self.model_dump(mode="json", exclude={"observation_sha256"})
        if digest_value(payload) != self.observation_sha256:
            raise ValueError("observation self-hash mismatch")
        return self


class AcquisitionReceiptV1(FoundationModel):
    """Durable server-owned result of one bounded evidence acquisition.

    The receipt is persisted before any fact interpretation.  It contains no
    fact state, sufficiency label, or evidence authority: those are derived by
    the separately bound interpreter from the immutable acquired bytes.
    """

    contract: Literal[
        "casepath.acquisition-receipt/1.1.0",
        "casepath.source-registration-compatibility-receipt/1.0.0",
    ] = "casepath.acquisition-receipt/1.1.0"
    status: ToolResultStatus
    session_id: str
    loop_id: str
    record_version: str
    action_id: str
    action_sha256: str
    dispatch_sha256: str
    dispatch_generation: int = Field(ge=1)
    adapter_id: str
    adapter_implementation_id: str
    adapter_implementation_source_sha256: str
    adapter_implementation_sha256: str
    source_locator: str = Field(min_length=1, max_length=2000)
    acquisition_request_sha256: str
    acquired_at: str
    content_kind: Literal["canonical_utf8_text_v1"] | None = None
    mime_type: Literal["text/plain; charset=utf-8"] | None = None
    raw_byte_count: int | None = Field(default=None, ge=1, le=100_000)
    raw_bytes_sha256: str | None = None
    sanitizer_implementation: Literal["identity_utf8_v1"] | None = None
    sanitized_content: str | None = Field(default=None, min_length=1, max_length=100_000)
    sanitized_content_sha256: str | None = None
    artifact_page_count: Literal[1] | None = None
    reason_code: str | None = Field(default=None, min_length=1, max_length=300)
    model_calls: Literal[0] = 0
    provider_calls: Literal[0] = 0
    provider_credentials_read: Literal[False] = False
    cost_usd: float = Field(default=0.0, ge=0.0, le=0.0)
    receipt_sha256: str

    @field_validator(
        "action_sha256",
        "dispatch_sha256",
        "adapter_implementation_source_sha256",
        "adapter_implementation_sha256",
        "acquisition_request_sha256",
        "raw_bytes_sha256",
        "sanitized_content_sha256",
        "receipt_sha256",
    )
    @classmethod
    def validate_hash(cls, value: str | None) -> str | None:
        if value is not None and not is_sha256(value):
            raise ValueError("acquisition hashes must be lowercase SHA-256 digests")
        return value

    @model_validator(mode="after")
    def validate_self_hash(self) -> AcquisitionReceiptV1:
        if self.action_id != f"action.{self.action_sha256}":
            raise ValueError("acquisition action identity is not content-addressed")
        implementation_identity = {
            "contract": "casepath.adapter-implementation-identity/1.1.0",
            "adapter_id": self.adapter_id,
            "implementation_id": self.adapter_implementation_id,
            "implementation_source_sha256": (
                self.adapter_implementation_source_sha256
            ),
        }
        if digest_value(implementation_identity) != self.adapter_implementation_sha256:
            raise ValueError("acquisition adapter implementation identity diverged")
        request_identity = {
            "contract": (
                "casepath.source-registration-request/1.0.0"
                if self.contract
                == "casepath.source-registration-compatibility-receipt/1.0.0"
                else "casepath.acquisition-request/1.1.0"
            ),
            "session_id": self.session_id,
            "loop_id": self.loop_id,
            "record_version": self.record_version,
            "action_id": self.action_id,
            "action_sha256": self.action_sha256,
            "dispatch_sha256": self.dispatch_sha256,
            "dispatch_generation": self.dispatch_generation,
            "adapter_id": self.adapter_id,
            "adapter_implementation_id": self.adapter_implementation_id,
            "adapter_implementation_source_sha256": (
                self.adapter_implementation_source_sha256
            ),
            "adapter_implementation_sha256": self.adapter_implementation_sha256,
            "source_locator": self.source_locator,
        }
        if digest_value(request_identity) != self.acquisition_request_sha256:
            raise ValueError("acquisition request identity diverged")
        content_fields = (
            self.content_kind,
            self.mime_type,
            self.raw_byte_count,
            self.raw_bytes_sha256,
            self.sanitizer_implementation,
            self.sanitized_content,
            self.sanitized_content_sha256,
            self.artifact_page_count,
        )
        if self.status is ToolResultStatus.OBSERVED:
            if any(value is None for value in content_fields) or self.reason_code is not None:
                raise ValueError("observed acquisition content partition is incomplete")
            assert self.sanitized_content is not None
            raw = self.sanitized_content.encode("utf-8")
            if (
                self.raw_byte_count != len(raw)
                or self.raw_bytes_sha256 != digest_text(self.sanitized_content)
                or self.sanitized_content_sha256 != digest_text(self.sanitized_content)
            ):
                raise ValueError("observed acquisition bytes are not canonical")
        elif any(value is not None for value in content_fields) or self.reason_code is None:
            raise ValueError("non-observed acquisition cannot carry content")
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if digest_value(payload) != self.receipt_sha256:
            raise ValueError("acquisition receipt self-hash mismatch")
        return self


class CanonicalFactInterpretationV1(FoundationModel):
    """Server-owned bounded interpretation of one immutable raw artifact."""

    contract: Literal["casepath.canonical-fact-interpretation/1.2.0"] = (
        "casepath.canonical-fact-interpretation/1.2.0"
    )
    action_id: str
    action_sha256: str
    fact_id: str
    evidence_item_id: str
    acquisition_receipt_sha256: str
    raw_artifact_sha256: str
    prior_fact_sha256: str
    assertion_catalog_sha256: str
    selected_assertion_id: str | None
    observation: ClaimObservation
    implementation: str = Field(min_length=8, max_length=160)
    implementation_source_sha256: str
    model_calls: Literal[0] = 0
    provider_calls: Literal[0] = 0
    provider_credentials_read: Literal[False] = False
    cost_usd: float = Field(default=0.0, ge=0.0, le=0.0)
    receipt_sha256: str

    @field_validator(
        "action_sha256",
        "acquisition_receipt_sha256",
        "raw_artifact_sha256",
        "prior_fact_sha256",
        "assertion_catalog_sha256",
        "implementation_source_sha256",
        "receipt_sha256",
    )
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError("interpretation hashes must be SHA-256 digests")
        return value

    @model_validator(mode="after")
    def validate_self_hash(self) -> CanonicalFactInterpretationV1:
        if (
            self.action_id != f"action.{self.action_sha256}"
            or self.raw_artifact_sha256 != self.acquisition_receipt_sha256
            or self.observation.fact_id != self.fact_id
            or self.observation.evidence_item_id != self.evidence_item_id
        ):
            raise ValueError("interpretation is not bound to its action and observation")
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if digest_value(payload) != self.receipt_sha256:
            raise ValueError("interpretation self-hash mismatch")
        return self


class ObligationState(FoundationModel):
    obligation_id: str
    process_node_ids: tuple[str, ...]
    fact_id: str
    status: ObligationStatus
    evidence_status: str
    mandatory_now: bool
    source_ref_ids: tuple[str, ...]


class EvidenceAction(FoundationModel):
    contract: Literal["casepath.evidence-action/1.0.0"] = (
        "casepath.evidence-action/1.0.0"
    )
    action_id: str
    action_kind: Literal["acquire", "validate", "clarify", "replan", "register"]
    process_node_id: str
    evidence_item_id: str
    fact_id: str
    title: str
    bounded_tool_id: str | None = None
    action_sha256: str

    @model_validator(mode="after")
    def validate_self_hash(self) -> EvidenceAction:
        # The content digest defines action_id, so neither identity field can be
        # part of the preimage without creating an impossible fixed point.
        payload = self.model_dump(
            mode="json", exclude={"action_id", "action_sha256"}
        )
        if digest_value(payload) != self.action_sha256:
            raise ValueError("evidence action self-hash mismatch")
        if self.action_id != f"action.{self.action_sha256}":
            raise ValueError("action_id is not content-addressed")
        return self


class ActionHistoryEntry(FoundationModel):
    action: EvidenceAction
    outcome: Literal["observed", "unavailable", "failed", "unknown"]
    observation_sha256: str | None = None
    recorded_at: str


class ProvenanceEdge(FoundationModel):
    observation_sha256: str
    source_ref_id: str
    fact_id: str
    evidence_item_id: str


class ProjectionLedgerEntry(FoundationModel):
    """One record-driven state update in authoritative journal order."""

    kind: Literal["observation", "correction"]
    record_sha256: str
    artifact_receipt_sha256: str
    recorded_at: str

    @field_validator("record_sha256", "artifact_receipt_sha256")
    @classmethod
    def validate_record_hash(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError("projection ledger record must be a SHA-256 digest")
        return value


class SufficiencyState(FoundationModel):
    status: SufficiencyStatus
    unresolved_mandatory_obligation_ids: tuple[str, ...]
    contradicted_obligation_ids: tuple[str, ...]
    provenance_complete: bool


class CorrectionScope(FoundationModel):
    claim_ids: tuple[str, ...] = Field(min_length=1)
    fact_ids: tuple[str, ...] = Field(min_length=1)
    evidence_item_ids: tuple[str, ...] = Field(min_length=1)


class CorrectionEffect(FoundationModel):
    fact_id: str
    evidence_item_id: str
    value: str
    fact_state: Literal["known", "unknown", "conflicting"]
    normalized_value: str | None = None
    explanation: str
    evidence_status: Literal["provided_sufficient", "provided_insufficient"]


class CorrectionArtifactReceipt(FoundationModel):
    contract: Literal["casepath.correction-artifact-receipt/1.0.0"] = (
        "casepath.correction-artifact-receipt/1.0.0"
    )
    session_id: str
    loop_id: str
    parent_state_sha256: str
    record_version: str
    target_claim_id: str
    target_action_id: str
    source_artifact_receipt_sha256: str
    source_observation_sha256: str
    source_ref: ClaimSourceRef
    authority_adapter_id: str = Field(min_length=1, max_length=200)
    authority_content: str = Field(min_length=1, max_length=10_000)
    authority_content_sha256: str
    authority_source_ref: ClaimSourceRef
    scope: CorrectionScope
    proposed_effect: CorrectionEffect
    before_fact_sha256: str
    before_evidence_sha256: str
    expected_after_fact_sha256: str
    expected_after_evidence_sha256: str
    unrelated_facts_before_sha256: str
    unrelated_facts_after_sha256: str
    rollback_fact_sha256: str
    rollback_evidence_sha256: str
    issuer_kind: Literal[
        "deterministic_tool", "human_optional", "model_optional"
    ]
    issuer_id: str = Field(min_length=1, max_length=200)
    provenance_note: str = Field(min_length=1, max_length=2_000)
    issued_at: str
    expires_at: str | None = None
    model_calls: Literal[0] = 0
    provider_calls: Literal[0] = 0
    provider_credentials_read: Literal[False] = False
    cost_usd: float = Field(default=0.0, ge=0.0, le=0.0)
    receipt_sha256: str

    @field_validator(
        "parent_state_sha256",
        "source_artifact_receipt_sha256",
        "source_observation_sha256",
        "authority_content_sha256",
        "before_fact_sha256",
        "before_evidence_sha256",
        "expected_after_fact_sha256",
        "expected_after_evidence_sha256",
        "unrelated_facts_before_sha256",
        "unrelated_facts_after_sha256",
        "rollback_fact_sha256",
        "rollback_evidence_sha256",
        "receipt_sha256",
    )
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError("correction artifact hashes must be SHA-256 digests")
        return value

    @model_validator(mode="after")
    def validate_self_hash(self) -> CorrectionArtifactReceipt:
        if self.scope.claim_ids != (self.target_claim_id,):
            raise ValueError("correction artifact claim scope is not singleton")
        if self.scope.fact_ids != (self.proposed_effect.fact_id,):
            raise ValueError("correction artifact fact scope is not singleton")
        if self.scope.evidence_item_ids != (
            self.proposed_effect.evidence_item_id,
        ):
            raise ValueError("correction artifact evidence scope is not singleton")
        if self.rollback_fact_sha256 != self.before_fact_sha256:
            raise ValueError("correction rollback does not bind the before fact")
        if self.rollback_evidence_sha256 != self.before_evidence_sha256:
            raise ValueError("correction rollback does not bind the before evidence")
        expected_content = canonical_json_bytes(
            self.proposed_effect.model_dump(mode="json")
        ).decode("utf-8")
        if (
            self.authority_content != expected_content
            or self.authority_content_sha256 != digest_text(expected_content)
            or self.authority_source_ref.adapter_id != self.authority_adapter_id
            or self.authority_source_ref.source_sha256
            != self.authority_content_sha256
            or self.authority_source_ref.source_version != self.record_version
            or self.authority_source_ref.locator_kind != "text_quote"
            or self.authority_source_ref.page != 1
            or self.authority_source_ref.text_start != 0
            or self.authority_source_ref.text_end != len(expected_content)
            or self.authority_source_ref.sanitized_excerpt != expected_content
            or self.authority_source_ref.span_sha256
            != self.authority_content_sha256
        ):
            raise ValueError(
                "correction effect is not exactly bound to its authority artifact"
            )
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if digest_value(payload) != self.receipt_sha256:
            raise ValueError("correction artifact self-hash mismatch")
        return self


class ScopedCorrection(FoundationModel):
    contract: Literal["casepath.scoped-correction/1.0.0"] = (
        "casepath.scoped-correction/1.0.0"
    )
    correction_id: str
    correction_artifact_receipt_sha256: str
    source_artifact_receipt_sha256: str
    source_ref: ClaimSourceRef
    record_version: str
    scope: CorrectionScope
    effect: CorrectionEffect
    effective_at: str
    expires_at: str | None = None
    # V1 defines expires_at as the last instant at which the correction may be
    # admitted.  Once admitted, the event-sourced effect persists until a later
    # scoped correction supersedes it.  This avoids time-dependent replay.
    expiry_semantics: Literal["admission_deadline_persistent_effect"] = (
        "admission_deadline_persistent_effect"
    )
    correction_sha256: str

    @field_validator(
        "correction_artifact_receipt_sha256",
        "source_artifact_receipt_sha256",
    )
    @classmethod
    def validate_artifact_receipt_hash(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError("correction artifact receipt must be a SHA-256 digest")
        return value

    @model_validator(mode="after")
    def validate_self_hash(self) -> ScopedCorrection:
        payload = self.model_dump(
            mode="json", exclude={"correction_id", "correction_sha256"}
        )
        if digest_value(payload) != self.correction_sha256:
            raise ValueError("correction self-hash mismatch")
        if self.correction_id != f"correction.{self.correction_sha256}":
            raise ValueError("correction_id is not content-addressed")
        if self.effect.fact_id not in self.scope.fact_ids:
            raise ValueError("correction effect escapes fact scope")
        if self.effect.evidence_item_id not in self.scope.evidence_item_ids:
            raise ValueError("correction effect escapes evidence scope")
        return self


class NativeProposalEvidenceRefV1(FoundationModel):
    """One source pointer retained with its fallible model-assigned role."""

    role: Literal["support", "contrary", "correction", "context"]
    source_ref: ClaimSourceRef


class NativeProposalReadingV1(FoundationModel):
    """A reading in a later native proposal snapshot, never a world fact."""

    reading_id: str = Field(min_length=1, max_length=200)
    need_id: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    answer: str | None = Field(default=None, max_length=4000)
    state: Literal[
        "missing",
        "partial",
        "pending",
        "received",
        "contested",
        "conditional",
        "withdrawn",
        "uncertain",
    ]
    until: str | None = Field(default=None, max_length=80)
    evidence: tuple[NativeProposalEvidenceRefV1, ...] = Field(
        min_length=1, max_length=20
    )
    proposal_item_sha256: str

    @field_validator("proposal_item_sha256")
    @classmethod
    def validate_item_hash(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError("native reading item hash must be a SHA-256")
        return value

    @field_validator("until")
    @classmethod
    def validate_until(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("native reading until must be aware") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("native reading until must be aware")
        return value

    @model_validator(mode="after")
    def validate_reading(self) -> NativeProposalReadingV1:
        if self.description != self.description.strip() or (
            self.answer is not None and self.answer != self.answer.strip()
        ):
            raise ValueError("native reading text is not normalized")
        if self.until is not None and self.state != "pending":
            raise ValueError("native reading until requires pending state")
        identities = [
            digest_value(value.model_dump(mode="json")) for value in self.evidence
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("native reading evidence is duplicated")
        return self


class NativeProposalActionV1(FoundationModel):
    """A display-only action from the latest fallible proposal."""

    action_id: str = Field(min_length=1, max_length=200)
    action_index: int = Field(ge=0, le=15)
    purpose: str = Field(min_length=1, max_length=4000)
    audience: Literal["internal", "provider", "claimant", "authority"]
    requested_contents: tuple[str, ...] = Field(min_length=1, max_length=8)
    source_warrant_refs: tuple[ClaimSourceRef, ...] = Field(
        min_length=1, max_length=20
    )

    @model_validator(mode="after")
    def validate_action(self) -> NativeProposalActionV1:
        if (
            self.purpose != self.purpose.strip()
            or any(
                not value.strip() or value != value.strip() or len(value) > 240
                for value in self.requested_contents
            )
            or len(self.requested_contents) != len(set(self.requested_contents))
        ):
            raise ValueError("native proposal action content is invalid")
        return self


class NativeProposalActionDispositionV1(FoundationModel):
    """Lifecycle relation to one action in the accepted initial proposal."""

    prior_action_index: int = Field(ge=0, le=15)
    prior_need_id: str = Field(min_length=1, max_length=200)
    prior_fact_id: str = Field(min_length=1, max_length=200)
    prior_evidence_item_id: str = Field(min_length=1, max_length=200)
    disposition: Literal["revised", "retired"]
    reason: str = Field(min_length=1, max_length=4000)
    source_refs: tuple[ClaimSourceRef, ...] = Field(min_length=1, max_length=20)
    replacement_action_id: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_replacement(self) -> NativeProposalActionDispositionV1:
        if (self.disposition == "revised") != (
            self.replacement_action_id is not None
        ):
            raise ValueError("native action disposition replacement is invalid")
        if self.reason != self.reason.strip():
            raise ValueError("native action disposition reason is invalid")
        return self


class NativeProposalRevisionV1(FoundationModel):
    """One journaled, source-bound and explicitly provisional replan snapshot."""

    contract: Literal["casepath.native-proposal-revision/1.0.0"] = (
        "casepath.native-proposal-revision/1.0.0"
    )
    claim_id: str = Field(min_length=1, max_length=200)
    loop_id: str = Field(min_length=1, max_length=200)
    prior_cycle_id: str = Field(min_length=1, max_length=200)
    cycle_id: str = Field(min_length=1, max_length=200)
    source_prefix_sha256: str
    proposal_sha256: str
    parent_revision: int = Field(ge=1)
    parent_state_sha256: str
    readings: tuple[NativeProposalReadingV1, ...] = Field(max_length=16)
    actions: tuple[NativeProposalActionV1, ...] = Field(max_length=16)
    action_dispositions: tuple[NativeProposalActionDispositionV1, ...] = Field(
        min_length=1, max_length=16
    )
    provisional: Literal[True] = True
    canonical_fact_effect: None = None
    readiness_effect: None = None
    recorded_at: str = Field(min_length=1, max_length=80)
    revision_sha256: str

    @field_validator(
        "source_prefix_sha256",
        "proposal_sha256",
        "parent_state_sha256",
        "revision_sha256",
    )
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError("native proposal revision hashes must be SHA-256")
        return value

    @field_validator("recorded_at")
    @classmethod
    def validate_recorded_at(cls, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("native revision recorded_at must be aware") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("native revision recorded_at must be aware")
        return value

    @model_validator(mode="after")
    def validate_revision(self) -> NativeProposalRevisionV1:
        reading_ids = [value.reading_id for value in self.readings]
        action_ids = [value.action_id for value in self.actions]
        action_indices = [value.action_index for value in self.actions]
        prior_indices = [value.prior_action_index for value in self.action_dispositions]
        prior_need_ids = [value.prior_need_id for value in self.action_dispositions]
        if (
            len(reading_ids) != len(set(reading_ids))
            or len(action_ids) != len(set(action_ids))
            or action_indices != list(range(len(action_indices)))
            or len(prior_indices) != len(set(prior_indices))
            or len(prior_need_ids) != len(set(prior_need_ids))
        ):
            raise ValueError("native proposal revision identities collide")
        replacements = {
            value.replacement_action_id
            for value in self.action_dispositions
            if value.replacement_action_id is not None
        }
        if replacements != set(action_ids):
            raise ValueError("native revision actions lack exact disposition lineage")
        if self.cycle_id == self.prior_cycle_id:
            raise ValueError("native proposal revision repeats its prior cycle")
        model_state = {
            "received": "supported",
            "partial": "partial",
            "pending": "pending",
            "uncertain": "unresolved",
        }
        for index, value in enumerate(self.readings):
            if value.state not in model_state:
                raise ValueError("native revision reading state is not snapshot-only")
            material = {
                "cycle_id": self.cycle_id,
                "wire_index": index,
                "question": value.description,
                "answer": value.answer,
                "state": model_state[value.state],
                "source_ref_ids": [
                    item.source_ref.span_sha256 for item in value.evidence
                ],
            }
            if value.until is not None:
                material["until"] = value.until
            identity = digest_value(material)
            if (
                value.proposal_item_sha256 != identity
                or value.reading_id != "native-reading." + identity
                or value.need_id != "native-snapshot-need." + identity
            ):
                raise ValueError("native revision reading identity is invalid")
        for value in self.actions:
            material = {
                "cycle_id": self.cycle_id,
                "action_index": value.action_index,
                "purpose": value.purpose,
                "proposed_action": {
                    "audience": value.audience,
                    "enabled": True,
                    "requested_contents": list(value.requested_contents),
                },
                "source_ref_ids": [
                    item.span_sha256 for item in value.source_warrant_refs
                ],
            }
            if value.action_id != "native-action." + digest_value(material):
                raise ValueError("native revision action identity is invalid")
        payload = self.model_dump(mode="json", exclude={"revision_sha256"})
        if digest_value(payload) != self.revision_sha256:
            # Revisions journaled before ``until`` existed hashed readings
            # without that key.  A null deadline retains that exact identity.
            legacy_payload = {
                **payload,
                "readings": [
                    {
                        key: item
                        for key, item in reading.items()
                        if key != "until" or item is not None
                    }
                    for reading in payload["readings"]
                ],
            }
            if digest_value(legacy_payload) != self.revision_sha256:
                raise ValueError("native proposal revision self-hash mismatch")
        return self


class ToolArtifactReceipt(FoundationModel):
    contract: Literal["casepath.tool-artifact-receipt/1.1.0"] = (
        "casepath.tool-artifact-receipt/1.1.0"
    )
    session_id: str
    loop_id: str
    action_id: str
    action_sha256: str
    dispatch_sha256: str
    adapter_id: str
    acquisition_receipt_sha256: str
    acquisition_receipt: AcquisitionReceiptV1
    artifact_source_version: str
    # V1 deliberately accepts only single-page canonical text.  A flat byte
    # string cannot prove a page-local locator for a multi-page artifact.
    artifact_page_count: Literal[1] = 1
    sanitized_content: str = Field(min_length=1, max_length=100_000)
    raw_artifact_sha256: str
    interpretation: CanonicalFactInterpretationV1
    observation: ClaimObservation
    registered_at: str
    model_calls: Literal[0] = 0
    provider_calls: Literal[0] = 0
    provider_credentials_read: Literal[False] = False
    cost_usd: float = Field(default=0.0, ge=0.0, le=0.0)
    receipt_sha256: str

    @field_validator(
        "action_sha256",
        "dispatch_sha256",
        "acquisition_receipt_sha256",
        "raw_artifact_sha256",
        "receipt_sha256",
    )
    @classmethod
    def validate_receipt_hash(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError("tool artifact hashes must be lowercase SHA-256 digests")
        return value

    @model_validator(mode="after")
    def validate_self_hash(self) -> ToolArtifactReceipt:
        if (
            self.acquisition_receipt.status is not ToolResultStatus.OBSERVED
            or self.acquisition_receipt_sha256
            != self.acquisition_receipt.receipt_sha256
            or self.raw_artifact_sha256 != self.acquisition_receipt_sha256
            or self.acquisition_receipt.session_id != self.session_id
            or self.acquisition_receipt.loop_id != self.loop_id
            or self.acquisition_receipt.action_id != self.action_id
            or self.acquisition_receipt.action_sha256 != self.action_sha256
            or self.acquisition_receipt.dispatch_sha256 != self.dispatch_sha256
            or self.acquisition_receipt.adapter_id != self.adapter_id
            or self.acquisition_receipt.record_version
            != self.artifact_source_version
            or self.acquisition_receipt.artifact_page_count
            != self.artifact_page_count
            or self.acquisition_receipt.sanitized_content
            != self.sanitized_content
            or self.interpretation.acquisition_receipt_sha256
            != self.acquisition_receipt_sha256
            or self.interpretation.raw_artifact_sha256
            != self.raw_artifact_sha256
            or self.interpretation.action_id != self.action_id
            or self.interpretation.action_sha256 != self.action_sha256
            or self.interpretation.observation != self.observation
        ):
            raise ValueError("tool artifact interpretation binding is invalid")
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if digest_value(payload) != self.receipt_sha256:
            raise ValueError("tool artifact receipt self-hash mismatch")
        if self.action_id != f"action.{self.action_sha256}":
            raise ValueError("tool artifact action identity is not content-addressed")
        return self


class CorrectionReuseReceipt(FoundationModel):
    contract: Literal["casepath.correction-reuse-receipt/1.0.0"] = (
        "casepath.correction-reuse-receipt/1.0.0"
    )
    correction_sha256: str
    correction_artifact_receipt_sha256: str
    source_artifact_receipt_sha256: str
    target_matching_artifact_receipt_sha256: str
    source_application_event_sha256: str
    source_application_state_sha256: str
    source_session_id: str
    source_loop_id: str
    target_session_id: str
    target_loop_id: str
    target_claim_id: str
    record_version: str
    target_parent_state_sha256: str
    target_before_fact_sha256: str
    target_before_evidence_sha256: str
    target_expected_after_fact_sha256: str
    target_expected_after_evidence_sha256: str
    target_unrelated_facts_before_sha256: str
    target_unrelated_facts_after_sha256: str
    applied_fact_ids: tuple[str, ...]
    applied_evidence_item_ids: tuple[str, ...]
    receipt_sha256: str

    @field_validator(
        "correction_artifact_receipt_sha256",
        "source_artifact_receipt_sha256",
        "target_matching_artifact_receipt_sha256",
        "source_application_event_sha256",
        "source_application_state_sha256",
        "target_parent_state_sha256",
        "target_before_fact_sha256",
        "target_before_evidence_sha256",
        "target_expected_after_fact_sha256",
        "target_expected_after_evidence_sha256",
        "target_unrelated_facts_before_sha256",
        "target_unrelated_facts_after_sha256",
    )
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError("correction reuse hashes must be SHA-256 digests")
        return value

    @model_validator(mode="after")
    def validate_self_hash(self) -> CorrectionReuseReceipt:
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if digest_value(payload) != self.receipt_sha256:
            raise ValueError("reuse receipt self-hash mismatch")
        return self


class AcceptedRoleArtifactsV1(FoundationModel):
    contract: Literal["casepath.accepted-role-artifacts/1.0.0"] = (
        "casepath.accepted-role-artifacts/1.0.0"
    )
    canonical_facts: tuple[dict[str, Any], ...]
    orchestrator_plan: dict[str, Any]
    document_source_integrity: dict[str, Any]
    process_decision_mapping: dict[str, Any]
    evidence_checklist: dict[str, Any]
    final_claim_brief_audit: dict[str, Any]
    receipt_sha256: str

    @field_validator("receipt_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError("accepted role artifact hash must be SHA-256")
        return value

    @model_validator(mode="after")
    def validate_self_hash(self) -> AcceptedRoleArtifactsV1:
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if digest_value(payload) != self.receipt_sha256:
            raise ValueError("accepted role artifacts self-hash mismatch")
        return self


class AcceptedCycleArtifactsV1(FoundationModel):
    contract: Literal["casepath.accepted-cycle-artifacts/1.0.0"] = (
        "casepath.accepted-cycle-artifacts/1.0.0"
    )
    facts: tuple[dict[str, Any], ...]
    process: dict[str, Any]
    checklist: dict[str, Any]
    final_claim_brief: dict[str, Any]
    verification: dict[str, Any]
    role_artifacts: AcceptedRoleArtifactsV1
    receipt_sha256: str

    @field_validator("receipt_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError("accepted cycle artifact hash must be SHA-256")
        return value

    @model_validator(mode="after")
    def validate_self_hash(self) -> AcceptedCycleArtifactsV1:
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if digest_value(payload) != self.receipt_sha256:
            raise ValueError("accepted cycle artifacts self-hash mismatch")
        return self


class SixAgentCycleReceipt(FoundationModel):
    contract: Literal["casepath.six-agent-cycle-receipt/1.0.0"] = (
        "casepath.six-agent-cycle-receipt/1.0.0"
    )
    source_run_id: str
    loop_id: str
    cycle_kind: Literal["source_acceptance", "observation", "correction"]
    prior_state_sha256: str | None
    trigger_sha256: str
    orchestration_id: str
    playbook_template_sha256: str
    observable_package_sha256: str
    facts_sha256: str
    process_sha256: str
    checklist_sha256: str
    accepted_cycle_artifacts_sha256: str
    final_claim_brief_sha256: str
    verification_sha256: str
    graph_audit_sha256: str
    agent_ids: tuple[str, ...]
    agent_receipt_sha256s: tuple[str, ...]
    deterministic_gate_ids: tuple[str, ...]
    gate_receipt_sha256s: tuple[str, ...]
    execution_implementation: Literal["compiled_langgraph_stategraph"]
    transport_mode: Literal[
        "accepted_source_run",
        "openrouter",
        "deterministic_test_double",
    ]
    model_calls: int = Field(ge=0)
    provider_calls: int = Field(ge=0)
    credential_access_status: Literal[
        "none_due_to_zero_provider_calls",
        "not_measured",
        "receipt_bound",
    ]
    credential_access_receipt_sha256s: tuple[str, ...] = ()
    cost_status: Literal["exact", "unknown"]
    cost_usd: float | None = Field(default=None, ge=0.0)
    receipt_sha256: str

    @field_validator(
        "playbook_template_sha256",
        "prior_state_sha256",
        "trigger_sha256",
        "observable_package_sha256",
        "facts_sha256",
        "process_sha256",
        "checklist_sha256",
        "accepted_cycle_artifacts_sha256",
        "final_claim_brief_sha256",
        "verification_sha256",
        "graph_audit_sha256",
        "receipt_sha256",
    )
    @classmethod
    def validate_hash(cls, value: str | None) -> str | None:
        if value is not None and not is_sha256(value):
            raise ValueError("cycle receipt hashes must be lowercase SHA-256 digests")
        return value

    @field_validator(
        "agent_receipt_sha256s",
        "gate_receipt_sha256s",
        "credential_access_receipt_sha256s",
    )
    @classmethod
    def validate_hash_roster(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not is_sha256(value) for value in values):
            raise ValueError("cycle roster hashes must be lowercase SHA-256 digests")
        return values

    @model_validator(mode="after")
    def validate_cycle(self) -> SixAgentCycleReceipt:
        expected_agents = (
            "canonical_facts",
            "orchestrator_plan",
            "document_source_integrity",
            "process_decision_mapping",
            "evidence_checklist",
            "final_claim_brief_audit",
        )
        expected_gates = (
            "deterministic_process_gate",
            "deterministic_evidence_gate",
            "whole_playbook_gate",
        )
        if self.agent_ids != expected_agents or len(self.agent_receipt_sha256s) != 6:
            raise ValueError("cycle receipt does not bind all six agent roles")
        if (
            self.deterministic_gate_ids != expected_gates
            or len(self.gate_receipt_sha256s) != 3
        ):
            raise ValueError("cycle receipt does not bind all three gates")
        if (self.cycle_kind == "source_acceptance") != (
            self.prior_state_sha256 is None
        ):
            raise ValueError("cycle receipt prior-state boundary is invalid")
        if self.cost_status == "exact":
            if self.cost_usd is None or not math.isfinite(self.cost_usd):
                raise ValueError("exact cycle cost must be finite")
        elif self.cost_usd is not None:
            raise ValueError("unknown cycle cost cannot carry a numeric value")
        if self.credential_access_status == "receipt_bound":
            if not self.credential_access_receipt_sha256s:
                raise ValueError("credential access lacks its dedicated receipt")
        elif self.credential_access_receipt_sha256s:
            raise ValueError("credential receipts contradict access status")
        if self.provider_calls == 0 and (
            self.credential_access_status
            != "none_due_to_zero_provider_calls"
            or self.cost_status != "exact"
            or self.cost_usd != 0.0
        ):
            raise ValueError("zero-provider cycle activity is inconsistent")
        if self.provider_calls > 0 and self.credential_access_status == (
            "none_due_to_zero_provider_calls"
        ):
            raise ValueError("provider calls require measured or unknown credentials")
        if self.transport_mode == "deterministic_test_double" and (
            self.model_calls != 0
            or self.provider_calls != 0
            or self.credential_access_status
            != "none_due_to_zero_provider_calls"
            or self.cost_status != "exact"
            or self.cost_usd != 0.0
        ):
            raise ValueError("deterministic graph transport cannot claim provider activity")
        if (
            self.transport_mode == "accepted_source_run"
            and self.cycle_kind != "source_acceptance"
        ):
            raise ValueError(
                "accepted source transport is restricted to source acceptance"
            )
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if digest_value(payload) != self.receipt_sha256:
            raise ValueError("cycle receipt self-hash mismatch")
        return self


class BoundActivity(FoundationModel):
    contract: Literal["casepath.bound-activity/1.0.0"] = (
        "casepath.bound-activity/1.0.0"
    )
    scope: Literal[
        "upstream_source_run",
        "source_acceptance",
        "incremental_loop",
        "total_bound",
    ]
    graph_traversal_count: int = Field(ge=0)
    model_calls: int = Field(ge=0)
    provider_calls: int = Field(ge=0)
    activity_receipt_sha256s: tuple[str, ...] = ()
    execution_identity_sha256s: tuple[str, ...] = ()
    credential_access_status: Literal[
        "none_due_to_zero_provider_calls",
        "not_measured",
        "receipt_bound",
    ]
    credential_access_receipt_sha256s: tuple[str, ...] = ()
    cost_status: Literal["exact", "unknown"]
    cost_usd: float | None = Field(default=None, ge=0.0)

    @field_validator(
        "activity_receipt_sha256s",
        "execution_identity_sha256s",
        "credential_access_receipt_sha256s",
    )
    @classmethod
    def validate_receipt_hashes(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not is_sha256(value) for value in values):
            raise ValueError("activity provenance must contain SHA-256 receipts")
        return values

    @model_validator(mode="after")
    def validate_activity(self) -> BoundActivity:
        if (
            self.graph_traversal_count
            != len(set(self.execution_identity_sha256s))
            or len(self.execution_identity_sha256s)
            != self.graph_traversal_count
        ):
            raise ValueError("activity traversal identities are not unique")
        if self.graph_traversal_count > 0 and not self.activity_receipt_sha256s:
            raise ValueError("activity traversal lacks provenance receipts")
        if self.cost_status == "exact":
            if self.cost_usd is None or not math.isfinite(self.cost_usd):
                raise ValueError("exact activity cost must be finite")
        elif self.cost_usd is not None:
            raise ValueError("unknown activity cost cannot carry a numeric value")
        if self.credential_access_status == "receipt_bound":
            if not self.credential_access_receipt_sha256s:
                raise ValueError("credential activity lacks a dedicated receipt")
        elif self.credential_access_receipt_sha256s:
            raise ValueError("credential receipts contradict activity status")
        if self.provider_calls == 0 and (
            self.credential_access_status
            != "none_due_to_zero_provider_calls"
            or self.cost_status != "exact"
            or self.cost_usd != 0.0
        ):
            raise ValueError("zero-provider bound activity is inconsistent")
        if self.provider_calls > 0 and self.credential_access_status == (
            "none_due_to_zero_provider_calls"
        ):
            raise ValueError("provider activity cannot claim zero credential boundary")
        return self


class ClaimLoopState(FoundationModel):
    contract: Literal["casepath.claim-loop-state/1.0.0"] = (
        "casepath.claim-loop-state/1.0.0"
    )
    session_id: str
    loop_id: str
    claim_id: str
    source_run_id: str
    record_version: str
    revision: int = Field(ge=1)
    phase: ClaimLoopPhase
    accepted_artifacts_sha256: str
    accepted_artifacts: dict[str, Any]
    observations: tuple[ClaimObservation, ...]
    projection_ledger: tuple[ProjectionLedgerEntry, ...]
    facts: tuple[dict[str, Any], ...]
    fact_catalog_sha256: str
    process: dict[str, Any]
    checklist: dict[str, Any]
    accepted_cycle_artifacts_sha256: str
    accepted_cycle_artifacts: AcceptedCycleArtifactsV1
    deterministic_gate_receipt: dict[str, Any]
    six_agent_verification: dict[str, Any]
    six_agent_graph_audit: dict[str, Any]
    six_agent_cycle_receipt: SixAgentCycleReceipt
    upstream_source_run_activity: BoundActivity
    source_acceptance_activity: BoundActivity
    incremental_loop_activity: BoundActivity
    total_bound_activity: BoundActivity
    obligations: tuple[ObligationState, ...]
    uncertainty_fact_ids: tuple[str, ...]
    blocking_uncertainty_fact_ids: tuple[str, ...]
    selected_action: EvidenceAction | None
    action_history: tuple[ActionHistoryEntry, ...]
    sufficiency: SufficiencyState
    provenance_edges: tuple[ProvenanceEdge, ...]
    corrections: tuple[ScopedCorrection, ...]
    correction_reuse_receipts: tuple[CorrectionReuseReceipt, ...]
    native_proposal_revisions: tuple[NativeProposalRevisionV1, ...] = ()
    active_dispatch_sha256: str | None
    active_dispatch_owner: str | None
    active_dispatch_expires_at: str | None
    terminal_mode: Literal["finalize", "abstain"] | None
    abstain_reason: str | None
    last_event_sha256: str
    state_sha256: str

    @field_validator(
        "accepted_artifacts_sha256",
        "fact_catalog_sha256",
        "accepted_cycle_artifacts_sha256",
        "last_event_sha256",
        "state_sha256",
        "active_dispatch_sha256",
    )
    @classmethod
    def validate_hash(cls, value: str | None) -> str | None:
        if value is not None and not is_sha256(value):
            raise ValueError("state hashes must be lowercase SHA-256 digests")
        return value

    @model_validator(mode="after")
    def validate_self_hash(self) -> ClaimLoopState:
        active_fields = (
            self.active_dispatch_sha256,
            self.active_dispatch_owner,
            self.active_dispatch_expires_at,
        )
        if any(value is None for value in active_fields) != all(
            value is None for value in active_fields
        ):
            raise ValueError("active dispatch lease fields must be atomic")
        if self.active_dispatch_sha256 is not None and (
            self.selected_action is None or self.phase is not ClaimLoopPhase.DISPATCHING
        ):
            raise ValueError("active dispatch requires selected action and dispatch phase")
        if (
            self.accepted_cycle_artifacts_sha256
            != self.accepted_cycle_artifacts.receipt_sha256
            or tuple(self.facts) != self.accepted_cycle_artifacts.facts
            or self.process != self.accepted_cycle_artifacts.process
            or self.checklist != self.accepted_cycle_artifacts.checklist
            or self.six_agent_verification
            != self.accepted_cycle_artifacts.verification
            or self.six_agent_cycle_receipt.accepted_cycle_artifacts_sha256
            != self.accepted_cycle_artifacts.receipt_sha256
            or self.six_agent_cycle_receipt.final_claim_brief_sha256
            != digest_value(self.accepted_cycle_artifacts.final_claim_brief)
        ):
            raise ValueError("state does not bind its accepted cycle artifacts")
        if (
            self.six_agent_verification.get("valid") is not True
            or self.six_agent_verification.get("computed") is not True
            or digest_value(self.six_agent_verification)
            != self.six_agent_cycle_receipt.verification_sha256
        ):
            raise ValueError("state does not bind the accepted cycle verification")
        audit = self.six_agent_graph_audit
        if (
            digest_value(audit) != self.six_agent_cycle_receipt.graph_audit_sha256
            or audit.get("orchestration_id")
            != self.six_agent_cycle_receipt.orchestration_id
            or audit.get("all_required_agents_contributed") is not True
            or not isinstance(audit.get("execution_topology"), dict)
            or audit["execution_topology"].get("implementation")
            != "compiled_langgraph_stategraph"
        ):
            raise ValueError("state does not bind its complete StateGraph audit")
        agents = audit.get("agents")
        gates = audit.get("deterministic_gates")
        if not isinstance(agents, list) or not isinstance(gates, list):
            raise ValueError("state graph audit receipt rosters are missing")
        agent_by_id = {
            value.get("agent_id"): value
            for value in agents
            if isinstance(value, dict) and isinstance(value.get("agent_id"), str)
        }
        gate_by_id = {
            value.get("agent_id"): value
            for value in gates
            if isinstance(value, dict) and isinstance(value.get("agent_id"), str)
        }
        if (
            len(agent_by_id) != len(agents)
            or len(gate_by_id) != len(gates)
            or set(agent_by_id) != set(self.six_agent_cycle_receipt.agent_ids)
            or set(gate_by_id)
            != set(self.six_agent_cycle_receipt.deterministic_gate_ids)
            or tuple(
                digest_value(agent_by_id[key])
                for key in self.six_agent_cycle_receipt.agent_ids
            )
            != self.six_agent_cycle_receipt.agent_receipt_sha256s
            or tuple(
                digest_value(gate_by_id[key])
                for key in self.six_agent_cycle_receipt.deterministic_gate_ids
            )
            != self.six_agent_cycle_receipt.gate_receipt_sha256s
        ):
            raise ValueError("state graph audit role/gate bindings diverged")
        audit_transport = audit.get("transport_mode")
        if audit_transport not in {"openrouter", "deterministic_test_double"}:
            raise ValueError("state graph audit transport is invalid")
        expected_actor_type = (
            "deterministic_structured_agent"
            if audit_transport == "deterministic_test_double"
            else "nemotron_agent"
        )
        if any(
            value.get("actor_type") != expected_actor_type
            for value in agent_by_id.values()
        ):
            raise ValueError("state graph agent transport label is inaccurate")
        if audit_transport == "deterministic_test_double" and (
            audit.get("model_assisted") is not False
            or audit.get("model") is not None
            or any(
                value.get("model") is not None
                or value.get("provider") is not None
                or value.get("call_count") != 0
                for value in agent_by_id.values()
            )
        ):
            raise ValueError("deterministic state graph claims model activity")
        if audit_transport == "openrouter" and audit.get(
            "model_assisted"
        ) is not True:
            raise ValueError("model state graph omits model assistance")
        upstream_activity = self.upstream_source_run_activity
        source_activity = self.source_acceptance_activity
        incremental_activity = self.incremental_loop_activity
        total_activity = self.total_bound_activity
        activities = (upstream_activity, source_activity, incremental_activity)
        source_reuses_upstream = bool(
            upstream_activity.graph_traversal_count == 1
            and source_activity.graph_traversal_count == 1
            and upstream_activity.execution_identity_sha256s
            == source_activity.execution_identity_sha256s
        )
        if source_reuses_upstream and (
            upstream_activity.model_calls != source_activity.model_calls
            or upstream_activity.provider_calls != source_activity.provider_calls
            or upstream_activity.cost_status != source_activity.cost_status
            or upstream_activity.cost_usd != source_activity.cost_usd
        ):
            raise ValueError("aliased source activity metrics diverged")
        accounted = (
            (upstream_activity, incremental_activity)
            if source_reuses_upstream
            else activities
        )
        expected_execution_identities = tuple(
            dict.fromkeys(
                identity
                for value in activities
                for identity in value.execution_identity_sha256s
            )
        )
        if (
            upstream_activity.scope != "upstream_source_run"
            or source_activity.scope != "source_acceptance"
            or incremental_activity.scope != "incremental_loop"
            or total_activity.scope != "total_bound"
            or total_activity.graph_traversal_count
            != len(expected_execution_identities)
            or total_activity.execution_identity_sha256s
            != expected_execution_identities
            or total_activity.model_calls
            != sum(value.model_calls for value in accounted)
            or total_activity.provider_calls
            != sum(value.provider_calls for value in accounted)
            or total_activity.activity_receipt_sha256s
            != (
                upstream_activity.activity_receipt_sha256s
                + source_activity.activity_receipt_sha256s
                + incremental_activity.activity_receipt_sha256s
            )
            or total_activity.credential_access_receipt_sha256s
            != (
                upstream_activity.credential_access_receipt_sha256s
                + source_activity.credential_access_receipt_sha256s
                + incremental_activity.credential_access_receipt_sha256s
            )
        ):
            raise ValueError("bound activity totals diverged")
        expected_credential_status = (
            "receipt_bound"
            if any(
                value.credential_access_status == "receipt_bound"
                for value in accounted
            )
            else "not_measured"
            if any(
                value.credential_access_status == "not_measured"
                for value in accounted
            )
            else "none_due_to_zero_provider_calls"
        )
        exact_costs = [
            value.cost_usd
            for value in accounted
            if value.cost_status == "exact"
        ]
        expected_cost_status = (
            "exact"
            if len(exact_costs) == len(accounted)
            else "unknown"
        )
        expected_cost_usd = (
            round(sum(value for value in exact_costs if value is not None), 8)
            if expected_cost_status == "exact"
            else None
        )
        if (
            total_activity.credential_access_status
            != expected_credential_status
            or total_activity.cost_status != expected_cost_status
            or total_activity.cost_usd != expected_cost_usd
        ):
            raise ValueError("bound activity completeness diverged")
        payload = self.model_dump(mode="json", exclude={"state_sha256"})
        # Journals created before native proposal revisions existed did not
        # hash an empty field.  Preserve their exact state identities; the
        # field enters the hash only after the first revision event.
        if not self.native_proposal_revisions:
            payload.pop("native_proposal_revisions", None)
        if digest_value(payload) != self.state_sha256:
            # Preserve state identities for journals whose native revision
            # readings predate the nullable ``until`` field.
            legacy_payload = {
                **payload,
                "native_proposal_revisions": [
                    {
                        **revision,
                        "readings": [
                            {
                                key: item
                                for key, item in reading.items()
                                if key != "until" or item is not None
                            }
                            for reading in revision["readings"]
                        ],
                    }
                    for revision in payload.get("native_proposal_revisions", [])
                ],
            }
            if digest_value(legacy_payload) != self.state_sha256:
                raise ValueError("claim loop state self-hash mismatch")
        return self


class ClaimLoopEvent(FoundationModel):
    contract: Literal["casepath.claim-loop-event/1.0.0"] = (
        "casepath.claim-loop-event/1.0.0"
    )
    session_id: str
    loop_id: str
    sequence: int = Field(ge=1)
    previous_event_sha256: str | None
    event_type: Literal[
        "LOOP_CREATED",
        "ACTION_SELECTED",
        "OBSERVATION_INGESTED",
        "EVIDENCE_PROPOSAL_REJECTED",
        "TOOL_UNAVAILABLE",
        "ACTION_DISPATCH_STARTED",
        "DISPATCH_UNKNOWN",
        "CORRECTION_APPLIED",
        "CORRECTION_REUSED",
        "NATIVE_PROPOSAL_REVISION_RECORDED",
    ]
    idempotency_key: str
    command_sha256: str
    command: dict[str, Any]
    created_at: str
    event_sha256: str
    resulting_state_sha256: str

    @field_validator(
        "previous_event_sha256",
        "command_sha256",
        "event_sha256",
        "resulting_state_sha256",
    )
    @classmethod
    def validate_hash(cls, value: str | None) -> str | None:
        if value is not None and not is_sha256(value):
            raise ValueError("event hashes must be lowercase SHA-256 digests")
        return value

    @model_validator(mode="after")
    def validate_event_hash(self) -> ClaimLoopEvent:
        if digest_value(self.command) != self.command_sha256:
            raise ValueError("event command hash mismatch")
        payload = self.model_dump(
            mode="json", exclude={"event_sha256", "resulting_state_sha256"}
        )
        if digest_value(payload) != self.event_sha256:
            raise ValueError("event self-hash mismatch")
        return self


class InsuranceProtocolClaimLoopEventV1(FoundationModel):
    """Versioned successor envelope for additive insurance transitions."""

    contract: Literal["casepath.claim-loop-protocol-event/1.0.0"] = (
        "casepath.claim-loop-protocol-event/1.0.0"
    )
    session_id: str
    loop_id: str
    sequence: int = Field(ge=1)
    previous_event_sha256: str | None
    event_type: Literal[
        "ACTION_DISPATCH_STARTED",
        "PROTOCOL_EXECUTION_STARTED",
        "PROTOCOL_ACTION_RECEIPT_RECORDED",
        "PROTOCOL_SOURCE_OBSERVATION_RECORDED",
        "PROTOCOL_ASSERTION_NORMALIZED",
        "PROTOCOL_INTERPRETATION_RECORDED",
        "PROTOCOL_INTENT_CANCELLED",
        "DISPATCH_UNKNOWN",
        "OBSERVATION_INGESTED",
    ]
    idempotency_key: str
    command_sha256: str
    command: dict[str, Any]
    created_at: str
    event_sha256: str
    resulting_state_sha256: str

    @field_validator(
        "previous_event_sha256",
        "command_sha256",
        "event_sha256",
        "resulting_state_sha256",
    )
    @classmethod
    def validate_hash(cls, value: str | None) -> str | None:
        if value is not None and not is_sha256(value):
            raise ValueError("protocol event hashes must be SHA-256 digests")
        return value

    @model_validator(mode="after")
    def validate_event_hash(self) -> InsuranceProtocolClaimLoopEventV1:
        if digest_value(self.command) != self.command_sha256:
            raise ValueError("protocol event command hash mismatch")
        payload = self.model_dump(
            mode="json", exclude={"event_sha256", "resulting_state_sha256"}
        )
        if digest_value(payload) != self.event_sha256:
            raise ValueError("protocol event self-hash mismatch")
        return self


class InsuranceProtocolClaimLoopEventV2(FoundationModel):
    """Successor envelope for the interpretation-bound replan receipt."""

    contract: Literal["casepath.claim-loop-protocol-event/2.0.0"] = (
        "casepath.claim-loop-protocol-event/2.0.0"
    )
    session_id: str
    loop_id: str
    sequence: int = Field(ge=1)
    previous_event_sha256: str
    event_type: Literal["PROTOCOL_REPLAN_RECEIPT_RECORDED"]
    idempotency_key: str
    command_sha256: str
    command: dict[str, Any]
    created_at: str
    event_sha256: str
    resulting_state_sha256: str

    @field_validator(
        "previous_event_sha256",
        "command_sha256",
        "event_sha256",
        "resulting_state_sha256",
    )
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError("protocol-v2 event hashes must be SHA-256 digests")
        return value

    @model_validator(mode="after")
    def validate_event_hash(self) -> InsuranceProtocolClaimLoopEventV2:
        if digest_value(self.command) != self.command_sha256:
            raise ValueError("protocol-v2 event command hash mismatch")
        payload = self.model_dump(
            mode="json", exclude={"event_sha256", "resulting_state_sha256"}
        )
        if digest_value(payload) != self.event_sha256:
            raise ValueError("protocol-v2 event self-hash mismatch")
        return self


ClaimLoopEventLike = (
    ClaimLoopEvent
    | InsuranceProtocolClaimLoopEventV1
    | InsuranceProtocolClaimLoopEventV2
)


def load_claim_loop_event_v1(value: Any) -> ClaimLoopEventLike:
    if not isinstance(value, dict):
        raise ValueError("claim-loop event must be an object")
    contract = value.get("contract")
    if contract == "casepath.claim-loop-event/1.0.0":
        return ClaimLoopEvent.model_validate(value)
    if contract == "casepath.claim-loop-protocol-event/1.0.0":
        return InsuranceProtocolClaimLoopEventV1.model_validate(value)
    if contract == "casepath.claim-loop-protocol-event/2.0.0":
        return InsuranceProtocolClaimLoopEventV2.model_validate(value)
    raise ValueError("claim-loop event contract is unsupported")


class ClaimLoopCommandReceipt(FoundationModel):
    contract: Literal["casepath.claim-loop-command-receipt/1.0.0"] = (
        "casepath.claim-loop-command-receipt/1.0.0"
    )
    loop_id: str
    idempotency_key: str
    event_sha256: str
    state_sha256: str
    revision: int = Field(ge=1)
    receipt_sha256: str

    @field_validator("event_sha256", "state_sha256", "receipt_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError("command receipt hashes must be lowercase SHA-256 digests")
        return value

    @model_validator(mode="after")
    def validate_self_hash(self) -> ClaimLoopCommandReceipt:
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if digest_value(payload) != self.receipt_sha256:
            raise ValueError("command receipt self-hash mismatch")
        return self


class DecisionReadyPacket(FoundationModel):
    contract: Literal["casepath.decision-ready-packet/1.0.0"] = (
        "casepath.decision-ready-packet/1.0.0"
    )
    loop_id: str
    claim_id: str
    phase: ClaimLoopPhase
    terminal_mode: Literal["finalize", "abstain"] | None
    current_overlay: dict[str, Any]
    selected_action: EvidenceAction | None
    obligations: tuple[ObligationState, ...]
    sufficiency: SufficiencyState
    provenance_edges: tuple[ProvenanceEdge, ...]
    deterministic_gate_receipt_sha256: str
    six_agent_cycle_receipt_sha256: str
    accepted_cycle_artifacts_sha256: str
    accepted_cycle_artifacts: AcceptedCycleArtifactsV1
    source_state_sha256: str
    packet_sha256: str

    @model_validator(mode="after")
    def validate_self_hash(self) -> DecisionReadyPacket:
        if self.selected_action is not None:
            raise ValueError("terminal decision packet cannot carry an action")
        if self.phase is ClaimLoopPhase.DECISION_READY:
            if (
                self.terminal_mode != "finalize"
                or self.sufficiency.status is not SufficiencyStatus.DECISION_READY
            ):
                raise ValueError("decision-ready packet is internally inconsistent")
        elif self.phase is ClaimLoopPhase.ABSTAINED:
            if (
                self.terminal_mode != "abstain"
                or self.sufficiency.status is not SufficiencyStatus.ABSTAIN
            ):
                raise ValueError("abstention packet is internally inconsistent")
        else:
            raise ValueError("decision packet requires a terminal claim-loop phase")
        if (
            self.accepted_cycle_artifacts_sha256
            != self.accepted_cycle_artifacts.receipt_sha256
        ):
            raise ValueError("decision packet accepted-cycle binding is invalid")
        payload = self.model_dump(mode="json", exclude={"packet_sha256"})
        if digest_value(payload) != self.packet_sha256:
            raise ValueError("decision-ready packet self-hash mismatch")
        return self

    @field_validator(
        "deterministic_gate_receipt_sha256",
        "six_agent_cycle_receipt_sha256",
        "accepted_cycle_artifacts_sha256",
        "source_state_sha256",
    )
    @classmethod
    def validate_bound_hash(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError("decision packet hashes must be lowercase SHA-256 digests")
        return value


__all__ = [
    "AcquisitionReceiptV1",
    "AcceptedCycleArtifactsV1",
    "AcceptedRoleArtifactsV1",
    "ActionHistoryEntry",
    "BoundActivity",
    "CanonicalFactInterpretationV1",
    "ClaimLoopCommandReceipt",
    "ClaimLoopEvent",
    "ClaimLoopEventLike",
    "ClaimLoopPhase",
    "ClaimLoopState",
    "ClaimObservation",
    "ClaimSourceRef",
    "CorrectionArtifactReceipt",
    "CorrectionEffect",
    "CorrectionReuseReceipt",
    "CorrectionScope",
    "DecisionReadyPacket",
    "EvidenceAction",
    "InsuranceProtocolClaimLoopEventV1",
    "ObligationState",
    "ObligationStatus",
    "ProvenanceEdge",
    "ProjectionLedgerEntry",
    "ScopedCorrection",
    "SixAgentCycleReceipt",
    "SufficiencyState",
    "SufficiencyStatus",
    "ToolResultStatus",
    "ToolArtifactReceipt",
    "load_claim_loop_event_v1",
]
