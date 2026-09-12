from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from casepath_api import native_inference_v1 as native_module
from casepath_api.native_inference_v1 import (
    OPENROUTER_ENDPOINT,
    OPENROUTER_HIGH_DETAIL_IMAGE_TOKEN_UPPER_BOUND,
    OPENROUTER_MINI_MODEL,
    MeteredNativeProvider,
    PreparedInference,
    ProviderConfig,
    TransportResponse,
    openrouter_http_once_transport,
    sha256_bytes,
)


def _provider(tmp_path: Path, *, call_cap: float = 0.05) -> MeteredNativeProvider:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["needs"],
        "properties": {"needs": {"type": "array"}},
    }
    schema_path = tmp_path / "actor.schema.json"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    return MeteredNativeProvider(
        ProviderConfig(
            output_schema_path=str(schema_path),
            working_directory=str(tmp_path),
            final_output_path=str(tmp_path / "final.json"),
            model=OPENROUTER_MINI_MODEL,
            reasoning_effort="low",
            transport_kind="openrouter",
            endpoint=OPENROUTER_ENDPOINT,
            max_input_tokens=32_768,
            max_output_tokens=3_072,
            maximum_call_cost_usd=call_cap,
        ),
        output_validator=lambda value: None,
    )


def _prepared(tmp_path: Path) -> tuple[PreparedInference, bytes]:
    raw = b"\x89PNG\r\n\x1a\nexact-native-pixels"
    image_path = tmp_path / "page.png"
    image_path.write_bytes(raw)
    receipt = {
        "image_id": "p0",
        "source_id": "source-1",
        "view_id": "source-1.page-1",
        "image_path": str(image_path),
        "sha256": sha256_bytes(raw),
        "size_bytes": len(raw),
        "media_type": "image/png",
        "raw_artifact_sha256": "a" * 64,
        "page_index": 0,
    }
    return (
        PreparedInference(
            messages=(
                {"role": "system", "content": "Inspect admitted sources."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": '{"observed_at":"2026-09-08T20:00:00+00:00"}'},
                        {
                            "type": "image",
                            "image_path": str(image_path),
                            "sha256": receipt["sha256"],
                            "image_id": "p0",
                        },
                    ],
                },
            ),
            input_identity="input-1",
            source_prefix_sha256="b" * 64,
            source_receipts=(),
            image_receipts=(receipt,),
            observed_at="2026-09-08T20:00:00+00:00",
        ),
        raw,
    )


def _response(*, content: str, cost: float) -> TransportResponse:
    envelope = {
        "id": "generation-test-1",
        "model": OPENROUTER_MINI_MODEL,
        "provider": "OpenAI",
        "choices": [
            {"finish_reason": "stop", "message": {"content": content}}
        ],
        "usage": {
            "prompt_tokens": 4000,
            "completion_tokens": 80,
            "total_tokens": 4080,
            "prompt_tokens_details": {"cached_tokens": 0},
            "completion_tokens_details": {"reasoning_tokens": 20},
            "cost": cost,
        },
    }
    return TransportResponse(
        returncode=0,
        stdout=json.dumps(envelope),
        stderr="",
        final_output=content,
        http_status=200,
    )


def test_openrouter_request_is_pinned_native_and_reserved_before_send(
    tmp_path: Path,
) -> None:
    provider = _provider(tmp_path)
    prepared, raw = _prepared(tmp_path)
    request = provider.build_request(prepared)

    assert request.argv == ()
    assert request.transport_kind == "openrouter"
    assert request.endpoint == OPENROUTER_ENDPOINT
    assert request.http_payload["model"] == OPENROUTER_MINI_MODEL
    assert request.http_payload["provider"] == {
        "only": ["openai"],
        "order": ["openai"],
        "allow_fallbacks": False,
        "require_parameters": True,
    }
    assert request.http_payload["reasoning"] == {"effort": "low"}
    assert "temperature" not in request.http_payload
    image = request.http_payload["messages"][1]["content"][1]
    assert image["image_url"]["detail"] == "high"
    assert image["image_url"]["url"] == (
        "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
    )
    assert request.image_token_upper_bound == (
        OPENROUTER_HIGH_DETAIL_IMAGE_TOKEN_UPPER_BOUND
    )
    assert 0 < request.estimated_input_tokens_upper_bound <= 32_768
    assert request.reserved_max_cost_usd == pytest.approx(0.0384)


def test_call_cap_must_cover_full_token_reserve(tmp_path: Path) -> None:
    provider = _provider(tmp_path, call_cap=0.03)
    prepared, _raw = _prepared(tmp_path)
    with pytest.raises(ValueError, match="cost cap cannot cover"):
        provider.build_request(prepared)


def test_known_overrun_is_retained_and_fails_qualification(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    prepared, _raw = _prepared(tmp_path)
    request = provider.build_request(prepared)
    content = '{"needs":[]}'
    receipt = provider._receipt(request, _response(content=content, cost=0.051), 0.1)

    assert receipt["qualified"] is False
    assert receipt["actual_cost_usd"] == pytest.approx(0.051)
    assert receipt["usage_complete"] is True
    assert receipt["trace"]["cost_known"] is True
    assert receipt["trace"]["cost_within_call_bound"] is False


def test_provider_receipt_keeps_actual_openrouter_usage(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    prepared, _raw = _prepared(tmp_path)
    request = provider.build_request(prepared)
    content = '{"needs":[]}'
    receipt = provider._receipt(request, _response(content=content, cost=0.0042), 0.2)

    assert receipt["qualified"] is True
    assert receipt["provider_identity"] == {
        "response_id": "generation-test-1",
        "model": OPENROUTER_MINI_MODEL,
        "provider": "OpenAI",
        "finish_reason": "stop",
    }
    assert receipt["usage"] == {
        "input_tokens": 4000,
        "cached_input_tokens": 0,
        "output_tokens": 80,
        "reasoning_output_tokens": 20,
        "total_tokens": 4080,
        "cost": 0.0042,
    }


def test_http_once_transport_sends_one_exact_payload_without_receipting_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _provider(tmp_path)
    prepared, _raw = _prepared(tmp_path)
    request = provider.build_request(prepared)
    content = '{"needs":[]}'
    wire = _response(content=content, cost=0.0042).stdout.encode("utf-8")
    seen = []

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit):
            return wire

    def fake_urlopen(outbound, *, timeout):
        seen.append((outbound, timeout))
        return Response()

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret-never-retained")
    monkeypatch.setattr(native_module, "urlopen", fake_urlopen)
    response = openrouter_http_once_transport(request)

    assert len(seen) == 1
    outbound, timeout = seen[0]
    assert timeout == request.timeout_seconds
    assert json.loads(outbound.data) == request.http_payload
    assert outbound.get_header("Authorization") == "Bearer test-secret-never-retained"
    assert "test-secret" not in repr(request)
    assert "test-secret" not in repr(response)
    assert response.http_status == 200
    assert response.final_output == content
