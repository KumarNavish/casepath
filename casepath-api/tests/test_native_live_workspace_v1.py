from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import fitz
import pytest
from fastapi.testclient import TestClient

from casepath_api import app as app_module
from casepath_api.native_inference_v1 import (
    ProviderConfig,
    SourcePrefixAssembler,
    TransportRequest,
    TransportResponse,
    sha256_bytes,
)
from casepath_api.native_live_workspace_v1 import (
    LIVE_RESEARCH_MODE,
    LIVE_RESEARCH_MODE_HEADER,
    NativeLiveWorkspaceConflict,
    NativeLiveWorkspaceServiceV1,
    render_claim_sources,
)
from casepath_api.workspace_corpus import PublicCorpus, default_public_corpus_root


MARA_CLAIM_ID = "clm_e262801f9368bc12"
OBSERVED_AT = "2026-09-06T09:15:00+00:00"
IDEMPOTENCY_KEY = "native.live.mara.0001"


def _actor_output(*, warrant_ref: str = "t0") -> dict[str, Any]:
    return {
        "needs": [
            {
                "need_id": "n0",
                "description": "Den wiederkehrenden Wasseraustritt weiter abklären.",
                "answer": None,
                "warrant_refs": [warrant_ref],
                "evidence": [{"ref": "p0", "role": "context"}],
                "state": "missing",
                "until": None,
            }
        ]
    }


def _jsonl_response(output: dict[str, Any]) -> TransportResponse:
    final = json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    events = [
        {"type": "thread.started", "thread_id": "test-thread"},
        {
            "type": "item.completed",
            "item": {"type": "agent_message", "text": final},
        },
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 321,
                "cached_input_tokens": 0,
                "output_tokens": 55,
                "reasoning_output_tokens": 34,
            },
        },
    ]
    return TransportResponse(
        returncode=0,
        stdout="".join(json.dumps(event) + "\n" for event in events),
        stderr="",
        final_output=final,
    )


@dataclass
class CapturingTransport:
    output: dict[str, Any]
    requests: list[TransportRequest]

    def __call__(self, request: TransportRequest) -> TransportResponse:
        self.requests.append(request)
        return _jsonl_response(self.output)


def _headers(key: str = IDEMPOTENCY_KEY) -> dict[str, str]:
    return {
        LIVE_RESEARCH_MODE_HEADER: LIVE_RESEARCH_MODE,
        "X-CasePath-Idempotency-Key": key,
    }


def _configure_app_service(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    transport: CapturingTransport,
) -> NativeLiveWorkspaceServiceV1:
    monkeypatch.setenv("CASEPATH_NATIVE_LIVE_ENABLED", "1")
    monkeypatch.setenv("CASEPATH_NATIVE_LIVE_ROOT", str(tmp_path / "native-live"))
    monkeypatch.delenv("CASEPATH_NATIVE_LIVE_ENABLE_CODEX_TRANSPORT", raising=False)
    app_module.native_live_workspace_service.cache_clear()
    service = app_module.native_live_workspace_service()
    service.transport = transport
    service.clock = lambda: OBSERVED_AT
    return service


def test_live_route_hands_current_public_bytes_to_native_transport_and_replays(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transport = CapturingTransport(_actor_output(), [])
    _configure_app_service(monkeypatch, tmp_path, transport)
    route = (
        f"/api/claim-loops/v1/workspace/claims/{MARA_CLAIM_ID}"
        "/native-inquiry/live"
    )
    try:
        with TestClient(app_module.app) as client:
            hidden = client.post(route, headers={"X-CasePath-Idempotency-Key": IDEMPOTENCY_KEY})
            assert hidden.status_code == 404
            response = client.post(route, headers=_headers())
            assert response.status_code == 200, response.text
            result = response.json()

            assert len(transport.requests) == 1
            request = transport.requests[0]
            assert request.argv[0:3] == ("codex", "exec", "--json")
            assert request.argv[request.argv.index("--model") + 1] == "gpt-5.6-sol"
            assert "model_reasoning_effort=\"xhigh\"" in request.argv
            assert request.argv.count("--image") == 1
            assert request.input_identity == result["input_identity"]

            source_json = request.stdin.split("\n\nPhysical image view", 1)[0]
            source_document = json.loads(source_json)
            assert source_document["observed_at"] == OBSERVED_AT
            assert source_document["prior_self"] == []
            assert [view["source_id"] for view in source_document["text_views"]] == [
                "com_f182ccb67285f004"
            ]
            assert [view["source_id"] for view in source_document["image_views"]] == [
                "doc_336f88b3a077b170"
            ]
            corpus = PublicCorpus(default_public_corpus_root())
            message_raw, _ = corpus.artifact(
                MARA_CLAIM_ID, "com_f182ccb67285f004"
            )
            actual_text = "".join(
                unit["text"]
                for view in source_document["text_views"]
                for unit in view["units"]
            )
            assert actual_text == message_raw.decode("utf-8")

            assert result["qualified"] is True
            assert result["status"] == "completed_qualified"
            assert result["observed_at"] == OBSERVED_AT
            assert result["replayed"] is False
            assert [
                row["admission_receipt"]["source_order_zero_based"]
                for row in result["source_receipts"]
            ] == [0, 1]
            image_receipt = result["native_image_receipts"][0]
            image_raw, image_row = corpus.artifact(
                MARA_CLAIM_ID, "doc_336f88b3a077b170"
            )
            assert image_receipt["image_id"] == "p0"
            assert image_receipt["sha256"] == image_row["sha256"]
            assert Path(image_receipt["image_path"]).read_bytes() == image_raw
            assert result["transport_receipt"]["qualified"] is True
            assert (
                result["transport_receipt"]["source_pointer_semantics_validated"]
                is True
            )
            assert result["cost_receipt"]["usage"]["input_tokens"] == 321
            proposal = result["provisional_proposal"]
            assert proposal["needs"][0]["warrants"][0]["ref"] == "t0"
            assert proposal["needs"][0]["evidence"][0]["ref"] == "p0"
            assert proposal["canonical_fact_effect"] is None
            assert proposal["readiness_effect"] is None
            assert result["canonical_facts"] == {}
            assert result["certified_readiness"] is None
            assert result["customer_send"] is False

            replay = client.post(route, headers=_headers())
            assert replay.status_code == 200, replay.text
            assert replay.json()["replayed"] is True
            assert replay.json()["terminal_event_sha256"] == result[
                "terminal_event_sha256"
            ]
            assert len(transport.requests) == 1

            next_cycle = client.post(
                route, headers=_headers("native.live.mara.0002")
            )
            assert next_cycle.status_code == 200, next_cycle.text
            assert len(transport.requests) == 2
            next_source_json = transport.requests[1].stdin.split(
                "\n\nPhysical image view", 1
            )[0]
            assert json.loads(next_source_json)["prior_self"] == _actor_output()[
                "needs"
            ]

        app_module.native_live_workspace_service.cache_clear()
        restarted = app_module.native_live_workspace_service()
        assert restarted.transport is None
        with TestClient(app_module.app) as client:
            replay_after_restart = client.post(route, headers=_headers())
            assert replay_after_restart.status_code == 200
            assert replay_after_restart.json()["replayed"] is True
            state = client.get(route, headers={
                LIVE_RESEARCH_MODE_HEADER: LIVE_RESEARCH_MODE
            })
            assert state.status_code == 200
            assert state.json()["completed_cycle_count"] == 2
            assert state.json()["unresolved_cycle_keys"] == []
    finally:
        app_module.native_live_workspace_service.cache_clear()


def _direct_service(
    tmp_path: Path,
    *,
    transport,
) -> NativeLiveWorkspaceServiceV1:
    runtime_root = tmp_path / "runtime"
    return NativeLiveWorkspaceServiceV1(
        corpus=PublicCorpus(default_public_corpus_root()),
        database=tmp_path / "journal.sqlite3",
        runtime_root=runtime_root,
        provider_config=ProviderConfig(
            output_schema_path=str(runtime_root / "schema.json"),
            working_directory=str(Path(__file__).parents[2]),
            final_output_path=str(runtime_root / "unbound.json"),
        ),
        transport=transport,
        clock=lambda: OBSERVED_AT,
    )


def test_unresolved_intent_blocks_same_key_and_new_key_relaunches(tmp_path: Path) -> None:
    calls: list[TransportRequest] = []

    def interrupted(request: TransportRequest) -> TransportResponse:
        calls.append(request)
        raise KeyboardInterrupt("simulated process loss after durable intent")

    service = _direct_service(tmp_path, transport=interrupted)
    with pytest.raises(KeyboardInterrupt, match="simulated process loss"):
        service.cycle(MARA_CLAIM_ID, idempotency_key="native.live.interrupted.0001")
    assert len(calls) == 1

    replacement = CapturingTransport(_actor_output(), [])
    restarted = _direct_service(tmp_path, transport=replacement)
    with pytest.raises(NativeLiveWorkspaceConflict, match="ambiguous retry"):
        restarted.cycle(
            MARA_CLAIM_ID, idempotency_key="native.live.interrupted.0001"
        )
    with pytest.raises(NativeLiveWorkspaceConflict, match="unresolved inference intent"):
        restarted.cycle(MARA_CLAIM_ID, idempotency_key="native.live.different.0002")
    assert replacement.requests == []
    state = restarted.state(MARA_CLAIM_ID)
    assert state["unresolved_cycle_keys"] == ["native.live.interrupted.0001"]
    assert state["completed_cycle_count"] == 0


def test_unknown_public_pointer_is_durably_unqualified(tmp_path: Path) -> None:
    transport = CapturingTransport(_actor_output(warrant_ref="t999999"), [])
    service = _direct_service(tmp_path, transport=transport)
    result = service.cycle(
        MARA_CLAIM_ID, idempotency_key="native.live.bad-pointer.0001"
    )
    assert result["qualified"] is False
    assert result["status"] == "completed_unqualified"
    assert result["provisional_proposal"] is None
    assert result["decoder_error"]["type"] == "NativeLiveWorkspaceError"
    assert "outside the live source prefix" in result["decoder_error"]["message"]
    assert result["transport_receipt"]["source_pointer_semantics_validated"] is False
    assert result["canonical_facts"] == {}
    replay = service.cycle(
        MARA_CLAIM_ID, idempotency_key="native.live.bad-pointer.0001"
    )
    assert replay["replayed"] is True
    assert len(transport.requests) == 1


class _ControlledPdfCorpus:
    def __init__(self, raw: bytes) -> None:
        sha = sha256_bytes(raw)
        self.raw = raw
        self.row = {
            "artifact_id": "controlled-mara-report",
            "role": "attachment",
            "file_name": "initial-report.pdf",
            "media_type": "application/pdf",
            "path": "controlled/initial-report.pdf",
            "sha256": sha,
            "size_bytes": len(raw),
        }
        self.identity = {"manifest_sha256": "f" * 64}

    def binding(self, claim_id: str) -> dict[str, Any]:
        assert claim_id == MARA_CLAIM_ID
        return {
            "claim_id": claim_id,
            "received_at": "2025-05-24T13:00:00+02:00",
            "binding_sha256": "e" * 64,
            "observable_artifacts": [self.row],
        }

    def artifact(self, claim_id: str, artifact_id: str):
        assert claim_id == MARA_CLAIM_ID
        assert artifact_id == self.row["artifact_id"]
        return self.raw, dict(self.row)


def test_controlled_pdf_renders_every_native_page_from_admitted_bytes(
    tmp_path: Path,
) -> None:
    fixture = (
        Path(__file__).parent
        / "fixtures"
        / "native-inquiry-mara-r1"
        / "source"
        / "initial-report.pdf"
    )
    raw = fixture.read_bytes()
    with fitz.open(stream=raw, filetype="pdf") as document:
        expected_pages = document.page_count
    corpus = _ControlledPdfCorpus(raw)
    sources = render_claim_sources(
        corpus, MARA_CLAIM_ID, observed_at=OBSERVED_AT
    )
    assert len(sources) == 1
    source = sources[0]
    assert len(source.native_views) == expected_pages
    assert [view.page_index for view in source.native_views] == list(
        range(expected_pages)
    )
    assert all(view.image_bytes.startswith(b"\x89PNG\r\n\x1a\n") for view in source.native_views)
    assert source.admission_receipt["renderer_receipt"]["page_count"] == expected_pages
    assert source.admission_receipt["renderer_receipt"]["native_page_count"] == expected_pages
    prepared = SourcePrefixAssembler(tmp_path / "pages").assemble(
        sources=sources,
        observed_at=OBSERVED_AT,
        prior_self=[],
        system_prompt="test-only system prompt",
    )
    assert len(prepared.image_receipts) == expected_pages
    assert [row["image_id"] for row in prepared.image_receipts] == [
        f"p{index}" for index in range(expected_pages)
    ]


def _historical_image_stream(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    source_kind: str,
    image_format: str = "PNG",
):
    """Persist historical decoder provenance using only the injected test transport."""
    import base64
    from io import BytesIO

    from PIL import Image
    from casepath_api import native_live_workspace_v1 as native_module

    buffer = BytesIO()
    Image.new("RGB", (12, 7), (20, 80, 140)).save(buffer, format=image_format)
    raw = buffer.getvalue()
    source = {
        "source_id": "decoder_upgrade_image",
        "file_name": "decoder-upgrade." + image_format.lower(),
        "media_type": "image/" + ("jpeg" if image_format == "JPEG" else "png"),
        "raw_base64": base64.b64encode(raw).decode("ascii"),
        "sha256": sha256_bytes(raw),
    }
    request = {"channel_id": "c1", "need_ids": ["n0"], "purpose": "Read returned image."}
    output = {**_actor_output(), "requests": [request] if source_kind == "admission" else []}
    transport = CapturingTransport(output, [])
    service = _configure_app_service(monkeypatch, tmp_path, transport)
    config = {
        "system_prompt": "Read only the supplied test sources.",
        "refinement_prompt": "Review the supplied proposal.",
        "available_channels": [{"channel_id": "c1", "description": "Test source export."}],
        "remaining_export_attempts": 1,
    }
    if source_kind == "knowledge":
        config["knowledge_sources"] = [{"knowledge_kind": "policy", "source": source}]
    # The regression is in recorded provenance, not decoding. The pinned decoder
    # reads the fixture; only its historical version label is simulated here.
    with monkeypatch.context() as historical:
        historical.setattr(Image, "__version__", "11.3.0")
        service.configure_export(
            MARA_CLAIM_ID, idempotency_key="decoder.config", config=config
        )
        first = service.cycle(MARA_CLAIM_ID, idempotency_key="decoder.first")
        assert first["qualified"] is True
        if source_kind == "admission":
            service.admit_source(
                MARA_CLAIM_ID,
                idempotency_key="decoder.admission",
                admission={
                    "kind": "export",
                    "origin_cycle_id": first["cycle_id"],
                    "request_index": 0,
                    "request": request,
                    "status": "exported",
                    "observed_at": "2026-09-06T09:16:00+00:00",
                    "source": source,
                },
            )
    journal = service._journal()
    try:
        events = journal.events(service._stream_id(MARA_CLAIM_ID))
    finally:
        journal.close()
    event_type = (
        native_module.EXPORT_CONFIG_EVENT
        if source_kind == "knowledge"
        else native_module.SOURCE_ADMISSION_EVENT
    )
    payload = next(event["payload"] for event in events if event["event_type"] == event_type)
    receipt = (
        payload["knowledge_renderer_receipts"][0]
        if source_kind == "knowledge"
        else payload["renderer_receipt"]
    )
    assert receipt["decoder_version"] == "11.3.0"
    return service, transport, events, source, raw, first


@pytest.mark.parametrize("source_kind", ["knowledge", "admission"])
@pytest.mark.parametrize("image_format", ["JPEG", "PNG"])
def test_pillow_upgrade_resumes_journaled_images_without_rewriting_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_kind: str,
    image_format: str,
) -> None:
    from PIL import Image

    service, transport, before, source, raw, first = _historical_image_stream(
        tmp_path, monkeypatch, source_kind=source_kind, image_format=image_format
    )
    assert Image.__version__ == "13.0.0"
    restarted = NativeLiveWorkspaceServiceV1(
        corpus=service.corpus,
        database=service.database,
        runtime_root=service.runtime_root,
        provider_config=service.provider_config,
        transport=transport,
        clock=lambda: "2026-09-06T09:17:00+00:00",
    )
    replay = restarted.cycle(MARA_CLAIM_ID, idempotency_key="decoder.first")
    assert replay["replayed"] is True
    assert replay["terminal_event_sha256"] == first["terminal_event_sha256"]
    assert len(transport.requests) == 1

    transport.output = {**_actor_output(), "requests": []}
    resumed = restarted.cycle(MARA_CLAIM_ID, idempotency_key="decoder.resumed")
    assert resumed["qualified"] is True
    assert len(transport.requests) == 2
    receipt = next(
        row for row in resumed["source_receipts"] if row["artifact_id"] == source["source_id"]
    )
    assert receipt["admission_receipt"]["renderer_receipt"]["decoder_version"] == "13.0.0"
    native = next(
        row for row in resumed["native_image_receipts"] if row["source_id"] == source["source_id"]
    )
    assert native["sha256"] == source["sha256"]
    assert Path(native["image_path"]).read_bytes() == raw
    journal = restarted._journal()
    try:
        after = journal.events(restarted._stream_id(MARA_CLAIM_ID))
    finally:
        journal.close()
    assert after[:len(before)] == before
    app_module.native_live_workspace_service.cache_clear()


@pytest.mark.parametrize("source_kind", ["knowledge", "admission"])
@pytest.mark.parametrize(
    "drift",
    ["unknown_decoder", "renderer", "dimensions", "format", "native_bytes", "extra_field", "raw_hash", "downgrade"],
)
def test_pillow_upgrade_still_rejects_image_evidence_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_kind: str,
    drift: str,
) -> None:
    from copy import deepcopy

    from PIL import Image
    from casepath_api import native_live_workspace_v1 as native_module

    service, transport, before, _, _, _ = _historical_image_stream(
        tmp_path, monkeypatch, source_kind=source_kind
    )
    events = deepcopy(before)
    event_type = (
        native_module.EXPORT_CONFIG_EVENT
        if source_kind == "knowledge"
        else native_module.SOURCE_ADMISSION_EVENT
    )
    payload = next(event["payload"] for event in events if event["event_type"] == event_type)
    if source_kind == "knowledge":
        receipt = payload["knowledge_renderer_receipts"][0]
        source = payload["config"]["knowledge_sources"][0]["source"]
        reconstruct = service._knowledge_sources
    else:
        receipt = payload["renderer_receipt"]
        source = payload["source"]
        reconstruct = service._returned_sources
    changes = {
        "unknown_decoder": ("decoder_version", "12.3.0"),
        "renderer": ("renderer", "unrecognized-renderer"),
        "dimensions": ("dimensions", [99, 7]),
        "format": ("decoded_format", "JPEG"),
        "native_bytes": ("native_bytes_unchanged", False),
        "extra_field": ("unreviewed_transform", True),
    }
    if drift == "raw_hash":
        source["sha256"] = "0" * 64
    elif drift == "downgrade":
        receipt["decoder_version"] = "13.0.0"
        monkeypatch.setattr(Image, "__version__", "11.3.0")
    else:
        key, value = changes[drift]
        receipt[key] = value
    with pytest.raises(
        native_module.NativeLiveWorkspaceError,
        match="byte hash mismatch" if drift == "raw_hash" else "renderer receipt drifted",
    ):
        reconstruct(
            MARA_CLAIM_ID, events, observed_at="2026-09-06T09:17:00+00:00"
        )
    journal = service._journal()
    try:
        assert journal.events(service._stream_id(MARA_CLAIM_ID)) == before
    finally:
        journal.close()
    assert len(transport.requests) == 1
    app_module.native_live_workspace_service.cache_clear()
