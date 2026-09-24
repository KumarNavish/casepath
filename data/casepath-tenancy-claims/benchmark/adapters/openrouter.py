"""Exact-once OpenRouter/Nemotron adapter for the matched-budget experiment."""

from __future__ import annotations

import json
import math
import os
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, cast

from baselines.base import ModelCallResult, StageRequest
from baselines.conditions import CONDITIONS
from baselines.prompting import FrozenPromptBundle
from contracts.schema import ProviderCallReceipt
from manifests.digests import digest_json

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
NEMOTRON_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"
EXPECTED_PROVIDER = "Together"
MAX_RESPONSE_BYTES = 1_000_000


class ProviderResponseError(RuntimeError):
    """A bounded provider failure that never includes response prose or credentials."""


class JsonTransport(Protocol):
    def post_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]: ...


class UrllibTransport:
    def post_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers=dict(headers),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            raise ProviderResponseError("provider request failed") from exc
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ProviderResponseError("provider response exceeded the byte limit")
        try:
            parsed = json.loads(
                raw,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_nonfinite,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise ProviderResponseError("provider returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise ProviderResponseError("provider response must be a JSON object")
        return cast(dict[str, Any], parsed)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError("duplicate JSON key")
        output[key] = value
    return output


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"non-finite number {value!r}")


def _required_string(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ProviderResponseError(f"provider response is missing {field}")
    return value


def _required_nonnegative_int(payload: Mapping[str, Any], field: str) -> int:
    value = payload.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ProviderResponseError(f"provider usage is missing {field}")
    return value


@dataclass(frozen=True)
class OpenRouterNemotronAdapter:
    api_key: str
    prompt_bundle: FrozenPromptBundle
    transport: JsonTransport

    @classmethod
    def from_environment(cls) -> OpenRouterNemotronAdapter:
        api_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not configured")
        return cls(
            api_key=api_key,
            prompt_bundle=FrozenPromptBundle(),
            transport=UrllibTransport(),
        )

    def invoke(self, request: StageRequest) -> ModelCallResult:
        if request.budget.model != NEMOTRON_MODEL:
            raise ValueError(f"experiment requires model {NEMOTRON_MODEL}")
        if request.budget.max_retries != 0:
            raise ValueError("the preregistered experiment uses exact-once calls")
        rendered = self.prompt_bundle.render(request)
        definition = CONDITIONS.get(request.condition_id)  # type: ignore[arg-type]
        if definition is None:
            raise ValueError("legacy adapter received a non-legacy condition")
        stage_count = len(definition.stages)
        max_tokens = request.budget.max_output_tokens // stage_count
        if max_tokens < 1:
            raise ValueError("output-token budget is too small for all condition stages")
        request_id = f"evalcall_{uuid.uuid4().hex}"
        payload: dict[str, Any] = {
            "model": request.budget.model,
            "messages": rendered.messages,
            "temperature": request.budget.temperature,
            "max_tokens": max_tokens,
            "provider": {
                "only": ["together"],
                "allow_fallbacks": False,
                "require_parameters": True,
                "data_collection": "deny",
            },
        }
        if rendered.response_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "casepath_candidate_artifact",
                    "strict": True,
                    "schema": rendered.response_schema,
                },
            }
        else:
            payload["response_format"] = {"type": "json_object"}
        started = time.perf_counter()
        response = self.transport.post_json(
            url=OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-Title": "CasePath matched-budget evaluation",
                "X-Request-ID": request_id,
            },
            payload=payload,
            timeout_seconds=request.budget.timeout_seconds,
        )
        latency_ms = max(0, round((time.perf_counter() - started) * 1000))
        response_id = _required_string(response, "id")
        response_model = _required_string(response, "model")
        if response_model not in {request.budget.model, request.budget.model_revision}:
            raise ProviderResponseError("provider returned an unapproved model revision")
        provider = _required_string(response, "provider")
        if provider != EXPECTED_PROVIDER:
            raise ProviderResponseError("provider returned an unapproved upstream provider")
        choices = response.get("choices")
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
            raise ProviderResponseError("provider response must contain exactly one choice")
        choice = choices[0]
        finish_reason = _required_string(choice, "finish_reason")
        if finish_reason != "stop":
            raise ProviderResponseError("provider response did not finish normally")
        message = choice.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise ProviderResponseError("provider response is missing assistant JSON")
        try:
            output = json.loads(
                message["content"],
                object_pairs_hook=_unique_object,
                parse_constant=_reject_nonfinite,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            raise ProviderResponseError("assistant output is not strict JSON") from exc
        if not isinstance(output, dict):
            raise ProviderResponseError("assistant output must be a JSON object")
        usage = response.get("usage")
        if not isinstance(usage, dict):
            raise ProviderResponseError("provider response is missing usage")
        input_tokens = _required_nonnegative_int(usage, "prompt_tokens")
        output_tokens = _required_nonnegative_int(usage, "completion_tokens")
        cost_value = usage.get("cost")
        cost_usd: float | None = None
        if cost_value is not None:
            if (
                not isinstance(cost_value, int | float)
                or isinstance(cost_value, bool)
                or not math.isfinite(float(cost_value))
                or cost_value < 0
            ):
                raise ProviderResponseError("provider usage contains invalid cost")
            cost_usd = float(cost_value)
        call_receipt = ProviderCallReceipt(
            request_id=request_id,
            response_id=response_id,
            stage=request.stage,
            request_sha256=digest_json(payload),
            requested_model=request.budget.model,
            response_model=response_model,
            upstream_provider=provider,
            finish_reason=finish_reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        )
        return ModelCallResult(
            payload=cast(dict[str, Any], output),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            provider_call=call_receipt,
        )
