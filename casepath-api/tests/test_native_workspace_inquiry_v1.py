"""Mounted recorded-entry tests; these do not score model semantic accuracy."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from casepath_api.app import (
    app,
    claim_workspace_corpus,
    native_workspace_inquiry_service,
)
from casepath_api.native_workspace_inquiry_v1 import (
    EXPECTED_CLAIM_ID,
    NativeWorkspaceInquiryServiceV1,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures/native-inquiry-mara-r1"
TRACE = FIXTURE / "SELECTED_RECORDED_TRACE.json"
BASE = f"/api/claim-loops/v1/workspace/claims/{EXPECTED_CLAIM_ID}/native-inquiry/recorded"
MODE = {"X-CasePath-Native-Research-Mode": "recorded-replay-v1"}


def _header(key: str) -> dict[str, str]:
    return {**MODE, "X-CasePath-Idempotency-Key": key}


def _client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, trace: Path = TRACE) -> TestClient:
    monkeypatch.setenv("CASEPATH_NATIVE_RECORDED_TRACE_PATH", str(trace))
    monkeypatch.setenv("CASEPATH_NATIVE_INQUIRY_DB_PATH", str(tmp_path / "inquiry.sqlite3"))
    native_workspace_inquiry_service.cache_clear()
    return TestClient(app)


def _through_response(client: TestClient) -> tuple[dict[str, Any], str, str]:
    opened = client.post(BASE + "/open", headers=_header("entry-open-0001"))
    assert opened.status_code == 200, opened.text
    initial = opened.json()
    dispatched = client.post(
        BASE + "/dispatch",
        headers=_header("entry-dispatch-0001"),
        json={"expected_state_sha256": initial["state_sha256"]},
    )
    assert dispatched.status_code == 200, dispatched.text
    pending = dispatched.json()
    request_id = pending["recorded_request"]["request_id"]
    response_expected = pending["state_sha256"]
    response = client.post(
        BASE + "/response",
        headers=_header("entry-response-0001"),
        json={
            "request_id": request_id,
            "expected_state_sha256": response_expected,
        },
    )
    assert response.status_code == 200, response.text
    return response.json(), request_id, response_expected


def _copy_trace(tmp_path: Path, transform: Any) -> Path:
    package = tmp_path / "modified-trace"
    shutil.copytree(FIXTURE, package)
    path = package / "SELECTED_RECORDED_TRACE.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    transform(value)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    return path


def _file_receipt(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def test_mounted_recorded_entry_preserves_native_provenance_and_scoped_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _client(monkeypatch, tmp_path)
    after_response, _, _ = _through_response(client)
    correction = client.post(
        BASE + "/correction",
        headers=_header("entry-correction-0001"),
        json={
            "expected_state_sha256": after_response["state_sha256"],
            "expected_opaque_target_id": "a_9402ba9ea76185b5dd52",
        },
    )
    assert correction.status_code == 200, correction.text
    final = correction.json()
    assert final["stage"] == "correction_applied"
    assert final["canonical_facts"] == {}
    assert final["certified_readiness"] is None
    assert final["selected_trajectory"]["fresh_inference"] is False
    assert len(final["provider_call_receipts"]) == 5
    image_orders = [
        receipt.get("image_sha256_order") for receipt in final["provider_call_receipts"]
    ]
    assert image_orders == [
        [
            "653894c9f4bd01095b8d26cabbc593b24f26bfe4a08461d2e532484d5af9a757",
            "a3361e9931eded0ec4104410aaee16f10eee9f83dd0c8452a03cfe987ee29595",
        ],
        [
            "653894c9f4bd01095b8d26cabbc593b24f26bfe4a08461d2e532484d5af9a757",
            "a3361e9931eded0ec4104410aaee16f10eee9f83dd0c8452a03cfe987ee29595",
        ],
        [
            "653894c9f4bd01095b8d26cabbc593b24f26bfe4a08461d2e532484d5af9a757",
            "a3361e9931eded0ec4104410aaee16f10eee9f83dd0c8452a03cfe987ee29595",
            "b1446b5e96d8a74b57a883fba97f550ac990bc459af6bf87e62197f8f2b9d0d1",
        ],
        [
            "653894c9f4bd01095b8d26cabbc593b24f26bfe4a08461d2e532484d5af9a757",
            "a3361e9931eded0ec4104410aaee16f10eee9f83dd0c8452a03cfe987ee29595",
            "b1446b5e96d8a74b57a883fba97f550ac990bc459af6bf87e62197f8f2b9d0d1",
            "80d3f242fc38328ada322fe88af0c873b568a16e281b208f5d7d69f45fbcfb4a",
        ],
        [
            "653894c9f4bd01095b8d26cabbc593b24f26bfe4a08461d2e532484d5af9a757",
            "a3361e9931eded0ec4104410aaee16f10eee9f83dd0c8452a03cfe987ee29595",
            "b1446b5e96d8a74b57a883fba97f550ac990bc459af6bf87e62197f8f2b9d0d1",
            "80d3f242fc38328ada322fe88af0c873b568a16e281b208f5d7d69f45fbcfb4a",
        ],
    ]
    assertions = list(final["provisional_source_assertions"].values())
    old_completion = next(
        row for row in assertions
        if row["reported_text"] == "Reparaturabschluss: 11.05.2025 um 14:40.\n"
    )
    old_window = next(
        row for row in assertions
        if row["reported_text"].startswith("Protokolliertes Wasseraustrittsfenster: 10.05")
    )
    reply_completion = next(
        row for row in assertions
        if row["reported_text"] == "Reparaturabschluss: 15.05.2025 um 16:20.\n"
    )
    assert old_completion["status"] == "superseded_by_source_correction"
    assert old_window["status"] == "active"
    assert reply_completion["status"] == "active"
    n4 = next(row for row in final["latest_model_proposal"]["needs"] if row["need_id"] == "n4")
    assert n4["state"] == "received"
    assert "15.05.2025 um 16:20" in n4["answer"]
    assert all(action["need_id"] != "n4" for action in final["suggested_actions"])
    # Restart reads the identical journal state.
    native_workspace_inquiry_service.cache_clear()
    restarted = client.get(BASE, headers=MODE)
    assert restarted.status_code == 200
    assert restarted.json()["state_sha256"] == final["state_sha256"]


def test_route_is_hidden_without_explicit_research_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _client(monkeypatch, tmp_path)
    assert client.get(BASE).status_code == 404


def test_public_corpus_fixture_substitution_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _client(monkeypatch, tmp_path)
    wrong = BASE.replace(EXPECTED_CLAIM_ID, "clm_0000000000000000")
    response = client.post(wrong + "/open", headers=_header("wrong-claim-0001"))
    assert response.status_code == 400
    assert "outside the recorded development trace" in response.text


def test_missing_native_image_fails_before_any_saved_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def alter(value: dict[str, Any]) -> None:
        source = next(row for row in value["sources"] if row["source_key"] == "initial_report")
        source["rendered"]["path"] = str(tmp_path / "missing.png")

    trace = _copy_trace(tmp_path, alter)
    client = _client(monkeypatch, tmp_path, trace)
    response = client.post(BASE + "/open", headers=_header("missing-image-0001"))
    assert response.status_code == 503
    assert "unavailable" in response.text


def test_changed_source_prefix_is_rejected_even_with_updated_file_receipt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    original = json.loads(
        (FIXTURE / "calls/after-response-input.json").read_text()
    )
    document = json.loads(original["messages"][1]["content"][0]["text"])
    document["text_views"][1]["units"][0]["text"] = "Geänderter Eingang\n\n"
    original["messages"][1]["content"][0]["text"] = json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    changed = tmp_path / "changed-input.json"
    changed.write_text(json.dumps(original, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    def alter(value: dict[str, Any]) -> None:
        call = next(row for row in value["calls"] if row["call_id"] == "after_response")
        call["input"] = _file_receipt(changed)
        call["messages_sha256"] = hashlib.sha256(
            json.dumps(
                original["messages"], ensure_ascii=False, sort_keys=True,
                separators=(",", ":"), allow_nan=False,
            ).encode()
        ).hexdigest()

    client = _client(monkeypatch, tmp_path, _copy_trace(tmp_path, alter))
    opened = client.post(BASE + "/open", headers=_header("prefix-open-0001")).json()
    pending = client.post(
        BASE + "/dispatch",
        headers=_header("prefix-dispatch-0001"),
        json={"expected_state_sha256": opened["state_sha256"]},
    ).json()
    response = client.post(
        BASE + "/response",
        headers=_header("prefix-response-0001"),
        json={
            "expected_state_sha256": pending["state_sha256"],
            "request_id": pending["recorded_request"]["request_id"],
        },
    )
    assert response.status_code == 400
    assert "message projections differ" in response.text


def test_stale_model_prior_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    original = json.loads(
        (FIXTURE / "calls/after-response-input.json").read_text()
    )
    document = json.loads(original["messages"][1]["content"][0]["text"])
    document["prior_self"][0]["description"] += " stale"
    original["messages"][1]["content"][0]["text"] = json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    changed = tmp_path / "stale-prior-input.json"
    changed.write_text(json.dumps(original, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    def alter(value: dict[str, Any]) -> None:
        call = next(row for row in value["calls"] if row["call_id"] == "after_response")
        call["input"] = _file_receipt(changed)
        call["messages_sha256"] = hashlib.sha256(
            json.dumps(
                original["messages"], ensure_ascii=False, sort_keys=True,
                separators=(",", ":"), allow_nan=False,
            ).encode()
        ).hexdigest()

    client = _client(monkeypatch, tmp_path, _copy_trace(tmp_path, alter))
    opened = client.post(BASE + "/open", headers=_header("prior-open-0001")).json()
    pending = client.post(
        BASE + "/dispatch",
        headers=_header("prior-dispatch-0001"),
        json={"expected_state_sha256": opened["state_sha256"]},
    ).json()
    response = client.post(
        BASE + "/response",
        headers=_header("prior-response-0001"),
        json={
            "expected_state_sha256": pending["state_sha256"],
            "request_id": pending["recorded_request"]["request_id"],
        },
    )
    assert response.status_code == 400
    assert "own prior differs" in response.text


def test_duplicate_dispatch_is_idempotent_only_for_same_transport_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _client(monkeypatch, tmp_path)
    opened = client.post(BASE + "/open", headers=_header("dupe-open-0001")).json()
    body = {"expected_state_sha256": opened["state_sha256"]}
    first = client.post(BASE + "/dispatch", headers=_header("dupe-dispatch-0001"), json=body)
    assert first.status_code == 200
    same = client.post(BASE + "/dispatch", headers=_header("dupe-dispatch-0001"), json=body)
    assert same.status_code == 200 and same.json()["replayed"] is True
    other = client.post(BASE + "/dispatch", headers=_header("dupe-dispatch-0002"), json=body)
    assert other.status_code == 409
    assert other.json()["detail"] == "recorded request is already dispatched"


def test_request_and_correction_target_divergence_are_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _client(monkeypatch, tmp_path)
    opened = client.post(BASE + "/open", headers=_header("diverge-open-0001")).json()
    pending = client.post(
        BASE + "/dispatch",
        headers=_header("diverge-dispatch-0001"),
        json={"expected_state_sha256": opened["state_sha256"]},
    ).json()
    wrong_request = "request." + "0" * 64
    wrong = client.post(
        BASE + "/response",
        headers=_header("diverge-response-bad"),
        json={"expected_state_sha256": pending["state_sha256"], "request_id": wrong_request},
    )
    assert wrong.status_code == 400
    response = client.post(
        BASE + "/response",
        headers=_header("diverge-response-good"),
        json={
            "expected_state_sha256": pending["state_sha256"],
            "request_id": pending["recorded_request"]["request_id"],
        },
    )
    assert response.status_code == 200, response.text
    after_response = response.json()
    wrong_target = client.post(
        BASE + "/correction",
        headers=_header("diverge-correction-0001"),
        json={
            "expected_state_sha256": after_response["state_sha256"],
            "expected_opaque_target_id": "a_00000000000000000000",
        },
    )
    assert wrong_target.status_code == 409
    assert "differs from model proposal" in wrong_target.text


def test_stale_state_cannot_advance_response(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _client(monkeypatch, tmp_path)
    opened = client.post(BASE + "/open", headers=_header("stale-open-0001")).json()
    pending = client.post(
        BASE + "/dispatch",
        headers=_header("stale-dispatch-0001"),
        json={"expected_state_sha256": opened["state_sha256"]},
    ).json()
    response = client.post(
        BASE + "/response",
        headers=_header("stale-response-0001"),
        json={
            "expected_state_sha256": opened["state_sha256"],
            "request_id": pending["recorded_request"]["request_id"],
        },
    )
    assert response.status_code == 409


def test_same_key_resumes_after_response_commit_before_provider_receipt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    service = NativeWorkspaceInquiryServiceV1(
        corpus=claim_workspace_corpus,
        database=tmp_path / "resume-response.sqlite3",
        trace_manifest=TRACE,
    )
    opened = service.open(EXPECTED_CLAIM_ID, idempotency_key="resume-open-0001")
    pending = service.dispatch(
        EXPECTED_CLAIM_ID,
        expected_state_sha256=opened["state_sha256"],
        idempotency_key="resume-dispatch-0001",
    )
    original = service._append_custom
    failed = False

    def fail_once(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal failed
        if kwargs.get("event_type") == "NATIVE_UPDATE_REPLAY_RECORDED" and not failed:
            failed = True
            raise RuntimeError("injected interruption")
        return original(*args, **kwargs)

    monkeypatch.setattr(service, "_append_custom", fail_once)
    with pytest.raises(RuntimeError, match="injected interruption"):
        service.admit_recorded_response(
            EXPECTED_CLAIM_ID,
            request_id=pending["recorded_request"]["request_id"],
            expected_state_sha256=pending["state_sha256"],
            idempotency_key="resume-response-0001",
        )
    resumed = service.admit_recorded_response(
        EXPECTED_CLAIM_ID,
        request_id=pending["recorded_request"]["request_id"],
        expected_state_sha256=pending["state_sha256"],
        idempotency_key="resume-response-0001",
    )
    assert resumed["stage"] == "response_observed"
    assert resumed["replayed"] is True
    assert resumed["response_count"] == 1


def test_same_key_resumes_after_correction_commit_before_provider_receipt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    service = NativeWorkspaceInquiryServiceV1(
        corpus=claim_workspace_corpus,
        database=tmp_path / "resume-correction.sqlite3",
        trace_manifest=TRACE,
    )
    opened = service.open(EXPECTED_CLAIM_ID, idempotency_key="resume2-open-0001")
    pending = service.dispatch(
        EXPECTED_CLAIM_ID,
        expected_state_sha256=opened["state_sha256"],
        idempotency_key="resume2-dispatch-0001",
    )
    observed = service.admit_recorded_response(
        EXPECTED_CLAIM_ID,
        request_id=pending["recorded_request"]["request_id"],
        expected_state_sha256=pending["state_sha256"],
        idempotency_key="resume2-response-0001",
    )
    original = service._append_custom
    failed = False

    def fail_once(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal failed
        if kwargs.get("event_type") == "NATIVE_UPDATE_REPLAY_RECORDED" and not failed:
            failed = True
            raise RuntimeError("injected interruption")
        return original(*args, **kwargs)

    monkeypatch.setattr(service, "_append_custom", fail_once)
    with pytest.raises(RuntimeError, match="injected interruption"):
        service.admit_recorded_correction(
            EXPECTED_CLAIM_ID,
            expected_state_sha256=observed["state_sha256"],
            expected_opaque_target_id="a_9402ba9ea76185b5dd52",
            idempotency_key="resume2-correction-0001",
        )
    resumed = service.admit_recorded_correction(
        EXPECTED_CLAIM_ID,
        expected_state_sha256=observed["state_sha256"],
        expected_opaque_target_id="a_9402ba9ea76185b5dd52",
        idempotency_key="resume2-correction-0001",
    )
    assert resumed["stage"] == "correction_applied"
    assert resumed["replayed"] is True
    assert resumed["correction_count"] == 1


def test_manifest_relative_fixture_runs_from_an_isolated_copy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manifest = json.loads(TRACE.read_text(encoding="utf-8"))
    assert manifest["package"]["coordinator_dependency"] is False
    assert ".discovery-loop" not in TRACE.read_text(encoding="utf-8")
    receipts = [manifest["trajectory_policy"]]
    for row in manifest["sources"]:
        receipts.extend(value for key in ("raw", "rendered") if (value := row.get(key)))
    for row in manifest["calls"]:
        receipts.extend(
            value
            for key in ("input", "source_input", "output", "instruction", "stdin")
            if (value := row.get(key))
        )
    assert receipts
    assert all(not Path(receipt["path"]).is_absolute() for receipt in receipts)

    copied = tmp_path / "portable-trace"
    shutil.copytree(FIXTURE, copied)
    original_read_bytes = Path.read_bytes
    original_read_text = Path.read_text

    def guarded_read_bytes(path: Path) -> bytes:
        if ".discovery-loop" in str(path):
            raise AssertionError("coordinator artifact read")
        return original_read_bytes(path)

    def guarded_read_text(
        path: Path, encoding: str | None = None, errors: str | None = None
    ) -> str:
        if ".discovery-loop" in str(path):
            raise AssertionError("coordinator artifact read")
        return original_read_text(path, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    service = NativeWorkspaceInquiryServiceV1(
        corpus=claim_workspace_corpus,
        database=tmp_path / "portable.sqlite3",
        trace_manifest=copied / "SELECTED_RECORDED_TRACE.json",
    )
    opened = service.open(EXPECTED_CLAIM_ID, idempotency_key="portable-open-0001")
    pending = service.dispatch(
        EXPECTED_CLAIM_ID,
        expected_state_sha256=opened["state_sha256"],
        idempotency_key="portable-dispatch-0001",
    )
    observed = service.admit_recorded_response(
        EXPECTED_CLAIM_ID,
        request_id=pending["recorded_request"]["request_id"],
        expected_state_sha256=pending["state_sha256"],
        idempotency_key="portable-response-0001",
    )
    final = service.admit_recorded_correction(
        EXPECTED_CLAIM_ID,
        expected_state_sha256=observed["state_sha256"],
        expected_opaque_target_id="a_9402ba9ea76185b5dd52",
        idempotency_key="portable-correction-0001",
    )
    assert final["stage"] == "correction_applied"
    assert final["canonical_facts"] == {}
    assert final["certified_readiness"] is None
