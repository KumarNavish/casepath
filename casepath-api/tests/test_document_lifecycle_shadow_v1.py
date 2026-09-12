from __future__ import annotations

import base64
import json
from datetime import datetime
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from casepath_api.document_lifecycle_shadow_v1 import (
    DOCUMENT_LIFECYCLE_ROUTE,
    DocumentLifecycleShadowError,
    DocumentLifecycleShadowRequestV1,
    LifecycleEventV1,
    LifecycleObligationV1,
    LifecycleProposalReceiptV1,
    LifecycleReceiptEnvelopeV1,
    LifecycleSourceV1,
    LifecycleStateV1,
    apply_document_lifecycle_shadow,
    lifecycle_adapter_payload_sha256,
    lifecycle_state_sha256,
    new_lifecycle_state,
)
from casepath_api.foundation.common import digest_text, digest_value


def _envelope(observed_at: str, sender: str = "constructed:test") -> LifecycleReceiptEnvelopeV1:
    return LifecycleReceiptEnvelopeV1(
        channel="synthetic_message",
        sender=sender,
        observed_at=observed_at,
    )


def _source(
    source_id: str,
    text: str,
    *,
    observed_at: str,
    source_kind: str = "document",
    source_version: str = "fixture-v1",
    receipt_envelope: LifecycleReceiptEnvelopeV1 | None = None,
) -> LifecycleSourceV1:
    raw = text.encode("utf-8")
    return LifecycleSourceV1(
        source_id=source_id,
        source_version=source_version,
        source_kind=source_kind,
        content_sha256=sha256(raw).hexdigest(),
        content_b64=base64.b64encode(raw).decode("ascii"),
        decoded_text=text,
        observed_at=observed_at,
        receipt_envelope=receipt_envelope,
    )


def _event(
    event_id: str,
    text: str,
    *,
    observed_at: str,
    documents: tuple[LifecycleSourceV1, ...] = (),
    received: bool = True,
) -> LifecycleEventV1:
    raw = text.encode("utf-8")
    return LifecycleEventV1(
        event_id=event_id,
        received=received,
        observed_at=observed_at,
        text_sha256=sha256(raw).hexdigest(),
        text_b64=base64.b64encode(raw).decode("ascii"),
        text=text,
        documents=documents,
    )


def _obligation(obligation_id: str) -> LifecycleObligationV1:
    return LifecycleObligationV1(
        obligation_id=obligation_id,
        title=f"Document for {obligation_id}",
        provider_keys=("provider",),
        scope_key=f"scope/{obligation_id}",
        timing_key="current",
        accepted_evidence_types=("record",),
        anchor_source_id="claim",
        quote_anchor="document needed",
        quote_start=0,
        quote_end=15,
    )


def _receipt(
    raw_output: str,
    source_prefix_sha256: str,
    adapter_payload_sha256: str,
    *,
    producer_kind: str = "test_fixture",
    identity: dict[str, Any] | None = None,
    **overrides: Any,
) -> LifecycleProposalReceiptV1:
    producer_identity = identity or {"fixture": "document-lifecycle-v1"}
    material: dict[str, Any] = {
        "contract": "casepath.document-lifecycle-proposal-receipt/1.0.0",
        "producer_kind": producer_kind,
        "record_id": "proposal.fixture.1",
        "producer_id": "fixture-parser",
        "producer_revision": "fixture-r1",
        "input_sha256": digest_text("input"),
        "rendered_prompt_sha256": digest_text("prompt"),
        "source_prefix_sha256": source_prefix_sha256,
        "output_sha256": digest_text(raw_output),
        "adapter_payload_sha256": adapter_payload_sha256,
        "input_tokens": 0,
        "output_tokens": 0,
        "status": "success",
        "finish_reason": "eos",
        "failure": None,
        "run_fingerprint_sha256": digest_text("run"),
        "producer_identity": producer_identity,
        "producer_identity_sha256": digest_value(producer_identity),
        "runtime": {"kind": "test"},
        "settings": {"deterministic": True},
        "cost_usd": None,
        "cost_basis": "unavailable",
    }
    material.update(overrides)
    material["receipt_sha256"] = digest_value(material)
    return LifecycleProposalReceiptV1.model_validate(material)


def _request(
    *,
    state: LifecycleStateV1,
    obligations: tuple[LifecycleObligationV1, ...],
    event: LifecycleEventV1,
    raw_output: str,
    source_prefix_sha256: str | None = None,
    expected_parent_state_sha256: str | None = None,
    receipt: LifecycleProposalReceiptV1 | None = None,
) -> DocumentLifecycleShadowRequestV1:
    prefix = source_prefix_sha256 or digest_text(f"prefix:{event.event_id}")
    adapter_payload = lifecycle_adapter_payload_sha256(state, obligations, event)
    return DocumentLifecycleShadowRequestV1(
        operation_id=f"test:{event.event_id}",
        obligations=obligations,
        previous_state=state,
        expected_parent_state_sha256=(
            expected_parent_state_sha256 or lifecycle_state_sha256(state)
        ),
        event=event,
        source_prefix_sha256=prefix,
        raw_proposed_output=raw_output,
        proposal_receipt=receipt or _receipt(raw_output, prefix, adapter_payload),
    )


def _next_state(result: dict[str, Any]) -> LifecycleStateV1:
    return LifecycleStateV1.model_validate(result["state"])


def _empty_output(**updates: Any) -> str:
    value = {"bind": [], "withdraw": [], "promise": [], "cancel": []}
    value.update(updates)
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def test_one_source_can_promise_two_obligations_and_wait_uses_earliest_instant() -> None:
    obligations = (_obligation("O1"), _obligation("O2"))
    state = new_lifecycle_state(
        sources=(
            _source(
                "claim",
                "document needed",
                observed_at="2026-05-01T08:00:00Z",
                source_kind="claim",
            ),
        )
    )
    event = _event("F1", "Both records will arrive.", observed_at="2026-05-02T08:00:00Z")
    raw = _empty_output(
        promise=[
            ["F1", "O1", "2026-05-05T10:00:00+02:00"],
            ["F1", "O2", "2026-05-05T07:30:00-01:00"],
        ]
    )

    result = apply_document_lifecycle_shadow(
        _request(state=state, obligations=obligations, event=event, raw_output=raw)
    )

    commitments = result["state"]["commitments"]
    assert len(commitments) == 2
    assert len({value["commitment_id"] for value in commitments}) == 2
    assert {(value["source_id"], value["obligation_id"]) for value in commitments} == {
        ("F1", "O1"),
        ("F1", "O2"),
    }
    waits = {value["obligation_id"]: value for value in result["next_actions"]["waits"]}
    assert waits["O1"]["until_utc"] == "2026-05-05T08:00:00Z"
    assert waits["O2"]["until_utc"] == "2026-05-05T08:30:00Z"


def test_multiple_sources_for_one_obligation_use_earliest_absolute_instant() -> None:
    obligations = (_obligation("O1"),)
    state = new_lifecycle_state(sources=())
    first_event = _event("F1", "First promise.", observed_at="2026-05-02T08:00:00Z")
    first_raw = _empty_output(
        promise=[["F1", "O1", "2026-05-05T10:00:00+02:00"]]
    )
    first = apply_document_lifecycle_shadow(
        _request(
            state=state,
            obligations=obligations,
            event=first_event,
            raw_output=first_raw,
        )
    )
    second_event = _event("F2", "Second promise.", observed_at="2026-05-02T09:00:00Z")
    second_raw = _empty_output(
        promise=[["F2", "O1", "2026-05-05T08:30:00+01:00"]]
    )

    result = apply_document_lifecycle_shadow(
        _request(
            state=_next_state(first),
            obligations=obligations,
            event=second_event,
            raw_output=second_raw,
        )
    )

    assert len([value for value in result["state"]["commitments"] if value["active"]]) == 2
    assert result["next_actions"]["waits"][0]["until_original"] == (
        "2026-05-05T08:30:00+01:00"
    )
    assert result["next_actions"]["waits"][0]["until_utc"] == "2026-05-05T07:30:00Z"


def test_scoped_retraction_preserves_sibling_binding_and_raw_bytes() -> None:
    obligations = (_obligation("O1"), _obligation("O2"))
    document = _source("D1", "one record, two fields", observed_at="2026-05-02T08:00:00Z")
    state = new_lifecycle_state(
        sources=(document,),
        bindings=(("D1", "O1", "support"), ("D1", "O2", "support")),
    )
    event = _event("F2", "Retract only field O1.", observed_at="2026-05-03T08:00:00Z")
    raw = _empty_output(withdraw=[["D1", "O1"]])

    result = apply_document_lifecycle_shadow(
        _request(state=state, obligations=obligations, event=event, raw_output=raw)
    )

    view = {value["obligation_id"]: value for value in result["obligation_view"]}
    assert view["O1"]["state"] == "withdrawn"
    assert view["O2"]["state"] == "received"
    assert any(value["source_id"] == "D1" for value in result["source_inventory"])
    assert _next_state(result).sources[0].decoded_text == "one record, two fields"


def test_timezone_equivalence_mixed_offsets_and_naive_sibling_isolation() -> None:
    obligations = tuple(_obligation(f"O{index}") for index in range(1, 6))
    state = new_lifecycle_state(sources=())
    valid_document = _source(
        "D1",
        "valid sibling",
        observed_at="2026-05-02T08:00:00Z",
        receipt_envelope=_envelope("2026-05-02T10:00:00+02:00"),
    )
    event = _event(
        "F1",
        "Promises and a document.",
        observed_at="2026-05-02T10:00:00+02:00",
        documents=(valid_document,),
    )
    raw = _empty_output(
        bind=[["D1", "O5", "support"]],
        promise=[
            ["F1", "O1", "2026-05-05T10:00:00+02:00"],
            ["F1", "O2", "2026-05-05T07:30:00-01:00"],
            ["F1", "O3", "2026-05-06T09:00:00"],
            ["F1", "O4", None],
        ],
    )

    result = apply_document_lifecycle_shadow(
        _request(state=state, obligations=obligations, event=event, raw_output=raw)
    )

    statuses = [value["status"] for value in result["operation_results"]]
    assert statuses == [
        "admitted",
        "admitted",
        "admitted",
        "admitted_unresolved_time",
        "admitted_unresolved_time",
    ]
    view = {value["obligation_id"]: value for value in result["obligation_view"]}
    assert view["O5"]["state"] == "received"
    assert view["O3"]["state"] == view["O4"]["state"] == "pending"
    unresolved = [
        value
        for value in result["state"]["commitments"]
        if value["timestamp_status"] == "unresolved"
    ]
    assert len(unresolved) == 2
    assert {value["available_at_original"] for value in unresolved} == {
        "2026-05-06T09:00:00",
        None,
    }


def test_stale_parent_admits_sources_but_quarantines_semantic_operations() -> None:
    obligations = (_obligation("O1"),)
    state = new_lifecycle_state(sources=())
    document = _source("D1", "observed bytes", observed_at="2026-05-02T08:00:00Z")
    event = _event(
        "F1", "New attachment.", observed_at="2026-05-02T08:00:00Z", documents=(document,)
    )
    raw = _empty_output(bind=[["D1", "O1", "support"]])

    result = apply_document_lifecycle_shadow(
        _request(
            state=state,
            obligations=obligations,
            event=event,
            raw_output=raw,
            expected_parent_state_sha256=digest_text("stale"),
        )
    )

    assert result["parent_state_matches"] is False
    assert result["operation_results"][0]["reason"] == "stale_parent_state"
    assert result["state"]["bindings"] == []
    assert {value["source_id"] for value in result["source_inventory"]} == {"D1", "F1"}


def test_hash_and_id_mismatches_are_isolated() -> None:
    obligations = (_obligation("O1"), _obligation("O2"))
    state = new_lifecycle_state(sources=())
    event = _event("F1", "Promise only.", observed_at="2026-05-02T08:00:00Z")
    raw = _empty_output(
        bind=[["UNKNOWN", "O1", "support"]],
        promise=[["F1", "O2", "2026-05-03T08:00:00Z"]],
    )
    result = apply_document_lifecycle_shadow(
        _request(state=state, obligations=obligations, event=event, raw_output=raw)
    )
    assert [value["status"] for value in result["operation_results"]] == [
        "quarantined",
        "admitted",
    ]

    prefix = digest_text("prefix")
    payload = lifecycle_adapter_payload_sha256(state, obligations, event)
    bad_receipt = _receipt(
        raw, prefix, payload, output_sha256=digest_text("different")
    )
    with pytest.raises(DocumentLifecycleShadowError, match="proposal_output_hash_differs"):
        apply_document_lifecycle_shadow(
            _request(
                state=state,
                obligations=obligations,
                event=event,
                raw_output=raw,
                source_prefix_sha256=prefix,
                receipt=bad_receipt,
            )
        )

    swapped_event = _event("F2", "Different bytes.", observed_at="2026-05-02T08:00:00Z")
    bound_receipt = _receipt(raw, prefix, payload)
    with pytest.raises(
        DocumentLifecycleShadowError, match="proposal_adapter_payload_hash_differs"
    ):
        apply_document_lifecycle_shadow(
            _request(
                state=state,
                obligations=obligations,
                event=swapped_event,
                raw_output=raw,
                source_prefix_sha256=prefix,
                receipt=bound_receipt,
            )
        )

    colliding = new_lifecycle_state(
        sources=(
            _source(
                "F1",
                "existing claim bytes",
                observed_at="2026-05-02T08:00:00Z",
                source_kind="claim",
            ),
        )
    )
    collision_result = apply_document_lifecycle_shadow(
        _request(
            state=colliding,
            obligations=obligations,
            event=event,
            raw_output=raw,
        )
    )
    assert collision_result["source_admission_results"][0]["reason"] == (
        "source_id_identity_mismatch"
    )
    assert {value["reason"] for value in collision_result["operation_results"]} == {
        "current_event_source_not_admitted"
    }


def test_repeated_exact_bytes_are_retained_but_not_corroborated_twice() -> None:
    obligations = (_obligation("O1"),)
    first = _source("I1", "same bytes", observed_at="2026-05-01T08:00:00Z")
    state = new_lifecycle_state(
        sources=(first,),
        bindings=(("I1", "O1", "support"),),
    )
    duplicate = _source("D4", "same bytes", observed_at="2026-05-02T08:00:00Z")
    event = _event(
        "F4", "Repeated delivery.", observed_at="2026-05-02T08:00:00Z", documents=(duplicate,)
    )
    raw = _empty_output(bind=[["D4", "O1", "support"]])

    result = apply_document_lifecycle_shadow(
        _request(state=state, obligations=obligations, event=event, raw_output=raw)
    )

    assert result["operation_results"][0]["status"] == "deduplicated"
    assert len([value for value in result["state"]["bindings"] if value["active"]]) == 1
    duplicate_inventory = next(
        value for value in result["source_inventory"] if value["source_id"] == "D4"
    )
    assert duplicate_inventory["canonical_evidence_id"] == "I1"
    assert duplicate_inventory["exact_byte_duplicate"] is True


def test_withdrawn_binding_cannot_be_revived_by_duplicate_or_backdated_receipt() -> None:
    obligations = (_obligation("O1"),)
    original = _source("I1", "same bytes", observed_at="2026-05-01T08:00:00Z")
    state = new_lifecycle_state(
        sources=(original,),
        bindings=(("I1", "O1", "support"),),
    )
    withdrawal_event = _event(
        "F1", "Withdraw I1.", observed_at="2026-05-02T08:00:00Z"
    )
    withdrawal_raw = _empty_output(withdraw=[["I1", "O1"]])
    withdrawn = apply_document_lifecycle_shadow(
        _request(
            state=state,
            obligations=obligations,
            event=withdrawal_event,
            raw_output=withdrawal_raw,
        )
    )
    backdated_duplicate = _source(
        "D0", "same bytes", observed_at="2026-04-01T08:00:00Z"
    )
    duplicate_event = _event(
        "F2",
        "Repeated old bytes.",
        observed_at="2026-04-01T08:00:00Z",
        documents=(backdated_duplicate,),
    )
    duplicate_raw = _empty_output(bind=[["D0", "O1", "support"]])

    result = apply_document_lifecycle_shadow(
        _request(
            state=_next_state(withdrawn),
            obligations=obligations,
            event=duplicate_event,
            raw_output=duplicate_raw,
        )
    )

    assert result["operation_results"][0]["status"] == "quarantined"
    assert result["operation_results"][0]["reason"] == (
        "retracted_binding_requires_explicit_revalidation"
    )
    assert result["obligation_view"][0]["state"] == "withdrawn"
    duplicate_inventory = next(
        value for value in result["source_inventory"] if value["source_id"] == "D0"
    )
    assert duplicate_inventory["canonical_evidence_id"] == "I1"
    assert duplicate_inventory["exact_byte_duplicate"] is True


def _claim_observed_at(raw: bytes) -> str:
    if raw.lstrip().startswith((b"From:", b"Date:")):
        message = BytesParser(policy=policy.default).parsebytes(raw)
        return parsedate_to_datetime(message["Date"]).isoformat()
    marker = "Zeitpunkt: "
    text = raw.decode("utf-8")
    value = next(line[len(marker) :] for line in text.splitlines() if line.startswith(marker))
    datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def _public_obligation(value: dict[str, Any]) -> LifecycleObligationV1:
    return LifecycleObligationV1(
        obligation_id=value["id"],
        title=value["title"],
        provider_keys=tuple(value["provider_keys"]),
        scope_key=value["scope_key"],
        timing_key=value["timing_key"],
        accepted_evidence_types=tuple(value["accepted_evidence_types"]),
        anchor_source_id=value["source_id"],
        quote_anchor=value["quote_anchor"],
        quote_start=value["quote_start"],
        quote_end=value["quote_end"],
    )


def _frozen_receipt(
    completion: dict[str, Any], source_prefix_sha256: str, adapter_payload_sha256: str
) -> LifecycleProposalReceiptV1:
    identity = completion["run_identity"]
    model = identity["model"]
    runtime = identity["runtime"]
    settings = identity["generation"]
    return _receipt(
        completion["raw_generated_text"],
        source_prefix_sha256,
        adapter_payload_sha256,
        producer_kind="model",
        identity=identity,
        record_id=completion["id"],
        producer_id="Qwen/Qwen3.8-27B",
        producer_revision=model["revision"],
        input_sha256=completion["input_sha256"],
        rendered_prompt_sha256=completion["rendered_sha256"],
        input_tokens=completion["input_tokens"],
        output_tokens=completion["output_tokens"],
        status=completion["status"],
        finish_reason=completion["finish_reason"],
        failure=completion.get("failure"),
        run_fingerprint_sha256=completion["run_fingerprint"],
        runtime=runtime,
        settings=settings,
    )


def _normalize_view(
    result: dict[str, Any], state: LifecycleStateV1
) -> list[dict[str, Any]]:
    source_by_commitment = {
        value.commitment_id: value.source_id for value in state.commitments if value.active
    }
    view = []
    for row in result["obligation_view"]:
        value = dict(row)
        value["pending_commitment_ids"] = sorted(
            source_by_commitment[item] for item in value["pending_commitment_ids"]
        )
        view.append(value)
    return view


def _snapshot(state: LifecycleStateV1) -> dict[str, Any]:
    return {
        "bindings": sorted(
            [value.evidence_id, value.obligation_id, value.relation]
            for value in state.bindings
        ),
        "withdrawn": sorted(
            {value.evidence_id for value in state.bindings if not value.active}
        ),
        "promises": sorted(
            [value.source_id, value.obligation_id, value.available_at_original]
            for value in state.commitments
            if value.active
        ),
    }


def _normalize_action(action: dict[str, Any]) -> dict[str, Any]:
    return {
        "requests": action["requests"],
        "eligible_requests": action["eligible_requests"],
        "waits": [
            {
                "obligation_id": value["obligation_id"],
                "until": value["until_original"],
            }
            for value in action["waits"]
        ],
        "documents_complete": action["documents_complete"],
    }


def test_frozen_base27_prefix_replay_reproduces_all_six_workflows() -> None:
    root = (
        Path(__file__).resolve().parents[3]
        / ".discovery-loop/coordinator-work/pro-investigator-r1/pro-work"
        / "casepath-independent-transition-r1-20260905/followup/ssh-output"
    )
    if not root.exists():
        pytest.skip("frozen independent-transition packet is not available")
    public_path = root / "author-packet/public-episodes.jsonl"
    private_path = root / "author-packet/private-construction.jsonl"
    completion_path = root / "base27/completions.jsonl"
    trajectory_path = root / "base27/trajectory.jsonl"
    public = {value["id"]: value for value in _jsonl(public_path)}
    private = {value["id"]: value for value in _jsonl(private_path)}
    completions = {value["id"]: value for value in _jsonl(completion_path)}
    trajectories = _jsonl(trajectory_path)
    assert set(public) == set(private) == {f"CP{index:03d}" for index in range(1, 7)}

    exact_steps = 0
    completed_workflows: set[str] = set()
    for episode_id, episode in public.items():
        raw_path = next((root / "raw-sources").glob(f"{episode['source_id']}.*"))
        claim_raw = raw_path.read_bytes()
        claim = _source(
            episode["source_id"],
            claim_raw.decode("utf-8"),
            observed_at=_claim_observed_at(claim_raw),
            source_kind="claim",
            source_version=episode["raw_source_sha256"],
        )
        initial_documents = []
        for value in episode["initial_constructed_documents"]:
            envelope = LifecycleReceiptEnvelopeV1.model_validate(value["receipt_envelope"])
            initial_documents.append(
                _source(
                    value["document_id"],
                    value["raw_text"],
                    observed_at=envelope.observed_at,
                    source_version=value["text_sha256_utf8"],
                    receipt_envelope=envelope,
                )
            )
        bindings = tuple(
            (document_id, row["obligation_id"], "support")
            for row in episode["initial_ledger"]
            for document_id in row["evidence_document_ids"]
        )
        state = new_lifecycle_state(
            sources=(claim, *initial_documents),
            bindings=bindings,
        )
        obligations = tuple(_public_obligation(value) for value in episode["obligations"])
        rows = sorted(
            (value for value in trajectories if value["episode"] == episode_id),
            key=lambda value: value["step"],
        )
        assert len(rows) == 4
        for row in rows:
            event_value = row["event"]
            documents = []
            for value in event_value.get("documents", []):
                envelope = LifecycleReceiptEnvelopeV1.model_validate(value["receipt_envelope"])
                documents.append(
                    _source(
                        value["id"],
                        value["text"],
                        observed_at=value["received_at"],
                        source_version=value["sha256"],
                        receipt_envelope=envelope,
                    )
                )
            event = _event(
                event_value["id"],
                event_value["text"],
                observed_at=event_value["received_at"],
                documents=tuple(documents),
                received=event_value["received"],
            )
            completion = completions[f"claim.base27.{episode_id}.{row['step']}"]
            prefix = row["source_prefix_sha256"]
            result = apply_document_lifecycle_shadow(
                _request(
                    state=state,
                    obligations=obligations,
                    event=event,
                    raw_output=completion["raw_generated_text"],
                    source_prefix_sha256=prefix,
                    receipt=_frozen_receipt(
                        completion,
                        prefix,
                        lifecycle_adapter_payload_sha256(state, obligations, event),
                    ),
                )
            )
            state = _next_state(result)
            assert _snapshot(state) == row["reference_snapshot"]
            assert _normalize_view(result, state) == row["reference_view"]
            assert _normalize_action(result["next_actions"]) == row["action"]
            assert sorted(value.source_id for value in state.sources) == row["reference_source_ids"]
            exact_steps += 1
        completed_workflows.add(episode_id)

    assert exact_steps == 24
    assert len(completed_workflows) == 6


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def test_route_is_registered_and_explicitly_non_authoritative() -> None:
    from casepath_api.app import app

    assert DOCUMENT_LIFECYCLE_ROUTE in {route.path for route in app.routes}
    obligations = (_obligation("O1"),)
    state = new_lifecycle_state(sources=())
    event = _event("F1", "No local effect.", observed_at="2026-05-02T08:00:00Z")
    raw = _empty_output()
    prefix = digest_text("parser-prefix")
    receipt = _receipt(
        raw,
        prefix,
        lifecycle_adapter_payload_sha256(state, obligations, event),
        producer_kind="deterministic_parser",
        finish_reason="complete",
    )
    result = apply_document_lifecycle_shadow(
        _request(
            state=state,
            obligations=obligations,
            event=event,
            raw_output=raw,
            source_prefix_sha256=prefix,
            receipt=receipt,
        )
    )
    assert result["mode"] == "shadow_non_authoritative"
    assert result["canonical_state_mutated"] is False
    assert result["producer_kind"] == "deterministic_parser"
    assert result["semantic_boundary"] == "attributable_exact_sources_do_not_certify_entailment"
