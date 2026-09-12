from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import time

import httpx
from openrouter import OpenRouter, components
from openrouter.utils.unmarshal_json_response import unmarshal_json_response
import pytest

from casepath_api import canonicalizer as canonicalizer_module
from casepath_api import langchain_runtime
from casepath_api.canonicalizer import (
    DEFAULT_CUMULATIVE_USD_CAP,
    MODEL_MODE_REFERENCE,
    OPENROUTER_CANONICAL_MODEL,
    OPENROUTER_GENERATION_URL,
    OPENROUTER_MODEL,
    OPENROUTER_URL,
    ModelConfigurationError,
    ModelCostGuardError,
    ModelResponseError,
    OpenRouterNemotronCanonicalizer,
    bounded_fact_assertion_catalog,
    configured_model_mode,
    cumulative_usd_cap,
    observable_source_reference_registry,
    resolve_observable_source_reference_id,
    source_reference_id,
    validate_exact_source_excerpts,
)
from casepath_api.data import CLAIMS
from casepath_api.pipeline_v15 import ClaimPipeline
from casepath_api.storage import Storage
from casepath_api.visual_annotations import visual_annotation_ref


def package() -> dict:
    return {
        "schema": "casepath.observable-claim-package/1.0.0",
        "received_at": "2026-08-01T09:03:00Z",
        "language": "en",
        "jurisdiction": {"country": "CH", "canton": "BS"},
        "intake_metadata": {"policy_reference": "POL-TEST"},
        "customer_message": {
            "artifact_id": "message",
            "subject": "Observable subject",
            "body": "The tenant reports a recurring mark.",
        },
        "artifacts": [
            {
                "artifact_id": "observable_email",
                "filename": "source.eml",
                "media_type": "message/rfc822",
                "received_at": "2026-08-01T09:03:00Z",
                "page_count": 1,
                "sha256": "0" * 64,
                "parsed_email": {"body": "The tenant reports a recurring mark."},
            }
        ],
    }


def text_reference(
    *,
    artifact_id: str = "message",
    page: int = 1,
    excerpt: str = "reports a recurring mark",
) -> dict:
    return {"artifact_id": artifact_id, "page": page, "excerpt": excerpt}


def observable_ref_id(value: dict, ref: dict | None = None) -> str:
    return resolve_observable_source_reference_id(
        ref or text_reference(),
        observable_source_reference_registry(value),
    )


def grounded_fact(*, ref: dict | None = None) -> dict:
    source = ref or text_reference()
    return {
        "fact_id": "fact_report",
        "label": "Reported condition",
        "state": "known",
        "source_refs": [
            {
                **source,
                "locator_kind": "text_quote",
                "agent": "OpenRouter Nemotron Canonicalizer",
            }
        ],
        "confidence": 0.9,
        "normalized_value": "supported",
    }


def response(*, model: str = OPENROUTER_MODEL, cost: float = 0.0042) -> dict:
    assertion = next(
        item
        for item in bounded_fact_assertion_catalog(
            catalog(), observable_source_reference_registry(package())
        )[0]["assertions"]
        if item["normalized_value"] == "supported"
    )
    output = {
        "facts": {
            "fact_report": {
                "fact_id": "fact_report",
                "assertion_id": assertion["assertion_id"],
                "source_ref_ids": {"message": observable_ref_id(package())},
                "confidence": 0.9,
            }
        }
    }
    return {
        "id": "generation-test-1",
        "model": model,
        "provider": "Together",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(output)},
            }
        ],
        "usage": {
            "prompt_tokens": 123,
            "completion_tokens": 45,
            "total_tokens": 168,
            "cost": cost,
            "cost_details": {"upstream_inference_cost": cost},
        },
        "openrouter_metadata": {"provider_name": "Together"},
    }


def generation_metadata(
    *,
    generation_id: str = "generation-test-1",
    model: str = OPENROUTER_CANONICAL_MODEL,
    cost: float = 0.0057,
    prompt_tokens: int = 321,
    completion_tokens: int = 87,
) -> dict:
    return {
        "data": {
            "id": generation_id,
            "model": model,
            "provider_name": "Together",
            "native_tokens_prompt": prompt_tokens,
            "native_tokens_completion": completion_tokens,
            "total_cost": cost,
            "usage": cost,
            "finish_reason": "stop",
        }
    }


def catalog(*, bounded_enrichments: list[dict] | None = None) -> list[dict]:
    return [
        {
            "fact_id": "fact_report",
            "label": "Reported condition",
            "controls_process": True,
            "decision_key": "recurrence",
            "normalized_options": {
                "supported": "recurrence_supported",
                "not_supported": "recurrence_not_supported",
                "unverified": "recurrence_unverified",
            },
            "admissible_normalized_values": ["supported"],
            "expected_state": "known",
            "canonical_value": "Recurring mark reported",
            "canonical_explanation": "The message directly reports recurrence.",
            "semantic_role": None,
            "deterministic_confidence": 0.82,
            "admissible_text_refs": [
                text_reference()
            ],
            "deterministic_text_refs": [
                {
                    **text_reference(),
                    "locator_kind": "text_quote",
                    "agent": "Deterministic Reference Oracle",
                }
            ],
            "bounded_enrichments": bounded_enrichments or [],
        }
    ]


def set_contract_text_refs(contract: dict, refs: list[dict]) -> None:
    contract["admissible_text_refs"] = refs
    contract["deterministic_text_refs"] = [
        {
            **ref,
            "locator_kind": "text_quote",
            "agent": "Deterministic Reference Oracle",
        }
        for ref in refs
    ]


def assertion_catalog_for(contracts: list[dict]) -> list[dict]:
    return bounded_fact_assertion_catalog(
        contracts, observable_source_reference_registry(package())
    )


def reference_assertion_for(contract: dict) -> dict:
    slot = assertion_catalog_for([contract])[0]
    expected_normalized = (
        contract["admissible_normalized_values"][0]
        if contract["controls_process"]
        else None
    )
    return next(
        item
        for item in slot["assertions"]
        if item["normalized_value"] == expected_normalized
        and item["value"] == contract["canonical_value"]
    )


def three_fact_catalog() -> list[dict]:
    first = catalog()[0]
    second = deepcopy(first)
    second.update(
        {
            "fact_id": "fact_context",
            "label": "Context detail",
            "controls_process": False,
            "decision_key": None,
            "normalized_options": {},
            "admissible_normalized_values": [],
            "canonical_value": "Context reported",
            "canonical_explanation": "The message contains the bounded context.",
            "deterministic_confidence": 0.71,
        }
    )
    third = deepcopy(second)
    third.update(
        {
            "fact_id": "fact_background",
            "label": "Background detail",
            "canonical_value": "Background reported",
            "canonical_explanation": "The message contains the bounded background.",
            "deterministic_confidence": 0.72,
        }
    )
    return [first, second, third]


def assert_zero_accepted_rejection(storage: Storage, invariant: str) -> None:
    entry = storage.model_calls()[0]
    assert entry["outcome"] == "failed"
    assert entry["error_invariant"] == "hybrid_model_contribution"
    assert entry["authority_mode"] == "hybrid_guarded"
    assert entry["accepted_fact_ids"] == []
    assert entry["accepted_fact_count"] == 0
    assert entry["rejected_facts"] == [{"fact_id": "fact_report", "invariant": invariant}]
    assert entry["rejected_fact_count"] == 1


def assert_provider_schema_rejection(storage: Storage) -> None:
    entry = storage.model_calls()[0]
    assert entry["outcome"] == "failed"
    assert entry["error_invariant"] == "provider_native_schema"
    assert entry["call_count"] == 1


def test_model_call_summary_marks_only_network_rows_with_unknown_cost(tmp_path: Path):
    storage = Storage(str(tmp_path / "summary.db"))
    assert storage.model_call_summary()["actual_cost_complete"] is True
    assert storage.model_call_summary()["unknown_cost_call_count"] == 0

    for outcome in ("blocked_cost_guard", "cache_hit"):
        storage.create_model_call(
            run_id=None,
            provider="openrouter",
            model=OPENROUTER_MODEL,
            cache_key=f"cache-{outcome}",
            purpose="summary fixture",
            call_count=0,
            estimated_cost_usd=0,
            outcome=outcome,
        )
    known_call = storage.create_model_call(
        run_id=None,
        provider="openrouter",
        model=OPENROUTER_MODEL,
        cache_key="cache-known",
        purpose="summary fixture",
        call_count=1,
        estimated_cost_usd=0.01,
        outcome="started",
    )
    storage.finish_model_call(known_call, outcome="succeeded", actual_cost_usd=0.004)
    storage.create_model_call(
        run_id=None,
        provider="openrouter",
        model=OPENROUTER_MODEL,
        cache_key="cache-unknown",
        purpose="summary fixture",
        call_count=1,
        estimated_cost_usd=0.01,
        outcome="failed",
    )

    summary = storage.model_call_summary()
    assert summary["network_calls"] == 2
    assert summary["actual_cost_usd"] == pytest.approx(0.004)
    assert summary["actual_cost_complete"] is False
    assert summary["unknown_cost_call_count"] == 1


def test_openrouter_request_is_one_bounded_exact_model_structured_call(tmp_path: Path):
    storage = Storage(str(tmp_path / "ledger.db"))
    calls: list[tuple] = []
    metadata_calls = 0

    def transport(url, headers, payload, timeout):
        calls.append((url, headers, payload, timeout))
        return response()

    def forbidden_metadata_transport(*_args):
        nonlocal metadata_calls
        metadata_calls += 1
        raise AssertionError("usage-present response must not query generation metadata")

    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=transport,
        metadata_transport=forbidden_metadata_transport,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    result = canonicalizer.canonicalize(
        package(),
        run_id="run_test",
        allowed_fact_catalog=catalog(),
    )
    assert result["model"] == "nvidia/nemotron-3-ultra-550b-a55b"
    assert result["implementation"] == "hybrid_guarded_openrouter_canonicalizer"
    assert result["authority_mode"] == "hybrid_guarded"
    assert result["agent_id"] == "canonical_facts"
    assert result["orchestration_id"].startswith("orch_")
    assert result["diagnostics"] == {
        "authority_mode": "hybrid_guarded",
        "accepted_fact_ids": ["fact_report"],
        "accepted_fact_count": 1,
        "rejected_facts": [],
        "rejected_fact_count": 0,
        "source_reference_projection_fact_ids": [],
        "source_reference_projection_count": 0,
        "deterministic_fallback_applied": False,
        "ignored_noncontrolling_normalized_proposals": 0,
    }
    assert result["cache_hit"] is False
    assert len(calls) == 1
    assert metadata_calls == 0
    url, headers, request, timeout = calls[0]
    assert url == "https://openrouter.ai/api/v1/chat/completions"
    assert timeout == 180.0
    assert headers["X-OpenRouter-Metadata"] == "enabled"
    assert request["model"] == OPENROUTER_MODEL
    assert "models" not in request
    assert request["max_tokens"] == 8192
    assert request["reasoning"] == {"effort": "none"}
    assert request["stream"] is False
    assert request["response_format"]["type"] == "json_schema"
    assert request["response_format"]["json_schema"]["strict"] is True
    facts_schema = request["response_format"]["json_schema"]["schema"]["properties"]["facts"]
    fact_schema = facts_schema["properties"]["fact_report"]
    assert set(fact_schema["properties"]) == {
        "fact_id",
        "assertion_id",
        "source_ref_ids",
        "confidence",
    }
    assert fact_schema["required"] == [
        "assertion_id",
        "confidence",
        "fact_id",
        "source_ref_ids",
    ]
    assert fact_schema["additionalProperties"] is False
    assert facts_schema["type"] == "object"
    assert facts_schema["required"] == ["fact_report"]
    assert facts_schema["additionalProperties"] is False
    assert fact_schema["properties"]["fact_id"]["enum"] == ["fact_report"]
    expected_source_pool = [
        item
        for item in observable_source_reference_registry(package())
        if item["artifact_id"] == "message"
    ]
    assert len(expected_source_pool) > 1
    source_ref_schema = fact_schema["properties"]["source_ref_ids"]
    assert source_ref_schema["type"] == "object"
    assert source_ref_schema["required"] == ["message"]
    assert source_ref_schema["additionalProperties"] is False
    assert source_ref_schema["properties"]["message"]["enum"] == sorted(
        item["source_ref_id"] for item in expected_source_pool
    )
    serialized_schema = json.dumps(
        request["response_format"]["json_schema"]["schema"],
        sort_keys=True,
    )
    for unsupported_keyword in (
        '"uniqueItems"',
        '"oneOf"',
        '"const"',
        '"prefixItems"',
    ):
        assert unsupported_keyword not in serialized_schema
    registry_ids = source_ref_schema["properties"]["message"]["enum"]
    assert observable_ref_id(package()) in registry_ids
    assert len(registry_ids) > 1
    assert request["provider"] == {
        "only": ["together"],
        "allow_fallbacks": False,
        "require_parameters": True,
        "data_collection": "deny",
    }
    assert "usage" not in request
    user_prompt = request["messages"][1]["content"]
    for private_field in (
        "controls_process",
        "decision_key",
        "normalized_options",
        "admissible_normalized_values",
        "expected_state",
        "canonical_value",
        "canonical_explanation",
        "admissible_text_refs",
        "required_source_ref_ids",
        "recurrence_supported",
    ):
        assert private_field not in user_prompt
    assert "required_text_reference_count" not in user_prompt
    assert "SOURCE REFERENCE REGISTRY:" in user_prompt
    assert observable_ref_id(package()) in user_prompt
    assert '"artifact_id":"message"' in user_prompt
    assert '"excerpt":"The tenant reports a recurring mark."' in user_prompt
    system_prompt = request["messages"][0]["content"]
    assert "required_text_reference_count" not in system_prompt
    assert "fixed source_ref_ids object names one required artifact" in system_prompt
    assert "Select exactly one source-reference ID from that property's enum" in system_prompt
    assert "application exclusively materializes labels, canonical states" in system_prompt
    assert "does not identify a preferred or expected answer" in system_prompt
    assert "bounded_assertion_catalog" not in user_prompt
    assert "ASSERTION CATALOG:" in user_prompt
    assert '"eligible_source_ref_ids":' not in user_prompt
    visible_catalog = json.loads(
        user_prompt.split("ASSERTION CATALOG:\n", 1)[1].split(
            "\n\nSOURCE REFERENCE REGISTRY:", 1
        )[0]
    )
    assert set(visible_catalog[0]) == {
        "assertions",
        "fact_id",
        "label",
        "model_selects_meaning",
    }
    assert result["facts"][0]["controls_process"] is True
    assert result["facts"][0]["decision_key"] == "recurrence"
    assert result["facts"][0]["decision_value"] == "recurrence_supported"
    assert result["facts"][0]["value"] == "Recurring mark reported"
    assert result["facts"][0]["explanation"] == "The message directly reports recurrence."
    assert result["facts"][0]["source_refs"] == [
        {
            "artifact_id": "message",
            "locator_kind": "text_quote",
            "page": 1,
                "excerpt": "The tenant reports a recurring mark.",
            "agent": "OpenRouter Nemotron Canonicalizer",
        }
    ]

    ledger = storage.model_calls()
    assert len(ledger) == 1
    entry = ledger[0]
    assert entry["provider"] == "openrouter"
    assert entry["provider_endpoint"] == OPENROUTER_URL
    assert entry["model"] == OPENROUTER_MODEL
    assert entry["implementation"] == "hybrid_guarded_openrouter_canonicalizer"
    assert entry["agent_id"] == "canonical_facts"
    assert entry["agent_role"] == "guarded_canonical_facts"
    assert entry["orchestration_id"] == result["orchestration_id"]
    assert entry["parent_call_id"] is None
    assert entry["call_count"] == 1
    assert entry["prompt_tokens"] == 123
    assert entry["completion_tokens"] == 45
    assert entry["total_tokens"] == 168
    assert entry["actual_cost_usd"] == pytest.approx(0.0042)
    assert entry["usage_source"] == "response"
    assert entry["latency_ms"] >= 0
    assert entry["cache_key"] == result["cache_key"]
    assert entry["purpose"] == "observable package to canonical facts"
    assert entry["outcome"] == "succeeded"
    assert entry["authority_mode"] == "hybrid_guarded"
    assert entry["accepted_fact_ids"] == ["fact_report"]
    assert entry["accepted_fact_count"] == 1
    assert entry["rejected_facts"] == []
    assert entry["rejected_fact_count"] == 0
    assert entry["upstream_provider"] == "Together"
    assert entry["model"] == OPENROUTER_MODEL
    assert entry["response_model"] == OPENROUTER_MODEL
    assert entry["response_id"] == "generation-test-1"
    assert "cost_details" not in json.dumps(entry)
    assert "openrouter_metadata" not in json.dumps(entry)
    assert "runtime-only-test-value" not in json.dumps(entry)


def test_source_ref_schema_ceiling_is_derived_from_required_artifact_groups(
    tmp_path: Path,
    monkeypatch,
):
    observable = package()
    observable["customer_message"]["body"] = (
        "First reported passage. Another message passage."
    )
    observable["artifacts"][0]["parsed_email"]["body"] = (
        "Second reported passage. Another email passage."
    )
    contract = catalog()[0]
    set_contract_text_refs(
        contract,
        [
            text_reference(excerpt="First reported passage."),
            text_reference(
                artifact_id="observable_email",
                excerpt="Second reported passage.",
            ),
        ],
    )
    captured_schemas: list[dict] = []
    original = canonicalizer_module.canonical_facts_schema

    def capture_schema(*args, **kwargs):
        schema = original(*args, **kwargs)
        captured_schemas.append(schema)
        return schema

    monkeypatch.setattr(
        canonicalizer_module,
        "canonical_facts_schema",
        capture_schema,
    )
    canonicalizer = OpenRouterNemotronCanonicalizer(
        Storage(str(tmp_path / "source-ref-ceiling.db")),
        api_key_provider=lambda: None,
    )
    with pytest.raises(ModelConfigurationError, match="requires an API credential"):
        canonicalizer.canonicalize(
            observable,
            run_id="run-source-ref-ceiling",
            allowed_fact_catalog=[contract],
        )

    assert len(captured_schemas) == 1
    source_refs = captured_schemas[0]["properties"]["facts"]["properties"][
        "fact_report"
    ]["properties"]["source_ref_ids"]
    eligible_pool = [
        item
        for item in observable_source_reference_registry(observable)
        if item["artifact_id"] in {"message", "observable_email"}
    ]
    assert len(eligible_pool) > 2
    assert source_refs["required"] == ["message", "observable_email"]
    assert set(source_refs["properties"]) == {"message", "observable_email"}
    for artifact_id in source_refs["required"]:
        assert source_refs["properties"][artifact_id]["enum"] == sorted(
            item["source_ref_id"]
            for item in eligible_pool
            if item["artifact_id"] == artifact_id
        )


def test_flagship_wire_schema_binds_every_fact_and_artifact_slot(tmp_path: Path):
    captured: dict[str, object] = {}

    class CapturingCanonicalizer:
        def canonicalize(
            self,
            observable_package,
            *,
            run_id,
            allowed_fact_catalog,
            progress_sink,
        ):
            captured["package"] = observable_package
            captured["catalog"] = allowed_fact_catalog
            raise ModelConfigurationError("flagship catalog captured")

    storage = Storage(str(tmp_path / "flagship-schema.db"))
    run_id = storage.create_run("DEF-027-E0-DEMO")
    pipeline = ClaimPipeline(
        storage,
        model_mode="openrouter_nemotron",
        canonicalizer=CapturingCanonicalizer(),
        agent_orchestrator=object(),
        pace_seconds=0,
    )
    with pytest.raises(ModelConfigurationError, match="flagship catalog captured"):
        pipeline._understand_stage(
            run_id,
            CLAIMS["DEF-027-E0-DEMO"],
            {"input_hash": "0" * 64},
        )

    observable = captured["package"]
    contracts = captured["catalog"]
    assert isinstance(observable, dict)
    assert isinstance(contracts, list)
    registry = observable_source_reference_registry(observable)
    assertion_catalog = bounded_fact_assertion_catalog(contracts, registry)
    schema = canonicalizer_module.canonical_facts_schema(
        registry,
        assertion_catalog,
    )
    facts_schema = schema["properties"]["facts"]
    expected_fact_ids = [contract["fact_id"] for contract in contracts]
    assert expected_fact_ids == [
        "fact_tenancy",
        "fact_policy_route",
        "fact_dispute",
        "fact_recurrence",
        "fact_notification",
        "fact_ventilation_allegation",
        "fact_cause",
        "fact_health",
        "fact_date_conflict",
        "fact_source_integrity",
        "fact_customer_objective",
        "fact_repair_history",
        "fact_tenant_use_cause",
        "fact_remedy_plan",
        "fact_financial_remedy",
        "fact_settlement_proposal",
        "fact_escalation_ready",
        "fact_resolution_complete",
    ]
    assert facts_schema["required"] == expected_fact_ids
    assert set(facts_schema["properties"]) == set(expected_fact_ids)
    slots_by_id = {slot["fact_id"]: slot for slot in assertion_catalog}
    registry_by_id = {item["source_ref_id"]: item for item in registry}

    for fact_id in expected_fact_ids:
        fact_schema = facts_schema["properties"][fact_id]
        slot = slots_by_id[fact_id]
        assert fact_schema["properties"]["fact_id"]["enum"] == [fact_id]
        assert fact_schema["properties"]["assertion_id"]["enum"] == [
            assertion["assertion_id"] for assertion in slot["assertions"]
        ]
        source_schema = fact_schema["properties"]["source_ref_ids"]
        expected_artifacts = sorted(
            {
                registry_by_id[ref_id]["artifact_id"]
                for ref_id in slot["eligible_source_ref_ids"]
            }
        )
        assert source_schema["required"] == expected_artifacts
        assert set(source_schema["properties"]) == set(expected_artifacts)
        for artifact_id in expected_artifacts:
            assert source_schema["properties"][artifact_id]["enum"] == sorted(
                ref_id
                for ref_id in slot["eligible_source_ref_ids"]
                if registry_by_id[ref_id]["artifact_id"] == artifact_id
            )

    assert set(
        facts_schema["properties"]["fact_dispute"]["properties"][
            "source_ref_ids"
        ]["properties"]
    ) == {"message", "art_management_reply"}
    assert set(
        facts_schema["properties"]["fact_notification"]["properties"][
            "source_ref_ids"
        ]["properties"]
    ) == {"art_notification", "art_delivery"}
    assert facts_schema["properties"]["fact_remedy_plan"]["properties"][
        "source_ref_ids"
    ] == {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }

    unsupported_keywords = {"uniqueItems", "oneOf", "const", "prefixItems"}

    def schema_keys(value):
        if isinstance(value, dict):
            for key, child in value.items():
                yield key
                yield from schema_keys(child)
        elif isinstance(value, list):
            for child in value:
                yield from schema_keys(child)

    assert unsupported_keywords.isdisjoint(set(schema_keys(schema)))

    message_ref_id = next(
        item["source_ref_id"] for item in registry if item["artifact_id"] == "message"
    )
    timeline_ref_id = next(
        item["source_ref_id"]
        for item in registry
        if item["artifact_id"] == "art_timeline"
    )
    reused_pair = {"message": message_ref_id, "art_timeline": timeline_ref_id}
    invalid_wire = {
        "facts": {
            fact_id: {
                "fact_id": fact_id,
                "assertion_id": slots_by_id[fact_id]["assertions"][0]["assertion_id"],
                "source_ref_ids": (
                    dict(reused_pair)
                    if slots_by_id[fact_id]["eligible_source_ref_ids"]
                    else {}
                ),
                "confidence": 0.8,
            }
            for fact_id in expected_fact_ids
        }
    }
    with pytest.raises(ModelResponseError, match="provider_native_schema"):
        canonicalizer_module._normalize_canonical_facts_response(
            invalid_wire,
            fact_ids=expected_fact_ids,
            provider_schema=schema,
        )


def test_canonical_cost_preflight_includes_serialized_provider_schema(
    tmp_path: Path,
    monkeypatch,
):
    estimated_inputs: list[str] = []
    original = canonicalizer_module._input_token_estimate

    def capture_estimate(value: str) -> int:
        estimated_inputs.append(value)
        return original(value)

    monkeypatch.setattr(
        canonicalizer_module,
        "_input_token_estimate",
        capture_estimate,
    )
    canonicalizer = OpenRouterNemotronCanonicalizer(
        Storage(str(tmp_path / "schema-cost.db")),
        transport=lambda *_args: response(),
        api_key_provider=lambda: "runtime-only-test-value",
    )
    canonicalizer.canonicalize(
        package(),
        run_id="run-schema-cost",
        allowed_fact_catalog=catalog(),
    )

    assert len(estimated_inputs) == 1
    assert '"fact_report":' in estimated_inputs[0]
    assert '"message":{"enum":' in estimated_inputs[0]
    assert '"additionalProperties":false' in estimated_inputs[0]


def test_valid_alternate_controlling_assertion_materializes_a_different_fact_state():
    contracts = catalog()
    assertion_catalog = assertion_catalog_for(contracts)
    alternate = next(
        assertion
        for assertion in assertion_catalog[0]["assertions"]
        if assertion["normalized_value"] == "unverified"
    )
    output = {
        "facts": [
            {
                "fact_id": "fact_report",
                "assertion_id": alternate["assertion_id"],
                "source_ref_ids": [observable_ref_id(package())],
                "confidence": 0.63,
            }
        ]
    }

    facts, diagnostics = canonicalizer_module._merge_fact_contracts(
        output,
        contracts,
        observable_source_reference_registry(package()),
        assertion_catalog,
    )
    receipts = canonicalizer_module._assertion_selection_receipts(
        output=output,
        merged_facts=facts,
        assertion_catalog=assertion_catalog,
        accepted_fact_ids=diagnostics["accepted_fact_ids"],
    )

    assert diagnostics["accepted_fact_ids"] == ["fact_report"]
    assert diagnostics["deterministic_fallback_applied"] is False
    assert facts[0]["state"] == "unknown"
    assert facts[0]["normalized_value"] == "unverified"
    assert facts[0]["decision_value"] == "recurrence_unverified"
    assert facts[0]["value"] != contracts[0]["canonical_value"]
    assert facts[0]["confidence"] == 0.63
    assert receipts == [
        {
            "fact_id": "fact_report",
            "assertion_id": alternate["assertion_id"],
            "model_owned_fields": [
                "assertion_id",
                "source_ref_ids",
                "confidence",
            ],
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
    ]


def test_cross_slot_assertion_identifier_fails_closed():
    contract = catalog()[0]
    other = deepcopy(contract)
    other["fact_id"] = "fact_other"
    foreign_assertion_id = reference_assertion_for(other)["assertion_id"]
    assertion_catalog = assertion_catalog_for([contract])

    with pytest.raises(ModelResponseError, match="hybrid_model_contribution") as caught:
        canonicalizer_module._merge_fact_contracts(
            {
                "facts": [
                    {
                        "fact_id": contract["fact_id"],
                        "assertion_id": foreign_assertion_id,
                        "source_ref_ids": [observable_ref_id(package())],
                        "confidence": 0.9,
                    }
                ]
            },
            [contract],
            observable_source_reference_registry(package()),
            assertion_catalog,
        )

    assert caught.value.diagnostics == {
        "authority_mode": "hybrid_guarded",
        "accepted_fact_ids": [],
        "accepted_fact_count": 0,
        "rejected_facts": [
            {"fact_id": "fact_report", "invariant": "assertion_membership"}
        ],
        "rejected_fact_count": 1,
        "source_reference_projection_fact_ids": [],
        "source_reference_projection_count": 0,
        "deterministic_fallback_applied": False,
        "ignored_noncontrolling_normalized_proposals": 0,
    }


def test_prior_one_of_eighteen_state_collapse_cannot_override_deterministic_state():
    expected_states = ["known"] * 10 + ["unknown"] * 7 + ["conflicting"]
    contracts = []
    for index, expected_state in enumerate(expected_states):
        contract = deepcopy(catalog()[0])
        contract.update(
            {
                "fact_id": (
                    "fact_date_conflict"
                    if expected_state == "conflicting"
                    else f"fact_{index:02d}"
                ),
                "label": f"Deterministic fact {index}",
                "controls_process": False,
                "decision_key": None,
                "normalized_options": {},
                "admissible_normalized_values": [],
                "expected_state": expected_state,
                "canonical_value": f"Canonical value {index}",
                "canonical_explanation": f"Canonical explanation {index}.",
            }
        )
        if expected_state == "conflicting":
            set_contract_text_refs(
                contract,
                [
                    text_reference(),
                    text_reference(artifact_id="observable_email"),
                ],
            )
        contracts.append(contract)

    registry = observable_source_reference_registry(package())
    assertion_catalog = bounded_fact_assertion_catalog(contracts, registry)
    slots = {slot["fact_id"]: slot for slot in assertion_catalog}
    provider_proposals = [
        {
            "fact_id": contract["fact_id"],
            "assertion_id": reference_assertion_for(contract)["assertion_id"],
            "source_ref_ids": [
                next(
                    ref_id
                    for ref_id in slots[contract["fact_id"]][
                        "eligible_source_ref_ids"
                    ]
                    if next(
                        item["artifact_id"]
                        for item in registry
                        if item["source_ref_id"] == ref_id
                    )
                    == artifact_id
                )
                for artifact_id in sorted(
                    {
                        ref["artifact_id"]
                        for ref in contract["admissible_text_refs"]
                    }
                )
            ],
            "confidence": 0.5 + index / 100,
        }
        for index, contract in reversed(list(enumerate(contracts)))
    ]
    facts, diagnostics = canonicalizer_module._merge_fact_contracts(
        {"facts": provider_proposals},
        contracts,
        registry,
        assertion_catalog,
    )

    assert sum(state == "conflicting" for state in expected_states) == 1
    assert [fact["fact_id"] for fact in facts] == [
        contract["fact_id"] for contract in contracts
    ]
    assert [fact["label"] for fact in facts] == [
        contract["label"] for contract in contracts
    ]
    assert [fact["state"] for fact in facts] == expected_states
    assert all(fact["normalized_value"] is None for fact in facts)
    assert diagnostics["accepted_fact_count"] == 18
    assert diagnostics["rejected_fact_count"] == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("label", "Provider-authored label"),
        ("state", "conflicting"),
        ("normalized_value", "urgent"),
    ],
)
def test_provider_cannot_inject_deterministic_owned_fact_fields(
    tmp_path: Path,
    field: str,
    value: object,
):
    storage = Storage(str(tmp_path / f"deterministic-field-{field}.db"))

    def transport(*_args):
        provider_response = response()
        output = json.loads(provider_response["choices"][0]["message"]["content"])
        output["facts"]["fact_report"][field] = value
        provider_response["choices"][0]["message"]["content"] = json.dumps(output)
        return provider_response

    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=transport,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(ModelResponseError, match="hybrid_model_contribution"):
        canonicalizer.canonicalize(
            package(),
            run_id=f"run-deterministic-field-{field}",
            allowed_fact_catalog=catalog(),
        )
    assert_zero_accepted_rejection(storage, "provider_fact_fields")


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "unknown"])
def test_fact_catalog_membership_is_exact_before_catalog_order_merge(mutation: str):
    contracts = three_fact_catalog()
    proposals = [
        {
            "fact_id": contract["fact_id"],
            "assertion_id": reference_assertion_for(contract)["assertion_id"],
            "source_ref_ids": [observable_ref_id(package())],
            "confidence": 0.8,
        }
        for contract in contracts
    ]
    if mutation == "missing":
        proposals.pop()
    elif mutation == "duplicate":
        proposals[-1]["fact_id"] = proposals[0]["fact_id"]
    else:
        proposals[-1]["fact_id"] = "fact_outside_catalog"

    with pytest.raises(ModelResponseError, match="fact_catalog_membership") as caught:
        canonicalizer_module._merge_fact_contracts(
            {"facts": proposals},
            contracts,
            observable_source_reference_registry(package()),
            assertion_catalog_for(contracts),
        )
    assert caught.value.invariant == "fact_catalog_membership"


def test_all_canonicalizer_contract_versions_invalidate_success_cache(
    tmp_path: Path,
    monkeypatch,
):
    storage = Storage(str(tmp_path / "versioned-cache.db"))
    provider_calls = 0

    def transport(*_args):
        nonlocal provider_calls
        provider_calls += 1
        provider_response = response()
        provider_response["id"] = f"generation-version-{provider_calls}"
        return provider_response

    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=transport,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    baseline = canonicalizer.canonicalize(
        package(), run_id="run-version-baseline", allowed_fact_catalog=catalog()
    )
    cached = canonicalizer.canonicalize(
        package(), run_id="run-version-cache-hit", allowed_fact_catalog=catalog()
    )
    assert canonicalizer_module.CANONICALIZER_VERSION == "1.10.0"
    assert canonicalizer_module.PROMPT_VERSION == "canonical-facts/1.9.0"
    assert canonicalizer_module.SCHEMA_VERSION == "casepath.canonical-facts/1.8.0"
    assert baseline["cache_hit"] is False
    assert cached["cache_hit"] is True

    changed_keys = []
    for name in ("CANONICALIZER_VERSION", "PROMPT_VERSION", "SCHEMA_VERSION"):
        with monkeypatch.context() as patcher:
            patcher.setattr(
                canonicalizer_module,
                name,
                f"{getattr(canonicalizer_module, name)}-cache-invalidation-test",
            )
            invalidated = canonicalizer.canonicalize(
                package(),
                run_id=f"run-version-{name.lower()}",
                allowed_fact_catalog=catalog(),
            )
            assert invalidated["cache_hit"] is False
            changed_keys.append(invalidated["cache_key"])

    assert provider_calls == 4
    assert len({baseline["cache_key"], *changed_keys}) == 4


def test_canonical_cache_binds_exact_wire_policy(monkeypatch):
    registry = [
        {
            "source_ref_id": "src_example",
            "artifact_id": "message",
            "page": 1,
            "excerpt": "Example.",
        }
    ]
    assertion_catalog = [
        {
            "fact_id": "fact_report",
            "eligible_source_ref_ids": ["src_example"],
            "assertions": [{"assertion_id": "assert_example"}],
        }
    ]
    provider_schema = canonicalizer_module.canonical_facts_schema(
        registry,
        assertion_catalog,
    )

    def cache_key() -> str:
        return canonicalizer_module._cache_key(
            {"package": package(), "fact_catalog": catalog()},
            provider_schema=provider_schema,
            system_prompt=canonicalizer_module.CANONICAL_SYSTEM_PROMPT,
        )

    baseline = cache_key()
    mutations = [
        (canonicalizer_module, "MAX_OUTPUT_TOKENS", 4096),
        (canonicalizer_module, "CANONICAL_REASONING", {"effort": "low"}),
        (
            canonicalizer_module,
            "openrouter_provider_policy",
            lambda: {
                "only": ["together"],
                "allow_fallbacks": False,
                "require_parameters": False,
                "data_collection": "deny",
            },
        ),
        (
            canonicalizer_module,
            "CANONICAL_SYSTEM_PROMPT",
            f"{canonicalizer_module.CANONICAL_SYSTEM_PROMPT} Changed.",
        ),
    ]
    changed = []
    for owner, name, value in mutations:
        with monkeypatch.context() as patcher:
            patcher.setattr(owner, name, value)
            changed.append(cache_key())

    altered_schema = deepcopy(provider_schema)
    altered_schema["properties"]["facts"]["properties"]["fact_report"][
        "properties"
    ]["confidence"]["maximum"] = 0.99
    schema_changed = canonicalizer_module._cache_key(
        {"package": package(), "fact_catalog": catalog()},
        provider_schema=altered_schema,
        system_prompt=canonicalizer_module.CANONICAL_SYSTEM_PROMPT,
    )
    assert len({baseline, *changed, schema_changed}) == 6


def test_missing_sync_usage_polls_generation_metadata_without_retrying_inference(tmp_path: Path):
    storage = Storage(str(tmp_path / "ledger.db"))
    inference_calls = 0
    metadata_calls: list[tuple[str, dict[str, str], float]] = []
    sleeps: list[float] = []

    def transport(*_args):
        nonlocal inference_calls
        inference_calls += 1
        value = response()
        value.pop("usage")
        return value

    metadata_success = generation_metadata(cost=0.0057, prompt_tokens=321, completion_tokens=87)
    metadata_success["data"]["secret_provider_blob"] = "must-not-be-persisted"
    metadata_values = [{"data": {}}, metadata_success]

    def metadata_transport(url, headers, timeout):
        metadata_calls.append((url, headers, timeout))
        return metadata_values.pop(0)

    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=transport,
        metadata_transport=metadata_transport,
        metadata_sleep=sleeps.append,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    result = canonicalizer.canonicalize(
        package(),
        run_id="run_metadata_fallback",
        allowed_fact_catalog=catalog(),
    )
    assert result["facts"][0]["decision_value"] == "recurrence_supported"
    assert inference_calls == 1
    assert len(metadata_calls) == 2
    assert sleeps == [0.5]
    for url, metadata_headers, timeout in metadata_calls:
        assert url == f"{OPENROUTER_GENERATION_URL}?id=generation-test-1"
        assert metadata_headers == {
            "Authorization": "Bearer runtime-only-test-value",
            "Accept": "application/json",
        }
        assert timeout == 10.0
    entry = storage.model_calls()[0]
    assert entry["outcome"] == "succeeded"
    assert entry["usage_source"] == "generation_metadata"
    assert entry["response_id"] == "generation-test-1"
    assert entry["response_model"] == OPENROUTER_MODEL
    assert entry["generation_model"] == OPENROUTER_CANONICAL_MODEL
    assert entry["upstream_provider"] == "Together"
    assert entry["prompt_tokens"] == 321
    assert entry["completion_tokens"] == 87
    assert entry["total_tokens"] == 408
    assert entry["actual_cost_usd"] == pytest.approx(0.0057)
    assert entry["metadata_poll_count"] == 2
    assert entry["metadata_latency_ms"] >= 0
    serialized = json.dumps(storage.model_calls())
    assert "runtime-only-test-value" not in serialized
    assert "must-not-be-persisted" not in serialized


def test_generation_metadata_eventual_consistency_uses_bounded_backoff(
    tmp_path: Path,
):
    storage = Storage(str(tmp_path / "delayed-metadata.db"))
    inference_calls = 0
    metadata_calls = 0
    sleeps: list[float] = []

    def transport(*_args):
        nonlocal inference_calls
        inference_calls += 1
        value = response()
        value.pop("provider")
        return value

    metadata_success = generation_metadata(
        cost=0.0042,
        prompt_tokens=123,
        completion_tokens=45,
    )

    def metadata_transport(*_args):
        nonlocal metadata_calls
        metadata_calls += 1
        if metadata_calls < canonicalizer_module.GENERATION_METADATA_POLL_ATTEMPTS:
            partial = deepcopy(metadata_success)
            partial["data"]["usage"] = None
            return partial
        return metadata_success

    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=transport,
        metadata_transport=metadata_transport,
        metadata_sleep=sleeps.append,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    result = canonicalizer.canonicalize(
        package(),
        run_id="run-delayed-generation-metadata",
        allowed_fact_catalog=catalog(),
    )

    assert result["facts"][0]["decision_value"] == "recurrence_supported"
    assert inference_calls == 1
    assert metadata_calls == 8
    assert sleeps == [0.5, 1.0, 2.0, 4.0, 8.0, 8.0, 8.0]
    ledger = storage.sanitized_model_ledger()[0]
    assert ledger["outcome"] == "succeeded"
    assert ledger["metadata_poll_count"] == 8
    assert ledger["usage_source"] == "generation_metadata"
    assert ledger["upstream_provider"] == "Together"
    assert ledger["actual_cost_usd"] == pytest.approx(0.0042)


def test_identical_canonicalization_uses_cache_without_network(tmp_path: Path):
    storage = Storage(str(tmp_path / "ledger.db"))
    network_calls = 0
    progress_receipts: list[dict[str, object]] = []

    def transport(*_args):
        nonlocal network_calls
        network_calls += 1
        return response()

    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=transport,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    kwargs = {
        "run_id": "run_test",
        "allowed_fact_catalog": catalog(),
        "progress_sink": progress_receipts.append,
    }
    first = canonicalizer.canonicalize(package(), **kwargs)
    second = canonicalizer.canonicalize(package(), **kwargs)
    assert first["cache_hit"] is False
    assert second["cache_hit"] is True
    assert network_calls == 1
    assert storage.model_call_summary()["network_calls"] == 1
    assert [value["outcome"] for value in storage.model_calls()] == ["succeeded", "cache_hit"]
    assert len(progress_receipts) == 1
    assert progress_receipts[0]["receipt_type"] == "agent_started"
    assert progress_receipts[0]["call_id"] == first["call_id"]
    assert progress_receipts[0]["cache_hit"] is False


def test_any_rejected_fact_fails_without_fallback_or_cache(tmp_path: Path):
    storage = Storage(str(tmp_path / "ledger.db"))
    network_calls = 0
    contracts = three_fact_catalog()

    def transport(*_args):
        nonlocal network_calls
        network_calls += 1
        value = response()
        output = json.loads(value["choices"][0]["message"]["content"])
        output["facts"]["fact_report"]["confidence"] = 0.37
        output["facts"]["fact_context"] = {
            "fact_id": "fact_context",
            "assertion_id": reference_assertion_for(contracts[1])["assertion_id"],
            "source_ref_ids": {"message": observable_ref_id(package())},
            "confidence": 1.01,
        }
        output["facts"]["fact_background"] = {
            "fact_id": "fact_background",
            "assertion_id": reference_assertion_for(contracts[2])["assertion_id"],
            "source_ref_ids": {"message": observable_ref_id(package())},
            "confidence": 0.61,
        }
        value["choices"][0]["message"]["content"] = json.dumps(output)
        return value

    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=transport,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    kwargs = {
        "allowed_fact_catalog": contracts,
    }
    for run_id in ("run_partial", "run_not_cached"):
        with pytest.raises(ModelResponseError, match="hybrid_model_contribution"):
            canonicalizer.canonicalize(package(), run_id=run_id, **kwargs)
    assert network_calls == 2
    expected_diagnostics = {
        "authority_mode": "hybrid_guarded",
        "accepted_fact_ids": ["fact_report", "fact_background"],
        "accepted_fact_count": 2,
        "rejected_facts": [
            {"fact_id": "fact_context", "invariant": "confidence_contract"}
        ],
        "rejected_fact_count": 1,
        "source_reference_projection_fact_ids": [],
        "source_reference_projection_count": 0,
        "deterministic_fallback_applied": False,
        "ignored_noncontrolling_normalized_proposals": 0,
    }
    ledger = storage.model_calls()
    assert [item["outcome"] for item in ledger] == ["failed", "failed"]
    for item in storage.sanitized_model_ledger():
        assert item["authority_mode"] == "hybrid_guarded"
        assert item["accepted_fact_ids"] == ["fact_report", "fact_background"]
        assert item["rejected_facts"] == [
            {"fact_id": "fact_context", "invariant": "confidence_contract"}
        ]
        assert item["deterministic_fallback_applied"] is False
        assert storage.cached_model_output(item["cache_key"]) is None
    sanitized = json.dumps(storage.sanitized_model_ledger())
    assert "reports a recurring mark" not in sanitized
    assert "source_ref_ids" not in sanitized
    assert "runtime-only-test-value" not in sanitized


@pytest.mark.parametrize("invalid_usage", [{"cost": 0.0}, {"completion_tokens": 0}, {"total_tokens": 1}])
def test_incomplete_sync_usage_fails_when_generation_metadata_remains_missing(
    tmp_path: Path,
    invalid_usage: dict,
):
    storage = Storage(str(tmp_path / "ledger.db"))
    metadata_calls = 0

    def transport(*_args):
        value = response()
        value["usage"].update(invalid_usage)
        return value

    def missing_metadata(*_args):
        nonlocal metadata_calls
        metadata_calls += 1
        return {"data": {}}

    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=transport,
        metadata_transport=missing_metadata,
        metadata_sleep=lambda _seconds: None,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(ModelResponseError, match="generation_metadata_completeness invariant failed"):
        canonicalizer.canonicalize(
            package(),
            run_id="run_invalid_usage",
            allowed_fact_catalog=catalog(),
        )
    assert metadata_calls == 8
    assert storage.model_calls()[0]["outcome"] == "failed"


@pytest.mark.parametrize(
    ("metadata_value", "expected_invariant", "expected_calls", "expected_cost"),
    [
        (
            generation_metadata(generation_id="different-generation"),
            "generation_metadata_identity",
            1,
            None,
        ),
        (
            generation_metadata(model="different/model"),
            "invalid_provenance",
            1,
            0.0057,
        ),
        (
            {"data": {}},
            "generation_metadata_completeness",
            8,
            None,
        ),
        (
            generation_metadata(cost=0.0),
            "generation_metadata_usage",
            1,
            None,
        ),
    ],
)
def test_generation_metadata_mismatch_missing_or_zero_fails_closed(
    tmp_path: Path,
    metadata_value: dict,
    expected_invariant: str,
    expected_calls: int,
    expected_cost: float | None,
):
    storage = Storage(str(tmp_path / "ledger.db"))
    inference_calls = 0
    metadata_calls = 0

    def transport(*_args):
        nonlocal inference_calls
        inference_calls += 1
        value = response()
        value.pop("usage")
        return value

    def metadata_transport(*_args):
        nonlocal metadata_calls
        metadata_calls += 1
        return metadata_value

    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=transport,
        metadata_transport=metadata_transport,
        metadata_sleep=lambda _seconds: None,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(ModelResponseError, match=rf"{expected_invariant} invariant failed"):
        canonicalizer.canonicalize(
            package(),
            run_id="run_bad_metadata",
            allowed_fact_catalog=catalog(),
        )
    assert inference_calls == 1
    assert metadata_calls == expected_calls
    entry = storage.model_calls()[0]
    assert entry["outcome"] == "failed"
    assert entry["response_id"] == "generation-test-1"
    assert entry["response_model"] == OPENROUTER_MODEL
    assert entry["actual_cost_usd"] == expected_cost
    assert entry["error_invariant"] == expected_invariant
    if expected_invariant in {
        "generation_metadata_completeness",
        "generation_metadata_usage",
    }:
        assert entry["metadata_poll_count"] == expected_calls
        assert entry["metadata_latency_ms"] >= 0
    if expected_invariant == "invalid_provenance":
        assert entry["invalid_provenance_field"] == "response_model"
        assert len(entry["invalid_provenance_value_hash"]) == 64
        assert "different/model" not in json.dumps(entry)


def test_generation_metadata_provenance_is_bounded_while_billing_is_retained(
    tmp_path: Path,
):
    storage = Storage(str(tmp_path / "metadata-provenance.db"))

    def transport(*_args):
        value = response()
        value.pop("usage")
        return value

    metadata = generation_metadata()
    metadata["data"]["provider_name"] = "SECRET_SENTINEL_PROVIDER"
    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=transport,
        metadata_transport=lambda *_args: metadata,
        metadata_sleep=lambda _seconds: None,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(ModelResponseError, match="invalid_provenance"):
        canonicalizer.canonicalize(
            package(),
            run_id="run_invalid_metadata_provenance",
            allowed_fact_catalog=catalog(),
        )
    entry = storage.model_calls()[0]
    serialized = json.dumps(entry)
    assert entry["outcome"] == "failed"
    assert entry["error_invariant"] == "invalid_provenance"
    assert entry["actual_cost_usd"] == pytest.approx(0.0057)
    assert entry["prompt_tokens"] == 321
    assert entry["completion_tokens"] == 87
    assert entry["invalid_provenance_field"] == "upstream_provider"
    assert "SECRET_SENTINEL_PROVIDER" not in serialized


def test_concurrent_identical_cold_cache_calls_are_single_flight(tmp_path: Path):
    storage = Storage(str(tmp_path / "ledger.db"))
    network_calls = 0

    def transport(*_args):
        nonlocal network_calls
        network_calls += 1
        time.sleep(0.05)
        return response()

    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=transport,
        api_key_provider=lambda: "runtime-only-test-value",
    )

    def invoke(run_id: str) -> dict:
        return canonicalizer.canonicalize(
            package(),
            run_id=run_id,
            allowed_fact_catalog=catalog(),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(invoke, ["run_a", "run_b"]))
    assert network_calls == 1
    assert sorted(result["cache_hit"] for result in results) == [False, True]
    assert sorted(value["outcome"] for value in storage.model_calls()) == ["cache_hit", "succeeded"]
    assert storage.model_call_summary()["network_calls"] == 1


def test_missing_credential_is_fail_closed_and_never_calls_network(tmp_path: Path):
    storage = Storage(str(tmp_path / "ledger.db"))

    def forbidden_transport(*_args):
        raise AssertionError("network must not be called")

    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=forbidden_transport,
        api_key_provider=lambda: None,
    )
    with pytest.raises(ModelConfigurationError, match="requires an API credential") as caught:
        canonicalizer.canonicalize(
            package(),
            run_id="run_test",
            allowed_fact_catalog=catalog(),
        )
    entry = storage.model_calls()[0]
    assert entry["outcome"] == "blocked_missing_credential"
    assert entry["call_count"] == 0
    assert entry["error_invariant"] == "missing_credential"
    assert caught.value.safe_context["error_invariant"] == "missing_credential"


def test_preflight_cost_guard_uses_persistent_committed_cost(tmp_path: Path):
    storage = Storage(str(tmp_path / "ledger.db"))
    call_id = storage.create_model_call(
        run_id="prior",
        provider="openrouter",
        model=OPENROUTER_MODEL,
        cache_key="prior-cache",
        purpose="prior paid call",
        call_count=1,
        estimated_cost_usd=24.999,
        outcome="started",
        provider_endpoint=OPENROUTER_URL,
        implementation="model_backed_openrouter_canonicalizer",
    )
    storage.finish_model_call(call_id, outcome="succeeded", actual_cost_usd=24.999)
    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=lambda *_args: (_ for _ in ()).throw(AssertionError("network must not be called")),
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(ModelCostGuardError, match="cumulative USD cap") as caught:
        canonicalizer.canonicalize(
            package(),
            run_id="run_test",
            allowed_fact_catalog=catalog(),
        )
    assert storage.model_calls()[-1]["outcome"] == "blocked_cost_guard"
    assert storage.model_calls()[-1]["call_count"] == 0
    assert storage.model_calls()[-1]["error_invariant"] == "cost_guard"
    assert caught.value.safe_context["error_invariant"] == "cost_guard"


def test_actual_usage_cost_is_recorded_even_when_it_exceeds_cap(tmp_path: Path):
    storage = Storage(str(tmp_path / "ledger.db"))
    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=lambda *_args: response(cost=25.01),
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(ModelCostGuardError, match="Actual model cost") as caught:
        canonicalizer.canonicalize(
            package(),
            run_id="run_test",
            allowed_fact_catalog=catalog(),
        )
    entry = storage.model_calls()[0]
    assert entry["outcome"] == "actual_cost_overrun"
    assert entry["actual_cost_usd"] == pytest.approx(25.01)
    assert storage.model_actual_cost_total() == pytest.approx(25.01)
    assert caught.value.safe_context["call_id"] == entry["call_id"]
    assert caught.value.safe_context["outcome"] == "actual_cost_overrun"
    assert caught.value.safe_context["error_invariant"] == "actual_cost_overrun"
    assert caught.value.safe_context["response_id"] == "generation-test-1"


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("id", "gen-" + "x" * 200),
        ("provider", "SECRET_SENTINEL_PROVIDER"),
        ("finish_reason", "SECRET_SENTINEL_FINISH"),
    ],
)
def test_provider_provenance_is_bounded_before_internal_storage(
    tmp_path: Path,
    field: str,
    invalid_value: str,
):
    storage = Storage(str(tmp_path / "bounded-provenance.db"))

    def transport(*_args):
        value = response()
        if field == "finish_reason":
            value["choices"][0]["finish_reason"] = invalid_value
        else:
            value[field] = invalid_value
        return value

    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=transport,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(ModelResponseError, match="invalid_provenance") as caught:
        canonicalizer.canonicalize(
            package(),
            run_id="run_invalid_provenance",
            allowed_fact_catalog=catalog(),
        )
    entry = storage.model_calls()[0]
    serialized = json.dumps(entry)
    assert entry["outcome"] == "failed"
    assert entry["error_invariant"] == "invalid_provenance"
    assert entry["actual_cost_usd"] == pytest.approx(0.0042)
    assert entry["invalid_provenance_field"] in {
        "response_id",
        "upstream_provider",
        "finish_reason",
    }
    assert len(entry["invalid_provenance_value_hash"]) == 64
    assert invalid_value not in serialized
    assert "runtime-only-test-value" not in serialized
    assert caught.value.safe_context["invalid_provenance_value_hash"] == entry[
        "invalid_provenance_value_hash"
    ]


def test_foreign_response_model_is_hashed_and_rejected_as_invalid_provenance(
    tmp_path: Path,
):
    storage = Storage(str(tmp_path / "ledger.db"))
    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=lambda *_args: response(model="different/model"),
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(ModelResponseError, match="invalid_provenance invariant failed") as caught:
        canonicalizer.canonicalize(
            package(),
            run_id="run_test",
            allowed_fact_catalog=catalog(),
        )
    entry = storage.model_calls()[0]
    assert entry["outcome"] == "failed"
    assert entry["usage_source"] == "response"
    assert entry["actual_cost_usd"] == pytest.approx(0.0042)
    assert entry["error_invariant"] == "invalid_provenance"
    assert entry["invalid_provenance_field"] == "response_model"
    assert "response_model" not in entry
    assert caught.value.safe_context["call_id"] == entry["call_id"]
    assert caught.value.safe_context["invalid_provenance_value_hash"] == entry[
        "invalid_provenance_value_hash"
    ]
    assert "different/model" not in json.dumps(entry)


def test_nonstop_canonical_response_cannot_be_accepted_or_cached(tmp_path: Path):
    value = response()
    value["choices"][0]["finish_reason"] = "length"
    storage = Storage(str(tmp_path / "nonstop-canonical.db"))
    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=lambda *_args: value,
        api_key_provider=lambda: "runtime-only-test-value",
    )

    with pytest.raises(ModelResponseError, match="provider_finish_reason"):
        canonicalizer.canonicalize(
            package(),
            run_id="run-nonstop-canonical",
            allowed_fact_catalog=catalog(),
        )

    ledger = storage.model_calls()[0]
    assert ledger["outcome"] == "failed"
    assert ledger["error_invariant"] == "provider_finish_reason"
    assert ledger["finish_reason"] == "length"
    assert ledger["actual_cost_usd"] == pytest.approx(0.0042)
    assert storage.cached_model_output(ledger["cache_key"]) is None


def test_canonicalizer_fails_closed_on_source_reference_id_outside_registry(tmp_path: Path):
    storage = Storage(str(tmp_path / "ledger.db"))

    def incorrect_id_response(*_args):
        value = response()
        output = json.loads(value["choices"][0]["message"]["content"])
        output["facts"]["fact_report"]["source_ref_ids"] = {
            "message": "src_not_in_the_observable_registry"
        }
        value["choices"][0]["message"]["content"] = json.dumps(output)
        return value

    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=incorrect_id_response,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(ModelResponseError, match="provider_native_schema invariant failed"):
        canonicalizer.canonicalize(
            package(),
            run_id="run_test",
            allowed_fact_catalog=catalog(),
        )
    assert_provider_schema_rejection(storage)


def test_canonicalizer_rejects_duplicate_source_reference_ids(tmp_path: Path):
    storage = Storage(str(tmp_path / "duplicate-source-refs.db"))

    def duplicate_id_response(*_args):
        value = response()
        output = json.loads(value["choices"][0]["message"]["content"])
        source_ref_id = output["facts"]["fact_report"]["source_ref_ids"]["message"]
        output["facts"]["fact_report"]["source_ref_ids"] = [source_ref_id, source_ref_id]
        value["choices"][0]["message"]["content"] = json.dumps(output)
        return value

    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=duplicate_id_response,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(ModelResponseError, match="provider_native_schema"):
        canonicalizer.canonicalize(
            package(),
            run_id="run-duplicate-source-refs",
            allowed_fact_catalog=catalog(),
        )
    assert_provider_schema_rejection(storage)


def test_alternate_eligible_passage_from_related_artifact_is_materialized(tmp_path: Path):
    observable = package()
    observable["customer_message"]["body"] = (
        "The tenant reports a recurring mark; the room remains occupied."
    )
    containing_ref = {
        "artifact_id": "message",
        "page": 1,
        "excerpt": "The tenant reports a recurring mark; the room remains occupied.",
    }
    containing_ref_id = source_reference_id(containing_ref)
    assert containing_ref_id in {
        item["source_ref_id"] for item in observable_source_reference_registry(observable)
    }

    def containing_passage_response(*_args):
        value = response()
        output = json.loads(value["choices"][0]["message"]["content"])
        output["facts"]["fact_report"]["source_ref_ids"] = {
            "message": containing_ref_id
        }
        value["choices"][0]["message"]["content"] = json.dumps(output)
        return value

    storage = Storage(str(tmp_path / "ledger.db"))
    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=containing_passage_response,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    result = canonicalizer.canonicalize(
        observable,
        run_id="run_containing_passage",
        allowed_fact_catalog=catalog(),
    )
    assert result["diagnostics"]["accepted_fact_ids"] == ["fact_report"]
    assert result["diagnostics"]["deterministic_fallback_applied"] is False
    assert result["facts"][0]["source_refs"][0]["excerpt"] == (
        "The tenant reports a recurring mark; the room remains occupied."
    )


def test_more_than_one_eligible_passage_per_artifact_is_rejected(
    tmp_path: Path,
):
    observable = package()
    observable["customer_message"]["body"] = (
        "The tenant reports a recurring mark; the room remains occupied."
    )
    registry = observable_source_reference_registry(observable)
    selected_ids = [
        item["source_ref_id"]
        for item in registry
        if item["artifact_id"] == "message"
        and item["excerpt"]
        in {
            "The tenant reports a recurring mark",
            "the room remains occupied.",
        }
    ]
    assert len(selected_ids) == 2

    def extra_passage_response(*_args):
        value = response()
        output = json.loads(value["choices"][0]["message"]["content"])
        output["facts"]["fact_report"]["source_ref_ids"] = selected_ids
        value["choices"][0]["message"]["content"] = json.dumps(output)
        return value

    storage = Storage(str(tmp_path / "ledger.db"))
    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=extra_passage_response,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(ModelResponseError, match="provider_native_schema"):
        canonicalizer.canonicalize(
            observable,
            run_id="run_redundant_eligible_subset",
            allowed_fact_catalog=catalog(),
        )
    assert_provider_schema_rejection(storage)


def test_registry_reference_from_unrelated_artifact_is_rejected(tmp_path: Path):
    observable = package()
    wrong_ref_id = next(
        item["source_ref_id"]
        for item in observable_source_reference_registry(observable)
        if item["artifact_id"] == "observable_email"
    )

    def wrong_artifact_response(*_args):
        value = response()
        output = json.loads(value["choices"][0]["message"]["content"])
        output["facts"]["fact_report"]["source_ref_ids"] = {"message": wrong_ref_id}
        value["choices"][0]["message"]["content"] = json.dumps(output)
        return value

    storage = Storage(str(tmp_path / "wrong-artifact.db"))
    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=wrong_artifact_response,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(ModelResponseError, match="provider_native_schema"):
        canonicalizer.canonicalize(
            observable,
            run_id="run-wrong-artifact",
            allowed_fact_catalog=catalog(),
        )
    assert_provider_schema_rejection(storage)


def test_missing_structurally_related_artifact_is_rejected(tmp_path: Path):
    observable = package()
    observable["customer_message"]["body"] = "Observed 12 March."
    observable["artifacts"][0]["parsed_email"]["body"] = "Observed 20 March."
    registry = observable_source_reference_registry(observable)
    first_side_id = next(
        item["source_ref_id"]
        for item in registry
        if item["artifact_id"] == "message"
        and item["excerpt"] == "Observed 12 March."
    )
    conflict_catalog = catalog()
    conflict_catalog[0]["expected_state"] = "conflicting"
    set_contract_text_refs(
        conflict_catalog[0],
        [
            text_reference(excerpt="Observed 12 March."),
            text_reference(
                artifact_id="observable_email",
                excerpt="Observed 20 March.",
            ),
        ],
    )

    def one_sided_response(*_args):
        value = response()
        output = json.loads(value["choices"][0]["message"]["content"])
        conflict_assertions = bounded_fact_assertion_catalog(
            [conflict_catalog[0]], registry
        )[0]["assertions"]
        output["facts"]["fact_report"]["assertion_id"] = next(
            assertion["assertion_id"]
            for assertion in conflict_assertions
            if assertion["value"] == conflict_catalog[0]["canonical_value"]
        )
        output["facts"]["fact_report"]["source_ref_ids"] = {"message": first_side_id}
        value["choices"][0]["message"]["content"] = json.dumps(output)
        return value

    storage = Storage(str(tmp_path / "ledger.db"))
    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=one_sided_response,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(ModelResponseError, match="provider_native_schema"):
        canonicalizer.canonicalize(
            observable,
            run_id="run_one_sided_conflict",
            allowed_fact_catalog=conflict_catalog,
        )
    assert_provider_schema_rejection(storage)


def test_conflicting_selection_spans_two_related_artifacts(tmp_path: Path):
    observable = package()
    observable["customer_message"]["body"] = "Observed 12 March."
    observable["artifacts"][0]["parsed_email"]["body"] = "Observed 20 March."
    registry = observable_source_reference_registry(observable)
    selected_ids = [
        next(
            item["source_ref_id"]
            for item in registry
            if item["artifact_id"] == artifact_id
            and item["excerpt"] == excerpt
        )
        for artifact_id, excerpt in (
            ("message", "Observed 12 March."),
            ("observable_email", "Observed 20 March."),
        )
    ]
    conflict_catalog = catalog()
    conflict_catalog[0]["expected_state"] = "conflicting"
    set_contract_text_refs(
        conflict_catalog[0],
        [
            text_reference(excerpt="Observed 12 March."),
            text_reference(
                artifact_id="observable_email",
                excerpt="Observed 20 March.",
            ),
        ],
    )

    def two_sided_response(*_args):
        value = response()
        output = json.loads(value["choices"][0]["message"]["content"])
        output["facts"]["fact_report"]["assertion_id"] = next(
            assertion["assertion_id"]
            for assertion in bounded_fact_assertion_catalog(
                conflict_catalog, registry
            )[0]["assertions"]
            if assertion["state"] == "conflicting"
        )
        output["facts"]["fact_report"]["source_ref_ids"] = {
            "message": selected_ids[0],
            "observable_email": selected_ids[1],
        }
        value["choices"][0]["message"]["content"] = json.dumps(output)
        return value

    result = OpenRouterNemotronCanonicalizer(
        Storage(str(tmp_path / "two-sided-conflict.db")),
        transport=two_sided_response,
        api_key_provider=lambda: "runtime-only-test-value",
    ).canonicalize(
        observable,
        run_id="run-two-sided-conflict",
        allowed_fact_catalog=conflict_catalog,
    )
    assert result["facts"][0]["state"] == "conflicting"
    assert {
        ref["artifact_id"] for ref in result["facts"][0]["source_refs"]
    } == {"message", "observable_email"}


def test_semantic_rejection_retains_charged_provider_usage_and_identity(tmp_path: Path):
    storage = Storage(str(tmp_path / "ledger.db"))

    def semantically_invalid_response(*_args):
        value = response(model=OPENROUTER_CANONICAL_MODEL, cost=0.0061)
        output = json.loads(value["choices"][0]["message"]["content"])
        output["facts"]["fact_report"]["normalized_value"] = "urgent"
        value["choices"][0]["message"]["content"] = json.dumps(output)
        return value

    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=semantically_invalid_response,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(ModelResponseError, match="hybrid_model_contribution invariant failed"):
        canonicalizer.canonicalize(
            package(),
            run_id="run_semantic_failure",
            allowed_fact_catalog=catalog(),
        )
    entry = storage.model_calls()[0]
    assert entry["outcome"] == "failed"
    assert entry["error_type"] == "ModelResponseError"
    assert entry["model"] == OPENROUTER_MODEL
    assert entry["response_model"] == OPENROUTER_CANONICAL_MODEL
    assert entry["upstream_provider"] == "Together"
    assert entry["response_id"] == "generation-test-1"
    assert entry["prompt_tokens"] == 123
    assert entry["completion_tokens"] == 45
    assert entry["total_tokens"] == 168
    assert entry["actual_cost_usd"] == pytest.approx(0.0061)
    assert storage.model_actual_cost_total() == pytest.approx(0.0061)
    assert_zero_accepted_rejection(storage, "provider_fact_fields")


def test_dated_canonical_nemotron_response_identity_is_accepted(tmp_path: Path):
    storage = Storage(str(tmp_path / "ledger.db"))
    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=lambda *_args: response(model=OPENROUTER_CANONICAL_MODEL),
        api_key_provider=lambda: "runtime-only-test-value",
    )
    result = canonicalizer.canonicalize(
        package(),
        run_id="run_dated_identity",
        allowed_fact_catalog=catalog(),
    )
    assert result["model"] == OPENROUTER_MODEL
    entry = storage.model_calls()[0]
    assert entry["model"] == OPENROUTER_MODEL
    assert entry["response_model"] == OPENROUTER_CANONICAL_MODEL
    assert entry["upstream_provider"] == "Together"


def test_conflicting_selection_must_span_two_artifacts(tmp_path: Path):
    observable = package()
    observable["customer_message"]["body"] = "The message says 20 March, while the chronology says 12 March."
    contract = catalog()
    contract[0].update(
        {
            "controls_process": False,
            "decision_key": None,
            "normalized_options": {},
            "admissible_normalized_values": [],
            "expected_state": "conflicting",
            "canonical_value": "Conflicting dates",
            "canonical_explanation": "Two observable dates conflict.",
            "admissible_text_refs": [
                {"artifact_id": "message", "page": 1, "excerpt": "20 March"},
                {"artifact_id": "message", "page": 1, "excerpt": "12 March"},
            ],
        }
    )
    set_contract_text_refs(
        contract[0],
        [
            {"artifact_id": "message", "page": 1, "excerpt": "20 March"},
            {"artifact_id": "message", "page": 1, "excerpt": "12 March"},
        ],
    )

    def one_sided_response(*_args):
        value = response()
        output = json.loads(value["choices"][0]["message"]["content"])
        selected_ref_id = next(
            item["source_ref_id"]
            for item in observable_source_reference_registry(observable)
            if item["artifact_id"] == "message"
        )
        output["facts"]["fact_report"].update(
            {
                "assertion_id": reference_assertion_for(contract[0])["assertion_id"],
                "source_ref_ids": {"message": selected_ref_id},
            }
        )
        value["choices"][0]["message"]["content"] = json.dumps(output)
        return value

    canonicalizer = OpenRouterNemotronCanonicalizer(
        Storage(str(tmp_path / "ledger.db")),
        transport=one_sided_response,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(ModelResponseError, match="hybrid_model_contribution invariant failed"):
        canonicalizer.canonicalize(
            observable,
            run_id="run_test",
            allowed_fact_catalog=contract,
        )
    assert_zero_accepted_rejection(
        canonicalizer.storage, "eligible_source_selection"
    )


def test_nonempty_eligible_pool_rejects_empty_selection(tmp_path: Path):
    contract = catalog()
    contract[0].update(
        {
            "controls_process": False,
            "decision_key": None,
            "normalized_options": {},
            "admissible_normalized_values": [],
            "expected_state": "unknown",
            "canonical_value": "Cause unresolved",
            "canonical_explanation": "A reported condition exists but technical cause is unknown.",
        }
    )
    def ungrounded_response(*_args):
        value = response()
        output = json.loads(value["choices"][0]["message"]["content"])
        output["facts"]["fact_report"]["assertion_id"] = reference_assertion_for(
            contract[0]
        )["assertion_id"]
        output["facts"]["fact_report"]["source_ref_ids"] = {}
        value["choices"][0]["message"]["content"] = json.dumps(output)
        return value

    storage = Storage(str(tmp_path / "ledger.db"))
    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=ungrounded_response,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(ModelResponseError, match="provider_native_schema"):
        canonicalizer.canonicalize(
            package(),
            run_id="run_test",
            allowed_fact_catalog=contract,
        )
    assert_provider_schema_rejection(storage)


def test_empty_eligible_pool_requires_and_accepts_empty_selection(tmp_path: Path):
    contract = catalog()
    contract[0].update(
        {
            "controls_process": False,
            "decision_key": None,
            "normalized_options": {},
            "admissible_normalized_values": [],
            "expected_state": "unknown",
            "canonical_value": "No text available",
            "canonical_explanation": "No structurally related text artifact is available.",
        }
    )
    set_contract_text_refs(contract[0], [])
    assertion = reference_assertion_for(contract[0])

    def empty_selection_response(*_args):
        value = response()
        output = json.loads(value["choices"][0]["message"]["content"])
        output["facts"]["fact_report"]["assertion_id"] = assertion["assertion_id"]
        output["facts"]["fact_report"]["source_ref_ids"] = {}
        value["choices"][0]["message"]["content"] = json.dumps(output)
        return value

    result = OpenRouterNemotronCanonicalizer(
        Storage(str(tmp_path / "empty-source-pool.db")),
        transport=empty_selection_response,
        api_key_provider=lambda: "runtime-only-test-value",
    ).canonicalize(
        package(),
        run_id="run-empty-source-pool",
        allowed_fact_catalog=contract,
    )
    assert result["facts"][0]["source_refs"] == []
    assert result["diagnostics"]["accepted_fact_ids"] == ["fact_report"]


def test_exact_excerpt_grounding_normalizes_whitespace_and_rejects_hallucination():
    value = package()
    value["customer_message"]["body"] = "The tenant reports a\n recurring   mark."
    fact = grounded_fact()
    validate_exact_source_excerpts(value, [fact])
    fact["source_refs"][0]["excerpt"] = "reports a severe structural defect"
    with pytest.raises(ModelResponseError, match="exact normalized substring"):
        validate_exact_source_excerpts(value, [fact])


def test_exact_excerpt_grounding_rejects_text_quoted_from_wrong_pdf_page():
    value = package()
    value["artifacts"].append(
        {
            "artifact_id": "observable_pdf",
            "filename": "source.pdf",
            "media_type": "application/pdf",
            "received_at": "2026-08-01T09:03:00Z",
            "page_count": 2,
            "sha256": "1" * 64,
            "extracted_pages": [
                {"page": 1, "text": "The first page reports recurring moisture."},
                {"page": 2, "text": "The second page contains routing details only."},
            ],
        }
    )
    fact = grounded_fact()
    fact["source_refs"][0] = {
        "artifact_id": "observable_pdf",
        "locator_kind": "text_quote",
        "page": 2,
        "excerpt": "reports recurring moisture",
        "agent": "OpenRouter Nemotron Canonicalizer",
    }
    with pytest.raises(ModelResponseError, match="exact normalized substring"):
        validate_exact_source_excerpts(value, [fact])


def test_exact_excerpt_grounding_rejects_binary_image_as_direct_text_evidence():
    value = package()
    value["artifacts"].append(
        {
            "artifact_id": "observable_image",
            "filename": "source.jpg",
            "media_type": "image/jpeg",
            "received_at": "2026-08-01T09:03:00Z",
            "page_count": 1,
            "sha256": "2" * 64,
            "binary_source_available": True,
        }
    )
    fact = grounded_fact()
    fact["source_refs"][0] = {
        "artifact_id": "observable_image",
        "locator_kind": "text_quote",
        "page": 1,
        "excerpt": "the pixels show mould",
        "agent": "OpenRouter Nemotron Canonicalizer",
    }
    with pytest.raises(ModelResponseError, match="has no observable text"):
        validate_exact_source_excerpts(value, [fact])


def test_model_cannot_override_deterministic_process_control_metadata(tmp_path: Path):
    def malicious_response(*_args):
        value = response()
        output = json.loads(value["choices"][0]["message"]["content"])
        output["facts"]["fact_report"]["controls_process"] = False
        output["facts"]["fact_report"]["decision_value"] = "cause_building"
        value["choices"][0]["message"]["content"] = json.dumps(output)
        return value

    canonicalizer = OpenRouterNemotronCanonicalizer(
        Storage(str(tmp_path / "ledger.db")),
        transport=malicious_response,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(ModelResponseError, match="hybrid_model_contribution invariant failed"):
        canonicalizer.canonicalize(
            package(),
            run_id="run_test",
            allowed_fact_catalog=catalog(),
        )


def test_noncontrolling_normalized_proposal_is_rejected_as_deterministic_owned(
    tmp_path: Path,
):
    storage = Storage(str(tmp_path / "ledger.db"))
    contract = catalog()
    contract[0].update(
        {
            "controls_process": False,
            "decision_key": None,
            "normalized_options": {},
            "admissible_normalized_values": [],
        }
    )
    def proposed_value_response(*_args):
        value = response()
        output = json.loads(value["choices"][0]["message"]["content"])
        output["facts"]["fact_report"]["normalized_value"] = "urgent"
        value["choices"][0]["message"]["content"] = json.dumps(output)
        return value

    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=proposed_value_response,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(ModelResponseError, match="hybrid_model_contribution"):
        canonicalizer.canonicalize(
            package(),
            run_id="run_noncontrolling_proposal",
            allowed_fact_catalog=contract,
        )
    assert_zero_accepted_rejection(storage, "provider_fact_fields")


def test_model_cannot_invert_fixture_bound_decision_polarity(tmp_path: Path):
    observable = package()
    observable["customer_message"]["body"] = "There are no current symptoms and no urgent deadline."
    contract = catalog()
    contract[0].update(
        {
            "decision_key": "urgency",
            "normalized_options": {
                "urgent": "urgent",
                "not_urgent": "not_urgent",
                "unverified": "urgency_unverified",
            },
            "admissible_normalized_values": ["not_urgent"],
            "canonical_value": "No acute concern reported",
            "canonical_explanation": "The source states there are no current symptoms or urgent deadline.",
            "admissible_text_refs": [
                {
                    "artifact_id": "message",
                    "page": 1,
                    "excerpt": "no current symptoms and no urgent deadline",
                }
            ],
        }
    )
    set_contract_text_refs(
        contract[0],
        [
            {
                "artifact_id": "message",
                "page": 1,
                "excerpt": "no current symptoms and no urgent deadline",
            }
        ],
    )

    def inverted_response(*_args):
        value = response()
        output = json.loads(value["choices"][0]["message"]["content"])
        output["facts"]["fact_report"].update(
            {
                "normalized_value": "urgent",
                "source_ref_ids": {
                    "message": observable_ref_id(
                        observable,
                        text_reference(excerpt="no current symptoms and no urgent deadline"),
                    )
                },
            }
        )
        value["choices"][0]["message"]["content"] = json.dumps(output)
        return value

    storage = Storage(str(tmp_path / "ledger.db"))
    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=inverted_response,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(ModelResponseError, match="hybrid_model_contribution invariant failed"):
        canonicalizer.canonicalize(
            observable,
            run_id="run_test",
            allowed_fact_catalog=contract,
        )
    assert_zero_accepted_rejection(storage, "provider_fact_fields")


def test_provider_cannot_author_contradictory_display_prose(tmp_path: Path):
    observable = package()
    observable["customer_message"]["body"] = "There are no current symptoms and no urgent deadline."
    contract = catalog()
    contract[0].update(
        {
            "decision_key": "urgency",
            "normalized_options": {
                "urgent": "urgent",
                "not_urgent": "not_urgent",
                "unverified": "urgency_unverified",
            },
            "admissible_normalized_values": ["not_urgent"],
            "canonical_value": "No acute concern reported",
            "canonical_explanation": "The source states there are no current symptoms or urgent deadline.",
            "admissible_text_refs": [
                {
                    "artifact_id": "message",
                    "page": 1,
                    "excerpt": "no current symptoms and no urgent deadline",
                }
            ],
        }
    )
    set_contract_text_refs(
        contract[0],
        [
            {
                "artifact_id": "message",
                "page": 1,
                "excerpt": "no current symptoms and no urgent deadline",
            }
        ],
    )

    def contradictory_response(*_args):
        value = response()
        output = json.loads(value["choices"][0]["message"]["content"])
        output["facts"]["fact_report"].update(
            {
                "value": "Acute emergency requiring immediate action",
                "explanation": "Symptoms and an urgent deadline are present.",
                "normalized_value": "not_urgent",
                "source_ref_ids": {
                    "message": observable_ref_id(
                        observable,
                        text_reference(excerpt="no current symptoms and no urgent deadline"),
                    )
                },
            }
        )
        value["choices"][0]["message"]["content"] = json.dumps(output)
        return value

    storage = Storage(str(tmp_path / "ledger.db"))
    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=contradictory_response,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(ModelResponseError, match="hybrid_model_contribution invariant failed"):
        canonicalizer.canonicalize(
            observable,
            run_id="run_test",
            allowed_fact_catalog=contract,
        )
    assert_zero_accepted_rejection(storage, "provider_fact_fields")


def test_process_owned_visual_enrichment_survives_model_merge(tmp_path: Path):
    observable = package()
    observable["artifacts"].append(
        {
            "artifact_id": "observable_image",
            "filename": "source.jpg",
            "media_type": "image/jpeg",
            "received_at": "2026-08-01T09:03:00Z",
            "page_count": 1,
            "sha256": "2" * 64,
            "binary_source_available": True,
        }
    )
    visual_ref = visual_annotation_ref(
        artifact_id="observable_image",
        image_sha256="2" * 64,
        region=[0.1, 0.2, 0.3, 0.4],
        observation="Visible localized dark spotting.",
    )
    requests: list[dict] = []

    def transport(_url, _headers, payload, _timeout):
        requests.append(payload)
        return response()

    canonicalizer = OpenRouterNemotronCanonicalizer(
        Storage(str(tmp_path / "ledger.db")),
        transport=transport,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    result = canonicalizer.canonicalize(
        observable,
        run_id="run_test",
        allowed_fact_catalog=catalog(bounded_enrichments=[visual_ref]),
    )
    assert visual_ref in result["facts"][0]["source_refs"]
    assert "Visible localized dark spotting" not in requests[0]["messages"][1]["content"]


def test_model_budget_cap_defaults_to_25_and_only_configures_downward(monkeypatch):
    monkeypatch.delenv("CASEPATH_MODEL_CUMULATIVE_USD_CAP", raising=False)
    assert cumulative_usd_cap() == DEFAULT_CUMULATIVE_USD_CAP == 25.0
    monkeypatch.setenv("CASEPATH_MODEL_CUMULATIVE_USD_CAP", "12.5")
    assert cumulative_usd_cap() == 12.5
    monkeypatch.setenv("CASEPATH_MODEL_CUMULATIVE_USD_CAP", "400")
    assert cumulative_usd_cap() == 25.0
    monkeypatch.setenv("CASEPATH_MODEL_CUMULATIVE_USD_CAP", "1000")
    assert cumulative_usd_cap() == 25.0
    for invalid in ("nan", "inf", "+inf", "-inf"):
        monkeypatch.setenv("CASEPATH_MODEL_CUMULATIVE_USD_CAP", invalid)
        with pytest.raises(ModelConfigurationError, match="finite and positive"):
            cumulative_usd_cap()


def test_no_key_default_remains_deterministic_reference(monkeypatch):
    monkeypatch.delenv("CASEPATH_MODEL_MODE", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert configured_model_mode() == MODEL_MODE_REFERENCE


def test_missing_finish_reason_uses_metadata_and_warm_cache_retains_origin_finish(
    tmp_path: Path,
):
    inference_calls = 0
    metadata_calls = 0

    def transport(*_args):
        nonlocal inference_calls
        inference_calls += 1
        value = response()
        value["choices"][0]["finish_reason"] = None
        return value

    def metadata_transport(*_args):
        nonlocal metadata_calls
        metadata_calls += 1
        return generation_metadata()

    storage = Storage(str(tmp_path / "finish.db"))
    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=transport,
        metadata_transport=metadata_transport,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    first = canonicalizer.canonicalize(
        package(), run_id="run-finish-cold", allowed_fact_catalog=catalog()
    )
    second = canonicalizer.canonicalize(
        package(), run_id="run-finish-warm", allowed_fact_catalog=catalog()
    )
    assert inference_calls == metadata_calls == 1
    assert first["finish_reason"] == "stop"
    assert first["usage_source"] == "generation_metadata"
    assert second["cache_hit"] is True
    assert second["origin_finish_reason"] == "stop"
    warm_ledger = storage.sanitized_model_ledger()[1]
    assert warm_ledger["finish_reason"] == "stop"
    assert warm_ledger["origin_finish_reason"] == "stop"
    assert warm_ledger["origin_usage"] == {
        "prompt_tokens": 321,
        "completion_tokens": 87,
        "total_tokens": 408,
        "actual_cost_usd": 0.0057,
        "usage_source": "generation_metadata",
    }


def test_missing_upstream_provider_uses_metadata_before_persisting_success(
    tmp_path: Path,
):
    inference_calls = 0
    metadata_calls = 0

    def structured_invoker(*_args):
        nonlocal inference_calls
        inference_calls += 1
        value = response()
        value.pop("provider")
        return value

    def metadata_transport(*_args):
        nonlocal metadata_calls
        metadata_calls += 1
        return generation_metadata()

    storage = Storage(str(tmp_path / "missing-provider.db"))
    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        structured_invoker=structured_invoker,
        metadata_transport=metadata_transport,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    result = canonicalizer.canonicalize(
        package(),
        run_id="run-missing-provider",
        allowed_fact_catalog=catalog(),
    )

    assert inference_calls == metadata_calls == 1
    assert result["upstream_provider"] == "Together"
    assert result["usage_source"] == "generation_metadata"
    ledger = storage.sanitized_model_ledger()[0]
    assert ledger["outcome"] == "succeeded"
    assert ledger["upstream_provider"] == "Together"
    assert ledger["usage_source"] == "generation_metadata"
    assert ledger["response_id"] == "generation-test-1"


def test_default_langchain_invoker_maps_protocol_failure_to_bounded_invariant(
    monkeypatch,
):
    runnable_kwargs: dict[str, Any] = {}

    class Runnable:
        def invoke(self, *_args, **_kwargs):
            raise langchain_runtime.OpenRouterProtocolError()

    def runnable_factory(**kwargs):
        runnable_kwargs.update(kwargs)
        return Runnable()

    monkeypatch.setattr(
        canonicalizer_module,
        "structured_nemotron_runnable",
        runnable_factory,
    )

    with pytest.raises(ModelResponseError) as captured:
        canonicalizer_module._default_structured_invoker(
            {"type": "object", "properties": {}, "additionalProperties": False},
            "bounded system",
            "bounded user",
            "runtime-only-test-value",
            "orch-protocol-boundary",
            100,
        )

    assert captured.value.invariant == "provider_response_envelope"
    assert runnable_kwargs["reasoning"] == {"effort": "none"}
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


def test_provider_admission_timeout_is_zero_call_noncacheable_ledger_record(
    tmp_path: Path,
    monkeypatch,
):
    class Runnable:
        def invoke(self, *_args, **_kwargs):
            raise langchain_runtime.OpenRouterSendAdmissionTimeoutError()

    monkeypatch.setattr(
        canonicalizer_module,
        "structured_nemotron_runnable",
        lambda **_kwargs: Runnable(),
    )
    storage = Storage(str(tmp_path / "provider-concurrency-timeout.db"))
    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        api_key_provider=lambda: "runtime-only-test-value",
    )

    with pytest.raises(
        ModelResponseError,
        match="provider_concurrency_timeout",
    ) as captured:
        canonicalizer.canonicalize(
            package(),
            run_id="run-provider-concurrency-timeout",
            allowed_fact_catalog=catalog(),
        )

    assert captured.value.invariant == "provider_concurrency_timeout"
    assert captured.value.safe_context["outcome"] == "blocked_provider_concurrency"
    ledger = storage.model_calls()[0]
    assert ledger["call_count"] == 0
    assert ledger["outcome"] == "blocked_provider_concurrency"
    assert ledger["actual_cost_usd"] is None
    assert ledger["error_invariant"] == "provider_concurrency_timeout"
    assert storage.model_call_summary()["network_calls"] == 0
    assert storage.model_call_summary()["unknown_cost_call_count"] == 0
    assert storage.model_cost_committed_or_reserved() == 0
    assert storage.cached_model_output(ledger["cache_key"]) is None


def test_default_langchain_invoker_maps_upstream_rejection_to_safe_context(
    monkeypatch,
):
    class Runnable:
        def invoke(self, *_args, **_kwargs):
            raise langchain_runtime.OpenRouterUpstreamRejectionError(
                response_id="gen-1786483160-AAAAAAAAAAAAAAAAAAAA",
                provider_error_code=429,
            )

    monkeypatch.setattr(
        canonicalizer_module,
        "structured_nemotron_runnable",
        lambda **_kwargs: Runnable(),
    )

    with pytest.raises(ModelResponseError) as captured:
        canonicalizer_module._default_structured_invoker(
            {"type": "object", "properties": {}, "additionalProperties": False},
            "bounded system",
            "bounded user",
            "runtime-only-test-value",
            "orch-upstream-rejection",
            100,
        )

    assert captured.value.invariant == "provider_upstream_rejection"
    assert captured.value.safe_context == {
        "response_id": "gen-1786483160-AAAAAAAAAAAAAAAAAAAA",
        "provider_error_code": 429,
        "provider_boundary": "openrouter",
        "expected_upstream_provider": "Together",
    }
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


def test_canonical_upstream_rejection_retains_only_safe_unknown_cost_evidence(
    tmp_path: Path,
):
    inference_calls = 0

    def rejected_invoker(*_args):
        nonlocal inference_calls
        inference_calls += 1
        raise ModelResponseError(
            "provider_upstream_rejection invariant failed",
            invariant="provider_upstream_rejection",
            safe_context={
                "response_id": "gen-1786483161-BBBBBBBBBBBBBBBBBBBB",
                "provider_error_code": 429,
                "provider_boundary": "openrouter",
                "expected_upstream_provider": "Together",
            },
        )

    storage = Storage(str(tmp_path / "upstream-rejection.db"))
    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        structured_invoker=rejected_invoker,
        api_key_provider=lambda: "runtime-only-test-value",
    )

    with pytest.raises(ModelResponseError, match="provider_upstream_rejection"):
        canonicalizer.canonicalize(
            package(),
            run_id="run-upstream-rejection",
            allowed_fact_catalog=catalog(),
        )

    assert inference_calls == 1
    ledger = storage.sanitized_model_ledger()[0]
    assert ledger["outcome"] == "failed"
    assert ledger["error_invariant"] == "provider_upstream_rejection"
    assert ledger["response_id"] == "gen-1786483161-BBBBBBBBBBBBBBBBBBBB"
    assert ledger["provider_error_code"] == 429
    assert ledger["provider_boundary"] == "openrouter"
    assert ledger["expected_upstream_provider"] == "Together"
    assert ledger["actual_cost_usd"] is None
    assert "usage_source" not in ledger
    assert "prompt_tokens" not in ledger
    assert storage.cached_model_output(ledger["cache_key"]) is None
    assert storage.model_call_summary()["actual_cost_complete"] is False
    assert storage.model_call_summary()["unknown_cost_call_count"] == 1


def test_canonical_success_rejects_nonpinned_upstream_after_retaining_billing(
    tmp_path: Path,
):
    inference_calls = 0

    def transport(*_args):
        nonlocal inference_calls
        inference_calls += 1
        value = response()
        value["provider"] = "DeepInfra"
        value["openrouter_metadata"]["provider_name"] = "DeepInfra"
        return value

    storage = Storage(str(tmp_path / "wrong-upstream.db"))
    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=transport,
        api_key_provider=lambda: "runtime-only-test-value",
    )

    with pytest.raises(ModelResponseError, match="upstream_provider_policy"):
        canonicalizer.canonicalize(
            package(),
            run_id="run-wrong-upstream",
            allowed_fact_catalog=catalog(),
        )

    assert inference_calls == 1
    ledger = storage.sanitized_model_ledger()[0]
    assert ledger["outcome"] == "failed"
    assert ledger["error_invariant"] == "upstream_provider_policy"
    assert ledger["response_id"] == "generation-test-1"
    assert ledger["response_model"] == OPENROUTER_MODEL
    assert ledger["upstream_provider"] == "DeepInfra"
    assert ledger["actual_cost_usd"] == pytest.approx(0.0042)
    assert ledger["usage_source"] == "response"
    assert storage.cached_model_output(ledger["cache_key"]) is None


def test_canonicalizer_uses_synchronous_sdk_provider_without_generation_poll(
    tmp_path: Path,
    monkeypatch,
):
    requests: list[httpx.Request] = []
    sdk_clients: list[httpx.Client] = []
    metadata_calls = 0
    expected = response()

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={
                "id": expected["id"],
                "model": expected["model"],
                "object": "chat.completion",
                "created": 1786479000,
                "system_fingerprint": None,
                "openrouter_metadata": {
                    "attempt": 1,
                    "endpoints": {
                        "available": [
                            {
                                "model": OPENROUTER_MODEL,
                                "provider": "Together",
                                "selected": True,
                            }
                        ],
                        "total": 1,
                    },
                    "is_byok": False,
                    "region": None,
                    "requested": OPENROUTER_MODEL,
                    "strategy": "direct",
                    "summary": "RAW_CANONICAL_ROUTER_SUMMARY_SENTINEL",
                },
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": expected["choices"][0]["message"],
                    }
                ],
                "usage": expected["usage"],
            },
        )

    def instrumented_openrouter(**kwargs):
        client = httpx.Client(transport=httpx.MockTransport(handler))
        sdk_clients.append(client)
        return OpenRouter(client=client, **kwargs)

    def forbidden_metadata_transport(*_args):
        nonlocal metadata_calls
        metadata_calls += 1
        raise AssertionError("synchronous Together metadata must avoid generation polling")

    monkeypatch.setattr(langchain_runtime, "OpenRouter", instrumented_openrouter)
    storage = Storage(str(tmp_path / "synchronous-sdk-provider.db"))
    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        metadata_transport=forbidden_metadata_transport,
        api_key_provider=lambda: "runtime-only-test-value",
    )

    try:
        result = canonicalizer.canonicalize(
            package(),
            run_id="run-synchronous-sdk-provider",
            allowed_fact_catalog=catalog(),
        )
    finally:
        for client in sdk_clients:
            client.close()

    assert len(requests) == 1
    assert metadata_calls == 0
    request_body = json.loads(requests[0].content)
    assert request_body["provider"] == {
        "only": ["together"],
        "allow_fallbacks": False,
        "require_parameters": True,
        "data_collection": "deny",
    }
    assert "x_open_router_metadata" not in request_body
    assert requests[0].headers["X-OpenRouter-Metadata"] == "enabled"
    assert result["upstream_provider"] == "Together"
    assert result["usage_source"] == "response"
    ledger = storage.sanitized_model_ledger()[0]
    assert ledger["outcome"] == "succeeded"
    assert ledger["upstream_provider"] == "Together"
    assert ledger["actual_cost_usd"] == pytest.approx(0.0042)
    assert "RAW_CANONICAL_ROUTER_SUMMARY_SENTINEL" not in json.dumps(ledger)


def test_canonicalizer_replays_sdk_schema_drift_through_real_langchain_once(
    tmp_path: Path,
    monkeypatch,
):
    provider_calls = 0
    metadata_calls = 0
    expected = response()
    provider_payload = {
        "id": expected["id"],
        "model": expected["model"],
        "object": "chat.completion",
        "created": 1786479000,
        "openrouter_metadata": {
            "provider_name": "Together",
            "summary": "RAW_SCHEMA_DRIFT_ROUTER_SENTINEL",
        },
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": expected["choices"][0]["message"],
            }
        ],
        "usage": expected["usage"],
        # Deliberately no system_fingerprint: openrouter==0.11.46 rejects this
        # otherwise valid response before LangChain without the shared bridge.
    }

    class GeneratedSdkChat:
        def send(self, **_kwargs):
            nonlocal provider_calls
            provider_calls += 1
            response_value = httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json=provider_payload,
                request=httpx.Request(
                    "POST", "https://openrouter.ai/api/v1/chat/completions"
                ),
            )
            return unmarshal_json_response(components.ChatResult, response_value)

    class FakeOpenRouter:
        def __init__(self, **_kwargs):
            self.chat = GeneratedSdkChat()

    def metadata_transport(*_args):
        nonlocal metadata_calls
        metadata_calls += 1
        raise AssertionError("synchronous Together metadata must avoid generation polling")

    monkeypatch.setattr(langchain_runtime, "OpenRouter", FakeOpenRouter)
    storage = Storage(str(tmp_path / "sdk-drift-replay.db"))
    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        metadata_transport=metadata_transport,
        api_key_provider=lambda: "runtime-only-test-value",
    )

    result = canonicalizer.canonicalize(
        package(),
        run_id="run-sdk-drift-replay",
        allowed_fact_catalog=catalog(),
    )

    assert provider_calls == 1
    assert metadata_calls == 0
    assert result["facts"][0]["fact_id"] == "fact_report"
    assert result["upstream_provider"] == "Together"
    assert result["usage_source"] == "response"
    ledger = storage.sanitized_model_ledger()[0]
    assert ledger["outcome"] == "succeeded"
    assert ledger["response_id"] == "generation-test-1"
    assert ledger["actual_cost_usd"] == pytest.approx(0.0042)
    assert "RAW_SCHEMA_DRIFT_ROUTER_SENTINEL" not in json.dumps(ledger)


@pytest.mark.parametrize("response_variant", ["length", "nullable_choice_error"])
def test_canonical_sdk_drift_nonstop_retains_billing_before_rejection(
    tmp_path: Path,
    monkeypatch,
    response_variant: str,
):
    provider_calls = 0
    metadata_calls = 0
    expected = response()
    expected_finish_reason = "length" if response_variant == "length" else "error"
    choice = {
        "index": 0,
        "finish_reason": expected_finish_reason,
        "message": {
            **expected["choices"][0]["message"],
            "content": (
                expected["choices"][0]["message"]["content"]
                if response_variant == "length"
                else None
            ),
        },
    }
    if response_variant == "nullable_choice_error":
        choice["error"] = {"message": "RAW_NULL_CONTENT_SENTINEL"}
    provider_payload = {
        "id": expected["id"],
        "model": expected["model"],
        "object": "chat.completion",
        "created": 1786479000,
        "choices": [choice],
        "usage": expected["usage"],
    }

    class GeneratedSdkChat:
        def send(self, **_kwargs):
            nonlocal provider_calls
            provider_calls += 1
            response_value = httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json=provider_payload,
                request=httpx.Request(
                    "POST", "https://openrouter.ai/api/v1/chat/completions"
                ),
            )
            return unmarshal_json_response(components.ChatResult, response_value)

    class FakeOpenRouter:
        def __init__(self, **_kwargs):
            self.chat = GeneratedSdkChat()

    def metadata_transport(*_args):
        nonlocal metadata_calls
        metadata_calls += 1
        return generation_metadata()

    monkeypatch.setattr(langchain_runtime, "OpenRouter", FakeOpenRouter)
    storage = Storage(str(tmp_path / f"sdk-drift-{response_variant}.db"))
    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        metadata_transport=metadata_transport,
        api_key_provider=lambda: "runtime-only-test-value",
    )

    with pytest.raises(ModelResponseError, match="provider_finish_reason"):
        canonicalizer.canonicalize(
            package(),
            run_id=f"run-sdk-drift-{response_variant}",
            allowed_fact_catalog=catalog(),
        )

    assert provider_calls == 1
    assert metadata_calls == 1
    ledger = storage.sanitized_model_ledger()[0]
    assert ledger["outcome"] == "failed"
    assert ledger["error_invariant"] == "provider_finish_reason"
    assert ledger["response_id"] == "generation-test-1"
    assert ledger["finish_reason"] == expected_finish_reason
    assert ledger["actual_cost_usd"] == pytest.approx(0.0057)
    assert "RAW_NULL_CONTENT_SENTINEL" not in json.dumps(ledger)
    assert storage.cached_model_output(ledger["cache_key"]) is None


def test_missing_upstream_provider_fails_closed_when_metadata_is_incomplete(
    tmp_path: Path,
):
    inference_calls = 0
    metadata_calls = 0

    def structured_invoker(*_args):
        nonlocal inference_calls
        inference_calls += 1
        value = response()
        value.pop("provider")
        return value

    def incomplete_metadata(*_args):
        nonlocal metadata_calls
        metadata_calls += 1
        return {"data": {}}

    storage = Storage(str(tmp_path / "missing-provider-incomplete.db"))
    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        structured_invoker=structured_invoker,
        metadata_transport=incomplete_metadata,
        metadata_sleep=lambda _seconds: None,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(
        ModelResponseError,
        match="generation_metadata_completeness invariant failed",
    ):
        canonicalizer.canonicalize(
            package(),
            run_id="run-missing-provider-incomplete",
            allowed_fact_catalog=catalog(),
        )

    assert inference_calls == 1
    assert metadata_calls == 8
    ledger = storage.sanitized_model_ledger()[0]
    assert ledger["outcome"] == "failed"
    assert ledger["error_invariant"] == "generation_metadata_completeness"
    assert ledger["actual_cost_usd"] == pytest.approx(0.0042)
    assert ledger["usage_source"] == "response"
    assert ledger["response_id"] == "generation-test-1"
    assert ledger["response_model"] == OPENROUTER_MODEL
    assert ledger["finish_reason"] == "stop"
    assert ledger["prompt_tokens"] == 123
    assert ledger["completion_tokens"] == 45
    assert ledger["total_tokens"] == 168
    assert ledger["metadata_poll_count"] == 8
    assert ledger["metadata_latency_ms"] >= 0
    assert ledger["error_type"] != "KeyError"
    assert storage.cached_model_output(ledger["cache_key"]) is None


def test_missing_response_id_with_sync_usage_retains_charge_and_safe_context(
    tmp_path: Path,
):
    def transport(*_args):
        value = response()
        value.pop("id")
        return value

    storage = Storage(str(tmp_path / "missing-id.db"))
    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=transport,
        metadata_transport=lambda *_args: (_ for _ in ()).throw(
            AssertionError("metadata lookup requires a valid response ID")
        ),
        api_key_provider=lambda: "runtime-only-test-value",
    )
    with pytest.raises(ModelResponseError, match="response_identity") as caught:
        canonicalizer.canonicalize(
            package(), run_id="run-missing-id", allowed_fact_catalog=catalog()
        )
    ledger = storage.model_calls()[0]
    assert ledger["outcome"] == "failed"
    assert ledger["actual_cost_usd"] == pytest.approx(0.0042)
    assert ledger["prompt_tokens"] == 123
    assert "response_id" not in ledger
    assert caught.value.safe_context["call_id"] == ledger["call_id"]


def test_canonical_equal_accept_reject_minority_fails_and_never_caches(tmp_path: Path):
    calls = 0
    two = three_fact_catalog()[:2]

    def transport(*_args):
        nonlocal calls
        calls += 1
        value = response()
        output = json.loads(value["choices"][0]["message"]["content"])
        output["facts"]["fact_context"] = {
            "fact_id": "fact_context",
            "assertion_id": reference_assertion_for(two[1])["assertion_id"],
            "source_ref_ids": {"message": observable_ref_id(package())},
            "confidence": 1.01,
        }
        value["choices"][0]["message"]["content"] = json.dumps(output)
        return value

    storage = Storage(str(tmp_path / "minority.db"))
    canonicalizer = OpenRouterNemotronCanonicalizer(
        storage,
        transport=transport,
        api_key_provider=lambda: "runtime-only-test-value",
    )
    for index in range(2):
        with pytest.raises(ModelResponseError, match="hybrid_model_contribution"):
            canonicalizer.canonicalize(
                package(), run_id=f"run-minority-{index}", allowed_fact_catalog=two
            )
    assert calls == 2
    assert [item["outcome"] for item in storage.model_calls()] == ["failed", "failed"]
