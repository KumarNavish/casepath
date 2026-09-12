from __future__ import annotations

from copy import deepcopy

from pydantic import ValidationError
import pytest

from casepath_api import langchain_runtime
from casepath_api.foundation.common import digest_value
from casepath_api.study_runtime import (
    EXPECTED_CALL_COUNT,
    QUALIFICATION_ARM_ID,
    STUDY_ARM_IDS,
    STUDY_ROLE_IDS,
    StudyCallScheduleV1,
    StudyCostProofV1,
    StudyRuntimeProfileV1,
    StudyScheduledCallV1,
    build_study_call_schedule_v1,
    build_study_cost_proof_v1,
    build_study_runtime_profile_v1,
    study_call_key_v1,
    validate_study_authority_bundle_v1,
)


TOKENIZER_SHA256 = "a" * 64
HOLDOUT_CASE_IDS = tuple(f"ecab-may-2026-{index:03d}" for index in range(1, 62))


def _rendered_inputs(token_count: int) -> dict[str, tuple[str, int]]:
    rows = [
        (phase, case_id, QUALIFICATION_ARM_ID, role_id, 0)
        for phase, case_id in (
            ("qualification_sentinel", "qualification.content-free"),
            ("qualification_generated", "qualification.generated"),
        )
        for role_id in STUDY_ROLE_IDS
    ] + [
        ("scored_holdout", case_id, arm_id, role_id, 0)
        for case_id in HOLDOUT_CASE_IDS
        for arm_id in STUDY_ARM_IDS
        for role_id in STUDY_ROLE_IDS
    ]
    return {
        study_call_key_v1(
            phase=phase,
            case_id=case_id,
            arm_id=arm_id,
            role_id=role_id,
            cycle_index=cycle_index,
        ): (
            digest_value(
                {
                    "phase": phase,
                    "case_id": case_id,
                    "arm_id": arm_id,
                    "role_id": role_id,
                    "cycle_index": cycle_index,
                }
            ),
            token_count,
        )
        for phase, case_id, arm_id, role_id, cycle_index in rows
    }


def _profile(max_input_tokens: int = 3_584) -> StudyRuntimeProfileV1:
    return build_study_runtime_profile_v1(
        tokenizer_identity_sha256=TOKENIZER_SHA256,
        max_input_tokens_per_call=max_input_tokens,
    )


def _rehash_profile(value: StudyRuntimeProfileV1, **updates: object) -> dict[str, object]:
    payload = value.model_dump(mode="json", exclude={"profile_sha256"})
    payload.update(updates)
    return {**payload, "profile_sha256": digest_value(payload)}


def _rehash_call(
    value: StudyScheduledCallV1, **updates: object
) -> StudyScheduledCallV1:
    payload = value.model_dump(
        mode="json", exclude={"call_sha256", "call_row_id"}
    )
    payload.update(updates)
    call_sha256 = digest_value(payload)
    return StudyScheduledCallV1.model_validate(
        {
            **payload,
            "call_sha256": call_sha256,
            "call_row_id": f"study-call.{call_sha256}",
        }
    )


def _rehash_schedule(
    value: StudyCallScheduleV1,
    *,
    calls: tuple[StudyScheduledCallV1, ...],
) -> StudyCallScheduleV1:
    payload = value.model_dump(mode="json", exclude={"schedule_sha256"})
    payload["calls"] = [call.model_dump(mode="json") for call in calls]
    return StudyCallScheduleV1.model_validate(
        {**payload, "schedule_sha256": digest_value(payload)}
    )


def _proof_for(
    profile: StudyRuntimeProfileV1,
    schedule: StudyCallScheduleV1,
    *,
    call_hashes: tuple[str, ...] | None = None,
    total: int | None = None,
) -> StudyCostProofV1:
    resolved_total = (
        sum(call.reserved_nano_usd for call in schedule.calls)
        if total is None
        else total
    )
    payload = {
        "contract": "casepath.study-cost-proof/1.0.0",
        "profile_sha256": profile.profile_sha256,
        "schedule_sha256": schedule.schedule_sha256,
        "call_row_sha256s": list(
            call_hashes
            if call_hashes is not None
            else tuple(call.call_sha256 for call in schedule.calls)
        ),
        "call_count": len(schedule.calls),
        "total_reserved_nano_usd": resolved_total,
        "cumulative_cap_nano_usd": profile.cumulative_cap_nano_usd,
        "remaining_margin_nano_usd": (
            profile.cumulative_cap_nano_usd - resolved_total
        ),
    }
    return StudyCostProofV1.model_validate(
        {**payload, "proof_sha256": digest_value(payload)}
    )


def test_exact_study_profile_does_not_change_product_defaults() -> None:
    default_endpoint = langchain_runtime.OPENROUTER_ENDPOINT_TAG
    default_provider = langchain_runtime.OPENROUTER_EXPECTED_UPSTREAM_PROVIDER
    default_policy = deepcopy(langchain_runtime.OPENROUTER_PROVIDER_POLICY)

    profile = _profile()

    assert profile.profile_sha256 == digest_value(
        profile.model_dump(mode="json", exclude={"profile_sha256"})
    )
    assert profile.role_ids == STUDY_ROLE_IDS
    assert profile.arm_ids == STUDY_ARM_IDS
    assert profile.required_endpoint_tag == "deepinfra/fp4"
    assert profile.required_response_model.endswith("-20260604")
    assert profile.cache_policy == "disabled"
    assert langchain_runtime.OPENROUTER_ENDPOINT_TAG == default_endpoint == "together"
    assert (
        langchain_runtime.OPENROUTER_EXPECTED_UPSTREAM_PROVIDER
        == default_provider
        == "Together"
    )
    assert langchain_runtime.OPENROUTER_PROVIDER_POLICY == default_policy


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("requested_model", "another-model"),
        ("required_response_model", "nvidia/nemotron-3-ultra-550b-a55b"),
        ("required_upstream_provider", "Together"),
        ("required_endpoint_tag", "deepinfra"),
        ("provider_only", ["deepinfra"]),
        ("allow_fallbacks", True),
        ("require_parameters", False),
        ("data_collection", "allow"),
        ("automatic_retry", True),
        ("max_in_flight", 2),
        ("reasoning_effort", "low"),
        ("cache_policy", "enabled"),
        ("max_completion_tokens_per_call", 1025),
        ("role_ids", list(STUDY_ROLE_IDS[:-1])),
        ("arm_ids", list(STUDY_ARM_IDS[:-1])),
    ],
)
def test_study_profile_rejects_any_route_or_roster_drift(
    field: str, value: object
) -> None:
    with pytest.raises(ValidationError):
        StudyRuntimeProfileV1.model_validate(_rehash_profile(_profile(), **{field: value}))


def test_study_profile_seed_and_integer_contracts_are_fail_closed() -> None:
    with pytest.raises(ValidationError, match="attestation"):
        build_study_runtime_profile_v1(
            tokenizer_identity_sha256=TOKENIZER_SHA256,
            seed=2701,
        )
    with pytest.raises(ValidationError):
        build_study_runtime_profile_v1(
            tokenizer_identity_sha256=TOKENIZER_SHA256,
            max_input_tokens_per_call=3_584.0,  # type: ignore[arg-type]
        )


def test_exact_1476_call_schedule_and_integer_cost_proof() -> None:
    profile = _profile()
    schedule = build_study_call_schedule_v1(
        profile=profile,
        holdout_case_ids=HOLDOUT_CASE_IDS,
        rendered_inputs=_rendered_inputs(3_584),
    )
    proof = build_study_cost_proof_v1(profile=profile, schedule=schedule)

    assert len(schedule.calls) == proof.call_count == EXPECTED_CALL_COUNT
    assert proof.total_reserved_nano_usd == 5_970_124_800
    assert proof.remaining_margin_nano_usd == 109_875_200
    assert proof.proof_sha256 == digest_value(
        proof.model_dump(mode="json", exclude={"proof_sha256"})
    )
    assert all(value.max_completion_tokens == 1024 for value in schedule.calls)
    assert len(
        {
            (value.case_id, value.arm_id, value.role_id)
            for value in schedule.calls
            if value.phase == "scored_holdout"
        }
    ) == 61 * 4 * 6


def test_3732_token_boundary_passes_and_3733_fails_hard_cap() -> None:
    passing = _profile(3_732)
    schedule = build_study_call_schedule_v1(
        profile=passing,
        holdout_case_ids=HOLDOUT_CASE_IDS,
        rendered_inputs=_rendered_inputs(3_732),
    )
    proof = build_study_cost_proof_v1(profile=passing, schedule=schedule)
    assert proof.total_reserved_nano_usd == 6_079_348_800
    assert proof.remaining_margin_nano_usd == 651_200

    failing = _profile(3_733)
    failing_schedule = build_study_call_schedule_v1(
        profile=failing,
        holdout_case_ids=HOLDOUT_CASE_IDS,
        rendered_inputs=_rendered_inputs(3_733),
    )
    with pytest.raises(ValidationError):
        build_study_cost_proof_v1(profile=failing, schedule=failing_schedule)


def test_missing_extra_retry_or_second_cycle_cannot_enter_schedule() -> None:
    profile = _profile()
    rendered = _rendered_inputs(10)
    missing = dict(rendered)
    missing.pop(next(iter(missing)))
    with pytest.raises(ValueError, match="roster"):
        build_study_call_schedule_v1(
            profile=profile,
            holdout_case_ids=HOLDOUT_CASE_IDS,
            rendered_inputs=missing,
        )

    extra = dict(rendered)
    extra[
        study_call_key_v1(
            phase="scored_holdout",
            case_id=HOLDOUT_CASE_IDS[0],
            arm_id=STUDY_ARM_IDS[0],
            role_id=STUDY_ROLE_IDS[0],
            cycle_index=1,
        )
    ] = ("b" * 64, 10)
    with pytest.raises(ValueError, match="roster"):
        build_study_call_schedule_v1(
            profile=profile,
            holdout_case_ids=HOLDOUT_CASE_IDS,
            rendered_inputs=extra,
        )

    schedule = build_study_call_schedule_v1(
        profile=profile,
        holdout_case_ids=HOLDOUT_CASE_IDS,
        rendered_inputs=rendered,
    )
    payload = schedule.model_dump(mode="json", exclude={"schedule_sha256"})
    payload["calls"].append(deepcopy(payload["calls"][-1]))
    with pytest.raises(ValidationError, match="roster"):
        StudyCallScheduleV1.model_validate(
            {**payload, "schedule_sha256": digest_value(payload)}
        )


def test_prompt_token_overflow_fails_before_any_runtime_path() -> None:
    with pytest.raises(ValidationError, match="bound"):
        build_study_call_schedule_v1(
            profile=_profile(),
            holdout_case_ids=HOLDOUT_CASE_IDS,
            rendered_inputs=_rendered_inputs(3_585),
        )


def test_authority_bundle_accepts_exact_builder_outputs() -> None:
    profile = _profile()
    schedule = build_study_call_schedule_v1(
        profile=profile,
        holdout_case_ids=HOLDOUT_CASE_IDS,
        rendered_inputs=_rendered_inputs(1),
    )
    proof = build_study_cost_proof_v1(profile=profile, schedule=schedule)

    checked = validate_study_authority_bundle_v1(
        profile=profile, schedule=schedule, proof=proof
    )
    assert tuple(value.profile_sha256 for value in checked[:1]) == (
        profile.profile_sha256,
    )
    assert checked[1].schedule_sha256 == schedule.schedule_sha256
    assert checked[2].proof_sha256 == proof.proof_sha256
    assert checked[2].total_reserved_nano_usd == 5_970_124_800


def test_authority_bundle_revalidates_model_copy_instances() -> None:
    profile = _profile()
    schedule = build_study_call_schedule_v1(
        profile=profile,
        holdout_case_ids=HOLDOUT_CASE_IDS,
        rendered_inputs=_rendered_inputs(1),
    )
    proof = build_study_cost_proof_v1(profile=profile, schedule=schedule)
    forged = profile.model_copy(update={"profile_sha256": "b" * 64})

    with pytest.raises(ValidationError, match="self-hash"):
        validate_study_authority_bundle_v1(
            profile=forged, schedule=schedule, proof=proof
        )


@pytest.mark.parametrize("damage", ["tokenizer", "cap", "proof_row", "total"])
def test_authority_bundle_rejects_self_consistent_cross_object_forgery(
    damage: str,
) -> None:
    profile = _profile()
    schedule = build_study_call_schedule_v1(
        profile=profile,
        holdout_case_ids=HOLDOUT_CASE_IDS,
        rendered_inputs=_rendered_inputs(1),
    )
    calls = list(schedule.calls)
    if damage == "tokenizer":
        calls[0] = _rehash_call(
            calls[0], tokenizer_identity_sha256="b" * 64
        )
    elif damage == "cap":
        calls[0] = _rehash_call(
            calls[0],
            max_input_tokens=3_000,
            reserved_nano_usd=3_000 * 500 + 1_024 * 2_200,
        )
    forged_schedule = _rehash_schedule(schedule, calls=tuple(calls))
    if damage == "proof_row":
        hashes = tuple(call.call_sha256 for call in forged_schedule.calls)
        substitute = "f" * 64
        assert substitute not in hashes
        proof = _proof_for(
            profile, forged_schedule, call_hashes=(substitute, *hashes[1:])
        )
    elif damage == "total":
        expected = sum(
            call.reserved_nano_usd for call in forged_schedule.calls
        )
        proof = _proof_for(profile, forged_schedule, total=expected - 1)
    else:
        proof = _proof_for(profile, forged_schedule)

    with pytest.raises(ValueError, match="diverges|not bound"):
        validate_study_authority_bundle_v1(
            profile=profile, schedule=forged_schedule, proof=proof
        )


def test_prompt_token_count_must_be_positive() -> None:
    profile = _profile()
    with pytest.raises(ValidationError):
        build_study_call_schedule_v1(
            profile=profile,
            holdout_case_ids=HOLDOUT_CASE_IDS,
            rendered_inputs=_rendered_inputs(0),
        )
