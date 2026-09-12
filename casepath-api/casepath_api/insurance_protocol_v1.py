from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from .foundation.common import canonical_json_bytes, digest_value, is_sha256
from .foundation.contracts import FoundationModel
from .claim_loop_contracts import (
    CanonicalFactInterpretationV1,
    ClaimObservation,
    EvidenceAction,
)
from .pace_contracts import (
    PACECapabilityOperator,
    PACECompileRequest,
    PACECompileResult,
    PACEVerificationReceipt,
)


MANUAL_NEUTRAL_ASSESSMENT_CAPABILITY = "evidence.obtain_neutral_assessment@1"
SOURCE_REGISTER_CAPABILITY = "source.register@1"
LOCAL_ARTIFACT_REGISTRY_ADAPTER_ID = (
    "casepath.local-artifact-registry-adapter/1.0.0"
)
INSURANCE_AUTHORITY_POLICY_VERSION = "casepath.insurance-action-authority/1.0.0"


class InsuranceProtocolError(ValueError):
    pass


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamp must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include an offset")
    return parsed


def _require_sha256(value: str) -> str:
    if not is_sha256(value):
        raise ValueError("value must be a lowercase SHA-256 digest")
    return value


def _require_self_hash(model: FoundationModel, field: str) -> None:
    payload = model.model_dump(mode="json", exclude={field})
    if digest_value(payload) != getattr(model, field):
        raise ValueError(f"{field} self-hash mismatch")


def sealed_capability_operator_roster_v1() -> tuple[str, ...]:
    """Return the executable enum roster; documentary aliases are forbidden."""

    roster = tuple(member.value for member in PACECapabilityOperator)
    if roster != ("CAPABILITY", "AND", "OR") or len(set(roster)) != len(roster):
        raise InsuranceProtocolError("PACE capability operator roster drifted")
    return roster


class CapabilityExecutionMode(str, Enum):
    MANUAL_EXTERNAL = "manual_external"
    LOCAL_ADAPTER = "local_adapter"


class ActionReceiptStatus(str, Enum):
    COMMITTED = "committed"
    REJECTED = "rejected"
    UNKNOWN = "unknown"
    CANCELLED = "cancelled"


class CapabilityDescriptorV1(FoundationModel):
    contract: Literal["casepath.insurance-capability-descriptor/1.0.0"] = (
        "casepath.insurance-capability-descriptor/1.0.0"
    )
    capability_id: Literal[
        "evidence.obtain_neutral_assessment@1", "source.register@1"
    ]
    execution_mode: CapabilityExecutionMode
    purpose: str = Field(min_length=1, max_length=500)
    non_goals: tuple[str, ...] = Field(min_length=1)
    side_effect_class: Literal["manual_external", "local_reversible_registration"]
    risk_class: Literal["recommendation_only", "bounded_local_effect"]
    idempotency_scope: Literal["case_record_content"]
    policy_version: Literal["casepath.insurance-action-authority/1.0.0"]
    adapter_port_id: Literal["casepath.artifact-registry-port/1.0.0"] | None
    descriptor_sha256: str

    @field_validator("descriptor_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return _require_sha256(value)

    @model_validator(mode="after")
    def validate_descriptor(self) -> CapabilityDescriptorV1:
        if self.capability_id == MANUAL_NEUTRAL_ASSESSMENT_CAPABILITY:
            if (
                self.execution_mode is not CapabilityExecutionMode.MANUAL_EXTERNAL
                or self.side_effect_class != "manual_external"
                or self.risk_class != "recommendation_only"
                or self.adapter_port_id is not None
            ):
                raise ValueError("manual assessment capability cannot be executed")
        elif (
            self.execution_mode is not CapabilityExecutionMode.LOCAL_ADAPTER
            or self.side_effect_class != "local_reversible_registration"
            or self.risk_class != "bounded_local_effect"
            or self.adapter_port_id
            != "casepath.artifact-registry-port/1.0.0"
        ):
            raise ValueError("source registration capability binding is invalid")
        _require_self_hash(self, "descriptor_sha256")
        return self


def capability_catalog_v1() -> tuple[CapabilityDescriptorV1, ...]:
    values = (
        {
            "contract": "casepath.insurance-capability-descriptor/1.0.0",
            "capability_id": MANUAL_NEUTRAL_ASSESSMENT_CAPABILITY,
            "execution_mode": "manual_external",
            "purpose": "Recommend that the handler obtain a neutral assessment.",
            "non_goals": (
                "CasePath does not contact, appoint, or represent an assessor.",
                "This capability never reports that an assessment was performed.",
            ),
            "side_effect_class": "manual_external",
            "risk_class": "recommendation_only",
            "idempotency_scope": "case_record_content",
            "policy_version": INSURANCE_AUTHORITY_POLICY_VERSION,
            "adapter_port_id": None,
        },
        {
            "contract": "casepath.insurance-capability-descriptor/1.0.0",
            "capability_id": SOURCE_REGISTER_CAPABILITY,
            "execution_mode": "local_adapter",
            "purpose": "Register handler-supplied UTF-8 evidence in the local artifact registry.",
            "non_goals": (
                "The adapter does not acquire evidence or contact an external party.",
                "The adapter does not interpret evidence or decide claim state.",
            ),
            "side_effect_class": "local_reversible_registration",
            "risk_class": "bounded_local_effect",
            "idempotency_scope": "case_record_content",
            "policy_version": INSURANCE_AUTHORITY_POLICY_VERSION,
            "adapter_port_id": "casepath.artifact-registry-port/1.0.0",
        },
    )
    return tuple(
        CapabilityDescriptorV1.model_validate(
            {**value, "descriptor_sha256": digest_value(value)}
        )
        for value in values
    )


def capability_catalog_sha256_v1() -> str:
    return digest_value(
        [value.model_dump(mode="json") for value in capability_catalog_v1()]
    )


class StagedArtifactReceiptV1(FoundationModel):
    contract: Literal["casepath.staged-artifact-receipt/1.0.0"] = (
        "casepath.staged-artifact-receipt/1.0.0"
    )
    session_id: str = Field(min_length=1)
    loop_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    record_version: str = Field(min_length=1)
    filename: str = Field(min_length=1, max_length=240)
    media_type: Literal["text/plain; charset=utf-8"]
    byte_count: int = Field(ge=1, le=100_000)
    content_sha256: str
    quarantine_uri: str = Field(pattern=r"^casepath-quarantine://sha256/[0-9a-f]{64}$")
    staged_at: str
    adapter_id: str = Field(min_length=8, max_length=200)
    receipt_sha256: str

    @field_validator("content_sha256", "receipt_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return _require_sha256(value)

    @model_validator(mode="after")
    def validate_receipt(self) -> StagedArtifactReceiptV1:
        _parse_timestamp(self.staged_at)
        if self.filename in {".", ".."} or "/" in self.filename or "\\" in self.filename:
            raise ValueError("staged filename must be a basename")
        _require_self_hash(self, "receipt_sha256")
        return self


class AdapterDryRunReceiptV1(FoundationModel):
    contract: Literal["casepath.artifact-registry-dry-run/1.0.0"] = (
        "casepath.artifact-registry-dry-run/1.0.0"
    )
    source_state_sha256: str
    proposal_sha256: str
    staged_artifact_receipt_sha256: str
    content_sha256: str
    capability_id: Literal["source.register@1"]
    adapter_id: str = Field(min_length=8, max_length=200)
    adapter_implementation_id: str
    adapter_implementation_source_sha256: str
    adapter_implementation_sha256: str
    evaluated_at: str
    would_commit: Literal[True]
    receipt_sha256: str

    @field_validator(
        "source_state_sha256",
        "proposal_sha256",
        "staged_artifact_receipt_sha256",
        "content_sha256",
        "adapter_implementation_source_sha256",
        "adapter_implementation_sha256",
        "receipt_sha256",
    )
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return _require_sha256(value)

    @model_validator(mode="after")
    def validate_receipt(self) -> AdapterDryRunReceiptV1:
        _parse_timestamp(self.evaluated_at)
        if digest_value(
            {
                "contract": "casepath.adapter-implementation-identity/1.1.0",
                "adapter_id": self.adapter_id,
                "implementation_id": self.adapter_implementation_id,
                "implementation_source_sha256": (
                    self.adapter_implementation_source_sha256
                ),
            }
        ) != self.adapter_implementation_sha256:
            raise ValueError("dry-run adapter identity diverged")
        _require_self_hash(self, "receipt_sha256")
        return self


class DecisionProposalV1(FoundationModel):
    contract: Literal["casepath.decision-proposal/1.0.0"] = (
        "casepath.decision-proposal/1.0.0"
    )
    session_id: str
    loop_id: str
    claim_id: str
    record_version: str
    source_revision: int = Field(ge=1)
    source_state_sha256: str
    capability_id: Literal["evidence.obtain_neutral_assessment@1"]
    execution_mode: Literal["manual_external"] = "manual_external"
    proposer: Literal["PACE_CORE_COMPILER_V1"] = "PACE_CORE_COMPILER_V1"
    pace_request: PACECompileRequest
    pace_result: PACECompileResult
    pace_verification: PACEVerificationReceipt
    proposed_at: str
    authoritative: Literal[False] = False
    robust_voi: Literal["NOT_COMPUTED_BY_METHOD_VERSION"] = (
        "NOT_COMPUTED_BY_METHOD_VERSION"
    )
    model_calls: Literal[0] = 0
    provider_calls: Literal[0] = 0
    credential_reads: Literal[0] = 0
    cost_usd: Literal[0.0] = 0.0
    proposal_sha256: str

    @field_validator("source_state_sha256", "proposal_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return _require_sha256(value)

    @model_validator(mode="after")
    def validate_proposal(self) -> DecisionProposalV1:
        _parse_timestamp(self.proposed_at)
        certificate = self.pace_result.certificate
        if (
            certificate is None
            or self.pace_result.terminal_state != "ACTION_SELECTED"
            or self.pace_result.request_sha256 != self.pace_request.request_sha256
            or certificate.action_id != MANUAL_NEUTRAL_ASSESSMENT_CAPABILITY
            or self.pace_verification.certificate_sha256
            != certificate.certificate_sha256
            or not self.pace_verification.valid
        ):
            raise ValueError("proposal is not an independently verified PACE action")
        _require_self_hash(self, "proposal_sha256")
        return self


class DecisionRecordV1(FoundationModel):
    contract: Literal["casepath.decision-record/1.0.0"] = (
        "casepath.decision-record/1.0.0"
    )
    session_id: str
    loop_id: str
    claim_id: str
    record_version: str
    source_revision: int = Field(ge=1)
    source_state_sha256: str
    proposal_sha256: str
    certificate_sha256: str
    authority: Literal["deterministic_claim_loop_authority_v1"]
    authority_policy_version: Literal["casepath.insurance-action-authority/1.0.0"]
    disposition: Literal["AUTHORIZE_LOCAL_REGISTRATION_OF_SUPPLIED_MATERIAL"]
    proposed_capability_id: Literal["evidence.obtain_neutral_assessment@1"]
    authorized_capability_id: Literal["source.register@1"]
    proposed_descriptor_sha256: str
    authorized_descriptor_sha256: str
    capability_catalog_sha256: str
    adapter_id: str = Field(min_length=8, max_length=200)
    adapter_implementation_id: str
    adapter_implementation_source_sha256: str
    adapter_implementation_sha256: str
    compatibility_action: EvidenceAction
    dry_run_receipt: AdapterDryRunReceiptV1
    dry_run_receipt_sha256: str
    staged_artifact_receipt_sha256: str
    decided_at: str
    effective_until: str
    decision_sha256: str

    @field_validator(
        "source_state_sha256",
        "proposal_sha256",
        "certificate_sha256",
        "proposed_descriptor_sha256",
        "authorized_descriptor_sha256",
        "capability_catalog_sha256",
        "adapter_implementation_source_sha256",
        "adapter_implementation_sha256",
        "dry_run_receipt_sha256",
        "staged_artifact_receipt_sha256",
        "decision_sha256",
    )
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return _require_sha256(value)

    @model_validator(mode="after")
    def validate_record(self) -> DecisionRecordV1:
        if _parse_timestamp(self.effective_until) <= _parse_timestamp(self.decided_at):
            raise ValueError("decision authority must have a future expiry")
        catalog = {value.capability_id: value for value in capability_catalog_v1()}
        if (
            self.proposed_descriptor_sha256
            != catalog[self.proposed_capability_id].descriptor_sha256
            or self.authorized_descriptor_sha256
            != catalog[self.authorized_capability_id].descriptor_sha256
            or self.capability_catalog_sha256 != capability_catalog_sha256_v1()
            or self.compatibility_action.bounded_tool_id
            != self.adapter_id
            or self.dry_run_receipt.adapter_id != self.adapter_id
            or self.dry_run_receipt.receipt_sha256
            != self.dry_run_receipt_sha256
            or self.dry_run_receipt.proposal_sha256 != self.proposal_sha256
            or self.dry_run_receipt.staged_artifact_receipt_sha256
            != self.staged_artifact_receipt_sha256
            or digest_value(
                {
                    "contract": "casepath.adapter-implementation-identity/1.1.0",
                    "adapter_id": self.adapter_id,
                    "implementation_id": self.adapter_implementation_id,
                    "implementation_source_sha256": (
                        self.adapter_implementation_source_sha256
                    ),
                }
            )
            != self.adapter_implementation_sha256
        ):
            raise ValueError("decision authority identities are inconsistent")
        _require_self_hash(self, "decision_sha256")
        return self


class ActionIntentV1(FoundationModel):
    contract: Literal["casepath.action-intent/1.0.0"] = (
        "casepath.action-intent/1.0.0"
    )
    session_id: str
    loop_id: str
    claim_id: str
    record_version: str
    source_revision: int = Field(ge=1)
    source_state_sha256: str
    proposal_sha256: str
    decision_sha256: str
    capability_id: Literal["source.register@1"]
    adapter_id: str = Field(min_length=8, max_length=200)
    policy_version: Literal["casepath.insurance-action-authority/1.0.0"]
    capability_catalog_sha256: str
    authorized_descriptor_sha256: str
    adapter_implementation_id: str
    adapter_implementation_source_sha256: str
    adapter_implementation_sha256: str
    compatibility_action_sha256: str
    dry_run_receipt_sha256: str
    staged_artifact_receipt_sha256: str
    content_sha256: str
    effect_idempotency_key: str
    created_at: str
    expires_at: str
    dry_run_passed: Literal[True] = True
    intent_sha256: str

    @field_validator(
        "source_state_sha256",
        "proposal_sha256",
        "decision_sha256",
        "capability_catalog_sha256",
        "authorized_descriptor_sha256",
        "adapter_implementation_source_sha256",
        "adapter_implementation_sha256",
        "compatibility_action_sha256",
        "dry_run_receipt_sha256",
        "staged_artifact_receipt_sha256",
        "content_sha256",
        "effect_idempotency_key",
        "intent_sha256",
    )
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return _require_sha256(value)

    @model_validator(mode="after")
    def validate_intent(self) -> ActionIntentV1:
        if _parse_timestamp(self.expires_at) <= _parse_timestamp(self.created_at):
            raise ValueError("action intent must have a future expiry")
        expected_effect_key = digest_value(
            {
                "contract": "casepath.local-registration-effect/1.0.0",
                "session_id": self.session_id,
                "loop_id": self.loop_id,
                "claim_id": self.claim_id,
                "record_version": self.record_version,
                "capability_id": self.capability_id,
                "content_sha256": self.content_sha256,
            }
        )
        if self.effect_idempotency_key != expected_effect_key:
            raise ValueError("action effect idempotency key is not canonical")
        authorized = {
            value.capability_id: value for value in capability_catalog_v1()
        }[SOURCE_REGISTER_CAPABILITY]
        if (
            self.capability_catalog_sha256 != capability_catalog_sha256_v1()
            or self.authorized_descriptor_sha256
            != authorized.descriptor_sha256
            or digest_value(
                {
                    "contract": "casepath.adapter-implementation-identity/1.1.0",
                    "adapter_id": self.adapter_id,
                    "implementation_id": self.adapter_implementation_id,
                    "implementation_source_sha256": (
                        self.adapter_implementation_source_sha256
                    ),
                }
            )
            != self.adapter_implementation_sha256
        ):
            raise ValueError("action intent implementation identity diverged")
        _require_self_hash(self, "intent_sha256")
        return self


class ActionReceiptV1(FoundationModel):
    contract: Literal["casepath.action-receipt/1.0.0"] = (
        "casepath.action-receipt/1.0.0"
    )
    status: ActionReceiptStatus
    intent_sha256: str
    effect_idempotency_key: str
    capability_id: Literal["source.register@1"]
    adapter_id: str = Field(min_length=8, max_length=200)
    adapter_implementation_id: str
    adapter_implementation_source_sha256: str
    adapter_implementation_sha256: str
    content_sha256: str
    artifact_uri: str | None
    deduplicated_existing_content: bool
    committed_at: str | None
    reason_code: str | None
    model_calls: Literal[0] = 0
    provider_calls: Literal[0] = 0
    credential_reads: Literal[0] = 0
    external_calls: Literal[0] = 0
    cost_usd: Literal[0.0] = 0.0
    receipt_sha256: str

    @field_validator(
        "intent_sha256",
        "effect_idempotency_key",
        "adapter_implementation_source_sha256",
        "adapter_implementation_sha256",
        "content_sha256",
        "receipt_sha256",
    )
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return _require_sha256(value)

    @model_validator(mode="after")
    def validate_receipt(self) -> ActionReceiptV1:
        if digest_value(
            {
                "contract": "casepath.adapter-implementation-identity/1.1.0",
                "adapter_id": self.adapter_id,
                "implementation_id": self.adapter_implementation_id,
                "implementation_source_sha256": (
                    self.adapter_implementation_source_sha256
                ),
            }
        ) != self.adapter_implementation_sha256:
            raise ValueError("action receipt adapter identity diverged")
        if self.status is ActionReceiptStatus.COMMITTED:
            if (
                self.artifact_uri is None
                or self.committed_at is None
                or self.reason_code is not None
            ):
                raise ValueError("committed receipt partition is incomplete")
            _parse_timestamp(self.committed_at)
            if self.artifact_uri != (
                f"casepath-artifact://sha256/{self.content_sha256}"
            ):
                raise ValueError("committed receipt artifact URI is not canonical")
        elif self.artifact_uri is not None or self.committed_at is not None:
            raise ValueError("non-committed receipt cannot claim an artifact")
        elif self.reason_code is None:
            raise ValueError("non-committed receipt requires a reason")
        _require_self_hash(self, "receipt_sha256")
        return self


class SourceObservationV1(FoundationModel):
    contract: Literal["casepath.source-observation/1.0.0"] = (
        "casepath.source-observation/1.0.0"
    )
    session_id: str
    loop_id: str
    claim_id: str
    record_version: str
    action_receipt_sha256: str
    artifact_uri: str
    content_sha256: str
    source_version: str
    page: Literal[1] = 1
    text_start: Literal[0] = 0
    text_end: int = Field(ge=1, le=100_000)
    exact_text_sha256: str
    observed_at: str
    authority: Literal["local_artifact_registry_receipt"]
    observation_sha256: str

    @field_validator(
        "action_receipt_sha256",
        "content_sha256",
        "exact_text_sha256",
        "observation_sha256",
    )
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return _require_sha256(value)

    @model_validator(mode="after")
    def validate_observation(self) -> SourceObservationV1:
        _parse_timestamp(self.observed_at)
        if self.content_sha256 != self.exact_text_sha256:
            raise ValueError("source observation span does not cover canonical content")
        _require_self_hash(self, "observation_sha256")
        return self


class NormalizedAssertionV1(FoundationModel):
    contract: Literal["casepath.normalized-assertion/1.0.0"] = (
        "casepath.normalized-assertion/1.0.0"
    )
    source_observation_sha256: str
    fact_id: str
    evidence_item_id: str
    fact_state: Literal["known", "unknown", "conflicting"]
    normalized_value: str | None
    extraction_method: str
    extraction_method_source_sha256: str
    claim_observation_sha256: str
    claim_observation: ClaimObservation
    canonical_interpretation: CanonicalFactInterpretationV1
    assertion_sha256: str

    @field_validator(
        "source_observation_sha256",
        "extraction_method_source_sha256",
        "claim_observation_sha256",
        "assertion_sha256",
    )
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return _require_sha256(value)

    @model_validator(mode="after")
    def validate_assertion(self) -> NormalizedAssertionV1:
        if (
            self.claim_observation.observation_sha256
            != self.claim_observation_sha256
            or self.canonical_interpretation.observation
            != self.claim_observation
            or self.fact_id != self.claim_observation.fact_id
            or self.evidence_item_id
            != self.claim_observation.evidence_item_id
        ):
            raise ValueError("normalized assertion authority chain diverged")
        _require_self_hash(self, "assertion_sha256")
        return self


class InterpretationV1(FoundationModel):
    contract: Literal["casepath.interpretation/1.0.0"] = (
        "casepath.interpretation/1.0.0"
    )
    assertion_sha256: str
    canonical_interpretation_receipt_sha256: str
    prior_fact_sha256: str
    assertion_catalog_sha256: str
    selected_assertion_id: str | None
    playbook_template_sha256: str
    policy_version: str
    status: Literal["supported", "insufficient", "disputed"]
    interpretation_sha256: str

    @field_validator(
        "assertion_sha256",
        "canonical_interpretation_receipt_sha256",
        "prior_fact_sha256",
        "assertion_catalog_sha256",
        "playbook_template_sha256",
        "interpretation_sha256",
    )
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return _require_sha256(value)

    @model_validator(mode="after")
    def validate_interpretation(self) -> InterpretationV1:
        _require_self_hash(self, "interpretation_sha256")
        return self


class InsuranceProtocolRecordSetV1(FoundationModel):
    contract: Literal["casepath.insurance-protocol-record-set/1.0.0"] = (
        "casepath.insurance-protocol-record-set/1.0.0"
    )
    proposal: DecisionProposalV1
    staged_artifact: StagedArtifactReceiptV1
    decision: DecisionRecordV1
    intent: ActionIntentV1
    action_receipt: ActionReceiptV1 | None = None
    source_observation: SourceObservationV1 | None = None
    normalized_assertion: NormalizedAssertionV1 | None = None
    interpretation: InterpretationV1 | None = None
    record_set_sha256: str

    @field_validator("record_set_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return _require_sha256(value)

    @model_validator(mode="after")
    def validate_chain(self) -> InsuranceProtocolRecordSetV1:
        proposed_at = _parse_timestamp(self.proposal.proposed_at)
        staged_at = _parse_timestamp(self.staged_artifact.staged_at)
        decided_at = _parse_timestamp(self.decision.decided_at)
        expires_at = _parse_timestamp(self.decision.effective_until)
        if (
            self.proposal.session_id != self.decision.session_id
            or self.proposal.session_id != self.intent.session_id
            or self.proposal.loop_id != self.decision.loop_id
            or self.proposal.loop_id != self.intent.loop_id
            or self.proposal.claim_id != self.decision.claim_id
            or self.proposal.claim_id != self.intent.claim_id
            or self.proposal.record_version != self.decision.record_version
            or self.proposal.record_version != self.intent.record_version
            or self.proposal.source_revision != self.decision.source_revision
            or self.proposal.source_revision != self.intent.source_revision
            or self.proposal.source_state_sha256
            != self.decision.source_state_sha256
            or self.proposal.source_state_sha256 != self.intent.source_state_sha256
            or self.decision.proposal_sha256 != self.proposal.proposal_sha256
            or self.intent.proposal_sha256 != self.proposal.proposal_sha256
            or self.intent.decision_sha256 != self.decision.decision_sha256
            or self.decision.staged_artifact_receipt_sha256
            != self.intent.staged_artifact_receipt_sha256
            or self.staged_artifact.receipt_sha256
            != self.intent.staged_artifact_receipt_sha256
            or self.staged_artifact.content_sha256 != self.intent.content_sha256
            or self.staged_artifact.session_id != self.intent.session_id
            or self.staged_artifact.loop_id != self.intent.loop_id
            or self.staged_artifact.claim_id != self.intent.claim_id
            or self.staged_artifact.record_version != self.intent.record_version
            or self.decision.certificate_sha256
            != self.proposal.pace_result.certificate.certificate_sha256
            or self.decision.compatibility_action.action_sha256
            != self.intent.compatibility_action_sha256
            or self.decision.adapter_id != self.intent.adapter_id
            or self.decision.adapter_id
            != self.decision.dry_run_receipt.adapter_id
            or self.decision.adapter_implementation_id
            != self.intent.adapter_implementation_id
            or self.decision.adapter_implementation_id
            != self.decision.dry_run_receipt.adapter_implementation_id
            or self.decision.adapter_implementation_source_sha256
            != self.intent.adapter_implementation_source_sha256
            or self.decision.adapter_implementation_source_sha256
            != self.decision.dry_run_receipt.adapter_implementation_source_sha256
            or self.decision.adapter_implementation_sha256
            != self.intent.adapter_implementation_sha256
            or self.decision.adapter_implementation_sha256
            != self.decision.dry_run_receipt.adapter_implementation_sha256
            or self.decision.dry_run_receipt_sha256
            != self.intent.dry_run_receipt_sha256
            or not proposed_at <= staged_at <= decided_at
            or self.decision.dry_run_receipt.evaluated_at
            != self.decision.decided_at
            or self.intent.created_at != self.decision.decided_at
            or self.intent.expires_at != self.decision.effective_until
        ):
            raise ValueError("proposal, decision and intent chain diverged")
        trailing = (
            self.action_receipt,
            self.source_observation,
            self.normalized_assertion,
            self.interpretation,
        )
        if self.action_receipt is None:
            if any(value is not None for value in trailing[1:]):
                raise ValueError("epistemic records require an action receipt")
        elif self.action_receipt.status is not ActionReceiptStatus.COMMITTED:
            if any(value is not None for value in trailing[1:]):
                raise ValueError("noncommitted action cannot carry epistemic records")
        elif (
            self.source_observation is None
            and any(value is not None for value in trailing[2:])
        ) or (
            self.normalized_assertion is None
            and self.interpretation is not None
        ):
            raise ValueError("committed epistemic records must form an exact prefix")
        if self.action_receipt is not None:
            if (
                self.action_receipt.intent_sha256 != self.intent.intent_sha256
                or self.action_receipt.effect_idempotency_key
                != self.intent.effect_idempotency_key
                or self.action_receipt.capability_id != self.intent.capability_id
                or self.action_receipt.adapter_id != self.intent.adapter_id
                or self.action_receipt.content_sha256 != self.intent.content_sha256
                or self.action_receipt.adapter_implementation_id
                != self.intent.adapter_implementation_id
                or self.action_receipt.adapter_implementation_source_sha256
                != self.intent.adapter_implementation_source_sha256
                or self.action_receipt.adapter_implementation_sha256
                != self.intent.adapter_implementation_sha256
            ):
                raise ValueError("action receipt does not bind its intent")
            if (
                self.action_receipt.status is ActionReceiptStatus.COMMITTED
                and not decided_at
                <= _parse_timestamp(self.action_receipt.committed_at or "")
                < expires_at
            ):
                raise ValueError("committed action receipt is outside its authority")
        if self.source_observation is not None:
            assert self.action_receipt is not None
            if (
                self.source_observation.action_receipt_sha256
                != self.action_receipt.receipt_sha256
                or self.source_observation.content_sha256
                != self.action_receipt.content_sha256
                or self.source_observation.source_version
                != self.intent.record_version
                or self.source_observation.session_id != self.intent.session_id
                or self.source_observation.loop_id != self.intent.loop_id
                or self.source_observation.claim_id != self.intent.claim_id
                or self.source_observation.record_version
                != self.intent.record_version
                or self.source_observation.artifact_uri
                != self.action_receipt.artifact_uri
                or _parse_timestamp(self.source_observation.observed_at)
                < _parse_timestamp(self.action_receipt.committed_at or "")
            ):
                raise ValueError("source observation does not bind the action receipt")
        if self.normalized_assertion is not None:
            assert self.source_observation is not None
            if (
                self.normalized_assertion.source_observation_sha256
                != self.source_observation.observation_sha256
                or self.normalized_assertion.fact_state
                != self.normalized_assertion.claim_observation.fact_state
                or self.normalized_assertion.normalized_value
                != self.normalized_assertion.claim_observation.normalized_value
            ):
                raise ValueError("normalized assertion does not bind its source")
        if self.interpretation is not None:
            assert self.normalized_assertion is not None
            if (
                self.interpretation.assertion_sha256
                != self.normalized_assertion.assertion_sha256
                or self.interpretation.canonical_interpretation_receipt_sha256
                != self.normalized_assertion.canonical_interpretation.receipt_sha256
                or self.interpretation.prior_fact_sha256
                != self.normalized_assertion.canonical_interpretation.prior_fact_sha256
                or self.interpretation.assertion_catalog_sha256
                != self.normalized_assertion.canonical_interpretation.assertion_catalog_sha256
                or self.interpretation.selected_assertion_id
                != self.normalized_assertion.canonical_interpretation.selected_assertion_id
            ):
                raise ValueError("interpretation does not bind its assertion authority")
        _require_self_hash(self, "record_set_sha256")
        return self


class VersionedCaseStateV1(FoundationModel):
    """Replay-derived insurance thin-waist projection; never writable authority."""

    contract: Literal["casepath.versioned-case-state/1.0.0"] = (
        "casepath.versioned-case-state/1.0.0"
    )
    session_id: str
    loop_id: str
    claim_id: str
    record_version: str
    base_revision: int = Field(ge=1)
    base_state_sha256: str
    last_event_sha256: str
    protocol_status: Literal[
        "not_started",
        "intent_journaled",
        "execution_started",
        "dispatch_unknown",
        "cancelled",
        "receipt_recorded",
        "source_observed",
        "assertion_normalized",
        "interpreted",
        "replanned",
    ]
    protocol_event_sha256s: tuple[str, ...]
    record_set: InsuranceProtocolRecordSetV1 | None = None
    pending_intent_sha256: str | None = None
    next_action: EvidenceAction | None = None
    terminal_mode: Literal["finalize", "abstain"] | None = None
    decision_ready_packet_sha256: str | None = None
    correction_count: int = Field(default=0, ge=0)
    projection_sha256: str

    @field_validator(
        "base_state_sha256",
        "last_event_sha256",
        "pending_intent_sha256",
        "decision_ready_packet_sha256",
        "projection_sha256",
    )
    @classmethod
    def validate_optional_hash(cls, value: str | None) -> str | None:
        return _require_sha256(value) if value is not None else None

    @field_validator("protocol_event_sha256s")
    @classmethod
    def validate_event_hashes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("protocol event identities must be unique")
        return tuple(_require_sha256(item) for item in value)

    @model_validator(mode="after")
    def validate_projection(self) -> VersionedCaseStateV1:
        if self.protocol_status == "not_started":
            if self.record_set is not None or self.protocol_event_sha256s:
                raise ValueError("not-started projection cannot claim protocol records")
        elif self.record_set is None or not self.protocol_event_sha256s:
            raise ValueError("active protocol projection requires replay evidence")
        if self.pending_intent_sha256 is not None and (
            self.record_set is None
            or self.pending_intent_sha256 != self.record_set.intent.intent_sha256
        ):
            raise ValueError("pending intent differs from replayed protocol records")
        if self.protocol_status in {"cancelled", "replanned"} and (
            self.pending_intent_sha256 is not None
        ):
            raise ValueError("terminal protocol projection cannot claim a pending intent")
        _require_self_hash(self, "projection_sha256")
        return self


def hash_record_set_v1(payload: dict[str, Any]) -> InsuranceProtocolRecordSetV1:
    return InsuranceProtocolRecordSetV1.model_validate_json(
        canonical_json_bytes(
            {**payload, "record_set_sha256": digest_value(payload)}
        )
    )


__all__ = [
    "ActionIntentV1",
    "AdapterDryRunReceiptV1",
    "ActionReceiptStatus",
    "ActionReceiptV1",
    "CapabilityDescriptorV1",
    "DecisionProposalV1",
    "DecisionRecordV1",
    "INSURANCE_AUTHORITY_POLICY_VERSION",
    "InsuranceProtocolError",
    "InsuranceProtocolRecordSetV1",
    "InterpretationV1",
    "LOCAL_ARTIFACT_REGISTRY_ADAPTER_ID",
    "MANUAL_NEUTRAL_ASSESSMENT_CAPABILITY",
    "NormalizedAssertionV1",
    "SOURCE_REGISTER_CAPABILITY",
    "SourceObservationV1",
    "StagedArtifactReceiptV1",
    "VersionedCaseStateV1",
    "capability_catalog_v1",
    "capability_catalog_sha256_v1",
    "hash_record_set_v1",
    "sealed_capability_operator_roster_v1",
]
