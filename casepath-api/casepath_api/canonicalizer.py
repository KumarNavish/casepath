from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
import os
import re
import threading
from time import perf_counter, sleep
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from .langchain_runtime import (
    OPENROUTER_EXPECTED_UPSTREAM_PROVIDER,
    OpenRouterProtocolError,
    OpenRouterSendAdmissionTimeoutError,
    OpenRouterUpstreamRejectionError,
    assert_external_tracing_disabled,
    openrouter_provider_policy,
    sanitize_provider_provenance,
    structured_nemotron_runnable,
)
from .storage import Storage
from .projections import DECISION_OPTIONS
from .validation import ContractValidationError, validate_claim_state, validate_source_grounding


MODEL_MODE_REFERENCE = "deterministic_reference"
MODEL_MODE_OPENROUTER = "openrouter_nemotron"
MODEL_MODES = {MODEL_MODE_REFERENCE, MODEL_MODE_OPENROUTER}
OPENROUTER_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"
OPENROUTER_CANONICAL_MODEL = "nvidia/nemotron-3-ultra-550b-a55b-20260604"
OPENROUTER_ACCEPTED_RESPONSE_MODELS = {OPENROUTER_MODEL, OPENROUTER_CANONICAL_MODEL}
OPENROUTER_PROVIDER = "openrouter"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_GENERATION_URL = "https://openrouter.ai/api/v1/generation"
CANONICALIZER_VERSION = "1.10.0"
PROMPT_VERSION = "canonical-facts/1.9.0"
SCHEMA_VERSION = "casepath.canonical-facts/1.8.0"
PROVIDER_FACT_FIELDS = {
    "fact_id",
    "assertion_id",
    "source_ref_ids",
    "confidence",
}
CANONICAL_SYSTEM_PROMPT = (
    "You are the bounded CasePath canonical-facts component. Read only the supplied observable claim package. "
    "Fill every predeclared property in the fixed facts object. Return exactly one bounded assertion selection for each "
    "fact slot: its repeated fact_id, assertion_id, source_ref_ids object, and confidence only. Choose assertion_id only "
    "from that fact slot's finite ASSERTION CATALOG. The catalog contains "
    "all available bounded assertions and does not identify a preferred or expected answer. The application exclusively "
    "materializes labels, canonical states, normalized values, display prose, and process metadata from the accepted "
    "assertion; do not return any of those fields. Never infer a process, legal conclusion, responsibility, remedy, checklist, "
    "precedent, or knowledge update. Use only the supplied fact IDs. Select source_ref_ids only from the global "
    "SOURCE REFERENCE REGISTRY; each ID deterministically maps "
    "to one exact observable artifact, page, and excerpt. Binary images expose no textual content in "
    "this package: do not cite or describe their pixels. Each property in a fact's fixed source_ref_ids object names one "
    "required artifact. Select exactly one source-reference ID from that property's enum. An empty source_ref_ids object "
    "means that fact has no text source to select. A conflicting assertion necessarily has source selections for at least "
    "two different artifacts. "
    "The application independently validates assertion membership, registry binding, eligible source selection, "
    "and structural artifact coverage. Confidence expresses "
    "only the strength of the returned assertion selection."
)
MODEL_SINGLE_FLIGHT_LOCK = threading.RLock()

INPUT_USD_PER_MILLION_TOKENS = 0.625
OUTPUT_USD_PER_MILLION_TOKENS = 3.60
MAX_OUTPUT_TOKENS = 8_192
CANONICAL_REASONING = {"effort": "none"}
DEFAULT_CUMULATIVE_USD_CAP = 25.0
ABSOLUTE_CUMULATIVE_USD_CAP = 400.0
GENERATION_METADATA_POLL_ATTEMPTS = 8
GENERATION_METADATA_POLL_INTERVAL_SECONDS = 0.5
GENERATION_METADATA_POLL_MAX_INTERVAL_SECONDS = 8.0
GENERATION_METADATA_TIMEOUT_SECONDS = 10.0


class CanonicalizerError(RuntimeError):
    def __init__(self, message: str, *, safe_context: dict[str, Any] | None = None):
        super().__init__(message)
        self.safe_context = dict(safe_context or {})


class ModelConfigurationError(CanonicalizerError):
    pass


class ModelCostGuardError(CanonicalizerError):
    pass


class ModelResponseError(CanonicalizerError):
    def __init__(
        self,
        message: str,
        *,
        fact_id: str | None = None,
        invariant: str | None = None,
        diagnostics: dict[str, Any] | None = None,
        safe_context: dict[str, Any] | None = None,
    ):
        super().__init__(message, safe_context=safe_context)
        self.fact_id = fact_id
        self.invariant = invariant
        self.diagnostics = diagnostics


def _fact_response_error(fact_id: str, invariant: str) -> ModelResponseError:
    """Create a diagnostic that contains no provider-authored values."""

    return ModelResponseError(
        f"{fact_id}: {invariant} invariant failed",
        fact_id=fact_id,
        invariant=invariant,
    )


Transport = Callable[[str, dict[str, str], dict[str, Any], float], dict[str, Any]]
MetadataTransport = Callable[[str, dict[str, str], float], dict[str, Any]]
StructuredInvoker = Callable[
    [dict[str, Any], str, str, str, str, int],
    dict[str, Any],
]


class _GenerationMetadataPending(RuntimeError):
    pass


def configured_model_mode() -> str:
    mode = os.getenv("CASEPATH_MODEL_MODE", MODEL_MODE_REFERENCE).strip() or MODEL_MODE_REFERENCE
    if mode not in MODEL_MODES:
        raise ModelConfigurationError(f"Unsupported CASEPATH_MODEL_MODE {mode!r}")
    return mode


def cumulative_usd_cap() -> float:
    raw = os.getenv("CASEPATH_MODEL_CUMULATIVE_USD_CAP")
    if raw is None or not raw.strip():
        return DEFAULT_CUMULATIVE_USD_CAP
    try:
        requested = float(raw)
    except ValueError as exc:
        raise ModelConfigurationError("CASEPATH_MODEL_CUMULATIVE_USD_CAP must be numeric") from exc
    if not math.isfinite(requested) or requested <= 0:
        raise ModelConfigurationError(
            "CASEPATH_MODEL_CUMULATIVE_USD_CAP must be finite and positive"
        )
    return min(requested, DEFAULT_CUMULATIVE_USD_CAP, ABSOLUTE_CUMULATIVE_USD_CAP)


def _default_structured_invoker(
    schema: dict[str, Any],
    system_prompt: str,
    user_prompt: str,
    api_key: str,
    orchestration_id: str,
    max_tokens: int,
) -> dict[str, Any]:
    """Invoke canonical facts through the shared non-retrying LangChain adapter."""

    runnable = structured_nemotron_runnable(
        schema={"title": "casepath_canonical_facts", **schema},
        api_key=api_key,
        orchestration_id=orchestration_id,
        max_tokens=max_tokens,
        reasoning=CANONICAL_REASONING,
    )
    assert_external_tracing_disabled()
    protocol_invariant: str | None = None
    protocol_safe_context: dict[str, Any] = {}
    try:
        envelope = runnable.invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)],
            config={"callbacks": []},
        )
    except (
        OpenRouterProtocolError,
        OpenRouterSendAdmissionTimeoutError,
        OpenRouterUpstreamRejectionError,
    ) as exc:
        protocol_invariant = exc.invariant
        if isinstance(exc, OpenRouterUpstreamRejectionError):
            protocol_safe_context = exc.safe_context
        elif isinstance(exc, OpenRouterSendAdmissionTimeoutError):
            protocol_safe_context = {
                "call_count": 0,
                "outcome": "blocked_provider_concurrency",
            }
    if protocol_invariant is not None:
        raise ModelResponseError(
            f"{protocol_invariant} invariant failed",
            invariant=protocol_invariant,
            safe_context=protocol_safe_context,
        )
    if not isinstance(envelope, dict):
        raise ModelResponseError("OpenRouter omitted the LangChain response envelope")
    parsed = envelope.get("parsed")
    if isinstance(parsed, BaseModel):
        parsed = parsed.model_dump(mode="json")
    raw = envelope.get("raw")
    response_metadata = getattr(raw, "response_metadata", None)
    usage_metadata = getattr(raw, "usage_metadata", None)
    if not isinstance(response_metadata, dict):
        response_metadata = {}
    if not isinstance(usage_metadata, dict):
        usage_metadata = {}
    response_id = response_metadata.get("id")
    response_model = response_metadata.get("model_name") or response_metadata.get("model")
    usage_value = response_metadata.get("usage")
    usage_value = dict(usage_value) if isinstance(usage_value, dict) else {}
    prompt_tokens = usage_value.get("prompt_tokens", usage_metadata.get("input_tokens"))
    completion_tokens = usage_value.get("completion_tokens", usage_metadata.get("output_tokens"))
    total_tokens = usage_value.get("total_tokens", usage_metadata.get("total_tokens"))
    cost = usage_value.get("cost", response_metadata.get("cost"))
    usage = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost": cost,
    }
    return {
        "id": response_id,
        "model": response_model,
        "provider": response_metadata.get("provider_name"),
        "choices": [
            {
                "finish_reason": response_metadata.get("finish_reason"),
                "message": {
                    "role": "assistant",
                    "content": parsed if isinstance(parsed, dict) else None,
                },
            }
        ],
        "usage": usage,
        "openrouter_metadata": None,
        "_structured_parsing_error": envelope.get("parsing_error") is not None
        or not isinstance(parsed, dict),
    }


def _default_metadata_transport(url: str, headers: dict[str, str], timeout: float) -> dict[str, Any]:
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed HTTPS endpoint
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            raise _GenerationMetadataPending from exc
        raise ModelResponseError("OpenRouter generation-metadata request failed") from exc
    except URLError as exc:
        raise ModelResponseError("OpenRouter generation-metadata request failed") from exc


def canonical_facts_schema(
    source_reference_registry: list[dict[str, Any]],
    assertion_catalog: list[dict[str, Any]],
) -> dict[str, Any]:
    registry_by_id = {
        item.get("source_ref_id"): item
        for item in source_reference_registry
        if isinstance(item, dict)
        and isinstance(item.get("source_ref_id"), str)
        and item.get("source_ref_id", "").strip()
        and isinstance(item.get("artifact_id"), str)
        and item.get("artifact_id", "").strip()
    }
    if len(registry_by_id) != len(source_reference_registry):
        raise ModelConfigurationError(
            "Canonical-facts schema requires a valid source-reference registry"
        )
    if not isinstance(assertion_catalog, list) or not assertion_catalog:
        raise ModelConfigurationError("Canonical-facts schema requires fact slots")

    fact_ids = [
        slot.get("fact_id") if isinstance(slot, dict) else None
        for slot in assertion_catalog
    ]
    if (
        any(not isinstance(fact_id, str) or not fact_id.strip() for fact_id in fact_ids)
        or len(set(fact_ids)) != len(fact_ids)
    ):
        raise ModelConfigurationError(
            "Canonical-facts schema requires nonempty unique fact identifiers"
        )

    fact_properties: dict[str, Any] = {}
    all_assertion_ids: list[str] = []
    for slot, fact_id in zip(assertion_catalog, fact_ids, strict=True):
        assertions = slot.get("assertions")
        assertion_ids = [
            item.get("assertion_id") if isinstance(item, dict) else None
            for item in assertions
        ] if isinstance(assertions, list) else []
        if (
            not assertion_ids
            or any(
                not isinstance(assertion_id, str) or not assertion_id.strip()
                for assertion_id in assertion_ids
            )
            or len(set(assertion_ids)) != len(assertion_ids)
        ):
            raise ModelConfigurationError(
                "Canonical-facts schema requires bounded assertion identifiers"
            )
        all_assertion_ids.extend(assertion_ids)

        eligible_source_ref_ids = slot.get("eligible_source_ref_ids")
        if (
            not isinstance(eligible_source_ref_ids, list)
            or eligible_source_ref_ids != sorted(set(eligible_source_ref_ids))
            or any(not isinstance(ref_id, str) for ref_id in eligible_source_ref_ids)
            or set(eligible_source_ref_ids) - set(registry_by_id)
        ):
            raise ModelConfigurationError(
                "Canonical-facts schema requires bounded source-reference identifiers"
            )
        refs_by_artifact: dict[str, list[str]] = {}
        for ref_id in eligible_source_ref_ids:
            artifact_id = registry_by_id[ref_id]["artifact_id"]
            refs_by_artifact.setdefault(artifact_id, []).append(ref_id)
        artifact_ids = sorted(refs_by_artifact)
        source_ref_ids = {
            "type": "object",
            "properties": {
                artifact_id: {
                    "type": "string",
                    "enum": sorted(refs_by_artifact[artifact_id]),
                }
                for artifact_id in artifact_ids
            },
            "required": artifact_ids,
            "additionalProperties": False,
        }
        fact_properties[fact_id] = {
            "type": "object",
            "properties": {
                "fact_id": {"type": "string", "enum": [fact_id]},
                "assertion_id": {"type": "string", "enum": assertion_ids},
                "source_ref_ids": source_ref_ids,
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": sorted(PROVIDER_FACT_FIELDS),
            "additionalProperties": False,
        }
    if len(set(all_assertion_ids)) != len(all_assertion_ids):
        raise ModelConfigurationError(
            "Canonical-facts schema requires globally unique assertion identifiers"
        )

    return {
        "type": "object",
        "properties": {
            "facts": {
                "type": "object",
                "properties": fact_properties,
                "required": fact_ids,
                "additionalProperties": False,
            }
        },
        "required": ["facts"],
        "additionalProperties": False,
    }


def _normalize_canonical_facts_response(
    output: dict[str, Any],
    *,
    fact_ids: list[str],
    provider_schema: dict[str, Any],
) -> dict[str, Any]:
    """Validate fixed provider slots, then restore the internal facts list."""

    def native_schema_error() -> ModelResponseError:
        return ModelResponseError(
            "provider_native_schema invariant failed",
            invariant="provider_native_schema",
        )

    if set(output) != {"facts"}:
        raise native_schema_error()
    wire_facts = output.get("facts")
    if not isinstance(wire_facts, dict) or set(wire_facts) != set(fact_ids):
        raise native_schema_error()
    try:
        fact_schemas = provider_schema["properties"]["facts"]["properties"]
    except (KeyError, TypeError) as exc:  # pragma: no cover - local construction invariant
        raise ModelConfigurationError("Canonical-facts provider schema is invalid") from exc
    if not isinstance(fact_schemas, dict) or set(fact_schemas) != set(fact_ids):
        raise ModelConfigurationError("Canonical-facts provider schema is invalid")

    normalized: list[dict[str, Any]] = []
    for fact_id in fact_ids:
        value = wire_facts.get(fact_id)
        if not isinstance(value, dict) or value.get("fact_id") != fact_id:
            raise native_schema_error()
        fact = dict(value)
        refs_by_artifact = fact.get("source_ref_ids")
        try:
            source_schema = fact_schemas[fact_id]["properties"]["source_ref_ids"]
            artifact_schemas = source_schema["properties"]
            required_artifact_ids = source_schema["required"]
        except (KeyError, TypeError) as exc:  # pragma: no cover - local construction invariant
            raise ModelConfigurationError("Canonical-facts provider schema is invalid") from exc
        if (
            not isinstance(refs_by_artifact, dict)
            or not isinstance(artifact_schemas, dict)
            or not isinstance(required_artifact_ids, list)
            or set(refs_by_artifact) != set(required_artifact_ids)
            or set(artifact_schemas) != set(required_artifact_ids)
            or any(
                not isinstance(refs_by_artifact.get(artifact_id), str)
                or refs_by_artifact[artifact_id]
                not in artifact_schemas[artifact_id].get("enum", [])
                for artifact_id in required_artifact_ids
            )
        ):
            raise native_schema_error()
        fact["source_ref_ids"] = [
            refs_by_artifact[artifact_id]
            for artifact_id in sorted(required_artifact_ids)
        ]
        normalized.append(fact)
    return {"facts": normalized}


def _assertion_id(
    *,
    fact_id: str,
    state: str,
    value: str,
    normalized_value: str | None,
) -> str:
    material = {
        "fact_id": fact_id,
        "state": state,
        "value": value,
        "normalized_value": normalized_value,
    }
    encoded = json.dumps(
        material, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return f"assert_{sha256(encoded).hexdigest()[:24]}"


def _alternative_assertion_material(
    *,
    label: str,
    normalized_value: str,
    decision_value: str,
) -> tuple[str, str, str]:
    unknown = normalized_value in {"unverified", "unresolved"}
    state = "unknown" if unknown else "known"
    readable = normalized_value.replace("_", " ")
    value = f"{label}: {readable}"
    explanation = (
        f"The selected bounded assertion leaves {label.lower()} unresolved."
        if unknown
        else f"The selected bounded assertion supports {label.lower()} as {readable}."
    )
    return state, value, explanation


def bounded_fact_assertion_catalog(
    fact_catalog: list[dict[str, Any]],
    source_reference_registry: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build a finite answer-neutral assertion catalog for each fact slot.

    The catalog contains materialization data for every bounded choice, but no
    expected/preferred marker. Candidate order is identifier order so the
    current deterministic reference value is not signalled positionally.
    """

    registry_ids = {
        item.get("source_ref_id")
        for item in source_reference_registry
        if isinstance(item, dict)
        and isinstance(item.get("source_ref_id"), str)
    }
    result: list[dict[str, Any]] = []
    for contract in fact_catalog:
        fact_id = contract.get("fact_id")
        label = contract.get("label")
        controls_process = contract.get("controls_process")
        decision_key = contract.get("decision_key")
        normalized_options = contract.get("normalized_options")
        current_values = contract.get("admissible_normalized_values")
        current_state = contract.get("expected_state")
        current_value = contract.get("canonical_value")
        current_explanation = contract.get("canonical_explanation")
        if (
            not isinstance(fact_id, str)
            or not fact_id
            or not isinstance(label, str)
            or not label
            or not isinstance(controls_process, bool)
            or not isinstance(normalized_options, dict)
            or not isinstance(current_values, list)
            or current_state
            not in {"known", "unknown", "conflicting", "not_applicable"}
            or not isinstance(current_value, str)
            or not isinstance(current_explanation, str)
            or not current_explanation.strip()
        ):
            raise ModelConfigurationError("Fact catalog assertion metadata is invalid")
        if controls_process:
            if (
                len(current_values) != 1
                or not isinstance(decision_key, str)
                or normalized_options != DECISION_OPTIONS.get(decision_key)
                or current_values[0] not in normalized_options
            ):
                raise ModelConfigurationError(
                    "Controlling fact assertion catalog is invalid"
                )
            conservative_normalized = {
                "scope": "unverified",
                "dispute": "unverified",
                "urgency": "unverified",
                "notification": "unverified",
                "recurrence": "unverified",
                "causation": "unresolved",
            }[decision_key]
            normalized_candidates = sorted(
                {current_values[0], conservative_normalized}
            )
        else:
            if decision_key is not None or normalized_options or current_values:
                raise ModelConfigurationError(
                    "Non-controlling fact assertion catalog is invalid"
                )
            normalized_candidates = [None]

        admissible_refs = contract.get("admissible_text_refs")
        if not isinstance(admissible_refs, list):
            raise ModelConfigurationError("Fact assertion grounding is invalid")
        related_artifact_ids = {
            ref.get("artifact_id")
            for ref in admissible_refs
            if isinstance(ref, dict) and isinstance(ref.get("artifact_id"), str)
        }
        eligible_source_ref_ids = sorted(
            item["source_ref_id"]
            for item in source_reference_registry
            if item.get("artifact_id") in related_artifact_ids
        )
        if set(eligible_source_ref_ids) - registry_ids:
            raise ModelConfigurationError("Fact assertion grounding is invalid")
        candidates: list[dict[str, Any]] = []
        for normalized_value in normalized_candidates:
            is_reference_material = (
                normalized_value is None
                or normalized_value == current_values[0]
            )
            if is_reference_material:
                state = current_state
                value = current_value
                explanation = current_explanation
            else:
                state, value, explanation = _alternative_assertion_material(
                    label=label,
                    normalized_value=str(normalized_value),
                    decision_value=normalized_options[str(normalized_value)],
                )
            decision_value = (
                normalized_options[normalized_value]
                if isinstance(normalized_value, str)
                else None
            )
            candidates.append(
                {
                    "assertion_id": _assertion_id(
                        fact_id=fact_id,
                        state=state,
                        value=value,
                        normalized_value=normalized_value,
                    ),
                    "fact_id": fact_id,
                    "assertion_label": (
                        f"{label}: {str(normalized_value).replace('_', ' ')}"
                        if normalized_value is not None
                        else f"{label}: {state}"
                    ),
                    "state": state,
                    "value": value,
                    "explanation": explanation,
                    "normalized_value": normalized_value,
                    "decision_value": decision_value,
                }
            )
        result.append(
            {
                "fact_id": fact_id,
                "label": label,
                "model_selects_meaning": controls_process,
                "eligible_source_ref_ids": eligible_source_ref_ids,
                "assertions": sorted(
                    candidates, key=lambda item: item["assertion_id"]
                ),
            }
        )
    assertion_ids = [
        assertion["assertion_id"]
        for slot in result
        for assertion in slot["assertions"]
    ]
    if len(set(assertion_ids)) != len(assertion_ids):
        raise ModelConfigurationError("Assertion identifier collision")
    return result


def _fact_catalog_identity(fact_catalog: list[dict[str, Any]]) -> list[str]:
    """Validate the provider-visible catalog identity before any cache/provider work."""

    if not isinstance(fact_catalog, list) or not fact_catalog:
        raise ModelConfigurationError("Fact catalog must be a nonempty list")
    if any(
        not isinstance(item, dict)
        or not isinstance(item.get("fact_id"), str)
        or not item.get("fact_id", "").strip()
        or not isinstance(item.get("label"), str)
        or not item.get("label", "").strip()
        for item in fact_catalog
    ):
        raise ModelConfigurationError(
            "Fact catalog identifiers and labels must be nonempty strings"
        )
    fact_ids = [item["fact_id"] for item in fact_catalog]
    if len(set(fact_ids)) != len(fact_ids):
        raise ModelConfigurationError("Fact catalog identifiers must be unique")
    return fact_ids


def _input_token_estimate(value: str) -> int:
    # Three bytes per token intentionally over-reserves relative to the common
    # four-character heuristic so the local preflight guard remains conservative.
    return max(1, math.ceil(len(value.encode("utf-8")) / 3))


def _estimated_cost(input_tokens: int) -> float:
    return round(
        input_tokens * INPUT_USD_PER_MILLION_TOKENS / 1_000_000
        + MAX_OUTPUT_TOKENS * OUTPUT_USD_PER_MILLION_TOKENS / 1_000_000,
        8,
    )


def _cache_key(
    input_contract: dict[str, Any],
    *,
    provider_schema: dict[str, Any],
    system_prompt: str,
) -> str:
    value = {
        "model": OPENROUTER_MODEL,
        "canonicalizer_version": CANONICALIZER_VERSION,
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "provider_schema": provider_schema,
        "system_prompt_sha256": sha256(system_prompt.encode("utf-8")).hexdigest(),
        "max_tokens": MAX_OUTPUT_TOKENS,
        "reasoning": dict(CANONICAL_REASONING),
        "provider_policy": openrouter_provider_policy(),
        "temperature": 0,
        "strict_schema": True,
        "input_contract": input_contract,
    }
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _response_content(response: dict[str, Any]) -> dict[str, Any]:
    if response.get("_structured_parsing_error") is True:
        raise ModelResponseError(
            "provider_native_schema invariant failed",
            invariant="provider_native_schema",
        )
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ModelResponseError("OpenRouter response omitted structured message content") from exc
    if isinstance(content, dict):
        value = content
    elif isinstance(content, str):
        try:
            value = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ModelResponseError("OpenRouter returned invalid canonical-facts JSON") from exc
    else:
        raise ModelResponseError("OpenRouter returned an unsupported message content type")
    if not isinstance(value, dict):
        raise ModelResponseError("Canonical-facts response must be an object")
    return value


def _partial_response_identity(response: Any) -> dict[str, Any]:
    """Extract only bounded identity fields without deciding their admissibility."""

    response = response if isinstance(response, dict) else {}
    choices = response.get("choices")
    first_choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
    sanitized, violation = sanitize_provider_provenance(
        response_id=response.get("id"),
        response_model=response.get("model"),
        upstream_provider=response.get("provider"),
        finish_reason=first_choice.get("finish_reason"),
    )
    return {
        "response_id": sanitized["response_id"],
        "response_model": sanitized["response_model"],
        "response_finish_reason": sanitized["finish_reason"],
        "upstream_provider": sanitized["upstream_provider"],
        "provenance_violation": violation,
    }


def _validate_response_identity(identity: dict[str, Any]) -> None:
    if identity.get("provenance_violation") is not None:
        raise ModelResponseError(
            "invalid_provenance invariant failed",
            invariant="invalid_provenance",
            diagnostics=identity["provenance_violation"],
            safe_context=identity["provenance_violation"],
        )
    if identity.get("response_id") is None or identity.get("response_model") is None:
        raise ModelResponseError(
            "response_identity invariant failed",
            invariant="response_identity",
        )
    if identity["response_model"] not in OPENROUTER_ACCEPTED_RESPONSE_MODELS:
        raise ModelResponseError(
            "response_model invariant failed",
            invariant="response_model",
        )


def _synchronous_usage_ledger_patch(
    response: dict[str, Any],
    *,
    identity: dict[str, Any],
    latency_ms: float,
) -> dict[str, Any] | None:
    """Return complete synchronous billing evidence, or request metadata fallback."""

    usage = response.get("usage")
    if not isinstance(usage, dict):
        return None
    cost = usage.get("cost")
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    total_tokens = usage.get("total_tokens")
    upstream_provider = identity.get("upstream_provider")
    if (
        not isinstance(cost, (int, float))
        or isinstance(cost, bool)
        or float(cost) <= 0
        or not math.isfinite(float(cost))
        or not isinstance(prompt_tokens, int)
        or isinstance(prompt_tokens, bool)
        or prompt_tokens <= 0
        or not isinstance(completion_tokens, int)
        or isinstance(completion_tokens, bool)
        or completion_tokens <= 0
        or not isinstance(total_tokens, int)
        or isinstance(total_tokens, bool)
        or total_tokens < prompt_tokens + completion_tokens
    ):
        return None
    patch = {
        "latency_ms": latency_ms,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "actual_cost_usd": float(cost),
        "usage_source": "response",
        "finish_reason": identity["response_finish_reason"],
    }
    if upstream_provider is not None:
        patch["upstream_provider"] = upstream_provider
    if identity.get("response_id") is not None:
        patch["response_id"] = identity["response_id"]
    if identity.get("response_model") is not None:
        patch["response_model"] = identity["response_model"]
    return patch


def _generation_metadata_ledger_patch(
    *,
    identity: dict[str, Any],
    headers: dict[str, str],
    metadata_transport: MetadataTransport,
    metadata_sleep: Callable[[float], None],
    timeout_seconds: float,
    poll_attempts: int,
    poll_interval_seconds: float,
    latency_ms: float,
) -> dict[str, Any]:
    """Resolve billing evidence for one existing generation without retrying inference."""

    metadata_url = f"{OPENROUTER_GENERATION_URL}?{urlencode({'id': identity['response_id']})}"
    metadata_headers = {
        "Authorization": headers["Authorization"],
        "Accept": "application/json",
    }
    started = perf_counter()
    for attempt in range(1, poll_attempts + 1):
        try:
            envelope = metadata_transport(metadata_url, metadata_headers, timeout_seconds)
        except _GenerationMetadataPending:
            envelope = None
        data = envelope.get("data") if isinstance(envelope, dict) else None
        if isinstance(data, dict):
            required = {
                "id",
                "model",
                "provider_name",
                "native_tokens_prompt",
                "native_tokens_completion",
                "total_cost",
                "usage",
                "finish_reason",
            }
            # The generation row is eventually materialized. During that window
            # OpenRouter can expose the full key set with nullable fields still
            # unset; treat that shape like a 404/partial row and keep polling.
            if required.issubset(data) and all(
                data[key] is not None for key in required
            ):
                prompt_tokens = data["native_tokens_prompt"]
                completion_tokens = data["native_tokens_completion"]
                total_cost = data["total_cost"]
                usage_cost = data["usage"]
                provenance, provenance_violation = sanitize_provider_provenance(
                    response_id=data["id"],
                    response_model=data["model"],
                    upstream_provider=data["provider_name"],
                    finish_reason=data["finish_reason"],
                )
                provider_name = provenance["upstream_provider"]
                finish_reason = provenance["finish_reason"]
                valid_usage = (
                    isinstance(prompt_tokens, int)
                    and not isinstance(prompt_tokens, bool)
                    and prompt_tokens > 0
                    and isinstance(completion_tokens, int)
                    and not isinstance(completion_tokens, bool)
                    and completion_tokens > 0
                    and isinstance(total_cost, (int, float))
                    and not isinstance(total_cost, bool)
                    and float(total_cost) > 0
                    and math.isfinite(float(total_cost))
                    and isinstance(usage_cost, (int, float))
                    and not isinstance(usage_cost, bool)
                    and float(usage_cost) > 0
                    and math.isfinite(float(usage_cost))
                    and math.isclose(float(total_cost), float(usage_cost), rel_tol=1e-6, abs_tol=1e-9)
                )
                if not valid_usage:
                    raise ModelResponseError(
                        "generation_metadata_usage invariant failed",
                        invariant="generation_metadata_usage",
                        safe_context={
                            "latency_ms": latency_ms,
                            "metadata_latency_ms": round(
                                (perf_counter() - started) * 1000, 3
                            ),
                            "metadata_poll_count": attempt,
                        },
                    )
                total_tokens = prompt_tokens + completion_tokens
                billing_patch = {
                    "latency_ms": latency_ms,
                    "metadata_latency_ms": round((perf_counter() - started) * 1000, 3),
                    "metadata_poll_count": attempt,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "actual_cost_usd": float(total_cost),
                    "usage_source": "generation_metadata",
                    "response_id": identity["response_id"],
                    **(
                        {"response_model": identity["response_model"]}
                        if identity.get("response_model") is not None
                        else {}
                    ),
                }
                if provenance_violation is not None:
                    raise ModelResponseError(
                        "invalid_provenance invariant failed",
                        invariant="invalid_provenance",
                        diagnostics=provenance_violation,
                        safe_context={**billing_patch, **provenance_violation},
                    )
                if provenance["response_id"] != identity["response_id"]:
                    raise ModelResponseError(
                        "generation_metadata_identity invariant failed",
                        invariant="generation_metadata_identity",
                    )
                if provider_name is None or finish_reason is None:
                    raise ModelResponseError(
                        "invalid_provenance invariant failed",
                        invariant="invalid_provenance",
                    )
                return {
                    **billing_patch,
                    "generation_model": provenance["response_model"],
                    "upstream_provider": provider_name,
                    "finish_reason": finish_reason,
                }
        if attempt < poll_attempts:
            metadata_sleep(
                min(
                    poll_interval_seconds * (2 ** (attempt - 1)),
                    GENERATION_METADATA_POLL_MAX_INTERVAL_SECONDS,
                )
            )
    raise ModelResponseError(
        "generation_metadata_completeness invariant failed",
        invariant="generation_metadata_completeness",
        safe_context={
            "latency_ms": latency_ms,
            "metadata_latency_ms": round((perf_counter() - started) * 1000, 3),
            "metadata_poll_count": poll_attempts,
        },
    )


def validate_exact_source_excerpts(package: dict[str, Any], facts: list[dict[str, Any]]) -> None:
    """Fail closed unless every cited excerpt occurs on the exact textual source page."""
    try:
        validate_source_grounding({"facts": facts}, observable_package=package)
    except ContractValidationError as exc:
        raise ModelResponseError(str(exc)) from exc


def source_reference_id(ref: dict[str, Any]) -> str:
    """Return a stable identifier for an exact observable text reference."""

    try:
        value = {
            "artifact_id": ref["artifact_id"],
            "page": ref["page"],
            "excerpt": ref["excerpt"],
        }
    except (KeyError, TypeError) as exc:
        raise ModelConfigurationError("Text-reference candidates require artifact_id, page, and excerpt") from exc
    if (
        not isinstance(value["artifact_id"], str)
        or not value["artifact_id"].strip()
        or not isinstance(value["page"], int)
        or isinstance(value["page"], bool)
        or value["page"] < 1
        or not isinstance(value["excerpt"], str)
        or not value["excerpt"].strip()
    ):
        raise ModelConfigurationError("Text-reference candidates require a nonempty source, page, and excerpt")
    digest = sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"src_{digest[:24]}"


def _bounded_passages(text: str) -> list[str]:
    """Split one observable field into bounded, source-owned passage candidates."""

    values: set[str] = set()
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    for line in lines:
        if not line:
            continue
        values.add(line)
        values.update(
            part.strip()
            for part in re.split(r"(?<=[.!?])\s+|\s*[;]\s*", line)
            if part.strip()
        )
    # Adjacent lines are exposed only for short structural labels (for example
    # ``Tenant\nAlex Morgan``). Blanket windows and whole-document compaction add
    # hundreds of redundant candidates and make the bounded provider task noisy.
    values.update(
        f"{lines[index]} {lines[index + 1]}"
        for index in range(len(lines) - 1)
        if len(lines[index]) <= 40
    )
    return sorted(values, key=lambda value: (len(value), value))


def observable_source_reference_registry(package: dict[str, Any]) -> list[dict[str, Any]]:
    """Build text candidates solely from the model-observable package."""

    candidates: list[dict[str, Any]] = []
    message = package.get("customer_message")
    if isinstance(message, dict):
        artifact_id = message.get("artifact_id", "message")
        for key in ("subject", "body"):
            value = message.get(key)
            if isinstance(value, str):
                candidates.extend(
                    {"artifact_id": artifact_id, "page": 1, "excerpt": passage}
                    for passage in _bounded_passages(value)
                )
    for artifact in package.get("artifacts", []):
        if not isinstance(artifact, dict) or not isinstance(artifact.get("artifact_id"), str):
            continue
        artifact_id = artifact["artifact_id"]
        for page in artifact.get("extracted_pages", []):
            if not isinstance(page, dict) or not isinstance(page.get("page"), int):
                continue
            text = page.get("text")
            if isinstance(text, str):
                candidates.extend(
                    {"artifact_id": artifact_id, "page": page["page"], "excerpt": passage}
                    for passage in _bounded_passages(text)
                )
        email = artifact.get("parsed_email")
        if isinstance(email, dict):
            for value in email.values():
                if isinstance(value, str):
                    candidates.extend(
                        {"artifact_id": artifact_id, "page": 1, "excerpt": passage}
                        for passage in _bounded_passages(value)
                    )

    registry_by_id: dict[str, dict[str, Any]] = {}
    for ref in candidates:
        ref_id = source_reference_id(ref)
        candidate = {"source_ref_id": ref_id, **ref}
        existing = registry_by_id.get(ref_id)
        if existing is not None and existing != candidate:
            raise ModelConfigurationError("Text-reference identifier collision")
        registry_by_id[ref_id] = candidate

    registry = [registry_by_id[ref_id] for ref_id in sorted(registry_by_id)]
    grounded_refs = [
        {
            "artifact_id": item["artifact_id"],
            "locator_kind": "text_quote",
            "page": item["page"],
            "excerpt": item["excerpt"],
            "agent": "CasePath Source Registry",
        }
        for item in registry
    ]
    if grounded_refs:
        try:
            validate_source_grounding(
                {"facts": [{"source_refs": grounded_refs}]},
                observable_package=package,
            )
        except ContractValidationError as exc:
            raise ModelConfigurationError("Source-reference registry contains ungrounded text") from exc
    return registry


def resolve_observable_source_reference_id(
    ref: dict[str, Any],
    registry: list[dict[str, Any]],
) -> str:
    """Resolve a private exact quote to its smallest observable source passage."""

    expected = " ".join(str(ref.get("excerpt", "")).split()).casefold()
    matches = [
        item
        for item in registry
        if item.get("artifact_id") == ref.get("artifact_id")
        and item.get("page") == ref.get("page")
        and expected
        and expected in " ".join(str(item.get("excerpt", "")).split()).casefold()
    ]
    if not matches:
        raise ModelConfigurationError("Private quote has no observable passage candidate")
    selected = min(matches, key=lambda item: (len(item["excerpt"]), item["source_ref_id"]))
    return selected["source_ref_id"]


def _merge_fact_contracts(
    output: dict[str, Any],
    fact_catalog: list[dict[str, Any]],
    source_reference_registry: list[dict[str, Any]],
    assertion_catalog: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Materialize one complete, strictly validated finite assertion response."""

    if set(output) != {"facts"} or not isinstance(output.get("facts"), list):
        raise ModelResponseError("Canonical-facts response must contain only a facts array")
    catalog_by_id = {item.get("fact_id"): item for item in fact_catalog}
    if len(catalog_by_id) != len(fact_catalog) or None in catalog_by_id:
        raise ModelConfigurationError("Fact catalog identifiers must be present and unique")
    returned_ids = [item.get("fact_id") for item in output["facts"] if isinstance(item, dict)]
    if len(returned_ids) != len(output["facts"]) or len(set(returned_ids)) != len(returned_ids):
        raise ModelResponseError(
            "fact_catalog_membership invariant failed",
            invariant="fact_catalog_membership",
        )
    allowed_ids = set(catalog_by_id)
    if set(returned_ids) != allowed_ids:
        raise ModelResponseError(
            "fact_catalog_membership invariant failed",
            invariant="fact_catalog_membership",
        )
    returned_by_id = {item["fact_id"]: item for item in output["facts"]}

    registry_by_id = {
        item.get("source_ref_id"): item
        for item in source_reference_registry
        if isinstance(item, dict)
    }
    if (
        len(registry_by_id) != len(source_reference_registry)
        or None in registry_by_id
        or any(
            set(item) != {"source_ref_id", "artifact_id", "page", "excerpt"}
            for item in source_reference_registry
        )
    ):
        raise ModelConfigurationError("Source-reference registry is invalid")

    assertion_slots = {
        slot.get("fact_id"): slot
        for slot in assertion_catalog
        if isinstance(slot, dict)
    }
    if set(assertion_slots) != set(catalog_by_id) or len(assertion_slots) != len(
        assertion_catalog
    ):
        raise ModelConfigurationError("Assertion catalog fact membership is invalid")
    assertions_by_slot: dict[str, dict[str, dict[str, Any]]] = {}
    eligible_source_ids_by_slot: dict[str, list[str]] = {}
    for fact_id, slot in assertion_slots.items():
        candidates = slot.get("assertions")
        if not isinstance(candidates, list) or not candidates:
            raise ModelConfigurationError("Assertion catalog slot is invalid")
        by_id = {
            candidate.get("assertion_id"): candidate
            for candidate in candidates
            if isinstance(candidate, dict)
            and isinstance(candidate.get("assertion_id"), str)
        }
        if len(by_id) != len(candidates):
            raise ModelConfigurationError("Assertion catalog identifiers are invalid")
        eligible_source_ids = slot.get("eligible_source_ref_ids")
        if (
            not isinstance(eligible_source_ids, list)
            or eligible_source_ids != sorted(set(eligible_source_ids))
            or any(not isinstance(ref_id, str) for ref_id in eligible_source_ids)
            or set(eligible_source_ids) - set(registry_by_id)
        ):
            raise ModelConfigurationError("Eligible source-selection policy is invalid")
        assertions_by_slot[fact_id] = by_id
        eligible_source_ids_by_slot[fact_id] = eligible_source_ids

    merged: list[dict[str, Any]] = []
    accepted_fact_ids: list[str] = []
    rejected_facts: list[dict[str, str]] = []
    source_reference_projection_fact_ids: list[str] = []
    ignored_noncontrolling_normalized_proposals = 0
    for contract in fact_catalog:
        fact_id = contract["fact_id"]
        returned_fact = returned_by_id[fact_id]
        label = contract.get("label")
        expected_state = contract.get("expected_state")
        canonical_value = contract.get("canonical_value")
        canonical_explanation = contract.get("canonical_explanation")
        deterministic_confidence = contract.get("deterministic_confidence")
        semantic_role = contract.get("semantic_role")
        admissible_text_refs = contract.get("admissible_text_refs")
        deterministic_text_refs = contract.get("deterministic_text_refs")
        if (
            not isinstance(label, str)
            or not label.strip()
            or expected_state not in {"known", "unknown", "conflicting", "not_applicable"}
            or not isinstance(canonical_value, str)
            or not isinstance(canonical_explanation, str)
            or not canonical_explanation.strip()
            or not isinstance(deterministic_confidence, (int, float))
            or isinstance(deterministic_confidence, bool)
            or not 0 <= deterministic_confidence <= 1
            or semantic_role not in {None, "management_ventilation_allegation"}
            or not isinstance(admissible_text_refs, list)
            or any(
                not isinstance(ref, dict)
                or set(ref) != {"artifact_id", "page", "excerpt"}
                or not isinstance(ref.get("artifact_id"), str)
                or not ref.get("artifact_id", "").strip()
                or not isinstance(ref.get("page"), int)
                or isinstance(ref.get("page"), bool)
                or ref.get("page", 0) < 1
                or not isinstance(ref.get("excerpt"), str)
                or not ref.get("excerpt", "").strip()
                for ref in admissible_text_refs
            )
            or not isinstance(deterministic_text_refs, list)
            or any(
                not isinstance(ref, dict)
                or set(ref) != {"artifact_id", "locator_kind", "page", "excerpt", "agent"}
                or ref.get("locator_kind") != "text_quote"
                or not isinstance(ref.get("agent"), str)
                or not ref.get("agent", "").strip()
                for ref in deterministic_text_refs
            )
            or {
                (ref["artifact_id"], ref["page"], ref["excerpt"])
                for ref in deterministic_text_refs
            }
            != {
                (ref["artifact_id"], ref["page"], ref["excerpt"])
                for ref in admissible_text_refs
            }
        ):
            raise ModelConfigurationError("Fact catalog canonical truth metadata is invalid")
        related_artifact_ids = {
            ref["artifact_id"] for ref in admissible_text_refs
        }
        expected_eligible_source_ids = sorted(
            ref_id
            for ref_id, ref in registry_by_id.items()
            if ref["artifact_id"] in related_artifact_ids
        )
        eligible_source_ids = eligible_source_ids_by_slot[fact_id]
        if eligible_source_ids != expected_eligible_source_ids:
            raise ModelConfigurationError(
                "Eligible source-selection policy does not match fact artifacts"
            )
        required_source_artifact_ids = {
            registry_by_id[ref_id]["artifact_id"]
            for ref_id in eligible_source_ids
        }
        controls_process = contract.get("controls_process")
        decision_key = contract.get("decision_key")
        normalized_options = contract.get("normalized_options")
        if not isinstance(controls_process, bool) or not isinstance(normalized_options, dict):
            raise ModelConfigurationError("Fact catalog process metadata is incomplete")
        if controls_process:
            admissible_values = contract.get("admissible_normalized_values")
            if (
                not isinstance(admissible_values, list)
                or len(admissible_values) != 1
                or not isinstance(decision_key, str)
                or any(value not in normalized_options for value in admissible_values)
            ):
                raise ModelConfigurationError("Controlling fact admissibility metadata is invalid")
            fallback_normalized_value = admissible_values[0]
            fallback_decision_value = normalized_options[fallback_normalized_value]
        else:
            if (
                decision_key is not None
                or normalized_options
                or contract.get("admissible_normalized_values")
            ):
                raise ModelConfigurationError("Non-controlling fact process metadata must remain empty")
            fallback_normalized_value = None
            fallback_decision_value = None
        enrichments = contract.get("bounded_enrichments", [])
        if not isinstance(enrichments, list) or any(
            not isinstance(ref, dict)
            or ref.get("locator_kind") not in {"visual_observation", "metadata_field"}
            for ref in enrichments
        ):
            raise ModelConfigurationError("Fact catalog bounded enrichments are invalid")

        fallback_assertion = next(
            (
                candidate
                for candidate in assertions_by_slot[fact_id].values()
                if candidate.get("state") == expected_state
                and candidate.get("value") == canonical_value
                and candidate.get("explanation") == canonical_explanation
                and candidate.get("normalized_value") == fallback_normalized_value
                and candidate.get("decision_value") == fallback_decision_value
            ),
            None,
        )
        if fallback_assertion is None:
            raise ModelConfigurationError(
                "Fact catalog fallback assertion is not structurally represented"
            )

        rejection_invariant: str | None = None
        returned_ref_ids = returned_fact.get("source_ref_ids")
        provider_confidence = returned_fact.get("confidence")
        returned_assertion_id = returned_fact.get("assertion_id")
        selected_assertion = assertions_by_slot[fact_id].get(returned_assertion_id)
        if set(returned_fact) != PROVIDER_FACT_FIELDS:
            rejection_invariant = "provider_fact_fields"
        elif selected_assertion is None:
            rejection_invariant = "assertion_membership"
        elif (
            not isinstance(provider_confidence, (int, float))
            or isinstance(provider_confidence, bool)
            or not 0 <= provider_confidence <= 1
        ):
            rejection_invariant = "confidence_contract"
        elif (
            not isinstance(returned_ref_ids, list)
            or any(not isinstance(ref_id, str) or not ref_id for ref_id in returned_ref_ids)
            or len(set(returned_ref_ids)) != len(returned_ref_ids)
        ):
            rejection_invariant = "source_reference_ids"
        elif set(returned_ref_ids) - set(registry_by_id):
            rejection_invariant = "source_reference_registry"
        elif set(returned_ref_ids) - set(eligible_source_ids):
            rejection_invariant = "eligible_source_selection"
        elif bool(returned_ref_ids) != bool(eligible_source_ids):
            rejection_invariant = "eligible_source_selection"
        elif len(returned_ref_ids) != len(required_source_artifact_ids):
            rejection_invariant = "eligible_source_selection"
        elif {
            registry_by_id[ref_id]["artifact_id"] for ref_id in returned_ref_ids
        } != required_source_artifact_ids:
            rejection_invariant = "eligible_source_selection"
        elif (
            selected_assertion.get("state") == "conflicting"
            and len(
                {
                    registry_by_id[ref_id]["artifact_id"]
                    for ref_id in returned_ref_ids
                }
            )
            < 2
        ):
            rejection_invariant = "eligible_source_selection"

        if rejection_invariant is None:
            accepted_fact_ids.append(fact_id)
            material = selected_assertion
            fact_refs = [
                {
                    "artifact_id": registry_by_id[ref_id]["artifact_id"],
                    "locator_kind": "text_quote",
                    "page": registry_by_id[ref_id]["page"],
                    "excerpt": registry_by_id[ref_id]["excerpt"],
                    "agent": "OpenRouter Nemotron Canonicalizer",
                }
                for ref_id in returned_ref_ids
            ]
            confidence = provider_confidence
        else:
            rejected_facts.append({"fact_id": fact_id, "invariant": rejection_invariant})
            material = fallback_assertion
            fact_refs = deterministic_text_refs
            confidence = deterministic_confidence
        merged.append(
            {
                "fact_id": fact_id,
                "label": label,
                "value": material["value"],
                "state": material["state"],
                "explanation": material["explanation"],
                "source_refs": [*fact_refs, *enrichments],
                "confidence": confidence,
                "controls_process": controls_process,
                "decision_key": decision_key,
                "normalized_value": material["normalized_value"],
                "decision_value": material["decision_value"],
                "semantic_role": semantic_role,
            }
        )
    diagnostics = {
        "authority_mode": "hybrid_guarded",
        "accepted_fact_ids": accepted_fact_ids,
        "accepted_fact_count": len(accepted_fact_ids),
        "rejected_facts": rejected_facts,
        "rejected_fact_count": len(rejected_facts),
        "source_reference_projection_fact_ids": source_reference_projection_fact_ids,
        "source_reference_projection_count": len(source_reference_projection_fact_ids),
        "deterministic_fallback_applied": False,
        "ignored_noncontrolling_normalized_proposals": (
            ignored_noncontrolling_normalized_proposals
        ),
    }
    if rejected_facts:
        raise ModelResponseError(
            "hybrid_model_contribution invariant failed",
            invariant="hybrid_model_contribution",
            diagnostics=diagnostics,
        )
    return merged, diagnostics


def _validated_hybrid_diagnostics(
    value: Any,
    *,
    allowed_fact_ids: set[str],
) -> dict[str, Any]:
    expected_keys = {
        "authority_mode",
        "accepted_fact_ids",
        "accepted_fact_count",
        "rejected_facts",
        "rejected_fact_count",
        "source_reference_projection_fact_ids",
        "source_reference_projection_count",
        "deterministic_fallback_applied",
        "ignored_noncontrolling_normalized_proposals",
    }
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise ModelConfigurationError("Cached hybrid diagnostics are invalid")
    accepted = value["accepted_fact_ids"]
    rejected = value["rejected_facts"]
    projected = value["source_reference_projection_fact_ids"]
    if (
        value["authority_mode"] != "hybrid_guarded"
        or not isinstance(accepted, list)
        or not accepted
        or any(not isinstance(fact_id, str) or fact_id not in allowed_fact_ids for fact_id in accepted)
        or len(set(accepted)) != len(accepted)
        or value["accepted_fact_count"] != len(accepted)
        or rejected
        or not isinstance(rejected, list)
        or any(
            not isinstance(item, dict)
            or set(item) != {"fact_id", "invariant"}
            or item.get("fact_id") not in allowed_fact_ids
            or not isinstance(item.get("invariant"), str)
            or not item.get("invariant", "").strip()
            for item in rejected
        )
        or len({item["fact_id"] for item in rejected}) != len(rejected)
        or set(accepted) & {item["fact_id"] for item in rejected}
        or set(accepted) | {item["fact_id"] for item in rejected} != allowed_fact_ids
        or value["rejected_fact_count"] != len(rejected)
        or not isinstance(projected, list)
        or any(
            not isinstance(fact_id, str) or fact_id not in accepted
            for fact_id in projected
        )
        or len(set(projected)) != len(projected)
        or value["source_reference_projection_count"] != len(projected)
        or value["deterministic_fallback_applied"] is not False
        or not isinstance(value["ignored_noncontrolling_normalized_proposals"], int)
        or isinstance(value["ignored_noncontrolling_normalized_proposals"], bool)
        or value["ignored_noncontrolling_normalized_proposals"] < 0
    ):
        raise ModelConfigurationError("Cached hybrid diagnostics are invalid")
    return value


def _assertion_selection_receipts(
    *,
    output: dict[str, Any],
    merged_facts: list[dict[str, Any]],
    assertion_catalog: list[dict[str, Any]],
    accepted_fact_ids: list[str],
) -> list[dict[str, Any]]:
    returned = {
        item.get("fact_id"): item
        for item in output.get("facts", [])
        if isinstance(item, dict)
    }
    accepted = set(accepted_fact_ids)
    materialized = {item["fact_id"]: item for item in merged_facts}
    receipts: list[dict[str, Any]] = []
    for slot in assertion_catalog:
        fact_id = slot["fact_id"]
        if fact_id not in accepted or fact_id not in materialized:
            raise ModelConfigurationError(
                "Assertion selection receipts require complete model acceptance"
            )
        assertion_id = returned[fact_id]["assertion_id"]
        receipts.append(
            {
                "fact_id": fact_id,
                "assertion_id": assertion_id,
                "model_owned_fields": (
                    ["assertion_id", "source_ref_ids", "confidence"]
                    if slot["model_selects_meaning"]
                    else ["source_ref_ids", "confidence"]
                ),
                "materialized_fields": [
                    "value",
                    "state",
                    "explanation",
                    "normalized_value",
                    "decision_value",
                ],
                "attribution": "OpenRouter Nemotron Canonicalizer",
                "deterministic_fallback_applied": False,
            }
        )
    return receipts


def _validated_assertion_selection_receipts(
    value: Any, *, allowed_fact_ids: set[str]
) -> list[dict[str, Any]]:
    expected_fields = {
        "fact_id",
        "assertion_id",
        "model_owned_fields",
        "materialized_fields",
        "attribution",
        "deterministic_fallback_applied",
    }
    if (
        not isinstance(value, list)
        or len(value) != len(allowed_fact_ids)
        or {item.get("fact_id") for item in value if isinstance(item, dict)}
        != allowed_fact_ids
        or any(
            not isinstance(item, dict)
            or set(item) != expected_fields
            or not isinstance(item.get("assertion_id"), str)
            or not item["assertion_id"].startswith("assert_")
            or item.get("model_owned_fields")
            not in (
                ["assertion_id", "source_ref_ids", "confidence"],
                ["source_ref_ids", "confidence"],
            )
            or item.get("materialized_fields")
            != [
                "value",
                "state",
                "explanation",
                "normalized_value",
                "decision_value",
            ]
            or item.get("attribution") != "OpenRouter Nemotron Canonicalizer"
            or item.get("deterministic_fallback_applied") is not False
            for item in value
        )
    ):
        raise ModelConfigurationError("Cached assertion selections are invalid")
    return [dict(item) for item in value]


@dataclass
class OpenRouterNemotronCanonicalizer:
    storage: Storage
    # Raw transport is retained only as an injection seam for the existing mocked
    # contract suite. Production uses the shared LangChain ChatOpenRouter adapter.
    transport: Transport | None = None
    structured_invoker: StructuredInvoker = _default_structured_invoker
    metadata_transport: MetadataTransport = _default_metadata_transport
    api_key_provider: Callable[[], str | None] = lambda: os.getenv("OPENROUTER_API_KEY")
    timeout_seconds: float = 180.0
    metadata_timeout_seconds: float = GENERATION_METADATA_TIMEOUT_SECONDS
    metadata_poll_attempts: int = GENERATION_METADATA_POLL_ATTEMPTS
    metadata_poll_interval_seconds: float = GENERATION_METADATA_POLL_INTERVAL_SECONDS
    metadata_sleep: Callable[[float], None] = sleep

    implementation: str = "hybrid_guarded_openrouter_canonicalizer"
    model: str = OPENROUTER_MODEL
    provider: str = OPENROUTER_PROVIDER

    def canonicalize(
        self,
        package: dict[str, Any],
        *,
        run_id: str,
        allowed_fact_catalog: list[dict[str, Any]],
        progress_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        # One worker serves two fixed fixtures. Serializing cache misses prevents
        # concurrent sessions from duplicating the same paid request; the cache is
        # rechecked inside the lock by the delegated implementation.
        with MODEL_SINGLE_FLIGHT_LOCK:
            return self._canonicalize_locked(
                package,
                run_id=run_id,
                allowed_fact_catalog=allowed_fact_catalog,
                progress_sink=progress_sink,
            )

    def _canonicalize_locked(
        self,
        package: dict[str, Any],
        *,
        run_id: str,
        allowed_fact_catalog: list[dict[str, Any]],
        progress_sink: Callable[[dict[str, Any]], None] | None,
    ) -> dict[str, Any]:
        if self.model != OPENROUTER_MODEL:
            raise ModelConfigurationError("OpenRouter canonicalizer must use the configured Nemotron alias")
        if (
            not isinstance(self.metadata_poll_attempts, int)
            or isinstance(self.metadata_poll_attempts, bool)
            or not 1 <= self.metadata_poll_attempts <= GENERATION_METADATA_POLL_ATTEMPTS
            or not isinstance(self.metadata_timeout_seconds, (int, float))
            or isinstance(self.metadata_timeout_seconds, bool)
            or not 0 < self.metadata_timeout_seconds <= GENERATION_METADATA_TIMEOUT_SECONDS
            or not isinstance(self.metadata_poll_interval_seconds, (int, float))
            or isinstance(self.metadata_poll_interval_seconds, bool)
            or not 0 <= self.metadata_poll_interval_seconds <= GENERATION_METADATA_POLL_INTERVAL_SECONDS
        ):
            raise ModelConfigurationError("Generation-metadata polling must remain within its fixed safety bounds")
        fact_ids = _fact_catalog_identity(allowed_fact_catalog)
        package_text = json.dumps(package, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        orchestration_id = f"orch_{sha256(run_id.encode('utf-8')).hexdigest()[:16]}"
        source_reference_registry = observable_source_reference_registry(package)
        registry_text = json.dumps(
            source_reference_registry,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        assertion_catalog = bounded_fact_assertion_catalog(
            allowed_fact_catalog, source_reference_registry
        )
        provider_assertion_catalog = [
            {
                "fact_id": slot["fact_id"],
                "label": slot["label"],
                "assertions": [
                    {"assertion_id": assertion["assertion_id"]}
                    | (
                        {
                            "assertion_label": (
                                f"{slot['label']}: "
                                f"{str(assertion['normalized_value']).replace('_', ' ')}"
                            ),
                            "state": assertion["state"],
                            "normalized_value": assertion["normalized_value"],
                        }
                        if slot["model_selects_meaning"]
                        else {"assertion_label": "source match only"}
                    )
                    for assertion in slot["assertions"]
                ],
                "model_selects_meaning": slot["model_selects_meaning"],
            }
            for slot in assertion_catalog
        ]
        catalog_text = json.dumps(
            provider_assertion_catalog,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        provider_schema = canonical_facts_schema(
            source_reference_registry,
            assertion_catalog,
        )
        system_prompt = CANONICAL_SYSTEM_PROMPT
        cache_key = _cache_key(
            {
                "package": package,
                "bounded_assertion_catalog": provider_assertion_catalog,
            },
            provider_schema=provider_schema,
            system_prompt=system_prompt,
        )
        cached = self.storage.cached_model_output(cache_key)
        if cached is not None:
            diagnostics = _validated_hybrid_diagnostics(
                cached.get("diagnostics"),
                allowed_fact_ids=set(fact_ids),
            )
            assertion_selections = _validated_assertion_selection_receipts(
                cached.get("assertion_selections"),
                allowed_fact_ids=set(fact_ids),
            )
            call_id = self.storage.create_model_call(
                run_id=run_id,
                provider=self.provider,
                model=self.model,
                cache_key=cache_key,
                purpose="observable package to canonical facts",
                call_count=0,
                estimated_cost_usd=0.0,
                outcome="cache_hit",
                provider_endpoint=OPENROUTER_URL,
                implementation=self.implementation,
                orchestration_id=orchestration_id,
                agent_id="canonical_facts",
                agent_role="guarded_canonical_facts",
            )
            origin = cached.get("origin") if isinstance(cached.get("origin"), dict) else {}
            cache_provenance = {
                key: origin[key]
                for key in (
                    "origin_call_id",
                    "response_id",
                    "response_model",
                    "upstream_provider",
                    "origin_usage",
                    "origin_finish_reason",
                )
                if key in origin
            }
            self.storage.finish_model_call(
                call_id,
                outcome="cache_hit",
                **diagnostics,
                **cache_provenance,
                usage_source="cache",
                finish_reason=origin.get("origin_finish_reason"),
            )
            return {
                "facts": cached["facts"],
                "assertion_selections": assertion_selections,
                "diagnostics": diagnostics,
                "authority_mode": "hybrid_guarded",
                "orchestration_id": orchestration_id,
                "agent_id": "canonical_facts",
                "implementation": self.implementation,
                "model": self.model,
                "provider": self.provider,
                "call_id": call_id,
                "cache_key": cache_key,
                "cache_hit": True,
                **cache_provenance,
                "usage_source": "cache",
            }

        user_prompt = (
            f"ASSERTION CATALOG:\n{catalog_text}\n\n"
            f"SOURCE REFERENCE REGISTRY:\n{registry_text}\n\n"
            f"OBSERVABLE CLAIM PACKAGE:\n{package_text}"
        )
        prompt_text = system_prompt + "\n" + user_prompt
        assert_external_tracing_disabled()
        provider_schema_text = json.dumps(
            provider_schema,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        estimated_input_tokens = _input_token_estimate(
            prompt_text + "\n" + provider_schema_text
        )
        estimated_cost_usd = _estimated_cost(estimated_input_tokens)
        cap = cumulative_usd_cap()
        key = self.api_key_provider()
        with self.storage.lock:
            committed = self.storage.model_cost_committed_or_reserved()
            if committed + estimated_cost_usd > cap:
                blocked_call_id = self.storage.create_model_call(
                    run_id=run_id,
                    provider=self.provider,
                    model=self.model,
                    cache_key=cache_key,
                    purpose="observable package to canonical facts",
                    call_count=0,
                    estimated_cost_usd=estimated_cost_usd,
                    outcome="blocked_cost_guard",
                    provider_endpoint=OPENROUTER_URL,
                    implementation=self.implementation,
                    orchestration_id=orchestration_id,
                    agent_id="canonical_facts",
                    agent_role="guarded_canonical_facts",
                )
                self.storage.finish_model_call(
                    blocked_call_id,
                    outcome="blocked_cost_guard",
                    error_type="ModelCostGuardError",
                    error_invariant="cost_guard",
                )
                raise ModelCostGuardError(
                    f"Estimated call cost would exceed the configured cumulative USD cap ({cap:.2f})",
                    safe_context={
                        "call_id": blocked_call_id,
                        "orchestration_id": orchestration_id,
                        "agent_id": "canonical_facts",
                        "outcome": "blocked_cost_guard",
                        "error_invariant": "cost_guard",
                    },
                )
            if not key:
                blocked_call_id = self.storage.create_model_call(
                    run_id=run_id,
                    provider=self.provider,
                    model=self.model,
                    cache_key=cache_key,
                    purpose="observable package to canonical facts",
                    call_count=0,
                    estimated_cost_usd=estimated_cost_usd,
                    outcome="blocked_missing_credential",
                    provider_endpoint=OPENROUTER_URL,
                    implementation=self.implementation,
                    orchestration_id=orchestration_id,
                    agent_id="canonical_facts",
                    agent_role="guarded_canonical_facts",
                )
                self.storage.finish_model_call(
                    blocked_call_id,
                    outcome="blocked_missing_credential",
                    error_type="ModelConfigurationError",
                    error_invariant="missing_credential",
                )
                raise ModelConfigurationError(
                    "OpenRouter model mode requires an API credential",
                    safe_context={
                        "call_id": blocked_call_id,
                        "orchestration_id": orchestration_id,
                        "agent_id": "canonical_facts",
                        "outcome": "blocked_missing_credential",
                        "error_invariant": "missing_credential",
                    },
                )

            call_id = self.storage.create_model_call(
                run_id=run_id,
                provider=self.provider,
                model=self.model,
                cache_key=cache_key,
                purpose="observable package to canonical facts",
                call_count=1,
                estimated_cost_usd=estimated_cost_usd,
                outcome="started",
                provider_endpoint=OPENROUTER_URL,
                implementation=self.implementation,
                orchestration_id=orchestration_id,
                agent_id="canonical_facts",
                agent_role="guarded_canonical_facts",
            )
        if progress_sink is not None:
            progress_sink(
                {
                    "receipt_type": "agent_started",
                    "agent_id": "canonical_facts",
                    "role": "Guarded Canonical Facts Agent",
                    "actor_type": "nemotron_agent",
                    "status": "started",
                    "call_id": call_id,
                    "call_count": 1,
                    "cache_hit": False,
                    "orchestration_id": orchestration_id,
                    "input_artifact": "observable_claim_package",
                    "input_artifact_hash": sha256(
                        package_text.encode("utf-8")
                    ).hexdigest(),
                }
            )
        request_payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "temperature": 0,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "reasoning": dict(CANONICAL_REASONING),
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "casepath_canonical_facts",
                    "strict": True,
                    "schema": provider_schema,
                },
            },
            "provider": openrouter_provider_policy(),
        }
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "X-OpenRouter-Title": "CasePath",
            "X-OpenRouter-Metadata": "enabled",
        }
        started = perf_counter()
        ledger_finished = False
        provider_ledger_patch: dict[str, Any] = {}
        try:
            if self.transport is None:
                response = self.structured_invoker(
                    provider_schema,
                    system_prompt,
                    user_prompt,
                    key,
                    orchestration_id,
                    MAX_OUTPUT_TOKENS,
                )
            else:
                response = self.transport(
                    OPENROUTER_URL,
                    headers,
                    request_payload,
                    self.timeout_seconds,
                )
            latency_ms = round((perf_counter() - started) * 1000, 3)
            identity = _partial_response_identity(response)
            provider_ledger_patch = {"latency_ms": latency_ms}
            if identity["response_id"] is not None:
                provider_ledger_patch["response_id"] = identity["response_id"]
            if identity["response_model"] is not None:
                provider_ledger_patch["response_model"] = identity["response_model"]
            if identity["response_finish_reason"] is not None:
                provider_ledger_patch["finish_reason"] = identity["response_finish_reason"]
            if identity["provenance_violation"] is not None:
                provider_ledger_patch.update(identity["provenance_violation"])
            synchronous_usage = _synchronous_usage_ledger_patch(
                response,
                identity=identity,
                latency_ms=latency_ms,
            )
            if synchronous_usage is not None:
                provider_ledger_patch.update(synchronous_usage)
            needs_metadata = synchronous_usage is None or (
                identity["provenance_violation"] is None
                and (
                    identity.get("response_finish_reason") is None
                    or identity.get("upstream_provider") is None
                )
            )
            if needs_metadata and identity["response_id"] is not None:
                metadata_patch = _generation_metadata_ledger_patch(
                    identity=identity,
                    headers=headers,
                    metadata_transport=self.metadata_transport,
                    metadata_sleep=self.metadata_sleep,
                    timeout_seconds=self.metadata_timeout_seconds,
                    poll_attempts=self.metadata_poll_attempts,
                    poll_interval_seconds=self.metadata_poll_interval_seconds,
                    latency_ms=latency_ms,
                )
                provider_ledger_patch.update(metadata_patch)
                if identity["response_finish_reason"] is not None:
                    provider_ledger_patch["finish_reason"] = identity[
                        "response_finish_reason"
                    ]
            if "actual_cost_usd" in provider_ledger_patch:
                with self.storage.lock:
                    self.storage.finish_model_call(
                        call_id,
                        outcome="provider_succeeded",
                        **provider_ledger_patch,
                    )
                    actual_overrun = self.storage.model_actual_cost_total() > cap
            else:
                actual_overrun = False
            _validate_response_identity(identity)
            if (
                provider_ledger_patch.get("generation_model") is not None
                and provider_ledger_patch["generation_model"]
                not in OPENROUTER_ACCEPTED_RESPONSE_MODELS
            ):
                raise ModelResponseError(
                    "generation_metadata_model invariant failed",
                    invariant="generation_metadata_model",
                )
            if "actual_cost_usd" not in provider_ledger_patch:
                raise ModelResponseError(
                    "generation_metadata_completeness invariant failed",
                    invariant="generation_metadata_completeness",
                )
            if (
                provider_ledger_patch.get("upstream_provider")
                != OPENROUTER_EXPECTED_UPSTREAM_PROVIDER
            ):
                raise ModelResponseError(
                    "upstream_provider_policy invariant failed",
                    invariant="upstream_provider_policy",
                )
            if provider_ledger_patch.get("finish_reason") != "stop":
                raise ModelResponseError(
                    "provider_finish_reason invariant failed",
                    invariant="provider_finish_reason",
                )
            output = _normalize_canonical_facts_response(
                _response_content(response),
                fact_ids=fact_ids,
                provider_schema=provider_schema,
            )
            merged_facts, diagnostics = _merge_fact_contracts(
                output,
                allowed_fact_catalog,
                source_reference_registry,
                assertion_catalog,
            )
            assertion_selections = _assertion_selection_receipts(
                output=output,
                merged_facts=merged_facts,
                assertion_catalog=assertion_catalog,
                accepted_fact_ids=diagnostics["accepted_fact_ids"],
            )
            understanding = {"facts": merged_facts}
            validate_claim_state(
                understanding,
                allowed_artifact_ids={item["artifact_id"] for item in package["artifacts"]},
                artifact_page_counts={item["artifact_id"]: item["page_count"] for item in package["artifacts"]},
                artifact_media_types={item["artifact_id"]: item["media_type"] for item in package["artifacts"]},
            )
            validate_exact_source_excerpts(package, merged_facts)
            with self.storage.lock:
                self.storage.finish_model_call(
                    call_id,
                    outcome="actual_cost_overrun" if actual_overrun else "succeeded",
                    **provider_ledger_patch,
                    **diagnostics,
                    canonical_output={
                        "facts": merged_facts,
                        "diagnostics": diagnostics,
                        "assertion_selections": assertion_selections,
                        "origin": {
                            "origin_call_id": call_id,
                            "response_id": provider_ledger_patch["response_id"],
                            "response_model": provider_ledger_patch["response_model"],
                            "upstream_provider": provider_ledger_patch["upstream_provider"],
                            "usage_source": provider_ledger_patch["usage_source"],
                            "origin_finish_reason": provider_ledger_patch["finish_reason"],
                            "origin_usage": {
                                "prompt_tokens": provider_ledger_patch["prompt_tokens"],
                                "completion_tokens": provider_ledger_patch["completion_tokens"],
                                "total_tokens": provider_ledger_patch["total_tokens"],
                                "actual_cost_usd": provider_ledger_patch["actual_cost_usd"],
                                "usage_source": provider_ledger_patch["usage_source"],
                            },
                        },
                    },
                )
            ledger_finished = True
            if actual_overrun:
                raise ModelCostGuardError(
                    "Actual model cost exceeded the configured cumulative USD cap",
                    safe_context={
                        "call_id": call_id,
                        "orchestration_id": orchestration_id,
                        "agent_id": "canonical_facts",
                        "outcome": "actual_cost_overrun",
                        "error_invariant": "actual_cost_overrun",
                        **{
                            key: provider_ledger_patch[key]
                            for key in (
                                "response_id",
                                "response_model",
                                "upstream_provider",
                                "usage_source",
                                "finish_reason",
                            )
                        },
                    },
                )
            return {
                "facts": merged_facts,
                "assertion_selections": assertion_selections,
                "diagnostics": diagnostics,
                "authority_mode": "hybrid_guarded",
                "orchestration_id": orchestration_id,
                "agent_id": "canonical_facts",
                "implementation": self.implementation,
                "model": self.model,
                "provider": self.provider,
                "call_id": call_id,
                "cache_key": cache_key,
                "cache_hit": False,
                "origin_call_id": call_id,
                "response_id": provider_ledger_patch["response_id"],
                "response_model": provider_ledger_patch["response_model"],
                "upstream_provider": provider_ledger_patch["upstream_provider"],
                "usage_source": provider_ledger_patch["usage_source"],
                "finish_reason": provider_ledger_patch["finish_reason"],
                "usage": {
                    "prompt_tokens": provider_ledger_patch["prompt_tokens"],
                    "completion_tokens": provider_ledger_patch["completion_tokens"],
                    "total_tokens": provider_ledger_patch["total_tokens"],
                    "actual_cost_usd": provider_ledger_patch["actual_cost_usd"],
                    "usage_source": provider_ledger_patch["usage_source"],
                },
            }
        except Exception as exc:
            latency_ms = round((perf_counter() - started) * 1000, 3)
            if isinstance(exc, CanonicalizerError):
                for key in (
                    "latency_ms",
                    "metadata_latency_ms",
                    "metadata_poll_count",
                    "prompt_tokens",
                    "completion_tokens",
                    "total_tokens",
                    "actual_cost_usd",
                    "usage_source",
                    "response_id",
                    "response_model",
                    "upstream_provider",
                    "finish_reason",
                    "invalid_provenance_field",
                    "invalid_provenance_value_hash",
                    "provider_error_code",
                    "provider_boundary",
                    "expected_upstream_provider",
                ):
                    if key in exc.safe_context:
                        provider_ledger_patch[key] = exc.safe_context[key]
            if not ledger_finished:
                concurrency_blocked = (
                    isinstance(exc, ModelResponseError)
                    and exc.invariant == "provider_concurrency_timeout"
                )
                failure_patch = {
                    **provider_ledger_patch,
                    "latency_ms": provider_ledger_patch.get("latency_ms", latency_ms),
                    "error_type": type(exc).__name__,
                }
                if concurrency_blocked:
                    failure_patch["call_count"] = 0
                if isinstance(exc, ModelResponseError):
                    if exc.fact_id is not None:
                        failure_patch["error_fact_id"] = exc.fact_id
                    if exc.invariant is not None:
                        failure_patch["error_invariant"] = exc.invariant
                    if exc.diagnostics is not None:
                        failure_patch.update(exc.diagnostics)
                self.storage.finish_model_call(
                    call_id,
                    outcome=(
                        "blocked_provider_concurrency"
                        if concurrency_blocked
                        else "failed"
                    ),
                    **failure_patch,
                )
            if isinstance(exc, CanonicalizerError):
                exc.safe_context = {
                    "call_id": call_id,
                    "orchestration_id": orchestration_id,
                    "agent_id": "canonical_facts",
                    "outcome": exc.safe_context.get("outcome", "failed"),
                    **{
                        key: provider_ledger_patch[key]
                        for key in (
                            "response_id",
                            "response_model",
                            "upstream_provider",
                            "usage_source",
                            "finish_reason",
                            "invalid_provenance_field",
                            "invalid_provenance_value_hash",
                            "provider_error_code",
                            "provider_boundary",
                            "expected_upstream_provider",
                        )
                        if key in provider_ledger_patch
                    },
                    **exc.safe_context,
                }
                raise
            raise ModelResponseError(
                "OpenRouter canonicalization failed",
                safe_context={
                    "call_id": call_id,
                    "orchestration_id": orchestration_id,
                    "agent_id": "canonical_facts",
                    "outcome": "failed",
                },
            ) from None
