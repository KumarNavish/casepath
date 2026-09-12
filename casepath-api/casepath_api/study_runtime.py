from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from .foundation.common import digest_value, is_sha256
from .foundation.contracts import FoundationModel


STUDY_ROLE_IDS = (
    "canonical_facts",
    "orchestrator_plan",
    "document_source_integrity",
    "process_decision_mapping",
    "evidence_checklist",
    "final_claim_brief_audit",
)
STUDY_ARM_IDS = (
    "casepath_obligation_controller",
    "generic_belief_state_planner",
    "rule_first_reactive",
    "document_first_adaptive",
)
QUALIFICATION_ARM_ID = "__qualification__"
QUALIFICATION_CASES = (
    ("qualification_sentinel", "qualification.content-free"),
    ("qualification_generated", "qualification.generated"),
)
EXPECTED_HOLDOUT_CASE_COUNT = 61
EXPECTED_CALL_COUNT = 1_476


def study_call_key_v1(
    *,
    phase: str,
    case_id: str,
    arm_id: str,
    role_id: str,
    cycle_index: int,
) -> str:
    return digest_value(
        {
            "contract": "casepath.study-call-key/1.0.0",
            "phase": phase,
            "case_id": case_id,
            "arm_id": arm_id,
            "role_id": role_id,
            "cycle_index": cycle_index,
        }
    )


class StudyRuntimeProfileV1(FoundationModel):
    contract: Literal["casepath.study-runtime-profile/1.0.0"] = (
        "casepath.study-runtime-profile/1.0.0"
    )
    requested_model: Literal["nvidia/nemotron-3-ultra-550b-a55b"]
    required_response_model: Literal[
        "nvidia/nemotron-3-ultra-550b-a55b-20260604"
    ]
    required_upstream_provider: Literal["DeepInfra"]
    required_endpoint_tag: Literal["deepinfra/fp4"]
    provider_only: tuple[Literal["deepinfra/fp4"], ...]
    allow_fallbacks: Literal[False]
    require_parameters: Literal[True]
    data_collection: Literal["deny"]
    automatic_retry: Literal[False]
    max_in_flight: Literal[1]
    temperature_milli: Literal[0]
    reasoning_effort: Literal["medium"]
    seed: int | None
    seed_attestation_sha256: str | None
    cache_policy: Literal["disabled"]
    fresh_session_per_arm_case: Literal[True]
    max_input_tokens_per_call: int = Field(ge=1)
    max_completion_tokens_per_call: Literal[1024]
    input_nano_usd_per_token: Literal[500]
    output_nano_usd_per_token: Literal[2200]
    cumulative_cap_nano_usd: Literal[6_080_000_000]
    tokenizer_identity_sha256: str
    role_ids: tuple[str, ...]
    arm_ids: tuple[str, ...]
    profile_sha256: str

    @field_validator(
        "max_in_flight",
        "temperature_milli",
        "max_input_tokens_per_call",
        "max_completion_tokens_per_call",
        "input_nano_usd_per_token",
        "output_nano_usd_per_token",
        "cumulative_cap_nano_usd",
        "seed",
        mode="before",
    )
    @classmethod
    def reject_boolean_integers(cls, value: Any) -> Any:
        if value is not None and type(value) is not int:
            raise ValueError("study integer fields must be exact integers")
        return value

    @field_validator(
        "seed_attestation_sha256",
        "tokenizer_identity_sha256",
        "profile_sha256",
    )
    @classmethod
    def validate_hash(cls, value: str | None) -> str | None:
        if value is not None and not is_sha256(value):
            raise ValueError("study profile hashes must be SHA-256")
        return value

    @model_validator(mode="after")
    def validate_profile(self) -> StudyRuntimeProfileV1:
        if (
            self.provider_only != ("deepinfra/fp4",)
            or self.role_ids != STUDY_ROLE_IDS
            or self.arm_ids != STUDY_ARM_IDS
        ):
            raise ValueError("study runtime roster or route is invalid")
        if (self.seed is None) != (self.seed_attestation_sha256 is None):
            raise ValueError("study seed requires an exact attestation")
        if self.seed is not None and self.seed != 2701:
            raise ValueError("study seed is outside the frozen contract")
        payload = self.model_dump(mode="json", exclude={"profile_sha256"})
        if digest_value(payload) != self.profile_sha256:
            raise ValueError("study runtime profile self-hash mismatch")
        return self


class StudyScheduledCallV1(FoundationModel):
    contract: Literal["casepath.study-scheduled-call/1.0.0"] = (
        "casepath.study-scheduled-call/1.0.0"
    )
    phase: Literal[
        "qualification_sentinel",
        "qualification_generated",
        "scored_holdout",
    ]
    case_id: str = Field(min_length=1, max_length=200)
    arm_id: str = Field(min_length=1, max_length=100)
    role_id: str = Field(min_length=1, max_length=100)
    cycle_index: Literal[0]
    rendered_input_sha256: str
    tokenizer_identity_sha256: str
    prompt_token_count: int = Field(ge=1)
    max_input_tokens: int = Field(ge=1)
    max_completion_tokens: Literal[1024]
    reserved_nano_usd: int = Field(ge=1)
    profile_sha256: str
    call_sha256: str
    call_row_id: str

    @field_validator(
        "cycle_index",
        "prompt_token_count",
        "max_input_tokens",
        "max_completion_tokens",
        "reserved_nano_usd",
        mode="before",
    )
    @classmethod
    def reject_boolean_integers(cls, value: Any) -> Any:
        if type(value) is not int:
            raise ValueError("study call integer fields must be exact integers")
        return value

    @field_validator(
        "rendered_input_sha256",
        "tokenizer_identity_sha256",
        "profile_sha256",
        "call_sha256",
    )
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError("study call hashes must be SHA-256")
        return value

    @model_validator(mode="after")
    def validate_call(self) -> StudyScheduledCallV1:
        if (
            self.role_id not in STUDY_ROLE_IDS
            or self.prompt_token_count > self.max_input_tokens
            or self.call_row_id != f"study-call.{self.call_sha256}"
        ):
            raise ValueError("study call roster or bound is invalid")
        expected = self.max_input_tokens * 500 + self.max_completion_tokens * 2200
        if self.reserved_nano_usd != expected:
            raise ValueError("study call cost reservation is invalid")
        payload = self.model_dump(
            mode="json", exclude={"call_sha256", "call_row_id"}
        )
        if digest_value(payload) != self.call_sha256:
            raise ValueError("study call self-hash mismatch")
        return self


class StudyCallScheduleV1(FoundationModel):
    contract: Literal["casepath.study-call-schedule/1.0.0"] = (
        "casepath.study-call-schedule/1.0.0"
    )
    profile_sha256: str
    holdout_case_ids: tuple[str, ...]
    calls: tuple[StudyScheduledCallV1, ...]
    schedule_sha256: str

    @field_validator("profile_sha256", "schedule_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError("study schedule hashes must be SHA-256")
        return value

    @model_validator(mode="after")
    def validate_schedule(self) -> StudyCallScheduleV1:
        if (
            len(self.holdout_case_ids) != EXPECTED_HOLDOUT_CASE_COUNT
            or tuple(sorted(self.holdout_case_ids)) != self.holdout_case_ids
            or len(set(self.holdout_case_ids)) != len(self.holdout_case_ids)
            or len(self.calls) != EXPECTED_CALL_COUNT
            or len({value.call_row_id for value in self.calls}) != len(self.calls)
            or any(value.profile_sha256 != self.profile_sha256 for value in self.calls)
        ):
            raise ValueError("study schedule roster is invalid")
        expected_roster = [
            (phase, case_id, QUALIFICATION_ARM_ID, role_id, 0)
            for phase, case_id in QUALIFICATION_CASES
            for role_id in STUDY_ROLE_IDS
        ] + [
            ("scored_holdout", case_id, arm_id, role_id, 0)
            for case_id in self.holdout_case_ids
            for arm_id in STUDY_ARM_IDS
            for role_id in STUDY_ROLE_IDS
        ]
        actual_roster = [
            (
                value.phase,
                value.case_id,
                value.arm_id,
                value.role_id,
                value.cycle_index,
            )
            for value in self.calls
        ]
        if actual_roster != expected_roster:
            raise ValueError("study schedule differs from the exact Cartesian roster")
        payload = self.model_dump(mode="json", exclude={"schedule_sha256"})
        if digest_value(payload) != self.schedule_sha256:
            raise ValueError("study schedule self-hash mismatch")
        return self


class StudyCostProofV1(FoundationModel):
    contract: Literal["casepath.study-cost-proof/1.0.0"] = (
        "casepath.study-cost-proof/1.0.0"
    )
    profile_sha256: str
    schedule_sha256: str
    call_row_sha256s: tuple[str, ...]
    call_count: Literal[1476]
    total_reserved_nano_usd: int = Field(ge=1)
    cumulative_cap_nano_usd: Literal[6_080_000_000]
    remaining_margin_nano_usd: int = Field(ge=0)
    proof_sha256: str

    @field_validator(
        "call_count",
        "total_reserved_nano_usd",
        "cumulative_cap_nano_usd",
        "remaining_margin_nano_usd",
        mode="before",
    )
    @classmethod
    def reject_boolean_integers(cls, value: Any) -> Any:
        if type(value) is not int:
            raise ValueError("study cost fields must be exact integers")
        return value

    @field_validator(
        "profile_sha256",
        "schedule_sha256",
        "call_row_sha256s",
        "proof_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str | tuple[str, ...]) -> str | tuple[str, ...]:
        values = (value,) if isinstance(value, str) else value
        if any(not is_sha256(item) for item in values):
            raise ValueError("study cost proof hashes must be SHA-256")
        return value

    @model_validator(mode="after")
    def validate_proof(self) -> StudyCostProofV1:
        if (
            len(self.call_row_sha256s) != self.call_count
            or len(set(self.call_row_sha256s)) != self.call_count
            or self.total_reserved_nano_usd > self.cumulative_cap_nano_usd
            or self.remaining_margin_nano_usd
            != self.cumulative_cap_nano_usd - self.total_reserved_nano_usd
        ):
            raise ValueError("study cost proof total is invalid")
        payload = self.model_dump(mode="json", exclude={"proof_sha256"})
        if digest_value(payload) != self.proof_sha256:
            raise ValueError("study cost proof self-hash mismatch")
        return self


def validate_study_authority_bundle_v1(
    *,
    profile: StudyRuntimeProfileV1,
    schedule: StudyCallScheduleV1,
    proof: StudyCostProofV1,
) -> tuple[StudyRuntimeProfileV1, StudyCallScheduleV1, StudyCostProofV1]:
    """Revalidate and cross-bind every object that can authorize a study call."""

    checked_profile = StudyRuntimeProfileV1.model_validate(
        profile.model_dump(mode="json")
    )
    checked_schedule = StudyCallScheduleV1.model_validate(
        schedule.model_dump(mode="json")
    )
    checked_proof = StudyCostProofV1.model_validate(
        proof.model_dump(mode="json")
    )
    if checked_schedule.profile_sha256 != checked_profile.profile_sha256:
        raise ValueError("study authority profile/schedule binding mismatch")
    expected_reserved = (
        checked_profile.max_input_tokens_per_call
        * checked_profile.input_nano_usd_per_token
        + checked_profile.max_completion_tokens_per_call
        * checked_profile.output_nano_usd_per_token
    )
    for call in checked_schedule.calls:
        if (
            call.profile_sha256 != checked_profile.profile_sha256
            or call.tokenizer_identity_sha256
            != checked_profile.tokenizer_identity_sha256
            or call.max_input_tokens
            != checked_profile.max_input_tokens_per_call
            or call.max_completion_tokens
            != checked_profile.max_completion_tokens_per_call
            or call.reserved_nano_usd != expected_reserved
        ):
            raise ValueError(
                f"study call diverges from profile: {call.call_row_id}"
            )
    call_hashes = tuple(call.call_sha256 for call in checked_schedule.calls)
    total = sum(call.reserved_nano_usd for call in checked_schedule.calls)
    if (
        checked_proof.profile_sha256 != checked_profile.profile_sha256
        or checked_proof.schedule_sha256 != checked_schedule.schedule_sha256
        or checked_proof.call_row_sha256s != call_hashes
        or checked_proof.call_count != len(checked_schedule.calls)
        or checked_proof.total_reserved_nano_usd != total
        or checked_proof.cumulative_cap_nano_usd
        != checked_profile.cumulative_cap_nano_usd
        or checked_proof.remaining_margin_nano_usd
        != checked_profile.cumulative_cap_nano_usd - total
    ):
        raise ValueError("study cost proof is not bound to the exact schedule")
    return checked_profile, checked_schedule, checked_proof


def build_study_runtime_profile_v1(
    *,
    tokenizer_identity_sha256: str,
    max_input_tokens_per_call: int = 3_584,
    seed: int | None = None,
    seed_attestation_sha256: str | None = None,
) -> StudyRuntimeProfileV1:
    payload = {
        "contract": "casepath.study-runtime-profile/1.0.0",
        "requested_model": "nvidia/nemotron-3-ultra-550b-a55b",
        "required_response_model": (
            "nvidia/nemotron-3-ultra-550b-a55b-20260604"
        ),
        "required_upstream_provider": "DeepInfra",
        "required_endpoint_tag": "deepinfra/fp4",
        "provider_only": ["deepinfra/fp4"],
        "allow_fallbacks": False,
        "require_parameters": True,
        "data_collection": "deny",
        "automatic_retry": False,
        "max_in_flight": 1,
        "temperature_milli": 0,
        "reasoning_effort": "medium",
        "seed": seed,
        "seed_attestation_sha256": seed_attestation_sha256,
        "cache_policy": "disabled",
        "fresh_session_per_arm_case": True,
        "max_input_tokens_per_call": max_input_tokens_per_call,
        "max_completion_tokens_per_call": 1024,
        "input_nano_usd_per_token": 500,
        "output_nano_usd_per_token": 2200,
        "cumulative_cap_nano_usd": 6_080_000_000,
        "tokenizer_identity_sha256": tokenizer_identity_sha256,
        "role_ids": list(STUDY_ROLE_IDS),
        "arm_ids": list(STUDY_ARM_IDS),
    }
    return StudyRuntimeProfileV1.model_validate(
        {**payload, "profile_sha256": digest_value(payload)}
    )


def _build_call(
    *,
    profile: StudyRuntimeProfileV1,
    phase: str,
    case_id: str,
    arm_id: str,
    role_id: str,
    rendered_input_sha256: str,
    prompt_token_count: int,
) -> StudyScheduledCallV1:
    payload = {
        "contract": "casepath.study-scheduled-call/1.0.0",
        "phase": phase,
        "case_id": case_id,
        "arm_id": arm_id,
        "role_id": role_id,
        "cycle_index": 0,
        "rendered_input_sha256": rendered_input_sha256,
        "tokenizer_identity_sha256": profile.tokenizer_identity_sha256,
        "prompt_token_count": prompt_token_count,
        "max_input_tokens": profile.max_input_tokens_per_call,
        "max_completion_tokens": profile.max_completion_tokens_per_call,
        "reserved_nano_usd": (
            profile.max_input_tokens_per_call
            * profile.input_nano_usd_per_token
            + profile.max_completion_tokens_per_call
            * profile.output_nano_usd_per_token
        ),
        "profile_sha256": profile.profile_sha256,
    }
    call_sha256 = digest_value(payload)
    return StudyScheduledCallV1.model_validate(
        {
            **payload,
            "call_sha256": call_sha256,
            "call_row_id": f"study-call.{call_sha256}",
        }
    )


def build_study_call_schedule_v1(
    *,
    profile: StudyRuntimeProfileV1,
    holdout_case_ids: tuple[str, ...],
    rendered_inputs: Mapping[str, tuple[str, int]],
) -> StudyCallScheduleV1:
    roster = [
        (phase, case_id, QUALIFICATION_ARM_ID, role_id, 0)
        for phase, case_id in QUALIFICATION_CASES
        for role_id in STUDY_ROLE_IDS
    ] + [
        ("scored_holdout", case_id, arm_id, role_id, 0)
        for case_id in holdout_case_ids
        for arm_id in STUDY_ARM_IDS
        for role_id in STUDY_ROLE_IDS
    ]
    expected_keys = {
        study_call_key_v1(
            phase=phase,
            case_id=case_id,
            arm_id=arm_id,
            role_id=role_id,
            cycle_index=cycle_index,
        )
        for phase, case_id, arm_id, role_id, cycle_index in roster
    }
    if set(rendered_inputs) != expected_keys:
        raise ValueError("rendered input roster differs from the exact study schedule")
    calls = []
    for phase, case_id, arm_id, role_id, cycle_index in roster:
        key = study_call_key_v1(
            phase=phase,
            case_id=case_id,
            arm_id=arm_id,
            role_id=role_id,
            cycle_index=cycle_index,
        )
        rendered_sha256, token_count = rendered_inputs[key]
        calls.append(
            _build_call(
                profile=profile,
                phase=phase,
                case_id=case_id,
                arm_id=arm_id,
                role_id=role_id,
                rendered_input_sha256=rendered_sha256,
                prompt_token_count=token_count,
            )
        )
    payload = {
        "contract": "casepath.study-call-schedule/1.0.0",
        "profile_sha256": profile.profile_sha256,
        "holdout_case_ids": list(holdout_case_ids),
        "calls": [value.model_dump(mode="json") for value in calls],
    }
    return StudyCallScheduleV1.model_validate(
        {**payload, "schedule_sha256": digest_value(payload)}
    )


def build_study_cost_proof_v1(
    *, profile: StudyRuntimeProfileV1, schedule: StudyCallScheduleV1
) -> StudyCostProofV1:
    if schedule.profile_sha256 != profile.profile_sha256:
        raise ValueError("study schedule and profile identities differ")
    total = sum(value.reserved_nano_usd for value in schedule.calls)
    payload = {
        "contract": "casepath.study-cost-proof/1.0.0",
        "profile_sha256": profile.profile_sha256,
        "schedule_sha256": schedule.schedule_sha256,
        "call_row_sha256s": [value.call_sha256 for value in schedule.calls],
        "call_count": len(schedule.calls),
        "total_reserved_nano_usd": total,
        "cumulative_cap_nano_usd": profile.cumulative_cap_nano_usd,
        "remaining_margin_nano_usd": profile.cumulative_cap_nano_usd - total,
    }
    proof = StudyCostProofV1.model_validate(
        {**payload, "proof_sha256": digest_value(payload)}
    )
    return validate_study_authority_bundle_v1(
        profile=profile, schedule=schedule, proof=proof
    )[2]


__all__ = [
    "EXPECTED_CALL_COUNT",
    "EXPECTED_HOLDOUT_CASE_COUNT",
    "QUALIFICATION_ARM_ID",
    "STUDY_ARM_IDS",
    "STUDY_ROLE_IDS",
    "StudyCallScheduleV1",
    "StudyCostProofV1",
    "StudyRuntimeProfileV1",
    "StudyScheduledCallV1",
    "build_study_call_schedule_v1",
    "build_study_cost_proof_v1",
    "build_study_runtime_profile_v1",
    "study_call_key_v1",
    "validate_study_authority_bundle_v1",
]
