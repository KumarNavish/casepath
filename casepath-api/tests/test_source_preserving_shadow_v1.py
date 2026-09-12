from __future__ import annotations

import base64
import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from casepath_api.foundation.common import digest_text, digest_value
from casepath_api.source_preserving_shadow_v1 import (
    ProposedShadowCorrectionV1,
    ShadowActionV1,
    ShadowModelReceiptV1,
    ShadowPremiseSpecV1,
    ShadowPremiseV1,
    ShadowRequirementV1,
    ShadowScopeV1,
    ShadowSourceV1,
    SourcePreservingShadowRequestV1,
    apply_source_preserving_shadow,
    create_source_preserving_shadow_router,
    exact_span,
    premise_state_sha256,
)


CORPUS = (
    Path(__file__).parents[1]
    / "casepath_api"
    / "corpora"
    / "synthetic-dev-60"
    / "artifacts"
)
MODEL_PATH = "/capstor/scratch/cscs/kumar0002/casepath-ground-truth-free-assets/qwen3-14b"
CONFIG_SHA = "cec46d7194096df4073cd1fdb13f482bb2b63d16a75f6ca139251b9bf62d1f26"
WEIGHT_SHA = "62d7ad35757bae5e7baa452cb1483178b7daa50e869e923226b8da10871f7ebc"
RUNNER_SHA = "bec1187f548fd60d48cafef95551eb182146a6c0f59ff95518a5543f7b479285"

INDEX_ACCESS = (
    "SYNTHETIC ARRIVAL — Intake index issued by the CasePath test desk on 2025-10-10. "
    "Actor: intake clerk Elina Roth. Scope: access-log comparison for apartment A-17. "
    "The index identifies two scheduled visits: 25 September 2025 and 2 October 2025, "
    "both in Europe/Zurich time."
)
REPLY_ACCESS = (
    "SYNTHETIC REPLY — Joint records response issued on 2025-10-11. Actors: contractor "
    "dispatcher Paolo Kunz and door-system custodian Iris Vogel. Scope: apartment A-17, "
    "08:00–13:00 Europe/Zurich on 25 September and 2 October 2025. Contractor log CL-88 "
    "records arrivals at 09:14 and 09:07, respectively. Door export DS-19 covers both "
    "requested windows and states that its displayed clock was 4 minutes slow; it supplies "
    "both displayed and corrected timestamps."
)
INDEX_HEATING = (
    "SYNTHETIC ARRIVAL — Heating-service intake index issued by the CasePath test desk on "
    "2025-02-03. Actor: intake clerk David Wenger. Scope: replacement-part scheduling check. "
    "The index links service ticket H-314 to boiler B-09 in apartment C-04 and to the customer "
    "report received on 3 February 2025."
)
REPLY_HEATING = (
    "SYNTHETIC REPLY — Sara Meier, 2025-02-04; scope: replacement-part status for H-314. "
    "‘I am the service coordinator assigned to H-314. No fixed replacement-part availability "
    "date has been issued for this ticket; the current supplier status field says date unconfirmed.’"
)
CONTROL_SOURCES = {
    "e4s8": (
        "SYNTHETIC ARRIVAL — Intake index issued by the CasePath test desk on 2025-05-24. "
        "Actor: case clerk Aline Graf. Scope: document-linkage check for unit K-22. The index "
        "identifies exhibits PM-41 and TN-42 under that scope."
    ),
    "b7q3": (
        "SYNTHETIC ARRIVAL — Exhibit PM-41, issued on 2025-05-01. Actor: property-service "
        "coordinator Noemi Keller. Scope: administrative confirmation record for the leak entry "
        "associated with the kitchen sink in unit K-22."
    ),
    "s2m6": (
        "SYNTHETIC ARRIVAL — Exhibit TN-42, issued on 2025-05-24. Actor: customer-record "
        "custodian Reto Baumann. Scope: recurrence-timeline record for the kitchen sink in unit "
        "K-22. TN-42 explicitly cites PM-41 as the earlier administrative confirmation record."
    ),
}

RAW_INITIAL_ACCESS = """{
  "atoms": [
    {
      "id": "n6t4",
      "status": "T",
      "evidence": "The index identifies two scheduled visits: 25 September 2025 and 2 October 2025"
    },
    {
      "id": "c9p2",
      "status": "U",
      "evidence": ""
    },
    {
      "id": "w3h8",
      "status": "U",
      "evidence": ""
    }
  ],
  "ready": false,
  "action": "h9k2",
  "question": ""
}<|im_end|>"""
RAW_POST_ACCESS = """{
  "atoms": [
    {
      "id": "n6t4",
      "status": "T",
      "evidence": "The index identifies two scheduled visits: 25 September 2025 and 2 October 2025"
    },
    {
      "id": "c9p2",
      "status": "T",
      "evidence": "Contractor log CL-88 records arrivals at 09:14 and 09:07, respectively."
    },
    {
      "id": "w3h8",
      "status": "T",
      "evidence": "Door export DS-19 covers both requested windows and states that its displayed clock was 4 minutes slow; it supplies both displayed and corrected timestamps."
    }
  ],
  "ready": true,
  "action": "none",
  "question": ""
}<|im_end|>"""
RAW_INITIAL_HEATING = """{
  "atoms": [
    {
      "id": "f7s3",
      "status": "T",
      "evidence": "The index links service ticket H-314 to boiler B-09 in apartment C-04 and to the customer report received on 3 February 2025."
    },
    {
      "id": "m2x8",
      "status": "U",
      "evidence": ""
    },
    {
      "id": "r4c1",
      "status": "U",
      "evidence": ""
    }
  ],
  "ready": false,
  "action": "a3y7",
  "question": "Ask the service desk to have the coordinator assigned to H-314 state whether a fixed replacement-part availability date has been issued and, if so, give that date."
}<|im_end|>"""
RAW_POST_HEATING = """{
  "atoms": [
    {
      "id": "f7s3",
      "status": "T",
      "evidence": "The index links service ticket H-314 to boiler B-09 in apartment C-04 and to the customer report received on 3 February 2025."
    },
    {
      "id": "m2x8",
      "status": "F",
      "evidence": "No fixed replacement-part availability date has been issued for this ticket; the current supplier status field says date unconfirmed."
    },
    {
      "id": "r4c1",
      "status": "T",
      "evidence": "Sara Meier, the service coordinator assigned to H-314, provided the response."
    }
  ],
  "ready": false,
  "action": "none",
  "question": ""
}<|im_end|>"""
RAW_CONTROL = """{
  "atoms": [
    {
      "id": "j8d2",
      "status": "T",
      "evidence": "SYNTHETIC ARRIVAL — Intake index issued by the CasePath test desk on 2025-05-24. Actor: case clerk Aline Graf. Scope: document-linkage check for unit K-22. The index identifies exhibits PM-41 and TN-42 under that scope."
    },
    {
      "id": "p5u9",
      "status": "T",
      "evidence": "SYNTHETIC ARRIVAL — Exhibit PM-41, issued on 2025-05-01. Actor: property-service coordinator Noemi Keller. Scope: administrative confirmation record for the leak entry associated with the kitchen sink in unit K-22."
    },
    {
      "id": "g1k7",
      "status": "T",
      "evidence": "SYNTHETIC ARRIVAL — Exhibit TN-42, issued on 2025-05-24. Actor: customer-record custodian Reto Baumann. Scope: recurrence-timeline record for the kitchen sink in unit K-22. TN-42 explicitly cites PM-41 as the earlier administrative confirmation record."
    }
  ],
  "ready": true,
  "action": "none",
  "question": ""
}<|im_end|>"""
RAW_CONTROL_POST = (
    '{"atoms":[{"id":"j8d2","status":"T","evidence":"SYNTHETIC ARRIVAL — Intake index '
    "issued by the CasePath test desk on 2025-05-24. Actor: case clerk Aline Graf. Scope: "
    "document-linkage check for unit K-22. The index identifies exhibits PM-41 and TN-42 under "
    'that scope."},{"id":"p5u9","status":"T","evidence":"SYNTHETIC ARRIVAL — Exhibit PM-41, '
    "issued on 2025-05-01. Actor: property-service coordinator Noemi Keller. Scope: administrative "
    "confirmation record for the leak entry associated with the kitchen sink in unit K-22.\"},{\"id\":\"g1k7\","
    '\"status\":\"T\",\"evidence\":\"SYNTHETIC ARRIVAL — Exhibit TN-42, issued on 2025-05-24. Actor: '
    "customer-record custodian Reto Baumann. Scope: recurrence-timeline record for the kitchen sink "
    "in unit K-22. TN-42 explicitly cites PM-41 as the earlier administrative confirmation record.\"}],"
    '\"ready\":true,\"action\":\"none\",\"question\":\"\"}<|im_end|>'
)


def _corpus_text(claim_id: str, sha_prefix: str) -> str:
    matches = list((CORPUS / claim_id).glob(f"00-{sha_prefix}-*"))
    assert len(matches) == 1
    return matches[0].read_text(encoding="utf-8")


def _source(
    source_id: str,
    text: str,
    allowed: tuple[str, ...],
    *,
    version: str = "v1",
    action_id: str | None = None,
    acquired_at: str = "2025-01-01T00:00:00Z",
) -> ShadowSourceV1:
    raw = text.encode("utf-8")
    return ShadowSourceV1(
        source_id=source_id,
        source_version=version,
        content_sha256=sha256(raw).hexdigest(),
        content_b64=base64.b64encode(raw).decode("ascii"),
        decoded_text=text,
        acquired_at=acquired_at,
        acquisition_action_id=action_id,
        allowed_premise_ids=allowed,
    )


def _receipt(
    raw: str,
    record_id: str,
    input_sha: str,
    rendered_sha: str,
    tokens: tuple[int, int],
    *,
    actual: bool = True,
) -> ShadowModelReceiptV1:
    material: dict[str, Any] = {
        "contract": "casepath.shadow-model-receipt/1.0.0",
        "record_id": record_id,
        "model_id": "Qwen/Qwen3-14B" if actual else "focused-test-fixture/not-a-model-run",
        "model_resolved_path": MODEL_PATH if actual else "fixture://deterministic-envelope",
        "resolved_config_sha256": CONFIG_SHA if actual else "1" * 64,
        "weight_index_sha256": WEIGHT_SHA if actual else "2" * 64,
        "runner_sha256": RUNNER_SHA if actual else "3" * 64,
        "runtime": (
            {
                "python": "3.12.12",
                "torch": "2.9.1",
                "transformers": "4.57.1",
                "model_device": "cuda:0",
                "model_dtype": "torch.bfloat16",
                "gpu": {"name": "NVIDIA GH200 120GB", "compute_capability": [9, 0]},
            }
            if actual
            else {"kind": "focused_test_fixture"}
        ),
        "settings": (
            {
                "strategy": "greedy",
                "seed": 0,
                "thinking_mode": "disabled",
                "max_new_tokens": 512,
                "max_input_tokens": 8192,
                "torch_dtype": "bfloat16",
            }
            if actual
            else {"kind": "focused_test_fixture"}
        ),
        "input_sha256": input_sha,
        "rendered_chat_sha256": rendered_sha,
        "output_sha256": digest_text(raw),
        "input_tokens": tokens[0],
        "output_tokens": tokens[1],
        "finish_reason": "eos",
        "failure": None,
        "cost_usd": 0.0,
    }
    return ShadowModelReceiptV1(
        **material,
        receipt_sha256=digest_value(material),
    )


def _scope(premise_id: str) -> ShadowScopeV1:
    return ShadowScopeV1(
        actor="synthetic record issuer",
        object=premise_id,
        time="frozen episode time",
        obligation=f"support premise {premise_id}",
    )


def _requirement(ids: tuple[str, ...], name: str) -> ShadowRequirementV1:
    return ShadowRequirementV1(
        requirement_id=name,
        statement=name,
        premises=tuple(
            ShadowPremiseSpecV1(
                premise_id=premise_id,
                statement=f"Frozen public premise {premise_id}",
                scope=_scope(premise_id),
            )
            for premise_id in ids
        ),
    )


def _premises(result: dict[str, Any]) -> tuple[ShadowPremiseV1, ...]:
    return tuple(ShadowPremiseV1.model_validate(value) for value in result["premises"])


def _states(result: dict[str, Any]) -> dict[str, str]:
    return {value["premise_id"]: value["state"] for value in result["premises"]}


def _access_initial() -> tuple[SourcePreservingShadowRequestV1, dict[str, Any]]:
    sources = (
        _source(
            "source_002",
            _corpus_text("clm_5156de89a4189cd1", "8a2a4f3a5ca1"),
            (),
            version="sha256:8a2a4f3a5ca1",
            acquired_at="2025-10-10T10:00:00+02:00",
        ),
        _source("v2k7", INDEX_ACCESS, ("n6t4",), acquired_at="2025-10-10T10:00:00+02:00"),
    )
    request = SourcePreservingShadowRequestV1(
        operation_id="replay.r8m2-v4q7.initial",
        phase="initial",
        sources=sources,
        requirement=_requirement(("n6t4", "c9p2", "w3h8"), "access-log comparison"),
        actions=(
            ShadowActionV1(
                action_id="h9k2",
                request="Request exact contractor and door-system records.",
                cost=2,
                may_update=("c9p2", "w3h8"),
            ),
        ),
        raw_model_output=RAW_INITIAL_ACCESS,
        model_receipt=_receipt(
            RAW_INITIAL_ACCESS,
            "direct.r8m2-v4q7",
            "a1cd5f4ae0634dd9867f996555cbd77a80edba483ebe1166c26b6aed5a870eac",
            "951d5f211c632013bd25c5373b12ca9d2ea618408c32a3e7b568624212e7446c",
            (1422, 138),
        ),
    )
    return request, apply_source_preserving_shadow(request)


def _heating_initial() -> tuple[SourcePreservingShadowRequestV1, dict[str, Any]]:
    sources = (
        _source(
            "source_003",
            _corpus_text("clm_c50db5a1837bf4e3", "e76a370187b5"),
            (),
            version="sha256:e76a370187b5",
            acquired_at="2025-02-03T12:00:00+01:00",
        ),
        _source("u6p4", INDEX_HEATING, ("f7s3",), acquired_at="2025-02-03T12:00:00+01:00"),
    )
    request = SourcePreservingShadowRequestV1(
        operation_id="replay.k5v9-b2d6.initial",
        phase="initial",
        sources=sources,
        requirement=_requirement(("f7s3", "m2x8", "r4c1"), "replacement-part scheduling"),
        actions=(
            ShadowActionV1(
                action_id="a3y7",
                request="Ask the assigned coordinator for exact part availability status.",
                cost=2,
                may_update=("m2x8", "r4c1"),
            ),
        ),
        raw_model_output=RAW_INITIAL_HEATING,
        model_receipt=_receipt(
            RAW_INITIAL_HEATING,
            "direct.k5v9-b2d6",
            "01d68fa7ebea132af843e6ffb366b1860b0fecd4409f33205969214118ec3719",
            "056c0ad33d5e7e25e840cf847d991c5ff4e27397041e282439f826f121a4244b",
            (1467, 185),
        ),
    )
    return request, apply_source_preserving_shadow(request)


def test_actual_access_log_replay_retains_acquisition_and_becomes_ready() -> None:
    initial_request, initial = _access_initial()
    assert initial["model_receipt"]["output_sha256"] == (
        "309670db6f74c0f4d5cbe57d30dc9bf2d26481bdfa1ea30df6d5267440149dad"
    )
    assert _states(initial) == {"c9p2": "U", "n6t4": "T", "w3h8": "U"}
    assert initial["next_action"]["action_id"] == "h9k2"
    assert {value["source_id"] for value in initial["available_sources"]} == {
        "source_002",
        "v2k7",
    }

    reply = _source(
        "reply.fb340455",
        REPLY_ACCESS,
        ("c9p2", "w3h8"),
        version="sha256:fb3404551abc",
        action_id="h9k2",
        acquired_at="2025-10-11T00:00:00Z",
    )
    post_request = SourcePreservingShadowRequestV1(
        operation_id="replay.r8m2-v4q7.post",
        phase="post_action",
        sources=(*initial_request.sources, reply),
        requirement=initial_request.requirement,
        previous_premises=_premises(initial),
        actions=initial_request.actions,
        applied_action_id="h9k2",
        raw_model_output=RAW_POST_ACCESS,
        model_receipt=_receipt(
            RAW_POST_ACCESS,
            "post.direct.r8m2-v4q7",
            "46a3c981896e104bc5300ee16415429dc9c488e2b8c8d4d7881e73970369dab6",
            "095eb2d3b78d6349d813aeaaabd3859c5f4a3bd1781226c8a10ad5d5a74609af",
            (1802, 191),
        ),
    )
    post = apply_source_preserving_shadow(post_request)

    assert _states(post) == {"c9p2": "T", "n6t4": "T", "w3h8": "T"}
    assert post["shadow_ready"] is True
    assert post["next_action"] is None
    assert post["quarantines"] == []
    assert len(post["available_sources"]) == 3
    assert post["model_receipt"]["output_sha256"] == (
        "9abf067da399cb3d179b5ee7ab5091d80e65a70916162c52f07b6d5c23549388"
    )
    assert sha256(REPLY_ACCESS.encode("utf-8")).hexdigest() == (
        "fb3404551abcf33c98eb3657410dade9e8cb16e605b79f1e62e95e51d41bc20d"
    )
    assert post["premises"][1]["support_bundles"] == initial["premises"][1]["support_bundles"]


def test_bad_coordinator_paraphrase_quarantines_only_role_premise() -> None:
    initial_request, initial = _heating_initial()
    assert initial["model_receipt"]["output_sha256"] == (
        "d8af56c25e503f813b19bb8e548f6cf79ff3817fc1acc509477db3ca2eb7938a"
    )
    ticket_support = initial["premises"][0]["support_bundles"][0]["support_id"]
    reply = _source(
        "reply.ca1e3e3f",
        REPLY_HEATING,
        ("m2x8", "r4c1"),
        version="sha256:ca1e3e3fe0eb",
        action_id="a3y7",
        acquired_at="2025-02-04T00:00:00Z",
    )
    post = apply_source_preserving_shadow(
        SourcePreservingShadowRequestV1(
            operation_id="replay.k5v9-b2d6.post",
            phase="post_action",
            sources=(*initial_request.sources, reply),
            requirement=initial_request.requirement,
            previous_premises=_premises(initial),
            actions=initial_request.actions,
            applied_action_id="a3y7",
            raw_model_output=RAW_POST_HEATING,
            model_receipt=_receipt(
                RAW_POST_HEATING,
                "post.direct.k5v9-b2d6",
                "8ddce3cf09bcf94c3ba63f75697abdfde06496329920c6406a60ad14b4d0838b",
                "3fc63743339eca09956fdfa891dc7c03701f3e42ba2318c40f43a31757e56212",
                (1834, 190),
            ),
        )
    )

    assert _states(post) == {"f7s3": "T", "m2x8": "F", "r4c1": "U"}
    assert post["premises"][0]["support_bundles"][0]["support_id"] == ticket_support
    assert post["premises"][1]["support_bundles"][0]["polarity"] == "negative"
    assert post["premises"][2]["support_bundles"] == []
    assert [(value["premise_id"], value["reason"]) for value in post["quarantines"]] == [
        ("r4c1", "non_exact_or_ambiguous_span")
    ]
    assert len(post["available_sources"]) == 3
    assert post["model_receipt"]["output_sha256"] == (
        "b77cf10e6a2e2aaf78c5ed3f9bcbb413793a071f2e0af5ce3cdfa5a9616aeb4c"
    )
    assert sha256(REPLY_HEATING.encode("utf-8")).hexdigest() == (
        "ca1e3e3fe0ebc186768579d0862508e3967eae4af327dcfd509e85f39439400f"
    )


def test_fully_supplied_actual_control_requests_nothing() -> None:
    ids = ("j8d2", "p5u9", "g1k7")
    original = _source(
        "source_001",
        _corpus_text("clm_e262801f9368bc12", "f877fc5bd65e"),
        (),
        version="sha256:f877fc5bd65e",
        acquired_at="2025-05-24T13:00:00+02:00",
    )
    sources = (original,) + tuple(
        _source(source_id, text, (premise_id,), acquired_at="2025-05-24T13:00:00+02:00")
        for source_id, text, premise_id in (
            ("e4s8", CONTROL_SOURCES["e4s8"], "j8d2"),
            ("b7q3", CONTROL_SOURCES["b7q3"], "p5u9"),
            ("s2m6", CONTROL_SOURCES["s2m6"], "g1k7"),
        )
    )
    result = apply_source_preserving_shadow(
        SourcePreservingShadowRequestV1(
            operation_id="replay.t3c8-y6n1.initial",
            phase="initial",
            sources=sources,
            requirement=_requirement(ids, "document-linkage control"),
            raw_model_output=RAW_CONTROL,
            model_receipt=_receipt(
                RAW_CONTROL,
                "direct.t3c8-y6n1",
                "17ec05148a1f92eb77d7566bb4b33b4eb9d9be6812d7d59f2ff3e659e086b483",
                "32103504046cb0d1bcaf470080bf19fe33e8df52b7068168b7ee08da22c86354",
                (1602, 309),
            ),
        )
    )
    assert set(_states(result).values()) == {"T"}
    assert result["shadow_ready"] is True
    assert result["next_action"] is None
    assert len(result["available_sources"]) == 4
    assert result["model_receipt"]["output_sha256"] == (
        "d11bc40d2617f5355cde82cfa715aa9c4fb0ec6f145cbedf85377ed789db89a5"
    )

    post = apply_source_preserving_shadow(
        SourcePreservingShadowRequestV1(
            operation_id="replay.t3c8-y6n1.post",
            phase="post_action",
            sources=sources,
            requirement=_requirement(ids, "document-linkage control"),
            previous_premises=_premises(result),
            applied_action_id="none",
            raw_model_output=RAW_CONTROL_POST,
            model_receipt=_receipt(
                RAW_CONTROL_POST,
                "post.direct.t3c8-y6n1",
                "39675053f968953f54d57127a818db1b8371bb752768c75ff432c20fd5fb993c",
                "bd4c30f2f85bd24db7432634ca530f73b4fbdaa358330c3897064b7c6010dc3e",
                (2016, 261),
            ),
        )
    )
    assert _states(post) == _states(result)
    assert post["shadow_ready"] is True
    assert post["next_action"] is None
    assert post["quarantines"] == []
    assert post["model_receipt"]["output_sha256"] == (
        "7eaf3eb35c73dd4b7c5cdb41235cf31d23705d106928a0672b60220cd3cf9561"
    )


def test_multiple_exact_spans_are_a_bundle_and_rationale_is_not_a_span() -> None:
    source = _source("multi", "Header: H-314\nBody: date unconfirmed\n", ("p1",))
    raw = json.dumps(
        {
            "atoms": [
                {
                    "id": "p1",
                    "status": "F",
                    "evidence_spans": ["Header: H-314", "Body: date unconfirmed"],
                    "rationale": "The two source fields jointly negate fixed-date availability.",
                }
            ],
            "ready": False,
            "action": "none",
            "question": "",
        }
    )
    result = apply_source_preserving_shadow(
        SourcePreservingShadowRequestV1(
            operation_id="fixture.multi-span",
            phase="initial",
            sources=(source,),
            requirement=_requirement(("p1",), "multi-span fixture"),
            raw_model_output=raw,
            model_receipt=_receipt(raw, "fixture.multi-span", "4" * 64, "5" * 64, (0, 0), actual=False),
        )
    )
    premise = result["premises"][0]
    assert premise["state"] == "F"
    assert [span["exact_text"] for span in premise["support_bundles"][0]["spans"]] == [
        "Header: H-314",
        "Body: date unconfirmed",
    ]
    assert premise["rationale"] == "The two source fields jointly negate fixed-date availability."
    assert premise["rationale_kind"] == "model_rationale_not_source_quote"


@pytest.mark.parametrize(
    ("case", "scope_value", "parent_sha", "versions", "expected_reason"),
    [
        ("wrong-version", "valid", "valid", ("v999",), "target_source_version_mismatch"),
        ("stale", "valid", "stale", ("v1",), "stale_parent_state"),
        ("unknown-scope", None, "valid", ("v1",), "unknown_correction_scope"),
    ],
)
def test_invalid_corrections_do_not_corrupt_support(
    case: str,
    scope_value: str | None,
    parent_sha: str,
    versions: tuple[str, ...],
    expected_reason: str,
) -> None:
    request, initial = _access_initial()
    previous = _premises(initial)
    target = next(value for value in previous if value.premise_id == "n6t4").support_bundles[0]
    correction_source = _source("correction", "Correction: index entry withdrawn.", ("n6t4",))
    correction = ProposedShadowCorrectionV1(
        correction_id=f"correction.{case}",
        premise_id="n6t4",
        target_support_ids=(target.support_id,),
        target_source_versions={target.support_id: versions},
        evidence_spans=(exact_span(correction_source, "Correction: index entry withdrawn."),),
        scope=_scope("n6t4") if scope_value == "valid" else None,
        expected_parent_state_sha256=(
            premise_state_sha256(previous) if parent_sha == "valid" else "f" * 64
        ),
    )
    result = apply_source_preserving_shadow(
        SourcePreservingShadowRequestV1(
            operation_id=f"correction.{case}",
            phase="correction_only",
            sources=(*request.sources, correction_source),
            requirement=request.requirement,
            previous_premises=previous,
            corrections=(correction,),
        )
    )
    assert _states(result)["n6t4"] == "T"
    assert result["premises"][1]["support_bundles"][0]["support_id"] == target.support_id
    assert result["quarantines"][0]["reason"] == expected_reason
    assert result["premises"][1]["correction_relations"][-1]["status"] == "quarantined"


def test_valid_correction_is_local_and_superseded_support_cannot_revive() -> None:
    request, initial = _access_initial()
    previous = _premises(initial)
    target = next(value for value in previous if value.premise_id == "n6t4").support_bundles[0]
    correction_source = _source("correction", "Correction: index entry withdrawn.", ("n6t4",))
    correction = ProposedShadowCorrectionV1(
        correction_id="correction.valid",
        premise_id="n6t4",
        target_support_ids=(target.support_id,),
        target_source_versions={
            target.support_id: tuple(sorted({span.source_version for span in target.spans}))
        },
        evidence_spans=(exact_span(correction_source, "Correction: index entry withdrawn."),),
        scope=_scope("n6t4"),
        expected_parent_state_sha256=premise_state_sha256(previous),
    )
    corrected = apply_source_preserving_shadow(
        SourcePreservingShadowRequestV1(
            operation_id="correction.valid",
            phase="correction_only",
            sources=(*request.sources, correction_source),
            requirement=request.requirement,
            previous_premises=previous,
            corrections=(correction,),
        )
    )
    assert _states(corrected) == {"c9p2": "U", "n6t4": "U", "w3h8": "U"}
    assert corrected["premises"][1]["correction_relations"][-1]["status"] == "applied"

    replay = apply_source_preserving_shadow(
        SourcePreservingShadowRequestV1(
            operation_id="correction.replay",
            phase="initial",
            sources=(*request.sources, correction_source),
            requirement=request.requirement,
            previous_premises=_premises(corrected),
            actions=request.actions,
            raw_model_output=RAW_INITIAL_ACCESS,
            model_receipt=request.model_receipt,
        )
    )
    assert _states(replay)["n6t4"] == "U"
    assert any(value["reason"] == "support_was_explicitly_superseded" for value in replay["quarantines"])


def test_negative_premise_does_not_prune_a_realizable_action() -> None:
    source = _source("status", "No fixed date has been issued.", ("m2x8",))
    raw = json.dumps(
        {
            "atoms": [{"id": "m2x8", "status": "F", "evidence": "No fixed date has been issued."}],
            "ready": False,
            "action": "a3y7",
            "question": "",
        }
    )
    result = apply_source_preserving_shadow(
        SourcePreservingShadowRequestV1(
            operation_id="fixture.action-on-negative",
            phase="initial",
            sources=(source,),
            requirement=_requirement(("m2x8",), "action-on-negative fixture"),
            actions=(ShadowActionV1(action_id="a3y7", request="Request a dated update.", cost=2, may_update=("m2x8",)),),
            raw_model_output=raw,
            model_receipt=_receipt(raw, "fixture.action-on-negative", "6" * 64, "7" * 64, (0, 0), actual=False),
        )
    )
    assert _states(result)["m2x8"] == "F"
    assert result["next_action"]["action_id"] == "a3y7"


def test_explicit_shadow_http_route_is_non_authoritative() -> None:
    request, _ = _access_initial()
    app = FastAPI()
    app.include_router(create_source_preserving_shadow_router())
    response = TestClient(app).post(
        "/api/shadow/source-preserving/v1/admit",
        json=request.model_dump(mode="json"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "shadow_non_authoritative"
    assert body["canonical_state_mutated"] is False
    assert body["canonical_authority"] == "existing_intake_grammar_and_claim_loop_reducer"
