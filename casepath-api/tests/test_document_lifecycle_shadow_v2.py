"""Native lifecycle interface tests; these do not score actor semantic accuracy."""

from __future__ import annotations

import base64
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from casepath_api.document_lifecycle_shadow_v2 import (
    DOCUMENT_LIFECYCLE_V2_ROUTE,
    LifecycleDerivedViewV2,
    LifecycleEventV2,
    LifecycleObligationV2,
    LifecyclePhysicalArtifactV2,
    LifecycleProposalBindingV2,
    LifecycleProposalReceiptV2,
    LifecycleSourceReferenceV2,
    LifecycleStateV2,
    derivation_sha256_v2,
    lifecycle_state_sha256_v2,
    new_lifecycle_state_v2,
    proposal_projection_sha256_v2,
)
from casepath_api.foundation.common import digest_text, digest_value


EPISODE_ID = "nsb_ep_a0facdfb944f0b0d"
SOURCE_RUN = (
    Path(__file__).resolve().parents[3]
    / ".discovery-loop/coordinator-work/pro-investigator-r1"
    / "native-source-binding-r1/terminal"
)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _content(path: Path) -> tuple[bytes, str, int]:
    raw = path.read_bytes()
    return raw, __import__("hashlib").sha256(raw).hexdigest(), len(raw)


def _artifact(
    artifact_id: str,
    path: Path,
    media_type: str,
    observed_at: str,
) -> LifecyclePhysicalArtifactV2:
    raw, content_sha256, size_bytes = _content(path)
    return LifecyclePhysicalArtifactV2(
        artifact_id=artifact_id,
        source_version=content_sha256,
        media_type=media_type,
        content_b64=base64.b64encode(raw).decode("ascii"),
        content_sha256=content_sha256,
        size_bytes=size_bytes,
        decoded_text=(
            raw.decode("utf-8")
            if media_type in {"text/plain", "text/plain; charset=utf-8", "message/rfc822"}
            else None
        ),
        observed_at=observed_at,
    )


def _view(
    *,
    parent: LifecyclePhysicalArtifactV2,
    local_view_id: str,
    raw: bytes,
    media_type: str,
    observed_at: str,
    page_index: int | None,
    method: str,
) -> LifecycleDerivedViewV2:
    content_sha256 = __import__("hashlib").sha256(raw).hexdigest()
    view_id = f"{parent.artifact_id}:{local_view_id}"
    fields = {
        "parent_artifact_id": parent.artifact_id,
        "parent_artifact_sha256": parent.content_sha256,
        "media_type": media_type,
        "content_sha256": content_sha256,
        "size_bytes": len(raw),
        "page_index": page_index,
        "derivation_method": method,
        "observed_at": observed_at,
    }
    return LifecycleDerivedViewV2(
        view_id=view_id,
        content_b64=base64.b64encode(raw).decode("ascii"),
        decoded_text=raw.decode("utf-8") if media_type == "text/plain" else None,
        derivation_sha256=derivation_sha256_v2(**fields),
        **fields,
    )


def _research_sources(
    artifact: dict[str, Any], observed_at: str
) -> tuple[LifecyclePhysicalArtifactV2, list[LifecycleDerivedViewV2]]:
    physical = _artifact(
        artifact["source_id"],
        SOURCE_RUN / "prepared" / artifact["path"],
        artifact["media_type"],
        observed_at,
    )
    assert physical.content_sha256 == artifact["sha256"]
    assert physical.size_bytes == artifact["size_bytes"]
    views = []
    for page in artifact["text_pages"]:
        raw = page["text"].encode("utf-8")
        assert __import__("hashlib").sha256(raw).hexdigest() == page["text_sha256"]
        views.append(_view(
            parent=physical,
            local_view_id=page["view_id"],
            raw=raw,
            media_type="text/plain",
            observed_at=observed_at,
            page_index=page["page_number"] - 1,
            method=page["origin"]["method"],
        ))
    for page in artifact["rendered_page_images"]:
        raw, content_sha256, _ = _content(SOURCE_RUN / "prepared" / page["path"])
        assert content_sha256 == page["sha256"]
        views.append(_view(
            parent=physical,
            local_view_id="pdf.page.%04d.image" % page["page_number"],
            raw=raw,
            media_type="image/png",
            observed_at=observed_at,
            page_index=page["page_number"] - 1,
            method="rendered page pixels from exact parent PDF",
        ))
    return physical, views


def _initial_event(episode: dict[str, Any]) -> LifecycleEventV2:
    observed_at = episode["initial_observed_at"]
    bundle = episode["initial_dossier"]["complete_original_bundle"]
    physical: list[LifecyclePhysicalArtifactV2] = []
    views: list[LifecycleDerivedViewV2] = []
    by_id: dict[str, LifecyclePhysicalArtifactV2] = {}
    for item in bundle["physical_artifacts"]:
        ref = item["raw_reference"]
        value = _artifact(
            item["source_id"],
            SOURCE_RUN / "prepared" / ref["absolute_path"],
            ref["media_type"],
            observed_at,
        )
        assert value.content_sha256 == ref["sha256"]
        assert value.size_bytes == ref["size_bytes"]
        physical.append(value)
        by_id[value.artifact_id] = value
    for item in bundle["physical_views"]:
        parent = by_id[item["source_id"]]
        raw = item["text"].encode("utf-8")
        assert __import__("hashlib").sha256(raw).hexdigest() == item["text_sha256"]
        views.append(_view(
            parent=parent,
            local_view_id=item["view_id"],
            raw=raw,
            media_type="text/plain",
            observed_at=observed_at,
            page_index=(item.get("origin", {}).get("page_number") or 1) - 1,
            method=item["origin"]["method"],
        ))
    for item in bundle["native_attachments"]:
        parent = by_id[item["source_id"]]
        for page in item["rendered_page_images"]:
            raw, content_sha256, _ = _content(SOURCE_RUN / "prepared" / page["path"])
            assert content_sha256 == page["sha256"]
            views.append(_view(
                parent=parent,
                local_view_id="original.pdf.page.%04d.image" % page["page_number"],
                raw=raw,
                media_type="image/png",
                observed_at=observed_at,
                page_index=page["page_number"] - 1,
                method="rendered page pixels from exact parent PDF",
            ))
    research, research_views = _research_sources(
        episode["initial_dossier"]["research_record"], observed_at
    )
    physical.append(research)
    views.extend(research_views)
    return LifecycleEventV2(
        event_id="native-source041-initial",
        observed_at=observed_at,
        physical_artifacts=tuple(physical),
        derived_views=tuple(views),
    )


def _later_event(
    event_id: str,
    artifact: dict[str, Any],
    observed_at: str,
    delivered_request_ids: tuple[str, ...] = (),
) -> LifecycleEventV2:
    physical, views = _research_sources(artifact, observed_at)
    return LifecycleEventV2(
        event_id=event_id,
        observed_at=observed_at,
        physical_artifacts=(physical,),
        derived_views=tuple(views),
        delivered_request_ids=delivered_request_ids,
    )


def _completion_raw(completion: dict[str, Any]) -> dict[str, Any]:
    text = completion["raw_generated_text"].replace("<|im_end|>", "").strip()
    if text.startswith("```json"):
        text = text[len("```json") :]
    if text.endswith("```"):
        text = text[:-3]
    return json.loads(text.strip())


def _binding(
    trajectory: dict[str, Any],
    completion: dict[str, Any],
    source_artifact_id: str,
) -> LifecycleProposalBindingV2:
    raw_need = next(
        value for value in _completion_raw(completion)["needs"]
        if value["need_id"] == "n0"
    )
    decoded_need = next(
        value for value in trajectory["decoded"]["needs"]
        if value["need_id"] == "n0"
    )
    references = []
    for value in decoded_need["evidence_resolved"]:
        resolved = value["resolved"]
        if resolved["source_id"] != source_artifact_id:
            continue
        references.append(LifecycleSourceReferenceV2(
            public_ref=value["ref"],
            view_id=f"{source_artifact_id}:{resolved['view_id']}",
            view_content_sha256=(
                resolved["view_text_sha256"]
                if resolved["kind"] == "text"
                else resolved["sha256"]
            ),
            text_start=(resolved["char_start"] if resolved["kind"] == "text" else None),
            text_end=(resolved["char_end"] if resolved["kind"] == "text" else None),
            exact_text_sha256=(
                resolved["text_sha256"] if resolved["kind"] == "text" else None
            ),
        ))
    assert references
    coverage = {
        "missing": "unresolved",
        "partial": "partial",
        "received": "complete",
    }.get(raw_need["state"], "unresolved")
    return LifecycleProposalBindingV2(
        obligation_id="n0",
        source_artifact_id=source_artifact_id,
        source_refs=tuple(references),
        relation="compatible",
        reported_coverage=coverage,
        reported_facts=((raw_need["answer"],) if raw_need.get("answer") else ()),
    )


def _receipt(
    completion: dict[str, Any],
    trajectory: dict[str, Any],
    bindings: tuple[LifecycleProposalBindingV2, ...],
    supersede_interpretation_ids: tuple[str, ...] = (),
) -> LifecycleProposalReceiptV2:
    identity = completion["run_identity"]
    material = {
        "contract": "casepath.lifecycle-proposal-receipt/2.0.0",
        "producer_kind": "model",
        "record_id": completion["id"],
        "producer_id": completion["run_identity"]["model_class"],
        "producer_revision": completion["run_identity"]["model_revision"],
        "input_sha256": completion["input_sha256"],
        "rendered_prompt_sha256": completion["rendered_sha256"],
        "source_prefix_sha256": trajectory["public_prefix_sha256"],
        "output_sha256": digest_text(completion["raw_generated_text"]),
        "proposal_projection_sha256": proposal_projection_sha256_v2(
            bindings, supersede_interpretation_ids
        ),
        "upstream_completion_sha256": digest_value(completion),
        "run_fingerprint_sha256": completion["run_fingerprint"],
        "producer_identity_sha256": digest_value(identity),
        "processor_input_fingerprint": completion["processor_input_fingerprint"],
        "status": completion["status"],
        "finish_reason": completion["finish_reason"],
        "failure": completion.get("failure"),
    }
    return LifecycleProposalReceiptV2(
        **material, receipt_sha256=digest_value(material)
    )


def _payload(
    *,
    operation_id: str,
    obligations: tuple[LifecycleObligationV2, ...],
    state: LifecycleStateV2,
    event: LifecycleEventV2,
    trajectory: dict[str, Any],
    completion: dict[str, Any],
    bindings: tuple[LifecycleProposalBindingV2, ...],
    supersede_interpretation_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "contract": "casepath.document-lifecycle-shadow-request/2.0.0",
        "operation_id": operation_id,
        "obligations": [value.model_dump(mode="json") for value in obligations],
        "previous_state": state.model_dump(mode="json"),
        "expected_parent_state_sha256": lifecycle_state_sha256_v2(state),
        "event": event.model_dump(mode="json"),
        "source_prefix_sha256": trajectory["public_prefix_sha256"],
        "raw_proposed_output": completion["raw_generated_text"],
        "proposal_bindings": [value.model_dump(mode="json") for value in bindings],
        "supersede_interpretation_ids": list(supersede_interpretation_ids),
        "proposal_receipt": _receipt(
            completion, trajectory, bindings, supersede_interpretation_ids
        ).model_dump(mode="json"),
        "max_requests": 2,
    }


@pytest.fixture(scope="module")
def saved_source041() -> dict[str, Any]:
    if not SOURCE_RUN.exists():
        pytest.skip("saved native source-binding run is unavailable")
    episode = next(
        value for value in _jsonl(SOURCE_RUN / "prepared/public-episodes.jsonl")
        if value["episode_id"] == EPISODE_ID
    )
    trajectories = {
        value["step"]: value
        for value in _jsonl(SOURCE_RUN / "outputs/worker2/trajectory.jsonl")
        if value["episode"] == EPISODE_ID
    }
    completions = {
        int(value["id"].rsplit(".", 1)[1]): value
        for value in _jsonl(SOURCE_RUN / "outputs/worker2/completions.jsonl")
        if f".{EPISODE_ID}." in value["id"]
    }
    assert set(trajectories) == set(completions) == {0, 1, 2}
    first_need = next(
        value for value in _completion_raw(completions[0])["needs"]
        if value["need_id"] == "n0"
    )
    obligations = (LifecycleObligationV2(
        obligation_id="n0",
        description=first_need["description"],
        provider_keys=("record_provider",),
        scope_key="reported_rent_increase_calculation_basis",
        timing_key="current_record",
        warrant_refs=tuple(first_need["warrant_refs"]),
    ),)
    return {
        "episode": episode,
        "trajectories": trajectories,
        "completions": completions,
        "obligations": obligations,
    }


def _post(client: TestClient, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.post(DOCUMENT_LIFECYCLE_V2_ROUTE, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def _three_step_replay(saved: dict[str, Any]) -> dict[str, Any]:
    from casepath_api.app import app

    client = TestClient(app)
    assert DOCUMENT_LIFECYCLE_V2_ROUTE in {route.path for route in app.routes}
    episode = saved["episode"]
    trajectories = saved["trajectories"]
    completions = saved["completions"]
    obligations = saved["obligations"]
    state = new_lifecycle_state_v2(obligations)

    wrong_source = episode["initial_dossier"]["research_record"]["source_id"]
    binding0 = (_binding(trajectories[0], completions[0], wrong_source),)
    payload0 = _payload(
        operation_id="source041.initial",
        obligations=obligations,
        state=state,
        event=_initial_event(episode),
        trajectory=trajectories[0],
        completion=completions[0],
        bindings=binding0,
    )
    result0 = _post(client, payload0)
    request_id = result0["next_actions"]["requests"][0]["request_id"]
    state0 = LifecycleStateV2.model_validate(result0["state"])

    event1_value = episode["events"][0]
    reply = event1_value["adaptive_delivery"]["on_semantically_matched_complete_request"][0]
    binding1 = (_binding(trajectories[1], completions[1], reply["source_id"]),)
    event1 = _later_event(
        "source041.requested-noah-reply",
        reply,
        event1_value["observed_at"],
        (request_id,),
    )
    payload1 = _payload(
        operation_id="source041.reply",
        obligations=obligations,
        state=state0,
        event=event1,
        trajectory=trajectories[1],
        completion=completions[1],
        bindings=binding1,
    )
    result1 = _post(client, payload1)
    state1 = LifecycleStateV2.model_validate(result1["state"])

    event2_value = episode["events"][1]
    correction = event2_value["received_research_artifacts"][0]
    binding2 = (_binding(trajectories[2], completions[2], reply["source_id"]),)
    payload2 = _payload(
        operation_id="source041.unrelated-correction",
        obligations=obligations,
        state=state1,
        event=_later_event(
            "source041.unrelated-nora-correction",
            correction,
            event2_value["observed_at"],
        ),
        trajectory=trajectories[2],
        completion=completions[2],
        bindings=binding2,
    )
    result2 = _post(client, payload2)
    return {
        "client": client,
        "payload0": payload0,
        "payload1": payload1,
        "payload2": payload2,
        "result0": result0,
        "result1": result1,
        "result2": result2,
        "reply": reply,
        "correction": correction,
    }


def test_saved_source041_native_replay_preserves_provenance_and_locality(
    saved_source041: dict[str, Any],
) -> None:
    replay = _three_step_replay(saved_source041)
    result0, result1, result2 = (
        replay["result0"], replay["result1"], replay["result2"]
    )
    reply, correction = replay["reply"], replay["correction"]

    for payload, result in (
        (replay["payload0"], result0),
        (replay["payload1"], result1),
        (replay["payload2"], result2),
    ):
        stored_artifacts = {
            value["artifact_id"]: value
            for value in result["state"]["physical_artifacts"]
        }
        stored_views = {
            value["view_id"]: value for value in result["state"]["derived_views"]
        }
        for value in payload["event"]["physical_artifacts"]:
            assert stored_artifacts[value["artifact_id"]] == value
        for value in payload["event"]["derived_views"]:
            assert stored_views[value["view_id"]] == value
        transition = dict(result["transition_receipt"])
        receipt_sha256 = transition.pop("receipt_sha256")
        assert receipt_sha256 == digest_value(transition)

    assert result0["obligation_view"][0]["certified_state"] == "open"
    assert result0["obligation_view"][0]["suggested_state"] == "open"
    assert result0["obligation_view"][0]["accepted_complete"] is False
    assert result0["next_actions"]["requests"][0]["obligation_id"] == "n0"
    assert result0["proposal_receipt"] == replay["payload0"]["proposal_receipt"]
    assert {
        value["public_ref"]
        for value in result0["state"]["interpretations"][0]["source_refs"]
    } == {"p3", "t13", "t14"}
    assert result1["request_delivery_receipts"][0]["request_id"] == (
        result0["next_actions"]["requests"][0]["request_id"]
    )
    assert result1["obligation_view"][0]["reported_coverage"] == "partial"
    assert result1["obligation_view"][0]["suggested_state"] == "partial"
    assert result1["obligation_view"][0]["accepted_complete"] is False
    assert result1["next_actions"]["documents_complete"] is False
    assert result1["proposal_receipt"] == replay["payload1"]["proposal_receipt"]
    assert {value["public_ref"] for value in result1["state"]["interpretations"][1]["source_refs"]} == {
        "p4", "t309", "t310", "t312"
    }

    inventory1 = {
        value["artifact_id"]: value for value in result1["state"]["physical_artifacts"]
    }
    assert inventory1[reply["source_id"]]["content_sha256"] == reply["sha256"]
    assert inventory1[reply["source_id"]]["size_bytes"] == reply["size_bytes"]
    assert base64.b64decode(inventory1[reply["source_id"]]["content_b64"]) == (
        SOURCE_RUN / "prepared" / reply["path"]
    ).read_bytes()
    reply_view_hashes = {
        value["content_sha256"] for value in result1["state"]["derived_views"]
        if value["parent_artifact_id"] == reply["source_id"]
    }
    assert reply_view_hashes == {
        reply["text_pages"][0]["text_sha256"],
        reply["rendered_page_images"][0]["sha256"],
    }

    assert result2["obligation_view"] == result1["obligation_view"]
    assert result2["next_actions"] == result1["next_actions"]
    assert result2["interpretation_results"][0]["status"] == "deduplicated"
    inventory2 = {
        value["artifact_id"]: value for value in result2["state"]["physical_artifacts"]
    }
    assert inventory2[correction["source_id"]]["content_sha256"] == correction["sha256"]
    assert result2["canonical_state_mutated"] is False
    assert result2["next_actions"]["documents_complete"] is False
    assert len(result2["state"]["proposal_receipts"]) == 3
    assert len(result2["state"]["event_receipts"]) == 3
    assert result2["proposal_receipt"] == replay["payload2"]["proposal_receipt"]


@pytest.fixture()
def replay(saved_source041: dict[str, Any]) -> dict[str, Any]:
    return _three_step_replay(saved_source041)


def _status(client: TestClient, payload: dict[str, Any]) -> tuple[int, str]:
    response = client.post(DOCUMENT_LIFECYCLE_V2_ROUTE, json=payload)
    return response.status_code, response.text


def test_one_byte_mutation_is_rejected(replay: dict[str, Any]) -> None:
    payload = deepcopy(replay["payload1"])
    artifact = payload["event"]["physical_artifacts"][0]
    raw = bytearray(base64.b64decode(artifact["content_b64"]))
    raw[-1] ^= 1
    artifact["content_b64"] = base64.b64encode(raw).decode("ascii")
    status, text = _status(replay["client"], payload)
    assert status == 422
    assert "content_bytes_size_or_hash_differ" in text


def test_cross_parent_view_swap_is_rejected(replay: dict[str, Any]) -> None:
    payload = deepcopy(replay["payload0"])
    artifacts = payload["event"]["physical_artifacts"]
    view = next(
        value for value in payload["event"]["derived_views"]
        if value["parent_artifact_id"].startswith("research_source_")
    )
    other = next(value for value in artifacts if value["artifact_id"] == "source_041_attachment_01")
    view["parent_artifact_id"] = other["artifact_id"]
    fields = {key: view[key] for key in (
        "parent_artifact_id", "parent_artifact_sha256", "media_type",
        "content_sha256", "size_bytes", "page_index", "derivation_method",
        "observed_at",
    )}
    view["derivation_sha256"] = derivation_sha256_v2(**fields)
    status, text = _status(replay["client"], payload)
    assert status == 422
    assert "view_parent_identity_differs" in text


def test_binary_cannot_be_declared_as_text(replay: dict[str, Any]) -> None:
    payload = deepcopy(replay["payload1"])
    artifact = payload["event"]["physical_artifacts"][0]
    artifact["media_type"] = "text/plain"
    artifact["decoded_text"] = "not an authoritative decoding"
    status, text = _status(replay["client"], payload)
    assert status == 422
    assert (
        "binary_content_cannot_be_declared_as_text" in text
        or "text_content_is_not_strict_utf8" in text
    )


def test_parent_continuity_and_duplicate_event_replay_are_rejected(
    replay: dict[str, Any],
) -> None:
    stale = deepcopy(replay["payload1"])
    stale["expected_parent_state_sha256"] = digest_text("stale parent")
    status, text = _status(replay["client"], stale)
    assert status == 422
    assert "parent_state_hash_differs" in text

    payload = deepcopy(replay["payload1"])
    state = LifecycleStateV2.model_validate(replay["result1"]["state"])
    payload["previous_state"] = state.model_dump(mode="json")
    payload["expected_parent_state_sha256"] = lifecycle_state_sha256_v2(state)
    status, text = _status(replay["client"], payload)
    assert status == 422
    assert "event_id_was_already_observed" in text


def test_reordered_state_and_backdated_event_are_rejected(replay: dict[str, Any]) -> None:
    reordered = deepcopy(replay["payload2"])
    reordered["previous_state"]["event_receipts"].reverse()
    status, text = _status(replay["client"], reordered)
    assert status == 422
    assert "state_events_are_reordered_or_backdated" in text

    backdated = deepcopy(replay["payload2"])
    old_time = replay["payload1"]["event"]["observed_at"]
    backdated["event"]["event_id"] = "source041.backdated"
    backdated["event"]["observed_at"] = old_time
    for artifact in backdated["event"]["physical_artifacts"]:
        artifact["observed_at"] = old_time
    for view in backdated["event"]["derived_views"]:
        view["observed_at"] = old_time
        fields = {key: view[key] for key in (
            "parent_artifact_id", "parent_artifact_sha256", "media_type",
            "content_sha256", "size_bytes", "page_index", "derivation_method",
            "observed_at",
        )}
        view["derivation_sha256"] = derivation_sha256_v2(**fields)
    status, text = _status(replay["client"], backdated)
    assert status == 422
    assert "event_is_reordered_or_backdated" in text


def test_future_artifact_is_rejected(replay: dict[str, Any]) -> None:
    payload = deepcopy(replay["payload1"])
    payload["event"]["physical_artifacts"][0]["observed_at"] = (
        "2025-11-24T15:31:00+01:00"
    )
    status, text = _status(replay["client"], payload)
    assert status == 422
    assert "future_artifact_cannot_enter_event" in text


def test_model_reported_complete_does_not_become_accepted_complete(
    replay: dict[str, Any],
) -> None:
    payload = deepcopy(replay["payload1"])
    payload["operation_id"] = "source041.model-complete-negative-control"
    payload["proposal_bindings"][0]["reported_coverage"] = "complete"
    bindings = tuple(
        LifecycleProposalBindingV2.model_validate(value)
        for value in payload["proposal_bindings"]
    )
    receipt = dict(payload["proposal_receipt"])
    receipt["proposal_projection_sha256"] = proposal_projection_sha256_v2(
        bindings
    )
    receipt.pop("receipt_sha256")
    receipt["receipt_sha256"] = digest_value(receipt)
    payload["proposal_receipt"] = receipt

    result = _post(replay["client"], payload)
    assert result["obligation_view"][0]["reported_coverage"] == "complete"
    assert result["obligation_view"][0]["accepted_complete"] is False
    assert result["obligation_view"][0]["certified_state"] == "open"
    assert result["obligation_view"][0]["suggested_state"] == "complete"
    assert result["next_actions"]["documents_complete"] is False
    assert result["next_actions"]["certified_documents_complete"] is False
    assert result["next_actions"]["suggested_documents_complete"] is True
    assert result["next_actions"]["requests"] == []
    assert result["next_actions"]["suppressed_requests"][0]["obligation_id"] == "n0"

    incompatible = deepcopy(replay["payload0"]["proposal_bindings"][0])
    incompatible["relation"] = "incompatible"
    payload["proposal_bindings"].append(incompatible)
    bindings = tuple(
        LifecycleProposalBindingV2.model_validate(value)
        for value in payload["proposal_bindings"]
    )
    receipt = dict(payload["proposal_receipt"])
    receipt["proposal_projection_sha256"] = proposal_projection_sha256_v2(
        bindings
    )
    receipt.pop("receipt_sha256")
    receipt["receipt_sha256"] = digest_value(receipt)
    payload["proposal_receipt"] = receipt
    unaffected = _post(replay["client"], payload)
    view = unaffected["obligation_view"][0]
    assert view["suggested_state"] == "complete"
    assert len(view["rejected_source_interpretation_ids"]) == 1
    assert unaffected["next_actions"]["requests"] == []


def test_issued_history_accepts_delayed_delivery_and_supersession_reopens_request(
    replay: dict[str, Any],
) -> None:
    complete_payload = deepcopy(replay["payload1"])
    complete_payload["operation_id"] = "source041.complete-before-correction"
    complete_payload["proposal_bindings"][0]["reported_coverage"] = "complete"
    complete_bindings = tuple(
        LifecycleProposalBindingV2.model_validate(value)
        for value in complete_payload["proposal_bindings"]
    )
    receipt = dict(complete_payload["proposal_receipt"])
    receipt["proposal_projection_sha256"] = proposal_projection_sha256_v2(
        complete_bindings
    )
    receipt.pop("receipt_sha256")
    receipt["receipt_sha256"] = digest_value(receipt)
    complete_payload["proposal_receipt"] = receipt
    complete = _post(replay["client"], complete_payload)
    complete_state = LifecycleStateV2.model_validate(complete["state"])
    assert complete_state.current_request_ids == ()
    assert complete_state.issued_request_ids

    complete_id = next(
        value["interpretation_id"]
        for value in complete["state"]["interpretations"]
        if value["reported_coverage"] == "complete"
    )
    correction_payload = deepcopy(replay["payload2"])
    correction_payload["operation_id"] = "source041.superseding-correction"
    correction_payload["previous_state"] = complete_state.model_dump(mode="json")
    correction_payload["expected_parent_state_sha256"] = lifecycle_state_sha256_v2(
        complete_state
    )
    delayed_request_id = complete_state.issued_request_ids[0]
    correction_payload["event"]["delivered_request_ids"] = [delayed_request_id]
    correction_payload["supersede_interpretation_ids"] = [complete_id]
    correction_bindings = tuple(
        LifecycleProposalBindingV2.model_validate(value)
        for value in correction_payload["proposal_bindings"]
    )
    receipt = dict(correction_payload["proposal_receipt"])
    receipt["proposal_projection_sha256"] = proposal_projection_sha256_v2(
        correction_bindings, (complete_id,)
    )
    receipt.pop("receipt_sha256")
    receipt["receipt_sha256"] = digest_value(receipt)
    correction_payload["proposal_receipt"] = receipt

    corrected = _post(replay["client"], correction_payload)
    assert corrected["request_delivery_receipts"][0]["request_id"] == (
        delayed_request_id
    )
    assert corrected["supersession_results"][0]["interpretation_id"] == complete_id
    assert corrected["obligation_view"][0]["suggested_state"] == "partial"
    assert corrected["next_actions"]["requests"][0]["obligation_id"] == "n0"
    corrected_state = LifecycleStateV2.model_validate(corrected["state"])
    assert delayed_request_id in corrected_state.issued_request_ids
    assert delayed_request_id in corrected_state.current_request_ids
