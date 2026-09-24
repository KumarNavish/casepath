"""Fail-closed receipts for the sealed autonomous production run."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from manifests.digests import digest_json

from .execution_budget import GlobalBudgetReceipt, nemotron_cost_microusd
from .schema import CandidateArtifact, ProviderCallReceipt, StrictModel, UsageReceipt

Sha256 = str
GenerationCondition = Literal["B3", "B6", "B7", "B9"]
Condition = Literal["B3", "B6", "B7", "B8", "B9"]
JournalState = Literal["prepared", "unknown", "succeeded", "failed"]


class MatchedCustomRunBudget(StrictModel):
    """One frozen, source-independent budget shared by every generative arm."""

    contract: Literal["casepath.autonomous-run-budget/1.1.0"]
    model: str = Field(min_length=1)
    model_revision: str = Field(min_length=1)
    upstream_provider: str = Field(min_length=1)
    max_model_calls_per_condition: Literal[2]
    max_tool_calls_per_condition: Literal[0]
    max_input_tokens_per_condition: int = Field(gt=0)
    max_output_tokens_per_condition: int = Field(gt=1)
    max_model_calls_global: Literal[1200]
    max_input_tokens_per_call: int = Field(gt=0)
    max_output_tokens_per_call: int = Field(gt=0)
    max_input_tokens_global: int = Field(gt=0)
    max_output_tokens_global: int = Field(gt=0)
    max_cost_microusd_global: int = Field(gt=0)
    input_price_microusd_per_million: Literal[600_000]
    output_price_microusd_per_million: Literal[3_600_000]
    max_retrieved_bytes_per_condition: Literal[0]
    temperature: float = Field(ge=0.0, le=0.0)
    samples: Literal[1]
    timeout_seconds: float = Field(gt=0.0)
    max_retries: Literal[0]
    request_id_semantics: Literal["deterministic_correlation_only_not_provider_idempotency"]
    budget_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")

    @property
    def model_revision_sha256(self) -> str:
        return digest_json({"model": self.model, "model_revision": self.model_revision})

    @model_validator(mode="after")
    def validate_hash(self) -> MatchedCustomRunBudget:
        if self.max_input_tokens_per_condition > 2 * self.max_input_tokens_per_call:
            raise ValueError("condition input cap exceeds its two-call envelope")
        if self.max_output_tokens_per_condition > 2 * self.max_output_tokens_per_call:
            raise ValueError("condition output cap exceeds its two-call envelope")
        if self.max_input_tokens_global > 600 * self.max_input_tokens_per_condition:
            raise ValueError("global input cap exceeds all 600 condition caps")
        if self.max_output_tokens_global > 600 * self.max_output_tokens_per_condition:
            raise ValueError("global output cap exceeds all 600 condition caps")
        if self.max_cost_microusd_global > nemotron_cost_microusd(
            self.max_input_tokens_global, self.max_output_tokens_global
        ):
            raise ValueError("global USD cap exceeds the frozen token-price envelope")
        if self.budget_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"budget_sha256"})
        ):
            raise ValueError("autonomous run budget has a stale hash")
        return self


class StageJournalRecord(StrictModel):
    """The atomic source of truth for one provider dispatch."""

    journal_version: Literal["casepath.stage-journal/1.0.0"]
    study_lock_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    compilation_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    schedule_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    budget_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    packet_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    case_id: str = Field(min_length=1)
    condition: GenerationCondition
    stage: str = Field(min_length=1)
    stage_index: int = Field(ge=0, le=1)
    request_id: str = Field(min_length=1)
    request_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    state: JournalState
    updated_at: str = Field(min_length=1)
    raw_response_sha256: Sha256 | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    output_payload: dict[str, Any] | None = None
    output_sha256: Sha256 | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    provider_call: ProviderCallReceipt | None = None
    stage_usage: UsageReceipt | None = None
    failure_code: str | None = None
    record_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_state_and_hash(self) -> StageJournalRecord:
        try:
            timestamp = datetime.fromisoformat(self.updated_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("journal timestamp is not ISO-8601") from exc
        if timestamp.tzinfo is None:
            raise ValueError("journal timestamp must include a timezone")
        terminal_fields = (
            self.raw_response_sha256,
            self.output_payload,
            self.output_sha256,
            self.provider_call,
            self.stage_usage,
            self.failure_code,
        )
        if self.state in {"prepared", "unknown"} and any(
            item is not None for item in terminal_fields
        ):
            raise ValueError("nonterminal journal states cannot contain a result")
        if self.state == "succeeded":
            required = (
                self.raw_response_sha256,
                self.output_payload,
                self.output_sha256,
                self.provider_call,
                self.stage_usage,
            )
            if any(item is None for item in required) or self.failure_code is not None:
                raise ValueError("successful journal entry lacks a complete provider result")
            assert self.output_payload is not None
            if self.output_sha256 != digest_json(self.output_payload):
                raise ValueError("successful journal output hash is stale")
        if self.state == "failed":
            if self.raw_response_sha256 is None or not self.failure_code:
                raise ValueError("terminal failure requires a response hash and failure code")
            if self.output_payload is not None or self.output_sha256 is not None:
                raise ValueError("failed journal entries cannot admit model output")
        if self.provider_call is not None and (
            self.provider_call.request_id != self.request_id
            or self.provider_call.request_sha256 != self.request_sha256
            or self.provider_call.stage != self.stage
        ):
            raise ValueError("provider receipt differs from the prepared dispatch")
        if self.record_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"record_sha256"})
        ):
            raise ValueError("stage journal record hash is stale")
        return self


class ConditionRunRecord(StrictModel):
    record_version: Literal["casepath.autonomous-condition-run/1.0.0"]
    study_lock_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    compilation_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    schedule_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    case_id: str = Field(min_length=1)
    condition: GenerationCondition
    status: Literal["succeeded", "failed"]
    stage_journal_sha256s: tuple[Sha256, ...] = Field(min_length=1, max_length=2)
    candidate: CandidateArtifact | None = None
    candidate_sha256: Sha256 | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    usage: UsageReceipt
    failure_stage: str | None = None
    failure_code: str | None = None
    record_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_result(self) -> ConditionRunRecord:
        if self.status == "succeeded":
            if (
                self.candidate is None
                or self.candidate_sha256 is None
                or len(self.stage_journal_sha256s) != 2
                or self.failure_stage is not None
                or self.failure_code is not None
            ):
                raise ValueError("successful condition record is incomplete")
            if self.candidate.case_id != self.case_id:
                raise ValueError("condition candidate belongs to another case")
            if self.candidate_sha256 != digest_json(self.candidate.model_dump(mode="json")):
                raise ValueError("condition candidate hash is stale")
        elif (
            self.candidate is not None
            or self.candidate_sha256 is not None
            or not self.failure_stage
            or not self.failure_code
        ):
            raise ValueError("failed condition record has inconsistent terminal fields")
        if self.record_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"record_sha256"})
        ):
            raise ValueError("condition record hash is stale")
        return self


class DerivedB8Record(StrictModel):
    record_version: Literal["casepath.autonomous-b8-derivation/1.0.0"]
    study_lock_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    compilation_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    schedule_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    case_id: str = Field(min_length=1)
    condition: Literal["B8"]
    source_condition: Literal["B7"]
    status: Literal["succeeded", "blocked_by_b7"]
    source_candidate_sha256: Sha256 | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    candidate: CandidateArtifact | None = None
    candidate_sha256: Sha256 | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    verification: dict[str, Any] | None = None
    additional_model_calls: Literal[0]
    record_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_derivation(self) -> DerivedB8Record:
        if self.status == "succeeded":
            if any(
                item is None
                for item in (
                    self.source_candidate_sha256,
                    self.candidate,
                    self.candidate_sha256,
                    self.verification,
                )
            ):
                raise ValueError("successful B8 derivation is incomplete")
            assert self.candidate is not None
            if self.candidate.case_id != self.case_id:
                raise ValueError("B8 candidate belongs to another case")
            if self.candidate_sha256 != digest_json(self.candidate.model_dump(mode="json")):
                raise ValueError("B8 candidate hash is stale")
            if self.verification is not None and (
                self.verification.get("input_candidate_sha256") != self.source_candidate_sha256
                or self.verification.get("output_candidate_sha256") != self.candidate_sha256
                or self.verification.get("additional_model_calls") != 0
            ):
                raise ValueError("B8 verification does not bind the exact B7 candidate")
        elif any(
            item is not None
            for item in (
                self.source_candidate_sha256,
                self.candidate,
                self.candidate_sha256,
                self.verification,
            )
        ):
            raise ValueError("blocked B8 cannot contain a derived result")
        if self.record_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"record_sha256"})
        ):
            raise ValueError("B8 derivation record hash is stale")
        return self


class CustomRunCompletenessReceipt(StrictModel):
    receipt_version: Literal["casepath.autonomous-run-completeness/1.0.0"]
    study_lock_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    compilation_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    schedule_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    budget_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    prompt_template_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    model_input_bundle_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    global_budget: GlobalBudgetReceipt
    evaluation_case_count: Literal[150]
    compiler_preflight_flag_count: Literal[6]
    compiler_flagged_outcome_count: int = Field(ge=0, le=6)
    terminal_generative_condition_count: int = Field(ge=0, le=600)
    terminal_b8_count: int = Field(ge=0, le=150)
    successful_provider_call_count: int = Field(ge=0, le=1200)
    terminal_provider_failure_count: int = Field(ge=0, le=600)
    prepared_dispatch_count: int = Field(ge=0)
    unknown_dispatch_count: int = Field(ge=0)
    total_input_tokens: int = Field(ge=0)
    total_output_tokens: int = Field(ge=0)
    total_cost_usd: float | None = Field(default=None, ge=0.0)
    complete: bool
    outcome_estimates_ready: bool
    blockers: tuple[str, ...]
    receipt_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_completeness(self) -> CustomRunCompletenessReceipt:
        expected = (
            self.terminal_generative_condition_count == 600
            and self.terminal_b8_count == 150
            and self.compiler_flagged_outcome_count == 6
            and self.prepared_dispatch_count == 0
            and self.unknown_dispatch_count == 0
            and self.global_budget.caps_respected
        )
        if self.complete != expected or self.outcome_estimates_ready != expected:
            raise ValueError("run completeness does not match terminal artifacts")
        if self.complete == bool(self.blockers):
            raise ValueError("complete runs have no blockers; incomplete runs require blockers")
        if self.receipt_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"receipt_sha256"})
        ):
            raise ValueError("completeness receipt hash is stale")
        return self


class CustomRunReadiness(StrictModel):
    readiness_version: Literal["casepath.autonomous-run-readiness/1.0.0"]
    eligible: bool
    missing_artifacts: tuple[str, ...]
    violations: tuple[str, ...]

    @model_validator(mode="after")
    def validate_eligibility(self) -> CustomRunReadiness:
        if self.eligible != (not self.missing_artifacts and not self.violations):
            raise ValueError("readiness eligibility does not match reported blockers")
        return self


# Publication-v3 uses new types rather than widening the old Literals.  This is
# intentional: a B-arm lock must fail to parse instead of silently authorizing
# a materially different factorial experiment.
GenerationConditionV3 = Literal[
    "PF_TYPED_V3",
    "PF_PLAIN_V3",
    "DIRECT_TYPED_V3",
    "DIRECT_PLAIN_V3",
    "EXIDE_V3",
    "DOCUMENT_FIRST_V3",
]


class MatchedCustomRunBudgetV3(StrictModel):
    contract: Literal["casepath.autonomous-run-budget/3.0.0"]
    custom_protocol_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    model: str = Field(min_length=1)
    model_revision: str = Field(min_length=1)
    upstream_provider: str = Field(min_length=1)
    max_model_calls_per_condition: Literal[2]
    max_tool_calls_per_condition: Literal[0]
    max_input_tokens_per_condition: int = Field(gt=0)
    max_output_tokens_per_condition: int = Field(gt=1)
    max_model_calls_global: Literal[1800]
    max_input_tokens_per_call: int = Field(gt=0)
    max_output_tokens_per_call: int = Field(gt=0)
    max_input_tokens_global: int = Field(gt=0)
    max_output_tokens_global: int = Field(gt=0)
    max_cost_microusd_global: int = Field(gt=0)
    input_price_microusd_per_million: Literal[600_000]
    output_price_microusd_per_million: Literal[3_600_000]
    max_retrieved_bytes_per_condition: Literal[0]
    temperature: float
    samples: Literal[1]
    timeout_seconds: float = Field(gt=0.0)
    max_retries: Literal[0]
    request_id_semantics: Literal["deterministic_correlation_only_not_provider_idempotency"]
    budget_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")

    @property
    def primary_model_identity_sha256(self) -> str:
        return digest_json(
            {
                "model": self.model,
                "model_revision": self.model_revision,
                "upstream_provider": self.upstream_provider,
            }
        )

    @model_validator(mode="after")
    def validate_budget(self) -> MatchedCustomRunBudgetV3:
        if self.temperature != 0.0:
            raise ValueError("publication-v3 temperature must be exactly zero")
        if self.max_input_tokens_per_condition > 2 * self.max_input_tokens_per_call:
            raise ValueError("condition input cap exceeds its two-call envelope")
        if self.max_output_tokens_per_condition > 2 * self.max_output_tokens_per_call:
            raise ValueError("condition output cap exceeds its two-call envelope")
        if self.max_input_tokens_global > 900 * self.max_input_tokens_per_condition:
            raise ValueError("global input cap exceeds all 900 condition caps")
        if self.max_output_tokens_global > 900 * self.max_output_tokens_per_condition:
            raise ValueError("global output cap exceeds all 900 condition caps")
        if self.max_cost_microusd_global > nemotron_cost_microusd(
            self.max_input_tokens_global, self.max_output_tokens_global
        ):
            raise ValueError("global USD cap exceeds the frozen token-price envelope")
        if self.budget_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"budget_sha256"})
        ):
            raise ValueError("publication-v3 custom budget has a stale hash")
        return self


class StageJournalRecordV3(StrictModel):
    journal_version: Literal["casepath.stage-journal/3.0.0"]
    publication_lock_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    custom_protocol_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    compilation_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    schedule_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    budget_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    packet_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    case_id: str = Field(min_length=1)
    condition: GenerationConditionV3
    stage: str = Field(min_length=1)
    stage_index: int = Field(ge=0, le=1)
    request_id: str = Field(min_length=1)
    request_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    state: JournalState
    updated_at: str = Field(min_length=1)
    raw_response_sha256: Sha256 | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    output_payload: dict[str, Any] | None = None
    output_sha256: Sha256 | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    provider_call: ProviderCallReceipt | None = None
    stage_usage: UsageReceipt | None = None
    failure_code: str | None = None
    record_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_state_and_hash(self) -> StageJournalRecordV3:
        try:
            timestamp = datetime.fromisoformat(self.updated_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("journal timestamp is not ISO-8601") from exc
        if timestamp.tzinfo is None:
            raise ValueError("journal timestamp must include a timezone")
        terminal_fields = (
            self.raw_response_sha256,
            self.output_payload,
            self.output_sha256,
            self.provider_call,
            self.stage_usage,
            self.failure_code,
        )
        if self.state in {"prepared", "unknown"} and any(
            item is not None for item in terminal_fields
        ):
            raise ValueError("nonterminal journal states cannot contain a result")
        if self.state == "succeeded":
            if (
                any(
                    item is None
                    for item in (
                        self.raw_response_sha256,
                        self.output_payload,
                        self.output_sha256,
                        self.provider_call,
                        self.stage_usage,
                    )
                )
                or self.failure_code is not None
            ):
                raise ValueError("successful journal entry lacks a complete provider result")
            assert self.output_payload is not None
            if self.output_sha256 != digest_json(self.output_payload):
                raise ValueError("successful journal output hash is stale")
        if self.state == "failed":
            if self.raw_response_sha256 is None or not self.failure_code:
                raise ValueError("terminal failure requires a response hash and failure code")
            if self.output_payload is not None or self.output_sha256 is not None:
                raise ValueError("failed journal entries cannot admit model output")
        if self.provider_call is not None and (
            self.provider_call.request_id != self.request_id
            or self.provider_call.request_sha256 != self.request_sha256
            or self.provider_call.stage != self.stage
        ):
            raise ValueError("provider receipt differs from the prepared dispatch")
        if self.record_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"record_sha256"})
        ):
            raise ValueError("stage journal record hash is stale")
        return self


class ConditionRunRecordV3(StrictModel):
    record_version: Literal["casepath.autonomous-condition-run/3.0.0"]
    publication_lock_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    custom_protocol_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    compilation_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    schedule_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    case_id: str = Field(min_length=1)
    condition: GenerationConditionV3
    status: Literal["succeeded", "failed"]
    stage_journal_sha256s: tuple[Sha256, ...] = Field(min_length=1, max_length=2)
    candidate: CandidateArtifact | None = None
    candidate_sha256: Sha256 | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    stage_one_output_sha256: Sha256 | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    usage: UsageReceipt
    failure_stage: str | None = None
    failure_code: str | None = None
    record_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_result(self) -> ConditionRunRecordV3:
        if self.status == "succeeded":
            if (
                self.candidate is None
                or self.candidate_sha256 is None
                or self.stage_one_output_sha256 is None
                or len(self.stage_journal_sha256s) != 2
                or self.failure_stage is not None
                or self.failure_code is not None
            ):
                raise ValueError("successful v3 condition record is incomplete")
            if self.candidate.case_id != self.case_id:
                raise ValueError("condition candidate belongs to another case")
            if self.candidate_sha256 != digest_json(self.candidate.model_dump(mode="json")):
                raise ValueError("condition candidate hash is stale")
        elif (
            self.candidate is not None
            or self.candidate_sha256 is not None
            or not self.failure_stage
            or not self.failure_code
        ):
            raise ValueError("failed condition record has inconsistent terminal fields")
        if self.record_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"record_sha256"})
        ):
            raise ValueError("condition record hash is stale")
        return self


class DerivedVerifierRecordV3(StrictModel):
    record_version: Literal["casepath.autonomous-verifier-derivation/3.0.0"]
    publication_lock_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    custom_protocol_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    compilation_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    schedule_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    case_id: str = Field(min_length=1)
    condition: Literal["VERIFY_PF_TYPED_V3"]
    source_condition: Literal["PF_TYPED_V3"]
    status: Literal["succeeded", "blocked_by_source"]
    source_candidate_sha256: Sha256 | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    candidate: CandidateArtifact | None = None
    candidate_sha256: Sha256 | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    verification: dict[str, Any] | None = None
    additional_model_calls: Literal[0]
    record_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_derivation(self) -> DerivedVerifierRecordV3:
        if self.status == "succeeded":
            if any(
                item is None
                for item in (
                    self.source_candidate_sha256,
                    self.candidate,
                    self.candidate_sha256,
                    self.verification,
                )
            ):
                raise ValueError("successful verifier derivation is incomplete")
            assert self.candidate is not None
            if self.candidate.case_id != self.case_id:
                raise ValueError("verified candidate belongs to another case")
            if self.candidate_sha256 != digest_json(self.candidate.model_dump(mode="json")):
                raise ValueError("verified candidate hash is stale")
            if self.verification is not None and (
                self.verification.get("input_candidate_sha256") != self.source_candidate_sha256
                or self.verification.get("output_candidate_sha256") != self.candidate_sha256
                or self.verification.get("additional_model_calls") != 0
            ):
                raise ValueError("verification does not bind the exact primary candidate")
        elif any(
            item is not None
            for item in (
                self.source_candidate_sha256,
                self.candidate,
                self.candidate_sha256,
                self.verification,
            )
        ):
            raise ValueError("blocked verification cannot contain a result")
        if self.record_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"record_sha256"})
        ):
            raise ValueError("verifier derivation record hash is stale")
        return self


class HeuristicRunRecordV3(StrictModel):
    record_version: Literal["casepath.ontology-rule-heuristic-run/3.0.0"]
    publication_lock_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    custom_protocol_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    case_id: str = Field(min_length=1)
    condition: Literal["ONTOLOGY_RULE_HEURISTIC_V3"]
    input_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    candidate: CandidateArtifact
    candidate_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    model_calls: Literal[0]
    tool_calls: Literal[0]
    record_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_record(self) -> HeuristicRunRecordV3:
        if self.candidate.case_id != self.case_id:
            raise ValueError("heuristic candidate belongs to another case")
        if self.candidate_sha256 != digest_json(self.candidate.model_dump(mode="json")):
            raise ValueError("heuristic candidate hash is stale")
        if self.record_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"record_sha256"})
        ):
            raise ValueError("heuristic run record hash is stale")
        return self


class CustomRunCompletenessReceiptV3(StrictModel):
    receipt_version: Literal["casepath.autonomous-run-completeness/3.0.0"]
    publication_lock_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    custom_protocol_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    compilation_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    schedule_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    budget_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    prompt_template_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    model_input_bundle_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    run_artifact_set_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    global_budget: GlobalBudgetReceipt
    evaluation_case_count: Literal[150]
    terminal_generative_condition_count: int = Field(ge=0, le=900)
    terminal_verifier_count: int = Field(ge=0, le=150)
    terminal_heuristic_count: int = Field(ge=0, le=150)
    successful_provider_call_count: int = Field(ge=0, le=1800)
    terminal_provider_failure_count: int = Field(ge=0, le=900)
    prepared_dispatch_count: int = Field(ge=0)
    unknown_dispatch_count: int = Field(ge=0)
    total_input_tokens: int = Field(ge=0)
    total_output_tokens: int = Field(ge=0)
    total_cost_usd: float | None = Field(default=None, ge=0.0)
    complete: bool
    outcome_scoring_ready: bool
    blockers: tuple[str, ...]
    receipt_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_completeness(self) -> CustomRunCompletenessReceiptV3:
        expected = (
            self.terminal_generative_condition_count == 900
            and self.terminal_verifier_count == 150
            and self.terminal_heuristic_count == 150
            and self.prepared_dispatch_count == 0
            and self.unknown_dispatch_count == 0
            and self.global_budget.caps_respected
        )
        if self.complete != expected or self.outcome_scoring_ready != expected:
            raise ValueError("v3 run completeness does not match terminal artifacts")
        if self.complete == bool(self.blockers):
            raise ValueError("complete runs have no blockers; incomplete runs require blockers")
        if self.receipt_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"receipt_sha256"})
        ):
            raise ValueError("v3 completeness receipt hash is stale")
        return self


class CustomRunReadinessV3(StrictModel):
    readiness_version: Literal["casepath.autonomous-run-readiness/3.0.0"]
    eligible: bool
    missing_artifacts: tuple[str, ...]
    violations: tuple[str, ...]

    @model_validator(mode="after")
    def validate_eligibility(self) -> CustomRunReadinessV3:
        if self.eligible != (not self.missing_artifacts and not self.violations):
            raise ValueError("readiness eligibility does not match reported blockers")
        return self
