from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .common import digest_value, is_sha256


class FoundationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PrivacyState(str, Enum):
    SAFE_TO_PROCESS = "safe_to_process"
    BLOCKED_FOR_UNRESOLVED_IDENTIFIERS = "blocked_for_unresolved_identifiers"
    ALREADY_SYNTHETIC_OR_ANONYMIZED = "already_synthetic_or_anonymized"


class KnowledgeState(str, Enum):
    CANDIDATE = "candidate"
    QUARANTINED = "quarantined"
    REVIEWED = "reviewed"
    REGRESSION_PASSED = "regression_passed"
    PROMOTED = "promoted"
    SUPERSEDED = "superseded"
    ROLLED_BACK = "rolled_back"


class ReviewerAuthorityType(str, Enum):
    NON_HUMAN_TEST_FIXTURE = "non_human_test_fixture"
    QUALIFIED_REVIEWER = "qualified_reviewer"
    ORGANIZATIONAL_APPROVER = "organizational_approver"


class SourceLocator(FoundationModel):
    artifact_id: str = Field(min_length=1)
    artifact_sha256: str
    locator_kind: str = Field(min_length=1)
    page: int | None = Field(default=None, ge=1)
    exact_text: str | None = None
    text_start: int | None = Field(default=None, ge=0)
    text_end: int | None = Field(default=None, ge=0)
    image_region: dict[str, Any] | None = None
    source_version: str | None = None
    effective_date: str | None = None
    json_pointer: str | None = None
    canonical_value_sha256: str | None = None

    @field_validator("artifact_sha256", "canonical_value_sha256")
    @classmethod
    def validate_hash(cls, value: str | None) -> str | None:
        if value is not None and not is_sha256(value):
            raise ValueError("must be a lowercase SHA-256 digest")
        return value

    @model_validator(mode="after")
    def validate_span(self) -> SourceLocator:
        if self.text_start is not None and self.text_end is not None:
            if self.text_end < self.text_start:
                raise ValueError("text_end must be greater than or equal to text_start")
        return self


class IntakeAttachment(FoundationModel):
    artifact_id: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    source_sha256: str
    text: str = ""
    locators: tuple[SourceLocator, ...] = ()

    @field_validator("source_sha256")
    @classmethod
    def validate_source_hash(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError("source_sha256 must be a lowercase SHA-256 digest")
        return value


class SeededIdentifier(FoundationModel):
    identifier_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    value: str = Field(min_length=1)
    replacement_token: str = Field(pattern=r"^\[[A-Z0-9_]+\]$")


class PrivacyIntake(FoundationModel):
    contract: Literal["casepath.privacy-intake/1.0.0"] = "casepath.privacy-intake/1.0.0"
    case_id: str = Field(min_length=1)
    language: str = Field(min_length=1)
    claim_message: str
    attachments: tuple[IntakeAttachment, ...]
    source_locators: tuple[SourceLocator, ...]
    seeded_identifiers: tuple[SeededIdentifier, ...] = ()
    declared_synthetic_or_anonymized: bool = False


class ReplacementReceipt(FoundationModel):
    identifier_id: str
    kind: str
    value_sha256: str
    replacement_token: str
    replacement_count: int = Field(ge=0)

    @field_validator("value_sha256")
    @classmethod
    def validate_value_hash(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError("value_sha256 must be a lowercase SHA-256 digest")
        return value


class PrivacyReceipt(FoundationModel):
    contract: Literal["casepath.privacy-receipt/1.0.0"] = (
        "casepath.privacy-receipt/1.0.0"
    )
    case_id: str
    state: PrivacyState
    input_sha256: str
    sanitized_payload_sha256: str
    source_lineage_sha256: str
    replacements: tuple[ReplacementReceipt, ...]
    unresolved_identifier_classes: tuple[str, ...]
    unresolved_value_hashes: tuple[str, ...]
    fail_closed: bool
    fixture_scope_only: Literal[True] = True
    safety_nonclaim: Literal[
        "Passing seeded synthetic fixtures does not establish general anonymization safety."
    ] = "Passing seeded synthetic fixtures does not establish general anonymization safety."
    receipt_sha256: str

    @field_validator(
        "input_sha256",
        "sanitized_payload_sha256",
        "source_lineage_sha256",
        "receipt_sha256",
    )
    @classmethod
    def validate_receipt_hashes(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError("receipt hash must be a lowercase SHA-256 digest")
        return value


class PrivacyResult(FoundationModel):
    state: PrivacyState
    sanitized_message: str | None
    sanitized_attachments: tuple[IntakeAttachment, ...]
    source_locators: tuple[SourceLocator, ...]
    receipt: PrivacyReceipt


class CanonicalCaseInput(FoundationModel):
    contract: Literal["casepath.canonical-case-input/1.0.0"] = (
        "casepath.canonical-case-input/1.0.0"
    )
    case_id: str = Field(min_length=1)
    language: str = Field(min_length=1)
    claim_message: str
    attachments: tuple[IntakeAttachment, ...]
    source_locators: tuple[SourceLocator, ...]
    privacy_receipt_sha256: str

    @field_validator("privacy_receipt_sha256")
    @classmethod
    def validate_privacy_hash(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError(
                "privacy_receipt_sha256 must be a lowercase SHA-256 digest"
            )
        return value


class ModelArtifact(FoundationModel):
    contract: Literal["casepath.provider-neutral-model-artifact/1.0.0"] = (
        "casepath.provider-neutral-model-artifact/1.0.0"
    )
    case_id: str
    process_artifact: dict[str, Any]
    evidence_document_plan: tuple[dict[str, Any], ...]
    provenance: tuple[SourceLocator, ...]
    artifact_sha256: str

    @field_validator("artifact_sha256")
    @classmethod
    def validate_artifact_hash(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError("artifact_sha256 must be a lowercase SHA-256 digest")
        return value


class ModelBoundaryReceipt(FoundationModel):
    contract: Literal["casepath.model-boundary-receipt/1.0.0"] = (
        "casepath.model-boundary-receipt/1.0.0"
    )
    case_id: str
    adapter_id: str
    execution_kind: Literal["deterministic_reference", "offline_fake"]
    request_sha256: str
    output_sha256: str
    adapter_invocations: int = 1
    model_calls: Literal[0] = 0
    provider_calls: Literal[0] = 0
    provider_credentials_read: Literal[False] = False
    cost_usd: float = Field(default=0.0, ge=0.0, le=0.0)
    receipt_sha256: str


class ModelBoundaryResult(FoundationModel):
    artifact: ModelArtifact
    receipt: ModelBoundaryReceipt


class CanonicalCaseArtifact(FoundationModel):
    contract: Literal["casepath.canonical-case-artifact/1.0.0"] = (
        "casepath.canonical-case-artifact/1.0.0"
    )
    case_id: str
    language: str
    claim_message: str
    attachments: tuple[IntakeAttachment, ...]
    source_locators: tuple[SourceLocator, ...]
    process_artifact: dict[str, Any]
    evidence_document_plan: tuple[dict[str, Any], ...]
    provenance: tuple[SourceLocator, ...]
    review_state: str
    knowledge_version: str
    privacy_receipt_sha256: str
    model_boundary_receipt_sha256: str
    canonical_sha256: str

    @model_validator(mode="after")
    def validate_canonical_hash(self) -> CanonicalCaseArtifact:
        payload = self.model_dump(mode="json", exclude={"canonical_sha256"})
        if digest_value(payload) != self.canonical_sha256:
            raise ValueError("canonical_sha256 does not match canonical artifact")
        return self


class ReviewReceipt(FoundationModel):
    contract: Literal["casepath.review-receipt/1.0.0"] = "casepath.review-receipt/1.0.0"
    reviewer_authority_type: ReviewerAuthorityType
    reviewed_artifact_version: str
    accepted_corrections: tuple[dict[str, Any], ...]
    timestamp: str
    provenance: tuple[SourceLocator, ...]
    signature_or_integrity_sha256: str


class RegressionReceipt(FoundationModel):
    contract: Literal["casepath.regression-receipt/1.0.0"] = (
        "casepath.regression-receipt/1.0.0"
    )
    artifact_version: str
    test_manifest_sha256: str
    passed: bool
    timestamp: str
    provenance: tuple[SourceLocator, ...]
    integrity_sha256: str


class KnowledgeVersion(FoundationModel):
    version_id: str
    content_sha256: str
    content: dict[str, Any]
    state: KnowledgeState
    rollback_target: str | None
    provenance: tuple[SourceLocator, ...]
    review_receipt: ReviewReceipt | None = None
    regression_receipt: RegressionReceipt | None = None


class GovernanceReceipt(FoundationModel):
    contract: Literal["casepath.knowledge-governance-receipt/1.0.0"] = (
        "casepath.knowledge-governance-receipt/1.0.0"
    )
    action: str
    version_id: str
    state_before: KnowledgeState | None
    state_after: KnowledgeState
    active_before: str | None
    active_after: str | None
    rollback_target: str | None
    content_sha256: str
    provenance: tuple[SourceLocator, ...]
    exact_prior_version_restored: bool | None = None
    timestamp: str
    receipt_sha256: str


class RetrievalReceipt(FoundationModel):
    contract: Literal["casepath.knowledge-retrieval-receipt/1.0.0"] = (
        "casepath.knowledge-retrieval-receipt/1.0.0"
    )
    case_id: str
    active_version_id: str
    content_sha256: str
    provenance: tuple[SourceLocator, ...]
    timestamp: str
    receipt_sha256: str


class ValidationReceipt(FoundationModel):
    contract: Literal["casepath.foundation-validation-receipt/1.0.0"] = (
        "casepath.foundation-validation-receipt/1.0.0"
    )
    case_id: str
    passed: bool
    checks: tuple[dict[str, Any], ...]
    canonical_sha256: str
    receipt_sha256: str
